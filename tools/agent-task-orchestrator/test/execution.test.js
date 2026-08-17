import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs-extra';
import path from 'path';
import os from 'os';
import { execFile } from 'child_process';
import { promisify } from 'util';
import { executeTasks } from '../index.js';

const execFileAsync = promisify(execFile);

let tmpDir;

// Silence console during engine tests: high-volume chalk output from
// executeTasks() corrupts the node --test runner protocol stream (flaky
// "Unable to deserialize cloned data" in the parent runner).
function silenceConsole() {
  const orig = { log: console.log, error: console.error };
  console.log = () => {};
  console.error = () => {};
  return () => { console.log = orig.log; console.error = orig.error; };
}

before(async () => {
  tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'ato-exec-'));
});

after(async () => {
  await fs.remove(tmpDir);
});

const settings = { parallelExecution: true, continueOnError: false, timeout: 10000 };

// ─── executeTasks: shell ───────────────────────────────────────────

describe('executeTasks shell tasks', () => {
  let restore;
  before(() => { restore = silenceConsole(); });
  after(() => { restore(); });

  it('executes a shell task and counts it completed', async () => {
    const plan = [[{ id: 'echo', type: 'shell', command: 'echo hello', priority: 5 }]];
    const results = await executeTasks(plan, settings);
    assert.equal(results.totalTasks, 1);
    assert.equal(results.completed, 1);
    assert.equal(results.failed, 0);
    assert.equal(results.tasks[0].status, 'completed');
    assert.match(results.tasks[0].result.stdout, /hello/);
  });

  it('captures stderr in the result', async () => {
    const plan = [[{ id: 'warn', type: 'shell', command: 'echo oops 1>&2', priority: 5 }]];
    const results = await executeTasks(plan, settings);
    assert.equal(results.tasks[0].status, 'completed');
    assert.match(results.tasks[0].result.stderr, /oops/);
  });

  it('writes stdout to task.output file when specified', async () => {
    const out = path.join(tmpDir, 'shell-out.txt');
    const plan = [[{ id: 'save', type: 'shell', command: 'echo saved-data', output: out, priority: 5 }]];
    await executeTasks(plan, settings);
    const content = await fs.readFile(out, 'utf8');
    assert.match(content, /saved-data/);
  });

  it('throws when a shell task fails and continueOnError=false', async () => {
    const plan = [[{ id: 'boom', type: 'shell', command: 'exit 7', priority: 5 }]];
    await assert.rejects(
      () => executeTasks(plan, settings),
      err => err.message.length > 0
    );
  });

  it('records failure but continues when continueOnError=true', async () => {
    const softSettings = { ...settings, continueOnError: true };
    const plan = [
      [
        { id: 'ok', type: 'shell', command: 'echo fine', priority: 5 },
        { id: 'bad', type: 'shell', command: 'exit 3', priority: 5 }
      ]
    ];
    const results = await executeTasks(plan, softSettings);
    assert.equal(results.completed, 1);
    assert.equal(results.failed, 1);
    const failed = results.tasks.find(t => t.id === 'bad');
    assert.equal(failed.status, 'failed');
    assert.ok(failed.error);
  });

  it('kills shell task exceeding its timeout', async () => {
    const shortSettings = { ...settings, timeout: 300 };
    const plan = [[{ id: 'slow', type: 'shell', command: 'sleep 5', priority: 5 }]];
    await assert.rejects(
      () => executeTasks(plan, shortSettings),
      () => true // timeout kill produces various error messages across platforms
    );
  });

  it('uses task-level timeout override over settings timeout', async () => {
    const plan = [[{ id: 'slow2', type: 'shell', command: 'sleep 5', timeout: 300, priority: 5 }]];
    const t0 = Date.now();
    await assert.rejects(
      () => executeTasks(plan, settings),
      () => true
    );
    assert.ok(Date.now() - t0 < 4000, 'should fail fast via task timeout, not settings timeout');
  });
});

// ─── executeTasks: agent / function ────────────────────────────────

describe('executeTasks agent and function tasks', () => {
  let restore;
  before(() => { restore = silenceConsole(); });
  after(() => { restore(); });

  it('returns agent result structure with agent and prompt', async () => {
    const plan = [[{ id: 'bot', type: 'agent', agent: 'catalyst', prompt: 'do things', priority: 5 }]];
    const results = await executeTasks(plan, settings);
    assert.equal(results.tasks[0].status, 'completed');
    const r = results.tasks[0].result;
    assert.equal(r.agent, 'catalyst');
    assert.equal(r.prompt, 'do things');
    assert.ok(r.response.includes('catalyst'));
  });

  it('writes agent result as JSON to output file', async () => {
    const out = path.join(tmpDir, 'agent-out.json');
    const plan = [[{ id: 'bot2', type: 'agent', agent: 'helper', prompt: 'hi', output: out, priority: 5 }]];
    await executeTasks(plan, settings);
    const saved = await fs.readJson(out);
    assert.equal(saved.agent, 'helper');
    assert.equal(saved.prompt, 'hi');
  });

  it('returns function result structure', async () => {
    const plan = [[{ id: 'fn', type: 'function', function: 'myFn', priority: 5 }]];
    const results = await executeTasks(plan, settings);
    const r = results.tasks[0].result;
    assert.equal(r.function, 'myFn');
    assert.ok(r.result.includes('myFn'));
  });

  it('writes function result as JSON to output file', async () => {
    const out = path.join(tmpDir, 'fn-out.json');
    const plan = [[{ id: 'fn2', type: 'function', function: 'calc', output: out, priority: 5 }]];
    await executeTasks(plan, settings);
    const saved = await fs.readJson(out);
    assert.equal(saved.function, 'calc');
  });
});

// ─── executeTasks: plan/counter semantics ──────────────────────────

describe('executeTasks plan semantics', () => {
  let restore;
  before(() => { restore = silenceConsole(); });
  after(() => { restore(); });

  it('fails with unknown task type', async () => {
    const plan = [[{ id: 'weird', type: 'quantum', priority: 5 }]];
    await assert.rejects(
      () => executeTasks(plan, settings),
      err => err.message.includes('未知') || err.message.includes('quantum')
    );
  });

  it('executes stages sequentially and reports stage completion in order', async () => {
    const orderFile = path.join(tmpDir, 'order.txt');
    const plan = [
      [{ id: 'first', type: 'shell', command: `echo first >> ${orderFile}`, priority: 5 }],
      [{ id: 'second', type: 'shell', command: `echo second >> ${orderFile}`, priority: 5 }]
    ];
    const results = await executeTasks(plan, settings);
    assert.equal(results.completed, 2);
    const content = await fs.readFile(orderFile, 'utf8');
    assert.match(content, /first\n.*second/);
  });

  it('returns zero counters for an empty plan', async () => {
    const results = await executeTasks([], settings);
    assert.equal(results.totalTasks, 0);
    assert.equal(results.completed, 0);
    assert.equal(results.failed, 0);
    assert.equal(results.skipped, 0);
    assert.deepEqual(results.tasks, []);
  });

  it('runs parallel tasks in the same stage together', async () => {
    const plan = [[
      { id: 'p1', type: 'shell', command: 'echo p1', priority: 5 },
      { id: 'p2', type: 'shell', command: 'echo p2', priority: 5 },
      { id: 'p3', type: 'shell', command: 'echo p3', priority: 5 }
    ]];
    const results = await executeTasks(plan, settings);
    assert.equal(results.completed, 3);
    assert.equal(results.tasks.length, 3);
    const ids = results.tasks.map(t => t.id).sort();
    assert.deepEqual(ids, ['p1', 'p2', 'p3']);
  });
});

// ─── CLI end-to-end smoke ──────────────────────────────────────────

describe('CLI end-to-end', () => {

  const cli = path.join(process.cwd(), 'index.js');
  let workDir;

  before(async () => {
    workDir = await fs.mkdtemp(path.join(os.tmpdir(), 'ato-cli-'));
  });

  after(async () => {
    await fs.remove(workDir);
  });

  const run = (args) => execFileAsync('node', [cli, ...args], { cwd: workDir });

  it('create → add-task → validate → run --dry-run full flow', async () => {
    const { stdout: createOut } = await run(['create', 'e2e', '-d', 'e2e flow']);
    assert.match(createOut, /创建成功/);

    const orchFile = path.join(workDir, '.orchestrator', 'e2e.json');
    const orch = await fs.readJson(orchFile);
    assert.equal(orch.name, 'e2e');
    assert.equal(orch.settings.timeout, 300000);
    assert.deepEqual(orch.tasks, []);

    await run(['add-task', 'e2e', 'step1', '-c', 'echo one']);
    await run(['add-task', 'e2e', 'step2', '-c', 'echo two', '-d', 'step1', '-p', '9']);
    const orch2 = await fs.readJson(orchFile);
    assert.equal(orch2.tasks.length, 2);
    assert.equal(orch2.tasks[0].type, 'shell');
    assert.equal(orch2.tasks[0].command, 'echo one');
    assert.deepEqual(orch2.tasks[1].dependsOn, ['step1']);
    assert.equal(orch2.tasks[1].priority, 9);

    const { stdout: valOut } = await run(['validate', 'e2e']);
    assert.match(valOut, /验证通过/);

    const { stdout: dryOut } = await run(['run', 'e2e', '--dry-run']);
    assert.match(dryOut, /执行计划/);
    assert.match(dryOut, /step1/);
    assert.match(dryOut, /step2/);
    // dry-run must not execute anything
    assert.ok(!await fs.pathExists(path.join(workDir, 'e2e_export.md')));
  });

  it('refuses to overwrite an existing orchestration without --force', async () => {
    await assert.rejects(
      () => run(['create', 'e2e']),
      err => err.code === 1
    );
    const { stdout } = await run(['create', 'e2e', '--force']);
    assert.match(stdout, /创建成功/);
  });

  it('run executes shell tasks end-to-end', async () => {
    await run(['create', 'runme', '--force']);
    await run(['add-task', 'runme', 'hello', '-c', 'echo cli-ran-ok']);
    const { stdout } = await run(['run', 'runme', '-v']);
    assert.match(stdout, /cli-ran-ok/);
    assert.match(stdout, /完成: 1/);
    assert.match(stdout, /成功率: 100.0%/);
  });

  it('run --tasks filter executes only selected tasks', async () => {
    await run(['create', 'filtered', '--force']);
    await run(['add-task', 'filtered', 'a', '-c', 'echo only-a']);
    await run(['add-task', 'filtered', 'b', '-c', 'echo not-b']);
    const { stdout } = await run(['run', 'filtered', '--tasks', 'a', '-v']);
    assert.match(stdout, /only-a/);
    assert.ok(!stdout.includes('not-b'));
  });

  it('export markdown writes report file', async () => {
    await run(['create', 'exp', '--force', '-d', 'export test']);
    await run(['add-task', 'exp', 't1', '-c', 'echo x']);
    await run(['export', 'exp', '-f', 'markdown']);
    const md = await fs.readFile(path.join(workDir, 'exp_export.md'), 'utf8');
    assert.match(md, /# 任务编排: exp/);
    assert.match(md, /export test/);
    assert.match(md, /t1/);
  });

  it('errors on unknown orchestration name', async () => {
    await assert.rejects(
      () => run(['run', 'ghost-flow']),
      err => err.code === 1 && /不存在/.test(err.stderr + err.stdout)
    );
  });
});
