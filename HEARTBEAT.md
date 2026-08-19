# HEARTBEAT.md - August 19, 2026 (Wednesday) — 02:05 AM update

## 待办任务

### 🔴 最高优先级（本周）
- [ ] **agent-memory-graph: README + PyPI/npm publish** — **9579 Python tests**, 990+ APIs, 40+ entropy APIs, 25-API classification suite + FINGEREntropy + PPR + multi_hop_reason + spreading_activation + activation_trace + competitive_spreading + SummaryTree + code-aware APIs + OWASP security suite (6) + amg-bench + OTel telemetry + MultiAgentMemoryGraph (MESI) + FastAppendQueue ✅ + consolidate() + retrieval quality family **COMPLETE** ✅ + attention (distribution/rebalance) + temporal trilogy + bi-temporal APIs (5) + forgetting_forecast + **Experience Compression Spectrum COMPLETE** ✅ + **GraphRAG API family COMPLETE** ✅ (extract_from_text → graphrag_query → graphrag_explain → graphrag_coverage_report) + knowledge_freshness_report + **GraphRAG-Bench 适配器 run_amg.py COMPLETE** (C439) + export_graphml (C438) + chunk_text 无损分块 (C440) + resolve_entity_variants (C445, 差距 6/6) + amg_bench_quality LongMemEval 适配器 (C447) + 熵双门 abstention (C448)。**⚠️ #068 审计：无 TS 实现（旧 "TS 7349" 幻影双计已删）；npm 裸名已被 LightHaru 占用，命名决策（scoped/amgraph）列为 human-blocked，须在 README 终稿前**
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
- **agent-memory-graph (Python)**: **9579 tests**（C473，08-19 凌晨；experiments 链 9519→9545→9565→9574→9579）— 990+ APIs。entropy + classification + FINGEREntropy + PPR + multi_hop_reason + spreading_activation (5-member family) + activation_trace ✅ + competitive_spreading ✅ + SummaryTree + code-aware + provenance (4) + OWASP security suite (6) ✅ + amg-bench ✅ (C446 repatriated) + MCP 16 tools ✅ + OTel telemetry ✅ (C446 repatriated: 8 methods incl search_graphrag) + MultiAgentMemoryGraph (MESI) ✅ + FastAppendQueue ✅ + flush_and_consolidate ✅ (确定性 tie-break C437) + ResidualExtractor ✅ + consolidate() NREM/REM ✅ + consolidation_status() ✅ + memory_interference_report() ✅ + knowledge_freshness_report() ✅ + retrieval quality family COMPLETE ✅ + attention ✅ + temporal trilogy ✅ + bi-temporal APIs (5) ✅ + forgetting_forecast ✅ + seeded RNG fix ✅ + Experience Compression Spectrum COMPLETE ✅ + GraphRAG API family COMPLETE ✅ + export_graphml ✅ + run_amg.py 适配器 ✅ + chunk_text ✅ + resolve_entity_variants ✅ + amg_bench_quality LongMemEval 适配器 ✅ + 熵置信双门 abstention ✅ + locomo_bench_quality LoCoMo 适配器 ✅ (C451) + when-question date resolution ✅ (C456) + temporal-arithmetic answer path ✅ (C457) + telemetry v2 semconv 对齐 ✅ (C461) + judge_llm() 双口径+CLI ✅ (C462-464) + calibration_by_category ✅ (C465) + honest attribution ✅ (C466) + evidence-session coverage (answer_session_hit) ✅ (C467) + 锚定卫生 ✅ (C471) + 全图锚回退 ✅ (C472) + form-scoped seed breadth ✅ (C473)。**⚠️ 08-16 审计 (#068)：旧台账 "(TS) 7349" 为幻影双计，已删——无 TS 实现（唯一真 TS = amg-mcp wrapper 1718 行/122 tests）**
- **agent-context-store**: **2929 tests**
- **structured-output-toolkit**: **571 tests**
- **agent-task-cli**: **1570 tests** — F237
- **context-forge**: **1458 tests** (F79, 21 dimensions)
- **nano-agent**: **1156 tests** — F69 (R20: 序列协议 dunders/copy+content_hash/subscribe 事件钩子)
- **edge-agent-runtime**: **345 tests**
- **prompt-mgr**: **283 tests**（08-17 render 字面量 bug 修复 + F15 export_markdown；旧台账 196 系 07-31 后自然增长未记）
- **agent-cost-tracker**: **25 tests** (08-15 修复 export.js 死导入 + 格式化函数测试)
- **agent-mesh-network**: **373 tests** (355→373, taskStats/cancelTask/routingAnalytics)
- **四项目总计**: 11720 tests ✅（amg 9579 + sot 571 + atc 1570）
- **全项目总计**: ~20593 tests（08-19 KO 口径：amg 9579；obs 222/nano 1156/prompt-mgr 283 沿用修正台账）
- **零回滚率**: amg **296天** 🏆（KO 日历链：08-17=294 / 08-18=295 / 08-19=296，会话漂移勿沿用）/ acs 200天 🏆

## 近期活动 (08-19 晚 cron 21:00)
- **Cycle 477 (code-lab-evening)**: amg 9579→**9606+5** (+28) ✅。#075 i3 counting forms 原型→生产：4 个 prec≥0.5 机制（duration_sum/total_sum/number_total/argmax）分层接入，temporal 守卫+全量 haystack+conjunct 弃权+意图排除+numeric-first judge。Oracle A/B (n=133): **12/16 prec 0.75** vs 原型 12/28/0.43——oracle-parity 直接暴露 2 个真 bug（argmax 键序 "Market Thrive"、judge 词序敏感）。commit 8c085e4
- **Cycle 478**: 真实 lme50 A/B 完全相同（0.320/0.760/0.880）——**0/50 题匹配任何 counting form**：LME_s 单会话切片无多会话聚合题，form-gate 零成本（C473 外科哲学再证）。commit 48a86de
- **Cycle 479**: 删 memory_graph.py.new（209 行，6月遗留，内容在主文件 11206，零引用）——删代码得同结果。commit b1cc6f7
- 方法论收获：**oracle-parity（生产函数跑研究 fixture）比复现数字更强**——本次直接把 prec 0.43 提到 0.75。后续：#075 v3 venue+date 复合键解锁 entity_count；full-500 rerun 验证零成本结论。

## 近期活动 (08-19 凌晨 cron 02:05)
- **Cycle 473 (key-development-3, ac8d9a3/3e2476e)**: amg 9574→**9579** (+5)，form-scoped seed breadth ✅。取证 C467 的 12 个 ssa evhit miss：**10/12 ev_in_candidates=0**（evidence 命中 7-16 kw 但 weight-ordered `recall() LIMIT 5` 上游截断）；recall_form 匹配 48/500 全为 ssa → `recall_seed_k=40` 手术式 scope。**ssa-56 evhit 0.786→0.929**（44→52/56），exact 0.268 持平，temporal-133 0.271 零翻转（judge-corrected）。**决定性负发现**：全局 k=40 毁 temporal（36→14/133，mirror 行入窗）→ **检索超参不可全局调优，form 分类器即配置面**。坑：harness judge bug 读作代码回归（temporal 答案须走 temporal_arith_judge，plain exact_judge 报假 21-loss——先跑 pre==c473 对照暴露）。报告 /tmp/c473/ssa56_official.json。Next: ssa 答案侧 / multi_session counting forms（C474 候选）/ full-500 rerun

## 近期活动 (08-19 凌晨 cron 00:35)
- **Cycle 472 (key-development-2, 497f547)**: amg 9565→**9574** (+9)，temporal 全图锚回退 ✅。form 命中但窗内失败（缺锚 OR 双锚坍缩到同一 session——mirror/advice 行词法回声）→ 对全 haystack 重试。**C471 的“0.85 不可达因检索窗”归因修正：同会话坍缩才是主因**。temporal-133 exact 0.226→**0.271**（+6/0，fired 31→37），102 错题 taxonomy 落 experiments。报告 /tmp/lme_s_temporal133_c472.json。Next: #071 multi_session 聚合接管线（C473 候选）/ 桶 B 弃权路径 / ssa 覆盖

## 近期活动 (08-18 深夜 cron 23:00)
- **Cycle 471 (key-development-1, bbb3bb1)**: amg 9545→**9565** (+20)，锚定卫生三件套 ✅（#072 四件套落地版）。①引号/所有格 token 归一（'ibotta' 25 命中 0 修复）②确定性平局阶梯：区分度命中 > 泛词命中 > user-role > 过去时相 > 更晚日期（替换从未被审视的 first-max 列表位置裁决，暗中决定过 3/9 失败）③周单位 round-half-up。**temporal-133 A/B：fire 精度 0.679→0.774，exact 0.180→0.226，逐题零回归**（19→24 fired-correct；修复 b46e15ed/af082822/e072b769=引号×舍入堆叠栈/三新火全对）。**两个决定性发现**：(a) prefix-stem 试后回退——submitted↔submission 需 5 字符前缀而 instacart↔instagram 同在 5 碰撞、6 处分离（submit≠submis），无任何长度可分，且目标题本就窗口受限；(b) **周语义=round 7/7 全拟合**（13d→2w 20d→3w 23d→3w 30d→4w），floor 败 2 ceil 败 2——取证“包含式=ceil”假说被证伪。**0.85 目标运行时不可达**：b0863698/21adecb5 金锚行进不了 4000-token 检索窗（全量取证≠运行时可修性——headroom 在检索侧非锚定侧，Cycle 472 候选：temporal-form 触发的定向检索/窗口扩大）。报告 /tmp/lme_s_temporal133_c471_final.json

## 近期活动 (08-18 晚 cron 20:00/20:11)
- **Research #071 (20:00 早轮)**: Multi-Session 答案侧聚合立项 ✅（详见 MEMORY）
- **Research #072 (20:11 deep-exploration 本轮)**: fired-but-wrong 9 题取证 ✅ — honest qid 首个消费。**同日叙事天花板**：对照组 17/17 fired-correct 全部纯会话日算术；9 失败五桶（计划-事件 2 / 子会话日期 3 / 锚词 bug 2 / 周舍入 2 / 多金歧义 1），堆栈 bug 实证（引号×舍入），平局裁决暗中决定 3/9。Fix-locality：六题可确定性修 → fire 精度 0.679→0.893。Maps to Cycle 468 锚定卫生四件套（与 #071 合并排期）。Tavily 配额仍耗尽（AnySearch academic 域替代，HeidelTime TIMEX3/DCT 锚点获取）

## 近期活动 (08-18 凌晨 cron 01:00)
- **Cycle 467 (key-dev-3, 1ca1a28)**: amg 9507→**9519** (+12)，evidence-session coverage 指标 ✅。preference 题实为建议请求（truth=合成元描述）→ truth-containment hit 结构性永不触发（**structural zero 第二案**，C466 的"hit 0.000 检索盲区"读数是伪影）。解锁=数据集自带 answer_session_ids → answer_session_hit + None=不可解析不计 miss。**修正地图（full-500 重跑 /tmp/lme_s_full500_evhit.json）**：overall evhit **0.890**；multi_session evhit **0.955** vs exact 0.007（检索非瓶颈，**答案侧聚合=新头号确定性 headroom**）/ temporal 0.895 / kupdate 0.987 / ssa 0.786（唯一 sub-0.85 轴）/ preference 0.567。preference-marker rerank 假说被原型证伪弃用。Next：multi_session counting/listing forms 答案侧 / ssa 覆盖 / fired-wrong 取证（qid 可追溯）/ 博客候选 "when the metric can't fire"

## 近期活动 (08-18 凌晨 cron 00:00)
- **Cycle 466 (key-dev-2, 301e677)**: amg 9497→**9507** (+10)，honest attribution ✅。取证 C465 基准产物发现双缺陷：① run_eval 500 行 question_id 全为 "0"（单元素列表→索引 0；LME_cleaned 用 question_id 而非 id）② _classify_question 启发式把 419/500 误标 single_session_user（真 70），temporal 49 vs 真 133 → **C465 calibration_by_category 在幻影类目上分组**。修复：question_id 回退 + question_type/category 权威优先（未知类型诚实透传）。**修正版全量 reference（按题干 join，总量精确复现 0.140/0.194/0.378）**：temporal 0.061→**0.180（C457 在全量复现）** / ssu 0.343 / kupdate 0.256(calib 12 rescue/0 falsepass) / **preference 30q hit 0.000 = 新检索轴** / multi 0.008。坑：类别表先验归属再读数；get(key, default) 对字段方言静默降级。报告 /tmp/lme_s_full500_dual_corrected.json；Next：preference 检索轴 / temporal fired-wrong 取证已解锁（qid 可追溯）

## 近期活动 (08-17 深夜 cron 23:00)
- **Cycle 465 (key-development-1, 50c2e97)**: amg 9485→**9497** (+12)，calibration_by_category() ✅ — 类目级 exact-vs-LLM 分歧分解（Research #069 延伸），接入全部 4 个 dual 报告点（LME evaluate/run_eval + LoCoMo evaluate_sample/run_locomo）。全量 9497/9497 (122s)，零回归，294 天 🏆。**双产出：full-500 LME_s 新 overall reference 落地**（19min，dual judge+temporal-arith）：exact **0.140** / mock-llm 0.194 / hit 0.378 / div 0.11 rubric OK；类目分歧 kupdate 4 rescue/0 falsepass（单向：containment 过严）×ssu 30/13×temporal 7/1。**x50 A/B 复现 C454 0.360 精确一致**（temporal-arith on/off 均 0.360）→ 全量差距系数据组成（首 50 题易：hit 0.76 vs 0.378），非回归。报告 /tmp/lme_s_full500_dual.json；坑：基准运行进程导入旧代码 → per-category 用保存的 results 行事后计算（duck-typed 设计直接消化）；test_large_flush_performance 在基准负载下 >2s 假败（clean HEAD 复现），空闲后 1.68s 过——负载敏感 perf 断言，非回归。Next ② 解除

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
3. ⬜ Next dev targets: **ssa 答案侧（evhit 0.929 vs exact 0.268——C468 speaker-recall fires 率取证，同 forensics playbook）** / **multi_session counting forms（evhit 0.955 vs exact 0.007，全 benchmark 最大 gap——C474 候选）** / temporal 残余（桶 B 2 题弃权=C448 熵门答案侧推广；fire 30/37 中 7 错）/ full-500 rerun（C467 ssa reference 已 stale）/ 8月底双首跑① GraphRAG-Bench Novel sample_100 retrieval_eval（唯一阻塞=`ollama pull qwen2.5:7b`，本机未装 ollama）/ cat5+多跳残余→LLM judge 实测（机制 C462-465 全就位，等 ollama；C467 已证 multi_session 检索侧就绪 0.955）/ MCP registry publish / OpenClaw plugin。⚠️ ~~TS port of Python APIs~~ 已移除——#068 审计：无 TS 实现，须单独立项

## 上次检查
- **Knowledge org: 2026-08-19 02:05** — 补整合轮（02:00 轮后 5 分钟 C473 落盘）：amg 9574→**9579**（git ac8d9a3/3e2476e 验证，experiments.tsv 链完整 9519→…→9579）。C473 form-scoped seed breadth：ssa-56 evhit 0.786→0.929 + temporal 零翻转；**检索超参不可全局调优（form 分类器即配置面）= insight 级发现**。四项目 11720 / 全项目 ~20593。day counter 296 维持 KO 链（key-dev-3 会话报 297 系漂移，勿沿用）。
- **Knowledge org: 2026-08-19 02:00** — Integrated C471+C472 (amg 9565→9574 verified vs git 497f547；day counter 296=KO 链 08-17:294→08-19:296)。四项目 11715 / 全项目 ~20588。**#072 ceil 周语义假说被 C471 全拟合证伪（round-half-up 7/7）——研究结论入库后被更严拟合推翻的实证案例**；C472 又修正 C471 归因（同会话坍缩非缺锚——两轮“结论被下一轮修正”链）。遗忘工程研究重编号 #073（笔记头部自标 #072 系碰撞）+ MEMORY 补条目；temporal 锚定卫生 Timeline 项已关。experiments.tsv 链完整（项目仓 9519→9545→9565→9574）。
- **Knowledge org: 2026-08-18 02:00** — Integrated C461-467 (amg 9497→9519 verified vs git 1ca1a28/fac9190, full-suite 9519/9519 08-18 01:40；day counter 295 calendar-corrected，会话又报 295/297)。四项目 11660 / 全项目 ~20533（obs 222/nano 1156/prompt-mgr 283 台账修正）。新增 insights #242-#244（度量效度/归因验证/数据集 grounding）。**priority map 重写**：multi_session 答案侧聚合=新头号确定性 headroom，preference "检索轴"降级为度量伪影。
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
