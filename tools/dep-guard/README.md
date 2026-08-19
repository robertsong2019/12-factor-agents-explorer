# dep-guard 🔒

Lightweight dependency health & security scanner for Node.js and Python projects.

## Features

- 🔍 Detects outdated dependencies
- ⚠️ Flags known vulnerabilities (npm audit / pip audit)
- 📊 Generates health score (0-100)
- 📋 Multiple output formats (text, json, markdown)
- 🚀 Zero config — runs against package.json or requirements.txt

## Install

```bash
# Copy to PATH or run directly
chmod +x dep-guard.sh
./dep-guard.sh /path/to/project
```

## Usage

```bash
# Scan current directory
dep-guard.sh .

# Scan specific project
dep-guard.sh ~/projects/my-app

# JSON output
dep-guard.sh --format json ~/projects/my-app

# Markdown report
dep-guard.sh --format markdown ~/projects/my-app

# CSV (machine-readable)
dep-guard.sh --format csv ~/projects/my-app

# Only security check (skip outdated)
dep-guard.sh --security-only ~/projects/my-app

# CI mode: exit 1 if score < threshold
dep-guard.sh --min-score 70 ~/projects/my-app

# CI mode: exit 1 if specific findings exist
dep-guard.sh --fail-on vuln ~/projects/my-app    # any vulnerability
dep-guard.sh --fail-on major ~/projects/my-app   # any major-outdated package
dep-guard.sh --fail-on outdated ~/projects/my-app # any outdated package

# Exclude intentionally-pinned packages
dep-guard.sh --ignore lodash,express ~/projects/my-app
```

## Health Score Calculation

Per-item deduction from 100, clamped to \[0, 100\]:

| Finding | Deduction |
|--------|-----------|
| Each high/critical vulnerability | -15 |
| Each low/moderate vulnerability | -5 |
| Each major-outdated package | -5 |
| Each minor/patch-outdated package | -2 |
| No lock file | -5 |

## JSON Output

`--format json` includes counts plus `details` arrays (severity/name/title for
vulnerabilities, current/latest for outdated packages).

## Tests

```bash
bash test/run.sh   # 58 hermetic tests, zero network (stubs npm/pip)
```

## Example Output

```
╔══════════════════════════════════════╗
║  dep-guard · Dependency Health Scan  ║
╠══════════════════════════════════════╣
║  Project: my-app                     ║
║  Type:    node                       ║
║  Score:   82/100 ✅                  ║
╠══════════════════════════════════════╣
║                                      ║
║  🔒 Security (0 issues)             ║
║  📦 Outdated (3 packages)            ║
║    • express 4.18 → 5.0 (major)     ║
║    • lodash 4.17.20 → 4.17.21       ║
║    • jest 29.0 → 29.7 (minor)       ║
║  🔐 Lockfile: package-lock.json ✓   ║
║                                      ║
╚══════════════════════════════════════╝
```
