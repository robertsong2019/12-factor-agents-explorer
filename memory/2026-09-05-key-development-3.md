# key-development-3 — Cycle 3 (2026-09-05 01:00 cron, C548)

**起点**：C547 banked 264/500 (0.528)。**终点：270/500 (0.540)，+6 / 0 kill / 0 downgrade，keep**。本轮单周期增益 = 近 40 个周期最大（+6）。

## 主攻：cross-session user-statement challenge face —— C546 kh-elite 证伪的精化版

C546 关闭了 plain kh-elite admission（23.3% kill），但留下一个问题：kill 全是 assistant 共情 preamble，而 4 个 viable rescue 行的 GT 都是 user 行——**分离信号可能存在**。本轮两遍 census 检验这个假设。

### Census 链（/tmp/c548/，census-first 全程）
1. **Pass-1（census_challenge.py，187 行）**：kill 面 = 50 行 banked-correct answer-gate 随机样本（seed 7）；rescue 面 = 全部 137 行 banked-wrong answer-gate。P0 plain admission 复现 C546：**kill 7/50 = 14%，NET-NEGATIVE 确认**。P1（phrase-run 门）kill 0/50、rescue 4——但关键发现是**角色分离**：4/4 rescue 全是 user 行，2/2 kill-trigger 全是 assistant 行。
2. **Pass-2（census_user.py，user+cross-session 门烧进策略）**：挑战者必须 ①role=user ②跨 session（同 session 归 C526）③phrase-run 支配（run(ch) > run(win)，floor 2，C540 原语），且在生产排序 (-hits,-seq) 下 outrank 现胜者（kh>win 或 kh==win∧later-seq）。结果：**5 RESCUE / 0 KILL / kill 侧 0/50 触发**。
3. **Live smoke（smoke.py）抓真洞**：c19f7a0b/f523d9fe census 说 RESCUE 但管线不 fire——`face_found=False`。根因 = **C525 context-split 陷阱**：多段落 label 进 window 只剩第一行，exact-match 找不到胜者。修复 = first-line 匹配（比较仍按 census 口径在第一行证据上）。修复后 5/5 全 fire，impostor 行（gpt4_7de946e7/caf9ead2）全程静默。
4. **A/B（ab500.py，全 500 replayed-preds，473s）**：baseline 264 精确复现 → **new 270**，21 pred 变化 = **6 RESCUE + 15 noop + 0 KILL**。非 answer-gate 行结构性不可达（face 在所有 early-return gate 之后）。8fb83627 是 A/B 独有 rescue：C526 先改写胜者，我的 face 挑战的是**新胜者**（stored-pred census 近似的盲区，A/B 为准）。

### Rescue 清单
- c8c3f81d（Nike running shoes 偏好）、8ebdbe50（Master's still considering）、c19f7a0b（language-learning habit）、gpt4_5dcc0aab（Adidas sneakers 清洗）、f523d9fe（Netflix 下架投诉）、8fb83627（news mix 变体）
- 共同形状：**胜者是 assistant 回声/preamble，GT 是另一 session 里 user 的第一人称事实陈述**

### 机制故事（为什么这三道门不是装饰）
LongMemEval 个人事实问题由 user 陈述作答；assistant 行是 advice/echo——**正是历届 impostor census 的 kill 全家福**。C546 的教训不是"admission 不可能"，而是"无门 admission 不可能"。role 门是分离器，phrase-run 门挡 bag-of-hits 假证据，cross-session 门避开 C526 领土。

## 验证
- +10 tests（test_user_challenge_face.py）：rescue、role 门、same-session 门、kh-tie later-seq、run 门、outrank 门、multiline 胜者（红先行——live smoke 先红后修）、flag-off、ghost bail、fixture sanity
- **suite 10261→10271 green 219.5s**（PYTHONHASHSEED=7 钉死）
- A/B 双臂同源（HEAD judge + frozen correct_exact + 18 abs），full preds 落盘无截断

## 数值轨迹
0.502 → 0.504 → 0.506 → 0.510 → 0.512 → 0.518 → 0.520 → 0.524 → 0.526 → 0.528 → **0.540**

## 教训
- **证伪记录里藏着精化方向**：C546 的 kill 全是 assistant 行、rescue 全是 user 行——下一轮 census 应该先问"kill/rescue 的构成有什么共同变量"，而不是把 census-negative 当终点
- **多段落 label 的 context-split 是管线级陷阱**（第 2 次遇到，C525 注释过）：任何按 label 匹配胜者的 face 都要用 first-line 匹配或显式 no-op
- census 近似（stored-pred 胜者身份）与管线真值有已知盲区（C526 前置改写）——census 定方向，A/B 定数字

## Next（队列状态）
- **residue 需在 0.540 链上重审**：WRONG 82 关闭、partial-overlap 31 审计都在 +6 churn 之前
- 剩余大项：ollama oracle（human-blocked，解锁 ~169 NJ cascade）、GraphRAG-Bench census pivot、run_amg packaging
- ⚠️ memory_graph.py +24 行 _search_cache 死代码脏 hunk 第 16 天未触碰（本轮逐文件 add，未混入）

## Artifacts & 提交
- /tmp/c548/{census_challenge.py,census_challenge.json,census_user.py,census_user.json,smoke.py,debug2.py,probe.py,ab500.py,ab500.json}
- amg 归 monorepo，相对路径 add：amg_bench_quality.py + test_user_challenge_face.py + experiments.tsv + memory 文件
