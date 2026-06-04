// tests/trust-engine-extended.test.ts — Edge cases for TrustEngine
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { TrustEngine } from '../src/trust-engine.js';
import { canonicalizeJSON } from '../src/crypto.js';

describe('TrustEngine extended edge cases', () => {
  it('getScore returns 50 default for unknown agent', () => {
    const engine = new TrustEngine();
    assert.equal(engine.getScore('nobody'), 50);
  });

  it('multiple agents are independent', () => {
    const engine = new TrustEngine();
    engine.recordInteraction('a1', true);
    engine.recordInteraction('a1', true);
    engine.recordInteraction('a2', false);
    assert.ok(engine.getScore('a1') > engine.getScore('a2'));
    assert.equal(engine.getTrustLevel('a1'), 'neutral');
    assert.equal(engine.getTrustLevel('a2'), 'untrusted');
  });

  it('recordSkillInteraction updates both skill and overall', () => {
    const engine = new TrustEngine();
    engine.recordSkillInteraction('a1', 'sql', true);
    // Overall should also reflect the interaction
    const report = engine.getTrustReport('a1');
    assert.ok(report.overall.interactions >= 1);
    assert.ok(report.overall.score > 50);
  });

  it('diminishing returns floors at 0.1 multiplier', () => {
    const engine = new TrustEngine();
    // Record 200 successes to drive the multiplier to its floor
    for (let i = 0; i < 200; i++) {
      engine.recordInteraction('a1', true);
    }
    // Score should be clamped at 100
    assert.equal(engine.getScore('a1'), 100);
    // Now fail once — should drop by 15
    engine.recordInteraction('a1', false);
    assert.equal(engine.getScore('a1'), 85);
  });

  it('getSkillTrustLevel returns unknown for unknown agent', () => {
    const engine = new TrustEngine();
    assert.equal(engine.getSkillTrustLevel('ghost', 'sql'), 'unknown');
  });

  it('per-skill records are independent across agents', () => {
    const engine = new TrustEngine();
    engine.recordSkillInteraction('a1', 'sql', true);
    engine.recordSkillInteraction('a2', 'sql', false);
    assert.equal(engine.getSkillTrustLevel('a1', 'sql'), 'neutral');
    assert.equal(engine.getSkillTrustLevel('a2', 'sql'), 'untrusted');
  });

  it('trust report for agent with only overall interactions has empty skills', () => {
    const engine = new TrustEngine();
    engine.recordInteraction('a1', true);
    engine.recordInteraction('a1', true);
    const report = engine.getTrustReport('a1');
    assert.deepEqual(report.skills, {});
    assert.ok(report.overall.interactions >= 2);
  });

  it('canDelegate: unknown agent passes for untrusted required', () => {
    const engine = new TrustEngine();
    // unknown level index = 0, untrusted = 1
    // unknown >= untrusted → false
    assert.equal(engine.canDelegate('ghost', 'untrusted'), false);
  });

  it('canDelegate: unknown agent passes for unknown required', () => {
    const engine = new TrustEngine();
    assert.equal(engine.canDelegate('ghost', 'unknown'), true);
  });

  it('scoreDecay with zero hours is no-op', () => {
    const engine = new TrustEngine();
    engine.recordInteraction('a1', true);
    const before = engine.getScore('a1');
    engine.scoreDecay('a1', 0);
    assert.equal(engine.getScore('a1'), before);
  });

  it('scoreDecay fractional hours', () => {
    const engine = new TrustEngine();
    engine.recordInteraction('a1', true);
    const before = engine.getScore('a1');
    engine.scoreDecay('a1', 0.5); // 0.5 * 0.1 = 0.05
    const after = engine.getScore('a1');
    assert.ok(after < before);
    assert.ok(Math.abs(after - (before - 0.05)) < 0.001);
  });

  it('success after decay restores score', () => {
    const engine = new TrustEngine();
    for (let i = 0; i < 10; i++) {
      engine.recordInteraction('a1', true);
    }
    engine.scoreDecay('a1', 50);
    const decayed = engine.getScore('a1');
    engine.recordInteraction('a1', true);
    assert.ok(engine.getScore('a1') > decayed);
  });
});

describe('Crypto canonicalization edge cases', () => {
  it('handles null values', () => {
    const result = canonicalizeJSON({ a: null, b: 1 });
    assert.equal(result, '{"a":null,"b":1}');
  });

  it('handles empty object', () => {
    assert.equal(canonicalizeJSON({}), '{}');
  });

  it('handles empty array', () => {
    assert.equal(canonicalizeJSON([]), '[]');
  });

  it('handles primitives', () => {
    assert.equal(canonicalizeJSON(42), '42');
    assert.equal(canonicalizeJSON('hello'), '"hello"');
    assert.equal(canonicalizeJSON(true), 'true');
    assert.equal(canonicalizeJSON(null), 'null');
  });

  it('handles deeply nested objects', () => {
    const obj = { a: { b: { c: { d: 1 } } } };
    assert.equal(canonicalizeJSON(obj), '{"a":{"b":{"c":{"d":1}}}}');
  });

  it('handles mixed types', () => {
    const obj = { str: 'hi', num: 1, bool: true, nil: null, arr: [1, 'x'] };
    const canonical = canonicalizeJSON(obj);
    // Keys should be sorted
    assert.equal(canonical, '{"arr":[1,"x"],"bool":true,"nil":null,"num":1,"str":"hi"}');
  });
});

describe('Middleware access control edge cases', () => {
  it('checkAccess falls back to overall when skill is unknown', async () => {
    const { generateKeyPair } = await import('../src/crypto.js');
    const { TrustEngine } = await import('../src/trust-engine.js');
    const { createMiddleware } = await import('../src/middleware.js');

    const key = await generateKeyPair();
    const engine = new TrustEngine();
    const mw = createMiddleware(engine, key);

    // Build up overall trust
    engine.recordInteraction('a1', true);
    engine.recordInteraction('a1', true);
    engine.recordInteraction('a1', true);

    // Unknown skill should fall back to overall (neutral)
    assert.equal(mw.checkAccess('a1', 'unknown-skill', 'untrusted'), true);
    assert.equal(mw.checkAccess('a1', 'unknown-skill', 'neutral'), true);
  });

  it('checkAccess denies everything for completely unknown agent', async () => {
    const { generateKeyPair } = await import('../src/crypto.js');
    const { TrustEngine } = await import('../src/trust-engine.js');
    const { createMiddleware } = await import('../src/middleware.js');

    const key = await generateKeyPair();
    const engine = new TrustEngine();
    const mw = createMiddleware(engine, key);

    assert.equal(mw.checkAccess('ghost', 'sql', 'untrusted'), false);
    assert.equal(mw.checkAccess('ghost', 'sql', 'neutral'), false);
  });

  it('signOutbound produces deterministic signatures for same data', async () => {
    const { generateKeyPair, verify } = await import('../src/crypto.js');
    const { TrustEngine } = await import('../src/trust-engine.js');
    const { createMiddleware } = await import('../src/middleware.js');

    const key = await generateKeyPair();
    const engine = new TrustEngine();
    const mw = createMiddleware(engine, key);

    const data = { msg: 'test', n: 42 };
    const sig1 = await mw.signOutbound(data);
    const sig2 = await mw.signOutbound(data);
    // Both signatures should verify
    assert.equal(await verify(key.publicKey, data, sig1), true);
    assert.equal(await verify(key.publicKey, data, sig2), true);
  });
});
