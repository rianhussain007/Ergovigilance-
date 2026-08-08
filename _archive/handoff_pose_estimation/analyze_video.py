
"""
analyze_video.py — Standalone CLI for single-video posture analysis.

Usage:
    python analyze_video.py <video_path> [--model <path>] [--output <path>] [--every N]

Example:
    python analyze_video.py demo.mp4
    python analyze_video.py demo.mp4 --output results.json --every 5
"""

import argparse
import json
import sys
import time

import cv2

from pose_engine import PoseEngine
from features import compute_rula_informed_score
from guidance import build_guidance


def _download_default_model(cache_path: str) -> str:
    import os
    import urllib.request

    url = (
        "https://storage.googleapis.com/mediapipe-models/"
        "pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
    )
    if not os.path.exists(cache_path):
        print(f"Downloading MediaPipe pose model to {cache_path} ...")
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        urllib.request.urlretrieve(url, cache_path)
    return cache_path


def main():
    parser = argparse.ArgumentParser(description="Per-frame posture analysis on a video file.")
    parser.add_argument("video", help="Path to input video file")
    parser.add_argument("--model", default=None, help="Path to MediaPipe PoseLandmarker model (.task)")
    parser.add_argument("--output", default=None, help="Path to output JSON file (default: print to stdout)")
    parser.add_argument("--every", type=int, default=1, help="Process every Nth frame (default: 1 = all frames)")
    args = parser.parse_args()

    if args.model:
        model_path = args.model
    else:
        model_path = _download_default_model(
            "models/pose_landmarker_lite.task"
        )

    print(f"Opening video: {args.video}")
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Error: Could not open video {args.video}", file=sys.stderr)
        sys.exit(1)

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Video: {total_frames} frames @ {fps:.1f} FPS")

    print("Initializing PoseEngine ...")
    engine = PoseEngine(model_path)
    engine.initialize()

    frames_data = []
    frame_index = 0
    processed = 0
    start_wall = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_index % args.every != 0:
                frame_index += 1
                continue

            result = engine.process_frame(frame)

            rula = compute_rula_informed_score(result.features, result.unavailable_features)

            guidance = build_guidance(result.features)

            entry = {
                "frame_index": frame_index,
                "timestamp_sec": round(frame_index / fps, 3) if fps > 0 else frame_index,
                "person_detected": result.person_detected,
                "confidence": round(result.confidence, 1),
            }

            if result.person_detected:
                entry["risk_level"] = result.risk_level
                entry["features"] = {k: round(v, 4) if v == v else None for k, v in result.features.items()}
                entry["unavailable_features"] = result.unavailable_features
                entry["approximate_features"] = result.approximate_features
                entry["lower_body_confidence"] = round(result.lower_body_confidence, 1)
                entry["rula"] = rula
                entry["guidance"] = guidance

                if result.task_info:
                    entry["task"] = {
                        "name": result.task_info.get("task", "Unknown"),
                        "confidence": result.task_info.get("confidence", 0.0),
                        "reason": result.task_info.get("reason", ""),
                        "duration_seconds": result.task_info.get("task_duration_seconds", 0.0),
                    }

                entry["issues"] = result.issues
                entry["recommendations"] = [
                    {
                        "issue": r["issue"],
                        "severity": r["severity"],
                        "worker_actions": r.get("worker_actions", []),
                        "supervisor_actions": r.get("supervisor_actions", []),
                    }
                    for r in result.recommendations
                ]

            frames_data.append(entry)
            processed += 1

            if processed % 50 == 0:
                elapsed = time.time() - start_wall
                rate = processed / elapsed if elapsed > 0 else 0
                print(f"  Processed {processed} frames ({rate:.1f} fps) ...")

            frame_index += 1

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        engine.release()
        cap.release()

    elapsed = time.time() - start_wall
    print(f"\nDone. Processed {processed} frames in {elapsed:.1f}s ({processed/elapsed:.1f} fps).")

    output = {
        "metadata": {
            "video": args.video,
            "total_frames": total_frames,
            "fps": fps,
            "frames_processed": processed,
            "every_nth": args.every,
            "elapsed_seconds": round(elapsed, 2),
        },
        "frames": frames_data,
    }

    if args.output:
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"Results written to {args.output}")
    else:
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
