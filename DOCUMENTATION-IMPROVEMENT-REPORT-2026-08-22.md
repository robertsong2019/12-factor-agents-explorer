# 文档完善报告 2026-08-22

## 主题：amg README 追平 Cycle 490-496 + agent-log 测试与四 bugfix 入档

上轮报告停在 08-18（Cycles 458-467）。期间 7d61ded/08e63d5 两个日间 commit 已覆盖 C468-473 与 C456-489 教程，但 README 计数停在 9768、测试段落停在 9519/467 cycle（08e63d5 的 drift fix 漏掉了这段），C490-C496 七轮完全无文档。另：今日 03:05 测试循环给 agent-log 落了 18/18 bats + 4 个真 bugfix（088c51a），README/features 均未入档。

### 1. projects/agent-memory-graph/README.md 追平 490→496

- **badge**: 9768 → 9801；**对比表 Tests 行**: 9768 → 9801；**测试段落**: 9519/467 cycle/296 天 → 9801/496 cycle/299 天（修复 08e63d5 漏改的陈旧段）
- **新增 API 参考章节「Multi-session 锚定纪律、官方基准刷新与 pairwise 收尾 (Cycles 490-496)」**，7 个条目全部从源码 grep 签名/行号后撰写：
  - C490: `_cnt_question_anchors` 单位词锄除（`_CNT_STOP_Q`/`_CNT_GENERIC_HEADS`，泛化头词全锚集移除超出原型加固）— multi_session 9→12/133
  - C491: `_cnt_total_sum` 金额锚定纪律移植（锚点门/会话传播/价格区间跳过三器官）— 12→16/133，四个具名总额全精确
  - C492: full-500 官方刷新 exact 0.204→**0.284**，needs_verification 债清偿
  - C493: temporal_arith first-kind 退役（删除型 cycle 双验证 12/30 零翻转，C479 先例第二案）
  - C494: `_PW_EVENTIVE_RE` 进行时 gerund / `_PW_SINCE_RE` 序数后缀 / 粗相对时长日历锚 + `_pw_scan_anchor` 向后窗口
  - C495: 从句粒度 + 跨行锚点对（firstfam 16→23、temporal 68→75）
  - C496: `_pw` F6 anaphora 购买汇报 join（四重判别式防毒，套件 9801）
- 章节头部指针链至 TUTORIAL-TEMPORAL-QA.md（C474-489 归教程管），保持 README API 链与教程的分工不重叠

### 2. projects/agent-log — 测试套件与四 bugfix 入档

- **README.md 新增「Testing」章节**：bats 运行方式（`bats test/commands.bats test/bugfixes.test.bats`，HOME 覆盖全密闭）、两套测试定位，以及四个已修真 bug 的回归记录——help/usage DOA（sed 抓不存在的 `## Usage` 段）、clean 数据丢失（无结尾换行被当空文件删）、find -j 多结果 JSON 无逗号、JSON 注入（`esc_json` 转义）
- **features.md F16 勾选**：Bats 单测 ✅ 2026-08-22（18 bats 含 10 回归）

### 3. 验证与提交

- amg README：`9801` 4 处（badge/表格/测试段/C496 条目）；`9768`/`9519 个测试`/`467 个 cycle` 0 残留；新章节落位于旧 473 节与「## 许可」之间
- 源码锚点：`_cnt_question_anchors` amg_bench_quality.py:3901、`_PW_SINCE_RE`:3217、`_PW_EVENTIVE_RE`:3326（C494/C495 注释在位）、`_cnt_total_sum`:4191（C491 锚定纪律注释在位）、C496 F6 注释 :3399/:3510
- commit（workspace 根仓，pathspec 定向提交）

### 教训与延续

- 08e63d5 证明日间 session 也会改 README——文档 cron 每 5 分钟动手前必须重 grep 当前态（本轮测试段落 9519 陈旧即为此因），不能沿用上轮报告的"最新已知值"
- agent-log 的「Read-only — never modifies your logs」设计原则与 `clean` 命令的存在本就矛盾（clean 删除空文件）；本轮只在 Testing 章节记录 clean 安全修复，原则句留待下轮与其作者会商
