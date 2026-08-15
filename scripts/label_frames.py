"""Ground-truth frame labeling tool (Phase 2 of docs/DATA_COLLECTION_GUIDE.md).

Opens a session recording's ``original.mp4`` with OpenCV, shows every Nth frame,
and records a human labeler's verdict keyed by frame number. Produces
``ground_truth_risk.json`` (risk pass: LOW/MEDIUM/HIGH) or
``ground_truth_task.json`` (task pass: 5 task classes + Unknown) in the guide's
exact format:

    {
      "session_id": "SESH-...",
      "labeler": "annotator_name",
      "date": "2026-07-25",
      "frames": [
        {"frame": 0, "label": "LOW"},
        {"frame": 30, "label": "LOW"}
      ]
    }

Usage:
    venv/Scripts/python.exe scripts/label_frames.py --video recordings/worker-001/2026.../original.mp4 --kind risk --labeler "Me"
    venv/Scripts/python.exe scripts/label_frames.py --video recordings/worker-001/2026.../ --kind task --labeler "Me" --step 10
    venv/Scripts/python.exe scripts/label_frames.py --video recordings/worker-001/2026.../ --prelabel  # seed provisional labels from timeline.json

``--prelabel`` seeds each candidate frame with the prediction the pipeline
recorded at capture time (from the recording's ``timeline.json``, matched by
nearest timestamp). Those are **provisional placeholders only** — the tool then
walks every seeded frame so the human confirms or overrides each one before it
counts as ground truth. The output file notes ``prelabel_source`` so the
provenance stays visible.

Keys:
    Risk pass:  1 = LOW, 2 = MEDIUM, 3 = HIGH
    Task pass:  1 = Neutral Standing, 2 = Assembly Work, 3 = Reaching,
                4 = Lifting / Picking, 5 = Inspection, 0 = Unknown
    Space       pause / resume playback
    Left/Right  step one frame back / forward (skip frames)
    q / ESC     save and quit

Existing labels in the output file are loaded on start (resume) and never
overwritten. Labels are also flushed to disk every 20 new verdicts so a crash
does not lose the session's work.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from bisect import bisect_left
from datetime import date, datetime
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RISK_LABELS = {"1": "LOW", "2": "MEDIUM", "3": "HIGH"}
TASK_LABELS = {
    "1": "Neutral Standing",
    "2": "Assembly Work",
    "3": "Reaching",
    "4": "Lifting / Picking",
    "5": "Inspection",
    "0": "Unknown",
}
AUTO_SAVE_EVERY = 20


def resolve_video(path: Path) -> Path:
    """Accept either the mp4 itself or a recording directory containing it."""
    if path.is_dir():
        candidate = path / "original.mp4"
        if not candidate.exists():
            sys.exit(f"No original.mp4 found in {path}")
        return candidate
    if path.is_file() and path.suffix.lower() in (".mp4", ".avi", ".mov"):
        return path
    sys.exit(f"Cannot find a video at {path}")


def resolve_session_id(video: Path) -> str:
    """Prefer summary.json's session_id; fall back to the recording dir name."""
    summary = video.parent / "summary.json"
    if summary.exists():
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
            if data.get("session_id"):
                return str(data["session_id"])
        except (json.JSONDecodeError, OSError):
            pass
    name = video.parent.name
    if "SESH-" in name:
        return name.split("SESH-", 1)[1]
    return name or "unknown"


def load_existing(out_path: Path, labeler: str) -> tuple[dict, dict]:
    """Return (metadata, {frame_index: label}) from a previous run, if any."""
    if out_path.exists():
        try:
            data = json.loads(out_path.read_text(encoding="utf-8"))
            frames = {int(f["frame"]): f["label"] for f in data.get("frames", [])}
            if frames:
                print(f"Resumed: {len(frames)} already-labeled frames loaded from {out_path}")
            return data, frames
        except (json.JSONDecodeError, OSError, KeyError, ValueError) as exc:
            print(f"Warning: could not load existing {out_path} ({exc}); starting fresh")
    return {"session_id": "", "labeler": labeler, "date": date.today().isoformat(), "frames": []}, {}


def load_prelabels(timeline_path: Path, total: int, fps: float, step: int,
                   kind: str, tolerance: float = 0.5) -> dict[int, str]:
    """Provisional labels from the recording's own timeline.json predictions.

    Seeds every ``step``th frame with the nearest timeline entry's prediction
    within ``tolerance`` seconds (default 0.5 — tight, so a prelabel only appears
    where a prediction genuinely exists nearby; frame index converted to time
    via ``fps``; timeline ``frame_number`` is a processed-frame counter, not a
    video index, so timestamps are the join key). These are placeholders the
    human confirms or overrides — never ground truth by themselves.
    """
    try:
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  ! Could not read {timeline_path}: {exc}")
        return {}
    if not isinstance(timeline, list) or not timeline:
        print(f"  ! {timeline_path} is empty or not a list of records — no prelabels")
        return {}
    pairs = sorted((e.get("timestamp"), e) for e in timeline if e.get("timestamp") is not None)
    if not pairs:
        print(f"  ! {timeline_path} has no timestamped records — no prelabels")
        return {}
    keys = [p[0] for p in pairs]
    key_field = "risk_level" if kind == "risk" else "current_task"
    prelabels: dict[int, str] = {}
    for idx in range(0, total, step):
        target = idx / fps
        pos = bisect_left(keys, target)
        best = None
        best_err = float("inf")
        for cand in (pos - 1, pos, pos + 1):
            if 0 <= cand < len(pairs):
                err = abs(pairs[cand][0] - target)
                if err < best_err:
                    best_err = err
                    best = pairs[cand][1]
        if best is not None and best_err <= tolerance:
            value = best.get(key_field)
            if value is not None:
                cleaned = str(value).strip()
                prelabels[idx] = cleaned.upper() if kind == "risk" else cleaned
    return prelabels


def generate_timeline(video: Path, timeline_path: Path, model_path: Path,
                       progress_every: int = 60) -> list[dict]:
    """Run pose extraction frame-by-frame and write a ``timeline.json``.

    Processes **every** video frame sequentially through ``PoseEngine`` so
    MediaPipe's VIDEO-mode temporal tracking stays active — the fix for
    randomly jumping keypoints on recorded videos (sampled/fast-forwarded
    extraction resets the tracker between frames). Also records normalized
    keypoints per frame so the labeling window can draw a persistent skeleton
    overlay that never blinks between samples.

    The output is the same list-of-records format ``load_prelabels()`` reads
    (``timestamp`` + ``risk_level`` / ``current_task`` keys), so a freshly
    generated timeline feeds ``--prelabel`` identically to a recording's own
    timeline. Returns the records written.
    """
    from backend.services.performance import frame_skipper
    from backend.services.pose_engine import PoseEngine

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        sys.exit(f"OpenCV could not open {video}")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = cap.get(cv2.CAP_PROP_FPS) or 1.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1)

    engine = PoseEngine(str(model_path))
    # Deterministically process every frame: the time-based frame skipper is
    # designed for live capture and could drop frames here.
    _orig_should = frame_skipper.should_process
    frame_skipper.should_process = lambda: True
    records: list[dict] = []
    frame_idx = 0
    print(f"  [timeline] generating {total} frames sequentially (temporal tracking on)...")
    try:
        engine.initialize()  # inside try/finally: failure must release cap + engine
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            result = engine.process_frame(frame)
            if result.person_detected and result.keypoints:
                # Normalize to 0-1 like the video-analysis pipeline so the
                # same draw_skeleton overlay used on the live feed can render.
                kps = [[kp[0] / width, kp[1] / height, kp[2], kp[3]] for kp in result.keypoints]
                task = (result.task_info or {}).get("task", "Unknown") if result.task_info else "Unknown"
                records.append({
                    "timestamp": round(frame_idx / fps, 3),
                    "frame_number": frame_idx,
                    "risk_level": result.risk_level,
                    "current_task": task,
                    "confidence": round(float(result.confidence), 2),
                    # NaN and ±inf -> None so the file stays strict-JSON-safe
                    # (bare Infinity/NaN tokens break JSON.parse in JS tools).
                    "features": {k: (None if v != v or abs(v) == float("inf")
                                     else round(float(v), 4))
                                 for k, v in result.features.items()},
                    "keypoints": kps,
                })
            frame_idx += 1
            if progress_every and frame_idx % progress_every == 0:
                print(f"  [timeline] {frame_idx}/{total} frames ({len(records)} with pose)")
    finally:
        frame_skipper.should_process = _orig_should
        cap.release()
        engine.release()

    timeline_path.parent.mkdir(parents=True, exist_ok=True)
    timeline_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"  [timeline] wrote {len(records)} records to {timeline_path} "
          f"({len(records)} of {frame_idx} frames had a person)")
    return records


def build_overlay_index(timeline_path: Path) -> list[tuple[float, dict]]:
    """Load a timeline and return ``[(timestamp, record), ...]`` sorted by time.

    Records are matched to the displayed frame by nearest timestamp (the same
    join key ``load_prelabels`` uses) so the skeleton overlay tracks the pose
    across playback instead of only on the frames pose was sampled on.
    """
    try:
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(timeline, list):
        return []
    pairs = [(e.get("timestamp"), e) for e in timeline
             if isinstance(e, dict) and e.get("timestamp") is not None]
    pairs.sort(key=lambda p: p[0])
    return pairs


def save(out_path: Path, meta: dict, frames: dict) -> None:
    meta["frames"] = [{"frame": int(f), "label": label} for f, label in sorted(frames.items())]
    out_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    counts: dict[str, int] = {}
    for label in frames.values():
        counts[label] = counts.get(label, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    print(f"Saved {len(frames)} labels to {out_path} ({summary})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Label posture-risk or task classes per frame.")
    parser.add_argument("--video", required=True,
                        help="Path to original.mp4 or the recording directory containing it")
    parser.add_argument("--kind", choices=("risk", "task"), default="risk",
                        help="Which labeling pass to run (default: risk)")
    parser.add_argument("--labeler", default="unknown", help="Annotator name for provenance")
    parser.add_argument("--step", type=int, default=1,
                        help="Label every Nth frame for sparse labeling (default: 1 = every frame)")
    parser.add_argument("--out", help="Output JSON path (default: <video_dir>/ground_truth_<kind>.json)")
    parser.add_argument("--export-frames", metavar="DIR", default=None,
                        help="Headless mode: extract every Nth frame as PNG into DIR/frames/ "
                             "plus a frames_manifest.json, then exit (no display needed; "
                             "supports VIA/CVAT-style offline labeling)")
    parser.add_argument("--prelabel", action="store_true",
                        help="Seed provisional labels from the recording's timeline.json "
                             "predictions (matched by nearest timestamp); each is then "
                             "confirmed or overridden manually")
    parser.add_argument("--timeline",
                        help="timeline.json path for --prelabel (default: <video_dir>/timeline.json)")
    args = parser.parse_args()

    if args.step < 1:
        sys.exit("--step must be >= 1")

    video = resolve_video(Path(args.video))

    # ── Headless frame extraction (VIA/CVAT path) ────────────────────────
    if args.export_frames:
        out_dir = Path(args.export_frames)
        frames_dir = out_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            sys.exit(f"OpenCV could not open {video}")
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 1.0
        session_id = resolve_session_id(video)

        extracted = []
        for idx in range(0, total, args.step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue
            png_name = f"frame_{idx:06d}.png"
            png_path = frames_dir / png_name
            if not cv2.imwrite(str(png_path), frame):
                print(f"Warning: failed to write {png_path}")
                continue
            extracted.append({"frame": idx, "png": png_name})
        cap.release()

        manifest = {
            "session_id": session_id,
            "source_video": str(video),
            "total_frames": total,
            "fps": fps,
            "step": args.step,
            "frames_extracted": len(extracted),
            "frames": extracted,
        }
        manifest_path = out_dir / "frames_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Extracted {len(extracted)} frames (every {args.step}th of {total}) to {frames_dir}")
        print(f"Manifest written to {manifest_path} (session {session_id})")
        return

    if not video.exists():
        sys.exit(f"Video not found: {video}")

    labels = RISK_LABELS if args.kind == "risk" else TASK_LABELS
    default_name = f"ground_truth_{args.kind}.json"
    out_path = Path(args.out) if args.out else video.parent / default_name

    meta, frames = load_existing(out_path, args.labeler)
    meta.setdefault("session_id", resolve_session_id(video))
    meta.setdefault("labeler", args.labeler)
    meta.setdefault("date", date.today().isoformat())

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        sys.exit(f"OpenCV could not open {video}")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 1.0
    print(f"\nLabeling: {video}")
    print(f"  session_id: {meta['session_id']} | kind: {args.kind} | total frames: {total} | fps: {fps:.1f}")
    print(f"  existing labels: {len(frames)} | step: {args.step}")

    # ── Optional: seed provisional labels from the recording's timeline.json ──
    confirmed = set(frames)  # human-entered labels (loaded from file or keyed this session)
    prelabels: dict[int, str] = {}
    timeline_path: Path | None = None
    if args.prelabel:
        timeline_path = Path(args.timeline) if args.timeline else video.parent / "timeline.json"
        if not timeline_path.exists():
            # No timeline on disk (e.g. a review clip exported by the video
            # analyzer): generate one frame-by-frame on the fly. Sequential
            # processing keeps MediaPipe temporal tracking alive, so the
            # overlay keypoints stay stable and prelabels appear immediately.
            model_path = Path(os.environ.get("POSE_MODEL_PATH", ROOT / "models" / "pose_landmarker_lite.task"))
            if not model_path.exists():
                sys.exit(f"Pose model not found at {model_path} — cannot auto-generate a timeline. "
                         f"Set POSE_MODEL_PATH or copy the .task file into models/.")
            print(f"  ! --prelabel set but no timeline.json at {timeline_path} — generating one now")
            generate_timeline(video, timeline_path, model_path)
        prelabels = load_prelabels(timeline_path, total, fps, args.step, args.kind)
        prelabels = {k: v for k, v in prelabels.items() if k not in confirmed}
        frames = {**prelabels, **frames}
        meta.setdefault("prelabel_source",
                        f"{timeline_path.name} (provisional, needs human review)")
        print(f"  prelabeled {len(prelabels)} frames from {timeline_path.name} — "
              f"review each frame and press a key to confirm or override")
    print(f"  keys: {labels}")
    print("  Space=pause  Left/Right=step  q/ESC=save & quit\n")

    # Playback control
    idx = 0
    paused = True  # start paused so the first frame is examined deliberately
    new_since_save = 0
    done = False

    # ── Persistent skeleton overlay (sample retention) ────────────────
    # Pose was analyzed on a subset of frames; without retention the skeleton
    # would blink on/off on every unsampled frame. Hold the last valid pose
    # and risk, refresh it whenever the displayed frame hits a nearby timeline
    # record, and keep drawing it until a newer pose replaces it.
    overlay_index: list[tuple[float, dict]] = (
        build_overlay_index(timeline_path) if timeline_path is not None else []
    )
    overlay_keys = [t for t, _ in overlay_index]
    last_pose: list | None = None
    last_pose_risk = "LOW"
    last_pose_features: dict = {}
    last_pose_hit = -1
    # Expire the held pose after this many seconds without a refresh — if the
    # worker left the frame, a lingering "ghost" skeleton would mislead the
    # labeler. Timeline gaps = no person detected, so gaps expire naturally.
    POSE_HOLD_SECONDS = 2.0
    last_pose_frame = -10**9  # video frame index when last_pose was refreshed
    _draw_overlay = None
    if overlay_index and any(rec.get("keypoints") for _, rec in overlay_index):
        try:
            from backend_api.app.services.pose_overlay import draw_skeleton as _draw_overlay
        except ImportError:
            _draw_overlay = None
        if _draw_overlay is not None:
            print(f"  overlay: persistent skeleton on ({len(overlay_index)} timeline records)")

    # Fast-forward to the first unconfirmed frame when resuming
    if confirmed:
        labeled = sorted(confirmed)
        # Next candidate after the largest confirmed frame, aligned to step
        start = labeled[-1] + args.step
        idx = start - (start % args.step) if start % args.step else start
        idx = min(idx, total - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)

    while True:
        if not paused:
            idx += 1
        if idx >= total:
            print("Reached end of video.")
            done = True
            break
        if idx < 0:
            idx = 0

        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            print(f"Could not read frame {idx}; stopping.")
            done = True
            break

        if idx in confirmed:
            status = "LABELED"
        elif idx in prelabels:
            status = "PRELBL"
        else:
            status = "unlabeled"

        # Refresh the retained pose from the nearest timeline record (within
        # 0.5s, same tolerance as prelabel matching) — the overlay persists
        # across unsampled frames instead of flickering off.
        if overlay_index:
            target = idx / fps
            pos = bisect_left(overlay_keys, target)
            best_i, best_err = -1, float("inf")
            for cand in (pos - 1, pos, pos + 1):
                if 0 <= cand < len(overlay_index):
                    err = abs(overlay_index[cand][0] - target)
                    if err < best_err:
                        best_err, best_i = err, cand
            if best_i >= 0 and best_err <= 0.5 and best_i != last_pose_hit:
                rec = overlay_index[best_i][1]
                kps = rec.get("keypoints")
                if kps:
                    last_pose = kps
                    last_pose_risk = rec.get("risk_level", "LOW")
                    last_pose_features = rec.get("features") or {}
                    last_pose_hit = best_i
                    last_pose_frame = idx
        # Ghost-pose expiry: no fresh sample for POSE_HOLD_SECONDS -> clear.
        if last_pose is not None and (idx - last_pose_frame) / fps > POSE_HOLD_SECONDS:
            last_pose = None

        if _draw_overlay is not None and last_pose is not None:
            try:
                frame = _draw_overlay(frame, last_pose, last_pose_risk,
                                      features=last_pose_features)
            except Exception:  # noqa: BLE001 - overlay must never block labeling
                pass

        overlay = frame.copy()
        cv2.putText(overlay, f"frame {idx}/{total - 1} [{status}] step={args.step}",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(overlay, f"{'PAUSED' if paused else 'PLAYING'}  kind={args.kind}  labels={len(frames)}",
                    (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        if _draw_overlay is not None and last_pose is not None:
            cv2.putText(overlay, f"overlay RISK: {last_pose_risk} (held from last sample)", (10, 118),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
        if idx in frames:
            tag = " (prelabel)" if idx in prelabels and idx not in confirmed else ""
            cv2.putText(overlay, f"current: {frames[idx]}{tag}", (10, 88),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)

        cv2.imshow("ErgoVigilance ground-truth labeling", overlay)
        key = cv2.waitKey(30 if not paused else 0) & 0xFF

        if key in (ord("q"), 27):  # q or ESC
            done = True
            break
        elif key == ord(" "):  # pause / resume
            paused = not paused
        elif key in (81, 82, 2, 3):  # Left / Right arrows
            paused = True
            idx += -1 if key in (81, 2) else 1
            idx = max(0, min(idx, total - 1))
        elif key != 255:
            ch = chr(key)
            if ch in labels:
                frames[idx] = labels[ch]
                confirmed.add(idx)
                new_since_save += 1
                if new_since_save >= AUTO_SAVE_EVERY:
                    save(out_path, meta, frames)
                    new_since_save = 0
                # Advance to the next unconfirmed candidate (prelabels get reviewed too)
                nxt = idx + args.step
                while nxt in confirmed and nxt < total:
                    nxt += args.step
                idx = nxt if nxt < total else idx
                if idx >= total:
                    done = True
                    break
            else:
                print(f"Unknown key '{ch}' — expected one of: {', '.join(labels)}")

    cap.release()
    cv2.destroyAllWindows()

    if frames:
        save(out_path, meta, frames)
        print(f"\nDone. {len(frames)} frames labeled for session {meta['session_id']} "
              f"by {meta['labeler']} on {meta['date']}.")
    else:
        print("\nNo labels recorded — nothing saved.")


if __name__ == "__main__":
    main()
