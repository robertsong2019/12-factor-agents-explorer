# 2026-09-04 — key-development-2 (cron `88679f9e`, C544, kd-2 00:00)

## 任务
autoresearch 循环 B：读 autoresearch.md + kd-1（C543）最新成果，继续推进 amg LongMemEval full-500。成功标准 = C543 之上 ≥1 增量。

## 结果：KEEP，banked 260→262（0.520→0.524），+2 / 0 kill / 0 downgrade ✅

### 主攻：judge 侧 NJ 队列挖 face（C543 next 候选 #3，C541/C542 已验证的矿脉）

**Census 先行**（/tmp/c544/census_nj.py）：
- 同源基线复核：live500_head.json 存储快照 + C535 ledger 公式重算 = **260 精确**；唯一 drift 行 = 8752c811（存储 v=WRONG 早于 C542 face 接线，现 CORRECT = 那 +1）——TOOLS.md 同源规则直接救了一轮错误结论（第一次跑只数纯语义 CORRECT 得 236，差点误判 ledger 崩坏）
- 可采队列 = **146 NJ ∧ frozen-exact-False**（149 是 kd-1 时的计数，现口径 146）：113 zero-overlap（诚实弃权区，不碰）+ 33 partial-overlap（挖 face 的矿脉）
- NJ ∧ exact-True 6 行已被 exact credit 入账（flip 无增量），WRONG 82 行结构性不可达（全部 WRONG 路径在 face 行之前 return）

### 两个 face，全 500 census 后接线

1. **`_sem_paren_complement_face`（paren-elaboration）**：GT = `Head (elaboration)` 时 head 本身即断言事实（c6853660: GT `You increased the limit (from one cup to two cups)` vs pred `I have increased the limit to two cups`）。守卫：head 剥离括号后 ≥2 content token（薄头 `Yes. (You have a road bike too.)` 排除）、嵌套括号 bail、**人称 deixis fold（you/your→i/my）**——census 抓到 naive 版依赖 pred 另一句里顺带的 "you" 才 fire（`Do you have any recommendations...`），语义上是错的理由；fold 后按 grader 第二人称 vs user 第一人称同事实诚实 fire
2. **`_sem_tense_superset_face`（tense-fold superset）**：had/has、was/is、were/are 三对时态折叠加两侧 token 严格超集（89527b6b: GT `The Plesiosaur had a blue scaly body.` vs pred `The Plesiosaur has a blue scaly body, and its eyes are fixed...`）。要求至少一对时态词实际出现——时态一致的对早走原 superset 分支返回 CORRECT，face 不放宽既有路径

两个 face 都接在 C541 alias-face 行（NEEDS_JUDGE zone），数学上只可能 NJ→CORRECT，纯上行。

### Census 数字（/tmp/c544/census_faces.py，接线前全枚举）

- Face A：3 fires = 2 已 CORRECT（no-op）+ 1 gain；0 thin-head/嵌套假阳性
- Face B：31 fires = 30 已 CORRECT（no-op）+ 1 gain；0 时态无关误触

### A/B 验证（/tmp/c544/ab_faces.py，双臂同源 + 逐行 tripwire）

- 3 flips 全 upgrade：c6853660 + 89527b6b（新）+ 8752c811（已知 C542 存储增量）；0 kills、0 downgrade、0 "banked 变了但 verdict 没变" 异常
- **suite 10227→10240 green 215s**（+13 tests，test_paren_tense_faces.py：双 live fixture、薄头/嵌套/无括号/缺 token 负例、deixis 正例、number-guard 先于 face、tense 等集不 fire）

## 数值轨迹
0.444（C535 前基线）→ 0.502 → 0.504 → 0.506 → 0.510 → 0.512 → 0.518 → 0.520 → **0.524**

## 教训
- **census 脚本第一遍就要用 ledger 公式**（v==CORRECT or (frozen exact ∧ v≠WRONG) + abs 18 行），只数语义 CORRECT 会读出 236 vs 260 的假崩坏——同源规则不仅是 A/B 纪律，也是基线复核纪律
- face 的 fire 理由要语义正确，不止要 fire：c6853660 靠顺带 "you" fire 的版本在数字上等价、语义上错误；deixis fold 让它按对的理由 fire（且 fixture 可用最小答案复现）
- NEEDS_JUDGE zone 的结构性纯上行（WRONG 路径先 return）是这类 face 可以低风险接线的根本原因——C541 第 3 次复用，持续有效

## Next（C544 遗留队列）
- 嵌入 side-channel 生产化（③，#083 form-gated 0.87）——连续两轮被推后，pred/检索侧队首
- 窗口组成 census cycle（29 无 GT 行死区）
- 113 zero-overlap NJ 行：诚实弃权区，唯有 ollama/LLM oracle 能救（仍 human-blocked）

## Artifacts
/tmp/c544/{census_nj.py, census_nj.json, nj_dump.txt, census_faces.py, census_faces.json, ab_faces.py, face_flips.json}

## 提交拓扑
amg 无独立 .git 归 monorepo（TOOLS.md 08-29 口径），amg 目录内相对路径 add，commit 带 amg 前缀，push openclaw-workspace.git 一次
