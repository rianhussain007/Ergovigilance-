from __future__ import annotations

import sys
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.task_recognition import TaskRecognition


def _make_kps(
    nose=(0.5, 0.2, 0.0),
    lsh=(0.4, 0.35, 0.0), rsh=(0.6, 0.35, 0.0),
    lel=(0.35, 0.5, 0.0), rel=(0.65, 0.5, 0.0),
    lwr=(0.3, 0.65, 0.0), rwr=(0.7, 0.65, 0.0),
    lhip=(0.42, 0.65, 0.0), rhip=(0.58, 0.65, 0.0),
    lknee=(0.43, 0.82, 0.0), rknee=(0.57, 0.82, 0.0),
    lankle=(0.44, 0.95, 0.0), rankle=(0.56, 0.95, 0.0),
):
    pts = [[0.0, 0.0, 0.0] for _ in range(33)]
    def _p(v):
        return list(v) + [0.0] * max(0, 3 - len(v))
    pts[0] = _p(nose)
    pts[11] = _p(lsh)
    pts[12] = _p(rsh)
    pts[13] = _p(lel)
    pts[14] = _p(rel)
    pts[15] = _p(lwr)
    pts[16] = _p(rwr)
    pts[23] = _p(lhip)
    pts[24] = _p(rhip)
    pts[25] = _p(lknee)
    pts[26] = _p(rknee)
    pts[27] = _p(lankle)
    pts[28] = _p(rankle)
    return np.array(pts)


def _make_features(
    neck=5.0, trunk=5.0, shoulder_l=10.0, shoulder_r=10.0,
    shoulder_sym=2.0, knee=170.0, alignment=3.0,
):
    return {
        "neck_flexion": neck,
        "trunk_flexion": trunk,
        "left_shoulder_elev": shoulder_l,
        "right_shoulder_elev": shoulder_r,
        "shoulder_symmetry": shoulder_sym,
        "knee_angle": knee,
        "alignment_deviation": alignment,
    }


results: list[str] = []


def check(label, got, expected):
    status = "PASS" if got == expected else "FAIL"
    line = f"  {status}: {label} — got {got!r}, expected {expected!r}"
    print(line)
    results.append(line)
    if status == "FAIL":
        raise SystemExit(1)


def nearly_eq(a, b, tol=5.0):
    return abs(a - b) <= tol


# ---------------------------------------------------------------------------
# 1.  Neutral Standing
# ---------------------------------------------------------------------------
kps = _make_kps()
feats = _make_features(neck=3.0, trunk=4.0, knee=175.0)
t = TaskRecognition()
r = t.detect_task(kps, feats)
check("neutral task", r["task"], "Neutral Standing")
check("neutral confidence > 50", r["confidence"] > 50.0, True)
check("neutral reason not empty", len(r["reason"]) > 0, True)


# ---------------------------------------------------------------------------
# 2.  Assembly Work
# ---------------------------------------------------------------------------
kps = _make_kps(
    lel=(0.38, 0.38), rel=(0.62, 0.38),
    lwr=(0.42, 0.42), rwr=(0.58, 0.42),
)
feats = _make_features(neck=8.0, trunk=8.0)
t = TaskRecognition()
r = t.detect_task(kps, feats)
check("assembly task", r["task"], "Assembly Work")
check("assembly confidence > 50", r["confidence"] > 50.0, True)


# ---------------------------------------------------------------------------
# 3.  Reaching (wrists forward/closer to camera, trunk lean)
# ---------------------------------------------------------------------------
kps = _make_kps(
    nose=(0.5, 0.28, 0.0),
    lsh=(0.42, 0.36, 0.0), rsh=(0.58, 0.36, 0.0),
    lel=(0.44, 0.34, -0.05), rel=(0.56, 0.34, -0.05),
    lwr=(0.46, 0.32, -0.10), rwr=(0.54, 0.32, -0.10),
    lhip=(0.46, 0.62, 0.0), rhip=(0.54, 0.62, 0.0),
)
feats = _make_features(neck=8.0, trunk=15.0)
t = TaskRecognition()
r = t.detect_task(kps, feats)
check("reaching task", r["task"], "Reaching")
check("reaching confidence > 50", r["confidence"] > 50.0, True)


# ---------------------------------------------------------------------------
# 4.  Lifting / Picking (trunk flexed, hands low)
# ---------------------------------------------------------------------------
kps = _make_kps(
    nose=(0.5, 0.5),
    lsh=(0.4, 0.55), rsh=(0.6, 0.55),
    lel=(0.38, 0.72), rel=(0.62, 0.72),
    lwr=(0.36, 0.88), rwr=(0.64, 0.88),
    lhip=(0.44, 0.80), rhip=(0.56, 0.80),
    lknee=(0.43, 0.88), rknee=(0.57, 0.88),
)
feats = _make_features(neck=8.0, trunk=35.0, knee=140.0)
t = TaskRecognition()
r = t.detect_task(kps, feats)
check("lifting task", r["task"], "Lifting / Picking")
check("lifting confidence > 50", r["confidence"] > 50.0, True)


# ---------------------------------------------------------------------------
# 5.  Inspection (neck flexed, hands near face)
# ---------------------------------------------------------------------------
kps = _make_kps(
    nose=(0.5, 0.28),
    lel=(0.38, 0.28), rel=(0.62, 0.28),
    lwr=(0.42, 0.24), rwr=(0.58, 0.24),
)
feats = _make_features(neck=25.0, trunk=5.0)
t = TaskRecognition()
r = t.detect_task(kps, feats)
check("inspection task", r["task"], "Inspection")
check("inspection confidence > 50", r["confidence"] > 50.0, True)


# ---------------------------------------------------------------------------
# 6.  Unknown (no clear pattern - noisy/sparse keypoints)
# ---------------------------------------------------------------------------
kps_bad = np.zeros((33, 2))
feats_bad = _make_features(neck=0.0, trunk=0.0, knee=180.0)
t = TaskRecognition()
r = t.detect_task(kps_bad, feats_bad)
check("unknown task", r["task"], "Unknown")


# ---------------------------------------------------------------------------
# 7.  get_current_task / get_confidence / get_reason accessors
# ---------------------------------------------------------------------------
t = TaskRecognition()
kps_n = _make_kps()
feats_n = _make_features(neck=3.0, trunk=4.0)
t.detect_task(kps_n, feats_n)
check("get_current_task", t.get_current_task(), "Neutral Standing")
check("get_confidence returns float", isinstance(t.get_confidence(), float), True)
check("get_confidence > 0", t.get_confidence() > 0.0, True)
check("get_reason not empty", len(t.get_reason()) > 0, True)


# ---------------------------------------------------------------------------
# 8.  reset() clears state
# ---------------------------------------------------------------------------
t.reset()
check("reset task", t.get_current_task(), "Unknown")
check("reset confidence", t.get_confidence(), 0.0)
check("reset reason", t.get_reason(), "Insufficient data")


# ---------------------------------------------------------------------------
# 9.  Initial state before detect_task
# ---------------------------------------------------------------------------
t2 = TaskRecognition()
check("initial task", t2.get_current_task(), "Unknown")
check("initial confidence", t2.get_confidence(), 0.0)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
all_pass = all("PASS" in r for r in results)
print(f"\n  {'=' * 50}")
if all_pass:
    print(f"  RESULT: ALL TESTS PASSED ({len(results)} checks)")
else:
    print(f"  RESULT: SOME CHECKS FAILED")
print(f"  {'=' * 50}")
