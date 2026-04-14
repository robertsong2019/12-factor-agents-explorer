# OpenClaw MCP Server

Expose OpenClaw core tools via the Model Context Protocol (MCP).

## Overview

The OpenClaw MCP Server acts as a bridge between AI agents and OpenClaw's powerful toolset. It implements the [Model Context Protocol](https://modelcontextprotocol.io/), allowing any MCP-compatible client (Claude Desktop, MCP Inspector, etc.) to access OpenClaw tools in a standardized way.

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   AI Agent      │ ←──→ │  OpenClaw MCP    │ ←──→ │  OpenClaw Core  │
│  (MCP Client)   │      │     Server       │      |     Tools       │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                               │
                               ├── stdio (default)
                               └── HTTP (planned)
```

### Core Components

1. **MCP Server** (`src/index.ts`)
   - Implements MCP protocol using `@modelcontextprotocol/sdk`
   - Exposes OpenClaw tools as MCP tools
   - Handles tool listing and execution requests
   - Transforms MCP requests to OpenClaw API calls

2. **Tool Mapping Layer**
   - Maps OpenClaw tools to MCP tool definitions
   - Converts between MCP and OpenClaw schemas
   - Handles parameter validation and transformation

3. **OpenClaw Integration** (placeholder)
   - Connects to OpenClaw's internal API
   - Executes real tool operations
   - Returns formatted results to MCP clients

## Supported Tools

Currently supports these core OpenClaw tools:

| Tool | Description | Status |
|------|-------------|--------|
| `web_search` | Search the web using Brave Search API | ✅ Mocked |
| `read` | Read file contents (text and images) | ✅ Mocked |
| `write` | Write content to files | ✅ Mocked |
| `exec` | Execute shell commands | ✅ Mocked |

*Note: Tools are currently mocked. Integration with OpenClaw's real API is planned.*

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

## Tool Schemas

### web_search

```json
{
  "name": "web_search",
  "description": "Search the web using Brave Search API",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": { "type": "string" },
      "count": { "type": "number", "default": 5, "minimum": 1, "maximum": 10 },
      "country": { "type": "string", "default": "US" },
      "language": { "type": "string" },
      "freshness": { "type": "string", "enum": ["day", "week", "month", "year"] }
    },
    "required": ["query"]
  }
}
```

### read

```json
{
  "name": "read",
  "description": "Read file contents",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": { "type": "string" },
      "offset": { "type": "number" },
      "limit": { "type": "number" }
    },
    "required": ["path"]
  }
}
```

### write

```json
{
  "name": "write",
  "description": "Write content to a file",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": { "type": "string" },
      "content": { "type": "string" }
    },
    "required": ["path", "content"]
  }
}
```

### exec

```json
{
  "name": "exec",
  "description": "Execute shell commands",
  "inputSchema": {
    "type": "object",
    "properties": {
      "command": { "type": "string" },
      "workdir": { "type": "string" },
      "env": { "type": "object" },
      "yieldMs": { "type": "number" },
      "background": { "type": "boolean" },
      "timeout": { "type": "number" },
      "pty": { "type": "boolean" }
    },
    "required": ["command"]
  }
}
```

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

The project includes tests for:

1. Tool listing
2. Tool execution
3. Error handling
4. Schema validation

Run tests with:
```bash
npm test
```

## Roadmap

- [ ] Integrate with real OpenClaw API
- [ ] Add more OpenClaw tools (feishu_doc, feishu_bitable, etc.)
- [ ] Support HTTP transport
- [ ] Add authentication/authorization
- [ ] Implement tool capabilities (progress, streaming)
- [ ] Add resource support (for file system, etc.)
- [ ] Add prompt templates
- [ ] Performance optimizations

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

MIT

## References

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [MCP SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [Claude Desktop](https://claude.ai/download)
- [OpenClaw Documentation](../README.md)
