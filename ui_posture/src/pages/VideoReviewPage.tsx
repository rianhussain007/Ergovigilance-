import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Download, Eye, EyeOff, FileVideo, History, RotateCcw, Sparkles, UploadCloud } from "lucide-react";
import {
  startVideoAnalysis,
  getVideoAnalysisJob,
  startRecordingAnalysis,
  downloadVideoWithOverlay,
  getRecordings,
  getRecordingRawVideoUrl,
} from "@/src/services/dashboardService";
import type { VideoAnalysisResponse, VideoAnalysisFrame, RecordingListItem } from "@/src/types/api";
import SessionCalendar, {
  aggregateByDay,
  parseSessionTimestamp,
  toDateKey,
} from "@/src/components/common/SessionCalendar";
import { formatISTFull } from "@/src/utils/formatTime";

const MAX_VIDEO_BYTES = 200 * 1024 * 1024;
const FEATURE_LABELS: Record<string, string> = {
  neck_flexion: "Neck Flexion",
  trunk_flexion: "Trunk Flexion",
  left_shoulder_elev: "Left Shoulder Elevation",
  right_shoulder_elev: "Right Shoulder Elevation",
  shoulder_symmetry: "Shoulder Symmetry",
  alignment_deviation: "Alignment Deviation",
  knee_angle: "Knee Angle",
  forward_head_posture: "Forward Head Posture",
  head_tilt_angle: "Head Tilt",
  wrist_deviation_angle: "Wrist Deviation",
  stance_stability: "Stance Stability",
  weight_shift_offset: "Weight Shift",
};

// MediaPipe Pose connections for skeleton drawing (from video_feed.py)
const POSE_CONNECTIONS: [number, number][] = [
  [11, 12],
  [11, 13],
  [13, 15],
  [12, 14],
  [14, 16], // Arms
  [11, 23],
  [12, 24],
  [23, 24], // Torso
  [23, 25],
  [25, 27],
  [24, 26],
  [26, 28], // Legs
  [27, 29],
  [29, 31],
  [28, 30],
  [30, 32], // Lower legs
  [15, 17],
  [15, 19],
  [15, 21],
  [16, 18],
  [16, 20],
  [16, 22], // Hands
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 7], // Face
  [0, 4],
  [4, 5],
  [5, 6],
  [6, 8], // Face
  [9, 10], // Mouth
];

const RISK_COLORS = {
  LOW: "rgb(74, 222, 128)", // green-400
  MEDIUM: "rgb(251, 191, 36)", // amber-400
  HIGH: "rgb(248, 113, 113)", // red-400
};

const CHART_WIDTH = 835;
const CHART_HEIGHT = 240;
const CHART_PADDING = { left: 40, right: 40, top: 30, bottom: 60 };

// Which body region each skeleton connection belongs to (same mapping the
// live overlay uses in backend_api/app/services/pose_overlay.py).
const CONNECTION_REGION: Record<string, string> = {
  "11-12": "torso",
  "11-13": "left_arm",
  "13-15": "left_arm",
  "12-14": "right_arm",
  "14-16": "right_arm",
  "11-23": "torso",
  "12-24": "torso",
  "23-24": "torso",
  "23-25": "left_leg",
  "25-27": "left_leg",
  "24-26": "right_leg",
  "26-28": "right_leg",
  "27-29": "left_leg",
  "29-31": "left_leg",
  "28-30": "right_leg",
  "30-32": "right_leg",
  "15-17": "left_arm",
  "15-19": "left_arm",
  "15-21": "left_arm",
  "16-18": "right_arm",
  "16-20": "right_arm",
  "16-22": "right_arm",
};

const REGION_RISK_ORDER: Record<string, number> = { LOW: 0, MEDIUM: 1, HIGH: 2 };

function regionForConnection(a: number, b: number): string {
  return CONNECTION_REGION[`${Math.min(a, b)}-${Math.max(a, b)}`] || "head";
}

function dimColor(color: string, visibility: number): string {
  if (visibility >= 0.75) return color;
  let factor: number;
  if (visibility >= 0.35) {
    factor = 0.5 + (0.5 * (visibility - 0.35)) / 0.4;
  } else {
    factor = Math.max(0.15, (visibility / 0.35) * 0.35);
  }
  // Scale an rgb(...) color by factor.
  const m = color.match(/rgb\((\d+), (\d+), (\d+)\)/);
  if (!m) return color;
  const [r, g, b] = [Number(m[1]), Number(m[2]), Number(m[3])];
  return `rgb(${Math.round(r * factor)}, ${Math.round(g * factor)}, ${Math.round(b * factor)})`;
}

/** Displayed content box of the video (handles letterboxing from object-fit). */
function getContentRect(video: HTMLVideoElement) {
  const elW = video.clientWidth || 640;
  const elH = video.clientHeight || 360;
  const vw = video.videoWidth || elW;
  const vh = video.videoHeight || elH;
  const scale = Math.min(elW / vw, elH / vh);
  const width = vw * scale;
  const height = vh * scale;
  return { x: (elW - width) / 2, y: (elH - height) / 2, width, height };
}

// ── Keypoint validity guard (mirrors backend `_kp_valid` in pose_overlay.py) ──
// MediaPipe emits (0,0)-style snaps or out-of-frame coordinates for occluded /
// missing landmarks. The backend burn path and live feed reject those before
// drawing; the in-browser canvas must apply the same rules or the skeleton
// draws "lines to the corner" and the overlay misaligns from the person.
const MIN_KP_VISIBILITY = 0.35;
// Face landmarks that MediaPipe can snap to frame edges when occluded.
const FACE_LANDMARK_INDICES = new Set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);

function isKeypointValid(kp: number[] | undefined): kp is number[] {
  if (!kp || kp.length < 2) return false;
  const visibility = kp[3] !== undefined ? kp[3] : 1.0;
  if (visibility < MIN_KP_VISIBILITY) return false;
  const x = kp[0];
  const y = kp[1];
  // Tight bounds for body landmarks (5% margin for edge jitter).
  if (x < -0.05 || x > 1.05 || y < -0.05 || y > 1.05) return false;
  return true;
}

// Face landmarks near the frame edge are almost certainly MediaPipe snapping an
// occluded face point to (0,0)/(1,0) — reject the outer band (same rule as the
// backend) to kill diagonal lines without losing real face data.
function isFaceEdgeSnap(idx: number, kp: number[]): boolean {
  if (!FACE_LANDMARK_INDICES.has(idx)) return false;
  const x = kp[0];
  const y = kp[1];
  return x < 0.1 || x > 0.9 || y < 0.05 || y > 0.9;
}

function drawSkeleton(
  ctx: CanvasRenderingContext2D,
  frame: VideoAnalysisFrame,
  canvasWidth: number,
  canvasHeight: number,
  contentRect: { x: number; y: number; width: number; height: number }
): void {
  if (!frame.keypoints || frame.keypoints.length === 0) return;

  ctx.clearRect(0, 0, canvasWidth, canvasHeight);

  // Per-region risk bands — identical values the live overlay uses (computed
  // by the backend from the same per-feature thresholds), so a raised arm
  // turns red while the rest of the skeleton stays green.
  const regionLevels: Record<string, string> = frame.region_risks || {};
  const overall = frame.risk_level;
  const regionColor = (region: string): string => {
    const level = regionLevels[region] || overall;
    return RISK_COLORS[level as keyof typeof RISK_COLORS] || RISK_COLORS.LOW;
  };

  // Joint color = worst-risk region touching that joint.
  const jointRegions: Record<number, Set<string>> = {};
  for (const [startIdx, endIdx] of POSE_CONNECTIONS) {
    const region = regionForConnection(startIdx, endIdx);
    (jointRegions[startIdx] ||= new Set()).add(region);
    (jointRegions[endIdx] ||= new Set()).add(region);
  }
  const jointColor = (idx: number): string => {
    const regions = jointRegions[idx];
    if (!regions || regions.size === 0) return regionColor("head");
    let worst = "head";
    for (const r of regions) {
      const lvl = regionLevels[r] || overall;
      const cur = regionLevels[worst] || overall;
      if (REGION_RISK_ORDER[lvl] > REGION_RISK_ORDER[cur]) worst = r;
    }
    return regionColor(worst);
  };

  const px = (kp: number[]): [number, number] => [
    contentRect.x + kp[0] * contentRect.width,
    contentRect.y + kp[1] * contentRect.height,
  ];

  // Draw connections (each segment colored by its own region's risk).
  // Skip any segment touching an invalid keypoint (occluded / out-of-frame /
  // low-visibility) — same rule the backend burn path uses, so the browser
  // overlay never draws "lines to the corner" from a (0,0) snap.
  for (const [startIdx, endIdx] of POSE_CONNECTIONS) {
    if (startIdx >= frame.keypoints.length || endIdx >= frame.keypoints.length) {
      continue;
    }
    const startKp = frame.keypoints[startIdx];
    const endKp = frame.keypoints[endIdx];
    if (!isKeypointValid(startKp) || !isKeypointValid(endKp)) continue;
    if (isFaceEdgeSnap(startIdx, startKp) || isFaceEdgeSnap(endIdx, endKp)) continue;
    const [x1, y1] = px(startKp);
    const [x2, y2] = px(endKp);
    const visibility = Math.min(
      startKp[3] !== undefined ? startKp[3] : 1.0,
      endKp[3] !== undefined ? endKp[3] : 1.0
    );
    ctx.globalAlpha = 0.35 + visibility * 0.65;
    ctx.beginPath();
    ctx.strokeStyle = dimColor(regionColor(regionForConnection(startIdx, endIdx)), visibility);
    ctx.lineWidth = 3.5;
    ctx.lineCap = "round";
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    ctx.globalAlpha = 1.0;
  }

  // Draw joints (colored by their worst touching region).
  // Skip invalid keypoints so a (0,0) snap never draws a joint dot in the
  // top-left corner of the frame.
  for (let i = 0; i < Math.min(frame.keypoints.length, 33); i++) {
    const kp = frame.keypoints[i];
    if (!isKeypointValid(kp)) continue;
    if (isFaceEdgeSnap(i, kp)) continue;
    const [x, y] = px(kp);
    const visibility = kp[3] !== undefined ? kp[3] : 1.0;
    ctx.globalAlpha = 0.35 + visibility * 0.65;
    ctx.beginPath();
    ctx.fillStyle = dimColor(jointColor(i), visibility);
    ctx.arc(x, y, 7, 0, 2 * Math.PI);
    ctx.fill();
    ctx.strokeStyle = "rgba(240, 250, 245, 0.9)";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.globalAlpha = 1.0;
  }

  // Per-joint angle labels (same joints/labels as the live overlay)
  const labelConfigs: Array<[string, string, number, [number, number]]> = [
    ["neck_flexion", "N", 0, [-20, -30]],
    ["trunk_flexion", "T", 23, [15, -10]],
    ["left_shoulder_elev", "LS", 11, [-30, -20]],
    ["right_shoulder_elev", "RS", 12, [10, -20]],
    ["shoulder_symmetry", "Sym", 11, [-55, -35]],
    ["knee_angle", "K", 25, [15, 5]],
  ];

  ctx.font = "12px sans-serif";
  ctx.textBaseline = "middle";

  for (const [feat, short, kpIdx, offset] of labelConfigs) {
    if (kpIdx >= frame.keypoints.length) continue;
    const value = frame.features[feat];
    // Skip null / undefined / NaN values (NaN may arrive serialized as null).
    if (value == null || value !== value) continue;
    const kp = frame.keypoints[kpIdx];
    // Don't anchor an angle label to an occluded / out-of-frame joint — the
    // label would float at a bogus position and mislead the viewer.
    if (!isKeypointValid(kp) || isFaceEdgeSnap(kpIdx, kp)) continue;
    const [baseX, baseY] = px(kp);
    const x = Math.max(4, Math.min(baseX + offset[0], canvasWidth - 90));
    const y = Math.max(14, Math.min(baseY + offset[1], canvasHeight - 4));
    const text = `${short}:${value.toFixed(1)}`;
    const labelColor = jointColor(kpIdx);
    ctx.fillStyle = "rgba(8, 12, 18, 0.9)";
    const metrics = ctx.measureText(text);
    ctx.fillRect(x - 4, y - 9, metrics.width + 8, 17);
    ctx.strokeStyle = labelColor;
    ctx.lineWidth = 1;
    ctx.strokeRect(x - 4, y - 9, metrics.width + 8, 17);
    ctx.fillStyle = labelColor;
    ctx.fillText(text, x, y);
  }
}

// ── Person boxes + identity tags (mirrors backend draw_person_boxes) ──
// Draws one YOLO bounding box per person with an identity tag: the worker's
// name when face-matched, "Not recognized" when a face was seen but not
// enrolled/matched. Same colors as the live feed so Video Review matches the
// monitoring overlay. Boxes use normalized 0-1 xyxy mapped into the letterboxed
// video rect (same mapping as the skeleton's px() helper).
function drawPersonIdentities(
  ctx: CanvasRenderingContext2D,
  frame: VideoAnalysisFrame,
  contentRect: { x: number; y: number; width: number; height: number },
): void {
  const entries = frame.person_identities;
  const boxes = frame.person_boxes;
  if ((!entries || entries.length === 0) && (!boxes || boxes.length === 0)) return;

  const toX = (nx: number) => contentRect.x + nx * contentRect.width;
  const toY = (ny: number) => contentRect.y + ny * contentRect.height;

  // Normalize to per-person entries (same fallback the backend uses).
  type Entry = { box: { x1: number; y1: number; x2: number; y2: number }; worker_id?: string | null; name?: string | null; confidence?: number; matched?: boolean; seen?: boolean };
  let entriesNorm: Entry[];
  if (entries && entries.length > 0) {
    entriesNorm = entries.map((e) => ({
      box: e.box,
      worker_id: e.worker_id,
      name: e.name,
      confidence: e.confidence,
      matched: e.matched,
      seen: e.seen !== undefined ? e.seen : !!e.confidence && e.confidence > 0,
    }));
  } else {
    entriesNorm = (boxes || []).map((b) => ({ box: b }));
  }
  if (entriesNorm.length === 0) return;

  const area = (e: Entry) => (e.box.x2 - e.box.x1) * (e.box.y2 - e.box.y1);
  const primary = entriesNorm.reduce((best, e) => (area(e) > area(best) ? e : best), entriesNorm[0]);

  for (const entry of entriesNorm) {
    const isPrimary = entry === primary;
    const matched = !!entry.matched && !!entry.worker_id;
    const tag =
      matched
        ? (entry.name || entry.worker_id || '') + (entry.confidence && entry.confidence > 0 ? `  (${(entry.confidence * 100).toFixed(0)}%)` : '')
        : entry.seen
          ? 'Not recognized'
          : null;

    const color = matched ? '#40e078' : tag ? '#55aaff' : '#788aa8';
    const x1 = toX(entry.box.x1);
    const y1 = toY(entry.box.y1);
    const x2 = toX(entry.box.x2);
    const y2 = toY(entry.box.y2);

    ctx.strokeStyle = color;
    ctx.lineWidth = isPrimary ? 3 : 1;
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

    if (tag) {
      ctx.font = 'bold 13px system-ui, sans-serif';
      const tw = ctx.measureText(tag).width;
      const pad = 5;
      const tx = Math.max(0, Math.min(x1, contentRect.width - tw - pad * 2));
      const ty = Math.max(0, y1 - 24);
      ctx.fillStyle = 'rgba(8, 12, 18, 0.92)';
      ctx.fillRect(tx, ty, tw + pad * 2, 22);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.strokeRect(tx, ty, tw + pad * 2, 22);
      ctx.fillStyle = color;
      ctx.fillText(tag, tx + pad, ty + 16);
    }
  }
}

function RiskLegend() {
  return (
    <div className="flex items-center gap-4 text-sm text-on-surface">
      {(["LOW", "MEDIUM", "HIGH"] as const).map((level) => (
        <div key={level} className="flex items-center gap-1">
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: RISK_COLORS[level] }}
          />
          <span className="text-xs uppercase">{level}</span>
        </div>
      ))}
    </div>
  );
}

function RiskBar({ level, value }: { level: "LOW" | "MEDIUM" | "HIGH"; value: number }) {
  // A zero value must render as an empty track — never as a filled neutral
  // bar that reads as if data exists.
  const pct = Math.max(0, Math.min(100, value));
  const empty = pct <= 0;
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="text-on-surface-variant">{level}</span>
        <span className="font-mono text-on-surface">{value.toFixed(1)}%</span>
      </div>
      <div
        className={`h-2 overflow-hidden rounded ${empty ? "border border-outline-variant/30 bg-transparent" : "bg-surface-container-highest"}`}
      >
        {!empty && (
          <div
            className="h-full rounded transition-all"
            style={{
              width: `${pct}%`,
              backgroundColor: RISK_COLORS[level],
            }}
          />
        )}
      </div>
    </div>
  );
}

function buildRiskPath(result: VideoAnalysisResponse): string {
  if (!result || result.frames.length === 0) return "";
  const width = CHART_WIDTH - CHART_PADDING.left - CHART_PADDING.right;
  const height = CHART_HEIGHT - CHART_PADDING.top - CHART_PADDING.bottom;
  const maxTime = Math.max(...result.frames.map((frame) => frame.timestamp_seconds), 1);
  const score = (risk: string) => (risk === "HIGH" ? 3 : risk === "MEDIUM" ? 2 : 1);
  return result.frames
    .map((frame, index) => {
      const x =
        CHART_PADDING.left + (frame.timestamp_seconds / maxTime) * width;
      const y =
        CHART_PADDING.top +
        height -
        ((score(frame.risk_level) - 1) / 2) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
}

function buildTimeLabels(result: VideoAnalysisResponse): { x: number; label: string }[] {
  if (!result || result.frames.length === 0) return [];
  const maxTime = Math.max(...result.frames.map((frame) => frame.timestamp_seconds), 1);
  const count = Math.min(6, result.frames.length);
  const step = maxTime / (count - 1);
  const width = CHART_WIDTH - CHART_PADDING.left - CHART_PADDING.right;
  const labels: { x: number; label: string }[] = [];
  for (let i = 0; i < count; i++) {
    const t = i * step;
    const x = CHART_PADDING.left + (t / maxTime) * width;
    labels.push({ x, label: `${t.toFixed(1)}s` });
  }
  return labels;
}

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function VideoReviewPage() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [result, setResult] = useState<VideoAnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "processing" | "complete">("idle");
  const [progress, setProgress] = useState(0);
  const analysisCancelledRef = useRef(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [recordings, setRecordings] = useState<RecordingListItem[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [recordingLoading, setRecordingLoading] = useState(false);
  const [sortOrder, setSortOrder] = useState<"newest" | "oldest">("newest");
  const [workerFilter, setWorkerFilter] = useState("");
  const [riskFilter, setRiskFilter] = useState("");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [levelFilter, setLevelFilter] = useState<"LOW" | "MEDIUM" | "HIGH" | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [showOverlay, setShowOverlay] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [hoverTime, setHoverTime] = useState<number | null>(null);

  const riskPath = useMemo(() => buildRiskPath(result!), [result]);
  const timeLabels = useMemo(() => buildTimeLabels(result!), [result]);

  // Helper 1: find current frame (nearest stored sample)
  const findCurrentFrame = useCallback(
    (time: number): VideoAnalysisFrame | null => {
      if (!result || result.frames.length === 0) return null;
      let closest = result.frames[0];
      let minDiff = Math.abs(time - closest.timestamp_seconds);
      for (let i = 1; i < result.frames.length; i++) {
        const diff = Math.abs(time - result.frames[i].timestamp_seconds);
        if (diff < minDiff) {
          minDiff = diff;
          closest = result.frames[i];
        }
      }
      return closest;
    },
    [result]
  );

  // Helper 1b: temporally-interpolated keypoints for the overlay.
  // The backend stores one analysis record every frame_step frames (default
  // 10 -> ~0.4 s at 25 fps), so drawing the raw nearest sample makes the
  // skeleton STEP between samples during playback. Blend the two surrounding
  // stored samples' keypoints by playback position so the skeleton glides
  // continuously and stays locked to the person on screen (the same
  // temporal-smoothing idea the CLI labeling tool uses).
  const interpolatedKeypoints = useCallback(
    (time: number): number[][] | null => {
      if (!result || result.frames.length === 0) return null;
      const frames = result.frames;
      const first = frames[0];
      // Note: [] is truthy in JS — always check length, or an empty-keypoints
      // edge would short-circuit the overlay fallback and blank the skeleton.
      if (time <= first.timestamp_seconds) {
        return first.keypoints?.length ? first.keypoints : null;
      }
      const last = frames[frames.length - 1];
      if (time >= last.timestamp_seconds) {
        return last.keypoints?.length ? last.keypoints : null;
      }
      for (let i = 0; i < frames.length - 1; i++) {
        const a = frames[i];
        const b = frames[i + 1];
        if (time >= a.timestamp_seconds && time <= b.timestamp_seconds) {
          const span = b.timestamp_seconds - a.timestamp_seconds;
          if (span <= 0) return a.keypoints?.length ? a.keypoints : null;
          const f = (time - a.timestamp_seconds) / span;
          const ka = a.keypoints || [];
          const kb = b.keypoints || [];
          if (ka.length === 0) return kb.length ? kb : null;
          if (kb.length === 0) return ka;
          const n = Math.max(ka.length, kb.length);
          const out: number[][] = [];
          for (let j = 0; j < n; j++) {
            const pa = ka[j] || [0, 0, 0, 0];
            const pb = kb[j] || pa;
            // Never interpolate toward an invalid (occluded / out-of-frame)
            // keypoint — that would drag the skeleton toward a (0,0) snap
            // between samples. Hold the valid endpoint's value instead, so the
            // overlay only moves when both samples are trustworthy.
            const aValid = isKeypointValid(pa) && !isFaceEdgeSnap(j, pa);
            const bValid = isKeypointValid(pb) && !isFaceEdgeSnap(j, pb);
            if (!aValid && bValid) {
              out.push(pb);
              continue;
            }
            if (aValid && !bValid) {
              out.push(pa);
              continue;
            }
            if (!aValid && !bValid) {
              out.push(pa);
              continue;
            }
            out.push([
              pa[0] + (pb[0] - pa[0]) * f,
              pa[1] + (pb[1] - pa[1]) * f,
              pa[2] + (pb[2] - pa[2]) * f,
              pa[3] + (pb[3] - pa[3]) * f,
            ]);
          }
          return out;
        }
      }
      return last.keypoints || null;
    },
    [result]
  );

  const currentFrame = useMemo(() => findCurrentFrame(currentTime), [
    currentTime,
    findCurrentFrame,
  ]);

  // Keypoints actually drawn on the canvas: interpolated between the two
  // surrounding stored samples (falls back to the nearest sample's raw
  // keypoints when no interpolation is possible, e.g. first/last frame).
  const overlayKeypoints = useMemo(
    () => interpolatedKeypoints(currentTime) || currentFrame?.keypoints || null,
    [currentTime, interpolatedKeypoints, currentFrame]
  );

  const handleTimeUpdate = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    setCurrentTime(video.currentTime);
    if (!result || !showOverlay) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    // Keep the canvas buffer in sync with the displayed video element so the
    // skeleton never draws into a stale 300x150 default buffer (which the CSS
    // would stretch, misaligning the overlay from the person in the video).
    canvas.width = video.clientWidth || canvas.width;
    canvas.height = video.clientHeight || canvas.height;
    if (currentFrame) {
      // Draw with the temporally-interpolated keypoints so the skeleton
      // tracks the person smoothly between stored samples instead of stepping.
      const drawFrame: VideoAnalysisFrame = {
        ...currentFrame,
        keypoints: overlayKeypoints || currentFrame.keypoints,
      };
      const contentRect = getContentRect(video);
      drawSkeleton(ctx, drawFrame, canvas.width, canvas.height, contentRect);
      // Person boxes + identity tags on top of the skeleton — every person
      // gets a box, and each face is tagged by name or "Not recognized".
      drawPersonIdentities(ctx, drawFrame, contentRect);
    } else {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }, [result, showOverlay, currentFrame, overlayKeypoints]);

  // Redraw the skeleton immediately when the overlay is re-enabled (the canvas
  // only mounts while the overlay is on, so a fresh frame is needed).
  useEffect(() => {
    if (!showOverlay || !currentFrame) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    canvas.width = video.clientWidth || canvas.width;
    canvas.height = video.clientHeight || canvas.height;
    const drawFrame: VideoAnalysisFrame = {
      ...currentFrame,
      keypoints: overlayKeypoints || currentFrame.keypoints,
    };
    drawSkeleton(ctx, drawFrame, canvas.width, canvas.height, getContentRect(video));
  }, [showOverlay, currentFrame, overlayKeypoints]);

  const handleVideoLoadedMetadata = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width = video.clientWidth;
    canvas.height = video.clientHeight;
  }, []);

  // The SVG uses a fixed viewBox (CHART_WIDTH x CHART_HEIGHT) but is scaled to
  // fill its container, so CSS-pixel x must be scaled back into viewBox units
  // before mapping to a timestamp — otherwise clicks land at the wrong second.
  const chartTimeFromEvent = useCallback(
    (clientX: number, rect: DOMRect): number | null => {
      if (!result) return null;
      const viewX = ((clientX - rect.left) / rect.width) * CHART_WIDTH;
      const chartLeft = CHART_PADDING.left;
      const chartRight = CHART_WIDTH - CHART_PADDING.right;
      const maxTime = Math.max(...result.frames.map((f) => f.timestamp_seconds), 1);
      const ratio = (viewX - chartLeft) / (chartRight - chartLeft);
      return Math.max(0, Math.min(maxTime, ratio * maxTime));
    },
    [result]
  );

  const handleChartClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!videoRef.current || !result) return;
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const time = chartTimeFromEvent(e.clientX, rect);
    if (time === null) return;
    videoRef.current.currentTime = time;
    setCurrentTime(time);
  };

  const handleChartMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!result) return;
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const time = chartTimeFromEvent(e.clientX, rect);
    if (time === null) return;
    setHoverTime(time);
  };

  const handleChartMouseLeave = () => {
    setHoverTime(null);
  };

  const seekToFrame = (frame: VideoAnalysisFrame) => {
    if (videoRef.current) {
      videoRef.current.currentTime = frame.timestamp_seconds;
      setCurrentTime(frame.timestamp_seconds);
    }
  };

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (videoRef.current && canvasRef.current) {
        canvasRef.current.width = videoRef.current.clientWidth;
        canvasRef.current.height = videoRef.current.clientHeight;
        handleTimeUpdate();
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [handleTimeUpdate]);

  // Load the recorded-session list once so admins can re-analyze past sessions.
  useEffect(() => {
    getRecordings()
      .then((r) => setRecordings(r.recordings.filter((rec) => rec.has_video)))
      .catch(() => {
        /* non-fatal: the upload path still works without the session list */
      });
  }, []);

  // ── Filters + sorting ────────────────────────────────────────────────
  const formatSessionTs = useCallback((ts: string): string => {
    const d = parseSessionTimestamp(ts);
    if (!d) return ts;
    return formatISTFull(d);
  }, []);

  const workerOptions = useMemo(() => {
    const set = new Set<string>();
    for (const rec of recordings) if (rec.worker_id) set.add(rec.worker_id);
    return [...set].sort();
  }, [recordings]);

  // Calendar data: one shared aggregation drives both the calendar heatmap and
  // the legend's load-level filter, so they always agree.
  const calendarItems = useMemo(
    () =>
      recordings.map((rec) => ({
        timestamp: rec.session_timestamp,
        riskLevel: rec.risk_level || rec.highest_risk_level,
      })),
    [recordings]
  );

  // Day keys whose highest risk matches the active legend filter (e.g. the 5
  // heavy-load days when "Heavy load" is clicked).
  const levelDayKeys = useMemo(() => {
    if (!levelFilter) return null;
    const byDay = aggregateByDay(calendarItems);
    const keys = new Set<string>();
    for (const [key, agg] of byDay) if (agg.highestRisk === levelFilter) keys.add(key);
    return keys;
  }, [levelFilter, calendarItems]);

  const filteredRecordings = useMemo(() => {
    let list = recordings;
    if (workerFilter) list = list.filter((rec) => rec.worker_id === workerFilter);
    if (riskFilter)
      list = list.filter(
        (rec) => (rec.risk_level || rec.highest_risk_level || "LOW").toUpperCase() === riskFilter
      );
    if (selectedDate)
      list = list.filter((rec) => {
        const d = parseSessionTimestamp(rec.session_timestamp);
        return d ? toDateKey(d) === selectedDate : false;
      });
    if (levelDayKeys)
      list = list.filter((rec) => {
        const d = parseSessionTimestamp(rec.session_timestamp);
        return d ? levelDayKeys.has(toDateKey(d)) : false;
      });
    return [...list].sort((a, b) => {
      const ta = parseSessionTimestamp(a.session_timestamp)?.getTime() ?? 0;
      const tb = parseSessionTimestamp(b.session_timestamp)?.getTime() ?? 0;
      return sortOrder === "newest" ? tb - ta : ta - tb;
    });
  }, [recordings, workerFilter, riskFilter, selectedDate, sortOrder, levelDayKeys]);

  const clearFilters = useCallback(() => {
    setSortOrder("newest");
    setWorkerFilter("");
    setRiskFilter("");
    setSelectedDate(null);
    setLevelFilter(null);
  }, []);

  const hasActiveFilters =
    workerFilter !== "" || riskFilter !== "" || selectedDate !== null || levelFilter !== null;

  // If the selected session is hidden by the current filters, drop it.
  useEffect(() => {
    if (
      selectedSessionId &&
      !filteredRecordings.some((rec) => rec.session_id === selectedSessionId)
    ) {
      setSelectedSessionId("");
    }
  }, [filteredRecordings, selectedSessionId]);

  const chooseFile = (file: File | null) => {
    analysisCancelledRef.current = true;
    setError(null);
    setResult(null);
    setJobId(null);
    setStatus("idle");
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    if (!file) {
      setSelectedFile(null);
      setVideoUrl(null);
      return;
    }
    if (file.size > MAX_VIDEO_BYTES) {
      setSelectedFile(null);
      setVideoUrl(null);
      setError("Video exceeds the 200MB upload limit.");
      return;
    }
    setSelectedFile(file);
    setVideoUrl(URL.createObjectURL(file));
  };

  // Cancel any in-flight analysis when the user picks a new file or the page
  // unmounts (prevents stale poll loops writing state after unmount).
  useEffect(() => {
    return () => { analysisCancelledRef.current = true; };
  }, []);

  // Shared poll loop for both uploads and recorded-session analyses.
  const pollJob = useCallback(async (job_id: string) => {
    analysisCancelledRef.current = false;
    setStatus("processing");
    setProgress(0);
    setError(null);
    setResult(null);
    for (let attempt = 0; attempt < 600; attempt++) {
      await new Promise((r) => setTimeout(r, 1000));
      if (analysisCancelledRef.current) return;
      const job = await getVideoAnalysisJob(job_id);
      if (analysisCancelledRef.current) return;
      if (job.progress && typeof job.progress.percent === "number") {
        setProgress(Math.min(99, job.progress.percent));
      }
      if (job.status === "complete") {
        setJobId(job_id);
        setResult(job.result);
        setProgress(100);
        setStatus("complete");
        return;
      }
      if (job.status === "error") {
        setStatus("idle");
        setError(job.error || "Video analysis failed");
        return;
      }
    }
    if (analysisCancelledRef.current) return;
    setStatus("idle");
    setError("Analysis timed out. Please try again.");
  }, []);

  const handleAnalyze = async () => {
    if (!selectedFile || status === "processing") return;
    setError(null);
    try {
      const { job_id } = await startVideoAnalysis(selectedFile);
      await pollJob(job_id);
    } catch (err) {
      if (analysisCancelledRef.current) return;
      setStatus("idle");
      setError(err instanceof Error ? err.message : "Video analysis failed");
    }
  };

  const handleAnalyzeRecording = async () => {
    if (!selectedSessionId || status === "processing") return;
    setError(null);
    setRecordingLoading(true);
    try {
      const { job_id } = await startRecordingAnalysis(selectedSessionId);
      // Play the session's CLEAN original video while the job runs. The raw
      // file is required: the server prefers the live-burned overlay.mp4, and
      // drawing the analysis skeleton on top of that would stack two
      // skeletons from different runs (the "overlay not matching" bug).
      setVideoUrl(getRecordingRawVideoUrl(selectedSessionId));
      setSelectedFile(null);
      await pollJob(job_id);
    } catch (err) {
      if (analysisCancelledRef.current) return;
      setStatus("idle");
      setError(err instanceof Error ? err.message : "Recording analysis failed");
    } finally {
      setRecordingLoading(false);
    }
  };

  const downloadJson = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${result.filename.replace(/\.[^.]+$/, "")}_analysis.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-lg space-y-lg pb-32">
      {/* Single page title — no competing cards in the header. */}
      <header className="min-w-0">
        <h1 className="text-display-lg font-bold text-on-surface">Video Analysis</h1>
        <p className="mt-xs text-body-sm text-on-surface-variant">
          Upload a video to compute real posture risk over time from the existing pose pipeline.
        </p>
      </header>

      <section className="grid grid-cols-1 gap-lg xl:grid-cols-[420px_minmax(0,1fr)] items-start">
        {/* LEFT: actions — upload + recorded-session review */}
        <div className="flex flex-col space-y-lg">
          <div className="rounded-lg border border-outline-variant bg-surface-container p-lg">
          <div
            className="flex-1 rounded-lg border border-dashed border-outline-variant bg-surface-container-low p-xl text-center"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              chooseFile(event.dataTransfer.files?.[0] ?? null);
            }}
          >
            <UploadCloud className="mx-auto h-10 w-10 text-primary" />
            <h2 className="mt-md text-headline-md text-on-surface">Upload Video</h2>
            <p className="mt-sm text-body-sm text-on-surface-variant">
              MP4, AVI, MOV, or M4V. Max size: 200MB.
            </p>
            <input
              ref={inputRef}
              type="file"
              accept="video/mp4,video/avi,video/quicktime,video/x-m4v,.mp4,.avi,.mov,.m4v"
              className="hidden"
              onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
            />
            <button
              className="mt-lg h-10 rounded-lg bg-primary px-lg text-body-sm font-semibold text-on-primary"
              onClick={() => inputRef.current?.click()}
            >
              Select File
            </button>
          </div>

          {selectedFile && (
            <div className="mt-lg rounded-lg border border-outline-variant bg-surface-container-low p-md">
              <div className="flex items-start gap-md">
                <FileVideo className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                <div className="min-w-0">
                  <p className="truncate text-body-sm font-semibold text-on-surface">{selectedFile.name}</p>
                  <p className="mt-xs text-[11px] text-on-surface-variant">{formatBytes(selectedFile.size)}</p>
                </div>
              </div>
              <button
                className="mt-md h-10 w-full rounded-lg bg-tertiary px-md text-body-sm font-bold text-on-tertiary disabled:opacity-60"
                disabled={status === "processing"}
                onClick={handleAnalyze}
              >
                {status === "processing" ? "Processing video..." : "Analyze Video"}
              </button>
            </div>
          )}

          {status === "processing" && (
            <div className="mt-lg rounded-lg border border-primary/30 bg-primary/10 p-md space-y-sm">
              <div className="flex items-center gap-sm text-body-sm text-primary">
                <div className="h-4 w-4 animate-pulse rounded-full bg-primary" />
                Analyzing video in the background — {progress.toFixed(0)}%
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-container-higher">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-500"
                  style={{ width: `${Math.max(4, Math.min(100, progress))}%` }}
                />
              </div>
              <p className="text-[10px] text-on-surface-variant">
                Every frame runs through PoseEngine + Context Intelligence for smooth tracking (results stored at ~10-frame intervals). You can keep browsing — results appear here when ready.
              </p>
            </div>
          )}

          {error && (
            <div className="mt-lg rounded-lg border border-error/40 bg-error/10 p-md text-body-sm text-error">
              {error}
            </div>
          )}
          </div>

          <div className="rounded-lg border border-outline-variant bg-surface-container p-lg">
            <div className="mb-sm flex items-center gap-sm">
              <History className="h-4 w-4 text-primary" />
              <h3 className="text-body-sm font-bold text-on-surface">Review a Recorded Session</h3>
            </div>

            <div className="grid grid-cols-1 gap-sm sm:grid-cols-2">
              <label className="block">
                <span className="mb-xs block text-[10px] font-semibold uppercase text-on-surface-variant">
                  Sort order
                </span>
                <select
                  className="w-full rounded-lg border border-outline-variant bg-surface-container px-md py-sm text-body-sm text-on-surface"
                  value={sortOrder}
                  onChange={(e) => setSortOrder(e.target.value as "newest" | "oldest")}
                >
                  <option value="newest">Newest first</option>
                  <option value="oldest">Oldest first</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-xs block text-[10px] font-semibold uppercase text-on-surface-variant">
                  Worker
                </span>
                <select
                  className="w-full rounded-lg border border-outline-variant bg-surface-container px-md py-sm text-body-sm text-on-surface"
                  value={workerFilter}
                  onChange={(e) => setWorkerFilter(e.target.value)}
                >
                  <option value="">All workers</option>
                  {workerOptions.map((wid) => (
                    <option key={wid} value={wid}>
                      {wid}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="mb-xs block text-[10px] font-semibold uppercase text-on-surface-variant">
                  Highest risk
                </span>
                <select
                  className="w-full rounded-lg border border-outline-variant bg-surface-container px-md py-sm text-body-sm text-on-surface"
                  value={riskFilter}
                  onChange={(e) => setRiskFilter(e.target.value)}
                >
                  <option value="">Any level</option>
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                </select>
              </label>
              <div className="flex items-end">
                {hasActiveFilters && (
                  <button
                    className="flex h-10 w-full items-center justify-center gap-sm rounded-lg border border-outline-variant px-md text-body-sm text-on-surface hover:bg-surface-container"
                    onClick={clearFilters}
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    Clear filters
                  </button>
                )}
              </div>
            </div>

            <div className="mt-sm flex items-center justify-between text-[10px] text-on-surface-variant">
              <span>
                {filteredRecordings.length} session{filteredRecordings.length === 1 ? "" : "s"}
                {hasActiveFilters ? " match the filters" : " available"}
              </span>
              <span className="flex items-center gap-sm">
                {levelFilter && <span>Load: {levelFilter === "HIGH" ? "Heavy" : levelFilter === "MEDIUM" ? "Medium" : "Low"}</span>}
                {selectedDate && <span>{selectedDate}</span>}
              </span>
            </div>

            <select
              className="mt-sm w-full rounded-lg border border-outline-variant bg-surface-container px-md py-sm text-body-sm text-on-surface"
              value={selectedSessionId}
              onChange={(e) => setSelectedSessionId(e.target.value)}
            >
              <option value="">Select a session with a recording…</option>
              {filteredRecordings.map((rec) => (
                <option key={rec.session_id} value={rec.session_id}>
                  {formatSessionTs(rec.session_timestamp)} · {rec.worker_id} · {(rec.duration_seconds ?? 0).toFixed(0)}s · {rec.risk_level || rec.highest_risk_level}
                </option>
              ))}
            </select>
            <button
              className="mt-md h-10 w-full rounded-lg bg-tertiary px-md text-body-sm font-bold text-on-tertiary disabled:opacity-60"
              disabled={!selectedSessionId || status === "processing" || recordingLoading}
              onClick={handleAnalyzeRecording}
            >
              {recordingLoading ? "Analyzing recorded session…" : "Analyze Recorded Session"}
            </button>
            <p className="mt-sm text-[10px] text-on-surface-variant">
              Runs the same ML pose pipeline on the session's stored video — full keypoints, features,
              risk timeline, and a downloadable overlay video.
            </p>
            <a
              href="/sessions"
              className="mt-md inline-flex items-center gap-sm rounded-lg border border-dashed border-outline-variant bg-surface-container-low px-md py-sm no-underline transition hover:bg-surface-container"
            >
              <p className="font-label-caps text-[10px] text-on-surface-variant">Looking for a live session instead?</p>
              <p className="font-label-mono text-body-sm text-primary">Go to Sessions →</p>
            </a>
          </div>
        </div>

        {/* RIGHT: calendar above the analysis results — one connected column */}
        <div className="flex flex-col space-y-lg min-w-0">
          <SessionCalendar
            items={calendarItems}
            selectedDate={selectedDate}
            onSelectDate={setSelectedDate}
            levelFilter={levelFilter}
            onLevelFilterChange={setLevelFilter}
          />
          <div className="flex flex-col rounded-lg border border-outline-variant bg-surface-container p-lg min-h-[480px]">
          {!result ? (
            <div className="flex flex-1 flex-col items-center justify-center text-center">
              <Sparkles className="h-12 w-12 text-on-surface-variant" />
              <h2 className="mt-md text-headline-md text-on-surface">No Analysis Yet</h2>
              <p className="mt-sm text-body-sm text-on-surface-variant leading-relaxed">
                Upload a real video to see the risk timeline and feature averages from the live pose pipeline.
              </p>
            </div>
          ) : (
            <div className="space-y-lg">
              <div className="flex flex-wrap items-start justify-between gap-md">
                <div>
                  <p className="font-label-caps text-[10px] text-on-surface-variant">Analyzed File</p>
                  <h2 className="mt-xs text-headline-md text-on-surface">{result.filename}</h2>
                </div>
                <div className="flex items-center gap-md">
                  <button
                    className="flex items-center gap-sm rounded-lg border border-outline-variant px-md py-sm text-body-sm text-on-surface hover:bg-surface-container-low"
                    onClick={() => setShowOverlay(!showOverlay)}
                  >
                    {showOverlay ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    {showOverlay ? "Hide Overlay" : "Show Overlay"}
                  </button>
                  <button
                    className="flex items-center gap-sm rounded-lg bg-primary px-md py-sm text-body-sm font-semibold text-on-primary disabled:opacity-50"
                    disabled={!jobId || downloading || status !== "complete"}
                    onClick={async () => {
                      if (!jobId || !result) return;
                      setDownloading(true);
                      try {
                        await downloadVideoWithOverlay(jobId, `${result.filename.replace(/\.[^.]+$/, "")}_overlay.mp4`);
                      } catch (err) {
                        setError(err instanceof Error ? err.message : "Download failed");
                      } finally {
                        setDownloading(false);
                      }
                    }}
                  >
                    <Download className="h-4 w-4" />
                    {downloading ? "Preparing…" : "Download with Overlay"}
                  </button>
                  <button
                    className="flex items-center gap-sm rounded-lg border border-outline-variant px-md py-sm text-body-sm text-on-surface hover:bg-surface-container-low"
                    onClick={downloadJson}
                  >
                    <Download className="h-4 w-4" />
                    Download Data (JSON)
                  </button>
                </div>
              </div>

              {/* Honest status line — directly under "Analyzed File", before any
                  numbers, so data completeness is the first thing reviewers see.
                  One consistent status (amber when partial, neutral when complete)
                  replaces the old green badge that contradicted the warning. */}
              {(() => {
                const unavailable = result.summary.all_unavailable_features;
                const total = Object.keys(result.summary.average_features).length;
                if (unavailable.length === 0) {
                  return (
                    <div className="flex items-center gap-sm rounded-lg border border-outline-variant bg-surface-container-low px-md py-sm">
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-on-surface-variant" />
                      <p className="text-body-sm text-on-surface-variant">
                        Computed from real pipeline output — all {total} features available.
                      </p>
                    </div>
                  );
                }
                return (
                  <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-md">
                    <div className="flex items-start gap-sm">
                      <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
                      <div>
                        <p className="text-body-sm font-medium text-amber-500">
                          Computed from real pipeline output — {unavailable.length} of {total} features unavailable due to incomplete framing.
                        </p>
                        <p className="text-[11px] text-on-surface-variant mt-1">
                          {result.summary.frames_with_unavailable_features.toFixed(0)}% of frames have missing features · Unavailable: {unavailable.map(f => FEATURE_LABELS[f] || f).join(", ")}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* ------------------------------ */}
              {/* PART 1 & PART 2: Video Player + Skeleton + Current Frame Panel */}
              {/* ------------------------------ */}
              <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-lg">
                {/* Video & Canvas Overlay */}
                <div className="relative w-full rounded-lg overflow-hidden bg-black border border-outline-variant">
                  {videoUrl && (
                    <>
                      <video
                        ref={videoRef}
                        src={videoUrl}
                        controls
                        className="w-full max-h-[500px] object-contain"
                        onTimeUpdate={handleTimeUpdate}
                        onLoadedMetadata={handleVideoLoadedMetadata}
                        onSeeked={handleTimeUpdate}
                        onPlay={handleTimeUpdate}
                      />
                      {showOverlay && currentFrame && (
                        <canvas
                          ref={canvasRef}
                          className="absolute top-0 left-0 w-full h-full pointer-events-none"
                        />
                      )}
                    </>
                  )}
                </div>
                {/* Current Frame Feature Panel (PART 2) */}
                {currentFrame && (
                  <div className="rounded-lg border border-outline-variant bg-surface-container-low p-md">
                    <h3 className="text-body-sm font-semibold text-on-surface mb-3">
                      Current Frame ({currentFrame.timestamp_seconds.toFixed(1)}s)
                    </h3>
                    <div className="grid grid-cols-1 gap-2">
                      {Object.entries(FEATURE_LABELS).map(([feat, label]) => (
                        <div
                          key={feat}
                          className="flex items-center justify-between border-b border-outline-variant/60 last:border-0 pb-1 last:pb-0"
                        >
                          <span className="text-sm text-on-surface-variant">{label}</span>
                          {(() => {
                            const v = currentFrame.features[feat];
                            // A feature listed in the session-level "Partial
                            // Analysis" set is unavailable in the aggregate
                            // result — dash it here too, so this panel can
                            // never show a real number beside a warning that
                            // says the feature was unavailable (the Wrist
                            // Deviation 24.4-vs-unavailable contradiction).
                            const sessionUnavailable = (result.summary.all_unavailable_features || []).includes(feat);
                            const usable = !sessionUnavailable && v != null && v === v;
                            return usable ? (
                              <span className="text-sm text-on-surface font-mono">{v.toFixed(1)}</span>
                            ) : (
                              <span className="text-sm text-on-surface-variant font-mono">—</span>
                            );
                          })()}
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 flex items-center justify-between">
                      <span className="text-xs text-on-surface-variant font-label-caps uppercase">Risk</span>
                      <span
                        className="text-sm font-bold"
                        style={{ color: RISK_COLORS[currentFrame.risk_level as keyof typeof RISK_COLORS] }}
                      >
                        {currentFrame.risk_level}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* ------------------------------ */}
              {/* PART 1: Risk Over Time Chart (Interactive) */}
              {/* ------------------------------ */}
              <section className="rounded-lg border border-outline-variant bg-surface-container-low p-md">
                <div className="mb-md flex items-center justify-between gap-md">
                  <h3 className="text-body-sm font-bold text-on-surface">Risk Over Time</h3>
                  <RiskLegend />
                </div>
                <div className="h-[240px] rounded bg-[#111722]">
                  <svg
                    viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
                    className="h-full w-full cursor-pointer"
                    onClick={handleChartClick}
                    onMouseMove={handleChartMouseMove}
                    onMouseLeave={handleChartMouseLeave}
                  >
                    {/* Background Grid & Y-Axis */}
                    <line x1={CHART_PADDING.left} y1={CHART_PADDING.top} x2={CHART_PADDING.left} y2={CHART_HEIGHT - CHART_PADDING.bottom} stroke="var(--color-outline-variant)" />
                    <line x1={CHART_PADDING.left} y1={CHART_HEIGHT - CHART_PADDING.bottom} x2={CHART_WIDTH - CHART_PADDING.right} y2={CHART_HEIGHT - CHART_PADDING.bottom} stroke="var(--color-outline-variant)" />
                    <text x={CHART_PADDING.left - 10} y={CHART_PADDING.top + 5} fill="var(--color-on-surface-variant)" fontSize="12" textAnchor="end">HIGH</text>
                    <text x={CHART_PADDING.left - 10} y={(CHART_HEIGHT - CHART_PADDING.bottom - CHART_PADDING.top)/2 + CHART_PADDING.top + 5} fill="var(--color-on-surface-variant)" fontSize="12" textAnchor="end">MED</text>
                    <text x={CHART_PADDING.left - 10} y={CHART_HEIGHT - CHART_PADDING.bottom - 5} fill="var(--color-on-surface-variant)" fontSize="12" textAnchor="end">LOW</text>

                    {/* Risk Path */}
                    {riskPath && <path d={riskPath} fill="none" stroke="var(--color-primary)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />}

                    {/* Time Labels */}
                    {timeLabels.map((tick, i) => (
                      <g key={i}>
                        <line x1={tick.x} y1={CHART_HEIGHT - CHART_PADDING.bottom} x2={tick.x} y2={CHART_HEIGHT - CHART_PADDING.bottom + 10} stroke="var(--color-outline-variant)" strokeWidth="1" />
                        <text x={tick.x} y={CHART_HEIGHT - CHART_PADDING.bottom + 25} fill="var(--color-on-surface-variant)" fontSize="10" textAnchor="middle">{tick.label}</text>
                      </g>
                    ))}

                    {/* Hover Marker & Tooltip */}
                    {hoverTime !== null && result && (
                      <>
                        <line
                          x1={CHART_PADDING.left + (hoverTime / Math.max(...result.frames.map(f => f.timestamp_seconds), 1)) * (CHART_WIDTH - CHART_PADDING.left - CHART_PADDING.right)}
                          y1={CHART_PADDING.top}
                          x2={CHART_PADDING.left + (hoverTime / Math.max(...result.frames.map(f => f.timestamp_seconds), 1)) * (CHART_WIDTH - CHART_PADDING.left - CHART_PADDING.right)}
                          y2={CHART_HEIGHT - CHART_PADDING.bottom}
                          stroke="var(--color-on-surface)"
                          strokeWidth="2"
                          strokeDasharray="4 4"
                        />
                        {(() => {
                          const frame = findCurrentFrame(hoverTime);
                          if (!frame) return null;
                          const xPos = CHART_PADDING.left + (frame.timestamp_seconds / Math.max(...result.frames.map(f => f.timestamp_seconds), 1)) * (CHART_WIDTH - CHART_PADDING.left - CHART_PADDING.right);
                          return (
                            <g>
                              <rect
                                x={xPos - 50}
                                y={10}
                                width="100"
                                height="40"
                                fill="rgba(8,12,18,0.95)"
                                rx="4"
                              />
                              <text
                                x={xPos}
                                y={28}
                                fill="white"
                                fontSize="12"
                                textAnchor="middle"
                              >
                                {frame.timestamp_seconds.toFixed(1)}s
                              </text>
                              <text
                                x={xPos}
                                y={42}
                                fill={RISK_COLORS[frame.risk_level as keyof typeof RISK_COLORS]}
                                fontSize="12"
                                fontWeight="bold"
                                textAnchor="middle"
                              >
                                {frame.risk_level}
                              </text>
                            </g>
                          );
                        })()}
                      </>
                    )}

                    {/* Playhead (PART 1) */}
                    {result && (
                      <line
                        x1={CHART_PADDING.left + (currentTime / Math.max(...result.frames.map(f => f.timestamp_seconds), 1)) * (CHART_WIDTH - CHART_PADDING.left - CHART_PADDING.right)}
                        y1={CHART_PADDING.top}
                        x2={CHART_PADDING.left + (currentTime / Math.max(...result.frames.map(f => f.timestamp_seconds), 1)) * (CHART_WIDTH - CHART_PADDING.left - CHART_PADDING.right)}
                        y2={CHART_HEIGHT - CHART_PADDING.bottom}
                        stroke="#60a5fa"
                        strokeWidth="3"
                      />
                    )}
                  </svg>
                </div>
              </section>

              {/* Summary Section (Existing) */}
              <div className="grid grid-cols-1 gap-lg xl:grid-cols-2">
                <div className="rounded-lg border border-outline-variant bg-surface-container-low p-md">
                  <h3 className="text-body-sm font-bold text-on-surface">Risk Distribution</h3>
                  <div className="mt-md space-y-sm">
                    {(["LOW", "MEDIUM", "HIGH"] as const).map((level) => (
                      <RiskBar
                        key={level}
                        level={level}
                        value={result.summary.risk_percentages[level] ?? 0}
                      />
                    ))}
                  </div>
                </div>

                <div className="rounded-lg border border-outline-variant bg-surface-container-low p-md">
                  <h3 className="text-body-sm font-bold text-on-surface">Feature Averages</h3>
                  <div className="mt-md space-y-sm">
                    {Object.entries(result.summary.average_features).map(([name, value]) => {
                      // Any feature listed as unavailable in this session's
                      // status line must show a dash here too — never a numeric
                      // 0.0 that implies a real reading was taken.
                      const isUnavailable = result.summary.all_unavailable_features.includes(name);
                      return (
                        <div
                          key={name}
                          className="flex items-center justify-between gap-md border-b border-outline-variant/60 pb-xs"
                        >
                          <span className="text-body-sm text-on-surface-variant">{FEATURE_LABELS[name] || name}</span>
                          {isUnavailable ? (
                            <span className="font-label-mono text-body-sm text-on-surface-variant/60">—</span>
                          ) : (
                            <span className="font-label-mono text-body-sm text-on-surface">{(value ?? 0).toFixed(1)}</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              <section className="rounded-lg border border-outline-variant bg-surface-container-low p-md">
                <h3 className="text-body-sm font-bold text-on-surface">Frame Samples</h3>
                <div className="mt-md max-h-64 overflow-auto">
                  <table className="w-full text-left text-body-sm">
                    <thead className="sticky top-0 bg-surface-container-low text-[10px] uppercase text-on-surface-variant">
                      <tr>
                        <th className="py-sm">Time</th>
                        <th className="py-sm">Frame</th>
                        <th className="py-sm">Risk</th>
                        <th className="py-sm">Confidence</th>
                        <th className="py-sm">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.frames.map((frame) => (
                        <tr key={frame.frame_index} className="border-t border-outline-variant/60">
                          <td className="py-sm font-mono">{frame.timestamp_seconds.toFixed(1)}s</td>
                          <td className="py-sm font-mono">{frame.frame_index}</td>
                          <td className="py-sm" style={{ color: RISK_COLORS[frame.risk_level as keyof typeof RISK_COLORS] }}>
                            {frame.risk_level}
                          </td>
                          <td className="py-sm">{frame.confidence.toFixed(1)}%</td>
                          <td className="py-sm">
                            <button
                              className="text-xs text-primary hover:underline"
                              onClick={() => seekToFrame(frame)}
                            >
                              Jump to Frame
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          )}
          </div>
        </div>
      </section>
    </div>
  );
}
