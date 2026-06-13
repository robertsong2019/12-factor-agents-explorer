import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  buildExecutionPlan,
  validateOrchestrator,
  generateMarkdownReport,
  getStatusIcon
} from '../index.js';

// ─── buildExecutionPlan ────────────────────────────────────────────

describe('buildExecutionPlan', () => {

  it('returns empty array for empty tasks', () => {
    const plan = buildExecutionPlan([], false);
    assert.deepEqual(plan, []);
  });

  it('puts each task in its own stage when sequential=true', () => {
    const tasks = [
      { id: 'a', type: 'shell', priority: 5 },
      { id: 'b', type: 'shell', priority: 5 },
      { id: 'c', type: 'shell', priority: 5 }
    ];
    const plan = buildExecutionPlan(tasks, true);
    assert.equal(plan.length, 3);
    assert.deepEqual(plan[0], [tasks[0]]);
    assert.deepEqual(plan[1], [tasks[1]]);
    assert.deepEqual(plan[2], [tasks[2]]);
  });

  it('groups independent tasks into one stage when parallel', () => {
    const tasks = [
      { id: 'a', type: 'shell', priority: 5 },
      { id: 'b', type: 'shell', priority: 5 },
      { id: 'c', type: 'shell', priority: 5 }
    ];
    const plan = buildExecutionPlan(tasks, false);
    assert.equal(plan.length, 1);
    assert.equal(plan[0].length, 3);
  });

  it('respects simple dependency chain', () => {
    const tasks = [
      { id: 'a', type: 'shell', priority: 5 },
      { id: 'b', type: 'shell', priority: 5, dependsOn: ['a'] },
      { id: 'c', type: 'shell', priority: 5, dependsOn: ['b'] }
    ];
    const plan = buildExecutionPlan(tasks, false);
    assert.equal(plan.length, 3);
    assert.equal(plan[0][0].id, 'a');
    assert.equal(plan[1][0].id, 'b');
    assert.equal(plan[2][0].id, 'c');
  });

  it('respects diamond dependency', () => {
    //     a
    //    / \
    //   b   c
    //    \ /
    //     d
    const tasks = [
      { id: 'a', type: 'shell', priority: 5 },
      { id: 'b', type: 'shell', priority: 5, dependsOn: ['a'] },
      { id: 'c', type: 'shell', priority: 5, dependsOn: ['a'] },
      { id: 'd', type: 'shell', priority: 5, dependsOn: ['b', 'c'] }
    ];
    const plan = buildExecutionPlan(tasks, false);
    assert.equal(plan.length, 3);
    assert.equal(plan[0][0].id, 'a');
    // stage 2 should have b and c
    const stage2Ids = plan[1].map(t => t.id).sort();
    assert.deepEqual(stage2Ids, ['b', 'c']);
    assert.equal(plan[2][0].id, 'd');
  });

  it('groups tasks with no deps in stage 1 even if other tasks have deps', () => {
    const tasks = [
      { id: 'a', type: 'shell', priority: 5 },
      { id: 'b', type: 'shell', priority: 5 },
      { id: 'c', type: 'shell', priority: 5, dependsOn: ['a'] }
    ];
    const plan = buildExecutionPlan(tasks, false);
    assert.equal(plan.length, 2);
    // stage 1: a and b (both have no deps)
    assert.equal(plan[0].length, 2);
    // stage 2: c
    assert.equal(plan[1].length, 1);
    assert.equal(plan[1][0].id, 'c');
  });

  it('handles circular dependency by breaking out of loop', () => {
    const tasks = [
      { id: 'a', type: 'shell', priority: 5, dependsOn: ['b'] },
      { id: 'b', type: 'shell', priority: 5, dependsOn: ['a'] }
    ];
    const plan = buildExecutionPlan(tasks, false);
    // Both tasks depend on each other - can't execute either
    assert.equal(plan.length, 0);
  });

  it('handles single task', () => {
    const tasks = [{ id: 'solo', type: 'shell', priority: 5 }];
    const plan = buildExecutionPlan(tasks, false);
    assert.equal(plan.length, 1);
    assert.equal(plan[0][0].id, 'solo');
  });
});

// ─── validateOrchestrator ──────────────────────────────────────────

describe('validateOrchestrator', () => {

  const validOrchestrator = {
    name: 'test-pipeline',
    tasks: [
      { id: 'task1', type: 'shell' },
      { id: 'task2', type: 'shell', dependsOn: ['task1'] }
    ]
  };

  it('passes for a valid orchestrator', () => {
    const result = validateOrchestrator(validOrchestrator);
    assert.equal(result.isValid, true);
    assert.deepEqual(result.errors, []);
  });

  it('fails when name is missing', () => {
    const result = validateOrchestrator({ tasks: [] });
    assert.equal(result.isValid, false);
    assert.ok(result.errors.some(e => e.includes('名称')));
  });

  it('fails when tasks is not an array', () => {
    const result = validateOrchestrator({ name: 'test', tasks: 'not-array' });
    assert.equal(result.isValid, false);
    assert.ok(result.errors.some(e => e.includes('格式错误')));
  });

  it('fails when tasks is missing entirely', () => {
    const result = validateOrchestrator({ name: 'test' });
    assert.equal(result.isValid, false);
    assert.ok(result.errors.some(e => e.includes('格式错误')));
  });

  it('detects duplicate task IDs', () => {
    const orch = {
      name: 'test',
      tasks: [
        { id: 'dup', type: 'shell' },
        { id: 'dup', type: 'shell' }
      ]
    };
    const result = validateOrchestrator(orch);
    assert.equal(result.isValid, false);
    assert.ok(result.errors.some(e => e.includes('重复')));
  });

  it('detects task missing ID', () => {
    const orch = {
      name: 'test',
      tasks: [
        { type: 'shell' }
      ]
    };
    const result = validateOrchestrator(orch);
    assert.equal(result.isValid, false);
    assert.ok(result.errors.some(e => e.includes('缺少ID')));
  });

  it('detects task missing type', () => {
    const orch = {
      name: 'test',
      tasks: [
        { id: 't1' }
      ]
    };
    const result = validateOrchestrator(orch);
    assert.equal(result.isValid, false);
    assert.ok(result.errors.some(e => e.includes('缺少类型')));
  });

  it('detects dependency on non-existent task', () => {
    const orch = {
      name: 'test',
      tasks: [
        { id: 't1', type: 'shell', dependsOn: ['ghost'] }
      ]
    };
    const result = validateOrchestrator(orch);
    assert.equal(result.isValid, false);
    assert.ok(result.errors.some(e => e.includes('ghost')));
  });

  it('passes with empty tasks array', () => {
    const result = validateOrchestrator({ name: 'empty', tasks: [] });
    assert.equal(result.isValid, true);
  });
});

// ─── generateMarkdownReport ────────────────────────────────────────

describe('generateMarkdownReport', () => {

  it('generates report with name and basic info', () => {
    const orch = {
      name: 'my-pipeline',
      description: 'A test pipeline',
      version: '1.0.0',
      createdAt: '2026-01-01T00:00:00.000Z',
      tasks: [],
      settings: { parallelExecution: true, continueOnError: false, timeout: 300000 }
    };
    const md = generateMarkdownReport(orch);
    assert.ok(md.includes('# 任务编排: my-pipeline'));
    assert.ok(md.includes('**描述:** A test pipeline'));
    assert.ok(md.includes('**版本:** 1.0.0'));
    assert.ok(md.includes('**任务数量:** 0'));
  });

  it('includes task details when tasks exist', () => {
    const orch = {
      name: 'with-tasks',
      version: '1.0.0',
      createdAt: '2026-01-01T00:00:00.000Z',
      tasks: [
        { id: 'build', type: 'shell', priority: 5, description: 'Build step' },
        { id: 'test', type: 'shell', priority: 8, dependsOn: ['build'] }
      ],
      settings: { parallelExecution: false, continueOnError: false, timeout: 60000 }
    };
    const md = generateMarkdownReport(orch);
    assert.ok(md.includes('### 1. build'));
    assert.ok(md.includes('### 2. test'));
    assert.ok(md.includes('**类型:** shell'));
    assert.ok(md.includes('**优先级:** 8'));
    assert.ok(md.includes('**描述:** Build step'));
    assert.ok(md.includes('**依赖:** build'));
  });

  it('handles empty description', () => {
    const orch = {
      name: 'no-desc',
      version: '1.0.0',
      createdAt: '2026-01-01T00:00:00.000Z',
      tasks: [],
      settings: { parallelExecution: true, continueOnError: false, timeout: 300000 }
    };
    const md = generateMarkdownReport(orch);
    assert.ok(md.includes('# 任务编排: no-desc'));
    assert.ok(!md.includes('**描述:**'));
  });

  it('shows correct parallel/error values', () => {
    const orch = {
      name: 'cfg-test',
      version: '1.0.0',
      createdAt: '2026-01-01T00:00:00.000Z',
      tasks: [],
      settings: { parallelExecution: false, continueOnError: true, timeout: 5000 }
    };
    const md = generateMarkdownReport(orch);
    assert.ok(md.includes('**并行执行:** 否'));
    assert.ok(md.includes('**错误继续:** 是'));
    assert.ok(md.includes('**超时时间:** 5000ms'));
  });
});

// ─── getStatusIcon ─────────────────────────────────────────────────

describe('getStatusIcon', () => {

  it('returns ⏸️ for undefined status', () => {
    assert.equal(getStatusIcon({}), '⏸️');
    assert.equal(getStatusIcon({ status: undefined }), '⏸️');
  });

  it('returns ✅ for completed', () => {
    assert.equal(getStatusIcon({ status: 'completed' }), '✅');
  });

  it('returns ❌ for failed', () => {
    assert.equal(getStatusIcon({ status: 'failed' }), '❌');
  });

  it('returns 🔄 for running', () => {
    assert.equal(getStatusIcon({ status: 'running' }), '🔄');
  });

  it('returns ⏳ for pending', () => {
    assert.equal(getStatusIcon({ status: 'pending' }), '⏳');
  });

  it('returns ⏸️ for unknown status', () => {
    assert.equal(getStatusIcon({ status: 'whatever' }), '⏸️');
  });
});
