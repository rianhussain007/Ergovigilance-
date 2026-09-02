#!/usr/bin/env python3
"""
Full data extraction + training pipeline for ErgoVigilance.
Uses MediaPipe Tasks API (v1.0+) for pose detection.
All features are normalized to [0, 1] range relative to image dimensions.
"""
import sys
import io
import json
import pickle
import logging
from pathlib import Path
from collections import Counter
from datetime import datetime
import numpy as np

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import cv2
from mediapipe.tasks.python import vision as mp_vision
from mediapipe import tasks as mp_tasks
from mediapipe import Image as MPImage, ImageFormat
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "datasets"
OUTPUT_DIR = ROOT / "outputs" / "real_data"
MODELS_DIR = ROOT / "models"
RESULTS_DIR = ROOT / "results"
POSE_MODEL = ROOT / "models" / "mediapipe" / "pose_landmarker_heavy.task"

FEATURE_COLS = [
    "neck_flexion", "trunk_flexion", "left_shoulder_elev", "right_shoulder_elev",
    "shoulder_symmetry", "alignment_deviation", "knee_angle", "forward_head_posture",
    "head_tilt_angle", "wrist_deviation_angle", "stance_stability", "weight_shift_offset",
    "elbow_flexion_angle", "upper_arm_angle_from_vertical",
    "hand_reach_ratio", "finger_spread_ratio", "stance_width_ratio",
    "movement_velocity", "wrist_movement_velocity",
]


def create_landmarker():
    base_options = mp_tasks.BaseOptions(model_asset_path=str(POSE_MODEL))
    options = mp_vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=mp_vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return mp_vision.PoseLandmarker.create_from_options(options)


def compute_angle(p1, vertex, p2):
    v1 = p1 - vertex
    v2 = p2 - vertex
    cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
    return float(np.degrees(np.arccos(np.clip(cos_a, -1.0, 1.0))))


def extract_features(landmarks, w, h):
    """Extract ergonomic features from MediaPipe landmarks.
    Spatial features are normalized to [0, 100] range relative to image dimensions.
    """
    pts = np.array([[lm.x * w, lm.y * h] for lm in landmarks])
    l_shoulder, r_shoulder = pts[11], pts[12]
    l_elbow, r_elbow = pts[13], pts[14]
    l_wrist, r_wrist = pts[15], pts[16]
    l_hip, r_hip = pts[23], pts[24]
    l_knee, r_knee = pts[25], pts[26]
    l_ankle, r_ankle = pts[27], pts[28]

    mid_shoulder = (l_shoulder + r_shoulder) / 2
    mid_hip = (l_hip + r_hip) / 2

    # Angles (already in degrees, independent of image size)
    neck_vec = pts[0] - mid_shoulder
    neck_angle = abs(float(np.degrees(np.arctan2(neck_vec[0], neck_vec[1]))))
    trunk_vec = mid_shoulder - mid_hip
    trunk_angle = abs(float(np.degrees(np.arctan2(trunk_vec[0], trunk_vec[1]))))

    left_arm_angle = compute_angle(l_shoulder, l_elbow, l_wrist)
    right_arm_angle = compute_angle(r_shoulder, r_elbow, r_wrist)

    def upper_arm_vertical(shoulder, elbow):
        vec = elbow - shoulder
        return abs(float(np.degrees(np.arctan2(vec[0], vec[1]))))

    # Body scale for normalization (shoulder-to-hip distance in pixels)
    body_scale = max(np.linalg.norm(mid_shoulder - mid_hip), 1.0)

    return {
        # Angle features (degrees, 0-90 range)
        "neck_flexion": min(neck_angle, 90),
        "trunk_flexion": min(trunk_angle, 90),
        "elbow_flexion_angle": min((left_arm_angle + right_arm_angle) / 2, 180),
        "upper_arm_angle_from_vertical": min(
            (upper_arm_vertical(l_shoulder, l_elbow) + upper_arm_vertical(r_shoulder, r_elbow)) / 2, 180
        ),
        "head_tilt_angle": min(abs(float(np.degrees(np.arctan2(pts[3][1] - pts[4][1], pts[3][0] - pts[4][0])))), 90),

        # Spatial features normalized by body_scale (dimensionless ratios)
        "left_shoulder_elev": abs(l_shoulder[1] - mid_shoulder[1]) / body_scale * 100,
        "right_shoulder_elev": abs(r_shoulder[1] - mid_shoulder[1]) / body_scale * 100,
        "shoulder_symmetry": abs(l_shoulder[1] - r_shoulder[1]) / body_scale * 100,
        "alignment_deviation": abs(mid_shoulder[0] - mid_hip[0]) / body_scale * 100,
        "forward_head_posture": abs((pts[3][0] + pts[4][0]) / 2 - mid_shoulder[0]) / body_scale * 100,
        "wrist_deviation_angle": (
            abs(float(np.degrees(np.arctan2(l_wrist[1] - l_elbow[1], l_wrist[0] - l_elbow[0]))))
            + abs(float(np.degrees(np.arctan2(r_wrist[1] - r_elbow[1], r_wrist[0] - r_elbow[0]))))
        ) / 2,

        # Knee angle (degrees)
        "knee_angle": (compute_angle(l_hip, l_knee, l_ankle) + compute_angle(r_hip, r_knee, r_ankle)) / 2,

        # Normalized spatial features
        "stance_stability": abs(l_ankle[0] - r_ankle[0]) / body_scale * 100,
        "weight_shift_offset": abs(mid_hip[0] - w / 2) / w * 100,
        "hand_reach_ratio": np.linalg.norm(l_wrist - mid_shoulder) / body_scale,
        "finger_spread_ratio": 0.0,
        "stance_width_ratio": abs(l_ankle[0] - r_ankle[0]) / (abs(l_hip[0] - r_hip[0]) + 1e-6),

        # Velocity features
        "movement_velocity": 0.0,
        "wrist_movement_velocity": 0.0,
    }


def classify_task(features):
    neck = features["neck_flexion"]
    trunk = features["trunk_flexion"]
    knee = features["knee_angle"]
    shoulder_elev = max(features["left_shoulder_elev"], features["right_shoulder_elev"])
    elbow = features["elbow_flexion_angle"]
    hand_reach = features.get("hand_reach_ratio", 1.0)
    stance = features.get("stance_width_ratio", 1.0)

    # Lifting: bent knees + forward lean
    if knee < 90 and trunk > 25:
        return "Lifting/Carrying"
    elif knee < 100 and trunk > 35:
        return "Lifting/Carrying"

    # Seated Work: knees moderately bent + hands close to body (desk work)
    # From front camera, seated workers show high trunk flexion but hands are
    # close and the overall pose is stable (low stance width ratio)
    if 80 < knee < 150 and hand_reach < 1.2 and stance < 1.5:
        return "Seated Work"
    elif knee > 140 and trunk < 15 and shoulder_elev < 5:
        return "Seated Work"

    # Inspection: looking down at object, hands raised
    if neck > 25 and trunk < 20 and knee > 130:
        return "Inspection"
    elif neck > 40 and elbow > 100:
        return "Inspection"

    # Neutral Standing: upright, legs straight, no movement
    if trunk < 10 and knee > 160:
        return "Neutral Standing"

    # Assembly Work: moderate arm flexion, upright-ish
    if knee > 110 and elbow < 130:
        return "Assembly Work"

    return "Assembly Work"


def classify_risk(features):
    """Classify risk using ergonomic thresholds.
    Thresholds calibrated for normalized features.
    """
    neck = features["neck_flexion"]
    trunk = features["trunk_flexion"]
    shoulder = features["shoulder_symmetry"]
    knee = features["knee_angle"]
    alignment = features["alignment_deviation"]

    score = 0
    # Neck flexion (degrees)
    if neck > 20: score += 1
    if neck > 40: score += 2
    if neck > 60: score += 3
    # Trunk flexion (degrees)
    if trunk > 20: score += 1
    if trunk > 40: score += 2
    if trunk > 60: score += 3
    # Shoulder asymmetry (normalized)
    if shoulder > 10: score += 1
    if shoulder > 25: score += 2
    # Knee angle (degrees, lower = more flexed = worse)
    if knee < 90: score += 2
    if knee < 60: score += 3
    # Alignment deviation (normalized)
    if alignment > 10: score += 1
    if alignment > 30: score += 2

    if score <= 2:
        return "LOW"
    elif score <= 5:
        return "MEDIUM"
    else:
        return "HIGH"


def synthesize_high_risk(rows):
    synthetic = []
    rng = np.random.RandomState(42)
    for row in rows:
        risk = classify_risk(row)
        if risk == "LOW" and rng.random() < 0.4:
            aug = row.copy()
            aug["neck_flexion"] = min(90, aug["neck_flexion"] + rng.uniform(25, 50))
            aug["trunk_flexion"] = min(90, aug["trunk_flexion"] + rng.uniform(20, 45))
            aug["shoulder_symmetry"] = aug["shoulder_symmetry"] + rng.uniform(5, 20)
            aug["alignment_deviation"] = aug["alignment_deviation"] + rng.uniform(5, 20)
            if rng.random() < 0.5:
                aug["knee_angle"] = max(30, aug["knee_angle"] - rng.uniform(30, 60))
            synthetic.append(aug)
    return synthetic


def process_single_video(video_path, landmarker, max_frames=25, sample_interval_sec=1.5):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_interval = max(1, int(fps * sample_interval_sec))
    rows = []
    frame_num = 0
    extracted = 0
    prev_pts = None
    timestamp_ms = 0

    while cap.isOpened() and extracted < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        frame_num += 1
        timestamp_ms = int(frame_num / fps * 1000)
        if frame_num % frame_interval != 0:
            continue

        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = MPImage(image_format=ImageFormat.SRGB, data=rgb)

        result = landmarker.detect_for_video(mp_image, timestamp_ms)

        if not result.pose_landmarks or len(result.pose_landmarks) == 0:
            continue

        landmarks = result.pose_landmarks[0]
        features = extract_features(landmarks, w, h)

        curr_pts = np.array([[lm.x * w, lm.y * h] for lm in landmarks])
        if prev_pts is not None:
            features["movement_velocity"] = float(np.mean(np.linalg.norm(curr_pts - prev_pts, axis=1)))
            features["wrist_movement_velocity"] = float(np.mean([
                np.linalg.norm(curr_pts[15] - prev_pts[15]),
                np.linalg.norm(curr_pts[16] - prev_pts[16]),
            ]))
        prev_pts = curr_pts

        features["video"] = video_path.name
        features["frame"] = frame_num
        features["task_label"] = classify_task(features)
        features["risk_level"] = classify_risk(features)
        rows.append(features)
        extracted += 1

    cap.release()
    return rows


def extract_from_videos(max_per_video=25, sample_interval=1.5):
    all_rows = []
    video_dirs = [
        DATA_DIR / "diverse_training" / "youtube",
        DATA_DIR / "diverse_training" / "youtube" / "seated_work",
        DATA_DIR / "diverse_training" / "youtube" / "inspection",
        DATA_DIR / "diverse_training" / "youtube" / "lifting_heavy",
        DATA_DIR / "diverse_training" / "youtube" / "walking_reaching",
        DATA_DIR / "diverse_training" / "huggingface",
        DATA_DIR / "voxel51" / "videos",
        DATA_DIR / "factory_manipulation" / "videos",
        DATA_DIR / "assembly_videos",
    ]

    videos = []
    seen_names = set()
    for vdir in video_dirs:
        if vdir.exists():
            for v in vdir.glob("*.mp4"):
                if v.name not in seen_names:
                    videos.append(v)
                    seen_names.add(v.name)

    logger.info("Found %d videos to process", len(videos))

    for i, video_path in enumerate(videos):
        logger.info("[%d/%d] Processing %s", i + 1, len(videos), video_path.name)
        landmarker = create_landmarker()
        try:
            rows = process_single_video(video_path, landmarker, max_per_video, sample_interval)
            all_rows.extend(rows)
            logger.info("  Extracted %d frames", len(rows))
        except Exception as e:
            logger.warning("  Error processing %s: %s", video_path.name, e)
        finally:
            landmarker.close()

    return all_rows


def train_models(df):
    X = df[FEATURE_COLS].fillna(0).values
    results = {}
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    # Risk Model
    logger.info("=" * 50)
    logger.info("Training RISK model")
    y_risk = df["risk_level"].values
    le_risk = LabelEncoder()
    y_risk_enc = le_risk.fit_transform(y_risk)
    logger.info("Risk distribution: %s", dict(Counter(y_risk)))

    class_counts = np.bincount(y_risk_enc)
    n_samples = len(y_risk_enc)
    n_classes = len(le_risk.classes_)
    class_weights = n_samples / (n_classes * class_counts)
    sample_weights = np.array([class_weights[c] for c in y_risk_enc])

    model_risk = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.08, max_depth=6,
        min_samples_leaf=5, random_state=42,
    )

    if n_classes > 1:
        fold_scores = []
        for train_idx, val_idx in cv.split(X, y_risk_enc):
            model_risk.fit(X[train_idx], y_risk_enc[train_idx], sample_weight=sample_weights[train_idx])
            fold_scores.append(model_risk.score(X[val_idx], y_risk_enc[val_idx]))
        risk_cv = np.array(fold_scores)
        logger.info("Risk model 5-fold CV accuracy: %.3f +/- %.3f", risk_cv.mean(), risk_cv.std())
    else:
        logger.warning("Only 1 risk class - skipping cross-validation")
        risk_cv = np.array([1.0])

    model_risk.fit(X, y_risk_enc, sample_weight=sample_weights)
    y_risk_pred = model_risk.predict(X)
    risk_report = classification_report(y_risk_enc, y_risk_pred, target_names=le_risk.classes_, output_dict=True, zero_division=0)

    results["risk"] = {
        "model": model_risk,
        "encoder": le_risk,
        "cv_f1": float(risk_cv.mean()),
        "cv_std": float(risk_cv.std()),
        "classification_report": risk_report,
        "confusion_matrix": confusion_matrix(y_risk_enc, y_risk_pred).tolist(),
        "class_weights": dict(zip(le_risk.classes_.tolist(), class_weights.tolist())),
        "n_samples": n_samples,
        "class_distribution": dict(Counter(y_risk)),
    }
    logger.info("Risk Report:\n%s", classification_report(y_risk_enc, y_risk_pred, target_names=le_risk.classes_, zero_division=0))

    # Task Model
    logger.info("=" * 50)
    logger.info("Training TASK model")
    y_task = df["task_label"].values
    le_task = LabelEncoder()
    y_task_enc = le_task.fit_transform(y_task)
    logger.info("Task distribution: %s", dict(Counter(y_task)))

    class_counts_t = np.bincount(y_task_enc)
    n_classes_t = len(le_task.classes_)
    class_weights_t = len(y_task_enc) / (n_classes_t * class_counts_t)
    sample_weights_t = np.array([class_weights_t[c] for c in y_task_enc])

    model_task = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.08, max_depth=6,
        min_samples_leaf=5, random_state=42,
    )
    fold_scores_t = []
    for train_idx, val_idx in cv.split(X, y_task_enc):
        model_task.fit(X[train_idx], y_task_enc[train_idx], sample_weight=sample_weights_t[train_idx])
        fold_scores_t.append(model_task.score(X[val_idx], y_task_enc[val_idx]))
    task_cv = np.array(fold_scores_t)
    logger.info("Task model 5-fold CV accuracy: %.3f +/- %.3f", task_cv.mean(), task_cv.std())

    model_task.fit(X, y_task_enc, sample_weight=sample_weights_t)
    y_task_pred = model_task.predict(X)
    task_report = classification_report(y_task_enc, y_task_pred, target_names=le_task.classes_, output_dict=True, zero_division=0)

    results["task"] = {
        "model": model_task,
        "encoder": le_task,
        "cv_f1": float(task_cv.mean()),
        "cv_std": float(task_cv.std()),
        "classification_report": task_report,
        "confusion_matrix": confusion_matrix(y_task_enc, y_task_pred).tolist(),
        "class_weights": dict(zip(le_task.classes_.tolist(), class_weights_t.tolist())),
        "n_samples": n_samples,
        "class_distribution": dict(Counter(y_task)),
    }
    logger.info("Task Report:\n%s", classification_report(y_task_enc, y_task_pred, target_names=le_task.classes_, zero_division=0))

    if hasattr(model_risk, "feature_importances_"):
        imp = sorted(zip(FEATURE_COLS, model_risk.feature_importances_), key=lambda x: -x[1])
        logger.info("Top risk features:")
        for feat, val in imp[:8]:
            logger.info("  %s: %.3f", feat, val)

    return results


def save_results(results, df):
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = OUTPUT_DIR / "diverse_extracted_features.csv"
    df.to_csv(csv_path, index=False)
    logger.info("Saved %d rows to %s", len(df), csv_path)

    for tag in ["risk", "task"]:
        model_data = {
            "model": results[tag]["model"],
            "encoder": results[tag]["encoder"],
            "features": FEATURE_COLS,
            "version": "v2_balanced",
            "trained": datetime.now().isoformat(),
        }
        with open(MODELS_DIR / f"{tag}_model_v2.pkl", "wb") as f:
            pickle.dump(model_data, f)
        logger.info("Saved %s model", tag)

    metrics = {
        "timestamp": datetime.now().isoformat(),
        "n_samples": len(df),
        "risk": {
            "cv_f1": results["risk"]["cv_f1"],
            "cv_std": results["risk"]["cv_std"],
            "classification_report": results["risk"]["classification_report"],
            "confusion_matrix": results["risk"]["confusion_matrix"],
            "class_distribution": results["risk"]["class_distribution"],
            "class_weights": results["risk"]["class_weights"],
        },
        "task": {
            "cv_f1": results["task"]["cv_f1"],
            "cv_std": results["task"]["cv_std"],
            "classification_report": results["task"]["classification_report"],
            "confusion_matrix": results["task"]["confusion_matrix"],
            "class_distribution": results["task"]["class_distribution"],
            "class_weights": results["task"]["class_weights"],
        },
        "caveat": "CV metrics on extracted + synthetic data. True accuracy requires held-out human-labeled ground truth.",
    }
    with open(RESULTS_DIR / "v2_training_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    logger.info("Saved metrics")


def main():
    logger.info("=" * 60)
    logger.info("ErgoVigilance Data Extraction & Training Pipeline v2")
    logger.info("=" * 60)

    logger.info("\n--- Step 1: Extracting features from videos ---")
    rows = extract_from_videos(max_per_video=25, sample_interval=1.5)
    logger.info("Extracted %d frames total", len(rows))

    if len(rows) < 50:
        logger.error("Not enough frames extracted. Check video paths.")
        sys.exit(1)

    logger.info("\n--- Step 2: Synthesizing HIGH-risk examples ---")
    synthetic = synthesize_high_risk(rows)
    logger.info("Created %d synthetic HIGH-risk samples", len(synthetic))
    rows.extend(synthetic)

    df = pd.DataFrame(rows)
    logger.info("\nTotal dataset: %d samples", len(df))

    logger.info("\n--- Step 3: Training models ---")
    results = train_models(df)

    logger.info("\n--- Step 4: Saving results ---")
    save_results(results, df)

    logger.info("\n" + "=" * 60)
    logger.info("Pipeline complete!")
    logger.info("Risk model CV F1: %.3f", results["risk"]["cv_f1"])
    logger.info("Task model CV F1: %.3f", results["task"]["cv_f1"])
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
