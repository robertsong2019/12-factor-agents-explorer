# Key Development Task 2 (Loop B) - 2026-08-19 00:00

## Focus: Autoresearch Experiment Loop B — Cycle 472 (build on C465→C471 arc, esp. C471 anchor hygiene)

### Baseline at start
- 9565 tests (C471: anchor hygiene, fire precision 0.774, exact 0.226 on temporal-133), 296th day
- Project: projects/agent-memory-graph; targeted suites verified green before changes (222 pass)

### 🔍 Forensics before code (C457's decisive step, third consecutive cycle)
Ran form-level forensics on all 133 temporal questions (window + full-haystack anchor resolution, /tmp/c472_forensics.json + c472_missed.json). Taxonomy of the 102 wrong-answered:

| Bucket | n | reading |
|---|---|---|
| fired (temporal_arith gate) | 31 (24 correct) | C471's turf, untouched |
| form-matched but failed | 37 (4 lucky-correct via fallback) | **the target** |
| form-missed (regex None) | 63 | 9 how_long / 17 how_many_other / 34 other — future work |
| abstained | 2 | honest |

Phase 2 on the 37: full-haystack resolution **rescues exactly 6 (6/6 correct)**; 31 are a lexical wall (anchor entities never appear verbatim — e.g. question says "Samsung Galaxy S22"/"Dell XPS 13", haystack only says "my new phone"/"the new laptop" — entity aliasing, zero-LLM wall).

**Root-cause surprise**: the 6 were NOT "anchor line missing from window" (my phase-1 bucket label) — the anchors resolved `[true,true]` in-window but onto **mirror/advice lines** (assistant chit-chat lexically echoing the question, e.g. "What a great experience! The Museum of Modern Art (MoMA) is an iconic institution…") that collapse BOTH anchors onto one wrong session → same-session geometry → None. First A/B with a narrow "missing-anchor-only" fallback condition: **+0/0 — didn't fire at runtime.** Debug trace of gpt4_59149c77 exposed the real mechanism; broadened the condition to any form-matched window-None.

### 🛠 Implementation (amg_bench_quality.py, surgical)
`answer_extractive` temporal branch: extract `_dated(nids)` helper; when `t_ans is None and form matched` → retry `answer_temporal_arith` over **ALL ingested messages** (`self._messages`), flag `detail["fallback"]="full_graph"`. Window-first preserved: an in-window answer is never re-guessed; walls persisting on full graph still fall through (verified: the 4 prev-correct same-session cases stay None on full retry — zero-flip by construction AND by data).

Tests: +9 (`test_temporal_fallback.py`) — between/ago/first fallback fires, window-first no-flag, lexical-wall fall-through, same-session wall persists, disabled path, no-dates skip, faithful same-session-collapse-rescued fixture. Fixture lesson: synthetic advice-mirror lines fail to reproduce real ranking (later-date tie-break still prefers them); the faithful fixture needs the window's top line to mirror the WHOLE question while true event lines win on user-role/past-aspect only in the full search. 9565→**9574**, zero regressions (121s).

### 📊 A/B (133q, C467 config, /tmp/lme_s_temporal133_c472.json, 281s)
- **exact 0.226 → 0.271 (30→36/133), fired 31→37, +6 gained / 0 lost**
- The 6: MoMA 7d, keyboard 6d, herb-garden 24d, gardening 6d, Farmers-Market 3w, bike 4d — exactly the forensics-predicted set, all correct
- Commit 497f547 + records f3867bd, pushed ✅

### Debug lessons this cycle
1. **Forensics bucket labels can lie about mechanism** — "anchor_missed" (anchors False) vs reality (anchors True-True on WRONG lines). The A/B's +0 was the tell: predicted +6, got 0 → trace one question before touching the condition again. Cheap sanity: run the new code path on ONE known-rescuable question before the 4-minute A/B
2. **Mirror lines are the temporal window's systematic poison** — assistant advice that echoes question entities ranks top (hits the most question keywords) and collapses both anchors onto one session. Retrieval ranking cannot fix this (the mirror line IS the best lexical match); only evidence-scope escalation (full-graph retry) breaks the artificial tie
3. **Synthetic fixtures don't reproduce tie-ladder dynamics** — design them around the contract (window fails / full succeeds), not around imitating real line text; verify with the real adapter trace first

### ✅ Decision: RETAIN
Incremental over C471: ✅ temporal-133 exact +0.045 (6 questions) with zero per-question regressions; ✅ new failure taxonomy of the remaining 96 wrong (31 lexical wall / 63 form-missed) sets up C473+; ✅ window-first escalation pattern (evidence-scope retry) is reusable for other form families. 9574/9574, pushed.

### 🔮 Next Steps
1. **form_missed 63q**: 9 "how long did it take me to…" (duration-of-activity — event-end minus event-start, same-session granularity wall?) + 17 how_many_other + "when did I…" — each needs its own form regex + forensics; the how_long family is the largest coherent group
2. **B-bucket abstention** (C471 #072 leftover): fired-wrong questions with no date-bearing anchor lines should abstain instead of answering (entropy-gate generalization to the answer side) — small, pairs with any C473
3. Lexical wall 31q = documented zero-LLM boundary (entity aliasing); cite in README priority map
4. Full-500 rerun after 2-3 more temporal cycles to refresh the C466/C467 reference tables (temporal exact will move 0.180→~0.226+ on full-500)

---
**Generated**: 2026-08-19 01:05
**Status:** ✅ Complete — 9574/9574 tests, commits 497f547/f3867bd, pushed
**Baseline**: 9565 → 9574 (+9 tests) + temporal-133 exact 0.226→0.271 (+6/0) — ≥1 incremental improvement over C471 ✅
**Milestone:** Cycle 472; Loop B arc: forensics taxonomy → mechanism correction (same-session collapse, not missing anchors) → window-first full-graph retry → decisive A/B. 296th day, 零回滚
