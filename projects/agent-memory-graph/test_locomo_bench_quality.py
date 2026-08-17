"""Tests for locomo_bench_quality.py — LoCoMo adapter (Cycle 451).

Research #067 design promoted to the real repo. The fixture is a
mini-LoCoMo (2 samples / 3 sessions / dia_id evidence / all 5
categories) covering the behaviors the adapter must demonstrate:

* session→messages conversion with dia_id → node indexing
* adversarial questions scored by ABSTENTION (not retrieval)
* session-level AND turn-level evidence recall (dia_id precision)
* per-sample fresh graphs (no cross-sample leakage)
* cross-sample category aggregation in run_locomo
"""

import json

import pytest

import locomo_bench_quality as lbq
from locomo_bench_quality import (
    CATEGORY_NAMES,
    LoCoMoAdapter,
    _canon_to_day_month_year,
    _dia_session,
    answer_temporal,
    date_canon,
    extract_dates,
    load_locomo,
    main,
    run_locomo,
    temporal_judge,
)
from amg_bench_quality import LongMemEvalAdapter


# ---------------------------------------------------------------------------
# Fixture: mini-LoCoMo
# ---------------------------------------------------------------------------

def make_sample(sample_id="s1", second_session=True):
    conv = {
        "speaker_a": "Caroline", "speaker_b": "Mel",
        "session_1_date_time": "1:56 pm on 8 May, 2023",
        "session_1": [
            {"speaker": "Caroline", "dia_id": "D1:1",
             "text": "Hey Mel! I started pottery class last week."},
            {"speaker": "Mel", "dia_id": "D1:2",
             "text": "Nice! When is the class?"},
            {"speaker": "Caroline", "dia_id": "D1:3",
             "text": "Every Tuesday at the community center."},
        ],
    }
    qa = [
        {"question": "What class did Caroline start?",
         "answer": "pottery class",
         "evidence": ["D1:1"], "category": 1},
        {"question": "Where is the pottery class held?",
         "answer": "community center",
         "evidence": ["D1:3"], "category": 1},
        {"question": "When is Caroline's pottery class?",
         "answer": "Tuesday",
         "evidence": ["D1:3"], "category": 3},
        {"question": "Did Caroline ever go skydiving in Dubai?",
         "answer": "no",
         "evidence": [], "category": 5},
        {"question": "What hobby does Caroline enjoy?",
         "answer": "pottery",
         "evidence": ["D1:1"], "category": 4},
    ]
    if second_session:
        conv["session_2_date_time"] = "3:10 pm on 20 May, 2023"
        conv["session_2"] = [
            {"speaker": "Mel", "dia_id": "D2:1",
             "text": "How was pottery class this week?"},
            {"speaker": "Caroline", "dia_id": "D2:2",
             "text": "Great, I made a ceramic vase for my sister."},
        ]
        qa.append({"question": "What did Caroline make in pottery?",
                   "answer": "ceramic vase",
                   "evidence": ["D2:2"], "category": 1})
    return {"sample_id": sample_id, "conversation": conv, "qa": qa}


def make_sample2():
    s = make_sample("s2")
    s["conversation"]["speaker_a"] = "Tom"
    for m in s["conversation"]["session_1"]:
        m["speaker"] = "Tom"
    s["qa"] = [
        {"question": "What class did Caroline start?",
         "answer": "pottery class",
         "evidence": ["D1:1"], "category": 1},
        {"question": "Has Caroline ever visited Mars?",
         "answer": "no",
         "evidence": [], "category": 5},
    ]
    return s


def fresh_adapter(**kwargs):
    kwargs.setdefault("use_ppr", False)   # small fixture: no PPR noise
    return LoCoMoAdapter(**kwargs)


@pytest.fixture
def data_file(tmp_path):
    p = tmp_path / "locomo.json"
    p.write_text(json.dumps([make_sample(), make_sample2()]),
                 encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# CATEGORY_NAMES / _dia_session
# ---------------------------------------------------------------------------

class TestCategoryNames:
    def test_five_categories(self):
        assert CATEGORY_NAMES == {
            1: "single_hop", 2: "multi_hop", 3: "temporal",
            4: "open_domain", 5: "adversarial"}

    def test_dia_session(self):
        assert _dia_session("D1:3") == "S1"
        assert _dia_session("D12:45") == "S12"
        assert _dia_session("junk") == ""


# ---------------------------------------------------------------------------
# load_locomo
# ---------------------------------------------------------------------------

class TestLoadLocomo:
    def test_loads_and_counts(self, data_file):
        data = load_locomo(data_file)
        assert len(data) == 2
        assert data[0]["conversation"]["speaker_a"] == "Caroline"

    def test_limit_samples(self, data_file):
        assert len(load_locomo(data_file, limit_samples=1)) == 1

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_locomo(tmp_path / "nope.json")

    def test_not_a_list(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="expected JSON list"):
            load_locomo(p)

    def test_missing_keys(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps([{"qa": []}]), encoding="utf-8")
        with pytest.raises(ValueError, match="conversation"):
            load_locomo(p)


# ---------------------------------------------------------------------------
# ingest_sample + dia indexing
# ---------------------------------------------------------------------------

class TestIngestSample:
    def test_stats(self):
        ad = fresh_adapter()
        stats = ad.ingest_sample(make_sample())
        assert stats["sessions"] == 2
        assert stats["messages"] == 5
        assert stats["entities"] >= 2      # Caroline, Mel, ...

    def test_dia_nodes_indexed(self):
        ad = fresh_adapter()
        ad.ingest_sample(make_sample())
        assert set(ad._dia_nodes) == {"D1:1", "D1:2", "D1:3",
                                      "D2:1", "D2:2"}
        labels = {ad._messages[nid]["label"] for nid in
                  ad._dia_nodes.values()}
        assert any("pottery" in l.lower() for l in labels)

    def test_dia_maps_to_exact_text(self):
        ad = fresh_adapter()
        ad.ingest_sample(make_sample())
        node = ad._messages[ad._dia_nodes["D1:2"]]
        assert "When is the class?" in node["label"]
        assert node["role"] == "Mel"

    def test_session_ids_and_order(self):
        ad = fresh_adapter()
        ad.ingest_sample(make_sample())
        d11 = ad._messages[ad._dia_nodes["D1:1"]]
        d21 = ad._messages[ad._dia_nodes["D2:1"]]
        assert d11["session_id"] == "S1"
        assert d21["session_id"] == "S2"
        assert d11["seq"] < d21["seq"]      # insertion order kept

    def test_evidence_helpers(self):
        ad = fresh_adapter()
        ad.ingest_sample(make_sample())
        assert ad.evidence_sessions(["D1:3", "D2:1"]) == {"S1", "S2"}
        ids = ad.evidence_node_ids(["D1:1", "D9:9"])
        assert len(ids) == 1                 # D9:9 unknown → dropped
        assert ad._messages[next(iter(ids))]["label"].startswith(
            "Hey Mel")

    def test_empty_sample_noop(self):
        """No sessions → no-op (0 new nodes, empty dia map)."""
        ad = fresh_adapter()
        stats = ad.ingest_sample({"conversation": {"speaker_a": "x"},
                                  "qa": []})
        assert stats["sessions"] == 0
        assert stats["messages"] == 0
        assert ad._dia_nodes == {}


# ---------------------------------------------------------------------------
# retrieve_context: retrieved_ids (base-class C451 enhancement)
# ---------------------------------------------------------------------------

class TestRetrievedIds:
    def test_meta_has_retrieved_ids(self):
        ad = fresh_adapter()
        ad.ingest_sample(make_sample())
        ctx, meta = ad.retrieve_context("pottery class")
        assert meta["retrieved_ids"]
        assert all(nid in ad._messages for nid in meta["retrieved_ids"])

    def test_base_adapter_still_works(self):
        ad = LongMemEvalAdapter(use_ppr=False)
        ad.ingest_sessions([{"session_id": "s", "messages": [
            {"role": "u", "content": "hello world"}]}])
        ctx, meta = ad.retrieve_context("hello")
        assert "hello world" in ctx
        assert meta["retrieved_ids"]


# ---------------------------------------------------------------------------
# evaluate_sample
# ---------------------------------------------------------------------------

class TestEvaluateSample:
    def test_report_shape(self):
        ad = fresh_adapter()
        ad.ingest_sample(make_sample())
        r = ad.evaluate_sample(make_sample()["qa"])
        for key in ("overall_accuracy", "overall_accuracy_no_adversarial",
                    "abstention_rate", "session_hit_rate", "turn_hit_rate",
                    "avg_tokens", "total_questions", "categories",
                    "questions"):
            assert key in r
        assert r["total_questions"] == 6

    def test_adversarial_correct_iff_abstained(self):
        ad = fresh_adapter()
        sample = make_sample()
        ad.ingest_sample(sample)
        r = ad.evaluate_sample(sample["qa"])
        adv = [q for q in r["questions"] if q["category"] == "adversarial"]
        assert adv
        for q in adv:
            assert q["correct"] == q["abstained"]

    def test_factual_answer_scores_via_judge(self):
        ad = fresh_adapter()
        sample = make_sample()
        ad.ingest_sample(sample)
        r = ad.evaluate_sample(sample["qa"])
        found = [q for q in r["questions"]
                 if "What class" in q["question"]]
        assert found
        # The top-ranked extractive answer should contain "pottery"
        assert any("pottery" in q["predicted"].lower() for q in found)

    def test_judge_fn_override(self):
        ad = fresh_adapter()
        sample = make_sample()
        ad.ingest_sample(sample)
        calls = []

        def judge(q, truth, pred):
            calls.append(q)
            return True

        r = ad.evaluate_sample(sample["qa"], judge_fn=judge)
        assert len(calls) == 5            # adversarial skips the judge
        assert r["overall_accuracy_no_adversarial"] == 1.0

    def test_session_hit_and_turn_hit(self):
        ad = fresh_adapter()
        sample = make_sample()
        ad.ingest_sample(sample)
        r = ad.evaluate_sample(sample["qa"])
        hits = [q for q in r["questions"] if q["session_hit"]]
        assert hits                        # at least one session-level hit
        turns = [q for q in r["questions"] if q["turn_hit"]]
        # turn_hit implies session_hit (a dia node lives in a session)
        for q in turns:
            assert q["session_hit"]

    def test_adversarial_excluded_from_recall_rates(self):
        ad = fresh_adapter()
        sample = make_sample()
        ad.ingest_sample(sample)
        r = ad.evaluate_sample(sample["qa"])
        for q in r["questions"]:
            if q["category"] == "adversarial":
                assert q["session_hit"] is False
                assert q["turn_hit"] is False
                assert q["context_hit"] is False

    def test_context_hit_when_truth_in_context(self):
        """Truth visible in the retrieved window → context_hit,
        even when the top-1 line is the partner's reply."""
        ad = fresh_adapter()
        sample = make_sample()
        ad.ingest_sample(sample)
        r = ad.evaluate_sample(sample["qa"])
        found = [q for q in r["questions"]
                 if q["question"].startswith("What class")]
        assert found
        assert any(q["context_hit"] for q in found)
        for key in ("session_hit_rate", "turn_hit_rate",
                    "context_hit_rate"):
            assert key in r

    def test_limit(self):
        ad = fresh_adapter()
        sample = make_sample()
        ad.ingest_sample(sample)
        assert ad.evaluate_sample(sample["qa"], limit=2)[
            "total_questions"] == 2

    def test_unknown_category_falls_back(self):
        ad = fresh_adapter()
        sample = make_sample()
        ad.ingest_sample(sample)
        sample["qa"].append({"question": "x?", "answer": "x",
                             "evidence": ["D1:1"], "category": 99})
        r = ad.evaluate_sample(sample["qa"])
        assert "unknown" in r["categories"]


# ---------------------------------------------------------------------------
# run_locomo (multi-sample aggregation + isolation)
# ---------------------------------------------------------------------------

class TestRunLoop:
    def test_report_shape(self, data_file):
        r = run_locomo(data_file, use_ppr=False)
        for key in ("overall_accuracy", "overall_accuracy_no_adversarial",
                    "abstention_rate", "session_hit_rate", "turn_hit_rate",
                    "context_hit_rate", "avg_tokens", "categories",
                    "samples", "config"):
            assert key in r
        assert r["total_questions"] == 8   # 6 + 2

    def test_per_sample_fresh_graph(self, data_file):
        """Sample 2's answer must not leak sample 1's nodes."""
        r = run_locomo(data_file, use_ppr=False)
        stats = [s["ingest_stats"] for s in r["samples"]]
        assert stats[0]["messages"] == 5
        assert stats[1]["messages"] == 5
        # both samples ingested the same corpus independently
        assert stats[0]["entities"] == stats[1]["entities"]

    def test_category_aggregation(self, data_file):
        r = run_locomo(data_file, use_ppr=False)
        cats = r["categories"]
        assert cats["single_hop"]["total"] == 4
        assert cats["temporal"]["total"] == 1
        assert cats["adversarial"]["total"] == 2
        total = sum(c["total"] for c in cats.values())
        assert total == r["total_questions"]

    def test_limit_samples(self, data_file):
        r = run_locomo(data_file, limit_samples=1, use_ppr=False)
        assert r["total_questions"] == 6

    def test_max_questions_per_sample(self, data_file):
        r = run_locomo(data_file, max_questions_per_sample=1,
                       use_ppr=False)
        assert r["total_questions"] == 2

    def test_config_echoed(self, data_file):
        r = run_locomo(data_file, use_ppr=False, abstain_entropy=None)
        assert r["config"]["use_ppr"] is False
        assert r["config"]["abstain_entropy"] is None
        assert "wall_seconds" in r["config"]

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            run_locomo(tmp_path / "nope.json")


# ---------------------------------------------------------------------------
# sweep_abstention (Cycle 452)
# ---------------------------------------------------------------------------

class TestSweepAbstention:
    ENTROPIES = [None, 0.9, 0.5]

    def test_shape_and_labels(self):
        ad = fresh_adapter()
        sample = make_sample()
        ad.ingest_sample(sample)
        r = ad.sweep_abstention(sample["qa"], entropies=self.ENTROPIES)
        assert r["thresholds"] == ["None", "0.9", "0.5"]
        assert set(r["summary"]) == set(r["thresholds"])
        for lab in r["thresholds"]:
            for key in ("accuracy", "abstention_rate",
                        "adversarial_accuracy", "accuracy_non_adv",
                        "total"):
                assert key in r["summary"][lab]
        assert len(r["rows"]) == 6

    def test_one_retrieval_per_question(self):
        """The gate is post-retrieval: N questions → N retrievals,
        regardless of threshold count."""
        ad = fresh_adapter()
        sample = make_sample()
        ad.ingest_sample(sample)
        r = ad.sweep_abstention(sample["qa"], entropies=self.ENTROPIES)
        assert r["retrievals"] == len(sample["qa"])

    def test_adversarial_scores_by_abstention(self):
        ad = fresh_adapter()
        sample = make_sample()
        ad.ingest_sample(sample)
        r = ad.sweep_abstention(sample["qa"], entropies=[None])
        adv_rows = [row for row in r["rows"]
                    if row["category"] == "adversarial"]
        for row in adv_rows:
            assert row["correct"]["None"] == row["abstained"]["None"]

    def test_entropy_gate_helps_adversarial(self):
        """Fixture: 'skydiving in Dubai' never happened — weak
        scattered evidence (only 'Caroline' hits) → gate abstains."""
        ad = fresh_adapter(abstain_entropy=None)   # control via sweep
        sample = make_sample()
        ad.ingest_sample(sample)
        r = ad.sweep_abstention(sample["qa"], entropies=self.ENTROPIES)
        s = r["summary"]
        assert s["0.9"]["adversarial_accuracy"] >= \
            s["None"]["adversarial_accuracy"]

    def test_lower_threshold_abstains_more(self):
        ad = fresh_adapter()
        sample = make_sample()
        ad.ingest_sample(sample)
        r = ad.sweep_abstention(sample["qa"], entropies=self.ENTROPIES)
        rates = [r["summary"][lab]["abstention_rate"]
                 for lab in r["thresholds"]]
        # None → 0.9 → 0.5: monotonic non-decreasing abstention
        assert rates[0] <= rates[1] <= rates[2]

    def test_gate_cost_visible_on_non_adversarial(self):
        """accuracy_non_adv present per threshold — the tradeoff
        axis for working-point selection."""
        ad = fresh_adapter()
        sample = make_sample()
        ad.ingest_sample(sample)
        r = ad.sweep_abstention(sample["qa"], entropies=self.ENTROPIES)
        for lab in r["thresholds"]:
            assert 0.0 <= r["summary"][lab]["accuracy_non_adv"] <= 1.0

    def test_limit(self):
        ad = fresh_adapter()
        sample = make_sample()
        ad.ingest_sample(sample)
        r = ad.sweep_abstention(sample["qa"], entropies=[None], limit=2)
        assert len(r["rows"]) == 2
        assert r["retrievals"] == 2


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCli:
    def test_main_smoke(self, data_file, tmp_path, capsys):
        out = tmp_path / "report.json"
        rc = main(["--data", str(data_file), "--no-ppr",
                   "--output", str(out)])
        assert rc == 0
        captured = capsys.readouterr().out
        assert "questions" in captured
        assert "evidence recall" in captured
        report = json.loads(out.read_text(encoding="utf-8"))
        assert report["total_questions"] == 8
        assert report["config"]["use_ppr"] is False

    def test_main_negative_entropy_disables_gate(self, data_file,
                                                 tmp_path):
        out = tmp_path / "r2.json"
        rc = main(["--data", str(data_file), "--no-ppr",
                   "--abstain-entropy", "-1", "--output", str(out)])
        assert rc == 0
        report = json.loads(out.read_text(encoding="utf-8"))
        assert report["config"]["abstain_entropy"] is None


# ---------------------------------------------------------------------------
# Cycle 455 — subject-support gate (answer-side verification, cat 5)
# ---------------------------------------------------------------------------

from locomo_bench_quality import (
    _question_subjects,
    _same_name,
    subject_support_gate,
)


class TestQuestionSubjects:
    def test_mid_question_capitalized_names(self):
        assert _question_subjects(
            "What are Melanie's plans for the summer?") == ["melanie"]

    def test_multiple_subjects_and_stop_words(self):
        subjects = _question_subjects(
            "What did Caroline tell Melanie about Dubai?")
        assert "caroline" in subjects and "melanie" in subjects
        assert "dubai" in subjects
        assert "what" not in subjects and "the" not in subjects

    def test_first_word_excluded(self):
        assert _question_subjects("Melanie loves pottery.") == []

    def test_no_subjects(self):
        assert _question_subjects(
            "where is the pottery class held?") == []


class TestSameName:
    def test_diminutive_prefix(self):
        assert _same_name("carol", "caroline")
        assert _same_name("sarah", "sarahs")

    def test_short_prefix_not_merged(self):
        assert not _same_name("ali", "alice")
        assert not _same_name("mel", "melanie")  # 3 < 4

    def test_unrelated(self):
        assert not _same_name("melanie", "caroline")

    def test_equal(self):
        assert _same_name("mel", "mel")


class TestSubjectSupportGate:
    def test_fires_on_subject_swap(self):
        # LoCoMo cat-5 shape: ask about Melanie, evidence is about
        # Caroline ("Wow, Caroline! ..." with no Melanie in text).
        assert subject_support_gate(
            "What are Melanie's plans for adoption?",
            "Wow, Caroline! Adoption is amazing, you're so kind.")

    def test_no_fire_when_subject_present(self):
        assert not subject_support_gate(
            "What did Caroline say about adoption?",
            "Wow, Caroline! Adoption is amazing, you're so kind.")

    def test_no_fire_without_names_in_answer(self):
        # Third-person pronoun answer: no names → cannot conclude
        # subject mismatch → conservative pass.
        assert not subject_support_gate(
            "What is Melanie's job?", "She's a nurse.")

    def test_no_fire_without_question_subject(self):
        assert not subject_support_gate(
            "where is the pottery class held?",
            "Wow, Caroline! Adoption is amazing.")

    def test_diminutive_tolerance(self):
        # "Carol" ≈ "Caroline" (prefix ≥4): not foreign → no fire.
        assert not subject_support_gate(
            "What did Caroline research?",
            "Carol found some adoption agencies.")

    def test_speaker_is_subject_no_fire(self):
        # "[Caroline] Thanks, Melanie! ... my grandma ... Sweden" —
        # the subject herself is the SPEAKER; "Melanie" is a
        # vocative, not foreign-subject evidence.
        assert not subject_support_gate(
            "What country is Caroline's grandma from?",
            "Thanks, Melanie! This necklace is a gift from my grandma "
            "in Sweden.",
            known_names=["Melanie", "Caroline"],
            speaker="Caroline")

    def test_speaker_differs_from_subject_still_fires(self):
        assert subject_support_gate(
            "What are Melanie's plans for adoption?",
            "Wow, Caroline! Adoption plans sound amazing.",
            known_names=["Melanie", "Caroline"],
            speaker="Caroline")

    def test_month_not_foreign_name(self):
        # "June" is a month, not a person — must not read as foreign
        # subject evidence (factual "starts in June" answer).
        assert not subject_support_gate(
            "What are Melanie's plans for adoption?",
            "Adoption paperwork starts in June.")
        # Speaker mode: only known speakers count as names.
        assert not subject_support_gate(
            "What are Melanie's plans for adoption?",
            "Adoption paperwork starts in June.",
            known_names=["Melanie", "Caroline"])

    def test_no_fire_when_only_foreign_but_subject_named_too(self):
        # Subject named anywhere in the answer → supported. Uses
        # known_names mode (speaker名单) — the generic fallback skips
        # sentence-initial capitals, a documented limitation.
        assert not subject_support_gate(
            "What are Melanie's plans for adoption?",
            "Melanie said Caroline should handle the adoption paperwork.",
            known_names=["Melanie", "Caroline"])


def make_swap_sample():
    """Mini fixture whose adversarial question is a subject swap."""
    conv = {
        "speaker_a": "Caroline", "speaker_b": "Mel",
        "session_1_date_time": "1:00 pm on 1 May, 2024",
        "session_1": [
            {"speaker": "Caroline", "dia_id": "D1:1",
             "text": "I researched adoption agencies for my summer."},
            {"speaker": "Mel", "dia_id": "D1:2",
             "text": "Wow, Caroline! Adoption plans sound amazing, "
                     "you're so kind."},
            {"speaker": "Caroline", "dia_id": "D1:3",
             "text": "Yes, adoption paperwork starts in June."},
        ],
    }
    qa = [
        # factual: subject Caroline named in answer line → no fire
        {"question": "What did Caroline research?",
         "answer": "adoption agencies",
         "evidence": ["D1:1"], "category": 1},
        # adversarial subject swap: top-1 hit is Mel's Caroline line
        {"question": "What are Melanie's plans for adoption?",
         "adversarial_answer": "adoption paperwork",
         "evidence": ["D1:2"], "category": 5},
    ]
    return {"conversation": conv, "qa": qa}


class TestSubjectGateIntegration:
    def test_gate_off_answers_both(self):
        ad = LoCoMoAdapter(use_ppr=False)
        ad.ingest_sample(make_swap_sample())
        _, meta = ad.answer_extractive(
            "What are Melanie's plans for adoption?")
        assert meta["abstained"] is False

    def test_gate_on_abstains_with_subject_reason(self):
        ad = LoCoMoAdapter(use_ppr=False, subject_gate=True)
        ad.ingest_sample(make_swap_sample())
        answer, meta = ad.answer_extractive(
            "What are Melanie's plans for adoption?")
        assert meta["abstained"] is True
        assert meta["gate"] == "subject"
        assert answer == lbq.ABSTAIN_ANSWER

    def test_gate_on_factual_untouched(self):
        ad = LoCoMoAdapter(use_ppr=False, subject_gate=True)
        ad.ingest_sample(make_swap_sample())
        answer, meta = ad.answer_extractive(
            "What did Caroline research?")
        assert meta["abstained"] is False
        assert "adoption" in answer.lower()

    def test_evaluate_sample_scores_swap_correct(self):
        ad = LoCoMoAdapter(use_ppr=False, subject_gate=True)
        sample = make_swap_sample()
        ad.ingest_sample(sample)
        r = ad.evaluate_sample(sample["qa"])
        adv = next(q for q in r["questions"]
                   if q["category"] == "adversarial")
        assert adv["correct"] is True and adv["abstained"] is True


class TestSweepSubjectGate:
    def test_off_on_modes_and_aggregation(self):
        ad = LoCoMoAdapter(use_ppr=False, subject_gate=True)
        sample = make_swap_sample()
        ad.ingest_sample(sample)
        r = ad.sweep_subject_gate(sample["qa"])
        assert r["retrievals"] == 2 and len(r["rows"]) == 2
        assert set(r["modes"]) == {"off", "on"}
        # gate lifts adversarial accuracy without touching factual
        assert (r["modes"]["on"]["adversarial_accuracy"]
                > r["modes"]["off"]["adversarial_accuracy"])
        assert (r["modes"]["on"]["accuracy_non_adv"]
                == r["modes"]["off"]["accuracy_non_adv"])

    def test_restores_subject_gate_flag(self):
        ad = LoCoMoAdapter(use_ppr=False, subject_gate=True)
        ad.ingest_sample(make_swap_sample())
        ad.sweep_subject_gate(make_swap_sample()["qa"])
        assert ad.subject_gate is True

    def test_run_locomo_config_passthrough(self, tmp_path):
        data = [make_swap_sample()]
        p = tmp_path / "swap.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        r = run_locomo(str(p), use_ppr=False, subject_gate=True)
        assert r["config"]["subject_gate"] is True
        cat5 = r["categories"]["adversarial"]
        assert cat5["total"] == 1 and cat5["correct"] == 1

    def test_cli_subject_gate(self, data_file, tmp_path):
        out = tmp_path / "r3.json"
        rc = main(["--data", str(data_file), "--no-ppr",
                   "--subject-gate", "--output", str(out)])
        assert rc == 0
        report = json.loads(out.read_text(encoding="utf-8"))
        assert report["config"]["subject_gate"] is True


# ---------------------------------------------------------------------------
# Temporal date resolution (Cycle 456)
# ---------------------------------------------------------------------------

class TestDateExtraction:
    def test_all_formats_canonical(self):
        assert extract_dates("We met on 7 May 2023.") == ["2023-05-07"]
        assert extract_dates("It was May 7th, 2023 already") == \
            ["2023-05-07"]
        assert extract_dates("Deadline: 2023-05-07 sharp") == ["2023-05-07"]
        assert extract_dates("Opened 05/07/2023") == ["2023-05-07"]
        assert extract_dates("The 7th of May, 2023 was great") == \
            ["2023-05-07"]
        assert extract_dates("Opened 05/07/23") == ["2023-05-07"]

    def test_multiple_dedup_sorted(self):
        ds = extract_dates("from 9 May 2023 until 1 June 2023, again 9 May 2023")
        assert ds == ["2023-05-09", "2023-06-01"]

    def test_no_false_positives(self):
        assert extract_dates("I have 3 cats and 12 dogs") == []
        assert extract_dates("Room 2023 was nice") == []   # no word boundary year pattern w/o date grammar

    def test_canon_roundtrip(self):
        assert date_canon("see you 7 May 2023") == "2023-05-07"
        assert _canon_to_day_month_year("2023-05-07") == "7 May 2023"


class TestTemporalJudge:
    def test_format_insensitive_equality(self):
        assert temporal_judge("q", "7 May 2023", "May 7th, 2023")
        assert temporal_judge("q", "2023-05-07", "7 May 2023")

    def test_wrong_date_fails(self):
        assert not temporal_judge("q", "7 May 2023", "8 May 2023")

    def test_year_only_truth(self):
        assert temporal_judge("q", "2023", "graduated 7 May 2023")
        assert not temporal_judge("q", "2019", "graduated 7 May 2023")

    def test_containment_fallback(self):
        # Non-date truths keep the containment protocol.
        assert temporal_judge("q", "Tuesday", "Every Tuesday at noon")
        assert not temporal_judge("q", "Friday", "Every Tuesday at noon")


class TestAnswerTemporal:
    CTX = ("[Mel] That trip sounds amazing!\n"
           "[Caroline] I adopted my dog on 12 March 2021, a beagle.\n"
           "[Mel] My interview was on 3 April 2022.")

    def test_subject_line_preferred_over_first_dated(self):
        ans, found = answer_temporal("When did Caroline adopt her dog?",
                                     self.CTX)
        assert found and ans == "12 March 2021"

    def test_rank_order_first_subject_line_wins(self):
        # Rank order within subject-matching lines; month-year-only
        # mentions ("June 2019") are not full dates and are skipped.
        ctx = ("[Caroline] We moved house in June 2019.\n"
               "[Caroline] The reno finished 2 September 2020.\n"
               "[Caroline] Party on 1 January 2021.")
        ans, _ = answer_temporal("When did Caroline finish the reno?", ctx)
        assert ans == "2 September 2020"

    def test_no_subject_match_top_line_trusted(self):
        # Subject-less dated lines are trusted ONLY at rank 0.
        ans, found = answer_temporal("When did Sam travel?", self.CTX)
        assert not found            # rank-0 line has no date
        ctx = ("[Sam] I flew out on 3 April 2022.\n"
               "[Mel] unrelated chit chat")
        ans, found = answer_temporal("When did Sam travel?", ctx)
        assert found and ans == "3 April 2022"

    def test_no_dates_not_found(self):
        ans, found = answer_temporal("When is class?",
                                     "[Caroline] Every Tuesday at the center.")
        assert not found and ans == ""


class TestTemporalEvaluateWiring:
    def make_dated_sample(self):
        conv = {
            "speaker_a": "Caroline", "speaker_b": "Mel",
            "session_1_date_time": "1:56 pm on 8 May, 2023",
            "session_1": [
                {"speaker": "Mel", "dia_id": "D1:1",
                 "text": "Hey! How was the support group?"},
                {"speaker": "Caroline", "dia_id": "D1:2",
                 "text": "I went to the LGBTQ support group on 7 May 2023 and it helped."},
            ],
        }
        qa = [
            {"question": "When did Caroline go to the LGBTQ support group?",
             "answer": "7 May 2023", "evidence": ["D1:2"], "category": 3},
        ]
        return {"sample_id": "sd", "conversation": conv, "qa": qa}

    def test_temporal_row_correct_with_date(self):
        ad = LoCoMoAdapter(use_ppr=False)
        s = self.make_dated_sample()
        ad.ingest_sample(s)
        rep = ad.evaluate_sample(s["qa"])
        row = rep["questions"][0]
        assert row["date_answer"] is True
        assert row["predicted"] == "7 May 2023"
        assert row["correct"] is True

    def test_no_dates_flag_restores_c453_protocol(self):
        s = self.make_dated_sample()
        ad = LoCoMoAdapter(use_ppr=False, temporal_dates=False)
        ad.ingest_sample(s)
        rep = ad.evaluate_sample(s["qa"])
        row = rep["questions"][0]
        assert row["date_answer"] is False
        # C453 protocol: extractive answer is the whole message and
        # containment judges it (correct here only because the truth
        # string appears verbatim in the ranked message — real-run
        # temporal was 1/96 because ranking rarely achieves this).
        assert "7 May 2023" in row["predicted"]
        assert row["correct"] is True

    def test_fixture_tuesday_unaffected(self):
        # Existing fixture temporal question has no dated message:
        # no date resolution fires; extractive+judge behavior is the
        # documented pre-C456 outcome (incorrect — the temporal floor).
        ad = LoCoMoAdapter(use_ppr=False)
        s = make_sample()
        ad.ingest_sample(s)
        rep = ad.evaluate_sample(
            [q for q in s["qa"] if q["category"] == 3])
        row = rep["questions"][0]
        assert row["date_answer"] is False
        assert row["correct"] is False    # C453 temporal floor, unchanged

    def test_run_locomo_config_passthrough(self, tmp_path):
        p = tmp_path / "d.json"
        p.write_text(json.dumps([self.make_dated_sample()]),
                     encoding="utf-8")
        r = run_locomo(str(p), use_ppr=False, temporal_dates=False)
        assert r["config"]["temporal_dates"] is False

    def test_cli_no_dates(self, data_file, tmp_path):
        out = tmp_path / "nd.json"
        rc = main(["--data", str(data_file), "--no-ppr", "--no-dates",
                   "--output", str(out)])
        assert rc == 0
        cfg = json.loads(out.read_text(encoding="utf-8"))["config"]
        assert cfg["temporal_dates"] is False


# ---------------------------------------------------------------------------
# Cycle 464: dual-metric judge (Research #069) — exact/LLM two-column
# ---------------------------------------------------------------------------

class TestDualJudge:
    def _dual(self, qa=None, sample=None):
        import amg_bench_quality as abq
        s = sample or make_sample()
        ad = fresh_adapter()
        ad.ingest_sample(s)
        abq._JUDGE_MODE = "mock"   # skip ollama probe
        try:
            return ad.evaluate_sample(qa or s["qa"], judge_mode="dual")
        finally:
            abq._JUDGE_MODE = None

    def test_dual_report_keys(self):
        r = self._dual()
        for key in ("accuracy_exact", "accuracy_llm", "calibration"):
            assert key in r
        assert r["accuracy_exact"] == r["overall_accuracy"]
        for q in r["questions"]:
            assert q["correct_exact"] is not None
            assert q["correct_llm"] is not None

    def test_exact_mode_default_no_dual_keys(self):
        ad = fresh_adapter()
        ad.ingest_sample(make_sample())
        r = ad.evaluate_sample(make_sample()["qa"])
        assert "accuracy_llm" not in r
        assert "calibration" not in r
        for q in r["questions"]:
            assert q["correct_exact"] is None
            assert q["correct_llm"] is None

    def test_adversarial_verdicts_shared(self):
        r = self._dual()
        adv = [q for q in r["questions"] if q["category"] == "adversarial"]
        assert adv
        for q in adv:
            # cat5 is protocol-level: both columns carry the abstain verdict
            assert q["correct_llm"] == q["correct_exact"] == q["correct"]

    def test_run_locomo_dual_aggregates(self, data_file):
        import amg_bench_quality as abq
        abq._JUDGE_MODE = "mock"
        try:
            r = run_locomo(str(data_file), use_ppr=False,
                           judge_mode="dual")
        finally:
            abq._JUDGE_MODE = None
        for key in ("accuracy_exact", "accuracy_llm", "calibration"):
            assert key in r
        assert r["config"]["judge_mode"] == "dual"
        # calibration scored == every question across both samples
        assert r["calibration"]["scored"] == r["total_questions"]

    def test_run_locomo_default_regression(self, data_file):
        r = run_locomo(str(data_file), use_ppr=False)
        assert "accuracy_llm" not in r
        assert "calibration" not in r
        assert r["config"]["judge_mode"] == "exact"

    def test_cli_judge_dual(self, data_file, tmp_path):
        import amg_bench_quality as abq
        out = tmp_path / "dual.json"
        abq._JUDGE_MODE = "mock"
        try:
            rc = main(["--data", str(data_file), "--no-ppr",
                       "--judge", "dual", "--output", str(out)])
        finally:
            abq._JUDGE_MODE = None
        assert rc == 0
        rep = json.loads(out.read_text(encoding="utf-8"))
        assert rep["config"]["judge_mode"] == "dual"
        assert "accuracy_llm" in rep and "calibration" in rep
