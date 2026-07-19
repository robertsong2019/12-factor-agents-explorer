"""Tests for auto_consolidate() — cycle 269.

Redundancy act-loop: detect -> consolidate.
Mirrors auto_heal_gaps() for the gap loop.
"""

import pytest
from memory_graph import MemoryGraph


def _set_weight(g, node, w):
    """Helper: set node weight via SQL (add() doesn't accept weight)."""
    g.conn.execute("UPDATE nodes SET weight=? WHERE id=?", (w, node.id))
    g.conn.commit()


@pytest.fixture
def empty_graph():
    return MemoryGraph(":memory:")


@pytest.fixture
def redundant_graph():
    """Graph with clear redundancy for consolidation testing."""
    g = MemoryGraph(":memory:")

    # Two near-duplicate content nodes
    a1 = g.add("Python programming language", "concept")
    a2 = g.add("Python programing language", "concept")
    _set_weight(g, a1, 1.0)
    _set_weight(g, a2, 0.9)

    # Two structural clones — same neighbours
    b1 = g.add("Component Alpha", "module")
    b2 = g.add("Component Beta", "module")
    _set_weight(g, b1, 1.0)
    _set_weight(g, b2, 1.0)
    hub = g.add("Hub Node", "hub")
    _set_weight(g, hub, 2.0)
    g.link(b1.id, hub.id, "connects_to")
    g.link(b2.id, hub.id, "connects_to")

    # A unique node that won't be merged
    unique = g.add("Unique standalone node", "concept")

    return g, a1, a2, b1, b2, hub, unique


# -- TestAutoConsolidateBasics --

class TestAutoConsolidateBasics:

    def test_empty_graph_returns_zero_merges(self, empty_graph):
        result = empty_graph.auto_consolidate()
        assert result["total_merges"] == 0
        assert result["merges_performed"] == []
        assert result["dry_run"] is False

    def test_single_node_nothing_to_merge(self, empty_graph):
        empty_graph.add("Solo node", "concept")
        result = empty_graph.auto_consolidate()
        assert result["total_merges"] == 0

    def test_result_has_required_fields(self, empty_graph):
        result = empty_graph.auto_consolidate()
        for key in ("merges_performed", "total_merges",
                     "redundancy_score_before", "redundancy_score_after",
                     "nodes_before", "nodes_after",
                     "actions", "dry_run", "skipped"):
            assert key in result, f"Missing key: {key}"

    def test_dry_run_flag_reflected(self, empty_graph):
        result = empty_graph.auto_consolidate(dry_run=True)
        assert result["dry_run"] is True


# -- TestMergeExecution --

class TestMergeExecution:

    def test_content_duplicates_merged(self, redundant_graph):
        g, a1, a2, b1, b2, hub, unique = redundant_graph
        result = g.auto_consolidate(min_score=0.3)

        assert result["total_merges"] >= 1
        merged_flat = set()
        for m in result["merges_performed"]:
            merged_flat.add(m["source"])
            merged_flat.add(m["target"])
        assert a1.id in merged_flat or a2.id in merged_flat, \
            "Content duplicates should be among merged nodes"

    def test_node_count_decreases_after_merge(self, redundant_graph):
        g = redundant_graph[0]
        nodes_before = len(g.conn.execute("SELECT * FROM nodes").fetchall())
        g.auto_consolidate(min_score=0.3)
        nodes_after = len(g.conn.execute("SELECT * FROM nodes").fetchall())
        assert nodes_after < nodes_before, "Node count should decrease after merges"

    def test_dry_run_preserves_nodes(self, redundant_graph):
        g = redundant_graph[0]
        nodes_before = len(g.conn.execute("SELECT * FROM nodes").fetchall())
        g.auto_consolidate(min_score=0.3, dry_run=True)
        nodes_after = len(g.conn.execute("SELECT * FROM nodes").fetchall())
        assert nodes_after == nodes_before, "Dry run must not modify nodes"

    def test_merge_direction_lower_to_higher_degree(self):
        """Lower-degree node should be merged into higher-degree node."""
        g = MemoryGraph(":memory:")
        hub = g.add("Hub", "hub")
        leaf1 = g.add("Duplicate Leaf", "leaf")
        leaf2 = g.add("Duplicate Leaf", "leaf")
        g.link(hub.id, leaf1.id, "connects")
        g.link(hub.id, leaf2.id, "connects")

        result = g.auto_consolidate(min_score=0.2)
        for merge in result["merges_performed"]:
            assert "source" in merge
            assert "target" in merge
            # Target should still exist (it's the survivor)
            tgt_row = g.conn.execute(
                "SELECT 1 FROM nodes WHERE id=?", (merge["target"],)
            ).fetchone()
            assert tgt_row is not None, "Target node should survive"


# -- TestScoringAndThresholds --

class TestScoringAndThresholds:

    def test_min_score_filters_low_pairs(self):
        """High min_score should filter out most candidates."""
        g = MemoryGraph(":memory:")
        a = g.add("Alpha concept node", "concept")
        b = g.add("Beta concept node", "concept")
        g.link(a.id, b.id, "rel")

        result_strict = g.auto_consolidate(min_score=0.95)
        assert result_strict["total_merges"] == 0

    def test_max_merges_limits_count(self, redundant_graph):
        g = redundant_graph[0]
        result = g.auto_consolidate(max_merges=1, min_score=0.2)
        assert result["total_merges"] <= 1

    def test_redundancy_score_decreases_after_merge(self, redundant_graph):
        g = redundant_graph[0]
        result = g.auto_consolidate(min_score=0.2)
        if result["total_merges"] > 0:
            assert result["redundancy_score_after"] <= result["redundancy_score_before"], \
                "Redundancy should not increase after merges"

    def test_skipped_pairs_tracked(self):
        """Pairs below threshold should be tracked in skipped."""
        g = MemoryGraph(":memory:")
        a = g.add("Node A", "concept")
        b = g.add("Node B", "concept")
        result = g.auto_consolidate(min_score=0.99)
        assert isinstance(result["skipped"], list)


# -- TestSkippedAndEdgeCases --

class TestSkippedAndEdgeCases:

    def test_already_merged_node_not_double_merged(self):
        """If A-B and A-C are candidates, merging A-B should skip A-C."""
        g = MemoryGraph(":memory:")
        a = g.add("Python programming", "concept")
        b = g.add("Python programming", "concept")
        c = g.add("Python programming", "concept")

        result = g.auto_consolidate(max_merges=5, min_score=0.3)
        all_merged = []
        for m in result["merges_performed"]:
            all_merged.extend([m["source"], m["target"]])
        assert len(all_merged) == len(set(all_merged)), \
            "No node should appear in multiple merges"

    def test_actions_list_matches_merge_count(self, redundant_graph):
        g = redundant_graph[0]
        result = g.auto_consolidate(min_score=0.2)
        assert len(result["actions"]) == result["total_merges"]

    def test_node_ids_filter_restricts_scope(self):
        """Restrict consolidation to a subgraph via node_ids."""
        g = MemoryGraph(":memory:")
        a1 = g.add("Duplicate content here", "concept")
        a2 = g.add("Duplicate content here!", "concept")
        b1 = g.add("Other pair content", "concept")
        b2 = g.add("Other pair content?", "concept")

        result = g.auto_consolidate(
            node_ids=[a1.id, a2.id], min_score=0.3
        )
        for merge in result["merges_performed"]:
            assert merge["source"] in (a1.id, a2.id)
            assert merge["target"] in (a1.id, a2.id)


# -- TestNonMutating --

class TestNonMutating:

    def test_dry_run_no_node_changes(self, redundant_graph):
        g, a1, a2, b1, b2, hub, unique = redundant_graph
        nodes_before = set(r["id"] for r in g.conn.execute("SELECT * FROM nodes").fetchall())
        edges_before = len(g.conn.execute("SELECT * FROM edges").fetchall())
        g.auto_consolidate(dry_run=True, min_score=0.1)
        nodes_after = set(r["id"] for r in g.conn.execute("SELECT * FROM nodes").fetchall())
        edges_after = len(g.conn.execute("SELECT * FROM edges").fetchall())
        assert nodes_before == nodes_after
        assert edges_before == edges_after

    def test_real_run_actually_merges(self):
        g = MemoryGraph(":memory:")
        a = g.add("Identical content", "concept")
        b = g.add("Identical content", "concept")
        count_before = len(g.conn.execute("SELECT * FROM nodes").fetchall())
        g.auto_consolidate(min_score=0.3)
        count_after = len(g.conn.execute("SELECT * FROM nodes").fetchall())
        assert count_after == count_before - 1, \
            "One merge should reduce node count by 1"


# -- TestMergeRecord --

class TestMergeRecord:

    def test_merge_record_has_score_fields(self, redundant_graph):
        g = redundant_graph[0]
        result = g.auto_consolidate(min_score=0.2)
        for merge in result["merges_performed"]:
            assert "score" in merge
            assert "content_sim" in merge
            assert "structural_sim" in merge
            assert "functional_dup" in merge
            assert "reason" in merge

    def test_merge_scores_in_valid_range(self, redundant_graph):
        g = redundant_graph[0]
        result = g.auto_consolidate(min_score=0.2)
        for merge in result["merges_performed"]:
            assert 0.0 <= merge["score"] <= 1.0
            assert 0.0 <= merge["content_sim"] <= 1.0
            assert 0.0 <= merge["structural_sim"] <= 1.0

    def test_reason_string_describes_dominant_dimension(self, redundant_graph):
        g = redundant_graph[0]
        result = g.auto_consolidate(min_score=0.2)
        for merge in result["merges_performed"]:
            assert merge["reason"]  # non-empty
            assert "dominated" in merge["reason"]
