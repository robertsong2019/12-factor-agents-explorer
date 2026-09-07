/**
 * Regression tests 2026-09-07 evening code-lab cycle 1.
 * Red-first bugs:
 *  1. Tracer.clear() did not reset activeStack -> spans started after clear()
 *     got a dead parentSpanId (ghost parent), vanishing from getSpanTree().
 *  2. getCausalChain pushed spans to the result before marking them visited,
 *     so diamond topologies (A->B, A->C, B->D, C->D) yielded duplicates.
 */
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { Tracer } from '../src/tracer.js';
import { PolicyEngine } from '../src/policy-engine.js';

describe('regressions 2026-09-07: tracer', () => {
  test('clear() resets active stack: spans started after clear are parentless roots', () => {
    const tracer = new Tracer();
    const stale = tracer.startSpan('agent.run');
    tracer.clear();

    assert.equal(tracer.getActiveSpanCount(), 0, 'active stack must be empty after clear');

    const fresh = tracer.startSpan('llm.call');
    assert.equal(fresh.parentSpanId, null, 'span after clear must not inherit a dead parent');
    assert.notEqual(fresh.parentSpanId, stale.spanId);

    // Fresh span must be reachable from the tree roots (ghost-parent bug = invisible span)
    const tree = tracer.getSpanTree();
    assert.equal(tree.length, 1, 'fresh span must appear as a root in the span tree');
    assert.equal(tree[0].spanId, fresh.spanId);
  });

  test('clear() resets active stack: getActiveSpan no longer returns cleared spans', () => {
    const tracer = new Tracer();
    tracer.startSpan('agent.run');
    tracer.clear();
    assert.equal(tracer.getActiveSpan(), undefined);
    assert.equal(tracer.spanCount(), 0);
  });

  test('getCausalChain diamond topology: each span appears exactly once', () => {
    const tracer = new Tracer();
    const a = tracer.startSpan('agent.run');
    const b = tracer.startSpan('llm.call');
    const c = tracer.startSpan('tool.execute');
    const d = tracer.startSpan('retrieval.search');
    for (const s of [a, b, c, d]) tracer.endSpan(s.spanId);

    tracer.linkSpans(a.spanId, b.spanId);
    tracer.linkSpans(a.spanId, c.spanId);
    tracer.linkSpans(b.spanId, d.spanId);
    tracer.linkSpans(c.spanId, d.spanId);

    const chain = tracer.getCausalChain(a.spanId, 'downstream');
    const ids = chain.map(s => s.spanId);
    assert.equal(ids.length, new Set(ids).size, `expected unique spans, got ${ids.length} entries`);
    assert.deepEqual([...new Set(ids)].sort(), [b.spanId, c.spanId, d.spanId].sort());
  });

  test('getCausalChain upstream diamond: no duplicates either direction', () => {
    const tracer = new Tracer();
    const a = tracer.startSpan('agent.run');
    const b = tracer.startSpan('llm.call');
    const c = tracer.startSpan('tool.execute');
    const d = tracer.startSpan('retrieval.search');
    for (const s of [a, b, c, d]) tracer.endSpan(s.spanId);

    tracer.linkSpans(a.spanId, b.spanId);
    tracer.linkSpans(a.spanId, c.spanId);
    tracer.linkSpans(b.spanId, d.spanId);
    tracer.linkSpans(c.spanId, d.spanId);

    const chain = tracer.getCausalChain(d.spanId, 'upstream');
    const ids = chain.map(s => s.spanId);
    assert.equal(ids.length, new Set(ids).size);
  });
});

describe('regressions 2026-09-07: tracer purity + importJSON atomicity', () => {
  const snapshot = () => JSON.stringify({
    traceId: 'tid-orig',
    spans: [
      { traceId: 'tid-orig', spanId: 's2', parentSpanId: null, operation: 'llm.call', startTime: 200, endTime: 300, attributes: {}, status: 'ok', events: [] },
      { traceId: 'tid-orig', spanId: 's1', parentSpanId: null, operation: 'agent.run', startTime: 100, endTime: 400, attributes: {}, status: 'ok', events: [] },
    ],
  });

  test('getTraceHash does not mutate internal span order (pure read)', () => {
    const tracer = new Tracer();
    tracer.importJSON(snapshot());
    const before = tracer.getSpans().map(s => s.spanId);
    tracer.getTraceHash();
    const after = tracer.getSpans().map(s => s.spanId);
    assert.deepEqual(after, before, 'a read API must not reorder stored spans');
  });

  test('importJSON: malformed JSON throws with diagnostics, state untouched', () => {
    const tracer = new Tracer();
    const s = tracer.startSpan('agent.run');
    tracer.endSpan(s.spanId);
    const spansBefore = tracer.getSpans();
    assert.throws(() => tracer.importJSON('{not json'), TypeError);
    assert.deepEqual(tracer.getSpans(), spansBefore, 'failed import must not mutate spans');
  });

  test('importJSON: non-object / wrong-shape payloads rejected atomically', () => {
    const tracer = new Tracer();
    tracer.startSpan('agent.run');
    const tidBefore = tracer.getTraceReport().traceId;
    const countBefore = tracer.spanCount();

    assert.throws(() => tracer.importJSON('[1,2,3]'), TypeError);
    assert.throws(() => tracer.importJSON('null'), TypeError);
    // traceId-only object: currently silently rewrites traceId while keeping old spans (mixed state)
    assert.throws(() => tracer.importJSON('{"spans": "not-an-array"}'), TypeError);
    assert.throws(() => tracer.importJSON('{"traceId": 42, "spans": []}'), TypeError);

    assert.equal(tracer.getTraceReport().traceId, tidBefore, 'traceId unchanged after failed imports');
    assert.equal(tracer.spanCount(), countBefore, 'spans unchanged after failed imports');
  });

  test('importJSON: valid snapshot resets active stack (no cross-trace ghost parents)', () => {
    const tracer = new Tracer();
    tracer.startSpan('agent.run'); // leave active
    tracer.importJSON(snapshot());
    assert.equal(tracer.getActiveSpanCount(), 0, 'imported snapshot has no active spans');
    const fresh = tracer.startSpan('llm.call');
    assert.equal(fresh.parentSpanId, null, 'span after import must not inherit pre-import active parent');
  });

  test('importJSON: valid round-trip still works (export/import pinned)', () => {
    const t1 = new Tracer();
    const s = t1.startSpan('agent.run');
    t1.endSpan(s.spanId);
    const t2 = new Tracer();
    t2.importJSON(t1.exportJSON());
    assert.equal(t2.spanCount(), 1);
    assert.equal(t2.getSpans()[0].operation, 'agent.run');
  });
});

describe('regressions 2026-09-07: policy-engine round-trip', () => {
  test('toJSON -> fromJSON preserves disabled rule state', () => {
    const engine = new PolicyEngine();
    engine.loadFromJSON([
      { name: 'block-rm', description: 'no rm', category: 'tool', type: 'blockDestructiveOps' },
      { name: 'cost-cap', description: 'cap', category: 'llm', type: 'costLimit', config: { maxCost: 1 } },
    ]);
    engine.disableRule('tool', 'block-rm');

    const revived = PolicyEngine.fromJSON(engine.toJSON());
    assert.equal(revived.getRule('tool', 'block-rm')?.name, 'block-rm', 'rules restored');
    assert.equal(revived.isRuleEnabled('tool', 'block-rm'), false, 'disabled state must survive the round-trip');
    assert.equal(revived.isRuleEnabled('llm', 'cost-cap'), true, 'enabled rules stay enabled');
  });
});

describe('regressions 2026-09-07: policy-engine name identity', () => {
  test('loadFromJSON honors def name; disableRule deactivates the LIVE rule', () => {
    const engine = new PolicyEngine();
    engine.loadFromJSON([
      { name: 'block', description: 'block rm', category: 'tool_execution', type: 'blockDestructiveOps' },
    ]);
    assert.equal(engine.getRule('tool_execution', 'block')?.name, 'block', 'rule registered under def name');
    assert.equal(engine.evaluate('tool_execution', { command: 'rm -rf /' }).allowed, false, 'rule active');

    engine.disableRule('tool_execution', 'block');
    assert.equal(
      engine.evaluate('tool_execution', { command: 'rm -rf /' }).allowed,
      true,
      'disable by def name must reach the live rule (was a silent no-op via hardcoded builder name)'
    );
  });
});
