"""Unit tests for wrist-movement velocity (px/s) used by task recognition.

The helper lives in backend.core.utils so it can be tested without pulling
in cv2/mediapipe. It converts MediaPipe's normalized landmark deltas into
pixel-per-second velocities — the scale the Reaching gaussian expects
(mean ~150 px/s).
"""

import math

from backend.core.utils import wrist_movement_velocity_px


# Mirror of the Reaching velocity gaussian in backend/services/task_recognition.py
def _reaching_velocity_score(px_per_sec: float) -> float:
    return math.exp(-0.5 * ((px_per_sec - 150.0) / 80.0) ** 2)


def test_pixel_space_scale_x_axis():
    # 10 px displacement in x on a 1280-wide frame over 0.1 s -> 100 px/s
    prev = [0.5, 0.5]
    curr = [0.5 + 10 / 1280, 0.5]
    v = wrist_movement_velocity_px(prev, prev, curr, curr, 0.1, 1280, 720)
    assert v == 100.0


def test_y_axis_scaled_by_height():
    # 12 px displacement in y on a 720-tall frame over 0.1 s -> 120 px/s
    prev = [0.5, 0.5]
    curr = [0.5, 0.5 + 12 / 720]
    v = wrist_movement_velocity_px(prev, prev, curr, curr, 0.1, 1280, 720)
    assert v == 120.0


def test_uses_max_of_left_and_right():
    # Left wrist still, right wrist moves 15 px -> velocity reflects the right
    left_prev = [0.5, 0.5]
    left_curr = [0.5, 0.5]
    right_prev = [0.7, 0.5]
    right_curr = [0.7 + 15 / 1280, 0.5]
    v = wrist_movement_velocity_px(left_prev, right_prev, left_curr, right_curr, 0.1, 1280, 720)
    assert v == 150.0


def test_ignores_keypoint_extra_dims():
    # Keypoint rows carry [x, y, z, visibility]; only x/y participate.
    prev = [0.5, 0.5, 0.0, 0.9]
    curr = [0.5 + 20 / 1280, 0.5, 0.0, 0.9]
    v = wrist_movement_velocity_px(prev, prev, curr, curr, 0.2, 1280, 720)
    assert v == 100.0


def test_zero_when_no_previous_frame():
    # First frame after a detection gap has no previous wrists -> 0, no crash
    curr = [0.5, 0.5]
    v = wrist_movement_velocity_px(None, None, curr, curr, 0.033, 1280, 720)
    assert v == 0.0


def test_zero_when_one_prev_wrist_missing():
    # Previous frame had only the left wrist (16 keypoints) -> 0, no crash
    v = wrist_movement_velocity_px(
        [0.5, 0.5], None, [0.51, 0.5], [0.71, 0.5], 0.033, 1280, 720
    )
    assert v == 0.0


def test_zero_when_dt_nonpositive():
    prev = [0.5, 0.5]
    curr = [0.51, 0.5]
    assert wrist_movement_velocity_px(prev, prev, curr, curr, 0.0, 1280, 720) == 0.0
    assert wrist_movement_velocity_px(prev, prev, curr, curr, -1.0, 1280, 720) == 0.0


def test_zero_when_stationary():
    p = [0.5, 0.5]
    assert wrist_movement_velocity_px(p, p, p, p, 0.033, 1280, 720) == 0.0


def test_reaching_gaussian_contract():
    """Lock in the scale contract: a fast reach scores high, idle scores low.

    The whole point of the px/s conversion is that production velocities land
    in the range the Reaching gaussian (mean 150, sigma 80) was tuned for.
    If either side drifts, this test catches it.
    """
    # ~200 px/s wrist movement during a reach -> near-peak velocity term
    fast = 200.0
    assert _reaching_velocity_score(fast) > 0.8
    # A 200 px/s displacement on a 1280-wide frame in 1 s produces ~200 px/s
    p = [0.5, 0.5]
    c = [0.5 + 200 / 1280, 0.5]
    assert wrist_movement_velocity_px(p, p, c, c, 1.0, 1280, 720) == 200.0
    # Idle fidgeting (10 px/s) must NOT satisfy the reaching velocity term
    assert _reaching_velocity_score(10.0) < 0.3
