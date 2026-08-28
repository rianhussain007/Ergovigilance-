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
  return (
    <img
      src="/images/logo.png"
      alt="ErgoVigilance"
      className={className}
      style={{ objectFit: 'contain' }}
    />
  );
}
