# Nano-Agent Framework 🧪

> 超轻量级 AI Agent 框架，专为快速原型和边缘计算设计

## ✨ 特性

- **极简架构** - 核心 <500 行代码，易于理解和定制
- **模块化设计** - 可插拔的 LLM 后端、工具、记忆系统
- **嵌入式友好** - 最小化依赖，支持受限环境
- **可视化追踪** - 清晰的执行路径和状态管理
- **快速原型** - 5 分钟启动一个完整代理

## 🚀 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 创建你的第一个代理

```python
from nano_agent import Agent, tool

@tool
def search(query: str) -> str:
    """搜索网络获取信息"""
    # 实现你的搜索逻辑
    return f"搜索 '{query}' 的结果..."

agent = Agent(
    name="助手",
    instructions="你是一个有帮助的助手",
    tools=[search]
)

response = agent.run("帮我搜索 AI 最新发展")
print(response)
```

## 📁 项目结构

```
nano-agent/
├── src/
│   └── nano_agent/
│       ├── __init__.py
│       ├── agent.py      # 核心代理类
│       ├── tools.py      # 工具系统
│       ├── memory.py     # 记忆管理
│       └── llm.py        # LLM 接口
├── examples/
│   ├── planner.py        # 任务规划代理
│   ├── coder.py          # 代码生成代理
│   └── researcher.py     # 研究助理代理
├── tests/
└── README.md
```

## 🎯 设计理念

### 1. 极简主义
- 代码行数最小化
- 依赖最小化
- 认知负担最小化

### 2. 可组合性
- 每个组件独立可测
- 支持任意组合和扩展
- 清晰的接口定义

### 3. 可观测性
- 每个步骤都可追踪
- 状态变化可见
- 调试友好

### 4. 资源感知
- 支持受限环境
- 内存使用可控
- 延迟可预测

## 🔧 核心组件

### Agent
代理的核心类，负责：
- 推理和决策
- 工具调用
- 记忆管理
- 状态追踪

### Tool
工具系统，支持：
- 装饰器式注册
- 类型安全
- 自动文档生成

### Memory
记忆管理，支持：
- 短期记忆（会话级）
- 长期记忆（持久化）
- 记忆检索和过滤

### LLM
统一的大语言模型接口，支持：
- OpenAI GPT 系列
- Anthropic Claude
- 本地模型（通过 OpenAI 兼容 API）

## 📖 示例

### 任务规划代理
```python
# examples/planner.py
from nano_agent import Agent, tool
import json

@tool
def create_task(description: str, priority: str = "medium") -> str:
    """创建一个新任务"""
    task = {"description": description, "priority": priority, "status": "pending"}
    return json.dumps(task, ensure_ascii=False)

planner = Agent(
    name="任务规划师",
    instructions="帮助用户规划和分解任务",
    tools=[create_task]
)

result = planner.run("帮我规划一个项目：开发一个 AI 聊天机器人")
print(result)
```

### 研究助理代理
```python
# examples/researcher.py
from nano_agent import Agent, tool

@tool
def search_papers(topic: str) -> str:
    """搜索相关论文"""
    # 实现论文搜索
    return f"找到 5 篇关于 {topic} 的论文..."

@tool
def summarize_paper(paper_id: str) -> str:
    """总结论文内容"""
    # 实现论文总结
    return f"论文 {paper_id} 的摘要..."

researcher = Agent(
    name="研究助理",
    instructions="帮助用户研究和总结学术资料",
    tools=[search_papers, summarize_paper]
)
```

## 🎨 应用场景

- **嵌入式设备** - 边缘设备上的智能决策
- **IoT 系统** - 智能传感器和执行器
- **快速原型** - 概念验证和实验
- **教育学习** - 理解 AI Agent 原理
- **微服务** - 轻量级的 AI 能力

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📖 API 参考

### `Agent`

```python
Agent(
    name: str,                    # 代理名称
    instructions: str,            # 系统指令
    llm: Optional[LLMBackend],    # LLM 后端，默认 MockBackend
    tools: Optional[List[Tool]],  # 可用工具列表
    memory: Optional[Memory],     # 记忆管理器
    max_iterations: int = 10,     # 最大迭代轮数
    verbose: bool = True          # 是否打印执行过程
)
```

**核心方法：**
- `run(user_input, context=None)` → `str` — 运行代理，返回最终响应

### `@tool` 装饰器

```python
@tool                                    # 自动从函数名和 docstring 推断
@tool(name="...", description="...")      # 自定义名称和描述
def my_function(param: str) -> str:
    """工具描述（给 LLM 看）"""
    return result
```

### `Memory`

```python
Memory(max_entries=100, persistence_path=None)
```
- `add(content, metadata)` — 添加记忆
- `search(query, limit=5)` — 关键词搜索
- `get_recent(n=5)` — 最近 n 条
- `clear()` — 清空

### `LLMBackend`

```python
OpenAIBackend(api_key, base_url="...", model="gpt-3.5-turbo")
```
继承 `LLMBackend` 实现自定义后端，只需实现 `complete(messages, tools)` 方法。

---

## 📚 更多文档

- [教程 — 5 分钟上手](TUTORIAL.md) — 从 Hello Agent 到实战研究助理

---

## 📄 许可证

MIT License

## 🙏 致谢

灵感来源于：
- SmolAgents (极简主义)
- AutoGen (多代理协作)
- CrewAI (基于角色的设计)

---

**Nano-Agent** - 让 AI Agent 开发变得简单有趣 🎉
