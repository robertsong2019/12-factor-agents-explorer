import { Tracer } from './tracer.js';
import type { Span } from './tracer.js';
import { PolicyEngine } from './policy-engine.js';
import { Evaluator, policyComplianceCheck, latencyCheck, reliabilityCheck, costEfficiencyCheck } from './evaluator.js';
import type { EvalCheckResult } from './evaluator.js';
export { TrendTracker } from './evaluator.js';

export interface ObservabilityReport {
  traceReport: ReturnType<Tracer['getTraceReport']>;
  evalResults: EvalCheckResult[];
  aggregateScore: number;
}

export type AlertCallback = (alert: { type: 'policy_violation' | 'high_error_rate' | 'slow_span'; details: string; timestamp: number }) => void;

export class AgentObserver {
  private tracer: Tracer;
  private policyEngine: PolicyEngine;
  private evaluator: Evaluator;
  private rootSpanId: string | null = null;

  private alerts: AlertCallback[] = [];

  /** Register an alert callback */
  onAlert(cb: AlertCallback): void {
    this.alerts.push(cb);
  }

  private emitAlert(type: 'policy_violation' | 'high_error_rate' | 'slow_span', details: string): void {
    for (const cb of this.alerts) cb({ type, details, timestamp: Date.now() });
  }

  /** Run a full audit: evaluate all spans, check regressions, return structured report */
  quickAudit(): {
    score: number;
    errorRate: number;
    policyViolations: number;
    slowSpans: number;
    topIssues: EvalCheckResult[];
    markdown: string;
  } {
    const spans = this.tracer.getSpans();
    const results = this.evaluator.evaluate(spans);
    const score = this.evaluator.aggregateScore(results);
    const errorRate = this.getErrorRate();
    const policyVios = spans.filter(s => s.attributes.policyDenied === true).length;
    const slowSpans = this.tracer.getSlowSpans(100).length;
    const topIssues = this.evaluator.topFailures(results, 3);
    // Emit alerts
    if (policyVios > 0) this.emitAlert('policy_violation', `${policyVios} policy violations detected`);
    if (errorRate > 0.1) this.emitAlert('high_error_rate', `Error rate ${(errorRate * 100).toFixed(1)}% exceeds 10%`);
    if (slowSpans > 0) this.emitAlert('slow_span', `${slowSpans} spans exceeded 100ms`);
    return { score, errorRate, policyViolations: policyVios, slowSpans, topIssues, markdown: this.reportMarkdown() };
  }

  constructor() {
    this.tracer = new Tracer();
    this.policyEngine = new PolicyEngine();
    this.evaluator = new Evaluator();
    this.evaluator.addCheck('policy_compliance', policyComplianceCheck, 1.5);
    this.evaluator.addCheck('latency', latencyCheck, 1.0);
    this.evaluator.addCheck('reliability', reliabilityCheck, 2.0);
    this.evaluator.addCheck('cost_efficiency', costEfficiencyCheck, 1.0);
  }

  startRun(agentId: string, task: string): Span {
    const span = this.tracer.startSpan('agent.run', { agentId, task });
    this.rootSpanId = span.spanId;
    return span;
  }

  llmCall(model: string, prompt: string, completion: string, tokenUsage?: { promptTokens: number; completionTokens: number }): Span {
    const span = this.tracer.startSpan('llm.call', {
      'gen_ai.request.model': model,
      'gen_ai.prompt': prompt,
      'gen_ai.completion': completion,
      promptTokens: tokenUsage?.promptTokens ?? 0,
      completionTokens: tokenUsage?.completionTokens ?? 0,
      totalTokens: (tokenUsage?.promptTokens ?? 0) + (tokenUsage?.completionTokens ?? 0),
    });
    this.tracer.endSpan(span.spanId);
    return span;
  }

  toolExecute(tool: string, input: string): { span: Span; allowed: boolean } {
    const policyResult = this.policyEngine.evaluate('tool_execution', { tool, command: input, input });
    const span = this.tracer.startSpan('tool.execute', {
      'tool.name': tool,
      'tool.input': input,
      policyDenied: !policyResult.allowed,
    });
    if (!policyResult.allowed) {
      span.status = 'error';
      span.attributes.policyViolations = policyResult.violations.map(v => v.reason);
    }
    this.tracer.endSpan(span.spanId, policyResult.allowed ? 'ok' : 'error');
    return { span, allowed: policyResult.allowed };
  }

  endRun(): Span | undefined {
    if (!this.rootSpanId) return undefined;
    const span = this.tracer.endSpan(this.rootSpanId);
    this.rootSpanId = null;
    return span;
  }

  memoryOperation(type: 'read' | 'write', attrs: Record<string, unknown>): Span {
    const span = this.tracer.startSpan(`memory.${type}`, attrs);
    this.tracer.endSpan(span.spanId);
    return span;
  }

  retrievalSearch(method: string, attrs: Record<string, unknown>): Span {
    const span = this.tracer.startSpan('retrieval.search', { method, ...attrs });
    this.tracer.endSpan(span.spanId);
    return span;
  }

  getReport(): ObservabilityReport {
    const spans = this.tracer.getSpans();
    const evalResults = this.evaluator.evaluate(spans);
    return {
      traceReport: this.tracer.getTraceReport(),
      evalResults,
      aggregateScore: this.evaluator.aggregateScore(evalResults),
    };
  }

  getTracer(): Tracer { return this.tracer; }
  getPolicyEngine(): PolicyEngine { return this.policyEngine; }
  getEvaluator(): Evaluator { return this.evaluator; }

  reportMarkdown(): string {
    const report = this.getReport();
    const lines: string[] = [];
    lines.push(`# Observability Report`);
    lines.push(``);
    lines.push(`**Trace:** ${report.traceReport.traceId.slice(0, 8)}...`);
    lines.push(`**Spans:** ${report.traceReport.totalSpans}`);
    lines.push(`**Errors:** ${report.traceReport.errorCount}`);
    lines.push(`**Duration:** ${report.traceReport.totalDurationMs.toFixed(1)}ms`);
    lines.push(`**Score:** ${(report.aggregateScore * 100).toFixed(0)}%`);
    lines.push(``);
    if (report.evalResults.length > 0) {
      lines.push(`## Evaluation`);
      for (const r of report.evalResults) {
        lines.push(`- **${r.dimension}:** ${(r.score * 100).toFixed(0)}% — ${r.reason}`);
      }
      lines.push(``);
    }
    if (report.traceReport.durationByOp) {
      lines.push(`## Duration by Operation`);
      for (const [op, dur] of Object.entries(report.traceReport.durationByOp)) {
        lines.push(`- ${op}: ${dur.toFixed(1)}ms`);
      }
    }
    return lines.join('\n');
  }

  spanStats(): { total: number; completed: number; errors: number; byOperation: Record<string, number> } {
    const spans = this.tracer.getSpans();
    const byOperation: Record<string, number> = {};
    for (const s of spans) {
      byOperation[s.operation] = (byOperation[s.operation] ?? 0) + 1;
    }
    return {
      total: spans.length,
      completed: spans.filter(s => s.endTime !== null).length,
      errors: spans.filter(s => s.status === 'error').length,
      byOperation,
    };
  }

  observeSync<T>(fn: () => T): { result: T; report: ObservabilityReport } {
    this.startRun('observer', 'observeSync');
    const result = fn();
    this.endRun();
    return { result, report: this.getReport() };
  }

  /** Observe with automatic policy-guarded tool execution */
  observeWithPolicy<T>(
    fn: (ctx: { tool: (name: string, input: string) => { allowed: boolean; reason?: string } }) => T,
    agentId = 'observer'
  ): { result: T; report: ObservabilityReport } {
    this.startRun(agentId, 'observeWithPolicy');
    const tool = (name: string, input: string) => {
      const { allowed, span } = this.toolExecute(name, input);
      return { allowed, reason: allowed ? undefined : String(span.attributes.policyViolations ?? 'denied') };
    };
    const result = fn({ tool });
    this.endRun();
    return { result, report: this.getReport() };
  }

  getErrorSummary(): Array<{ operation: string; reason: string }> {
    const spans = this.tracer.getSpans();
    const errors = spans.filter(s => s.status === 'error');
    return errors.map(s => ({
      operation: s.operation,
      reason: String(s.attributes.policyViolations ?? s.attributes.error ?? 'unknown'),
    }));
  }

  /** Get error rate as a ratio (0-1) */
  getErrorRate(): number {
    const spans = this.tracer.getSpans();
    if (spans.length === 0) return 0;
    return spans.filter(s => s.status === 'error').length / spans.length;
  }

  /** Observe an async function with tracing */
  async observeAsync<T>(fn: () => Promise<T>, agentId = 'observer'): Promise<{ result: T; report: ObservabilityReport }> {
    this.startRun(agentId, 'observeAsync');
    try {
      const result = await fn();
      this.endRun();
      return { result, report: this.getReport() };
    } catch (err) {
      this.endRun();
      throw err;
    }
  }

  /** Get the AgentObserver's root span ID */
  getRootSpanId(): string | null {
    return this.rootSpanId;
  }

  /** Quick health check: returns { healthy, errorRate, spanCount } */
  healthCheck(threshold = 0.1): { healthy: boolean; errorRate: number; spanCount: number } {
    const errorRate = this.getErrorRate();
    return { healthy: errorRate <= threshold, errorRate, spanCount: this.tracer.spanCount() };
  }

  /** Reset observer state for reuse */
  reset(): void {
    this.tracer.reset();
    this.rootSpanId = null;
  }

  /** Observe a synchronous operation with span tracking */
  runSync<T>(operation: string, fn: () => T): T {
    const span = this.tracer.startSpan(operation as any);
    try {
      const result = fn();
      this.tracer.endSpan(span.spanId, 'ok');
      return result;
    } catch (err) {
      this.tracer.endSpan(span.spanId, 'error');
      throw err;
    }
  }

  /** Quick span count accessor */
  getSpanCount(): number {
    return this.tracer.spanCount();
  }

  /** Check if policy category exists */
  hasPolicyCategory(category: string): boolean {
    return this.policyEngine.listCategories().includes(category);
  }

  /** Trace an entire agent run (start→fn→end) returning result + report */
  traceAgent<T>(agentId: string, task: string, fn: () => T): { result: T; report: ObservabilityReport } {
    this.startRun(agentId, task);
    try {
      const result = fn();
      this.endRun();
      return { result, report: this.getReport() };
    } catch (err) {
      this.endRun();
      throw err;
    }
  }
}

// OTel GenAI semantic-convention export adapter (pinned @ c739977) —
// mapSpan / exportGenAiOtlp / lintGenAiSpans / evaluationEventAttributes
export * from './otel-genai.js';
