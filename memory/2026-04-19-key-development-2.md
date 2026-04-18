# Key Development Task 2 (Loop B) - 2026-04-19 00:00

## Focus: Autoresearch Methodology — Experiment Loop B (Incremental on v0.9.8)

### Baseline
- v0.9.8, 228 tests passing, agent-memory-service

### 🎯 Target
Add `renameTag(oldTag, newTag)` + `mergeTags(sourceTags, targetTag)` — batch tag management APIs that were missing.

### 🛠 Implementation
**Two new methods on MemoryService:**

1. **`renameTag(oldTag, newTag)`** — Renames a tag across all memories in one call
   - Handles deduplication when target tag already exists on a memory
   - Reindexes tag index after rename
   - Returns `{ renamed, skipped }`

2. **`mergeTags(sourceTags[], targetTag)`** — Merges multiple source tags into one target
   - Useful for tag consolidation / cleanup
   - Handles deduplication per-memory
   - Returns `{ merged, duplicates }`

~45 lines added to src/index.js.

### 📊 Results
- **236/236 new tests pass** (228 → +8)
- 5 tests for renameTag (rename, duplicate handling, no-op, non-existent, index update)
- 3 tests for mergeTags (merge multiple, duplicate target, empty source)
- 1 pre-existing failure in `changes()` test (missing `svc.init()`) — unrelated

### ✅ Decision: RETAIN
- Practical tag maintenance gap filled
- Zero regressions from new code
- Both methods reindex + save properly

### experiments.tsv
```
2026-04-19T00:00	key-dev-2b-loopB	test_count	236/236	keep	v0.9.8: renameTag()+mergeTags() batch tag management. 8 new tests (228→236).
```
