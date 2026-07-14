"""Tests for serialize() token-budget-aware serialization — Cycle 241.

Searchat-inspired: pointer-based representation maximizing information density.
"""
import json
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph()


@pytest.fixture
def populated(mg):
    """Graph with nodes and edges."""
    a = mg.add("Alice", "person", {"role": "engineer"}, tags=["team"])
    b = mg.add("Bob", "person", {"role": "designer"})
    c = mg.add("Python", "skill", {"level": "expert"})
    mg.link(a.id, b.id, "works_with")
    mg.link(a.id, c.id, "skilled_in")
    return mg, a, b, c


# ── Basic serialization ──────────────────────────────────────

class TestBasicSerialize:
    def test_returns_dict(self, mg):
        mg.add("test", "fact")
        result = mg.serialize()
        assert isinstance(result, dict)

    def test_empty_graph(self, mg):
        result = mg.serialize()
        assert result["context"] == ""
        assert result["nodes_included"] == 0
        assert result["tokens_used"] >= 1  # max(1, ...)

    def test_single_node(self, mg):
        n = mg.add("hello", "fact")
        result = mg.serialize()
        assert result["nodes_included"] == 1
        assert "hello" in result["context"]
        assert n.id in result["node_pointers"]

    def test_multiple_nodes(self, populated):
        mg, a, b, c = populated
        result = mg.serialize()
        assert result["nodes_included"] == 3
        assert a.id in result["node_pointers"]
        assert b.id in result["node_pointers"]
        assert c.id in result["node_pointers"]

    def test_context_contains_node_ids(self, populated):
        mg, a, b, c = populated
        result = mg.serialize()
        for nid in [a.id, b.id, c.id]:
            assert nid in result["context"]

    def test_context_contains_labels(self, populated):
        mg, a, b, c = populated
        result = mg.serialize()
        assert "Alice" in result["context"]
        assert "Bob" in result["context"]

    def test_context_contains_kinds(self, populated):
        mg, a, b, c = populated
        result = mg.serialize()
        assert "person" in result["context"]
        assert "skill" in result["context"]


# ── Token budget enforcement ─────────────────────────────────

class TestTokenBudget:
    def test_budget_limits_nodes(self, mg):
        """With very small budget, only some nodes fit."""
        for i in range(20):
            mg.add(f"item number {i} with some description", "fact")
        result = mg.serialize(token_budget=50)  # ~200 chars
        assert result["nodes_included"] < 20
        assert result["nodes_truncated"] > 0

    def test_large_budget_includes_all(self, populated):
        mg, a, b, c = populated
        result = mg.serialize(token_budget=10000)
        assert result["nodes_included"] == 3
        assert result["nodes_truncated"] == 0

    def test_tokens_used_within_budget(self, mg):
        for i in range(10):
            mg.add(f"node {i}", "fact", {"data": "x" * 50})
        result = mg.serialize(token_budget=200)
        assert result["tokens_used"] <= 200 + 10  # small slack

    def test_zero_budget(self, mg):
        mg.add("test", "fact")
        result = mg.serialize(token_budget=0)
        # Zero budget → at most 0 chars, but max(1,...) on tokens_used
        assert result["nodes_included"] == 0


# ── Node ordering by weight ──────────────────────────────────

class TestWeightOrdering:
    def test_high_weight_first(self, mg):
        low = mg.add("low priority", "fact")
        high = mg.add("high priority", "fact")
        # Boost high weight
        mg.conn.execute("UPDATE nodes SET weight=0.9 WHERE id=?", (high.id,))
        mg.conn.execute("UPDATE nodes SET weight=0.1 WHERE id=?", (low.id,))
        mg.conn.commit()
        result = mg.serialize()
        # High weight should appear first in context
        assert result["context"].index("high priority") < result["context"].index("low priority")

    def test_specific_node_ids_override_ordering(self, populated):
        mg, a, b, c = populated
        result = mg.serialize(node_ids=[c.id, a.id])
        lines = result["context"].split("\n")
        assert c.id in lines[0]
        assert a.id in lines[1]


# ── Data field handling ──────────────────────────────────────

class TestDataHandling:
    def test_include_data_default(self, mg):
        n = mg.add("test", "fact", {"key": "value"})
        result = mg.serialize()
        assert "key" in result["context"]

    def test_exclude_data(self, mg):
        n = mg.add("test", "fact", {"key": "value"})
        result = mg.serialize(include_data=False)
        assert "key" not in result["context"]

    def test_empty_data_not_shown(self, mg):
        mg.add("test", "fact")
        result = mg.serialize()
        # No {} in context for nodes with empty data
        assert "{}" not in result["context"]

    def test_data_truncated_to_80_chars(self, mg):
        long_data = {"big": "X" * 200}
        mg.add("test", "fact", long_data)
        result = mg.serialize()
        # Data preview is capped at 80 chars
        assert "X" * 100 not in result["context"]


# ── Edge summary ─────────────────────────────────────────────

class TestEdgeSummary:
    def test_edges_included_by_default(self, populated):
        mg, a, b, c = populated
        result = mg.serialize()
        assert len(result["edge_summary"]) == 2

    def test_edges_excluded(self, populated):
        mg, a, b, c = populated
        result = mg.serialize(include_edges=False)
        assert result["edge_summary"] == []

    def test_edge_has_relation(self, populated):
        mg, a, b, c = populated
        result = mg.serialize()
        relations = [e["relation"] for e in result["edge_summary"]]
        assert "works_with" in relations

    def test_edge_has_source_target(self, populated):
        mg, a, b, c = populated
        result = mg.serialize()
        edge = result["edge_summary"][0]
        assert "source" in edge
        assert "target" in edge

    def test_edges_within_budget(self, mg):
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        mg.link(a.id, b.id, "rel")
        result = mg.serialize(token_budget=50)
        # Edge may or may not fit depending on budget
        assert isinstance(result["edge_summary"], list)


# ── Node pointers ────────────────────────────────────────────

class TestNodePointers:
    def test_pointers_have_label_and_kind(self, populated):
        mg, a, b, c = populated
        result = mg.serialize()
        ptr = result["node_pointers"][a.id]
        assert ptr["label"] == "Alice"
        assert ptr["kind"] == "person"

    def test_pointers_count_matches_included(self, populated):
        mg, a, b, c = populated
        result = mg.serialize()
        assert len(result["node_pointers"]) == result["nodes_included"]


# ── Compacted node detection ─────────────────────────────────

class TestCompactedDetection:
    def test_compacted_nodes_flagged(self, mg):
        n = mg.add("test content here", "fact", {"body": "x" * 100})
        # Compact with level 1 (sets _compacted flag)
        def s(l, d): return "summary"
        mg.compact_node(n.id, level=1, summarizer=s)
        result = mg.serialize()
        assert n.id in result["compacted_nodes"]

    def test_uncompacted_nodes_not_flagged(self, mg):
        n = mg.add("test", "fact")
        result = mg.serialize()
        assert n.id not in result["compacted_nodes"]


# ── serialize_compact convenience ────────────────────────────

class TestSerializeCompact:
    def test_auto_compact_low_weight(self, mg):
        # Create nodes with varying weights
        nodes = []
        for i in range(6):
            n = mg.add(f"node {i} with content", "fact", {"v": i})
            nodes.append(n)
        # Set varying weights
        for i, n in enumerate(nodes):
            mg.conn.execute("UPDATE nodes SET weight=? WHERE id=?",
                            (0.1 * (i + 1), n.id))
        mg.conn.commit()
        result = mg.serialize_compact(token_budget=4096)
        assert isinstance(result, dict)
        assert result["nodes_included"] > 0

    def test_empty_graph_serialize_compact(self, mg):
        result = mg.serialize_compact()
        assert result["nodes_included"] == 0

    def test_returns_valid_format(self, mg):
        mg.add("test", "fact")
        result = mg.serialize_compact()
        assert "context" in result
        assert "node_pointers" in result
        assert "tokens_used" in result


# ── Integration with immutable store ─────────────────────────

class TestImmutableIntegration:
    def test_serialize_after_compaction(self, mg):
        n = mg.add("Long content " * 20, "fact", {"big": "X" * 200})
        mg.compact_node(n.id, level=2)
        result = mg.serialize()
        # Serialization should use compacted live data
        assert result["nodes_included"] == 1
        # But immutable store has original
        recs = mg.immutable_retrieve(n.id)
        assert len(recs) == 1

    def test_serialize_then_expand(self, mg):
        n = mg.add("original content", "fact", {"key": "val"})
        result = mg.serialize()
        # Serialize gives compact view
        assert n.id in result["node_pointers"]
        # Expand gives full data
        full = mg.expand(n.id)
        assert full is not None
        assert full["label"] == "original content"


# ── Nonexistent node IDs ─────────────────────────────────────

class TestEdgeCases:
    def test_nonexistent_node_ids(self, mg):
        result = mg.serialize(node_ids=["fake-id-1", "fake-id-2"])
        assert result["nodes_included"] == 0

    def test_mixed_valid_invalid(self, populated):
        mg, a, b, c = populated
        result = mg.serialize(node_ids=[a.id, "fake-id"])
        assert result["nodes_included"] == 1
        assert a.id in result["node_pointers"]

    def test_single_large_budget(self, mg):
        n = mg.add("test", "fact")
        result = mg.serialize(token_budget=100000)
        assert result["tokens_used"] < 100000
