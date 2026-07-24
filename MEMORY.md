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

## Current Focus (2026-07-23)

### Active Theme
Autoresearch 方法论实践 — amg **连续253天零回滚率** 🏆。Degree-based entropy family complete: 5 indices × 2 APIs = 10 entropy measures。Triple-loop quality system complete (gap→heal, redundancy→consolidate, skill→compress)。acs **200天** 🏆 scorecard dimension correlation。MCP Phase 1 Day 5 cross-era verified。context-forge 1054 tests / 8684 lines (18 analysis dimensions).

### 项目测试总量 (07-25 凌晨快照)
| 项目 | Tests | APIs | 状态 |
|------|-------|------|------|
| agent-memory-graph | **4394** | 810+ | 七十七合一: degree-based entropy family (5 indices × 2 APIs) + triple-loop quality system + evaluation quartet + 全检索管线 + ... |
| agent-context-store | **2898** | 600+ | 二十六层: detect→configure→recommend→validate→**correlate** pipeline complete |
| structured-output-toolkit | **561** | 4650+ lines | generation+validation+consensus+recovery+scoring+monitoring+versioning+cross-provider |
| agent-task-cli | **1319** | 203 features | Cache+Storage+EventBus+ConcurrencyManager+merge — **F203** |
| **四项目总计** | **9172** | — | — |

其他: context-forge **1054** (F66, 8684 lines, 18 analysis dimensions) / nano-agent 732 / amg-mcp **122** (Day 5 cross-era verified) / prompt-weaver 223 / openclaw-langgraph-bridge 261 / better-ralph-core 376 / lab/agent-observability 166 / AMS v1.0-dev 645 / prompt-router 72 / edge-agent-runtime 244 / agent-mesh-network 108

**全项目总计**: 13130 tests (四核心 9172 + cf 1054 + nano 732 + mcp 122 + pw 223 + lg-bridge 261 + ralph 376 + observability 166 + AMS 645 + router 72 + edge 244 + mesh 108)

### 最高优先级
**README → npm publish** (四项目)。MCP Phase 1 Day 5 ✅ (cross-era verified, 122 tests)。amg 定位: "beyond recall — agency-grade graph memory — security-first"。9172 tests across 4 projects, 全部 npm ready。⚠️ Mandol (LoCoMo SOTA 92.21%) 已在 paper+PyPI+GitHub，PlugMem 已有 OpenClaw plugin，竞争窗口收紧。

### 早期 Cycle 归档 (07-01 ~ 07-16)
> 详细记录已归档至 [memory/archive-2026-07-early.md](memory/archive-2026-07-early.md)。以下仅保留里程碑摘要：

- **07-14 cycles 239-242**: immutable_store + compact_node + serialize + RelationIntegrityChecker. Context Engineering Layer 3/4 ✅. +145 tests
- **07-14 Research #008**: Memory Security — ShadowMerge 93.8% ASR, amg positioning 

### 07-24~25 开发 (amg cycles 279-280, cf F59-F66, autoresearch)
- **Cycle 280: abc_entropy() + ga_entropy()** — Shannon entropy of ABC and GA edge contributions. ABC uniquely filters K₂ edges (d_u+d_v−2=0). GA = ratio perspective (geometric/arithmetic). Degree-based entropy family complete: 5 indices × 2 APIs = 10 measures. +68 tests, 4326→4394. **253rd day**. bea3f92.
- **Cycle 279: randic_entropy() + zagreb_m1_entropy()** — Shannon entropy of Randić and Zagreb M₁ contributions. Randić emphasises low-degree edge heterogeneity (inverse weights), Zagreb M₁ emphasises high-degree (additive weights). +57 tests, 4269→4326. 252nd day. a5d2c6f.
- **context-forge F62-F66** — F62 analyzeLoggingHealth (console.* + catch-without-log), F63 analyzeEnvHealth (.env.example + hardcoded secrets), F64 analyzePerformancePatterns (sync I/O + nested loops), F65 analyzeTypeSafety (any/ts-ignore/type assertions), F66 analyzeCodeSmells (long files/deep nesting/magic numbers). 929→1054 (+125), 7670→8684 lines.
- **context-forge F59-F61** (07-24 evening) — F59 analyzeCliHealth (CLI completeness), F60 analyzeDependencyRisk (version pinning), F61 analyzeTestCoverage (untested file detection). 856→929 (+73), 7001→7670 lines.
- **autoresearch testing** — micro-agent-protocol 88→101 (+13), prompt-router 35→72 (+37). atc /tmp clone: deepMerge + PriorityQueue + debounce/throttle (+52, not pushed).

### 07-23~24 开发 (amg cycles 277-278, acs cycle 200, cf F56-F58, amg-mcp Day 5)
- **Cycle 278: sombor_entropy() + reduced_sombor_entropy()** — Shannon entropy of normalized Sombor edge contributions. Index (magnitude) + entropy (distribution) = complete structural descriptor. Normalized [0,1]: regular→1.0, irregular<1.0. RS entropy K₂=0 unique case. Degree-based family 16 metrics / 10 APIs. +46 tests, 4223→4269. **251st day**. 3ca0faf.
- **Cycle 277: auto_compress_skills()** — Automatic skill promotion: detect_skill_candidates → batch compress episodic clusters → skill nodes. Completes triple-loop quality system. Idempotent. +18 tests, 4205→4223. e481e60.
- **acs Cycle 200: scorecard_dimension_correlation()** — Pearson r between scorecard dimensions across presets. Classifies redundant (|r|≥0.8)/independent/complementary (r≤0.3). Merge suggestions. Capstone of scorecard analytics layer. +34 tests, 2864→2898. **200th day** 🏆. 8f54402.
- **context-forge F56-F58** — F56 analyzeAsyncPatterns (async/await, floating promises), F57 analyzeExportHealth (barrel files, re-export chains), F58 analyzeFunctionMetrics (length, params, return paths). 786→856 (+70), 6008→7001 lines.
- **amg-mcp Day 5** — Cross-era integration tests (93→122). Legacy↔Auto persistence verified, all 14 tools legacy-tested. bf3e3c0.
- **prompt-weaver CLI** — 39 CLI tests (184→223).
- **Research #024** — MCP SDK v2 Day-5: dual-era test gap, cacheHints 3-line ROI, MRTR deferred Phase 2.
- **amg 4205→4269 (+64), acs 2864→2898 (+34)** — amg 251st day 🏆, acs 200th day 🏆

### 07-22~23 开发摘要 (amg cycles 273-276, acs 199, amg-mcp Day 3-4, cf F55, atc R51)
- **c276**: sombor_index() + reduced_sombor_index() (+42). **c275**: detect_skill_candidates() (+19). **c273-274**: walk_statistics + edge_type_stats (+23). amg 4121→4205. **250th day** 🏆.
- **acs c199**: hysteresis_band_backtest() (+33). Closes detect→configure→recommend→validate. 199th day.
- **amg-mcp Day 3-4**: memory.gaps + memory.skills + HTTP transport (+50). Dual transport complete.
- **cf F55**: analyzeCommentHealth (+13). **atc R51**: F201-F203 (+20).
- **Research #023**: OTel GenAI + MCP Day 3. **Blog**: hysteresis essay. **amg-mcp README**: 274 lines.

### 07-21~22 早期开发摘要 (amg cycles 270-272, acs cycle 197-198, context-forge F49-F54, nano-agent F22-F46, amg-mcp Day 1-2)
- **c270 query_explain** (+39): search plan diagnostics — per-result score decomposition + match quality + timing. 246th day.
- **c271 semantic_cluster_detect** (+26): group-level redundancy via single-linkage clustering. 247th day.
- **c272 auto_consolidate_cluster** (+22): group-level batch merge. 248th day.
- **acs c197 threshold_hysteresis_config** (+26): raise/clear bands with dead-band stickiness + flapping detection. 197th day.
- **acs c198 hysteresis_band_recommender** (+21): auto-recommend bands. Three strategies + direction bias. 198th day.
- **nano-agent F22-F46** (+273): 25 features. 459→732.
- **context-forge F49-F54** (+110): 6 code analysis features (debug/import graph/maturity/security/error handling/duplicate code). 663→773, 5005→6008 lines.
- **amg-mcp Day 1-2** — MCP Phase 1 kickoff: 6 curated tools + resource subscription. 43 tests.

### 07-19 凌晨~07-20 凌晨开发摘要 (amg 268-269, acs 196)
- **c268 gap_redundancy_balance** (+19): unified health_score (0-100) + balance_ratio (-1,+1). Capstone of dual-loop.
- **c269 auto_consolidate** (+20): pairwise redundancy act-loop. merge_nodes() 5-step dedup fix.
- **acs c196 alert_threshold_sensitivity** (+21): threshold fragility via delta sweep.
- amg 3995→4034 (+39), acs 2763→2784 (+21).

### 07-18~19 开发摘要 (amg 266-267, acs 195, cf F46-48, nano F17-21)
- **c266 auto_heal_gaps** (+18): orphan rescue + bridge construction. Gap loop closed.
- **c267 redundancy_detect** (+32): 3D analysis (content/structural/functional).
- **acs c195 scorecard_ensemble** (+19): multi-preset consensus.
- **context-forge F46-48** (+44): code complexity + file coupling + tech debt.
- **nano-agent F17-21** (+44): search_fuzzy + group_by_tag + tools + dedup + chain_search.
- amg 3945→3995 (+50), acs 2744→2763 (+19).

### 07-17~18 开发摘要 (cycles 259-265, acs 194, atc F200)
- **7 cycles**: intent_aware_token_budgets + screen_retrieval (c259, +61) → govern_skill_bank (c260, +20) → 7-intent taxonomy (c261, +32) → query_route_audit (c262, +15) → reasoning_quality_eval (c263, +29) → graph_information_density (c264, +39) → knowledge_gap_report (c265, +28). amg 3721→3945 (+224). Evaluation quartet complete.
- **acs 194**: scorecard_preset_recommend + alert_prediction_tuned (+17)
- **atc F200** 🎯: 200 features (1280→1299)
- Blog: 自适应查询路由 + 记忆评估的五个新前沿
- Research #014: Self-Evolving Agent Memory. Insights #51-56.

### 近期研究一览 (详细笔记在 catalyst-research/exploration-notes/)
| 日期 | 主题 | 核心洞察 |
|------|------|----------|
| 07-24 | **Agent Memory Landscape npm Strategy (#026)** | Platform-vs-Library divide (all competitors are platforms)/Mem0 v3 ADD-only validates amg conflict resolution/Plugin ecosystem IS distribution channel (OpenClaw plugin missing)/Benchmark scores table stakes/PyPI-first strategy: Python home turf thinner competition ✅ |
| 07-24 | **Agentic Code Reasoning (#025)** | Semi-formal certificates (78→88% patch equiv)/RADAR production auto-review (105.9% YoY)/ProfMalPlus agent-coordinated static+dynamic/Structural retrieval > semantic/RADAR risk calibration = context-forge F59-F60 roadmap ✅ |
| 07-23 | **MCP SDK v2 Day-5 Integration (#024)** | Beta→stable zero-migration (factory correct)/Dual-era test gap (all tests auto-only)/cacheHints=3-line ROI/MRTR deferred Phase 2/Inspector=primary external test tool/SDK examples=CI self-verifying pairs ✅ |
| 07-21 | **MCP SDK v2 Day-1 Implementation (#022)** | Factory pattern mandatory/In-process testing handler.fetch/Resource subscriptions dual-era/.describe()=only model docs/ctx.mcpReq.log not console.log. Runnable Day-1 server+tests ✅ |
| 07-23 | **MCP SDK v2 Day-5 Integration (#024)** | Beta→stable zero-migration (factory correct)/Dual-era test gap (all tests auto-only)/cacheHints=3-line ROI/MRTR deferred Phase 2/Inspector=primary external test tool/SDK examples=CI self-verifying pairs ✅ |
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

> Pre-July research (06-07 ~ 06-30, 30+ entries): see [memory/archive-2026-07-early.md](memory/archive-2026-07-early.md)

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
93. **serveStdio takes a factory function, not a server instance (#022)** — The #1 Day-1 mistake: creating McpServer at module scope. `serveStdio(buildServer)` calls the factory internally; `createMcpHandler(buildServer)` does the same for HTTP. Factory pattern enables per-request isolation for HTTP transport and is mandatory for dual-transport support. Every official SDK v2 example uses this pattern.
94. **In-process testing via handler.fetch eliminates test infrastructure (#022)** — `createMcpHandler(buildServer)` returns a handler whose `.fetch` method can be passed directly as a transport's fetch option. No socket, no port, no process spawning. Tests run through the exact same code path as production, covering 2026-07-28 protocol features. This is the fastest test feedback loop for MCP server development — faster than MCP Inspector, faster than spawning stdio processes.
96. **Group-level batch consolidation is the natural completion of redundancy act-loop (c272)** — `auto_consolidate_cluster()` extends pairwise `auto_consolidate()` to entire clusters. Degree-sorted merge ensures highest-degree node survives all merges, maximising connectivity preservation. One API call replaces N-1 pairwise calls. Deterministic merge order (no random pair sequencing). Both redundancy loops now complete: pairwise (detect→act) + group (detect→act).
97. **Auto-recommended hysteresis bands close the fragility remediation trilogy (acs c198)** — c196 detects fragile thresholds (delta sweep). c197 provides manual hysteresis config. c198 computes optimal bands automatically from sensitivity data. Three strategies (safe_range/elasticity/volatility) cover conservative→aggressive tuning. Direction bias adjustment (asymmetric band widening) is uniquely intelligent — doesn't just compute symmetric ±width, understands WHICH direction the threshold is wrong. Non-mutating by default (apply=True to write). The prediction confidence stack is now: accuracy → tune → sensitivity → manual hysteresis → auto hysteresis.
98. **context-forge comprehensive code analysis suite complete (F49-F54)** — Six static analysis features: debug code detection, import graph (HITS hub/authority + circular deps), project maturity scorecard, security vulnerability scanner (CWE-tagged), error handling anti-patterns, duplicate code fingerprinting. 5005→6008 lines, 663→773 tests. context-forge is now a comprehensive code quality platform alongside amg (memory graphs) and acs (analytics).
99. **MCP Memory Server Phase 1 validates SDK v2 patterns from research #020-022 (amg-mcp Day 1-2)** — Factory pattern (buildServer) confirmed mandatory. Module-scope singleton required for stateless HTTP (MemoryGraph must survive across server instances). handler.fetch in-process testing works perfectly — no socket/port/spawn overhead. Resource subscriptions add `memory://graph` auto-refresh for clients. Zod v4 `.describe()` on every field is the difference between "LLM calls tool correctly" and "LLM has no idea". 6 curated tools wrapping 790+ amg APIs, 43 tests.
100. **Sombor index family extends degree-based metrics to Euclidean degree-distance quadrant (amg c276)** — Gutman 2021's SO = Σ√(d_u²+d_v²) is the Euclidean distance from origin in degree-degree plane. Reduced Sombor RS(K₂)=0 is unique among ALL degree-based indices — pure branching detector ignoring simple bonds. Neither multiplicative (Randić/Zagreb) nor harmonic (sum-connectivity/harmonic) families explore this quadrant. Cross-relationships: SO > χ_S, SO < M₂, RS ≤ SO. Degree-based family now 14 metrics across 8 APIs. First 2020s-era topological index added. 250th consecutive day milestone.
101. **Backtesting completes the analytics validation pipeline (acs c199)** — Without historical validation, band recommendations are unverified formulas. hysteresis_band_backtest() runs dual-evaluator replay (baseline vs hysteresis) over the same timeline. Key trade-off metric: delayed_detections (stability costs detection latency). Per-dimension breakdown reveals which dimensions benefit and which don't. Synthetic fallback (deterministic seed=42) enables zero-history estimation. The detect→configure→recommend→validate pipeline (c196-199) is now the most complete threshold management system in any npm analytics library.
102. **MCP dual transport is a factory pattern benefit, not an architecture decision (amg-mcp Day 4)** — HTTP transport required only ~60 lines of adapter code (Web API Request/Response ↔ Node IncomingMessage/ServerResponse). The factory pattern from Day 1 (buildServer) made this trivial: same tools, same schemas, same MemoryGraph singleton. HTTP mode enables remote clients (Claude Desktop, Cursor) connecting over network. stdio mode for local CLI. The ~60-line adapter proves SDK v2's factory design is correct — dual transport is emergent, not engineered.
103. **detect_skill_candidates() is the foundation for Experience Compression Spectrum (#041-043, #078) (amg c275)** — Scanning episodic nodes for action-verb patterns is step 1 of L0→L1→L2 promotion. 25 action verbs (created/tested/deployed/etc.) grouped with frequency/confidence. Confidence saturates at 5 occurrences (min(1.0, freq/5.0)). This is the detection layer; compress_to_skill() will be the act layer. The "missing diagonal" (cross-level compression) value proposition becomes tangible: each skill candidate is a quantified promotion opportunity from episodic memory to procedural memory.
104. **Dual-era testing is the missing coverage in amg-mcp (#024)** — All 93 tests use `versionNegotiation: { mode: 'auto' }` (2026-era). Production clients (Claude Desktop, Cursor) still use 2025-era `initialize` handshake. Official SDK runs every example over BOTH eras in CI. A single `mode: 'legacy'` test catches era-specific bugs (resource subscriptions, session-based listChanged). ~30 lines to add, shipping without it = testing blind on the protocol real users are on.
105. **cacheHints is the highest ROI Day-5 change (#024)** — Adding `cacheHints: { 'tools/list': { ttlMs: 86400000, cacheScope: 'public' } }` to McpServer constructor is 3 lines. Clients skip redundant tools/list for 24h. For 11 tools with outputSchema, saves ~4KB per connection. 2026-07-28 spec models this on HTTP Cache-Control. Zero complexity, immediate measurable benefit.
106. **MRTR is Phase 2, not Phase 1 (#024)** — memory.forget's `destructiveHint: true` annotation triggers client-side confirmation UI (Claude Desktop, Cursor). MRTR adds server-side HMAC-sealed confirmation with `createRequestStateCodec` (~40 lines). Useful for multi-step auth flows but adds complexity. Decision: Phase 1 = annotation-based, Phase 2 = MRTR for multi-step workflows (e.g., scoped batch forget).
107. **Triple-loop quality system is the complete paradigm (amg c264-277)** — Gap loop (report→auto_heal) + Redundancy loop (detect→auto_consolidate) + Skill loop (detect_candidates→auto_compress_skills). Three failure modes of knowledge graphs — missing connections, excess connections, unpromoted patterns — each with detect→act. This three-loop architecture has zero npm competitors and is the strongest positioning statement for amg.
108. **Dimension correlation is analytics' redundancy detection (acs c200)** — scorecard_dimension_correlation() does for analytics what redundancy_detect() did for graphs: identifies which components measure the same underlying signal. Pearson r across presets, classification (redundant/independent/complementary), merge suggestions. Capstone of scorecard layer: c192 define → c195 ensemble → c200 correlate. 200th consecutive day milestone 🏆.
109. **All major agent memory competitors are platforms, not libraries (#026 2026.07)** — Mem0/Zep/Supermemory/Cognee/Letta all require external services (API, graph DB, Docker, managed platform). amg is the only zero-dependency embeddable library. Positioning: "pip install, import, done." Mem0 v3's ADD-only pivot (removed UPDATE/DELETE) explicitly validates amg's conflict resolution advantage. Plugin ecosystem (OpenClaw/Claude Code) IS the distribution channel — amg needs an OpenClaw plugin. PyPI-first strategy: Python ecosystem has thinner competition than npm.
110. **Degree-based entropy family completion is a structural analysis milestone (amg c278-280)** — All 5 major degree-based indices (Sombor/RS/Randić/Zagreb M₁/ABC/GA) now have index+entropy = 10 APIs. Key finding: Shannon entropy is dominated by count/proportion of distinct edge contributions, not the formula. ABC entropy uniquely filters K₂ edges. The 10-API toolkit enables entropy fingerprinting. No npm library has any topological index entropy.

---

## Active Next Actions

### 🔴 最高优先级: npm Publish
- [ ] **agent-memory-graph: README + npm publish** — **4394 tests**, 810+ APIs
- [ ] **agent-context-store: README + npm publish** — **2898 tests**, 600+ APIs
- [ ] **structured-output-toolkit: README + npm publish** — **571 tests**
- [ ] **agent-task-cli: README + npm publish** — **1319 tests**, F203

> ⚠️ Mandol (ISCAS+MSRA) 已发 paper+PyPI+GitHub，LoCoMo SOTA 92.21%。PlugMem 已有 OpenClaw plugin。竞争窗口收紧。**9047 tests across 4 projects, all npm ready.**

### 🟡 研究驱动 — 待实现 (Research #026 新增)
- [ ] amg: OpenClaw plugin — Supermemory + Cognee both have one. amg is invisible to fastest-growing user segment without it. Lifecycle hooks (SessionStart/PostToolUse/SessionEnd). ~200 lines.
- [ ] amg README: Competitive matrix (Platform-vs-Library, zero-dep differentiator, ADD-only vs consolidation). Lead with "pip install, import, done."
- [ ] amg PyPI publish (Python-first strategy: thinner competition than npm)

### 🟡 研究驱动 — 待实现 (Research #025 新增)
- [ ] context-forge F59: `SemiFormalCertificateBuilder` — Wrap F52 (security) output as premises, generate traces from F50 import graph. Certificate.report() + Certificate.toJSON(). ~60 tests, +200 lines. Makes F52 output 10× more actionable.
- [ ] context-forge F60: `complexity-assessment` certificate — Wraps F49/F51/F54 as premises. Risk-calibrated review routing (RADAR pattern). ~40 tests.
- [ ] amg-mcp: `code.analyze` tool wrapping context-forge certificate engine — First MCP server with semi-formal code reasoning. `destructiveHint: false`, `readOnlyHint: true`.

### 🟡 研究驱动 — 待实现 (Research #018 新增)
- [ ] amg: add `kind="repair_pattern"` node type — AgentTether-inspired cross-iteration repair memory. ~20 lines + ~40 tests. Connects prospective memory roadmap.
- [ ] amg: cross-modal leak detection in write_governance_check — MemLeak-inspired. Scan image_derived/correlated_inference edges before forget(). ~60 lines + ~80 tests.

### 🟡 研究驱动 — 待实现 (existing)
- [ ] amg: compress_to_skill() + retrieve_skills() + evolve_skill() + skill_bank_health() — Read-Write-Assess-Govern lifecycle (MemRefine + MemSkill + #019). ~+140 tests. **Implementation blueprint ready in #019**: Cycle 268 compress_to_skill (~40 tests), Cycle 269 retrieve_skills+evolve_skill (~40 tests), Cycle 270 skill_bank_health (~35 tests). Self-created skills > human-authored (MUSE 85.24% vs 81.17%). **No npm library has skill extraction/evolution/health.**
- [ ] amg: EvoMemBench adapter — 4-setting benchmark (in-ep/cross-ep × knowledge/exec). **Priority over LoCoMo** (#014)
- [ ] amg: three_layer_router_cascade — rules→SLM→keywords fallback. MemFlow #015. ~+40 tests
- [ ] amg: intent_aware_edge_cost() — PRISM intent routing (#010). ~+40 tests
- [ ] amg: procedural memory node type — PlugMem prescriptive knowledge (#010). ~+50 tests
- [x] ✅ amg: auto_heal_gaps() — Cycle 266 (done, 4-strategy self-healing already implemented)
- [ ] LoCoMo benchmark adapter + full-context baseline reporting
- [ ] **amg README: 竞品对比表** — Mem0/Zep/Mandol/PlugMem/PRISM/Hippocampus + **GraphRAG/LightRAG positioning: security-first agent-native GraphRAG**

### 🟣 Deep Research (detailed notes in catalyst-research/exploration-notes/)
- **#026 (07-24)**: Competitive landscape for npm/PyPI. All competitors (Mem0/Graphiti/Supermemory/Cognee/Letta) are platforms, none is a pure library. Mem0 v3 ADD-only = amg conflict advantage. Plugin ecosystem = distribution. PyPI-first strategy. [笔记](catalyst-research/exploration-notes/2026-07-24-agent-memory-landscape-npm-strategy.md)
- **#025 (07-24)**: Semi-formal reasoning certificates (Ugare & Chandra Meta) / RADAR production auto-review 105.9% YoY / ProfMalPlus agent static+dynamic / Structural retrieval > semantic / Neuro-symbolic triangle (static→generate→test) / context-forge F59-F60 roadmap. [笔记](catalyst-research/exploration-notes/2026-07-24-agentic-code-reasoning.md)
- **#015 (07-17)**: MemFlow 7-intent routing / GraphBit DAG isolation / GhostWriter 98% injection → amg security validation. [笔记](catalyst-research/exploration-notes/2026-07-17-intent-driven-memory-orchestration.md)
- **#016 (07-18)**: EvoGraph-R1 GraphEdit MDP / HealthClaw induction / Local self-healing 90% / Topology-aware degree≥3. [笔记](catalyst-research/exploration-notes/2026-07-18-self-healing-knowledge-graphs.md)
- **#021 (07-20)**: Official MCP server ~500 lines JSONL=low bar / Resource subscriptions critical / Tool annotations=governance / outputSchema mandatory / Inspector-first dev. [笔记](catalyst-research/exploration-notes/2026-07-20-mcp-memory-server-source-analysis.md)

### 🔵 中优先级
- [ ] openclaw-langgraph-bridge: Supervisor 完善 (261 tests)
- [ ] lab/a2a-trust-prototype: TrustEngineV2 (7算法)
- [ ] lab/agent-observability: gen_ai.* + CostAggregator (研究完成 ✅)
- [ ] AMS 生产化: EmbeddingProvider 接入
- [ ] **MCP Memory Server: agent-memory-graph-mcp** — 研究完成 ✅ #017 + #020 + #021 + #022 (Day-1 implementation patterns). 8 curated tools, v2-native (stateless, outputSchema, resource subscriptions, handler.fetch testing). ~500 lines TypeScript. MCP Registry has ZERO graph memory servers. SDK v2 stable July 28 = timing window. **Phase 1: TS wrapper (July 21-25) — Day-1 code in #022, blueprint in #021. Phase 2: Registry publish (July 28) ride v2 stable**

### 待评估
- [ ] Agentic evaluation suite (MemoryBenchmarkHarness)
- [ ] README 定位升级: "Bridge between production and research agent memory"
- [ ] TrustEngineV2: 实现 lab/a2a-trust-prototype (~300行src+200行tests), 7算法已研究+代码已验证

---

## Core Projects Quick Reference

| # | 项目 | Tests | 状态 |
|---|------|-------|------|
| 1 | agent-task-cli | 1319 | ✅ npm ready, F203 (203 features) |
| 2 | agent-memory-graph | 4394 | ✅ npm ready, 七十七合一: degree-based entropy family (5 indices / 10 APIs) + triple-loop quality + MCP Day 1-5 |
| 3 | agent-context-store | 2898 | ✅ npm ready, 二十六层: detect→configure→recommend→validate→correlate complete |
| 4 | structured-output-toolkit | 561 | ✅ npm ready |
| 5 | openclaw-langgraph-bridge | 261 | 🔄 Supervisor 完善 |
| 6 | context-forge | **1054** | ✅ F66 code smells (8684 lines, 18 dimensions) |
| 7 | lab/agent-observability | 166 | 🔄 OTel GenAI 对齐 (Research #023 ✅) |
| 8 | nano-agent | 732 | 🔄 F46 to_prompt |
| 9 | Agent Memory Service | 645 | ✅ v1.0-dev |
| 10 | prompt-router | 72 | ✅ stable (corrected from stale 258) |
| 11 | prompt-weaver | **223** | ✅ CLI tests added |
| 12 | better-ralph-core | 376 | ✅ 稳定 |
| 13 | **amg-mcp** | **122** | ✅ Phase 1 Day 1-5 (14 tools, dual transport, dual-era verified) |

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
- [x] **MCP Memory Server Phase 1 Day 5**: ✅ Cross-era integration tests (93→122). Legacy↔Auto persistence, all 14 tools, outputSchema consistency. Research #024 action items completed.
- [ ] README(agent-memory-graph) → npm publish — **#1 priority**. **4394 tests**, 810+ APIs.
- [ ] README(agent-context-store) → npm publish — **2898 tests**.

### Short-term (August)
- [ ] Implement `get_operation_history()` API in amg (MemOps-compatible operation traces)
- [ ] Run EvoMemBench InEp-Know setting against amg (Research #022 adapter skeleton ready)
- [ ] Add long-context baseline to amg evaluation suite
- [ ] README(agent-context-store) → npm publish

### Medium-term (September)
- [ ] Full EvoMemBench 4-setting evaluation suite for amg
- [ ] compress_to_skill() + retrieve_skills() + evolve_skill() (blueprint ready: cycles 270-272; Research #024 ✅ 07-23: verify_skill + prune_low_utility_skills + skill_to_artifact pipeline designed, Skill-Pro PPO Gate + D2Skill dual-granularity + COLLEAGUE.SKILL artifact contract)
- [ ] MemOps-style operation-level probes (6 failure mode categories)
- [ ] Watch for MemOps code release (not yet public as of July 14)

### 重要框架
- **A2A协议** — Agent间"HTTP", 150+组织, Linux Foundation AAIF
- **MCP协议** — Agent的"USB接口", 97M+下载, 工具访问标准
- **memorywire** — 5 ops × 4 types, 计划 MCP-WG + IETF at v0.5
