"""One-camera live-stream smoke (production path, no mocks).

Serves a real video over HTTP, registers it as a camera through the real cloud
API, and drives the full pipeline:

    HTTP source -> FFmpeg (production RTSPStream) -> YOLOv8-pose
    -> per-track processing -> /cameras/{id} + /cameras/{id}/persons

Fails loudly on any runtime exception. A hard watchdog guarantees the process
exits even if a background thread wedges.

Run (from the repo root):

    python -u scripts/verify_one_camera.py
"""

import functools
import http.server
import json
import os
import socketserver
import sys
import threading
import time

RESULT: dict = {"steps": [], "errors": []}
OUT_PATH = os.path.join("outputs", "verify_one_camera_result.json")

# Make the repo importable when run as a script (mirrors scripts/soak_cloud.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("YOLO_AUTOINSTALL", "false")
os.environ.pop("DATABASE_URL", None)  # dev mode -> API-key auth bypassed
os.environ.setdefault("SESSIONS_DIR", os.path.join("outputs", "smoke_sessions"))
os.environ.setdefault("RECORDINGS_DIR", os.path.join("outputs", "smoke_recordings"))

VIDEO = "data/datasets/diverse_training/huggingface/defect_testing_station08_worker009.mp4"
HTTP_PORT = 8791
CAM_ID = "smoke-cam-1"


def note(step: str, **kw):
    RESULT["steps"].append({"step": step, **kw})
    print(f"[smoke] {step}: {json.dumps(kw, default=str)[:600]}", flush=True)


def finish(code: int):
    try:
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as fh:
            json.dump(RESULT, fh, indent=2)
    except Exception as exc:  # pragma: no cover
        print("failed to write result:", exc, flush=True)
    print(f"[smoke] exit={code}", flush=True)
    os._exit(code)


threading.Timer(300, lambda: (print("[smoke] WATCHDOG fired", flush=True), finish(2))).start()

# ── 1. Real network source: the video served over HTTP ─────────────────────
video_abs = os.path.abspath(VIDEO)
basename = os.path.basename(video_abs)
URL = f"http://127.0.0.1:{HTTP_PORT}/{basename}"
handler = functools.partial(
    http.server.SimpleHTTPRequestHandler, directory=os.path.dirname(video_abs)
)


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


httpd = _Server(("127.0.0.1", HTTP_PORT), handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
note("http_source_ready", url=URL, bytes=os.path.getsize(video_abs))

from fastapi.testclient import TestClient  # noqa: E402

import yolo_cloud.api as api  # noqa: E402

shared_engine = bool(getattr(api, "_HAS_SHARED_ENGINE", None))
if shared_engine is False:
    shared_engine = bool(getattr(__import__("yolo_cloud.pose_engine", fromlist=["x"]), "_HAS_SHARED_ENGINE", None))
note("engine", shared_engine=shared_engine)

try:
    with TestClient(api.create_app()) as client:
        resp = client.post(
            "/api/cloud/cameras",
            json={"id": CAM_ID, "name": "Smoke Cam", "url": URL},
        )
        note("post_cameras", status=resp.status_code, body=resp.json() if resp.status_code < 500 else resp.text[:300])
        if resp.status_code >= 300:
            RESULT["errors"].append(f"POST /cameras -> {resp.status_code}")
            finish(1)

        # ── 2. Wait for the pipeline to produce frames ────────────────────
        state = None
        deadline = time.time() + 180
        while time.time() < deadline:
            time.sleep(5)
            r = client.get(f"/api/cloud/cameras/{CAM_ID}")
            if r.status_code != 200:
                continue
            state = r.json()
            if state.get("frame_count", 0) > 0:
                break

        if not state or not state.get("frame_count"):
            RESULT["errors"].append("pipeline produced no frames")
            note("camera_state", body=(state or {}) and json.dumps(state, default=str)[:400])
            finish(1)

        tracks_1 = sorted(p.get("track_id") for p in (state.get("persons") or []))
        note(
            "camera_state",
            frame_count=state.get("frame_count"),
            session_id=state.get("session_id"),
            is_active=state.get("is_active"),
            track_ids=tracks_1,
        )

        # ── 3. Per-track person snapshots ────────────────────────────────
        pr = client.get(f"/api/cloud/cameras/{CAM_ID}/persons")
        persons_payload = pr.json() if pr.status_code == 200 else {}
        persons = persons_payload.get("persons") or []
        note(
            "camera_persons",
            status=pr.status_code,
            person_count=persons_payload.get("person_count"),
            sample=persons[:2],
        )

        # ── 4. Track ids stay stable across a 15 s window ────────────────
        time.sleep(15)
        s2 = client.get(f"/api/cloud/cameras/{CAM_ID}").json()
        tracks_2 = sorted(p.get("track_id") for p in (s2.get("persons") or []))
        stable = bool(tracks_1) and bool(set(tracks_1) & set(tracks_2))
        note(
            "track_stability",
            tracks_before=tracks_1,
            tracks_after=tracks_2,
            overlapping=stable,
            frame_count=s2.get("frame_count"),
        )
        RESULT["summary"] = {
            "frame_count": s2.get("frame_count"),
            "session_id": s2.get("session_id"),
            "track_ids": tracks_2,
            "track_ids_stable": stable,
            "shared_engine": shared_engine,
        }

        # ── 5. Clean shutdown of the camera (no crash) ───────────────────
        rm = client.delete(f"/api/cloud/cameras/{CAM_ID}")
        note("delete_camera", status=rm.status_code)

    print("[smoke] ALL STEPS COMPLETED", flush=True)
    finish(0)
except Exception as exc:  # pragma: no cover - the point of the smoke
    import traceback

    traceback.print_exc()
    RESULT["errors"].append(f"{type(exc).__name__}: {exc}")
    finish(3)
