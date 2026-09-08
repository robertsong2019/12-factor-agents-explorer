# Key Development 3 — Cycle C560 (2026-09-09)

**Task:** cron `key-development-3` · autoresearch 方法论实验循环 C · 基于链头 C559（banked 290 / 0.580，commit `66adc0a`）

**结果：预测中性 keep（banked 290 / 0.580 保持），判定面 provenance 增量——report 双列新增 `judge_prompt_sha12` + `judge_model` 两枚指纹，suite 10361 → 10370 green junit 306s 0F/0E（+9 tests），无回放（设计使然：预测路径零改动，A/B 等价由构造保证）**

## 并发事件（本次循环的主线剧情）

01:00 到岗即撞 kd-2 的 C559 in-flight：`amg_bench_quality.py` 102 行脏插入（name-def face）+ 活跃 pytest（junit_base 流程）+ 500-replay 进程。按幂等纪律第 3 条处理：

- **不碰它的文件/目标**（c4f10528 是它 C558 行里排的队，它有权先做）
- 测试草案全写 `/tmp/c560/`，不进项目目录（避免污染它的 base/green 计数——它会临时摘自己的测试文件跑基线）
- 挂后台等待器盯 commit，38 分钟后 C559 落地（289→290），再在其上应用
- 教训：轮询期 ps 的 START 列与 etime 读数一度"矛盾"，实际是 poll 提前返回导致我对墙上时间的估计漂了 50 分钟——**以 `date` 为准，勿用累计 sleep 推算当前时刻**

## 增量内容：judge provenance fingerprint（C558 队列第 4 项）

C530 指纹了 judge backend（mock/ollama/unconsulted），但两个维度仍不可审计：

1. **JUDGE_PROMPT 漂移**：改 prompt = 同代码不同 verdict，报告无迹可查 → `judge_prompt_sha12`（sha256 前 12 位），放在 dual/semantic 分支 judge_llm_backend 旁；测试证明它跟随活常量（改 JUDGE_PROMPT 哈希即变，不是死字面量）
2. **judge 模型身份**：`judge_ollama` 的 model 参数（默认 qwen2.5:7b）在报告里隐形 → sticky `_JUDGE_MODEL`（仅非 ERROR verdict 时记录——ERROR=网络/模型故障=没出判决，不得冒认），报告仅在 backend==ollama 时携带 `judge_model`；mock/unconsulted 诚实缺席

## 验证链

- 红先：2 个核心接线测试在 HEAD 上按预期理由失败（缺 `_JUDGE_MODEL` 属性 / 缺 `judge_prompt_sha12` 键）
- 实现后 9/9 绿；全套件 junit：**10370 tests / 0 failures / 0 errors / 0 skipped**（C559 的 10361 + 我的 9，严丝合缝）
- 无 500-replay：config-only 面，预测逐字节不变由构造保证（C527/C528/C530 指纹周期同款先例）

## 技术坑（两个，都有普适性）

- **同函数两个 `global X` 声明 = SyntaxError**（"assigned to before global declaration"）——第一版把 global 放在两个分支里，改为函数顶部单声明
- **fd 级 stdout 吞噬复现**：全套件 `pytest -q` 三次 exit 0 但管道/重定向输出全空（0 字节）——kd-2 的 suite.out 同为 0 字节，**junitxml 是唯一可靠计数通道**，此后套件计数一律 `--junitxml` + ET 解析
- 环境事实：本机 ollama **不在线**（probe 秒降级 sticky mock）；我原以为 1 题样本会 "unconsulted"，实际 dual 模式照样探测 → 测试改为断言诚实缺席（backend != "ollama" 且无 judge_model），不过度钉环境

## 纪律保持

- `git diff --stat` = 恰 12 行插入，逐 hunk 对得上自己的编辑（无外来 hunk 混入）
- memory_graph.py 脏 hunk 第 21 天未碰；3 个 untracked 旧文件留置
- preflight 拒复杂解释器调用链 → write 工具建脚本 + 纯 `python3 <file>` 直跑
- experiments.tsv 追加走幂等脚本（已存在 C560 行则拒写）

## 数值轨迹

0.502 → … → 0.576 → 0.578 → **0.580（本轮预测中性，保持）**

## Next queue（继承 C558/C559 后的残余）

1. ollama oracle（human-blocked，~169 NJ cascade）
2. run_amg packaging
3. MCP registry publish
4. （新）若后续跑真 ollama：`judge_model` 应实值出现，可加 end-to-end 断言

## Artifacts

- /tmp/c560/{test_judge_provenance.py, append_row.py, junit.xml, suite_final.txt}
- experiments.tsv C560 行（8 字段，keep）
