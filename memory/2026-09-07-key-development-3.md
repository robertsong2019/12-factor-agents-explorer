# C554 — key-development-3 (2026-09-07)

**Verdict: keep** — banked 282→283 (0.564→0.566), commit `39ac859` (pushed), suite 10312 green 233s.

## 成果：slash-date adverbial face

`_line_adverbial_date` 的 `_TA_LINE_DATE_RE` 只认月份词形式（"on March 5th" / "on the 3rd of March"），
漏掉数字斜杠形式 **"on the 3/8"**。8c18457d（graduation gift ↔ birthday gift between）里
"graduation gift on the 3/8" 行的 anchor 日期没有精化到 03-08，停在 session 日期 03-29，
between 差值 = 14 天 vs GT 7。修复：加第三条 regex 备选（**强制 "on" 前缀**挡分数/比例误匹配
"3/8 of the budget"；支持可选 2/4 位年），parser 加 `nm/nd/ny` 分支。

- 离线 A/B：temporal 45 行 = 1 rescue / 0 banked flips；pairwise 18 + ecm 3 = 0 flips（它们经 `_pw_line_dt` 消费同一 regex）
- 全量 500 live replay（1165s）：283 banked；pred 变化 3 = C553 两个 duration flips 复现（e831120c/71315a70，都保 banked）+ 新 rescue；0 down、0 v/exact drift、零噪声
- +7 tests（TestSlashAdverbialDate：on-the-3/8 / bare on 3/8 / 2位年 / 无年 hint=None / 分数不误匹配 / 月份词优先 / 8c18457d 端到端 mini 几何）

## 关键 census 发现（本 cycle 最大的方向修正）

**C553 队列点名的 judge 行（60bf93ed/aae3761f/b3c15d39）已经 banked=True（judge_semantic v=CORRECT）**
—— C553 memory 里那张 wrongs 列表是 exact==False 中间层的旧账，judge faces 那条路是死路。
step2b census 在接线前拦下（先证伪后接线纪律的又一次兑现）。

282 时点 real wrongs（206）的真实分布：
- answer 127（80 NJ + 47 WRONG）— C549 已挖尽，ollama-blocked
- pref 29 NJ — C498 structural zero（answered 30→1 也没分，generation-native），死路
- speaker_recall 17 / where 8 / entropy 7 — NJ-honest 提取不可达
- **temporal_arith 8** — 本 cycle 攻的就是这，1 个数字日期 face 到手，剩 7 行三个机制（见下）
- counting 9 — 异质单行

## temporal 剩余 7 行的机制账（next 队列的弹药）

1. **plan-vs-realized hits 支配**（gpt4_b0863698、982b5123）：tie ladder 里 hits 是第一位，
   plan 行（"I'm planning to run a charity event... "）hits=2 压过 realization 行 hits=1，
   future-marker 降权只在 hits 打平时才生效。修法方向：realization 行应无视 hits 数压过 plan 行
   （plan-verb 门控："planning to / will / going to / signed up"）。
2. **when-clause split-anchor**（eac54adc、9a707b81）："How many days ago did I X when Y?"
   现在 form parser 把整句折成一个 anchor。标注者用**两者中较晚**的日期（03-06>03-01；
   03-25>03-21）。修法方向：ago X when Y 拆双 anchor 取 max——语义 = 复合事件完成日。
3. **count-ordinal / 杂项**（370a8ff4 "10th jog"、b46e15ed charity、dcfa8644 converse）——单行各案。

## 纪律记录

- census/judge 层检查用存储 preds 即可（judge 是纯函数），但**答案函数改动必须全量 live replay**（本次 1165s）
- probe 用 in-memory monkey-patch 先跑 A/B，commit 后再跑权威 replay（regex 左最近匹配 vs probe 的
  "month-word 优先"顺序有细微分歧风险——8c18457d 行无月份词日期，rescue 不受影响，已由权威 replay 验证）
- amg 无独立 .git：从 workspace root `git add projects/agent-memory-graph/<file>` 相对路径；memory_graph.py
  脏 hunk（第 18 天）不碰

## Trajectory

0.502→…→0.546→0.556→0.560→0.564 (C553)→**0.566 (C554)**　|　commits: d9de045→db93160→935a16c→48b9264→d73b6e6→**39ac859**

## Next

1. temporal plan-vs-realized（预计 gpt4_b0863698 + 982b5123 最多 +2）
2. when-clause split-anchor（eac54adc + 9a707b81 最多 +2）
3. ollama oracle（human-blocked）、GraphRAG-Bench census pivot、run_amg packaging、
   memory_graph.py 脏 hunk（第 18 天）
