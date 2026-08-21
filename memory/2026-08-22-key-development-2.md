# C495 — Loop B (key-development-2), 2026-08-22

## 结果

**keep**（commit `de00540`，基线 C494 `e8e6d33`）

| 指标 | C494 | C495 | Δ |
|------|------|------|---|
| first-family-30 | 16/30 | **23/30** | +7/−0 |
| temporal-133 | 68/133 (0.511) | **75/133 (0.564)** | +7/−0 |

7 个 win（两 slice 一致，零回归）：`70e84552`（修栅栏）、`b4a80587`（prime lens）、`8c8961ae`（泰国独自旅行）、`78cf46a3`（手机壳）、`1a1dc16d`（与 Rachel 会面）、`2f584639`（相册，计划外 win）、`213fd887`（排球联赛）。

## 改动（amg_bench_quality.py pairwise 区，+185/−41）

1. **F3 从句粒度窗口**：`_pw_hit_windows` 窗口锚在任何 kw-hit 从句（v1 只锚 full-kw 从句）±1 桥接 → 同位语证据 "Rachel, who I had a meeting with on April 10th"。
2. **F1 跨行 join**：同 session 相邻行各贡献 ≥1 kw 组、拼接后 full-match 才建锚；**部分匹配行也可作 join 起点**（补全方常是非匹配行，8c8961ae 的 [148]/[149]）。
3. **F5 planning 豁免**：kw-scoped planning veto + 从属/相对从句过去式豁免（`_PW_SUB_RE`：since/because/after/when + eventive；that/which/who + got/bought/…）→ "planning to buy a charger, **since I lost** my old one"、"lens **that I got** a month ago"（在 'interested in' 下）。
4. **F4 目的从句剪枝**：`_PW_PURPOSE_RE` 截断候选尾巴 "charity 5K run **to raise money**" → kws 不含 raise/money。
5. **eventive 扩词**：`\bwent\b`（裸，"went on a two-week trip"）、`\bdid (a|it|my|the)\b`（非裸 did，问句安全）、`had a meeting`。
6. **verb map**：`take → (took, went)`——"which trip did I **take** first" 的证据是 "went on a trip"（qv 一致性曾挡住 8c8961ae 的 A 侧 join）。
7. **'trip' 入 _PW_FRAME_STOP**；`_pw_any_mention` 跨行版（neg-exist 门，不做 planning veto——设计如此）。
8. **weak-kw guard**：跨行 join 的相对日期拉伸必须落在含**本候选独有** kw 的从句（`_weak` = 与对方共享的组 ∪ `_PW_GENERIC` 通用名词集）；否则退回 session clock。救回 `c27434e8`（'model' 仅因 words[:4] 截断而共享，Ferrari −21d 拉伸被拒，sub-24h-tie 保持）。

## 过程教训

- **proto v1 教训**：v2 初版把 fresh 行也要求 eventive → 6 处回归。修复后严格 **v1-exact 分层复制**（fresh 行无 eventive 直接锚）再做增量——重构时先复制原语义再改。
- **双 slice 同进程 OOM**（23% mem 被 SIGTERM）：A/B 改为**每臂一进程**（arm.py + tag），stdout 缓冲也要 flush=True。
- 原型 census 的快速 judge 有假阴性（78cf46a3 "their vs the"），官方 judge 确认 7 win——**结论必须以官方 A/B 为准**。
- monkeypatch 自引用递归（`B._pw_kws` 指向自身）：patch 前先存 `_orig`。

## 残余（first-family 30 → 7 wrong）

- `2312f94c`、`0b2f1d21`：同 session tie，分钟级也不可分——放弃。
- `6ed717ea`（Luna puppy）：B 侧 mention 现在能跨行找到（neg-exist-B→B-unanchored），但锚仍未建立；需 nominal-possession 锚（"my new puppy"）。
- `98f46fc6`、`68e94287`、`76048e76`、`7de946e7`：multi-sentence 证据墙 + neither 族，下轮候选。
- `2d58bcd6`、`483dd43c`：sub-24h-tie（真同日双事件）。

## 工件

- A/B：/tmp/c495/{arm.py, amg_base.py, firstfam_{base,cur}.json, temporal133_{base,cur}.json}
- 原型：/tmp/c495/{proto.py, census_v2.json, form_census.json, dbg.py}
- experiments.tsv：`2026-08-22T00:55+08 de00540 temporal-133 75/133=0.564 keep`
