# agent-log 📋

A CLI tool for searching, filtering, and summarizing OpenClaw session logs and memory files.

## Why

OpenClaw accumulates session transcripts, memory files, and daily notes. There's no quick way to:
- Search across all logs for a keyword/topic
- See a timeline of activity
- Summarize what happened on a given day
- Find when something was discussed

`agent-log` fills that gap with a single zero-dependency Bash script.

## Install

```bash
cd ~/.openclaw/workspace/projects/agent-log
chmod +x agent-log.sh
ln -s "$(pwd)/agent-log.sh" /usr/local/bin/agent-log  # optional
```

## Quick Start

```bash
# What did I do today?
agent-log today

# Search for discussions about Docker
agent-log search "docker"

# What happened in the last week?
agent-log summary 7
```

## Usage

```bash
# Search across all logs for a keyword
agent-log search "docker"

# Search with context (show surrounding lines)
agent-log search "docker" -C 3

# Show today's activity timeline
agent-log today

# Show activity for a specific date
agent-log date 2026-04-01

# Summarize recent activity (last N days)
agent-log summary 7

# List all cron job runs
agent-log cron

# Show session stats
agent-log stats
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `search <query>` | Search all logs for a keyword |
| `today` | Show today's activity timeline |
| `date <YYYY-MM-DD>` | Show activity for a specific date |
| `summary <N>` | Summarize last N days of activity |
| `cron` | List all cron job runs |
| `stats` | Show session statistics |

## Testing

```bash
# Full bats suite (18 tests, fully sandboxed — HOME is overridden to a fixture dir)
bats test/commands.bats test/bugfixes.test.bats
```

`test/commands.bats` covers each command's contract on fixture data; `test/bugfixes.test.bats` is a regression suite pinning four real bugs found on 2026-08-22:

1. **help/usage DOA** — `agent-log help` and unknown commands printed 0 bytes (the extraction sed grabbed a `## Usage` heading that didn't exist in the emitted text)
2. **clean data loss** — files whose last line lacked a trailing newline were miscounted as empty by `wc -l == 0` and deleted; emptiness now requires a zero-byte file
3. **find -j invalid JSON** — multi-result JSON output concatenated objects without commas
4. **JSON injection** — unescaped quotes/newlines in query/keyword/pattern/content could break machine-parseable output; all interpolated strings now go through `esc_json`

## How It Works

```
~/.openclaw/workspace/
├── memory/          ← agent-log reads daily notes (YYYY-MM-DD.md)
├── sessions/        ← session transcripts (if available)
└── .openclaw/       ← cron logs, config
```

`agent-log` scans these standard OpenClaw directories using `grep`/`ripgrep` and presents results with colorized output. No indexing, no database — just fast text search.

## Design Principles

- **Single Bash script, zero dependencies** — works on any Unix system
- **Read-only** — never modifies your logs
- **Respects `.gitignore`** — skips binary files and ignored paths
- **Colorized output** — easy to scan visually
- **Composable** — pipe to `less`, `wc -l`, etc.

## Extending

Want to add a new command? The script is structured as a case statement — just add a new function and wire it into the `case "$1"` block.

## License

MIT
