export interface PolicyRule {
  name: string;
  description: string;
  category: string;
  evaluate: (input: Record<string, unknown>) => { allow: boolean; reason?: string };
}

export interface EvalResult {
  allowed: boolean;
  violations: Array<{ rule: string; reason: string }>;
}

export class PolicyEngine {
  private rules: Map<string, PolicyRule[]> = new Map();

  addPolicy(category: string, rule: PolicyRule): void {
    const list = this.rules.get(category) ?? [];
    list.push(rule);
    this.rules.set(category, list);
  }

  removePolicy(category: string, ruleName: string): boolean {
    const list = this.rules.get(category);
    if (!list) return false;
    const before = list.length;
    const filtered = list.filter(r => r.name !== ruleName);
    this.rules.set(category, filtered);
    return filtered.length < before;
  }

  evaluate(category: string, input: Record<string, unknown>): EvalResult {
    const rules = this.rules.get(category) ?? [];
    const violations: Array<{ rule: string; reason: string }> = [];
    for (const rule of rules) {
      if (!this.isRuleEnabled(category, rule.name)) continue;
      const result = rule.evaluate(input);
      if (!result.allow) {
        violations.push({ rule: rule.name, reason: result.reason ?? 'Denied by policy' });
      }
    }
    return { allowed: violations.length === 0, violations };
  }

  loadFromJSON(data: Array<{ name: string; description: string; category: string; type: string; config?: Record<string, unknown> }>): void {
    this._jsonDefs = data;
    for (const def of data) {
      const rule = this.buildRule(def);
      if (rule) this.addPolicy(def.category, rule);
    }
  }

  private _jsonDefs: Array<{ name: string; description: string; category: string; type: string; config?: Record<string, unknown> }> = [];

  listCategories(): string[] {
    return [...this.rules.keys()];
  }

  ruleCount(category: string): number {
    return this.rules.get(category)?.length ?? 0;
  }

  exportJSON(): Array<{ name: string; description: string; category: string; type: string; config?: Record<string, unknown> }> {
    return [...this._jsonDefs];
  }

  private disabledRules: Set<string> = new Set();

  enableRule(category: string, ruleName: string): void {
    this.disabledRules.delete(`${category}::${ruleName}`);
  }

  disableRule(category: string, ruleName: string): void {
    this.disabledRules.add(`${category}::${ruleName}`);
  }

  isRuleEnabled(category: string, ruleName: string): boolean {
    return !this.disabledRules.has(`${category}::${ruleName}`);
  }

  evaluateAll(input: Record<string, unknown>): Record<string, EvalResult> {
    const results: Record<string, EvalResult> = {};
    for (const category of this.rules.keys()) {
      results[category] = this.evaluate(category, input);
    }
    return results;
  }

  /** Return all rule names across all categories */
  ruleNames(): string[] {
    const names: string[] = [];
    for (const rules of this.rules.values()) {
      for (const r of rules) {
        names.push(r.name);
      }
    }
    return names;
  }

  addPolicies(category: string, rules: PolicyRule[]): void {
    const list = this.rules.get(category) ?? [];
    list.push(...rules);
    this.rules.set(category, list);
  }

  batchEvaluate(inputs: Record<string, Record<string, unknown>>): Record<string, EvalResult> {
    const results: Record<string, EvalResult> = {};
    for (const [category, input] of Object.entries(inputs)) {
      results[category] = this.evaluate(category, input);
    }
    return results;
  }

  getRule(category: string, ruleName: string): PolicyRule | undefined {
    return this.rules.get(category)?.find(r => r.name === ruleName);
  }

  hasCategory(category: string): boolean {
    return this.rules.has(category) && (this.rules.get(category)?.length ?? 0) > 0;
  }

  /** Total rule count across all categories */
  countAll(): number {
    let total = 0;
    for (const rules of this.rules.values()) total += rules.length;
    return total;
  }

  /** Import rules from JSON array, replacing existing rules */
  importRules(data: Array<{ name: string; description: string; category: string; type: string; config?: Record<string, unknown> }>): number {
    this.rules.clear();
    this.disabledRules.clear();
    this._jsonDefs = [];
    let count = 0;
    for (const def of data) {
      const rule = this.buildRule(def);
      if (rule) {
        this.addPolicy(def.category, rule);
        this._jsonDefs.push(def);
        count++;
      }
    }
    return count;
  }

  /** Return all rules for a given category */
  getRulesByCategory(category: string): PolicyRule[] {
    return [...(this.rules.get(category) ?? [])];
  }

  /** Serialize all rules to JSON */
  toJSON(): object {
    const data: Record<string, Array<{ name: string; description: string; enabled: boolean }>> = {};
    for (const [cat, rules] of this.rules) {
      data[cat] = rules.map(r => ({
        name: r.name,
        description: r.description,
        enabled: this.isRuleEnabled(cat, r.name),
      }));
    }
    return data;
  }

  /** Import rules from toJSON output (note: evaluate fns are lost, only metadata) */
  static fromJSON(data: Record<string, Array<{ name: string; description: string }>>): PolicyEngine {
    const engine = new PolicyEngine();
    for (const [cat, rules] of Object.entries(data)) {
      for (const r of rules) {
        engine.addPolicy(cat, {
          name: r.name,
          description: r.description,
          category: cat,
          evaluate: () => ({ allow: true }),
        });
      }
    }
    return engine;
  }

  private buildRule(def: { name: string; description: string; category: string; type: string; config?: Record<string, unknown> }): PolicyRule | null {
    const helpers: Record<string, (cfg: Record<string, unknown>) => PolicyRule> = {
      blockDestructiveOps: blockDestructiveOps,
      costLimit: costLimit,
      rateLimit: rateLimit,
      piiFilter: piiFilter,
    };
    const builder = helpers[def.type];
    return builder ? builder(def.config ?? {}) : null;
  }

  /** Remove an entire category of rules */
  removeCategory(category: string): boolean {
    return this.rules.delete(category);
  }

  /** Rename a category */
  renameCategory(oldName: string, newName: string): boolean {
    const rules = this.rules.get(oldName);
    if (!rules) return false;
    this.rules.set(newName, rules);
    this.rules.delete(oldName);
    return true;
  }

  /** Count enabled rules across all categories */
  enabledCount(): number {
    let total = 0;
    for (const rules of this.rules.values()) total += rules.length;
    return total - this.disabledRules.size;
  }

  /** Merge another PolicyEngine's rules into this one (additive) */
  merge(other: PolicyEngine): number {
    let added = 0;
    for (const [cat, rules] of other.rules) {
      for (const rule of rules) {
        const existing = this.rules.get(cat) ?? [];
        if (!existing.some(r => r.name === rule.name)) {
          existing.push(rule);
          this.rules.set(cat, existing);
          added++;
        }
      }
    }
    return added;
  }

  /** Evaluate with per-rule detail */
  evaluateWithDetails(category: string, input: Record<string, unknown>): {
    allowed: boolean;
    details: Array<{ rule: string; allowed: boolean; reason?: string }>;
  } {
    const rules = this.rules.get(category) ?? [];
    const details: Array<{ rule: string; allowed: boolean; reason?: string }> = [];
    for (const rule of rules) {
      if (!this.isRuleEnabled(category, rule.name)) {
        details.push({ rule: rule.name, allowed: true, reason: 'disabled' });
        continue;
      }
      const result = rule.evaluate(input);
      details.push({ rule: rule.name, allowed: result.allow, reason: result.reason });
    }
    return { allowed: details.every(d => d.allowed), details };
  }

  /** Evaluate a batch of inputs against one category */
  evaluateBatch(category: string, inputs: Record<string, unknown>[]): EvalResult[] {
    return inputs.map(input => this.evaluate(category, input));
  }

  /** Get all categories with rule counts */
  getCategories(): Array<{ category: string; ruleCount: number }> {
    return this.listCategories().map(c => ({ category: c, ruleCount: this.ruleCount(c) }));
  }

  /** Count rules per category */
  countByCategory(): Record<string, number> {
    const result: Record<string, number> = {};
    for (const [cat, rules] of this.rules) {
      result[cat] = rules.length;
    }
    return result;
  }

  /** Diff two PolicyEngines: returns added/removed/modified rule names */
  static diff(base: PolicyEngine, other: PolicyEngine): {
    added: Array<{ category: string; rule: string }>;
    removed: Array<{ category: string; rule: string }>;
    unchanged: number;
  } {
    const baseEntries = new Map<string, Set<string>>();
    for (const [cat, rules] of base.rules) {
      baseEntries.set(cat, new Set(rules.map(r => r.name)));
    }
    const added: Array<{ category: string; rule: string }> = [];
    const removed: Array<{ category: string; rule: string }> = [];
    let unchanged = 0;
    // Find added
    for (const [cat, rules] of other.rules) {
      const baseSet = baseEntries.get(cat) ?? new Set();
      for (const r of rules) {
        if (baseSet.has(r.name)) unchanged++;
        else added.push({ category: cat, rule: r.name });
      }
    }
    // Find removed
    const otherEntries = new Map<string, Set<string>>();
    for (const [cat, rules] of other.rules) {
      otherEntries.set(cat, new Set(rules.map(r => r.name)));
    }
    for (const [cat, rules] of base.rules) {
      const otherSet = otherEntries.get(cat) ?? new Set();
      for (const r of rules) {
        if (!otherSet.has(r.name)) removed.push({ category: cat, rule: r.name });
      }
    }
    return { added, removed, unchanged };
  }

  /** Snapshot current state (disabled rules + loaded JSON defs) for later restore */
  snapshot(): { disabledRules: string[]; jsonDefs: object[] } {
    return {
      disabledRules: [...this.disabledRules],
      jsonDefs: [...this._jsonDefs],
    };
  }

  /** Restore from a previous snapshot */
  restore(snap: { disabledRules: string[]; jsonDefs: object[] }): void {
    // Re-import JSON defs (rebuilds rules)
    this.rules.clear();
    this.disabledRules.clear();
    this._jsonDefs = [];
    for (const def of snap.jsonDefs as Array<{ name: string; description: string; category: string; type: string; config?: Record<string, unknown> }>) {
      const rule = this.buildRule(def);
      if (rule) {
        this.addPolicy(def.category, rule);
        this._jsonDefs.push(def);
      }
    }
    for (const key of snap.disabledRules) {
      this.disabledRules.add(key);
    }
  }
}

// --- Built-in rule helpers ---

const DESTRUCTIVE_PATTERNS = ['rm ', 'drop ', 'delete ', 'truncate ', 'DROP ', 'DELETE ', 'TRUNCATE '];

export function blockDestructiveOps(_cfg: Record<string, unknown> = {}): PolicyRule {
  return {
    name: 'block_destructive_ops',
    description: 'Blocks commands that look destructive',
    category: 'tool_execution',
    evaluate: (input) => {
      const cmd = String(input.command ?? input.input ?? '');
      const blocked = DESTRUCTIVE_PATTERNS.some(p => cmd.includes(p));
      return blocked ? { allow: false, reason: `Destructive operation detected: ${cmd.slice(0, 50)}` } : { allow: true };
    },
  };
}

export function costLimit(cfg: Record<string, unknown> = {}): PolicyRule {
  const maxCost = Number(cfg.maxCost ?? 1.0);
  return {
    name: 'cost_limit',
    description: `Enforce max cost of $${maxCost}`,
    category: 'cost_control',
    evaluate: (input) => {
      const cost = Number(input.cost ?? input.estimatedCost ?? 0);
      return cost > maxCost
        ? { allow: false, reason: `Cost $${cost} exceeds limit $${maxCost}` }
        : { allow: true };
    },
  };
}

export function rateLimit(cfg: Record<string, unknown> = {}): PolicyRule {
  const maxCalls = Number(cfg.maxCalls ?? 10);
  const windowMs = Number(cfg.windowMs ?? 60_000);
  const timestamps: number[] = [];
  return {
    name: 'rate_limit',
    description: `Max ${maxCalls} calls per ${windowMs}ms`,
    category: 'rate_control',
    evaluate: (input) => {
      const now = Number(input.timestamp ?? Date.now());
      timestamps.push(now);
      const cutoff = now - windowMs;
      const recent = timestamps.filter(t => t >= cutoff);
      if (recent.length > maxCalls) {
        return { allow: false, reason: `Rate limit: ${recent.length} calls in window` };
      }
      return { allow: true };
    },
  };
}

const PII_PATTERNS = [/\b\d{3}[-.]?\d{2}[-.]?\d{4}\b/, /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/];

export function piiFilter(_cfg: Record<string, unknown> = {}): PolicyRule {
  return {
    name: 'pii_filter',
    description: 'Blocks input containing PII (SSN-like, email)',
    category: 'data_privacy',
    evaluate: (input) => {
      const text = String(input.text ?? input.content ?? input.input ?? '');
      const matched = PII_PATTERNS.find(p => p.test(text));
      return matched
        ? { allow: false, reason: 'PII detected in input' }
        : { allow: true };
    },
  };
}
