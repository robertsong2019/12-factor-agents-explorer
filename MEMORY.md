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

## Current Focus (2026-07-05)

### Active Theme
Autoresearch 方法论实践 — **连续175天零回滚率** 🏆。

### 项目测试总量 (07-04 快照)
| 项目 | Tests | APIs | 状态 |
|------|-------|------|------|
| agent-memory-graph | **1768** | 385+ | 32合一: graph algo+vector+BM25+Adaptive Fusion+RL Memory+CRDT+Consolidation+Workflow Memory+Graph Reasoning+Adaptive Retrieval+diffusion_retrieve(PPR)+Security+Bi-temporal+Q-value+Lamport clock+pub/sub+conflict detect+strategic forget+LPA community detection+community-aware retrieval+community profile+bridge nodes+cache temperature+memorywire format+scope-delete guard+temporal staleness+RRF multi-path fusion+sleep consolidation+episodic replay+graph analytics+memory diff |
| agent-context-store | **2253** | 500+ | 三大管线 37 层: Graph 12 / Quality 12 / Store 13 |
| structured-output-toolkit | **507** | 4650+ lines | generation+validation+consensus+recovery+scoring+monitoring+versioning+cross-provider |
| agent-task-cli | **986** | — | Cache+Storage+merge |
| **四项目总计** | **5514** | — | — |

其他: openclaw-langgraph-bridge 261 / better-ralph-core 376 / lab/agent-observability 166 / context-forge 513 / nano-agent 314 / AMS v1.0-dev 645 / prompt-router 258

### 最高优先级
**README → npm publish** (四项目)。这是当前最大未交付价值。

### 07-05 晚间开发 (4 TDD cycles, autoresearch cron)
- **Cycle 188: Batch Operations** — batch_create_nodes/batch_add_edges/batch_delete_nodes with transaction safety + ID/label resolution, +24 tests
- **Cycle 189: Link Prediction** — predict_links() using common-neighbors + Adamic-Adar + preferential-attachment scoring, +14 tests
- **Cycle 190: Weighted Shortest Path** — shortest_path_weighted() (Dijkstra) + path_cost() helper, +14 tests
- **Cycle 191: Path Enumeration** — all_paths() (DFS simple path enumeration with hop/limit pruning) + k_shortest_paths() (K lowest-cost paths), +15 tests
- **agent-memory-graph: 1701→1768 passed**, 零回滚率 177 天

### 07-05 晚间开发 (3 TDD cycles, autoresearch cron)
- **Cycle 185: Episodic Memory Replay** — retrieve_episodes() (temporal sequence retrieval with time-window/kind/neighborhood filters + gap tracking) + episode_timeline() (human-readable adaptive formatting s/h/d) + replay_from() (BFS forward/backward with hop+edge tracking)，+19 tests
- **Cycle 186: Graph Analytics** — graph_analytics() one-call dashboard: degree distribution (5 buckets), density, hub nodes (top-5), weight/Q-value stats, orphan detection, reciprocal edges, top relations, composite memory_health [0,1]，+14 tests
- **Cycle 187: Memory Diff** — diff_graph(other) structural diff (added/removed/changed nodes + edges, quarantine-aware) + diff_report() human-readable with truncation，+16 tests
- **agent-memory-graph: 1652→1701 passed**，零回滚率 176 天

### 07-04 晚间深度研究 #002
- **AI Agent Memory Architecture: SOTA 2026** — 20篇论文/系统全景调研。五大范式: OS启发分层(Letta/MemGPT) / Zettelkasten链接(A-MEM) / 生产平台(Mem0) / 图原生(Cognee/Zep) / 情景+RL(MemRL)。MemRL核心洞察: memory usefulness ≠ similarity, 用Q-value学习"过去有用的"记忆。LRAT(SIGIR 2026): 生产日志是未用训练资产, 失败轨迹也能+15-19%。LoCoMo审计: 6.4%答案错误, judge接受63%故意错误。安全: 90%+agent可被memory poisoning攻击, 对话纠正100%复发。笔记: `catalyst-research/exploration-notes/2026-07-04-agent-memory-architecture.md`

### 07-04 晚间开发 (6 TDD cycles, 两轮)

**第一轮 13:23-13:45:**
- **Cycle 179: Cache Temperature** — cache_temperature()/snapshot()/warm_cache()/evict_cold(), CPU-cache-inspired hot/warm/cold zones，+15 tests
- **Cycle 180: Memorywire Format** — to_memorywire_format()/from_memorywire_format() round-trip export/import，+8 tests
- **Cycle 181: Scope-Delete Guard** — delete_node_safe() prevents deleting nodes with live dependents，+5 tests

**第二轮 22:00-22:30:**
- **Cycle 182: Temporal Staleness** — staleness_score()/stale_nodes()/fresh_nodes()/refresh_node()，age+access+validity 三因子，+9 tests
- **Cycle 183: Multi-Path RRF Fusion** — search_multi() 4-path Reciprocal Rank Fusion (bm25/q_value/community/temperature)，+8 tests
- **Cycle 184: Sleep Consolidation** — sleep_consolidate() 相似低权重节点合并+边缘重定向+隔离，+8 tests
- **agent-memory-graph: 1599→1652 passed**，零回滚率 175 天

### 07-03 晚间开发 (3+3 TDD cycles)
- **Cycle 173: Lamport Logical Clock + Typed Pub/Sub** — lamport_clock()/event_log()/on()/off()，因果排序+响应式订阅，+17 tests
- **Cycle 174: Memory Conflict Detection** — conflict_detect() (entity-overlap + numeric-mismatch) + conflict_resolve() + conflict_report()，+11 tests
- **Cycle 175: Strategic Forget** — strategic_forget() 多标准置信度遗忘 (min_weight/max_age/kind/target_count) + Q值保护 + dry_run，+11 tests
- **Cycle 176-177: LPA Community Detection** — detect_communities() (Label Propagation + resolution) + community_of/members/stats + search_community (社区感知检索) + community_graph (超节点缩减) + _modularity() Q-score，+29 tests
- **Cycle 178: Community Profile + Bridge Nodes** — community_profile() (cohesion/bridge/representative labels/Q值) + community_bridge_nodes() (跨社区桥节点检测)，+10 tests
- **agent-memory-graph: 1521→1599 passed**，零回滚率 174 天

### 07-02 晚间开发 (3 TDD cycles)
- **Cycle 170: KGE 修复** — link_by_label() + search_hybrid kge_weight 集成，13 失败→0
- **Cycle 171: Bi-temporal validity** — valid_from/valid_to/txn_time + supersede() + query_valid_at() + get_history()，+17 tests
- **Cycle 172: Q-value scoring** — RL 启发 TD-learning: update_q_value/reward/penalize/recall_with_q/top_q_nodes，+19 tests

### 07-02 深度研究 #001
- **Graph-Structured Memory for AI Agents** — 20篇论文/系统调研。Graph vs Vector 收敛于混合+entity linking(Mem0 v3 移除graph用entity boost达SOTA); MemoryArena 证明 recall≠agency(LoCoMo 95%→40-60%); 遗忘是最被低估的memory operation。笔记: `catalyst-research/exploration-notes/2026-07-02-graph-memory-agents.md`

### 07-01 晚间研究
- **Graph-Enhanced Memory for LLM Agents** — GraphRAG → Agentic Memory → Temporal KG 演进。HippoRAG/2 海马体索引+PPR 20%提升; A-MEM Zettelkasten 6×多跳/85-93% token节省; LazyGraphRAG 索引成本0.1%; Zep/Graphiti 双时序KG; AriGraph 语义+情景一体化。笔记: `catalyst-research/exploration-notes/2026-07-01-graph-memory-agentic-rag.md`
- **GitHub Trending 分析** — codebase-memory-mcp(23K⭐, tree-sitter+知识图谱, 99% token节省) / Agent-Reach(48K⭐, 13平台接入) / design.md(Google, DESIGN.md规范) / CubeSandbox(腾讯, KVM microVM) / Orca(并行agent IDE) / OmniRoute(236+ provider聚合+token压缩)
- **博客发布** — 「Agent 记忆的 2026 前沿」~2800字, 已推送 GitHub Pages ✅

### 近期研究一览 (详细笔记在 catalyst-research/exploration-notes/)
| 日期 | 主题 | 核心洞察 |
|------|------|----------|
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
5. **npm 生态空白** — agent-memory-graph 可成为首个整合 graph algo+vector+BM25+CRDT+consolidation+workflow+temporal+security 的 TS 记忆库
6. **Recall benchmarks solved, agency benchmarks not** — README 应定位 "beyond recall"
7. **Bi-temporal validity is the missing dimension** — 3 列 + ~80 行即可补齐
8. **CRDT 是多 Agent 记忆同步的共识方案** — 「Agent Memory is a CRDT Problem」2026 三源汇聚
9. **memorywire-compatible 是 npm 发布战略加分项** — 采用 5 操作名
10. **Context Drift 65% 失败率** — Context Engineering 三原语(fold/squash/outline)已落地

---

## Active Next Actions

### 最高优先级: npm Publish (本周)
- [ ] **agent-memory-graph: README + npm publish** — 1554 tests, 350+ APIs, 十二合一
- [ ] **agent-context-store: README + npm publish** — 2253 tests, 500+ APIs, 37 层管线
- [ ] **structured-output-toolkit: README + npm publish** — 507 tests, 4650+ lines
- [ ] **agent-task-cli: README + npm publish** — 986 tests

### 高优先级: 功能完善
- [x] agent-memory-graph: bi-temporal validity tracking ✅ (cycle 171, +17 tests)
- [x] agent-memory-graph: Q-value scoring ✅ (cycle 172, +19 tests)
- [x] agent-memory-graph: KGE scoring ✅ (cycle 170, search_hybrid kge_weight)
- [x] agent-memory-graph: Lamport clock + pub/sub ✅ (cycle 173, +17 tests)
- [x] agent-memory-graph: conflict detection ✅ (cycle 174, +11 tests)
- [x] agent-memory-graph: strategic forget ✅ (cycle 175, +11 tests)
- [x] agent-memory-graph: LPA community detection ✅ (cycles 176-177, +29 tests)
- [x] agent-memory-graph: community profile + bridge nodes ✅ (cycle 178, +10 tests)
- [ ] agent-memory-graph: DF-Leiden 集成 (~190行+~120行增量)
- [x] agent-memory-graph: cache_temperature() API ✅ (cycle 179, +15 tests)
- [x] memorywire 兼容: toMemorywireFormat() + no-scope-delete guard ✅ (cycles 180-181, +13 tests)
- [x] agent-memory-graph: temporal staleness scoring ✅ (cycle 182, +9 tests)
- [x] agent-memory-graph: multi-path RRF fusion ✅ (cycle 183, +8 tests)
- [x] agent-memory-graph: sleep consolidation ✅ (cycle 184, +8 tests)
- [x] agent-memory-graph: episodic memory replay ✅ (cycle 185, +19 tests)
- [x] agent-memory-graph: graph analytics ✅ (cycle 186, +14 tests)
- [x] agent-memory-graph: memory diff ✅ (cycle 187, +16 tests)

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
| 1 | agent-task-cli | 986 | ✅ npm ready |
| 2 | agent-memory-graph | 1701 | ✅ npm ready, 三十一合一 |
| 3 | agent-context-store | 2253 | ✅ npm ready, 37层管线 |
| 4 | structured-output-toolkit | 507 | ✅ npm ready |
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
