# handoff_pose_estimation

Standalone posture analysis module extracted from ErgoVigilance.

**Zero product dependencies.** No FastAPI, no auth, no SQLite, no React.
Pure Python - only needs `mediapipe`, `opencv-python`, and `numpy`.

---

## Quick Start

```
cd handoff_pose_estimation
pip install -r requirements.txt
python analyze_video.py path/to/demo.mp4
```

The first run downloads the MediaPipe PoseLandmarker model (~5 MB) automatically
to `models/pose_landmarker_lite.task`.

---

## CLI Usage

```
python analyze_video.py <video_path> [--model <path>] [--output <path>] [--every N]
```

| Argument  | Default                    | Description                                  |
|-----------|----------------------------|----------------------------------------------|
| video     | (required)                 | Path to input video file                     |
| --model   | auto-downloaded model      | Path to MediaPipe .task model file           |
| --output  | print to stdout            | Path to write JSON results                  |
| --every   | 1                          | Process every Nth frame (e.g. 5 = 5 fps)     |

---

## Output Format

Per-frame JSON with these keys when a person is detected:

- `frame_index` / `timestamp_sec` - frame identity
- `person_detected` / `confidence` - detection status
- `risk_level` - "LOW", "MEDIUM", or "HIGH"
- `features` - all 9 ergonomic angles (or null if unavailable)
- `unavailable_features` / `approximate_features` - feature quality flags
- `lower_body_confidence` - % of lower-body visibility
- `rula` - RULA-informed score (1-7), partial score flag
- `guidance` - per-zone feedback + recommendations
- `task` - detected activity (Neutral Standing, Assembly Work, etc.)
- `issues` - triggered posture issues with severity
- `recommendations` - worker/supervisor action items

---

## Files

| File                   | Purpose                                         |
|------------------------|-------------------------------------------------|
| `analyze_video.py`     | CLI entry point - reads video, outputs JSON    |
| `pose_engine.py`       | MediaPipe pipeline: frame -> features -> risk  |
| `features.py`          | RULA feature extraction + risk scoring         |
| `task_recognition.py`  | Motion-based activity classifier               |
| `issue_detection.py`   | Feature-threshold-based issue detection        |
| `recommendation_engine.py` | Issue -> worker/supervisor text mappings   |
| `guidance.py`          | Human-readable posture feedback                |
| `pose_types.py`        | ProcessedFrame / LiveState dataclasses         |
| `constants.py`         | Landmark indices, feature columns, thresholds  |
| `utils.py`             | Geometry helpers (angle_between, midpoint...)  |
