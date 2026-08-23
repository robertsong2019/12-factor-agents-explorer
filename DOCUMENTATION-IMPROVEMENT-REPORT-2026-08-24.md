# 文档完善报告 2026-08-24

## 主题：amg README 追平 Cycles 503-506v + 套件计数 9928 校准 + atc README 计数修复

上轮报告（08-23）停在 C501/9872。期间（08-23 晚 ~08-24 凌晨）四轮生产化（C503 enum_count、C505 duration-family、C506 嵌入 side-channel、C506v full-500 刷新 0.368）、atc Round 62（F241-F243）、以及 398adf8（session-archiver CLI 修复 + 测试）均无 README 入档。

### 1. projects/agent-memory-graph/README.md 追平 501→506v

- **badge / 对比表 / 测试段**: 9872 → **9928**；cycles 501 → **505**；零回滚 300 → **301 天**
  - 计数校准插曲：初稿按 02:00 KO 台账写 9914，pytest collect 实测 **9928**（+14，来自 03:30 的 398adf8 顺带变更）——再次验证"动手前重 grep 当前态"纪律：台账记忆值可能落后于最新提交，collect 实测才是权威
- **新增 API 参考章节「Counting 第 5 形态、duration-family 四机制、嵌入 side-channel 与官方刷新 0.368 (Cycles 503-506v)」**，4 条目全部从源码行号 + experiments.tsv 指标撰写：
  - C503: `_cnt_enum_count`:6102 枚举签名计数（#084 v5.2，counting 第 5 形态；turn 级候选/子句级签名/尺寸签名；`_ENUM_MY_INVENTORY`:6149 所有权门防 Billie Eilish 品牌污染、`_ENUM_TWINS_APPOS`:6145、排他谓词；oracle parity 4/4；133 切片 0.180→0.203 +3/−0；9888）
  - C505: duration-family M1-M4（`_dur_m1`:4916 franchise 去重 / `_cnt_freq_days`:5305 课程语境锚 / `_dur_m3`:4965 计划-事实墙 / `_dur_m4`:5039 日期 join + 题侧产品守卫；`_cnt_duration_family`:5089 族分发；oracle 7/7 含双控制题；0.203→0.233 +4/−0 链条累计 +7/−0；9899）
  - C506: 嵌入 side-channel（`chunk_session_text`:1782 150w×6 / `SidechannelEngine`:1798 import-probe 双档 / `session_embedding_scores`:1875 chunk-max 纯 python / `sidechannel_form`:1905 form-gated switch——embed/hybrid/None 三态，RRF 融合被 #083 A/B 否决；`--sidechannel` CLI:6507；词法零依赖默认不动；9914）
  - C506v: full-500 官方刷新 exact 0.316→**0.368**（multi 0.128→0.233 三连弧 / ssu 0.329→0.457 / 零类目回归；零代码改动纯刷新；POST 臂为下一里程碑）
- 章节引言注明 C502 zero-loss revert 不计入 cycle 链，读者不会疑惑编号跳跃
- C501 条目末尾的历史值 9872 保留（cycle 时点真值）

### 2. projects/agent-task-cli/README.md — 计数过期修复

- 测试覆盖行：1503 tests / 226 features → **1599 tests / 202 features**
- 验证：全量 jest 两跑——首跑 1598/1599（1 失败），复跑 + `--onlyFailures` 全绿，判定 flaky（时基类）；features.md 勾选 `- [x]` 实数 202、无未勾选项。旧值 226 与勾选实数 202 的差疑为历史重构遗留，以实数为准
- Round 62（F241 `Storage.updateWhere` / F242 `PriorityQueue.priorities` / F243 `enqueueAll`，532fa78）的 features.md 勾选已由 dev 会话完成，本轮只补 README 计数

### 3. 验证与提交

- amg README：`9928` 3 处（badge/表格/测试段）；`9872` 仅存 C501 历史条目 1 处；新章节落位 C501 条目与「## 许可」之间；pytest collect 实测 9928 ✓
- atc README：jest 1599/1599 ✓、features 202 ✓
- 提交：workspace 根仓（报告 + amg README，pathspec 定向）；agent-task-cli 子仓（README，独立 .git）

### 教训与延续

- **套件计数三源合一**: experiments.tsv（cycle 时点）→ KO 日志（02:00 快照）→ pytest collect（当前实态），README badge 必须用最后一源。本轮 9914→9928 的 14 题差来自文档窗口期内的新提交（398adf8 03:30），台账不可能预知
- 398adf8 把 session-archiver（JS）与 amg_bench_quality.py（python）改动打进同一 commit——跨语言混合提交让"哪个 commit 加了哪些测试"的追溯变难，报告里以 collect 实测兜底
- 下轮候选：POST --sidechannel 臂 A/B 结果入档（若已出）；398adf8 的 session-archiver 修复是否值得 README 一行；tools/ 域巡检（上轮教训延续）
