# Nano-Agent 教程 🧪

> 从零开始，5 分钟构建你的第一个 AI Agent

## 目录

1. [Hello Agent — 最简代理](#1-hello-agent--最简代理)
2. [工具系统 — 让 Agent 能做事](#2-工具系统--让-agent-能做事)
3. [记忆系统 — 让 Agent 记住上下文](#3-记忆系统--让-agent-记住上下文)
4. [LLM 后端 — 接入真实模型](#4-llm-后端--接入真实模型)
5. [实战：构建一个研究助理](#5-实战构建一个研究助理)

---

## 1. Hello Agent — 最简代理

不需要 API key，不需要工具，先跑起来：

```python
from nano_agent import Agent

agent = Agent(
    name="小助手",
    instructions="你是一个友好的助手，用中文回答问题。",
)

response = agent.run("你好！")
print(response)
```

**发生了什么？**

1. `Agent` 使用 `LLM.mock()` 作为默认后端（不需要 API key）
2. 输入被拼入对话历史，发送给 LLM
3. 返回纯文本响应

> 💡 Mock 后端适合测试和开发。生产环境请切换到真实 LLM 后端（见第 4 节）。

---

## 2. 工具系统 — 让 Agent 能做事

Agent 的核心能力来自工具。用 `@tool` 装饰器注册：

```python
from nano_agent import Agent, tool

@tool
def add(a: int, b: int) -> str:
    """计算两个数的和"""
    return str(a + b)

@tool
def multiply(a: int, b: int) -> str:
    """计算两个数的乘积"""
    return str(a * b)

agent = Agent(
    name="计算器",
    instructions="你是一个计算助手，使用工具进行计算。",
    tools=[add, multiply],
)

response = agent.run("计算 15 乘以 7，然后加上 33")
```

**工具注册要点：**

- 函数的 **docstring** 会自动成为工具的 `description`（给 LLM 看的）
- 函数的 **参数签名** 会自动提取为 `parameters`
- 工具返回值应该是 **字符串**

**自定义工具名和描述：**

```python
@tool(name="web_search", description="搜索互联网获取信息")
def search(query: str) -> str:
    return f"搜索结果: {query}"
```

---

## 3. 记忆系统 — 让 Agent 记住上下文

Memory 组件让 Agent 能跨对话保留信息：

```python
from nano_agent import Agent, Memory

# 创建带持久化的记忆
memory = Memory(
    max_entries=100,           # 最多保留 100 条
    persistence_path="data/memory.json"  # 持久化到文件
)

agent = Agent(
    name="助手",
    instructions="你是一个有记忆的助手。",
    memory=memory,
)

# 第一轮对话
agent.run("我叫小明，我喜欢编程")

# 第二轮对话 — Agent 能回忆起之前的信息
response = agent.run("我叫什么名字？我喜欢什么？")
```

**Memory API：**

| 方法 | 说明 |
|------|------|
| `add(content, metadata)` | 添加一条记忆 |
| `search(query, limit)` | 关键词搜索记忆 |
| `get_recent(n)` | 获取最近 n 条记忆 |
| `get_all()` | 获取所有记忆 |
| `clear()` | 清空记忆 |

---

## 4. LLM 后端 — 接入真实模型

### OpenAI / 兼容 API

```python
from nano_agent import Agent
from nano_agent.llm import OpenAIBackend

llm = OpenAIBackend(
    api_key="sk-xxx",
    base_url="https://api.openai.com/v1",  # 可换成任何兼容 API
    model="gpt-4o-mini"
)

agent = Agent(
    name="助手",
    instructions="你是一个有帮助的助手。",
    llm=llm,
)
```

### 自定义后端

继承 `LLMBackend` 实现自己的后端：

```python
from nano_agent.llm import LLMBackend

class MyBackend(LLMBackend):
    def complete(self, messages, tools=None, **kwargs):
        # 调用你的模型
        response_text = my_model.chat(messages)
        return {
            "content": response_text,
            "tool_calls": None,
            "usage": {"tokens": 0}
        }

agent = Agent(name="助手", instructions="...", llm=MyBackend())
```

---

## 5. 实战：构建一个研究助理

组合所有组件：

```python
from nano_agent import Agent, tool, Memory
from nano_agent.llm import OpenAIBackend
import json

# 工具定义
@tool
def save_note(title: str, content: str) -> str:
    """保存研究笔记"""
    note = {"title": title, "content": content}
    # 实际应用中保存到数据库或文件
    return f"已保存笔记: {title}"

@tool
def summarize(text: str) -> str:
    """生成摘要（简化版）"""
    sentences = text.split('。')[:3]
    return '。'.join(sentences) + '。'

# 组装 Agent
researcher = Agent(
    name="研究助理",
    instructions="""你是一个研究助理，帮助用户：
1. 整理和分析信息
2. 生成摘要
3. 保存重要笔记
请主动使用工具完成任务。""",
    llm=OpenAIBackend(
        api_key="sk-xxx",
        model="gpt-4o-mini"
    ),
    tools=[save_note, summarize],
    memory=Memory(persistence_path="data/research.json"),
    max_iterations=5,
)

# 使用
response = researcher.run("帮我研究一下 RAG 技术的最新进展")
print(response)
```

---

## 设计理念速查

| 理念 | 体现 |
|------|------|
| **极简** | 核心 < 500 行，5 分钟上手 |
| **可组合** | Agent = LLM + Tools + Memory，任意组合 |
| **可观测** | `verbose=True` 看到每步执行过程 |
| **资源友好** | 最小依赖，可运行在受限环境 |

## 下一步

- 阅读 [examples/](examples/) 中的完整示例
  - `planner.py` — 任务规划代理
  - `coder.py` — 代码生成代理
  - `researcher.py` — 研究助理
- 查看源码 `src/nano_agent/` 了解实现细节

---

_有问题？看源码是最好的文档 — 核心代码不到 500 行。_ 🧪
