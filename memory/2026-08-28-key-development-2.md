# 2026-08-28 key-development-2 (C522): bigram census RECORD-NEGATIVE + 官方 full-500 刷新 0.454

## 接力点

C518 官方 0.448（224/500）之后，C519（proper-noun neg_exist 修复，预测 +1）、
C520（risk_coverage_report，无 eval 影响）、C521（enum_count event signature，
切片 +1）三个 cycle 的收益均停留在"预测口径"。本轮两件事：
①用全量 census 关闭 C518 Next 队列的"短语级 restrictor"方向（负结果）；
②官方刷新一次收账（C506v/C517 收债先例）。

## Part 1：bigram census — RECORD-NEGATIVE（无 port，零风险）

C518 队列项：table tennis / vintage films / Italian restaurants 的
"bigram 不在、confusable sibling 在"陷阱。设计 v1 签名：**相邻内容
bigram 在 haystack 中缺席（含形态容差），但两个 token 各自都在**
——sibling 陷阱的结构化表达。census /tmp/c522/census_v1.py：

- 48 fires = **4 win + 12+ hijack + 其余 neutral/noop**
- 4 win 恰为队列目标：f685340e_abs（table tennis）、15745da0_abs
  （vintage films）、88432d0a_abs（egg tarts！C518 判"不可捕"实为
  可捕——Pop-Tarts 恰是 sibling）、2133c1b5_abs（Shinjuku，顺带
  拿到 C513 遗留案的 census 证据）
- 但 hijack 与 win 在所有可计算特征上**不可分**：
  - sibling 形态相同（head-alone under same predicate）：
    [table|tennis] win ≅ [current|job]/[lunch|meals]/[trip|destinations] hijack
  - 所有格跨界排除只杀 6 个 hijack，剩 12+ 无原则可杀
  - 问句形式不可分：[current|apartment] win ≅ [current|job] hijack
- **诚实红线**：4 win 全部是 `_abs` 变体，用 qid 后缀过滤 = 标签泄漏，
  部署态不可得，坚决不用
- 结论：C516 当年 pre-implementation 枪毙泛化 bigram 路线是对的，
  现在有全量 census 证据了；"egg tarts 不可捕"注记同时证伪
  （可捕，只是与 hijack 不可分）

## Part 2：官方 full-500 刷新 @61525fa — 0.448 → **0.454**（227/500，+3/−0）

- flips 全部对账：**2318644b**（C519 Hawaii delta_agg）、
  **gpt4_a56e767c**（C521 festival enum_count）、**86f00804**
  （C518 的 tie-jitter 噪声受害者自行翻回）——两条预测增益如数兑现
- multi_session 64→66/133（0.481→0.496），ssu 35→36/70，
  abstention 11.8%→11.0%
- 累计弧线：C481 0.204 → C492 0.284 → C499 0.316 → C506v 0.368
  → C517 0.444 → C518 0.448 → **C522 0.454**（2.23×）
- suite 10057 + 5 subtests 全绿 @61525fa（242s——C518 同 suite 跑了
  1154s，swap 清掉后快 5 倍）
- exact 判分与 lineage 同口径（dual 的 LLM 臂省略：500 题 ollama
  叠加在本机纯风险；dual 模式下 accuracy_exact == exact 模式
  overall_accuracy，判分语义一致）

## 基建事件：数据集形状漂移（重要，下一轮必读）

C521 会话重下的 raw LongMemEval（/root/lme_data/，/tmp/lme_s.json
symlink）的 haystack_sessions 是**裸 turn-list**，而 C517/C518 时代
的 cleaned 文件是 {session_id, turns} dict。整条 pipeline 只有
`run_eval`（--mode eval）会 normalize 裸列表为 {session_id, messages}；
裸 CLI（默认 extract 路径）直接 ingest 会 `AttributeError: 'list'
object has no attribute 'get'`。**本轮首跑即崩于此**。 census 类脚本
（直接按 turn-list 读）不受影响——所以 C521 的 census/parity 没炸。
教训：eval 入口固定 `--mode eval`；fixture 持久化 /root/lme_data 已就位。

## 判例与教训

- **负结果要有产出门槛**：v1 census 直接全量跑，48 fires 的
  win/hijack 同构证据比"再调几轮 stop 表"更有价值——分离失败本身
  就是可记录的发现（C510 virtual-flip 先例的静态版）
- **收债刷新是最便宜的增量**：C519/C521 各自只做了切片 A/B，两轮
  "预测口径"的账本悬置；一次官方刷新 +3/−0 全部兑现，含 jitter
  自愈（86f00804）。切片链的可预测性再次验证（C517 先例）
- **标签红线**：benchmark 元数据（_abs 后缀）出现在 gate 特征里 =
  作弊，宁可放弃 4 个 win

## 留给下一轮

- ssu 34-wrong / speaker_recall 26-wrong 取证（C517 队列遗留，未动）
- POST --sidechannel 臂刷新（C517 遗留，未动；C508 树曾测 0.414）
- 已解锁题（25e5aa4f/bf659f65/488d3006）的 answer-face 转述失配
  （C519 遗留；风险高，需逐题取证）
- entropy gate 6 题误杀（0.95 阈值 C447/C448 sweep 过，动它影响全量）
- ⚠️ 主树 memory_graph.py 的 e04d222d `_search_cache` +24 行仍未提交，
  勿碰勿提交勿恢复；本轮全程 /tmp/c522 pristine（git show HEAD 抽取 +
  git archive suite 树），零接触

## 工件

/tmp/c522/{census_v1.py,census_v1.json,amg_post.py,memory_graph.py,
post_full500.json,cmp.py,run.log,suite/,suite_result.txt,tsv_rows.tsv}
官方基线：/tmp/c518/post_full500.json（0.448）
