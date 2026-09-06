/**
 * Seal a state object to prevent further mutations.
 *
 * seal() wraps a node's output in a shallow-frozen copy, ensuring
 * downstream nodes cannot accidentally mutate shared state.
 * Provides optional change detection to catch mutation attempts.
 */

export interface SealConfig {
  /** If true, log attempted mutations via onChange callback. */
  detectMutations?: boolean;
  /** Called when a mutation is attempted on sealed state. */
  onChange?: (key: string, value: unknown, oldValue: unknown) => void;
}

/**
 * Create a deep-readonly proxy that detects write attempts.
 */
function sealedProxy(
  obj: Record<string, unknown>,
  onChange?: (key: string, value: unknown, oldValue: unknown) => void
): Record<string, unknown> {
  return new Proxy(obj, {
    set(target, prop, value) {
      if (typeof prop === "string") {
        onChange?.(prop, value, target[prop]);
      }
      return false; // Block mutation
    },
    get(target, prop) {
      return target[prop as string];
    },
  });
}

/**
 * Wrap a node so its output state is sealed (shallow immutable).
 */
export function seal(
  node: (state: Record<string, unknown>) => Promise<Record<string, unknown>>,
  config?: SealConfig
): (state: Record<string, unknown>) => Promise<Record<string, unknown>> {
  return async (state) => {
    const result = await node(state);
    const frozen = Object.freeze({ ...result });
    if (config?.detectMutations) {
      // Freeze the target too: Object.isFrozen(proxy) forwards to the target,
      // so without this isSealed() would disown our own output. The set trap
      // still blocks writes and fires onChange (freeze makes it doubly safe).
      return sealedProxy(Object.freeze({ ...result }), config.onChange);
    }
    return frozen;
  };
}

/**
 * Check if a state object has been sealed (frozen).
 */
export function isSealed(state: Record<string, unknown>): boolean {
  return Object.isFrozen(state);
}

/**
 * Create a writable copy of a sealed state.
 */
export function unseal(state: Record<string, unknown>): Record<string, unknown> {
  return { ...state };
}
