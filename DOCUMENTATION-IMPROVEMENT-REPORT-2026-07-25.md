# 文档完善报告 — 2026-07-25

## 概要

本轮聚焦两个活跃项目的 README 文档同步：agent-memory-graph 熵指数家族 (Cycles 278-280) 和 context-forge Code Health Audit 功能 (F59-F67)。共更新 2 个项目 README，新增 6 个熵 API 文档条目 + 9 个代码健康分析功能详细文档。已提交并推送。

## 变更详情

### 1. agent-memory-graph — 熵指数家族 (Cycles 278-280)

**Commit:** `8314ca2` (workspace repo)

**问题：** README 的测试徽章 (4205) 和对比表 (4034) 落后于实际测试数 (4394)。Cycles 278-280 新增的 6 个熵指数 API 完全未出现在 README 特性列表和 API 参考中。

**更新内容：**

| 区域 | 变更 |
|------|------|
| 测试徽章 | 4205 → **4394** |
| 对比表 Tests 行 | 4034 → **4394** |
| 特性列表 | "14 个度拓扑指数" → "19 度拓扑指数 + 5 熵指数"，含六族名称和 Cycles |
| API 参考 | 新增「熵指数家族」完整章节 |

**新增 API 文档（6 个）：**

| API | Cycle | 边权重公式 | K₂ 处理 |
|-----|-------|-----------|---------|
| `sombor_entropy()` | 278 | √(d_u²+d_v²) | 包含 |
| `reduced_sombor_entropy()` | 278 | √((d_u-1)²+(d_v-1)²) | 零贡献 |
| `randic_entropy()` | 279 | 1/√(d_u·d_v) | 包含 |
| `zagreb_m1_entropy()` | 279 | d_u+d_v | 包含 |
| `abc_entropy()` | 280 | √((d_u+d_v-2)/(d_u·d_v)) | 过滤 |
| `ga_entropy()` | 280 | 2√(d_u·d_v)/(d_u+d_v) | 包含 |

包含完整的汇总对比表和归一化说明。

### 2. context-forge — Code Health Audit (F59-F67)

**Commit:** `13686a3` (workspace repo)

**问题：** README 特性列表仅到 F34（主列表）+ F39-F40（高级章节），但 F59-F67（9 个代码健康分析功能）已实现并在 features.md 中记录，README 完全缺失。

**更新内容：**

**Features 列表新增子章节「Code Health Audit (F59–F67)」：**
- 🖥️ CLI health (F59) — 8 项检查
- 📦 Dependency risk (F60) — 5 类风险评估
- 🧪 Test coverage (F61) — 测试/源文件映射
- 📝 Logging health (F62) — console.log 污染检测
- 🔧 Env health (F63) — .env.example 覆盖分析
- ⚡ Performance patterns (F64) — 5 模式扫描器
- 🛡️ Type safety (F65) — TS 类型安全分析
- 💩 Code smells (F66) — 7 种代码异味
- 📖 README health (F67) — 10 节质量分析器

**详细文档章节（166 行新增）：**
每个功能包含：
- 功能描述和检测模式列表
- 代码示例（import + 调用 + 输出预览）
- 返回值结构表

## 推送状态

| 仓库 | Commit | 推送 |
|------|--------|------|
| workspace (amg) | `8314ca2` | ✅ pushed |
| workspace (context-forge) | `13686a3` | ✅ pushed |

## 下次关注

- **amg-mcp**: 主库 README 仍需度指数家族独立分组（多次报告遗留）
- **amg-mcp**: TUTORIAL.md 仍未创建 — API 接近 400 条
- **nano-agent**: API.md 需更新以包含 F17-F46 新方法
- **code-lab**: Cycle 244+ 新增功能检查 README 是否需要更新
- **context-forge**: features.md 中 F41-F58 的状态可同步到 README（目前 README 跳过了 F41-F58）
