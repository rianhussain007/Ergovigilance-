import { Clock, User, Search, Sun, Moon, Monitor, Video } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { SessionInfo } from '@/src/types/api';
import { useTheme } from '@/src/hooks/useTheme';
import { formatISTClock } from '@/src/utils/formatTime';

interface HeaderProps {
  session: SessionInfo | null;
}

function ThemeToggle() {
  const { mode, setMode } = useTheme();
  const cycle = () => {
    if (mode === 'dark') setMode('light');
    else if (mode === 'light') setMode('system');
    else setMode('dark');
  };
  const Icon = mode === 'dark' ? Moon : mode === 'light' ? Sun : Monitor;
  return (
    <button onClick={cycle} className="w-8 h-8 rounded-lg hover:bg-surface-container-highest transition-colors text-on-surface-variant hover:text-on-surface flex items-center justify-center" title={`Theme: ${mode}`}>
      <Icon className="w-4 h-4" />
    </button>
  );
}

export function Header({ session }: HeaderProps) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  // Single source of truth for the session status: when the camera is not
  // active there is no live session, so the header shows one unambiguous
  // "No active session" badge — never a fake session ID or a worker name
  // next to an alarming red OFFLINE indicator.
  const isActive = session?.cameraStatus === 'active';

  return (
    <header className="sticky top-0 z-30 bg-surface/95 backdrop-blur-xl border-b border-outline-variant/60">
      <div className="flex items-center h-14 px-lg gap-lg">
        <button onClick={() => window.dispatchEvent(new CustomEvent('opensearch'))} className="flex items-center gap-md h-9 px-md rounded-lg bg-surface-container-high border border-outline-variant/80 text-on-surface-variant hover:text-on-surface hover:border-primary/40 hover:shadow-sm hover:shadow-primary/5 focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/20 transition-all w-[340px] shrink group">
          <Search className="w-4 h-4 shrink-0 text-on-surface-variant/60 group-hover:text-primary transition-colors" />
          <span className="text-body-sm text-on-surface-variant/60 group-hover:text-on-surface-variant/80 truncate">Search sessions, workers, reports...</span>
          <span className="ml-auto font-label-mono text-[10px] text-on-surface-variant/30 border border-outline-variant rounded px-1.5 py-0.5 group-hover:text-on-surface-variant/60 group-hover:border-outline-variant/60 transition-colors shrink-0">Ctrl+K</span>
        </button>

        <div className="flex items-center gap-lg ml-auto h-8">
          {isActive && (
            <div className="flex items-center gap-sm text-on-surface-variant h-full">
              <Video className="w-4 h-4 shrink-0 text-green-400" />
              <span className="text-body-sm text-on-surface whitespace-nowrap">{session?.workerName || 'Active session'}</span>
            </div>
          )}

          <div className="flex items-center gap-sm text-on-surface-variant h-full">
            <Clock className="w-4 h-4 shrink-0" />
            <span className="font-label-mono text-label-mono text-on-surface whitespace-nowrap">
              {formatISTClock()}
            </span>
          </div>

          <div className={`flex items-center gap-sm h-8 px-md rounded-full border font-label-mono text-label-mono transition-all ${isActive ? 'bg-green-500/10 border-green-500/30 text-green-400 shadow-sm shadow-green-500/10' : 'bg-surface-container-high border-outline-variant text-on-surface-variant'}`}>
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${isActive ? 'bg-green-400 animate-pulse-glow' : 'bg-outline'}`} />
            <span className="whitespace-nowrap">{isActive ? 'LIVE' : 'No active session'}</span>
          </div>

          <ThemeToggle />

          {isActive && session?.id && (
            <div className="h-8 flex items-center px-md bg-surface-container-high rounded-lg border border-outline-variant">
              <span className="font-label-mono text-[10px] text-on-surface-variant uppercase whitespace-nowrap">{session.id}</span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
