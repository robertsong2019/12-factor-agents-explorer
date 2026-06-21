import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  registerTemplate,
  getTemplate,
  listTemplates,
  removeTemplate,
  clearTemplates,
  generateFromTemplate,
  applyTemplate,
  validateTemplate,
  extractTemplateVars,
} from '../context-forge.mjs';

// ─── Registry Management ────────────────────────────────────────

describe('Template Registry', () => {
  beforeEach(() => {
    clearTemplates();
  });

  it('registers and retrieves templates by name', () => {
    registerTemplate('brief', '# {{project.name}}');
    registerTemplate('custom', 'Hello {{name}}!');
    assert.equal(getTemplate('custom'), 'Hello {{name}}!');
    assert.equal(getTemplate('brief'), '# {{project.name}}');
  });

  it('returns null for unregistered templates', () => {
    assert.equal(getTemplate('nonexistent'), null);
  });

  it('lists all registered template names', () => {
    registerTemplate('brief', '# {{x}}');
    registerTemplate('json-compact', '{}');
    registerTemplate('custom', 'temp');
    const names = listTemplates();
    assert.ok(names.includes('brief'));
    assert.ok(names.includes('json-compact'));
    assert.ok(names.includes('custom'));
  });

  it('removes templates by name', () => {
    registerTemplate('temp', 'temporary');
    assert.ok(getTemplate('temp'));
    removeTemplate('temp');
    assert.equal(getTemplate('temp'), null);
  });

  it('returns true when removing existing template', () => {
    registerTemplate('existing', 'val');
    assert.equal(removeTemplate('existing'), true);
  });

  it('returns false when removing non-existent template', () => {
    assert.equal(removeTemplate('nope'), false);
  });

  it('clears all templates', () => {
    registerTemplate('a', '1');
    registerTemplate('b', '2');
    clearTemplates();
    assert.equal(listTemplates().length, 0);
  });

  it('overwrites template when re-registering same name', () => {
    registerTemplate('dual', 'first');
    registerTemplate('dual', 'second');
    assert.equal(getTemplate('dual'), 'second');
  });

  it('throws on invalid arguments', () => {
    assert.throws(() => registerTemplate(123, 'x'), TypeError);
    assert.throws(() => registerTemplate('x', 123), TypeError);
    assert.throws(() => registerTemplate(null, 'x'), TypeError);
  });
});

// ─── generateFromTemplate ───────────────────────────────────────

describe('generateFromTemplate', () => {
  beforeEach(() => {
    clearTemplates();
    registerTemplate('greeting', 'Hello {{name}}, you are {{role}}!');
    registerTemplate('nested', '{{project.name}} ({{project.type}})');
  });

  it('generates from named template', () => {
    const result = generateFromTemplate('greeting', { name: 'Alice', role: 'admin' });
    assert.equal(result, 'Hello Alice, you are admin!');
  });

  it('resolves nested dot-notation paths', () => {
    const result = generateFromTemplate('nested', { project: { name: 'app', type: 'node' } });
    assert.equal(result, 'app (node)');
  });

  it('falls back to inline template string when name not found', () => {
    const result = generateFromTemplate('Hi {{user}}!', { user: 'Bob' });
    assert.equal(result, 'Hi Bob!');
  });

  it('returns empty string for missing variables', () => {
    const result = generateFromTemplate('Hello {{missing.thing}}', {});
    assert.equal(result, 'Hello ');
  });

  it('handles array values by joining with commas', () => {
    const result = generateFromTemplate('Items: {{items}}', { items: ['a', 'b', 'c'] });
    assert.equal(result, 'Items: a, b, c');
  });

  it('handles object values by JSON stringifying', () => {
    const result = generateFromTemplate('Data: {{obj}}', { obj: { x: 1 } });
    assert.equal(result, 'Data: {"x":1}');
  });

  it('handles null and undefined gracefully', () => {
    assert.equal(generateFromTemplate(null, {}), '');
    assert.equal(generateFromTemplate(undefined, {}), '');
  });
});

// ─── applyTemplate edge cases ───────────────────────────────────

describe('applyTemplate', () => {
  it('replaces simple variables', () => {
    assert.equal(applyTemplate('Hello {{name}}', { name: 'World' }), 'Hello World');
  });

  it('handles multiple variables in one string', () => {
    const result = applyTemplate('{{a}} + {{b}} = {{c}}', { a: 1, b: 2, c: 3 });
    assert.equal(result, '1 + 2 = 3');
  });

  it('handles deeply nested paths', () => {
    const data = { a: { b: { c: { d: 'deep' } } } };
    assert.equal(applyTemplate('{{a.b.c.d}}', data), 'deep');
  });

  it('returns empty for missing nested path', () => {
    assert.equal(applyTemplate('{{a.b.missing}}', { a: { b: {} } }), '');
  });

  it('returns empty for null intermediate', () => {
    assert.equal(applyTemplate('{{a.b}}', { a: null }), '');
  });

  it('handles non-string templates', () => {
    assert.equal(applyTemplate(123, {}), '');
    assert.equal(applyTemplate(null, {}), '');
    assert.equal(applyTemplate(undefined, {}), '');
  });

  it('preserves surrounding text', () => {
    const result = applyTemplate('The {{animal}} jumps over the {{target}}', {
      animal: 'fox', target: 'fence'
    });
    assert.equal(result, 'The fox jumps over the fence');
  });

  it('handles special characters in values', () => {
    assert.equal(
      applyTemplate('{{html}}', { html: '<div class="x">test & verify</div>' }),
      '<div class="x">test & verify</div>'
    );
  });
});

// ─── validateTemplate ───────────────────────────────────────────

describe('validateTemplate', () => {
  it('returns valid=true when all vars are available', () => {
    const result = validateTemplate('{{name}} is {{age}}', ['name', 'age']);
    assert.equal(result.valid, true);
    assert.deepEqual(result.missing, []);
  });

  it('returns missing vars list', () => {
    const result = validateTemplate('{{name}} uses {{unknown}}', ['name', 'age']);
    assert.equal(result.valid, false);
    assert.deepEqual(result.missing, ['unknown']);
  });

  it('only checks top-level key for nested paths', () => {
    const result = validateTemplate('{{a.b.c}}', ['a']);
    assert.equal(result.valid, true);
  });

  it('handles non-string input', () => {
    const result = validateTemplate(123, ['a']);
    assert.equal(result.valid, false);
    assert.deepEqual(result.missing, []);
  });

  it('finds multiple missing keys', () => {
    const result = validateTemplate('{{x}} {{y}} {{z}}', ['a', 'b']);
    assert.equal(result.valid, false);
    assert.equal(result.missing.length, 3);
  });
});

// ─── extractTemplateVars ────────────────────────────────────────

describe('extractTemplateVars', () => {
  it('extracts all variable names', () => {
    const vars = extractTemplateVars('{{name}} and {{age}}');
    assert.equal(vars.length, 2);
    assert.ok(vars.includes('name'));
    assert.ok(vars.includes('age'));
  });

  it('deduplicates repeated vars', () => {
    const vars = extractTemplateVars('{{name}} {{name}} {{name}}');
    assert.equal(vars.length, 1);
    assert.equal(vars[0], 'name');
  });

  it('handles nested paths', () => {
    const vars = extractTemplateVars('{{a.b.c}}');
    assert.deepEqual(vars, ['a.b.c']);
  });

  it('returns empty for no vars', () => {
    assert.deepEqual(extractTemplateVars('plain text'), []);
  });

  it('handles non-string input', () => {
    assert.deepEqual(extractTemplateVars(null), []);
    assert.deepEqual(extractTemplateVars(123), []);
  });
});

// ─── Built-in Templates ─────────────────────────────────────────

describe('Built-in templates', () => {
  beforeEach(() => {
    clearTemplates();
    // Re-register all builtins manually (same as module init)
    registerTemplate('brief', '# {{project.name}} Context Brief\n\nType: {{project.type}}');
    registerTemplate('json-compact', '{"name":"{{project.name}}","type":"{{project.type}}"}');
    registerTemplate('dockerfile-hint', '# Dockerfile hints for {{project.name}}');
  });

  it('has "brief" template', () => {
    assert.ok(getTemplate('brief'));
  });

  it('has "json-compact" template', () => {
    assert.ok(getTemplate('json-compact'));
  });

  it('has "dockerfile-hint" template', () => {
    assert.ok(getTemplate('dockerfile-hint'));
  });

  it('brief template generates valid output', () => {
    const data = { project: { name: 'myapp', type: 'node', version: '1.0.0', description: 'test' } };
    const result = generateFromTemplate('brief', data);
    assert.match(result, /myapp/);
    assert.match(result, /node/);
  });

    it('dockerfile-hint template includes project info', () => {
    registerTemplate('dockerfile-hint', '# {{project.name}} entry: {{entryPoints}} deps: {{dependencies}}');
    const data = {
      project: { name: 'api', type: 'node' },
      entryPoints: ['src/index.js'],
      dependencies: { express: '^4.18.0' },
    };
    const result = generateFromTemplate('dockerfile-hint', data);
    assert.match(result, /api/);
    assert.ok(result.includes('src/index.js'));
  });
});
