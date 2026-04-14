# OpenClaw MCP Server Architecture

## Overview

The OpenClaw MCP Server is a TypeScript/Node.js implementation of the Model Context Protocol (MCP) that exposes OpenClaw's core tools to AI agents in a standardized way.

## System Design

```
┌─────────────────────────────────────────────────────────────┐
│                     AI Agent / Client                        │
│                  (Claude, Inspector, etc.)                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          │ MCP Protocol (JSON-RPC 2.0)
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                 OpenClaw MCP Server                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           MCP Protocol Layer                         │  │
│  │  - Server (@modelcontextprotocol/sdk)               │  │
│  │  - Transport (StdioServerTransport)                  │  │
│  │  - Request Handlers                                  │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           Tool Mapping Layer                         │  │
│  │  - Tool Definitions (OPENCLAW_TOOLS)                │  │
│  │  - Schema Validation                                │  │
│  │  - Parameter Transformation                          │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           Tool Execution Layer                       │  │
│  │  - executeWebSearch()                                │  │
│  │  - executeRead()                                     │  │
│  │  - executeWrite()                                    │  │
│  │  - executeExec()                                     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          │ (Future: HTTP/gRPC)
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                 OpenClaw Core API                           │
│              (Gateway / Internal Services)                   │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. MCP Protocol Layer

**Location:** `src/index.ts` (lines 1-150)

**Responsibilities:**
- Initialize and configure MCP Server
- Handle stdio transport
- Register request handlers
- Manage server lifecycle

**Key Classes:**
- `Server` from `@modelcontextprotocol/sdk`
- `StdioServerTransport` for communication

**Request Handlers:**
- `ListToolsRequestSchema` - Returns available tools
- `CallToolRequestSchema` - Executes tool calls

### 2. Tool Mapping Layer

**Location:** `src/index.ts` (lines 26-130)

**Responsibilities:**
- Define tool schemas
- Map OpenClaw tools to MCP format
- Specify input/output schemas
- Document tool behavior

**Tool Definitions:**

```typescript
const OPENCLAW_TOOLS: Tool[] = [
  {
    name: "web_search",
    description: "...",
    inputSchema: {
      type: "object",
      properties: { ... },
      required: [ ... ]
    }
  },
  // ... more tools
]
```

**Schema Design:**
- Uses JSON Schema Draft 7
- Type-safe parameter definitions
- Clear documentation for each field
- Default values and constraints

### 3. Tool Execution Layer

**Location:** `src/index.ts` (lines 180-280)

**Responsibilities:**
- Execute tool logic
- Handle errors gracefully
- Transform responses to MCP format
- Integrate with OpenClaw API (future)

**Current State:**
- All tools return mock responses
- Ready for OpenClaw API integration
- Error handling framework in place

**Future Integration:**
```typescript
async function executeWebSearch(args: any): Promise<any> {
  // Call OpenClaw's internal API
  const response = await openclaw.api.call('web_search', args);
  return transformToMCPFormat(response);
}
```

## Data Flow

### Tool Listing Flow

```
Client                          MCP Server
  │                                │
  ├── ListTools ──────────────────>│
  │                                │
  │<─────────── Tool List ──────────│
  │  [web_search, read, ...]        │
```

### Tool Execution Flow

```
Client                          MCP Server                    OpenClaw API
  │                                │                              │
  ├── CallTool ──────────────────>│                              │
  │  {name: "web_search",          │                              │
  │   arguments: {query: "..."}}   │                              │
  │                                │                              │
  │                                ├── Validate Parameters        │
  │                                │                              │
  │                                ├── Execute Tool ─────────────>│
  │                                │                              │
  │                                │<────────── Result ────────────│
  │                                │                              │
  │<─────────── Tool Result ───────│                              │
  │  {content: [...]}               │                              │
```

## Error Handling Strategy

### Error Types

1. **Validation Errors**
   - Missing required parameters
   - Invalid parameter types
   - Out-of-range values

2. **Execution Errors**
   - File not found (ENOENT)
   - Permission denied (EACCES)
   - Command failures
   - Network errors

3. **System Errors**
   - Timeouts
   - Resource exhaustion
   - Protocol errors

### Error Response Format

```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"error\": \"Error message details\"}"
    }
  ],
  "isError": true
}
```

## Transport Layer

### Current: stdio

**Advantages:**
- Simple to implement
- Works with all MCP clients
- Low latency
- No networking overhead

**Implementation:**
```typescript
const transport = new StdioServerTransport();
await server.connect(transport);
```

### Future: HTTP (Planned)

**Advantages:**
- Remote access
- Better for web-based clients
- Easier debugging
- Support for websockets

**Design:**
```typescript
// Future implementation
const transport = new HTTPServerTransport({
  port: 3000,
  path: "/mcp"
});
```

## Testing Strategy

### Test Categories

1. **Unit Tests** (`tests/list-tools.test.js`)
   - Tool listing
   - Schema validation
   - Response structure

2. **Integration Tests** (`tests/execute-tools.test.js`)
   - Tool execution
   - Parameter handling
   - Result transformation

3. **Error Tests** (`tests/error-handling.test.js`)
   - Error scenarios
   - Edge cases
   - Concurrent requests

### Test Coverage

```
✓ 15/15 tests passing
  - Tool listing: 2 tests
  - Tool execution: 6 tests
  - Error handling: 7 tests
```

## Security Considerations

### Current (Placeholder)

- No authentication
- No authorization
- No rate limiting
- No input sanitization beyond schema validation

### Future Enhancements

1. **Authentication**
   - API key validation
   - JWT tokens
   - OAuth 2.0

2. **Authorization**
   - Tool-level permissions
   - Resource-based access control
   - Role-based access control (RBAC)

3. **Rate Limiting**
   - Per-tool limits
   - Per-client limits
   - Time-window based limits

4. **Input Sanitization**
   - Path traversal prevention
   - Command injection prevention
   - XSS prevention

## Performance Optimizations

### Current

- Minimal overhead (mock responses)
- Efficient JSON serialization
- No persistent state

### Future

1. **Caching**
   - Web search results
   - File content cache
   - Command output cache

2. **Batching**
   - Multiple tool calls in one request
   - Parallel execution
   - Result aggregation

3. **Streaming**
   - Large file streaming
   - Command output streaming
   - Search result streaming

## Extension Points

### Adding New Tools

1. Define tool schema in `OPENCLAW_TOOLS`
2. Create execution function
3. Add case in `CallToolRequestSchema` handler
4. Write tests

```typescript
// 1. Add to OPENCLAW_TOOLS
{
  name: "new_tool",
  description: "Tool description",
  inputSchema: { ... }
}

// 2. Create execution function
async function executeNewTool(args: any): Promise<any> {
  // Implementation
}

// 3. Add to handler
case "new_tool":
  result = await executeNewTool(args);
  break;

// 4. Write tests
// tests/new-tool.test.js
```

### Custom Transports

```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { CustomTransport } from "./custom-transport.js";

const transport = new CustomTransport({ /* config */ });
await server.connect(transport);
```

### Middleware

```typescript
// Future: Add middleware support
server.use(async (request, next) => {
  // Pre-processing
  console.log("Request:", request);

  const response = await next(request);

  // Post-processing
  console.log("Response:", response);

  return response;
});
```

## Monitoring and Observability

### Current

- Console.error for logging
- Error responses include details

### Future

1. **Metrics**
   - Request count
   - Error rate
   - Latency
   - Tool usage stats

2. **Logging**
   - Structured logging
   - Log levels
   - Request tracing

3. **Tracing**
   - Distributed tracing
   - Request IDs
   - Tool call chains

## Deployment

### Development

```bash
npm install
npm run dev  # Watch mode
npm test
```

### Production

```bash
npm run build
npm start
```

### Docker (Future)

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY dist ./dist
CMD ["node", "dist/index.js"]
```

## References

- [MCP Specification](https://modelcontextprotocol.io/)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [JSON Schema](https://json-schema.org/)
- [OpenClaw Documentation](../README.md)
