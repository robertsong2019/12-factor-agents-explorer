# 🧪 Catalyst Lab

Experimental projects exploring the frontier of AI agent infrastructure.

## Active Projects

| Project | Status | Tests | Description |
|---------|--------|-------|-------------|
| **[agent-observability](agent-observability/)** | 🟢 Active | 91+ | Tracing + PolicyEngine + Evaluator for agent runs |
| **[structured-output-toolkit](structured-output-toolkit/)** | 🟢 Active | 273 | Zod-driven structured LLM output: 13-module toolkit (consensus, validation, recovery, scoring, diff) |
| **[a2a-trust-prototype](a2a-trust-prototype/)** | 🟢 Active | 27+ | Agent-to-Agent trust scoring with EdDSA signatures |
| **[openclaw-langgraph-bridge](openclaw-langgraph-bridge/)** | 🔬 Research | 18 | LangGraph.js integration with OpenClaw Gateway |
| **[agent-context-store](agent-context-store/)** | 🟡 Paused | 97 | KV store with changelog and graph queries |

## Completed / Archived

| Project | Description |
|---------|-------------|
| **[a2a-minimal](a2a-minimal/)** | Minimal A2A protocol client/server |
| **[mcp-client-explorer](mcp-client-explorer/)** | MCP server discovery and exploration |
| **[openclaw-mcp-server](openclaw-mcp-server/)** | OpenClaw as an MCP server |
| **[pocket-agent](pocket-agent/)** | Minimal agent runtime experiment |

## Backlog (Research Done, Awaiting Implementation)

| Project | Research | Notes |
|---------|----------|-------|
| **hindsight-mini** | [笔记](../catalyst-research/exploration-notes/2026-05-13-hindsight-mini.md) | Agent self-reflection via HER + Reflexion |
| **wasm-agent-sandbox** | [笔记](../catalyst-research/exploration-notes/2026-05-13-wasm-agent-sandbox-runtime.md) | WASM sandboxed agent execution |

## 📚 Learning Path (从零构建 Agent)

如果刚接触 Agent 开发，推荐按以下顺序学习：

| 顺序 | 项目 | 教程 | 核心概念 |
|------|------|------|----------|
| 1 | [nano-agent](../nano-agent/) | [TUTORIAL](../nano-agent/TUTORIAL.md) + [API](../nano-agent/API.md) | Agent 核心：LLM ↔ Tools ↔ Memory 循环 |
| 2 | [mini-agent](code-lab/mini-agent/) | [综合教程](code-lab/TUTORIAL.md) | 深入 ReAct Loop 和 tool 注册 |
| 3 | [mini-mcp](code-lab/mini-mcp/) | [综合教程](code-lab/TUTORIAL.md) | MCP 工具调用协议 |
| 4 | [agent-pipeline](code-lab/agent-pipeline/) | [独立教程](code-lab/agent-pipeline/TUTORIAL.md) | 工具串联成工作流 |
| 5 | [pocket-agent](pocket-agent/) | [教程](pocket-agent/TUTORIAL.md) | Self-Evolving Agent（exec() 动态工具生成） |
| 6 | [agent-observability](agent-observability/) | README Quick Start | 观测、治理、评估 Agent 执行 |

> 💡 顺序 1-4 有一篇串联教程：[`code-lab/TUTORIAL.md`](code-lab/TUTORIAL.md)

## Research Notes

All research lives in [`catalyst-research/exploration-notes/`](../catalyst-research/exploration-notes/) — 150+ deep-dive notes covering A2A protocol, structured output, observability, trust models, and more.
