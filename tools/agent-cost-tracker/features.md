# agent-cost-tracker features.md

`act` CLI — AI 用量/成本追踪（token 计价、预算、导出）。存储：$HOME/.config/config.json（conf 包）。

## F1 记录与存储
- [x] log（-m/-p/-c/-s/--cost/-n），模型价自动算成本 F1
- [x] addLog/getLogs（period/model/session/before 过滤）F1

## F2 统计与导出
- [x] stats（-p/-m/-s/-g model|session|day/--format table|json）F1
- [x] trend（-d/--chart）F1
- [x] export（json/csv/markdown, -o 文件）F1

## F3 配置与预算
- [x] config list/add/remove/update（模型价格 per 1M）F1
- [x] budget set/check/reset（-w 警告阈值）F1

## F4 估算与清空（2026-08-21 补齐：命令声明了但模块从未存在）
- [x] estimate -m -p/-c（价格直算）F2
- [x] estimate -t（total 按 input:output=1:2 拆分）F2
- [x] estimate --words（×1.3 tokens/word）+ -r 次数放大 F2
- [x] estimate 未知模型 exit 1；纯读不写日志 F2
- [x] clear（-y 确认门；无 -y exit 1 保留数据）F2
- [x] clear --before <date>（删旧数据并报告条数）F2

## Bug 修复记录
- 2026-08-21: bin/act.js `fileURLToPath` 从 'path' 导入 → SyntaxError，CLI 入口完全无法启动（25 个 lib 测试全绿但 bin 从未被测过）→ 改从 'url' 导入
- 2026-08-21: clearLogs(before) 返回剩余条数而非删除条数 → 语义反转，改为返回 ids.length
- 2026-08-21: estimate/clear 在 CLI 声明但 lib/commands/ 下模块不存在（ERR_MODULE_NOT_FOUND）→ 补实现

## 测试
- test/storage.test.cjs + export.test.cjs — lib 单元（原有）
- test/cli.test.cjs — CLI e2e，hermetic（HOME 覆盖 + NO_COLOR + ANSI 剥离），`npm test`
