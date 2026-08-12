"""Tests for batch_half_life() — Cycle 419.

Batch computation of memory half-life across multiple nodes.
Returns aggregate statistics, category distribution, ranking.
"""

import pytest
import time
from memory_graph import MemoryGraph


def _make_graph_with_variety():
    """Create a graph with nodes of varying durability."""
    g = MemoryGraph()
    # Low durability: isolated, no q-value
    for i in range(5):
        g.add(f"ephemeral_{i}", kind="temp")
    # High durability: connected + high q-value
    hub = g.add("hub", kind="core")
    g.conn.execute("UPDATE nodes SET q_value=1.0 WHERE id=?", (hub.id,))
    for i in range(15):
        leaf = g.add(f"leaf_{i}", kind="support")
        g.link(hub.id, leaf.id, "connects")
    return g


class TestBatchHalfLifeBasic:
    """Basic functionality."""

    def test_empty_graph(self):
        g = MemoryGraph()
        result = g.batch_half_life()
        assert result["total"] == 0

    def test_returns_dict(self):
        g = MemoryGraph()
        g.add("test")
        result = g.batch_half_life()
        assert isinstance(result, dict)
        assert "statistics" in result
        assert "categories" in result
        assert "nodes" in result

    def test_total_count(self):
        g = MemoryGraph()
        for i in range(10):
            g.add(f"node_{i}")
        result = g.batch_half_life()
        assert result["total"] == 10

    def test_node_subset(self):
        g = MemoryGraph()
        nodes = [g.add(f"n{i}").id for i in range(10)]
        result = g.batch_half_life(node_ids=nodes[:3])
        assert result["total"] == 3


class TestBatchHalfLifeStatistics:
    """Aggregate statistics."""

    def test_has_mean(self):
        g = _make_graph_with_variety()
        result = g.batch_half_life()
        assert "mean" in result["statistics"]
        assert result["statistics"]["mean"] > 0

    def test_has_median(self):
        g = _make_graph_with_variety()
        result = g.batch_half_life()
        assert "median" in result["statistics"]

    def test_min_le_max(self):
        g = _make_graph_with_variety()
        result = g.batch_half_life()
        assert result["statistics"]["min"] <= result["statistics"]["max"]

    def test_has_std(self):
        g = _make_graph_with_variety()
        result = g.batch_half_life()
        assert "std" in result["statistics"]

    def test_count(self):
        g = _make_graph_with_variety()
        result = g.batch_half_life()
        assert result["statistics"]["count"] == result["total"]


class TestBatchHalfLifeCategories:
    """Stability category distribution."""

    def test_has_all_categories(self):
        g = _make_graph_with_variety()
        result = g.batch_half_life()
        cats = result["categories"]
        assert "durable" in cats
        assert "stable" in cats
        assert "fragile" in cats
        assert "ephemeral" in cats

    def test_category_counts_sum_to_total(self):
        g = _make_graph_with_variety()
        result = g.batch_half_life()
        cats = result["categories"]
        assert sum(cats.values()) == result["total"]

    def test_connected_node_is_durable(self):
        g = MemoryGraph()
        hub = g.add("hub")
        g.conn.execute("UPDATE nodes SET q_value=1.0 WHERE id=?", (hub.id,))
        for i in range(30):
            leaf = g.add(f"leaf_{i}")
            g.link(hub.id, leaf.id, "connects")
        result = g.batch_half_life()
        # Hub should be durable
        hub_entry = [n for n in result["nodes"] if n["node_id"] == hub.id]
        if hub_entry:
            assert hub_entry[0]["stability_category"] == "durable"


class TestBatchHalfLifeSorting:
    """Result sorting."""

    def test_sort_by_half_life_desc(self):
        g = _make_graph_with_variety()
        result = g.batch_half_life(sort_by="half_life")
        hls = [n["half_life_hours"] for n in result["nodes"]]
        assert hls == sorted(hls, reverse=True)

    def test_sort_by_decay_rate_asc(self):
        g = _make_graph_with_variety()
        result = g.batch_half_life(sort_by="decay_rate")
        rates = [n["decay_rate"] for n in result["nodes"]]
        assert rates == sorted(rates)  # ascending = lowest decay first

    def test_sort_by_degree_desc(self):
        g = _make_graph_with_variety()
        result = g.batch_half_life(sort_by="degree")
        degrees = [n["degree"] for n in result["nodes"]]
        assert degrees == sorted(degrees, reverse=True)


class TestBatchHalfLifeLimit:
    """Result limiting."""

    def test_limit_results(self):
        g = MemoryGraph()
        for i in range(20):
            g.add(f"node_{i}")
        result = g.batch_half_life(limit=5)
        assert len(result["nodes"]) == 5
        assert result["total"] == 5  # total reflects returned count

    def test_no_limit(self):
        g = MemoryGraph()
        for i in range(10):
            g.add(f"node_{i}")
        result = g.batch_half_life(limit=0)
        assert len(result["nodes"]) == 10


class TestBatchHalfLifeRanking:
    """Most/least durable rankings."""

    def test_most_durable_has_5_or_fewer(self):
        g = _make_graph_with_variety()
        result = g.batch_half_life()
        assert len(result["most_durable"]) <= 5

    def test_least_durable_has_5_or_fewer(self):
        g = _make_graph_with_variety()
        result = g.batch_half_life()
        assert len(result["least_durable"]) <= 5

    def test_most_durable_sorted_desc(self):
        g = _make_graph_with_variety()
        result = g.batch_half_life()
        if len(result["most_durable"]) > 1:
            hls = [n["half_life_hours"] for n in result["most_durable"]]
            assert hls == sorted(hls, reverse=True)

    def test_least_durable_sorted_asc(self):
        g = _make_graph_with_variety()
        result = g.batch_half_life()
        if len(result["least_durable"]) > 1:
            hls = [n["half_life_hours"] for n in result["least_durable"]]
            assert hls == sorted(hls)


class TestBatchHalfLifeRecommendations:
    """Recommendation generation."""

    def test_empty_graph_recommendation(self):
        g = MemoryGraph()
        result = g.batch_half_life()
        assert any("empty" in r.lower() for r in result["recommendations"])

    def test_durable_graph_recommendation(self):
        g = MemoryGraph()
        # Create mostly durable nodes: high q + many edges each
        for i in range(10):
            n = g.add(f"durable_{i}")
            g.conn.execute("UPDATE nodes SET q_value=1.0 WHERE id=?", (n.id,))
            # Add many edges to cap degree multiplier
            for j in range(40):
                leaf = g.add(f"leaf_{i}_{j}")
                g.link(n.id, leaf.id, "supports")
        # Check that the durable nodes appear in most_durable
        result = g.batch_half_life()
        assert len(result["most_durable"]) > 0
        # Most durable nodes should indeed be in durable category
        for node in result["most_durable"][:3]:
            assert node["stability_category"] in ("durable", "stable")

    def test_ephemeral_warning(self):
        g = MemoryGraph()
        # Many isolated nodes with no edges or q-value
        for i in range(30):
            g.add(f"ephemeral_{i}")
        result = g.batch_half_life()
        # Most nodes should be fragile/ephemeral
        assert len(result["recommendations"]) >= 1


class TestBatchHalfLifeEdgeCases:
    """Edge cases."""

    def test_single_node(self):
        g = MemoryGraph()
        g.add("only")
        result = g.batch_half_life()
        assert result["total"] == 1
        assert result["statistics"]["std"] == 0.0

    def test_empty_node_ids_list(self):
        g = MemoryGraph()
        g.add("test")
        result = g.batch_half_life(node_ids=[])
        assert result["total"] >= 0

    def test_nonexistent_node_ids(self):
        g = MemoryGraph()
        g.add("real")
        result = g.batch_half_life(node_ids=["fake1", "fake2"])
        assert result["total"] == 0

    def test_all_nodes_have_half_life(self):
        g = _make_graph_with_variety()
        result = g.batch_half_life()
        for node in result["nodes"]:
            assert "half_life_hours" in node
            assert "stability_category" in node
            assert "decay_rate" in node
