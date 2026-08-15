"""Regression tests for video-overlay sample retention.

Two QA Phase 1 fixes are covered here:

1. ``_burn_overlay`` (video_analysis.py) used to draw the ML skeleton ONLY on
   every ``frame_step``th sampled frame, so 9 of 10 video frames played raw and
   the overlay visibly blinked. It now holds the last analyzed frame and keeps
   drawing its skeleton until a newer analyzed frame replaces it (sample
   retention).

2. ``scripts/label_frames.py`` prelabels + overlay persistence: the timeline
   auto-generator runs pose extraction sequentially (temporal tracking on),
   records normalized keypoints per frame, and the labeling window holds the
   last valid pose across unsampled frames (nearest-timestamp match).
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))

from app.api.video_analysis import _burn_overlay  # noqa: E402
from app.schemas.api import VideoAnalysisFrame  # noqa: E402

from scripts.label_frames import (  # noqa: E402
    build_overlay_index,
    generate_timeline,
    load_prelabels,
)


def _make_synthetic_video(path: Path, frames: int = 12, w: int = 320,
                          h: int = 240, fps: float = 25.0) -> None:
    """Write a flat-colored video so per-frame pixel diffs are measurable."""
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for i in range(frames):
        writer.write(np.full((h, w, 3), 20 + i * 3, dtype=np.uint8))
    writer.release()


def _humanoid_keypoints(scale: float = 1.0) -> list[list[float]]:
    """A realistic 33-landmark stick figure spread across the frame.

    Real skeletons span the whole frame, so drawing them produces a large,
    measurable pixel change. (A degenerate skeleton with all joints at the
    center draws a tiny blob whose impact is below codec noise.)
    """
    pts = [
        (0.50, 0.12), (0.46, 0.15), (0.44, 0.18), (0.45, 0.24), (0.48, 0.30),  # nose, eyes, ears
        (0.55, 0.16), (0.57, 0.19), (0.56, 0.25), (0.53, 0.31),
        (0.43, 0.21), (0.58, 0.22),  # mouth
        (0.38, 0.32), (0.62, 0.32),  # shoulders
        (0.32, 0.45), (0.68, 0.45),  # elbows
        (0.28, 0.58), (0.72, 0.58),  # wrists
        (0.30, 0.62), (0.70, 0.62), (0.32, 0.66), (0.68, 0.66), (0.30, 0.70), (0.70, 0.70),  # hands
        (0.40, 0.62), (0.60, 0.62),  # hips
        (0.42, 0.80), (0.58, 0.80),  # knees
        (0.43, 0.95), (0.57, 0.95),  # ankles
        (0.44, 0.97), (0.56, 0.97), (0.43, 0.99), (0.57, 0.99),  # heels/feet
    ]
    return [[x * scale, y * scale, 0.0, 0.9] for x, y in pts]


def _fake_analyzed_frames(indices: list[int]) -> list[VideoAnalysisFrame]:
    """One VideoAnalysisFrame per sampled index with a fixed valid skeleton."""
    kps = _humanoid_keypoints()
    frames = []
    for i, idx in enumerate(indices):
        frames.append(
            VideoAnalysisFrame(
                frame_index=idx,
                timestamp_seconds=round(idx / 25.0, 3),
                risk_level="HIGH" if i % 2 == 0 else "LOW",
                confidence=0.9,
                features={"neck_flexion": 45.0},
                feature_scores={},
                unavailable_features=[],
                lower_body_confidence=0.5,
                keypoints=kps,
                region_risks={},
            )
        )
    return frames


class BurnOverlayRetentionTest(unittest.TestCase):
    """Fix 1: the burned overlay video must keep the skeleton on unsampled frames.

    Note: mp4v is a lossy codec, so comparing against the raw input is noisy
    (~5 mean pixel diff on flat frames with no overlay at all). The reliable
    signal is to burn the SAME video twice — once with analyzed frames, once
    with none — and diff the two outputs: identical codec noise cancels, and
    any remaining difference is purely the overlay.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.src = Path(self._tmp.name) / "src.mp4"
        _make_synthetic_video(self.src)

    def tearDown(self):
        self._tmp.cleanup()

    def _burn(self, indices: list[int], name: str) -> Path:
        out = Path(self._tmp.name) / name
        ok = _burn_overlay(str(self.src), _fake_analyzed_frames(indices), 10, str(out))
        self.assertTrue(ok)
        return out

    def _mean_diffs(self, video: Path) -> list[float]:
        cap = cv2.VideoCapture(str(video))
        diffs = []
        for i in range(12):
            ret, frame = cap.read()
            self.assertTrue(ret)
            base = np.full((240, 320, 3), 20 + i * 3, dtype=np.uint8)
            diffs.append(float(np.abs(frame.astype(int) - base.astype(int)).mean()))
        cap.release()
        return diffs

    def _frame_diff_map(self, video_a: Path, video_b: Path) -> list[float]:
        """Per-frame mean abs diff between two burned videos (caps released)."""
        cap_a = cv2.VideoCapture(str(video_a))
        cap_b = cv2.VideoCapture(str(video_b))
        diffs = []
        try:
            for _ in range(12):
                ret_a, fa = cap_a.read()
                ret_b, fb = cap_b.read()
                self.assertTrue(ret_a and ret_b)
                diffs.append(float(np.abs(fa.astype(int) - fb.astype(int)).mean()))
        finally:
            cap_a.release()
            cap_b.release()
        return diffs

    def test_overlay_held_between_samples(self):
        """Every frame (sampled AND between samples) differs from a no-overlay burn."""
        with_overlay = self._burn([0, 10], "with.mp4")
        without_overlay = self._burn([], "without.mp4")
        diffs = self._frame_diff_map(with_overlay, without_overlay)
        for i, d in enumerate(diffs):
            # Frames 1..9 and 11 are NOT sampled. Old code: identical to the
            # no-overlay burn (d ~ 0). With retention: overlay still present.
            self.assertGreater(d, 1.0,
                               f"frame {i} lost the held overlay (diff vs no-overlay={d:.2f})")

    def test_overlay_updates_when_new_sample_arrives(self):
        """A newer analyzed frame replaces the held skeleton (risk level flips)."""
        # Sample 0 = HIGH, sample 10 = LOW; a second burn where sample 10 is
        # also HIGH differs after the sample (different RISK badge text).
        with_overlay = self._burn([0, 10], "with.mp4")
        frames_high = _fake_analyzed_frames([0, 10])
        for fr in frames_high:
            fr.risk_level = "HIGH"
        out_high = Path(self._tmp.name) / "high.mp4"
        ok = _burn_overlay(str(self.src), frames_high, 10, str(out_high))
        self.assertTrue(ok)

        diffs = self._frame_diff_map(with_overlay, out_high)
        # Frames 10-11 should reflect the flipped risk badge (LOW vs HIGH text).
        self.assertGreater(diffs[10], 1.0, f"sample replacement not visible: {diffs}")
        self.assertGreater(diffs[11], 1.0, f"held overlay not refreshed: {diffs}")

    def test_no_analyzed_frames_still_copies_through(self):
        """With zero analyzed frames the video passes through untouched (no crash)."""
        out = self._burn([], "copy.mp4")
        diffs = self._mean_diffs(out)
        # Only codec noise (~5 mean), never an overlay: identical to the raw
        # frames within a generous bound (overlay would add far more).
        self.assertTrue(all(d < 12.0 for d in diffs), f"diffs: {diffs}")


class TimelineOverlayIndexTest(unittest.TestCase):
    """Fix 2: prelabel seeding + overlay index from a generated timeline."""

    def test_build_overlay_index_sorts_and_keeps_keypoints(self):
        timeline = {
            "records": [
                {"timestamp": 1.0, "risk_level": "LOW", "keypoints": [[0.1, 0.2, 0, 0.9]]},
                {"timestamp": 0.0, "risk_level": "HIGH", "keypoints": [[0.5, 0.5, 0, 0.9]]},
                {"timestamp": 2.0, "risk_level": "MEDIUM"},  # no keypoints -> skipped for overlay
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            tl_path = Path(tmp) / "timeline.json"
            tl_path.write_text(json.dumps(timeline["records"]), encoding="utf-8")
            pairs = build_overlay_index(tl_path)
        self.assertEqual([t for t, _ in pairs], [0.0, 1.0, 2.0])
        self.assertTrue(any(rec.get("keypoints") for _, rec in pairs))

    def test_load_prelabels_seeds_risk_and_task(self):
        timeline = [
            {"timestamp": 0.0, "risk_level": "MEDIUM", "current_task": "Assembly Work"},
            {"timestamp": 0.4, "risk_level": "HIGH", "current_task": "Reaching"},
            {"timestamp": 0.8, "risk_level": "LOW", "current_task": "Neutral Standing"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tl_path = Path(tmp) / "timeline.json"
            tl_path.write_text(json.dumps(timeline), encoding="utf-8")
            risk = load_prelabels(tl_path, total=30, fps=25.0, step=10, kind="risk")
            task = load_prelabels(tl_path, total=30, fps=25.0, step=10, kind="task")
        # Frame 0 -> t=0.0 (MEDIUM), frame 10 -> t=0.4 (HIGH), frame 20 -> t=0.8 (LOW)
        self.assertEqual(risk, {0: "MEDIUM", 10: "HIGH", 20: "LOW"})
        self.assertEqual(task, {0: "Assembly Work", 10: "Reaching", 20: "Neutral Standing"})


if __name__ == "__main__":
    unittest.main()
