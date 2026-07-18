import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeTechDebt, formatTechDebtReport } from '../context-forge.mjs';

describe('F48: analyzeTechDebt', () => {
  it('returns zero score for no signals', () => {
    const result = analyzeTechDebt({});
    assert.equal(result.overallScore, 0);
    assert.equal(result.grade, 'A');
    assert.equal(result.items.length, 0);
    assert.equal(result.recommendations.length, 0);
  });

  it('scores TODO signals', () => {
    const result = analyzeTechDebt({
      todos: { total: 15, items: [{ priority: 'high' }, { priority: 'high' }, { priority: 'low' }] },
    });
    const todoItem = result.items.find(i => i.category.includes('TODO'));
    assert.ok(todoItem);
    assert.ok(todoItem.score > 0);
    assert.equal(todoItem.count, 15);
    assert.equal(todoItem.highPriority, 2);
  });

  it('scores dead code signals', () => {
    const result = analyzeTechDebt({
      deadCode: { unused: 10, total: 50 },
    });
    const dcItem = result.items.find(i => i.category === 'Dead Code');
    assert.ok(dcItem);
    assert.equal(dcItem.score, 20); // 10/50 = 0.2 * 100 = 20
    assert.equal(dcItem.ratio, 0.2);
  });

  it('scores complexity signals', () => {
    const result = analyzeTechDebt({
      complexity: { avgComplexity: 15, gradeDistribution: { A: 5, B: 3, C: 2, D: 4, F: 1 } },
    });
    const cxItem = result.items.find(i => i.category === 'Code Complexity');
    assert.ok(cxItem);
    assert.ok(cxItem.score > 0);
    assert.equal(cxItem.highComplexityFiles, 5); // D + F
  });

  it('scores unused dependencies', () => {
    const result = analyzeTechDebt({
      importHealth: { unusedDeps: ['lodash', 'moment', 'jquery'] },
    });
    const depItem = result.items.find(i => i.category === 'Unused Dependencies');
    assert.ok(depItem);
    assert.equal(depItem.count, 3);
    assert.ok(depItem.score >= 30);
  });

  it('scores security signals with critical severity', () => {
    const result = analyzeTechDebt({
      secrets: { total: 5, high: 2 },
    });
    const secItem = result.items[0];
    assert.ok(secItem.category.includes('Security'));
    assert.equal(secItem.highRisk, 2);
    assert.ok(secItem.severity === 'critical' || secItem.severity === 'high');
  });

  it('combines multiple signals with weights', () => {
    const result = analyzeTechDebt({
      todos: { total: 10 },
      deadCode: { unused: 5, total: 20 },
      complexity: { avgComplexity: 8, gradeDistribution: { A: 5, B: 5, C: 0, D: 0, F: 0 } },
    });
    assert.ok(result.items.length === 3);
    assert.ok(result.overallScore > 0);
    assert.ok(result.overallScore <= 100);
  });

  it('generates recommendations for high-score items', () => {
    const result = analyzeTechDebt({
      secrets: { total: 5, high: 3 },
      deadCode: { unused: 15, total: 30 },
      todos: { total: 2 },
    });
    assert.ok(result.recommendations.length >= 2);
    // Security should appear first (highest score)
    assert.ok(result.recommendations[0].includes('secret') || result.recommendations[0].includes('⚠️'));
  });

  it('skips recommendations for low-score items', () => {
    const result = analyzeTechDebt({
      todos: { total: 1 },
    });
    assert.equal(result.recommendations.length, 0);
  });

  it('assigns correct overall grade', () => {
    const lowDebt = analyzeTechDebt({ todos: { total: 1 } });
    assert.equal(lowDebt.grade, 'A');

    const highDebt = analyzeTechDebt({
      secrets: { total: 10, high: 5 },
      deadCode: { unused: 40, total: 50 },
      complexity: { avgComplexity: 30, gradeDistribution: { A: 0, B: 0, C: 0, D: 5, F: 5 } },
      todos: { total: 30, items: [{ priority: 'high' }] },
      importHealth: { unusedDeps: ['a', 'b', 'c', 'd', 'e', 'f', 'g'] },
    });
    assert.ok(['D', 'F'].includes(highDebt.grade));
    assert.ok(highDebt.overallScore >= 60);
  });

  it('counts high-priority items', () => {
    const result = analyzeTechDebt({
      secrets: { total: 3, high: 2 },
      complexity: { avgComplexity: 25, gradeDistribution: { A: 0, B: 0, C: 0, D: 3, F: 2 } },
      todos: { total: 1 },
    });
    assert.ok(result.highPriorityCount >= 2);
  });

  it('handles partial signals (only some provided)', () => {
    const result = analyzeTechDebt({
      complexity: { avgComplexity: 12, gradeDistribution: { A: 3, B: 2, C: 1, D: 0, F: 0 } },
    });
    assert.equal(result.items.length, 1);
    assert.ok(result.overallScore > 0);
  });
});

describe('F48: formatTechDebtReport', () => {
  it('formats a complete report', () => {
    const debt = {
      overallScore: 55,
      grade: 'C',
      items: [
        { category: 'Security (Secrets)', score: 70, severity: 'high', weight: 20, count: 3 },
        { category: 'Dead Code', score: 30, severity: 'medium', weight: 15, count: 6 },
      ],
      recommendations: [
        '⚠️ Fix 2 high-risk secret exposures immediately',
        'Remove 6 unused exports',
      ],
    };
    const report = formatTechDebtReport(debt);
    assert.ok(report.includes('### Tech Debt Assessment'));
    assert.ok(report.includes('**Overall Score: 55/100 (C)**'));
    assert.ok(report.includes('| Security (Secrets) |'));
    assert.ok(report.includes('#### Recommendations'));
    assert.ok(report.includes('⚠️ Fix 2'));
  });

  it('handles empty input', () => {
    const report = formatTechDebtReport({ items: [] });
    assert.ok(report.includes('No signals available'));
  });

  it('handles null input', () => {
    const report = formatTechDebtReport(null);
    assert.ok(report.includes('No signals available'));
  });

  it('omits recommendations when none', () => {
    const debt = {
      overallScore: 10,
      grade: 'A',
      items: [{ category: 'TODOs', score: 5, severity: 'low', weight: 15, count: 1 }],
      recommendations: [],
    };
    const report = formatTechDebtReport(debt);
    assert.ok(!report.includes('#### Recommendations'));
  });

  it('includes severity emoji', () => {
    const debt = {
      overallScore: 50,
      grade: 'C',
      items: [
        { category: 'Critical Issue', score: 80, severity: 'critical', weight: 20, count: 1 },
        { category: 'High Issue', score: 60, severity: 'high', weight: 15, count: 2 },
        { category: 'Medium Issue', score: 40, severity: 'medium', weight: 10, count: 3 },
        { category: 'Low Issue', score: 10, severity: 'low', weight: 5, count: 1 },
      ],
      recommendations: [],
    };
    const report = formatTechDebtReport(debt);
    assert.ok(report.includes('🔴'));
    assert.ok(report.includes('🟠'));
    assert.ok(report.includes('🟡'));
    assert.ok(report.includes('🟢'));
  });
});
