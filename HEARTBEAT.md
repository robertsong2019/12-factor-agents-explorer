# HEARTBEAT.md - July 27, 2026 (Monday)

## 待办任务

### 🔴 最高优先级（本周）
- [ ] **agent-memory-graph: README + npm publish** — **4902 tests**, 850+ APIs, 八十合一
- [ ] **agent-context-store: README + npm publish** — **2898 tests**, 600+ APIs, 二十六层
- [ ] **structured-output-toolkit: README + npm publish** — **561 tests**
- [ ] **agent-task-cli: README + npm publish** — **1319 tests**, F203

### 中优先级（本月）
- [ ] agent-memory-graph: EvoMemBench adapter (4-setting benchmark)
- [ ] context-forge: 继续 F80+ code analysis features
- [ ] lab/agent-observability: OTel GenAI 对齐 (Research #023 ✅, 3 action items ready)
- [ ] openclaw-langgraph-bridge: Gateway 集成测试 (261 tests)
- [ ] lab/a2a-trust-prototype: TrustEngineV2 (7算法, Research #027 ✅ skeleton verified)
- [ ] amg: von_neumann_entropy() + spectral_entropy_profile() (Research #031 ✅, ~50 lines + ~80 tests)
- [ ] amg: TemporalEntropyTracker + entropy_trajectory() (Research #031 ✅, ~75 lines + ~90 tests)

### 已完成 ✅ (07-26~27)
- [x] amg cycle 297: entropy_weighted_retrieval() — entropy as retrieval signal (+11 tests, 5098→5109). **262nd day**
- [x] amg cycle 296: EntityResolver — alias management, duplicate detection, entity merging (+30 tests, 5068→5098). **262nd day**
- [x] amg cycle 288: renyi_entropy() + entropy_distance() — Rényi generalized + JSD graph distance (+77 tests, 4825→4902). **260th day**
- [x] amg cycle 287: entropy_guided_query_route() — entropy-aware retrieval (+52 tests, 4693→4745). **256th day**
- [x] amg cycles 283-286: Adaptive forgetting suite — compute_activation/apply_decay/forget_policy/soft_forget/cue_reactivation/security_purge (+110 tests). FSFM taxonomy + Oblivion pattern.
- [x] context-forge F79: analyzeDeadCode() — unreachable code, always-false branches, commented-out blocks (+20 tests, 1326→1346)
- [x] amg cycle 282: augmented_zagreb_entropy() + edge_betweenness_entropy() (+93 tests, 4479→4572). **255th day**
- [x] amg cycle 281: entropy_profile() + tsallis_entropy() (+85 tests, 4394→4479). **254th day**
- [x] Research #029: Multi-Agent Orchestration (coordination defects, LAMaS, Arbor)
- [x] Research #030: Adaptive Forgetting (entropy as forgetting signal = novel)
- [x] Research #027-028: TrustEngineV2 + Agent Planning
- [x] Knowledge org (07-26 02:04): insights #1-55 archived, MEMORY.md compressed 402→279 lines

## 系统状态
- **agent-memory-graph**: **5109 tests** — 860+ APIs。八十合一: **entropy framework** ✅ (17+ APIs: degree/distance/spectral) + **adaptive forgetting suite** ✅ + **entropy-guided query routing** ✅ + **EntityResolver** ✅ (alias/duplicate/merge) + **entropy-weighted retrieval** ✅ + MCP Day 1-5 ✅
- **agent-context-store**: **2898 tests** — 600+ APIs。二十六层 pipeline COMPLETE ✅
- **structured-output-toolkit**: **561 tests**
- **agent-task-cli**: **1319 tests** — F203
- **context-forge**: **1346 tests** (F79, 11000+ lines, 21 analysis dimensions)
- **nano-agent**: **732 tests** (F46)
- **amg-mcp**: **122 tests** — Phase 1 Day 5 complete ✅
- **prompt-weaver**: **223 tests**
- **四项目总计**: 9687 tests ✅
- **全项目总计**: 14022 tests
- **零回滚率**: amg 262天 🏆 / acs 200天 🏆

## 近期活动 (07-27)
- **Cycle 297** ✅ (22:30): entropy_weighted_retrieval() — entropy as retrieval signal. Novel differentiator. BM25 + per-node entropy weight blend. +11 tests (5098→5109). **262nd day**. cd36149.
- **Cycle 296** ✅ (22:25): EntityResolver — alias management, duplicate detection, entity merging. 7 APIs. Fills critical gap vs Mem0/Graphiti. +30 tests (5068→5098). **262nd day**. fed5e7c.
- **Cycle 288** ✅ (00:57): renyi_entropy() + entropy_distance() — Rényi (extensive generalized entropy, α→1=Shannon) + Jensen-Shannon divergence between graphs (first inter-graph method). +77 tests (4825→4902). **260th day**. d4c8fbd.

## 近期活动 (07-26)
- **Cycle 287** ✅ (22:18): entropy_guided_query_route() — entropy-aware retrieval. +52 tests (4693→4745). 256th day.
- **Cycles 283-286** ✅ (21:00-21:30): Adaptive forgetting suite. +110 tests (4583→4693). 256th-259th days.
- **context-forge F79** ✅ (23:00): analyzeDeadCode(). +20 tests (1326→1346). b1682c9.
- **Cycle 282** ✅ (01:00): AZI entropy + edge-betweenness entropy. +93 tests (4479→4572). 255th day.
- **Cycle 281** ✅ (00:00): entropy_profile() + tsallis_entropy(). +85 tests (4394→4479). 254th day.

## 近期活动 (07-25)
- **context-forge F67-F78** ✅: 12 features. 1054→1326 (+272 tests), 8684→10812 lines.
- **Research #027-028** ✅: TrustEngineV2 + Agent Planning.
- **amg c279-280** ✅: Randić/Zagreb/ABC/GA entropies. +125 tests.

## 本周关键路径
1. ✅ ~~amg c281-288: entropy framework + forgetting suite~~ DONE
2. ⬜ README(agent-memory-graph) → npm publish
3. ⬜ README(agent-context-store) → npm publish

## 上次检查
- **Knowledge org: 2026-07-27 02:03** — 02:00 run did heavy lifting (experiments.tsv synced, MEMORY.md + HEARTBEAT fully updated). 02:03 pass: consistency check ✅, entropy_guided_query_route marked done in #028, Current Focus date → 07-27. No new activity since 02:00.

## ⚠️ 已知问题
- **experiments.tsv phantom (12th occurrence)**: Cycles 283-288 + research #029-030 missing from central experiments.tsv. Recovered from project-level file. Root cause STILL unsolved after 12 occurrences. Pattern: project-level experiments.tsv gets written, central memory/experiments.tsv does not.
- **MEMORY.md 体积**: ~290 行。Threshold 400 行。Headroom comfortable ✅.
- **SOT 测试运行器**: `node --test` 无法直接运行 TS 测试。必须用 `npx tsx` 逐文件运行。
