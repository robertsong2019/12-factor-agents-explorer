# agent-log Feature Backlog

## ✅ Existing Features
- `search` command: Search all logs for a keyword with colorized output
- `today` command: Show today's activity timeline
- `date` command: Show activity for a specific date
- `summary` command: Summarize last N days of activity (line counts)
- `cron` command: List all cron job runs
- `stats` command: Show workspace statistics (file counts, sizes)
- Colorized output for better readability
- Zero dependencies, single Bash script

## 🔲 Feature Backlog

### Search Enhancements
- [x] **F1**: `search` with regex support — `-r`/`--regex` flag ✅ (previously done)
- [x] **F2**: `search` with date range filtering (`--from`/`--to` YYYY-MM-DD) ✅ 2026-05-30
- [x] **F3**: `search` with export — save results to file (`-o results.txt`) ✅ 2026-04-30

### Timeline & Summary
- [x] **F4**: `summary` with keyword filtering — show only entries matching a pattern ✅ 2026-06-01
- [x] **F5**: `summary` with activity types — categorize by coding/research/planning ✅ 2026-05-26
- [x] **F6**: `trend` command — show activity trends over time (sparkline bars) ✅ 2026-05-26

### Session Analysis
- [x] **F7**: `sessions` command — list all session files with metadata ✅ 2026-05-19
- [x] **F8**: `session <id>` command — show detailed session transcript ✅ 2026-05-24
- [x] **F9**: `find` command — find sessions by agent/model/date ✅ 2026-05-25

### Output Formats
- [x] **F10**: JSON output mode — `-j` flag for structured output ✅ 2026-04-30
- [x] **F11**: CSV export — export stats/summary as CSV ✅ 2026-05-19
- [x] **F12**: Markdown export — `--md` flag for summary/stats ✅ 2026-05-24
- [x] **F9**: `find` command — find sessions by pattern/date ✅ 2026-05-25
- [x] **F13**: `grep` wrapper — fast grep across session files ✅ 2026-05-25
- [x] **F14**: `tail` wrapper — watch latest session file ✅ 2026-05-25

### Utilities
- [x] **F13**: `grep` wrapper — fast grep across session files ✅ 2026-05-25
- [x] **F14**: `tail` wrapper — watch latest session file ✅ 2026-05-25
- [x] **F15**: `clean` command — remove old/empty log files (--dry-run, --age) ✅ 2026-05-19

### Testing & Quality
- [x] **F16**: Unit tests for each command (Bats framework) ✅ 2026-08-22 (18 bats tests incl. 10 regression tests for 4 real bugs: help DOA, clean data loss, find -j JSON, escaping)
- [x] **F17**: Integration tests with sample fixture data ✅ 2026-05-30
- [ ] **F18**: Performance benchmarks for large log sets

## Priorities
**Round 1 (Core UX):** F1, F4, F10 — Improve search and add JSON output
**Round 2 (Analysis):** F6, F7, F8 — Better session and trend analysis
**Round 3 (Quality):** F16, F17 — Add test coverage
