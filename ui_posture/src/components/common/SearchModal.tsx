import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { Search, FileText, Activity, User, Calendar, Radio, BarChart3, Settings, Users, Camera, Brain, Shield, ClipboardList } from 'lucide-react';
import { useNavigate } from 'react-router';
import { apiFetch } from '@/src/services/apiClient';
import { useAuth } from '@/src/auth/AuthContext';
import { isPathAllowed, rolePaths } from '@/src/auth/routes';

/* ── Types ────────────────────────────────────────────────────────── */

interface SearchResult {
  id?: string;
  label: string;
  description: string;
  icon?: typeof FileText;
  route: string;
  category: string;
  type?: string;
}

/* ── Static navigation items (always available as fallback) ───────── */

/** Exported for the palette↔rolePaths contract test (capabilities.test.ts). */
export const NAV_ITEMS: SearchResult[] = [
  { label: 'Dashboard', description: 'Live monitoring overview', icon: Activity, route: '/dashboard', category: 'Navigation', type: 'nav' },
  { label: 'Live Monitoring', description: 'Real-time camera feed and pose analysis', icon: Radio, route: '/monitoring', category: 'Navigation', type: 'nav' },
  { label: 'Session History', description: 'Browse past monitoring sessions', icon: Calendar, route: '/sessions', category: 'Navigation', type: 'nav' },
  { label: 'Reports', description: 'Safety, risk trend, and session reports', icon: FileText, route: '/reports', category: 'Navigation', type: 'nav' },
  { label: 'Analytics', description: 'Cross-session analytics and trends', icon: BarChart3, route: '/analytics', category: 'Navigation', type: 'nav' },
  { label: 'Workers', description: 'Worker profiles and enrollment', icon: Users, route: '/workers', category: 'Navigation', type: 'nav' },
  { label: 'Settings', description: 'Theme, camera, notifications', icon: Settings, route: '/settings', category: 'Navigation', type: 'nav' },
  { label: 'Cloud Cameras', description: 'YOLO-based CCTV RTSP monitoring', icon: Camera, route: '/cloud-cameras', category: 'Navigation', type: 'nav' },
  { label: 'Cloud Settings', description: 'YOLO model and RTSP configuration', icon: Settings, route: '/cloud-settings', category: 'Navigation', type: 'nav' },
  { label: 'Model Dashboard', description: 'YOLO vs MediaPipe comparison', icon: Brain, route: '/model-dashboard', category: 'Navigation', type: 'nav' },
  { label: 'YOLO Demo', description: 'Upload image for pose detection', icon: Camera, route: '/yolo-demo', category: 'Navigation', type: 'nav' },
  { label: 'ROI Analytics', description: 'Cost savings and business case', icon: BarChart3, route: '/roi-analytics', category: 'Navigation', type: 'nav' },
  { label: 'System Health', description: 'Service status and metrics', icon: Activity, route: '/system-health', category: 'Navigation', type: 'nav' },
  { label: 'Video Review', description: 'Review recorded sessions', icon: FileText, route: '/video-review', category: 'Navigation', type: 'nav' },
  { label: 'Multi-Camera View', description: 'Grid view of all camera feeds', icon: Camera, route: '/cameras', category: 'Navigation', type: 'nav' },
  { label: 'Audit Trail', description: 'System activity log', icon: Shield, route: '/audit', category: 'Navigation', type: 'nav' },
  { label: 'Onboarding', description: 'Factory IT setup checklist', icon: ClipboardList, route: '/onboarding', category: 'Navigation', type: 'nav' },
];

const ICON_MAP: Record<string, typeof FileText> = {
  nav: Activity,
  session: Calendar,
  worker: User,
  audit: Shield,
};

/* ── Main Component ───────────────────────────────────────────────── */

export function SearchModal() {
  const { user } = useAuth();
  const role = user?.role;
  // The palette used to offer every page to every role, so Ctrl+K → Users as an
  // operator landed on a silent redirect (audit F-UX-02/F-UX-14). Filter both
  // the static nav items and the server results through the same rule the
  // router guard uses.
  const navItems = useMemo(
    () => (role ? NAV_ITEMS.filter((item) => isPathAllowed(item.route, rolePaths[role])) : []),
    [role],
  );
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Server-side search with debounce
  const performSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const res = await apiFetch(`/api/search?q=${encodeURIComponent(q)}&limit=10`);
      if (res.ok) {
        const data = await res.json();
        const items: SearchResult[] = (data.results || [])
          .map((r: any) => ({
            ...r,
            icon: ICON_MAP[r.type || 'nav'] || Activity,
          }))
          .filter((r: SearchResult) => !role || isPathAllowed(r.route, rolePaths[role]));
        setResults(items);
      }
    } catch {
      // Fallback: filter local nav items
      const ql = q.toLowerCase();
      setResults(
        navItems.filter(
          (r) => r.label.toLowerCase().includes(ql) || r.description.toLowerCase().includes(ql)
        )
      );
    } finally {
      setLoading(false);
    }
  }, [navItems, role]);

  // Debounced search
  const handleQueryChange = useCallback((value: string) => {
    setQuery(value);
    setSelectedIndex(0);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!value.trim()) {
      setResults([]);
      return;
    }
    debounceRef.current = setTimeout(() => performSearch(value), 200);
  }, [performSearch]);

  // Keyboard shortcuts
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

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setQuery('');
      setResults([]);
      setSelectedIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Keyboard navigation within results
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    const items = query.trim() ? results : navItems;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((i) => (i + 1) % items.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((i) => (i - 1 + items.length) % items.length);
    } else if (e.key === 'Enter' && items[selectedIndex]) {
      e.preventDefault();
      handleSelect(items[selectedIndex].route);
    }
  }, [query, results, selectedIndex, navItems]);

  // When no query, show nav items; when querying, show server results
  const displayItems = query.trim() ? results : navItems;

  // Group results by category
  const grouped = displayItems.reduce<Record<string, SearchResult[]>>((acc, item) => {
    (acc[item.category] ??= []).push(item);
    return acc;
  }, {});

  const handleSelect = (route: string) => {
    setOpen(false);
    navigate(route);
  };

  const handleClose = () => setOpen(false);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex justify-center items-start pt-[100px]" role="dialog" aria-modal="true" aria-label="Search pages and workers">
      <div className="fixed inset-0 bg-black/70" onClick={handleClose} />
      <div className="relative w-[720px] max-w-[90vw] min-w-[400px] shrink-0 bg-surface-container border border-outline-variant rounded-xl shadow-2xl overflow-hidden">
        {/* Search input */}
        <div className="flex items-center h-[52px] gap-md px-lg border-b border-outline-variant">
          <Search className="w-5 h-5 text-on-surface-variant shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search sessions, workers, reports, pages..."
            aria-label="Search"
            className="flex-1 bg-transparent text-[16px] text-on-surface placeholder:text-outline focus:outline-none h-full min-w-0"
            spellCheck={false}
            autoComplete="off"
          />
          {loading && (
            <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin shrink-0" />
          )}
          <kbd className="shrink-0 font-label-mono text-[10px] text-on-surface-variant/50 border border-outline-variant rounded px-1.5 py-0.5">ESC</kbd>
        </div>

        {/* Results */}
        <div className="max-h-80 overflow-y-auto p-sm">
          {displayItems.length === 0 ? (
            <p className="text-body-sm text-on-surface-variant text-center py-lg">
              {loading ? 'Searching...' : `No results found for "${query}"`}
            </p>
          ) : (
            Object.entries(grouped).map(([category, items]) => (
              <div key={category} className="mb-2">
                <p className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant/50 px-md py-1">
                  {category}
                  {category !== 'Navigation' && items.length > 0 && (
                    <span className="ml-1 text-primary/60">({items.length})</span>
                  )}
                </p>
                {items.map((r, i) => {
                  const globalIdx = displayItems.indexOf(r);
                  const Icon = r.icon || Activity;
                  return (
                    <button
                      key={`${r.category}-${r.label}-${r.route}`}
                      onClick={() => handleSelect(r.route)}
                      onMouseEnter={() => setSelectedIndex(globalIdx)}
                      className={`w-full flex items-center gap-md px-md py-sm rounded-lg transition-colors text-left ${
                        globalIdx === selectedIndex
                          ? 'bg-primary/10 border border-primary/20'
                          : 'hover:bg-surface-container-highest border border-transparent'
                      }`}
                    >
                      <Icon className="w-5 h-5 text-primary shrink-0" />
                      <div className="min-w-0">
                        <p className="text-body-sm font-medium text-on-surface">{r.label}</p>
                        <p className="text-[11px] text-on-surface-variant truncate">{r.description}</p>
                      </div>
                      {r.type && r.type !== 'nav' && (
                        <span className="ml-auto text-[9px] uppercase tracking-wider text-on-surface-variant/40 bg-surface-container-highest px-1.5 py-0.5 rounded">
                          {r.type}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer hint */}
        <div className="px-lg py-2 border-t border-outline-variant/50 flex items-center justify-between">
          <span className="text-[10px] text-on-surface-variant/40">↑↓ navigate · ↵ select · esc close</span>
          <span className="text-[10px] text-on-surface-variant/40">{displayItems.length} result{displayItems.length !== 1 ? 's' : ''}</span>
        </div>
      </div>
    </div>,
    document.body
  );
}
