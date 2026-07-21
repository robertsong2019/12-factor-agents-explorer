import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeMaturity, formatMaturityReport } from '../context-forge.mjs';

describe('F51: analyzeMaturity', () => {
  it('returns zero score for empty project', () => {
    const result = analyzeMaturity({});
    assert.ok(result.overallScore >= 0);
    assert.ok(result.grade);
    assert.ok(result.maxScore === 100);
  });

  it('scores full marks for a well-configured project', () => {
    const info = {
      dependencies: { lodash: '4.17.21' },
      devDependencies: { jest: '29.0.0' },
      scripts: { build: 'tsc', test: 'jest', dev: 'node .', lint: 'eslint .', format: 'prettier .' },
      license: 'MIT',
      configFiles: [
        'README.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'LICENSE',
        '.eslintrc.json', '.prettierrc', 'tsconfig.json', '.gitignore', '.editorconfig',
        'jest.config.js', 'test/', '.github/workflows/ci.yml', 'codecov.yml',
      ],
    };
    const result = analyzeMaturity(info);
    assert.ok(result.overallScore >= 80, `Expected >= 80, got ${result.overallScore}`);
    assert.ok(['A', 'B'].includes(result.grade));
  });

  it('penalizes missing test framework', () => {
    const result = analyzeMaturity({ configFiles: ['README.md'] });
    assert.equal(result.signals.testing.hasFramework, false);
    assert.ok(result.signals.testing.score < 15);
    assert.ok(result.recommendations.some(r => r.area === 'testing' && r.priority === 'high'));
  });

  it('penalizes missing README', () => {
    const result = analyzeMaturity({ configFiles: [] });
    assert.equal(result.signals.documentation.hasReadme, false);
    assert.ok(result.recommendations.some(r => r.area === 'documentation'));
  });

  it('penalizes missing license', () => {
    const result = analyzeMaturity({ configFiles: ['README.md'] });
    assert.equal(result.signals.documentation.hasLicense, false);
    assert.ok(result.recommendations.some(r => r.message.includes('LICENSE')));
  });

  it('detects CI configuration', () => {
    const result = analyzeMaturity({ configFiles: ['.github/workflows/ci.yml', 'README.md'] });
    assert.equal(result.signals.testing.hasCI, true);
  });

  it('detects linter configuration', () => {
    const result = analyzeMaturity({ configFiles: ['.eslintrc.json'] });
    assert.equal(result.signals.codeQuality.hasLinter, true);
  });

  it('detects formatter configuration', () => {
    const result = analyzeMaturity({ configFiles: ['.prettierrc'] });
    assert.equal(result.signals.codeQuality.hasFormatter, true);
  });

  it('detects type checking config', () => {
    const result = analyzeMaturity({ configFiles: ['tsconfig.json'] });
    assert.equal(result.signals.codeQuality.hasTypeChecking, true);
  });

  it('penalizes unpinned dependencies', () => {
    const result = analyzeMaturity({
      dependencies: { lodash: '^4.17.21', express: '~4.18.0' },
      devDependencies: { jest: '>=29.0.0' },
    });
    assert.ok(result.signals.dependencyHealth.pinnedRatio < 0.5);
    assert.ok(result.recommendations.some(r => r.area === 'dependencies'));
  });

  it('rewards pinned dependencies', () => {
    const result = analyzeMaturity({
      dependencies: { lodash: '4.17.21', express: '4.18.2' },
    });
    assert.equal(result.signals.dependencyHealth.pinnedRatio, 1);
    assert.equal(result.signals.dependencyHealth.score, 20);
  });

  it('checks for build/test/dev/lint/format scripts', () => {
    const result = analyzeMaturity({
      scripts: { build: 'tsc', test: 'jest', dev: 'nodemon', lint: 'eslint', format: 'prettier' },
    });
    assert.equal(result.signals.projectStructure.hasBuildScript, true);
    assert.equal(result.signals.projectStructure.hasTestScript, true);
    assert.equal(result.signals.projectStructure.hasDevScript, true);
    assert.equal(result.signals.projectStructure.hasLintScript, true);
    assert.equal(result.signals.projectStructure.hasFormatScript, true);
  });

  it('sorts recommendations by priority', () => {
    const result = analyzeMaturity({ configFiles: [] });
    const priorities = result.recommendations.map(r => r.priority);
    const priOrder = { high: 0, medium: 1, low: 2 };
    for (let i = 1; i < priorities.length; i++) {
      assert.ok(priOrder[priorities[i]] >= priOrder[priorities[i - 1]]);
    }
  });

  it('generates summary string', () => {
    const result = analyzeMaturity({});
    assert.ok(typeof result.summary === 'string');
    assert.ok(result.summary.includes('maturity'));
    assert.ok(result.summary.includes('/100'));
  });

  it('handles info with pkg nested structure', () => {
    const result = analyzeMaturity({
      pkg: {
        dependencies: { lodash: '4.17.21' },
        scripts: { test: 'jest' },
      },
      configFiles: ['README.md'],
    });
    assert.ok(result.signals.dependencyHealth.depCount === 1);
    assert.equal(result.signals.projectStructure.hasTestScript, true);
  });

  it('computes grade correctly', () => {
    // Max project
    const full = analyzeMaturity({
      dependencies: { a: '1.0.0' },
      devDependencies: { b: '2.0.0' },
      scripts: { build: 'x', test: 'x', dev: 'x', lint: 'x', format: 'x' },
      license: 'MIT',
      configFiles: [
        'README.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'LICENSE',
        '.eslintrc', '.prettierrc', 'tsconfig.json', '.gitignore', '.editorconfig',
        'jest.config.js', 'tests/', '.github/workflows/ci.yml', 'codecov.yml',
      ],
    });
    assert.ok(['A', 'B'].includes(full.grade), `Expected A/B, got ${full.grade}`);
  });
});

describe('F51: formatMaturityReport', () => {
  it('handles null result', () => {
    const report = formatMaturityReport(null);
    assert.ok(report.includes('No data'));
  });

  it('includes grade and score', () => {
    const report = formatMaturityReport({
      overallScore: 75,
      grade: 'C',
      maxScore: 100,
      achievedScore: 75,
      signals: {
        testing: { score: 15, max: 20, status: 'fair' },
        documentation: { score: 10, max: 20, status: 'fair' },
      },
      recommendations: [],
    });
    assert.ok(report.includes('C'));
    assert.ok(report.includes('75/100'));
  });

  it('includes signal table with status', () => {
    const report = formatMaturityReport({
      overallScore: 50,
      grade: 'D',
      maxScore: 100,
      achievedScore: 50,
      signals: {
        testing: { score: 10, max: 20, status: 'fair' },
        codeQuality: { score: 5, max: 20, status: 'poor' },
        documentation: { score: 20, max: 20, status: 'good' },
      },
      recommendations: [],
    });
    assert.ok(report.includes('Testing'));
    assert.ok(report.includes('fair'));
    assert.ok(report.includes('🟡'));
    assert.ok(report.includes('🔴'));
    assert.ok(report.includes('✅'));
  });

  it('lists recommendations with priority emojis', () => {
    const report = formatMaturityReport({
      overallScore: 30,
      grade: 'F',
      maxScore: 100,
      achievedScore: 30,
      signals: {},
      recommendations: [
        { area: 'testing', priority: 'high', message: 'Add tests' },
        { area: 'docs', priority: 'medium', message: 'Add README' },
      ],
    });
    assert.ok(report.includes('🔴'));
    assert.ok(report.includes('HIGH'));
    assert.ok(report.includes('Add tests'));
  });

  it('shows all-clear when no recommendations', () => {
    const report = formatMaturityReport({
      overallScore: 100,
      grade: 'A',
      maxScore: 100,
      achievedScore: 100,
      signals: {},
      recommendations: [],
    });
    assert.ok(report.includes('No critical improvements'));
  });
});
