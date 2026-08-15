# 文档完善报告 2026-08-16

## 主题：amg README 追平 Cycle 440→448 + code-lab 里程碑事实纠错

昨晚三场连续开发（21:00 C441-444 / 23:00 C446 / 00:12+01:10 C447-448）让 amg 文档落后 8 个 cycle。本轮全部追平。

### 1. projects/agent-memory-graph/README.md 追平 440→448

- **badge**: 8942 → 9241；测试章节 "448 个 cycle，294 天零回滚"
- **新增 API 参考章节「搜索树、泄漏安全与记忆质量 (Cycles 441-448)」**，13 个新 API 条目，全部从源码 grep 签名后撰写（不凭记忆）：
  - C441: `expand_search_tree` / `prune_search_tree`（非破坏剪枝）/ `search_tree_report`（Arbor #029 图即搜索树）
  - C442: `cross_modal_leak_scan`（风险分级 high/medium/low）/ `safe_forget`（泄漏闸门遗忘）
  - C443: `record_repair` / `recall_repairs` / `repair_stats`（AgentTether #018 前瞻修复记忆）
  - C444: `apply_decay(exclude_ids)` × `forget_policy("safety_purge")` 泄漏闸门集成
  - C445: `resolve_entity_variants`（Gap #5，case/title/containment 三模式）
  - C446: `enable_telemetry` / `disable_telemetry` / `telemetry_status`（OTel gen_ai.memory.* + 遣返说明）
  - C447: `amg_bench_quality.py` LongMemEvalAdapter 全链路
  - C448: `score_confidence`（熵置信度）+ `sweep_abstention`（弃权阈值扫描）

### 2. code-lab/README.md — 事实纠错 + 进化史补齐

- **⚠️ 纠错**：C440 行原声称 "Gap #6 关闭，GraphRAG-Bench 差距清单全部清零" —— **错误**。experiments.tsv 证实 Gap #5（EntityResolver）是 C445 的 `resolve_entity_variants` 才关闭的。已改为 "Gap #6 关闭"，清零声明移到 445 行（"6/6 真正清零"）。
- 进化史表 +8 行（Cycles 441-448）
- 里程碑段重写为 "安全遗忘 + 记忆质量双轴基准（Cycles 441-448，9241 tests）"，旧里程碑（432-440）降级为"此前"链

### 3. 验证与提交

- amg README 无残留旧计数（grep 8942/9053 为空）；code-lab 两处编辑 grep 验证落盘（吸取 8/14 报告未落盘的教训）
- 确认 knowledge-org commit 5ba272e 只动 HEARTBEAT/MEMORY/memory 文件，与本次项目 README 无重叠
- commit **997a92e**（workspace 根仓，pathspec 定向提交）

### 教训延续

- 文档声明的里程碑必须用 experiments.tsv/git log 交叉验证（本次抓到 code-lab 一处提前宣告"清零"）
- 每处编辑后 grep 验证（上轮 8/14 的失灵教训已固化为习惯）
