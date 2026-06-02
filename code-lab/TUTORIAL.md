# 🧪 从零构建 AI Agent：概念与实践

> 一篇串联 mini-agent → mini-mcp → agent-pipeline 的综合教程。
> 读完你会理解 AI Agent 的三大核心：**大脑、工具、工作流**。

---

## 你将学到什么

| 概念 | 实践项目 | 行数 |
|------|---------|------|
| Agent 的基本结构 | mini-agent | ~200 |
| 工具注册与调用协议 | mini-mcp | ~150 |
| 工具串联成工作流 | agent-pipeline | ~400 |

三个项目加起来不到 800 行代码，但覆盖了 AI Agent 最核心的架构。

---

## 第一部分：Agent 是什么？(mini-agent)

### 问题

"AI Agent" 听起来很神秘，但本质上就是：

```
感知 → 思考 → 行动
```

循环往复，直到任务完成。

### mini-agent 的答案

mini-agent 用 ~200 行实现了这个循环：

```
Agent
├── Brain (LLM — 做决策的"大脑")
├── Memory (短期对话 + 长期记忆)
├── Toolbox (可以调用的工具)
└── Planner (把目标拆成步骤)
```

### 关键代码模式

```python
# 1. 注册工具 — Agent "会"什么
agent.toolbox.register("search", search_function)
agent.toolbox.register("calculate", calc_function)

# 2. 规划 — 把 "写一份报告" 拆成步骤
steps = agent.planner.decompose("写一份市场分析报告")
# → ["收集数据", "分析趋势", "生成报告"]

# 3. 执行循环
for step in steps:
    result = agent.execute(step)
    agent.memory.save(step, result)  # 记住做了什么
```

### 三个核心洞察

1. **Agent ≠ LLM**：LLM 是大脑，Agent 还需要记忆、工具、规划能力
2. **记忆分两层**：短期（当前对话）+ 长期（跨会话的知识）
3. **规划是关键**：复杂任务需要分解，而不是一口气做完

### 动手试

```bash
cd code-lab/mini-agent
python agent.py
```

---

## 第二部分：工具怎么调用？(mini-mcp)

### 问题

Agent 有了大脑，但怎么跟外部世界交互？需要一个**标准化的工具协议**。

这就是 MCP (Model Context Protocol) 要解决的问题。

### mini-mcp 的答案

用一个装饰器就能把普通 Python 函数变成"工具"：

```python
@registry.register("time", description="获取当前时间")
def get_time(tz: str = "UTC") -> dict:
    from datetime import datetime, timezone
    return {"time": datetime.now(timezone.utc).isoformat()}
```

系统自动帮你做三件事：
1. **提取 schema** — 函数名、参数类型、默认值
2. **注册到目录** — `list` 命令可以看到
3. **标准化调用** — JSON 进，JSON 出

### 工具调用的完整流程

```
LLM 说："我需要查一下时间"
    ↓
Agent 构造调用: {"name": "time", "args": {"tz": "Asia/Shanghai"}}
    ↓
Mini-MCP 路由到 get_time 函数
    ↓
函数返回: {"time": "2026-06-03T04:00:00+08:00"}
    ↓
LLM 拿到结果，继续思考
```

### 为什么是 JSON？

因为 LLM 输入输出都是文本，JSON 是最通用的结构化文本格式：
- LLM 能理解（训练数据里有大量 JSON）
- 任何语言都能解析（通用性）
- 嵌套结构能表达复杂数据（表达力）

### 动手试

```bash
cd code-lab/mini-mcp

# 列出所有工具
python3 mini_mcp.py --list

# 调用工具
python3 mini_mcp.py --call calc '{"expr": "2**10 + 1"}'
# → {"result": 1025}

# 交互式探索
python3 mini_mcp.py
```

---

## 第三部分：工具怎么组合？(agent-pipeline)

### 问题

单个工具能做的事很有限。真正的能力来自**工具的组合**。

就像 Unix pipe：`cat log | grep ERROR | wc -l`

### agent-pipeline 的答案

用 YAML 声明工作流：

```yaml
name: log-analyzer
steps:
  - tool: text.clean
    config:
      lowercase: true
      trim_whitespace: true

  - tool: agent.extract
    config:
      patterns:
        - "ERROR: (?P<error>.+)"

  - tool: data.transform
    config:
      format: json
```

数据自动在步骤间流转：

```
"2026-06-02 ERROR: Connection timeout\nWARN: Retry..."
    ↓ text.clean
"2026-06-02 error: connection timeout warn: retry..."
    ↓ agent.extract
{"error": "connection timeout"}
    ↓ data.transform
{"error": "connection timeout"}  # JSON 格式化输出
```

### 为什么用 YAML 而不是代码？

1. **声明式** — 只说"做什么"，不说"怎么做"
2. **可读性** — 非程序员也能理解和修改
3. **可序列化** — 可以保存、分享、版本控制
4. **热更新** — 改工作流不用重启服务

### 自定义工具

```python
from pipeline import Tool

class SentimentTool(Tool):
    name = "my.sentiment"
    description = "简单情感分析"
    
    def process(self, input_data, config):
        text = str(input_data).lower()
        positive = sum(1 for w in ["好", "棒", "great"] if w in text)
        negative = sum(1 for w in ["差", "烂", "bad"] if w in text)
        return {"sentiment": "positive" if positive > negative else "negative"}
```

### 动手试

```bash
cd code-lab/agent-pipeline

# 运行示例
python pipeline.py run examples/basic.yaml

# 调试模式 — 看每步的数据流
python pipeline.py run examples/log-analysis.yaml --debug

# 交互式
python pipeline.py repl
```

---

## 三者关系：一张图

```
┌─────────────────────────────────────────┐
│              AI Agent                    │
│                                         │
│  ┌─────────┐    ┌──────────────────┐    │
│  │  Brain   │───→│  Planner         │    │
│  │  (LLM)   │    │  (目标→步骤)      │    │
│  └─────────┘    └───────┬──────────┘    │
│                         │               │
│                    执行步骤              │
│                         │               │
│  ┌──────────────────────▼────────────┐  │
│  │        Tool Protocol (MCP)        │  │
│  │                                   │  │
│  │  ┌──────┐ ┌──────┐ ┌──────┐      │  │
│  │  │Tool A│→│Tool B│→│Tool C│      │  │
│  │  └──────┘ └──────┘ └──────┘      │  │
│  │         Pipeline 工作流            │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  Memory (短期 + 长期)            │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘

mini-agent = 整个框架
mini-mcp   = Tool Protocol 层
agent-pipeline = Pipeline 工作流层
```

---

## 学习路径

```
1. mini-agent     → 理解 Agent 的整体架构
2. mini-mcp       → 理解工具协议（Agent 怎么用工具）
3. agent-pipeline → 理解工作流（工具怎么串联）
```

每个项目都可以独立运行，不需要另外两个。但理解了全部三个，你就掌握了 AI Agent 的核心架构。

---

## 延伸阅读

- **真实 MCP 协议**: [modelcontextprotocol.io](https://modelcontextprotocol.io)
- **真实 Agent 框架**: LangChain, CrewAI, OpenAI Agents SDK
- **本项目更多实验**: `lab/` 目录下的 agent-observability、agent-context-store 等

---

_代码实验室出品 — 2026-06-03_
