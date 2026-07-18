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

## Current Focus (2026-07-18)

### Active Theme
Autoresearch 方法论实践 — amg **连续241天零回滚率** 🏆。

### 项目测试总量 (07-17 凌晨快照)
| 项目 | Tests | APIs | 状态 |
|------|-------|------|------|
| agent-memory-graph | **3945** | 760+ | 六十四合一: 全检索管线 + 17 centrality + 拓扑指数十九族 + IR eval + governed selection + phantom detection + spreading activation + proactive context + cascade invalidation + immutable_store + compact_node + serialize + RelationIntegrityChecker + intent_aware_token_budgets + screen_retrieval + query_confidence_score + govern_skill_bank + 7-intent taxonomy (temporal + constraint) + query_route_audit + ... |
| agent-context-store | **2744** | 555+ | 三大管线完整+全分析闭环(二十层): Graph 12 / Quality 12 (action+velocity+cohort+heatmap) / Store 17 (longitudinal+predictive+prescriptive+feedback+monitoring+dashboard+batch+alert-history) |
| structured-output-toolkit | **561** | 4650+ lines | generation+validation+consensus+recovery+scoring+monitoring+versioning+cross-provider |
| agent-task-cli | **1299** | 200 features | Cache+Storage+EventBus+ConcurrencyManager+merge — **F200 milestone** 🎯 |
| **四项目总计** | **8549** | — | — |

其他: openclaw-langgraph-bridge 261 / better-ralph-core 376 / lab/agent-observability 166 / context-forge 613 / nano-agent 384 / AMS v1.0-dev 645 / prompt-router 258

**全项目总计**: 11246+ tests (四核心 8549 + context-forge 613 + nano-agent 415 + 其他 1669)

### 最高优先级
**README → npm publish** (四项目)。这是当前最大未交付价值。amg 定位: "beyond recall — agency-grade graph memory — security-first"。8549 tests across 4 projects, 全部 npm ready。⚠️ Mandol (LoCoMo SOTA 92.21%) 已在 paper+PyPI+GitHub，PlugMem 已有 OpenClaw plugin，竞争窗口收紧。

### 早期 Cycle 归档 (07-01 ~ 07-16)
> 详细记录已归档至 [memory/archive-2026-07-early.md](memory/archive-2026-07-early.md)。以下仅保留里程碑摘要：

- **07-14 cycles 239-242**: immutable_store + compact_node + serialize + RelationIntegrityChecker. Context Engineering Layer 3/4 ✅. +145 tests
- **07-14 Research #008**: Memory Security — ShadowMerge 93.8% ASR, amg positioning 

### 07-17 晚间~07-18 凌晨开发 (amg cycles 259-265, acs cycle 194, agent-task-cli F198-F200)
- **Cycle 259: intent_aware_token_budgets + query_with_budgets + screen_retrieval + query_confidence_score** — MemFlow (arXiv:2605.03312) tiered token budgets (basic=200/local=500/hybrid=600/drift=800/global=1000) + GhostWriter/AM-Sentry (arXiv:2607.06595) read-time injection screening (14 instruction patterns, dual-layer defense complementing write_governance) + MemFlow Validator-inspired query confidence (5 factors: coverage/score_spread/graph_density/result_count/freshness). +61 tests
- **Cycle 260: govern_skill_bank()** — SkeMex/MUSE-inspired Govern step of Read-Write-Assess-Govern lifecycle. Four policies: (1) deprecate stale (>N days), (2) deprecate low-confidence, (3) merge redundant (Jaccard ≥ threshold via skill_compose), (4) prune overflow (max_skills). dry_run mode for audit. Completes procedural memory governance. +20 tests
- **Cycle 261: seven_intent_taxonomy** — MemFlow 7-intent expansion. query() routes from 5→7 modes: adds temporal_reasoning (bi-temporal scan with validity windows + supersede awareness) and constraint_validation (kind/tag/keyword search for rule/policy/requirement nodes). Fixed substring matching bug in _route_query (how∈show, was∈was) using word-boundary regex. +32 tests
- **Cycle 262: query_route_audit()** — Routing observability. Mode distribution + per-question rationale + optional result counts for latency analysis. Built-in diagnostic question set covers all 7 modes. +15 tests
- **Cycle 263: reasoning_quality_eval()** — 7-dimension graph quality assessment (coverage/connectivity/richness/freshness/consistency/redundancy/governance). Completes evaluation trio with retrieval_quality_eval + lifecycle_operation_eval. +29 tests
- **Cycle 264: graph_information_density()** — Evaluation quartet complete. Information density metric (nodes per token, edges per node, semantic diversity ratio). Enables Pareto frontier positioning. +39 tests
- **Cycle 265: knowledge_gap_report()** — Structural gap detection and actionable recommendations. Four gap types: orphan nodes (degree ≤1), isolated clusters (<2 cross-component edges), bridge opportunities (best node pairs across boundaries), underconnected hubs (high-weight/low-degree). gap_score 0-100 composite. Closes the measure→diagnose→act loop. +28 tests
- **acs Cycle 194: scorecard_preset_recommend + alert_prediction_tuned** — Store profile analysis (edge density/tag diversity/freshness/quality variance) → auto-recommend best preset. Prediction threshold self-tuning with adaptive step size (precision/recall imbalance correction, target F1). Closes recommend→apply→measure→tune cycle. +17 tests
- **agent-task-cli F198-F200** — ConcurrencyManager.awaitIdle (Promise-based idle wait) + Cache.shift (evict oldest LRU entry) + EventBus.hasListeners (boolean check). **F200 milestone: 200 utility features**. 1280→1299 tests (+19)
- **amg 3721→3945 (+224 tests), 241st consecutive day without rollback**
- **acs 2727→2744 (+17 tests), 194th consecutive day without rollback**

### 07-17 技术博文
- **自适应查询路由** (1191 词) — _route_query() 五条启发式规则完整实现 + dispatch 统一格式 + 性能数据表
- **记忆评估的五个新前沿** (~3000 词) — LoCoMo 虚晃一枪 → E-P-R 顺从陷阱 → MemOps 六探针 → PASB 阿谀陷阱 → 五维分类法

### 07-17 晚间深度研究 #014: Self-Evolving Agent Memory
> 7 papers (MemGen/EvoMemBench/MemEvolve/MUSE/SkeMex/Memp/FieldMem). Details in [catalyst-research](catalyst-research/exploration-notes/2026-07-17-self-evolving-agent-memory-meta-adaptive.md). Key insights #51-56 below. amg path: compress_to_skill + evolve_skill + skill_bank_health ~140 tests.

### 近期研究一览 (详细笔记在 catalyst-research/exploration-notes/)
| 日期 | 主题 | 核心洞察 |
|------|------|----------|
| 07-17 | **Self-Evolving Agent Memory (#014)** | MemGen/EvoMemBench/MemEvolve/MUSE/SkeMex/Memp/FieldMem. Meta-adaptation+17%. Per-skill memory killer feature ✅ |
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

---

## Active Next Actions

### 🔴 最高优先级: npm Publish
- [ ] **agent-memory-graph: README + npm publish** — **3945 tests**, 760+ APIs
- [ ] **agent-context-store: README + npm publish** — **2744 tests**, 555+ APIs
- [ ] **structured-output-toolkit: README + npm publish** — **561 tests**
- [ ] **agent-task-cli: README + npm publish** — **1299 tests**, F200 milestone

> ⚠️ Mandol (ISCAS+MSRA) 已发 paper+PyPI+GitHub，LoCoMo SOTA 92.21%。PlugMem 已有 OpenClaw plugin。竞争窗口收紧。**8549 tests across 4 projects, all npm ready.**

### 🟡 研究驱动 — 待实现
- [x] ✅ amg: lifecycle_operation_eval() — MemOps-style operation validator (#013). Cycle 254, +29 tests
- [x] ✅ amg: write_governance_check() — PASB-inspired commit boundary protection (#013). Cycle 252, +70 tests
- [x] ✅ amg: summarize_community() + community_overview() — GraphRAG community summaries (#012). Cycle 253, +40 tests
- [x] ✅ amg: query() adaptive routing — GraphRAG/LightRAG mode selection (#012). Cycle 258, +39 tests
- [x] ✅ amg: drift_search() — DRIFT hybrid search with question generation (#012). Cycle 256, +35 tests
- [ ] amg: compress_to_skill() + retrieve_skills() + evolve_skill() + skill_bank_health() — Read-Write-Assess-Govern lifecycle (SkeMex + MUSE + #014). ~+140 tests. **Self-created skills > human-authored (MUSE 85.24% vs 81.17%)**
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
- [x] ✅ amg: lifecycle_operation_eval() — Cycle 254, +29 tests
- [x] ✅ amg: write_governance_check() — Cycle 252, +70 tests
- [x] ✅ amg: summarize_community() + community_overview() — Cycle 253, +40 tests
- [x] ✅ amg: query() adaptive routing — Cycle 258, +39 tests
- [x] ✅ amg: drift_search() — Cycle 256, +35 tests
- [ ] amg: three_layer_router_cascade — rules→SLM→keywords fallback. MemFlow #015. ~+40 tests
- [ ] amg: intent_aware_edge_cost() — PRISM intent routing (#010). ~+40 tests
- [ ] amg: procedural memory node type — PlugMem prescriptive knowledge (#010). ~+50 tests
- [ ] amg: auto_heal_gaps() — 4-strategy self-healing (orphan_adoption + bridge_construction + hub_enrichment + duplicate_detection). Research #016, ~+35 tests. **detect→heal→measure→audit loop, first in npm ecosystem**
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

### 🔵 中优先级
- [ ] openclaw-langgraph-bridge: Supervisor 完善 (261 tests)
- [ ] lab/a2a-trust-prototype: TrustEngineV2 (7算法)
- [ ] lab/agent-observability: gen_ai.* + CostAggregator (研究完成 ✅)
- [ ] AMS 生产化: EmbeddingProvider 接入
- [ ] MCP Memory Server: agent-memory-graph-mcp ~200行

### 待评估
- [ ] agent-memory-graph-mcp 包实现 + MCP Registry 注册
- [ ] Agentic evaluation suite (MemoryBenchmarkHarness)
- [ ] README 定位升级: "Bridge between production and research agent memory"
- [ ] TrustEngineV2: 实现 lab/a2a-trust-prototype (~300行src+200行tests), 7算法已研究+代码已验证

---

## Core Projects Quick Reference

| # | 项目 | Tests | 状态 |
|---|------|-------|------|
| 1 | agent-task-cli | 1299 | ✅ npm ready, **F200 milestone** (200 features) |
| 2 | agent-memory-graph | 3945 | ✅ npm ready, 六十五合一 + 评估五重奏 (retrieval/lifecycle/reasoning/density/gap_report) + 全检索管线 + 拓扑指数十九族 + governed selection + phantom detection + spreading activation + proactive context + cascade invalidation + immutable_store + compact_node + serialize + RelationIntegrityChecker + write_governance_check + community_semantic + drift_search + prospective_memory + query() 7-intent routing + screen_retrieval + govern_skill_bank + query_route_audit |
| 3 | agent-context-store | 2744 | ✅ npm ready, 全分析闭环(二十层): descriptive→diagnostic→predictive→prescriptive→feedback→monitoring→executive→batch→time-series→export→decay→correlation→diff→prediction→scorecard→trend→prediction-qa→presets→preset_recommend→prediction_tuning (self-optimizing) |
| 4 | structured-output-toolkit | 561 | ✅ npm ready |
| 5 | openclaw-langgraph-bridge | 261 | 🔄 Supervisor 完善 |
| 6 | context-forge | 613 | 🔄 继续 features |
| 7 | lab/agent-observability | 166 | 🔄 OTel 集成 |
| 8 | nano-agent | 384 | 🔄 Memory 扩展 |
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

### 重要框架
- **A2A协议** — Agent间"HTTP", 150+组织, Linux Foundation AAIF
- **MCP协议** — Agent的"USB接口", 97M+下载, 工具访问标准
- **memorywire** — 5 ops × 4 types, 计划 MCP-WG + IETF at v0.5
