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
    _dia_session,
    load_locomo,
    main,
    run_locomo,
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
