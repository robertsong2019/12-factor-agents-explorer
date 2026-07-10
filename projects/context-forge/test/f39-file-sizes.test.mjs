import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { analyzeFileSizes, formatFileSizeReport } from "../context-forge.mjs";

describe('F39: analyzeFileSizes', () => {
  let tmpDir;

  beforeEach(async () => {
    tmpDir = await mkdtemp(join(tmpdir(), 'cf-f39-'));
  });

  afterEach(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  it('should return zeros for empty directory', async () => {
    const result = await analyzeFileSizes(tmpDir);
    assert.equal(result.totalFiles, 0);
    assert.equal(result.totalSizeKB, 0);
    assert.equal(result.largest.length, 0);
    assert.equal(result.outliers.length, 0);
  });

  it('should count files and compute total size', async () => {
    await writeFile(join(tmpDir, 'a.js'), 'x'.repeat(100));
    await writeFile(join(tmpDir, 'b.js'), 'y'.repeat(200));
    const result = await analyzeFileSizes(tmpDir);
    assert.equal(result.totalFiles, 2);
    assert.ok(result.totalSizeKB > 0);
  });

  it('should compute average size correctly', async () => {
    await writeFile(join(tmpDir, 'a.js'), 'x'.repeat(1024));
    await writeFile(join(tmpDir, 'b.js'), 'y'.repeat(2048));
    const result = await analyzeFileSizes(tmpDir);
    assert.ok(result.avgSizeKB > 0);
    // avg should be between the two sizes
    assert.ok(result.avgSizeKB >= 1 && result.avgSizeKB <= 3);
  });

  it('should sort largest files descending', async () => {
    await writeFile(join(tmpDir, 'small.js'), 'x');
    await writeFile(join(tmpDir, 'big.js'), 'x'.repeat(10000));
    await writeFile(join(tmpDir, 'medium.js'), 'x'.repeat(5000));
    const result = await analyzeFileSizes(tmpDir);
    assert.equal(result.largest[0].file, 'big.js');
    assert.equal(result.largest[1].file, 'medium.js');
    assert.equal(result.largest[2].file, 'small.js');
  });

  it('should group by extension', async () => {
    await writeFile(join(tmpDir, 'a.js'), 'xxx');
    await writeFile(join(tmpDir, 'b.js'), 'yyy');
    await writeFile(join(tmpDir, 'c.py'), 'zzz');
    const result = await analyzeFileSizes(tmpDir);
    const jsExt = result.byExtension.find(e => e.ext === '.js');
    assert.equal(jsExt.count, 2);
    const pyExt = result.byExtension.find(e => e.ext === '.py');
    assert.equal(pyExt.count, 1);
  });

  it('should detect size outliers with z-score > 2', async () => {
    // Create many small files and one huge file
    for (let i = 0; i < 10; i++) {
      await writeFile(join(tmpDir, `file${i}.js`), 'x'.repeat(100));
    }
    await writeFile(join(tmpDir, 'huge.js'), 'x'.repeat(50000));
    const result = await analyzeFileSizes(tmpDir);
    assert.ok(result.outliers.length > 0);
    assert.equal(result.outliers[0].file, 'huge.js');
    assert.ok(result.outliers[0].zScore > 2);
  });

  it('should respect maxDepth option', async () => {
    await writeFile(join(tmpDir, 'top.js'), 'xxx');
    await mkdir(join(tmpDir, 'sub'), { recursive: true });
    await writeFile(join(tmpDir, 'sub', 'deep.js'), 'yyy');
    const result = await analyzeFileSizes(tmpDir, { maxDepth: 0 });
    // With maxDepth 0, only top-level files
    assert.equal(result.totalFiles, 1);
  });

  it('should skip node_modules', async () => {
    await writeFile(join(tmpDir, 'app.js'), 'xxx');
    await mkdir(join(tmpDir, 'node_modules'), { recursive: true });
    await writeFile(join(tmpDir, 'node_modules', 'dep.js'), 'yyy');
    const result = await analyzeFileSizes(tmpDir);
    assert.equal(result.totalFiles, 1);
  });

  it('should compute percentile values', async () => {
    for (let i = 1; i <= 100; i++) {
      await writeFile(join(tmpDir, `f${i}.js`), 'x'.repeat(i * 100));
    }
    const result = await analyzeFileSizes(tmpDir);
    assert.ok(result.medianSizeKB > 0);
    assert.ok(result.p90SizeKB > result.medianSizeKB);
    assert.ok(result.p95SizeKB > result.p90SizeKB);
    assert.ok(result.p99SizeKB >= result.p95SizeKB);
  });

  it('should sort byExtension by totalKB descending', async () => {
    await writeFile(join(tmpDir, 'a.js'), 'x'.repeat(1000));
    await writeFile(join(tmpDir, 'b.py'), 'x'.repeat(100));
    const result = await analyzeFileSizes(tmpDir);
    assert.equal(result.byExtension[0].ext, '.js');
  });
});

describe('F39: formatFileSizeReport', () => {
  it('should handle empty analysis', () => {
    const report = formatFileSizeReport({ totalFiles: 0 });
    assert.ok(report.includes('No files'));
  });

  it('should include key sections', () => {
    const analysis = {
      totalFiles: 5,
      totalSizeKB: 100,
      avgSizeKB: 20,
      medianSizeKB: 15,
      p90SizeKB: 40,
      p95SizeKB: 50,
      p99SizeKB: 90,
      largest: [{ file: 'big.js', sizeKB: 90 }],
      byExtension: [{ ext: '.js', count: 5, totalKB: 100, avgKB: 20 }],
      outliers: [{ file: 'big.js', sizeKB: 90, zScore: 2.5 }],
    };
    const report = formatFileSizeReport(analysis);
    assert.ok(report.includes('File Size Analysis'));
    assert.ok(report.includes('Largest Files'));
    assert.ok(report.includes('big.js'));
    assert.ok(report.includes('Size Outliers'));
    assert.ok(report.includes('By Extension'));
  });

  it('should omit outliers section when none', () => {
    const analysis = {
      totalFiles: 3,
      totalSizeKB: 30,
      avgSizeKB: 10,
      medianSizeKB: 10,
      p90SizeKB: 12,
      p95SizeKB: 12,
      p99SizeKB: 12,
      largest: [{ file: 'a.js', sizeKB: 12 }],
      byExtension: [{ ext: '.js', count: 3, totalKB: 30, avgKB: 10 }],
      outliers: [],
    };
    const report = formatFileSizeReport(analysis);
    assert.ok(!report.includes('Size Outliers'));
  });
});
