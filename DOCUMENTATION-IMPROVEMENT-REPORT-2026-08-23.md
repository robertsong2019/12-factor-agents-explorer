# 文档完善报告 2026-08-23

## 主题：amg README 追平 Cycles 497-501 + agent-log F18 bench 入档 + skill-scaffolder Testing 章节

上轮报告（08-22，82074cf）停在 C496 与 agent-log 18 bats。期间夜间五个 amg cycle（C497-C501）、agent-log F18 bench harness、skill-scaffolder CLI e2e 套件（03:20 testing cron，992c88e）均无 README 入档。

### 1. projects/agent-memory-graph/README.md 追平 496→501

- **badge**: 9801 → 9872；**对比表 Tests 行**: 9801 → 9872；**测试段落**: 9801/496 cycle/299 天 → 9872/501 cycle/300 天
- **新增 API 参考章节「Neither-family ECM、偏好诚实弃权、官方刷新 0.316 与角色感知答案面 (Cycles 497-501)」**，5 个条目全部从源码 grep 行号 + experiments.tsv 指标撰写：
  - C497: ECM neither-family matcher（#082 五决策生产化；`ecm_form`:3990、门正则 :3741/:3744、`_ECM_VERBMAP`:3748；temporal 76→80=0.602、firstfam 24→28/30；oracle 四题零劫持；9801→9828）
  - C498: preference 诚实弃权 + shipped-gate census 纪律（`_PREF_RE`:3687 精确后缀集排除过去分词、`pref_form`:3698；answered 30→1/abstained 0→29；500 题普查 fire 29/30 pref + 0/470 其他——naive `recommend\w*` 词干普查劫持 14 道 ssa 题的根因入档；9847）
  - C499: full-500 官方刷新 exact 0.284→**0.316**（temporal 0.481→**0.602** 四连兑现、ssu −1 窗方差 C481 先例、abstain 0.032→0.086 诚实弃权入口径；C493-C498 六 cycle 债清偿）
  - C500: `item_total` 枚举金额聚合（`_cnt_item_total`:4862、族标签 :4463、分派 :5274、T1-T4 四层证据绑定；multi 0.128→**0.166** +5/−0 全中；9862）
  - C501: role-aware answer face——echo pathology 修复（`_user_fact_form`:3723 + `_answer_form_claimed`:3730 双守卫、"gate 顺序即正确性面" C482/C488、margin 0 floor 2；full-500 exact 0.326→**0.366** +20/−0；9872）

### 2. projects/agent-log/README.md — F18 bench harness 入档

- Testing 章节 bats 计数 18 → **22**（+4 bench smoke tests），新增 `bash test/bench.sh`（365 天合成语料、逐命令计时 + 阈值）与 `bats test/bench.test.bats` 两行运行方式。features.md F18 已由 dev session（3d34ae9）勾选，本轮只补 README。

### 3. tools/skill-scaffolder/README.md — 新增 Testing 章节

- `npm test`（29 tests）运行方式 + 双套件定位（库 API vs spawnSync 真进程 e2e）+ 2026-08-23 两个已修 bug 回归记录（validate 对无效 skill 误退 0；api 模板 kebab-case 生成带连字符的非法环境变量名）。tmpdir 密闭说明。

### 4. 验证与提交

- amg README：`9872` 4 处（badge/表格/测试段/C501 条目）；`9801 个测试`/`tests-9801`/表格旧值/`9519`/`496 个 cycle` 0 残留；新章节落位于 C496 条目与「## 许可」之间；四个新测试文件（test_ecm/pref_abstain/item_total/role_answer.py）实存
- agent-log：`18 tests` 0 残留；bench 两行在位
- commit（workspace 根仓，pathspec 定向提交，add+commit 同命令）

### 教训与延续

- 本轮延续上轮教训：动手前重 grep 当前态（果然 suite 已是 9872 而非台账记忆值），experiments.tsv + daily note 的指标列是权威数据源
- C501 的 exact 轨迹（0.316 官方 → C500 +5 → 0.326 → C501 +20 → **0.366**）在两个 commit message 间有隐式跳变，入档时用 base arm 复现（158+5=163）显式补链，避免读者困惑
- skill-scaffolder 属 tools/ 而非 projects/——testing cron 修的东西不止 projects 域，下轮文档巡检范围应含 tools/
