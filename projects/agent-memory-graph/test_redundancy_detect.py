"""Tests for redundancy_detect() — Cycle 267.

Complements knowledge_gap_report by detecting the opposite problem:
too much overlap / noise instead of too few connections.
"""
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def empty_graph():
    return MemoryGraph(":memory:")


@pytest.fixture
def dense_graph():
    """Graph with no redundancy — well-separated nodes."""
    mg = MemoryGraph(":memory:")
    mg.add("Python", "skill", {"level": "expert"})
    mg.add("Rust", "skill", {"level": "learning"})
    mg.add("Cooking", "hobby")
    mg.add("Astronomy", "hobby")
    mg.add("TypeScript", "skill")
    mg.add("Gardening", "hobby")
    # Sparse connections — different neighbours
    return mg


@pytest.fixture
def dup_graph():
    """Graph with obvious content + structural redundancy."""
    mg = MemoryGraph(":memory:")
    mg.add("Python programming", "skill")
    mg.add("Python programing", "skill")  # near-duplicate label
    mg.add("Rust embedded", "skill")
    mg.add("Cooking Italian", "hobby")
    mg.add("Gardening", "hobby")
    return mg


class TestRedundancyDetectBasics:
    """Core structural tests."""

    def test_empty_graph(self, empty_graph):
        r = empty_graph.redundancy_detect()
        assert r["content_duplicates"] == []
        assert r["structural_clones"] == []
        assert r["functional_duplicates"] == []
        assert r["redundancy_score"] == 0.0
        assert r["total_nodes"] == 0

    def test_single_node(self, empty_graph):
        empty_graph.add("Solo", "test")
        r = empty_graph.redundancy_detect()
        assert r["redundancy_score"] == 0.0
        assert r["total_nodes"] == 1
        assert "Not enough nodes" in r["recommendations"][0]

    def test_two_distinct_nodes(self, empty_graph):
        empty_graph.add("Apple", "fruit")
        empty_graph.add("Calculus", "math")
        r = empty_graph.redundancy_detect()
        assert r["content_duplicates"] == []
        assert r["redundancy_score"] == 0.0

    def test_returns_required_keys(self, dense_graph):
        r = dense_graph.redundancy_detect()
        required = {
            "content_duplicates", "structural_clones", "functional_duplicates",
            "redundancy_score", "merge_candidates", "total_nodes",
            "recommendations",
        }
        assert required.issubset(r.keys())

    def test_redundancy_score_range(self, dense_graph):
        r = dense_graph.redundancy_detect()
        assert 0 <= r["redundancy_score"] <= 100


class TestContentDuplicates:
    """Content-level similarity detection."""

    def test_detects_near_duplicate_labels(self, dup_graph):
        r = dup_graph.redundancy_detect()
        assert len(r["content_duplicates"]) >= 1
        pair = r["content_duplicates"][0]
        assert "Python" in pair["label_a"]
        assert "Python" in pair["label_b"]
        assert pair["similarity"] >= 0.65

    def test_content_duplicate_fields(self, dup_graph):
        r = dup_graph.redundancy_detect()
        if r["content_duplicates"]:
            d = r["content_duplicates"][0]
            assert "node_a" in d
            assert "node_b" in d
            assert "label_a" in d
            assert "label_b" in d
            assert "similarity" in d

    def test_no_false_positives(self, dense_graph):
        r = dense_graph.redundancy_detect(content_threshold=0.95)
        assert r["content_duplicates"] == []

    def test_threshold_respected(self, dup_graph):
        r_high = dup_graph.redundancy_detect(content_threshold=0.99)
        r_low = dup_graph.redundancy_detect(content_threshold=0.3)
        assert len(r_high["content_duplicates"]) <= len(r_low["content_duplicates"])

    def test_sorted_by_similarity(self, dup_graph):
        r = dup_graph.redundancy_detect()
        sims = [d["similarity"] for d in r["content_duplicates"]]
        assert sims == sorted(sims, reverse=True)


class TestStructuralClones:
    """Structural overlap detection."""

    def test_detects_same_neighbours(self, empty_graph):
        mg = empty_graph
        a = mg.add("A", "test")
        b = mg.add("B", "test")
        c = mg.add("C", "hub")
        d = mg.add("D", "hub")
        # A and B both connect to C and D (identical neighbours)
        mg.link(a.id, c.id, "rel")
        mg.link(a.id, d.id, "rel")
        mg.link(b.id, c.id, "rel")
        mg.link(b.id, d.id, "rel")
        r = mg.redundancy_detect(structural_threshold=0.5)
        assert len(r["structural_clones"]) >= 1
        clone = r["structural_clones"][0]
        assert clone["jaccard"] >= 0.5
        assert clone["shared_count"] >= 2

    def test_structural_clone_fields(self, empty_graph):
        mg = empty_graph
        a = mg.add("Alpha", "t")
        b = mg.add("Beta", "t")
        c = mg.add("Gamma", "h")
        mg.link(a.id, c.id, "r")
        mg.link(b.id, c.id, "r")
        r = mg.redundancy_detect(structural_threshold=0.3)
        if r["structural_clones"]:
            sc = r["structural_clones"][0]
            assert "node_a" in sc
            assert "node_b" in sc
            assert "jaccard" in sc
            assert "shared_count" in sc
            assert "total_neighbors" in sc

    def test_no_structural_clones_in_sparse_graph(self, dense_graph):
        r = dense_graph.redundancy_detect(structural_threshold=0.8)
        # No nodes share neighbours in dense_graph
        assert r["structural_clones"] == []

    def test_threshold_filtering(self, empty_graph):
        mg = empty_graph
        a = mg.add("A", "t")
        b = mg.add("B", "t")
        c = mg.add("C", "h")
        mg.link(a.id, c.id, "r")
        mg.link(b.id, c.id, "r")
        # 1 shared / 2 union = 0.5 Jaccard (each has {C}, but also each other)
        # Actually neighbours: A→{C,B}, B→{C,A} → intersection={C}, union={A,B,C} → 0.33
        r_strict = mg.redundancy_detect(structural_threshold=0.9)
        r_relaxed = mg.redundancy_detect(structural_threshold=0.2)
        assert len(r_strict["structural_clones"]) <= len(r_relaxed["structural_clones"])


class TestFunctionalDuplicates:
    """Same-kind + similar weight + similar degree detection."""

    def test_detects_same_kind(self, empty_graph):
        mg = empty_graph
        mg.add("X1", "concept", {})
        mg.add("X2", "concept", {})
        # Both: kind=concept, weight=1.0, degree=0
        r = mg.redundancy_detect()
        assert len(r["functional_duplicates"]) >= 1
        fd = r["functional_duplicates"][0]
        assert fd["kind"] == "concept"

    def test_different_kinds_not_flagged(self, empty_graph):
        mg = empty_graph
        mg.add("X1", "concept")
        mg.add("X2", "event")
        r = mg.redundancy_detect()
        assert r["functional_duplicates"] == []

    def test_weight_difference_filtered(self, empty_graph):
        mg = empty_graph
        h = mg.add("Heavy", "concept", {})
        l = mg.add("Light", "concept", {})
        # Set very different weights
        mg.conn.execute("UPDATE nodes SET weight=? WHERE id=?", (10.0, h.id))
        mg.conn.execute("UPDATE nodes SET weight=? WHERE id=?", (1.0, l.id))
        mg.conn.commit()
        r = mg.redundancy_detect()
        # Weight diff > 20% → not functional duplicate
        assert r["functional_duplicates"] == []

    def test_degree_difference_filtered(self, empty_graph):
        mg = empty_graph
        a = mg.add("Hub", "concept")
        b = mg.add("Solo", "concept")
        c = mg.add("C1", "x")
        d = mg.add("C2", "x")
        e = mg.add("C3", "x")
        mg.link(a.id, c.id, "r")
        mg.link(a.id, d.id, "r")
        mg.link(a.id, e.id, "r")
        # a: degree 3, b: degree 0, diff > 1
        r = mg.redundancy_detect()
        func_pairs = [(fd["node_a"], fd["node_b"]) for fd in r["functional_duplicates"]]
        assert (a.id, b.id) not in func_pairs
        assert (b.id, a.id) not in func_pairs

    def test_functional_dup_fields(self, empty_graph):
        mg = empty_graph
        mg.add("A", "test")
        mg.add("B", "test")
        r = mg.redundancy_detect()
        if r["functional_duplicates"]:
            fd = r["functional_duplicates"][0]
            assert "node_a" in fd
            assert "node_b" in fd
            assert "kind" in fd
            assert "weight_diff" in fd
            assert "degree_diff" in fd


class TestMergeCandidates:
    """Cross-dimensional merge ranking."""

    def test_merge_candidates_present_when_duplicates_exist(self, dup_graph):
        r = dup_graph.redundancy_detect()
        assert len(r["merge_candidates"]) >= 1

    def test_merge_candidate_fields(self, dup_graph):
        r = dup_graph.redundancy_detect()
        if r["merge_candidates"]:
            mc = r["merge_candidates"][0]
            assert "node_a" in mc
            assert "node_b" in mc
            assert "content_score" in mc
            assert "structural_score" in mc
            assert "functional_score" in mc
            assert "combined_score" in mc

    def test_sorted_by_combined_score(self, dup_graph):
        r = dup_graph.redundancy_detect()
        scores = [mc["combined_score"] for mc in r["merge_candidates"]]
        assert scores == sorted(scores, reverse=True)

    def test_max_pairs_limit(self, empty_graph):
        mg = empty_graph
        # Create many duplicates
        for i in range(20):
            mg.add(f"Python prog {i}", "skill")
        r = mg.redundancy_detect(max_pairs=3)
        assert len(r["content_duplicates"]) <= 3
        assert len(r["merge_candidates"]) <= 3


class TestNodeIdFilter:
    """Subgraph restriction."""

    def test_filter_restricts_analysis(self, empty_graph):
        mg = empty_graph
        mg.add("Python prog", "skill")
        mg.add("Python prog copy", "skill")
        u1 = mg.add("Unique topic", "concept")
        u2 = mg.add("Another unique", "event")
        # Filter to just the unique nodes (by node ID)
        r = mg.redundancy_detect(node_ids=[u1.id, u2.id])
        assert r["content_duplicates"] == []
        assert r["total_nodes"] == 2

    def test_filter_includes_duplicates(self, empty_graph):
        mg = empty_graph
        a = mg.add("Python programming language", "skill")
        b = mg.add("Python programming language", "skill")
        mg.add("Totally different", "x")
        r = mg.redundancy_detect(node_ids=[a.id, b.id])
        assert len(r["content_duplicates"]) >= 1
        assert r["total_nodes"] == 2


class TestRecommendations:
    """Human-readable output."""

    def test_recommendations_non_empty(self, dense_graph):
        r = dense_graph.redundancy_detect()
        assert len(r["recommendations"]) >= 1

    def test_no_redundancy_message(self, empty_graph):
        mg = empty_graph
        mg.add("Python", "skill")
        mg.add("Cooking", "hobby")
        mg.add("Astronomy", "science")
        r = mg.redundancy_detect()
        # Diverse, disconnected nodes → low/no redundancy
        assert any("Low redundancy" in rec or "No significant" in rec
                    for rec in r["recommendations"])

    def test_high_redundancy_warning(self, empty_graph):
        mg = empty_graph
        # Create high redundancy
        for i in range(10):
            mg.add(f"Python programming v{i}", "skill")
        r = mg.redundancy_detect()
        assert any("High redundancy" in rec or "Moderate redundancy" in rec
                    for rec in r["recommendations"])

    def test_content_dup_mentioned(self, dup_graph):
        r = dup_graph.redundancy_detect()
        assert any("Content duplicate" in rec for rec in r["recommendations"])


class TestNonMutating:
    """Ensure redundancy_detect doesn't modify the graph."""

    def test_no_nodes_added(self, dense_graph):
        before = dense_graph.stats()["nodes"]
        dense_graph.redundancy_detect()
        after = dense_graph.stats()["nodes"]
        assert before == after

    def test_no_edges_added(self, dense_graph):
        before = dense_graph.count_edges()
        dense_graph.redundancy_detect()
        after = dense_graph.count_edges()
        assert before == after

    def test_no_tags_modified(self, empty_graph):
        mg = empty_graph
        n = mg.add("Test", "x")
        mg.tag_nodes("tag1", [n.id])
        tags_before = mg.all_tags()
        mg.redundancy_detect()
        tags_after = mg.all_tags()
        assert set(tags_before) == set(tags_after)
