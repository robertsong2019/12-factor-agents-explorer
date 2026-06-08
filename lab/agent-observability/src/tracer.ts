import { randomUUID } from 'node:crypto';

export type SpanStatus = 'ok' | 'error' | 'unset';
export type SpanOperation =
  | 'agent.run' | 'llm.call' | 'tool.execute'
  | 'retrieval.search' | 'memory.read' | 'memory.write';

export interface SpanEvent {
  name: string;
  timestamp: number;
  attributes?: Record<string, unknown>;
}

export interface Span {
  traceId: string;
  spanId: string;
  parentSpanId: string | null;
  operation: SpanOperation;
  startTime: number;
  endTime: number | null;
  attributes: Record<string, unknown>;
  status: SpanStatus;
  events: SpanEvent[];
}

export interface SpanTreeNode extends Span {
  children: SpanTreeNode[];
}

export interface TraceReport {
  traceId: string;
  spans: Span[];
  totalSpans: number;
  durationByOp: Record<string, number>;
  errorCount: number;
  totalDurationMs: number;
}

export class Tracer {
  private spans: Span[] = [];
  private activeStack: string[] = []; // stack of spanIds
  private traceId: string;

  constructor() {
    this.traceId = randomUUID();
  }

  startSpan(operation: SpanOperation, attributes?: Record<string, unknown>): Span {
    const parentSpanId = this.activeStack.length > 0 ? this.activeStack[this.activeStack.length - 1] : null;
    const span: Span = {
      traceId: this.traceId,
      spanId: randomUUID(),
      parentSpanId,
      operation,
      startTime: performance.now(),
      endTime: null,
      attributes: { ...attributes },
      status: 'unset',
      events: [],
    };
    this.spans.push(span);
    this.activeStack.push(span.spanId);
    return span;
  }

  endSpan(spanId: string, status: SpanStatus = 'ok'): Span | undefined {
    const span = this.spans.find(s => s.spanId === spanId);
    if (!span || span.endTime !== null) return undefined;
    span.endTime = performance.now();
    span.status = status;
    this.activeStack = this.activeStack.filter(id => id !== spanId);
    return span;
  }

  addEvent(spanId: string, name: string, attributes?: Record<string, unknown>): void {
    const span = this.spans.find(s => s.spanId === spanId);
    if (span) {
      span.events.push({ name, timestamp: Date.now(), attributes });
    }
  }

  getActiveSpan(): Span | undefined {
    if (this.activeStack.length === 0) return undefined;
    const id = this.activeStack[this.activeStack.length - 1];
    return this.spans.find(s => s.spanId === id);
  }

  getSpans(): Span[] {
    return [...this.spans];
  }

  getTraceReport(): TraceReport {
    const durationByOp: Record<string, number> = {};
    let errorCount = 0;
    for (const span of this.spans) {
      const dur = span.endTime !== null ? span.endTime - span.startTime : 0;
      durationByOp[span.operation] = (durationByOp[span.operation] ?? 0) + dur;
      if (span.status === 'error') errorCount++;
    }
    const root = this.spans.find(s => s.parentSpanId === null);
    const totalDurationMs = root?.endTime !== null && root?.endTime !== undefined
      ? root.endTime - root.startTime : 0;
    return {
      traceId: this.traceId,
      spans: this.spans,
      totalSpans: this.spans.length,
      durationByOp,
      errorCount,
      totalDurationMs,
    };
  }

  exportJSON(): string {
    return JSON.stringify({ traceId: this.traceId, spans: this.spans }, null, 2);
  }

  importJSON(json: string): void {
    const data = JSON.parse(json);
    if (data.traceId) this.traceId = data.traceId;
    if (Array.isArray(data.spans)) this.spans = data.spans;
  }

  findSpans(predicate: (span: Span) => boolean): Span[] {
    return this.spans.filter(predicate);
  }

  findSpansByOperation(op: SpanOperation): Span[] {
    return this.spans.filter(s => s.operation === op);
  }

  getSpanById(spanId: string): Span | undefined {
    return this.spans.find(s => s.spanId === spanId);
  }

  spanCount(): number {
    return this.spans.length;
  }

  reset(): void {
    this.spans = [];
    this.activeStack = [];
    this.traceId = randomUUID();
  }

  getChildren(spanId: string): Span[] {
    return this.spans.filter(s => s.parentSpanId === spanId);
  }

  getSpanTree(spanId?: string): SpanTreeNode[] {
    const roots = spanId
      ? this.spans.filter(s => s.spanId === spanId)
      : this.spans.filter(s => s.parentSpanId === null);
    const build = (span: Span): SpanTreeNode => {
      const kids = this.getChildren(span.spanId).map(build);
      return { ...span, children: kids };
    };
    return roots.map(build);
  }

  // --- Causal links ---

  private causalLinks: Array<{ from: string; to: string; type: string }> = [];

  linkSpans(fromSpanId: string, toSpanId: string, type: string = 'causal'): boolean {
    const from = this.spans.find(s => s.spanId === fromSpanId);
    const to = this.spans.find(s => s.spanId === toSpanId);
    if (!from || !to) return false;
    this.causalLinks.push({ from: fromSpanId, to: toSpanId, type });
    return true;
  }

  getCausalChain(spanId: string, direction: 'upstream' | 'downstream' = 'upstream'): Span[] {
    const visited = new Set<string>();
    const result: Span[] = [];
    const queue = [spanId];
    while (queue.length > 0) {
      const current = queue.shift()!;
      if (visited.has(current)) continue;
      visited.add(current);
      const links = direction === 'upstream'
        ? this.causalLinks.filter(l => l.to === current)
        : this.causalLinks.filter(l => l.from === current);
      for (const link of links) {
        const nextId = direction === 'upstream' ? link.from : link.to;
        const span = this.spans.find(s => s.spanId === nextId);
        if (span && !visited.has(nextId)) {
          result.push(span);
          queue.push(nextId);
        }
      }
    }
    return result;
  }

  getCausalLinks(): Array<{ from: string; to: string; type: string }> {
    return [...this.causalLinks];
  }

  getActiveSpanCount(): number {
    return this.activeStack.length;
  }

  getSpanDepth(spanId: string): number {
    let depth = 0;
    let current = this.spans.find(s => s.spanId === spanId);
    while (current?.parentSpanId) {
      depth++;
      current = this.spans.find(s => s.spanId === current!.parentSpanId);
    }
    return depth;
  }

  /** Export spans in OTLP JSON format (compatible with OTel Collector) */
  exportOTLP(): Record<string, unknown> {
    return {
      resourceSpans: [{
        scopeSpans: [{
          scope: { name: 'agent-observability', version: '1.0.0' },
          spans: this.spans.map(s => ({
            traceId: s.traceId,
            spanId: s.spanId,
            parentSpanId: s.parentSpanId ?? undefined,
            name: s.operation,
            kind: 1, // INTERNAL
            startTimeUnixNano: Math.round(s.startTime * 1e6),
            endTimeUnixNano: s.endTime !== null ? Math.round(s.endTime * 1e6) : undefined,
            status: { code: s.status === 'error' ? 2 : s.status === 'ok' ? 1 : 0 },
            attributes: Object.entries(s.attributes).map(([k, v]) => ({ key: k, value: { stringValue: String(v) } })),
            events: s.events.map(e => ({
              timeUnixNano: e.timestamp * 1e6,
              name: e.name,
              attributes: Object.entries(e.attributes ?? {}).map(([k, v]) => ({ key: k, value: { stringValue: String(v) } })),
            })),
          })),
        }],
      }],
    };
  }

  /** Return spans with duration >= thresholdMs */
  getSlowSpans(thresholdMs: number): Span[] {
    return this.spans.filter(s => s.endTime !== null && (s.endTime - s.startTime) >= thresholdMs);
  }

  /** Return all spans with status='error' */
  getErrorSpans(): Span[] {
    return this.spans.filter(s => s.status === 'error');
  }

  /** Filter spans by a predicate */
  filter(predicate: (span: Span) => boolean): Span[] {
    return this.spans.filter(predicate);
  }

  /** Group spans by operation name */
  groupByOperation(): Record<string, Span[]> {
    const groups: Record<string, Span[]> = {};
    for (const s of this.spans) {
      (groups[s.operation] ??= []).push(s);
    }
    return groups;
  }

  /** Clear all spans and reset trace */
  clear(): void {
    const newTraceId = randomUUID();
    this.spans = [];
    this.traceId = newTraceId;
  }

  /** Get duration of a completed span in ms, or null if still active */
  getSpanDuration(spanId: string): number | null {
    const span = this.spans.find(s => s.spanId === spanId);
    if (!span || span.endTime === null) return null;
    return span.endTime - span.startTime;
  }

  /** Convenience: run fn inside a span, auto-end, return result */
  traceFn<T>(operation: SpanOperation, fn: () => T, attributes?: Record<string, unknown>): { result: T; span: Span } {
    const span = this.startSpan(operation, attributes);
    try {
      const result = fn();
      this.endSpan(span.spanId, 'ok');
      return { result, span };
    } catch (err) {
      this.endSpan(span.spanId, 'error');
      throw err;
    }
  }

  /** Async version of traceFn */
  async traceAsync<T>(operation: SpanOperation, fn: () => Promise<T>, attributes?: Record<string, unknown>): Promise<{ result: T; span: Span }> {
    const span = this.startSpan(operation, attributes);
    try {
      const result = await fn();
      this.endSpan(span.spanId, 'ok');
      return { result, span };
    } catch (err) {
      this.endSpan(span.spanId, 'error');
      throw err;
    }
  }

  /** Get total duration of all completed spans */
  totalDuration(): number {
    return this.spans.reduce((sum, s) => {
      if (s.endTime === null) return sum;
      return sum + (s.endTime - s.startTime);
    }, 0);
  }

  /** Get duration at a given percentile (0-100) among completed spans */
  getPercentile(p: number): number {
    const durs = this.spans
      .filter(s => s.endTime !== null)
      .map(s => s.endTime! - s.startTime)
      .sort((a, b) => a - b);
    if (durs.length === 0) return 0;
    const idx = Math.min(Math.floor(p / 100 * durs.length), durs.length - 1);
    return durs[idx];
  }

  /** Count spans by status */
  spanCountByStatus(): Record<SpanStatus, number> {
    const counts: Record<SpanStatus, number> = { ok: 0, error: 0, unset: 0 };
    for (const s of this.spans) counts[s.status]++;
    return counts;
  }

  /** Add or update a single attribute on a span */
  addAttribute(spanId: string, key: string, value: unknown): boolean {
    const span = this.spans.find(s => s.spanId === spanId);
    if (!span) return false;
    span.attributes[key] = value;
    return true;
  }

  /** Check if a span exists */
  hasSpan(spanId: string): boolean {
    return this.spans.some(s => s.spanId === spanId);
  }

  /** Bulk annotate: add multiple key-value pairs to a span */
  annotate(spanId: string, attrs: Record<string, unknown>): boolean {
    const span = this.spans.find(s => s.spanId === spanId);
    if (!span) return false;
    Object.assign(span.attributes, attrs);
    return true;
  }

  /** One-call summary stats */
  getStats(): { total: number; active: number; completed: number; errors: number; avgDurationMs: number } {
    const completed = this.spans.filter(s => s.endTime !== null);
    const totalDur = completed.reduce((sum, s) => sum + (s.endTime! - s.startTime), 0);
    return {
      total: this.spans.length,
      active: this.spans.filter(s => s.endTime === null).length,
      completed: completed.length,
      errors: this.spans.filter(s => s.status === 'error').length,
      avgDurationMs: completed.length > 0 ? totalDur / completed.length : 0,
    };
  }

  /** Change the operation name of an existing span. Returns false if not found. */
  renameSpan(spanId: string, newOperation: SpanOperation): boolean {
    const span = this.spans.find(s => s.spanId === spanId);
    if (!span) return false;
    span.operation = newOperation;
    return true;
  }

  /** Deep clone a span with a new spanId (no parent link). Returns undefined if not found. */
  cloneSpan(spanId: string): Span | undefined {
    const span = this.spans.find(s => s.spanId === spanId);
    if (!span) return undefined;
    const clone: Span = {
      traceId: this.traceId,
      spanId: randomUUID(),
      parentSpanId: null,
      operation: span.operation,
      startTime: span.startTime,
      endTime: span.endTime,
      attributes: { ...span.attributes },
      status: span.status,
      events: [...span.events],
    };
    this.spans.push(clone);
    return clone;
  }

  /** Merge all spans from another Tracer into this one. Returns count of merged spans. */
  mergeTracer(other: Tracer): number {
    const otherSpans = other.getSpans();
    for (const s of otherSpans) {
      this.spans.push(s);
    }
    return otherSpans.length;
  }

  /** End multiple spans at once. Returns count of spans successfully ended. */
  batchEnd(spanIds: string[], status: SpanStatus = 'ok'): number {
    let count = 0;
    for (const id of spanIds) {
      if (this.endSpan(id, status)) count++;
    }
    return count;
  }

  /** Return a map of spanId → depth (number of ancestors) */
  getDepthMap(): Map<string, number> {
    const map = new Map<string, number>();
    for (const s of this.spans) {
      map.set(s.spanId, this.getSpanDepth(s.spanId));
    }
    return map;
  }

  // --- Tag system ---

  private tags: Map<string, Set<string>> = new Map(); // tag -> Set<spanId>

  /** Tag a span with one or more labels. Returns count of spans successfully tagged. */
  tagSpan(spanId: string, ...labels: string[]): boolean {
    if (!this.spans.some(s => s.spanId === spanId)) return false;
    for (const label of labels) {
      const set = this.tags.get(label) ?? new Set();
      set.add(spanId);
      this.tags.set(label, set);
    }
    return true;
  }

  /** Remove a tag from a span. Returns true if tag was present. */
  untagSpan(spanId: string, label: string): boolean {
    const set = this.tags.get(label);
    if (!set) return false;
    const had = set.delete(spanId);
    if (set.size === 0) this.tags.delete(label);
    return had;
  }

  /** Get all spans matching a tag. */
  getSpansByTag(label: string): Span[] {
    const set = this.tags.get(label);
    if (!set) return [];
    return this.spans.filter(s => set.has(s.spanId));
  }

  /** Get all tags for a specific span. */
  getTagsForSpan(spanId: string): string[] {
    const result: string[] = [];
    for (const [label, set] of this.tags) {
      if (set.has(spanId)) result.push(label);
    }
    return result;
  }

  /** Get all tags with their span counts. */
  getAllTags(): Map<string, number> {
    const result = new Map<string, number>();
    for (const [label, set] of this.tags) result.set(label, set.size);
    return result;
  }

  /** Search spans by matching attribute values (case-insensitive substring). */
  searchAttributes(query: string): Span[] {
    const lower = query.toLowerCase();
    return this.spans.filter(s =>
      Object.values(s.attributes).some(v => String(v).toLowerCase().includes(lower))
    );
  }

  /** Get the full ancestor chain from root to the given span (inclusive). */
  getSpanLineage(spanId: string): Span[] {
    const chain: Span[] = [];
    let current = this.spans.find(s => s.spanId === spanId);
    while (current) {
      chain.unshift(current);
      current = current.parentSpanId
        ? this.spans.find(s => s.spanId === current!.parentSpanId)
        : undefined;
    }
    return chain;
  }

  /** Walk upstream causal chain to find the root cause error (closest to source). */
  findRootCause(spanId: string): Span | undefined {
    const upstream = this.getCausalChain(spanId, 'upstream');
    const errors = upstream.filter(s => s.status === 'error');
    if (errors.length === 0) {
      const span = this.getSpanById(spanId);
      return span?.status === 'error' ? span : undefined;
    }
    // Return the last error in upstream order (= deepest/furthest from span = root cause)
    return errors[errors.length - 1];
  }

  /** Aggregate stats of children of a span. */
  getChildSummary(spanId: string): { count: number; errors: number; totalDurationMs: number; avgDurationMs: number } {
    const children = this.getChildren(spanId);
    const completed = children.filter(s => s.endTime !== null);
    const totalDur = completed.reduce((sum, s) => sum + (s.endTime! - s.startTime), 0);
    return {
      count: children.length,
      errors: children.filter(s => s.status === 'error').length,
      totalDurationMs: totalDur,
      avgDurationMs: completed.length > 0 ? totalDur / completed.length : 0,
    };
  }

  /** Find the critical path: longest-duration path from root to any leaf. */
  getCriticalPath(): Span[] {
    if (this.spans.length === 0) return [];
    const trees = this.getSpanTree();
    let longestPath: Span[] = [];
    let longestDur = 0;
    const walk = (node: SpanTreeNode, path: Span[]): void => {
      const currentPath = [...path, node];
      const dur = node.endTime !== null ? node.endTime - node.startTime : 0;
      if (node.children.length === 0) {
        const pathDur = currentPath.reduce((sum, s) => sum + (s.endTime !== null ? s.endTime - s.startTime : 0), 0);
        if (pathDur > longestDur) {
          longestDur = pathDur;
          longestPath = currentPath;
        }
      } else {
        for (const child of node.children) walk(child, currentPath);
      }
    };
    for (const root of trees) walk(root, []);
    return longestPath;
  }

  /** Return spans sorted by startTime as a timeline */
  getOperationTimeline(): Array<{ spanId: string; operation: string; startMs: number; durationMs: number | null; status: SpanStatus }> {
    return [...this.spans]
      .sort((a, b) => a.startTime - b.startTime)
      .map(s => ({
        spanId: s.spanId,
        operation: s.operation,
        startMs: s.startTime,
        durationMs: s.endTime !== null ? s.endTime - s.startTime : null,
        status: s.status,
      }));
  }
}
