import { useEffect, useState } from 'react';
import { getStoredToken } from '@/src/auth/AuthContext';

/**
 * Short-lived token scoped ONLY to the MJPEG stream
 * (POST /video/stream-token, ~10-minute expiry).
 *
 * Query strings end up in browser history and server access logs — they
 * must carry this video-only token, never the long-lived API JWT.
 * Returns null while minting or when the mint call fails; callers fall
 * back to the legacy JWT path (which the backend still accepts) so the
 * feed degrades instead of dying.
 */
export function useStreamToken(active: boolean): string | null {
  const [videoToken, setVideoToken] = useState<string | null>(null);

  useEffect(() => {
    if (!active) {
      setVideoToken(null);
      return;
    }
    let cancelled = false;
    const mint = async () => {
      try {
        const res = await fetch('/video/stream-token', {
          method: 'POST',
          headers: { Authorization: `Bearer ${getStoredToken() ?? ''}` },
        });
        if (!res.ok) throw new Error(`stream-token ${res.status}`);
        const data = await res.json();
        if (!cancelled && data?.token) setVideoToken(data.token);
      } catch {
        if (!cancelled) setVideoToken(null);
      }
    };
    void mint();
    // Re-mint well before the backend's 10-minute expiry.
    const interval = setInterval(mint, 8 * 60 * 1000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [active]);

  return videoToken;
}
