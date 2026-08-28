import React from 'react';

/**
 * ErgoVigilance Logo — SVG component that adapts to dark/light theme.
 *
 * Props:
 *   - className: additional CSS classes (e.g. "h-10 w-auto")
 *   - variant: "auto" (default, follows theme), "dark" (for light bg), "light" (for dark bg)
 */
interface LogoProps {
  className?: string;
  variant?: 'auto' | 'dark' | 'light';
}

export default function Logo({ className = 'h-10 w-auto', variant = 'auto' }: LogoProps) {
  // When variant is "auto", use CSS to switch colors via currentColor and data-theme
  // When variant is forced, use explicit colors
  const isLight = variant === 'light' || variant === 'auto';

  // Shield colors
  const shieldStroke = isLight ? '#1e293b' : '#e2e8f0';
  const shieldFill = isLight ? 'none' : 'none';

  // Spine colors
  const spineFill = isLight ? '#3b82f6' : '#60a5fa';
  const spineInner = isLight ? '#93c5fd' : '#93c5fd';

  // Text colors
  const ergoColor = isLight ? '#3b82f6' : '#60a5fa';
  const vigilanceColor = isLight ? '#1e293b' : '#f1f5f9';

  return (
    <svg
      viewBox="0 0 320 100"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="ErgoVigilance"
    >
      {/* Shield outline */}
      <path
        d="M50 8 L8 28 L8 55 Q8 80 50 95 Q92 80 92 55 L92 28 Z"
        fill={shieldFill}
        stroke={shieldStroke}
        strokeWidth="5"
      />

      {/* Inner shield ring */}
      <path
        d="M50 16 L18 32 L18 54 Q18 74 50 87 Q82 74 82 54 L82 32 Z"
        fill="none"
        stroke={spineFill}
        strokeWidth="2"
        opacity="0.4"
      />

      {/* Spine column — stylized vertebrae */}
      {[22, 30, 38, 46, 54, 62, 70].map((y, i) => (
        <g key={i}>
          {/* Vertebra body */}
          <rect
            x={44}
            y={y}
            width={12}
            height={5}
            rx={2}
            fill={spineFill}
          />
          {/* Left process */}
          <rect
            x={38}
            y={y + 1}
            width={6}
            height={3}
            rx={1.5}
            fill={spineInner}
            opacity={0.7}
          />
          {/* Right process */}
          <rect
            x={56}
            y={y + 1}
            width={6}
            height={3}
            rx={1.5}
            fill={spineInner}
            opacity={0.7}
          />
          {/* Disc between vertebrae (not after last) */}
          {i < 6 && (
            <rect
              x={46}
              y={y + 5}
              width={8}
              height={3}
              rx={1}
              fill={spineInner}
              opacity={0.3}
            />
          )}
        </g>
      ))}

      {/* Swoosh / accent curve */}
      <path
        d="M60 20 Q85 45 60 75"
        fill="none"
        stroke={spineFill}
        strokeWidth="2.5"
        opacity="0.5"
      />

      {/* Text: Ergo */}
      <text
        x={108}
        y={62}
        fontFamily="Inter, system-ui, sans-serif"
        fontSize="38"
        fontWeight="700"
        fill={ergoColor}
        letterSpacing="-0.5"
      >
        Ergo
      </text>

      {/* Text: Vigilance */}
      <text
        x={196}
        y={62}
        fontFamily="Inter, system-ui, sans-serif"
        fontSize="38"
        fontWeight="700"
        fill={vigilanceColor}
        letterSpacing="-0.5"
      >
        Vigilance
      </text>
    </svg>
  );
}
