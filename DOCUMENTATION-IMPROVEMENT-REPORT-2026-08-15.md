# 文档完善报告 — 2026-08-15

## 概要

本轮聚焦 **GraphRAG 端到端教程**（上次报告"下次关注"第 2 项）+ **README 追平至 Cycle 440**。时机正好：Cycles 439-440（run_amg.py 适配器 + chunk_text）于昨日晚间关闭了 GraphRAG-Bench 全部 6 项差距，流水线完整收官，教程得以覆盖从原始文本到官方基准评测的全链路。

## 变更详情

### 1. projects/agent-memory-graph/TUTORIAL-GRAPHRAG.md — 新建（10.7 KB，约 250 行）⭐ 本轮核心

上次报告规划的事项，本轮完成。端到端串联 8 个环节：

```
segment_sentences (432) → chunk_text (440) → extract_from_text (428)
→ graphrag_query + fact-answer (429/433) → graphrag_explain (430)
→ graphrag_coverage_report (431/435/436) → export_graphml (438)
→ run_amg.py (439, GraphRAG-Bench)
```

章节结构：8 步渐进教程 + Agent 实战模式（FastAppendQueue 结合）+ 概念速查表 + 排障表。

**代码片段 100% 实测验证**（本次执行中发现并修正 2 处失真）：
- `entities` 实际返回 `[{'label', 'node_id', 'new'}]` 字典列表，非纯字符串列表
- `relations` 键为 `source/target/relation`，非 `subject/object`
- fact-answer 正例验证：`"Who created Neo4j?"` → `answers: ['Alice']`；`"Who works at Acme Corp?"` → `['Alice', 'Bob']`
- networkx GraphML 往返验证通过（7 nodes / 6 edges）

### 2. projects/agent-memory-graph/README.md — Cycles 425-440 API 参考（追平 16 个 cycle）

**纠偏发现**：上次报告声称已给该 README 添加 "Cycles 425-431 API 参考" 并更新 badge 至 8794，但 `git log -- README.md` 显示最后一次 README 提交停在 `5828008 docs: cycles 416-424`，grep 亦无 FastAppend/freshness/8794 痕迹——**昨日报告与实际落盘不符**（只更新了 code-lab 两份副本）。本轮补齐：

- badge 8505 → 8942；测试节 8505/424 cycles/290 天 → 8942/440/292
- 头部新增双教程链接（TUTORIAL.md 基础 + TUTORIAL-GRAPHRAG.md 进阶）
- 新增 "Cycles 425-440" 章节：FastAppendQueue（写架构）、knowledge_freshness_report、segment_sentences、extract_from_text、graphrag_query（含 fact-answer 三级主语解析）、graphrag_explain、graphrag_coverage_report（含关系维度+单一化告警）、export_graphml、run_amg.py、chunk_text

### 3. code-lab/agent-memory-graph/README.md — GraphRAG-Bench 章节新增

- 新增 "GraphRAG-Bench Integration (Cycles 432-440)" 章节（含 run_amg.py 基准跑法 CLI + 5 个新 API 片段）
- GraphRAG Pipeline 章节头部链接新教程
- 统计：8,794 → 8,942 tests，291 → 292nd day

### 4. code-lab/README.md — 进化史 + 里程碑 + 功能域表

- 进化史表新增 9 行（Cycles 432-440：缩写安全切分 / fact-answer / 关系覆盖 / 单一化告警 / 确定性巩固 / GraphML 导出 / 基准适配器 / 长文分块）
- 里程碑更新为 **GraphRAG-Bench 差距清单全部清零**
- 功能全景表新增 "GraphRAG-Bench 适配" 域（4 方法）+ GraphRAG 检索/健康行补 fact-answer、关系维度
- 项目表 agent-memory-graph 行 + GraphRAG-Bench 适配器描述；统计 8,794 → 8,942

## 教训（Error Escalation）

**报告-落盘偏差**：8/14 报告声称完成了 projects/agent-memory-graph/README.md 的更新，实际该文件未被修改。这属于"文档工作声称完成但未验证落盘"——与 TOOLS.md 中飞书文档"写入后必须 read 验证"是同类问题。已在本轮通过 `git log -- <file>` + grep 双重验证修正。**规则：文档改动后必须用 git diff/grep 验证目标文件实际变更。**

## 下次关注

1. **Cycles 342-415 API 参考补全**（遗留项，第三次提醒）— projects/agent-memory-graph/README.md 的 API 参考在 342-415 区间仍有大量 cycle 只有清单无详情。建议分 3-4 轮批量消化，每轮 ~25 cycle。
2. **TUTORIAL-GRAPHRAG.md 实战数据补充** — 待 GraphRAG-Bench Novel 域批量 E2E benchmark 跑出结果后，在教程追加真实评测数字章节。
3. **FastAppendQueue 独立教程**（遗留项，第二次提醒）— System-1/System-2 双进程模式 + Agent 写入生命周期，可与 knowledge_freshness_report 合并为一篇"记忆写入与保鲜"教程。

## 推送状态

| 文件 | 状态 |
|------|------|
| projects/agent-memory-graph/TUTORIAL-GRAPHRAG.md | ✅ 新建 |
| projects/agent-memory-graph/README.md | ✅ 更新（badge+章节）|
| code-lab/agent-memory-graph/README.md | ✅ 更新 |
| code-lab/README.md | ✅ 更新 |
| 本报告 + memory 日志 | ✅ |

---

*Generated: 2026-08-15 04:00 AM · Documentation cron*
