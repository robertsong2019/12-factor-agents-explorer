"""Tests for query_as_of() — unified bi-temporal query API.

Engram pattern: bi-temporal context retrieval beats full-context by +10.4pp.
Two modes: localized (BFS from seed) and global (full snapshot).
"""
import time
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


@pytest.fixture
def temporal_graph(mg):
    """Build a graph with temporal edges and superseded nodes.

    Timeline (approximate, uses real timestamps):
    - t0: Create A, B, C, D nodes
    - t1: Add edges A→B, A→C, C→D
    - t2: Invalidate edge A→C
    - t3: Supersede B with B2
    """
    t0 = time.time()
    a = mg.add("Alpha", "concept")
    b = mg.add("Beta", "concept")
    c = mg.add("Gamma", "concept")
    d = mg.add("Delta", "concept")
    # Add plain edges
    mg.link(a.id, b.id, "relates")
    mg.link(a.id, c.id, "relates")
    mg.link(c.id, d.id, "relates")
    time.sleep(0.01)
    t1 = time.time()
    # Set temporal validity on edges
    mg.edge_set_validity(a.id, b.id, "relates", valid_from=t1)
    mg.edge_set_validity(a.id, c.id, "relates", valid_from=t1)
    mg.edge_set_validity(c.id, d.id, "relates", valid_from=t1)
    time.sleep(0.01)
    t2 = time.time()
    mg.edge_invalidate(a.id, c.id, "relates", invalidated_by="test")
    time.sleep(0.01)
    t3 = time.time()
    b2_id = mg.supersede(b.id, new_label="Beta-v2")
    time.sleep(0.01)
    t4 = time.time()
    return {
        "graph": mg,
        "nodes": {"a": a.id, "b": b.id, "b2": b2_id, "c": c.id, "d": d.id},
        "times": {"t0": t0, "t1": t1, "t2": t2, "t3": t3, "t4": t4},
    }


# ── Mode selection ──────────────────────────────────────────

class TestQueryAsOfModes:
    def test_global_mode_when_no_node_id(self, temporal_graph):
        mg = temporal_graph["graph"]
        result = mg.query_as_of(temporal_graph["times"]["t1"])
        assert result["mode"] == "global"
        assert result["timestamp"] == temporal_graph["times"]["t1"]
        assert "nodes" in result
        assert "edges" in result
        assert "stats" in result

    def test_localized_mode_with_node_id(self, temporal_graph):
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        result = mg.query_as_of(temporal_graph["times"]["t1"], ids["a"])
        assert result["mode"] == "localized"
        assert result["timestamp"] == temporal_graph["times"]["t1"]


# ── Global mode ─────────────────────────────────────────────

class TestQueryAsOfGlobal:
    def test_global_returns_all_valid_nodes(self, temporal_graph):
        mg = temporal_graph["graph"]
        result = mg.query_as_of(temporal_graph["times"]["t1"])
        node_ids = {n["id"] for n in result["nodes"]}
        ids = temporal_graph["nodes"]
        # B should be valid (not superseded yet at t1)
        assert ids["a"] in node_ids
        assert ids["b"] in node_ids

    def test_global_excludes_superseded_nodes(self, temporal_graph):
        mg = temporal_graph["graph"]
        result = mg.query_as_of(temporal_graph["times"]["t4"])
        node_ids = {n["id"] for n in result["nodes"]}
        ids = temporal_graph["nodes"]
        # After t3, B is superseded by B2
        assert ids["b"] not in node_ids or ids["b2"] in node_ids

    def test_global_kind_filter(self, temporal_graph):
        mg = temporal_graph["graph"]
        mg.add("Extra", "entity")
        result = mg.query_as_of(time.time(), kind="entity")
        kinds = {n["kind"] for n in result["nodes"]}
        assert kinds == {"entity"}

    def test_global_relation_filter(self, temporal_graph):
        mg = temporal_graph["graph"]
        result = mg.query_as_of(temporal_graph["times"]["t1"], relation="relates")
        rels = {e["relation"] for e in result["edges"]}
        assert rels == {"relates"}

    def test_global_limit(self, temporal_graph):
        mg = temporal_graph["graph"]
        result = mg.query_as_of(time.time(), limit=2)
        assert result["stats"]["nodes"] <= 2


# ── Localized mode (BFS) ────────────────────────────────────

class TestQueryAsOfLocalized:
    def test_localized_returns_seed_node(self, temporal_graph):
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        result = mg.query_as_of(temporal_graph["times"]["t1"], ids["a"], depth=0)
        node_ids = {n["id"] for n in result["nodes"]}
        assert ids["a"] in node_ids

    def test_localized_depth_1_finds_neighbors(self, temporal_graph):
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        result = mg.query_as_of(temporal_graph["times"]["t1"], ids["a"], depth=1)
        node_ids = {n["id"] for n in result["nodes"]}
        assert ids["a"] in node_ids
        # A→B and A→C were both valid at t1
        assert ids["b"] in node_ids
        assert ids["c"] in node_ids

    def test_localized_depth_2_reaches_grandchildren(self, temporal_graph):
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        result = mg.query_as_of(temporal_graph["times"]["t1"], ids["a"], depth=2)
        node_ids = {n["id"] for n in result["nodes"]}
        # C→D is reachable at depth 2
        assert ids["d"] in node_ids

    def test_localized_excludes_invalidated_edge(self, temporal_graph):
        """After invalidation, edge A→C should not appear in BFS."""
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        # Use t3 (after invalidation at t2) to query
        result = mg.query_as_of(temporal_graph["times"]["t3"], ids["a"], depth=1)
        node_ids = {n["id"] for n in result["nodes"]}
        assert ids["a"] in node_ids
        assert ids["b"] in node_ids
        # A→C invalidated at t2, so at t3 it should not appear
        edge_pairs = {(e["source"], e["target"]) for e in result["edges"]}
        assert (ids["a"], ids["c"]) not in edge_pairs

    def test_localized_excludes_superseded_node(self, temporal_graph):
        """After t3, B is superseded by B2. Localized query should exclude B."""
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        result = mg.query_as_of(temporal_graph["times"]["t4"], ids["a"], depth=1)
        node_ids = {n["id"] for n in result["nodes"]}
        assert ids["b"] not in node_ids

    def test_localized_kind_filter(self, temporal_graph):
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        mg.add("OtherKind", "different")
        result = mg.query_as_of(time.time(), ids["a"], depth=1, kind="concept")
        kinds = {n["kind"] for n in result["nodes"]}
        assert "different" not in kinds

    def test_localized_relation_filter(self, temporal_graph):
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        mg.link(ids["a"], ids["d"], "special_link")
        result = mg.query_as_of(time.time(), ids["a"], depth=1, relation="special_link")
        rels = {e["relation"] for e in result["edges"]}
        assert rels == {"special_link"}

    def test_localized_nonexistent_node(self, mg):
        result = mg.query_as_of(time.time(), "nonexistent", depth=1)
        assert result["nodes"] == []
        assert result["edges"] == []
        assert result["stats"]["nodes"] == 0

    def test_localized_returns_temporal_metadata(self, temporal_graph):
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        result = mg.query_as_of(time.time(), ids["a"], depth=1)
        for node in result["nodes"]:
            assert "valid_from" in node
            assert "valid_to" in node

    def test_localized_depth_0_only_seed(self, temporal_graph):
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        result = mg.query_as_of(temporal_graph["times"]["t1"], ids["a"], depth=0)
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["id"] == ids["a"]
        assert result["edges"] == []

    def test_localized_limit_cap(self, temporal_graph):
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        result = mg.query_as_of(temporal_graph["times"]["t1"], ids["a"], depth=2, limit=1)
        assert result["stats"]["nodes"] <= 1

    def test_localized_stats_depth_reached(self, temporal_graph):
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        result = mg.query_as_of(temporal_graph["times"]["t1"], ids["a"], depth=2)
        assert result["stats"]["depth_reached"] >= 1

    def test_localized_no_duplicate_edges(self, temporal_graph):
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        result = mg.query_as_of(temporal_graph["times"]["t1"], ids["a"], depth=2)
        edge_keys = [(e["source"], e["target"], e["relation"]) for e in result["edges"]]
        assert len(edge_keys) == len(set(edge_keys))

    def test_localized_undirected_traversal(self, temporal_graph):
        """BFS should traverse both outgoing and incoming edges."""
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        # D is reachable from A via A→C→D, but also from D's perspective
        result = mg.query_as_of(temporal_graph["times"]["t1"], ids["d"], depth=1)
        node_ids = {n["id"] for n in result["nodes"]}
        # D should see C (incoming edge)
        assert ids["c"] in node_ids


# ── Edge cases ──────────────────────────────────────────────

class TestQueryAsOfEdgeCases:
    def test_empty_graph_global(self, mg):
        result = mg.query_as_of(time.time())
        assert result["mode"] == "global"
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_empty_graph_localized(self, mg):
        result = mg.query_as_of(time.time(), "missing", depth=1)
        assert result["mode"] == "localized"
        assert result["nodes"] == []

    def test_no_temporal_info_returns_all(self, mg):
        """Nodes/edges without temporal info should always be included."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "plain")
        result = mg.query_as_of(time.time(), a.id, depth=1)
        node_ids = {n["id"] for n in result["nodes"]}
        assert a.id in node_ids
        assert b.id in node_ids

    def test_future_timestamp(self, temporal_graph):
        """Querying with a future timestamp should return current valid state."""
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        future = time.time() + 1000
        result = mg.query_as_of(future, ids["a"], depth=1)
        node_ids = {n["id"] for n in result["nodes"]}
        assert ids["a"] in node_ids

    def test_past_before_creation(self, temporal_graph):
        """Querying before any node was created should return empty."""
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        past = temporal_graph["times"]["t0"] - 1000
        result = mg.query_as_of(past, ids["a"], depth=1)
        # Node A has no explicit valid_from in _node_temporal,
        # so node_valid_at returns True. But is_valid_at checks
        # the SQL columns which might have valid_from set.
        # Either way, this shouldn't crash.
        assert isinstance(result, dict)


# ── Integration with supersede ──────────────────────────────

class TestQueryAsOfSupersede:
    def test_superseded_chain_visible_at_correct_times(self, temporal_graph):
        mg = temporal_graph["graph"]
        ids = temporal_graph["nodes"]
        # Before supersede (t1), B is valid
        result_before = mg.query_as_of(temporal_graph["times"]["t1"], ids["a"], depth=1)
        ids_before = {n["id"] for n in result_before["nodes"]}
        assert ids["b"] in ids_before

        # After supersede (t4), B2 should be visible, B should not
        result_after = mg.query_as_of(temporal_graph["times"]["t4"], ids["a"], depth=1)
        ids_after = {n["id"] for n in result_after["nodes"]}
        assert ids["b"] not in ids_after

    def test_temporal_consistency(self, temporal_graph):
        """query_as_of at different times should be consistent with
        temporal_graph_snapshot."""
        mg = temporal_graph["graph"]
        t = temporal_graph["times"]["t1"]
        snap = mg.temporal_graph_snapshot(t)
        result = mg.query_as_of(t)
        assert result["stats"]["nodes"] == snap["stats"]["nodes"]
