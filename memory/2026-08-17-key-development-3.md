# Key Development Task 3 (Loop C) - 2026-08-17 01:00

## Focus: Autoresearch Experiment Loop C — Cycle 457 (build on key-development-2's C456)

### Baseline
- 9371 tests (Cycle 456: when-question date resolution in locomo_bench_quality.py, key-dev-2's be86830), 296th day
- Built on key-development-2's own Next Step #2: "Cross-validate date resolution on LME_s"
- Baseline verified before changes: targeted 143 pass; full suite at end 9406/9406 (122s)

### 🔍 Data reconnaissance (prototypes BEFORE code — the decisive step)
LME_s "temporal-reasoning" (133/500) questions are **NOT when-questions** — C456's mechanism does not transfer directly. They are:
- **Duration arithmetic** (67): "How many days passed between X and Y?", "How many weeks ago did I X?", "How many months have passed since X?"
- **Event ordering** (30+): "Which event happened first, X or Y?" + variants ("Who did I meet first, A or B?")
- Skipped: ordering-lists, "how long had I been" state durations, "days before X did Y" (prototype 0/6 — falsified, dropped)

**The unlock**: dataset ships structured grounding — `question_date` + `haystack_dates[j]` (one ISO date per session). Duration = calendar arithmetic on anchor session dates, zero LLM.

Prototype 1 (full-haystack scan): between 7/9, ago 14/21, first 5/7 correct. Prototype 2 (generalized first-form): 13/18 correct. Decided scope BEFORE touching the module.

### 🛠 Implementation (amg_bench_quality.py, +35 tests)
| Component | Role |
|-----------|------|
| `parse_lme_date` | "2023/02/01 (Wed) 10:20" → canonical YYYY-MM-DD |
| `temporal_arith_form` | form-triggered (C456 lesson 4: category labels untrusted), between/ago/since/first |
| `answer_temporal_arith` | anchors resolved by **inflection-tolerant keyword hits over RETRIEVED dated lines only**; falls through (None, no fabrication) on unresolved anchor / same session / anchor-after-ask-date |
| `duration_units` | exact days/weeks; calendar-month arithmetic with half-month rounding |
| `temporal_arith_judge` | multi-gold integer match (dataset: "7 days. 8 days also acceptable"); either-direction keyword containment for first-form |
| wiring | `ingest_sessions(session_dates=)` + run_eval positional haystack_dates map; `--no-temporal-arith` reproduces pre-C457 |

Runs BEFORE the C447/C448 gate chain in answer_extractive; unresolved forms fall through to gates untouched — abstention behavior fully preserved.

### Debug lessons this cycle
1. **Prototype before module** — two throwaway scripts over the raw dataset falsified form-D and validated 3 forms in <10 min, before writing any real code
2. **Expectation arithmetic again**: calendar months Dec-01→Jan-20 = 2 not 1 (compute with the code, C448 lesson #1 repeats); "7 days." does not contain gold 8 — the multi-gold string must actually be in the truth
3. **A/B lost-question forensics**: the 1 lost question had gate≠temporal_arith and identical code path in both arms → retrieval nondeterminism (noise), not a regression — worth checking before blaming the new path
4. **Python sys.path gotcha**: `python3 /tmp/script.py` puts /tmp (not cwd) on sys.path — insert repo path explicitly in bench scripts

### 📊 Results (A/B, full temporal-reasoning slice, 133q, 271s/arm)
- **Accuracy 0.045 → 0.180 (4.0×)**, won 19 / lost 1
- temporal_arith fired 28/133, 19 correct (68% precision on fired)
- retrieval_hit 0.211→0.218, abstention 1.5%→0.8%, tokens 3726→3737 — all noise
- Slice hit-rate structurally low (0.21 vs 0.78 overall): duration truths ("7 days") never appear verbatim — the path needs anchor SESSIONS retrieved, not verbatim answers
- 9371 → **9406 tests** (+35), zero regressions; committed `ff02a43` + records `5a7421f`, **pushed ✅**

### ✅ Decision: RETAIN
Incremental over key-development-2 (C456): ✅ cross-dataset generalization of the date-grounding mechanism family (LoCoMo → LME_s); ✅ NEW answer-side capability class — date ARITHMETIC (grounding → resolution → arithmetic); ✅ 4.0× on the target category; ✅ no-fabrication fall-through keeps abstention path intact.

### 🔮 Next Steps
1. **Full-500 LME_s run** with temporal-arith on (~20 min) → new overall accuracy reference for 8月底 (expected ~+3.6pp from this slice alone)
2. Fired-but-wrong forensics: 9 questions fired and missed — anchor mis-resolution (session of MENTION vs session of EVENT is a real confound worth one cycle)
3. LoCoMo multi_hop residuals (≈89/321 non-date) + LME_s remaining forms (ordering-lists, "how long had I been") — both likely need LLM judge; candidate for the full-mode milestone
4. Blog candidate upgrade: "temporal arithmetic without an LLM" now spans two datasets and three mechanism generations (C456/C457)
