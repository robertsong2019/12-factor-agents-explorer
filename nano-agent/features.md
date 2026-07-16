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

## Priorities
**Round 1:** F1-F4 — Memory serialization, stats, and tag management ✅
**Round 2:** F5-F8 — Importance scoring and forgetting ✅
**Round 3:** F9-F12 — Agent batch processing and tool enhancements ✅
**Round 4:** F13-F14 — Tag search and memory merge ✅ 2026-07-16
