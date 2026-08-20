#!/usr/bin/env node
// Hermetic test suite for agent-framework-manager (afm)
// All tests run in a temp cwd; no live-workspace dependencies.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs-extra';
import path from 'path';
import os from 'os';
import { execFile } from 'child_process';
import { promisify } from 'util';

const execFileAsync = promisify(execFile);

const ROOT = path.dirname(path.dirname(new URL(import.meta.url).pathname));
const CLI = path.join(ROOT, 'bin', 'afm.js');

let tmpdir;
const afm = () => path.join(tmpdir, '.afm');

before(async () => {
  tmpdir = await fs.mkdtemp(path.join(os.tmpdir(), 'afm-test-'));
  process.chdir(tmpdir);
});

after(async () => {
  process.chdir(os.tmpdir());
  await fs.remove(tmpdir);
});

// ---------- ConfigManager ----------
const { ConfigManager } = await import(path.join(ROOT, 'lib', 'config-manager.js'));

test('ConfigManager: default config when no file exists (constructor race fixed)', async () => {
  const cm = new ConfigManager();
  assert.ok(cm.config, 'config must be set immediately after construction');
  assert.equal(cm.config.globalSettings.logLevel, 'info');
  assert.equal(cm.config.globalSettings.maxConcurrent, 5);
  assert.deepEqual(cm.config.agents, {});
});

test('ConfigManager: editSection prompt array is constructible (editAgents quote bug fixed)', async () => {
  // Regression: `name:editAgents` (missing quotes) threw ReferenceError when
  // building the inquirer prompt array. We can't run inquirer non-interactively,
  // so verify the source no longer contains the bare identifier form.
  const src = await fs.readFile(path.join(ROOT, 'lib', 'config-manager.js'), 'utf8');
  assert.doesNotMatch(src, /name\s*:\s*editAgents\s*,/m, 'bare editAgents identifier must be quoted');
  assert.match(src, /name\s*:\s*'editAgents'/);
});

test('ConfigManager: loadConfig reads existing config.json', async () => {
  await fs.ensureDir(afm());
  await fs.writeJSON(path.join(afm(), 'config.json'), { globalSettings: { logLevel: 'debug' }, agents: { a1: {} } });
  const cm = new ConfigManager();
  assert.equal(cm.config.globalSettings.logLevel, 'debug');
  assert.ok(cm.config.agents.a1);
});

test('ConfigManager: loadConfig survives corrupted JSON (falls back to default)', async () => {
  await fs.ensureDir(afm());
  await fs.writeFile(path.join(afm(), 'config.json'), '{not json');
  const cm = new ConfigManager();
  assert.equal(cm.config.globalSettings.logLevel, 'info');
});

test('ConfigManager: mergeConfig deep-merges nested objects without clobbering siblings', async () => {
  const cm = new ConfigManager();
  cm.mergeConfig({ globalSettings: { logLevel: 'warn' }, storage: { type: 'redis' } });
  assert.equal(cm.config.globalSettings.logLevel, 'warn');
  assert.equal(cm.config.globalSettings.timeout, 30000, 'sibling keys preserved');
  assert.equal(cm.config.storage.type, 'redis');
  assert.equal(cm.config.monitoring.enabled, true, 'other sections preserved');
});

test('ConfigManager: importFromEnv converts types and merges (non-interactive)', async () => {
  process.env.AFM_LOG_LEVEL = 'debug';
  process.env.AFM_MAX_CONCURRENT = '9';
  process.env.AFM_TIMEOUT = '1234';
  process.env.AFM_AUTO_START = 'true';
  const cm = new ConfigManager();
  await cm.importFromEnv();
  delete process.env.AFM_LOG_LEVEL; delete process.env.AFM_MAX_CONCURRENT;
  delete process.env.AFM_TIMEOUT; delete process.env.AFM_AUTO_START;
  assert.equal(cm.config.globalSettings.logLevel, 'debug');
  assert.equal(cm.config.globalSettings.maxConcurrent, 9);
  assert.equal(cm.config.globalSettings.timeout, 1234);
  assert.equal(cm.config.globalSettings.autoStart, true);
  // persisted to disk
  const saved = await fs.readJSON(path.join(afm(), 'config.json'));
  assert.equal(saved.globalSettings.maxConcurrent, 9);
});

test('ConfigManager: backupConfig rotates, keeping only 5 newest backups', async () => {
  await cmSave(new ConfigManager()); // ensure config.json exists
  const backupDir = path.join(afm(), 'backups');
  await fs.ensureDir(backupDir);
  // seed 7 old backups (older timestamps sort before new one)
  for (let i = 1; i <= 7; i++) {
    await fs.writeFile(path.join(backupDir, `config-backup-2026-01-0${i}T00-00-00-000Z.json`), '{}');
  }
  const cm = new ConfigManager();
  await cm.backupConfig();
  const remaining = (await fs.readdir(backupDir)).filter(f => f.startsWith('config-backup-')).sort();
  assert.equal(remaining.length, 5, 'exactly 5 backups retained');
  // oldest two seeds pruned
  assert.ok(!remaining.includes('config-backup-2026-01-01T00-00-00-000Z.json'));
  assert.ok(!remaining.includes('config-backup-2026-01-02T00-00-00-000Z.json'));
});

async function cmSave(cm) { await cm.saveConfig(); }

test('ConfigManager: checkConfigFile/checkAgentsDir report missing state', async () => {
  await fs.remove(afm());
  const cm = new ConfigManager();
  const cfg = await cm.checkConfigFile();
  assert.equal(cfg.status, false);
  assert.ok(cfg.suggestions.some(s => s.includes('afm init')));
  const dir = await cm.checkAgentsDir();
  assert.equal(dir.status, false);
  const perm = await cm.checkPermissions();
  assert.equal(perm.status, true, 'temp dir is writable');
});

// ---------- AgentManager ----------
const { AgentManager } = await import(path.join(ROOT, 'lib', 'agent-manager.js'));

test('AgentManager: config defaults when file missing (null-config bug fixed)', async () => {
  await fs.remove(afm());
  const am = new AgentManager();
  assert.ok(am.config, 'config must not be null after construction');
  assert.deepEqual(am.config.agents, {});
});

test('AgentManager: init creates structure + sample agent, refuses overwrite without --force', async () => {
  await fs.remove(afm());
  const am = new AgentManager();
  await am.init();
  for (const d of ['agents', 'logs', 'backups']) {
    assert.ok(await fs.pathExists(path.join(afm(), d)), `${d} dir created`);
  }
  const sample = await fs.readJSON(path.join(afm(), 'agents', 'sample-agent.json'));
  assert.equal(sample.name, 'sample-agent');
  assert.equal(sample.type, 'openai');
  // guard
  await assert.rejects(() => am.init(), /--force/);
  await am.init(true); // force overwrite ok
});

test('AgentManager: listAgents on missing .afm/agents no longer throws ENOENT', async () => {
  await fs.remove(afm());
  const am = new AgentManager();
  await am.listAgents(); // must not throw
});

test('AgentManager: addAgent writes file + registry, rejects duplicates', async () => {
  await fs.remove(afm());
  const am = new AgentManager();
  await am.init();
  await am.addAgent({ name: 'bot1', type: 'claude', endpoint: 'http://x', apiKey: 'k', model: 'm1', maxTokens: 100 });
  const file = await fs.readJSON(path.join(afm(), 'agents', 'bot1.json'));
  assert.equal(file.temperature, 0.7, 'default temperature');
  assert.equal(file.enabled, true);
  const cfg = await fs.readJSON(path.join(afm(), 'config.json'));
  assert.ok(cfg.agents.bot1, 'registered in main config');
  await assert.rejects(() => am.addAgent({ name: 'bot1', type: 'x' }), /已存在/);
});

test('AgentManager: parseUptime handles all ps etime formats', async () => {
  const am = new AgentManager();
  assert.equal(am.parseUptime('42'), 42, 'SS');
  assert.equal(am.parseUptime('05:30'), 330, 'MM:SS — regression: was 19800');
  assert.equal(am.parseUptime('02:03:04'), 7384, 'HH:MM:SS');
  assert.equal(am.parseUptime('1-02:03:04'), 93784, 'DD-HH:MM:SS');
});

test('AgentManager: getAgentStatus — no pid file, live pid, dead pid auto-cleanup', async () => {
  await fs.remove(afm());
  const am = new AgentManager();
  await am.init();
  // no pid file
  assert.deepEqual(await am.getAgentStatus('bot1'), { running: false, pid: null, uptime: 0 });
  // live pid (this test process)
  await fs.ensureDir(path.join(afm(), 'pids'));
  await fs.writeFile(path.join(afm(), 'pids', 'bot1.pid'), String(process.pid));
  const live = await am.getAgentStatus('bot1');
  assert.equal(live.running, true);
  assert.equal(live.pid, String(process.pid));
  assert.ok(live.uptime >= 0);
  // dead pid → cleaned up + reported stopped
  await fs.writeFile(path.join(afm(), 'pids', 'bot1.pid'), '99999999');
  const dead = await am.getAgentStatus('bot1');
  assert.equal(dead.running, false);
  assert.ok(!(await fs.pathExists(path.join(afm(), 'pids', 'bot1.pid'))), 'stale pid file removed');
});

test('AgentManager: stopAgent on missing pid file is a no-op, on dead pid cleans up', async () => {
  await fs.remove(afm());
  const am = new AgentManager();
  await am.init();
  await am.stopAgent('ghost'); // no pid file → warn + return
  await fs.ensureDir(path.join(afm(), 'pids'));
  await fs.writeFile(path.join(afm(), 'pids', 'ghost.pid'), '99999999');
  await am.stopAgent('ghost');
  assert.ok(!(await fs.pathExists(path.join(afm(), 'pids', 'ghost.pid'))));
});

test('AgentManager: startAgent spawns real process, records real pid (exec-no-pid bug fixed)', { timeout: 20000 }, async () => {
  await fs.remove(afm());
  const am = new AgentManager();
  await am.init();
  await assert.rejects(() => am.startAgent('missing-agent'), /不存在/);
  await am.startAgent('sample-agent');
  const pidPath = path.join(afm(), 'pids', 'sample-agent.pid');
  assert.ok(await fs.pathExists(pidPath), 'pid file written');
  const pid = parseInt(await fs.readFile(pidPath, 'utf8'));
  assert.ok(Number.isInteger(pid) && pid > 0, 'pid must be a real number (was "undefined")');
  // generated script imports runner via absolute URL
  const script = await fs.readFile(path.join(afm(), 'scripts', 'start-sample-agent.js'), 'utf8');
  assert.match(script, /file:\/\//, 'runner import is an absolute file URL');
  // second start is a no-op while running
  await am.startAgent('sample-agent');
  assert.equal(parseInt(await fs.readFile(pidPath, 'utf8')), pid);
  // stop it
  await am.stopAgent('sample-agent');
  // give the OS a beat, then confirm process is gone
  await new Promise(r => setTimeout(r, 300));
  let alive = false;
  try { process.kill(pid, 0); alive = true; } catch {}
  assert.equal(alive, false, 'spawned agent terminated');
});

// ---------- Monitor ----------
const { Monitor } = await import(path.join(ROOT, 'lib', 'monitor.js'));

test('Monitor: formatUptime + formatBytes', async () => {
  const m = new Monitor();
  assert.equal(m.formatUptime(59), '59秒');
  assert.equal(m.formatUptime(60), '1分钟 0秒');
  assert.equal(m.formatUptime(3661), '1小时 1分钟 1秒');
  assert.equal(m.formatUptime(90061), '1天 1小时 1分钟');
  assert.equal(m.formatBytes(0), '0 Bytes');
  assert.equal(m.formatBytes(1024), '1 KB');
  assert.equal(m.formatBytes(1536), '1.5 KB');
});

test('Monitor: parseUptime MM:SS regression (was 19800 for 05:30)', async () => {
  const m = new Monitor();
  assert.equal(m.parseUptime('05:30'), 330);
  assert.equal(m.parseUptime('02:03:04'), 7384);
});

test('Monitor: getAllAgentsStatus on missing/empty dirs returns [] without crash', async () => {
  await fs.remove(afm());
  const m = new Monitor();
  assert.deepEqual(await m.getAllAgentsStatus(), []);
  await fs.ensureDir(path.join(afm(), 'agents'));
  assert.deepEqual(await m.getAllAgentsStatus(), []);
});

test('Monitor: getAgentStatus live/dead + memory field present when running', async () => {
  await fs.remove(afm());
  const m = new Monitor();
  await fs.ensureDir(path.join(afm(), 'pids'));
  await fs.writeFile(path.join(afm(), 'pids', 'me.pid'), String(process.pid));
  const live = await m.getAgentStatus('me');
  assert.equal(live.running, true);
  assert.equal(typeof live.memory, 'number');
  await fs.writeFile(path.join(afm(), 'pids', 'dead.pid'), '99999999');
  const dead = await m.getAgentStatus('dead');
  assert.equal(dead.running, false);
  assert.ok(!(await fs.pathExists(path.join(afm(), 'pids', 'dead.pid'))));
});

// ---------- AgentRunner (unit, no real timers beyond stubbed loop) ----------
const { AgentRunner } = await import(path.join(ROOT, 'lib', 'agent-runner.js'));

function makeRunner() {
  return new AgentRunner({ name: 'unit-agent', type: 'custom', model: 'test' });
}

test('AgentRunner: start/stop lifecycle + events', async () => {
  const r = makeRunner();
  const events = [];
  r.on('started', e => events.push(['started', e]));
  r.on('stopped', e => events.push(['stopped', e]));
  assert.equal(r.running, false);
  r.performAgentTask = async () => {}; // stub the simulated API call
  await r.start();
  assert.equal(r.running, true);
  await r.start().then(() => assert.fail('double start must throw'), e => assert.match(e.message, /已在运行中/));
  await r.stop();
  assert.equal(r.running, false);
  await r.stop().then(() => assert.fail('stop when idle must throw'), e => assert.match(e.message, /未运行/));
  assert.equal(events[0][0], 'started');
  assert.equal(events[0][1].name, 'unit-agent');
  assert.equal(events[1][0], 'stopped');
  assert.ok(events[1][1].uptime >= 0);
});

test('AgentRunner: stats math — incremental average response time', async () => {
  const r = makeRunner();
  r.updateStats(100);
  assert.equal(r.stats.requests, 1);
  assert.equal(r.stats.averageResponseTime, 100);
  r.updateStats(200);
  assert.equal(r.stats.averageResponseTime, 150);
  r.updateStats(250);
  assert.equal(r.stats.averageResponseTime, 183 + 1 / 3, 'cumulative mean over 3 samples');
});

test('AgentRunner: isFatalError classification', async () => {
  const r = makeRunner();
  assert.equal(r.isFatalError(new Error('API_KEY_INVALID: bad key')), true);
  assert.equal(r.isFatalError(new Error('QUOTA_EXCEEDED')), true);
  assert.equal(r.isFatalError(new Error('transient NETWORK_TIMEOUT')), false);
  assert.equal(r.isFatalError(new Error('unknown')), false);
});

test('AgentRunner: unsupported type throws, getStatus snapshot', async () => {
  const r = new AgentRunner({ name: 'x', type: 'weird', model: 'm' });
  await assert.rejects(() => r.performAgentTask(), /不支持的Agent类型/);
  const s = r.getStatus();
  assert.equal(s.name, 'x');
  assert.equal(s.running, false);
  assert.equal(s.uptime, 0);
  assert.deepEqual(s.stats.errors, 0);
});

// ---------- CLI end-to-end (non-interactive paths only) ----------
async function cli(args) {
  return execFileAsync('node', [CLI, ...args], { cwd: tmpdir });
}

test('CLI: --help / --version', async () => {
  const help = await cli(['--help']);
  assert.match(help.stdout, /afm/);
  assert.match(help.stdout, /init/);
  const v = await cli(['--version']);
  assert.equal(v.stdout.trim(), '1.0.0');
});

test('CLI: init → agent --list → config --show → tools --diagnose', async () => {
  await fs.remove(afm());
  const init = await cli(['init']);
  assert.match(init.stdout, /初始化完成/);
  const again = await execFileAsync('node', [CLI, 'init'], { cwd: tmpdir }).then(
    () => assert.fail('re-init without --force must fail'),
    e => { assert.equal(e.code, 1); assert.match(e.stderr, /--force/); }
  );
  const list = await cli(['agent', '--list']);
  assert.match(list.stdout, /sample-agent/);
  assert.match(list.stdout, /openai/);
  const show = await cli(['config', '--show']);
  assert.match(show.stdout, /globalSettings/);
  const diag = await cli(['tools', '--diagnose']);
  assert.match(diag.stdout, /configFile/);
  assert.match(diag.stdout, /✓|✗/);
});

test('CLI: agent --list with no .afm degrades gracefully (exit 0)', async () => {
  await fs.remove(afm());
  const list = await cli(['agent', '--list']);
  assert.match(list.stdout, /没有找到Agent/);
});

test('CLI: monitor --logs for missing agent exits cleanly', async () => {
  await fs.remove(afm());
  await cli(['init']);
  const out = await cli(['monitor', '--logs', 'nobody']);
  assert.match(out.stdout, /日志文件不存在/);
});

test('CLI: agent --status via pid file (live self pid)', async () => {
  await fs.remove(afm());
  await cli(['init']);
  await fs.ensureDir(path.join(afm(), 'pids'));
  await fs.writeFile(path.join(afm(), 'pids', 'sample-agent.pid'), String(process.pid));
  const out = await cli(['agent', '--status', 'sample-agent']);
  assert.match(out.stdout, /运行中|已停止/);
});
