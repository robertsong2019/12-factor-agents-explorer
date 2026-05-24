import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { Tracer } from '../src/tracer.js';

describe('Tracer', () => {
  it('creates a span with correct fields', () => {
    const tracer = new Tracer();
    const span = tracer.startSpan('agent.run', { agentId: 'a1' });
    assert.equal(span.operation, 'agent.run');
    assert.equal(span.parentSpanId, null);
    assert.equal(span.status, 'unset');
    assert.equal(span.endTime, null);
    assert.equal(span.attributes.agentId, 'a1');
    assert.ok(span.traceId);
    assert.ok(span.spanId);
  });

  it('ends a span and sets status', () => {
    const tracer = new Tracer();
    const span = tracer.startSpan('agent.run');
    const ended = tracer.endSpan(span.spanId, 'ok');
    assert.ok(ended);
    assert.equal(ended!.status, 'ok');
    assert.ok(ended!.endTime !== null);
  });

  it('creates parent-child relationships', () => {
    const tracer = new Tracer();
    const parent = tracer.startSpan('agent.run');
    const child = tracer.startSpan('llm.call');
    assert.equal(child.parentSpanId, parent.spanId);
    assert.equal(child.traceId, parent.traceId);
    tracer.endSpan(child.spanId);
    tracer.endSpan(parent.spanId);
  });

  it('tracks active span via stack', () => {
    const tracer = new Tracer();
    const s1 = tracer.startSpan('agent.run');
    assert.equal(tracer.getActiveSpan()?.spanId, s1.spanId);
    const s2 = tracer.startSpan('llm.call');
    assert.equal(tracer.getActiveSpan()?.spanId, s2.spanId);
    tracer.endSpan(s2.spanId);
    assert.equal(tracer.getActiveSpan()?.spanId, s1.spanId);
    tracer.endSpan(s1.spanId);
    assert.equal(tracer.getActiveSpan(), undefined);
  });

  it('adds events to spans', () => {
    const tracer = new Tracer();
    const span = tracer.startSpan('agent.run');
    tracer.addEvent(span.spanId, 'retry', { attempt: 2 });
    assert.equal(span.events.length, 1);
    assert.equal(span.events[0].name, 'retry');
    assert.equal(span.events[0].attributes?.attempt, 2);
  });

  it('generates trace report with summary stats', () => {
    const tracer = new Tracer();
    const s1 = tracer.startSpan('agent.run');
    const s2 = tracer.startSpan('llm.call');
    tracer.endSpan(s2.spanId);
    tracer.endSpan(s1.spanId, 'error');
    const report = tracer.getTraceReport();
    assert.equal(report.totalSpans, 2);
    assert.equal(report.errorCount, 1);
    assert.ok(report.durationByOp['agent.run'] > 0);
    assert.ok(report.durationByOp['llm.call'] > 0);
  });

  it('exports and imports traces preserving traceId', () => {
    const tracer = new Tracer();
    const span = tracer.startSpan('agent.run');
    tracer.endSpan(span.spanId);
    const json = tracer.exportJSON();
    const parsed = JSON.parse(json);
    assert.ok(parsed.traceId);
    assert.equal(parsed.spans.length, 1);
    assert.equal(parsed.spans[0].operation, 'agent.run');
    // Import into new tracer
    const tracer2 = new Tracer();
    tracer2.importJSON(json);
    assert.equal(tracer2.spanCount(), 1);
    assert.equal(tracer2.getSpans()[0].operation, 'agent.run');
  });

  it('finds spans by predicate', () => {
    const tracer = new Tracer();
    tracer.startSpan('agent.run');
    tracer.startSpan('llm.call');
    tracer.startSpan('llm.call');
    const llmSpans = tracer.findSpans(s => s.operation === 'llm.call');
    assert.equal(llmSpans.length, 2);
  });

  it('finds spans by operation', () => {
    const tracer = new Tracer();
    tracer.startSpan('agent.run');
    tracer.startSpan('llm.call');
    assert.equal(tracer.findSpansByOperation('llm.call').length, 1);
    assert.equal(tracer.findSpansByOperation('tool.execute').length, 0);
  });

  it('gets span by id', () => {
    const tracer = new Tracer();
    const span = tracer.startSpan('agent.run');
    assert.equal(tracer.getSpanById(span.spanId)?.operation, 'agent.run');
    assert.equal(tracer.getSpanById('nonexistent'), undefined);
  });

  it('reports span count', () => {
    const tracer = new Tracer();
    assert.equal(tracer.spanCount(), 0);
    tracer.startSpan('agent.run');
    assert.equal(tracer.spanCount(), 1);
  });

  it('getChildren returns direct child spans', () => {
    const tracer = new Tracer();
    const parent = tracer.startSpan('agent.run');
    const c1 = tracer.startSpan('llm.call');
    tracer.endSpan(c1.spanId);
    // Must end c1 before starting c2 so c2's parent is root, not c1
    const c2 = tracer.startSpan('tool.execute');
    tracer.endSpan(c2.spanId);
    tracer.endSpan(parent.spanId);
    const kids = tracer.getChildren(parent.spanId);
    assert.equal(kids.length, 2);
    assert.ok(kids.some(k => k.operation === 'llm.call'));
    assert.ok(kids.some(k => k.operation === 'tool.execute'));
  });

  it('getChildren returns empty for leaf span', () => {
    const tracer = new Tracer();
    const span = tracer.startSpan('agent.run');
    tracer.endSpan(span.spanId);
    assert.equal(tracer.getChildren(span.spanId).length, 0);
  });

  it('getSpanTree builds full hierarchy', () => {
    const tracer = new Tracer();
    const root = tracer.startSpan('agent.run');
    const c1 = tracer.startSpan('llm.call');
    tracer.endSpan(c1.spanId);
    const c2 = tracer.startSpan('tool.execute');
    const gc = tracer.startSpan('llm.call');
    tracer.endSpan(gc.spanId);
    tracer.endSpan(c2.spanId);
    tracer.endSpan(root.spanId);
    const tree = tracer.getSpanTree();
    assert.equal(tree.length, 1);
    assert.equal(tree[0].operation, 'agent.run');
    assert.equal(tree[0].children.length, 2);
    const toolNode = tree[0].children.find(c => c.operation === 'tool.execute');
    assert.ok(toolNode);
    assert.equal(toolNode!.children.length, 1);
    assert.equal(toolNode!.children[0].operation, 'llm.call');
  });

  it('getSpanTree with spanId returns subtree', () => {
    const tracer = new Tracer();
    const root = tracer.startSpan('agent.run');
    const c1 = tracer.startSpan('tool.execute');
    const gc = tracer.startSpan('llm.call');
    tracer.endSpan(gc.spanId);
    tracer.endSpan(c1.spanId);
    tracer.endSpan(root.spanId);
    const subtree = tracer.getSpanTree(c1.spanId);
    assert.equal(subtree.length, 1);
    assert.equal(subtree[0].operation, 'tool.execute');
    assert.equal(subtree[0].children.length, 1);
  });

  // --- Causal links ---

  it('linkSpans creates causal link between spans', () => {
    const tracer = new Tracer();
    const s1 = tracer.startSpan('retrieval.search');
    tracer.endSpan(s1.spanId);
    const s2 = tracer.startSpan('tool.execute');
    tracer.endSpan(s2.spanId);
    const ok = tracer.linkSpans(s1.spanId, s2.spanId, 'triggered');
    assert.equal(ok, true);
    const links = tracer.getCausalLinks();
    assert.equal(links.length, 1);
    assert.equal(links[0].from, s1.spanId);
    assert.equal(links[0].to, s2.spanId);
    assert.equal(links[0].type, 'triggered');
  });

  it('linkSpans returns false for missing span', () => {
    const tracer = new Tracer();
    const s1 = tracer.startSpan('agent.run');
    tracer.endSpan(s1.spanId);
    assert.equal(tracer.linkSpans(s1.spanId, 'nonexistent'), false);
    assert.equal(tracer.linkSpans('nonexistent', s1.spanId), false);
  });

  it('getCausalChain follows upstream links', () => {
    const tracer = new Tracer();
    const s1 = tracer.startSpan('retrieval.search');
    tracer.endSpan(s1.spanId);
    const s2 = tracer.startSpan('tool.execute');
    tracer.endSpan(s2.spanId);
    const s3 = tracer.startSpan('llm.call');
    tracer.endSpan(s3.spanId);
    tracer.linkSpans(s1.spanId, s2.spanId);
    tracer.linkSpans(s2.spanId, s3.spanId);
    const chain = tracer.getCausalChain(s3.spanId, 'upstream');
    assert.equal(chain.length, 2);
    assert.equal(chain[0].operation, 'tool.execute');
    assert.equal(chain[1].operation, 'retrieval.search');
  });

  it('getCausalChain downstream direction', () => {
    const tracer = new Tracer();
    const s1 = tracer.startSpan('agent.run');
    tracer.endSpan(s1.spanId);
    const s2 = tracer.startSpan('tool.execute');
    tracer.endSpan(s2.spanId);
    tracer.linkSpans(s1.spanId, s2.spanId);
    const chain = tracer.getCausalChain(s1.spanId, 'downstream');
    assert.equal(chain.length, 1);
    assert.equal(chain[0].operation, 'tool.execute');
  });

  it('getCausalChain handles cycles gracefully', () => {
    const tracer = new Tracer();
    const s1 = tracer.startSpan('agent.run');
    tracer.endSpan(s1.spanId);
    const s2 = tracer.startSpan('tool.execute');
    tracer.endSpan(s2.spanId);
    tracer.linkSpans(s1.spanId, s2.spanId);
    tracer.linkSpans(s2.spanId, s1.spanId);
    const chain = tracer.getCausalChain(s1.spanId, 'upstream');
    // Should not infinite loop, returns at most the other span
    assert.ok(chain.length <= 2);
  });

  // --- getActiveSpanCount + getSpanDepth ---

  it('getActiveSpanCount returns 0 when no active spans', () => {
    const tracer = new Tracer();
    assert.strictEqual(tracer.getActiveSpanCount(), 0);
  });

  it('getActiveSpanCount tracks nested spans', () => {
    const tracer = new Tracer();
    const s1 = tracer.startSpan('agent.run');
    assert.strictEqual(tracer.getActiveSpanCount(), 1);
    const s2 = tracer.startSpan('llm.call');
    assert.strictEqual(tracer.getActiveSpanCount(), 2);
    tracer.endSpan(s2.spanId);
    assert.strictEqual(tracer.getActiveSpanCount(), 1);
    tracer.endSpan(s1.spanId);
    assert.strictEqual(tracer.getActiveSpanCount(), 0);
  });

  it('getSpanDepth returns 0 for root span', () => {
    const tracer = new Tracer();
    const s = tracer.startSpan('agent.run');
    tracer.endSpan(s.spanId);
    assert.strictEqual(tracer.getSpanDepth(s.spanId), 0);
  });

  it('getSpanDepth returns correct depth for nested spans', () => {
    const tracer = new Tracer();
    const s1 = tracer.startSpan('agent.run');
    const s2 = tracer.startSpan('tool.execute');
    const s3 = tracer.startSpan('llm.call');
    tracer.endSpan(s3.spanId);
    tracer.endSpan(s2.spanId);
    tracer.endSpan(s1.spanId);
    assert.strictEqual(tracer.getSpanDepth(s1.spanId), 0);
    assert.strictEqual(tracer.getSpanDepth(s2.spanId), 1);
    assert.strictEqual(tracer.getSpanDepth(s3.spanId), 2);
  });

  it('getSpanDepth returns 0 for unknown span', () => {
    const tracer = new Tracer();
    assert.strictEqual(tracer.getSpanDepth('nonexistent'), 0);
  });

  it('traceFn wraps sync fn in span', () => {
    const tracer = new Tracer();
    const { result, span } = tracer.traceFn('tool.execute', () => 42, { tool: 'calc' });
    assert.strictEqual(result, 42);
    assert.strictEqual(span.operation, 'tool.execute');
    assert.strictEqual(span.status, 'ok');
    assert.notStrictEqual(span.endTime, null);
  });

  it('traceFn marks error on throw', () => {
    const tracer = new Tracer();
    assert.throws(() => tracer.traceFn('tool.execute', () => { throw new Error('boom'); }));
    const spans = tracer.getSpans();
    assert.strictEqual(spans.length, 1);
    assert.strictEqual(spans[0].status, 'error');
  });

  it('getSlowSpans returns spans exceeding threshold', () => {
    const tracer = new Tracer();
    const slow = tracer.startSpan('agent.run');
    // simulate slow span by adjusting startTime
    slow.startTime = performance.now() - 200;
    tracer.endSpan(slow.spanId);
    const fast = tracer.startSpan('tool.execute');
    tracer.endSpan(fast.spanId);
    const result = tracer.getSlowSpans(100);
    assert.equal(result.length, 1);
    assert.equal(result[0].spanId, slow.spanId);
  });

  it('getErrorSpans returns only error spans', () => {
    const tracer = new Tracer();
    const s1 = tracer.startSpan('agent.run');
    tracer.endSpan(s1.spanId, 'ok');
    const s2 = tracer.startSpan('tool.execute');
    tracer.endSpan(s2.spanId, 'error');
    const s3 = tracer.startSpan('llm.call');
    tracer.endSpan(s3.spanId, 'ok');
    const errors = tracer.getErrorSpans();
    assert.equal(errors.length, 1);
    assert.equal(errors[0].spanId, s2.spanId);
  });

  it('exportOTLP produces valid OTLP structure', () => {
    const tracer = new Tracer();
    const s = tracer.startSpan('agent.run', { key: 'val' });
    tracer.addEvent(s.spanId, 'test-event', { detail: 42 });
    tracer.endSpan(s.spanId);
    const otlp = tracer.exportOTLP();
    assert.ok(otlp.resourceSpans);
    const scope = (otlp.resourceSpans as any[])[0].scopeSpans[0];
    assert.equal(scope.scope.name, 'agent-observability');
    assert.equal(scope.spans.length, 1);
    assert.equal(scope.spans[0].name, 'agent.run');
    assert.ok(scope.spans[0].attributes.length > 0);
    assert.equal(scope.spans[0].events.length, 1);
  });

  it('filter returns spans matching predicate', () => {
    const tracer = new Tracer();
    const s1 = tracer.startSpan('agent.run');
    tracer.endSpan(s1.spanId, 'error');
    const s2 = tracer.startSpan('llm.call');
    tracer.endSpan(s2.spanId, 'ok');
    const errors = tracer.filter(s => s.status === 'error');
    assert.equal(errors.length, 1);
    assert.equal(errors[0].operation, 'agent.run');
  });

  it('groupByOperation groups spans correctly', () => {
    const tracer = new Tracer();
    tracer.startSpan('agent.run');
    tracer.startSpan('agent.run');
    tracer.startSpan('llm.call');
    const groups = tracer.groupByOperation();
    assert.equal(Object.keys(groups).length, 2);
    assert.equal(groups['agent.run'].length, 2);
    assert.equal(groups['llm.call'].length, 1);
  });

  it('spanCountByStatus returns correct counts', () => {
    const tracer = new Tracer();
    const s1 = tracer.startSpan('agent.run');
    tracer.endSpan(s1.spanId, 'error');
    const s2 = tracer.startSpan('llm.call');
    tracer.endSpan(s2.spanId, 'ok');
    const s3 = tracer.startSpan('tool.execute'); // unset
    void s3;
    const counts = tracer.spanCountByStatus();
    assert.equal(counts['error'], 1);
    assert.equal(counts['ok'], 1);
    assert.equal(counts['unset'], 1);
  });

  it('clear resets all spans and generates new traceId', () => {
    const tracer = new Tracer();
    tracer.startSpan('agent.run');
    assert.equal(tracer.getSpans().length, 1);
    const oldTraceId = tracer.getTraceReport().traceId;
    tracer.clear();
    assert.equal(tracer.getSpans().length, 0);
    assert.notEqual(tracer.getTraceReport().traceId, oldTraceId);
  });

  it('getSpanDuration returns ms for completed span, null for active', () => {
    const tracer = new Tracer();
    const span = tracer.startSpan('agent.run');
    assert.equal(tracer.getSpanDuration(span.spanId), null);
    tracer.endSpan(span.spanId);
    const dur = tracer.getSpanDuration(span.spanId);
    assert.ok(dur !== null && dur >= 0);
    assert.equal(tracer.getSpanDuration('nonexistent'), null);
  });


  it('traceAsync wraps async fn in span', async () => {
    const tracer = new Tracer();
    const { result, span } = await tracer.traceAsync('tool.execute', async () => {
      await new Promise(r => setTimeout(r, 5));
      return 42;
    });
    assert.equal(result, 42);
    assert.equal(span.status, 'ok');
    assert.ok(span.endTime !== null);
  });

  it('traceAsync marks error on rejection', async () => {
    const tracer = new Tracer();
    await assert.rejects(
      () => tracer.traceAsync('tool.execute', async () => { throw new Error('boom'); }),
      /boom/
    );
    const spans = tracer.getSpans();
    assert.equal(spans.length, 1);
    assert.equal(spans[0].status, 'error');
  });

  it('totalDuration sums completed spans', () => {
    const tracer = new Tracer();
    const s1 = tracer.startSpan('agent.run');
    tracer.endSpan(s1.spanId);
    const s2 = tracer.startSpan('llm.call');
    tracer.endSpan(s2.spanId);
    const s3 = tracer.startSpan('tool.execute'); // active, not ended
    assert.equal(tracer.totalDuration(), tracer.getSpans()[0].endTime! - tracer.getSpans()[0].startTime + tracer.getSpans()[1].endTime! - tracer.getSpans()[1].startTime);
  });

  it('getPercentile returns p50/p99 of completed spans', () => {
    const tracer = new Tracer();
    // Create spans with known durations (sorted by completion)
    for (let i = 0; i < 10; i++) {
      const span = tracer.startSpan('llm.call');
      // Force known startTime/endTime
      span.startTime = i * 100;
      span.endTime = i * 100 + (i + 1) * 10; // durations: 10,20,30,...100
    }
    const p50 = tracer.getPercentile(50);
    const p99 = tracer.getPercentile(99);
    assert.ok(p50 >= 10 && p50 <= 100);
    assert.ok(p99 >= p50);
  });

  it('getPercentile returns 0 for no spans', () => {
    const tracer = new Tracer();
    assert.equal(tracer.getPercentile(50), 0);
  });

  it('spanCountByStatus counts by status', () => {
    const tracer = new Tracer();
    const s1 = tracer.startSpan('agent.run');
    const s2 = tracer.startSpan('llm.call');
    tracer.endSpan(s1.spanId, 'ok');
    tracer.endSpan(s2.spanId, 'error');
    const counts = tracer.spanCountByStatus();
    assert.equal(counts.ok, 1);
    assert.equal(counts.error, 1);
    assert.equal(counts.unset, 0);
  });

  it('addAttribute adds to existing span', () => {
    const tracer = new Tracer();
    const span = tracer.startSpan('agent.run');
    assert.ok(tracer.addAttribute(span.spanId, 'foo', 'bar'));
    const retrieved = tracer.getSpanById(span.spanId);
    assert.equal(retrieved!.attributes.foo, 'bar');
  });

  it('addAttribute returns false for missing span', () => {
    const tracer = new Tracer();
    assert.ok(!tracer.addAttribute('nope', 'key', 'val'));
  });

  it('hasSpan checks existence', () => {
    const tracer = new Tracer();
    const span = tracer.startSpan('agent.run');
    assert.ok(tracer.hasSpan(span.spanId));
    assert.ok(!tracer.hasSpan('nope'));
  });

  it('renameSpan changes operation', () => {
    const tracer = new Tracer();
    const span = tracer.startSpan('agent.run');
    tracer.endSpan(span.spanId);
    assert.ok(tracer.renameSpan(span.spanId, 'tool.execute'));
    assert.equal(tracer.getSpanById(span.spanId)!.operation, 'tool.execute');
    assert.ok(!tracer.renameSpan('nope', 'llm.call'));
  });

  it('cloneSpan creates independent copy', () => {
    const tracer = new Tracer();
    const span = tracer.startSpan('agent.run', { key: 'val' });
    tracer.endSpan(span.spanId);
    const clone = tracer.cloneSpan(span.spanId)!;
    assert.notEqual(clone.spanId, span.spanId);
    assert.equal(clone.operation, 'agent.run');
    assert.equal(clone.attributes.key, 'val');
    assert.equal(clone.parentSpanId, null);
    assert.equal(tracer.spanCount(), 2);
    assert.equal(tracer.cloneSpan('nope'), undefined);
  });

  it('mergeTracer combines spans from two tracers', () => {
    const tracer = new Tracer();
    const other = new Tracer();
    const s1 = other.startSpan('llm.call');
    other.endSpan(s1.spanId);
    const s2 = other.startSpan('tool.execute');
    other.endSpan(s2.spanId);
    const count = tracer.mergeTracer(other);
    assert.equal(count, 2);
    assert.equal(tracer.spanCount(), 2);
  });
});
