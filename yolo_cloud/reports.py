"""Cloud Core — Report Generation.

Generates daily and weekly risk reports as PDF and CSV exports.
Designed for factory floor managers who need printable/downloadable summaries.
"""

import csv
import io
import logging
from datetime import datetime, timedelta
from typing import Optional

from yolo_cloud.ingestion import get_cloud_service

logger = logging.getLogger(__name__)

# ── Risk color mapping ────────────────────────────────────────────────────────
RISK_COLORS = {
    "LOW": (46, 204, 113),
    "MEDIUM": (241, 196, 15),
    "HIGH": (231, 76, 60),
}


def generate_daily_csv(
    sessions: list[dict],
    report_date: datetime,
    camera_id: Optional[str] = None,
) -> str:
    """Generate a CSV daily report.

    Columns: Time, Camera, Session ID, Duration (s), Frames, Avg Risk Score,
    Highest Risk, Alert Count, Task Breakdown
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Time",
        "Camera",
        "Session ID",
        "Duration (s)",
        "Frames Processed",
        "Avg Risk Score",
        "Highest Risk Level",
        "Alert Count",
        "Person Count",
    ])

    for s in sessions:
        if camera_id and s.get("camera_id") != camera_id:
            continue
        writer.writerow([
            s.get("start_time", ""),
            s.get("camera_name", "Unknown"),
            s.get("session_id", ""),
            s.get("duration_seconds", 0),
            s.get("frame_count", 0),
            s.get("avg_risk_score", 0),
            s.get("highest_risk", "LOW"),
            s.get("alert_count", 0),
            s.get("person_count", 0),
        ])

    return output.getvalue()


def generate_daily_summary(
    sessions: list[dict],
    report_date: datetime,
    camera_id: Optional[str] = None,
) -> dict:
    """Generate a daily summary report as JSON.

    Returns structured data that the frontend can render as a card or PDF.
    """
    day_start = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    day_start_ts = day_start.timestamp()
    day_end_ts = day_end.timestamp()

    # Filter sessions to this day
    day_sessions = []
    for s in sessions:
        try:
            st = datetime.fromisoformat(s.get("start_time", ""))
            if day_start_ts <= st.timestamp() < day_end_ts:
                if camera_id is None or s.get("camera_id") == camera_id:
                    day_sessions.append(s)
        except (ValueError, TypeError):
            pass

    total_frames = sum(s.get("frame_count", 0) for s in day_sessions)
    total_alerts = sum(s.get("alert_count", 0) for s in day_sessions)
    total_duration = sum(s.get("duration_seconds", 0) for s in day_sessions)

    # Risk distribution
    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    all_risk_scores = []
    for s in day_sessions:
        summary = s.get("risk_summary", {})
        for level in ("LOW", "MEDIUM", "HIGH"):
            risk_counts[level] += summary.get(level, 0)
        all_risk_scores.append(s.get("avg_risk_score", 0))

    avg_risk = (
        round(sum(all_risk_scores) / len(all_risk_scores), 1)
        if all_risk_scores
        else 0.0
    )

    # Camera breakdown
    cameras_active = set()
    for s in day_sessions:
        cameras_active.add(s.get("camera_id", "unknown"))

    return {
        "report_type": "daily",
        "date": day_start.strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_sessions": len(day_sessions),
            "total_frames": total_frames,
            "total_alerts": total_alerts,
            "total_duration_hours": round(total_duration / 3600, 2),
            "avg_risk_score": avg_risk,
            "cameras_active": len(cameras_active),
        },
        "risk_distribution": risk_counts,
        "sessions": day_sessions,
    }


def generate_weekly_csv(
    sessions: list[dict],
    week_start: datetime,
    camera_id: Optional[str] = None,
) -> str:
    """Generate a weekly CSV report with daily breakdowns."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Day",
        "Date",
        "Sessions",
        "Total Frames",
        "Total Alerts",
        "Avg Risk Score",
        "Highest Risk",
        "Active Cameras",
    ])

    for day_offset in range(7):
        current_day = week_start + timedelta(days=day_offset)
        day_end = current_day + timedelta(days=1)
        day_ts_start = current_day.timestamp()
        day_ts_end = day_end.timestamp()

        day_sessions = []
        for s in sessions:
            try:
                st = datetime.fromisoformat(s.get("start_time", ""))
                if day_ts_start <= st.timestamp() < day_ts_end:
                    if camera_id is None or s.get("camera_id") == camera_id:
                        day_sessions.append(s)
            except (ValueError, TypeError):
                pass

        day_name = current_day.strftime("%A")
        date_str = current_day.strftime("%Y-%m-%d")
        total_frames = sum(s.get("frame_count", 0) for s in day_sessions)
        total_alerts = sum(s.get("alert_count", 0) for s in day_sessions)
        avg_risk = (
            round(
                sum(s.get("avg_risk_score", 0) for s in day_sessions) / len(day_sessions),
                1,
            )
            if day_sessions
            else 0.0
        )
        highest = "LOW"
        for s in day_sessions:
            hr = s.get("highest_risk", "LOW")
            if hr == "HIGH":
                highest = "HIGH"
                break
            if hr == "MEDIUM":
                highest = "MEDIUM"

        cameras = set(s.get("camera_id", "") for s in day_sessions)

        writer.writerow([
            day_name,
            date_str,
            len(day_sessions),
            total_frames,
            total_alerts,
            avg_risk,
            highest,
            len(cameras),
        ])

    return output.getvalue()


def generate_weekly_summary(
    sessions: list[dict],
    week_start: datetime,
    camera_id: Optional[str] = None,
) -> dict:
    """Generate a weekly summary report as JSON."""
    daily_breakdowns = []

    for day_offset in range(7):
        current_day = week_start + timedelta(days=day_offset)
        day_end = current_day + timedelta(days=1)
        day_ts_start = current_day.timestamp()
        day_ts_end = day_end.timestamp()

        day_sessions = []
        for s in sessions:
            try:
                st = datetime.fromisoformat(s.get("start_time", ""))
                if day_ts_start <= st.timestamp() < day_ts_end:
                    if camera_id is None or s.get("camera_id") == camera_id:
                        day_sessions.append(s)
            except (ValueError, TypeError):
                pass

        total_frames = sum(s.get("frame_count", 0) for s in day_sessions)
        total_alerts = sum(s.get("alert_count", 0) for s in day_sessions)
        daily_breakdowns.append({
            "day": current_day.strftime("%A"),
            "date": current_day.strftime("%Y-%m-%d"),
            "sessions": len(day_sessions),
            "frames": total_frames,
            "alerts": total_alerts,
        })

    # Overall stats
    all_sessions = []
    for d in daily_breakdowns:
        all_sessions.append(d)

    total_sessions = sum(d["sessions"] for d in daily_breakdowns)
    total_frames = sum(d["frames"] for d in daily_breakdowns)
    total_alerts = sum(d["alerts"] for d in daily_breakdowns)

    return {
        "report_type": "weekly",
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_end": (week_start + timedelta(days=6)).strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_sessions": total_sessions,
            "total_frames": total_frames,
            "total_alerts": total_alerts,
        },
        "daily_breakdown": daily_breakdowns,
    }


def generate_pdf_report(
    report_data: dict,
    report_type: str = "daily",
) -> Optional[bytes]:
    """Generate a PDF report.

    Requires reportlab. Falls back to returning None if not installed.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            HRFlowable,
        )
        from reportlab.graphics.shapes import Drawing, Rect, String
        from reportlab.graphics.charts.barcharts import VerticalBarChart

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=18,
            spaceAfter=20,
            textColor=colors.HexColor("#1a1a2e"),
        )
        subtitle_style = ParagraphStyle(
            "CustomSubtitle",
            parent=styles["Heading2"],
            fontSize=14,
            spaceAfter=10,
            textColor=colors.HexColor("#16213e"),
        )

        elements = []

        # Title
        date_str = report_data.get("date", report_data.get("week_start", ""))
        elements.append(Paragraph(
            f"ErgoVigilance {report_type.title()} Report — {date_str}",
            title_style,
        ))
        elements.append(Paragraph(
            f"Generated: {report_data.get('generated_at', '')}",
            styles["Normal"],
        ))
        elements.append(Spacer(1, 20))

        # Summary section
        summary = report_data.get("summary", {})
        elements.append(Paragraph("Summary", subtitle_style))

        summary_data = [
            ["Metric", "Value"],
            ["Total Sessions", str(summary.get("total_sessions", 0))],
            ["Total Frames Analyzed", f"{summary.get('total_frames', 0):,}"],
            ["Total Alerts", str(summary.get("total_alerts", 0))],
            ["Avg Risk Score", f"{summary.get('avg_risk_score', 'N/A')}"],
        ]
        if report_type == "daily":
            summary_data.append([
                "Total Duration",
                f"{summary.get('total_duration_hours', 0)} hours",
            ])
            summary_data.append([
                "Cameras Active",
                str(summary.get("cameras_active", 0)),
            ])

        table = Table(summary_data, colWidths=[2.5 * inch, 2 * inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8f9fa")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 20))

        # Risk Distribution
        risk_dist = report_data.get("risk_distribution")
        if risk_dist:
            elements.append(Paragraph("Risk Distribution", subtitle_style))

            risk_data = [
                ["Level", "Count"],
                ["Low", str(risk_dist.get("LOW", 0))],
                ["Medium", str(risk_dist.get("MEDIUM", 0))],
                ["High", str(risk_dist.get("HIGH", 0))],
            ]
            risk_table = Table(risk_data, colWidths=[2 * inch, 2 * inch])
            risk_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#d5f5e3")),
                ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#fef9e7")),
                ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#fadbd8")),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
            ]))
            elements.append(risk_table)
            elements.append(Spacer(1, 20))

        # Daily breakdown (for weekly reports)
        daily = report_data.get("daily_breakdown")
        if daily:
            elements.append(Paragraph("Daily Breakdown", subtitle_style))
            daily_data = [["Day", "Date", "Sessions", "Frames", "Alerts"]]
            for d in daily:
                daily_data.append([
                    d.get("day", ""),
                    d.get("date", ""),
                    str(d.get("sessions", 0)),
                    str(d.get("frames", 0)),
                    str(d.get("alerts", 0)),
                ])

            daily_table = Table(daily_data, colWidths=[1.2 * inch, 1.2 * inch, 1 * inch, 1 * inch, 1 * inch])
            daily_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
            ]))
            elements.append(daily_table)
            elements.append(Spacer(1, 20))

        # Footer
        elements.append(HRFlowable(width="100%", color=colors.HexColor("#dee2e6")))
        elements.append(Paragraph(
            "ErgoVigilance Cloud Core — Industrial Ergonomic Safety Monitoring",
            styles["Normal"],
        ))

        doc.build(elements)
        return buffer.getvalue()

    except ImportError:
        logger.warning("reportlab not installed — PDF generation unavailable")
        return None
    except Exception as exc:
        logger.error("PDF generation failed: %s", exc)
        return None
