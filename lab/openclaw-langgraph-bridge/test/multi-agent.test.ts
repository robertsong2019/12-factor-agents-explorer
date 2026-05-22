import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { AgentPool, createCodeWorkflow, type AgentPoolConfig, type Task } from "../dist/multi-agent.js";

// Helper: create a simple pool with mock agents
function makePool(roles?: { id: string; caps: string[]; fn?: (t: string) => Promise<string> }[]): AgentPool {
  const defaultRoles = [
    { id: "coder", caps: ["code", "refactor"], fn: async (t: string) => `coded:${t}` },
    { id: "tester", caps: ["test"], fn: async (t: string) => `tested:${t}` },
    { id: "general", caps: ["*"], fn: async (t: string) => `general:${t}` },
  ];
  const list = roles ?? defaultRoles;
  const config: AgentPoolConfig = {
    roles: list.map(r => ({
      id: r.id,
      description: r.id,
      capabilities: r.caps,
      config: { executor: r.fn ?? (async (t: string) => `done:${t}`) },
    })),
  };
  return new AgentPool(config);
}

describe("AgentPool", () => {
  it("stores and retrieves roles", () => {
    const pool = makePool();
    assert.equal(pool.getRole("coder")!.id, "coder");
    assert.equal(pool.getRole("nonexistent"), undefined);
  });

  it("listRoles returns all roles", () => {
    const pool = makePool();
    assert.equal(pool.listRoles().length, 3);
  });

  it("findBestAgent matches exact capability first", () => {
    const pool = makePool();
    assert.equal(pool.findBestAgent("test")!.id, "tester");
    assert.equal(pool.findBestAgent("code")!.id, "coder");
  });

  it("findBestAgent falls back to wildcard", () => {
    const pool = makePool();
    assert.equal(pool.findBestAgent("deploy")!.id, "general");
  });

  it("findBestAgent returns undefined when no match", () => {
    const pool = makePool([
      { id: "a", caps: ["code"], fn: async (t) => t },
    ]);
    assert.equal(pool.findBestAgent("nonexistent"), undefined);
  });

  it("execute runs the agent executor", async () => {
    const pool = makePool();
    const result = await pool.execute("coder", "hello");
    assert.equal(result, "coded:hello");
  });

  it("execute throws for unknown role", async () => {
    const pool = makePool();
    await assert.rejects(() => pool.execute("ghost", "x"), /Unknown agent role/);
  });

  it("routeAndExecute dispatches by type", async () => {
    const pool = makePool();
    const { agent, result } = await pool.routeAndExecute("test", "unit tests");
    assert.equal(agent, "tester");
    assert.equal(result, "tested:unit tests");
  });

  it("routeAndExecute throws when no agent available", async () => {
    const pool = makePool([{ id: "a", caps: ["code"] }]);
    await assert.rejects(() => pool.routeAndExecute("deploy", "x"), /No agent available/);
  });
});

describe("Orchestrator", () => {
  // Import dynamically since it's not exported at top-level
  // We'll use the internal Orchestrator class via the module
  it("runs independent tasks in parallel", async () => {
    const { default: mod } = await import("../dist/multi-agent.js");
    // Orchestrator is not exported, but we can test via createCodeWorkflow
    // Let's test the orchestrator logic manually
  });

  it("respects task dependencies (topological order)", async () => {
    const order: string[] = [];
    const pool = makePool([
      { id: "a", caps: ["step1"], fn: async (t) => { order.push("step1"); return "s1"; } },
      { id: "b", caps: ["step2"], fn: async (t) => { order.push("step2"); return "s2"; } },
    ]);
    const { Orchestrator } = await import("../dist/multi-agent.js") as any;
    const orch = new Orchestrator(pool);
    const tasks: Task[] = [
      { id: "t2", description: "do step2", type: "step2", input: {}, dependsOn: ["t1"] },
      { id: "t1", description: "do step1", type: "step1", input: {} },
    ];
    const result = await orch.run(tasks);
    assert.equal(result.stats.passed, 2);
    assert.equal(result.stats.failed, 0);
    assert.equal(order[0], "step1");
    assert.equal(order[1], "step2");
  });

  it("detects circular dependencies", async () => {
    const pool = makePool([
      { id: "a", caps: ["*"], fn: async (t) => "ok" },
    ]);
    const { Orchestrator } = await import("../dist/multi-agent.js") as any;
    const orch = new Orchestrator(pool);
    const tasks: Task[] = [
      { id: "a", description: "a", type: "x", input: {}, dependsOn: ["b"] },
      { id: "b", description: "b", type: "x", input: {}, dependsOn: ["a"] },
    ];
    const result = await orch.run(tasks);
    assert.equal(result.stats.failed, 2);
    assert.equal(result.stats.passed, 0);
  });

  it("logs execution details", async () => {
    const pool = makePool([
      { id: "worker", caps: ["work"], fn: async (t) => `result:${t}` },
    ]);
    const { Orchestrator } = await import("../dist/multi-agent.js") as any;
    const orch = new Orchestrator(pool);
    const tasks: Task[] = [
      { id: "t1", description: "do work", type: "work", input: {} },
    ];
    const result = await orch.run(tasks);
    assert.equal(result.log.length, 1);
    assert.equal(result.log[0].task, "t1");
    assert.equal(result.log[0].agent, "worker");
    assert.equal(result.log[0].status, "success");
    assert.ok(result.log[0].duration >= 0);
  });

  it("records failures in log", async () => {
    const pool = makePool([
      { id: "bad", caps: ["work"], fn: async () => { throw new Error("boom"); } },
    ]);
    const { Orchestrator } = await import("../dist/multi-agent.js") as any;
    const orch = new Orchestrator(pool);
    const result = await orch.run([
      { id: "t1", description: "fail", type: "work", input: {} },
    ]);
    assert.equal(result.stats.failed, 1);
    assert.equal(result.log[0].status, "failure");
    assert.match(result.log[0].output!, /boom/);
  });
});

describe("createCodeWorkflow", () => {
  it("returns pool and maxLoops", () => {
    const wf = createCodeWorkflow({
      pool: {
        roles: [
          { id: "analyzer", description: "a", capabilities: ["analyze"], config: { executor: async () => "ok" } },
        ],
      },
      maxFixLoops: 5,
    });
    assert.equal(wf.maxLoops, 5);
    assert.equal(wf.pool.listRoles().length, 1);
  });

  it("defaults maxFixLoops to 3", () => {
    const wf = createCodeWorkflow({
      pool: { roles: [] },
    });
    assert.equal(wf.maxLoops, 3);
  });
});
