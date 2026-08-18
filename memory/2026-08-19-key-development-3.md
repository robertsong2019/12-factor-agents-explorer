# Key Development Task 3 (Loop C) - 2026-08-19 01:00

## Focus: Autoresearch Experiment Loop C — Cycle 473 (build on key-development-1/2's C467→C472 arc)

### Baseline
- 9574 tests (C472: temporal full-graph fallback, temporal-133 exact 0.271), 297th day
- Target from C467 Next Step #2: **single_session_assistant coverage 0.786 — the only sub-0.85 retrieval axis** (Loop B owns temporal; avoided collision)
- Full suite green before changes: 9574 (121s); targeted suites 105 pass

### 🔍 Forensics BEFORE code (C457 discipline, 4th consecutive cycle)
C467's 12 ssa evhit misses decomposed (/tmp/c473/ssa_forensics.json):
- **10/12 had `ev_in_candidates=0`** — evidence messages scored 7–16 keyword hits but NEVER entered the candidate set. All 12 were budget-packing to ~3.5k tokens with only 3–14 lines retrieved — the cut was upstream of ranking
- Root cause: three truncation layers — `recall()` is `ORDER BY weight DESC LIMIT 5` per keyword (ingest-weight order, question-blind), BM25 capped at 10, PPR seeds capped at 8. High-hit evidence lost at layer 1 by construction

### 🧪 Prototype sweep on the 12 misses
seed_recall_k 5→1/12, 12→5, 20→8, **40→10/12** — monotone. Full ssa-56 category: k=5 0.804 → k=20 0.911 → **k=40 0.946** evhit, exact 15→16.

### ❌ The falsified global variant (the cycle's decisive negative)
Global k=40 on temporal-133: **exact 36→14/133** (24 lost, only 6 form-matched). Mechanism: broad seeds feed MORE question-echoing mirror/advice lines into the window; anchors then resolve in-window onto wrong sessions → C472's full-graph retry never fires (window "succeeded") → wrong answers. Same C471 poison, injected by seed breadth. **Scope needed.**

### 🔑 The surgical unlock
`recall_form` (C468) matches **exactly 48/500 questions — every one ssa, zero in any other category**. Perfect partition → scope the breadth there and the rest of the benchmark is untouched BY CONSTRUCTION.

### 🛠 Implementation (amg_bench_quality.py, +5 tests test_seed_breadth.py)
`recall_seed_k: int = 40` ctor param + `k_eff = recall_seed_k if recall_form(question) else seed_recall_k` in `retrieve_context`; `run_eval` plumbs it. Fixture lesson applied (C472 #3): the rescue test neutralizes BM25/PPR to isolate the seed-stage truncation contract.

### 📊 Results
- **ssa-56 (official run_eval): evhit 0.786 → 0.929 (44→52/56)**, exact 0.268 held, abstain 0 (/tmp/c473/ssa56_official.json)
- **temporal-133: 36/133 (0.271), ZERO flips vs C472** — judge-corrected verification
- 9574 → **9579 tests**, zero regressions; commits `ac8d9a3` + `3e2476e`, **pushed ✅**

### Debug lessons this cycle
1. **A harness judge bug reads as a code regression** — my A/B used plain `exact_judge` on temporal answers; `evaluate()` routes temporal-gated answers through `temporal_arith_judge` ("7 days" ≈ "1 week"). Phantom 21-loss sent me chasing a mechanism my code couldn't have (recall_form matches 0 temporal questions). The `pre` == `c473` control exposed it: identical numbers under the "regressing" build = measure the measurement
2. **Reference tables age faster than benchmarks** — C467's ssa exact 0.018 predates C468's speaker-recall recovery (lost in the C469 checkout incident, restored in C470); current ssa exact is 0.268. When slices drift unexpectedly, check what cycles touched the code between reference and now
3. **Seed breadth is category-dependent poison/cure** — the same recall_seed_k=40 that rescues ssa (+8 evhit) destroys temporal (−22 exact). Retrieval hyperparameters cannot be tuned globally once answer paths have per-form window geometry (C471/C472 tuned at breadth 5); the form classifier IS the config surface

### ✅ Decision: RETAIN
Incremental over key-development-2 (C472) and C467's priority map: ✅ ssa coverage 0.786→0.929 — every retrieval axis now ≥0.87 except preference 0.567 (structural, C467); ✅ zero temporal impact verified judge-correct with zero per-question flips; ✅ the global-breadth negative + form-scoping pattern documented for the README priority map.

### 🔮 Next Steps
1. **ssa answer side** (56q, evhit 0.929 vs exact 0.268) — evidence retrieved, answer still wrong: C468 speaker-recall fires on how many? Same forensics playbook (bucket: recall-fired-wrong / min-score-fallthrough / non-recall 8q)
2. **multi_session counting forms** (133q, evhit 0.955 vs exact 0.007) — C467 #1, largest gap in the benchmark; how_many/listing forms over retrieved evidence lines
3. Preference 8/30 beyond 0.567 — ev_in_candidates forensics (same script, /tmp/c473) on the 13 pref misses
4. Full-500 rerun due after 1-2 more cycles (C467 reference now stale on ssa exact: C468/C473 both moved it)
5. Blog candidate upgraded: "one recall limit, two regimes" — breadth as cure (speaker evidence) vs poison (mirror lines), form-scoped retrieval config

---
**Generated**: 2026-08-19 02:05
**Status:** ✅ Complete — 9579/9579 tests, commits ac8d9a3/3e2476e, pushed
**Baseline**: 9574 → 9579 (+5 tests) + ssa-56 evhit 0.786→0.929 — ≥1 incremental improvement over C472 ✅
**Milestone:** Cycle 473; Loop C arc: C448 entropy gate → C457 temporal arithmetic → C467 evidence-coverage metric → C473 form-scoped seed breadth. 297 days, 零回滚
