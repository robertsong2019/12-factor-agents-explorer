# Quick Start — AI Agent Workspace

> 5 分钟了解这个 workspace 里有什么、怎么用。

## 🗺️ Workspace 结构

```
workspace/
├── projects/          # 完整可运行的项目
│   ├── agent-task-cli/       # 多 Agent 任务编排 CLI
│   ├── agent-memory-service/ # Agent 记忆管理服务
│   ├── agent-memory-graph/   # 知识图谱记忆（Python）
│   ├── agent-log/            # Agent 日志分析（Bash）
│   ├── context-forge/        # 为 AI 工具生成上下文文件
│   ├── mission-control/      # 任务看板
│   └── prompt-mgr/           # Prompt 管理
├── skills/            # OpenClaw 技能插件
├── experiments/       # 实验性代码
├── code-lab/          # 编程实验
├── examples/          # 集成示例
├── docs/              # 文档和报告
└── experiments/       # 原型和实验
```

## 🚀 三个最实用的工具

### 1. context-forge — 一键生成 AI 上下文

```bash
node projects/context-forge/context-forge.mjs /path/to/your-project
```

自动生成 `AGENTS.md`、`.cursorrules` 等，让 Cursor/Copilot/Claude 更懂你的项目。

### 2. agent-task-cli — 多 Agent 编排

```bash
cd projects/agent-task-cli && npm install && npm link
agent-task run task.yaml
```

支持 Work Crew、Supervisor、Pipeline、Council 等编排模式。详见 [docs/TUTORIAL.md](projects/agent-task-cli/docs/TUTORIAL.md)。

### 3. agent-memory-service — Agent 记忆管理

```bash
cd projects/agent-memory-service && npm install && npm test
```

三层记忆（短期/长期/核心）+ 语义搜索 + 遗忘衰减。零外部依赖。

## 📖 深入了解

| 文档 | 路径 |
|------|------|
| 项目列表和状态 | [README.md](../README.md) |
| 文档维护指南 | [docs/DOCUMENTATION-GUIDE.md](DOCUMENTATION-GUIDE.md) |
| 历史改进报告 | [docs/reports/](reports/) |
| 集成示例 | [examples/README.md](../examples/README.md) |

## 🧪 运行全部示例

```bash
python3 examples/integration-demo.py
```

---

_最后更新: 2026-04-20_
