# Agent Memory Graph

> 基于 SQLite 的轻量知识图谱，模拟 AI Agent 的长期记忆管理

[![Tests](https://img.shields.io/badge/tests-1554-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.10+-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()
[![Dependencies](https://img.shields.io/badge/dependencies-zero-success)]()

## 🎯 概述

用知识图谱管理 Agent 的记忆——节点是概念/实体/事件，边是关系。核心特性：

- **记忆衰减** — 基于 Ebbinghaus 遗忘曲线，未访问的记忆逐渐弱化
- **访问增强** — 被 recall 的记忆强度恢复，模拟人类复习效果
- **关联遍历** — BFS / DFS 遍历记忆网络，发现关联上下文
- **批量操作** — add_many / link_many / delete_many / batch_reweight 高效批量写入
- **图算法** — PageRank、中心性（度/介数/特征向量）、社区发现、k-core、三角形计数、聚类系数
- **图变换** — 反转边、转无向、按标签诱导子图、权重归一化
- **BM25 全文搜索** — 内置 FTS5 全文索引，BM25 排序 + 权重提升
- **向量搜索** — sqlite-vec 可选集成，KNN 向量搜索
- **三路混合搜索** — Reciprocal Rank Fusion: BM25 文本 + 向量 KNN + 图邻居加权
- **GraphRAG 检索** — naive/local/global/hybrid 四种检索模式，社区级搜索 + 图扩展
- **演化追踪** — 记录节点 label/kind 变化历史，支持回滚和合并
- **快照与恢复** — 一键快照 → 恢复完整图谱状态
- **去重** — 基于 Levenshtein 距离的模糊标签去重 + 合并
- **导入导出** — JSON / DOT / GraphML / Cytoscape / Edge List / Adjacency List 六种格式
- **子图提取** — 聚焦邻域提取，适配 LLM context window
- **LLM 上下文导出** — to_markdown 图谱转 Markdown + context_window BFS 提取
- **智能剪枝** — prune_by_relevance 基于 BM25 相关性保留 top-k 节点
- **社区分析** — 社区发现 + community_summary 密度/成员/标签洞察
- **结构角色分类** — hub/authority/bridge/isolated/member 五种角色
- **网络效率分析** — 全局效率、S-metric、有效偏心率，衡量信息传递与拓扑结构
- **标签 CRUD** — add_tag/remove_tag/has_tag 单标签管理
- **差分与合并** — 图差异对比、patch 应用、双图合并
- **可学习记忆管理** — Memory-R1/AgeMem 启发的自动 CRUD 决策 + 审计 + FiFA 有界遗忘 + 反馈学习
- **memorywire 互操作** — to_memorywire/from_memorywire 跨后端记忆交换 (semantic/episodic/procedural/emotional)
- **图探索与采样** — 加权随机游走 (random walk with restart) + BFS/DFS/random_walk 三策略子图采样
- **鲁棒社区检测** — Leiden 启发的随机化迭代 + 模块度回退，避免对称图标签级联
- **网络拓扑分析** — 度分布 (Shannon 熵) + 连通前沿 + Freeman 归一化度中心性 + 诱导子图密度 + 加权度 + 邻域普查
- **多智能体记忆合并** — CRDT-based 合并策略 (LWW/OR-Set/Trust-weighted)，支持多 Agent 记忆图一致合并
- **零依赖** — 仅用 Python 标准库（sqlite3 + json + math），sqlite-vec 为可选依赖

## 安装

```bash
pip install agent-memory-graph
```

或直接将 `memory_graph.py` 放入项目——零依赖，Python ≥ 3.10。

## 快速开始

```python
from memory_graph import MemoryGraph

mg = MemoryGraph()  # 内存数据库

# 添加记忆
rust = mg.add("Rust", "concept", {"type": "systems language"}, ["fast", "safe"])
ts = mg.add("TypeScript", "concept", {"type": "web language"}, ["typed"])
mg.link(rust.id, ts.id, "contrasts_with")

# 召回
results = mg.recall("Rust")
print(results[0].label)  # "Rust"

# 关联遍历
neighbors = mg.neighbors(rust.id, depth=2)

# 图分析
print(mg.stats())  # {nodes: 2, edges: 1, ...}
print(mg.pagerank())  # {"1": 0.57, "2": 0.43}
```

运行内置演示：

```bash
python3 memory_graph.py
```

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

#### `reweight(node_id, delta) -> Node | None`

调整节点权重（delta 可负），自动 clamp 到 [0, 1]。

#### `random_node() -> Node | None`

随机返回一个节点，空图返回 None。

---

### 批量操作

#### `add_many(items) -> list[Node]`

批量添加节点。`items` 为 `[{label, kind?, data?, tags?}]` 列表。

#### `delete_many(node_ids) -> int`

批量删除节点，返回删除数量。

#### `batch_reweight(items) -> int`

批量调整权重。`items` 为 `[{"id": ..., "delta": 0.1}]`，返回成功更新数。

---

### 边操作

#### `link(source_id, target_id, relation, weight=1.0)`

建立节点间关系。

```python
mg.link(user.id, project.id, "works_on")
```

#### `unlink(source_id, target_id, relation)`

删除指定边。

#### `unlink_all(node_id) -> int`

删除节点的所有边，返回删除数。

#### `unlink_many(pairs) -> int`

批量删边。`pairs` 为 `[{source, target, relation?}]`，relation 省略时删除两点间所有边。

#### `is_linked(source_id, target_id, relation=None) -> bool`

检查两点间是否存在边（可按 relation 过滤）。

#### `edges_of(node_id, direction="both") -> list[Edge]`

获取节点的所有边。direction: `"in"` / `"out"` / `"both"`。

#### `get_edge(source_id, target_id, relation) -> Edge | None`

获取特定边（source + target + relation），不存在返回 None。

#### `update_edge(source_id, target_id, relation, weight=None, new_relation=None) -> Edge | None`

更新边的权重和/或重命名 relation。

#### `edge_properties(source_id, target_id, relation) -> dict | None`

获取边的元数据（properties 字段）。

#### `set_edge_properties(source_id, target_id, relation, properties) -> bool`

设置边的元数据（upsert），边不存在返回 False。

#### `link_many(pairs) -> int`

批量建边。`pairs` 为 `[{source, target, relation, weight?}]` 列表。

#### `link_strength(node_id) -> list[dict]`

返回节点所有边按权重降序排列，含 partner 信息。

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

#### `search_by_label(query, limit=10) -> list[Node]`

仅在 label 字段搜索（FTS5 全文索引）。

#### `search_by_tag(tag) -> list[Node]`

按标签搜索。

#### `search_unified(query, limit=10) -> list[dict]`

统一搜索（label + kind + tags + data），返回带匹配分数的结果。

#### `top_nodes(n=5) -> list[Node]`

按权重返回前 N 个节点。

#### `count_by_kind() -> dict[str, int]`

按类型统计节点数量。

#### `importance_rank(limit=20, decay_hours=168.0) -> list[dict]`

综合重要性排序：权重(40%) + 度数(30%) + 最近访问(30%)。

#### `search_bm25(query, limit=10, kind=None, tag=None, weight_boost=1.0) -> list[dict]`

FTS5 全文搜索（BM25 排序）。支持按 kind/tag 过滤，权重提升高权重节点。返回 `{node_id, label, kind, score}`。

```python
results = mg.search_bm25("memory decay", limit=5, kind="concept")
```

#### `search_hybrid(query, embedding=None, limit=10) -> list[dict]`

三路混合搜索 (Reciprocal Rank Fusion):
1. **BM25 文本搜索**: label/data/tags/kind 全文匹配
2. **向量搜索** (可选): embedding KNN
3. **图邻居加权**: 种子节点的邻居按边权重排序（edge-weight-sorted ranking），边权重越大排名越高

WRRF 融合模式下，图路由使用边权重归一化后的原始分数作为置信度。返回 `{node_id, label, kind, score, sources}` 按融合分数降序。向量不可用时静默降级。

#### `search_graphrag(query, mode="hybrid", limit=20, depth=2, community=None) -> dict`

GraphRAG 统一检索，四种模式：
- `"naive"` — 直接 BM25 搜索
- `"local"` — 搜索 + 邻域图扩展
- `"global"` — 社区级汇总搜索
- `"hybrid"` — local + global 结合

返回 `{mode, results, expanded_nodes, communities}`。

#### `search_labels(query, limit=10) -> list[Node]`

仅在 label 字段中搜索（FTS5）。

#### `search_similar(embedding, limit=10) -> list[dict]`

KNN 向量相似度搜索。返回 `{node_id, label, kind, distance, score}` 按距离升序。

#### `search_similar_to_node(node_id, limit=10) -> list[dict]`

基于嵌入向量查找与指定节点最相似的其他节点。排除自身。

#### `search_similar_by_kind(embedding, kind, limit=10) -> list[dict]`

按 kind 过滤的向量搜索。

#### `search_similar_by_tag(embedding, tag, limit=10) -> list[dict]`

按 tag 过滤的向量搜索。

#### `neighbors_filtered(node_id, relation=None, kind=None, tag=None, min_weight=None, direction="both") -> list[Node]`

过滤邻居搜索：按 relation/kind/tag/weight 多条件筛选。

---

### 标签 CRUD

#### `add_tag(node_id, tag) -> Node | None`

为节点添加单个标签。

#### `remove_tag(node_id, tag) -> Node | None`

移除节点的单个标签。

#### `has_tag(node_id, tag) -> bool`

检查节点是否拥有指定标签。

---

### LLM 上下文导出

#### `to_markdown(node_ids=None, max_nodes=50) -> str`

将图谱转为 Markdown 格式（按 kind 分组，含标签/数据/权重/边信息）。适合直接注入 LLM 上下文。

```python
md = mg.to_markdown(mg.neighbors(center_id, depth=2))
# ## concept
# - **Rust** (w: 0.85) #safe #fast
#   data: {type: systems language}
#   → contrasts_with → TypeScript
```

#### `context_window(seed_id, hops=2, max_nodes=30, direction="both") -> str`

BFS 上下文提取：以 seed 为中心，双向扩展，★ 标记种子节点。自动格式化为 Markdown。

#### `prune_by_relevance(query, keep_top=50, fallback_min_weight=0.3) -> dict`

基于 BM25 相关性的智能剪枝。保留与查询最相关的 top-k 节点，不够时用高权重节点补充。自动清理 FTS + 嵌入。

---

### 图遍历

#### `neighbors(node_id, depth=1) -> list[Node]`

BFS 遍历获取关联记忆。

#### `bfs_order(start_id, max_depth=10) -> list[str]`

BFS 遍历序（返回节点 ID 列表）。

#### `dfs_order(start_id, max_depth=10) -> list[str]`

DFS 遍历序（返回节点 ID 列表）。

#### `shortest_path(start_id, end_id) -> list[str] | None`

BFS 最短路径（按跳数）。

#### `bfs_shortest_path(start_id, end_id, weight_key=None) -> list | None`

BFS 最短路径，可选按边权重计算路径成本。

#### `path_exists(start_id, end_id, max_depth=20) -> bool`

快速检查两点是否连通。

#### `find_paths(from_id, to_id, max_depth=10) -> list`

查找两点间所有路径（深度限制内）。

#### `reachability_count(node_id, max_depth=10) -> int`

从某节点可达的不同节点数（不含自身）。

---

### 子图与提取

#### `subgraph(node_id, depth=1) -> dict`

提取以某节点为中心的子图，返回 `{nodes, edges}`。适配 LLM context window。

```python
sg = mg.subgraph(node.id, depth=2)
# sg = {"nodes": [...], "edges": [...]}
```

#### `induced_subgraph(node_ids) -> MemoryGraph`

由指定节点集合构成的诱导子图，返回新的 MemoryGraph 实例。

#### `induce_by_tags(tags, match_all=False) -> dict`

按标签筛选节点并返回子图。`match_all=True` 要求拥有所有标签。

#### `ancestor_graph(node_id, max_depth=10) -> list[str]`

返回所有祖先节点 ID（逆向 BFS）。

#### `descendant_graph(node_id, max_depth=10) -> list[str]`

返回所有后代节点 ID（正向 BFS）。

#### `random_walk(start_id, steps=10, restart_prob=0.0, weight_key=None) -> list[str]`

从指定节点出发在图上进行随机游走。每一步以边权重为概率选择下一个邻居（无 `weight_key` 时均匀随机）。以 `restart_prob` 概率传送回起点（PageRank-style random walk with restart）。

适用场景：
- 图采样（node2vec / DeepWalk 嵌入预处理）
- 个性化 PageRank 近似
- GraphRAG 局部探索

```python
path = mg.random_walk("node-1", steps=20, restart_prob=0.15)
# => ["node-1", "node-3", "node-7", "node-1", "node-2", ...]
```

#### `graph_sample(start_id, max_nodes=50, strategy="bfs") -> list[str]`

提取代表性子图样本，支持三种策略：

| 策略 | 描述 |
|------|------|
| `"bfs"` | 广度优先扩展（默认） |
| `"dfs"` | 深度优先扩展 |
| `"random_walk"` | 随机游走采样（以更少节点保留结构特征） |

```python
sample = mg.graph_sample("node-1", max_nodes=30, strategy="random_walk")
# => ["node-1", "node-3", "node-7", "node-12", ...]  # ≤30 nodes
```

---

### 图变换

#### `reverse_edges() -> int`

反转所有边方向，返回受影响边数。

#### `to_undirected() -> int`

将有向多重边合并为无向（对称边去重），返回移除的边数。

#### `weight_normalize(target_min=0.0, target_max=1.0) -> int`

将所有节点权重线性归一化到 [target_min, target_max]，返回更新数。

---

### 图结构与拓扑

#### `find_components() -> list[list[str]]`

所有连通分量（基于 Union-Find）。

#### `largest_component_size() -> int`

最大连通分量大小。

#### `find_roots() -> list[Node]`

无入边的根节点（含孤立节点）。

#### `find_leaves() -> list[Node]`

无出边的叶子节点（含孤立节点）。

#### `find_orphans() -> list[Node]`

没有任何边的孤立节点。

#### `has_cycle() -> bool`

检测图中是否存在环（DFS 三色标记法）。

#### `is_dag() -> bool`

图是否为有向无环图。

#### `topological_sort() -> list`

拓扑排序（DAG 适用），含环时返回空列表。

#### `degree_histogram() -> dict[int, int]`

度分布直方图 `{degree: count}`。

#### `degree_sequence(order="desc") -> list[int]`

所有节点的度数序列（排序后）。

#### `distance_matrix(node_ids=None) -> dict[tuple, int]`

节点间最短距离矩阵。`node_ids=None` 时计算全图。

---

### 聚合与分析

#### `aggregate(kind, field="weight", fn="sum") -> float`

按类型聚合数值。fn 支持 `"sum"` / `"avg"` / `"min"` / `"max"` / `"count"`。

#### `stats() -> dict`

返回记忆网络统计（节点数、边数、平均强度、类型分布）。

#### `stats_summary() -> dict`

一键图统计仪表盘（节点/边/密度/平均度/类型分布/标签数等）。

#### `group_by(kind=None, tag=None) -> dict[str, list[Node]]`

按 kind 或 tag 分组节点。

#### `count_edges() -> int`

边总数（可按 relation 过滤：`count_edges(relation="works_on")`）。

#### `edge_count(relation=None) -> int`

`count_edges` 的别名。

#### `is_empty() -> bool`

图是否为空（无节点）。

#### `prune(min_weight=0.1) -> dict`

清理低权重节点。返回 `{removed_nodes, removed_edges}`。

#### `clear() -> None`

清空所有节点和边。

---

### 图算法

#### `degree(node_id, direction="both") -> int`

节点度数。direction: `"in"` / `"out"` / `"both"`。

#### `degree_centrality(node_id) -> float`

度中心性（归一化，0.0–1.0）。

#### `centrality_degree(node_id) -> float`

度中心性（考虑双向边）。

#### `betweenness_centrality(node_id, samples=50) -> float`

近似介数中心性（基于随机采样最短路径）。

#### `betweenness_centrality_approx(samples=20) -> dict[str, float]`

全局近似介数中心性（采样 Brandes 算法，大图适用）。

#### `eigenvector_centrality(iterations=100, damping=0.85) -> dict[str, float]`

特征向量中心性。

#### `pagerank(iterations=100, damping=0.85) -> dict[str, float]`

PageRank 值。

#### `community_detect(max_iter=10) -> dict[str, list[str]]`

标签传播社区发现，返回 `{community_label: [node_ids]}`。

#### `community_detection_greedy() -> dict[str, int]`

贪心社区检测（基于边密度），返回 `{node_id: community_id}`。

#### `k_core(k=3) -> set[str]`

k-core 分解（度数 ≥ k 的节点集合）。

#### `triangles(node_id) -> int`

节点参与的三角形计数。

#### `graph_density() -> float`

有向图密度 = 实际边数 / 最大可能边数。

#### `reciprocity() -> float`

互惠率 = 双向边对数 / 总边数。

#### `assortativity_degree() -> float`

度-度相关性：正值 = 同配，负值 = 异配。

#### `clustering_coefficient(node_id) -> float`

局部聚类系数：邻居间实际边数 / 最大可能。

#### `rich_club_coefficient(degree_k) -> float`

富人俱乐部系数：度 ≥ k 节点间边密度。

#### `global_clustering_coefficient() -> float`

全局聚类系数（传递性）。

#### `modularity(communities) -> float`

模块度 Q：衡量社区划分质量。`communities = {node_id: community_id}`。

#### `community_partition(method="leiden", **kwargs) -> dict[str, int]`

统一社区划分 API。`method` 可选 `"leiden"` 或 `"greedy"`，返回 `{node_id: community_id}`。

#### `community_quality_report(community_id=None) -> dict`

社区质量报告：划分质量指标、各社区统计（节点数/密度/标签）、推荐关注社区。

#### `articulation_points() -> list[str]`

关节点（Tarjan 算法）——移除后会增加连通分量的节点。

#### `find_bridges() -> list[tuple]`

桥边（Tarjan 算法）——移除后会增加连通分量的边。

#### `is_bipartite() -> bool`

检测图是否为二部图（BFS 染色法）。

#### `effective_diameter(percentile=0.9) -> int`

有效直径——指定百分位的最大最短距离，比绝对直径更抗异常值。

#### `harmonic_centrality(node_id=None) -> float | dict[str, float]`

调和中心性——倒数距离之和，断连图友好（不依赖最大距离）。

#### `edge_betweenness(normalized=True) -> dict[tuple, float]`

边介数（Brandes 算法）——每条边在最短路径中出现频率。识别关键连接。

#### `community_summary(community_id=None) -> dict`

社区洞察仪表盘：密度、top 成员、标签聚合、kind 分布。社区级快速画像。

#### `node_roles(node_id=None) -> str | dict[str, str]`

结构角色分类：`hub`（高度数）/ `authority`（高入度）/ `bridge`（高介数）/ `isolated`（孤立）/ `member`（普通）。

#### `role_summary() -> dict[str, list[str]]`

全局角色汇总——按角色分类列出所有节点。

#### `effective_eccentricity(node_id, percentile=0.9) -> Optional[float]`

有效偏心率——指定百分位的到其他节点的最短距离。比绝对偏心率更抗异常值，衡量节点信息传播范围。

#### `global_efficiency() -> Optional[float]`

全局效率（Latora-Marchiori）——所有节点对距离倒数之和的归一化值。衡量网络整体信息传递效率，断连图友好（断连对贡献 0 而非无穷）。

#### `authority_score(iterations=100) -> dict[str, float]`

HITS authority 得分——衡量节点作为权威信息源的强度。

#### `average_path_length() -> Optional[float]`

平均最短路径长度（所有可达节点对）。

#### `closeness_centrality(node_id) -> float`

接近中心性——到其他节点平均距离的倒数，衡量节点到全图的接近程度。

#### `connected_components() -> list[list[str]]`

`find_components()` 的别名——所有连通分量列表。

#### `core_number() -> dict[str, int]`

核心数——每个节点的最大 k-core 值 (Batagelj-Zaversnik 算法)。

#### `count_triangles() -> int`

全局三角形计数。

#### `local_triangle_count(node_id) -> int`

单节点参与的三角形计数（`triangles()` 的别名）。

#### `detect_communities_leiden(resolution=1.0) -> dict[str, int]`

Leiden 社区检测算法——比标签传播更稳定，返回 `{node_id: community_id}`。

#### `lazy_community_detect(seed_nodes, hops=1, max_nodes=50) -> dict[str, int]`

LazyGraphRAG 风格的局部社区发现——从种子节点出发，仅扩展 N 跳邻域，在局部子图上运行标签传播。适合增量式社区分析和大图的局部探索。

内部实现采用 Leiden 启发的快速局部移动算法，每轮迭代随机化节点顺序（防止对称图上的标签级联），并计算模块度 Q 值。若分区结果劣于单一社区（Q < 0），自动回退为单社区方案。

```python
communities = mg.lazy_community_detect(["node-1", "node-5"], hops=2)
# => {"node-1": 0, "node-2": 0, "node-5": 1, ...}
```

#### `community_fit_scores(communities=None) -> dict[str, float]`

计算节点的社区适应度分数——衡量节点与所在社区的契合度（邻居中同社区比例）。`communities` 为 `{node_id: community_id}` 映射，默认使用 `community_detect()` 结果。

```python
scores = mg.community_fit_scores()
# => {"node-1": 0.85, "node-2": 0.92, "node-3": 0.30}
# 低分节点可能是跨社区桥梁或异类节点
```

#### `bridge_nodes(communities=None, threshold=0.4) -> list[dict]`

识别跨社区桥梁节点——社区适应度低于 threshold 的节点，其邻居横跨多个社区。返回 `[{"node_id": ..., "score": ..., "communities": [0, 1, 2]}]`。

#### `community_outliers(communities=None, threshold=0.3) -> list[str]`

识别社区异常点——社区适应度极低的节点（孤岛、噪声、跨域异类）。先计算 `community_fit_scores`，再筛出低于 threshold 的节点。

```python
outliers = mg.community_outliers(threshold=0.2)
# => ["node-42", "node-87"]  # 这些节点不属于任何明确社区
```

#### `smart_query_route(query, embedding=None) -> dict`

智能查询路由——自动分析查询特征，选择最优 GraphRAG 检索模式。根据查询中的实体/关系/社区关键词，动态决定使用 `local`、`global` 还是 `hybrid` 模式。

```python
route = mg.smart_query_route("和 Rust 相关的概念有哪些")
# => {"mode": "local", "reason": "entity-centric query", "entities": ["Rust"]}

route = mg.smart_query_route("整个知识库的主要主题是什么")
# => {"mode": "global", "reason": "broad thematic query"}
```

#### `dfs(start_id, max_depth=10) -> list[str]`

深度优先搜索遍历序。

#### `eccentricity(node_id) -> Optional[int]`

偏心率——节点到其他所有可达节点的最大最短距离。

#### `graph_diameter() -> Optional[int]`

图直径——所有节点对最大最短距离。

#### `graph_radius() -> Optional[int]`

图半径——所有节点最小偏心率。

#### `is_connected() -> bool`

图是否连通（单一连通分量）。

#### `node_distance(start_id, end_id) -> Optional[int]`

两节点间最短距离（跳数）。

#### `s_metric() -> Optional[float]`

S-metric——所有边的度数乘积之和（Σ d(u)·d(v)）。衡量网络的 hub-spoke 结构强度，值越高越倾向于 hub 集中式拓扑。

#### `local_efficiency(node_id) -> Optional[float]`

局部效率——节点邻居子图（不含节点本身）的全局效率。衡量节点被移除后邻居间仍能通信的程度。范围 [0, 1]，高值 = 鲁棒的局部结构。与 clustering_coefficient 互补。

References: Latora & Marchiori (2001).

#### `wiener_index() -> Optional[int]`

Wiener 指数——所有节点对最短路径长度之和（W = Σ d(u,v)）。经典图论不变量 (Wiener 1947)，average_path_length 的未归一化版本。不可达对不计入。

#### `onion_structure(n_layers=3) -> Optional[list[dict]]`

洋葱结构——k-core 分层剖面。逐步移除度数 < k 的节点，返回每层的节点集合和统计信息。比 core_number() 更直观展示图的 "深度结构"。每层返回 `{k, nodes, count, edges}`。

#### `minimum_spanning_tree() -> Optional[list[dict]]`

最小生成树（Kruskal 算法 + Union-Find 路径压缩 + 按秩合并）。返回权重最小的生成树边集，按权重升序排列。用于识别记忆网络的核心骨架。

#### `mst_weight() -> Optional[float]`

最小生成树总权重。`minimum_spanning_tree()` 的快捷方式。

#### `resistance_distance(id_a, id_b) -> Optional[float]`

电阻距离（effective resistance）——基于拉普拉斯矩阵伪逆。低值 = 节点间有多条冗余路径；高值 = 依赖少数脆弱路径。

#### `algebraic_connectivity() -> Optional[float]`

代数连通度（Fiedler value）——拉普拉斯矩阵第二小特征值。0 = 不连通；大值 = 强连通。衡量图整体连通强度。

#### `fiedler_vector() -> Optional[list[float]]`

Fiedler 向量——对应代数连通度的特征向量。可用于谱二分（正/负分两组）和 1D 谱嵌入。

#### `spectral_radius() -> Optional[float]`

邻接矩阵的谱半径（幂迭代法）。高值 = 强连通、hub-hub 连接多；低值 = 稀疏链状结构。

#### `edge_connectivity() -> int`

边连通度 λ(G)——使图不连通所需移除的最少边数。

#### `node_connectivity() -> int`

节点连通度 κ(G)——使图不连通所需移除的最少节点数（基于 Menger 定理 + 节点分裂最大流）。

#### `closeness_vitality(node_id) -> Optional[float]`

节点删除后 Wiener 指数的变化量。正值 = 节点对连通性重要；负值 = 节点是瓶颈。

#### `percolation_centrality(states=None) -> dict[str, float]`

渗透中心性——衡量节点在信息渗透过程中的传播重要性。默认用归一化度数作为渗透状态。

#### `triad_census() -> dict[str, int]`

有向三元组普查（16-type, MaaS convention）——统计所有可能的有向三元组类型。编码：0=无边, 1=i→j, 2=j→i, 3=双向，三元组编码 (ij)(ik)(jk)。

#### `average_neighbor_degree() -> dict[str, float]`

平均邻居度数 k_nn(i) = (1/k_i) × Σk_j。高值 = 邻居是 hub 节点；低值 = 邻居是低度节点。

#### `degree_correlation() -> Optional[float]`

Newman 度-度相关系数（assortativity）。r>0 同配（hub 连 hub）；r<0 异配（hub 连低度）；r≈0 无相关。

#### `node_similarity(id_a, id_b, mode="jaccard") -> float`

节点结构相似度。`mode="jaccard"` 为 Jaccard 系数，`mode="overlap"` 为 Szymkiewicz–Simpson 重叠系数。返回 0.0~1.0。

---

### 节点相似性与链路预测

#### `edge_weight_stats() -> dict`

边权重统计：最小值/最大值/均值/标准差/中位数。

#### `weight_distribution(bins=10) -> list[int]`

权重分布直方图——按区间统计节点数量。

#### `jaccard_similarity(node_id1, node_id2) -> float`

邻居集合的 Jaccard 相似度。

#### `neighborhood_overlap(node_id1, node_id2) -> float`

邻居重叠系数（较小集的共享比例）。

#### `adamic_adar(node_id1, node_id2) -> float`

Adamic/Adar 指数 — 共同邻居的 1/log(degree) 之和，用于链路预测。

---

### 网络拓扑分析

#### `degree_distribution() -> dict[int, float]`

度分布——每个度数值对应的节点比例。返回 `{degree: fraction}`，用于分析网络的异质性（幂律 vs 均匀）。

```python
dist = mg.degree_distribution()
# {0: 0.05, 1: 0.30, 2: 0.35, 3: 0.20, 4: 0.10}
```

#### `network_summary() -> dict`

综合网络统计仪表盘——节点数、边数、密度、平均度、最大度、连通分量数、平均聚类系数、标签数、类型分布等。`stats()` 的增强版。

#### `k_hop_neighbors(node_id, k=2) -> dict[int, list[str]]`

K-hop 邻居普查——返回每一跳的节点 ID 列表 `{hop: [node_ids]}`。比 `neighbors(depth=k)` 更直观地展示逐层扩展结构。

```python
hops = mg.k_hop_neighbors("node-1", k=3)
# {1: ["node-2", "node-3"], 2: ["node-4", "node-5", "node-6"], 3: ["node-7"]}
```

#### `common_neighbors(node_id_a, node_id_b) -> list[str]`

两个节点的共同邻居列表——用于链路预测和社区桥梁分析。

#### `graph_entropy() -> dict[str, float]`

图熵——基于度分布的 Shannon 熵。高值 = 度分布均匀（异构网络）；低值 = 度集中（hub-spoke 结构）。返回 `{entropy, max_entropy, normalized}`。

#### `connectivity_frontier(node_id, max_hop=3) -> dict[int, int]`

连通前沿——从指定节点出发，每一跳新增的可达节点数 `{hop: new_nodes}`。衡量节点的信息辐射范围和速度。

#### `degree_centrality_normalized() -> dict[str, float]`

Freeman 归一化度中心性——节点度数 / (n-1)，范围 [0, 1]。消除图规模差异后的标准化中心性。适用于跨图比较节点重要性。

#### `edge_density_subgraph(node_ids) -> float`

诱导子图边密度——指定节点集合内部的边数 / 最大可能边数。用于评估社区或群体的紧密度。

#### `weighted_degree(node_id) -> float`

加权度——节点所有邻接边的权重之和。衡量节点的总连接强度（vs 普通度数只计边数）。

#### `weighted_degree_all() -> dict[str, float]`

全图加权度——每个节点的加权度 `{node_id: weighted_degree}`。

#### `neighborhood_census() -> dict[str, dict]`

邻域普查——每个节点的邻居统计 `{node_id: {"in": n, "out": n, "both": n}}`。快速了解全图的度分布细节。

---

### CRDT 合并与多智能体记忆

#### `merge_crdt(other_graph_data, strategy="lww", trust_weights=None) -> dict`

CRDT-based 多 Agent 记忆图合并——将另一个图的数据合并到当前图，保证收敛一致性。

| 策略 | 说明 |
|------|------|
| `"lww"` | Last-Write-Wins：以 created_at 时间戳最新者为准 |
| `"or-set"` | OR-Set：所有添加和删除都记录，无冲突 |
| `"trust"` | Trust-weighted：按 Agent 信任度权重加权决策 |

```python
# 多 Agent 场景：合并两个 Agent 的记忆图
mg1 = MemoryGraph("agent1.db")
mg2_data = MemoryGraph("agent2.db").export_json()
result = mg1.merge_crdt(mg2_data, strategy="trust",
                       trust_weights={"agent1": 0.9, "agent2": 0.7})
# {"merged_nodes": 45, "merged_edges": 12, "conflicts_resolved": 3}
```

适用场景：多智能体协作场景下的记忆同步、联邦学习中的知识聚合、Agent 团队的共享记忆构建。

---

### 聚类

#### `cluster(kind, threshold=0.4) -> list[dict]`

按 kind 过滤节点，基于 Jaccard 相似度聚类。返回 `[{"id": centroid_id, "members": [...]}`。

---

### 标签管理

#### `tag_nodes(tag, node_ids)`

批量打标签。

#### `rename_tag(old_tag, new_tag) -> int`

重命名标签，返回受影响节点数。

#### `clear_tags(node_id) -> bool`

清除节点所有标签。

#### `tag_cloud() -> list[dict]`

标签云数据——按使用频率排序，返回 `[{tag, count}]`。

#### `tag_stats() -> dict`

标签统计——总标签数、平均每节点标签数、最常用标签等。

#### `all_tags() -> list[str]`

返回所有标签。

---

### 演化追踪

#### `evolve(node_id, new_label=None, new_kind=None) -> Node | None`

演化节点（记录变更历史到 evolution log）。

#### `evolution_history(node_id) -> list[dict]`

获取节点的完整演化历史。

#### `revert_evolution(node_id, step_index) -> Node | None`

回滚到演化历史中的某一步。

#### `batch_evolve(mapping) -> list[Node | None]`

批量演化。`mapping` 为 `[{"id": ..., "label": ..., "kind": ...}]`。

#### `merge_evolution(node_id) -> dict | None`

合并节点所有演化步骤为单条摘要。

#### `evolution_summary() -> dict`

全局演化统计（总节点、演化节点、总步数、最活跃节点）。

---

### 快照与恢复

#### `snapshot() -> dict`

捕获完整图状态（节点 + 边 + 演化日志）。

#### `restore(snap) -> None`

从快照恢复图状态。

```python
snap = mg.snapshot()
# ... 做一些实验性修改 ...
mg.restore(snap)  # 回滚
```

---

### 导入导出

#### `export_json() -> dict`

导出完整图谱为 JSON 兼容字典。

```python
data = mg.export_json()
# {"nodes": [...], "edges": [...]}
```

#### `import_json(data, merge=False)`

导入图谱。`merge=True` 时与现有数据合并。

#### `import_edgelist(text, default_kind="fact", default_relation="related_to") -> int`

从边列表文本导入（每行 `source\ttarget\t[relation]\t[weight]`），返回导入边数。

#### `import_cytoscape(data, merge=False) -> int`

从 Cytoscape JSON 导入，返回导入节点数。

#### `import_graphml(xml_str, merge=False) -> int`

从 GraphML XML 导入，返回导入节点数。

#### `import_adjacency_list(data, default_relation="related_to") -> int`

从邻接表导入。`data` 为 `{node_label: [{target, relation?, weight?}]}` 或 `{label: [target_label]}`，返回导入边数。

#### `to_adjacency_list() -> dict[str, list[dict]]`

导出邻接表表示 `{node_id: [{"target", "relation", "weight"}]}`。

#### `serialize_dot() -> str`

导出为 Graphviz DOT 格式字符串。

#### `to_adjacency_matrix(node_ids=None) -> list[list[int]]`

邻接矩阵表示（0/1 矩阵）。`node_ids` 可选指定行/列顺序。

#### `serialize_edgelist() -> str`

导出为边列表格式（TSV: `source_id\ttarget_id\trelation\tweight`）。

#### `serialize_graphml() -> str`

导出为 GraphML XML 格式字符串。

#### `serialize_cytoscape() -> dict`

导出为 Cytoscape JSON 格式。

```python
dot = mg.serialize_dot()
# digraph G { "0" -> "1" [label="knows"]; ... }
```

#### `graph_hash() -> str`

图的结构指纹（MD5），基于排序后的节点/边数据。

---

### 差分、合并与对比

#### `graph_diff(other) -> dict`

对比两个图谱差异（节点/边增删改）。

#### `diff_summary(other) -> dict`

高层差异摘要（含计数和样本标签）。

#### `patch(diff, source) -> dict`

应用 `graph_diff()` 的结果同步图谱，返回应用统计。

#### `union(other) -> dict`

`merge_graph(other, strategy="union")` 的快捷方式。

#### `merge_graph(other, strategy="union") -> dict`

合并另一个图。strategy: `"union"`（增量）或 `"update"`（覆盖）。

#### `merge_nodes(source_id, target_id) -> Node | None`

合并两个节点（数据合并，边迁移到目标）。

#### `compact(strategy="merge_similar", similarity_threshold=0.8) -> dict`

图谱压缩（合并相似节点，清理冗余边）。

#### `dedup_nodes(similarity_threshold=0.8) -> list[dict]`

模糊标签去重（Levenshtein 距离），返回合并组列表。

---

### 隐私与导出

#### `anonymize() -> MemoryGraph`

创建隐私安全副本：去除 label 和 data，保留结构和 kind/weight。

---

### 时间与推荐

#### `timeline(kind=None, since=None, until=None, limit=50) -> list[Node]`

按时间线查询节点。`since`/`until` 为 ISO 字符串。

#### `recommend(node_id, limit=5) -> list[dict]`

基于 Jaccard 相似度的邻居推荐。

---

### 可视化

#### `visualize_ascii() -> str`

终端可视化，显示记忆强度条形图和关系图。

---

### 维护

#### `decay_all()`

对所有记忆应用遗忘衰减，清除已遗忘节点。

---

### 向量搜索 (sqlite-vec 可选集成)

> 需要安装可选依赖: `pip install sqlite-vec`

#### `add_embedding(node_id, embedding) -> None`

为节点添加向量嵌入。首次调用决定维度，后续必须一致。

#### `add_embeddings_batch(items) -> int`

批量添加嵌入。`items = [(node_id, embedding), ...]`，返回成功添加数。

#### `update_embedding(node_id, embedding) -> bool`

更新已有节点的嵌入向量。

#### `remove_embedding(node_id) -> bool`

删除节点的向量嵌入。

#### `remove_embeddings_batch(node_ids) -> int`

批量删除嵌入，返回成功数。

#### `has_embedding(node_id) -> bool`

检查节点是否有嵌入向量。

#### `embedding_count() -> int`

返回已存储嵌入的数量。

#### `vector_stats() -> dict`

返回 `{count, has_vectors, dimensions, node_count, coverage}` 统计信息。

---

### 可学习记忆管理 (Memory-R1 / AgeMem 启发)

> 自动决策新信息的记忆操作：新增、更新、忽略，并支持审计、有界遗忘和反馈学习。

#### `score_memory_ops(content, existing_keys=None, noop_bias=0.15) -> list[dict]`

对新信息评分 4 种操作 (ADD/UPDATE/DELETE/NOOP)，返回按分数降序排列的操作建议列表。
基于内容新颖度和与现有记忆的 trigram Jaccard 相似度计算。Memory-R1 启发。

```python
scores = mg.score_memory_ops("Python 是解释型语言")
# [{'op': 'ADD', 'score': 0.85, 'reason': 'novelty=1.00'}, ...]
```

#### `decide_memory_op(content, threshold=0.5, noop_bias=0.15) -> dict`

选择最优记忆操作。若 ADD 分数低于 threshold，降级为 NOOP。

#### `execute_memory_op(content, kind="fact", threshold=0.5, noop_bias=0.15, tags=None) -> dict`

端到端：决策 + 执行记忆操作。ADD 时创建节点，UPDATE 时合并到现有节点。

#### `memory_decision_log(items, threshold=0.5) -> list[dict]`

批量决策日志：对多条信息生成操作建议（不执行）。

#### `memory_audit(max_nodes=500, staleness_days=30) -> dict`

全局记忆审计：健康评分 (0-100) + 冗余分析 + 过期检测 + 平均重要性 + 改进建议。
MemoryArena (ICLR 2026) 启发的评估维度。

```python
audit = mg.memory_audit()
# {'health_score': 85, 'total_nodes': 120, 'redundant_pairs': 3,
#  'stale_nodes': 12, 'avg_importance': 0.72, 'noop_ratio': 0.1,
#  'suggestions': ['12 nodes untouched in 30d. Consider prune().']}
```

#### `fifa_forget(budget=50, min_importance=0.1) -> dict`

FiFA (Find-and-Forget) 有界遗忘策略：删除 budget 个最低重要性 + 最陈旧的节点。
选择性遗忘是 MemoryArena 核心能力。返回 `{removed, kept, details}`。

#### `memory_compact(similarity_threshold=0.7, max_merge_per_pass=20) -> dict`

记忆压缩：合并高相似度节点，减少冗余。返回 `{merged_count, details}`。

#### `memory_feedback(corrections) -> dict`

从反馈数据学习调整阈值 (AgeMem 在线学习启发)。
`corrections = [{content, correct_op, chosen_op, was_correct}, ...]`
返回 `{adjusted_threshold, adjustments, samples, false_adds, missed_adds}`。

#### `memory_stats_summary() -> dict`

记忆概览仪表盘：类型分布 + 权重分布 (高/中/低) + 时间跨度 + Top 5 加权节点。

```python
summary = mg.memory_stats_summary()
# {'total': 120, 'by_kind': {'fact': 80, 'event': 30, ...},
#  'weight_dist': {'high': 45, 'medium': 50, 'low': 25, 'avg': 0.58},
#  'time_span_days': 45.2, 'top_weighted': [...]}
```

### 向量时钟与增量同步（多 Agent 因果一致性）

> Vector clock 因果追踪 + pub/sub 事件通知 + 增量 delta 同步。
> 支持多 Agent 间的因果一致记忆同步。

#### `vector_clock(node_id) -> dict[str, int]`

返回节点的向量时钟（每个 writer agent 的因果版本号）。
用于 `merge_crdt` 和 `apply_changes` 检测并发更新 vs 因果排序。

```python
vc = mg.vector_clock("concept:ai")
# {'agent_a': 3, 'agent_b': 1}
```

#### `subscribe(callback) -> None`

注册节点变更事件回调。回调接收一个 dict：
`{event: 'add'|'update'|'delete'|'link', node_id, agent_id, timestamp}`。

```python
def on_change(evt):
    print(f"{evt['event']}: {evt['node_id']} by {evt['agent_id']}")

mg.subscribe(on_change)
mg.add("new_fact", "sky is blue")  # 触发回调
```

#### `get_changes(since=0.0) -> dict`

导出指定时间戳之后的所有节点/边变更（增量 delta）。
与 `apply_changes()` 配对使用，实现 Agent 间的增量同步。

```python
delta = mg.get_changes(since=time.time() - 3600)  # 最近 1 小时
# {'nodes': [...], 'edges': [...], 'timestamp': 1718700000.0}
```

#### `apply_changes(delta, agent_id="_remote", strategy="lww") -> dict`

应用来自另一个 Agent 的 delta（`get_changes()` 输出）。
使用向量时钟进行因果感知合并：

- `'before'`/`'equal'`: 跳过（本地相同或更新）
- `'after'`: 接受（远端更新）
- `'concurrent'`: 按 strategy 解决（`lww`/`or_set`/`trust`）

```python
summary = mg.apply_changes(remote_delta, agent_id="agent_b", strategy="lww")
# {'nodes_added': 5, 'nodes_updated': 2, 'nodes_skipped': 1,
#  'concurrent_conflicts': 0, 'edges_added': 3}
```

---

### memorywire 互操作

> [memorywire v0.1](https://arxiv.org/abs/2606.01138) 跨后端记忆交换格式。
> 5 种操作 (remember/recall/forget/merge/expire) × 4 种类型 (semantic/episodic/procedural/emotional)。

内部 kind 与 memorywire type 自动映射：

| 内部 kind | memorywire type |
|-----------|----------------|
| fact, concept | semantic |
| event, person | episodic |
| skill | procedural |
| emotion | emotional |

#### `to_memorywire(agent_id="default", node_ids=None) -> dict`

导出图谱记忆为 memorywire v0.1 wire format。生成 JSON 可序列化的 `remember` 操作列表，
可重放到任何 memorywire 兼容后端。包含节点数据、标签、关系和元数据。

```python
wire = mg.to_memorywire(agent_id="catalyst")
# {"version": "0.1", "agent_id": "catalyst",
#  "memories": [{"operation": "remember", "type": "semantic", ...}]}
```

#### `from_memorywire(wire_data) -> int`

导入 memorywire v0.1 格式数据到当前图谱。接受 `to_memorywire()` 输出或任何
memorywire 兼容的 `remember` 操作列表。自动创建节点和边。返回导入节点数。

```python
mg2 = MemoryGraph(":memory:")
mg2.from_memorywire(wire)  # → 120 (imported nodes)
```

---

### Agentic Workflow Memory (AWM)

> 从经验中学习的程序性记忆 — 记录成功/失败的工作流，挖掘跨轨迹模式，辅助 Agent 决策。

#### Workflow 生命周期

```python
# 记录一个工作流
wf_id = mg.add_workflow(
    ["search_docs", "read_api", "write_code", "run_tests"],
    outcome="success",
    context={"task": "add feature X"}
)

# 检索相似工作流
results = mg.retrieve_workflows("search_docs", limit=5)

# 记录结果
mg.record_workflow_outcome(wf_id, "success")

# 统计
stats = mg.workflow_stats()
# {'total': 42, 'successful': 35, 'failed': 7, 'success_rate': 0.83}

# 组合 + 去重
mg.workflow_compose(wf_id_1, wf_id_2)  # 合并两个工作流
mg.workflow_dedup()  # 去重相似工作流

# Tip 管理
mg.add_workflow_tip(wf_id, "always check types first")
tips = mg.retrieve_workflow_tips(wf_id)
mg.workflow_prompt_section(task="coding")  # 生成 LLM 上下文片段

# 剪枝 + 导出/导入
mg.workflow_prune_tips(max_tips=100)
mg.workflow_export()  # → JSON
mg.workflow_import(data)  # 批量导入

# 跨轨迹模式挖掘 (Cycle 141)
patterns = mg.workflow_success_patterns(min_frequency=2)
# [{'actions': ['search', 'read', 'implement'], 'frequency': 5, 'success_rate': 0.9}]

# 标签检索 (Cycle 142)
results = mg.workflow_retrieve_by_tag(["coding", "debug"], match_all=False)
```

#### 图差分与度分析

```python
# 人类可读的图差异摘要 (Cycle 142)
summary = mg.graph_diff_summary(mg2)
# 'Added 3 nodes, removed 1, changed 5 edges'

# 紧凑的度分布 (Cycle 142)
deg = mg.node_degree_summary(node_id)
# {'in_degree': 3, 'out_degree': 2, 'total': 5, 'by_relation': {'rel_a': 2}}
```

#### 标签关联与路径解释

```python
# 标签共现网络 (Cycle 143)
net = mg.tag_correlation_network(min_cooccurrence=2)
# {'edges': [{'tag_a': 'python', 'tag_b': 'async', 'weight': 5, 'correlation': 0.8}],
#  'strongest': {'tags': ('python', 'async'), 'correlation': 0.8}}

# 叙事路径渲染 (Cycle 143)
narrative = mg.memory_path_explain(start_id, end_id)
# 'Rust → contrasts_with → TypeScript → used_by → React'
```

### 记忆 Q-Value 与漂移检测

> MemRL (arXiv:2601.03192) + SSGM (arXiv:2603.11768) 启发的记忆质量评估。

```python
# Q-Value — 单节点效用评分 (Cycle 144)
q = mg.memory_qvalue(node_id)
# {'q_value': 0.72, 'components': {'frequency': 0.3, 'degree': 0.2, 'weight': 0.15, 'neighbor': 0.07}}

# 批量 Q-Value 排序
ranking = mg.memory_qvalue_batch(top_n=10)
# [{'node_id': 5, 'label': 'Python', 'q_value': 0.85}, ...]

# 漂移检测 — 三维度 (Cycle 144)
drift = mg.memory_drift_detect(node_id)
# {'semantic_drift': 0.12, 'structural_drift': 0.34, 'temporal_drift': 0.56,
#  'overall': 0.34, 'recommendation': 'review'}

# 批量漂移扫描
scan = mg.memory_drift_scan(threshold=0.3)
# [{'node_id': 7, 'overall': 0.42, 'recommendation': 'action'}, ...]
```

### 技能发现与利用率报告

> EvoSkill (arXiv:2603.02766) + SAGE (arXiv:2512.17102) 启发。

```python
# 从成功工作流中挖掘技能 (Cycle 145)
skills = mg.discover_skills(min_frequency=2, min_success_rate=0.7)
# [{'actions': ('search', 'read'), 'frequency': 8, 'success_rate': 0.88,
#   'retention_score': 0.75}]

# 执行仪表盘 (Cycle 145)
report = mg.memory_utilization_report()
# {'q_value_distribution': {...}, 'drift_summary': {...},
#  'workflow_coverage': 0.65, 'recommendations': [...]}
```

### 记忆强化与差距分析

```python
# 基于结果调整权重 (Cycle 146)
mg.memory_reinforce(node_id, outcome="positive", boost=0.1)
# weight: 0.5 → 0.6, audit trail updated
mg.memory_reinforce(node_id, outcome="negative", boost=0.1)
# weight: 0.6 → 0.54 (decay)

# 失败驱动的技能差距 (Cycle 146)
gaps = mg.skill_gap_analysis(min_failures=2)
# [{'missing_step': 'validate_input', 'gap_severity': 0.7,
#   'failed_workflows': 3, 'successful_with_step': 5}]
```

### 注意力评分与合并优先级

```python
# 时间注意力分数 (Cycle 147)
attention = mg.memory_attention_score(node_id, recency_window_hours=24)
# {'score': 0.68, 'components': {'recency_boost': 0.8, 'reinforcement_velocity': 0.5, 'neighbor_activity': 0.6}}

# 合并/驱逐优先级 (Cycle 147)
priority = mg.consolidation_priority(limit=10)
# [{'node_id': 12, 'priority': 0.82, 'drift': 0.5, 'q_value': 0.2, 'attention': 0.1}]
```

---

### OWASP ASI06: Provenance & Quarantine (Cycle 149)

Track memory origin and quarantine untrusted memories (OWASP ASI06 defense).

```python
# Set provenance — WHERE memory came from, HOW MUCH to trust it
mg.node_set_provenance(
    "person:alice",
    source="user_input",       # where it came from
    trust_level=0.8,           # 0.0-1.0 confidence
    parents=["person:bob"]     # derived-from nodes
)

# Quarantine a suspicious memory — excluded from recall/search/neighbors
mg.node_quarantine("person:alice", reason="suspected injection")

# Release from quarantine
mg.node_unquarantine("person:alice")

# List all quarantined nodes
mg.quarantine_list()
# [{'id': 'person:eve', 'label': 'Eve', 'kind': 'person',
#   'trust_level': 0.1, 'source': 'external_api',
#   'quarantine_reason': 'auto: trust_level below 0.3'}]

# Auto-quarantine low-trust nodes (batch)
newly_quarantined = mg.quarantine_scan(trust_threshold=0.3)
# ['person:eve', 'concept:unverified_1']
```

**Schema additions:** `source`, `trust_level`, `parents`, `quarantined`, `quarantine_reason` columns on `nodes` table.

**Retrieval safety:** `recall()`, `search_by_tag()`, and `neighbors()` automatically exclude quarantined nodes.

### 记忆生命周期分析

> 三个层次的记忆健康分析：个体生命周期、访问模式、全局健康 KPI。

#### `memory_lifecycle_report() -> dict`

统一记忆生命周期仪表盘 — 将访问时效、权重分布、衰减状态、合并状态、隔离健康和强化活动整合到一份执行报告中。

**4 层访问时效：**

| 层级 | 窗口 | 说明 |
|------|------|------|
| `active` | 7 天内 | 活跃使用中 |
| `stale` | 7-30 天 | 近期有访问 |
| `decaying` | 30-90 天 | 衰减中 |
| `dormant` | 90 天+ | 休眠 |

**5 桶权重分布：** `critical (<0.1)` / `low (0.1-0.3)` / `medium (0.3-0.5)` / `high (0.5-0.8)` / `peak (≥0.8)`

**5 阶段生命周期：** `seed` / `thriving` / `active` / `declining` / `maintenance`

```python
report = mg.memory_lifecycle_report()
# {
#   'total_nodes': 120,
#   'active_nodes': 45, 'stale_nodes': 30,
#   'decaying_nodes': 25, 'dormant_nodes': 20,
#   'avg_weight': 0.52,
#   'weight_distribution': {'critical': 5, 'low': 20, 'medium': 35, 'high': 40, 'peak': 20},
#   'quarantine_count': 2,
#   'consolidated_count': 15,
#   'reinforcement_events': 42,
#   'lifecycle_stage': 'active',
#   'recommendations': ['20 dormant nodes detected. Consider prune() or consolidation.'],
# }
```

#### `memory_access_pattern(*, days=30) -> dict`

时间访问模式分析 — 按类型分组，识别访问热点（频繁访问）和冷点（从未/极少访问），计算访问速度，检测昼夜偏差。

**Kind 温度分类：**

| 温度 | 条件 | 说明 |
|------|------|------|
| `hot` | 访问率 > 70% | 高频访问 |
| `warm` | 30%-70% | 正常访问 |
| `cold` | < 30% | 冷淡记忆 |

**4 种推荐：** `high_cold_ratio` / `low_access_velocity` / `diurnal_bias` / `balanced`

```python
pattern = mg.memory_access_pattern(days=30)
# {
#   'window_days': 30,
#   'total_nodes': 120,
#   'hot_nodes': 45, 'cold_nodes': 35,
#   'access_velocity': 0.38,
#   'diurnal_bias': {'peak_hour': 14, 'concentration': 0.65},
#   'kind_temperature': {'fact': 'hot', 'event': 'cold', 'concept': 'warm'},
#   'recommendations': ['High cold ratio (29%). Consider recall() boost or prune.'],
# }
```

#### `memory_health_score() -> dict`

综合健康评分（0-100） — 将五个维度整合为一个执行 KPI，附带字母等级和问题标记。

**5 维度加权：**

| 维度 | 权重 | 衡量内容 |
|------|------|----------|
| Vitality | 30 | 平均权重 + 活跃比率 |
| Integrity | 20 | 隔离率惩罚 |
| Connectivity | 20 | 图密度 + 边覆盖率 |
| Diversity | 15 | Kind 分布均匀度（Shannon 熵） |
| Maintenance | 15 | 合并 + 强化追踪 |

**字母等级：** A (≥80) / B (≥65) / C (≥50) / D (≥35) / F (<35)

**6 种问题标记：** `low_vitality` / `quarantine_backlog` / `poor_connectivity` / `low_diversity` / `no_maintenance` / `healthy`

```python
health = mg.memory_health_score()
# {
#   'score': 72.5,
#   'grade': 'B',
#   'dimensions': {
#     'vitality': 22.0, 'integrity': 18.5,
#     'connectivity': 14.2, 'diversity': 10.8, 'maintenance': 7.0,
#   },
#   'issues': ['low_diversity: only 2 kinds present'],
#   'trends': {'avg_weight': 0.52, 'quarantine_ratio': 0.017},
# }
```

---

### Diffusion 检索 (ExpGraph 启发)

#### `diffusion_retrieve(query="", *, seeds=None, embedding=None, limit=10, alpha=0.15, max_iter=50, tol=1e-4, edge_weight_factor=1.0, merge_bm25=True, bm25_boost=0.3, explain=False) -> list[dict]`

Personalized PageRank 扩散检索 — 用图扩散替代固定跳数 BFS 邻域展开。

Seed 节点通过 BM25 / 向量搜索识别，然后 PPR 在图上传播相关性分数，
随图距离自然衰减。研究到生产 <24h（源自 ExpGraph + Memory-R1 研究）。

```python
results = mg.diffusion_retrieve("memory consolidation", limit=5)
# [{node_id: 'n42', label: 'Memory Replay', kind: 'concept',
#   score: 0.87, diffusion_score: 0.72, bm25_score: 0.95,
#   hop_distance: 2, sources: ['bm25', 'diffusion']}, ...]

# 保守扩散（更大的 alpha = 更靠近 seed）
results = mg.diffusion_retrieve("attention", alpha=0.3, limit=10)

# 调试模式：查看扩散路径
results = mg.diffusion_retrieve("forgetting", explain=True)
# 额外返回 diffusion_paths 和 step_scores

# 使用向量 embedding 发现 seed
results = mg.diffusion_retrieve(
    embedding=[0.1, 0.3, ...], merge_bm25=False, limit=5
)
```

**关键参数：**
- `alpha`: 随机游走重启概率（0.15 标准 PPR，0.3 保守）
- `edge_weight_factor`: 边权重指数（1.0 线性，0.5 阻尼强边，2.0 放大）
- `merge_bm25`: 是否混合 BM25 相关性分数
- `bm25_boost`: BM25 权重（0-1），剩余部分为扩散权重

---

## 测试

```bash
python3 -m pytest test_memory_graph.py -q
```

1554 个测试覆盖所有 API。

## 设计思路

1. **Agent 记忆应该用什么结构？** — 图谱比列表更适合表达关联
2. **如何避免记忆膨胀？** — 遗忘曲线是自然的"垃圾回收"
3. **如何模拟人类回忆？** — recall 时增强 + 关联遍历 = 上下文感知
4. **子图提取** — 让 Agent 聚焦相关记忆，适配有限的 context window
5. **图算法** — PageRank 发现重要记忆，社区发现识别知识领域
6. **演化追踪** — 记忆不是静态的，记录概念的演变过程
7. **快照与恢复** — Agent 实验"如果改变这个记忆会怎样"，然后回滚
8. **向量搜索** — sqlite-vec 可选集成，三路 RRF 混合搜索 (文本+向量+图) 是 npm/PyPI 唯一三合一方案
9. **BM25 + GraphRAG** — 全文索引 + 社区级检索，从关键词搜索到知识图谱问答的完整路径
10. **LLM 适配** — to_markdown + context_window + prune_by_relevance 让图谱直接服务于 LLM 上下文
11. **网络分析** — global_efficiency + s_metric + effective_eccentricity + local_efficiency + wiener_index + onion_structure + minimum_spanning_tree + resistance_distance + algebraic_connectivity + spectral_radius + triad_census + average_neighbor_degree + degree_correlation + node_similarity 量化记忆网络的全局与局部拓扑特性
12. **可学习记忆管理** — Memory-R1/AgeMem 启发的自动 CRUD 决策 + MemoryArena 审计 + FiFA 有界遗忘 + 反馈学习，让 Agent 自主管理记忆生命周期
13. **memorywire 互操作** — to_memorywire/from_memorywire 实现跨后端记忆交换，标准化语义/情景/程序/情感四种记忆类型的导入导出
14. **图探索与采样** — random_walk（带重启的加权随机游走）+ graph_sample（BFS/DFS/random_walk 三策略子图采样），服务于图嵌入预处理和 GraphRAG 局部探索
15. **鲁棒社区检测** — lazy_community_detect 采用 Leiden 启发的随机化节点迭代 + 模块度回退机制，避免对称图上的标签级联问题
16. **网络拓扑分析** — degree_distribution (Shannon 度分布熵) + network_summary (综合仪表盘) + k_hop_neighbors + common_neighbors + graph_entropy + connectivity_frontier + degree_centrality_normalized (Freeman) + edge_density_subgraph + weighted_degree + neighborhood_census 量化记忆网络的多维度拓扑特征
17. **多智能体记忆合并** — merge_crdt 实现 CRDT-based 多 Agent 记忆图合并，支持 LWW (Last-Write-Wins)、OR-Set (Add-Remove Set) 和 Trust-weighted 三种合并策略，确保分布式场景下的记忆一致性
18. **向量时钟与增量同步** — vector_clock 因果追踪 + subscribe pub/sub 事件通知 + get_changes/apply_changes 增量 delta 同步，实现多 Agent 间因果一致的记忆同步，支持 LWW/OR-Set/Trust 冲突解决策略
19. **Agentic Workflow Memory (AWM)** — add_workflow/retrieve_workflows/record_workflow_outcome + workflow_compose/dedup + tip 管理 + success_patterns 跨轨迹模式挖掘 + retrieve_by_tag 标签检索，构建 Agent 的程序性记忆：从经验中学习成功路径
20. **记忆 Q-Value 与漂移检测** — memory_qvalue (MemRL 启发) 用访问频率/度/权重/邻居传播近似 Q 值，memory_drift_detect (SSGM 启发) 从语义/结构/时间三维度检测记忆漂移，服务于 evict/consolidate 决策
21. **技能发现与利用率** — discover_skills (EvoSkill/SAGE 启发) 从成功 workflow 中挖掘共现行动对，memory_utilization_report 汇总 Q 值分布/漂移/覆盖率/建议的执行仪表盘
22. **记忆强化与差距分析** — memory_reinforce 根据观察结果调整权重并记录审计轨迹，skill_gap_analysis (EvoSkill) 对比失败/成功 workflow 找出缺失的中间步骤
23. **注意力评分与合并优先级** — memory_attention_score 结合时效性/强化速度/邻居活跃度的时间注意力分数，consolidation_priority 综合 drift×(1-Q)×(1-attention) 排序合并/驱逐候选
24. **生命周期仪表盘** — memory_lifecycle_report 统一生命周期报告：4 层访问时效（active/stale/decaying/dormant）+ 5 桶权重分布 + 5 阶段生命周期分类 + 隔离/合并/强化追踪 + 6 种建议
25. **访问模式分析** — memory_access_pattern 时间访问模式分析：冷热分类（hot/cold/warm per-kind）、访问速度（utilization metric）、昼夜偏差检测（hour-of-day concentration）、4 种推荐
26. **健康评分 KPI** — memory_health_score 综合健康评分（0-100）：5 维度加权（Vitality 30 + Integrity 20 + Connectivity 20 + Diversity 15 + Maintenance 15）+ 字母等级（A-F）+ 问题标记
27. **Diffusion 检索** — diffusion_retrieve 实现 ExpGraph 启发的 Personalized PageRank 扩散检索：BM25/向量识别 seed → PPR 传播分数 → 边权重感知衰减 → BM25 混合排序。从研究到生产 <24h 的案例（ExpGraph + Memory-R1 → diffusion_retrieve）

## 许可

MIT
