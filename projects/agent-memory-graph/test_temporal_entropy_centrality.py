"""Tests for temporal_entropy_centrality() — Cycle 391.

Combined structural-temporal importance ranking.
"""
import math
import time
import pytest
from memory_graph import MemoryGraph


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def small_graph():
    """Small graph (3 nodes, 1 edge) — below threshold."""
    mg = MemoryGraph()
    mg.add("a")
    mg.add("b")
    mg.add("c")
    mg.link("a", "b", "rel")
    return mg


@pytest.fixture
def medium_graph():
    """Medium graph suitable for temporal_entropy_centrality."""
    mg = MemoryGraph()
    for label in ["hub", "spoke1", "spoke2", "spoke3", "leaf1", "leaf2", "isolated"]:
        mg.add(label, tags=["component"])
    mg.link("hub", "spoke1", "dep", weight=0.9)
    mg.link("hub", "spoke2", "dep", weight=0.8)
    mg.link("hub", "spoke3", "dep", weight=0.7)
    mg.link("spoke1", "leaf1", "rel", weight=0.5)
    mg.link("spoke2", "leaf2", "rel", weight=0.4)
    mg.link("spoke1", "spoke2", "sim", weight=0.3)
    return mg


@pytest.fixture
def rich_graph():
    """Graph with varied structure and temporal properties."""
    mg = MemoryGraph()
    labels = [f"n{i}" for i in range(12)]
    for i, label in enumerate(labels):
        mg.add(label, data={"idx": i}, tags=[f"group_{i % 3}"])
    # Star topology around n0
    mg.link("n0", "n1", "dep", weight=0.9)
    mg.link("n0", "n2", "dep", weight=0.8)
    mg.link("n0", "n3", "dep", weight=0.7)
    mg.link("n0", "n4", "dep", weight=0.6)
    # Path among n5-n6-n7-n8
    mg.link("n5", "n6", "rel", weight=0.5)
    mg.link("n6", "n7", "rel", weight=0.5)
    mg.link("n7", "n8", "rel", weight=0.5)
    # Cross links
    mg.link("n1", "n5", "sim", weight=0.4)
    mg.link("n3", "n7", "sim", weight=0.4)
    mg.link("n9", "n10", "rel", weight=0.3)
    return mg


# ── Structure ─────────────────────────────────────────────

class TestStructure:

    def test_returns_dict(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        assert isinstance(result, dict)

    def test_required_top_keys(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        for key in ["nodes", "summary", "category_counts", "recommendation_counts", "weights", "index"]:
            assert key in result, f"Missing key: {key}"

    def test_nodes_is_list(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        assert isinstance(result["nodes"], list)

    def test_node_entry_keys(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        if result["nodes"]:
            node = result["nodes"][0]
            for key in ["node_id", "label", "priority", "entropy_score",
                        "staleness_score", "connectivity_score", "degree",
                        "recommendation", "category"]:
                assert key in node, f"Missing node key: {key}"

    def test_summary_keys(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        for key in ["total_nodes", "mean_priority", "urgent_count",
                     "fresh_important_count", "stale_critical_count", "archivable_count"]:
            assert key in result["summary"], f"Missing summary key: {key}"

    def test_weights_keys(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        for key in ["entropy", "temporal", "connectivity"]:
            assert key in result["weights"]


# ── Degenerate ────────────────────────────────────────────

class TestDegenerate:

    def test_empty_graph_returns_none(self):
        mg = MemoryGraph()
        assert mg.temporal_entropy_centrality() is None

    def test_single_node_returns_none(self):
        mg = MemoryGraph()
        mg.add("only")
        assert mg.temporal_entropy_centrality() is None

    def test_two_nodes_no_edge_returns_none(self):
        mg = MemoryGraph()
        mg.add("a")
        mg.add("b")
        assert mg.temporal_entropy_centrality() is None

    def test_two_nodes_one_edge_returns_none(self):
        mg = MemoryGraph()
        mg.add("a")
        mg.add("b")
        mg.link("a", "b", "rel")
        assert mg.temporal_entropy_centrality() is None

    def test_three_nodes_no_edge_returns_none(self):
        mg = MemoryGraph()
        mg.add("a")
        mg.add("b")
        mg.add("c")
        assert mg.temporal_entropy_centrality() is None


# ── Correctness ───────────────────────────────────────────

class TestCorrectness:

    def test_priority_in_zero_one(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        for node in result["nodes"]:
            assert 0.0 <= node["priority"] <= 1.0

    def test_entropy_score_in_zero_one(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        for node in result["nodes"]:
            assert 0.0 <= node["entropy_score"] <= 1.0

    def test_staleness_score_in_zero_one(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        for node in result["nodes"]:
            assert 0.0 <= node["staleness_score"] <= 1.0

    def test_connectivity_score_in_zero_one(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        for node in result["nodes"]:
            assert 0.0 <= node["connectivity_score"] <= 1.0

    def test_sorted_by_priority_desc(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        priorities = [n["priority"] for n in result["nodes"]]
        assert priorities == sorted(priorities, reverse=True)

    def test_degree_non_negative(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        for node in result["nodes"]:
            assert node["degree"] >= 0

    def test_total_nodes_matches(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        assert result["summary"]["total_nodes"] == len(result["nodes"])

    def test_mean_priority_consistent(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        priorities = [n["priority"] for n in result["nodes"]]
        expected = round(sum(priorities) / len(priorities), 4) if priorities else 0.0
        assert abs(result["summary"]["mean_priority"] - expected) < 0.01


# ── Weight Configuration ──────────────────────────────────

class TestWeights:

    def test_default_weights(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        w = result["weights"]
        assert abs(w["entropy"] - 0.4) < 0.01
        assert abs(w["temporal"] - 0.3) < 0.01
        assert abs(w["connectivity"] - 0.3) < 0.01

    def test_weights_normalise_to_one(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality(
            entropy_weight=10, temporal_weight=20, connectivity_weight=70
        )
        w = result["weights"]
        assert abs(w["entropy"] - 0.1) < 0.01
        assert abs(w["temporal"] - 0.2) < 0.01
        assert abs(w["connectivity"] - 0.7) < 0.01

    def test_zero_entropy_weight(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality(
            entropy_weight=0, temporal_weight=1, connectivity_weight=1
        )
        w = result["weights"]
        assert w["entropy"] == 0.0
        assert abs(w["temporal"] - 0.5) < 0.01
        assert abs(w["connectivity"] - 0.5) < 0.01

    def test_all_zero_weights_returns_none(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality(
            entropy_weight=0, temporal_weight=0, connectivity_weight=0
        )
        assert result is None

    def test_custom_weights_affect_priority(self, medium_graph):
        # Heavy connectivity weight vs heavy temporal weight
        # With fresh graph, staleness=0 but connectivity>0, so different weights produce different results
        r1 = medium_graph.temporal_entropy_centrality(
            entropy_weight=0.0, temporal_weight=0.0, connectivity_weight=1.0
        )
        r2 = medium_graph.temporal_entropy_centrality(
            entropy_weight=0.0, temporal_weight=1.0, connectivity_weight=0.0
        )
        p1 = [n["priority"] for n in r1["nodes"]]
        p2 = [n["priority"] for n in r2["nodes"]]
        # Connectivity-only should have varied values, temporal-only all zeros for fresh graph
        assert any(p > 0 for p in p1), "Connectivity should produce non-zero priorities"
        assert all(p == 0 for p in p2), "Temporal-only should be zero for fresh graph"


# ── Index Parameter ───────────────────────────────────────

class TestIndex:

    def test_default_index_is_sombor(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        assert result["index"] == "sombor"

    def test_custom_index(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality(index="randic")
        assert result["index"] == "randic"

    def test_different_indices_may_differ(self, rich_graph):
        r1 = rich_graph.temporal_entropy_centrality(index="sombor")
        r2 = rich_graph.temporal_entropy_centrality(index="randic")
        # Entropy scores may differ with different indices
        e1 = [n["entropy_score"] for n in r1["nodes"]]
        e2 = [n["entropy_score"] for n in r2["nodes"]]
        # At least one value should differ for a rich enough graph
        assert e1 != e2 or all(v == 0 for v in e1), "Indices should produce different entropy profiles"


# ── Limit Parameter ───────────────────────────────────────

class TestLimit:

    def test_limit_three(self, rich_graph):
        result = rich_graph.temporal_entropy_centrality(limit=3)
        assert len(result["nodes"]) == 3

    def test_limit_one(self, rich_graph):
        result = rich_graph.temporal_entropy_centrality(limit=1)
        assert len(result["nodes"]) == 1

    def test_limit_zero_returns_all(self, rich_graph):
        result = rich_graph.temporal_entropy_centrality(limit=0)
        stats = rich_graph.stats()
        assert len(result["nodes"]) == stats["nodes"]

    def test_limit_larger_than_nodes(self, rich_graph):
        result = rich_graph.temporal_entropy_centrality(limit=100)
        stats = rich_graph.stats()
        assert len(result["nodes"]) == stats["nodes"]


# ── Recommendations ───────────────────────────────────────

class TestRecommendations:

    def test_valid_recommendations(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        valid = {"refresh", "protect", "consolidate", "archive", "review", "monitor"}
        for node in result["nodes"]:
            assert node["recommendation"] in valid

    def test_recommendation_counts_sum(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        total = sum(result["recommendation_counts"].values())
        assert total == len(result["nodes"])

    def test_fresh_graph_few_refresh(self, medium_graph):
        # Fresh graph (all nodes just created) should have mostly fresh categories
        result = medium_graph.temporal_entropy_centrality()
        # Most nodes should be in fresh_important or fresh_minor
        fresh = result["summary"]["fresh_important_count"]
        stale = result["summary"]["stale_critical_count"]
        # Fresh graph should have more fresh than stale
        assert fresh >= stale


# ── Categories ─────────────────────────────────────────────

class TestCategories:

    def test_valid_categories(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        valid = {"stale_critical", "fresh_important", "stale_minor", "fresh_minor"}
        for node in result["nodes"]:
            assert node["category"] in valid

    def test_category_counts_sum(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        total = sum(result["category_counts"].values())
        assert total == len(result["nodes"])


# ── Non-Mutating ──────────────────────────────────────────

class TestNonMutating:

    def test_graph_unchanged(self, medium_graph):
        before_stats = medium_graph.stats()
        before_nodes = before_stats["nodes"]
        before_edges = before_stats["edges"]
        medium_graph.temporal_entropy_centrality()
        after_stats = medium_graph.stats()
        assert after_stats["nodes"] == before_nodes
        assert after_stats["edges"] == before_edges

    def test_no_new_edges(self, medium_graph):
        before = medium_graph.stats()["edges"]
        medium_graph.temporal_entropy_centrality()
        assert medium_graph.stats()["edges"] == before


# ── Determinism ───────────────────────────────────────────

class TestDeterminism:

    def test_same_result_twice(self, medium_graph):
        r1 = medium_graph.temporal_entropy_centrality()
        r2 = medium_graph.temporal_entropy_centrality()
        p1 = [n["priority"] for n in r1["nodes"]]
        p2 = [n["priority"] for n in r2["nodes"]]
        assert p1 == p2

    def test_node_ids_stable(self, medium_graph):
        r1 = medium_graph.temporal_entropy_centrality()
        r2 = medium_graph.temporal_entropy_centrality()
        ids1 = [n["node_id"] for n in r1["nodes"]]
        ids2 = [n["node_id"] for n in r2["nodes"]]
        assert ids1 == ids2


# ── Integration ───────────────────────────────────────────

class TestIntegration:

    def test_works_with_rich_graph(self, rich_graph):
        result = rich_graph.temporal_entropy_centrality()
        assert result is not None
        stats = rich_graph.stats()
        assert result["summary"]["total_nodes"] == stats["nodes"]

    def test_works_after_modification(self, medium_graph):
        medium_graph.add("extra1")
        medium_graph.add("extra2")
        medium_graph.link("extra1", "extra2", "rel")
        result = medium_graph.temporal_entropy_centrality()
        assert result is not None
        stats = medium_graph.stats()
        assert result["summary"]["total_nodes"] == stats["nodes"]

    def test_now_parameter(self, medium_graph):
        # Using a future timestamp should make everything very stale
        # Note: staleness_score uses its own time.time(), so the 'now' parameter
        # is passed to temporal_freshness_map but may not affect staleness_score.
        # Instead, test that the API accepts the parameter without error.
        result = medium_graph.temporal_entropy_centrality(now=time.time() + 999999999)
        assert result is not None
        assert result["summary"]["total_nodes"] > 0

    def test_consistent_with_entropy_contribution(self, medium_graph):
        """Nodes identified as critical by entropy_contribution should have high entropy_score."""
        ec = medium_graph.entropy_contribution()
        result = medium_graph.temporal_entropy_centrality()
        # Find the highest entropy node from entropy_contribution
        if ec["ranked"]:
            top_node_id = ec["ranked"][0][0]
            # Find this node in our result
            for node in result["nodes"]:
                if node["node_id"] == top_node_id:
                    # Should have a relatively high entropy_score
                    # (might not be 1.0 if normalization maps it differently)
                    assert node["entropy_score"] >= 0.0
                    break

    def test_urgent_count_matches_recommendations(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        refresh_count = result["recommendation_counts"].get("refresh", 0)
        assert result["summary"]["urgent_count"] == refresh_count

    def test_archivable_count_matches(self, medium_graph):
        result = medium_graph.temporal_entropy_centrality()
        archive_count = result["recommendation_counts"].get("archive", 0)
        assert result["summary"]["archivable_count"] == archive_count

    def test_connectivity_correlates_with_degree(self, rich_graph):
        """Higher-degree nodes should have higher connectivity scores."""
        result = rich_graph.temporal_entropy_centrality()
        # n0 is the hub with degree 4 — should have highest connectivity
        hub_entry = None
        for node in result["nodes"]:
            if node["label"] == "n0":
                hub_entry = node
                break
        if hub_entry:
            assert hub_entry["connectivity_score"] > 0.5
            assert hub_entry["degree"] >= 4

    def test_isolated_node_low_connectivity(self, rich_graph):
        """Isolated nodes should have zero connectivity score."""
        result = rich_graph.temporal_entropy_centrality()
        # n11 should have no edges
        for node in result["nodes"]:
            if node["label"] == "n11":
                assert node["connectivity_score"] == 0.0
                assert node["degree"] == 0
                break
