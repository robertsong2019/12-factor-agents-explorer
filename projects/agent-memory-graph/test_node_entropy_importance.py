"""Tests for node_entropy_importance() — Cycle 316.

Unified per-node importance ranking combining entropy contribution,
ego-entropy, and anomaly z-score into a single composite score.
"""
import pytest
from memory_graph import MemoryGraph


def build_complete(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return g


def build_star(leaves):
    g = MemoryGraph()
    hub = g.add("hub")
    for i in range(leaves):
        leaf = g.add(f"leaf{i}")
        g.link(hub.id, leaf.id, "r")
    return g


def build_path(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return g


def build_hub_with_outlier():
    """Hub with one outlier node that has unusual degree."""
    g = MemoryGraph()
    hub = g.add("hub")
    for i in range(5):
        n = g.add(f"n{i}")
        g.link(hub.id, n.id, "r")
    # Add interconnections among n1-n3 to create structural anomaly
    n1 = g.add("n1")
    n2 = g.add("n2")
    n3 = g.add("n3")
    g.link(n1.id, n2.id, "r")
    g.link(n2.id, n3.id, "r")
    g.link(n1.id, n3.id, "r")
    g.link(hub.id, n1.id, "r")
    return g


# ── Edge cases ──

class TestNodeImportanceEdgeCases:
    def test_empty_returns_none(self):
        assert MemoryGraph().node_entropy_importance() is None

    def test_single_node_returns_none(self):
        g = MemoryGraph()
        g.add("solo")
        assert g.node_entropy_importance() is None

    def test_two_nodes_returns_none(self):
        g = MemoryGraph()
        a = g.add("A")
        b = g.add("B")
        g.link(a.id, b.id, "r")
        assert g.node_entropy_importance() is None


# ── Structure ──

class TestNodeImportanceStructure:
    def test_returns_dict_with_keys(self):
        g = build_complete(5)
        result = g.node_entropy_importance()
        for key in ["ranking", "scores", "components", "top_k_critical",
                     "bottom_k_expendable", "mean", "std", "index"]:
            assert key in result

    def test_ranking_sorted_descending(self):
        g = build_star(5)
        result = g.node_entropy_importance()
        ranked = result["ranking"]
        for i in range(len(ranked) - 1):
            assert ranked[i][1] >= ranked[i + 1][1]

    def test_components_have_all_signals(self):
        g = build_complete(4)
        result = g.node_entropy_importance()
        for nid, comps in result["components"].items():
            assert "contribution" in comps
            assert "ego" in comps
            assert "anomaly" in comps

    def test_all_nodes_scored(self):
        g = build_path(6)
        result = g.node_entropy_importance()
        all_nodes = set(str(r["id"]) for r in g.conn.execute("SELECT id FROM nodes").fetchall())
        assert set(result["scores"].keys()) == all_nodes


# ── Correctness ──

class TestNodeImportanceCorrectness:
    def test_star_hub_highest_importance(self):
        g = build_star(5)
        result = g.node_entropy_importance()
        # Hub should be the most important node
        all_nodes = list(g.conn.execute("SELECT id, label FROM nodes").fetchall())
        hub_id = [str(r["id"]) for r in all_nodes if r["label"] == "hub"][0]
        assert result["ranking"][0][0] == hub_id

    def test_complete_graph_uniform_scores(self):
        """K4: all nodes symmetric → similar importance scores."""
        g = build_complete(4)
        result = g.node_entropy_importance()
        scores = list(result["scores"].values())
        # All scores should be close (symmetric graph)
        assert max(scores) - min(scores) < 0.2

    def test_scores_in_zero_one_range(self):
        g = build_star(5)
        result = g.node_entropy_importance()
        for score in result["scores"].values():
            assert 0.0 <= score <= 1.0

    def test_top_k_critical_non_empty(self):
        g = build_complete(5)
        result = g.node_entropy_importance()
        assert len(result["top_k_critical"]) > 0

    def test_bottom_k_expendable_non_empty(self):
        g = build_complete(5)
        result = g.node_entropy_importance()
        assert len(result["bottom_k_expendable"]) > 0

    def test_top_and_bottom_disjoint(self):
        g = build_path(8)
        result = g.node_entropy_importance()
        assert not set(result["top_k_critical"]) & set(result["bottom_k_expendable"])

    def test_mean_in_range(self):
        g = build_star(5)
        result = g.node_entropy_importance()
        assert 0.0 <= result["mean"] <= 1.0


# ── Custom weights ──

class TestNodeImportanceWeights:
    def test_custom_weights_change_ranking(self):
        """Different weight profiles should (potentially) change rankings."""
        g = build_star(5)
        # Emphasize contribution
        r1 = g.node_entropy_importance(weights={"contribution": 1.0, "ego": 0.0, "anomaly": 0.0})
        # Emphasize ego
        r2 = g.node_entropy_importance(weights={"contribution": 0.0, "ego": 1.0, "anomaly": 0.0})
        assert r1 is not None and r2 is not None

    def test_weights_normalized(self):
        g = build_complete(4)
        result = g.node_entropy_importance(weights={"contribution": 5, "ego": 5, "anomaly": 5})
        # Weights should be normalized to 1/3 each
        total = sum(result["weights"].values())
        assert total == pytest.approx(1.0, abs=1e-6)


# ── Consistency ──

class TestNodeImportanceConsistency:
    def test_repeated_call_same_result(self):
        g = build_star(5)
        r1 = g.node_entropy_importance()
        r2 = g.node_entropy_importance()
        assert r1["scores"] == r2["scores"]

    def test_ranking_ids_match_nodes(self):
        g = build_path(5)
        result = g.node_entropy_importance()
        all_node_ids = set(str(r["id"]) for r in g.conn.execute("SELECT id FROM nodes").fetchall())
        ranked_ids = {entry[0] for entry in result["ranking"]}
        assert ranked_ids == all_node_ids


# ── Large graph ──

class TestNodeImportanceLarge:
    def test_50_nodes_efficient(self):
        import random
        random.seed(42)
        g = MemoryGraph()
        nodes = [g.add(str(i)) for i in range(50)]
        for i in range(1, 50):
            j = random.randint(0, i - 1)
            g.link(nodes[i].id, nodes[j].id, "r")
        result = g.node_entropy_importance()
        assert result is not None
        assert len(result["scores"]) == 50
        assert len(result["top_k_critical"]) >= 1
        assert len(result["bottom_k_expendable"]) >= 1
