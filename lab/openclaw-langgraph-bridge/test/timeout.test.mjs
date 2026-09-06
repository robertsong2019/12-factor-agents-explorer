/**
 * Tests for withTimeout — uses built JS output
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { withTimeout } from "../dist/timeout.js";

describe("withTimeout", () => {
  it("passes through result when node completes in time", async () => {
    const node = withTimeout(
      async (state) => ({ result: `done:${state.task}` }),
      { ms: 1000 },
    );

    const result = await node({ task: "hello" });
    assert.deepEqual(result, { result: "done:hello" });
  });

  it("returns timeout error when node exceeds deadline", async () => {
    const slowNode = async (_state) => {
      await new Promise((r) => setTimeout(r, 500));
      return { result: "should not appear" };
    };

    const node = withTimeout(slowNode, { ms: 50 });
    const result = await node({ task: "slow" });

    assert.ok(result._timeoutError);
    assert.match(result._timeoutError, /timed out after 50ms/);
    assert.equal(result.result, undefined);
  });

  it("supports number shorthand for config", async () => {
    const node = withTimeout(
      async (state) => ({ result: `fast:${state.task}` }),
      2000,
    );

    const result = await node({ task: "quick" });
    assert.deepEqual(result, { result: "fast:quick" });
  });

  it("returns fallback state on timeout", async () => {
    const slowNode = async () => {
      await new Promise((r) => setTimeout(r, 500));
      return { result: "nope" };
    };

    const node = withTimeout(slowNode, {
      ms: 50,
      fallbackState: { result: "fallback" },
    });

    const result = await node({ task: "x" });
    assert.equal(result.result, "fallback");
    assert.ok(result._timeoutError);
  });

  it("re-throws non-timeout errors", async () => {
    const crashNode = async () => {
      throw new Error("something broke");
    };

    const node = withTimeout(crashNode, { ms: 1000 });
    await assert.rejects(() => node({ task: "crash" }), {
      message: "something broke",
    });
  });
});

describe("timeout classification (C4 red-first)", () => {
  it("must NOT swallow upstream errors that merely mention 'timed out'", async () => {
    const flaky = withTimeout(async () => {
      throw new Error("upstream fetch failed: request timed out after 30s");
    }, { ms: 5000 });
    await assert.rejects(
      () => flaky({}),
      (err) => err.message.includes("upstream fetch failed"),
      "upstream error must propagate, not become _timeoutError"
    );
  });

  it("genuine timeout still returns _timeoutError", async () => {
    const slow = withTimeout(async () => {
      await new Promise((r) => setTimeout(r, 200));
      return { done: true };
    }, { ms: 30 });
    const result = await slow({});
    assert.ok(result._timeoutError.includes("timed out"));
  });
});
