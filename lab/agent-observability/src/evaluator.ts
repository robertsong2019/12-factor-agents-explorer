import type { Span } from './tracer.js';

export interface EvalCheckResult {
  dimension: string;
  score: number; // 0-1
  reason: string;
}

export type EvalCheck = (spans: Span[]) => EvalCheckResult[];

export class Evaluator {
  private checks: Array<{ name: string; fn: EvalCheck; weight: number }> = [];
  private weights: Map<string, number> = new Map();

  addCheck(name: string, fn: EvalCheck, weight = 1.0): void {
    this.checks.push({ name, fn, weight });
    this.weights.set(name, weight);
  }

  evaluate(spans: Span[], dimensions?: string[]): EvalCheckResult[] {
    const results: EvalCheckResult[] = [];
    for (const check of this.checks) {
      if (dimensions && !dimensions.includes(check.name)) continue;
      results.push(...check.fn(spans));
    }
    return results;
  }

  aggregateScore(results: EvalCheckResult[]): number {
    if (results.length === 0) return 0;
    let totalWeight = 0;
    let weightedSum = 0;
    for (const r of results) {
      const w = this.weights.get(r.dimension) ?? 1.0;
      weightedSum += r.score * w;
      totalWeight += w;
    }
    return totalWeight > 0 ? weightedSum / totalWeight : 0;
  }

  listChecks(): string[] {
    return this.checks.map(c => c.name);
  }

  removeCheck(name: string): boolean {
    const before = this.checks.length;
    this.checks = this.checks.filter(c => c.name !== name);
    this.weights.delete(name);
    return this.checks.length < before;
  }

  setWeight(name: string, weight: number): boolean {
    if (!this.weights.has(name)) return false;
    this.weights.set(name, weight);
    const check = this.checks.find(c => c.name === name);
    if (check) check.weight = weight;
    return true;
  }

  resetChecks(): void {
    this.checks = [];
    this.weights.clear();
  }

  getCheck(name: string): { name: string; fn: EvalCheck; weight: number } | undefined {
    return this.checks.find(c => c.name === name);
  }

  /** Return dimension names from all registered checks */
  dimensionNames(): string[] {
    return this.checks.map(c => c.name);
  }

  /** Return overall pass rate (fraction of results with score >= 0.5) */
  overallPassRate(results: EvalCheckResult[]): number {
    if (results.length === 0) return 1;
    return results.filter(r => r.score >= 0.5).length / results.length;
  }

  /** Return dimensions with lowest scores from a set of results */
  topFailures(results: EvalCheckResult[], limit = 3): EvalCheckResult[] {
    return [...results].sort((a, b) => a.score - b.score).slice(0, limit);
  }

  /** Run each check separately and return per-check results */
  evaluateEach(spans: Span[]): Array<{ check: string; results: EvalCheckResult[] }> {
    return this.checks.map(c => ({ check: c.name, results: c.fn(spans) }));
  }

  /** Count how many results pass (score >= 0.5) */
  passCount(results: EvalCheckResult[]): number {
    return results.filter(r => r.score >= 0.5).length;
  }

  /** Get all configured weights */
  getWeights(): Map<string, number> {
    return new Map(this.weights);
  }

  /** Aggregate summary: total/pass/fail/avg/min/max by dimension */
  summary(results: EvalCheckResult[]): {
    total: number; passed: number; failed: number;
    avgScore: number; dimensions: number;
  } {
    const passed = results.filter(r => r.score >= 0.5).length;
    const avgScore = results.length > 0
      ? Math.round(results.reduce((s, r) => s + r.score, 0) / results.length * 100) / 100
      : 0;
    const dims = new Set(results.map(r => r.dimension));
    return { total: results.length, passed, failed: results.length - passed, avgScore, dimensions: dims.size };
  }

  /** Filter results by dimension name */
  byDimension(results: EvalCheckResult[], dimension: string): EvalCheckResult[] {
    return results.filter(r => r.dimension === dimension);
  }

  /** Generate human-readable markdown report */
  toMarkdown(results: EvalCheckResult[]): string {
    const s = this.summary(results);
    const lines: string[] = [
      `# Evaluation Report`,
      ``,
      `**Total**: ${s.total} | **Passed**: ${s.passed} | **Failed**: ${s.failed} | **Avg Score**: ${s.avgScore}`,
      ``,
      `| Dimension | Score | Status | Reason |`,
      `|-----------|-------|--------|--------|`,
    ];
    for (const r of results) {
      const status = r.score >= 0.5 ? '✅' : '❌';
      lines.push(`| ${r.dimension} | ${r.score.toFixed(2)} | ${status} | ${r.reason} |`);
    }
    return lines.join('\n');
  }

  /** Compare two sets of spans and return regression info */
  runComparison(baselineSpans: Span[], currentSpans: Span[], threshold = -0.1): TraceComparison[] {
    return compareTraces(baselineSpans, currentSpans, this.checks.map(c => c.fn), threshold);
  }
  /** Convenience: add all built-in checks (policy_compliance, latency, reliability, cost_efficiency) */
  addBuiltinChecks(): void {
    this.addCheck('policy_compliance', policyComplianceCheck, 1.0);
    this.addCheck('latency', latencyCheck, 1.0);
    this.addCheck('reliability', reliabilityCheck, 1.0);
    this.addCheck('cost_efficiency', costEfficiencyCheck, 1.0);
  }

  /** Add a single built-in check by name */
  addBuiltinCheck(name: string): boolean {
    const map: Record<string, EvalCheck> = {
      policy_compliance: policyComplianceCheck,
      latency: latencyCheck,
      reliability: reliabilityCheck,
      cost_efficiency: costEfficiencyCheck,
    };
    const fn = map[name];
    if (!fn) return false;
    this.addCheck(name, fn, 1.0);
    return true;
  }

  /** Check if a check with given name exists */
  hasCheck(name: string): boolean {
    return this.checks.some(c => c.name === name);
  }

  /** Get number of registered checks */
  getCheckCount(): number {
    return this.checks.length;
  }

  /** Evaluate with a score threshold: returns pass/fail + results */
  evaluateWithThreshold(spans: Span[], threshold = 0.5): { pass: boolean; score: number; results: EvalCheckResult[] } {
    const results = this.evaluate(spans);
    const score = this.aggregateScore(results);
    return { pass: score >= threshold, score, results };
  }

  /** Evaluate spans and return results + aggregate score + markdown report in one call */
  evaluateAndReport(spans: Span[], dimensions?: string[]): {
    results: EvalCheckResult[];
    score: number;
    report: string;
  } {
    const results = this.evaluate(spans, dimensions);
    const score = this.aggregateScore(results);
    const report = this.toMarkdown(results);
    return { results, score, report };
  }
}

// --- Built-in checks ---

export function policyComplianceCheck(spans: Span[]): EvalCheckResult[] {
  const toolSpans = spans.filter(s => s.operation === 'tool.execute');
  const blocked = toolSpans.filter(s => s.status === 'error' && s.attributes.policyDenied === true);
  const ratio = toolSpans.length > 0 ? 1 - blocked.length / toolSpans.length : 1;
  return [{
    dimension: 'policy_compliance',
    score: ratio,
    reason: `${blocked.length}/${toolSpans.length} tool calls blocked by policy`,
  }];
}

export function latencyCheck(spans: Span[]): EvalCheckResult[] {
  const completed = spans.filter(s => s.endTime !== null);
  if (completed.length === 0) return [{ dimension: 'latency', score: 1, reason: 'No completed spans' }];
  const durations = completed.map(s => s.endTime! - s.startTime);
  const avg = durations.reduce((a, b) => a + b, 0) / durations.length;
  // Score 1 if avg < 100ms, degrade to 0 at 5000ms
  const score = Math.max(0, Math.min(1, 1 - (avg - 100) / 4900));
  return [{
    dimension: 'latency',
    score: Math.round(score * 100) / 100,
    reason: `Avg span duration: ${avg.toFixed(1)}ms`,
  }];
}

export function reliabilityCheck(spans: Span[]): EvalCheckResult[] {
  if (spans.length === 0) return [{ dimension: 'reliability', score: 1, reason: 'No spans' }];
  const errors = spans.filter(s => s.status === 'error').length;
  const score = 1 - errors / spans.length;
  return [{
    dimension: 'reliability',
    score: Math.round(score * 100) / 100,
    reason: `${errors}/${spans.length} spans errored`,
  }];
}

export interface TraceComparison {
  dimension: string;
  baseline: number;
  current: number;
  delta: number;
  regression: boolean;
}

export function compareTraces(
  baselineSpans: Span[],
  currentSpans: Span[],
  checks: EvalCheck[] = [policyComplianceCheck, latencyCheck, reliabilityCheck, costEfficiencyCheck],
  threshold = -0.1
): TraceComparison[] {
  const results: TraceComparison[] = [];
  for (const check of checks) {
    const bResults = check(baselineSpans);
    const cResults = check(currentSpans);
    // Match by dimension
    for (const br of bResults) {
      const cr = cResults.find(c => c.dimension === br.dimension);
      const cv = cr?.score ?? 0;
      const delta = cv - br.score;
      results.push({
        dimension: br.dimension,
        baseline: br.score,
        current: cv,
        delta: Math.round(delta * 1000) / 1000,
        regression: delta < threshold,
      });
    }
  }
  return results;
}

export function costEfficiencyCheck(spans: Span[]): EvalCheckResult[] {
  const llmSpans = spans.filter(s => s.operation === 'llm.call');
  if (llmSpans.length === 0) return [{ dimension: 'cost_efficiency', score: 1, reason: 'No LLM calls' }];
  const totalTokens = llmSpans.reduce((sum, s) => sum + Number(s.attributes.totalTokens ?? 0), 0);
  // Score 1 if < 1000 tokens, degrade to 0 at 100k
  const score = Math.max(0, Math.min(1, 1 - (totalTokens - 1000) / 99000));
  return [{
    dimension: 'cost_efficiency',
    score: Math.round(score * 100) / 100,
    reason: `Total tokens: ${totalTokens}`,
  }];
}

/** Track evaluation scores over multiple runs and detect trends */
export class TrendTracker {
  private history: Array<{ run: number; timestamp: number; results: EvalCheckResult[]; score: number }> = [];
  private runCounter = 0;

  /** Record a new evaluation run */
  record(results: EvalCheckResult[], aggregateScore: number): number {
    const run = ++this.runCounter;
    this.history.push({ run, timestamp: Date.now(), results, score: aggregateScore });
    return run;
  }

  /** Get trend for a specific dimension: returns array of scores over runs */
  dimensionTrend(dimension: string): Array<{ run: number; score: number }> {
    return this.history.map(h => {
      const match = h.results.find(r => r.dimension === dimension);
      return { run: h.run, score: match?.score ?? 0 };
    });
  }

  /** Detect if aggregate score is trending down over last N runs (potential regression) */
  isRegressing(windowSize = 3): boolean {
    if (this.history.length < windowSize) return false;
    const recent = this.history.slice(-windowSize);
    const first = recent[0].score;
    const last = recent[recent.length - 1].score;
    return last < first;
  }

  /** Get run count */
  get runCount(): number {
    return this.history.length;
  }

  /** Get aggregate scores for all runs */
  get scoreHistory(): Array<{ run: number; score: number }> {
    return this.history.map(h => ({ run: h.run, score: h.score }));
  }

  /** Reset all history */
  reset(): void {
    this.history = [];
    this.runCounter = 0;
  }
}
