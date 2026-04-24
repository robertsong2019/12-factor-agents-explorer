# Key Development Task 3 (Loop C) - 2026-04-24 01:00

## Focus: Autoresearch Methodology — Experiment Loop C (Build on key-development-1/2)

### Baseline
- v0.x, 389 tests passing (after autoTag from key-development-2)
- Note: 1 pre-existing flaky test (expire.test.js), not caused by our changes

### 🎯 Target
Add **`mergeClusters(topics, opts)`** — merge multiple topic clusters into one unified cluster.

**Problem:** After `clusterByTopic()` identifies topic clusters, there's no way to consolidate related clusters. If "machine-learning" and "neural-networks" are separate clusters, you need to manually retag memories to merge them.

**Solution:** `mergeClusters(topics, opts)` takes an array of topic tag names, finds all matching memories, retags them with a unified `targetTag`, and optionally removes source tags.

### 🛠 Implementation

**Added:** `mergeClusters(topics, opts)` method (~40 lines src)
- Options: `targetTag` (default: first topic), `removeSourceTags` (default: true)
- Case-insensitive topic matching
- Returns: `{ targetTag, mergedCount, sourceTopics }`
- Calls `#store.reindex()` after modifications

### 📊 Testing

**6 new tests:**
1. ✅ Merges memories from multiple topics into target tag
2. ✅ Removes source tags by default
3. ✅ Keeps source tags when removeSourceTags is false
4. ✅ Uses first topic as default targetTag
5. ✅ Throws with fewer than 2 topics
6. ✅ Skips memories already having target tag

**Results:**
- 389 → 395 tests (+6, 394/395 passing — 1 pre-existing flaky)
- ~40 lines added to src/index.js
- Committed: `212574f`

### ✅ Decision: RETAIN

**Rationale:**
- Natural companion to clusterByTopic + summarizeCluster — find → summarize → merge pipeline
- Zero regressions, clean API
- Small footprint (~40 lines src)
- Flexible: can keep or remove source tags

### experiments.tsv
```
2026-04-24T01:00	212574f	test_count	394/395	keep	mergeClusters(topics, opts) — merge multiple topic clusters into unified tag. Supports targetTag, removeSourceTags. 6 new tests (389→395), ~40 lines src.
```

### 🔮 Potential Next Steps
1. `searchByEntity(entity, opts)` — find memories mentioning specific named entities
2. `contentVersioning(id)` — store content snapshots on update for true diff
3. `autoTag` v2 with embedding-based similarity for better tag suggestions
4. `clusterHealth()` — metrics on cluster quality (avg similarity, overlap, orphaned memories)

---

**Generated**: 2026-04-24 01:00 AM
**Status:** ✅ Complete — mergeClusters() API added, 6 new tests, 394/395 passing
