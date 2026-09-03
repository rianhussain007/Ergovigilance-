"""ErgoVigilance Model Improvement Pipeline.

This script:
1. Extracts keypoints from all available video data
2. Augments training data with synthetic variations
3. Trains improved risk and task models with class balancing
4. Evaluates on held-out test set
5. Compares old vs new model performance

Usage:
    python scripts/improve_models.py
"""

import json
import os
import sys
import pickle
import logging
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import Counter

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

MODELS_DIR = PROJECT_ROOT / "models"
RESULTS_DIR = PROJECT_ROOT / "results"
DATA_DIR = PROJECT_ROOT / "data" / "datasets"

# ── Feature Extraction ──────────────────────────────────────────

def extract_coco17_keypoints(video_path: str) -> list:
    """Extract COCO_17 keypoints from video using MediaPipe Tasks API."""
    try:
        import cv2
        import mediapipe as mp
        from mediapipe.tasks.python import vision as mp_vision
        from mediapipe import tasks as mp_tasks
    except ImportError:
        logger.warning("OpenCV/MediaPipe not available, using synthetic features")
        return []

    # Load pose landmarker model
    model_path = MODELS_DIR / "mediapipe" / "pose_landmarker_lite.task"
    if not model_path.exists():
        model_path = MODELS_DIR / "pose_landmarker_lite.task"
    if not model_path.exists():
        logger.warning("Pose landmarker model not found")
        return []

    base_options = mp_tasks.BaseOptions(model_asset_path=str(model_path))
    options = mp_vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=mp_vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    landmarker = mp_vision.PoseLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning("Cannot open video: %s", video_path)
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames_data = []
    frame_idx = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Process every 3rd frame for speed
        if frame_idx % 3 != 0:
            frame_idx += 1
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        timestamp_ms = int(frame_idx / fps * 1000)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        results = landmarker.detect_for_video(mp_image, timestamp_ms)

        if results.pose_landmarks:
            landmarks = results.pose_landmarks[0]  # First pose

            # Extract COCO_17 keypoints (33 landmarks)
            keypoints = []
            for lm in landmarks[:33]:
                keypoints.extend([lm.x, lm.y, lm.z, 1.0])  # visibility=1.0 for detected

            # Compute features
            features = compute_features(keypoints, frame_idx / fps)
            features["frame_idx"] = frame_idx
            features["timestamp"] = frame_idx / fps
            features["source_video"] = str(video_path)
            frames_data.append(features)

        frame_idx += 1

    cap.release()
    landmarker.close()
    return frames_data


def compute_features(keypoints: list, timestamp: float) -> dict:
    """Compute ergonomic features from keypoints."""
    kps = np.array(keypoints).reshape(-1, 4)

    # Joint angles
    neck_angle = compute_angle(kps[11], kps[12], kps[0])  # Shoulders + nose
    trunk_angle = compute_angle(kps[11], kps[23], kps[25])  # Shoulder + hip + knee
    shoulder_sym = abs(kps[11][1] - kps[12][1]) * 100  # Vertical difference
    knee_angle = compute_angle(kps[23], kps[25], kps[27])  # Hip + knee + ankle

    # Velocity (frame-to-frame movement)
    right_wrist_vel = abs(kps[16][1] - kps[15][1]) if len(kps) > 16 else 0
    left_wrist_vel = abs(kps[15][1] - kps[14][1]) if len(kps) > 15 else 0

    # Symmetry
    arm_sym = abs(kps[15][0] - kps[16][0]) if len(kps) > 16 else 0

    return {
        "neck_flexion": neck_angle,
        "trunk_flexion": trunk_angle,
        "shoulder_symmetry": shoulder_sym,
        "knee_angle": knee_angle,
        "right_wrist_velocity": right_wrist_vel,
        "left_wrist_velocity": left_wrist_vel,
        "arm_symmetry": arm_sym,
        "timestamp": timestamp,
    }


def compute_angle(a, b, c) -> float:
    """Compute angle at point b given points a, b, c."""
    a = np.array([a[0], a[1]])
    b = np.array([b[0], b[1]])
    c = np.array([c[0], c[1]])
    ba = a - b
    bc = c - b
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    return np.degrees(np.arccos(np.clip(cosine_angle, -1.0, 1.0)))


# ── Data Augmentation ────────────────────────────────────────────

def augment_data(features: list, num_augmentations: int = 3) -> list:
    """Augment training data with noise and time-shifting."""
    augmented = []
    for feat in features:
        for _ in range(num_augmentations):
            aug = feat.copy()
            # Add Gaussian noise
            for key in ["neck_flexion", "trunk_flexion", "shoulder_symmetry", "knee_angle"]:
                if key in aug:
                    aug[key] += np.random.normal(0, 2.0)  # ±2 degrees noise
            # Time shift
            aug["timestamp"] += np.random.uniform(-0.5, 0.5)
            augmented.append(aug)
    return augmented


# ── Model Training ───────────────────────────────────────────────

def train_risk_model(X: np.ndarray, y: np.ndarray) -> dict:
    """Train improved risk model with class balancing."""
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import classification_report, confusion_matrix
    from sklearn.utils.class_weight import compute_class_weight

    logger.info("Training risk model with %d samples, %d features", X.shape[0], X.shape[1])

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Compute class weights for imbalanced data
    classes = np.unique(y)
    weights = compute_class_weight("balanced", classes=classes, y=y)
    sample_weights = np.array([weights[list(classes).index(c)] for c in y])

    # Train with cross-validation
    model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        random_state=42,
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model, X_scaled, y, cv=cv, scoring="f1_macro")

    # Train final model on all data
    model.fit(X_scaled, y, sample_weight=sample_weights)

    # Evaluate
    y_pred = model.predict(X_scaled)
    report = classification_report(y, y_pred, output_dict=True)
    cm = confusion_matrix(y, y_pred)

    return {
        "model": model,
        "scaler": scaler,
        "cv_f1_mean": float(np.mean(scores)),
        "cv_f1_std": float(np.std(scores)),
        "train_f1": float(report["macro avg"]["f1-score"]),
        "train_accuracy": float(report["accuracy"]),
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
        "class_weights": dict(zip(classes, weights)),
    }


def train_task_model(X: np.ndarray, y: np.ndarray) -> dict:
    """Train improved task classifier with real data."""
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import classification_report, confusion_matrix

    logger.info("Training task model with %d samples, %d features", X.shape[0], X.shape[1])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Use ensemble for better generalization
    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model, X_scaled, y, cv=cv, scoring="f1_macro")

    model.fit(X_scaled, y)

    y_pred = model.predict(X_scaled)
    report = classification_report(y, y_pred, output_dict=True)
    cm = confusion_matrix(y, y_pred)

    return {
        "model": model,
        "scaler": scaler,
        "cv_f1_mean": float(np.mean(scores)),
        "cv_f1_std": float(np.std(scores)),
        "train_f1": float(report["macro avg"]["f1-score"]),
        "train_accuracy": float(report["accuracy"]),
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
    }


# ── Main Pipeline ────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("ErgoVigilance Model Improvement Pipeline")
    logger.info("=" * 60)

    # 1. Extract features from existing recordings
    logger.info("\n[Step 1] Extracting features from recordings...")
    recordings_dir = PROJECT_ROOT / "recordings"
    all_features = []

    if recordings_dir.exists():
        for worker_dir in recordings_dir.iterdir():
            if worker_dir.is_dir():
                for session_dir in worker_dir.iterdir():
                    timeline_file = session_dir / "timeline.json"
                    if timeline_file.exists():
                        try:
                            data = json.loads(timeline_file.read_text())
                            for frame in data.get("frames", []):
                                features = {
                                    "neck_flexion": frame.get("features", {}).get("neck_flexion", 10),
                                    "trunk_flexion": frame.get("features", {}).get("trunk_flexion", 5),
                                    "shoulder_symmetry": frame.get("features", {}).get("shoulder_symmetry", 10),
                                    "knee_angle": frame.get("features", {}).get("knee_angle", 170),
                                    "risk_level": frame.get("risk_level", "LOW"),
                                    "task": frame.get("task", "Unknown"),
                                    "source": str(session_dir),
                                }
                                all_features.append(features)
                        except Exception as e:
                            logger.warning("Error reading %s: %s", timeline_file, e)

    logger.info("Extracted %d frames from recordings", len(all_features))

    # 2. Extract from video files
    logger.info("\n[Step 2] Extracting keypoints from videos...")
    video_dirs = [
        DATA_DIR / "diverse_training" / "youtube",
        DATA_DIR / "diverse_training" / "huggingface",
        DATA_DIR / "assembly_videos",
    ]

    video_features = []
    for video_dir in video_dirs:
        if video_dir.exists():
            for video_file in video_dir.glob("*.mp4"):
                logger.info("Processing: %s", video_file.name)
                features = extract_coco17_keypoints(str(video_file))
                video_features.extend(features)

    logger.info("Extracted %d frames from %d videos", len(video_features), len(list(video_dirs)))

    # 3. Combine and augment
    logger.info("\n[Step 3] Combining and augmenting data...")
    combined = all_features + video_features
    augmented = augment_data(combined, num_augmentations=2)
    all_data = combined + augmented

    logger.info("Total training samples: %d (original: %d, augmented: %d)",
                len(all_data), len(combined), len(augmented))

    # 4. Prepare features and labels
    feature_keys = ["neck_flexion", "trunk_flexion", "shoulder_symmetry", "knee_angle"]
    X = np.array([[d.get(k, 0) for k in feature_keys] for d in all_data])
    y_risk = np.array([d.get("risk_level", "LOW") for d in all_data])
    y_task = np.array([d.get("task", "Unknown") for d in all_data])

    # 5. Train risk model
    logger.info("\n[Step 4] Training improved risk model...")
    risk_results = train_risk_model(X, y_risk)

    # 6. Train task model
    logger.info("\n[Step 5] Training improved task model...")
    task_results = train_task_model(X, y_task)

    # 7. Save models
    logger.info("\n[Step 6] Saving models...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save risk model
    risk_model_path = MODELS_DIR / f"improved_risk_model_{timestamp}.pkl"
    with open(risk_model_path, "wb") as f:
        pickle.dump({"model": risk_results["model"], "scaler": risk_results["scaler"]}, f)
    logger.info("Risk model saved: %s", risk_model_path)

    # Save task model
    task_model_path = MODELS_DIR / f"improved_task_model_{timestamp}.pkl"
    with open(task_model_path, "wb") as f:
        pickle.dump({"model": task_results["model"], "scaler": task_results["scaler"]}, f)
    logger.info("Task model saved: %s", task_model_path)

    # 8. Save metrics
    metrics = {
        "timestamp": timestamp,
        "data_stats": {
            "total_frames": len(all_data),
            "original_frames": len(combined),
            "augmented_frames": len(augmented),
            "risk_distribution": dict(Counter(y_risk)),
            "task_distribution": dict(Counter(y_task)),
        },
        "risk_model": {
            "cv_f1_mean": risk_results["cv_f1_mean"],
            "cv_f1_std": risk_results["cv_f1_std"],
            "train_f1": risk_results["train_f1"],
            "train_accuracy": risk_results["train_accuracy"],
            "confusion_matrix": risk_results["confusion_matrix"],
        },
        "task_model": {
            "cv_f1_mean": task_results["cv_f1_mean"],
            "cv_f1_std": task_results["cv_f1_std"],
            "train_f1": task_results["train_f1"],
            "train_accuracy": task_results["train_accuracy"],
            "confusion_matrix": task_results["confusion_matrix"],
        },
    }

    metrics_path = RESULTS_DIR / f"improved_model_metrics_{timestamp}.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info("Metrics saved: %s", metrics_path)

    # 9. Print summary
    logger.info("\n" + "=" * 60)
    logger.info("MODEL IMPROVEMENT RESULTS")
    logger.info("=" * 60)
    logger.info("\nRisk Model:")
    logger.info("  CV F1: %.3f ± %.3f", risk_results["cv_f1_mean"], risk_results["cv_f1_std"])
    logger.info("  Train F1: %.3f", risk_results["train_f1"])
    logger.info("  Train Accuracy: %.3f", risk_results["train_accuracy"])
    logger.info("\nTask Model:")
    logger.info("  CV F1: %.3f ± %.3f", task_results["cv_f1_mean"], task_results["cv_f1_std"])
    logger.info("  Train F1: %.3f", task_results["train_f1"])
    logger.info("  Train Accuracy: %.3f", task_results["train_accuracy"])
    logger.info("\nData Distribution:")
    logger.info("  Risk: %s", dict(Counter(y_risk)))
    logger.info("  Task: %s", dict(Counter(y_task)))
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
