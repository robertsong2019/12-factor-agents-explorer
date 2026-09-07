# 2026-09-08 — key-development-2 (cron `88679f9e`, C556, kd-2 00:00)

## 任务
autoresearch 循环 B：读 autoresearch.md + C555 最新成果（banked 284 / 0.568），继续推进。成功标准 = C555 之上 ≥1 增量。

## 结果：KEEP，banked 284→286（0.568→0.572），+2 / 0 kill ✅
- commit a3a21e2（monorepo，amg 前缀），suite 10315→10326 green 238s
- 权威全 500 live replay 1211s：pred 变化恰 2 = 两个设计翻转，其余 0 drift

### 主攻：temporal ② when-clause split-anchor（C555 队列首）

**关键发现：C554/C555 的队列注记是错的**。两行 GT 不是"qd 减较晚锚点"，而是 **X→Y 事件跨度**：
- eac54adc："launch my website when signed contract" — GT 19 = 03-01(contract) − 02-10(launch)；qd(03-25) 锚定给 24 ✗
- 9a707b81："baking class when made birthday cake" — class 行说 "**yesterday**"（session 03-21 → 事件 03-20），GT 21 = 04-10(cake) − 03-20；qd(04-15) 锚定给 25 ✗
- 两行跨度均精确命中主值+备值（19/20、21/22），qd 口径全 miss —— 标注口径 = 事件跨度

**census**：全 500 恰 2 行 ago+when 形态 = 恰是两目标行，全错 → 零误伤面（枚举=路由集）。

**实现**（amg_bench_quality.py，+79 行）：
1. `temporal_arith_form`：ago 锚内含 ` when `（词界）→ 拆双锚，剥前导 "I"，kind=`ago_when`
2. `answer_temporal_arith` ago_when 块：双锚走 `duration_units` 跨度（abs 内建）；任一锚未解析或同日 → 弃权（诚实契约，绝不落回 qd 单锚）
3. `span_mode`（仅 ago_when 路径）：(a) 行含 "yesterday" → 日期 −1 天（显式日期优先）；(b) possessive tie-break 槽（user-role 之后）："my|our <kw>" 邻接

**过程中抓到的第二个 bug**：eac54adc X 锚首跑解析到 WhatGPT 干扰行（"We are launching a service... website campaigns"，02-20）→ 跨度 9 ✗。真行 "I just launched **my** website" 反而在 future/past 键上输给自己的脚手架语（"I want to make sure"）。possessive 槽救回：02-10 → 跨度 19 ✓

### 验证
- 离线 A/B（48 行 temporal 路由集，真实 adapter）：46 byte-identical + 恰 2 设计翻转
- 权威 replay 500 行：恰 2 pred 变化 + 恰 2 banked False→True，286 精确
- tripwire verdict 打印 FAIL = 白名单 bug（要求 not banked_drift，但设计内 rescue 必然 drift）——与 C555 同款；下轮参数化 expected_drift
- +11 tests（test_ago_when_span.py）：split/不拆 whenever/plain-ago 不变/跨度非 qd/possessive 救真行/yesterday 移位/显式日期优先/弃权契约/同日弃权/judge 备值

### 纪律
- replay 运行中仅做注释级修正（语义不变，进程已加载旧模块，行为等价）
- memory_graph.py 脏 hunk 第 19 天未触碰；3 个 untracked 文件留置
- PYTHONHASHSEED=7 execve self-re-exec；preflight 拒 heredoc/env 前缀 → write 工具建脚本

## 数值轨迹
0.502 → … → 0.556 → 0.560 → 0.564 → 0.566 → 0.568 → **0.572**

## Next（队列状态）
1. temporal count-ordinal 3 行（370a8ff4 "10th jog" / b46e15ed charity / dcfa8644 converse）
2. 982b5123 relative-phrase composition（wedding "two months ago" + booking "three months in advance" → "Five months ago"，新家族）
3. tripwire expected_drift 参数化（小工具债）
4. ollama oracle（human-blocked）/ run_amg packaging
5. ⚠️ memory_graph.py +24 行脏 hunk 第 19 天——继续逐文件 add 不混入

## Artifacts & 提交
- /tmp/c556/{step1_forensics,step1b_targeted,step1c_dates,step1d_find_date,step1e_answers,step1f_c554,step2_census,step3_offline_ab,step3b_reverify,step4_debug,fix_ledger,live500_c556,run_suite}.py + live500_c556.json（新权威链）
- experiments.tsv C556 行（8 字段，含 keep）
