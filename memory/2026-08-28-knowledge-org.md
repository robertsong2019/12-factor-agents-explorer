# 2026-08-28 Knowledge Organization (02:00, autoresearch 方法论)

**幂等三查**：①今日无 knowledge-org 产物（昨日 02:10 是 08-27 轮）✓ ②工作树 MEMORY.md 有未提交 +6 行（昨晚 #090 会话遗留，合法 pending，保留并纳入本轮提交）✓ ③⚠️ 本 cron 本身是双注册之一（`@ Asia/Shanghai` + `(exact)` 两份同时 <1m 前触发，均 running）——并发 twin 会话风险已知，提交前重查 git log

## 过去 24h 素材盘点（不是流水账，只列整合输入）

- **amg C520-C523 四连全 keep**：C520 risk_coverage_report（oracle Taylor 近似真 bug）/ C521 enum_count event 专名 / C522 bigram census RECORD-NEGATIVE + 官方刷新 0.454 / C523 quant_rerank **0.476（+11/−0，近期最大单 cycle，arc 2.33×）**。suite 10069 绿 @5aae7e0
- **工具线**：skill-doctor 64→77 三连（家族第 6 例遗传性修复）/ atc Round 64（F247-F249，1636）/ ptm 20→29（3 真 bug，570c05a）
- **Research #090**：answer-face 等价判分（26/26；判分↔作答镜像律）——其 answer-face 方向已由 C523 首兑，judge_semantic 编号顺延
- **博客 ×3**：925b750 脚手架遗传病 / acebed2 Aragón 误杀 / c8f08cf answer equivalence
- **文档**：ptm README 追平 + amg README C517-C519 + TUTORIAL-ABSTENTION 扩充（bb8ab99）
- **基建课**：/tmp fixture 蒸发→/root/lme_data/；raw LME 裸 turn-list 须 --mode eval；amg 真账本=项目仓 tsv（root 误写已 revert）；exec preflight 拒 heredoc+&& 组合

## 本轮落盘

### MEMORY.md（8+1 处编辑，均有实质内容）
1. Current Focus 日期 → 08-28，新增 **C520-C523 arc 节**（含方法论沉淀：how-many 残余家族地图 / 负结果产出门槛 / 收债刷新）
2. Research #090 节 Next 更新（C520 编号被占用，judge_semantic 顺延；C523 首兑注记）
3. 项目测试总量快照：amg 10040→**10069**（API 列表追加 C520/C521/C523）、atc 1618→**1636**（F247-F249）、四项目 12229→**12276**、全项目 ~21349→**~21409**（skill-doctor 77 入账）
4. **insight #256**：基准元数据进机制特征=标签泄漏（C522 _abs 4 win 宁弃）；分离失败本身是可记录发现
5. **insight #257**：收债刷新=切片链可预测性的低成本终局（C506v/C517/C522 三次验证）

### HEARTBEAT.md（65KB → 18.5KB，可操作性恢复）
- 标题/计数六处刷新；新活动节（08-27 白天 ~ 08-28 凌晨，含 cron 双触发 3 例+ 记录）
- **裁剪**：近期活动删 08-24 及更早 9 节；上次检查删 08-25 及更早 12 条（保留 08-28/08-27/08-26 三轮）
- 关键路径 #3 重写：**latest-number-wins 上位 C524 首选**（40+ 题，风险高一档）；judge_semantic A/B / 非数量 echo ~200 / ssu 取证顺位
- 已知问题更新：MEMORY 250KB 增长预警（下轮候选：insights 早段迁 archive）、账本拓扑混用 monitoring、cron 重复注册待罗嵩拍板、Tavily 第 5 天

### experiments.tsv 趋势检查
- **amg（项目仓）**：C519→C523 五行连 keep + 1 RECORD-NEGATIVE，官方分 0.444→0.448→0.454→0.476——**热 streak，切片 A/B 预测全部兑现**
- **atc**：Round 64（44 行），1636 tests，零回滚
- **lab 诸 tsv 多数停滞**（agent-context-store 止于 07-24 / observability 08-17 / langgraph-bridge 06-26）——项目休眠如实反映，非账本缺失
- **拓扑混用**：skill-doctor C1-C3 行落在 root tsv，tools/ 本表止于 08-16 且末行 note 有内嵌重复——append-only 不改史，已入已知问题 monitoring

## 质量自检
- MEMORY.md 反映真实状态？✓ 分数弧线/测试计数均与 git log + tsv 对账（10069@5aae7e0、0.476、1636）
- HEARTBEAT.md 可操作？✓ 三轮检查日志 + 单一队首目标 + 人工阻塞项显式
- 成功标准（≥1 处有意义更新）：远超——arc 节 + 2 insights + 5 处计数 + 队列重排
