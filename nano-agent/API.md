# API 参考 🧪

> Nano-Agent 框架的完整 API 文档

---

## 目录

- [Agent](#agent)
- [Tool 装饰器](#tool-装饰器)
- [Tool 类](#tool-类)
- [Memory](#memory)
- [LLM 接口](#llm-接口)
- [LLMBackend](#llmbackend)
- [OpenAIBackend](#openaibackend)
- [MockBackend](#mockbackend)

---

## Agent

```python
from nano_agent import Agent
```

AI 代理的核心类。负责推理循环、工具调用、记忆管理和对话追踪。

### 构造函数

```python
Agent(
    name: str,                         # 代理名称，用于日志和系统提示
    instructions: str,                 # 系统指令，定义代理的行为
    llm: Optional[LLM] = None,        # LLM 后端，默认 MockBackend
    tools: Optional[List[Tool]] = None,  # 可用工具列表
    memory: Optional[Memory] = None,   # 记忆管理器
    max_iterations: int = 10,          # 最大推理迭代轮数
    verbose: bool = True               # 是否打印执行过程
)
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | `str` | 必填 | 代理名称，出现在系统提示和日志中 |
| `instructions` | `str` | 必填 | 代理的行为指令，决定代理如何响应 |
| `llm` | `LLM` | `LLM.mock()` | 语言模型后端 |
| `tools` | `List[Tool]` | `[]` | 代理可调用的工具列表 |
| `memory` | `Memory` | `Memory()` | 记忆管理器实例 |
| `max_iterations` | `int` | `10` | 推理循环最大轮数，防止无限循环 |
| `verbose` | `bool` | `True` | 控制日志输出 |

### 方法

#### `run(user_input, context=None)`

运行代理，执行推理循环。

```python
response: str = agent.run("你好")
response: str = agent.run("分析这段代码", context="def foo(): pass")
```

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `user_input` | `str` | 用户输入文本 |
| `context` | `Optional[str]` | 附加上下文，会被注入系统提示 |

**返回：** `str` — 代理的最终文本响应

**执行流程：**
1. 构建系统提示（instructions + 工具列表 + 记忆 + 上下文）
2. 发送消息给 LLM
3. 如果 LLM 返回工具调用 → 执行工具，将结果追加到消息列表
4. 重复步骤 2-3，直到 LLM 不再调用工具或达到 `max_iterations`
5. 将对话保存到记忆，返回最终响应

#### `reset()`

清除对话历史。

```python
agent.reset()  # 清空本次会话的对话记录
```

> 注意：`reset()` 只清空对话历史，不清空 Memory 中的长期记忆。

### 内部行为

**系统提示构建顺序：**
1. 代理名称和指令
2. 可用工具列表
3. 附加上下文（如有）
4. 记忆中的近期条目
5. 工作流程指引

**对话历史：** 保留最近 10 轮对话，防止上下文过长。

---

## Tool 装饰器

```python
from nano_agent import tool
```

将普通 Python 函数注册为 Agent 可调用的工具。

### 基本用法

```python
@tool
def search(query: str) -> str:
    """搜索网络获取信息"""
    return f"搜索 '{query}' 的结果"
```

### 自定义名称和描述

```python
@tool(name="web_search", description="搜索互联网获取实时信息")
def my_search(q: str) -> str:
    return f"结果: {q}"
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | `str` | 函数名 | 工具名称（LLM 通过名称调用） |
| `description` | `str` | 函数 docstring | 工具描述（LLM 根据描述决定是否调用） |

### 自动提取规则

- **名称：** 未指定时使用函数名
- **描述：** 未指定时使用函数 docstring 的第一行
- **参数：** 自动从函数签名提取，默认类型为 `string`
- **默认值：** 自动识别带默认值的参数

```python
@tool
def search(query: str, max_results: int = 10) -> str:
    # 参数会被自动提取为:
    # {"query": {"type": "string"}, "max_results": {"type": "string", "default": 10}}
    ...
```

> ⚠️ 当前版本参数类型统一为 `string`。如需精确类型，建议在 docstring 中说明。

---

## Tool 类

```python
from nano_agent.tools import Tool
```

工具的数据类，通常通过 `@tool` 装饰器自动创建。

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 工具名称 |
| `description` | `str` | 工具描述 |
| `func` | `Callable` | 实际执行的函数 |
| `parameters` | `Dict[str, Any]` | 参数定义 |

### 方法

#### `execute(**kwargs)`

执行工具函数。

```python
result = my_tool.execute(query="AI", max_results=5)
```

#### `to_dict()`

转换为字典格式，供 LLM 使用。

```python
schema = my_tool.to_dict()
# {"name": "search", "description": "...", "parameters": {...}}
```

### 全局函数

```python
from nano_agent.tools import get_tool, list_tools, clear_tools
```

| 函数 | 说明 |
|------|------|
| `get_tool(name)` | 按名称获取已注册工具 |
| `list_tools()` | 列出所有已注册工具 |
| `clear_tools()` | 清除所有已注册工具 |
| `get_tool_from_func(func)` | 从函数获取其关联的 Tool 对象 |

---

## Memory

```python
from nano_agent import Memory
```

记忆管理器，支持短期记忆和可选的文件持久化。

### 构造函数

```python
Memory(
    max_entries: int = 100,              # 最大记忆条数
    persistence_path: Optional[str] = None  # 持久化文件路径
)
```

### 方法

#### `add(content, metadata=None)`

添加一条记忆。

```python
memory.add("用户偏好中文回复", metadata={"type": "preference"})
```

#### `search(query, limit=5)`

关键词搜索记忆（不区分大小写）。

```python
results = memory.search("用户偏好", limit=3)
# 返回 List[MemoryEntry]
```

#### `get_recent(n=5)`

获取最近 n 条记忆。

```python
recent = memory.get_recent(10)
```

#### `get_all()`

获取所有记忆的副本。

#### `clear()`

清空所有记忆并删除持久化文件内容。

#### `to_context(max_tokens=1000)`

将近期记忆格式化为可注入提示的文本。

```python
context_str = memory.to_context(max_tokens=500)
# "## 记忆\n- 2024-01-10 14:30: 用户偏好中文回复\n- ..."
```

### MemoryEntry

记忆条目数据类。

| 属性 | 类型 | 说明 |
|------|------|------|
| `content` | `str` | 记忆内容 |
| `timestamp` | `datetime` | 创建时间 |
| `metadata` | `Dict[str, Any]` | 附加元数据 |

### 持久化

设置 `persistence_path` 后，记忆会自动保存到 JSON 文件：

```python
memory = Memory(persistence_path="data/memory.json")
# 每次 add/clear 自动读写文件
# 文件格式: [{"content": "...", "timestamp": "...", "metadata": {...}}, ...]
```

---

## LLM 接口

```python
from nano_agent.llm import LLM
```

LLM 的统一接口层，封装不同的后端实现。

### 工厂方法

```python
# 使用 OpenAI（或兼容 API）
llm = LLM.openai(api_key="sk-xxx", base_url="...", model="gpt-4o-mini")

# 使用 Mock（测试用）
llm = LLM.mock()
```

### 方法

#### `chat(messages, tools=None, **kwargs)`

发送聊天请求。

```python
response = llm.chat(
    messages=[
        {"role": "system", "content": "你是助手"},
        {"role": "user", "content": "你好"}
    ],
    tools=[{"name": "search", "description": "搜索", "parameters": {}}]
)
```

**返回格式：**

```python
{
    "content": "回复文本",           # str，可能为空字符串
    "tool_calls": [                  # List[Dict]，可能为空列表
        {
            "id": "call_xxx",
            "name": "search",
            "arguments": '{"query": "AI"}'  # str (JSON)
        }
    ],
    "usage": {                       # Dict，token 使用统计
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150
    }
}
```

---

## LLMBackend

```python
from nano_agent.llm import LLMBackend
```

LLM 后端的抽象基类。自定义后端必须继承此类。

### 抽象方法

#### `complete(messages, tools=None, **kwargs)`

```python
class MyBackend(LLMBackend):
    def complete(self, messages, tools=None, **kwargs):
        # 你的实现
        return {
            "content": "回复",
            "tool_calls": [],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }
```

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `messages` | `List[Dict[str, str]]` | 对话消息列表 |
| `tools` | `Optional[List[Dict]]` | 可用工具的 schema 列表 |
| `**kwargs` | | 传递给底层 API 的额外参数 |

**返回：** `Dict[str, Any]` — 必须包含 `content`、`tool_calls`、`usage`

---

## OpenAIBackend

```python
from nano_agent.llm import OpenAIBackend
```

OpenAI API 后端，兼容所有 OpenAI 格式的 API（如 Azure OpenAI、vLLM、Ollama 等）。

### 构造函数

```python
OpenAIBackend(
    api_key: str,
    base_url: str = "https://api.openai.com/v1",
    model: str = "gpt-3.5-turbo"
)
```

### 依赖

需要安装 `openai` 包：

```bash
pip install openai
```

### 兼容 API 示例

```python
# Azure OpenAI
OpenAIBackend(api_key="...", base_url="https://xxx.openai.azure.com/v1", model="gpt-4")

# 本地 Ollama
OpenAIBackend(api_key="dummy", base_url="http://localhost:11434/v1", model="llama3")

# vLLM
OpenAIBackend(api_key="dummy", base_url="http://localhost:8000/v1", model="meta-llama/Meta-Llama-3-8B")

# 其他兼容 API（DeepSeek、Moonshot 等）
OpenAIBackend(api_key="sk-xxx", base_url="https://api.deepseek.com/v1", model="deepseek-chat")
```

---

## MockBackend

```python
from nano_agent.llm import MockBackend
```

测试和演示用的模拟后端。不需要 API key。

### 行为规则

| 输入条件 | 返回行为 |
|----------|----------|
| 消息包含"搜索" | 返回工具调用（调用第一个工具） |
| 其他 | 返回模拟文本回复 |

```python
from nano_agent.llm import MockBackend

llm = MockBackend()
response = llm.complete([{"role": "user", "content": "你好"}])
# {"content": "这是对 '你好' 的模拟回复", "tool_calls": [], "usage": {...}}
```

---

## 架构图

```
┌─────────────────────────────────────────┐
│                  Agent                   │
│                                          │
│  run(user_input)                         │
│    │                                     │
│    ├── _build_messages()                 │
│    │     ├── system prompt (instructions)│
│    │     ├── history (last 10 rounds)    │
│    │     ├── user input                  │
│    │     └── memory context              │
│    │                                     │
│    └── loop (max_iterations):            │
│          ├── LLM.chat(messages, tools)   │
│          ├── if tool_calls:              │
│          │     └── _execute_tool(call)   │
│          └── else: break                 │
│                                          │
│  return final_response                   │
└─────────────────────────────────────────┘
         │              │              │
         ▼              ▼              ▼
    ┌─────────┐   ┌─────────┐   ┌──────────┐
    │   LLM   │   │  Tools  │   │  Memory  │
    │ (Backend)│   │ (@tool) │   │ (persist)│
    └─────────┘   └─────────┘   └──────────┘
```

---

## 快速参考卡

```python
from nano_agent import Agent, tool, Memory
from nano_agent.llm import OpenAIBackend

# 1. 定义工具
@tool
def my_tool(param: str) -> str:
    """工具描述"""
    return "结果"

# 2. 创建代理
agent = Agent(
    name="助手",
    instructions="你是一个助手",
    llm=OpenAIBackend(api_key="sk-xxx"),
    tools=[my_tool],
    memory=Memory(persistence_path="data/mem.json"),
)

# 3. 运行
response = agent.run("你好")
agent.reset()  # 清空对话
```

---

_源码即文档 — 核心不到 500 行，直接阅读 `src/nano_agent/` 了解细节。_ 🧪
