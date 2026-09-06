/**
 * Tests for batch — parallel node execution
 * Run: npm run build && node --test test/batch.test.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { batch } from "../dist/batch.js";

describe("batch", () => {
  it("runs all nodes in parallel and merges results", async () => {
    const order = [];
    const node = (id, ms) => async () => {
      await new Promise((r) => setTimeout(r, ms));
      order.push(id);
      return { [`key${id}`]: id };
    };

    const run = batch({
      name: "parallel",
      nodes: [node(1, 30), node(2, 10), node(3, 20)],
    });

    const result = await run({});
    assert.equal(result.key1, 1);
    assert.equal(result.key2, 2);
    assert.equal(result.key3, 3);
    assert.equal(result.completedCount, 3);
    assert.equal(order[0], 2);
  });

  it("respects concurrency limit", async () => {
    let active = 0;
    let maxActive = 0;

    const node = (id) => async () => {
      active++;
      maxActive = Math.max(maxActive, active);
      await new Promise((r) => setTimeout(r, 20));
      active--;
      return { [`n${id}`]: id };
    };

    const run = batch({
      name: "limited",
      nodes: [node(1), node(2), node(3), node(4), node(5)],
      concurrency: 2,
    });

    const result = await run({});
    assert.equal(result.completedCount, 5);
    assert.ok(maxActive <= 2, `maxActive was ${maxActive}, expected <= 2`);
  });

  it("passes state to all nodes", async () => {
    const run = batch({
      name: "state",
      nodes: [
        async (state) => ({ doubled: state.x * 2 }),
        async (state) => ({ tripled: state.x * 3 }),
      ],
    });

    const result = await run({ x: 5 });
    assert.equal(result.doubled, 10);
    assert.equal(result.tripled, 15);
  });

  it("throws on first error by default", async () => {
    const run = batch({
      name: "fail",
      nodes: [
        async () => ({ ok: true }),
        async () => { throw new Error("boom"); },
      ],
    });

    await assert.rejects(() => run({}), /boom/);
  });

  it("continues on error when continueOnError is true", async () => {
    const run = batch({
      name: "tolerant",
      nodes: [
        async () => ({ a: 1 }),
        async () => { throw new Error("fail"); },
        async () => ({ c: 3 }),
      ],
      continueOnError: true,
    });

    const result = await run({});
    assert.equal(result.a, 1);
    assert.equal(result.c, 3);
    assert.equal(result.completedCount, 2);
    assert.ok(result.tolerantErrors);
  });

  it("handles empty nodes array", async () => {
    const run = batch({ name: "empty", nodes: [] });
    const result = await run({});
    assert.equal(result.completedCount, 0);
  });

  it("handles single node", async () => {
    const run = batch({
      name: "single",
      nodes: [async () => ({ solo: true })],
    });
    const result = await run({});
    assert.equal(result.solo, true);
    assert.equal(result.completedCount, 1);
  });

  it("concurrency=1 runs sequentially", async () => {
    const order = [];
    const node = (id) => async () => {
      order.push(id);
      await new Promise((r) => setTimeout(r, 10));
      return { [`n${id}`]: id };
    };

    const run = batch({
      name: "seq",
      nodes: [node(1), node(2), node(3)],
      concurrency: 1,
    });

    await run({});
    assert.deepEqual(order, [1, 2, 3]);
  });
});

describe("batch config validation (C1 red-first)", () => {
  const noop = async () => ({ x: 1 });

  it("concurrency=0 must NOT silently run zero nodes (fails at construction)", () => {
    assert.throws(() => batch({ name: "b", nodes: [noop, noop], concurrency: 0 }), RangeError);
  });

  it("concurrency negative must throw RangeError", () => {
    assert.throws(() => batch({ name: "b", nodes: [noop], concurrency: -3 }), RangeError);
  });

  it("concurrency fractional < 1 must throw RangeError (would mean 0 workers)", () => {
    assert.throws(() => batch({ name: "b", nodes: [noop], concurrency: 0.5 }), RangeError);
  });

  it("concurrency NaN must throw RangeError", () => {
    assert.throws(() => batch({ name: "b", nodes: [noop], concurrency: NaN }), RangeError);
  });

  it("valid edge: concurrency=1 still runs all nodes", async () => {
    let calls = 0;
    const run = batch({ name: "b", nodes: [async () => { calls++; return { c: calls }; }], concurrency: 1 });
    const result = await run({});
    assert.equal(calls, 1);
    assert.equal(result.completedCount, 1);
  });

  it("valid edge: concurrency=Infinity (explicit) runs all", async () => {
    let calls = 0;
    const run = batch({ name: "b", nodes: [async () => { calls++; return {}; }, async () => { calls++; return {}; }], concurrency: Infinity });
    await run({});
    assert.equal(calls, 2);
  });

  it("empty nodes array returns completedCount=0 (legit, not an error)", async () => {
    const run = batch({ name: "b", nodes: [] });
    const result = await run({});
    assert.equal(result.completedCount, 0);
  });
});
