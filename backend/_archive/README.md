# Archived / Retired Files

These files are **not part of the active pipeline**. They are kept for reference only.
Do not import from `_archive` in any active code.

## What was archived and why

| Archived file | Superseded by | Notes |
|---|---|---|
| `main.py` | `backend_api/app/main.py` | Old single-image-prediction FastAPI app. Superseded by the full backend_api microservice with live monitoring sessions, replay, and reports. |
| `services/pose.py` | `backend/services/pose_engine.py` | Old single-frame pose detection (`detect_pose_from_bgr`). Superseded by `pose_engine.py` which handles continuous video frame processing, landmark extraction, and feature calculation. |
| `services/trend_analysis.py` | `backend_api/app/services/live_monitor.py` & `analytics.py` | Standalone trend analysis. Trend/summary logic is now embedded in live_monitor's session summary and the analytics module. |
| `services/safety_reporting.py` | `backend_api/app/services/report_service.py` & `live_monitor.py` | Safety reporting utilities. Superseded by the report generation pipeline in backend_api. |
| `persistence/` | `backend_api/app/repositories/live.py` & `live_monitor.py` | Old `SessionRepository` / `JsonSessionRepository` abstraction. Direct file I/O in `live.py` and `live_monitor.py` replaced this pattern. |

## Files deliberately left in place

| File | Reason kept |
|---|---|
| `services/issue_detection.py` | **Still imported** by active module `pose_engine.py:21` (`detect_posture_issues`) |
| `services/recommendation_engine.py` | **Still imported** by active module `pose_engine.py:22` (`get_recommendations`) |
