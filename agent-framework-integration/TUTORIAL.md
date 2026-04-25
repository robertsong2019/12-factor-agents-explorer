# Agent Framework Integration 教程

> 用 CrewAI 和 LangGraph 构建多 Agent 工作流，集成 OpenClaw

---

## 1. 理解两种框架

| 特性 | CrewAI | LangGraph |
|------|--------|-----------|
| 组织方式 | 角色（Role） | 状态图（State Graph） |
| 适合场景 | 团队协作任务 | 有条件分支的复杂流程 |
| 学习曲线 | 低 | 中 |
| 状态管理 | 隐式 | 显式 |

**简单规则：**
- 任务像「团队分工」→ CrewAI
- 任务像「流程图」→ LangGraph
- 需要 OpenClaw 进程管理 → 两者都支持

---

## 2. 安装

```bash
cd ~/.openclaw/workspace/agent-framework-integration
pip install -r requirements.txt
```

核心依赖：`crewai`, `langgraph`, `openclaw`

---

## 3. CrewAI：内容创作流水线

这是最经典的 CrewAI 用例——多个角色协作完成内容。

### 定义团队

```python
from crewai import Agent, Task, Crew

# 定义角色
researcher = Agent(
    role="研究员",
    goal="收集和分析技术信息",
    backstory="你是一名技术研究员，擅长快速找到关键信息",
    verbose=True,
)

writer = Agent(
    role="技术作者",
    goal="把复杂技术写成易懂的文章",
    backstory="你擅长把技术概念解释给非技术人员",
    verbose=True,
)

reviewer = Agent(
    role="审稿人",
    goal="确保文章质量和技术准确性",
    backstory="你是严格的审稿人，关注事实准确和逻辑清晰",
    verbose=True,
)
```

### 定义任务

```python
research_task = Task(
    description="研究 {topic} 的最新进展，总结 3-5 个关键点",
    agent=researcher,
    expected_output="关键点列表，每个包含标题和一段说明",
)

write_task = Task(
    description="基于研究结果，写一篇 500 字的技术博客",
    agent=writer,
    expected_output="Markdown 格式的博客文章",
)

review_task = Task(
    description="审核文章，指出问题并给出修改建议",
    agent=reviewer,
    expected_output="审核意见 + 修改后的最终版本",
)
```

### 执行

```python
crew = Crew(
    agents=[researcher, writer, reviewer],
    tasks=[research_task, write_task, review_task],
    verbose=True,
)

result = crew.kickoff(inputs={"topic": "边缘 AI Agent 框架"})
print(result)
```

---

## 4. LangGraph：客户支持分流

LangGraph 适合有条件判断的工作流。

### 定义状态

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class SupportState(TypedDict):
    message: str
    category: str       # "billing" | "technical" | "general"
    response: str
    resolved: bool
```

### 定义节点

```python
def classify(state: SupportState) -> dict:
    """对用户消息进行分类"""
    msg = state["message"].lower()
    if any(w in msg for w in ["账单", "付款", "退款", "billing"]):
        return {"category": "billing"}
    elif any(w in msg for w in ["错误", "bug", "不能", "technical"]):
        return {"category": "technical"}
    else:
        return {"category": "general"}

def handle_billing(state: SupportState) -> dict:
    return {"response": "账单问题已转交财务团队处理。", "resolved": True}

def handle_technical(state: SupportState) -> dict:
    return {"response": "技术问题已创建工单，工程师将尽快联系您。", "resolved": False}

def handle_general(state: SupportState) -> dict:
    return {"response": "感谢您的反馈！", "resolved": True}
```

### 构建图

```python
def route_by_category(state: SupportState) -> str:
    return state["category"]

graph = StateGraph(SupportState)

# 添加节点
graph.add_node("classify", classify)
graph.add_node("billing", handle_billing)
graph.add_node("technical", handle_technical)
graph.add_node("general", handle_general)

# 设置边
graph.set_entry_point("classify")
graph.add_conditional_edges("classify", route_by_category, {
    "billing": "billing",
    "technical": "technical",
    "general": "general",
})
graph.add_edge("billing", END)
graph.add_edge("technical", END)
graph.add_edge("general", END)

# 编译
app = graph.compile()
```

### 运行

```python
result = app.invoke({
    "message": "我的账单多扣了 50 元",
    "category": "",
    "response": "",
    "resolved": False,
})
print(result)
# {'message': '...', 'category': 'billing', 'response': '账单问题已转交财务团队处理。', 'resolved': True}
```

---

## 5. 集成 OpenClaw

两种框架都可以通过 OpenClaw 生成子 Agent 进程：

```python
from openclaw.adapter import OpenClawSpawner

spawner = OpenClawSpawner()

# CrewAI 中使用
researcher = Agent(
    role="研究员",
    goal="深度研究",
    llm=None,  # 使用 OpenClaw 的模型配置
)

# 或者直接 spawn
task = spawner.spawn(
    task="研究边缘AI的最新进展",
    model="gpt-4",
    tools=["web_search"],
)
result = await task.result()
```

---

## 6. 如何选择

```
你的任务是什么？
│
├─ 多个角色协作完成一件事 → CrewAI
│  例：写文章（研究+写作+审核）
│  例：产品设计（调研+设计+评审）
│
├─ 有明确流程和条件分支 → LangGraph
│  例：客户支持分流
│  例：数据处理流水线
│
└─ 需要长时间运行/进程管理 → OpenClaw + 任意框架
   例：后台研究任务
   例：CI/CD 自动化
```

---

## 7. 运行示例

```bash
# CrewAI 内容流水线
python examples/content_pipeline_crewai.py

# LangGraph 客户支持
python examples/customer_support_langgraph.py
```

---

## 下一步

- 阅读 [FRAMEWORK_COMPARISON.md](FRAMEWORK_COMPARISON.md) 深入对比
- 阅读 [docs/RESEARCH.md](docs/RESEARCH.md) 了解设计决策
- 尝试混合使用：CrewAI 团队中嵌入 LangGraph 子流程
