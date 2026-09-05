# 🧪 Pocket Agent 教程：从零理解 AI Agent

> 30 分钟，零依赖，纯 Python。读完你会理解 Agent 不是魔法——只是循环+工具+记忆。

## 你会学到什么

| 概念 | 在哪一行 | 一句话 |
|------|---------|--------|
| Tool（工具） | `pocket_agent.py` L15-45 | 把 Python 函数包装成 LLM 可调用的 JSON Schema |
| Memory（记忆） | L49-65 | FIFO 短期记忆 + 关键词召回，可替换为向量搜索 |
| ReAct Loop | L95-115 | Reason → Act → Observe 循环，直到给出最终答案 |
| Agent | L79-115 | 把 Tool + Memory + LLM 串起来的编排器 |

## 前置知识

- Python 3.10+（用了 `X | None` 类型语法）
- 知道什么是 JSON
- 不需要机器学习背景

---

## 第一部分：Tool 是怎么注册的

打开 `pocket_agent.py`，看 `ToolRegistry.register()` 方法（约 L19-30）：

```python
def register(self, func: Callable, description: str = ""):
    sig = inspect.signature(func)        # 1. 拿到函数签名
    props, required = {}, []
    for name, param in sig.parameters.items():
        t = param.annotation             # 2. 读取类型注解
        type_map = {str: "string", int: "integer", ...}
        props[name] = {"type": type_map.get(t, "string")}
        if param.default == inspect.Parameter.empty:
            required.append(name)         # 3. 没默认值的 = 必填
    schema = {"type": "object", "properties": props, "required": required}
```

**发生了什么？** Python 的类型注解 → JSON Schema。这样 LLM 就知道"这个工具叫什么、需要什么参数、什么类型"。

### 动手试

```python
from pocket_agent import ToolRegistry

reg = ToolRegistry()

def greet(name: str, formal: bool = False) -> str:
    """Say hello"""
    return f"Hello, {name}!" if not formal else f"Good day, {name}."

reg.register(greet, description="Say hello to someone")
print(reg.list_schemas())
# 输出：[{"type": "function", "function": {"name": "greet", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "formal": {"type": "boolean"}}, "required": ["name"]}}}]
```

### 关键洞察

生产环境的 Agent（LangChain、OpenAI Assistants）做的是**完全一样的事**——只是更复杂。本质都是：**把代码变成 LLM 能理解的 schema**。

---

## 第二部分：ReAct Loop——Agent 的心脏

跳到 `PocketAgent.run()`（约 L95-115）。核心是个 `for` 循环：

```
for i in range(max_iterations):    # 最多跑 5 轮
    response = llm.respond(history)  # 1. 让 LLM 想一想
    
    if 没有 tool_calls:               # 2. LLM 觉得不用工具了
        return 最终回答               #    → 结束
    
    for call in tool_calls:           # 3. 执行工具
        result = registry.execute(name, args)
        history.append(result)        # 4. 把结果喂回去
    # 回到第 1 步，LLM 看到工具结果后再想
```

**为什么要有 max_iterations？** 因为 LLM 可能陷入死循环（反复调同一个工具）。5 次是安全阀。

### 模拟运行

不用运行代码，在脑中走一遍这个例子：

```
用户: "北京今天热吗？"

第1轮:
  LLM: 💭 让我用 get_weather 查一下... [tool_call: get_weather(city="Beijing")]
  执行: {"temp": "22°C", "condition": "sunny"}
  
第2轮:
  LLM: ✅ get_weather 返回结果: 22°C，晴天  ← 没有新 tool_call，结束！

最终回答: "✅ get_weather 返回结果: 22°C，晴天"
```

两轮就结束了。复杂问题可能需要 3-4 轮（比如"查天气+算温度差+翻译成英文"）。

---

## 第三部分：Memory——不只是历史记录

`Memory` 有两种用法：

### 短期记忆（history）

`PocketAgent.history` 是完整的对话历史，每次 `run()` 都会追加。这是 **上下文窗口**——LLM 通过看这个列表来"记住"之前说了什么。

### 长期记忆（Memory）

`Memory` 是独立的存储，agent 在每次工具调用后自动存储关键信息：

```python
self.memory.store(f"Tool {name}({args}) → {result[:100]}")
```

通过 `recall(query)` 可以用关键词匹配找回。生产环境会换成向量搜索（embeddings）。

### 动手试

```python
from pocket_agent import Memory

mem = Memory()
mem.store("今天北京的天气是 22°C 晴天")
mem.store("用户问了 42 * 137 = 5754")
mem.store("系统运行了 3 次 tool calls")

print(mem.recall("天气"))   # ["[HH:MM:SS] 今天北京的天气是 22°C 晴天"]
print(mem.recent(2))        # 最近 2 条
```

---

## 第四部分：连接真实 LLM

`MockLLM` 用 if-else 模拟 LLM 的决策。真实世界只需替换这一个类：

```python
class OpenAILLM:
    def __init__(self, registry, model="gpt-4o-mini"):
        self.registry = registry
        self.model = model

    def respond(self, messages):
        import openai
        resp = openai.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.registry.list_schemas(),  # ← 自动生成的 schema
        )
        msg = resp.choices[0].message
        result = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            result["tool_calls"] = [
                {"name": tc.function.name, 
                 "arguments": json.loads(tc.function.arguments)}
                for tc in msg.tool_calls
            ]
        return result
```

然后一行替换：

```python
agent.llm = OpenAILLM(agent.registry)
```

**其他什么都不用改。** 这就是抽象的威力——MockLLM 和 OpenAILLM 实现同一个接口（`respond(messages) → dict`），Agent 不关心底层是谁。

---

## 第五部分：Self-Evolving Agent（进阶）

`self_evolving_agent.py` 演示了一个更疯狂的概念：**Agent 在运行时动态生成新工具**——启动时它一个工具都没有。

```python
agent = SelfEvolvingAgent()
agent.evolve("fibonacci")    # 运行时生成斐波那契函数并注册
agent.evolve("password_gen") # 运行时生成密码生成器
agent.use("fibonacci", n=42) # ✅ Fibonacci(42) = 267914296
agent.evolve("password_gen") # 再演化一次 → gen 递增
agent.inspect("password_gen")# 把生成的源码读回来看
```

### evolve() 的三步机制

```
spec "make-a-fibonacci"
   │ 1. 归一化：小写、空格/连字符 → 下划线
   ▼
"make_a_fibonacci"
   │ 2. 模板匹配：互相包含即命中（key in spec 或 spec in key）
   ▼
TOOL_TEMPLATES["fibonacci"] ──未命中──→ echo 兜底工具
   │ 3. exec(code, namespace) → 取出同名函数 → 包装成 EvolvingTool
   ▼
EvolvingTool(name, code, func, generation, hash)
```

**原理：** 用 `exec()` 在运行时创建函数，注册到 agent 的工具表。生产环境这是让 Agent 自己写代码来扩展能力的基础模式（类似 OpenAI 的 Code Interpreter）。

### 代码即身份：hash 与 generation

每个工具都有两个可追溯的字段：

- **`hash = md5(code)[:8]`** —— 工具的身份指纹是**它的源码**，不是名字。同一份代码永远算出同一个 hash，改一行代码就换一个身份。这是「代码即数据」世界观的自然推论。
- **`generation`** —— 对同名工具重复 `evolve()` 时递增（0→1→2），记录「这个工具被重新生成过几版」。未来接上 LLM 真正改写代码时，generation 就是演化谱系。

所有演化动作都写进 `agent.history`（evolve/use/hash/时间戳），`status()` 和 `inspect()` 让你随时审计 agent 现在有什么能力、能力从哪来。

### 三个真实 Bug：测试如何抓住自生成代码的问题

这个模块上线时零测试，首轮补测试就抓出 3 个真 bug。它们每一个都是这类模式（运行时 `exec` 生成代码）的**通病**，值得单独记：

**Bug 1：死模板（最隐蔽）。** 有个模板的字典 key 叫 `"base64_encode"`，但模板代码里定义的函数却叫别的名字。`exec()` 成功了、不报错——但 namespace 里根本没有 `base64_encode` 这个函数，查找时要么 `KeyError` 要么静默落到兜底。**教训：在 `exec(code)` 的世界里，「字典 key」和「代码里定义的函数名」是两个没有编译器帮你对齐的东西。**

**Bug 2：坏 spec 直接崩。** 用户传入语法非法的 spec，`exec()` 抛 `SyntaxError` 直接冲出 `evolve()`。修复：捕获后返回 `"❌ Failed to evolve ..."` 错误消息。**教训：面向不可信输入的代码生成器，崩溃不是可接受的失败模式——返回结构化错误才是。**

**Bug 3：空 spec 的子串怪癖。** 空 spec 能穿过模板匹配逻辑落到意外分支。修复：`evolve()` 入口显式拒绝空 spec。**教训：归一化+匹配这种「宽松匹配」设计，必须对退化输入（空串、纯符号）单独想一遍。**

### 模板完整性测试：一个便宜的守卫

Bug 1 的修复不只是改名，而是加了一条参数化测试，**对每个模板 key 断言其代码里定义了同名函数**：

```python
@pytest.mark.parametrize("key", list(EvolutionEngine.TOOL_TEMPLATES))
def test_template_defines_its_own_key(self, key):
    namespace = {"json": json}
    exec(EvolutionEngine.TOOL_TEMPLATES[key], namespace)  # 跟生产同一条路径
    assert key in namespace, f"模板 {key} 没有定义同名函数 → 死模板"
```

以后任何人加新模板，忘了对齐 key 和函数名，测试在 CI 就红了——**这类 bug 不可能再活到运行时**。这就是「结构守卫」模式：不测行为，测「代码结构自洽」本身。

当前测试快照：**58 tests**（`pytest test_pocket_agent.py test_self_evolving_agent.py`），覆盖模板值校验（fibonacci 数值、质数判定、JSON 形状）、spec 匹配边界、再演化 generation 递增、坏输入鲁棒性（永远返回错误消息而非抛异常）。

### ⚠️ 安全提醒

`exec()` 执行任意代码是危险的。生产环境需要：
- 沙箱执行（Docker/WASM）
- 代码审查（LLM 生成 → 人类确认 → 执行）
- 权限限制（文件系统、网络访问）

---

## 学习路径

```
你现在在这里 ↓

pocket_agent.py        → 理解 Agent 基础（工具 + 循环 + 记忆）
    ↓
self_evolving_agent.py → Agent 动态扩展自己的能力
    ↓
连接真实 LLM           → 把 MockLLM 换成 OpenAI/Anthropic
    ↓
向量记忆               → 把关键词匹配换成 embedding 搜索
    ↓
生产框架               → LangChain、CrewAI、AutoGen（同一原理，更多工程）
```

## 延伸阅读

- [ReAct 论文](https://arxiv.org/abs/2210.03629) — Reason+Act 范式的原始论文
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling) — 生产级 Tool Schema 规范
- [MCP 协议](https://modelcontextprotocol.io/) — Anthropic 的通用工具调用标准

---

*有问题？直接看代码——两个模块各约 220 行，每行都有注释。最好的教程就是源码本身。*
