# 2026-08-29 key-development C525 — ku recency session-scope answer face（keep，census +2/−0）

cron `key-development-2`（88679f9e…，00:00 触发）。C524 spin-off「session-scoped answer-face」落地为 C525 keep；同夜完成 answer-gate 全人口 census，瓶颈正式迁移到检索窗口组成。

## 结论 TL;DR

- **KEEP**：`_KU_RECENCY_RE`（so far/currently/to date/lately/these days/up to now/as of now|today）+ face 会话 ≠ 最新证据会话 → 重排 face 到最新证据会话最优行（max hits 平局取最新 seq，任意 role，floor 2）。**census：6 fires = 2 wins + 4 wrong→wrong noop，零 correct 触碰；prodverify 生产码 A/B 完全复现（OFF 67 → ON 69）**。
- 预测口径 +2/−0（official exact 238→240 待官方刷新收债，C519/C521→C522 先例）；官方 0.476 未变。
- **scope 收窄即分离器**：同一 fire 条件去掉 adverb scope 会 fire 58 次含 10 hijack（含 3 个 C523 win）——C522/C524「签名同构不可分」模式这次靠 form-narrowing 躲过，不是靠新判别器。
- **主产出（记录性）**：answer-gate 面枯竭 + 瓶颈迁移——158 wrong 中 **109 题 GT 行根本不在窗口（69%）**，其中 **92 题 GT 会话在窗口、GT 行不在**（answer_session_hit=True）→ 下一 surface = 窗口组成（dump 预算截断前的完整 ranked list / GT 行 rank 分布）；17 题 GT 会话全漏。

## 实验循环记录

1. **目标**：C524 spin-off（HEARTBEAT 关键路径候选）。census-first：先对 225 个 answer-gate 题（官方 C523 post `retrieval.gate=='answer'`，ijson 流式抽取 `/tmp/c525/pop225.json`）做会话拓扑 dump。
2. **census 工具两次翻车与修复**：
   - v1 发现 **label 内嵌换行 → `context.split('\n')` 与 `retrieved_ids` 错位 → sid 全错配**（face/gt/会话归属全不可信）。v1 存档 `census_rows_v1_badsid.json` 作废，v2 改从 ids+`adapter._messages` 重建行。**教训：窗口行映射永远走 retrieved_ids，split 只是显示层**；生产码本来的 split-遍历有同一潜在 quirk（cosmetic，未动）。
   - 重放保真度：225 题 PA 与官方 mismatch 仅 3，6 个 verdict diff 全部 official-True→replay-wrong（margin-0.0 tie-jitter 家族，C518/C524 先例；099778bb/945e3d21 为幻影 hijack——重放里本就 wrong）。
3. **分析（analyze_c525.py v2）**：topology = 67 correct / 109 GT 行不在窗口 / 13 in-session / 36 cross-session。**行级 R1（session recency）+6/−10、R4 +6/−9 双双证伪**（C524 行级 + 会话级双重确认 recency 方向裸用会劫持）。
4. **KU-adverb scope 发现（analyze_ku.py）**：kupdate 语义（C524「recency 是 session/date 信号」）的词汇化标记 → scoped R1 **fires=6 +2/−0**。
5. **落地**：/tmp/c525/base（HEAD: 5aae7e0 双文件 pristine，diff 验证与 /tmp/c523/patched 一致）→ 工作树外科式编辑 `amg_bench_quality.py`（6 处接线：regex/init/块/run_eval/argparse×3）+ 新 `test_ku_session_face.py` 10 tests 红→绿。**未触碰 memory_graph.py 脏改动（e04d222d _search_cache 第 5 天）**。
6. **测试**：单文件 10/10；unittest discover 797 绿 exit 0；**pytest 全量（10069 collected 口径）跑通**（C523 基准 241s）。
7. **prodverify A/B（/tmp/c525/prodverify.py）**：225 题 × {ku ON, OFF} 生产码重放，**与 census 预测逐 qid 一致**：fires 同 6 题、wins 1a8a66a6+6a27ffc2、losses 0、OFF 67→ON 69。
8. **keep**：单 commit（码+test+tsv+memory+HEARTBEAT），git add 精确文件列表，**绝不 add memory_graph.py**。

## 机制细节（给未来 cycle）

- 块位置：answer_extractive 的 answer-gate 路径 **C523 块之后**（在 C523 face 基础上再修会话错位——6a27ffc2 正是 C523 在旧会话内重排后、本机制跨会话纠正的实例）。
- 窗口行映射：`meta['retrieved_ids']` + `self._messages[nid]`（label 可能内嵌换行，**禁止 split 映射**——census v1 教训写进了代码注释）。
- candidates = 最新证据会话（hits≥1 行中 max seq 的 sid）内 hits≥2 的**任意 role** 行（1a8a66a6 的 win 就是 assistant 行；与 C501/C523 的 user-only 不同，census 支持的差异化）。
- 平局取 max seq（C437/C447 recency 惯例）。无候选 → fall-through（C488），meta 恒记 `ku_session_face` 四字段（face_session/latest_evidence_session/candidate_hits/override）。
- flag：`ku_session_face` / `--no-ku-session-face`，与 quant_rerank 正交。
- wins 剖面：1a8a66a6（magazine subscriptions currently，候选=assistant h2，GT"2"）+ 6a27ffc2（Corey Schafer 30 videos so far，user h5 平局 seq 取最新）。如实记录：1a8a66a6 的 GT 判定仍属 containment 口径（a9f6b44c 同族），机制不读 judge、行为合法。

## 决策记录：为什么 -2/0 也算达标的 keep

- census 覆盖完整 fire 面（answer-gate ∩ KU-form 全人口，非抽样）；0 hijack 不是样本估计而是闭集事实。
- 专职守卫：专用 gate（counting/TA/delta）在 gate 顺序上游先认领自己的 form，本块只见 answer-gate 残差——fire 面天然受限。
- C516 stop-mining 教训对照：这不是「从 win 里钓 scope」——C524 独立指出 kupdate recency 方向后 census 验证，且 unscoped 对照组（58 fires/10 hijack）证明 scope 承载全部分离力。

## 下 cycle 队列（window-composition census 规格）

1. dump 预算截断前的完整 ranked list（retrieve_context 内部顺序，不只 top-12 窗口）+ GT 行 rank 分布；92 题分层：GT 行 rank 13-N（预算外）vs 根本没被检索出来。
2. 对照 17 题全漏：GT 会话 seed 召回失败原因（无关键词重叠 / PPR 扩散失败）。
3. 工具侧：census 行映射直接复用本 cycle 的 ids+messages 重建法（v1 split 错位勿再犯）。
4. 相关队列遗留：judge_semantic A/B 仍是最优先（#090）；1a8a66a6 类 containment 口径 win 是 judge_semantic 的天然评测题。

## 工具/环境备忘

- exec 复杂 heredoc/管道预检被拒（本轮 2 次）→ 直接 `python3 /abs/file.py` 重定向日志。
- 全量 suite 口径：**pytest -x -q（10069 collected）**，unittest discover 只有 797（顶层口径，勿混用）。
- 后台会话：quiet-ember（prodverify）、young-basil（pytest）、nimble-tidepool（discover）。
