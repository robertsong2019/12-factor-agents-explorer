// tests/trust-engine.test.ts
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { TrustEngine } from '../src/trust-engine.js';

describe('TrustEngine', () => {
  it('returns "unknown" for unregistered agents', () => {
    const engine = new TrustEngine();
    assert.equal(engine.getTrustLevel('agent-unknown'), 'unknown');
  });

  it('starts at neutral after first interaction', () => {
    const engine = new TrustEngine();
    engine.recordInteraction('a1', true);
    assert.equal(engine.getTrustLevel('a1'), 'neutral');
    assert.equal(engine.getScore('a1'), 55); // 50 + 5*1
  });

  it('drops to untrusted on failure', () => {
    const engine = new TrustEngine();
    engine.recordInteraction('a1', false);
    assert.equal(engine.getTrustLevel('a1'), 'untrusted');
    assert.equal(engine.getScore('a1'), 35); // 50 - 15
  });

  it('has diminishing returns on success', () => {
    const engine = new TrustEngine();
    // Record many successes
    for (let i = 0; i < 10; i++) {
      engine.recordInteraction('a1', true);
    }
    // Score should be less than 50 + 10*5 due to diminishing returns
    assert.ok(engine.getScore('a1') < 100);
    assert.ok(engine.getScore('a1') > 80);
  });

  it('clamps score to 0-100', () => {
    const engine = new TrustEngine();
    for (let i = 0; i < 10; i++) {
      engine.recordInteraction('a1', false);
    }
    assert.equal(engine.getScore('a1'), 0);
    // Now pile on successes
    for (let i = 0; i < 100; i++) {
      engine.recordInteraction('a1', true);
    }
    assert.equal(engine.getScore('a1'), 100);
  });

  it('supports per-skill trust levels', () => {
    const engine = new TrustEngine();
    engine.recordSkillInteraction('a1', 'sql', true);
    engine.recordSkillInteraction('a1', 'sql', true);
    engine.recordSkillInteraction('a1', 'http', false);
    assert.equal(engine.getSkillTrustLevel('a1', 'sql'), 'neutral');
    assert.equal(engine.getSkillTrustLevel('a1', 'http'), 'untrusted');
    // Unknown skill on known agent
    assert.equal(engine.getSkillTrustLevel('a1', 'ftp'), 'unknown');
  });

  it('applies time decay', () => {
    const engine = new TrustEngine();
    engine.recordInteraction('a1', true);
    engine.recordInteraction('a1', true);
    const before = engine.getScore('a1');
    engine.scoreDecay('a1', 100); // 100 hours
    const after = engine.getScore('a1');
    assert.ok(after < before);
    assert.equal(after, before - 10); // 100 * 0.1 = 10
  });

  it('generates trust report', () => {
    const engine = new TrustEngine();
    engine.recordInteraction('a1', true);
    engine.recordSkillInteraction('a1', 'skill1', true);
    engine.recordSkillInteraction('a1', 'skill1', false);
    const report = engine.getTrustReport('a1');
    // Overall includes the recordInteraction + 1 from recordSkillInteraction
    assert.ok(report.overall.interactions >= 2);
    assert.ok(report.skills['skill1']);
    assert.equal(report.skills['skill1'].level, 'untrusted');
  });

  it('canDelegate works correctly', () => {
    const engine = new TrustEngine();
    // Unknown agent can't delegate at neutral level
    assert.equal(engine.canDelegate('a1', 'neutral'), false);
    // Make agent trusted
    for (let i = 0; i < 20; i++) {
      engine.recordInteraction('a1', true);
    }
    assert.equal(engine.canDelegate('a1', 'trusted'), true);
    assert.equal(engine.canDelegate('a1', 'neutral'), true);
  });

  it('returns unknown trust report for unregistered agent', () => {
    const engine = new TrustEngine();
    const report = engine.getTrustReport('nobody');
    assert.equal(report.overall.level, 'unknown');
    assert.equal(report.overall.interactions, 0);
    assert.equal(report.overall.score, 50);
    assert.deepEqual(report.skills, {});
  });

  it('scoreDecay is no-op for unknown agent', () => {
    const engine = new TrustEngine();
    engine.scoreDecay('ghost', 1000);
    assert.equal(engine.getScore('ghost'), 50); // default
  });

  it('scoreDecay clamps to 0', () => {
    const engine = new TrustEngine();
    engine.recordInteraction('a1', true); // 55
    engine.scoreDecay('a1', 10000); // 10000 * 0.1 = 1000
    assert.equal(engine.getScore('a1'), 0);
  });

  it('trust report includes multiple skills', () => {
    const engine = new TrustEngine();
    engine.recordSkillInteraction('a1', 'sql', true);
    engine.recordSkillInteraction('a1', 'http', true);
    engine.recordSkillInteraction('a1', 'http', true);
    const report = engine.getTrustReport('a1');
    assert.ok(report.skills['sql']);
    assert.ok(report.skills['http']);
    assert.equal(Object.keys(report.skills).length, 2);
  });

  it('canDelegate works for untrusted level', () => {
    const engine = new TrustEngine();
    engine.recordInteraction('a1', false); // score 35 = untrusted
    assert.equal(engine.canDelegate('a1', 'untrusted'), true);
    assert.equal(engine.canDelegate('a1', 'neutral'), false);
  });

  it('alternating success and failure', () => {
    const engine = new TrustEngine();
    for (let i = 0; i < 5; i++) {
      engine.recordInteraction('a1', true);
      engine.recordInteraction('a1', false);
    }
    // Each failure is -15, each success gains ~5 with diminishing
    // Net should be negative
    assert.ok(engine.getScore('a1') < 50);
    assert.equal(engine.getTrustLevel('a1'), 'untrusted');
  });
});
