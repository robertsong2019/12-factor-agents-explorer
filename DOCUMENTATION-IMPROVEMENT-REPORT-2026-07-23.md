# 文档完善报告 — 2026-07-23

## 概要

本轮聚焦 agent-memory-graph Cycles 272-276 的 API 文档补全。共新增 6 个 API 条目，更新特性列表和测试徽章。已提交并推送。

## 变更详情

### agent-memory-graph — Cycles 272-276

**Commit:** `1273d9b` (openclaw-workspace repo)

**新增 6 个 API 文档条目：**

| API | Cycle | 功能 |
|-----|-------|------|
| `auto_consolidate_cluster()` | 272 | 群体级批量合并：最高度数节点吸收整个簇，替代 N-1 次逐对调用 |
| `walk_statistics()` | 273 | 多次随机游走聚合：覆盖率、重访步、死端率、最常访问节点 |
| `edge_type_stats()` | 274 | 按关系类型聚合统计：数量、权重范围、唯一源/目标、互反性 |
| `detect_skill_candidates()` | 275 | 情景模式挖掘：扫描 event/intention 节点发现重复行为，建议技能提升 |
| `sombor_index()` | 276 | Sombor 指数 SO（Gutman 2021）：度数对几何距离总和 |
| `reduced_sombor_index()` | 276 | Reduced Sombor RS：K₂→0 的分支敏感变体 |

**文档亮点：**

- **auto_consolidate_cluster**: 批量 vs 逐对合并优势对比、双循环架构补充说明
- **walk_statistics**: 6 个返回字段说明表
- **detect_skill_candidates**: 置信度饱和公式、候选返回结构示例
- **sombor/reduced_sombor**: 4 种参数公式验证表、交叉关系说明、度指数家族（14 个）总览

**特性列表更新：**

- 双循环质量系统 → 补充「逐对 & 整簇」
- 新增「情景模式挖掘」「图采样统计」「14 个度拓扑指数」三条特性

**数据变化：**

| 指标 | 之前 | 之后 |
|------|------|------|
| 测试 badge | 4099 | **4205** |
| API 条目 (####) | 393 | **399** |
| 特性条目 | 更新 1 + 新增 3 | — |

## 推送状态

| 仓库 | Commit | 推送 |
|------|--------|------|
| openclaw-workspace (amg) | `1273d9b` | ✅ `f026b58..1273d9b` |

## 下次关注

- **agent-context-store** (lab/) 最近的 Cycle 变更需检查是否有未文档化的 API
- **amg README** 度指数家族章节可考虑独立分组（目前散布在谱分析区域）
- **TUTORIAL.md** (amg) 仍未创建 — 随 API 数量接近 400，教程需求上升
- **README → npm publish** 仍为四项目最高优先级
