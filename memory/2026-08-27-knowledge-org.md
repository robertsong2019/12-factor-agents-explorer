# 2026-08-27 02:00 — knowledge-organization-morning

## 输入扫描（过去 24h）
- memory/2026-08-26.md（全天 11 条 cron 记录：C514/C515 + 测试循环 + 文档晨轮 + essay + trending + #089 双触发 + mcpt 四连 + atc Round 63 + AI×Neuro 注意力）
- memory/2026-08-27-key-development-2.md（C518）+ key-development-3.md（C519）
- 项目仓 experiments.tsv 628 行（尾部 C515/C516/C517/C518/C519 链完整）
- workspace experiments.tsv 286 行（mcpt 四条 08-26 晚 + amg flake + blog 两条在案）

## 验证（count-from-truth）
- C517 f40da92 / C518 50c4406 / C519 86cbde3 + ledger commits（2622183/1986057）全在库 ✓
- amg 套件 10040 维持（C517/C518/C519 三轮自报一致，无测试数变化）
- atc e5be0b9 在库；本机 1.9GB 内存复跑全量被 OOM SIGKILL → 采信昨晈 22:07 会话 pre-commit 门控 1618/1618（环境限制如实记录，非跳过验证）
- **mcpt 口径谜团解开**：HEARTBEAT 旧记 38 系 08-20 会话（af05208）的 run.sh bash 测试口径，当时 package.json test 脚本指向未安装的 jest——npm test 从未跑通；08-26 C1 才真接线 node --test（0→33，实测 collect 34）。两口径不可比，**38 作废改 33**，全项目总计相应 −5
- memory_graph.py e04d222d `_search_cache` +24 行仍未提交（第 3 天）——C508 纪律维持，未触碰
- day counter：08-27=304（KO 日历链 08-22:299→08-27:304 连续无断）

## 本轮整合（MEMORY.md ≥1 处实质更新 ✓，共 8 处）
1. **Current Focus 08-27**：新增 C517-C519 arc 节——C517 full-500 官方刷新 **0.368→0.444（+38/−0 all-time high，C507-C516 七 cycle 债兑现，multi 0.233→0.459）**；C518 abs 预设失败门三连（E1 at-which/E2 other_until/E3 N-gallon，multi 64/133=0.481）；C519 proper-noun 误杀取证修复（NFKD fold 先于 tokenize / 学位媒体 stop / geo-sub，9→5 严格子集，预测 0.450）
2. **方法论沉淀**：shipped-gate census 第 4 次验证（这次轮到 C513 亲儿子）；Unicode 折叠时序（fold 必须先于 tokenize，否则 'Aragón'→'Arag' 截断毒已入 token）；tie 抖动要代码路径归因
3. **Active Theme**：C517-C519 链前插 + day 304
4. **表格**：amg API 列尾 +C517/C518/C519；atc 1599→1618（F244-F246）；四项目 12210→12229；全项目 ~21335→~21349（atc +19、mcpt 38→33 修正 −5）
5. **Next 重写**：full-500 刷新债标 ✅ 清偿；risk_coverage_report() 仍在队首（C517 名额被官方刷新占用）；新增 C518/C519 遗留项（短语级 restrictor / C519 解锁题转述失配 / entropy gate 误杀 / Shinjuku event-level）；LEX 词表标 C519 geo-sub 部分覆盖
6. **HEARTBEAT**：标题日期、atc/amg/计数五处、新活动节（11 条）、关键路径 #3 重写、上次检查条目

## 质量自检
- MEMORY 反映真实状态：✓（C517-C519 数字全部对照 commit message + tsv 双验；atc 1618 采信门控并如实标注 OOM 环境限制；mcpt 33 实测 node --test）
- HEARTBEAT 可操作：✓（Next 队列 11 项优先级明确；博客勘误 pending 项保留显式标注）
- 幂等：本轮为首次触发（02:00），无重复投递

## 小项备忘（不阻塞）
- AI×Neuro 编号漂移：08-25 与 08-26 两报均标 #22（topics 表防重但编号没跟上）——已在 HEARTBEAT 活动节标注，下报应 #23
- Tavily 432 配额错误连续第 4 天（AnySearch + web_fetch 降级路径稳定）
- cron 双触发今日 4 例（essay/deep-exploration×2/tool-dev），幂等三查全部生效零重复产出——模式稳定，无需升级规则
