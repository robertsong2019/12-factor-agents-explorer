import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  registerTemplate,
  getTemplate,
  listTemplates,
  removeTemplate,
  clearTemplates,
  generateFromTemplate,
  formatScriptsTable,
  formatDepsTable,
  resolvePath,
  isIgnored,
} from '../context-forge.mjs';

// ─── Template Registry Tests ─────────────────────────────────────

test('F31: registerTemplate adds to registry', () => {
  // Save existing templates to restore later
  const existing = listTemplates();
  clearTemplates();
  
  registerTemplate('my-tmpl', 'Hello {{name}}!');
  assert.deepEqual(listTemplates(), ['my-tmpl']);
  
  // Restore
  clearTemplates();
  for (const name of existing) {
    // Can't restore content, but at least restore names by re-registering builtins
  }
});

test('F31: registerTemplate throws on non-string args', () => {
  assert.throws(() => registerTemplate(123, 'template'), TypeError);
  assert.throws(() => registerTemplate('name', 42), TypeError);
});

test('F31: getTemplate returns registered template', () => {
  clearTemplates();
  registerTemplate('greeting', 'Hello {{name}}!');
  const tmpl = getTemplate('greeting');
  assert.equal(tmpl, 'Hello {{name}}!');
});

test('F31: getTemplate returns null for unregistered', () => {
  clearTemplates();
  const tmpl = getTemplate('nonexistent');
  assert.equal(tmpl, null);
});

test('F31: listTemplates returns all names', () => {
  clearTemplates();
  registerTemplate('a', 'A');
  registerTemplate('b', 'B');
  registerTemplate('c', 'C');
  const names = listTemplates();
  assert.deepEqual(names.sort(), ['a', 'b', 'c']);
});

test('F31: removeTemplate deletes entry', () => {
  clearTemplates();
  registerTemplate('removable', 'content');
  assert.equal(removeTemplate('removable'), true);
  assert.equal(getTemplate('removable'), null);
  assert.equal(removeTemplate('nonexistent'), false);
});

test('F31: clearTemplates empties registry', () => {
  registerTemplate('x', 'X');
  registerTemplate('y', 'Y');
  clearTemplates();
  assert.equal(listTemplates().length, 0);
});

test('F31: generateFromTemplate uses registered template', () => {
  clearTemplates();
  registerTemplate('hello', 'Hello {{name}}!');
  const result = generateFromTemplate('hello', { name: 'World' });
  assert.equal(result, 'Hello World!');
});

test('F31: generateFromTemplate uses inline template', () => {
  clearTemplates();
  const result = generateFromTemplate('Hi {{name}}!', { name: 'Catalyst' });
  assert.equal(result, 'Hi Catalyst!');
});

test('F31: generateFromTemplate prefers registered over inline', () => {
  clearTemplates();
  registerTemplate('greet', 'Registered: {{name}}');
  // When the string matches a registered name, use the registered template
  const result = generateFromTemplate('greet', { name: 'Test' });
  assert.equal(result, 'Registered: Test');
});

// ─── formatScriptsTable Tests ────────────────────────────────────

test('F31: formatScriptsTable formats scripts', () => {
  const scripts = { test: 'jest', build: 'tsc', start: 'node .' };
  const result = formatScriptsTable(scripts);
  assert.ok(result.includes('| Script | Command |'));
  assert.ok(result.includes('`test`'));
  assert.ok(result.includes('jest'));
  assert.ok(result.includes('`build`'));
  assert.ok(result.includes('tsc'));
});

test('F31: formatScriptsTable handles empty', () => {
  const result = formatScriptsTable({});
  assert.equal(result, '- (none defined)');
});

test('F31: formatScriptsTable respects max limit', () => {
  const scripts = {};
  for (let i = 0; i < 25; i++) scripts[`s${i}`] = `cmd${i}`;
  const result = formatScriptsTable(scripts, 5);
  assert.ok(result.includes('more'));
  assert.ok(result.includes('20 more'));
});

// ─── formatDepsTable Tests ───────────────────────────────────────

test('F31: formatDepsTable formats deps', () => {
  const deps = { lodash: '4.17.21', express: '^4.18.0' };
  const result = formatDepsTable(deps);
  assert.ok(result.includes('| Package | Version |'));
  assert.ok(result.includes('`lodash`'));
  assert.ok(result.includes('4.17.21'));
});

test('F31: formatDepsTable handles empty', () => {
  const result = formatDepsTable({});
  assert.equal(result, '- (none)');
});

test('F31: formatDepsTable respects max limit', () => {
  const deps = {};
  for (let i = 0; i < 25; i++) deps[`pkg${i}`] = `^${i}.0.0`;
  const result = formatDepsTable(deps, 5);
  assert.ok(result.includes('more'));
  assert.ok(result.includes('20 more'));
});

// ─── resolvePath Tests ───────────────────────────────────────────

test('F31: resolvePath returns absolute path as-is', () => {
  const result = resolvePath('/usr/local/bin');
  assert.equal(result, '/usr/local/bin');
});

test('F31: resolvePath joins cwd with relative path', () => {
  const result = resolvePath('foo/bar');
  assert.ok(result.startsWith('/'));
  assert.ok(result.endsWith('foo/bar'));
});

// ─── isIgnored Tests ─────────────────────────────────────────────

test('F31: isIgnored matches exact directory name', () => {
  assert.equal(isIgnored('node_modules', ['node_modules']), true);
  assert.equal(isIgnored('src/main.js', ['node_modules']), false);
});

test('F31: isIgnored matches nested path', () => {
  assert.equal(isIgnored('project/node_modules/express', ['node_modules']), true);
  assert.equal(isIgnored('project/src/index.js', ['node_modules']), false);
});

test('F31: isIgnored handles wildcard patterns', () => {
  assert.equal(isIgnored('test.log', ['*.log']), true);
  assert.equal(isIgnored('src/app.js', ['*.log']), false);
});

test('F31: isIgnored handles directory patterns with trailing slash', () => {
  assert.equal(isIgnored('dist', ['dist/']), true);
  assert.equal(isIgnored('distribute', ['dist/']), false);
});

test('F31: isIgnored handles negation patterns', () => {
  // First match, then negate
  assert.equal(isIgnored('important.log', ['*.log', '!important.log']), false);
  assert.equal(isIgnored('debug.log', ['*.log', '!important.log']), true);
});

test('F31: isIgnored returns false for empty patterns', () => {
  assert.equal(isIgnored('any/path', []), false);
});
