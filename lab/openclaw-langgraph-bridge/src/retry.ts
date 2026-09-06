/**
 * Retry wrapper for LangGraph nodes with exponential backoff.
 *
 * withRetry() wraps a node function, retrying on failure up to `maxAttempts`
 * total calls. Each retry waits `baseDelayMs * 2^(attempt-1)` milliseconds.
 * Optionally calls `onRetry` before each retry for logging/metrics.
 */

export interface RetryConfig {
  /** Maximum total attempts (default: 3) */
  maxAttempts?: number;
  /** Base delay in ms, doubled each retry (default: 100) */
  baseDelayMs?: number;
  /** Called before each retry with the error and attempt number */
  onRetry?: (error: unknown, attempt: number) => void;
}

/**
 * Sleep for `ms` milliseconds.
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Wrap a LangGraph node function with retry logic.
 *
 * On success, returns immediately. On failure, retries up to `maxAttempts - 1`
 * additional times with exponential backoff. If all attempts fail, throws the
 * last error.
 */
export function withRetry(
  node: (state: Record<string, unknown>) => Promise<Record<string, unknown>>,
  config: RetryConfig = {}
): (state: Record<string, unknown>) => Promise<Record<string, unknown>> {
  const maxAttempts = config.maxAttempts ?? 3;
  const baseDelayMs = config.baseDelayMs ?? 100;

  // Config validation: maxAttempts < 1 means the loop never runs and the
  // wrapper would `throw undefined` — violating the "throws the last error"
  // contract. Fail loudly at construction instead.
  if (!Number.isFinite(maxAttempts) || maxAttempts < 1) {
    throw new RangeError(
      `withRetry: maxAttempts must be a number >= 1, got ${maxAttempts}`
    );
  }

  return async (state) => {
    let lastError: unknown;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        return await node(state);
      } catch (err) {
        lastError = err;
        if (attempt < maxAttempts) {
          config.onRetry?.(err, attempt);
          await sleep(baseDelayMs * Math.pow(2, attempt - 1));
        }
      }
    }
    throw lastError;
  };
}
