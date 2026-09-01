import { useEffect, useRef, useState } from 'react';

interface RiskGaugeProps {
  score: number; // 0-100
  level: string; // LOW, MEDIUM, HIGH
  size?: number; // px
  label?: string;
  showScore?: boolean;
  animated?: boolean;
}

const LEVEL_COLORS = {
  LOW: { arc: '#22c55e', glow: 'rgba(34,197,94,0.3)', text: 'text-green-400' },
  MEDIUM: { arc: '#f59e0b', glow: 'rgba(245,158,11,0.3)', text: 'text-amber-400' },
  HIGH: { arc: '#ef4444', glow: 'rgba(239,68,68,0.3)', text: 'text-red-400' },
  low: { arc: '#22c55e', glow: 'rgba(34,197,94,0.3)', text: 'text-green-400' },
  moderate: { arc: '#f59e0b', glow: 'rgba(245,158,11,0.3)', text: 'text-amber-400' },
  high: { arc: '#ef4444', glow: 'rgba(239,68,68,0.3)', text: 'text-red-400' },
} as Record<string, { arc: string; glow: string; text: string }>;

export function RiskGauge({
  score,
  level,
  size = 160,
  label = 'Risk Score',
  showScore = true,
  animated = true,
}: RiskGaugeProps) {
  const [displayScore, setDisplayScore] = useState(animated ? 0 : score);
  const animRef = useRef<number | null>(null);
  const prevScore = useRef(0);

  useEffect(() => {
    if (!animated) {
      setDisplayScore(score);
      return;
    }
    const start = prevScore.current;
    const end = score;
    const duration = 800;
    const startTime = Date.now();

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayScore(start + (end - start) * eased);
      if (progress < 1) {
        animRef.current = requestAnimationFrame(animate);
      } else {
        prevScore.current = end;
      }
    };

    animRef.current = requestAnimationFrame(animate);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [score, animated]);

  const colors = LEVEL_COLORS[level] || LEVEL_COLORS.LOW;
  const radius = (size - 20) / 2;
  const circumference = 2 * Math.PI * radius;
  const arcLength = circumference * 0.75; // 270 degrees
  const fillLength = arcLength * (displayScore / 100);
  const center = size / 2;

  // SVG arc path for 270-degree gauge
  const startAngle = 135; // degrees
  const endAngle = 405; // degrees
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const x1 = center + radius * Math.cos(toRad(startAngle));
  const y1 = center + radius * Math.sin(toRad(startAngle));
  const x2 = center + radius * Math.cos(toRad(endAngle));
  const y2 = center + radius * Math.sin(toRad(endAngle));

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Background arc */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={`${arcLength} ${circumference}`}
          transform={`rotate(${startAngle} ${center} ${center})`}
        />
        {/* Filled arc */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={colors.arc}
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={`${fillLength} ${circumference}`}
          transform={`rotate(${startAngle} ${center} ${center})`}
          style={{
            filter: `drop-shadow(0 0 6px ${colors.glow})`,
            transition: animated ? 'none' : 'stroke-dasharray 0.8s ease-out',
          }}
        />
        {/* Glow effect */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={colors.arc}
          strokeWidth={12}
          strokeLinecap="round"
          strokeDasharray={`${fillLength} ${circumference}`}
          transform={`rotate(${startAngle} ${center} ${center})`}
          opacity={0.15}
          style={{ filter: 'blur(4px)' }}
        />
      </svg>
      {/* Center content */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {showScore && (
          <span className={`text-3xl font-bold ${colors.text}`}>
            {Math.round(displayScore)}
          </span>
        )}
        <span className="text-[10px] text-slate-400 uppercase tracking-wider mt-0.5">{label}</span>
        <span className={`text-xs font-bold ${colors.text} mt-1`}>
          {level.toUpperCase()}
        </span>
      </div>
    </div>
  );
}

export default RiskGauge;
