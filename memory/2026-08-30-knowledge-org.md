# Knowledge Organization — 2026-08-30 02:00 (cron knowledge-organization-morning)

job fd0515b0-f483-411d-b110-3a16fbc49983。素材：git log 24h（fd204d7=C528 / f3bb5f7=C527b / c1863ad=C527）、memory/2026-08-30-key-development-{2,3}.md、memory/2026-08-29.md、memory/2026-08-29-knowledge-org.md、HEARTBEAT.md、MEMORY.md、两份 experiments.tsv、git status。

## 幂等三查
1. 产物：HEARTBEAT.md 有 kd-3 会话留下的**未提交**改动（3 处：全项目总计行、C528 活动条目替换 kd-2 条目、关键路径 #3 重写）；memory/2026-08-30-key-development-3.md **未提交**（git log 无记录）→ kd-3 已收工未落账，本轮接手补账。
2. commit/发布态：fd204d7 在库顶；无在飞会话（sessions_list 90min 仅本会话）→ 无并发冲突。
3. 台账：root experiments.tsv 有 C527 重复行 `20260830_004500`（项目仓真账本已有 20260830_002400+08 行）→ 拓扑混用又一例，按既有政策不改写历史，仅此处记录。

## MEMORY.md 更新（实质内容 5 处）
1. **Current Focus (2026-08-30)**：新增两节——
   - **08-30 凌晨 C527/C527b/C528 三连 arc**：官方 0.484 收债（+5/−1，census 预测 5/5 兑现，arc 0.204→0.484=2.37×）+ DATASET BIFURCATION（oracle/s_cleaned 同 500 qid 两套基准，官方只认 s_cleaned，三件套纪律）+ lineage 指纹（C527b）+ **tie-jitter 家族根因关闭**（C528：RNG 审计证伪 kd-2 假设 → 真双源=recall() wall-clock weight 写回突变 + uuid4-keyed set 迭代序 PPR seeds；readonly=True 纯读 rowid tie-break + 首发现序 seeds；det500 243/500=0.486，+1/−0 唯一 win=86f00804 本尊；q86 四进程跨 seed bitwise 同 predhash 4d4744e8b149618f；prefix50 A/A 50/50）→ **管线=dataset 纯函数，单题独立重放恢复合法**。
   - **08-29 白天~晚工具线 twin-purge 三连**：acs rename_key src+tests 双层孪生 2898→2934（家族 #7 首例测试层孪生，shadow class 遮蔽=假绿；force-push → 单提交 cherry-pick 正解）/ atc R67 1683→1704（12 死孪生清扫 + F143 Cache.swap TTL-blind 真 bug；家族 #8/#9；规则硬化：dup-check=unfiltered grep 写码前跑）/ agent-log F22-F24 31→49（dispatch 裸调用 bug；cron --job 实锤双注册 62bf7f3b+ce2fb615）。
2. **Active Theme**：零回滚 306→**307 天**；keep 链 C517→C527b 十一连→**C528 十二连**；官方口径 0.484 / det 0.486。
3. **测试总量表**：amg 10084→**10096**（表头 08-30 快照）+ amg API 列追加 C527/C527b/C528 三段；atc 1683→**1704**（+R67）；acs 2929→**2934**；agent-log 31→**49**；四项目 12338→**12371**；全项目 ~21546→**~21602**。
4. **insight #259**：「同 seed ≠ 确定」——PYTHONHASHSEED 钉不住 uuid4 值（os.urandom）与 time.time()；审计先于修复；残差驱动定位；bitwise 基线纪律（1 题 diff 即真信号，取代 ≥5 题阈值）；管线=dataset 纯函数后单题重放合法；twin 家族跨层再现（#7/#8/#9 + C528 变量遮蔽级联）。
5. C526 条目官方预测注记改为「已由 C527 收债 0.484 兑现」。

## HEARTBEAT.md 更新
- 标题 08-30 (Sunday)；amg 10089→10096（链 →10096(C528)，10095 绿 + 1 已知 perf-flake）；API 链追加 C527/C527b/C528 三段 ✅；acs 2929→2934（两处：TODO 行 + 计数行）；atc 1683→1704 + R67；四项目 12371；全项目 ~21602（KO 口径重排）；零回滚 307 天十二连。
- 近期活动：节标题 → 08-28~08-30；**新增 08-29 白天/晚 crons 两块**（acs #7 / agent-log docs 405a8ee / essay 79a2cec+05:04 双触发 / dashboard 9718b93 / trending GitNexus+ponytail 发飞书 M5ocdOdoSoh4MwxdBcuc7DPCnDb；creative 晚报 / Research #092 + 博客 8c2d897 / atc R67 / agent-log F22-F24+双注册实锤 / AI×Neuro #26 SNN）；C528 条目修时间戳（02:5x→01:00-02:00）+ 删 kd-2 遗留 stale 尾巴（增量①②/RNG 播种首选项——已被 C528 超越）；C527 条目 −1 注记改为 tie-jitter 牺牲品（C528 收回）；裁剪 08-27~28 era 陈旧条目（C520-C523、ptm 03:00、essay 双发 05:00、#090 三触发、skill-doctor 21:16——全在 MEMORY arc）；整节删除 08-26~27 活动节（内容在 MEMORY arc）。
- ⚠️ cron 双触发行更新为 08-29 三例 + tool-dev 双注册 live 实锤；Tavily 432 第 6→7 天；npm publish blocked 行 12371；MEMORY.md size ~265→~274KB；上次检查裁至三轮（新增 08-30、删 08-27）。

## experiments.tsv 趋势（项目仓真账本）
- C522 0.454 → C523 0.476 → **C527 0.484（242/500）→ C528 det500 0.486（243/500）**；arc 0.204→0.486=2.38×。C527b 无分数行（指纹基建，+5 tests）。连续 5 次官方刷新收债（C517/C519/C522/C527/C528）全数兑现或超预期，census 预测准确率 5/5。
- root tsv C527 重复行 20260830_004500：不改写（append-only），拓扑混用监测续。

## 质量检查
- MEMORY.md 反映真实状态 ✅：顶部 arc=08-30 凌晨三连；表格 suite 10096 与 fd204d7 实测一致（10095 绿 + 1 已知 perf-flake）；det 0.486 官方口径明确标注；#259 与 C528 证据链一致。
- HEARTBEAT.md 可操作性 ✅：关键路径 #3 已由 kd-3 重写（judge_semantic 升最高优先——确定性管线下面/检索侧已稳，剩余 wrong 大头在判分器）；#2 仍 BLOCKED on human（npm publish）；孤儿 dirty 文件 memory_graph.py e04d222d 连续第 8 天记录在案。
- 遗留债（未处理，记录）：memory/2026-08-30-key-development-3.md 与本轮三文件待 commit（下步执行）；cron 双注册 5 组仍待罗嵩拍板删除；kd-3 提出的 exec 后台 kill 孤儿进程课已入 MEMORY/HEARTBEAT。

## 提交
git add 仅 MEMORY.md HEARTBEAT.md memory/2026-08-30-knowledge-org.md memory/2026-08-30-key-development-3.md（kd-3 未落账的笔记），commit 消息沿用「knowledge org 08-30: …」风格。
