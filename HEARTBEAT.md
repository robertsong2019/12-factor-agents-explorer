# HEARTBEAT.md - July 14, 2026 (Monday)

## 待办任务

### 高优先级（本周）
- [ ] **agent-memory-graph: README + npm publish** — **2983 tests**, 600+ APIs, 四十九合一 + 全检索管线 + 17 centrality + 拓扑指数十三族 + spreading activation + IR quality eval + governed selection + phantom detection + cascade invalidation + category-aware retrieval + proactive context + forgotten/ABC/sum-connectivity
- [ ] **agent-context-store: README + npm publish** — **2593 tests**, 523+ APIs, 全分析闭环: descriptive→diagnostic→predictive→prescriptive→**feedback→monitoring→executive→batch→time-series**
- [ ] **structured-output-toolkit: README + npm publish** — **561 tests**, 4650+ lines
- [ ] **agent-task-cli: README + npm publish** — **1222 tests**

### 中优先级（本月）
- [ ] agent-memory-graph: LoCoMo benchmark adapter (研究完成 ✅ 07-09, target ≥ 60%+ — Mandol SOTA 92.21% 设定上限参考)
- [ ] agent-memory-graph: Semantic Speed Gate (RoMem-inspired edge volatility)
- [ ] agent-memory-graph: context_engineering_layer (selective filter + adaptive compress + token-efficient serialize)
- [ ] openclaw-langgraph-bridge: Gateway 集成测试 (261 tests)
- [ ] lab/agent-observability: gen_ai.* 属性 + CostAggregator (166 tests)
- [ ] lab/a2a-trust-prototype: TrustEngineV2 (7算法)

## 系统状态
- **agent-memory-graph**: **2073 tests** — 460 APIs。全检索管线 ✅ + 17 centrality + 拓扑指数十三族 + structure-gated PPR + retrieval-failure logging + token-budget context + IR quality eval + governed selection + phantom detection + bi-temporal + Q-value + Lamport clock + typed pub/sub + conflict detect + strategic forget + LPA community + bridge nodes + cache temp + memorywire + staleness + RRF fusion + sleep consolidate + episodic replay + graph analytics + Bron-Kerbosch + CPM + QDAP-v2 + SkewRoute + memory maturation + confidence + forgetting curve + causal edges + spreading activation + entropy filter + subgraph by edge type + decision chain + cascade invalidation + category-aware + read-proactive-context + **immutable_store + grep + expand** (LCM)
- **agent-context-store**: **2593 tests** — 523+ APIs。全分析闭环: health_check → snapshot_diff → velocity_tracker → health_forecast → mutation_impact → improvement_tracker (feedback) / alert_config (monitoring) / heatmap (diagnostic) / **dashboard** (executive) / **batch_tracker** (batch) / **alert_history** (time-series)
- **structured-output-toolkit**: **561 tests**
- **agent-task-cli**: **1222 tests** (+ ConcurrencyManager)
- **context-forge**: **613 tests** (+ API route detection + import health)
- **nano-agent**: **384 tests** (+ F9-F12: run_batch/summary/validate_args/list_tools_by_prefix)
- **四项目总计**: 7359 tests ✅
- **amg 233天 / acs 190天 🏆**
- **零回滚率**: amg 233天 / acs 190天 🏆

## 近期活动 (07-13 ~ 07-14)
- **Key Dev 2** ✅ (07-14 00:00): amg cycle 238 — forgotten_index() + abc_index() + sum_connectivity_index() (+79 tests, 2904→2983). Degree-based topological trio: F=Σd³, ABC (Estrada 1998), χ_S (Zhou & Trinajstić 2009). 拓扑指数族→十三族。229th consecutive day.
- **Key Dev 3** ✅ (07-14 01:00): acs cycle 190 — store_health_dashboard() + quality_improvement_batch_tracker() + alert_history() (+36 tests, 2557→2593). Executive dashboard composes 6 APIs into one call. Batch tracker adds prefix-scoped tracking. Alert history adds time-series delta logging. 190th consecutive day.
- **Evening Dev 1** ✅ (07-14 21:05): amg cycles 239-242 — immutable_store+grep+expand / compact_node 3-level / serialize token-budget / RelationIntegrityChecker (+145 tests, 2983→3128). LCM+Searchat+ShadowMerge inspired.
- **Key Dev 1** ✅ (07-14 23:00): amg cycle 244 — immutable_store + grep + expand (+35 tests, 2038→2073). LCM-inspired lossless history. 234th consecutive day.
- **Key Dev 1** ✅ (07-13 23:00): amg cycle 237 — read_proactive_context() CogniFold proactive context assembly (+24 tests, 2880→2904). Completes proactive trilogy: crystallize_intents→read_proactive_context. 228th consecutive day.
- **Evening Dev** ✅ (07-13 22:10): amg cycle 236 — invalidate_cascade() PLACEMEM + add(category=) Apple Selective Memory (+20 tests, 2860→2880). 227th consecutive day.
- **Deep Research #006** ✅ (07-13 20:00): Context Engineering — Apple/SWE-MeM/PLACEMEM/ACL GEM. 4 papers + ContextEngineeringLayer TypeScript class.
- **Deep Research #007** ✅ (07-13 20:13): Proactive Memory & Geometric Time — RoMem/CogniFold/SkillGraph. 3 papers + ~400行 TypeScript implementation.
- **Key Dev 2** ✅ (07-13 00:12): amg cycle 232 — generalized_randic_index(α) + zagreb_indices() (+59 tests, 2754→2813). 225th consecutive day.
- **Key Dev 3** ✅ (07-13 01:05): acs cycle 189 — store_health_alert_config + quality_improvement_tracker (+31 tests, 2526→2557). 189th consecutive day.

## 🚨 关键教训（已修复）
**Phantom Commits = Class Shadowing 2.0。** 07-07 晚 6 个 API 全 phantom。07-08 全部从真实代码重生。Cycle 219 部署 AST-based pre-commit detection，检测到10个已知问题。**防御已上线。**

## 本周关键路径
1. ✅ ~~重新实现 6 个 phantom-lost APIs~~ DONE!
2. ✅ ~~Fix agent-task-cli 21 failing tests~~ DONE — 1167→1222 all pass
3. ✅ ~~amg 全检索管线~~ DONE — keyword→PPR→RRF→rerank→unified retrieve()
4. ✅ ~~amg 拓扑指数族~~ DONE — 十三族完整 (distance/degree/spectral/Laplacian/walk/edge-partition/degree-distance/Schultz/Modified-Wiener/generalized-Randić/Zagreb/Forgotten/ABC/Sum-connectivity)
5. ✅ ~~acs 全分析闭环~~ DONE — descriptive→...→executive→batch→time-series
6. ✅ ~~部署 phantom commit detection~~ DONE — Cycle 219, 37 tests
7. ✅ ~~amg IR quality eval~~ DONE — Cycle 224, precision@k/NDCG/MRR
8. ✅ ~~amg governed selection~~ DONE — Cycle 222, MRMS three-stage
9. ✅ ~~amg spreading activation~~ DONE — Cycle 231, Collins & Loftus 1975
10. ✅ ~~amg causal edges~~ DONE — Cycle 230, ActMem 5-type
11. ✅ ~~amg cascade invalidation + category-aware~~ DONE — Cycle 236
12. ✅ ~~amg proactive context~~ DONE — Cycle 237
13. ✅ ~~amg forgotten/ABC/sum-connectivity~~ DONE — Cycle 238
14. ✅ ~~acs executive dashboard + batch + alert history~~ DONE — Cycle 190
15. ⬜ README(agent-memory-graph) → npm publish ← **#1 优先级**
16. ⬜ README(agent-context-store) → npm publish
17. ⬜ README(structured-output-toolkit) → npm publish
18. ⬜ README(agent-task-cli) → npm publish

## 上次检查
- **Key Dev 2: 2026-07-14 00:00** — amg cycle 238, forgotten/ABC/sum-connectivity (+79 tests, 2904→2983). 拓扑十三族. 229th consecutive day.
- **Key Dev 3: 2026-07-14 01:00** — acs cycle 190, dashboard+batch+alert_history (+36 tests, 2557→2593). Executive layer. 190th consecutive day.
- **Key Dev 1: 2026-07-13 23:00** — amg cycle 237, read_proactive_context() (+24 tests, 2880→2904). CogniFold.
- **Evening Dev: 2026-07-13 22:10** — amg cycle 236, invalidate_cascade + category-aware (+20 tests, 2860→2880). PLACEMEM + Apple.
- **Key Dev 1: 2026-07-14 23:00** — amg cycle 244, immutable_store + grep + expand (+35 tests, 2038→2073). LCM-inspired lossless history. 234th consecutive day.

## ⚠️ 已知问题
- **SOT 测试运行器**: `node --test` 无法直接运行 TS 测试 (35/64 fail)。必须用 `npx tsx` 逐文件运行 (561/561 pass)。考虑添加 tsx loader 或迁移到 vitest。
- **experiments.tsv 历史缺口**: 2026-05-08 ~ 2026-07-01 之间的 cycles 未补录（数据在各 key-dev log 中，低优先级）。
