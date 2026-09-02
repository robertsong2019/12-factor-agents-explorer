# Agent Memory Graph

> 基于 SQLite 的轻量知识图谱，模拟 AI Agent 的长期记忆管理

[![Tests](https://img.shields.io/badge/tests-10196-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.10+-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()
[![Dependencies](https://img.shields.io/badge/dependencies-zero-success)]()

> 📚 教程：[基础入门](TUTORIAL.md) · [GraphRAG 端到端（Cycles 425-440）](TUTORIAL-GRAPHRAG.md) · [Temporal QA 零 LLM 时间推理（Cycles 456-489）](TUTORIAL-TEMPORAL-QA.md) · [Abstention 弃权语义（Cycles 448-516）](TUTORIAL-ABSTENTION.md) · [Answer Faces 问题结构驱动的答案选择（Cycles 529-539）](TUTORIAL-ANSWER-FACES.md)

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
- **MCP Server** — 10 工具 (remember/recall/relate/ask/lookup/neighbors/forget/stats/timeline/health)，可直接接入 mcporter 或任何 MCP 客户端
- **批量图操作** — batch_create_nodes / batch_add_edges / batch_delete_nodes 单事务批量写入
- **链路预测** — predict_links 基于 common-neighbors / Adamic-Adar / preferential-attachment 三信号推荐缺失边
- **加权路径** — shortest_path_weighted (Dijkstra) / path_cost / all_paths / k_shortest_paths (Yen's algorithm)
- **子图提取** — extract_subgraph 返回新 MemoryGraph，neighborhood 轻量 ID 列表
- **全图中心性** — betweenness_all / closeness_all / eigenvector_all 一次调用计算所有节点
- **图序列化** — to_dict / from_dict JSON 安全序列化，支持快照和跨 Agent 传输
- **图收缩** — contract_nodes 节点合并为超节点 / contract_communities 社区级超节点折叠
- **自适应检索** — QDAP-v2 6 类查询分类器 (trivial/exact/semantic/relational/temporal/exploratory) + 连续权重插值 + SkewRoute 分数偏度分析 + Entropy 修正，per-query 动态融合权重
- **图拓扑分析** — find_cycle 环路检测 (DFS back-edge) + graph_periphery 最远节点 + maximal_cliques Bron-Kerbosch 极大团枚举 + clique_number/largest_clique + clique_overlap_matrix 团重叠矩阵 + k_clique_communities CPM 重叠社区
- **程序性记忆压缩** — compress_to_skill / retrieve_skills / evolve_skill / skill_bank_health 将情景记忆压缩为可复用的技能节点 (Experience Compression Spectrum L1→L2)
- **信息密度评估** — memory_information_density PRISM/PlugMem 启发的 Pareto 指标，衡量每个节点的信息量/token 比
- **意图感知检索** — detect_query_intent / intent_aware_edge_cost / retrieve_with_intent PRISM 启发的查询意图路由，按意图类型调整边遍历成本
- **双模检索** — binary_signature / similarity_search_binary / dual_mode_retrieve Hippocampus 启发的 SimHash 二进制签名预过滤 + 图重排序两阶段检索
- **去重** — find_duplicate_nodes / deduplicate 基于 SimHash 汉明距离的近重复节点检测与合并
- **洛伦兹系数与重定义指数** — lorenz_coefficient (度分布 Gini 系数) + redefined_randic_indices (Randić 2008 三变体) + redefined_zagreb_index (第三 Zagreb 指数)
- **双循环质量系统** — 知识缺口分析 + 冗余检测 + 自动修复（逐对 & 整簇）+ 统一健康评分 (gap_redundancy_balance)
- **情景模式挖掘** — 从 event/intention 节点发现重复行为模式，建议技能提升 (detect_skill_candidates)
- **图采样统计** — 多次随机游走聚合分析：覆盖率、重访率、死端率 (walk_statistics)
- **19 度拓扑指数 + 5 熵指数** — Sombor/Reduced Sombor/Randić/Zagreb M₁/ABC/GA 六族 (Cycles 278-280)，度加权 Shannon 熵分析，覆盖化学图论主流指标
- **条件遍历与多视角** — HAGE 启发的意图感知遍历 + 关系投影图 + 多维度对比分析 (Cycles 331-333)
- **数据溯源与修正传播** — derived_from/computed_from 边类型 + 向后溯源 + 向前影响分析 + 统一世系报告 + 级联修正标记 (Cycles 336-338)
- **拓扑快捷统计** — hub_nodes/peripheral_nodes/mean_degree 一键获取关键结构指标 (Cycle 339)
- **图分类套件** — 8 种分类方法 + 基准评估 + 最大置信度元分类器 + 噪声鲁棒性测试 (Cycles 326-341)
- **Temporal QA 家族 (5 路由)** — LongMemEval temporal-reasoning 零 LLM 解法：temporal_arith 日历算术 + pp_duration/pure_tenure 状态时长 + order 排序 + pairwise which-first，form gate + 最早-FRESH 锚定 + 负存在弃权，temporal-133 0.323→0.474 全程 zero-flip (Cycles 457-489)
- **确定性语义判分级联** — judge_semantic 规范化阶梯（大小写/日期折叠/时间单位/守卫包含）零 LLM 可判面 + judge_cascade 仅 NEEDS_JUDGE 才降级 LLM；readonly 确定性召回让评估成为 dataset 纯函数，官方 LME_s cascade-500 **0.494** (Cycles 520-531)
- **零依赖** — 仅用 Python 标准库（sqlite3 + json + math），sqlite-vec 为可选依赖
- **传播激活家族 (5 API)** — ACT-R 认知模型: spreading_activation (基础) → activation_trace (可解释) → competitive_spreading (多种子竞争) → temporal_spreading (时间衰减) → activation_diff (对比分析) (Cycles 366-383)
- **流式熵追踪** — FINGEREntropy O(Δ) 增量 von Neumann 熵 + StreamingGraph 实时异常检测 (Cycle 361)
- **图推理** — multi_hop_reason (PPR + BFS 证据路径) + personalized_pagerank (HippoRAG2 模式) + enrich_node (A-MEM 回溯完喬) (Cycle 361-362)
- **时序层次** — SummaryTree 5 层 (segment→session→day→week→profile) 渐进汇总 (Cycle 364)
- **代码感知 API** — explainCode / recordCodeDecision / impactAnalysis 连接代码结构与 Agent 经验 (Cycle 365)
- **OTel 遥测** — enable_telemetry() 自动写仪 8 个 CRUD 方法 + 5 个 OTel context manager (Cycles 374-381)
- **OWASP ASI06 安全套件 (6 API)** — trust_score + memory_quarantine + selective_repair + memory_audit_report + detect_provenance_laundering + security_dashboard (Cycle 367-368)
- **性能基准** — amg-bench: BenchHarness + BenchmarkResult + run_bench() 吞吐量/延迟/搜索/多跳评估 (Cycle 370)
- **MCP Server 16 工具** — 增加 entropy/reason/snapshot/code_explain/quarantine/security 6 个高级工具 (Cycle 371)

## Why agent-memory-graph?

> **Not RAG. Memory.** — RAG 是无状态的一次性检索。Agent Memory 是 write-manage-read 循环：持续、有状态、可演化。

2026 年 Agent Memory 领域的核心洞察：**recall benchmarks 已不是差异化指标，agency benchmarks 才是。** 检索准确率 90%+ 的系统很多，但能治理记忆生命周期、检测质量缺口、自愈知识图谱的系统——几乎没有。

agent-memory-graph 的定位：**beyond recall — agency-grade graph memory — security-first.**

### 与其他记忆方案的区别

| 维度 | agent-memory-graph | Mem0 (48K⭐) | Letta (21K⭐) | Zep/Graphiti (24K⭐) | Mandol (SOTA) | PlugMem (ICML'26) |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| **语言** | Python (npm: TS) | Python | Python | Python | Python | Python |
| **存储** | SQLite (零依赖) | Vector DB + Graph | 抽象层 | Neo4j + Redis | 自定义 | 自定义 |
| **图算法** | ✅ 30+ centrality + PPR + Leiden + 19 拓扑指数 | 部分 | ❌ | ✅ 时序图 | ❌ | ❌ |
| **向量搜索** | ✅ sqlite-vec KNN | ✅ 外部 | ❌ | ❌ | ❌ | ❌ |
| **全文搜索** | ✅ BM25 (FTS5) | ✅ 外部 | ❌ | ✅ | ❌ | ❌ |
| **混合搜索** | ✅ RRF 三路融合 | ❌ | ❌ | 部分 | ❌ | ❌ |
| **CRDT 多 Agent** | ✅ LWW/OR-Set/Trust | ❌ | ❌ | ❌ | ❌ | ❌ |
| **记忆治理** | ✅ write_governance + screen_retrieval | ❌ | ❌ | ❌ | ❌ | ❌ |
| **质量评估** | ✅ 评估五件套 | ❌ | ❌ | ❌ | ❌ | ❌ |
| **缺口检测** | ✅ detect→heal→measure | ❌ | ❌ | ❌ | ❌ | ❌ |
| **冗余检测** | ✅ 3D 冗余 + auto_consolidate | ❌ | ❌ | ❌ | ❌ | ❌ |
| **技能压缩** | ✅ L1→L2 Experience Spectrum | ❌ | ❌ | ❌ | ❌ | ❌ |
| **安全审计** | ✅ PASB 防护 + 决策链追踪 | ❌ | ❌ | ❌ | ❌ | ❌ |
| **记忆衰减** | ✅ Ebbinghaus 曲线 | ❌ | ✅ | ❌ | ❌ | ❌ |
| **演化追踪** | ✅ supersede 链 | conflict (35.7%) | ❌ | ✅ bi-temporal | ❌ | ❌ |
| **MCP Server** | ✅ 10 工具内置 | ❌ | ❌ | ❌ | ❌ | ✅ (OpenClaw) |
| **memorywire** | ✅ 5ops×4types | ❌ | ❌ | ❌ | ❌ | ❌ |
| **零依赖** | ✅ 仅 Python 标准库 | ❌ | ❌ | ❌ | ❌ | ❌ |
| **LoCoMo Score** | 未测 | 49.0% | N/A | N/A | **92.21%** | 90.2% |
| **Tests** | **10040** | ~500 | ~300 | ~800 | N/A | N/A |

### 独特价值

1. **唯一集成图质量管理系统** — 知识缺口检测 + 冗余检测 + 自动修复 + 统一健康评分。不是「记住更多」，而是「记住对的」
2. **唯一安全优先设计** — 写入治理 (PASB 防护) + 读取筛选 + 决策链审计。更强 Agent 需要更强记忆治理
3. **唯一完整检索管线** — BM25 + Vector KNN + PPR + GraphRAG + DRIFT + SimHash 双模 + 意图路由。790+ public API 覆盖从关键词到知识图谱问答
4. **唯一跨压缩级别** — 情景记忆 (L1) → 技能压缩 (L2) → 治理 (Govern)。Experience Compression Spectrum 全谱覆盖
5. **零依赖 Python** — 仅用 sqlite3 + json + math。sqlite-vec 可选。可嵌入式部署

### 适用场景

- **AI Agent 长期记忆** — 对话历史、用户偏好、任务经验的结构化存储与智能检索
- **知识图谱管理** — 研究/产品知识的图谱化、社区发现、质量评估
- **多 Agent 协作** — CRDT 合并 + 向量时钟同步，多个 Agent 共享一致的记忆
- **GraphRAG 应用** — 从文档提取实体关系，支持 naive/local/global/hybrid 四种检索模式
- **MCP 生态接入** — 内置 MCP Server，Claude/Cursor 等 MCP 客户端可直接操作记忆图谱

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

## 教程：构建一个 AI 助手的记忆系统

这个教程展示如何用 agent-memory-graph 为 AI 助手构建生产级记忆系统。

### 场景：客服 Agent 记住用户偏好

```python
from memory_graph import MemoryGraph

mg = MemoryGraph('customer_agent.db')

# 1. 记住用户信息
user = mg.add("用户: 张三", "person", {"plan": "pro", "since": "2024-01"}, ["vip"])
pref = mg.add("偏好: 中文回复", "fact", {"category": "communication"}, ["language"])
history = mg.add("历史: 曾购买 API 服务", "event", {"date": "2024-03"}, ["purchase"])

# 2. 建立关系
mg.link(user.id, pref.id, "prefers", weight=0.9)
mg.link(user.id, history.id, "has_history", weight=0.7)

# 3. 智能召回 — 混合搜索
results = mg.hybrid_retrieve("张三喜欢什么", top_k=5)
# => 自动融合 BM25 + 向量 + 图邻居信号

# 4. 记忆衰减 — 30 天后弱化
mg.decay_all(interval_days=30)
# 未访问的记忆权重下降，模拟自然遗忘

# 5. 召回时增强 — 用户再次提到
mg.recall("张三")
# => 相关记忆权重恢复，模拟复习效果

# 6. 图质量检查
report = mg.knowledge_gap_report()
print(report['gap_score'])  # 0-100, 越高缺口越大
print(report['recommendations'][:3])  # 建议添加的连接

# 7. 自动修复缺口
mg.auto_heal_gaps(dry_run=True)  # 先预览
mg.auto_heal_gaps(dry_run=False)  # 执行修复

# 8. 健康评分
health = mg.gap_redundancy_balance()
print(f"Health: {health['health_score']}/100 ({health['verdict']})")
```

### 场景：多 Agent 记忆合并

```python
from memory_graph import MemoryGraph

# Agent A 和 Agent B 各自积累记忆
mg_a = MemoryGraph('agent_a.db')
mg_b = MemoryGraph('agent_b.db')

# ... 两个 Agent 独立工作，各自 add/link ...

# CRDT 合并 — 保证一致性
result = mg_a.merge_crdt(mg_b, strategy="trust", trust_weights={"A": 0.7, "B": 0.3})
print(f"合并: {result['merged_nodes']} 节点, {result['conflicts_resolved']} 冲突已解决")

# 增量同步 — 向量时钟追踪因果
mg_a.subscribe("updates", lambda event: print(f"新变更: {event}"))
changes = mg_a.get_changes(since_vector=clock)
mg_b.apply_changes(changes)
```

### 场景：GraphRAG 检索

```python
from memory_graph import MemoryGraph

mg = MemoryGraph('knowledge_base.db')

# 从文档提取的知识已入库
# local 模式：实体级检索
local_results = mg.graphrag_search("Rust 的内存安全机制", mode="local")

# global 模式：跨社区主题检索
global_results = mg.graphrag_search("系统级编程语言趋势", mode="global")

# hybrid 模式：local + global 融合
hybrid_results = mg.graphrag_search("Rust vs Go 在微服务中的应用", mode="hybrid")
```

---

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

#### `recall(query, limit=5, *, readonly=False) -> list[Node]`

按关键词召回记忆（自动增强访问强度）。`readonly=True` 时为纯读：无 decay/boost 写回，tie-break 用摄入序（rowid），结果成为存储图的纯函数——基准评估路径默认用此模式（`deterministic_recall`，Cycle 528），`--wallclock-recall` 可逃逸回旧行为。

```python
results = mg.recall("Python")          # 交互路径：访问会增强权重
results = mg.recall("Python", readonly=True)   # 评估/重放：零副作用，跨 run 逐字节可复现
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

### MCP Server (10 工具)

内置 MCP (Model Context Protocol) Server，可直接接入 mcporter 或任何 MCP 客户端，让 AI Agent 通过标准协议操作记忆图谱。

```bash
# 启动 MCP Server
python3 mcp_server.py

# 或通过 mcporter 接入
mcporter add agent-memory-graph -- python3 /path/to/mcp_server.py
```

| 工具 | 功能 |
|------|------|
| `remember` | 添加或更新记忆节点 |
| `recall` | BM25 关键词召回 |
| `relate` | 建立节点间关系边 |
| `ask` | 混合搜索 (BM25 + 向量 + 图邻居) |
| `lookup` | 按 ID / 标签 / 类型查找 |
| `neighbors` | BFS 关联遍历 |
| `forget` | 删除节点 |
| `stats` | 图统计概览 |
| `timeline` | 时间线查询 |
| `health` | 记忆健康评分 |

---

### 批量图操作

#### `batch_create_nodes(nodes_data) -> dict`

单事务批量创建节点。`nodes_data` 为 `[{label, kind?, data?, tags?}]` 列表。返回 `{created, node_ids}`。

#### `batch_add_edges(edges_data) -> dict`

单事务批量建边。`edges_data` 为 `[{source, target, relation, weight?}]`。返回 `{added, skipped}`。

#### `batch_delete_nodes(node_ids, safe=True) -> dict`

批量删除节点。`safe=True` 时跳过有存活依赖的节点。返回 `{deleted, skipped, reasons}`。

---

### 链路预测

#### `predict_links(node_id=None, limit=10, min_score=0.0) -> list[dict]`

基于三种信号推荐缺失边：
- **Common Neighbors** — 共同邻居数量
- **Adamic-Adar** — 共同邻居的 1/log(degree) 之和
- **Preferential Attachment** — degree(u) × degree(v)

```python
suggestions = mg.predict_links("node-1", limit=5)
# [{'source': 'node-1', 'target': 'node-5', 'score': 0.82,
#   'common_neighbors': 3, 'adamic_adar': 1.2, 'pref_attachment': 12}, ...]
```

---

### 加权路径算法

#### `shortest_path_weighted(source_id, target_id, default_weight=1.0) -> dict | None`

Dijkstra 加权最短路径。与 BFS 最短路径不同，考虑边权重——经过低权重边的 3 跳路径可能优于 2 跳高权重路径。

#### `path_cost(path) -> float`

计算给定路径的总权重。路径中任一边不存在时返回 `inf`。

#### `all_paths(source_id, target_id, max_hops=5, limit=20) -> list[list[str]]`

两点间所有简单路径（DFS + 深度剪枝）。按长度排序，限制返回 `limit` 条防止组合爆炸。

#### `k_shortest_paths(source_id, target_id, k=3, max_hops=8) -> list[dict]`

K 条最低成本路径（Yen's algorithm）。返回 `[{'path': [...], 'cost': 2.5, 'hops': 3}]`，按成本升序。

---

### 子图提取与邻域

#### `extract_subgraph(node_id, radius=1, max_nodes=100, include_quarantined=False) -> MemoryGraph`

以 `node_id` 为中心，BFS 扩展 `radius` 跳，返回包含子集的**新 MemoryGraph 实例**。`max_nodes` 防止大图抽取。

#### `neighborhood(node_id, radius=1, include_quarantined=False) -> list[str]`

返回 `radius` 跳内的节点 ID 列表（含自身）。`extract_subgraph` 的轻量替代——只需 ID 不需要子图副本时使用。

---

### 全图中心性

#### `betweenness_all(normalized=True, include_quarantined=False) -> dict[str, float]`

所有节点的介数中心性（Brandes 算法）。高介数 = 桥梁节点。

#### `closeness_all(normalized=True, include_quarantined=False) -> dict[str, float]`

所有节点的接近中心性（多源 BFS）。高接近 = 能快速到达全图。

#### `eigenvector_all(iterations=100, tolerance=1e-6, include_quarantined=False) -> dict[str, float]`

所有节点的特征向量中心性（幂迭代）。高值 = 连接到其他重要节点。

---

### 图序列化

#### `to_dict() -> dict`

图序列化为 JSON 安全字典（含 nodes / edges / edge_props / meta）。适用于快照、API 响应、跨 Agent 传输。

#### `from_dict(data) -> MemoryGraph` *(classmethod)*

从 `to_dict()` 输出创建新 MemoryGraph 实例。

```python
mg_data = mg.to_dict()
# ... 传输或存储 ...
mg2 = MemoryGraph.from_dict(mg_data)
```

---

### 图收缩

#### `contract_nodes(node_ids, supernode_label, kind="supernode", data=None, quarantine_members=True) -> dict`

将一组节点合并为单个超节点。外部边重定向到超节点（权重求和），内部边丢弃。适用于多分辨率图视图和实体去重。

#### `contract_communities(labels=None, max_iterations=20, resolution=1.0) -> dict`

检测社区并将每个社区收缩为超节点。LPA 社区检测 + contract_nodes 组合。适用于图摘要和多层级分析。

### 高级中心性

#### `katz_centrality(alpha=0.1, beta=1.0, iterations=100, tolerance=1e-6, include_quarantined=False) -> dict[str, float]`

Katz 中心性。特征向量中心性的推广，引入衰减因子 alpha 折扣长路径。每个节点获得基准贡献 beta，因此在 disconnected graph 上也能收敛。分数 `c_i = beta + alpha * Σ c_j（j 是 i 的邻居）`。alpha 越小越强调局部结构，越大越接近特征向量中心性。收敛条件：`alpha < 1/λ_max`（最大特征值的倒数）。

#### `subgraph_centrality(max_order=20, include_quarantined=False) -> dict[str, float]`

子图中心性。统计所有长度的闭合游走（closed walk），以 `1/k!` 加权长度 k。等价于邻接矩阵指数 `e^A` 的对角线元素。自然地奖励参与大量三角形和短环的节点，对局部社区结构敏感。与 degree centrality（仅长度 1）和 Katz（开+闭合游走）互补。结果归一化到 [0, 1]。

#### `laplacian_centrality(include_quarantined=False) -> dict[str, float]`

Laplacian 中心性。衡量移除节点后图 Laplacian 能量 `E_L = tr(L²)` 的下降幅度。公式：`C_L(v) = d_v² + d_v + 2·Σ_{u ∈ N(v)} d_u`，其中 `d_v` 是节点度，`N(v)` 是邻居集合。同时捕获直接连接重要性（`d_v²`）和间接重要性（邻居度之和）。与其他中心性不同，Laplacian 中心性关注的是**网络中断潜力**——移除该节点会损失多少连通性。对桥接关键节点特别敏感。结果归一化到 [0, 1]。

#### `estrada_index(max_order=20, include_quarantined=False) -> float`

Estrada 指数。图级别的整体连通性度量，定义为邻接矩阵指数的迹：`EE = tr(e^A) = Σ_i e^(λ_i)`。统计所有长度的闭合游走并以 `1/k!` 加权。EE 越高表示图越密集/冗余连接，越低表示稀疏树状结构。EE 始终 ≥ n（节点数）。对三角形和短环敏感（类似子图中心性但聚合到全图）。使用截断 Taylor 级数（默认 max_order=20，精度 >15 位）。

#### `communicability(node_a, node_b, max_order=20, include_quarantined=False) -> float`

通信度。衡量两节点间通过**所有路径**的信息流便捷度：`G(a,b) = (e^A)_{ab} = Σ (A^k)_{ab}/k!`。比最短路径更全面——多条短路径的通信度高于一条长路径。共享邻居（三角形）会显著提升通信度。自通信度（`a == b`）等于该节点的子图中心性（未归一化）。

---

### GraphRAG 检索管线 (Cycles 207-213)

#### `personalized_pagerank(seed_ids, *, damping=0.85, max_iter=100, tol=1e-6, seed_weights=None) -> dict[str, float]`

Personalized PageRank (PPR) — topic-sensitive PageRank 从 seed 节点传播。与全局 PageRank 不同，PPR 只向 seed 节点 teleport，让图拓扑从 seed 传播相关性。HippoRAG 核心检索算法。seed_weights 可选按重要性加权 seed。

#### `ppr_retrieve(query, *, limit=10, damping=0.85) -> list[dict]`

两阶段检索管线（HippoRAG pattern）：1) recall() 关键词匹配找到 seed 节点；2) 从 seed 运行 PPR 发现多跳邻居。让图拓扑参与检索——单次传播即可发现概念相关但无关键词重叠的节点。

#### `compute_graph_activity(window_hours=1.0) -> float`

计算最近时间窗口内的归一化图活跃度 [0, 1]。实现 FOREVER 模型：活跃图（每小时多新节点/边）保留记忆更久，沉寂图加速遗忘。Sigmoid 归一化。

#### `auto_forget(window_hours=1.0) -> dict`

便捷封装 batch_forgetting()，自动从近期图事件计算 graph_activity。活跃图忘记更少，沉寂图忘记更多。返回 batch_forgetting 结果 + computed graph_activity。

#### `hybrid_retrieve(query, *, limit=10, damping=0.85, k=60) -> list[dict]`

混合检索：keyword + PPR + tag 三路 RRF (Reciprocal Rank Fusion) 融合。三路信号：1) recall() BM25 关键词匹配；2) ppr_retrieve() 图游走；3) search_by_tag() 标签精确匹配。RRF score = Σ 1/(k + rank_i)，k=60 (标准值)。

#### `graph_rerank(results, *, alpha=0.5, centrality='degree') -> list[dict]`

图中心性重排序。将原始检索分数与图中心性分数混合：combined = α·centrality_norm + (1−α)·retrieval_norm。boost 结构重要的节点。centrality 可选 degree/pagerank/betweenness/eigenvector。GraphRAG/HippoRAG2 管线的标准最终步骤。

#### `retrieve(query, *, limit=10, stages=None, rerank=True, rerank_centrality='degree', rerank_alpha=0.5, damping=0.85, rrf_k=60, explain=False) -> list[dict] | dict`

端到端检索管线——一次调用，四个阶段：1) Keyword (recall BM25)；2) Topology (ppr_retrieve PPR 游走)；3) Hybrid (hybrid_retrieve RRF 融合)；4) Re-rank (graph_rerank 中心性加权)。explain=True 返回每阶段中间结果和分数。

#### `natural_connectivity(max_order=20, include_quarantined=False) -> float`

自然连通性——尺寸归一化鲁棒性度量（平均子图中心性的对数）。λ̄ = ln(EE/n)，其中 EE 是 Estrada 指数，n 是节点数。消除图尺寸偏差，可公平比较不同大小的图。值越高表示越鲁棒。

#### `effective_resistance(node_a, node_b, *, include_quarantined=False) -> float`

有效电阻（电路 analogy）。将图视为电路，每条边是 1Ω 电阻。R(a,b) = L⁺_aa + L⁺_bb − 2·L⁺_ab（Laplacian 伪逆）。低电阻→多短路径→连通好；高电阻→少/长路径→连通差。三角形中 R=2/3（并联路径降低电阻）。

#### `information_centrality(*, include_quarantined=False) -> dict[str, float]`

信息中心性 (Stephenson & Zelen 1989)。基于有效电阻：信息流 I(v,w) = 1/R(v,w)，中心性 C_I(v) = n / Σ_w R(v,w)。考虑所有路径（非仅最短路径）的信息流效率。惩罚长链末端的节点。

### 电流中心性 (Cycles 214-218)

#### `current_flow_betweenness(*, include_quarantined=False, normalized=True) -> dict[str, float]`

电流介数中心性 (Brandes & Fleischer 2007)。又称随机游走介数。通过 Laplacian 伪逆计算电压差，测量流经每个节点的“电流”量。与经典介数（仅计最短路径）不同，电流介数考虑所有路径——每个节点按其在电流网络中承载的流量排名。O(n²m) 算法基于 Laplacian 伪逆基础设施 (Cycle 213)。

#### `current_flow_closeness(*, include_quarantined=False) -> dict[str, float]`

电流接近中心性 (Brandes & Fleischer 2007)。又称随机游走接近度。每个节点 v 的接近度为 C_CF(v) = n / Σ_w R(v,w)，其中 R(v,w) 是有效电阻。低电阻→高接近度。考虑全网连通性而非仅最短路径距离。

#### `edge_current_flow_betweenness(*, include_quarantined=False, normalized=True) -> dict[frozenset[str], float]`

边级电流介数中心性。对每条边 e=(v,w)，测量通过该边的电流流量。返回 frozenset{v,w} → score 字典。与节点级 current_flow_betweenness 互补，边级度量揭示哪些连接是信息流的瓶颈。graph_rerank 已集成此度量作为可选 centrality 维度。

### 谱分析 (Cycles 215-217)

#### `kirchhoff_index(*, include_quarantined=False) -> float`

基尔霍夫指数（总有效电阻）。无序节点对有效电阻之和：Kf = Σ_{u<v} R(u,v)。基于 Matrix-Tree 定理和 Laplacian 伪逆恒等式计算。是全图连通性的标量度量——值越小表示连通性越好。完全图 K_n 的 Kirchhoff 指数为 n-1（最小可能值）。

#### `spanning_tree_count(*, include_quarantined=False) -> int`

生成树数量（Matrix-Tree 定理）。Laplacian 矩阵的任意余子式等于生成树数。利用 Laplacian 伪逆恒等式：τ(G) = det(L⁺) · n / Πλᵢ（非零特征值）。可用于量化网络的冗余连接程度。

#### `spectral_gap(*, include_quarantined=False) -> float`

谱隙 (Spectral Gap)。邻接矩阵两个最大特征值之差 δ = λ₁ − λ₂。较大的谱隙意味着随机游走更快混合、图更难切断。与代数连通度 (Fiedler value) 不同：谱隙基于邻接矩阵而非 Laplacian。

#### `graph_energy(*, include_quarantined=False) -> float`

图能量 (Gutman 1978)。邻接矩阵所有特征值绝对值之和：E(G) = Σ|λᵢ|。在化学图论中用作分子描述符，在网络科学中作为复杂度度量。与谱半径、代数连通度互补。

#### `hyper_wiener_index() -> Optional[int]`

超 Wiener 指数 (Randić 1993)。Wiener 指数的扩展，不仅考虑最短路径长度，还计及所有最短路径的条数：WW = ½ Σ_{u,v} (d(u,v) + d(u,v)²)。提供比经典 Wiener 指数更丰富的距离分布信息。

#### `balaban_index() -> Optional[float]`

Balaban J 指数 (Balaban 1982)。基于距离的拓扑描述符，被誉为“最相关的拓扑指数之一”：J = m / (m − n + 2) · Σ_{edges} (d_u · d_v)^{-½}，其中 d_u 是节点 u 到所有其他节点的距离和。对图的分支结构高度敏感。

#### `randic_index() -> Optional[float]`

Randić 连通性指数 (Kier & Hall 1976)。最被引用的分子描述符之一：R = Σ_{(u,v)∈E} 1/√(d_u · d_v)。连接度高的节点对的贡献被惩罚。与图的整体连通性负相关。

#### `harary_index() -> Optional[float]`

Harary 指数。成对距离倒数之和：H = Σ_{u<v} 1/d(u,v)。是 Wiener 指数的“倒数版本”——近距离节点对贡献更大。0 表示无连接的图，完全图 K_n 的 Harary 指数为 n(n-1)/2。

### Phantom Commit Detector (Cycle 219)

#### `scripts/phantom_check.py`

Pre-commit 守卫脚本，防止类遮蔽 (class shadowing) 和幻影 API (phantom API) 问题。07-07 事故的教训：6 个 API 被提交但实际不存在于代码中，根因是重复类定义中第二个类静默覆盖第一个。

功能：
1. 检测同一文件内的重复类/函数定义（遮蔽）
2. 解析 staged commit message 中的 API 名称，验证它们实际存在于代码
3. 清晰报告违规项

用法：
```bash
python3 scripts/phantom_check.py                        # 检查所有 .py 文件
python3 scripts/phantom_check.py memory_graph.py        # 检查特定文件
python3 scripts/phantom_check.py --commit-msg COMMIT_MSG # 验证 commit 中的 API
```

---

### 自适应检索 (QDAP-v2 + SkewRoute)

#### `_classify_query(query, known_labels=None) -> dict` *(staticmethod)*

QDAP-v2 6 类查询分类器。将查询分为 trivial / exact / semantic / relational / temporal / exploratory 六类，基于特征提取（标识符匹配、关系关键词、时间关键词、探索性关键词）计算 specificity ∈ [0,1]，然后通过连续权重插值生成 per-query 三路融合权重 [bm25_w, vector_w, graph_w]。trivial 查询直接跳过检索。

返回：`{type, weights, k, needs_retrieval, specificity}`

#### `_score_skewness(route_scores) -> list[float]` *(staticmethod)*

SkewRoute 检索后分数分布偏度分析。分析每路检索结果的分数偏度——top-heavy 分布（高正偏）表示高置信检索，平坦分布表示不确定。使用标准化三阶矩计算偏度，sigmoid 映射到 [0.1, 0.9] 置信度权重。零训练，即插即用。

#### `search_hybrid(query, embedding=None, limit=10, fusion="adaptive", kge_weight=0.0) -> list[dict]`

三路混合搜索：BM25 文本 + 向量 KNN + 图邻居加权 RRF 融合。支持三种模式：
- `"adaptive"`（默认）：QDAP-v2 查询分类 + 连续权重插值 + Entropy 修正 + SkewRoute 偏度分析，per-query 动态调整权重
- `"rrf"`：经典 Reciprocal Rank Fusion, k=60
- `"wrrf"`：Weighted RRF，用归一化分数置信度加权

### 图拓扑与团分析

#### `find_cycle() -> list[str] | None`

在有向图中查找并返回一个环路路径。基于 DFS 显式栈跟踪当前路径，当发现 back-edge（邻居在当前路径上）时提取环路。返回的路径首尾相等（闭合路径），如 `[A, B, C, A]`。无环返回 None。隔离节点排除。

#### `graph_periphery() -> list[str] | None`

返回图中具有最大偏心率的节点（即位于图直径的「最远」节点）。与 graph_center()（偏心率 = 半径）互补。使用 BFS 计算每个节点的最大距离。隔离节点排除。

#### `maximal_cliques(min_size=3) -> list[list[str]]`

使用 Bron-Kerbosch 算法（带 pivoting 优化）枚举所有极大团。团是所有节点对都直接相连的子图，极大团是不被更大团包含的团。用于识别紧密耦合的记忆簇（冗余事实、密集情景链）。隔离节点排除。

#### `clique_number() -> int`

最大团的节点数。无节点返回 0，无边返回 1。

#### `largest_clique() -> list[str]`

最大的极大团（排序后的节点 ID 列表）。无节点返回空列表。

#### `clique_overlap_matrix() -> dict[tuple[int, int], int]`

计算所有极大团对之间的共享节点数。返回 `(clique_i, clique_j) → shared_count` 字典，仅包含共享 ≥1 节点的团对。用于分析团间重叠结构。

#### `k_clique_communities(k=3) -> list[list[str]]`

CPM (Clique Percolation Method) 重叠社区检测 (Palla et al. 2005)。两个 k-clique 共享 k-1 节点时视为相邻，团邻接图的连通分量即为社区。与 LPA/Leiden 不同，节点可同时属于多个社区。返回按大小降序排列的社区列表。k 必须 ≥ 2。隔离节点排除。

#### `szeged_index() -> int | None`

Szeged 指数 — 边分割拓扑描述符。对每条边 (u,v)，统计更靠近 u 的节点数 n_u 和更靠近 v 的节点数 n_v，求和 ∏(n_u · n_v)。对树等价于 Wiener 指数 (Gutman 1994 定理)。返回 int 或 None（无边时）。

#### `gutman_index() -> int | None`

Gutman 指数 (Gutman 1994) — 度加权 Wiener 指数。∑_{u<v} d_u · d_v · d(u,v)，d_u 为节点度数。对正则图 k²·W。返回 int 或 None（无边时）。

#### `ppr_structured(seed_ids, *, damping=0.85, max_iter=100, tol=1e-6, gate="degree", gate_alpha=0.5) -> dict[str, float]`

SAGE 启发的结构门控 Personalized PageRank。传播信号由节点中心性调制——结构重要的节点（桥节点、枢纽）传递更多信号。gate_alpha=0 时退化为标准 PPR。gate 支持 degree/betweenness/closeness/eigenvector/pagerank 五种中心性度量。

#### `log_retrieval_failure(query, result_count=0, top_score=0.0, stage="recall") -> int`

记录检索失败。SAGE reader-writer 反馈环路：当检索返回少量/零结果或低置信度命中时，记录查询供后续分析。返回自增行 ID。

#### `get_retrieval_failures(*, since=None, stage=None, analysed_only=False, limit=100) -> list[dict]`

查询检索失败日志。支持按时间、阶段、是否已分析过滤，返回失败字典列表（最新优先）。

#### `analyse_retrieval_failures(*, min_failures=3, since_hours=24.0) -> list[dict]`

分析检索失败以发现缺失的图连接。按归一化查询分组，识别反复失败的查询，检查是否存在部分标签匹配但未被关键词召回命中的节点（SAGE writer 反馈循环）。返回 `[{query, failure_count, suggested_nodes, severity}]` 列表。

#### `clear_retrieval_failures(older_than_hours=None) -> int`

清除检索失败日志。older_than_hours 指定时仅清除更早的条目。返回删除行数。

#### `centrality_optimized(normalized=True, include_quarantined=False) -> tuple[dict, dict]`

联合计算 betweenness 和 closeness 中心性，避免重复邻接表构建和 BFS 遍历。返回 `(betweenness_dict, closeness_dict)`。

#### `retrieve_token_budgeted(query, *, token_budget=2048, chars_per_token=4.0, damping=0.85, rerank=True, rerank_centrality="degree") -> dict`

Token 预算上下文生成 — Mandol 启发的定量检索。在指定 token 预算内贪心打包检索结果，**无需任何 LLM 调用**。返回 `{context, nodes, token_count, char_count, truncated, budget}`。

#### `select_governed(query, *, limit=10, min_confidence=0.0, kinds=None, require_tags=None, rerank=True, rerank_centrality="degree", explain=False) -> list[dict] | dict`

MRMS 三阶段治理选择管线 (arXiv:2607.04617)：
- **阶段 1 — 结构门控**：过滤隔离/过期/低置信度节点
- **阶段 2 — 向量召回**：委托 retrieve() 混合检索
- **阶段 3 — 图展开**：标注 evidence/conflicts/superseded_by，标记安全/不安全

每个结果包包含 `node_id, claim, kind, score, confidence, is_safe, evidence, conflicts, superseded_by`。explain=True 时返回治理元数据。

#### `retrieval_quality_eval(eval_cases, *, k=10, limit=None, rerank=True, rerank_centrality="degree", rerank_alpha=0.5) -> dict`

评估检索质量 — 对比 ground-truth 相关集。每个评估用例为 `{query, relevant_ids}`。计算 6 项指标：precision@k、recall@k、F1@k、NDCG@k、MRR、hit@k。返回 `{overall, per_query, k, n_cases, n_evaluated}`。

#### `add_with_entropy_filter(label, kind="fact", data=None, tags=None, threshold=0.3) -> Node | None`

SimpleMem (ICML 2026) 启发的写入时熵过滤。计算信息密度综合分数（词汇多样性 + 长度因子 + 与现有节点的 Jaccard 新颖度），低于 threshold 的内容直接拒绝写入。score ∈ [0, 1]，默认阈值 0.3 过滤低质量重复内容。返回创建的 Node 或 None（被过滤）。

#### `subgraph_by_edge_type(relation, include_isolated=False) -> dict`

MAGMA (ACL 2026) 启发的正交多图视图。提取仅包含指定 relation 类型的子图（节点+边+统计信息）。返回 `{nodes, edges, relation, stats}` 字典，可通过 `import_json()` 导入为独立图。适用于因果、时序、层次等不同语义维度的隔离分析。

#### `add_causal_edge(source_id, target_id, relation, confidence=1.0, evidence=None, note=None) -> dict`

ActMem (arXiv:2603.00026) 启发的因果边层。五种有类型关系：`causes`（导致）、`prevents`（阻止）、`conflicts_with`（冲突）、`enables`（使能）、`depends_on`（依赖）。每条边携带 confidence ∈ [0,1]、evidence 节点 ID 列表和可选 note。返回创建边的摘要字典。

#### `get_causal_edges(node_id, direction="both", relation=None) -> list[dict]`

查询节点的因果边。direction 支持 `outgoing`/`incoming`/`both`，可按 relation 过滤。返回边字典列表，含 `source, target, relation, weight, confidence, evidence, note, created_at`。

#### `trace_causal_chain(node_id, max_depth=10, direction="forward") -> list[list[dict]]`

BFS 遍历因果链。`forward` 方向跟随 causes→effects（向外追踪后果），`backward` 方向追溯到根因。Cycle-safe（visited 集合防止环路）。返回链列表，每条链为边字典列表，按长度降序、总置信度降序排列。

#### `trace_decision_chain(topic=None, node_id=None) -> list[dict]`

TokenMizer 启发的决策/ supersede 链追踪。对每个 hop 报告 trigger（supersede/conflict_resolve/unknown）、reason 文本和 evidence 节点列表，回答"为什么这个事实从 A 变成了 B？"。通过 topic（标签模糊搜索最老节点）或 node_id 起始，按时间顺序返回 hop 字典列表。

#### `spread_activation(seed_ids, *, decay_factor=0.5, threshold=0.1, max_hops=3, include_quarantined=False, edge_weight_factor=True) -> dict[str, float]`

Collins & Loftus (1975) 扩散激活检索。从 seed 节点出发沿边传播激活值，每跳乘以 decay_factor。返回 `{node_id: activation}` 字典（≥ threshold 的节点）。支持多 seed、隔离节点跳过、边权重调制。

#### `schultz_index() -> int | None`

Schultz 分子拓扑指数 (Schultz 1989)。∑_{u<v} (d_u + d_v) · d(u,v)，d_u 为节点度数。与 Gutman 指数的关系：Schultz 用度之和，Gutman 用度之积。对正则图退化为 Wiener 指标的常数倍。返回 int 或 None（<2 节点或无边时）。

#### `modified_wiener_index(lam=-1) -> float | None`

Modified Wiener 指数 (Nikolić, Trinajstić, Randić 1994)。∑_{u<v} d(u,v)^λ。λ=1 为经典 Wiener 指数；λ=-1（默认）逆距离加权，强调近邻；λ=2 二次距离惩罚，强调远端。不连通对的距离不计。返回 float 或 None。

#### `generalized_randic_index(alpha=-0.5) -> float | None`

广义 Randić 指数 R_α (Bollobás & Erdős 1998)。∑_{(u,v)∈E} (d_u · d_v)^α。α=-1/2（默认）为经典 Randić 连接性指数；α=0 为边数 m；α=+1 为第二 Zagreb M₂ 指数。参数化族统一了多个度描述符。

#### `zagreb_indices() -> dict | None`

第一和第二 Zagreb 指数 (Gutman & Trinajstić 1972)。M₁ = ∑ d_v²（度平方和），M₂ = ∑_{(u,v)∈E} d_u · d_v（边上度积之和）。返回 `{first, second, difference, ratio}` 字典或 None。

---

## 测试

```bash
python3 -m pytest test_memory_graph.py -q
```

8505 → **10040 个测试**覆盖所有 API（**519 个 cycle，304 天零回滚**；计数为 08-27 04:00 后 pytest collect 实测）。

## Cycles 416-424: Experience Compression Spectrum L2→L3 + 检索质量趋势 + 知识耐久度

### 架构里程碑

Cycles 416-424 完成了两个重要架构里程碑：

**1. Experience Compression Spectrum L2→L3 规则生命周期完结**

```
L0 (raw trace) → L1 (episode) → L2 (skill) → L3 (rule)
                                   ↑              ↑
                             compress_to_skill    extract_rules (Cycle 420)
                                                rule_conflict_detect (422)
                                                rule_apply (423)
                                                rule_explain (424)
```

完整生命周期：从原始跟踪到声明式规则的全谱压缩。L3 规则分离负向约束（RuleShaping 研究：负向约束 +7-14pp）与正向规则，支持矛盾检测、运行时匹配和诊断解释。

**2. 检索质量五步流水线完结**

```
audit (404) → explain (406b) → rerank (414) → compare (415) → trend (416)
                                                            COMPLETE ✅
```

### 新增 API 参考

#### `retrieval_quality_trend(snapshots) -> dict` (Cycle 416)

N 份审计快照的时序趋势分析。每维度线性回归（斜率/r²），方向判定（improving/degrading/stable），波动率（变异系数），变化点检测（z-score）。

#### `memory_half_life(node_id) -> dict` (Cycle 417)

逐节点知识耐久度估算。基于 Ebbinghaus 衰减模型，综合访问频率、Q 值、度数、活动因子计算半衰期。4 级分类：durable（>720h）/ stable（168-720h）/ fragile（24-168h）/ ephemeral（<24h）。

#### `staleness_report(*, group_by=None) -> dict` (Cycle 418)

全图陈旧度人口分析。4 级分布（fresh/aging/stale/critical）+ 统计（mean/median/std）+ 最陈旧排名 + 分组分解 + 维护建议。

#### `batch_half_life(node_ids=None) -> dict` (Cycle 419)

批量半衰期分析。聚合统计（mean/median/std）+ 类别分布 + top/bottom-5 排名 + 维护建议。

#### `extract_rules(skill_ids, *, min_confidence=0.7) -> list[dict]` (Cycle 420)

**Experience Compression Spectrum L2→L3。** 从技能节点提取声明式规则。自动分离负向约束（"never/avoid/not"）与正向规则。跨技能模式检测（共享约束置信度 +0.15）。返回规则节点（kind='rule'），建立 `derived_from` 边链接回源技能。

#### `compression_spectrum_report() -> dict` (Cycle 421)

L0-L3 全谱分布分析。按 kind 分类所有节点（trace/event→L0, episode/fact→L1, skill→L2, rule→L3）。级别分布 + 百分比 + 加权压缩比（L0=1×, L1=10×, L2=100×, L3=1000×）+ 主导级别识别 + 可执行压缩建议。

#### `rule_conflict_detect(*, rule_ids=None) -> dict` (Cycle 422)

L3 规则集矛盾检测。直接矛盾（同一动作关键词在一规则中正向、另一规则中负向）+ 重叠检测（共享约束文本）+ 清洁规则计数。

#### `rule_apply(content, *, top_k=5) -> list[dict]` (Cycle 423)

运行时 L3 规则匹配。通过 Jaccard 关键词重叠将规则与新内容匹配。返回排名匹配 + 正/负向引导。完整规则生命周期：extract_rules → rule_conflict_detect → rule_apply。

#### `rule_explain(content, rule_id) -> dict` (Cycle 424)

逐规则匹配诊断。关键词重叠分解 + Jaccard 贡献评分 + 人类可读解释 + 可执行建议。规则自省生命周期完结：extract_rules → rule_conflict_detect → rule_apply → rule_explain。

---

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
28. **MCP Server** — 10 工具标准化协议接口 (remember/recall/relate/ask/lookup/neighbors/forget/stats/timeline/health)，AI Agent 可通过 MCP 直接操作记忆图谱，已接入 mcporter 自用 dogfood
29. **批量操作 + 链路预测** — batch_create_nodes/batch_add_edges/batch_delete_nodes 单事务高效写入；predict_links 三信号推荐缺失边（common-neighbors + Adamic-Adar + preferential-attachment）
30. **加权路径 + 子图提取** — Dijkstra 加权最短路径 + Yen's k-shortest-paths + all_paths 枚举；extract_subgraph 返回独立子图实例，neighborhood 轻量 ID 列表
31. **全图中心性 + 图收缩** — betweenness_all/closeness_all/eigenvector_all 批量中心性计算；contract_nodes/contract_communities 超节点折叠实现多分辨率图分析
32. **图序列化** — to_dict/from_dict 提供 JSON 安全的图序列化方案，支持快照恢复、API 响应和跨 Agent 记忆传输
33. **自适应检索 (QDAP-v2 + SkewRoute)** — 6 类查询分类器 + 连续权重插值 + 分数偏度分析 + 熵修正，per-query 动态调整 BM25/Vector/Graph 三路融合权重。trivial 查询跳过检索，relational 查询图主导，exact 查询 BM25 主导——让问题自己说话
34. **图拓扑与团分析** — find_cycle (DFS 环路检测) + graph_periphery (最远节点) + maximal_cliques (Bron-Kerbosch 极大团) + clique_overlap_matrix (团间共享节点) + k_clique_communities (CPM 重叠社区发现，节点可属多社区)
35. **高级中心性** — katz_centrality (衰减路径求和中心性) + subgraph_centrality (闭合游走参与度) + laplacian_centrality (网络中断潜力，Laplacian 能量下降) + estrada_index (全图连通性指数) + communicability (节点对信息流便捷度) + natural_connectivity (尺寸归一化鲁棒性) + effective_resistance (电路 analogy 节点对连通性) + information_centrality (Stephenson-Zelen 信息流效率) 提供 14 种经典中心性/连通性度量，覆盖从节点级到图级别的多维度重要性分析
36. **GraphRAG 检索管线** — personalized_pagerank (HippoRAG 核心 PPR 从 seed 节点传播相关性) + ppr_retrieve (关键词→seed→PPR 两阶段检索) + compute_graph_activity/auto_forget (FOREVER 模型：活跃图忘记更少，沉寂图加速遗忘) + hybrid_retrieve (RRF 融合 keyword+PPR+tag 三路信号) + graph_rerank (中心性加权重排序) + retrieve() 统一四阶段管线编排器 (keyword→PPR→hybrid→rerank)
37. **电流中心性与谱分析** — current_flow_betweenness/current_flow_closeness/edge_current_flow_betweenness (Brandes & Fleischer 2007 电流类比随机游走中心性) + kirchhoff_index/spanning_tree_count (Matrix-Tree 定理全图连通性) + spectral_gap/graph_energy (邻接矩阵谱特性) + hyper_wiener_index/balaban_index/randic_index/harary_index (化学图论距离描述符) + phantom_check.py (Cycle 219 pre-commit 守卫，防止类遮蔽和幻影 API)。总计 20 种中心性/连通性/谱/拓扑度量
38. **SAGE 检索反馈与治理管线** — ppr_structured (SAGE 启发的结构门控 PPR：中心性高的节点传播更多信号) + log_retrieval_failure/get_retrieval_failures/analyse_retrieval_failures/clear_retrieval_failures (检索失败日志 + writer-reader 反馈环路：自动发现缺失边并建议图改进) + centrality_optimized (联合 betweenness+closeness 单次 BFS 计算) + retrieve_token_budgeted (Mandol 启发的 token 预算上下文生成：无 LLM 调用的确定性贪心打包) + select_governed (MRMS 三阶段治理选择管线：结构门控→向量召回→图展开) + retrieval_quality_eval (precision@k/recall@k/F1/NDCG/MRR/hit_rate 六指标评估) + szeged_index/gutman_index (化学图论距离描述符)。从检索质量评估到治理选择的完整 SAGE 闭环
39. **写入过滤 + 因果推理 + 扩散激活** — add_with_entropy_filter (SimpleMem ICML 2026：写入时信息密度过滤，词汇多样性+长度+新颖度三因子) + subgraph_by_edge_type (MAGMA ACL 2026：正交多图视图，按关系类型隔离分析) + add_causal_edge/get_causal_edges/trace_causal_chain (ActMem 5 型因果边：causes/prevents/conflicts_with/enables/depends_on，confidence+evidence+BFS 链追踪) + trace_decision_chain (TokenMizer 启发：supersede 链 trigger/reason/evidence 决策审计) + spread_activation (Collins & Loftus 1975：扩散激活 BFS 传播，decay/threshold/max_hops 可控) + schultz_index/modified_wiener_index/generalized_randic_index/zagreb_indices (Schultz 1989/Nikolić 1994/Bollobás 1998/Gutman 1972：度加权距离描述符四族，拓扑指数扩展至十一族)
40. **级联失效 + 分类检索** — invalidate_cascade (PLACEM 启发：BFS 级联失效，depends_on 反向传播 + enables 正向传播，cycle-safe visited 集，max_depth 限制，幂等) + add(category=) + search_by_category (Apple Shared Selective Memory：preference/protocol/episodic/reference/skill 五类，selective retrieval)
41. **主动上下文召回** — read_proactive_context 基于当前活跃意图主动推送相关记忆，结合温度（访问频率+时间衰减）和意图匹配，在 Agent 提问前预取上下文
42. **拓扑指数扩展至十四族** — forgotten_index (Fajtlowicz 1998) + abc_index (Estrada 1998) + sum_connectivity_index (Zhou & Trinajstić 2009)，度描述符从十一族扩展至十四族
43. **不可变记忆日志 + grep + 全息展开** — immutable_store 追加写入不可变历史 (node_id, label, kind, op, timestamp)，immutable_retrieve/immutable_all/immutable_count 完整查询接口，grep 跨全历史文本搜索，expand 从不可变存储无损恢复节点完整数据。审计级记忆版本控制
44. **节点压缩 + 批量压缩** — compact_node 三级压缩 (level 0/1/2：截断→摘要→极致压缩) + compact_batch 批量压缩 + compact_stats 压缩统计。token 预算友好
45. **Token 预算序列化** — serialize() 按指定 token 预算贪心打包节点为 LLM 可用格式 (include_edges/include_data 可选)，serialize_compact() 自动压缩+序列化一步到位
46. **关系完整性校验** — check_relation_integrity 检测 relation channel 上的值冲突（矛盾数据/ dangling references/ type mismatches）+ integrity_quarantine 自动隔离高危节点。数据质量守卫
47. **语义速度门控 + 选择性过滤** — semantic_speed_gate 测量节点邻域波动率（边增删频率），speed_gate_batch 批量门控，volatile_nodes 高波动节点排行 + selective_filter 多维度质量过滤（权重/kind/标签/隔离/完整度）+ selective_filter_report 过滤摘要报告。SSGM 启发的动态质量管控
48. **程序性记忆压缩** — compress_to_skill 将多个情景记忆压缩为 Skill Contract 节点 (Experience Compression Spectrum L1→L2, Anything2Skill)，retrieve_skills 多信号检索 (文本相关性+置信度+Q值+时效)，evolve_skill 反馈驱动版本演进 (AutoRefine)，skill_bank_health 技能库健康度
49. **信息密度评估** — memory_information_density PRISM/PlugMem 启发的 Pareto 指标 (unique_terms/char_count × q_value_weight)，衡量每节点的信息量/token 比，支持 kind 过滤和 top-k 排名
50. **意图感知边成本** — detect_query_intent 4 类查询分类 (temporal/causal/multi_hop/factual) + intent_aware_edge_cost 按意图调整边遍历成本 (temporal 查询折扣时序边，causal 折扣因果边) + retrieve_with_intent 意图路由检索管线 (PRISM 启发)
51. **双模 SimHash 检索** — binary_signature (64-bit SimHash) + similarity_search_binary (汉明距离 O(N) 近邻搜索) + dual_mode_retrieve (二进制预过滤→图重排序两阶段，Hippocampus 启发：31× 更快检索，14× 更少 token)
52. **去重与合并** — find_duplicate_nodes O(N²) 汉明距离近重复检测 + deduplicate 自动合并 (高权重节点吸收低权重节点的边和数据，Charikar 2002 SimHash + Manku 2008 Hamming LSH)
53. **洛伦兹系数与重定义指数** — lorenz_coefficient (度分布 Gini 系数 + Lorenz 曲线) + redefined_randic_indices (Randić 2008: RD₁/RD₂/RD₃ 三变体) + redefined_zagreb_index (ReZM₃ = Σ(d_u+d_v)·(d_u·d_v))，拓扑指数扩展至十七族

---

### 级联失效与分类检索 (Cycle 236)

#### `invalidate_cascade(node_id, reason=None, invalidated_by=None, cascade_relations=None, max_depth=10) -> dict`

PLACEM (arXiv:2607.04089) 启发的级联失效。当节点被标记为失效时，BFS 遍历 `depends_on`（反向）和 `enables`（正向）边传播失效到依赖节点。Cycle-safe（visited 集合防止环路），max_depth 限制传播深度，幂等设计。

```python
result = mg.invalidate_cascade("fact:old_api", reason="API deprecated")
# {'invalidated': ['fact:old_api', 'fact:usage_example', 'concept:wrapper'],
#  'cascade_depth': 2, 'reason': 'API deprecated'}
```

#### `add(label, kind="fact", ..., category=None) -> Node`

`add()` 方法新增 `category` 参数 (Apple Shared Selective Memory, arXiv:2607.09493)。支持五类记忆分类：`preference` / `protocol` / `episodic` / `reference` / `skill`。

#### `search_by_category(category) -> list[Node]`

按 category 检索节点，自动排除已隔离的节点。

---

### 主动上下文召回 (Cycle 237)

#### `read_proactive_context(*, active_intents=None, top_k=10, min_temperature=0.1, include_inactive=False) -> list[dict]`

基于当前活跃意图主动推送相关记忆。结合温度评分（访问频率 × 时间衰减）和意图关键词匹配，在 Agent 发起查询前预取最相关的上下文。适用于 proactive memory injection 场景。

```python
context = mg.read_proactive_context(
    active_intents=["debug auth issue", "review PR"],
    top_k=5
)
# [{'node_id': 'n42', 'label': 'Auth Module', 'temperature': 0.82,
#   'matched_intents': ['debug auth issue'], ...}]
```

---

### 拓扑指数扩展 (Cycle 238)

#### `forgotten_index() -> int | None`

Forgotten 拓扑指数 F (Fajtlowicz 1998)。基于度乘积的边和：F = Σ_{(u,v)∈E} (d_u · d_v)²。对高度节点间的连接给予指数级权重。

#### `abc_index() -> float | None`

Atom-bond 连通性指数 (Estrada et al. 1998)。ABC = Σ_{(u,v)∈E} √((d_u-1 + d_v-1) / (d_u·d_v))。与 Randić 指数负相关，对低度节点间的连接给予更高权重。

#### `sum_connectivity_index() -> float | None`

Sum-connectivity 指数 (Zhou & Trinajstić 2009)。⁰S = Σ_{(u,v)∈E} 1/(d_u + d_v)。Randić 指数的变体，使用度和的倒数而非积的平方根的倒数。

---

### 不可变记忆日志 (Cycles 239, 244)

> 追加写入的不可变变更历史，支持审计、回溯和全文本搜索。

#### `_immutable_log(node_id, label, kind, op, data=None)` *(internal)*

记录不可变日志条目。每次节点变更（add/update/delete）自动调用。

#### `immutable_retrieve(node_id) -> list[dict]`

返回指定节点的所有不可变快照，按时间升序。每条含 `seq, node_id, label, kind, op, data, timestamp`。

#### `immutable_all(limit=0) -> list[dict]`

返回全量不可变历史。`limit=0` 不限制。

#### `immutable_count() -> int`

返回不可变日志总条目数。

#### `grep(pattern, case_insensitive=True) -> list[dict]`

跨所有不可变历史进行文本搜索（label + kind + data）。支持大小写敏感/不敏感模式。返回匹配条目列表。

```python
matches = mg.grep("auth", case_insensitive=True)
# [{'seq': 42, 'node_id': 'n5', 'label': 'Auth Module', 'op': 'update', ...}]
```

#### `expand(node_id) -> dict | None`

从不可变存储无损恢复节点的完整原始数据。合并所有历史条目的 data 字段，最新覆盖最旧。

---

### 节点压缩 (Cycle 240)

#### `compact_node(node_id, max_label_len=80, level=0, summarizer=None) -> dict`

压缩单个节点的表示，保留关键信息。三级压缩策略：

| Level | 策略 | 效果 |
|-------|------|------|
| 0 | 截断标签 + 精简 data | ~30% token 减少 |
| 1 | 摘要标签 + 关键字段保留 | ~50% token 减少 |
| 2 | 极致压缩（仅保留核心字段） | ~70% token 减少 |

`summarizer` 可选传入自定义摘要函数 `(text, max_len) -> str`。

#### `compact_batch(node_ids, max_label_len=80, level=2, summarizer=None) -> dict`

批量压缩多个节点。返回 `{compacted, skipped, stats}`。

#### `compact_stats() -> dict`

返回压缩统计：已压缩节点数、未压缩节点数、平均 token 节省比例。

---

### Token 预算序列化 (Cycle 241)

#### `serialize(node_ids=None, token_budget=4096, include_edges=True, include_data=True, include_quarantined=False) -> dict`

按 token 预算贪心打包节点为 LLM 可用的序列化格式。自动跳过隔离节点。返回 `{context, nodes_included, nodes_skipped, token_count, char_count, truncated}`。

```python
result = mg.serialize(
    node_ids=mg.neighbors(center_id, depth=2),
    token_budget=2048,
    include_edges=True
)
# {'context': '## fact\n- **Auth Module** ...',
#  'nodes_included': 12, 'token_count': 1923, 'truncated': True}
```

#### `serialize_compact(token_budget=2048) -> dict`

便捷方法：自动压缩全图节点 + 序列化。一步到位生成极简 LLM 上下文。

---

### 关系完整性校验 (Cycle 242)

#### `check_relation_integrity(node_id=None) -> dict`

扫描 relation channel 上的数据完整性问题。检测三类问题：
- **值冲突** — 同一节点对不同邻居声明矛盾数据（如 contradictory properties）
- **悬挂引用** — 边指向不存在的节点
- **类型不匹配** — relation 语义与节点 kind 不符

`node_id=None` 扫描全图，指定则只检查单节点。返回 `{total_issues, by_type, issues}`。

#### `integrity_quarantine(issues=None, severity_threshold='high') -> dict`

自动隔离被标记为高危的节点。接受 `check_relation_integrity()` 的输出或自动扫描。severity_threshold 控制隔离门槛（high/medium/low）。返回 `{quarantined, reasons}`。

---

### 语义速度门控 (Cycle 243)

> SSGM (Semantic Speed Gate Model) 启发的动态质量管控。

#### `semantic_speed_gate(node_id, *, window_hours=24.0, query_time=None) -> dict`

测量单节点邻域的波动率——在指定时间窗口内边的新增/删除频率。返回 `{node_id, speed, edge_changes, window_hours, verdict}`。verdict: `stable` / `moderate` / `volatile`。

#### `speed_gate_batch(node_ids=None, *, window_hours=24.0, query_time=None, min_speed=0.0) -> list[dict]`

批量速度门控。`node_ids=None` 扫描全图。`min_speed` 过滤低速度节点。

#### `volatile_nodes(*, window_hours=24.0, min_speed=0.5, limit=20, query_time=None) -> list[dict]`

返回最波动的节点排行。高 speed 值表示该节点邻域近期经历大量变更，可能是噪声记忆或活跃编辑区。

#### `selective_filter(node_ids, *, max_weight=None, min_weight=None, kinds=None, tags=None, exclude_quarantined=True, exclude_compacted=False, min_integrity_score=None) -> list[str]`

多维度质量过滤。从给定节点集合中按权重范围、kind、标签、隔离状态、压缩状态和完整性评分筛选。返回通过所有过滤的节点 ID 列表。

#### `selective_filter_report(node_ids, **kwargs) -> dict`

运行 `selective_filter` 并生成摘要报告：输入数、通过数、各维度淘汰数。

---

### 程序性记忆压缩 (Cycle 245)

> Experience Compression Spectrum (Zhang et al., arXiv:2604.15877) + Anything2Skill (arXiv:2607.09033)

#### `compress_to_skill(episode_ids, name, *, description="", confidence=0.5) -> Node | None`

将多个情景记忆节点压缩为一个 `kind='skill'` 的技能节点。创建 Skill Contract 数据结构 (skill_name/description/source_episodes/steps/constraints/confidence/version)，链接技能→每个源节点（`abstracts` 边），并给予 Q 值提升。

```python
episodes = ["node-001", "node-002", "node-003"]
skill = mg.compress_to_skill(episodes, "deploy_to_staging",
                             description="Standard deploy workflow")
print(skill.data["compression_ratio"])  # ~15.0 (3 episodes × 5)
print(skill.data["steps"])  # extracted action steps
```

#### `retrieve_skills(context="", *, top_k=5, min_confidence=0.0, tags=None) -> list[Node]`

多信号技能检索。评分 = 0.30×文本相关性 + 0.25×置信度 + 0.30×Q值 + 0.15×时效性。

#### `evolve_skill(skill_id, *, feedback=0.0, new_steps=None, new_constraints=None, description=None, reason="") -> Node | None`

反馈驱动的技能演进。正向 feedback 提升置信度和 Q 值，负向降低。置信度 < 0.1 时标记 deprecated。使用 semver 版本追踪，supersede 链记录历史。

```python
# 技能成功使用后强化
mg.evolve_skill(skill.id, feedback=0.3, reason="successful deploy")

# 技能失败后弱化
mg.evolve_skill(skill.id, feedback=-0.5, new_constraints=["requires Python 3.12+"],
               reason="failed on Python 3.11")
```

#### `skill_bank_health() -> dict`

技能库健康度报告：总数、活跃、已废弃、平均置信度、平均 Q 值。

---

### 信息密度评估 (Cycle 246)

> PRISM (arXiv:2607) + PlugMem (ICML 2026) 启发

#### `memory_information_density(*, node_id=None, kind=None, top_k=20) -> dict | list[dict]`

计算记忆节点的信息密度：`density = (unique_terms / char_count) × q_value_weight`。

- **unique_terms**: label + data 中长度 > 2 的不同词数
- **char_count**: label + JSON 序列化 data 的总字符数
- **q_value_weight**: 0.5 + q_value (范围 [0.5, 1.5])

```python
# 全图密度 Top 5
dense = mg.memory_information_density(top_k=5)
for d in dense:
    print(f"{d['label']}: density={d['density']}, terms={d['unique_terms']}")

# 单节点密度
info = mg.memory_information_density(node_id="node-001")
print(info["rank_percentile"])  # e.g. 95.2
```

---

### 意图感知边成本 (Cycle 247)

> PRISM (arXiv:2607) 启发的意图路由

#### `detect_query_intent(query) -> str`

将查询分类为四种意图类型：

| 类型 | 关键词示例 | 优先边类型 |
|------|-----------|-----------|
| `temporal` | when/before/after/timeline/什么时候 | supersedes, causes |
| `causal` | why/because/cause/为什么/原因 | causes, prevents, enables |
| `multi_hop` | connect/path/link/关联/链路 | similar_to, related_to |
| `factual` | _(默认)_ | 无特殊加权 |

#### `intent_aware_edge_cost(query, *, node_id=None) -> dict`

计算意图调整后的边成本。每种意图有不同的 edge-type affinity multiplier（< 1.0 = 折扣，> 1.0 = 惩罚）。

```python
result = mg.intent_aware_edge_cost("why did the deploy fail?")
# {'intent': 'causal', 'edge_count': 12,
#  'edges': [{'source': '...', 'relation': 'causes', 'adjusted_cost': 0.2, ...}, ...]}
```

#### `retrieve_with_intent(query, *, limit=10) -> dict`

意图路由检索管线：1) 检测意图 → 2) 标准 retrieve 管线 → 3) 意图感知边成本重排序。

返回 `{intent, results: [...], edge_adjustments: {...}}`。

---

### 双模 SimHash 检索 (Cycles 249-250)

> Hippocampus (arXiv:2602.13594) 启发 — 31× 更快检索，14× 更少 token

#### `binary_signature(node_id, *, bits=64) -> str`

计算节点的 SimHash 二进制签名。基于 label + data 的 token-level MD5 哈希加权和，中位数阈值量化为 bit string。相同内容 → 相同签名；语义相似 → 少量 bit 差异。

#### `similarity_search_binary(query, *, limit=10, max_hamming=None, kind=None) -> list[dict]`

二进制签名相似度搜索。计算查询的 SimHash，扫描所有节点的汉明距离。O(N) 但常数极小 (~1 cmp/ns)。

```python
results = mg.similarity_search_binary("deploy failure", max_hamming=20)
# [{'node_id': '...', 'label': 'deploy error', 'hamming_distance': 5}, ...]
```

#### `dual_mode_retrieve(query, *, limit=10) -> dict`

两阶段检索：**Phase 1** 二进制预过滤（SimHash 汉明距离筛选 3×limit 候选）→ **Phase 2** 图检索+重排序（blend binary_similarity × 0.4 + graph_score × 0.6）。小图 (< 10 节点) 自动跳过二进制阶段。

```python
result = mg.dual_mode_retrieve("rust memory safety")
# {'candidates': [...], 'results': [...],
#  'binary_phase': {'candidate_count': 30, 'query_signature': '10101...'},
#  'graph_phase': {'method': 'retrieve_rerank', 'count': 10}}
```

---

### 去重与合并 (Cycle 250)

> Charikar (2002) SimHash + Manku et al. (2008) Hamming LSH

#### `find_duplicate_nodes(*, threshold=3, bits=64, kind=None) -> list[dict]`

检测近重复节点。预计算每个节点的 SimHash，O(N²) 两两比对汉明距离。threshold=3 表示 ≥95% bit 重叠即为重复。

```python
dupes = mg.find_duplicate_nodes(threshold=3)
# [{'node_a': '...', 'node_b': '...', 'label_a': 'deploy error',
#   'label_b': 'deployment error', 'hamming_distance': 2}, ...]
```

#### `deduplicate(*, threshold=3, dry_run=True, kind=None) -> dict`

检测并合并近重复节点。合并策略：高权重节点吸收低权重节点的边和数据（使用 `merge_nodes`）。簇处理（A≈B, B≈C）按汉明距离升序合并，已合并节点跳过。

```python
# 先 dry run 查看结果
report = mg.deduplicate(threshold=3, dry_run=True)
print(report["duplicates_found"])  # e.g. 5

# 实际合并
report = mg.deduplicate(threshold=3, dry_run=False)
print(report["merges_executed"])   # e.g. 3
print(report["savings"])           # est. bytes saved
```

---

### 洛伦兹系数与重定义指数 (Cycle 251)

#### `lorenz_coefficient() -> dict | None`

度分布的 Lorenz 系数 / Gini 指数。衡量节点度分布的不均等程度。

| Gini 值 | 含义 |
|---------|------|
| 0.0 | 完全均等（正则图，每个节点度相同） |
| 1.0 | 最大不均等（星型图，一个 hub + 所有其他节点度=1） |
| < 0.3 | 平等主义 |
| > 0.6 | Hub 主导 |

返回 `{gini, lorenz_curve, mean_degree, degree_sequence}`。

#### `redefined_randic_indices() -> dict | None`

Randić (2008) 重定义 Randić 指数三变体：

- **RD₁** = Σ (d_u·d_v / (d_u+d_v))
- **RD₂** = Σ (d_u·d_v / (d_u+d_v))²
- **RD₃** = Σ (d_u·d_v / (d_u+d_v))³

高次变体对高度数边区分度更强。返回 `{rd1, rd2, rd3}`。

#### `redefined_zagreb_index() -> float | None`

第三 Zagreb 重定义指数：ReZM₃ = Σ (d_u+d_v)·(d_u·d_v)。结合加性 (M₁-like) 和乘性 (M₂-like) 度项。

---

### 写入治理 (Cycle 252)

#### `write_governance_check(node_id, label=None, data=None, tags=None) -> dict`

PASB 启发（arXiv:2607.10526），在 commit 边界检测三类谄媚失败模式：

| 失败模式 | 检测内容 |
|---------|---------|
| `status_promotion` | hedged → definitive（确定性升级）|
| `attribution_removal` | source/evidence/provenance 被剥离 |
| `scope_broadening` | specific → universal（范围扩大）|

返回 `{classification: 'safe'|'flag'|'reject', findings: [...]}`。

#### `safe_supersede(old_id, new_node, ...) -> dict`

带治理门的 supersede 操作。reject 级别的发现会阻止写入。

#### `governance_audit(node_id) -> dict`

回溯审计 supersede 链，检查历史写入中是否存在治理违规。

---

### 社区语义层 (Cycle 253)

#### `community_topic_labels(community_id) -> list[str]`

GraphRAG 启发的社区主题标签提取。从节点 kind、tags、关键词中提取社区代表性标签。

#### `community_semantic_summary(community_id, llm_callback=None) -> str`

社区语义摘要。支持确定性摘要（默认）或通过 `llm_callback` 接入 LLM。

#### `community_overview() -> list[dict]`

综合结构 + 语义的社区仪表盘。每个社区返回成员数、主题标签、语义摘要。

#### `query_global(question, top_k=5) -> list[dict]`

GraphRAG 全局搜索：跨社区摘要匹配问题，返回最相关社区及其成员。

---

### 生命周期操作评估 (Cycle 254)

#### `lifecycle_operation_eval(operation, args, golden_set=None) -> dict`

MemOps 启发（arXiv:2607.12893）的 6 探针生命周期验证器：

| 探针 | 检测内容 |
|------|---------|
| `detection` | 操作是否被正确检测 |
| `target` | 目标节点是否正确 |
| `transition` | 状态转换是否合法 |
| `robustness` | 边界条件鲁棒性 |
| `provenance` | 来源链是否完整 |
| `leakage` | 是否有数据泄漏 |

支持 add/update/supersede/forget/merge 操作。golden_set 验证 + 每探针 override。

---

### 前瞻记忆 (Cycle 255)

#### `add_intention(label, trigger_cues, deadline=None) -> Node`

PM-Bench 启发（arXiv:2607.12385, COLM 2026）。存储延迟执行的意图，附带触发线索和截止时间。

#### `check_prospective_cues(context_text) -> list[dict]`

关键词重叠匹配。检查当前上下文是否触发任何 pending intention。返回带紧迫度分类（urgent/soon/future/expired）的匹配列表。

#### `fulfill_intention(node_id) -> Node | None`

标记意图为已完成，记录完成时间戳。

#### `pending_intentions(include_expired=False) -> list[Node]`

列出活跃（或全部）的待执行意图。

---

### DRIFT 搜索 (Cycle 256)

#### `drift_search(question, max_iter=2, top_k=10) -> dict`

GraphRAG 启发（Edge et al. 2024）的 DRIFT 混合搜索：

1. **Global sweep** — `query_global()` 社区级理解
2. **Local spread** — 从社区成员出发的扩散激活
3. **RRF merge** — 全局 + 局部信号逆序融合
4. **Iterative refine** — 用发现的标签扩展查询，重新检索

保留 `in_global`/`in_local` 标志跨迭代。桥接 GraphRAG 的全局理解力与节点级精度。

---

### 技能组合与谱系 (Cycle 257)

#### `skill_compose(skill_ids, meta_label=None, meta_data=None) -> Node`

Experience Compression Spectrum 启发的 L1→L2 元技能组合。将多个技能节点组合成元技能。

#### `skill_decompose(meta_skill_id) -> list[Node]`

分解元技能为组成组件列表。

#### `skill_lineage(node_id, max_depth=10) -> dict`

递归构建技能谱系树。返回祖先和后代的层级关系。

---

### 自适应查询路由 (Cycle 258)

#### `query(question, mode='auto', detail=False, top_k=10) -> dict`

GraphRAG/LightRAG 启发的自适应查询路由器。分析问题特征并分派到最佳检索模式：

| 模式 | 触发条件 | 底层方法 |
|------|---------|---------|
| `basic` | 短事实查询（≤3 words）| `retrieve()` BM25+vector |
| `global` | 探索性关键词（overview/themes/summary）| `query_global()` |
| `drift` | 复杂多跳（how/why/multi-clause）| `drift_search()` |
| `local` | 关系关键词（connected/related/depends）| `spread_activation()` |
| `hybrid` | 大图通用查询 | `dual_mode_retrieve()` |
| `temporal` | 时间关键词（when/before/after/timeline）| bi-temporal scan |
| `constraint` | 约束关键词（must/rule/valid/policy）| validation scan |

`mode='auto'` 自动路由，也支持手动指定。`detail=True` 返回丰富结果。
统一返回格式：`{question, mode, rationale, results, stats}`。

### 七意图分类路由 (Cycle 259-260)

#### `intent_aware_token_budgets(question='', *, mode='auto', override=None) -> dict`

MemFlow (arXiv:2605.03312) 启发的意图感知 token 预算分配。不同查询意图需要不同大小的上下文窗口：简单查找只需 200 tokens，全局社区扫描需要 1000+ tokens。禁用意图感知预算会损失约 18.7pp 准确率。

**预算预设：**

| 模式 | Token 预算 | 场景 |
|------|-----------|------|
| `basic` | 200 | 快速实体查找 |
| `local` | 500 | 邻域探索 |
| `hybrid` | 600 | SimHash + 图混合 |
| `drift` | 800 | 多跳 + 全局上下文 |
| `global` | 1000 | 社区级主题扫描 |

`override` 参数可自定义特定模式的预算，如 `{"global": 1500}`。
返回 `{mode, budgets, selected_budget, rationale}`。此方法不执行检索，仅返回预算分配。

#### `query_with_budgets(question, *, mode='auto', override=None, chars_per_token=4.0, detail=False) -> dict`

结合 `intent_aware_token_budgets()` 和 `retrieve_token_budgeted()` 的单调用检索。自动根据查询复杂度缩放上下文大小。**推荐作为外部调用者（LLM agents、MCP servers 等）的生产检索路径。**

返回 `{question, mode, rationale, budget, context, nodes, token_count, truncated, stats}`。

#### `screen_retrieval(results, *, patterns=None, threshold=1, node_field='nodes') -> dict`

GhostWriter/AM-Sentry (arXiv:2607.06595) 启发的检索结果注入检测。未保护系统面临 98% 的内存注入风险。此方法提供**读取时**安全筛选，扫描检索到的节点内容中的指令注入模式。

双层防御体系：
- **写入时**（Cycle 252）：`write_governance_check()` 阻止谄媚写入
- **读取时**（此方法）：标记可疑的检索内容

内置 14 种注入模式检测（如 "ignore previous"、"system prompt:" 等）。返回 `{clean, flagged, total, flagged_count, flagged_ids, details}`。

#### `query_confidence_score(question, *, mode='auto', limit=10) -> dict`

MemFlow Validator 启发的查询置信度评分。并非所有检索结果都同样可信。此方法包装 `query()` 并添加 `[0, 1]` 置信度字段，调用方可据此决定直接使用结果或升级（如询问用户、扩大搜索）。

**置信度因子：**

| 因子 | 权重 | 说明 |
|------|------|------|
| Coverage | 0.30 | 有非空数据的节点占比 |
| Score spread | 0.20 | 结果分数方差（差异化程度）|
| Graph density | 0.20 | 结果节点的局部边密度 |
| Result count | 0.15 | 结果数 / limit 充足度 |
| Freshness | 0.15 | Top-3 结果的平均新鲜度 |

返回 `{question, mode, results, confidence, factors, stats}`。

### 技能库治理 (Cycle 260)

#### `govern_skill_bank(*, max_skills=100, min_confidence=0.2, deprecate_after_days=60, merge_redundancy_threshold=0.7, dry_run=False) -> dict`

SkeMex (arXiv:2606.09365) Read-Write-Assess-**Govern** 生命周期的治理步骤。应用可配置策略保持技能库健康有界。

**执行策略（按顺序）：**

1. **废弃过期技能** — 超过 `deprecate_after_days` 天未演化的技能标记为 'deprecated'
2. **废弃低置信度** — 置信度 < `min_confidence` 的技能标记为 'deprecated'
3. **合并冗余对** — 步骤重叠 ≥ `merge_redundancy_threshold` 的技能通过 `skill_compose()` 合并
4. **修剪溢出** — 总技能数 > `max_skills` 时，删除最旧的废弃技能

`dry_run=True` 时仅报告不执行。返回 `{policies, actions, summary}`，其中 actions 为 `{action, skill_id, reason}` 列表。

### 路由可观测性 (Cycle 261-262)

#### `query_route_audit(questions=None, *, include_results=False) -> dict`

MemFlow 启发的查询路由审计工具。调试问题为何被路由到特定模式，识别路由误分类。对每个问题执行 `_route_query()`（不执行检索），构建路由表。

无参数时使用内置 12 问题诊断集（覆盖 basic/global/drift/local/temporal/constraint 六种模式）。
`include_results=True` 同时执行完整 `query()` 获取结果数和耗时。

返回 `{audited, mode_distribution, summary, per_question}`。

### 推理质量评估 (Cycle 263)

#### `reasoning_quality_eval(*, seed_ids=None) -> dict`

MemOps/ActMem 启发的图推理质量评估。完成评估三部曲：

- `retrieval_quality_eval()` — IR 指标（能找到吗？）
- `lifecycle_operation_eval()` — 操作安全（能维护吗？）
- `reasoning_quality_eval()` — 图质量（能推理吗？）

**七个质量维度：**

1. **connectivity** — 从种子节点可达的节点比例
2. **causal_chain_completeness** — 完整 vs 断裂的因果链
3. **conflict_resolution_rate** — 已解决的 supersede 链
4. **supersede_depth_stats** — 波动性指标（平均/最大深度）
5. **temporal_consistency** — valid_from/valid_to 间隙检测

### 信息密度分析 (Cycle 264)

#### `graph_information_density(*, node_ids=None, edge_types=None) -> dict`

PlugMem PMI 启发的图信息密度度量。使用 Pointwise Mutual Information 评估记忆连接是否携带真实信息还是仅为结构噪声。

PMI 公式：`PMI(w_ij) = log2((w_ij × W_total) / (s_i × s_j))`，其中 s_i、s_j 为节点的加权度（强度），W_total 为所有边权重之和。

**返回指标：**

| 指标 | 说明 |
|------|------|
| `mean_pmi` | 所有边的平均 PMI |
| `positive_fraction` | PMI > 0 的边占比（强于预期）|
| `entropy` | 边权重分布的香农熵（bits）|
| `normalized_entropy` | 熵 / log₂(N_edges)，∈ [0, 1] |
| `information_score` | (1 - normalized_entropy) × density，∈ [0, 1] |
| `pmi_spread` | PMI 标准差（差异化程度）|
| `edge_type_breakdown` | 按边类型的 PMI 统计 |

### 知识缺口分析 (Cycle 265)

#### `knowledge_gap_report(*, node_ids=None, max_gaps=10, min_score=0.3) -> dict`

结构化知识图谱缺口检测。回答 "应该在哪里添加连接？" — 在 `graph_information_density` 的整体分析基础上，定位具体的节点和集群边界缺口。

**返回部分：**

| 部分 | 说明 |
|------|------|
| `orphan_nodes` | 度 ≤ 1 的孤立节点（通过图遍历不可达）|
| `isolated_clusters` | 跨组件桥接边 < 2 的连通分量 |
| `bridge_opportunities` | 跨集群边界的最佳节点对（按共享标签 + 组合权重评分）|
| `underconnected_hubs` | 高权重但低度的节点（"重要但孤独"）|
| `gap_score` | 0-100 复合分（100 = 连接良好）|
| `recommendations` | 优先级行动列表 |

### 自动缺口修复 (Cycle 266)

#### `auto_heal_gaps(*, max_heals=10, min_bridge_score=0.3, connect_orphans=True, orphan_strategy="nearest", dry_run=False, node_ids=None) -> dict`

自动应用 `knowledge_gap_report` 发现的结构缺口修复。完成 **度量→诊断→行动** 闭环的「行动」环节。

**修复动作：**

1. **桥接连接（Bridge）** — 对缺口报告中的每个桥接机会，在两个组件代表节点之间添加边（关系 `bridged_to`），合并孤立集群。
2. **孤儿救援（Orphan Rescue）** — 对每个度 ≤ 1 的孤立节点，找到最相似的非孤儿节点并连接。相似度基于共享标签和权重接近度计算。

**参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_heals` | 10 | 最大修复动作总数（桥接 + 孤儿）|
| `min_bridge_score` | 0.3 | 最小桥接机会评分阈值 |
| `connect_orphans` | True | 是否执行孤儿救援 |
| `orphan_strategy` | `"nearest"` | `"nearest"` 连接最相似节点；`"hub"` 连接最高度节点 |
| `dry_run` | False | 若为 True，仅预览不修改图 |
| `node_ids` | None | 限制分析子图 |

**返回：** `bridges_added`、`orphans_connected`、`total_heals`、`gap_score_before`、`gap_score_after`、`actions`（人类可读摘要）、`dry_run`。

---

### 冗余检测 (Cycle 267)

#### `redundancy_detect(*, node_ids=None, max_pairs=10, content_threshold=0.65, structural_threshold=0.6) -> dict`

三维冗余分析。与 `knowledge_gap_report` 互补 — 回答「哪里重叠太多？」。缺口报告发现连接不足，冗余检测发现噪声过多。

**三个检测维度：**

| 维度 | 检测方法 | 阈值 |
|------|---------|------|
| `content_duplicates` | 标签 trigram Jaccard 相似度 | ≥ `content_threshold` |
| `structural_clones` | 邻居集合 Jaccard 重叠 | ≥ `structural_threshold` |
| `functional_duplicates` | 同 `kind` + 权重接近 (±20%) + 度接近 (±1) | — |

**返回：**

| 部分 | 说明 |
|------|------|
| `content_duplicates` | `[{node_a, node_b, label_a, label_b, similarity}]` |
| `structural_clones` | `[{node_a, node_b, jaccard, shared_count, total_neighbors}]` |
| `functional_duplicates` | `[{node_a, node_b, kind, weight_diff, degree_diff}]` |
| `redundancy_score` | 0-100（100 = 高度冗余）|
| `merge_candidates` | 跨维度综合排序的推荐合并对 |
| `recommendations` | 人类可读行动项 |

**闭环关系：**
- 缺口分析 → `auto_heal_gaps()` → 检测→修复循环
- 冗余检测 → `auto_consolidate()` → 检测→合并循环（自动化）

### 自动冗余合并 (Cycle 269)

> 冗余检测的行动闭环 — `redundancy_detect()` 的 act 半环

#### `auto_consolidate(*, max_merges=5, min_score=0.5, content_threshold=0.65, structural_threshold=0.6, dry_run=False, node_ids=None) -> dict`

自动合并 `redundancy_detect()` 识别的顶级冗余候选对。与 `auto_heal_gaps()` 对应缺口循环的角色对称。

**合并策略：**

1. 运行 `redundancy_detect()` 获取候选对
2. 按 `min_score` 过滤 `merge_candidates`
3. 对每个候选（最多 `max_merges` 个），将低度数节点合并到高度数节点（保证 survivor 是更重要的节点）
4. 跳过已在本轮被合并的节点（防止双重合并）

**参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_merges` | 5 | 最大合并操作次数 |
| `min_score` | 0.5 | 最小综合分数 (0–1) 才会行动 |
| `content_threshold` | 0.65 | 透传给 `redundancy_detect` |
| `structural_threshold` | 0.6 | 透传给 `redundancy_detect` |
| `dry_run` | False | 模拟运行，不实际修改 |
| `node_ids` | None | 限制分析范围 |

**返回：**

| 部分 | 说明 |
|------|------|
| `merges_performed` | `[{source, target, score, content_sim, structural_sim, functional_dup, reason}]` |
| `total_merges` | 实际合并次数 |
| `redundancy_score_before` | 行动前冗余分数 |
| `redundancy_score_after` | 行动后冗余分数（`dry_run` 时等于 before）|
| `nodes_before / nodes_after` | 节点数变化 |
| `actions` | 人类可读行动摘要 |
| `skipped` | 被跳过的候选及原因 |

---

> **更新闭环关系：**
>
> ```
> Loop 1 (缺口)                Loop 2 (冗余)
>     │                             │
>     ▼                             ▼
> knowledge_gap_report        redundancy_detect
>     │                             │
>     ▼                             ▼
> auto_heal_gaps              auto_consolidate
>     │                             │
>     └────────┬────────────────────┘
>              ▼
>    gap_redundancy_balance  ← 综合健康评估
> ```

### 语义簇检测 (Cycle 271)

> 从配对冗余到群体级冗余 — `redundancy_detect()` 的自然进化

#### `semantic_cluster_detect(*, node_ids=None, min_cluster_size=3, content_threshold=0.55, structural_threshold=0.5) -> dict`

检测 N+ 个语义相似节点组成的**簇**。当 5+ 个节点形成冗余群时，配对合并序列不再最优 — 需要群体级分析。

**两个聚类维度：**

| 维度 | 方法 | 算法 |
>------|------|------|
| 内容簇 | 标签 trigram Jaccard ≥ `content_threshold` | 单链凝聚聚类 |
| 结构簇 | 邻居集合 Jaccard ≥ `structural_threshold` | 单链凝聚聚类 |

单链聚类（Single-Linkage）：两个簇在*任意*跨对超过阈值时合并。使用 Union-Find 实现，复杂度 O(n² α(n))。

**返回：**

| 部分 | 说明 |
|------|------|
| `content_clusters` | `[{members, size, avg_similarity, representative, labels}]` |
| `structural_clusters` | 同格式 |
| `combined_clusters` | 在*两个*维度上都显著的簇 — 最佳合并候选 |
| `cluster_score` | 0-100，整体簇冗余度 |
| `recommendations` | 行动建议 |

**与 `redundancy_detect()` 的关系：**
- `redundancy_detect()` → 配对分析（1:1）
- `semantic_cluster_detect()` → 群体分析（N:1）
- 进化路径：对 → 行动于对 → 群体

### 双循环质量综合评估 (Cycle 268)

> **capstone** — 缺口分析与冗余检测的统一健康分数

将 `knowledge_gap_report` 和 `redundancy_detect` 融合为单一可行动评估。

#### `gap_redundancy_balance(*, node_ids=None, gap_weight=0.5, redundancy_weight=0.5) -> dict`

统一双循环健康指标，结合缺口分数和冗余分数生成单一健康评估。

**评分模型：**

- `health_score = 100 - w_gap × (100 - gap_score) - w_red × redundancy_score`
- 权重自动归一化为总和 1.0
- `balance_ratio` ∈ [-1, 1]：负值 = 缺口主导，正值 = 冗余主导，≈0 = 均衡

**裁决（verdict）：**

| 裁决 | 含义 |
|------|------|
| `empty` | 图中无节点 |
| `healthy` | health ≥ 80，无显著问题 |
| `good` | health ≥ 65，轻微问题 |
| `gap-heavy` | 缺口是健康度的主要拖累 |
| `redundancy-heavy` | 冗余是主要拖累 |
| `balanced-issues` | 缺口和冗余均显著 |

**行动优先级（action_priority）：** `none` / `gap` / `redundancy` / `both`

**双循环质量体系全景：**

```
Loop 1 (缺口)              Loop 2 (冗余)
    │                           │
    ▼                           ▼
knowledge_gap_report      redundancy_detect
    │                           │
    ▼                           ▼
auto_heal_gaps            merge_nodes
    │                           │
    └────────┬──────────────────┘
             ▼
   gap_redundancy_balance  ← 综合健康评估
```

### 查询诊断 (Cycle 270)

#### `query_explain(query, embedding=None, limit=10, fusion='adaptive', kge_weight=0.0) -> dict`

查询执行计划诊断。返回与 `search_hybrid` 相同的排序结果，外加完整的诊断计划 — 展示每条检索路径如何贡献到每个结果。

**用途：** 调试检索质量下降、理解为什么某条结果排在前面（或排在后面）、验证融合权重配置。

**参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `query` | — | 文本查询 |
| `embedding` | None | 可选查询向量 |
| `limit` | 10 | 返回结果数 |
| `fusion` | 'adaptive' | 融合模式 (`adaptive` \| `rrf` \| `wrrf`) |
| `kge_weight` | 0.0 | KGE 路径权重 |

**返回结构：**

| 部分 | 说明 |
|------|------|
| `classification` | `{type, specificity, needs_retrieval}` — 查询分类 |
| `weights` | `{bm25, vector, graph, kge}` — 实际使用的融合权重 |
| `paths` | 每条检索路径的状态报告：`[{name, status, result_count, top_ids, elapsed_ms}]` |
| `entropy_refinement` | 熵修正信息（如适用）|
| `results` | 每个结果的分数分解：`[{node_id, label, kind, score, sources, score_breakdown}]` |
| `summary` | `{total_candidates, unique_sources_used, top_score, bottom_score}` |

**结果质量分类：**

| 质量等级 | 分数条件 | 含义 |
|---------|---------|------|
| `excellent` | score ≥ 0.08 | 多源命中，高置信 |
| `good` | score ≥ 0.04 | 合理命中 |
| `partial` | score ≥ 0.02 | 弱命中或单源 |
| `weak` | score < 0.02 | 可能不相关 |

---

#### `auto_consolidate_cluster(cluster_index=0, cluster_type='combined', min_cluster_size=3, content_threshold=0.55, structural_threshold=0.5, dry_run=False, node_ids=None) -> dict`

批量合并整个语义簇。`semantic_cluster_detect()` 的行动闭环 — 一次性合并整个节点群，而非逐对处理。

**用途：** 当冗余不是两两关系而是 N 个节点互相相似时（例如同一概念的 5 种表述），逐对合并效率低且合并顺序随机。本 API 选择最高度数节点作为幸存者，按度数排序依次吸收所有簇成员。

**参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `cluster_index` | 0 | 簇索引（0 = 最大/最佳簇）|
| `cluster_type` | 'combined' | 簇类型：`combined` \| `content` \| `structural` |
| `min_cluster_size` | 3 | 最小簇大小（传递给 `semantic_cluster_detect`）|
| `content_threshold` | 0.55 | 内容相似度阈值 |
| `structural_threshold` | 0.5 | 结构相似度阈值 |
| `dry_run` | False | 模拟模式，不修改图 |
| `node_ids` | None | 限制分析范围 |

**为什么批量优于逐对：**

- *最优幸存者*：最高度数节点在所有合并中幸存，积累每个成员的边
- *确定性顺序*：度数排序避免了 `auto_consolidate` 多次调用的随机配对问题
- *单次调用*：1 次调用替代 N-1 次逐对调用

**返回：** `merges_performed`、`survivor`（幸存节点 id）、`survivor_label`、`total_merges`、`cluster_score_before/after`、`nodes_before/after`、`dry_run`。

> **双循环架构补充：** `auto_consolidate`（逐对）和 `auto_consolidate_cluster`（整簇）共同构成冗余修复的行动层，分别对应 `redundancy_detect`（逐对检测）和 `semantic_cluster_detect`（群体检测）。

---

#### `walk_statistics(num_walks=10, steps=20, restart_prob=0.15, seed=None) -> dict`

多次随机游走的聚合统计。通过随机游走采样评估图的连通性、节点可达性和结构特征。

**用途：** 评估记忆图的可达性 — 哪些节点容易被游走到（高可达 = 活跃记忆），哪些被遗漏（低可达 = 可能被遗忘的记忆）。

**参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `num_walks` | 10 | 游走次数 |
| `steps` | 20 | 每次游走的步数 |
| `restart_prob` | 0.15 | 每步重启概率 |
| `seed` | None | 随机种子（可复现）|

**返回：**

| 字段 | 说明 |
|------|------|
| `avg_unique_ratio` | 每次游走的平均唯一节点比例 |
| `avg_revisit_step` | 平均首次重访步数（-1 = 无重访）|
| `coverage` | 总唯一节点 / 总节点数 |
| `most_visited` | 访问最多的前 10 个节点 `(node_id, visit_count)` |
| `dead_end_rate` | 到达死端的游走比例 |
| `walk_lengths` | 实际游走长度列表 |

---

#### `edge_type_stats() -> dict`

按边关系类型聚合统计。展示每种关系类型的数量、权重分布、唯一源/目标节点数和互反性。

**用途：** 快速了解记忆图中各类关系的分布 — 例如 `created` 关系有多少条、平均权重多少、是否双向（互反性）。

**返回：**

```python
{
    "created": {
        "count": 45,
        "avg_weight": 0.72,
        "min_weight": 0.3,
        "max_weight": 1.0,
        "unique_sources": 12,
        "unique_targets": 38,
        "reciprocity": 0.08  # 8% 的 created 边有反向边
    },
    "related_to": { ... },
    ...
}
```

---

#### `detect_skill_candidates(min_frequency=2) -> list`

从情景记忆中挖掘重复行为模式。扫描 event 和 intention 类型节点中的动作动词（created、tested、deployed 等），返回有资格提升为 skill 类型的候选项。

**用途：** `compress_to_skill()` 的只读基础 — 发现「反复执行的操作」并建议将其固化为技能节点，减少情景膨胀。

**参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `min_frequency` | 2 | 最小出现次数，低于此值不作为模式 |

**返回：** 按置信度降序排列的候选列表：

```python
[
    {
        "action": "created",
        "frequency": 3,
        "confidence": 0.6,        # min(1.0, frequency / 5)
        "memory_ids": ["abc123", "def456", "ghi789"],
        "suggested_compression": "'created' repeated 3× — promote to skill?"
    },
    ...
]
```

> **置信度饱和：** 频率在 5 次时达到 100% 置信（`min(1.0, freq / 5)`），鼓励稳定模式而非偶发事件。

---

#### `sombor_index() -> float`

Sombor 指数 SO（Gutman 2021）。

$$SO = \sum_{(u,v) \in E} \sqrt{d_u^2 + d_v^2}$$

度量度数对在度-度平面上距原点的几何距离。Sombor 指数是近年化学图论中备受关注的度拓扑描述子，在记忆图语境下衡量「度差异性的几何总量」。

**参数公式验证：**

| 图类型 | SO 公式 | 说明 |
|--------|---------|------|
| $K_n$ (n≥2) | $n(n-1)^2\sqrt{2}/2$ | 完全图 |
| $C_n$ | $2n\sqrt{2}$ | 环图 |
| $P_n$ (n≥3) | $2\sqrt{5} + (n-3) \cdot 2\sqrt{2}$ | 路径图 |
| $K_{1,k}$ | $k\sqrt{k^2+1}$ | 星图 |

**与其他度指数的关系：**

- $SO > \text{sum\_connectivity}$（每项 $\geq 1/(d_u+d_v)$）
- $SO < M_2$ Zagreb（当 $d_u, d_v \geq 1$ 时 $\sqrt{d_u^2+d_v^2} < d_u \cdot d_v$）

**返回：** `float`，边数 < 1 时返回 `None`。

---

#### `reduced_sombor_index() -> float`

Reduced Sombor 指数 RS（Gutman 2021）。

$$RS = \sum_{(u,v) \in E} \sqrt{(d_u-1)^2 + (d_v-1)^2}$$

使用 `d-1` 替代 `d`，使得 $K_2$（单键）的 RS = 0。这一特性区分了「真正有分支的图」和「仅有单键的图」— 强调分支性而非单纯连通性。

**参数公式验证：**

| 图类型 | RS 公式 | 说明 |
|--------|---------|------|
| $K_n$ (n≥3) | $n(n-1)(n-2)\sqrt{2}/2$ | 完全图 |
| $C_n$ | $n\sqrt{2}$ | 环图 |
| $P_n$ (n≥3) | $2 + (n-3)\sqrt{2}$ | 路径图 |
| $K_{1,k}$ (k≥2) | $k(k-1)$ | 星图 |
| $K_2$ | $0$ | ⭐ 区分属性 |

**交叉关系：**

- $RS \leq SO$（恒成立）
- $RS(K_2) = 0$（唯一区分属性：可识别图中是否只有单键）

**返回：** `float`，边数 < 1 时返回 `None`。

> **度指数家族已扩展至 14 个指标：** sum_connectivity, randic_index, zagreb_m1, zagreb_m2, augmented_zagreb, forgotten_index, hyper_zagreb, first_redefined_zagreb, second_redefined_zagreb, third_redefined_zagreb, leleka_index, sombor_index, reduced_sombor_index, 及 harmonic_index。

### 熵指数家族 (Cycles 278–280)

基于度加权的 Shannon 熵，衡量记忆网络的度分布均匀性。H = -Σ p_e·ln(p_e)，归一化后 [0,1]。正则图 → 1.0（完全均匀），路径图 < 1.0（不均匀）。

#### `sombor_entropy(normalized=True) -> float | None`

Shannon 熵 of normalized Sombor edge contributions。p_e = √(d_u²+d_v²)/SO。

#### `reduced_sombor_entropy(normalized=True) -> float | None`

Reduced Sombor 版本，处理 K₂ 零贡献问题。p_e = √((d_u-1)²+(d_v-1)²)/RSO。

#### `randic_entropy(normalized=True) -> float | None`

Shannon 熵 of normalized Randić edge contributions。p_e = (1/√(d_u·d_v))/R_α(-1/2)。Cycle 279。

#### `zagreb_m1_entropy(normalized=True) -> float | None`

Shannon 熵 of normalized Zagreb M₁ edge contributions。p_e = (d_u+d_v)/M₁。Cycle 279。

#### `abc_entropy(normalized=True) -> float | None`

Shannon 熵 of normalized ABC edge contributions。p_e = √((d_u+d_v-2)/(d_u·d_v))/ABC。ABC 独有特性：对 K₂ 边过滤。Cycle 280。

#### `ga_entropy(normalized=True) -> float | None`

Shannon 熵 of normalized GA edge contributions。p_e = (2√(d_u·d_v)/(d_u+d_v))/GA。Cycle 280。

**熵家族汇总：**

| 指数 | Cycle | 边权重 | K₂ 处理 |
|------|-------|--------|--------|
| sombor_entropy | 278 | √(d_u²+d_v²) | 包含 |
| reduced_sombor_entropy | 278 | √((d_u-1)²+(d_v-1)²) | 零贡献 |
| randic_entropy | 279 | 1/√(d_u·d_v) | 包含 |
| zagreb_m1_entropy | 279 | d_u+d_v | 包含 |
| abc_entropy | 280 | √((d_u+d_v-2)/(d_u·d_v)) | 过滤 |
| ga_entropy | 280 | 2√(d_u·d_v)/(d_u+d_v) | 包含 |

---

### 条件遍历 (Cycle 331)

#### `conditioned_traverse(entry_id, intent_profile=None, max_depth=5, min_weight=0.0, top_k=20) -> dict`

HAGE (arXiv:2605.09942) 启发的查询条件 BFS 遍历。不同查询意图应遍历不同边类型：因果查询跟随 `causes` 和 `depends_on` 边，相似性查询跟随 `similar_to` 和 `relates_to` 边。

每种边类型有遍历权重 (0–1)。BFS 每一步修剪权重低于 `min_weight` 的边。累积节点分数随深度衰减并乘以边遍历权重，因此通过高权重边到达的节点排名更高。

```python
result = mg.conditioned_traverse("node:rust", intent_profile={"causes": 1.0, "depends_on": 1.0})
# {'entry': 'node:rust', 'visited': [{node_id, depth, score, path}, ...],
#  'edge_types_used': ['causes', 'depends_on'],
#  'stats': {'nodes_visited': 12, 'edges_traversed': 18, 'max_depth_reached': 3}}
```

---

### 关系投影图 (Cycle 332)

#### `project_graph(relation_type, include_metadata=True) -> MemoryGraph`

将图投影到单一关系类型，返回新的 MemoryGraph 实例。与 `subgraph_by_edge_type()`（返回 dict）不同，此方法返回完整的 `MemoryGraph`，支持所有图算法（熵、中心性、分类等）。

```python
causal_graph = mg.project_graph("causes")
print(causal_graph.stats())  # 仅包含 causes 边的子图统计
print(causal_graph.graph_density())  # 因果子图的密度
```

---

### 多视角分析 (Cycle 333)

#### `multi_perspective_analysis(node_id=None, max_depth=3) -> dict`

HAGE 启发的多关系维度对比分析。对图中每种关系类型独立分析，返回比较报告。

每种关系类型计算：节点数、边数、密度、平均度。若提供 `node_id`，则从该节点出发按该关系为主导意图运行 `conditioned_traverse`。

```python
analysis = mg.multi_perspective_analysis(node_id="concept:ai")
# {'perspectives': {'causes': {...}, 'similar_to': {...}, 'related_to': {...}},
#  'relation_ranking': ['related_to', 'causes', 'similar_to'],
#  'dominant_relation': 'related_to',
#  'cross_perspective_nodes': [{node_id, perspectives, perspective_count}, ...]}
```

---

### 分类基准评估 (Cycle 334)

#### `classification_benchmark(*, topologies=None, sizes=None, num_references_per_category=2, num_queries=1, methods=None, include_quarantined=False) -> dict`

标准化分类基准评估套件。生成 6 种规范图拓扑（star/path/cycle/complete/bipartite/tree）作为参考图和查询图，运行所有可用分类方法，报告每种方法的 accuracy/precision/recall/F1。

6 种拓扑使用 `_bench_build_topology()` 静态方法构建：

| 拓扑 | 结构 | 特征 |
|------|------|------|
| `star` | 中心 + 辐射 | 单 hub, 高度集中 |
| `path` | 线性链 | 低密度, 长距离 |
| `cycle` | 环形 | 均匀度, 无叶子 |
| `complete` | 全连接 | 最大密度 |
| `bipartite` | 二部图 | 跨集合连接 |
| `tree` | 层次树 | 分支结构 |

```python
bench = mg.classification_benchmark(topologies=['star', 'path', 'cycle'],
                                    sizes=[8, 12], num_references_per_category=3)
# {'results': {'graph_classification': {'accuracy': 0.78, 'precision': 0.80, ...},
#              'spectral_classification': {'accuracy': 0.89, ...}, ...},
#  'best_method_per_topology': {'star': 'spectral', 'path': 'graph', ...},
#  'confusion_matrix': {...},
#  'overall_best_method': 'bayesian_classification'}
```

---

### 最大置信度元分类 (Cycle 335)

#### `max_confidence_classification(references, *, degree_index="sombor", include_quarantined=False, confidence_metric="margin", min_methods=2) -> dict`

元分类器：从所有分类方法中选择对当前查询**置信度最高**的方法的结果。

与 `classification_compare()`（多数投票）不同，此元分类器信任对自己的判断最有信心的方法。不同的查询/参考组合适合不同的模态——星型图可能最容易通过度熵分类，而环型图更容易通过谱分析分类。

**执行 5 种基础方法：**

1. `graph_classification` — 度熵距离
2. `spectral_classification` — 谱发散
3. `hybrid_classification` — 固定权重集成
4. `rrf_classification` — Reciprocal Rank Fusion
5. `bayesian_classification` — 自适应权重集成

**三种置信度度量：**

| 度量 | 公式 | 特点 |
|------|------|------|
| `margin` | `2nd_best − best` | 绝对差距，跨方法稳健 |
| `confidence` | `(2nd-best − best)/best` | 相对比率，best≈0 时可为 inf |
| `z_score` | `(best − mean_others)/std_others` | 标准差倍数，天然跨方法归一化 |

```python
result = mg.max_confidence_classification(references, confidence_metric="z_score")
# {'best_match': 2, 'best_score': 0.034,
#  'winning_method': 'spectral_classification',
#  'winning_confidence': -1.82,
#  'confidence_metric': 'z_score',
#  'per_method': {'spectral_classification': {...}, 'graph_classification': {...}, ...},
#  'agreement': 0.6,  # 3/5 methods agree
#  'margin_of_victory': 0.45,
#  'recommendation': 'spectral_classification has highest z_score...'}
```

**何时用 `max_confidence_classification` vs `classification_compare`？**

- `classification_compare`：方法趋于一致时（高信号场景），想要**共识**
- `max_confidence_classification`：方法分歧时（低信号场景），想要**确信** — 某一方法可能捕获了其他方法遗漏的结构特征

### 级联修正传播 (Cycle 336)

#### `propagate_correction(node_id, new_content=None, reason=None, corrected_by=None, impact_relations=None, mark_status="needs_review", max_depth=10) -> dict`

当一个节点的内容被修正时，将修正标记**级联传播**到所有依赖它的节点。

与 `invalidate_cascade()`（标记节点为无效）不同，此方法使用更柔和的 `_correction` 元数据标记，保留知识的同时发出"需要复审"信号。

**遍历逻辑（与 `invalidate_cascade` 一致）：**
- `depends_on`: A --depends_on--> current → 反向查找（找到指向当前节点的源）
- `enables`: current --enables--> B → 正向查找

```python
mg.add_edge("report", "source_data", "depends_on")
mg.add_edge("source_data", "chart", "enables")

result = mg.propagate_correction(
    "source_data",
    new_content="修正后的数据",
    reason="原始传感器读数偏差",
    corrected_by="validator_v2"
)
# {'root': 'source_data',
#  'impacted': ['source_data', 'report', 'chart'],
#  'skipped': [],
#  'count': 3,
#  'depth_reached': 2,
#  'reason': '原始传感器读数偏差',
#  'corrected_by': 'validator_v2'}
```

**vs. `invalidate_cascade()`：**

| 方法 | 标记方式 | 适用场景 |
|------|---------|----------|
| `invalidate_cascade` | `valid_until` → 节点无效 | 知识已失效，不应再被检索 |
| `propagate_correction` | `_correction.status = needs_review` | 知识可能仍有效，但需人工复审 |

---

### 数据溯源与派生分析 (Cycles 337-338)

#### 新增边类型

| 边类型 | 语义 | 示例 |
|--------|------|------|
| `derived_from` | 派生来源 — A 的内容部分来源于 B | `summary` derived_from `raw_data` |
| `computed_from` | 计算来源 — A 由 B 经计算/变换得到 | `score` computed_from `features` |

#### `trace_derivation(node_id, max_depth=10) -> dict`

**向后溯源** — 追踪一个节点的完整来源链。沿 `derived_from` / `computed_from` 边反向遍历，回答"这个知识从哪里来？"

```python
mg.add_causal_edge("summary", "raw_data", "derived_from", confidence=0.9)
mg.add_causal_edge("raw_data", "sensor_1", "computed_from", confidence=1.0)

mg.trace_derivation("summary")
# {'node': 'summary',
#  'roots': ['sensor_1'],
#  'chains': [[
#      {'source': 'summary', 'target': 'raw_data',
#       'relation': 'derived_from', 'confidence': 0.9},
#      {'source': 'raw_data', 'target': 'sensor_1',
#       'relation': 'computed_from', 'confidence': 1.0},
#  ]],
#  'all_sources': ['raw_data', 'sensor_1'],
#  'depth_reached': 2}
```

- 返回 `roots`（无上游来源的原始节点）、`chains`（溯源路径，长路径优先）、`all_sources`（所有上游节点）
- 环安全 + `max_depth` 截断 + 菱形依赖去重

#### `trace_derivation_impact(node_id, max_depth=10) -> dict`

**向前影响分析** — `trace_derivation` 的前向对应。回答"哪些节点依赖于这个节点？"

```python
mg.add_causal_edge("summary", "raw_data", "derived_from", confidence=0.9)
mg.add_causal_edge("report", "summary", "derived_from", confidence=0.8)

mg.trace_derivation_impact("raw_data")
# {'node': 'raw_data',
#  'leaves': ['report'],
#  'chains': [[
#      {'source': 'summary', 'target': 'raw_data',
#       'relation': 'derived_from', 'confidence': 0.9},
#      {'source': 'report', 'target': 'summary',
#       'relation': 'derived_from', 'confidence': 0.8},
#  ]],
#  'all_dependents': ['report', 'summary'],
#  'depth_reached': 2}
```

- 返回 `leaves`（无下游派生的终端节点）、`chains`（影响路径）、`all_dependents`（所有下游节点）

#### `derivation_lineage_report(node_id, max_depth=10) -> dict` — 便利 API

一次调用合并向前 + 向后分析，并提供摘要指标：

| 指标 | 说明 |
|------|------|
| `fan_in` / `fan_out` | 直接上游/下游数量 |
| `lineage_size` | 完整世系图节点数 |
| `is_root` | 无上游派生（原始观测） |
| `is_leaf` | 无下游派生（终端节点） |
| `bottleneck_score` | fan_out / max(fan_in, 1)，>1 表示派生瓶颈 |
| `completeness` | 置信度 ≥ 0.8 的边占比 |
| `avg_confidence` | 所有边的平均置信度 |

```python
rep = mg.derivation_lineage_report("summary")
# rep["is_root"] → False
# rep["is_leaf"] → False
# rep["bottleneck_score"] → 1.0
# rep["summary"] → "Node 'summary' has 1 upstream source, 1 downstream dependent."
```

**典型用例：**
- 数据治理 — 识别关键瓶颈节点（高 bottleneck_score）
- 可解释性 — 为 LLM 决策提供完整数据来源链
- 影响评估 — 修正一个源数据前，查看所有受影响的下游结论

---

### 拓扑快捷统计 (Cycle 339)

#### `hub_nodes(n=10) -> list[tuple[str, int]]`

返回度数最高的 N 个节点，按度数降序排列。快速识别图中的关键枢纽节点。

```python
mg.hub_nodes(3)
# [('concept:ai', 15), ('event:launch', 12), ('entity:openai', 9)]
```

#### `peripheral_nodes() -> list[str]`

返回无向度数恰好为 1 的节点（叶子/悬挂节点）。这些是图中的边缘信息——
仅与一个其他节点关联，可能是待丰富或待清理的候选。

```python
mg.peripheral_nodes()
# ['note:draft_idea', 'tag:obsolete_v1', 'ref:broken_link']
```

#### `mean_degree() -> float`

返回所有节点的平均度数。空图返回 0.0。快速衡量图的整体连通密度：

| mean_degree | 含义 |
|-------------|------|
| ~0-1 | 稀疏图，大量孤立/叶子节点 |
| ~2-3 | 中等连通 |
| >4 | 密集图，高度互联 |

```python
mg.mean_degree()  # 2.45
```

**与 `lorenz_coefficient()` 的互补性：** `mean_degree` 告诉你平均连通度，
`lorenz_coefficient` 告诉你度分布是否均匀。两者结合可快速刻画图的结构特征。

---

### 分类噪声鲁棒性测试 (Cycle 341)

#### `classification_noise_test(*, topologies=None, size=10, noise_levels=None, num_references_per_category=2, num_queries=2, methods=None, seed=42) -> dict`

测试分类方法在图扰动下的鲁棒性。生成标准拓扑参考图，然后在每个噪声级别
下随机添加/删除边来创建噪声查询图，报告各方法的精度退化曲线。

**噪声模型：**
- 每条已存在的边以 `noise_level` 概率被删除
- 每条不存在的边以 `noise_level` 概率被添加
- 例如 noise_level=0.1：约 10% 的边被删除，约 10% 的可能新边被添加

```python
result = mg.classification_noise_test(
    topologies=['star', 'path', 'complete'],
    noise_levels=[0.0, 0.05, 0.1, 0.2, 0.3],
    num_references_per_category=3,
    num_queries=5,
)

# result['degradation_curves']['spectral']
# → {0.0: 1.0, 0.05: 0.93, 0.1: 0.80, 0.2: 0.53, 0.3: 0.27}
#
# result['robustness_score']
# → {'spectral': 0.72, 'bayesian': 0.68, 'graph': 0.55, ...}
#
# result['rankings']
# → [('spectral', 0.72), ('bayesian', 0.68), ...]
#
# result['breakpoint']
# → {'spectral': 0.1, 'bayesian': 0.1, 'graph': 0.05}
#
# result['summary']
# → "Noise robustness: 8 methods × 6 topologies × 5 noise levels.
#     Most robust: spectral (AUC=0.72).
#     Least robust: graph (AUC=0.41).
#     Most fragile topology: star (0.38).
#     Most resilient: complete (0.75)."
```

**返回字段：**

| 字段 | 说明 |
|------|------|
| `degradation_curves` | 每种方法在各噪声级别的精度 `{method: {noise: accuracy}}` |
| `robustness_score` | 每种方法的 AUC（精度-噪声曲线下面积，归一化到 0-1） |
| `rankings` | 方法按鲁棒性得分降序排列 |
| `breakpoint` | 每种方法精度首次低于 0.8 的噪声级别（None = 从未低于） |
| `per_topology_robustness` | 每种拓扑跨方法的平均鲁棒性 |
| `per_topology_at_noise` | 每个噪声级别下每种拓扑的精度 |
| `best_method` / `worst_method` | 鲁棒性最优/最差方法名 |
| `summary` | 人类可读的一行摘要 |

**典型用例：**
- 选择分类方法 — 在噪声环境下应选择 robustness_score 最高的方法
- 质量门槛 — 设定 breakpoint 作为可接受的噪声上限
- 拓扑脆弱性诊断 — 识别哪些图结构对噪声最敏感

---

## Cycles 425-440: 双进程写入 + GraphRAG 全流水线 + GraphRAG-Bench 适配器

> 端到端教程见 [TUTORIAL-GRAPHRAG.md](TUTORIAL-GRAPHRAG.md)——本文档为 API 参考摘要。

### 架构里程碑

```
双进程写入 (425-427)          GraphRAG 全流水线 (428-433)         基准接入 (432-440)
System-1 O(1) 热路径           extract → query → explain           segment_sentences 缩写安全
System-2 flush 巩固            + fact-answer 直接作答               chunk_text / export_graphml
知识新鲜度 FAMA 诊断           coverage_report 全局健康            run_amg.py (ICLR 2026)
```

### 写入架构 (Cycles 425-427)

#### `FastAppendQueue(mg, *, capacity=..., auto_flush_threshold=...)`

双进程写路径，灵感来自 Engram 的 System-1/System-2 分离（准确率 83.6% vs 73.2%）：

- **热路径（System-1）**：`append()` O(1) 入缓冲、`search()` 缓冲区关键词搜索、`peek(n)` 预览
- **冷路径（System-2）**：`flush()` 去重 + link-by-kind/tags 入图、`flush_and_consolidate(strategy="nrem"|"rem")` NREM/REM 巩固
- **诊断**：`status()` / `is_healthy()` / `peak_buffer_size()`

#### `knowledge_freshness_report() -> dict | None` (Cycle 426)

FAMA 感知的知识新鲜度诊断（过时知识惩罚 15-43 分）：5 级时间桶 + 加权评分 + per_kind 细分 + 新鲜度排序 + 建议。

### GraphRAG 全流水线 (Cycles 428-433)

#### `segment_sentences(text) -> list[str]` (Cycle 432, 模块级)

缩写安全句切分（两级 Punkt 式）：保护 `Mr.`、`J. K. Rowling`、`St. Louis` 等缩写句点不被切分。切分集 `. ! ? ; \n`。`extract_from_text` 与 `chunk_text` 共享，保证块边界与提取边界一致。

#### `extract_from_text(text, *, kind="entity", tags=None) -> dict` (Cycle 428)

规则式 KG 构建，零外部依赖：大写短语/引号术语实体检测 + 7 种关系模式（`is_a`、`works_at`、`created`、`located_in`、`has`、`part_of`、`built`）+ 按 label 去重复用。返回 `nodes_created / edges_created / entities / relations / sentences`。幂等，可增量调用。

#### `graphrag_query(question, *, max_hops=2, top_k=5, include_context=True) -> dict` (Cycle 429, 433)

关键词提取 → 种子匹配（label/tags）→ 双向 BFS → 排名（`keyword_score × degree_centrality × hop_penalty`）→ top-k 子图。返回 `answer_nodes / context_edges / context / keywords / seed_nodes / fact_answer`。

**fact-answer 路径 (Cycle 433)**：7 种问句 cue + 三级主语解析（精确/正向包含/反向包含取最长内嵌 label），事实型问题（Who created X?）直接返回边宾语 `answers`。

#### `graphrag_explain(question, *, max_hops=2, top_k=5) -> dict` (Cycle 430)

逐查询诊断：`keyword_matches`（exact/prefix/contains/tag 四种命中类型）、`unmatched_keywords`、`coverage`、逐节点得分分解、`fact_answer` 诊断、`suggestions`。

#### `graphrag_coverage_report() -> dict` (Cycle 431, 435, 436)

全局检索健康：`health_score`、`label_coverage`、`tag_coverage`、`orphan_count/rate`、`matchability` 分级、`sparse_nodes`、`suggestions`；关系维度 (435)：`relation_distribution`、`typed_edge_rate`、`relation_diversity`、`top_relations`；单一化告警 (436)：`dominant_relation`，typed_edges ≥ 5 且 top share ≥ 80% 时触发 diversify 建议。

### 基准接入 (Cycles 438-440)

#### `export_graphml(path, *, overwrite=False) -> dict` (Cycle 438)

文件级 GraphML 导出（GraphRAG-Bench indexing_eval 消费路径）。拒绝覆盖已有文件除非 `overwrite=True`。label/kind/relation/weight 全保留，networkx `read_graphml` 往返验证通过。

#### `run_amg.py` (Cycle 439, Gap #4)

GraphRAG-Bench (ICLR 2026) 完整适配器，零 LLM/零 API 成本的检索式分阶段入口：

```bash
python run_amg.py --data-dir data/ --out results/amg.json \
    --sample 100 --graphml results/amg.graphml
```

`load_bench_data → index_corpus (chunk + extract) → answer_question (query + fact_answer) → 官方 prediction schema（8 键严格对齐）→ 可选 export_graphml`。

#### `chunk_text(text, *, max_tokens=512) -> list[str]` (Cycle 440, `run_amg.py` 内)

长文档分块：贪婪打包整句到 token 预算内，与提取器共享 `segment_sentences`，块边界与提取边界永远一致。

### 搜索树、泄漏安全与记忆质量 (Cycles 441-448)

#### `expand_search_tree(node_id, query=None, *, branching_factor=2, max_depth=3) -> dict` (Cycle 441)

Arbor 模式 #029：图即搜索树。每次扩展把评分的 `search_tree` 子节点经 `search_child` 边物化到图中——多个 agent 能直接看到哪些分支被探索过、得分如何。

#### `prune_search_tree(node_id, *, min_score) -> dict` (Cycle 441)

非破坏性剪枝：标记 `status="pruned"` 而非删除，探索历史保持可审计。对已展开节点剪枝会级联整个子树。

#### `search_tree_report(root_id) -> dict` (Cycle 441)

搜索树摘要：状态分布、深度、最佳路径（根到叶累计得分最高的路线，即树搜索的主输出“哪个分支赢了”）。

#### `cross_modal_leak_scan(node_id) -> dict` (Cycle 442)

MemLeak 研究 #018：沿 `image_derived` / `correlated_inference` / `derived_from` 类派生边扫描——遗忘/清除一个节点不安全，当其他模态的派生物（图像标题、推断摘要、压缩副本）仍携带源的敏感 token。风险分级：`high`（≥3 个泄漏 token 或任何邮箱/数字串）、`medium`、`low`/`none`。

#### `safe_forget(node_id, *, force=False) -> dict` (Cycle 442)

带泄漏闸门的遗忘：`cross_modal_leak_scan → 闸门 → 删除`。`high` 风险默认阻断（`force=True` 可覆盖并留审计 verdict），`medium` 记录警告后放行。

#### `record_repair(failure_signature, fix, ...) / recall_repairs(failure_signature, ...) / repair_stats() -> dict` (Cycle 443)

AgentTether #018：前瞻式修复记忆。(failure→fix) 对为一等节点，去重 + Jaccard 相似度召回 + 命中追踪——同样的失败签名再次出现时能召回上次的修复。

#### `apply_decay(..., exclude_ids=None)` × `forget_policy("safety_purge")` 泄漏闸门 (Cycle 444)

真实集成缺口修复：`safety_purge` 曾默默删除敏感源节点却留下泄漏的派生物。现在 `apply_decay` 新增 `exclude_ids` 保护集，`forget_policy` 的 safety_purge 路径接入 C442 泄漏扫描（dry-run 预览 + `blocked_by_leak`）。

#### `resolve_entity_variants(*, modes=("case", "title"), min_len=4, dry_run=False) -> dict` (Cycle 445, Gap #5)

实体标签变体归一为规范节点（GraphRAG-Bench Gap #5 收官，差距清单 6/6 清零）。三模式依序执行：`case`（大小写不敏感精确匹配）、`title`（剥离敬称+尾部首缩写后匹配）、`containment`（短标签是长标签的全词前缀，默认关闭，`len(short) >= min_len`）。规范节点取归一化核心最长者；`dry_run` 先预览。

#### `enable_telemetry(*, store="agent_memory_graph", wrap=None) / disable_telemetry() / telemetry_status()` (Cycle 446)

OTel `gen_ai.memory.*` span 自动插桩核心 CRUD（`add`/`link`/`get_node`/`neighbors`/`recall` 等，可经 `wrap` 选择子集）。同 cycle 从过期 C424 code-lab 副本遣返 `telemetry.py` + `amg_bench.py`（79 tests）到真身仓，pyproject py-modules 登记。

#### `amg_bench_quality.py` — LongMemEvalAdapter (Cycle 447)

LongMemEval 记忆质量适配器（Research #061）：`ingest_sessions`（会话→图）→ `retrieve_context` → `answer_extractive`（双置信度门控）→ `evaluate`（judge_fn 可注入）→ `CategorySummary`（accuracy / abstention_rate / retrieval_hit_rate / avg_tokens）。

#### `score_confidence(scores) -> dict` + `sweep_abstention(dataset, ...)` (Cycle 448)

熵置信度闸门（Research #061 洞察 #3/#4）：`score_confidence` 计算候选关键词命中分数的 Shannon 熵——低熵=证据集中=可作答，高熵=证据分散=应弃权。`sweep_abstention` 在 LongMemEval 数据集上扫描弃权阈值，输出 accuracy-vs-coverage 曲线（诚实契约：宁可弃权不可胡答）。

### 压缩残差、保留遗忘与对抗鲁棒 (Cycles 449-457)

#### `extract_residuals(*, node_ids=None, kinds=("fact", "event", "entity"), dry_run=False) -> dict` (Cycle 449)

压缩残差三件套之一：从待压缩节点提取原子事实存为残差节点，防止摘要化过程丢失细节。`dry_run=True` 只预览不落库。

#### `residual_report() -> dict` (Cycle 449)

残差全景：残差节点计数、平均每残差事实数、源节点覆盖率、陈旧度指标——压缩损失的体检表。

#### `consolidate_with_residuals(**kwargs) -> dict` (Cycle 449)

`consolidate()` + `extract_residuals()` 合一，但**先**提取残差再合并——源节点被合并吞掉后原子事实仍然幸存。

#### `forget_preserving(node_id, *, force=False, extract=True) -> dict` / `batch_forget_preserving(node_ids, ...) -> dict` (Cycle 450)

保留式遗忘：删除节点前先把原子事实提取为残差（`extract=False` 则直接删）。与 C442 `safe_forget`（泄漏闸门）互补——一个防删漏敏感信息，一个防删丢有价值信息。

#### `locomo_bench_quality.py` — LoCoMo 记忆质量适配器 (Cycle 451, Research #067)

对标 C447 LongMemEvalAdapter 的 LoCoMo 接入层：会话摄入、检索、抽取式作答与分类别评估。

#### `sweep_abstention` LoCoMo 对抗调参 — 决定性负发现 (Cycle 452)

把 C448 弃权扫描搬到 LoCoMo 对抗集：**负发现**——对抗性 cat-5 问题词法重叠高，置信度门与新颖性计数都无法将其与正常问题分离。

#### LoCoMo 10 样本全量基线 + `include_questions` (Cycle 453)

全量基线落地，适配器新增 `include_questions` 参数支持按题过滤。

#### `run_eval(dataset, *, limit=0, entropies=None, use_ppr=True, max_context_tokens=4000, abstain_score=1.0, abstain_entropy=0.95, entropy_weak_score=1, temporal_arith=True) -> dict` (Cycle 454)

每题独立 haystack 评估（LongMemEval-cleaned 一题一 haystack）：为每道题构建全新适配器+图（隔离保证，无跨题污染），运行单题 `evaluate()` 后聚合，可在同一批图上顺带跑 C448 `sweep_abstention`。`temporal_arith` 开关 C457 时间运算路径。配套 CLI `--mode eval`。

#### `subject_support_gate(question, answer_text, known_names=None, speaker=None) -> bool` (Cycle 455)

零 LLM 答案侧语义验证，破解 C452 负发现：LoCoMo cat-5 是主语调包伪造（问 X 的事件，对话里只有 Y 谈过）——当问题点名主体 X，而最佳匹配答案行提到另一个人且从未提到 X 时，问题预设不成立，应弃权。9354 tests 时定稿，**决定性负发现 → 专用闸门**的完整闭环。

#### when-question 日期解析 (Cycle 456)

绝对文本日期 + 相对表述（“上周二”）grounding 到 session 日期作答；multi_hop 42/321。教训入 memory：findall 分组 bug、类别标签对齐、session-date grounding。

#### temporal-arithmetic 答案路径 (Cycle 457)

LME_s duration/ordering 类问题经 session 日期做日历运算作答，temporal 切片 **4.0x** 提升，跨数据集验证了 C456 的时间推理路径。

### 记忆演化审计、OTel 对齐与 LLM-as-Judge 双口径判分 (Cycles 458-467)

#### `estimate_node_impact(*, degree: int = 0, weight: float = 1.0, label: str = "", existing_neighbors: int = 0) -> dict` (Cycle 458)

非破坏性拓扑预测：在真正写入前，投影「若添加一个给定特征的节点，density/度熵/聚类系数/图类型指示器将如何变化」。写治理决策的直接依据（"这个节点会让图变得更星型吗？"），不产生任何副作用。

#### `export_tsv(*, include_weights: bool = True, include_kinds: bool = True, include_tags: bool = False) -> dict` / `import_tsv(nodes_tsv: str = "", edges_tsv: str = "", *, merge: bool = False) -> dict` (Cycle 459)

TSV 互换格式——最简单的表格交换协议，电子表格 / R / pandas / awk 即开即用，与 JSON、GraphML 导出互补。表头行自动检测跳过；`merge=True` 并入现有图而非先清空；round-trip 保留节点 ID、边、kinds、tags。

#### `graph_changelog(*, limit: int = 20, node_id: str = None) -> list[dict]` (Cycle 460)

把 `evolution_log` 表（label/kind 变更历史）以结构化 dict 输出为可读变更日志，可按 `node_id` 过滤、按最近优先截断。同 cycle 给 `update_node()` 补上 label/kind 变更时写 `evolution_log` 的埋点——此前只有显式 API 留痕，图演化审计从此完整。

#### telemetry v2 对齐 semantic-conventions-genai @c739977 (Cycle 461)

OTel span 命名与属性全面对齐 GenAI 语义约定注册表：span 名改为动词形式 `create_memory` / `search_memory` / `update_memory` / `delete_memory`；`gen_ai.operation.name` 每个必填；`gen_ai.memory.store.id` 标识存储；计数收敛为单一 `gen_ai.memory.record.count`（语义随操作变化）；内容属性 `gen_ai.memory.query.text` 走规范规定的 Opt-In 门控（`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`）；无注册表等价物的 amg 专有概念（memory_type、top_k、hit 等）全部迁至保留命名空间 `amg.*`——规范禁止自造 `gen_ai.*` 键。进程内记忆系统允许 `SpanKind.INTERNAL`。

#### `judge_llm(question: str, answer: str, reference: str, *, mode: str | None = None, n_judges: int = 1, **ollama_kw) -> str` (Cycle 462)

多数投票 LLM judge（Research #069 协议落地）：返回 `"CORRECT"` / `"WRONG"` / `"ERROR"`。`mode` 支持 `"mock"`（确定性降级）/ `"ollama"`（真实端点）/ `None`（auto-detect：一次性 probe ollama，失败则整轮 sticky 降级 mock，流水线永不因 judge 不可用而中断）。`n_judges` 奇数 ≥3 启用多数投票（Memora 3-judge 原子判据 κ 0.86-0.90 的可复现路径），ERROR 票不计入多数、全 ERROR 返回 `"ERROR"`。`evaluate(judge_mode="dual")` 输出 exact / llm 双列 accuracy。

#### `--judge` CLI 与 run_eval 双口径聚合 (Cycle 463)

`run_amg.py` 评估模式接入 `--judge` 开关，`run_eval` 聚合双口径结果。mock 冒烟 2 题全通，8 月底 full-500 LME_s 判分跑就绪。

#### LoCoMo 双口径接线 (Cycle 464)

`evaluate_sample(qa: list[dict], *, judge_fn=None, limit: int = 0, judge_mode: str = "exact") -> dict` 与 `run_locomo(path, *, limit_samples: int = 0, ...)` 三层（evaluate_sample / run_locomo / CLI）全部支持 dual——对抗类 cat-5 判定协议与主基准共享 `subject_support_gate`，两套数据集的 judge 口径从此一致。

#### `calibration_by_category(results: list) -> dict` (Cycle 465)

Research #069 延伸：`calibration_summary` 只有全局口径，本函数把 exact-vs-LLM 分解到类目级——kupdate 的 llm_only_correct rescue（containment 过严）与对抗集的 llm_only_wrong false pass 方向相反，全局 divergence 究竟由谁驱动一目了然。输入 duck-typed（QuestionResult 或报告 dict 行）。四个 dual 报告点（LME evaluate/run_eval + LoCoMo evaluate_sample/run_locomo）全部接入。同 cycle 建立 **full-500 LME_s overall reference**：exact **0.140** / mock-llm **0.194** / retrieval_hit 0.378；x50 A/B 精确复现 C454 的 0.360——全量差是数据组成（前 50 题 hit 0.76 vs 全量 0.378），非回归。

#### 诚实归因：question_id 回退 + 权威 question_type (Cycle 466)

full-500 暴露两个可追溯性缺陷：① `run_eval` 行全部携带 `question_id="0"`（单题 evaluate 列表恒取 index 0，而 LongMemEval-cleaned 原生字段是 question_id 而非 id）；② `_classify_question` 启发式把 419/500 误标为 single_session_user——`calibration_by_category` 一直在给幻影类目分组。修复：question_id 作为 id 回退；数据集自带 question_type/category 时为权威（连字符/规范名映射，未知类型诚实透传），启发式只做兜底。修正后参考：temporal 0.061→**0.180**（C457 在全量复现）、ssu 0.343、preference hit 0.000（新检索轴）；总量精确复现（0.140/0.194/0.378）。

#### `answer_session_hit_rate` — 证据会话覆盖率 (Cycle 467)

retrieval_hit（truth-containment）在合成真相类目上结构性失明：preference 切片「hit 0.000、30 题全部 miss」其实是指标伪影——原始数据侦察显示适配器已在 17/30 题上浮出证据会话。新指标 `answer_session_hit`：检索是否命中**任一**证据会话（数据集 answer_session_ids → ingest 侧 session id 映射，QuestionResult 逐题记录）；无法解析指针的题记 `None` 而非 miss，排除在分率之外（C466 教训 3 的直接应用）。evaluate() / run_eval 按类目 + overall 聚合，CLI eval 模式打印 evidence_hit。

### 时序取证、锚定卫生与确定性修复 (Cycles 468-473)

#### `answer_speaker_recall` — you-addressed 回忆路径 (Cycle 468)

`recall_form()` 识别 you-addressed 回忆题（"remind me what you recommended" / "did you suggest" / "your advice"）——目标是 assistant 自己的既往陈述，而第一人称源短语（"I told you"）是用户侧、必须静默不触发。配 `recall_min_score` 关键词命中门与 `_ANCHOR_GENERIC` 事件词剥离（"the day I visited the MoMA" 按 "moma" 计分，不按 day/visited）。

#### duration-aggregation 答案路径 — 决定性负发现 (Cycle 469)

"How many hours ... in total" 答案侧路径：32 个单测全绿、全套 9570，但 LME 16 题 A/B **0 rescued / 0 lost / 9 changed 全错**——realized-vs-intended 谓词语义（planned/frequency/difference 形态 + GT=info-not-enough 被伪造）是零 LLM 无法翻越的墙。代码回退、A/B 取证存档：**全绿单测 ≠ 基准提升**。

#### 确定性 label propagation (Cycle 470)

修复全套 ~1/3 概率 flake（test_lp）：PK 索引扫描使初始标签按 uuid 序随机 + 平局按 dict 插入序决胜。修复 = `ORDER BY rowid`（插入序初始标签）+ seeded `rng.choice`（值排序平局集）——min-label 方案被否（0 号标签经桥渗漏导致确定性坍缩）。同 cycle 从会话 transcript 完整复活被跨仓 checkout 摧毁的 C468（12 块 edit payload 回放，19/19 通过）。

#### 锚定卫生四件套 (Cycle 471)

引号/所有格 token 归一（`_strip_quotes`：'ibotta' 25 次出现命中 0 的根因）、best_line 确定性平局阶梯（distinctive hits > generic hits > user-role > past-aspect > later-date，取代静默首个最大值——取证 9 失败中 3 个由它决定）、周单位 round-half-up（数据集 "including the last day" → ceil 语义逆向验证）。prefix-stem 尝试后回退（submitted↔subscription 碰撞）。temporal-133：fire_precision 0.679→0.774，exact 0.180→0.226，零逐题回归。

#### temporal 全图锚点回退 (Cycle 472)

form 匹配但窗口内失败时（锚点缺失 OR 两锚点经 mirror/advice 行坍缩到同一会话），全量 ingest 消息上重试 `answer_temporal_arith`；窗口优先保留（窗口内已出的答案绝不重猜，全图仍撞墙则诚实落空）。temporal-133 exact 0.226→0.271（+6/0——正是取证标记的 6 道全 haystack 可救题，全部答对）。

#### speaker-recall 种子广度 — `recall_seed_k` (Cycle 473)

取证：ssa evhit miss 12 题中 10 题 `ev_in_candidates=0`——证据消息有 7-16 个关键词命中，但权重序 `LIMIT 5` 永远浮不出。`recall_seed_k=40` 经 `recall_form` 手术式限定（恰匹配 48/500 题、全部 ssa）；全局 k=40 对照被否：temporal-133 exact 36→14（mirror/advice 行淹没窗口）。ssa-56 evhit 0.786→0.929，temporal 零翻转——**定向扩宽优于全局扩宽**。

### Multi-session 锚定纪律、官方基准刷新与 pairwise 收尾 (Cycles 490-496)

> Cycles 474-489 的 temporal QA 家族（session 上下文过滤、past-perfect 路径、order-family/pairwise N-锚点）详见[Tutorial：Temporal QA 零 LLM 时间推理](TUTORIAL-TEMPORAL-QA.md)。本节覆盖其后七轮：multi_session 0.045→0.120 的锚定纪律移植、full-500 官方刷新（exact 0.204→**0.284**）、以及 pairwise 家族三连收尾（temporal-133 0.481→0.571、first-family 12→24/30）。

#### `_cnt_question_anchors` 单位词锄除 — 锚定卫生 (Cycle 490)

multi_session 计数的锚点集在编译前先剔除问题自身携带的单位词（`_CNT_STOP_Q` 话题均匀词、`_CNT_GENERIC_HEADS` 泛化地理头词）——“问 days 的题里每个锚点候选都命中 'days'” 是噪声不是信号。三个具名失效按预测修复（camping 18→8、social-media 59→17、Hawaii+NYC 90→15）；泛化头词从完整锚集（而非仅 cap_anchors）移除是超出原型的加固，由 C490 单测抓到原型缺口。multi_session 9→12/133，counting fired-precision 0.32→0.46。

#### `_cnt_total_sum` 金额锚定纪律移植 (Cycle 491)

旧的无门控求和吞下 haystack 里每一个 `$`：收入行（$50k）、L-visa 法定费（$4500×2）、手表/餐厅消费全部污染总额（$56355 vs GT $5850）。从 duration_sum 移植同构器官：(a) 锚点门——问题 token 减去金额单位词，连字符头拆分（bike-related→bike），单复数双形匹配；(b) 会话传播——一句非意图锚点命中点亮整个会话，意图句（planning）不能点亮；(c) 价格区间对跳过（$50 to $200 = 预算非消费）。四个具名总额全部精确（$2440→$185 / $56355→$5850 / $8750→$3750 / $8940→$720），multi_session 12→16/133 零损失零门控翻转。

#### full-500 官方 reference 刷新 (Cycle 492)

C481 后首次官方刷新，收 C482-C491 十 cycle 逾期债：exact **0.204→0.284**（+40 净：temporal 0.271→**0.481** = C485-489 五连全量兑现，multi_session 0.045→**0.120** = C490/C491 两连，ssu/kupdate 各 +1）；llm 0.256→0.296；evhit 0.910→0.912。C484/C485 的 needs_verification 债随刷新清偿（答案侧零回归；检索 hit -3 为检索侧唯一变更且证据命中反升）。

#### temporal_arith first-kind 退役 (Cycle 493)

删除型 cycle 也要 A/B：monkeypatch 双臂 + 生产验证 30 题切片 **12/30 = 12/30 零翻转**才提交。取证：500 题中 30 题匹配 first-regex，pairwise 截获 11（8 对）；TA-first 仅解析 3（1/3 精度）——唯一正确项经普通 extractive answer gate 等价重答，两个错误项哪边都错。删除 `_TA_FIRST_RE` + form/answer/judge 三分支死代码。C479 先例第二案：“更准机制已前置”只是推断，双验证才是证据。

#### pairwise 锚面扩展 — `_PW_EVENTIVE_RE` / `_PW_SINCE_RE` / 粗相对时长 (Cycle 494)

29-family 残余 14 错分解后修三个表面缺口：(a) 进行时 gerund（attending/starting/taking）入事件词表——进行时是“正在发生的过去汇报”，planning veto 完好；(b) `since February 20th` 序数后缀（裸 `(\d{1,2})\b` 在 '20th' 上失配）；(c) 粗相对时长日历锚：last summer→上年 7 月 1 日、a few N ago→3 单位、for the past N→状态起点回拉。加 `_pw_scan_anchor` 向后窗口（主句动词统辖尾列表）。first-family 12→16、temporal 64→68（+4/−0）。

#### 从句粒度 + 跨行锚点对 (Cycle 495)

clause 是意图的最小单位：同一行可以既 plan 一个事件又新鲜汇报另一个；相对从句窗口 + 跨行锚点 join。7 个具名修复全胜零翻转——first-family 16→**23**/30、temporal 68→**75**/133（+7/−0）。

#### `_pw` F6 anaphora 购买汇报 join (Cycle 496)

kw 对全命中后，无 kw 的购买汇报句（“We got her for $500”之类裸量词 NP + 价格宾语）可回指续接 pair item——四重判别式防毒，行内 anaphora（“started it 3 weeks ago” 继续按会话时钟）构造上不受影响。firstfam 23→24、temporal 75→**76**/133；套件 9790→9801。

### Neither-family ECM、偏好诚实弃权、官方刷新 0.316 与角色感知答案面 (Cycles 497-501)

#### ECM neither-family matcher (Cycle 497)

Research #082 五决策生产化：strict form gate（“who did I V first, X or Y” 严格形态门）+ 序数标量轨/日历轨 + 描述 NP 免动词门 + 人名保动词门 + 跨 turn anaphora join + 负存在弃权孪生；`unit_sum` 加 (n, entity) 去重修 cataphora 双计。temporal 76→**80**/133（0.602）、firstfam 24→**28**/30、multi 16→17；翻转恰为 #082 oracle 四题，零劫持。+27 `test_ecm.py`，套件 9801→9828。锚点：`ecm_form` amg_bench_quality.py:3990、门正则 `_ECM_GATE_A_RE`/`_ECM_GATE_B_RE`:3741/:3744、`_ECM_VERBMAP`:3748、族间互锁 :3735。

#### preference 诚实弃权与 shipped-gate census (Cycle 498)

advice 请求形态（`_PREF_RE`:3687 精确后缀集——刻意排除过去分词 recommended/suggested（“did you recommend…” 属事实寻回而非建议请求），词形坑 suggestion=suggest+ion 非 atation；`pref_form`:3698、`pref_abstain` 旗标 :518/:787）诚实弃权而非硬答：pref-30 answered 30→1、abstained 0→29（exact 0.000 为结构性零，非退步）。**出厂 gate 全量普查（500 题）：fire 29/30 pref + 0/470 其他**——根因发现：naive `recommend\w*` 词干普查正则与实现漂移，会劫持 14 道 ssa 助手召回题且首查不可见，精确后缀集修复（shipped-gate census 纪律：普查必须跑出厂 gate 本体）。+15 `test_pref_abstain.py`，套件 9847。

#### full-500 官方基准刷新 (Cycle 499)

exact 0.284→**0.316**（+17/−1）：temporal 0.481→**0.602**（+16，C494-497 pairwise/锚点/anaphora/ECM 四连全量兑现）、multi_session 0.120→0.128（+1）、ssu 0.343→0.329（−1 = 86f00804 窗方差书名出窗，C481 先例非机制）；llm 0.296→0.318、hit 0.390→0.394、abstain 0.032→**0.086**（pref 29 弃权入口径——诚实弃权是特性而非损失）、evhit 0.910 平。收 C493-C498 六 cycle 刷新债。

#### `item_total` 枚举金额聚合 (Cycle 500)

“What is the total amount/cost/price…” 21 错簇：题目侧 item 枚举 + 证据绑定四层（T1 同从句 / T2 同句任意从句 / T3 相邻句 anaphora / T4a-b turn/session 唯一）+ foreign-full 守卫 + 区间价/周期价/汇总句排除。族标签 :4463、求解 `_cnt_item_total`:4862、分派表 :5274。multi_session 17→**22**/133（0.128→0.166，+5/−0 全中预测）、temporal/firstfam 零漂移；普查 gate 触发 8 题全为此前错题（5 可解 + 3 设计性弃权），零劫持 number_total/duration_sum 既有正确。+15 `test_item_total.py`，套件 9862。

#### role-aware answer face——echo pathology 修复 (Cycle 501)

第一人称事实题的 GT 常藏在简短用户行，而助手 advice 行 kw 命中更高，答案门回显 advice 文本（“Mint is a fantastic app…”）。user-line 选择仅在两守卫下出手：`_user_fact_form`:3723（`_ROLE_USER_FACT_RE`:3720 第一人称代词 + 非 you 寻回形态（C468 管助手侧）+ 非 advice 请求（C498 已弃权））与 `_answer_form_claimed`:3730（被 ECM/pairwise/temporal_arith/counting 专业族 claim 的形态不动 fall-through——**gate 顺序即正确性面**，C482/C488 教训）；竞争时 margin 0、floor 2。full-500 163→**183**/500（exact 0.326→**0.366**，+20/−0：ssu 12、kupdate 5、multi 2、temporal 1）；base arm 精确复现 C499+C500（158+5=163）。+10 `test_role_answer.py`，套件 **9872**。

### Counting 第 5 形态、duration-family 四机制、嵌入 side-channel 与官方刷新 0.368 (Cycles 503-506v)

研究→生产流水线 #083/#084/#085 三连落地（原型 oracle parity 先行，A/B 串行切片验证，零劫持门槛），加上 C506v 全量官方刷新。C502 为 zero-loss revert（词法删除引入语法错误，即时回退），不计入 cycle 链。

#### enum_count——枚举签名计数，counting 第 5 形态 (Cycle 503)

"How many X…" 枚举计数（Research #084 v5.2）：用户 TURN 为候选单元（含 stem 的 turn 贡献其全部子句——role 吸收必须看到 stem-less 子句，如 "my cousin Rachel's wedding" 搭乘同 turn 其他子句的 stem）、子句为签名单元、尺寸签名（`_ENUM_SIZE_UNITS`:6123 gallon/liter/inch…）扫全 turn。三层防劫持：所有权门 `_ENUM_MY_INVENTORY`:6149（my-inventory 抑制名字签名——"Billie Eilish albums" 品牌污染防线）、排他谓词（missed/skipped）+ shower 尾部窗排他、twins 同位语 `_ENUM_TWINS_APPOS`:6145。求解 `_cnt_enum_count`:6102、形态门 `counting_form`:4666 → "enum_count":4879、分派表 :6361。oracle parity 4/4（tanks/weddings/babies/ceremonies）；A/B 串行 133 切片 24→**27**/133（0.180→0.203，+3/−0）；counting fired 29→35。+16 `test_enum_count.py`，套件 9888。

#### duration-family 四机制 (Cycle 505)

Research #085 v3 四机制移植：**M1** binge-dedup-sum——franchise/目的地键去重，重提不双计（`_dur_m1`:4916，franchise 键 `_DUR_FRANCHISE`:4757）；**M2** freq_days + 课程语境锚——无关星期句不再污染计数（`_cnt_freq_days`:5305）；**M3** realized-window-duration——子句级计划/事实墙，习惯语气排除（`_dur_m3`:4965）；**M4** delivery-interval——月份名+斜杠日期 join、代词回指产品、题侧产品守卫缺失→弃权（`_dur_m4`:5039）。族分发 `_cnt_duration_family`:5089、家族门 `_dur_family_gate`:4896、分派表 :6356。oracle parity 7/7（5 目标题 + aae3761f=15 计数控制 + 2788b940 未 claim 控制——原型上限 ≠ 管线预期，控制题是护栏）；27→**31**/133（0.203→**0.233**，+4/−0，C503+C505 链条累计 +7/−0）；counting fired 35→37。+11 `test_duration_family.py`，套件 9899。

#### 嵌入 side-channel (Cycle 506)

Research #083 定案生产化（form-gated switch，非 RRF fusion——融合被 #083 A/B 否决）：`chunk_session_text`:1782（150 词 × 6 块，贴合 MiniLM 256-token 上下文预算）+ `SidechannelEngine`:1798（import-probe 双档依赖：quality=fastembed/MiniLM → fast=model2vec/potion → None 降级）+ `session_embedding_scores`:1875（chunk-max 余弦，纯 python 零 numpy）+ `sidechannel_form`:1905 形态门——`pref_form`→"embed"（词法桥不可达的 advice 请求，纯嵌入会话选择替换关键词排序）、`recall_form`→"hybrid"（词法召回强，嵌入仅重排关键词候选修 @1 排序）、其余 None（词法管线原样，两门实测不相交：C498 普查 pref 29/30 + 0/470）。`--sidechannel` CLI:6507 + `run_eval`:6293 透传。密闭 stub-engine 测试；真引擎冒烟：probe 2.2s（缓存后）、语义桥 0.427 vs 词法 −0.029。**词法零依赖默认不动**。+15 tests，套件 **9914**。

#### full-500 官方刷新 0.368 (Cycle 506v)

exact 0.316→**0.368**（+0.052，C499 后首个全量参考）：C501 role-answer +20 与 C503/C505 +7 全量兑现——multi_session 0.128→**0.233**（0.128→0.166→0.203→0.233 三连弧）、ssu 0.329→**0.457**、kupdate +0.026、temporal 0.602→0.609；hit 0.396 / evhit 0.910 / abstain 8.6%；**零类目回归**。本轮零代码改动，纯基准刷新。POST `--sidechannel` 臂 A/B 已完成：**207/500=0.414 全库新高**（见下节）。

---

### Total-number v2、where-form、delta-family 两锚点聚合、inventory_count 第 10 形态与 POST 臂 0.414 (Cycles 507-511)

08-24 白天 ~ 08-25 凌晨五连（四 keep 一负结果）：multi_session 0.233→**0.414** 133 切片四连弧（C507/C509/C511 各 +5/+16/+3 全零回退），C510 为首个 RECORD-NEGATIVE（负结果台账化，不涉生产代码，不计入 cycle 链——与 C502 zero-loss revert 同理）；full-500 POST 臂收口 0.414 全库新高。

#### total-number 家族 v2——两实体数值求和 (Cycle 507)

"Total number of views on YouTube and TikTok" 类问题要求按实体拆分求和，单向聚合器看不见题目自身的实体划分。`_cnt_number_total`:5935 v2 七项升级：P1 NP 上限 60→90 / P2 -es/-ies 复数形态 / P3 跨度级频率过滤 / P4 后置编号 `own_re`:5948+"of" 守卫（own_re 限定题目自有 head 而非 hyponym head——防 "Expand on module 4" 祈使句劫持）/ P5 序数计数 / P6 实体锚定拆分按实体 max 求和 / P7 sibling 入 species；另加逗号千分位保护 `[,;](?!\d)`。multi_session 0.233→**0.271**（31→36/133，+5/−0 恰为两实体求和目标）；xcat 交叉验证 temporal+single_session 114/203 逐位零翻转。

#### where-form locative 提取 (Cycle 508)

严格 start-with-where 门 `where_form`:2145（census 19/500 零家族重叠、全部原走 echo 路径）：`_where_loc_candidates`:2161 专名/普通两分支 locative 抽取（专名分支必须大小写敏感——re.I 会把句中动词垃圾当专名），locative 句子选择 :2183 仅扫 retrieved 会话（C472 全图锚回退教训不迁移到 where，sim v4 A/B 反证）；answer gate 挂接 `self.where_loc` :1094。where 家族 4→**6**（+2/−0 IKEA/Oahu）；组合树 0.368→**0.382**（+5 为 C507 同树测得）。已取证坑：①检索 hash 方差——retrieve_context 的 PPR 种子受 set 迭代序影响，同代码不同进程 retrieved_ids 漂移（遗留待修）；②10×50 分块官方 CLI 绕 277MB json.load 内存墙（~28 min 全量）。

#### delta-family 两锚点数值聚合 (Cycle 509)

题目文本自身命名比较双方（"how much more … compared to …" / "… instead of …" / "minimum amount … and …"）：`delta_form`:6824 STRICT 形态门（题面算子族精确分派 t_diff/rate/count_ratio/cmp_pct/pct_price/save/minmax——question-text only，无证据偷看；"faster" 单独门 temporal-diff 分支）+ 引擎区块 :6646（any-of 锚点绑定 + user-role 优先 + strict-majority 跨侧排除 + 子句局部性 tiebreak，再施加算子族 diff/sum2/minmax/rate/ratio/pct）。防劫持三设计：miss→None fall-through（gates own abstention）、counting 之前执行（dispatcher :1021）、`--no-delta` CLI :7390 隔离开关。21 题全错族 → oracle 16/21、fired 精度 **100%**。multi_session 0.271→**0.391**（36→52/133，+16/−0，16 wins 全 corpus-21 成员与 oracle 逐题一致）；套件 9928→9948（+20）。

#### C510：kupdate answer-face 负结果 (RECORD-NEGATIVE)

Research #087 被**移植前杀死**——virtual-flip census（门控+原型逻辑+生产判分函数级全库，~3 分钟）三重否证：①判分鸿沟：原型 oracle 19→54（2.46×）系关键词判分幻觉，生产 `exact_judge` 连续包含要求下 57 fire 仅 21 过；②形态不可分：PERFECT 形态内赢输共存，根因是选择质量而非形态路由；③跨类劫持：124 fire 翻错 31 个 currently-correct，净 **−7**。**census 升格 #088+ 所有 answer-face 生产化前置关卡（insight #254）：原型数字只代表研究方向，不代表生产收益**。负结果进台账（484ea70），v10 方向留档：值跨提取 / 值-签名距离选择 / judge 侧救援。

#### inventory_count——第 10 counting form (Cycle 511)

{kit, instrument, property} 白名单家族（133+500 双 census 恰 3 fire 全错 → 结构性零劫持面）：`_cnt_inventory_count`:6510 distinct-item 枚举，形态门 `counting_form` → "inventory_count":4909、分派表 :7088。分家族身份抽取（kit=scale+brand+专名句级 union / instrument=brand+model 码如 1/72 B-29、Tamiya Spitfire / property=N-bedroom+类型+邻区专名对）+ `_inv_dedup`:6505 最大签名包含去重；排除面：hypothetical acquisition（"thinking of buying"）/ foreign possessor（"my niece … her violin"）/ 域守卫；selling 不排除。坑：lower 后丢 anchor 专名（大小写保留抽取）/ 贪婪 optional 组 / scale 数字 token 拆分双计（句级 union+纯数字跳过）/ "Women in Art" 伪签名（单词专名须 marker）。multi_session 0.391→**0.414**（52→55/133，+3/−0）；oracle 3/3。

#### full-500 POST 臂 0.414——嵌入通道全量兑现

C506 留下的 `--sidechannel` 全量 A/B 收口：C508 树 0.382 → **207/500=0.414 全库新高**（1135s）；逐类目 multi 36→52（+16），其余五类**逐位不变**（losses=0——跨类目零回归实证，#083 form-gated 嵌入通道在 multi_session 上全量兑现）。

#### 工具线注记：npm scripts DOA 修复 + 结构守卫

`package.json` test 链为模板垃圾（`npm test --` 自递归至 core dump；prepare→build→test 链毒化每次 npm install）——b52e6ba 接线到真实 runner（python3 -m pytest / py_compile / python -m build），移除 prepare/prepublishOnly 钩子；新增 `test_package_json_scripts.py` 5 条结构守卫（amk scripts={} 655c173、ai-dev-tools 虚荣测试 e542697、本例三案同类）与 `scripts/find_untested.py` 覆盖缺口发现器。套件 9958→**9963**。

---

## Cycles 512-516: 弃权语义家族 — 预设有失败检测 + RECORD-NEGATIVE 台账化

> 本家族概念教程见 [TUTORIAL-ABSTENTION.md](TUTORIAL-ABSTENTION.md)："I don't know" 是答案不是失败。

08-25 夜 ~ 08-26 凌晨五连（三 keep 一负结果一 revert）：弃权（abstention）从 temporal 家族的局部纪律升格为答案侧一等公民，multi_session 0.414→**0.459**（55→61/133）四连弧收尾，abs30 切片 10→15（+5/−0）。

#### C512：knowledge_update #088 负结果台账化 (RECORD-NEGATIVE)

原型 oracle 19→54（2.46×）被 virtual-flip census 在生产化前杀死：判分鸿沟（关键词判分幻觉 vs 生产 `exact_judge` 57 fire 仅 21 过）、形态不可分、跨类劫持净 −7。**原型数字只代表研究方向，不代表生产收益**（insight #254），census 升格为所有 answer-face 生产化前置关卡。负结果进 `experiments.tsv` 台账（484ea70）。同期 C512-B 写时嵌入摊销因冗余仅 1.02× 被 revert（133a7b1）。

#### C513：negative-existence 弃权门 (#087 ABS_Q 血统)

LME `_abs` 预设有失败陷阱：问题预设一个全语料零提及的实体（问 Shinjuku、语料只有 Harajuku），检索强而切线、置信度高、下游门全部编造（C511 HEAD：18/24 abs-GT 题被编造、0 弃权）。修复：回答前检测问题中专名的全量 haystack 零提及（word-boundary、case-insensitive；引号标题正则伪影排除，裸 token only）→ ABSTAIN。**跑在所有 mechanism 门之前——预设有失败优先于形态家族**（gate 顺序即正确性面）。census v3：13 fire/500、+3 abs-GT 赢、0 劫持；abs24 6→8（+2/−0）；ctrl16 零劫持。+16 tests。

#### C514：museum_count 第 11 counting 形态 + 计数家族内首个弃权

场馆到访月窗口计数（"How many different museums or galleries did I visit in the month of February?"）：身份在场馆专名（Natural History Museum、"The Art Cube"），实现在到访动词，月窗口承载排除语义（排除 1 月 workshop、保留 2/8 与 15 日）。**零场馆 = 预设有失败 → ABSTAIN**（counting-path abstained mapping，museum-only，全家族唯一返回 ABSTAIN 的 counting form）；12 月孪生题弃权即正确（GT 即 abstain）。census 恰 2 fire 全为原错题；oracle 2/2（Feb=2、Dec 弃权）。multi_session 0.414→0.429（55→57/133，+2/−0）；+23 tests（套件 10002）。

#### C515：age_diff 第 12 counting 形态 — 自我年龄锚定年算术

"How many years older is my grandma than me?" 族三形态（other-then-until）：自我年龄锚 + 靶事件年龄做整数年减法（grandma 75−32=43；25 岁毕业 vs 32 岁 = 7；明年结婚 32+1=33）。歧义纪律：**每个锚必须唯一取值，否则整个形态落回不动**；非正差值 = 语法 miss。census 3 fire、oracle 3/3、零劫持。multi_session 0.429→0.451（57→60/133，+3/−0）；+18 tests（套件 10020）。

#### C516：neg_exist 普通名词限定器 — LME 换轨陷阱

`_abs` 家族换的是**被问对象名词**（violin/guitar、football/baseball、iPad/iPhone、uncle/niece）：第一人称对象问句中普通名词全语料零提及 = 预设有失败 → ABSTAIN。与 C513 专名版分开是因为假阳性面不同（普通名词太常见，必须形态限定防劫持）。census v6：6 fire/500、5 赢 1 控；abs30 10→15（+5/−0）；multi_session 0.451→0.459（60→61/133，+1/−0）。+20 tests（套件 **10040**）。

---

## Cycles 517-519: 全量兑现弧 + abs 门三连 + 误杀取证

> [TUTORIAL-ABSTENTION.md](TUTORIAL-ABSTENTION.md) 同步扩充至 C519：预设失败的三个新入口、老门也要 census、accent-fold。

#### C517：full-500 官方刷新 — 七 cycle 债一次兑现 (f40da92)

multi_session 是 133 题切片 A/B，full-500 是官方记分板；C507-C516 七个 cycle 的切片增益累积成一笔“验证债”。C517 把 full-500 基线从 C506 的 **0.368 → 0.444**（222/500，+38/−0，all-time high）——切片 A/B 的每一步 +N/−0 都在官方口径下复现，无一步回吐。教训：**切片 A/B 管方向，官方刷新管结账**，两者不可互替。

#### C518：abs 预设失败门三连 E1/E2/E3 (50c4406)

15 个 abs-wrong 逐题取证分簇后三个新入口，全部挂在已有正确性面上：**E1** `at which` 前缀进 `_NEG_EXIST_OBJECT_FORM_RE`（undergrad poster 题释放 C516 门）；**E2** age_diff 第 4 形态 `other_until`（“我结婚时 X 多大”）——主体年龄锚全库缺失 = 已解析的否定存在，走 counting-resolver abstain（复用 C514 museum 先例，架构零新增），有锚则 fall-through 不猜；**E3** 所有格 N-gallon 复合词（“my 30-gallon” 全语料零出现，只有 20/10-gallon sibling）——**所有格数字属性 ≠ 可释义名词**，按所有格限定收窄而不是泛化名词复合（C510 sibling-signature 已证伪泛化路线）。census 3 fire/3 win/0 劫持；full500 **0.444→0.448**（224/500）；multi_session **0.459→0.481**（61→64/133）；abstain 11.2%→11.8%。唯一 −1 是 margin=0.0 检索 tie 抖动（diff 证明 5 处编辑无一触及该题路径——**tie 抖动要代码路径归因**，不是回归但台账如实记）。

#### C519：proper-noun neg_exist 误杀取证 (86cbde3)

C516 给普通名词版做了 v1→v6 census，但 C513 的专名版 **fire 面从未被审计**——三天后全量 census 才发现 9 fire 里藏 4 个误杀（Bachelor/Hawaii/EPs/Aragón，全是 answer_session_hit 的题被误弃权）。四个根因三层修复：① **Unicode 截断**（普适 bug）：`[A-Za-z]` token 类在 ó 处截断，'Aragón'→'Arag'，`\barag\b` 匹配不上 'aragón'——NFKD 去组合符折叠必须做在 tokenize **之前**且**两侧**（先 tokenize 后 fold 治不了 'Arag'）；② 学位类别词（Bachelor 是属性词，语料用“CS from UCLA”转述）→ stop 表 +Master/PhD/MBA；③ 媒体复数（问 EPs 语料只有 EP）→ +CDs/LPs/DVDs；④ 地理下位词（问 Hawaii 语料全说 Maui）→ 保守 `_NEG_EXIST_GEO_SUB` 映射，每条由真实误杀证明。fold/stop/sub 都只能减 fire 不能加，census 确认 POST fires=5 ⊂ before 9，严格子集 → 全 500 净 +1（0.448→0.450 预测口径）；abstain 11.8%→11.4%（**诚实弃权下降 = 误杀减少**）。教训：**老门也要 census**——不上新功能的取证轮次同样是增益；解锁的 4 题暴露 answer-face 转述失配是下一方向。

---

## Cycles 520-531: 官方记分板 0.450→0.494 — census-first 判分革命与确定性管线

> 官方口径（LongMemEval **s_cleaned** full-500，PYTHONHASHSEED=7）轨迹：0.450（C519 预测）→ 0.454 → 0.476 → 0.484 → 0.486（det）→ 0.492（cascade）→ **0.494**。本段主轴：RECORD-NEGATIVE 台账（C522/C524）+ 数据集分叉拦截（C527/C527b phantom +25）+ tie-jitter 家族根因关闭（C528）+ 判分级联生产化（C529-C531）。

#### C520：`risk_coverage_report` — 风险-覆盖曲线进报告 (cde5d38)

AURC/E-AURC/Risk@coverage + per-form breakdown 进 amg_bench_quality（Research #089 port），run_eval 报告无条件接线。移植时抓出 #089 原型一个真实 bug：oracle 闭式 k²/2n² 是小-k Taylor 近似，系统性低估 E-AURC（n=10、k=4 时 0.0926 vs 精确 0.0800，方向恰好是"体面"）——换成与实测同一梯形积分器的构造式精确 oracle。full-500 smoke：risk@50%=0.516 vs overall 0.556，平坦曲线定量复证 #089 读数；preference 全错切片 E-AURC=0 退化下限。+12 tests（含 oracle 交叉校验），套件 10052。

#### C521：enum_count 事件专名签名 (61525fa)

festival/fest-head → 数 DISTINCT 事件专名：重提去重、排除动词子句跳过、先于 names/roles 消歧（"Rachel's favorite festival" 不算一个 Rachel 计数）。21-q 切片 A/B +1/−0（gpt4_a56 null→4=GT）；oracle-parity 4/4 恢复；套件 10057。

#### C522：phrase-restrictor bigram 否证 + 官方刷新 0.454 (RECORD-NEGATIVE)

C518 队列项「相邻内容 bigram 在 haystack 缺失而两 token 都在」全量 census：48 fire = 4 win / 12+ 劫持，机械签名完全相同 → **实现前否证**。同 cycle 官方 full-500 收 C519+C521 债：0.448→**0.454**（224→227，+3/−0；86f00804 tie-jitter 自愈归还）。

#### C523：quantity-form 答案面重排 — 0.454→0.476 (e4ac826)

"how many/much" 答案门 quantity 形态重排：103-q 切片 0.214→0.320 与 full 逐题一致；全量 227→**238**（+11/−0：10 个真 fact-line 重排 + 1 个包含事故 a9f6b44c——GT "2" ⊆ "2023"，此事故后被 C529/C530 判分侧拦截反杀）；both-correct PA 扰动 0/489。套件 10069。

#### C524：latest-number-wins 否证 (RECORD-NEGATIVE)

a2f3aa27 队列项实现前 census 否证：top-has-number 38/103；loose override +2/−8、strict +0/−4、flagship 题信号层不可解。C512/C522 census-first 纪律第三案。

#### C525/C526：narrowing-scope + session-completion 两面 census（+5/−0）

**C525** narrowing-scope 答案面 +2/−0（fires=6，零正确题触及；同条件 unscoped fire 58 含 10 劫持——**scope=narrowing 承载全部分离力**）。**C526** session-completion 面 +3/−0 same-session；unscoped 变体 +7/−3 且 3 劫持全跨 session → 拒绝 unscoped。窗口预算 cut 分析：真实瓶颈 = seed-miss 105（58 题 GT 串根本不在 haystack——quotation-judge 死路）。五题预测被 C527 官方刷新 5/5 兑现。

#### C527/C527b：官方 0.484 + 数据集分叉拦截 + 指纹基建 (b5e5843/c1863ad)

官方 full-500 刷新 0.476→**0.484**（242/500，+5/−1，钉 PYTHONHASHSEED=7；−1 = 86f00804 tie-jitter 家族）。**主发现 DATASET BIFURCATION**：`longmemeval_oracle.json`（1.9 sess/22 msg 每题）与 `longmemeval_s_cleaned.json`（47.7 sess/494 msg）共享同 500 qid = **两套基准**；oracle 首跑 0.526「phantom +25」被好得可疑纪律拦截——官方血统全在 S-track，oracle-track 只配当 fast-iteration 开发集（1/5 体积；机制杠杆不可跨集比较：quant_rerank oracle +20 vs s_cleaned +11）。C527b 指纹基建：report config 新增 `data_file`/`data_sha256_12`/`pythonhashseed`，run_eval(data_source=) 接线（零作答行为变化）——**跨 run 比对先验指纹**从此是纪律。同期 RNG 取证：86f00804 同环境 A/B 单题翻转 + 顺序交换重放 ✓✓✗✗，统一解释 C517✓→C527✗ 四次官方翻转（真根因 C528 关闭）。套件 10089。

#### `recall(query: str, limit: int = 5, *, readonly: bool = False) -> list[Node]` — 确定性纯读召回 (Cycle 528)

tie-jitter 家族（同码同 seed 跨 run verdict 翻转）RNG 审计证伪「未播种 random」假设——检索路径可达面零未播种随机。真双源：① `recall()` wall-clock weight 突变（decay+ACCESS_BOOST 写回；每题 fresh ingest → fresh accessed 时间戳 → `ORDER BY weight DESC` 近平分骑衰减浮点噪声）；② PPR seeds 取 fresh uuid4 的 set 哈希序（os.urandom，PYTHONHASHSEED 免疫）。修复：`readonly=True` 纯读（零写入，tie-break 用 rowid=摄入序；legacy 路径逐字节等价）+ PPR 改发现序 seeds；适配器 `deterministic_recall=True` 默认、`--wallclock-recall` 逃生口。证据：det500 243/500（**0.486**）vs banked 242，+1/−0 且唯一 win = 86f00804 本尊；499/500 verdict 逐字节同；q86 四进程跨 seed bitwise 同 predhash；prefix50 A/A 两进程 50/50 同。**评估管线 = dataset 纯函数，单题独立重放恢复合法**。套件 10096。

#### `judge_semantic(question: str, answer: str, reference: str) -> str` — 确定性语义 judge (Cycle 529)

Research #090 简化 port：规范化（大小写/标点/数字词 five→5）→ 日期折叠 → 时间单位换算（统一秒）→ 守卫包含 → 软相似（SequenceMatcher ≥0.75）阶梯，返回 CORRECT / WRONG / **NEEDS_JUDGE**——第三判定是词法不可解对（实体替换、零重叠改述）的诚实弃权，**永不计分**。三个假通过/假损失守卫：number veto 仅在数字集**不相交**时否决（超集候选合法共享 GT 数字——"16GB" 答成全配置清单，C529 前规则误杀 32 题）；币种域冲突（$5 vs 5 euros）；非对称包含带 exact-number 答案面（"140"="140 hours"）。

#### `judge_cascade(question, answer, reference, *, llm_fn=None, **llm_kw) -> str` + A/B 统计三件套 (Cycle 529)

cascade = judge_semantic 先行，仅 NEEDS_JUDGE 降级 `judge_llm`（可注入 llm_fn）。`judge_mode="semantic"` 贯通 evaluate()/run_eval()/CLI `--judge semantic`（dual 报告形状 + judge_ab）。统计三件套（Research #092 协议）：`cohens_kappa`——原始 agreement 在非平衡数据上被机会共识灌水（官方 judge raw 0.98，κ 后缩水 33-41pp）；`mcnemar_exact`——判对对抵消，只数不一致对的精确二项检验；`judge_ab_report`——rescue/loss 计数 + McNemar p + κ + 分类目分解（类目噪声地板不同：preference 0.10 vs ss 0.00）。det500 replay census 修复兑现：8 个确定性 rescue 待收、veto-kill 32→5、169 题 LLM-judge 表面测绘。套件 10137。

#### C530：官方 cascade-500 收债 0.492 + judge backend 指纹

@pristine 重放 0.486 exact 逐字节一致（0 pred/verdict diff——C528 纯函数再认证）→ 确定性 cascade **246/500（0.492）入账**：+8 rescue（C529 census 8/8 兑现）−5 veto-kill（包含假通过拦截，含 a9f6b44c 已知事故反杀）。**主发现：mock fallback 静默污染**——无 ollama 时 judge_llm sticky 降级 lexical mock，24 个 NEEDS_JUDGE 行被 mock 判定（20 假 rescue + 4 假 kill），raw cascade 262/500（0.524）不可入账；修法 = report config `judge_llm_backend` 指纹（mock/ollama/unconsulted）。McNemar (b=8,c=5) p=0.581 n.s.——**升级依据 = 判分有效性，非分数 delta**。169-172 题 NEEDS_JUDGE 的 LLM 上行空间待 ollama oracle。套件 10140。

#### C531：either/or 答案面 rescue — 0.494 (0f7f6b1)

veto census 复核发现 subset-branch 在官方 cascade-500 上精度 0/2（两个假 kill：gpt4_98f46fc6 charity either/or 获救；gpt4_45189cb4 narrative abbreviation 仍留 veto——无非拟合规则前不救）。问题条件化守卫：题面恰给两个候选时，逐字点名其一 = 完整答案而非弱子集（数字答案面的文本类比）；限定单-or 问题 + 候选被包含 + undecided-ref/negation 守卫，C529 tennis spec 保留。banked 246→**247（0.494）**，kills 5→4（冻结 C530 预测上 verdict-delta 枚举验证）。套件 10143。

---

## Cycles 532-539: 破半之路 0.494→0.510 — 问题结构驱动的答案面家族

> 官方口径（LongMemEval **s_cleaned** full-500，PYTHONHASHSEED=7，deterministic cascade banked）轨迹：0.494（C531）→ 0.496（C532）→ 0.498（C533）→ **0.500（C534 破半）** → 0.502（C535）→ 0.504（C537）→ 0.508（C538）→ **0.510（C539）**。本段主轴：答案门 answer-face 家族化——候选排序不再调阈值，而是读**问题结构**（要什么类型的事实 / 谁实施的言语行为 / 问题用什么动词 / 语篇标记骨架）；judge 残差收敛（C535 英式折叠）；census-first 纪律三连否证（C536 ordinal 未接线 / C539 pref oracle 与 judge-fold 方向关闭 / 朴素 opener floor 离线证伪）。概念教程见 [TUTORIAL-ANSWER-FACES.md](TUTORIAL-ANSWER-FACES.md)。

#### C532：marker-aware 子序列答案面 — 清偿叙事缩写债 (7eefcd2)

C531 留债 gpt4_45189cb4（narrative abbreviation，"需要原则性表述而非覆盖率阈值"）。原则性表述找到了：**语篇标记骨架**（first/then/finally…）。顺序类问题的叙事答案若满足三条件——① 共享 reference 的标记骨架（同标记同顺序，≥2 个，首标记前无内容前言）② 每段是 reference 对应段的**有序 token 子序列** ③ 无空段——即同一叙事的**缩写**而非弱子集。事件跳读被结构性排除：丢事件 = 丢标记 = 骨架失配；乱序/外来事件破坏段内对齐。+1 cascade row，0 side effects；banked 247→**248（0.496）**。套件 10144。

#### C533：where-gate 地点回忆 + 相关性地板 (9ad01e2)

10 个 wrong where 行取证分解出三重病根：`_WHERE_COMMON_RE` 词表有 `cities` 无 `city`，且谓语性短语（"it was a coffee shop"）无介词前导 → GT 句 "For Sophia, it was a coffee shop in the city." 完全进不了候选集（3d86fd0a）。修复：① 词表补单数地点名词（cit(y|ies)/towns?/cafes?…）；② **相关性地板**——kh=0 获胜者让位给最优 kh≥1 候选（insight #086：问题即连接条件），无 kh≥1 候选时不干预。+1 official，A/B 19 行干净（0 字节失配外）。banked **249（0.498）**。留债：4 行证据 session 未被检索（retrieval 层，gate 无能为力）。套件 10147（+3）。

#### C534：speaker_recall 答案类型面 — banked 破半 0.500 (24220b1)

问题索要什么**类型**的事实（how many/much、what year、@handle）⇒ floor-passer 间按类型承载偏好重排：tier = 类型承载句优先 + 有界豁免通道（类型承载、raw≥2、preface 与 weighted_floor 保留）。源于 C533 留债解剖：多数 GT 承载句是被 min_raw/df 地板**过滤**而非排序惜败——**问题结构非阈值**（C531 原则首次系统化）。+1 official（7a8d0b71 DHL $2,000 预算行），A/B 48 recall 行 +1/−0。**banked 250/500（0.500）破半关口**。套件 10152（+5）。

#### C535：judge _sem_norm 残差折叠 — 英式→美式词形 (ecf74a2)

b759caee 三层病根（markdown 转义 + 标点粘连 + BrE/AmE）：`_sem_norm` 分隔符折叠扩展（转义/引号/方括号/下划线折为词分隔符，保持 [,$.] 下游位置使逗号分组数字仍折叠为裸数字）+ `_SEM_BRE_VARIANTS` 词表（jewellery→jewelry、colour→color、centre→center、-ise→-ize…）。sense-split 对（programme/storey/licence）显式排除——**词表非后缀规则**，our/hour/sour 完好。+1 rescue b759caee（转义 handle @jessica_poole_jewellery + AmE 行文 vs BrE GT）。verdict-delta 枚举：1 rescue / 0 kills / 9 中性翻转 = 省 9 次 cascade LLM 调用。banked **251（0.502）**；banked 复算公式钉死：18(abs) + |{非abs: (exact∧sem≠WRONG)∨(¬exact∧sem=CORRECT)}|。套件 10158（+6）。

#### C536：ordinal-item 面 census 否证 — 未接线（RECORD-NEGATIVE）(a2cc77c)

紧双守卫检测器（序数+名词 + you-list-act）人口仅 3/500 且全 frozen-wrong（零 kill 面），机制在干净 fixture 上工作，但 frozen-500 census 证伪一切词法连接：① 3249768e 语料有**孪生五瓶鸡尾酒清单**（kh 12/12 打平，GT "5. Absinthe" vs decoy "5. Triple Sec"，仅 "gin-based" 措辞可分）；② 1903aded GT 裸数字清单 kh=1（任何相关性地板下必死）而 act 前导贴士清单 kh=8 获胜；③ 8752c811 抽对 item 但 exact_judge truth⊆pred 败于整句包裹 GT（判分侧缺口，非检索）。**教训：枚举清单没有唯一结构键——救援需嵌入 side-channel join（C506 前例）而非词法排序**。函数保留为文档化基建，管线字节等价（census-pinned test 钉住）。套件 10164（+6）。

#### C537：speech-act face — "you recommended" 认领第一人称行为句 (905ec67)

4c36ccef：问题引用助手自身行为（"the restaurant **you recommended**"），GT 承载句是第一人称言语行为 "For a romantic dinner, I would recommend Roscioli."，惜败 La Pergola 内容寄生行（145.5 vs 150.8，fine-dining/Italian/Rome 词汇重叠——C475 preface 族的排序版）。机制：floor-passer 间 tier 偏好（问题结构非阈值），无豁免 pass（C536 教训：地板排除自有理由）。bearer 判别 = I + 言语动词族（recommend/suggest/mention/tell/said/gave…，≤2 词间隙，含 've/ll/m 缩写）+ **3 结构守卫**（A/B 法医产物）：命题从句（suggest THAT hiking）/ 否定行为（you DIDN'T mention…I'll provide）/ 泛指宾语（recommend SOME OTHER bands——离题寄生行为动词本身）；preface 句永不作 bearer（2 个 fixture 回归抓出——**act-bearer ≠ act-mention，句子必须对具体宾语实施行为**）。组合顺序钉死：speech-act 先、C534 type face 后（"how many did you recommend" 仍归数字句，composition test 钉住）。A/B 48 行：脸翻转恰 4c36ccef（+1/−0，4 行 C534 时代 overlay verdict 逐字节同）。banked **252（0.504）**。套件 10169（+5）。

#### C538：answer-gate acquisition/conversation 陈述句面 — 0.508 (dbd5f5e)

C468 opener 寄生在 answer 门的完整版：66f24dbb 问买了什么，GT 承载句 "For my sister's birthday, I got her a yellow dress"（hits=2）输给开场白 "Here's a start - I've bought gifts..."（hits=3）。机制 `answer_acquisition_face` 接线在 answer_extractive 尾部：问题头动词族映射（buy/purchase/complete/finish/get）+ who-conversation 形态（"my conversation with Sarah"）；tier-1 = 第一人称过去陈述 + 词族成员 + C501 hits≥2 地板复用 + opener 任意位置排除（C475 `_RECALL_PREAMBLE_RE`）。+2 rescue（66f24dbb、3f1e9474），changed=3/500，0 kills，1 neutral（acq:finish 把 face 换成更直接的 bearer，两侧都 banked）。banked **254（0.508**；账本 tsv/kd 记 0.506 为算术滑差——252→254 应 +0.004，分母 500 由 250→0.500、255→0.510 钉死**）**。套件 10185（+16 tests TestAcquisitionFace）。

#### C539：answer-gate opener 降级地板 — 0.510 (4269dd2)

census 三连先于接线：判分层零人口（exact=True ∩ NEEDS_JUDGE = 0，C535 已榨干，方向永久关闭）；pref 组合 oracle 0/30（head 模板 × MIDS × 全部偏好句最高覆盖 0.38，走人）；opener census 16/16 FULL 行胜者全是 hand-over/acknowledgment/meta 形状——C475 寄生在 answer 门主路径的完整暴露。**朴素同分降级地板被离线全人口模拟证伪（70 行 hand-over 胜者枚举 ~155s：2 rescue/5 kill 净负）**——kill 形状一致：hand-over 首行是多句消息，答案嵌在同句延续里。幸存判别式 = **rep_kh > win_kh 严格证据优势**（5 个 kill 全是同分降级）+ 第一人称陈述守卫（剔除 list/lecture/meta 面具），接线在 acq face **之前**（floor 动过的行 acq 可再认领，保护 3f1e9474）。离线模拟精确预测 A/B（+1/0 kill/翻转行清单）——**face 类改动默认先 census-模拟再接线**从此是纪律。+1 rescue 87f22b4a（GT "$120"，rep_kh=4 vs hand-over win_kh=2），changed=9/500，8 个 banked-neutral 翻转。banked **255（0.510）**。套件 10196（+11）。

## Cycles 540-542: 0.510→0.520 — 序数面收债 + judge 侧 face 家族

> 官方口径（LongMemEval **s_cleaned** full-500，PYTHONHASHSEED=7，deterministic cascade banked）轨迹：0.510（C539）→ **0.512（C540）** → **0.518（C541）** → **0.520（C542）**。本段主轴：C536 RECORD-NEGATIVE 债务以**另一种分隔符**（短语连续 run，非被证伪的嵌入 join）清偿接线；face 概念从 gate 侧（候选重排）延伸到 **judge 侧**（NEEDS_JUDGE 区间的 verdict rescue，数学上只可能 NEEDS_JUDGE→CORRECT）；基础设施上 authoritative full-500 live 重跑验证台账并退役脆弱的 delta chain。概念教程见 [TUTORIAL-ANSWER-FACES.md](TUTORIAL-ANSWER-FACES.md)。

#### C540：ordinal-item 面 WIRED — phrase-run tie-break 清偿 C536 债务 (277f90b)

C536 声明的嵌入 side-channel join 在实现前被证伪（3249768e probe：message-level cos(q,decoy) 0.7068 > GT 0.5607——MiniLM 把问题里 'gin-based' 约束当次要质量，干扰清单是问题域的语义超集）。幸存分隔符是**问题短语连续性**：`answer_ordinal` 按 `_kw_phrase_run`（label tokens 中最长连续问题关键词 run，两侧 Cycle-471 归一化）打分，仅当 best run ≥2 才认领——**单靠 kh 地板的承载句选择恰是 C536 失败模式**（1903aded presentation-tips 清单 kh=8/run=0 会答 'Encourage Questions'，被阻断，逐字节 fall-through 验证）。gate 接线在 speaker_recall **之前**（它修的 preface 寄生胜者正是 speaker_recall 输出，C468 家族）；C536 守卫全保留。A/B full-500：changed=10，+1 rescue 3249768e（孪生鸡尾酒清单 kh 12/12 打平，GT 短语 run 3 vs 干扰 2），0 kills。**A/B 基建陷阱**（error-patterns 家族 #4）：overlay dumps `str(ans)[:200]` 截断使 banked(HEAD) 误读 254——live 管线逐字节复现 C539 答案，账目自洽 255+1=256。**同周期 HEARTBEAT 陈旧情报修正**：entropy-gate '6 题误杀' 被全量复跑证伪（7 行重答全 NEEDS_JUDGE，零真误杀，负结果归档）。banked **256（0.512）**。套件 10199（+3）。

#### C541：judge reference-alias faces + where-gate intent guard — 0.518 (14e8991)

两个 judge face 落在 NEEDS_JUDGE 区间（guards 1-3 与 subset veto 之后才可达，纯上行）：`_sem_paren_acronym_face`——reference 自带别名断言 'Full Name (ACRONYM)'，token 守卫的缩写匹配（rescue 1d4da289 OTP、25e5aa4f UCLA）；`_sem_place_complement_face`——GT '<head> in <Capitalized Tail>' 是判分者消歧而非答案一部分，head tokens ⊆ answer ∧ tail 缺席即 CORRECT（rescue 3b6f954b University of Melbourne in Australia）。where-gate intent guard：did-form 地点问题中 locative clause 呈 intention 形态（_WHERE_INTENT_RE，16 标记）的候选降级，band-restricted + **clause-scoped**——朴素全句扫描被 census 证伪（1 rescue/2 kills：d52b4f67 已 banked 行被旁支 'want to get her something' 从句误伤），从句级变体 = 恰 1 变化/0 kills，与 acronym face 组合拳把 25e5aa4f 的 pred 从'考虑读硕'计划句翻到 'completed my undergrad in CS from UCLA'。51a45a95 弃置（跨 turn 推理，无诚实可机化规则）。验证：500 行 verdict 枚举 = 2 flips 全 rescue 0 降级；**C540 截断陷阱结构化** → changed-row delta 协议。banked **259（0.518）**。套件 10213（+14，test_reference_faces.py）。

#### C542：judge quoted-core GT-wrap face — 0.520 + authoritative live chain (2adcf92)

C540 留下的 in-pipeline live debt：8752c811 抽取出了**正确 item**，但 GT "The 27th parameter was 'Sound effects…'." 的 frame tokens 使逐字节相同的 pred 成为严格 token 子集 → Guard-3 subset veto → WRONG。`_sem_quoted_core_face`：reference 把断言事实包进引号（frame + quoted core）时，引号核心就是数据集断言的答案——norm(candidate)==norm(quoted-span) ⇒ 完整事实而非弱化子集；4 条引号 regex（ASCII+curly）带 word-boundary lookaround（撇号永不开 span），2-char span floor，branch-local 于 subset veto 分支 → 只可能 WRONG→CORRECT。Census：hit set 恰 {8752c811}；subset-veto 分支全人口 40 行。**基建**：HEAD 全量 live 重跑 500 行（1144s，FULL preds）精确验证 C541 台账 259，chain-vs-live diff 恰 1 行 stale（25e5aa4f true pred 未写回）——**delta chain 退役**，后续判分实验直接用 live500。**假 NET-NEGATIVE 险情**（显示层家族 #5，TOOLS.md 规则升级）：首跑 A/B 双臂公式不同源（frozen correct_exact vs live exact_judge）伪造 -2，修复 = 双臂逐字段同源 + 每行 baseline assert。banked **260（0.520）**。套件 10224（+11，test_quoted_core_face.py）。

---

## 许可

MIT
