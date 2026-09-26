import { useRef, useState, useCallback, useEffect } from 'react';
import { Camera, X, Check, RotateCcw, Video, VideoOff } from 'lucide-react';

interface CameraCaptureProps {
  onCapture: (blob: Blob) => void;
  onClose: () => void;
  title?: string;
}

export default function CameraCapture({ onCapture, onClose, title = 'Capture Face Photo' }: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [captured, setCaptured] = useState<string | null>(null);
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cameraReady, setCameraReady] = useState(false);

  const startCamera = useCallback(async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
        audio: false,
      });
      setStream(mediaStream);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        videoRef.current.onloadedmetadata = () => {
          setCameraReady(true);
        };
      }
    } catch (err) {
      setError('Camera access denied. Please allow camera permissions.');
      console.error('Camera error:', err);
    }
  }, []);

  useEffect(() => {
    startCamera();
    return () => {
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  const capturePhoto = () => {
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Mirror the image for selfie view
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0);
    ctx.setTransform(1, 0, 0, 1, 0, 0);

    const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
    setCaptured(dataUrl);

    canvas.toBlob((blob) => {
      if (blob) setCapturedBlob(blob);
    }, 'image/jpeg', 0.9);
  };

  const retake = () => {
    setCaptured(null);
    setCapturedBlob(null);
  };

  const confirmCapture = () => {
    if (capturedBlob) {
      onCapture(capturedBlob);
    }
  };

  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
      <div className="bg-surface-container rounded-2xl border border-outline-variant/30 shadow-2xl max-w-[32rem] w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-outline-variant/20">
          <div className="flex items-center gap-2">
            <Camera className="w-5 h-5 text-primary" />
            <h3 className="text-lg font-semibold text-on-surface">{title}</h3>
          </div>
          <button onClick={stopCamera} className="p-1 rounded-lg hover:bg-surface-container-highest transition-colors">
            <X className="w-5 h-5 text-on-surface-variant" />
          </button>
        </div>

        {/* Camera / Preview */}
        <div className="relative aspect-[4/3] bg-black">
          {error ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6">
              <VideoOff className="w-12 h-12 text-red-400" />
              <p className="text-sm text-red-400 text-center">{error}</p>
              <button
                onClick={startCamera}
                className="px-4 py-2 rounded-lg bg-primary text-on-primary text-sm font-medium hover:bg-primary/90 transition"
              >
                Try Again
              </button>
            </div>
          ) : captured ? (
            <img src={captured} alt="Captured" className="w-full h-full object-cover" />
          ) : (
            <>
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full h-full object-cover"
                style={{ transform: 'scaleX(-1)' }}
              />
              {!cameraReady && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                    <p className="text-sm text-white/70">Starting camera...</p>
                  </div>
                </div>
              )}
              {/* Face guide overlay */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="w-48 h-48 rounded-full border-2 border-dashed border-white/30" />
              </div>
            </>
          )}
          <canvas ref={canvasRef} className="hidden" />
        </div>

        {/* Controls */}
        <div className="flex items-center justify-center gap-4 p-4 bg-surface-container-low">
          {captured ? (
            <>
              <button
                onClick={retake}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-container-highest text-on-surface text-sm font-medium hover:bg-outline-variant/30 transition"
              >
                <RotateCcw className="w-4 h-4" />
                Retake
              </button>
              <button
                onClick={confirmCapture}
                className="flex items-center gap-2 px-6 py-2 rounded-lg bg-primary text-on-primary text-sm font-medium hover:bg-primary/90 transition"
              >
                <Check className="w-4 h-4" />
                Use Photo
              </button>
            </>
          ) : (
            <button
              onClick={capturePhoto}
              disabled={!cameraReady || !!error}
              className="flex items-center gap-2 px-6 py-3 rounded-full bg-primary text-on-primary text-sm font-medium hover:bg-primary/90 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="w-8 h-8 rounded-full border-2 border-on-primary flex items-center justify-center">
                <div className="w-6 h-6 rounded-full bg-on-primary" />
              </div>
              Capture
            </button>
          )}
        </div>

        {/* Tips */}
        <div className="px-4 pb-4">
          <p className="text-xs text-on-surface-variant text-center">
            Position face within the circle. Ensure good lighting. Remove glasses if possible.
          </p>
        </div>
      </div>
    </div>
  );
}
