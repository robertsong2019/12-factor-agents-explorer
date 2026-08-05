# Mini Agent Framework Tutorial 🧪

> 5 分钟理解 AI Agent 的核心概念

本教程通过一个 ~200 行的玩具框架，带你理解 AI Agent 的四大支柱：**工具调用、记忆、规划、反思**。

## 前置条件

- Python 3.10+
- 无外部依赖

```bash
cd code-lab/mini-agent
python agent.py
```

## Step 1: Hello Agent

```python
from agent import Agent

agent = Agent(name="MyAgent")
reply = agent.run("What time is it?")
print(reply)
# 🔧 Calling tool: clock({})
# 📤 Result: It's Monday, June 01, 2026 at 04:00 AM
```

Agent 自动做了：**规划 → 思考 → 调用工具 → 反思**。

## Step 2: 工具系统

Agent 通过 `Toolbox` 注册和调用工具：

```python
agent = Agent()

# 内置 4 个工具
print(agent.toolbox.available())
# - calculator: Evaluate math expressions
# - clock: Get current date and time
# - memorize: Store a key-value pair
# - recall: Retrieve a value from long-term memory
```

**试一试：**
```
Calculate 42 + 58 + 100
# → 42 + 58 + 100 = 200
```

## Step 3: 记忆系统

两种记忆，模拟人脑：

```python
# 短期记忆 — 对话历史
agent.memory.add_message("user", "hello")
agent.memory.recent(3)  # 最近 3 条

# 长期记忆 — 持久化 key-value
agent.run("Remember that my favorite color is blue")
agent.run("What is my favorite color?")
# → favorite color = blue
```

**模糊匹配：** `recall("color")` 也能找到 `favorite color`。

## Step 4: 规划

`Planner.decompose()` 把目标分解为步骤：

```
Input: "Calculate 42 + 100 and remember the result"
Plan: ["Extract numbers", "Use calculator", "Store in memory", "Reflect"]
```

这是规则匹配的 mock。真实 Agent 中，LLM 负责规划。

## Step 5: 反思

每条回答都经过 `reflect()` 检查：
- 包含 "error" → 标记 ⚠️
- 太短 → 提示可能需要补充
- 正常 → ✅ 确认

```python
final = agent.brain.reflect("The answer is 42")
# → "The answer is 42\n[✅ Reflection: Answer looks good.]"
```

## 架构全景

```
Agent.run(user_input)
    │
    ├─ 1. Planner → 分解为步骤
    ├─ 2. Brain → 生成回复 + 工具调用
    ├─ 3. Toolbox → 执行工具
    ├─ 4. 组合结果
    └─ 5. Brain.reflect → 自检
```

## 核心组件

| 组件 | 行数 | 职责 |
|------|------|------|
| `Memory` | ~30 | 短期对话 + 长期 KV |
| `Toolbox` | ~20 | 注册/查找/调用工具 |
| `Planner` | ~20 | 目标 → 步骤分解 |
| `MockBrain` | ~50 | 模拟 LLM 的思考+反思 |
| `Agent` | ~80 | 编排以上所有组件 |

## 下一步

- 把 `MockBrain.think()` 替换成真实 LLM 调用（OpenAI / Claude）
- 给 `Planner` 加 LLM 驱动的分解能力
- 添加持久化记忆（SQLite / 文件）
- 参考 `code-lab/agent-memory-graph` 做图谱记忆
- 参考 `nano-agent/` 做更完整的 Agent 框架
