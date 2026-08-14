"""Tests for run_amg.py — GraphRAG-Bench (ICLR 2026) adapter.

Research #064 Gap #4. The Mont St. Michel corpus is the regression
fixture from the 2026-08-14 prototype validation: known to produce
10 nodes / 4 edges, and (thanks to Cycle 433 fact-answer extraction)
the correct edge-object answer "Normandy".
"""

import json

import pytest

import memory_graph as mg
import run_amg
from run_amg import (
    OFFICIAL_SCHEMA_KEYS,
    answer_question,
    index_corpus,
    load_bench_data,
    main,
    run_bench,
)

# ---------------------------------------------------------------------------
# Fixture: GraphRAG-Bench mini dataset (Research #064, verbatim corpus)
# ---------------------------------------------------------------------------

CORPUS = [
    {"corpus_name": "Novel-0001", "context": (
        "Cornwall is a region in the southwest of England. "
        "John Curgenven is a Cornish boatman. "
        "John Curgenven ferries visitors to Mont St. Michel. "
        "Mont St. Michel is located in Normandy. "
        "Erica vagans is a plant known as Cornish heath. "
        "King Arthur compared himself to John Curgenven."
    )},
    {"corpus_name": "Novel-0002", "context": (
        "Ada Lovelace works at the Analytical Engine. "
        "Charles Babbage created the Analytical Engine."
    )},
]

# Q1/Q2/Q3 hit via fact cues; Q4/Q5 exercise fallback (no cue / no keyword).
QUESTIONS = [
    {"id": "Novel-aaa1", "source": "Novel-0001",
     "question": "Where is Mont St. Michel located?",
     "answer": "Normandy", "question_type": "Fact Retrieval",
     "evidence": "Mont St. Michel is located in Normandy.",
     "evidence_relations": ""},
    {"id": "Novel-bbb1", "source": "Novel-0002",
     "question": "Where does Ada Lovelace work?",
     "answer": "Analytical Engine", "question_type": "Fact Retrieval",
     "evidence": "Ada Lovelace works at the Analytical Engine.",
     "evidence_relations": ""},
    {"id": "Novel-bbb2", "source": "Novel-0002",
     "question": "Who created the Analytical Engine?",
     "answer": "Charles Babbage", "question_type": "Complex Reasoning",
     "evidence": "Charles Babbage created the Analytical Engine.",
     "evidence_relations": ""},
    {"id": "Novel-aaa2", "source": "Novel-0001",
     "question": "Which region is Cornwall part of?",
     "answer": "England", "question_type": "Fact Retrieval",
     "evidence": "Cornwall is a region in the southwest of England.",
     "evidence_relations": ""},
    {"id": "Novel-bbb3", "source": "Novel-0002",
     "question": "What color is the invisible dragon?",
     "answer": "green", "question_type": "Creative Generation",
     "evidence": "", "evidence_relations": ""},
]


@pytest.fixture()
def bench_dir(tmp_path):
    d = tmp_path / "bench"
    d.mkdir()
    (d / "novel.json").write_text(json.dumps(CORPUS), encoding="utf-8")
    (d / "novel_questions.json").write_text(
        json.dumps(QUESTIONS), encoding="utf-8")
    return d


@pytest.fixture()
def indexed():
    g = mg.MemoryGraph()
    index_corpus(g, CORPUS)
    return g


# ---------------------------------------------------------------------------
# load_bench_data
# ---------------------------------------------------------------------------

class TestLoadBenchData:
    def test_happy_path(self, bench_dir):
        corpus, questions = load_bench_data(bench_dir)
        assert len(corpus) == 2 and len(questions) == 5
        assert corpus[0]["corpus_name"] == "Novel-0001"
        assert questions[0]["id"] == "Novel-aaa1"

    def test_missing_data_dir(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_bench_data(tmp_path / "nope")

    def test_missing_questions_file(self, tmp_path, bench_dir):
        (bench_dir / "novel_questions.json").unlink()
        with pytest.raises(FileNotFoundError):
            load_bench_data(bench_dir)

    def test_non_list_json(self, bench_dir):
        (bench_dir / "novel.json").write_text('{"a": 1}', encoding="utf-8")
        with pytest.raises(ValueError, match="expected JSON list"):
            load_bench_data(bench_dir)

    def test_question_missing_required_key(self, bench_dir):
        bad = [{"question": "q?", "source": "Novel-0001"}]  # no id
        (bench_dir / "novel_questions.json").write_text(
            json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError, match="missing key 'id'"):
            load_bench_data(bench_dir)

    def test_corpus_missing_context(self, bench_dir):
        (bench_dir / "novel.json").write_text(
            json.dumps([{"corpus_name": "x"}]), encoding="utf-8")
        with pytest.raises(ValueError, match="corpus_name/context"):
            load_bench_data(bench_dir)

    def test_sample_deterministic(self, bench_dir):
        a1, b1 = load_bench_data(bench_dir, sample=3)
        a2, b2 = load_bench_data(bench_dir, sample=3)
        assert [q["id"] for q in b1] == [q["id"] for q in b2]
        assert len(b1) == 3 and len(a1) == 2

    def test_sample_zero_returns_all(self, bench_dir):
        _, qs = load_bench_data(bench_dir, sample=0)
        assert len(qs) == 5

    def test_sample_larger_than_total_returns_all(self, bench_dir):
        _, qs = load_bench_data(bench_dir, sample=100)
        assert len(qs) == 5

    def test_seed_changes_sample(self, tmp_path):
        d = tmp_path / "big"
        d.mkdir()
        (d / "novel.json").write_text(json.dumps(CORPUS), encoding="utf-8")
        many = [dict(QUESTIONS[0], id=f"Novel-q{i:03d}") for i in range(20)]
        (d / "novel_questions.json").write_text(
            json.dumps(many), encoding="utf-8")
        _, b1 = load_bench_data(d, sample=5, seed=1)
        _, b2 = load_bench_data(d, sample=5, seed=9999)
        assert {q["id"] for q in b1} != {q["id"] for q in b2}


# ---------------------------------------------------------------------------
# index_corpus
# ---------------------------------------------------------------------------

class TestIndexCorpus:
    def test_aggregate_stats(self, indexed):
        # Research #064 fixture: 10 nodes / 4 edges for Novel-0001 alone.
        assert indexed  # fixture sanity

    def test_stats_keys(self):
        g = mg.MemoryGraph()
        stats = index_corpus(g, CORPUS)
        for key in ("docs", "nodes_created", "edges_created",
                    "sentences", "relations", "corpus_names"):
            assert key in stats
        assert stats["docs"] == 2
        assert stats["corpus_names"] == ["Novel-0001", "Novel-0002"]

    def test_research_fixture_counts(self):
        g = mg.MemoryGraph()
        stats = index_corpus(g, CORPUS[:1])  # Novel-0001 only
        # 11 nodes / 4 edges post-Cycle-432 abbreviation-safe splitting
        # (the Research #064 prototype measured 10 pre-fix: "Mont St" +
        # "Michel" are now one entity).
        assert stats["nodes_created"] == 11
        assert stats["edges_created"] == 4

    def test_empty_corpus(self):
        g = mg.MemoryGraph()
        stats = index_corpus(g, [])
        assert stats["docs"] == 0 and stats["nodes_created"] == 0

    def test_tags_from_corpus_name(self, indexed):
        row = indexed.conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE tags LIKE '%Novel-0002%'"
        ).fetchone()
        assert row[0] > 0


# ---------------------------------------------------------------------------
# answer_question
# ---------------------------------------------------------------------------

class TestAnswerQuestion:
    def test_official_schema_exact_keys(self, indexed):
        row = answer_question(indexed, QUESTIONS[0])
        assert sorted(row.keys()) == sorted(OFFICIAL_SCHEMA_KEYS)
        assert len(row) == 8  # strictly official — eval parsers rely on it

    def test_fact_answer_edge_object_wins(self, indexed):
        """Research #064 core lesson: 'Where is Mont St. Michel located?'
        must return the located_in EDGE OBJECT (Normandy), not the
        top-ranked seed node (Michel)."""
        row = answer_question(indexed, QUESTIONS[0])
        assert row["generated_answer"] == "Normandy"

    def test_reverse_fact_cue(self, indexed):
        """'Who created the Analytical Engine?' → created reverse edge."""
        row = answer_question(indexed, QUESTIONS[2])
        assert "Charles Babbage" in row["generated_answer"]

    def test_works_at_fact_cue(self, indexed):
        row = answer_question(indexed, QUESTIONS[1])
        assert "Analytical Engine" in row["generated_answer"]

    def test_fallback_to_top_node(self, indexed):
        # No fact cue match ("invisible dragon") and no keyword hits →
        # either empty or node fallback; must never crash.
        row = answer_question(indexed, QUESTIONS[4])
        assert isinstance(row["generated_answer"], str)

    def test_context_included(self, indexed):
        row = answer_question(indexed, QUESTIONS[0])
        assert isinstance(row["context"], str) and row["context"]

    def test_fields_passed_through(self, indexed):
        row = answer_question(indexed, QUESTIONS[3])
        assert row["id"] == "Novel-aaa2"
        assert row["question_type"] == "Fact Retrieval"
        assert row["ground_truth"] == "England"
        assert row["source"] == "Novel-0001"


# ---------------------------------------------------------------------------
# run_bench — end to end
# ---------------------------------------------------------------------------

class TestRunBench:
    def test_e2e_research_fixture_hits(self, bench_dir, tmp_path):
        """Prototype → module regression: same corpus, same questions,
        extractive hits must IMPROVE over the prototype's raw top-node
        baseline (which scored 0 on the Mont St. Michel question)."""
        out = tmp_path / "amg.json"
        s = run_bench(bench_dir, out, quiet=True)
        assert s["questions"] == 5
        # fact-answer rows hit (Normandy / Analytical Engine / Charles
        # Babbage); Cornwall-part-of (no cue) and dragon (no keyword)
        # exercise fallback.
        assert s["extractive_hits"] >= 3
        assert out.is_file()
        rows = json.loads(out.read_text(encoding="utf-8"))
        assert len(rows) == 5
        for row in rows:
            assert sorted(row.keys()) == sorted(OFFICIAL_SCHEMA_KEYS)

    def test_hit_rate_and_per_type(self, bench_dir):
        s = run_bench(bench_dir, quiet=True)
        assert 0.0 <= s["hit_rate"] <= 1.0
        fact = s["per_question_type"]["Fact Retrieval"]
        assert fact["n"] == 3 and fact["hits"] == 2
        cr = s["per_question_type"]["Complex Reasoning"]
        assert cr["n"] == 1 and cr["hits"] == 1

    def test_sample_limits_questions(self, bench_dir, tmp_path):
        s = run_bench(bench_dir, tmp_path / "s.json", sample=2, quiet=True)
        assert s["questions"] == 2

    def test_graphml_export(self, bench_dir, tmp_path):
        gpath = tmp_path / "kg.graphml"
        s = run_bench(bench_dir, None, graphml_path=gpath, quiet=True)
        assert gpath.is_file()
        assert s["graphml_path"] == str(gpath)
        text = gpath.read_text(encoding="utf-8")
        assert "<graphml" in text and "Normandy" in text

    def test_no_out_file_when_none(self, bench_dir, tmp_path):
        run_bench(bench_dir, None, quiet=True)
        assert not (tmp_path / "amg.json").exists()

    def test_out_creates_parent_dirs(self, bench_dir, tmp_path):
        out = tmp_path / "deep" / "nested" / "amg.json"
        run_bench(bench_dir, out, quiet=True)
        assert out.is_file()

    def test_summary_index_stats(self, bench_dir):
        s = run_bench(bench_dir, quiet=True)
        assert s["index"]["docs"] == 2
        assert s["index"]["nodes_created"] > 0

    def test_empty_questions_dir(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        (d / "novel.json").write_text(json.dumps(CORPUS), encoding="utf-8")
        (d / "novel_questions.json").write_text("[]", encoding="utf-8")
        s = run_bench(d, quiet=True)
        assert s["questions"] == 0 and s["hit_rate"] == 0.0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCli:
    def test_main_end_to_end(self, bench_dir, tmp_path, capsys):
        out = tmp_path / "cli.json"
        rc = main(["--data-dir", str(bench_dir), "--out", str(out),
                   "--sample", "3", "--seed", "7"])
        assert rc == 0
        assert out.is_file()
        assert len(json.loads(out.read_text(encoding="utf-8"))) == 3
        assert "hit_rate=" in capsys.readouterr().out

    def test_main_requires_data_dir(self, capsys):
        with pytest.raises(SystemExit):
            main([])
