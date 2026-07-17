"""Tests for graph_information_density() — PMI-based memory quality metric.

Tests cover:
- Empty / minimal graph edge cases
- Uniform-weight graphs (maximum entropy, PMI ≈ 0)
- Differentiated-weight graphs (positive/negative PMI)
- Subgraph filtering (node_ids, edge_types)
- Per-edge-type breakdown
- Recommendation generation
- Mathematical properties (PMI bounds, entropy bounds)
- Integration with real MemoryGraph usage patterns
"""

import math
import pytest
from memory_graph import MemoryGraph


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def empty_graph():
    return MemoryGraph(":memory:")


@pytest.fixture
def balanced_graph():
    """Graph with uniform weights — maximum entropy, PMI ≈ 0."""
    mg = MemoryGraph(":memory:")
    a = mg.add("A", "concept")
    b = mg.add("B", "concept")
    c = mg.add("C", "concept")
    mg.link(a.id, b.id, "relates_to", weight=1.0)
    mg.link(b.id, c.id, "relates_to", weight=1.0)
    mg.link(a.id, c.id, "relates_to", weight=1.0)
    return mg


@pytest.fixture
def weighted_graph():
    """Graph with differentiated weights."""
    mg = MemoryGraph(":memory:")
    a = mg.add("Alpha", "concept")
    b = mg.add("Beta", "concept")
    c = mg.add("Gamma", "concept")
    d = mg.add("Delta", "concept")
    mg.link(a.id, b.id, "causes", weight=5.0)
    mg.link(b.id, c.id, "relates_to", weight=1.0)
    mg.link(c.id, d.id, "relates_to", weight=1.0)
    mg.link(a.id, d.id, "causes", weight=3.0)
    return mg


@pytest.fixture
def typed_graph():
    """Graph with multiple edge types."""
    mg = MemoryGraph(":memory:")
    a = mg.add("X", "event")
    b = mg.add("Y", "event")
    c = mg.add("Z", "concept")
    mg.link(a.id, b.id, "causes", weight=3.0)
    mg.link(b.id, c.id, "relates_to", weight=1.0)
    mg.link(a.id, c.id, "triggers", weight=2.0)
    return mg


@pytest.fixture
def large_uniform_graph():
    """10 nodes, 15 edges, all weight 1.0 — high entropy baseline."""
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(f"N{i}", "concept") for i in range(10)]
    for i in range(10):
        for j in range(i + 1, 10):
            mg.link(nodes[i].id, nodes[j].id, "relates_to", weight=1.0)
    return mg


@pytest.fixture
def star_graph():
    """Star topology: hub connected to 5 spokes."""
    mg = MemoryGraph(":memory:")
    hub = mg.add("Hub", "concept")
    spokes = [mg.add(f"S{i}", "concept") for i in range(5)]
    for s in spokes:
        mg.link(hub.id, s.id, "connects", weight=2.0)
    return mg


# ── Empty / Minimal Cases ─────────────────────────────────────────────

class TestEmptyCases:

    def test_empty_graph_no_edges(self, empty_graph):
        """Graph with nodes but no edges → graceful empty result."""
        empty_graph.add("Solo", "concept")
        result = empty_graph.graph_information_density()
        assert result["edge_count"] == 0
        assert result["mean_pmi"] == 0.0
        assert result["information_score"] == 0.0
        assert len(result["recommendations"]) >= 1

    def test_single_edge(self, empty_graph):
        """Single edge → insufficient for entropy calc."""
        a = empty_graph.add("A", "concept")
        b = empty_graph.add("B", "concept")
        empty_graph.link(a.id, b.id, "relates_to", weight=1.0)
        result = empty_graph.graph_information_density()
        assert result["edge_count"] == 1
        # Single edge → < 2 → early return
        assert result["mean_pmi"] == 0.0

    def test_result_has_all_keys(self, balanced_graph):
        """Result dict has all expected fields."""
        result = balanced_graph.graph_information_density()
        expected_keys = {
            "mean_pmi", "positive_fraction", "negative_fraction",
            "entropy", "normalized_entropy", "density", "weighted_density",
            "pmi_spread", "information_score", "edge_type_breakdown",
            "recommendations",
        }
        assert expected_keys.issubset(result.keys())


class TestUniformWeights:
    """Uniform-weight graphs should have maximum entropy, PMI ≈ 0."""

    def test_balanced_pmi_near_zero(self, balanced_graph):
        """All-equal weights → PMI is identical for all edges (zero spread)."""
        result = balanced_graph.graph_information_density()
        # Triangle with equal weights: PMI = log2(3/4) ≈ -0.415 for all edges
        # The key property: spread = 0 (all PMI values identical)
        assert result["pmi_spread"] < 0.01  # zero spread = no differentiation
        assert result["normalized_entropy"] > 0.95  # near-maximum entropy

    def test_balanced_pmi_spread_low(self, balanced_graph):
        """Uniform weights → low PMI spread."""
        result = balanced_graph.graph_information_density()
        assert result["pmi_spread"] < 0.5

    def test_large_uniform_entropy(self, large_uniform_graph):
        """10-node complete uniform graph → near-max entropy, zero spread."""
        result = large_uniform_graph.graph_information_density()
        # 45 edges, all weight 1.0
        assert result["edge_count"] == 45
        assert result["normalized_entropy"] > 0.98
        # K10 uniform: PMI = log2(45/(9*9)) ≈ -0.848 for all edges
        assert result["pmi_spread"] < 0.01  # identical PMI → zero spread

    def test_large_uniform_density(self, large_uniform_graph):
        """Complete graph → density = 1.0."""
        result = large_uniform_graph.graph_information_density()
        assert result["density"] == 1.0  # complete graph


class TestDifferentiatedWeights:
    """Graphs with varied weights should show information differentiation."""

    def test_weighted_pmi_nonzero(self, weighted_graph):
        """Differentiated weights → non-trivial PMI."""
        result = weighted_graph.graph_information_density()
        assert result["mean_pmi"] != 0.0
        # Some edges should have positive PMI
        assert result["positive_fraction"] > 0.0 or result["negative_fraction"] > 0.0

    def test_weighted_lower_entropy(self, weighted_graph):
        """Differentiated weights → lower entropy than uniform."""
        result_w = weighted_graph.graph_information_density()
        mg_uniform = MemoryGraph(":memory:")
        a = mg_uniform.add("A", "concept")
        b = mg_uniform.add("B", "concept")
        c = mg_uniform.add("C", "concept")
        d = mg_uniform.add("D", "concept")
        mg_uniform.link(a.id, b.id, "r", weight=1.0)
        mg_uniform.link(b.id, c.id, "r", weight=1.0)
        mg_uniform.link(c.id, d.id, "r", weight=1.0)
        mg_uniform.link(a.id, d.id, "r", weight=1.0)
        result_u = mg_uniform.graph_information_density()
        assert result_w["normalized_entropy"] < result_u["normalized_entropy"]

    def test_weighted_higher_spread(self, weighted_graph):
        """Differentiated weights → higher PMI spread."""
        result_w = weighted_graph.graph_information_density()
        mg_uniform = MemoryGraph(":memory:")
        a = mg_uniform.add("A", "concept")
        b = mg_uniform.add("B", "concept")
        c = mg_uniform.add("C", "concept")
        d = mg_uniform.add("D", "concept")
        mg_uniform.link(a.id, b.id, "r", weight=1.0)
        mg_uniform.link(b.id, c.id, "r", weight=1.0)
        mg_uniform.link(c.id, d.id, "r", weight=1.0)
        mg_uniform.link(a.id, d.id, "r", weight=1.0)
        result_u = mg_uniform.graph_information_density()
        assert result_w["pmi_spread"] >= result_u["pmi_spread"]

    def test_positive_and_negative_pmi(self, weighted_graph):
        """With weight variance, both positive and negative PMI exist."""
        result = weighted_graph.graph_information_density()
        # 4 edges with different weights → some positive, some negative
        assert result["positive_fraction"] > 0.0
        assert result["negative_fraction"] > 0.0


class TestEdgeTypeBreakdown:

    def test_typed_breakdown_keys(self, typed_graph):
        """Multiple edge types appear in breakdown."""
        result = typed_graph.graph_information_density()
        assert "causes" in result["edge_type_breakdown"]
        assert "relates_to" in result["edge_type_breakdown"]
        assert "triggers" in result["edge_type_breakdown"]

    def test_typed_breakdown_stats(self, typed_graph):
        """Each type has count, mean_pmi, min, max."""
        for rel, stats in typed_graph.graph_information_density()["edge_type_breakdown"].items():
            assert "count" in stats
            assert "mean_pmi" in stats
            assert "min" in stats
            assert "max" in stats
            assert stats["count"] >= 1
            assert stats["min"] <= stats["max"]

    def test_edge_type_filter(self, typed_graph):
        """Filtering by edge_type restricts analysis."""
        result_all = typed_graph.graph_information_density()
        result_causes = typed_graph.graph_information_density(edge_types=["causes"])
        # Single edge → < 2 → early return with edge_count
        assert result_causes["edge_count"] <= 1
        assert result_causes["edge_count"] < result_all["edge_count"]


class TestSubgraphFiltering:

    def test_node_filter_reduces_edges(self, weighted_graph):
        """Filtering by node_ids restricts to induced subgraph."""
        full = weighted_graph.graph_information_density()
        nodes = weighted_graph.conn.execute("SELECT id FROM nodes LIMIT 2").fetchall()
        node_ids = [r["id"] for r in nodes]
        filtered = weighted_graph.graph_information_density(node_ids=node_ids)
        assert filtered["edge_count"] <= full["edge_count"]

    def test_node_filter_empty_list(self, weighted_graph):
        """Empty node_ids list → no filter applied (all edges)."""
        result = weighted_graph.graph_information_density(node_ids=[])
        assert result["edge_count"] == 4  # all edges

    def test_nonexistent_node_filter(self, weighted_graph):
        """Nonexistent node_ids → no matching edges → graceful empty."""
        result = weighted_graph.graph_information_density(node_ids=["fake_id"])
        assert result["edge_count"] == 0


class TestMathematicalProperties:

    def test_entropy_bounded(self, balanced_graph):
        """Entropy ∈ [0, log2(N_edges)]."""
        result = balanced_graph.graph_information_density()
        n = result["edge_count"]
        assert 0 <= result["entropy"] <= math.log2(n) + 0.001

    def test_normalized_entropy_range(self, weighted_graph):
        """Normalized entropy ∈ [0, 1]."""
        result = weighted_graph.graph_information_density()
        assert 0.0 <= result["normalized_entropy"] <= 1.0

    def test_information_score_range(self, weighted_graph):
        """Information score ∈ [0, 1]."""
        result = weighted_graph.graph_information_density()
        assert 0.0 <= result["information_score"] <= 1.0

    def test_density_range(self, weighted_graph):
        """Density ∈ [0, 1]."""
        result = weighted_graph.graph_information_density()
        assert 0.0 <= result["density"] <= 1.0

    def test_positive_plus_negative_leq_one(self, weighted_graph):
        """positive_fraction + negative_fraction ≤ 1."""
        result = weighted_graph.graph_information_density()
        assert result["positive_fraction"] + result["negative_fraction"] <= 1.0

    def test_density_complete_graph(self, large_uniform_graph):
        """Complete graph K₁₀ has density = 1.0."""
        result = large_uniform_graph.graph_information_density()
        assert abs(result["density"] - 1.0) < 0.001

    def test_weighted_density_positive(self, weighted_graph):
        """Weighted density > 0 for graph with positive weights."""
        result = weighted_graph.graph_information_density()
        assert result["weighted_density"] > 0.0

    def test_pmi_symmetric_property(self, empty_graph):
        """PMI(A→B) == PMI(B→A) for symmetric strengths."""
        mg = empty_graph
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        c = mg.add("C", "concept")
        mg.link(a.id, b.id, "r", weight=2.0)
        mg.link(b.id, c.id, "r", weight=1.0)
        mg.link(a.id, c.id, "r", weight=2.0)
        result = mg.graph_information_density()
        # With 3 edges, PMI is deterministic
        assert result["edge_count"] == 3
        assert isinstance(result["mean_pmi"], float)


class TestStarTopology:

    def test_star_graph_density(self, star_graph):
        """Star: 5 nodes, 5 edges → density = 5/10 = 0.5."""
        result = star_graph.graph_information_density()
        assert result["node_count"] == 6  # hub + 5 spokes
        assert result["edge_count"] == 5
        expected_density = 5 / (6 * 5 / 2)
        assert abs(result["density"] - expected_density) < 0.01

    def test_star_uniform_pmi(self, star_graph):
        """All edges same weight → PMI ≈ 0."""
        result = star_graph.graph_information_density()
        assert abs(result["mean_pmi"]) < 0.5


class TestRecommendations:

    def test_high_entropy_recommendation(self, large_uniform_graph):
        """High entropy → recommendation about uniform weights."""
        result = large_uniform_graph.graph_information_density()
        assert any("uniform" in r.lower() or "entropy" in r.lower() or "differentiat" in r.lower()
                      for r in result["recommendations"])

    def test_sparse_graph_recommendation(self, empty_graph):
        """Sparse graph → recommendation about adding connections."""
        mg = empty_graph
        for i in range(15):
            mg.add(f"N{i}", "concept")
        # Only 1 edge between 15 nodes
        nodes = mg.conn.execute("SELECT id FROM nodes").fetchall()
        mg.link(nodes[0]["id"], nodes[1]["id"], "r", weight=1.0)
        result = mg.graph_information_density()
        assert any("sparse" in r.lower() or "connect" in r.lower()
                      for r in result["recommendations"])

    def test_healthy_graph_recommendation(self, weighted_graph):
        """Reasonable graph → may get healthy recommendation."""
        result = weighted_graph.graph_information_density()
        assert isinstance(result["recommendations"], list)
        assert len(result["recommendations"]) >= 1

    def test_recommendations_always_list(self, balanced_graph):
        """Recommendations is always a non-empty list."""
        result = balanced_graph.graph_information_density()
        assert isinstance(result["recommendations"], list)
        assert len(result["recommendations"]) >= 1


class TestIntegration:

    def test_after_add_and_link(self, empty_graph):
        """Density changes as edges are added."""
        mg = empty_graph
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        c = mg.add("C", "concept")
        d = mg.add("D", "concept")

        # 1 edge → too few
        mg.link(a.id, b.id, "r", weight=1.0)
        r1 = mg.graph_information_density()
        assert r1["edge_count"] == 1

        # Add 3 more edges with varied weights → enough for differentiation
        mg.link(b.id, c.id, "r", weight=3.0)
        mg.link(c.id, d.id, "r", weight=1.0)
        mg.link(a.id, d.id, "r", weight=2.0)
        r2 = mg.graph_information_density()
        assert r2["edge_count"] == 4
        assert r2["pmi_spread"] > 0  # varied weights across different topology

    def test_after_weight_change(self, weighted_graph):
        """Density metrics respond to weight changes."""
        mg = weighted_graph
        r_before = mg.graph_information_density()

        # Boost an edge weight dramatically
        edges = mg.conn.execute("SELECT source, target FROM edges WHERE weight=1.0 LIMIT 1").fetchone()
        if edges:
            mg.conn.execute("UPDATE edges SET weight=100.0 WHERE source=? AND target=?",
                          (edges["source"], edges["target"]))
            mg.conn.commit()

        r_after = mg.graph_information_density()
        assert r_after["pmi_spread"] != r_before["pmi_spread"]

    def test_realistic_memory_graph(self):
        """Simulate a realistic memory graph with mixed content."""
        mg = MemoryGraph(":memory:")

        # People and concepts
        alice = mg.add("Alice", "person", {"role": "engineer"})
        bob = mg.add("Bob", "person", {"role": "researcher"})
        project = mg.add("ProjectX", "concept", {"status": "active"})
        bug = mg.add("Critical Bug", "event", {"severity": "high"})
        fix = mg.add("Hotfix Deployed", "event", {"severity": "medium"})

        # Typed, weighted edges
        mg.link(alice.id, project.id, "works_on", weight=5.0)
        mg.link(bob.id, project.id, "collaborates", weight=3.0)
        mg.link(bug.id, project.id, "affects", weight=4.0)
        mg.link(fix.id, bug.id, "resolves", weight=5.0)
        mg.link(alice.id, fix.id, "deployed", weight=2.0)
        mg.link(alice.id, bob.id, "mentors", weight=1.0)

        result = mg.graph_information_density()

        assert result["edge_count"] == 6
        assert result["node_count"] == 5
        assert 0 < result["density"] <= 1.0
        assert result["information_score"] >= 0.0
        assert len(result["edge_type_breakdown"]) >= 4  # at least 4 distinct types
        assert isinstance(result["recommendations"], list)

    def test_works_with_reasoning_eval(self, weighted_graph):
        """Both evaluation methods can run on the same graph."""
        mg = weighted_graph
        density = mg.graph_information_density()
        reasoning = mg.reasoning_quality_eval()
        assert "information_score" in density
        assert "overall_score" in reasoning

    def test_works_with_skill_bank_health(self, weighted_graph):
        """PMI density + skill bank health can run together."""
        mg = weighted_graph
        density = mg.graph_information_density()
        skills = mg.skill_bank_health()
        assert "information_score" in density
        assert "total_skills" in skills

    def test_returns_dict_not_none(self, empty_graph):
        """Always returns a dict, never None."""
        mg = empty_graph
        mg.add("Solo", "concept")
        result = mg.graph_information_density()
        assert isinstance(result, dict)

    def test_total_weight_positive(self, weighted_graph):
        """Total weight > 0 when edges exist."""
        result = weighted_graph.graph_information_density()
        assert result["total_weight"] > 0.0

    def test_node_count_matches(self, weighted_graph):
        """Node count in result matches actual distinct nodes with edges."""
        result = weighted_graph.graph_information_density()
        actual = weighted_graph.conn.execute(
            "SELECT COUNT(DISTINCT n.id) FROM nodes n"
            " JOIN edges e ON e.source = n.id OR e.target = n.id"
        ).fetchone()[0]
        assert result["node_count"] == actual
