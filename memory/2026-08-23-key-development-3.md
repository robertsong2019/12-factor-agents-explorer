# 2026-08-23 key-development-3 (Cycle 501) — role-aware answer face：echo pathology 修复

cron `b0fd7e8d-f946-4228-bb85-1baaa3502c7c`，Loop C 实验循环。
**结果：keep（e703ddd）— full-500 exact 163→183/500（0.326→0.366），+20/−0 零回归；套件 9872 全绿（+10）。**

## 前置：到达时状态机

- C499（23:00 Loop A）已刷新官方 reference（exact 0.316）；C500（00:00 Loop B）**正在跑**——工作树有未提交 item_total 改动 + /tmp/c500 活跃 arm 进程。
- 按 TOOLS.md 双发规则：不碰代码区，先做零成本取证（读 C499 报告 JSON）。C500 于 01:35 提交（8fa1825，multi 17→22）后接管。

## 问题定位（C499 报告取证，零进程）

- answer gate 全量 302 题：**257 wrong / 45 correct**；multi 106 wrong、kupdate 56 wrong 几乎全在 answer gate。
- **answer_session_hit 112/116 (multi wrong)、55/56 (kupdate wrong) = 检索找对了 session，抽答选错说话人** —— 病灶是 extraction 不是 retrieval。
- 病理：ranker `(-hits, -seq)` 下 assistant advice 重复讨论话题 → out-hit 用户简短事实陈述 → 回答="Mint is a fantastic app…" 而 GT="I spent $800 on a designer handbag"（用户行里就有）。
- exact judge 是 containment → 返回完整用户行（含 GT）即可判对，无需生成。

## 修复（amg_bench_quality.py，+233/−1）

`_user_fact_form`（第一人称代词 ∧ ¬recall_form ∧ ¬pref_form）+ `_answer_form_claimed`（ECM/pairwise/TA/counting/recall/pref 任一认领则跳过——**form 归属家族所有，fall-through 也不抢**，C482/C488 纪律）。answer gate 尾部：top 行是 assistant 且存在 user 行 hits ≥ top−margin（margin=0）且 ≥ floor(2) → 选 user 行。

**Sim 消融（302 题全 census，/tmp/c501/sim.json）**：m0f2/m1f2/m2f2 均 +20；无 form 排除版会翻掉 ec93e27f（counting 认领）+ c27434e8（pairwise 认领）——form 排除是防回归关键；floor=1 版 +21 但多 15 次覆盖（弱行劫持风险），floor=2 定稿。

## A/B（串行 full-500 两臂，每臂 ~19 min）

- base 臂 163/500 = C499 的 158 + C500 的 +5，**逐臂复现零漂移**。
- cur 臂 183/500：+20/−0 —— ssu +12、kupdate +5、multi +2、temporal +1（468eb064 "Who did I meet with during the lunch last Tuesday"，非 pairwise 形态）。
- 2312f94c/c27434e8/ec93e27f 等 form 认领题零扰动（构造性保证）。

## 踩坑

1. **跨会话协同**：到达时 C500 在飞——不抢文件、不抢内存，先零成本取证，等对方 commit（观察到 pytest+commit 序列）再动。1.9GB 盒子 A/B/suite 必须全串行（C495/C496 教训的延伸：连"观察别人跑"都要算内存）。
2. exec preflight 拒绝 `cd X && python3 ... > log` 复合命令——脚本先落盘再直接 `python3 file.py`（2026-08-22 研究日志同坑）。
3. sim 首版列表推导内变量遮蔽，D 状态进程是换页阵痛非死锁。

## 残余（answer gate 45→仍剩 ~237 wrong）

- ssu answer-gate wrong 剩 ~31：GT 不在检索窗口（rhit=False）或 user 行不 tie hits——下轮可试 margin=1 定向消融（+0 但多 4 override，风险面）。
- kupdate 剩 ~51：多数 GT=数值/短事实但用户行无 kw 重叠（floor 挡住）——需要 question-type 感知的 kw 扩展（数字/单位词），或放弃（性价比）。
- speaker_recall 26 wrong（C468 路径，本轮不碰）：mid-body 事实 vs 开场白排名仍差一步。

## Next Steps（C502 候选）

1. speaker_recall 剩余 26 wrong（ssa 0.286 是新最低非零类）——preface 排名改进或 distinctive 权重调参。
2. kupdate 数值事实的 kw 扩展（"How many…" → 数字 token 命中）。
3. full-500 刷新债重置（C501 已官方刷新，新债从 C502 起算）。

## 工件

- A/B：/tmp/c501/{arm500.py, base.py, full500_base.json, full500_cur.json}
- Sim：/tmp/c501/{sim.py, sim.json}（302 题 × 6 变体消融）
- 单测：test_role_answer.py（10 tests）
- experiments.tsv：`2026-08-23T02:32+08 e703ddd keep`
- commits：e703ddd（代码+测试，2 files，--stat 已核）
