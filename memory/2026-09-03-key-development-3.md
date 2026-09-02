# 2026-09-03 — key-development-3（cron `b0fd7e8d`，C542）

## 任务
autoresearch 循环 C：读 autoresearch.md + kd-1/2 最新成果，推进 amg LongMemEval full-500。成功标准 = kd-2（C541，banked 259/500 = 0.518）之上 ≥1 增量。

## 结果：KEEP，banked 259→260（0.520），+1 / 0 kill ✅

### 主攻：C541 遗留队列 #1 —— 8752c811 judge-side GT-wrap face
C540 接线 ordinal face 后留下的 in-pipeline live debt：`8752c811` 抽取出了**正确 item**但 judge 判 WRONG。
- GT: `"The 27th parameter was 'Sound effects (e.g., ambient, diegetic, non-diegetic, etc.)'."`
- pred: `'Sound effects (e.g., ambient, diegetic, non-diegetic, etc.)'` —— **与引号核心逐字节相同**
- 失败机理：frame 的 `27th parameter` token 使 pred 成为 GT 严格 token 子集 → Guard 3 subset veto → WRONG。既有三个 subset-rescue face（exact-number/either-or/marker-subsequence）全不覆盖。

### 实现：`_sem_quoted_core_face(reference, answer)`
- 引用把断言事实用引号包起来（frame + quoted core）时，引号核心就是数据集断言的答案；norm(candidate) == norm(quoted span) ⇒ 完整事实而非弱化子集
- 4 条引号 regex（ASCII '/" + curly ''/""），word-boundary lookaround 防撇号开 span（`it's 'test'` 只quote `test`）
- 2-char span floor（防杂散符号）；branch-local 于 subset veto 分支（quoted core 的数字天然 ⊆ reference 数字，guards 1-2 已过）→ 只可能 WRONG→CORRECT，纯上行
- +11 tests（test_quoted_core_face.py）；suite 10213→10224 green 198s

### Census（接线前全枚举）
- chain preds 上 quoted-core hit set = **{8752c811} 恰一行**（当前 WRONG → +1）
- subset-veto 分支全人口 40 行（39 CORRECT / 1 WRONG）——face 只可能碰那 1 行
- 无 stopword-only frame 假阳性

### 基础设施：authoritative live-500 chain（本周期第二产出）
delta chain（frozen C530 + 200-char overlay dumps）经 C540/C541 两轮证实脆弱。本轮直接 HEAD 全量 live 重跑 500 行（1144s，**FULL preds** 落盘 `/tmp/c542/live500_head.json`）：
- **验证 C541 ledger 259 精确成立**（首次自 C530 以来的全人口复算验证）
- chain-vs-live 逐行 diff = **恰 1 行 stale**：25e5aa4f 的 true pred（C541 where-gate 翻转后的 UCLA bearer）从未写回 effective_preds.json —— 这就是 chain 复算读 255/258 与 ledger 259 对不上的全部原因
- 后续 cycle 判分实验直接用 live500_head.json，delta chain 退役

### ⚠️ 假 NET-NEGATIVE 险情（显示层家族第 5 例，已升级 TOOLS.md 规则）
face_ab.py 首跑报 259→257（-2，3 个 "KILL"）——实为**双臂公式不同源**：baseline 臂用 frozen `correct_exact`，new 臂用 live `exact_judge`，两源在 3 行上不一致，而 verdict 根本没变（NEEDS_JUDGE→NEEDS_JUDGE）。翻转打印露的馅。修复 = 双臂统一 frozen exact + 每行 `assert ok_old == r["banked"]` 漂移 tripwire；修正后 259→260 +1/0 kill。同周期 chain_vs_live.py 尾部又犯同族（+18 双计）。**A/B 双臂必须逐字段同源 + baseline 逐行 assert** 已写入 TOOLS.md 永久规则。

## 验证链
- census_quoted_core: 500 行全枚举，hit={8752c811}，当前 verdict WRONG
- live500_head: 全量 500 live 重跑（PYTHONHASHSEED=7），banked=259 ✓ ledger
- face_ab（修正后）: 每行 baseline assert 通过，恰 1 verdict flip，banked 260
- chain_vs_live: 恰 1 行 stale（25e5aa4f），chain+face=259 自洽
- suite: 10213→10224 green 198s，零回归

## 弃置/不改
- 1-char quoted core（`'x'`）保持 WRONG：2-char floor 是文档化的保守性，population 中 0 命中，不放宽
- judge leniency queue / ollama oracle：仍 human-blocked

## 数值轨迹
0.444（C535 前基线）→ 0.502 → 0.504（C537）→ 0.506（C538）→ 0.510（C539）→ 0.512（C540）→ 0.518（C541）→ **0.520（C542）**

## Next（C542 遗留队列）
- answer-gate non-echo 46 / ssu 34-wrong（pred 侧，需 A/B）
- embedding side-channel 生产化（#083 form-gated switch 已验证 0.87）
- ollama judge 实验（human-blocked）

## Artifacts
/tmp/c542/{probe_8752c811.py, census_quoted_core.py, census_quoted_core.json,
verify_banked.py, scan_chain.py, suspects.json, live500_head.py,
live500_head.json, face_ab.py, face_flips.json, chain_vs_live.py}

## 教训
- **A/B 双臂公式逐字段同源 + baseline 逐行 assert**：假 NET-NEGATIVE 比真失败更危险（会错杀好改动）。翻转打印里 verdict 不变的 "KILL" 是最便宜的露馅信号
- delta chain 的复杂度成本已超过全量 live 重跑（19 min）：能全量重跑就别维护增量链
- exec preflight 拒绝 `cd X && python3`（复合解释器调用）→ 直接 `python3 /abs/path/file.py`
