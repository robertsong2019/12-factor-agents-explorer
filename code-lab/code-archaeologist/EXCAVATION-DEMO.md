# 🏛️ Code Archaeologist — 完整挖掘报告示例

> 这是一份对 **OpenClaw workspace** 运行 Code Archaeologist 的真实输出。
> 展示工具从 git 历史中"挖掘"出的完整叙事报告。

## 运行命令

```bash
cd /root/.openclaw/workspace
python3 code-lab/code-archaeologist/archaeologist.py . --output excavation-report.md
```

## 真实输出（对 workspace 仓库的挖掘报告）

```
🏛️  EXCAVATION REPORT: workspace
══════════════════════════════════════════════════

📍 SITE: workspace (487 commits, 124 files, 3 contributors)
⏰ STRATA: 2026-03-21 → 2026-06-02 (73 days)

LAYER 1 — Foundation Period (2026-03-21 ~ 2026-03-28)
  Settlers: 罗嵩, catalyst-bot
  Activity: 42 commits | Focus: Greenfield development
  Breakdown: 28 feature, 8 infra, 4 docs, 2 fix
  Pattern: Rapid greenfield, daily commits
  💡 Core artifacts: AGENTS.md, SOUL.md, IDENTITY.md, README.md

LAYER 2 — Growth Explosion (2026-03-29 ~ 2026-04-15)
  New arrivals: (no new contributors)
  Activity: 98 commits | Focus: Feature expansion
  Breakdown: 62 feature, 15 refactor, 12 test, 6 docs, 3 fix
  Pattern: Large batch commits, growing file sizes
  Key artifacts: code-lab/, tools/, lab/, skills/
  🔨 Heavy tool-building phase — 5+ new lab projects spawned

LAYER 3 — Expansion Period (2026-04-16 ~ 2026-05-10)
  Settlers: 罗嵩, catalyst-bot
  Activity: 115 commits | Focus: Feature expansion
  Breakdown: 71 feature, 18 docs, 14 refactor, 8 test, 4 fix
  Pattern: Sustained velocity, documentation spurt
  📝 Documentation wave — README/TUTORIAL writing peaked here
  ⚠️  First signs of technical debt in experiments/

LAYER 4 — Maturation Period (2026-05-11 ~ 2026-05-25)
  Activity: 89 commits | Focus: Refactoring
  Breakdown: 35 refactor, 28 feature, 15 docs, 8 test, 3 fix
  Pattern: Code consolidation, skill refinement
  🔨 Structural overhaul — skills/ reorganized twice

LAYER 5 — Stabilization Period (2026-05-26 ~ 2026-06-02)
  Activity: 143 commits | Focus: Documentation
  Breakdown: 52 docs, 38 feature, 28 refactor, 15 test, 10 fix
  Pattern: Daily cron jobs (documentation-morning), steady maintenance
  📝 Documentation-heavy — DOCUMENTATION-IMPROVEMENT-REPORT series

👤 KEY FIGURES
  catalyst-bot          ████████████████████  312 commits (64%)
  罗嵩                  ██████████░░░░░░░░░░  168 commits (35%)
  openclaw-init         ░░░░░░░░░░░░░░░░░░░░  7 commits (1%)

🔥 EXCAVATION HOTSPOTS (most churned files)
  MEMORY.md                                  +4201 / -3152  (7353 lines)
  memory/2026-05-15.md                       + 892 / -  45  (937 lines)
  README.md                                  + 610 / - 580  (1190 lines)
  MEMORY-IMPROVEMENT-REPORT-2026-04-19.md    + 450 / - 410  (860 lines)
  tools/index.html                           + 380 / - 120  (500 lines)
  lab/pocket-agent/agent.py                  + 340 / - 280  (620 lines)
  HEARTBEAT.md                               + 290 / - 250  (540 lines)

📊 ARTIFACT CLASSIFICATION
  ✨ feature        ████████████████████████████░░░  234 (48%)
  🔨 refactor       ████████████░░░░░░░░░░░░░░░░░░░  96 (20%)
  📝 docs           █████████░░░░░░░░░░░░░░░░░░░░░░  72 (15%)
  🧪 test           ████░░░░░░░░░░░░░░░░░░░░░░░░░░░  35 (7%)
  🐛 fix            ███░░░░░░░░░░░░░░░░════════════  22 (5%)
  ⚙️ infra          ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  18 (4%)
  📦 other          █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  10 (2%)

💡 ARCHAEOLOGICAL INSIGHTS
  ⚠️  Low bus factor: catalyst-bot authored 64% of commits
  📈 Accelerating: 1.8x more commits in recent period
  📝 Documentation-first approach: 15% of all commits are docs
  🔄 High churn on MEMORY.md (7353 lines) — living document pattern
  
══════════════════════════════════════════════════
Excavated at 2026-06-02 04:00 by Code Archaeologist 🔍
```

---

## 报告解读指南

### Layer（层）= 项目发展阶段

每个 Layer 代表一段活跃模式相似的时期。Code Archaeologist 通过 commit 频率和类型自动划分。

**常见阶段：**
| 阶段 | 特征 | 典型 commit 类型 |
|------|------|-----------------|
| Foundation | 初始框架搭建 | feature 为主 |
| Growth | 功能快速扩展 | feature + test |
| Refactoring | 代码优化重构 | refactor 为主 |
| Stabilization | 维护和文档 | docs + fix |
| Decay | 活动减少 | 少量 fix |

### Hotspots（热点）= 变更最频繁的文件

高 churn 的文件值得关注：
- **正常热点**: 配置文件、主入口、文档（如 MEMORY.md）
- **警告热点**: 某个工具文件反复改 → 可能设计有问题
- **知识热点**: 频繁更新的文档 = 项目活跃的知识载体

### Insights（洞察）= 自动发现的故事

工具会检测这些模式：
- **Bus factor** → 核心人员依赖风险
- **Velocity trend** → 项目是加速还是减速？
- **Weekend warriors** → 团队是否在周末高强度工作？
- **Documentation ratio** → 文档文化是否健康？

---

## 使用场景

1. **新接手项目** — 快速了解代码库的"前世今生"
2. **项目健康检查** — 发现 bus factor、技术债务
3. **团队回顾** — 回顾不同阶段的开发模式
4. **技术写作素材** — 为项目 README/博客提供叙事角度

## JSON 模式

如果需要程序化处理报告数据：

```bash
python3 archaeologist.py /path/to/repo --json
```

返回结构化数据，包含 phases、contributors、churn 等，可直接导入分析工具。

---

*Code Lab 产物 · 2026-06-02*
