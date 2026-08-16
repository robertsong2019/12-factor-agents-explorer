# ctxpack Features

## Core (v0.1.0) ✅
- [x] Smart directory scanning (respects .gitignore)
- [x] Language detection (10+ languages)
- [x] Framework detection (Next, React, Vue, FastAPI, Django, etc.)
- [x] Key file categorization (entry, config, schema, docs, test, agent_context)
- [x] Export extraction (TS/JS, Python, Go)
- [x] Token estimation
- [x] Multiple output formats (agents, claude, cursor, generic)
- [x] Stats mode (--stats JSON output)
- [x] CLI interface (argparse)

## Recent Additions
- [x] **`.ctxpackignore`** — ctxpack-specific ignore file ✅ 2026-05-05
- [x] **Include inline source** — embed key file contents in output ✅ 2026-05-13
- [x] **`--exclude` flag** — exclude additional file patterns ✅ 2026-05-16

## Planned
- [ ] **Diff mode** — compare generated context with existing file, show changes → ✅ 2026-05-14 (3 tests)
- [x] **Watch mode** (`--watch` + `--interval`) — polling fingerprint (mtime+size), auto-regenerate on change, output-file excluded to prevent feedback loop ✅ 2026-08-16 (13 tests)
