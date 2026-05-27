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
});
