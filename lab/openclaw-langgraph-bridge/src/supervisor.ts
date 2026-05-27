/**
 * Preset supervisor routers + Supervisor class for dynamic agent management.
 */

import { END } from "@langchain/langgraph";
import { type AgentRole, AgentPool } from "./multi-agent.js";

export interface RouterState {
  completedSteps?: string[];
  [key: string]: unknown;
}

// ── Supervisor ─────────────────────────────────────────

export interface AgentHealth {
  successCount: number;
  failureCount: number;
  lastUsed: number;
  avgDuration: number;
}

export interface SupervisorConfig {
  /** Maximum consecutive failures before marking agent unhealthy (default: 3) */
  maxFailures?: number;
  /** Route strategy: "round-robin" | "least-busy" | "random" (default: "round-robin") */
  strategy?: "round-robin" | "least-busy" | "random";
}

export class Supervisor {
  private agents: Map<string, AgentRole> = new Map();
  private health: Map<string, AgentHealth> = new Map();
  private rrIndex = 0;
  private maxFailures: number;
  private strategy: NonNullable<SupervisorConfig["strategy"]>;

  constructor(config: SupervisorConfig = {}) {
    this.maxFailures = config.maxFailures ?? 3;
    this.strategy = config.strategy ?? "round-robin";
  }

  /** Register a new agent */
  register(role: AgentRole): this {
    this.agents.set(role.id, role);
    this.health.set(role.id, {
      successCount: 0, failureCount: 0, lastUsed: 0, avgDuration: 0,
    });
    return this;
  }

  /** Deregister an agent */
  deregister(agentId: string): boolean {
    return this.agents.delete(agentId) && this.health.delete(agentId);
  }

  /** List registered agent IDs */
  listAgents(): string[] {
    return [...this.agents.keys()];
  }

  /** Get health stats for an agent */
  getHealth(agentId: string): AgentHealth | undefined {
    return this.health.get(agentId);
  }

  /** Check if agent is healthy (consecutive failures < maxFailures) */
  isHealthy(agentId: string): boolean {
    const h = this.health.get(agentId);
    if (!h) return false;
    return h.failureCount < this.maxFailures;
  }

  /** Select next healthy agent based on strategy */
  selectAgent(capability?: string): AgentRole | undefined {
    const healthy = [...this.agents.values()].filter(a => this.isHealthy(a.id));
    if (healthy.length === 0) return undefined;

    // Filter by capability if specified
    const candidates = capability
      ? healthy.filter(a => a.capabilities.includes(capability) || a.capabilities.includes("*"))
      : healthy;
    if (candidates.length === 0) return undefined;

    switch (this.strategy) {
      case "round-robin": {
        const agent = candidates[this.rrIndex % candidates.length];
        this.rrIndex++;
        return agent;
      }
      case "least-busy": {
        // Pick agent with fewest successes (least utilized as proxy)
        candidates.sort((a, b) => {
          const ha = this.health.get(a.id)!;
          const hb = this.health.get(b.id)!;
          return (ha.successCount + ha.failureCount) - (hb.successCount + hb.failureCount);
        });
        return candidates[0];
      }
      case "random": {
        return candidates[Math.floor(Math.random() * candidates.length)];
      }
    }
  }

  /** Execute a task with the best available agent */
  async execute(task: string, capability?: string): Promise<{ agentId: string; result: string }> {
    const agent = this.selectAgent(capability);
    if (!agent) throw new Error(`No healthy agent available${capability ? ` for capability: ${capability}` : ""}`);

    const start = Date.now();
    const h = this.health.get(agent.id)!;
    try {
      const result = await agent.config.executor(task);
      const duration = Date.now() - start;
      const total = h.successCount + h.failureCount;
      h.avgDuration = total === 0 ? duration : (h.avgDuration * total + duration) / (total + 1);
      h.successCount++;
      h.failureCount = 0; // reset consecutive failures on success
      h.lastUsed = Date.now();
      return { agentId: agent.id, result };
    } catch (err) {
      h.failureCount++;
      h.lastUsed = Date.now();
      throw err;
    }
  }

  /** Reset health for an agent */
  resetHealth(agentId: string): void {
    if (this.health.has(agentId)) {
      this.health.set(agentId, { successCount: 0, failureCount: 0, lastUsed: 0, avgDuration: 0 });
    }
  }

  /** Convert to AgentPool for compatibility */
  toPool(): AgentPool {
    return new AgentPool({ roles: [...this.agents.values()] });
  }

  /** Broadcast a task to all healthy agents in parallel */
  async broadcast(task: string, capability?: string): Promise<Array<{ agentId: string; result: string }>> {
    const healthy = [...this.agents.values()].filter(a => this.isHealthy(a.id));
    const candidates = capability
      ? healthy.filter(a => a.capabilities.includes(capability) || a.capabilities.includes("*"))
      : healthy;
    const results = await Promise.allSettled(
      candidates.map(async (agent) => {
        const start = Date.now();
        const h = this.health.get(agent.id)!;
        try {
          const result = await agent.config.executor(task);
          const duration = Date.now() - start;
          const total = h.successCount + h.failureCount;
          h.avgDuration = total === 0 ? duration : (h.avgDuration * total + duration) / (total + 1);
          h.successCount++;
          h.failureCount = 0;
          h.lastUsed = Date.now();
          return { agentId: agent.id, result };
        } catch (err) {
          h.failureCount++;
          h.lastUsed = Date.now();
          throw err;
        }
      })
    );
    return results
      .filter((r): r is PromiseFulfilledResult<{ agentId: string; result: string }> => r.status === "fulfilled")
      .map(r => r.value);
  }

  /** Get aggregate health summary */
  getHealthSummary(): { total: number; healthy: number; unhealthy: number; avgResponseTime: number } {
    const entries = [...this.health.values()];
    const healthy = entries.filter(h => h.failureCount < this.maxFailures);
    return {
      total: entries.length,
      healthy: healthy.length,
      unhealthy: entries.length - healthy.length,
      avgResponseTime: entries.length === 0 ? 0 : entries.reduce((s, h) => s + h.avgDuration, 0) / entries.length,
    };
  }

  /** Execute with automatic fallback to another agent on failure */
  async retryWithFallback(task: string, capability?: string, maxRetries: number = 3): Promise<{ agentId: string; result: string; attempts: number }> {
    let attempts = 0;
    while (attempts < maxRetries) {
      attempts++;
      try {
        return { ...await this.execute(task, capability), attempts };
      } catch {
        if (attempts >= maxRetries) break;
        // Will try a different agent next iteration since the failed one's health degraded
      }
    }
    throw new Error(`All ${attempts} attempts failed for task: ${task}`);
  }
}

/**
 * Merge results from parallel nodes into a single field.
 *
 * Usage: After fan-out (multiple edges from one node),
 * route all branches into a merge node that uses this function
 * to combine outputs into a structured summary.
 */
export function mergeResults(
  state: RouterState,
  sourceFields: string[],
  targetField: string = "mergedResult"
): Record<string, unknown> {
  const merged: Record<string, string> = {};
  for (const field of sourceFields) {
    const value = state[field];
    if (typeof value === "string") {
      merged[field] = value;
    }
  }
  return {
    [targetField]: JSON.stringify(merged),
  };
}

/**
 * Create a sequential router that visits steps in order,
 * skipping already-completed ones.
 */
export function sequentialRouter(steps: string[]) {
  return (state: RouterState): string => {
    const completed = new Set(state.completedSteps ?? []);
    for (const step of steps) {
      if (!completed.has(step)) return step;
    }
    return END;
  };
}

/**
 * Create a conditional router that checks a state field
 * to decide which branch to enter.
 */
export function conditionalRouter(
  field: string,
  mapping: Record<string, string>,
  fallback: string = END
) {
  return (state: RouterState): string => {
    const value = state[field];
    if (typeof value === "string" && mapping[value]) return mapping[value];
    return fallback;
  };
}
