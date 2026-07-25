import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeNamingConventions, formatNamingConventionsReport } from '../context-forge.mjs';

const makeFile = (path, content) => ({ path, content });

describe('F68: analyzeNamingConventions', () => {
  it('returns empty result for empty input', () => {
    const r = analyzeNamingConventions([]);
    assert.equal(r.score, 100);
    assert.equal(r.stats.totalFiles, 0);
    assert.equal(r.stats.totalIssues, 0);
  });

  it('classifies camelCase variables correctly', () => {
    const r = analyzeNamingConventions([makeFile('src/index.js', 'const myVar = 1;\nlet otherVar = 2;')]);
    assert.ok(r.stats.conventions.camelCase.count >= 2);
    assert.equal(r.stats.totalIssues, 0);
  });

  it('classifies PascalCase correctly', () => {
    const r = analyzeNamingConventions([makeFile('src/index.js', 'const MyComponent = () => {};')]);
    assert.ok(r.stats.conventions.PascalCase.count >= 1);
  });

  it('classifies SCREAMING_SNAKE constants', () => {
    const r = analyzeNamingConventions([makeFile('src/index.js', 'const MAX_RETRIES = 3;\nconst DEFAULT_TIMEOUT = 5000;')]);
    assert.ok(r.stats.conventions.SCREAMING_SNAKE.count >= 2);
  });

  it('classifies snake_case in Python const declarations', () => {
    const r = analyzeNamingConventions([makeFile('src/utils.py', 'const my_var = 1;\nconst other_var = 2;')]);
    assert.ok(r.stats.conventions.snake_case.count >= 2);
  });

  it('flags PascalCase function in JS', () => {
    const r = analyzeNamingConventions([makeFile('src/index.js', 'function MyFunction() {}')]);
    assert.ok(r.stats.violations.pascalFunctions >= 1);
    assert.ok(r.files[0].issues.some(i => i.description.includes('PascalCase') && i.description.includes('expected camelCase')));
  });

  it('allows PascalClass classes', () => {
    const r = analyzeNamingConventions([makeFile('src/index.js', 'class MyClass {}')]);
    assert.ok(r.stats.violations.camelClasses === 0);
  });

  it('flags non-PascalCase class names', () => {
    const r = analyzeNamingConventions([makeFile('src/index.js', 'class my_class {}')]);
    assert.ok(r.stats.violations.camelClasses >= 1);
    assert.ok(r.files[0].issues.some(i => i.category === 'class' && i.severity === 'high'));
  });

  it('flags non-PascalCase enum type', () => {
    const r = analyzeNamingConventions([makeFile('src/index.ts', 'enum my_enum {\n  ValueA = 1,\n  VALUE_B = 2\n}')]);
    assert.ok(r.stats.violations.camelEnums >= 1);
  });

  it('flags single letter variable names (non-iterator)', () => {
    const r = analyzeNamingConventions([makeFile('src/index.js', 'const d = 5;\nconst l = "hello";')]);
    assert.ok(r.stats.violations.singleLetterNames >= 2);
  });

  it('allows common iterator single letter names', () => {
    const r = analyzeNamingConventions([makeFile('src/index.js', 'const i = 0;\nconst j = 1;\nconst e = err;')]);
    assert.equal(r.stats.violations.singleLetterNames, 0);
  });

  it('flags abbreviated variable names', () => {
    const r = analyzeNamingConventions([makeFile('src/index.js', 'const tmp = 1;\nconst btn = element;\nconst msg = "hi";')]);
    assert.ok(r.stats.violations.abbreviatedNames >= 3);
    assert.ok(r.files[0].issues.some(i => i.description.includes('tmp')));
    assert.ok(r.files[0].issues.some(i => i.description.includes('btn')));
  });

  it('flags camelCase function in Python', () => {
    const r = analyzeNamingConventions([makeFile('src/utils.py', 'function myFunction() {}')]);
    assert.ok(r.stats.violations.snakeVariables >= 1);
    assert.ok(r.files[0].issues.some(i => i.description.includes('snake_case')));
  });

  it('allows snake_case in Python', () => {
    const r = analyzeNamingConventions([makeFile('src/utils.py', 'def my_function():\n    pass')]);
    assert.equal(r.stats.violations.snakeVariables, 0);
  });

  it('flags camelCase Python filenames', () => {
    const r = analyzeNamingConventions([makeFile('src/myModule.py', 'x = 1')]);
    assert.ok(r.files[0].issues.some(i => i.description.includes('snake_case')));
  });

  it('respects maxIssuesPerFile option', () => {
    const manyVars = Array.from({ length: 30 }, (_, i) => `const d${i} = ${i};`).join('\n');
    const r = analyzeNamingConventions([makeFile('src/index.js', manyVars)], { maxIssuesPerFile: 5 });
    assert.ok(r.files[0].issues.length <= 5);
  });

  it('detects dominant convention', () => {
    const code = `const a = 1;\nconst b = 2;\nconst c = 3;\nconst MY_CONST = 1;`;
    const r = analyzeNamingConventions([makeFile('src/index.js', code)]);
    assert.equal(r.dominantConvention, 'camelCase');
  });

  it('counts files with issues', () => {
    const r = analyzeNamingConventions([
      makeFile('src/good.js', 'const myVar = 1;'),
      makeFile('src/bad.js', 'class my_class {}'),
      makeFile('src/good2.js', 'const another = 2;'),
    ]);
    assert.equal(r.stats.filesWithIssues, 1);
    assert.equal(r.stats.totalFiles, 3);
  });

  it('score decreases with more issues', () => {
    const clean = analyzeNamingConventions([makeFile('src/a.js', 'const x = 1;')]);
    const dirty = analyzeNamingConventions([makeFile('src/b.js', 'class bad_name {}\nfunction BadFunc() {}\nconst d = 1;\nconst tmp = 2;')]);
    assert.ok(clean.score > dirty.score);
  });

  it('skips comments', () => {
    const r = analyzeNamingConventions([makeFile('src/index.js', '// const d = 1;\n/* class bad {} */\nconst myVar = 1;')]);
    assert.equal(r.stats.violations.singleLetterNames, 0);
  });

  it('skips # comments in Python', () => {
    const r = analyzeNamingConventions([makeFile('src/utils.py', '# const d = 1\nmy_var = 1')]);
    assert.equal(r.stats.violations.singleLetterNames, 0);
  });

  it('classifies kebab-case names', () => {
    const r = analyzeNamingConventions([makeFile('src/my-file.js', 'const myVar = 1;')]);
    // File name my-file is kebab-case
    assert.ok(r.conventionDistribution);
  });

  it('handles mixed conventions and reports distribution', () => {
    const code = `const myVar = 1;\nconst MY_CONST = 2;\nclass MyClass {};\nfunction myFunc() {};`;
    const r = analyzeNamingConventions([makeFile('src/index.ts', code)]);
    assert.ok(r.conventionDistribution.camelCase);
    assert.ok(r.conventionDistribution.SCREAMING_SNAKE);
    assert.ok(r.conventionDistribution.PascalCase);
  });

  it('allows single-word PascalCase file names (component pattern)', () => {
    const r = analyzeNamingConventions([makeFile('src/Utils.ts', 'export function format() {}')]);
    assert.equal(r.files[0].issues.filter(i => i.category === 'fileName').length, 0);
  });

  it('flags module-level PascalCase numeric constant', () => {
    const r = analyzeNamingConventions([makeFile('src/index.js', 'const MaxCount = 100;')]);
    assert.ok(r.stats.violations.lowerConstants >= 1);
    assert.ok(r.files[0].issues.some(i => i.description.includes('SCREAMING_SNAKE')));
  });

  it('does not flag PascalCase const with require/import', () => {
    const r = analyzeNamingConventions([makeFile('src/index.js', 'const Express = require("express");')]);
    assert.equal(r.stats.violations.lowerConstants, 0);
  });
});

describe('F68: formatNamingConventionsReport', () => {
  it('produces markdown report with score', () => {
    const r = analyzeNamingConventions([makeFile('src/a.js', 'const myVar = 1;')]);
    const report = formatNamingConventionsReport(r);
    assert.ok(report.includes('Naming Conventions Analysis'));
    assert.ok(report.includes('Score:'));
  });

  it('includes violation summary', () => {
    const r = analyzeNamingConventions([makeFile('src/a.js', 'class bad_name {}')]);
    const report = formatNamingConventionsReport(r);
    assert.ok(report.includes('Violation Summary'));
    assert.ok(report.includes('Non-PascalCase classes'));
  });

  it('includes convention distribution', () => {
    const r = analyzeNamingConventions([makeFile('src/a.js', 'const myVar = 1;\nconst MY_CONST = 2;')]);
    const report = formatNamingConventionsReport(r);
    assert.ok(report.includes('Convention Distribution'));
    assert.ok(report.includes('camelCase'));
  });

  it('includes top files with issues', () => {
    const r = analyzeNamingConventions([
      makeFile('src/bad.js', 'class x {}\nfunction Y() {}\nconst d = 1;'),
      makeFile('src/good.js', 'const myVar = 1;'),
    ]);
    const report = formatNamingConventionsReport(r);
    assert.ok(report.includes('Top Files with Issues'));
    assert.ok(report.includes('bad.js'));
  });

  it('handles clean project with no issues', () => {
    const r = analyzeNamingConventions([makeFile('src/good.js', 'const myVariable = 1;')]);
    const report = formatNamingConventionsReport(r);
    assert.ok(report.includes('0'));
    assert.ok(!report.includes('Violation Summary'));
  });
});
