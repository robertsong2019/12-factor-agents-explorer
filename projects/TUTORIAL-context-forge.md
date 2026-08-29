# Tutorial: 用 context-forge 让 AI 编码助手真正理解你的项目

> **适合**: 任何使用 Cursor / Claude Code / Copilot / Codex 的开发者
> **难度**: 初级
> **时间**: 10 分钟

---

## 你有没有遇到过这些问题？

- Cursor 总是生成不符合你项目风格的代码？
- Claude Code 不知道你的项目用什么测试框架？
- 每次开新对话都要重复解释项目结构？

**根本原因**: AI 编码助手不知道你的项目上下文。它们需要一份"项目说明书"。

`context-forge` 就是自动生成这份说明书的工具。

---

## 概念：什么是"上下文文件"？

AI 编码助手通过读取项目中的特定文件来理解项目：

| 文件 | 谁读它 | 里面有什么 |
|------|--------|-----------|
| `AGENTS.md` | OpenClaw, Claude Code | 项目约定、构建步骤、代码风格 |
| `.cursorrules` | Cursor | 编辑器规则和上下文 |
| `.github/copilot-instructions.md` | GitHub Copilot | PR/代码审查指南 |
| `.claude/CLAUDE.md` | Claude Code | 详细项目指令 |

手动写这些文件很烦，而且容易过时。**context-forge 自动生成它们。**

---

## Step 1: 安装

```bash
# 确保你有 Node.js (v18+)
node --version

# 下载单文件（零依赖）
cp context-forge.mjs /usr/local/bin/context-forge
chmod +x /usr/local/bin/context-forge
```

就这样。不需要 `npm install`，不需要任何依赖。

---

## Step 2: 预览（不写文件）

在运行之前，先看看它会生成什么：

```bash
context-forge /path/to/your-project --dry-run
```

你会看到类似这样的输出：

```markdown
## AGENTS.md

# Project: my-app

## Overview
Node.js (ESM) project with TypeScript.

## Dependencies
- express (production)
- jest (development)

## Scripts
- `npm test` — Run tests with Jest
- `npm start` — Start server

## Conventions
- Language: TypeScript
- Entry points: src/index.ts
```

**这时候没有任何文件被修改。** 安全地预览。

---

## Step 3: 正式生成

确认预览内容没问题后：

```bash
context-forge /path/to/your-project
```

这会在项目目录下生成 4 个上下文文件。

---

## Step 4: 添加你的定制内容

自动生成的内容是基础。你可以在此基础上添加项目特有的规则：

```bash
context-forge /path/to/your-project --update
```

**关键**: `--update` 模式会保留你手动添加的内容。原理是使用标记：

```markdown
<!-- context-forge:start -->
这部分是自动生成的，会被更新
<!-- context-forge:end -->

这部分是你手动写的，更新时会被保留
```

---

## 实战案例：给一个 Express 项目生成上下文

```bash
# 1. 克隆或进入项目
cd ~/my-express-app

# 2. 预览
context-forge . --dry-run

# 3. 生成
context-forge .

# 4. 检查生成的 AGENTS.md
cat AGENTS.md

# 5. 在标记外添加你的规则
# 例如：禁止使用 var，必须用 async/await 等

# 6. 下次更新时保留你的修改
context-forge . --update
```

---

## 它是怎么工作的？

简单三步：

1. **检测项目类型** — 扫描 `package.json`、`pyproject.toml`、`Cargo.toml` 等
2. **分析结构** — 读取目录结构、入口文件、依赖关系
3. **生成文件** — 根据模板为每个 AI 工具生成对应格式

支持的检测：
- **语言**: JavaScript, TypeScript, Python, Go, Rust, Ruby, Java, Kotlin, Swift, Zig, Vue, Svelte
- **包管理**: npm/pnpm/yarn, pip/poetry, cargo, go modules
- **框架**: 自动从依赖中推断（express, fastapi, react, next.js 等）

---

## 只生成特定文件

不需要所有文件？只生成你用的：

```bash
# 只生成 AGENTS.md（给 Claude Code / OpenClaw 用）
context-forge . --only agents

# 只生成 .cursorrules（给 Cursor 用）
context-forge . --only cursor

# 只生成 Copilot 指令
context-forge . --only copilot

# 只生成 .claude/CLAUDE.md
context-forge . --only claude

# 导出结构化数据（给其他工具消费）
context-forge . --format=json
context-forge . --format=toml
context-forge . --format=yaml
```

---

## 进阶：不止生成上下文文件，还是代码体检仪

生成上下文文件只是上半场。context-forge 内置了 **28+ 个代码健康分析器**（F35–F82），可以给你的项目做全身体检，每个维度都给 A–F 评级。

### 为什么需要？

AI 助手生成的代码质量取决于它看到的上下文——但**你自己的代码**也会被 AI 模仿。如果项目里充满空的 catch 块、资源泄漏和 `eval`，AI 会继续这个风格。先用分析器找出这些问题：

### 两类调用方式

分析器分两种传参方式，用错不会报错——而是**静默返回空白结果 + 满分评级**（比报错更危险）：

**① 传文件列表**（大多数，包括 F53–F59、F61–F66、F75–F82 全家）：接收 `[{ path, content }]` 数组

**② 传目录/根路径**（少数）：`detectTestFiles(root)`、`detectApiRoutes(root)`、`analyzeGitHotspots(root)`、`detectNamingConventions(root)`、`detectSecrets(root)`、`analyzeFileSizes(root)`、`extractImports(root, 3)` 等

```javascript
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import {
  analyzeErrorHandling, analyzeCyclomaticComplexity,
  formatCyclomaticComplexityReport, detectApiRoutes,
} from './context-forge.mjs'

// ① 文件列表式：先收集文件（定义一次，处处复用）
const loadFiles = (...dirs) => dirs.flatMap(dir =>
  readdirSync(dir, { withFileTypes: true, recursive: true })
    .filter(e => e.isFile())
    .map(e => {
      const path = join(e.parentPath ?? e.path, e.name)
      return { path, content: readFileSync(path, 'utf8') }
    }))

const eh = analyzeErrorHandling(loadFiles('./src'))
console.log(eh.total, eh.grade)  // 找到的问题数 + 评级

const cc = analyzeCyclomaticComplexity(loadFiles('./src'))
console.log(formatCyclomaticComplexityReport(cc))

// ② 目录式：直接扫
const routes = await detectApiRoutes('./src')
console.log(routes.count)
```

> ⚠️ 体检结果中 grade= A 且 issues=0 不一定是好事——先确认扫描的文件数（`totalFiles` / `filesScanned`）不为零，否则可能是传参方式用错了（文件列表 vs 目录）。

### 分析器全景图

按用途分四组，完整列表见 [README](./context-forge/README.md)：

| 组 | 代表分析器 | 找什么 |
|---|---|---|
| **代码质量** (F46–F58) | error handling、duplicate code、async patterns、comment health | 空 catch、浮动 Promise、复制粘贴代码、缺失的 await |
| **代码结构** (F75–F81) | cyclomatic/cognitive complexity、guard clauses、return paths | 深嵌套、超复杂函数、过多参数、不可达代码 |
| **安全与资源** (F80, F82) | resource leaks、security anti-patterns | 未清理的 `setInterval`/监听器、`eval`、XSS、SQL 拼接 |
| **项目体检** (F59–F67) | CLI health、test coverage、logging、README health | 缺 --help、未测文件、console.log 污染、坏链接 |

每个分析器都有 `formatXxxReport()` 配套函数，输出 markdown 报告；`{ stats, issues, score, grade }` 是结构家族的统一返回形状。

### 实战：给项目做一次体检

```javascript
// checkup.mjs — 一行一个维度，5 分钟搭好项目体检
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import {
  analyzeErrorHandling, analyzeCyclomaticComplexity,
  formatCyclomaticComplexityReport,
} from './context-forge.mjs'

const loadFiles = (...dirs) => dirs.flatMap(dir =>
  readdirSync(dir, { withFileTypes: true, recursive: true })
    .filter(e => e.isFile())
    .map(e => {
      const path = join(e.parentPath ?? e.path, e.name)
      return { path, content: readFileSync(path, 'utf8') }
    }))

const files = loadFiles('./src')
const eh = analyzeErrorHandling(files)
const cc = analyzeCyclomaticComplexity(files)
console.log('错误处理:', eh.total, '个问题，评级', eh.grade)
console.log('圈复杂度: 评级', cc.grade)
console.log(formatCyclomaticComplexityReport(cc))
```

跑 `node checkup.mjs`，按报告里的 `issues` 从 critical 往下修。修完再跑一次，看 grade 爬升。

> 常用目录式分析器（无需 loadFiles）：`detectTestFiles`、`detectApiRoutes`、`analyzeGitHotspots`、`analyzeFileSizes`、`extractImports`——直接传项目路径。

---

## 扩展和定制

`context-forge.mjs` 是一个单文件，可以自由修改：

- **添加新的项目检测器** — 写一个返回 `{ type, language, framework }` 的函数
- **添加新的输出模板** — 为新的 AI 工具添加生成函数
- **修改标记格式** — 改 `MARKER_START`/`MARKER_END` 常量

---

## 总结

| 场景 | 命令 / API |
|------|-----------|
| 首次使用 | `context-forge .` |
| 预览不写入 | `context-forge . --dry-run` |
| 更新保留手动内容 | `context-forge . --update` |
| 只生成 Cursor 规则 | `context-forge . --only cursor` |
| 结构化导出 | `context-forge . --format=json\|toml\|yaml` |
| 代码体检 | `analyzeErrorHandling('./src')` 等分析器 |
| 格式化报告 | `formatXxxReport(result)` |

**核心思路**: 让 AI 工具自动读取项目上下文 → 生成的代码质量显著提升 → 用分析器保证存量代码本身是好的范本 → 省去每次对话重复解释的麻烦。

---

_基于 [context-forge](./context-forge/) 项目 · 2026-08-30 更新（覆盖 CLI + F35–F82 分析器套件）_
