# HEARTBEAT.md - August 6, 2026 (Thursday) — 02:11 AM update

## 待办任务

### 🔴 最高优先级（本周）
- [ ] **agent-memory-graph: README + npm publish** — **7349 TS + 2294 Python tests**, 1000+ APIs, 40+ entropy APIs, 25-API classification suite + FINGEREntropy + PPR + multi_hop_reason + spreading_activation + SummaryTree + code-aware APIs ✅
- [ ] **agent-context-store: README + npm publish** — **2898 tests**, 600+ APIs
- [ ] **structured-output-toolkit: README + npm publish** — **571 tests**
- [ ] **agent-task-cli: README + npm publish** — **1485 tests**, F226

### 中优先级（本月）
- [ ] amg-bench: Benchmark harness — Research #037 ✅, ready to implement
- [ ] amg: query_as_of(timestamp) — expose bi-temporal as first-class API (#033)
- [ ] amg MCP server (stateless, 2026-07-28 compatible) — Research #043 ✅, ~300 lines
- [ ] amg OpenClaw plugin (~200 lines) — fastest-growing distribution channel. ⚠️ TencentDB 已有 team-level asset sharing
- [ ] amg: OTel GenAI instrumentation — Research #034 ✅, ~50 lines telemetry module
- [ ] amg PyPI publish (Python-first strategy)
- [ ] context-forge: 继续 F80+ code analysis features
- [ ] lab/agent-observability: OTel GenAI alignment — Research #034 complete
- [ ] openclaw-langgraph-bridge: Gateway 集成测试 (261 tests)
- [ ] prompt-mgr: 继续 template management features (175 tests)

### 已完成 ✅ (08-06 PM Dev)
- [x] Cycle 370: **amg-bench** — Performance benchmark harness (BenchHarness + BenchmarkResult + run_bench). Add/link throughput + search/recall/multi_hop latency at scale tiers. Markdown/JSON/text output. Research #037 Python impl. +24 tests.

### 已完成 ✅ (08-06 AM)
- [x] Cycle 365: **Code-aware APIs** — function/class/file/module node types + explainCode() + recordCodeDecision() + impactAnalysis(). Research #044. +36 Python tests.
- [x] Cycle 366: **spreading_activation()** — ACT-R cognitive model (Anderson 1983). Fire-once BFS, threshold-gated. 5th retrieval paradigm. Research #049. +41 Python tests.
- [x] Cycle 358 TS: **classification_confidence_interval()** — Bootstrap CI (Efron 1979). 25th classification API. Per-class F1 intervals. Research #050. +35 TS tests.

### 已完成 ✅ (08-05 PM)
- [x] Research #047: **Streaming & Incremental Graph Entropy** — FINGER O(Δ) incremental. FINGEREntropy class ~200 lines. 5 insights (#201-205).
- [x] Research #048: **GraphRAG 2.0: Retrieval to Reasoning** — HippoRAG2 PPR, GFM-RAG, A-MEM, PathRAG. 2 code examples. 5 insights (#206-210).
- [x] amg cycle 361: **FINGEREntropy + personalized_pagerank() + multi_hop_reason()** — Streaming entropy + HippoRAG2 PPR + first reasoning API. +29 Python tests.
- [x] amg cycle 362: **enrich_node() + streaming_health()** — A-MEM retroactive enrichment. +10 tests.
- [x] amg cycle 363: **StreamingGraph** — Real-time FINGER tracking + anomaly detection. +9 tests.
- [x] amg cycle 364: **SummaryTree** — TiMem 5-level hierarchy + ProGraph residuals + HiMem reconsolidation. +39 tests. Research #045.
- [x] nano-agent F47: **Memory.resize** — 4 eviction strategies.
- [x] nano-agent F48: **Memory.search_similar** — SequenceMatcher similarity search.
- [x] AI×Neuroscience newsletter #8: World Models & Cognitive Maps.
- [x] AI×Neuroscience newsletter #19: Neural Manifold Geometry.

## 系统状态
- **agent-memory-graph**: **2294 Python tests** + **7349 TS tests** — 1000+ APIs。entropy framework (40+) ✅ + **25-API classification suite** ✅ + FINGEREntropy + StreamingGraph ✅ + PPR + multi_hop_reason ✅ + **spreading_activation** ✅ + **code-aware APIs** ✅ + SummaryTree ✅ + enrich_node ✅ + 4-API provenance/lineage ✅ + 4-API entropy scan ✅ + topology stats ✅ + adaptive forgetting ✅ + EntityResolver ✅ + MCP Day 1-5 ✅
- **agent-context-store**: **2898 tests** — 600+ APIs
- **structured-output-toolkit**: **571 tests**
- **agent-task-cli**: **1485 tests** — F226
- **context-forge**: **1458 tests** (F79, 21 dimensions)
- **nano-agent**: **791 tests** (F48 search_similar)
- **edge-agent-runtime**: **345 tests**
- **prompt-mgr**: **175 tests**
- **四项目总计**: 12303 tests ✅
- **全项目总计**: ~17100 tests
- **零回滚率**: amg **279天** 🏆 / acs 200天 🏆

## 近期活动 (08-06 AM)
- **Cycle 365**: Code-aware APIs — first code+experience unified memory. Node types + explainCode + recordCodeDecision + impactAnalysis. Research #044 implemented. +36 Python tests.
- **Cycle 366**: spreading_activation() — ACT-R cognitive science model. Fire-once BFS, threshold-gated propagation, decay per hop. Fundamentally different from PPR. Research #049. +41 Python tests.
- **Cycle 358 TS**: classification_confidence_interval() — Bootstrap percentile CI. 25th classification API. First uncertainty quantification tool. Research #050. +35 TS tests.
- **Competitive alert**: TencentDB-Agent-Memory (14.6K★, +3.6K/week) — 4-layer team memory with CodeGraph. amg's code-aware APIs now match this capability, plus entropy + classification + streaming remain unique differentiators.

## 本周关键路径
1. ✅ ~~Cycles 350-357: classification completion~~ DONE
2. ✅ ~~Research #047 + #048~~ DONE
3. ✅ ~~Cycles 361-364: FINGEREntropy + PPR + multi_hop_reason + SummaryTree~~ DONE
4. ✅ ~~Cycles 365-366 + 358 TS: code-aware + spreading_activation + confidence_interval~~ DONE
5. ⬜ README(agent-memory-graph) → npm publish — **BLOCKED on human action**
6. ⬜ Next dev targets: amg-bench / MCP server / OpenClaw plugin / PyPI publish

## 上次检查
- **Knowledge org: 2026-08-06 02:11** — Added 08-06 AM dev section to MEMORY.md (cycles 365-366 Python + cycle 358 TS). Updated test counts (amg TS 7349, Python 2294, total ~17100). Marked code-aware + confidence_interval TODOs as done. Updated classification suite to 25 APIs. Day counter 279. HEARTBEAT refreshed.

## ⚠️ 已知问题
- **MEMORY.md size**: ~460 lines. Over 400 soft limit but content is active reference material (research tables, TODO lists, insights). Further archiving would reduce visibility of actionable items.
- **npm publish blocked**: All 4 projects test-ready (12303 tests). README writing needs human review.
- **Competitive pressure**: TencentDB-Agent-Memory growing fast (14.6K★, +3.6K/week). Has CodeGraph layer but amg now has code-aware APIs too. Entropy framework + 25-API classification + streaming + provenance remain differentiated.
- **experiments.tsv phantom (20th+ occurrence)**: Monitoring only per rule.
