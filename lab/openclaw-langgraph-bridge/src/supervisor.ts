/**
 * Preset supervisor routers + Supervisor class for dynamic agent management.
 */

import { END } from "@langchain/langgraph";
import { type AgentRole, AgentPool } from "./multi-agent.js";
import { TaskQueue, type QueueTask } from "./task-queue.js";

export interface RouterState {
  completedSteps?: string[];
  [key: string]: unknown;
}

// ── Supervisor ─────────────────────────────────────────

export type CircuitState = "closed" | "open" | "half-open";

export interface AgentHealth {
  successCount: number;
  failureCount: number;
  lastUsed: number;
  avgDuration: number;
  /** History of recent events for observability */
  history: Array<{ ts: number; event: "success" | "failure"; duration: number }>;
  /** Circuit breaker state */
  circuit: CircuitState;
  /** Timestamp when circuit opened (for recovery timeout) */
  circuitOpenedAt?: number;
}

export interface SupervisorConfig {
  /** Maximum consecutive failures before marking agent unhealthy (default: 3) */
  maxFailures?: number;
  /** Route strategy: "round-robin" | "least-busy" | "random" | "weighted" (default: "round-robin") */
  strategy?: "round-robin" | "least-busy" | "random" | "weighted";
  /** Max history entries per agent (default: 100) */
  maxHistory?: number;
  /** Circuit breaker recovery timeout in ms (default: 30000) */
  circuitRecoveryMs?: number;
}

export class Supervisor {
  private agents: Map<string, AgentRole> = new Map();
  private health: Map<string, AgentHealth> = new Map();
  private rrIndex = 0;
  private maxFailures: number;
  private strategy: NonNullable<SupervisorConfig["strategy"]>;
  private maxHistory: number;
  private circuitRecoveryMs: number;

  constructor(config: SupervisorConfig = {}) {
    this.maxFailures = config.maxFailures ?? 3;
    this.strategy = config.strategy ?? "round-robin";
    this.maxHistory = config.maxHistory ?? 100;
    this.circuitRecoveryMs = config.circuitRecoveryMs ?? 30000;
  }

  /** Register a new agent */
  register(role: AgentRole): this {
    this.agents.set(role.id, role);
    this.health.set(role.id, {
      successCount: 0, failureCount: 0, lastUsed: 0, avgDuration: 0, history: [],
      circuit: "closed",
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

  /** Check if agent is healthy (circuit breaker logic) */
  isHealthy(agentId: string): boolean {
    const h = this.health.get(agentId);
    if (!h) return false;
    this._updateCircuit(agentId);
    return h.circuit !== "open";
  }

  /** Get circuit breaker state for an agent */
  getCircuitState(agentId: string): CircuitState {
    const h = this.health.get(agentId);
    if (!h) return "closed";
    this._updateCircuit(agentId);
    return h.circuit;
  }

  /** Update circuit state based on recovery timeout */
  private _updateCircuit(agentId: string): void {
    const h = this.health.get(agentId);
    if (!h || h.circuit !== "open") return;
    if (h.circuitOpenedAt && Date.now() - h.circuitOpenedAt >= this.circuitRecoveryMs) {
      h.circuit = "half-open";
    }
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
      case "weighted": {
        // Weighted random: success rate as weight
        const weights = candidates.map(a => {
          const h = this.health.get(a.id)!;
          const total = h.successCount + h.failureCount;
          return total === 0 ? 1 : h.successCount / total;
        });
        const sum = weights.reduce((a, b) => a + b, 0);
        if (sum === 0) return candidates[0];
        let r = Math.random() * sum;
        for (let i = 0; i < candidates.length; i++) {
          r -= weights[i];
          if (r <= 0) return candidates[i];
        }
        return candidates[candidates.length - 1];
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
      if (h.circuit === "half-open") h.circuit = "closed"; // recover on success
      h.lastUsed = Date.now();
      this._recordHistory(agent.id, 'success', duration);
      return { agentId: agent.id, result };
    } catch (err) {
      h.failureCount++;
      if (h.failureCount >= this.maxFailures) {
        h.circuit = "open";
        h.circuitOpenedAt = Date.now();
      }
      h.lastUsed = Date.now();
      this._recordHistory(agent.id, 'failure', Date.now() - start);
      throw err;
    }
  }

  /** Get execution history for an agent */
  getHistory(agentId: string, limit?: number): AgentHealth["history"] {
    const h = this.health.get(agentId);
    if (!h) return [];
    const hist = [...h.history].reverse(); // newest first
    return limit ? hist.slice(0, limit) : hist;
  }

  /** Record a health event */
  private _recordHistory(agentId: string, event: "success" | "failure", duration: number): void {
    const h = this.health.get(agentId);
    if (!h) return;
    h.history.push({ ts: Date.now(), event, duration });
    if (h.history.length > this.maxHistory) {
      h.history = h.history.slice(-this.maxHistory);
    }
  }

  /** Reset health for an agent */
  resetHealth(agentId: string): void {
    if (this.health.has(agentId)) {
      this.health.set(agentId, { successCount: 0, failureCount: 0, lastUsed: 0, avgDuration: 0, history: [], circuit: "closed" });
    }
  }

  /** Serialize supervisor state (agents + health) to JSON-safe object */
  saveState(): {
    agents: Array<{ id: string; description: string; capabilities: string[] }>;
    health: Record<string, AgentHealth>;
    strategy: string;
  } {
    const agents = [...this.agents.values()].map(a => ({
      id: a.id, description: a.description, capabilities: a.capabilities,
    }));
    const health: Record<string, AgentHealth> = {};
    for (const [id, h] of this.health) {
      health[id] = { ...h, history: [...h.history] };
    }
    return { agents, health, strategy: this.strategy };
  }

  /** Restore supervisor state from a previously saved snapshot */
  loadState(state: ReturnType<Supervisor["saveState"]>): void {
    this.agents.clear();
    this.health.clear();
    for (const a of state.agents) {
      // Register as minimal stub — executor not serializable
      this.agents.set(a.id, {
        id: a.id,
        description: a.description ?? "",
        capabilities: a.capabilities,
        config: { name: a.id, systemPrompt: "", executor: async () => "" },
      });
      const h = state.health[a.id];
      if (h) {
        this.health.set(a.id, { ...h, history: [...h.history], circuit: h.circuit ?? "closed" });
      } else {
        this.health.set(a.id, { successCount: 0, failureCount: 0, lastUsed: 0, avgDuration: 0, history: [], circuit: "closed" });
      }
    }
    this.strategy = state.strategy as NonNullable<SupervisorConfig["strategy"]>;
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

  /** Process all tasks from a TaskQueue, returning results in order */
  async processQueue(queue: TaskQueue): Promise<Array<{ taskId: string; agentId: string; result: string }>> {
    const results: Array<{ taskId: string; agentId: string; result: string }> = [];
    const failed: QueueTask[] = [];
    while (!queue.isEmpty) {
      const task = queue.dequeue();
      if (!task) break;
      try {
        const { agentId, result } = await this.execute(task.payload, task.capability);
        results.push({ taskId: task.id, agentId, result });
      } catch {
        failed.push(task);
      }
    }
    // Re-enqueue failed tasks
    for (const t of failed) queue.enqueue(t);
    return results;
  }

  /** Process queue tasks in parallel, limited concurrency */
  async processQueueParallel(queue: TaskQueue, concurrency: number = 4): Promise<Array<{ taskId: string; agentId: string; result: string }>> {
    const all = queue.drain();
    const results: Array<{ taskId: string; agentId: string; result: string }> = [];
    const failed: QueueTask[] = [];
    // Process in batches
    for (let i = 0; i < all.length; i += concurrency) {
      const batch = all.slice(i, i + concurrency);
      const settled = await Promise.allSettled(
        batch.map(async (task) => {
          const { agentId, result } = await this.execute(task.payload, task.capability);
          return { taskId: task.id, agentId, result };
        })
      );
      for (let j = 0; j < settled.length; j++) {
        const s = settled[j];
        if (s.status === "fulfilled") {
          results.push(s.value);
        } else {
          failed.push(batch[j]);
        }
      }
    }
    for (const t of failed) queue.enqueue(t);
    return results;
  }

  /** High-level delegation: capability match + load balance + fallback */
  async delegate(
    task: string,
    opts?: { capability?: string; maxRetries?: number; preferAgent?: string }
  ): Promise<{ agentId: string; result: string; attempts: number; fallbackUsed: boolean }> {
    const maxRetries = opts?.maxRetries ?? 3;
    // If preferAgent specified and healthy, try it first
    if (opts?.preferAgent) {
      const h = this.health.get(opts.preferAgent);
      if (h && h.failureCount < this.maxFailures) {
        try {
          const r = await this.execute(task, opts?.capability);
          if (r.agentId === opts.preferAgent) {
            return { ...r, attempts: 1, fallbackUsed: false };
          }
        } catch { /* fall through */ }
      }
    }
    // Try with fallback
    let attempts = 0;
    let lastError: Error | null = null;
    while (attempts < maxRetries) {
      attempts++;
      try {
        const r = await this.execute(task, opts?.capability);
        return { ...r, attempts, fallbackUsed: attempts > 1 };
      } catch (e) {
        lastError = e instanceof Error ? e : new Error(String(e));
      }
    }
    throw lastError ?? new Error(`delegate failed after ${attempts} attempts`);
  }

  /** Per-agent health report */
  healthReport(): Array<{ agentId: string; healthy: boolean; failureCount: number; avgDuration: number; capabilities: string[] }> {
    return [...this.health.entries()].map(([id, h]) => {
      const agent = [...this.agents.values()].find(a => a.id === id);
      return {
        agentId: id,
        healthy: h.failureCount < this.maxFailures,
        failureCount: h.failureCount,
        avgDuration: Math.round(h.avgDuration * 100) / 100,
        capabilities: agent?.capabilities ?? [],
      };
    });
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
