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

## Current Focus (2026-07-17)

### Active Theme
Autoresearch 方法论实践 — amg **连续238天零回滚率** 🏆。

### 项目测试总量 (07-17 凌晨快照)
| 项目 | Tests | APIs | 状态 |
|------|-------|------|------|
| agent-memory-graph | **3849** | 750+ | 六十四合一: 全检索管线 + 17 centrality + 拓扑指数十九族 + IR eval + governed selection + phantom detection + spreading activation + proactive context + cascade invalidation + immutable_store + compact_node + serialize + RelationIntegrityChecker + intent_aware_token_budgets + screen_retrieval + query_confidence_score + govern_skill_bank + 7-intent taxonomy (temporal + constraint) + query_route_audit + ... |
| agent-context-store | **2727** | 550+ | 三大管线完整+全分析闭环(十八层): Graph 12 / Quality 12 (action+velocity+cohort+heatmap) / Store 17 (longitudinal+predictive+prescriptive+feedback+monitoring+dashboard+batch+alert-history) |
| structured-output-toolkit | **561** | 4650+ lines | generation+validation+consensus+recovery+scoring+monitoring+versioning+cross-provider |
| agent-task-cli | **1222** | 190+ features | Cache+Storage+EventBus+ConcurrencyManager+merge |
| **四项目总计** | **8359** | — | — |

其他: openclaw-langgraph-bridge 261 / better-ralph-core 376 / lab/agent-observability 166 / context-forge 613 / nano-agent 384 / AMS v1.0-dev 645 / prompt-router 258

**全项目总计**: 11056+ tests (四核心 8359 + context-forge 613 + nano-agent 384 + 其他 1700)

### 最高优先级
**README → npm publish** (四项目)。这是当前最大未交付价值。amg 定位: "beyond recall — agency-grade graph memory — security-first"。8231 tests across 4 projects, 全部 npm ready。⚠️ Mandol (LoCoMo SOTA 92.21%) 已在 paper+PyPI+GitHub，PlugMem 已有 OpenClaw plugin，竞争窗口收紧。

### 07-14 晚间开发 (amg cycles 239-242, code-lab-evening)
- **Cycle 239: immutable_store + grep() + expand()** — LCM (arXiv:2605.04050) + Searchat 启发。append-only 不可变存储，add() 自动写入，确保数据在 compact/delete 后存活。grep() 全历史搜索（含已删节点），expand() 无损回溯（优先 live，fallback immutable）。+41 tests
- **Cycle 240: compact_node() 三级升级** — LCM 启发。Level 0/1=LLM summarizer callback，Level 2=确定性截断（label ellipsis + data key/length 压缩）。自动降级：LLM 失败→level 2。compact_batch + compact_stats。原数据始终在 immutable_store 中保留。+34 tests
- **Cycle 241: serialize() token-budget 序列化** — Searchat 启发。pointer-based 表示，最大化信息密度。weight 排序贪心打包，edge summary 共享预算。serialize_compact() 便捷方法（先自动 compact 低权重节点）。compacted node 检测。+34 tests
- **Cycle 242: RelationIntegrityChecker** — ShadowMerge 防御 (arXiv:2605.09033，93.8% 攻击成功率)。三重检查：value_conflict/confidence_anomaly/origin_mismatch。integrity_quarantine() 自动隔离高严重性节点。integrity_score [0,1]。+36 tests
- **amg 2983→3128 (+145 tests), 233rd consecutive day without rollback**
- **Context Engineering Layer 完成 3/4**: immutable_store ✅ + compact ✅ + serialize ✅ + grep/expand ✅。仅剩 DAG 层级压缩未实现（低优先级）。

### 07-14 晚间深度研究 #009: Context Engineering Layer Implementation (LCM + Distillation)
- **LCM** (arXiv:2605.04050, Voltropy PBC) — Lossless Context Management。DAG 层级压缩 + 三级升级(LLM详细→LLM要点→确定性截断) + 零成本续行。OOLONG 基准超 Claude Code (32K-1M tokens)。核心洞察：让 LLM 管上下文 = GOTO，引擎确定性管理 = Structured Programming。
- **Searchat** (GitHub开源) — Verbatim + Distilled 双层索引，实现 **11x token 缩减**且零数据丢失。Cross-layer ranking 统一排序。DuckDB 存储 + sentence-transformers embedding。搜索 <100ms。
- **Aeon** (arXiv:2601) — 神经符号记忆，图结构 + 注意力优化解决 Lost-in-Middle。
- **Active Context Compression** (arXiv:2601) — Agent 自主压缩解决 Context Bloat。
- **关键实现路径**: (1) immutableStore 数据不丢失 (2) compact() 三级升级保证收敛 (3) serialize() token-budget + 指针 (4) expand() 无损回溯 (5) grep() 全历史搜索
- **与 amg 关系**: retrieve() → 双层结果(distilled+verbatim pointers); sleep_consolidate() → 三级升级; add() → 大文件引用化
- **Next: Cycle 239 候选新增**: ContextEngineeringLayer class — selectiveFilter + compact(三级) + serialize(token-budget) + expand + grep。预计 +60 tests。
- **研究笔记**: [catalyst-research/exploration-notes/2026-07-14-context-engineering-layer-lcm-distillation.md](catalyst-research/exploration-notes/2026-07-14-context-engineering-layer-lcm-distillation.md)

### 07-14 晚间深度研究 #008: Memory Security & Hybrid Architecture
- **ShadowMerge** (arXiv:2605.09033) — 93.8% attack success rate against Mem0 graph memory via relation-channel conflicts。graph memory 安全面临新威胁。
- **HMARS** (arXiv:2606.28349) — 证明 managed memory hierarchy 优于 flat retrieval，即使有 long context。外部 graph memory 仍然不可替代。
- **OSL-MR** (arXiv:2606.10616) — 证明 memory retention 是 NP-hard。amg 的 heuristic 方法 (temporal_score, cache_temperature) 是正确路径。
- **CoreMem** (arXiv:2606.18406) — Fisher-Rao metric 替代 cosine similarity，+4.5pp on LoCoMo。Mahalanobis distance 改进检索。
- **Memory poisoning 爆发**: 2026年5-7月有 10+ 篇论文 (ShadowMerge/Trojan Hippo/Sleeper/Forensic Trajectory/Forged Reasoning...)。memory security 是研究前沿。
- **amg 竞争定位**: "Security-first graph memory" — phantom detection + integrity checker + cascade invalidation 是 Mem0 没有的差异化。
- **Next: Cycle 239 候选**: RelationIntegrityChecker (3 checks: value_conflict/confidence_anomaly/origin_mismatch + integrity_score)。~40 tests。已有 runnable TypeScript demo。
- **研究笔记**: [catalyst-research/exploration-notes/2026-07-14-memory-security-hybrid-architecture.md](catalyst-research/exploration-notes/2026-07-14-memory-security-hybrid-architecture.md)

### 07-17 晚间 code-lab (amg cycles 259-262)
- **Cycle 259: intent_aware_token_budgets + query_with_budgets + screen_retrieval + query_confidence_score** — MemFlow (arXiv:2605.03312) tiered token budgets (basic=200/local=500/hybrid=600/drift=800/global=1000) + GhostWriter/AM-Sentry (arXiv:2607.06595) read-time injection screening (14 instruction patterns, dual-layer defense complementing write_governance) + MemFlow Validator-inspired query confidence (5 factors: coverage/score_spread/graph_density/result_count/freshness). +61 tests
- **Cycle 260: govern_skill_bank()** — SkeMex/MUSE-inspired Govern step of Read-Write-Assess-Govern lifecycle. Four policies: (1) deprecate stale (>N days), (2) deprecate low-confidence, (3) merge redundant (Jaccard ≥ threshold via skill_compose), (4) prune overflow (max_skills). dry_run mode for audit. Completes procedural memory governance. +20 tests
- **Cycle 261: seven_intent_taxonomy** — MemFlow 7-intent expansion. query() routes from 5→7 modes: adds temporal_reasoning (bi-temporal scan with validity windows + supersede awareness) and constraint_validation (kind/tag/keyword search for rule/policy/requirement nodes). Fixed substring matching bug in _route_query (how∈show, was∈was) using word-boundary regex. +32 tests
- **Cycle 262: query_route_audit()** — Routing observability. Mode distribution + per-question rationale + optional result counts for latency analysis. Built-in diagnostic question set covers all 7 modes. +15 tests
- **amg 3721→3849 (+128 tests), 242nd consecutive day without rollback**

### 07-16 晚间~07-17 凌晨开发 (amg cycles 252-258, acs cycle 193)
- **Cycle 252: write_governance_check + safe_supersede + governance_audit** — PASB-inspired (arXiv:2607.10526) commit boundary protection. Three sycophantic failure mode detectors: status_promotion (hedged→definitive), attribution_removal (source qualifiers stripped), scope_broadening (specific→universal). safe_supersede gates supersede operations. governance_audit retrospectively audits supersede chains. +70 tests
- **Cycle 253: community_topic_labels + community_semantic_summary + community_overview + query_global** — GraphRAG-inspired community semantic layer. Topic extraction (kind+tag+keyword frequency), deterministic + LLM-callback summaries, combined structural+semantic dashboard, global query across community summaries. +40 tests
- **Cycle 254: lifecycle_operation_eval** — MemOps-inspired (arXiv:2607.12893) 6-probe validator. detection/target/transition/robustness/provenance/leakage probes across add/update/supersede/forget/merge operations. +29 tests
- **Cycle 255: prospective memory** — PM-Bench-inspired (arXiv:2607.12385, COLM 2026). add_intention with trigger cues + deadline, check_prospective_cues keyword-overlap matching, fulfill_intention, pending_intentions. +38 tests
- **Cycle 256: drift_search** — DRIFT-style hybrid search (global→local→refine with RRF merge). GraphRAG Edge et al. 2024. +35 tests, commit 7ac582d
- **Cycle 257** — +26 tests (commit 311ba6a)
- **Cycle 258: query() adaptive routing** — GraphRAG/LightRAG-inspired mode router (auto→basic/global/drift/local/hybrid). _route_query 5 heuristic rules. detail= enrichment. +39 tests, commit 841b2b6
- **acs Cycle 193: store_trend_report + alert_prediction_accuracy + scorecard_preset_library** — Trend report (N-snapshot time-series with change-point detection) + prediction backtesting (precision/recall/F1 confusion matrix) + 6 built-in presets (default/archive/kgraph/realtime/qa/balanced). +49 tests, commit bb124bb
- **amg 3444→3721 (+277 tests), 238th consecutive day without rollback**
- **acs 2678→2727 (+49 tests), 193rd consecutive day without rollback**

### 07-16 凌晨开发 (amg Key Dev 2 + acs Key Dev 3)
- **Key Dev 2 (amg cycle 251): lorenz_coefficient() + redefined_randic_indices() + redefined_zagreb_index()** — 三新 degree-based 拓扑指数。Lorenz/Gini = 首个图级别度分布不平等度量 (Lorenz 曲线 + Gini 系数, star K_{1,k} → (k-1)/(2(k+1)))。RD₁/RD₂/RD₃ = Randić 2008 redefined variants (ratio d_u·d_v/(d_u+d_v) raised to powers 1/2/3, progressive discrimination)。ReZM₃ = Σ(d_u+d_v)·(d_u·d_v) (hybrid additive-multiplicative, always ≥ M₂)。拓扑指数族→十九族。3386→3444 (+58 tests), commit 0939b10
- **Key Dev 3 (acs cycle 192): store_health_diff() + alert_prediction() + store_health_scorecard()** — 三新分析层。health_diff = 时序对比 (score/grade/alert/metric/forecast/improvement/recommendation deltas)。alert_prediction = 预测性告警 (decay model + history-weighted confidence, active/high/moderate severity)。scorecard = 自定义权重评分 (per-team reweighting, auto-normalization, grade comparison)。分析管线扩展: +temporal +predictive-alerting +custom-perspective。2636→2678 (+42 tests), commit a70a130
- **amg 3444 tests, 236th consecutive day without rollback**
- **acs 2678 tests, 192nd consecutive day without rollback**

### 07-15 晚间开发 (amg cycles 249-250)
- **Cycle 249: dual_mode_retrieve() + binary_signature() + similarity_search_binary()** — Hippocampus (arXiv:2602.13594) 启发。SimHash 64-bit 签名 + Hamming distance O(1) 比较 + 两阶段检索 (binary pre-filter → graph rerank, 0.4×binary_sim + 0.6×graph_score)。小图优化 (<10 nodes 直接 retrieve)。3326→3354 (+28 tests), commit c751e9d, 235th day
- **Cycle 250: find_duplicate_nodes() + deduplicate()** — SimHash-based near-duplicate detection (threshold Hamming distance) + merge duplicates with edge consolidation。3354→3386 (+32 tests)

### 07-15 凌晨开发 (amg Key Dev 2 + acs Key Dev 3)
- **Key Dev 2 (amg cycle 239 key-dev-2): ga_index() + augmented_zagreb_index() + harmonic_index()** — 三新 degree-based 拓扑指数。GA = Σ 2√(d_u·d_v)/(d_u+d_v) (AM-GM bound: GA ≤ m)。AZI = Σ (d_u·d_v/(d_u+d_v-2))³ (最高判别力, K₂→0)。H = Σ 2/(d_u+d_v) = 2·χ_S (文献独立命名)。拓扑指数族→十六族。3165→3249 (+84 tests), commit 3a7a4c7
- **Key Dev 3 (acs cycle 191): store_health_report_export() + quality_decay_model() + alert_correlation()** — 报告导出 (markdown/json/text, 8 section types) + 质量衰减预测 (urgency classification, earliest threshold crossing) + 告警因果分析 (mutation-alert temporal correlation)。分析管线扩展: +export +predictive-decay +causal。2593→2636 (+43 tests), commit dd3b8ad
- **amg 3249 tests, 234th consecutive day without rollback**
- **acs 2636 tests, 191st consecutive day without rollback**

### 07-14 晚间开发 (amg cycles 239-244)
- **Cycle 243: semantic_speed_gate() + selective_filter()** — RoMem-inspired edge volatility detection (speed/stability/velocity/verdict) + Context Engineering multi-criteria node pruning (weight/kind/quarantine/staleness/freshness)。+37 tests
- **Cycle 244: immutable_store reimplementation** — LCM-inspired lossless history (append-only log auto-populated by add/update/delete + immutable_retrieve/history/count + grep + expand)。发现 cycles 239-243 logged 但代码 NOT in memory_graph.py (workspace-level phantom)，本 cycle 重新实现。+35 tests
- Cycles 239-242 已在 MEMORY.md 记录 (immutable_store/compact_node/serialize/RelationIntegrityChecker)

### 07-13 晚间开发 (amg cycles 233-235)
- **Cycle 233: retrieval_quality_eval utilization_rate** — ACL 2026 GEM 驱动。IR metrics 高估高级检索收益。cited_ids 可选字段, 计算 |retrieved ∩ cited|/|retrieved|。Per-query + macro-average。+9 tests
- **Cycle 234: temporal_score()** — RoMem 连续相位旋转启发。替代二元 staleness, 使用 exp(-α * age/half_life) 连续评分 [0,1]。composite = age^0.40 × access^0.35 × validity^0.25。α 控制衰减锐度 (static facts α≈0, volatile α≈1)。query_time override + configurable half_life_days。+21 tests
- **Cycle 235: crystallize_intents()** — CogniFold 启发。社区密度超阈值时自动结晶为 intent 节点。intent 节点通过 'abstracts' 边链接所有成员。幂等 (重复运行跳过已结晶)。+17 tests
- **amg 2813→2860 (+47 tests), 228th consecutive day without rollback**
- **Cycle 226: Schultz + Modified Wiener Indices** — degree-sum-weighted distances + generalized W_λ exponent (default λ=-1)，+31 tests
- **Cycle 227: trace_decision_chain()** — TokenMizer-inspired supersede chain traversal with trigger/reason/evidence/timestamp per hop，+21 tests
- **Cycle 228: add_with_entropy_filter()** — SimpleMem-inspired write-time filtering (lexical diversity + length + novelty Jaccard)，+25 tests
- **Cycle 229: subgraph_by_edge_type()** — MAGMA-inspired orthogonal multi-graph view per relation type，+18 tests
- **Cycle 230: add_causal_edge() + get_causal_edges() + trace_causal_chain()** — ActMem-inspired causal edge layer. 5 typed relations (causes/prevents/conflicts_with/enables/depends_on), confidence scoring, evidence lists, BFS traversal forward/backward, cycle-safe. +55 tests
- **Cycle 231: spread_activation()** — Collins & Loftus (1975) spreading activation. BFS propagation with decay/threshold/max_hops/edge-weight/multi-seed. +36 tests
- **Cycle 232: generalized_randic_index(α) + zagreb_indices()** — Parametric R_α family (R_{-0.5}=Randić, R₀=m, R₁=M₂) + oldest degree-based descriptors M₁/M₂. Cross-relationship verified. +59 tests
- **amg 2568→2813 (+245 tests), 225th consecutive day without rollback**
- **acs Cycle 189: store_health_alert_config + quality_improvement_tracker** — Configurable per-dimension alert thresholds (set/list/check, severity classification) + closed-loop feedback tracking (record/summary/list, actual vs planned delta accuracy). Completes analytics pipeline: descriptive→diagnostic→predictive→prescriptive→**feedback+monitoring**. +31 tests
- **acs 2526→2557 (+31 tests), 189th consecutive day**

### 07-13 晚间~07-14 凌晨开发 (amg cycles 236-238, acs cycle 190)
- **Cycle 236: invalidate_cascade() + add(category=) + search_by_category()** — PLACEMEM cascade invalidation (BFS over depends_on+enables, cycle-safe, idempotent) + Apple Selective Memory category parameter (backward-compatible column migration) + category-filtered search。+20 tests
- **Cycle 237: read_proactive_context()** — CogniFold proactive context assembly。无 query 参数，基于 intent nodes 主动推送上下文。Pipeline: find intents → filter by active_intents → gather abstracted members → score by cache_temperature → deduplicate → per-intent context bundles。Completes proactive trilogy: crystallize_intents(c235) → read_proactive_context(c237)。+24 tests
- **Cycle 238: forgotten_index() + abc_index() + sum_connectivity_index()** — 三个 degree-based 拓扑指数。F=Σd³ (forgotten Zagreb sibling), ABC=Σ√((d_u+d_v-2)/(d_u·d_v)) (Atom-Bond Connectivity, more discriminating than Randić), χ_S=Σ1/(d_u+d_v) (additive counterpart to Randić multiplicative)。拓扑指数族扩展至十三族。+79 tests
- **amg 2860→2983 (+123 tests), 229th consecutive day without rollback**
- **acs Cycle 190: store_health_dashboard() + quality_improvement_batch_tracker() + alert_history()** — Executive dashboard (composes 6 APIs into one call: gauge+alerts+heatmap+forecast+improvements+recommendations+interpretation) + batch tracker (prefix-scoped multi-entry improvement tracking with snapshot comparison) + alert history (time-series delta-only logging of alert state changes)。Analytics pipeline: +executive +batch +time-series layers。+36 tests
- **acs 2557→2593 (+36 tests), 190th consecutive day**

### 07-11~07-12 开发 (amg cycles 221-225, acs cycle 188)
- **Cycle 221: Structure-Gated PPR** — SAGE-inspired propagation gating: centrality modulates signal flow (degree/betweenness/closeness/eigenvector/pagerank gates)，+31 tests
- **Cycle 222: Retrieval-Failure Logging + select_governed()** — SAGE reader-writer feedback: log/get/analyse/clear failures + MRMS-style three-stage governed selection pipeline，+44 tests
- **Cycle 223: Token-Budgeted Context Generation** — retrieve_token_budgeted(): greedy packing by score into token budget, no LLM calls (Mandol-inspired)，+24 tests
- **Cycle 224: retrieval_quality_eval()** — IR metrics harness: precision@k/recall@k/NDCG/MRR/F1/hit_rate，+31 tests。LoCoMo building block
- **Cycle 225: Szeged + Gutman Indices** — edge-partition + degree-distance topological descriptors，拓扑指数族扩展至七族，+31 tests
- **amg 2407→2568 (+161 tests), 218th consecutive day without rollback**
- **acs Cycle 188: Quality Heatmap + Mutation Impact** — diagnostic heatmap (6 dimension × entry matrix, 5-band classification) + prescriptive mutation_impact (5-action what-if simulator)，+28 tests。分析闭环完整: descriptive→diagnostic→predictive→prescriptive
- **acs 2498→2526 (+28 tests), 188th consecutive day**
- **Evening dev**: context-forge F42-F45 (API route detection + import health, +30 tests→613), agent-task-cli F187-F188 (ConcurrencyManager, +13 tests→1222)

### 07-09 深度研究: Agent Memory Benchmark Landscape
- Mem0 v3 在 BEAM contradiction_resolution 仅 35.7% — ADD-only 架构致命弱点
- LongMemEval-V2 (2026.05) 开辟 "agent experience memory" 新赛道
- Letta 转型 agent CLI，留下 self-hosted memory infra 市场真空
- amg 的 conflict+forget+consolidate 精准攻击 Mem0 弱点
- 下一步: 实现 LoCoMo benchmark adapter (target ≥ 30% overall)

### 07-04 深度研究 #002 + 开发 (6 cycles)
- **SOTA 2026 全景调研** — 五大范式(OS分层/Zettelkasten/生产平台/图原生/情景+RL)。MemRL: usefulness ≠ similarity。LRAT: 失败轨迹+15-19%。安全: 90%+可被poisoning。笔记: `catalyst-research/exploration-notes/2026-07-04-agent-memory-architecture.md`
- **Cycles 179-184**: cache_temperature/snapshot/warm/evict_cold, memorywire round-trip, scope-delete guard, staleness 3-factor, search_multi 4-path RRF, sleep_consolidate。1599→1652 tests, 零回滚175天

### 07-03 开发 (5 cycles)
- **Cycles 173-178**: Lamport clock + typed pub/sub, conflict detect/resolve/report, strategic_forget (Q值保护), LPA community detection + community_graph + modularity, community_profile + bridge nodes。1521→1599 tests, 零回滚174天

### 07-02 深度研究 #001 + 开发 (3 cycles)
- **Graph vs Vector 收敛于混合** — Mem0 v3 entity boost SOTA; MemoryArena recall≠agency; 遗忘被低估。笔记: `catalyst-research/exploration-notes/2026-07-02-graph-memory-agents.md`
- **Cycles 170-172**: KGE修复, bi-temporal validity (supersede/query_valid_at/get_history), Q-value TD-learning (update_q/reward/penalize/recall_with_q)。零回滚172天

### 07-01 研究
- **Graph-Enhanced Memory**: HippoRAG/2 PPR 20%, A-MEM 6×多跳, LazyGraphRAG 0.1%成本, Zep双时序KG。笔记: `catalyst-research/exploration-notes/2026-07-01-graph-memory-agentic-rag.md`
- **GitHub Trending**: codebase-memory-mcp(23K⭐) / Agent-Reach(48K⭐) / design.md(Google)
- **博客发布**: 「Agent 记忆的 2026 前沿」~2800字 ✅

### 07-16 晚间深度研究 #013: Agent Memory Evaluation Revolution — From Recall to Lifecycle Operations
- **MemOps** (arXiv:2607.12893, Jul 14) — Lifecycle memory operations benchmark。memory 不是静态事实集合而是 remember/forget/update/reflect 操作的生命周期。6 类探针(detection/target/transition/robustness/provenance/leakage)。关键发现：final-answer accuracy 掩盖 unsafe memory state。session-level >> turn-level retrieval。parametric memory 全线 unreliable。
- **The Compliance Trap** (arXiv:2607.10608, Jul 12, Johns Hopkins) — E-P-R (Entry-Propagation-Recovery) 轨迹框架。agents 在第一个决策点就 adopt conflicting memory。更强模型 = 更大绝对损害(compliance trap)。MemTrapBench benchmark。recovery 全线 weak。
- **PM-Bench** (arXiv:2607.12385, Jul 14, COLM 2026) — Prospective memory benchmark。执行延迟意图在未来 cue 出现时。GPT-5.4 仅 65.1% F1。无单一策略跨模型有效。amg 完全缺 prospective memory 维度。
- **PASB / Persistent Sycophancy** (arXiv:2607.10526, Jul 11-13) — 1600 tasks，测试 OpenClaw + Hermes-Agent。commit boundary = 关键转折点：session-only 45.0% → committed 71.9% (+27pp)。三种写入失败模式(status promotion/attribution removal/scope broadening)。agent sycophancy = state-writing governance 问题。
- **五维评估分类法**: Recall(solved) → Lifecycle(frontier) → Consumption(frontier) → Prospective(frontier) → Write Safety(frontier)。amg 仅评估 dimension 1。competitive opportunity：amg can be first npm lib with 5D evaluation。
- **Next: lifecycle_operation_eval() (~80 tests) + write_governance_check() (~50 tests)**。两个 runnable code demos 已验证 (MemOps validator + EPR detector)。研究笔记: [catalyst-research/exploration-notes/2026-07-16-agent-memory-evaluation-revolution.md]

### 07-17 晚间深度研究 #014: Self-Evolving Agent Memory — From Static Architectures to Meta-Adaptive Systems
- **MemGen** (arXiv:2509.24704, Sep 2025) — Generative latent memory。不检索条目而是生成 latent token 序列作为 memory。Memory Trigger (何时调用) + Memory Weaver (生成记忆)。比 ExpeL/AWM +38.22%，比 GRPO +13.44%。无监督下自发涌现 planning/procedural/working memory。
- **EvoMemBench** (arXiv:2605.18421, May 2026, HKUST-GZ) — 首个 self-evolving memory benchmark。两轴: in-episode vs cross-episode × knowledge vs execution。15 方法对比。发现：(1) long-context baselines 仍高度竞争 (2) 无单一 memory 形式全胜 (3) retrieval 赢知识密集，procedural 赢执行密集。amg 跨所有 5 族但未在此 benchmark 测评。
- **MemEvolve + EvolveLab** (arXiv:2512.18746, Dec 2025) — Meta-evolution: 不仅 evolve memory content，还 evolve memory ARCHITECTURE。EvolveLab 统一 12 系统为 encode/store/retrieve/manage 设计空间。+17.06% 改进。
- **MUSE-Autoskill** (arXiv:2605.27366, ByteDance, May 2026) — Skill 5-stage lifecycle (creation→memory→management→evaluation→refinement)。Per-skill memory 跨任务积累经验。Self-created skills 超越 human-authored (85.24% vs 81.17%)。Cross-agent transfer 51.90%。
- **SkeMex** (arXiv:2606.09365, Jun 2026) — Read-Write-Assess-Govern lifecycle。Value-aware retrieval (context-dependent utility)。Multi-branch repository (general/task-specific/action-level)。
- **Memp** (arXiv:2508.06433, ACL 2026 Findings, zjunlp) — Procedural memory 两级抽象 (step-by-step + script-level)。Stronger→weaker model skill transfer 有效。
- **FieldMem** (arXiv:2602.21220, Jan 2026) — PDE-based continuous field memory。Memories diffuse + thermodynamic decay + field coupling。LongMemEval +116% F1 multi-session, +43.8% temporal。Multi-agent >99.8% collective intelligence。
- **关键洞察**: (1) Memory architecture meta-adaptation is next frontier (2) EvoMemBench 是缺失的标准化 benchmark (3) Per-skill memory 是 npm 生态杀手特性 (4) Generative latent memory 威胁 retrieval-based 系统 (5) Physics-inspired decay outperforms exponential
- **amg 实现路径**: compress_to_skill() + retrieve_skills() + evolve_skill() + skill_bank_health() + govern_skill_bank() ~140 tests。Read-Write-Assess-Govern 映射到 amg 现有 Q-value + strategic_forget。
- **Code demo**: Read-Write-Assess-Govern lifecycle TypeScript, 已验证可运行
- **研究笔记**: [catalyst-research/exploration-notes/2026-07-17-self-evolving-agent-memory-meta-adaptive.md](catalyst-research/exploration-notes/2026-07-17-self-evolving-agent-memory-meta-adaptive.md)

### 近期研究一览 (详细笔记在 catalyst-research/exploration-notes/)
| 日期 | 主题 | 核心洞察 |
|------|------|----------|
| 07-15 | **Procedural Memory & Skill Extraction (#011)** | Experience Compression Spectrum: L0→L1→L2→L3 (5-500-1000×), cross-community citation <1%, "missing diagonal" = adaptive cross-level compression / Anything2Skill: SkillBank + structured Skill Contracts (invocation/contraindication/steps/constraints/confidence) → 98.85% qsv / MemSkill: meta-memory skills (how to remember, not what) + RL controller, HuggingFace #3 paper / AutoSkill: lifecycle v0.1→v0.1.1, OpenClaw integration exists / AutoRefine: skill decay without maintenance / amg = L1-only, kind="skill" exists but no procedural structure / Next: compress_to_skill + retrieve_skills + evolve_skill APIs ✅ |
| 07-17 | **Self-Evolving Agent Memory (#014)** | MemGen generative latent(+38.22%)/EvoMemBench 4-setting benchmark(15 methods)/MemEvolve meta-architecture(+17.06%)/MUSE 5-stage skill lifecycle(per-skill memory, self>human 85.24%)/SkeMex Read-Write-Assess-Govern/Memp ACL 2026 procedural/FieldMem PDE continuous(+116% F1)/amg spans all 5 EvoMemBench families/skill lifecycle ~140 tests ✅ |
| 07-16 | **Agent Memory Evaluation Revolution (#013)** | MemOps lifecycle ops(6 probes)/Compliance Trap E-P-R(更强模型=更大损害)/PM-Bench prospective(65.1% F1)/PASB persistent sycophancy(commit boundary +27pp)/5D taxonomy replaces 1D accuracy/amg=dim1 only→5D opportunity ✅ |
| 07-15 | **Structured Memory Pareto Frontier (#010)** | PRISM: training-free intent-aware edge costing + bundle search + LLM compression → 0.831 LoCoMo @ 22K tokens (13× less)/PlugMem (ICML 2026): knowledge-centric graph (propositional+prescriptive) → LongMemEval 90.2 SOTA, OpenClaw plugin shipped/Hippocampus: Dynamic Wavelet Matrix → 31× faster, 14× fewer tokens/信息密度 > recall@k/Pareto frontier is the new eval standard/amg gaps: intent-aware edges + procedural memory + density metrics + plugin distribution ✅ |
| 07-13 | **Proactive Memory & Geometric Time (#007)** | RoMem: 连续相位旋转+Semantic Speed Gate→几何阴影解决时间冲突 (SOTA ICEWS 72.6 MRR, MultiTQ 2-3×)/CogniFold: 三层CLS扩展(event→concept→intent) + 拓扑自组织涌现意图 (LoCoMo 81.23%, LongMemEval 93.0%)/SkillGraph: 技能图进化+组合关系/"不完美即机制"哲学/append-only>破坏性更新/三层proactive context window ✅ |
| 07-13 | **Context Engineering: Beyond Retrieval (#006)** | Apple: 全量历史比无记忆更差(71%<79%)/选择性持久化4类/SWE-MeM: 自适应压缩工具+Memory-aware GRPO 60.2% SWE-Bench/PLACEMEM: 记忆胶囊统一语义+KV cache 级联失效/ACL 2026: 检索-生成鸿沟 19-53% token节省/零token数据刷新14×加速 ✅ |
| 07-12 | **Retrieval-Reasoning Gap & Actionable Memory (#005)** | ActMem 因果图+反事实推理/SimpleMem 熵感知压缩 30×token/MAGMA 正交多图 ACL 2026/Write-Manage-Read 5家族/Survey: Memory≠RAG/因果边=检索→推理桥梁/写入时过滤>检索时排序 ✅ |
| 07-12 | **Session Graph Memory & Auditability Turn (#004)** | TokenMizer 14-node session graph/MOSS auditable-by-construction/Engram 83.6% vs 73.2% full-context/DocTrace hypergraph -53% compute/"Is GraphRAG Needed" retrieval-generation gap/decision chain = killer feature/Lean context > full context |
| 07-11 | **Memory Substrate Convergence (#003)** | MRMS 两轴 substrate 验证 amg/Mandol LoCoMo SOTA 92.21% 竞争窗口/select_governed() 三阶段 pipeline/retrieval_quality_eval IR metrics/structure-gated PPR ✅ |
| 07-10 | **Agent Memory Architecture Convergence** | MRMS 验证 amg SVG 架构/Nous 贝叶斯 Dimension 为 Q-value 升级路径/Memory Governance = 2026 共识/可运行贝叶斯惊喜代码 ✅ |
| 07-10 | Current-Flow Betweenness | 排序恒等式 O(n²d log n)/brute-force 5图验证/CF-closeness=info centrality 已实现/cycle 214 铺路完成 |
| 07-09 | Agent Memory Benchmark Landscape | Mem0 v3 BEAM contradiction 35.7%/LongMemEval-V2 新赛道/Letta 转型留真空/amg 精准攻击弱点 |
| 07-05 | A2A Trust & Reputation | 六信任模态(Brief/Claim/Proof/Stake/Reputation/Constraint)/EigenTrust全局传播/Beta贝叶斯更新/MAV多维验证/TrustEngineV2七算法代码已验证13tests pass |
| 07-05 | OTel GenAI Observability | gen_ai.* v1.41 4层 span/invoke_agent→chat→execute_tool/CostAggregator 6tests pass/属性迁移=机械化/MCP semconv v1.39+ |
| 07-02 | Graph-Structured Memory | Mem0 v3 entity boost SOTA/MemoryArena recall≠agency/遗忘被低估/混合架构收敛 |
| 07-02 | 知识整理+TDD | 3 cycles(bi-temporal+Q-value+KGE)/1521 tests/零回滚172天 |
| 07-01 | Graph-Enhanced Memory | HippoRAG/2 PPR 20%/A-MEM 6×多跳/LazyGraphRAG 0.1%成本/Zep双时序KG |
| 06-30 | Agent Memory Architecture | OS隐喻标准/图DB争议/自进化前沿/纯文本74%/过程性记忆未解 |
| 06-27 | Self-Evolving Graph Memory | ExpGraph PPR/Memory-R1 CRUD/DF-Leiden 105×/diffusion_retrieve已落地 |
| 06-27 | Bi-Temporal Agent Memory | MemStrata cosine AUROC=0.59不可能结果/确定性supersession/Type I+II invalidation |
| 06-26 | KV Cache as Agent Memory | KV cache=working memory/Prefix Barrier=BM25 Barrier/SIGARCH cache coherence |
| 06-26 | Knowledge Graph Embeddings | TransE 80-20法则/SeedER dense+graph/四路融合Text+BM25+Graph+KGE |
| 06-25 | Agentic Graph Memory 2026 | Mnemis dual-route/Graph-R1 RL/MRAgent reconstruction/structure>ranking |
| 06-25 | Vector Clocks → HLC | HLC O(1) vs VC O(N)/OR-Set add-wins/DVV pruning |
| 06-24 | MCP Memory Server Protocol | 三层产品架构: SDK→memorywire→MCP/官方server=JSON文件75K/wk |
| 06-24 | Agent Memory Benchmarks | recall已解/agency未解/BEAM-10M<50%/MemoryArena recall≠agency |
| 06-23 | Graph Reasoning | retrieve-reason-prune/npm零图推理库/HopRAG纯遍历>BMS25 45% |
| 06-23 | Test-Time Scaling | AdaMEM positive scaling/MemR³ evidence-gap/A-MAC 5因子admission |
| 06-22 | Dynamic Community Detection | DF-Leiden 10³×/CPM>Modularity/社区稳定性=10×成本差 |
| 06-22 | LLM KG Construction | Extract→Resolve→Retrieve/dependency-parser 94%质量0%成本 |
| 06-21 | Agent Memory Security | OWASP ASI06/4-layer defense/provenance DAG/80-95% ASR |
| 06-21 | Temporal KGs | Bi-temporal双时间线/fact invalidation≠deletion/volatility scoring |
| 06-20 | Compositional 3-Layer | MemRL Q-value/AgentFold folding/SSGM drift/governance 99.6% |
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
56. **Stronger model skills transfer to weaker models (Memp ACL 2026)** — Procedural memory built with strong models retains value when migrated。Two-level abstraction (step-by-step + script-level)。Cross-model skill portability is a feature, not side effect。

---

## Active Next Actions

### 🔴 最高优先级: npm Publish
- [ ] **agent-memory-graph: README + npm publish** — 3721 tests, 700+ APIs
- [ ] **agent-context-store: README + npm publish** — 2727 tests, 550+ APIs
- [ ] **structured-output-toolkit: README + npm publish** — 561 tests
- [ ] **agent-task-cli: README + npm publish** — 1222 tests

> ⚠️ Mandol (ISCAS+MSRA) 已发 paper+PyPI+GitHub，LoCoMo SOTA 92.21%。PlugMem 已有 OpenClaw plugin。竞争窗口收紧。

### 🟡 研究驱动 — 待实现
- [x] ✅ amg: lifecycle_operation_eval() — MemOps-style operation validator (#013). Cycle 254, +29 tests
- [x] ✅ amg: write_governance_check() — PASB-inspired commit boundary protection (#013). Cycle 252, +70 tests
- [x] ✅ amg: summarize_community() + community_overview() — GraphRAG community summaries (#012). Cycle 253, +40 tests
- [x] ✅ amg: query() adaptive routing — GraphRAG/LightRAG mode selection (#012). Cycle 258, +39 tests
- [x] ✅ amg: drift_search() — DRIFT hybrid search with question generation (#012). Cycle 256, +35 tests
- [ ] amg: compress_to_skill() + retrieve_skills() + evolve_skill() + skill_bank_health() + govern_skill_bank() — Read-Write-Assess-Govern lifecycle (SkeMex + MUSE + #014). ~+140 tests. **Self-created skills > human-authored (MUSE 85.24% vs 81.17%)**
- [ ] amg: EvoMemBench adapter — 4-setting benchmark (in-ep/cross-ep × knowledge/exec). **Priority over LoCoMo** (#014)
- [ ] amg: intent_aware_token_budgets() — serialize/retrieve mode-dependent budgets (basic=200, local=500, global=1000, drift=800, hybrid=600). MemFlow #015. ~+15 tests
- [ ] amg: screen_retrieval() — read-time security check (instruction-pattern detection in retrieved content). GhostWriter/AM-Sentry #015. ~+25 tests
- [ ] amg: query_confidence_score — confidence field in query() return for caller-side escalation. MemFlow Validator #015. ~+15 tests
- [ ] amg: seven_intent_taxonomy — expand 5 routes to MemFlow's 7 (add temporal-reasoning + constraint-validation). #015. ~+60 tests
- [ ] amg: three_layer_router_cascade — rules→SLM→keywords fallback. MemFlow #015. ~+40 tests
- [ ] amg: intent_aware_edge_cost() — PRISM intent routing (#010). ~+40 tests
- [ ] amg: procedural memory node type — PlugMem prescriptive knowledge (#010). ~+50 tests
- [ ] amg: memory_information_density() metric — PlugMem PMI density (#010). ~+25 tests
- [ ] amg: Bayesian Dimension 类型 — Nous 启发. ~250行
- [ ] amg: DF-Leiden 集成 — ~310行增量
- [ ] amg: reasoning_quality_eval() — 冲突检测率/因果链完整度
- [ ] amg: fact-level evaluation metrics — 参考 Engram
- [ ] LoCoMo benchmark adapter + full-context baseline reporting
- [ ] **amg README: 竞品对比表** — Mem0/Zep/Mandol/PlugMem/PRISM/Hippocampus + **GraphRAG/LightRAG positioning: security-first agent-native GraphRAG**

### 🟣 Deep Research #015 Findings (2026-07-17)
- **MemFlow** (arXiv:2605.03312): Route-then-compile pattern. 7 intent types → tiered retrieval + token budgets. 3-layer cascade router (rules→SLM→keywords, 87.7% accuracy). 2× SLM improvement. Disabling intent routing costs 18.7pp.
- **GraphBit** (arXiv:2605.13848): DAG-based deterministic orchestration. 3-tier memory isolation (ephemeral/structured/external). Rust engine: 0% hallucination, 11.9ms latency. 67.6% GAIA accuracy.
- **GhostWriter/AM-Sentry** (arXiv:2607.06595): 98% memory injection rate. Dual-layer defense (write policy + retrieval screen). Validates amg security positioning, identifies missing read-time screening.
- **笔记**: [catalyst-research/exploration-notes/2026-07-17-intent-driven-memory-orchestration.md](catalyst-research/exploration-notes/2026-07-17-intent-driven-memory-orchestration.md)

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
| 1 | agent-task-cli | 1222 | ✅ npm ready |
| 2 | agent-memory-graph | 3849 | ✅ npm ready, 六十四合一 + 全检索管线 + 拓扑指数十九族 + IR eval + governed selection + phantom detection + spreading activation + proactive context + cascade invalidation + immutable_store + compact_node + serialize + RelationIntegrityChecker + semantic_speed_gate + selective_filter + GA/AZI/Harmonic + Lorenz/Redefined-Randić/Redefined-Zagreb + SimHash dual-mode + deduplicate + write_governance_check + community_semantic_summary + query_global + drift_search + lifecycle_operation_eval + prospective_memory + query() 7-intent adaptive routing + intent_aware_token_budgets + screen_retrieval + query_confidence_score + govern_skill_bank + query_route_audit |
| 3 | agent-context-store | 2727 | ✅ npm ready, 全分析闭环(十八层)+trend-report+prediction-accuracy+preset-library (descriptive→diagnostic→predictive→prescriptive→feedback→monitoring→executive→batch→time-series→export→decay→correlation→diff→prediction→scorecard→trend→prediction-qa→presets) |
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
