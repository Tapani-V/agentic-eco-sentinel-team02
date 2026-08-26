/**
 * Freshness label based on elapsed milliseconds since last update.
 * < 60_000 → "Ns ago" (seconds)
 * < 3_600_000 → "Nm ago" (minutes)
 * >= 3_600_000 → "from cache"
 * Negative/non-finite → "0s ago"
 */
export function formatFreshness(elapsedMs: number): string {
  if (!Number.isFinite(elapsedMs) || elapsedMs < 0) return '0s ago';
  if (elapsedMs < 60_000) return `${Math.floor(elapsedMs / 1000)}s ago`;
  if (elapsedMs < 3_600_000) return `${Math.floor(elapsedMs / 60_000)}m ago`;
  return 'from cache';
}

/** 2-digit local hour:minute:second */
export function formatClockTime(date: Date): string {
  return date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/** Format as dollar amount: dp=0 → "$1234", dp=2 → "$12.34" */
export function formatMoney(v: unknown, dp: 0 | 2): string {
  const n = numberOr0(v);
  return `$${n.toFixed(dp)}`;
}

/** Format as percentage with 1 decimal place */
export function formatPercent1(v: unknown): string {
  const n = numberOr0(v);
  return `${(n * 100).toFixed(1)}%`;
}

/** Returns the number or 0 if input is not a valid finite number */
export function numberOr0(v: unknown): number {
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  return 0;
}

/** Returns the string or the fallback if input is not a non-empty string */
export function textOr(v: unknown, fallback: string): string {
  if (typeof v === 'string' && v.length > 0) return v;
  return fallback;
}
