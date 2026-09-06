import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { seal, isSealed, unseal } from "../dist/seal.js";

describe("seal", () => {
  it("returns frozen state", async () => {
    const node = async () => ({ x: 1, y: "hello" });
    const sealed = seal(node);
    const result = await sealed({});
    assert.strictEqual(Object.isFrozen(result), true);
  });

  it("preserves node output values", async () => {
    const node = async (s) => ({ ...s, added: 42 });
    const sealed = seal(node);
    const result = await sealed({ input: "test" });
    assert.strictEqual(result.input, "test");
    assert.strictEqual(result.added, 42);
  });

  it("prevents mutation of sealed output", async () => {
    const node = async () => ({ count: 0 });
    const sealed = seal(node);
    const result = await sealed({});
    assert.throws(() => { result.count = 99; }, /read only|Cannot assign/i);
    assert.strictEqual(result.count, 0);
  });

  it("detectMutations fires onChange", async () => {
    const mutations = [];
    const node = async () => ({ x: 1 });
    const sealed = seal(node, {
      detectMutations: true,
      onChange: (key, value, old) => mutations.push({ key, value, old }),
    });
    const result = await sealed({});
    assert.throws(() => { result.x = 99; }, /falsish|trap/i);
    assert.strictEqual(mutations.length, 1);
    assert.strictEqual(mutations[0].key, "x");
    assert.strictEqual(mutations[0].value, 99);
    assert.strictEqual(mutations[0].old, 1);
  });
});

describe("isSealed", () => {
  it("returns true for frozen objects", () => {
    assert.strictEqual(isSealed(Object.freeze({})), true);
  });

  it("returns false for regular objects", () => {
    assert.strictEqual(isSealed({}), false);
  });
});

describe("unseal", () => {
  it("creates writable copy of frozen state", async () => {
    const node = async () => ({ x: 1 });
    const sealed = seal(node);
    const frozen = await sealed({});
    const writable = unseal(frozen);
    writable.x = 42;
    assert.strictEqual(writable.x, 42);
    assert.strictEqual(frozen.x, 1); // original unchanged
  });
});

describe("seal identity contract (C3 red-first)", () => {
  it("seal with detectMutations must satisfy isSealed", async () => {
    const node = seal(async (s) => ({ v: s.x * 2 }), { detectMutations: true });
    const out = await node({ x: 1 });
    assert.equal(isSealed(out), true, "mutation-detecting seal must report sealed");
  });

  it("detectMutations seal still blocks writes AND fires onChange", async () => {
    const events = [];
    const node = seal(async () => ({ v: 1 }), {
      detectMutations: true,
      onChange: (k, val, old) => events.push([k, val, old]),
    });
    const out = await node({});
    "use strict";
    let blocked = false;
    try {
      out.v = 99;
    } catch {
      blocked = true; // TypeError expected in strict mode
    }
    assert.equal(out.v, 1, "write must not take effect");
    assert.deepEqual(events, [["v", 99, 1]], "onChange must fire with old value");
  });

  it("unseal of a detectMutations-sealed state returns writable copy", async () => {
    const node = seal(async () => ({ v: 1 }), { detectMutations: true });
    const out = await node({});
    const copy = unseal(out);
    copy.v = 42;
    assert.equal(copy.v, 42);
    assert.equal(out.v, 1);
  });
});
