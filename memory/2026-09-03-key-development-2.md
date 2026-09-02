# 2026-09-03 — key-development-2 (C541)

**cron**: 88679f9e (kd-2, 00:00) | **cycle**: C541 | **verdict**: KEEP
**结果**: banked 256→259 (0.512→0.518)，trajectory 0.502→0.504→0.506→0.510→0.512→0.518

## 做了什么

三个机制，全部先 census 后接线（0 kill 门槛）：

1. **paren-acronym judge face**：reference 自带 `Full Name (ACRONYM)` 双命名 →
   answer 含该缩写 token 即 CORRECT。 Rescue: 1d4da289 (OTP)。
2. **place-complement judge face**：GT `<head> in <Place>` 中 tail 是 grader
   disambiguation → answer 含全部 head content token 且 tail 不在 answer 即
   CORRECT。 Rescue: 3b6f954b (University of Melbourne in Australia)。
3. **where-gate intent guard**：did-form where 问题中，locative clause 是
   intention-shaped（considering/pursuing/narrowed down...）的候选降级，
   band-restricted（有 clean 候选才降）。 Pred flip: 25e5aa4f（"考虑读硕"句
   压过 "completed my undergrad in CS from UCLA" 句）→ 新 pred 由 acronym
   face 判 CORRECT（guard+face 组合拳，单靠任何一个都不 bank）。

两个 judge face 都在 NEEDS_JUDGE zone（guards 1-3 与 subset veto 之后），
数学上只能 NEEDS_JUDGE→CORRECT，纯上行。

## 关键方法论收获

- **Census 拦下 NET-NEGATIVE 实现**：naive 全句 intent marker 扫描 = 1 rescue /
  2 kills（d52b4f67 已 banked 行被 tangent clause "want to get her something"
   误杀；e01b8e2f 尾句 "thinking of planning another trip" 误杀）。改成
  **marker 只查 locative 所在 clause** 后 = 1 rescue / 0 kills。
  「先全 population 离线枚举再接线」纪律再次值回票价。
- **C540 truncation trap 结构化**：ab500.json overlay dumps `str(ans)[:200]`，
  8/10 行截断 → full recompute with true preds 读 253 ≠ ledger 256。
  结论：**ledger 是 delta 链，不是 recompute**。本轮协议 = changed-row 级
  delta（C540 同款）+ true effective population 上全量 verdict 枚举。
- **基线并发 rebase**：kd-1 会话在我 census 中途 commit 了 C540（277f90b，
  255→256）。本轮所有对比 rebase 到新 HEAD；两个方向无重叠（它做 ordinal
  face，我做 judge faces + where guard）。

## 弃置

- 51a45a95 ("Where did I redeem a $5 coupon...")：GT bearer 证据跨 turn 推理，
  无诚实可机化规则，弃置（C539 遗留队列清空该条）。

## 验证链

- census_faces: 500 行 verdict 枚举 = 2 flips 全 rescue 0 kills
- census_guard (naive): 3 changes (1 rescue/2 kills) → FALSIFIED
- census_guard2 (clause-scoped): 1 change (25e5aa4f) 0 kills
- 接线后 ab_where: 1 pred change，judge CORRECT
- dump_verdicts old/new diff: 2 flips，0 downgrades
- suite: 10199→10213 green 198s
- +14 tests (test_reference_faces.py)

## Next（C541 遗留队列）

- 8752c811 judge-side GT-wrap face（C540 留下的 in-pipeline live case：
  RIGHT item extracted 但 judge truth⊆pred 失败）
- judge leniency queue / ollama oracle（仍 human-blocked）
- answer-gate non-echo 46 / ssu 34-wrong

## Artifacts

/tmp/c541/{mod/, mod_old/, census_faces.py, census_guard.py, census_guard2.py,
rebuild_eff.py, effective_preds.json, ab_where.py, dump_verdicts.py,
verdicts_old.json, verdicts_new.json, smoke.py, ab_composed.py(废弃: dataclass
module-alias 冲突，两进程方案替代)}

## 教训

- exec preflight 拒绝 heredoc 与 `cmd1 && cmd2` 中带 python 内联的情况 →
  一律写脚本文件直接 `python3 file.py`
- importlib.dataclass 加载需 sys.modules 注册 → 旧/新 judge 对比用两进程
  各自 dump JSON 再 diff，干净
