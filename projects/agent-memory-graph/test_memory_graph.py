"""Tests for Agent Memory Graph."""
import math
import time
import pytest
from memory_graph import MemoryGraph, Node, Edge


@pytest.fixture
def mg():
    return MemoryGraph()


@pytest.fixture
def populated(mg):
    a = mg.add("Alice", "person", {"role": "engineer"})
    b = mg.add("Bob", "person", {"role": "designer"})
    c = mg.add("Python", "skill")
    mg.link(a.id, b.id, "works_with")
    mg.link(a.id, c.id, "skilled_in")
    mg.link(b.id, c.id, "learning")
    return mg, a, b, c


class TestNodeCreation:
    def test_add_basic(self, mg):
        n = mg.add("test fact", "fact")
        assert n.label == "test fact"
        assert n.kind == "fact"
        assert n.weight == 1.0
        assert n.id  # has an id

    def test_add_with_data(self, mg):
        n = mg.add("event", "event", {"duration": 2})
        assert n.data == {"duration": 2}

    def test_add_multiple_kinds(self, mg):
        for kind in ("fact", "event", "person", "concept", "skill"):
            n = mg.add(f"test {kind}", kind)
            assert n.kind == kind


class TestLink:
    def test_link_two_nodes(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "connects")
        neighbors = mg.neighbors(a.id)
        assert len(neighbors) == 1
        assert neighbors[0].id == b.id

    def test_link_with_weight(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "strong", weight=0.9)
        # verify edge exists via neighbors
        assert len(mg.neighbors(a.id)) == 1

    def test_unlink(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "temp")
        assert len(mg.neighbors(a.id)) == 1
        mg.unlink(a.id, b.id, "temp")
        assert len(mg.neighbors(a.id)) == 0

    def test_unlink_nonexistent_safe(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.unlink(a.id, b.id, "none")  # should not raise


class TestRecall:
    def test_recall_by_keyword(self, populated):
        mg, a, b, c = populated
        results = mg.recall("Alice")
        assert len(results) == 1
        assert results[0].id == a.id

    def test_recall_partial_match(self, populated):
        mg, a, b, c = populated
        results = mg.recall("Pyt")
        assert len(results) == 1
        assert results[0].label == "Python"

    def test_recall_no_match(self, mg):
        mg.add("something")
        assert mg.recall("nothing") == []

    def test_recall_boosts_weight(self, populated):
        mg, a, b, c = populated
        # simulate aging
        mg.conn.execute("UPDATE nodes SET accessed = accessed - 86400")
        mg.conn.commit()
        mg.conn.execute("UPDATE nodes SET weight = 0.5 WHERE id = ?", (a.id,))
        mg.conn.commit()
        results = mg.recall("Alice")
        assert results[0].weight > 0.5  # boosted


class TestNeighbors:
    def test_depth_1(self, populated):
        mg, a, b, c = populated
        neighbors = mg.neighbors(a.id, depth=1)
        ids = {n.id for n in neighbors}
        assert b.id in ids
        assert c.id in ids

    def test_depth_2(self, populated):
        mg, a, b, c = populated
        neighbors = mg.neighbors(a.id, depth=2)
        ids = {n.id for n in neighbors}
        assert b.id in ids
        assert c.id in ids

    def test_empty_neighbors(self, mg):
        n = mg.add("lonely")
        assert mg.neighbors(n.id) == []


class TestDecay:
    def test_decay_reduces_weight(self, mg):
        n = mg.add("old memory")
        # simulate 1 day old (small enough to survive MIN_WEIGHT)
        mg.conn.execute("UPDATE nodes SET accessed = ? WHERE id = ?",
                        (time.time() - 86400, n.id))
        mg.conn.commit()
        mg.decay_all()
        row = mg.conn.execute("SELECT weight FROM nodes WHERE id=?", (n.id,)).fetchone()
        assert row is not None
        assert row["weight"] < 1.0

    def test_decay_removes_forgotten(self, mg):
        n = mg.add("forgotten")
        mg.conn.execute("UPDATE nodes SET weight = 0.01, accessed = ? WHERE id = ?",
                        (time.time() - 8640000, n.id))
        mg.conn.commit()
        mg.decay_all()
        row = mg.conn.execute("SELECT * FROM nodes WHERE id=?", (n.id,)).fetchone()
        assert row is None


class TestStats:
    def test_empty_stats(self, mg):
        s = mg.stats()
        assert s["nodes"] == 0
        assert s["edges"] == 0

    def test_populated_stats(self, populated):
        mg, a, b, c = populated
        s = mg.stats()
        assert s["nodes"] == 3
        assert s["edges"] == 3
        assert "person" in s["by_kind"]
        assert "skill" in s["by_kind"]


class TestMergeNodes:
    def test_merge_combines_data(self, mg):
        a = mg.add("A", "person", {"x": 1})
        b = mg.add("B", "person", {"y": 2})
        result = mg.merge_nodes(a.id, b.id)
        assert result.data == {"x": 1, "y": 2}
        assert mg.stats()["nodes"] == 1

    def test_merge_rewires_edges(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        c = mg.add("C")
        mg.link(a.id, c.id, "connects")
        mg.merge_nodes(a.id, b.id)
        # a's edge to c should now be b's
        neighbors = mg.neighbors(b.id)
        assert any(n.id == c.id for n in neighbors)

    def test_merge_nonexistent_returns_none(self, mg):
        result = mg.merge_nodes("nope", "nope2")
        assert result is None

    def test_merge_removes_self_loops(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "rel")
        mg.link(b.id, a.id, "rel")
        mg.merge_nodes(a.id, b.id)
        # no self-loop
        neighbors = mg.neighbors(b.id)
        assert len(neighbors) == 0


class TestShortestPath:
    def test_direct_connection(self, populated):
        mg, a, b, c = populated
        path = mg.shortest_path(a.id, b.id)
        assert path == [a.id, b.id]

    def test_two_hop(self, populated):
        mg, a, b, c = populated
        # a -> b -> c exists (b learning c)
        path = mg.shortest_path(a.id, c.id)
        assert path is not None
        assert path[0] == a.id
        assert path[-1] == c.id

    def test_no_path(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        assert mg.shortest_path(a.id, b.id) is None

    def test_same_node(self, mg):
        a = mg.add("A")
        assert mg.shortest_path(a.id, a.id) == [a.id]


class TestTags:
    def test_add_with_tags(self, mg):
        n = mg.add("tagged", tags=["important", "work"])
        found = mg.search_by_tag("important")
        assert len(found) == 1
        assert found[0].id == n.id

    def test_tag_nodes_after_creation(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.tag_nodes("shared", [a.id, b.id])
        found = mg.search_by_tag("shared")
        assert len(found) == 2

    def test_tag_no_duplicate(self, mg):
        n = mg.add("X")
        mg.tag_nodes("t", [n.id])
        mg.tag_nodes("t", [n.id])
        assert len(mg.search_by_tag("t")) == 1

class TestCRUD:
    def test_get_node(self, populated):
        mg, a, b, c = populated
        node = mg.get_node(a.id)
        assert node is not None
        assert node.label == "Alice"
        assert node.kind == "person"
        assert node.data == {"role": "engineer"}

    def test_get_node_not_found(self, mg):
        assert mg.get_node("nonexistent") is None

    def test_delete_node(self, populated):
        mg, a, b, c = populated
        assert mg.delete_node(b.id) is True
        assert mg.get_node(b.id) is None
        # edges to/from b should be gone
        assert mg.stats()["edges"] == 1  # only a->c remains
        assert mg.stats()["nodes"] == 2

    def test_delete_node_not_found(self, mg):
        assert mg.delete_node("nope") is False

    def test_delete_node_cleans_edges(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        c = mg.add("C")
        mg.link(a.id, b.id, "rel")
        mg.link(c.id, b.id, "rel")
        mg.delete_node(b.id)
        assert len(mg.neighbors(a.id)) == 0
        assert len(mg.neighbors(c.id)) == 0

    def test_update_node_label(self, populated):
        mg, a, b, c = populated
        updated = mg.update_node(a.id, label="Alice Smith")
        assert updated.label == "Alice Smith"
        assert updated.kind == "person"  # unchanged

    def test_update_node_data(self, populated):
        mg, a, b, c = populated
        updated = mg.update_node(a.id, data={"role": "manager", "level": 5})
        assert updated.data == {"role": "manager", "level": 5}

    def test_update_node_weight(self, populated):
        mg, a, b, c = populated
        updated = mg.update_node(a.id, weight=0.3)
        assert abs(updated.weight - 0.3) < 0.01

    def test_update_node_not_found(self, mg):
        assert mg.update_node("nope", label="X") is None

    def test_update_node_partial(self, populated):
        mg, a, b, c = populated
        updated = mg.update_node(a.id, kind="entity")
        assert updated.kind == "entity"
        assert updated.label == "Alice"  # unchanged
        assert updated.data == {"role": "engineer"}  # unchanged

class TestBatchOperations:
    def test_add_many_basic(self, mg):
        nodes = mg.add_many([
            {"label": "A", "kind": "person"},
            {"label": "B", "kind": "skill", "data": {"level": 3}},
            {"label": "C"},
        ])
        assert len(nodes) == 3
        assert nodes[0].label == "A"
        assert nodes[1].kind == "skill"
        assert nodes[1].data == {"level": 3}
        assert nodes[2].kind == "fact"  # default
        assert mg.stats()["nodes"] == 3

    def test_add_many_empty_list(self, mg):
        assert mg.add_many([]) == []

    def test_add_many_with_tags(self, mg):
        nodes = mg.add_many([
            {"label": "X", "tags": ["important"]},
            {"label": "Y", "tags": ["important"]},
        ])
        found = mg.search_by_tag("important")
        assert len(found) == 2

    def test_link_many(self, mg):
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        count = mg.link_many([
            {"source": a.id, "target": b.id, "relation": "knows"},
            {"source": b.id, "target": c.id, "relation": "mentor", "weight": 0.8},
        ])
        assert count == 2
        assert len(mg.neighbors(a.id)) == 1
        assert len(mg.neighbors(b.id)) == 1

    def test_link_many_empty(self, mg):
        assert mg.link_many([]) == 0

    def test_delete_many(self, mg):
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "rel")
        mg.link(c.id, b.id, "rel")
        count = mg.delete_many([a.id, b.id])
        assert count == 2
        assert mg.stats()["nodes"] == 1
        assert len(mg.neighbors(c.id)) == 0  # edge to b cleaned

    def test_delete_many_skips_nonexistent(self, mg):
        a = mg.add("A")
        count = mg.delete_many([a.id, "nonexistent"])
        assert count == 1

    def test_add_many_then_export_import(self, mg):
        nodes = mg.add_many([
            {"label": "N1"}, {"label": "N2"}, {"label": "N3"}
        ])
        mg.link_many([
            {"source": nodes[0].id, "target": nodes[1].id, "relation": "r"},
            {"source": nodes[1].id, "target": nodes[2].id, "relation": "r"},
        ])
        exported = mg.export_json()
        mg2 = MemoryGraph()
        mg2.import_json(exported)
        assert mg2.stats()["nodes"] == 3
        assert mg2.stats()["edges"] == 2
        path = mg2.shortest_path(nodes[0].id, nodes[2].id)
        assert path is not None
        assert len(path) == 3

class TestExportImport:
    def test_export_roundtrip(self, populated):
        mg, a, b, c = populated
        exported = mg.export_json()
        assert exported["version"] == 1
        assert len(exported["nodes"]) == 3
        assert len(exported["edges"]) == 3

        mg2 = MemoryGraph()
        mg2.import_json(exported)
        assert mg2.stats()["nodes"] == 3
        assert mg2.stats()["edges"] == 3
        # Verify recall works on imported graph
        results = mg2.recall("Alice")
        assert len(results) == 1
        assert results[0].label == "Alice"

    def test_import_preserves_ids(self, mg):
        n = mg.add("test", "fact", {"key": "val"}, tags=["t1"])
        exported = mg.export_json()
        mg2 = MemoryGraph()
        mg2.import_json(exported)
        assert mg2.shortest_path(n.id, n.id) == [n.id]

    def test_import_replaces_by_default(self, populated):
        mg, a, b, c = populated
        mg2 = MemoryGraph()
        mg2.add("existing")
        mg2.import_json(mg.export_json())
        assert mg2.stats()["nodes"] == 3  # replaced, not added to

    def test_import_merge_mode(self, populated):
        mg, a, b, c = populated
        mg2 = MemoryGraph()
        extra = mg2.add("extra node")
        mg2.import_json(mg.export_json(), merge=True)
        assert mg2.stats()["nodes"] == 4  # 3 imported + 1 existing

    def test_export_preserves_tags(self, mg):
        n = mg.add("tagged", tags=["a", "b"])
        exported = mg.export_json()
        node_data = exported["nodes"][0]
        assert set(node_data["tags"]) == {"a", "b"}

    def test_import_empty_data(self, mg):
        mg.import_json({})
        assert mg.stats()["nodes"] == 0

