# context-forge Feature Backlog

## ✅ Existing Features
- Auto-detects project type (Node.js, Python, Go, Rust, etc.)
- Extracts dependencies, scripts, entry points from package.json/pyproject.toml/Cargo.toml
- Maps directory structure and architecture patterns
- Generates context files for multiple AI tools (AGENTS.md, .cursorrules, .github/copilot-instructions.md)
- Updates existing files (preserves manual additions in marked sections)
- Zero dependencies, single file Node.js script
- CLI with options: --only, --dry-run, --update, --json

## 🔲 Feature Backlog

### Core Analysis
- [x] **F8**: .gitignore parsing — respect ignored paths during analysis ✅ 2026-06-17
- [x] **F2**: Import statement analysis — actual imports from source files (not just package.json) ✅ 2026-06-17
- [x] **F3**: API surface extraction — exported functions/classes/methods from source files ✅ 2026-06-18
- [x] **F4**: Configuration file parser — tsconfig, eslint, prettier, docker, vite/webpack/tailwind ✅ 2026-06-18
- [x] **F1**: Git history analysis — commit patterns, contributors, recent activity ✅ 2026-06-20

### Output Formats
- [x] **F5**: Mermaid.js diagrams — directory structure visualization ✅ 2026-06-19
- [x] **F6**: Markdown tables — better formatted dependency/script lists ✅ 2026-06-21
- [x] **F7**: TOML/YAML export — structured output for other tools ✅ 2026-06-21

### Quality & Safety
- [x] **F9**: File size limits — skip huge files in analysis ✅ 2026-06-19
- [x] **F10**: Validation mode — check generated files against actual codebase ✅ 2026-06-19

### Developer Experience
- [ ] **F11**: Watch mode — regenerate on file changes
- [x] **F12**: Diff preview — show what would change before updating ✅ 2026-06-20
- [x] **F13**: Template system — customizable output templates ✅ 2026-06-21
- [x] **F14**: Cache analysis results — faster re-runs ✅ 2026-06-21

### Testing & Documentation
- [x] **F15**: Unit tests for core functions
- [x] **F16**: Integration tests with real projects ✅ 2026-06-21
- [ ] **F17**: Performance benchmarks on large repos
- [ ] **F18**: Documentation examples for each generated file type

### Security & Quality
- [x] **F32**: Secret detection — scan source for API keys, tokens, passwords ✅ 2026-06-23
- [x] **F33**: Documentation readability analysis — A-F scoring with 15+ metrics ✅ 2026-06-23

## Priorities
**Round 1 (Core):** F1, F2, F3 — Better codebase understanding
**Round 2 (Output):** F5, F6 — Better visualization
**Round 3 (DX):** F11, F12 — Better workflow