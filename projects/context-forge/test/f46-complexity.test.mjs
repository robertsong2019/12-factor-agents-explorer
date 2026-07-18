import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeCodeComplexity, formatComplexityReport } from '../context-forge.mjs';
import { writeFile, mkdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

const TMP = join(tmpdir(), `cf-complexity-${Date.now()}`);

async function setup(files) {
  await mkdir(TMP, { recursive: true });
  for (const [path, content] of Object.entries(files)) {
    const full = join(TMP, path);
    await mkdir(join(full, '..'), { recursive: true });
    await writeFile(full, content);
  }
}

async function cleanup() {
  await rm(TMP, { recursive: true, force: true });
}

describe('F46: analyzeCodeComplexity', () => {
  it('counts decision points in JavaScript', async () => {
    const files = new Map([
      ['simple.js', { lang: 'JavaScript' }],
      ['complex.js', { lang: 'JavaScript' }],
    ]);
    await setup({
      'simple.js': 'const x = 1;\n',
      'complex.js': 'if (a) { for (let i=0;i<n;i++) { if (b && c) { } } }\n',
    });
    try {
      const result = await analyzeCodeComplexity(TMP, files);
      assert.equal(result.totalFiles, 2);
      const complex = result.files.find(f => f.file === 'complex.js');
      const simple = result.files.find(f => f.file === 'simple.js');
      assert.ok(complex.complexity > simple.complexity);
      // complex.js: if + for + if + && = 4 decision points + 1 = 5
      assert.ok(complex.complexity >= 5, `expected >= 5, got ${complex.complexity}`);
      // simple.js: no decisions = 1
      assert.equal(simple.complexity, 1);
    } finally { await cleanup(); }
  });

  it('counts decision points in Python', async () => {
    const files = new Map([['app.py', { lang: 'Python' }]]);
    await setup({
      'app.py': 'if x:\n  pass\nelif y:\n  pass\nelse:\n  for i in range(10):\n    if a and b:\n      pass\n',
    });
    try {
      const result = await analyzeCodeComplexity(TMP, files);
      const py = result.files[0];
      // if + elif + else + for + if + and = 6 + 1 = 7
      assert.ok(py.complexity >= 7, `expected >= 7, got ${py.complexity}`);
      assert.equal(py.lang, 'Python');
    } finally { await cleanup(); }
  });

  it('assigns correct grades', async () => {
    let code = '';
    for (let i = 0; i < 50; i++) code += `if (x${i}) { } `;
    const files = new Map([['big.js', { lang: 'JavaScript' }]]);
    await setup({ 'big.js': code });
    try {
      const result = await analyzeCodeComplexity(TMP, files);
      const big = result.files[0];
      // 50 ifs = 50 + 1 = 51 → F
      assert.equal(big.grade, 'F');
    } finally { await cleanup(); }
  });

  it('calculates density correctly', async () => {
    const content = 'const a = 1;\nconst b = 2;\nconst c = 3;\nif (a) {}\nfor (let i=0;i<2;i++){}\nconst d=4;\nconst e=5;\nconst f=6;\nconst g=7;\nconst h=8;\n';
    const files = new Map([['test.js', { lang: 'JavaScript' }]]);
    await setup({ 'test.js': content });
    try {
      const result = await analyzeCodeComplexity(TMP, files);
      const f = result.files[0];
      // 10 content lines + trailing newline = 11 split entries
      assert.equal(f.lines, 11);
      // if + for = 2 decision points + 1 = 3
      assert.equal(f.complexity, 3);
      // density = 3/11 * 100 = 27.27
      assert.equal(f.density, parseFloat((3 / 11 * 100).toFixed(2)));
    } finally { await cleanup(); }
  });

  it('sorts files by complexity descending', async () => {
    const files = new Map([
      ['low.js', { lang: 'JavaScript' }],
      ['high.js', { lang: 'JavaScript' }],
    ]);
    await setup({
      'low.js': 'const x = 1;\n',
      'high.js': 'if(a){if(b){if(c){if(d){}}}}\n',
    });
    try {
      const result = await analyzeCodeComplexity(TMP, files);
      assert.ok(result.files[0].complexity >= result.files[1].complexity);
      assert.equal(result.files[0].file, 'high.js');
    } finally { await cleanup(); }
  });

  it('skips unsupported languages', async () => {
    const files = new Map([
      ['readme.md', { lang: 'Markdown' }],
      ['data.json', { lang: 'JSON' }],
    ]);
    const result = await analyzeCodeComplexity('/tmp', files);
    assert.equal(result.totalFiles, 0);
    assert.equal(result.avgComplexity, 0);
  });

  it('computes aggregate stats', async () => {
    const files = new Map([
      ['a.js', { lang: 'JavaScript' }],
      ['b.js', { lang: 'JavaScript' }],
    ]);
    await setup({
      'a.js': 'const x=1;\n',
      'b.js': 'if(a){if(b){}}\n',
    });
    try {
      const result = await analyzeCodeComplexity(TMP, files);
      assert.equal(result.totalFiles, 2);
      assert.equal(result.totalComplexity, 4); // 1 + 3
      assert.equal(result.avgComplexity, 2);
    } finally { await cleanup(); }
  });

  it('tracks grade distribution', async () => {
    const simpleCode = 'const x = 1;\n';
    let complexCode = '';
    for (let i = 0; i < 30; i++) complexCode += `if(x${i}){}`;
    const files = new Map([
      ['simple.js', { lang: 'JavaScript' }],
      ['complex.js', { lang: 'JavaScript' }],
    ]);
    await setup({ 'simple.js': simpleCode, 'complex.js': complexCode });
    try {
      const result = await analyzeCodeComplexity(TMP, files);
      assert.ok(result.gradeDistribution.A >= 1);
      assert.ok(result.gradeDistribution.D >= 1 || result.gradeDistribution.F >= 1);
    } finally { await cleanup(); }
  });

  it('limits files in output to top 20', async () => {
    const fileMap = new Map();
    const fileContents = {};
    for (let i = 0; i < 25; i++) {
      const name = `file${i}.js`;
      fileMap.set(name, { lang: 'JavaScript' });
      fileContents[name] = `if(x${i}){}\n`;
    }
    await setup(fileContents);
    try {
      const result = await analyzeCodeComplexity(TMP, fileMap);
      assert.ok(result.files.length <= 20);
    } finally { await cleanup(); }
  });
});

describe('F46: formatComplexityReport', () => {
  it('formats a complete report', () => {
    const analysis = {
      totalFiles: 10,
      totalComplexity: 50,
      avgComplexity: 5.0,
      totalLines: 500,
      overallDensity: 10.0,
      gradeDistribution: { A: 3, B: 4, C: 2, D: 1, F: 0 },
      files: [
        { file: 'src/index.js', complexity: 15, density: 3.5, lines: 430, grade: 'C' },
        { file: 'src/utils.js', complexity: 8, density: 2.0, lines: 400, grade: 'B' },
      ],
    };
    const report = formatComplexityReport(analysis);
    assert.ok(report.includes('### Code Complexity'));
    assert.ok(report.includes('| Files analyzed | 10 |'));
    assert.ok(report.includes('| Avg complexity/file | 5 |'));
    assert.ok(report.includes('#### Grade Distribution'));
    assert.ok(report.includes('#### Top Complex Files'));
    assert.ok(report.includes('`src/index.js`'));
    assert.ok(report.includes('| C |'));
  });

  it('handles empty analysis', () => {
    const report = formatComplexityReport({ files: [], totalFiles: 0 });
    assert.ok(report.includes('No analyzable source files found'));
  });

  it('handles null input', () => {
    const report = formatComplexityReport(null);
    assert.ok(report.includes('No analyzable source files found'));
  });

  it('shows top 10 files max in table', () => {
    const files = [];
    for (let i = 0; i < 15; i++) files.push({ file: `f${i}.js`, complexity: i+1, density: 1, lines: 100, grade: 'B' });
    const report = formatComplexityReport({ totalFiles: 15, totalComplexity: 120, avgComplexity: 8, totalLines: 1500, overallDensity: 8, gradeDistribution: {A:0,B:15,C:0,D:0,F:0}, files });
    const tableRows = report.split('\n').filter(l => l.startsWith('| `f'));
    assert.ok(tableRows.length <= 10);
  });
});
