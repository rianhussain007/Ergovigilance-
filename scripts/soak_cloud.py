"""Cloud core soak / sizing harness.

Two modes:

  * ``--urls rtsp://... rtsp://...``  — REAL RTSP soak. Uses the production
    ingestion path end-to-end (FFmpeg -> decode -> YOLO -> tracker -> sessions).
  * ``--video FILE`` (default)        — COMPUTE sizing only. Feeds the same video
    file to N concurrent camera processors through the real engine, skipping
    FFmpeg/RTP/network. Measures the dominant cost (inference per stream).

Per-stream samples and a summary are written to ``outputs/soak/``.

Measured per stream: effective FPS, distinct track ids, new-track events
(identity (re)assignment), ID switches, alerts.
Measured process-wide: CPU %, RSS.

Metric definitions (kept explicit because they are easy to misread):
  * ``new_track_events`` — a track_id not seen before in that camera. Every
    exit/re-entry produces one (track ids are never reused), so this is the
    honest "identity churn" counter, not a flip rate.
  * ``id_switches`` — a bound track_id changing worker (seat hand-over).

This harness does NOT measure GPU memory (no GPU API on the measuring host) and
does not prove multi-hour stability by itself — a 4 h soak still has to be run.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone

# Make the repo importable when run as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2  # noqa: E402
import psutil  # noqa: E402

from yolo_cloud.identity import get_identity_registry  # noqa: E402
from yolo_cloud.ingestion import LATENCY_BUDGET_MS, get_cloud_service  # noqa: E402
from yolo_cloud.pose_engine import get_pose_engine  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cloud core soak / sizing harness")
    p.add_argument("--streams", type=int, default=4, help="number of camera streams")
    p.add_argument("--seconds", type=int, default=60, help="soak duration (seconds)")
    p.add_argument("--interval", type=float, default=2.0, help="sampling interval (seconds)")
    p.add_argument("--video", default="data/datasets/diverse_training/huggingface/"
                                      "cardboard_manipulation_station01_worker041.mp4",
                   help="local video used as the frame source in compute mode")
    p.add_argument("--urls", nargs="*", default=[], help="real RTSP URLs (enables RTSP mode)")
    p.add_argument("--out", default=os.path.join("outputs", "soak"))
    p.add_argument("--label", default="calibration",
                   help="label recorded in the summary (e.g. calibration, 4h)")
    p.add_argument("--target-fps", type=float, default=10.0,
                   help="per-feed FPS the run is being compared against")
    return p.parse_args()


class VideoFeeder:
    """Loops a local video, one decode position per camera."""

    def __init__(self, path: str, count: int):
        self.path = path
        self.caps = [cv2.VideoCapture(path) for _ in range(count)]
        self.locks = [__import__("threading").Lock() for _ in range(count)]
        if not self.caps[0].isOpened():
            raise RuntimeError(f"cannot open video: {path}")

    def frame(self, idx: int):
        cap, lock = self.caps[idx], self.locks[idx]
        with lock:
            ok, frame = cap.read()
            if not ok:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
            return frame if ok else None


def main() -> int:
    args = parse_args()
    os.makedirs(args.out, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    jsonl_path = os.path.join(args.out, f"soak_{stamp}.jsonl")
    summary_path = os.path.join(args.out, f"soak_{stamp}_summary.json")

    mode = "rtsp" if args.urls else "compute"
    stream_count = len(args.urls) if args.urls else args.streams

    engine = get_pose_engine()
    engine.initialize()
    service = get_cloud_service()

    feeders = None
    if mode == "rtsp":
        for i, url in enumerate(args.urls, start=1):
            service.add_and_start_camera(f"soak-{i}", f"Soak Camera {i}", url)
    else:
        from yolo_cloud.rtsp_manager import RTSPStream, get_rtsp_manager

        RTSPStream.start = lambda self: None  # no ffmpeg in compute mode
        feeders = VideoFeeder(args.video, stream_count)
        manager = get_rtsp_manager()
        manager.get_frame = lambda cid: feeders.frame(int(cid.split("-")[-1]) - 1)
        for i in range(1, stream_count + 1):
            service.add_and_start_camera(f"soak-{i}", f"Soak Camera {i}", f"rtsp://soak/{i}")

    proc = psutil.Process()
    proc.cpu_percent(None)  # prime the counter

    print(f"mode={mode} streams={stream_count} duration={args.seconds}s interval={args.interval}s")
    print(f"source={args.urls or args.video}")
    print(f"backend={'bytetrack' if engine._bytetrack_cls else 'builtin-iou'} device=device(unset)")

    seen_ids: dict[str, set[int]] = {}
    prev: dict[str, tuple[int, float]] = {}
    cpu_samples: list[float] = []
    rss_samples: list[float] = []
    fps_samples: list[float] = []
    started = time.time()

    with open(jsonl_path, "w", encoding="utf-8") as log:
        while time.time() - started < args.seconds:
            time.sleep(args.interval)
            now = time.time()
            elapsed = round(now - started, 1)
            cameras = service.get_all_cameras()
            per_cam, new_events = [], 0
            for cam in cameras:
                cid = cam.get("camera_id")
                fc = cam.get("frame_count", 0)
                p = prev.get(cid)
                fps = (fc - p[0]) / (now - p[1]) if p and now > p[1] else 0.0
                prev[cid] = (fc, now)
                ids = {int(x["track_id"]) for x in cam.get("persons", [])}
                old = seen_ids.get(cid, set())
                new_events += len(ids - old) if old else 0
                seen_ids.setdefault(cid, set()).update(ids)
                per_cam.append({
                    "camera_id": cid,
                    "fps": round(fps, 2),
                    "workers": len(ids),
                    "frames": fc,
                    "distinct_tracks": len(seen_ids[cid]),
                })
                fps_samples.append(fps)
            cpu = proc.cpu_percent(None)
            rss = proc.memory_info().rss / 1e6
            cpu_samples.append(cpu)
            rss_samples.append(rss)
            row = {"t": elapsed, "cpu_pct": cpu, "rss_mb": round(rss, 1),
                   "cameras": per_cam, "new_track_events": new_events}
            log.write(json.dumps(row) + "\n")
            log.flush()
            if int(elapsed) % 10 < args.interval:
                print(f"  t={elapsed:5.0f}s cpu={cpu:5.1f}% rss={rss:7.1f}MB "
                      f"fps/stream={[c['fps'] for c in per_cam]}")

    reg = get_identity_registry()
    alerts = service.get_alerts(limit=1000)
    elapsed_s = time.time() - started
    # Processing metrics straight from the live processors: latency percentiles,
    # frame-drop counters and source lag. Read-only snapshot.
    stream_metrics = service.get_processing_metrics()
    tracking = engine.tracking_audit(elapsed_s)
    distinct = {cid: sorted(ids) for cid, ids in seen_ids.items()}

    # Count audit events by type, straight from the append-only JSONL (robust
    # regardless of the read-API limit) — override rate is a soak deliverable.
    audit_counts: dict[str, int] = {}
    try:
        from yolo_cloud import identity_audit as _audit

        _audit_path = _audit.audit_path()
        if os.path.exists(_audit_path):
            with open(_audit_path, "r", encoding="utf-8") as fh:
                for _line in fh:
                    try:
                        _ev = json.loads(_line).get("event")
                    except json.JSONDecodeError:
                        continue
                    if _ev:
                        audit_counts[_ev] = audit_counts.get(_ev, 0) + 1
    except Exception as exc:  # noqa: BLE001 - reporting must not fail the soak
        print(f"audit count skipped: {exc}")
    overrides = audit_counts.get("override", 0)
    binds = audit_counts.get("bind", 0) + audit_counts.get("rebind", 0)

    # Per-tile quality flags (booleans inside each person's `quality` dict)
    # from the latest camera snapshots.
    quality_counts: dict[str, int] = {"low_light": 0, "occluded": 0, "too_small": 0}
    try:
        for cam in service.get_all_cameras():
            for person in cam.get("persons", []):
                q = person.get("quality", {}) or {}
                for flag in quality_counts:
                    if q.get(flag):
                        quality_counts[flag] += 1
    except Exception as exc:  # noqa: BLE001
        print(f"quality flag count skipped: {exc}")

    decoded_total = sum(m["decoded_frames"] for m in stream_metrics)
    processed_total = sum(m["processed_frames"] for m in stream_metrics)
    dropped_total = sum(m["dropped_frames"] for m in stream_metrics)

    # Everything this run does NOT establish, stated inside the artifact so a
    # summary can never be read as covering it.
    not_measured = [
        "GPU memory / utilisation — no GPU on the measuring host "
        "(nvidia-smi absent, torch.cuda.is_available() == False)",
        "10 FPS per feed — frames are decoded at whatever rate the source "
        "provides; the measured processing rate is reported instead",
        "8 workers per feed — the available footage is single-worker clips, so "
        "real detection cannot produce 8 tracks per feed to measure",
        "4-hour continuous run — this is a short calibration run; the harness "
        "supports --seconds 14400 but the full-duration run was not executed",
        "clip encode cost as a share of frame latency — pre-alert clips ARE "
        "written during this soak (alerts do fire here and the per-camera ring "
        "buffer is saved on HIGH; clip frame counts measured separately in "
        "docs/TRL6_EVIDENCE.md), but the JPEG encode + file write happens inside "
        "the frame latency window and is not broken out as its own number",
        "ByteTrack-specific counters — ByteTrack cannot be imported in this "
        "ultralytics build; counters come from the active _SimpleTracker",
        "accuracy / detection quality of any kind",
    ]
    if decoded_total == 0:
        not_measured.append(
            "frame-drop rate — compute mode runs no FFmpeg decoder, so decoded "
            "frames stay 0; run with --urls <rtsp...> to measure drops"
        )

    summary = {
        "mode": mode,
        "started_utc": stamp,
        "duration_s": round(time.time() - started, 1),
        "streams": stream_count,
        "source": args.urls or args.video,
        "tracker_backend": "bytetrack" if engine._bytetrack_cls else "builtin-iou",
        "fps_per_stream": {
            "min": round(min(fps_samples), 2) if fps_samples else 0,
            "mean": round(statistics.fmean(fps_samples), 2) if fps_samples else 0,
            "max": round(max(fps_samples), 2) if fps_samples else 0,
        },
        "total_fps": round(sum(fps_samples) / max(1, len(fps_samples)), 2) if fps_samples else 0,
        "cpu_pct": {
            "mean": round(statistics.fmean(cpu_samples), 1) if cpu_samples else 0,
            "max": round(max(cpu_samples), 1) if cpu_samples else 0,
        },
        "rss_mb": {
            "mean": round(statistics.fmean(rss_samples), 1) if rss_samples else 0,
            "max": round(max(rss_samples), 1) if rss_samples else 0,
        },
        "distinct_tracks_per_camera": distinct,
        "total_distinct_tracks": sum(len(v) for v in distinct.values()),
        "id_switches": reg.switch_count(),
        "reentry_rebinds": reg.reentry_count,
        "reentry_ambiguous": reg.reentry_ambiguous_count,
        "alerts_total": len(alerts),
        "alerts_per_worker_hour": round(
            len(alerts) / max(1e-9, (stream_count * (time.time() - started) / 3600.0)), 2
        ),
        "identity_audit_counts": audit_counts,
        "supervisor_overrides": overrides,
        "override_rate": round(overrides / binds, 3) if binds else None,
        "tile_quality_flags_snapshot": quality_counts,
        "label": args.label,
        "latency": {
            # Percentiles cover the newest LATENCY_SAMPLE_MAX frames per stream
            # (bounded buffer), not necessarily every frame of a long run.
            "budget_ms": LATENCY_BUDGET_MS,
            "by_stream": {m["camera_id"]: m["latency_ms"] for m in stream_metrics},
            "inference_by_stream": {m["camera_id"]: m["inference_ms"] for m in stream_metrics},
            "source_lag_by_stream": {m["camera_id"]: m["source_lag_ms"] for m in stream_metrics},
            "p95_worst_stream_ms": max(
                (m["latency_ms"].get("p95", 0.0) for m in stream_metrics), default=0.0
            ),
            "over_budget_frames_total": sum(
                m.get("latency_over_budget_frames", 0) for m in stream_metrics
            ),
            "frames_scored_total": sum(m.get("frames_scored", 0) for m in stream_metrics),
            "samples_per_stream": max(
                (m["latency_ms"].get("n", 0) for m in stream_metrics), default=0
            ),
            "within_budget": bool(stream_metrics) and all(
                m["latency_ms"].get("p95", float("inf")) <= LATENCY_BUDGET_MS
                for m in stream_metrics
            ),
        },
        "frame_drops": {
            # Only meaningful with a real decoder: in compute mode no FFmpeg
            # reader runs, so a drop RATE would be a meaningless zero.
            "applicable": decoded_total > 0,
            "decoded_frames_total": decoded_total,
            "processed_frames_total": processed_total,
            "dropped_frames_total": dropped_total if decoded_total else None,
            "overall_drop_rate": (
                round(dropped_total / decoded_total, 4) if decoded_total else None
            ),
            "repeat_frames_total": sum(m["repeat_frames"] for m in stream_metrics),
            "by_stream": {
                m["camera_id"]: {
                    "decoded": m["decoded_frames"],
                    "processed": m["processed_frames"],
                    "dropped": m["dropped_frames"],
                    "drop_rate": m["drop_rate"],
                }
                for m in stream_metrics
            },
        },
        "tracking_audit": tracking,
        "spec_comparison": {
            "spec": "4 feeds x 8 workers x 10 FPS, p95 < 500 ms, continuous 4 h",
            "measured_streams": stream_count,
            # A 1- or 2-stream run is a CAPACITY PROBE, not a spec run: it asks
            # whether this host holds the p95 budget at that pool size. Naming the
            # class here is what lets a report say "1-2 streams within budget, 4
            # streams breach" instead of quoting one shortfall factor (e.g. 7.4x)
            # that silently mixes two different questions.
            "run_class": "capacity-probe" if stream_count < 4 else "spec-load",
            "run_class_note": (
                f"{stream_count} concurrent stream(s) on a CPU-only host. The spec's "
                "load point is 4 feeds, so this run establishes capacity at this pool "
                "size and is NOT a spec pass/fail."
                if stream_count < 4
                else "Spec load point (4 concurrent feeds): a BREACH here is a real "
                "miss at the spec's own concurrency."
            ),
            # Shortfall against the 10 FPS/feed target is only a spec statement
            # when the run actually reproduces the spec's concurrency.
            "fps_shortfall_is_spec_meaningful": stream_count >= 4,
            "measured_fps_per_stream_mean": (
                round(statistics.fmean(fps_samples), 2) if fps_samples else 0
            ),
            "target_fps_per_stream": args.target_fps,
            "fps_shortfall_factor": (
                round(args.target_fps / statistics.fmean(fps_samples), 1)
                if fps_samples and statistics.fmean(fps_samples) > 0 else None
            ),
            "workers_per_feed_available": 1,
            "workers_per_feed_target": 8,
            "p95_within_budget": bool(stream_metrics) and all(
                m["latency_ms"].get("p95", float("inf")) <= LATENCY_BUDGET_MS
                for m in stream_metrics
            ),
            "run_completed_full_spec_duration": elapsed_s >= 4 * 3600,
        },
        "not_measured": not_measured,
        "machine": {
            "cpus": psutil.cpu_count(),
            "ram_gb": round(psutil.virtual_memory().total / 1e9, 1),
            "gpu_measured": False,
            "note": "no GPU present on the measuring host; GPU memory is NOT measured",
        },
    }
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    lat = summary["latency"]
    print(
        f"\nVERDICT [{args.label}]: p95 worst stream = {lat['p95_worst_stream_ms']} ms "
        f"(budget {lat['budget_ms']} ms) -> "
        f"{'WITHIN' if lat['within_budget'] else 'BREACH'}; "
        f"{lat['over_budget_frames_total']}/{lat['frames_scored_total']} scored frames over budget"
    )
    sc = summary["spec_comparison"]
    # The split line: what THIS pool size says, kept separate from the spec.
    print(
        f"          scale: {sc['measured_streams']} stream(s) = {sc['run_class']} -> "
        f"{'WITHIN' if sc['p95_within_budget'] else 'BREACH'} budget at this pool size "
        f"({sc['measured_fps_per_stream_mean']} FPS/stream)"
    )
    if sc["fps_shortfall_is_spec_meaningful"]:
        print(
            f"          spec FPS gap: {sc['fps_shortfall_factor']}x short of "
            f"{sc['target_fps_per_stream']} FPS/stream at spec load"
        )
    else:
        print(
            f"          {sc['fps_shortfall_factor']}x shortfall vs the "
            f"{sc['target_fps_per_stream']} FPS target is NOT a spec number at "
            f"{sc['measured_streams']} streams — capacity probe only"
        )
    if summary["frame_drops"]["applicable"]:
        print(
            f"          drops {summary['frame_drops']['dropped_frames_total']} of "
            f"{summary['frame_drops']['decoded_frames_total']} decoded frames "
            f"(rate {summary['frame_drops']['overall_drop_rate']})"
        )
    else:
        print("          drops NOT APPLICABLE (compute mode runs no decoder)")
    print(f"          NOT measured: {len(summary['not_measured'])} items — see summary.not_measured")
    print(f"\nwrote {jsonl_path}\nwrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
