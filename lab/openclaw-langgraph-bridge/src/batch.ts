/**
 * batch() — Parallel node execution with concurrency limit.
 *
 * Runs multiple node functions concurrently, merging all results.
 * Useful for fan-out patterns where nodes are independent.
 */

import type { AgentState } from "./create-node.js";

export interface BatchConfig {
  /** Batch name (for error messages) */
  name: string;
  /** Node functions to run in parallel */
  nodes: Array<(state: AgentState) => Promise<Record<string, unknown>>>;
  /** Max concurrent executions (default: Infinity) */
  concurrency?: number;
  /** If true, continue on individual node errors (default: false) */
  continueOnError?: boolean;
}

/**
 * Run nodes in parallel with optional concurrency limit.
 */
export function batch(config: BatchConfig) {
  const { name, nodes, concurrency = Infinity, continueOnError = false } = config;

  // Config validation: a non-positive/fractional/NaN concurrency yields zero
  // worker coroutines, which would silently execute NO nodes and return
  // { completedCount: 0 } — a false success. Fail loudly instead.
  if (concurrency !== Infinity && (!Number.isFinite(concurrency) || concurrency < 1)) {
    throw new RangeError(
      `batch("${name}"): concurrency must be a number >= 1 or Infinity, got ${concurrency}`
    );
  }

  return async (state: AgentState): Promise<Record<string, unknown>> => {
    const results: Record<string, unknown>[] = [];
    const errors = new Map<number, Error>();

    // Simple concurrency pool
    const limit = Math.min(concurrency, nodes.length);
    let nextIndex = 0;

    async function runNext() {
      while (nextIndex < nodes.length) {
        const i = nextIndex++;
        try {
          results[i] = await nodes[i]({ ...state } as AgentState);
        } catch (err) {
          if (!continueOnError) throw err;
          errors.set(i, err instanceof Error ? err : new Error(String(err)));
        }
      }
    }

    const workers = Array.from({ length: limit }, () => runNext());
    await Promise.all(workers);

    // Merge all successful results
    let merged: Record<string, unknown> = {};
    for (let i = 0; i < results.length; i++) {
      if (results[i]) merged = { ...merged, ...results[i] };
    }

    return {
      ...merged,
      completedCount: results.filter(Boolean).length,
      ...(errors.size > 0 ? { [`${name}Errors`]: Object.fromEntries(errors) } : {}),
    };
  };
}
