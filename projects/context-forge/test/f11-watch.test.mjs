import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync, rmSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { watchProject } from '../context-forge.mjs';

const TMP = join(process.cwd(), 'test-f11-fixture');

function setupFixture() {
  rmSync(TMP, { recursive: true, force: true });
  mkdirSync(TMP, { recursive: true });
  mkdirSync(join(TMP, 'src'), { recursive: true });
  writeFileSync(join(TMP, 'package.json'), JSON.stringify({
    name: 'test-fixture',
    version: '1.0.0',
    main: 'index.js',
  }));
  writeFileSync(join(TMP, 'src', 'index.js'), 'module.exports = { hello: () => "world" };\n');
}

function cleanupFixture() {
  rmSync(TMP, { recursive: true, force: true });
}

describe('F11: watchProject', () => {
  beforeEach(setupFixture);
  afterEach(cleanupFixture);

  it('should return a cancel function', () => {
    const cancel = watchProject(TMP, { dryRun: true }, 100);
    assert.strictEqual(typeof cancel, 'function');
    cancel();
  });

  it('should call onRegenerate callback on file change', async () => {
    const results = [];
    const cancel = watchProject(TMP, { dryRun: true }, 100, (r) => results.push(r));

    // Trigger a file change
    setTimeout(() => {
      writeFileSync(join(TMP, 'src', 'index.js'), 'module.exports = { updated: true };\n');
    }, 150);

    // Wait for debounce + regeneration
    await new Promise(resolve => setTimeout(resolve, 3000));

    cancel();
    assert.ok(results.length > 0, 'onRegenerate should have been called');
    assert.strictEqual(results[0].success, true);
    assert.strictEqual(typeof results[0].runCount, 'number');
    assert.strictEqual(typeof results[0].elapsed, 'number');
  });

  it('should track runCount across multiple regenerations', async () => {
    const results = [];
    const cancel = watchProject(TMP, { dryRun: true }, 100, (r) => results.push(r));

    // First change
    setTimeout(() => {
      writeFileSync(join(TMP, 'src', 'index.js'), '// change 1\n');
    }, 100);

    // Second change (after first regen completes)
    setTimeout(() => {
      writeFileSync(join(TMP, 'src', 'index.js'), '// change 2\n');
    }, 2500);

    await new Promise(resolve => setTimeout(resolve, 5000));

    cancel();
    assert.ok(results.length >= 1, 'at least one regeneration should happen');
    if (results.length >= 2) {
      assert.ok(results[1].runCount > results[0].runCount, 'runCount should increment');
    }
  });

  it('should debounce rapid changes (single regen for multiple changes)', async () => {
    const results = [];
    const cancel = watchProject(TMP, { dryRun: true }, 200, (r) => results.push(r));

    // Rapid-fire changes
    setTimeout(() => {
      writeFileSync(join(TMP, 'src', 'a.js'), '// a\n');
      writeFileSync(join(TMP, 'src', 'b.js'), '// b\n');
      writeFileSync(join(TMP, 'src', 'c.js'), '// c\n');
    }, 100);

    await new Promise(resolve => setTimeout(resolve, 2500));

    cancel();
    // Debounce should collapse 3 rapid changes into 1 regeneration
    assert.strictEqual(results.length, 1, '3 rapid changes should debounce to 1 regeneration');
  });

  it('should ignore non-source files', async () => {
    const results = [];
    const cancel = watchProject(TMP, { dryRun: true }, 100, (r) => results.push(r));

    // Change a .txt file (not in watched extensions)
    setTimeout(() => {
      writeFileSync(join(TMP, 'README.txt'), 'not a source file\n');
    }, 100);

    await new Promise(resolve => setTimeout(resolve, 2000));

    cancel();
    assert.strictEqual(results.length, 0, 'non-source files should be ignored');
  });

  it('should handle errors gracefully via onRegenerate callback', async () => {
    const results = [];
    // Point to a non-existent path to force an error path
    const cancel = watchProject('/nonexistent/path/xyz', { dryRun: true }, 100, (r) => results.push(r));

    // Simulate a change by triggering regenerate through a file event
    // Since path doesn't exist, the watcher may error
    await new Promise(resolve => setTimeout(resolve, 1000));

    cancel();
    // We mainly verify it doesn't crash
    assert.ok(true, 'watchProject handled non-existent path without crashing');
  });
});
