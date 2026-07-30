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

## Current Focus (2026-07-30)

### Active Theme
Autoresearch 方法论实践 — amg **连续271天零回滚率** 🏆。Entropy framework **28+ APIs**: 7 degree-based Shannon + 3 spectral (von Neumann, QJSD, spectral_divergence) + 1 dashboard + 2 generalized (Tsallis, Rényi) + 4 inter-graph (JSD, cross-entropy, KL divergence, QJSD) + TemporalEntropyTracker + **entropy_contribution** (leave-one-out node importance) + **entropy_stability** (Monte Carlo perturbation robustness) + **spectral_divergence_scan** (multi-resolution analysis) + **entropy_fingerprint** (12+ dim feature vector) + **fingerprint_distance** (L2 vector comparison) + **spectral_classification** (3-method reference graph classification) + **classification_with_rejection** (threshold-based reject/accept layer) + **three_layer_router_cascade** (MemFlow production pattern)。Adaptive forgetting suite complete。EntityResolver + entropy-weighted retrieval。Information-theoretic trilogy complete (JSD + CE + KL)。Triple-loop quality system complete。acs **200天** 🏆。context-forge **1346 tests** / 11000+ lines (F79, 21 dimensions)。Research #031-036: Spectral methods + Production architecture + Agent Memory Engineering 2026H2 + OTel GenAI Alignment + A2A Trust Engine V2 + Graph Classification & Entropy Fingerprinting.

### 项目测试总量 (07-30 快照)
| 项目 | Tests | APIs | 状态 |
|------|-------|------|------|
| agent-memory-graph | **5807** | 896+ | 八十合一: entropy framework (28+ APIs incl. spectral + inter-graph trilogy + contribution + stability + spectral_divergence + scan + fingerprint + classification + classification_with_rejection) + adaptive forgetting suite (6 APIs) + EntityResolver (8 APIs) + entropy-weighted retrieval + entropy-guided routing + **three_layer_router_cascade** + triple-loop quality + MCP Day 1-5 |
| structured-output-toolkit | **561** | 4650+ lines | generation+validation+consensus+recovery+scoring+monitoring+versioning+cross-provider |
| agent-task-cli | **1340** | 214 features | Cache+Storage+EventBus+ConcurrencyManager+merge — **F214** (emitSeries rename + mset/intersect/emitWithDelay) |
| **四项目总计** | **10606** | — | — |

其他: context-forge **1346** (F79, 11000+ lines, 21 dimensions) / nano-agent 732 / amg-mcp **122** / prompt-weaver 223 / openclaw-langgraph-bridge 261 / better-ralph-core 376 / lab/agent-observability 166 / AMS v1.0-dev 645 / prompt-router 72 / edge-agent-runtime 244 / agent-mesh-network **158** (+50)

**全项目总计**: 14851 tests (四核心 10606 + cf 1346 + nano 732 + mcp 122 + pw 223 + lg-bridge 261 + ralph 376 + observability 166 + AMS 645 + router 72 + edge 244 + mesh 158)

### 最高优先级
**README → npm publish** (四项目)。MCP Phase 1 Day 5 ✅ (cross-era verified, 122 tests)。amg 定位: "agency-grade graph memory for self-evolving agents"。10606 tests across 4 projects, 全部 npm ready。⚠️ Mandol (LoCoMo SOTA 92.21%) 已在 paper+PyPI+GitHub，PlugMem 已有 OpenClaw plugin，竞争窗口收紧。**Entropy-weighted forgetting + retrieval = two publishable contributions** (no competitor uses graph entropy for either signal)。**Information-theoretic trilogy** (JSD + CE + KL) = novel graph comparison suite。**Entropy contribution + stability** = node-level importance and robustness analysis。**Spectral divergence + scan** = multi-resolution inter-graph comparison。**Entropy fingerprint + spectral classification** = graph identification via 12+ dim feature vectors。**Three-layer router cascade** = MemFlow production pattern (rules→entropy→fallback).

### 早期 Cycle 归档 (07-01 ~ 07-16)
> 详细记录已归档至 [memory/archive-2026-07-early.md](memory/archive-2026-07-early.md)。以下仅保留里程碑摘要：

- **07-14 cycles 239-242**: immutable_store + compact_node + serialize + RelationIntegrityChecker. Context Engineering Layer 3/4 ✅. +145 tests
- **07-14 Research #008**: Memory Security — ShadowMerge 93.8% ASR, amg positioning 

### 07-30 开发 (amg c320)
- **Cycle 320: classification_with_rejection()** — Production-safe rejection layer for any classification result. Dual criteria (score threshold + min margin). Exact match always accepted. Calibrated confidence rescale to [0,1]. Works with graph_classification + spectral_classification + hybrid_classification. Completes classify→reject/accept pipeline. +40 tests, 5767→5807. **271st day**. 6320eff.

### 07-29 开发 (amg c308-318, atc F204-F214, mesh, essay)
- **Cycle 318: spectral_classification()** — Multi-method reference graph classification. 3 methods (spectral/spectral_scan/fingerprint). Returns best_match + rankings + confidence + margin. Complements degree-based graph_classification(). +38 tests, 5681→5719. **270th day**. 50d7cea.
- **Cycle 317: three_layer_router_cascade()** — MemFlow production pattern: Layer 1 rules (~0ms) → Layer 2 entropy-guided (~1-5ms) → Layer 3 fallback. Full cascade_trace with per-layer latency. +36 tests, 5645→5681. **269th day**. e1d6c59.
- **Cycles 310-316**: entropy_fingerprint() (12+ dim feature vector) + fingerprint_distance() (L2) + graph_classification() (degree-based) + intermediate cycles. ~174 tests.
- **Cycle 309: spectral_divergence_scan()** — Multi-resolution spectral divergence. Fibonacci bins [2,3,5,8,13,21,34,55]. +63 tests, 5408→5471. **268th day**. aa2822f.
- **Cycle 308: spectral_divergence()** — Histogram-based JSD/KL/CE between Laplacian eigenvalue distributions. Size-invariant. +54 tests, 5354→5408. **267th day**. cfb3a82.
- **agent-task-cli Round 55**: F211 emitBatch bug fix (renamed emitSeries) + F212 Cache.mset + F213 Storage.intersect + F214 EventBus.emitWithDelay. +21 tests (4 pre-existing failures fixed). 82087b4.
- **agent-mesh-network**: TaskBid/TaskResult/priority/serialization/MeshNode tests. +50 tests (108→158).
- **Essay**: "节点的信息论价值" — Leave-One-Out 熵贡献度识别记忆图关键节点. ~3000字, 2 Python 示例. [链接](https://robertsong2019.github.io/posts/entropy-contribution-critical-nodes-2026-07.html). f4e14f1.

### 07-28 开发 (amg c300-307, Research #033)
- **Cycle 307: entropy_stability()** — Monte Carlo entropy variance under random edge perturbation. remove/rewire modes, stability_score=1-CV, 7 indices, seedable. +47 tests, 5307→5354. **266th day**. 5780e3e.
- **Cycle 306: entropy_contribution()** — Leave-one-out marginal entropy contribution per node. ΔH_v=|H(G)−H(G−v)|. 7 indices, O(n·m) cached degree vectors, critical vs expendable node classification. +20 tests, 5287→5307. **265th day**. c064b04.
- **Cycles 300-305**: +95 tests (5192→5287). Details not logged — experiments.tsv phantom (15th occurrence). API count grew from 870+ to 880+.

### 07-27~28 开发 (amg c292-299, Research #031-032)
- **Cycle 299: kl_divergence_graph()** — KL(P‖Q) relative entropy between graphs. Completes information-theoretic trilogy: JSD (symmetric) + CE (asymmetric cost) + KL (asymmetric information gain). Non-negative, asymmetric, not a true metric. +45 tests, 5147→5192. **263rd day**. 262de7b.
- **Cycle 298: cross_entropy_graph()** — First asymmetric inter-graph measure. H(P,Q) = encoding cost of P using Q's code. Gibbs' inequality verified. Complements JSD with directionality. +38 tests, 5109→5147. **262nd day**. 461848a.
- **Cycles 292-295: Spectral entropy suite** — von_neumann_entropy() (first spectral entropy, H=ln(n-1) for K_n) + spectral_entropy_profile() (10-metric dashboard) + TemporalEntropyTracker (phase transition detection: growth/consolidation/forgetting/transition) + quantum_jensen_shannon_distance() (spectral inter-graph true metric) + entropy_profile() spectral extension. +117 tests, 4951→5068. **262nd day**.
- **Cycle 296: EntityResolver** — 8 APIs (register_alias/resolve_alias/list_aliases/remove_alias/suggest_duplicates/merge_entities/resolve_or_add/auto_resolve_check). Fills Research #032's #1 competitive gap. +30 tests, 5068→5098.
- **Cycle 297: entropy_weighted_retrieval()** — Blends BM25 similarity with per-node entropy weight. Novel differentiator — no competitor uses entropy for retrieval. +11 tests, 5098→5109.
- **Research #032** — Production Agent Memory Architecture: Mem0 v3 ADD-only (3x latency ↓), entity resolution = table stakes, bi-temporal tracking, entropy as retrieval signal. amg now has all 3 critical gaps filled.

### 07-26~27 开发 (amg c283-288, cf F79, Research #029-030)
- **Cycle 288: renyi_entropy() + entropy_distance()** — Rényi generalized entropy (extensive, α→1=Shannon, α=2=collision, α→∞=min-entropy). Jensen-Shannon divergence between two graphs (symmetric, bounded [0,1], triangle inequality). First inter-graph comparison method. Entropy toolkit = 16 APIs. +77 tests, 4825→4902. **260th day**. d4c8fbd.
- **Cycle 287: entropy_guided_query_route()** — Entropy-aware retrieval: high entropy (uniform) → basic mode, low entropy (heterogeneous) → drift mode. 8 selectable indices. override_heuristic parameter. +52 tests, 4693→4745. **256th day**. 4792815.
- **Cycles 283-286: Adaptive Forgetting Suite** — compute_activation() (entropy-weighted) + apply_decay() + forget_policy() (FSFM 4-category taxonomy) + soft_forget() + cue_reactivation() (Oblivion pattern) + security_purge() (irreversible safety deletion). +110 tests, 4583→4693. 256th-259th days.
- **context-forge F79**: analyzeDeadCode() — unreachable code, always-false branches, commented-out blocks, unused privates. 1326→1346 (+20 tests), 10812→11000+ lines, 21 dimensions.
- **Research #029** — Multi-Agent Orchestration 2026: 41-87% production failures from coordination defects (not model weakness). LAMaS learned orchestration -38-46% latency. Arbor tree search = shared memory (193% improvement). LangGraph 38% production share. Insights #119-120.
- **Research #030** — Adaptive Forgetting: FSFM 4-category taxonomy, FadeMem 45% storage ↓, Oblivion cue-reactivation > hard delete, MemFactory RL framework. **Entropy as forgetting signal = novel, no competitor does this**. 2 runnable code examples.

### 07-25~26 开发 (amg cycles 281-282, cf F67-F78, Research #027-028)
- **Cycle 282: augmented_zagreb_entropy() + edge_betweenness_entropy()** — AZI cubic (P_n AZI=8 unique). First centrality-based entropy. 14 APIs. +93 tests, 4479→4572. **255th day**.
- **Cycle 281: entropy_profile() + tsallis_entropy()** — Dashboard + generalized (Tsallis). +85 tests, 4394→4479. **254th day**.
- **context-forge F67-F78** — 12 features. 1054→1326 (+272 tests), 18→20 dimensions.
- **Research #027-028** — TrustEngineV2 (7 algorithms) + Agent Planning (VRR-Stop, RLAW).
- **Blog** — Episodic-to-skill pipeline essay (~2800 words).

### 07-24~25 开发 (amg c279-280, cf F59-F66, autoresearch)
- **c280**: abc_entropy() + ga_entropy() (+68, 4326→4394). **c279**: randic_entropy() + zagreb_m1_entropy() (+57, 4269→4326). Degree-based entropy family 5 indices complete.
- **cf F59-F66**: 8 analysis features (CLI/deps/test-cov/logging/env/perf/type-safety/code-smells). 856→1054 (+198), 7001→8684 lines.
- **autoresearch**: micro-agent-protocol 88→101, prompt-router 35→72.

### 07-23~24 开发 (amg c277-278, acs c200, cf F56-F58, amg-mcp Day 5)
- **c278**: sombor_entropy() + reduced_sombor_entropy() (+46). **c277**: auto_compress_skills() — triple-loop quality complete (+18). amg 4205→4269.
- **acs c200**: scorecard_dimension_correlation() (+34, 2864→2898). **200th day** 🏆.
- **cf F56-F58**: async/export/function metrics (+70, 786→856).
- **amg-mcp Day 5**: cross-era integration (93→122). **prompt-weaver**: CLI tests (184→223).
- **Research #024**: MCP SDK v2 Day-5 patterns.

### 07-17~22 开发归档 (详细记录在 memory/ 日志)
- **amg c259-276**: 18 cycles. 关键: query_explain · semantic_cluster_detect · auto_consolidate_cluster · auto_heal_gaps · redundancy_detect · gap_redundancy_balance · knowledge_gap_report · graph_information_density · reasoning_quality_eval · 7-intent taxonomy · govern_skill_bank · auto_compress_skills · sombor_index/entropy · detect_skill_candidates · walk_statistics. amg 3721→4205 (+484). Evaluation quartet + dual-loop quality + triple-loop complete.
- **acs c194-199**: 6 cycles. 关键: scorecard_preset_recommend · alert_prediction_tuned · alert_threshold_sensitivity · threshold_hysteresis_config · hysteresis_band_recommender · hysteresis_band_backtest. acs 2744→2898 (+154). detect→configure→recommend→validate pipeline complete.
- **cf F46-F58**: 13 features (complexity/coupling/tech-debt/debug/import-graph/maturity/security/error/duplicate/async/export/function-metrics/comments). 663→856 (+193).
- **nano-agent F17-F46**: 30 features (+316, 416→732).
- **amg-mcp Day 1-5**: MCP Phase 1 complete (43→122 tests, 14 tools, dual transport, dual-era verified).
- **atc F197-F203**: 7 features, F200 🎯 milestone.
- **Research #014-024**: 11 deep research notes.

### 近期研究一览 (详细笔记在 catalyst-research/exploration-notes/)
| 日期 | 主题 | 核心洞察 |
|------|------|----------|
| 07-28 | **Agent Memory Engineering 2026H2 (#033)** | Engram bi-temporal 83.6% vs 73.2% full-context (+10.4pp)/Dual-process System-1/System-2 = production architecture (hot append + async consolidate)/H-Mem hybrid tree+graph = SOTA on 3 benchmarks/Memanto info-theoretic retrieval validates amg entropy approach/MAGE four-subgraph for multi-agent/Benchmark harness = competitive weapon. 2 runnable code examples ✅ |
| 07-27 | **Production Agent Memory Architecture (#032)** | Mem0 v3 ADD-only: 3x latency ↓ + higher accuracy (dropped UPDATE/DELETE)/Entity resolution = table stakes (both Mem0 + Graphiti have it)/Bi-temporal tracking = Graphiti moat (valid_from/valid_to)/Entropy as retrieval signal = amg unique advantage/LTM pipeline: encode→store→retrieve→forget. 1 runnable code example ✅ |
| 07-27 | **Temporal Graph Entropy & Spectral Methods (#031)** | Von Neumann graph entropy = first spectral entropy (Laplacian eigenvalue Shannon)/K_n maximizes: H=log(n-1), opposite of degree-entropy/Temporal entropy trajectory = novel health metric for agent memory (phase transition detection)/QJSD between density matrices > combinatorial JSD for graph comparison/**IMPLEMENTED**: c292-295 (+117 tests). 3 runnable code examples ✅ |
| 07-27 | **Rényi Entropy + Graph Distance (c288)** | Rényi generalized entropy (extensive, α-parameterized) completes Tsallis+Rényi pair/entropy_distance() JSD = first inter-graph method/sqrt(JSD) is a true metric/triangle inequality verified ✅ |
| 07-29 | **Spectral Divergence & Multi-Resolution Scan (c308-309)** | Histogram-based eigenvalue binning = size-invariant graph comparison/Fibonacci resolution sweep reveals structural scale of divergence/Convergence detection (CV<0.05) tells when enough resolution/Spectral toolkit now 3 methods: quantum JSD + spectral divergence + scan ✅ |
| 07-26 | **Adaptive Forgetting & Memory Pruning (#030)** | Entropy as forgetting signal = novel (no competitor does this)/FSFM 4-category taxonomy maps to amg/FadeMem 45% storage ↓ via consolidation not deletion/Oblivion: cue-reactivated soft forgetting > hard delete/MemFactory: RL training framework (Apache 2.0, Neo4j+Milvus). 2 runnable code examples ✅ |
| 07-26 | **Multi-Agent Orchestration 2026 (#029)** | Coordination defects cause 41-87% production failures (not model weakness)/LAMaS: learned orchestration 38-46% latency reduction via parallel critical path optimization/Arbor: tree search as shared cognition layer (193% improvement, single agent crashes in hours)/LangGraph 38% production share, but 28% still custom/LangSmith observability = primary differentiator/Transparency paradox: more agents = more surface but more emergent opacity. 3 runnable code examples ✅ |
| 07-25 | **Agent Planning & Reasoning (#028)** | VRR-Stop: 60.6pp via adaptive stopping (4-param noise model)/SkillComposer: constrained autoregressive skill composition (+23.1pp GPT-5.2-Codex)/RLAW: POMDP+GAT+Critic 78.6% vs ReAct 54.1%/Entropy-guided branching for long-horizon/PlanFlip: planning-phase attack surface. 3 runnable code examples ✅ |
| 07-29 | **Graph Classification & Entropy Fingerprinting (#036)** | Rényi order α = resolution parameter for graph structure/Entropy curve SHAPE = fingerprint (not scalar)/Ego-local VNEstruct > global entropy for node tasks/TIDE tri-component decomposition (feature×structure×joint)/PRI formalizes entropy-guided forgetting as optimization/FGN continuous entropy fields (June 2026). 2 runnable code examples ✅ |
| 07-29 | **A2A Trust Engine V2 (#035)** | Beta-Bayesian > linear scoring (Wilson LB = conservative trust)/A2A Agent Cards = perfect trust anchor (signed identity + capabilities)/EigenTrust propagation needs hop decay (0.5/hop)/SimHash catches adversarial patterns behavioral metrics miss/Risk-stratified gates map to A2A enterprise security model. 12/12 tests ✅ |
| 07-25 | **Agent Trust & Safety (#027)** | Ontological dissociativity kills reputation (FAccT)/Per-component SimHash 0.974 AUC/Pre-execution gating > static policy (ScopeJudge F1=0.78)/Distributed attacks defeat per-instance monitors/7 algorithms for TrustEngineV2 ✅ |
| 07-25 | **Agent Memory Landscape npm Strategy (#026)** | Platform-vs-Library divide (all competitors are platforms)/Mem0 v3 ADD-only validates amg conflict resolution/Plugin ecosystem IS distribution channel (OpenClaw plugin missing)/Benchmark scores table stakes/PyPI-first strategy: Python home turf thinner competition ✅ |
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

> **#1-55 archived** to [memory/archive-insights-001-055.md](memory/archive-insights-001-055.md). Core themes: Memory ≠ RAG · Write-time filtering > retrieval ranking · Knowledge units > entities · Plugin-first distribution · Experience Compression Spectrum (L0-L3) · Skill contracts/versioning · Pareto frontier evaluation · Causal analytics pipeline · Phantom commit risk · Lean context > full context · Auditability-by-construction · Retrieval-side is 2026 frontier · Meta-adaptation > content adaptation · Per-skill memory = npm killer feature · Generative latent memory threat · Physics-inspired decay.

57. **Knowledge gap detection closes the measure→diagnose→act loop (amg c265)** — knowledge_gap_report() identifies orphans, clusters, bridges, hubs. gap_score 0-100.
58. **Prediction auto-tuning closes analytics pipeline (acs c194)** — recommend→apply→measure→tune = self-optimizing.
59. **Evaluation quartet is competitive moat** — No npm memory library has retrieval_quality_eval + lifecycle_operation_eval + reasoning_quality_eval + graph_information_density + knowledge_gap_report.
60. **Self-healing graphs: local heuristics + confidence-gated autonomy (#016)** — 4 strategies (orphan_adoption/bridge_construction/hub_enrichment/duplicate_link). First npm lib with detect→heal→measure→audit.
61. **MCP Registry has ZERO graph memory servers (#017)** — amg-mcp would be first in MCP ecosystem.
62. **MCP tool annotations = governance surface (#017)** — readOnly/destructive hints enforce governance at protocol level.
63. **Tool count is critical UX constraint (#017)** — 8-12 curated tools, not 760+ APIs.
64. **Dual-loop quality management = complete paradigm (c264-267)** — Gap (missing) + Redundancy (excess) = both failure modes covered.
65. **Multi-preset ensemble = cross-validation for store health (acs c195)** — Fragile dimensions have high preset-spread.
66-70. **TypeScript moat + Graph > Filesystem + Git-as-memory** (#018) — npm ZERO TS-native graph memory libs. Graphs express M:N. Git gives persistence, amg adds governance+quality.
71-78. **Compression + Skills lifecycle (#019)** — compress_to_skill() completes dual-loop. Q-value bridges retrieval+evolution. "Missing diagonal" (L0→L3 full-spectrum) = unique value prop.
79. **Dual-loop quality FULLY complete (c268-269)** — auto_consolidate() exposed merge_nodes() bug (UNIQUE violations). 5-step dedup fix benefits all merges.
80. **Threshold sensitivity = confidence layer (acs c196)** — accuracy→tune→sensitivity audit. Direction_bias tells you WHICH way to adjust.
81-90. **MCP SDK v2 patterns (#020-022, #024)** — Stateless=SQLite match · outputSchema typed JSON · factory pattern mandatory · handler.fetch in-process testing · resource subscriptions critical · dual-era testing gap · cacheHints 3-line ROI · MRTR=Phase 2 · official server bar is low · Inspector=primary dev tool.
91-97. **Group redundancy + hysteresis trilogy (c271-272, c197-199)** — semantic_cluster_detect (Union-Find) · auto_consolidate_cluster · detect→configure→recommend→validate pipeline complete with backtesting.
98. **context-forge comprehensive code analysis (F49-F54)** — 6 static analysis features. Now a code quality platform.
99. **MCP Phase 1 validates SDK v2 (Day 1-2)** — Factory pattern confirmed. Zod .describe() = LLM tool-call quality.
100-103. **Sombor index + backtesting + skill candidates + dual-era** — Sombor Euclidean quadrant · hysteresis_band_backtest · detect_skill_candidates (L0→L2 promotion foundation).
104-106. **amg-mcp Day 5: cacheHints + MRTR deferred** — 3-line ROI. Phase 2 for multi-step workflows.
107. **Triple-loop quality system = complete paradigm (c264-277)** — Gap + Redundancy + Skill loops. Zero npm competitors.
108. **Dimension correlation = analytics' redundancy detection (acs c200)** — Pearson r across presets. 200th day 🏆.
109. **All competitors are platforms, not libraries (#026)** — amg = only zero-dep embeddable library. PyPI-first strategy.
110. **Degree-based entropy family complete (c278-280)** — 10 APIs, 5 indices. Shannon entropy dominated by count of distinct contributions.
112-115. **Agent trust: dissociative identity + SimHash + pre-execution gating + distributed attacks (#027)** — Reputation can't work. Shift to behavioral harnesses.
116-117. **Entropy dashboard + Tsallis + centrality-based entropy (c281-282)** — 14 APIs across 7 indices + 1 structural + 1 dashboard + 1 generalized. AZI entropy=1.0 on all paths (novel). edge_betweenness = first global topology entropy.
118. **Pre-execution gating = shift from reputation to behavioral harnesses (#027)** — ScopeJudge static recall ~0. Per-component SimHash AUC 0.974.
119. **Coordination defects (not model weakness) cause 41-87% multi-agent production failures (#029)** — Framework choice is 4th priority after model selection, evaluation infra, and human-checkpoint design. Coordination should be a separable architectural layer.
120. **Tree search = shared memory substrate, not just planning (Arbor #029)** — 193% improvement via Orchestrator+Critic with explicit search tree as shared working memory. Single agents crash irrecoverably within hours without the harness. amg graph IS the search tree.
121. **Entropy as forgetting signal = novel publishable contribution (#030)** — No competitor uses graph entropy for decay weighting. compute_activation × 16 entropy APIs enables structure-aware forgetting: high-entropy (uniform) nodes are redundant → faster decay; low-entropy (unique structural role) nodes preserved longer.
122. **Rényi (extensive) + Tsallis (non-extensive) = complete generalized entropy pair (c288)** — Both converge to Shannon at limit (α/q→1) but emphasize differently: Rényi is additive for independent systems, Tsallis is non-additive. Having both covers all entropy generalization frameworks.
123. **entropy_distance() = first inter-graph method (c288)** — JSD between two graphs' edge-contribution distributions. Symmetric, bounded [0,1], satisfies triangle inequality. Enables graph clustering, similarity search, and classification without external tools. All previous entropies were intra-graph (single-graph descriptors).
124. **Von Neumann graph entropy = first spectral entropy (#031)** — Shannon entropy of normalized Laplacian eigenvalues. Captures GLOBAL topology (not local features). K_n maximizes: H=log(n-1) with uniform non-zero eigenvalues, opposite to degree-entropy where K_n=0. For agent memory: well-connected graph = HIGH spectral entropy (healthy), fragmented = LOW (unhealthy). Amg already has _sym_eigenvalues infrastructure → ~25 lines to implement.
125. **Temporal entropy trajectory = novel publishable health metric (#031)** — Track S_vN(G_t) over time. First/second derivatives detect growth/consolidation/forgetting/phase-transition phases. Sustained negative rate + decreasing nodes = knowledge collapse. Plateau = consolidation trigger. No competitor has ANY temporal entropy tracking. Combined with #030 (entropy-weighted forgetting) = two publishable contributions.
126. **Information-theoretic trilogy complete (c288+298+299)** — Three complementary inter-graph measures: JSD (symmetric, bounded [0,1], true metric) + cross-entropy H(P,Q) (asymmetric, encoding cost) + KL divergence (asymmetric, information gain). Enables graph classification, anomaly detection, and clustering without external tools. No npm/PyPI competitor has ANY inter-graph comparison.
127. **EntityResolver closes competitive gap (c296, #032)** — Mem0 v3 and Graphiti both have entity resolution as core feature. amg now matches with 8 APIs (alias/duplicate/merge). Critical for real-world memory graphs where entities are referenced differently across sessions.
128. **Entropy-weighted retrieval = second publishable contribution (c297)** — BM25 + per-node entropy weight blend. Hub nodes (high entropy) get boosted. Connects entropy toolkit to retrieval scoring. Combined with entropy-weighted forgetting (#121) = two novel contributions no competitor has.
129. **Von Neumann spectral entropy captures global topology (c292, #031)** — Shannon entropy of normalized Laplacian eigenvalues. K_n maximizes H=ln(n-1) — opposite of degree-entropy where K_n=0. Well-connected graph = HIGH spectral entropy (healthy), fragmented = LOW (unhealthy). Existing _sym_eigenvalues infra → ~50 lines.
130. **Mem0 v3 ADD-only validates amg conflict resolution (#032)** — Mem0 dropped UPDATE/DELETE for 3x latency reduction + higher accuracy. amg's merge/consolidation approach was right all along. Graph-based resolution > vector dedup.
131. **Bi-temporal is now table stakes — Engram 83.6% vs 73.2% full-context (#033)** — Bi-temporal fact graphs (valid_time + transaction_time, invalidate-never-delete) beat full-context by +10.4pp on LongMemEval. amg already has bi-temporal edge tracking but doesn't expose `query_as_of(timestamp)` as first-class API. Graphiti's moat is no longer unique.
132. **Dual-process System-1/System-2 is THE production architecture pattern (#033)** — Every high-performing system (Engram, Mem0 v3, H-Mem) separates hot write path (no LLM, O(1) append) from cold async consolidation. amg's synchronous write path is fine for batch but wrong for real-time. FastAppendQueue needed.
133. **Benchmark harness IS the competitive weapon (#033)** — Same system appears as 58%/66%/92% across sources. Engram ships neutral reproducible harness with official judge. For amg npm launch: shipping benchmark harness creates ecosystem lock-in. Being the scoreboard = power.
134. **H-Mem hybrid tree+graph reveals amg's missing temporal abstraction layer (#033)** — H-Mem's temporal-semantic tree (daily→weekly→monthly summaries) is simpler version of amg's planned compress_to_skill (L0→L3). SummaryTree layer on top of graph would fill temporal abstraction gap.

135. **Spectral divergence = histogram-based inter-graph comparison, size-invariant (c308)** — Bin Laplacian eigenvalues into common [0,λ_max] grid, normalize to probability distributions, compute JSD/KL/CE. Unlike quantum_jensen_shannon_distance (elementwise, same-size only), histogram approach works for different-size graphs. 3 measures in one unified API. Complements degree-based trilogy with spectral-domain comparison.
136. **Multi-resolution scan reveals structural scale of divergence (c309)** — Fibonacci-like bins [2,3,5,8,13,21,34,55] sweep from coarse (global topology) to fine (individual eigenvalues). Peak resolution = where graphs differ most. Convergence (CV<0.05 last 3) = when enough resolution. Monotonicity direction = whether divergence grows or shrinks with resolution. Transforms single-number comparison into analytical instrument.

---

137. **Beta distribution gives confidence for free — Wilson LB prevents lucky-early-access attacks (#035)** — Beta(α,β) variance = confidence measure. Agent with 2✓0✗ has mean=1.0 but Wilson LB (95%) = 0.34. Using Wilson LB for critical-risk decisions means untested agents can't access dangerous capabilities despite perfect mean. Two-tier: mean for low/medium, Wilson LB for high/critical.
138. **A2A Agent Cards are the perfect trust anchor — signed identity + declared capabilities (#035)** — A2A Protocol v1.0.0 defines Agent Cards as signed JSON with publicKeyJwk, skills[], authentication schemes. This maps 1:1 to trust model: identity (who), capabilities (what they claim), verification (signature). Mismatch between declared skills and observed performance is itself a trust signal.
139. **Trust propagation needs hop decay — gossip without decay is poisonous (#035)** — EigenTrust-style distributed trust without hop decay lets a single compromised agent amplify trust through colluding chains. hopDecay=0.5/hop bounds influence to direct neighborhood. Combined with content fingerprinting (SimHash) that catches adversarial patterns behavioral metrics miss = defense in depth.

---

140. **Rényi entropy order α is graph resolution control (#036)** — Low α (→0) emphasizes graph size/connectivity. High α (→∞, min-entropy) detects bottlenecks and hubs. The CURVE of H(α) across orders is a structural fingerprint: flat=regular, steep=heterogeneous, convex with knee=mixed community+hub structure. A scan across α ∈ {0.5,1,2,3,5,8,20,∞} produces a unique signature for graph families. No npm/PyPI competitor has entropy scan capability.
141. **Entropy curve SHAPE (not scalar) is the graph fingerprint (#036)** — Single entropy value tells little. But a VECTOR of entropies at multiple scales — Shannon, Rényi(α=2,3,5,∞), Tsallis, von Neumann, edge-betweenness — creates a unique fingerprint. Two graphs with identical degree distributions but different clustering have identical Shannon degree entropy but diverge on spectral entropy. Combined degree+spectral fingerprint correctly classifies 6/7 graph families (verified in code). The shape (monotonic, range, convergence CV) is the analytical instrument.

---

142. **Three-layer router cascade = production-pattern MemFlow implemented (c317)** — Rules layer commits immediately for high-confidence intents (basic/temporal/constraint/global). Entropy layer escalates for ambiguous queries using graph topology. Fallback layer catches edge cases. Full cascade_trace with per-layer latency = production routing observability. First npm library with entropy-aware query routing.
143. **Spectral classification completes the identification stack (c318)** — Three methods in one API: spectral (single-resolution histogram JSD/KL/CE), spectral_scan (multi-resolution mean across Fibonacci bins), fingerprint (L2 on 12+ dim entropy feature vectors). Confidence = separation ratio between best and second-best match. Margin = absolute gap. Enables graph family identification without training data.
144. **Entropy fingerprint = compact graph DNA (c314)** — 12+ dimensional feature vector (Shannon degree, Rényi α=2/3/5/∞, Tsallis, von Neumann, edge-betweenness, etc). Two graphs with identical degree distributions but different clustering have identical Shannon degree entropy but diverge on spectral entropy. Combined degree+spectral fingerprint correctly classifies 6/7 graph families. Not a scalar — a vector signature.
145. **Classification with rejection = production safety layer (c320)** — classify→reject/accept pipeline. Dual criteria (score threshold + min margin) prevents low-confidence misclassification. Exact match always accepted (score≈0). Calibrated confidence linear rescale to [0,1]. Works with all 3 classification APIs. First npm library with entropy-aware classification rejection.
146. **The scoreboard IS the moat (#037)** — Shipping a neutral benchmark harness alongside amg makes amg's scores "official" (reference implementation). Competitors must either use amg's harness (endorsing it) or build their own (looking defensive). Mem0 already does this with Python-only memory-benchmarks. amg's harness should be TypeScript-native with clean MemoryBackend interface.
147. **Operation-level evaluation = differentiator no competitor has (#037)** — MemOps proves final-answer scoring conflates failure modes. amg already has lifecycle hooks (governance, entity resolution, forgetting, gap detection). Exposing as MemOps-compatible structured traces creates evaluation layer impossible without deep architectural integration. Moat within the moat.
148. **Scale tiers reveal non-linear failure modes (#037)** — BEAM: temporal reasoning 0.618 (1M) → 0.163 (10M). Event ordering 0.536 → 0.202. Memory systems have cliffs. amg's entropy-weighted retrieval + forgetting should theoretically prevent cliffs. Harness must include scale tiers.
149. **LongMemEval-V2 shifts to agentic multimodal context (May 2026, #037)** — 451 questions, up to 115M tokens, web trajectories with screenshots. 5 new ability types. "Environment gotchas" + "premise awareness" align with amg's knowledge gap detection + entity resolution.
150. **Fixed reader model is the reproducibility key (#037)** — LongMemEval-V2 uses Qwen3.5-9B as fixed reader. Eliminates "better reader = better score" variance. For amg-bench: default to small reproducible model (Qwen-9B/Llama-8B via Ollama) for answerer, stronger model for judge. Enables fully reproducible offline runs.

### 🔴 最高优先级: npm Publish
- [ ] **agent-memory-graph: README + npm publish** — **5807 tests**, 896+ APIs
- [ ] **agent-context-store: README + npm publish** — **2898 tests**, 600+ APIs
- [ ] **structured-output-toolkit: README + npm publish** — **571 tests**
- [ ] **agent-task-cli: README + npm publish** — **1340 tests**, F214

> ⚠️ Mandol (ISCAS+MSRA) 已发 paper+PyPI+GitHub，LoCoMo SOTA 92.21%。PlugMem 已有 OpenClaw plugin。竞争窗口收紧。**10606 tests across 4 projects, all npm ready.**

### 🟡 研究驱动 — 待实现 (Research #035: A2A Trust Engine V2 新增)
- [ ] **lab/a2a-trust-prototype: Replace TrustEngineV2 skeleton with full implementation** — 7 algorithms (Bayesian Beta + Wilson LB, time decay, SimHash, trust gates, EigenTrust propagation, capability scoping, harness safety). Add Jest test suite (40+ tests). Code in research note.
- [ ] **lab/a2a-trust-prototype: A2A Middleware Adapter** — Wrap TrustEngineV2.evaluate() as A2A-compatible middleware. Intercept tasks/send, check trust before forwarding. ~80 lines.
- [ ] **lab/a2a-trust-prototype: Two-tier trust (Wilson LB for high/critical, mean for low/medium)** — Prevents untested agents from getting lucky early access to dangerous capabilities.

### 🟡 研究驱动 — 待实现 (Research #034: OTel GenAI Alignment 新增)
- [ ] **lab/agent-observability: Rename SpanOperation → gen_ai.operation.name** — Align with OTel spec: `agent.run`→`invoke_agent`, `llm.call`→`chat`, add 7 memory ops. Breaking but pre-1.0.
- [ ] **lab/agent-observability: Add `gen_ai.conversation.compacted` attr** — Maps directly to amg adaptive forgetting. 1-line per span.
- [ ] **amg-mcp: Implement `_meta` trace context propagation** — Extract W3C Trace Context from MCP `_meta`, create child spans. ~50 lines. SEP-414 compliant.
- [ ] **lab/agent-observability: OTelGenAITracer adapter** — Wraps existing Tracer, emits spec-compliant attributes. Drop into `src/otel-adapter.ts`. Code in research note.
- [ ] **amg: Add `gen_ai.client.token.usage` histogram** — With spec bucket boundaries [1,4,16,64,256,1024,4096,...]. Feeds into any OTel dashboard.

### 🟡 研究驱动 — 待实现 (Research #033)
- [ ] amg: `query_as_of(timestamp)` — Expose bi-temporal tracking as first-class API. Engram pattern. ~40 lines + ~30 tests.
- [ ] amg: `FastAppendQueue` — System-1/System-2 split. Hot append + async consolidate. ~200 lines + ~80 tests.
- [ ] amg: `SummaryTree` layer — Periodic consolidation nodes (H-Mem pattern). Temporal abstraction hierarchy. ~150 lines + ~60 tests.
- [ ] amg: Benchmark harness — Neutral, reproducible LongMemEval harness in-repo. Ship alongside npm. Ecosystem play.

### 🟡 研究驱动 — 待实现 (Research #032: COMPLETED items ✅)
- [x] ✅ amg: EntityResolver — DONE (c296, 8 APIs, +30 tests)
- [x] ✅ amg: entropy_weighted_retrieval() — DONE (c297, +11 tests)
- [x] ✅ amg: bi-temporal edge tracking — ALREADY EXISTS (discovered during implementation)
- [ ] amg README: Position as "agency-grade graph memory for self-evolving agents" NOT "graph library". Lead with entropy-weighted forgetting + retrieval (two publishable contributions).

### 🟡 研究驱动 — 待实现 (Research #031: COMPLETED items ✅)
- [x] ✅ amg Cycle 292: `von_neumann_entropy()` + `spectral_entropy_profile()` — DONE (+50 tests)
- [x] ✅ amg Cycle 293: `TemporalEntropyTracker` — DONE (+37 tests)
- [x] ✅ amg Cycle 294: `quantum_jensen_shannon_distance()` — DONE (+26 tests)
- [x] ✅ amg Cycle 295: entropy_profile() spectral extension — DONE (+4 tests)

### 🟡 研究驱动 — 待实现 (Research #029 新增)
- [ ] amg: SearchTreeNode + expand_search_tree() / prune_search_tree() — Graph-as-search-tree (Arbor pattern). Nodes get score+depth. Connects to entropy-guided branching (#028). ~80 lines + ~60 tests.
- [ ] agent-task-cli: LatencyAwarePlanner — Extend ConcurrencyManager with EMA-based learned latency, wave-grouped execution topology (LAMaS pattern). ~100 lines + ~50 tests.
- [ ] openclaw-langgraph-bridge: Coordination pattern switcher (Supervisor/GroupChat/TreeSearch modes) — A/B test coordination configs with same agent pool. ~150 lines + ~80 tests.
- [ ] lab/agent-observability: Multi-agent span dimensions (gen_ai.agent.role, gen_ai.coordination.wave, gen_ai.critical_path.position). ~40 lines + ~30 tests.

### 🟡 研究驱动 — 待实现 (Research #028 新增)
- [ ] better-ralph: VRRStopper — 从 PRD 迭代历史估计 (α, β, γ, δ) 噪声参数，expectedRepairGain < 0 时停止。~60 行 + ~30 tests。关联 VRR-Stop arXiv:2607.17641
- [ ] nano-agent: Critique 接口 — Agent.critique(action, context) 返回 0-1 分数。默认启发式实现。~50 行 + ~40 tests。关联 RLAW
- [x] ✅ amg: entropy_guided_query_route() — DONE (c287, 52 tests). 高熵→basic, 低熵→drift mode.

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
- [x] ✅ amg: three_layer_router_cascade — DONE (c317, 36 tests). MemFlow production pattern. rules→entropy→fallback.
- [ ] amg: intent_aware_edge_cost() — PRISM intent routing (#010). ~+40 tests
- [ ] amg: procedural memory node type — PlugMem prescriptive knowledge (#010). ~+50 tests
- [x] ✅ amg: auto_heal_gaps() — Cycle 266 (done, 4-strategy self-healing already implemented)
- [ ] LoCoMo benchmark adapter + full-context baseline reporting
- [ ] **amg README: 竞品对比表** — Mem0/Zep/Mandol/PlugMem/PRISM/Hippocampus + **GraphRAG/LightRAG positioning: security-first agent-native GraphRAG**

### 🟣 Deep Research (detailed notes in catalyst-research/exploration-notes/)
- **#037 (07-30)** ✅: Agent Memory Benchmark Harness Design. Four evaluation layers (answer/operation/form/scale). Scoreboard = moat. Operation-level eval = differentiator. BEAM scale cliffs. LongMemEval-V2 agentic multimodal. Fixed reader model = reproducibility. Full TS harness skeleton (~200 lines, zero-dep). 5 insights (#146-#150). [笔记](catalyst-research/exploration-notes/2026-07-30-agent-memory-benchmark-harness-design.md)
- **#036 (07-29)** ✅: Information-Theoretic Graph Classification & Multi-Scale Entropy Fingerprinting. Rényi α = resolution parameter (low α=connectivity, high α=bottleneck). Entropy curve shape = graph fingerprint (not scalar value). VNEstruct ego-local entropy > global for node tasks (ICML 2020). TIDE tri-component decomposition (feature×structure×joint, ICML 2026). PRI formalizes entropy-guided forgetting. FGN continuous entropy fields (June 2026). AERK quantum walk kernels. 2 runnable code examples (entropy_scan + graph_classification prototypes, verified ✅). Feeds amg cycles 310-311. [笔记](catalyst-research/exploration-notes/2026-07-29-graph-classification-entropy-fingerprinting.md)
- **#033 (07-28)** ✅: Agent Memory Engineering 2026H2. Engram bi-temporal dual-process (83.6% vs 73.2%, +10.4pp). H-Mem hybrid tree+graph (SOTA 3 benchmarks). Memanto info-theoretic retrieval. MAGE four-subgraph multi-agent. Dual-process System-1/System-2 = production pattern. Benchmark harness = competitive weapon. 2 runnable code examples. [笔记](catalyst-research/exploration-notes/2026-07-28-agent-memory-engineering-2026h2.md)
- **#031 (07-27)** ✅ IMPLEMENTED: Temporal Graph Entropy & Von Neumann spectral methods. First spectral entropy (Laplacian eigenvalue Shannon). K_n maximizes H=log(n-1). Temporal entropy trajectory for phase transition detection. QJSD for spectral graph comparison. 3 runnable code examples. **Cycles 292-295 complete** (+117 tests). [笔记](catalyst-research/exploration-notes/2026-07-27-temporal-graph-entropy-spectral-methods.md)
- **#035 (07-29)** ✅: A2A Trust Engine V2. Full 7-algorithm implementation (Bayesian Beta reputation, exponential time decay, SimHash content fingerprinting, risk-stratified trust gates, EigenTrust distributed propagation, capability scoping, harness safety). Wilson lower bound for conservative trust. 12/12 self-tests passing. Maps to A2A Protocol v1.0.0 enterprise security model. 1 runnable code example (complete engine, ~400 lines). [笔记](catalyst-research/exploration-notes/2026-07-29-a2a-trust-engine-v2.md)
- **#028 (07-25)**: Agent planning beyond ReAct. VRR-Stop adaptive stopping (60.6pp gain). SkillComposer structured skill composition (+23.1pp). RLAW POMDP+GAT+Critic (78.6% vs 54.1%). Entropy-guided branching. PlanFlip planning attacks. 3 runnable code examples. [笔记](catalyst-research/exploration-notes/2026-07-25-agent-planning-reasoning-2026.md)
- **#027 (07-25)**: Agent trust & safety. Dissociative identity kills reputation. Per-component SimHash (0.974 AUC). Pre-execution gating. Distributed attacks. 7 TrustEngineV2 algorithms. [笔记](catalyst-research/exploration-notes/2026-07-25-agent-trust-safety-2026.md)
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
- [ ] TrustEngineV2: 实现 lab/a2a-trust-prototype — **Research #027 ✅ 7 algorithms designed + verified**: Bayesian trust update, exponential decay, per-component SimHash skill fingerprint, pre-execution gate, distributed attack detector, authority-scoped delegation, behavioral harness. Skeleton in lab/a2a-trust-prototype/src/trust-engine-v2.ts. Full impl + tests next. (~300 src + ~200 tests)

---

## Core Projects Quick Reference

| # | 项目 | Tests | 状态 |
|---|------|-------|------|
| 1 | agent-task-cli | 1340 | ✅ npm ready, F214 (214 features) |
| 2 | agent-memory-graph | **5807** | ✅ npm ready, 八十合一: entropy framework (28+ APIs incl. spectral + inter-graph trilogy + contribution + stability + spectral_divergence + scan + fingerprint + classification + classification_with_rejection) + adaptive forgetting (6) + EntityResolver (8) + entropy-weighted retrieval + MCP Day 1-5 |
| 3 | agent-context-store | 2898 | ✅ npm ready, 二十六层: detect→configure→recommend→validate→correlate complete |
| 4 | structured-output-toolkit | 561 | ✅ npm ready |
| 5 | openclaw-langgraph-bridge | 261 | 🔄 Supervisor 完善 |
| 6 | context-forge | **1346** | ✅ F79 dead code detection (11000+ lines, 21 dimensions) |
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

## Timeline

### Immediate (Week of July 30)
- [ ] README(amg) → npm publish — **#1 priority**. 5807 tests, 896+ APIs.
- [ ] README(acs) → npm publish — 2898 tests.
- [ ] MCP Registry publish (SDK v2 stable July 28)
- [ ] **amg Cycle 321+: hybrid_classification()** — Combine degree + spectral + fingerprint scores. ~40 lines + ~50 tests.
- [ ] **amg: query_as_of(timestamp)** (#033) — Expose bi-temporal tracking. Engram pattern. ~40 lines + ~30 tests.
- [ ] **amg: entropy_scan()** — Multi-scale Rényi/Tsallis sweep across α/q range. Returns curve for graph fingerprinting. ~40 lines + ~50 tests.
- [ ] **amg-bench: Benchmark harness** — TypeScript MemoryBackend interface + AMGBackend adapter. ~400 lines harness + ~100 lines adapter. LongMemEval-compatible. Operation-level evaluation (moat). Research #037 ✅.

### Short-term (August)
- [ ] amg: forget_policy() — ✅ DONE (c284)
- [ ] amg: cue_reactivation() — ✅ DONE (c285)
- [ ] amg: security_purge() — ✅ DONE (c286)
- [ ] amg: get_operation_history() (MemOps-compatible)
- [ ] EvoMemBench InEp-Know setting vs amg
- [ ] amg OpenClaw plugin (~200 lines)
- [ ] amg-bench: LongMemEval S baseline run (full-context vs entropy-weighted retrieval)

### Medium-term (September)
- [ ] compress_to_skill() + retrieve_skills() + evolve_skill()
- [ ] Full EvoMemBench 4-setting evaluation
- [ ] MemFactory integration experiment (RL-trained memory policy via GRPO)
- [ ] Benchmark on LoCoMo + LTI-Bench (vs FadeMem 45% storage reduction)

### 重要框架
- **A2A协议** — Agent间"HTTP", 150+组织, Linux Foundation AAIF
- **MCP协议** — Agent的"USB接口", 97M+下载, 工具访问标准
- **memorywire** — 5 ops × 4 types, 计划 MCP-WG + IETF at v0.5
