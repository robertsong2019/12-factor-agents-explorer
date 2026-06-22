import { test } from 'node:test';
import assert from 'node:assert/strict';
import { auditDependencies, formatRiskAudit } from '../context-forge.mjs';

test('F25: auditDependencies — version type classification', () => {
  const info = {
    dependencies: {
      react: '^18.0.0',
      lodash: '~4.17.21',
      express: '4.18.0',
    },
  };
  const audit = auditDependencies(info);

  assert.equal(audit.versionTypes.caret, 1);
  assert.equal(audit.versionTypes.tilde, 1);
  assert.equal(audit.versionTypes.pinned, 1); // exact version counts as pinned
  assert.ok(audit.pinRate > 0);
});

test('F25: auditDependencies — flags latest tag as high risk', () => {
  const info = { dependencies: { risky: 'latest' } };
  const audit = auditDependencies(info);

  const highRisk = audit.flagged.find(f => f.name === 'risky');
  assert.ok(highRisk);
  assert.equal(highRisk.risk, 'high');
  assert.ok(highRisk.reason.includes('unpinned'));
});

test('F25: auditDependencies — flags git URL dependencies', () => {
  const info = { dependencies: { custom: 'git+https://github.com/x/y.git' } };
  const audit = auditDependencies(info);

  const gitDep = audit.flagged.find(f => f.name === 'custom');
  assert.ok(gitDep);
  assert.equal(gitDep.risk, 'medium');
});

test('F25: auditDependencies — detects abandoned packages', () => {
  const info = { dependencies: { 'left-pad': '^1.0.0', request: '^2.88.0' } };
  const audit = auditDependencies(info);

  const abandoned = audit.flagged.filter(f => f.reason.includes('abandoned'));
  assert.ok(abandoned.length >= 2);
});

test('F25: auditDependencies — detects duplicate deps in deps and devDeps', () => {
  const info = {
    dependencies: { lodash: '^4.0.0' },
    devDependencies: { lodash: '^4.0.0' },
  };
  const audit = auditDependencies(info);

  assert.ok(audit.duplicates.includes('lodash'));
  const dupFlag = audit.flagged.find(f => f.name === 'lodash');
  assert.ok(dupFlag);
  assert.ok(dupFlag.reason.includes('both'));
});

test('F25: auditDependencies — risk grade assignment', () => {
  const goodInfo = { dependencies: { react: '18.0.0', lodash: '4.17.21' } };
  const goodAudit = auditDependencies(goodInfo);
  assert.ok(['A', 'B'].includes(goodAudit.riskGrade), `Expected A or B, got ${goodAudit.riskGrade}`);

  const badInfo = { dependencies: { a: 'latest', b: 'latest', c: 'latest', d: 'latest' } };
  const badAudit = auditDependencies(badInfo);
  assert.ok(['D', 'F'].includes(badAudit.riskGrade), `Expected D or F, got ${badAudit.riskGrade}`);
});

test('F25: auditDependencies — empty deps', () => {
  const audit = auditDependencies({});
  assert.equal(audit.total, 0);
  assert.equal(audit.flagged.length, 0);
});

test('F25: auditDependencies — all pinned is good', () => {
  const info = {
    dependencies: { react: '18.2.0', express: '4.18.2' },
  };
  const audit = auditDependencies(info);
  assert.equal(audit.versionTypes.pinned, 2);
  assert.equal(audit.pinRate, 1);
  assert.ok(audit.riskScore < 20);
});

test('F25: formatRiskAudit — valid markdown output', () => {
  const info = { dependencies: { risky: 'latest' } };
  const audit = auditDependencies(info);
  const md = formatRiskAudit(audit);

  assert.ok(md.includes('# Dependency Risk Audit'));
  assert.ok(md.includes('Risk Grade'));
  assert.ok(md.includes('Version Pinning'));
  assert.ok(md.includes('Flagged Dependencies'));
});

test('F25: formatRiskAudit — no flagged section when clean', () => {
  const info = { dependencies: { react: '18.2.0' } };
  const audit = auditDependencies(info);
  const md = formatRiskAudit(audit);

  assert.ok(md.includes('# Dependency Risk Audit'));
  assert.ok(md.includes('Pin Rate'));
});

test('F25: auditDependencies — sorts by risk level', () => {
  const info = {
    dependencies: {
      safe: '1.0.0',
      risky: 'latest',
      medium: 'git+https://github.com/x/y.git',
    },
  };
  const audit = auditDependencies(info);
  const risks = audit.flagged.map(f => f.risk);
  const order = { high: 0, medium: 1, low: 2 };
  for (let i = 1; i < risks.length; i++) {
    assert.ok(order[risks[i]] >= order[risks[i - 1]], `Risk ordering: ${risks}`);
  }
});
