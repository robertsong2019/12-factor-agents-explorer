"""Tests for rrf_classification() — Cycle 326.

Reciprocal Rank Fusion classification.
Parameter-free ensemble combining degree + spectral + fingerprint rankings.
Research #038: RRF is the zero-parameter default for multi-method graph classification.
"""
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def query_graph():
    """Path-like graph with a closing edge."""
    mg = MemoryGraph()
    nodes = [mg.add(f"N{i}").id for i in range(6)]
    for i in range(5):
        mg.link(nodes[i], nodes[i + 1], "next", weight=0.8)
    mg.link(nodes[0], nodes[5], "closes", weight=0.7)
    return mg


@pytest.fixture
def similar_ref():
    """Graph structurally similar to query (path + closing edge)."""
    mg = MemoryGraph()
    nodes = [mg.add(f"R{i}").id for i in range(6)]
    for i in range(5):
        mg.link(nodes[i], nodes[i + 1], "next", weight=0.8)
    mg.link(nodes[0], nodes[5], "closes", weight=0.7)
    return mg


@pytest.fixture
def different_ref():
    """Star graph — very different topology."""
    mg = MemoryGraph()
    nodes = [mg.add(f"S{i}").id for i in range(6)]
    for i in range(1, 6):
        mg.link(nodes[0], nodes[i], "center", weight=0.9)
    return mg


@pytest.fixture
def dense_ref():
    """Dense random graph."""
    import random
    random.seed(300)
    mg = MemoryGraph()
    nodes = [mg.add(f"D{i}").id for i in range(8)]
    for _ in range(20):
        import random as r
        s, t = r.sample(nodes, 2)
        mg.link(s, t, "r", weight=r.uniform(0.3, 0.9))
    return mg


# ─── Structure tests ──────────────────────────────────────────────

class TestStructure:
    def test_returns_dict(self, query_graph, similar_ref, different_ref):
        r = query_graph.rrf_classification([similar_ref, different_ref])
        assert isinstance(r, dict)

    def test_returns_none_for_empty_refs(self, query_graph):
        assert query_graph.rrf_classification([]) is None

    def test_has_required_keys(self, query_graph, similar_ref, different_ref):
        r = query_graph.rrf_classification([similar_ref, different_ref])
        for key in ("best_match", "best_score", "rankings", "k",
                     "methods_used", "confidence", "margin"):
            assert key in r, f"Missing key: {key}"


# ─── Ranking tests ────────────────────────────────────────────────

class TestRankings:
    def test_best_is_similar(self, query_graph, similar_ref, different_ref):
        r = query_graph.rrf_classification([similar_ref, different_ref])
        assert r["best_match"] == 0  # similar_ref

    def test_rankings_sorted_desc(self, query_graph, similar_ref, different_ref, dense_ref):
        r = query_graph.rrf_classification([similar_ref, different_ref, dense_ref])
        scores = [e["rrf_score"] for e in r["rankings"]]
        assert scores == sorted(scores, reverse=True)

    def test_rankings_have_all_fields(self, query_graph, similar_ref, different_ref):
        r = query_graph.rrf_classification([similar_ref, different_ref])
        for entry in r["rankings"]:
            assert "index" in entry
            assert "rrf_score" in entry

    def test_three_references(self, query_graph, similar_ref, different_ref, dense_ref):
        r = query_graph.rrf_classification([similar_ref, different_ref, dense_ref])
        assert len(r["rankings"]) == 3
        assert r["best_match"] == 0  # similar should still win


# ─── Methods used ─────────────────────────────────────────────────

class TestMethodsUsed:
    def test_all_three_methods(self, query_graph, similar_ref, different_ref):
        r = query_graph.rrf_classification([similar_ref, different_ref])
        assert "degree_jsd" in r["methods_used"]
        assert "spectral_divergence" in r["methods_used"]
        assert "fingerprint_distance" in r["methods_used"]

    def test_per_ranking_diagnostics(self, query_graph, similar_ref, different_ref):
        r = query_graph.rrf_classification([similar_ref, different_ref])
        for entry in r["rankings"]:
            assert "degree_rank" in entry
            assert "spectral_rank" in entry
            assert "fingerprint_rank" in entry
            assert "degree_raw" in entry
            assert "spectral_raw" in entry
            assert "fingerprint_raw" in entry


# ─── K parameter ──────────────────────────────────────────────────

class TestKParameter:
    def test_default_k_is_6(self, query_graph, similar_ref, different_ref):
        r = query_graph.rrf_classification([similar_ref, different_ref])
        assert r["k"] == 6

    def test_custom_k(self, query_graph, similar_ref, different_ref):
        r = query_graph.rrf_classification([similar_ref, different_ref], k=10)
        assert r["k"] == 10

    def test_small_k_more_discriminative(self, query_graph, similar_ref, different_ref):
        """Smaller k → larger gap between rank 1 and rank 2."""
        r6 = query_graph.rrf_classification([similar_ref, different_ref], k=6)
        r1 = query_graph.rrf_classification([similar_ref, different_ref], k=1)
        assert r1["margin"] >= r6["margin"]

    def test_large_k_less_discriminative(self, query_graph, similar_ref, different_ref):
        r6 = query_graph.rrf_classification([similar_ref, different_ref], k=6)
        r60 = query_graph.rrf_classification([similar_ref, different_ref], k=60)
        assert r60["margin"] <= r6["margin"]


# ─── Confidence ───────────────────────────────────────────────────

class TestConfidence:
    def test_confidence_positive(self, query_graph, similar_ref, different_ref):
        r = query_graph.rrf_classification([similar_ref, different_ref])
        assert r["confidence"] > 0

    def test_margin_positive(self, query_graph, similar_ref, different_ref):
        r = query_graph.rrf_classification([similar_ref, different_ref])
        assert r["margin"] > 0

    def test_unanimous_vote_high_confidence(self, query_graph, similar_ref, different_ref):
        """When all methods rank the same ref #1, confidence should be high."""
        r = query_graph.rrf_classification([similar_ref, different_ref])
        best_entry = r["rankings"][0]
        if best_entry.get("degree_rank") == 1 and best_entry.get("spectral_rank") == 1:
            assert r["confidence"] > 1.0  # best/second > 1


# ─── Consistency ──────────────────────────────────────────────────

class TestConsistency:
    def test_idempotent(self, query_graph, similar_ref, different_ref):
        r1 = query_graph.rrf_classification([similar_ref, different_ref])
        r2 = query_graph.rrf_classification([similar_ref, different_ref])
        assert r1["best_match"] == r2["best_match"]
        assert r1["best_score"] == r2["best_score"]

    def test_single_reference(self, query_graph, similar_ref):
        r = query_graph.rrf_classification([similar_ref])
        assert r["best_match"] == 0
        assert len(r["rankings"]) == 1


# ─── RRF math verification ────────────────────────────────────────

class TestRRFMath:
    def test_rrf_formula(self, query_graph, similar_ref, different_ref):
        """Verify RRF score = sum of 1/(k + rank) for each method."""
        r = query_graph.rrf_classification([similar_ref, different_ref], k=6)
        for entry in r["rankings"]:
            expected = 0.0
            if "degree_rank" in entry:
                expected += 1.0 / (6 + entry["degree_rank"])
            if "spectral_rank" in entry:
                expected += 1.0 / (6 + entry["spectral_rank"])
            if "fingerprint_rank" in entry:
                expected += 1.0 / (6 + entry["fingerprint_rank"])
            assert abs(entry["rrf_score"] - round(expected, 8)) < 1e-6

    def test_max_possible_score(self):
        """With 3 methods and rank 1 for each: max = 3 * 1/(k+1)."""
        k = 6
        max_score = 3 * (1.0 / (k + 1))
        assert max_score == 3.0 / 7.0
