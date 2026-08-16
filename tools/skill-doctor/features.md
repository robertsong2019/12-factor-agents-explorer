# skill-doctor Features

## Core (v1.0.0) ✅
- [x] SKILL.md existence & size check
- [x] SKILL.md description detection
- [x] README.md existence check
- [x] Oversized files detection (>500KB)
- [x] Suspicious patterns detection (eval, injection, pipe-to-shell)
- [x] Script references validation
- [x] node_modules / .gitignore check
- [x] package.json validation
- [x] CLI interface with exit codes (0=pass, 1=warn, 2=fail)
- [x] Multiple directory support

## Planned
- [x] **JSON output** (`--json`) — machine-readable output for CI integration ✅ 2026-05-09
- [x] **Custom checks** — load additional checks from `.skill-doctor.js` ✅ 2026-05-16
- [x] **Quiet mode** (`--quiet`) — only show warnings/failures ✅ 2026-05-16
- [x] **Auto-fix** (`--fix`) — auto-fix simple issues (add .gitignore, create SKILL.md/README.md) ✅ 2026-05-14 (7 tests)
- [x] **GitHub Actions format** (`--format github`) — emit `::error`/`::warning` workflow-command annotations (CI inline annotations, `%`/newline escaped, --json takes precedence) ✅ 2026-08-16 (11 tests)
