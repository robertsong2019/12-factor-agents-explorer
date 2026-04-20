# Key Development Task 3 (Loop C) - 2026-04-20 01:00

## Focus: Autoresearch Methodology — Experiment Loop C

### Baseline
- v0.9.x, 278 tests, searchUnified() 3-way RRF fusion

### 🎯 Target
Add `suggestTags(content, opts)` — tag recommendation API based on content analysis.

### 🛠 Implementation
1. **`suggestTags(content, opts)`** — analyzes content against existing tag distributions using:
   - Tag name direct match in content (0.5 weight)
   - Keyword overlap with tagged memories' content (0.4 weight)
   - Frequency bonus for popular tags (0.1 weight)
   - Supports `limit`, `minScore`, `layer` filters

### 📊 Results
- **284/284 tests pass** (was 278 → +6)
- ~55 lines added to src
- 6 new tests covering: keyword overlap, empty state, tag name match, limit, minScore, layer filter

### ✅ Decision: RETAIN
- Solves real agent need: auto-tagging memories on creation
- Backward compatible, zero regressions
- Complements existing tagStats/tagCloud/bulkTag APIs

### experiments.tsv
```
2026-04-19T17:00	ca68eec	test_count	284/284	keep	suggestTags() — tag recommendation via content overlap, tag name match, frequency bonus. 6 new tests (278→284).
```
