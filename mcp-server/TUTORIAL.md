# MCP Server 教程 🔌

> 从零开始，学会用 OpenClaw MCP Server 连接 AI Agent 和 OpenClaw 工具

## 目录

1. [理解 MCP 协议](#1-理解-mcp-协议)
2. [构建并运行 Server](#2-构建并运行-server)
3. [连接 Claude Desktop](#3-连接-claude-desktop)
4. [用 MCP Inspector 调试](#4-用-mcp-inspector-调试)
5. [工具调用详解](#5-工具调用详解)
6. [扩展：添加新工具](#6-扩展添加新工具)
7. [常见问题](#7-常见问题)

---

## 1. 理解 MCP 协议

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 是一个标准化协议，让 AI 应用能以统一方式调用外部工具。

```
┌──────────────┐    MCP Protocol    ┌──────────────┐
│  AI Client   │ ◄──────────────► │  MCP Server   │
│ (Claude etc) │   JSON-RPC/stdio │ (OpenClaw)    │
└──────────────┘                   └──────────────┘
```

**核心概念：**

- **Tool** — 一个可调用的函数（如 `read_file`, `exec_command`）
- **Resource** — 可读取的数据源（未来支持）
- **Prompt** — 预定义的提示模板（未来支持）

OpenClaw MCP Server 把 OpenClaw 的核心能力（文件操作、命令执行、网页搜索）暴露为 MCP 工具，任何 MCP 客户端都可以使用。

---

## 2. 构建并运行 Server

### 安装依赖

```bash
cd mcp-server
npm install
```

### 构建

```bash
npm run build
```

### 启动

```bash
npm start
```

Server 以 stdio 模式启动，等待 MCP 客户端连接。它不会自己输出任何内容 — 所有通信通过 stdin/stdout 的 JSON-RPC 消息进行。

### 验证安装

```bash
# 用 echo 手动发送一个 MCP 请求
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | node dist/index.js
```

你应该收到一个 JSON 响应，包含 server info 和 capabilities。

---

## 3. 连接 Claude Desktop

### 配置

编辑 Claude Desktop 配置文件：

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

添加：

```json
{
  "mcpServers": {
    "openclaw": {
      "command": "node",
      "args": ["/absolute/path/to/mcp-server/dist/index.js"],
      "env": {
        "OPENCLAW_API_URL": "http://localhost:3000"
      }
    }
  }
}
```

> ⚠️ `args` 必须用绝对路径。

### 验证连接

1. 重启 Claude Desktop
2. 在对话中输入：`你有哪些工具？`
3. Claude 应该会列出 `web_search`, `read`, `write`, `exec` 等工具

### 使用示例

在 Claude Desktop 中：

```
请搜索 "Model Context Protocol" 并总结前 3 条结果
```

Claude 会自动调用 `web_search` 工具，将结果返回给你。

---

## 4. 用 MCP Inspector 调试

MCP Inspector 是官方调试工具，可以可视化地测试 MCP 工具：

```bash
npx @modelcontextprotocol/inspector node dist/index.js
```

Inspector 会打开一个 Web UI（默认 http://localhost:6274），你可以：

1. **查看工具列表** — 看到所有已注册的工具和参数 schema
2. **手动调用工具** — 填写参数，看返回结果
3. **查看通信日志** — 每个 JSON-RPC 请求和响应

这对开发新工具特别有用。

---

## 5. 工具调用详解

### web_search — 网页搜索

```json
// 调用
{
  "query": "OpenClaw AI agent framework",
  "count": 5,
  "freshness": "week"
}

// 返回
{
  "results": [
    {
      "title": "OpenClaw GitHub",
      "url": "https://github.com/...",
      "description": "..."
    }
  ]
}
```

**参数：**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `query` | string | ✅ | — | 搜索关键词 |
| `count` | number | ❌ | 5 | 结果数量 (1-10) |
| `country` | string | ❌ | "US" | 国家代码 |
| `language` | string | ❌ | — | 语言代码 |
| `freshness` | string | ❌ | — | 时间范围: day/week/month/year |

### read — 读取文件

```json
// 调用
{
  "path": "/path/to/file.py",
  "offset": 1,
  "limit": 50
}

// 返回文件内容（文本）
```

### write — 写入文件

```json
// 调用
{
  "path": "/path/to/output.txt",
  "content": "Hello, MCP!"
}

// 返回确认信息
```

### head — 读取文件前 N 行

```json
// 调用
{ "path": "/var/log/app.log", "lines": 20 }

// 返回
{
  "tool": "head",
  "path": "/var/log/app.log",
  "requestedLines": 20,
  "totalLines": 1542,
  "returnedLines": 20,
  "content": "..." // 前 20 行
}
```

适合快速预览大文件，无需加载全部内容。

### tail — 读取文件后 N 行

```json
// 调用
{ "path": "/var/log/app.log", "lines": 50 }

// 返回
{
  "tool": "tail",
  "path": "/var/log/app.log",
  "requestedLines": 50,
  "totalLines": 1542,
  "returnedLines": 50,
  "content": "..." // 后 50 行
}
```

适合查看日志末尾、检查最新输出。

### exec — 执行命令

```json
// 调用
{
  "command": "git status",
  "workdir": "/path/to/project",
  "timeout": 30
}

// 返回命令输出
```

---

## 6. 扩展：添加新工具

### 步骤

1. 在 `src/index.ts` 中定义工具 schema
2. 在 `handleToolCall` 中添加执行逻辑

### 示例：添加一个 `list_files` 工具

```typescript
// 1. 在 setupServer 中注册工具
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    // ... 现有工具
    {
      name: "list_files",
      description: "列出目录中的文件和文件夹",
      inputSchema: {
        type: "object",
        properties: {
          path: { type: "string", description: "目录路径" },
          recursive: { type: "boolean", default: false }
        },
        required: ["path"]
      }
    }
  ]
}));

// 2. 在 handleToolCall 中处理
async function handleToolCall(name: string, args: any) {
  switch (name) {
    // ... 现有 case
    case "list_files": {
      const fs = await import("fs/promises");
      const path = await import("path");
      const dirPath = args.path;
      const entries = await fs.readdir(dirPath, {
        withFileTypes: true,
        recursive: args.recursive ?? false
      });
      return entries.map(e => 
        `${e.isDirectory() ? "📁" : "📄"} ${path.join(e.parentPath || "", e.name)}`
      ).join("\n");
    }
  }
}
```

### 添加测试

```typescript
// tests/tools.test.ts
describe("list_files tool", () => {
  it("should list files in a directory", async () => {
    const result = await handleToolCall("list_files", {
      path: "/tmp/test-dir"
    });
    expect(result).toContain(".txt");
  });
});
```

---

## 7. 常见问题

### Claude Desktop 连不上

| 症状 | 检查 |
|------|------|
| 工具不出现 | `args` 路径是否是绝对路径 |
| 连接超时 | `npm run build` 是否成功 |
| 工具调用失败 | 检查 `OPENCLAW_API_URL` 是否正确 |

### 调试方法

```bash
# 查看 Claude Desktop 的 MCP 日志
# macOS:
cat ~/Library/Logs/Claude/mcp-server-openclaw.log

# 手动测试 server
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | node dist/index.js
```

### 当前限制

- `web_search` 需要配置 Brave API Key 才能使用真实搜索
- 仅支持 **stdio** 传输（Streamable HTTP 已完成 MVP）
- 文件操作已完全实现（非 mock），直接操作工作区文件系统

---

## 架构速查

```
src/
├── index.ts          # 入口：MCP Server 初始化 + 工具注册 (113L)
└── tools.ts          # 18 个工具定义 + 安全层 (700L)

tests/                # 526 个测试
├── read.test.js
├── write.test.js
├── edit.test.js
├── head-tail.test.js
├── exec-validation.test.js
├── safe-path-validation.test.js
├── memory-search.test.js
└── ... (共 21 个测试文件)
```

---

_下一步：查看 [MCP 官方文档](https://modelcontextprotocol.io/) 了解协议细节。_ 🔌
