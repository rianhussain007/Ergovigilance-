/**
 * Normalize session/report IDs for DISPLAY so the whole app uses one
 * human-readable format: SESH-YYYY-MM-DD_HH-MM-SS.
 *
 * Historical session files used two other shapes:
 *   - SESH-YYYYMMDD-<HEX>  (old short-hex format, no time recorded)
 *   - SESH-YYYYMMDD_HHMMSS_SSS  (millisecond suffix)
 *
 * Raw IDs are kept for lookups/hover; this only changes what is shown.
 */
export function normalizeSessionId(id: string): string {
  if (!id) return id;
  // Already human-readable: SESH-2026-08-10_14-25-22 (or date-only).
  if (/^SESH-\d{4}-\d{2}-\d{2}(_\d{2}-\d{2}-\d{2})?$/.test(id)) return id;
  // SESH-YYYYMMDD_HHMMSS_SSS -> SESH-YYYY-MM-DD_HH-MM-SS
  const ms = id.match(/^SESH-(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_\d+$/);
  if (ms) return `SESH-${ms[1]}-${ms[2]}-${ms[3]}_${ms[4]}-${ms[5]}-${ms[6]}`;
  // SESH-YYYYMMDD_HHMMSS -> SESH-YYYY-MM-DD_HH-MM-SS
  const plain = id.match(/^SESH-(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/);
  if (plain) return `SESH-${plain[1]}-${plain[2]}-${plain[3]}_${plain[4]}-${plain[5]}-${plain[6]}`;
  // SESH-YYYYMMDD-<HEX...> -> SESH-YYYY-MM-DD (time was never recorded)
  const hex = id.match(/^SESH-(\d{4})(\d{2})(\d{2})-([0-9A-Fa-f]{4,})$/);
  if (hex) return `SESH-${hex[1]}-${hex[2]}-${hex[3]}`;
  return id;
}

/** Reports are keyed RPT-<sessionId> — strip the prefix before normalizing. */
export function normalizeReportId(id: string): string {
  return normalizeSessionId(id.startsWith('RPT-') ? id.slice(4) : id);
}
