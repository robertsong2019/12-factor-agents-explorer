# HEARTBEAT.md - August 28, 2026 (Friday) — 02:00 AM update

## 待办任务

### 🔴 最高优先级（本周）
- [ ] **agent-memory-graph: README + PyPI/npm publish** — **10040 Python tests**（08-26 collect 实测，C514 处首破 10,000 🎉）, 990+ APIs, 40+ entropy APIs, 25-API classification suite + FINGEREntropy + PPR + multi_hop_reason + spreading_activation + activation_trace + competitive_spreading + SummaryTree + code-aware APIs + OWASP security suite (6) + amg-bench + OTel telemetry + MultiAgentMemoryGraph (MESI) + FastAppendQueue ✅ + consolidate() + retrieval quality family **COMPLETE** ✅ + attention (distribution/rebalance) + temporal trilogy + bi-temporal APIs (5) + forgetting_forecast + **Experience Compression Spectrum COMPLETE** ✅ + **GraphRAG API family COMPLETE** ✅ (extract_from_text → graphrag_query → graphrag_explain → graphrag_coverage_report) + knowledge_freshness_report + **GraphRAG-Bench 适配器 run_amg.py COMPLETE** (C439) + export_graphml (C438) + chunk_text 无损分块 (C440) + resolve_entity_variants (C445, 差距 6/6) + amg_bench_quality LongMemEval 适配器 (C447) + 熵双门 abstention (C448) + past-perfect duration (C486/487) + order-family/pairwise which-first (C488/489) + 锚纪律两连 + TA first-kind 退役 (C493) + pairwise v2 三连：从句粒度/跨行 join/anaphora 购买汇报 (C490-C496) + **ECM neither-family (C497) + preference 诚实弃权 (C498) + item_total 枚举金额聚合 (C500) + role-aware answer face (C501) + enum_count (C503) + duration-family M1-M4 (C505) + 嵌入 side-channel (C506) + where-form locative (C508) + delta-family (C509) + inventory_count (C511) + neg-exist abstention 双门（专有 C513 + 普通名词 C516）+ museum_count (C514) + age_diff (C515) + risk_coverage_report (C520) + enum_count event 专名签名 (C521) + quant_rerank 数量子型 answer-face 重排（官方 0.476，+11/−0）(C523)**。**⚠️ #068 审计：无 TS 实现（旧 "TS 7349" 幻影双计已删）；npm 裸名已被 LightHaru 占用，命名决策（scoped/amgraph）列为 human-blocked，须在 README 终稿前**
- [ ] **amg PyPI publish — 人工三步**（建独立 GitHub 仓 agent-memory-graph / PyPI 2FA + Trusted Publisher / twine upload）+ **④ npm 命名决策 (#068)**（裸名被占：`@robertsong2019/agent-memory-graph` 推荐 / `amgraph` / `agent-memory-graph-py`，均实测 FREE）— 技术前置 100% 完成 (#066)，与 PyPI 同为 human-blocked
- [ ] **agent-context-store: README + npm publish** — **2929 tests**, 600+ APIs
- [ ] **structured-output-toolkit: README + npm publish** — **571 tests**
- [ ] **agent-task-cli: README + npm publish** — **1636 tests**, F249 (Round 64: EventBus.waitForMatch/Storage.partition/Storage.minBy-maxBy, dda22fa)

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
- **agent-memory-graph (Python)**: **10069 tests**（08-28 suite 实测绿 @5aae7e0；C514 处首破 10,000 🎉；链 10040(C516)→10052(C520)→10057(C521)→10069(C523) 绿）— 990+ APIs。entropy + classification + FINGEREntropy + PPR + multi_hop_reason + spreading_activation (5-member family) + activation_trace ✅ + competitive_spreading ✅ + SummaryTree + code-aware + provenance (4) + OWASP security suite (6) ✅ + amg-bench ✅ + MCP 16 tools ✅ + OTel telemetry ✅ + MultiAgentMemoryGraph (MESI) ✅ + FastAppendQueue ✅ + flush_and_consolidate ✅ (确定性 tie-break C437) + ResidualExtractor ✅ + consolidate() NREM/REM ✅ + consolidation_status() ✅ + memory_interference_report() ✅ + knowledge_freshness_report() ✅ + retrieval quality family COMPLETE ✅ + attention ✅ + temporal trilogy ✅ + bi-temporal APIs (5) ✅ + forgetting_forecast ✅ + seeded RNG fix ✅ + Experience Compression Spectrum COMPLETE ✅ + GraphRAG API family COMPLETE ✅ + export_graphml ✅ + run_amg.py 适配器 ✅ + chunk_text ✅ + resolve_entity_variants ✅ + amg_bench_quality LongMemEval 适配器 ✅ + 熵置信双门 abstention ✅ + locomo_bench_quality LoCoMo 适配器 ✅ (C451) + when-question date resolution ✅ (C456) + temporal-arithmetic answer path ✅ (C457) + telemetry v2 semconv 对齐 ✅ (C461) + judge_llm() 双口径+CLI ✅ (C462-464) + calibration_by_category ✅ (C465) + honest attribution ✅ (C466) + evidence-session coverage (answer_session_hit) ✅ (C467) + 锚定卫生 ✅ (C471) + 全图锚回退 ✅ (C472) + form-scoped seed breadth ✅ (C473) + distinctive speaker recall ✅ (C475) + counting forms 管线 ✅ (C477/C483) + in-text date anchors ✅ (C482) + past-perfect duration/纯任期 ✅ (C486/487) + order-family N 锚排序 + pairwise which-first 门 ✅ (C488/489) + 锚纪律两连 ✅ (C490/491) + TA first-kind 退役 ✅ (C493) + pairwise v2 三连 ✅ (C494-496) + ECM neither-family ✅ (C497) + preference 诚实弃权 ✅ (C498) + item_total ✅ (C500) + role-aware answer face ✅ (C501) + enum_count ✅ (C503) + duration-family M1-M4 ✅ (C505) + 嵌入 side-channel form-gated ✅ (C506) + where-form locative ✅ (C508) + delta-family 两锚点数值聚合 ✅ (C509) + inventory_count 枚举库存（第 10 counting form）✅ (C511) + neg-exist abstention 专有名词门 ✅ (C513) + museum_count 第 11 form ✅ (C514) + age_diff 第 12 form ✅ (C515) + neg_exist 普通名词 restrictor ✅ (C516) + **full-500 官方刷新 0.444（+38/−0，multi 0.459 兑现）** ✅ (C517) + abs 预设失败门三连 E1/E2/E3 ✅ (C518) + proper-noun 误杀取证修复（NFKD fold/学位媒体 stop/geo-sub）✅ (C519) + **risk_coverage_report（AURC/E-AURC，oracle Taylor 近似→constructive-exact）** ✅ (C520) + **enum_count event 专名签名** ✅ (C521) + **官方刷新 0.454（+3/−0 收债）+ bigram census RECORD-NEGATIVE** ✅ (C522) + **quant_rerank 数量子型（官方 0.476，+11/−0，arc 0.204→0.476=2.33×）** ✅ (C523)。**⚠️ 08-16 审计 (#068)：旧台账 "(TS) 7349" 为幻影双计，已删——无 TS 实现（唯一真 TS = amg-mcp wrapper 1718 行/122 tests）**
- **agent-context-store**: **2929 tests**
- **structured-output-toolkit**: **571 tests**
- **agent-task-cli**: **1636 tests** — F247-F249 (Round 64: EventBus.waitForMatch 谓词版 waitFor / Storage.partition / Storage.minBy-maxBy，dda22fa；Round 63: waterfall/deleteMany/onOnce，e5be0b9)。⚠️ 重犯已记录错误：cm.destroy() 不存在第 2 次（Round 59 台账已记）——第 3 次将写死规则：写 ConcurrencyManager 测试前先 grep 清理方法
- **context-forge**: **1458 tests** (F79, 21 dimensions)
- **nano-agent**: **1156 tests** — F69 (R20: 序列协议 dunders/copy+content_hash/subscribe 事件钩子)
- **edge-agent-runtime**: **345 tests**
- **prompt-mgr**: **283 tests**（08-17 render 字面量 bug 修复 + F15 export_markdown；旧台账 196 系 07-31 后自然增长未记）
- **agent-cost-tracker**: **36 tests**（08-21 晚：CLI 入口 DOA——fileURLToPath 从 'path' 导入致每次调用 SyntaxError，25 个 lib 测试全绿但 bin 从未被测；补实现声明过但从未存在的 estimate/clear 命令 + hermetic CLI e2e）
- **agent-framework-manager (afm)**: **29 tests**（08-21 晨 0→29，8 真 bug：await Promise.trim() 优先级致 getAgentStatus 恒报 stopped、构造器 async 竞态、exec 无 pid 等）
- **project-dashboard**: **11 tests**（hermetic 重写，3 真 bug：_detect_tests 白送 has_tests、workspace 缺失 traceback）
- **agent-mesh-network**: **373 tests** (355→373, taskStats/cancelTask/routingAnalytics)
- **session-archiver**: **81 tests**（08-24 晨 65→81）
- **tools/ai-dev-tools**: **79 tests**（08-24 晚 3 cycle：prompt delete/log 双假成功 + $& 模板注入 + 单文件静默）
- **tools/agent-memory-kit**: **29 tests**（08-24 晚：npm test DOA 接线 + context 跨工作区污染 + CJK 巨词 bigram）
- **四项目总计**: 12276 tests ✅（amg 10069 + sot 571 + atc 1636）
- **全项目总计**: ~21409 tests（08-28 KO 口径：amg 10069、atc 1636、skill-doctor 77（08-27 晚三连 64→77 新入）、session-archiver 81/ai-dev-tools 79/amk 29/cqc 56/mcpt 33；其余沿用 08-22 修正台账）
- **零回滚率**: amg **306天** 🏆（KO 日历链：08-22=299 … 08-28=305 / 08-29=306，会话漂移勿沿用；C517→C525 八连 keep（C524 负结果），C522 附带官方刷新 0.454）/ acs 200天 🏆

## 近期活动 (08-27 白天 ~ 08-28 深夜 crons)
- **C520 (cde5d38, keep, 21:11)**: risk_coverage_report——AURC/E-AURC/Risk@coverage（#089 移植）；**#089 oracle k²/2n² Taylor 近似低估 E-AURC → constructive-exact 修复**；flat curve：risk@50%=0.516 vs overall 0.556
- **C521 (61525fa, keep, 23:27)**: enum_count event 专名签名（数 DISTINCT 活动专名）；how-many 21 题切片 +1/−0；suite 10057；**/tmp lme_s.json 蒸发 → /root/lme_data/ 持久化，oracle-parity 4/4 复活**；⚠️ C520/C521 行误写 root tsv 已 revert，amg 真账本=项目仓 tsv
- **C522 (e4ac826, keep, 00:50)**: **bigram census RECORD-NEGATIVE**（48 fires：4 win 全 _abs + 12+ hijack 同构不可分；_abs 后缀进特征=标签泄漏弃用）→ C518"短语级 restrictor"方向全量关闭 + **官方刷新 0.448→0.454（+3/−0：C519+C521 兑现，86f00804 jitter 自愈）**；raw LME 数据集形状漂移：裸 turn-list 须 --mode eval
- **C523 (5aae7e0, keep, 01:47)**: **quant_rerank 0.454→0.476（238/500，+11/−0，近期最大单 cycle）**——数量型且 top 行无数字→重排到含数量 token 的 user 行；(-hits,-seq)+严格> 免费获得 kupdate 新值优先；基数词 only；10 真实翻转 + 1 containment 巧合（如实记）；ssu 36→42/70；suite 10069
- **03:00 测试循环**: prompt-template-manager 20→29（3 真 bug：静默覆盖→--force / 路径穿越→validateName / 头注释承诺的 edit 命令实装，570c05a）
- **05:00 essay 双发**: 《脚手架的 bug 是遗传病》925b750（mcpt scripts-wiring 遗传案例）+ 05:03 轮《语料里明明有 Aragón，门却说它不存在》acebed2（C519 误杀取证）——双触发各自幂等但各出一篇，当日两篇
- **20:09/20:25/20:29 deep-exploration 三触发**: Research #090 answer-face 等价判分（Bulian EMNLP'22 不对称等价/PEDANTS/GEM ACL'26；answer_equiv_judge.py 26/26；判分↔作答镜像律）；幂等三查生效仅发一篇博文《answer equivalence judging》c8f08cf
- **21:16 code-lab**: skill-doctor 三连 64→77 全 keep——C1 eval( 子串 FP（lookbehind 锚定）+ 插值 exec 注入 / C2 SKILL.md frontmatter 校验 + **遗传性修复：--fix 模板生成非法 skill（生成器→后代家族第 6 例）** / C3 autoFixJSON ENOENT 崩溃 + CLI --fix --json stdout 截断（fs.writeSync 同步刷）
- **23:30 key-development C524 (RECORD-NEGATIVE)**: latest-number-wins census 证伪——top-has-number 面 38/103；loose +2/−8、strict +0/−4、assistant-only +0/−0；8 hijack 与 2 win 机械签名同构（C522 不可分模式再例）；旗舰 a2f3aa27 信号层死亡（用户更新行 hedged hits=1 + 双侧 assistant 恭喜 echo）——C523 "top-with-number untouched" 守卫承重确认，零 port；衍生 session-scoped answer-face 候选入关键路径
- **00:00 key-development C525 (keep, 08-29)**: **ku recency session-scope answer face**（C524 spin-off）——adverb 标记（so far/currently/lately…）+ face 会话≠最新证据会话 → 重排到最新证据会话最优行；census 225 answer-gate 题全量 **6 fires = +2/−0**（prodverify 生产码 A/B 逐 qid 复现 67→69）；unscoped 对照 fire 58 含 10 hijack → scope 收窄承载全部分离力；**主产出：answer-gate 面枯竭+瓶颈迁移到窗口组成（109/158 wrong GT 行不在窗口，其中 92 题 GT 会话在而行不在）**；census v1 split-换行 sid 错位作废教训；官方 0.476 待刷新收债
- **22:00 tool-dev 双触发**: atc Round 64 F247-F249（waitForMatch/partition/minBy-maxBy，+18，1636/1636，dda22fa）；22:08 轮幂等跳过仅补增量
- **⚠️ cron 双触发昨日 3 例+（essay 05:04 / deep-exploration ×3 / tool-dev 22:08）**——幂等三查全部生效零重复产出；**5 组重复注册仍在 cron 表（08-27 已列清单待罗嵩拍板删除）**

## 近期活动 (08-26 白天 ~ 08-27 凌晨 crons)
- **C517 (f40da92, keep, 23:30)**: **full-500 官方刷新 exact 0.368→0.444（222/500，+38/−0 all-time high）**——C507-C516 七 cycle 债全量兑现，multi_session 0.233→0.459（counting+abstention 链 +30），零类目回归；套件 10040/10040 @HEAD。**刷新债清偿**
- **C518 (50c4406, keep, 01:15)**: abs 预设失败门三连——E1 at-which object form（C516 门释放）/ E2 age_diff 第 4 形态 other_until（counting-resolver abstain，C514 先例）/ E3 所有格 N-gallon 复合词。**0.448（224/500）/ multi 61→64/133=0.481 / abst 11.8%**；census 3 fires/3 wins/0 hijack；−1=margin 0.0 tie 抖动（代码路径归因=运行噪声）
- **C519 (86cbde3, keep, 01:58)**: C513 proper-noun gate 从未被 census——9 fires=4 误杀+4 正确+1 wrong→wrong；NFKD fold 两侧且 tokenize 前（'Aragón'→'Arag' 截断）+学位/媒体 stop+geo-sub 映射（hawaii→maui）；9→5 严格子集 +1 net，**预测 0.450 待下次刷新兑现**。遗留：3 题解锁后暴露 answer-face 转述失配（下轮高风险方向）
- **03:00 测试循环**: amg test_large_flush_performance 负载 flake 修复（4 紧阈值→绊网 2/10/1/0.5s，仍抓 O(n²)，0b3c94d）；基线 10040+5 subtests
- **04:00 文档晨轮**: TUTORIAL-ABSTENTION.md 新建（C448→C516 弃权家族教程）+ README 徽章 9963→10040、C512-C516 五 cycle 节（71618e3）
- **05:00 essay**: 《Flake 不是随机性，是答非所问》2b9b9d5；05:04 双触发幂等跳过
- **08:00 trending 深析**: apache/maka（local-first Agent 工作台）+ ponytail（110k⭐ 反过度工程，七级懒梯+诚实基准）——可行动：七级懒梯入 AGENTS 自查、earliest-valid-attempt 权威规则
- **20:06/20:10 deep-exploration 双触发**: Research #089（弃权×selective prediction：AbstentionBench 推理微调降弃权 24% / Calibration≠SP / AURC 唯一可靠指标；risk_coverage_aurc.py 零依赖）+ 博客《越会推理的 AI 越不敢说“我不知道”》117936f
- **21:00 code-lab**: mcp-server-toolkit 0→33 四连（6c62c03/81a54ee/ba799cf/d7e327e）——npm test DOA→node --test 真接线；validate/generate 真实现；**init 模板病情遗传（子项目 npm test 出生即 DOA）= scripts-wiring 家族第 5 例、首例传染后代**
- **22:07 tool-dev**: atc Round 63 F244-F246（waterfall/deleteMany/onOnce，+19，1618/1618，e5be0b9 已 push 清积压）；22:10 双触发幂等跳过
- **22:30 AI×Neuro**: 注意力机制 vs 生物注意力（皮层柱↔transformer block / divisive normalization↔softmax / STDP attention 能耗-88%）；飞书 68 blocks 已发（注：编号又用 #22，与 08-25 撞号——topics 表防重但编号漂移，下次应 #23）
- **⚠️ cron 双触发今日 4 例**（essay 05:04 / deep-exploration 20:08+20:10 / tool-dev 22:10）——幂等三查全部生效，零重复产出

## 近期活动 (08-25 晚 ~ 08-26 凌晨 crons)
- **C512 (fc07456, RECORD-NEGATIVE, 21:55)**: #088 跨题嵌入冗余证伪——触发面 census 仅 77/500 真嵌，haystack 近不相交 1.02×；A/B 真 MiniLM 位级一致但墙上时钟反 +24% → 生产回退。**教训：机制投影前先跑触发面 census（insight #254 检索侧版本）**
- **C512-B (bb6ecd5→133a7b1, retract, 22:07)**: 同向 SidechannelCache 独立实现 25 分钟后被发现前提已死——hunk 级分离提交 + 逆 patch 完美往返；方法论：动手前先 `git log --since` 看当晚同仓 commit（fc07456 已在库 12 分钟）
- **C513 (e34b34d, keep)**: neg-exist abstention 专有名词门（abs24 6→8）——近失陷阱：问 Shinjuku 有 Harajuku；全库缺席+第一人称⇒机制门前弃权。取证三迭：census 必须用 HEAD 状态/引号 regex 跨擇号伪造（显示层 bug 家族第 4 例）/第三人称主体豁免
- **C514 (dcd0996, keep, 23:00)**: museum_count 第 11 form，multi **0.414→0.429**，套件 10002 = **首破 10,000 🎉**；abs twin 判分走 meta["abstained"] 非数值包含（silence ≠ 0 claim）
- **C515 (1c78ab9, keep, 00:00)**: age_diff 第 12 form（self-age 锚定年份算术），multi **0.429→0.451**，套件 10020；question_id[:8] 孪生撞车=工具层 bug 伪装数据异常第 5 例
- **C516 (60b2e74, keep, 01:30)**: neg_exist 普通名词 restrictor（对象调包陷阱），multi **0.451→0.459** + abs30 **10→15**，套件 10039（collect 10040）；**insight #255：census 与单元套件正交（闸位劫持 census 看不见）+ 子集论证省 330s 复跑**
- **工具线**: code-quality-checker 32→49→56（两 cycle：node_modules 从未跳过/bin-symlink no-op/npm outdated 吞结果 health 谎绿；--fail-on/--min-score CI 门控）；amg npm-test DOA 修复 b52e6ba（自递归 core dump + prepare 链毒化 install，接 python3 -m pytest）
- **⚠️ 博客-证伪竞速**: e9dd6a4《嵌入账单寄给写入路径》20:17 发布 vs C512 证伪 21:55——公开携带已证伪 6.1×（真实 1.02×），**博客公开勘误 pending**（外部动作待定）
- **AI×Neuro #22**: 突触稳态可塑性与 BN（Turrigiano 1998 乘法性 scaling ↔ BN/LN/WeightNorm 三轴对比；Santurkar 2018 翻案平行）；飞书 107 blocks 已发；Tavily 432 配额错误连续第三天，AnySearch academic 降级稳定
- **博客 08-25 晨**: 《测试全绿的四种骗术》44e471c（接线 bug 类四连，05:03 重复触发未重发，第 3 例）

## 本周关键路径
1. ✅ ~~Cycles 367-457: security + bench + MCP + multi-agent + consolidation + retrieval QA + attention + temporal + Experience Compression + GraphRAG lifecycle + GraphRAG-Bench 适配器 + LoCoMo/LME_s 双基准 + 时序答案侧机制族~~ DONE
2. ⬜ README(agent-memory-graph) → npm publish + **amg PyPI 人工三步 + npm 命名决策** — **BLOCKED on human action**
3. ⬜ Next dev targets: **⓪ 官方 full-500 刷新收债（C525 +2 与 C526 +2，官方 0.476 → 预测 0.480+；C506v/C517/C522 收债第 4 验证）** / **judge_semantic() A/B（#090 判分器落地候选：C519 解锁 3 题 + kupdate 12 rescue 题 + C526 census 新证据：58 题 GT 串全 haystack 不存在=引用式判分结构性死亡，天然评测题集；llm 标签当 oracle）** / answer-gate 非 echo 面残余（census 后可救面仅 9~14 题，窗口/检索侧杠杆边际递减）/ ssu 34-wrong + speaker_recall 26-wrong 取证（C517 队列遗留）/ entropy gate 6 题误杀 / POST --sidechannel 臂刷新（C517 遗留）/ 三解锁题 answer-face 转述失配（25e5aa4f/488d3006，高风险）/ **博客勘误节（e9dd6a4 的 6.1× 已证伪为 1.02×）** / 8月底双首跑① GraphRAG-Bench Novel sample_100（阻塞=ollama pull qwen2.5:7b）/ cat5+多跳残余→LLM judge 实测（等 ollama）/ MCP registry publish / OpenClaw plugin / 博客候选 "the question is the join condition"（#086）+ "two directions, one word"（#087）+ "the wall was four walls"（#084）+ "presupposition failure is an answer"（C513/C514 弃权弧线）+ "the judge is the mirror"（#090 判分↔作答镜像律）。✅ 已落：**C526 session-completion face（census +3/−0，prodverify 69→72 零损失；预算截断假说证伪+105 题 seed-miss 归因）** + **C525 ku recency session-scope answer face（census +2/−0，官方待收债）** + C524 latest-number-wins census RECORD-NEGATIVE + C520 risk_coverage_report + C521 enum_count event + C522 bigram 负结果&官方刷新 0.454 + C523 quant_rerank 0.476（+11/−0）

## 上次检查
- **Knowledge org: 2026-08-28 02:00** — Integrated C520-C523 四连全 keep（amg suite **10069 绿** @5aae7e0 verified + commits cde5d38/61525fa/e4ac826/5aae7e0 全在库 + 项目仓 tsv C520/C521/C522/C523 行链完整；**day 305** 🏆 KO 链 08-22:299→08-28:305）。**C523 quant_rerank 官方 0.454→0.476（238/500，+11/−0，近期最大单 cycle，arc 0.204→0.476=2.33×）；C522 bigram census RECORD-NEGATIVE（方向关闭）+ 官方刷新 0.454（+3/−0 收债第 3 验证）；C520 risk_coverage_report（oracle Taylor 近似真 bug 修复）；C521 enum_count event 专名**。工具线：skill-doctor 64→77 三连（frontmatter 校验+遗传性模板修复家族第 6 例+CLI stdout 截断）+ atc Round 64 1636（F247-F249）+ ptm 20→29（3 真 bug）+ Research #090 判分器 26/26 + 博文×3（925b750/acebed2/c8f08cf）+ 2 essay + AI×Neuro。MEMORY：Current Focus 08-28 + C520-C523 arc + 表格 10069/1636/12276/~21409 + insights #256（标签泄漏红线）/#257（收债刷新）+ #090 Next 编号顺延。HEARTBEAT：标题/计数六处/新活动节/旧活动节裁剪（08-24 前）/关键路径 #3 重写（latest-number-wins 上位）/上次检查裁剪至两轮。⚠️ 未触碰：memory_graph.py e04d222d _search_cache +24 行仍未提交（第 4 天）。
- **Knowledge org: 2026-08-27 02:00** — Integrated C517/C518/C519（amg 10040 维持 ✓ C517 f40da92/C518 50c4406/C519 86cbde3 全在库 + 项目仓 tsv 628 行链完整；**day 304** 🏆 KO 链 08-22:299→08-27:304）。**C517 full-500 官方刷新 exact 0.368→0.444（+38/−0 all-time high，C507-C516 七 cycle 债兑现）；C518 abs 门三连 multi 61→64/133=0.481；C519 proper-noun 误杀修复预测 0.450**。工具线：atc Round 63 1618（e5be0b9，会话 pre-commit 验证——本机 1.9GB OOM 无法复跑全量，采信门控）+ mcpt 0→33（真接线 node --test；**旧台账 38 系 08-20 run.sh 口径且 npm test 从未跑通，已废**）+ amg flake 绊网修复（0b3c94d）+ TUTORIAL-ABSTENTION.md（71618e3）+ 博客×2（2b9b9d5 flake / 117936f abstention）+ Research #089 + AI×Neuro 注意力（编号撞 #22 已记）。MEMORY：Current Focus 08-27 + C517-C519 arc + 表格 atc 1618/12229/~21349 + Next 重写（刷新债清偿、risk_coverage_report 上位）+ mcpt 口径修正。HEARTBEAT：标题/计数/新活动节/关键路径。⚠️ 未触碰：memory_graph.py e04d222d _search_cache +24 行仍未提交（第 3 天）。
- **Knowledge org: 2026-08-26 02:00** — Integrated C512（RECORD-NEGATIVE）+ C512-B（retract）+ C513/C514/C515/C516 四连 keep（amg 9958→**10040** verified：pytest collect 实测 10040 ✓ + commits fc07456/bb6ecd5/133a7b1/e34b34d/dcd0996/1c78ab9/60b2e74 全在库 + 项目仓 tsv 625 行链完整 9979→10002→10020→10039；**day 303** 🏆 KO 链 08-22:299→08-26:303）。**C514 处 amg 首破 10,000 tests 🎉；multi_session 0.414→0.459 三连（C514/C515/C516）；abs30 10→15（C516 对象调包陷阱族）**。工具线：code-quality-checker 32→56 新入台账（3 真 bug + CI 门控）+ amg npm-test DOA 修复（b52e6ba）。**⚠️ 发现博客-证伪竞速事故：e9dd6a4《嵌入账单寄给写入路径》08-25 20:17 发布 vs C512 21:55 证伪 6.1×（真实 1.02×）——公开勘误 pending（外部动作待罗嵩确认或下轮 essay cron 附勘误节）**。MEMORY：Current Focus 08-26 + C514-C516 arc 节 + 表格 10040/12210/~21335 + insight #255（census 与单元套件正交/闸位也是正确性面）+ Next 重写（写时嵌入线关闭、abs30/ssu 取证上位）+ cqc 56 新入。HEARTBEAT：标题/计数四处/新活动节/关键路径 #3 重写。⚠️ 未触碰：memory_graph.py 另一会话（e04d222d）+24 行 `_search_cache` 未提交改动——C508 纪律，下轮 KO 勿误提交/误恢复。

## ⚠️ 已知问题
- **MEMORY.md size**: ~250KB（bootstrap 注入时被截 91%，仅保留 Current Focus 头部）——内容仍是活跃参考材料，但增长已不可持续；下轮 KO 候选：把 Key Insights #129-#257 中较早者迁 archive 文件
- **experiments.tsv 结构性缺口**: amg C410+ cycle 条目记录在项目仓内（code-lab/projects/agent-memory-graph），workspace experiments.tsv 仅记外部项目 — 补录可选，非阻塞
- **npm publish blocked**: 四项目 12276 tests ready（amg 10069/atc 1636/acs 2929/sot 571）。README 需 human review + amg npm 命名决策（#068 human-blocked）
- **Competitive pressure**: TencentDB-Agent-Memory growing fast (14.6K★). amg now has GraphRAG lifecycle + code-aware APIs + OWASP security suite as additional differentiators beyond entropy/classification/streaming.
- **experiments.tsv 账本拓扑**: amg 真账本 = projects/agent-memory-graph/experiments.tsv（08-27 C520/C521 误写 root 已 revert）；skill-doctor C1-C3 行落在 root tsv 而 tools/skill-doctor/experiments.tsv 止于 08-16——拓扑混用 monitoring，另该文件末行 note 字段有内嵌重复文本（append-only 不改史）
- **cron 重复注册未清理**: 5 组 7 份冗余 job 仍在表（deep-exploration ×3 / essay / github-creative / tool-dev / knowledge-org 各 ×2），08-27 已列清单待罗嵩拍板；幂等三查持续兜底
- **Tavily 配额**: 432 错误第 5 天，AnySearch + web_fetch 降级路径稳定
