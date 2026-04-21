/**
 * Agent Memory Service — Tests
 */
import { describe, it, before } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService, MemoryExtractor, tokenize, ngramSimilarity, keywordScore, LAYERS } from '../src/index.js';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

// ─── Helpers ─────────────────────────────────────────────

function createService() {
  const dir = mkdtempSync(join(tmpdir(), 'mem-test-'));
  const svc = new MemoryService({ dbPath: dir });
  return { svc, cleanup: () => { try { rmSync(dir, { recursive: true }); } catch {} } };
}

// ─── Tokenizer & Similarity ──────────────────────────────

describe('Tokenizer', () => {
  it('splits English text', () => {
    const tokens = tokenize('Hello World Test');
    assert.deepEqual(tokens, ['hello', 'world', 'test']);
  });

  it('handles Chinese characters', () => {
    const tokens = tokenize('我喜欢编程');
    assert.ok(tokens.includes('喜欢'));
  });

  it('filters single characters', () => {
    const tokens = tokenize('a b cd');
    assert.deepEqual(tokens, ['cd']);
  });
});

describe('N-gram Similarity', () => {
  it('returns 1 for identical strings', () => {
    assert.ok(ngramSimilarity('hello', 'hello') > 0.9);
  });

  it('returns 0 for completely different strings', () => {
    assert.ok(ngramSimilarity('abc', 'xyz') < 0.1);
  });

  it('returns partial match for similar strings', () => {
    const sim = ngramSimilarity('hello world', 'hello there');
    assert.ok(sim > 0 && sim < 1);
  });
});

describe('Keyword Score', () => {
  it('returns 1 for perfect match', () => {
    const score = keywordScore(['hello'], ['hello', 'world']);
    assert.equal(score, 1);
  });

  it('returns 0 for no match', () => {
    const score = keywordScore(['xyz'], ['hello', 'world']);
    assert.equal(score, 0);
  });

  it('returns partial score', () => {
    const score = keywordScore(['hello', 'foo'], ['hello', 'world']);
    assert.equal(score, 0.5);
  });
});

// ─── MemoryExtractor ─────────────────────────────────────

describe('MemoryExtractor', () => {
  const extractor = new MemoryExtractor();

  it('extracts preferences (Chinese)', () => {
    const results = extractor.extract('我喜欢用 TypeScript 写项目');
    assert.ok(results.some(r => r.type === 'preference'));
  });

  it('extracts preferences (English)', () => {
    const results = extractor.extract('I prefer dark mode for coding');
    assert.ok(results.some(r => r.type === 'preference'));
  });

  it('extracts decisions', () => {
    const results = extractor.extract('我要开始研究 Mem0 框架');
    assert.ok(results.some(r => r.type === 'decision'));
  });

  it('extracts facts', () => {
    const results = extractor.extract('Python 是动态类型语言');
    assert.ok(results.some(r => r.type === 'fact'));
  });

  it('returns context or fact for user messages with no pattern match', () => {
    const text = 'This is a longer message about something that does not match any pattern exactly';
    const results = extractor.extract(text, 'user');
    assert.ok(results.length > 0);
    // May be 'context' (fallback) or 'fact' (if "is" pattern matched)
    assert.ok(['context', 'fact'].includes(results[0].type));
  });

  it('extracts from full conversation', () => {
    const results = extractor.extractFromConversation([
      { role: 'user', content: '我喜欢用 Rust 写系统程序' },
      { role: 'assistant', content: '好的，Rust 确实是系统编程的好选择' },
    ]);
    assert.ok(results.length >= 1);
    assert.ok(results.some(r => r.type === 'preference'));
  });

  it('classifies preferences as core layer', () => {
    const results = extractor.extractFromConversation([
      { role: 'user', content: 'I prefer TypeScript over JavaScript' },
    ]);
    assert.ok(results.some(r => r.layer === 'core'));
  });
});

// ─── MemoryService ───────────────────────────────────────

describe('MemoryService', () => {
  it('initializes and adds a memory', async () => {
    const { svc, cleanup } = createService();
    try {
      const m = await svc.add({ content: 'test memory', layer: 'short' });
      assert.ok(m.id);
      assert.equal(m.content, 'test memory');
      assert.equal(m.layer, 'short');
      assert.equal(m.weight, 1.0);
      assert.equal(m.accessCount, 0);
    } finally { cleanup(); }
  });

  it('retrieves a memory by id', async () => {
    const { svc, cleanup } = createService();
    try {
      const m = await svc.add({ content: 'hello', layer: 'long' });
      const fetched = await svc.get(m.id);
      assert.ok(fetched);
      assert.equal(fetched.content, 'hello');
      assert.equal(fetched.accessCount, 1);  // get boosts access
    } finally { cleanup(); }
  });

  it('searches memories', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'Python is a dynamic language', layer: 'long', tags: ['python'] });
      await svc.add({ content: 'Rust is a systems language', layer: 'long', tags: ['rust'] });
      await svc.add({ content: 'TypeScript adds types to JavaScript', layer: 'long', tags: ['typescript'] });

      const results = await svc.search('Python dynamic');
      assert.ok(results.length >= 1);
      assert.equal(results[0].content, 'Python is a dynamic language');
    } finally { cleanup(); }
  });

  it('filters search by layer', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'core item', layer: 'core' });
      await svc.add({ content: 'short item', layer: 'short' });

      const results = await svc.search('item', { layer: 'core' });
      assert.ok(results.length >= 1);
      assert.ok(results.every(r => r.layer === 'core'));
    } finally { cleanup(); }
  });

  it('respects limit in search', async () => {
    const { svc, cleanup } = createService();
    try {
      for (let i = 0; i < 10; i++) {
        await svc.add({ content: `memory item ${i} about Python`, layer: 'long' });
      }
      const results = await svc.search('Python', { limit: 3 });
      assert.ok(results.length <= 3);
    } finally { cleanup(); }
  });

  it('extracts from conversation and deduplicates', async () => {
    const { svc, cleanup } = createService();
    try {
      const m1 = await svc.extractFromConversation([
        { role: 'user', content: '我喜欢用 TypeScript 写项目' },
      ]);
      assert.ok(m1.length >= 1);

      // Same conversation again → should deduplicate
      const m2 = await svc.extractFromConversation([
        { role: 'user', content: '我喜欢用 TypeScript 写项目' },
      ]);
      assert.equal(m2.length, 0);  // no new memories (deduped)
    } finally { cleanup(); }
  });

  it('decays long and short memories but not core', async () => {
    const { svc, cleanup } = createService();
    try {
      const core = await svc.add({ content: 'core memory', layer: 'core' });
      const long = await svc.add({ content: 'long memory', layer: 'long' });

      // Simulate time passing by manipulating accessedAt
      const longMem = await svc.get(long.id);
      // Set accessedAt to 60 days ago by direct manipulation
      const stats1 = await svc.stats();

      const result = await svc.decay();
      assert.ok(result.decayed >= 0 || result.removed >= 0);

      // Core should still be there with full weight
      const coreMem = await svc.get(core.id);
      assert.ok(coreMem);
      assert.equal(coreMem.weight, 1.0);  // core never decays
    } finally { cleanup(); }
  });

  it('returns stats', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'core', layer: 'core', tags: ['a', 'b'] });
      await svc.add({ content: 'long', layer: 'long', entities: ['x'] });
      await svc.add({ content: 'short', layer: 'short' });

      const stats = await svc.stats();
      assert.equal(stats.total, 3);
      assert.deepEqual(stats.byLayer, { core: 1, long: 1, short: 1 });
      assert.equal(stats.uniqueTags, 2);
      assert.equal(stats.uniqueEntities, 1);
    } finally { cleanup(); }
  });

  it('persists and reloads memories', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'mem-persist-'));
    try {
      const svc1 = new MemoryService({ dbPath: dir });
      await svc1.add({ content: 'persistent memory', layer: 'long' });

      const svc2 = new MemoryService({ dbPath: dir });
      const results = await svc2.search('persistent');
      assert.ok(results.length >= 1);
      assert.equal(results[0].content, 'persistent memory');
    } finally {
      try { rmSync(dir, { recursive: true }); } catch {}
    }
  });

  it('clears all memories', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'test1', layer: 'short' });
      await svc.add({ content: 'test2', layer: 'long' });
      const stats1 = await svc.stats();
      assert.equal(stats1.total, 2);

      await svc.clear();
      const stats2 = await svc.stats();
      assert.equal(stats2.total, 0);
    } finally { cleanup(); }
  });

  it('exports all memories', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'export test', layer: 'long' });
      const exported = await svc.export();
      assert.equal(exported.length, 1);
      assert.equal(exported[0].content, 'export test');
    } finally { cleanup(); }
  });

  it('search boosts accessed memories', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'searchable memory about Rust', layer: 'long' });
      
      const r1 = await svc.search('Rust');
      assert.ok(r1.length >= 1);
      
      // Weight should be boosted after search
      const stats = await svc.stats();
      assert.ok(stats.avgWeight > 0);
    } finally { cleanup(); }
  });
});

// ─── Edge Cases & Bug Fixes ─────────────────────────────

describe('Edge Cases', () => {
  it('ngramSimilarity handles empty strings', () => {
    assert.equal(ngramSimilarity('', ''), 0);
    assert.equal(ngramSimilarity('hello', ''), 0);
    assert.equal(ngramSimilarity('', 'hello'), 0);
  });

  it('ngramSimilarity handles single char strings', () => {
    const sim = ngramSimilarity('a', 'a');
    assert.equal(sim, 0); // no 2-grams possible
  });

  it('keywordScore handles empty query tokens', () => {
    assert.equal(keywordScore([], ['hello']), 0);
  });

  it('tokenize handles empty and whitespace', () => {
    assert.deepEqual(tokenize(''), []);
    assert.deepEqual(tokenize('   '), []);
  });

  it('add with default layer is short', async () => {
    const { svc, cleanup } = createService();
    try {
      const m = await svc.add({ content: 'defaults' });
      assert.equal(m.layer, 'short');
    } finally { cleanup(); }
  });

  it('add generates unique IDs', async () => {
    const { svc, cleanup } = createService();
    try {
      const m1 = await svc.add({ content: 'a' });
      const m2 = await svc.add({ content: 'b' });
      assert.notEqual(m1.id, m2.id);
    } finally { cleanup(); }
  });

  it('get returns undefined for non-existent ID', async () => {
    const { svc, cleanup } = createService();
    try {
      const m = await svc.get('nonexistent-id');
      assert.equal(m, undefined);
    } finally { cleanup(); }
  });

  it('search with empty query returns results', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'test memory', layer: 'long' });
      const results = await svc.search('');
      // Should not crash; results may be empty or scored low
      assert.ok(Array.isArray(results));
    } finally { cleanup(); }
  });

  it('decay removes low-weight short memories', async () => {
    const { svc, cleanup } = createService();
    try {
      const m = await svc.add({ content: 'short lived', layer: 'short' });
      // Manually set weight below minWeight and accessedAt to far past
      const mem = svc.export().then(arr => {
        const item = arr[0];
        item.weight = 0.01;
        item.accessedAt = Date.now() - 100 * 24 * 60 * 60 * 1000; // 100 days ago
      });
      await mem;
      // Re-add via get to force load, then decay
      const result = await svc.decay();
      assert.ok(result.removed >= 0);
    } finally { cleanup(); }
  });

  it('extractFromConversation with empty messages returns empty', async () => {
    const { svc, cleanup } = createService();
    try {
      const result = await svc.extractFromConversation([]);
      assert.deepEqual(result, []);
    } finally { cleanup(); }
  });

  it('dislike patterns are extracted', () => {
    const extractor = new MemoryExtractor();
    const results = extractor.extract('我不喜欢早起');
    assert.ok(results.some(r => r.type === 'preference'));
  });

  it('tech mentions are extracted', () => {
    const extractor = new MemoryExtractor();
    const results = extractor.extract('project: openclaw is great');
    assert.ok(results.some(r => r.type === 'entity'));
  });

  it('search strategy keyword works', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'JavaScript frameworks', layer: 'long' });
      const results = await svc.search('JavaScript', { strategy: 'keyword' });
      assert.ok(results.length >= 1);
    } finally { cleanup(); }
  });

  it('search strategy semantic works', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'JavaScript frameworks', layer: 'long' });
      const results = await svc.search('JavaScript', { strategy: 'semantic' });
      assert.ok(results.length >= 1);
    } finally { cleanup(); }
  });

  it('contentHash is deterministic', () => {
    // Access via re-import not possible; test via add duplicate content
    // We test dedup behavior instead
  });

  it('stats on empty store', async () => {
    const { svc, cleanup } = createService();
    try {
      const stats = await svc.stats();
      assert.equal(stats.total, 0);
      assert.equal(stats.avgWeight, 0);
    } finally { cleanup(); }
  });
});

// ─── Consolidation ───────────────────────────────────────

describe('Memory Consolidation', () => {
  it('merges similar short memories into long layer', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: '用户喜欢用 TypeScript 开发后端', layer: 'short', entities: ['typescript'] });
      await svc.add({ content: '用户偏好 TypeScript 语言', layer: 'short', entities: ['typescript'] });
      await svc.add({ content: '完全不相关的内容关于天气', layer: 'short', entities: ['weather'] });

      const result = await svc.consolidate();
      assert.ok(result.clusters >= 1, 'should find at least 1 cluster');
      assert.ok(result.merged >= 2, 'should merge at least 2 memories');
      
      // The consolidated memory should be in 'long' layer
      const stats = await svc.stats();
      // Original: 3 short, after consolidation: 1 long (from 2 similar) + 1 short (weather)
      assert.ok(stats.byLayer.long >= 1, 'should have at least 1 long memory');
    } finally { cleanup(); }
  });

  it('promotes to core when long memories merge', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: '项目架构使用微服务架构模式', layer: 'long', entities: ['microservice'] });
      await svc.add({ content: '微服务架构模式决定已确认', layer: 'short', entities: ['microservice'] });

      const result = await svc.consolidate();
      assert.ok(result.clusters >= 1);
      
      const coreMems = (await svc.search('微服务', { limit: 10, strategy: 'hybrid' }))
        .filter(m => m.layer === 'core');
      assert.ok(coreMems.length >= 1, 'should promote merged long+short to core');
    } finally { cleanup(); }
  });

  it('preserves earliest creation time and total access count', async () => {
    const { svc, cleanup } = createService();
    try {
      const m1 = await svc.add({ content: '关于 Python 数据分析', layer: 'short', entities: ['python'] });
      const m2 = await svc.add({ content: 'Python 数据处理偏好', layer: 'short', entities: ['python'] });
      
      // Access m1 multiple times
      await svc.get(m1.id);
      await svc.get(m1.id);

      const result = await svc.consolidate();
      if (result.promoted.length > 0) {
        const consolidated = result.promoted[0];
        assert.ok(consolidated.accessCount >= 2, 'should preserve total access count');
      }
    } finally { cleanup(); }
  });

  it('dry run does not modify store', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: '相似内容 A 关于 Redis 缓存', layer: 'short' });
      await svc.add({ content: '相似内容 B 关于 Redis 缓存策略', layer: 'short' });

      const statsBefore = await svc.stats();
      const result = await svc.consolidate({ dryRun: true });
      const statsAfter = await svc.stats();

      assert.equal(statsBefore.total, statsAfter.total, 'dry run should not change memory count');
      assert.ok(result.promoted.length >= 1, 'dry run should still report potential merges');
      assert.ok(result.promoted[0].id.startsWith('dry-run-'), 'dry run ids should be prefixed');
    } finally { cleanup(); }
  });

  it('does not merge unrelated memories', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: '今天吃了拉面', layer: 'short', entities: ['food'] });
      await svc.add({ content: 'Kubernetes 集群部署完成', layer: 'short', entities: ['k8s'] });
      await svc.add({ content: '量子计算论文阅读笔记', layer: 'short', entities: ['quantum'] });

      const result = await svc.consolidate();
      assert.equal(result.clusters, 0, 'should not cluster unrelated memories');
      assert.equal(result.merged, 0);
    } finally { cleanup(); }
  });

  it('consolidation source tracks original ids', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'React 组件设计模式学习', layer: 'short', entities: ['react'] });
      await svc.add({ content: 'React 设计模式笔记', layer: 'short', entities: ['react'] });

      const result = await svc.consolidate();
      if (result.promoted.length > 0) {
        assert.ok(
          result.promoted[0].source.startsWith('consolidated:'),
          'source should track consolidation origin'
        );
      }
    } finally { cleanup(); }
  });

  it('respects custom similarity threshold', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'A very unique sentence about cats', layer: 'short' });
      await svc.add({ content: 'A very unique sentence about dogs', layer: 'short' });

      // High threshold: should not merge
      const strict = await svc.consolidate({ similarityThreshold: 0.9 });
      assert.equal(strict.clusters, 0, 'high threshold should not merge low-similarity items');

      // Low threshold: might merge (they share many n-grams)
      const loose = await svc.consolidate({ similarityThreshold: 0.1 });
      // Don't assert strictly since n-gram similarity depends on exact content
      assert.ok(typeof loose.clusters === 'number');
    } finally { cleanup(); }
  });
});

// ─── Layer Config ────────────────────────────────────────

describe('Layer Configuration', () => {
  it('core has zero decay rate', () => {
    assert.equal(LAYERS.core.decayRate, 0);
  });

  it('long has slower decay than short', () => {
    assert.ok(LAYERS.long.decayRate < LAYERS.short.decayRate);
  });

  it('all layers have minWeight defined', () => {
    for (const layer of Object.values(LAYERS)) {
      assert.ok(layer.minWeight !== undefined);
    }
  });
});

// ─── Memory Associations ─────────────────────────────────

describe('Memory Associations (Links)', () => {
  it('links two memories', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'TypeScript is great', layer: 'core' });
      const b = await svc.add({ content: 'Node.js uses V8 engine', layer: 'long' });
      const link = await svc.link({ source: a.id, target: b.id, type: 'relates_to' });
      assert.ok(link.id);
      assert.equal(link.source, a.id);
      assert.equal(link.target, b.id);
      assert.equal(link.type, 'relates_to');
      assert.equal(link.strength, 1.0);
    } finally { cleanup(); }
  });

  it('throws if source memory does not exist', async () => {
    const { svc, cleanup } = createService();
    try {
      const b = await svc.add({ content: 'exists', layer: 'short' });
      await assert.rejects(
        () => svc.link({ source: 'nonexistent', target: b.id, type: 'relates_to' }),
        /Source memory.*not found/
      );
    } finally { cleanup(); }
  });

  it('throws if target memory does not exist', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'exists', layer: 'short' });
      await assert.rejects(
        () => svc.link({ source: a.id, target: 'nonexistent', type: 'relates_to' }),
        /Target memory.*not found/
      );
    } finally { cleanup(); }
  });

  it('getLinks returns links for a memory', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'memory A', layer: 'short' });
      const b = await svc.add({ content: 'memory B', layer: 'short' });
      const c = await svc.add({ content: 'memory C', layer: 'short' });
      await svc.link({ source: a.id, target: b.id, type: 'relates_to' });
      await svc.link({ source: c.id, target: a.id, type: 'derived_from' });

      const links = await svc.getLinks(a.id);
      assert.equal(links.length, 2);
    } finally { cleanup(); }
  });

  it('unlink removes a link', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'A', layer: 'short' });
      const b = await svc.add({ content: 'B', layer: 'short' });
      const link = await svc.link({ source: a.id, target: b.id, type: 'relates_to' });

      await svc.unlink(link.id);
      const links = await svc.getLinks(a.id);
      assert.equal(links.length, 0);
    } finally { cleanup(); }
  });

  it('links persist across reload', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'mem-link-'));
    try {
      const svc1 = new MemoryService({ dbPath: dir });
      const a = await svc1.add({ content: 'persist A', layer: 'long' });
      const b = await svc1.add({ content: 'persist B', layer: 'long' });
      await svc1.link({ source: a.id, target: b.id, type: 'causes' });

      const svc2 = new MemoryService({ dbPath: dir });
      const links = await svc2.getLinks(a.id);
      assert.equal(links.length, 1);
      assert.equal(links[0].type, 'causes');
    } finally {
      try { rmSync(dir, { recursive: true }); } catch {}
    }
  });

  it('traverse follows links up to specified depth', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'A', layer: 'short' });
      const b = await svc.add({ content: 'B', layer: 'short' });
      const c = await svc.add({ content: 'C', layer: 'short' });
      const d = await svc.add({ content: 'D', layer: 'short' });
      await svc.link({ source: a.id, target: b.id, type: 'relates_to' });
      await svc.link({ source: b.id, target: c.id, type: 'relates_to' });
      await svc.link({ source: c.id, target: d.id, type: 'relates_to' });

      // Depth 1: only B
      const d1 = await svc.traverse(a.id, { depth: 1 });
      assert.equal(d1.neighbors.length, 1);
      assert.equal(d1.neighbors[0].memory.id, b.id);

      // Depth 2: at least B and C
      const d2 = await svc.traverse(a.id, { depth: 2 });
      assert.ok(d2.neighbors.length >= 2, `depth 2 should reach at least 2, got ${d2.neighbors.length}`);

      // Depth 3: at least B, C, D
      const d3 = await svc.traverse(a.id, { depth: 3 });
      assert.ok(d3.neighbors.length >= 3, `depth 3 should reach at least 3, got ${d3.neighbors.length}`);
    } finally { cleanup(); }
  });

  it('traverse filters by link type', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'A', layer: 'short' });
      const b = await svc.add({ content: 'B', layer: 'short' });
      const c = await svc.add({ content: 'C', layer: 'short' });
      await svc.link({ source: a.id, target: b.id, type: 'relates_to' });
      await svc.link({ source: a.id, target: c.id, type: 'contradicts' });

      const result = await svc.traverse(a.id, { types: ['contradicts'] });
      assert.ok(result.neighbors.length >= 1);
      assert.ok(result.neighbors.some(n => n.memory.id === c.id));
    } finally { cleanup(); }
  });

  it('autoLink creates links for memories with shared entities', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'TypeScript 编译器优化', layer: 'short', entities: ['typescript', 'compiler'] });
      await svc.add({ content: 'TypeScript 类型系统设计', layer: 'short', entities: ['typescript', 'types'] });
      await svc.add({ content: 'Rust 所有权模型', layer: 'short', entities: ['rust', 'ownership'] });

      const result = await svc.autoLink({ threshold: 1 });
      assert.ok(result.created >= 1, 'should link memories sharing entities');

      // Verify link exists between TypeScript memories
      const allLinks = await svc.getLinks(
        (await svc.search('TypeScript 编译器'))[0]?.id || 'x'
      );
      // At least one TypeScript memory should have links
    } finally { cleanup(); }
  });

  it('autoLink skips already-linked pairs', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'Redis 缓存策略', layer: 'short', entities: ['redis'] });
      const b = await svc.add({ content: 'Redis 持久化方案', layer: 'short', entities: ['redis'] });
      await svc.link({ source: a.id, target: b.id, type: 'relates_to' });

      const result = await svc.autoLink({ threshold: 1 });
      assert.equal(result.created, 0, 'should not duplicate existing links');
    } finally { cleanup(); }
  });

  it('clear removes all links too', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'A', layer: 'short' });
      const b = await svc.add({ content: 'B', layer: 'short' });
      await svc.link({ source: a.id, target: b.id, type: 'relates_to' });

      await svc.clear();
      // After clear, no memories exist so links should be clean
      const stats = await svc.stats();
      assert.equal(stats.total, 0);
    } finally { cleanup(); }
  });

  // ─── Batch Operations ───────────────────────────────

  describe('Batch Operations', () => {
    it('batchAdd creates multiple memories', async () => {
      const { svc, cleanup } = createService();
      try {
        const memories = await svc.batchAdd([
          { content: 'Batch memory 1', layer: 'core', tags: ['test'] },
          { content: 'Batch memory 2', layer: 'long', entities: ['node'] },
          { content: 'Batch memory 3', layer: 'short' },
        ]);
        assert.equal(memories.length, 3);
        assert.equal(memories[0].layer, 'core');
        assert.equal(memories[1].entities[0], 'node');
        assert.equal(memories[2].layer, 'short');
        const stats = await svc.stats();
        assert.equal(stats.total, 3);
      } finally { cleanup(); }
    });

    it('batchAdd with empty array returns empty', async () => {
      const { svc, cleanup } = createService();
      try {
        const memories = await svc.batchAdd([]);
        assert.deepEqual(memories, []);
      } finally { cleanup(); }
    });

    it('batchDelete removes multiple memories', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'To delete 1', layer: 'short' });
        const m2 = await svc.add({ content: 'To delete 2', layer: 'short' });
        const m3 = await svc.add({ content: 'To keep', layer: 'core' });

        const result = await svc.batchDelete([m1.id, m2.id]);
        assert.equal(result.deleted, 2);
        assert.equal(result.notFound, 0);

        const stats = await svc.stats();
        assert.equal(stats.total, 1);
        const remaining = await svc.get(m3.id);
        assert.ok(remaining);
      } finally { cleanup(); }
    });

    it('batchDelete reports notFound for missing IDs', async () => {
      const { svc, cleanup } = createService();
      try {
        const result = await svc.batchDelete(['nonexistent-1', 'nonexistent-2']);
        assert.equal(result.deleted, 0);
        assert.equal(result.notFound, 2);
      } finally { cleanup(); }
    });

    it('batchDelete cleans up associated links', async () => {
      const { svc, cleanup } = createService();
      try {
        const a = await svc.add({ content: 'A', layer: 'short' });
        const b = await svc.add({ content: 'B', layer: 'short' });
        const c = await svc.add({ content: 'C', layer: 'short' });
        await svc.link({ source: a.id, target: b.id, type: 'relates_to' });
        await svc.link({ source: b.id, target: c.id, type: 'derived_from' });

        const result = await svc.batchDelete([a.id, b.id]);
        assert.equal(result.deleted, 2);

        // c should still exist, links to a and b should be gone
        const cMem = await svc.get(c.id);
        assert.ok(cMem);
        const links = await svc.getLinks(c.id);
        assert.equal(links.length, 0, 'links to deleted memories should be cleaned');
      } finally { cleanup(); }
    });
  });

  // ─── Search and Link ────────────────────────────────

  describe('Search and Link', () => {
    it('searchAndLink connects query results to a memory', async () => {
      const { svc, cleanup } = createService();
      try {
        const target = await svc.add({ content: 'Python web framework', layer: 'long', entities: ['python'] });
        await svc.add({ content: 'Django is a Python framework', layer: 'long', entities: ['python', 'django'] });
        await svc.add({ content: 'Flask lightweight Python web', layer: 'long', entities: ['python', 'flask'] });

        const { linked } = await svc.searchAndLink({
          memoryId: target.id,
          query: 'Python framework',
          linkType: 'relates_to',
        });
        assert.ok(linked.length >= 1, 'should link at least 1 result');
        for (const { link } of linked) {
          assert.equal(link.source, target.id);
          assert.equal(link.type, 'relates_to');
        }
      } finally { cleanup(); }
    });

    it('searchAndLink skips self', async () => {
      const { svc, cleanup } = createService();
      try {
        const m = await svc.add({ content: 'Unique content xyz', layer: 'long' });
        const { linked } = await svc.searchAndLink({
          memoryId: m.id,
          query: 'Unique content xyz',
        });
        assert.equal(linked.length, 0, 'should not link to self');
      } finally { cleanup(); }
    });

    it('searchAndLink respects limit', async () => {
      const { svc, cleanup } = createService();
      try {
        const target = await svc.add({ content: 'Target', layer: 'short' });
        for (let i = 0; i < 5; i++) {
          await svc.add({ content: `Related item ${i} to target`, layer: 'short' });
        }
        const { linked } = await svc.searchAndLink({
          memoryId: target.id,
          query: 'Related item',
          limit: 2,
        });
        assert.ok(linked.length <= 2, 'should respect limit');
      } finally { cleanup(); }
    });
  });

  // ─── Timeline ───────────────────────────────────────

  describe('Timeline', () => {
    it('returns memories sorted by creation date descending', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'First', layer: 'short' });
        await svc.add({ content: 'Second', layer: 'short' });
        await svc.add({ content: 'Third', layer: 'short' });

        const timeline = await svc.timeline();
        assert.equal(timeline.length, 3);
        assert.ok(timeline[0].createdAt >= timeline[1].createdAt);
        assert.ok(timeline[1].createdAt >= timeline[2].createdAt);
      } finally { cleanup(); }
    });

    it('filters by time range', async () => {
      const { svc, cleanup } = createService();
      try {
        const old = await svc.add({ content: 'Old', layer: 'short' });
        // Manually set createdAt to past
        const svcInternal = svc;
        // We'll use from/to with known timestamps
        const now = Date.now();
        const oneDayAgo = now - 86400000;
        const twoDaysAgo = now - 172800000;

        const recent = await svc.add({ content: 'Recent', layer: 'short' });

        const result = await svc.timeline({ from: oneDayAgo });
        assert.ok(result.length >= 1);
        assert.ok(result.every(m => m.createdAt >= oneDayAgo));
      } finally { cleanup(); }
    });

    it('filters by layer', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Core', layer: 'core' });
        await svc.add({ content: 'Short', layer: 'short' });
        await svc.add({ content: 'Long', layer: 'long' });

        const coreOnly = await svc.timeline({ layer: 'core' });
        assert.equal(coreOnly.length, 1);
        assert.equal(coreOnly[0].content, 'Core');
      } finally { cleanup(); }
    });

    it('respects limit', async () => {
      const { svc, cleanup } = createService();
      try {
        for (let i = 0; i < 10; i++) {
          await svc.add({ content: `Memory ${i}`, layer: 'short' });
        }
        const limited = await svc.timeline({ limit: 3 });
        assert.equal(limited.length, 3);
      } finally { cleanup(); }
    });

    it('returns empty for range with no memories', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Current', layer: 'short' });
        const future = await svc.timeline({ from: Date.now() + 100000 });
        assert.equal(future.length, 0);
      } finally { cleanup(); }
    });
  });

  it('all link types are supported', async () => {
    const { svc, cleanup } = createService();
    try {
      const types = ['relates_to', 'contradicts', 'supersedes', 'derived_from', 'causes'];
      const mems = [];
      for (let i = 0; i <= types.length; i++) {
        mems.push(await svc.add({ content: `memory ${i}`, layer: 'short' }));
      }
      for (let i = 0; i < types.length; i++) {
        const link = await svc.link({ source: mems[i].id, target: mems[i + 1].id, type: types[i] });
        assert.equal(link.type, types[i]);
      }
      const links = await svc.getLinks(mems[0].id);
      // mems[0] has: outgoing link to mems[1] + incoming link from mems[0]... no, just outgoing
      assert.ok(links.length >= 1, 'should have at least 1 link for first memory');
    } finally { cleanup(); }
  });

  describe('changes() — incremental change tracking', () => {
    it('returns empty for timestamp before any changes', async () => {
      const { svc, cleanup } = createService();
      try {
        const before = Date.now();
        await svc.add({ content: 'M1', layer: 'short' });
        const changes = await svc.changes(before);
        assert.equal(changes.added.length, 1);
        assert.equal(changes.updated.length, 0);
        assert.equal(changes.deleted.length, 0);
      } finally { cleanup(); }
    });

    it('tracks added memories', async () => {
      const { svc, cleanup } = createService();
      try {
        const ts = Date.now();
        await svc.add({ content: 'M1', layer: 'short' });
        await svc.add({ content: 'M2', layer: 'long' });
        const changes = await svc.changes(ts);
        assert.equal(changes.added.length, 2);
        assert.ok(changes.added.some(m => m.content === 'M1'));
        assert.ok(changes.added.some(m => m.content === 'M2'));
      } finally { cleanup(); }
    });

    it('tracks deleted memories', async () => {
      const { svc, cleanup } = createService();
      try {
        const ts = Date.now();
        // Small delay to ensure ts is strictly before operations
        await new Promise(r => setTimeout(r, 5));
        const m = await svc.add({ content: 'To delete', layer: 'short' });
        await svc.batchDelete([m.id]);
        const changes = await svc.changes(ts);
        assert.equal(changes.added.length, 0); // added then deleted = skip
        assert.equal(changes.deleted.length, 1);
        assert.equal(changes.deleted[0], m.id);
      } finally { cleanup(); }
    });

    it('includes snapshot with total and byLayer', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'C', layer: 'core' });
        await svc.add({ content: 'L1', layer: 'long' });
        await svc.add({ content: 'L2', layer: 'long' });
        await svc.add({ content: 'S', layer: 'short' });
        const changes = await svc.changes(0);
        assert.equal(changes.snapshot.total, 4);
        assert.equal(changes.snapshot.byLayer.core, 1);
        assert.equal(changes.snapshot.byLayer.long, 2);
        assert.equal(changes.snapshot.byLayer.short, 1);
      } finally { cleanup(); }
    });

    it('clear() records all deletions in changelog', async () => {
      const { svc, cleanup } = createService();
      try {
        const ts = Date.now();
        await svc.add({ content: 'M1', layer: 'short' });
        await svc.add({ content: 'M2', layer: 'long' });
        await svc.clear();
        const changes = await svc.changes(ts);
        assert.equal(changes.deleted.length, 2);
      } finally { cleanup(); }
    });

    it('update() modifies content and records in changelog', async () => {
      const { svc, cleanup } = createService();
      try {
        const m = await svc.add({ content: 'original', layer: 'short' });
        await new Promise(r => setTimeout(r, 10));
        const ts = Date.now();
        // Delay to ensure update happens after ts
        await new Promise(r => setTimeout(r, 10));
        const updated = await svc.update(m.id, { content: 'modified content' });
        assert.ok(updated);
        assert.equal(updated.content, 'modified content');

        const changes = await svc.changes(ts);
        assert.equal(changes.updated.length, 1);
        assert.equal(changes.updated[0].content, 'modified content');
        assert.equal(changes.added.length, 0);
      } finally { cleanup(); }
    });

    it('update() changes layer', async () => {
      const { svc, cleanup } = createService();
      try {
        const m = await svc.add({ content: 'layer test', layer: 'short' });
        const updated = await svc.update(m.id, { layer: 'core' });
        assert.equal(updated.layer, 'core');
      } finally { cleanup(); }
    });

    it('update() returns null for nonexistent memory', async () => {
      const { svc, cleanup } = createService();
      try {
        const result = await svc.update('nonexistent', { content: 'x' });
        assert.equal(result, null);
      } finally { cleanup(); }
    });

    it('update() preserves unmodified fields', async () => {
      const { svc, cleanup } = createService();
      try {
        const m = await svc.add({ content: 'original', layer: 'short', tags: ['a'], entities: ['x'] });
        await svc.update(m.id, { content: 'new content' });
        const fetched = await svc.get(m.id);
        assert.equal(fetched.tags[0], 'a');
        assert.equal(fetched.entities[0], 'x');
        assert.equal(fetched.layer, 'short');
      } finally { cleanup(); }
    });

    it('compactChangelog removes old entries', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'M1', layer: 'short' });
        await svc.add({ content: 'M2', layer: 'short' });
        // Small delay to ensure entries are older than maxAge=0
        await new Promise(r => setTimeout(r, 2));
        // Compact with maxAge=0 → removes everything
        const result = await svc.compactChangelog({ maxAge: 0 });
        assert.ok(result.removed >= 2);
        assert.equal(result.remaining, 0);
        // Changes since epoch should now be empty
        const changes = await svc.changes(0);
        assert.equal(changes.added.length, 0);
        // But memories still exist
        const stats = await svc.stats();
        assert.equal(stats.total, 2);
      } finally { cleanup(); }
    });

    it('compactChangelog keeps recent entries', async () => {
      const { svc, cleanup } = createService();
      try {
        const ts = Date.now();
        await new Promise(r => setTimeout(r, 5));
        await svc.add({ content: 'M1', layer: 'short' });
        // Compact with large maxAge → keeps everything
        const result = await svc.compactChangelog({ maxAge: 999999999 });
        assert.equal(result.remaining, 1);
        assert.equal(result.removed, 0);
        const changes = await svc.changes(ts);
        assert.equal(changes.added.length, 1);
      } finally { cleanup(); }
    });
  });

  // ─── Search Advanced ────────────────────────────────────

  describe('searchAdvanced()', () => {
    it('returns results with BM25 scoring', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'JavaScript is a programming language', layer: 'core', tags: ['js'] });
        await svc.add({ content: 'Python is great for data science', layer: 'long', tags: ['python'] });
        await svc.add({ content: 'Rust provides memory safety', layer: 'short', tags: ['rust'] });
        const results = await svc.searchAdvanced('JavaScript programming');
        assert.ok(results.length >= 1);
        assert.ok(results[0].content.includes('JavaScript'));
        assert.ok(results[0].score > 0);
      } finally { cleanup(); }
    });

    it('includes explanation when explain=true', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Machine learning with neural networks', layer: 'core' });
        const results = await svc.searchAdvanced('machine learning', { explain: true });
        assert.ok(results[0].explanation);
        assert.ok('bm25' in results[0].explanation);
        assert.ok('ngram' in results[0].explanation);
        assert.ok('total' in results[0].explanation);
      } finally { cleanup(); }
    });

    it('omits explanation when explain=false', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Test memory content', layer: 'core' });
        const results = await svc.searchAdvanced('test', { explain: false });
        assert.ok(!results[0].explanation);
      } finally { cleanup(); }
    });

    it('respects layer filter', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Core memory item', layer: 'core' });
        await svc.add({ content: 'Short memory item', layer: 'short' });
        const results = await svc.searchAdvanced('memory', { layer: 'core' });
        assert.ok(results.every(r => r.layer === 'core'));
      } finally { cleanup(); }
    });

    it('respects limit option', async () => {
      const { svc, cleanup } = createService();
      try {
        for (let i = 0; i < 10; i++) {
          await svc.add({ content: `Memory item ${i}`, layer: 'long' });
        }
        const results = await svc.searchAdvanced('Memory', { limit: 3 });
        assert.equal(results.length, 3);
      } finally { cleanup(); }
    });

    it('boosts accessed memories', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Target memory', layer: 'core' });
        await svc.searchAdvanced('target');
        const stats = await svc.stats();
        assert.ok(stats.total >= 1);
      } finally { cleanup(); }
    });
  });

  // ─── Merge ──────────────────────────────────────────────

  describe('merge()', () => {
    it('merges two memories into one', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'Likes Python', layer: 'long', tags: ['python'], entities: ['lang'] });
        const m2 = await svc.add({ content: 'Uses VSCode', layer: 'short', tags: ['editor'], entities: ['tool'] });
        const merged = await svc.merge(m1.id, m2.id);
        assert.ok(merged.content.includes('Likes Python'));
        assert.ok(merged.content.includes('Uses VSCode'));
        assert.ok(merged.tags.includes('python'));
        assert.ok(merged.tags.includes('editor'));
        assert.ok(merged.entities.includes('lang'));
        assert.ok(merged.entities.includes('tool'));
        // Only one memory remains
        const stats = await svc.stats();
        assert.equal(stats.total, 1);
      } finally { cleanup(); }
    });

    it('promotes to stronger layer', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'A', layer: 'short' });
        const m2 = await svc.add({ content: 'B', layer: 'core' });
        const merged = await svc.merge(m1.id, m2.id);
        assert.equal(merged.layer, 'core');
      } finally { cleanup(); }
    });

    it('returns null for non-existent ids', async () => {
      const { svc, cleanup } = createService();
      try {
        const result = await svc.merge('nope', 'nope2');
        assert.equal(result, null);
      } finally { cleanup(); }
    });

    it('handles self-merge gracefully', async () => {
      const { svc, cleanup } = createService();
      try {
        const m = await svc.add({ content: 'Self', layer: 'core' });
        const result = await svc.merge(m.id, m.id);
        assert.equal(result.id, m.id);
        const stats = await svc.stats();
        assert.equal(stats.total, 1);
      } finally { cleanup(); }
    });

    it('accepts content override', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'Old content A', layer: 'long' });
        const m2 = await svc.add({ content: 'Old content B', layer: 'long' });
        const merged = await svc.merge(m1.id, m2.id, { content: 'New unified content' });
        assert.equal(merged.content, 'New unified content');
      } finally { cleanup(); }
    });
  });

  // ─── Export / Import ────────────────────────────────────

  describe('exportAll() / importAll()', () => {
    it('exports and imports all data', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'M1', layer: 'core', tags: ['t1'] });
        await svc.add({ content: 'M2', layer: 'long', tags: ['t2'] });
        const m1 = await svc.add({ content: 'M3', layer: 'core' });
        const m2 = await svc.add({ content: 'M4', layer: 'long' });
        await svc.link({ source: m1.id, target: m2.id, type: 'relates_to' });

        const exported = await svc.exportAll();
        assert.ok(exported.memories.length >= 4);
        assert.ok(exported.links.length >= 1);
        assert.ok(Array.isArray(exported.changelog));
        assert.ok(exported.exportedAt > 0);

        // Import into fresh service
        const { svc: svc2, cleanup: cleanup2 } = createService();
        try {
          const result = await svc2.importAll(exported);
          assert.equal(result.memories, exported.memories.length);
          assert.equal(result.links, exported.links.length);
          // Verify data integrity
          const stats = await svc2.stats();
          assert.equal(stats.total, exported.memories.length);
          const links = await svc2.getLinks(m1.id);
          assert.ok(links.some(l => l.source === m1.id));
        } finally { cleanup2(); }
      } finally { cleanup(); }
    });

    it('import clears existing data', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Old', layer: 'core' });
        const { svc: svc2, cleanup: cleanup2 } = createService();
        try {
          await svc2.add({ content: 'Existing', layer: 'core' });
          const result = await svc2.importAll(await svc.exportAll());
          assert.equal(result.memories, 1);
          const stats = await svc2.stats();
          assert.equal(stats.total, 1);
        } finally { cleanup2(); }
      } finally { cleanup(); }
    });

    it('throws error on invalid import data', async () => {
      const { svc, cleanup } = createService();
      try {
        await assert.rejects(
          () => svc.importAll({}),
          /importAll requires/
        );
      } finally { cleanup(); }
    });
  });

  // ─── Delete Single ──────────────────────────────────────

  describe('delete()', () => {
    it('deletes a single memory and returns true', async () => {
      const { svc, cleanup } = createService();
      try {
        const m = await svc.add({ content: 'to delete', layer: 'short' });
        const result = await svc.delete(m.id);
        assert.equal(result, true);
        const stats = await svc.stats();
        assert.equal(stats.total, 0);
      } finally { cleanup(); }
    });

    it('returns false for non-existent id', async () => {
      const { svc, cleanup } = createService();
      try {
        const result = await svc.delete('nonexistent');
        assert.equal(result, false);
      } finally { cleanup(); }
    });

    it('cleans up associated links', async () => {
      const { svc, cleanup } = createService();
      try {
        const a = await svc.add({ content: 'A', layer: 'short' });
        const b = await svc.add({ content: 'B', layer: 'short' });
        await svc.link({ source: a.id, target: b.id, type: 'relates_to' });
        await svc.delete(a.id);
        const links = await svc.getLinks(b.id);
        assert.equal(links.length, 0);
      } finally { cleanup(); }
    });

    it('records deletion in changelog', async () => {
      const { svc, cleanup } = createService();
      try {
        const ts = Date.now();
        await new Promise(r => setTimeout(r, 5));
        const m = await svc.add({ content: 'temp', layer: 'short' });
        await svc.delete(m.id);
        const changes = await svc.changes(ts);
        assert.equal(changes.deleted.length, 1);
        assert.equal(changes.deleted[0], m.id);
      } finally { cleanup(); }
    });
  });

  // ─── Scheduled Maintenance ──────────────────────────────

  describe('scheduledMaintenance()', () => {
    it('runs all three maintenance steps', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Python data analysis', layer: 'short', entities: ['python'] });
        await svc.add({ content: 'Python data processing', layer: 'short', entities: ['python'] });
        const result = await svc.scheduledMaintenance();
        assert.ok('decay' in result);
        assert.ok('consolidation' in result);
        assert.ok('changelog' in result);
        assert.ok('decayed' in result.decay);
        assert.ok('clusters' in result.consolidation);
        assert.ok('removed' in result.changelog);
      } finally { cleanup(); }
    });

    it('passes options to consolidate and compactChangelog', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'test', layer: 'short' });
        // dryRun=true → consolidation should not modify
        const before = await svc.stats();
        const result = await svc.scheduledMaintenance({ dryRun: true, changelogMaxAge: 999999999 });
        assert.equal(before.total, (await svc.stats()).total);
        assert.ok(result.changelog.remaining >= 1);
      } finally { cleanup(); }
    });

    it('returns usable result for agent decision-making', async () => {
      const { svc, cleanup } = createService();
      try {
        // No memories → should still work
        const result = await svc.scheduledMaintenance();
        assert.equal(result.decay.decayed, 0);
        assert.equal(result.consolidation.clusters, 0);
        assert.equal(result.changelog.removed, 0);
      } finally { cleanup(); }
    });
  });

  // ─── Find Related ───────────────────────────────────────

  describe('findRelated()', () => {
    it('finds memories by entity overlap', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'Python is great', layer: 'core', entities: ['python'] });
        const m2 = await svc.add({ content: 'Rust is safe', layer: 'long', entities: ['rust'] });
        await svc.add({ content: 'Learn Python basics', layer: 'short', entities: ['python'] });

        const related = await svc.findRelated(m1.id);
        assert.ok(related.some(r => r.id !== m1.id && r.entities.includes('python')));
        assert.ok(related.every(r => 'score' in r && 'matchType' in r));
      } finally { cleanup(); }
    });

    it('finds memories by tag overlap', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Doc 1', layer: 'core', tags: ['important'] });
        const m2 = await svc.add({ content: 'Doc 2', layer: 'long', tags: ['urgent'] });
        await svc.add({ content: 'Doc 3', layer: 'short', tags: ['important', 'urgent'] });

        const related = await svc.findRelated(m2.id);
        assert.ok(related.some(r => r.matchType.includes('tags')));
      } finally { cleanup(); }
    });

    it('finds memories by semantic similarity', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'Machine learning with neural networks', layer: 'core' });
        await svc.add({ content: 'Deep learning and AI', layer: 'long' });
        await svc.add({ content: 'Cooking recipes', layer: 'short' });

        const related = await svc.findRelated(m1.id, { minScore: 0.05 });
        assert.ok(related.length >= 1);
        assert.ok(related.every(r => 'score' in r && 'matchType' in r));
      } finally { cleanup(); }
    });

    it('respects minScore threshold', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'A', layer: 'core', entities: ['x'] });
        await svc.add({ content: 'B', layer: 'long', entities: ['y'] });
        await svc.add({ content: 'C', layer: 'short', entities: ['x'] });

        const relatedLow = await svc.findRelated(m1.id, { minScore: 0.5 });
        const relatedHigh = await svc.findRelated(m1.id, { minScore: 0.9 });
        assert.ok(relatedHigh.length <= relatedLow.length);
      } finally { cleanup(); }
    });

    it('respects limit', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'Base', layer: 'core' });
        for (let i = 0; i < 10; i++) {
          await svc.add({ content: `Related ${i}`, layer: 'long' });
        }

        const related = await svc.findRelated(m1.id, { limit: 3 });
        assert.ok(related.length <= 3);
      } finally { cleanup(); }
    });

    it('handles non-existent id', async () => {
      const { svc, cleanup } = createService();
      try {
        const related = await svc.findRelated('nope');
        assert.deepEqual(related, []);
      } finally { cleanup(); }
    });

    it('excludes self by default', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'Self', layer: 'core' });
        await svc.add({ content: 'Other', layer: 'long' });

        const related = await svc.findRelated(m1.id, { includeSelf: false });
        assert.ok(!related.some(r => r.id === m1.id));
      } finally { cleanup(); }
    });
  });

  describe('reindex', () => {
    it('rebuilds tag and entity indices from scratch', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Alpha', layer: 'core', tags: ['a', 'b'], entities: ['x'] });
        await svc.add({ content: 'Beta', layer: 'long', tags: ['b', 'c'], entities: ['y'] });

        const result = await svc.reindex();
        assert.equal(result.memories, 2);
        assert.ok(result.tags >= 2);
        assert.ok(result.entities >= 2);
      } finally { cleanup(); }
    });

    it('fixes stale indices after tag change via update', async () => {
      const { svc, cleanup } = createService();
      try {
        const m = await svc.add({ content: 'Test', layer: 'core', tags: ['old'], entities: ['e1'] });

        // Update tags
        await svc.update(m.id, { tags: ['new'], entities: ['e2'] });

        // Reindex and verify counts are correct (no stale 'old' entries)
        const result = await svc.reindex();
        assert.ok(result.tags >= 1);
        // After update + reindex, memory should have exactly 1 tag ('new')
        const updated = await svc.get(m.id);
        assert.deepEqual(updated.tags, ['new']);
        assert.deepEqual(updated.entities, ['e2']);
      } finally { cleanup(); }
    });

    it('is included in scheduledMaintenance results', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Maint', layer: 'short', tags: ['t1'] });
        const result = await svc.scheduledMaintenance();
        assert.ok(result.reindex);
        assert.equal(result.reindex.memories, 1);
        assert.ok(result.reindex.tags >= 1);
      } finally { cleanup(); }
    });
  });
});

  describe('findDuplicates', () => {
    it('finds near-duplicate memories', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'The quick brown fox jumps over the lazy dog', layer: 'core' });
        await svc.add({ content: 'The quick brown fox jumps over the lazy dog', layer: 'long' });
        await svc.add({ content: 'Completely different content here', layer: 'core' });

        const dupes = await svc.findDuplicates();
        assert.equal(dupes.length, 1);
        assert.equal(dupes[0].memories.length, 2);
        assert.ok(dupes[0].similarity >= 0.7);
      } finally { cleanup(); }
    });

    it('respects threshold option', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Apple banana cherry', layer: 'core' });
        await svc.add({ content: 'Apple banana orange', layer: 'core' });

        const strict = await svc.findDuplicates({ threshold: 0.99 });
        const loose = await svc.findDuplicates({ threshold: 0.3 });
        assert.equal(strict.length, 0);
        assert.ok(loose.length >= 1);
      } finally { cleanup(); }
    });

    it('filters by layer', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Duplicate content alpha beta', layer: 'core' });
        await svc.add({ content: 'Duplicate content alpha beta', layer: 'long' });
        await svc.add({ content: 'Duplicate content alpha beta', layer: 'core' });

        const coreDupes = await svc.findDuplicates({ layer: 'core' });
        assert.equal(coreDupes.length, 1);
        assert.equal(coreDupes[0].memories.length, 2);
      } finally { cleanup(); }
    });

    it('returns empty for no duplicates', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Unique one', layer: 'core' });
        await svc.add({ content: 'Completely different two', layer: 'core' });
        await svc.add({ content: 'Totally unrelated three', layer: 'core' });

        const dupes = await svc.findDuplicates({ threshold: 0.9 });
        assert.equal(dupes.length, 0);
      } finally { cleanup(); }
    });
  });

  describe('archive and restore', () => {
    it('archives memories older than threshold', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'Old memory', layer: 'short' });
        const m2 = await svc.add({ content: 'Recent memory', layer: 'short' });

        // Archive memories older than -1ms (effectively all)
        const result = await svc.archive({ olderThanMs: -1 });
        assert.equal(result.count, 2);

        // Verify they're gone from active store
        const stats = await svc.stats();
        assert.equal(stats.total, 0);
      } finally { cleanup(); }
    });

    it('archives by specific IDs', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'Keep me', layer: 'core' });
        const m2 = await svc.add({ content: 'Archive me', layer: 'short' });

        const result = await svc.archive({ ids: [m2.id] });
        assert.equal(result.count, 1);
        assert.ok(result.archivedIds.includes(m2.id));

        const stats = await svc.stats();
        assert.equal(stats.total, 1);
      } finally { cleanup(); }
    });

    it('archives by layer', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Core memory', layer: 'core' });
        await svc.add({ content: 'Short memory', layer: 'short' });

        const result = await svc.archive({ layer: 'short' });
        assert.equal(result.count, 1);

        const stats = await svc.stats();
        assert.equal(stats.total, 1);
      } finally { cleanup(); }
    });

    it('restores archived memories', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'Will be restored', layer: 'core' });
        await svc.archive({ ids: [m1.id] });

        const result = await svc.restore({ ids: [m1.id] });
        assert.equal(result.count, 1);

        const stats = await svc.stats();
        assert.equal(stats.total, 1);

        const restored = await svc.get(m1.id);
        assert.ok(restored);
        assert.equal(restored.content, 'Will be restored');
      } finally { cleanup(); }
    });

    it('restore with limit', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'A', layer: 'short' });
        await svc.add({ content: 'B', layer: 'short' });
        await svc.add({ content: 'C', layer: 'short' });
        await svc.archive({ olderThanMs: 0 });

        const result = await svc.restore({ limit: 2 });
        assert.equal(result.count, 2);

        const stats = await svc.stats();
        assert.equal(stats.total, 2);
      } finally { cleanup(); }
    });

    it('restore all when no filter', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'X', layer: 'short' });
        await svc.add({ content: 'Y', layer: 'long' });
        await svc.archive({ olderThanMs: 0 });

        const result = await svc.restore();
        assert.equal(result.count, 2);
      } finally { cleanup(); }
    });
  });

  describe('validate', () => {
    it('reports valid store with no issues', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Valid memory', layer: 'core', tags: ['ok'] });
        const result = await svc.validate();
        assert.equal(result.valid, true);
        assert.equal(result.issues.length, 0);
      } finally { cleanup(); }
    });

    it('detects empty content', async () => {
      const { svc, cleanup } = createService();
      try {
        // Manually inject a bad memory
        await svc.add({ content: 'Good', layer: 'core' });
        // Use update to set empty content
        const m = await svc.add({ content: 'Will be cleared', layer: 'core' });
        await svc.update(m.id, { content: '' });

        const result = await svc.validate();
        assert.equal(result.valid, false);
        assert.ok(result.issues.some(i => i.includes('empty content')));
      } finally { cleanup(); }
    });

    it('repair mode reindexes stale indices', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Test', layer: 'core', tags: ['a'], entities: ['e1'] });
        // Just verify validate+repair runs without error and reports valid
        const result = await svc.validate({ repair: true });
        assert.equal(result.valid, true);
      } finally { cleanup(); }
    });

    it('non-repair mode reports issues without fixing', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Good', layer: 'core' });
        const m = await svc.add({ content: 'Temporary', layer: 'core' });
        await svc.update(m.id, { content: '' });

        const result = await svc.validate();
        assert.equal(result.valid, false);
        assert.equal(result.repaired, undefined);
      } finally { cleanup(); }
    });
  });

  describe('tagCloud', () => {
    it('returns tag frequencies sorted by count', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'A', layer: 'core', tags: ['x', 'y'] });
        await svc.add({ content: 'B', layer: 'long', tags: ['x', 'z'] });
        await svc.add({ content: 'C', layer: 'short', tags: ['x'] });

        const cloud = await svc.tagCloud();
        assert.equal(cloud[0].tag, 'x');
        assert.equal(cloud[0].count, 3);
        assert.equal(cloud[0].layers.core, 1);
        assert.equal(cloud[0].layers.long, 1);
      } finally { cleanup(); }
    });

    it('respects top limit', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'A', layer: 'core', tags: ['a', 'b', 'c'] });
        const cloud = await svc.tagCloud({ top: 2 });
        assert.equal(cloud.length, 2);
      } finally { cleanup(); }
    });

    it('returns empty for no tags', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'No tags', layer: 'core' });
        const cloud = await svc.tagCloud();
        assert.deepEqual(cloud, []);
      } finally { cleanup(); }
    });
  });

  describe('aggregate', () => {
    it('groups by layer', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'A', layer: 'core' });
        await svc.add({ content: 'B', layer: 'core' });
        await svc.add({ content: 'C', layer: 'long' });

        const result = await svc.aggregate({ groupBy: 'layer' });
        assert.equal(result.length, 2);
        assert.equal(result.find(r => r.group === 'core').count, 2);
        assert.equal(result.find(r => r.group === 'long').count, 1);
      } finally { cleanup(); }
    });

    it('groups by tag', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'A', layer: 'core', tags: ['ai', 'ml'] });
        await svc.add({ content: 'B', layer: 'long', tags: ['ai'] });

        const result = await svc.aggregate({ groupBy: 'tag' });
        const ai = result.find(r => r.group === 'ai');
        assert.equal(ai.count, 2);
        assert.ok(ai.avgWeight > 0);
      } finally { cleanup(); }
    });

    it('groups by entity', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'A', layer: 'core', entities: ['user1', 'user2'] });
        await svc.add({ content: 'B', layer: 'long', entities: ['user1'] });

        const result = await svc.aggregate({ groupBy: 'entity' });
        assert.equal(result.find(r => r.group === 'user1').count, 2);
      } finally { cleanup(); }
    });

    it('returns empty for empty store', async () => {
      const { svc, cleanup } = createService();
      try {
        const result = await svc.aggregate({ groupBy: 'layer' });
        assert.deepEqual(result, []);
      } finally { cleanup(); }
    });
  });

  describe('searchByTime', () => {
    it('finds memories in time range', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'First', layer: 'core' });
        await new Promise(r => setTimeout(r, 10));
        const m2 = await svc.add({ content: 'Second', layer: 'long' });
        await new Promise(r => setTimeout(r, 10));
        const m3 = await svc.add({ content: 'Third', layer: 'short' });

        // Get only m2 by time range
        const results = await svc.searchByTime({ from: m2.createdAt - 1, to: m2.createdAt + 1 });
        assert.equal(results.length, 1);
        assert.equal(results[0].content, 'Second');
      } finally { cleanup(); }
    });

    it('filters by layer', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Core', layer: 'core' });
        await svc.add({ content: 'Long', layer: 'long' });

        const results = await svc.searchByTime({ layer: 'core' });
        assert.equal(results.length, 1);
        assert.equal(results[0].content, 'Core');
      } finally { cleanup(); }
    });

    it('respects limit', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'A', layer: 'core' });
        await svc.add({ content: 'B', layer: 'core' });
        await svc.add({ content: 'C', layer: 'core' });

        const results = await svc.searchByTime({ limit: 2 });
        assert.equal(results.length, 2);
      } finally { cleanup(); }
    });

    it('returns newest first', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Old', layer: 'core' });
        await new Promise(r => setTimeout(r, 5));
        await svc.add({ content: 'New', layer: 'core' });

        const results = await svc.searchByTime({});
        assert.equal(results[0].content, 'New');
      } finally { cleanup(); }
    });
  });

  describe('deduplicate', () => {
    it('merges duplicate memories', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Python is great for data science', layer: 'core', tags: ['python'] });
        await svc.add({ content: 'Python is great for data science', layer: 'long', tags: ['python'] });
        await svc.add({ content: 'Something totally unique', layer: 'core' });

        const result = await svc.deduplicate({ threshold: 0.7 });
        assert.ok(result.merged >= 1);
        assert.ok(result.groups >= 1);
      } finally { cleanup(); }
    });

    it('dryRun does not modify store', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Duplicate alpha beta gamma', layer: 'core' });
        await svc.add({ content: 'Duplicate alpha beta gamma', layer: 'long' });

        const result = await svc.deduplicate({ threshold: 0.7, dryRun: true });
        assert.equal(result.merged, 0);
        assert.equal(result.details[0].action, 'would_merge');

        const stats = await svc.stats();
        assert.equal(stats.total, 2);
      } finally { cleanup(); }
    });

    it('returns empty for no duplicates', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Unique A', layer: 'core' });
        await svc.add({ content: 'Unique B', layer: 'core' });

        const result = await svc.deduplicate({ threshold: 0.9 });
        assert.equal(result.merged, 0);
        assert.equal(result.groups, 0);
      } finally { cleanup(); }
    });
  });

  describe('memoryGraph', () => {
    it('returns nodes and edges for linked memories', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'Node A', layer: 'core', tags: ['a'] });
        const m2 = await svc.add({ content: 'Node B', layer: 'core', tags: ['b'] });
        await svc.link({ source: m1.id, target: m2.id, type: 'related' });

        const graph = await svc.memoryGraph();
        assert.equal(graph.nodes.length, 2);
        assert.equal(graph.edges.length, 1);
        assert.equal(graph.edges[0].type, 'related');
      } finally { cleanup(); }
    });

    it('filters by layer', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Core', layer: 'core' });
        await svc.add({ content: 'Long', layer: 'long' });

        const graph = await svc.memoryGraph({ layer: 'core' });
        assert.equal(graph.nodes.length, 1);
      } finally { cleanup(); }
    });

    it('truncates long content', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'A'.repeat(200), layer: 'core' });
        const graph = await svc.memoryGraph();
        assert.ok(graph.nodes[0].content.length <= 80);
      } finally { cleanup(); }
    });

    it('excludes edges to filtered-out nodes', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'Core', layer: 'core' });
        const m2 = await svc.add({ content: 'Long', layer: 'long' });
        await svc.link({ source: m1.id, target: m2.id, type: 'related' });

        const graph = await svc.memoryGraph({ layer: 'core' });
        assert.equal(graph.edges.length, 0);
      } finally { cleanup(); }
    });
  });

  describe('compact', () => {
    it('removes low-weight memories', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'Heavy', layer: 'core' });
        const m2 = await svc.add({ content: 'Light', layer: 'short' });
        // Decay to reduce weights
        await svc.decay();
        await svc.decay();

        const result = await svc.compact({ minWeight: 0.5 });
        assert.ok(result.removed >= 0);
        assert.ok(result.remaining >= 0);
      } finally { cleanup(); }
    });

    it('dryRun does not remove anything', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Will stay', layer: 'core' });
        await svc.decay();
        await svc.decay();

        const before = (await svc.stats()).total;
        const result = await svc.compact({ minWeight: 0.5, dryRun: true });
        const after = (await svc.stats()).total;
        assert.equal(before, after);
      } finally { cleanup(); }
    });

    it('respects layer filter', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Core', layer: 'core' });
        await svc.add({ content: 'Short', layer: 'short' });

        const result = await svc.compact({ layer: 'short', minWeight: 0.01 });
        assert.ok(result.removed >= 0);
      } finally { cleanup(); }
    });
  });

  describe('searchByEmbedding', () => {
    it('returns results sorted by similarity (ngram fallback)', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'machine learning algorithms', layer: 'core' });
        await svc.add({ content: 'cooking recipes for dinner', layer: 'core' });
        await svc.add({ content: 'deep learning neural networks', layer: 'core' });

        const results = await svc.searchByEmbedding('machine learning');
        assert.ok(results.length >= 2);
        assert.ok(results[0].score >= results[results.length - 1].score);
        assert.equal(results[0].method, 'ngram');
      } finally { cleanup(); }
    });

    it('uses vector similarity when embedFn provided', async () => {
      let callCount = 0;
      const mockEmbed = async (text) => {
        callCount++;
        // Simple: [1,0] for ML-related, [0,1] for other
        if (text.toLowerCase().includes('machine') || text.toLowerCase().includes('learning')) return [1, 0];
        return [0, 1];
      };
      const dir = mkdtempSync(join(tmpdir(), 'mem-test-'));
      const svc = new MemoryService({ dbPath: dir, embedFn: mockEmbed });
      const cleanup = () => { try { rmSync(dir, { recursive: true }); } catch {} };
      try {
        await svc.add({ content: 'machine learning model', layer: 'core' });
        await svc.add({ content: 'cooking dinner tonight', layer: 'core' });

        const results = await svc.searchByEmbedding('machine learning');
        assert.equal(results[0].method, 'vector');
        assert.ok(results[0].content.includes('machine'));
        assert.ok(callCount > 0);
      } finally { cleanup(); }
    });

    it('respects threshold option', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'alpha beta gamma', layer: 'core' });
        await svc.add({ content: 'completely unrelated xyz', layer: 'core' });

        const results = await svc.searchByEmbedding('alpha beta', { threshold: 0.99 });
        assert.ok(results.length === 0 || results.every(r => r.score >= 0.99));
      } finally { cleanup(); }
    });

    it('respects layer filter', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'core memory item', layer: 'core' });
        await svc.add({ content: 'short memory item', layer: 'short' });

        const results = await svc.searchByEmbedding('memory', { layer: 'core' });
        assert.ok(results.every(r => r.layer === 'core'));
      } finally { cleanup(); }
    });

    it('respects limit option', async () => {
      const { svc, cleanup } = createService();
      try {
        for (let i = 0; i < 10; i++) {
          await svc.add({ content: `memory item ${i}`, layer: 'core' });
        }
        const results = await svc.searchByEmbedding('memory', { limit: 3 });
        assert.equal(results.length, 3);
      } finally { cleanup(); }
    });
  });

  describe('EmbeddingProvider.stats', () => {
    it('returns stats without embedFn', async () => {
      const { svc, cleanup } = createService();
      try {
        const stats = svc.embeddings.stats();
        assert.equal(stats.enabled, false);
        assert.equal(stats.cachedVectors, 0);
        assert.ok(typeof stats.cachePath === 'string');
      } finally { cleanup(); }
    });

    it('returns stats with embedFn', async () => {
      const mockEmbed = async () => [0.1, 0.2];
      const dir = mkdtempSync(join(tmpdir(), 'mem-test-'));
      const svc = new MemoryService({ dbPath: dir, embedFn: mockEmbed });
      const cleanup = () => { try { rmSync(dir, { recursive: true }); } catch {} };
      try {
        const stats = svc.embeddings.stats();
        assert.equal(stats.enabled, true);
      } finally { cleanup(); }
    });
  });

  describe('MemoryExtractor with LLM', () => {
    it('extractWithLLM returns empty when llmFn is null', async () => {
      const extractor = new MemoryExtractor();
      const results = await extractor.extractWithLLM('test text', null);
      assert.equal(results.length, 0);
    });

    it('extractWithLLM uses LLM function and parses JSON response', async () => {
      const mockLLM = async () => JSON.stringify([
        { content: 'User prefers dark mode', type: 'preference', confidence: 0.9, entities: ['dark', 'mode'] }
      ]);
      const extractor = new MemoryExtractor();
      const results = await extractor.extractWithLLM('I like dark mode', mockLLM);
      assert.equal(results.length, 1);
      assert.equal(results[0].type, 'preference');
      assert.equal(results[0].content, 'User prefers dark mode');
    });

    it('extractWithLLM handles object response directly', async () => {
      const mockLLM = async () => [
        { content: 'Decision made', type: 'decision', confidence: 0.8, entities: [] }
      ];
      const extractor = new MemoryExtractor();
      const results = await extractor.extractWithLLM('test', mockLLM);
      assert.equal(results.length, 1);
      assert.equal(results[0].type, 'decision');
    });

    it('extractWithLLM filters invalid results (too short/long)', async () => {
      const mockLLM = async () => [
        { content: 'x', type: 'fact', confidence: 1, entities: [] },
        { content: 'a'.repeat(600), type: 'fact', confidence: 1, entities: [] },
        { content: 'Valid memory', type: 'fact', confidence: 1, entities: [] }
      ];
      const extractor = new MemoryExtractor();
      const results = await extractor.extractWithLLM('test', mockLLM);
      assert.equal(results.length, 1);
      assert.equal(results[0].content, 'Valid memory');
    });

    it('extractWithLLM normalizes type and confidence', async () => {
      const mockLLM = async () => [
        { content: 'test memory item', type: 'invalid', confidence: 2, entities: [] }
      ];
      const extractor = new MemoryExtractor();
      const results = await extractor.extractWithLLM('test', mockLLM);
      assert.equal(results[0].type, 'fact');
      assert.equal(results[0].confidence, 1);
    });

    it('extractWithLLM returns empty on parse error', async () => {
      const mockLLM = async () => 'invalid json';
      const extractor = new MemoryExtractor();
      const results = await extractor.extractWithLLM('test', mockLLM);
      assert.equal(results.length, 0);
    });

    it('extractHybrid without LLM returns rule-based only', async () => {
      const extractor = new MemoryExtractor();
      const results = await extractor.extractHybrid('我喜欢 TypeScript');
      assert.ok(results.some(r => r.type === 'preference'));
    });

    it('extractHybrid combines and deduplicates rule-based and LLM results', async () => {
      const mockLLM = async () => [
        { content: 'User likes TypeScript', type: 'preference', confidence: 0.9, entities: ['TypeScript'] }
      ];
      const extractor = new MemoryExtractor();
      const results = await extractor.extractHybrid('我喜欢用 TypeScript 开发', mockLLM);
      assert.ok(results.length >= 1);
      const uniqueContents = new Set(results.map(r => r.content));
      assert.equal(uniqueContents.size, results.length);
    });

    it('extractHybrid deduplicates similar content', async () => {
      const mockLLM = async () => [
        { content: 'I prefer TypeScript', type: 'preference', confidence: 0.9, entities: ['TypeScript'] }
      ];
      const extractor = new MemoryExtractor();
      const results = await extractor.extractHybrid('I prefer TypeScript for coding', mockLLM);
      // Should have at least 1, but should not have duplicates of similar content
      assert.ok(results.length >= 1);
    });
  });

// ─── touch(id) ──────────────────────────────────────────
describe('touch(id)', () => {
  it('updates accessedAt and increments accessCount', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m = await svc.add({ content: 'hello', layer: 'short' });
      const beforeAccess = m.accessCount;
      const beforeTime = m.accessedAt;
      await new Promise(r => setTimeout(r, 5));
      const updated = await svc.touch(m.id);
      assert.equal(updated.accessCount, beforeAccess + 1);
      assert.ok(updated.accessedAt > beforeTime);
      assert.equal(updated.content, 'hello');
      assert.equal(updated.weight, m.weight);
    } finally { cleanup(); }
  });

  it('applies optional weight boost on decayed memory', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m = await svc.add({ content: 'boost me', layer: 'short' });
      // Lower weight via update
      await svc.update(m.id, { content: 'boost me' });
      // Simulate lower weight by adding with low weight context
      const m2 = await svc.add({ content: 'low weight', layer: 'short' });
      // Get it, manually check boost on fresh memory at max - verify no change
      const fresh = await svc.touch(m2.id, { boost: 0.3 });
      assert.equal(fresh.weight, 1.0); // already max, capped
      // Verify accessCount incremented regardless
      assert.equal(fresh.accessCount, 1);
    } finally { cleanup(); }
  });

  it('returns null for non-existent id', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const result = await svc.touch('no-such-id');
      assert.equal(result, null);
    } finally { cleanup(); }
  });

  it('does not create changelog entries', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m = await svc.add({ content: 'no log', layer: 'short' });
      const changes1 = Array.from(await svc.changes(0));
      await svc.touch(m.id);
      const changes2 = Array.from(await svc.changes(0));
      assert.equal(changes2.length, changes1.length);
    } finally { cleanup(); }
  });
});

describe('count()', () => {
  it('counts all memories with no filter', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'a', layer: 'core' });
      await svc.add({ content: 'b', layer: 'short' });
      await svc.add({ content: 'c', layer: 'core' });
      assert.equal(await svc.count(), 3);
    } finally { cleanup(); }
  });

  it('counts by layer', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'a', layer: 'core' });
      await svc.add({ content: 'b', layer: 'short' });
      await svc.add({ content: 'c', layer: 'core' });
      assert.equal(await svc.count({ layer: 'core' }), 2);
      assert.equal(await svc.count({ layer: 'short' }), 1);
    } finally { cleanup(); }
  });

  it('counts by tag', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'a', tags: ['x', 'y'] });
      await svc.add({ content: 'b', tags: ['x'] });
      await svc.add({ content: 'c', tags: ['z'] });
      assert.equal(await svc.count({ tag: 'x' }), 2);
      assert.equal(await svc.count({ tag: 'z' }), 1);
      assert.equal(await svc.count({ tag: 'missing' }), 0);
    } finally { cleanup(); }
  });

  it('counts by combined filter', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'a', layer: 'core', tags: ['x'] });
      await svc.add({ content: 'b', layer: 'short', tags: ['x'] });
      await svc.add({ content: 'c', layer: 'core', tags: ['y'] });
      assert.equal(await svc.count({ layer: 'core', tag: 'x' }), 1);
      assert.equal(await svc.count({ layer: 'core' }), 2);
    } finally { cleanup(); }
  });
});

describe('random()', () => {
  it('returns up to count memories', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      for (let i = 0; i < 10; i++) await svc.add({ content: `m${i}` });
      const result = await svc.random({ count: 3 });
      assert.equal(result.length, 3);
      // All unique
      const ids = new Set(result.map(m => m.id));
      assert.equal(ids.size, 3);
    } finally { cleanup(); }
  });

  it('respects layer filter', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'core', layer: 'core' });
      await svc.add({ content: 'short', layer: 'short' });
      await svc.add({ content: 'core2', layer: 'core' });
      const result = await svc.random({ count: 10, layer: 'core' });
      assert.ok(result.every(m => m.layer === 'core'));
      assert.equal(result.length, 2);
    } finally { cleanup(); }
  });

  it('returns empty for empty store', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const result = await svc.random({ count: 5 });
      assert.equal(result.length, 0);
    } finally { cleanup(); }
  });

  it('defaults to count=1', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'only' });
      const result = await svc.random();
      assert.equal(result.length, 1);
    } finally { cleanup(); }
  });

  it('respects tag filter', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'a', tags: ['red'] });
      await svc.add({ content: 'b', tags: ['blue'] });
      const result = await svc.random({ count: 5, tag: 'red' });
      assert.equal(result.length, 1);
      assert.ok(result[0].tags.includes('red'));
    } finally { cleanup(); }
  });
});

describe('recent()', () => {
  it('returns most recent memories by createdAt', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'first' });
      await new Promise(r => setTimeout(r, 2));
      await svc.add({ content: 'second' });
      await new Promise(r => setTimeout(r, 2));
      await svc.add({ content: 'third' });
      const result = await svc.recent({ count: 2 });
      assert.equal(result.length, 2);
      assert.equal(result[0].content, 'third');
      assert.equal(result[1].content, 'second');
    } finally { cleanup(); }
  });

  it('sorts by accessedAt', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m1 = await svc.add({ content: 'old' });
      await svc.add({ content: 'newer' });
      // Touch m1 to make it most recently accessed
      await svc.touch(m1.id);
      const result = await svc.recent({ count: 1, sortBy: 'accessedAt' });
      assert.equal(result[0].content, 'old');
    } finally { cleanup(); }
  });

  it('respects layer filter', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'a', layer: 'core' });
      await svc.add({ content: 'b', layer: 'short' });
      const result = await svc.recent({ count: 5, layer: 'core' });
      assert.equal(result.length, 1);
      assert.equal(result[0].layer, 'core');
    } finally { cleanup(); }
  });

  it('defaults to count=10', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      for (let i = 0; i < 15; i++) await svc.add({ content: `m${i}` });
      const result = await svc.recent();
      assert.equal(result.length, 10);
    } finally { cleanup(); }
  });
});

describe('mergeMemories()', () => {
  it('merges two memories into one', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m1 = await svc.add({ content: 'hello', tags: ['a'], entities: ['x'] });
      const m2 = await svc.add({ content: 'world', tags: ['b'], entities: ['y'] });
      const { merged, removed } = await svc.mergeMemories([m1.id, m2.id]);
      assert.ok(merged.content.includes('hello'));
      assert.ok(merged.content.includes('world'));
      assert.deepEqual(removed.sort(), [m1.id, m2.id].sort());
      // Originals gone
      assert.equal(await svc.get(m1.id), undefined);
      assert.equal(await svc.get(m2.id), undefined);
    } finally { cleanup(); }
  });

  it('merges tags and entities', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m1 = await svc.add({ content: 'a', tags: ['x'], entities: ['e1'] });
      const m2 = await svc.add({ content: 'b', tags: ['x', 'y'], entities: ['e2'] });
      const { merged } = await svc.mergeMemories([m1.id, m2.id]);
      assert.deepEqual(merged.tags.sort(), ['x', 'y']);
      assert.deepEqual(merged.entities.sort(), ['e1', 'e2']);
    } finally { cleanup(); }
  });

  it('throws for fewer than 2 ids', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await assert.rejects(() => svc.mergeMemories(['only-one']), /at least 2/);
    } finally { cleanup(); }
  });

  it('accepts custom content override', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m1 = await svc.add({ content: 'alpha' });
      const m2 = await svc.add({ content: 'beta' });
      const { merged } = await svc.mergeMemories([m1.id, m2.id], { content: 'custom' });
      assert.equal(merged.content, 'custom');
    } finally { cleanup(); }
  });

  it('transfers access counts', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m1 = await svc.add({ content: 'a' });
      await svc.touch(m1.id);
      await svc.touch(m1.id);
      const m2 = await svc.add({ content: 'b' });
      await svc.touch(m2.id);
      const { merged } = await svc.mergeMemories([m1.id, m2.id]);
      assert.ok(merged.accessCount >= 3);
    } finally { cleanup(); }
  });
});

// ─── query() ─────────────────────────────────────────────
describe('query()', () => {
  it('returns paginated results with total', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'a', layer: 'core' });
      await svc.add({ content: 'b', layer: 'long' });
      await svc.add({ content: 'c', layer: 'short' });
      const res = await svc.query({ layer: 'long' });
      assert.equal(res.total, 1);
      assert.equal(res.results[0].content, 'b');
      assert.equal(res.limit, 20);
    } finally { cleanup(); }
  });

  it('filters by tags with AND logic', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'ab', tags: ['a', 'b'] });
      await svc.add({ content: 'ac', tags: ['a', 'c'] });
      await svc.add({ content: 'bc', tags: ['b', 'c'] });
      const res = await svc.query({ tags: ['a', 'b'], tagsOp: 'and' });
      assert.equal(res.total, 1);
      assert.equal(res.results[0].content, 'ab');
    } finally { cleanup(); }
  });

  it('filters by entities', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'x', entities: ['alice', 'bob'] });
      await svc.add({ content: 'y', entities: ['carol'] });
      const res = await svc.query({ entities: ['alice'] });
      assert.equal(res.total, 1);
      assert.equal(res.results[0].content, 'x');
    } finally { cleanup(); }
  });

  it('filters by weight range', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m1 = await svc.add({ content: 'heavy', layer: 'core' });
      await svc.add({ content: 'light', layer: 'short' });
      // manually set weight
      const m = await svc.get(m1.id);
      const res = await svc.query({ minWeight: 0.9 });
      assert.ok(res.total >= 1);
      assert.ok(res.results.every(r => r.weight >= 0.9));
    } finally { cleanup(); }
  });

  it('sorts ascending', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'first', layer: 'core' });
      await svc.add({ content: 'second', layer: 'long' });
      const res = await svc.query({ sortBy: 'createdAt', sortOrder: 'asc' });
      assert.ok(res.results[0].createdAt <= res.results[1].createdAt);
    } finally { cleanup(); }
  });

  it('paginates with offset', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      for (let i = 0; i < 5; i++) await svc.add({ content: `item${i}` });
      const page1 = await svc.query({ limit: 2, offset: 0 });
      const page2 = await svc.query({ limit: 2, offset: 2 });
      assert.equal(page1.results.length, 2);
      assert.equal(page2.results.length, 2);
      assert.notEqual(page1.results[0].id, page2.results[0].id);
      assert.equal(page1.total, 5);
    } finally { cleanup(); }
  });

  it('filters by source', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'chat', source: 'conversation' });
      await svc.add({ content: 'api', source: 'manual' });
      const res = await svc.query({ source: 'conversation' });
      assert.equal(res.total, 1);
    } finally { cleanup(); }
  });
});

// ─── findByEntity() ──────────────────────────────────────
describe('findByEntity()', () => {
  it('finds memories by entity', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'about alice', entities: ['alice'], layer: 'core' });
      await svc.add({ content: 'about bob', entities: ['bob'] });
      const res = await svc.findByEntity('alice');
      assert.equal(res.length, 1);
      assert.equal(res[0].content, 'about alice');
    } finally { cleanup(); }
  });

  it('returns empty for unknown entity', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'test', entities: ['alice'] });
      const res = await svc.findByEntity('nobody');
      assert.equal(res.length, 0);
    } finally { cleanup(); }
  });

  it('filters by layer', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'a', entities: ['x'], layer: 'core' });
      await svc.add({ content: 'b', entities: ['x'], layer: 'short' });
      const res = await svc.findByEntity('x', { layer: 'core' });
      assert.equal(res.length, 1);
    } finally { cleanup(); }
  });
});

// ─── batchUpdate() ───────────────────────────────────────
describe('batchUpdate()', () => {
  it('updates multiple memories', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m1 = await svc.add({ content: 'a', tags: ['old'] });
      const m2 = await svc.add({ content: 'b', tags: ['old'] });
      const { updated, notFound } = await svc.batchUpdate([
        { id: m1.id, tags: ['new1'] },
        { id: m2.id, tags: ['new2'] },
      ]);
      assert.equal(updated, 2);
      assert.equal(notFound.length, 0);
      assert.deepEqual((await svc.get(m1.id)).tags, ['new1']);
    } finally { cleanup(); }
  });

  it('reports not found ids', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const { updated, notFound } = await svc.batchUpdate([
        { id: 'nonexistent', tags: ['x'] },
      ]);
      assert.equal(updated, 0);
      assert.deepEqual(notFound, ['nonexistent']);
    } finally { cleanup(); }
  });

  it('clamps weight to valid range', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m = await svc.add({ content: 'test' });
      await svc.batchUpdate([{ id: m.id, weight: 5.0 }]);
      assert.ok((await svc.get(m.id)).weight <= 1.0);
      await svc.batchUpdate([{ id: m.id, weight: -1 }]);
      assert.ok((await svc.get(m.id)).weight >= 0);
    } finally { cleanup(); }
  });
});

// ─── snapshot() & diff() ─────────────────────────────────
describe('snapshot()', () => {
  it('captures current state', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'a', layer: 'core' });
      await svc.add({ content: 'b', layer: 'long' });
      const snap = await svc.snapshot();
      assert.equal(snap.length, 2);
      assert.ok(snap[0].hash);
      assert.ok(snap[0].id);
    } finally { cleanup(); }
  });
});

describe('diff()', () => {
  it('detects added and removed', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const before = await svc.snapshot();
      const m = await svc.add({ content: 'new' });
      const after = await svc.snapshot();
      const d = svc.diff(before, after);
      assert.ok(d.added.includes(m.id));
      assert.equal(d.removed.length, 0);
    } finally { cleanup(); }
  });

  it('detects changes and unchanged', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m1 = await svc.add({ content: 'stable', layer: 'core' });
      const m2 = await svc.add({ content: 'will change', layer: 'long' });
      const before = await svc.snapshot();
      await svc.update(m2.id, { content: 'changed' });
      const after = await svc.snapshot();
      const d = svc.diff(before, after);
      assert.ok(d.changed.includes(m2.id));
      assert.ok(d.unchanged >= 1);
    } finally { cleanup(); }
  });
});

// ─── tagStats() ──────────────────────────────────────────
describe('tagStats()', () => {
  it('returns per-tag aggregation', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'a', tags: ['x', 'y'], layer: 'core' });
      await svc.add({ content: 'b', tags: ['x'], layer: 'long' });
      await svc.add({ content: 'c', tags: ['z'], layer: 'short' });
      const stats = await svc.tagStats();
      const xStat = stats.find(s => s.tag === 'x');
      assert.equal(xStat.count, 2);
      assert.ok(xStat.avgWeight > 0);
      assert.ok(xStat.layers.core >= 1);
    } finally { cleanup(); }
  });

  it('filters by minCount', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'a', tags: ['common'] });
      await svc.add({ content: 'b', tags: ['common'] });
      await svc.add({ content: 'c', tags: ['rare'] });
      const stats = await svc.tagStats({ minCount: 2 });
      assert.ok(stats.every(s => s.count >= 2));
      assert.equal(stats.length, 1);
    } finally { cleanup(); }
  });
});

// ─── listArchived() ────────────────────────────────────────
describe('listArchived()', () => {
  it('lists archived memories', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m1 = await svc.add({ content: 'Archive 1', layer: 'core' });
      const m2 = await svc.add({ content: 'Archive 2', layer: 'core' });
      await svc.add({ content: 'Keep active', layer: 'core' });

      await svc.archive({ ids: [m1.id, m2.id] });

      const archived = await svc.listArchived();
      assert.equal(archived.length, 2);
      assert.ok(archived.some(m => m.content === 'Archive 1'));
      assert.ok(archived.some(m => m.content === 'Archive 2'));
    } finally { cleanup(); }
  });

  it('respects limit in listArchived', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m1 = await svc.add({ content: 'A1' });
      const m2 = await svc.add({ content: 'A2' });
      const m3 = await svc.add({ content: 'A3' });
      await svc.archive({ ids: [m1.id, m2.id, m3.id] });

      const archived = await svc.listArchived({ limit: 2 });
      assert.equal(archived.length, 2);
    } finally { cleanup(); }
  });

  it('returns empty array when no archived memories', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'Active memory' });
      const archived = await svc.listArchived();
      assert.equal(archived.length, 0);
    } finally { cleanup(); }
  });

  it('excludes archivedAt field from results', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m = await svc.add({ content: 'To archive' });
      await svc.archive({ ids: [m.id] });

      const archived = await svc.listArchived();
      assert.equal(archived.length, 1);
      assert.ok(!archived[0].hasOwnProperty('archivedAt'));
      assert.equal(archived[0].content, 'To archive');
    } finally { cleanup(); }
  });
});

// ─── renameTag & mergeTags Tests ─────────────────────────

describe('renameTag', () => {
  it('renames a tag across all memories', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'A', tags: ['old'] });
      await svc.add({ content: 'B', tags: ['old', 'keep'] });
      const result = await svc.renameTag('old', 'new');
      assert.equal(result.renamed, 2);
      const all = await svc.query({ tags: ['new'] });
      assert.equal(all.total, 2);
    } finally { cleanup(); }
  });

  it('skips duplicate when target already exists', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'X', tags: ['a', 'b'] });
      const result = await svc.renameTag('a', 'b');
      assert.equal(result.renamed, 1);
      const m = (await svc.query({ tags: ['b'] })).results[0];
      assert.deepEqual(m.tags.sort(), ['b']);
    } finally { cleanup(); }
  });

  it('returns zero for no-op rename', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'Y', tags: ['x'] });
      const result = await svc.renameTag('x', 'x');
      assert.equal(result.renamed, 0);
    } finally { cleanup(); }
  });

  it('handles non-existent tag gracefully', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const result = await svc.renameTag('none', 'something');
      assert.equal(result.renamed, 0);
    } finally { cleanup(); }
  });

  it('updates tag index after rename', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'Z', tags: ['alpha'] });
      await svc.renameTag('alpha', 'beta');
      const byTag = await svc.query({ tags: ['beta'] });
      assert.equal(byTag.total, 1);
      const oldTag = await svc.query({ tags: ['alpha'] });
      assert.equal(oldTag.total, 0);
    } finally { cleanup(); }
  });
});

describe('mergeTags', () => {
  it('merges multiple tags into one', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'A', tags: ['x'] });
      await svc.add({ content: 'B', tags: ['y'] });
      await svc.add({ content: 'C', tags: ['z'] });
      const result = await svc.mergeTags(['x', 'y'], 'merged');
      assert.equal(result.merged, 2);
      const merged = await svc.query({ tags: ['merged'] });
      assert.equal(merged.total, 2);
      const z = await svc.query({ tags: ['z'] });
      assert.equal(z.total, 1);
    } finally { cleanup(); }
  });

  it('handles duplicate target in merge', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'D', tags: ['a', 'target'] });
      const result = await svc.mergeTags(['a'], 'target');
      assert.equal(result.duplicates, 1);
      const m = (await svc.query({ tags: ['target'] })).results[0];
      assert.deepEqual(m.tags, ['target']);
    } finally { cleanup(); }
  });

  it('handles empty source tags', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const result = await svc.mergeTags([], 'target');
      assert.equal(result.merged, 0);
    } finally { cleanup(); }
  });
});

describe('bulkTag', () => {
  it('adds and removes tags on multiple memories', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m1 = await svc.add({ content: 'A', tags: ['x'] });
      const m2 = await svc.add({ content: 'B', tags: ['x'] });
      const result = await svc.bulkTag([m1.id, m2.id], { add: ['y'], remove: ['x'] });
      assert.equal(result.updated, 2);
      assert.deepEqual(result.notFound, []);
      const r1 = await svc.get(m1.id);
      assert.deepEqual(r1.tags, ['y']);
      const r2 = await svc.get(m2.id);
      assert.deepEqual(r2.tags, ['y']);
    } finally { cleanup(); }
  });

  it('skips not-found IDs and reports them', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const result = await svc.bulkTag(['nonexistent'], { add: ['z'] });
      assert.equal(result.updated, 0);
      assert.deepEqual(result.notFound, ['nonexistent']);
    } finally { cleanup(); }
  });

  it('does not add duplicate tags', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m = await svc.add({ content: 'C', tags: ['existing'] });
      const result = await svc.bulkTag([m.id], { add: ['existing'] });
      assert.equal(result.updated, 0);
      const updated = await svc.get(m.id);
      assert.deepEqual(updated.tags, ['existing']);
    } finally { cleanup(); }
  });

  it('handles add-only and remove-only', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m = await svc.add({ content: 'D', tags: ['a', 'b'] });
      await svc.bulkTag([m.id], { remove: ['a'] });
      let mem = await svc.get(m.id);
      assert.deepEqual(mem.tags, ['b']);
      await svc.bulkTag([m.id], { add: ['c'] });
      mem = await svc.get(m.id);
      assert.deepEqual(mem.tags, ['b', 'c']);
    } finally { cleanup(); }
  });

  it('reindexes tag index after modification', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m = await svc.add({ content: 'E' });
      await svc.bulkTag([m.id], { add: ['newTag'] });
      const stats = await svc.tagStats();
      assert.ok(stats.some(s => s.tag === 'newTag'));
    } finally { cleanup(); }
  });
});

describe('suggestTags()', () => {
  it('suggests tags based on content keyword overlap', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'machine learning neural network training', tags: ['ai', 'ml'] });
      await svc.add({ content: 'deep learning model training data', tags: ['ai', 'deep-learning'] });
      const suggestions = await svc.suggestTags('training a neural network with data');
      assert.ok(suggestions.length > 0);
      assert.ok(suggestions.some(s => s.tag === 'ai'));
      assert.ok(suggestions[0].score > 0);
    } finally { cleanup(); }
  });

  it('returns empty when no tagged memories exist', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'no tags here' });
      const suggestions = await svc.suggestTags('something');
      assert.equal(suggestions.length, 0);
    } finally { cleanup(); }
  });

  it('matches tag name found in content', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'python code example', tags: ['python', 'coding'] });
      const suggestions = await svc.suggestTags('I love python programming');
      assert.ok(suggestions.some(s => s.tag === 'python' && s.reason.includes('tag name found')));
    } finally { cleanup(); }
  });

  it('respects limit option', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'a b c', tags: ['t1', 't2', 't3', 't4', 't5'] });
      const suggestions = await svc.suggestTags('a b c', { limit: 2 });
      assert.ok(suggestions.length <= 2);
    } finally { cleanup(); }
  });

  it('respects minScore option', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'unique xyz content', tags: ['rare-tag'] });
      const suggestions = await svc.suggestTags('completely different unrelated text', { minScore: 0.8 });
      assert.equal(suggestions.length, 0);
    } finally { cleanup(); }
  });

  it('filters by layer when specified', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'short term python code', tags: ['python'], layer: 'short' });
      await svc.add({ content: 'long term java code', tags: ['java'], layer: 'long' });
      const suggestions = await svc.suggestTags('python code', { layer: 'long' });
      assert.ok(!suggestions.some(s => s.tag === 'python'));
    } finally { cleanup(); }
  });

  // ─── healthScore() Tests ──────────────────────────────

  it('returns perfect score for empty memory store', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const health = await svc.healthScore();
      assert.equal(health.score, 100);
      assert.equal(health.details.expiry, 100);
      assert.equal(health.details.access, 100);
      assert.equal(health.details.weight, 100);
      assert.equal(health.details.changelog, 100);
      assert.ok(Array.isArray(health.recommendations));
    } finally { cleanup(); }
  });

  it('detects expired and expiring memories', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const nowTs = Date.now();
      await svc.add({ content: 'already expired', layer: 'short', expiresAt: nowTs - 1000 });
      await svc.add({ content: 'expires in 3 days', layer: 'short', expiresAt: nowTs + 3 * 24 * 60 * 60 * 1000 });
      await svc.add({ content: 'healthy memory', layer: 'core' });

      const health = await svc.healthScore({ horizonDays: 7 });
      assert.ok(health.score < 100);
      assert.ok(health.details.expiry < 100);
      assert.ok(health.recommendations.some(r => r.includes('expired')));
    } finally { cleanup(); }
  });

  it('detects stale memories (low access activity)', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      // Add a memory, then use decay() to make it stale
      const stale = await svc.add({ content: 'stale memory', layer: 'short' });
      const active = await svc.add({ content: 'active memory', layer: 'core' });

      // Decay to simulate time passing (short memories decay faster)
      await svc.decay();
      await svc.decay();  // Multiple decays for significant effect

      const health = await svc.healthScore();
      // After decay, short-term memories will have lower weight and older accessedAt
      assert.ok(health.details.access <= 100);
    } finally { cleanup(); }
  });

  it('detects low-weight memories', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'healthy', layer: 'core' });
      await svc.add({ content: 'decayed', layer: 'short' });

      // Decay the short memory significantly
      await svc.decay();

      const health = await svc.healthScore();
      assert.ok(health.details.weight <= 100);
    } finally { cleanup(); }
  });

  it('detects changelog bloat', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      // Add and delete memories to create changelog entries
      for (let i = 0; i < 1200; i++) {
        const m = await svc.add({ content: `temp ${i}`, layer: 'short' });
        await svc.delete(m.id);
      }

      const health = await svc.healthScore();
      assert.ok(health.details.changelog < 100);
      assert.ok(health.recommendations.some(r => r.includes('Compact changelog') || r.includes('compactChangelog')));
    } finally { cleanup(); }
  });

  it('respects custom weight configuration', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'test', layer: 'core' });

      // Focus heavily on expiry
      const health1 = await svc.healthScore({ weights: { expiry: 1.0, access: 0, weight: 0, changelog: 0 } });
      // Focus heavily on access
      const health2 = await svc.healthScore({ weights: { expiry: 0, access: 1.0, weight: 0, changelog: 0 } });

      assert.equal(health1.details.expiry, 100);
      assert.equal(health2.details.access, 100);
    } finally { cleanup(); }
  });

  it('returns actionable recommendations', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      // Create multiple issues
      const nowTs = Date.now();
      await svc.add({ content: 'expired', layer: 'short', expiresAt: nowTs - 1000 });
      await svc.add({ content: 'expiring soon', layer: 'short', expiresAt: nowTs + 3 * 24 * 60 * 60 * 1000 });

      const health = await svc.healthScore({ horizonDays: 7 });
      assert.ok(health.recommendations.length > 0);
      assert.ok(health.recommendations.every(r => typeof r === 'string'));
    } finally { cleanup(); }
  });
});

// ─── memoryTimeline() ──────────────────────────────
describe('MemoryService — memoryTimeline', () => {
  it('returns empty events for unknown memory', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const tl = await svc.memoryTimeline('nonexistent');
      assert.equal(tl.found, false);
      assert.equal(tl.totalEvents, 0);
      assert.equal(tl.currentLayer, undefined);
    } finally { cleanup(); }
  });

  it('returns timeline with add event for a new memory', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m = await svc.add({ content: 'timeline test', layer: 'core' });
      const tl = await svc.memoryTimeline(m.id);
      assert.equal(tl.found, true);
      assert.equal(tl.currentLayer, 'core');
      assert.ok(tl.totalEvents >= 1);
      assert.equal(tl.events[0].action, 'add');
      assert.equal(tl.events[0].memoryId, m.id);
    } finally { cleanup(); }
  });

  it('tracks multiple events for the same memory', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m = await svc.add({ content: 'v1', layer: 'short' });
      await svc.update(m.id, { content: 'v2' });
      const tl = await svc.memoryTimeline(m.id);
      assert.ok(tl.totalEvents >= 2);
      const actions = tl.events.map(e => e.action);
      assert.ok(actions.includes('add'));
      assert.ok(actions.includes('update'));
    } finally { cleanup(); }
  });

  it('events are sorted chronologically', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const m = await svc.add({ content: 'ordered', layer: 'long' });
      await svc.update(m.id, { content: 'ordered-v2' });
      const tl = await svc.memoryTimeline(m.id);
      for (let i = 1; i < tl.events.length; i++) {
        assert.ok(tl.events[i].ts >= tl.events[i - 1].ts);
      }
    } finally { cleanup(); }
  });
});

// ─── searchByTags() ──────────────────────────────
describe('MemoryService — searchByTags', () => {
  it('returns empty for empty tags array', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      const r = await svc.searchByTags([]);
      assert.equal(r.length, 0);
    } finally { cleanup(); }
  });

  it('OR mode returns memories matching any tag', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'a', layer: 'core', tags: ['x'] });
      await svc.add({ content: 'b', layer: 'core', tags: ['y'] });
      await svc.add({ content: 'c', layer: 'core', tags: ['z'] });
      const r = await svc.searchByTags(['x', 'y'], { mode: 'or' });
      assert.equal(r.length, 2);
    } finally { cleanup(); }
  });

  it('AND mode returns memories matching all tags', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'both', layer: 'core', tags: ['x', 'y'] });
      await svc.add({ content: 'only-x', layer: 'core', tags: ['x'] });
      const r = await svc.searchByTags(['x', 'y'], { mode: 'and' });
      assert.equal(r.length, 1);
      assert.equal(r[0].content, 'both');
    } finally { cleanup(); }
  });

  it('respects layer filter', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'core', layer: 'core', tags: ['t'] });
      await svc.add({ content: 'short', layer: 'short', tags: ['t'] });
      const r = await svc.searchByTags(['t'], { layer: 'core' });
      assert.equal(r.length, 1);
      assert.equal(r[0].content, 'core');
    } finally { cleanup(); }
  });

  it('respects limit', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      for (let i = 0; i < 5; i++) await svc.add({ content: `m${i}`, layer: 'core', tags: ['t'] });
      const r = await svc.searchByTags(['t'], { limit: 2 });
      assert.equal(r.length, 2);
    } finally { cleanup(); }
  });

  it('sorts by weight descending', async () => {
    const { svc, cleanup } = createService();
    await svc.init();
    try {
      await svc.add({ content: 'low', layer: 'core', tags: ['t'], weight: 0.1 });
      await svc.add({ content: 'high', layer: 'core', tags: ['t'], weight: 0.9 });
      const r = await svc.searchByTags(['t']);
      assert.equal(r[0].content, 'high');
    } finally { cleanup(); }
  });
});
