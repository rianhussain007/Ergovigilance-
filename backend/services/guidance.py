"""Human-readable posture guidance.

Produces per-area status strings and immediate fix tips from the
features computed by backend/services/features.py (core + Phase-A
head/hand/stance additions).  No ML model, no risk scoring, no engine
logic — pure text generation on top of already-computed feature values.
"""

from __future__ import annotations

from typing import Dict, List, Mapping


def _feature_status(value: float, medium: float, high: float, inverted: bool = False) -> str:
    """Classify a feature value as LOW / MEDIUM / HIGH against thresholds.

    For inverted features (e.g. stance_stability) a LOWER value means
    HIGHER risk.  NaN (unavailable) is treated as LOW so guidance never
    yells at the user over a missing measurement.
    """
    if value != value:  # NaN check
        return "LOW"
    if inverted:
        if value < high:
            return "HIGH"
        if value < medium:
            return "MEDIUM"
        return "LOW"
    if value > high:
        return "HIGH"
    if value > medium:
        return "MEDIUM"
    return "LOW"


def posture_feedback(features: Mapping[str, float]) -> List[Dict[str, str]]:
    """Per-area status + guidance text for 5 ergonomic zones.

    Returns a list of dicts with keys: area, status, text.
    Identical logic and text to frontend/app.py:89-138.
    """
    shoulder_value = max(features.get("left_shoulder_elev", 0.0), features.get("right_shoulder_elev", 0.0))
    items: List[Dict[str, str]] = []

    # Head and neck
    neck_status = _feature_status(features.get("neck_flexion", 0.0), 10, 30)
    if neck_status == "HIGH":
        neck_text = "Your head is too far forward - tuck your chin slightly back"
    elif neck_status == "MEDIUM":
        neck_text = "Your neck is slightly forward - try to bring your ears above your shoulders"
    else:
        neck_text = "Good - your neck position looks natural"
    items.append({"area": "Head and neck", "status": neck_status, "text": neck_text})

    # Back
    trunk_status = _feature_status(features.get("trunk_flexion", 0.0), 20, 60)
    if trunk_status == "HIGH":
        trunk_text = "You are hunching forward significantly - sit up straight and push your lower back into the chair"
    elif trunk_status == "MEDIUM":
        trunk_text = "You are leaning forward slightly - try to straighten your back"
    else:
        trunk_text = "Good - your back posture looks upright"
    items.append({"area": "Back", "status": trunk_status, "text": trunk_text})

    # Shoulders
    shoulder_status = _feature_status(shoulder_value, 30, 60)

    if shoulder_status == "HIGH":
        shoulder_text = "Your shoulders are raised - relax them down away from your ears"
    elif shoulder_status == "MEDIUM":
        shoulder_text = "Your shoulders are slightly tense - try to drop them and relax"
    else:
        shoulder_text = "Good - your shoulders look relaxed"
    items.append({"area": "Shoulders", "status": shoulder_status, "text": shoulder_text})

    # Shoulder balance
    symmetry_status = _feature_status(features.get("shoulder_symmetry", 0.0), 5, 15)
    if symmetry_status == "HIGH":
        symmetry_text = "Your shoulders are uneven - check if you are leaning to one side"
    elif symmetry_status == "MEDIUM":
        symmetry_text = "Slight shoulder tilt detected - try to sit evenly on both sides"
    else:
        symmetry_text = "Good - your shoulders are level"
    items.append({"area": "Shoulder balance", "status": symmetry_status, "text": symmetry_text})

    # Overall alignment
    alignment_status = _feature_status(features.get("alignment_deviation", 0.0), 5, 15)
    if alignment_status == "HIGH":
        alignment_text = "Your head is not aligned with your hips - sit back in your chair and sit tall"
    elif alignment_status == "MEDIUM":
        alignment_text = "Slight forward lean detected - imagine a string pulling the top of your head upward"
    else:
        alignment_text = "Good - your overall alignment looks balanced"
    items.append({"area": "Overall alignment", "status": alignment_status, "text": alignment_text})

    # Forward head posture (Phase-A: screen-work head protrusion)
    fhp_status = _feature_status(features.get("forward_head_posture", 0.0), 10, 20)
    if fhp_status == "HIGH":
        fhp_text = "Your head is jutting forward - tuck your chin and bring your ears over your shoulders"
    elif fhp_status == "MEDIUM":
        fhp_text = "Mild forward head posture - bring your head back over your shoulders"
    else:
        fhp_text = "Good - your head sits naturally over your shoulders"
    items.append({"area": "Forward head posture", "status": fhp_status, "text": fhp_text})

    # Head tilt (monitor-height proxy)
    tilt_status = _feature_status(features.get("head_tilt_angle", 0.0), 10, 20)
    if tilt_status == "HIGH":
        tilt_text = "Your head is tilted strongly - raise the monitor so the top edge is at eye level"
    elif tilt_status == "MEDIUM":
        tilt_text = "Slight head tilt - check your screen height and viewing angle"
    else:
        tilt_text = "Good - your head is level"
    items.append({"area": "Head tilt", "status": tilt_status, "text": tilt_text})

    # Wrist deviation (RULA Table B)
    wrist_status = _feature_status(features.get("wrist_deviation_angle", 0.0), 5, 15)
    if wrist_status == "HIGH":
        wrist_text = "Your wrists are bent sharply - keep hands in line with the forearms and use a wrist rest"
    elif wrist_status == "MEDIUM":
        wrist_text = "Slight wrist bend - keep your wrists straight while typing or handling tools"
    else:
        wrist_text = "Good - your wrists are in a neutral position"
    items.append({"area": "Wrists", "status": wrist_status, "text": wrist_text})

    # Stance stability (inverted: narrow/wide base = risky)
    stance_status = _feature_status(features.get("stance_stability", 1.0), 0.7, 0.5, inverted=True)
    if stance_status == "HIGH":
        stance_text = "Unstable stance - stand with feet about shoulder-width apart"
    elif stance_status == "MEDIUM":
        stance_text = "Narrow stance - widen your base of support for lifting"
    else:
        stance_text = "Good - your stance is stable"
    items.append({"area": "Stance", "status": stance_status, "text": stance_text})

    # Weight shift (balance)
    shift_status = _feature_status(features.get("weight_shift_offset", 0.0), 8, 15)
    if shift_status == "HIGH":
        shift_text = "Your weight is shifted far to one side - center yourself over both feet"
    elif shift_status == "MEDIUM":
        shift_text = "Slight weight shift - balance evenly across both feet"
    else:
        shift_text = "Good - your weight is balanced"
    items.append({"area": "Weight balance", "status": shift_status, "text": shift_text})

    return items


def actionable_recommendations(features: Mapping[str, float]) -> List[str]:
    """Immediate fix tips for flagged areas + 3 generic tips.

    Returns at most 3 items.  Identical logic to frontend/app.py:145-172.
    """
    items = posture_feedback(features)
    flagged = [item for item in items if item["status"] in {"MEDIUM", "HIGH"}]
    recommendations: List[str] = []

    for item in flagged:
        area = item["area"]
        if area == "Head and neck":
            recommendations.append("Bring your ears directly above your shoulders and tuck your chin slightly back.")
        elif area == "Back":
            recommendations.append("Sit tall and gently press your lower back into the chair for support.")
        elif area == "Shoulders":
            recommendations.append("Relax your shoulders down away from your ears and keep your elbows close.")
        elif area == "Shoulder balance":
            recommendations.append("Sit evenly on both sides and avoid leaning onto one arm.")
        elif area == "Overall alignment":
            recommendations.append("Sit back in your chair and imagine a string pulling the top of your head upward.")
        elif area == "Forward head posture":
            recommendations.append("Tuck your chin slightly back and bring your ears above your shoulders.")
        elif area == "Head tilt":
            recommendations.append("Raise your screen so the top edge sits around eye level.")
        elif area == "Wrists":
            recommendations.append("Keep your wrists straight and in line with your forearms while working.")
        elif area == "Stance":
            recommendations.append("Stand with feet about shoulder-width apart for a stable base.")
        elif area == "Weight balance":
            recommendations.append("Shift back to center and balance your weight across both feet.")

    recommendations.extend([
        "Take a short movement break every 30 minutes.",
        "Set your screen so the top edge is around eye level.",
        "Use a small hourly reminder to reset your posture.",
    ])

    deduped: List[str] = []
    for item in recommendations:
        if item not in deduped:
            deduped.append(item)
    return deduped[:3]


def build_guidance(features: Mapping[str, float]) -> Dict[str, object]:
    """Build a complete guidance payload from current features.

    Returns a dict suitable for embedding in an API response:
      - feedback: list of {area, status, text}
      - flagged_areas: list of area names with MEDIUM or HIGH status
      - recommendations: list of up to 3 actionable tip strings
    """
    feedback = posture_feedback(features)
    flagged = [item["area"] for item in feedback if item["status"] in {"MEDIUM", "HIGH"}]
    recs = actionable_recommendations(features)
    return {
        "feedback": feedback,
        "flagged_areas": flagged,
        "recommendations": recs,
    }
