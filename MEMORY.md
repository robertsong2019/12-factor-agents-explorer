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

## Current Focus (2026-07-12)

### Active Theme
Autoresearch 方法论实践 — amg **连续222天零回滚率** 🏆。

### 项目测试总量 (07-12 晚间快照)
| 项目 | Tests | APIs | 状态 |
|------|-------|------|------|
| agent-memory-graph | **2663** | 575+ | 四十三合一: 全检索管线 + 17 centrality + 拓扑指数八族(distance/degree/spectral/Laplacian/walk/edge-partition/degree-distance/Schultz+Modified-Wiener) + structure-gated PPR + retrieval-failure logging + token-budgeted context + IR quality eval + governed selection + Laplacian pseudoinverse + phantom detection + auto_forget + bi-temporal + Q-value + CRDT + community + decision-chain + entropy-filter + subgraph-by-edge-type + ... |
| agent-context-store | **2526** | 510+ | 三大管线完整+全分析闭环: Graph 12 / Quality 12 (action+velocity+cohort+heatmap) / Store 14 (longitudinal+predictive+prescriptive mutation-impact) |
| structured-output-toolkit | **561** | 4650+ lines | generation+validation+consensus+recovery+scoring+monitoring+versioning+cross-provider |
| agent-task-cli | **1222** | 190+ features | Cache+Storage+EventBus+ConcurrencyManager+merge |
| **四项目总计** | **6972** | — | — |

其他: openclaw-langgraph-bridge 261 / better-ralph-core 376 / lab/agent-observability 166 / context-forge 613 / nano-agent 314 / AMS v1.0-dev 645 / prompt-router 258

**全项目总计**: 7586+ tests (四核心 6972 + context-forge 613)

### 最高优先级
**README → npm publish** (四项目)。这是当前最大未交付价值。amg 定位: "beyond recall — agency-grade graph memory"。6877 tests across 4 projects, 全部 npm ready。⚠️ Mandol (LoCoMo SOTA 92.21%) 已在 paper+PyPI+GitHub，竞争窗口收紧。

### 07-12 晚间开发 (amg cycles 226-229)
- **Cycle 226: Schultz + Modified Wiener Indices** — degree-sum-weighted distances + generalized W_λ exponent (default λ=-1)，+31 tests
- **Cycle 227: trace_decision_chain()** — TokenMizer-inspired supersede chain traversal with trigger/reason/evidence/timestamp per hop，+21 tests
- **Cycle 228: add_with_entropy_filter()** — SimpleMem-inspired write-time filtering (lexical diversity + length + novelty Jaccard)，+25 tests
- **Cycle 229: subgraph_by_edge_type()** — MAGMA-inspired orthogonal multi-graph view per relation type，+18 tests
- **amg 2568→2663 (+95 tests), 222nd consecutive day without rollback**

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

### 近期研究一览 (详细笔记在 catalyst-research/exploration-notes/)
| 日期 | 主题 | 核心洞察 |
|------|------|----------|
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
13. **拓扑指数七族完整 = 图论工具链里程碑** — distance(Wiener/Hyper-Wiener/Harary) + degree(Randić/Balaban) + spectral(gap/energy/Estrada) + Laplacian(Kirchhoff/spanning tree/algebraic conn) + walk-based(subgraph/communicability/natural conn) + edge-partition(Szeged) + degree-distance(Gutman)。npm 生态零竞品。
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

---

## Active Next Actions

### 最高优先级: npm Publish (本周)
- [ ] **agent-memory-graph: README + npm publish** — 2407 tests, 530+ APIs, 三十七合一 + 全检索管线 + 完整拓扑指数族 + phantom detection
- [ ] **agent-context-store: README + npm publish** — 2498 tests, 500+ APIs, 37 层管线
- [ ] **structured-output-toolkit: README + npm publish** — 561 tests, 4650+ lines
- [ ] **agent-task-cli: README + npm publish** — 1167 tests

> ⚠️ **竞争窗口收紧 (07-11 研究)** — Mandol (ISCAS+MSRA) 已发 paper+PyPI+GitHub，LoCoMo SOTA 92.21%。MRMS 验证 amg 架构方向。npm 发布不再是可选项。

### 高优先级: 功能完善
- [ ] agent-memory-graph: Bayesian Dimension 类型 (cycle 214, ~150行src+~100行tests, 受 Nous 启发)
- [x] agent-memory-graph: 全检索管线完成 ✅ (cycles 207-212: PPR→auto_forget→hybrid RRF→graph_rerank→unified retrieve())
- [x] agent-memory-graph: Laplacian toolkit ✅ (cycle 213: natural_connectivity + effective_resistance + information_centrality + _laplacian_pseudoinverse infra)
- [x] agent-memory-graph: 14 centrality metrics ✅ (degree/eigenvector/betweenness/closeness/harmonic/percolation/pagerank/katz/subgraph/laplacian/PPR/natural_conn/effective_resistance/information)
- [x] agent-context-store: longitudinal analytics ✅ (cycle 186: snapshot_diff + velocity_tracker)
- [x] agent-task-cli: Cache/Storage/EventBus 扩展 ✅ (cycles 43-44, +29 tests)
- [x] structured-output-toolkit: batchSafe concurrency fix ✅ (cycle 208, +7 tests)
- [ ] agent-memory-graph: DF-Leiden 集成 (~190行+~120行增量)
- [x] agent-memory-graph: current-flow betweenness/closeness ✅ (cycles 214-218: full spectral+topological index family, 拓扑五族完整)
- [x] agent-memory-graph: pre-commit phantom commit detection ✅ (cycle 219: AST-based class shadowing guard, 37 tests, detected 10 known issues)
- [x] agent-memory-graph: Randić + Harary indices ✅ (cycle 220: 拓扑指数族补完)
- [x] agent-memory-graph: select_governed() 三阶段 governed selection ✅ (cycle 222: MRMS-style structured gates → vector recall → graph expansion, +21 tests)
- [x] agent-memory-graph: retrieval_quality_eval() IR metrics ✅ (cycle 224: precision@k/recall@k/NDCG/MRR/F1/hit_rate, +31 tests)
- [x] agent-memory-graph: Szeged + Gutman indices ✅ (cycle 225: edge-partition + degree-distance, +31 tests)
- [x] agent-context-store: quality_heatmap + mutation_impact ✅ (cycle 188: diagnostic + prescriptive, +28 tests)
- [ ] agent-context-store: store_health_alert_config (cycle 189 next)
- [ ] agent-context-store: quality_improvement_tracker (track executed plans vs actual impact)
- [x] agent-memory-graph: Schultz index + modified Wiener index ✅ (cycle 226: degree-sum + generalized W_λ, +31 tests)
- [x] agent-memory-graph: trace_decision_chain() ✅ (cycle 227: TokenMizer-inspired supersede chain, +21 tests)
- [x] agent-memory-graph: add_with_entropy_filter() ✅ (cycle 228: SimpleMem write-time filter, +25 tests)
- [x] agent-memory-graph: subgraph_by_edge_type() ✅ (cycle 229: MAGMA orthogonal view, +18 tests)

### 07-11 研究驱动的新任务
- [x] agent-memory-graph: structure-gated PPR ✅ (cycle 221: SAGE propagation gating, 5 gate metrics, +31 tests)
- [x] agent-memory-graph: retrieval-failure logging ✅ (cycle 222: SAGE reader-writer feedback loop, +23 tests)
- [x] agent-memory-graph: token-budget context generation ✅ (cycle 223: retrieve_token_budgeted, Mandol-inspired, +24 tests)
- [x] agent-memory-graph: IR quality eval ✅ (cycle 224: precision@k/recall@k/NDCG/MRR, +31 tests)
- [x] agent-memory-graph: Szeged + Gutman indices ✅ (cycle 225: edge-partition + degree-distance, +31 tests)
- [x] agent-context-store: heatmap + mutation_impact ✅ (cycle 188: diagnostic + prescriptive analytics, +28 tests)
- [ ] **amg README: 竞品对比表** — LoCoMo leaderboard (Mem0/Zep/MemOS/EverMemOS/Mandol/Engram), 定位 "beyond recall — agency-grade graph memory"

### 07-12 深度研究 #005 驱动的新任务
- [ ] **agent-memory-graph: `add_causal_edge(from, to, relation, confidence)` API** — ~60行src+30行tests。5种关系(causes/prevents/conflicts_with/enables/depends_on)。对标 ActMem (arXiv:2603.00026)。ActMemEval benchmark 评估冲突检测率。
- [x] agent-memory-graph: `add_with_entropy_filter()` ✅ (cycle 228: SimpleMem-inspired, lexical+novelty composite score, +25 tests)
- [x] agent-memory-graph: `subgraph_by_edge_type(type)` ✅ (cycle 229: MAGMA orthogonal view, +18 tests)
- [ ] agent-memory-graph: `reasoning_quality_eval()` API — 评估冲突检测率/因果链完整度。扩展 IR eval。
- [ ] agent-memory-graph: `trace_decision_chain(topic)` API — 遍历 supersede 链输出 trigger+reason+evidence per hop, 对标 TokenMizer why_decision, ~50行src+~20行tests
- [ ] agent-memory-graph: fact-level evaluation metrics (不止 IR, 还有 fact correctness), 参考 Engram per-category breakdown
- [ ] agent-memory-graph: context engineering layer (检索结果 → 最优上下文组织), 参考 TokenMizer 14-node-type serialization
- [ ] LoCoMo benchmark: 必须同时报告 full-context baseline (Engram 方法论: same answerer + same judge)

### 中优先级
- [ ] openclaw-langgraph-bridge: Supervisor 完善 — 261 tests, Gateway 集成测试
- [ ] lab/a2a-trust-prototype: TrustEngineV2 (7算法集成)
- [ ] lab/agent-observability: gen_ai.* 属性 + CostAggregator — **研究完成 ✅ 07-05**, CostAggregator 代码已验证 (6/6 tests pass), 下一步: 写入 src/cost-aggregator.ts + 属性迁移
- [ ] AMS 生产化: EmbeddingProvider 真实接入
- [ ] MCP Memory Server: agent-memory-graph-mcp 包 ~200行

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
| 2 | agent-memory-graph | 2568 | ✅ npm ready, 四十合一 + 全检索管线 + 拓扑指数七族 + IR eval + governed selection + phantom detection |
| 3 | agent-context-store | 2526 | ✅ npm ready, 全分析闭环 (descriptive→diagnostic→predictive→prescriptive) |
| 4 | structured-output-toolkit | 561 | ✅ npm ready |
| 5 | openclaw-langgraph-bridge | 261 | 🔄 Supervisor 完善 |
| 6 | context-forge | 513 | 🔄 继续 features |
| 7 | lab/agent-observability | 166 | 🔄 OTel 集成 |
| 8 | nano-agent | 314 | 🔄 Memory 扩展 |
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
