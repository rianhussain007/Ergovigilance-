import { useEffect, useRef, useState } from 'react';

/**
 * Animated pose-skeleton overlay for the landing page hero.
 *
 * Draws a stylized person silhouette with MediaPipe-style 33 landmarks
 * and colored connecting lines (green LOW, amber MEDIUM, red HIGH) that
 * pulse and shift to demonstrate the system actively monitoring posture
 * risk in real time.
 */

// Simplified skeleton landmark positions (normalized 0-1) — upper body
// focus since that's what the camera sees most in a factory workstation.
const LANDMARKS = [
  // Head / face (0-10)
  { x: 0.50, y: 0.08 }, // 0 nose
  { x: 0.48, y: 0.06 }, // 1 left eye inner
  { x: 0.46, y: 0.06 }, // 2 left eye
  { x: 0.44, y: 0.07 }, // 3 left eye outer
  { x: 0.52, y: 0.06 }, // 4 right eye inner
  { x: 0.54, y: 0.06 }, // 5 right eye
  { x: 0.56, y: 0.07 }, // 6 right eye outer
  { x: 0.43, y: 0.09 }, // 7 left ear
  { x: 0.57, y: 0.09 }, // 8 right ear
  { x: 0.47, y: 0.10 }, // 9 mouth left
  { x: 0.53, y: 0.10 }, // 10 mouth right
  // Shoulders (11-12)
  { x: 0.38, y: 0.18 }, // 11 left shoulder
  { x: 0.62, y: 0.18 }, // 12 right shoulder
  // Left arm (13, 15, 17, 19, 21)
  { x: 0.32, y: 0.28 }, // 13 left elbow
  // Right arm (14, 16, 18, 20, 22)
  { x: 0.68, y: 0.28 }, // 14 right elbow
  { x: 0.28, y: 0.38 }, // 15 left wrist
  { x: 0.72, y: 0.38 }, // 16 right wrist
  // Hips (23-24)
  { x: 0.42, y: 0.48 }, // 23 left hip
  { x: 0.58, y: 0.48 }, // 24 right hip
  // Left leg (25, 27, 29, 31)
  { x: 0.43, y: 0.60 }, // 25 left knee
  // Right leg (26, 28, 30, 32)
  { x: 0.57, y: 0.60 }, // 26 right knee
];

// Connections with region coloring
const CONNECTIONS: [number, number, string][] = [
  // Face
  [0, 1, 'head'], [1, 2, 'head'], [2, 3, 'head'],
  [0, 4, 'head'], [4, 5, 'head'], [5, 6, 'head'],
  [9, 10, 'head'],
  // Torso
  [11, 12, 'torso'],
  [11, 23, 'torso'], [12, 24, 'torso'],
  [23, 24, 'torso'],
  // Left arm
  [11, 13, 'left_arm'], [13, 15, 'left_arm'],
  // Right arm
  [12, 14, 'right_arm'], [14, 16, 'right_arm'],
  // Left leg
  [23, 25, 'left_leg'],
  // Right leg
  [24, 26, 'right_leg'],
];

const REGION_COLORS: Record<string, { low: string; med: string; high: string }> = {
  head:      { low: '#4ade80', med: '#fbbf24', high: '#f87171' },
  torso:     { low: '#4ade80', med: '#fb923c', high: '#ef4444' },
  left_arm:  { low: '#4ade80', med: '#fbbf24', high: '#f87171' },
  right_arm: { low: '#4ade80', med: '#fb923c', high: '#ef4444' },
  left_leg:  { low: '#4ade80', med: '#fbbf24', high: '#f87171' },
  right_leg: { low: '#4ade80', med: '#fbbf24', high: '#f87171' },
};

// Risk state sequence — cycles through LOW → MEDIUM → HIGH → LOW
const RISK_STATES = ['low', 'low', 'low', 'low', 'low', 'med', 'med', 'high', 'high', 'med', 'low', 'low', 'low', 'low', 'low'];

export default function LandingSkeleton({ className = '', height = 500 }: { className?: string; height?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [riskIdx, setRiskIdx] = useState(0);
  const animFrame = useRef<number>(0);
  const startTime = useRef(Date.now());

  useEffect(() => {
    const interval = setInterval(() => {
      setRiskIdx((prev) => (prev + 1) % RISK_STATES.length);
    }, 1800);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const draw = () => {
      const w = canvas.width;
      const h = canvas.height;
      const elapsed = (Date.now() - startTime.current) / 1000;

      ctx.clearRect(0, 0, w, h);

      // Subtle breathing animation — landmarks shift slightly
      const breathe = Math.sin(elapsed * 1.2) * 0.008;
      // Subtle pulse for the glow intensity
      const glowPulse = 0.12 + Math.sin(elapsed * 0.8) * 0.05;

      const currentRisk = RISK_STATES[riskIdx];

      // Draw connections
      for (const [a, b, region] of CONNECTIONS) {
        const la = LANDMARKS[a];
        const lb = LANDMARKS[b];
        if (!la || !lb) continue;

        const colors = REGION_COLORS[region];
        const color = colors[currentRisk as keyof typeof colors] || colors.low;

        const x1 = (la.x + breathe) * w;
        const y1 = (la.y + breathe * 0.5) * h;
        const x2 = (lb.x + breathe) * w;
        const y2 = (lb.y + breathe * 0.5) * h;

        // Outer glow layer
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.strokeStyle = color;
        ctx.globalAlpha = glowPulse * 0.5;
        ctx.lineWidth = 14;
        ctx.stroke();

        // Glow layer
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.strokeStyle = color;
        ctx.globalAlpha = glowPulse;
        ctx.lineWidth = 7;
        ctx.stroke();

        // Main line
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.strokeStyle = color;
        ctx.globalAlpha = 0.92;
        ctx.lineWidth = 2.5;
        ctx.stroke();
      }

      // Draw landmarks
      for (let i = 0; i < LANDMARKS.length; i++) {
        const lm = LANDMARKS[i];
        const x = (lm.x + breathe) * w;
        const y = (lm.y + breathe * 0.5) * h;

        const region = i <= 10 ? 'head' : i <= 12 ? 'torso' : i <= 16 ? (i % 2 === 1 ? 'left_arm' : 'right_arm') : 'torso';
        const colors = REGION_COLORS[region] || REGION_COLORS.torso;
        const landmarkColor = colors[currentRisk as keyof typeof colors] || colors.low;

        // Outer soft glow
        ctx.beginPath();
        ctx.arc(x, y, 8, 0, Math.PI * 2);
        ctx.fillStyle = landmarkColor;
        ctx.globalAlpha = 0.12;
        ctx.fill();

        // Core dot with crisp edge
        ctx.beginPath();
        ctx.arc(x, y, 3.5, 0, Math.PI * 2);
        ctx.fillStyle = landmarkColor;
        ctx.globalAlpha = 0.95;
        ctx.fill();

        // Inner highlight
        ctx.beginPath();
        ctx.arc(x, y, 1.5, 0, Math.PI * 2);
        ctx.fillStyle = '#fff';
        ctx.globalAlpha = 0.4;
        ctx.fill();
      }

      ctx.globalAlpha = 1;
      animFrame.current = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(animFrame.current);
  }, [riskIdx]);

  return (
    <canvas
      ref={canvasRef}
      width={400}
      height={height}
      className={`block ${className}`}
      style={{ imageRendering: 'auto' }}
    />
  );
}
