import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { mapSpan, lintGenAiSpans, exportGenAiOtlp, evaluationEventAttributes } from '../src/otel-genai.js';
import type { AdapterSpan } from '../src/otel-genai.js';
import { Tracer } from '../src/tracer.js';

const ENV_KEY = 'OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT';
let savedEnv: string | undefined;

function span(op: string, attrs: Record<string, unknown> = {}, status: 'ok' | 'error' | 'unset' = 'ok'): AdapterSpan {
  return { traceId: '11111111-2222-3333-4444-555555555555', spanId: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee', parentSpanId: null,
    operation: op, startTime: 100, endTime: 200, attributes: attrs, status, events: [] };
}

/** A representative 7-span trace exactly as Tracer emits it. */
function demoSpans(): AdapterSpan[] {
  return [
    span('agent.run', { agentId: 'research-agent', task: 'find papers' }),
    span('llm.call', { 'gen_ai.request.model': 'gpt-4o-mini', promptTokens: 120, completionTokens: 80, 'gen_ai.prompt': 'hi', 'gen_ai.completion': 'hello' }),
    span('tool.execute', { 'tool.name': 'bash', 'tool.input': 'ls -la' }, 'error'),
    span('memory.write', { namespace: 'user-prefs', items: 3 }),
    span('memory.read', { namespace: 'user-prefs', query: 'theme', results: 2 }),
    span('retrieval.search', { query: 'otel genai', top_k: 5, method: 'vector' }),
  ];
}

describe('mapSpan — operation mapping (spec: span name = operation verb)', () => {
  it('agent.run → invoke_agent {name} INTERNAL with gen_ai.agent.name', () => {
    const m = mapSpan(span('agent.run', { agentId: 'research-agent', task: 'find papers' }));
    assert.equal(m.name, 'invoke_agent research-agent');
    assert.equal(m.kind, 'SPAN_KIND_INTERNAL');
    assert.equal(m.operationName, 'invoke_agent');
    assert.equal(m.attributes['gen_ai.agent.name'], 'research-agent');
    // custom info isolated in ao.* namespace, never self-invented gen_ai.* keys
    assert.equal(m.attributes['ao.task'], 'find papers');
    assert.equal('gen_ai.task' in m.attributes, false);
  });

  it('agent.run falls back to "agent" when no agentId', () => {
    const m = mapSpan(span('agent.run', {}));
    assert.equal(m.name, 'invoke_agent agent');
  });

  it('llm.call → chat {model} CLIENT with integer usage tokens', () => {
    const m = mapSpan(span('llm.call', { 'gen_ai.request.model': 'gpt-4o-mini', promptTokens: 120, completionTokens: 80 }));
    assert.equal(m.name, 'chat gpt-4o-mini');
    assert.equal(m.kind, 'SPAN_KIND_CLIENT');
    assert.equal(m.attributes['gen_ai.usage.input_tokens'], 120);
    assert.equal(m.attributes['gen_ai.usage.output_tokens'], 80);
  });

  it('llm.call model falls back to plain "model" attr', () => {
    const m = mapSpan(span('llm.call', { model: 'llama-3' }));
    assert.equal(m.name, 'chat llama-3');
    assert.equal(m.attributes['gen_ai.request.model'], 'llama-3');
  });

  it('tool.execute → execute_tool {name}; error status maps to error.type=policy_denied', () => {
    const ok = mapSpan(span('tool.execute', { 'tool.name': 'bash' }));
    assert.equal(ok.name, 'execute_tool bash');
    assert.equal(ok.attributes['gen_ai.tool.name'], 'bash');
    const err = mapSpan(span('tool.execute', { 'tool.name': 'bash' }, 'error'));
    assert.equal(err.attributes['error.type'], 'policy_denied');
  });

  it('retrieval.search → bare "retrieval" CLIENT with top_k; method isolated in ao.*', () => {
    const m = mapSpan(span('retrieval.search', { top_k: 5, method: 'vector' }));
    assert.equal(m.name, 'retrieval');
    assert.equal(m.kind, 'SPAN_KIND_CLIENT');
    assert.equal(m.attributes['gen_ai.retrieval.top_k'], 5);
    assert.equal(m.attributes['ao.retrieval.method'], 'vector');
  });

  it('memory.write → upsert_memory INTERNAL with store.id + single record.count', () => {
    const m = mapSpan(span('memory.write', { namespace: 'user-prefs', items: 3 }));
    assert.equal(m.name, 'upsert_memory');
    assert.equal(m.kind, 'SPAN_KIND_INTERNAL');
    assert.equal(m.attributes['gen_ai.memory.store.id'], 'user-prefs');
    assert.equal(m.attributes['gen_ai.memory.record.count'], 3);
  });

  it('memory.read → search_memory; record.count prefers results over items', () => {
    const m = mapSpan(span('memory.read', { namespace: 'user-prefs', query: 'theme', results: 2, items: 9 }));
    assert.equal(m.name, 'search_memory');
    assert.equal(m.attributes['gen_ai.memory.record.count'], 2);
  });

  it('every mapped span carries gen_ai.operation.name (Required attr)', () => {
    for (const s of demoSpans()) {
      assert.ok(mapSpan(s).attributes['gen_ai.operation.name'], `missing operation.name for ${s.operation}`);
    }
  });

  it('unknown operation passes through with operation name preserved', () => {
    const m = mapSpan(span('custom.op', { foo: 'bar' }));
    assert.equal(m.name, 'custom.op');
    assert.equal(m.attributes['gen_ai.operation.name'], 'custom.op');
    assert.equal(m.attributes['foo'], 'bar');
  });

  it('conversation.id defaults to traceId, overridable via opts', () => {
    const a = mapSpan(span('agent.run', {}));
    assert.equal(a.attributes['gen_ai.conversation.id'], '11111111-2222-3333-4444-555555555555');
    const b = mapSpan(span('agent.run', {}), { conversationId: 'conv-42' });
    assert.equal(b.attributes['gen_ai.conversation.id'], 'conv-42');
  });
});

describe('mapSpan — content capture is Opt-In (spec default OFF)', () => {
  it('default: memory query text absent; llm prompt/completion not on span or event', () => {
    const mr = mapSpan(span('memory.read', { query: 'theme' }));
    assert.equal('gen_ai.memory.query.text' in mr.attributes, false);
    const llm = mapSpan(span('llm.call', { 'gen_ai.prompt': 'p', 'gen_ai.completion': 'c' }));
    assert.equal('gen_ai.prompt' in llm.attributes, false);
    assert.equal(llm.events.length, 0);
  });

  it('default: retrieval query text absent, tool arguments absent', () => {
    assert.equal('gen_ai.retrieval.query.text' in mapSpan(span('retrieval.search', { query: 'q' })).attributes, false);
    assert.equal('gen_ai.tool.call.arguments' in mapSpan(span('tool.execute', { 'tool.input': 'x' })).attributes, false);
  });

  it('captureContent=true → details event with aggregated v1.37 message structure', () => {
    const m = mapSpan(span('llm.call', { 'gen_ai.request.model': 'm', 'gen_ai.prompt': 'question', 'gen_ai.completion': 'answer' }), { captureContent: true });
    const ev = m.events.find(e => e.name === 'gen_ai.client.inference.operation.details');
    assert.ok(ev);
    const input = ev!.attributes['gen_ai.input.messages'] as Array<{ role: string; parts: Array<{ type: string; content: string }> }>;
    assert.equal(input[0].role, 'user');
    assert.equal(input[0].parts[0].content, 'question');
    const output = ev!.attributes['gen_ai.output.messages'] as Array<{ role: string; finish_reason: string }>;
    assert.equal(output[0].role, 'assistant');
    assert.equal(output[0].finish_reason, 'stop');
  });

  it('captureContent=true → memory/retrieval query text + tool arguments present', () => {
    assert.equal(mapSpan(span('memory.read', { query: 'theme' }), { captureContent: true }).attributes['gen_ai.memory.query.text'], 'theme');
    assert.equal(mapSpan(span('retrieval.search', { query: 'q' }), { captureContent: true }).attributes['gen_ai.retrieval.query.text'], 'q');
    assert.ok(mapSpan(span('tool.execute', { 'tool.input': 'ls' }), { captureContent: true }).attributes['gen_ai.tool.call.arguments']);
  });

  it('env var OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true unlocks capture', () => {
    process.env[ENV_KEY] = 'true';
    try {
      assert.equal(mapSpan(span('memory.read', { query: 'x' })).attributes['gen_ai.memory.query.text'], 'x');
    } finally {
      delete process.env[ENV_KEY];
    }
  });

  it('env var variants 1/yes (case-insensitive) also unlock; "0" does not', () => {
    for (const val of ['1', 'YES', 'True']) {
      process.env[ENV_KEY] = val;
      assert.ok(mapSpan(span('memory.read', { query: 'x' })).attributes['gen_ai.memory.query.text'], `val=${val}`);
    }
    process.env[ENV_KEY] = '0';
    assert.equal('gen_ai.memory.query.text' in mapSpan(span('memory.read', { query: 'x' })).attributes, false);
    delete process.env[ENV_KEY];
  });
});

describe('lintGenAiSpans — CI compliance gate (pinned @c739977)', () => {
  it('clean 6-operation trace passes with capture off', () => {
    const r = lintGenAiSpans(demoSpans());
    assert.deepEqual(r.violations, []);
    assert.equal(r.ok, true);
  });

  it('clean trace passes with capture on (opt-in attrs allowed)', () => {
    const r = lintGenAiSpans(demoSpans(), { captureContent: true });
    assert.equal(r.ok, true);
  });

  it('error span without error.type → violation (llm.call error has no mapped error.type)', () => {
    const r = lintGenAiSpans([span('llm.call', { model: 'm' }, 'error')]);
    assert.equal(r.ok, false);
    assert.ok(r.violations.some(v => v.includes('error span without error.type')));
  });

  it('non-integer usage tokens → violation', () => {
    const r = lintGenAiSpans([span('llm.call', { model: 'm', promptTokens: '120' })]);
    assert.ok(r.violations.some(v => v.includes('gen_ai.usage.input_tokens not integer')));
  });

  it('violations are labelled with operation and spanId prefix', () => {
    const r = lintGenAiSpans([span('llm.call', { model: 'm' }, 'error')]);
    assert.match(r.violations[0], /^llm\.call\(aaaaaaaa\): /);
  });
});

describe('evaluationEventAttributes — gen_ai.evaluation.result event (v1.38)', () => {
  it('maps score/label/explanation with low-cardinality labels', () => {
    const a = evaluationEventAttributes('policy_compliance', 0.5, '2 of 4 checks failed');
    assert.equal(a['gen_ai.evaluation.name'], 'policy_compliance');
    assert.equal(a['gen_ai.evaluation.score.value'], 0.5);
    assert.equal(a['gen_ai.evaluation.score.label'], 'warn');
    assert.equal(a['gen_ai.evaluation.explanation'], '2 of 4 checks failed');
    assert.equal(evaluationEventAttributes('latency', 1.0, 'ok')['gen_ai.evaluation.score.label'], 'pass');
  });
});

describe('exportGenAiOtlp — OTLP-JSON resourceSpans', () => {
  it('produces resourceSpans > scopeSpans > spans nesting', () => {
    const otlp = exportGenAiOtlp(demoSpans(), {}, 1_000_000);
    assert.equal(otlp.resourceSpans.length, 1);
    const spans = otlp.resourceSpans[0].scopeSpans[0].spans;
    assert.equal(spans.length, 6);
    assert.equal(spans[0].name, 'invoke_agent research-agent');
  });

  it('IDs normalized to 32-hex traceId and 16-hex spanId', () => {
    const spans = exportGenAiOtlp(demoSpans(), {}, 1e6).resourceSpans[0].scopeSpans[0].spans;
    assert.match(spans[0].traceId, /^[0-9a-f]{32}$/);
    assert.match(spans[0].spanId, /^[0-9a-f]{16}$/);
    assert.equal(spans[0].parentSpanId, undefined); // demo root has no parent
  });

  it('nanosecond times anchored to epoch; end >= start; error span → STATUS_CODE_ERROR', () => {
    const spans = exportGenAiOtlp(demoSpans(), {}, 1_000_000).resourceSpans[0].scopeSpans[0].spans;
    for (const s of spans) {
      assert.ok(BigInt(s.endTimeUnixNano) >= BigInt(s.startTimeUnixNano));
    }
    const tool = spans.find(s => s.name.startsWith('execute_tool'))!;
    assert.equal(tool.status.code, 'STATUS_CODE_ERROR');
  });

  it('numeric attributes → intValue, strings → stringValue', () => {
    const spans = exportGenAiOtlp(demoSpans(), {}, 1e6).resourceSpans[0].scopeSpans[0].spans;
    const mem = spans.find(s => s.name === 'upsert_memory')!;
    const cnt = mem.attributes.find((a: { key: string }) => a.key === 'gen_ai.memory.record.count')!;
    assert.deepEqual(cnt.value, { intValue: 3 });
    const agent = spans.find(s => s.name.startsWith('invoke_agent'))!;
    const nm = agent.attributes.find((a: { key: string }) => a.key === 'gen_ai.agent.name')!;
    assert.deepEqual(nm.value, { stringValue: 'research-agent' });
  });

  it('opt-in details event serialized into OTLP span events', () => {
    const spans = exportGenAiOtlp(demoSpans(), { captureContent: true }, 1e6).resourceSpans[0].scopeSpans[0].spans;
    const chat = spans.find(s => s.name.startsWith('chat'))!;
    assert.ok(chat.events.some(e => e.name === 'gen_ai.client.inference.operation.details'));
  });
});

describe('integration — real Tracer spans feed the adapter unmodified', () => {
  it('zero-intrusion: getSpans() → lint PASS', () => {
    const t = new Tracer();
    const root = t.startSpan('agent.run', { agentId: 'obs-agent', task: 'watch' });
    const llm = t.startSpan('llm.call', { 'gen_ai.request.model': 'qwen2.5:7b', promptTokens: 10, completionTokens: 5, 'gen_ai.prompt': 'q', 'gen_ai.completion': 'a' });
    t.endSpan(llm.spanId);
    const tool = t.startSpan('tool.execute', { 'tool.name': 'grep' }, );
    t.endSpan(tool.spanId, 'error');
    t.endSpan(root.spanId);
    const r = lintGenAiSpans(t.getSpans());
    assert.equal(r.ok, true);
    assert.equal(t.getSpans().length, 3);
  });

  it('trace-level: Tracer → exportGenAiOtlp → lint all compose', () => {
    const t = new Tracer();
    const a = t.startSpan('memory.write', { namespace: 'kb', items: 7 });
    t.endSpan(a.spanId);
    const b = t.startSpan('memory.read', { namespace: 'kb', query: 'otel', results: 3 });
    t.endSpan(b.spanId);
    const otlp = exportGenAiOtlp(t.getSpans());
    const spans = otlp.resourceSpans[0].scopeSpans[0].spans;
    assert.equal(spans.length, 2);
    assert.equal(spans[0].name, 'upsert_memory');
    assert.equal(spans[1].name, 'search_memory');
    assert.equal(lintGenAiSpans(t.getSpans()).ok, true);
  });
});
