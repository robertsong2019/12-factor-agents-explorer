# 文档完善报告 — 2026-07-15

## 概要

本次文档轮次覆盖 agent-memory-graph Cycles 236-244（12 个 cycle）和 agent-context-store Cycles 190-191 的 README API 文档补全。2 个 docs commits，均已推送。

## 变更详情

### agent-memory-graph — Cycles 236-244

**Commit:** `5e4a922` (openclaw-workspace repo)

**新增 14 个 API 文档条目 + 8 个设计思想：**

| API | Cycle | 来源论文 | 功能 |
|-----|-------|---------|------|
| `invalidate_cascade()` | 236 | PLACEM (2607.04089) | BFS 级联失效，depends_on 反向 + enables 正向传播 |
| `add(category=)` | 236 | Apple Shared Selective Memory (2607.09493) | 五类记忆分类（preference/protocol/episodic/reference/skill） |
| `search_by_category()` | 236 | 同上 | 按 category 检索，排除隔离节点 |
| `read_proactive_context()` | 237 | — | 基于活跃意图的主动上下文推送 |
| `forgotten_index()` | 238 | Fajtlowicz 1998 | Forgotten 拓扑指数 |
| `abc_index()` | 238 | Estrada et al. 1998 | Atom-bond 连通性指数 |
| `sum_connectivity_index()` | 238 | Zhou & Trinajstić 2009 | Sum-connectivity 指数 |
| `immutable_retrieve/all/count()` | 239/244 | — | 不可变记忆日志查询 |
| `grep()` | 239 | — | 跨不可变历史全文本搜索 |
| `expand()` | 239 | — | 从不可变存储无损恢复节点数据 |
| `compact_node/batch/stats()` | 240 | — | 三级节点压缩（截断→摘要→极致） |
| `serialize/serialize_compact()` | 241 | — | Token 预算序列化（贪心打包 LLM 上下文） |
| `check_relation_integrity()` | 242 | — | 关系通道完整性校验（值冲突/悬挂引用/类型不匹配） |
| `integrity_quarantine()` | 242 | — | 自动隔离高危节点 |
| `semantic_speed_gate/batch()` | 243 | SSGM | 邻域波动率测量（边增删频率） |
| `volatile_nodes()` | 243 | SSGM | 高波动节点排行 |
| `selective_filter/report()` | 243 | SSGM | 多维度质量过滤 |

**Header 更新：**
- 测试计数：2813 → **3249** (+436)
- Cycle 计数：232 → **244** (237 天零回滚)
- 设计思想：39 → **47**（新增 #40-#47）

**新增设计思想 #40-#47：**
- #40: 级联失效 + 分类检索（PLACEM + Apple SSML）
- #41: 主动上下文召回（意图驱动预取）
- #42: 拓扑指数扩展至十四族（forgotten/abc/sum_connectivity）
- #43: 不可变记忆日志 + grep + 全息展开（审计级版本控制）
- #44: 节点压缩 + 批量压缩（token 预算友好）
- #45: Token 预算序列化（贪心打包 LLM 上下文）
- #46: 关系完整性校验（数据质量守卫）
- #47: 语义速度门控 + 选择性过滤（SSGM 动态质量管控）

### agent-context-store — Cycles 190-191

**Commit:** `19e1326` (agent-context-store repo)

**新增 6 个 API 文档条目：**

| API | Cycle | 功能 |
|-----|-------|------|
| `store_health_dashboard()` | 190 | 7-section 统一执行仪表盘（gauge/alerts/heatmap/forecast/improvements/recommendations/interpretation） |
| `quality_improvement_batch_tracker()` | 190 | prefix 范围批量改进追踪（snapshot/record/report） |
| `alert_history()` | 190 | 告警状态变更时间序列日志（log/history/timeline/stats/clear） |
| `store_health_report_export()` | 191 | 导出报告（markdown/json/text 三格式，8 种 section） |
| `quality_decay_model()` | 191 | 质量衰减预测（freshness-weighted linear decay, urgency 分类） |
| `alert_correlation()` | 191 | 告警-变更时序相关性分析 |

**Header 更新：**
- 测试计数：2557 → **2636** (+79)
- Cycle 计数：189 → **191**

## 推送状态

| 仓库 | 推送 | 远程 |
|------|------|------|
| openclaw-workspace | ✅ `5e4a922..4b9fd12` | github.com/robertsong2019/openclaw-workspace |
| agent-context-store | ✅ `3e0b3fa..19e1326` | github.com/robertsong2019/agent-context-store |

## 未变更项目

- **context-forge**: 无新代码变更
- **agent-pipeline**: 无新代码变更
- **prompt-weaver**: 无新代码变更

## 下次关注

- 监控 agent-memory-graph 是否有 Cycle 245+ 新功能
- 监控 agent-context-store 是否有 Cycle 192+ 新功能
- **README → npm publish** 仍为四项目最高优先级（AMG/ACS/context-forge/agent-pipeline）
- agent-pipeline cycle 3-4 的新功能可能需要文档化
