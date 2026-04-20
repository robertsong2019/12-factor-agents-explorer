#!/usr/bin/env node

/**
 * OpenClaw MCP Server
 * Exposes OpenClaw core tools via Model Context Protocol (MCP)
 *
 * Transport modes:
 *   stdio  - Default. Communicates via stdin/stdout (for CLI integration)
 *   http   - Streamable HTTP on configurable port (for remote/web clients)
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { createMcpExpressApp } from "@modelcontextprotocol/sdk/server/express.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { createServer } from "node:http";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { OPENCLAW_TOOLS, toolHandlers } from "./tools.js";

export function createServerInstance(): Server {
  const server = new Server(
    { name: "openclaw-mcp-server", version: "0.2.0" },
    { capabilities: { tools: {} } }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: OPENCLAW_TOOLS }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    try {
      const handler = toolHandlers[name];
      if (!handler) throw new Error(`Unknown tool: ${name}`);
      const result = await handler(args);
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: JSON.stringify({ error: errorMessage }, null, 2) }], isError: true };
    }
  });

  return server;
}

export function parseArgs(argv: string[]): { transport: "stdio" | "http"; port: number; host: string } {
  const args = argv.slice(2);
  let transport: "stdio" | "http" = "stdio";
  let port = 3000;
  let host = "127.0.0.1";

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--transport" && args[i + 1]) {
      transport = args[i + 1] === "http" ? "http" : "stdio";
      i++;
    } else if (args[i] === "--port" && args[i + 1]) {
      port = parseInt(args[i + 1], 10) || 3000;
      i++;
    } else if (args[i] === "--host" && args[i + 1]) {
      host = args[i + 1];
      i++;
    } else if (args[i] === "--http") {
      transport = "http";
    }
  }

  return { transport, port, host };
}

async function main() {
  const { transport, port, host } = parseArgs(process.argv);

  if (transport === "http") {
    await startHttpServer(port, host);
  } else {
    await startStdioServer();
  }
}

async function startStdioServer() {
  const server = createServerInstance();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("OpenClaw MCP Server running on stdio");
}

async function startHttpServer(port: number, host: string) {
  const mcpServer = createServerInstance();
  const httpTransport = new StreamableHTTPServerTransport({
    sessionIdGenerator: () => randomUUID(),
  });

  const app = createMcpExpressApp({ host });
  app.post("/mcp", (req: any, res: any) => httpTransport.handleRequest(req, res, req.body));
  app.get("/mcp", (req: any, res: any) => httpTransport.handleRequest(req, res));
  app.delete("/mcp", (req: any, res: any) => httpTransport.handleRequest(req, res));

  await mcpServer.connect(httpTransport);

  const httpServer = createServer(app);
  httpServer.listen(port, host, () => {
    console.error(`OpenClaw MCP Server running on http://${host}:${port}/mcp`);
  });
}

// Only run main when executed directly (not imported)
const isMainModule = process.argv[1] && fileURLToPath(new URL(import.meta.url)).startsWith(process.argv[1]);
if (isMainModule) {
  main().catch((error) => {
    console.error("Fatal error in main():", error);
    process.exit(1);
  });
}
