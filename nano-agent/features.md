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

### Agent Enhancements
- [ ] **F5**: `Agent.run_batch(inputs)` — process multiple inputs in sequence
- [ ] **F6**: `Agent.summary()` — summarize conversation history

### Tool System
- [ ] **F7**: `Tool.validate_args()` strict mode — reject unknown parameters
- [ ] **F8**: `list_tools_by_prefix()` — filter registered tools by name prefix

## Priorities
**Round 1:** F1, F2, F3 — Memory serialization and stats
**Round 2:** F4, F5 — Tag management and batch processing
