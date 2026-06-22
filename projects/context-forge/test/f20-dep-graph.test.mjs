import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildDependencyGraph, findCircularDependencies, formatDependencyGraph } from '../context-forge.mjs';

test('F20: buildDependencyGraph — basic graph construction', () => {
  const importData = {
    imports: new Map([
      ['src/a.js', ['react', 'lodash']],
      ['src/b.js', ['react', 'express']],
      ['src/c.js', ['lodash']],
    ]),
    allImports: ['react', 'lodash', 'express'],
  };
  const graph = buildDependencyGraph(importData);

  assert.equal(graph.stats.totalNodes, 6); // 3 files + 3 packages
  assert.equal(graph.stats.fileNodes, 3);
  assert.equal(graph.stats.packageNodes, 3);
  assert.equal(graph.stats.totalEdges, 5); // 2+2+1
  assert.equal(graph.stats.avgDepsPerFile, 1.67); // 5/3 rounded
});

test('F20: buildDependencyGraph — adjacency list', () => {
  const importData = {
    imports: new Map([
      ['src/app.js', ['react', 'react-dom']],
      ['src/server.js', ['express']],
    ]),
    allImports: ['react', 'react-dom', 'express'],
  };
  const graph = buildDependencyGraph(importData);

  assert.deepEqual(graph.adjacency['src/app.js'], ['react', 'react-dom']);
  assert.deepEqual(graph.adjacency['src/server.js'], ['express']);
});

test('F20: buildDependencyGraph — reverse adjacency', () => {
  const importData = {
    imports: new Map([
      ['src/a.js', ['react']],
      ['src/b.js', ['react', 'lodash']],
    ]),
    allImports: ['react', 'lodash'],
  };
  const graph = buildDependencyGraph(importData);

  assert.ok(graph.reverseAdjacency['react'].includes('src/a.js'));
  assert.ok(graph.reverseAdjacency['react'].includes('src/b.js'));
  assert.deepEqual(graph.reverseAdjacency['lodash'], ['src/b.js']);
});

test('F20: buildDependencyGraph — package usage ranking', () => {
  const importData = {
    imports: new Map([
      ['a.js', ['shared', 'unique-a']],
      ['b.js', ['shared', 'unique-b']],
      ['c.js', ['shared']],
    ]),
    allImports: ['shared', 'unique-a', 'unique-b'],
  };
  const graph = buildDependencyGraph(importData);

  assert.equal(graph.packageUsage[0].package, 'shared');
  assert.equal(graph.packageUsage[0].usedBy, 3);
});

test('F20: buildDependencyGraph — empty import data', () => {
  const importData = { imports: new Map(), allImports: [] };
  const graph = buildDependencyGraph(importData);

  assert.equal(graph.stats.totalNodes, 0);
  assert.equal(graph.stats.totalEdges, 0);
  assert.equal(graph.stats.avgDepsPerFile, 0);
});

test('F20: buildDependencyGraph — deduplicates edges', () => {
  const importData = {
    imports: new Map([
      ['src/a.js', ['react', 'react', 'lodash']], // duplicate 'react'
    ]),
    allImports: ['react', 'lodash'],
  };
  const graph = buildDependencyGraph(importData);

  // adjacency should dedupe
  assert.deepEqual(graph.adjacency['src/a.js'], ['react', 'lodash']);
});

test('F20: findCircularDependencies — no cycles in DAG', () => {
  const importData = {
    imports: new Map([
      ['a.js', ['b.js']],
      ['b.js', ['c.js']],
      ['c.js', []],
    ]),
    allImports: ['b.js', 'c.js'],
  };
  const cycles = findCircularDependencies(importData);
  assert.equal(cycles.length, 0);
});

test('F20: findCircularDependencies — detects simple cycle', () => {
  const importData = {
    imports: new Map([
      ['a.js', ['b.js']],
      ['b.js', ['a.js']],
    ]),
    allImports: ['a.js', 'b.js'],
  };
  const cycles = findCircularDependencies(importData);
  assert.ok(cycles.length >= 1, `Expected at least 1 cycle, got ${cycles.length}`);
});

test('F20: formatDependencyGraph — produces valid markdown', () => {
  const importData = {
    imports: new Map([
      ['src/app.js', ['react']],
      ['src/utils.js', ['lodash']],
    ]),
    allImports: ['react', 'lodash'],
  };
  const graph = buildDependencyGraph(importData);
  const md = formatDependencyGraph(graph);

  assert.ok(md.includes('# Dependency Graph'));
  assert.ok(md.includes('File Nodes'));
  assert.ok(md.includes('Package Nodes'));
  assert.ok(md.includes('## Top Packages by Usage'));
});

test('F20: formatDependencyGraph — handles empty graph', () => {
  const graph = buildDependencyGraph({ imports: new Map(), allImports: [] });
  const md = formatDependencyGraph(graph);

  assert.ok(md.includes('# Dependency Graph'));
  assert.ok(md.includes('| File Nodes | 0 |'));
});
