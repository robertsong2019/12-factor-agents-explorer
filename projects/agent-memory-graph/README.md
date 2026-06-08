# Agent Memory Graph

> 基于 SQLite 的轻量知识图谱，模拟 AI Agent 的长期记忆管理

[![Tests](https://img.shields.io/badge/tests-811-brightgreen)]()
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
3. **图邻居加权**: 种子节点的邻居 bonus

返回 `{node_id, label, kind, score, sources}` 按融合分数降序。向量不可用时静默降级。

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

## 测试

```bash
python3 -m pytest test_memory_graph.py -q
```

811 个测试覆盖所有 API。

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
11. **网络分析** — global_efficiency + s_metric + effective_eccentricity + local_efficiency + wiener_index + onion_structure 量化记忆网络的全局与局部拓扑特性

## 许可

MIT
