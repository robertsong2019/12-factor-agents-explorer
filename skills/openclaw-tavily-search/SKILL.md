---
name: tavily-search
description: "Web search via Tavily API (alternative to Brave). Use when the user asks to search the web / look up sources / find links and Brave web_search is unavailable or undesired. Returns a small set of relevant results (title, url, snippet) and can optionally include short answer summaries."
---

# Tavily Search

Use the bundled script to search the web with Tavily.

## Requirements

- Provide API key via either:
  - environment variable: `TAVILY_API_KEY`, or
  - `~/.openclaw/.env` line: `TAVILY_API_KEY=...`

## CLI Reference

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query` | string | (required) | Search query |
| `--max-results` | int | 5 | Number of results (1–10) |
| `--include-answer` | flag | off | Include AI-generated short answer |
| `--search-depth` | `basic`/`advanced` | `basic` | `advanced` = deeper, slower, better |
| `--format` | `raw`/`brave`/`md` | `raw` | Output format (see below) |

## Examples

```bash
# Basic search (raw JSON)
python3 {baseDir}/scripts/tavily_search.py --query "LLM agent frameworks 2026"

# With AI-generated answer summary
python3 {baseDir}/scripts/tavily_search.py --query "Rust vs Go performance" --include-answer

# Deep search for research
python3 {baseDir}/scripts/tavily_search.py --query "MCP protocol specification" --search-depth advanced

# Brave-compatible format (for pipeline compatibility)
python3 {baseDir}/scripts/tavily_search.py --query "OpenClaw setup guide" --format brave

# Human-readable Markdown
python3 {baseDir}/scripts/tavily_search.py --query "best restaurants Tokyo" --format md --max-results 3

# Pipe to jq for filtering
python3 {baseDir}/scripts/tavily_search.py --query "python async" --format raw | jq '.results[0].url'
```

## Output Formats

### `raw` (default)
```json
{
  "query": "...",
  "answer": "...",
  "results": [{"title": "...", "url": "...", "content": "..."}]
}
```
- `content` = full snippet from Tavily (can be long)
- `answer` only present if `--include-answer` is set

### `brave`
```json
{
  "query": "...",
  "results": [{"title": "...", "url": "...", "snippet": "..."}]
}
```
- `snippet` = same as `content`, renamed for Brave API compatibility
- Use when piping into tools expecting `web_search` schema

### `md`
```markdown
1. Title
   https://example.com
   - Snippet text here
```
- Compact Markdown list, ideal for reading or pasting into notes

## Programmatic Usage (Python)

```python
import subprocess, json

def search(query, max_results=3):
    result = subprocess.run(
        ["python3", "path/to/tavily_search.py",
         "--query", query, "--max-results", str(max_results),
         "--format", "raw"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)
```

## Best Practices

- **Keep `max-results` small** (3–5) to reduce token load
- **Use `basic` depth** for quick lookups; `advanced` only for research
- **Return URLs + snippets** to user; fetch full pages (`web_fetch`/`tavily_extract`) only when needed
- **Always include `--include-answer`** when the user needs a quick factual answer, not a link list

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Missing TAVILY_API_KEY` | No key configured | Set env var or add to `~/.openclaw/.env` |
| `Tavily returned non-JSON` | API error or rate limit | Check key validity; retry after 60s |
| Empty results | Query too specific | Broaden query or try `--search-depth advanced` |
| Timeout | Network issue | Default timeout is 30s; check connectivity |

## Rate Limits

- Free tier: ~1000 requests/month
- Keep `max-results` ≤ 5 for routine queries
- Prefer caching results when doing multi-step research
