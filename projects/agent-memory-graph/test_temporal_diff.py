"""Tests for temporal_diff() — graph evolution between two timestamps.

Measures node/edge churn, growth rate, and phase classification.
Bridges temporal queries with structural analysis.
"""
import time
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def evolving_graph():
    """Build a graph that evolves over time, returning snapshots at key moments."""
    mg = MemoryGraph(":memory:")

    t_start = time.time()
    a = mg.add("Alpha", "concept")
    b = mg.add("Beta", "concept")
    mg.link(a.id, b.id, "knows")
    mg.node_set_validity(a.id, valid_from=t_start)
    mg.node_set_validity(b.id, valid_from=t_start)
    mg.edge_set_validity(a.id, b.id, "knows", valid_from=t_start)

    time.sleep(0.02)
    t_mid = time.time()

    # Growth phase: add more nodes (valid_from AFTER t_mid)
    time.sleep(0.01)
    growth_time = time.time()
    c = mg.add("Gamma", "concept")
    d = mg.add("Delta", "concept")
    mg.link(b.id, c.id, "knows")
    mg.link(c.id, d.id, "knows")
    mg.node_set_validity(c.id, valid_from=growth_time)
    mg.node_set_validity(d.id, valid_from=growth_time)
    mg.edge_set_validity(b.id, c.id, "knows", valid_from=growth_time)
    mg.edge_set_validity(c.id, d.id, "knows", valid_from=growth_time)

    time.sleep(0.02)
    t_late = time.time()

    # Decay phase: supersede a node
    mg.supersede(b.id, new_label="Beta-v2")

    time.sleep(0.02)
    t_end = time.time()

    return {
        "graph": mg,
        "ids": {"a": a.id, "b": b.id, "c": c.id, "d": d.id},
        "times": {"start": t_start, "mid": t_mid, "growth": growth_time, "late": t_late, "end": t_end},
    }


class TestTemporalDiffStructure:
    def test_returns_dict(self, evolving_graph):
        mg = evolving_graph["graph"]
        t = evolving_graph["times"]
        result = mg.temporal_diff(t["start"], t["end"])
        assert isinstance(result, dict)

    def test_has_all_keys(self, evolving_graph):
        mg = evolving_graph["graph"]
        t = evolving_graph["times"]
        result = mg.temporal_diff(t["start"], t["end"])
        expected_keys = {
            "t1", "t2", "nodes_added", "nodes_removed", "nodes_stable",
            "edges_added", "edges_removed", "edges_stable",
            "node_churn", "edge_churn", "growth_rate", "phase",
        }
        assert expected_keys.issubset(result.keys())

    def test_timestamps_preserved(self, evolving_graph):
        mg = evolving_graph["graph"]
        t = evolving_graph["times"]
        result = mg.temporal_diff(t["mid"], t["late"])
        assert result["t1"] == t["mid"]
        assert result["t2"] == t["late"]


class TestTemporalDiffGrowth:
    def test_growth_phase(self, evolving_graph):
        """From mid to late, nodes C and D were added → growth phase."""
        mg = evolving_graph["graph"]
        ids = evolving_graph["ids"]
        t = evolving_graph["times"]
        result = mg.temporal_diff(t["mid"], t["late"])
        assert result["phase"] == "growth"
        assert result["growth_rate"] > 0
        assert len(result["nodes_added"]) > 0

    def test_growth_node_count(self, evolving_graph):
        mg = evolving_graph["graph"]
        t = evolving_graph["times"]
        result = mg.temporal_diff(t["mid"], t["late"])
        # At least 2 nodes added (C, D)
        assert len(result["nodes_added"]) >= 2


class TestTemporalDiffDecay:
    def test_decay_phase(self, evolving_graph):
        """From late to end, node B was superseded → decay phase."""
        mg = evolving_graph["graph"]
        t = evolving_graph["times"]
        result = mg.temporal_diff(t["late"], t["end"])
        assert result["phase"] in ("decay", "churn")
        assert result["growth_rate"] <= 0

    def test_decay_removes_node(self, evolving_graph):
        mg = evolving_graph["graph"]
        ids = evolving_graph["ids"]
        t = evolving_graph["times"]
        result = mg.temporal_diff(t["late"], t["end"])
        assert ids["b"] in result["nodes_removed"]


class TestTemporalDiffStable:
    def test_stable_phase(self, evolving_graph):
        """Same timestamp should produce stable phase."""
        mg = evolving_graph["graph"]
        t = evolving_graph["times"]["mid"]
        result = mg.temporal_diff(t, t)
        assert result["phase"] == "stable"
        assert result["node_churn"] == 0.0
        assert result["edge_churn"] == 0.0
        assert result["nodes_added"] == []
        assert result["nodes_removed"] == []
        assert result["growth_rate"] == 0.0

    def test_stable_edges(self, evolving_graph):
        mg = evolving_graph["graph"]
        t = evolving_graph["times"]["mid"]
        result = mg.temporal_diff(t, t)
        assert result["edges_added"] == 0
        assert result["edges_removed"] == 0
        assert result["edges_stable"] >= 1


class TestTemporalDiffChurn:
    def test_churn_metrics(self, evolving_graph):
        """Node churn should be between 0 and 2."""
        mg = evolving_graph["graph"]
        t = evolving_graph["times"]
        result = mg.temporal_diff(t["start"], t["end"])
        assert 0 <= result["node_churn"] <= 2.0
        assert 0 <= result["edge_churn"] <= 2.0


class TestTemporalDiffEdges:
    def test_edges_added_in_growth(self, evolving_graph):
        mg = evolving_graph["graph"]
        t = evolving_graph["times"]
        result = mg.temporal_diff(t["mid"], t["late"])
        assert result["edges_added"] >= 2  # B→C and C→D

    def test_edges_stable_count(self, evolving_graph):
        mg = evolving_graph["graph"]
        t = evolving_graph["times"]
        result = mg.temporal_diff(t["mid"], t["late"])
        # The A→B edge existed at both times
        assert result["edges_stable"] >= 1


class TestTemporalDiffEmptyGraph:
    def test_empty_graph_diff(self):
        mg = MemoryGraph(":memory:")
        now = time.time()
        result = mg.temporal_diff(now - 1, now)
        assert result["phase"] == "stable"
        assert result["node_churn"] == 0.0

    def test_empty_to_populated(self):
        mg = MemoryGraph(":memory:")
        t_before = time.time()
        time.sleep(0.01)
        n = mg.add("A", "concept")
        time.sleep(0.01)
        t_after = time.time()
        # query_as_of checks both temporal systems, so we need the
        # node to have valid_from set. Use supersede or SQL approach:
        # Actually temporal_graph_snapshot checks _node_temporal (JSON props)
        # which regular add() doesn't set. Use query_valid_at-based approach:
        result = mg.temporal_diff(t_before, t_after)
        # Without _node_temporal or SQL valid_from, nodes are always valid,
        # so the graph looks the same at both timestamps
        # This is expected behavior — only bi-temporally tracked nodes show up
        assert result["phase"] == "stable"


class TestTemporalDiffReverse:
    def test_reverse_swaps_added_removed(self, evolving_graph):
        """Diff(t1, t2) nodes_added should equal Diff(t2, t1) nodes_removed."""
        mg = evolving_graph["graph"]
        t = evolving_graph["times"]
        forward = mg.temporal_diff(t["mid"], t["late"])
        reverse = mg.temporal_diff(t["late"], t["mid"])
        assert forward["nodes_added"] == reverse["nodes_removed"]
        assert forward["nodes_removed"] == reverse["nodes_added"]


class TestTemporalDiffNodesStable:
    def test_stable_nodes_present_in_both(self, evolving_graph):
        mg = evolving_graph["graph"]
        t = evolving_graph["times"]
        result = mg.temporal_diff(t["mid"], t["late"])
        # Node A and B existed at both mid and late
        assert result["nodes_stable"] >= 2
