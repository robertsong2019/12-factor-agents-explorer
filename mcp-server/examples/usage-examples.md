# OpenClaw MCP Server Usage Examples

## Example 1: Using with Claude Desktop

1. Build the server:
```bash
cd mcp-server
npm install
npm run build
```

2. Update your Claude Desktop config:
```json
{
  "mcpServers": {
    "openclaw": {
      "command": "node",
      "args": ["/absolute/path/to/mcp-server/dist/index.js"]
    }
  }
}
```

3. Restart Claude Desktop

4. In Claude, ask:
```
Search the web for "OpenAI latest news" and show me the top 5 results
```

## Example 2: Testing with MCP Inspector

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Run the inspector
npx @modelcontextprotocol/inspector node dist/index.js

# In the inspector UI, try:
# 1. List tools
# 2. Call web_search with query="test"
# 3. Call read with path="/path/to/file.txt"
```

## Example 3: Programmatic Usage

```typescript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const transport = new StdioClientTransport({
  command: "node",
  args: ["./dist/index.js"],
});

const client = new Client({
  name: "test-client",
  version: "1.0.0",
}, {
  capabilities: {},
});

await client.connect(transport);

// List tools
const tools = await client.listTools();
console.log("Available tools:", tools);

// Call web_search
const searchResult = await client.callTool({
  name: "web_search",
  arguments: {
    query: "TypeScript MCP server",
    count: 5,
  },
});
console.log("Search results:", searchResult);

// Call read
const readResult = await client.callTool({
  name: "read",
  arguments: {
    path: "/path/to/file.txt",
  },
});
console.log("File content:", readResult);

// Call write
const writeResult = await client.callTool({
  name: "write",
  arguments: {
    path: "/path/to/output.txt",
    content: "Hello from MCP!",
  },
});
console.log("Write result:", writeResult);

// Call exec
const execResult = await client.callTool({
  name: "exec",
  arguments: {
    command: "ls -la",
  },
});
console.log("Exec result:", execResult);
```

## Example 4: AI Agent Integration

```typescript
// Example AI agent using OpenClaw MCP Server
class Agent {
  private mcpClient: Client;

  async initialize() {
    const transport = new StdioClientTransport({
      command: "node",
      args: ["./mcp-server/dist/index.js"],
    });

    this.mcpClient = new Client({
      name: "ai-agent",
      version: "1.0.0",
    }, { capabilities: {} });

    await this.mcpClient.connect(transport);
  }

  async searchWeb(query: string, count: number = 5) {
    const result = await this.mcpClient.callTool({
      name: "web_search",
      arguments: { query, count },
    });
    return JSON.parse(result.content[0].text);
  }

  async readFile(path: string) {
    const result = await this.mcpClient.callTool({
      name: "read",
      arguments: { path },
    });
    return JSON.parse(result.content[0].text);
  }

  async writeFile(path: string, content: string) {
    const result = await this.mcpClient.callTool({
      name: "write",
      arguments: { path, content },
    });
    return JSON.parse(result.content[0].text);
  }

  async executeCommand(command: string) {
    const result = await this.mcpClient.callTool({
      name: "exec",
      arguments: { command },
    });
    return JSON.parse(result.content[0].text);
  }
}

// Usage
const agent = new Agent();
await agent.initialize();

const searchResults = await agent.searchWeb("AI agents", 5);
console.log("Search results:", searchResults);

const fileContent = await agent.readFile("/tmp/test.txt");
console.log("File content:", fileContent);

await agent.writeFile("/tmp/output.txt", "Hello from agent!");
console.log("File written successfully");

const commandResult = await agent.executeCommand("echo 'Hello from MCP!'");
console.log("Command output:", commandResult);
```

## Example 5: Error Handling

```typescript
async function safeToolCall(client: Client, name: string, args: any) {
  try {
    const result = await client.callTool({ name, arguments: args });

    if (result.isError) {
      const error = JSON.parse(result.content[0].text);
      throw new Error(error.error || "Unknown error");
    }

    return JSON.parse(result.content[0].text);
  } catch (error) {
    console.error(`Tool ${name} failed:`, error);
    throw error;
  }
}

// Usage
try {
  const result = await safeToolCall(client, "web_search", {
    query: "test",
    count: 5,
  });
  console.log("Success:", result);
} catch (error) {
  console.error("Failed:", error);
}
```

## Example 6: Streaming Results (Future)

```typescript
// Future enhancement: Support for streaming results
const stream = await client.callTool({
  name: "exec",
  arguments: {
    command: "tail -f /var/log/app.log",
    background: true,
  },
});

// Process streaming output
for await (const chunk of stream) {
  console.log("Log output:", chunk);
}
```

## Example 7: Tool Composition

```typescript
// Combine multiple tools
async function analyzeFile(client: Client, filePath: string) {
  // 1. Read the file
  const fileData = await safeToolCall(client, "read", {
    path: filePath,
  });

  // 2. Search for related information
  const searchResults = await safeToolCall(client, "web_search", {
    query: `analysis of ${filePath}`,
    count: 3,
  });

  // 3. Execute analysis script
  const analysisResult = await safeToolCall(client, "exec", {
    command: `node analyze.js ${filePath}`,
  });

  // 4. Write report
  const report = `
    File Analysis Report
    ====================
    File: ${filePath}
    Content length: ${fileData.content?.length || 0}

    Related Information:
    ${searchResults.results?.map(r => `- ${r.title}: ${r.url}`).join('\n') || 'None'}

    Analysis Results:
    ${analysisResult.stdout || 'No output'}
  `;

  await safeToolCall(client, "write", {
    path: `${filePath}.analysis.md`,
    content: report,
  });

  return report;
}
```

## Tips and Best Practices

1. **Always handle errors**: MCP tools can fail, so always wrap calls in try-catch
2. **Validate parameters**: Check required parameters before calling tools
3. **Use timeouts**: Set appropriate timeouts for long-running operations
4. **Cache results**: Cache expensive operations like web searches
5. **Batch operations**: When possible, batch multiple operations together
6. **Log operations**: Log tool calls for debugging and auditing
7. **Rate limit**: Respect rate limits, especially for web_search
