"""One-time backfill of session risk summaries corrupted by the pre-fix engine.

Context (2026-08): two defects made saved session summaries show HIGH on
sessions that were actually LOW/neutral:

1. ``head_tilt_angle`` measured the ear->nose vector against image-vertical
   (a profile-view convention). On frontal webcam poses it read 150-173 deg
   on neutral heads, so ``risk_from_features`` fired HIGH on every frame.
2. The analytics summary counted the *raw pose-engine* risk level, while the
   live timeline/UI showed the *context-moderated* level - so a session could
   display LOW live and still save as "HIGH 100%".
3. Sessions where no person was ever usable (confidence < 30, all features
   NaN) scored HIGH from the fail-closed "unknown features" policy, even
   though the pose engine explicitly returns LOW for no-person frames.

This script re-scores every stored per-frame feature set with the FIXED
engine, then rewrites the risk fields of:
  - recordings/<worker>/<dir>/summary.json
  - outputs/sessions/session_*.json

Rules per frame:
  - confidence < 30  -> "LOW" (no usable person detection; not an assessment)
  - otherwise        -> risk_from_features(features, unavailable) with the
                        stored (garbage) head_tilt_angle zeroed when it lies
                        outside the fixed convention's 0-90 deg range.

Run:  venv/Scripts/python.exe scripts/backfill_risk_summaries.py [--dry-run]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter
from typing import Any

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
# Put the project ROOT (parent of backend/) and backend_api/ on the path — the
# import machinery looks for ``backend/__init__.py`` / ``app/__init__.py``
# INSIDE each path entry, so the packages' parent dirs are what must be listed.
sys.path.insert(0, os.path.abspath(os.path.join(_SCRIPTS_DIR, "..")))
sys.path.insert(0, os.path.abspath(os.path.join(_SCRIPTS_DIR, "..", "backend_api")))

from backend.services.features import risk_from_features  # noqa: E402
from backend.services.issue_detection import detect_posture_issues  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RECORDINGS_DIR = os.path.join(ROOT, "recordings")
SESSIONS_DIR = os.path.join(ROOT, "outputs", "sessions")

PERSON_CONFIDENCE_MIN = 30.0  # below this, landmarks are unusable -> "no assessment"

# Summary fields that are safe to recompute from stored per-frame features.
AVG_FIELDS = [
    "avg_neck_flexion",
    "avg_trunk_flexion",
    "avg_shoulder_symmetry",
    "avg_knee_angle",
    "avg_forward_head_posture",
    "avg_head_tilt_angle",
    "avg_wrist_deviation_angle",
    "avg_stance_stability",
    "avg_weight_shift_offset",
]
FEATURE_KEY = {
    "avg_neck_flexion": "neck_flexion",
    "avg_trunk_flexion": "trunk_flexion",
    "avg_shoulder_symmetry": "shoulder_symmetry",
    "avg_knee_angle": "knee_angle",
    "avg_forward_head_posture": "forward_head_posture",
    "avg_head_tilt_angle": "head_tilt_angle",
    "avg_wrist_deviation_angle": "wrist_deviation_angle",
    "avg_stance_stability": "stance_stability",
    "avg_weight_shift_offset": "weight_shift_offset",
}


def sanitize(features: dict, unavailable: list[str]) -> tuple[dict[str, float], list[str]]:
    """Reconstruct a re-scoreable feature dict from the stored timeline row.

    Stored features use None for NaN (unavailable); those move into the
    unavailable list. The pre-fix head_tilt_angle convention produced values
    in 150-173 deg on neutral heads; the fixed convention is 0-90 deg, so any
    stored value outside 0-90 is treated as the neutral 0.0.
    """
    unavail = set(unavailable or [])
    out: dict[str, float] = {}
    for key, val in (features or {}).items():
        if val is None:
            unavail.add(key)
            out[key] = float("nan")
        else:
            out[key] = float(val)
    ht = out.get("head_tilt_angle")
    if ht is not None and ht == ht and (ht > 90.0 or ht < 0.0):
        out["head_tilt_angle"] = 0.0
    return out, sorted(unavail)


# Same implausibility bounds as backend/services/features.py risk_from_features:
# a corrupt pose (landmarks snapped to furniture, person half out of frame)
# cannot be a valid HIGH-risk assessment.
_IMPLAUSIBLE_MAX = {
    "neck_flexion": 90.0,
    "trunk_flexion": 90.0,
    "shoulder_symmetry": 150.0,
    "forward_head_posture": 200.0,
    "head_tilt_angle": 90.0,
    "wrist_deviation_angle": 180.0,
    "weight_shift_offset": 200.0,
}


def _is_implausible(feats: dict[str, float]) -> bool:
    for key, limit in _IMPLAUSIBLE_MAX.items():
        val = feats.get(key)
        if val is not None and val == val and val > limit:
            return True
    return False


def recompute(frames: list[dict]) -> dict[str, Any]:
    """Re-score one session's frames with the fixed engine."""
    levels: Counter[str] = Counter()
    issues: Counter[str] = Counter()
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    n_detected = 0
    n_invalid = 0
    total = len(frames)

    for frame in frames:
        conf = float(frame.get("confidence") or 0.0)
        feats, unavail = sanitize(frame.get("features") or {}, frame.get("unavailable_features") or [])
        if conf < PERSON_CONFIDENCE_MIN or _is_implausible(feats):
            levels["LOW"] += 1
            if conf >= PERSON_CONFIDENCE_MIN and _is_implausible(feats):
                n_invalid += 1
                issues["Invalid pose data"] += 1
        else:
            levels[risk_from_features(feats, unavail)] += 1
            n_detected += 1
            for issue in detect_posture_issues(feats) or []:
                name = issue.get("issue") or "Unknown Issue"
                issues[name] += 1
        for key, val in feats.items():
            if val == val:  # not NaN
                sums[key] = sums.get(key, 0.0) + val
                counts[key] = counts.get(key, 0) + 1

    risk_pct = {
        k: round(levels.get(k, 0) / total * 100, 1) if total else 0.0
        for k in ("LOW", "MEDIUM", "HIGH")
    }
    highest = "LOW"
    for level in ("LOW", "MEDIUM", "HIGH"):
        if levels.get(level, 0) > 0:
            highest = level
    # ``risk_level`` = the DOMINANT level (plurality of frames). The list and
    # calendar use this so a session that was 98% MEDIUM with one stray HIGH
    # frame doesn't render as a red "high risk" session. ``highest_risk_level``
    # keeps its peak semantics for reports.
    dominant = "LOW"
    dominant_count = -1
    for level in ("LOW", "MEDIUM", "HIGH"):
        if levels.get(level, 0) > dominant_count:
            dominant = level
            dominant_count = levels.get(level, 0)

    if n_detected == 0 and n_invalid == 0:
        most_frequent = "No worker detected"
        most_frequent_count = total
    elif n_detected == 0 and n_invalid > 0:
        most_frequent = "Invalid pose data"
        most_frequent_count = n_invalid
    elif issues:
        most_frequent = max(issues, key=issues.get)
        most_frequent_count = issues[most_frequent]
    else:
        most_frequent = None
        most_frequent_count = 0

    avgs: dict[str, float] = {}
    for avg_field, feat_key in FEATURE_KEY.items():
        c = counts.get(feat_key, 0)
        avgs[avg_field] = round(sums.get(feat_key, 0.0) / c, 2) if c else 0.0

    return {
        "total_frames": total,
        "risk_percentages": risk_pct,
        "highest_risk_level": highest,
        "risk_level": dominant,
        "most_frequent_issue": most_frequent,
        "most_frequent_issue_count": most_frequent_count,
        **avgs,
    }


def find_session_file(dir_basename: str) -> str | None:
    """Match a recordings dir basename to outputs/sessions/session_*.json."""
    candidates = [
        os.path.join(SESSIONS_DIR, f"session_{dir_basename}.json"),
        os.path.join(SESSIONS_DIR, f"session_{dir_basename[:15]}.json"),
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return cand
    # Fall back to scanning (filenames embed the same session timestamp).
    for fname in os.listdir(SESSIONS_DIR):
        if fname.startswith("session_") and fname.endswith(".json") and dir_basename in fname:
            return os.path.join(SESSIONS_DIR, fname)
    return None


def update_summary(summary: dict, result: dict) -> dict:
    summary["risk_percentages"] = result["risk_percentages"]
    summary["highest_risk_level"] = result["highest_risk_level"]
    summary["risk_level"] = result["risk_level"]
    summary["most_frequent_issue"] = result["most_frequent_issue"]
    summary["most_frequent_issue_count"] = result["most_frequent_issue_count"]
    for field in AVG_FIELDS:
        summary[field] = result[field]
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="print changes without writing")
    args = parser.parse_args()

    timelines = sorted(glob.glob(os.path.join(RECORDINGS_DIR, "*", "*", "timeline.json")))
    updated_sessions = 0
    updated_recordings = 0
    no_timeline_sessions = 0
    skipped_empty = 0

    for tl in timelines:
        dir_path = os.path.dirname(tl)
        dir_basename = os.path.basename(dir_path)
        try:
            frames = json.load(open(tl, encoding="utf-8"))
        except Exception as exc:
            print(f"SKIP (unreadable timeline) {dir_basename}: {exc}")
            continue
        if not frames:
            skipped_empty += 1
            continue

        result = recompute(frames)

        # recordings/<worker>/<dir>/summary.json
        summary_path = os.path.join(dir_path, "summary.json")
        if os.path.exists(summary_path):
            with open(summary_path, encoding="utf-8") as f:
                summary = json.load(f)
            before = (summary.get("highest_risk_level"), summary.get("risk_percentages"))
            update_summary(summary, result)
            if args.dry_run:
                print(f"DRY recordings {dir_basename}: {before} -> {result['highest_risk_level']} {result['risk_percentages']} issue={result['most_frequent_issue']}")
            else:
                with open(summary_path, "w", encoding="utf-8") as f:
                    json.dump(summary, f, indent=2)
                updated_recordings += 1

        # outputs/sessions/session_*.json
        sess_path = find_session_file(dir_basename)
        if sess_path:
            with open(sess_path, encoding="utf-8") as f:
                sess = json.load(f)
            before = (sess.get("highest_risk_level"), sess.get("risk_percentages"))
            update_summary(sess, result)
            if args.dry_run:
                print(f"DRY session  {os.path.basename(sess_path)}: {before} -> {result['highest_risk_level']} {result['risk_percentages']} issue={result['most_frequent_issue']}")
            else:
                with open(sess_path, "w", encoding="utf-8") as f:
                    json.dump(sess, f, indent=2)
                updated_sessions += 1

    # Report session files that had no matching recording timeline.
    session_files = set(glob.glob(os.path.join(SESSIONS_DIR, "session_*.json")))
    matched = set()
    for tl in timelines:
        matched.add(find_session_file(os.path.basename(os.path.dirname(tl))))
    for sf in sorted(session_files):
        if sf not in matched:
            no_timeline_sessions += 1
            print(f"NO-TIMELINE (left as-is) {os.path.basename(sf)}")

    print(f"\nDone ({'DRY RUN' if args.dry_run else 'written'}):")
    print(f"  recordings summaries updated: {updated_recordings}")
    print(f"  sessions summaries updated:   {updated_sessions}")
    print(f"  empty timelines skipped:      {skipped_empty}")
    print(f"  session files w/o timeline:   {no_timeline_sessions}")


if __name__ == "__main__":
    main()
