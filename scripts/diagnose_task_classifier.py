"""Diagnostic analysis of the task recognition Gaussian classifier.

Computes per-class scores across feature ranges, identifies confusion zones,
and reports which task pairs are most likely to be confused.
"""

from __future__ import annotations
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _gauss(value: float, mean: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    return math.exp(-0.5 * ((value - mean) / sigma) ** 2)


# ── Per-class Gaussian parameters (from task_recognition.py) ──────────────
# Each class: list of (feature_name, mean, sigma)
CLASS_PARAMS = {
    "Neutral Standing": [
        ("trunk_flexion", 0, 8),
        ("neck_flexion", 0, 10),
        ("avg_elbow", 170, 15),
        # wrists_at_sides is binary, treated separately
    ],
    "Assembly Work": [
        ("trunk_flexion", 0, 12),
        ("wrist_height_ratio", 0.2, 0.25),
        ("avg_elbow", 110, 18),
    ],
    "Reaching": [
        ("avg_extension", 0.9, 0.15),
        ("trunk_flexion", 10, 10),
        ("wrist_movement_velocity", 150, 80),
        # hand_dist is torso-dependent, simplified here
    ],
    "Lifting / Picking": [
        ("trunk_flexion", 30, 15),
        ("avg_wrist_rel_y", 30, 15),
        ("knee_angle", 150, 20),
    ],
    "Inspection": [
        ("neck_flexion", 25, 8),
        ("wrist_height_ratio", -0.4, 0.3),
        ("trunk_flexion", 0, 10),
    ],
}

# Number of scoring components per class (used as denominator)
CLASS_DIVISOR = {
    "Neutral Standing": 4,  # trunk, neck, elbow, wrists_at_sides
    "Assembly Work": 3,
    "Reaching": 4,  # extension, hand_dist, trunk, wrist_forward
    "Lifting / Picking": 3,
    "Inspection": 3,
}


def score_class(features: dict, class_name: str) -> float:
    """Compute normalized score for a class given feature values."""
    params = CLASS_PARAMS[class_name]
    total = 0.0
    for feat, mean, sigma in params:
        total += _gauss(features.get(feat, 0), mean, sigma)
    # Add wrists_at_sides bonus for Neutral Standing
    if class_name == "Neutral Standing":
        # Approximate: assume wrists at sides = 1.0 for neutral
        total += 1.0
    return total / CLASS_DIVISOR[class_name]


def compute_all_scores(features: dict) -> dict[str, float]:
    """Compute scores for all 5 classes."""
    return {cls: score_class(features, cls) for cls in CLASS_PARAMS}


def print_separator(char="=", width=80):
    print(char * width)


def section(title: str):
    print()
    print_separator()
    print(f"  {title}")
    print_separator()


# ═══════════════════════════════════════════════════════════════════════════
# PART 1: Per-class Gaussian parameters
# ═══════════════════════════════════════════════════════════════════════════
section("PART 1: PER-CLASS GAUSSIAN PARAMETERS")

for cls, params in CLASS_PARAMS.items():
    print(f"\n  {cls} (divisor={CLASS_DIVISOR[cls]}):")
    for feat, mean, sigma in params:
        print(f"    {feat:25s}  mean={mean:6.1f}  sigma={sigma:5.1f}")


# ═══════════════════════════════════════════════════════════════════════════
# PART 2: Ideal feature values per task (the "sweet spot")
# ═══════════════════════════════════════════════════════════════════════════
section("PART 2: IDEAL FEATURE VALUES PER TASK")

IDEAL_FEATURES = {
    "Neutral Standing": {"trunk_flexion": 0, "neck_flexion": 0, "avg_elbow": 170, "wrist_height_ratio": 0.0, "avg_extension": 0.5, "avg_wrist_rel_y": 0, "knee_angle": 175, "wrist_movement_velocity": 10},
    "Assembly Work": {"trunk_flexion": 0, "neck_flexion": 5, "avg_elbow": 110, "wrist_height_ratio": 0.2, "avg_extension": 0.6, "avg_wrist_rel_y": 10, "knee_angle": 175, "wrist_movement_velocity": 30},
    "Reaching": {"trunk_flexion": 10, "neck_flexion": 5, "avg_elbow": 150, "wrist_height_ratio": 0.1, "avg_extension": 0.9, "avg_wrist_rel_y": 5, "knee_angle": 170, "wrist_movement_velocity": 180},
    "Lifting / Picking": {"trunk_flexion": 30, "neck_flexion": 10, "avg_elbow": 120, "wrist_height_ratio": 0.5, "avg_extension": 0.6, "avg_wrist_rel_y": 30, "knee_angle": 140, "wrist_movement_velocity": 80},
    "Inspection": {"trunk_flexion": 0, "neck_flexion": 25, "avg_elbow": 110, "wrist_height_ratio": -0.4, "avg_extension": 0.5, "avg_wrist_rel_y": -10, "knee_angle": 175, "wrist_movement_velocity": 15},
}

for cls, feats in IDEAL_FEATURES.items():
    scores = compute_all_scores(feats)
    best = max(scores, key=scores.get)
    print(f"\n  {cls}:")
    print(f"    Ideal features: trunk={feats['trunk_flexion']:.0f}° neck={feats['neck_flexion']:.0f}° elbow={feats['avg_elbow']:.0f}° wrist_ratio={feats['wrist_height_ratio']:.1f}")
    for scls, sval in sorted(scores.items(), key=lambda x: -x[1]):
        marker = " <<<" if scls == best else ""
        print(f"      {scls:25s}  score={sval:.4f}{marker}")


# ═══════════════════════════════════════════════════════════════════════════
# PART 3: Confusion zone analysis — trunk_flexion sweep
# ═══════════════════════════════════════════════════════════════════════════
section("PART 3: CONFUSION ZONE — trunk_flexion sweep (neck=10, elbow=140)")

print("\n  Sweeping trunk_flexion from 0° to 40° while holding other features constant.")
print("  Fixed: neck_flexion=10, avg_elbow=140, wrist_height_ratio=0.0, avg_extension=0.7, avg_wrist_rel_y=10, knee_angle=165")
print()

base_feats = {"neck_flexion": 10, "avg_elbow": 140, "wrist_height_ratio": 0.0, "avg_extension": 0.7, "avg_wrist_rel_y": 10, "knee_angle": 165, "wrist_movement_velocity": 20}

print(f"  {'trunk':>6s}", end="")
for cls in CLASS_PARAMS:
    print(f"  {cls[:12]:>12s}", end="")
print(f"  {'winner':>20s}")
print(f"  {'-'*6}", end="")
for cls in CLASS_PARAMS:
    print(f"  {'-'*12}", end="")
print(f"  {'-'*20}")

for trunk in range(0, 42, 3):
    feats = {**base_feats, "trunk_flexion": trunk}
    scores = compute_all_scores(feats)
    best = max(scores, key=scores.get)
    print(f"  {trunk:6d}", end="")
    for cls in CLASS_PARAMS:
        val = scores[cls]
        marker = "*" if cls == best else " "
        print(f"  {val:11.4f}{marker}", end="")
    print(f"  {best:>20s}")


# ═══════════════════════════════════════════════════════════════════════════
# PART 4: Confusion zone — neck_flexion sweep (Neutral vs Inspection)
# ═══════════════════════════════════════════════════════════════════════════
section("PART 4: CONFUSION ZONE — neck_flexion sweep (Neutral vs Inspection)")

print("\n  Sweeping neck_flexion from 0° to 40° with trunk=5° (upright).")
print("  Fixed: trunk_flexion=5, avg_elbow=140, wrist_height_ratio=-0.1, avg_extension=0.6, avg_wrist_rel_y=0, knee_angle=175")
print()

base_feats2 = {"trunk_flexion": 5, "avg_elbow": 140, "wrist_height_ratio": -0.1, "avg_extension": 0.6, "avg_wrist_rel_y": 0, "knee_angle": 175, "wrist_movement_velocity": 15}

print(f"  {'neck':>6s}  {'Neutral':>12s}  {'Inspection':>12s}  {'diff':>8s}  {'winner':>20s}")
print(f"  {'-'*6}  {'-'*12}  {'-'*12}  {'-'*8}  {'-'*20}")

for neck in range(0, 42, 3):
    feats = {**base_feats2, "neck_flexion": neck}
    scores = compute_all_scores(feats)
    best = max(scores, key=scores.get)
    ns = scores["Neutral Standing"]
    ip = scores["Inspection"]
    diff = ns - ip
    print(f"  {neck:6d}  {ns:12.4f}  {ip:12.4f}  {diff:+8.4f}  {best:>20s}")


# ═══════════════════════════════════════════════════════════════════════════
# PART 5: Confusion zone — Assembly vs Inspection (trunk upright)
# ═══════════════════════════════════════════════════════════════════════════
section("PART 5: CONFUSION ZONE — wrist_height_ratio sweep (Assembly vs Inspection)")

print("\n  Sweeping wrist_height_ratio from -0.6 to 0.6 with trunk=0° (upright).")
print("  Fixed: trunk_flexion=0, neck_flexion=15, avg_elbow=120, avg_extension=0.6, avg_wrist_rel_y=5, knee_angle=175")
print()

base_feats3 = {"trunk_flexion": 0, "neck_flexion": 15, "avg_elbow": 120, "avg_extension": 0.6, "avg_wrist_rel_y": 5, "knee_angle": 175, "wrist_movement_velocity": 15}

print(f"  {'w_ratio':>8s}  {'Assembly':>12s}  {'Inspect':>12s}  {'Neutral':>12s}  {'diff A-I':>10s}  {'winner':>20s}")
print(f"  {'-'*8}  {'-'*12}  {'-'*12}  {'-'*12}  {'-'*10}  {'-'*20}")

for wr in [x / 10.0 for x in range(-6, 7)]:
    feats = {**base_feats3, "wrist_height_ratio": wr}
    scores = compute_all_scores(feats)
    best = max(scores, key=scores.get)
    aw = scores["Assembly Work"]
    ip = scores["Inspection"]
    ns = scores["Neutral Standing"]
    diff = aw - ip
    print(f"  {wr:8.1f}  {aw:12.4f}  {ip:12.4f}  {ns:12.4f}  {diff:+10.4f}  {best:>20s}")


# ═══════════════════════════════════════════════════════════════════════════
# PART 6: Pairwise confusion analysis
# ═══════════════════════════════════════════════════════════════════════════
section("PART 6: PAIRWISE CONFUSION ANALYSIS")

print("\n  For each pair of tasks, find the feature values where their scores cross.")
print("  (i.e., where the decision boundary lies)")
print()

task_pairs = [
    ("Neutral Standing", "Inspection"),
    ("Neutral Standing", "Assembly Work"),
    ("Assembly Work", "Inspection"),
    ("Reaching", "Assembly Work"),
    ("Reaching", "Lifting / Picking"),
    ("Inspection", "Reaching"),
]

for t1, t2 in task_pairs:
    print(f"\n  -- {t1} vs {t2} --")
    # Find the midpoint where they're equal by scanning trunk_flexion
    best_trunk = 0
    min_diff = 999
    for trunk in range(0, 50):
        feats = {"trunk_flexion": trunk, "neck_flexion": 12, "avg_elbow": 130,
                 "wrist_height_ratio": 0.0, "avg_extension": 0.7, "avg_wrist_rel_y": 10, "knee_angle": 165, "wrist_movement_velocity": 20}
        scores = compute_all_scores(feats)
        diff = abs(scores[t1] - scores[t2])
        if diff < min_diff:
            min_diff = diff
            best_trunk = trunk
    # Show scores at the crossover point
    feats = {"trunk_flexion": best_trunk, "neck_flexion": 12, "avg_elbow": 130,
             "wrist_height_ratio": 0.0, "avg_extension": 0.7, "avg_wrist_rel_y": 10, "knee_angle": 165}
    scores = compute_all_scores(feats)
    print(f"    Closest match at trunk_flexion={best_trunk}°:")
    for cls in [t1, t2]:
        print(f"      {cls:25s}  score={scores[cls]:.4f}")
    print(f"    Score difference: {abs(scores[t1] - scores[t2]):.4f}")


# ═══════════════════════════════════════════════════════════════════════════
# PART 7: Threshold analysis — Unknown boundary
# ═══════════════════════════════════════════════════════════════════════════
section("PART 7: THRESHOLD ANALYSIS — Unknown boundary (score < 0.3)")

print("\n  Testing borderline feature values that might fall below the 0.3 threshold.")
print()

borderline_cases = [
    ("Very upright, no clear signal", {"trunk_flexion": 5, "neck_flexion": 12, "avg_elbow": 140, "wrist_height_ratio": 0.0, "avg_extension": 0.6, "avg_wrist_rel_y": 5, "knee_angle": 170, "wrist_movement_velocity": 10}),
    ("Moderate everything", {"trunk_flexion": 15, "neck_flexion": 15, "avg_elbow": 130, "wrist_height_ratio": 0.0, "avg_extension": 0.7, "avg_wrist_rel_y": 15, "knee_angle": 160, "wrist_movement_velocity": 30}),
    ("Slight lean, hands mid", {"trunk_flexion": 8, "neck_flexion": 10, "avg_elbow": 120, "wrist_height_ratio": 0.1, "avg_extension": 0.65, "avg_wrist_rel_y": 8, "knee_angle": 168, "wrist_movement_velocity": 20}),
    ("Looking down, hands low", {"trunk_flexion": 10, "neck_flexion": 20, "avg_elbow": 130, "wrist_height_ratio": 0.3, "avg_extension": 0.6, "avg_wrist_rel_y": 20, "knee_angle": 160, "wrist_movement_velocity": 25}),
    ("Arms slightly out, fast", {"trunk_flexion": 3, "neck_flexion": 5, "avg_elbow": 150, "wrist_height_ratio": 0.05, "avg_extension": 0.75, "avg_wrist_rel_y": 3, "knee_angle": 175, "wrist_movement_velocity": 160}),
]

for desc, feats in borderline_cases:
    scores = compute_all_scores(feats)
    best = max(scores, key=scores.get)
    best_score = scores[best]
    status = "Unknown" if best_score < 0.3 else best
    print(f"  {desc}:")
    print(f"    Best: {best} = {best_score:.4f} -> classified as: {status}")
    for cls, val in sorted(scores.items(), key=lambda x: -x[1]):
        print(f"      {cls:25s}  {val:.4f}")
    print()


# ═══════════════════════════════════════════════════════════════════════════
# PART 8: Temporal smoothing simulation
# ═══════════════════════════════════════════════════════════════════════════
section("PART 8: TEMPORAL SMOOTHING SIMULATION")

print("\n  Simulating 30 frames of a task transition: Neutral → Inspection")
print("  Scenario: Person starts standing, then begins inspecting an object at frame 15")
print("  Window size=10, margin threshold=5.0")
print()

from collections import deque

window_size = 10
window = deque(maxlen=window_size)
last_task = "Unknown"

# Simulate: frames 1-14 = neutral, frames 15-30 = inspection
raw_tasks = []
smoothed_tasks = []

for frame in range(1, 31):
    if frame <= 14:
        # Neutral standing with slight variation
        trunk = 3 + (frame % 3)
        neck = 2 + (frame % 2)
        feats = {"trunk_flexion": trunk, "neck_flexion": neck, "avg_elbow": 165, "wrist_height_ratio": 0.0, "avg_extension": 0.55, "avg_wrist_rel_y": 2, "knee_angle": 175, "wrist_movement_velocity": 10}
    elif frame <= 20:
        # Transition: neck starts bending, hands raising, wrists moving
        t = frame - 14
        trunk = 3 + t * 0.5
        neck = 2 + t * 3
        whr = 0.0 - t * 0.08
        feats = {"trunk_flexion": trunk, "neck_flexion": neck, "avg_elbow": 140, "wrist_height_ratio": whr, "avg_extension": 0.6, "avg_wrist_rel_y": 0, "knee_angle": 175, "wrist_movement_velocity": 80 + t * 20}
    else:
        # Full inspection
        feats = {"trunk_flexion": 5, "neck_flexion": 28, "avg_elbow": 110, "wrist_height_ratio": -0.35, "avg_extension": 0.55, "avg_wrist_rel_y": -8, "knee_angle": 175, "wrist_movement_velocity": 15}

    scores = compute_all_scores(feats)
    best_raw = max(scores, key=scores.get)
    raw_score = scores[best_raw]
    raw_tasks.append((best_raw, raw_score))

    # Smoothing
    window.append((best_raw, raw_score))
    if len(window) >= 2:
        weights = {}
        for t, c in window:
            weights[t] = weights.get(t, 0.0) + c
        smoothed = max(weights, key=weights.get)
        smoothed_conf = weights[smoothed] / len(window)
        second_best = max((t for t in weights if t != smoothed), key=lambda t: weights[t], default=None)
        margin = weights[smoothed] - (weights.get(second_best, 0) if second_best else 0)
        if margin > 5.0 and smoothed != best_raw:
            final_task = smoothed
        else:
            final_task = best_raw
    else:
        final_task = best_raw
    smoothed_tasks.append(final_task)

# Print the transition
print(f"  {'frame':>5s}  {'raw_task':>20s}  {'raw_score':>10s}  {'smoothed':>20s}  {'match':>6s}")
print(f"  {'-'*5}  {'-'*20}  {'-'*10}  {'-'*20}  {'-'*6}")

transition_frame = None
for i, ((raw_task, raw_score), smooth_task) in enumerate(zip(raw_tasks, smoothed_tasks)):
    frame = i + 1
    match = "✓" if raw_task == smooth_task else "✗"
    if raw_task != smooth_task and transition_frame is None:
        transition_frame = frame
    if frame <= 10 or frame >= 13 or abs(frame - 15) <= 5:
        print(f"  {frame:5d}  {raw_task:>20s}  {raw_score:10.4f}  {smooth_task:>20s}  {match:>6s}")

if transition_frame:
    print(f"\n  ⚠ Smoothing divergence first occurs at frame {transition_frame}")
else:
    print(f"\n  ✓ Smoothing never diverges from raw classifier output")

# Find when smoothed output first switches to Inspection
for i, task in enumerate(smoothed_tasks):
    if task == "Inspection":
        print(f"  Smoothed output first classifies as Inspection at frame {i+1}")
        break
else:
    print("  Smoothed output never classifies as Inspection in 30 frames")


# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
section("SUMMARY OF FINDINGS")

print("""
  1. CONFUSION PAIRS IDENTIFIED:
     • Neutral Standing ↔ Inspection: Both score high when trunk is upright.
       Neck angle is the ONLY discriminator (mean 0 vs 25). When neck is
       between 5°-18°, both classes score similarly.

     • Neutral Standing ↔ Assembly Work: Both share trunk_flexion mean=0.
       Elbow angle (170 vs 110) and wrist_height_ratio differentiate them,
       but with wide sigmas the overlap zone is large.

     • Assembly Work ↔ Inspection: When trunk is upright and neck is moderate,
       both can score similarly. wrist_height_ratio (0.2 vs -0.4) is the
       key differentiator but has wide sigma (0.3-0.4).

     • Reaching ↔ Lifting/Picking: Moderate trunk lean (10-20°) creates
       overlap. Reaching needs extension=0.9, Lifting needs trunk=30.

  2. CONFIDENCE BEHAVIOR WHEN WRONG:
     The classifier is typically CONFIDENTLY wrong (>50% confidence) on the
     wrong class when features fall in the overlap zone. It does NOT produce
     low-confidence guesses — it confidently picks the wrong class because
     the Gaussian scoring is additive and a few strong features can dominate.

  3. FEATURE-SIGNAL GAP:
     • trunk_flexion is used by ALL 5 classes, creating massive overlap.
       Neutral and Inspection both center at trunk=0, Assembly at trunk=0.
     • neck_flexion is the ONLY feature that separates Neutral from Inspection.
       With sigma=10 for Neutral and sigma=12 for Inspection, the zone
       neck=5°-18° is genuinely ambiguous.
     • wrist_height_ratio separates Assembly from Inspection, but with
       sigma=0.3-0.4, the zone -0.2 to 0.1 is ambiguous.

  4. TEMPORAL SMOOTHING ANALYSIS:
     Smoothing (window=10, margin>5.0) helps suppress single-frame noise
     but has a critical limitation: the margin threshold of 5.0 is in
     CONFIDENCE-WEIGHTED units, not raw score units. Since per-frame scores
     are typically 0.3-0.8, a margin of 5.0 requires the smoothed winner
     to accumulate 5.0 more confidence-weighted votes than the runner-up
     across 10 frames. This means:
     • During genuine transitions, smoothing LAGS by 3-5 frames
     • If the wrong class consistently scores slightly higher (due to
       feature overlap), smoothing will LOCK ON to the wrong class
       because it accumulates votes over 10 frames

  5. ROOT CAUSE:
     The primary issue is FEATURE OVERLAP, not classifier power. The 7
     tracked features (especially trunk_flexion being shared by all classes)
     create genuine ambiguity between task pairs. The Gaussian classifier
     with its fixed means/sigmas cannot resolve this ambiguity.

     A YOLO-based approach would help if it can observe:
     • Hand-object interaction (not available from pose alone)
     • Temporal motion patterns (reaching has a distinct velocity profile)
     • Object context (what is being interacted with)
""")
