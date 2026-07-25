# API 参考 🧪

> Nano-Agent 框架的完整 API 文档

---

## 目录

- [Agent](#agent)
- [Tool 装饰器](#tool-装饰器)
- [Tool 类](#tool-类)
- [全局工具函数](#全局工具函数)
- [Memory](#memory)
  - [基础操作](#基础操作)
  - [重要度与遗忘 (F5-F8)](#重要度与遗忘-f5-f8)
  - [标签管理 (F4, F13, F15-F16, F18)](#标签管理)
  - [序列化与持久化 (F1-F2, F31, F40, F43)](#序列化与持久化)
  - [搜索与过滤 (F17, F21, F23-F25, F38)](#搜索与过滤)
  - [集合运算 (F14, F27-F28, F44-F45)](#集合运算)
  - [分析与统计 (F3, F29-F35, F37, F39, F41-F42)](#分析与统计)
  - [快照与格式化 (F22, F26, F33, F46)](#快照与格式化)
- [MemoryEntry](#memoryentry)
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

| 参数 | 类型 | 说明 |
|------|------|------|
| `user_input` | `str` | 用户输入文本 |
| `context` | `Optional[str]` | 附加上下文，会被注入系统提示 |

**返回：** `str` — 代理的最终文本响应

#### `run_batch(inputs, context=None)`  *(F9)*

批量处理多个输入，依次执行 `run()` 并收集结果。单个输入失败不影响后续。

```python
results = agent.run_batch(["你好", "搜索AI新闻", "总结一下"])
for r in results:
    print(r["success"], r["response"])
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `inputs` | `List[str]` | 用户输入列表 |
| `context` | `Optional[str]` | 所有输入共享的附加上下文 |

**返回：** `List[Dict[str, Any]]`，每项包含：

| 键 | 说明 |
|----|------|
| `input` | 原始输入 |
| `response` | 代理回复（失败时为 None） |
| `success` | 是否成功 |
| `error` | 错误信息（成功时为 None） |

#### `summary()`  *(F10)*

生成对话历史的摘要信息。

```python
s = agent.summary()
print(f"{s['agent_name']}: {s['turn_count']}轮, {s['total_messages']}条消息")
```

**返回：** `Dict[str, Any]`

| 键 | 类型 | 说明 |
|----|------|------|
| `agent_name` | `str` | 代理名称 |
| `turn_count` | `int` | 用户发言轮次 |
| `total_messages` | `int` | 总消息数 |
| `user_messages` | `int` | 用户消息数 |
| `assistant_messages` | `int` | 助手消息数 |
| `total_chars` | `int` | 总字符数 |
| `tool_count` | `int` | 工具数量 |
| `memory_count` | `int` | 记忆条目数 |
| `recent` | `List[Dict]` | 最近 6 条消息预览 |

#### `conversation_stats()`  *(F36)*

返回当前对话的详细统计信息。

```python
stats = agent.conversation_stats()
# {"total_messages": 10, "by_role": {"user": 5, "assistant": 5},
#  "avg_length": 120.5, "tool_calls": 3, "est_tokens": 1500}
```

| 键 | 类型 | 说明 |
|----|------|------|
| `total_messages` | `int` | 消息总数 |
| `by_role` | `Dict[str, int]` | 按角色统计的消息数 |
| `avg_length` | `float` | 平均消息长度（字符） |
| `tool_calls` | `int` | 工具调用次数 |
| `est_tokens` | `int` | 预估 token 数（总字符数 / 4） |

#### `add_tool(tool)`  *(F19)*

运行时动态添加工具。如果同名工具已存在则替换。

```python
agent.add_tool(new_tool)
```

#### `remove_tool(name)`  *(F19)*

按名称移除工具。

```python
ok = agent.remove_tool("search")  # → True
```

**返回：** `bool` — 找到并移除返回 `True`

#### `reset()`

清除对话历史。

```python
agent.reset()  # 清空本次会话的对话记录
```

> 注意：`reset()` 只清空对话历史，不清空 Memory 中的长期记忆。

#### `history(limit=10)`

获取对话历史，返回最近 `limit` 条消息（包含 user 和 assistant）。

```python
msgs = agent.history(limit=5)
for m in msgs:
    print(f"{m['role']}: {m['content'][:50]}")
```

#### `turn_count` (property)

返回当前对话的用户轮次数（即用户发言次数）。

```python
print(f"已对话 {agent.turn_count} 轮")
```

#### `on_step` (callback)

可选的回调函数，每轮迭代结束时调用。接收一个字典参数：

```python
def on_step_callback(info):
    print(f"第{info['iteration']}轮，工具: {info['tool_calls']}")

agent.on_step = on_step_callback
agent.run("搜索AI新闻")
# 输出: 第1轮，工具: ['search']
```

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
    # {"query": {"type": "string"}, "max_results": {"type": "integer", "default": 10}}
    ...
```

**类型推断映射表：**

| Python 类型 | 工具参数类型 |
|-------------|-------------|
| `str` | `string` |
| `int` | `integer` |
| `float` | `number` |
| `bool` | `boolean` |
| `list` | `array` |
| `dict` | `object` |
| 其他 | `string`（兜底） |

> 💡 无类型注解的参数默认为 `string`。建议始终添加类型注解以获得精确的类型映射。

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

#### `validate_args(**kwargs)`

验证参数是否满足必填要求，返回错误列表（空列表=验证通过）。

```python
errors = my_tool.validate_args(query="test")
if errors:
    print(errors)  # ["缺少必要参数: query"]
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
| `unregister_tool(name)` | 注销指定工具，返回是否成功 |
| `list_tools_by_prefix(prefix)`  *(F12)* | 按名称前缀过滤已注册工具列表 |

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

### 基础操作

#### `add(content, metadata=None, tags=None, importance=0.5)`

添加一条记忆。

```python
memory.add("用户偏好中文回复", metadata={"type": "preference"})
memory.add("API 密钥已轮换", tags=["security", "config"])
memory.add("关键决策", importance=0.9)  # 高重要度
```

#### `search(query, limit=5, tags=None)`

关键词搜索记忆（不区分大小写），支持按标签过滤。

```python
results = memory.search("用户偏好", limit=3)
# 返回 List[MemoryEntry]

# 按标签过滤
sec_results = memory.search("密钥", tags=["security"])
```

#### `get_recent(n=5)`

获取最近 n 条记忆。

```python
recent = memory.get_recent(10)
```

#### `get_all()`

获取所有记忆的副本。

#### `count()`

返回当前记忆条目数。

```python
print(f"共 {memory.count()} 条记忆")
```

#### `remove(index)`

按索引删除一条记忆，返回是否成功。

```python
ok = memory.remove(0)  # 删除第一条
```

#### `update(index, content, metadata=None)`

按索引更新记忆内容和元数据（时间戳自动更新），返回是否成功。

```python
memory.update(0, "新内容", metadata={"edited": True})
```

#### `clear()`

清空所有记忆并删除持久化文件内容。

#### `export_json()`  *(F1)*

将所有记忆序列化为 JSON 字符串，用于备份或迁移。

```python
json_str = memory.export_json()
# '[{"content": "...", "timestamp": "2026-06-24T...", "metadata": {}, "tags": []}]'
```

**返回：** `str` — JSON 格式的记忆数组

#### `import_json(data, merge=True)`  *(F2)*

从 JSON 字符串导入记忆，返回成功导入的条目数。

```python
# 从备份恢复
count = memory.import_json(json_str)
print(f"恢复了 {count} 条记忆")

# 覆盖导入（清除现有记忆后导入）
count = memory.import_json(json_str, merge=False)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `data` | `str` | 必填 | `export_json()` 生成的 JSON 字符串 |
| `merge` | `bool` | `True` | `True`=追加，`False`=先清空再导入 |

**返回：** `int` — 成功导入的条目数（格式错误的条目会被跳过）

#### `stats()`  *(F3)*

返回记忆统计信息：总数、标签分布、时间范围。

```python
s = memory.stats()
print(s)
# {
#   "total": 42,
#   "tags": {"security": 5, "config": 3, "task": 20},
#   "date_range": {"oldest": "2026-01-01T...", "newest": "2026-06-24T..."}
# }
```

**返回：** `Dict[str, Any]` — 空 Memory 时返回 `{"total": 0, "tags": {}, "date_range": None}`

#### `add_tag(index, tag)`  *(F4)*

给指定索引的记忆添加标签（去重，已存在则不重复添加）。

```python
memory.add_tag(0, "important")  # 给第一条记忆加标签
```

**返回：** `bool` — 索引有效返回 `True`，越界返回 `False`

#### `remove_tag(index, tag)`  *(F4)*

从指定索引的记忆移除标签。

```python
memory.remove_tag(0, "draft")  # 移除标签
```

**返回：** `bool` — 索引有效返回 `True`，越界返回 `False`

### 重要度与遗忘

#### `set_importance(index, score)`  *(F5)*

设置指定记忆的重要度分数（自动 clamp 到 0.0-1.0）。

```python
memory.add("关键决策", importance=0.9)
memory.set_importance(0, 1.0)  # 提升到最高
memory.set_importance(0, 1.5)  # 自动 clamp 为 1.0
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `index` | `int` | 记忆索引（基于 `get_all()` 的顺序） |
| `score` | `float` | 重要度分数，范围 0.0-1.0，超出范围自动 clamp |

**返回：** `bool` — 索引有效返回 `True`，越界返回 `False`

---

#### `importance_decay(factor=0.95)`  *(F6)*

对所有记忆应用衰减因子（importance *= factor），模拟时间流逝导致的遗忘。

```python
# 每次调用将所有记忆重要度乘以 0.95
affected = memory.importance_decay(0.95)
print(f"{affected} 条记忆已衰减")

# 衰减后低重要度的记忆可以用 forget() 清理
removed = memory.forget(threshold=0.1)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `factor` | `float` | `0.95` | 衰减因子，必须在 (0, 1) 范围内 |

**返回：** `int` — 受影响的记忆条目数（factor 无效时返回 0）

---

#### `forget(threshold=0.1)`  *(F7)*

删除重要度低于阈值的记忆，实现自动遗忘。

```python
# 删除重要度低于 0.1 的记忆
removed = memory.forget(threshold=0.1)
print(f"清理了 {removed} 条低价值记忆")

# 更激进的清理
removed = memory.forget(threshold=0.3)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `threshold` | `float` | `0.1` | 重要度低于此值的记忆将被删除 |

**返回：** `int` — 被删除的记忆条目数

---

#### `top_important(n=5)`  *(F8)*

按重要度降序返回前 n 条记忆。

```python
# 查看最重要的 5 条记忆
top5 = memory.top_important(5)
for entry in top5:
    print(f"[{entry.importance:.2f}] {entry.content}")
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `n` | `int` | `5` | 返回的条目数 |

**返回：** `List[MemoryEntry]` — 按重要度从高到低排列

---

#### `to_context(max_tokens=1000)`

将近期记忆格式化为可注入提示的文本。

```python
context_str = memory.to_context(max_tokens=500)
# "## 记忆\n- 2024-01-10 14:30: 用户偏好中文回复\n- ..."
```

---

### 标签管理

#### `add_tag(index, tag)` / `remove_tag(index, tag)`  *(F4)*

> 见上方基础操作章节。

#### `search_by_tag(tag, limit=0)`  *(F13)*

返回带有指定标签的所有记忆，按时间排序。

```python
results = memory.search_by_tag("security")
results = memory.search_by_tag("bug", limit=5)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tag` | `str` | 必填 | 要搜索的标签 |
| `limit` | `int` | `0` | 返回上限，0 = 全部 |

**返回：** `List[MemoryEntry]`

#### `search_all_tags(tags, limit=0)`  *(F15)*

返回同时包含**所有**指定标签的记忆（AND 语义）。

```python
# 必须同时有 "security" 和 "critical" 标签
results = memory.search_all_tags(["security", "critical"])
```

#### `distinct_tags()`  *(F16)*

返回所有出现过的标签，按字母排序。

```python
all_tags = memory.distinct_tags()
# ["bug", "config", "security", ...]
```

**返回：** `List[str]`

#### `group_by_tag()`  *(F18)*

按标签分组记忆，返回 `tag → entries` 映射。没有标签的记忆归入 `"_untagged"`。

```python
groups = memory.group_by_tag()
for tag, entries in groups.items():
    print(f"{tag}: {len(entries)} 条")
```

**返回：** `Dict[str, List[MemoryEntry]]`

#### `auto_tag(rules, overwrite=False)`  *(F39)*

基于关键词规则自动打标签。

```python
rules = {
    "bug": ["error", "crash", "fail", "exception"],
    "feature": ["add", "implement", "create", "new"],
    "security": ["vulnerability", "cve", "exploit"],
}
tagged = memory.auto_tag(rules)
print(f"{tagged} 条记忆被自动标记")
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `rules` | `Dict[str, List[str]]` | 必填 | 标签名 → 关键词列表 |
| `overwrite` | `bool` | `False` | `True` = 替换现有标签，`False` = 追加 |

**返回：** `int` — 至少获得一个新标签的条目数

#### `normalize_tags(mapping)`  *(F41)*

批量重命名/合并标签，自动去重。

```python
# 将 "bugs" 和 "defect" 都统一为 "issue"
changed = memory.normalize_tags({"bugs": "issue", "defect": "issue"})
```

**返回：** `int` — 标签列表发生变化的条目数

#### `tag_cloud(min_count=1, max_tags=50)`  *(F37)*

生成归一化的标签云（权重 0-1，基于频率）。

```python
cloud = memory.tag_cloud(min_count=2, max_tags=20)
# {"security": 1.0, "bug": 0.8, "config": 0.4}
```

**返回：** `Dict[str, float]` — 标签名 → 权重（最高频标签 = 1.0）

---

### 序列化与持久化

#### `export_json()` / `import_json(data, merge=True)`  *(F1-F2)*

> 见上方基础操作章节。

#### `export_markdown(tags=None)`  *(F31)*

导出为 Markdown 文档，含目录和条目详情。

```python
md = memory.export_markdown(tags=["security"])
with open("memory_export.md", "w") as f:
    f.write(md)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tags` | `Optional[List[str]]` | `None` | 仅导出包含任一指定标签的条目 |

**返回：** `str` — Markdown 格式文档

#### `export_csv(tags=None)`  *(F31)*

导出为 CSV 格式。列：`index,timestamp,importance,tags,content,metadata`。

```python
csv_str = memory.export_csv()
```

#### `export_jsonl(tags=None)`  *(F40)*

导出为 JSON Lines 格式（每行一个 JSON 对象），适合流式管道和 ML 数据加载。

```python
jsonl = memory.export_jsonl()
# '{"content": "...", "importance": 0.9, ...}\n{"content": "...", ...}'
```

#### `import_jsonl(data, merge=True)`  *(F43)*

从 JSON Lines 字符串导入记忆（`export_jsonl` 的逆操作）。

```python
# 从流式管道恢复
count = memory.import_jsonl(jsonl_data)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `data` | `str` | 必填 | JSONL 字符串 |
| `merge` | `bool` | `True` | `True` = 追加，`False` = 替换 |

**返回：** `int` — 成功导入的条目数

---

### 搜索与过滤

#### `search_fuzzy(query, threshold=0.3, limit=5)`  *(F17)*

使用 difflib SequenceMatcher 进行模糊搜索。当精确搜索无结果时，可用此方法找到内容相近的记忆。

```python
results = memory.search_fuzzy("用户喜好", threshold=0.25)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | `str` | 必填 | 搜索查询 |
| `threshold` | `float` | `0.3` | 相似度阈值 (0.0-1.0) |
| `limit` | `int` | `5` | 返回上限，≤0 = 全部 |

**返回：** `List[MemoryEntry]` — 按相似度降序排列

#### `search_regex(pattern, limit=0)`  *(F23)*

正则表达式搜索（不区分大小写）。

```python
results = memory.search_regex(r"\d{4}-\d{2}-\d{2}")  # 匹配日期
results = memory.search_regex(r"(error|warning|critical)", limit=10)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `pattern` | `str` | 正则表达式模式 |
| `limit` | `int` | 返回上限，0 = 全部 |

**返回：** `List[MemoryEntry]` — 按时间排序

#### `weighted_search(query, limit=5, w_content=0.5, w_importance=0.3, w_recency=0.2)`  *(F25)*

多因子加权搜索，综合内容相似度、重要度和时间近度。

```python
# 侧重重要度
results = memory.weighted_search("API", w_content=0.3, w_importance=0.5, w_recency=0.2)
```

三个因子归一化到 [0, 1] 后按权重加权求和：
- **content** — SequenceMatcher 相似度（子串匹配 ≥ 0.8）
- **importance** — `entry.importance`（已是 0-1）
- **recency** — 线性衰减（最新 = 1.0，最旧 = 0.0）

**返回：** `List[MemoryEntry]` — 按综合得分降序排列

#### `search_in_fields(query, fields, limit=5)`  *(F38)*

在指定字段内搜索，按匹配字段数排序。

```python
# 在 content 和 tags 中搜索
results = memory.search_in_fields("API", ["content", "tags"], limit=10)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `query` | `str` | 搜索文本 |
| `fields` | `List[str]` | 搜索字段：`"content"`、`"tags"`、`"metadata"` |
| `limit` | `int` | 返回上限，0 = 全部 |

#### `chain_search(queries, limit=0, fuzzy=False, threshold=0.3)`  *(F21)*

多查询链式搜索，合并去重后按匹配查询数降序排列。

```python
results = memory.chain_search(["API", "接口", "endpoint"], fuzzy=True)
# 匹配多个查询的条目排名更高
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `queries` | `List[str]` | 必填 | 搜索查询列表 |
| `fuzzy` | `bool` | `False` | 是否启用模糊匹配 |
| `threshold` | `float` | `0.3` | 模糊匹配阈值 |
| `limit` | `int` | `0` | 返回上限，0 = 全部 |

#### `filter(predicate)`  *(F24)*

函数式过滤：传入回调函数，返回满足条件的所有记忆。

```python
# 所有重要度 > 0.7 的记忆
important = memory.filter(lambda e: e.importance > 0.7)

# 所有带 "urgent" 标签的记忆
urgent = memory.filter(lambda e: "urgent" in e.tags)
```

**返回：** `List[MemoryEntry]`

---

### 集合运算

#### `merge(other)`  *(F14)*

将另一个 Memory 合并到当前实例，基于 content 去重。

```python
other = Memory()
other.add("额外的记忆")
added = memory.merge(other)
print(f"新增 {added} 条")
```

**返回：** `int` — 实际新增的条目数（超出 `max_entries` 会截断）

#### `union(other)`  *(F44)*

返回两个 Memory 的并集（新实例）。基于 content 去重，保留 `self` 的条目。

```python
combined = memory1.union(memory2)
```

**返回：** `Memory` — 新的 Memory 实例

#### `intersect(other)`  *(F28)*

返回两个 Memory 共有的记忆（按 content 匹配）。

```python
common = memory1.intersect(memory2)
```

**返回：** `List[MemoryEntry]`

#### `subtract(other)`  *(F45)*

返回 `self` 中不存在于 `other` 的记忆（差集）。

```python
unique = memory1.subtract(memory2)
```

**返回：** `Memory` — 新的 Memory 实例

#### `diff(other)`  *(F27)*

双向差异比较，返回三个列表。

```python
d = memory1.diff(memory2)
print(f"新增: {len(d['added'])}, 删除: {len(d['removed'])}, 共同: {len(d['common'])}")
```

**返回：** `Dict[str, List[MemoryEntry]]`

| 键 | 说明 |
|----|------|
| `added` | `other` 有但 `self` 没有的 |
| `removed` | `self` 有但 `other` 没有的 |
| `common` | 两边都有的 |

---

### 分析与统计

#### `stats()`  *(F3)*

> 见上方基础操作章节。

#### `sample(n=5, weighted=True)`  *(F29)*

随机采样 n 条记忆，可选按重要度加权。

```python
# 按重要度加权采样
sampled = memory.sample(10, weighted=True)

# 均匀随机采样
sampled = memory.sample(10, weighted=False)
```

**返回：** `List[MemoryEntry]`

#### `timeline(bucket="day")`  *(F30)*

按时间桶聚合记忆数量。

```python
# 按天统计
daily = memory.timeline("day")
# {"2026-07-01": 5, "2026-07-02": 12, ...}

# 按小时
hourly = memory.timeline("hour")
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `bucket` | `str` | `"day"` | `"hour"` / `"day"` / `"week"` / `"month"` |

**返回：** `Dict[str, int]` — 按时间正序

#### `cluster(threshold=0.5, limit=0)`  *(F32)*

贪婪相似度聚类，使用 SequenceMatcher。

```python
clusters = memory.cluster(threshold=0.6)
for cluster_id, entries in clusters.items():
    print(f"Cluster {cluster_id}: {len(entries)} 条")
```

**返回：** `Dict[int, List[MemoryEntry]]` — 聚类 ID 到条目列表

#### `histogram(bins=10)`  *(F34)*

重要度分布直方图。

```python
hist = memory.histogram(bins=5)
print(hist["labels"])  # ['0.0-0.2', '0.2-0.4', '0.4-0.6', '0.6-0.8', '0.8-1.0']
print(hist["counts"])  # [3, 5, 12, 8, 2]
```

**返回：** `Dict[str, Any]` — 含 `bin_edges`、`counts`、`labels`、`max_bin`

#### `correlation_stats()`  *(F35)*

计算重要度与内容长度的 Pearson 相关系数，以及每个标签的平均重要度。

```python
stats = memory.correlation_stats()
print(f"重要度-长度相关系数: {stats['importance_length_r']:.3f}")
# r > 0 表示越长的重要度越高，r < 0 则相反
```

**返回：** `Dict[str, Any]` — 含 `importance_length_r`、`tag_count`、`avg_importance_per_tag`、`total_chars`

#### `entropy()`  *(F42)*

计算 Shannon 熵作为记忆多样性指标。高熵 = 内容多样化，低熵 = 重复。

```python
ent = memory.entropy()
print(f"内容熵: {ent['content_entropy']:.2f} bits")
print(f"标签熵: {ent['tag_entropy']:.2f} bits")
```

**返回：** `Dict[str, Any]`

| 键 | 说明 |
|----|------|
| `content_entropy` | 内容多样性（按精确内容匹配） |
| `tag_entropy` | 标签多样性 |
| `unique_contents` | 唯一内容数 |
| `unique_tags` | 唯一标签数 |
| `total_entries` | 总条目数 |

#### `deduplicate(threshold=0.95)`  *(F20)*

移除内容相似度 ≥ 阈值的重复记忆，保留最早添加的。

```python
removed = memory.deduplicate(threshold=0.9)
print(f"清理了 {removed} 条重复记忆")
```

**返回：** `int` — 被移除的条目数

---

### 快照与格式化

#### `snapshot()`  *(F22)*

创建当前记忆的深拷贝快照，用于 undo/restore。

```python
snap = memory.snapshot()
# 后续可以用 memory.restore(snap) 恢复
```

**返回：** `List[Dict[str, Any]]` — 可序列化的快照数据

#### `restore(snapshot_data)`  *(F22)*

从快照恢复记忆状态（完全替换当前所有记忆）。

```python
memory.restore(snap)
```

**返回：** `int` — 恢复的条目数

#### `paginate(page=1, page_size=10, order="asc")`  *(F26)*

分页获取记忆条目。

```python
result = memory.paginate(page=2, page_size=20, order="desc")
for entry in result["entries"]:
    print(entry.content)
print(f"第 {result['page']}/{result['total_pages']} 页")
```

**返回：** `Dict[str, Any]`

| 键 | 说明 |
|----|------|
| `entries` | 当前页的 `List[MemoryEntry]` |
| `page` | 当前页码 |
| `page_size` | 每页条目数 |
| `total` | 总条目数 |
| `total_pages` | 总页数 |

#### `compact_summary(max_entries=5)`  *(F33)*

生成紧凑摘要，包含 Top-N 重要条目、标签分布和时间跨度。

```python
summary = memory.compact_summary(max_entries=10)
# {"total": 42, "top_entries": [...], "tag_distribution": {...}, "time_span": {...}}
```

**返回：** `Dict[str, Any]` — 含 `total`、`top_entries`、`tag_distribution`、`time_span`

#### `to_prompt(include_metadata=True, include_tags=True, max_entries=20)`  *(F46)*

格式化为结构化 LLM Prompt 块。按重要度降序排列，包含分数、标签和元数据。与 `to_context()` 不同，此方法生成更丰富的结构化格式，适合注入系统提示。

```python
prompt_block = memory.to_prompt(include_tags=True, max_entries=10)
system_prompt = f"""你是一个助手。

{prompt_block}
"""
```

**返回：** `str` — 格式化的 Prompt 文本

---

### MemoryEntry

记忆条目数据类。

| 属性 | 类型 | 说明 |
|------|------|------|
| `content` | `str` | 记忆内容 |
| `timestamp` | `datetime` | 创建时间 |
| `metadata` | `Dict[str, Any]` | 附加元数据 |
| `tags` | `List[str]` | 标签列表（用于过滤） |
| `importance` | `float` | 重要度分数（0.0-1.0，默认 0.5） |

**方法：**

| 方法 | 说明 |
|------|------|
| `to_dict()` | 序列化为字典（不含空 tags） |
| `__eq__(other)` | 按 content 比较相等性 |

### 持久化

设置 `persistence_path` 后，记忆会自动保存到 JSON 文件：

```python
memory = Memory(persistence_path="data/memory.json")
# 每次 add/clear 自动读写文件
# 文件格式: [{"content": "...", "timestamp": "...", "metadata": {...}, "tags": [...], "importance": 0.5}, ...]
```

> 💡 **向后兼容**：旧版持久化文件（无 `importance` 字段）加载时自动使用默认值 0.5。

### 重要度与遗忘机制 (F5-F8)

Nano-Agent 的记忆系统支持基于重要度的遗忘机制，模拟人类记忆的衰减过程：

```python
from nano_agent import Memory

memory = Memory(persistence_path="data/mem.json")

# 1. 标记重要记忆
memory.add("项目上线日期: 2026-07-01", importance=0.9)
memory.add("随手记的笔记", importance=0.2)

# 2. 模拟时间衰减（每次调用所有记忆 importance *= 0.95）
memory.importance_decay(factor=0.95)

# 3. 清理低价值记忆
removed = memory.forget(threshold=0.1)

# 4. 查看最重要的记忆
top = memory.top_important(5)

# 5. 统计信息包含平均重要度
stats = memory.stats()
print(f"平均重要度: {stats['avg_importance']}")
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
