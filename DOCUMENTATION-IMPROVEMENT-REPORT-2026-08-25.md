# 文档完善报告 2026-08-25

## 主题：amg README 追平 Cycles 507-511 + POST 臂 0.414 收口 + 套件计数 9963 校准

上轮报告（08-24）停在 C506v/9928。期间（08-24 白天 ~08-25 凌晨）五连（C507/C508/C509/C510 负结果/C511）、full-500 POST 臂收口、KO 08-25（1b130ea）、以及 b52e6ba（npm scripts DOA 修复 +5 守卫）均无 README 入档。

### 1. projects/agent-memory-graph/README.md 追平 505→511

- **badge / 对比表 / 测试段**: 9928 → **9963**；cycles 505 → **511**；零回滚 301 → **302 天**
  - 计数校准：KO 08-25（02:19）台账值 9958，但 03:10 的 b52e6ba 又 +5 结构守卫 → pytest collect 实测 **9963**。三源合一纪律（experiments.tsv → KO 台账 → collect 实态）再次生效：README badge 必须用最后一源
- **C506v 段尾收口**：上轮留下的 "POST `--sidechannel` 臂 A/B 为下一里程碑" → 已完成 **207/500=0.414 全库新高**（指向新节）——上轮报告的"下轮候选①"兑现
- **新增 API 参考章节「Total-number v2、where-form、delta-family 两锚点聚合、inventory_count 第 10 形态与 POST 臂 0.414 (Cycles 507-511)」**，7 条目全部从源码行号 + experiments.tsv 撰写：
  - C507: `_cnt_number_total`:5935 v2 七项升级（NP cap 60→90 / -es/-ies / 频率过滤 / 后置编号 own_re:5948+"of" 祈使句守卫 / 序数 / 实体拆分 max 求和 / sibling→species / 千分位保护）；multi 0.233→0.271 (+5/−0)
  - C508: `where_form`:2145 严格 start-with-where 门 + `_where_loc_candidates`:2161 大小写敏感双分支 + 仅扫 retrieved 会话（C472 教训不迁移）；where 4→6 (+2/−0)；取证坑两条入档（PPR set 迭代序检索方差遗留未修 / 10×50 分块绕 277MB 内存墙）
  - C509: `delta_form`:6824 STRICT 题面算子门 + 引擎 :6646（any-of 锚点 / user-role 优先 / strict-majority 跨侧排除 / 子句局部性）+ dispatcher :1021 counting 前执行 + `--no-delta`:7390 隔离开关；oracle 16/21 fired 精度 100%；multi 0.271→0.391 (+16/−0)
  - C510: RECORD-NEGATIVE 专条目——kupdate #087 被 virtual-flip census 三重否证（判分鸿沟/形态不可分/净 −7 劫持），**census 升格 answer-face 生产化前置关卡（insight #254）**；不计入 cycle 链，与 C502 同理在章节引言注明
  - C511: `_cnt_inventory_count`:6510 第 10 counting form（{kit,instrument,property} 白名单 + `_inv_dedup`:6505 最大签名包含去重 + 四坑入档）；multi 0.391→0.414 (+3/−0)
  - POST 臂: C508 树 0.382 → 207/500=0.414（1135s；multi 36→52，其余五类逐位不变 losses=0——#083 嵌入通道全量兑现）
  - 工具线注记: b52e6ba npm scripts DOA（`npm test --` 自递归 core dump）→ pytest 接线 + `test_package_json_scripts.py` 5 守卫（三案同类 bug 类）+ `scripts/find_untested.py`；套件 9958→9963

### 2. projects/agent-task-cli/README.md — 无需变更

- git log 确认 08-24 04:25（上轮 docs 提交）后无任何 dev 提交；1599 tests / 202 features 维持有效。上轮候选"session-archiver 修复值否 README 一行"：session-archiver 不在 atc README 射程内，其 65→81 已在 amg 工作区 MEMORY.md 台账入档，本轮不重复

### 3. 验证与提交

- amg README：`9963` 4 处（badge/表格/测试段/工具线注记）；`9928` 仅存 C509 历史条目 1 处；新章节落位 C506v 条目与「## 许可」之间；pytest collect 实测 9963 ✓；全部行号锚点经 grep 复核 ✓
- 提交：workspace 根仓（报告 + amg README，pathspec 定向）——amg 无独立 .git（TOOLS.md 拓扑注记核实：status 显示 ../../ 路径即根仓视角）

### 教训与延续

- **计数窗口期又踩同款**：KO 台账（02:19 快照）与最新提交（03:10 b52e6ba）差 5 题——KO 集成与文档 cron 之间任何提交都会让台账过期，collect 实测是唯一权威，与上轮 9914→9928 模式完全一致
- **负结果的文档位**：C510 作为首个 RECORD-NEGATIVE 入档 README（此前 C502 revert 只在章节引言一笔带过）——给独立 #### 条目但明确"不计入 cycle 链"，读者不会误把 511 数成 510
- 下轮候选：①写时嵌入摊销（FastAppendQueue 钩子）若落地则 README 架构段需补；②full-500 官方刷新债清偿（C507-C511 四 cycle 累积）后 badge 段 exact 读数待更新；③tools/ 域巡检（连续第三轮挂起——工具线 08-24 已有 ai-dev-tools/amk 两案 README 无计数声明，可低优先确认）
