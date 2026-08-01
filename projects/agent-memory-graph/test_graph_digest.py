"""Tests for graph_digest() — content-addressed integrity hash."""
import hashlib
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


class TestGraphDigestBasic:
    def test_returns_sha256_hex_string(self, mg):
        mg.add("A")
        result = mg.graph_digest()
        assert isinstance(result, str)
        assert len(result) == 64
        int(result, 16)

    def test_empty_graph_has_digest(self, mg):
        result = mg.graph_digest()
        assert len(result) == 64

    def test_deterministic(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "edge")
        h1 = mg.graph_digest()
        h2 = mg.graph_digest()
        assert h1 == h2

    def test_adding_node_changes_hash(self, mg):
        mg.add("A")
        h1 = mg.graph_digest()
        mg.add("B")
        h2 = mg.graph_digest()
        assert h1 != h2

    def test_adding_edge_changes_hash(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        h1 = mg.graph_digest()
        mg.link(a.id, b.id, "edge")
        h2 = mg.graph_digest()
        assert h1 != h2

    def test_removing_node_changes_hash(self, mg):
        a = mg.add("A")
        mg.add("B")
        h1 = mg.graph_digest()
        mg.delete_node(a.id)
        h2 = mg.graph_digest()
        assert h1 != h2


class TestGraphDigestOptions:
    def test_include_content_changes_hash(self, mg):
        mg.add("A")
        h1 = mg.graph_digest(include_content=False)
        h2 = mg.graph_digest(include_content=True)
        assert h1 != h2

    def test_label_change_affects_content_hash(self, mg):
        n = mg.add("Original")
        h1 = mg.graph_digest(include_content=True)
        mg.rename_node(n.id, "Changed")
        h2 = mg.graph_digest(include_content=True)
        assert h1 != h2

    def test_label_change_no_effect_without_content(self, mg):
        n = mg.add("Original")
        h1 = mg.graph_digest(include_content=False)
        mg.rename_node(n.id, "Changed")
        h2 = mg.graph_digest(include_content=False)
        assert h1 == h2

    def test_include_weights(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "edge", weight=1.0)
        h1 = mg.graph_digest(include_weights=True)
        mg.unlink(a.id, b.id, "edge")
        mg.link(a.id, b.id, "edge", weight=5.0)
        h2 = mg.graph_digest(include_weights=True)
        assert h1 != h2

    def test_exclude_weights(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "edge", weight=1.0)
        h1 = mg.graph_digest(include_weights=False)
        mg.unlink(a.id, b.id, "edge")
        mg.link(a.id, b.id, "edge", weight=99.0)
        h2 = mg.graph_digest(include_weights=False)
        assert h1 == h2

    def test_include_temporal(self, mg):
        mg.add("A")
        mg.add("B")
        h1 = mg.graph_digest(include_temporal=False)
        h2 = mg.graph_digest(include_temporal=True)
        assert h1 != h2


class TestGraphDigestStructural:
    def test_same_graph_same_hash(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        c = mg.add("C")
        mg.link(a.id, b.id, "x")
        h1 = mg.graph_digest()
        h2 = mg.graph_digest()
        assert h1 == h2

    def test_different_relation_different_hash(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "friend")
        h1 = mg.graph_digest()
        mg.unlink(a.id, b.id, "friend")
        mg.link(a.id, b.id, "enemy")
        h2 = mg.graph_digest()
        assert h1 != h2

    def test_self_loop(self, mg):
        n = mg.add("A")
        h1 = mg.graph_digest()
        mg.link(n.id, n.id, "self")
        h2 = mg.graph_digest()
        assert h1 != h2

    def test_multiple_edges_same_pair(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        h1 = mg.graph_digest()
        mg.link(a.id, b.id, "r1")
        h2 = mg.graph_digest()
        mg.link(a.id, b.id, "r2")
        h3 = mg.graph_digest()
        assert h1 != h2
        assert h2 != h3


class TestGraphDigestEdgeCases:
    def test_large_graph(self, mg):
        for i in range(100):
            mg.add("N%d" % i)
        h = mg.graph_digest()
        assert len(h) == 64

    def test_isolated_nodes(self, mg):
        mg.add("A")
        mg.add("B")
        mg.add("C")
        h = mg.graph_digest()
        assert len(h) == 64

    def test_hash_is_valid_sha256(self, mg):
        mg.add("X")
        h = mg.graph_digest()
        node_rows = mg.conn.execute("SELECT id FROM nodes ORDER BY id").fetchall()
        canonical = "\n".join("N:%s" % r["id"] for r in node_rows)
        expected = hashlib.sha256(canonical.encode()).hexdigest()
        assert h == expected

    def test_only_structure_mode(self, mg):
        """Structure-only mode: same structure, different labels = same hash."""
        mg1 = MemoryGraph(":memory:")
        mg2 = MemoryGraph(":memory:")
        a = mg1.add("A")
        b = mg1.add("B")
        mg1.link(a.id, b.id, "r")
        c = mg2.add("C")
        d = mg2.add("D")
        mg2.link(c.id, d.id, "r")
        # Same number of nodes + edges, different labels
        h1 = mg1.graph_digest(include_content=False, include_weights=False)
        h2 = mg2.graph_digest(include_content=False, include_weights=False)
        # Both have 2 nodes and 1 edge with same relation
        assert len(h1) == 64
        assert len(h2) == 64
