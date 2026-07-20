# HEARTBEAT.md - July 21, 2026 (Tuesday)

## 待办任务

### 🔴 最高优先级（本周）
- [ ] **MCP Memory Server Phase 1: TS wrapper** — **STARTS TODAY (Day 1)**. Day-by-day blueprint in Research #021. 8 curated tools wrapping 785+ APIs. SDK v2 stable July 28.
  - Day 1 (today): 4 core tools — recall/remember/health/forget + resource subscriptions
  - Day 2: +2 quality tools (query/consolidate)
  - Day 3: +2 advanced tools (gaps/skills)
  - Day 4: HTTP transport
  - Day 5: Integration tests
- [ ] **agent-memory-graph: README + npm publish** — **4099 tests**, 785+ APIs, 七十一合一
- [ ] **agent-context-store: README + npm publish** — **2810 tests**, 575+ APIs, 二十三层
- [ ] **structured-output-toolkit: README + npm publish** — **561 tests**
- [ ] **agent-task-cli: README + npm publish** — **1299 tests**, F200

### 中优先级（本月）
- [ ] agent-memory-graph: compress_to_skill() (blueprint ready: cycles 272-274, ~115 tests)
- [ ] agent-memory-graph: EvoMemBench adapter (4-setting benchmark)
- [ ] openclaw-langgraph-bridge: Gateway 集成测试 (261 tests)
- [ ] lab/agent-observability: gen_ai.* 属性 + CostAggregator (166 tests)
- [ ] lab/a2a-trust-prototype: TrustEngineV2 (7算法)

### 已完成 ✅ (07-20~21)
- [x] amg cycle 271: semantic_cluster_detect() — group-level redundancy via clustering (+26 tests, 4073→4099). 247th day.
- [x] acs cycle 197: threshold_hysteresis_config — alert flapping fix (+26 tests, 2784→2810). 197th day.
- [x] amg cycle 270: query_explain() — search plan diagnostics (+39 tests, 4034→4073). 246th day.
- [x] nano-agent F22-F46: 25 features (+273 tests, 459→732). Export/cluster/stats/set-ops/prompt.
- [x] Deep Research #020: MCP SDK v2 Implementation Patterns
- [x] Deep Research #021: MCP Memory Server Source Analysis — 5-day Phase 1 blueprint
- [x] Blog: Cross-Modal Forgetting (~2800 words, GitHub Pages live)
- [x] README competitive comparison table (18 dimensions vs 5 competitors)

## 系统状态
- **agent-memory-graph**: **4099 tests** — 785+ APIs。七十一合一: dual-loop quality system FULLY COMPLETE ✅✅ (gap + redundancy + balance + auto_heal + auto_consolidate + semantic_cluster) + evaluation quartet ✅ + query_explain ✅ + 全检索管线 ✅ + query() 7-intent + screen_retrieval + govern_skill_bank + 19 centrality + 拓扑指数十九族 + immutable_store + compact_node + serialize + write_governance_check + drift_search + prospective_memory + SimHash dual-mode
- **agent-context-store**: **2810 tests** — 575+ APIs。全分析闭环(二十三层): **threshold sensitivity + hysteresis**: descriptive→diagnostic→predictive→prescriptive→feedback→monitoring→executive→batch→time-series→export→decay→correlation→diff→prediction→scorecard→trend→prediction-qa→presets→preset_recommend→prediction_tuning→preset_ensemble→threshold_sensitivity→**hysteresis_config**
- **structured-output-toolkit**: **561 tests**
- **agent-task-cli**: **1299 tests** — **F200 milestone** 🎯
- **context-forge**: **663 tests** (F48 tech debt)
- **nano-agent**: **732 tests** (F46 to_prompt)
- **四项目总计**: 8769 tests ✅
- **amg 247天 / acs 197天 🏆**
- **零回滚率**: amg 247天 / acs 197天 🏆

## 近期活动 (07-20 ~ 07-21)
- **Cycle 271** ✅ (07-21 00:00): amg — semantic_cluster_detect() group-level redundancy (+26 tests, 4073→4099). 96bf3b7. 247th day.
- **acs Cycle 197** ✅ (07-21 01:00): threshold_hysteresis_config — raise/clear bands (+26 tests, 2784→2810). 838781d. 197th day.
- **Cycle 270** ✅ (07-20 ~22:00): amg — query_explain() search diagnostics (+39 tests, 4034→4073). 4b5dd21. 246th day.
- **nano-agent F22-F46** ✅ (07-20 evening): 25 features (+273 tests, 459→732).
- **Research #020** ✅ (07-20 20:00): MCP SDK v2 patterns — stateless/outputSchema/MRTR/extensions/dual-transport.
- **Research #021** ✅ (07-20 20:18): MCP Memory Server source analysis — 5-day Phase 1 blueprint.
- **Blog** ✅ (07-20 05:00): Cross-Modal Forgetting (~2800 words). GitHub Pages live.
- **README** ✅ (07-20 04:00): Competitive comparison table (18 dimensions).

## 本周关键路径
1. ✅ ~~amg cycle 270: query_explain~~ DONE
2. ✅ ~~amg cycle 271: semantic_cluster_detect~~ DONE
3. ✅ ~~acs cycle 197: threshold_hysteresis_config~~ DONE
4. 🔴 **MCP Phase 1 Day 1: TS wrapper — STARTS TODAY** ← **#1 优先级**
5. ⬜ README(agent-memory-graph) → npm publish
6. ⬜ README(agent-context-store) → npm publish
7. ⬜ (optional) amg: compress_to_skill() — next major feature, blueprint ready

## 上次检查
- **Knowledge org: 2026-07-21 02:06** — experiments.tsv phantom fix (5th occurrence, 8 entries recovered). MEMORY.md slimmed: 07-17~18 cycle details condensed (379→365 lines). All counts verified: amg 4099 / acs 2810 / four-core 8769 / all 12222.

## ⚠️ 已知问题
- **experiments.tsv phantom (5th occurrence)**: Cycles 270-271, acs 197, nano-agent F22-F46, research #020-021, blog — all 8 entries missing after cron key-dev tasks. Manually recovered. Root cause: cron key-dev tasks write to experiments.tsv but entries don't persist (likely file handle race or process isolation). **Permanent rule**: all experiments.tsv writes must be verified by read-back. Consider atomic write (temp file + mv).
- **MEMORY.md 体积**: ~385 行。Threshold 400 行。下次 org 应归档 07-17 前的 cycle 细节。
- **SOT 测试运行器**: `node --test` 无法直接运行 TS 测试。必须用 `npx tsx` 逐文件运行。
