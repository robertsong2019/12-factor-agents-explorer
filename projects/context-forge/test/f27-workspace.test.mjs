import { test } from 'node:test';
import assert from 'node:assert/strict';
import { matchGlob, formatWorkspaceAnalysis } from '../context-forge.mjs';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

test('F27: matchGlob — simple star matching', () => {
  assert.ok(matchGlob('packages/foo', 'packages/*'));
  assert.ok(matchGlob('packages/bar', 'packages/*'));
  assert.ok(!matchGlob('packages/foo/bar', 'packages/*'));
});

test('F27: matchGlob — double star matching', () => {
  assert.ok(matchGlob('libs/deep/nested/pkg', 'libs/**'));
  assert.ok(matchGlob('libs/pkg', 'libs/**'));
});

test('F27: matchGlob — no match', () => {
  assert.ok(!matchGlob('node_modules/x', 'packages/*'));
  assert.ok(!matchGlob('src/index.js', 'packages/*'));
});

test('F27: matchGlob — exact path', () => {
  assert.ok(matchGlob('apps/api', 'apps/api'));
  assert.ok(!matchGlob('apps/api-v2', 'apps/api'));
});

test('F27: formatWorkspaceAnalysis — no workspaces', () => {
  const md = formatWorkspaceAnalysis([], null);
  assert.ok(md.includes('# Workspace Analysis'));
  assert.ok(md.includes('No monorepo'));
});

test('F27: formatWorkspaceAnalysis — with packages', () => {
  const workspaces = [{ manager: 'pnpm', config: 'pnpm-workspace.yaml', globs: ['packages/*'] }];
  const analysis = {
    packages: [
      { name: '@scope/a', path: 'packages/a', version: '1.0.0', deps: 3, devDeps: 2, private: false },
      { name: '@scope/b', path: 'packages/b', version: '0.5.0', deps: 1, devDeps: 4, private: true },
    ],
    internalDeps: [{ from: '@scope/b', to: '@scope/a', version: 'workspace:*', type: 'prod' }],
    stats: { totalPackages: 2, internalDepLinks: 1, avgDepsPerPackage: 2 },
  };
  const md = formatWorkspaceAnalysis(workspaces, analysis);

  assert.ok(md.includes('# Workspace Analysis'));
  assert.ok(md.includes('pnpm'));
  assert.ok(md.includes('@scope/a'));
  assert.ok(md.includes('@scope/b'));
  assert.ok(md.includes('Internal Dependencies'));
  assert.ok(md.includes('@scope/b → @scope/a'));
});

test('F27: formatWorkspaceAnalysis — workspace managers listing', () => {
  const workspaces = [
    { manager: 'turborepo', config: 'turbo.json', globs: [] },
    { manager: 'pnpm', config: 'pnpm-workspace.yaml', globs: ['packages/*', 'apps/*'] },
  ];
  const md = formatWorkspaceAnalysis(workspaces, null);

  assert.ok(md.includes('turborepo'));
  assert.ok(md.includes('pnpm'));
  assert.ok(md.includes('packages/*'));
  assert.ok(md.includes('apps/*'));
});

test('F27: formatWorkspaceAnalysis — empty analysis', () => {
  const workspaces = [{ manager: 'lerna', config: 'lerna.json', globs: ['packages/*'] }];
  const analysis = { packages: [], internalDeps: [], stats: { totalPackages: 0, internalDepLinks: 0, avgDepsPerPackage: 0 } };
  const md = formatWorkspaceAnalysis(workspaces, analysis);

  assert.ok(md.includes('# Workspace Analysis'));
  assert.ok(md.includes('lerna'));
});

// Integration test with real temp directory
test('F27: detectWorkspaces + analyzeWorkspace — temp monorepo', async () => {
  const { detectWorkspaces, analyzeWorkspace } = await import('../context-forge.mjs');

  const tmpRoot = await mkdtemp(join(tmpdir(), 'cf-monorepo-'));
  try {
    // Create pnpm-workspace.yaml
    await writeFile(join(tmpRoot, 'pnpm-workspace.yaml'), 'packages:\n  - packages/*\n');
    // Create package.json root
    await writeFile(join(tmpRoot, 'package.json'), JSON.stringify({ name: 'root', private: true }));
    // Create packages
    await mkdir(join(tmpRoot, 'packages', 'a'), { recursive: true });
    await mkdir(join(tmpRoot, 'packages', 'b'), { recursive: true });
    await writeFile(join(tmpRoot, 'packages', 'a', 'package.json'), JSON.stringify({
      name: '@test/a', version: '1.0.0', dependencies: { '@test/b': 'workspace:*', react: '^18.0.0' },
    }));
    await writeFile(join(tmpRoot, 'packages', 'b', 'package.json'), JSON.stringify({
      name: '@test/b', version: '2.0.0', dependencies: { lodash: '^4.0.0' },
    }));

    const workspaces = await detectWorkspaces(tmpRoot);
    assert.ok(workspaces.length >= 1);
    assert.ok(workspaces.some(w => w.manager === 'pnpm'));

    const pnpmWs = workspaces.find(w => w.manager === 'pnpm');
    assert.ok(pnpmWs.globs.includes('packages/*'));

    const analysis = await analyzeWorkspace(tmpRoot, ['packages/*']);
    assert.equal(analysis.stats.totalPackages, 2);
    assert.ok(analysis.internalDeps.some(d => d.from === '@test/a' && d.to === '@test/b'));
  } finally {
    await rm(tmpRoot, { recursive: true, force: true });
  }
});

test('F27: matchGlob — dot escaping', () => {
  assert.ok(matchGlob('src/app.tsx', 'src/app.tsx'));
  assert.ok(!matchGlob('srcXappYtsx', 'src/app.tsx'));
});
