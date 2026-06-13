# Agent Task Orchestrator (ato)

> 基于依赖关系的智能任务编排器，支持并行执行、Agent 协作和多种任务类型

[![Tests](https://img.shields.io/badge/tests-27-brightgreen)]()
[![Node](https://img.shields.io/badge/node-%3E%3D16.0.0-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

## 🎯 概述

`ato` 是一个命令行任务编排工具，让你用 JSON 定义任务依赖图，自动进行拓扑排序、并行执行和结果追踪。支持三种任务类型：Shell 命令、Agent 调用和自定义函数。

核心能力：

- **依赖图执行** — 自动拓扑排序，同层任务并行执行
- **三种任务类型** — `shell`（命令行）、`agent`（AI Agent）、`function`（自定义函数）
- **执行控制** — 顺序/并行模式、dry-run 预览、选择性执行
- **验证与导出** — 依赖循环检测、JSON/YAML/Markdown 导出
- **彩色 CLI** — 使用 chalk 提供清晰的执行进度反馈

## 安装

```bash
cd tools/agent-task-orchestrator
npm install
npm link  # 全局注册 ato 命令（可选）
```

依赖：`commander`、`chalk`、`fs-extra`、`yaml`

## 快速开始

```bash
# 1. 创建编排
ato create my-pipeline --description "数据处理流水线"

# 2. 添加任务（自动存入 .orchestrator/my-pipeline.json）
ato add-task my-pipeline fetch-data -t shell -c "curl -s https://api.example.com/data -o raw.json"
ato add-task my-pipeline parse -t shell -c "jq '.items' raw.json > parsed.json" -d fetch-data
ato add-task my-pipeline analyze -t agent -a catalyst -c "分析 parsed.json 中的趋势" -d parse

# 3. 预览执行计划
ato run my-pipeline --dry-run

# 4. 执行
ato run my-pipeline --verbose
```

## CLI 命令参考

### `ato create <name>`

创建新的编排文件。

| 选项 | 说明 |
|------|------|
| `-d, --description <desc>` | 编排描述 |
| `-f, --force` | 覆盖已有编排 |

### `ato add-task <orchestrator> <task-name>`

向编排添加任务。

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `-t, --type <type>` | 任务类型：`shell` / `agent` / `function` | `shell` |
| `-c, --command <cmd>` | 执行命令（shell）或 prompt（agent） | — |
| `-a, --agent <name>` | Agent 名称（type=agent 时） | — |
| `-d, --depends <deps>` | 依赖任务 ID（逗号分隔） | — |
| `-p, --priority <num>` | 优先级 1-10 | `5` |
| `-o, --output <path>` | 输出文件路径 | — |
| `--timeout <ms>` | 超时（毫秒） | — |
| `--description <desc>` | 任务描述 | — |

### `ato run <orchestrator>`

执行编排。

| 选项 | 说明 |
|------|------|
| `-s, --sequential` | 顺序执行（禁用并行） |
| `-d, --dry-run` | 只显示执行计划，不实际运行 |
| `-v, --verbose` | 显示详细输出 |
| `-t, --tasks <ids>` | 只执行指定任务（逗号分隔） |

### `ato list`

列出当前项目所有编排。

### `ato status <orchestrator>`

查看编排详情和分阶段执行计划。

### `ato validate <orchestrator>`

验证编排配置（检测循环依赖、重复 ID、缺失依赖等）。

### `ato export <orchestrator>`

导出编排为其他格式。

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `-f, --format <fmt>` | `json` / `yaml` / `markdown` | `json` |
| `-o, --output <file>` | 输出文件路径 | `<name>_export.<ext>` |

## 编排文件结构

```json
{
  "name": "my-pipeline",
  "description": "数据处理流水线",
  "version": "1.0.0",
  "createdAt": "2026-06-13T12:00:00.000Z",
  "tasks": [
    {
      "id": "fetch-data",
      "type": "shell",
      "command": "curl -s https://api.example.com/data",
      "priority": 5,
      "dependsOn": []
    },
    {
      "id": "analyze",
      "type": "agent",
      "agent": "catalyst",
      "prompt": "分析数据趋势",
      "priority": 5,
      "dependsOn": ["fetch-data"]
    }
  ],
  "settings": {
    "parallelExecution": true,
    "continueOnError": false,
    "timeout": 300000
  }
}
```

## 执行模型

```
阶段 1: [fetch-data]           ← 无依赖，立即执行
阶段 2: [parse]                ← 依赖 fetch-data
阶段 3: [analyze, notify]      ← 都依赖 parse，并行执行
```

同阶段任务并行执行（`Promise.all`），阶段间串行等待。顺序模式 (`--sequential`) 下所有任务单层串行。

## 程序化 API

```javascript
import { buildExecutionPlan, validateOrchestrator } from './index.js';

// 构建执行计划
const plan = buildExecutionPlan(tasks, false); // false = 并行模式

// 验证编排
const result = validateOrchestrator(data);
if (!result.isValid) {
  console.error(result.errors);
}
```

## 测试

```bash
npm test
```

27 个测试覆盖：执行计划构建、编排验证、Markdown 报告生成、状态图标映射。

## 项目结构

```
index.js              # CLI 入口 + 核心逻辑（685 行）
test/
  orchestrator.test.js # 27 个单元测试
package.json
```

## License

MIT
