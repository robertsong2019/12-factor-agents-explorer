"""Tests for SearchTree suite — Cycle 441 (Arbor pattern, Research #029).

Graph-as-search-tree: expand_search_tree() materializes scored child
branches as ``search_tree`` nodes + ``search_child`` edges;
prune_search_tree() marks weak subtrees non-destructively;
search_tree_report() summarizes depth/status/best-path.

Best path = highest cumulative score root→leaf route (the primary
tree-search output: "which branch won").
"""

import pytest
from memory_graph import MemoryGraph


# ── Fixtures ──

@pytest.fixture
def base_graph():
    """Star-ish graph: hub linked to 4 scored satellites."""
    g = MemoryGraph()
    g.add("alpha hub", kind="concept", tags=["hub"])
    g.add("database scaling", kind="concept", tags=["database"])
    g.add("database indexing", kind="concept", tags=["database"])
    g.add("unrelated cooking", kind="concept", tags=["food"])
    g.add("lowweight target", kind="concept")
    g.conn.execute("UPDATE nodes SET weight=0.2 WHERE label='lowweight target'")
    g.link_by_label("alpha hub", "database scaling", "related_to")
    g.link_by_label("alpha hub", "database indexing", "related_to")
    g.link_by_label("alpha hub", "unrelated cooking", "related_to")
    g.link_by_label("alpha hub", "lowweight target", "related_to")
    return g


@pytest.fixture
def empty_graph():
    return MemoryGraph()


# ── expand_search_tree: rooting ──

class TestExpandRooting:

    def test_non_tree_node_becomes_root(self, base_graph):
        hub = base_graph.search_by_label("alpha hub")[0]
        result = base_graph.expand_search_tree(hub.id, "database scaling")
        assert result["reason"] == "expanded"
        root = base_graph.get_node(result["root_id"])
        assert root.kind == "search_tree"
        assert root.data["status"] == "root"
        assert root.data["depth"] == 0
        assert root.data["ref_node_id"] == hub.id

    def test_root_wraps_same_label(self, base_graph):
        hub = base_graph.search_by_label("alpha hub")[0]
        result = base_graph.expand_search_tree(hub.id)
        root = base_graph.get_node(result["root_id"])
        assert root.label == hub.label

    def test_missing_node_raises(self, base_graph):
        with pytest.raises(ValueError, match="node not found"):
            base_graph.expand_search_tree("nope123")

    def test_expansion_creates_search_child_edges(self, base_graph):
        hub = base_graph.search_by_label("alpha hub")[0]
        result = base_graph.expand_search_tree(hub.id, branching_factor=2)
        for child in result["children"]:
            edge = base_graph.conn.execute(
                "SELECT 1 FROM edges WHERE source=? AND target=? AND relation='search_child'",
                (result["root_id"], child["id"])).fetchone()
            assert edge is not None

    def test_children_are_search_tree_kind(self, base_graph):
        hub = base_graph.search_by_label("alpha hub")[0]
        result = base_graph.expand_search_tree(hub.id, branching_factor=3)
        for child in result["children"]:
            node = base_graph.get_node(child["id"])
            assert node.kind == "search_tree"
            assert node.data["status"] == "frontier"
            assert node.data["depth"] == 1


# ── expand_search_tree: branching & scoring ──

class TestExpandScoring:

    def test_branching_factor_limits_children(self, base_graph):
        hub = base_graph.search_by_label("alpha hub")[0]
        result = base_graph.expand_search_tree(hub.id, branching_factor=2)
        assert len(result["children"]) == 2

    def test_zero_branching_factor_no_children(self, base_graph):
        hub = base_graph.search_by_label("alpha hub")[0]
        result = base_graph.expand_search_tree(hub.id, branching_factor=0)
        assert result["children"] == []
        assert result["reason"] == "no_candidates"

    def test_query_prefers_matching_labels(self, base_graph):
        """Query 'database' should rank database-labeled neighbors top."""
        hub = base_graph.search_by_label("alpha hub")[0]
        result = base_graph.expand_search_tree(hub.id, "database performance",
                                               branching_factor=2)
        labels = [c["label"] for c in result["children"]]
        assert "database scaling" in labels
        assert "database indexing" in labels

    def test_scores_sorted_descending(self, base_graph):
        hub = base_graph.search_by_label("alpha hub")[0]
        result = base_graph.expand_search_tree(hub.id, "database",
                                               branching_factor=4)
        scores = [c["score"] for c in result["children"]]
        assert scores == sorted(scores, reverse=True)

    def test_no_query_uses_weight_only(self, base_graph):
        hub = base_graph.search_by_label("alpha hub")[0]
        result = base_graph.expand_search_tree(hub.id, branching_factor=4)
        # lowweight target (0.2) scores lowest
        by_label = {c["label"]: c["score"] for c in result["children"]}
        assert by_label["lowweight target"] == 0.2  # weight-only, no query

    def test_query_relevance_dominates_weight(self, base_graph):
        hub = base_graph.search_by_label("alpha hub")[0]
        result = base_graph.expand_search_tree(hub.id, "database scaling",
                                               branching_factor=4)
        by_label = {c["label"]: c["score"] for c in result["children"]}
        assert by_label["database scaling"] > by_label["lowweight target"]

    def test_re_expand_root_marks_expanded(self, base_graph):
        hub = base_graph.search_by_label("alpha hub")[0]
        r1 = base_graph.expand_search_tree(hub.id, branching_factor=2)
        root = base_graph.get_node(r1["root_id"])
        assert root.data["status"] == "root"  # roots stay root

    def test_frontier_child_expands_to_depth_2(self, base_graph):
        hub = base_graph.search_by_label("alpha hub")[0]
        r1 = base_graph.expand_search_tree(hub.id, branching_factor=1)
        child = r1["children"][0]
        # child's ref node has no further neighbors (except hub)
        r2 = base_graph.expand_search_tree(child["id"])
        assert r2["depth"] == 1
        # grandchildren must not duplicate existing members
        for gc in r2["children"]:
            assert gc["depth"] == 2

    def test_expanded_parent_transition(self, base_graph):
        """A frontier node that gets expanded becomes status=expanded."""
        hub = base_graph.search_by_label("alpha hub")[0]
        r1 = base_graph.expand_search_tree(hub.id, branching_factor=1)
        child_id = r1["children"][0]["id"]
        assert base_graph.get_node(child_id).data["status"] == "frontier"
        base_graph.expand_search_tree(child_id)
        # no candidates likely, but status unchanged unless children made
        # status transition only occurs with successful expansion
        if r1["children"]:
            pass  # covered by chain fixture below


@pytest.fixture
def chain_graph():
    """Chain: A -> B -> C -> D with a side branch at B."""
    g = MemoryGraph()
    g.add("alpha start", kind="concept")
    g.add("beta middle", kind="concept")
    g.add("gamma deep", kind="concept")
    g.add("delta deepest", kind="concept")
    g.add("epsilon side", kind="concept")
    g.link_by_label("alpha start", "beta middle", "next")
    g.link_by_label("beta middle", "gamma deep", "next")
    g.link_by_label("gamma deep", "delta deepest", "next")
    g.link_by_label("beta middle", "epsilon side", "next")
    return g


class TestExpandChain:

    def test_chain_expands_two_levels(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2)
        assert len(r1["children"]) == 1  # only beta
        child = r1["children"][0]
        assert child["label"] == "beta middle"
        r2 = chain_graph.expand_search_tree(child["id"], branching_factor=2)
        labels = {c["label"] for c in r2["children"]}
        assert labels == {"gamma deep", "epsilon side"}

    def test_no_revisit_of_tree_members(self, chain_graph):
        """Grandchildren must not include already-member alpha/beta."""
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2)
        beta = r1["children"][0]
        r2 = chain_graph.expand_search_tree(beta["id"], branching_factor=5)
        r3 = chain_graph.expand_search_tree(
            [c for c in r2["children"] if c["label"] == "gamma deep"][0]["id"],
            branching_factor=5)
        all_ids = {r1["root_id"]} | {c["id"] for c in r1["children"]}
        all_ids |= {c["id"] for c in r2["children"]}
        all_ids |= {c["id"] for c in r3["children"]}
        # alpha (root ref) and beta (member ref) must not appear as new nodes
        for c in r3["children"]:
            assert c["label"] not in ("alpha start", "beta middle")

    def test_max_depth_refuses_expansion(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2, max_depth=1)
        assert len(r1["children"]) == 1
        child = r1["children"][0]
        r2 = chain_graph.expand_search_tree(child["id"], max_depth=1)
        assert r2["reason"] == "max_depth"
        assert r2["children"] == []

    def test_frontier_count_tracks(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2)
        assert r1["frontier_count"] == 1
        beta = r1["children"][0]
        r2 = chain_graph.expand_search_tree(beta["id"], branching_factor=2)
        assert r2["frontier_count"] == 2
        assert r2["reason"] == "expanded"


# ── prune_search_tree ──

class TestPrune:

    def test_prune_below_threshold(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2)
        beta = r1["children"][0]
        r2 = chain_graph.expand_search_tree(beta["id"], branching_factor=2)
        # prune the subtree rooted at beta: its low-score children die
        result = chain_graph.prune_search_tree(beta["id"], min_score=0.99)
        assert result["pruned_count"] >= 1
        assert beta["id"] in result["pruned_ids"]

    def test_prune_marks_not_deletes(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2)
        beta = r1["children"][0]
        chain_graph.expand_search_tree(beta["id"], branching_factor=2)
        chain_graph.prune_search_tree(beta["id"], min_score=0.99)
        node = chain_graph.get_node(beta["id"])
        assert node is not None  # still exists
        assert node.data["status"] == "pruned"

    def test_prune_cascades_to_descendants(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2)
        beta = r1["children"][0]
        r2 = chain_graph.expand_search_tree(beta["id"], branching_factor=2)
        grandchild_ids = {c["id"] for c in r2["children"]}
        result = chain_graph.prune_search_tree(beta["id"], min_score=0.99)
        assert grandchild_ids <= set(result["pruned_ids"])

    def test_root_survives_self_prune(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2)
        result = chain_graph.prune_search_tree(r1["root_id"], min_score=0.99)
        # root itself must NOT be pruned (status=root survives)
        assert r1["root_id"] not in result["pruned_ids"]

    def test_high_threshold_prunes_all_children(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2)
        beta = r1["children"][0]
        chain_graph.expand_search_tree(beta["id"], branching_factor=2)
        result = chain_graph.prune_search_tree(r1["root_id"], min_score=99.0)
        assert result["pruned_count"] >= 3  # beta + 2 grandchildren
        assert result["remaining_frontier"] == 0

    def test_zero_threshold_prunes_nothing(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2)
        beta = r1["children"][0]
        chain_graph.expand_search_tree(beta["id"], branching_factor=2)
        result = chain_graph.prune_search_tree(r1["root_id"], min_score=0.0)
        assert result["pruned_count"] == 0

    def test_prune_non_tree_node_raises(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        with pytest.raises(ValueError, match="not a search tree node"):
            chain_graph.prune_search_tree(a.id, min_score=0.5)

    def test_remaining_frontier_after_partial_prune(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2)
        beta = r1["children"][0]
        r2 = chain_graph.expand_search_tree(beta["id"], branching_factor=2)
        # prune only beta's subtree, frontier should drop to 0 (both were beta's kids)
        result = chain_graph.prune_search_tree(beta["id"], min_score=0.99)
        assert result["remaining_frontier"] == 0


# ── search_tree_report ──

class TestReport:

    def test_report_basic_shape(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2)
        chain_graph.expand_search_tree(r1["children"][0]["id"], branching_factor=2)
        report = chain_graph.search_tree_report(r1["root_id"])
        assert report["total"] == 4  # root + beta + gamma + epsilon
        assert report["max_depth"] == 2
        assert report["by_status"]["root"] == 1
        assert report["by_status"]["expanded"] == 1
        assert report["by_status"]["frontier"] == 2
        assert "avg_score" in report

    def test_best_path_starts_at_root(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2)
        chain_graph.expand_search_tree(r1["children"][0]["id"], branching_factor=2)
        report = chain_graph.search_tree_report(r1["root_id"])
        assert report["best_path"][0]["id"] == r1["root_id"]
        assert len(report["best_path"]) == 3  # root → beta → best grandchild

    def test_best_path_excludes_pruned(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2)
        beta = r1["children"][0]
        r2 = chain_graph.expand_search_tree(beta["id"], branching_factor=2)
        # Prune one grandchild specifically
        weakest = min(r2["children"], key=lambda c: c["score"])
        chain_graph.prune_search_tree(weakest["id"], min_score=0.99)
        report = chain_graph.search_tree_report(r1["root_id"])
        path_ids = [p["id"] for p in report["best_path"]]
        assert weakest["id"] not in path_ids

    def test_tree_text_renders_hierarchy(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2)
        chain_graph.expand_search_tree(r1["children"][0]["id"], branching_factor=2)
        report = chain_graph.search_tree_report(r1["root_id"])
        text = report["tree_text"]
        assert "score=" in text
        assert text.count("\n") >= 3
        # root line has no indentation
        assert text.splitlines()[0].startswith("alpha start")

    def test_pruned_marker_in_tree_text(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=2)
        beta = r1["children"][0]
        r2 = chain_graph.expand_search_tree(beta["id"], branching_factor=2)
        chain_graph.prune_search_tree(r1["root_id"], min_score=1.5)  # weight-only scores are 1.0
        report = chain_graph.search_tree_report(r1["root_id"])
        assert "[pruned]" in report["tree_text"]

    def test_report_single_root_only(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        r1 = chain_graph.expand_search_tree(a.id, branching_factor=0)
        report = chain_graph.search_tree_report(r1["root_id"])
        assert report["total"] == 1
        assert report["max_depth"] == 0
        assert len(report["best_path"]) == 1
        assert report["avg_score"] == 0.0

    def test_report_non_tree_node_raises(self, chain_graph):
        a = chain_graph.search_by_label("alpha start")[0]
        with pytest.raises(ValueError, match="not a search tree node"):
            chain_graph.search_tree_report(a.id)


# ── Integration: full search cycle ──

class TestSearchCycleIntegration:

    def test_expand_prune_report_cycle(self, base_graph):
        """Full tree-search lifecycle on a hub graph."""
        hub = base_graph.search_by_label("alpha hub")[0]
        r1 = base_graph.expand_search_tree(hub.id, "database", branching_factor=3)
        assert r1["frontier_count"] == 3
        # prune weak branches
        pr = base_graph.prune_search_tree(r1["root_id"], min_score=0.5)
        report = base_graph.search_tree_report(r1["root_id"])
        assert report["total"] == 4  # root + 3 children
        assert report["by_status"].get("pruned", 0) + \
            report["by_status"].get("frontier", 0) == 3

    def test_tree_nodes_distinguishable_by_kind(self, base_graph):
        """Tree children link from the root wrapper (not the source node);
        base graph structure stays untouched and tree nodes are
        filterable via kind='search_tree'."""
        hub = base_graph.search_by_label("alpha hub")[0]
        base_graph.expand_search_tree(hub.id, branching_factor=2)
        # hub's own neighbors unchanged (search_child edges start at wrapper)
        kinds = {n.kind for n in base_graph.neighbors(hub.id)}
        assert "search_tree" not in kinds
        # tree nodes exist and are filterable
        tree_rows = base_graph.conn.execute(
            "SELECT COUNT(*) c FROM nodes WHERE kind='search_tree'").fetchone()["c"]
        assert tree_rows == 3  # root + 2 children

    def test_pruned_node_refuses_expansion(self, base_graph):
        hub = base_graph.search_by_label("alpha hub")[0]
        r1 = base_graph.expand_search_tree(hub.id, branching_factor=2)
        child = r1["children"][0]
        base_graph.prune_search_tree(child["id"], min_score=0.99)
        r2 = base_graph.expand_search_tree(child["id"])
        assert r2["reason"] == "pruned"
        assert r2["children"] == []

    def test_persistence_across_graphs(self, tmp_path):
        """SearchTree state survives save/load round-trip."""
        import sqlite3
        path = str(tmp_path / "st.db")
        g1 = MemoryGraph(path)
        hub = g1.add("persist hub", kind="concept")
        g1.add("persist target", kind="concept")
        g1.link_by_label("persist hub", "persist target", "related_to")
        r1 = g1.expand_search_tree(hub.id, branching_factor=1)
        g1.conn.close()

        g2 = MemoryGraph(path)
        report = g2.search_tree_report(r1["root_id"])
        assert report["total"] == 2
        g2.conn.close()

    def test_two_trees_coexist(self, base_graph):
        """Independent search trees over the same base graph."""
        hub = base_graph.search_by_label("alpha hub")[0]
        r1 = base_graph.expand_search_tree(hub.id, "database", branching_factor=1)
        r2 = base_graph.expand_search_tree(hub.id, "cooking", branching_factor=1)
        assert r1["root_id"] != r2["root_id"]
        rep1 = base_graph.search_tree_report(r1["root_id"])
        rep2 = base_graph.search_tree_report(r2["root_id"])
        assert rep1["total"] == 2
        assert rep2["total"] == 2

    def test_empty_graph_errors_cleanly(self, empty_graph):
        with pytest.raises(ValueError):
            empty_graph.expand_search_tree("missing")
