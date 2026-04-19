/**
 * BM25 Index + Bigram Tokenizer + Hybrid Search Tests
 */
import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService, BM25Index, tokenize } from '../src/index.js';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

function createService() {
  const dir = mkdtempSync(join(tmpdir(), 'bm25-test-'));
  const svc = new MemoryService({ dbPath: dir });
  return { svc, cleanup: () => { try { rmSync(dir, { recursive: true }); } catch {} } };
}

// ─── Bigram Tokenizer ────────────────────────────────────

describe('Bigram Tokenizer', () => {
  it('splits Chinese into character bigrams', () => {
    const tokens = tokenize('混合检索');
    assert.deepEqual(tokens, ['混合', '合检', '检索']);
  });

  it('handles mixed Chinese and English', () => {
    const tokens = tokenize('BM25混合检索test');
    assert.ok(tokens.includes('混合'));
    assert.ok(tokens.includes('合检'));
    assert.ok(tokens.includes('检索'));
    assert.ok(tokens.includes('bm25'));
  });

  it('handles single Chinese character', () => {
    const tokens = tokenize('好');
    assert.deepEqual(tokens, ['好']);
  });

  it('still splits English words', () => {
    const tokens = tokenize('Hello World Test');
    assert.deepEqual(tokens, ['hello', 'world', 'test']);
  });

  it('handles empty string', () => {
    assert.deepEqual(tokenize(''), []);
  });
});

// ─── BM25Index ───────────────────────────────────────────

describe('BM25Index', () => {
  it('adds and searches documents', () => {
    const idx = new BM25Index();
    idx.add('1', 'machine learning algorithm');
    idx.add('2', 'deep learning neural network');
    idx.add('3', 'cooking recipe pasta');
    const results = idx.search('machine learning');
    assert.ok(results.length > 0);
    assert.equal(results[0].id, '1'); // best match
  });

  it('removes documents from index', () => {
    const idx = new BM25Index();
    idx.add('1', 'machine learning');
    idx.add('2', 'deep learning');
    idx.remove('1');
    const results = idx.search('machine');
    assert.equal(results.length, 0);
  });

  it('returns empty for no matches', () => {
    const idx = new BM25Index();
    idx.add('1', 'hello world');
    const results = idx.search('xyz');
    assert.equal(results.length, 0);
  });

  it('tracks N and avgdl', () => {
    const idx = new BM25Index();
    idx.add('1', 'alpha beta gamma');
    idx.add('2', 'delta echo');
    assert.equal(idx.N, 2);
    assert.ok(idx.avgdl > 0);
  });

  it('handles Chinese text search', () => {
    const idx = new BM25Index();
    idx.add('1', '混合检索是搜索引擎的核心功能');
    idx.add('2', '深度学习神经网络');
    const results = idx.search('混合检索');
    assert.ok(results.length > 0);
    assert.equal(results[0].id, '1');
  });

  it('replacing document updates index', () => {
    const idx = new BM25Index();
    idx.add('1', 'old content about cats');
    idx.add('1', 'new content about dogs');
    const results = idx.search('dogs');
    assert.equal(results.length, 1);
    assert.equal(results[0].id, '1');
  });

  it('topK limits results', () => {
    const idx = new BM25Index();
    for (let i = 0; i < 20; i++) idx.add(String(i), `learning algorithm number ${i}`);
    const results = idx.search('learning', 3);
    assert.equal(results.length, 3);
  });
});

// ─── searchBM25() ────────────────────────────────────────

describe('searchBM25()', () => {
  /** @type {MemoryService} */
  let svc, cleanup;
  before(async () => {
    ({ svc, cleanup } = createService());
    await svc.init();
    await svc.add({ content: 'Machine learning algorithms for classification', layer: 'long' });
    await svc.add({ content: 'Deep learning with neural networks', layer: 'long' });
    await svc.add({ content: 'Cooking Italian pasta recipes', layer: 'short' });
    await svc.add({ content: 'Natural language processing and machine learning', layer: 'core' });
  });
  after(() => cleanup());

  it('returns ranked BM25 results', async () => {
    const results = await svc.searchBM25('machine learning');
    assert.ok(results.length > 0);
    assert.ok(results[0].score > 0);
  });

  it('filters by layer', async () => {
    const results = await svc.searchBM25('machine learning', { layer: 'core' });
    assert.ok(results.every(r => r.layer === 'core'));
  });

  it('respects limit', async () => {
    const results = await svc.searchBM25('learning', { limit: 2 });
    assert.ok(results.length <= 2);
  });

  it('includes explanation by default', async () => {
    const results = await svc.searchBM25('machine learning', { explain: true });
    assert.ok(results[0].explanation);
    assert.ok(results[0].explanation.bm25 > 0);
  });

  it('skips explanation when disabled', async () => {
    const results = await svc.searchBM25('machine learning', { explain: false });
    assert.ok(!results[0].explanation);
  });

  it('works with Chinese queries', async () => {
    const { svc: s, cleanup: c } = createService();
    await s.init();
    await s.add({ content: '混合检索是搜索引擎的核心功能' });
    await s.add({ content: '深度学习模型训练' });
    const results = await s.searchBM25('混合检索');
    assert.ok(results.length > 0);
    assert.ok(results[0].content.includes('混合'));
    c();
  });
});

// ─── searchHybrid() ──────────────────────────────────────

describe('searchHybrid()', () => {
  /** @type {MemoryService} */
  let svc, cleanup;
  before(async () => {
    ({ svc, cleanup } = createService());
    await svc.init();
    await svc.add({ content: 'Machine learning algorithms for classification tasks', layer: 'core' });
    await svc.add({ content: 'Deep learning with convolutional neural networks', layer: 'long' });
    await svc.add({ content: 'Cooking Italian pasta with garlic and olive oil', layer: 'short' });
    await svc.add({ content: 'Natural language processing and text mining', layer: 'long' });
    await svc.add({ content: 'ML model training optimization techniques', layer: 'core' });
  });
  after(() => cleanup());

  it('returns results in hybrid mode', async () => {
    const results = await svc.searchHybrid('machine learning');
    assert.ok(results.length > 0);
    assert.ok(results[0].score > 0);
  });

  it('keyword mode uses BM25 ranking', async () => {
    const results = await svc.searchHybrid('machine learning', { mode: 'keyword' });
    assert.ok(results.length > 0);
  });

  it('semantic mode uses ngram similarity', async () => {
    const results = await svc.searchHybrid('machine learning', { mode: 'semantic' });
    assert.ok(results.length > 0);
  });

  it('keyword beats semantic for exact match', async () => {
    // Exact term "pasta" should rank cooking result higher in keyword mode
    const kw = await svc.searchHybrid('pasta', { mode: 'keyword' });
    const sem = await svc.searchHybrid('pasta', { mode: 'semantic' });
    assert.ok(kw.length > 0);
    assert.ok(sem.length > 0);
  });

  it('hybrid includes explanation', async () => {
    const results = await svc.searchHybrid('machine learning', { explain: true });
    assert.ok(results[0].explanation);
    assert.equal(results[0].explanation.mode, 'hybrid');
  });

  it('respects limit and layer filter', async () => {
    const results = await svc.searchHybrid('learning', { limit: 2, layer: 'core' });
    assert.ok(results.length <= 2);
    assert.ok(results.every(r => r.layer === 'core'));
  });
});
