# 文档完善报告 — 2026-07-24

## 概要

本轮聚焦两个项目的文档补全：agent-context-store Cycles 198-200（3 个 API）和 nano-agent README 的 Memory 系统全面更新。共新增 3 个 API 条目、更新 2 个项目特性列表。已提交并推送。

## 变更详情

### 1. agent-context-store — Cycles 198-200

**Commit:** `ba73c9c` → pushed to GitHub

**新增 3 个 API 文档条目：**

| API | Cycle | 功能 |
|-----|-------|------|
| `hysteresis_band_recommender()` | 198 | 灵敏度分析自动推荐 raise/clear 迟滞带，三种策略（safe_range/elasticity/volatility），方向偏置调整，可选 auto-apply |
| `hysteresis_band_backtest()` | 199 | 双评估器回测（baseline vs hysteresis），测量转换减少率/振荡消除/检测延迟，支持真实历史或合成快照 |
| `scorecard_dimension_correlation()` | 200 | 跨预设维度间 Pearson 相关性，分类（redundant/independent/complementary），合并建议 |

**文档亮点：**

- **hysteresis_band_recommender**: 三种带策略对比表、方向偏置说明、完整 detect→configure→recommend→validate 流水线图
- **hysteresis_band_backtest**: 测量指标表、带宽来源解析优先级、合成快照生成说明
- **scorecard_dimension_correlation**: 四级分类规则表、返回核心字段表、使用场景

**特性列表更新：**
- 新增「Health & Alerting (Cycles 184-192)」特性条目
- 新增「Scorecard Intelligence (Cycles 193-200)」特性条目

**数据变化：**

| 指标 | 之前 | 之后 |
|------|------|------|
| 测试数 (badge) | 2810 | **2898** |
| Cycles | 197 | **200** |
| API 条目 (####) | 17 | **20** |

### 2. nano-agent — Memory 系统文档更新

**Commit:** `cb9a535`

**问题：** README 的 Memory 部分仅列出基础操作（add/search/get/remove），遗漏了 F1-F46 的 30+ 个新方法。

**更新内容：**

- **组件简介**：从 4 条扩展到 9 条分类（集合运算、模糊搜索、导出格式、聚类分析、标签管理、快照恢复等）
- **API 参考**：从 8 个基础方法扩展为 6 个分类、30+ 方法签名，涵盖：
  - 重要度与遗忘（F5-F8）
  - 高级搜索（F17-F27, F38）
  - 集合运算（F14, F28, F44-F45）
  - 分析与导出（F1-F3, F29-F42）

## 推送状态

| 仓库 | Commit | 推送 |
|------|--------|------|
| agent-context-store | `ba73c9c` | ✅ `3fb3597..ba73c9c` |
| nano-agent (workspace) | `cb9a535` | ✅ workspace repo |

## 下次关注

- **agent-context-store**: Cycle 200 已达成里程碑，可考虑 TUTORIAL.md 创建（类似 nano-agent）
- **amg-mcp**: 主库 README 的度指数家族可独立分组（上次报告遗留）
- **amg-mcp**: TUTORIAL.md 仍未创建 — API 接近 400 条，教程需求持续上升
- **nano-agent**: API.md 可能也需要更新以包含 F17-F46 新方法
- **code-lab**: Cycle 244 新增了 immutable_store + grep + expand，检查 README 是否需要更新
