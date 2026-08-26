import { RETRY_POLICY } from '../config/intervals';

// ---------------------------------------------------------------------------
// ApiError
// ---------------------------------------------------------------------------

/**
 * Structured error thrown by the API_Client.
 *
 * - `reason: 'http'`    → the server returned a non-200 status (or 503 after all retries)
 * - `reason: 'network'` → `fetch` itself rejected (DNS failure, offline, abort)
 * - `reason: 'parse'`   → HTTP 200 received but body was not valid JSON
 */
export class ApiError extends Error {
  constructor(
    readonly path: string,
    readonly status: number | null,
    readonly reason: 'http' | 'network' | 'parse',
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

// ---------------------------------------------------------------------------
// Retry delay schedule
// ---------------------------------------------------------------------------

/**
 * Compute the delays (in ms) before attempts 2..maxAttempts.
 *
 * Returns an array of length `maxAttempts - 1` where `delays[i] = unitMs * (i + 1)`.
 *
 * Example with default values (maxAttempts=10, unitMs=500):
 *   [500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500]
 */
export function retryDelays(maxAttempts: number, unitMs = 500): number[] {
  const delays: number[] = [];
  for (let i = 0; i < maxAttempts - 1; i++) {
    delays.push(unitMs * (i + 1));
  }
  return delays;
}

// ---------------------------------------------------------------------------
// Query-string builder
// ---------------------------------------------------------------------------

type QueryParams = Record<string, string | number | boolean | null | undefined>;

function buildUrl(path: string, query?: QueryParams): string {
  const base = `/api${path}`;
  if (!query) return base;

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null) {
      params.append(key, String(value));
    }
  }

  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}

// ---------------------------------------------------------------------------
// setTimeout-based delay (works with fake timers in tests)
// ---------------------------------------------------------------------------

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

// ---------------------------------------------------------------------------
// fetchJson — the core transport function
// ---------------------------------------------------------------------------

/**
 * Fetch JSON from the Dashboard_Service API.
 *
 * Behaviour (in order):
 * 1. Build URL as `/api${path}` plus query params (omitting null/undefined values).
 * 2. Issue fetch. A thrown rejection → ApiError(path, null, 'network') immediately (no retry).
 * 3. On HTTP 503, retry up to RETRY_POLICY.maxAttempts total attempts with linear backoff.
 * 4. Any other non-200, or 503 after max attempts → ApiError(path, status, 'http').
 * 5. On 200, parse JSON. SyntaxError → ApiError(path, 200, 'parse').
 * 6. Return parsed body as T.
 */
export async function fetchJson<T>(path: string, query?: QueryParams): Promise<T> {
  const url = buildUrl(path, query);
  const delays = retryDelays(RETRY_POLICY.maxAttempts, RETRY_POLICY.unitMs);

  let attempt = 0;

  for (;;) {
    let response: Response;

    try {
      response = await fetch(url);
    } catch {
      throw new ApiError(path, null, 'network', `Network error fetching ${url}`);
    }

    if (response.status === RETRY_POLICY.retryStatus) {
      const nextDelay = delays[attempt];
      if (nextDelay !== undefined) {
        await delay(nextDelay);
        attempt++;
        continue;
      }
      // All retries exhausted
      throw new ApiError(path, response.status, 'http', `HTTP ${response.status} after ${RETRY_POLICY.maxAttempts} attempts on ${url}`);
    }

    if (response.status !== 200) {
      throw new ApiError(path, response.status, 'http', `HTTP ${response.status} on ${url}`);
    }

    // 200 — parse JSON
    try {
      const body: T = await response.json() as T;
      return body;
    } catch {
      throw new ApiError(path, 200, 'parse', `Invalid JSON in response from ${url}`);
    }
  }
}
