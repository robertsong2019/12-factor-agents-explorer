# 2026-08-31 01:10 — key-development-3 (C531: veto census 复核 — either/or answer-face rescue, banked 0.492→0.494)

cron `key-development-3`（b0fd7e8d…，01:10 触发）。承接 kd-2（C530，00:33）队列 #4「veto 守卫对 multi_session 的 −3 可作 census 复核（确认无误杀）」。幂等三查通过（无今日 kd-3 产物、无并发会话、无在飞 eval）。ollama 仍缺席 → 队列 #1（真 cascade A/B）继续阻塞，census 复核升为本次主菜。

## 结论 TL;DR

- **5 个 C530 确定性 veto-kills 逐 qid 复核完毕**：3 个正确 kill（全部 Guard-1 disjoint-number：00ca467f '2'vs'20'、a9f6b44c '2'vs'2023' 已知、e56a43b9 '5'vs'500'）+ **2 个 false kill（全是 Guard-3 subset 分支）**。
- **Guard-3 subset 分支（toks_c ⊊ toks_r → WRONG）在官方 cascade-500 上生产精度 0/2**：
  - gpt4_98f46fc6：Q「charity gala **or** charity bake sale?」PRED 'the charity bake sale' vs GT 'I participated in the charity bake sale first.' —— either/or 问题的完整答案被否决。
  - gpt4_45189cb4：PRED 'First NBA game, then College Football National Championship game, finally NFL playoffs' vs GT 同序冗长句（ratio 0.715 < 0.75 difflib 救援线）—— 忠实缩写被否决。
- **修复（KEEP，0f7f6b1）**：`_sem_either_or_face(question, answer, reference)` —— C529 exact-number answer face 的文本类比，keyed off **question 结构**（问题只提供 2 个备选时，点名声 称其一即为完整答案，完整性由问题保证，非阈值）。守卫齐备：exactly-one-or / candidate 包含于某备选 / 未决 ref（双备选皆提及 → 猜测不救）/ 否定窗 / multi-or。**C529 tennis spec 保留**（'tennis' vs 'table tennis' 仍 WRONG）。
- **gpt4_45189cb4 有意不救**：无非拟合词法规则能区分「忠实叙事缩写」与「跳事件的部分答案」（coverage ≥0.6 阈值 = 拟合 benchmark）→ `test_narrative_abbreviation_stays_vetoed` 显式钉债，未来修复必须有原则性表述或走 oracle。
- **入账 246→247 (0.494)**，kills 5→4。suite **10143 green 173s**（10140+3）。

## 方法论沉淀

- **判定层增量用 verdict-delta 枚举，不重建全账本**：管线是数据集纯函数（C528 后）+ 冻结 predictions（C530 官方 run）→ 对 500 行逐行重判，枚举 verdict 变化 = 恰好 1 行。本次前 3 次尝试重建 246 的账本分解全部翻车（243 exact 含 _abs 行、abs 行从不进 cascade、+8/−5 净额口径），第 4 次换枚举法一次成型。**「重算总数」是陷阱，「枚举 diff」是正道。**
- **覆盖阈值是拟合，问题结构是原则**：NBA 行若用 coverage≥0.6 救援即刻入账，但该常数只为适配本次 census（0.714/0.60 恰好过线）。要么有结构化保证（either/or 的问题完备性），要么诚实弃权/留债 —— 与 C529 拒绝放宽 difflib 阈值同理。
- **census 先于修复再一次兑现**：kd-2 留下的「−3 确认无误杀」问题，实际答案是「multi_session 的 −3 里 00ca467f/a9f6b44c 是正确 kill，temporal 的 −2 里 1 正确 1 false」。若盲信 C529 的「2 residual defensible weak-veto edges」结论（defensible ≠ correct），这 2 个 rescue 就永远沉没。
- 30 个 _abs 行从不路由 cascade（is_abs 分支，C529 发现复用）——离线重判时必须剔除，否则幻影 +1。

## 下 cycle 队列

1. **ollama oracle 接入后跑真 cascade A/B**（#090/#092，连任 #1）：169-172 NEEDS_JUDGE 面 LLM 上行空间仍未入账；judge_llm_backend 指纹就位。
2. **NBA 叙事缩写救援的原则性表述**：marker-aware subsequence + 事件跳跃检测（候选序 markers 的相对位置须与 ref 对齐）或直接依赖 oracle；test_narrative_abbreviation_stays_vetoed 是规格锚点。
3. 遗留：answer-gate 非 echo 面 46 题 / ssu 34-wrong / speaker_recall 26-wrong 取证；oracle-track fast-iteration 开发集评估。

## 工件

- 离线 census，无新 eval run（管线纯函数性，C530 predictions 冻结复用 /tmp/c530/post_cascade500.json）
- commit 0f7f6b1（judge+tests）/ 438e149（tsv backfill）
- 官方口径更新：**247/500 (0.494)** = 243 exact + 8 rescues − 4 kills
