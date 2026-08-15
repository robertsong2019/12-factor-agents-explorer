# HEARTBEAT.md - August 15, 2026 (Saturday) — 02:00 AM update

## 待办任务

### 🔴 最高优先级（本周）
- [ ] **agent-memory-graph: README + npm publish** — **7349 TS + 8942 Python tests**, 1000+ APIs, 40+ entropy APIs, 25-API classification suite + FINGEREntropy + PPR + multi_hop_reason + spreading_activation + activation_trace + competitive_spreading + SummaryTree + code-aware APIs + OWASP security suite (6) + amg-bench + OTel telemetry + MultiAgentMemoryGraph (MESI) + FastAppendQueue ✅ + consolidate() + retrieval quality family **COMPLETE** ✅ + attention (distribution/rebalance) + temporal trilogy + bi-temporal APIs (5) + forgetting_forecast + **Experience Compression Spectrum COMPLETE** ✅ + **GraphRAG API family COMPLETE** ✅ (extract_from_text → graphrag_query → graphrag_explain → graphrag_coverage_report) + knowledge_freshness_report + **GraphRAG-Bench 适配器 run_amg.py COMPLETE** (C439) + export_graphml (C438) + chunk_text 无损分块 (C440)
- [ ] **agent-context-store: README + npm publish** — **2929 tests**, 600+ APIs
- [ ] **structured-output-toolkit: README + npm publish** — **571 tests**
- [ ] **agent-task-cli: README + npm publish** — **1570 tests**, F237

### 中优先级（本月）
- [ ] amg-bench: LongMemEval adapter + competitive scoring (harness skeleton done cycle 370, adapter design done Research #061)
- [ ] amg MCP server (stateless, 2026-07-28 compatible) — Research #043 ✅, #059 ✅, Python MCP now 16 tools
- [ ] amg OpenClaw plugin (~200 lines) — Research #063 ✅, fastest-growing distribution channel. Path B: Skill Extension (~60 lines)
- [x] amg: OTel GenAI instrumentation — Research #034 ✅, Research #053 ✅, **telemetry.py implemented Cycle 374** ✅
- [ ] amg PyPI publish (Python-first strategy)
- [ ] lab/agent-observability: OTel GenAI alignment
- [ ] openclaw-langgraph-bridge: Gateway 集成测试 (261 tests)
- [ ] prompt-mgr: 继续 template management features (196 tests)

> 08-06~07 completed items archived to MEMORY.md.

## 系统状态
- **agent-memory-graph (TS)**: **7349 tests** — 1000+ APIs。entropy framework (40+) + 25-API classification ✅ + FINGEREntropy + StreamingGraph ✅ + PPR + multi_hop_reason ✅ + spreading_activation ✅ + code-aware ✅ + SummaryTree ✅ + enrich_node ✅ + provenance (4) ✅ + entropy scan (4) ✅ + adaptive forgetting ✅ + EntityResolver ✅ + MCP Day 1-5 ✅
- **agent-memory-graph (Python)**: **8942 tests** — 940+ APIs。entropy + classification + FINGEREntropy + PPR + multi_hop_reason + spreading_activation (5-member family) + activation_trace ✅ + competitive_spreading ✅ + SummaryTree + code-aware + provenance (4) + OWASP security suite (6) ✅ + amg-bench ✅ + MCP 16 tools ✅ + OTel telemetry ✅ + enable_telemetry() ✅ + MultiAgentMemoryGraph (MESI) ✅ + **FastAppendQueue ✅** + flush_and_consolidate ✅ (确定性 tie-break C437) + ResidualExtractor ✅ + consolidate() NREM/REM ✅ + consolidation_status() ✅ + memory_interference_report() ✅ + knowledge_freshness_report() ✅ + **retrieval quality family COMPLETE** (audit/explain/rerank/compare/trend) ✅ + attention (distribution/rebalance_plan) ✅ + **temporal trilogy** (changepoints/stability/velocity) ✅ + **bi-temporal APIs** (5) ✅ + **forgetting_forecast** ✅ + seeded RNG fix ✅ + **Experience Compression Spectrum COMPLETE** (extract_rules + compression_spectrum_report + rule_conflict_detect + rule_apply + rule_explain) ✅ + **GraphRAG API family COMPLETE** (extract_from_text + graphrag_query + graphrag_explain + graphrag_coverage_report) ✅ + **export_graphml ✅ (C438)** + **run_amg.py GraphRAG-Bench 适配器 ✅ (C439, 严格官方 schema)** + **chunk_text 无损分块 ✅ (C440)**
- **agent-context-store**: **2929 tests**
- **structured-output-toolkit**: **571 tests**
- **agent-task-cli**: **1570 tests** — F237
- **context-forge**: **1458 tests** (F79, 21 dimensions)
- **nano-agent**: **1076 tests** — F63
- **edge-agent-runtime**: **345 tests**
- **prompt-mgr**: **196 tests**
- **四项目总计**: 18432 tests ✅ (amg TS+Py + sot + atc = 7349+8942+571+1570)
- **全项目总计**: ~27050 tests
- **零回滚率**: amg **292天** 🏆 / acs 200天 🏆

## 近期活动 (08-15 晚 cron)
- **Cycle 445**: resolve_entity_variants() + run_amg resolve_entities 配置 — **GraphRAG-Bench 差距清单 6/6 全部关闭**（Gap #5 最后一项）。3 模式：case / title（任意位置敬称剥离+尾缀缩写）/ containment（词边界前缀，min_len 守卫，默认关）。canonical=最长规范化核心，平局→先添加；merge_entities+alias 注册；dry_run。+26 tests (9053→**9079**)，**294 天** 🏆
- ⚠️ amg Python 真身在 `projects/agent-memory-graph`（54k 行）；`code-lab/agent-memory-graph` 是过期 C424 副本（22.5k 行）——考古耗 8 分钟，选仓先验真身

## 近期活动 (08-14 PM ~ 08-15 AM)
- **Cycles 432-440 (9 cycles)**: GraphRAG-Bench 差距清单 6 关 5。C432 缩写安全切分 (+16) → C433/434 fact-answer 边宾语 (+30) → C435/436 coverage relation 维度 + monoculture 告警 (+26) → C437 consolidate 确定性 tie-break 修 13% flaky (+3) → C438 export_graphml (+12) → C439 run_amg.py 全量适配器 (+32) → C440 chunk_text 无损分块 (+29)。amg Python 8794→**8942**，**292 天** 🏆
- **关键性质 (C440)**: chunking 对 rule 抽取**无损** — 预算 ≥ 最长句时，单元/句子/E2E 三层结果与整文档一致；segment_sentences 成为抽取器与分块器的共享切分权威
- **nano-agent Round 17+18**: 1018→**1076** (+58)。F61 pin / F62 search_prefix / F63 partition + range_query/annotate/inspect_tools
- **博客**: 《Agent 记忆的快与慢：双系统写入模型的工程实践》发布 (GitHub Pages ✅ HTTP 200)
- **AI×Neuroscience #16**: 信息瓶颈理论（Tishby；2026-04 LLM 逼近 IB bound 论文）。⚠️ Tavily 月配额耗尽，已切 AnySearch 替代
- **GitHub 周报**: prime-agent (RLM 自我改进 Agent, +12.5k/周) / TencentDB-Agent-Memory 21.5k★（竞争加剧）/ semantica (PROV-O 可审计图基础设施 — 与 amg bi-temporal+provenance 叙事重叠，警惕)

## 近期活动 (08-14 AM)
- **Cycles 437-438 (23:00 cron)**: ① consolidate() 工作区确定性 tie-break（根油 13% flaky：随机 id × covering-index 字典序 × importance 全并列 → 随机 region；修复=(-imp, label ASC)，+3→8869）② export_graphml() 关闭 GraphRAG-Bench 差距 #3（indexing_eval 消费路径 networkx 往返验证，E2E extract→export→nx，+12→**8881**）。全量 100%，291 天。差距清单：#1✅#2✅#3✅，剩 #4 run_amg.py/#5 EntityResolver 配置/#6 chunking。
- **Research #064**: GraphRAG-Bench (ICLR 2026) 参赛路径 — 适配器雏形实测验证（rule 索引 + graphrag_query + 官方 schema）。差距清单 6 项（缩写保护 ~20行 / 边宾语提取 ~30行 / export_graphml ~20行 / run_amg.py ~150行）。Cycle 432+ 候选。
- **Cycle 430**: graphrag_explain() — diagnostic companion to graphrag_query. Per-keyword match types, score decomposition, path reconstruction, coverage analysis, suggestions. +60 tests (8683→8743). 291st day.
- **Cycle 431**: graphrag_coverage_report() — global KG health diagnostic. Label/tag coverage, keyword index, orphan rate, degree stats, matchability tiers, sparse nodes, composite health score, suggestions. +51 tests (8743→8794). 291st day.
- **GraphRAG API family COMPLETE**: extract_from_text → graphrag_query → graphrag_explain → graphrag_coverage_report.

## 近期活动 (08-13 PM)
- **Cycles 425-429**: FastAppendQueue (System-1/System-2) + knowledge_freshness_report + FastAppendQueue extended + peek/E2E + extract_from_text + graphrag_query. +168 tests (8505→8673→8683 with 429).
- **nano-agent Round 17**: F58-F60 (search_boolean/condense/export_markdown_table). +27 tests (991→1018).
- **Research #062**: GraphRAG 2026 全景与 amg 定位.
- **Research #063**: OpenClaw Plugin Architecture for amg.
- **AI×Neuroscience #10**: 类脑计算芯片 (Neuromorphic Hardware).

## 近期活动 (08-12 PM ~ 08-13 AM)
- Cycles 420-424: Experience Compression Spectrum COMPLETE. +150 tests.

## 近期活动 (08-11 PM ~ 08-12 AM)
> Cycles 408-415: Temporal trilogy + bi-temporal APIs + retrieval quality family COMPLETE.

## 近期活动 (08-09~08-10)
> Cycles 384-407: Multi-agent (MESI) + consolidation + retrieval quality + attention.

## 本周关键路径
1. ✅ ~~Cycles 367-440: security suite + bench + MCP + multi-agent + consolidation + retrieval QA + attention + temporal + Experience Compression + GraphRAG lifecycle + GraphRAG-Bench 适配器~~ DONE
2. ⬜ README(agent-memory-graph) → npm publish — **BLOCKED on human action**
3. ⬜ Next dev targets: **8月底 HF Novel sample_100 retrieval_eval 首跑**（零 API 成本，参赛关键路径）/ GraphRAG-Bench #5 EntityResolver 配置（可选，最后一项）/ MCP registry publish / OpenClaw plugin / amg-bench LoCoMo adapter / TS port of Python APIs

## 上次检查
- **Knowledge org 验证轮: 2026-08-15 02:04** — 重复触发；核心更新已由 02:00 run 完成（cycles 432-440, amg 8942, 292d）。本轮修正：MEMORY.md 3 处过时计数（atc 1548→1570/F237；amg Py 2294→8942；12223→18432）+ HEARTBEAT 18284→18432；**experiments.tsv 回填 nano-agent R17/R18 三行**（1018→1076，08-13/14 会话遗漏，实际 158 行而非 summary 所称 239 行，末条原为 08-12）。
- **Knowledge org: 2026-08-15 02:00** — Integrated cycles 432-440 (amg Py 8794→8942, 292nd day, +148)。nano-agent 1018→1076。GraphRAG-Bench 差距清单 5/6 关闭（仅剩 #5 可选）。四项目 18371→18432，全项目 ~27050。acs 统一为 2929（MEMORY 内部三处 2898 已修正）。8月底 Novel sample_100 retrieval_eval 已列为参赛关键路径。
- **Previous: 2026-08-14 02:03** — Verified all counts current. Fixed snapshot label 08-12→08-14. No new changes since 02:00 knowledge-org run. GraphRAG lifecycle + FastAppendQueue milestones confirmed. 291st day.
- **Previous: 2026-08-14 02:00** — Updated amg Python 8505→8794. nano-agent 791→1018. Research #062+#063. Full total ~26809.

## ⚠️ 已知问题
- **MEMORY.md size**: ~630 lines. Over 400 soft limit but content is active reference material. Further archiving would reduce visibility of actionable items.
- **experiments.tsv 结构性缺口**: amg C410+ cycle 条目记录在项目仓内（code-lab/projects/agent-memory-graph），workspace experiments.tsv 仅记外部项目 — 补录可选，非阻塞
- **npm publish blocked**: All 4 projects test-ready (18432 tests). README writing needs human review.
- **Competitive pressure**: TencentDB-Agent-Memory growing fast (14.6K★). amg now has GraphRAG lifecycle + code-aware APIs + OWASP security suite as additional differentiators beyond entropy/classification/streaming.
- **experiments.tsv phantom (20th+ occurrence)**: Monitoring only per rule.
