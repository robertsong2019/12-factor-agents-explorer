# agent-log 教程

> 从零学会用 agent-log 搜索、浏览和总结你的 OpenClaw 日志

## 这是什么？

`agent-log` 是一个零依赖的 Bash 脚本，帮你从堆积如山的 OpenClaw 日志中快速找到想要的信息。不需要数据库，不需要索引——就是对文本文件做搜索和汇总。

## 你会学到什么

1. 搜索历史对话中的关键词
2. 查看某天的活动记录
3. 获取一段时间内的活动摘要
4. 查看工作区统计信息
5. 自定义和扩展 agent-log

---

## 前置条件

- Bash（macOS / Linux 自带）
- OpenClaw 工作区（默认 `~/.openclaw/workspace`）

## 安装

```bash
cd ~/.openclaw/workspace/projects/agent-log
chmod +x agent-log.sh

# 可选：创建全局符号链接
ln -s "$(pwd)/agent-log.sh" /usr/local/bin/agent-log
```

---

## 第一步：看看今天做了什么

最简单的用法——回顾今天的活动：

```bash
agent-log today
```

输出会显示：
- `memory/YYYY-MM-DD.md` 的完整内容（今天的日志）
- 今天有改动的 session 文件列表

如果今天没有日志，你会看到 `(no daily notes for ...)`，说明还没产生记录。

## 第二步：查看特定日期

```bash
agent-log date 2026-04-15
```

跟 `today` 一样的输出，但指定了日期。适合回顾过去某天的工作。

## 第三步：搜索关键词

这是最核心的功能——跨所有日志文件搜索：

```bash
# 搜索所有提到 "docker" 的地方
agent-log search "docker"

# 搜索人名、项目名、技术术语都行
agent-log search "memory-service"
agent-log search "张三"
```

输出包含：
- 匹配的文件路径
- 匹配行及上下文（带颜色高亮）
- 每个文件最多显示 20 行匹配

### 搜索范围

`agent-log` 会搜索三个目录：
1. `~/.openclaw/workspace/memory/` — 每日笔记（`YYYY-MM-DD.md`）
2. `~/.openclaw/workspace/` 根目录 — MEMORY.md、README 等
3. `~/.openclaw/sessions/` — session 记录

## 第四步：活动摘要

想知道最近一周有多活跃？

```bash
# 默认最近 7 天
agent-log summary

# 最近 30 天
agent-log summary 30
```

输出示例：
```
📊 Activity summary (last 7 days)

  2026-04-18 Fri  142 lines
  2026-04-17 Thu   87 lines
  2026-04-16 Wed  203 lines
  ...

  Total: 5 files, 632 lines
  MEMORY.md: 523 lines
```

这让你一眼看到哪些天工作量大、哪些天没有记录。

## 第五步：工作区统计

```bash
agent-log stats
```

显示：
- memory 文件数量
- session 文件数量
- 工作区总大小
- 最近的日志文件

适合快速评估工作区的健康状况。

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENCLAW_WORKSPACE` | `~/.openclaw/workspace` | 工作区根目录 |

如果你的工作区在别的地方：

```bash
OPENCLAW_WORKSPACE=/path/to/workspace agent-log today
```

## 自定义扩展

`agent-log` 是一个 168 行的 Bash 脚本，结构清晰，很容易扩展。

### 添加新命令

打开 `agent-log.sh`，找到 `# ── Commands ──` 部分，添加一个新函数：

```bash
cmd_weekly() {
  echo "📅 本周摘要"
  # 你的逻辑
}
```

然后在底部的 `case` 语句中注册：

```bash
weekly) cmd_weekly ;;
```

### 常见扩展方向

- **按项目过滤**：只显示某个项目相关的日志
- **导出功能**：将搜索结果导出为 Markdown 报告
- **时间线视图**：以时间线格式展示跨天的事件
- **与 ripgrep 集成**：如果系统有 `rg`，替代 `grep` 获得更快速度

---

## 常见问题

**Q: 搜索结果太多怎么办？**
A: 缩小关键词范围，或者先 `agent-log date YYYY-MM-DD` 定位到某天，再到对应文件里手动搜索。

**Q: 支持正则表达式吗？**
A: 底层用的是 `grep -i`，支持基本的正则。复杂的可以用 `grep -E`（扩展正则）。

**Q: 会修改我的日志吗？**
A: 不会。`agent-log` 是纯只读工具，不会写入任何文件。

**Q: macOS 和 Linux 都能用吗？**
A: 是的。日期计算部分同时兼容 GNU date（Linux）和 BSD date（macOS）。

---

## 与其他工具的关系

```
OpenClaw 生态中的位置：

  OpenClaw Agent ──写入──→ memory/*.md
       │                      ↑
       │                  agent-log 读取
       │                      │
       └──写入──→ sessions/*.md
                              ↑
                          agent-log 读取
```

`agent-log` 是日志的消费端——Agent 写日志，你用 agent-log 读日志。它不参与 Agent 的运行，只是一个方便的查询工具。
