import { useMemo, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";

/**
 * SessionCalendar — a month-grid heatmap of work sessions.
 *
 * Each day cell is colored by the *highest* risk level present that day
 * (HIGH > MEDIUM > LOW), so "when heavy work happened" reads instantly:
 * red days = heavy load, gray days = no work. Clicking a day selects it,
 * which the parent uses to filter the session list.
 *
 * Generic over the item shape: pass any objects with a parseable timestamp
 * and a risk level (RecordingsListItem or SessionRecord both work via the
 * `items` mapping the caller provides).
 */

export interface CalendarItem {
  timestamp: string;
  riskLevel: string;
}

export interface DayAggregate {
  count: number;
  highestRisk: "LOW" | "MEDIUM" | "HIGH";
}

// Theme-aware risk tints — color-mix resolves against the current theme's
// chart tokens, so the calendar reads correctly on dark AND light surfaces.
const RISK_BG: Record<string, string> = {
  LOW: "color-mix(in srgb, var(--color-chart-green) 16%, transparent)",
  MEDIUM: "color-mix(in srgb, var(--color-chart-orange) 22%, transparent)",
  HIGH: "color-mix(in srgb, var(--color-chart-red) 30%, transparent)",
};

const RISK_BORDER: Record<string, string> = {
  LOW: "color-mix(in srgb, var(--color-chart-green) 45%, transparent)",
  MEDIUM: "color-mix(in srgb, var(--color-chart-orange) 50%, transparent)",
  HIGH: "color-mix(in srgb, var(--color-chart-red) 60%, transparent)",
};

/**
 * Parse a session timestamp into a local Date.
 * Handles compact ("20260718_163724" / "..._163724_123"), session-id
 * ("SESH-2026-07-18_16-37-24"), and ISO ("2026-07-18T16:37:24Z") formats.
 *
 * IMPORTANT: The backend stores timestamps using datetime.now() which gives
 * the server's local time. These timestamps should be interpreted as UTC
 * and then converted to the user's local timezone by the browser.
 */
export function parseSessionTimestamp(ts: string): Date | null {
  if (!ts) return null;
  const compact = ts.match(/^(\d{4})(\d{2})(\d{2})[_\s]?(\d{2})?[:_-]?(\d{2})?[:_-]?(\d{2})?/);
  if (compact) {
    const [, y, mo, d, h, mi, s] = compact;
    // Treat as UTC and let browser convert to local time
    const date = new Date(Date.UTC(
      Number(y),
      Number(mo) - 1,
      Number(d),
      h ? Number(h) : 0,
      mi ? Number(mi) : 0,
      s ? Number(s) : 0
    ));
    return Number.isNaN(date.getTime()) ? null : date;
  }
  const iso = ts.match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})(?::(\d{2}))?/);
  if (iso) {
    const [, y, mo, d, h, mi, s] = iso;
    // Backend timestamps from datetime.now() are in server-local time (IST)
    // without timezone info. Parse as local time so the display matches
    // what the user actually saw on screen.
    const hasTimezone = ts.endsWith('Z') || ts.includes('+') || ts.includes('-');
    const date = hasTimezone
      ? new Date(ts)
      : new Date(
          Number(y),
          Number(mo) - 1,
          Number(d),
          Number(h),
          Number(mi),
          s ? Number(s) : 0
        );
    return Number.isNaN(date.getTime()) ? null : date;
  }
  return null;
}

/** Local date key "YYYY-MM-DD" for grouping/filtering. */
export function toDateKey(d: Date): string {
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

/** Group items by day, tracking count + highest risk level per day. */
export function aggregateByDay(items: CalendarItem[]): Map<string, DayAggregate> {
  const map = new Map<string, DayAggregate>();
  for (const item of items) {
    const date = parseSessionTimestamp(item.timestamp);
    if (!date) continue;
    const key = toDateKey(date);
    const agg = map.get(key) ?? { count: 0, highestRisk: "LOW" as const };
    agg.count += 1;
    const risk = (item.riskLevel || "LOW").toUpperCase();
    if (risk === "HIGH") agg.highestRisk = "HIGH";
    else if (risk === "MEDIUM" && agg.highestRisk !== "HIGH") agg.highestRisk = "MEDIUM";
    map.set(key, agg);
  }
  return map;
}

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export default function SessionCalendar({
  items,
  selectedDate,
  onSelectDate,
  levelFilter,
  onLevelFilterChange,
  compact = false,
}: {
  items: CalendarItem[];
  selectedDate: string | null;
  onSelectDate: (date: string | null) => void;
  /** Optional active load-level filter (toggled from the legend swatches). */
  levelFilter?: "LOW" | "MEDIUM" | "HIGH" | null;
  onLevelFilterChange?: (level: "LOW" | "MEDIUM" | "HIGH" | null) => void;
  /** Compact rendering — small fixed-size day cells and a slim header/footer. */
  compact?: boolean;
}) {
  // Default the view to the month of the most recent item, else today.
  const defaultMonth = useMemo(() => {
    let latest: Date | null = null;
    for (const item of items) {
      const d = parseSessionTimestamp(item.timestamp);
      if (d && (!latest || d.getTime() > latest.getTime())) latest = d;
    }
    const base = latest ?? new Date();
    return new Date(base.getFullYear(), base.getMonth(), 1);
  }, [items]);

  const [viewMonth, setViewMonth] = useState<Date>(defaultMonth);

  const byDay = useMemo(() => aggregateByDay(items), [items]);
  const todayKey = toDateKey(new Date());

  const shiftMonth = (delta: number) => {
    setViewMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() + delta, 1));
  };

  const goToLatest = () => {
    setViewMonth(defaultMonth);
  };

  const cells = useMemo(() => {
    const year = viewMonth.getFullYear();
    const month = viewMonth.getMonth();
    const firstDay = new Date(year, month, 1);
    const startOffset = firstDay.getDay(); // 0 = Sunday
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const out: Array<{ day: number | null; dateKey: string | null }> = [];
    for (let i = 0; i < startOffset; i++) out.push({ day: null, dateKey: null });
    for (let d = 1; d <= daysInMonth; d++) {
      out.push({
        day: d,
        dateKey: `${year}-${pad(month + 1)}-${pad(d)}`,
      });
    }
    while (out.length % 7 !== 0) out.push({ day: null, dateKey: null });
    return out;
  }, [viewMonth]);

  const monthLabel = viewMonth.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });

  const totalSessions = items.length;
  const heavyDays = useMemo(() => {
    let n = 0;
    for (const agg of byDay.values()) if (agg.highestRisk === "HIGH") n += 1;
    return n;
  }, [byDay]);

  return (
    <div className={`rounded-lg border border-outline-variant bg-surface-container-low ${compact ? "p-sm" : "p-md"}`}>
      <div className={`flex items-center justify-between gap-sm ${compact ? "mb-xs" : "mb-sm"}`}>
        <div className="flex items-center gap-sm">
          <CalendarDays className={`text-primary ${compact ? "h-3.5 w-3.5" : "h-4 w-4"}`} />
          <h3 className={`font-bold text-on-surface ${compact ? "text-body-sm" : "text-body-sm"}`}>Work Calendar</h3>
        </div>
        {!compact && (
          <p className="text-[10px] text-on-surface-variant">Session activity by day — click a date or load level to filter.</p>
        )}
        <div className="flex items-center gap-1">
          <button
            className="rounded border border-outline-variant p-1 text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
            onClick={() => shiftMonth(-1)}
            title="Previous month"
          >
            <ChevronLeft className={compact ? "h-3 w-3" : "h-4 w-4"} />
          </button>
          <span className={`text-center font-semibold text-on-surface ${compact ? "min-w-[6.25rem] text-body-sm" : "min-w-[7.5rem] text-body-sm"}`}>
            {monthLabel}
          </span>
          <button
            className="rounded border border-outline-variant p-1 text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
            onClick={() => shiftMonth(1)}
            title="Next month"
          >
            <ChevronRight className={compact ? "h-3 w-3" : "h-4 w-4"} />
          </button>
        </div>
      </div>

      <div className={`grid grid-cols-7 text-center ${compact ? "gap-0.5" : "gap-1"}`}>
        {WEEKDAYS.map((wd) => (
          <div key={wd} className={`font-semibold uppercase text-on-surface-variant ${compact ? "py-0.5 text-[9px]" : "py-xs text-[10px]"}`}>
            {wd}
          </div>
        ))}
        {cells.map((cell, i) => {
          if (cell.day === null || cell.dateKey === null) {
            return <div key={i} className="aspect-square" />;
          }
          const agg = byDay.get(cell.dateKey);
          const isSelected = selectedDate === cell.dateKey;
          const isToday = cell.dateKey === todayKey;
          // When a load-level filter is active, dim days that don't match so
          // the matching (e.g. heavy) days stand out.
          const levelActive = levelFilter != null;
          const matchesLevel = levelActive && agg != null && agg.highestRisk === levelFilter;
          const dimmed = levelActive && !matchesLevel;
          return (
            <button
              key={i}
              onClick={() => onSelectDate(isSelected ? null : cell.dateKey)}
              title={
                agg
                  ? `${cell.dateKey} — ${agg.count} session${agg.count === 1 ? "" : "s"}, highest ${agg.highestRisk}`
                  : `${cell.dateKey} — no sessions`
              }
              className={`relative flex items-center justify-center rounded border transition ${compact ? "h-7 w-7 text-[11px]" : "aspect-square flex-col text-body-sm"} ${dimmed ? "opacity-30" : ""}`}
              style={{
                backgroundColor: agg ? RISK_BG[agg.highestRisk] : "transparent",
                borderColor: isSelected
                  ? "var(--color-info)"
                  : agg
                    ? RISK_BORDER[agg.highestRisk]
                    : "transparent",
                borderWidth: isSelected ? 2 : 1,
                color: agg ? "var(--color-on-surface)" : "var(--color-on-surface-variant)",
              }}
            >
              <span className="leading-none">{cell.day}</span>
              {!compact && agg && (
                <span className="mt-0.5 text-[9px] leading-none opacity-80">{agg.count}</span>
              )}
              {isToday && (
                <span className={`absolute rounded-full bg-blue-400 ${compact ? "top-0.5 right-0.5 h-1 w-1" : "top-0.5 right-0.5 h-1 w-1"}`} />
              )}
            </button>
          );
        })}
      </div>

      <div className={`flex flex-wrap items-center justify-between gap-sm ${compact ? "mt-sm" : "mt-md"}`}>
        <div className={`flex flex-wrap items-center gap-sm text-on-surface-variant ${compact ? "gap-1.5 text-[9px]" : "gap-sm text-[10px]"}`}>
          <button
            className={`flex items-center gap-1 rounded px-1 py-0.5 transition ${levelFilter === null ? "opacity-100" : "opacity-50"}`}
            onClick={() => onLevelFilterChange?.(null)}
            title="Show all days"
          >
            <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: "transparent", border: "1px solid var(--color-outline-variant)" }} />
            No work
          </button>
          {(["LOW", "MEDIUM", "HIGH"] as const).map((level) => {
            const active = levelFilter === level;
            return (
              <button
                key={level}
                onClick={() => onLevelFilterChange?.(active ? null : level)}
                title={`Filter to ${level === "HIGH" ? "heavy-load" : level.toLowerCase()} days`}
                className={`flex items-center gap-1 rounded px-1 py-0.5 transition ${active ? "bg-surface-container-high ring-1 ring-primary/50" : "opacity-60 hover:opacity-100"}`}
              >
                <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: RISK_BG[level], border: `1px solid ${RISK_BORDER[level]}` }} />
                {level === "HIGH" ? "Heavy load" : level.charAt(0) + level.slice(1).toLowerCase()}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-sm">
          {!compact && (
            <span className="text-[10px] text-on-surface-variant">
              {totalSessions} sessions · {heavyDays} heavy day{heavyDays === 1 ? "" : "s"}
            </span>
          )}
          {(selectedDate || levelFilter != null || viewMonth.getTime() !== defaultMonth.getTime()) && (
            <button
              className="text-[10px] font-semibold text-primary hover:underline"
              onClick={() => {
                onSelectDate(null);
                onLevelFilterChange?.(null);
                goToLatest();
              }}
            >
              Reset
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
