# 🤖 Agent Orchestrator

Multi-agent orchestration for OpenClaw using **CrewAI** and **LangGraph** frameworks. Build complex, stateful AI workflows with task dependencies, conditional routing, and parallel execution.

## When to Use

- Coordinating multiple AI agents for complex tasks (content creation, research pipelines, customer support)
- Building workflows with dependencies between steps
- Need stateful, conditional agent pipelines

## Quick Start

### CrewAI Mode (Role-Based Teams)

```
Use agent-orchestrator: create a content team with a researcher and writer
```

Creates specialist agents that collaborate—researcher gathers info, writer produces output.

### LangGraph Mode (State Machines)

```
Use agent-orchestrator: build a LangGraph pipeline for processing customer feedback
```

For workflows requiring conditional branching, loops, and explicit state management.

## Features

| Feature | CrewAI | LangGraph |
|---------|--------|-----------|
| Role-based agents | ✅ | ❌ |
| State machines | ❌ | ✅ |
| Parallel execution | ✅ | ✅ |
| Conditional routing | Limited | ✅ |
| Task dependencies | ✅ | ✅ |

## Requirements

- Python ≥ 3.8
- See SKILL.md for full API reference
