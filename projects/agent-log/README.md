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

# Activity sparkline for the last 14 days
agent-log trend

# Ranked match counts per file (who talks about Docker the most?)
agent-log search "docker" --count
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
| `search <query>` | Search all logs. Flags: `-r` regex, `--from/--to YYYY-MM-DD` date range, `--count` ranked per-file match counts, `-o FILE` export, `-j` JSON |
| `today` | Show today's daily notes + session activity |
| `date <YYYY-MM-DD>` | Show activity for a specific date |
| `summary [N]` | Summarize last N days. Flags: `-k KW` keyword filter, `-t` break down by activity type, `--csv` / `--md` / `-j` output |
| `trend [N]` | Sparkline activity trend over N days (default 14); `-j` for JSON |
| `stats` | Workspace statistics; `--md` / `-j` output |
| `sessions` | List 30 most recent session files with lines/size/mtime; `-j` for JSON |
| `session <id>` | Show one session transcript by exact name or partial pattern; `-j` for JSON |
| `find <pattern>` | Find sessions by content/filename pattern and/or `-a DATE` / `-b DATE` modified-time bounds; `-j` for JSON |
| `grep <pattern>` | Fast grep across session logs (first 50 hits, line numbers) |
| `tail [-n N] [-f]` | Tail the most recent session; `-f` follows as it grows |
| `cron` | List all cron job runs |
| `clean [-n] [-a DAYS]` | Remove empty and old daily notes. **The only command that deletes** — always preview with `-n/--dry-run` first |

All commands that print reports also accept `-j/--json` where noted, so output can be piped into `jq` or fed to scripts. Colors are automatically disabled when stdout is not a TTY or `NO_COLOR` is set.

## Testing

```bash
# Full bats suite (31 tests, fully hermetic — HOME and OPENCLAW_WORKSPACE are
# overridden to a fixture dir with dynamic dates, so runs never touch live data)
bats test/commands.bats test/bugfixes.test.bats test/f19-f20.test.bats

# Performance benchmarks (F18) — 365-day synthetic corpus, per-command timing + thresholds
bash test/bench.sh          # full benchmark run
bats test/bench.test.bats   # 4 smoke tests
```

`test/commands.bats` covers each command's contract on fixture data; `test/bugfixes.test.bats` is a regression suite pinning four real bugs found on 2026-08-22:

1. **help/usage DOA** — `agent-log help` and unknown commands printed 0 bytes (the extraction sed grabbed a `## Usage` heading that didn't exist in the emitted text)
2. **clean data loss** — files whose last line lacked a trailing newline were miscounted as empty by `wc -l == 0` and deleted; emptiness now requires a zero-byte file
3. **find -j invalid JSON** — multi-result JSON output concatenated objects without commas
4. **JSON injection** — unescaped quotes/newlines in query/keyword/pattern/content could break machine-parseable output; all interpolated strings now go through `esc_json`

## How It Works

```
~/.openclaw/workspace/        ← WORKSPACE (override with OPENCLAW_WORKSPACE)
├── memory/                   ← daily notes, YYYY-MM-DD.md
└── *.md (root only)          ← MEMORY.md, README.md, ...

~/.openclaw/sessions/         ← session transcripts (outside the workspace)
```

`agent-log` scans these standard OpenClaw directories using `grep`/`find` and presents results with colorized output. No indexing, no database — just fast text search. Note that `SESSIONS_DIR` is fixed to `~/.openclaw/sessions` and does not follow `OPENCLAW_WORKSPACE`.

## Design Principles

- **Single Bash script, zero dependencies** — works on any Unix system
- **Read-only by default** — the only command that deletes anything is `clean` (preview with `-n/--dry-run`)
- **Pipe-safe** — ANSI colors auto-disabled when stdout is not a TTY or `NO_COLOR` is set
- **JSON everywhere** — machine-readable output for scripting (`-j` on most commands)
- **Colorized output** — easy to scan visually
- **Composable** — pipe to `less`, `wc -l`, `jq`, etc.

## Extending

Want to add a new command? The script is structured as a case statement — just add a new function and wire it into the `case "$1"` block.

## License

MIT
