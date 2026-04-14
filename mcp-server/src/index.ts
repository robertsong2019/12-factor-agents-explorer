#!/usr/bin/env node

/**
 * OpenClaw MCP Server
 * Exposes OpenClaw core tools via Model Context Protocol (MCP)
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { exec as execCb } from "node:child_process";
import { promisify } from "node:util";

const execAsync = promisify(execCb);

// Workspace root for sandboxing file operations
const WORKSPACE_ROOT = process.env.OPENCLAW_WORKSPACE || process.cwd();

// Define OpenClaw tool mappings
const OPENCLAW_TOOLS: Tool[] = [
  {
    name: "web_search",
    description: "Search the web using Brave Search API. Returns titles, URLs, and snippets for fast research.",
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "Search query string",
        },
        count: {
          type: "number",
          description: "Number of results to return (1-10)",
          default: 5,
          minimum: 1,
          maximum: 10,
        },
        country: {
          type: "string",
          description: "2-letter country code for region-specific results (e.g., 'DE', 'US', 'ALL')",
          default: "US",
        },
        language: {
          type: "string",
          description: "ISO 639-1 language code for results (e.g., 'en', 'de', 'fr')",
        },
        freshness: {
          type: "string",
          description: "Filter by time: 'day' (24h), 'week', 'month', or 'year'",
          enum: ["day", "week", "month", "year"],
        },
      },
      required: ["query"],
    },
  },
  {
    name: "read",
    description: "Read the contents of a file. Supports text files and images (jpg, png, gif, webp).",
    inputSchema: {
      type: "object",
      properties: {
        path: {
          type: "string",
          description: "Path to the file to read (relative or absolute)",
        },
        offset: {
          type: "number",
          description: "Line number to start reading from (1-indexed)",
        },
        limit: {
          type: "number",
          description: "Maximum number of lines to read",
        },
      },
      required: ["path"],
    },
  },
  {
    name: "write",
    description: "Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
    inputSchema: {
      type: "object",
      properties: {
        path: {
          type: "string",
          description: "Path to the file to write (relative or absolute)",
        },
        content: {
          type: "string",
          description: "Content to write to the file",
        },
      },
      required: ["path", "content"],
    },
  },
  {
    name: "exec",
    description: "Execute shell commands with background continuation. Use yieldMs/background to continue later via process tool.",
    inputSchema: {
      type: "object",
      properties: {
        command: {
          type: "string",
          description: "Shell command to execute",
        },
        workdir: {
          type: "string",
          description: "Working directory (defaults to cwd)",
        },
        env: {
          type: "object",
          description: "Environment variables (key-value pairs)",
        },
        yieldMs: {
          type: "number",
          description: "Milliseconds to wait before backgrounding (default 10000)",
        },
        background: {
          type: "boolean",
          description: "Run in background immediately",
        },
        timeout: {
          type: "number",
          description: "Timeout in seconds (optional, kills process on expiry)",
        },
        pty: {
          type: "boolean",
          description: "Run in a pseudo-terminal (PTY) when available (TTY-required CLIs)",
        },
      },
      required: ["command"],
    },
  },
];

// Create MCP server instance
const server = new Server(
  {
    name: "openclaw-mcp-server",
    version: "0.1.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Handle tool listing
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: OPENCLAW_TOOLS,
  };
});

// Handle tool execution
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    let result: any;

    switch (name) {
      case "web_search":
        result = await executeWebSearch(args);
        break;

      case "read":
        result = await executeRead(args);
        break;

      case "write":
        result = await executeWrite(args);
        break;

      case "exec":
        result = await executeExec(args);
        break;

      default:
        throw new Error(`Unknown tool: ${name}`);
    }

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({ error: errorMessage }, null, 2),
        },
      ],
      isError: true,
    };
  }
});

// Web search implementation (placeholder - connects to OpenClaw)
async function executeWebSearch(args: any): Promise<any> {
  const { query } = args;
  // TODO: Integrate with OpenClaw API / Brave Search
  return {
    tool: "web_search",
    query,
    results: [],
    note: "Web search requires OpenClaw API integration.",
  };
}

// Resolve and sandbox a path to WORKSPACE_ROOT
function safePath(inputPath: string): string {
  const resolved = resolve(WORKSPACE_ROOT, inputPath);
  if (!resolved.startsWith(WORKSPACE_ROOT)) {
    throw new Error(`Path traversal denied: ${inputPath}`);
  }
  return resolved;
}

// Read file implementation — real filesystem
async function executeRead(args: any): Promise<any> {
  const { path, offset, limit } = args;
  const resolved = safePath(path);
  const content = await readFile(resolved, "utf-8");

  let lines = content.split("\n");
  const startLine = offset ? Math.max(1, offset) - 1 : 0;
  const endLine = limit ? startLine + limit : lines.length;
  const selected = lines.slice(startLine, endLine).join("\n");

  return {
    tool: "read",
    path,
    lines: selected.split("\n").length,
    content: selected,
  };
}

// Write file implementation — real filesystem
async function executeWrite(args: any): Promise<any> {
  const { path, content } = args;
  const resolved = safePath(path);
  await mkdir(dirname(resolved), { recursive: true });
  await writeFile(resolved, content, "utf-8");
  return {
    tool: "write",
    path,
    success: true,
    bytesWritten: Buffer.byteLength(content, "utf-8"),
  };
}

// Exec command implementation — real shell execution
async function executeExec(args: any): Promise<any> {
  const { command, workdir, timeout = 30 } = args;
  const options: any = {
    cwd: workdir || WORKSPACE_ROOT,
    timeout: timeout * 1000,
    maxBuffer: 1024 * 1024,
  };
  try {
    const { stdout, stderr } = await execAsync(command, options);
    return {
      tool: "exec",
      command,
      exitCode: 0,
      stdout,
      stderr,
    };
  } catch (err: any) {
    return {
      tool: "exec",
      command,
      exitCode: err.code ?? 1,
      stdout: err.stdout ?? "",
      stderr: err.stderr ?? err.message,
    };
  }
}

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("OpenClaw MCP Server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error in main():", error);
  process.exit(1);
});
