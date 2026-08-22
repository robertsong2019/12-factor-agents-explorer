# skill-scaffolder

快速生成 OpenClaw Agent Skill 骨架的 CLI 工具。

## 安装

```bash
cd tools/skill-scaffolder
npm install
npm link  # 全局可用 skill-create
```

## 使用

### 创建新 skill

```bash
# 基础 skill
skill-create new my-skill -d "我的自定义 skill"

# API 集成 skill（自动包含 references/ 和 scripts/）
skill-create new github-api -t api -d "GitHub API 集成"

# MCP Server skill
skill-create new my-mcp -t mcp

# 编码辅助 skill
skill-create new python-helper -t coding --with-references
```

### 列出模板

```bash
skill-create templates
```

### 验证 skill 结构

```bash
skill-create validate ./my-skill
```

## 模板类型

| 模板 | 说明 |
|------|------|
| basic | 基础 skill，仅 SKILL.md |
| api | API 集成，含认证和错误处理模板 |
| mcp | MCP Server，含工具定义模板 |
| coding | 编码辅助，含代码模式模板 |

## Testing

```bash
npm test   # node --test test/*.test.js — 29 tests
```

`test/skill-scaffolder.test.js` covers the library API (create/list/validate); `test/cli.test.js` is a real-process e2e suite (`spawnSync`) covering help/version, templates, all `new` exit paths, validate exit codes — plus regressions for two bugs fixed on 2026-08-23: (A) `validate` exited 0 on an invalid skill; (B) the api template generated invalid env-var names (hyphens) for kebab-case skill names. All runs are sandboxed to a tmpdir.

## 设计原则

- **零依赖生成**: 只需 fs-extra（Node 内置即可工作）
- **模板驱动**: 4 种预置模板，覆盖常见场景
- **验证内置**: 创建后可立即验证结构
- **增量友好**: 生成的文件都是精心设计的起点，不是死板骨架

## 生成目录结构示例

```
my-skill/
├── SKILL.md          # 必需 — skill 定义
├── references/       # 可选 — 参考文档
│   └── README.md
└── scripts/          # 可选 — 辅助脚本
    └── helper.js
```
