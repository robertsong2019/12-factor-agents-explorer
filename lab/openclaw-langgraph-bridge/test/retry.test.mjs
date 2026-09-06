import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { withRetry } from "../dist/retry.js";

describe("withRetry", () => {
  it("returns result on first success", async () => {
    const node = withRetry(
      async () => ({ result: "ok" }),
      { maxAttempts: 3 }
    );
    const out = await node({});
    assert.deepEqual(out, { result: "ok" });
  });

  it("retries on failure and succeeds", async () => {
    let calls = 0;
    const node = withRetry(
      async () => {
        calls++;
        if (calls < 3) throw new Error(`fail ${calls}`);
        return { result: "recovered" };
      },
      { maxAttempts: 3, baseDelayMs: 10 }
    );
    const out = await node({});
    assert.equal(calls, 3);
    assert.deepEqual(out, { result: "recovered" });
  });

  it("throws after exhausting all attempts", async () => {
    const node = withRetry(
      async () => { throw new Error("always fail"); },
      { maxAttempts: 2, baseDelayMs: 10 }
    );
    await assert.rejects(() => node({}), { message: "always fail" });
  });

  it("calls onRetry callback before each retry", async () => {
    const retries = [];
    let calls = 0;
    const node = withRetry(
      async () => {
        calls++;
        if (calls < 3) throw new Error("retry me");
        return { ok: true };
      },
      {
        maxAttempts: 3,
        baseDelayMs: 10,
        onRetry: (error, attempt) => retries.push({ error, attempt }),
      }
    );
    await node({});
    assert.equal(retries.length, 2);
    assert.equal(retries[0].error.message, "retry me");
    assert.equal(retries[0].attempt, 1);
    assert.equal(retries[1].attempt, 2);
  });

  it("uses default config when none provided", async () => {
    let calls = 0;
    const node = withRetry(async () => {
      calls++;
      if (calls < 2) throw new Error("once");
      return { ok: true };
    });
    const out = await node({});
    assert.deepEqual(out, { ok: true });
    assert.equal(calls, 2);
  });

  it("works with maxAttempts=1 (no retry)", async () => {
    const node = withRetry(
      async () => { throw new Error("no retry"); },
      { maxAttempts: 1 }
    );
    await assert.rejects(() => node({}), { message: "no retry" });
  });

  it("preserves state context across retries", async () => {
    const states = [];
    let calls = 0;
    const node = withRetry(
      async (state) => {
        states.push(state);
        calls++;
        if (calls < 2) throw new Error("fail once");
        return { saw: state.task };
      },
      { maxAttempts: 2, baseDelayMs: 5 }
    );
    const out = await node({ task: "research" });
    assert.equal(out.saw, "research");
    assert.equal(states.length, 2);
    assert.equal(states[0], states[1]);
  });
});

describe("withRetry config validation (C2 red-first)", () => {
  const boom = async () => { throw new Error("boom"); };

  it("maxAttempts=0 must throw RangeError at construction (would throw undefined)", () => {
    assert.throws(() => withRetry(boom, { maxAttempts: 0 }), RangeError);
  });

  it("maxAttempts negative must throw RangeError at construction", () => {
    assert.throws(() => withRetry(boom, { maxAttempts: -2 }), RangeError);
  });

  it("maxAttempts fractional < 1 must throw RangeError (zero executions, throw undefined)", () => {
    assert.throws(() => withRetry(boom, { maxAttempts: 0.5 }), RangeError);
  });
});
