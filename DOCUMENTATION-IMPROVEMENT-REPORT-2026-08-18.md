# 文档完善报告 2026-08-18

## 主题：amg README 追平 Cycle 458→467 + code-lab 进化史 + 副本诚实同步

昨日（08-17）是三连开发日：白天 C458-460、晚间 code-lab-evening C461-464、深夜 C465-467，共 10 个 cycle 无文档。本轮全部追平。

### 1. projects/agent-memory-graph/README.md 追平 458→467

- **badge**: 9406 → 9519；测试章节 "467 个 cycle，296 天零回滚"（pytest --collect-only 实测 9519）
- **新增 API 参考章节「记忆演化审计、OTel 对齐与 LLM-as-Judge 双口径判分 (Cycles 458-467)」**，10 个条目全部从源码 grep 签名后撰写：
  - C458: `estimate_node_impact(*, degree, weight, label, existing_neighbors)` — 非破坏性写前拓扑预测
  - C459: `export_tsv` / `import_tsv(*, merge=False)` — TSV 互换（表头自动检测、round-trip、merge 模式）
  - C460: `graph_changelog(*, limit, node_id)` + `update_node()` evolution_log 埋点
  - C461: telemetry v2 对齐 semantic-conventions-genai @c739977（动词化 span 名、单一 record.count、query.text Opt-In、专有键迁 `amg.*`）
  - C462: `judge_llm(question, answer, reference, *, mode, n_judges)` — Research #069 多数投票，sticky mock 降级语义写入文档
  - C463: `--judge` CLI + run_eval 双口径聚合
  - C464: `evaluate_sample` / `run_locomo` 三层 dual 接线（cat-5 协议共享）
  - C465: `calibration_by_category(results)` + full-500 reference（exact 0.140 / llm 0.194 / hit 0.378）
  - C466: 诚实归因（question_id 回退 + 权威 question_type，temporal 0.061→0.180 修正）
  - C467: `answer_session_hit_rate` — 证据会话覆盖率（retrieval_hit 合成真相类目结构性失明的解药）

### 2. code-lab/README.md — 进化史 +10 行 + 里程碑 + 功能域

- 进化史表新增 10 行（Cycles 458-467）
- 里程碑段重写为「记忆演化审计 + OTel v2 + LLM-as-Judge 双口径（Cycles 458-467，9519 tests）」，旧里程碑（449-457）降级为"此前"链
- 项目表 agent-memory-graph 行补「LLM-as-Judge 双口径判分」功能域

### 3. code-lab/agent-memory-graph/README.md — 副本诚实同步

该英文精简副本自 08-15 后停在 8,942 tests / 291st day（C440），前两轮报告均未同步，积压 27 个 cycle。本轮采用**最小诚实同步**而非全量移植：

- 头部与文末统计统一更新：8,942 → 9,519 tests、291st/292nd → 296th day（顺带修掉了副本内部原本就不一致的天数）
- 文末新增「Recent (Cycles 441–467)」英文摘要段：一段话概括安全遗忘、实体归一、压缩残差、对抗鲁棒、时间推理、写前预测、TSV、演化审计、OTel v2、judge 双口径十个主题，并指向真身仓 README 作为权威 API 参考
- 不做 27 cycle 的全量英文 API 移植（成本高且真身仓才是权威）——副本定位是导览，不是镜像

### 4. 验证与提交

- 三份文件 grep 验证全部落盘（新计数 9519/9,519 共 6 处；旧计数 9406/8,942 在对应文件 0 残留——code-lab 主 README 中保留的一处 9406 是"此前"里程碑的历史引用，属正确用法）
- API 签名 100% 源码 grep 后撰写（estimate_node_impact 第 7491 行、export_tsv 3195、graph_changelog 7636、judge_llm amg_bench_quality:1075、calibration_by_category:1156、answer_session_hit_rate:355）
- 公开方法数复核：memory_graph.py 583 个公开方法，副本 "565+" 表述仍为真，未改动
- commit **a237016**（workspace 根仓，pathspec 定向提交，不触碰 HEARTBEAT/MEMORY 等其他 session 的未提交文件）

### 教训与延续

- 副本（code-lab/agent-memory-graph/README.md）连续两轮被跳过导致积压 27 cycle——本轮确立「最小诚实同步」策略（计数 + 摘要段 + 权威指针），后续每轮跟进成本 ~5 分钟
- C466 的「幻影类目分组」教训在文档中显式记录（启发式只做兜底、数据集字段权威），这是 calibration 类工具的通用陷阱
