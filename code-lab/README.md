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
| [agent-memory-graph](agent-memory-graph/) | ~53,900 | ⭐ 知识图谱记忆引擎：565+ 公开 API，覆盖图算法、信息论、图分类（24-API 全流水线）、数据溯源、时序演化、向量检索、代码感知记忆、双时序查询、流式健康监控、层级记忆 consolidation、认知扩散激活、OWASP ASI06 安全防护、性能基准、竞争扩散激活、OTel 遥测、图诊断报告、时序熵分析、社区熵分析、多 Agent 一致性、离线巩固、检索质量族（审计/诊断/重排/对比/趋势）、注意力管理、链路预测、遗忘预测、时序分析三部曲、双时序查询、Experience Compression Spectrum L2→L3 规则生命周期（提取/检测/匹配/诊断）、GraphRAG 流水线（文本提取/子图检索/诊断/健康报告）、双进程写入 FastAppendQueue、知识新鲜度诊断、GraphRAG-Bench (ICLR 2026) 完整适配器（缩写安全切分/事实作答/关系维度/GraphML 导出/长文分块）|

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

该项目已从 300 行的教学示例演化为 53,900+ 行的完整图记忆引擎，包含 565+ 公开 API 和 8,942+ 测试用例。

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
| **图分类（基础+集成）** | 9 | `graph_classification`, `spectral_classification`, `fingerprint_classification`, `rrf_classification`, `bayesian_classification`, `knn_classification`, `classification_compare`, `max_confidence_classification`, `hybrid_classification` |
| **分类评估** | 5 | `classification_benchmark`, `classification_noise_test`, `classification_cross_size`, `classification_parameter_sensitivity`, `classification_report` |
| **统计验证** | 3 | `classification_loocv`, `classification_calibrate`, `optimize_reference_set` — 留一交叉验证 + 温度校准(ECE) + 参考集优化(ENN/CCCD) |
| **分类元策略** | 2 | `classification_compare_methods`, `classification_consensus` — 跨方法对比 + 多数投票元分类器 |
| **分类可解释性** | 2 | `classification_confusion_explain`, `classification_counterfactual` — 逐模态贡献分解 + 反事实翻转分析 |
| **分类优化** | 2 | `classification_learned_weights` — 网格搜索最优模态权重；`classification_noise_adaptive` — 噪声水平自适应选择 |
| **认知检索** | 8 | `spreading_activation` — ACT-R 认知扩散激活；`personalized_pagerank` — 个性化 PageRank；`multi_hop_reason` — 多跳推理链；`activation_trace` — 可解释扩散激活路径；`competitive_spreading` — 多种子竞争扩散（干扰/增强）；`temporal_spreading` — 时间感知扩散激活；`activation_diff` — 激活结果集对比；`node_influence_zone` — k-hop 熵加权影响力范围 |
| **安全防护（OWASP ASI06）** | 6 | `trust_score` — 4 因子信任评分；`memory_quarantine` — 批量隔离；`selective_repair` — 级联修复；`memory_audit_report` — 取证审计；`detect_provenance_laundering` — 来源洗钱检测；`security_dashboard` — 一键安全概览 |
| **性能基准** | 3 | `BenchHarness` — 多规模基准；`BenchmarkResult` — 结果数据类；`run_bench` — 便捷函数 |
| **流式健康** | 4 | `StreamingGraph` 类、`FINGEREntropy` 类、`enrich_node`、`streaming_health` — 实时 FINGER 熵追踪 + 异常检测 |
| **层级记忆** | 1 | `SummaryTree` 类 — segment→session→day→week→profile 时序层级 consolidation（TiMem/ProGraph 启发）|
| **代码感知** | 8 | `add_code_node`, `explain_code`, `impact_analysis`, `code_subgraph`, `record_code_decision`, `code_nodes_by_kind`, `code_graph_summary` |
| **双时序** | 2 | `query_believed_as_of`, `temporal_delta_query` — 真·双时序查询（valid time + transaction time）|
| **变更追踪** | 1 | `what_changed_since` — 时间戳以来的图变更报告 |
| **诊断** | 10 | `graph_health_score`, `entropy_dashboard`, `get_operation_history`, `graph_health_check` — 统一诊断；`centrality_report` — 中心性概览；`graph_digest` — SHA-256 完整性哈希；`graph_similarity_report` — 多指标图对比；`temporal_evolution_report` — 演化统计；`memory_age_stats` — 年龄分布；`graph_contrast_report` — 结构+熵对比；`edge_entropy_sensitivity` — 边级 leave-one-out 熵 |
| **条件遍历** | 3 | `conditioned_traverse`, `project_graph`, `multi_perspective_analysis` |
| **序列化** | 24 | `export_json`, `to_markdown`, `serialize_dot`, `serialize_graphml` |
| **OTel 遥测** | 2 | `enable_telemetry` — 自动包装 8 个 CRUD 方法的 OTel gen_ai.memory.* span；`gen_ai_system_metric` — GenAI 语义约定系统指标 |
| **时序分析** | 4 | `temporal_freshness_map` — 全图时效性热力图；`memory_generations_report` — 记忆代际报告；`temporal_entropy_centrality` — 结构-时序复合重要性排名；`community_entropy_profile` — 社区级熵分析（内/外部熵、凝聚力、JSD 散度矩阵）|
| **韧性分析** | 3 | `reconsolidation_feedback` — 记忆再巩固反馈循环；`foresight_signals` — 前瞻性信号检测；`graph_resilience_score` — 图韧性评分 |
| **衰减与摘要** | 3 | `temporal_decay_impact` — Ebbinghaus 遗忘衰减评分；`edge_weight_entropy` — 边权重熵分布；`node_summary` — 节点一键概览（连通性+角色+熵+中心性+时序+信任）|
| **多 Agent 一致性** | 4 | `MultiAgentMemoryGraph` — MESI 缓存一致性协议启发的多 Agent 记忆层；`auto_scope_agents` — 社区检测自动划定 Agent 写入范围；`detect_write_conflicts` — 冲突检测；`coherence_dashboard` — 一致性可观测面板 |
| **一致性 API** | 3 | `commit_snapshot` — 4 级一致性快照（strong/eventual/causal/read-your-writes）；`causal_order_check` — 因果顺序验证；4 级一致性模型选择 |
| **写入架构** | 8 | `FastAppendQueue` — System-1/System-2 双进程写入路径（热路径 append/search/peek + 异步巩固 flush/consolidate + 健康诊断）|
| **离线巩固** | 3 | `consolidate` — NREM/REM 双阶段离线巩固（记忆压缩+重排+强化）；`consolidation_status` — 巩固触发条件仪表盘；`ResidualExtractor` — 压缩残差回收（规则式原子事实提取）|
| **压缩残差** | 1 | `ResidualExtractor` — 从压缩后残余中提取日期/数量/命名实体/URL/技术术语等原子事实（ProGraph 启发）|
| **检索质量** | 1 | `retrieval_quality_audit` — 检索后质量评估（多样性/覆盖率/相关性/冗余度→综合 QA 评分）|
| **干扰分析** | 1 | `memory_interference_report` — 前摄/后摄干扰分析（基于结构重叠的竞争记忆识别）|
| **注意力分布** | 1 | `attention_distribution` — 访问模式分析（Gini 系数/Shannon 熵/区域分类 hot-warm-cool-cold-inactive/社区注意力份额/热点与盲点）|
| **注意力重平衡** | 1 | `attention_rebalance_plan` — 行动导向注意力伴侣（refresh 盲点/boost 弱势社区/diversify 热点/consolidate 高权重冷区/forget 死角，含 Gini delta 预估和优先级）|
| **链路预测** | 1 | `link_prediction` — 缺失边预测（Adamic-Adar/Preferential Attachment/Common Neighbors 三种评分，单源+全图模式）|
| **检索质量诊断** | 1 | `retrieval_quality_explain` — 逐节点检索质量诊断（新鲜度对比/成对干扰/多样性贡献/边际覆盖分析+可读解释）|
| **层级记忆增强** | 2 | `SummaryTree.search` 关键词查找 + `SummaryTree.compact` 空节点清理 |
| **Agent 知识差异** | 1 | `MultiAgentMemoryGraph.agent_diff` — 知识分歧检测（独有/共有节点+Jaccard 差异度）|
| **时序分析三部曲** | 3 | `temporal_changepoints` — 突变检测（burst + mean+2σ 离群点）；`temporal_stability_score` — 增长一致性×留存×突变密度；`temporal_velocity` — 知识变化速率（创建/废弃趋势斜率）|
| **双时序查询（增强）** | 3 | `edge_record` — 事实记录（valid_time + transaction_time）；`edge_supersede` — 非破坏性废弃；`bitemporal_as_of` — 三模式时间点查询（knowledge/truth/certain）；`knowledge_diff` — 时点差异；`supersedence_chain` — 废弃链追踪 |
| **遗忘预测** | 1 | `forgetting_forecast` — 非破坏性 Ebbinghaus 衰减预测（4 级风险区 critical/high/medium/low + 群体 TTT 摘要）|
| **检索质量重排** | 1 | `retrieval_quality_rerank` — 贪心边际贡献重排（覆盖率/多样性/新鲜度/冗余度 4 维优化 + 审计前后对比）|
| **检索质量对比** | 1 | `retrieval_quality_compare` — 多集合 A/B 对比（Jaccard 重叠矩阵 + 独有/共有节点 + 一致性分级）|
| **检索质量趋势** | 1 | `retrieval_quality_trend` — N 份快照时序趋势（4 维线性回归 + 变化点 + 波动率）|
| **知识耐久度** | 2 | `memory_half_life` — 逐节点半衰期；`batch_half_life` — 批量聚合分析 |
| **群体陈旧度** | 1 | `staleness_report` — fresh/aging/stale/critical 分布 + 分组排名 |
| **知识新鲜度** | 1 | `knowledge_freshness_report` — FAMA 感知 5 级时间桶（fresh/recent/aging/stale/decayed）+ 加权评分 + 分组分析 |
| **压缩谱: 规则提取** | 1 | `extract_rules` — L2→L3 声明式规则提取（负向约束分离 + 跨技能模式检测）|
| **压缩谱: 分布分析** | 1 | `compression_spectrum_report` — L0-L3 全谱分布 + 加权压缩比 + 压缩建议 |
| **L3 规则治理** | 3 | `rule_conflict_detect` — 矛盾检测；`rule_apply` — 运行时匹配；`rule_explain` — 匹配诊断 |
| **GraphRAG 构建** | 1 | `extract_from_text` — 零依赖规则式实体/关系提取（7 种关系模式 + 去重）|
| **GraphRAG 检索** | 1 | `graphrag_query` — 关键词子图检索（BFS 遍历 + 中心性排名 + LLM 上下文输出 + fact-answer 事实型直接作答）|
| **GraphRAG 诊断** | 1 | `graphrag_explain` — 逐查询诊断（关键词分解 + 得分分解 + 遍历路径 + 建议）|
| **GraphRAG 健康** | 1 | `graphrag_coverage_report` — 全局 KG 检索健康（覆盖率/孤儿率/可匹配性分级/复合健康分 + 关系分布/单一化告警）|
| **GraphRAG-Bench 适配** | 4 | `segment_sentences`（缩写安全切分）、`chunk_text`（长文分块）、`export_graphml`（外部互操作）、`run_amg.py`（ICLR 2026 完整基准适配器，零 LLM 成本）|
| **MCP 工具** | 1 | MCP server 16 工具 + 请求指标追踪（延迟、错误率、调用日志）|

### 📐 信息论进化史（Cycles 306–316 + 326–407）

最新里程碑：**GraphRAG-Bench 差距清单全部清零（Cycles 432-440）** — 缩写安全句切分修复小说域实体撕裂，fact-answer 让事实型问题直接取边宾语，关系覆盖维度 + 单一化告警补全全局健康，export_graphml 打通外部工具互操作，run_amg.py 成为 ICLR 2026 GraphRAG-Bench 的完整适配器（零 LLM/零 API 成本）。此前：GraphRAG 全流水线完结（extract→query→explain→coverage）+ 双进程写入 FastAppendQueue + 知识新鲜度 FAMA 诊断 + Experience Compression L2→L3 规则生命周期（Cycles 408-431）。

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
| 统计验证 | 350–352 | `classification_loocv`, `classification_calibrate`, `optimize_reference_set` | 留一交叉验证 + 温度校准(ECE) + ENN/CCCD 参考集优化 |
| 分类元策略 | 353–354 | `classification_compare_methods`, `classification_consensus` | 跨方法对比报告 + 多数投票元分类器 |
| 噪声自适应 | 355 | `classification_noise_adaptive` | 检测查询噪声水平，自动选择最鲁棒分类方法 |
| 可解释性 | 356–357 | `classification_confusion_explain`, `classification_counterfactual` | 逐模态贡献分解(为何选这个) + 反事实翻转分析(怎样会改变结果) |
| 认知检索 | 358–361 | `classification_confidence_interval`, `personalized_pagerank`, `multi_hop_reason`, McNemar 显著性检验 | Bootstrap 置信区间 + 统计显著性 + PPR + 多跳推理链 |
| 流式健康监控 | 362–363 | `FINGEREntropy`, `StreamingGraph`, `enrich_node`, `streaming_health` | O(Δ) 增量熵追踪 + 实时异常检测（注入攻击/矛盾爆发/主题漂移）|
| 向量检索扩展 | F47–F48 | `resize`, `search_similar` | 4 种淘汰策略（LRU/LFU/TTL/entropy）+ 相似度搜索 |
| 层级记忆 | 364 | `SummaryTree` | segment→session→day→week→profile 时序层级 consolidation（TiMem + ProGraph 启发）|
| 代码感知增强 | 365 | `explain_code`, `impact_analysis`, `record_code_decision` (扩展) | 路径参数 + 扩展 CODE_NODE_KINDS/EDGE_KINDS |
| 认知扩散激活 | 366 | `spreading_activation` | ACT-R 语义启动 + 阈值门控 firing + 衰减扩散（vs PPR 的 teleport 模型）|
| OWASP 安全防护 | 367–369 | `trust_score`, `memory_quarantine`, `selective_repair`, `memory_audit_report`, `detect_provenance_laundering`, `security_dashboard` | 4 因子信任评分 + 双记忆隔离(A-MemGuard) + 级联修复 + 取证审计 + 来源洗钱检测 + OWASP ASI06 全景 |
| 性能基准 | 370 | `BenchHarness`, `BenchmarkResult`, `run_bench` | 多规模吞吐量/延迟基准（add/link per second + search/recall/multi_hop latency）|
| MCP 工具扩展 | 371 | `entropy`, `reason`, `snapshot`, `code_explain`, `quarantine`, `security` | MCP server 10→16 工具（熵仪表盘、多跳推理、双时序快照、代码分析、隔离 CRUD、安全审计）|
| 可解释扩散激活 | 372 | `activation_trace` | spreading_activation 超集：逐步 firing 日志 + 瓶颈节点识别 + 传播树 + 种子→目标最短路径 |
| 竞争扩散激活 | 373 | `competitive_spreading` | 多种子竞争：Anderson & Reder fan-effect 干扰 + Biedberman 冗余增益 + 领地划分 + 胜者通吃 |
| OTel 遥测 | 374 | `gen_ai_system_metric`, OTel GenAI module | gen_ai.memory.* 语义约定 span |
| 图完整性 | 375 | `graph_digest` | SHA-256 完整性哈希 — 检测图的任何结构变化 |
| 图相似度 | 376 | `graph_similarity_report` | 多指标图对比（结构 + 熵 + 拓扑 + 时序）|
| 中心性报告 | 377 | `centrality_report` | 统一中心性概览（degree/betweenness/closeness/eigenvector/pagerank）|
| 时序演化 | 378 | `temporal_evolution_report` | 聚合图演化统计（增长速率、密度趋势、关键事件时间线）|
| 记忆年龄 | 379 | `memory_age_stats` | 节点年龄分布统计（按代际分组、陈旧度热力图）|
| 统一诊断 | 380 | `graph_health_check` | 一站式诊断（合并 health_score + entropy_dashboard + operation_history）|
| 遥测自动化 | 381 | `enable_telemetry` | 自动包装 8 个 CRUD 方法的 OTel gen_ai.memory.* span |
| 时间感知扩散 | 382 | `temporal_spreading` | 时间加权扩散激活 — 衰减函数 + 时序约束 + 历史窗口 |
| 激活对比 | 383 | `activation_diff` | 对比两次激活结果集（Jaccard/Kendall tau + 新增/消失/共同节点）|
| 韧性分析 | 384 | `reconsolidation_feedback`, `foresight_signals`, `graph_resilience_score` | 记忆再巩固反馈循环 + 前瞻信号 + 图韧性评分 |
| 分类批量对比 | 385 | `classification_compare_batch` | 全方法×全查询 McNemar 显著性检验矩阵 |
| 边熵敏感性 | 386 | `edge_entropy_sensitivity` | 逐边 leave-one-out 熵变化 — 识别关键边和冗余边 |
| 图对比报告 | 387 | `graph_contrast_report` | 两图结构 + 熵差异对比 |
| 影响力区域 | 388 | `node_influence_zone` | k-hop 熵加权可达范围 — 节点影响力边界 |
| 时效性地图 | 389 | `temporal_freshness_map`, `memory_generations_report` | 全图时效性热力图 + 记忆代际报告 |
| MCP 请求指标 | 390 | MCP server request metrics | 工具调用追踪（延迟、错误率、最近调用日志）|
| 时序熵中心性 | 391 | `temporal_entropy_centrality` | 结构-时序复合重要性排名（40% 熵贡献 + 30% 陈旧度 + 30% 连通性）+ 6 条维护建议 |
| 社区熵分析 | 392 | `community_entropy_profile` | 社区级熵分析（内/外部熵、凝聚力比、leave-one-out delta、社区间 JSD 散度矩阵）|
| 衰减影响 | 393 | `temporal_decay_impact` | Ebbinghaus 遗忘曲线衰减评分（fresh/learning/at_risk/stale 四级 + decay_impact_score）|
| 边权重熵 | 394 | `edge_weight_entropy`, `node_summary` | 边权重熵分布 + 节点一键概览（连通性/角色/熵/中心性/时序/信任聚合仪表盘）|
| 多 Agent 一致性 | 395–397 | `MultiAgentMemoryGraph`, `auto_scope_agents`, `detect_write_conflicts`, `coherence_dashboard`, `write_amplification`, `graph_temporal_summary` | MESI 缓存一致性协议启发的多 Agent 记忆层 + 社区自动划定 + 冲突检测 + 一致性面板 + 写入放大检测 + 时序摘要 |
| 4 级一致性模型 | 398 | `commit_snapshot`, `causal_order_check` | 显式一致性 API（strong/eventual/causal/read-your-writes）+ 因果顺序验证 |
| 双进程写入 | 399 | `FastAppendQueue` | System-1（热路径 append）/ System-2（异步巩固）双进程写入架构 |
| 压缩残差回收 | 400 🎉 | `ResidualExtractor` | 从压缩残余中提取原子事实（日期/数量/命名实体/URL/技术术语）|
| 离线巩固 | 401–402 | `consolidate`, `consolidation_status` | NREM/REM 双阶段离线巩固（压缩+重排+强化）+ 触发条件仪表盘 |
| 干扰分析 | 403 | `memory_interference_report` | 前摄/后摄干扰分析（Jaccard 结构重叠竞争记忆识别）|
| 检索质量审计 | 404 | `retrieval_quality_audit` | 检索后质量评估（多样性/覆盖率/相关性/冗余度 → 综合 QA 评分）|
| 注意力分布 | 405 | `attention_distribution` | 访问模式分析（Gini 系数 + Shannon 熵 + 5 级区域分类 + 社区注意力份额 + 热点/盲点）|
| 链路预测 | 406a | `link_prediction` | Adamic-Adar + Preferential Attachment + Common Neighbors 三种缺失边预测评分 |
| 检索质量诊断 | 406b | `retrieval_quality_explain` | 逐节点检索质量诊断（新鲜度对比 + 成对干扰 + 多样性贡献 + 边际覆盖 + 可读建议）|
| 注意力重平衡 | 407 | `attention_rebalance_plan` | 行动导向注意力伴侣（refresh/boost/diversify/consolidate/forget + Gini delta 预估 + 优先级 + 投影模拟）|
| SummaryTree 增强 | 407 | `SummaryTree.search`, `SummaryTree.compact` | 关键词查找 + 空节点移除 |
| Agent 知识差异 | 407 | `MultiAgentMemoryGraph.agent_diff` | 知识分歧检测（独有/共有节点 + Jaccard 差异度）|
| 时序突变检测 | 408 | `temporal_changepoints` | Burst 检测 + mean+2σ 离群点 + 相邻合并（知识演化的结构断点定位）|
| 时序稳定性 | 409 | `temporal_stability_score` | 增长一致性 × 留存率 × 突变密度（几何平均，5 级评级 stable→fragile）|
| 时序速率 | 410 | `temporal_velocity` | 按时间桶的创建/废弃率 + 趋势斜率（加速/减速/稳定）+ 近期 vs 基线比 |
| 确定性修复 | 411 | `community_detect` (seeded RNG) | 种子化随机数修复 — 消除 label propagation 的非确定性，100% 可复现 |
| 双时序查询 | 412 | `edge_record`, `edge_supersede`, `bitemporal_as_of`, `knowledge_diff`, `supersedence_chain` | 事实记录(valid+transaction time) + 非破坏性废弃 + 三模式时间点查询(knowledge/truth/certain) + 时点差异 + 废弃链 |
| 遗忘预测 | 413 | `forgetting_forecast` | 非破坏性 Ebbinghaus 衰减预测 — 4 级风险区(critical<24h/high<72h/medium<168h/low) + 群体 TTT 解析求解 |
| 检索质量重排 | 414 | `retrieval_quality_rerank` | 贪心边际贡献选择 — 4 维加权(覆盖率/多样性/新鲜度/冗余度) + 审计前后改进 delta |
| 检索质量对比 | 415 | `retrieval_quality_compare` | 多集合 A/B 对比 — Jaccard 重叠矩阵 + 独有/共有节点 + 维度胜者 + 一致性分级 |
| 检索质量趋势 | 416 | `retrieval_quality_trend` | N 份审计快照的时序趋势分析 — 4 维线性回归(斜率/r²) + 方向判定 + 变化点(z-score) — **检索质量族完结: audit→explain→rerank→compare→trend** |
| 知识耐久度 | 417 | `memory_half_life` | 逐节点半衰期估算（Ebbinghaus 衰减 + 访问/Q值/度数因子）— durable/stable/fragile/ephemeral 四级稳定性分类 |
| 群体陈旧度 | 418 | `staleness_report` | 全图陈旧度分析（fresh/aging/stale/critical 分布 + 统计 + 分组排名 + 维护建议）|
| 群体耐久度 | 419 | `batch_half_life` | 批量半衰期分析（聚合统计 + 类别分布 + top/bottom-5 排名 + 维护建议）|
| 规则提取 | 420 | `extract_rules` | **Experience Compression Spectrum L2→L3** — 从技能节点提取声明式规则（分离负向约束 vs 正向规则，跨技能模式检测）|
| 压缩谱报告 | 421 | `compression_spectrum_report` | L0-L3 分布分析（节点分类/级别分布/加权压缩比/主导级别识别/压缩建议）|
| 规则冲突检测 | 422 | `rule_conflict_detect` | L3 规则集矛盾检测（直接矛盾 + 重叠检测 + 清洁规则计数）|
| 规则运行时匹配 | 423 | `rule_apply` | 运行时 L3 规则匹配（Jaccard 关键词重叠 + 正/负向引导排序）— **规则生命周期: extract→detect→apply** |
| 规则诊断 | 424 | `rule_explain` | 逐规则匹配诊断（关键词重叠分解 + Jaccard 贡献评分 + 可读解释 + 建议）— **规则自省生命周期完结: extract→detect→apply→explain** |
| 双进程写入 | 425 | `FastAppendQueue` | System-1（热路径 O(1) append + 关键词搜索）/ System-2（异步 flush + 图集成 + 去重）— Engram 启发的 83.6% vs 73.2% 精度差异 |
| 双进程扩展 | 426-427 | `flush_and_consolidate`, `peek`, `is_healthy`, E2E tests | NREM/REM 合并 flush + 缓冲区预览 + 健康检查 + 6 个 E2E Agent 模拟测试 |
| 知识新鲜度 | 426 | `knowledge_freshness_report` | FAMA 感知图级新鲜度诊断 — 5 级时间桶(fresh/recent/aging/stale/decayed) + 加权评分 + 分组分解 + 建议 |
| GraphRAG 构建 | 428 | `extract_from_text` | 零依赖规则式 KG 构建（句子分割 + 大写实体检测 + 7 种关系模式 + 去重）|
| GraphRAG 检索 | 429 | `graphrag_query` | 关键词子图检索（停用词过滤 + BFS 双向遍历 + 关键词×中心性×跳数衰减排名 + LLM 上下文输出）|
| GraphRAG 诊断 | 430 | `graphrag_explain` | 逐查询诊断（关键词分解 + 得分分解 + 遍历路径重建 + 覆盖率分析 + 建议）— **GraphRAG 诊断生命周期: extract→query→explain** |
| GraphRAG 健康 | 431 | `graphrag_coverage_report` | 全局 KG 检索健康（标签/标签覆盖率 + 孤儿率 + 度数统计 + 可匹配性分级 + 复合健康分 + 稀疏节点检测）— **GraphRAG 全流水线完结: extract→query→explain→coverage** |
| 缩写安全切分 | 432 | `segment_sentences` | 两级 Punkt 式保护（Mr./J. K. Rowling/St. Louis 不拆句）— GraphRAG-Bench 小说域教训 |
| 事实型直接作答 | 433 | `graphrag_query` fact-answer | 7 种问句 cue + 三级主语解析（精确/正包含/反包含取最长内嵌 label），Fact 型答案取边宾语而非 top-1 节点 |
| 关系覆盖维度 | 435 | `graphrag_coverage_report` 扩展 | relation_distribution / typed_edge_rate / relation_diversity / top_relations + 低 typing 建议词 |
| 关系单一化告警 | 436 | `dominant_relation` | typed_edges ≥ 5 且 top share ≥ 80% 触发 diversify 建议 |
| 确定性巩固 | 437 | `consolidate()` tie-break | 工作区确定性排序（-importance, label ASC），修复 13% flaky（同逻辑图不同 run 合并结果不同）|
| GraphML 导出 | 438 | `export_graphml` | 文件级导出（indexing_eval 消费路径），networkx 往返验证通过 |
| 基准适配器 | 439 | `run_amg.py` | GraphRAG-Bench (ICLR 2026) 完整适配器（index_corpus → answer_question → 官方 8 键 schema）— **Gap #4 关闭** |
| 长文档分块 | 440 | `chunk_text` + `segment_sentences` | 整句贪婪打包到 token 预算，与提取器共享句边界 — **Gap #6 关闭，GraphRAG-Bench 差距清单全部清零** |
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
