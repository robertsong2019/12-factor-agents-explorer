# Tech Briefing Skill 📡

Generate daily tech briefings from GitHub Trending and Hacker News.

## Features

- Aggregate GitHub Trending repos + HN top stories in one report
- Filter by language, time range, source
- Markdown or JSON output
- No API key required

## Quick Start

```bash
# Full briefing (Markdown)
python3 scripts/tech_briefing.py

# GitHub only, weekly, Python repos
python3 scripts/tech_briefing.py --source github --since weekly --lang python

# HN only, top 5
python3 scripts/tech_briefing.py --source hn --hn-limit 5
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--format` | `md` | `md` or `json` |
| `--source` | `all` | `all`, `github`, or `hn` |
| `--github-limit` | `10` | Max GitHub repos |
| `--hn-limit` | `10` | Max HN stories |
| `--lang` | _(all)_ | Language filter (`python`, `rust`, etc.) |
| `--since` | `daily` | `daily`, `weekly`, or `monthly` |

## Typical Workflow

1. Run the script to fetch data
2. Agent summarizes highlights
3. Highlights repos/stories relevant to user interests
4. Optionally compare with previous briefings for trends

## Integration

Add to `HEARTBEAT.md` for periodic automated briefings:

```markdown
- [ ] Check tech briefing if not done today
```

## Dependencies

- Python 3
- No API keys needed (uses public endpoints)
