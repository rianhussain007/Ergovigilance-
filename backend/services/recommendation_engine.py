from __future__ import annotations

from typing import Dict, List


_RECOMMENDATIONS: Dict[str, Dict] = {
    "Excessive Neck Flexion": {
        "worker_actions": [
            "Adjust your monitor or task target so the top is at eye level — avoid looking down for extended periods.",
            "Every 15 minutes, perform a chin-tuck: pull your head back so ears align over shoulders, hold 5 seconds.",
            "When reading instructions or part numbers, bring the item up to eye level rather than dropping your head.",
            "During repetitive assembly tasks, alternate between looking at your hands and resetting to a neutral head posture.",
        ],
        "supervisor_actions": [
            "Raise workstation shelves, part bins, or monitors by 15-20 cm so the worker's gaze is within 0-15 degrees below horizontal.",
            "Install adjustable tilt stands or document holders to keep reference materials at eye level.",
            "Add micro-break prompts every 20 minutes — a timer or wearable alert reminding the worker to reset neck posture.",
            "Redesign the work cell layout so that frequently accessed parts are placed at or above elbow height.",
        ],
    },
    "Excessive Trunk Flexion": {
        "worker_actions": [
            "Sit upright with your lower back pressed fully against the chair backrest — engage your core to support the spine.",
            "When leaning forward to reach parts, hinge from the hips (not the waist) and keep your back straight.",
            "Stand up and walk for 30 seconds every 20 minutes to reset trunk posture and reduce spinal disc pressure.",
            "If standing at a conveyor, shift weight between feet and avoid locking knees — use an anti-fatigue mat.",
        ],
        "supervisor_actions": [
            "Bring work surface closer to the worker by repositioning parts bins within 40 cm forward reach from the torso.",
            "Provide height-adjustable workstations so the worker can alternate between sitting and standing throughout the shift.",
            "Install a footrest or lean-support stool for semi-standing tasks to reduce trunk moment on lumbar spine.",
            "Evaluate whether reducing conveyor speed allows the worker to maintain an upright posture while keeping pace.",
        ],
    },
    "Shoulder Imbalance": {
        "worker_actions": [
            "Check if you are habitually leaning onto one elbow or favoring one arm — consciously distribute weight evenly.",
            "Periodically shrug and release both shoulders together to reset symmetry and release tension.",
            "Adjust your chair or stance so your pelvis is level — an uneven seat usually causes shoulder tilt.",
            "During two-handed tasks, apply equal force with both arms and watch the work surface is level.",
        ],
        "supervisor_actions": [
            "Verify the workstation surface is level and the chair is not tilted or sagging on one side.",
            "Provide bilateral tool use by alternating hand-intensive tasks or using jigs that allow both hands equally.",
            "Install a mirror at the workstation so the worker can self-check posture symmetry during operation.",
            "If imbalance persists, arrange a workstation assessment to check for reach-distance asymmetry in the layout.",
        ],
    },
    "Elevated Left Shoulder": {
        "worker_actions": [
            "Consciously drop your left shoulder down and back — imagine pulling your shoulder blade toward your opposite hip.",
            "Check if your left armrest is too high — if so, lower it so your shoulder sits relaxed at neutral height.",
            "Reduce left-hand grip force when possible — use clamp fixtures or tool balancers to offload weight.",
            "Stretch your left upper trap by tilting your head to the right and holding for 20 seconds, 3 times per shift.",
        ],
        "supervisor_actions": [
            "Lower the left-side work surface by 2-5 cm if the worker must elevate the shoulder to reach the task.",
            "Provide a tool balancer or articulating arm for tools used primarily in the left hand to reduce static load.",
            "Rotate the worker to a right-hand-dominant station every 2 hours to balance shoulder loading across the shift.",
            "Evaluate whether left-side parts bins can be lowered or repositioned within the optimal 60-110 cm zone.",
        ],
    },
    "Elevated Right Shoulder": {
        "worker_actions": [
            "Consciously drop your right shoulder down and back — relax the upper trap and let the arm hang naturally.",
            "Check if your right armrest is too high — adjust it so your shoulder sits in a relaxed, neutral position.",
            "Reduce right-hand grip force when possible — use clamps or tool balancers to let the tool's weight assist.",
            "Stretch your right upper trap by tilting your head to the left and holding for 20 seconds, 3 times per shift.",
        ],
        "supervisor_actions": [
            "Lower the right-side work surface by 2-5 cm if the worker must raise the shoulder to reach the task area.",
            "Provide a tool balancer for tools used primarily in the right hand to neutralize tool weight.",
            "Rotate the worker to a left-hand-dominant station every 2 hours to distribute shoulder load evenly.",
            "Check that the right-side parts bin height does not force the worker into continuous shoulder elevation.",
        ],
    },
    "Knee Instability": {
        "worker_actions": [
            "Adjust your chair height so your knees are at a 90-degree angle with feet flat on the floor — do not tuck feet under the chair.",
            "When standing for long periods, keep knees slightly soft (not locked) and shift weight foot-to-foot every few minutes.",
            "Avoid squatting or deep knee bending to reach low parts — use a step stool or ask for a reacher tool.",
            "If kneeling is part of your task, use a gel knee pad and alternate kneeling legs every 10 minutes.",
        ],
        "supervisor_actions": [
            "Provide adjustable-height chairs or sit-stand stools so workers can maintain optimal knee angles regardless of height.",
            "Install anti-fatigue matting at standing stations to reduce cumulative knee joint loading during long shifts.",
            "Eliminate floor-level part storage — raise all frequently accessed items to at least 30 cm above the floor.",
            "For tasks requiring kneeling, provide padded knee-protection mats and schedule rotation every 30 minutes.",
        ],
    },
    "Body Misalignment": {
        "worker_actions": [
            "Sit back fully in your chair and imagine a string pulling the crown of your head upward — stack ears, shoulders, and hips vertically.",
            "Avoid twisting your torso when reaching for parts — turn your whole body by moving your feet instead.",
            "Reset your alignment every 15 minutes by briefly standing tall, taking a deep breath, and re-centering your posture.",
            "When standing at a line, face the task directly rather than twisting to reach — reposition your feet to face the work.",
        ],
        "supervisor_actions": [
            "Reorient the workstation so the primary work zone is directly in front of the worker, not to the side.",
            "Provide a footrest or platform so the worker can shift weight without twisting the pelvis and spine.",
            "Install a full-length mirror so workers can self-check vertical alignment during natural break moments.",
            "Use a laser alignment marker or floor tape to mark the optimal standing position for each station.",
        ],
    },
}


def get_recommendations(issues: list[dict]) -> list[dict]:
    result: list[dict] = []
    for iss in issues:
        name = iss["issue"]
        rec = _RECOMMENDATIONS.get(name, {})
        result.append({
            "issue": name,
            "severity": iss["severity"],
            "worker_actions": rec.get("worker_actions", ["No specific guidance available."]),
            "supervisor_actions": rec.get("supervisor_actions", ["No specific guidance available."]),
        })
    return result


def format_recommendations_text(recs: list[dict], max_issues: int = 2) -> str:
    if not recs:
        return "No recommendations."
    lines: list[str] = []
    for rec in recs[:max_issues]:
        sev = rec["severity"]
        icon = "!" if sev == "HIGH" else "~"
        lines.append(f"[{icon}] {rec['issue']} ({sev})")
        lines.append("  Worker:")
        for a in rec["worker_actions"][:2]:
            lines.append(f"    - {a}")
        lines.append("  Supervisor:")
        for a in rec["supervisor_actions"][:2]:
            lines.append(f"    - {a}")
        lines.append("")
    return "\n".join(lines)
