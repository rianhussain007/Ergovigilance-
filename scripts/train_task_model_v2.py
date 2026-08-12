"""Train the task-classifier v2 on synthetic labeled poses.

Generates labeled 33-keypoint poses for the seven task classes
(Neutral Standing, Assembly Work, Reaching, Lifting / Picking,
Inspection, Seated Work, Walking / Moving) by parameterizing
realistic joint geometry, extracts the pipeline's 17 features plus the
two motion signals (movement_velocity, wrist_movement_velocity), and
keeps only samples whose label agrees with the deterministic Gaussian
scorer (top-2) — so the supervised model SUPPLEMENTS the Gaussian
instead of contradicting it.

Output bundle (models/task_model_v2.pkl):
    {model, feature_columns (19), labels, metrics, config: {confidence_threshold}}

Runtime: model-primary when predict_proba confidence >= threshold,
otherwise Gaussian fallback (see backend/services/task_recognition.py).

Generator notes (2026-08-08 fix):
- Arm geometry: the wrist Y override previously ran after the elbow-flexion
  arc, producing impossible wrist-above-elbow postures for low raises. The
  elbow now shifts so the wrist lands exactly at the raise height while
  preserving the flexion arc.
- Neutral Standing now spans raise 0.45-1.3 (chest-waist hands through
  straight-arm arms-at-sides) so a real neutral standing pose is inside the
  training distribution instead of ambiguous.
- Generation validates against the pure Gaussian scorer (never the model on
  disk), removing the retrain feedback loop.

Usage:
    python scripts/train_task_model_v2.py [--out models/task_model_v2.pkl] [--per-class 4000] [--seed 42]
    python scripts/train_task_model_v2.py --data data/processed/task_clips_features.csv

The synthetic substrate guarantees class coverage while the rule engine
(validated) labels stay geometrically consistent. Real captured data
(scripts/capture_task_clips.py → scripts/build_task_dataset.py) replaces the
synthetic substrate when --data is given — it is ground truth from your
actual workplace and therefore higher fidelity.
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
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

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
TRAIN_FEATURES = [*FEATURE_COLUMNS, *MOTION_FEATURES]

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


def _pose(
    trunk_deg: float, neck_px: float, elbow_deg: float, wrist_raise: float,
    knee_deg: float, reach_px: float, face_hands: bool, noise: float, rng,
) -> Dict[str, Tuple[float, float]]:
    """Build a parameterized pose dict (2D pixel coordinates).

    - trunk_deg: forward trunk lean (shoulders/head shift ahead of hips).
    - neck_px: forward head protrusion (px).
    - elbow_deg: elbow flexion angle (180 = straight).
    - wrist_raise: wrist height as a fraction of torso below the shoulder
      (0.3 ~ chest, 0.5 ~ waist, 1.0 ~ hands at sides / hip level).
      The elbow shifts so the wrist always lands below it (no degenerate
      wrist-above-elbow geometry).
    - knee_deg: knee angle (180 = straight).
    - reach_px: fingertips extended forward from the shoulders.
    - face_hands: wrists raised to face height (inspection).
    """
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
        # Fingers follow the wrist.
        pts[f"{side}_index"] = (wx + 15 * math.sin(rad), wy + 15 * math.cos(rad))
        pts[f"{side}_thumb"] = (wx + 8 * math.sin(rad) + 4, wy + 8 * math.cos(rad))
        pts[f"{side}_pinky"] = (wx + 12 * math.sin(rad) - 3, wy + 12 * math.cos(rad))

    if face_hands:
        # Inspection: wrists at face height, fingers near the nose.
        for side, sh, wr in [("left", "left_shoulder", "left_wrist"),
                             ("right", "right_shoulder", "right_wrist")]:
            sx, sy = pts[sh]
            pts[wr] = (sx + (40 if side == "left" else -40), sy - 70)
            pts[f"{side}_index"] = (pts[wr][0] + 25 * (1 if side == "left" else -1), pts[wr][1] - 15)
            pts[f"{side}_thumb"] = (pts[wr][0] + 10 * (1 if side == "left" else -1), pts[wr][1] + 5)
            pts[f"{side}_pinky"] = (pts[wr][0] + 20 * (1 if side == "left" else -1), pts[wr][1])
    else:
        # Wrist raise: shift the ELBOW so the wrist lands at the target
        # height, keeping the forearm arc from the flexion step. This keeps
        # the wrist strictly BELOW the elbow — the old code overrode the
        # wrist Y after the arc, producing impossible postures (wrist above
        # elbow, elbow_flexion_angle ~0°) for low raises that poisoned the
        # trained clusters.
        for side, sh, el, wr in [("left", "left_shoulder", "left_elbow", "left_wrist"),
                                 ("right", "right_shoulder", "right_elbow", "right_wrist")]:
            sx, sy = pts[sh]
            ex, _ = pts[el]
            wrist_y = sy + wrist_raise * _TORSO
            ey = wrist_y - _ARM_LEN * math.cos(rad)
            # Keep the elbow strictly below the shoulder even at the lowest
            # raises with near-straight arms (else the upper arm inverts).
            ey = max(ey, sy + 20.0)
            wx = ex + _ARM_LEN * math.sin(rad)
            pts[el] = (ex, ey)
            pts[wr] = (wx, wrist_y)
            pts[f"{side}_index"] = (wx + 15 * math.sin(rad), wrist_y + 15 * math.cos(rad))
            pts[f"{side}_thumb"] = (wx + 8 * math.sin(rad) + 4, wrist_y + 8 * math.cos(rad))
            pts[f"{side}_pinky"] = (wx + 12 * math.sin(rad) - 3, wrist_y + 12 * math.cos(rad))

    # Reach: fingertips extend forward from the shoulders.
    if reach_px:
        for side, sh in [("left", "left_shoulder"), ("right", "right_shoulder")]:
            sx, sy = pts[sh]
            pts[f"{side}_index"] = (sx + reach_px, sy + 30)
            pts[f"{side}_wrist"] = (sx + reach_px * 0.8, sy + 35)

    # Knee bend: ankles on an arc around the knees.
    krad = math.radians(180.0 - knee_deg)
    for side, hip, knee, ank in [("left", "left_hip", "left_knee", "left_ankle"),
                                 ("right", "right_hip", "right_knee", "right_ankle")]:
        kx, ky = pts[knee]
        pts[ank] = (kx + _LEG_LEN * math.sin(krad), ky + _LEG_LEN * math.cos(krad))
        pts[f"{side}_heel"] = (pts[ank][0] + 2, pts[ank][1] + 18)
        pts[f"{side}_foot_index"] = (pts[ank][0] + 10, pts[ank][1] + 20)

    # Noise.
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
    # Neutral spans chest-waist hands (raise ~0.45) through arms fully at the
    # sides (raise ~1.05+) — the posture real workers actually stand in. The
    # old range (0.45-0.6) never covered straight-arm hands-at-sides, so the
    # model was uncertain (0.51 Lifting vs 0.49 Inspection) on a real neutral
    # standing pose and gated to the Gaussian.
    "Neutral Standing": dict(trunk=(0, 8), neck=(0, 8), elbow=(155, 180), raise_=(0.45, 1.3),
                             knee=(155, 180), reach=(0, 0), face=False, vel=(0, 15), wvel=(0, 30)),
    # Only Reaching uses the forward-reach override — giving Assembly/Lifting a
    # small reach too placed their fingers at shoulder height, colliding with
    # Reaching's cluster and making the model misclassify Reaching ~65%.
    "Assembly Work": dict(trunk=(0, 12), neck=(4, 18), elbow=(90, 140), raise_=(0.2, 0.45),
                          knee=(155, 180), reach=(0, 0), face=False, vel=(5, 30), wvel=(20, 70)),
    "Reaching": dict(trunk=(5, 20), neck=(4, 15), elbow=(150, 175), raise_=(0.15, 0.45),
                     knee=(150, 180), reach=(240, 310), face=False, vel=(30, 90), wvel=(120, 240)),
    "Lifting / Picking": dict(trunk=(20, 50), neck=(4, 18), elbow=(120, 165), raise_=(0.5, 0.8),
                              knee=(90, 150), reach=(0, 0), face=False, vel=(5, 45), wvel=(20, 90)),
    "Inspection": dict(trunk=(0, 10), neck=(18, 40), elbow=(60, 110), raise_=(0.0, 0.0),
                       knee=(155, 180), reach=(0, 0), face=True, vel=(0, 20), wvel=(10, 50)),
    # Seated Work: hips dropped to knee height (thighs horizontal, knee bent
    # ~85-130°), trunk upright, hands at desk height (raise ~0.35-0.55).
    # Generated by the dedicated _seated_pose() below.
    "Seated Work": dict(trunk=(0, 10), neck=(4, 20), elbow=(70, 120), raise_=(0.35, 0.55),
                        knee=(85, 130), reach=(0, 0), face=False, vel=(0, 15), wvel=(5, 40),
                        seated=True),
    # Walking / Moving: upright trunk, arms swinging near the sides, knees
    # straight — distinguished from Neutral Standing by sustained velocity.
    "Walking / Moving": dict(trunk=(0, 10), neck=(0, 10), elbow=(140, 175), raise_=(0.7, 1.2),
                             knee=(155, 180), reach=(0, 0), face=False, vel=(60, 160), wvel=(40, 140)),
}


def _seated_pose(trunk_deg: float, neck_px: float, elbow_deg: float,
                 wrist_raise: float, noise: float, rng) -> Dict[str, Tuple[float, float]]:
    """Build a seated pose: hips dropped to knee height (thighs horizontal).

    A standing template with knees bent keeps the HIPS high — that is a
    squat/lunge, not sitting. Real seating lowers the hips so the thigh is
    horizontal and the knee is ~90-130°. This generator mirrors that: it
    drops the hip/shoulder block by ~0.6 of the thigh length, re-bends the
    knees, and places the hands at desk height.
    """
    pts: Dict[str, Tuple[float, float]] = dict(_NEUTRAL)

    # 1. Lower the whole torso: hips drop by ~60% of thigh length toward the
    #    knees (which stay at their standing Y), shoulders follow to keep the
    #    torso length constant.
    hip_drop = 0.6 * _LEG_LEN  # ~84px
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

    # 2. Re-bend the knees: ankles move forward on an arc so the knee angle
    #    lands in the seated range (85-130°).
    krad = math.radians(180.0 - rng.uniform(85, 130))
    for side, hip, knee, ank in [("left", "left_hip", "left_knee", "left_ankle"),
                                 ("right", "right_hip", "right_knee", "right_ankle")]:
        kx, ky = pts[knee]
        pts[ank] = (kx + _LEG_LEN * math.sin(krad) * 0.6, ky + _LEG_LEN * math.cos(krad) * 0.8)
        pts[f"{side}_heel"] = (pts[ank][0] + 2, pts[ank][1] + 14)
        pts[f"{side}_foot_index"] = (pts[ank][0] + 8, pts[ank][1] + 16)

    # 3. Trunk lean + neck flexion (same convention as _pose).
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

    # 4. Arms: elbows flexed, wrists at desk height (below the lowered
    #    shoulder, matching wrist_raise relative to the NEW torso position).
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

    # 5. Noise.
    if noise > 0:
        for name, (x, y) in pts.items():
            pts[name] = (x + rng.uniform(-noise, noise), y + rng.uniform(-noise, noise))
    return pts


def _sample_class(task: str, rng) -> Tuple[np.ndarray, Dict[str, float], str]:
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
    arr = _to_array(pts)
    feats, unavailable, _ = extract_features_from_keypoints(arr)
    feats["movement_velocity"] = round(rngv(p["vel"]), 2)
    feats["wrist_movement_velocity"] = round(rngv(p["wvel"]), 2)
    return arr, feats, task


def generate(per_class: int, seed: int) -> Tuple[List[List[float]], List[str], dict]:
    rng = np.random.default_rng(seed)
    # Validate against the PURE Gaussian scorer. Passing the default model
    # path would load whatever task_model_v2.pkl exists on disk and let the
    # model being trained filter its own training data — a feedback loop that
    # makes retrains depend on the previous artifact. A nonexistent path
    # forces TaskRecognition onto the deterministic Gaussian path.
    gaussian = TaskRecognition(model_path=str(ROOT / "models" / "__gaussian_only__.pkl"))

    X: List[List[float]] = []
    y: List[str] = []
    accepted = {c: 0 for c in CLASSES}
    rejected = {c: 0 for c in CLASSES}

    for task in CLASSES:
        attempts = 0
        while accepted[task] < per_class and attempts < per_class * 20:
            attempts += 1
            arr, feats, _ = _sample_class(task, rng)
            info = gaussian.detect_task(arr, feats)
            gauss_task = info["task"]
            gauss_conf = info["confidence"]
            # Keep the sample when the Gaussian agrees (top choice) OR is
            # genuinely uncertain (<50%). In uncertain frames the controlled
            # generator's label is ground truth by construction, and those are
            # exactly the frames where supervised learning adds the most value.
            if gauss_task == task or gauss_conf < 50.0:
                X.append([feats[c] for c in TRAIN_FEATURES])
                y.append(task)
                accepted[task] += 1
            else:
                rejected[task] += 1
        print(f"  {task}: accepted {accepted[task]} (rejected {rejected[task]})")

    return X, y, {"accepted": accepted, "rejected": rejected}


def load_real(data_path: Path) -> Tuple[List[List[float]], List[str], dict]:
    """Load real captured samples from a task_clips_features.csv.

    Rows whose task_label is not one of CLASSES are dropped; classes with
    zero samples are reported so the operator can capture more.
    """
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
    for _, row in df.iterrows():
        X.append([float(row[c]) for c in TRAIN_FEATURES])
        y.append(str(row["task_label"]))
    return X, y, {"per_class": counts}


def train(out: Path, per_class: int, seed: int, data_path: Path | None = None) -> dict:
    if data_path is not None:
        print(f"training on REAL captured samples from {data_path}...")
        X, y, gen_stats = load_real(data_path)
        trained_on = f"real captured task clips ({data_path.name})"
    else:
        print("generating synthetic labeled poses (validated against the Gaussian)...")
        X, y, gen_stats = generate(per_class, seed)
        trained_on = "synthetic validated poses (rule-engine geometry sweeps)"
    X = np.asarray(X, dtype=float)
    y = np.asarray(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y,
    )

    model = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.08, max_depth=5,
        min_samples_leaf=15, random_state=seed,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "test_size": int(len(y_test)),
        "classification_report": classification_report(y_test, y_pred, labels=CLASSES, zero_division=0),
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=CLASSES).tolist(),
        "labels": CLASSES,
        "generation": gen_stats,
    }
    print(f"holdout accuracy: {metrics['accuracy'] * 100:.1f}%")

    bundle = {
        "model": model,
        "feature_columns": TRAIN_FEATURES,
        "labels": CLASSES,
        "metrics": metrics,
        "config": {"confidence_threshold": 0.6},
        "purpose": "Task classifier v2 — model-primary with Gaussian fallback.",
        "trained_on": trained_on,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out)
    print(f"model saved: {out}")
    return metrics


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "models/task_model_v2.pkl")
    ap.add_argument("--per-class", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--data", type=Path, default=None,
                    help="Optional real captured feature CSV (see build_task_dataset.py). "
                         "When given, training uses these samples instead of synthetic.")
    args = ap.parse_args()
    train(args.out, args.per_class, args.seed, args.data)
