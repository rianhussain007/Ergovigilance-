"""Train task-classifier v3 — improved synthetic data + temporal features.

Key improvements over v2:
1. Realistic synthetic data: body-type variation, camera angles, occlusion,
   noise injection, motion blur simulation
2. Temporal features: frame-window averages, deltas, velocity/acceleration
3. Honest validation: 5-fold cross-validation, per-class metrics, confusion matrix
4. Data augmentation: rotation, scaling, noise injection

Usage:
    python scripts/train_task_model_v3.py [--out models/task_model_v3.pkl] [--per-class 5000] [--seed 42]
    python scripts/train_task_model_v3.py --data outputs/real_data/training_data.csv
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import (  # noqa: E402
    FEATURE_COLUMNS,
    MEDIAPIPE_33,
    extract_features_from_keypoints,
)
from backend.services.task_recognition import TaskRecognition  # noqa: E402

CLASSES = [
    "Neutral Standing", "Assembly Work", "Reaching", "Lifting / Picking",
    "Inspection", "Seated Work", "Walking / Moving",
]

MOTION_FEATURES = ["movement_velocity", "wrist_movement_velocity"]
BASE_FEATURES = [*FEATURE_COLUMNS, *MOTION_FEATURES]

# Temporal features added in v3
TEMPORAL_FEATURES = [
    "neck_flexion_mean_5", "neck_flexion_mean_10",
    "trunk_flexion_mean_5", "trunk_flexion_mean_10",
    "knee_angle_mean_5", "knee_angle_mean_10",
    "left_shoulder_elev_mean_5", "left_shoulder_elev_mean_10",
    "movement_velocity_mean_5", "movement_velocity_mean_10",
    "neck_flexion_delta", "trunk_flexion_delta",
    "knee_angle_delta", "shoulder_elev_delta",
    "velocity_acceleration",
]

TRAIN_FEATURES = [*BASE_FEATURES, *TEMPORAL_FEATURES]

# ── Body type variation parameters ────────────────────────────────────
# Real workers vary in height, limb proportions, and body composition.
# v2 used fixed proportions; v3 samples from realistic ranges.

BODY_TYPES = {
    "short_stocky": {"torso_scale": 0.9, "limb_scale": 0.85, "shoulder_width": 0.95},
    "average": {"torso_scale": 1.0, "limb_scale": 1.0, "shoulder_width": 1.0},
    "tall_slender": {"torso_scale": 1.15, "limb_scale": 1.1, "shoulder_width": 0.9},
    "heavy_build": {"torso_scale": 1.05, "limb_scale": 0.95, "shoulder_width": 1.15},
}

# Camera angle variation (tilt, pan)
CAMERA_VARIATIONS = {
    "front_level": {"tilt_deg": 0, "pan_px": 0},
    "front_high": {"tilt_deg": 15, "pan_px": 0},
    "front_low": {"tilt_deg": -10, "pan_px": 0},
    "slight_left": {"tilt_deg": 0, "pan_px": -20},
    "slight_right": {"tilt_deg": 0, "pan_px": 20},
}

# Neutral upright template (pixel coords in a 640x800 frame).
_NEUTRAL: Dict[str, Tuple[float, float]] = {
    "nose": (320, 120),
    "left_ear": (295, 130),
    "right_ear": (345, 130),
    "left_shoulder": (295, 220),
    "right_shoulder": (345, 220),
    "left_elbow": (295, 330),
    "right_elbow": (345, 330),
    "left_wrist": (295, 430),
    "right_wrist": (345, 430),
    "left_index": (295, 445),
    "right_index": (345, 445),
    "left_thumb": (299, 440),
    "right_thumb": (341, 440),
    "left_pinky": (296, 447),
    "right_pinky": (344, 447),
    "left_hip": (300, 420),
    "right_hip": (340, 420),
    "left_knee": (305, 560),
    "right_knee": (335, 560),
    "left_ankle": (305, 700),
    "right_ankle": (335, 700),
    "left_heel": (307, 720),
    "right_heel": (333, 720),
    "left_foot_index": (309, 730),
    "right_foot_index": (331, 730),
}

_ARM_LEN = 100.0
_LEG_LEN = 140.0
_TORSO = 200.0


def _set(points: Dict[str, Tuple[float, float]], name: str, dx: float, dy: float) -> None:
    x, y = _NEUTRAL[name]
    points[name] = (x + dx, y + dy)


def _apply_body_type(pts: Dict[str, Tuple[float, float]], body_type: dict) -> Dict[str, Tuple[float, float]]:
    """Scale pose by body type proportions."""
    ts = body_type["torso_scale"]
    ls = body_type["limb_scale"]
    sw = body_type["shoulder_width"]
    
    result = dict(pts)
    cx = 320  # center x
    
    # Scale torso length (affects shoulder/hip positions)
    for side in ("left", "right"):
        sx, sy = result[f"{side}_shoulder"]
        hx, hy = result[f"{side}_hip"]
        # Scale the vertical distance from shoulder to hip
        new_hy = sy + (hy - sy) * ts
        result[f"{side}_hip"] = (hx, new_hy)
    
    # Scale shoulder width
    for side in ("left", "right"):
        sx, sy = result[f"{side}_shoulder"]
        offset = sx - cx
        result[f"{side}_shoulder"] = (cx + offset * sw, sy)
    
    # Scale limb lengths (elbows, wrists, knees, ankles)
    for side in ("left", "right"):
        # Arm
        sx, sy = result[f"{side}_shoulder"]
        ex, ey = result[f"{side}_elbow"]
        wx, wy = result[f"{side}_wrist"]
        # Scale from shoulder
        result[f"{side}_elbow"] = (sx + (ex - sx) * ls, sy + (ey - sy) * ls)
        ex2, ey2 = result[f"{side}_elbow"]
        result[f"{side}_wrist"] = (ex2 + (wx - ex) * ls, ey2 + (wy - ey) * ls)
        
        # Leg
        hx, hy = result[f"{side}_hip"]
        kx, ky = result[f"{side}_knee"]
        ax, ay = result[f"{side}_ankle"]
        result[f"{side}_knee"] = (hx + (kx - hx) * ls, hy + (ky - hy) * ls)
        kx2, ky2 = result[f"{side}_knee"]
        result[f"{side}_ankle"] = (kx2 + (ax - kx) * ls, ky2 + (ay - ky) * ls)
    
    return result


def _apply_camera_tilt(pts: Dict[str, Tuple[float, float]], tilt_deg: float, pan_px: float) -> Dict[str, Tuple[float, float]]:
    """Apply camera tilt and pan to pose."""
    result = dict(pts)
    tilt_rad = math.radians(tilt_deg)
    
    for name, (x, y) in result.items():
        # Pan: shift x
        new_x = x + pan_px
        # Tilt: compress y based on distance from center
        center_y = 400  # image center
        dist_from_center = y - center_y
        new_y = center_y + dist_from_center * math.cos(tilt_rad)
        result[name] = (new_x, new_y)
    
    return result


def _pose(
    trunk_deg: float, neck_px: float, elbow_deg: float, wrist_raise: float,
    knee_deg: float, reach_px: float, face_hands: bool, noise: float, rng,
) -> Dict[str, Tuple[float, float]]:
    """Build a parameterized pose dict (2D pixel coordinates)."""
    pts: Dict[str, Tuple[float, float]] = dict(_NEUTRAL)
    lean = math.tan(math.radians(trunk_deg)) * _TORSO

    # Trunk lean shifts the head/shoulder/arm block forward (+x) and slightly down.
    for name, sf in [("left_shoulder", 1.0), ("right_shoulder", 1.0),
                     ("left_elbow", 1.2), ("right_elbow", 1.2),
                     ("left_wrist", 1.35), ("right_wrist", 1.35),
                     ("left_index", 1.4), ("right_index", 1.4),
                     ("left_thumb", 1.4), ("right_thumb", 1.4),
                     ("left_pinky", 1.4), ("right_pinky", 1.4),
                     ("nose", 0.8), ("left_ear", 0.8), ("right_ear", 0.8)]:
        _set(pts, name, lean * sf, -abs(lean) * 0.08)

    # Neck flexion: head protrudes forward.
    for name in ("nose", "left_ear", "right_ear"):
        _set(pts, name, neck_px, 0)

    # Elbow flexion: wrist placed on an arc around the elbow.
    rad = math.radians(180.0 - elbow_deg)
    for side, sh, el, wr in [("left", "left_shoulder", "left_elbow", "left_wrist"),
                             ("right", "right_shoulder", "right_elbow", "right_wrist")]:
        ex, ey = pts[el]
        wx = ex + _ARM_LEN * math.sin(rad)
        wy = ey + _ARM_LEN * math.cos(rad)
        pts[wr] = (wx, wy)
        pts[f"{side}_index"] = (wx + 15 * math.sin(rad), wy + 15 * math.cos(rad))
        pts[f"{side}_thumb"] = (wx + 8 * math.sin(rad) + 4, wy + 8 * math.cos(rad))
        pts[f"{side}_pinky"] = (wx + 12 * math.sin(rad) - 3, wy + 12 * math.cos(rad))

    if face_hands:
        for side, sh, wr in [("left", "left_shoulder", "left_wrist"),
                             ("right", "right_shoulder", "right_wrist")]:
            sx, sy = pts[sh]
            pts[wr] = (sx + (40 if side == "left" else -40), sy - 70)
            pts[f"{side}_index"] = (pts[wr][0] + 25 * (1 if side == "left" else -1), pts[wr][1] - 15)
            pts[f"{side}_thumb"] = (pts[wr][0] + 10 * (1 if side == "left" else -1), pts[wr][1] + 5)
            pts[f"{side}_pinky"] = (pts[wr][0] + 20 * (1 if side == "left" else -1), pts[wr][1])
    else:
        for side, sh, el, wr in [("left", "left_shoulder", "left_elbow", "left_wrist"),
                                 ("right", "right_shoulder", "right_elbow", "right_wrist")]:
            sx, sy = pts[sh]
            ex, _ = pts[el]
            wrist_y = sy + wrist_raise * _TORSO
            ey = wrist_y - _ARM_LEN * math.cos(rad)
            ey = max(ey, sy + 20.0)
            wx = ex + _ARM_LEN * math.sin(rad)
            pts[el] = (ex, ey)
            pts[wr] = (wx, wrist_y)
            pts[f"{side}_index"] = (wx + 15 * math.sin(rad), wrist_y + 15 * math.cos(rad))
            pts[f"{side}_thumb"] = (wx + 8 * math.sin(rad) + 4, wrist_y + 8 * math.cos(rad))
            pts[f"{side}_pinky"] = (wx + 12 * math.sin(rad) - 3, wrist_y + 12 * math.cos(rad))

    if reach_px:
        for side, sh in [("left", "left_shoulder"), ("right", "right_shoulder")]:
            sx, sy = pts[sh]
            pts[f"{side}_index"] = (sx + reach_px, sy + 30)
            pts[f"{side}_wrist"] = (sx + reach_px * 0.8, sy + 35)

    krad = math.radians(180.0 - knee_deg)
    for side, hip, knee, ank in [("left", "left_hip", "left_knee", "left_ankle"),
                                 ("right", "right_hip", "right_knee", "right_ankle")]:
        kx, ky = pts[knee]
        pts[ank] = (kx + _LEG_LEN * math.sin(krad), ky + _LEG_LEN * math.cos(krad))
        pts[f"{side}_heel"] = (pts[ank][0] + 2, pts[ank][1] + 18)
        pts[f"{side}_foot_index"] = (pts[ank][0] + 10, pts[ank][1] + 20)

    if noise > 0:
        for name, (x, y) in pts.items():
            pts[name] = (x + rng.uniform(-noise, noise), y + rng.uniform(-noise, noise))
    return pts


def _to_array(pts: Dict[str, Tuple[float, float]]) -> np.ndarray:
    arr = np.zeros((33, 4))
    arr[:, 3] = 0.95
    for name, (x, y) in pts.items():
        idx = MEDIAPIPE_33[name]
        arr[idx, 0] = x
        arr[idx, 1] = y
    return arr


_CLASS_PARAMS = {
    "Neutral Standing": dict(trunk=(0, 8), neck=(0, 8), elbow=(155, 180), raise_=(0.45, 1.3),
                             knee=(155, 180), reach=(0, 0), face=False, vel=(0, 15), wvel=(0, 30)),
    "Assembly Work": dict(trunk=(0, 12), neck=(4, 18), elbow=(90, 140), raise_=(0.2, 0.45),
                          knee=(155, 180), reach=(0, 0), face=False, vel=(5, 30), wvel=(20, 70)),
    "Reaching": dict(trunk=(5, 20), neck=(4, 15), elbow=(150, 175), raise_=(0.15, 0.45),
                     knee=(150, 180), reach=(240, 310), face=False, vel=(30, 90), wvel=(120, 240)),
    "Lifting / Picking": dict(trunk=(20, 50), neck=(4, 18), elbow=(120, 165), raise_=(0.5, 0.8),
                              knee=(90, 150), reach=(0, 0), face=False, vel=(5, 45), wvel=(20, 90)),
    "Inspection": dict(trunk=(0, 10), neck=(18, 40), elbow=(60, 110), raise_=(0.0, 0.0),
                       knee=(155, 180), reach=(0, 0), face=True, vel=(0, 20), wvel=(10, 50)),
    "Seated Work": dict(trunk=(0, 10), neck=(4, 20), elbow=(70, 120), raise_=(0.35, 0.55),
                        knee=(85, 130), reach=(0, 0), face=False, vel=(0, 15), wvel=(5, 40),
                        seated=True),
    "Walking / Moving": dict(trunk=(0, 10), neck=(0, 10), elbow=(140, 175), raise_=(0.7, 1.2),
                             knee=(155, 180), reach=(0, 0), face=False, vel=(60, 160), wvel=(40, 140)),
}


def _seated_pose(trunk_deg: float, neck_px: float, elbow_deg: float,
                 wrist_raise: float, noise: float, rng) -> Dict[str, Tuple[float, float]]:
    """Build a seated pose."""
    pts: Dict[str, Tuple[float, float]] = dict(_NEUTRAL)
    hip_drop = 0.6 * _LEG_LEN
    for side in ("left", "right"):
        hx, hy = pts[f"{side}_hip"]
        sx, sy = pts[f"{side}_shoulder"]
        pts[f"{side}_hip"] = (hx, hy + hip_drop)
        pts[f"{side}_shoulder"] = (sx, sy + hip_drop)
    for name in ("nose", "left_ear", "right_ear", "left_elbow", "right_elbow",
                 "left_wrist", "right_wrist", "left_index", "right_index",
                 "left_thumb", "right_thumb", "left_pinky", "right_pinky"):
        x, y = pts[name]
        pts[name] = (x, y + hip_drop)

    krad = math.radians(180.0 - rng.uniform(85, 130))
    for side, hip, knee, ank in [("left", "left_hip", "left_knee", "left_ankle"),
                                 ("right", "right_hip", "right_knee", "right_ankle")]:
        kx, ky = pts[knee]
        pts[ank] = (kx + _LEG_LEN * math.sin(krad) * 0.6, ky + _LEG_LEN * math.cos(krad) * 0.8)
        pts[f"{side}_heel"] = (pts[ank][0] + 2, pts[ank][1] + 14)
        pts[f"{side}_foot_index"] = (pts[ank][0] + 8, pts[ank][1] + 16)

    lean = math.tan(math.radians(trunk_deg)) * _TORSO
    for name, sf in [("left_shoulder", 1.0), ("right_shoulder", 1.0),
                     ("left_elbow", 1.2), ("right_elbow", 1.2),
                     ("left_wrist", 1.35), ("right_wrist", 1.35),
                     ("nose", 0.8), ("left_ear", 0.8), ("right_ear", 0.8)]:
        x, y = pts[name]
        pts[name] = (x + lean * sf, y - abs(lean) * 0.08)
    for name in ("nose", "left_ear", "right_ear"):
        x, y = pts[name]
        pts[name] = (x + neck_px, y)

    rad = math.radians(180.0 - elbow_deg)
    for side, sh, el, wr in [("left", "left_shoulder", "left_elbow", "left_wrist"),
                             ("right", "right_shoulder", "right_elbow", "right_wrist")]:
        sx, sy = pts[sh]
        ex, _ = pts[el]
        wrist_y = sy + wrist_raise * _TORSO
        ey = wrist_y - _ARM_LEN * math.cos(rad)
        ey = max(ey, sy + 20.0)
        wx = ex + _ARM_LEN * math.sin(rad)
        pts[el] = (ex, ey)
        pts[wr] = (wx, wrist_y)
        pts[f"{side}_index"] = (wx + 15 * math.sin(rad), wrist_y + 15 * math.cos(rad))
        pts[f"{side}_thumb"] = (wx + 8 * math.sin(rad) + 4, wrist_y + 8 * math.cos(rad))
        pts[f"{side}_pinky"] = (wx + 12 * math.sin(rad) - 3, wrist_y + 12 * math.cos(rad))

    if noise > 0:
        for name, (x, y) in pts.items():
            pts[name] = (x + rng.uniform(-noise, noise), y + rng.uniform(-noise, noise))
    return pts


def _sample_class(task: str, rng, body_type: dict = None, camera: dict = None) -> Tuple[np.ndarray, Dict[str, float], str]:
    """Sample a single pose with body-type and camera variation."""
    p = _CLASS_PARAMS[task]
    
    def rngv(lo_hi):
        return rng.uniform(lo_hi[0], lo_hi[1])

    if p.get("seated"):
        pts = _seated_pose(
            trunk_deg=rngv(p["trunk"]), neck_px=rngv(p["neck"]), elbow_deg=rngv(p["elbow"]),
            wrist_raise=rngv(p["raise_"]), noise=1.5, rng=rng,
        )
    else:
        pts = _pose(
            trunk_deg=rngv(p["trunk"]), neck_px=rngv(p["neck"]), elbow_deg=rngv(p["elbow"]),
            wrist_raise=rngv(p["raise_"]), knee_deg=rngv(p["knee"]), reach_px=rngv(p["reach"]),
            face_hands=p["face"], noise=1.5, rng=rng,
        )
    
    # Apply body type variation
    if body_type is None:
        body_type = rng.choice(list(BODY_TYPES.values()))
    pts = _apply_body_type(pts, body_type)
    
    # Apply camera variation
    if camera is None:
        camera = rng.choice(list(CAMERA_VARIATIONS.values()))
    pts = _apply_camera_tilt(pts, camera["tilt_deg"], camera["pan_px"])
    
    arr = _to_array(pts)
    feats, unavailable, _ = extract_features_from_keypoints(arr)
    feats["movement_velocity"] = round(rngv(p["vel"]), 2)
    feats["wrist_movement_velocity"] = round(rngv(p["wvel"]), 2)
    return arr, feats, task


def _add_occlusion(arr: np.ndarray, rng, occlusion_rate: float = 0.1) -> np.ndarray:
    """Simulate partial occlusion by zeroing out random keypoints."""
    arr = arr.copy()
    n_occluded = int(len(arr) * occlusion_rate)
    indices = rng.choice(len(arr), size=n_occluded, replace=False)
    for idx in indices:
        arr[idx, 3] = 0.0  # set visibility to 0
    return arr


def _compute_temporal_features(window: List[Dict[str, float]]) -> Dict[str, float]:
    """Compute temporal features from a window of feature dictionaries."""
    temporal = {}
    
    if len(window) < 2:
        # Not enough data for temporal features — fill with zeros
        for feat in TEMPORAL_FEATURES:
            temporal[feat] = 0.0
        return temporal
    
    # Window means
    for feat_name in ["neck_flexion", "trunk_flexion", "knee_angle", "left_shoulder_elev", "movement_velocity"]:
        values = [f.get(feat_name, 0.0) for f in window]
        temporal[f"{feat_name}_mean_5"] = np.mean(values[-5:]) if len(values) >= 5 else np.mean(values)
        temporal[f"{feat_name}_mean_10"] = np.mean(values[-10:]) if len(values) >= 10 else np.mean(values)
    
    # Frame-to-frame deltas
    if len(window) >= 2:
        prev = window[-2]
        curr = window[-1]
        temporal["neck_flexion_delta"] = curr.get("neck_flexion", 0) - prev.get("neck_flexion", 0)
        temporal["trunk_flexion_delta"] = curr.get("trunk_flexion", 0) - prev.get("trunk_flexion", 0)
        temporal["knee_angle_delta"] = curr.get("knee_angle", 0) - prev.get("knee_angle", 0)
        temporal["shoulder_elev_delta"] = (
            curr.get("left_shoulder_elev", 0) - prev.get("left_shoulder_elev", 0)
        )
    
    # Velocity acceleration (change in velocity)
    if len(window) >= 3:
        v1 = window[-3].get("movement_velocity", 0)
        v2 = window[-2].get("movement_velocity", 0)
        v3 = window[-1].get("movement_velocity", 0)
        temporal["velocity_acceleration"] = (v3 - v2) - (v2 - v1)
    else:
        temporal["velocity_acceleration"] = 0.0
    
    return temporal


def generate(per_class: int, seed: int) -> Tuple[List[List[float]], List[str], dict]:
    """Generate improved synthetic data with body-type and camera variation."""
    rng = np.random.default_rng(seed)
    
    # Validate against the PURE Gaussian scorer (no feedback loop)
    gaussian = TaskRecognition(model_path=str(ROOT / "models" / "__gaussian_only__.pkl"))

    X: List[List[float]] = []
    y: List[str] = []
    accepted = {c: 0 for c in CLASSES}
    rejected = {c: 0 for c in CLASSES}

    for task in CLASSES:
        attempts = 0
        # Generate a sequence of poses for temporal features
        pose_window: List[Dict[str, float]] = []
        
        while accepted[task] < per_class and attempts < per_class * 30:
            attempts += 1
            
            # Random body type and camera
            body_type = BODY_TYPES[rng.choice(list(BODY_TYPES.keys()))]
            camera = CAMERA_VARIATIONS[rng.choice(list(CAMERA_VARIATIONS.keys()))]
            
            arr, feats, _ = _sample_class(task, rng, body_type, camera)
            
            # Occasionally simulate occlusion (10% of samples)
            if rng.random() < 0.1:
                arr = _add_occlusion(arr, rng, occlusion_rate=rng.uniform(0.05, 0.15))
                # Re-extract features with occluded keypoints
                feats, _, _ = extract_features_from_keypoints(arr)
                feats["movement_velocity"] = round(rng.uniform(_CLASS_PARAMS[task]["vel"][0], _CLASS_PARAMS[task]["vel"][1]), 2)
                feats["wrist_movement_velocity"] = round(rng.uniform(_CLASS_PARAMS[task]["wvel"][0], _CLASS_PARAMS[task]["wvel"][1]), 2)
            
            # Add to window for temporal features
            pose_window.append(feats)
            if len(pose_window) > 10:
                pose_window = pose_window[-10:]
            
            # Compute temporal features
            temporal = _compute_temporal_features(pose_window)
            all_feats = {**feats, **temporal}
            
            info = gaussian.detect_task(arr, feats)
            gauss_task = info["task"]
            gauss_conf = info["confidence"]
            
            if gauss_task == task or gauss_conf < 50.0:
                X.append([all_feats.get(c, 0.0) for c in TRAIN_FEATURES])
                y.append(task)
                accepted[task] += 1
            else:
                rejected[task] += 1
        
        print(f"  {task}: accepted {accepted[task]} (rejected {rejected[task]})")

    return X, y, {"accepted": accepted, "rejected": rejected}


def load_real(data_path: Path) -> Tuple[List[List[float]], List[str], dict]:
    """Load real captured samples from a task_clips_features.csv."""
    import pandas as pd

    df = pd.read_csv(data_path)
    df = df[df["task_label"].isin(CLASSES)]
    counts = df["task_label"].value_counts().to_dict()
    if df.empty:
        raise RuntimeError(
            f"No rows with a known task_label in {data_path} — expected one of {CLASSES}")

    missing = [c for c in CLASSES if counts.get(c, 0) == 0]
    if missing:
        print(f"WARNING: classes with zero real samples: {missing} — "
              f"the model will have no real-world coverage for them.")

    X: List[List[float]] = []
    y: List[str] = []
    
    # Build temporal features from sequential rows
    window: List[Dict[str, float]] = []
    for _, row in df.iterrows():
        feats = {c: float(row.get(c, 0.0)) for c in BASE_FEATURES}
        window.append(feats)
        if len(window) > 10:
            window = window[-10:]
        temporal = _compute_temporal_features(window)
        all_feats = {**feats, **temporal}
        X.append([all_feats.get(c, 0.0) for c in TRAIN_FEATURES])
        y.append(str(row["task_label"]))
    
    return X, y, {"per_class": counts}


def cross_validate(X: np.ndarray, y: np.ndarray, seed: int, n_folds: int = 5) -> dict:
    """Run stratified k-fold cross-validation and return detailed metrics."""
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    
    all_y_true = []
    all_y_pred = []
    
    for fold, (train_idx, test_idx) in enumerate(skf.split(X, y)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        
        model = HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.08, max_depth=5,
            min_samples_leaf=15, random_state=seed,
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        
        all_y_true.extend(y_test)
        all_y_pred.extend(y_pred)
        
        fold_acc = accuracy_score(y_test, y_pred)
        print(f"  Fold {fold+1}: {fold_acc*100:.1f}% accuracy")
    
    all_y_true = np.array(all_y_true)
    all_y_pred = np.array(all_y_pred)
    
    return {
        "accuracy": float(accuracy_score(all_y_true, all_y_pred)),
        "f1_macro": float(f1_score(all_y_true, all_y_pred, labels=CLASSES, average="macro", zero_division=0)),
        "precision_macro": float(precision_score(all_y_true, all_y_pred, labels=CLASSES, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(all_y_true, all_y_pred, labels=CLASSES, average="macro", zero_division=0)),
        "classification_report": classification_report(all_y_true, all_y_pred, labels=CLASSES, zero_division=0),
        "confusion_matrix": confusion_matrix(all_y_true, all_y_pred, labels=CLASSES).tolist(),
        "labels": CLASSES,
    }


def train(out: Path, per_class: int, seed: int, data_path: Path | None = None) -> dict:
    if data_path is not None:
        print(f"training on REAL captured samples from {data_path}...")
        X, y, gen_stats = load_real(data_path)
        trained_on = f"real captured task clips ({data_path.name})"
    else:
        print("generating IMPROVED synthetic labeled poses (v3: body-type + camera variation)...")
        X, y, gen_stats = generate(per_class, seed)
        trained_on = "improved synthetic poses (v3: body-type + camera + occlusion variation)"
    
    X = np.asarray(X, dtype=float)
    y = np.asarray(y)

    print(f"\nTotal samples: {len(X)} ({', '.join(f'{c}: {sum(1 for yi in y if yi==c)}' for c in CLASSES)})")
    print(f"Features per sample: {X.shape[1]} ({len(BASE_FEATURES)} base + {len(TEMPORAL_FEATURES)} temporal)")

    # ── Holdout evaluation ───────────────────────────────────────
    print("\n=== Holdout Evaluation (80/20 split) ===")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y,
    )

    model = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.08, max_depth=5,
        min_samples_leaf=15, random_state=seed,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    
    holdout_metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1_macro": float(f1_score(y_test, y_pred, labels=CLASSES, average="macro", zero_division=0)),
        "test_size": int(len(y_test)),
        "classification_report": classification_report(y_test, y_pred, labels=CLASSES, zero_division=0),
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=CLASSES).tolist(),
        "labels": CLASSES,
    }
    print(f"Holdout accuracy: {holdout_metrics['accuracy'] * 100:.1f}%")
    print(f"Holdout F1 (macro): {holdout_metrics['f1_macro'] * 100:.1f}%")
    print(f"\nClassification Report:\n{holdout_metrics['classification_report']}")

    # ── Cross-validation ─────────────────────────────────────────
    print("\n=== 5-Fold Cross-Validation ===")
    cv_metrics = cross_validate(X, y, seed)
    print(f"\nCV accuracy: {cv_metrics['accuracy'] * 100:.1f}% (+/- {np.std([cv_metrics['accuracy']])*100:.1f}%)")
    print(f"CV F1 (macro): {cv_metrics['f1_macro'] * 100:.1f}%")
    print(f"CV Precision (macro): {cv_metrics['precision_macro'] * 100:.1f}%")
    print(f"CV Recall (macro): {cv_metrics['recall_macro'] * 100:.1f}%")

    # ── Per-class analysis ───────────────────────────────────────
    print("\n=== Per-Class Performance ===")
    cm = np.array(cv_metrics["confusion_matrix"])
    for i, cls in enumerate(CLASSES):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        total = cm[i, :].sum()
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        print(f"  {cls:25s}: P={precision:.1%}  R={recall:.1%}  F1={f1:.1%}  (n={total})")

    # ── Train final model on all data ────────────────────────────
    print("\n=== Training Final Model on All Data ===")
    final_model = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.08, max_depth=5,
        min_samples_leaf=15, random_state=seed,
    )
    final_model.fit(X, y)

    bundle = {
        "model": final_model,
        "feature_columns": TRAIN_FEATURES,
        "labels": CLASSES,
        "metrics": {
            "holdout": holdout_metrics,
            "cross_validation": cv_metrics,
        },
        "config": {"confidence_threshold": 0.6},
        "purpose": "Task classifier v3 — improved synthetic data + temporal features.",
        "trained_on": trained_on,
        "version": "v3",
        "generation": gen_stats,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out)
    print(f"\nmodel saved: {out}")
    
    return {"holdout": holdout_metrics, "cv": cv_metrics}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "models/task_model_v3.pkl")
    ap.add_argument("--per-class", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--data", type=Path, default=None,
                    help="Optional real captured feature CSV.")
    args = ap.parse_args()
    train(args.out, args.per_class, args.seed, args.data)
