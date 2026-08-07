import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Search, X, FileText, Activity, User, Calendar } from 'lucide-react';
import { useNavigate } from 'react-router';

interface SearchResult {
  label: string;
  description: string;
  icon: typeof FileText;
  route: string;
}

const allResults: SearchResult[] = [
  { label: 'Dashboard', description: 'Live monitoring overview', icon: Activity, route: '/' },
  { label: 'Session SESH-2026-06-30-001', description: 'Marcus Thorne — Assembly Line B', icon: Calendar, route: '/sessions' },
  { label: 'Session SESH-2026-06-29-003', description: 'Loading Dock — 8h 12m', icon: Calendar, route: '/sessions' },
  { label: 'Risk Trend Report', description: 'Cross-session risk trend analysis', icon: FileText, route: '/reports?view=risk-trend' },
  { label: 'Reports', description: 'Safety and trend reports', icon: FileText, route: '/reports' },
  { label: 'Worker: Marcus Thorne', description: 'WA-4092 — Assembly Line B', icon: User, route: '/sessions' },
  { label: 'Worker: Elena Rodriguez', description: 'WA-2104 — Loading Dock', icon: User, route: '/sessions' },
  { label: 'Settings', description: 'Theme, camera, notifications', icon: FileText, route: '/settings' },
];

export function SearchModal() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const filtered = query.trim()
    ? allResults.filter((r) => r.label.toLowerCase().includes(query.toLowerCase()) || r.description.toLowerCase().includes(query.toLowerCase()))
    : allResults;

  useEffect(() => {
    const keyHandler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === 'Escape') {
        setOpen(false);
      }
    };
    const customHandler = () => setOpen(true);
    window.addEventListener('keydown', keyHandler);
    window.addEventListener('opensearch', customHandler);
    return () => {
      window.removeEventListener('keydown', keyHandler);
      window.removeEventListener('opensearch', customHandler);
    };
  }, []);

  useEffect(() => {
    if (open) {
      setQuery('');
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const handleSelect = (route: string) => {
    setOpen(false);
    navigate(route);
  };

  const handleClose = () => setOpen(false);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex justify-center items-start pt-[100px]" role="dialog" aria-modal="true">
      <div className="fixed inset-0 bg-black/70" onClick={handleClose} />
      <div className="relative w-[720px] max-w-[90vw] min-w-[600px] shrink-0 bg-surface-container border border-outline-variant rounded-xl shadow-2xl overflow-hidden">
        <div className="flex items-center h-[52px] gap-md px-lg border-b border-outline-variant">
          <Search className="w-5 h-5 text-on-surface-variant shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search sessions, workers, reports..."
            className="flex-1 bg-transparent text-[16px] text-on-surface placeholder:text-outline focus:outline-none h-full min-w-0"
            spellCheck={false}
            autoComplete="off"
          />
          <kbd className="shrink-0 font-label-mono text-[10px] text-on-surface-variant/50 border border-outline-variant rounded px-1.5 py-0.5">ESC</kbd>
        </div>
        <div className="max-h-80 overflow-y-auto p-sm">
          {filtered.length === 0 ? (
            <p className="text-body-sm text-on-surface-variant text-center py-lg">No results found</p>
          ) : (
            filtered.map((r) => (
              <button
                key={r.label}
                onClick={() => handleSelect(r.route)}
                className="w-full flex items-center gap-md px-md py-sm rounded-lg hover:bg-surface-container-highest transition-colors text-left"
              >
                <r.icon className="w-5 h-5 text-primary shrink-0" />
                <div className="min-w-0">
                  <p className="text-body-sm font-medium text-on-surface">{r.label}</p>
                  <p className="text-[11px] text-on-surface-variant truncate">{r.description}</p>
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
