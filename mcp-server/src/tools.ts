/**
 * Tool definitions and handlers for OpenClaw MCP Server
 */

import { Tool } from "@modelcontextprotocol/sdk/types.js";
import { readFile, writeFile, mkdir, readdir, stat, unlink, rmdir, rename, cp } from "node:fs/promises";
import { dirname, resolve, join } from "node:path";
import { exec as execCb } from "node:child_process";
import { promisify } from "node:util";

const execAsync = promisify(execCb);

// Workspace root for sandboxing file operations
let _workspaceRoot = process.env.OPENCLAW_WORKSPACE || process.cwd();
export const WORKSPACE_ROOT = _workspaceRoot;
export function setWorkspaceRoot(path: string) { _workspaceRoot = path; }

function getWorkspaceRoot() { return _workspaceRoot; }

// Dangerous command patterns to block
const DANGEROUS_COMMANDS: RegExp[] = [
  new RegExp("rm\\s+-rf\\s*\\/", "i"),          // rm -rf /
  new RegExp("rm\\s+-rf\\s+\\.\\.", "i"),        // rm -rf ../
  new RegExp("dd\\s+if=", "i"),                 // dd (disk destruction)
  new RegExp("mkfs", "i"),                      // filesystem formatting
  new RegExp(":>.*\\/", "i"),                   // emptying files directly
  new RegExp("format\\s+[a-z]:", "i"),          // Windows format
  new RegExp("del\\s+\\/[sfq]\\s+\\*", "i"),    // Windows del
  new RegExp("chmod\\s+777\\s+\\/", "i"),       // chmod 777 /
  new RegExp("chown\\s+.*:\\*\\s+\\/", "i"),    // chown to root
  new RegExp("wget.*\\|\\s*sh", "i"),           // wget | sh (remote execution)
  new RegExp("curl.*\\|\\s*sh", "i"),           // curl | sh
  new RegExp("eval\\s*\\$\\(.*\\)", "i"),       // command injection
  new RegExp(">\\s*\\/dev\\/.*[a-z]d[a-z]", "i"), // writing to device files
];

// Validate exec command for dangerous patterns
export function validateExecCommand(command: string): { valid: boolean; reason?: string } {
  for (const pattern of DANGEROUS_COMMANDS) {
    if (pattern.test(command)) {
      return { valid: false, reason: "Command contains dangerous pattern" };
    }
  }
  return { valid: true };
}

// Resolve and sandbox a path to WORKSPACE_ROOT
export function safePath(inputPath: string): string {
  const root = getWorkspaceRoot();
  const resolved = resolve(root, inputPath);
  if (!resolved.startsWith(root)) {
    throw new Error(`Path traversal denied: ${inputPath}`);
  }
  return resolved;
}

// Tool definitions
export const OPENCLAW_TOOLS: Tool[] = [
  {
    name: "web_search",
    description: "Search the web using Brave Search API. Returns titles, URLs, and snippets for fast research.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query string" },
        count: { type: "number", description: "Number of results to return (1-10)", default: 5, minimum: 1, maximum: 10 },
        country: { type: "string", description: "2-letter country code for region-specific results", default: "US" },
        language: { type: "string", description: "ISO 639-1 language code for results" },
        freshness: { type: "string", description: "Filter by time: 'day', 'week', 'month', or 'year'", enum: ["day", "week", "month", "year"] },
      },
      required: ["query"],
    },
  },
  {
    name: "list_files",
    description: "List files in a directory within the workspace. Returns file names, sizes, and types.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Directory path relative to workspace root", default: "." },
        recursive: { type: "boolean", description: "Recursively list all files in subdirectories", default: false },
      },
    },
  },
  {
    name: "read",
    description: "Read the contents of a file. Supports text files and images.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file to read" },
        offset: { type: "number", description: "Line number to start reading from (1-indexed)" },
        limit: { type: "number", description: "Maximum number of lines to read" },
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
        path: { type: "string", description: "Path to the file to write" },
        content: { type: "string", description: "Content to write to the file" },
      },
      required: ["path", "content"],
    },
  },
  {
    name: "exec",
    description: "Execute shell commands with background continuation.",
    inputSchema: {
      type: "object",
      properties: {
        command: { type: "string", description: "Shell command to execute" },
        workdir: { type: "string", description: "Working directory" },
        env: { type: "object", description: "Environment variables" },
        yieldMs: { type: "number", description: "Milliseconds to wait before backgrounding" },
        background: { type: "boolean", description: "Run in background immediately" },
        timeout: { type: "number", description: "Timeout in seconds" },
        pty: { type: "boolean", description: "Run in a pseudo-terminal" },
      },
      required: ["command"],
    },
  },
  {
    name: "memory_search",
    description: "Search MEMORY.md and memory/*.md files for keywords. Returns matching file paths and line excerpts.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Keyword or phrase to search for" },
      },
      required: ["query"],
    },
  },
  {
    name: "edit",
    description: "Edit a file by replacing exact text. Replaces all occurrences.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file to edit" },
        oldText: { type: "string", description: "Exact text to find and replace (must match exactly)" },
        newText: { type: "string", description: "New text to replace the old text with" },
      },
      required: ["path", "oldText", "newText"],
    },
  },
  {
    name: "append",
    description: "Append content to an existing file. Creates the file if it doesn't exist.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file to append to" },
        content: { type: "string", description: "Content to append" },
        newline: { type: "boolean", description: "Prepend a newline before content if file is non-empty", default: true },
      },
      required: ["path", "content"],
    },
  },
  {
    name: "search_files",
    description: "Search file contents by regex pattern across the workspace. Returns matching files, lines, and line numbers.",
    inputSchema: {
      type: "object",
      properties: {
        pattern: { type: "string", description: "Regex pattern to search for" },
        path: { type: "string", description: "Directory path relative to workspace root", default: "." },
        include: { type: "string", description: "Glob pattern for file names to include (e.g. '*.ts')", default: "*" },
        maxResults: { type: "number", description: "Maximum number of matches to return", default: 50, minimum: 1, maximum: 200 },
      },
      required: ["pattern"],
    },
  },
  {
    name: "delete",
    description: "Delete a file within the workspace. Directories are only deleted if empty. This operation is irreversible.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file or empty directory to delete" },
      },
      required: ["path"],
    },
  },
  {
    name: "move",
    description: "Move or rename a file or directory within the workspace.",
    inputSchema: {
      type: "object",
      properties: {
        source: { type: "string", "description": "Source path relative to workspace root" },
        destination: { type: "string", "description": "Destination path relative to workspace root" },
      },
      required: ["source", "destination"],
    },
  },
  {
    name: "copy",
    description: "Copy a file or directory within the workspace.",
    inputSchema: {
      type: "object",
      properties: {
        source: { type: "string", description: "Source path relative to workspace root" },
        destination: { type: "string", description: "Destination path relative to workspace root" },
      },
      required: ["source", "destination"],
    },
  },
  {
    name: "create_directory",
    description: "Create a directory and any necessary parent directories within the workspace.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Directory path relative to workspace root" },
      },
      required: ["path"],
    },
  },
  {
    name: "system_status",
    description: "Get system status information: platform, Node.js version, uptime, memory usage, workspace info.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "file_info",
    description: "Get detailed metadata for a file or directory: size, type, timestamps, permissions.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file or directory" },
      },
      required: ["path"],
    },
  },
];

// Handler map — name → async function
export const toolHandlers: Record<string, (args: any) => Promise<any>> = {
  web_search: executeWebSearch,
  list_files: executeListFiles,
  read: executeRead,
  write: executeWrite,
  exec: executeExec,
  append: executeAppend,
  memory_search: executeMemorySearch,
  edit: executeEdit,
  search_files: executeSearchFiles,
  delete: executeDelete,
  move: executeMove,
  copy: executeCopy,
  create_directory: executeCreateDirectory,
  system_status: executeSystemStatus,
  file_info: executeFileInfo,
};

// --- Handler implementations ---

async function executeWebSearch(args: any): Promise<any> {
  return { tool: "web_search", query: args.query, results: [], note: "Web search requires OpenClaw API integration." };
}

async function executeRead(args: any): Promise<any> {
  const { path, offset, limit } = args;
  const resolved = safePath(path);
  const content = await readFile(resolved, "utf-8");
  const lines = content.split("\n");
  const startLine = offset ? Math.max(1, offset) - 1 : 0;
  const endLine = limit ? startLine + limit : lines.length;
  const selected = lines.slice(startLine, endLine).join("\n");
  return { tool: "read", path, lines: selected.split("\n").length, content: selected };
}

async function executeWrite(args: any): Promise<any> {
  const { path, content } = args;
  const resolved = safePath(path);
  await mkdir(dirname(resolved), { recursive: true });
  await writeFile(resolved, content, "utf-8");
  return { tool: "write", path, success: true, bytesWritten: Buffer.byteLength(content, "utf-8") };
}

async function executeAppend(args: any): Promise<any> {
  const { path, content, newline = true } = args;
  const resolved = safePath(path);
  await mkdir(dirname(resolved), { recursive: true });
  let existing = "";
  try {
    existing = await readFile(resolved, "utf-8");
  } catch { /* file doesn't exist yet */ }
  const separator = existing && newline ? "\n" : "";
  const newContent = existing + separator + content;
  await writeFile(resolved, newContent, "utf-8");
  return {
    tool: "append",
    path,
    success: true,
    bytesWritten: Buffer.byteLength(content, "utf-8"),
    totalSize: Buffer.byteLength(newContent, "utf-8"),
  };
}

async function executeExec(args: any): Promise<any> {
  const { command, workdir, timeout = 30 } = args;

  // Validate command for dangerous patterns
  const validation = validateExecCommand(command);
  if (!validation.valid) {
    return {
      tool: "exec",
      command,
      exitCode: -1,
      stdout: "",
      stderr: `Command rejected: ${validation.reason}`,
      error: "Command validation failed",
    };
  }

  const options: any = { cwd: workdir || getWorkspaceRoot(), timeout: timeout * 1000, maxBuffer: 1024 * 1024 };
  try {
    const { stdout, stderr } = await execAsync(command, options);
    return { tool: "exec", command, exitCode: 0, stdout, stderr };
  } catch (err: any) {
    return { tool: "exec", command, exitCode: err.code ?? 1, stdout: err.stdout ?? "", stderr: err.stderr ?? err.message };
  }
}

async function executeListFiles(args: any): Promise<any> {
  const { path: inputPath = ".", recursive = false } = args;
  const resolved = safePath(inputPath);
  const entries = await readdir(resolved, { recursive, withFileTypes: true });
  const files = await Promise.all(
    entries.map(async (entry) => {
      const fullPath = join(resolved, entry.name);
      const relativePath = fullPath.slice(getWorkspaceRoot().length + 1);
      try {
        const s = await stat(fullPath);
        return { name: entry.name, path: relativePath, type: entry.isDirectory() ? "directory" : "file", size: s.size };
      } catch {
        return { name: entry.name, path: relativePath, type: "file", size: 0 };
      }
    })
  );
  return { tool: "list_files", path: inputPath, count: files.length, files };
}

async function executeMemorySearch(args: any): Promise<any> {
  const { query } = args;
  const keyword = query.toLowerCase();
  const results: Array<{ file: string; matches: Array<{ line: number; text: string }> }> = [];

  const searchFile = async (filePath: string, displayName: string) => {
    try {
      const content = await readFile(filePath, "utf-8");
      const lines = content.split("\n");
      const matches = lines
        .map((line, i) => ({ line: i + 1, text: line }))
        .filter((m) => m.text.toLowerCase().includes(keyword));
      if (matches.length > 0) results.push({ file: displayName, matches });
    } catch { /* skip */ }
  };

  await searchFile(join(getWorkspaceRoot(), "MEMORY.md"), "MEMORY.md");

  try {
    const memDir = join(getWorkspaceRoot(), "memory");
    const entries = await readdir(memDir);
    for (const entry of entries) {
      if (entry.endsWith(".md")) await searchFile(join(memDir, entry), `memory/${entry}`);
    }
  } catch { /* skip */ }

  return {
    tool: "memory_search",
    query,
    totalMatches: results.reduce((sum, r) => sum + r.matches.length, 0),
    results,
  };
}

async function executeEdit(args: any): Promise<any> {
  const { path, oldText, newText } = args;
  const resolved = safePath(path);
  const content = await readFile(resolved, "utf-8");

  if (!content.includes(oldText)) {
    return { tool: "edit", path, success: false, error: "oldText not found in file" };
  }

  const newContent = content.replaceAll(oldText, newText);
  await writeFile(resolved, newContent, "utf-8");

  return {
    tool: "edit",
    path,
    success: true,
    replacements: (content.match(new RegExp(oldText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), "g")) || []).length,
    bytesChanged: Buffer.byteLength(newContent, "utf-8") - Buffer.byteLength(content, "utf-8"),
  };
}

async function executeSearchFiles(args: any): Promise<any> {
  const { pattern, path: inputPath = ".", include = "*", maxResults = 50 } = args;
  const resolved = safePath(inputPath);
  let regex: RegExp;
  try {
    regex = new RegExp(pattern, "i");
  } catch {
    return { tool: "search_files", pattern, success: false, error: "Invalid regex pattern" };
  }

  const globRegex = globToRegex(include);
  const results: Array<{ file: string; matches: Array<{ line: number; text: string }> }> = [];
  let totalMatches = 0;

  async function walk(dir: string, relPrefix: string): Promise<void> {
    if (totalMatches >= maxResults) return;
    const entries = await readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (totalMatches >= maxResults) return;
      if (entry.name.startsWith(".") || entry.name === "node_modules") continue;
      const fullPath = join(dir, entry.name);
      const rel = relPrefix ? `${relPrefix}/${entry.name}` : entry.name;
      if (entry.isDirectory()) {
        await walk(fullPath, rel);
      } else if (globRegex.test(entry.name)) {
        try {
          const content = await readFile(fullPath, "utf-8");
          const lines = content.split("\n");
          const matches: Array<{ line: number; text: string }> = [];
          for (let i = 0; i < lines.length && totalMatches + matches.length < maxResults; i++) {
            if (regex.test(lines[i])) {
              matches.push({ line: i + 1, text: lines[i] });
            }
          }
          if (matches.length > 0) {
            results.push({ file: rel, matches });
            totalMatches += matches.length;
          }
        } catch { /* skip unreadable files */ }
      }
    }
  }

  await walk(resolved, "");
  return { tool: "search_files", pattern, path: inputPath, totalMatches, files: results.length, results };
}

function globToRegex(glob: string): RegExp {
  const escaped = glob.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".");
  return new RegExp(`^${escaped}$`, "i");
}

async function executeDelete(args: any): Promise<any> {
  const { path } = args;
  const resolved = safePath(path);
  let s;
  try {
    s = await stat(resolved);
  } catch {
    return { tool: "delete", path, success: false, error: "File not found" };
  }
  if (s.isDirectory()) {
    try {
      await rmdir(resolved);
    } catch {
      return { tool: "delete", path, success: false, error: "Directory not empty, cannot delete" };
    }
  } else {
    await unlink(resolved);
  }
  return { tool: "delete", path, success: true };
}

async function executeMove(args: any): Promise<any> {
  const { source, destination } = args;
  const srcResolved = safePath(source);
  const dstResolved = safePath(destination);

  try {
    await stat(srcResolved);
  } catch {
    return { tool: "move", success: false, error: "Source not found" };
  }

  await mkdir(dirname(dstResolved), { recursive: true });

  try {
    await rename(srcResolved, dstResolved);
  } catch (err: any) {
    return { tool: "move", success: false, error: err.message };
  }

  return { tool: "move", source, destination, success: true };
}

async function executeCopy(args: any): Promise<any> {
  const { source, destination } = args;
  const srcResolved = safePath(source);
  const dstResolved = safePath(destination);

  try {
    await stat(srcResolved);
  } catch {
    return { tool: "copy", success: false, error: "Source not found" };
  }

  await mkdir(dirname(dstResolved), { recursive: true });

  try {
    // Node 18.7+ cp supports recursive directory copy
    await cp(srcResolved, dstResolved, { recursive: true });
  } catch (err: any) {
    return { tool: "copy", success: false, error: err.message };
  }

  return { tool: "copy", source, destination, success: true };
}

async function executeCreateDirectory(args: any): Promise<any> {
  const { path } = args;
  const resolved = safePath(path);

  // Check if already exists
  let existed = false;
  try {
    const s = await stat(resolved);
    if (s.isDirectory()) {
      existed = true;
    } else {
      return { tool: "create_directory", path, success: false, error: "A file with this name already exists" };
    }
  } catch { /* doesn't exist, good */ }

  await mkdir(resolved, { recursive: true });
  return { tool: "create_directory", path, success: true, created: !existed };
}

async function executeFileInfo(args: any): Promise<any> {
  const { path } = args;
  const resolved = safePath(path);
  let s;
  try {
    s = await stat(resolved);
  } catch {
    return { tool: "file_info", path, success: false, error: "File not found" };
  }
  return {
    tool: "file_info",
    path,
    success: true,
    type: s.isDirectory() ? "directory" : s.isFile() ? "file" : "other",
    size: s.size,
    sizeHuman: s.size < 1024 ? `${s.size}B` : s.size < 1024 * 1024 ? `${(s.size / 1024).toFixed(1)}KB` : `${(s.size / 1024 / 1024).toFixed(1)}MB`,
    created: s.birthtime.toISOString(),
    modified: s.mtime.toISOString(),
    accessed: s.atime.toISOString(),
    permissions: s.mode.toString(8).slice(-3),
  };
}

async function executeSystemStatus(): Promise<any> {
  const memUsage = process.memoryUsage();
  return {
    tool: "system_status",
    platform: process.platform,
    arch: process.arch,
    nodeVersion: process.version,
    pid: process.pid,
    uptime: Math.round(process.uptime()),
    memory: {
      rss: `${Math.round(memUsage.rss / 1024 / 1024)}MB`,
      heapUsed: `${Math.round(memUsage.heapUsed / 1024 / 1024)}MB`,
      heapTotal: `${Math.round(memUsage.heapTotal / 1024 / 1024)}MB`,
    },
    workspace: getWorkspaceRoot(),
  };
}
