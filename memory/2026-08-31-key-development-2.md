# 2026-08-31 00:00 — key-development-2 (C530: official cascade-500 收债 + judge backend 指纹)

cron `key-development-2`（88679f9e…，00:00 触发）。承接 kd-1 C529（dc6ddb6，23:00）遗留债务：「~+8 deterministic rescues 在下轮官方 cascade-500 入账」。幂等三查通过（今日无 kd-2 产物；git log 近 10 分钟无 kd 提交；sessions_list 无并发会话、ps 无在飞 eval 进程）。

## 结论 TL;DR

- **官方 cascade-500 落地（收债完成，第 6 次收债）**：243/500 (0.486 exact，与 det500 **逐字节一致**：predicted 0/500 diff、exact verdict 0/500 diff——管线纯函数性再次认证) → **语义层确定性判定 246/500 (0.492)**。指纹全对：judge_mode=semantic / det_recall=True / data_sha=d6f21ea9d60a / seed=7 / s_cleaned。
- **C529 census 预测 8/8 全兑现**：rescues +8 = 22d2cb42、352ab8bd、4b24c848、b320f3f8、e493bb7c、e9327a54、gpt4_4edbafa2、gpt4_68e94288（我 00:10 的 census 预演抓到 7/8——缺的 4b24c848 被过宽的 gate 排除遮蔽，官方 run 修正）。
- **veto-kills −5 = 判分有效性增量，非损失**：00ca467f、a9f6b44c（C523 已知的 "2"⊆"2023" containment 事故 win）、e56a43b9、gpt4_45189cb4、gpt4_98f46fc6 —— 全是 containment 伪包含被语义守卫拦截。净账 +3。
- **⚠️ 本轮主发现：mock fallback 静默污染 semantic run**。无 ollama 时 judge_llm 自动降级 lexical mock，24 个 NEEDS_JUDGE 行被 mock 判定（20 假 rescue + 4 假 kill），raw cascade 262/500 (0.524) **不可入账**；#092 协议要求 oracle 判定的原因具象化了。
- **代码增量（KEEP）**：report config 新增 `judge_llm_backend` 指纹（"mock"/"ollama"/"unconsulted"）——mock-resolved run 从此在 report 自白，不再需要离线重放才发现。+3 tests（unconsulted / mock / exact 无字段），test_judge_semantic 44→47。

## 决策记录：入账口径

- **入账 246 (0.492) = exact + 语义层确定性 delta（+8 rescues −5 veto-kills）**；NEEDS_JUDGE 行保留 exact 判定（无证据翻转）。这是 judge_cascade 语义的忠实读法：semantic WRONG（守卫 veto）是终审。
- **不入账 262**：mock 判定非 oracle 证据。judge_ab 的 mcnemar_p=0.0026 "cascade>exact" 被 mock 污染，不作数；诚实 A/B 在可判定 discordant 对 (b=8, c=5) 上 p=0.5811 —— 单看分数不显著，**升级依据是判分有效性**（伪包含拦截）而非分数 delta，与 C529 census 框架一致。
- 无代码回退需求：管线零改动，本轮代码增量纯 report 侧（C520/C527b 先例）。

## 分类净账（确定性 delta）

- knowledge_update +3/−0（ku 语面 rescue 族）
- single_session_assistant +2/−0；single_session_user +1/−0
- temporal_reasoning +2/−2；multi_session −3（伪包含 kill，含 a9f6b44c）
- gate cross-check：0 suspect —— 生产判定 100% 可由「语义 verdict + mock NEEDS_JUDGE 解析」解释，census 数字生产忠实

## 方法论沉淀

- **报告自证原则**：任何依赖环境探测（ollama probe）的降级路径必须在 report 留指纹，否则 A/B 读数会被静默污染（本轮若直接读 accuracy_llm=0.524 会误报「进 0.50+ 带」）。
- **census 预测的 gate 排除要保守**：我 00:10 预演用题面 form 正则排除 gate-ish 206 行，漏掉 1 个 rescue——form 匹配 ≠ gate 生效（答案未 resolve 会 fall-through）。官方 run 才是 gate 归属的 ground truth。
- C529 的「+8 → ~0.50 band」是 rescue 毛数；净数 +3 → 0.492。入账口径差异要在预测时写明（毛 vs 净）。

## 工具/环境备忘

- 官方 run 时长实测 ~20 min（1197s wall，95% 单核），/tmp/c530/{run_cascade500.py, launch.sh, census_preview.py, verify_c530.py, percat.py, post_cascade500.json, cascade500.log}。
- exec background 会话的 process poll 不阻塞真实时间（连续 poll 立即返回），长等待用 `sleep N; ...` 命令 + timeout。
- pytest 全套见 suite_result.txt（预期 10140 = 10137+3，known perf flake 单独判定）。
- memory_graph.py 脏 hunk（e04d222d _search_cache）第 9 天未触碰；本轮验证 search_fused 不在 bench 路径（grep 零引用）——该 hunk 对 eval 管线惰性，pristine ≡ worktree。

## 下 cycle 队列

1. **ollama oracle 接入后跑真 cascade A/B**（#090/#092 主菜）：169-172 题 NEEDS_JUDGE 面的 LLM 判定上行空间仍未入账；judge_llm_backend 指纹已就位，A/B 报告可信。
2. answer-gate 非 echo 面 46 题残余 / ssu 34-wrong / speaker_recall 26-wrong 取证（遗留）。
3. oracle-track fast-iteration 开发集启用评估（det 模式下 1/5 体积）。
4. veto 守卫对 multi_session 的 −3 可作 census 复核（确认无误杀）。

## 工件

- /tmp/c530/{post_cascade500.json, cascade500.log, run_cascade500.py, launch.sh, census_preview.py, verify_c530.py, percat.py, suite_result.txt}
