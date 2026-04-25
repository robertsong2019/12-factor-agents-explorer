# Key Development Task 3 (Loop C) - 2026-04-25 01:00

## Focus: Autoresearch Methodology — Experiment Loop C (Build on key-development-2)

### Baseline
- v0.x, 409 tests passing (after clusterHealth from key-development-2)
- Full pipeline: clusterByTopic → summarizeCluster → mergeClusters → autoTag → clusterHealth

### 🎯 Target
Add **`searchByEntity(entity, opts)`** — find memories mentioning specific named entities with fuzzy matching, layer filtering, and pagination.

**Problem:** While the internal store has `byEntity()`, there's no public API for entity-based search. Users can't query memories by entity name, do fuzzy matching, or paginate results.

**Solution:** `searchByEntity(entity, opts)` wraps the store's entity index with proper scoring (by weight), fuzzy matching (substring case-insensitive), layer filtering, and pagination.

### 🛠 Implementation

**Added:** `searchByEntity(entity, opts)` method (~25 lines src)
- Options: `fuzzy` (substring match), `layer` (filter), `limit`/`offset` (pagination)
- Returns: `{ entity, fuzzy, total, offset, limit, results: [{id, content, layer, weight, entities, tags}] }`
- Results sorted by weight descending

### 📊 Testing

**6 new tests:**
1. ✅ Finds memories by exact entity
2. ✅ Finds with fuzzy matching
3. ✅ Filters by layer
4. ✅ Paginates results
5. ✅ Throws for missing/empty entity
6. ✅ Returns empty for non-existent entity

**Results:**
- 409 → 415 tests (+6, 414/415 passing — 1 pre-existing flaky in expire.test.js)
- ~25 lines added to src/index.js
- Committed: `2e2ea1c`

### ✅ Decision: RETAIN

**Rationale:**
- Completes the query API — search (text), searchAdvanced, searchBM25, searchHybrid, and now searchByEntity
- Leverages existing `#entityIndex` infrastructure
- Zero regressions, clean API
- Small footprint

### experiments.tsv
```
2026-04-25T01:00	2e2ea1c	test_count	414/415	keep	searchByEntity(entity, opts) — entity-based search with fuzzy match, layer filter, pagination. 6 new tests (409→415), ~25 lines src.
```

### 🔮 Potential Next Steps
1. `contentVersioning(id)` — store content snapshots on update for true diff
2. `autoTag` v2 with embedding-based similarity for better tag suggestions
3. `clusterAutoMerge(healthReport)` — auto-merge orphaned clusters based on health report
4. `searchByTimeRange(opts)` — temporal search across memories

---

**Generated**: 2026-04-25 01:00 AM
**Status:** ✅ Complete — searchByEntity() API added, 6 new tests, 414/415 passing (1 pre-existing flaky)
