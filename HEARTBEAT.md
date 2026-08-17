# HEARTBEAT.md - August 17, 2026 (Monday) — 02:00 AM update

## 待办任务

### 🔴 最高优先级（本周）
- [ ] **agent-memory-graph: README + PyPI/npm publish** — **9241 Python tests**, 970+ APIs, 40+ entropy APIs, 25-API classification suite + FINGEREntropy + PPR + multi_hop_reason + spreading_activation + activation_trace + competitive_spreading + SummaryTree + code-aware APIs + OWASP security suite (6) + amg-bench + OTel telemetry + MultiAgentMemoryGraph (MESI) + FastAppendQueue ✅ + consolidate() + retrieval quality family **COMPLETE** ✅ + attention (distribution/rebalance) + temporal trilogy + bi-temporal APIs (5) + forgetting_forecast + **Experience Compression Spectrum COMPLETE** ✅ + **GraphRAG API family COMPLETE** ✅ (extract_from_text → graphrag_query → graphrag_explain → graphrag_coverage_report) + knowledge_freshness_report + **GraphRAG-Bench 适配器 run_amg.py COMPLETE** (C439) + export_graphml (C438) + chunk_text 无损分块 (C440) + resolve_entity_variants (C445, 差距 6/6) + amg_bench_quality LongMemEval 适配器 (C447) + 熵双门 abstention (C448)。**⚠️ #068 审计：无 TS 实现（旧 "TS 7349" 幻影双计已删）；npm 裸名已被 LightHaru 占用，命名决策（scoped/amgraph）列为 human-blocked，须在 README 终稿前**
- [ ] **amg PyPI publish — 人工三步**（建独立 GitHub 仓 agent-memory-graph / PyPI 2FA + Trusted Publisher / twine upload）+ **④ npm 命名决策 (#068)**（裸名被占：`@robertsong2019/agent-memory-graph` 推荐 / `amgraph` / `agent-memory-graph-py`，均实测 FREE）— 技术前置 100% 完成 (#066)，与 PyPI 同为 human-blocked
- [ ] **agent-context-store: README + npm publish** — **2929 tests**, 600+ APIs
- [ ] **structured-output-toolkit: README + npm publish** — **571 tests**
- [ ] **agent-task-cli: README + npm publish** — **1570 tests**, F237

### 中优先级（本月）
- [ ] amg-bench: LongMemEval adapter + competitive scoring (harness skeleton done cycle 370, adapter design done Research #061)
- [ ] amg MCP server (stateless, 2026-07-28 compatible) — Research #043 ✅, #059 ✅, Python MCP now 16 tools
- [ ] amg OpenClaw plugin (~200 lines) — Research #063 ✅, fastest-growing distribution channel. Path B: Skill Extension (~60 lines)
- [x] amg: OTel GenAI instrumentation — Research #034 ✅, Research #053 ✅, **telemetry.py implemented Cycle 374** ✅
- [ ] amg PyPI publish (Python-first strategy)
- [x] lab/agent-observability: OTel GenAI alignment — Research #070 ✅ → **src/otel-genai.ts 落地 22:05 会话**（192→222 tests，导出边界适配器+lint CI 门禁，amg telemetry v2 同批完成）
- [ ] openclaw-langgraph-bridge: Gateway 集成测试 (261 tests)
- [ ] prompt-mgr: 继续 template management features (196 tests)

> 08-06~07 completed items archived to MEMORY.md.

## 系统状态
- **agent-memory-graph (Python)**: **9406 tests**（08-17 KO 验证：git HEAD 1d57ec2=C457；grep 9242 test funcs + 47 parametrize 吻合）— 970+ APIs。entropy + classification + FINGEREntropy + PPR + multi_hop_reason + spreading_activation (5-member family) + activation_trace ✅ + competitive_spreading ✅ + SummaryTree + code-aware + provenance (4) + OWASP security suite (6) ✅ + amg-bench ✅ (C446 repatriated) + MCP 16 tools ✅ + OTel telemetry ✅ (C446 repatriated: 8 methods incl search_graphrag) + MultiAgentMemoryGraph (MESI) ✅ + FastAppendQueue ✅ + flush_and_consolidate ✅ (确定性 tie-break C437) + ResidualExtractor ✅ + consolidate() NREM/REM ✅ + consolidation_status() ✅ + memory_interference_report() ✅ + knowledge_freshness_report() ✅ + retrieval quality family COMPLETE ✅ + attention ✅ + temporal trilogy ✅ + bi-temporal APIs (5) ✅ + forgetting_forecast ✅ + seeded RNG fix ✅ + Experience Compression Spectrum COMPLETE ✅ + GraphRAG API family COMPLETE ✅ + export_graphml ✅ + run_amg.py 适配器 ✅ + chunk_text ✅ + resolve_entity_variants ✅ + amg_bench_quality LongMemEval 适配器 ✅ + 熵置信双门 abstention ✅ + locomo_bench_quality LoCoMo 适配器 ✅ (C451) + when-question date resolution ✅ (C456) + temporal-arithmetic answer path ✅ (C457)。**⚠️ 08-16 审计 (#068)：旧台账 "(TS) 7349" 为幻影双计，已删——无 TS 实现（唯一真 TS = amg-mcp wrapper 1718 行/122 tests）**
- **agent-context-store**: **2929 tests**
- **structured-output-toolkit**: **571 tests**
- **agent-task-cli**: **1570 tests** — F237
- **context-forge**: **1458 tests** (F79, 21 dimensions)
- **nano-agent**: **1106 tests** — F66 (R19: search_wildcard/similar_to/touch+lru)
- **edge-agent-runtime**: **345 tests**
- **prompt-mgr**: **196 tests**
- **agent-cost-tracker**: **25 tests** (08-15 修复 export.js 死导入 + 格式化函数测试)
- **agent-mesh-network**: **373 tests** (355→373, taskStats/cancelTask/routingAnalytics)
- **四项目总计**: 11547 tests ✅（同口径 amg+sot+atc = 9406+571+1570）
- **全项目总计**: ~20227 tests（08-17 KO 统一口径：含 ctxpack 69/skill-doctor 64；与 MEMORY 对齐，旧值 ~20175 基 amg 9354）
- **零回滚率**: amg **294天** 🏆（按日历校正，KO 链 08-16=293；08-16~17 会话又报 293/295/296 漂移）/ acs 200天 🏆

## 近期活动 (08-17 晚 22:05 tool-development-evening)
- **agent-observability otel-genai.ts 落地** (commit 9705e4e): Research #070 next-action #1 完成，amg telemetry v2 (C461) 的同批对啓。src/otel-genai.ts（导出边界适配器：mapSpan 6-op 映射 / Opt-In 内容门控 env+flag / lintGenAiSpans 5 规则 CI 门禁 / exportGenAiOtlp OTLP-JSON / evaluationEventAttributes）+ index.ts re-export + README 章节。测试 **192→222 (+30)** 一次全绿零回归（TDD：先写 30 测试再移植验证过的原型，唯一改动=OTLP traceId 改为 per-span）。坑：git add 目录时扫入了 .understand-anything/ 面板静态资产（工具生成物，无害已入库，下次应先 .gitignore）

## 近期活动 (08-17 晚 cron 20:04)
- **Research #069 (20:00 早轮)**: LLM-as-Judge 立项 ✅（详见 MEMORY）
- **Research #070 (20:04 本轮, deep-exploration 重触发)**: OTel GenAI 语义约定快照 + amg/lab 双资产对齐 ✅ — 2026-06 约定迁仓（semantic-conventions-genai，无 tag，钉 c739977）；17 op 含 7 memory 动词，upsert_memory≡amg consolidate；双资产同源漂移（RFC vs registry）；导出边界适配器 E2E 验证（code/otel_genai_align.ts，7-span 真实工具包演示，lint PASS，零侵入）。Next: lab 落地 src/otel-genai.ts / amg telemetry v2 / 季度盯新仓首 tag。Tavily 配额仍耗尽（AnySearch 替代中）

## 近期活动 (08-17 凌晨 cron 00:41/01:27)
- **Cycle 456 (key-dev-2, be86830)**: amg 9354→9371 (+17)，when-question date resolution ✅ RETAINED。digit-seed 假说先被 A/B 证伪（干净 revert）；数据驱动 pivot：session dates 锚定 + 相对时间词解析 + habitual/eventive when 区分。**A/B: multi_hop 4→42/321 (10.5×)，no-adv 0.1032→0.1266**，检索/abstention 不变。坑：findall-with-groups 年份 bug（用 finditer+group(0)）；[Speaker] 前缀是主体证据不能剥
- **Cycle 457 (key-dev-3, ff02a43)**: amg 9371→**9406** (+35)，LME_s temporal arithmetic ✅ RETAINED。侦察发现 LME_s temporal 实为 duration/ordering 非 when 题；解锁=question_date+haystack_dates 结构化锚点→纯日历算术。**A/B: 133q 0.045→0.180 (4.0×)**，unresolved anchor 无伪造 fall-through。C456/C457 教训沉淀 insights #239-#241（类目标签+FORM 触发/无 LLM 时序机制族/cat5 名字拓扑不可分；注：主清单 236-240 系 08-16 PM 会话写入文件尾部块，已合并去重）
- **Next（C457 遗留）**: ① full-500 LME_s 带 temporal-arith（~20min→8月底新 overall reference）② fired-but-wrong 9 题取证（mention session vs event session 混淆）③ 博客候选 "temporal arithmetic without an LLM"

## 近期活动 (08-16 晚 cron 23:00)
- **Cycle 455 (key-development-1)**: amg 9329→**9354** (+25)，cat5 答案侧校验实验 ✅。subject_support_gate（零 LLM：主体缺席 ∧ 外名在场 ∧ 说话人≠主体 → abstain）+ speaker 守卫 + sweep_subject_gate + CLI。**决定性负发现（1986q 全量）**：① 朴素版 +36 cat5/−47 事实伤害 = 净负 11；② speaker 守卫后 1/446 fire = 净 0；③ 根因：**LoCoMo cat5 从主体自己的行伪造**（evidence dia_id 全指向主体 turn，外名只是呼语），与事实型第三方内容题（grandma/Sweden）在名字拓扑上同构——谓词级语义匹配是唯一剩余路径（嵌入/LLM judge）。延伸 C452：置信门+名字拓扑双双证伪。另发现 LoCoMo 类别标签噪声（cat5 伪装题泄漏进 multi_hop/open_domain，fire 前后皆错=零成本）。commit 464361a/c3a8085

## 近期活动 (08-16 晚 cron 22:16)
- **Cycle 454 (tool-development-evening)**: amg 9320→**9329** (+9)，双首跑②完成 ✅。① run_eval() per-question-haystack 评估器 + CLI --mode eval/--sweep-entropies（fresh adapter+graph per question 隔离保证；真实数据形状修复：bare-list sessions 归一化）② **LongMemEval_s_cleaned --limit 50 首跑**（零 LLM 协议，144s）：acc 0.360 / **retrieval_hit 0.780** / abstention 8% / 3821 tok/query；sweep none/0.85/0.90/0.95 → best=None 0.360（熵门对纯事实型 split 无增益，与 C452 结论一致：门是任务相关的）。类别：preference 1.0 / temporal 0.5 / ssu 0.348(hit 0.783) / kupdate 0.0(hit 1.0 — 检索强、抽取协议弱，LLM judge 才是 leaderboard 可比口径）。**双首跑②解除，仅剩① (ollama blocker)**。数据集 /tmp/lme_s.json (277MB，HF 直连成功)；报告 /tmp/lme_s50.json。commit 7d26bdd→1cd9639

## 近期活动 (08-16 晚 cron 20:05)
- **Research #067 (20:02-20:04 早轮)**: LoCoMo 适配器前置完成 ✅（详见下方条目）
- **Research #068 (20:05 deep-exploration 本轮)**: 发布前双审计 ✅ — ① **幻影指标曝光**："amg TS 7349" 不存在（635 TS/JS 文件零命中 4 个“TS 专属 API”；唯一真 TS=amg-mcp wrapper 1718 行/122 tests；数字=真身 Python 仓 08-06 冻结计数，与 code-lab 副本计数双计）。四项目 18731→11382，全项目 ~27411→~20062，台账已修正（MEMORY+HEARTBEAT，历史日志加注不重写）② **npm 名被占**：`agent-memory-graph`=LightHaru（TS，05-22 抢注，10天19版后弃坑）；`@robertsong2019/agent-memory-graph`/`amgraph`/`amg-graph` FREE；PyPI 全免费零阻塞 ③ "TS port" 伪任务已从 Next dev targets 移除 ④ count-from-truth 脚本落地（exploration-notes/code/publish_namespace_audit.py，双部分实测）。洞察 #233-#235，人工三步扩为四步（+npm 命名决策）

## 近期活动 (08-15 晚 ~ 08-16 AM)
- **Cycles 445-448 (overnight)**: amg Py 9079→**9241** (+162)，零回归，全部 push ✅
- **C447 amg_bench_quality.py** — LongMemEval 记忆质量适配器（Research #061 落地）：abstention gate（`_abs` 题型=竞品幻觉重灾区）+ exact_judge 零 API 成本 + tokens/query 指标。坑：子串匹配污染排序（love→lovely）→ 词边界+屈折形态匹配器
- **C448 熵置信双门 abstention** — Shannon 熵 over 证据分布，fires iff best≤weak ∧ norm_entropy≥thr ∧ **evidence≥3**。二路弱平局不 abstain（-seq latest-wins=update 语义）；≥3 路弱平=均匀猜测域。混合 fixture 0.80→1.00；sweep 零额外检索成本
- **C446**: telemetry+amg_bench 回迁真身仓（+79，谱系漂移修复）；坑：大文件插入前 `grep -n '^class '` 确认类边界
- **辅助线**: act 11→25（export.js 死导入崩溃修复）/ mesh 355→373 / nano R19 1076→1106
- **博客 4 篇/日（纪录）**: 驱逐保护 / 编码 Agent 基准全景 / 信息外置纪律蒸发 / GraphRAG 零成本评测 — 全部 Pages 200 ✅
- **Research #065** ✅: retrieval_eval 机制全解析+真实数据冒烟。**唯一阻塞=本机未装 ollama**（`ollama pull qwen2.5:7b` 即可跑零成本评测）；数据可 GitHub raw 直连；Evidence Recall 若 <0.3 → context 附加三元组
- **AI×Neuro #11**: Sparse Coding→SAE→Scaling Monosemanticity，已发飞书

## 近期活动 (08-15 晚 cron 23:00)
- **Cycle 446 (key-development-1)**: repatriate telemetry.py (C374) + amg_bench.py (C370) + 3 测试文件 + MemoryGraph enable/disable/telemetry_status() 集成层，从过期 C424 code-lab 副本回迁真身仓。适配：multi_hop_reason→search_graphrag（真身谱系无前者）；StreamingGraph 测试→子类测试；pyproject py-modules 登记（PyPI 路径）。+79 (9079→**9158**)，全量 120s 100%，零回归，**294 天** 🏆 commit 40bbc44。**修复结构性滞留**：HEARTBEAT 曾声称两者 ✅ 但真身仓实缺——功能清单与真身谱系存在谱系漂移（FINGEREntropy/StreamingGraph/multi_hop_reason 仅存在于 code-lab 谱系）。**解锁 amg-bench LongMemEval/LoCoMo adapter 路径**

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
1. ✅ ~~Cycles 367-457: security + bench + MCP + multi-agent + consolidation + retrieval QA + attention + temporal + Experience Compression + GraphRAG lifecycle + GraphRAG-Bench 适配器 + LoCoMo/LME_s 双基准 + 时序答案侧机制族~~ DONE
2. ⬜ README(agent-memory-graph) → npm publish + **amg PyPI 人工三步 + npm 命名决策** — **BLOCKED on human action**
3. ⬜ Next dev targets: **8月底双首跑①** GraphRAG-Bench Novel sample_100 retrieval_eval（唯一阻塞=`ollama pull qwen2.5:7b`，本机未装 ollama；**②已解除** C454 LME_s x50 首跑完成）/ full-500 LME_s run 带 temporal-arith（~20 min，新 overall reference）/ cat5+多跳残余→LLM judge 立项 / MCP registry publish / OpenClaw plugin。⚠️ ~~TS port of Python APIs~~ 已移除——#068 审计：无 TS 实现，须单独立项

## 上次检查
- **Knowledge org: 2026-08-17 02:00** — Integrated C454-457 (amg 9354→9406 verified vs git 1d57ec2; day counter 294 calendar-corrected, sessions drifted 293/295/296 again)。四项目 11547 / 全项目 ~20227（统一口径含工具循环 ctxpack/skill-doctor，修复 MEMORY-HEARTBEAT 交叉漂移 ~113）。新增 insights #236-#238。双首跑②标记解除。C455 已由 23:00 会话自写入 HEARTBEAT。
- **Knowledge org 验证轮: 2026-08-16 02:04** — 重复触发（同昨日模式）。02:00 轮已完整执行，本轮仅验证：①git HEAD~1 = a4fb5ca "Cycle 448 amg 9241" ✅ 且 02:00 knowledge-org 提交 5ba272e 已入库 ②experiments.tsv 链 9079→9158→9210→9241 三条记录完整 ✅ ③grep test 函数 9077 + parametrize ≈ 9241 吻合 ④四项目 18731 验算通过。无新活动（02:00 后仅 3 个知识文件变更）。无需修正项。
- **Knowledge org: 2026-08-16 02:00** — Integrated C445-448 (amg Py 9079→9241 verified vs git a4fb5ca; day counter normalized 293 per calendar, sessions had drifted to 294/295). nano 1106 / act 25 / mesh 373. 四项目 18731（修正 HEARTBEAT 错误值 18511）/ 全项目 ~27411. Fixed stale agent-mesh-network 505→373. 双首跑关键路径 + ollama blocker surfaced. 新增 insight #231/#232 (abstention 语义分界 / 子串污染+token 效率).
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
