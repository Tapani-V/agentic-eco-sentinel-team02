export type HealthStatus = 'healthy' | 'warning' | 'critical';

/** Type guard for known health statuses */
export function isHealthStatus(v: unknown): v is HealthStatus {
  return v === 'healthy' || v === 'warning' || v === 'critical';
}

/** Maps a health_status to a CSS class. Unknown values → 'unknown' (renders --border-light) */
export function healthBarClass(status: unknown): 'healthy' | 'warning' | 'critical' | 'unknown' {
  if (isHealthStatus(status)) return status;
  return 'unknown';
}

/** Maps an alert severity to a CSS class. Unknown values → 'neutral' (white surface + border-light left border) */
export function alertSeverityClass(sev: unknown): 'critical' | 'high' | 'neutral' {
  if (sev === 'critical') return 'critical';
  if (sev === 'high') return 'high';
  return 'neutral';
}

/** Maps spare part availability to a CSS class. Unknown values → 'unavailable' (red) */
export function availabilityClass(a: unknown): 'in-stock' | 'on-order' | 'unavailable' {
  if (a === 'in_stock') return 'in-stock';
  if (a === 'on_order') return 'on-order';
  return 'unavailable';
}

/** Returns the attention label emoji + text for the Attention_List */
export function attentionLabel(status: unknown): '🔴 CRITICAL' | '🟡 WARNING' {
  if (status === 'critical') return '🔴 CRITICAL';
  return '🟡 WARNING';
}
