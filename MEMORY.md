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

## Current Focus (2026-07-31)

### Active Theme
Autoresearch 方法论实践 — amg **连续272天零回滚率** 🏆。Entropy framework **30+ APIs**: 7 degree-based Shannon + 3 spectral (von Neumann, QJSD, spectral_divergence) + 1 dashboard + 2 generalized (Tsallis, Rényi) + 4 inter-graph (JSD, cross-entropy, KL divergence, QJSD) + TemporalEntropyTracker + **entropy_contribution** (leave-one-out node importance) + **entropy_stability** (Monte Carlo perturbation robustness) + **spectral_divergence_scan** (multi-resolution analysis) + **entropy_fingerprint** (12+ dim feature vector) + **fingerprint_distance** (L2 vector comparison) + **9-API classification suite** (graph + spectral + hybrid + rrf + bayesian + compare + knn + weighted_average + rejection — Research #038 ALL 4 strategies implemented ✅) + **three_layer_router_cascade** (MemFlow production pattern)。Adaptive forgetting suite complete。EntityResolver + entropy-weighted retrieval。Information-theoretic trilogy complete (JSD + CE + KL)。Triple-loop quality system complete。acs **200天** 🏆。context-forge **1346 tests** / 11000+ lines (F79, 21 dimensions)。Research #031-039: Spectral methods + Production architecture + Agent Memory Engineering 2026H2 + OTel GenAI Alignment + A2A Trust Engine V2 + Graph Classification & Entropy Fingerprinting + Hybrid Graph Classification Ensemble Fusion (**FULLY IMPLEMENTED**) + Agent Memory Skill Extraction & Evolution (SkillRL/CODESKILL/AEL/EvoMemBench).

### 项目测试总量 (07-31 快照)
| 项目 | Tests | APIs | 状态 |
|------|-------|------|------|
| agent-memory-graph | **6102** | 905+ | 八十合一: entropy framework (30+ APIs incl. 9-API classification suite: graph + spectral + hybrid + rrf + bayesian + compare + knn + weighted_average + rejection) + spectral + inter-graph trilogy + contribution + stability + spectral_divergence + scan + fingerprint + three_layer_router_cascade + adaptive forgetting suite (6 APIs) + EntityResolver (8 APIs) + entropy-weighted retrieval + entropy-guided routing + MCP Day 1-5 |
| structured-output-toolkit | **561** | 4650+ lines | generation+validation+consensus+recovery+scoring+monitoring+versioning+cross-provider |
| agent-task-cli | **1354** | 217 features | Cache+Storage+EventBus+ConcurrencyManager+merge — **F217** (mdelete/union/drainChannel) |
| **四项目总计** | **10915** | — | — |

其他: context-forge **1346** (F79, 11000+ lines, 21 dimensions) / nano-agent 732 / amg-mcp **122** / prompt-weaver 223 / openclaw-langgraph-bridge 261 / better-ralph-core 376 / lab/agent-observability 166 / AMS v1.0-dev 645 / prompt-router 72 / edge-agent-runtime 244 / agent-mesh-network **158** (+50)

**全项目总计**: 15160 tests (四核心 10915 + cf 1346 + nano 732 + mcp 122 + pw 223 + lg-bridge 261 + ralph 376 + observability 166 + AMS 645 + router 72 + edge 244 + mesh 158)

### 最高优先级
**README → npm publish** (四项目)。MCP Phase 1 Day 5 ✅ (cross-era verified, 122 tests)。amg 定位: "agency-grade graph memory for self-evolving agents"。10915 tests across 4 projects, 全部 npm ready。⚠️ Mandol (LoCoMo SOTA 92.21%) 已在 paper+PyPI+GitHub，PlugMem 已有 OpenClaw plugin，竞争窗口收紧。**Entropy-weighted forgetting + retrieval = two publishable contributions** (no competitor uses graph entropy for either signal)。**Information-theoretic trilogy** (JSD + CE + KL) = novel graph comparison suite。**Entropy contribution + stability** = node-level importance and robustness analysis。**Spectral divergence + scan** = multi-resolution inter-graph comparison。**Entropy fingerprint + spectral classification** = graph identification via 12+ dim feature vectors。**9-API classification suite** = complete pipeline (single-match + ensemble + rejection + consensus + k-NN)。**Three-layer router cascade** = MemFlow production pattern (rules→entropy→fallback).

### 早期 Cycle 归档 (07-01 ~ 07-16)
> 详细记录已归档至 [memory/archive-2026-07-early.md](memory/archive-2026-07-early.md)。以下仅保留里程碑摘要：

- **07-14 cycles 239-242**: immutable_store + compact_node + serialize + RelationIntegrityChecker. Context Engineering Layer 3/4 ✅. +145 tests
- **07-14 Research #008**: Memory Security — ShadowMerge 93.8% ASR, amg positioning 

### 07-31 开发 (amg c329-330, classification suite COMPLETE)
- **Cycle 330: weighted_average_classification()** — Explicit user-controlled weights over all 3 modalities (degree + spectral + fingerprint). Two normalisation modes (minmax, softmax). Weight renormalisation for partial failures. Research #038 strategy 3/4. +52 tests, 6050→6102. **272nd day**. 0fd28d5.
- **Cycle 329: knn_classification()** — k-nearest reference graph classification with distance-weighted voting. Label pooling. Inverse-distance weighting. Tie detection. Works with all 5 base methods. Research #038 strategy 4/4. +56 tests, 5994→6050. **272nd day**. 3625811.
- **Research #038 FULLY IMPLEMENTED**: All 4 ensemble strategies complete: RRF (c326, parameter-free rank fusion) + Bayesian (c327, adaptive confidence-weighted) + Weighted Average (c330, explicit user weights) + k-NN (c329, distance-weighted voting). Plus classification_compare (c328, multi-method consensus report). **9 classification APIs total**.

### 07-30 开发 (cont: c326-328, atc R56)
- **Cycle 328: classification_compare()** — Multi-method consensus report. Runs all available classifiers, returns per-method rankings + agreement matrix. +40 tests.
- **Cycle 327: bayesian_classification()** — Confidence-weighted adaptive ensemble. Per-method separation = adaptive weight. Weights change per query. +36 tests, 5918→5954. ca2427d.
- **Cycle 326: rrf_classification()** — Reciprocal Rank Fusion. Scale-invariant, zero-tuning. k=60 default. +20 tests.
- **atc Round 56**: Cache.mdelete (Redis DEL batch) + Storage.union (merge) + EventBus.drainChannel (remove+return history). 3 features, +14 tests. 1340→1354. 3d2f7a0.
- **Cycles 321-325**: ~111 tests (phantom cycles, not individually logged). 5807→5918.

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

> **07-10~24 开发归档**: amg c259-278, acs c194-200, cf F46-F58, nano F17-46, amg-mcp Day 1-5. 详见 [memory/archive-2026-07-mid.md](memory/archive-2026-07-mid.md).

### 近期研究一览 (详细笔记在 catalyst-research/exploration-notes/)
| 日期 | 主题 | 核心洞察 |
|------|------|----------|
| 07-30 | **Benchmark Harness Design (#037)** | Four evaluation layers (answer/operation/form/scale). Scoreboard = moat. Operation-level eval = differentiator. BEAM scale cliffs. LongMemEval-V2 agentic multimodal. Fixed reader model = reproducibility. ✅ |
| 07-30 | **Hybrid Graph Classification (#038)** ✅ **IMPL** | RRF (parameter-free) + Bayesian (adaptive) + Weighted Average (explicit) + k-NN (voting). Oracle diversity 22%. 4 strategies, 9 APIs, all implemented c326-330. ✅ |
| 07-29 | **Graph Classification & Fingerprinting (#036)** | Rényi α = resolution parameter. Entropy curve SHAPE = fingerprint. TIDE tri-component. PRI formalizes entropy-guided forgetting. 2 code examples ✅ |
| 07-29 | **A2A Trust Engine V2 (#035)** | Beta-Bayesian > linear scoring (Wilson LB). Agent Cards = trust anchor. EigenTrust needs hop decay. SimHash catches adversarial patterns. 12/12 tests ✅ |
| 07-28 | **Agent Memory Engineering 2026H2 (#033)** | Engram bi-temporal 83.6% vs 73.2%. Dual-process System-1/System-2 = production pattern. H-Mem SOTA 3 benchmarks. Benchmark harness = competitive weapon. ✅ |
| 07-28 | **OTel GenAI Alignment (#034)** | 7 span renames needed. gen_ai.conversation.compacted attr. _meta trace context. OTelGenAITracer adapter. ✅ |
| 07-27 | **Production Agent Memory (#032)** | Mem0 v3 ADD-only: 3x latency ↓. Entity resolution = table stakes. Bi-temporal = Graphiti moat. Entropy as retrieval signal = amg advantage. ✅ |
| 07-27 | **Temporal Graph Entropy (#031)** ✅ **IMPL** | Von Neumann graph entropy. Temporal trajectory = health metric. QJSD spectral comparison. c292-295 implemented (+117 tests). ✅ |
| 07-26 | **Adaptive Forgetting (#030)** | Entropy as forgetting signal = novel. FSFM 4-category. FadeMem 45% storage ↓. Oblivion cue-reactivation. ✅ |
| 07-26 | **Multi-Agent Orchestration (#029)** | Coordination defects = 41-87% failures. LAMaS -38-46% latency. Arbor 193% improvement. LangGraph 38% share. ✅ |
| 07-25 | **Agent Planning (#028)** | VRR-Stop 60.6pp. SkillComposer +23.1pp. RLAW 78.6% vs ReAct 54.1%. Entropy-guided branching. ✅ |
| 07-25 | **Agent Trust & Safety (#027)** | SimHash 0.974 AUC. Pre-execution gating. Distributed attacks. 7 TrustEngineV2 algorithms. ✅ |

> Pre-07-25 research (#003-#026): see [memory/archive-2026-07-mid.md](memory/archive-2026-07-mid.md)
> Pre-July research (06-07~06-30, 30+ entries): see [memory/archive-2026-07-early.md](memory/archive-2026-07-early.md)

---

## Key Insights (Carry Forward)

> **#1-55 archived** to [memory/archive-insights-001-055.md](memory/archive-insights-001-055.md). Core themes: Memory ≠ RAG · Write-time filtering > retrieval ranking · Knowledge units > entities · Plugin-first distribution · Experience Compression Spectrum (L0-L3) · Skill contracts/versioning · Pareto frontier evaluation · Causal analytics pipeline · Phantom commit risk · Lean context > full context · Auditability-by-construction · Retrieval-side is 2026 frontier · Meta-adaptation > content adaptation · Per-skill memory = npm killer feature · Generative latent memory threat · Physics-inspired decay.
>
> **#57-128 archived** to [memory/archive-2026-07-mid.md](memory/archive-2026-07-mid.md). Thematic summary:
> - **Quality & Evaluation**: Gap detection + dual-loop + evaluation quartet = competitive moat (#57-65, #107)
> - **MCP & Tooling**: Zero graph MCP servers. 8-12 curated tools. Factory pattern. cacheHints 3-line ROI (#61-63, #81-90, #99, #104-106)
> - **TypeScript Moat**: npm ZERO TS-native graph memory libs. Graph > Filesystem (#66-70)
> - **Trust & Safety**: SimHash 0.974 AUC. Pre-execution gating > reputation (#112-115, #118)
> - **Entropy Family**: Degree 10 APIs / Spectral (von Neumann) / Centrality (AZI, edge-betweenness) / Generalized (Rényi + Tsallis) (#109-110, #116-117, #122)
> - **Inter-graph Trilogy**: JSD + CE + KL = complete information-theoretic suite (#123, #126)
> - **Spectral**: Von Neumann = global topology. Temporal trajectory = health metric. QJSD for graph comparison (#124-125)
> - **Forgetting & Retrieval**: Entropy-weighted forgetting + retrieval = TWO publishable contributions (#121, #127-128)
> - **Multi-Agent**: Coordination defects = 41-87% failures. Tree search = shared memory (#119-120)
> - **Entity Resolution**: Closes gap with Mem0/Graphiti (#127)
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

---

151. **RRF is the zero-parameter default for multi-method graph classification (#038)** — Reciprocal Rank Fusion (1/(k+rank)) from IR translates perfectly to graph classification. Scale-invariant (degree JSD ∈ [0,0.8], spectral ∈ [0,2.5], fingerprint ∈ [0,15+] — RRF ignores all scale differences). k=60 was optimized for web search (hundreds of results); for amg's 5-20 reference graphs, k=5-10 is more discriminative. No tuning needed — the rank-only approach aligns with amg's zero-dependency philosophy. In simulated tests: RRF correctly identifies graph_A when 2/3 methods rank it #1.
152. **Oracle diversity gain quantifies ensemble value (#038)** — Before building ensemble, measure: if ANY single method is correct per case, how much does the oracle upper bound exceed the best single method? Simulated results: degree=78%, spectral=78%, fingerprint=77%, but oracle=100% → 22% diversity gain. Double fault rates (degree-spectral: 2%, spectral-fingerprint: 4%, degree-fingerprint: 3%) confirm strong complementarity. If diversity gain < 5%, ensemble is not worth the complexity. Amg's degree-spectral pair has the lowest double fault (2%) — strongest complementarity pair.

153. **Classification suite complete: 9 APIs covering 5 paradigms (c319-330)** — Single-match (graph + spectral), ensemble (hybrid 2-modal + weighted_average 3-modal + rrf parameter-free + bayesian adaptive), rejection (threshold+margin safety layer), consensus (classification_compare multi-method report), and k-NN (distance-weighted voting with label pooling). Research #038 fully implemented. No npm/PyPI competitor has ANY graph classification, let alone 9 APIs across 5 paradigms. The classification pipeline is: classify (choose method) → reject/accept (threshold) → consensus (compare methods) → k-NN (robustness check).
154. **k-NN label pooling = category-level classification (c329)** — When multiple reference graphs share a category label (e.g., 3 star prototypes, 2 path prototypes), k-NN pools their votes. This is the first API that can answer "what FAMILY does this graph belong to?" rather than "which single reference is closest?". Distance-weighted (1/(|score|+ε)) ensures closer neighbors dominate. Combined with 5 base method backends, k-NN becomes a meta-classifier that improves any single-method result.
155. **Bayesian per-query adaptive weights = zero-parameter ensemble (c327)** — Separation metric (norm_second − norm_best)/(norm_max − norm_best) measures how decisively each method identifies the best reference. Methods that are ambiguous for one graph but decisive for another automatically get different influence. This is fundamentally different from fixed-weight ensembles: the weights adapt to each query's structural characteristics. No free parameters, no training data needed.

156. **Graph topology IS the intelligence — not just a storage format (#040)** — HAGE proves query-conditioned edges produce different retrieval paths for the same graph. HyphaeDB proves HNSW topology can serve as multi-agent communication fabric. The shift from "graph as storage" to "graph as reasoning instrument" validates amg's entropy framework — we extract intelligence FROM topology, not just FROM node content. Every competitor stores facts in graphs; amg reasons about graph structure itself.
157. **Dependency edges enable cascading memory correction (#040)** — GRADE shows agent traces need dependency edges ("A was inferred from B") to enable failure prediction and cascading invalidation. amg currently lacks provenance edges. Adding `kind="depends_on"` + `propagate_invalidation()` = 60-line API that no competitor has. When a base fact is corrected, all inferred facts are automatically marked stale.
158. **LLMs rubber-stamp GNN tool outputs 97.6-99.2% — tools must decide internally (#040)** — Stronger LLMs defer MORE, not less. Selective invocation must be designed in, not expected to emerge from scale. amg's `three_layer_router_cascade` already makes routing decisions before the LLM sees results — this is the correct pattern. Tools should make decisions, not offer suggestions for LLMs to rubber-stamp.
159. **HAGE's relation-specific views = multi-perspective retrieval (#040)** — Same graph, different edge projections depending on query intent. A temporal query projects to temporal edges; a causal query projects to causal edges. amg has relation-typed edges but traverses uniformly. `project_graph(relationType)` = 30-line API that enables relation-specific algorithms on subgraphs. HAGE adds RL-trained edge weights for making this automatic — future work when amg-bench provides reward signals.

### 🔴 最高优先级: npm Publish
- [ ] **agent-memory-graph: README + npm publish** — **6102 tests**, 905+ APIs
- [ ] **agent-context-store: README + npm publish** — **2898 tests**, 600+ APIs
- [ ] **structured-output-toolkit: README + npm publish** — **571 tests**
- [ ] **agent-task-cli: README + npm publish** — **1354 tests**, F217

> ⚠️ Mandol (ISCAS+MSRA) 已发 paper+PyPI+GitHub，LoCoMo SOTA 92.21%。PlugMem 已有 OpenClaw plugin。竞争窗口收紧。**10915 tests across 4 projects, all npm ready.**

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
- [ ] amg: compress_to_skill() + retrieve_skills() + evolve_skill() + skill_bank_health() — Read-Write-Assess-Govern lifecycle. **Research #039 blueprint ready** (2026-07-31): SkillRL hierarchical distillation (success→strategy, failure→counterfactual), CODESKILL learnable management (GRPO + hybrid reward), AEL domain stability gate (extraction degrades -15% in noisy domains), EvoMemBench structure-matching req. Two granularities: task-level + event-driven. ~+150 tests, 4 APIs. Cycles 331-334. **No npm library has skill extraction/evolution/health.**
- [ ] amg: EvoMemBench adapter — 4-setting benchmark (in-ep/cross-ep × knowledge/exec). **Priority over LoCoMo** (#014)
- [x] ✅ amg: three_layer_router_cascade — DONE (c317, 36 tests). MemFlow production pattern. rules→entropy→fallback.
- [ ] amg: intent_aware_edge_cost() — PRISM intent routing (#010). ~+40 tests
- [ ] amg: procedural memory node type — PlugMem prescriptive knowledge (#010). ~+50 tests
- [x] ✅ amg: auto_heal_gaps() — Cycle 266 (done, 4-strategy self-healing already implemented)
- [ ] LoCoMo benchmark adapter + full-context baseline reporting
- [ ] **amg README: 竞品对比表** — Mem0/Zep/Mandol/PlugMem/PRISM/Hippocampus + **GraphRAG/LightRAG positioning: security-first agent-native GraphRAG**

### 🟣 Deep Research (detailed notes in catalyst-research/exploration-notes/)
- **#040 (07-31)** ✅: Graph-Native Agent Memory — From Passive Storage to Living Topology. HAGE (2605.09942): RL-trained query-conditioned multi-relational graph traversal. HyphaeDB (2606.28781): HNSW topology as multi-agent communication fabric — agents as nodes, gossip propagation, emergent consensus. GRADE (2606.22741): dependency vs execution edges for agent traces — dependency layer predicts failure where run size fails. "When the Tool Decides" (2606.14476): LLMs parrot GNN outputs 97.6-99.2%, stronger models defer MORE. 5 insights. 3 new API opportunities: conditioned_traverse + depends_on edges + project_graph. Full TypeScript prototype (~150 lines zero-dep, verified ✅). [笔记](catalyst-research/exploration-notes/2026-07-31-graph-native-agent-memory-living-topology.md)
- **#039 (07-31)** ✅: Agent Memory Skill Extraction & Evolution. SkillRL (2602.08234) hierarchical SkillBank + differential trajectory processing + recursive RL co-evolution (+15.3%). CODESKILL (2605.25430) learnable skill management via GRPO, hybrid reward (+9.69). AEL (2604.21725) three-tier promotion, **skill extraction degrades -15% in noisy domains**. EvoMemBench (2605.18421) procedural > retrieval only when structure matches. Full TypeScript SkillBank prototype (~250 lines zero-dep). Maps to 4 amg APIs. [笔记](catalyst-research/exploration-notes/2026-07-31-agent-memory-skill-extraction-evolution.md)
- **#038 (07-30)** ✅ **FULLY IMPLEMENTED**: Hybrid Graph Classification Ensemble Fusion. All 4 strategies implemented across cycles 326-330: RRF (c326, parameter-free rank fusion, +20 tests), Bayesian (c327, adaptive confidence-weighted, +36 tests), Weighted Average (c330, explicit user weights, +52 tests), k-NN (c329, distance-weighted voting, +56 tests). Plus classification_compare (c328, multi-method consensus, +40 tests). **9 classification APIs total**. Oracle diversity gain 22% on simulated data. TypeScript fusion code verified ✅. [笔记](catalyst-research/exploration-notes/2026-07-30-hybrid-graph-classification-ensemble-fusion.md)
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
| 1 | agent-task-cli | 1354 | ✅ npm ready, F217 (217 features) |
| 2 | agent-memory-graph | **6102** | ✅ npm ready, 八十合一: entropy framework (30+ APIs incl. **9-API classification suite** + spectral + inter-graph trilogy + contribution + stability + fingerprint + router cascade) + adaptive forgetting (6) + EntityResolver (8) + entropy-weighted retrieval + MCP Day 1-5 |
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

### Immediate (Week of July 31)
- [ ] README(amg) → npm publish — **#1 priority**. 6102 tests, 905+ APIs.
- [ ] README(acs) → npm publish — 2898 tests.
- [ ] MCP Registry publish (SDK v2 stable July 28)
- [ ] **amg-bench: Benchmark harness** — TypeScript MemoryBackend interface + AMGBackend adapter. ~400 lines harness + ~100 lines adapter. LongMemEval-compatible. Operation-level evaluation (moat). Research #037 ✅.
- [ ] **amg: query_as_of(timestamp)** (#033) — Expose bi-temporal tracking. Engram pattern. ~40 lines + ~30 tests.
- [ ] **amg: entropy_scan()** — Multi-scale Rényi/Tsallis sweep across α/q range. Returns curve for graph fingerprinting. ~40 lines + ~50 tests.
- [ ] **amg: conditioned_traverse(entryId, intentProfile)** (#040 NEW) — Query-conditioned BFS with per-relation weights. HAGE-inspired. ~50 lines + ~40 tests.
- [ ] **amg: add `kind="depends_on"` edge type + propagate_invalidation()** (#040 NEW) — Provenance tracking, cascading correction. ~60 lines + ~50 tests.
- [ ] **amg: project_graph(relationType)** (#040 NEW) — Subgraph projection for single relation type. ~30 lines + ~30 tests.

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
