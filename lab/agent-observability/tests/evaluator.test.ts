import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { Evaluator, policyComplianceCheck, latencyCheck, reliabilityCheck, costEfficiencyCheck, compareTraces } from '../src/evaluator.js';
import { Tracer } from '../src/tracer.js';
import type { Span } from '../src/tracer.js';

function makeSpan(overrides: Partial<Span> = {}): Span {
  return {
    traceId: 't1',
    spanId: 's1',
    parentSpanId: null,
    operation: 'agent.run',
    startTime: 0,
    endTime: 100,
    attributes: {},
    status: 'ok',
    events: [],
    ...overrides,
  };
}

describe('Evaluator', () => {
  it('returns empty results with no checks', () => {
    const ev = new Evaluator();
    const results = ev.evaluate([makeSpan()]);
    assert.equal(results.length, 0);
  });

  it('runs added checks', () => {
    const ev = new Evaluator();
    ev.addCheck('test', () => [{ dimension: 'test', score: 0.9, reason: 'looks good' }]);
    const results = ev.evaluate([makeSpan()]);
    assert.equal(results.length, 1);
    assert.equal(results[0].score, 0.9);
  });

  it('computes weighted aggregate score', () => {
    const ev = new Evaluator();
    ev.addCheck('a', () => [{ dimension: 'a', score: 1.0, reason: '' }], 2.0);
    ev.addCheck('b', () => [{ dimension: 'b', score: 0.0, reason: '' }], 1.0);
    const results = ev.evaluate([makeSpan()]);
    const agg = ev.aggregateScore(results);
    assert.equal(agg, 2 / 3); // (1*2 + 0*1) / (2+1)
  });

  it('policy_compliance scores 1 when no blocks', () => {
    const spans = [makeSpan({ operation: 'tool.execute', attributes: {} })];
    const results = policyComplianceCheck(spans);
    assert.equal(results[0].score, 1);
  });

  it('policy_compliance degrades on blocks', () => {
    const spans = [
      makeSpan({ spanId: 's1', operation: 'tool.execute', status: 'ok' }),
      makeSpan({ spanId: 's2', operation: 'tool.execute', status: 'error', attributes: { policyDenied: true } }),
    ];
    const results = policyComplianceCheck(spans);
    assert.equal(results[0].score, 0.5);
  });

  it('reliability scores based on error ratio', () => {
    const spans = [
      makeSpan({ spanId: 's1', status: 'ok' }),
      makeSpan({ spanId: 's2', status: 'error' }),
    ];
    const results = reliabilityCheck(spans);
    assert.equal(results[0].score, 0.5);
  });

  it('cost_efficiency scores based on token usage', () => {
    const spans = [makeSpan({ operation: 'llm.call', attributes: { totalTokens: 500 } })];
    const results = costEfficiencyCheck(spans);
    assert.equal(results[0].score, 1);
  });

  it('lists registered check names', () => {
    const ev = new Evaluator();
    ev.addCheck('a', () => []);
    ev.addCheck('b', () => []);
    assert.deepEqual(ev.listChecks(), ['a', 'b']);
  });

  it('removes a check by name', () => {
    const ev = new Evaluator();
    ev.addCheck('a', () => [{ dimension: 'a', score: 1, reason: '' }]);
    ev.removeCheck('a');
    assert.equal(ev.evaluate([makeSpan()]).length, 0);
  });

  it('aggregateScore returns 0 for empty results', () => {
    const ev = new Evaluator();
    assert.equal(ev.aggregateScore([]), 0);
  });

  // --- compareTraces ---

  it('compareTraces detects no regression when identical', () => {
    const spans = [makeSpan()];
    const diffs = compareTraces(spans, spans);
    assert.ok(diffs.length > 0);
    for (const d of diffs) {
      assert.equal(d.regression, false);
    }
  });

  it('compareTraces detects latency regression', () => {
    const fast: Span[] = [{ ...makeSpan(), operation: 'llm.call' as const, startTime: 0, endTime: 10, attributes: { totalTokens: 50 } }];
    const slow: Span[] = [{ ...makeSpan(), operation: 'llm.call' as const, startTime: 0, endTime: 10000, attributes: { totalTokens: 100000 } }];
    const diffs = compareTraces(fast, slow);
    const latDiff = diffs.find(d => d.dimension === 'latency');
    assert.ok(latDiff);
    assert.ok(latDiff!.delta < 0);
  });

  it('compareTraces detects reliability regression', () => {
    const good = [makeSpan(), makeSpan()];
    const bad: Span[] = [makeSpan(), { ...makeSpan(), status: 'error' as const }];
    const diffs = compareTraces(good, bad);
    const rel = diffs.find(d => d.dimension === 'reliability');
    assert.ok(rel);
    assert.ok(rel!.delta < 0);
    assert.equal(rel!.regression, true);
  });

  // --- setWeight + resetChecks ---

  it('setWeight updates existing check weight', () => {
    const e = new Evaluator();
    e.addCheck('test', () => [{ dimension: 'test', score: 1, reason: 'ok' }], 1.0);
    assert.ok(e.setWeight('test', 2.5));
    const results = e.evaluate([]);
    assert.strictEqual(e.aggregateScore(results), 1); // score doesn't change, weight does
  });

  it('setWeight returns false for unknown check', () => {
    const e = new Evaluator();
    assert.strictEqual(e.setWeight('nonexistent', 1.0), false);
  });

  it('resetChecks clears all checks', () => {
    const e = new Evaluator();
    e.addCheck('a', () => []);
    e.addCheck('b', () => []);
    assert.strictEqual(e.listChecks().length, 2);
    e.resetChecks();
    assert.strictEqual(e.listChecks().length, 0);
    assert.strictEqual(e.aggregateScore([]), 0);
  });

  it('getCheck returns check by name', () => {
    const e = new Evaluator();
    const fn = () => [];
    e.addCheck('mycheck', fn, 2.5);
    const found = e.getCheck('mycheck');
    assert.ok(found);
    assert.strictEqual(found!.weight, 2.5);
    assert.strictEqual(e.getCheck('nope'), undefined);
  });

  it('evaluate filters by dimensions', () => {
    const e = new Evaluator();
    e.addCheck('dim_a', () => [{ dimension: 'a', score: 1, reason: '' }]);
    e.addCheck('dim_b', () => [{ dimension: 'b', score: 0.5, reason: '' }]);
    const all = e.evaluate([]);
    assert.strictEqual(all.length, 2);
    const filtered = e.evaluate([], ['dim_a']);
    assert.strictEqual(filtered.length, 1);
    assert.strictEqual(filtered[0].dimension, 'a');
  });

  it('topFailures returns lowest-scoring dimensions', () => {
    const e = new Evaluator();
    const results = [
      { dimension: 'a', score: 0.9, reason: '' },
      { dimension: 'b', score: 0.3, reason: 'bad' },
      { dimension: 'c', score: 0.7, reason: '' },
    ];
    const failures = e.topFailures(results, 2);
    assert.strictEqual(failures.length, 2);
    assert.strictEqual(failures[0].dimension, 'b');
    assert.strictEqual(failures[1].dimension, 'c');
  });

  it('dimensionNames returns registered check names', () => {
    const e = new Evaluator();
    e.addCheck('latency', () => []);
    e.addCheck('reliability', () => []);
    assert.deepEqual(e.dimensionNames(), ['latency', 'reliability']);
  });

  it('overallPassRate returns fraction of passing results', () => {
    const e = new Evaluator();
    assert.equal(e.overallPassRate([]), 1);
    const results = [
      { dimension: 'a', score: 0.8, reason: 'ok' },
      { dimension: 'b', score: 0.3, reason: 'fail' },
      { dimension: 'c', score: 0.6, reason: 'ok' },
    ];
    assert.equal(e.overallPassRate(results), 2 / 3);
  });

  it('evaluateEach returns per-check results', () => {
    const e = new Evaluator();
    e.addCheck('compliance', policyComplianceCheck);
    e.addCheck('latency', latencyCheck);
    const each = e.evaluateEach([]);
    assert.equal(each.length, 2);
    assert.equal(each[0].check, 'compliance');
    assert.equal(each[1].check, 'latency');
    assert.ok(each[0].results.length > 0);
  });

  it('passCount counts passing results', () => {
    const e = new Evaluator();
    const results = [
      { dimension: 'a', score: 0.9, reason: 'ok' },
      { dimension: 'b', score: 0.3, reason: 'fail' },
      { dimension: 'c', score: 0.6, reason: 'ok' },
    ];
    assert.equal(e.passCount(results), 2);
  });

  it('summary returns aggregate stats', () => {
    const e = new Evaluator();
    const results = [
      { dimension: 'a', score: 0.9, reason: 'ok' },
      { dimension: 'a', score: 0.3, reason: 'bad' },
      { dimension: 'b', score: 0.7, reason: 'ok' },
    ];
    const s = e.summary(results);
    assert.equal(s.total, 3);
    assert.equal(s.passed, 2);
    assert.equal(s.failed, 1);
    assert.equal(s.avgScore, 0.63);
    assert.equal(s.dimensions, 2);
  });

  it('summary handles empty results', () => {
    const e = new Evaluator();
    const s = e.summary([]);
    assert.equal(s.total, 0);
    assert.equal(s.avgScore, 0);
  });

  it('byDimension filters results', () => {
    const e = new Evaluator();
    const results = [
      { dimension: 'a', score: 0.9, reason: 'ok' },
      { dimension: 'b', score: 0.7, reason: 'ok' },
      { dimension: 'a', score: 0.3, reason: 'bad' },
    ];
    const filtered = e.byDimension(results, 'a');
    assert.equal(filtered.length, 2);
    assert.equal(filtered[0].score, 0.9);
    assert.equal(filtered[1].score, 0.3);
  });

  it('toMarkdown generates report', () => {
    const e = new Evaluator();
    const results = [
      { dimension: 'latency', score: 0.85, reason: 'Avg 200ms' },
      { dimension: 'reliability', score: 0.3, reason: '2/5 errors' },
    ];
    const md = e.toMarkdown(results);
    assert.ok(md.includes('# Evaluation Report'));
    assert.ok(md.includes('latency'));
    assert.ok(md.includes('reliability'));
    assert.ok(md.includes('✅'));
    assert.ok(md.includes('❌'));
  });

  it('addBuiltinChecks registers all 4 checks', () => {
    const ev = new Evaluator();
    ev.addBuiltinChecks();
    assert.deepEqual(ev.listChecks(), ['policy_compliance', 'latency', 'reliability', 'cost_efficiency']);
  });

  it('evaluateAndReport returns combined result', () => {
    const ev = new Evaluator();
    ev.addBuiltinChecks();
    const tracer = new Tracer();
    const s = tracer.startSpan('llm.call');
    tracer.endSpan(s.spanId);
    const { results, score, report } = ev.evaluateAndReport(tracer.getSpans());
    assert.ok(results.length >= 1);
    assert.ok(score >= 0 && score <= 1);
    assert.ok(report.includes('Evaluation Report'));
  });
});
