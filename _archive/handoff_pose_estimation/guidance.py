from __future__ import annotations

from typing import Dict, List, Mapping


def _feature_status(value: float, medium: float, high: float) -> str:
    if value > high:
        return "HIGH"
    if value > medium:
        return "MEDIUM"
    return "LOW"


def posture_feedback(features: Mapping[str, float]) -> List[Dict[str, str]]:
    shoulder_value = max(features.get("left_shoulder_elev", 0), features.get("right_shoulder_elev", 0))
    items: List[Dict[str, str]] = []

    neck_status = _feature_status(features.get("neck_flexion", 0), 10, 30)
    if neck_status == "HIGH":
        neck_text = "Your head is too far forward - tuck your chin slightly back"
    elif neck_status == "MEDIUM":
        neck_text = "Your neck is slightly forward - try to bring your ears above your shoulders"
    else:
        neck_text = "Good - your neck position looks natural"
    items.append({"area": "Head and neck", "status": neck_status, "text": neck_text})

    trunk_status = _feature_status(features.get("trunk_flexion", 0), 20, 60)
    if trunk_status == "HIGH":
        trunk_text = "You are hunching forward significantly - sit up straight and push your lower back into the chair"
    elif trunk_status == "MEDIUM":
        trunk_text = "You are leaning forward slightly - try to straighten your back"
    else:
        trunk_text = "Good - your back posture looks upright"
    items.append({"area": "Back", "status": trunk_status, "text": trunk_text})

    shoulder_status = _feature_status(shoulder_value, 30, 60)
    if shoulder_status == "HIGH":
        shoulder_text = "Your shoulders are raised - relax them down away from your ears"
    elif shoulder_status == "MEDIUM":
        shoulder_text = "Your shoulders are slightly tense - try to drop them and relax"
    else:
        shoulder_text = "Good - your shoulders look relaxed"
    items.append({"area": "Shoulders", "status": shoulder_status, "text": shoulder_text})

    symmetry_status = _feature_status(features.get("shoulder_symmetry", 0), 5, 15)
    if symmetry_status == "HIGH":
        symmetry_text = "Your shoulders are uneven - check if you are leaning to one side"
    elif symmetry_status == "MEDIUM":
        symmetry_text = "Slight shoulder tilt detected - try to sit evenly on both sides"
    else:
        symmetry_text = "Good - your shoulders are level"
    items.append({"area": "Shoulder balance", "status": symmetry_status, "text": symmetry_text})

    alignment_status = _feature_status(features.get("alignment_deviation", 0), 5, 15)
    if alignment_status == "HIGH":
        alignment_text = "Your head is not aligned with your hips - sit back in your chair and sit tall"
    elif alignment_status == "MEDIUM":
        alignment_text = "Slight forward lean detected - imagine a string pulling the top of your head upward"
    else:
        alignment_text = "Good - your overall alignment looks balanced"
    items.append({"area": "Overall alignment", "status": alignment_status, "text": alignment_text})

    return items


def actionable_recommendations(features: Mapping[str, float]) -> List[str]:
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
    feedback = posture_feedback(features)
    flagged = [item["area"] for item in feedback if item["status"] in {"MEDIUM", "HIGH"}]
    recs = actionable_recommendations(features)
    return {
        "feedback": feedback,
        "flagged_areas": flagged,
        "recommendations": recs,
    }
