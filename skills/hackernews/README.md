# Hacker News Skill 🟧

Browse and search Hacker News directly from OpenClaw.

## Features

- Browse top, new, best, Ask HN, Show HN stories
- View item details and comment threads
- Search stories and comments via Algolia
- Find "Who is hiring?" threads
- JSON output for programmatic use

## Quick Start

```bash
# Top 10 trending stories
scripts/hn.sh top

# Search for AI topics
scripts/hn.sh search "artificial intelligence"

# Show comments on a story
scripts/hn.sh comments 12345

# Who is hiring this month?
scripts/hn.sh whoishiring
```

## Usage Patterns

### Trending Monitoring
Ask "what's trending on HN?" → fetches top stories, summarizes highlights.

### Research
Ask "search HN for discussions about Rust" → returns relevant threads with context.

### Job Hunting
Ask "who is hiring on HN?" → finds latest hiring thread, filters by keyword.

## Dependencies

- `curl` and `jq` (standard on most systems)
- No API key required

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Skill definition and usage instructions |
| `scripts/hn.sh` | CLI tool for HN API |
