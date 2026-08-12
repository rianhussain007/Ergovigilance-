/**
 * Shared IST (Indian Standard Time, UTC+5:30) formatting utilities.
 *
 * The backend stores timestamps as local server time (IST) via
 * `datetime.now()` without timezone info.  All frontend displays must
 * render these as IST so what the user sees matches what actually
 * happened on the factory floor.
 *
 * Every date-display call in the app should use one of these helpers
 * instead of calling `toLocaleString` / `toLocaleTimeString` directly,
 * so timezone handling stays consistent and is easy to audit.
 */

const IST_TIMEZONE = 'Asia/Kolkata';

/** Short IST label, e.g. "IST" */
export const IST_LABEL = 'IST';

/**
 * Format a Date (or ISO string / epoch number) to a full IST datetime
 * string: "Aug 11, 2026, 8:04 PM IST"
 */
export function formatISTFull(date: Date | string | number): string {
  const d = typeof date === 'string' || typeof date === 'number' ? new Date(date) : date;
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('en-IN', {
    timeZone: IST_TIMEZONE,
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZoneName: 'short',
  });
}

/**
 * Format to time-only in IST: "8:04 PM"
 */
export function formatISTTime(date: Date | string | number): string {
  const d = typeof date === 'string' || typeof date === 'number' ? new Date(date) : date;
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('en-IN', {
    timeZone: IST_TIMEZONE,
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/**
 * Format to time-only in IST with seconds: "8:04:25 PM"
 */
export function formatISTTimeWithSeconds(date: Date | string | number): string {
  const d = typeof date === 'string' || typeof date === 'number' ? new Date(date) : date;
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('en-IN', {
    timeZone: IST_TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

/**
 * Format to date-only in IST: "Aug 11, 2026"
 */
export function formatISTDate(date: Date | string | number): string {
  const d = typeof date === 'string' || typeof date === 'number' ? new Date(date) : date;
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('en-IN', {
    timeZone: IST_TIMEZONE,
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/**
 * Compact session label in IST: "Aug 11, 8:04 PM IST"
 */
export function formatISTSessionLabel(date: Date | string | number): string {
  const d = typeof date === 'string' || typeof date === 'number' ? new Date(date) : date;
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('en-IN', {
    timeZone: IST_TIMEZONE,
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZoneName: 'short',
  });
}

/**
 * Format to a full date with weekday for audit trails:
 * "Monday, Aug 11, 2026"
 */
export function formatISTDateLong(date: Date | string | number): string {
  const d = typeof date === 'string' || typeof date === 'number' ? new Date(date) : date;
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('en-IN', {
    timeZone: IST_TIMEZONE,
    weekday: 'long',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/**
 * Format the current time for the header clock: "20:04:25"
 * Uses 24-hour IST.
 */
export function formatISTClock(): string {
  return new Date().toLocaleString('en-IN', {
    timeZone: IST_TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}
