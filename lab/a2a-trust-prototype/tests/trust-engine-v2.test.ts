// tests/trust-engine-v2.test.ts — coverage for the v2 pure functions (previously untested)
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  betaMean,
  betaUpdate,
  exponentialDecay,
  simpleHash,
  simhash,
  hammingDistance,
} from '../src/trust-engine-v2.js';

describe('TrustEngineV2 — Beta trust', () => {
  it('uniform prior has mean 0.5', () => {
    assert.equal(betaMean({ alpha: 1, beta: 1 }), 0.5);
  });

  it('success updates only alpha', () => {
    const next = betaUpdate({ alpha: 1, beta: 1 }, true);
    assert.deepEqual(next, { alpha: 2, beta: 1 });
  });

  it('failure updates only beta', () => {
    const next = betaUpdate({ alpha: 1, beta: 1 }, false);
    assert.deepEqual(next, { alpha: 1, beta: 2 });
  });

  it('weight scales the update', () => {
    assert.deepEqual(betaUpdate({ alpha: 1, beta: 1 }, true, 3), { alpha: 4, beta: 1 });
    assert.deepEqual(betaUpdate({ alpha: 1, beta: 1 }, false, 2), { alpha: 1, beta: 3 });
  });

  it('mean is monotonic in alpha', () => {
    assert.ok(betaMean({ alpha: 7, beta: 3 }) > betaMean({ alpha: 3, beta: 3 }));
  });

  it('ten successes push mean above 0.9', () => {
    let p = { alpha: 1, beta: 1 };
    for (let i = 0; i < 10; i++) p = betaUpdate(p, true);
    assert.ok(betaMean(p) > 0.9);
  });
});

describe('TrustEngineV2 — Decay', () => {
  it('zero elapsed time returns the mean unchanged', () => {
    assert.equal(exponentialDecay(0.9, 0), 0.9);
  });

  it('one half-life pulls mean halfway to prior', () => {
    const d = exponentialDecay(0.9, 168, 168);
    assert.ok(Math.abs(d - 0.7) < 1e-9, `expected ~0.7, got ${d}`);
  });

  it('high trust decays down toward the prior, never past it', () => {
    const d = exponentialDecay(0.9, 5_000, 168);
    assert.ok(d > 0.5 && d < 0.9, `expected (0.5, 0.9), got ${d}`);
  });

  it('low trust is pulled up toward the prior', () => {
    const d = exponentialDecay(0.2, 168, 168);
    assert.ok(Math.abs(d - 0.35) < 1e-9, `expected ~0.35, got ${d}`);
    assert.ok(d > 0.2);
  });
});

describe('TrustEngineV2 — Hashing', () => {
  it('simpleHash matches djb2 reference values', () => {
    assert.equal(simpleHash(''), 5381);
    assert.equal(simpleHash('a'), 177670); // (5381<<5)+5381+97
  });

  it('simpleHash is deterministic and unsigned', () => {
    assert.equal(simpleHash('agent-trust'), simpleHash('agent-trust'));
    assert.ok(simpleHash('agent-trust') >= 0);
    assert.ok(simpleHash('agent-trust') < 2 ** 32);
  });
});

describe('TrustEngineV2 — SimHash', () => {
  it('identical text yields identical fingerprint', () => {
    assert.equal(hammingDistance(simhash('hello world'), simhash('hello world')), 0);
  });

  it('empty text yields 0', () => {
    assert.equal(simhash(''), 0);
    assert.equal(simhash('   '), 0);
  });

  it('disjoint texts land far apart', () => {
    const hd = hammingDistance(simhash('the cat sat on the mat'), simhash('quantum flux reactors ignite'));
    assert.ok(hd >= 8, `expected HD >= 8 for disjoint texts, got ${hd}`);
  });

  it('texts sharing tokens are closer than disjoint ones', () => {
    const a = simhash('the cat sat on the mat today');
    const b = simhash('the cat sat on the mat now');
    const c = simhash('quantum flux reactors ignite tomorrow night');
    assert.ok(hammingDistance(a, b) < hammingDistance(a, c));
  });

  // Both cases below were RED on the banded-empty-slice bug: texts with fewer
  // tokens than bands produced empty slices whose constant hash (5381) won the
  // majority vote, collapsing distinct short texts to the same fingerprint.
  it('two-token texts sharing only the last word do not collide', () => {
    assert.notEqual(simhash('hello world'), simhash('goodbye world'));
  });

  it('single-token fingerprints reflect the token', () => {
    assert.notEqual(simhash('hello'), simhash('goodbye'));
  });

  it('normal path stays deterministic across calls', () => {
    const t = 'memory consolidation runs while the agent sleeps deeply tonight';
    assert.equal(simhash(t), simhash(t));
  });
});

describe('TrustEngineV2 — Hamming', () => {
  it('identical values have distance 0', () => {
    assert.equal(hammingDistance(0b1010, 0b1010), 0);
  });

  it('all-bits-differ has distance 32', () => {
    assert.equal(hammingDistance(0, 0xffffffff), 32);
  });

  it('is symmetric', () => {
    const a = 0b110010, b = 0b011011;
    assert.equal(hammingDistance(a, b), hammingDistance(b, a));
    assert.equal(hammingDistance(a, b), 3);
  });
});
