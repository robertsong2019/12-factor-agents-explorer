import { test } from 'node:test';
import assert from 'node:assert/strict';
import { detectQualitySignals, formatQualitySignals } from '../context-forge.mjs';

test('F26: detectQualitySignals — TypeScript detection', () => {
  const info = {
    dependencies: { typescript: '^5.0.0' },
    configFiles: ['tsconfig.json'],
  };
  const langs = new Map([['TypeScript', 20]]);
  const result = detectQualitySignals(info, langs, { allImports: [], imports: new Map() }, [], { 'tsconfig.json': {} });

  assert.ok(result.signals.typesafety.score >= 50);
  assert.ok(result.signals.typesafety.indicators.some(i => i.includes('TypeScript')));
});

test('F26: detectQualitySignals — testing framework detection', () => {
  const info = {
    dependencies: {},
    devDependencies: { jest: '^29.0.0' },
    configFiles: ['jest.config.js'],
  };
  const langs = new Map([['JavaScript', 10]]);
  const importData = {
    imports: new Map([
      ['test/a.test.js', ['jest']],
      ['test/b.test.js', ['jest']],
    ]),
    allImports: ['jest'],
  };
  const result = detectQualitySignals(info, langs, importData, [], {});

  assert.ok(result.signals.testing.score > 0);
  assert.ok(result.signals.testing.indicators.some(i => i.includes('jest')));
  assert.ok(result.signals.testing.indicators.some(i => i.includes('test files')));
});

test('F26: detectQualitySignals — linting detection', () => {
  const info = {
    devDependencies: { eslint: '^8.0.0' },
    configFiles: ['.eslintrc.json'],
  };
  const langs = new Map([['JavaScript', 10]]);
  const result = detectQualitySignals(info, langs, { allImports: [], imports: new Map() }, [], { '.eslintrc': {} });

  assert.ok(result.signals.linting.score >= 40);
});

test('F26: detectQualitySignals — CI/CD detection', () => {
  const info = { configFiles: ['Dockerfile', '.github/workflows/ci.yml'] };
  const langs = new Map([['JavaScript', 5]]);
  const result = detectQualitySignals(info, langs, { allImports: [], imports: new Map() }, [], { '.github/workflows': {} });

  assert.ok(result.signals.ci.score >= 40);
  assert.ok(result.signals.ci.indicators.some(i => i.includes('Docker')));
  assert.ok(result.signals.ci.indicators.some(i => i.includes('GitHub Actions')));
});

test('F26: detectQualitySignals — documentation detection', () => {
  const info = { configFiles: ['README.md', 'LICENSE', 'CHANGELOG.md'] };
  const langs = new Map([['JavaScript', 5]]);
  const result = detectQualitySignals(info, langs, { allImports: [], imports: new Map() }, [], {});

  assert.ok(result.signals.documentation.score >= 40);
  assert.ok(result.signals.documentation.indicators.some(i => i.includes('README')));
});

test('F26: detectQualitySignals — overall grade for well-equipped project', () => {
  const info = {
    dependencies: { typescript: '^5.0.0', react: '^18.0.0' },
    devDependencies: { jest: '^29.0.0', eslint: '^8.0.0', prettier: '^3.0.0' },
    configFiles: ['tsconfig.json', '.eslintrc', '.prettierrc', 'README.md', 'LICENSE', 'Dockerfile'],
  };
  const langs = new Map([['TypeScript', 30]]);
  const importData = {
    imports: new Map([
      ['test/a.test.js', ['jest']],
      ['test/b.test.js', ['jest']],
      ['test/c.test.js', ['jest']],
    ]),
    allImports: ['jest', 'react'],
  };
  const result = detectQualitySignals(info, langs, importData, [], { 'tsconfig.json': {}, '.github/workflows': {} });

  assert.ok(result.overall >= 40, `Expected overall >= 40, got ${result.overall}`);
  assert.ok(['A', 'B', 'C'].includes(result.grade), `Expected A/B/C, got ${result.grade}`);
});

test('F26: detectQualitySignals — minimal project gets low grade', () => {
  const info = { dependencies: {}, configFiles: [] };
  const langs = new Map([['JavaScript', 5]]);
  const result = detectQualitySignals(info, langs, { allImports: [], imports: new Map() }, [], {});

  assert.ok(result.overall < 30);
  assert.ok(['D', 'F'].includes(result.grade));
});

test('F26: detectQualitySignals — prettier formatting detection', () => {
  const info = { devDependencies: { prettier: '^3.0.0' }, configFiles: ['.prettierrc'] };
  const langs = new Map([['JavaScript', 5]]);
  const result = detectQualitySignals(info, langs, { allImports: [], imports: new Map() }, [], {});

  assert.ok(result.signals.formatting.score > 0);
  assert.ok(result.signals.formatting.indicators.some(i => i.includes('prettier')));
});

test('F26: formatQualitySignals — valid markdown', () => {
  const info = { devDependencies: { jest: '^29.0.0' }, configFiles: ['README.md'] };
  const langs = new Map([['JavaScript', 10]]);
  const importData = { imports: new Map([['test/a.test.js', ['jest']]]), allImports: ['jest'] };
  const result = detectQualitySignals(info, langs, importData, [], {});
  const md = formatQualitySignals(result);

  assert.ok(md.includes('# Code Quality Signals'));
  assert.ok(md.includes('Overall'));
  assert.ok(md.includes('Type Safety'));
  assert.ok(md.includes('Testing'));
});

test('F26: formatQualitySignals — progress bars', () => {
  const info = { dependencies: {} };
  const langs = new Map([['JavaScript', 5]]);
  const result = detectQualitySignals(info, langs, { allImports: [], imports: new Map() }, [], {});
  const md = formatQualitySignals(result);

  assert.ok(md.includes('█') || md.includes('░'));
});

test('F26: detectQualitySignals — scores capped at 100', () => {
  const info = {
    dependencies: { typescript: '^5.0.0' },
    devDependencies: { jest: '^29.0.0', eslint: '^8.0.0', prettier: '^3.0.0' },
    configFiles: ['tsconfig.json', '.eslintrc', '.prettierrc', 'README.md', 'LICENSE', 'CHANGELOG.md', 'Dockerfile', '.github/workflows/ci.yml'],
  };
  const langs = new Map([['TypeScript', 30]]);
  const importData = {
    imports: new Map(Array.from({ length: 50 }, (_, i) => [`test/t${i}.test.js`, ['jest']])),
    allImports: ['jest'],
  };
  const result = detectQualitySignals(info, langs, importData, [], { 'tsconfig.json': {}, '.github/workflows': {} });

  for (const { score } of Object.values(result.signals)) {
    assert.ok(score <= 100, `Score ${score} exceeds 100`);
  }
});
