"""Cycle 529 tests — semantic judge layer (Research #090/#092).

judge_semantic(): deterministic semantic-equivalence ladder with
false-pass guards (number-signature veto, currency conflict,
asymmetric containment). judge_cascade(): NEEDS_JUDGE → LLM
fallthrough. judge_ab_report(): #092 A/B statistics (discordant
counts + McNemar exact + Cohen's kappa, per category). Plus
judge_mode="semantic" wiring through evaluate()/run_eval().
"""

import math

import pytest

import amg_bench_quality as abq
from amg_bench_quality import (
    cohens_kappa,
    judge_ab_report,
    judge_cascade,
    judge_semantic,
    mcnemar_exact,
)

NJ = "NEEDS_JUDGE"


# ── judge_semantic: credit ladder ────────────────────────────────

@pytest.mark.parametrize("ref,cand", [
    ("teal", "Teal"),                       # case-insensitive exact
    ("1,250 followers", "1250 followers"),  # separator normalization
    ("January 5, 2023", "Jan 5th 2023"),    # date fold
    ("23rd of March 2019", "March 23, 2019"),
    ("two hours", "120 minutes"),           # time-unit conversion
    ("three weeks", "21 days"),
    ("$56,355", "56355 dollars"),           # same-domain currency
    ("blue", "blue is his favorite color"),  # superset (official rule)
    ("Sarah", "Sarah and her sister"),      # superset of persons
    ("photography", "photography and hiking"),  # superset w/ extra
])
def test_semantic_credits(ref, cand):
    assert judge_semantic("q?", cand, ref) == "CORRECT"


# ── judge_semantic: false-pass guards ────────────────────────────

@pytest.mark.parametrize("ref,cand", [
    ("7", "17"),                        # number-signature veto
    ("1300", "1250"),                   # near-miss number
    ("March 2019", "March 2020"),       # year mismatch veto
    ("two hours", "three hours"),       # duration mismatch
    ("$5", "5 euros"),                  # currency-domain conflict
    ("table tennis", "tennis"),         # weaker candidate (asymmetry)
])
def test_semantic_vetoes(ref, cand):
    assert judge_semantic("q?", cand, ref) == "WRONG"


def test_semantic_veto_beats_containment():
    """exact_judge passes '7' ⊂ '17' (substring containment); the
    semantic number-signature guard vetoes it — cascade can LOSE vs
    exact on such rows, which is exactly what the A/B McNemar
    measures. Feature, not bug: documented in the section header."""
    assert abq.exact_judge("q?", "7", "17") is True
    assert judge_semantic("q?", "17", "7") == "WRONG"


# ── Cycle 529 census fixes: disjoint-intersection veto + exact-number face ─

def test_veto_allows_superset_with_shared_number():
    """C529 audit: superset candidates legitimately carry extra numbers.
    GT '16GB' answered with a full laptop spec listing (16 + 5000 +
    2018...) — shared number → no veto → superset credit."""
    assert judge_semantic(
        "How much RAM?", "I have 16GB RAM and a 5000 series GPU",
        "16GB") == "CORRECT"


def test_veto_still_kills_disjoint_numbers():
    assert judge_semantic("q?", "17", "7") == "WRONG"
    assert judge_semantic("q?", "1300", "1250") == "WRONG"


def test_exact_number_answer_face():
    """Bare/equivalent numeric answer is the precise form of a verbose
    reference (norm folds five→5), not a weaker one."""
    assert judge_semantic("How long?", "140", "140 hours") == "CORRECT"
    assert judge_semantic("How many kits?", "5",
                          "I have worked on or bought five model kits") == "CORRECT"


def test_weak_veto_survives_for_non_numeric():
    """The exact-number face exception must not reopen the tennis hole."""
    assert judge_semantic("Sport?", "tennis", "table tennis") == "WRONG"


# ── Cycle 531: either/or answer-face rescue (question-conditioned) ──

def test_either_or_answer_face_rescue():
    """C531 census: the blanket subset veto fired twice on the official
    cascade-500, both false kills. When the QUESTION offers exactly two
    alternatives, a candidate that verbatim-names one of them is the
    complete answer (gpt4_98f46fc6: 'the charity bake sale' vs 'I
    participated in the charity bake sale first.') — the textual
    analogue of the exact-number face, keyed off the question."""
    assert judge_semantic(
        "Which event did I participate in first, the charity gala or "
        "the charity bake sale?",
        "the charity bake sale",
        "I participated in the charity bake sale first.") == "CORRECT"


def test_either_or_rescue_guards():
    """The rescue must not fire outside its scope: undecided reference
    (names both alternatives), negated reference, or questions offering
    more than one 'or' stay vetoed."""
    q = ("Which event did I participate in first, the charity gala or "
         "the charity bake sale?")
    cand = "the charity bake sale"
    # reference mentions both alternatives → a guess, not an answer face
    assert judge_semantic(
        q, cand,
        "I attended both the charity gala and the charity bake sale.") == "WRONG"
    # negated reference stays vetoed
    assert judge_semantic(
        q, cand,
        "I did not participate in the charity bake sale first; "
        "the gala came first.") == "WRONG"
    # multi-or question → no rescue
    assert judge_semantic(
        "Which came first, the gala or the bake sale or the raffle?",
        "the bake sale", "the bake sale came first") == "WRONG"


def test_narrative_abbreviation_rescued_by_marker_subsequence():
    """C532 — conscious update of the C531 spec anchor: the principled
    formulation now exists. A narrative answer that shares the reference's
    discourse-marker skeleton (first/then/finally...) and whose every
    segment is an in-order token subsequence of the corresponding
    reference segment is the SAME narrative, abbreviated — not a weaker
    subset. gpt4_45189cb4: the candidate merely drops the verbose filler
    ("I attended a ... at the Staples Center") around each event."""
    assert judge_semantic(
        "What is the order of the sports events I watched in January?",
        "First NBA game, then College Football National Championship "
        "game, finally NFL playoffs",
        "First, I attended a NBA game at the Staples Center, then I "
        "watched the College Football National Championship game, and "
        "finally, I watched the NFL playoffs.") == "CORRECT"


def test_marker_subsequence_guards():
    """The rescue fires only on the full skeleton + aligned segments:
    dropped events (marker missing), reordered events, foreign tokens,
    non-order questions, single markers and pre-marker preambles all
    stay vetoed (event-skipping partial answers are the population the
    subset veto exists for — C531's reason for pinning the debt)."""
    q = ("What is the order of the sports events I watched in January?")
    ref = ("First, I attended a NBA game at the Staples Center, then I "
           "watched the College Football National Championship game, and "
           "finally, I watched the NFL playoffs.")
    # event skipped: marker skeleton 'first, finally' != 'first, then, finally'
    assert judge_semantic(
        q, "First NBA game, finally NFL playoffs", ref) == "WRONG"
    # reordered events: segment alignment fails (NFL not in ref seg 1)
    assert judge_semantic(
        q, "First NFL playoffs, then College Football National "
           "Championship game, finally NBA game", ref) == "WRONG"
    # foreign token in a segment: not an abbreviation of that segment
    assert judge_semantic(
        q, "First NBA playoffs, then College Football National "
           "Championship game, finally NFL playoffs", ref) == "WRONG"
    # non-order question: no marker face, plain subset veto
    assert judge_semantic(
        "What did I watch in January?",
        "First NBA game, then College Football National Championship "
        "game, finally NFL playoffs", ref) == "WRONG"
    # single marker: no skeleton to align
    assert judge_semantic(
        q, "First NBA game", ref) == "WRONG"
    # pre-marker preamble on the candidate: skeleton must start clean
    # (verdict falls out of the subset branch — guard property is
    # "no rescue", either WRONG or honest NEEDS_JUDGE)
    assert judge_semantic(
        q, "On monday first NBA game, then NFL playoffs, finally "
           "nothing else", ref) != "CORRECT"


# ── judge_semantic: honest abstention ────────────────────────────

@pytest.mark.parametrize("ref,cand", [
    ("she planned it herself", "Rachel"),   # zero-overlap paraphrase
    ("jazz", "rock music"),                 # entity/genre substitution
    ("Sarah", "Rachel"),                    # entity substitution —
    # lexically undecidable (both names), only world knowledge or an
    # LLM can resolve; vetoing here would murder paraphrase recall
])
def test_semantic_abstains(ref, cand):
    assert judge_semantic("q?", cand, ref) == NJ


def test_semantic_empty_conventions():
    assert judge_semantic("q?", "anything", "") == "CORRECT"
    assert judge_semantic("q?", "", "teal") == "WRONG"


# ── judge_cascade ────────────────────────────────────────────────

def test_cascade_passes_semantic_verdict_through():
    calls = []

    def llm(q, a, r, **kw):
        calls.append((q, a, r))
        return "CORRECT"

    assert judge_cascade("q?", "17", "7", llm_fn=llm) == "WRONG"
    assert judge_cascade("q?", "teal", "teal", llm_fn=llm) == "CORRECT"
    assert calls == []  # LLM never consulted on decidable pairs


def test_cascade_falls_through_on_needs_judge():
    def llm(q, a, r, **kw):
        return "WRONG"

    assert judge_cascade("q?", "Rachel", "she planned it herself",
                         llm_fn=llm) == "WRONG"


def test_cascade_default_is_judge_llm(monkeypatch):
    seen = {}

    def fake_judge_llm(q, a, r, **kw):
        seen["args"] = (q, a, r)
        return "CORRECT"

    monkeypatch.setattr(abq, "judge_llm", fake_judge_llm)
    out = judge_cascade("Who planned?", "Rachel",
                        "she planned it herself")
    assert out == "CORRECT"
    assert seen["args"] == ("Who planned?", "Rachel",
                            "she planned it herself")


# ── statistics: kappa / mcnemar ──────────────────────────────────

def test_kappa_perfect_and_chance():
    assert cohens_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    assert abs(cohens_kappa([1, 1, 0, 0], [1, 0, 1, 0])) < 1e-9


def test_kappa_shrinks_vs_raw_agreement():
    pred = [1] * 90 + [0] * 10
    oracle = [1] * 85 + [0] * 5 + [1] * 5 + [0] * 5
    raw = sum(1 for a, b in zip(pred, oracle) if a == b) / 100
    k = cohens_kappa(pred, oracle)
    assert abs(raw - 0.90) < 1e-9
    assert 0.40 < k < 0.50  # Research #092: raw 0.98 → κ shrink 33-41pp


def test_mcnemar_exact_pvalues():
    assert abs(mcnemar_exact(10, 1) - 2 * 12 / 2048) < 1e-12
    assert mcnemar_exact(5, 5) == 1.0
    assert mcnemar_exact(0, 0) == 1.0
    assert math.isclose(mcnemar_exact(0, 9), 2 * 1 / 512)


# ── judge_ab_report ──────────────────────────────────────────────

def _rows(pairs, cats=None):
    return [{"correct_exact": e, "correct_llm": c,
             "category": (cats[i] if cats else "cat")}
            for i, (e, c) in enumerate(pairs)]


def test_ab_report_counts_and_verdict():
    # 3 rescues (0→1), 1 loss (1→0), 4 agree; b=3 c=1 → p = 0.625 n.s.
    pairs = [(0, 1), (0, 1), (0, 1), (1, 0), (1, 1), (0, 0), (1, 1), (0, 0)]
    rep = judge_ab_report(_rows(pairs))
    assert rep["scored"] == 8
    assert rep["agree"] == 4
    assert rep["cascade_only_correct"] == 3
    assert rep["cascade_only_wrong"] == 1
    assert rep["verdict"] == "n.s."
    assert rep["by_category"]["cat"]["mcnemar_p"] == rep["mcnemar_p"]


def test_ab_report_significant_cascade_win():
    # 9 rescues, 0 losses → McNemar p = 2/512 < 0.05
    pairs = [(0, 1)] * 9 + [(1, 1)]
    rep = judge_ab_report(_rows(pairs))
    assert rep["verdict"] == "cascade>exact"
    assert abs(rep["mcnemar_p"] - 2 / 512) < 1e-12


def test_ab_report_exact_win_and_kappa_direction():
    # 0 rescues, 6 losses → exact>cascade
    pairs = [(1, 0)] * 6 + [(0, 0)]
    rep = judge_ab_report(_rows(pairs))
    assert rep["verdict"] == "exact>cascade"
    # anti-correlated judges → negative kappa (chance-corrected)
    assert rep["kappa"] < 0


def test_ab_report_error_rows_excluded_and_by_category():
    rows = [
        {"correct_exact": 1, "correct_llm": 1, "category": "kupdate"},
        {"correct_exact": 0, "correct_llm": 1, "category": "kupdate"},
        {"correct_exact": 1, "correct_llm": None, "category": "preference"},
        {"correct_exact": None, "correct_llm": 0, "category": "preference"},
    ]
    rep = judge_ab_report(rows)
    assert rep["scored"] == 2  # ERROR/None rows carry no pair evidence
    assert set(rep["by_category"]) == {"kupdate"}
    assert rep["by_category"]["kupdate"]["cascade_only_correct"] == 1


def test_ab_report_empty():
    rep = judge_ab_report([])
    assert rep["scored"] == 0 and rep["verdict"] == "n.s."
    assert rep["kappa"] == 0.0


def test_ab_report_matches_calibration_summary_counts():
    """calibration_summary's llm_only_* are the same discordant cells —
    the two lenses must never disagree on the raw counts."""
    pairs = [(0, 1), (1, 0), (1, 1), (0, 0)]
    cal = abq.calibration_summary(_rows(pairs))
    rep = judge_ab_report(_rows(pairs))
    assert cal["llm_only_correct"] == rep["cascade_only_correct"] == 1
    assert cal["llm_only_wrong"] == rep["cascade_only_wrong"] == 1


# ── evaluate()/run_eval() wiring ─────────────────────────────────

HAY1 = [{"session_id": "s1", "messages": [
    {"role": "user", "content": "My favorite color is teal."},
    {"role": "assistant", "content": "Noted, teal is a great color."},
]}]

SEM_Q = {"id": "sem1", "question": "What is my favorite color?",
         "answer": "teal", "haystack_sessions": HAY1}


def test_run_eval_semantic_mode_shape():
    rep = abq.run_eval([SEM_Q], judge_mode="semantic")
    assert rep["config"]["judge_mode"] == "semantic"
    assert rep["accuracy_exact"] == rep["overall_accuracy"]
    assert rep["accuracy_llm"] == 1.0  # teal/teal decided by semantic rung
    row = rep["results"][0]
    assert row["correct_exact"] is True and row["correct_llm"] is True
    ab = rep["judge_ab"]
    assert ab["scored"] == 1 and ab["verdict"] == "n.s."
    assert ab["by_category"]["single_session_user"]["scored"] == 1


def test_run_eval_semantic_abs_shares_verdict():
    q = {"id": "abs1", "question": "What is my favorite color?",
         "answer": "", "abstention": True,
         "haystack_sessions": [{"session_id": "s2", "messages": [
             {"role": "user", "content": "I like cats."},
         ]}]}
    rep = abq.run_eval([q], judge_mode="semantic")
    row = rep["results"][0]
    assert row["abstained"] and row["correct_llm"] == row["correct"]


def test_evaluate_semantic_uses_cascade_not_raw_llm(monkeypatch):
    """In semantic mode the LLM judge must run ONLY on NEEDS_JUDGE
    rows; a decidable pair never reaches judge_llm."""
    calls = []

    def fake_judge_llm(q, a, r, **kw):
        calls.append((q, a, r))
        return "CORRECT"

    monkeypatch.setattr(abq, "judge_llm", fake_judge_llm)
    adapter = abq.LongMemEvalAdapter()
    adapter.ingest_sessions(HAY1)  # run_eval ingests before evaluate()
    rep = adapter.evaluate([SEM_Q], judge_mode="semantic")
    assert rep["results"][0]["correct_llm"] is True
    assert calls == []  # teal vs teal decided deterministically


def test_cli_rejects_unknown_judge_choice():
    """--judge gained "semantic"; unknown values still exit 2."""
    with pytest.raises(SystemExit) as ei:
        abq.main(["--data", "nope.json", "--judge", "bogus"])
    assert ei.value.code == 2



# ── Cycle 530: judge backend fingerprint ────────────────────────

def test_run_eval_semantic_records_unconsulted_backend(monkeypatch):
    """Decidable-only dataset: judge_llm never called. The backend
    fingerprint must read 'unconsulted' regardless of prior state."""
    monkeypatch.setattr(abq, "_JUDGE_MODE", None)
    rep = abq.run_eval([SEM_Q], judge_mode="semantic")
    assert rep["config"]["judge_llm_backend"] == "unconsulted"


def test_run_eval_semantic_records_mock_backend(monkeypatch):
    """NEEDS_JUDGE row + dead endpoint: the sticky mock fallback must
    be visible in the report config — a mock-resolved run is NOT an
    oracle-resolved one (C530 cascade-500: 24 mock verdicts rode along
    unrecorded, inflating raw cascade 262/500 vs 246 bankable)."""
    monkeypatch.setattr(abq, "_JUDGE_MODE", abq._JUDGE_MODE)
    # simulate the post-probe degraded state (what a failed ollama
    # probe leaves behind: sticky _JUDGE_MODE = "mock")
    abq._JUDGE_MODE = "mock"
    monkeypatch.setattr(abq, "judge_semantic",
                        lambda *a, **k: "NEEDS_JUDGE")
    rep = abq.run_eval([SEM_Q], judge_mode="semantic")
    assert rep["config"]["judge_llm_backend"] == "mock"
    row = rep["results"][0]
    assert row["correct_exact"] is not None
    assert row["correct_llm"] is not None


def test_run_eval_exact_mode_has_no_backend_field():
    """exact mode never consults an LLM, so no backend field."""
    rep = abq.run_eval([SEM_Q])
    assert "judge_llm_backend" not in rep["config"]
