# Key Development Task 3 (Loop C) - 2026-04-17 01:00

## Focus: Autoresearch Methodology — Experiment Loop C

### Baseline
- v0.7.0, 130 tests, delete(id) + scheduledMaintenance()

### 🎯 Target
Fix stale index bug + add `reindex()` API for memory index integrity.

### 🐛 Bug Found & Fixed
**Problem:** `MemoryStore.put()` added to tag/entity indices but never cleaned old entries when updating an existing memory. If a memory's tags changed from `['old']` to `['new']`, the 'old' tag index still pointed to that memory ID.

**Fix:** `put()` now calls `#deindexMemory(old)` before `#indexMemory(m)` when the memory already exists.

### 🛠 New Features
1. **`MemoryStore.reindex()`** — rebuilds all tag/entity indices from scratch, returns `{ memories, tags, entities }`
2. **`MemoryService.reindex()`** — public API wrapper
3. **`scheduledMaintenance()` now includes reindex** — returns `{ decay, consolidation, changelog, reindex }`

### 📊 Results
- **133/133 tests pass** (was 130 → +3)
- 3 new tests: reindex basic, stale index fix, scheduledMaintenance integration
- ~20 lines added to src

### ✅ Decision: RETAIN
- Fixes a real correctness bug (stale indices)
- Adds maintenance tool for agents to verify index health
- Backward compatible, zero regressions

### experiments.tsv
```
2026-04-17T01:00	key-dev-3	test_count	133/133	keep	v0.8.0: reindex() API + fix stale tag/entity index bug in put(). scheduledMaintenance now includes reindex. 133 tests (was 130). 3 new tests.
```
