# C551 — key-development-3（cron 01:00，autoresearch 循环 C）

**结论：keep。banked 273→278 live（0.546→0.556），temporal full-graph-first +4/−0，并起获 C550 counting-face 遗留漂移（net +1，2 个 latent KILL 留给下轮）。**

## 主攻：temporal_arith 13 wrongs（C550 队列首位）

### Census（/tmp/c551，全部先证伪后接线）
- **锚点取证**（step1）：13 wrongs 全部 fire temporal gate 且有日期；主导失败形态 = 锚点选错行（982b5123 两锚点都落在 question date → "0 months"）。
- **月舍入方向**（step2）：接线上限矩阵 NET-NEGATIVE（naive cur-1：1 rescue [b46e15ed 3→2] vs 4 kills [0bc8ad92、gpt4_6dc9b45b、5e1b23de、6613b389]）→ 不改。半月舍入与标注语义对齐。drift check：temporal 代码 C542→C550 零漂移（13 wrongs 全是 C542 前就错）。
- **变体矩阵**（step3，46 行全 population，rep_control 与生产 byte-identical）：
  - B1 gen-升序：+0/−0（无操作）
  - B2 role 提前：+0/−0（无操作）
  - **C full-graph-first：+4 rescue / −0 kill** ✓ 采纳
- 机制：干扰语料行（Tribunal 式词汇镜像噪声）挤占检索窗口 top-k，真事件行进不了候选集；C471 tie ladder 拿到**完整候选集**后自然选中真行。**杠杆 = 候选可得性，不是 ladder 排序**（B1/B2 无操作证明）。C472 的 window-first 谨慎在这个 population 上被经验推翻。

### 接线
- `LongMemEvalAdapter(temporal_fullgraph: bool = True)`：default = 一次 `answer_temporal_arith(question, _dated(self._messages), question_date)`，telemetry `fallback="fullgraph_first"`；flag off = legacy window-first + C472 full-graph retry（原路径，telemetry "full_graph"）。
- report config 增 `temporal_fullgraph` 指纹。

### 验证链
1. **46 行生产 A/B**（step4）：off 臂 vs stored preds **0 漂移**；on 臂精确 4 RESCUE / 0 KILL / 42 行 byte-identical（212s）。
2. 测试：+5 test_temporal_fullgraph.py（wiring 契约 3 + 机制缩影 2）；test_temporal_fallback.py 的 C472 钉子被新默认拦截 → `_adapter` 钉 `temporal_fullgraph=False`（legacy 路径照旧钉死）+ 文件头 C551 注释。**suite 10290 全绿 204s**。
3. **全量 500 live 重跑**（复用 C542 harness，1161s）：**banked = 278**（预测 277，多 1 → 强制逐行对账）。

### Step6 逐行对账（278 vs 链 273，18 行差异全部归因）
| 类别 | 行 | 净 |
|---|---|---|
| temporal RESCUE（本轮改动） | 0db4c65d 18d / gpt4_21adecb5 6mo / 08f4fc43 30d / a3045048 7d | +4 |
| counting RESCUE（C550 face 首次 live 暴露） | 031748ae '4' / 0f05491a '120' / ba61f0b9 '6' | +3 |
| counting KILL（同上，latent） | 0ddfec37 '20' vs GT 15 / 10e09553 '9' vs GT 7 | −2 |
| churn（pred 变判定不变） | 9 行，含 b46e15ed 3mo→1mo 仍错、gpt4_4fc4f797 fall-through（均与 census 预测一致） | 0 |

数学：273 + 4 + 1 = **278 精确闭合**。

### ⚠️ C550 遗留发现（下轮队列首位）
C550 counting census 只重放了 54 行 enum_count 枚举集，但 gate=counting 实际路由 12 行——**census 枚举集 ≠ gate 路由集**，2 个真 KILL 漏网。ledger 273 其实低估了 C550-live 真实值 274。教训入册：**census 枚举必须等于 gate 谓词路由集，按 gate 谓词重放，不按"哪个机制会 fire"枚举**。下轮最清晰目标：修 0ddfec37（'20'-vs-15）/ 10e09553（'9'-vs-7）的 qty-stated recency 选错 digit statement，潜在 +2 → 280。

## 轨迹
0.502→0.504→0.506→0.510→0.512→0.518→0.520→0.524→0.526→0.528→0.540→0.546→**0.556**（C548 +6 单周期纪录保持，本轮 live 口径 +5，其中归属本轮改动 +4）

## Artifacts
- /tmp/c551/{step1_census, step2_monthpop, step3_variants, step4_ab46, step6_attribute, live500_c551}.py + step3_variants.json + step4_ab46.json + live500_c551.json（新权威链）
- 项目改动：amg_bench_quality.py（flag + temporal 分支 + config）、test_temporal_fullgraph.py（新）、test_temporal_fallback.py（legacy 钉回）、experiments.tsv

## next
counting 2 latent KILLs（+2 潜力）/ duration-family 0.5-hour rows / ollama oracle（human-blocked）/ GraphRAG-Bench pivot / run_amg packaging
