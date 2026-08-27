"""Web-based frame labeling tool for human validation.

Opens a local web UI showing extracted frames from real factory footage.
A human labeler reviews each frame and assigns:
  - Task category (Assembly Work, Seated Work, Neutral Standing, etc.)
  - Risk level (LOW / MEDIUM / HIGH)
  - Quality flag (clear / partial / occluded)

Produces a CSV file that can be used to train/evaluate models against
genuine human ground truth, not auto-generated labels.

Usage:
    python scripts/label_tool.py --data outputs/real_data --port 8899
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import base64
import io
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]

TASK_CATEGORIES = [
    "Neutral Standing",
    "Seated Work",
    "Assembly Work",
    "Inspection",
    "Reaching",
    "Lifting / Picking",
    "Walking / Moving",
    "Unknown",
]

RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"]


def load_frames(data_dir: Path) -> list[dict[str, Any]]:
    """Load frames from the real_data directory."""
    frames = []

    # Try real_features.csv first (has task labels)
    csv_path = data_dir / "real_features.csv"
    if csv_path.exists():
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                frame_path = data_dir / "frames" / row.get("frame", "")
                if frame_path.exists():
                    frames.append({
                        "path": str(frame_path),
                        "video": row.get("video", ""),
                        "frame_name": row.get("frame", ""),
                        "auto_task": row.get("task_label", "Unknown"),
                        "auto_risk": row.get("risk_level", "LOW"),
                        "confidence": float(row.get("confidence", 0)),
                        "human_task": "",
                        "human_risk": "",
                        "quality": "",
                        "notes": "",
                    })

    # Fallback: scan frames directory
    if not frames:
        frames_dir = data_dir / "frames"
        if frames_dir.exists():
            for img in sorted(frames_dir.glob("*.jpg")):
                frames.append({
                    "path": str(img),
                    "video": "",
                    "frame_name": img.name,
                    "auto_task": "Unknown",
                    "auto_risk": "LOW",
                    "confidence": 0,
                    "human_task": "",
                    "human_risk": "",
                    "quality": "",
                    "notes": "",
                })

    return frames


def save_labels(frames: list[dict], output_path: Path) -> None:
    """Save labeled frames to CSV."""
    fieldnames = [
        "path", "video", "frame_name",
        "auto_task", "auto_risk", "confidence",
        "human_task", "human_risk", "quality", "notes",
    ]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(frames)
    print(f"Saved {len(frames)} labels to {output_path}")


def load_existing_labels(output_path: Path) -> dict[str, dict]:
    """Load previously saved labels to resume where we left off."""
    labels = {}
    if output_path.exists():
        with open(output_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("human_task"):
                    labels[row["frame_name"]] = row
    return labels


class LabelHandler(SimpleHTTPRequestHandler):
    """HTTP handler for the labeling tool."""

    frames: list[dict] = []
    labels_path: Path = Path(".")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._serve_index()
        elif parsed.path == "/api/frames":
            self._serve_frames()
        elif parsed.path == "/api/stats":
            self._serve_stats()
        elif parsed.path.startswith("/frame/"):
            self._serve_frame(parsed.path)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/label":
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length)
            data = json.loads(body)

            # Update frame label
            frame_name = data.get("frame_name")
            for frame in self.frames:
                if frame["frame_name"] == frame_name:
                    frame["human_task"] = data.get("human_task", "")
                    frame["human_risk"] = data.get("human_risk", "")
                    frame["quality"] = data.get("quality", "")
                    frame["notes"] = data.get("notes", "")
                    break

            # Save after each label
            save_labels(self.frames, self.labels_path)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
        else:
            self.send_error(404)

    def _serve_index(self) -> None:
        html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ErgoVigilance — Frame Labeling Tool</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; }
.header { background: #1e293b; padding: 16px 24px; border-bottom: 1px solid #334155; display: flex; align-items: center; gap: 16px; }
.header h1 { font-size: 18px; color: #38bdf8; }
.stats { font-size: 13px; color: #94a3b8; margin-left: auto; }
.main { display: flex; height: calc(100vh - 60px); }
.frame-panel { flex: 1; padding: 24px; display: flex; flex-direction: column; align-items: center; gap: 16px; overflow-y: auto; }
.frame-panel img { max-width: 100%; max-height: 60vh; border-radius: 8px; border: 2px solid #334155; }
.frame-info { background: #1e293b; border-radius: 8px; padding: 12px 16px; font-size: 13px; width: 100%; max-width: 640px; }
.frame-info span { color: #38bdf8; }
.label-panel { width: 380px; background: #1e293b; border-left: 1px solid #334155; padding: 24px; overflow-y: auto; }
.label-panel h2 { font-size: 16px; margin-bottom: 16px; color: #38bdf8; }
.field { margin-bottom: 16px; }
.field label { display: block; font-size: 13px; color: #94a3b8; margin-bottom: 6px; }
.field select, .field input, .field textarea { width: 100%; padding: 8px 12px; border-radius: 6px; border: 1px solid #475569; background: #0f172a; color: #e2e8f0; font-size: 14px; }
.field textarea { height: 60px; resize: vertical; }
.btn-group { display: flex; gap: 8px; margin-top: 20px; }
.btn { flex: 1; padding: 12px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-save { background: #22c55e; color: #fff; }
.btn-save:hover { background: #16a34a; }
.btn-next { background: #3b82f6; color: #fff; }
.btn-next:hover { background: #2563eb; }
.btn-skip { background: #475569; color: #94a3b8; }
.btn-skip:hover { background: #64748b; }
.task-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.task-btn { padding: 10px 8px; border: 2px solid #475569; border-radius: 8px; background: transparent; color: #e2e8f0; font-size: 12px; cursor: pointer; text-align: center; }
.task-btn:hover { border-color: #38bdf8; }
.task-btn.selected { border-color: #22c55e; background: rgba(34,197,94,0.15); color: #22c55e; }
.risk-btn { padding: 10px; border: 2px solid #475569; border-radius: 8px; background: transparent; color: #e2e8f0; font-size: 13px; cursor: pointer; flex: 1; text-align: center; }
.risk-btn:hover { border-color: #38bdf8; }
.risk-btn.selected.low { border-color: #22c55e; background: rgba(34,197,94,0.15); color: #22c55e; }
.risk-btn.selected.medium { border-color: #eab308; background: rgba(234,179,8,0.15); color: #eab308; }
.risk-btn.selected.high { border-color: #ef4444; background: rgba(239,68,68,0.15); color: #ef4444; }
.progress-bar { height: 4px; background: #334155; border-radius: 2px; margin-bottom: 16px; }
.progress-fill { height: 100%; background: #38bdf8; border-radius: 2px; transition: width 0.3s; }
.auto-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; background: #334155; color: #94a3b8; margin-left: 8px; }
</style>
</head>
<body>
<div class="header">
  <h1>🏷️ ErgoVigilance — Frame Labeling Tool</h1>
  <div class="stats" id="stats">Loading...</div>
</div>
<div class="main">
  <div class="frame-panel">
    <div class="progress-bar"><div class="progress-fill" id="progress"></div></div>
    <img id="frame-img" src="" alt="Frame">
    <div class="frame-info" id="frame-info"></div>
  </div>
  <div class="label-panel">
    <h2>Label This Frame</h2>
    <div class="field">
      <label>Task Category</label>
      <div class="task-grid" id="task-grid"></div>
    </div>
    <div class="field">
      <label>Risk Level</label>
      <div style="display:flex;gap:8px" id="risk-grid"></div>
    </div>
    <div class="field">
      <label>Quality</label>
      <select id="quality">
        <option value="">Select...</option>
        <option value="clear">Clear — full body visible</option>
        <option value="partial">Partial — upper body only</option>
        <option value="occluded">Occluded — blocked by object</option>
        <option value="blurry">Blurry — hard to tell</option>
      </select>
    </div>
    <div class="field">
      <label>Notes (optional)</label>
      <textarea id="notes" placeholder="Any observations about this frame..."></textarea>
    </div>
    <div class="btn-group">
      <button class="btn btn-save" onclick="saveAndNext()">✓ Save & Next</button>
      <button class="btn btn-skip" onclick="skipFrame()">Skip →</button>
    </div>
  </div>
</div>
<script>
let frames = [];
let currentIdx = 0;
let selectedTask = '';
let selectedRisk = '';

async function init() {
  const res = await fetch('/api/frames');
  frames = await res.json();
  
  const statsRes = await fetch('/api/stats');
  const stats = await statsRes.json();
  document.getElementById('stats').textContent = 
    stats.labeled + '/' + stats.total + ' labeled (' + Math.round(stats.labeled/stats.total*100) + '%)';
  
  // Build task buttons
  const taskGrid = document.getElementById('task-grid');
  """ + "".join([
      f'<button class="task-btn" onclick="selectTask(\'{task}\', this)">{task}</button>\n'
      for task in TASK_CATEGORIES
  ]) + """
  
  // Build risk buttons
  const riskGrid = document.getElementById('risk-grid');
  """ + "".join([
      f'<button class="risk-btn" onclick="selectRisk(\'{risk}\', this)">{risk}</button>\n'
      for risk in RISK_LEVELS
  ]) + """
  
  loadFrame(0);
}

function loadFrame(idx) {
  if (idx >= frames.length) { 
    alert('All frames labeled! You can close this window.'); 
    return; 
  }
  currentIdx = idx;
  const frame = frames[idx];
  
  document.getElementById('frame-img').src = '/frame/' + frame.path;
  document.getElementById('frame-info').innerHTML = 
    '<strong>' + frame.frame_name + '</strong>' +
    ' <span class="auto-badge">Auto: ' + frame.auto_task + ' (' + Math.round(frame.confidence) + '%)</span>' +
    '<br>Video: ' + (frame.video || 'N/A') +
    ' | Risk: ' + frame.auto_risk;
  
  // Pre-fill if already labeled
  selectedTask = frame.human_task || '';
  selectedRisk = frame.human_risk || '';
  document.getElementById('quality').value = frame.quality || '';
  document.getElementById('notes').value = frame.notes || '';
  
  // Update button states
  document.querySelectorAll('.task-btn').forEach(b => {
    b.classList.toggle('selected', b.textContent === selectedTask);
  });
  document.querySelectorAll('.risk-btn').forEach(b => {
    b.classList.remove('selected');
    if (b.textContent === selectedRisk) {
      b.classList.add('selected');
      b.classList.add(selectedRisk.toLowerCase());
    }
  });
  
  // Progress
  const labeled = frames.filter(f => f.human_task).length;
  document.getElementById('progress').style.width = (labeled/frames.length*100) + '%';
}

function selectTask(task, btn) {
  selectedTask = task;
  document.querySelectorAll('.task-btn').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
}

function selectRisk(risk, btn) {
  selectedRisk = risk;
  document.querySelectorAll('.risk-btn').forEach(b => { b.classList.remove('selected', 'low', 'medium', 'high'); });
  btn.classList.add('selected', risk.toLowerCase());
}

async function saveAndNext() {
  if (!selectedTask) { alert('Select a task category'); return; }
  if (!selectedRisk) { alert('Select a risk level'); return; }
  
  const frame = frames[currentIdx];
  await fetch('/api/label', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      frame_name: frame.frame_name,
      human_task: selectedTask,
      human_risk: selectedRisk,
      quality: document.getElementById('quality').value,
      notes: document.getElementById('notes').value,
    })
  });
  
  frame.human_task = selectedTask;
  frame.human_risk = selectedRisk;
  
  loadFrame(currentIdx + 1);
}

function skipFrame() {
  loadFrame(currentIdx + 1);
}

// Keyboard shortcuts
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); saveAndNext(); }
  if (e.key === 's' || e.key === 'S') { selectedTask = 'Seated Work'; saveAndNext(); }
  if (e.key === 'n' || e.key === 'N') { selectedTask = 'Neutral Standing'; saveAndNext(); }
  if (e.key === 'a' || e.key === 'A') { selectedTask = 'Assembly Work'; saveAndNext(); }
  if (e.key === 'i' || e.key === 'I') { selectedTask = 'Inspection'; saveAndNext(); }
});

init();
</script>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def _serve_frames(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(self.frames).encode())

    def _serve_stats(self) -> None:
        total = len(self.frames)
        labeled = sum(1 for f in self.frames if f.get("human_task"))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"total": total, "labeled": labeled}).encode())

    def _serve_frame(self, path: str) -> None:
        # path is /frame/outputs/real_data/frames/frame_000030.jpg
        file_path = ROOT / path.replace("/frame/", "")
        if file_path.exists():
            self.send_response(200)
            content_type = "image/jpeg" if file_path.suffix == ".jpg" else "image/png"
            self.send_header("Content-Type", content_type)
            self.end_headers()
            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Suppress default logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Frame labeling tool")
    parser.add_argument("--data", default="outputs/real_data", help="Data directory")
    parser.add_argument("--port", type=int, default=8899, help="Port")
    parser.add_argument("--output", default="outputs/real_data/human_labels.csv", help="Output CSV")
    args = parser.parse_args()

    data_dir = ROOT / args.data
    output_path = ROOT / args.output

    frames = load_frames(data_dir)
    if not frames:
        print(f"No frames found in {data_dir}")
        sys.exit(1)

    # Load existing labels
    existing = load_existing_labels(output_path)
    for frame in frames:
        if frame["frame_name"] in existing:
            lbl = existing[frame["frame_name"]]
            frame["human_task"] = lbl.get("human_task", "")
            frame["human_risk"] = lbl.get("human_risk", "")
            frame["quality"] = lbl.get("quality", "")
            frame["notes"] = lbl.get("notes", "")

    labeled = sum(1 for f in frames if f.get("human_task"))
    print(f"Found {len(frames)} frames ({labeled} already labeled)")
    print(f"Output: {output_path}")
    print(f"Starting labeling server on http://localhost:{args.port}")

    # Set class variables
    LabelHandler.frames = frames
    LabelHandler.labels_path = output_path

    server = HTTPServer(("0.0.0.0", args.port), LabelHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        save_labels(frames, output_path)
        print("\nLabels saved. Goodbye!")


if __name__ == "__main__":
    main()
