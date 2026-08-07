"""Shared utility functions for ErgoVigilance.

Pure functions used across multiple subsystems.
Original modules re-export these for backward compatibility.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def midpoint(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute the midpoint between two 2D points."""
    return (a[:2] + b[:2]) / 2.0


def angle_between(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Compute angle at vertex b between segments ba and bc, in degrees."""
    v1 = a[:2] - b[:2]
    v2 = c[:2] - b[:2]
    denom = np.linalg.norm(v1) * np.linalg.norm(v2)
    if denom < 1e-8:
        return 180.0
    cos_a = np.dot(v1, v2) / denom
    return float(np.degrees(np.arccos(np.clip(cos_a, -1.0, 1.0))))


def dist_2d(a: np.ndarray, b: np.ndarray) -> float:
    """Compute Euclidean distance between two 2D points."""
    return float(np.linalg.norm(a[:2] - b[:2]))


def wrist_movement_velocity_px(
    prev_left: Sequence[float] | None,
    prev_right: Sequence[float] | None,
    curr_left: Sequence[float] | None,
    curr_right: Sequence[float] | None,
    dt: float,
    width: int,
    height: int,
) -> float:
    """Frame-to-frame wrist displacement in pixels per second (px/s).

    MediaPipe keypoints are normalized to [0, 1] per axis (x by image width,
    y by image height), so raw normalized deltas are resolution- and
    axis-dependent. Converting to pixel space yields a stable physical scale
    that the task classifier's Reaching gaussian expects (~150 px/s).

    Returns 0.0 whenever any wrist point is missing (``None``) or ``dt`` is
    not positive, so callers never have to special-case partial detections.

    Points are any indexable sequence of at least two coordinates
    ``[x, y, ...]`` (e.g. ``[x, y, z, visibility]`` keypoint rows).
    """
    if dt <= 0.0 or prev_left is None or prev_right is None or curr_left is None or curr_right is None:
        return 0.0
    d_lx = (curr_left[0] - prev_left[0]) * width
    d_ly = (curr_left[1] - prev_left[1]) * height
    d_rx = (curr_right[0] - prev_right[0]) * width
    d_ry = (curr_right[1] - prev_right[1]) * height
    d_l = (d_lx**2 + d_ly**2) ** 0.5
    d_r = (d_rx**2 + d_ry**2) ** 0.5
    return round(float(max(d_l, d_r) / dt), 2)


_UNICODE_REPLACEMENTS = {
    "\u2014": " - ",
    "\u2013": "-",
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u2022": "*",
    "\u2026": "...",
}


def sanitize_text(text: str) -> str:
    """Replace Unicode characters with ASCII equivalents."""
    for char, replacement in _UNICODE_REPLACEMENTS.items():
        text = text.replace(char, replacement)
    return text
