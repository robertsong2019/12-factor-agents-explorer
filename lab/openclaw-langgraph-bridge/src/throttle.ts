/**
 * Throttle node execution to at most N calls per time window.
 *
 * Unlike withRateLimit (token bucket), throttle uses a fixed sliding window
 * and queues excess calls rather than rejecting them.
 */

export interface ThrottleConfig {
  /** Max calls per window. */
  limit: number;
  /** Window duration in milliseconds. */
  windowMs: number;
  /** Optional callback when a call is delayed. */
  onThrottle?: (queueDepth: number) => void;
}

interface QueueEntry {
  resolve: () => void;
}

/**
 * Wrap a node with throttling. Excess calls are queued and released
 * when the next window slot opens.
 */
export function throttle(
  node: (state: Record<string, unknown>) => Promise<Record<string, unknown>>,
  config: ThrottleConfig
): (state: Record<string, unknown>) => Promise<Record<string, unknown>> {
  const timestamps: number[] = [];
  const queue: QueueEntry[] = [];

  // Config validation: limit < 1 means `timestamps.length < limit` can never
  // hold, so every call would queue forever — a deadlock. Fail loudly instead.
  if (!Number.isFinite(config.limit) || config.limit < 1) {
    throw new RangeError(
      `throttle: limit must be a number >= 1, got ${config.limit}`
    );
  }

  function cleanWindow(now: number) {
    const cutoff = now - config.windowMs;
    while (timestamps.length > 0 && timestamps[0] <= cutoff) {
      timestamps.shift();
    }
  }

  function processQueue() {
    const now = Date.now();
    cleanWindow(now);
    while (queue.length > 0 && timestamps.length < config.limit) {
      timestamps.push(now);
      queue.shift()!.resolve();
    }
    if (queue.length > 0) {
      const waitMs = config.windowMs - (now - timestamps[0]) + 1;
      setTimeout(processQueue, Math.max(waitMs, 10));
    }
  }

  return async (state) => {
    const now = Date.now();
    cleanWindow(now);
    if (timestamps.length < config.limit) {
      timestamps.push(now);
      return node(state);
    }
    // Queue the call
    config.onThrottle?.(queue.length);
    await new Promise<void>((resolve) => {
      queue.push({ resolve });
      processQueue();
    });
    return node(state);
  };
}
