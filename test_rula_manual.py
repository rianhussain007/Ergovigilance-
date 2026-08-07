import numpy as np
from backend.services.features import (
    extract_features_from_keypoints,
    compute_rula_informed_score,
    COCO_17,
)

def make_kps(h, w, **overrides):
    kps = np.zeros((17, 3))
    defaults = {
        0: [w//2, h*0.20, 1],
        1: [w//2-20, h*0.19, 1],
        2: [w//2+20, h*0.19, 1],
        3: [w//2-25, h*0.20, 1],
        4: [w//2+25, h*0.20, 1],
        5: [w//2-80, h*0.30, 1],
        6: [w//2+80, h*0.30, 1],
        7: [w//2-100, h*0.45, 1],
        8: [w//2+100, h*0.45, 1],
        9: [w//2-100, h*0.62, 1],
        10: [w//2+100, h*0.62, 1],
        11: [w//2-60, h*0.55, 1],
        12: [w//2+60, h*0.55, 1],
        13: [w//2-60, h*0.75, 1],
        14: [w//2+60, h*0.75, 1],
        15: [w//2-60, h*0.95, 1],
        16: [w//2+60, h*0.95, 1],
    }
    ov = overrides.get("overrides", {})
    for idx, val in defaults.items():
        kps[idx] = ov.get(idx, val)
    return kps

h, w = 480, 640

print("=" * 60)
print("CASE 1: Neutral standing (erect posture)")
kps = make_kps(h, w)
feat, _unavail = extract_features_from_keypoints(kps, COCO_17)
rula = compute_rula_informed_score(feat)
for k, v in feat.items():
    print(f"  {k}: {v:.1f}")
print(f"  RULA grand score: {rula['rula_informed_score']}/7")
print()

print("=" * 60)
print("CASE 2: Arms raised (elbows up, wrists higher)")
kps = make_kps(h, w, overrides={
    7: [w//2-120, h*0.20, 1],
    8: [w//2+120, h*0.20, 1],
    9: [w//2-100, h*0.15, 1],
    10: [w//2+100, h*0.15, 1],
})
feat, _unavail = extract_features_from_keypoints(kps, COCO_17)
rula = compute_rula_informed_score(feat)
for k, v in feat.items():
    print(f"  {k}: {v:.1f}")
print(f"  RULA grand score: {rula['rula_informed_score']}/7")
print()

print("=" * 60)
print("CASE 3: Forward bend (trunk flexion, neck extended)")
kps = make_kps(h, w, overrides={
    0: [w//2, h*0.40, 1],
    1: [w//2-15, h*0.39, 1],
    2: [w//2+15, h*0.39, 1],
    3: [w//2-20, h*0.40, 1],
    4: [w//2+20, h*0.40, 1],
    5: [w//2-80, h*0.45, 1],
    6: [w//2+80, h*0.45, 1],
    7: [w//2-100, h*0.55, 1],
    8: [w//2+100, h*0.55, 1],
    9: [w//2-100, h*0.70, 1],
    10: [w//2+100, h*0.70, 1],
    11: [w//2-60, h*0.50, 1],
    12: [w//2+60, h*0.50, 1],
})
feat, _unavail = extract_features_from_keypoints(kps, COCO_17)
rula = compute_rula_informed_score(feat)
for k, v in feat.items():
    print(f"  {k}: {v:.1f}")
print(f"  RULA grand score: {rula['rula_informed_score']}/7")
print()

print("=" * 60)
print("MANUAL CROSS-CHECK: Pick CASE 1 (neutral) and trace RULA tables")
print()
print("Step 1: Group A (Upper limb)")
print(f"  Upper arm angle from vertical: {feat['upper_arm_angle_from_vertical']:.1f}")
ua_score = rula['rula_upper_arm']
print(f"  → RULA upper arm score: {ua_score}")
print(f"  Lower arm (elbow flexion): {feat['elbow_flexion_angle']:.1f}")
la_score = rula['rula_lower_arm']
print(f"  → RULA lower arm score: {la_score}")
print(f"  Wrist score (not measured, default): {rula['rula_wrist']}")
print(f"  Wrist twist (not measured, default): {rula['rula_wrist_twist']}")
print(f"  Table A lookup: UA={ua_score}, LA={la_score}, WT=1, W=1")
print(f"  → Table A({ua_score},{la_score},1,1) = {rula['rula_posture_a']}")
print()

print("Step 2: Group B (Neck, trunk, legs)")
print(f"  Neck score: {rula['rula_neck']}")
print(f"  Trunk score: {rula['rula_trunk']}")
print(f"  Legs score: {rula['rula_legs']}")
print(f"  Table B lookup: N={rula['rula_neck']}, T={rula['rula_trunk']}, L={rula['rula_legs']}")
print(f"  → Table B({rula['rula_neck']},{rula['rula_trunk']},{rula['rula_legs']}) = {rula['rula_posture_b']}")
print()

print("Step 3: Table C (grand score)")
print(f"  Score C (from Table A): {rula['rula_score_c']}")
print(f"  Score D (from Table B): {rula['rula_score_d']}")
print(f"  → Table C({rula['rula_score_c']},{rula['rula_score_d']}) = {rula['rula_informed_score']}")
print()

print("=" * 60)
print("PUBLISHED RULA TABLE C (McAtamney & Corlett 1993)")
print()
print("Manually verify:")
print(f"  Table C[{rula['rula_score_c']}-1][{rula['rula_score_d']}-1] = {rula['rula_informed_score']}")
print()

# Now do a REAL manual verification against the published table
from backend.services.features import _TABLE_C
table_c_row = rula['rula_score_c'] - 1
table_c_col = rula['rula_score_d'] - 1
manual_lookup = _TABLE_C[table_c_row][table_c_col]
print(f"  Code lookup: _TABLE_C[{table_c_row}][{table_c_col}] = {manual_lookup}")
print(f"  Match: {manual_lookup == rula['rula_informed_score']}")
print()

# Verify Table A for case 1
from backend.services.features import _TABLE_A
ua = rula['rula_upper_arm']
la = rula['rula_lower_arm']
wt = rula['rula_wrist_twist']
w = rula['rula_wrist']
a_lookup = _TABLE_A.get(ua, {}).get(la, {}).get(wt, [0])[w-1]
print(f"  Table A manual: _TABLE_A[{ua}][{la}][{wt}][{w-1}] = {a_lookup}")
print(f"  Match: {a_lookup == rula['rula_posture_a']}")

# Verify Table B for case 1
from backend.services.features import _TABLE_B
n = rula['rula_neck']
t = rula['rula_trunk']
l = rula['rula_legs']
b_lookup = _TABLE_B.get(n, {}).get(t, {}).get(l, -1)
print(f"  Table B manual: _TABLE_B[{n}][{t}][{l}] = {b_lookup}")
print(f"  Match: {b_lookup == rula['rula_posture_b']}")
