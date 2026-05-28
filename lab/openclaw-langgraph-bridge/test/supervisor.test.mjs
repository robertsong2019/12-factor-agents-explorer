import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { Supervisor } from "../dist/supervisor.js";

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
});
