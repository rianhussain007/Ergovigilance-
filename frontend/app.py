from __future__ import annotations

import json
import os
import sys
import tempfile
from collections import Counter
from datetime import datetime
from io import BytesIO
from pathlib import Path
from time import sleep

import cv2
import joblib
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# Handle imports - add repo root to path for Streamlit Cloud
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from backend.services.features import FEATURE_COLUMNS
from backend.services.pose import ImageQualityError, NoPersonDetectedError, annotate_pose, detect_pose_from_bgr


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "best_model.pkl"
RESULTS_DIR = ROOT / "results"

RISK_COPY = {
    "LOW": "Posture looks comfortable right now",
    "MEDIUM": "A few posture habits need attention",
    "HIGH": "Your posture needs correction now",
}

RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
RISK_SCORE = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


@st.cache_resource
def load_model():
    loaded = joblib.load(MODEL_PATH)
    bundle = coerce_model_bundle(loaded)
    make_model_compatible(bundle["model"])
    return bundle


def coerce_model_bundle(loaded):
    if isinstance(loaded, dict) and "model" in loaded:
        loaded.setdefault("feature_columns", FEATURE_COLUMNS)
        return loaded
    return {"model": loaded, "feature_columns": FEATURE_COLUMNS, "labels": getattr(loaded, "classes_", None)}


def make_model_compatible(model) -> None:
    try:
        if not hasattr(model, "monotonic_cst"):
            model.monotonic_cst = None
    except Exception:
        pass
    for estimator in np.asarray(getattr(model, "estimators_", [])).ravel():
        try:
            if not hasattr(estimator, "monotonic_cst"):
                estimator.monotonic_cst = None
        except Exception:
            continue


def badge_color(level: str) -> str:
    colors = {"LOW": "#16803c", "MEDIUM": "#d97706", "HIGH": "#dc2626"}
    return colors.get(level, "#4b5563")


def risk_icon(level: str) -> str:
    return {"LOW": "✅", "MEDIUM": "⚠️", "HIGH": "❌"}.get(level, "⚠️")


def feature_status(value: float, medium: float, high: float) -> str:
    if value > high:
        return "HIGH"
    if value > medium:
        return "MEDIUM"
    return "LOW"


def posture_feedback(features: dict[str, float]) -> list[dict[str, str]]:
    shoulder_value = max(features["left_shoulder_elev"], features["right_shoulder_elev"])
    items = []

    neck_status = feature_status(features["neck_flexion"], 10, 30)
    if neck_status == "HIGH":
        neck_text = "Your head is too far forward - tuck your chin slightly back"
    elif neck_status == "MEDIUM":
        neck_text = "Your neck is slightly forward - try to bring your ears above your shoulders"
    else:
        neck_text = "Good - your neck position looks natural"
    items.append({"area": "Head and neck", "status": neck_status, "text": neck_text})

    trunk_status = feature_status(features["trunk_flexion"], 20, 60)
    if trunk_status == "HIGH":
        trunk_text = "You are hunching forward significantly - sit up straight and push your lower back into the chair"
    elif trunk_status == "MEDIUM":
        trunk_text = "You are leaning forward slightly - try to straighten your back"
    else:
        trunk_text = "Good - your back posture looks upright"
    items.append({"area": "Back", "status": trunk_status, "text": trunk_text})

    shoulder_status = feature_status(shoulder_value, 30, 60)
    if shoulder_status == "HIGH":
        shoulder_text = "Your shoulders are raised - relax them down away from your ears"
    elif shoulder_status == "MEDIUM":
        shoulder_text = "Your shoulders are slightly tense - try to drop them and relax"
    else:
        shoulder_text = "Good - your shoulders look relaxed"
    items.append({"area": "Shoulders", "status": shoulder_status, "text": shoulder_text})

    symmetry_status = feature_status(features["shoulder_symmetry"], 5, 15)
    if symmetry_status == "HIGH":
        symmetry_text = "Your shoulders are uneven - check if you are leaning to one side"
    elif symmetry_status == "MEDIUM":
        symmetry_text = "Slight shoulder tilt detected - try to sit evenly on both sides"
    else:
        symmetry_text = "Good - your shoulders are level"
    items.append({"area": "Shoulder balance", "status": symmetry_status, "text": symmetry_text})

    alignment_status = feature_status(features["alignment_deviation"], 5, 15)
    if alignment_status == "HIGH":
        alignment_text = "Your head is not aligned with your hips - sit back in your chair and sit tall"
    elif alignment_status == "MEDIUM":
        alignment_text = "Slight forward lean detected - imagine a string pulling the top of your head upward"
    else:
        alignment_text = "Good - your overall alignment looks balanced"
    items.append({"area": "Overall alignment", "status": alignment_status, "text": alignment_text})

    return items


def assessment_findings(features: dict[str, float]) -> list[str]:
    return [item["text"] for item in posture_feedback(features)]


def actionable_recommendations(features: dict[str, float]) -> list[str]:
    items = posture_feedback(features)
    flagged = [item for item in items if item["status"] in {"MEDIUM", "HIGH"}]
    recommendations = []
    for item in flagged:
        if item["area"] == "Head and neck":
            recommendations.append("Bring your ears directly above your shoulders and tuck your chin slightly back.")
        elif item["area"] == "Back":
            recommendations.append("Sit tall and gently press your lower back into the chair for support.")
        elif item["area"] == "Shoulders":
            recommendations.append("Relax your shoulders down away from your ears and keep your elbows close.")
        elif item["area"] == "Shoulder balance":
            recommendations.append("Sit evenly on both sides and avoid leaning onto one arm.")
        elif item["area"] == "Overall alignment":
            recommendations.append("Sit back in your chair and imagine a string pulling the top of your head upward.")

    recommendations.extend(
        [
            "Take a short movement break every 30 minutes.",
            "Set your screen so the top edge is around eye level.",
            "Use a small hourly reminder to reset your posture.",
        ]
    )
    deduped = []
    for item in recommendations:
        if item not in deduped:
            deduped.append(item)
    return deduped[:3]


def compute_posture_score(features: dict[str, float]) -> float:
    thresholds = {
        "neck_flexion": (10, 30),
        "trunk_flexion": (20, 60),
        "left_shoulder_elev": (30, 60),
        "right_shoulder_elev": (30, 60),
        "shoulder_symmetry": (5, 15),
        "alignment_deviation": (5, 15),
    }
    total_penalty = 0.0
    count = 0
    for feature, (low, high) in thresholds.items():
        value = features.get(feature, 0)
        if value <= low:
            penalty = 0
        elif value <= high:
            ratio = (value - low) / (high - low) if (high - low) > 0 else 0
            penalty = ratio * 50
        else:
            ratio = min((value - high) / high, 1.0) if high > 0 else 1.0
            penalty = 50 + ratio * 50
        total_penalty += penalty
        count += 1
    avg_penalty = total_penalty / count if count > 0 else 0
    return float(max(0, min(100, round(100 - avg_penalty))))


def render_posture_score(score: float) -> None:
    if score >= 80:
        color = "#16803c"
        label = "Good"
    elif score >= 50:
        color = "#d97706"
        label = "Fair"
    else:
        color = "#dc2626"
        label = "Needs Improvement"
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:1rem;margin:0.5rem 0 1rem 0;">
            <div style="
                width:90px;height:90px;border-radius:50%;
                background:conic-gradient({color} {score}%, #e5e7eb {score}%);
                display:flex;align-items:center;justify-content:center;
                font-size:1.1rem;font-weight:800;color:#1f2937;
                box-shadow:0 2px 8px rgba(0,0,0,0.1);
            ">
                <div style="width:76px;height:76px;border-radius:50%;background:white;
                    display:flex;align-items:center;justify-content:center;">
                    {score}
                </div>
            </div>
            <div>
                <div style="font-size:1.3rem;font-weight:700;color:{color};">Posture Score</div>
                <div style="font-size:0.95rem;color:#4b5563;">{label}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def detected_issues(features: dict[str, float]) -> list[dict[str, str]]:
    items = posture_feedback(features)
    return [item for item in items if item["status"] in {"MEDIUM", "HIGH"}]


def render_detected_issues(features: dict[str, float]) -> None:
    issues = detected_issues(features)
    if not issues:
        st.success("No posture issues detected - everything looks good!")
        return
    st.markdown("#### Detected Issues")
    for item in issues:
        icon = "⚠️" if item["status"] == "MEDIUM" else "❌"
        st.markdown(f"{icon} **{item['area']}**: {item['text']}")


def long_term_recommendations(features: dict[str, float]) -> list[str]:
    items = posture_feedback(features)
    flagged_areas = {item["area"] for item in items if item["status"] in {"MEDIUM", "HIGH"}}
    recs = []
    if "Head and neck" in flagged_areas or "Overall alignment" in flagged_areas:
        recs.append("Adjust your monitor height so the top of the screen is at eye level.")
    if "Shoulders" in flagged_areas or "Shoulder balance" in flagged_areas:
        recs.append("Strengthen your upper back with rows and face pulls to help your shoulders sit back.")
    if "Back" in flagged_areas:
        recs.append("Improve chair support so your lower back stays supported while you work.")
    recs.append("Set a posture reminder every hour and rescan after one week.")
    return recs[:3]


def normalized_probabilities(raw_probabilities: np.ndarray) -> np.ndarray:
    probabilities = np.asarray(raw_probabilities, dtype=float)
    probabilities = np.nan_to_num(probabilities, nan=0.0, posinf=0.0, neginf=0.0)
    probabilities = np.clip(probabilities, 0.0, None)
    total = float(probabilities.sum())
    if total > 0:
        probabilities = probabilities / total
    return probabilities


def predict_frame(image_bgr: np.ndarray) -> tuple[str, float, dict[str, float], np.ndarray, list[str]]:
    pose = detect_pose_from_bgr(image_bgr)
    features = pose["features"]
    bundle = load_model()
    model = bundle["model"]
    feature_columns = bundle.get("feature_columns", FEATURE_COLUMNS)
    vector = pd.DataFrame([{name: features[name] for name in feature_columns}], columns=feature_columns)
    probabilities = normalized_probabilities(model.predict_proba(vector)[0])
    class_index = int(np.argmax(probabilities))
    risk_level = str(model.classes_[class_index])
    prob = float(probabilities[class_index])
    confidence = round(prob * 100, 2)
    annotated_bgr = annotate_pose(image_bgr, pose["keypoints"], features, risk_level)
    return risk_level, confidence, features, annotated_bgr, pose.get("unavailable_features", [])


def save_result_image(
    annotated_bgr: np.ndarray,
    source_filename: str,
    risk_level: str,
    confidence: float,
    features: dict[str, float],
    unavailable_features: list[str],
) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now()
    filename = f"result_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.jpg"
    output_path = RESULTS_DIR / filename
    cv2.imwrite(str(output_path), annotated_bgr)
    metadata = {
        "filename": filename,
        "source_filename": source_filename,
        "timestamp": timestamp.isoformat(timespec="seconds"),
        "risk_level": risk_level,
        "confidence": round(float(confidence), 2),
        "features": features,
        "unavailable_features": unavailable_features,
    }
    output_path.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return output_path


def render_badge(risk_level: str, confidence: float | None = None) -> None:
    color = badge_color(risk_level)
    explanation = RISK_COPY.get(risk_level, "")
    confidence_html = ""
    if confidence is not None:
        confidence_html = f"""
        <div style="font-size:0.95rem;color:#4b5563;margin-bottom:1rem;">
        Confidence: {confidence:.2f}%
        </div>
        """
    st.markdown(
        f"""
        <div style="display:inline-block;padding:0.85rem 1.25rem;border-radius:0.5rem;
        background:{color};color:white;font-size:1.65rem;font-weight:800;letter-spacing:0;
        margin:0.35rem 0 0.45rem 0;">
        {risk_icon(risk_level)} {risk_level} RISK
        </div>
        <div style="font-size:1.05rem;font-weight:600;color:#1f2937;margin-bottom:0.2rem;">
        {explanation}
        </div>
        {confidence_html}
        """,
        unsafe_allow_html=True,
    )


def render_feedback(features: dict[str, float]) -> None:
    st.subheader("Posture Feedback")
    for item in posture_feedback(features):
        st.write(f"{risk_icon(item['status'])} **{item['area']}**: {item['text']}")


def render_unavailable_notes(unavailable_features: list[str]) -> None:
    if unavailable_features:
        st.warning("Part of the body was not clearly visible, so this scan may be less reliable.")


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_pdf_report(
    annotated_bgr: np.ndarray,
    source_filename: str,
    risk_level: str,
    confidence: float | None,
    features: dict[str, float],
    unavailable_features: list[str],
    *,
    video_summary: dict[str, float] | None = None,
) -> bytes:
    page = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(page)
    font = ImageFont.load_default()
    title_font = ImageFont.load_default()
    y = 55
    left = 70
    max_width = 1080

    def line(text: str = "", step: int = 30, fill: tuple[int, int, int] = (25, 33, 47)) -> None:
        nonlocal y
        if not text:
            y += step
            return
        for wrapped in wrap_text(draw, text, font, max_width):
            draw.text((left, y), wrapped, fill=fill, font=font)
            y += step

    draw.text((left, y), "ERGONOMIC POSTURE ASSESSMENT REPORT", fill=(17, 24, 39), font=title_font)
    y += 44
    line(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    line(f"Source: {source_filename}")
    line()

    line("YOUR CURRENT POSTURE", 36)
    line(f"Overall Risk: {risk_level}")
    if confidence is not None:
        line(f"Model confidence: {confidence:.2f}%")
    if video_summary:
        line(
            "Video summary: "
            + ", ".join(f"{level} {video_summary.get(level, 0.0):.1f}%" for level in ["LOW", "MEDIUM", "HIGH"])
        )
    line()

    annotated_rgb = Image.fromarray(cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB))
    annotated_rgb.thumbnail((500, 500))
    page.paste(annotated_rgb, (left, y))
    y += annotated_rgb.height + 35

    line("What we found:", 36)
    for finding in assessment_findings(features):
        line(f"- {finding}")

    if unavailable_features:
        line("- Some body areas were not clearly visible, so this assessment may be less reliable.")

    line()
    line("WHAT YOU SHOULD DO", 36)
    line("Immediate fixes (do these now):")
    for index, item in enumerate(actionable_recommendations(features), start=1):
        line(f"{index}. {item}")

    line()
    line("Long term improvements:")
    for index, item in enumerate(long_term_recommendations(features), start=1):
        line(f"{index}. {item}")

    line()
    line("PROGRESS TRACKING", 36)
    line("Come back and scan again after 1 week to see if your posture has improved.")

    output = BytesIO()
    page.save(output, format="PDF", resolution=150.0)
    return output.getvalue()


def image_tab() -> None:
    uploaded = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png", "bmp"])
    if uploaded is None:
        return

    image_rgb = np.array(Image.open(uploaded).convert("RGB"))
    image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)

    try:
        risk_level, confidence, features, annotated_bgr, unavailable_features = predict_frame(image_bgr)
    except (ImageQualityError, NoPersonDetectedError) as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        st.error(str(exc))
        return

    saved_path = save_result_image(
        annotated_bgr,
        uploaded.name,
        risk_level,
        confidence,
        features,
        unavailable_features,
    )
    annotated_rgb = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)

    score = compute_posture_score(features)
    col_left, col_right = st.columns([1, 1])
    with col_left:
        render_badge(risk_level, confidence)
    with col_right:
        render_posture_score(score)

    render_unavailable_notes(unavailable_features)
    st.image(Image.fromarray(annotated_rgb), caption="Annotated posture")
    st.caption(f"Saved result: {saved_path}")
    render_detected_issues(features)
    with st.expander("Detailed Feedback", expanded=False):
        render_feedback(features)
    pdf_bytes = generate_pdf_report(annotated_bgr, uploaded.name, risk_level, confidence, features, unavailable_features)
    st.download_button(
        "Download Assessment Report",
        data=pdf_bytes,
        file_name=f"posture_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf",
        mime="application/pdf",
    )


def live_camera_tab() -> None:
    st.write("Use the local webcam for live posture risk analysis.")
    camera_index = st.number_input("Camera index", min_value=0, max_value=5, value=0, step=1)
    frame_limit = st.slider("Frames to analyze", min_value=30, max_value=600, value=180, step=30)
    run_live = st.button("Start Live Camera")

    frame_placeholder = st.empty()
    status_placeholder = st.empty()
    stats_placeholder = st.empty()
    saved_placeholder = st.empty()

    if not run_live:
        return

    cap = cv2.VideoCapture(int(camera_index))
    if not cap.isOpened():
        st.error("Could not open webcam. Check camera permissions or try camera index 1.")
        return

    latest_annotated = None
    session_records: list[dict] = []
    try:
        for _ in range(frame_limit):
            ok, frame = cap.read()
            if not ok:
                status_placeholder.error("Could not read a webcam frame.")
                break

            try:
                risk_level, confidence, features, annotated_bgr, unavailable_features = predict_frame(frame)
                session_records.append({
                    "risk_level": risk_level,
                    "features": features,
                })
                latest_annotated = (annotated_bgr.copy(), risk_level, confidence, features, unavailable_features)
                color = badge_color(risk_level)
                cv2.rectangle(annotated_bgr, (12, 12), (360, 78), (0, 0, 0), -1)
                cv2.putText(
                    annotated_bgr,
                    risk_level,
                    (24, 58),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.15,
                    tuple(int(color.lstrip("#")[i : i + 2], 16) for i in (4, 2, 0)),
                    3,
                    cv2.LINE_AA,
                )
                feedback_text = posture_feedback(features)[0]["text"]
                status_placeholder.markdown(
                    f"**{risk_icon(risk_level)} {risk_level} RISK** - {RISK_COPY.get(risk_level, '')}  \n"
                    f"{feedback_text}"
                )
                render_unavailable_notes(unavailable_features)
            except Exception:
                annotated_bgr = frame
                cv2.putText(
                    annotated_bgr,
                    "No pose detected",
                    (24, 58),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA,
                )

            analyzed = len(session_records)
            low_pct = sum(1 for r in session_records if r["risk_level"] == "LOW") / max(analyzed, 1) * 100
            med_pct = sum(1 for r in session_records if r["risk_level"] == "MEDIUM") / max(analyzed, 1) * 100
            high_pct = sum(1 for r in session_records if r["risk_level"] == "HIGH") / max(analyzed, 1) * 100
            stats_placeholder.markdown(
                f"""<div style="display:flex;gap:1.5rem;padding:0.5rem 0;font-size:0.9rem;">
                <div>Frames: <strong>{analyzed}/{frame_limit}</strong></div>
                <div style="color:#16803c;">LOW: <strong>{low_pct:.0f}%</strong></div>
                <div style="color:#d97706;">MED: <strong>{med_pct:.0f}%</strong></div>
                <div style="color:#dc2626;">HIGH: <strong>{high_pct:.0f}%</strong></div>
                </div>""",
                unsafe_allow_html=True,
            )

            frame_placeholder.image(cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB), channels="RGB")
            sleep(0.03)
    finally:
        cap.release()

    if latest_annotated is not None and session_records:
        annotated_bgr, risk_level, confidence, features, unavailable_features = latest_annotated
        saved_path = save_result_image(
            annotated_bgr,
            f"webcam_{int(camera_index)}",
            risk_level,
            confidence,
            features,
            unavailable_features,
        )
        saved_placeholder.caption(f"Saved latest live result: {saved_path}")

        # Session summary
        st.subheader("Session Summary")
        analyzed = len(session_records)
        low_count = sum(1 for r in session_records if r["risk_level"] == "LOW")
        med_count = sum(1 for r in session_records if r["risk_level"] == "MEDIUM")
        high_count = sum(1 for r in session_records if r["risk_level"] == "HIGH")
        overall = "LOW"
        if high_count > med_count and high_count > low_count:
            overall = "HIGH"
        elif med_count > low_count:
            overall = "MEDIUM"
        avg_features = {
            k: sum(r["features"][k] for r in session_records) / analyzed
            for k in session_records[0]["features"]
        }
        session_score = compute_posture_score(avg_features)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Frames Analyzed", analyzed)
        col2.metric("Overall Risk", overall)
        col3.metric("Avg Posture Score", f"{session_score}")
        col4.metric("Session Duration", f"{analyzed * 0.03:.1f}s")
        st.markdown("#### Risk Distribution")
        st.bar_chart(pd.DataFrame({
            "Level": ["LOW", "MEDIUM", "HIGH"],
            "Frames": [low_count, med_count, high_count],
        }).set_index("Level"))
        render_detected_issues(avg_features)


def choose_worst_frame(records: list[dict]) -> dict:
    return max(records, key=lambda item: (RISK_ORDER.get(item["risk_level"], 0), item["confidence"]))


def choose_best_frame(records: list[dict]) -> dict:
    return min(records, key=lambda item: (RISK_ORDER.get(item["risk_level"], 0), -item["confidence"]))


def process_video(video_path: str, frame_step: int = 10, progress=None) -> list[dict]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Could not open the uploaded video.")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    records = []
    frame_index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if frame_index % frame_step == 0:
                try:
                    risk_level, confidence, features, annotated_bgr, unavailable_features = predict_frame(frame)
                    timestamp_seconds = frame_index / fps if fps > 0 else float(len(records))
                    records.append(
                        {
                            "frame_index": frame_index,
                            "time_seconds": timestamp_seconds,
                            "risk_level": risk_level,
                            "confidence": confidence,
                            "features": features,
                            "annotated_bgr": annotated_bgr,
                            "unavailable_features": unavailable_features,
                        }
                    )
                except (ImageQualityError, NoPersonDetectedError):
                    pass

            frame_index += 1
            if progress is not None and total_frames > 0:
                progress.progress(min(frame_index / total_frames, 1.0))
    finally:
        cap.release()

    if not records:
        raise NoPersonDetectedError("No clear person was detected in the processed video frames.")
    return records


def video_summary(records: list[dict]) -> dict[str, float]:
    counts = Counter(record["risk_level"] for record in records)
    total = max(len(records), 1)
    return {level: counts.get(level, 0) / total * 100 for level in ["LOW", "MEDIUM", "HIGH"]}


def render_video_results(records: list[dict], source_name: str) -> None:
    summary = video_summary(records)
    worst = choose_worst_frame(records)
    best = choose_best_frame(records)
    overall = worst["risk_level"]

    avg_features = {
        k: sum(r["features"][k] for r in records) / len(records)
        for k in records[0]["features"]
    }
    video_score = compute_posture_score(avg_features)

    col_left, col_right = st.columns([1, 1])
    with col_left:
        render_badge(overall)
    with col_right:
        render_posture_score(video_score)

    st.subheader("Overall Risk Summary")
    cols = st.columns(3)
    for col, level in zip(cols, ["LOW", "MEDIUM", "HIGH"]):
        col.metric(f"{risk_icon(level)} {level}", f"{summary[level]:.1f}%")
    render_detected_issues(avg_features)

    st.subheader("Risk Timeline")
    timeline = pd.DataFrame(
        {
            "Time": [record["time_seconds"] for record in records],
            "Risk": [RISK_SCORE[record["risk_level"]] for record in records],
            "Level": [record["risk_level"] for record in records],
        }
    )
    st.line_chart(timeline.set_index("Time")["Risk"])
    st.dataframe(
        timeline.assign(Time=timeline["Time"].map(lambda value: f"{value:.1f}s"))[["Time", "Level"]],
        use_container_width=True,
    )

    worst_col, best_col = st.columns(2)
    with worst_col:
        st.subheader("Worst Frame")
        st.image(cv2.cvtColor(worst["annotated_bgr"], cv2.COLOR_BGR2RGB), caption=f"{worst['risk_level']} risk")
        render_feedback(worst["features"])
    with best_col:
        st.subheader("Best Frame")
        st.image(cv2.cvtColor(best["annotated_bgr"], cv2.COLOR_BGR2RGB), caption=f"{best['risk_level']} risk")
        render_feedback(best["features"])

    pdf_bytes = generate_pdf_report(
        worst["annotated_bgr"],
        source_name,
        overall,
        worst["confidence"],
        worst["features"],
        worst["unavailable_features"],
        video_summary=summary,
    )
    st.download_button(
        "Download Video Assessment Report",
        data=pdf_bytes,
        file_name=f"video_posture_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf",
        mime="application/pdf",
    )


def video_tab() -> None:
    uploaded = st.file_uploader("Upload a video", type=["mp4", "avi", "mov"])
    if uploaded is None:
        return

    suffix = Path(uploaded.name).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.read())
        temp_path = tmp.name

    try:
        st.video(temp_path)
        if st.button("Analyze Video"):
            progress = st.progress(0.0)
            with st.spinner("Analyzing every 10th frame..."):
                records = process_video(temp_path, frame_step=10, progress=progress)
            progress.progress(1.0)
            st.success(f"Analyzed {len(records)} video frames.")
            render_video_results(records, uploaded.name)
    except Exception as exc:
        st.error(str(exc))
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def history_tab() -> None:
    records = []
    for path in sorted(RESULTS_DIR.glob("result_*.json"), reverse=True):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue

    if not records:
        st.info("No saved results yet.")
        return

    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date"] = df["timestamp"].dt.date

    for r in records:
        r.setdefault("features", {})
    df["score"] = df["features"].apply(
        lambda f: compute_posture_score(f) if isinstance(f, dict) and f else 0
    )

    # Summary cards
    total_scans = len(df)
    latest_risk = df.iloc[0]["risk_level"] if not df.empty else "N/A"
    latest_score = int(df.iloc[0]["score"]) if not df.empty else 0
    unique_days = df["date"].nunique()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Scans", total_scans)
    col2.metric("Latest Risk", latest_risk)
    col3.metric("Latest Score", f"{latest_score}")
    col4.metric("Active Days", unique_days)
    st.divider()

    # Daily trend
    daily = df.groupby("date").agg(avg_score=("score", "mean"), count=("score", "count")).reset_index()
    daily["avg_score"] = daily["avg_score"].round(1)
    daily = daily.sort_values("date")
    st.subheader("Daily Posture Score Trend")
    st.line_chart(daily.set_index("date")["avg_score"])

    # Risk distribution by day
    daily_risk = df.groupby(["date", "risk_level"]).size().reset_index(name="count")
    daily_pivot = daily_risk.pivot_table(index="date", columns="risk_level", values="count", fill_value=0)
    for level in ["LOW", "MEDIUM", "HIGH"]:
        if level not in daily_pivot.columns:
            daily_pivot[level] = 0
    st.subheader("Daily Scan Distribution")
    st.bar_chart(daily_pivot[["LOW", "MEDIUM", "HIGH"]])

    # Recent scans table
    st.subheader("Recent Scans")
    table = df[["timestamp", "risk_level", "score"]].copy()
    table["timestamp"] = table["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
    table.columns = ["Time", "Risk", "Score"]
    st.dataframe(table.head(20), use_container_width=True, hide_index=True)


st.set_page_config(page_title="Posture Risk Analysis", layout="wide")
st.title("Ergonomic Posture Analysis")

image_upload, live_camera, video_analysis, history = st.tabs(
    ["Image Upload", "Live Camera", "Video Analysis", "History"]
)
with image_upload:
    image_tab()
with live_camera:
    live_camera_tab()
with video_analysis:
    video_tab()
with history:
    history_tab()
