from __future__ import annotations

import numpy as np


def midpoint(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a[:2] + b[:2]) / 2.0


def angle_between(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    v1 = a[:2] - b[:2]
    v2 = c[:2] - b[:2]
    denom = np.linalg.norm(v1) * np.linalg.norm(v2)
    if denom < 1e-8:
        return 180.0
    cos_a = np.dot(v1, v2) / denom
    return float(np.degrees(np.arccos(np.clip(cos_a, -1.0, 1.0))))


def dist_2d(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a[:2] - b[:2]))
