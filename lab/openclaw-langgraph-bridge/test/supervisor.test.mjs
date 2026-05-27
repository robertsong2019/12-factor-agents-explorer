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
});
