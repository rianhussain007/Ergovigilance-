import React from 'react';

/**
 * ErgoVigilance Logo — uses the official brand PNG.
 *
 * Props:
 *   - className: additional CSS classes (e.g. "h-10 w-auto")
 *   - variant: "auto" (default), "dark" (for light bg), "light" (for dark bg)
 */
interface LogoProps {
  className?: string;
  variant?: 'auto' | 'dark' | 'light';
}

export default function Logo({ className = 'h-10 w-auto', variant = 'auto' }: LogoProps) {
  // The brand PNG has a transparent background and works on both
  // light and dark surfaces. Add a subtle filter for dark-bg variant
  // to ensure the shield+spine details pop against dark backgrounds.
  const filter = variant === 'light' ? 'brightness(1.1) contrast(1.05)' : undefined;
  return (
    <img
      src="/images/logo.png"
      alt="ErgoVigilance"
      className={className}
      style={{ objectFit: 'contain', filter }}
    />
  );
}
