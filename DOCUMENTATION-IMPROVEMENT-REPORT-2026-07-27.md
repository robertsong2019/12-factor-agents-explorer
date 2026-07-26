# 文档完善报告 — 2026-07-27

## 概要

本轮聚焦 **amg-mcp TUTORIAL.md 的创建**——这是连续多轮报告中标记为"下次关注"的头号遗留项。同时修正了 README 中工具数量的严重错误（6→14）。

## 变更详情

### amg-mcp — TUTORIAL.md 从零创建

**Commit:** `7d1b026`
**变更量:** +656 行 / -3 行

#### 创建内容

完整的 30 分钟教程，覆盖全部 **14 个工具**：

**教程结构：**
1. **Prerequisites & Installation** — 环境要求和安装步骤
2. **Connecting to MCP Clients** — Claude Desktop / Cursor / HTTP / Inspector
3. **6 Core Workflows** — Learn, Recall, Curate, Connect, Reflect, Backup
4. **14 个工具逐一详解** — 每个含 JSON 示例、参数表、使用技巧：
   - `memory.remember` — 6 种 kind 示例
   - `memory.recall` — 关键词搜索
   - `memory.query` — 高级过滤搜索（kind/date/sort）
   - `memory.health` — 健康分数解读表
   - `memory.forget` — 安全删除指南
   - `memory.consolidate` — 阈值指南表 + Jaccard 原理
   - `memory.gaps` — 结构/时间/语义三类间隙
   - `memory.skills` — 模式挖掘和技能提升
   - `memory.relate` — 6 种关系类型表
   - `memory.neighbors` — 图遍历和多跳推理
   - `memory.reflect` — 4 种自省模式
   - `memory.export` / `memory.import` — 备份/恢复/迁移
   - `memory.stats` — 详细图分析
5. **4 个真实场景模式** — 新项目上手、事故学习、周维护、多 Agent 共享
6. **Best Practices** — DO/DON'T 对照表
7. **Troubleshooting** — 5 个常见问题及解决方案

### amg-mcp — README.md 修正

- **工具数修正:** "6 curated tools" → "14 curated tools"
  - 实际工具：recall, remember, health, forget, query, consolidate + gaps, skills, relate, reflect, neighbors, export, import, stats
- **Roadmap 更新:** Phase 1 从"Day 1–2"改为"Complete"（HTTP 已工作）
- **新增 Tutorial 区块** 链接到 TUTORIAL.md

## 问题背景

amg-mcp 的 README 只详细文档化了前 6 个工具（Tool 1-6），但 `server.ts` 中实际注册了 14 个工具。README 的 Phase 1 描述也过时（说"6 curated tools"）。TUTORIAL.md 在此前多轮报告中反复标记为未创建，本次终于完成。

## 文档覆盖状态

| 项目 | README | TUTORIAL | API.md | 状态 |
|------|--------|----------|-------|------|
| amg-mcp | ✅ 修正（14 tools） | ✅ **本次创建** | N/A | ✅ 完整 |
| nano-agent | ✅ 完整 | 待添加 F17-F46 示例 | ✅ 完整（F1-F46） | ⚠️ TUTORIAL 可增强 |
| context-forge | ✅ F1-F67 | N/A | N/A | ✅ 完整 |
| code-lab | ✅ 74 行 | ✅ 存在 | N/A | ⚠️ 可检查 Cycle 244+ |

## 推送状态

| 仓库 | Commit | 推送 |
|------|--------|------|
| amg-mcp | `7d1b026` | 待推送 |

## 下次关注

1. **nano-agent**: TUTORIAL.md 可添加 F17-F46（模糊搜索、集合运算、聚类分析等）的实战示例
2. **amg-mcp**: README 中 Tools 区块仍只详述了 6 个工具——可补全 gaps/skills/relate/reflect/neighbors/export/import/stats 的简要文档
3. **code-lab**: 检查 Cycle 244+ 新增功能的 README 覆盖
4. **context-forge**: 确认 README 中 F41-F58 状态是否已同步

---

*Generated: 2026-07-27 04:00 AM · Documentation cron*
