import { useCallback, useEffect, useRef, useState } from 'react';
import { Upload, Camera, CameraOff, AlertTriangle, CheckCircle2, Brain, Loader2, Video } from 'lucide-react';

interface PersonResult {
  person_id: number;
  confidence: number;
  risk_level: string;
  risk_score: number;
  task: string;
  keypoints_detected: number;
  features?: Record<string, number>;
}

interface DetectionResult {
  image_width: number;
  image_height: number;
  persons: PersonResult[];
  person_count: number;
  annotated_image: string;
  model_used: string;
}

export default function YoloDemoPage() {
  const [result, setResult] = useState<DetectionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);

  // Webcam state
  const [webcamActive, setWebcamActive] = useState(false);
  const [webcamError, setWebcamError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [webcamFps, setWebcamFps] = useState(0);
  const frameCountRef = useRef(0);
  const fpsStartRef = useRef(Date.now());

  const runDetection = useCallback(async (file: File) => {
    setLoading(true);
    setError(null);
    setResult(null);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const resp = await fetch('/cloud-api/cloud/inference/detect', { method: 'POST', body: formData });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Detection failed' }));
        throw new Error(err.detail || 'Detection failed');
      }
      const data: DetectionResult = await resp.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Detection failed');
    } finally {
      setLoading(false);
    }
  }, []);

  // Webcam capture loop
  const startWebcam = async () => {
    setWebcamError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'environment' },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setWebcamActive(true);
      fpsStartRef.current = Date.now();
      frameCountRef.current = 0;

      // Capture frames every 250ms (4 FPS inference)
      intervalRef.current = setInterval(async () => {
        if (!videoRef.current || videoRef.current.readyState < 2) return;
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        canvas.width = videoRef.current.videoWidth || 640;
        canvas.height = videoRef.current.videoHeight || 480;
        ctx.drawImage(videoRef.current, 0, 0);

        // Convert to blob and send
        canvas.toBlob(async (blob) => {
          if (!blob) return;
          try {
            const formData = new FormData();
            formData.append('file', blob, 'frame.jpg');
            const resp = await fetch('/cloud-api/cloud/inference/detect', { method: 'POST', body: formData });
            if (resp.ok) {
              const data: DetectionResult = await resp.json();
              setResult(data);
            }
          } catch {
            // Ignore frame errors in webcam mode
          }
          frameCountRef.current++;
          const elapsed = (Date.now() - fpsStartRef.current) / 1000;
          if (elapsed >= 1) {
            setWebcamFps(Math.round(frameCountRef.current / elapsed));
            frameCountRef.current = 0;
            fpsStartRef.current = Date.now();
          }
        }, 'image/jpeg', 0.7);
      }, 250);
    } catch (err: any) {
      setWebcamError(err.name === 'NotAllowedError'
        ? 'Camera access denied. Please allow camera permissions.'
        : err.name === 'NotFoundError'
        ? 'No camera found. Connect a webcam or use image upload.'
        : `Camera error: ${err.message}`);
    }
  };

  const stopWebcam = () => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    setWebcamActive(false);
    setWebcamFps(0);
  };

  useEffect(() => {
    return () => { stopWebcam(); };
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
      runDetection(file);
    }
  }, [runDetection]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      runDetection(file);
    }
  }, [runDetection]);

  const riskColor = (level: string) => {
    switch (level) {
      case 'HIGH': return 'text-red-400 bg-red-500/10 border-red-500/30';
      case 'MEDIUM': return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
      case 'LOW': return 'text-green-400 bg-green-500/10 border-green-500/30';
      default: return 'text-slate-400 bg-slate-500/10 border-slate-500/30';
    }
  };

  const riskDot = (level: string) => {
    switch (level) {
      case 'HIGH': return 'bg-red-500';
      case 'MEDIUM': return 'bg-amber-500';
      case 'LOW': return 'bg-green-500';
      default: return 'bg-slate-500';
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="rounded-lg bg-primary/10 p-2">
          <Camera className="h-6 w-6 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">YOLO Demo</h1>
          <p className="text-sm text-slate-400">
            Upload a factory floor image to see real-time pose detection and ergonomic risk scoring
          </p>
        </div>
      </div>

      {/* Mode Tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => { stopWebcam(); }}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${!webcamActive ? 'bg-primary/20 text-primary border border-primary/30' : 'bg-white/5 text-slate-400 border border-white/10 hover:bg-white/10'}`}
        >
          <Upload className="w-4 h-4" /> Image Upload
        </button>
        <button
          onClick={webcamActive ? stopWebcam : startWebcam}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${webcamActive ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-white/5 text-slate-400 border border-white/10 hover:bg-white/10'}`}
        >
          {webcamActive ? <CameraOff className="w-4 h-4" /> : <Video className="w-4 h-4" />}
          {webcamActive ? 'Stop Camera' : 'Live Webcam'}
        </button>
        {webcamActive && (
          <span className="flex items-center gap-2 px-3 py-2 text-xs text-green-400">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            LIVE — {webcamFps} FPS
          </span>
        )}
      </div>

      {/* Hidden canvas for frame capture */}
      <canvas ref={canvasRef} className="hidden" />

      {/* Webcam Error */}
      {webcamError && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/10 p-4 text-amber-400">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          <span className="text-sm">{webcamError}</span>
        </div>
      )}

      {/* Webcam Live View */}
      {webcamActive && (
        <div className="relative rounded-xl border border-white/10 bg-black overflow-hidden">
          <video
            ref={videoRef}
            className="w-full rounded-xl"
            style={{ transform: 'scaleX(-1)' }}
            playsInline
            muted
          />
          {/* Annotated overlay */}
          {result && result.annotated_image && (
            <img
              src={result.annotated_image}
              alt="YOLO detection"
              className="absolute inset-0 w-full h-full object-contain pointer-events-none"
              style={{ transform: 'scaleX(-1)' }}
            />
          )}
          {/* Live badge */}
          <div className="absolute top-3 left-3 flex items-center gap-2 bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-lg border border-red-500/30">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-[10px] font-bold text-red-400 uppercase">Live Analysis</span>
          </div>
          {/* Person count */}
          {result && (
            <div className="absolute top-3 right-3 bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-lg border border-white/10">
              <span className="text-[10px] text-white">{result.person_count} worker{result.person_count !== 1 ? 's' : ''} detected</span>
            </div>
          )}
        </div>
      )}

      {/* Upload Area (only when webcam is off) */}
      {!webcamActive && (
        <div
          ref={dropRef}
          onDrop={handleDrop}
          onDragOver={e => e.preventDefault()}
          onClick={() => fileInputRef.current?.click()}
          className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-white/10 bg-white/5 p-12 transition-colors hover:border-primary/40 hover:bg-primary/5"
        >
          <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
          {loading ? (
            <Loader2 className="mb-3 h-10 w-10 animate-spin text-primary" />
          ) : (
            <Upload className="mb-3 h-10 w-10 text-slate-500" />
          )}
          <p className="text-sm text-slate-400">
            {loading ? 'Running YOLO inference...' : 'Drop an image or click to upload'}
          </p>
          <p className="mt-1 text-xs text-slate-600">JPEG, PNG — factory floor, workstation, or warehouse images</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-4 text-red-400">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Summary Bar */}
          <div className="flex items-center gap-4 rounded-xl border border-white/10 bg-white/5 p-4">
            <Brain className="h-5 w-5 text-primary" />
            <span className="text-sm text-slate-400">
              Model: <span className="text-white">{result.model_used}</span>
            </span>
            <span className="text-slate-600">|</span>
            <span className="text-sm text-slate-400">
              Detected: <span className="font-bold text-white">{result.person_count}</span> person{result.person_count !== 1 ? 's' : ''}
            </span>
            <span className="text-slate-600">|</span>
            <span className="text-sm text-slate-400">
              Resolution: <span className="text-white">{result.image_width}×{result.image_height}</span>
            </span>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* Annotated Image */}
            <div className="rounded-xl border border-white/10 bg-white/5 p-2">
              <img
                src={result.annotated_image}
                alt="YOLO detection result"
                className="w-full rounded-lg"
              />
            </div>

            {/* Person Details */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-300">Detected Workers</h3>
              {result.persons.length === 0 ? (
                <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-4 text-amber-400 text-sm">
                  No persons detected. Try a clearer image with visible workers.
                </div>
              ) : (
                result.persons.map(person => (
                  <div
                    key={person.person_id}
                    className="rounded-xl border border-white/10 bg-white/5 p-4"
                  >
                    <div className="mb-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className={`h-2 w-2 rounded-full ${riskDot(person.risk_level)}`} />
                        <span className="font-semibold text-white">
                          Worker #{person.person_id + 1}
                        </span>
                      </div>
                      <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${riskColor(person.risk_level)}`}>
                        {person.risk_level}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <span className="text-slate-500">Risk Score</span>
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 flex-1 rounded-full bg-white/10">
                            <div
                              className={`h-full rounded-full ${riskDot(person.risk_level)}`}
                              style={{ width: `${person.risk_score}%` }}
                            />
                          </div>
                          <span className="font-mono text-xs text-slate-300">
                            {person.risk_score.toFixed(0)}
                          </span>
                        </div>
                      </div>
                      <div>
                        <span className="text-slate-500">Task</span>
                        <div className="font-medium text-white">{person.task}</div>
                      </div>
                      <div>
                        <span className="text-slate-500">Confidence</span>
                        <div className="font-mono text-white">{(person.confidence * 100).toFixed(1)}%</div>
                      </div>
                      <div>
                        <span className="text-slate-500">Keypoints</span>
                        <div className="font-mono text-white">{person.keypoints_detected}/17</div>
                      </div>
                    </div>

                    {/* Key Features */}
                    {person.features && Object.keys(person.features).length > 0 && (
                      <div className="mt-3 border-t border-white/5 pt-2">
                        <span className="text-xs text-slate-500">Ergonomic Features</span>
                        <div className="mt-1 grid grid-cols-2 gap-1 text-xs">
                          {Object.entries(person.features)
                            .filter(([_, v]) => v !== 0 && !isNaN(v))
                            .slice(0, 6)
                            .map(([k, v]) => (
                              <div key={k} className="flex justify-between">
                                <span className="text-slate-400">{k.replace(/_/g, ' ')}</span>
                                <span className="font-mono text-slate-300">{typeof v === 'number' ? v.toFixed(1) : v}</span>
                              </div>
                            ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!result && !loading && !error && (
        <div className="rounded-xl border border-white/10 bg-white/5 p-8 text-center">
          <CheckCircle2 className="mx-auto mb-3 h-8 w-8 text-slate-600" />
          <p className="text-sm text-slate-400">
            Upload a factory floor image to see the YOLO cloud core in action
          </p>
          <p className="mt-1 text-xs text-slate-600">
            The model will detect workers, classify their posture, and score ergonomic risk
          </p>
        </div>
      )}
    </div>
  );
}
