/**
 * withTimeout — wraps a LangGraph node function with a configurable timeout.
 * On timeout, returns a partial state with a `_timeoutError` field.
 */
import type { AgentState } from "./create-node.js";

export interface TimeoutConfig {
  /** Timeout in milliseconds */
  ms: number;
  /** State fields to return on timeout (defaults to empty) */
  fallbackState?: Partial<AgentState>;
}

/**
 * Wrap a node function with a timeout guard.
 *
 * @param fn - The LangGraph node function (async, takes state, returns partial state)
 * @param config - Timeout config { ms, fallbackState? }
 * @returns Wrapped function that rejects/times out after `ms` milliseconds
 *
 * @example
 * ```ts
 * const node = withTimeout(myNode, { ms: 5000 });
 * // Returns { _timeoutError: "Node timed out after 5000ms" } on timeout
 * ```
 */
/**
 * Sentinel thrown by the internal race when the timeout fires. Detection is
 * by instanceof — NOT by message matching (an upstream error that merely
 * mentions "timed out" must propagate, not become our fallback).
 */
class TimeoutError extends Error {
  constructor(ms: number) {
    super(`Node timed out after ${ms}ms`);
    this.name = "TimeoutError";
  }
}

export function withTimeout<T extends AgentState>(
  fn: (state: T) => Promise<Partial<T>>,
  config: TimeoutConfig | number,
): (state: T) => Promise<Partial<T>> {
  const { ms, fallbackState } =
    typeof config === "number" ? { ms: config, fallbackState: undefined } : config;

  return async (state: T): Promise<Partial<T>> => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), ms);

    try {
      const result = await Promise.race([
        fn(state),
        new Promise<never>((_, reject) =>
          controller.signal.addEventListener("abort", () =>
            reject(new TimeoutError(ms)),
          ),
        ),
      ]);
      clearTimeout(timer);
      return result;
    } catch (err: any) {
      clearTimeout(timer);
      if (err instanceof TimeoutError) {
        return {
          ...(fallbackState ?? {}),
          _timeoutError: err.message,
        } as unknown as Partial<T>;
      }
      throw err;
    }
  };
}
