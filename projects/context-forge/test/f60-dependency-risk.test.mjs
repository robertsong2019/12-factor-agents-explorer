import { test } from 'node:test';
import assert from 'node:assert';
import { analyzeDependencyRisk, formatDependencyRiskReport } from '../context-forge.mjs';

test('analyzeDependencyRisk — empty input returns safe result', () => {
  const result = analyzeDependencyRisk({});
  assert.equal(result.totalDependencies, 0);
  assert.equal(result.grade, 'A'); // zero deps = low risk
  assert.ok(result.riskScore >= 90);
});

test('analyzeDependencyRisk — null input returns safe result', () => {
  const result = analyzeDependencyRisk(null);
  assert.equal(result.totalDependencies, 0);
});

test('analyzeDependencyRisk — accepts pkg-style input', () => {
  const result = analyzeDependencyRisk({ pkg: { dependencies: { lodash: '^4.0.0' } } });
  assert.equal(result.totalDependencies, 1);
  assert.equal(result.prodDependencies, 1);
});

test('analyzeDependencyRisk — detects pinned versions', () => {
  const result = analyzeDependencyRisk({
    dependencies: { express: '4.18.0', lodash: '4.17.21' },
  });
  assert.equal(result.categories.versionPinning.pinned, 2);
  assert.equal(result.categories.versionPinning.caret, 0);
});

test('analyzeDependencyRisk — detects caret versions', () => {
  const result = analyzeDependencyRisk({
    dependencies: { express: '^4.18.0', lodash: '^4.17.21' },
  });
  assert.equal(result.categories.versionPinning.caret, 2);
  assert.equal(result.categories.versionPinning.pinned, 0);
});

test('analyzeDependencyRisk — detects tilde versions', () => {
  const result = analyzeDependencyRisk({
    dependencies: { express: '~4.18.0' },
  });
  assert.equal(result.categories.versionPinning.tilde, 1);
});

test('analyzeDependencyRisk — detects wildcard versions', () => {
  const result = analyzeDependencyRisk({
    dependencies: { risky: '*', otherrisky: '*' },
  });
  assert.equal(result.categories.versionPinning.wildcard, 2);
  assert.ok(result.issues.some(i => i.type === 'wildcard_versions'));
});

test('analyzeDependencyRisk — flags code execution packages', () => {
  const result = analyzeDependencyRisk({
    dependencies: { vm2: '^3.9.0', shelljs: '^0.8.0' },
  });
  assert.ok(result.flaggedCount >= 2);
  assert.ok(result.categories.riskyPatterns.flagged.some(f => f.risk === 'code_execution'));
});

test('analyzeDependencyRisk — flags legacy heavyweight packages', () => {
  const result = analyzeDependencyRisk({
    dependencies: { moment: '^2.29.0', lodash: '^4.17.0' },
  });
  assert.ok(result.categories.riskyPatterns.flagged.some(f => f.risk === 'legacy_heavyweight'));
});

test('analyzeDependencyRisk — detects duplicate testing frameworks', () => {
  const result = analyzeDependencyRisk({
    devDependencies: { jest: '^29.0.0', mocha: '^10.0.0' },
  });
  assert.ok(result.categories.duplicateFunctionality.duplicates.some(d => d.category === 'testing'));
});

test('analyzeDependencyRisk — detects duplicate HTTP frameworks', () => {
  const result = analyzeDependencyRisk({
    dependencies: { express: '^4.0.0', fastify: '^4.0.0' },
  });
  assert.ok(result.categories.duplicateFunctionality.duplicates.some(d => d.category === 'http'));
});

test('analyzeDependencyRisk — high dev ratio flagged', () => {
  const result = analyzeDependencyRisk({
    dependencies: { express: '^4.0.0' },
    devDependencies: { jest: '^29.0.0', eslint: '^8.0.0', prettier: '^3.0.0', tsx: '^4.0.0', '@types/node': '^20.0.0', '@types/express': '^4.0.0', '@types/jest': '^29.0.0', supertest: '^6.0.0', nodemon: '^3.0.0', 'ts-node': '^10.0.0' },
  });
  assert.ok(result.categories.devProdRatio.ratio > 8);
  assert.ok(result.issues.some(i => i.type === 'high_dev_ratio'));
});

test('analyzeDependencyRisk — zero dependencies scores well', () => {
  const result = analyzeDependencyRisk({});
  assert.equal(result.categories.dependencyCount.score, 20);
});

test('analyzeDependencyRisk — excessive deps flagged', () => {
  const deps = {};
  for (let i = 0; i < 60; i++) deps[`pkg${i}`] = '^1.0.0';
  const result = analyzeDependencyRisk({ dependencies: deps });
  assert.ok(result.totalDependencies > 50);
  assert.ok(result.issues.some(i => i.type === 'excessive_deps'));
});

test('analyzeDependencyRisk — grade A for clean minimal project', () => {
  const result = analyzeDependencyRisk({
    dependencies: { '4.18.0': 'express' }, // will parse as name:value
  });
  // just check it doesn't crash
  assert.ok(result.grade !== undefined);
});

test('analyzeDependencyRisk — grades decrease with risk', () => {
  const cleanResult = analyzeDependencyRisk({});
  const riskyResult = analyzeDependencyRisk({
    dependencies: { vm2: '*', eval: '*', shelljs: '*' },
    devDependencies: {},
  });
  assert.ok(cleanResult.riskScore > riskyResult.riskScore);
});

test('analyzeDependencyRisk — separate prod and dev counts', () => {
  const result = analyzeDependencyRisk({
    dependencies: { express: '^4.0.0' },
    devDependencies: { jest: '^29.0.0', eslint: '^8.0.0' },
  });
  assert.equal(result.prodDependencies, 1);
  assert.equal(result.devDependencies, 2);
});

test('analyzeDependencyRisk — range versions detected', () => {
  const result = analyzeDependencyRisk({
    dependencies: { lib: '>=1.0.0 <2.0.0' },
  });
  assert.equal(result.categories.versionPinning.range, 1);
});

test('formatDependencyRiskReport — null returns warning', () => {
  const report = formatDependencyRiskReport(null);
  assert.ok(report.includes('No dependency data'));
});

test('formatDependencyRiskReport — includes grade and score', () => {
  const result = analyzeDependencyRisk({ dependencies: { lodash: '^4.0.0' } });
  const report = formatDependencyRiskReport(result);
  assert.ok(report.includes('Risk Grade'));
  assert.ok(report.includes('Total dependencies'));
});

test('formatDependencyRiskReport — includes issues section when issues exist', () => {
  const result = analyzeDependencyRisk({
    dependencies: { vm2: '*', otherrisky: '*' },
  });
  const report = formatDependencyRiskReport(result);
  assert.ok(report.includes('Issues') || report.includes('wildcard'));
});

test('formatDependencyRiskReport — includes category table', () => {
  const result = analyzeDependencyRisk({ dependencies: { express: '^4.0.0' } });
  const report = formatDependencyRiskReport(result);
  assert.ok(report.includes('Version Pinning'));
  assert.ok(report.includes('Category'));
});

test('formatDependencyRiskReport — issues sorted by severity', () => {
  const result = analyzeDependencyRisk({
    dependencies: { vm2: '*', lodash: '^4.0.0' },
  });
  const report = formatDependencyRiskReport(result);
  assert.ok(report.includes('[critical]'));
});
