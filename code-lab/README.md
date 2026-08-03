# 🧪 Code Lab

> 实验性项目集合 — 用最少代码探索 AI Agent 核心概念。

每个子项目都是独立的、自包含的，大部分用纯 Python 标准库实现（零依赖）。

---

## 子项目

### Agent 核心

| 项目 | 行数 | 描述 |
|------|------|------|
| [mini-agent](mini-agent/) | ~200 | 玩具级 Agent 框架：工具调用 + 记忆系统 |
| [pocket-agent](pocket-agent/) | ~130 | 极简 ReAct 循环演示（感知→思考→行动） |
| [mini-mcp](mini-mcp/) | ~150 | MCP 协议概念演示：工具注册、发现、调用 |
| [mini-mcp-bus.py](mini-mcp-bus.py) | ~295 | MCP 总线演示：多 Agent 通过协议互调 |

### 工具与管道

| 项目 | 行数 | 描述 |
|------|------|------|
| [agent-pipeline](agent-pipeline/) | ~400 | YAML 声明式工作流引擎，类 Unix pipe 哲学 |
| [prompt-weaver](prompt-weaver/) | ~350 | 轻量级 Prompt 编排引擎，零依赖 |
| [agent-memory-graph](agent-memory-graph/) | ~42,500 | ⭐ 知识图谱记忆引擎：800+ API，覆盖图算法、信息论、图分类、数据溯源、时序演化、向量检索、代码感知记忆、双时序查询 |

### 代码分析与可视化

| 项目 | 行数 | 描述 |
|------|------|------|
| [code-archaeologist](code-archaeologist/) | — | AI 驱动的 Git 历史考古报告生成器 |
| [ctxgen](ctxgen/) | — | 为 AI 编码助手自动生成项目上下文文件 |
| [md-knowledge-graph.py](md-knowledge-graph.py) | ~165 | 扫描 .md 文件，提取标题/链接/标签，输出 Mermaid 图 |
| [mindmap.py](mindmap.py) | ~310 | 从文本生成 ASCII 思维导图 |

### 开发者工具

| 项目 | 行数 | 描述 |
|------|------|------|
| [jp](jp/) | ~250 | 轻量级 JSONPath 查询工具 |

---

## 📊 agent-memory-graph 功能全景

该项目已从 300 行的教学示例演化为 42,500+ 行的完整图记忆引擎，包含 800+ 公开 API 和 6,850+ 测试用例，横跨 136 个测试文件。

| 功能域 | 方法数 | 代表 API |
|--------|--------|----------|
| **CRUD** | 12 | `add`, `update_node`, `link`, `delete_node` |
| **搜索** | 33 | `recall`, `search_unified`, `search_bm25`, `search_hybrid`, `search_graphrag` |
| **图度量** | 57 | `pagerank`, `betweenness_centrality`, `community_detect`, `clustering_coefficient` |
| **谱/信息论** | 22 | `von_neumann_entropy`, `spectral_entropy_contribution`, `ego_entropy_profile`, `entropy_fingerprint` |
| **记忆生命周期** | 24 | `forgetting_curve`, `consolidate_memory`, `fifa_forget`, `sleep_consolidate`, `strategic_forget` |
| **工作流/模式** | 14 | `add_workflow`, `retrieve_workflows`, `workflow_success_patterns` |
| **时序/版本** | 31 | `evolve`, `temporal_snapshot`, `query_as_of`, `temporal_diff`, `supersede` |
| **嵌入/向量** | 19 | `add_embedding`, `search_similar`, `train_kge`, `kge_score` |
| **图分类** | 9 | `rrf_classification`, `bayesian_classification`, `knn_classification`, `classification_compare`, `max_confidence_classification` |
| **分类评估** | 5 | `classification_benchmark`, `classification_noise_test`, `classification_cross_size`, `classification_parameter_sensitivity`, `classification_report` |
| **分类优化** | 1 | `classification_learned_weights` — 网格搜索最优模态权重 |
| **代码感知** | 8 | `add_code_node`, `explain_code`, `impact_analysis`, `code_subgraph`, `record_code_decision`, `code_nodes_by_kind`, `code_graph_summary` |
| **双时序** | 2 | `query_believed_as_of`, `temporal_delta_query` — 真·双时序查询（valid time + transaction time）|
| **变更追踪** | 1 | `what_changed_since` — 时间戳以来的图变更报告 |
| **诊断** | 3 | `graph_health_score`, `entropy_dashboard`, `get_operation_history` |
| **条件遍历** | 3 | `conditioned_traverse`, `project_graph`, `multi_perspective_analysis` |
| **序列化** | 24 | `export_json`, `to_markdown`, `serialize_dot`, `serialize_graphml` |

### 📐 信息论进化史（Cycles 306–316 + 326–349）

最新里程碑：用信息论工具量化图结构，从单一指标到完整分类体系，再到元分类器。

| 阶段 | Cycles | 代表方法 | 核心思想 |
|------|--------|----------|----------|
| 基础 | 306–309 | `entropy_contribution`, `spectral_divergence` | 边际熵 + 图形状差异 |
| 谱分析 | 310–314 | `spectral_entropy_contribution`, `ego_entropy_profile`, `entropy_fingerprint` | VNE per-node + ego-local + 指纹 |
| 拓扑分类 | 315–316 | `graph_type_indicator`, `node_entropy_importance` | 7种拓扑 + 统一重要性排名 |
| 图分类 | 326–330 | `rrf_classification`, `bayesian_classification`, `knn_classification` | 多模态参考图匹配 |
| 元分类与基准 | 331–335 | `conditioned_traverse`, `multi_perspective_analysis`, `classification_benchmark`, `max_confidence_classification` | 条件遍历 + 基准评估 + 最大置信度元分类器 |
| 数据溯源与修正传播 | 336–338 | `propagate_correction`, `trace_derivation`, `trace_derivation_impact`, `derivation_lineage_report` | 级联修正标记 + 向后溯源 + 向前影响分析 + 统一世系报告 |
| 拓扑快捷统计 | 339 | `hub_nodes`, `peripheral_nodes`, `mean_degree` | 度数最高的 N 个节点 + 叶子节点 + 平均度数 |
| 噪声鲁棒性 | 340–341 | `classification_benchmark` (fix), `classification_noise_test` | 基准预测修复 + 噪声退化曲线 + 鲁棒性 AUC + breakpoint |
| 代码感知记忆 | 342–343 | `add_code_node`, `explain_code`, `impact_analysis`, `code_subgraph`, `record_code_decision`, `code_graph_summary` | 函数/类/文件节点 + 决策记录 + 影响分析 + 代码子图 |
| 双时序查询 | 344 | `query_believed_as_of`, `temporal_delta_query` | 真·双时序模型（valid time + transaction time）|
| 变更追踪 | 345 | `what_changed_since` | 时间戳以来的新增/修改/废弃节点报告 |
| 跨尺寸泛化 | 346 | `classification_cross_size` | 参考图与查询图尺寸差异时的分类稳定性 |
| 参数敏感性 | 347 | `classification_parameter_sensitivity` | 超参数鲁棒性评估（spectral bins, RRF k, KNN k 等）|
| 权重学习 | 348 | `classification_learned_weights` | 从标注数据网格搜索最优模态权重组合 |
| 分类报告 | 349 | `classification_report` | 混淆矩阵 + 每类 precision/recall/F1 + 错误分析 |
| 诊断 | 323–325 | `graph_health_score`, `entropy_dashboard`, `get_operation_history` | 一站式健康检查 |

---

## 📚 综合教程

读 [TUTORIAL.md](TUTORIAL.md) — 一篇串联 mini-agent → mini-mcp → agent-pipeline 的综合教程，用不到 800 行代码讲清 AI Agent 的三大核心：**大脑、工具、工作流**。

---

## 🚀 快速开始

大部分项目可以直接运行：

```bash
cd code-lab/mini-agent && python3 main.py
cd code-lab/pocket-agent && python3 pocket_agent.py
cd code-lab/mini-mcp && python3 mini_mcp.py
```

查看各子项目目录下的 README 获取详细说明。

---

## 设计哲学

- **最小实现** — 用最少代码展示核心概念，不做过度封装
- **零依赖** — 优先使用 Python 标准库，方便学习和实验
- **可组合** — 项目之间可以灵活组合，构建更复杂的系统
- **教育优先** — 代码可读性 > 性能优化

---

*Part of the [OpenClaw workspace](https://github.com/robertsong2019)*
