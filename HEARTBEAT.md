# HEARTBEAT.md - July 12, 2026 (Sunday)

## 待办任务

### 高优先级（本周/下周）
- [ ] **agent-memory-graph: README + npm publish** — **2568 tests**, 560+ APIs, 四十合一 + 全检索管线 + 17 centrality + 拓扑指数七族 + IR quality eval + governed selection + phantom detection
- [ ] **agent-context-store: README + npm publish** — **2526 tests**, 510+ APIs, 全分析闭环: descriptive→diagnostic→predictive→prescriptive
- [ ] **structured-output-toolkit: README + npm publish** — **561 tests**, 4650+ lines
- [ ] **agent-task-cli: README + npm publish** — **1222 tests**

### 中优先级（本月）
- [ ] agent-memory-graph: LoCoMo benchmark adapter (研究完成 ✅ 07-09, target ≥ 60%+ — Mandol SOTA 92.21% 设定上限参考)
- [ ] agent-memory-graph: Schultz index + modified Wiener index (cycle 226)
- [ ] agent-context-store: store_health_alert_config (cycle 189)
- [ ] agent-context-store: quality_improvement_tracker (prescriptive feedback loop)
- [ ] openclaw-langgraph-bridge: Gateway 集成测试 (261 tests)
- [ ] lab/agent-observability: gen_ai.* 属性 + CostAggregator (166 tests)
- [ ] lab/a2a-trust-prototype: TrustEngineV2 (7算法)

## 系统状态
- **agent-memory-graph**: **2754 tests** — 595+ APIs。四十四合一。全检索管线 ✅ + 17 centrality + 拓扑指数八族(distance/degree/spectral/Laplacian/walk/edge-partition/degree-distance) + structure-gated PPR + retrieval-failure logging + token-budget context + IR quality eval (precision@k/NDCG/MRR) + governed selection (MRMS three-stage) + phantom detection + bi-temporal + Q-value + Lamport clock + typed pub/sub + conflict detect + strategic forget + LPA community + bridge nodes + cache temp + memorywire + staleness + RRF fusion + sleep consolidate + episodic replay + graph analytics + Bron-Kerbosch + CPM + QDAP-v2 + SkewRoute + memory maturation + confidence + forgetting curve + causal edges (ActMem 5-type) + spreading activation (Collins & Loftus 1975)
- **agent-context-store**: **2526 tests** — 510+ APIs。全分析闭环: health_check → snapshot_diff → velocity_tracker → health_forecast → **mutation_impact** (prescriptive) / benchmark → cohort_analysis → **heatmap** (diagnostic)
- **structured-output-toolkit**: **561 tests**
- **agent-task-cli**: **1222 tests** (+ ConcurrencyManager)
- **context-forge**: **613 tests** (+ API route detection + import health)
- **四项目总计**: 7063 tests ✅
- **amg 219天 / acs 188天 🏆**
- **零回滚率**: amg 224天 / acs 188天 🏆

## 近期活动 (07-11 ~ 07-12)
- **Key Dev 1** ✅ (07-12 23:00): amg cycle 231 — spread_activation() Collins & Loftus (1975) (+36 tests, 2718→2754). BFS activation propagation with decay/threshold/max_hops/edge-weight/multi-seed. 224th consecutive day.
- **Key Dev 2** ✅ (07-12 00:00): amg cycle 225 — szeged_index + gutman_index (+31 tests, 2537→2568). Edge-partition + degree-distance topological sub-families. 218th consecutive day.
- **Key Dev 3** ✅ (07-12 01:00): acs cycle 188 — quality_heatmap + store_health_mutation_impact (+28 tests, 2498→2526). Diagnostic + prescriptive analytics layers. 188th consecutive day.
- **Evening Dev** ✅ (07-12 22:25): amg cycle 230 — add_causal_edge() + get_causal_edges() + trace_causal_chain() (+55 tests, 2663→2718). ActMem 5-type causal relations + BFS traversal. 223rd consecutive day.
- **Key Dev 1** ✅ (07-11 23:05): amg cycle 224 — retrieval_quality_eval() IR metrics (+31 tests, 2506→2537). precision@k/recall@k/NDCG/MRR.
- **Evening Dev 2** ✅ (07-11 22:30): amg cycle 222 — select_governed() MRMS three-stage (+21 tests, 2485→2506).
- **深度研究 #003** ✅ (07-11 20:00): Memory Substrate Convergence — MRMS + Mandol LoCoMo SOTA 92.21%. 竞争窗口收紧。
- **Evening Dev** ✅ (07-11 22:00): context-forge F42-F45 (+30→613), agent-task-cli F187-F188 (+13→1222)
- **技术随笔** ✅ (07-11 05:02): 预测性分析文章发布到 GitHub Pages

## 🚨 关键教训（已修复）
**Phantom Commits = Class Shadowing 2.0。** 07-07 晚 6 个 API 全 phantom。07-08 全部从真实代码重生。Cycle 219 部署 AST-based pre-commit detection，检测到10个已知问题。**防御已上线。**

## 本周关键路径
1. ✅ ~~重新实现 6 个 phantom-lost APIs~~ DONE!
2. ✅ ~~Fix agent-task-cli 21 failing tests~~ DONE — 1167→1222 all pass
3. ✅ ~~amg 全检索管线~~ DONE — keyword→PPR→RRF→rerank→unified retrieve()
4. ✅ ~~amg 拓扑指数族~~ DONE — 七族完整 (distance/degree/spectral/Laplacian/walk/edge-partition/degree-distance)
5. ✅ ~~acs 全分析闭环~~ DONE — descriptive→diagnostic→predictive→prescriptive
6. ✅ ~~部署 phantom commit detection~~ DONE — Cycle 219, 37 tests
7. ✅ ~~amg IR quality eval~~ DONE — Cycle 224, precision@k/NDCG/MRR
8. ✅ ~~amg governed selection~~ DONE — Cycle 222, MRMS three-stage
9. ⬜ README(agent-memory-graph) → npm publish ← **#1 优先级**
10. ⬜ README(agent-context-store) → npm publish
11. ⬜ README(structured-output-toolkit) → npm publish
12. ⬜ README(agent-task-cli) → npm publish

## 上次检查
- **Key Dev 1: 2026-07-12 23:00** — amg cycle 231, spread_activation() Collins & Loftus 1975 (+36 tests, 2718→2754)
- **知识组织: 2026-07-12 02:03** — 所有测试计数已验证 (amg 2568 ✅, acs 2526 ✅, atc 1222 ✅, sot 561 ✅ via tsx). experiments.tsv 已补充 13 条历史记录。
- **Key Dev 2: 2026-07-12 00:00** — amg cycle 225, szeged+gutman indices (+31 tests, 2537→2568)
- **Key Dev 3: 2026-07-12 01:00** — acs cycle 188, heatmap+mutation_impact (+28 tests, 2498→2526)
- **Key Dev 1: 2026-07-11 23:05** — amg cycle 224, retrieval_quality_eval IR metrics (+31 tests)

## ⚠️ 已知问题
- **SOT 测试运行器**: `node --test` 无法直接运行 TS 测试 (35/64 fail)。必须用 `npx tsx` 逐文件运行 (561/561 pass)。考虑添加 tsx loader 或迁移到 vitest。
- **experiments.tsv 历史缺口**: 2026-05-08 ~ 2026-07-01 之间的 cycles 未补录（数据在各 key-dev log 中，低优先级）
