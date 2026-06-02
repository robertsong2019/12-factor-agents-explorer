# 🧪 Mini Agent Framework

A toy AI agent framework in ~200 lines of Python. Demonstrates core concepts:
- **Tool calling** — agents can invoke registered tools
- **Memory** — short-term conversation + long-term key-value store
- **Planning** — break goals into steps, execute sequentially
- **Reflection** — agent reviews its own output before responding

## Usage

```bash
python agent.py
```

No external dependencies — uses only Python stdlib (with a mock LLM for demo).

## 相关项目

- **[mini-mcp](../mini-mcp/)** — Agent 的工具协议层
- **[agent-pipeline](../agent-pipeline/)** — Agent 的工作流引擎
- **[综合教程](../TUTORIAL.md)** — 从零构建 AI Agent

## 相关项目

- **[mini-mcp](../mini-mcp/)** — 工具注册与调用协议（Agent 的工具层）
- **[agent-pipeline](../agent-pipeline/)** — 工具串联工作流（Agent 的执行引擎）
- **[综合教程](../TUTORIAL.md)** — 从零构建 AI Agent，串联三个项目

## Architecture

```
Agent
├── Brain (LLM interface — mock for demo)
├── Memory
│   ├── short_term: conversation history
│   └── long_term: persistent key-value store
├── Toolbox (registered callable tools)
└── Planner (decomposes goals into steps)
```
