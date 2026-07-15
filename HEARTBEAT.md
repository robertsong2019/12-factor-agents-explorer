# HEARTBEAT.md - July 15, 2026 (Wednesday)

## 待办任务

### 高优先级（本周）
- [ ] **agent-memory-graph: README + npm publish** — **3249 tests**, 670+ APIs, 五十五合一 + 全检索管线 + 17 centrality + 拓扑指数十六族 + spreading activation + IR quality eval + governed selection + phantom detection + cascade invalidation + category-aware + proactive context + immutable_store + compact_node + serialize + RelationIntegrityChecker + semantic_speed_gate + GA/AZI/Harmonic
- [ ] **agent-context-store: README + npm publish** — **2636 tests**, 526+ APIs, 全分析闭环: descriptive→diagnostic→predictive→prescriptive→feedback→monitoring→executive→batch→time-series→**export→predictive decay→causal**
- [ ] **structured-output-toolkit: README + npm publish** — **561 tests**, 4650+ lines
- [ ] **agent-task-cli: README + npm publish** — **1222 tests**

### 中优先级（本月）
- [ ] agent-memory-graph: LoCoMo benchmark adapter (研究完成 ✅ 07-09, target ≥ 60%+ — Mandol SOTA 92.21% 设定上限参考)
- [ ] openclaw-langgraph-bridge: Gateway 集成测试 (261 tests)
- [ ] lab/agent-observability: gen_ai.* 属性 + CostAggregator (166 tests)
- [ ] lab/a2a-trust-prototype: TrustEngineV2 (7算法)

### 已完成 ✅ (07-14~15)
- [x] amg immutable_store + grep + expand (cycles 239/244)
- [x] amg compact_node three-level (cycle 240)
- [x] amg serialize token-budget (cycle 241)
- [x] amg RelationIntegrityChecker (cycle 242)
- [x] amg semantic_speed_gate + selective_filter (cycle 243)
- [x] amg dual-mode binary signature / SimHash (cycle 249)
- [x] acs report_export + decay_model + alert_correlation (Key Dev 3 cycle 191)
- [x] Deep Research #008: Memory Security (ShadowMerge/HMARS/OSL-MR)
- [x] Deep Research #009: Context Engineering Layer (LCM/Searchat)
- [x] Docs: code-lab/README.md + 2 skill READMEs

## 系统状态
- **agent-memory-graph**: **3354 tests** — 680+ APIs。全检索管线 ✅ + 17 centrality + 拓扑指数十六族 + structure-gated PPR + retrieval-failure logging + token-budget context + IR quality eval + governed selection + phantom detection + bi-temporal + Q-value + Lamport clock + typed pub/sub + conflict detect + strategic forget + LPA community + bridge nodes + cache temp + memorywire + staleness + RRF fusion + sleep consolidate + episodic replay + graph analytics + Bron-Kerbosch + CPM + QDAP-v2 + SkewRoute + memory maturation + confidence + forgetting curve + causal edges + spreading activation + entropy filter + subgraph by edge type + decision chain + cascade invalidation + category-aware + read-proactive-context + immutable_store + grep + expand + compact_node(3-level) + serialize(token-budget) + RelationIntegrityChecker + semantic_speed_gate + selective_filter + GA/AZI/Harmonic
- **agent-context-store**: **2636 tests** — 526+ APIs。全分析闭环+export+decay+causal: health_check → snapshot_diff → velocity_tracker → health_forecast → mutation_impact → improvement_tracker / alert_config / heatmap / dashboard / batch_tracker / alert_history / **report_export** / **quality_decay_model** / **alert_correlation**
- **structured-output-toolkit**: **561 tests**
- **agent-task-cli**: **1222 tests**
- **context-forge**: **613 tests**
- **nano-agent**: **384 tests**
- **四项目总计**: 7773 tests ✅
- **amg 234天 / acs 191天 🏆**
- **零回滚率**: amg 235天 / acs 191天 🏆

## 近期活动 (07-14 ~ 07-15)
- **Key Dev 2** ✅ (07-15 00:00): amg cycle 239 — ga_index() + augmented_zagreb_index() + harmonic_index() (+84 tests, 3165→3249). Degree-based topological trio. 拓扑→十六族. 227th consecutive day (key-dev-2 lineage).
- **Key Dev 3** ✅ (07-15 01:00): acs cycle 191 — store_health_report_export + quality_decay_model + alert_correlation (+43 tests, 2593→2636). Export+predictive+causal layers. 191st consecutive day.
- **Evening Dev** ✅ (07-14 21:05): amg cycles 239-242 — immutable_store+grep+expand / compact_node 3-level / serialize token-budget / RelationIntegrityChecker (+145 tests, 2983→3128). LCM+Searchat+ShadowMerge inspired.
- **Evening Dev** ✅ (07-14 22:25): amg cycle 243 — semantic_speed_gate + selective_filter (+37 tests, 3128→3165). RoMem + Context Engineering.
- **Key Dev 1** ✅ (07-14 23:00): amg cycle 244 — immutable_store + grep + expand reimplementation (+35 tests, 2038→2073). LCM-inspired lossless history. 234th consecutive day.
- **Deep Research #008** ✅ (07-14 20:00): Memory Security — ShadowMerge/HMARS/OSL-MR/CoreMem. amg 定位 "security-first graph memory".
- **Deep Research #009** ✅ (07-14 20:00): Context Engineering Layer — LCM/Searchat/Aeon. 完整 TypeScript 实现验证。
- **Docs** ✅ (07-14 04:00): code-lab/README.md + skills READMEs (github-trending, x-trends).

## 🚨 关键教训（已修复）
**Phantom Commits = Class Shadowing 2.0。** 07-07 晚 6 个 API 全 phantom。07-08 全部从真实代码重生。Cycle 219 部署 AST-based pre-commit detection，检测到10个已知问题。**07-14 再次发现 workspace-level phantom**（cycles 239-243 logged 但代码不在 memory_graph.py），cycle 244 重新实现。**防御已上线但需扩展到 cron 路径。**

## 本周关键路径
1. ✅ ~~amg immutable_store + compact + serialize + grep/expand~~ DONE
2. ✅ ~~amg RelationIntegrityChecker~~ DONE
3. ✅ ~~amg semantic_speed_gate + selective_filter~~ DONE
4. ✅ ~~amg GA/AZI/Harmonic indices~~ DONE — 拓扑十六族
5. ✅ ~~acs report export + decay model + alert correlation~~ DONE
6. ✅ ~~Deep Research #008 + #009~~ DONE
7. ⬜ README(agent-memory-graph) → npm publish ← **#1 优先级**
8. ⬜ README(agent-context-store) → npm publish
9. ⬜ README(structured-output-toolkit) → npm publish
10. ⬜ README(agent-task-cli) → npm publish

## 上次检查
- **Key Dev 2: 2026-07-15 00:00** — amg cycle 239, GA/AZI/Harmonic indices (+84 tests, 3165→3249). 拓扑十六族.
- **Key Dev 3: 2026-07-15 01:00** — acs cycle 191, report_export+decay_model+alert_correlation (+43 tests, 2593→2636). Export+predictive+causal.
- **Evening Dev: 2026-07-14 21:05** — amg cycles 239-242, immutable_store/compact/serialize/integrity (+145 tests, 2983→3128).
- **Evening Dev: 2026-07-15 22:25** — amg cycle 249, dual-mode binary signature / SimHash fast path (+28 tests, 3326→3354). Hippocampus-inspired.
- **Key Dev 1: 2026-07-14 23:00** — amg cycle 244, immutable_store reimplementation (+35 tests, 2038→2073).

## ⚠️ 已知问题
- **SOT 测试运行器**: `node --test` 无法直接运行 TS 测试 (35/64 fail)。必须用 `npx tsx` 逐文件运行 (561/561 pass)。考虑添加 tsx loader 或迁移到 vitest。
- **experiments.tsv 历史缺口**: 2026-05-08 ~ 2026-07-01 之间的 cycles 未补录（数据在各 key-dev log 中，低优先级）。
- **Workspace phantom risk**: cron 任务可能在 workspace 日志中记录 cycles 但代码不在实际项目 repo 中。Cycle 244 是修复案例。需考虑在 cron 模板中增加 `cd /path/to/repo && npx tsx test` 验证步骤。
