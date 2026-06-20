import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { Supervisor } from "../dist/supervisor.js";
import { TaskQueue } from "../dist/task-queue.js";

const makeRole = (id, caps = ["*"]) => ({
  id,
  description: `Agent ${id}`,
  config: { executor: async (task) => `${id}:${task}` },
  capabilities: caps,
});

describe("Supervisor", () => {
  it("registers and lists agents", () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    s.register(makeRole("b"));
    assert.deepEqual(s.listAgents(), ["a", "b"]);
  });

  it("deregisters an agent", () => {
    const s = new Supervisor();
    s.register(makeRole("a")).register(makeRole("b"));
    assert.equal(s.deregister("a"), true);
    assert.deepEqual(s.listAgents(), ["b"]);
  });

  it("selects agents round-robin by default", () => {
    const s = new Supervisor();
    s.register(makeRole("a")).register(makeRole("b"));
    const first = s.selectAgent();
    const second = s.selectAgent();
    assert.notEqual(first.id, second.id);
  });

  it("filters by capability", () => {
    const s = new Supervisor();
    s.register(makeRole("a", ["code"])).register(makeRole("b", ["review"]));
    const agent = s.selectAgent("review");
    assert.equal(agent.id, "b");
  });

  it("executes task with selected agent", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    const { agentId, result } = await s.execute("hello");
    assert.equal(agentId, "a");
    assert.equal(result, "a:hello");
  });

  it("tracks health stats on success", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    await s.execute("t1");
    const h = s.getHealth("a");
    assert.equal(h.successCount, 1);
    assert.equal(h.failureCount, 0);
    assert.ok(h.avgDuration >= 0);
  });

  it("marks unhealthy after consecutive failures", async () => {
    const s = new Supervisor({ maxFailures: 2 });
    s.register({
      id: "bad",
      description: "always fails",
      config: { executor: async () => { throw new Error("boom"); } },
      capabilities: ["*"],
    });
    await assert.rejects(() => s.execute("t1"));
    await assert.rejects(() => s.execute("t2"));
    assert.equal(s.isHealthy("bad"), false);
  });

  it("resets consecutive failures on success", async () => {
    let callCount = 0;
    const s = new Supervisor({ maxFailures: 2 });
    s.register({
      id: "flaky",
      description: "flaky",
      config: { executor: async () => { callCount++; if (callCount === 1) throw new Error("once"); return "ok"; } },
      capabilities: ["*"],
    });
    await assert.rejects(() => s.execute("t1"));
    assert.equal(s.isHealthy("flaky"), true); // 1 failure, maxFailures=2
    await s.execute("t2");
    assert.equal(s.getHealth("flaky").failureCount, 0); // reset on success
  });

  it("resetHealth clears stats", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    await s.execute("t1");
    s.resetHealth("a");
    assert.equal(s.getHealth("a").successCount, 0);
  });

  it("throws when no healthy agent available", async () => {
    const s = new Supervisor();
    await assert.rejects(() => s.execute("t"), /No healthy agent/);
  });

  it("toPool creates a compatible AgentPool", () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    const pool = s.toPool();
    assert.equal(pool.listRoles().length, 1);
  });

  it("broadcast sends to all healthy agents", async () => {
    const s = new Supervisor();
    s.register(makeRole("a")).register(makeRole("b")).register(makeRole("c"));
    const results = await s.broadcast("hello");
    assert.equal(results.length, 3);
    const ids = results.map(r => r.agentId).sort();
    assert.deepEqual(ids, ["a", "b", "c"]);
  });

  it("broadcast skips unhealthy agents", async () => {
    const s = new Supervisor({ maxFailures: 1, strategy: "least-busy" });
    // First, make 'bad' unhealthy by executing directly
    s.register(makeRole("a"));
    s.register({
      id: "bad", description: "fails",
      config: { executor: async () => { throw new Error("no"); } },
      capabilities: ["*"],
    });
    // Execute with 'a' first so it has more usage
    await s.execute("t1");
    // Now 'bad' is least-busy, next execute will pick it
    await assert.rejects(() => s.execute("t2"));
    assert.equal(s.isHealthy("bad"), false);
    const results = await s.broadcast("hello");
    assert.equal(results.length, 1);
    assert.equal(results[0].agentId, "a");
  });

  it("broadcast filters by capability", async () => {
    const s = new Supervisor();
    s.register(makeRole("a", ["code"])).register(makeRole("b", ["review"]));
    const results = await s.broadcast("task", "code");
    assert.equal(results.length, 1);
    assert.equal(results[0].agentId, "a");
  });

  it("getHealthSummary returns aggregate stats", async () => {
    const s = new Supervisor();
    s.register(makeRole("a")).register(makeRole("b"));
    await s.execute("t1");
    const summary = s.getHealthSummary();
    assert.equal(summary.total, 2);
    assert.equal(summary.healthy, 2);
    assert.equal(summary.unhealthy, 0);
    assert.ok(summary.avgResponseTime >= 0);
  });

  it("getHealthSummary tracks unhealthy agents", async () => {
    const s = new Supervisor({ maxFailures: 1, strategy: "least-busy" });
    s.register(makeRole("a"));
    s.register({
      id: "bad", description: "fails",
      config: { executor: async () => { throw new Error("no"); } },
      capabilities: ["*"],
    });
    await s.execute("t1"); // uses 'a'
    await assert.rejects(() => s.execute("t2")); // uses 'bad', fails
    const summary = s.getHealthSummary();
    assert.equal(summary.unhealthy, 1);
    assert.equal(summary.healthy, 1);
  });

  it("retryWithFallback falls back to healthy agent", async () => {
    let badCalls = 0;
    const s = new Supervisor({ maxFailures: 1 });
    s.register({
      id: "bad", description: "fails",
      config: { executor: async () => { badCalls++; throw new Error("no"); } },
      capabilities: ["*"],
    });
    s.register(makeRole("good"));
    // Round-robin: first call hits 'bad', fails; second call hits 'good', succeeds
    // But after 1 failure with maxFailures=1, 'bad' is unhealthy, so execute() will skip it
    const result = await s.retryWithFallback("task");
    assert.equal(result.agentId, "good");
    assert.ok(result.attempts >= 2);
  });

  it("retryWithFallback throws when all retries exhausted", async () => {
    const s = new Supervisor({ maxFailures: 5 });
    s.register({
      id: "bad", description: "always fails",
      config: { executor: async () => { throw new Error("no"); } },
      capabilities: ["*"],
    });
    await assert.rejects(() => s.retryWithFallback("task", undefined, 2), /All 2 attempts failed/);
  });

  // ── Weighted strategy ───────────────────────────────
  it("weighted strategy selects from candidates", () => {
    const s = new Supervisor({ strategy: "weighted" });
    s.register(makeRole("a")).register(makeRole("b"));
    // Should always return a valid agent
    const agent = s.selectAgent();
    assert.ok(agent);
    assert.ok(["a", "b"].includes(agent.id));
  });

  // ── History tracking ───────────────────────────────
  it("records history on execute", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    await s.execute("t1");
    const hist = s.getHistory("a");
    assert.equal(hist.length, 1);
    assert.equal(hist[0].event, "success");
    assert.ok(hist[0].duration >= 0);
  });

  it("records failure in history", async () => {
    const s = new Supervisor();
    s.register({
      id: "bad", description: "fails",
      config: { executor: async () => { throw new Error("boom"); } },
      capabilities: ["*"],
    });
    await assert.rejects(() => s.execute("t1"));
    const hist = s.getHistory("bad");
    assert.equal(hist.length, 1);
    assert.equal(hist[0].event, "failure");
  });

  it("getHistory returns empty for unknown agent", () => {
    const s = new Supervisor();
    assert.deepEqual(s.getHistory("nope"), []);
  });

  it("getHistory respects limit", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    for (let i = 0; i < 5; i++) await s.execute(`t${i}`);
    const limited = s.getHistory("a", 2);
    assert.equal(limited.length, 2);
  });

  it("history respects maxHistory config", async () => {
    const s = new Supervisor({ maxHistory: 3 });
    s.register(makeRole("a"));
    for (let i = 0; i < 5; i++) await s.execute(`t${i}`);
    const hist = s.getHistory("a");
    assert.equal(hist.length, 3);
  });

  it("resetHealth clears history", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    await s.execute("t1");
    s.resetHealth("a");
    assert.equal(s.getHistory("a").length, 0);
  });

  // ── saveState / loadState ──
  it("saveState serializes agents and health", async () => {
    const s = new Supervisor({ strategy: "round-robin" });
    s.register(makeRole("a"));
    s.register(makeRole("b"));
    const res = await s.execute("t1");
    const state = s.saveState();
    assert.equal(state.agents.length, 2);
    assert.equal(state.strategy, "round-robin");
    assert.ok(state.health[res.agentId]);
    assert.equal(state.health[res.agentId].successCount, 1);
    assert.ok(state.health[res.agentId].history.length > 0);
  });

  it("loadState restores agents and health", async () => {
    const s1 = new Supervisor({ strategy: "round-robin" });
    s1.register(makeRole("x"));
    await s1.execute("t1");
    await s1.execute("t2");
    const state = s1.saveState();

    const s2 = new Supervisor();
    s2.loadState(state);
    assert.deepEqual(s2.listAgents(), ["x"]);
    assert.equal(s2.getHealth("x").successCount, 2);
    assert.equal(s2["strategy"], "round-robin");
  });

  it("loadState handles missing health gracefully", () => {
    const s = new Supervisor();
    s.loadState({
      agents: [{ id: "z", description: "", capabilities: ["test"] }],
      health: {},
      strategy: "round-robin",
    });
    assert.ok(s.isHealthy("z"));
    assert.equal(s.getHealth("z").successCount, 0);
  });

  it("saveState → JSON.stringify → loadState round-trip", async () => {
    const s1 = new Supervisor();
    s1.register(makeRole("a"));
    await s1.execute("t1");
    const json = JSON.stringify(s1.saveState());

    const s2 = new Supervisor();
    s2.loadState(JSON.parse(json));
    assert.equal(s2.listAgents().length, 1);
    assert.equal(s2.getHealth("a").successCount, 1);
  });

  // ── Circuit Breaker ────────────────────────────────
  it("circuit starts closed", () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    assert.equal(s.getCircuitState("a"), "closed");
  });

  it("circuit opens after maxFailures consecutive failures", async () => {
    const s = new Supervisor({ maxFailures: 2 });
    s.register({
      id: "bad", description: "fails",
      config: { executor: async () => { throw new Error("boom"); } },
      capabilities: ["*"],
    });
    await assert.rejects(() => s.execute("t1"));
    assert.equal(s.getCircuitState("bad"), "closed"); // 1 failure, need 2
    await assert.rejects(() => s.execute("t2"));
    assert.equal(s.getCircuitState("bad"), "open"); // 2 failures = open
  });

  it("open circuit blocks agent selection", async () => {
    const s = new Supervisor({ maxFailures: 1, strategy: "least-busy" });
    s.register({
      id: "bad", description: "fails",
      config: { executor: async () => { throw new Error("boom"); } },
      capabilities: ["*"],
    });
    s.register(makeRole("good"));
    // least-busy: both at 0, but 'bad' registered first → picked first
    await assert.rejects(() => s.execute("t1"));
    assert.equal(s.getCircuitState("bad"), "open");
    const agent = s.selectAgent();
    assert.equal(agent.id, "good");
  });

  it("circuit transitions to half-open after recovery timeout", async () => {
    const s = new Supervisor({ maxFailures: 1, circuitRecoveryMs: 50 });
    s.register({
      id: "bad", description: "fails",
      config: { executor: async () => { throw new Error("boom"); } },
      capabilities: ["*"],
    });
    await assert.rejects(() => s.execute("t1"));
    assert.equal(s.getCircuitState("bad"), "open");
    // Wait for recovery
    await new Promise(r => setTimeout(r, 60));
    assert.equal(s.getCircuitState("bad"), "half-open");
  });

  it("half-open circuit closes on success", async () => {
    let calls = 0;
    const s = new Supervisor({ maxFailures: 1, circuitRecoveryMs: 50 });
    s.register({
      id: "flaky", description: "flaky",
      config: { executor: async () => { calls++; if (calls === 1) throw new Error("boom"); return "ok"; } },
      capabilities: ["*"],
    });
    await assert.rejects(() => s.execute("t1"));
    assert.equal(s.getCircuitState("flaky"), "open");
    await new Promise(r => setTimeout(r, 60));
    assert.equal(s.getCircuitState("flaky"), "half-open");
    await s.execute("t2");
    assert.equal(s.getCircuitState("flaky"), "closed");
  });

  it("half-open circuit reopens on failure", async () => {
    const s = new Supervisor({ maxFailures: 1, circuitRecoveryMs: 50 });
    s.register({
      id: "bad", description: "always fails",
      config: { executor: async () => { throw new Error("boom"); } },
      capabilities: ["*"],
    });
    await assert.rejects(() => s.execute("t1"));
    assert.equal(s.getCircuitState("bad"), "open");
    await new Promise(r => setTimeout(r, 60));
    assert.equal(s.getCircuitState("bad"), "half-open");
    await assert.rejects(() => s.execute("t2"));
    assert.equal(s.getCircuitState("bad"), "open");
  });

  it("resetHealth resets circuit to closed", async () => {
    const s = new Supervisor({ maxFailures: 1 });
    s.register({
      id: "bad", description: "fails",
      config: { executor: async () => { throw new Error("boom"); } },
      capabilities: ["*"],
    });
    await assert.rejects(() => s.execute("t1"));
    assert.equal(s.getCircuitState("bad"), "open");
    s.resetHealth("bad");
    assert.equal(s.getCircuitState("bad"), "closed");
  });

  it("getCircuitState returns closed for unknown agent", () => {
    const s = new Supervisor();
    assert.equal(s.getCircuitState("nope"), "closed");
  });

  // ── processQueue ────────────────────────────────
  it("processQueue drains tasks and returns results", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    const q = new TaskQueue();
    q.enqueue({ id: "t1", payload: "hello" });
    q.enqueue({ id: "t2", payload: "world" });
    const results = await s.processQueue(q);
    assert.equal(results.length, 2);
    assert.equal(results[0].taskId, "t1");
    assert.equal(results[0].result, "a:hello");
    assert.equal(results[1].taskId, "t2");
    assert.equal(q.isEmpty, true);
  });

  it("processQueue respects task priority", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    const q = new TaskQueue();
    q.enqueue({ id: "low", payload: "low", priority: 1 });
    q.enqueue({ id: "high", payload: "high", priority: 10 });
    const results = await s.processQueue(q);
    assert.equal(results[0].taskId, "high");
    assert.equal(results[1].taskId, "low");
  });

  it("processQueue re-enqueues failed tasks", async () => {
    const s = new Supervisor({ maxFailures: 5 });
    let calls = 0;
    s.register({
      id: "flaky", description: "flaky",
      config: { executor: async (task) => { calls++; if (task === "fail") throw new Error("boom"); return `ok:${task}`; } },
      capabilities: ["*"],
    });
    const q = new TaskQueue();
    q.enqueue({ id: "good", payload: "good" });
    q.enqueue({ id: "bad", payload: "fail" });
    const results = await s.processQueue(q);
    assert.equal(results.length, 1); // only good succeeded
    assert.equal(results[0].taskId, "good");
    assert.equal(q.size, 1); // bad re-enqueued
    assert.equal(q.peek().id, "bad");
  });

  it("processQueue with empty queue returns empty results", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    const q = new TaskQueue();
    const results = await s.processQueue(q);
    assert.equal(results.length, 0);
  });

  // ── processQueueParallel ────────────────────────────
  it("processQueueParallel processes tasks concurrently", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    s.register(makeRole("b"));
    const q = new TaskQueue();
    for (let i = 0; i < 6; i++) q.enqueue({ id: `t${i}`, payload: `task${i}` });
    const results = await s.processQueueParallel(q, 3);
    assert.equal(results.length, 6);
    assert.equal(q.isEmpty, true);
  });

  it("processQueueParallel re-enqueues failures", async () => {
    const s = new Supervisor({ maxFailures: 10 });
    s.register({
      id: "bad", description: "fails",
      config: { executor: async (task) => { if (task === "fail") throw new Error("boom"); return `ok:${task}`; } },
      capabilities: ["*"],
    });
    const q = new TaskQueue();
    q.enqueue({ id: "good", payload: "good" });
    q.enqueue({ id: "bad", payload: "fail" });
    q.enqueue({ id: "good2", payload: "good2" });
    const results = await s.processQueueParallel(q, 10);
    assert.equal(results.length, 2);
    assert.equal(q.size, 1);
    assert.equal(q.peek().id, "bad");
  });

  it("processQueueParallel with empty queue", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    const results = await s.processQueueParallel(new TaskQueue());
    assert.equal(results.length, 0);
  });

  // ── delegate ────────────────────────────────
  it("delegate prefers specified agent", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    s.register(makeRole("b"));
    const r = await s.delegate("task", { preferAgent: "b" });
    assert.equal(r.agentId, "b");
    assert.equal(r.attempts, 1);
    assert.equal(r.fallbackUsed, false);
  });

  it("delegate falls back when preferred agent unhealthy", async () => {
    const s = new Supervisor({ maxFailures: 1 });
    s.register({
      id: "bad", description: "fails",
      config: { executor: async () => { throw new Error("boom"); } },
      capabilities: ["*"],
    });
    s.register(makeRole("good"));
    await assert.rejects(() => s.execute("t1")); // break bad
    const r = await s.delegate("task", { preferAgent: "bad" });
    assert.equal(r.agentId, "good");
  });

  it("delegate retries on failure", async () => {
    const s = new Supervisor({ maxFailures: 10 });
    let calls = 0;
    s.register({
      id: "flaky", description: "flaky",
      config: { executor: async () => { calls++; if (calls < 2) throw new Error("boom"); return "ok"; } },
      capabilities: ["*"],
    });
    const r = await s.delegate("task", { maxRetries: 3 });
    assert.equal(r.result, "ok");
    assert.equal(r.attempts, 2);
    assert.equal(r.fallbackUsed, true);
  });

  it("delegate throws after max retries", async () => {
    const s = new Supervisor({ maxFailures: 10 });
    s.register({
      id: "bad", description: "fails",
      config: { executor: async () => { throw new Error("boom"); } },
      capabilities: ["*"],
    });
    await assert.rejects(() => s.delegate("task", { maxRetries: 2 }), /boom/);
  });

  it("delegate with capability filter", async () => {
    const s = new Supervisor();
    s.register({ id: "a", description: "a", config: { executor: async (t) => `a:${t}` }, capabilities: ["math"] });
    s.register({ id: "b", description: "b", config: { executor: async (t) => `b:${t}` }, capabilities: ["code"] });
    const r = await s.delegate("task", { capability: "code" });
    assert.equal(r.agentId, "b");
  });

  // ── healthReport ────────────────────────────────
  it("healthReport returns per-agent details", () => {
    const s = new Supervisor();
    s.register({ id: "a", description: "a", config: { executor: async () => "" }, capabilities: ["math", "code"] });
    s.register({ id: "b", description: "b", config: { executor: async () => "" }, capabilities: ["code"] });
    const report = s.healthReport();
    assert.equal(report.length, 2);
    const a = report.find(r => r.agentId === "a");
    assert.equal(a.healthy, true);
    assert.deepEqual(a.capabilities, ["math", "code"]);
  });

  it("healthReport shows unhealthy agent", async () => {
    const s = new Supervisor({ maxFailures: 1 });
    s.register({ id: "bad", description: "fails", config: { executor: async () => { throw new Error("boom"); } }, capabilities: ["*"] });
    await assert.rejects(() => s.execute("t1"));
    const report = s.healthReport();
    assert.equal(report[0].healthy, false);
    assert.ok(report[0].failureCount >= 1);
  });

  it("healthReport empty for no agents", () => {
    const s = new Supervisor();
    assert.deepEqual(s.healthReport(), []);
  });

  // ── getMetrics ─────────────────────────────────
  it("getMetrics returns undefined for unknown agent", () => {
    const s = new Supervisor();
    assert.equal(s.getMetrics("nope"), undefined);
  });

  it("getMetrics returns zeroed stats for new agent", () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    const m = s.getMetrics("a");
    assert.equal(m.totalRequests, 0);
    assert.equal(m.successRate, 0);
    assert.equal(m.errorRate, 0);
    assert.equal(m.p50Latency, 0);
    assert.equal(m.p95Latency, 0);
    assert.equal(m.p99Latency, 0);
    assert.equal(m.throughputPerMin, 0);
  });

  it("getMetrics computes success/error rates", async () => {
    const s = new Supervisor({ maxFailures: 10 });
    let call = 0;
    s.register({
      id: "a", description: "",
      config: { executor: async () => { call++; if (call === 2) throw new Error("boom"); return "ok"; } },
      capabilities: ["*"],
    });
    await s.execute("t1"); // success
    await assert.rejects(() => s.execute("t2")); // failure
    await s.execute("t3"); // success
    const m = s.getMetrics("a");
    assert.equal(m.totalRequests, 3);
    assert.equal(m.successCount, 2);
    assert.equal(m.failureCount, 1);
    assert.ok(m.successRate > 0.6 && m.successRate < 0.7);
    assert.ok(m.errorRate > 0.3 && m.errorRate < 0.34);
  });

  it("getMetrics computes latency percentiles from history", async () => {
    const s = new Supervisor({ maxHistory: 100 });
    s.register({
      id: "a", description: "",
      config: { executor: async () => { await new Promise(r => setTimeout(r, 5)); return "ok"; } },
      capabilities: ["*"],
    });
    for (let i = 0; i < 10; i++) await s.execute(`t${i}`);
    const m = s.getMetrics("a");
    assert.equal(m.totalRequests, 10);
    assert.ok(m.p50Latency >= 0);
    assert.ok(m.p95Latency >= m.p50Latency);
    assert.ok(m.p99Latency >= m.p95Latency);
    assert.ok(m.avgLatency >= 0);
  });

  it("getMetrics tracks throughput (requests in last 60s)", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    for (let i = 0; i < 5; i++) await s.execute(`t${i}`);
    const m = s.getMetrics("a");
    assert.equal(m.throughputPerMin, 5); // all 5 are recent
  });

  it("getMetrics avgLatency is rounded", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    await s.execute("t1");
    const m = s.getMetrics("a");
    // Should be rounded to 2 decimal places
    const decimals = (m.avgLatency.toString().split(".")[1] || "").length;
    assert.ok(decimals <= 2);
  });

  // ── getPoolMetrics ────────────────────────────────
  it("getPoolMetrics returns zeros for no agents", () => {
    const s = new Supervisor();
    const m = s.getPoolMetrics();
    assert.equal(m.totalRequests, 0);
    assert.equal(m.overallErrorRate, 0);
    assert.equal(m.activeAgents, 0);
    assert.equal(m.circuitOpenAgents, 0);
  });

  it("getPoolMetrics aggregates across agents", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    s.register(makeRole("b"));
    await s.execute("t1"); // a
    await s.execute("t2"); // b
    const m = s.getPoolMetrics();
    assert.equal(m.totalRequests, 2);
    assert.equal(m.totalErrors, 0);
    assert.equal(m.overallErrorRate, 0);
    assert.equal(m.activeAgents, 2);
    assert.equal(m.circuitOpenAgents, 0);
    assert.equal(m.throughputPerMin, 2);
  });

  it("getPoolMetrics tracks circuit-open agents", async () => {
    const s = new Supervisor({ maxFailures: 1 });
    s.register({
      id: "bad", description: "",
      config: { executor: async () => { throw new Error("boom"); } },
      capabilities: ["*"],
    });
    s.register(makeRole("good"));
    await assert.rejects(() => s.execute("t1")); // bad circuit opens
    const m = s.getPoolMetrics();
    assert.equal(m.circuitOpenAgents, 1);
    assert.equal(m.activeAgents, 1);
    assert.equal(m.totalRequests, 1);
    assert.equal(m.totalErrors, 1);
    assert.ok(m.overallErrorRate > 0);
  });

  it("getPoolMetrics computes pool-wide percentiles", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    s.register(makeRole("b"));
    for (let i = 0; i < 6; i++) await s.execute(`t${i}`);
    const m = s.getPoolMetrics();
    // 6 total events across 2 agents
    assert.ok(m.p50Latency >= 0);
    assert.ok(m.p95Latency >= m.p50Latency);
    assert.ok(m.p99Latency >= m.p95Latency);
  });

  it("getPoolMetrics avgLatency is averaged across agents", async () => {
    const s = new Supervisor();
    s.register(makeRole("a"));
    s.register(makeRole("b"));
    await s.execute("t1");
    await s.execute("t2");
    const m = s.getPoolMetrics();
    assert.ok(m.avgLatency >= 0);
  });
});
