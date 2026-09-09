# 2026-09-10

## 项目测试循环（03:00 cron，context-forge，15min 预算内）

- 基线扫描：agent-task-cli 1800/1800、agent-memory-service 724/724、**context-forge 1511 tests（最长未循环，08-30 起 11 天）** → 选定 context-forge。
- context-forge run1 1510/1511 → rerun 绿 = node --test deserialize flake（TOOLS.md 规则第 4 次应验，rerun-2x 直接判定）。
- 覆盖率（--experimental-test-coverage）：96.74% 行 / 88.19% 分支。最大缺口 main() 2576-2691（CLI 入口，import 不可测，留给未来 spawn 式测试）；实际选了 5 个分析器零覆盖分支。
- **RED-FIRST 真 bug**：`analyzeGuardClauses` guard-opportunity 分支 (10223-10238) 是**死分支**——
  - style A（`}` 换行 `else {`，最常见）：`afterIf = lines[ifEnd]` 读到的是 `}` 行自身，`/^else/` 永不匹配；
  - style B（`} else {` 同行）：else 的 `{` 抵消 `}`，ifBraceDepth 永不归 0 → ifEnd 落到函数尾。
  - 真实代码不可能触发（只有构造花括号进字符串的病态对齐才行）。**dead-defensive-code 家族第 3 例**。
  - 修复：ifEnd 后向前扫 ≤3 行找 else（style A 外科手术式修复；style B 记为已知限制不动，需 brace-parity 重写才根治）。
- +10 tests `f84-analyzer-branches.test.mjs`（5 分支各 pos/neg）。**1555/1555 ×2 green** ~23s。
- 教训：先看现有 f66/f56 测试确认返回形状再写断言——async 是 `files[].issues`+`totalUnhandledRejections`、smells 是 `summary.tooManyParams`+`files[].issues`，形状猜错白改 4 处。
- 工作区发现外来 untracked `test/f13-template.test.mjs`——非我所建，按 08-28 规则不 add 不动它。
- 提交：monorepo **88d6701**（amend 后），experiments.tsv 已记 20260910_0330 行。
- 成功标准达成：测试数 1511→1555（+10 实增，flake 少报修正后口径）✅
