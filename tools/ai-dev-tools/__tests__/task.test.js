import { loadTemplate, generateTaskContent } from '../commands/task.js';

// Real-module tests (replaced previous suite that tested self-defined fixtures)
describe('task command — real template engine', () => {
  const ALL_TEMPLATES = [
    'code-review', 'refactor', 'test-generation', 'documentation',
    'api-design', 'bug-fix', 'feature-implementation', 'performance-optimization'
  ];

  describe('loadTemplate', () => {
    test('loads every template advertised by --list', async () => {
      for (const name of ALL_TEMPLATES) {
        const t = await loadTemplate(name);
        expect(t).toBeDefined();
        expect(t.name).toBe(name);
        expect(t.template).toBeTruthy();
        expect(Array.isArray(t.variables)).toBe(true);
        expect(t.variables.length).toBeGreaterThan(0);
      }
    });

    test('every {placeholder} in template body is declared in variables', async () => {
      for (const name of ALL_TEMPLATES) {
        const t = await loadTemplate(name);
        const placeholders = [...t.template.matchAll(/\{(\w+)\}/g)].map(m => m[1]);
        const declared = new Set(t.variables);
        placeholders.forEach(p => {
          expect(declared.has(p)).toBe(true);
        });
      }
    });

    test('unknown template returns undefined (not a throw)', async () => {
      expect(await loadTemplate('no-such-template')).toBeUndefined();
    });
  });

  describe('generateTaskContent', () => {
    test('substitutes all declared variables', async () => {
      const t = await loadTemplate('code-review');
      const out = generateTaskContent(t, { file_path: 'src/app.js', review_type: 'security' });
      expect(out).toContain('src/app.js');
      expect(out).toContain('security');
      expect(out).not.toContain('{file_path}');
      expect(out).not.toContain('{review_type}');
    });

    test('replaces every occurrence, not just the first', async () => {
      const t = { name: 'dup', variables: ['x'], template: '{x} and {x} again' };
      expect(generateTaskContent(t, { x: 'A' })).toBe('A and A again');
    });

    test('dollar-sign replacement patterns in values are NOT interpreted ($& bugfix)', () => {
      const t = { name: 'shell', variables: ['cmd'], template: 'run: {cmd}' };
      // Before fix: value '$&' would be replaced by the matched text ('{cmd}')
      expect(generateTaskContent(t, { cmd: '$&' })).toBe('run: $&');
      expect(generateTaskContent(t, { cmd: "$`" })).toBe('run: $`');
      expect(generateTaskContent(t, { cmd: "$'" })).toBe("run: $'");
      expect(generateTaskContent(t, { cmd: 'cost: $5 & $10' })).toBe('cost: $5 & $10' && 'run: cost: $5 & $10');
    });

    test('non-string values are stringified, not corrupted', () => {
      const t = { name: 'num', variables: ['n'], template: 'count: {n}' };
      expect(generateTaskContent(t, { n: 42 })).toBe('count: 42');
    });

    test('undeclared placeholders are left untouched', () => {
      const t = { name: 'partial', variables: ['a'], template: '{a} {b}' };
      expect(generateTaskContent(t, { a: 'X' })).toBe('X {b}');
    });
  });
});
