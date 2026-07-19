"""Tests for gap_redundancy_balance() — unified dual-loop health metric.

Covers the fusion of knowledge_gap_report.gap_score and
redundancy_detect.redundancy_score into a single actionable assessment.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def balanced_graph():
    """A well-connected graph with minimal gaps and redundancy.

    Nodes have different kinds/tags to avoid functional duplicate triggers,
    but are well-connected to keep gap_score high.
    """
    mg = MemoryGraph()
    a = mg.add("Design Document", "artifact", tags=["architecture"])
    b = mg.add("API Gateway", "service", tags=["infra"])
    c = mg.add("User Database", " datastore", tags=["persistence"])
    d = mg.add("Auth Module", "feature", tags=["security"])
    e = mg.add("Monitoring Dashboard", "tool", tags=["ops"])
    mg.link(a.id, b.id, "describes")
    mg.link(a.id, c.id, "references")
    mg.link(b.id, c.id, "connects_to")
    mg.link(b.id, d.id, "depends_on")
    mg.link(c.id, d.id, "backed_by")
    mg.link(d.id, e.id, "logs_to")
    mg.link(a.id, e.id, "mentions")
    mg.link(b.id, e.id, "monitored_by")
    return mg


@pytest.fixture
def gappy_graph():
    """A graph with many orphans / isolated clusters → high gap, low redundancy."""
    mg = MemoryGraph()
    for i in range(10):
        mg.add(f"Orphan_{i}", "note")
    return mg


@pytest.fixture
def redundant_graph():
    """A graph with many near-duplicate nodes → high redundancy, low gap."""
    mg = MemoryGraph()
    labels = [
        "Python machine learning tutorial",
        "Python machine-learning tutorial",
        "Python ML tutorial guide",
        "Python ML tutorial guide",
    ]
    for lbl in labels:
        mg.add(lbl, "skill", tags=["python", "ml"])
    nodes = [r["id"] for r in mg.conn.execute("SELECT id FROM nodes").fetchall()]
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            mg.link(nodes[i], nodes[j], "similar")
    return mg


@pytest.fixture
def empty_graph():
    return MemoryGraph()


@pytest.fixture
def single_node_graph():
    mg = MemoryGraph()
    mg.add("Solo", "note")
    return mg


class TestGapRedundancyBalance:
    """Core API tests."""

    def test_returns_dict_with_required_keys(self, balanced_graph):
        result = balanced_graph.gap_redundancy_balance()
        assert isinstance(result, dict)
        for key in (
            "health_score", "gap_score", "redundancy_score",
            "verdict", "dominant_issue", "balance_ratio",
            "action_priority", "summary", "recommendations",
        ):
            assert key in result, f"Missing key: {key}"

    def test_empty_graph(self, empty_graph):
        result = empty_graph.gap_redundancy_balance()
        assert result["health_score"] == 100.0
        assert result["verdict"] == "empty"
        assert result["gap_score"] == 100.0
        assert result["redundancy_score"] == 0.0

    def test_single_node_graph(self, single_node_graph):
        result = single_node_graph.gap_redundancy_balance()
        assert isinstance(result["health_score"], float)
        assert 0 <= result["health_score"] <= 100
        # Single node → high gap (orphan), no redundancy
        assert result["redundancy_score"] == 0.0

    def test_balanced_graph_high_health(self, balanced_graph):
        result = balanced_graph.gap_redundancy_balance()
        assert result["health_score"] >= 60.0, (
            f"Expected health ≥60 for balanced graph, got {result['health_score']}"
        )
        assert result["verdict"] in ("healthy", "good")

    def test_gappy_graph_low_health(self, gappy_graph):
        result = gappy_graph.gap_redundancy_balance()
        assert result["health_score"] < 70.0, (
            f"Expected health <70 for gappy graph, got {result['health_score']}"
        )
        # 10 orphans → gap_penalty should dominate unless redundancy also fires
        assert result["gap_score"] < 70.0
        assert result["dominant_issue"] in ("gap", "balanced-issues")

    def test_redundant_graph_flags_redundancy(self, redundant_graph):
        result = redundant_graph.gap_redundancy_balance()
        assert result["redundancy_score"] > 0
        assert result["dominant_issue"] in ("redundancy", "redundancy-heavy", "balanced-issues")

    def test_health_score_bounds(self, balanced_graph):
        result = balanced_graph.gap_redundancy_balance()
        assert 0.0 <= result["health_score"] <= 100.0

    def test_balance_ratio_bounded(self, balanced_graph):
        result = balanced_graph.gap_redundancy_balance()
        ratio = result["balance_ratio"]
        assert -1.0 <= ratio <= 1.0, f"balance_ratio out of bounds: {ratio}"

    def test_action_priority_values(self, balanced_graph):
        result = balanced_graph.gap_redundancy_balance()
        assert result["action_priority"] in ("none", "gap", "redundancy", "both")

    def test_recommendations_is_list(self, balanced_graph):
        result = balanced_graph.gap_redundancy_balance()
        assert isinstance(result["recommendations"], list)
        assert len(result["recommendations"]) >= 1

    def test_summary_is_nonempty_string(self, balanced_graph):
        result = balanced_graph.gap_redundancy_balance()
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 10


class TestGapRedundancyWeights:
    """Test custom weight parameter."""

    def test_custom_gap_weight(self, gappy_graph):
        """Heavy gap weight should make health score lower."""
        default = gappy_graph.gap_redundancy_balance()
        gap_heavy = gappy_graph.gap_redundancy_balance(gap_weight=0.9, redundancy_weight=0.1)
        assert gap_heavy["health_score"] <= default["health_score"] + 0.5

    def test_custom_redundancy_weight(self, redundant_graph):
        """Heavy redundancy weight should make health score lower for redundant graphs."""
        default = redundant_graph.gap_redundancy_balance()
        red_heavy = redundant_graph.gap_redundancy_balance(
            gap_weight=0.1, redundancy_weight=0.9
        )
        assert red_heavy["health_score"] <= default["health_score"] + 0.5

    def test_weights_sum_warning(self, balanced_graph):
        """Weights don't sum to 1.0 should still work (auto-normalised)."""
        result = balanced_graph.gap_redundancy_balance(
            gap_weight=0.3, redundancy_weight=0.3
        )
        assert 0 <= result["health_score"] <= 100


class TestGapRedundancySubgraph:
    """Test node_ids subgraph restriction."""

    def test_subgraph_restriction(self, balanced_graph):
        nodes = [r["id"] for r in balanced_graph.conn.execute(
            "SELECT id FROM nodes LIMIT 2"
        ).fetchall()]
        result = balanced_graph.gap_redundancy_balance(node_ids=nodes)
        assert isinstance(result["health_score"], float)
        assert 0 <= result["health_score"] <= 100


class TestGapRedundancyVerdicts:
    """Verdict classification tests."""

    def test_empty_verdict(self, empty_graph):
        result = empty_graph.gap_redundancy_balance()
        assert result["verdict"] == "empty"

    def test_healthy_verdict(self, balanced_graph):
        result = balanced_graph.gap_redundancy_balance()
        assert result["verdict"] in ("healthy", "good")

    def test_gappy_verdict(self, gappy_graph):
        result = gappy_graph.gap_redundancy_balance()
        # High-gap graphs should NOT be healthy
        assert result["verdict"] != "healthy"

    def test_verdict_is_string(self, balanced_graph):
        result = balanced_graph.gap_redundancy_balance()
        assert isinstance(result["verdict"], str)
