/**
 * Timing constants shared across the Query_Layer and API_Client.
 *
 * Every hook reads its refetchInterval from this module;
 * no component or hook contains an interval literal.
 */

/** Per-endpoint auto-refresh intervals in milliseconds. */
export const REFRESH_INTERVALS_MS = {
  fleetSummary: 60_000,
  devices: 60_000,
  alerts: 20_000,
  analytics: 300_000,
  healthHistory: 300_000,
  maintenance: 60_000,
  status: 300_000,
} as const;

/** Retry policy for 503 responses in the API_Client. */
export const RETRY_POLICY = { maxAttempts: 10, unitMs: 500, retryStatus: 503 } as const;

/** Tick interval for the freshness indicator re-render (ms). */
export const FRESHNESS_TICK_MS = 5_000;

/** Maximum age (ms) of the embedded fleet-summary analytics before falling back to the dedicated endpoint. */
export const ANALYTICS_CACHE_MAX_AGE_MS = 60_000;

/** Duration (ms) to show "Done!" / "Failed" on the hard-refresh button before resetting. */
export const HARD_REFRESH_LABEL_RESET_MS = 2_000;
