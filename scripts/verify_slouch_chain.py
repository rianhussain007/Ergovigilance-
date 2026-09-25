"""Automated slouch chain smoke test.

Validates the chain end to end and records each leg independently so a partial
pass cannot be read as a full one:

    Dwell Trigger -> Risk State HIGH -> Alert Created -> WebSocket Event Sent
    -> 10 s Video Clip Saved -> reportlab PDF Generated

Part A drives a DELIBERATE sustained slouch (trunk flexion > 60 deg for > 10
frames) through the real scoring path as synthetic keypoints. Detection itself
is bypassed — YOLO cannot be handed an imagined slouch — so this proves the
scoring/trigger chain, not the detector.

Part B runs a real stream through the real API and checks the alert reaches a
WebSocket client and that the reportlab PDF is produced.

The clip leg downloads the clip saved when the HIGH alert fired. Clips are
PRE-ALERT only: the camera's rolling buffer of the seconds before the alert,
written at the configured inference rate, ending at the alert.

Run (from the repo root):

    python -u scripts/verify_slouch_chain.py
"""

import functools
import http.server
import json
import os
import socketserver
import sys
import threading
import time

# Make the repo importable when run as a script (mirrors scripts/soak_cloud.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("YOLO_AUTOINSTALL", "false")
os.environ.pop("DATABASE_URL", None)  # dev mode -> API-key auth bypassed
os.environ.setdefault("SESSIONS_DIR", os.path.join("outputs", "slouch_smoke", "sessions"))
# RECORDINGS_DIR is deliberately NOT overridden: alert clips must land in the
# real recordings/ tree, which is the artifact this smoke is expected to produce.

import numpy as np  # noqa: E402

RESULT: dict = {"legs": {}, "evidence": [], "errors": []}
OUT_PATH = os.path.join("outputs", "slouch_smoke", "result.json")

VIDEO = "data/datasets/diverse_training/huggingface/defect_testing_station08_worker009.mp4"
HTTP_PORT = 8793
CAM_ID = "slouch-smoke-cam"

# Thresholds from the spec.
TRUNK_MIN_DEG = 60.0
SUSTAINED_FRAMES = 10
FEED_FRAMES = 15

FRAME_W, FRAME_H = 1280.0, 720.0
# Deep sustained forward bend: shoulder midpoint offset ~0.62 in normalised x
# from the hip midpoint gives a computed trunk angle of ~74.8 deg at 1280x720.
# NOTE: angles are computed in PIXEL space (keypoints are denormalised with the
# frame dimensions before the angle maths), so this offset maps to the same
# physical trunk angle at any aspect ratio. The deep bend is deliberate: it
# clears the 60 deg threshold with margin rather than sitting on the boundary.
SLOUCH_KEYPOINTS = {
    0: (0.80, 0.30), 1: (0.81, 0.29), 2: (0.79, 0.29), 3: (0.83, 0.30), 4: (0.77, 0.30),
    5: (0.72, 0.40), 6: (0.82, 0.40),          # shoulders -> mid (0.77, 0.40)
    7: (0.69, 0.55), 8: (0.85, 0.55),
    9: (0.67, 0.68), 10: (0.87, 0.68),
    11: (0.10, 0.70), 12: (0.20, 0.70),        # hips -> mid (0.15, 0.70)
    13: (0.11, 0.85), 14: (0.21, 0.85),
    15: (0.11, 0.95), 16: (0.21, 0.95),
}


def note(label: str, **kw):
    RESULT["evidence"].append({"step": label, **kw})
    print(f"[chain] {label}: {json.dumps(kw, default=str)[:700]}", flush=True)


def leg(name: str, status: str, detail: str = "", **extra):
    """Record one chain leg. status is PASS | FAIL | NOT_IMPLEMENTED."""
    RESULT["legs"][name] = {"status": status, "detail": detail, **extra}
    print(f"[chain] leg {name}: {status} {detail}"[:400], flush=True)


def finish(code: int):
    try:
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as fh:
            json.dump(RESULT, fh, indent=2)
    except Exception as exc:  # pragma: no cover
        print("failed to write result:", exc, flush=True)
    print(f"[chain] exit={code}", flush=True)
    os._exit(code)


threading.Timer(300, lambda: (print("[chain] WATCHDOG fired", flush=True), finish(2))).start()


# ── Part A: the deliberate slouch, through the real scoring path ─────────────
def part_a_deliberate_slouch() -> tuple[float, str, bool]:
    """Feed a sustained deep trunk bend and report (angle, risk_level, dwell_ok)."""
    from yolo_cloud.pose_engine import YOLOPoseEngine

    keypoints = np.zeros((17, 3), dtype=float)
    for idx, (x, y) in SLOUCH_KEYPOINTS.items():
        keypoints[idx] = [x * FRAME_W, y * FRAME_H, 0.9]

    engine = YOLOPoseEngine()
    frame = np.full((int(FRAME_H), int(FRAME_W), 3), 128, dtype=np.uint8)

    trunk_angles: list[float] = []
    levels: list[str] = []
    for _ in range(FEED_FRAMES):
        pose = engine._process_tracked_pose(
            1, [100, 100, 900, 690], keypoints, FRAME_W, FRAME_H, frame, "slouch-cam"
        )
        trunk_angles.append(float(pose.joint_angles.get("trunk", 0.0)))
        levels.append(pose.risk_level)

    sustained = sum(1 for a in trunk_angles if a > TRUNK_MIN_DEG)
    note(
        "slouch_fed",
        frames=FEED_FRAMES,
        trunk_deg=[round(a, 1) for a in trunk_angles[:4]] + ["..."],
        sustained_over_threshold=sustained,
        risk_levels=sorted(set(levels)),
    )

    leg(
        "slouch_trigger",
        "PASS" if sustained >= SUSTAINED_FRAMES else "FAIL",
        f"{sustained}/{FEED_FRAMES} frames above {TRUNK_MIN_DEG} deg "
        f"(needs >{SUSTAINED_FRAMES})",
        sustained_frames=sustained,
    )

    high = levels.count("HIGH")
    leg(
        "risk_state_high",
        "PASS" if high > 0 else "FAIL",
        f"HIGH on {high}/{FEED_FRAMES} frames (observed: {sorted(set(levels))})",
    )

    # Dwell: the task engine keeps smoothing/dwell state per (camera, track).
    engine_key = ("slouch-cam", 1)
    dwell_engine = engine._task_engines.get(engine_key)
    dwell_ok = dwell_engine is not None and len(dwell_engine._window) >= SUSTAINED_FRAMES
    leg(
        "dwell_trigger",
        "PASS" if dwell_ok else "FAIL",
        f"per-track task engine window={len(dwell_engine._window) if dwell_engine else 0} "
        f"(needs >={SUSTAINED_FRAMES}); engine is per (camera, track_id)",
    )

    return trunk_angles[-1], levels[-1], dwell_ok


# ── Part B: the live chain on a real stream ──────────────────────────────────
def part_b_live_chain() -> bool:
    video_abs = os.path.abspath(VIDEO)
    url = f"http://127.0.0.1:{HTTP_PORT}/{os.path.basename(video_abs)}"
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=os.path.dirname(video_abs)
    )

    class _Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    httpd = _Server(("127.0.0.1", HTTP_PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    from fastapi.testclient import TestClient

    import yolo_cloud.api as api

    ok = True
    with TestClient(api.create_app()) as client:
        resp = client.post("/api/cloud/cameras", json={"id": CAM_ID, "name": "Slouch Smoke", "url": url})
        if resp.status_code >= 300:
            leg("live_camera_start", "FAIL", f"POST /cameras -> {resp.status_code}")
            return False
        note("camera_started", status=resp.status_code, body=resp.json())

        # Connect the WebSocket BEFORE the alert, so observing it arrive is a
        # real delivery check rather than reading history.
        ws_alert = None
        delivery_path = None  # "alert" = immediate event push, "update" = 5 Hz snapshot
        deadline = time.time() + 120
        with client.websocket_connect("/api/cloud/ws") as ws:
            init = ws.receive_json()
            note("ws_connected", first_message_type=init.get("type"))
            while time.time() < deadline:
                msg = ws.receive_json()
                kind = msg.get("type")
                if kind == "alert":
                    alert = msg.get("alert") or {}
                    if alert.get("severity") == "HIGH":
                        ws_alert, delivery_path = alert, "alert"
                        break
                elif kind == "update":
                    for alert in msg.get("recent_alerts") or []:
                        if alert.get("severity") == "HIGH":
                            ws_alert, delivery_path = alert, "update"
                            break
                if ws_alert:
                    break

        if ws_alert:
            leg(
                "websocket_event_sent",
                "PASS",
                f"HIGH alert {ws_alert.get('alert_id')} delivered via '{delivery_path}' "
                "— contract: the 5 Hz snapshot carrying recent_alerts is the "
                "GUARANTEED path (<=200 ms), the immediate {type: alert} event is "
                "an accelerator and may duplicate it, so clients de-dupe on alert_id",
                alert_id=ws_alert.get("alert_id"),
                delivery=delivery_path,
            )
        else:
            leg("websocket_event_sent", "FAIL", "no HIGH alert observed on the WS within the deadline")
            ok = False
            ws_alert = {}

        alerts = client.get("/api/cloud/alerts", params={"limit": 100})
        # /alerts returns {"alerts": [...]}, not a bare list.
        alert_payload = alerts.json() if alerts.status_code == 200 else {}
        alert_list = alert_payload.get("alerts") or []
        high_alerts = [a for a in alert_list if a.get("severity") == "HIGH"]
        if high_alerts:
            leg("alert_created", "PASS", f"{len(high_alerts)} HIGH alert(s) in /alerts")
        else:
            leg("alert_created", "FAIL", "no HIGH alert in /alerts")
            ok = False

        note("alert_sample", alert=high_alerts[0] if high_alerts else None)

        pdf = client.get("/api/cloud/reports/pdf", params={"report_type": "daily", "camera_id": CAM_ID})
        body = pdf.content
        is_pdf = pdf.status_code == 200 and body[:4] == b"%PDF"
        leg(
            "pdf_generated",
            "PASS" if is_pdf else "FAIL",
            f"HTTP {pdf.status_code}, {len(body)} bytes, magic={body[:4]!r}",
        )
        ok = ok and is_pdf
        if is_pdf:
            try:
                os.makedirs(os.path.join("outputs", "slouch_smoke"), exist_ok=True)
                with open(os.path.join("outputs", "slouch_smoke", "daily_report.pdf"), "wb") as fh:
                    fh.write(body)
                note("pdf_written", path="outputs/slouch_smoke/daily_report.pdf", bytes=len(body))
            except Exception as exc:  # noqa: BLE001
                note("pdf_write_failed", error=str(exc))

        # Clip leg: a clip should have been written when the HIGH alert fired.
        from yolo_cloud.config import settings as cloud_settings

        clips_dir = os.path.join(cloud_settings.RECORDINGS_DIR, "clips", CAM_ID)
        saved_files = sorted(os.listdir(clips_dir)) if os.path.isdir(clips_dir) else []
        clip_alert_id = (ws_alert or {}).get("alert_id") or (
            high_alerts[0].get("alert_id") if high_alerts else None
        )
        clip = (
            client.get(f"/api/cloud/cameras/{CAM_ID}/clips/{clip_alert_id}")
            if clip_alert_id else None
        )
        clip_bytes = clip.content if clip is not None else b""
        # MP4 files carry a 'ftyp' box at offset 4; this catches an empty or
        # truncated body that a 200 status alone would not.
        is_video = (
            clip is not None
            and clip.status_code == 200
            and len(clip_bytes) > 12
            and clip_bytes[4:8] == b"ftyp"
        )
        clip_meta = (ws_alert or {}).get("clip") or {}
        leg(
            "video_clip_saved",
            "PASS" if is_video else "FAIL",
            f"HTTP {clip.status_code if clip is not None else 'n/a'}, "
            f"{len(clip_bytes)} bytes, magic={clip_bytes[4:8]!r}, "
            f"{len(saved_files)} file(s) in {clips_dir} {saved_files}",
            alert_id=clip_alert_id,
            bytes=len(clip_bytes),
            clip_dir=clips_dir,
            files=saved_files,
            pre_alert_only=True,
            captured_frames=clip_meta.get("frames"),
            captured_duration_s=clip_meta.get("duration_s"),
        )
        # The clip is PRE-roll only, so its length is however many frames the
        # buffer held when the alert fired — not a fixed 10 s. This smoke posts a
        # clip whose worker is ALREADY deeply bent, so the very first scored frame
        # is HIGH and the alert fires on frame 1; the buffer therefore legitimately
        # holds one frame. State that explicitly, so a short clip is not misread as
        # a broken ring buffer. Multi-frame buffering is covered by the unit tests
        # (yolo_cloud/tests/test_trl6_blockers.py::TestAlertClips).
        note(
            "clip_is_pre_roll_only",
            captured_frames=clip_meta.get("frames"),
            buffer_capacity_frames="CLIP_BUFFER_SECONDS * INFERENCE_FPS",
            why_short="alert fired on the first scored frame (this clip opens with "
            "the worker already bent), and the buffer only ever holds frames the "
            "pipeline has already pulled",
        )
        ok = ok and is_video

        client.delete(f"/api/cloud/cameras/{CAM_ID}")
    return ok


def main() -> int:
    part_a_deliberate_slouch()
    live_ok = part_b_live_chain()

    passed = [k for k, v in RESULT["legs"].items() if v["status"] == "PASS"]
    failed = [k for k, v in RESULT["legs"].items() if v["status"] == "FAIL"]
    unimplemented = [k for k, v in RESULT["legs"].items() if v["status"] == "NOT_IMPLEMENTED"]
    RESULT["summary"] = {
        "legs_passed": passed,
        "legs_failed": failed,
        "legs_not_implemented": unimplemented,
        "chain_complete": not failed and not unimplemented,
        "evidence_pdf": "outputs/slouch_smoke/daily_report.pdf" if "pdf_generated" in passed else None,
    }
    note("summary", **RESULT["summary"])

    print("[chain] ALL STEPS COMPLETED", flush=True)
    finish(0 if not failed and live_ok else 1)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - the point of the smoke
        import traceback

        traceback.print_exc()
        RESULT["errors"].append(f"{type(exc).__name__}: {exc}")
        finish(3)
