"""Shared utility functions for ErgoVigilance.

Pure functions used across multiple subsystems.
Original modules re-export these for backward compatibility.
"""

from __future__ import annotations

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
