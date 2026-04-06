# 🔍 Code Archaeologist

> *"Every codebase tells a story. This tool excavates it."*

AI-powered git history analyzer that generates narrative reports about how a project evolved — like an archaeological dig through your commit history.

## What It Does

- **Excavates** git log, blame data, and file churn patterns
- **Identifies** phases of development (foundation, growth, refactoring, decay)
- **Narrates** the story: who built what, when momentum shifted, where technical debt accumulated
- **Generates** a readable markdown "dig report"

## Quick Start

```bash
cd /path/to/any/git/repo
python3 /path/to/code-archaeologist/archaeologist.py .
```

## Example Output

```
🏛️ EXCAVATION REPORT: my-project
═══════════════════════════════════════

📍 SITE: my-project (312 commits, 47 files, 14 contributors)
⏰ STRATA: 2024-01-15 → 2026-04-06 (2.2 years)

LAYER 1 — Foundation Period (Jan-Mar 2024)
  Early settlers: alice, bob
  Core artifacts: src/main.py, src/config.py
  Activity: HIGH | Focus: Greenfield development
  Pattern: Rapid iteration, daily commits, small files
  
LAYER 2 — Growth Explosion (Apr-Aug 2024)  
  New arrivals: charlie, diana
  Key artifacts: src/api/, src/models/, tests/
  Activity: VERY HIGH | Focus: Feature expansion
  Pattern: Large batch commits, growing file sizes
  ⚠️  First signs of technical debt in src/utils.py

...
```

## Why?

Because `git log --oneline` tells you *what* happened, but not the *story*. 
This tool finds the narrative hiding in your commit history.

## License

MIT
