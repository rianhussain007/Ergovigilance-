"""Lightweight Kalman smoothing for the pose landmark stream.

Tier 0 (stability) — removes landmark jitter at the source with a
per-coordinate constant-velocity Kalman filter, so features, risk scores,
and the overlay skeleton all read a cleaner signal. One 1-D
(position, velocity) Kalman per landmark coordinate (33 landmarks x 3 dims).

Design:
  - Updates are gated by landmark visibility: occluded joints freeze their
    last estimate instead of snapping/drifting to a bogus measurement.
  - ``reset()`` must be called when the person is lost, so a re-detection
    initializes fresh instead of interpolating against a stale pose.
  - Pure Python, no numpy in the hot path — cheap enough for per-frame use.
"""

from __future__ import annotations


class _Kalman1D:
    """1-D constant-velocity Kalman filter (state = [position, velocity]).

    Standard predict/update cycle with F = [[1, 1], [0, 1]] (dt = 1 frame),
    H = [1, 0], scalar process noise ``q`` and measurement noise ``r``.
    """

    __slots__ = ("q", "r", "_x", "_v", "_p00", "_p01", "_p10", "_p11", "initialized")

    def __init__(self, process_noise: float, measurement_noise: float) -> None:
        self.q = process_noise
        self.r = measurement_noise
        self.reset()

    def reset(self) -> None:
        self._x = 0.0
        self._v = 0.0
        self._p00 = 1.0
        self._p01 = 0.0
        self._p10 = 0.0
        self._p11 = 1.0
        self.initialized = False

    def update(self, z: float) -> float:
        """Fold measurement ``z`` in and return the smoothed position."""
        if not self.initialized:
            self._x = z
            self._v = 0.0
            self.initialized = True
            return z

        # ── Predict (constant velocity, dt = 1) ──
        x_pred = self._x + self._v
        v_pred = self._v
        # P' = F P F^T + Q  (P symmetric -> p01 == p10)
        p00 = self._p00 + self._p01 + self._p10 + self._p11 + self.q
        p01 = self._p01 + self._p11
        p10 = self._p10 + self._p11
        p11 = self._p11 + self.q

        # ── Update ──
        y = z - x_pred
        s = p00 + self.r
        if s <= 1e-12:
            return x_pred
        k0 = p00 / s
        k1 = p10 / s

        self._x = x_pred + k0 * y
        self._v = v_pred + k1 * y
        self._p00 = p00 - k0 * p00
        self._p01 = p01 - k0 * p01
        self._p10 = p10 - k1 * p00
        self._p11 = p11 - k1 * p01
        return self._x

    def last(self) -> float:
        """Current best estimate without a new measurement."""
        return self._x


DEFAULT_PROCESS_NOISE = 0.05
# Measurement noise in px^2 — MediaPipe landmark jitter is typically a few
# pixels; a larger R means a smoother (and slightly laggier) track.
DEFAULT_MEASUREMENT_NOISE = 4.0
# Landmarks with visibility below this are treated as occluded and frozen.
MIN_VISIBILITY = 0.35


class LandmarkKalmanSmoother:
    """Per-landmark, per-coordinate constant-velocity Kalman smoother."""

    def __init__(
        self,
        num_landmarks: int = 33,
        dims: int = 3,
        process_noise: float | None = None,
        measurement_noise: float | None = None,
    ) -> None:
        if process_noise is None:
            process_noise = DEFAULT_PROCESS_NOISE
        if measurement_noise is None:
            measurement_noise = DEFAULT_MEASUREMENT_NOISE
        self._dims = dims
        self._filters = [
            [_Kalman1D(process_noise, measurement_noise) for _ in range(dims)]
            for _ in range(num_landmarks)
        ]

    def smooth(self, keypoints) -> list[list[float]]:
        """Smooth a batch of keypoints in place (returns a new list).

        ``keypoints`` items are ``[x, y, z, visibility]`` (visibility at index
        3 when present; bare ``[x, y, z]`` triples are treated as visible).
        Out-of-range landmarks and occluded joints pass through with their
        current estimate frozen — shape and visibility are preserved.
        """
        out: list[list[float]] = []
        for i, kp in enumerate(keypoints):
            vis = kp[3] if len(kp) > 3 else 1.0
            if i >= len(self._filters):
                # Out-of-range landmark (no filter allocated) — pass through.
                out.append(list(kp))
                continue
            if vis < MIN_VISIBILITY:
                # Occluded: freeze the last estimate so the overlay doesn't
                # snap to a bogus measurement. Visibility still reflects the
                # real measurement so downstream consumers see the occlusion.
                frozen = [self._filters[i][d].last() for d in range(min(self._dims, len(kp)))]
                frozen.extend(kp[self._dims:])
                out.append(frozen)
                continue
            smoothed: list[float] = []
            for d in range(min(self._dims, len(kp))):
                val = kp[d]
                if val is None or val != val:  # NaN -> hold last estimate
                    smoothed.append(self._filters[i][d].last())
                else:
                    smoothed.append(self._filters[i][d].update(float(val)))
            # Preserve visibility and any extra columns verbatim.
            smoothed.extend(kp[self._dims:])
            out.append(smoothed)
        return out

    def reset(self) -> None:
        for row in self._filters:
            for f in row:
                f.reset()
