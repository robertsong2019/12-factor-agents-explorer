# 2026-08-26 23:00 — key-development-1 (Cycle 517)

## C517: full-500 官方刷新 @C516 HEAD — exact 0.368 → **0.444**（222/500，全库新高，+38/−0 零损失）

autoresearch 循环 A。HEARTBEAT 顶部队列「full-500 官方刷新债（C507-C516 累积）」本轮收口。

### 关键数字（judge dual, PRE 臂, 与 C499/C506v 同口径）

| category | C506v | C517 | Δ |
|---|---|---|---|
| multi_session | 31/133=0.233 | **61/133=0.459** | +30 |
| temporal | 81/133=0.609 | 83/133=0.624 | +2 |
| ssu | 32/70=0.457 | 36/70=0.514 | +4 |
| kupdate | 24/78=0.308 | 26/78=0.333 | +2 |
| ssa | 16/56 | 16/56 | 0 |
| pref | 0/30 | 0/30 | 0（C498 诚实弃权设计使然） |
| **OVERALL** | 184/500=**0.368** | 222/500=**0.444** | **+38** |

- **per-question join（vs /tmp/c507/pre_full500.json）：+38 gains / 0 losses** —— lineage 最干净的一次大额刷新（C492 有 −2、C499 有 −1）
- multi 61/133 **精确复现** C514→C515→C516 切片 A/B 链终点（0.414→0.429→0.451→0.459）
- abs30：7→15（+8），C513/C516 双门弃权兑现
- abstention 8.6%→11.2%（诚实弃权上升 = 特性）；hit 0.394 / evhit 0.912 持平（答案侧改动零检索回归）
- 累计弧线：C481 reference 0.204 → C492 0.284 → C499 0.316 → C506v 0.368 → **C517 0.444**（2.18×）；multi_session 自首个 reference 0.007 → 0.459（65×）

### 验证

- **suite 10040/10040 green @HEAD（190s，含平时 flaky 的 perf-timing test）**——pristine 环境认证
- 工件：/tmp/c517/lme_s_full500_c517.json（官方报告）+ /tmp/c517/cmp.json（flips）+ /tmp/c517/suite_result.txt
- tsv：experiments.tsv C517 行（full500_exact, keep）

### 方法论要点（供 KO 整合）

- **并发脏树隔离**：主树 memory_graph.py 有另一会话（e04d222d）未提交 `_search_cache` +24 行改动（C508 纪律：不碰不提交不恢复）。本轮用 `git show HEAD:` 抽取 pristine 双文件到 /tmp/c517 运行 eval、`git archive HEAD` 抽取全套跑 suite——**官方参考完全不受脏树影响**，也零风险落地 commit（只 add tsv + 本文件）
- 七 cycle 债一次收口 = C506v 先例的复用；切片 A/B 链（multi 0.459）与全量精确一致，再次验证「切片串行 A/B + census 零劫持」方法论的可预测性

### Next（HEARTBEAT 队列更新建议）

1. POST --sidechannel 臂刷新（C508 树曾测 207/500=0.414，现 C516 树 + 答案侧 +38 后预计 ~0.45+）
2. ssu 34-wrong 同类形态取证（ssu 0.514 后剩余 34 错）
3. speaker_recall 26 wrong / abs30 剩余 15（gpt4_*_abs、时间型）
4. ⚠️ 主树 memory_graph.py 脏改动归属 e04d222d 会话——下轮 KO 勿误提交/误恢复
