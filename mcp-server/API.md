# API Reference — OpenClaw MCP Server

Complete reference for all 18 tools exposed by the MCP Server.

> **Base path**: All file operations are sandboxed to `OPENCLAW_WORKSPACE` (default: `cwd`).
> Paths are resolved relative to the workspace root; traversal (`../`) is blocked.

---

## File Operations

### `read`

Read file contents with optional line range.

```json
{ "path": "src/index.ts", "offset": 10, "limit": 20 }
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | ✅ | — | File path relative to workspace |
| `offset` | number | — | 1 | Start line (1-indexed) |
| `limit` | number | — | all | Max lines to read |

**Response:**
```json
{ "path": "src/index.ts", "lines": 20, "content": "..." }
```

---

### `write`

Write content to a file (creates or overwrites). Parent directories are created automatically.

```json
{ "path": "notes/todo.md", "content": "# Tasks\n- [ ] Fix bug" }
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | ✅ | File path |
| `content` | string | ✅ | Content to write |

**Response:**
```json
{ "path": "notes/todo.md", "success": true, "bytesWritten": 20 }
```

---

### `edit`

Replace exact text in a file. Replaces **all** occurrences.

```json
{ "path": "config.json", "oldText": "\"debug\": false", "newText": "\"debug\": true" }
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | ✅ | File path |
| `oldText` | string | ✅ | Exact text to find (must match exactly) |
| `newText` | string | ✅ | Replacement text |

**Response:**
```json
{ "success": true, "replacements": 1, "bytesChanged": 4 }
```

Returns `{ "success": false, "error": "oldText not found in file" }` if no match.

---

### `append`

Append content to a file. Creates the file if it doesn't exist.

```json
{ "path": "log.txt", "content": "New entry\n", "newline": true }
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | ✅ | — | File path |
| `content` | string | ✅ | — | Content to append |
| `newline` | boolean | — | `true` | Prepend newline if file is non-empty |

**Response:**
```json
{ "success": true, "bytesWritten": 10, "totalSize": 510 }
```

---

### `delete`

Delete a file or **empty** directory. Irreversible.

```json
{ "path": "temp/old-file.txt" }
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | ✅ | File or empty directory path |

**Response:**
```json
{ "success": true }
```

Returns `{ "success": false, "error": "Directory not empty, cannot delete" }` for non-empty dirs.

---

### `move`

Move or rename a file/directory within the workspace.

```json
{ "source": "draft.md", "destination": "published/draft.md" }
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source` | string | ✅ | Source path |
| `destination` | string | ✅ | Destination path |

---

### `copy`

Copy a file or directory (recursive) within the workspace.

```json
{ "source": "src/config.ts", "destination": "src/config.ts.bak" }
```

Parameters same as `move`.

---

### `create_directory`

Create a directory and all parent directories.

```json
{ "path": "projects/new-app/src" }
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | ✅ | Directory path |

**Response:**
```json
{ "success": true, "created": true }
```

`created: false` means the directory already existed.

---

## Search & Discovery

### `list_files`

List files in a directory.

```json
{ "path": "src", "recursive": true, "maxDepth": 3 }
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | — | `"."` | Directory path |
| `recursive` | boolean | — | `false` | List subdirectories |
| `maxDepth` | number | — | `0` | Max depth when recursive (0 = unlimited) |

**Response:**
```json
{
  "path": "src", "count": 5,
  "files": [
    { "name": "index.ts", "path": "src/index.ts", "type": "file", "size": 2048 },
    { "name": "tools", "path": "src/tools", "type": "directory", "size": 4096 }
  ]
}
```

---

### `find_files`

Find files by glob pattern.

```json
{ "pattern": "**/*.test.ts", "maxResults": 20 }
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | string | ✅ | — | Glob pattern (e.g. `**/*.ts`, `src/*.test.js`) |
| `path` | string | — | `"."` | Search root |
| `maxDepth` | number | — | `10` | Max depth |
| `maxResults` | number | — | `100` | Max results (1–500) |

**Response:**
```json
{ "pattern": "**/*.test.ts", "count": 3, "files": ["src/tools.test.ts", "src/index.test.ts"] }
```

---

### `search_files`

Search file contents by regex.

```json
{ "pattern": "TODO|FIXME", "include": "*.ts", "maxResults": 30 }
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | string | ✅ | — | Regex pattern |
| `path` | string | — | `"."` | Search root |
| `include` | string | — | `"*"` | Glob filter for file names |
| `maxResults` | number | — | `50` | Max matches (1–200) |

**Response:**
```json
{
  "pattern": "TODO", "totalMatches": 2, "files": 1,
  "results": [{ "file": "src/index.ts", "matches": [{ "line": 42, "text": "// TODO: refactor" }] }]
}
```

---

### `file_info`

Get file metadata. Optionally compute SHA-256 hash.

```json
{ "path": "package.json", "computeHash": true }
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | ✅ | — | File or directory path |
| `computeHash` | boolean | — | `false` | Compute SHA-256 (files only) |

**Response:**
```json
{
  "success": true, "type": "file", "size": 1024, "sizeHuman": "1.0KB",
  "created": "2026-01-15T...", "modified": "2026-05-01T...",
  "permissions": "644", "sha256": "a1b2c3..."
}
```

### `head`

Read the first N lines of a text file. Useful for previewing large files without loading them entirely.

```json
{ "path": "large-log.txt", "lines": 20 }
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | ✅ | — | File path relative to workspace |
| `lines` | number | — | `10` | Number of lines from the beginning |

**Response:**
```json
{
  "tool": "head", "path": "large-log.txt",
  "requestedLines": 20, "totalLines": 1500, "returnedLines": 20,
  "content": "first 20 lines..."
}
```

Returns fewer lines than requested if the file is shorter.

---

### `tail`

Read the last N lines of a text file. Useful for checking the end of log files or large files.

```json
{ "path": "app.log", "lines": 50 }
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | ✅ | — | File path relative to workspace |
| `lines` | number | — | `10` | Number of lines from the end |

**Response:**
```json
{
  "tool": "tail", "path": "app.log",
  "requestedLines": 50, "totalLines": 1200, "returnedLines": 50,
  "content": "last 50 lines..."
}
```

---

## Execution

### `exec`

Execute shell commands. **Dangerous patterns are blocked** (see Security below).

```json
{ "command": "npm test", "workdir": "projects/my-app", "timeout": 60 }
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `command` | string | ✅ | — | Shell command |
| `workdir` | string | — | workspace root | Working directory |
| `env` | object | — | `{}` | Environment variables |
| `timeout` | number | — | `30` | Timeout in seconds |
| `yieldMs` | number | — | — | ms before backgrounding |
| `background` | boolean | — | `false` | Run in background |
| `pty` | boolean | — | `false` | Use pseudo-terminal |

**Response:**
```json
{ "exitCode": 0, "stdout": "...", "stderr": "" }
```

---

## Memory

### `memory_search`

Search `MEMORY.md` and `memory/*.md` files by keyword.

```json
{ "query": "project architecture" }
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | ✅ | Keyword or phrase |

**Response:**
```json
{
  "query": "project architecture", "totalMatches": 3,
  "results": [
    { "file": "MEMORY.md", "matches": [{ "line": 15, "text": "## Project Architecture" }] },
    { "file": "memory/2026-05-01.md", "matches": [{ "line": 8, "text": "Discussed architecture with..." }] }
  ]
}
```

---

## Web

### `web_search`

Search the web (requires OpenClaw API integration for full results).

```json
{ "query": "MCP protocol specification", "count": 5, "freshness": "week" }
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | ✅ | — | Search query |
| `count` | number | — | `5` | Results (1–10) |
| `country` | string | — | `"US"` | 2-letter country code |
| `language` | string | — | — | ISO 639-1 language code |
| `freshness` | string | — | — | `"day"`, `"week"`, `"month"`, `"year"` |

---

## System

### `system_status`

Get runtime info. No parameters.

**Response:**
```json
{
  "platform": "linux", "arch": "x64", "nodeVersion": "v22.22.1",
  "pid": 12345, "uptime": 3600,
  "memory": { "rss": "85MB", "heapUsed": "42MB", "heapTotal": "56MB" },
  "workspace": "/root/.openclaw/workspace"
}
```

---

## Security

### Path Sandboxing

All file paths are resolved relative to `OPENCLAW_WORKSPACE`. Paths attempting traversal (`../`) are rejected with:

```json
{ "error": "Path traversal denied: ../../../etc/passwd" }
```

### Command Blocklist

The following patterns are blocked in `exec`:

| Pattern | Reason |
|---------|--------|
| `rm -rf /` | Recursive root deletion |
| `rm -rf ../` | Parent directory deletion |
| `dd if=` | Raw disk operations |
| `mkfs` | Filesystem formatting |
| `:>/` | File truncation |
| `format [a-z]:` | Windows format |
| `del /[sfq] *` | Windows bulk delete |
| `chmod 777 /` | Insecure permissions |
| `chown .*: /` | Ownership change to root |
| `wget \| sh` | Remote script execution |
| `curl \| sh` | Remote script execution |
| `eval $()` | Command injection |
| `> /dev/.*d` | Device file writes |

**Blocked response:**
```json
{ "exitCode": -1, "stderr": "Command rejected: Command contains dangerous pattern" }
```

---

## Transport

Currently supports **stdio** transport. The server reads JSON-RPC from stdin and writes to stdout.

**Planned**: Streamable HTTP transport for remote access.

### Starting the Server

```bash
# Via npx
npx openclaw-mcp-server

# Direct
node dist/index.js

# With custom workspace
OPENCLAW_WORKSPACE=/path/to/project node dist/index.js
```

### MCP Client Configuration

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "openclaw": {
      "command": "node",
      "args": ["/path/to/openclaw-mcp-server/dist/index.js"],
      "env": { "OPENCLAW_WORKSPACE": "/path/to/project" }
    }
  }
}
```
