# Key Development Task 2 (Loop B) - 2026-08-20 00:00

## Focus: Autoresearch Experiment Loop B — Cycle 482 (build on C471→C481 arc; C472's form_missed-63q target)

### Baseline at start
- 9620 tests (C481: full-500 reference refresh — exact 0.204, temporal 0.271), 297th day
- Project: projects/agent-memory-graph; targeted suites verified green before changes (124 pass)
- Note: key-development-1 cron retired (last memory 07-29); its arc continues via Loop B/C — this cycle directly consumed C481's fresh per-question reference

### 🔍 Forensics before code (C457 discipline, 5th consecutive cycle)
C481 reference: temporal 133 wrong = 97 → **63 form-missed** (C472 taxonomy confirmed on fresh data). Decomposed into coherent families (/tmp/c482/form_missed.json):

| family | n | mechanism reading |
|---|---|---|
| order ("what is the order of…") | 10 | multi-event chronological listing — needs N-anchor sort |
| before ("how many days before X did I Y") | 5 | **disguised `between`** — two anchors + calendar distance |
| past-perfect duration ("how long had I been X when Y") | 14 | state-start anchor + event anchor; unit inference needed for "how long" |
| other | 34 | heterogeneous |

Two risk checks BEFORE code: ① among the 36 correct temporal, exactly 2 are form-missed (gpt4_ec9 counting-claimed, gpt4_760 "first" via extractive) — neither matches the new regexes ✓ ② **17 of the 63 are claimed by counting's `d` mechanism, which fires WRONG numbers on 8 of them** (12w vs GT 3, 31d vs GT 4…) — session-count arithmetic on calendar questions. The temporal gate runs FIRST → claiming these questions back is displacement of wrong firings, zero-risk.

### 🔬 Trace-first (C472 lesson #1 applied)
Prototype monkeypatched `temporal_arith_form` (before/since-when → between) over the unmodified answer path: regexes matched, anchors resolved `[True,True]`, but ALL collapsed same-session (`dates=None`) — including cross-check questions already correct via window resolution. Trace of 0bb5a684 exposed the real granularity wall:

**"I'm glad I attended that workshop … on January 10th" + "team meeting on January 17th" — both lines in the SAME Jan-13 session. 17−10 = 7 = GT.** Day-level truth lives IN THE LINE TEXT; session dates collapse it. Same pattern confirmed on Rack Fest (Jun 18 vs Jun 14 in-text, session Jun 28). This is C471's "sub-session dates" bucket, now actionable.

### 🛠 Implementation (amg_bench_quality.py + test_in_text_dates.py, +19 tests)
1. `_TA_BEFORE_RE` / `_TA_SINCEWHEN_RE` → kind `between` (the C473 lesson: form classifier IS the config surface)
2. `_line_adverbial_date()`: extracts `on January 10th` / `on Jun 14` / `on the 3rd of March` / `on March 5, 2022`. **Dated nouns excluded by design** — "the March 15th issue of The New Yorker" carries an entity name, not an event time (regression guard: that question is currently correct via session arithmetic)
3. `best_line` ladder gains an `explicit-date` tier (after aspect, before date-later); arithmetic uses effective dates → **same-session rescues for between AND first forms**

### 📊 Three-round gate iteration (each round = full A/B, 282s)
- v1 (ungated): 42/133, +7/**−1** — reminder line "set up a reminder for Alex's graduation **on June 1st**" (March session, 76d future) hijacked anchor B via explicit-preference → 1w became 12w
- v2 (symmetric ≤14d gate): 39/133, +3/0 — zero losses ✓ but wrongly blocked 4 gains: Holi/Rachel/Walk-for-Hunger/router lines are **past recall** ("during Holi on March 7th" mentioned weeks later)
- v3 (**asymmetric gate**: near-or-past engages, only far-future blocked): **43/133 = 0.323, fired 37→53, +7/0** — all gains, zero losses

The 7: 4 new forms (before×3, since-when×1) + 3 existing-form in-text rescues (between×2 incl. Holi 21d, first×1 router). Verified per-question against C481.

### 🐛 Debug lessons this cycle
1. **The direction of a date is its trust signal** — future >14d in-text dates are plans/reminders (hijack anchors), past in-text dates are recall (true evidence), near dates either way are same-session truth. A symmetric window gate was half-wrong in both directions; the A/B's per-question diff caught both halves
2. **Fixture contracts beat fixture realism (C472 #3 reprise)** — my first regression fixture imitated the real question's surface text and diverged from its ladder dynamics (anchor A resolved elsewhere); rebuilt it around the discriminating contract (hits-tie → dated line wins → gate blocks → same answer)
3. **Counting's `d` mechanism owns questions it cannot answer** — 8 calendar questions fired wrong session-count numbers behind the temporal gate's leftovers. Gate ORDER is a correctness surface, not just a priority: when two form families overlap, the one with the right arithmetic must claim first

### ✅ Decision: RETAIN
Incremental over C481: ✅ temporal-133 exact 0.271→**0.323** (+7 questions, zero per-question regressions); ✅ fired 37→53; ✅ same-session day-granularity wall broken mechanism-wide (first-form rescued too); ✅ 9620→**9639 tests** (+19), full suite 122s green; commits `2d3d305` + `9d6443c`, pushed (also carried C475-C481 evening commits to remote).

### 🔮 Next Steps
1. **past-perfect duration family (14q)** — "how long had I been X when Y" needs state-start anchors (join/buy/start verb hints) + unit inference for unitless "how long" (GT "Two weeks"/"2 months"; judge needs word-number parsing); largest remaining coherent family
2. **order family (10q)** — N-anchor chronological sort; answer is a sentence listing — needs a listing judge
3. B-bucket abstention (C471 #072 leftover) still open; pairs with any C483
4. Full-500 rerun due ~C484 (temporal will move 0.271→0.323 on the reference; counting `d` questions now claimed by temporal — verify multi_session category stays 0.045)
5. Blog candidate upgraded: "the date was in the text all along" — session granularity vs line-stated dates, symmetric vs asymmetric trust gates

---
**Generated**: 2026-08-20 00:55
**Status:** ✅ Complete — 9639/9639 tests, commits 2d3d305/9d6443c, pushed
**Baseline**: 9620 → 9639 (+19 tests) + temporal-133 exact 0.271→0.323 (+7/0) — ≥1 incremental improvement over C481 ✅
**Milestone:** Cycle 482; Loop B arc: C457 temporal arithmetic → C471 anchor hygiene → C472 full-graph fallback → C482 in-text dates + disguised forms. 297th day, 零回滚
