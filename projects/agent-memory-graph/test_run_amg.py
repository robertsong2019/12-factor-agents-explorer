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
    chunk_text,
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


# ---------------------------------------------------------------------------
# chunk_text — Gap #6 sentence-boundary chunking (Cycle 440)
# ---------------------------------------------------------------------------

NOVEL = " ".join(
    f"Sentence number {i} mentions Person{i}." for i in range(40))


class TestChunkText:
    def test_empty_text(self):
        assert chunk_text("") == []

    def test_whitespace_only(self):
        assert chunk_text("   \n\t  ") == []

    @pytest.mark.parametrize("bad", [0, -1, -100])
    def test_invalid_max_tokens(self, bad):
        with pytest.raises(ValueError):
            chunk_text("Some text.", max_tokens=bad)

    def test_short_text_single_chunk(self):
        chunks = chunk_text("Alpha is a beta. Gamma works at Delta.",
                            max_tokens=512)
        assert len(chunks) == 1
        assert "Alpha is a beta." in chunks[0]
        assert "Gamma works at Delta" in chunks[0]

    def test_no_content_loss_roundtrip(self):
        """Crown invariant: re-segmenting every chunk recovers exactly
        the original sentence sequence (chunking never merges, drops,
        or reorders sentences)."""
        from memory_graph import segment_sentences
        orig = segment_sentences(NOVEL)
        for budget in (512, 100, 50, 20, 13):
            recovered = [s for c in chunk_text(NOVEL, max_tokens=budget)
                         for s in segment_sentences(c)]
            assert recovered == orig, f"budget={budget} lost sentences"

    @pytest.mark.parametrize("budget", [512, 100, 50, 20, 13])
    def test_budget_respected(self, budget):
        for c in chunk_text(NOVEL, max_tokens=budget):
            assert run_amg._estimate_tokens(c) <= budget

    def test_order_preserved(self):
        chunks = chunk_text(NOVEL, max_tokens=50)
        assert chunks[0].startswith("Sentence number 0 mentions Person0")
        assert chunks[-1].endswith("Person39.")

    def test_greedy_packing(self):
        text = "Alpha is a beta. Gamma works at Delta."
        assert len(chunk_text(text, max_tokens=512)) == 1

    def test_split_on_tight_budget(self):
        assert len(chunk_text(NOVEL, max_tokens=20)) > 1

    def test_runon_sentence_hard_split(self):
        runon = " ".join(f"word{i}" for i in range(100))
        pieces = chunk_text(runon, max_tokens=13)
        assert len(pieces) > 1
        for p in pieces:
            assert run_amg._estimate_tokens(p) <= 13
        # all words present, in order
        assert " ".join(pieces).split() == runon.split()

    def test_abbreviation_safe_boundaries(self):
        """A protected abbreviation must never split a sentence across
        chunks (Cycle 432 lesson, applied at chunk granularity)."""
        text = ("Mr. Darcy works at Pemberley. "
                "Mont St. Michel is located in Normandy. ") * 3
        chunks = chunk_text(text, max_tokens=20)
        for c in chunks:
            for bad in ("Mr\n", "St\n", "Mr .", "St ."):
                assert bad not in c
        from memory_graph import segment_sentences
        recovered = [s for c in chunks for s in segment_sentences(c)]
        assert any("Mr. Darcy works at Pemberley" in s for s in recovered)

    def test_terminators_restored(self):
        """Chunks containing multiple sentences carry restored '. '
        separators so downstream re-segmentation works."""
        chunks = chunk_text(NOVEL, max_tokens=50)
        assert any(". " in c for c in chunks)

    def test_deterministic(self):
        assert (chunk_text(NOVEL, max_tokens=30)
                == chunk_text(NOVEL, max_tokens=30))

    def test_max_tokens_one(self):
        chunks = chunk_text("one two three", max_tokens=1)
        assert all(run_amg._estimate_tokens(c) <= 1 for c in chunks)


class TestIndexCorpusChunked:
    def test_chunks_counter_default_equals_docs(self):
        g = mg.MemoryGraph()
        stats = index_corpus(g, CORPUS)
        assert stats["chunks"] == stats["docs"] == 2

    def test_chunk_size_zero_disabled(self):
        g = mg.MemoryGraph()
        stats = index_corpus(g, CORPUS, chunk_size=0)
        assert stats["chunks"] == 2  # whole-doc behavior

    def test_chunking_lossless_for_extraction(self):
        """Gap #6 acceptance: at a budget ≥ the longest sentence,
        chunked indexing produces IDENTICAL extraction results to
        whole-document indexing (rule mode is per-sentence)."""
        g1, g2 = mg.MemoryGraph(), mg.MemoryGraph()
        whole = index_corpus(g1, CORPUS)
        chunked = index_corpus(g2, CORPUS, chunk_size=32)
        assert chunked["chunks"] > whole["chunks"]  # actually chunked
        for key in ("nodes_created", "edges_created", "sentences"):
            assert chunked[key] == whole[key], key

    def test_tags_survive_chunking(self):
        g = mg.MemoryGraph()
        index_corpus(g, CORPUS, chunk_size=16)
        row = g.conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE tags LIKE '%Novel-0001%'"
        ).fetchone()
        assert row[0] > 0

    def test_tight_budget_still_indexes(self):
        g = mg.MemoryGraph()
        stats = index_corpus(g, CORPUS, chunk_size=16)
        assert stats["chunks"] > 2
        assert stats["nodes_created"] > 0


class TestRunBenchChunked:
    def test_e2e_chunked_identical_answers(self, bench_dir):
        """E2E lossless property: with chunking enabled (budget ≥
        longest sentence), every generated answer is identical to the
        unchunked run — chunking must not perturb retrieval."""
        base = run_bench(bench_dir, quiet=True)
        chunked = run_bench(bench_dir, quiet=True, chunk_size=32)
        assert chunked["hit_rate"] == base["hit_rate"]
        assert chunked["extractive_hits"] == base["extractive_hits"]
        assert ([r["generated_answer"] for r in chunked["predictions"]]
                == [r["generated_answer"] for r in base["predictions"]])
        assert chunked["index"]["chunks"] > base["index"]["chunks"]

    def test_summary_carries_chunk_stats(self, bench_dir):
        s = run_bench(bench_dir, quiet=True, chunk_size=32)
        assert "chunks" in s["index"]


class TestCliChunkSize:
    def test_chunk_size_flag(self, bench_dir, tmp_path, capsys):
        out = tmp_path / "cli-chunked.json"
        rc = main(["--data-dir", str(bench_dir), "--out", str(out),
                   "--chunk-size", "32"])
        assert rc == 0
        assert out.is_file()
        assert "chunks=" in capsys.readouterr().out

    def test_chunk_size_zero_runs(self, bench_dir, tmp_path):
        out = tmp_path / "cli-zero.json"
        rc = main(["--data-dir", str(bench_dir), "--out", str(out),
                   "--chunk-size", "0"])
        assert rc == 0 and out.is_file()
