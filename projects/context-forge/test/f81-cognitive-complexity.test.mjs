import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { analyzeCognitiveComplexity, formatCognitiveComplexityReport } from '../context-forge.mjs';

describe('F81: analyzeCognitiveComplexity()', () => {
  let tmpDir;

  before(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'f81-'));
  });

  after(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  function makeFile(name, content) {
    const filePath = path.join(tmpDir, name);
    fs.writeFileSync(filePath, content);
    return { path: filePath, content };
  }

  it('returns zero-score result for empty file list', () => {
    const result = analyzeCognitiveComplexity([]);
    assert.equal(result.stats.totalFunctions, 0);
    assert.equal(result.score, 100);
    assert.equal(result.grade, 'A');
  });

  it('returns grade A for simple flat functions', () => {
    const files = [makeFile('simple.js', `
      function add(a, b) {
        return a + b;
      }
      function greet(name) {
        return 'hello ' + name;
      }
    `)];
    const result = analyzeCognitiveComplexity(files);
    assert.equal(result.stats.totalFunctions, 2);
    assert.equal(result.grade, 'A');
    assert.equal(result.issues.length, 0);
  });

  it('detects nested if-statements as more complex than flat ones', () => {
    const nested = [makeFile('nested.js', `
      function process(data) {
        if (data) {
          if (data.type) {
            if (data.type === 'A') {
              return 1;
            }
          }
        }
      }
    `)];
    const flat = [makeFile('flat.js', `
      function process(data) {
        if (!data) return 0;
        if (!data.type) return 0;
        if (data.type === 'A') return 1;
      }
    `)];
    const nestedResult = analyzeCognitiveComplexity(nested);
    const flatResult = analyzeCognitiveComplexity(flat);
    // Nested 3-deep: 1 + (1+1) + (1+2) = 6
    // Flat 3 guards: 1 + 1 + 1 = 3
    assert.ok(nestedResult.stats.maxCognitiveComplexity > flatResult.stats.maxCognitiveComplexity,
      `nested (${nestedResult.stats.maxCognitiveComplexity}) should be > flat (${flatResult.stats.maxCognitiveComplexity})`);
  });

  it('counts logical operators as complexity', () => {
    const files = [makeFile('logical.js', `
      function check(a, b, c) {
        if (a && b || c) {
          return true;
        }
      }
    `)];
    const result = analyzeCognitiveComplexity(files);
    // if=1+nesting(0), &&=1, ||=1 → total ≥ 3
    assert.ok(result.stats.maxCognitiveComplexity >= 3,
      `expected >= 3, got ${result.stats.maxCognitiveComplexity}`);
  });

  it('counts ternary operators', () => {
    const files = [makeFile('ternary.js', `
      function getValue(x) {
        return x > 0 ? 'positive' : 'negative';
      }
    `)];
    const result = analyzeCognitiveComplexity(files);
    assert.ok(result.stats.maxCognitiveComplexity >= 1,
      `ternary should add complexity, got ${result.stats.maxCognitiveComplexity}`);
  });

  it('detects for and while loops', () => {
    const files = [makeFile('loops.js', `
      function iterate(arr) {
        for (let i = 0; i < arr.length; i++) {
          while (arr[i] > 0) {
            arr[i]--;
          }
        }
      }
    `)];
    const result = analyzeCognitiveComplexity(files);
    // for: 1+nesting(0)=1, while: 1+nesting(1)=2 → total 3
    assert.ok(result.stats.maxCognitiveComplexity >= 3,
      `nested loops should have complexity >= 3, got ${result.stats.maxCognitiveComplexity}`);
  });

  it('detects switch/case', () => {
    const files = [makeFile('switch.js', `
      function handle(type) {
        switch (type) {
          case 'a':
            return 1;
          case 'b':
            return 2;
          default:
            return 0;
        }
      }
    `)];
    const result = analyzeCognitiveComplexity(files);
    assert.ok(result.stats.maxCognitiveComplexity >= 2,
      `switch with cases should have complexity >= 2, got ${result.stats.maxCognitiveComplexity}`);
  });

  it('detects catch blocks as complexity', () => {
    const files = [makeFile('trycatch.js', `
      function risky() {
        try {
          doWork();
        } catch (err) {
          handleError(err);
        }
      }
    `)];
    const result = analyzeCognitiveComplexity(files);
    assert.ok(result.stats.maxCognitiveComplexity >= 1,
      `catch should add complexity, got ${result.stats.maxCognitiveComplexity}`);
  });

  it('flags high-complexity functions as issues', () => {
    const files = [makeFile('complex.js', `
      function bigLogic(a, b, c, d, e, f, g) {
        if (a) {
          if (b) {
            if (c) {
              if (d) {
                if (e) {
                  if (f) {
                    if (g) {
                      return 'deep';
                    }
                  }
                }
              }
            }
          }
        }
      }
    `)];
    const result = analyzeCognitiveComplexity(files);
    // 7 nested ifs: 1+2+3+4+5+6+7 = 28 (>= 20 → high)
    assert.ok(result.issues.length >= 1, 'should flag deep nesting');
    assert.equal(result.issues[0].severity, 'high');
    assert.equal(result.issues[0].function, 'bigLogic');
  });

  it('assigns grade F for extremely complex code', () => {
    const files = [makeFile('nightmare.js', `
      function nightmare(a, b, c, d, e, f, g) {
        if (a) {
          if (b) {
            for (let i = 0; i < c; i++) {
              while (d) {
                if (e && f || g) {
                  switch (a) {
                    case 1:
                      if (b > 0) return 1;
                    case 2:
                      return 2;
                  }
                }
              }
            }
          }
        }
      }
    `)];
    const result = analyzeCognitiveComplexity(files);
    assert.ok(result.grade === 'D' || result.grade === 'E' || result.grade === 'F',
      `expected D/E/F for nightmare, got ${result.grade} (score ${result.score})`);
  });

  it('does not count simple linear code as complex', () => {
    const files = [makeFile('linear.js', `
      function pipeline(data) {
        const step1 = transform(data);
        const step2 = filter(step1);
        const step3 = enrich(step2);
        const step4 = validate(step3);
        const step5 = format(step4);
        return step5;
      }
    `)];
    const result = analyzeCognitiveComplexity(files);
    assert.equal(result.stats.maxCognitiveComplexity, 0);
    assert.equal(result.grade, 'A');
    assert.equal(result.issues.length, 0);
  });

  it('detects arrow functions', () => {
    const files = [makeFile('arrow.js', `
      const compute = (x) => {
        if (x > 10) {
          if (x > 100) {
            return 'huge';
          }
          return 'big';
        }
        return 'small';
      };
    `)];
    const result = analyzeCognitiveComplexity(files);
    assert.ok(result.stats.totalFunctions >= 1, 'should detect arrow function');
    assert.ok(result.stats.maxCognitiveComplexity >= 2,
      `nested if in arrow should be >= 2, got ${result.stats.maxCognitiveComplexity}`);
  });

  it('detects recursion', () => {
    const files = [makeFile('recursive.js', `
      function fibonacci(n) {
        if (n <= 1) return n;
        return fibonacci(n - 1) + fibonacci(n - 2);
      }
    `)];
    const result = analyzeCognitiveComplexity(files);
    // if=1, two recursive calls=+2 → total ≥ 3
    assert.ok(result.stats.maxCognitiveComplexity >= 3,
      `recursion should add complexity >= 3, got ${result.stats.maxCognitiveComplexity}`);
  });

  it('skips test files', () => {
    const files = [
      makeFile('code.js', `
        function simple(x) {
          if (x) { return 1; }
          return 0;
        }
      `),
      makeFile('code.test.js', `
        function nightmare(a) {
          if (a) { if (a) { if (a) { if (a) { if (a) { return 'deep'; } } } } }
        }
      `),
    ];
    const result = analyzeCognitiveComplexity(files);
    // Only code.js should be analyzed, not code.test.js
    assert.equal(result.stats.totalFunctions, 1);
    assert.equal(result.issues.length, 0);
  });

  it('skips non-JS files', () => {
    const files = [
      makeFile('code.py', `
def nightmare(a):
    if a:
        if a:
            if a:
                return 'deep'
    return 'flat'
      `),
    ];
    const result = analyzeCognitiveComplexity(files);
    assert.equal(result.stats.totalFunctions, 0);
  });

  it('sorts issues by complexity descending', () => {
    const files = [makeFile('multi.js', `
      function simple() { return 1; }
      function medium(x) {
        if (x) { if (x) { if (x) { return 1; } } }
      }
      function complex(a) {
        if (a) { if (a) { if (a) { if (a) { if (a) { if (a) { return 1; } } } } } }
      }
    `)];
    const result = analyzeCognitiveComplexity(files);
    if (result.issues.length >= 2) {
      assert.ok(result.issues[0].complexity >= result.issues[1].complexity,
        'issues should be sorted by complexity descending');
    }
  });

  // === formatCognitiveComplexityReport ===

  describe('formatCognitiveComplexityReport()', () => {
    it('formats a report with all sections', () => {
      const result = {
        stats: {
          totalFunctions: 10,
          complexFunctions: 2,
          veryComplexFunctions: 1,
          avgCognitiveComplexity: 7.5,
          maxCognitiveComplexity: 25,
        },
        issues: [
          { function: 'bigFn', file: 'src/big.js', line: 42, complexity: 25, severity: 'high' },
          { function: 'medFn', file: 'src/med.js', line: 10, complexity: 12, severity: 'medium' },
        ],
        score: 60,
        grade: 'C',
      };
      const report = formatCognitiveComplexityReport(result);
      assert.ok(report.includes('🧠 Cognitive Complexity'));
      assert.ok(report.includes('Health Score: 60/100'));
      assert.ok(report.includes('Total functions: 10'));
      assert.ok(report.includes('bigFn'));
      assert.ok(report.includes('Cognitive Complexity Differs'));
    });

    it('handles empty results', () => {
      const result = {
        stats: {
          totalFunctions: 0,
          complexFunctions: 0,
          veryComplexFunctions: 0,
          avgCognitiveComplexity: 0,
          maxCognitiveComplexity: 0,
        },
        issues: [],
        score: 100,
        grade: 'A',
      };
      const report = formatCognitiveComplexityReport(result);
      assert.ok(report.includes('No overly complex functions'));
    });

    it('truncates long issue lists', () => {
      const issues = [];
      for (let i = 0; i < 30; i++) {
        issues.push({
          function: `fn${i}`,
          file: `f${i}.js`,
          line: i,
          complexity: 10 + i,
          severity: 'medium',
        });
      }
      const result = {
        stats: {
          totalFunctions: 30,
          complexFunctions: 30,
          veryComplexFunctions: 15,
          avgCognitiveComplexity: 15,
          maxCognitiveComplexity: 39,
        },
        issues,
        score: 40,
        grade: 'D',
      };
      const report = formatCognitiveComplexityReport(result);
      assert.ok(report.includes('...and 10 more'));
    });
  });
});

describe('F81: cognitive complexity — labels & recursion', () => {
  const mk = (name, content) => ({ path: name, content });

  it('scores labeled continue higher than plain continue', () => {
    const labeled = [mk('labeled.js', `
      function find(matrix) {
        outer: for (const row of matrix) {
          for (const cell of row) {
            if (cell > 3) continue outer;
          }
        }
        return -1;
      }
    `)];
    const plain = [mk('plain.js', `
      function find(matrix) {
        for (const row of matrix) {
          for (const cell of row) {
            if (cell > 3) continue;
          }
        }
        return -1;
      }
    `)];
    const lr = analyzeCognitiveComplexity(labeled);
    const pr = analyzeCognitiveComplexity(plain);
    assert.ok(lr.stats.maxCognitiveComplexity > pr.stats.maxCognitiveComplexity,
      `labeled ${lr.stats.maxCognitiveComplexity} should exceed plain ${pr.stats.maxCognitiveComplexity}`);
  });

  it('adds +1 for direct recursion', () => {
    const files = [mk('rec.js', `
      function fact(n) {
        if (n <= 1) return 1;
        return n * fact(n - 1);
      }
    `)];
    const result = analyzeCognitiveComplexity(files);
    // if (+1) + recursion (+1) = 2
    assert.ok(result.stats.maxCognitiveComplexity >= 2,
      `expected >= 2, got ${result.stats.maxCognitiveComplexity}`);
  });

  it('does not count function declaration or assignment shadowing as recursion', () => {
    const files = [mk('shadow.js', `
      function fact(n) {
        const fact = prepare(n);
        return fact;
      }
    `)];
    const result = analyzeCognitiveComplexity(files);
    // only if/prepare-call contributes nothing recursion-wise; const fact = ... has prevToken 'const' anyway
    assert.equal(result.issues.length, 0);
  });
});
