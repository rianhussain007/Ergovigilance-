const pptxgen = require("pptxgenjs");
const path = require("path");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
const W = 13.333, H = 7.5;

// ---------- palette ----------
const BG = "0A0F1C";
const CARD = "121A2C";
const CARD2 = "17233A";
const LINE = "26324A";
const TEAL = "2DD4BF";
const TEAL_DK = "0F766E";
const BLUE = "5B8DEF";
const WHITE = "FFFFFF";
const MUTED = "93A0B8";
const MUTED2 = "6B7A96";

const FONT_HEAD = "Cambria";
const FONT_BODY = "Calibri";

function bgSlide(s) {
  s.background = { color: BG };
}

function corner(s, x, y, flipX, flipY) {
  const len = 0.35;
  const dx = flipX ? -1 : 1, dy = flipY ? -1 : 1;
  s.addShape("line", { x, y, w: dx * len, h: 0, line: { color: TEAL, width: 1.5 } });
  s.addShape("line", { x, y, w: 0, h: dy * len, line: { color: TEAL, width: 1.5 } });
}

function kicker(s, text, x, y) {
  s.addText(text.toUpperCase(), {
    x, y, w: 8, h: 0.3, fontFace: FONT_BODY, fontSize: 11, color: TEAL,
    bold: true, charSpacing: 2, align: "left"
  });
}

function pageTitle(s, text, x, y, w, opts) {
  s.addText(text, Object.assign({
    x, y, w, h: 0.9, fontFace: FONT_HEAD, fontSize: 30, bold: true, color: WHITE,
    align: "left", valign: "top"
  }, opts || {}));
}

function footer(s, n) {
  s.addText("ErgoVigilance", { x: 0.5, y: 7.16, w: 3, h: 0.28, fontFace: FONT_BODY, fontSize: 9, color: MUTED2 });
  s.addText("Tech Eximius 2026 · National Hackathon", { x: W/2 - 2.5, y: 7.16, w: 5, h: 0.28, fontFace: FONT_BODY, fontSize: 9, color: MUTED2, align: "center" });
  s.addText(String(n).padStart(2,"0"), { x: W - 1, y: 7.16, w: 0.5, h: 0.28, fontFace: FONT_BODY, fontSize: 9, color: MUTED2, align: "right" });
}

function card(s, x, y, w, h, opts) {
  s.addShape("roundRect", Object.assign({
    x, y, w, h, rectRadius: 0.08, fill: { color: CARD }, line: { color: LINE, width: 1 },
    shadow: { type: "outer", color: "000000", opacity: 0.35, blur: 8, offset: 3, angle: 90 }
  }, opts || {}));
}

function badge(s, x, y, label, size) {
  size = size || 0.42;
  s.addShape("roundRect", { x, y, w: size, h: size, rectRadius: 0.06, fill: { color: TEAL_DK }, line: { color: TEAL, width: 1 } });
  s.addText(label, { x, y, w: size, h: size, align: "center", valign: "middle", fontFace: FONT_BODY, fontSize: 13, bold: true, color: TEAL, margin: 0 });
}

// =========================================================
// SLIDE 1 — TITLE
// =========================================================
{
  const s = pres.addSlide();
  bgSlide(s);

  const px = 10.15, py = 1.55;
  const joints = [
    [0,0],[0,0.55],[-0.5,0.95],[0.5,0.95],[-0.55,1.75],[0.55,1.75],
    [0,0.55],[0,1.55],[-0.4,2.55],[0.4,2.55]
  ];
  const bones = [[0,1],[1,2],[1,3],[2,4],[3,5],[1,6],[6,7],[7,8],[7,9]];
  bones.forEach(([a,b]) => {
    s.addShape("line", {
      x: px + joints[a][0], y: py + joints[a][1],
      w: joints[b][0]-joints[a][0], h: joints[b][1]-joints[a][1],
      line: { color: TEAL, width: 1.5, transparency: 25 }
    });
  });
  joints.forEach(([jx,jy]) => {
    s.addShape("ellipse", { x: px+jx-0.035, y: py+jy-0.035, w: 0.07, h: 0.07, fill: { color: TEAL }, line: { type: "none" } });
  });
  s.addText("<200ms  END-TO-END", { x: px-0.9, y: py+2.7, w: 2.2, h: 0.3, fontFace: FONT_BODY, fontSize: 9, color: MUTED2, align: "center", charSpacing: 1 });

  corner(s, 0.55, 0.55, false, false);
  corner(s, W-0.55, H-0.55, true, true);

  s.addText("TECH EXIMIUS 2026  ·  NATIONAL HACKATHON", {
    x: 0.7, y: 0.9, w: 8, h: 0.35, fontFace: FONT_BODY, fontSize: 12, color: TEAL, bold: true, charSpacing: 2
  });

  s.addText([
    { text: "Ergo", options: { color: WHITE } },
    { text: "Vigilance", options: { color: TEAL } },
  ], { x: 0.65, y: 2.55, w: 9.5, h: 1.5, fontFace: FONT_HEAD, fontSize: 64, bold: true });

  s.addText("AI-powered ergonomic posture monitoring SaaS.\nReal-time workplace safety — without wearables.", {
    x: 0.7, y: 3.95, w: 8, h: 1.0, fontFace: FONT_BODY, fontSize: 18, color: MUTED, lineSpacingMultiple: 1.25
  });

  const chips = ["LIVE", "33-POINT POSE", "CV MONITORING", "SUB-200MS"];
  let cx = 0.7;
  chips.forEach(c => {
    const cw = 0.22 + c.length * 0.11;
    s.addShape("roundRect", { x: cx, y: 5.15, w: cw, h: 0.4, rectRadius: 0.2, fill: { color: CARD2 }, line: { color: TEAL, width: 0.75 } });
    s.addText(c, { x: cx, y: 5.15, w: cw, h: 0.4, align: "center", valign: "middle", fontFace: FONT_BODY, fontSize: 10, bold: true, color: TEAL, margin: 0 });
    cx += cw + 0.18;
  });

  s.addShape("line", { x: 0.7, y: 6.15, w: 6.6, h: 0, line: { color: LINE, width: 1 } });
  s.addText("TEAM · SIMULATION FRONT", { x: 0.7, y: 6.35, w: 4, h: 0.3, fontFace: FONT_BODY, fontSize: 10, color: MUTED2, bold: true, charSpacing: 1.5 });
  s.addText("Rian Hussain   ·   Jatin Kumar   ·   Guru Charan", { x: 0.7, y: 6.65, w: 8, h: 0.4, fontFace: FONT_BODY, fontSize: 15, color: WHITE, bold: true });
}

// =========================================================
// SLIDE 2 — PROBLEM
// =========================================================
{
  const s = pres.addSlide();
  bgSlide(s);
  kicker(s, "01 · The Hidden Cost", 0.7, 0.55);
  pageTitle(s, "Poor posture is silently\ncosting industry billions.", 0.7, 0.9, 7.2, { fontSize: 32, h: 1.5, lineSpacingMultiple: 1.05 });

  s.addText(
    "In manufacturing, warehousing, and office work, repetitive ergonomic stress causes chronic musculoskeletal disorders (MSDs), fatigue, and productivity loss. Organizations lack an objective, continuous way to measure ergonomic risk — existing methods rely on manual observation, self-reporting, or costly wearables that workers avoid.",
    { x: 0.7, y: 2.55, w: 6.9, h: 1.9, fontFace: FONT_BODY, fontSize: 13.5, color: MUTED, lineSpacingMultiple: 1.35 }
  );

  s.addShape("roundRect", { x: 0.7, y: 4.65, w: 6.9, h: 1.55, rectRadius: 0.08, fill: { color: CARD2 }, line: { color: TEAL, width: 1 } });
  s.addText("THE RESULT", { x: 1.0, y: 4.85, w: 3, h: 0.3, fontFace: FONT_BODY, fontSize: 10, bold: true, color: TEAL, charSpacing: 1.5 });
  s.addText("Injuries go undetected until they're serious. Compliance is manual. Safety teams are flying blind.", {
    x: 1.0, y: 5.18, w: 6.3, h: 0.9, fontFace: FONT_BODY, fontSize: 14.5, color: WHITE, bold: true, lineSpacingMultiple: 1.25
  });

  const stats = [
    { big: "76%", label: "of workers globally report MSD-related pain at some point in their working life", src: "Placemark / ILO / OSHA data" },
    { big: "$15K–$80K", label: "average direct + indirect cost per MSD injury claim to the employer", src: "Placemark / NIOSH / EU-OSHA PIT" },
    { big: "3× higher", label: "absence rate in high-risk ergonomic roles vs. baseline; safety teams have no real-time data to act on", src: "Placemark / workplace safety reports" },
  ];
  let sy = 0.9;
  stats.forEach(st => {
    card(s, 8.0, sy, 4.65, 1.85);
    s.addText(st.big, { x: 8.3, y: sy + 0.15, w: 4.1, h: 0.6, fontFace: FONT_HEAD, fontSize: 30, bold: true, color: TEAL });
    s.addText(st.label, { x: 8.3, y: sy + 0.78, w: 4.05, h: 0.85, fontFace: FONT_BODY, fontSize: 10.5, color: MUTED, lineSpacingMultiple: 1.2 });
    sy += 2.05;
  });
  footer(s, 2);
}

// =========================================================
// SLIDE 3 — SOLUTION
// =========================================================
{
  const s = pres.addSlide();
  bgSlide(s);
  kicker(s, "02 · Our Solution", 0.7, 0.55);
  pageTitle(s, "One webcam. Zero hardware.\nContinuous ergonomic safety.", 0.7, 0.9, 11.5, { fontSize: 30, h: 1.5, lineSpacingMultiple: 1.05 });

  card(s, 0.7, 2.65, 3.9, 4.15, { fill: { color: CARD2 } });
  s.addText([{text:"Ergo", options:{color:WHITE}},{text:"Vigilance", options:{color:TEAL}}], { x: 1.0, y: 2.95, w: 3.3, h: 0.45, fontFace: FONT_HEAD, fontSize: 20, bold: true });
  s.addText("v1.0 · AI Posture Monitoring SaaS", { x: 1.0, y: 3.4, w: 3.3, h: 0.3, fontFace: FONT_BODY, fontSize: 10.5, color: MUTED2 });
  s.addShape("roundRect", { x: 1.0, y: 3.78, w: 2.1, h: 0.35, rectRadius: 0.18, fill: { color: "0F2A28" }, line: { color: TEAL, width: 0.75 } });
  s.addText("WEB-ONLY · NO WEARABLES", { x: 1.0, y: 3.78, w: 2.1, h: 0.35, align: "center", valign: "middle", fontFace: FONT_BODY, fontSize: 8, bold: true, color: TEAL, margin: 0 });
  s.addText("A standard webcam + computer-vision pose estimation continuously analyzes posture in real time, detects risky postures (neck/trunk flexion, shoulder elevation, knee strain, asymmetry) and delivers instant alerts, recommendations, and analytics.", {
    x: 1.0, y: 4.35, w: 3.3, h: 1.5, fontFace: FONT_BODY, fontSize: 10.5, color: MUTED, lineSpacingMultiple: 1.3
  });
  s.addShape("line", { x: 1.0, y: 5.95, w: 3.3, h: 0, line: { color: LINE, width: 1 } });
  s.addText("33", { x: 1.0, y: 6.05, w: 1.5, h: 0.45, fontFace: FONT_HEAD, fontSize: 24, bold: true, color: TEAL });
  s.addText("BODY-LANDMARK\nPOINTS / FRAME", { x: 1.0, y: 6.5, w: 1.6, h: 0.4, fontFace: FONT_BODY, fontSize: 7.5, color: MUTED2, bold: true });
  s.addText("24/7", { x: 2.55, y: 6.05, w: 1.5, h: 0.45, fontFace: FONT_HEAD, fontSize: 24, bold: true, color: TEAL });
  s.addText("REAL-TIME\nRISK SCORING", { x: 2.55, y: 6.5, w: 1.6, h: 0.4, fontFace: FONT_BODY, fontSize: 7.5, color: MUTED2, bold: true });

  const diffs = [
    ["A","No wearables required","Camera-only deployment — zero adoption friction, no charging, no forgetting to put it on."],
    ["B","Real-time AI","Frame-by-frame MediaPipe pose + ergonomic risk engine produce risk scores under 200ms."],
    ["C","Context intelligence","Models fatigue, exposure duration and shift-level strain — not just a snapshot."],
    ["D","Rich analytics","Timeline, joint telemetry, shift heatmaps and compliance-ready exports."],
    ["E","Role-based dashboards","Operator · Supervisor · Safety Manager · Admin — each gets a tailored view."],
    ["F","Multi-camera ready","Scale from one workstation to a full facility — same dashboard, aggregated insight."],
  ];
  const gx = 4.9, gy = 2.65, gw = 3.9, gh = 1.28, gap = 0.15;
  diffs.forEach((d, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = gx + col * (gw + gap), y = gy + row * (gh + gap);
    card(s, x, y, gw, gh, { fill: { color: CARD } });
    badge(s, x + 0.2, y + 0.2, d[0], 0.38);
    s.addText(d[1], { x: x + 0.7, y: y + 0.16, w: gw - 0.9, h: 0.32, fontFace: FONT_BODY, fontSize: 12.5, bold: true, color: WHITE });
    s.addText(d[2], { x: x + 0.7, y: y + 0.5, w: gw - 0.9, h: 0.7, fontFace: FONT_BODY, fontSize: 9.5, color: MUTED, lineSpacingMultiple: 1.2 });
  });
  footer(s, 3);
}

// =========================================================
// SLIDE 4 — HOW IT WORKS
// =========================================================
{
  const s = pres.addSlide();
  bgSlide(s);
  kicker(s, "03 · How It Works", 0.7, 0.55);
  pageTitle(s, "From pixel to posture score\nin under 200 ms.", 0.7, 0.9, 10, { fontSize: 30, h: 1.5, lineSpacingMultiple: 1.05 });
  s.addText("Every video frame passes through a six-stage pipeline — capture, pose estimation, ergonomic feature extraction, context intelligence, live risk scoring, and delivery to the web via REST + WebSockets.", {
    x: 0.7, y: 2.15, w: 11.9, h: 0.55, fontFace: FONT_BODY, fontSize: 12, color: MUTED, lineSpacingMultiple: 1.25
  });

  const steps = [
    ["01","Webcam Capture","A standard 720p+ webcam streams live frames from the workstation.","30 FPS · MJPEG"],
    ["02","Pose Detection","MediaPipe Pose extracts 33 body landmarks per frame with sub-pixel accuracy.","MEDIAPIPE · 33 KP"],
    ["03","Risk Engine","Feature engineering computes neck/trunk angle, shoulder elevation, asymmetry.","CUSTOM ML · RBA / RULA"],
    ["04","Context Intel","Models fatigue, exposure duration, and shift-level cumulative strain.","TIME-WEIGHTED"],
    ["05","Live Risk State","Per-frame joint risk vector normalized against severity thresholds.","SAFE · CAUTION · CRITICAL"],
    ["06","Live Dashboard","REST API + WebSockets push risk score, video frame, alerts, analytics.","REST + WS · MJPEG"],
  ];
  const sx = 0.7, sy = 2.95, sw = 1.87, sh = 2.15, gap = 0.16;
  steps.forEach((st, i) => {
    const x = sx + i * (sw + gap);
    card(s, x, sy, sw, sh, { fill: { color: i === 4 ? "10241F" : CARD } });
    if (i === 4) s.addShape("roundRect", { x, y: sy, w: sw, h: sh, rectRadius: 0.08, fill: {type:"none"}, line: { color: TEAL, width: 1.25 } });
    badge(s, x + 0.16, sy + 0.16, st[0], 0.36);
    s.addText(st[1], { x: x + 0.16, y: sy + 0.62, w: sw - 0.32, h: 0.55, fontFace: FONT_BODY, fontSize: 11.5, bold: true, color: WHITE, lineSpacingMultiple: 1.05 });
    s.addText(st[2], { x: x + 0.16, y: sy + 1.15, w: sw - 0.32, h: 0.72, fontFace: FONT_BODY, fontSize: 8, color: MUTED, lineSpacingMultiple: 1.2 });
    s.addText(st[3], { x: x + 0.16, y: sy + sh - 0.34, w: sw - 0.32, h: 0.28, fontFace: FONT_BODY, fontSize: 6.5, bold: true, color: TEAL, charSpacing: 0.5 });
    if (i < steps.length - 1) {
      s.addShape("line", { x: x + sw + 0.02, y: sy + sh/2, w: gap - 0.04, h: 0, line: { color: TEAL, width: 1.5, endArrowType: "triangle" } });
    }
  });

  // outputs bar
  const oy = 5.55;
  s.addShape("roundRect", { x: 0.7, y: oy, w: 12.0, h: 1.35, rectRadius: 0.08, fill: { color: CARD2 }, line: { color: LINE, width: 1 } });
  s.addText("PIPELINE OUTPUTS", { x: 1.0, y: oy + 0.14, w: 3, h: 0.25, fontFace: FONT_BODY, fontSize: 9, bold: true, color: TEAL, charSpacing: 1.5 });
  const outs = [
    ["Instant Alerts", "Operator + supervisor notifications when a severity threshold is crossed."],
    ["Recommendations", "Context-aware posture corrections (\"straighten back\", \"drop shoulder\")."],
    ["Risk Analytics", "Shift-level heatmaps, joint telemetry, compliance audit trail."],
    ["Session Archive", "JSON frame logs for replay, debugging, and model fine-tuning."],
  ];
  const ow = 2.9;
  outs.forEach((o, i) => {
    const x = 1.0 + i * ow;
    s.addText(o[0], { x, y: oy + 0.46, w: ow - 0.2, h: 0.28, fontFace: FONT_BODY, fontSize: 11, bold: true, color: WHITE });
    s.addText(o[1], { x, y: oy + 0.75, w: ow - 0.2, h: 0.5, fontFace: FONT_BODY, fontSize: 8.5, color: MUTED, lineSpacingMultiple: 1.2 });
  });
  footer(s, 4);
}

// =========================================================
// SLIDE 5 — KEY FEATURES
// =========================================================
{
  const s = pres.addSlide();
  bgSlide(s);
  kicker(s, "04 · Key Features", 0.7, 0.55);
  pageTitle(s, "Eight capabilities. One platform.", 0.7, 0.9, 11, { fontSize: 30, h: 0.7 });
  s.addText("From real-time risk scoring to compliance audit trails, every feature ships behind a single role-aware dashboard.", {
    x: 0.7, y: 1.62, w: 11.5, h: 0.4, fontFace: FONT_BODY, fontSize: 12.5, color: MUTED
  });

  const feats = [
    ["01","Live Monitoring Dashboard","Real-time risk gauge, joint telemetry, and live video feed with pose overlay — all on one screen."],
    ["02","Instant Alerts & Recos","Worker + supervisor notifications with contextual posture-fix recommendations."],
    ["03","Session Analytics & Risk History","Risk timeline, joint-angle charts, and shift summaries drill into the data."],
    ["04","Role-Based Dashboards","Operator · Supervisor · Safety Manager · Admin — each sees only what they need."],
    ["05","Reports & Exports","One-click PDF and Excel exports for compliance audits and HR reviews."],
    ["06","Worker Profiles & Health Scores","Per-worker risk envelope and longitudinal musculoskeletal-health scores."],
    ["07","Multi-Camera Monitoring","Aggregate risk across a whole deployment — facility-floor view, all stations live."],
    ["08","Audit Trail","Immutable log of every risk event — ready for OSHA / ISO 45001 audits."],
  ];
  const cols = 4, rows = 2, gw = 2.83, gh = 2.15, gapx = 0.14, gapy = 0.18;
  const startX = 0.7, startY = 2.2;
  feats.forEach((f, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    const x = startX + col * (gw + gapx), y = startY + row * (gh + gapy);
    card(s, x, y, gw, gh);
    badge(s, x + 0.18, y + 0.18, f[0], 0.36);
    s.addText(f[1], { x: x + 0.18, y: y + 0.68, w: gw - 0.36, h: 0.65, fontFace: FONT_BODY, fontSize: 11.5, bold: true, color: WHITE, lineSpacingMultiple: 1.1 });
    s.addText(f[2], { x: x + 0.18, y: y + 1.28, w: gw - 0.36, h: 0.78, fontFace: FONT_BODY, fontSize: 8.5, color: MUTED, lineSpacingMultiple: 1.25 });
  });
  footer(s, 5);
}

// =========================================================
// SLIDE 6 — TECH STACK
// =========================================================
{
  const s = pres.addSlide();
  bgSlide(s);
  kicker(s, "05 · Tech Stack", 0.7, 0.55);
  pageTitle(s, "Production-grade. Hackathon-shipped.", 0.7, 0.9, 11, { fontSize: 30, h: 0.7 });
  s.addText("A modern TypeScript-first frontend, a Python posture-AI service, and a lean persistence layer — boring on purpose, fast where it counts.", {
    x: 0.7, y: 1.62, w: 11.6, h: 0.4, fontFace: FONT_BODY, fontSize: 12.5, color: MUTED
  });

  const layers = [
    ["01","Frontend","Reactive SoaS dashboard",["React","TypeScript","Tailwind CSS","Vite","Recharts"],"Live risk gauge, MJPEG video tile, role-aware route guards, responsive across workstation."],
    ["02","Backend","Async API + real-time push",["Python","FastAPI","REST API","WebSockets","MediaPipe"],"Async I/O, JWT auth, structured alert events, MJPEG streaming for low-latency overlay."],
    ["03","AI / ML","Pose + ergonomic engine",["MediaPipe Pose","33 Landmarks","Feature Eng.","Risk Classifier","RBA / RULA"],"Per-frame joint geometry — RBA + RULA heuristics — severity tiers, fatigue-weighted exposure."],
    ["04","Data","Lean persistence",[],["SQLite","JSON Archive","Analytics"],"Auth, roles, workers, alerts and reports in SQLite. Per-session JSON for replay and post-hoc analytics."],
  ];
  const gw = 2.83, gh = 4.15, gapx = 0.14, startX = 0.7, startY = 2.2;
  layers.forEach((l, i) => {
    const tags = l[3].length ? l[3] : l[4];
    const desc = l[5];
    const x = startX + i * (gw + gapx);
    card(s, x, startY, gw, gh, { fill: { color: CARD2 } });
    s.addText(`LAYER 0${i+1}`, { x: x + 0.2, y: startY + 0.2, w: gw - 0.4, h: 0.25, fontFace: FONT_BODY, fontSize: 8.5, bold: true, color: TEAL, charSpacing: 1.5 });
    s.addText(l[1], { x: x + 0.2, y: startY + 0.5, w: gw - 0.4, h: 0.4, fontFace: FONT_HEAD, fontSize: 18, bold: true, color: WHITE });
    s.addText(l[2], { x: x + 0.2, y: startY + 0.92, w: gw - 0.4, h: 0.3, fontFace: FONT_BODY, fontSize: 9, color: MUTED2, italic: true });
    let ty = startY + 1.35;
    tags.forEach(tag => {
      const tw = 0.3 + tag.length * 0.085;
      s.addShape("roundRect", { x: x + 0.2, y: ty, w: tw, h: 0.32, rectRadius: 0.16, fill: { color: "0E1830" }, line: { color: LINE, width: 0.75 } });
      s.addText(tag, { x: x + 0.2, y: ty, w: tw, h: 0.32, align: "center", valign: "middle", fontFace: FONT_BODY, fontSize: 8.5, color: BLUE, margin: 0 });
      ty += 0.42;
    });
    s.addShape("line", { x: x + 0.2, y: startY + gh - 1.15, w: gw - 0.4, h: 0, line: { color: LINE, width: 1 } });
    s.addText(desc, { x: x + 0.2, y: startY + gh - 1.0, w: gw - 0.4, h: 0.9, fontFace: FONT_BODY, fontSize: 8.7, color: MUTED, lineSpacingMultiple: 1.25 });
  });

  s.addShape("roundRect", { x: 0.7, y: 6.6, w: 12.0, h: 0.5, rectRadius: 0.06, fill: { color: CARD }, line: { color: LINE, width: 1 } });
  s.addText([
    { text: "ARCHITECTURE:  ", options: { bold: true, color: TEAL } },
    { text: "Stateless API · WebSocket fan-out · SQLite for fast early traction · Swap-ready for Postgres + Redis.", options: { color: MUTED } }
  ], { x: 0.95, y: 6.6, w: 11.5, h: 0.5, valign: "middle", fontFace: FONT_BODY, fontSize: 10 });
  footer(s, 6);
}

// =========================================================
// SLIDE 7 — IMPACT & USE CASES
// =========================================================
{
  const s = pres.addSlide();
  bgSlide(s);
  kicker(s, "06 · Impact & Use Cases", 0.7, 0.55);
  pageTitle(s, "From shop floor to home office\n— same AI, same impact.", 0.7, 0.9, 8, { fontSize: 28, h: 1.4, lineSpacingMultiple: 1.05 });

  const sectors = [
    ["01","Manufacturing & Assembly","Line workers · Safety officers","High-repetition lines where trunk flexion and shoulder strain dominate. AI flags risky posture in real time without disrupting output."],
    ["02","Warehousing & Logistics","Shift managers · Floor supervisors","Lifting, bending, repetitive motion across hundreds of workstations — multi-camera aggregation gives floor-wide visibility."],
    ["03","Corporate & Remote Work","HR · Workplace-experience teams","Employee laptops ship with webcams. Setting objective ergonomics to permanent WFH and hybrid workforces."],
    ["04","Occupational Health","Clinics · Insurers · OSH consultants","Validated, longitudinal posture data feeds into clinical assessment and insurance premium calibration."],
  ];
  const gw = 3.75, gh = 2.05, gapx = 0.15, gapy = 0.18, startX = 0.7, startY = 2.5;
  sectors.forEach((sec, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = startX + col * (gw + gapx), y = startY + row * (gh + gapy);
    card(s, x, y, gw, gh, { fill: { color: CARD2 } });
    badge(s, x + 0.18, y + 0.18, sec[0], 0.34);
    s.addText(sec[1], { x: x + 0.65, y: y + 0.14, w: gw - 0.85, h: 0.4, fontFace: FONT_BODY, fontSize: 12, bold: true, color: WHITE });
    s.addText(sec[2].toUpperCase(), { x: x + 0.65, y: y + 0.44, w: gw - 0.85, h: 0.25, fontFace: FONT_BODY, fontSize: 7.5, bold: true, color: TEAL, charSpacing: 0.5 });
    s.addText(sec[3], { x: x + 0.18, y: y + 0.78, w: gw - 0.36, h: 1.15, fontFace: FONT_BODY, fontSize: 9, color: MUTED, lineSpacingMultiple: 1.25 });
  });

  const px = 8.95, py = 2.5, pw = 3.7, ph = 4.4;
  s.addShape("roundRect", { x: px, y: py, w: pw, h: ph, rectRadius: 0.08, fill: { color: "0E1B2E" }, line: { color: TEAL, width: 1 } });
  s.addText("REAL WORLD IMPACT", { x: px + 0.25, y: py + 0.22, w: pw - 0.5, h: 0.25, fontFace: FONT_BODY, fontSize: 9.5, bold: true, color: TEAL, charSpacing: 1.5 });
  s.addText("What changes when you can measure it.", { x: px + 0.25, y: py + 0.5, w: pw - 0.5, h: 0.55, fontFace: FONT_HEAD, fontSize: 15, bold: true, color: WHITE, lineSpacingMultiple: 1.1 });
  const impacts = [
    ["Reduced MSD risk","Continuous coaching cuts high-risk posture exposure across shifts."],
    ["Objective safety data","Per-shift, per-worker posture health replaces annual self-reports."],
    ["Lower compliance effort","OSHA / ISO 45001 reports generated from live data, not manually compiled."],
    ["Higher worker trust","Camera-only deployment removes the wearable stigma — workers opt in."],
  ];
  let iy = py + 1.25;
  impacts.forEach(it => {
    s.addShape("ellipse", { x: px + 0.25, y: iy + 0.06, w: 0.1, h: 0.1, fill: { color: TEAL }, line: { type: "none" } });
    s.addText(it[0], { x: px + 0.48, y: iy - 0.06, w: pw - 0.75, h: 0.3, fontFace: FONT_BODY, fontSize: 11, bold: true, color: WHITE });
    s.addText(it[1], { x: px + 0.48, y: iy + 0.24, w: pw - 0.75, h: 0.55, fontFace: FONT_BODY, fontSize: 8.7, color: MUTED, lineSpacingMultiple: 1.25 });
    iy += 0.82;
  });

  s.addShape("roundRect", { x: 0.7, y: 6.75, w: 11.95, h: 0.5, rectRadius: 0.06, fill: { color: CARD }, line: { color: LINE, width: 1 } });
  s.addText([
    { text: "4 ", options: { bold: true, color: TEAL, fontSize: 13 } },
    { text: "  Four industries, one product. Wherever a webcam can see a worker, ErgoVigilance can measure — and reduce — their ergonomic risk.", options: { color: MUTED } }
  ], { x: 0.95, y: 6.75, w: 11.4, h: 0.5, valign: "middle", fontFace: FONT_BODY, fontSize: 10.5 });
  footer(s, 7);
}

// =========================================================
// SLIDE 8 — COMPETITIVE EDGE
// =========================================================
{
  const s = pres.addSlide();
  bgSlide(s);
  kicker(s, "07 · Competitive Edge", 0.7, 0.55);
  pageTitle(s, "Wearables make promises.\nWe ship cameras.", 0.7, 0.9, 9, { fontSize: 30, h: 1.4, lineSpacingMultiple: 1.05 });
  s.addText("Existing ergonomic-safety tools need hardware investment and worker compliance. ErgoVigilance is a webcam the worker already has — and the platform already running.", {
    x: 0.7, y: 2.15, w: 11.6, h: 0.45, fontFace: FONT_BODY, fontSize: 12, color: MUTED, lineSpacingMultiple: 1.25
  });

  const rows = [
    ["Hardware","IMUs, smartwatches or sensor vests per worker","Off-the-shelf webcams the workstation already has","Zero capex — no charging, no forgetting to wear it"],
    ["Worker adoption","Stigma + low compliance; workers remove devices","Camera-only — no body-worn tech, no sensor discomfort","Higher sustained adherence across shifts"],
    ["Data","Sparse sampling, manual observation, self-report","30 FPS pose data, session analytics, exposure intelligence","Continuous objective measurement"],
    ["Insights","Quarterly reports, lagging indicators","Live risk score + instant alerts + role dashboards","Reactive tools become proactive prevention"],
    ["Deployment cost","$300–$1,500 per worker for wearables","Standard webcam, AI runs in software","10×+ cheaper to deploy at scale"],
    ["Compliance","Manual logs, paper audits","Automatic audit trail, one-click compliance reports","OSH officers stop chasing paperwork"],
  ];
  const tx = 0.7, ty = 2.75, tw = 12.0, rh = 0.46;
  const c1 = 2.0, c2 = 4.1, c3 = 4.1, c4 = 1.8;
  s.addShape("roundRect", { x: tx, y: ty, w: tw, h: 0.42, rectRadius: 0.04, fill: { color: "0E1830" }, line: { color: LINE, width: 0.75 } });
  s.addText("DIMENSION", { x: tx + 0.15, y: ty, w: c1 - 0.15, h: 0.42, valign: "middle", fontFace: FONT_BODY, fontSize: 8.5, bold: true, color: MUTED2, charSpacing: 1 });
  s.addText("INDUSTRY (WEARABLE / MANUAL)", { x: tx + c1, y: ty, w: c2, h: 0.42, valign: "middle", fontFace: FONT_BODY, fontSize: 8.5, bold: true, color: MUTED2, charSpacing: 1 });
  s.addText("ERGOVIGILANCE (CAMERA-ONLY)", { x: tx + c1 + c2, y: ty, w: c3, h: 0.42, valign: "middle", fontFace: FONT_BODY, fontSize: 8.5, bold: true, color: TEAL, charSpacing: 1 });
  s.addText("OUR ADVANTAGE", { x: tx + c1 + c2 + c3, y: ty, w: c4, h: 0.42, valign: "middle", fontFace: FONT_BODY, fontSize: 8.5, bold: true, color: MUTED2, charSpacing: 1 });

  let ry = ty + 0.46;
  rows.forEach((r, i) => {
    if (i % 2 === 0) s.addShape("rect", { x: tx, y: ry, w: tw, h: rh, fill: { color: CARD }, line: { type: "none" } });
    s.addText(r[0], { x: tx + 0.15, y: ry, w: c1 - 0.15, h: rh, valign: "middle", fontFace: FONT_BODY, fontSize: 9.5, bold: true, color: WHITE });
    s.addText(r[1], { x: tx + c1, y: ry, w: c2 - 0.15, h: rh, valign: "middle", fontFace: FONT_BODY, fontSize: 9, color: MUTED });
    s.addText(r[2], { x: tx + c1 + c2, y: ry, w: c3 - 0.15, h: rh, valign: "middle", fontFace: FONT_BODY, fontSize: 9, color: TEAL });
    s.addText(r[3], { x: tx + c1 + c2 + c3, y: ry, w: c4, h: rh, valign: "middle", fontFace: FONT_BODY, fontSize: 8.5, bold: true, color: "9BE8DC" });
    ry += rh;
  });

  const hi = [["10×","cheaper vs. wearable deployment"], ["0","body hardware · camera-only, wearable-free"], ["Live","real-time insight, not quarterly reports"], ["Proven MVP","working webcam, real risk score, live dashboard"]];
  const hw = 2.9, hy = 6.55;
  hi.forEach((h, i) => {
    const x = 0.7 + i * (hw + 0.13);
    s.addText(h[0], { x, y: hy, w: hw, h: 0.35, fontFace: FONT_HEAD, fontSize: 18, bold: true, color: TEAL });
    s.addText(h[1].toUpperCase(), { x, y: hy + 0.34, w: hw, h: 0.35, fontFace: FONT_BODY, fontSize: 7.5, color: MUTED2, bold: true, charSpacing: 0.5 });
  });
  footer(s, 8);
}

// =========================================================
// SLIDE 9 — BUSINESS MODEL
// =========================================================
{
  const s = pres.addSlide();
  bgSlide(s);
  kicker(s, "08 · Business Model", 0.7, 0.55);
  pageTitle(s, "SaaS tiers that grow from\none camera to one enterprise.", 0.7, 0.9, 10, { fontSize: 28, h: 1.4, lineSpacingMultiple: 1.05 });
  s.addText("Hardware-free economics + low seat cost = viral adoption up the chain from a single workstation.", {
    x: 0.7, y: 2.25, w: 11.5, h: 0.4, fontFace: FONT_BODY, fontSize: 12.5, color: MUTED
  });

  const tiers = [
    { name: "Freemium", tag: "FOR TRIAL TEAMS, INDIVIDUAL SITES", price: "$0", per: "/ workstation / month", feats: ["Single webcam camera per surface", "Basic risk dashboard + risk gauge", "7-day session history", "Up to 3-role-based users", "Community support"], hl: false },
    { name: "Pro", tag: "WHERE MOST B2B REVENUE SITS", price: "$29", per: "/ seat · camera / month", feats: ["Multi-camera + multi-site aggregation", "Full analytics + heatmaps + reports", "Role-based dashboards (all 4 roles)", "Worker profiles + health scores", "PDF / Excel reports + audit trail", "Email + in-app alerts"], hl: true, badge: "RECOMMENDED" },
    { name: "Enterprise", tag: "FOR MULTI-SITE MANUFACTURING & FLEETS", price: "Custom", per: "/ site / month", feats: ["Multi-site enterprise deployment center", "SSO / SAML / Active Directory", "HRMS / ERP integrations (SAP, Oracle)", "Custom ML fine-tuning on your data", "Dedicated success manager + SLA", "On-prem or private cloud"], hl: false },
  ];
  const gw = 3.85, gh = 3.9, gapx = 0.22, startX = 0.7, startY = 2.9;
  tiers.forEach((t, i) => {
    const x = startX + i * (gw + gapx);
    card(s, x, startY, gw, gh, { fill: { color: t.hl ? "0E241F" : CARD2 }, line: { color: t.hl ? TEAL : LINE, width: t.hl ? 1.5 : 1 } });
    if (t.hl) {
      s.addShape("roundRect", { x: x + gw - 1.75, y: startY - 0.16, w: 1.6, h: 0.32, rectRadius: 0.16, fill: { color: TEAL } });
      s.addText(t.badge, { x: x + gw - 1.75, y: startY - 0.16, w: 1.6, h: 0.32, align: "center", valign: "middle", fontFace: FONT_BODY, fontSize: 8, bold: true, color: "062824", margin: 0 });
    }
    s.addText(`TIER 0${i+1}`, { x: x + 0.25, y: startY + 0.2, w: gw - 0.5, h: 0.22, fontFace: FONT_BODY, fontSize: 8.5, bold: true, color: MUTED2, charSpacing: 1.5 });
    s.addText(t.name, { x: x + 0.25, y: startY + 0.42, w: gw - 0.5, h: 0.42, fontFace: FONT_HEAD, fontSize: 20, bold: true, color: WHITE });
    s.addText([{ text: t.price, options: { fontSize: 26, bold: true, color: TEAL } }, { text: "  " + t.per, options: { fontSize: 9.5, color: MUTED2 } }], { x: x + 0.25, y: startY + 0.86, w: gw - 0.5, h: 0.45 });
    let fy = startY + 1.45;
    t.feats.forEach(f => {
      s.addShape("ellipse", { x: x + 0.27, y: fy + 0.075, w: 0.06, h: 0.06, fill: { color: TEAL }, line: { type: "none" } });
      s.addText(f, { x: x + 0.45, y: fy - 0.03, w: gw - 0.7, h: 0.35, fontFace: FONT_BODY, fontSize: 9.3, color: MUTED, valign: "top" });
      fy += 0.4;
    });
  });

  s.addText("CORE LEVER · Recurring seat/camera subscriptions (monthly & annual)      UPSELL · Premium analytics add-on & HRMS/ERP integrations      SERVICES · Deployment, ML tuning, compliance audits", {
    x: 0.7, y: 6.95, w: 11.95, h: 0.35, fontFace: FONT_BODY, fontSize: 8, color: MUTED2, align: "center"
  });
  footer(s, 9);
}

// =========================================================
// SLIDE 10 — ROADMAP
// =========================================================
{
  const s = pres.addSlide();
  bgSlide(s);
  kicker(s, "09 · Roadmap", 0.7, 0.55);
  pageTitle(s, "From hackathon weekend\nto multi-site enterprise.", 0.7, 0.9, 9, { fontSize: 28, h: 1.4, lineSpacingMultiple: 1.05 });
  s.addText("A four-phase rollout designed to validate the core on day 1, hit product-market-fit by month 3, and scale by month 4+.", {
    x: 0.7, y: 2.25, w: 11.5, h: 0.4, fontFace: FONT_BODY, fontSize: 12.5, color: MUTED
  });

  const phases = [
    { p: "PHASE 01 · NOW", t: "Hackathon MVP", w: "WEEKS 1–2", deliver: ["Webcam capture · 33-point MediaPipe pose", "Ergonomic feature engine + risk classifier", "Live dashboard + alerts + analytics — all deployed and demoable"], goal: "Live camera → risk score dashboard in under 200 ms." },
    { p: "PHASE 02 · BETA", t: "Closed Beta", w: "WEEKS 3–6", deliver: ["Multi-camera aggregation + facility view", "Role-based dashboards — Op / Sup / Mgr / Admin", "Worker profiles + longitudinal health score"], goal: "2+ paid pilot customers, measurable MSD reduction." },
    { p: "PHASE 03 · LAUNCH", t: "Public Launch", w: "MONTHS 2–3", deliver: ["Subscriptions — deployment center + self-serve onboarding", "Stripe billing — Freemium · Pro · Enterprise tiers", "First HRMS integrations"], goal: "$25K MRR · NPS > 40 · CAC payback < 9 months." },
    { p: "PHASE 04 · SCALE", t: "Scale Up", w: "MONTH 4+", deliver: ["Multi-site enterprise architecture + SSO/SAML", "iOS / Android companion app for supervisors", "Predictive injury-risk forecasting"], goal: "Enterprise contracts · 100+ monitored workstations." },
  ];
  const gw = 2.9, gh = 3.75, gapx = 0.13, startX = 0.7, startY = 2.9;
  s.addShape("line", { x: startX + 0.35, y: startY - 0.28, w: 4*(gw)+3*gapx - 0.7, h: 0, line: { color: LINE, width: 1.25 } });
  phases.forEach((ph, i) => {
    const x = startX + i * (gw + gapx);
    s.addShape("ellipse", { x: x + 0.2, y: startY - 0.4, w: 0.28, h: 0.28, fill: { color: TEAL_DK }, line: { color: TEAL, width: 1.25 } });
    s.addText(String(i+1), { x: x + 0.2, y: startY - 0.4, w: 0.28, h: 0.28, align: "center", valign: "middle", fontFace: FONT_BODY, fontSize: 10, bold: true, color: TEAL, margin: 0 });
    card(s, x, startY, gw, gh, { fill: { color: CARD2 } });
    s.addText(ph.p, { x: x + 0.2, y: startY + 0.18, w: gw - 0.4, h: 0.22, fontFace: FONT_BODY, fontSize: 8, bold: true, color: TEAL, charSpacing: 1 });
    s.addText(ph.t, { x: x + 0.2, y: startY + 0.42, w: gw - 0.4, h: 0.38, fontFace: FONT_HEAD, fontSize: 15.5, bold: true, color: WHITE });
    s.addText(ph.w, { x: x + 0.2, y: startY + 0.8, w: gw - 0.4, h: 0.24, fontFace: FONT_BODY, fontSize: 7.5, color: MUTED2, bold: true, charSpacing: 0.5 });
    s.addText("DELIVER", { x: x + 0.2, y: startY + 1.1, w: gw - 0.4, h: 0.2, fontFace: FONT_BODY, fontSize: 7, bold: true, color: MUTED2, charSpacing: 1 });
    let dy = startY + 1.32;
    ph.deliver.forEach(d => {
      s.addShape("ellipse", { x: x + 0.22, y: dy + 0.06, w: 0.05, h: 0.05, fill: { color: TEAL }, line: { type: "none" } });
      s.addText(d, { x: x + 0.37, y: dy - 0.04, w: gw - 0.55, h: 0.55, fontFace: FONT_BODY, fontSize: 7.7, color: MUTED, lineSpacingMultiple: 1.15 });
      dy += 0.58;
    });
    s.addShape("line", { x: x + 0.2, y: startY + gh - 0.55, w: gw - 0.4, h: 0, line: { color: LINE, width: 1 } });
    s.addText("GOAL", { x: x + 0.2, y: startY + gh - 0.46, w: gw - 0.4, h: 0.18, fontFace: FONT_BODY, fontSize: 6.5, bold: true, color: TEAL, charSpacing: 1 });
    s.addText(ph.goal, { x: x + 0.2, y: startY + gh - 0.28, w: gw - 0.4, h: 0.35, fontFace: FONT_BODY, fontSize: 7.6, color: WHITE, bold: true, lineSpacingMultiple: 1.1 });
  });
  s.addText("CURRENT FOCUS: Phase 01 — Hackathon MVP. Live demo end of weekend.", {
    x: 0.7, y: 6.85, w: 8, h: 0.3, fontFace: FONT_BODY, fontSize: 9.5, italic: true, color: TEAL
  });
  footer(s, 10);
}

// =========================================================
// SLIDE 11 — VISION + ENGINEERING CREDIBILITY
// =========================================================
{
  const s = pres.addSlide();
  bgSlide(s);
  kicker(s, "10 · Vision & Engineering", 0.7, 0.55);
  pageTitle(s, "Vision, then the four levers\nthat make it real.", 0.7, 0.9, 10, { fontSize: 28, h: 1.4, lineSpacingMultiple: 1.05 });

  s.addShape("roundRect", { x: 0.7, y: 2.45, w: 11.95, h: 1.15, rectRadius: 0.08, fill: { color: "0E1B2E" }, line: { color: TEAL, width: 1 } });
  s.addText("OUR VISION", { x: 1.0, y: 2.62, w: 3, h: 0.25, fontFace: FONT_BODY, fontSize: 9, bold: true, color: TEAL, charSpacing: 1.5 });
  s.addText([
    { text: "Make objective ergonomic safety monitoring ", options: { color: WHITE } },
    { text: "accessible to every workplace", options: { color: TEAL } },
    { text: " — from shop floors to home offices — without expensive hardware.", options: { color: WHITE } },
  ], { x: 1.0, y: 2.88, w: 11.4, h: 0.65, fontFace: FONT_HEAD, fontSize: 17, bold: true, lineSpacingMultiple: 1.15 });

  s.addText("BUILT FOR TRUST, NOT JUST DEMOS", { x: 0.7, y: 3.85, w: 6, h: 0.3, fontFace: FONT_BODY, fontSize: 11, bold: true, color: MUTED2, charSpacing: 1.5 });

  const eng = [
    ["Offline-first & private","Local SQLite + bcrypt + JWT auth, no cloud dependency. Runs a full shift with zero internet; the AI Assistant uses a local Ollama LLM."],
    ["Explainable AI","Every alert references a concrete posture event (frame, timestamp, risk snapshot); every recommendation traces back to the exact feature/threshold that triggered it."],
    ["Governed & tested","36-test pytest suite plus a 22-script legacy suite, model checksums verified in CI (SHA-256 manifest), green pipeline on every push."],
    ["Privacy by design","Right-to-erasure per worker, age + disk-cap data retention, role-enforced server-side permissions (403s) — not just hidden UI."],
  ];
  const gw2 = 5.85, gh2 = 1.35, gapx2 = 0.25, gapy2 = 0.2, startX2 = 0.7, startY2 = 4.2;
  eng.forEach((e, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = startX2 + col * (gw2 + gapx2), y = startY2 + row * (gh2 + gapy2);
    card(s, x, y, gw2, gh2, { fill: { color: CARD } });
    s.addShape("roundRect", { x: x + 0.2, y: y + 0.22, w: 0.34, h: 0.34, rectRadius: 0.06, fill: { color: TEAL_DK }, line: { color: TEAL, width: 1 } });
    s.addText("✓", { x: x + 0.2, y: y + 0.22, w: 0.34, h: 0.34, align: "center", valign: "middle", fontFace: FONT_BODY, fontSize: 13, bold: true, color: TEAL, margin: 0 });
    s.addText(e[0], { x: x + 0.7, y: y + 0.18, w: gw2 - 0.9, h: 0.3, fontFace: FONT_BODY, fontSize: 13, bold: true, color: WHITE });
    s.addText(e[1], { x: x + 0.7, y: y + 0.5, w: gw2 - 0.9, h: 0.75, fontFace: FONT_BODY, fontSize: 9.3, color: MUTED, lineSpacingMultiple: 1.25 });
  });
  footer(s, 11);
}

// =========================================================
// SLIDE 12 — TEAM + CLOSING
// =========================================================
{
  const s = pres.addSlide();
  bgSlide(s);
  corner(s, 0.55, 0.55, false, false);
  corner(s, W-0.55, H-0.55, true, true);

  kicker(s, "11 · The Team", 0.7, 0.7);
  s.addText("A lean team shipping a\nfull-stack AI product.", { x: 0.7, y: 1.05, w: 8, h: 1.2, fontFace: FONT_HEAD, fontSize: 28, bold: true, color: WHITE, lineSpacingMultiple: 1.05 });
  s.addText("Team Simulation Front — three specialists covering architecture, AI/ML, and full-stack delivery.", {
    x: 0.7, y: 2.15, w: 9, h: 0.35, fontFace: FONT_BODY, fontSize: 12.5, color: MUTED
  });

  const team = [
    ["R","Rian Hussain","Team Lead · AI / Pose Engineering","Pose estimation architecture, ergonomic risk engine, system design & integration"],
    ["J","Jatin Kumar","Backend / DevOps","FastAPI service & auth, WebSocket + MJPEG streaming, deployment & CI"],
    ["G","Guru Charan","Frontend / Product","React + TypeScript dashboard, role-based UX, demo strategy & pitch"],
  ];
  const gw = 3.85, gh = 2.7, gapx = 0.22, startX = 0.7, startY = 2.75;
  team.forEach((t, i) => {
    const x = startX + i * (gw + gapx);
    card(s, x, startY, gw, gh, { fill: { color: CARD2 } });
    s.addShape("ellipse", { x: x + gw/2 - 0.45, y: startY + 0.35, w: 0.9, h: 0.9, fill: { color: TEAL_DK }, line: { color: TEAL, width: 1.5 } });
    s.addText(t[0], { x: x + gw/2 - 0.45, y: startY + 0.35, w: 0.9, h: 0.9, align: "center", valign: "middle", fontFace: FONT_HEAD, fontSize: 28, bold: true, color: TEAL, margin: 0 });
    s.addText(t[1], { x: x + 0.2, y: startY + 1.45, w: gw - 0.4, h: 0.35, align: "center", fontFace: FONT_BODY, fontSize: 14, bold: true, color: WHITE });
    s.addText(t[2].toUpperCase(), { x: x + 0.2, y: startY + 1.78, w: gw - 0.4, h: 0.3, align: "center", fontFace: FONT_BODY, fontSize: 8, bold: true, color: TEAL, charSpacing: 0.5 });
    s.addText(t[3], { x: x + 0.3, y: startY + 2.12, w: gw - 0.6, h: 0.55, align: "center", fontFace: FONT_BODY, fontSize: 8.3, color: MUTED, lineSpacingMultiple: 1.2 });
  });

  s.addShape("line", { x: 0.7, y: 5.85, w: 11.95, h: 0, line: { color: LINE, width: 1 } });
  s.addText([
    { text: "Ergo", options: { color: WHITE, bold: true, fontSize: 22 } },
    { text: "Vigilance", options: { color: TEAL, bold: true, fontSize: 22 } },
  ], { x: 0.7, y: 6.05, w: 6, h: 0.5, fontFace: FONT_HEAD });
  s.addText("One webcam. Zero hardware. Continuous ergonomic safety — thank you.", {
    x: 0.7, y: 6.55, w: 8, h: 0.4, fontFace: FONT_BODY, fontSize: 13, italic: true, color: MUTED
  });
  s.addText("github.com/rianhussain007/Ergovigilance-", {
    x: 8.2, y: 6.6, w: 4.4, h: 0.35, fontFace: FONT_BODY, fontSize: 10.5, color: TEAL, align: "right", bold: true
  });
}

const outPath = path.resolve(__dirname, "../public/Hackathon_MVP.pptx");
pres.writeFile({ fileName: outPath }).then(() => {
  console.log("✅ PPTX written to " + outPath);
}).catch(err => {
  console.error("❌ Failed to write PPTX:", err);
  process.exit(1);
});
