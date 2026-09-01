import React from 'react';

/**
 * ErgoVigilance Logo — renders inline SVG for crisp scaling at any size.
 *
 * Props:
 *   - className: additional CSS classes (e.g. "h-10 w-auto")
 *   - variant: "auto" (default), "dark" (for light bg), "light" (for dark bg)
 *   - iconOnly: if true, renders just the shield icon (no wordmark)
 */
interface LogoProps {
  className?: string;
  variant?: 'auto' | 'dark' | 'light';
  iconOnly?: boolean;
}

function ShieldIcon({ color = '#22d3ee' }: { color?: string }) {
  return (
    <g>
      <path
        d="M100 10 L185 45 L185 110 C185 155 148 195 100 210 C52 195 15 155 15 110 L15 45 Z"
        stroke={color}
        strokeWidth="14"
        strokeLinejoin="round"
        fill="none"
      />
      <circle cx="100" cy="72" r="16" fill={color} />
      <path d="M100 88 L100 145" stroke={color} strokeWidth="12" strokeLinecap="round" />
      <path d="M100 105 L60 72" stroke={color} strokeWidth="12" strokeLinecap="round" />
      <path d="M100 105 L140 72" stroke={color} strokeWidth="12" strokeLinecap="round" />
      <path d="M100 145 L70 185" stroke={color} strokeWidth="12" strokeLinecap="round" />
      <path d="M100 145 L130 185" stroke={color} strokeWidth="12" strokeLinecap="round" />
    </g>
  );
}

export default function Logo({ className = 'h-10 w-auto', variant = 'auto', iconOnly = false }: LogoProps) {
  // "light" variant = light/bright colors for use ON dark backgrounds (landing, sidebar)
  // "dark" variant = dark colors for use ON light backgrounds (login page)
  const onDarkBg = variant === 'light' || variant === 'auto';
  const iconColor = onDarkBg ? '#22d3ee' : '#0891b2';
  const textColor = onDarkBg ? '#ffffff' : '#0f172a';

  if (iconOnly) {
    return (
      <svg
        viewBox="0 0 200 220"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={className}
        role="img"
        aria-label="ErgoVigilance"
      >
        <ShieldIcon color={iconColor} />
      </svg>
    );
  }

  return (
    <svg
      viewBox="0 0 750 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`${className} max-w-full`}
      role="img"
      aria-label="ErgoVigilance"
    >
      {/* Shield icon */}
      <g transform="translate(10, 5) scale(0.55)">
        <ShieldIcon color={iconColor} />
      </g>
      {/* Wordmark: "Ergo" bold + "Vigilance" regular */}
      <text
        x="145"
        y="82"
        fontFamily="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
        fontSize="62"
        fontWeight="700"
        fill={textColor}
        letterSpacing="-1"
      >
        Ergo
      </text>
      <text
        x="270"
        y="82"
        fontFamily="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
        fontSize="62"
        fontWeight="400"
        fill={textColor}
        letterSpacing="-1"
      >
        Vigilance
      </text>
    </svg>
  );
}
