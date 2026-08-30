import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { PolicyEngine, rateLimit } from '../src/policy-engine.js';

describe('rateLimit', () => {
  it('has correct rule metadata', () => {
    const rule = rateLimit({ maxCalls: 5, windowMs: 1000 });
    assert.equal(rule.name, 'rate_limit');
    assert.equal(rule.category, 'rate_control');
    assert.ok(rule.description.includes('5'));
    assert.ok(rule.description.includes('1000ms'));
  });

  it('allows calls up to the limit with default config (10)', () => {
    const rule = rateLimit();
    for (let i = 0; i < 10; i++) {
      const r = rule.evaluate({ timestamp: 1000 + i });
      assert.equal(r.allow, true, `call ${i + 1} should be allowed`);
    }
  });

  it('blocks the call that exceeds maxCalls within the window', () => {
    const rule = rateLimit({ maxCalls: 3, windowMs: 10_000 });
    assert.equal(rule.evaluate({ timestamp: 1000 }).allow, true);
    assert.equal(rule.evaluate({ timestamp: 2000 }).allow, true);
    assert.equal(rule.evaluate({ timestamp: 3000 }).allow, true);
    const fourth = rule.evaluate({ timestamp: 4000 });
    assert.equal(fourth.allow, false);
    assert.match(fourth.reason ?? '', /Rate limit: 4 calls in window/);
  });

  it('treats the boundary correctly: exactly maxCalls within window is allowed', () => {
    const rule = rateLimit({ maxCalls: 2, windowMs: 10_000 });
    assert.equal(rule.evaluate({ timestamp: 1000 }).allow, true);
    assert.equal(rule.evaluate({ timestamp: 1000 }).allow, true); // same ms, still 2 calls
  });

  it('sliding window: expired timestamps no longer count', () => {
    const rule = rateLimit({ maxCalls: 2, windowMs: 5000 });
    assert.equal(rule.evaluate({ timestamp: 1000 }).allow, true);
    assert.equal(rule.evaluate({ timestamp: 2000 }).allow, true);
    // third call inside window → blocked
    assert.equal(rule.evaluate({ timestamp: 3000 }).allow, false);
    // jump far ahead: both originals expired; only prior attempts inside new window count
    const later = rule.evaluate({ timestamp: 20_000 });
    assert.equal(later.allow, true, 'old calls should have slid out of the window');
  });

  it('blocked calls still occupy the window (recorded before decision)', () => {
    const rule = rateLimit({ maxCalls: 1, windowMs: 10_000 });
    assert.equal(rule.evaluate({ timestamp: 1000 }).allow, true);
    // blocked attempt is still recorded
    assert.equal(rule.evaluate({ timestamp: 2000 }).allow, false);
    assert.equal(rule.evaluate({ timestamp: 3000 }).allow, false);
  });

  it('window edge: cutoff is inclusive (t >= cutoff counts as recent), older calls expire', () => {
    const rule = rateLimit({ maxCalls: 2, windowMs: 1000 });
    assert.equal(rule.evaluate({ timestamp: 1000 }).allow, true);
    // cutoff = 2000-1000 = 1000; t=1000 is >= cutoff → still recent → 2/2 allowed
    assert.equal(rule.evaluate({ timestamp: 2000 }).allow, true);
    // cutoff = 2001-1000 = 1001; t=1000 expired, recent=[2000,2001] → 2/2 still allowed
    assert.equal(rule.evaluate({ timestamp: 2001 }).allow, true);
    // cutoff = 2002-1000 = 1002; recent=[2000,2001,2002] → 3 > 2 → blocked
    assert.equal(rule.evaluate({ timestamp: 2002 }).allow, false);
  });

  it('defaults to Date.now() when no timestamp provided', () => {
    const rule = rateLimit({ maxCalls: 1, windowMs: 60_000 });
    assert.equal(rule.evaluate({}).allow, true);
    assert.equal(rule.evaluate({}).allow, false);
  });

  it('coerces string timestamps via Number()', () => {
    const rule = rateLimit({ maxCalls: 1, windowMs: 10_000 });
    assert.equal(rule.evaluate({ timestamp: '1000' }).allow, true);
    assert.equal(rule.evaluate({ timestamp: '1500' }).allow, false);
  });

  it('integrates with PolicyEngine.evaluate', () => {
    const engine = new PolicyEngine();
    engine.addPolicy('rate_control', rateLimit({ maxCalls: 2, windowMs: 10_000 }));
    const r1 = engine.evaluate('rate_control', { timestamp: 1000 });
    assert.equal(r1.allowed, true);
    const r2 = engine.evaluate('rate_control', { timestamp: 1100 });
    assert.equal(r2.allowed, true);
    const r3 = engine.evaluate('rate_control', { timestamp: 1200 });
    assert.equal(r3.allowed, false);
    assert.equal(r3.violations.length, 1);
    assert.equal(r3.violations[0].rule, 'rate_limit');
    assert.match(r3.violations[0].reason, /Rate limit: 3 calls in window/);
  });

  it('each rateLimit() instance has independent state', () => {
    const a = rateLimit({ maxCalls: 1, windowMs: 10_000 });
    const b = rateLimit({ maxCalls: 1, windowMs: 10_000 });
    assert.equal(a.evaluate({ timestamp: 1000 }).allow, true);
    // b is unaffected by a's calls
    assert.equal(b.evaluate({ timestamp: 1000 }).allow, true);
    assert.equal(a.evaluate({ timestamp: 1100 }).allow, false);
  });
});
