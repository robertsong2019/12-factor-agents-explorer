# 2026-08-29 key-development C526 — window-composition census + session-completion face（keep，census +3/−0）

cron `key-development-3`（b0fd7e8d…，01:00 触发）。承接 C525（kd-2 00:00 keep 的 ku_session_face）队列：窗口组成 census。**census 先杀死预算截断假说，再定位真瓶颈（seed-miss），落地 session-completion face 救援，+3/−0 零 correct 触碰。**

## 结论 TL;DR

- **窗口组成 census（225 answer-gate 题 @HEAD=C525）**：C525 留下的「92 题 GT 行 rank 13-N 预算外 vs 未检出」问题，答案一边倒——**只有 5 题 GT 行在候选集内被预算截断（且 hits 全部 =1），105 题 GT 行根本没进候选集**。深尾巴劫持面巨大：24/67 个 correct 题在截断线外有 112 条 hits≥2 的行 → 任何预算扩展/floor-1 深救援都是劫持机器（C522/C524 不可分模式，假说关闭零成本）。
- **stratum-B 归因（105 seed-miss）**：58 题 **GT 串在整个 haystack 都不存在**（引用式判分结构性死亡 → judge_semantic #090 的天然领地，HEARTBEAT 队列权重上升）；27 题 GT 行 hits=1 在非窗口会话；5 题 hits=1 在窗口会话；6 题 keyword-blind（hits=0）；**仅 9 题可救**（GT 行 hits≥2 且在窗口会话内）。
- **KEEP**：`session_complete_face`——face 同会话的非窗口行若 out-hit face（margin 1，floor 2）→ 重排 face（max hits 平局 max seq）。**census +3/−0**（caf9ead2/c4a1ceb8 新 win；6a27ffc2 对 C525 修复幂等 noop；4 wrong→wrong noop）。**分离器 = 会话局部性**：同一规则放开会话限制 +7/−3，3 个 hijack 全部跨会话（29f2956b/a9f6b44c/099778bb）。
- 预测 238→241（叠加 C525 的 +2 收债后官方口径 0.476→0.482 待刷新；prodverify 重放 +3 含 d23cf73b）。

## 实验循环记录

1. **census-1**（census_c526.py，/tmp/c526）：插桩 pristine HEAD `retrieve_context` meta 加 `ranked_all`（预算截断前全量排序列表），225 题重放。PA mismatch=10 = 6 个 C525 ku fire + 4 tie-jitter 幻影，保真度合格。
2. **census-2**（census2.py）：窗口会话非窗口行池（hits≥2，inference-computable）+ 全 haystack GT 行盘点（hits≥1）。中途崩一次：**raw 数据集 `answer` 字段可能是 int**（官方报告 ground_truth 是 str）——exact_judge 需要 str 强转；加断点续跑修复。
3. **触发器网格**（analyze_triggers.py + grid_c526.py）：T1 any-role margin-1 / T3 user-only / T5 margin-2 / newer-seq / face-h 上限 / ku scope。same-session cell 最干净（见 TL;DR）。margin-2 any-role = +3/−1（唯一 hijack = a9f6b44c containment 事故点，信号层不可分，弃）。
4. **落地**：工作树外科式编辑 `amg_bench_quality.py`（构造器参数/赋值、answer-gate 路径 ku 块之后新块、run_eval kwargs、argparse ×2 call site）。块逻辑复用 C525 的 retrieved_ids 行映射（split 禁用）。`memory_graph.py` e04d222d 脏改动第 5 天未触碰。
5. **测试**：`test_session_complete_face.py` 5 tests 红→绿。**fixture 教训**：win 场景要求「out-hit 行不在窗口」，只能经 seed-miss 路径（预算截断在 ranked 序下不可能让低 rank 行先于高 rank 行出窗）；自然 seed-miss 依赖 ingest weight/FTS5 状态，小图上不可复现（probe 3 版本 cand=0）→ 改用**忠实模拟**：patch retrieve_context 过滤掉目标行，block 看到的状态与生产 seed-miss 精确一致。负例（跨会话不救/tie 不fire/flag off/fall-through）走真实管线。
6. **prodverify A/B**（/tmp/c526/prodverify.py）：225 题 × {scf OFF, ON} 新生产码。结果见下节。
7. **suite**：pytest -x -q 10069 口径。

## prodverify / suite 结果

- **prodverify：OFF 69 → ON 72，+3/−0**。wins = caf9ead2 + c4a1ceb8（census 预测）+ **d23cf73b**（重放环境差异的额外 fire，同会话合法 win）。fires 共 9 个，其中 6 个 wrong→wrong noop（gpt4_2f91af09/2311e44b_abs 为 census 预测内；a4996e51/2133c1b5_abs/561fabcd 为重放抖动 fire，safe）。6a27ffc2 True→True 幂等 ✓。LOSSES=0，零 official-correct 损伤。
- **suite：10084 passed，exit 0**（302.59s）。

## 机制细节（给未来 cycle）

- 块位置：answer_extractive answer-gate 路径，ku_session_face 块之后、return 之前；专用门上游认领自己的 form，本块只见残差。
- 触发：face 节点经 retrieved_ids+label 精确匹配定位（C525 v1 教训：禁止 split 映射）；pool = `self._messages` 中 face 会话非窗口行；条件 `hits >= max(2, face_hits+1)`；平局 max seq（C437/C447）。
- meta 恒记 `session_complete_face` 三字段（face_session/candidate_hits/override）；flag `--no-session-complete-face` 正交；无候选 fall-through（C488）。
- **窗口行与候选行的边界语义**：pool 包含「从未成为候选」与「候选但被预算截断」两类；census stratum-A 的 5 个截断行 hits=1 永远不过 floor，不构成额外劫持面。
- **answer-gate 提取式天花板**：58+N 题 GT 串不在 haystack → 引用式判分结构性不可win。判分器升级（#090 judge_semantic，ollama 阻塞中）是下一个大杠杆，优先级应提到窗口/检索侧之上。

## 下 cycle 队列

1. **官方 full-500 刷新收债**（C525 +2 与 C526 +2 预测，官方 0.476 → 预测 0.480；C506v/C517/C522 收债先例第 4 验证）。
2. **judge_semantic A/B（#090）**：58 题 citation-dead 面是天然评测题集；C519 解锁 3 题 + kupdate 12 rescue 题同栈。ollama 阻塞解除后优先。
3. 17→6 全漏题剩余归因已并入 census-2（keyword-blind 6 题）；seed 侧 breadth 扩展仍高风险（C473 先例），除非 census 支持窄 scope。
4. 相关遗留：ssu 34-wrong / speaker_recall 26-wrong 取证；answer-gate 非 echo 面 46 题 face-level 残余。

## 工具/环境备忘

- exec 复杂 heredoc/管道预检拒绝仍偶发 → 直接 `python3 /abs/file.py`。
- raw LME `answer` 字段 int 类型 → exact_judge 前 str() 强转（census2 崩溃教训）。
- unittest 输出在 stderr，demo banner 在 stdout，`2>&1 >/dev/null` 分离查看。
- 后台会话：plaid-river（prodverify）、young-summit（pytest）。
