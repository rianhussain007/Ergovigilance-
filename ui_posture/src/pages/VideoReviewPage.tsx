import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Eye, EyeOff, FileVideo, Sparkles, UploadCloud } from "lucide-react";
import { analyzeVideo } from "@/src/services/dashboardService";
import type { VideoAnalysisResponse, VideoAnalysisFrame } from "@/src/types/api";

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

function drawSkeleton(
  ctx: CanvasRenderingContext2D,
  frame: VideoAnalysisFrame,
  canvasWidth: number,
  canvasHeight: number
): void {
  if (!frame.keypoints || frame.keypoints.length === 0) return;

  ctx.clearRect(0, 0, canvasWidth, canvasHeight);
  const color = RISK_COLORS[frame.risk_level as keyof typeof RISK_COLORS];

  // Draw connections
  for (const [startIdx, endIdx] of POSE_CONNECTIONS) {
    if (startIdx < frame.keypoints.length && endIdx < frame.keypoints.length) {
      const startKp = frame.keypoints[startIdx];
      const endKp = frame.keypoints[endIdx];
      if (startKp.length >= 2 && endKp.length >= 2) {
        const x1 = startKp[0] * canvasWidth;
        const y1 = startKp[1] * canvasHeight;
        const x2 = endKp[0] * canvasWidth;
        const y2 = endKp[1] * canvasHeight;
        const visibility = Math.min(
          startKp[3] !== undefined ? startKp[3] : 1.0,
          endKp[3] !== undefined ? endKp[3] : 1.0
        );
        ctx.globalAlpha = 0.3 + visibility * 0.7;
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        ctx.lineCap = "round";
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
        ctx.globalAlpha = 1.0;
      }
    }
  }

  // Draw joints
  for (let i = 0; i < Math.min(frame.keypoints.length, 33); i++) {
    const kp = frame.keypoints[i];
    if (kp.length >= 2) {
      const x = kp[0] * canvasWidth;
      const y = kp[1] * canvasHeight;
      const visibility = kp[3] !== undefined ? kp[3] : 1.0;
      ctx.globalAlpha = 0.3 + visibility * 0.7;
      ctx.beginPath();
      ctx.fillStyle = color;
      ctx.arc(x, y, 7, 0, 2 * Math.PI);
      ctx.fill();
      ctx.globalAlpha = 1.0;
    }
  }

  // Draw per-joint angle labels (simplified, just neck, trunk, shoulders, knee)
  const labelConfigs: Array<[string, number, [number, number]]> = [
    ["neck_flexion", 0, [-25, -25]],
    ["trunk_flexion", 23, [25, -15]],
    ["left_shoulder_elev", 11, [-25, -20]],
    ["right_shoulder_elev", 12, [25, -20]],
    ["knee_angle", 25, [25, 10]],
  ];

  ctx.font = "12px sans-serif";
  ctx.fillStyle = "white";
  ctx.textBaseline = "middle";

  for (const [feat, kpIdx, offset] of labelConfigs) {
    if (
      kpIdx >= frame.keypoints.length ||
      frame.unavailable_features.includes(feat)
    )
      continue;
    const value = frame.features[feat];
    if (value === undefined || value !== value) continue;
    const kp = frame.keypoints[kpIdx];
    const x = kp[0] * canvasWidth + offset[0];
    const y = kp[1] * canvasHeight + offset[1];
    ctx.fillStyle = "rgba(8, 12, 18, 0.9)";
    const text = `${value.toFixed(1)}`;
    const metrics = ctx.measureText(text);
    ctx.fillRect(x - 4, y - 8, metrics.width + 8, 16);
    ctx.fillStyle = color;
    ctx.fillText(text, x, y);
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
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="text-on-surface-variant">{level}</span>
        <span className="font-mono text-on-surface">{value.toFixed(1)}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded bg-surface-container-highest">
        <div
          className="h-full rounded transition-all"
          style={{
            width: `${Math.max(0, Math.min(100, value))}%`,
            backgroundColor: RISK_COLORS[level],
          }}
        />
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
  const [showOverlay, setShowOverlay] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [hoverTime, setHoverTime] = useState<number | null>(null);

  const riskPath = useMemo(() => buildRiskPath(result!), [result]);
  const timeLabels = useMemo(() => buildTimeLabels(result!), [result]);

  // Helper 1: find current frame
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

  const currentFrame = useMemo(() => findCurrentFrame(currentTime), [
    currentTime,
    findCurrentFrame,
  ]);

  const handleTimeUpdate = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    setCurrentTime(video.currentTime);
    if (!result || !showOverlay) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    if (currentFrame) {
      drawSkeleton(ctx, currentFrame, canvas.width, canvas.height);
    } else {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }, [result, showOverlay, currentFrame]);

  const handleVideoLoadedMetadata = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width = video.clientWidth;
    canvas.height = video.clientHeight;
  }, []);

  const handleChartClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!videoRef.current || !result) return;
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const chartLeft = CHART_PADDING.left;
    const chartRight = CHART_WIDTH - CHART_PADDING.right;
    const maxTime = Math.max(...result.frames.map((f) => f.timestamp_seconds), 1);
    const ratio = (x - chartLeft) / (chartRight - chartLeft);
    const time = Math.max(0, Math.min(maxTime, ratio * maxTime));
    videoRef.current.currentTime = time;
    setCurrentTime(time);
  };

  const handleChartMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!result) return;
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const chartLeft = CHART_PADDING.left;
    const chartRight = CHART_WIDTH - CHART_PADDING.right;
    const maxTime = Math.max(...result.frames.map((f) => f.timestamp_seconds), 1);
    const ratio = (x - chartLeft) / (chartRight - chartLeft);
    const time = Math.max(0, Math.min(maxTime, ratio * maxTime));
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

  const chooseFile = (file: File | null) => {
    setError(null);
    setResult(null);
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

  const handleAnalyze = async () => {
    if (!selectedFile || status === "processing") return;
    setError(null);
    setResult(null);
    setStatus("processing");
    try {
      const data = await analyzeVideo(selectedFile);
      setResult(data);
      setStatus("complete");
    } catch (err) {
      setStatus("idle");
      setError(err instanceof Error ? err.message : "Video analysis failed");
    }
  };

  return (
    <div className="p-lg space-y-lg pb-32">
      <div className="flex flex-wrap items-end justify-between gap-md">
        <div>
          <h1 className="text-display-lg font-bold text-on-surface">Video Analysis</h1>
          <p className="mt-xs text-body-sm text-on-surface-variant">
            Upload a video to compute real posture risk over time from the existing pose pipeline.
          </p>
        </div>
        <a
          href="/sessions"
          className="rounded-lg border border-dashed border-outline-variant bg-surface-container px-md py-sm text-right no-underline transition hover:bg-surface-container-low"
        >
          <p className="font-label-caps text-[10px] text-on-surface-variant">Live Session Replay</p>
          <p className="font-label-mono text-body-sm text-primary">Go to Sessions →</p>
        </a>
      </div>

      <section className="grid grid-cols-1 gap-lg xl:grid-cols-[420px_minmax(0,1fr)]">
        <div className="flex flex-col rounded-lg border border-outline-variant bg-surface-container p-lg">
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
            <div className="mt-lg rounded-lg border border-primary/30 bg-primary/10 p-md">
              <div className="flex items-center gap-sm text-body-sm text-primary">
                <div className="h-4 w-4 animate-pulse rounded-full bg-primary" />
                Processing sampled frames through PoseEngine + Context Intelligence.
              </div>
            </div>
          )}

          {error && (
            <div className="mt-lg rounded-lg border border-error/40 bg-error/10 p-md text-body-sm text-error">
              {error}
            </div>
          )}
        </div>

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
              {result.summary.all_unavailable_features.length > 0 && (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-md">
                  <div className="flex items-start gap-sm">
                    <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
                    <div>
                      <h3 className="text-body-sm font-semibold text-amber-500">Partial Analysis</h3>
                      <p className="text-body-sm text-on-surface-variant mt-1">
                        This video's framing didn't capture the full body. {result.summary.frames_with_unavailable_features.toFixed(0)}% of frames have missing features.
                        <br />
                        Unavailable: {result.summary.all_unavailable_features.map(f => FEATURE_LABELS[f] || f).join(", ")}
                      </p>
                    </div>
                  </div>
                </div>
              )}

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
                  <div className="flex items-center gap-sm rounded-lg border border-green-400/30 bg-green-400/10 px-md py-sm text-body-sm text-green-400">
                    <CheckCircle2 className="h-4 w-4" />
                    Real computed results
                  </div>
                </div>
              </div>

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
                        className="w-full max-h-[500px]"
                        onTimeUpdate={handleTimeUpdate}
                        onLoadedMetadata={handleVideoLoadedMetadata}
                        onSeeked={handleTimeUpdate}
                        onPlay={handleTimeUpdate}
                      />
                      {showOverlay && currentFrame && (
                        <canvas
                          ref={canvasRef}
                          className="absolute top-0 left-0 w-full h-full pointer-events-none"
                          style={{ objectFit: "contain" }}
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
                          {currentFrame.unavailable_features.includes(feat) ||
                          currentFrame.features[feat] !== currentFrame.features[feat] ? (
                            <span className="text-sm text-on-surface-variant font-mono">—</span>
                          ) : (
                            <span className="text-sm text-on-surface font-mono">
                              {currentFrame.features[feat].toFixed(1)}
                            </span>
                          )}
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
                    <line x1={CHART_PADDING.left} y1={CHART_PADDING.top} x2={CHART_PADDING.left} y2={CHART_HEIGHT - CHART_PADDING.bottom} stroke="#424754" />
                    <line x1={CHART_PADDING.left} y1={CHART_HEIGHT - CHART_PADDING.bottom} x2={CHART_WIDTH - CHART_PADDING.right} y2={CHART_HEIGHT - CHART_PADDING.bottom} stroke="#424754" />
                    <text x={CHART_PADDING.left - 10} y={CHART_PADDING.top + 5} fill="#c2c6d6" fontSize="12" textAnchor="end">HIGH</text>
                    <text x={CHART_PADDING.left - 10} y={(CHART_HEIGHT - CHART_PADDING.bottom - CHART_PADDING.top)/2 + CHART_PADDING.top + 5} fill="#c2c6d6" fontSize="12" textAnchor="end">MED</text>
                    <text x={CHART_PADDING.left - 10} y={CHART_HEIGHT - CHART_PADDING.bottom - 5} fill="#c2c6d6" fontSize="12" textAnchor="end">LOW</text>

                    {/* Risk Path */}
                    {riskPath && <path d={riskPath} fill="none" stroke="#adc6ff" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />}

                    {/* Time Labels */}
                    {timeLabels.map((tick, i) => (
                      <g key={i}>
                        <line x1={tick.x} y1={CHART_HEIGHT - CHART_PADDING.bottom} x2={tick.x} y2={CHART_HEIGHT - CHART_PADDING.bottom + 10} stroke="#424754" strokeWidth="1" />
                        <text x={tick.x} y={CHART_HEIGHT - CHART_PADDING.bottom + 25} fill="#c2c6d6" fontSize="10" textAnchor="middle">{tick.label}</text>
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
                          stroke="#ffffff"
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
                    {Object.entries(result.summary.average_features).map(([name, value]) => (
                      <div
                        key={name}
                        className="flex items-center justify-between gap-md border-b border-outline-variant/60 pb-xs"
                      >
                        <span className="text-body-sm text-on-surface-variant">{FEATURE_LABELS[name] || name}</span>
                        <span className="font-label-mono text-body-sm text-on-surface">{(value ?? 0).toFixed(1)}</span>
                      </div>
                    ))}
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
      </section>
    </div>
  );
}
