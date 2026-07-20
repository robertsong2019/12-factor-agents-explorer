# nano-agent Feature Backlog

## ✅ Existing Features
- Agent core with multi-turn iteration, tool calling, conversation history
- LLM abstraction (mock + OpenAI-compatible)
- Memory with add/search/remove/update/count/recent/clear/persistence
- Tool decorator system with auto parameter extraction
- Context generation with token-aware truncation

## 🔲 Feature Backlog

### Memory Enhancements
- [x] **F1**: `Memory.export_json()` — serialize all entries to JSON string (backup/snapshot) ✅ 2026-06-24
- [x] **F2**: `Memory.import_json()` — load entries from JSON string (restore from backup) ✅ 2026-06-24
- [x] **F3**: `Memory.stats()` — statistics: total, per-tag counts, date range ✅ 2026-06-24
- [x] **F4**: `Memory.add_tag(index, tag)` / `Memory.remove_tag(index, tag)` — tag management by index ✅ 2026-06-24
- [x] **F5**: `Memory.set_importance(index, score)` — manually assign importance scores ✅ 2026-06-25
- [x] **F6**: `Memory.importance_decay(factor)` — simulate time-based forgetting ✅ 2026-06-25
- [x] **F7**: `Memory.forget(threshold)` — remove entries below importance threshold ✅ 2026-06-25
- [x] **F8**: `Memory.top_important(n)` — rank memories by importance ✅ 2026-06-25

### Agent Enhancements
- [x] **F9**: `Agent.run_batch(inputs)` — process multiple inputs in sequence ✅ 2026-07-12
- [x] **F10**: `Agent.summary()` — summarize conversation history ✅ 2026-07-12

### Tool System
- [x] **F11**: `Tool.validate_args()` strict mode — reject unknown parameters ✅ 2026-07-12
- [x] **F12**: `list_tools_by_prefix()` — filter registered tools by name prefix ✅ 2026-07-12
- [x] **F13**: `Memory.search_by_tag(tag)` — search memories by single tag with optional limit ✅ 2026-07-16
- [x] **F14**: `Memory.merge(other)` — merge two Memory instances with content-based dedup ✅ 2026-07-16
- [x] **F15**: `Memory.search_all_tags(tags)` — AND semantic multi-tag search ✅ 2026-07-16
- [x] **F16**: `Memory.distinct_tags()` — sorted unique tag list ✅ 2026-07-16
- [x] **F17**: `Memory.search_fuzzy()` — difflib fuzzy search with threshold ✅ 2026-07-18
- [x] **F18**: `Memory.group_by_tag()` — tag-based grouping, _untagged bucket ✅ 2026-07-18

### Agent Enhancements (Dynamic Tools)
- [x] **F19**: `Agent.add_tool()` / `Agent.remove_tool()` — runtime tool management ✅ 2026-07-18
- [x] **F20**: `Memory.deduplicate()` — similarity-based dedup, preserves earliest ✅ 2026-07-18
- [x] **F21**: `Memory.chain_search()` — multi-query ranked search with optional fuzzy fallback ✅ 2026-07-18

### Memory Advanced Operations
- [x] **F22**: `Memory.snapshot()` / `Memory.restore()` — deep copy snapshot for undo/restore ✅ 2026-07-19
- [x] **F23**: `Memory.search_regex(pattern)` — regex pattern search with IGNORECASE ✅ 2026-07-19
- [x] **F24**: `Memory.filter(predicate)` — functional callback-based filtering ✅ 2026-07-19
- [x] **F25**: `Memory.weighted_search(query)` — 3-factor weighted ranking (content+importance+recency) ✅ 2026-07-19
- [x] **F26**: `Memory.paginate(page, page_size, order)` — pagination with asc/desc ordering ✅ 2026-07-19
- [x] **F27**: `Memory.diff(other)` — two-way diff returning added/removed/common ✅ 2026-07-19

### Memory Set Operations & Analytics
- [x] **F28**: `Memory.intersect(other)` — set intersection, returns common entries (complements diff) ✅ 2026-07-19
- [x] **F29**: `Memory.sample(n, weighted)` — importance-weighted random sampling ✅ 2026-07-19
- [x] **F30**: `Memory.timeline(bucket)` — time-bucketed distribution (hour/day/week/month) ✅ 2026-07-19

### Export & Analytics
- [x] **F31**: `Memory.export_markdown()` / `Memory.export_csv()` — structured export with tag filtering ✅ 2026-07-20
- [x] **F32**: `Memory.cluster(threshold)` — greedy similarity clustering using SequenceMatcher ✅ 2026-07-20
- [x] **F33**: `Memory.compact_summary(max_entries)` — top entries + tag distribution + time span ✅ 2026-07-20
- [x] **F34**: `Memory.histogram(bins)` — importance distribution histogram ✅ 2026-07-20
- [x] **F35**: `Memory.correlation_stats()` — importance-length Pearson r + per-tag averages ✅ 2026-07-20
- [x] **F36**: `Agent.conversation_stats()` — message counts by role, avg length, est tokens ✅ 2026-07-20
- [x] **F37**: `Memory.tag_cloud(min_count, max_tags)` — normalized frequency-weighted tag cloud ✅ 2026-07-20
- [x] **F38**: `Memory.search_in_fields(query, fields)` — field-specific search (content/tags/metadata) with multi-field ranking ✅ 2026-07-20
- [x] **F39**: `Memory.auto_tag(rules, overwrite)` — keyword-based automatic tagging ✅ 2026-07-20

- [x] **F40**: `Memory.export_jsonl()` — JSON Lines export for streaming/ML pipelines ✅ 2026-07-20
- [x] **F41**: `Memory.normalize_tags(mapping)` — batch rename/merge tags with dedup ✅ 2026-07-20
- [x] **F42**: `Memory.entropy()` — Shannon entropy for content & tag diversity ✅ 2026-07-20

- [x] **F43**: `Memory.import_jsonl()` — Import from JSON Lines format, round-trip with F40 export_jsonl ✅ 2026-07-20
- [x] **F44**: `Memory.union(other)` — Set union returning new Memory, content-based dedup preserving self entries ✅ 2026-07-20

## Priorities
**Round 1:** F1-F4 — Memory serialization, stats, and tag management ✅
**Round 2:** F5-F8 — Importance scoring and forgetting ✅
**Round 3:** F9-F12 — Agent batch processing and tool enhancements ✅
**Round 4:** F13-F14 — Tag search and memory merge ✅ 2026-07-16
**Round 5:** F17-F19 — Fuzzy search, tag grouping, dynamic tools ✅ 2026-07-18
**Round 6:** F20-F21 — Deduplicate, chain search ✅ 2026-07-18
**Round 7:** F22-F23 — Snapshot/restore, regex search ✅ 2026-07-19
**Round 8:** F24-F25 — Filter, weighted search ✅ 2026-07-19
**Round 9:** F26-F27 — Paginate, diff ✅ 2026-07-19
**Round 10:** F28-F30 — Intersect, sample, timeline ✅ 2026-07-19
**Round 11:** F31-F33 — Export formats, cluster, compact_summary ✅ 2026-07-20
**Round 12:** F34-F35 — Histogram, correlation_stats ✅ 2026-07-20
**Round 13:** F36-F37 — Conversation_stats, tag_cloud ✅ 2026-07-20
**Round 14:** F38-F39 — Search_in_fields, auto_tag ✅ 2026-07-20
