# 🔍 Agent Observability

A zero-dependency TypeScript toolkit for **observing, governing, and evaluating** AI agent execution.

Three composable components unified via a high-level `AgentObserver` facade:

| Component | Role | Key Capability |
|-----------|------|---------------|
| **Tracer** | Distributed tracing | Parent-child spans, causal links, OTLP export |
| **PolicyEngine** | Guardrails | Block destructive ops, rate/cost limits, PII detection |
| **Evaluator** | Quality scoring | Weighted multi-dimension evaluation (latency, reliability, compliance) |

**245 tests passing · Zero dependencies · Pure TypeScript**

## ⚡ 30-Second Quick Start

Copy, paste, run — see observability in action:

```ts
import { AgentObserver } from './src/index.js';

const obs = new AgentObserver();

obs.startRun('hello', 'Test run');
obs.llmCall('gpt-4', 'Hi', 'Hello!');
obs.endRun();

console.log(obs.reportMarkdown());
// ✅ Score, token usage, latency — all captured
```

**Add guardrails** (one line):

```ts
obs.getPolicyEngine().loadFromJSON([
  { name: 'no-rm', description: 'Block rm', category: 'tool_execution', type: 'blockDestructiveOps' },
]);
const { allowed } = obs.toolExecute('bash', 'rm -rf /');
// → allowed: false, violation logged
```

---

## Quick Start (Full Example)

```ts
import { AgentObserver } from './src/index.js';

const observer = new AgentObserver();

// Configure guardrails
observer.getPolicyEngine().loadFromJSON([
  { name: 'block_rm', description: 'Block destructive ops', category: 'tool_execution', type: 'blockDestructiveOps' },
  { name: 'rate', description: 'Rate limit', category: 'rate_control', type: 'rateLimit', config: { maxCalls: 20, windowMs: 60000 } },
]);

// --- Run an agent ---
observer.startRun('my-agent', 'Summarize document');
observer.llmCall('gpt-4', 'Summarize...', 'Here is the summary...', { promptTokens: 120, completionTokens: 80 });

// Tool calls are automatically policy-checked
const { allowed, span } = observer.toolExecute('bash', 'rm -rf /tmp/test');
if (!allowed) console.log('Blocked:', span.attributes.policyViolations);

observer.endRun();

// --- Get results ---
const report = observer.getReport();
console.log('Score:', report.aggregateScore);          // 0-1 weighted score
console.log('Errors:', report.traceReport.errorCount);
console.log(observer.reportMarkdown());                 // Human-readable report
```

## API Reference

### AgentObserver (Facade)

The main entry point. Wraps Tracer + PolicyEngine + Evaluator.

| Method | Description |
|--------|-------------|
| `startRun(agentId, task)` | Begin a root agent span |
| `endRun()` | End the root span |
| `llmCall(model, prompt, completion, tokens?)` | Trace an LLM call |
| `toolExecute(tool, input)` | Execute tool through policy engine |
| `memoryOperation(type, attrs)` | Trace memory read/write |
| `retrievalSearch(method, attrs)` | Trace a retrieval operation |
| `getReport()` | Full report: trace + eval + aggregate score |
| `reportMarkdown()` | Human-readable markdown report |
| `spanStats()` | Quick stats: total, completed, errors, by-operation |
| `getErrorSummary()` | List of errors with operation and reason |
| `getErrorRate()` | Error ratio (0-1) |
| `observeSync(fn)` | Wrap a sync function with auto-tracing |
| `observeAsync(fn, agentId?)` | Wrap an async function with auto-tracing |
| `observeWithPolicy(fn, agentId?)` | Wrap a function with policy-guarded tool access |

### Tracer

OpenTelemetry-inspired distributed tracing with causal linking.

**Core:**

| Method | Description |
|--------|-------------|
| `startSpan(operation, attributes?)` | Start a new span (pushes onto active stack) |
| `endSpan(spanId, status?)` | End a span, record duration |
| `addEvent(spanId, name, attributes?)` | Attach a timestamped event to a span |
| `getActiveSpan()` | Current top-of-stack span |
| `getSpans()` | Return all spans |
| `getTraceReport()` | Aggregate: duration by operation, error count, total duration |
| `clear()` | Reset all spans, generate new traceId |

**Query & Analysis:**

| Method | Description |
|--------|-------------|
| `findSpansByOperation(op)` | Filter spans by operation type |
| `filter(predicate)` | Custom filter with predicate |
| `groupByOperation()` | Group spans into `{ [op]: Span[] }` |
| `spanCountByStatus()` | Count spans by status: `{ ok, error, unset }` |
| `getSlowSpans(thresholdMs)` | Find spans exceeding duration threshold |
| `getErrorSpans()` | Return all error-status spans |
| `getSpanDuration(spanId)` | Duration in ms (null if still active) |

**Hierarchy & Causal Links:**

| Method | Description |
|--------|-------------|
| `getChildren(spanId)` | Direct child spans |
| `getSpanTree(spanId?)` | Full nested tree (or subtree) |
| `getSpanDepth(spanId)` | Nesting depth (0 = root) |
| `getActiveSpanCount()` | Number of currently active (open) spans |
| `linkSpans(from, to, type?)` | Create a causal link between two spans |
| `getCausalChain(spanId, direction?)` | Follow causal links upstream or downstream |

**Serialization:**

| Method | Description |
|--------|-------------|
| `exportJSON()` / `importJSON(json)` | Serialize/restore trace data |
| `exportOTLP()` | Export in OTLP-compatible structure |
| `traceFn(operation, fn, attributes?)` | Wrap a sync function in a span (auto-end, catch errors) |

### PolicyEngine

Rule-based guardrails with per-category evaluation.

| Method | Description |
|--------|-------------|
| `addPolicy(category, rule)` | Register a rule under a category |
| `removePolicy(category, ruleName)` | Remove a rule |
| `evaluate(category, input)` | Run all rules in a category; returns `{ allowed, violations }` |
| `evaluateAll(input)` | Run all categories at once |
| `loadFromJSON(data)` | Bulk-load rules from JSON config |
| `importRules(data)` | Replace all rules (returns count) |
| `exportJSON()` | Export current rule definitions |
| `enableRule(category, name)` / `disableRule(category, name)` | Toggle rules without removing |
| `isRuleEnabled(category, name)` | Check if a rule is active |
| `ruleNames()` | List all rule names |
| `getRulesByCategory(category)` | Get rules for a category |
| `listCategories()` | List all categories |
| `ruleCount(category)` | Count rules in a category |
| `clearCategory(category)` | Remove all rules in a category |

**Built-in rule builders:** `blockDestructiveOps()`, `costLimit(cfg)`, `rateLimit(cfg)`, `piiFilter()`

### Evaluator

Weighted multi-dimension quality scoring.

| Method | Description |
|--------|-------------|
| `addCheck(name, fn, weight?)` | Register an evaluation check |
| `evaluate(spans, dimensions?)` | Run checks (optionally filter by dimension names) |
| `aggregateScore(results)` | Weighted average (0-1) |
| `passRate(results)` | Fraction of checks scoring ≥ 0.5 |
| `listChecks()` | List registered check names |
| `removeCheck(name)` | Remove a check |
| `setWeight(name, weight)` | Update a check's weight |
| `resetChecks()` | Remove all checks |

**Built-in checks:** `policyComplianceCheck` (weight 1.5), `latencyCheck` (1.0), `reliabilityCheck` (2.0), `costEfficiencyCheck` (1.0)

## Concepts

### Spans & Traces

A **Span** represents a unit of work: an LLM call, tool execution, memory operation, etc. Spans form a parent-child tree — `startRun()` creates the root, and each subsequent operation is a child.

```
agent.run (root)
├── llm.call "Summarize..."
├── tool.execute "bash ls -la"  ✅ ok
├── tool.execute "bash rm -rf"  ❌ blocked by policy
└── memory.write
```

### Causal Links

Beyond parent-child hierarchy, `linkSpans()` creates explicit causal relationships between spans. This enables **causal chain tracing** — follow `getCausalChain()` upstream (what caused this?) or downstream (what did this cause?).

### Policy Evaluation

Rules are organized by **category** (e.g., `tool_execution`, `rate_control`). Each category is evaluated independently, so you can enforce different guardrails for different operations. Rules can be enabled/disabled dynamically.

### Evaluation Dimensions

The Evaluator scores agent runs across multiple dimensions with configurable weights:

- **Policy compliance** — Were any policy rules violated?
- **Latency** — How fast were the operations?
- **Reliability** — What fraction of operations succeeded?
- **Cost efficiency** — Token usage vs. output quality

The aggregate score is a weighted average, with `reliability` weighted highest (2.0) by default.

## Advanced Examples

### Causal Chain Tracing

```ts
const tracer = observer.getTracer();
const spanA = tracer.startSpan('tool.execute', { tool: 'web_search' });
tracer.endSpan(spanA.spanId);

const spanB = tracer.startSpan('tool.execute', { tool: 'summarize' });
tracer.endSpan(spanB.spanId);

// Link: search caused summarize
tracer.linkSpans(spanA.spanId, spanB.spanId, 'causal');

// Trace the chain
const chain = tracer.getCausalChain(spanB.spanId, 'upstream');
// => [spanB, spanA] — what led to this operation
```

### OTLP Export

```ts
const tracer = observer.getTracer();
const otlp = tracer.exportOTLP();
// Send to your OTel collector
```

### Observe with Policy-Guarded Tools

```ts
const { result, report } = observer.observeWithPolicy(({ tool }) => {
  // tool() automatically checks policies
  const r1 = tool('bash', 'ls -la');     // { allowed: true }
  const r2 = tool('bash', 'rm -rf /');   // { allowed: false, reason: '...' }
  return r1.allowed && !r2.allowed;
});
console.log('Score:', report.aggregateScore);
```

### Custom Evaluation Checks

```ts
const evaluator = observer.getEvaluator();

evaluator.addCheck('relevance', (spans) => {
  const llmSpans = spans.filter(s => s.operation === 'llm.call');
  // Your custom scoring logic
  const score = llmSpans.length > 0 ? 0.85 : 0;
  return [{ dimension: 'relevance', score, reason: `${llmSpans.length} LLM calls` }];
}, 1.5); // weight
```

## Project Structure

```
src/
  index.ts          # AgentObserver facade + types
  tracer.ts         # Distributed tracing (Span, TraceReport, causal links, OTLP)
  policy-engine.ts  # Guardrails & policy evaluation
  evaluator.ts      # Quality scoring across dimensions
  otel-genai.ts     # OTel GenAI semantic-conventions export adapter

tests/                     # 245 tests, 26 suites
  tracer.test.ts           # 73  — spans, stack, tree, causal links, serialization
  evaluator.test.ts        # 44  — checks, weights, aggregation
  policy-engine.test.ts    # 35  — rules, categories, enable/disable
  otel-genai.test.ts       # 30  — semantic mapping + lint gate
  integration.test.ts      # 23  — facade end-to-end flows
  rate-limit.test.ts       # 11  — windowed rate limiting
  regressions-0907.test.ts # 12  — red-first regression bugs (see below)
  cycle1/2/3.test.ts       # 17  — review-cycle findings
```

## Running Tests

```bash
npm test
```

### What the tests guard against

The regression suites (`regressions-0907` + `cycle1-3`) are built **red-first** from
real bugs caught in review cycles. Each one is a generalizable failure concept:

| Concept | The bug | The guard |
|---------|---------|-----------|
| **Ghost parents** | `clear()` reset spans but not the active stack — new spans silently inherited a dead `parentSpanId` and vanished from `getSpanTree()` | Reset APIs must be behavioral twins; a span started after `clear()` must appear as a tree root |
| **Duplicate chains** | `getCausalChain()` pushed a span to results *before* marking it visited — diamond topologies (A→B, A→C, B→D, C→D) reported D twice | Mark visited before push; every span appears exactly once |
| **Partial imports** | `importJSON()` mutated state straight from untrusted JSON — a malformed payload left mixed state (new traceId, old spans) | Validate-then-mutate atomically: bad input changes nothing |
| **Read APIs that write** | `getTraceHash()` sorted `this.spans` in place — a pure query reordered stored data | Readers never mutate; hash a sorted copy instead |
| **Name-as-identity** | `buildRule()` dropped `def.name`/`description`, so JSON-loaded rules got hard-coded identities and `disableRule(category, name)` was a silent no-op | A rule's declared name is its identity; export→import round-trip must preserve it (and disabled flags) |
| **Dead-key counts** | `enabledCount()` derived from a stale bookkeeping set diverging from live rules | Counts come from live keys, never parallel state |

The meta-lesson: **a fake-green test is worse than no test**. The round-trip test for
rule disabling kept passing while the disable itself was a no-op — the assertion
checked the wrong thing, so the suite looked healthy while the guardrail was dead.
When a green suite still surprises you, audit what the assertions actually observe,
not just that they pass.

## OTel GenAI-Convention Export

`src/otel-genai.ts` is an export-boundary adapter that maps internal spans to the
OpenTelemetry GenAI semantic conventions (**pinned against
`semantic-conventions-genai` @ `c739977`, 2026-07-30** — all `gen_ai.*`
conventions are Status: Development; on the repo's first tagged release the pin
is re-verified):

- `agent.run` → `invoke_agent {name}` · `llm.call` → `chat {model}` ·
  `tool.execute` → `execute_tool {name}` · `retrieval.search` → `retrieval` ·
  `memory.write` → `upsert_memory` · `memory.read` → `search_memory`
- Prompt/completion/tool args/memory queries are **Opt-In** content, gated by
  `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` — off by default per spec
- Custom info with no spec equivalent lives under `ao.*` (no self-invented
  `gen_ai.*` keys)
- `lintGenAiSpans()` is a 5-rule compliance gate (Required attrs, span-name
  formats, `error.type`, Opt-In leakage, integer usage) usable in CI
- `exportGenAiOtlp()` emits OTLP-JSON `resourceSpans` — importable into
  Jaeger/Tempo/Datadog backends that aggregate v1.37+ conventions natively

```ts
import { lintGenAiSpans, exportGenAiOtlp } from './src/index.js';
const result = lintGenAiSpans(tracer.getSpans()); // zero-intrusion
const otlp = exportGenAiOtlp(tracer.getSpans());  // → OTLP-JSON
```

## Design Principles

1. **Zero dependencies** — Pure TypeScript on Node.js built-ins. No OTel SDK required.
2. **Composable** — Use Tracer alone, or combine all three via AgentObserver.
3. **Behavior-based evaluation** — Score what the agent *did*, not just what it returned.
4. **Policy as code** — Guardrails are data-driven (JSON-loadable), not hardcoded.
5. **OTel-aligned** — Span model and attributes follow OpenTelemetry GenAI semantic conventions.

## License

MIT
