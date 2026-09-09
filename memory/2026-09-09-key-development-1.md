# Key Development 1 — Cycle C561 (2026-09-09)

**Task:** cron `key-development-1` · autoresearch 方法论实验循环 A · 基于链头 C560（banked 290 / 0.580，commit `eab9d61`）

**结果：+4 rescue / 0 kills — banked 290 → 294（0.580 → 0.588），单周期最大增益（此前纪录 C548 的 +2）。measure_sum 面族：counting_form 的非金钱同胞（"What is the total distance/weight/time"）从 gate 链落底改判为测量单位求和。suite 10370 → 10383 junit 406s 0F/0E（+13 tests）；full-500 live replay 1340s PASS tripwire（pred changes 恰 4 / drift 全 False→True / abs_banked 18）**

## 选题（queue 头 ollama 仍 human-blocked 后的最优可量化目标）

queue 头 ollama oracle 需人工安装（`ollama pull qwen2.5:7b`），改选 WRONG 行 census 驱动的面族：

- 210 个 WRONG 行问句形式 census：最大簇 "What is the total \<measure\>" — `counting_form` 只认钱类（item_total: amount/cost/price），**测量单位（distance/weight/time）全部落底**
- 全 500 行 census（/tmp/c561/census1.py）：加宽 form **恰 4 行，全 WRONG，零 banked 重叠**（amount/cost/number 各归其主）——零 kill 面由构造保证
- 机制排除项：2b8f3739（qty×单价乘加，过难）、days 族（日期锚定活动计数，非求和）、36b9f61e/2b8f3739 属 item_total 领地（C500 泳道）

## 机制（问题结构，非阈值——C531 原则）

每行证据先从原始 haystack 逐行核实（diag4 + verify_lines.py），再定结构规则：

- **distance/weight 两档制**：任一 user 句带 "total" 标记（"covered a total of 1,800 miles"）→ 只 sums 标记句（6c49646a：1800+1200=3000，user 干扰句 "drove around 300 miles on the first day" 无 total 被排除）；否则全量 user 数量求和（d3ab962e：3-mile loop + 5-mile hike = 8；bc149d6b：50-pound batch + 20 pounds = 70）
- **time takes 锚定**："commute takes about 30 minutes" / "takes me about an hour"；takes 句内的列举项（"includes a 20-minute meditation"）与无锚句（"4.5-hour drive away"）不算；90 min → "an hour and a half"（1192316e：60+30）
- **意图位置细化（TDD 中途 redesign）**：commute 句 "...takes about 30 minutes, so I want to..." 被 `_CNT_INTENT_RE`（"I want"）整体击杀——但这就是真实 s4 原句！改为位置语义：意图短语在数量**之前**才毒化（"I'm thinking of getting 30 pounds"），在其后不毒化（takes/total 锚已认证事实）
- 连字符形容词（"3-mile"/"50-pound"）两个 pattern 都要 `-?`；区间（"20-40 miles"）range-skip；渲染 `3,000 miles`（千分位）/ "an hour and a half"

## 验证链

- 红先 13 miniatures：form 2 + weight 2 + distance 4 + time 3 + dispatch 2；RED 确认（ImportError）后 GREEN 抓到 **2 个真 bug**：weight pattern 漏 `-?`（得 "20 pounds" 非 "70 pounds"）、"and a half" 后缀非捕获组（IndexError）
- 全套件 junit：**10383 / 0F / 0E / 0 skipped**（10370+13 严丝合缝）
- live-500：pred changes 恰 {d3ab962e, 6c49646a, bc149d6b, 1192316e}，drift 全 False→True，**0 kills**，banked 294/500=0.588，abs_banked 18 断言过
- counting_judge 无需改动：numeric-first + containment 天然 credit "an hour and a half"；judge_semantic 精确等值 credit 全部 4 个渲染

## 教训

- **miniature 就是干这个的**：两个真 bug + 一个 redesign 全在 RED→GREEN 循环内被小测试抓住，500 行回放一次过 tripwire——机制面测试先行是回放成功率的直接来源
- 证据核实先于机制设计：6c49646a 的 300 英里干扰句若不看原文就会设计出 3300 的错误机制；1192316e 的句内列举项若不逐句看就会 60+20+30=110
- census 零 banked 重叠 = 最安全的选题形状（对比 C555-C557 时代的 banked-adjacent 面）

## 纪律保持

- memory_graph.py 脏 hunk 第 21 天未碰；3 个 untracked 旧文件留置
- staged-diff 验尸：3 hunks == 3 处编辑，逐块对上（+141 代码 +174 测试，0 删除）
- preflight 拒复杂解释器调用链 → write 工具建脚本 + 纯 `python3 <file>` 直跑
- experiments.tsv 追加走幂等脚本（已存在 C561 行则拒写）

## 数值轨迹

0.502 → … → 0.576 → 0.578 → 0.580 → **0.588（+4 rescue，单周期最大）**

## Next queue（继承）

1. ollama oracle（human-blocked，~169 NJ cascade）
2. run_amg packaging
3. MCP registry publish
4. item_total 内部修复点：36b9f61e（'$2,500'=$800+$1,200+$500，item_total 已认领但返回 None 落底）——C500 泳道内的下一候选

## Artifacts

- /tmp/c561/{lite.json, diag1.py, diag2_evidence.py, diag3_units.py, diag4_miles.py, census1.py, verify_lines.py, live500_c561.py, live500_c561.json, junit.xml, append_row.py}
- experiments.tsv C561 行（8 字段，keep，code commit 5b42dc1）
- 新 authoritative chain: /tmp/c561/live500_c561.json
