import { useState, useEffect, useRef, useCallback } from 'react';
import { Camera, CameraOff, AlertTriangle, CheckCircle2, Clock3, Zap } from 'lucide-react';

interface Keypoint {
  x: number;
  y: number;
  z: number;
  visibility: number;
}

interface DetectResult {
  pose_detected: boolean;
  keypoints: Keypoint[];
  features: Record<string, number>;
  risk_level: string;
  task_label: string;
  risk_score: number;
  task_confidence: number;
  inference_ms: number;
}

const POSE_CONNECTIONS: [number, number][] = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
  [11, 23], [12, 24], [23, 24], [23, 25], [24, 26],
  [25, 27], [26, 28], [27, 29], [28, 30], [29, 31], [30, 32],
  [0, 1], [1, 2], [2, 3], [0, 4], [4, 5], [5, 6], [9, 10],
];

const RISK_COLORS: Record<string, string> = {
  LOW: '#22c55e',
  MEDIUM: '#f59e0b',
  HIGH: '#ef4444',
  UNKNOWN: '#6b7280',
};

export default function WebCamDemo() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [streaming, setStreaming] = useState(false);
  const [result, setResult] = useState<DetectResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fps, setFps] = useState(0);
  const frameCount = useRef(0);
  const lastFpsTime = useRef(Date.now());
  const animFrameRef = useRef<number>(0);
  const processingRef = useRef(false);

  const detectFrame = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current || processingRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (video.readyState < 2) return;

    processingRef.current = true;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) { processingRef.current = false; return; }

    ctx.drawImage(video, 0, 0);
    const imageData = canvas.toDataURL('image/jpeg', 0.6).split(',')[1];

    try {
      const resp = await fetch('/api/webcam/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageData, width: video.videoWidth, height: video.videoHeight }),
      });
      if (resp.ok) {
        const data: DetectResult = await resp.json();
        setResult(data);
        if (data.pose_detected && data.keypoints.length > 0) {
          drawPose(ctx, data.keypoints, video.videoWidth, video.videoHeight, data.risk_level);
        }
        frameCount.current++;
        const now = Date.now();
        if (now - lastFpsTime.current >= 1000) {
          setFps(frameCount.current);
          frameCount.current = 0;
          lastFpsTime.current = now;
        }
      }
    } catch {
      // retry next frame
    }
    processingRef.current = false;
  }, []);

  const drawPose = (ctx: CanvasRenderingContext2D, keypoints: Keypoint[], w: number, h: number, riskLevel: string) => {
    const color = RISK_COLORS[riskLevel] || '#6b7280';
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    for (const [i, j] of POSE_CONNECTIONS) {
      if (i < keypoints.length && j < keypoints.length) {
        const a = keypoints[i];
        const b = keypoints[j];
        if (a.visibility > 0.5 && b.visibility > 0.5) {
          ctx.beginPath();
          ctx.moveTo(a.x * w, a.y * h);
          ctx.lineTo(b.x * w, b.y * h);
          ctx.stroke();
        }
      }
    }
    for (const kp of keypoints) {
      if (kp.visibility > 0.5) {
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(kp.x * w, kp.y * h, 4, 0, 2 * Math.PI);
        ctx.fill();
      }
    }
  };

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
        setStreaming(true);
        setError(null);
      }
    } catch {
      setError('Camera access denied. Please allow camera permissions.');
    }
  };

  const stopCamera = () => {
    if (videoRef.current?.srcObject) {
      const tracks = (videoRef.current.srcObject as MediaStream).getTracks();
      tracks.forEach((t) => t.stop());
      videoRef.current.srcObject = null;
    }
    setStreaming(false);
    setResult(null);
    cancelAnimationFrame(animFrameRef.current);
  };

  useEffect(() => {
    if (!streaming) return;
    let running = true;
    const loop = () => {
      if (!running) return;
      detectFrame();
      animFrameRef.current = requestAnimationFrame(loop);
    };
    animFrameRef.current = requestAnimationFrame(loop);
    return () => { running = false; cancelAnimationFrame(animFrameRef.current); };
  }, [streaming, detectFrame]);

  useEffect(() => () => stopCamera(), []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Camera className="w-6 h-6 text-cyan-400" />
            Live Webcam Demo
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time pose detection and ergonomic risk assessment using your webcam
          </p>
        </div>
        <button
          onClick={streaming ? stopCamera : startCamera}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
            streaming
              ? 'bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30'
              : 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/30'
          }`}
        >
          {streaming ? <CameraOff className="w-4 h-4" /> : <Camera className="w-4 h-4" />}
          {streaming ? 'Stop Camera' : 'Start Camera'}
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">{error}</div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="relative bg-black rounded-xl overflow-hidden border border-white/10">
            <video ref={videoRef} className="w-full rounded-xl" playsInline muted
              style={{ display: streaming ? 'block' : 'none' }} />
            <canvas ref={canvasRef}
              className="absolute top-0 left-0 w-full h-full pointer-events-none"
              style={{ display: streaming ? 'block' : 'none' }} />
            {!streaming && (
              <div className="flex flex-col items-center justify-center h-[400px] text-slate-500">
                <Camera className="w-16 h-16 mb-4 opacity-30" />
                <p className="text-lg">Click &quot;Start Camera&quot; to begin</p>
                <p className="text-sm mt-2 opacity-60">Your camera feed stays local — nothing is uploaded</p>
              </div>
            )}
            {streaming && (
              <div className="absolute top-3 right-3 bg-black/60 text-xs text-green-400 px-2 py-1 rounded flex items-center gap-1">
                <Zap className="w-3 h-3" /> {fps} FPS
              </div>
            )}
            {result?.pose_detected && (
              <div className="absolute top-3 left-3 px-3 py-1 rounded-lg text-sm font-bold text-white"
                style={{ backgroundColor: RISK_COLORS[result.risk_level] + 'cc' }}>
                {result.risk_level} RISK
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-white/5 rounded-xl border border-white/10 p-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" /> Risk Assessment
            </h3>
            {result?.pose_detected ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400 text-sm">Risk Level</span>
                  <span className="font-bold text-lg" style={{ color: RISK_COLORS[result.risk_level] }}>
                    {result.risk_level}
                  </span>
                </div>
                <div className="w-full bg-white/10 rounded-full h-2">
                  <div className="h-2 rounded-full transition-all duration-300"
                    style={{ width: `${result.risk_score}%`, backgroundColor: RISK_COLORS[result.risk_level] }} />
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">Score</span>
                  <span className="text-white">{result.risk_score}/100</span>
                </div>
              </div>
            ) : (
              <p className="text-slate-500 text-sm">
                {streaming ? 'No pose detected — face the camera' : 'Start camera to begin'}
              </p>
            )}
          </div>

          <div className="bg-white/5 rounded-xl border border-white/10 p-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" /> Task Detection
            </h3>
            {result?.pose_detected ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400 text-sm">Activity</span>
                  <span className="text-white font-medium">{result.task_label}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">Confidence</span>
                  <span className="text-cyan-400">{result.task_confidence.toFixed(0)}%</span>
                </div>
              </div>
            ) : <p className="text-slate-500 text-sm">—</p>}
          </div>

          <div className="bg-white/5 rounded-xl border border-white/10 p-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
              <Clock3 className="w-4 h-4" /> Performance
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Inference</span>
                <span className="text-white">{result?.inference_ms ?? 0}ms</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">FPS</span>
                <span className="text-white">{fps}</span>
              </div>
            </div>
          </div>

          {result?.pose_detected && Object.keys(result.features).length > 0 && (
            <div className="bg-white/5 rounded-xl border border-white/10 p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">Key Features</h3>
              <div className="space-y-1 text-xs">
                {['neck_flexion', 'trunk_flexion', 'knee_angle', 'shoulder_symmetry'].map((key) => (
                  <div key={key} className="flex justify-between">
                    <span className="text-slate-400">{key.replace(/_/g, ' ')}</span>
                    <span className="text-white">{(result.features[key] ?? 0).toFixed(1)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
