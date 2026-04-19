# Key Development Task 3 (Loop C) - 2026-04-19 01:00

## Focus: Autoresearch Methodology — Experiment Loop C

### Baseline
- v0.9.8, 236 tests passing, agent-memory-service
- Commit: ca57e4c (listArchived API)

### 🎯 Target
Add `bulkTag(ids, {add, remove})` — batch tag mutation API for incrementally adding/removing tags on specific memories by ID. Previously, `batchUpdate` could only *set* tags (full replacement), and `renameTag`/`mergeTags` operated globally. No way to do targeted tag add/remove on selected memories.

### 🛠 Implementation
~25 lines added to src/index.js:
- `bulkTag(ids, {add?: string[], remove?: string[]})` — adds and/or removes tags on specified memory IDs
- Deduplication: won't add a tag that already exists
- Reports not-found IDs
- Reindexes tag index and saves store after mutations

5 new tests:
1. Adds and removes tags on multiple memories
2. Skips not-found IDs and reports them
3. Does not add duplicate tags (no-op → updated=0)
4. Handles add-only and remove-only operations
5. Reindexes tag index after modification (verified via tagStats)

### 📊 Results
- **241/241 tests pass** (236 → +5)
- Zero regressions
- Committed: fd3bae4

### ✅ Decision: RETAIN
- Fills a real gap: `batchUpdate` replaces tags entirely; `bulkTag` does incremental add/remove
- Complements `renameTag`/`mergeTags` (global ops) with targeted per-ID ops
- Zero regressions, clean API

### experiments.tsv
```
2026-04-19T01:00	fd3bae4	test_count	241/241	keep	v0.9.8: bulkTag(ids,{add,remove}) batch tag mutation — 5 new tests (236→241). Committed.
```
