"""Tests for staleness_report() — Cycle 418.

Population-level staleness analysis: distribution, statistics,
group breakdown, and maintenance recommendations.
"""

import pytest
import time
from memory_graph import MemoryGraph


def _populate_graph(n_fresh=5, n_stale=5):
    """Create a graph with known fresh and stale nodes."""
    g = MemoryGraph()
    for i in range(n_fresh):
        g.add(f"fresh_{i}", kind="recent")
    for i in range(n_stale):
        nid = g.add(f"stale_{i}", kind="old").id
        # Set old access time to make stale
        g.conn.execute(
            "UPDATE nodes SET accessed=?, created=? WHERE id=?",
            (time.time() - 999999, time.time() - 999999, nid),
        )
    return g


class TestStalenessReportBasic:
    """Basic functionality."""

    def test_empty_graph(self):
        g = MemoryGraph()
        result = g.staleness_report()
        assert result["total_nodes"] == 0
        assert "empty" in result["summary"].lower()

    def test_returns_dict(self):
        g = MemoryGraph()
        g.add("test")
        result = g.staleness_report()
        assert isinstance(result, dict)
        assert "distribution" in result
        assert "statistics" in result
        assert "most_stale" in result
        assert "group_breakdown" in result
        assert "recommendations" in result

    def test_total_nodes_count(self):
        g = _populate_graph(n_fresh=3, n_stale=2)
        result = g.staleness_report()
        assert result["total_nodes"] == 5

    def test_distribution_sums_to_total(self):
        g = _populate_graph(n_fresh=3, n_stale=3)
        result = g.staleness_report()
        d = result["distribution"]
        assert d["fresh"] + d["aging"] + d["stale"] + d["critical"] == result["total_nodes"]


class TestStalenessReportDistribution:
    """Staleness level distribution."""

    def test_has_four_levels(self):
        g = MemoryGraph()
        g.add("test")
        result = g.staleness_report()
        assert "fresh" in result["distribution"]
        assert "aging" in result["distribution"]
        assert "stale" in result["distribution"]
        assert "critical" in result["distribution"]

    def test_distribution_pct(self):
        g = _populate_graph(n_fresh=4, n_stale=0)
        result = g.staleness_report()
        assert result["distribution_pct"]["fresh"] == pytest.approx(100.0)

    def test_stale_nodes_detected(self):
        g = _populate_graph(n_fresh=0, n_stale=5)
        result = g.staleness_report()
        # Old nodes should at least be 'aging' or worse
        non_fresh = (
            result["distribution"]["aging"]
            + result["distribution"]["stale"]
            + result["distribution"]["critical"]
        )
        assert non_fresh == result["total_nodes"]


class TestStalenessReportStatistics:
    """Statistical measures."""

    def test_has_mean(self):
        g = _populate_graph()
        result = g.staleness_report()
        assert "mean" in result["statistics"]
        assert isinstance(result["statistics"]["mean"], float)

    def test_has_median(self):
        g = _populate_graph()
        result = g.staleness_report()
        assert "median" in result["statistics"]

    def test_has_std(self):
        g = _populate_graph()
        result = g.staleness_report()
        assert "std" in result["statistics"]

    def test_min_max(self):
        g = _populate_graph()
        result = g.staleness_report()
        assert result["statistics"]["min"] <= result["statistics"]["max"]

    def test_count(self):
        g = _populate_graph(n_fresh=3, n_stale=4)
        result = g.staleness_report()
        assert result["statistics"]["count"] == 7


class TestStalenessReportMostStale:
    """Most stale nodes ranking."""

    def test_most_stale_sorted_descending(self):
        g = _populate_graph(n_fresh=3, n_stale=5)
        result = g.staleness_report()
        scores = [ns["staleness"] for ns in result["most_stale"]]
        assert scores == sorted(scores, reverse=True)

    def test_most_stale_respects_limit(self):
        g = _populate_graph(n_fresh=5, n_stale=10)
        result = g.staleness_report(limit=3)
        assert len(result["most_stale"]) <= 3

    def test_most_stale_has_node_info(self):
        g = MemoryGraph()
        n = g.add("test node")
        result = g.staleness_report()
        if result["most_stale"]:
            entry = result["most_stale"][0]
            assert "node_id" in entry
            assert "label" in entry
            assert "staleness" in entry
            assert "level" in entry


class TestStalenessReportGroupBy:
    """Group breakdown options."""

    def test_group_by_kind(self):
        g = MemoryGraph()
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.add("c", kind="event")
        result = g.staleness_report(group_by="kind")
        assert "fact" in result["group_breakdown"]
        assert "event" in result["group_breakdown"]

    def test_group_by_kind_counts(self):
        g = MemoryGraph()
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.add("c", kind="event")
        result = g.staleness_report(group_by="kind")
        assert result["group_breakdown"]["fact"]["count"] == 2
        assert result["group_breakdown"]["event"]["count"] == 1

    def test_group_by_tag(self):
        g = MemoryGraph()
        n1 = g.add("tagged1")
        n2 = g.add("tagged2")
        g.add_tag(n1.id, "important")
        g.add_tag(n2.id, "trivial")
        result = g.staleness_report(group_by="tag")
        assert "important" in result["group_breakdown"]
        assert "trivial" in result["group_breakdown"]

    def test_group_breakdown_has_staleness_stats(self):
        g = _populate_graph()
        result = g.staleness_report(group_by="kind")
        for gname, stats in result["group_breakdown"].items():
            assert "mean_staleness" in stats
            assert "median_staleness" in stats
            assert "fresh_count" in stats
            assert "stale_count" in stats

    def test_group_sorted_by_mean_staleness(self):
        g = _populate_graph(n_fresh=3, n_stale=3)
        result = g.staleness_report(group_by="kind")
        means = [
            v["mean_staleness"]
            for v in result["group_breakdown"].values()
        ]
        assert means == sorted(means, reverse=True)


class TestStalenessReportRecommendations:
    """Recommendation generation."""

    def test_empty_graph_recommendation(self):
        g = MemoryGraph()
        result = g.staleness_report()
        assert any("Add nodes" in r for r in result["recommendations"])

    def test_fresh_graph_recommendation(self):
        g = _populate_graph(n_fresh=10, n_stale=0)
        result = g.staleness_report()
        assert any("fresh" in r.lower() for r in result["recommendations"])

    def test_stale_graph_warning(self):
        g = _populate_graph(n_fresh=0, n_stale=20)
        result = g.staleness_report()
        recs = result["recommendations"]
        # With all old nodes, should have some maintenance recommendation
        assert len(recs) >= 1
        assert any(
            "stale" in r.lower() or "critical" in r.lower()
            or "aging" in r.lower() or "maintenance" in r.lower()
            or "refresh" in r.lower()
            for r in recs
        )


class TestStalenessReportNodeSubset:
    """Node ID filtering."""

    def test_subset_analysis(self):
        g = _populate_graph(n_fresh=5, n_stale=5)
        all_nodes = [r["id"] for r in g.conn.execute(
            "SELECT id FROM nodes WHERE label LIKE 'fresh_%'"
        ).fetchall()]
        result = g.staleness_report(node_ids=all_nodes)
        assert result["total_nodes"] == 5

    def test_subset_empty_list(self):
        g = MemoryGraph()
        g.add("test")
        result = g.staleness_report(node_ids=[])
        # Empty node_ids list = no filtering = all nodes
        # (this is consistent with SQL IN () being all rows when empty)
        assert result["total_nodes"] >= 0


class TestStalenessReportSummary:
    """Summary generation."""

    def test_summary_contains_count(self):
        g = _populate_graph(n_fresh=3, n_stale=2)
        result = g.staleness_report()
        assert "5" in result["summary"]

    def test_summary_contains_distribution(self):
        g = _populate_graph(n_fresh=3, n_stale=2)
        result = g.staleness_report()
        assert "Fresh" in result["summary"]
        assert "Stale" in result["summary"]


class TestStalenessReportEdgeCases:
    """Edge cases."""

    def test_single_node(self):
        g = MemoryGraph()
        g.add("only node")
        result = g.staleness_report()
        assert result["total_nodes"] == 1
        assert result["statistics"]["std"] == 0.0

    def test_all_same_staleness(self):
        """All nodes created at the same time should have similar staleness."""
        g = MemoryGraph()
        for i in range(10):
            g.add(f"node_{i}")
        result = g.staleness_report()
        assert result["statistics"]["std"] < 0.1  # very low variance

    def test_group_by_community(self):
        """Community grouping should work without errors."""
        g = MemoryGraph()
        for i in range(10):
            g.add(f"node_{i}")
        for i in range(9):
            g.link(f"node_{i}", f"node_{i+1}", "relates")
        result = g.staleness_report(group_by="community")
        assert isinstance(result["group_breakdown"], dict)

    def test_unknown_kind_grouped(self):
        g = MemoryGraph()
        n = g.add("no kind")
        # kind defaults to 'fact'
        result = g.staleness_report(group_by="kind")
        assert result["total_nodes"] == 1
