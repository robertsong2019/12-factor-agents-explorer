/**
 * Agent Memory Service — Mem0 风格的记忆管理
 * 
 * 三层存储 + 自动提取 + 语义检索
 * 零外部依赖，纯 Node.js
 */

import { randomUUID } from 'node:crypto';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile, appendFile } from 'node:fs/promises';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';

// ─── Types ───────────────────────────────────────────────

/**
 * @typedef {'core'|'long'|'short'} MemoryLayer
 * @typedef {'relates_to'|'contradicts'|'supersedes'|'derived_from'|'causes'} LinkType
 * @typedef {{
 *   id: string,
 *   content: string,
 *   layer: MemoryLayer,
 *   tags: string[],
 *   entities: string[],
 *   weight: number,
 *   createdAt: number,
 *   accessedAt: number,
 *   accessCount: number,
 *   source?: string,
 *   hash: string
 * }} Memory
 * @typedef {{
 *   id: string,
 *   source: string,
 *   target: string,
 *   type: LinkType,
 *   strength: number,
 *   createdAt: number
 * }} Link
 */

// ─── Constants ───────────────────────────────────────────

const LAYERS = /** @type {const} */ ({
  core:  { decayRate: 0,     minWeight: 1.0   },  // 永不过期
  long:  { decayRate: 0.02,  minWeight: 0.05  },  // 30天半衰期
  short: { decayRate: 0.5,   minWeight: 0.05  },  // 1天半衰期
});

const DECAY_BASE = 0.3;  // Ebbinghaus coefficient
const BOOST_AMOUNT = 0.3;
const MAX_WEIGHT = 1.0;

// ─── Utility ─────────────────────────────────────────────

function contentHash(content) {
  return createHash('sha256').update(content).digest('hex').slice(0, 16);
}

function now() {
  return Date.now();
}

function daysSince(timestamp) {
  return (now() - timestamp) / (1000 * 60 * 60 * 24);
}

/**
 * Tokenize text into lowercase words for keyword matching
 */
function tokenize(text) {
  return text.toLowerCase()
    .replace(/[^\w\u4e00-\u9fff]/g, ' ')
    .split(/\s+/)
    .filter(w => w.length > 1);
}

/**
 * Simple TF-IDF inspired scoring
 */
function keywordScore(queryTokens, contentTokens) {
  if (queryTokens.length === 0) return 0;
  let hits = 0;
  for (const qt of queryTokens) {
    if (contentTokens.includes(qt)) hits++;
  }
  return hits / queryTokens.length;
}

/**
 * Very simple n-gram based semantic similarity (no embeddings needed)
 */
function ngramSimilarity(a, b) {
  const ngrams = (s, n = 2) => {
    const chars = s.toLowerCase().replace(/\s+/g, '');
    const set = new Set();
    for (let i = 0; i <= chars.length - n; i++) {
      set.add(chars.slice(i, i + n));
    }
    return set;
  };
  const setA = ngrams(a);
  const setB = ngrams(b);
  const union = setA.size + setB.size - (function() {
    let c = 0;
    for (const g of setA) { if (setB.has(g)) c++; }
    return c;
  })();
  if (union === 0) return 0;
  let intersection = 0;
  for (const g of setA) {
    if (setB.has(g)) intersection++;
  }
  return intersection / union;
}

// ─── Changelog Store (lightweight append-only change log) ─

class ChangelogStore {
  /** @type {Array<{ts: number, action: 'add'|'update'|'delete', memoryId: string, layer?: MemoryLayer}>} */
  #entries = [];
  #filePath;
  #dirty = false;

  constructor(dirPath) {
    this.#filePath = join(dirPath, 'changelog.json');
  }

  async load() {
    try {
      const raw = await readFile(this.#filePath, 'utf-8');
      this.#entries = JSON.parse(raw);
    } catch { this.#entries = []; }
  }

  async save() {
    if (!this.#dirty) return;
    await mkdir(dirname(this.#filePath), { recursive: true });
    await writeFile(this.#filePath, JSON.stringify(this.#entries, null, 2));
    this.#dirty = false;
  }

  record(action, memoryId, layer) {
    this.#entries.push({ ts: now(), action, memoryId, layer });
    this.#dirty = true;
  }

  /** Return all entries */
  all() {
    return [...this.#entries];
  }

  /** Replace all entries (for import) */
  replace(entries) {
    this.#entries = entries || [];
    this.#dirty = true;
  }

  /** Return all entries since a given timestamp */
  since(ts) {
    return this.#entries.filter(e => e.ts > ts);
  }
}

// ─── Memory Store (JSON file-based) ──────────────────────

class MemoryStore {
  /** @type {Map<string, Memory>} */
  #memories = new Map();
  /** @type {string} */
  #filePath;
  /** @type {Map<string, Set<string>>} */  // tag -> memory ids
  #tagIndex = new Map();
  /** @type {Map<string, Set<string>>} */  // entity -> memory ids
  #entityIndex = new Map();
  #dirty = false;

  /**
   * @param {string} dirPath 
   */
  constructor(dirPath) {
    this.#filePath = join(dirPath, 'memories.json');
  }

  async load() {
    try {
      const data = await readFile(this.#filePath, 'utf-8');
      const arr = JSON.parse(data);
      this.#memories.clear();
      this.#tagIndex.clear();
      this.#entityIndex.clear();
      for (const m of arr) {
        this.#memories.set(m.id, m);
        this.#indexMemory(m);
      }
    } catch {
      this.#memories.clear();
    }
  }

  async save() {
    if (!this.#dirty) return;
    const arr = Array.from(this.#memories.values());
    await mkdir(dirname(this.#filePath), { recursive: true });
    await writeFile(this.#filePath, JSON.stringify(arr, null, 2));
    this.#dirty = false;
  }

  /**
   * @param {Memory} m 
   */
  #indexMemory(m) {
    for (const tag of m.tags) {
      if (!this.#tagIndex.has(tag)) this.#tagIndex.set(tag, new Set());
      this.#tagIndex.get(tag).add(m.id);
    }
    for (const entity of m.entities) {
      if (!this.#entityIndex.has(entity)) this.#entityIndex.set(entity, new Set());
      this.#entityIndex.get(entity).add(m.id);
    }
  }

  /** @param {string} id */
  get(id) { return this.#memories.get(id); }

  /** @param {Memory} m */
  put(m) {
    // Clean old indices if memory already exists (tags/entities may have changed)
    const old = this.#memories.get(m.id);
    if (old) this.#deindexMemory(old);
    this.#memories.set(m.id, m);
    this.#indexMemory(m);
    this.#dirty = true;
  }

  /**
   * Remove a memory from tag/entity indices (does NOT remove from #memories)
   * @param {Memory} m
   */
  #deindexMemory(m) {
    for (const tag of m.tags) this.#tagIndex.get(tag)?.delete(m.id);
    for (const entity of m.entities) this.#entityIndex.get(entity)?.delete(m.id);
  }

  /** @param {string} id */
  delete(id) {
    const m = this.#memories.get(id);
    if (m) {
      for (const tag of m.tags) this.#tagIndex.get(tag)?.delete(id);
      for (const entity of m.entities) this.#entityIndex.get(entity)?.delete(id);
    }
    this.#memories.delete(id);
    this.#dirty = true;
  }

  /** @returns {Memory[]} */
  all() { return Array.from(this.#memories.values()); }

  /** @param {string} tag */
  byTag(tag) {
    const ids = this.#tagIndex.get(tag);
    return ids ? Array.from(ids).map(id => this.#memories.get(id)).filter(Boolean) : [];
  }

  /** @param {string} entity */
  byEntity(entity) {
    const ids = this.#entityIndex.get(entity);
    return ids ? Array.from(ids).map(id => this.#memories.get(id)).filter(Boolean) : [];
  }

  /**
   * Rebuild all indices from scratch
   * @returns {{ tags: number, entities: number, memories: number }}
   */
  reindex() {
    this.#tagIndex.clear();
    this.#entityIndex.clear();
    for (const m of this.#memories.values()) {
      this.#indexMemory(m);
    }
    return {
      memories: this.#memories.size,
      tags: this.#tagIndex.size,
      entities: this.#entityIndex.size,
    };
  }

  /** @param {MemoryLayer} layer */
  byLayer(layer) {
    return this.all().filter(m => m.layer === layer);
  }

  get size() { return this.#memories.size; }
}

// ─── Link Store ──────────────────────────────────────────

class LinkStore {
  /** @type {Map<string, Link>} */
  #links = new Map();
  /** @type {string} */
  #filePath;
  /** @type {Map<string, Set<string>>} */  // memoryId -> link ids
  #memIndex = new Map();
  #dirty = false;

  constructor(dirPath) {
    this.#filePath = join(dirPath, 'links.json');
  }

  async load() {
    try {
      const data = await readFile(this.#filePath, 'utf-8');
      const arr = JSON.parse(data);
      this.#links.clear();
      this.#memIndex.clear();
      for (const l of arr) {
        this.#links.set(l.id, l);
        this.#indexLink(l);
      }
    } catch {
      this.#links.clear();
    }
  }

  async save() {
    if (!this.#dirty) return;
    const arr = Array.from(this.#links.values());
    await mkdir(dirname(this.#filePath), { recursive: true });
    await writeFile(this.#filePath, JSON.stringify(arr, null, 2));
    this.#dirty = false;
  }

  /** @param {Link} l */
  #indexLink(l) {
    for (const id of [l.source, l.target]) {
      if (!this.#memIndex.has(id)) this.#memIndex.set(id, new Set());
      this.#memIndex.get(id).add(l.id);
    }
  }

  /** @param {Link} l */
  put(l) {
    this.#links.set(l.id, l);
    this.#indexLink(l);
    this.#dirty = true;
  }

  /** @param {string} id */
  delete(id) {
    const l = this.#links.get(id);
    if (l) {
      this.#memIndex.get(l.source)?.delete(id);
      this.#memIndex.get(l.target)?.delete(id);
    }
    this.#links.delete(id);
    this.#dirty = true;
  }

  /** Clean up links pointing to deleted memories */
  cleanForMemory(memId) {
    const linkIds = this.#memIndex.get(memId);
    if (linkIds) {
      for (const lid of [...linkIds]) this.delete(lid);
    }
  }

  /**
   * Get all links involving a memory (both directions)
   * @param {string} memId
   * @returns {Link[]}
   */
  forMemory(memId) {
    const ids = this.#memIndex.get(memId);
    return ids ? Array.from(ids).map(id => this.#links.get(id)).filter(Boolean) : [];
  }

  /**
   * Traverse graph from a memory, following links up to `depth` hops
   * @param {string} startId
   * @param {{depth?: number, types?: LinkType[], direction?: 'out'|'in'|'both'}} opts
   * @returns {Map<string, {link: Link, hop: number}>}
   */
  traverse(startId, opts = {}) {
    const depth = opts.depth ?? 2;
    const types = opts.types;
    const direction = opts.direction ?? 'both';
    const visited = new Map(); // memoryId -> {link, hop}
    const queue = [{id: startId, hop: 0}];

    while (queue.length > 0) {
      const {id, hop} = queue.shift();
      if (hop >= depth) continue;

      const links = this.forMemory(id);
      for (const l of links) {
        if (types && !types.includes(l.type)) continue;

        // Determine neighbor based on direction
        let neighbor = null;
        if (direction === 'out' && l.source === id) neighbor = l.target;
        else if (direction === 'in' && l.target === id) neighbor = l.source;
        else if (direction === 'both') neighbor = l.source === id ? l.target : l.source;

        if (neighbor && !visited.has(neighbor)) {
          visited.set(neighbor, {link: l, hop: hop + 1});
          queue.push({id: neighbor, hop: hop + 1});
        }
      }
    }
    return visited;
  }

  all() { return Array.from(this.#links.values()); }
  get size() { return this.#links.size; }
}

// ─── Extractor ───────────────────────────────────────────

/**
 * Simple rule-based memory extractor
 * In production, this would call an LLM
 */
class MemoryExtractor {
  /**
   * Extract potential memories from text
   * @param {string} text
   * @param {string} role - 'user' | 'assistant' | 'system'
   * @returns {Array<{content: string, type: string, confidence: number, entities: string[]}>}
   */
  extract(text, role = 'user') {
    const memories = [];

    // Pattern: preferences ("我喜欢...", "I prefer...", "用...比较好")
    const prefPatterns = [
      /(?:我喜欢|偏好|prefer|喜欢用|比较喜欢|最好用)([^。，！？\n]+)/g,
      /(?:我不喜欢|讨厌|don't like)([^。，！？\n]+)/g,
    ];
    for (const pat of prefPatterns) {
      let match;
      while ((match = pat.exec(text)) !== null) {
        memories.push({
          content: match[0],
          type: 'preference',
          confidence: 0.8,
          entities: tokenize(match[1]),
        });
      }
    }

    // Pattern: facts/statements ("...是...", "... means ...")
    const factPatterns = [
      /([^。，！？\n]+(?:是|等于|意味着|means|is|are)[^。，！？\n]+)/g,
    ];
    for (const pat of factPatterns) {
      let match;
      while ((match = pat.exec(text)) !== null) {
        const content = match[1].trim();
        if (content.length > 5 && content.length < 200) {
          memories.push({
            content,
            type: 'fact',
            confidence: 0.6,
            entities: [],
          });
        }
      }
    }

    // Pattern: decisions/intentions ("我要...", "计划...", "let's...", "I will...")
    const decisionPatterns = [
      /(?:我要|我打算|计划|let's|I will|going to|准备)([^。，！？\n]+)/g,
    ];
    for (const pat of decisionPatterns) {
      let match;
      while ((match = pat.exec(text)) !== null) {
        memories.push({
          content: match[0],
          type: 'decision',
          confidence: 0.7,
          entities: tokenize(match[1]),
        });
      }
    }

    // Pattern: project/tech mentions
    const techPattern = /(?:project|项目|repo|仓库|框架|framework|工具|tool)\s*[:：]?\s*([A-Za-z0-9\-_\.]+)/gi;
    let techMatch;
    while ((techMatch = techPattern.exec(text)) !== null) {
      memories.push({
        content: `技术/项目: ${techMatch[1]}`,
        type: 'entity',
        confidence: 0.7,
        entities: [techMatch[1].toLowerCase()],
      });
    }

    // For user messages, also treat the whole message as a potential fact if substantial
    if (role === 'user' && text.length > 20 && text.length < 500 && memories.length === 0) {
      memories.push({
        content: text.trim(),
        type: 'context',
        confidence: 0.3,
        entities: tokenize(text).slice(0, 5),
      });
    }

    return memories;
  }

  /**
   * Extract from a full conversation
   * @param {Array<{role: string, content: string}>} messages
   * @returns {Array<{content: string, type: string, confidence: number, entities: string[], layer: MemoryLayer}>}
   */
  extractFromConversation(messages) {
    const allMemories = [];
    for (const msg of messages) {
      const extracted = this.extract(msg.content, msg.role);
      for (const m of extracted) {
        // Classify into layers
        let layer = 'short';
        if (m.type === 'preference' || m.type === 'decision') layer = 'core';
        else if (m.type === 'fact' || m.type === 'entity') layer = 'long';

        allMemories.push({ ...m, layer });
      }
    }
    return allMemories;
  }

  /**
   * Extract memories using LLM
   * @param {string} text
   * @param {function} llmFn - Async function that takes a prompt and returns structured JSON
   * @returns {Promise<Array<{content: string, type: string, confidence: number, entities: string[]}>>}
   */
  async extractWithLLM(text, llmFn) {
    if (!llmFn) return [];

    const prompt = `Extract meaningful memories from the following text. Return JSON array with objects: {content, type (preference|decision|fact|entity), confidence (0-1), entities (string[])}.
Only extract high-quality, actionable information. Skip general chatter.

Text: "${text}"

Return only JSON array, no explanation.`;

    try {
      const response = await llmFn(prompt);
      let parsed = response;
      if (typeof response === 'string') {
        parsed = JSON.parse(response);
      }

      if (Array.isArray(parsed)) {
        return parsed
          .filter(m => m.content && m.content.length > 5 && m.content.length < 500)
          .map(m => ({
            content: m.content.trim(),
            type: ['preference', 'decision', 'fact', 'entity'].includes(m.type) ? m.type : 'fact',
            confidence: Math.min(1, Math.max(0, m.confidence || 0.5)),
            entities: Array.isArray(m.entities) ? m.entities : [],
          }));
      }
      return [];
    } catch {
      return [];
    }
  }

  /**
   * Hybrid extraction: rule-based + LLM with deduplication
   * @param {string} text
   * @param {function} llmFn - Optional LLM function
   * @returns {Promise<Array<{content: string, type: string, confidence: number, entities: string[]}>>}
   */
  async extractHybrid(text, llmFn = null) {
    const ruleBased = this.extract(text);
    if (!llmFn) return ruleBased;

    const llmBased = await this.extractWithLLM(text, llmFn);
    const combined = [...ruleBased, ...llmBased];

    // Deduplicate by content similarity
    const seen = new Set();
    const unique = [];
    for (const m of combined) {
      const key = m.content.toLowerCase().slice(0, 50);
      let duplicate = false;
      for (const k of seen) {
        if (ngramSimilarity(key, k) > 0.8) {
          duplicate = true;
          break;
        }
      }
      if (!duplicate) {
        seen.add(key);
        unique.push(m);
      }
    }
    return unique;
  }
}

// ─── Memory Service ──────────────────────────────────────

export class MemoryService {
  /** @type {MemoryStore} */
  #store;
  /** @type {LinkStore} */
  #links;
  /** @type {ChangelogStore} */
  #changelog;
  /** @type {MemoryExtractor} */
  #extractor;
  /** @type {EmbeddingProvider} */
  #embeddings;
  /** @type {string} */
  #dirPath;
  /** @type {boolean} */
  #loaded = false;

  /**
   * @param {{dbPath?: string, embedFn?: EmbedFn}} options
   */
  constructor(options = {}) {
    this.#dirPath = options.dbPath || './data/memory';
    this.#store = new MemoryStore(this.#dirPath);
    this.#links = new LinkStore(this.#dirPath);
    this.#changelog = new ChangelogStore(this.#dirPath);
    this.#extractor = new MemoryExtractor();
    this.#embeddings = new EmbeddingProvider(this.#dirPath, options.embedFn || null);
  }

  /** Access the embedding provider for configuration */
  get embeddings() {
    return this.#embeddings;
  }

  async init() {
    if (!this.#loaded) {
      await this.#store.load();
      await this.#links.load();
      await this.#changelog.load();
      await this.#embeddings.loadCache();
      this.#loaded = true;
    }
  }

  async #ensureLoaded() {
    if (!this.#loaded) await this.init();
  }

  /**
   * Add a memory directly
   * @param {{content: string, layer?: MemoryLayer, tags?: string[], entities?: string[], source?: string}} opts
   * @returns {Promise<Memory>}
   */
  async add(opts) {
    await this.#ensureLoaded();
    const id = randomUUID();
    const ts = now();
    /** @type {Memory} */
    const memory = {
      id,
      content: opts.content,
      layer: opts.layer || 'short',
      tags: opts.tags || [],
      entities: opts.entities || [],
      weight: MAX_WEIGHT,
      createdAt: ts,
      accessedAt: ts,
      accessCount: 0,
      source: opts.source,
      hash: contentHash(opts.content),
    };
    this.#store.put(memory);
    this.#changelog.record('add', id, memory.layer);
    await this.#store.save();
    await this.#changelog.save();
    return memory;
  }

  /**
   * Extract and store memories from a conversation
   * @param {Array<{role: string, content: string}>} messages
   * @returns {Promise<Memory[]>}
   */
  async extractFromConversation(messages) {
    await this.#ensureLoaded();
    const extracted = this.#extractor.extractFromConversation(messages);
    const stored = [];
    for (const m of extracted) {
      // Deduplicate by content hash
      const hash = contentHash(m.content);
      const existing = this.#store.all().find(x => x.hash === hash);
      if (existing) {
        // Boost existing memory
        existing.weight = Math.min(MAX_WEIGHT, existing.weight + BOOST_AMOUNT * 0.5);
        existing.accessedAt = now();
        existing.accessCount++;
        continue;
      }
      const memory = await this.add({
        content: m.content,
        layer: m.layer,
        entities: m.entities,
      });
      stored.push(memory);
    }
    await this.#store.save();
    return stored;
  }

  /**
   * Search memories with multi-strategy retrieval
   * @param {string} query
   * @param {{limit?: number, layer?: MemoryLayer, strategy?: 'keyword'|'semantic'|'hybrid'}} opts
   * @returns {Promise<Array<Memory & {score: number}>>}
   */
  async search(query, opts = {}) {
    await this.#ensureLoaded();
    const limit = opts.limit || 5;
    const strategy = opts.strategy || 'hybrid';
    let candidates = this.#store.all();

    // Filter by layer if specified
    if (opts.layer) {
      candidates = candidates.filter(m => m.layer === opts.layer);
    }

    // Filter out decayed memories
    candidates = candidates.filter(m => m.weight >= LAYERS[m.layer].minWeight);

    const queryTokens = tokenize(query);

    // Pre-compute query embedding if available (async, done once)
    let queryVec = null;
    if (this.#embeddings.enabled) {
      queryVec = await this.#embeddings.embed(query);
    }

    // Score each candidate
    const scored = await Promise.all(candidates.map(async m => {
      let score = 0;

      if (strategy === 'keyword' || strategy === 'hybrid') {
        const contentTokens = tokenize(m.content);
        score += keywordScore(queryTokens, contentTokens) * 0.5;
        // Tag match bonus
        const tagMatch = m.tags.filter(t => queryTokens.includes(t.toLowerCase())).length;
        score += tagMatch * 0.1;
      }

      if (strategy === 'semantic' || strategy === 'hybrid') {
        // Use embedding similarity if available, else fallback to ngram
        if (queryVec && this.#embeddings.enabled) {
          const memVec = await this.#embeddings.embed(m.content);
          if (memVec) {
            score += cosineSimilarity(queryVec, memVec) * 0.3;
          } else {
            score += ngramSimilarity(query, m.content) * 0.3;
          }
        } else {
          score += ngramSimilarity(query, m.content) * 0.3;
        }
      }

      // Time decay bonus (prefer recent)
      const ageDays = daysSince(m.createdAt);
      score *= Math.exp(-0.01 * ageDays);

      // Weight bonus (prefer strong memories)
      score *= m.weight;

      // Layer priority: core > long > short
      const layerBoost = { core: 1.5, long: 1.0, short: 0.7 };
      score *= layerBoost[m.layer];

      return { ...m, score };
    }));

    // Sort by score, take top N
    scored.sort((a, b) => b.score - a.score);
    const results = scored.slice(0, limit);

    // Persist any new embedding caches
    await this.#embeddings.saveCache();

    // Boost accessed memories
    for (const m of results) {
      const original = this.#store.get(m.id);
      if (original) {
        original.accessedAt = now();
        original.accessCount++;
        original.weight = Math.min(MAX_WEIGHT, original.weight + BOOST_AMOUNT);
      }
    }
    await this.#store.save();

    return results;
  }

  /**
   * Get a specific memory by ID
   * @param {string} id
   */
  async get(id) {
    await this.#ensureLoaded();
    const m = this.#store.get(id);
    if (m) {
      m.accessedAt = now();
      m.accessCount++;
      m.weight = Math.min(MAX_WEIGHT, m.weight + BOOST_AMOUNT * 0.5);
      await this.#store.save();
    }
    return m;
  }

  /**
   * Advanced search with BM25-inspired scoring and result explanations
   * @param {string} query
   * @param {{limit?: number, layer?: MemoryLayer, explain?: boolean}} opts
   * @returns {Promise<Array<Memory & {score: number, explanation?: object}>>}
   */
  async searchAdvanced(query, opts = {}) {
    await this.#ensureLoaded();
    const limit = opts.limit || 5;
    const explain = opts.explain !== false;
    let candidates = this.#store.all();

    if (opts.layer) {
      candidates = candidates.filter(m => m.layer === opts.layer);
    }
    candidates = candidates.filter(m => m.weight >= LAYERS[m.layer].minWeight);

    // Precompute IDF across corpus
    const N = candidates.length;
    const queryTokens = tokenize(query);
    const df = {};
    for (const t of queryTokens) {
      df[t] = 0;
      for (const m of candidates) {
        if (tokenize(m.content).includes(t)) df[t]++;
      }
    }

    const avgDl = candidates.reduce((s, m) => s + tokenize(m.content).length, 0) / (N || 1);
    const k1 = 1.2, b = 0.75; // BM25 params

    const scored = candidates.map(m => {
      const dl = tokenize(m.content).length;
      const parts = { bm25: 0, ngram: 0, recency: 0, weight: 0, layer: 0 };

      // BM25 term scoring
      for (const t of queryTokens) {
        const tf = tokenize(m.content).filter(c => c === t).length;
        const idf = Math.log((N - (df[t] || 0) + 0.5) / ((df[t] || 0) + 0.5) + 1);
        const tfNorm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / (avgDl || 1)));
        parts.bm25 += idf * tfNorm;
      }

      // N-gram similarity
      parts.ngram = ngramSimilarity(query, m.content) * 0.3;

      // Recency (prefer recent)
      const ageDays = daysSince(m.createdAt);
      parts.recency = Math.exp(-0.01 * ageDays);

      // Memory weight
      parts.weight = m.weight;

      // Layer priority
      parts.layer = { core: 1.5, long: 1.0, short: 0.7 }[m.layer];

      const score = (parts.bm25 * 0.4 + parts.ngram) * parts.recency * parts.weight * parts.layer;

      const result = { ...m, score };
      if (explain) {
        result.explanation = { ...parts, total: score };
      }
      return result;
    });

    scored.sort((a, b) => b.score - a.score);
    const results = scored.slice(0, limit);

    for (const m of results) {
      const original = this.#store.get(m.id);
      if (original) {
        original.accessedAt = now();
        original.accessCount++;
        original.weight = Math.min(MAX_WEIGHT, original.weight + BOOST_AMOUNT);
      }
    }
    await this.#store.save();
    return results;
  }

  /**
   * Apply decay to all memories
   * @returns {{decayed: number, removed: number}}
   */
  async decay() {
    await this.#ensureLoaded();
    let decayed = 0;
    let removed = 0;
    const toRemove = [];

    for (const m of this.#store.all()) {
      const config = LAYERS[m.layer];
      if (config.decayRate === 0) continue;  // core never decays

      const elapsedDays = daysSince(m.accessedAt);
      const newWeight = m.weight * Math.exp(-DECAY_BASE * config.decayRate * elapsedDays);
      
      if (newWeight < config.minWeight) {
        toRemove.push(m.id);
        removed++;
      } else if (newWeight < m.weight) {
        m.weight = newWeight;
        decayed++;
      }
    }

    for (const id of toRemove) {
      this.#store.delete(id);
    }

    await this.#store.save();
    return { decayed, removed };
  }

  /**
   * Get statistics
   */
  async stats() {
    await this.#ensureLoaded();
    const all = this.#store.all();
    const byLayer = { core: 0, long: 0, short: 0 };
    let totalWeight = 0;
    const tags = new Set();
    const entities = new Set();

    for (const m of all) {
      byLayer[m.layer]++;
      totalWeight += m.weight;
      m.tags.forEach(t => tags.add(t));
      m.entities.forEach(e => entities.add(e));
    }

    return {
      total: all.length,
      byLayer,
      avgWeight: all.length > 0 ? totalWeight / all.length : 0,
      uniqueTags: tags.size,
      uniqueEntities: entities.size,
      oldestAgeMs: all.length ? now() - Math.min(...all.map(m => m.createdAt)) : 0,
      changelogEntries: this.#changelog.all().length,
      links: this.#links.size,
    };
  }

  /**
   * Export all memories as JSON
   */
  async export() {
    await this.#ensureLoaded();
    return this.#store.all();
  }

  /**
   * Full export: memories + links + changelog for backup
   * @returns {Promise<{memories: Memory[], links: Link[], changelog: Array, exportedAt: number}>}
   */
  async exportAll() {
    await this.#ensureLoaded();
    return {
      memories: this.#store.all(),
      links: this.#links.all(),
      changelog: this.#changelog.all(),
      exportedAt: now(),
    };
  }

  /**
   * Full import: restore from a previous exportAll() backup
   * Clears existing data before importing.
   * @param {{memories: Memory[], links: Link[], changelog?: Array}} data
   * @returns {Promise<{memories: number, links: number}>}
   */
  async importAll(data) {
    await this.#ensureLoaded();
    if (!data || !Array.isArray(data.memories)) {
      throw new Error('importAll requires {memories: Array}');
    }
    // Clear existing
    for (const m of this.#store.all()) this.#store.delete(m.id);
    for (const l of this.#links.all()) this.#links.delete(l.id);
    this.#changelog.replace([]);

    // Import memories
    for (const m of data.memories) this.#store.put(m);
    // Import links
    if (Array.isArray(data.links)) {
      for (const l of data.links) this.#links.put(l);
    }
    // Import changelog
    if (Array.isArray(data.changelog)) {
      this.#changelog.replace(data.changelog);
    }
    await this.#store.save();
    await this.#links.save();
    await this.#changelog.save();
    return { memories: data.memories.length, links: (data.links || []).length };
  }

  /**
   * Consolidate related short-term memories into long-term/core memories.
   * Inspired by human sleep consolidation: related weak memories merge into stronger ones.
   * 
   * Algorithm:
   * 1. Cluster short/long memories by n-gram similarity (threshold ≥ 0.4)
   * 2. For each cluster of 2+ memories, merge into a single memory
   * 3. Merged memory gets: higher layer, combined entities/tags, boosted weight, references to originals
   * 4. Original memories are deleted
   * 
   * @param {{similarityThreshold?: number, dryRun?: boolean}} opts
   * @returns {Promise<{clusters: number, merged: number, promoted: Memory[]}>}
   */
  async consolidate(opts = {}) {
    await this.#ensureLoaded();
    const threshold = opts.similarityThreshold ?? 0.4;
    const dryRun = opts.dryRun ?? false;

    // Only consolidate non-core memories with weight > minWeight
    const candidates = this.#store.all().filter(
      m => m.layer !== 'core' && m.weight >= LAYERS[m.layer].minWeight
    );

    // Cluster by similarity (union-find)
    const parent = new Map();
    const find = (id) => {
      if (!parent.has(id)) parent.set(id, id);
      if (parent.get(id) !== id) parent.set(id, find(parent.get(id)));
      return parent.get(id);
    };
    const union = (a, b) => {
      const ra = find(a), rb = find(b);
      if (ra !== rb) parent.set(ra, rb);
    };

    for (let i = 0; i < candidates.length; i++) {
      for (let j = i + 1; j < candidates.length; j++) {
        const sim = ngramSimilarity(candidates[i].content, candidates[j].content);
        // Also consider shared entities/tags as similarity signals
        const sharedEntities = candidates[i].entities.filter(e => candidates[j].entities.includes(e)).length;
        const sharedTags = candidates[i].tags.filter(t => candidates[j].tags.includes(t)).length;
        const effectiveSim = sim + sharedEntities * 0.1 + sharedTags * 0.05;
        if (effectiveSim >= threshold) {
          union(candidates[i].id, candidates[j].id);
        }
      }
    }

    // Group by root
    const clusters = new Map();
    for (const m of candidates) {
      const root = find(m.id);
      if (!clusters.has(root)) clusters.set(root, []);
      clusters.get(root).push(m);
    }

    // Only merge clusters with 2+ memories
    let clusterCount = 0;
    let mergedCount = 0;
    const promoted = [];

    for (const [, group] of clusters) {
      if (group.length < 2) continue;
      clusterCount++;

      // Sort by weight descending — strongest memory is the anchor
      group.sort((a, b) => b.weight - a.weight);
      const anchor = group[0];

      // Determine target layer: if any is 'long', promote to 'core'; otherwise 'long'
      const hasLong = group.some(m => m.layer === 'long');
      const targetLayer = hasLong ? 'core' : 'long';

      // Merge content: anchor content + unique fragments from others
      const allContent = [anchor.content];
      for (let i = 1; i < group.length; i++) {
        // Only add content that's not too similar to anchor (> 0.8 overlap = skip)
        const overlap = ngramSimilarity(anchor.content, group[i].content);
        if (overlap < 0.8) {
          allContent.push(group[i].content);
        }
      }
      const mergedContent = allContent.join(' | ');

      // Merge entities and tags
      const mergedEntities = [...new Set(group.flatMap(m => m.entities))];
      const mergedTags = [...new Set(group.flatMap(m => m.tags))];
      const totalAccess = group.reduce((s, m) => s + m.accessCount, 0);
      const earliestCreated = Math.min(...group.map(m => m.createdAt));

      if (!dryRun) {
        // Delete originals
        for (const m of group) {
          this.#store.delete(m.id);
        }

        // Create consolidated memory
        const memory = await this.add({
          content: mergedContent,
          layer: targetLayer,
          tags: mergedTags,
          entities: mergedEntities,
          source: `consolidated:${group.map(m => m.id.slice(0, 8)).join(',')}`,
        });

        // Preserve earliest creation time and total access count
        const stored = this.#store.get(memory.id);
        if (stored) {
          stored.createdAt = earliestCreated;
          stored.accessCount = totalAccess;
          stored.weight = Math.min(MAX_WEIGHT, anchor.weight + BOOST_AMOUNT);
        }
        await this.#store.save();
        promoted.push(stored);
      } else {
        promoted.push({
          id: `dry-run-${clusterCount}`,
          content: mergedContent,
          layer: targetLayer,
          tags: mergedTags,
          entities: mergedEntities,
          sourceGroup: group.map(m => ({ id: m.id.slice(0, 8), content: m.content.slice(0, 60) })),
        });
      }
      mergedCount += group.length;
    }

    return { clusters: clusterCount, merged: mergedCount, promoted };
  }

  /**
   * Link two memories with a typed association
   * @param {{source: string, target: string, type: LinkType, strength?: number}} opts
   * @returns {Promise<Link>}
   */
  async link(opts) {
    await this.#ensureLoaded();
    const { source, target, type, strength = 1.0 } = opts;
    // Validate both memories exist
    if (!this.#store.get(source)) throw new Error(`Source memory ${source} not found`);
    if (!this.#store.get(target)) throw new Error(`Target memory ${target} not found`);
    
    const id = randomUUID();
    /** @type {Link} */
    const link = { id, source, target, type, strength, createdAt: now() };
    this.#links.put(link);
    await this.#links.save();
    return link;
  }

  /**
   * Remove a link by id
   * @param {string} linkId
   */
  async unlink(linkId) {
    await this.#ensureLoaded();
    this.#links.delete(linkId);
    await this.#links.save();
  }

  /**
   * Get all links for a memory
   * @param {string} memoryId
   * @returns {Promise<Link[]>}
   */
  async getLinks(memoryId) {
    await this.#ensureLoaded();
    return this.#links.forMemory(memoryId);
  }

  /**
   * Traverse the memory graph from a starting memory
   * @param {string} startId
   * @param {{depth?: number, types?: LinkType[], direction?: 'out'|'in'|'both'}} opts
   * @returns {Promise<{neighbors: Array<{memory: Memory, link: Link, hop: number}>}>}
   */
  async traverse(startId, opts = {}) {
    await this.#ensureLoaded();
    const map = this.#links.traverse(startId, opts);
    const neighbors = [];
    for (const [memId, {link, hop}] of map) {
      const memory = this.#store.get(memId);
      if (memory) neighbors.push({ memory, link, hop });
    }
    return { neighbors };
  }

  /**
   * Auto-link: automatically create associations between memories based on shared entities/tags
   * @param {{types?: LinkType[], threshold?: number}} opts
   * @returns {Promise<{created: number, skipped: number}>}
   */
  async autoLink(opts = {}) {
    await this.#ensureLoaded();
    const threshold = opts.threshold ?? 2; // min shared signals to link
    const type = opts.types?.[0] ?? 'relates_to';
    let created = 0, skipped = 0;

    // Get existing link pairs to avoid duplicates
    const existing = new Set();
    for (const l of this.#links.all()) {
      existing.add(`${l.source}->${l.target}`);
      existing.add(`${l.target}->${l.source}`);
    }

    const memories = this.#store.all();
    for (let i = 0; i < memories.length; i++) {
      for (let j = i + 1; j < memories.length; j++) {
        const a = memories[i], b = memories[j];
        const key = `${a.id}->${b.id}`;
        if (existing.has(key)) { skipped++; continue; }

        // Count shared signals
        const sharedEntities = a.entities.filter(e => b.entities.includes(e)).length;
        const sharedTags = a.tags.filter(t => b.tags.includes(t)).length;
        const sim = ngramSimilarity(a.content, b.content);
        const signals = sharedEntities + sharedTags + (sim > 0.3 ? 1 : 0);

        if (signals >= threshold) {
          await this.link({
            source: a.id,
            target: b.id,
            type,
            strength: Math.min(1.0, signals * 0.25),
          });
          created++;
        }
      }
    }
    return { created, skipped };
  }

  /**
   * Add multiple memories in one call (batch)
   * @param {Array<{content: string, layer?: MemoryLayer, tags?: string[], entities?: string[], source?: string}>} items
   * @returns {Promise<Memory[]>}
   */
  async batchAdd(items) {
    await this.#ensureLoaded();
    const memories = [];
    for (const opts of items) {
      const memory = await this.add(opts);
      memories.push(memory);
    }
    return memories;
  }

  /**
   * Delete multiple memories by ID (batch)
   * Cleans up associated links for each.
   * @param {string[]} ids
   * @returns {Promise<{deleted: number, notFound: number}>}
   */
  async batchDelete(ids) {
    await this.#ensureLoaded();
    let deleted = 0, notFound = 0;
    for (const id of ids) {
      const m = this.#store.get(id);
      if (!m) { notFound++; continue; }
      this.#links.cleanForMemory(id);
      this.#changelog.record('delete', id, m.layer);
      this.#store.delete(id);
      deleted++;
    }
    await this.#store.save();
    await this.#links.save();
    await this.#changelog.save();
    return { deleted, notFound };
  }

  /**
   * Search and auto-link: search for a query, then link top results to a given memory.
   * Useful for connecting a new memory to existing related ones.
   * @param {{memoryId: string, query: string, limit?: number, linkType?: LinkType, strength?: number}} opts
   * @returns {Promise<{linked: Array<{memory: Memory & {score: number}, link: Link}>}>}
   */
  async searchAndLink(opts) {
    await this.#ensureLoaded();
    const results = await this.search(opts.query, { limit: opts.limit || 3 });
    const linked = [];
    for (const r of results) {
      if (r.id === opts.memoryId) continue; // skip self
      try {
        const link = await this.link({
          source: opts.memoryId,
          target: r.id,
          type: opts.linkType || 'relates_to',
          strength: opts.strength || Math.min(1.0, r.score * 0.5),
        });
        linked.push({ memory: r, link });
      } catch {
        // Memory might have been deleted between search and link
      }
    }
    return { linked };
  }

  /**
   * Get memories within a time range, sorted by creation date.
   * @param {{from?: number, to?: number, layer?: MemoryLayer, limit?: number}} opts
   * @returns {Promise<Memory[]>}
   */
  async timeline(opts = {}) {
    await this.#ensureLoaded();
    let memories = this.#store.all();
    if (opts.layer) memories = memories.filter(m => m.layer === opts.layer);
    if (opts.from) memories = memories.filter(m => m.createdAt >= opts.from);
    if (opts.to) memories = memories.filter(m => m.createdAt <= opts.to);
    memories.sort((a, b) => b.createdAt - a.createdAt);
    if (opts.limit) memories = memories.slice(0, opts.limit);
    return memories;
  }

  /**
   * Update an existing memory's content and/or metadata.
   * Records an 'update' entry in the changelog so changes() can report it.
   * @param {string} id
   * @param {{content?: string, tags?: string[], entities?: string[], layer?: MemoryLayer}} opts
   * @returns {Promise<Memory|null>} null if not found
   */
  async update(id, opts = {}) {
    await this.#ensureLoaded();
    const m = this.#store.get(id);
    if (!m) return null;

    if (opts.content !== undefined) {
      m.content = opts.content;
      m.hash = contentHash(opts.content);
    }
    if (opts.tags !== undefined) m.tags = opts.tags;
    if (opts.entities !== undefined) m.entities = opts.entities;
    if (opts.layer !== undefined) m.layer = opts.layer;

    this.#store.put(m); // re-index
    this.#changelog.record('update', id, m.layer);
    await this.#store.save();
    await this.#changelog.save();
    return m;
  }

  /**
   * Merge two memories into one — keeps the stronger, absorbs the weaker
   * @param {string} keeperId - Memory to keep/absorb into
   * @param {string} absorbedId - Memory to absorb and delete
   * @param {{content?: string, layer?: MemoryLayer}} opts - Override merged content/layer
   * @returns {Promise<Memory|null>} The merged memory
   */
  async merge(keeperId, absorbedId, opts = {}) {
    await this.#ensureLoaded();
    const keeper = this.#store.get(keeperId);
    const absorbed = this.#store.get(absorbedId);
    if (!keeper || !absorbed) return null;
    if (keeperId === absorbedId) return keeper;

    // Merge content: use override or concatenate
    keeper.content = opts.content || `${keeper.content}; ${absorbed.content}`;
    keeper.hash = contentHash(keeper.content);

    // Merge tags and entities (union)
    keeper.tags = [...new Set([...keeper.tags, ...absorbed.tags])];
    keeper.entities = [...new Set([...keeper.entities, ...absorbed.entities])];

    // Keep stronger layer (core > long > short)
    const layerOrder = { core: 3, long: 2, short: 1 };
    if (opts.layer) {
      keeper.layer = opts.layer;
    } else if (layerOrder[absorbed.layer] > layerOrder[keeper.layer]) {
      keeper.layer = absorbed.layer;
    }

    // Combine weight (cap at MAX_WEIGHT)
    keeper.weight = Math.min(MAX_WEIGHT, keeper.weight + absorbed.weight * 0.5);
    keeper.accessCount += absorbed.accessCount;
    keeper.accessedAt = Math.max(keeper.accessedAt, absorbed.accessedAt);

    // Re-link any links pointing to absorbed → point to keeper
    for (const link of this.#links.all()) {
      if (link.source === absorbedId) link.source = keeperId;
      if (link.target === absorbedId) link.target = keeperId;
    }

    // Delete absorbed memory
    this.#store.delete(absorbedId);
    this.#changelog.record('delete', absorbedId, absorbed.layer);
    this.#store.put(keeper);
    this.#changelog.record('update', keeperId, keeper.layer);
    await this.#store.save();
    await this.#changelog.save();
    return keeper;
  }

  /**
   * Compact changelog by removing entries older than `maxAge` ms.
   * Keeps the store healthy for long-running agents.
   * @param {{maxAge?: number}} opts — maxAge defaults to 30 days (ms)
   * @returns {Promise<{removed: number, remaining: number}>}
   */
  async compactChangelog(opts = {}) {
    await this.#ensureLoaded();
    const maxAge = opts.maxAge ?? 30 * 24 * 60 * 60 * 1000;
    const cutoff = now() - maxAge;
    const entries = this.#changelog.since(0);
    const before = entries.length;
    const kept = entries.filter(e => e.ts >= cutoff);
    const filePath = join(this.#dirPath, 'changelog.json');
    await mkdir(dirname(filePath), { recursive: true });
    await writeFile(filePath, JSON.stringify(kept, null, 2));
    await this.#changelog.load();
    return { removed: before - kept.length, remaining: kept.length };
  }

  /**
   * Delete a single memory by ID.
   * Cleans up associated links and records in changelog.
   * @param {string} id
   * @returns {Promise<boolean>} true if deleted, false if not found
   */
  /**
   * Lightweight access tracking — update accessedAt and accessCount without
   * modifying content or recording a changelog entry.
   * @param {string} id
   * @param {{boost?: number}} [opts] - optional weight boost (default 0)
   * @returns {Promise<Memory|null>}
   */
  async touch(id, opts = {}) {
    await this.#ensureLoaded();
    const m = this.#store.get(id);
    if (!m) return null;
    m.accessedAt = now();
    m.accessCount++;
    if (opts.boost) {
      m.weight = Math.min(MAX_WEIGHT, m.weight + opts.boost);
    }
    this.#store.put(m);
    await this.#store.save();
    return m;
  }

  async delete(id) {
    await this.#ensureLoaded();
    const m = this.#store.get(id);
    if (!m) return false;
    this.#links.cleanForMemory(id);
    this.#changelog.record('delete', id, m.layer);
    this.#store.delete(id);
    await this.#store.save();
    await this.#links.save();
    await this.#changelog.save();
    return true;
  }

  /**
   * Run scheduled maintenance: decay + consolidate + compact changelog.
   * Agents should call this periodically (e.g., on session start or via heartbeat).
   * @param {{consolidateThreshold?: number, changelogMaxAge?: number, dryRun?: boolean}} opts
   * @returns {Promise<{decay: {decayed: number, removed: number}, consolidation: {clusters: number, merged: number}, changelog: {removed: number, remaining: number}}>}
   */
  async scheduledMaintenance(opts = {}) {
    const decay = await this.decay();
    const consolidation = await this.consolidate({
      similarityThreshold: opts.consolidateThreshold ?? 0.4,
      dryRun: opts.dryRun ?? false,
    });
    const changelog = await this.compactChangelog({ maxAge: opts.changelogMaxAge });
    const reindex = this.#store.reindex();
    return { decay, consolidation, changelog, reindex };
  }

  /**
   * Rebuild all tag/entity indices from scratch
   * @returns {Promise<{ memories: number, tags: number, entities: number }>}
   */
  async reindex() {
    await this.#ensureLoaded();
    return this.#store.reindex();
  }

  /**
   * Clear all memories
   */
  async clear() {
    await this.#ensureLoaded();
    const all = this.#store.all();
    for (const m of all) {
      this.#links.cleanForMemory(m.id);
      this.#changelog.record('delete', m.id, m.layer);
      this.#store.delete(m.id);
    }
    await this.#store.save();
    await this.#links.save();
    await this.#changelog.save();
  }

  /**
   * Get incremental changes since a given timestamp.
   * Returns memories that were added/updated/deleted since `since`.
   * Useful for cross-session sync — agents can call this to learn what's new.
   * @param {number} since — Unix timestamp (ms)
   * @returns {Promise<{added: Memory[], updated: Memory[], deleted: string[], snapshot: {total: number, byLayer: Object}}>}
   */
  async changes(since) {
    await this.#ensureLoaded();
    const entries = this.#changelog.since(since);
    const added = [];
    const updated = [];
    const deletedIds = new Set();
    const seenAdded = new Set();

    for (const entry of entries) {
      if (entry.action === 'delete') {
        deletedIds.add(entry.memoryId);
        // If it was added then deleted in the same window, skip it from added
        seenAdded.delete(entry.memoryId);
      } else if (entry.action === 'add' && !deletedIds.has(entry.memoryId)) {
        seenAdded.add(entry.memoryId);
      }
    }

    // Populate added memories (still in store)
    for (const id of seenAdded) {
      const m = this.#store.get(id);
      if (m) added.push(m);
    }

    // Populate updated memories (update action, still in store, not in added)
    const seenUpdated = new Set();
    for (const entry of entries) {
      if (entry.action === 'update' && !seenAdded.has(entry.memoryId) && !seenUpdated.has(entry.memoryId)) {
        const m = this.#store.get(entry.memoryId);
        if (m) { updated.push(m); seenUpdated.add(entry.memoryId); }
      }
    }

    const allMemories = this.#store.all();
    const byLayer = { core: 0, long: 0, short: 0 };
    for (const m of allMemories) byLayer[m.layer]++;

    return {
      added,
      updated,
      deleted: [...deletedIds],
      snapshot: { total: allMemories.length, byLayer },
    };
  }

  /**
   * Find memories related to a given memory
   * Considers: entity overlap, tag overlap, and semantic similarity
   * @param {string} memoryId
   * @param {{limit?: number, minScore?: number, includeSelf?: boolean}} opts
   * @returns {Promise<Array<Memory & {score: number, matchType: string[]}>>}
   */
  async findRelated(memoryId, opts = {}) {
    await this.#ensureLoaded();
    const target = this.#store.get(memoryId);
    if (!target) return [];

    const limit = opts.limit || 10;
    const minScore = opts.minScore || 0.1;
    const includeSelf = opts.includeSelf ?? false;

    const candidates = this.#store.all().filter(m => includeSelf || m.id !== memoryId);

    const scored = candidates.map(m => {
      const matchType = [];
      let score = 0;

      // Entity overlap (strong signal)
      const sharedEntities = target.entities.filter(e => m.entities.includes(e));
      if (sharedEntities.length > 0) {
        score += sharedEntities.length * 0.4;
        matchType.push('entities');
      }

      // Tag overlap
      const sharedTags = target.tags.filter(t => m.tags.includes(t));
      if (sharedTags.length > 0) {
        score += sharedTags.length * 0.2;
        matchType.push('tags');
      }

      // Semantic similarity
      const sim = ngramSimilarity(target.content, m.content);
      if (sim > 0.1) {
        score += sim * 0.4;
        matchType.push('semantic');
      }

      return { ...m, score, matchType };
    });

    // Filter by min score and sort
    const filtered = scored.filter(r => r.score >= minScore);
    filtered.sort((a, b) => b.score - a.score);

    return filtered.slice(0, limit);
  }

  /**
   * Find near-duplicate memories using n-gram similarity.
   * Returns groups of duplicate memories.
   * @param {{threshold?: number, layer?: string}} opts
   * @returns {Promise<Array<{memories: object[], similarity: number}>>}
   */
  async findDuplicates(opts = {}) {
    await this.#ensureLoaded();
    const threshold = opts.threshold || 0.7;
    let memories = this.#store.all();
    if (opts.layer) memories = memories.filter(m => m.layer === opts.layer);

    const groups = [];
    const assigned = new Set();

    for (let i = 0; i < memories.length; i++) {
      if (assigned.has(memories[i].id)) continue;
      const group = [memories[i]];
      for (let j = i + 1; j < memories.length; j++) {
        if (assigned.has(memories[j].id)) continue;
        const sim = ngramSimilarity(memories[i].content, memories[j].content);
        if (sim >= threshold) {
          group.push(memories[j]);
          assigned.add(memories[j].id);
        }
      }
      if (group.length > 1) {
        const sim = ngramSimilarity(group[0].content, group[1].content);
        assigned.add(group[0].id);
        groups.push({ memories: group, similarity: sim });
      }
    }
    return groups;
  }

  /**
   * Archive memories (move to cold storage, remove from active store).
   * Returns archived memory IDs.
   * @param {{olderThanMs?: number, layer?: string, ids?: string[]}} opts
   * @returns {Promise<{archivedIds: string[], count: number}>}
   */
  async archive(opts = {}) {
    await this.#ensureLoaded();
    let targets;
    if (opts.ids) {
      targets = opts.ids.map(id => this.#store.get(id)).filter(Boolean);
    } else {
      targets = this.#store.all();
      if (opts.layer) targets = targets.filter(m => m.layer === opts.layer);
      if (opts.olderThanMs) {
        const cutoff = Date.now() - opts.olderThanMs;
        targets = targets.filter(m => m.createdAt < cutoff);
      }
    }

    const archiveDir = join(this.#dirPath, 'archive');
    mkdirSync(archiveDir, { recursive: true });
    const archivePath = join(archiveDir, 'archived.json');
    let archived = [];
    try { archived = JSON.parse(readFileSync(archivePath, 'utf8')); } catch {}

    for (const m of targets) {
      archived.push({ ...m, archivedAt: Date.now() });
      this.#store.delete(m.id);
      this.#links.cleanForMemory(m.id);
      this.#changelog.record('archive', m.id, m.layer);
    }

    writeFileSync(archivePath, JSON.stringify(archived, null, 2));
    return { archivedIds: targets.map(m => m.id), count: targets.length };
  }

  /**
   * Restore archived memories back to active store.
   * @param {{ids?: string[], limit?: number}} opts
   * @returns {Promise<{restoredIds: string[], count: number}>}
   */
  async restore(opts = {}) {
    await this.#ensureLoaded();
    const archivePath = join(this.#dirPath, 'archive', 'archived.json');
    let archived;
    try { archived = JSON.parse(readFileSync(archivePath, 'utf8')); } catch { archived = []; }

    let toRestore = opts.ids
      ? archived.filter(m => opts.ids.includes(m.id))
      : archived;
    if (opts.limit) toRestore = toRestore.slice(0, opts.limit);

    const restoreIds = new Set(toRestore.map(m => m.id));
    for (const m of toRestore) {
      const { archivedAt, ...memory } = m;
      this.#store.put({ ...memory, updatedAt: Date.now() });
    }

    const remaining = archived.filter(m => !restoreIds.has(m.id));
    writeFileSync(archivePath, JSON.stringify(remaining, null, 2));

    return { restoredIds: [...restoreIds], count: restoreIds.size };
  }

  /**
   * Validate store integrity. Checks for orphan links, missing indices, stale data.
   * @param {{repair?: boolean}} opts
   * @returns {Promise<{valid: boolean, issues: string[], repaired?: number}>}
   */
  async validate(opts = {}) {
    await this.#ensureLoaded();
    const issues = [];
    let repaired = 0;
    const allMemories = this.#store.all();
    const allIds = new Set(allMemories.map(m => m.id));

    // Check orphan links
    const allLinks = this.#links.all();
    for (const link of allLinks) {
      if (!allIds.has(link.sourceId)) {
        issues.push(`Orphan link ${link.id}: source ${link.sourceId} missing`);
        if (opts.repair) { this.#links.delete(link.id); repaired++; }
      }
      if (!allIds.has(link.targetId)) {
        issues.push(`Orphan link ${link.id}: target ${link.targetId} missing`);
        if (opts.repair) { this.#links.delete(link.id); repaired++; }
      }
    }

    // Check tag/entity indices consistency
    for (const m of allMemories) {
      const byTag = this.#store.byTag('__check__');
      // Verify each memory's tags are indexed
      for (const tag of m.tags) {
        const tagged = this.#store.byTag(tag);
        if (!tagged.some(t => t.id === m.id)) {
          issues.push(`Memory ${m.id} tag "${tag}" not in index`);
          if (opts.repair) { this.#store.reindex(); repaired++; break; }
        }
      }
      if (issues.some(i => i.includes(m.id) && i.includes('not in index'))) break; // one reindex enough
    }

    // Check for memories with missing required fields
    for (const m of allMemories) {
      if (!m.content) issues.push(`Memory ${m.id} has empty content`);
      if (!m.id) issues.push(`Memory missing id`);
    }

    if (opts.repair && repaired > 0) {
      await this.#store.save();
      await this.#links.save();
      await this.#changelog.save();
    }

    return { valid: issues.length === 0, issues, ...(opts.repair ? { repaired } : {}) };
  }

  /**
   * Tag frequency analysis across all memories.
   * @param {{top?: number}} opts
   * @returns {Promise<Array<{tag: string, count: number, layers: Record<string, number>}>>}
   */
  async tagCloud(opts = {}) {
    await this.#ensureLoaded();
    const freq = new Map();
    for (const m of this.#store.all()) {
      for (const tag of m.tags) {
        if (!freq.has(tag)) freq.set(tag, { tag, count: 0, layers: {} });
        const entry = freq.get(tag);
        entry.count++;
        entry.layers[m.layer] = (entry.layers[m.layer] || 0) + 1;
      }
    }
    const result = [...freq.values()].sort((a, b) => b.count - a.count);
    return opts.top ? result.slice(0, opts.top) : result;
  }

  /**
   * Aggregate statistics grouped by a field.
   * @param {{groupBy: 'layer'|'tag'|'entity'}} opts
   * @returns {Promise<Array<{group: string, count: number, avgWeight: number}>>}
   */
  async aggregate(opts) {
    await this.#ensureLoaded();
    const groups = new Map();
    const all = this.#store.all();

    for (const m of all) {
      const keys = opts.groupBy === 'layer' ? [m.layer]
        : opts.groupBy === 'tag' ? m.tags
        : m.entities;
      for (const key of keys) {
        if (!groups.has(key)) groups.set(key, { group: key, count: 0, totalWeight: 0 });
        const g = groups.get(key);
        g.count++;
        g.totalWeight += m.weight;
      }
    }

    return [...groups.values()].map(g => ({
      group: g.group,
      count: g.count,
      avgWeight: g.count ? Math.round(g.totalWeight / g.count * 100) / 100 : 0
    })).sort((a, b) => b.count - a.count);
  }

  /**
   * Search memories by time range.
   * @param {{from?: number, to?: number, layer?: string, limit?: number}} opts
   * @returns {Promise<object[]>}
   */
  async searchByTime(opts = {}) {
    await this.#ensureLoaded();
    let results = this.#store.all();
    if (opts.from) results = results.filter(m => m.createdAt >= opts.from);
    if (opts.to) results = results.filter(m => m.createdAt <= opts.to);
    if (opts.layer) results = results.filter(m => m.layer === opts.layer);
    results.sort((a, b) => b.createdAt - a.createdAt);
    return opts.limit ? results.slice(0, opts.limit) : results;
  }

  /**
   * Auto-merge duplicate memories. Uses findDuplicates then merge for each group.
   * @param {{threshold?: number, dryRun?: boolean}} opts
   * @returns {Promise<{merged: number, groups: number, details: Array}>}
   */
  async deduplicate(opts = {}) {
    await this.#ensureLoaded();
    const threshold = opts.threshold || 0.8;
    const dupes = await this.findDuplicates({ threshold });
    let merged = 0;
    const details = [];

    for (const group of dupes) {
      if (opts.dryRun) {
        details.push({ action: 'would_merge', ids: group.memories.map(m => m.id) });
        continue;
      }
      // Keep the oldest memory, merge others into it
      const sorted = [...group.memories].sort((a, b) => a.createdAt - b.createdAt);
      const keeper = sorted[0];
      for (let i = 1; i < sorted.length; i++) {
        await this.merge(keeper.id, sorted[i].id);
        merged++;
      }
      details.push({ action: 'merged', keeperId: keeper.id, absorbed: sorted.slice(1).map(m => m.id) });
    }

    return { merged, groups: dupes.length, details };
  }

  /**
   * Get memory graph: nodes (memories) + edges (links) for visualization.
   * @param {{layer?: string, limit?: number}} opts
   * @returns {Promise<{nodes: Array, edges: Array}>}
   */
  async memoryGraph(opts = {}) {
    await this.#ensureLoaded();
    let memories = this.#store.all();
    if (opts.layer) memories = memories.filter(m => m.layer === opts.layer);
    if (opts.limit) memories = memories.slice(0, opts.limit);

    const ids = new Set(memories.map(m => m.id));
    const nodes = memories.map(m => ({
      id: m.id, content: m.content.slice(0, 80), layer: m.layer,
      weight: m.weight, tags: m.tags
    }));

    const allLinks = this.#links.all();
    const edges = allLinks
      .filter(l => ids.has(l.source) && ids.has(l.target))
      .map(l => ({ source: l.source, target: l.target, type: l.type, strength: l.strength }));

    return { nodes, edges };
  }

  /**
   * Pure semantic/vector search. Uses embeddings if available, falls back to ngram.
   * @param {string} query
   * @param {{limit?: number, layer?: MemoryLayer, threshold?: number}} opts
   * @returns {Promise<Array<Memory & {score: number, method: string}>>}
   */
  async searchByEmbedding(query, opts = {}) {
    await this.#ensureLoaded();
    const limit = opts.limit || 5;
    const threshold = opts.threshold || 0;
    let candidates = this.#store.all();

    if (opts.layer) {
      candidates = candidates.filter(m => m.layer === opts.layer);
    }
    candidates = candidates.filter(m => m.weight >= LAYERS[m.layer].minWeight);

    const useEmbedding = this.#embeddings.enabled;
    const method = useEmbedding ? 'vector' : 'ngram';

    const queryVec = useEmbedding ? await this.#embeddings.embed(query) : null;

    const scored = await Promise.all(candidates.map(async m => {
      let score;
      if (useEmbedding && queryVec) {
        const memVec = await this.#embeddings.embed(m.content);
        score = memVec ? cosineSimilarity(queryVec, memVec) : ngramSimilarity(query, m.content);
      } else {
        score = ngramSimilarity(query, m.content);
      }
      return { ...m, score, method };
    }));

    scored.sort((a, b) => b.score - a.score);
    const results = scored.filter(m => m.score >= threshold).slice(0, limit);

    await this.#embeddings.saveCache();
    return results;
  }

  /**
   * Compact the store by removing low-weight memories.
   * @param {{minWeight?: number, layer?: string, dryRun?: boolean}} opts
   * @returns {Promise<{removed: number, remaining: number}>}
   */
  async compact(opts = {}) {
    await this.#ensureLoaded();
    const minWeight = opts.minWeight ?? 0.1;
    let memories = this.#store.all();
    if (opts.layer) memories = memories.filter(m => m.layer === opts.layer);

    const toRemove = memories.filter(m => m.weight < minWeight);
    if (opts.dryRun) return { removed: toRemove.length, remaining: memories.length - toRemove.length };

    for (const m of toRemove) {
      this.#links.cleanForMemory(m.id);
      this.#store.delete(m.id);
    }
    await this.#store.save();
    await this.#links.save();

    return { removed: toRemove.length, remaining: this.#store.all().length };
  }

  /**
   * Count memories matching optional filter criteria.
   * @param {{layer?: string, tag?: string, minWeight?: number}} [filter]
   * @returns {Promise<number>}
   */
  async count(filter = {}) {
    await this.#ensureLoaded();
    let memories = this.#store.all();
    if (filter.layer) memories = memories.filter(m => m.layer === filter.layer);
    if (filter.tag) memories = memories.filter(m => m.tags && m.tags.includes(filter.tag));
    if (filter.minWeight !== undefined) memories = memories.filter(m => m.weight >= filter.minWeight);
    return memories.length;
  }

  /**
   * Get random memories (useful for serendipity/exploration).
   * @param {{count?: number, layer?: string, tag?: string}} [opts]
   * @returns {Promise<Memory[]>}
   */
  async random(opts = {}) {
    await this.#ensureLoaded();
    let memories = this.#store.all();
    if (opts.layer) memories = memories.filter(m => m.layer === opts.layer);
    if (opts.tag) memories = memories.filter(m => m.tags && m.tags.includes(opts.tag));
    // Fisher-Yates shuffle then take first N
    const shuffled = [...memories];
    const n = Math.min(opts.count ?? 1, shuffled.length);
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled.slice(0, n);
  }
}

// ─── Embedding Provider Interface ────────────────────────

/**
 * Cosine similarity between two vectors
 * @param {number[]} a
 * @param {number[]} b
 * @returns {number}
 */
function cosineSimilarity(a, b) {
  if (a.length !== b.length || a.length === 0) return 0;
  let dot = 0, normA = 0, normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  const denom = Math.sqrt(normA) * Math.sqrt(normB);
  return denom === 0 ? 0 : dot / denom;
}

/**
 * @typedef {(text: string) => Promise<number[]>} EmbedFn
 */

/**
 * EmbeddingProvider wraps an async embedding function and manages a vector cache.
 * Falls back gracefully if the embedding function is unavailable.
 */
class EmbeddingProvider {
  /** @type {EmbedFn|null} */
  #embedFn;
  /** @type {Map<string, number[]>} */  // content hash -> vector
  #cache = new Map();
  #cachePath;
  #dirty = false;

  /**
   * @param {string} dirPath - Directory to persist cache
   * @param {EmbedFn|null} embedFn - Async function that returns a vector for text. null = disabled.
   */
  constructor(dirPath, embedFn = null) {
    this.#cachePath = join(dirPath, 'embed-cache.json');
    this.#embedFn = embedFn;
  }

  /** Set or replace the embedding function at runtime */
  setEmbedFn(fn) {
    this.#embedFn = fn;
  }

  /** Check if embeddings are available */
  get enabled() {
    return this.#embedFn !== null;
  }

  async loadCache() {
    try {
      const raw = await readFile(this.#cachePath, 'utf-8');
      const obj = JSON.parse(raw);
      this.#cache = new Map(Object.entries(obj));
    } catch {
      this.#cache = new Map();
    }
  }

  async saveCache() {
    if (!this.#dirty) return;
    await mkdir(dirname(this.#cachePath), { recursive: true });
    const obj = Object.fromEntries(this.#cache);
    await writeFile(this.#cachePath, JSON.stringify(obj));
    this.#dirty = false;
  }

  /**
   * Get embedding for text (cached)
   * @param {string} text
   * @returns {Promise<number[]|null>}
   */
  async embed(text) {
    if (!this.#embedFn) return null;
    const key = contentHash(text);
    if (this.#cache.has(key)) return this.#cache.get(key);
    try {
      const vec = await this.#embedFn(text);
      if (vec && Array.isArray(vec) && vec.length > 0) {
        this.#cache.set(key, vec);
        this.#dirty = true;
        return vec;
      }
    } catch {
      // Embedding function failed; return null (graceful fallback)
    }
    return null;
  }

  /**
   * Compute similarity between two texts via embeddings
   * @param {string} a
   * @param {string} b
   * @returns {Promise<number|null>} null if unavailable
   */
  async similarity(a, b) {
    const [vecA, vecB] = await Promise.all([this.embed(a), this.embed(b)]);
    if (!vecA || !vecB) return null;
    return cosineSimilarity(vecA, vecB);
  }

  /** Clear the cache */
  clearCache() {
    this.#cache.clear();
    this.#dirty = true;
  }

  /** Get cache size */
  get cacheSize() {
    return this.#cache.size;
  }

  /**
   * Get embedding cache statistics
   * @returns {{enabled: boolean, cachedVectors: number, cachePath: string}}
   */
  stats() {
    return {
      enabled: this.enabled,
      cachedVectors: this.#cache.size,
      cachePath: this.#cachePath,
    };
  }
}

export { MemoryStore, MemoryExtractor, LinkStore, ChangelogStore, LAYERS, tokenize, ngramSimilarity, keywordScore, EmbeddingProvider, cosineSimilarity };
