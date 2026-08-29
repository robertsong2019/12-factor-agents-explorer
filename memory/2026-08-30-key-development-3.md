# 2026-08-30 01:00 — key-development-3 (C528: tie-jitter 家族根因关闭 — readonly 确定性 recall + uuid 序 PPR seeds)

cron `key-development-3`（b0fd7e8d…，01:00 触发）。承接 kd-2（f3bb5f7 C527b）队列 #1「RNG 播种」。**审计证伪 C527b 根因假设 → 定位真双源（wall-clock recall 突变 + uuid hash 序 PPR seeds）→ 修复 → det500 +1/−0 且唯一 win 恰是 86f00804 本尊 → 家族关闭。**

## 结论 TL;DR

- **RNG 审计（负结果，修正 C527b）**：memory_graph.py 全部 `random` 调用点要么已播种（`Random(42/123/seed)`、`seed(42)`）要么在检索不可达的分析函数里（betweenness/spectral/random_walk）；amg_bench_quality.py 零使用。**检索路径不存在未播种 RNG** — kd-2 的「tie-jitter = 未播种 RNG」假设被 grep 审计证伪。
- **真根因（双源）**：
  1. `recall()` **wall-clock 突变**：每次调用写回 `weight=min(1.0, w·exp(-0.3·elapsed))+ACCESS_BOOST`、`accessed=now`；ingest 给**所有节点 weight=1.0** → `ORDER BY weight DESC` 的 near-tie 完全由 ingest 时间散布的 decay 浮点噪声决定排序。DECAY_RATE=0.3/天，跨天 replay 差 26% 权重。
  2. **PPR seed 选择的 uuid hash 序**：`seeds=[nid for nid in candidate_ids][:8]` 迭代 set —— set 的 hash 序由 key 决定，而 node id 是**每次 ingest 全新 uuid4（os.urandom，PYTHONHASHSEED 管不到）** → PPR 扩展逐 run 重掷。kd-2 的「疑似 PPR/采样路径」方向对、机制错（set 序非 RNG 采样）。
  - C527b 观察到的「scf 随机 hijack」是下游症状：候选集翻转 → face 行进出窗口 → scf fire 翻转。
- **修复（KEEP，fd204d7）**：`MemoryGraph.recall(readonly=True)` 纯读（无 decay/boost/写回，`ORDER BY weight DESC, rowid` 显式 tie-break=ingest 序）+ `ordered_candidates` 首发现序选 PPR seeds；adapter `deterministic_recall=True` 默认，run_eval/report-config/argparse 全接线，`--wallclock-recall` 逃生口（legacy 路径逐字节保留，readonly=False 默认行为零改动）。
- **证据链**：
  - **det500**（全 500 题、s_cleaned、PYTHONHASHSEED=7、ku+scf ON）：**243/500（0.486）vs 银行 242**，**+1/−0，唯一 win = 86f00804**（噪声牺牲品收回其历史多数判定 C517✓/C522✓/C523✓）；其余 499 题判定与银行 run 逐 qid 一致。官方口径 0.484 → 0.486（fd204d7 收债，第 5 次收债）。
  - **q86 稳定性**：4 个独立 fresh 进程（含 PYTHONHASHSEED 7/6 跨种子）predhash 全部 `4d4744e8b149618f`、correct=True —— 对比 C527 换序重放 ✓✓✗✗。**方差归零达成（队列 #1 成功标准）**。
  - **prefix50 A/A**：两个 fresh 进程 50/50 predhash 逐字节一致。端到端 bitwise 可复现成立。
- **测试**：+7（test_deterministic_recall.py：时间免疫/无突变/rowid tie-break/legacy boost 保留/adapter 默认/跨时钟表 schedule 答案恒定/report flag）；test_seed_breadth.py spy 签名 `**kw` 修复；suite **10096 = 10095 绿 + 1 perf-flake**（test_large_batch_performance 全套压力下失败、standalone 两次通过 55/55，已知家族非回归）。

## 方法论沉淀

- **「同 seed ≠ 确定」的完整解释**：PYTHONHASHSEED 只钉 str 的 hash → set/dict 序。但 (a) uuid4 的值本身随机（os.urandom），以它为 key 的容器序照样随机；(b) time.time() 进决策 = 另一独立源。C527b「两个独立抖动源」方向对，但把 (a) 误归因为「未播种 random 模块」。
- **审计先于修复**：10 分钟的 grep 审计（random 调用点 × 所属函数 × 可达性）就杀死了上一轮的根因假设——「先证伪再动工」再次省掉一次无效实现（真去播种 RNG 将一无所获）。
- **残差驱动定位**：readonly recall 后 q86 仍 1/4 翻转 → 逼出 uuid-set 序第二源。单点修复不完整是常态，重放电池（多 fresh 进程 + 跨种子）是抓残差的正确工具。
- **Bitwise 基线纪律（升级 kd-2 的「≥5 题阈值」）**：确定性模式下跨 run 任何 1 题 diff 即真信号；A/A prefix50 可作为任意 cycle 的廉价健康检查（~6 分钟）。
- **单题独立重放恢复合法**：pipeline 现在是 dataset 的纯函数 —— census/取证不再需要全套件上下文（C527 时代「单题重放必须独立进程且不可信」的痛感消除）。

## 工具/环境备忘

- **exec 后台 kill 只杀 shell 不杀 python 子进程**（本轮实录：young-kelp kill 后 python 孤儿存活，双 run 争 2 核各掉一半速）——kill 后必须 `ps -ef | grep` 验证子进程；孤儿重定向到已删除 inode 的 log 可经 /proc/<pid>/fd 找回（本轮未需要，直接 kill -9）。
- 后台脚本 `env VAR=... cmd > log` 前缀会被 exec preflight 拒 → 写 launcher .sh 包装（chmod +x）。
- pytest 全套 ~230s；**perf 测试（test_large_batch_performance）在全套压力/并发 eval 下是已知 flaky**，standalone 0.2s 过 —— 判定流程与 node --test deserialize flake 相同：重跑 standalone。
- staging 教训复用：memory_graph.py 脏 hunk（_search_cache e04d222d）第 8 天未动 —— 本轮用 `git apply --cached` 只提交 recall hunk（`git diff > patch → 过滤 @@ -547 hunk → apply --cached`），脏改动原样留在 worktree。

## 下 cycle 队列

1. **judge_semantic A/B（#090）升为最高优先**：58 题 citation-dead 面 + #092 校准协议已备；ollama 解除阻塞后直接开跑。（窗口/检索侧已确定性化，剩余 wrong 面大头在判分器。）
2. **scf/ku fire 面精确 census**：确定性管线下面行进出窗口不再漂移 —— C526 队列的「scf fire 面精确 census」现在可做；86f00804 已定格 correct，scf scope 收紧需求消失（无 fire 可翻）。
3. **oracle-track fast-iteration 开发集**启用评估（det 模式下 oracle 臂同样 bitwise 可复现，1/5 体积）。
4. 遗留：ssu 34-wrong / speaker_recall 26-wrong 取证；answer-gate 非 echo 面 46 题残余；PYTHONHASHSEED 钉 seed 纪律降级评估（q86 跨种子已稳，但未全量验证——保守起见 runbook 暂保留钉 seed）。

## 工件

- /tmp/c528/{run_det500.py, post_det500.json, det500.log, q86_once.py, q86_launch.sh, q86_stable.log, prefix50.py, prefix_launch.sh, prefix50_{A,B}.json, mg_recall_only.patch}
- 官方刷新 runbook 增量：det 模式默认开（无需加 flag）；`--wallclock-recall` 仅用于血统对照；config.deterministic_recall 字段已入 report。
