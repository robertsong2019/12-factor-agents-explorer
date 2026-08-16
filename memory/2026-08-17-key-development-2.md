# Key Development Task 2 (Loop B) - 2026-08-17 00:00

## Focus: Autoresearch Experiment Loop B — Cycle 456 (build on C447/C455 state)

### Baseline at start
- 9354 tests (amg repo). The overnight state had advanced beyond my C447: C448 entropy gate, C449-450 residuals/forget, C451 LoCoMo adapter, C452+455 gate negatives, C453 LoCoMo full baseline, C454 LME_s x50 + run_eval
- Project: projects/agent-memory-graph

### Attempt 1 — digit keyword seeds (REVERTED, decisive negative)
Hypothesis: `_keywords` regex `[A-Za-z']+` drops years → temporal questions lose their discriminative token.
- Implemented: digit extraction both sides (question seeds + label tokens), years leading seeds; 8 tests, 9362 pass
- A/B: LoCoMo turn 0.650→0.644, temporal turn 40→37/96; LME_s hit 0.780→0.760. **Falsified.**
- Root cause of failure: only **9/96 "temporal" cat-3 questions carry digits** — cat 3 is counterfactual "would"-questions; real when-questions (252) live in **cat 2 (multi_hop)** and dates live in *truths/evidence text*, not questions
- Lesson: temporal weakness is **answer-side**, not retrieval-side. Reverted clean (9354 verified).

### Attempt 2 — when-question date resolution (RETAINED ✅)
Data-grounded mechanism (verified in raw data): evidence says "I went ... **yesterday**", truth "7 May 2023" = session_1 date "8 May, 2023" − 1 day. Multi-hop: message → session → absolute date.

**Implementation (locomo_bench_quality.py, +17 tests, 9371 total):**
| Component | Role |
|-----------|------|
| `extract_dates`/`date_canon` | D-Mon-Y / Mon-D-Y / ISO / M-D-Y grammar → canonical YYYY-MM-DD, dedup |
| `_relative_days` | day-precision offsets only (yesterday/today/tomorrow/last night/last week/next week/N days·weeks ago); month/year relatives skipped (no honest day-precision) |
| `answer_temporal` | rank-order scan; subject match **includes [Speaker] prefix** (speaker IS the subject evidence); absolute-before-relative; subject-less trust only at rank 0 (fabrication guard) |
| `temporal_judge` | canonical date equality + bare-year overlap (finditer full-match — findall-with-groups "2019"/"2023"→both {"20"} bug caught), containment fallback |
| trigger `_WHEN_RE` | **past/eventive when-forms only** ("when did/was/were", "what year/date"); habitual "when is" keeps extractive path; category-agnostic |
| ingest wiring | `session_N_date_time` → `_session_dates`; `_node_session` map (D1:3 → session 1) |

### Debug lessons this cycle
1. **findall-with-groups year bug**: `re.findall(r"\b(19|20)\d{2}\b")` returns "19"/"20" prefixes — "2019" and "2023" both collapse to {"20"}. Use finditer + group(0).
2. **Speaker prefix is subject evidence** — stripping `[Caroline]` before subject matching breaks speaker-subject questions
3. **Habitual vs eventive "when"** — "When is the class?" (Tuesday) vs "When did she go?" (date); grammar distinction prevents date fabrication
4. **LoCoMo category labels mislead**: cat 3 "temporal" = counterfactuals; when/date questions = cat 2 multi_hop (252/321). Trigger on question FORM, not category.
5. **Month-year without day** ("June 2019") must NOT parse as full date — no honest day precision

### 📊 Results (A/B LoCoMo 10-sample, 1986q)
- **multi_hop 4/321 → 42/321 (10.5×)**; overall no-adv accuracy **0.1032 → 0.1266 (+23%)**
- Retrieval unchanged (sess 0.851), abstention unchanged (0.067), tokens 824→827
- Costs: open_domain 150→148 (−2), turn 0.650→0.647 (noise)
- `--no-dates` reproduces C453 exactly (4/321) — clean attribution
- Committed `be86830` + records `84a00a5`, **pushed ✅**

### ✅ Decision: RETAIN
Incremental over the C455 state: ✅ first double-digit multi_hop accuracy axis; ✅ date-resolution is a NEW answer-side capability class (joins abstention C448); ✅ session-date grounding via node→session graph path is amg-native (no competitor reports this mechanism).

### 🔮 Next Steps
1. Non-date multi_hop questions (≈89/321 remain) — the 42-correct set covers date truths; residual gap = synthesis questions → LLM judge territory
2. Cross-validate date resolution on LME_s (temporal category there) via run_eval adapter path
3. open_domain −2 regression: inspect the 7 when-form open_domain triggers, maybe require evidence-turn adjacency
4. Blog candidate: "multi-hop date resolution without an LLM" (graph-native temporal composition)

---
**Generated**: 2026-08-17 00:55
**Status:** ✅ Complete — 9371/9371 tests, commit be86830, pushed
**Baseline**: 9354 → 9371 (+17 tests) + multi_hop 4→42/321 — ≥1 incremental improvement ✅
**Milestone:** 295th day; Cycle 456; Loop B ran the full autoresearch arc: hypothesis → falsify → revert → data-grounded pivot → retain
