import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, rmSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { execSync } from 'node:child_process';
import { analyzeGitHotspots, formatGitHotspotsReport } from '../context-forge.mjs';

function makeGitRepo() {
  const dir = mkdtempSync(join(tmpdir(), 'cf-hotspot-'));
  execSync(`git init -q "${dir}"`);
  execSync(`git -C "${dir}" config user.email "test@test.com"`);
  execSync(`git -C "${dir}" config user.name "Test"`);
  return dir;
}

function commitFile(dir, filename, content, msg) {
  writeFileSync(join(dir, filename), content);
  execSync(`git -C "${dir}" add "${filename}"`);
  execSync(`git -C "${dir}" commit -q -m "${msg}"`);
}

describe('F36: analyzeGitHotspots', async () => {
  it('finds hotspot files that change most', async () => {
    const dir = makeGitRepo();
    try {
      // Create 3 commits for hot.js, 1 for cold.js
      commitFile(dir, 'hot.js', 'v1\n', 'v1');
      commitFile(dir, 'other.js', 'other\n', 'add other');
      commitFile(dir, 'hot.js', 'v2\n', 'v2');
      commitFile(dir, 'cold.js', 'cold\n', 'add cold');
      commitFile(dir, 'hot.js', 'v3\n', 'v3');

      const result = await analyzeGitHotspots(dir);
      assert.ok(result.hotspots.length > 0, 'Should have hotspots');
      assert.equal(result.hotspots[0].file, 'hot.js', 'hot.js should be top hotspot');
      assert.equal(result.hotspots[0].changes, 3, 'hot.js changed 3 times');
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('returns correct change counts', async () => {
    const dir = makeGitRepo();
    try {
      commitFile(dir, 'a.js', '1\n', 'a1');
      commitFile(dir, 'b.js', '1\n', 'b1');
      commitFile(dir, 'a.js', '2\n', 'a2');

      const result = await analyzeGitHotspots(dir);
      const aHot = result.hotspots.find(h => h.file === 'a.js');
      const bHot = result.hotspots.find(h => h.file === 'b.js');
      assert.equal(aHot.changes, 2, 'a.js changed twice');
      assert.equal(bHot.changes, 1, 'b.js changed once');
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('computes change ratio', async () => {
    const dir = makeGitRepo();
    try {
      commitFile(dir, 'frequent.js', '1\n', 'c1');
      commitFile(dir, 'frequent.js', '2\n', 'c2');
      commitFile(dir, 'rare.js', '1\n', 'c3');

      const result = await analyzeGitHotspots(dir);
      const freq = result.hotspots.find(h => h.file === 'frequent.js');
      assert.ok(freq.ratio > 0, 'Should have a positive ratio');
      assert.ok(freq.ratio <= 1, 'Ratio should be <= 1');
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('sorts hotspots by change count descending', async () => {
    const dir = makeGitRepo();
    try {
      commitFile(dir, 'z.js', '1\n', 'z1');
      commitFile(dir, 'a.js', '1\n', 'a1');
      commitFile(dir, 'a.js', '2\n', 'a2');
      commitFile(dir, 'a.js', '3\n', 'a3');

      const result = await analyzeGitHotspots(dir);
      for (let i = 1; i < result.hotspots.length; i++) {
        assert.ok(result.hotspots[i - 1].changes >= result.hotspots[i].changes,
          'Hotspots should be sorted descending');
      }
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('limits to 20 hotspots', async () => {
    const dir = makeGitRepo();
    try {
      // Create 25 unique files with 1 commit each
      for (let i = 0; i < 25; i++) {
        commitFile(dir, `file${i}.js`, `${i}\n`, `commit ${i}`);
      }
      const result = await analyzeGitHotspots(dir);
      assert.ok(result.hotspots.length <= 20, 'Should limit to 20 hotspots');
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('returns error for non-git directory', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'cf-nogit-'));
    try {
      const result = await analyzeGitHotspots(dir);
      assert.ok(result.error, 'Should return error for non-git directory');
      assert.equal(result.hotspots.length, 0);
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('returns empty for git repo with no commits', async () => {
    const dir = makeGitRepo();
    try {
      const result = await analyzeGitHotspots(dir);
      assert.equal(result.hotspots.length, 0, 'No commits means no hotspots');
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('respects maxCommits parameter', async () => {
    const dir = makeGitRepo();
    try {
      for (let i = 0; i < 10; i++) {
        commitFile(dir, 'dyn.js', `${i}\n`, `commit ${i}`);
      }
      const limited = await analyzeGitHotspots(dir, 3);
      const full = await analyzeGitHotspots(dir, 50);
      // Limited should have fewer total changes
      assert.ok(limited.totalCommits <= full.totalCommits,
        'Limited scan should have <= total changes of full scan');
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });
});

describe('F36: formatGitHotspotsReport', async () => {
  it('formats a normal report', async () => {
    const dir = makeGitRepo();
    try {
      commitFile(dir, 'hot.js', '1\n', 'c1');
      commitFile(dir, 'hot.js', '2\n', 'c2');
      commitFile(dir, 'cool.js', '1\n', 'c3');

      const result = await analyzeGitHotspots(dir);
      const report = formatGitHotspotsReport(result);
      assert.ok(report.includes('🔥'), 'Should have fire emoji');
      assert.ok(report.includes('hot.js'), 'Should mention hottest file');
      assert.ok(report.includes('2×'), 'Should show change count');
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('handles error result', async () => {
    const report = formatGitHotspotsReport({ error: 'git not available', hotspots: [] });
    assert.ok(report.includes('⚠️'), 'Should have warning emoji for error');
  });

  it('handles empty hotspots', async () => {
    const report = formatGitHotspotsReport({ hotspots: [], totalCommits: 0, totalFiles: 0 });
    assert.ok(report.includes('No git history'), 'Should handle empty history');
  });

  it('handles null result', async () => {
    const report = formatGitHotspotsReport(null);
    assert.ok(report.includes('⚠️'), 'Should handle null');
  });

  it('includes visual bar chart', async () => {
    const dir = makeGitRepo();
    try {
      commitFile(dir, 'top.js', '1\n', 'c1');
      commitFile(dir, 'top.js', '2\n', 'c2');
      commitFile(dir, 'top.js', '3\n', 'c3');
      commitFile(dir, 'low.js', '1\n', 'c4');

      const result = await analyzeGitHotspots(dir);
      const report = formatGitHotspotsReport(result);
      assert.ok(report.includes('█'), 'Should include bar chart character');
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });
});
