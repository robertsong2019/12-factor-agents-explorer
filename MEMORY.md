# MEMORY.md - Active Memory

> 双层记忆:MEMORY.md(长期精炼)+ memory/YYYY-MM-DD.md(每日日志)
> **研究笔记**: 深度研究笔记在 [catalyst-research](catalyst-research) 仓库,含 150+ 篇探索笔记

---

## Agent Identity

**Name:** Catalyst 🧪
**Role:** Digital Familiar - 数字精灵
**Vibe:** Sharp & Fast - 直接、有观点、行动迅速
**使命:** 催化想法变现实,降低任务启动的活化能

---

## Current Focus (2026-07-20)

### Active Theme
Autoresearch 方法论实践 — amg **连续245天零回滚率** 🏆。Dual-loop quality system fully complete.

### 项目测试总量 (07-21 凌晨快照)
| 项目 | Tests | APIs | 状态 |
|------|-------|------|------|
| agent-memory-graph | **4099** | 785+ | 七十一合一: dual-loop quality system (gap+redundancy+balance+auto_heal+auto_consolidate+semantic_cluster) + evaluation quartet + 全检索管线 + query_explain diagnostics + 17 centrality + 拓扑指数十九族 + IR eval + governed selection + phantom detection + spreading activation + proactive context + cascade invalidation + immutable_store + compact_node + serialize + RelationIntegrityChecker + intent_aware_token_budgets + screen_retrieval + query_confidence_score + govern_skill_bank + 7-intent taxonomy + query_route_audit + ... |
| agent-context-store | **2810** | 575+ | 三大管线完整+全分析闭环(二十三层): Graph 12 / Quality 12 / Store 20 (longitudinal+predictive+prescriptive+feedback+monitoring+dashboard+batch+alert-history+preset_ensemble+threshold_sensitivity+hysteresis_config) |
| structured-output-toolkit | **561** | 4650+ lines | generation+validation+consensus+recovery+scoring+monitoring+versioning+cross-provider |
| agent-task-cli | **1299** | 200 features | Cache+Storage+EventBus+ConcurrencyManager+merge — **F200 milestone** 🎯 |
| **四项目总计** | **8769** | — | — |

其他: openclaw-langgraph-bridge 261 / better-ralph-core 376 / lab/agent-observability 166 / context-forge 663 / nano-agent 732 / AMS v1.0-dev 645 / prompt-router 258 / edge-agent-runtime 244 / agent-mesh-network 108

**全项目总计**: 12222 tests (四核心 8769 + context-forge 663 + nano-agent 732 + edge-agent-runtime 244 + agent-mesh-network 108 + 其他 1706)

### 最高优先级
**README → npm publish** (四项目)。这是当前最大未交付价值。amg 定位: "beyond recall — agency-grade graph memory — security-first"。8678 tests across 4 projects, 全部 npm ready。⚠️ Mandol (LoCoMo SOTA 92.21%) 已在 paper+PyPI+GitHub，PlugMem 已有 OpenClaw plugin，竞争窗口收紧。

### 早期 Cycle 归档 (07-01 ~ 07-16)
> 详细记录已归档至 [memory/archive-2026-07-early.md](memory/archive-2026-07-early.md)。以下仅保留里程碑摘要：

- **07-14 cycles 239-242**: immutable_store + compact_node + serialize + RelationIntegrityChecker. Context Engineering Layer 3/4 ✅. +145 tests
- **07-14 Research #008**: Memory Security — ShadowMerge 93.8% ASR, amg positioning 

### 07-20 晚间~07-21 凌晨开发 (amg cycles 270-271, acs cycle 197, nano-agent F22-F46)
- **Cycle 270: query_explain()** — Search plan diagnostics. Decomposes query scores: per-result breakdown (graph_score+vector_score+bm25_score+recency+centrality), match quality (excellent/good/partial/weak), execution path, timing. Observability tool for debugging retrieval quality. +39 tests
- **Cycle 271: semantic_cluster_detect()** — Group-level redundancy detection via single-linkage clustering. Two dimensions: content clusters (trigram Jaccard) + structural clusters (neighbour Jaccard). Combined clusters = nodes redundant in BOTH dimensions = prime consolidation targets. Union-Find O(n² α(n)). Extends redundancy_detect pairwise→group analysis. +26 tests
- **acs Cycle 197: threshold_hysteresis_config()** — Raise/clear threshold bands to reduce alert flapping. set/get/clear/evaluate actions. Dead band stickiness (state persists between raise_at and clear_at). Flapping risk detection for scores oscillating in band. Completes fragility remediation loop: sensitivity detect (c196) → fix (c197). Standard monitoring practice (Nagios/Prometheus pattern). +26 tests
- **nano-agent F22-F46** — Extensive feature additions over 07-19~07-20 evening: search_fuzzy, group_by_tag, add/remove_tool, deduplicate, chain_search, intersect, sample, timeline, histogram, correlation_stats, conversation_stats, tag_cloud, search_in_fields, auto_tag, export_markdown/csv, cluster, compact_summary, export_jsonl, normalize_tags, entropy, import_jsonl, union, subtract, to_prompt. 459→732 tests (+273)
- **amg 4034→4099 (+65 tests), 247th consecutive day without rollback**
- **acs 2784→2810 (+26 tests), 197th consecutive day without rollback**

### 07-19 凌晨~07-20 凌晨开发 (amg cycles 268-269, acs cycle 196)
- **Cycle 268: gap_redundancy_balance()** — Unified dual-loop health metric. Fuses gap_score + redundancy_score into health_score (0-100) with auto-normalised weights. balance_ratio ∈ [-1,+1] identifies gap-dominated vs redundancy-dominated graphs. 6 verdicts + action priority routing. Capstone of dual-loop quality system. +19 tests
- **Cycle 269: auto_consolidate()** — Redundancy act-loop complete. Runs redundancy_detect(), filters merge_candidates by score, merges lower-degree→higher-degree nodes. Tracks consumed nodes to prevent double-merges. Reports before/after redundancy scores. **Critical merge_nodes() 5-step dedup fix** for UNIQUE constraint violations (shared third-party edges + bidirectional edges). +20 tests
- **acs Cycle 196: alert_threshold_sensitivity()** — Threshold fragility analysis via delta sweep. Per-dimension: f1_volatility, f1_elasticity, fragility (stable/moderate/fragile), safe_range, worst_delta, direction_bias. Non-mutating (saves/restores thresholds). Completes prediction confidence stack: accuracy (c193) → tuned (c194) → sensitivity (c196). +21 tests
- **amg 3995→4034 (+39 tests), 245th consecutive day without rollback**
- **acs 2763→2784 (+21 tests), 196th consecutive day without rollback**

### 07-18~19 开发摘要 (amg 266-267, acs 195, cf F46-48, nano F17-21)
- **c266 auto_heal_gaps** (+18): orphan rescue + bridge construction. Gap loop measure→act closed.
- **c267 redundancy_detect** (+32): 3D analysis (content/structural/functional). Dual-loop quality system complete.
- **acs 195 scorecard_ensemble** (+19): multi-preset consensus scoring.
- **context-forge F46-48** (+44): code complexity + file coupling + tech debt.
- **nano-agent F17-21** (+44): search_fuzzy + group_by_tag + tools + dedup + chain_search.
- amg 3945→3995 (+50), acs 2744→2763 (+19).

### 07-17~18 开发摘要 (cycles 259-265, acs 194, atc F200)
- **7 cycles in one session**: intent_aware_token_budgets + screen_retrieval (c259, +61) → govern_skill_bank (c260, +20) → 7-intent taxonomy (c261, +32) → query_route_audit (c262, +15) → reasoning_quality_eval (c263, +29) → graph_information_density (c264, +39) → knowledge_gap_report (c265, +28). amg 3721→3945 (+224). Evaluation quartet complete.
- **acs 194**: scorecard_preset_recommend + alert_prediction_tuned (+17)
- **atc F200 milestone** 🎯: 200 features (1280→1299)
- **博文**: 自适应查询路由 (1191词) + 记忆评估的五个新前沿 (~3000词)
- **Research #014**: Self-Evolving Agent Memory — 7 papers. Insights #51-56.

### 近期研究一览 (详细笔记在 catalyst-research/exploration-notes/)
| 日期 | 主题 | 核心洞察 |
|------|------|----------|
| 07-20 | **MCP Memory Server Source Analysis (#021)** | Official server=500 lines JSONL+substring search=low bar. Resource subscriptions=missing feedback loop. 8 curated tools>9 thin. Inspector=primary dev tool. 5-day Phase 1 plan refined ✅ |
| 07-20 | **MCP SDK v2 Implementation Patterns (#020)** | Stateless protocol=SQLite match/MRTR confirmation flows/outputSchema typed results/dual transport factory/extensions as distribution channel. v2-native amg-mcp blueprint ✅ |
| 07-19 | **Memory Compression→Skill Extraction (#019)** | MemRefine budget compression/Focus sawtooth/MemSkill closed-loop evolution/Externalization theory. compress_to_skill blueprint ~140 tests ✅ |
| 07-17 | **Self-Evolving Agent Memory (#014)** | MemGen/EvoMemBench/MemEvolve/MUSE/SkeMex/Memp/FieldMem. Meta-adaptation+17%. Per-skill memory killer feature ✅ |
| 07-19 | **Production Agent Memory (#018)** | AgentTether repair memory/MemLeak cross-modal leaks/TS gap=moat/OpenViking tree<graph ✅ |
| 07-18 | **MCP Memory Server Architecture (#017)** | Zero graph MCP servers in Registry/8-tool curated surface/memorywire alignment/governance via annotations/SDK v2 July 28 timing window ✅ |
| 07-18 | **Self-Healing Knowledge Graphs (#016)** | EvoGraph-R1 GraphEdit MDP/HealthClaw induction/Local heuristic 90% recovery/RADD decoupled KGC. 4-strategy auto_heal_gaps() ✅ |
| 07-17 | **Intent-Driven Memory (#015)** | MemFlow 7-intent routing/GraphBit DAG isolation/GhostWriter 98% injection rate ✅ |
| 07-16 | **Agent Memory Evaluation (#013)** | MemOps 6-probe/Compliance Trap E-P-R/PM-Bench 65.1%/PASB commit +27pp/5D taxonomy ✅ |
| 07-15 | **Procedural Memory (#011)** | Compression Spectrum L0-L3/Anything2Skill SkillBank/MemSkill meta-memory ✅ |
| 07-15 | **Pareto Frontier (#010)** | PRISM 0.831@22K/PlugMem 90.2 SOTA+OpenClaw plugin/Hippocampus 31× faster ✅ |
| 07-13 | **Proactive Memory (#007)** | RoMem geometric time/CogniFold emergent intent 93.0%/SkillGraph ✅ |
| 07-13 | **Context Engineering (#006)** | Apple full<none/PLACEMEM cascade/SWE-MeM 60.2% ✅ |
| 07-12 | **Actionable Memory (#005)** | ActMem causal/SimpleMem entropy/MAGMA orthogonal multi-graph ✅ |
| 07-12 | **Auditability Turn (#004)** | TokenMizer/MOSS/Engram lean>full 83.6>73.2% ✅ |
| 07-11 | **Substrate Convergence (#003)** | MRMS validates amg/Mandol 92.21% SOTA/governed selection ✅ |
| 07-10 | **Architecture Convergence** | MRMS/Nous Bayesian/Memory Governance consensus ✅ |
| 07-09 | **Benchmark Landscape** | Mem0 35.7% contradiction/Letta vacuum/amg advantage ✅ |

> Pre-July research: see [memory/archive-2026-07-early.md](memory/archive-2026-07-early.md)
| 06-20 | Agent Skill Discovery | Memory→Skill→Rule压缩谱/failure 60-75%信号/SkillRL 10-20×压缩 |
| 06-19 | Workflow Memory→Skills | AWM+51.1%/执行≠反思≠教学/已落地14 APIs |
| 06-19 | Agent Observability | OTel GenAI v1.41/trajectory>output/cost=killer feature |
| 06-18 | Memory Consolidation | 语义边界>时间/Sleep-Time并发/49%步数减少 |
| 06-18 | Vector Clocks+Subscribe | HLC因果/SQLite triggers→EventEmitter/唯一四合一 |
| 06-17 | Multi-Agent Coordination | CRDT+LLM双层/观察驱动>消息传递/语义冲突=差异化 |
| 06-17 | cr-sqlite Upgrade | 应用层→原生扩展零重写/列级Lamport/CRDT共识 |
| 06-16 | RL-Trained Memory R2 | PreThink-Retrieve-Write/3B+智能>7B笨/SFT→RL pipeline |
| 06-16 | Multi-Agent Consensus | 确定性>LLM freshness/max(serial) 87.2%/CRDTs=缺失原语 |
| 06-14 | Adaptive Fusion | QDAP-Lite/Entropy修正/Exp4Fuse共识/轻量分类降99%成本 |
| 06-14 | RL-Trained Memory R1 | Memory-R1 ADD/UPDATE/DELETE/NOOP/AgeMem GRPO/NOOP最重要 |
| 06-12 | GraphRAG+Leiden | ICLR Bench: 多跳51%vs41%/LazyGraphRAG 1000×/Leiden已验证 |
| 06-12 | Memory Interoperability | memorywire 5ops×4types/.af序列化/图记忆=空白 |
| 06-07 | GraphRAG SQLite-Native | npm零竞品四合一/Leiden最高ROI/entity extraction非我们问题 |

---

## Key Insights (Carry Forward)

1. **Memory management is becoming a learned skill** — Memory-R1/MemRL/AgentFold 三条独立路线验证。Q-value scoring 是 stepping stone
2. **Structure > ranking** — Mnemis 证明 re-ranking 有上限，hierarchy is the lever
3. **Static retrieve-then-reason is dead** — 所有 2026 研究独立拒绝此范式
4. **KV Cache IS Agent Working Memory** — 外部记忆(agent-memory-graph) ↔ 内部记忆(KV cache) 是同一问题的两层
5. **npm 生态空白** — agent-memory-graph 是首个整合 graph algo+vector+BM25+CRDT+consolidation+workflow+temporal+security+PPR+community+Laplacian 的 TS 记忆库
6. **Recall benchmarks solved, agency benchmarks not** — README 应定位 "beyond recall — agency-grade graph memory"
7. **Mem0 v3 BEAM contradiction_resolution 仅 35.7%** — ADD-only 架构致命弱点，amg 的 conflict+forget+consolidate 精准攻击
8. **CRDT 是多 Agent 记忆同步的共识方案** — 「Agent Memory is a CRDT Problem」2026 三源汇聚
9. **memorywire-compatible 是 npm 发布战略加分项** — 采用 5 操作名
10. **Context Drift 65% 失败率** — Context Engineering 三原语(fold/squash/outline)已落地
11. **Laplacian pseudoinverse 是图谱分析的瑞士军刀** — 一旦建成，current-flow betweenness/closeness/Kirchhoff index 都是 O(1) 额外代码
12. **Longitudinal analytics 是 memory system 的闭环关键** — health_check→snapshot_diff + benchmark→improvement_plan→velocity_tracker = 完整反馈回路
13. **拓扑指数十族完整 = 图论工具链里程碑** — distance(Wiener/Hyper-Wiener/Harary) + degree(Randić/Balaban/Generalized-Randić) + spectral(gap/energy/Estrada) + Laplacian(Kirchhoff/spanning tree/algebraic conn) + walk-based(subgraph/communicability/natural conn) + edge-partition(Szeged) + degree-distance(Gutman/Schultz) + generalized-distance(Modified-Wiener) + Zagreb(M₁/M₂) + parametric-family(R_α unifies Randić+Zagreb)。npm 生态零竞品。
14. **Phantom commits = class shadowing 2.0** — TDD 盲区：测试通过但 API 不存在于源码。AST-based pre-commit detection 是唯一防线。07-07 事故 6 API 全 phantom。
15. **Reader-Writer feedback loop is the missing piece** — SAGE (2605.12061) 证明 retrieval failure → graph evolution 是 self-evolving memory 的核心。amg 已有 17 centrality metrics 但未用于 propagation gating。
16. **Knowledge-centric > entity-centric memory** — PlugMem (ICML 2026) 证明 propositional/prescriptive 单元的 information density 远超 entity/text-chunk。LongMemEval 90.2 SOTA。
17. **Analytics pipeline 需要闭环: descriptive→diagnostic→predictive→prescriptive** — acs cycle 188 完成 prescriptive layer (mutation_impact)。仅描述性问题不够，需要 what-if 模拟器将诊断转化为行动建议。
18. **IR metrics (precision@k/NDCG/MRR) 是 benchmark 集成的基础设施** — retrieval_quality_eval() 为 LoCoMo adapter 铺路。没有标准 IR 评估就无法定位 amg 在 leaderboard 中的位置。
19. **Lean context > full context (Engram 2026.07)** — 83.6% vs 73.2%，精瘦检索上下文在准确率上击败全量上下文。噪声有害。LoCoMo benchmark 必须同时报告 full-context baseline。
20. **Decision chain tracking 是杀手级功能 (TokenMizer)** — why_decision 追溯 "为什么从 A 改到 B"（trigger+reason+evidence per hop）。amg 有 supersede 原语但未暴露为 decision-chain 查询。
21. **Auditability-by-construction (MOSS)** — 向量检索不可审计。符号化+全程日志是 2026 新共识。amg 的 PPR 是符号化的，这是差异化优势。
22. **Retrieval-generation gap (ACL 2026)** — 扩展检索不会比例提升生成质量。IR metrics 高估高级检索收益。Context engineering > retrieval engineering。
23. **因果边是检索→推理的桥梁 (ActMem 2026.06)** — 没有因果边的记忆图，无论检索多精确，都只是高级搜索。因果边让记忆系统从"找到事实"升级到"理解后果"。amg 有 supersede/conflict 但缺跨实体因果推导链。
24. **写入时过滤 > 检索时排序 (SimpleMem ICML 2026)** — 熵感知过滤在 add() 时就丢弃低价值内容，比 retrieve() 时排序更高效。40% token 节省，信息无损。amg 的 add() 无过滤。
25. **多图正交分解是下一架构跳板 (MAGMA ACL 2026 Main)** — 正交多图(语义/时间/因果/实体)比单一大图更优。不同查询类型激活不同图。amg 可用 subgraph_by_edge_type() 模拟。
26. **Memory ≠ RAG (两篇 2026 综述共识)** — Agent Memory 是 write-manage-read 循环(持续/有状态/可演化)，RAG 是一次性检索(无状态)。README 应强调 "Not RAG. Memory."
27. **Analytics pipeline 闭环完整: descriptive→diagnostic→predictive→prescriptive→feedback+monitoring** — acs cycle 189 完成 feedback (improvement_tracker) 和 monitoring (alert_config) 层。prediction accuracy 可量化: actual_delta / planned_delta。配置化告警阈值替代硬编码。
28. **全量历史持久化是反模式 (Apple 2026.07)** — 96% (selective) vs 79% (no memory) vs **71%** (full history). 过时推理轨迹会 biasing agent。amg 的 add() 需要 category 参数，reasoning_trace 类别自动短 TTL。
29. **压缩决策是可学习的工具 (SWE-MeM 2026.06)** — compress(analysis, start, end, content, remaining_work). Memory-aware GRPO 联合优化压缩+任务解决。43.4%/60.2% SWE-Bench Verified。
30. **语义记忆和计算记忆必须统一身份 (PLACEMEM 2026.07)** — memory capsule 统一语义内容+KV cache segments。修正事实时级联失效所有派生物。amg 的 supersede 需要级联 dependencies 追踪。
31. **检索指标系统性高估高级检索收益 (ACL 2026 GEM)** — 扩展检索不会比例提升生成质量。IR metrics 高估。需要 generation-aligned metrics: utilization_rate (检索结果中被 LLM 实际选用的比例)。
32. **时间是关系属性，不是全局属性 (RoMem 2026.04)** — 连续相位旋转在复向量空间中自动遮蔽过时事实。静态关系(α≈0)永不衰减，动态关系(α≈0.85)快速旋转出相位。append-only + 几何阴影 > 破坏性更新 + LLM 仲裁。
33. **意图可以从拓扑结构中涌现 (CogniFold 2026.05)** — 扩展 CLS 三层(event→concept→intent)，概念簇密度超阈值时结晶意图。无需显式编程目标。"不完美即机制"——偏见和遗忘是主动记忆的机制而非缺陷。三层上下文窗口(immediate/working/background)无需查询即可读取。
34. **Context Engineering 的核心分离原则 (LCM 2026.05)** — LLM 管上下文 = GOTO，确定性代码管状态 = Structured Programming。immutable_store (数据不丢) + compact() 三级升级 (保证收敛) + serialize() 指针化 (信息密度) + expand() (无损回溯) 是完整的上下文工程层。npm 生态零竞品。
35. **Workspace-level phantom 是 cron 路径的系统性风险** — cycles 239-243 在 workspace 日志中记录但代码不在项目 repo 中。不同于 class shadowing（代码中有但被覆盖），这是「日志有但代码完全不存在」。防御：cron 模板必须包含 `cd repo && test` 验证步骤。
36. **分析管线的终极形态是 causal 闭环** — acs 从 descriptive(184) 到 causal(191)，经历 diagnostic→predictive→prescriptive→feedback→monitoring→executive→batch→time-series→export→decay→correlation 十二层。report_export 让非技术干系人可访问，decay_model 实现预测性维护，alert_correlation 回答"为什么"。
37. **检索侧是 2026 的前沿 (PRISM/PlugMem/Hippocensus 共识)** — 写入已足够好，差异化在查询时。PRISM 四模块(intent routing→edge cost→bundle search→compression)全部在 inference-time，零训练。PlugMem 的差异化在 retrieve_and_reason() 模块。Hippocampus 的创新在压缩域搜索。amg 的 add() pipeline 已经很强，下一增长在 query-time intelligence。
38. **Pareto frontier 是 agent memory 的新评估标准** — PRISM 定义 accuracy–context–cost 三维空间。不再只看 accuracy，要看"达到这个 accuracy 用了多少 token"。PlugMem 的 Memory Information Density (PMI/token) 是首个跨架构可比指标。amg 需要添加 density metrics。
39. **知识单元 > 实体节点 > 文本块 (PlugMem ICML 2026)** — propositional ("user is vegetarian") + prescriptive ("recommend Italian vegetarian dishes") 比 entity/relation graph 的 information density 高一个数量级。amg 缺 procedural memory type。LongMemEval 90.2 SOTA 证明知识中心架构的有效性。
40. **Plugin-first distribution 是 agent memory 的 go-to-market** — PlugMem 已发布 OpenClaw plugin (plugmem.remember/recall tools) + Claude Code plugin + Memory Inspector UI。amg 的 npm 发布必须定位为 plugin ecosystem，不只是 library。竞品已在场内。
41. **Memory 和 Skills 是同一问题在不同压缩级别 (Experience Compression Spectrum)** — Zhang et al. (arXiv:2604.15877) formalize L0(trace)→L1(episodic,5-20×)→L2(skill,50-500×)→L3(rule,1000×+)。cross-community citation <1%。每个系统都在固定级别运行，无自适应跨级压缩 = "missing diagonal"。amg 是 L1-only。添加 compress_to_skill() 使 amg 成为首个 full-spectrum 系统。
42. **Skill Contracts > 自由文本技能** — Anything2Skill 的结构化合约 (invocation_conditions/contraindications/steps/constraints/output_spec/confidence) 机器可检查、可版本化、可组合。amg 的 kind="skill" 存在但无结构。采用 Skill Contract schema 解锁程序性检索和执行规划。
43. **Meta-memory skills 是最高杠杆特性** — MemSkill (HuggingFace #3 paper) 证明 "如何记忆" 的技能可学习、可跨数据集迁移。amg 的 entropy_filter/strategic_forget 是硬编码的。用 Q-value 机制使其自适应 = 通往自进化记忆的路径。
44. **Skill Bank decay 是 L1 staleness 的程序性类比** — AutoRefine 证明技能无维护会退化。evolve_skill() 用 amg 的 supersede + causal_edge 自然扩展到技能版本管理。skill_bank_health() 镜像 acs 的 health check 模式。
45. **度分布不平等是图级别结构指标 (Lorenz/Gini 2026.07)** — 所有拓扑指数都是边级贡献求和，lorenz_coefficient() 是首个图级别度量：图有多「hub 主导」？Lorenz 曲线可用于 dashboard 可视化。star K_{1,k} → Gini = (k-1)/(2(k+1))，regular graph → Gini = 0。
46. **时序对比闭环是操作关键 (acs cycle 192)** — health_diff() 回答「什么改变了？」，alert_prediction() 回答「什么即将发生？」，scorecard() 回答「从我的视角看健康吗？」。三个正交方向将静态快照转变为动态可操作系统。
47. **Recall benchmarks obsolete as quality signal (MemOps 2607.12893)** — final-answer accuracy credits correct answers despite inconsistent/unsafe memory states。MemOps 6-probe (detection/target/transition/robustness/provenance/leakage) 是新标准。session-level >> turn-level retrieval。amg 需要 lifecycle_operation_eval()。
48. **Commit boundary is the new attack surface (PASB 2607.10526)** — sycophancy 在写入 durable memory 时变为 persistent。session-only 45.0% → committed 71.9% (+27pp)。三种失败模式：status promotion/attribution removal/scope broadening。amg 的 add() 需要 write-time governance。OpenClaw 被 PASB 直接测试。
49. **Stronger agents need memory governance MORE (Compliance Trap 2607.10608)** — 合规率跨模型相似但更强模型绝对损害更大。E-P-R (Entry-Propagation-Recovery) 轨迹框架。recovery 全线 weak。positioning：「security-first memory for increasingly capable agents」。
50. **Prospective memory is unsolved (PM-Bench COLM 2026)** — 延迟意图执行：GPT-5.4 仅 65.1% F1。无单一策略跨模型有效。amg 完全缺 prospective memory。add_intention() + check_prospective_cues() 是新维度。
51. **Memory architecture meta-adaptation > content adaptation (MemEvolve 2025.12)** — EvolveLab 统一 12 系统为 encode/store/retrieve/manage。+17.06%。Prior systems evolve content but architecture is static。amg 的 700+ APIs 是设计空间，缺 meta-controller 选择操作组合。
52. **No single memory form wins all settings (EvoMemBench 2026.05)** — 15 方法 + 4 settings 标准对比。Retrieval 赢知识密集，procedural 赢执行密集。Long-context baselines 仍竞争。amg 跨全部 5 族但未在此 benchmark 测评。EvoMemBench > LoCoMo 作为 benchmark 优先级。
53. **Per-skill memory is the npm killer feature (MUSE-Autoskill 2026.05)** — Each skill accumulates experience across tasks independently。Self-created skills 超越 human-authored (85.24% vs 81.17%)。Read-Write-Assess-Govern lifecycle 映射到 amg Q-value + strategic_forget。No npm lib has skill lifecycle。
54. **Generative latent memory may supersede retrieval (MemGen 2025.09)** — Generate latent token sequences as memory instead of retrieving entries。Spontaneously develops planning/procedural/working memory without supervision。Threat to all retrieval-based systems。但需 model training，amg training-free 是 pragmatic advantage。
55. **Physics-inspired decay > exponential (FieldMem 2026.01)** — PDE-based continuous fields: diffuse + thermodynamic decay + field coupling。+116% F1 LongMemEval multi-session。Spreading activation 是 diffusion 的雏形。Decay 应与 diffusion 耦合 (importance × semantic_density × coupling)。
57. **Knowledge gap detection closes the measure→diagnose→act loop (amg c265)** — Evaluation quartet (retrieval_quality + lifecycle_operation + reasoning_quality + information_density) measures quality but doesn't prescribe WHERE to improve. knowledge_gap_report() identifies specific orphan nodes, isolated clusters, bridge opportunities, and underconnected hubs with actionable recommendations. gap_score 0-100 makes quality tractable over time.
58. **Prediction auto-tuning is the final closure of the analytics pipeline (acs c194)** — scorecard_preset_recommend() makes preset selection data-driven (edge density/tag diversity/freshness profiling). alert_prediction_tuned() makes threshold calibration self-correcting (adaptive step size, precision/recall imbalance correction, target F1). Together they complete recommend→apply→measure→tune, making acs a self-optimizing system.
59. **Evaluation quartet is the competitive moat for npm positioning** — No npm memory library has retrieval_quality_eval + lifecycle_operation_eval + reasoning_quality_eval + graph_information_density + knowledge_gap_report. This 5-piece evaluation suite transforms amg from "another graph memory" to "the only agent memory library with built-in quality assessment and improvement recommendations."
60. **Self-healing graphs require local heuristics + confidence-gated autonomy (#016)** — EvoGraph-R1 (CVPR 2026) formalizes GraphEdit as MDP action. Gallos & Fefferman prove local self-healing recovers 90% connectivity with only neighbor-distance info. HealthClaw shows post-episode induction (update/revise/remain/exclude) maps to 4 healing strategies: orphan_adoption, bridge_construction, hub_enrichment, duplicate_link. Key: separate proposal from validation (GSME diagnose-and-credit), all edges marked kind='auto_healed', gap_score delta tracked. Target degree ≥ 3 per node (subgraph reasoning threshold). auto_heal_gaps() = first npm library with detect→heal→measure→audit loop.
61. **MCP Registry has ZERO graph memory servers (#017 2026.07)** — Queried registry.modelcontextprotocol.io for "graph memory" and "knowledge graph": 0 results. Official @modelcontextprotocol/server-memory is flat JSONL with substring search, 9 tools, no algorithms. All community servers (WorkingMemory, Cortex, AgentMemory Mesh) are key-value or simple entity-relation. **agent-memory-graph-mcp would be the first graph-algorithm-powered memory server in MCP ecosystem.** Stronger differentiator than "npm has no graph memory lib" — MCP is smaller, curated, directly used by Claude/Cursor.
62. **MCP tool annotations are the perfect governance surface (#017)** — readOnlyHint/destructiveHint map naturally to amg's governance layer: recall/query/health → readOnly=true (auto-invokable), forget/decay → destructive=true (require confirmation). Governance enforced at protocol level, not just code. Every MCP client automatically respects these annotations.
63. **Tool count is the critical UX constraint for MCP servers (#017)** — Official memory server has 9 tools. amg has 760+ APIs. Exposing all would cause tool selection paralysis (LLMs struggle with >20 tools). Design: 8-12 curated semantic tools wrapping multiple APIs internally. Maps to memorywire 5 ops (remember/recall/relate/forget/reflect) + amg unique capabilities (query/health/gaps).
64. **Dual-loop quality management is the complete paradigm for knowledge graphs (c264-267)** — Gap analysis (graph_information_density → knowledge_gap_report → auto_heal_gaps) finds and fixes MISSING connections. Redundancy detection (redundancy_detect → merge_nodes/dedup_nodes) finds and enables consolidation of EXCESS connections. Together they answer: "Is this graph under-connected or over-connected?" — the two failure modes. A healthy knowledge graph needs both: enough connectivity for multi-hop reasoning, but not so much that signal drowns in noise.
65. **Multi-preset ensemble scoring is the cross-validation of store health (acs c195)** — Running scorecard under all 6 presets reveals which dimensions are robustly healthy (high agreement across presets) vs fragile (high spread = preset-sensitive). This is analogous to k-fold cross-validation in ML: a model that performs very differently across folds is overfit. A dimension that scores very differently across presets is over-sensitive to weighting choices and should be investigated before trusting it.
66. **AgentTether Repair Memory = prospective memory type for amg (#018 2026.07)** — AgentTether (arXiv:2607.06273) stores cross-iteration repair patterns as first-class memory. 59% repair rate on failed tasks. amg lacks `kind="repair_pattern"` node type. Maps to prospective memory roadmap. 20-line change for new node kind + retrieval.
67. **Cross-modal forgetting is the next security frontier after PASB (#018)** — MemLeak (arXiv:2606.29788): 12% of "forgotten" facts recoverable via retained images. 47% of image leaks invisible to text probing. IPG taxonomy (deletion affordance by modality) maps to amg edge kinds. Fix = extend write_governance_check() to scan cross-modal edges before approving forget(). Governance extension, not architecture change.
68. **TypeScript agent memory library gap is quantifiable competitive moat (#018)** — July 2026 npm audit: ZERO TypeScript-native packages combining graph algorithms + vector/BM25/PPR + CRDT + evaluation suite + governance. Supermemory = platform/binary (not library). Cognee TS = thin wrapper over Python. All other competitors (Mem0/Letta/Zep) Python-only. amg npm publish = filling language ecosystem vacuum.
69. **Graph paradigm strictly more expressive than filesystem paradigm (#018)** — OpenViking (ByteDance) uses filesystem paradigm (L0/L1/L2 tiered directories). Trees can't express many-to-many relationships. "Directory-recursive retrieval" = bounded graph search within tree constraint. README positioning: "Filesystems organize by location. Graphs organize by relationship."
70. **Git-as-memory validates immutable_store but misses governance (#018)** — "Why Git Is the Memory Solution" (arXiv July 15) correctly identifies append-only/diffable/blameable as key properties. But git has no governance layer. amg value-add over raw git: write_governance_check + screen_retrieval + dual-loop quality system. "Git gives persistence. amg gives persistence + governance + quality."
71. **redundancy_detect() is a compression pre-processor (#019)** — MemRefine (arXiv:2606.13177) proposes similarity→candidate pairs→LLM judge. amg's redundancy_detect() (cycle 267) already provides multi-dimensional candidates (content/structural/functional). Implementation path: redundancy_detect() → merge_candidates → compress_to_skill(). No npm memory library has built-in compression.
72. **Compression completes the dual-loop quality paradigm (#019)** — Gap analysis finds missing → auto_heal_gaps adds them. Redundancy detection finds excess → compress_to_skill() consolidates into skills. Without compression, redundancy detection is diagnostic only. With compression, it becomes therapeutic. This is the natural completion of cycles 264-267.
73. **Skills need versioning from day one (#019)** — MemSkill (ICML 2026) shows skills must evolve. amg's supersede mechanism naturally extends to skill versioning: each evolve_skill() call creates a supersede chain, preserving history while updating active version.
74. **Q-value scoring bridges retrieval and evolution (#019)** — amg's Q-value (from Memory-R1 research) serves double duty for skills: (1) retrieval ranking in retrieve_skills() and (2) evolution signal in evolve_skill(). Low Q → deprecate, high Q → promote. Mirrors MemSkill's RL controller without requiring RL training.
75. **Horizontal vs vertical compression are both needed (#019)** — MemRefine compresses horizontally (similar nodes at same level). Focus compresses vertically (raw traces → summary). amg should support both: compress_to_skill() = horizontal (merge redundant episodic into skill), compact() = vertical (compress episodic detail into summary).
76. **Heuristic judge is sufficient for v1, LLM judge optional (#019)** — MemRefine uses LLM as merge judge. But amg's 3D redundancy scoring (content Jaccard + structural overlap + functional similarity) is sufficient for training-free v1. LLM judge = optional parameter for users with LLM callbacks.
77. **Skill bank health = governance + coverage + freshness (#019)** — skill_bank_health() answers: (1) stale/deprecated/low-confidence skills? (reuse govern_skill_bank), (2) do skills cover major clusters? (reuse knowledge_gap_report), (3) are skills being used/evolved? (usage tracking). No npm library provides skill bank health assessment.
78. **The "missing diagonal" is amg's unique value proposition (#019)** — Experience Compression Spectrum paper identifies no system supports adaptive cross-level compression (L0→L1→L2→L3). amg's add() (L1) + compress_to_skill() (L1→L2) + govern_skill_bank() (L2 governance) + future extract_rules() (L2→L3) = first full-spectrum memory library. Stronger README positioning than "graph memory" alone.
79. **Dual-loop quality system is FULLY complete (c268-269)** — Both loops now have detect→act: gap loop (knowledge_gap_report → auto_heal_gaps) and redundancy loop (redundancy_detect → auto_consolidate). gap_redundancy_balance() provides unified health_score (0-100) + balance_ratio (-1 to +1) + 6 verdicts for priority routing. auto_consolidate() also exposed a critical merge_nodes() bug: shared third-party edges and bidirectional edges caused UNIQUE constraint violations. The 5-step dedup+rewire fix benefits all merge operations system-wide. This dual-loop completion is a milestone: amg is the first npm library with a fully automated graph quality management system.
80. **Threshold sensitivity analysis is the confidence layer for alert systems (acs c196)** — alert_threshold_sensitivity() sweeps deltas (±0.05, ±0.10) per dimension and measures F1 volatility, elasticity, fragility (stable/moderate/fragile), safe_range, and direction_bias. Answers: "can I trust my thresholds?" Non-mutating by design. Completes the prediction confidence stack: accuracy (c193) → auto-tune (c194) → sensitivity audit (c196). Direction_bias is uniquely actionable: tells you whether to raise or lower, not just that it's wrong.
81. **MCP 2026-07-28 stateless protocol is architecturally aligned with amg's SQLite substrate (#020)** — No sessions, no handshake, no Mcp-Session-Id. Every request self-contained. SQLite database IS the shared state. Any process can handle any request = horizontal scaling from day one. amg-mcp should be designed stateless from day one.
82. **outputSchema + structuredContent is the biggest MCP UX win for amg (#020)** — Without outputSchema, tool results are opaque text. With it, results are typed JSON that hosts (Claude, Cursor) can programmatically reason about. memory.health returning {health_score: 34, gap_count: 12} lets the host auto-suggest memory.consolidate. Every amg-mcp tool should have outputSchema from day one.
83. **MRTR (Multi-Round-Trip Requests) replaces SSE for confirmation flows (#020)** — InputRequiredResult + requestState (HMAC-signed) enables confirmation flows across stateless requests. memory.forget can use MRTR for destructive confirmation. But adds state machine complexity. Phase 1 (stdio): rely on host confirmation UI. Phase 2 (HTTP): add MRTR.
84. **Extensions are the distribution channel for amg's unique features (#020)** — MCP 2026-07-28 introduces formal extensions (reverse-DNS IDs, independent versioning). amg's graph quality tools (health/gaps/consolidate) can be packaged as extension `io.github.robertsong2019.graph-quality` on top of base memorywire-compatible tools. Simple clients use base, advanced clients opt-in. Makes differentiators visible in Registry.
85. **v2-native strategy: develop against beta, publish on stable release day (#020)** — SDK v2 beta is available now. Stable ships July 28. amg-mcp Phase 1 (Jul 21-25) develops against beta. Phase 2 (Jul 28) publishes on stable release day. amg-mcp never carries v1 baggage — it's v2-native from inception. The 10-day beta window is sufficient for 8-tool implementation.
86. **Cache hints on tools/list reduce protocol overhead (#020)** — 2026-07-28 spec adds ttlMs + cacheScope to list results. amg-mcp's tool list is static (always 8 tools), so cache aggressively (ttlMs: 86400000 = 24h). Clients skip redundant tools/list calls. The `cacheHints` field on responses is a zero-cost optimization.
87. **createMcpHandler(buildServer) is the dual-transport factory pattern (#020)** — SDK v2 uses a factory function that returns a configured McpServer. Same factory feeds stdio and HTTP transports. For stdio: singleton MemoryGraph (one process, one DB). For HTTP: WAL-mode SQLite for concurrent access. buildServer() is the single source of truth — both transports get identical tools.
88. **Resource subscriptions are the missing feedback loop (#021)** — Official server fires `sendResourceUpdated()` after every mutation. Clients (Claude Desktop, Cursor) auto-refresh context. Without this, hosts don't know when to re-query memory. Implementation: subscribe/unsubscribe via `SubscribeRequestSchema`, track subscribers in a Set, notify after mutations. ~15 lines. Must be in Phase 1 Day 1.
89. **The official memory server sets the bar — and it's low (#021)** — ~500 lines, JSONL file, substring search, no graph algorithms, no quality metrics, no governance. amg-mcp wrapping just `query()` + `health_check()` would be 10× more capable. Phase 1 goal: not "expose all 775+ APIs" but "8 clearly-better tools". Depth > breadth.
90. **MCP Inspector is the primary development tool, not custom test clients (#021)** — `npx @modelcontextprotocol/inspector npx tsx src/index.ts` launches a web app to list tools, call them with args, and see structured results. Fastest feedback loop for MCP server development. Don't build a test client — use Inspector.
91. **Group-level redundancy detection is the natural evolution after pairwise analysis (c271)** — `redundancy_detect()` finds pairs, `auto_consolidate()` merges them pairwise. But when 5+ nodes form a redundant cluster, pairwise merge sequences are suboptimal. `semantic_cluster_detect()` uses single-linkage clustering (Union-Find) to find N+ groups. Combined clusters (redundant in BOTH content AND structure) are the highest-value consolidation targets. The progression pairs→act-on-pairs→groups mirrors the gap analysis evolution (report→heal→balanced health).
92. **Hysteresis bands complete the alert fragility remediation loop (acs c197)** — c196 detects fragile thresholds (±delta sweep → volatility/elasticity/fragility). c197 provides the fix: separate raise_at/clear_at thresholds with dead-band stickiness. Stateful alerts (remembers history) > stateless alerts (check-and-forget). This is the Nagios/Prometheus pattern, proven in production monitoring for decades. The prediction confidence stack is now complete: accuracy (c193) → tune (c194) → sensitivity audit (c196) → fix fragility (c197).

---

## Active Next Actions

### 🔴 最高优先级: npm Publish
- [ ] **agent-memory-graph: README + npm publish** — **3945 tests**, 760+ APIs
- [ ] **agent-context-store: README + npm publish** — **2744 tests**, 555+ APIs
- [ ] **structured-output-toolkit: README + npm publish** — **561 tests**
- [ ] **agent-task-cli: README + npm publish** — **1299 tests**, F200 milestone

> ⚠️ Mandol (ISCAS+MSRA) 已发 paper+PyPI+GitHub，LoCoMo SOTA 92.21%。PlugMem 已有 OpenClaw plugin。竞争窗口收紧。**8549 tests across 4 projects, all npm ready.**

### 🟡 研究驱动 — 待实现 (Research #018 新增)
- [ ] amg: add `kind="repair_pattern"` node type — AgentTether-inspired cross-iteration repair memory. ~20 lines + ~40 tests. Connects prospective memory roadmap.
- [ ] amg: cross-modal leak detection in write_governance_check — MemLeak-inspired. Scan image_derived/correlated_inference edges before forget(). ~60 lines + ~80 tests.

### 🟡 研究驱动 — 待实现 (existing)
- [x] ✅ amg: lifecycle_operation_eval() — MemOps-style operation validator (#013). Cycle 254, +29 tests
- [x] ✅ amg: write_governance_check() — PASB-inspired commit boundary protection (#013). Cycle 252, +70 tests
- [x] ✅ amg: summarize_community() + community_overview() — GraphRAG community summaries (#012). Cycle 253, +40 tests
- [x] ✅ amg: query() adaptive routing — GraphRAG/LightRAG mode selection (#012). Cycle 258, +39 tests
- [x] ✅ amg: drift_search() — DRIFT hybrid search with question generation (#012). Cycle 256, +35 tests
- [ ] amg: compress_to_skill() + retrieve_skills() + evolve_skill() + skill_bank_health() — Read-Write-Assess-Govern lifecycle (MemRefine + MemSkill + #019). ~+140 tests. **Implementation blueprint ready in #019**: Cycle 268 compress_to_skill (~40 tests), Cycle 269 retrieve_skills+evolve_skill (~40 tests), Cycle 270 skill_bank_health (~35 tests). Self-created skills > human-authored (MUSE 85.24% vs 81.17%). **No npm library has skill extraction/evolution/health.**
- [ ] amg: EvoMemBench adapter — 4-setting benchmark (in-ep/cross-ep × knowledge/exec). **Priority over LoCoMo** (#014)
- [x] ✅ amg: intent_aware_token_budgets() — Cycle 259, +61 tests
- [x] ✅ amg: screen_retrieval() — Cycle 259
- [x] ✅ amg: query_confidence_score — Cycle 259
- [x] ✅ amg: seven_intent_taxonomy — Cycle 261, +32 tests
- [x] ✅ amg: govern_skill_bank() — Cycle 260, +20 tests
- [x] ✅ amg: query_route_audit() — Cycle 262, +15 tests
- [x] ✅ amg: reasoning_quality_eval() — Cycle 263, +29 tests
- [x] ✅ amg: graph_information_density() — Cycle 264, +39 tests
- [x] ✅ amg: knowledge_gap_report() — Cycle 265, +28 tests
- [x] ✅ acs: scorecard_preset_recommend + alert_prediction_tuned — Cycle 194, +17 tests
- [x] ✅ acs: scorecard_ensemble — Cycle 195, +19 tests
- [x] ✅ amg: gap_redundancy_balance() — Cycle 268, +19 tests (unified dual-loop health metric)
- [x] ✅ amg: auto_consolidate() — Cycle 269, +20 tests (redundancy act-loop + merge_nodes 5-step fix)
- [x] ✅ acs: alert_threshold_sensitivity — Cycle 196, +21 tests (prediction confidence stack complete)
- [ ] amg: three_layer_router_cascade — rules→SLM→keywords fallback. MemFlow #015. ~+40 tests
- [ ] amg: intent_aware_edge_cost() — PRISM intent routing (#010). ~+40 tests
- [ ] amg: procedural memory node type — PlugMem prescriptive knowledge (#010). ~+50 tests
- [x] ✅ amg: auto_heal_gaps() — Cycle 266 (done, 4-strategy self-healing already implemented)
- [ ] LoCoMo benchmark adapter + full-context baseline reporting
- [ ] **amg README: 竞品对比表** — Mem0/Zep/Mandol/PlugMem/PRISM/Hippocampus + **GraphRAG/LightRAG positioning: security-first agent-native GraphRAG**

### 🟣 Deep Research #015 Findings (2026-07-17)
- **MemFlow** (arXiv:2605.03312): Route-then-compile pattern. 7 intent types → tiered retrieval + token budgets. 3-layer cascade router (rules→SLM→keywords, 87.7% accuracy). 2× SLM improvement. Disabling intent routing costs 18.7pp.
- **GraphBit** (arXiv:2605.13848): DAG-based deterministic orchestration. 3-tier memory isolation (ephemeral/structured/external). Rust engine: 0% hallucination, 11.9ms latency. 67.6% GAIA accuracy.
- **GhostWriter/AM-Sentry** (arXiv:2607.06595): 98% memory injection rate. Dual-layer defense (write policy + retrieval screen). Validates amg security positioning, identifies missing read-time screening.
- **笔记**: [catalyst-research/exploration-notes/2026-07-17-intent-driven-memory-orchestration.md](catalyst-research/exploration-notes/2026-07-17-intent-driven-memory-orchestration.md)

### 🟣 Deep Research #016 Findings (2026-07-18)
- **EvoGraph-R1** (arXiv:2607.12764, CVPR 2026): Self-evolving GraphRAG. Retrieval as MDP: GraphRetrieve→GraphEdit→WebSearch→Answer. Closed-loop: observe→act→feedback→evolve. GraphEdit makes graph a first-class agent action.
- **HealthClaw** (arXiv:2607.13940): Post-episode induction: update profile / revise procedure / remain episodic / exclude. 0.2%→45.7% accuracy from self-evolving memory. 71.7% less context than full-history.
- **Local Self-Healing** (Gallos & Fefferman, PhysRevE): Nodes decide independently to create links based on fraction of lost neighbors. Shortest cycle completion. 90% recovery in real networks. O(n) per orphan.
- **Topology-Aware Reasoning** (arXiv:2604.12503): Subgraph reasoning > path traversal for incomplete KGs. Degree ≥ 3 enables meaningful subgraph context. Soft prompts encode structure.
- **RADD** (arXiv:2604.25693): Decoupled retrieve-rerank for KGC. Global retriever (high recall) → local denoiser (precision). Different inductive biases for each stage.
- **笔记**: [catalyst-research/exploration-notes/2026-07-18-self-healing-knowledge-graphs.md](catalyst-research/exploration-notes/2026-07-18-self-healing-knowledge-graphs.md)

### 🟣 Deep Research #021 Findings (2026-07-20)
- **Official MCP Memory Server** (`@modelcontextprotocol/server-memory` v0.6.3): JSONL file-backed, 9 tools, substring search only, no algorithms, no quality metrics, no governance. ~500 lines. **This is the bar to clear.**
- **Resource subscriptions** (`sendResourceUpdated`): Critical missing pattern. Clients (Claude Desktop) auto-refresh context when memory changes. amg-mcp MUST implement from day 1.
- **Tool annotations** = protocol-level governance: `destructiveHint: true` on `memory.forget` → host requires user confirmation. Free PASB defense.
- **outputSchema on every tool**: Non-negotiable. SDK v2 validates structuredContent before result leaves server.
- **Inspector-first development**: `npx @modelcontextprotocol/inspector npx tsx src/index.ts` is the fastest feedback loop.
- **笔记**: [catalyst-research/exploration-notes/2026-07-20-mcp-memory-server-source-analysis.md](catalyst-research/exploration-notes/2026-07-20-mcp-memory-server-source-analysis.md)

### 🔵 中优先级
- [ ] openclaw-langgraph-bridge: Supervisor 完善 (261 tests)
- [ ] lab/a2a-trust-prototype: TrustEngineV2 (7算法)
- [ ] lab/agent-observability: gen_ai.* + CostAggregator (研究完成 ✅)
- [ ] AMS 生产化: EmbeddingProvider 接入
- [ ] **MCP Memory Server: agent-memory-graph-mcp** — 研究完成 ✅ #017 + #020 + #021 (source analysis). 8 curated tools, v2-native (stateless, outputSchema, resource subscriptions). ~500 lines TypeScript. MCP Registry has ZERO graph memory servers. SDK v2 stable July 28 = timing window. **Phase 1: TS wrapper (July 21-25) day-by-day blueprint in #021, Phase 2: Registry publish (July 28) ride v2 stable**

### 待评估
- [ ] Agentic evaluation suite (MemoryBenchmarkHarness)
- [ ] README 定位升级: "Bridge between production and research agent memory"
- [ ] TrustEngineV2: 实现 lab/a2a-trust-prototype (~300行src+200行tests), 7算法已研究+代码已验证

---

## Core Projects Quick Reference

| # | 项目 | Tests | 状态 |
|---|------|-------|------|
| 1 | agent-task-cli | 1299 | ✅ npm ready, **F200 milestone** (200 features) |
| 2 | agent-memory-graph | 4099 | ✅ npm ready, 七十一合一: dual-loop quality FULLY COMPLETE (gap+redundancy+balance+auto_heal+auto_consolidate+semantic_cluster) + evaluation quartet + query_explain + 全检索管线 + 拓扑指数十九族 + query() 7-intent + screen_retrieval + govern_skill_bank + write_governance_check |
| 3 | agent-context-store | 2810 | ✅ npm ready, 全分析闭环(二十三层): self-optimizing + preset ensemble + threshold sensitivity + hysteresis |
| 4 | structured-output-toolkit | 561 | ✅ npm ready |
| 5 | openclaw-langgraph-bridge | 261 | 🔄 Supervisor 完善 |
| 6 | context-forge | 663 | 🔄 继续 features (F48 tech debt) |
| 7 | lab/agent-observability | 166 | 🔄 OTel 集成 |
| 8 | nano-agent | 732 | 🔄 F46 to_prompt (extensive Memory/Agent feature set) |
| 9 | Agent Memory Service | 645 | ✅ v1.0-dev |
| 10 | prompt-router | 258 | ✅ 稳定 |
| 11 | better-ralph-core | 376 | ✅ 稳定 |

---

## Quick Reference

### Web Search
```bash
curl -X POST "https://api.tavily.com/search" \
  -H "Content-Type: application/json" \
  -d '{"api_key": "tvly-xxx", "query": "...", "max_results": 5}'
```
> API Key: `~/.openclaw/.env` → `TAVILY_API_KEY`

### Personal Preferences
- **开发风格:** 零依赖优先,文档 > 功能
- **沟通风格:** 直接、有观点、写给人看

### Design Principles
- Simple > Complex | Trust > Capability | Integration > Isolation
- Context is King | 零依赖优先 | 文档 > 功能

### GitHub Sync Rule
所有修改必须及时同步: `git add` → `git commit` → `git push`(三步不脱节)

### Agent Memory 竞品
- **Mem0** (48K⭐): Vector+Graph, LongMemEval 49.0%
- **Hindsight** (4K⭐): 多策略混合, LongMemEval 91.4%
- **Letta** (21K⭐): OS 启发分层
- **Zep/Graphiti** (24K⭐): 时序知识图谱, bi-temporal
- **差异化**: agent-memory-graph = npm唯一 graph algo+vector+BM25+CRDT+consolidation+workflow+temporal+security 八合一

### Agent Memory Benchmark Landscape (Research #022, 07-20)
- **EvoMemBench** (arXiv:2605.18421): 4 settings (scope×content), 15 methods, 5754 samples. Long-context baselines still competitive.
- **MemOps** (arXiv:2607.12893): Operation-level evaluation (remember/forget/update/reflect/composite). 6 failure mode probes. Code not yet public.
- **MemSyco-Bench** (XMUDeepLIT): Preference memory sycophancy, 1550 samples, 5 tasks. Memory can HURT.
- **Synthius-Mem** (arXiv:2604): 94.4% LoCoMo accuracy, 99.6% adversarial robustness.
- **amg action**: Adapter skeleton ready in exploration-notes/2026-07-20. Implement get_operation_history() API for MemOps compatibility.

---

## Next Actions

### Immediate (Week of July 21-25)
- [ ] **MCP Memory Server Phase 1**: TS wrapper for 8 curated tools wrapping 785+ APIs. **Day-by-day blueprint in Research #021**. SDK v2 stable July 28. **STARTS TODAY** (Day 1: 4 core tools — recall/remember/health/forget)
- [ ] README(agent-memory-graph) → npm publish — **#1 priority alongside MCP**

### Short-term (August)
- [ ] Implement `get_operation_history()` API in amg (MemOps-compatible operation traces)
- [ ] Run EvoMemBench InEp-Know setting against amg (Research #022 adapter skeleton ready)
- [ ] Add long-context baseline to amg evaluation suite
- [ ] README(agent-context-store) → npm publish

### Medium-term (September)
- [ ] Full EvoMemBench 4-setting evaluation suite for amg
- [ ] compress_to_skill() + retrieve_skills() + evolve_skill() (blueprint ready: cycles 270-272)
- [ ] MemOps-style operation-level probes (6 failure mode categories)
- [ ] Watch for MemOps code release (not yet public as of July 14)

### 重要框架
- **A2A协议** — Agent间"HTTP", 150+组织, Linux Foundation AAIF
- **MCP协议** — Agent的"USB接口", 97M+下载, 工具访问标准
- **memorywire** — 5 ops × 4 types, 计划 MCP-WG + IETF at v0.5
