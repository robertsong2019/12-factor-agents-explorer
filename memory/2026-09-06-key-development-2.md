# 2026-09-06 — key-development-2 (cron `88679f9e`, C550, kd-2 00:00)

## 任务
autoresearch 循环 B：读 autoresearch.md + kd-1（C549）最新成果，继续推进。成功标准 = C549 之上 ≥1 增量。

## 结果：KEEP，banked 270→273（0.540→0.546），+3 / 0 kill / 0 downgrade ✅

### 主攻：counting enum_count 的 qty-stated face（显式数字数量陈述压过签名计数）

**起点侦察**：C549 关闭了 answer-gate 131 行（challenger 枚举耗尽）。本轮先按队列把残余在 0.540 链上重审：
- 非 answer-gate NJ 58 = 35 zero-overlap（诚实弃权）+ 23 partial-overlap 逐行审计 = **0 诚实可救**（寄生重叠/IDK/答非所问；a40e080f 是 assistant-fact 领土，C524/C543 已证伪）
- **转向 counting gate**：12 counting wrongs 里 5 行 pred 退化为 "1"，而证据里明白数量陈述（"having watched 15 Crash Course videos"）——names/roles 签名把话题自身当实例数了（"crash course" = 1 个 name）

**Face：`_cnt_qty_stated`**（enum_count form gate 之后、签名分支之前）：
- **仅数字**提及 `<num> <0-3词> <head-stem>`——naive 全数字词版本模拟出 14 KILL / 0 RESCUE（"a baby"/"one tank" 冠词毒），**接线前证伪**，census-first 又立功
- 单题型 = 最新 user turn 胜（500→600 followers，10→15 videos）；and/both/combined 题型 = distinct 值求和（3+5=8 plants）
- 非候选 turn 扫 head-stem 子句（"now at 600 followers" 不含 "Instagram" 也抓到）
- 同 turn 歧义弃权：**lookahead 值扫描**（consuming finditer 会把 "40 or 50 followers" 解析成先锚定的 40——trap test 抓到后改 lookahead）

### 验证
- 生产同源 census 重跑：3 RESCUE / 0 KILL / 7 no-fire（10 行 enum_count 全 population）
- 54 行 counting replay：44 非 enum 行 byte-identical + 逐行 banked 公式 assert
- **A/B 基线陷阱**：live500_head 的 banked 标志是 0.520 时代（259）——0.540 账本在 C548 ab500 new_preds 里；step9 overlay 数学 270 精确 → 273
- +11 tests（test_qty_stated_face.py）；2 个 quant_rerank 机制钉死测试被拦截（fixture 题可被 enum_count 认领）→ `counting=False` 钉回原机制 + 路径注释
- **suite 10274→10285 green 200s**（PYTHONHASHSEED=7 shell env 钉死）

## 数值轨迹
0.502 → 0.504 → 0.506 → 0.510 → 0.512 → 0.518 → 0.520 → 0.524 → 0.526 → 0.528 → 0.540 → **0.546**

## 教训
- **"mined out" 判断要带作用域**：C549 说残余"fully attributed"，但那是 answer-gate 视角；counting gate 的 12 行 wrongs 里有 5 行系统性退化 pred="1"，一轮 census 就翻出 +3
- **census 模拟即生产代码**：两次语义微调（digits-only、lookahead）都立即重跑生产同源 census——模拟器和生产漂移 = 假阳性温床
- 机制钉死测试被新 face 拦截时，用能力开关（counting=False）把测试钉回它本来要测的机制，并注释新路径归属

## Next（队列状态）
- temporal_arith 13 wrongs（anchor-date 抽取形态，本轮未动）+ duration-family 0.5-hour 行
- ollama oracle（human-blocked，解锁 ~169 NJ cascade）
- GraphRAG-Bench census pivot / run_amg packaging
- ⚠️ memory_graph.py +24 行 _search_cache 死代码脏 hunk 第 17 天未触碰（逐文件 add 未混入）

## Artifacts & 提交
- /tmp/c550/{step1..step9}.py + qty_census{,2,3}_final.json + ab_counting.json + ledger_0540.json
- amg 归 monorepo，commit 带 amg 前缀，push
