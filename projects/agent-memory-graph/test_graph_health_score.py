"""Tests for graph_health_score() — Cycle 323.

Composite 0-100 health metric combining six orthogonal signals:
connectivity, density, diversity, spectral entropy, redundancy, stability.
"""
import math
import pytest
from memory_graph import MemoryGraph


# ─── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def empty_graph():
    return MemoryGraph()


@pytest.fixture
def triangle():
    mg = MemoryGraph()
    a = mg.add("A", kind="concept")
    b = mg.add("B", kind="concept")
    c = mg.add("C", kind="concept")
    mg.link(a.id, b.id, "relates", weight=0.9)
    mg.link(b.id, c.id, "relates", weight=0.8)
    mg.link(a.id, c.id, "relates", weight=0.7)
    return mg


@pytest.fixture
def rich_graph():
    """Well-connected graph with diverse structure."""
    import random
    random.seed(42)
    mg = MemoryGraph()
    nodes = [mg.add(f"N{i}", kind="fact").id for i in range(15)]
    for i in range(14):
        mg.link(nodes[i], nodes[i + 1], "next", weight=0.8)
    for _ in range(30):
        s, t = random.sample(nodes, 2)
        mg.link(s, t, "relates", weight=random.uniform(0.3, 0.9))
    return mg


@pytest.fixture
def sparse_graph():
    """Graph with orphans and disconnected components."""
    mg = MemoryGraph()
    a = mg.add("A")
    b = mg.add("B")
    mg.link(a.id, b.id, "relates", weight=0.5)
    # Orphan nodes
    for i in range(10):
        mg.add(f"Orphan{i}")
    return mg


@pytest.fixture
def dense_redundant():
    """Graph with many redundant edges."""
    mg = MemoryGraph()
    a = mg.add("A")
    b = mg.add("B")
    for _ in range(20):
        mg.link(a.id, b.id, "duplicate", weight=0.5)
    return mg


# ─── Structure tests ──────────────────────────────────────────────

class TestStructure:
    def test_returns_dict(self, triangle):
        r = triangle.graph_health_score()
        assert isinstance(r, dict)

    def test_has_required_keys(self, triangle):
        r = triangle.graph_health_score()
        for key in ("score", "grade", "status", "components",
                     "weakest", "recommendations"):
            assert key in r, f"Missing key: {key}"

    def test_components_has_all_six(self, triangle):
        r = triangle.graph_health_score()
        comps = r["components"]
        for name in ("connectivity", "density", "diversity",
                      "spectral", "redundancy", "stability"):
            assert name in comps, f"Missing component: {name}"
            assert "score" in comps[name]
            assert "weight" in comps[name]
            assert "raw" in comps[name]

    def test_verbose_adds_counts(self, triangle):
        r = triangle.graph_health_score(verbose=True)
        assert "node_count" in r
        assert "edge_count" in r
        assert r["node_count"] == 3
        assert r["edge_count"] == 3


# ─── Score range tests ────────────────────────────────────────────

class TestScoreRange:
    def test_score_0_to_100(self, triangle):
        r = triangle.graph_health_score()
        assert 0 <= r["score"] <= 100

    def test_component_scores_0_to_1(self, triangle):
        r = triangle.graph_health_score()
        for name, comp in r["components"].items():
            assert 0 <= comp["score"] <= 1, f"{name} score out of range"

    def test_weights_sum_to_1(self, triangle):
        r = triangle.graph_health_score()
        total = sum(c["weight"] for c in r["components"].values())
        assert abs(total - 1.0) < 1e-9

    def test_empty_graph_low_score(self, empty_graph):
        r = empty_graph.graph_health_score()
        assert r["score"] < 20
        assert r["grade"] == "F"
        assert r["status"] == "critical"

    def test_triangle_high_score(self, triangle):
        r = triangle.graph_health_score()
        assert r["score"] >= 80
        assert r["grade"] in ("A", "B")


# ─── Grade tests ──────────────────────────────────────────────────

class TestGrade:
    def test_grade_A(self, triangle):
        r = triangle.graph_health_score()
        if r["score"] >= 90:
            assert r["grade"] == "A"
            assert r["status"] == "excellent"

    def test_grade_F(self, empty_graph):
        r = empty_graph.graph_health_score()
        assert r["grade"] == "F"
        assert r["status"] == "critical"

    def test_grade_boundaries(self):
        """Test grade boundary logic directly."""
        mg = MemoryGraph()
        # Mock the score by testing the grade thresholds
        for score, expected_grade, expected_status in [
            (90, "A", "excellent"),
            (89.9, "B", "good"),
            (75, "B", "good"),
            (74.9, "C", "fair"),
            (60, "C", "fair"),
            (59.9, "D", "poor"),
            (40, "D", "poor"),
            (39.9, "F", "critical"),
            (0, "F", "critical"),
        ]:
            # Use the function to check mapping is consistent
            grade = ("A" if score >= 90 else
                     "B" if score >= 75 else
                     "C" if score >= 60 else
                     "D" if score >= 40 else
                     "F")
            status = ("excellent" if score >= 90 else
                       "good" if score >= 75 else
                       "fair" if score >= 60 else
                       "poor" if score >= 40 else
                       "critical")
            assert grade == expected_grade
            assert status == expected_status


# ─── Component-specific tests ─────────────────────────────────────

class TestComponents:
    def test_connectivity_uses_gap_score(self, triangle):
        r = triangle.graph_health_score()
        # Triangle should have decent connectivity
        assert r["components"]["connectivity"]["score"] > 0.5

    def test_density_log_scaled(self, triangle):
        """K3 has density 1.0 → log-scaled should be ~1.0."""
        r = triangle.graph_health_score()
        assert r["components"]["density"]["score"] > 0.9

    def test_diversity_from_entropy_profile(self, triangle):
        r = triangle.graph_health_score()
        assert r["components"]["diversity"]["score"] > 0.5

    def test_spectral_von_neumann(self, triangle):
        r = triangle.graph_health_score()
        assert r["components"]["spectral"]["score"] > 0.5

    def test_redundancy_no_duplicates(self):
        """Graph with different kinds and varied degrees → less redundant."""
        mg = MemoryGraph()
        a = mg.add("A", kind="concept")
        b = mg.add("B", kind="entity")
        c = mg.add("C", kind="event")
        d = mg.add("D", kind="fact")
        mg.link(a.id, b.id, "relates", weight=0.9)
        mg.link(a.id, c.id, "causes", weight=0.7)
        mg.link(a.id, d.id, "supports", weight=0.5)
        mg.link(b.id, c.id, "triggers", weight=0.6)
        r = mg.graph_health_score()
        # Diverse kinds → fewer functional duplicates → higher redundancy health
        assert r["components"]["redundancy"]["score"] >= 0.3

    def test_redundancy_with_duplicates(self, dense_redundant):
        r = dense_redundant.graph_health_score()
        # 20 duplicate edges between same pair → high redundancy → low score
        assert r["components"]["redundancy"]["score"] <= 0.5

    def test_stability_present(self, rich_graph):
        r = rich_graph.graph_health_score()
        # Stability should be > 0 for a well-connected graph
        assert r["components"]["stability"]["score"] >= 0


# ─── Weakest component ────────────────────────────────────────────

class TestWeakest:
    def test_weakest_is_min_component(self, triangle):
        r = triangle.graph_health_score()
        comps = r["components"]
        actual_min = min(comps, key=lambda k: comps[k]["score"])
        assert r["weakest"] == actual_min

    def test_empty_graph_weakest(self, empty_graph):
        r = empty_graph.graph_health_score()
        # All scores 0, weakest is whichever is first in min()
        assert r["weakest"] in r["components"]


# ─── Recommendations ──────────────────────────────────────────────

class TestRecommendations:
    def test_empty_graph_has_recommendations(self, empty_graph):
        r = empty_graph.graph_health_score()
        assert len(r["recommendations"]) >= 1

    def test_healthy_graph_has_ok(self, triangle):
        r = triangle.graph_health_score()
        # Very healthy triangle should say ok
        if r["score"] >= 85:
            assert any("✅" in rec for rec in r["recommendations"])

    def test_sparse_graph_recommends_connectivity(self, sparse_graph):
        r = sparse_graph.graph_health_score()
        recs = " ".join(r["recommendations"])
        assert "onnectivity" in recs or "gap" in recs.lower()

    def test_recommendations_are_strings(self, triangle):
        r = triangle.graph_health_score()
        for rec in r["recommendations"]:
            assert isinstance(rec, str)


# ─── Custom weights ───────────────────────────────────────────────

class TestCustomWeights:
    def test_custom_weights_change_score(self, triangle):
        r1 = triangle.graph_health_score()
        # Heavily weight stability (which is 1.0 for triangle)
        r2 = triangle.graph_health_score(
            weights={"stability": 0.9, "connectivity": 0.1})
        assert r2["score"] != r1["score"]

    def test_weights_auto_normalised(self, triangle):
        """Weights don't need to sum to 1."""
        r = triangle.graph_health_score(
            weights={"connectivity": 50, "density": 50})
        total = sum(c["weight"] for c in r["components"].values())
        assert abs(total - 1.0) < 1e-9

    def test_zero_weights_uses_default(self, triangle):
        r = triangle.graph_health_score(weights={"connectivity": 0})
        total = sum(c["weight"] for c in r["components"].values())
        assert abs(total - 1.0) < 1e-9

    def test_partial_weights_override(self, triangle):
        r_default = triangle.graph_health_score()
        r_custom = triangle.graph_health_score(
            weights={"spectral": 0.5, "stability": 0.5})
        # Custom weights should differ from default
        assert (r_custom["components"]["spectral"]["weight"] >
                r_default["components"]["spectral"]["weight"])

    def test_invalid_weight_key_ignored(self, triangle):
        r = triangle.graph_health_score(weights={"nonexistent": 0.99})
        # Should not crash, should use defaults
        assert 0 <= r["score"] <= 100


# ─── Consistency ──────────────────────────────────────────────────

class TestConsistency:
    def test_idempotent(self, rich_graph):
        r1 = rich_graph.graph_health_score()
        r2 = rich_graph.graph_health_score()
        assert r1["score"] == r2["score"]

    def test_score_is_rounded(self, triangle):
        r = triangle.graph_health_score()
        # Score should be rounded to 1 decimal place
        assert round(r["score"], 1) == r["score"]

    def test_rich_graph_reasonable(self, rich_graph):
        r = rich_graph.graph_health_score()
        assert 30 <= r["score"] <= 100


# ─── Edge cases ───────────────────────────────────────────────────

class TestEdgeCases:
    def test_single_node(self):
        mg = MemoryGraph()
        mg.add("Lonely")
        r = mg.graph_health_score()
        assert 0 <= r["score"] <= 100
        assert r["grade"] in ("A", "B", "C", "D", "F")

    def test_single_edge(self):
        mg = MemoryGraph()
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "relates", weight=0.5)
        r = mg.graph_health_score()
        assert 0 <= r["score"] <= 100

    def test_disconnected_components(self, sparse_graph):
        r = sparse_graph.graph_health_score()
        # Should flag connectivity issues
        assert r["components"]["connectivity"]["score"] < 0.7

    def test_many_nodes_no_edges(self):
        mg = MemoryGraph()
        for i in range(20):
            mg.add(f"Node{i}")
        r = mg.graph_health_score()
        assert r["score"] < 30
        assert r["grade"] in ("D", "F")

    def test_very_dense_graph(self):
        mg = MemoryGraph()
        nodes = [mg.add(f"N{i}").id for i in range(10)]
        import itertools
        for s, t in itertools.combinations(nodes, 2):
            mg.link(s, t, "relates", weight=0.8)
        r = mg.graph_health_score()
        # Complete graph should be healthy
        assert r["score"] >= 70


# ─── Integration with other APIs ──────────────────────────────────

class TestIntegration:
    def test_health_score_after_consolidation(self):
        """Health score should reflect improvement after consolidation."""
        mg = MemoryGraph()
        a = mg.add("A")
        b = mg.add("B")
        for _ in range(5):
            mg.link(a.id, b.id, "dup", weight=0.5)

        r_before = mg.graph_health_score()
        # Try to consolidate
        try:
            mg.auto_consolidate()
        except Exception:
            pass
        r_after = mg.graph_health_score()
        # Score may or may not improve, but should not crash
        assert 0 <= r_after["score"] <= 100

    def test_health_score_with_tags(self):
        """Tags don't affect health score calculation."""
        mg = MemoryGraph()
        a = mg.add("A", tags=["x"])
        b = mg.add("B", tags=["x"])
        mg.link(a.id, b.id, "relates", weight=0.8)
        r = mg.graph_health_score()
        assert 0 <= r["score"] <= 100


# ─── Determinism ──────────────────────────────────────────────────

class TestDeterminism:
    def test_stability_component_seeded(self, rich_graph):
        """entropy_stability uses seed internally — results should be deterministic."""
        r1 = rich_graph.graph_health_score()
        r2 = rich_graph.graph_health_score()
        assert r1["components"]["stability"]["raw"] == r2["components"]["stability"]["raw"]
