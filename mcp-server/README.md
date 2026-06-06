# OpenClaw MCP Server

Expose OpenClaw core tools via the Model Context Protocol (MCP).

## Overview

The OpenClaw MCP Server acts as a bridge between AI agents and OpenClaw's powerful toolset. It implements the [Model Context Protocol](https://modelcontextprotocol.io/), allowing any MCP-compatible client (Claude Desktop, MCP Inspector, etc.) to access OpenClaw tools in a standardized way.

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   AI Agent      │ ←──→ │  OpenClaw MCP    │ ←──→ │  File System    │
│  (MCP Client)   │ MCP  │     Server       │ I/O  │  + Memory + Web │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                               │
                               ├── stdio (current)
                               └── Streamable HTTP (planned)
```

### Core Components

1. **MCP Server** (`src/index.ts`)
   - MCP protocol via `@modelcontextprotocol/sdk`
   - Streamable HTTP transport
   - Tool routing and request handling

2. **Tools Module** (`src/tools.ts`)
   - 16 tool definitions with JSON Schema input validation
   - Path sandboxing (`safePath()` — prevents traversal)
   - Command validation (`validateExecCommand()` — blocks dangerous patterns)
   - Workspace-rooted file operations
   - Memory search across MEMORY.md + memory/*.md

3. **Security Layer**
   - Path sandboxing: all paths resolved relative to `OPENCLAW_WORKSPACE`
   - Command blocklist: dangerous shell patterns rejected
   - Directory deletion: only empty dirs can be removed

## Supported Tools

18 tools spanning file operations, search, execution, and system introspection:

### File Operations

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `read` | Read file contents with optional line range | `path`, `offset`, `limit` |
| `write` | Write/create files (overwrites) | `path`, `content` |
| `append` | Append content to files | `path`, `content`, `newline` |
| `edit` | Find & replace exact text in a file | `path`, `oldText`, `newText` |
| `delete` | Delete a file or empty directory | `path` |
| `move` | Move/rename files or directories | `source`, `destination` |
| `copy` | Copy files or directories (recursive) | `source`, `destination` |
| `create_directory` | Create directory with parents | `path` |
| `list_files` | List directory contents (optional recursive) | `path`, `recursive`, `maxDepth` |
| `find_files` | Find files by glob pattern | `pattern`, `path`, `maxResults` |
| `file_info` | File metadata (size, timestamps, SHA-256) | `path`, `computeHash` |
| `search_files` | Regex search across files | `pattern`, `path`, `include`, `maxResults` |
| `head` | Read first N lines of a file (preview large files) | `path`, `lines` |
| `tail` | Read last N lines of a file (check log endings) | `path`, `lines` |

### System & Search

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `exec` | Execute shell commands (with safety checks) | `command`, `workdir`, `timeout` |
| `web_search` | Web search via Brave Search API | `query`, `count`, `freshness` |
| `memory_search` | Search MEMORY.md and memory/*.md | `query` |
| `system_status` | Platform, Node version, memory, uptime | *(none)* |

## Installation

```bash
cd mcp-server
npm install
npm run build
```

## Usage

### As a CLI Tool

```bash
# Start the server (stdio transport)
npm start
```

### With Claude Desktop

Add to your Claude Desktop config file (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "openclaw": {
      "command": "node",
      "args": ["/path/to/mcp-server/dist/index.js"],
      "env": {
        "OPENCLAW_API_URL": "http://localhost:PORT"
      }
    }
  }
}
```

### With MCP Inspector

```bash
npx @modelcontextprotocol/inspector node dist/index.js
```

## Security

### Path Sandboxing

All file operations are sandboxed to the workspace root (`OPENCLAW_WORKSPACE` env or `cwd`). Path traversal attempts (e.g. `../../etc/passwd`) are rejected.

### Command Validation

`exec` blocks dangerous shell patterns including:
- `rm -rf /`, `dd if=`, `mkfs`, `format`
- `wget | sh`, `curl | sh` (remote execution)
- `chmod 777 /`, command injection patterns

### File Deletion

- Files: deleted immediately (irreversible)
- Directories: only deleted if empty

## Tool Schemas

All 16 tool schemas are defined in `src/tools.ts`. Key schemas:

### File Editing Triad

Three complementary file modification tools:
- **`write`** — Full file overwrite. Use for creating or replacing entire files.
- **`append`** — Add content to end of file. Use for logs, appending data.
- **`edit`** — Find & replace exact text. Use for surgical edits.

### Search & Discovery

- **`search_files`** — Regex content search across files (like `grep`). Supports glob include filter.
- **`find_files`** — Glob-based file name matching (like `find -name`). Uses Node.js 22+ `fs.glob`.
- **`memory_search`** — Keyword search in MEMORY.md and `memory/*.md` files.

### File Metadata

- **`file_info`** — Returns size, type, timestamps, permissions. Optionally computes SHA-256 hash.
- **`list_files`** — Directory listing with optional recursion and depth control.

## Development

```bash
# Watch mode for development
npm run dev

# Run tests
npm test

# Build for production
npm run build
```

## Testing

The project includes **526 tests** covering:

1. Tool listing and schema validation
2. Tool execution (file ops, search, exec)
3. Error handling and edge cases
4. Path sandboxing and command validation
5. Transport layer

Run tests with:
```bash
npm test
```

## Roadmap

- [x] ~~Add more OpenClaw tools~~ — 18 tools implemented (incl. head/tail)
- [x] ~~Streamable HTTP transport~~ — MVP complete
- [ ] Integrate web_search with real Brave API (currently mocked)
- [ ] Add authentication/authorization
- [ ] Add resource support (file system browsing)
- [ ] Add prompt templates
- [ ] Streaming responses for long-running exec

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

MIT

## References

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [MCP SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [Claude Desktop](https://claude.ai/download)
- [OpenClaw Documentation](../README.md)
