# agent-log 教程

> 从零学会用 agent-log 搜索、浏览和总结你的 OpenClaw 日志

## 这是什么？

`agent-log` 是一个零依赖的 Bash 脚本，帮你从堆积如山的 OpenClaw 日志中快速找到想要的信息。不需要数据库，不需要索引——就是对文本文件做搜索和汇总。

## 你会学到什么

1. 搜索历史对话中的关键词（含正则、日期范围、计数排名）
2. 查看某天的活动记录
3. 获取活动摘要和趋势图
4. 浏览、定位和跟踪 session 记录
5. 用 JSON 输出把结果接进脚本
6. 安全地清理过期日志（以及为什么先 dry-run）

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

`agent-log` 会搜索三处（`sessions` 目录在 workspace 之外）：
1. `~/.openclaw/workspace/memory/` — 每日笔记（`YYYY-MM-DD.md`）
2. `~/.openclaw/workspace/` 根目录一层 — MEMORY.md、README.md 等
3. `~/.openclaw/sessions/` — session 记录

### 进阶搜索

`search` 有一组实用的修饰旗标：

```bash
# 正则搜索（-r / --regex，底层 grep -E）
agent-log search -r "cron.*(essay|briefing)"

# 只搜某个日期范围（按文件名日期过滤，对 memory/ 生效）
agent-log search "docker" --from 2026-08-01 --to 2026-08-28

# 计数排名：每个文件命中多少次，从多到少排序
agent-log search "docker" --count

# 把完整结果导出到文件（含命中行和上下文）
agent-log search "docker" -o results.txt

# JSON 输出，接 jq 或脚本
agent-log search "docker" -j | jq '.results[] | select(.matches > 3)'
```

`--count` 的输出长这样（F19 特性）：

```
Match counts (text): docker
(412 files scanned)

   37  .openclaw/workspace/memory/2026-08-20.md
   12  .openclaw/workspace/MEMORY.md
    3  .openclaw/workspace/memory/2026-07-02.md
```

一眼看出哪个话题在哪些天聊得最多，比逐页翻搜索结果快得多。

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

适合快速评估工作区的健康状况。加 `--md` 输出 Markdown 表格，`-j` 输出 JSON。

## 第六步：活动趋势

`summary` 给你数字，`trend` 给你形状——用 sparkline 字符画出每天的活跃度：

```bash
agent-log trend          # 默认最近 14 天
agent-log trend 30       # 最近 30 天
agent-log trend -j       # JSON（画图脚本友好）
```

输出示例：

```
📈 Activity trend (last 14 days)
  08/16  142  ██████▌
  08/17   87  ████
  08/18  203  █████████▎
  ...

  Max: 203 lines | Scale: ▁(0) → █(203)
```

哪些天是高峰、哪些天空窗，一张图看清。

## 第七步：session 工具箱

这组命令围绕 `~/.openclaw/sessions/` 下的会话记录：

```bash
# 列出最近 30 个 session（行数、大小、修改时间）
agent-log sessions

# 看某个 session 的完整内容（支持文件名片段匹配）
agent-log session 2026-08-28

# 按内容/文件名找 session，还能限定修改日期范围
agent-log find "prompt-mgr"
agent-log find "prompt-mgr" -a 2026-08-25 -b 2026-08-28

# 直接对 session 日志 grep（带行号，最多 50 条）
agent-log grep "rename_key"

# 盯着最新的 session 看（类似 tail -f，Agent 干活时实时观察）
agent-log tail -f
```

`sessions`、`session`、`find` 都支持 `-j` JSON 输出。`tail -f` 特别的适合开另一个终端窗口，看 agent 正在做什么。

## 第八步：清理旧日志（唯一的写命令）

⚠️ 这是全工具唯一会删除文件的命令，其余命令全部只读。

```bash
# 先预览！只列出会删什么，不动手
agent-log clean --dry-run

# 删除零字节文件
agent-log clean

# 额外删除 90 天前的日志（按文件名日期判断）
agent-log clean --age 90
```

清理逻辑很保守：空文件要求零字节（不是零行——末行无换行符的文件 `wc -l` 会误报 0，这是个修过的 bug）；`--age` 只匹配 `YYYY-MM-DD` 命名的文件。但保守归保守，养成先 `--dry-run` 的习惯。

## 用 JSON 输出接脚本

大部分报表命令支持 `-j/--json`，管道里颜色自动关闭（设了 `NO_COLOR` 也一样），输出干净可解析：

```bash
# 命中超过 10 次的文件
agent-log search "memory" -j --count | jq -r '.results[] | select(.matches > 10) | .file'

# 最近 30 天活跃度折线（喂给你喜欢的画图库）
agent-log trend 30 -j

# 找出本周改过的 session
agent-log find -a 2026-08-22 -j | jq '.count'
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENCLAW_WORKSPACE` | `~/.openclaw/workspace` | 工作区根目录（memory/ 从这里派生） |

注意：session 日志目录固定为 `~/.openclaw/sessions`，**不**跟随 `OPENCLAW_WORKSPACE`。

如果你的工作区在别的地方：

```bash
OPENCLAW_WORKSPACE=/path/to/workspace agent-log today
```

## 自定义扩展

`agent-log` 是一个约 690 行的 Bash 脚本，结构清晰，很容易扩展。

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
A: 用 `--count` 先看哪个文件命中最多，再 `agent-log date YYYY-MM-DD` 定位到某天，或用 `--from/--to` 限定日期范围。

**Q: 支持正则表达式吗？**
A: 支持。`search -r` 启用扩展正则（底层 `grep -E`）；`grep` 命令也可直接用基础正则。

**Q: 会修改我的日志吗？**
A: 默认不会。所有查询命令都是纯只读，唯一的例外是 `clean`（删空文件/旧日志）——先跑 `agent-log clean --dry-run` 预览。

**Q: 输出重定向到文件后颜色码乱掉了？**
A: 不会。检测到 stdout 不是终端（或设置了 `NO_COLOR`）时颜色自动关闭，管道和重定向输出都是干净的。

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
