# Frequently Asked Questions (FAQ)

> 工作区常见问题解答

## 📋 目录

- [通用问题](#通用问题)
- [Agent Task CLI](#agent-task-cli)
- [Local Embedding Memory](#local-embedding-memory)
- [Agent Trust Network](#agent-trust-network)
- [技能系统](#技能系统)
- [文档维护](#文档维护)
- [故障排除](#故障排除)

---

## 通用问题

### ❓ 这个工作区是什么？

**A:** 这是一个 AI Agent 的工作空间，包含多个实验性项目和工具：
- **Agent Task CLI**: 任务管理命令行工具
- **Local Embedding Memory**: 语义搜索工具
- **Agent Trust Network**: 信任网络模拟器
- **技能系统**: 各种扩展技能

### ❓ 如何快速开始？

**A:** 查看各个项目的 README.md 和 GETTING-STARTED.md：

```bash
# 查看工作区概览
cat README.md

# 查看快速开始指南
cat GETTING-STARTED.md

# 选择一个项目开始
cd projects/agent-task-cli
cat README.md
```

### ❓ 项目之间的关系是什么？

**A:** 工作区采用三层架构：
1. **工作区层**: 全局文档和配置
2. **项目层**: 独立的项目（agent-task-cli, embedding, trust-network）
3. **技能层**: 可复用的功能模块

---

## Agent Task CLI

### ❓ Agent Task CLI 是什么？

**A:** 一个命令行工具，用于管理和执行 AI Agent 任务，具有以下特性：
- 109 个测试用例
- 80%+ 代码覆盖率
- 支持多种任务类型
- 完整的错误处理

### ❓ 如何安装 Agent Task CLI？

**A:**
```bash
cd projects/agent-task-cli
npm install
npm run build
npm link  # 全局安装

# 验证安装
agent-task --version
```

### ❓ Agent Task CLI 支持哪些任务类型？

**A:** 支持以下任务类型：
- `file`: 文件操作任务
- `api`: API 调用任务
- `script`: 脚本执行任务
- `workflow`: 工作流任务
- `custom`: 自定义任务

### ❓ 如何调试任务执行？

**A:** 使用详细模式：
```bash
agent-task run task.json --verbose
agent-task run task.json --debug
```

### ❓ 如何编写自定义任务？

**A:** 参考 TUTORIAL.md：
```bash
cat projects/agent-task-cli/TUTORIAL.md
```

---

## Local Embedding Memory

### ❓ Local Embedding Memory 是什么？

**A:** 一个本地语义搜索工具，用于搜索 Markdown 格式的记忆文件：
- 无需 API 调用（完全本地）
- 语义理解（不仅仅是关键词）
- 快速（80MB 轻量模型）
- 支持增量索引

### ❓ 如何索引我的记忆文件？

**A:**
```bash
cd experiments/local-embedding-memory
python memory_embedder.py --index
```

### ❓ 如何搜索记忆？

**A:**
```bash
# 命令行搜索
python memory_embedder.py --search "AI Agent memory patterns"

# 交互式搜索
python interactive_demo.py

# Web UI
python web_ui.py --port 8080
```

### ❓ 为什么搜索结果不准确？

**A:** 可能的原因和解决方案：

1. **索引过时**
   ```bash
   # 重新索引
   python memory_embedder.py --index
   ```

2. **查询太模糊**
   - 使用更具体的描述
   - 包含关键词和上下文

3. **文件格式问题**
   - 确保使用 Markdown 格式
   - 使用清晰的标题结构

### ❓ 如何比较语义搜索和文本搜索？

**A:**
```bash
python memory_embedder.py --compare "your query"
```

这会同时显示两种搜索的结果，方便对比。

### ❓ 支持哪些文件格式？

**A:** 目前仅支持 Markdown 文件：
- `MEMORY.md` - 主记忆文件
- `memory/*.md` - 每日笔记
- 任何 `.md` 文件

---

## Agent Trust Network

### ❓ Agent Trust Network 是什么？

**A:** 一个多 Agent 信任网络模拟器，使用 PageRank 式算法：
- 模拟 Agent 之间的信任关系
- 自动检测恶意 Agent
- 可视化网络拓扑
- 支持多种 Agent 行为类型

### ❓ 如何运行演示？

**A:**
```bash
cd experiments/agent-trust-network
npm install
npm run demo
```

### ❓ Agent 的行为类型有哪些？

**A:**
- 🟢 **cooperative**: 合作型，85% 成功率
- 🟡 **neutral**: 中立型，65% 成功率
- 🔴 **malicious**: 恶意型，40% 成功率
- ⚫ **adversarial**: 对抗型，10% 成功率

### ❓ 如何创建自定义网络？

**A:** 参考 TUTORIAL.md：
```typescript
import { Agent } from './src/agent';
import { TrustNetwork } from './src/trust-network';

const network = new TrustNetwork();
const alice = new Agent({
  id: 'alice',
  behavior: 'cooperative'
});
network.addAgent(alice);
```

### ❓ 信任分数如何计算？

**A:** 使用 PageRank 式算法：
```
TrustScore = (1 - d) / N + d × Σ(IncomingTrust / OutgoingDegree)
```
其中：
- `d` = 阻尼因子（默认 0.85）
- `N` = Agent 总数

### ❓ 如何检测恶意 Agent？

**A:**
```typescript
const maliciousAgents = network.getMaliciousAgents();
console.log(maliciousAgents);
```

系统会自动识别信任分数低于阈值的 Agent。

---

## 技能系统

### ❓ 什么是技能（Skills）？

**A:** 技能是可复用的功能模块，存储在 `skills/` 目录：
- 每个 skill 都有 `SKILL.md` 说明文档
- 可以包含脚本、配置、参考文档
- 通过 OpenClaw 激活和使用

### ❓ 如何使用技能？

**A:** 查看 skill 的 `SKILL.md`：
```bash
cat skills/akshare-finance/SKILL.md
```

### ❓ 如何创建新技能？

**A:** 参考 [skill-creator](skills/../../../skills/skill-creator/SKILL.md) 技能：
```bash
cat ~/.local/share/pnpm/global/5/.pnpm/openclaw@*/node_modules/openclaw/skills/skill-creator/SKILL.md
```

### ❓ 技能和项目有什么区别？

**A:**
- **项目**: 独立的完整应用，有自己的测试和文档
- **技能**: 轻量级功能模块，可被多个项目复用

---

## 文档维护

### ❓ 如何维护文档？

**A:** 遵循 `DOCUMENTATION-GUIDE.md`：
```bash
cat DOCUMENTATION-GUIDE.md
```

关键原则：
- 保持简洁
- 提供示例
- 解释 "为什么"
- 包含故障排除

### ❓ 文档结构是什么？

**A:** 标准文档文件：
- `README.md` - 项目概览和快速开始
- `TUTORIAL.md` - 详细教程
- `API.md` - API 参考
- `CONTRIBUTING.md` - 贡献指南
- `CHANGELOG.md` - 变更日志

### ❓ 如何更新 CHANGELOG？

**A:** 遵循 [Keep a Changelog](https://keepachangelog.com/) 格式：
```markdown
## [版本号] - 日期

### Added
- 新功能

### Changed
- 变更内容

### Fixed
- 修复内容
```

### ❓ 如何检查文档质量？

**A:** 使用检查清单（见 `DOCUMENTATION-GUIDE.md`）：
```bash
# 检查链接
markdown-link-check README.md

# 检查格式
markdownlint README.md
```

---

## 故障排除

### ❓ 通用故障排除步骤

**A:**
1. 检查依赖是否安装
2. 查看项目文档的 "故障排除" 章节
3. 检查日志和错误信息
4. 尝试重新安装或重建
5. 查看项目的 Issues

### ❓ Python 项目依赖问题

**A:**
```bash
# 重新创建虚拟环境
cd experiments/local-embedding-memory
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### ❓ Node.js 项目依赖问题

**A:**
```bash
# 清理并重新安装
cd projects/agent-task-cli
rm -rf node_modules package-lock.json
npm install
```

### ❓ TypeScript 编译错误

**A:**
```bash
# 检查 TypeScript 版本
npm list typescript

# 清理并重新编译
npm run clean
npm run build
```

### ❓ 找不到命令

**A:**
```bash
# 检查是否已安装
which agent-task

# 如果没有，尝试链接
npm link

# 或使用 npx
npx agent-task
```

### ❓ 权限错误

**A:**
```bash
# 检查文件权限
ls -la

# 修复权限
chmod +x script.sh

# 或使用 sudo（谨慎）
sudo npm install -g package-name
```

### ❓ 内存不足错误

**A:**
```bash
# 增加 Node.js 内存限制
export NODE_OPTIONS="--max-old-space-size=4096"

# 或在命令中指定
node --max-old-space-size=4096 script.js
```

---

## 获取帮助

### ❓ 在哪里提问？

**A:**
1. 查看项目的 README 和 TUTORIAL
2. 查看这个 FAQ
3. 查看 DOCUMENTATION-GUIDE.md
4. 检查项目的 Issues
5. 联系维护者

### ❓ 如何报告 Bug？

**A:** 参考 `CONTRIBUTING.md`：
```bash
cat CONTRIBUTING.md
```

关键信息：
- 清晰的标题
- 重现步骤
- 预期行为
- 实际行为
- 环境信息

### ❓ 如何贡献代码？

**A:** 参考 `CONTRIBUTING.md`：
1. Fork 仓库
2. 创建功能分支
3. 编写代码和测试
4. 提交 Pull Request
5. 等待审查

---

## 性能相关

### ❓ 项目性能如何？

**A:** 查看各项目的性能基准：

| 项目 | 数据规模 | 性能指标 |
|------|----------|----------|
| Agent Task CLI | 1000 tasks | < 100ms |
| Local Embedding Memory | 10K chunks | ~100ms search |
| Agent Trust Network | 1000 agents | ~1s convergence |

### ❓ 如何优化性能？

**A:** 通用优化建议：
- 使用增量索引（embedding）
- 批量处理任务（task-cli）
- 缓存计算结果（trust-network）
- 异步执行（所有项目）

---

## 其他问题

### ❓ 工作区支持哪些操作系统？

**A:**
- ✅ Linux（主要支持）
- ✅ macOS
- ⚠️ Windows（部分功能可能需要 WSL）

### ❓ 需要哪些前置条件？

**A:**
- Node.js v18+
- Python 3.8+（用于 embedding 项目）
- Git
- 文本编辑器

### ❓ 如何保持项目更新？

**A:**
```bash
# 拉取最新代码
git pull

# 更新依赖
npm update  # Node.js 项目
pip install -U -r requirements.txt  # Python 项目
```

---

*最后更新: 2026-03-26*
*维护者: OpenClaw Workspace Team*
*反馈: 查看 CONTRIBUTING.md*
