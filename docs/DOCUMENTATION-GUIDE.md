# Documentation Maintenance Guide

> 如何维护和改进这个工作区的文档

## 📋 文档标准

### 文件命名规范

```
README.md        - 项目概览,快速开始
TUTORIAL.md      - 从零开始的教程
API.md           - API 参考文档
CONTRIBUTING.md  - 贡献指南
CHANGELOG.md     - 变更日志
EXAMPLES.md      - 示例集合
```

### 文档结构模板

#### README.md 模板

```markdown
# Project Name

> 一句话描述

## 🎯 概述

- 这是什么?
- 为什么需要它?
- 谁应该使用它?

## 🚀 快速开始 (5 分钟)

### 安装
### 基础使用
### 第一个示例

## 📚 核心功能

### 功能 1
### 功能 2

## ⚙️ 配置

## 📖 文档

- [教程](TUTORIAL.md)
- [API 参考](API.md)

## 🤝 贡献

## 📄 许可证
```

#### TUTORIAL.md 模板

```markdown
# Tutorial - Project Name

> 从零到精通

## 📚 目录

## 介绍

- 这是什么?
- 你将学到什么?

## 第一部分: 快速开始 (X 分钟)

### 步骤 1
### 步骤 2

## 第二部分: 核心概念

## 第三部分: 实战案例

## 第四部分: 高级特性

## 故障排除

## 总结

## 额外资源
```

---

## ✍️ 写作指南

### 1. 清晰简洁

**好的:**
```markdown
运行 `npm install` 安装依赖。
```

**不好的:**
```markdown
首先,你需要打开终端,然后导航到项目目录,接着运行 npm install 命令来安装所有必需的依赖包。
```

### 2. 提供示例

**好的:**
```markdown
## 使用方法

\`\`\`bash
# 基础使用
python script.py --input data.csv

# 高级选项
python script.py --input data.csv --output results.json --verbose
\`\`\`
```

**不好的:**
```markdown
## 使用方法

你可以使用各种参数来运行脚本。
```

### 3. 解释 "为什么"

**好的:**
```markdown
我们使用 PageRank 算法计算信任分数,因为它能有效地传播信任关系,类似于 Google 用于网页排名的方法。
```

**不好的:**
```markdown
我们使用 PageRank 算法。
```

### 4. 包含故障排除

**好的:**
```markdown
## 常见问题

### 问题: 安装失败

**原因:** 网络问题或权限不足

**解决方案:**
\`\`\`bash
# 使用国内镜像
npm install --registry=https://registry.npmmirror.com

# 或使用 sudo
sudo npm install
\`\`\`
```

### 5. 保持更新

在文档顶部添加最后更新时间:

```markdown
*最后更新: 2026-03-24*
*文档版本: 1.0*
```

---

## 🔄 文档维护流程

### 1. 定期审查

**频率:** 每月一次

**检查清单:**
- [ ] 代码示例是否仍然有效?
- [ ] 链接是否损坏?
- [ ] 版本号是否正确?
- [ ] 截图是否需要更新?
- [ ] 是否有新的功能未文档化?

**工具:**

```bash
# 检查链接
markdown-link-check README.md

# 检查拼写
markdown-spellcheck -r README.md

# 检查格式
markdownlint README.md
```

### 2. 用户反馈

**收集渠道:**
- GitHub Issues
- 用户评论
- 内部反馈

**处理流程:**

1. 收集常见问题
2. 添加到 FAQ 章节
3. 更新教程中的故障排除
4. 改进不清楚的部分

### 3. 版本更新

**当发布新版本时:**

1. 更新 CHANGELOG.md
2. 更新 API.md 中的变更
3. 在 README.md 中更新版本号
4. 添加新功能的文档
5. 标记废弃的功能

---

## 📊 文档质量检查清单

### README.md 检查清单

- [ ] 项目名称和描述清晰
- [ ] 快速开始能在 5 分钟内完成
- [ ] 安装说明完整
- [ ] 至少有一个工作示例
- [ ] 链接到详细文档
- [ ] 许可证信息
- [ ] 联系方式或支持渠道

### TUTORIAL.md 检查清单

- [ ] 目标受众明确
- [ ] 学习目标清晰
- [ ] 步骤按顺序编号
- [ ] 每个步骤都能独立验证
- [ ] 包含预期输出
- [ ] 有故障排除章节
- [ ] 有总结和下一步

### API.md 检查清单

- [ ] 所有公共方法都有文档
- [ ] 参数类型和说明
- [ ] 返回值类型和说明
- [ ] 异常和错误情况
- [ ] 使用示例
- [ ] 版本兼容性说明

---

## 🛠️ 文档工具

### Markdown 检查工具

```bash
# 安装
npm install -g markdownlint-cli
npm install -g markdown-link-check

# 使用
markdownlint README.md
markdown-link-check README.md
```

### 自动生成 API 文档

```bash
# TypeScript
npm install -g typedoc
typedoc --out docs src

# Python
pip install pdoc3
pdoc --html --output-dir docs module_name
```

### 文档站点生成

```bash
# MkDocs (Python)
pip install mkdocs
mkdocs serve

# Docsify (JavaScript)
npm install -g docsify-cli
docsify serve docs
```

---

## 📝 文档模板库

### 项目文档

```markdown
# Project Name

<div align="center">
  <img src="logo.png" alt="Logo" width="200">
  <p><strong>简短描述</strong></p>
  <img src="https://img.shields.io/badge/version-1.0.0-blue">
  <img src="https://img.shields.io/badge/license-MIT-green">
</div>

## 🎯 概述

## 🚀 快速开始

## 📚 文档

## 🤝 贡献

## 📄 许可证

## 🙏 致谢
```

### API 文档

```markdown
# API Reference

## Class: ClassName

### 描述
简要描述这个类的用途。

### 构造函数

#### `new ClassName(options)`

**参数:**
- `options` (Object)
  - `param1` (string) - 参数说明
  - `param2` (number) - 参数说明

**示例:**
\`\`\`javascript
const instance = new ClassName({
  param1: 'value',
  param2: 42
});
\`\`\`

### 方法

#### `methodName(param)`

**描述:** 方法说明

**参数:**
- `param` (string) - 参数说明

**返回值:** (Promise<Result>) 返回值说明

**异常:** 可能抛出的异常

**示例:**
\`\`\`javascript
const result = await instance.methodName('value');
\`\`\`
```

### 教程文档

```markdown
# Tutorial - Title

> 时间: X 分钟 | 难度: 初级/中级/高级

## 📚 目录

## 你将学到什么

- 目标 1
- 目标 2

## 前置要求

- 要求 1
- 要求 2

## 步骤 1: 标题

### 说明

### 操作

\`\`\`bash
command
\`\`\`

### 验证

\`\`\`bash
verification command
\`\`\`

### 预期输出

\`\`\`
expected output
\`\`\`

## 步骤 2: 标题

...

## 故障排除

### 问题: 问题描述

**原因:** 原因

**解决方案:**
\`\`\`bash
solution
\`\`\`

## 总结

## 下一步
```

---

## 🌐 多语言文档

### 结构

```
docs/
├── README.md          # 默认(中文)
├── en/
│   ├── README.md
│   ├── TUTORIAL.md
│   └── API.md
└── zh/
    ├── README.md
    ├── TUTORIAL.md
    └── API.md
```

### 语言切换链接

```markdown
[English](en/README.md) | [中文](zh/README.md)
```

---

## 📈 文档指标

### 跟踪指标

1. **可读性评分**
   - 使用 Flesch-Kincaid 或类似工具
   - 目标: 8 年级阅读水平

2. **完整性**
   - 所有公共 API 是否文档化?
   - 所有功能是否有示例?

3. **准确性**
   - 代码示例是否能运行?
   - 链接是否有效?

4. **用户满意度**
   - 收集反馈
   - 监控支持请求

### 工具

```bash
# 可读性评分
npm install -g alex
alex README.md

# 文档覆盖率
npm install -g documentation
documentation coverage src/**/*.js
```

---

## 🔍 文档审查清单

### 新功能发布前

- [ ] README.md 已更新
- [ ] CHANGELOG.md 已更新
- [ ] API 文档已更新
- [ ] 教程已更新(如果需要)
- [ ] 示例已添加
- [ ] 代码示例已测试
- [ ] 链接已检查
- [ ] 拼写已检查
- [ ] 格式已检查

### 定期维护

- [ ] 每月检查一次链接
- [ ] 每季度更新截图
- [ ] 每半年审查结构
- [ ] 根据反馈持续改进

---

## 💡 最佳实践

### 1. 写给初学者

假设读者是第一次接触你的项目。

### 2. 使用活跃语态

**好的:** "运行这个命令来安装依赖。"

**不好的:** "依赖可以通过运行这个命令来安装。"

### 3. 提供上下文

解释代码示例的作用和为什么这样做。

### 4. 使用视觉元素

- 图表说明复杂概念
- 截图展示 UI
- 代码高亮重要部分

### 5. 保持一致

- 使用相同的术语
- 保持格式一致
- 遵循风格指南

---

## 🤝 贡献文档

### 如何贡献

1. Fork 仓库
2. 创建分支: `git checkout -b docs/improvement`
3. 修改文档
4. 提交: `git commit -m "docs: improve installation guide"`
5. 推送: `git push origin docs/improvement`
6. 创建 Pull Request

### 提交信息格式

```
docs: 简短描述

- 详细说明 1
- 详细说明 2

Closes #issue-number
```

### 审查标准

- 准确性
- 清晰度
- 完整性
- 格式
- 拼写和语法

---

## 📞 获取帮助

- **文档问题:** 提交 Issue
- **建议改进:** 创建 Discussion
- **紧急修复:** 直接提交 PR

---

*最后更新: 2026-03-24*  
*维护者: OpenClaw Workspace Team*
