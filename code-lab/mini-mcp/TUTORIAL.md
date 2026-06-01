# Mini-MCP 教程：从零理解 Model Context Protocol

> 本教程用 ~150 行 Python 代码，带你理解 MCP 的核心概念。
> 不需要任何框架，只需要 Python 标准库。

## 前置知识

- Python 基础（函数、装饰器、类型注解）
- JSON 基本概念
- 对 MCP（Model Context Protocol）有好奇心

---

## Step 1: 理解问题 — 为什么需要工具协议？

LLM 本质上是文本处理器。要让它们"执行操作"（查时间、算数学、查数据库），
需要一个**标准化的接口**：

```
LLM → "我想调用 time 工具" → 工具服务器 → 返回 JSON 结果 → LLM
```

MCP 就是定义这个"对话规则"的协议。Mini-MCP 用最少的代码模拟了这个过程。

---

## Step 2: 工具注册 — 装饰器模式

Mini-MCP 的核心是 `ToolRegistry`。注册一个工具只需一个装饰器：

```python
from mini_mcp import registry

@registry.register("greet", description="打招呼", name="对方名字")
def greet(name: str, language: str = "zh") -> dict:
    """用指定语言打招呼"""
    greetings = {"zh": f"你好，{name}！", "en": f"Hello, {name}!"}
    return {"text": greetings.get(language, greetings["zh"])}

# 工具已注册！现在 LLM 可以通过 "greet" 名字调用它
```

**发生了什么？**
1. `@registry.register(...)` 创建了一个 `Tool` 对象
2. `inspect` 模块自动提取了函数签名 → 生成参数 schema
3. 工具名、描述、参数类型都存入 registry

---

## Step 3: 工具发现 — 自动生成 Schema

LLM 需要知道有哪些工具可用、参数是什么。Mini-MCP 自动完成这件事：

```python
# 列出所有工具的 schema
for tool in registry.list_tools():
    print(tool)
```

输出示例：
```json
{
  "name": "greet",
  "description": "打招呼",
  "parameters": {
    "name": {"type": "string", "description": "对方名字", "required": true},
    "language": {"type": "string", "description": "", "required": false}
  }
}
```

**关键洞察**: MCP 协议的核心就是这份 schema。
真实 MCP 用 JSON-RPC，Mini-MCP 用 Python dict，但概念完全一样。

---

## Step 4: 工具调用 — JSON 进，JSON 出

统一的调用接口，输入 JSON，输出 JSON：

```python
# 编程式调用
result = registry.call("greet", name="世界", language="zh")
print(result)  # {"text": "你好，世界！"}

# 命令行调用
# python3 mini_mcp.py --call greet '{"name": "World", "language": "en"}'
```

**为什么强调 JSON？**
- LLM 天然擅长生成 JSON
- JSON 是语言无关的（Python/JS/Rust 都能解析）
- 嵌套结构可以表达复杂返回值

---

## Step 5: 交互式 REPL — 模拟 LLM 工具调用

启动 REPL 体验完整的工具交互流程：

```bash
python3 mini_mcp.py
```

```
🔧 Mini-MCP Tool Server
   7 tools registered

Commands: list | call <name> [json] | schema <name> | help | quit

mcp> list
  📌 time: Get current date/time
      - timezone: string
  📌 calc: Evaluate a math expression safely
      - expr: string (required)
  ...

mcp> call time {"timezone": "America/New_York"}
  ✅ {
    "iso": "2026-06-02T00:00:00-04:00",
    "weekday": "Tuesday",
    "formatted": "2026-06-02 00:00:00"
  }

mcp> schema calc
{
  "name": "calc",
  "parameters": {
    "expr": {"type": "string", "required": true}
  }
}
```

这和真实 LLM 的工具调用流程**完全一致**：
1. LLM 看到 `list` 返回的 schema → 知道有哪些工具
2. LLM 决定调用某个工具 → 生成 JSON 参数
3. 工具执行 → 返回 JSON 结果
4. LLM 读取结果 → 继续推理

---

## Step 6: 编写自定义工具

尝试添加你自己的工具：

```python
from mini_mcp import registry

@registry.register("word_count", description="统计文本字数", text="要统计的文本")
def word_count(text: str) -> dict:
    """统计单词数和字符数"""
    words = text.split()
    return {
        "words": len(words),
        "chars": len(text),
        "chars_no_spaces": len(text.replace(" ", "")),
    }

# 测试
result = registry.call("word_count", text="Hello Mini MCP World")
# {"words": 4, "chars": 21, "chars_no_spaces": 18}
```

**练习建议：**
1. 写一个 `temperature_convert` 工具（摄氏↔华氏）
2. 写一个 `url_parse` 工具（提取协议、域名、路径）
3. 写一个 `text_diff` 工具（比较两段文本的差异）

---

## 架构总览

```
┌──────────────────────────────────────────┐
│            ToolRegistry                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐    │
│  │ Tool:   │ │ Tool:   │ │ Tool:   │    │
│  │ time    │ │ calc    │ │ hash    │    │
│  │ func()  │ │ func()  │ │ func()  │    │
│  │ schema  │ │ schema  │ │ schema  │    │
│  └─────────┘ └─────────┘ └─────────┘    │
│                                          │
│  list_tools()  → [schema, schema, ...]  │
│  call(name)    → result                  │
│  interactive() → REPL                    │
└──────────────────────────────────────────┘
```

## 与真实 MCP 的对比

| 概念 | Mini-MCP | 真实 MCP |
|------|---------|---------|
| 传输层 | Python 函数调用 | JSON-RPC over stdio/SSE |
| 工具发现 | `list_tools()` | `tools/list` 请求 |
| 工具调用 | `call(name, **kwargs)` | `tools/call` 请求 |
| Schema 格式 | Python dict | JSON Schema |
| 进程模型 | 单进程 | 客户端-服务器 |

**核心思想完全相同**：工具是独立可调用的单元，有明确的输入输出契约。

## 下一步

- 阅读 [mini_mcp.py](mini_mcp.py) 源码（仅 ~150 行）
- 尝试用 `@registry.register` 写 3 个自定义工具
- 了解真实 MCP：[modelcontextprotocol.io](https://modelcontextprotocol.io)

---

*Code Lab 产物 · 2026-06-02*
