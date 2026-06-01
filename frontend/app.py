from __future__ import annotations

import json
import os
import sys
from io import BytesIO
from datetime import datetime
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

from backend.services.features import FEATURE_COLUMNS, FEATURE_THRESHOLDS
from backend.services.pose import ImageQualityError, NoPersonDetectedError, annotate_pose, detect_pose_from_bgr


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "best_model.pkl"
RESULTS_DIR = ROOT / "results"

RISK_COPY = {
    "LOW": "Posture is safe, no action needed",
    "MEDIUM": "Some risk detected, consider adjustments",
    "HIGH": "Immediate correction required",
}


@st.cache_resource
def load_model():
    bundle = joblib.load(MODEL_PATH)
    make_model_compatible(bundle["model"])
    return bundle


def make_model_compatible(model) -> None:
    if not hasattr(model, "monotonic_cst"):
        model.monotonic_cst = None
    for estimator in getattr(model, "estimators_", []):
        if not hasattr(estimator, "monotonic_cst"):
            estimator.monotonic_cst = None


def badge_color(level: str) -> str:
    colors = {"LOW": "#16803c", "MEDIUM": "#d97706", "HIGH": "#dc2626"}
    return colors.get(level, "#4b5563")


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
    vector = [[features[name] for name in FEATURE_COLUMNS]]
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


def render_badge(risk_level: str, confidence: float) -> None:
    color = badge_color(risk_level)
    explanation = RISK_COPY.get(risk_level, "")
    st.markdown(
        f"""
        <div style="display:inline-block;padding:0.85rem 1.25rem;border-radius:0.5rem;
        background:{color};color:white;font-size:1.65rem;font-weight:800;letter-spacing:0;
        margin:0.35rem 0 0.45rem 0;">
        {risk_level} RISK
        </div>
        <div style="font-size:1.05rem;font-weight:600;color:#1f2937;margin-bottom:0.2rem;">
        {explanation}
        </div>
        <div style="font-size:0.95rem;color:#4b5563;margin-bottom:1rem;">
        Confidence: {confidence:.2f}%
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_features(features: dict[str, float]) -> None:
    st.subheader("Feature Values")
    for name in FEATURE_COLUMNS:
        value = features[name]
        display = name.replace("_", " ").title()
        suffix = "%" if name in {"shoulder_symmetry", "alignment_deviation"} else "deg"
        st.write(f"{display}: {value:.2f} {suffix} | {FEATURE_THRESHOLDS[name]}")


def render_unavailable_notes(unavailable_features: list[str]) -> None:
    if unavailable_features:
        readable = ", ".join(name.replace("_", " ").title() for name in unavailable_features)
        st.warning(f"Partial body visible. Analysis ran, but these features may be less reliable: {readable}")


def recommendations_for(features: dict[str, float]) -> list[str]:
    recommendations = []
    if features["neck_flexion"] > 30:
        recommendations.append("Reduce neck bending: raise the monitor and keep the head aligned over the shoulders.")
    if features["trunk_flexion"] > 60:
        recommendations.append("Correct trunk posture: sit back, support the lower back, and avoid leaning forward.")
    if max(features["left_shoulder_elev"], features["right_shoulder_elev"]) > 60:
        recommendations.append("Lower shoulder strain: bring keyboard/mouse closer and keep elbows relaxed.")
    if features["shoulder_symmetry"] > 15:
        recommendations.append("Improve shoulder symmetry: level the chair/desk setup and avoid one-sided reaching.")
    if not recommendations:
        recommendations.append("Maintain current posture and take regular movement breaks.")
    return recommendations


def generate_pdf_report(
    annotated_bgr: np.ndarray,
    source_filename: str,
    risk_level: str,
    confidence: float,
    features: dict[str, float],
    unavailable_features: list[str],
) -> bytes:
    page = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(page)
    font = ImageFont.load_default()
    y = 55

    def line(text: str, step: int = 32) -> None:
        nonlocal y
        draw.text((70, y), text, fill=(25, 33, 47), font=font)
        y += step

    line("Ergonomic Posture Analysis Report", 44)
    line(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    line(f"Filename: {source_filename}")
    line(f"Risk Level: {risk_level}")
    line(f"Confidence: {confidence:.2f}%", 42)

    annotated_rgb = Image.fromarray(cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB))
    annotated_rgb.thumbnail((520, 520))
    page.paste(annotated_rgb, (70, y))
    y += annotated_rgb.height + 36

    line("Feature Values And Thresholds", 38)
    for name in FEATURE_COLUMNS:
        suffix = "%" if name in {"shoulder_symmetry", "alignment_deviation"} else "deg"
        line(f"- {name.replace('_', ' ').title()}: {features[name]:.2f} {suffix} | {FEATURE_THRESHOLDS[name]}")

    if unavailable_features:
        y += 12
        line("Partial Body Note", 38)
        line("Some features may be less reliable: " + ", ".join(unavailable_features))

    y += 12
    line("Recommendations", 38)
    for item in recommendations_for(features):
        line(f"- {item}", 34)

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

    render_badge(risk_level, confidence)
    render_unavailable_notes(unavailable_features)
    st.image(Image.fromarray(annotated_rgb), caption="Annotated posture")
    st.caption(f"Saved result: {saved_path}")
    render_features(features)
    pdf_bytes = generate_pdf_report(annotated_bgr, uploaded.name, risk_level, confidence, features, unavailable_features)
    st.download_button(
        "Download Report",
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
    saved_placeholder = st.empty()

    if not run_live:
        return

    cap = cv2.VideoCapture(int(camera_index))
    if not cap.isOpened():
        st.error("Could not open webcam. Check camera permissions or try camera index 1.")
        return

    latest_annotated = None
    try:
        for _ in range(frame_limit):
            ok, frame = cap.read()
            if not ok:
                status_placeholder.error("Could not read a webcam frame.")
                break

            try:
                risk_level, confidence, features, annotated_bgr, unavailable_features = predict_frame(frame)
                latest_annotated = (annotated_bgr.copy(), risk_level, confidence, features, unavailable_features)
                color = badge_color(risk_level)
                cv2.rectangle(annotated_bgr, (12, 12), (360, 78), (0, 0, 0), -1)
                cv2.putText(
                    annotated_bgr,
                    f"{risk_level} {confidence:.0f}%",
                    (24, 58),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.25,
                    tuple(int(color.lstrip("#")[i : i + 2], 16) for i in (4, 2, 0)),
                    3,
                    cv2.LINE_AA,
                )
                status_placeholder.markdown(
                    f"**{risk_level} RISK** - {RISK_COPY.get(risk_level, '')}  \n"
                    f"Neck: {features['neck_flexion']:.1f} deg | "
                    f"Trunk: {features['trunk_flexion']:.1f} deg | "
                    f"Shoulder: {max(features['left_shoulder_elev'], features['right_shoulder_elev']):.1f} deg"
                )
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

            frame_placeholder.image(cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB), channels="RGB")
            sleep(0.03)
    finally:
        cap.release()

    if latest_annotated is not None:
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
    table = df[["filename", "timestamp", "risk_level", "confidence"]].copy()
    table["confidence"] = table["confidence"].map(
        lambda value: f"{float(value) * 100:.2f}%" if float(value) <= 1 else f"{float(value):.2f}%"
    )
    st.subheader("Saved Results")
    st.dataframe(table, use_container_width=True)

    counts = df.groupby(["timestamp", "risk_level"]).size().reset_index(name="count")
    risk_counts = df["risk_level"].value_counts().reindex(["LOW", "MEDIUM", "HIGH"], fill_value=0)
    st.subheader("Risk Count Summary")
    st.bar_chart(risk_counts)

    st.subheader("Risk Results Over Time")
    counts["timestamp"] = pd.to_datetime(counts["timestamp"])
    pivot = counts.pivot_table(index="timestamp", columns="risk_level", values="count", fill_value=0)
    st.bar_chart(pivot)


st.set_page_config(page_title="Posture Risk Analysis", layout="wide")
st.title("Ergonomic Posture Analysis")

image_upload, live_camera, history = st.tabs(["Image Upload", "Live Camera", "History"])
with image_upload:
    image_tab()
with live_camera:
    live_camera_tab()
with history:
    history_tab()
