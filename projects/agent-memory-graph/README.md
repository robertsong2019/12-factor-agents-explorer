# Agent Memory Graph

> 基于 SQLite 的轻量知识图谱，模拟 AI Agent 的长期记忆管理

## 🎯 概述

用知识图谱管理 Agent 的记忆——节点是概念/实体/事件，边是关系。核心特性：

- **记忆衰减** — 基于 Ebbinghaus 遗忘曲线，未访问的记忆逐渐弱化
- **访问增强** — 被 recall 的记忆强度恢复，模拟人类复习效果
- **关联遍历** — BFS 遍历记忆网络，发现关联上下文
- **批量操作** — add_many / link_many / delete_many 高效批量写入
- **图算法** — PageRank、中心性、社区发现、k-core、三角形计数
- **导入导出** — JSON 序列化完整图谱，支持跨实例迁移
- **子图提取** — 聚焦邻域提取，适配 LLM context window
- **零依赖** — 仅用 Python 标准库（sqlite3 + json + math）

## 快速开始

```bash
python memory_graph.py
```

无需安装任何依赖，直接运行即可看到演示。

## 核心概念

### 节点类型 (Kind)

| Kind | 用途 | 示例 |
|------|------|------|
| `fact` | 事实性知识 | "Python 是动态类型语言" |
| `event` | 事件记录 | "深夜 debug session" |
| `person` | 人物信息 | "罗嵩" |
| `concept` | 概念/想法 | "Rust 嵌入式 AI" |
| `skill` | 技能标签 | "Python 快速原型" |

### 记忆衰减机制

```python
# Ebbinghaus 遗忘曲线
weight = initial_weight × e^(-0.3 × elapsed_days)

# 每次访问恢复
weight = min(1.0, decayed_weight + 0.4)

# 低于阈值自动遗忘
MIN_WEIGHT = 0.05
```

## API 参考

### 构造

#### `MemoryGraph(db_path=":memory:")`

创建记忆图谱实例。

```python
mg = MemoryGraph()           # 内存数据库
mg = MemoryGraph("mem.db")   # 持久化到文件
```

---

### 节点 CRUD

#### `add(label, kind="fact", data=None, tags=None) -> Node`

添加记忆节点。

```python
node = mg.add("OpenClaw", "concept", {"lang": "TypeScript"}, ["oss", "ai"])
```

#### `get_node(node_id) -> Node | None`

按 ID 获取节点。

#### `update_node(node_id, label=None, kind=None, data=None, tags=None) -> Node | None`

更新节点字段（仅传需要修改的）。

#### `delete_node(node_id) -> bool`

删除节点及其所有边。

#### `has_node(node_id) -> bool`

检查节点是否存在。

#### `touch(node_id) -> Node | None`

触碰节点（更新 accessed_at，恢复衰减权重），不改变其他字段。

#### `rename_node(node_id, new_label) -> Node | None`

重命名节点。

#### `clone_node(node_id, new_label=None) -> Node | None`

克隆节点（复制 label/kind/data/tags，不复制边）。

---

### 批量操作

#### `add_many(items) -> list[Node]`

批量添加节点。`items` 为 `[{label, kind?, data?, tags?}]` 列表。

#### `delete_many(node_ids) -> int`

批量删除节点，返回删除数量。

---

### 边操作

#### `link(source_id, target_id, relation, weight=1.0)`

建立节点间关系。

```python
mg.link(user.id, project.id, "works_on")
```

#### `unlink(source_id, target_id, relation)`

删除指定边。

#### `is_linked(source_id, target_id, relation=None) -> bool`

检查两点间是否存在边（可按 relation 过滤）。

#### `edges_of(node_id, direction="both") -> list[Edge]`

获取节点的所有边。direction: `"in"` / `"out"` / `"both"`。

#### `link_many(pairs) -> int`

批量建边。`pairs` 为 `[{source, target, relation, weight?}]` 列表。

#### `unlink_many(pairs) -> int`

批量删边。

---

### 搜索与召回

#### `recall(query, limit=5) -> list[Node]`

按关键词召回记忆（自动增强访问强度）。

```python
results = mg.recall("Python")
```

#### `find_by_kind(kind) -> list[Node]`

按类型查找所有节点。

#### `search_by_data(key, value=None) -> list[Node]`

按 data 字段搜索。`value=None` 时匹配包含 key 的所有节点。

#### `search_by_tag(tag) -> list[Node]`

按标签搜索。

#### `search_unified(query, limit=10) -> list[dict]`

统一搜索（label + kind + tags + data），返回带匹配分数的结果。

#### `top_nodes(n=5) -> list[Node]`

按权重返回前 N 个节点。

#### `count_by_kind() -> dict[str, int]`

按类型统计节点数量。

---

### 图遍历

#### `neighbors(node_id, depth=1) -> list[Node]`

BFS 遍历获取关联记忆。

#### `shortest_path(start_id, end_id) -> list[str] | None`

Dijkstra 最短路径（按边权重）。

#### `path_exists(start_id, end_id) -> bool`

快速检查两点是否连通。

---

### 子图与分析

#### `subgraph(node_id, depth=1) -> dict`

提取以某节点为中心的子图，返回 `{nodes, edges}`。适配 LLM context window。

```python
sg = mg.subgraph(node.id, depth=2)
# sg = {"nodes": [...], "edges": [...]}
```

#### `aggregate(kind, field="weight", fn="sum") -> float`

按类型聚合数值。fn 支持 `"sum"` / `"avg"` / `"min"` / `"max"` / `"count"`。

#### `prune(min_weight=0.1) -> dict`

清理低权重节点。返回 `{removed_nodes, removed_edges}`。

#### `stats() -> dict`

返回记忆网络统计（节点数、边数、平均强度、类型分布）。

#### `merge_nodes(source_id, target_id) -> Node | None`

合并两个节点（数据合并，边迁移到目标）。

#### `graph_diff(other) -> dict`

对比两个图谱差异（节点/边增删）。

#### `compact(strategy="merge_similar", similarity_threshold=0.8) -> dict`

图谱压缩（合并相似节点，清理冗余边）。

---

### 图算法

#### `degree(node_id) -> int`

节点度数。

#### `degree_centrality(node_id) -> float`

度中心性。

#### `betweenness_centrality(node_id) -> float`

介数中心性。

#### `eigenvector_centrality(node_id, max_iter=100) -> float`

特征向量中心性。

#### `pagerank(damping=0.85, max_iter=100) -> dict[str, float]`

PageRank 值。

#### `community_detect() -> list[set[str]]`

Louvain 风格社区发现。

#### `k_core(k=3) -> set[str]`

k-core 分解。

#### `triangles() -> dict[str, int]`

每个节点的三角形计数。

---

### 标签管理

#### `tag_nodes(tag, node_ids)`

批量打标签。

#### `rename_tag(old_tag, new_tag) -> int`

重命名标签，返回受影响节点数。

#### `clear_tags(node_id) -> bool`

清除节点所有标签。

#### `all_tags() -> list[str]`

返回所有标签。

---

### 导入导出

#### `export_json() -> dict`

导出完整图谱为 JSON 兼容字典。

```python
data = mg.export_json()
# {"nodes": [...], "edges": [...]}
```

#### `import_json(data, merge=False)`

导入图谱。`merge=True` 时与现有数据合并而非替换。

---

### 时间与推荐

#### `timeline(kind=None, since=None, until=None, limit=50) -> list[Node]`

按时间线查询节点。`since`/`until` 为 ISO 字符串。

#### `recommend(node_id, limit=5) -> list[dict]`

基于 Jaccard 相似度的邻居推荐。

---

### 拓扑查询

#### `find_roots() -> list[Node]`

查找无入边的根节点。

#### `find_leaves() -> list[Node]`

查找无出边的叶子节点。

---

### 可视化

#### `visualize_ascii() -> str`

终端可视化，显示记忆强度条形图和关系图。

---

### 维护

#### `decay_all()`

对所有记忆应用遗忘衰减，清除已遗忘节点。

---

## 测试

```bash
python3 -m pytest test_memory_graph.py -q
```

184 个测试覆盖所有 API。

## 设计思路

1. **Agent 记忆应该用什么结构？** — 图谱比列表更适合表达关联
2. **如何避免记忆膨胀？** — 遗忘曲线是自然的"垃圾回收"
3. **如何模拟人类回忆？** — recall 时增强 + 关联遍历 = 上下文感知
4. **子图提取** — 让 Agent 聚焦相关记忆，适配有限的 context window
5. **图算法** — PageRank 发现重要记忆，社区发现识别知识领域

## 许可

MIT
