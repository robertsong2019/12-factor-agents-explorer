# Key Development Task 3 (Loop C) - 2026-04-28 01:00

## Focus: Autoresearch Methodology — Experiment Loop C (Build on k-d-2/3)

### Baseline
- 491 tests passing (after searchByContent from k-d-2 + contentRollback from k-d-3 + bulkReclassify)
- Full pipeline including pattern search, content versioning/rollback, temporal/entity/fact search

### 🎯 Target
Add **`contentBranch(id, opts)`** — fork a memory as an independent branch with bidirectional links.

**Problem:** When experimenting with memory content (e.g., trying different summaries, exploring alternative phrasings), the only option was to `update()` the original (losing the old version in active use) or manually `add()` + `link()`. No clean "fork this memory and evolve it independently" operation.

**Solution:** `contentBranch` creates a new memory as a copy of the source, with optional overrides for content/layer/tags/entities. Automatically creates bidirectional `derived_from` links. The branch evolves independently — updates to it don't affect the source.

### 🛠 Implementation

**Added to src/index.js (~25 lines):**
- `contentBranch(id, opts)`: validates source exists, creates new memory via `add()`, creates bidirectional `derived_from` links
- Options: `content` (override), `layer`, `tags`, `entities` — all default to source values
- Sets `source` metadata to `branch:<originalId>` for traceability
- Supports chained branches (branch of a branch)

### 📊 Testing

**8 new tests:**
1. ✅ Creates new memory as branch with copied fields
2. ✅ Creates bidirectional derived_from links
3. ✅ Allows overriding content
4. ✅ Allows overriding layer and tags
5. ✅ Sets source metadata to branch:originalId
6. ✅ Returns null for non-existent memory
7. ✅ Branch evolves independently from source
8. ✅ Supports chained branches (branch of a branch)

**Results:**
- 491 → 499 tests (+8, all passing)
- Zero failures
- ~25 lines added to src/index.js
- Committed: `22e98a3`

### ✅ Decision: RETAIN

**Rationale:**
- Enables safe content experimentation — fork, try, keep or discard without touching original
- Completes the content branching story alongside versioning (history/diff/rollback)
- Bidirectional links mean you can traverse branch trees via `getLinks` and `traverseGraph`
- Minimal code — reuses existing `add()` and `link()` primitives
- Chained branches support deep exploration trees

### experiments.tsv
```
2026-04-28T01:00	22e98a3	test_count	499/499	keep	contentBranch(id, opts) — fork memory as independent branch with bidirectional derived_from links. 8 new tests (491→499), ~25 lines src. Builds on k-d-2 searchByContent + k-d-3 contentRollback.
```

### 🔮 Potential Next Steps
1. `memoryMerge` v2 with conflict resolution strategies (content strategy: concat/keep-newer/keep-longer/manual)
2. Persist contentVersions to disk (JSON sidecar) — survive restarts
3. `autoTag` v2 with embedding-based similarity
4. `searchByBranch(id)` — find all branches of a memory via derived_from links
5. Content version persistence (survive restarts)

---

**Generated**: 2026-04-28 01:00 AM
**Status:** ✅ Complete — contentBranch() API added, 8 new tests, 499/499 passing
