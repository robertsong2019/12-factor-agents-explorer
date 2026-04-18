# Agent Memory Graph 教程

> 从零开始：用知识图谱管理 AI Agent 的记忆

## 🎯 你将学到什么

- 知识图谱如何表达 Agent 记忆
- 记忆衰减与恢复机制
- 关联遍历发现上下文
- 用 Python 标准库构建完整记忆系统

## 📋 前置条件

- Python 3.10+
- **零依赖** — 仅用标准库（sqlite3 + json + math）

## 第 1 步：运行演示

```bash
python memory_graph.py
```

你会看到：
1. 记忆网络的 ASCII 可视化
2. 关键词召回演示
3. 关联记忆遍历
4. 7 天遗忘衰减模拟

## 第 2 步：创建记忆图谱

```python
from memory_graph import MemoryGraph

# 内存数据库（适合测试）
mg = MemoryGraph()

# 持久化到文件（适合生产）
mg = MemoryGraph("agent_memory.db")
```

所有数据存储在 SQLite 中，无需额外服务。

## 第 3 步：添加记忆节点

记忆节点有 5 种类型，代表不同性质的信息：

```python
# 人物
user = mg.add("罗嵩", "person", {"timezone": "Asia/Shanghai", "role": "developer"})

# 概念
agent = mg.add("AI Agent", "concept", {"definition": "自主执行任务的AI系统"})

# 事实
fact = mg.add("Python 是动态类型语言", "fact")

# 事件
event = mg.add("完成了 API 重构", "event", {"duration_hours": 4})

# 技能
skill = mg.add("Python 快速原型", "skill")
```

### 如何选择节点类型？

| 类型 | 什么时候用 | 例子 |
|------|-----------|------|
| `fact` | 客观事实、知识点 | "React 是 Meta 开发的" |
| `event` | 发生了的事 | "今天部署了 v2.0" |
| `person` | 人物信息 | "张三是后端工程师" |
| `concept` | 想法、概念、主题 | "微服务架构" |
| `skill` | 能力标签 | "Docker 容器编排" |

## 第 4 步：建立关联

节点之间的关联让记忆不再是孤立的：

```python
# 建立关系
mg.link(user.id, agent.id, "building")
mg.link(user.id, skill.id, "skilled_in")
mg.link(event.id, agent.id, "about")
```

关系类型是自由文本，根据你的场景定义：

```python
# 常见关系类型
"works_on"      # 正在做
"interested_in"  # 感兴趣
"caused"         # 因果
"related_to"     # 相关
"learned"        # 学到了
"prefers"        # 偏好
```

## 第 5 步：召回记忆

### 关键词召回

```python
results = mg.recall("Python")
for r in results:
    print(f"{r.label} (强度={r.weight:.2f}, 类型={r.kind})")
```

**重要**：每次 `recall` 会自动增强被召回记忆的强度，模拟人类"复习"效果。

### 关联遍历

从一个节点出发，发现关联的上下文：

```python
# 1 跳：直接关联
direct = mg.neighbors(user.id, depth=1)

# 2 跳：关联的关联（发现更远的关系）
extended = mg.neighbors(user.id, depth=2)
```

**实战场景**：用户提到"上次那个 bug" → 搜索 "bug" → 召回相关事件 → 遍历关联 → 找到涉及的项目和人。

## 第 6 步：记忆衰减与遗忘

记忆不是永久的——不用的记忆会逐渐弱化：

```python
# 对所有记忆应用衰减
mg.decay_all()
```

衰减公式（Ebbinghaus 遗忘曲线）：

```
weight = initial_weight × e^(-0.3 × 天数)
```

- 每次被 `recall` 访问，强度恢复 `+0.4`（上限 1.0）
- 低于 `0.05` 的记忆自动删除（"遗忘"）

**这意味着**：重要的、反复使用的记忆会保持强韧；不再提及的记忆会自然淡出。

## 第 7 步：可视化

```python
print(mg.visualize_ascii())
```

输出示例：
```
📊 Memory Network:
  [person ] 罗嵩                           ██████████ 1.0
    ──created──▶ Catalyst - 数字精灵
    ──works_on──▶ OpenClaw Agent
  [skill  ] Python 快速原型                  ████████░░ 0.8
  [concept] Rust 嵌入式AI                    ██████░░░░ 0.6
```

## 第 8 步：统计与监控

```python
stats = mg.stats()
print(stats)
# {
#   "nodes": 5,
#   "edges": 4,
#   "avg_weight": 0.82,
#   "by_kind": {"person": 2, "concept": 2, "skill": 1}
# }
```

## 💡 实战模式

### Agent 会话中

```python
# 启动时：加载核心记忆
mg = MemoryGraph("agent.db")

# 对话中：记录新信息
user_node = mg.recall("用户名")[0]  # 找到用户节点
new_topic = mg.add("讨论了数据库选型", "event")
mg.link(new_topic.id, user_node.id, "discussed_by")

# 搜索上下文
context = mg.recall("数据库")
related = mg.neighbors(context[0].id, depth=1)

# 结束时：衰减
mg.decay_all()
```

### 长期运行

```python
import time

def daily_maintenance(mg):
    """每天运行一次"""
    mg.decay_all()  # 衰减不活跃的记忆
    
    stats = mg.stats()
    if stats["avg_weight"] < 0.3:
        print("⚠️ 记忆整体强度偏低，考虑复习核心记忆")
```

## 🔄 与 Memory Service 的关系

本项目是 `agent-memory-service`（Node.js）的 Python 概念验证版：

| 特性 | Memory Graph (Python) | Memory Service (Node.js) |
|------|----------------------|-------------------------|
| 语言 | Python | Node.js |
| 存储 | SQLite | JSON 文件 |
| 记忆结构 | 图谱节点 | 三层存储 |
| 提取 | 手动 | 自动（对话→记忆） |
| 搜索 | 关键词 | 关键词+语义+BM25 |
| 去重/合并 | — | ✅ |
| 依赖 | 零 | 零 |

**推荐**：用 Memory Graph 做概念验证和原型，用 Memory Service 做生产级 Agent。

## 🧪 扩展思路

```python
# 1. 语义搜索（需要 embedding）
def semantic_recall(mg, query_embedding, threshold=0.8):
    """用向量相似度替代关键词匹配"""
    pass

# 2. 摘要压缩
def compress_memories(mg, node_ids):
    """将多个相关记忆压缩为一条摘要"""
    pass

# 3. 时间感知
def recall_recent(mg, days=7):
    """优先召回最近的记忆"""
    cutoff = time.time() - days * 86400
    # 查询 created > cutoff 的节点
    pass
```

## 下一步

- 修改 `demo()` 函数，加入你自己的记忆场景
- 查看 [README.md](./README.md) 了解完整 API
- 阅读 [源码](./memory_graph.py)（~200 行，注释详尽）
