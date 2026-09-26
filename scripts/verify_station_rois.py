"""Station ROI end-to-end check (production path, no mocks).

Serves a real video over HTTP, registers it as a camera through the real cloud
API, draws three station polygons through the station API, then watches the live
``persons[]`` payload and checks that each track's reported ``station_id``
matches the polygon that actually contains its bbox centroid.

For every sample it independently recomputes the expected station from the
returned ``bbox`` using the same ray-casting primitive and compares — so a
mismatch between the engine's mapping and the drawn geometry fails loudly.

Run (from the repo root):

    python -u scripts/verify_station_rois.py
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

# Isolated station file so a check never touches a site's real configuration.
# Must be set before yolo_cloud.config is imported.
STATIONS_FILE = os.path.join("outputs", "station_roi_smoke", "stations.json")
os.environ["STATIONS_FILE"] = os.path.abspath(STATIONS_FILE)
os.environ.setdefault("YOLO_AUTOINSTALL", "false")
os.environ.pop("DATABASE_URL", None)  # dev mode -> API-key auth bypassed
os.environ.setdefault("SESSIONS_DIR", os.path.join("outputs", "smoke_sessions"))
os.environ.setdefault("RECORDINGS_DIR", os.path.join("outputs", "smoke_recordings"))

os.makedirs(os.path.dirname(os.path.abspath(STATIONS_FILE)), exist_ok=True)
if os.path.exists(STATIONS_FILE):
    os.remove(STATIONS_FILE)

from yolo_cloud.stations import point_in_polygon  # noqa: E402

RESULT: dict = {"steps": [], "errors": [], "samples": [], "station_series": []}
OUT_PATH = os.path.join("outputs", "station_roi_smoke", "result.json")

VIDEO = "data/datasets/diverse_training/huggingface/defect_testing_station08_worker009.mp4"
HTTP_PORT = 8792
CAM_ID = "roi-smoke-cam"
SAMPLE_SECONDS = 5
SAMPLE_COUNT = 10  # ~50 s of wall clock


def note(step: str, **kw):
    RESULT["steps"].append({"step": step, **kw})
    print(f"[roi] {step}: {json.dumps(kw, default=str)[:600]}", flush=True)


def finish(code: int):
    try:
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as fh:
            json.dump(RESULT, fh, indent=2)
    except Exception as exc:  # pragma: no cover
        print("failed to write result:", exc, flush=True)
    print(f"[roi] exit={code}", flush=True)
    os._exit(code)


threading.Timer(300, lambda: (print("[roi] WATCHDOG fired", flush=True), finish(2))).start()

# ── 1. Real network source ───────────────────────────────────────────────────
video_abs = os.path.abspath(VIDEO)
URL = f"http://127.0.0.1:{HTTP_PORT}/{os.path.basename(video_abs)}"
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

# ── 2. Three side-by-side workstations across the frame ──────────────────────
STATIONS = [
    ("ST-LEFT", "Left Bay", [{"x": 0.0, "y": 0.0}, {"x": 0.33, "y": 0.0},
                             {"x": 0.33, "y": 1.0}, {"x": 0.0, "y": 1.0}]),
    ("ST-MID", "Middle Bay", [{"x": 0.33, "y": 0.0}, {"x": 0.66, "y": 0.0},
                              {"x": 0.66, "y": 1.0}, {"x": 0.33, "y": 1.0}]),
    ("ST-RIGHT", "Right Bay", [{"x": 0.66, "y": 0.0}, {"x": 1.0, "y": 0.0},
                               {"x": 1.0, "y": 1.0}, {"x": 0.66, "y": 1.0}]),
]
EXPECTED = {sid: poly for sid, _name, poly in STATIONS}

try:
    with TestClient(api.create_app()) as client:
        # ── 3. Draw the ROIs through the real station API ────────────────────
        for station_id, station_name, polygon in STATIONS:
            r = client.put(
                f"/api/cloud/cameras/{CAM_ID}/stations/{station_id}",
                json={"station_name": station_name, "polygon": polygon},
            )
            if r.status_code >= 300:
                RESULT["errors"].append(f"PUT station {station_id} -> {r.status_code} {r.text[:200]}")
                finish(1)

        listed = client.get(f"/api/cloud/cameras/{CAM_ID}/stations")
        note(
            "stations_drawn",
            status=listed.status_code,
            station_count=listed.json().get("station_count"),
            station_ids=[s["station_id"] for s in listed.json().get("stations", [])],
        )

        # Rejects a bad polygon (pixel coords) with 400 rather than storing it.
        bad = client.put(
            f"/api/cloud/cameras/{CAM_ID}/stations/ST-BAD",
            json={"station_name": "bad", "polygon": [{"x": 100, "y": 50}, {"x": 300, "y": 50}, {"x": 300, "y": 400}]},
        )
        note("bad_polygon_rejected", status=bad.status_code)

        # ── 4. Start the camera and watch the mapping ────────────────────────
        resp = client.post(
            "/api/cloud/cameras",
            json={"id": CAM_ID, "name": "ROI Smoke", "url": URL},
        )
        note("post_cameras", status=resp.status_code, body=resp.json() if resp.status_code < 500 else resp.text[:200])
        if resp.status_code >= 300:
            RESULT["errors"].append(f"POST /cameras -> {resp.status_code}")
            finish(1)

        deadline = time.time() + 120
        while time.time() < deadline:
            time.sleep(5)
            state = client.get(f"/api/cloud/cameras/{CAM_ID}")
            if state.status_code == 200 and state.json().get("frame_count"):
                break

        mismatches = 0
        note_frame_size = False
        for _ in range(SAMPLE_COUNT):
            r = client.get(f"/api/cloud/cameras/{CAM_ID}/persons")
            if r.status_code != 200:
                time.sleep(SAMPLE_SECONDS)
                continue
            payload = r.json()
            persons = payload.get("persons") or []
            # Use the frame size the engine actually processed, not an assumed
            # resolution — the pixel bbox is only meaningful with it.
            fw = float(payload.get("frame_width") or 0) or 1.0
            fh = float(payload.get("frame_height") or 0) or 1.0
            if not note_frame_size:
                note("frame_size", frame_width=payload.get("frame_width"), frame_height=payload.get("frame_height"))
                note_frame_size = True
            for person in persons:
                x, y, w, h = person["bbox"]
                cx = (x + w / 2.0) / fw
                cy = (y + h / 2.0) / fh
                expected = next(
                    (sid for sid, poly in EXPECTED.items() if point_in_polygon(cx, cy, poly)),
                    None,
                )
                reported = person.get("station_id")
                match = expected == reported
                if not match:
                    mismatches += 1
                RESULT["samples"].append({
                    "track_id": person["track_id"],
                    "centroid": [round(cx, 4), round(cy, 4)],
                    "reported": reported,
                    "expected": expected,
                    "match": match,
                })
            RESULT["station_series"].append(
                [p.get("station_id") for p in persons]
            )
            note(
                "sample",
                tracks=[p["track_id"] for p in persons],
                stations=[p.get("station_id") for p in persons],
            )
            time.sleep(SAMPLE_SECONDS)

        distinct = sorted({s for frame in RESULT["station_series"] for s in frame if s})
        RESULT["summary"] = {
            "stations_drawn": len(STATIONS),
            "samples": len(RESULT["samples"]),
            "mismatches": mismatches,
            "distinct_stations_observed": distinct,
            "station_assignment_changed": len(distinct) > 1,
        }
        note("summary", **RESULT["summary"])

        # ── 5. Clean shutdown ───────────────────────────────────────────────
        rm = client.delete(f"/api/cloud/cameras/{CAM_ID}")
        note("delete_camera", status=rm.status_code)
        for station_id, _n, _p in STATIONS:
            client.delete(f"/api/cloud/cameras/{CAM_ID}/stations/{station_id}")
        note("stations_cleared", status=client.get(f"/api/cloud/cameras/{CAM_ID}/stations").json())

        if mismatches:
            RESULT["errors"].append(f"{mismatches} station mismatch(es) between payload and geometry")
            finish(1)

    print("[roi] ALL STEPS COMPLETED", flush=True)
    finish(0)
except Exception as exc:  # pragma: no cover - the point of the check
    import traceback

    traceback.print_exc()
    RESULT["errors"].append(f"{type(exc).__name__}: {exc}")
    finish(3)
