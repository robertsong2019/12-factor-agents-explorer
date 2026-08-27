# 2026-08-28 key-development-3 (C523) — quantity-form answer-face re-rank

**Cron**: key-development-3 · **方法**: autoresearch（census → 靶向修复 → red/green 单测 → slice A/B → full-500 官方 → 落地）
**结果**: **0.454 → 0.476**（227→238/500，+11/−0）—— C481 0.204 起累计 **2.33×**

## Census（/tmp/c523/census_gates.py，直接读官方 post_full500.json 的 retrieval.gate 字段）

- `^how (many|long|much)` 匹配 220/500；其中 **103 题走到 answer gate**（其余被 counting/delta/TA/pp_duration/entropy 认领）
- 103 = 81 wrong + 22 correct；wrong 中 **42 题 retrieval_hit=True & answer_session_hit=True**——GT 数字就在窗口内，答面引了同窗口无数字的相邻消息（C499 echo 病理的数量子型）
- 7 个 ssu 代表：c960da58 Spotify 20 / 94f70d80 IKEA 4h / af8d2e46 7 shirts / 6b168ec8 three bikes / 21436231 12 bass / 8e9d538c 17 skeins / 311778f1 10 hours

## 修复（#090 quant_rerank）

答案门 C501 块之后：数量型问题 **且 top 行不含数量 token** 时，重排到含数量 token 且关键词 hits≥2 的 user 行（hits 最大者）。要点：

- **迭代序 (-hits,-seq) + 严格 `>`**：平局保序首项 = seq 最大 = 最新消息——kupdate 新值优先（C437/C447）免费获得（72e3ee87、7401057b 等翻转靠它）
- **数量 token 正则只收基数词**：one..ninety/hundred/dozen + `\d+`；**不收 once/twice/couple/half**（建议文本高频，会假阳性）
- **严格作用域护栏**：top 行已含数字则整块不进（正确数字答案按构造不回归）；无候选项 fall-through（C488）；关键词 floor 2（C501）
- `_quantity_form` 无家族排除：门序保证 counting/TA/delta 已在上游过场，fall-through 正是本干预面；where 问句以 where 开头不可能匹配 ^how
- flag 正交：`quant_rerank: bool = True` / `--no-quant-rerank`

## 验证

1. 单测 12 个 red/green（pristine import error = red；patched 12/12）
2. Slice A/B（103 题，官方 CLI 同路径）：base 0.214 (22/103) → patched 0.320 (33/103)；**+11/−0，已正确 92 题 PA 扰动 0**；base 与官方逐题 parity 102/103（681a1674 检索非确定抖动，判定不变）
3. 11 翻转全量检查：**10 个真实证据行**（"I have 20 playlists on Spotify already"、"it took me 4 hours"…事实句藏在长消息中部）；**a9f6b44c 是 containment 子串巧合**（GT "2" ⊆ "2023"，判定合法但非真实证据修复——如实记录）
4. Full-500 官方：0.476，翻转与 slice 完全一致，489 非翻转题零扰动
5. Suite：10069 collected，1 失败 = C501 switch-off 测试与 C523 交互（role_answer=False 时 C523 合法触发）→ 测试加 `quant_rerank=False` 隔离 C501 机制（特性超越场景，非回归），修复后全绿

## 落地

- `amg_bench_quality.py`（quant_rerank 块 + 谓词 + flag）、`test_quant_rerank.py`（新）、`test_role_answer.py`（switch-off 隔离）、`experiments.tsv` C523 行
- 纪律：memory_graph.py 的 e04d222d 脏改动全程未碰；只 add 具体文件
- 工件：/tmp/c523/{amg_base.py,amg_post.py,test_quant_rerank.py,slice103.json,base_slice.json,patched_slice.json,post_full500_c523.json,census_*.py,compare_slice.py,dump_wins.py,diff_official.py,base/,patched/,red/}

## 遗留队列（供下轮）

1. **latest-number-wins**（a2f3aa27 "1250→1300 followers"：top 已含数字 1250 但 GT 是更新的 1300）——需要"数字行内 recency 比较"，比本轮风险高一档，40+ 题人口
2. 三解锁题答案面转述失配（C519 遗留：25e5aa4f/488d3006）——高风险
3. entropy gate 6 误杀（C522 遗留）
4. answer-gate 非数量型 echo（103 题之外 answer gate 还有 ~200 wrong，同病理不同触发面——本轮的 role/keyword 机制不覆盖，需要新的行选择信号）
