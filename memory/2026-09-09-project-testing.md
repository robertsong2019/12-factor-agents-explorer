# 2026-09-09

## 03:00 project-testing-morning — mission-control 首测覆盖 ✅ (1 cycle, keep, 2 red-verified)

- 幂等三查过：tsv 末行=09-08 03:30 agent-log；昨晚 amg 循环 commit 止于 01:55；无 project-testing 今日条目
- 基线扫描：monorepo+lab 各项目最后触碰排序 → mission-control 04-16（5 个月）**且 0 测试**（151 行单体脚本，全部顶层执行带副作用）；agent-task-cli 05-17（jest 慢，继续跳过）；agent-context-store 07-15（own-repo，次轮候选）
- **选型 mission-control**：抽取 parse_cron_jobs/ago/parse_meminfo 三个纯函数 + main() 门卫，行为保持验证=重构前后全量输出 diff（仅时间漂移字段不同，cronJobs 逐条一致）
- **RED-FIRST ×2**（均先对 git HEAD 旧代码实证再修）：
  1. `row_re` 要求 name 后跟字面 `cron ` → `--every`/`--at` 型任务（`openclaw cron add --help` 证实存在）整行静默丢弃，dashboard 计数偏低——潜伏 bug（今日 15 个 job 恰好全是 cron 型，无活体实例）；修复 `(?:cron|every|at)`
  2. `ago()` 未来时间戳 → dashboard 显示 "-5s ago"；修复 clamp max(0,d)
- 真 6-col 粘连行（`Asia/Shangha... in 2h`）被真实数据命中，characterization 全覆盖；KNOWN_NAMES 映射、省略号剥离、@tz 剥离均钉住
- 坑：手造 every 行全单空格不符合真实表格列对齐（2+ 空格 split → 1 列 → 因另一原因被跳过），fixture 改真实对齐 + 补 every+tz 6-col 变体
- 24/24 ×2 绿 0.04s；own-repo commit **acb371b 已 push**；data/ 留给 06:00 dashboard cron
- 下轮候选：agent-context-store（07-15 own-repo）、agent-task-cli（05-17，留足时间预算再啃 jest）
