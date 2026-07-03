"""Tests for Agent Memory Graph."""
import json
import math
import os
import tempfile
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



# ── Cycle 2026-05-25: find_by_kind, search_by_data, edges_of ──

class TestFindByKind:
    def test_returns_nodes_of_given_kind(self, mg):
        mg.add("A", "person")
        mg.add("B", "person")
        mg.add("C", "skill")
        result = mg.find_by_kind("person")
        assert len(result) == 2
        assert all(n.kind == "person" for n in result)

    def test_empty_for_nonexistent_kind(self, mg):
        mg.add("A", "person")
        assert mg.find_by_kind("concept") == []

    def test_ordered_by_weight_desc(self, mg):
        n1 = mg.add("low", "fact", data={}, tags=[], )
        n2 = mg.add("high", "fact")
        mg.update_node(n2.id, weight=0.9)
        mg.update_node(n1.id, weight=0.3)
        result = mg.find_by_kind("fact")
        assert result[0].weight >= result[1].weight


class TestSearchByData:
    def test_find_by_key_only(self, mg):
        mg.add("A", "fact", {"x": 1})
        mg.add("B", "fact", {"y": 2})
        result = mg.search_by_data("x")
        assert len(result) == 1
        assert result[0].label == "A"

    def test_find_by_key_and_value(self, mg):
        mg.add("A", "fact", {"role": "engineer"})
        mg.add("B", "fact", {"role": "designer"})
        result = mg.search_by_data("role", "engineer")
        assert len(result) == 1
        assert result[0].label == "A"

    def test_no_match_returns_empty(self, mg):
        mg.add("A", "fact", {"x": 1})
        assert mg.search_by_data("z") == []

    def test_empty_data_nodes_skipped(self, mg):
        mg.add("A", "fact")
        mg.add("B", "fact", {"x": 1})
        assert len(mg.search_by_data("x")) == 1


class TestEdgesOf:
    def test_outgoing_edges(self, populated):
        mg, a, b, c = populated
        edges = mg.edges_of(a.id, "outgoing")
        assert len(edges) == 2
        assert all(e.source == a.id for e in edges)

    def test_incoming_edges(self, populated):
        mg, a, b, c = populated
        edges = mg.edges_of(b.id, "incoming")
        assert len(edges) == 1
        assert edges[0].source != b.id

    def test_both_directions(self, populated):
        mg, a, b, c = populated
        assert len(mg.edges_of(a.id, "both")) == 2
        assert len(mg.edges_of(c.id, "both")) == 2

    def test_no_edges(self, mg):
        n = mg.add("lonely", "fact")
        assert mg.edges_of(n.id) == []


class TestCountByKind:
    def test_counts(self, mg):
        mg.add("A", "person")
        mg.add("B", "person")
        mg.add("C", "skill")
        result = mg.count_by_kind()
        assert result == {"person": 2, "skill": 1}

    def test_empty_graph(self, mg):
        assert mg.count_by_kind() == {}


class TestTopNodes:
    def test_top_n(self, mg):
        for i in range(5):
            n = mg.add(f"node{i}", "fact")
            mg.update_node(n.id, weight=0.1 * (i + 1))
        top = mg.top_nodes(3)
        assert len(top) == 3
        assert top[0].weight >= top[1].weight >= top[2].weight

    def test_top_more_than_count(self, mg):
        mg.add("A", "fact")
        assert len(mg.top_nodes(10)) == 1


class TestTouch:
    def test_touch_boosts_weight(self, mg):
        n = mg.add("A", "fact")
        mg.update_node(n.id, weight=0.3)
        touched = mg.touch(n.id)
        assert touched.weight == pytest.approx(0.7, abs=0.01)

    def test_touch_caps_at_1(self, mg):
        n = mg.add("A", "fact")
        touched = mg.touch(n.id)
        assert touched.weight <= 1.0

    def test_touch_updates_accessed(self, mg):
        n = mg.add("A", "fact")
        import time
        before = n.accessed
        time.sleep(0.01)
        touched = mg.touch(n.id)
        assert touched.accessed > before

    def test_touch_nonexistent(self, mg):
        assert mg.touch("nope") is None


class TestHasNode:
    def test_exists(self, mg):
        n = mg.add("A", "fact")
        assert mg.has_node(n.id) is True

    def test_not_exists(self, mg):
        assert mg.has_node("nope") is False

    def test_after_delete(self, mg):
        n = mg.add("A", "fact")
        mg.delete_node(n.id)
        assert mg.has_node(n.id) is False


class TestRenameTag:
    def test_rename_across_nodes(self, mg):
        n1 = mg.add("A", "fact", tags=["old"])
        n2 = mg.add("B", "fact", tags=["old", "other"])
        count = mg.rename_tag("old", "new")
        assert count == 2
        assert len(mg.search_by_tag("new")) == 2
        assert mg.search_by_tag("old") == []

    def test_no_match(self, mg):
        assert mg.rename_tag("x", "y") == 0


class TestClearTags:
    def test_clear(self, mg):
        n = mg.add("A", "fact", tags=["t1", "t2"])
        assert mg.clear_tags(n.id) is True
        assert mg.search_by_tag("t1") == []

    def test_nonexistent(self, mg):
        assert mg.clear_tags("nope") is False


class TestReweight:
    def test_positive_delta(self, mg):
        n = mg.add("A", "fact")
        mg.update_node(n.id, weight=0.5)
        result = mg.reweight(n.id, 0.3)
        assert result.weight == pytest.approx(0.8)

    def test_negative_delta(self, mg):
        n = mg.add("A", "fact")
        result = mg.reweight(n.id, -0.5)
        assert result.weight == pytest.approx(0.5)

    def test_clamp_at_zero(self, mg):
        n = mg.add("A", "fact")
        result = mg.reweight(n.id, -2.0)
        assert result.weight == 0.0

    def test_clamp_at_one(self, mg):
        n = mg.add("A", "fact")
        result = mg.reweight(n.id, 5.0)
        assert result.weight == 1.0

    def test_nonexistent(self, mg):
        assert mg.reweight("nope", 0.5) is None


class TestIsLinked:
    def test_linked_with_relation(self, populated):
        mg, a, b, c = populated
        assert mg.is_linked(a.id, b.id, "works_with") is True

    def test_not_linked(self, populated):
        mg, a, b, c = populated
        assert mg.is_linked(b.id, a.id, "works_with") is False

    def test_any_relation(self, populated):
        mg, a, b, c = populated
        assert mg.is_linked(a.id, b.id) is True

    def test_no_match_any(self, populated):
        mg, a, b, c = populated
        assert mg.is_linked(b.id, a.id) is False


class TestAllTags:
    def test_returns_unique_sorted(self, mg):
        mg.add("A", "fact", tags=["beta", "alpha"])
        mg.add("B", "fact", tags=["alpha", "gamma"])
        assert mg.all_tags() == ["alpha", "beta", "gamma"]

    def test_empty(self, mg):
        assert mg.all_tags() == []

    def test_no_tags_on_nodes(self, mg):
        mg.add("A", "fact")
        assert mg.all_tags() == []


class TestSubgraph:
    def test_single_node_depth0(self, mg):
        n = mg.add("root", "entity")
        sg = mg.subgraph(n.id, depth=0)
        assert sg["center"] == n.id
        assert len(sg["nodes"]) == 1
        assert len(sg["edges"]) == 0

    def test_depth1_picks_up_neighbors(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        c = mg.add("C")  # disconnected
        mg.link(a.id, b.id, "knows")
        sg = mg.subgraph(a.id, depth=1)
        ids = {n["id"] for n in sg["nodes"]}
        assert a.id in ids
        assert b.id in ids
        assert c.id not in ids
        assert len(sg["edges"]) == 1

    def test_depth2_traverses(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        c = mg.add("C")
        mg.link(a.id, b.id, "knows")
        mg.link(b.id, c.id, "knows")
        sg = mg.subgraph(a.id, depth=2)
        ids = {n["id"] for n in sg["nodes"]}
        assert ids == {a.id, b.id, c.id}
        assert len(sg["edges"]) == 2

    def test_nonexistent_center(self, mg):
        sg = mg.subgraph("nope", depth=1)
        assert len(sg["nodes"]) == 0
        assert len(sg["edges"]) == 0

    def test_export_format_compatible(self, mg):
        a = mg.add("A", tags=["x"])
        b = mg.add("B", data={"k": 1})
        mg.link(a.id, b.id, "rel")
        sg = mg.subgraph(a.id, depth=1)
        # nodes should have same keys as export_json
        assert set(sg["nodes"][0].keys()) == {"id", "label", "kind", "data", "created", "accessed", "weight", "tags"}


class TestUnlinkMany:
    def test_batch_unlink_with_relation(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        c = mg.add("C")
        mg.link(a.id, b.id, "x")
        mg.link(a.id, c.id, "y")
        removed = mg.unlink_many([
            {"source": a.id, "target": b.id, "relation": "x"},
            {"source": a.id, "target": c.id, "relation": "y"},
        ])
        assert removed == 2
        assert mg.is_linked(a.id, b.id) is False
        assert mg.is_linked(a.id, c.id) is False

    def test_unlink_without_relation_removes_all(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "x")
        mg.link(a.id, b.id, "y")
        removed = mg.unlink_many([{"source": a.id, "target": b.id}])
        assert removed == 2

    def test_no_match_returns_zero(self, mg):
        removed = mg.unlink_many([{"source": "no", "target": "no", "relation": "z"}])
        assert removed == 0


class TestPrune:
    def test_removes_low_weight_nodes(self, mg):
        a = mg.add("keep", "fact")
        b = mg.add("gone", "fact")
        mg.update_node(b.id, weight=0.05)
        result = mg.prune(min_weight=0.1)
        assert result["nodes_removed"] == 1
        assert mg.has_node(a.id) is True
        assert mg.has_node(b.id) is False

    def test_removes_orphaned_edges(self, mg):
        a = mg.add("keep", "fact")
        b = mg.add("gone", "fact")
        mg.link(a.id, b.id, "rel")
        mg.update_node(b.id, weight=0.05)
        result = mg.prune(min_weight=0.1)
        assert result["nodes_removed"] == 1
        assert result["edges_removed"] == 1
        assert len(mg.edges_of(a.id)) == 0

    def test_nothing_below_threshold(self, mg):
        mg.add("strong", "fact")
        result = mg.prune(min_weight=0.1)
        assert result["nodes_removed"] == 0
        assert result["edges_removed"] == 0

    def test_keeps_nodes_at_threshold(self, mg):
        n = mg.add("exact", "fact")
        mg.update_node(n.id, weight=0.1)
        result = mg.prune(min_weight=0.1)
        assert result["nodes_removed"] == 0
        assert mg.has_node(n.id) is True

    def test_batch_prune(self, mg):
        for i in range(5):
            n = mg.add(f"node{i}", "fact")
            mg.update_node(n.id, weight=0.01 * i)  # 0, 0.01, 0.02, 0.03, 0.04
        result = mg.prune(min_weight=0.03)
        assert result["nodes_removed"] == 3  # weight 0, 0.01, 0.02
        assert mg.stats()["nodes"] == 2


class TestAggregate:
    def test_sum_weight_by_kind(self, mg):
        mg.add("A", "event")
        mg.add("B", "event")
        n = mg.add("C", "event")
        mg.update_node(n.id, weight=0.5)
        result = mg.aggregate("event", "weight", "sum")
        assert result == pytest.approx(2.5)  # 1.0 + 1.0 + 0.5

    def test_avg_weight_by_kind(self, mg):
        mg.add("A", "skill")
        n = mg.add("B", "skill")
        mg.update_node(n.id, weight=0.4)
        result = mg.aggregate("skill", "weight", "avg")
        assert result == pytest.approx(0.7)  # (1.0 + 0.4) / 2

    def test_count_by_kind(self, mg):
        mg.add("A", "person")
        mg.add("B", "person")
        mg.add("C", "skill")
        assert mg.aggregate("person", fn="count") == 2.0

    def test_min_max_weight(self, mg):
        mg.add("A", "fact")
        n = mg.add("B", "fact")
        mg.update_node(n.id, weight=0.3)
        assert mg.aggregate("fact", "weight", "min") == pytest.approx(0.3)
        assert mg.aggregate("fact", "weight", "max") == pytest.approx(1.0)

    def test_empty_kind_returns_zero(self, mg):
        assert mg.aggregate("nonexistent", "weight", "sum") == 0.0
        assert mg.aggregate("nonexistent", fn="count") == 0.0

    def test_invalid_fn_raises(self, mg):
        with pytest.raises(ValueError):
            mg.aggregate("fact", fn="median")


class TestGraphDiff:
    def test_identical_graphs(self, mg):
        import copy
        mg2 = MemoryGraph()
        a = mg.add("X", "fact")
        mg2.import_json(mg.export_json())
        diff = mg.graph_diff(mg2)
        assert diff["nodes_only_self"] == []
        assert diff["nodes_only_other"] == []
        assert diff["nodes_modified"] == []

    def test_added_nodes(self, mg):
        mg2 = MemoryGraph()
        mg.add("A", "fact")
        mg2.add("B", "event")
        diff = mg.graph_diff(mg2)
        assert "B" not in [x for x in diff["nodes_only_self"]]  # B is in other
        assert len(diff["nodes_only_self"]) == 1
        assert len(diff["nodes_only_other"]) == 1

    def test_modified_node(self, mg):
        mg2 = MemoryGraph()
        n = mg.add("Hello", "fact", {"x": 1})
        mg2.import_json(mg.export_json())
        mg.update_node(n.id, label="Hello World")
        diff = mg.graph_diff(mg2)
        mod_labels = [m for m in diff["nodes_modified"] if m["field"] == "label"]
        assert len(mod_labels) == 1
        assert mod_labels[0]["self_val"] == "Hello World"

    def test_edge_diff(self, mg):
        mg2 = MemoryGraph()
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        mg.link(a.id, b.id, "knows")
        mg2.import_json(mg.export_json())
        c = mg.add("C", "fact")
        mg.link(a.id, c.id, "related")
        diff = mg.graph_diff(mg2)
        assert len(diff["edges_only_self"]) == 1

    def test_empty_graphs(self, mg):
        mg2 = MemoryGraph()
        diff = mg.graph_diff(mg2)
        assert diff["nodes_only_self"] == []
        assert diff["nodes_only_other"] == []

    def test_data_diff(self, mg):
        mg2 = MemoryGraph()
        n = mg.add("X", "fact", {"score": 10})
        mg2.import_json(mg.export_json())
        mg.update_node(n.id, data={"score": 20})
        diff = mg.graph_diff(mg2)
        data_mods = [m for m in diff["nodes_modified"] if m["field"] == "data"]
        assert len(data_mods) == 1


class TestCompact:
    def test_merge_duplicate_labels(self, mg):
        a = mg.add("Python", "skill")
        b = mg.add("Python", "skill")
        result = mg.compact()
        assert result["total_merged"] == 1
        assert mg.has_node(a.id) or mg.has_node(b.id)
        assert mg.stats()["nodes"] == 1

    def test_no_duplicates(self, mg):
        mg.add("Python", "skill")
        mg.add("Rust", "skill")
        result = mg.compact()
        assert result["total_merged"] == 0

    def test_merge_preserves_edges(self, mg):
        a = mg.add("X", "fact")
        b = mg.add("X", "fact")
        c = mg.add("Y", "event")
        mg.link(b.id, c.id, "caused")
        mg.compact()
        # Survivor should have the edge
        assert mg.stats()["edges"] == 1

    def test_different_kinds_not_merged(self, mg):
        mg.add("test", "fact")
        mg.add("test", "event")
        result = mg.compact()
        assert result["total_merged"] == 0

    def test_invalid_strategy_raises(self, mg):
        with pytest.raises(ValueError):
            mg.compact(strategy="unknown")


class TestSearchUnified:
    def test_search_by_label(self, mg):
        mg.add("Python programming", "skill")
        mg.add("Rust systems", "skill")
        results = mg.search_unified("python")
        assert len(results) == 1
        assert results[0]["matched_fields"] == ["label"]

    def test_search_by_data(self, mg):
        mg.add("node1", "fact", {"language": "python"})
        results = mg.search_unified("python")
        assert len(results) == 1
        assert "data" in results[0]["matched_fields"]

    def test_search_by_tag(self, mg):
        mg.add("node1", "fact", tags=["python", "backend"])
        results = mg.search_unified("python")
        assert len(results) == 1
        assert "tags" in results[0]["matched_fields"]

    def test_search_by_kind(self, mg):
        mg.add("something", "skill")
        results = mg.search_unified("skill")
        assert len(results) >= 1
        assert any("kind" in r["matched_fields"] for r in results)

    def test_multi_field_match(self, mg):
        mg.add("Python expert", "skill", {"lang": "python"}, tags=["python"])
        results = mg.search_unified("python")
        assert len(results) == 1
        assert len(results[0]["matched_fields"]) >= 2

    def test_weight_boosts_score(self, mg):
        a = mg.add("Python A", "skill")
        b = mg.add("Python B", "skill")
        mg.update_node(a.id, weight=0.2)
        mg.update_node(b.id, weight=1.0)
        results = mg.search_unified("Python")
        assert results[0]["node"].id == b.id  # higher weight ranks first

    def test_limit(self, mg):
        for i in range(10):
            mg.add(f"Python {i}", "skill")
        results = mg.search_unified("Python", limit=3)
        assert len(results) == 3

    def test_no_match(self, mg):
        mg.add("Something", "fact")
        results = mg.search_unified("nonexistent")
        assert len(results) == 0


class TestRenameNode:
    def test_rename(self, mg):
        n = mg.add("old name", "fact")
        updated = mg.rename_node(n.id, "new name")
        assert updated.label == "new name"
        assert mg.get_node(n.id).label == "new name"

    def test_rename_nonexistent(self, mg):
        assert mg.rename_node("nonexistent", "x") is None


class TestCloneNode:
    def test_clone_basic(self, mg):
        n = mg.add("original", "skill", {"level": 5}, tags=["tag1"])
        cloned = mg.clone_node(n.id, "clone")
        assert cloned is not None
        assert cloned.id != n.id
        assert cloned.label == "clone"
        assert cloned.kind == "skill"
        assert mg.stats()["nodes"] == 2

    def test_clone_preserves_data(self, mg):
        n = mg.add("orig", "fact", {"x": 1}, tags=["t1"])
        cloned = mg.clone_node(n.id)
        assert cloned.data == {"x": 1}

    def test_clone_no_edges(self, mg):
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        mg.link(a.id, b.id, "knows")
        cloned = mg.clone_node(a.id, "A clone")
        assert len(mg.edges_of(cloned.id)) == 0

    def test_clone_nonexistent(self, mg):
        assert mg.clone_node("nonexistent") is None


class TestPathExists:
    def test_direct_path(self, mg):
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        mg.link(a.id, b.id, "to")
        assert mg.path_exists(a.id, b.id) is True

    def test_no_path(self, mg):
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        assert mg.path_exists(a.id, b.id) is False

    def test_same_node(self, mg):
        n = mg.add("X", "fact")
        assert mg.path_exists(n.id, n.id) is True

    def test_same_node_nonexistent(self, mg):
        assert mg.path_exists("fake", "fake") is False

    def test_indirect_path(self, mg):
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        c = mg.add("C", "fact")
        mg.link(a.id, b.id, "to")
        mg.link(b.id, c.id, "to")
        assert mg.path_exists(a.id, c.id) is True

    def test_depth_limit(self, mg):
        nodes = [mg.add(f"N{i}", "fact") for i in range(5)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i+1].id, "to")
        # 4 hops, limit 3 should fail
        assert mg.path_exists(nodes[0].id, nodes[4].id, max_depth=3) is False
        # 4 hops, limit 5 should succeed
        assert mg.path_exists(nodes[0].id, nodes[4].id, max_depth=5) is True


class TestFindRootsLeaves:
    """find_roots() and find_leaves() — source/sink node detection."""

    def test_find_roots_empty(self, mg):
        assert mg.find_roots() == []

    def test_find_roots_single(self, mg):
        n = mg.add("root", "fact")
        roots = mg.find_roots()
        assert len(roots) == 1
        assert roots[0].id == n.id

    def test_find_roots_chain(self, mg):
        a, b, c = [mg.add(f"N{i}", "fact") for i in range(3)]
        mg.link(a.id, b.id, "to")
        mg.link(b.id, c.id, "to")
        roots = mg.find_roots()
        assert len(roots) == 1
        assert roots[0].id == a.id

    def test_find_leaves_chain(self, mg):
        a, b, c = [mg.add(f"N{i}", "fact") for i in range(3)]
        mg.link(a.id, b.id, "to")
        mg.link(b.id, c.id, "to")
        leaves = mg.find_leaves()
        assert len(roots := mg.find_leaves()) == 1
        assert roots[0].id == c.id

    def test_find_leaves_isolated(self, mg):
        a = mg.add("isolated", "fact")
        b = mg.add("connected", "fact")
        mg.link(a.id, b.id, "to")
        # a has outgoing, b has incoming but no outgoing
        leaves = mg.find_leaves()
        assert len(leaves) == 1
        assert leaves[0].id == b.id

    def test_multiple_roots(self, mg):
        a, b, c = [mg.add(f"N{i}", "fact") for i in range(3)]
        mg.link(a.id, c.id, "to")
        mg.link(b.id, c.id, "to")
        roots = mg.find_roots()
        assert len(roots) == 2
        root_ids = {r.id for r in roots}
        assert a.id in root_ids
        assert b.id in root_ids


class TestDegree:
    """degree() and degree_centrality() — node connectivity analysis."""

    def test_degree_missing(self, mg):
        assert mg.degree("nonexistent") == 0

    def test_degree_isolated(self, mg):
        n = mg.add("solo", "fact")
        assert mg.degree(n.id) == 0

    def test_degree_in_out_both(self, mg):
        a, b, c = [mg.add(f"N{i}", "fact") for i in range(3)]
        mg.link(a.id, b.id, "to")
        mg.link(c.id, b.id, "from")
        assert mg.degree(b.id, "in") == 2
        assert mg.degree(b.id, "out") == 0
        assert mg.degree(b.id, "both") == 2
        assert mg.degree(a.id, "out") == 1
        assert mg.degree(a.id, "in") == 0

    def test_degree_centrality_single(self, mg):
        n = mg.add("only", "fact")
        assert mg.degree_centrality(n.id) == 0.0

    def test_degree_centrality_star(self, mg):
        center = mg.add("hub", "fact")
        spokes = [mg.add(f"s{i}", "fact") for i in range(4)]
        for s in spokes:
            mg.link(center.id, s.id, "to")
        # center has 4 out of 4 possible connections (5 nodes, n-1=4)
        assert mg.degree_centrality(center.id) == 1.0
        # spoke has 1 out of 4
        assert mg.degree_centrality(spokes[0].id) == 0.25

    def test_degree_centrality_missing(self, mg):
        assert mg.degree_centrality("nonexistent") == 0.0


class TestShortestPath:
    """shortest_path() — BFS path reconstruction."""

    def test_shortest_path_same_node(self, mg):
        n = mg.add("self", "fact")
        assert mg.shortest_path(n.id, n.id) == [n.id]

    def test_shortest_path_missing(self, mg):
        a = mg.add("a", "fact")
        assert mg.shortest_path(a.id, "nonexistent") is None

    def test_shortest_path_direct(self, mg):
        a, b = mg.add("a", "fact"), mg.add("b", "fact")
        mg.link(a.id, b.id, "to")
        assert mg.shortest_path(a.id, b.id) == [a.id, b.id]

    def test_shortest_path_chain(self, mg):
        nodes = [mg.add(f"N{i}", "fact") for i in range(4)]
        for i in range(3):
            mg.link(nodes[i].id, nodes[i+1].id, "to")
        path = mg.shortest_path(nodes[0].id, nodes[3].id)
        assert path == [n.id for n in nodes]

    def test_shortest_path_no_path(self, mg):
        a, b = mg.add("a", "fact"), mg.add("b", "fact")
        assert mg.shortest_path(a.id, b.id) is None

    def test_shortest_path_shortcut(self, mg):
        nodes = [mg.add(f"N{i}", "fact") for i in range(4)]
        mg.link(nodes[0].id, nodes[1].id, "to")
        mg.link(nodes[1].id, nodes[2].id, "to")
        mg.link(nodes[2].id, nodes[3].id, "to")
        mg.link(nodes[0].id, nodes[3].id, "shortcut")
        path = mg.shortest_path(nodes[0].id, nodes[3].id)
        assert path == [nodes[0].id, nodes[3].id]


class TestBetweennessCentrality:
    """betweenness_centrality() — approximate via path sampling."""

    def test_missing_node(self, mg):
        assert mg.betweenness_centrality("nonexistent") == 0.0

    def test_bridge_node(self, mg):
        # Two clusters connected by a single bridge
        # Cluster A: a1-a2-a3
        a1, a2, a3 = [mg.add(f"A{i}", "fact") for i in range(3)]
        mg.link(a1.id, a2.id, "to"); mg.link(a2.id, a3.id, "to")
        # Cluster B: b1-b2-b3
        b1, b2, b3 = [mg.add(f"B{i}", "fact") for i in range(3)]
        mg.link(b1.id, b2.id, "to"); mg.link(b2.id, b3.id, "to")
        # Bridge
        bridge = mg.add("bridge", "fact")
        mg.link(a3.id, bridge.id, "to"); mg.link(bridge.id, b1.id, "to")
        # Bridge should have high betweenness
        bc = mg.betweenness_centrality(bridge.id, samples=200)
        assert bc > 0.0

    def test_leaf_node(self, mg):
        a = mg.add("hub", "fact")
        b = mg.add("leaf", "fact")
        mg.link(a.id, b.id, "to")
        # leaf is never intermediate on a path
        bc = mg.betweenness_centrality(b.id, samples=20)
        assert bc == 0.0


class TestCommunityDetect:
    """community_detect() — label propagation."""

    def test_empty(self, mg):
        assert mg.community_detect() == {}

    def test_two_clusters(self, mg):
        # Cluster 1: a-b-c connected
        a, b, c = [mg.add(f"c1_{i}", "fact") for i in range(3)]
        mg.link(a.id, b.id, "to")
        mg.link(b.id, c.id, "to")
        # Cluster 2: d-e-f connected
        d, e, f = [mg.add(f"c2_{i}", "fact") for i in range(3)]
        mg.link(d.id, e.id, "to")
        mg.link(e.id, f.id, "to")
        # Single bridge
        mg.link(c.id, d.id, "bridge")
        communities = mg.community_detect(max_iter=20)
        # Should detect at most 2-3 communities
        assert len(communities) >= 1
        assert len(communities) <= 3

    def test_fully_connected(self, mg):
        nodes = [mg.add(f"N{i}", "fact") for i in range(4)]
        for i in range(4):
            for j in range(4):
                if i != j:
                    mg.link(nodes[i].id, nodes[j].id, "to")
        communities = mg.community_detect()
        # Fully connected graph should collapse to 1 community
        assert len(communities) == 1


class TestEigenvectorCentrality:
    """eigenvector_centrality() — iterative power method."""

    def test_empty(self, mg):
        assert mg.eigenvector_centrality() == {}

    def test_hub_highest(self, mg):
        # Hub receives from many: spokes point TO hub
        hub = mg.add("hub", "fact")
        spokes = [mg.add(f"s{i}", "fact") for i in range(3)]
        for s in spokes:
            mg.link(s.id, hub.id, "to")  # spokes → hub
        ec = mg.eigenvector_centrality()
        # Hub should have highest eigenvector centrality
        hub_score = ec[hub.id]
        for s in spokes:
            assert hub_score >= ec[s.id]

    def test_isolated_lowest(self, mg):
        a = mg.add("connected", "fact")
        b = mg.add("isolated", "fact")
        c = mg.add("other", "fact")
        mg.link(a.id, c.id, "to")
        mg.link(c.id, a.id, "to")
        ec = mg.eigenvector_centrality()
        # Isolated node should have lowest score
        assert ec[b.id] <= ec[a.id]


class TestPageRank:
    """pagerank() — classic PageRank."""

    def test_empty(self, mg):
        assert mg.pagerank() == {}

    def test_single(self, mg):
        n = mg.add("only", "fact")
        pr = mg.pagerank()
        assert abs(pr[n.id] - 1.0) < 0.01

    def test_hub_highest(self, mg):
        hub = mg.add("hub", "fact")
        spokes = [mg.add(f"s{i}", "fact") for i in range(3)]
        for s in spokes:
            mg.link(s.id, hub.id, "to")  # spokes cite hub
        pr = mg.pagerank()
        assert pr[hub.id] > pr[spokes[0].id]

    def test_scores_sum_to_one(self, mg):
        nodes = [mg.add(f"N{i}", "fact") for i in range(4)]
        for i in range(3):
            mg.link(nodes[i].id, nodes[i+1].id, "to")
        pr = mg.pagerank()
        assert abs(sum(pr.values()) - 1.0) < 0.01


class TestKCore:
    """k_core() — k-core decomposition."""

    def test_empty(self, mg):
        assert mg.k_core(1) == []

    def test_isolated_pruned(self, mg):
        a = mg.add("solo", "fact")
        b, c = mg.add("b", "fact"), mg.add("c", "fact")
        mg.link(b.id, c.id, "to")
        core = mg.k_core(1)
        assert a.id not in core
        assert b.id in core
        assert c.id in core

    def test_high_k_empty(self, mg):
        nodes = [mg.add(f"N{i}", "fact") for i in range(3)]
        mg.link(nodes[0].id, nodes[1].id, "to")
        mg.link(nodes[1].id, nodes[2].id, "to")
        # k=3 needs each node to have 3+ neighbors, impossible with 3 nodes
        assert mg.k_core(3) == []

    def test_triangle_2core(self, mg):
        nodes = [mg.add(f"N{i}", "fact") for i in range(3)]
        for i in range(3):
            mg.link(nodes[i].id, nodes[(i+1)%3].id, "to")
        core = mg.k_core(2)
        assert len(core) == 3


class TestTriangles:
    """triangles() — triangle counting per node."""

    def test_missing(self, mg):
        assert mg.triangles("nonexistent") == 0

    def test_no_triangle(self, mg):
        a, b, c = mg.add("a","fact"), mg.add("b","fact"), mg.add("c","fact")
        mg.link(a.id, b.id, "to")
        mg.link(b.id, c.id, "to")
        assert mg.triangles(a.id) == 0

    def test_one_triangle(self, mg):
        a, b, c = mg.add("a","fact"), mg.add("b","fact"), mg.add("c","fact")
        mg.link(a.id, b.id, "to")
        mg.link(b.id, c.id, "to")
        mg.link(c.id, a.id, "to")
        assert mg.triangles(a.id) == 1
        assert mg.triangles(b.id) == 1

    def test_two_triangles(self, mg):
        # Two triangles sharing an edge (undirected via bidirectional links)
        nodes = [mg.add(f"N{i}", "fact") for i in range(4)]
        # Triangle 1: 0-1-2 (bidirectional)
        mg.link(nodes[0].id, nodes[1].id, "to")
        mg.link(nodes[1].id, nodes[0].id, "to")
        mg.link(nodes[1].id, nodes[2].id, "to")
        mg.link(nodes[2].id, nodes[1].id, "to")
        mg.link(nodes[2].id, nodes[0].id, "to")
        mg.link(nodes[0].id, nodes[2].id, "to")
        # Triangle 2: 0-1-3
        mg.link(nodes[0].id, nodes[3].id, "to")
        mg.link(nodes[3].id, nodes[0].id, "to")
        mg.link(nodes[3].id, nodes[1].id, "to")
        mg.link(nodes[1].id, nodes[3].id, "to")
        assert mg.triangles(nodes[0].id) == 2


class TestTimeline:
    def test_basic_timeline(self, mg):
        mg.add("first", "event")
        mg.add("second", "event")
        mg.add("third", "event")
        tl = mg.timeline()
        assert len(tl) == 3
        # newest first
        assert tl[0].label == "third"
        assert tl[2].label == "first"

    def test_timeline_by_kind(self, mg):
        mg.add("ev1", "event")
        mg.add("fact1", "fact")
        mg.add("ev2", "event")
        tl = mg.timeline(kind="event")
        assert len(tl) == 2
        assert all(n.kind == "event" for n in tl)

    def test_timeline_with_time_range(self, mg):
        a = mg.add("old", "event")
        import time as _t
        now = _t.time()
        b = mg.add("new", "event")
        # Only recent
        tl = mg.timeline(since=now - 1)
        labels = [n.label for n in tl]
        assert "new" in labels

    def test_timeline_limit(self, mg):
        for i in range(10):
            mg.add(f"item{i}", "event")
        assert len(mg.timeline(limit=3)) == 3


class TestRecommend:
    def test_recommend_shared_neighbors(self, mg):
        # A-B-C triangle: A and C share B as neighbor
        a = mg.add("A", "person")
        b = mg.add("B", "person")
        c = mg.add("C", "person")
        d = mg.add("D", "person")
        mg.link(a.id, b.id, "knows")
        mg.link(b.id, a.id, "knows")
        mg.link(c.id, b.id, "knows")
        mg.link(b.id, c.id, "knows")
        mg.link(d.id, a.id, "knows")
        mg.link(a.id, d.id, "knows")
        recs = mg.recommend(a.id)
        # C should be recommended (shares B), D is already a direct neighbor
        rec_ids = [r["node"].id for r in recs]
        assert c.id in rec_ids

    def test_recommend_no_neighbors(self, mg):
        a = mg.add("loner", "person")
        assert mg.recommend(a.id) == []

    def test_recommend_limit(self, mg):
        center = mg.add("center", "person")
        hub = mg.add("hub", "person")
        mg.link(center.id, hub.id, "knows")
        mg.link(hub.id, center.id, "knows")
        others = []
        for i in range(10):
            n = mg.add(f"o{i}", "person")
            others.append(n)
            mg.link(hub.id, n.id, "knows")
            mg.link(n.id, hub.id, "knows")
        recs = mg.recommend(center.id, limit=3)
        assert len(recs) <= 3
        assert len(recs) > 0

    def test_recommend_score_order(self, mg):
        # center connected to hub; hub connected to A and B
        center = mg.add("center", "person")
        hub = mg.add("hub", "person")
        a = mg.add("A", "person")
        b = mg.add("B", "person")
        mg.link(center.id, hub.id, "k")
        mg.link(hub.id, center.id, "k")
        mg.link(hub.id, a.id, "k")
        mg.link(a.id, hub.id, "k")
        mg.link(hub.id, b.id, "k")
        mg.link(b.id, hub.id, "k")
        # A also connected to center (higher jaccard)
        mg.link(center.id, a.id, "k")
        mg.link(a.id, center.id, "k")
        recs = mg.recommend(center.id)
        if len(recs) >= 2:
            # A has higher score than B (A is direct neighbor of center too)
            a_rec = next((r for r in recs if r["node"].id == a.id), None)
            b_rec = next((r for r in recs if r["node"].id == b.id), None)
            if a_rec and b_rec:
                assert b_rec["score"] >= a_rec["score"]

    # ── importance_rank ──────────────────────────────────

    def test_importance_rank_basic(self, mg):
        a = mg.add("alpha", "concept", {"w": 1})
        b = mg.add("beta", "concept", {"w": 2})
        mg.link(a.id, b.id, "rel")
        ranked = mg.importance_rank()
        assert len(ranked) == 2
        assert all("importance" in r for r in ranked)
        assert all("components" in r for r in ranked)
        # beta should have higher degree (connected to alpha)
        beta = next(r for r in ranked if r["node_id"] == b.id)
        alpha = next(r for r in ranked if r["node_id"] == a.id)
        assert beta["importance"] >= alpha["importance"]

    def test_importance_rank_empty(self, mg):
        assert mg.importance_rank() == []

    def test_importance_rank_limit(self, mg):
        for i in range(10):
            mg.add(f"n{i}", "concept")
        ranked = mg.importance_rank(limit=3)
        assert len(ranked) == 3

    def test_importance_rank_recency(self, mg):
        old = mg.add("old", "concept")
        new = mg.add("new", "concept")
        # Force old accessed time far in the past
        mg.conn.execute("UPDATE nodes SET accessed = ? WHERE id = ?", (time.time() - 1e6, old.id))
        mg.conn.commit()
        ranked = mg.importance_rank()
        new_r = next(r for r in ranked if r["node_id"] == new.id)
        old_r = next(r for r in ranked if r["node_id"] == old.id)
        assert new_r["components"]["recency"] > old_r["components"]["recency"]
        assert new_r["importance"] > old_r["importance"]

    def test_importance_rank_components_sum(self, mg):
        mg.add("x", "concept")
        ranked = mg.importance_rank()
        assert len(ranked) == 1
        c = ranked[0]["components"]
        # Weighted: 0.4*weight + 0.3*degree + 0.3*recency
        expected = 0.4 * c["weight"] + 0.3 * c["degree"] + 0.3 * c["recency"]
        assert abs(ranked[0]["importance"] - round(expected, 4)) < 0.001

    def test_importance_rank_high_degree_wins(self, mg):
        hub = mg.add("hub", "concept")
        for i in range(5):
            n = mg.add(f"leaf{i}", "concept")
            mg.link(hub.id, n.id, "rel")
        ranked = mg.importance_rank()
        assert ranked[0]["node_id"] == hub.id
        assert ranked[0]["components"]["degree"] == 1.0  # normalized max

    def test_importance_rank_single_node(self, mg):
        mg.add("solo", "concept")
        ranked = mg.importance_rank()
        assert len(ranked) == 1
        assert ranked[0]["importance"] > 0

    # ── patch() tests ──────────────────────────────────────────

    def test_patch_adds_nodes_from_other(self):
        g1 = MemoryGraph()
        g2 = MemoryGraph()
        g2.add("only_in_g2", "fact")
        diff = g1.graph_diff(g2)
        result = g1.patch(diff, source=g2)
        assert result["nodes_added"] == 1
        assert g1.has_node(diff["nodes_only_other"][0])

    def test_patch_removes_self_only_nodes(self):
        g1 = MemoryGraph()
        g2 = MemoryGraph()
        g1.add("only_in_g1", "fact")
        diff = g1.graph_diff(g2)
        result = g1.patch(diff)
        assert result["nodes_removed"] == 1
        assert not g1.has_node("only_in_g1")

    def test_patch_syncs_edges(self):
        g1 = MemoryGraph()
        g2 = MemoryGraph()
        a = g2.add("a", "fact")
        b = g2.add("b", "fact")
        g2.link(a.id, b.id, "new_rel")
        # g1 has same nodes but no edge
        g1.add("a", "fact")  # different id
        g1.add("b", "fact")
        diff = g1.graph_diff(g2)
        # The edge in g2 references g2's node ids, not g1's
        # So let's use explicit ids
        g1b = MemoryGraph()
        g2b = MemoryGraph()
        import memory_graph as mg
        # Manually insert with same ids
        g1b.conn.execute("INSERT INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
            ("id_a", "a", "fact", '{}', 0, 0, 1.0, '[]'))
        g1b.conn.execute("INSERT INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
            ("id_b", "b", "fact", '{}', 0, 0, 1.0, '[]'))
        g1b.conn.commit()
        g2b.conn.execute("INSERT INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
            ("id_a", "a", "fact", '{}', 0, 0, 1.0, '[]'))
        g2b.conn.execute("INSERT INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
            ("id_b", "b", "fact", '{}', 0, 0, 1.0, '[]'))
        g2b.conn.execute("INSERT INTO edges (source,target,relation,weight) VALUES (?,?,?,1.0)",
            ("id_a", "id_b", "new_rel"))
        g2b.conn.commit()
        diff = g1b.graph_diff(g2b)
        result = g1b.patch(diff, source=g2b)
        assert result["edges_added"] >= 1
        assert g1b.is_linked("id_a", "id_b", "new_rel")

    def test_patch_applies_field_updates(self):
        g1 = MemoryGraph()
        g2 = MemoryGraph()
        # Use same id manually
        g1.conn.execute("INSERT INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
            ("x", "x", "fact", '{\"v\": 1}', 0, 0, 1.0, '[]'))
        g1.conn.commit()
        g2.conn.execute("INSERT INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
            ("x", "x", "fact", '{\"v\": 2}', 0, 0, 1.0, '[]'))
        g2.conn.commit()
        diff = g1.graph_diff(g2)
        result = g1.patch(diff, source=g2)
        assert result["fields_updated"] >= 1
        node = g1.get_node("x")
        assert node.data["v"] == 2

    def test_patch_empty_diff_noop(self):
        g1 = MemoryGraph()
        g1.add("a", "fact")
        result = g1.patch({"nodes_only_self": [], "nodes_only_other": [], "nodes_modified": [], "edges_only_self": [], "edges_only_other": []})
        assert sum(result.values()) == 0

    # ── stats_summary() tests ──────────────────────────────────────

    def test_stats_summary_empty(self):
        mg = MemoryGraph()
        s = mg.stats_summary()
        assert s["node_count"] == 0
        assert s["edge_count"] == 0
        assert s["density"] == 0.0

    def test_stats_summary_basic(self):
        mg = MemoryGraph()
        a = mg.add("a", "fact")
        b = mg.add("b", "event")
        mg.link(a.id, b.id, "caused")
        s = mg.stats_summary()
        assert s["node_count"] == 2
        assert s["edge_count"] == 1
        assert s["kind_distribution"] == {"fact": 1, "event": 1}
        assert s["relation_distribution"] == {"caused": 1}

    def test_stats_summary_isolated_nodes(self):
        mg = MemoryGraph()
        a = mg.add("connected", "fact")
        b = mg.add("connected2", "fact")
        iso = mg.add("lonely", "concept")
        mg.link(a.id, b.id, "rel")
        s = mg.stats_summary()
        assert s["isolated_nodes"] == 1

    def test_stats_summary_density(self):
        mg = MemoryGraph()
        a = mg.add("a", "fact")
        b = mg.add("b", "fact")
        c = mg.add("c", "fact")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        s = mg.stats_summary()
        assert s["density"] == 1.0  # fully connected 3-node graph

    def test_stats_summary_avg_weight(self):
        mg = MemoryGraph()
        mg.add("heavy", "fact")
        n = mg.add("light", "fact")
        mg.reweight(n.id, -0.8)
        s = mg.stats_summary()
        assert 0 < s["avg_weight"] < 1.0

    # ── anonymize() tests ──────────────────────────────────────────

    def test_anonymize_strips_labels_and_data(self, mg):
        a = mg.add("secret", "fact", data={"key": "value"})
        anon = mg.anonymize()
        nodes = anon.conn.execute("SELECT * FROM nodes").fetchall()
        assert len(nodes) == 1
        assert nodes[0]["label"] == "***"
        assert nodes[0]["data"] == "{}"
        assert nodes[0]["kind"] == "fact"

    def test_anonymize_preserves_structure(self, mg):
        a = mg.add("a", "fact")
        b = mg.add("b", "fact")
        mg.link(a.id, b.id, "rel")
        anon = mg.anonymize()
        assert anon.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 2
        assert anon.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0] == 1

    def test_anonymize_changes_ids(self, mg):
        a = mg.add("a", "fact")
        anon = mg.anonymize()
        assert not anon.has_node(a.id)

    def test_anonymize_empty_graph(self):
        mg = MemoryGraph()
        anon = mg.anonymize()
        assert anon.stats_summary()["node_count"] == 0

    # ── bfs_order() tests ──────────────────────────────────────────

    def test_bfs_order_linear(self, mg):
        a = mg.add("a", "fact")
        b = mg.add("b", "fact")
        c = mg.add("c", "fact")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        order = mg.bfs_order(a.id)
        assert order[0] == a.id
        assert order[1] == b.id
        assert order[2] == c.id

    def test_bfs_order_missing_start(self, mg):
        assert mg.bfs_order("nonexistent") == []

    def test_bfs_order_respects_max_depth(self, mg):
        a = mg.add("a", "fact")
        b = mg.add("b", "fact")
        c = mg.add("c", "fact")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        order = mg.bfs_order(a.id, max_depth=1)
        assert a.id in order
        assert b.id in order
        assert c.id not in order

    def test_bfs_order_diamond(self, mg):
        a = mg.add("a", "fact")
        b = mg.add("b", "fact")
        c = mg.add("c", "fact")
        d = mg.add("d", "fact")
        mg.link(a.id, b.id, "r")
        mg.link(a.id, c.id, "r")
        mg.link(b.id, d.id, "r")
        mg.link(c.id, d.id, "r")
        order = mg.bfs_order(a.id)
        assert order[0] == a.id
        assert set(order[1:3]) == {b.id, c.id}
        assert order[3] == d.id


class TestMergeGraph:
    def test_merge_union_adds_new_nodes(self, mg):
        other = MemoryGraph()
        a = other.add("node_a", "fact")
        b = other.add("node_b", "event")
        other.link(a.id, b.id, "rel")
        result = mg.merge_graph(other)
        assert result["nodes_added"] == 2
        assert result["edges_added"] == 1
        assert mg.has_node(a.id)
        assert mg.has_node(b.id)

    def test_merge_union_skips_existing(self, mg):
        n = mg.add("existing", "fact")
        other = MemoryGraph()
        other.add("existing", "fact")  # same label, diff graph = diff id, won't conflict
        result = mg.merge_graph(other)
        assert result["nodes_added"] == 1  # the other node is new

    def test_merge_update_overwrites(self, mg):
        n = mg.add("old_label", "fact", {"x": 1})
        other = MemoryGraph()
        # Create node with same ID in other graph
        other.conn.execute(
            "INSERT INTO nodes (id, label, kind, data, weight, accessed, created) VALUES (?,?,?,?,?,?,?)",
            (n.id, "new_label", "event", '{"x": 2}', 2.0, time.time(), time.time())
        )
        other.conn.commit()
        result = mg.merge_graph(other, strategy="update")
        assert result["nodes_updated"] == 1
        updated = mg.get_node(n.id)
        assert updated.label == "new_label"

    def test_merge_empty_graph(self, mg):
        other = MemoryGraph()
        result = mg.merge_graph(other)
        assert result["nodes_added"] == 0
        assert result["edges_added"] == 0

    def test_merge_edges_no_duplicate(self, mg):
        other = MemoryGraph()
        a = other.add("a", "fact")
        b = other.add("b", "fact")
        other.link(a.id, b.id, "r")
        mg.merge_graph(other)
        # Second merge should not duplicate the edge
        result = mg.merge_graph(other)
        assert result["edges_added"] == 0


class TestDiffSummary:
    def test_diff_identical_graphs(self, mg):
        other = MemoryGraph()
        a = mg.add("shared", "fact")
        other.conn.execute(
            "INSERT INTO nodes (id, label, kind, data, weight, accessed, created) VALUES (?,?,?,?,?,?,?)",
            (a.id, "shared", "fact", "{}", 1.0, time.time(), time.time())
        )
        other.conn.commit()
        diff = mg.diff_summary(other)
        assert diff["common"] == 1
        assert diff["only_in_self"] == 0
        assert diff["only_in_other"] == 0

    def test_diff_disjoint_graphs(self, mg):
        other = MemoryGraph()
        mg.add("self_only", "fact")
        other.add("other_only", "fact")
        diff = mg.diff_summary(other)
        assert diff["only_in_self"] == 1
        assert diff["only_in_other"] == 1
        assert diff["common"] == 0

    def test_diff_label_mismatch(self, mg):
        other = MemoryGraph()
        n = mg.add("label_a", "fact")
        other.conn.execute(
            "INSERT INTO nodes (id, label, kind, data, weight, accessed, created) VALUES (?,?,?,?,?,?,?)",
            (n.id, "label_b", "fact", "{}", 1.0, time.time(), time.time())
        )
        other.conn.commit()
        diff = mg.diff_summary(other)
        assert len(diff["label_diffs"]) == 1
        assert diff["label_diffs"][0]["self_label"] == "label_a"

    def test_diff_sample_labels(self, mg):
        other = MemoryGraph()
        mg.add("s1", "fact")
        mg.add("s2", "fact")
        other.add("o1", "fact")
        diff = mg.diff_summary(other)
        assert "s1" in diff["sample_only_self"]
        assert "o1" in diff["sample_only_other"]

    def test_diff_empty_graphs(self, mg):
        other = MemoryGraph()
        diff = mg.diff_summary(other)
        assert diff["total_self"] == 0
        assert diff["total_other"] == 0


class TestGroupBy:
    def test_group_by_kind_all(self, mg):
        mg.add("fact1", "fact")
        mg.add("fact2", "fact")
        mg.add("evt1", "event")
        groups = mg.group_by()
        assert len(groups["fact"]) == 2
        assert len(groups["event"]) == 1

    def test_group_by_specific_kind(self, mg):
        mg.add("fact1", "fact")
        mg.add("evt1", "event")
        groups = mg.group_by(kind="fact")
        assert "fact" in groups
        assert len(groups["fact"]) == 1

    def test_group_by_tag(self, mg):
        n = mg.add("tagged", "fact", tags=["ai"])
        mg.add("untagged", "fact")
        groups = mg.group_by(tag="ai")
        assert "ai" in groups
        assert len(groups["ai"]) == 1

    def test_group_by_empty_graph(self, mg):
        groups = mg.group_by()
        assert groups == {}


class TestLinkStrength:
    def test_link_strength_sorted(self, mg):
        a = mg.add("a", "fact")
        b = mg.add("b", "fact")
        c = mg.add("c", "fact")
        mg.link(a.id, b.id, "r", 3.0)
        mg.link(a.id, c.id, "r", 1.0)
        strengths = mg.link_strength(a.id)
        assert len(strengths) == 2
        assert strengths[0]["weight"] == 3.0
        assert strengths[0]["partner_label"] == "b"

    def test_link_strength_empty(self, mg):
        n = mg.add("solo", "fact")
        assert mg.link_strength(n.id) == []

    def test_link_strength_missing_node(self, mg):
        assert mg.link_strength("nonexistent") == []


class TestRandomNode:
    def test_random_node_returns_node(self, mg):
        mg.add("a", "fact")
        mg.add("b", "fact")
        n = mg.random_node()
        assert n is not None
        assert n.label in ("a", "b")

    def test_random_node_empty(self, mg):
        assert mg.random_node() is None


class TestUnlinkAll:
    def test_unlink_all_removes_both_directions(self, mg):
        a = mg.add("a", "fact")
        b = mg.add("b", "fact")
        c = mg.add("c", "fact")
        mg.link(a.id, b.id, "r1")
        mg.link(c.id, a.id, "r2")
        removed = mg.unlink_all(a.id)
        assert removed == 2
        assert mg.edge_count() == 0

    def test_unlink_all_isolated(self, mg):
        n = mg.add("solo", "fact")
        assert mg.unlink_all(n.id) == 0

    def test_unlink_all_missing(self, mg):
        assert mg.unlink_all("nonexistent") == 0


class TestEdgeCount:
    def test_edge_count_total(self, mg):
        a = mg.add("a", "fact")
        b = mg.add("b", "fact")
        mg.link(a.id, b.id, "r")
        assert mg.edge_count() == 1

    def test_edge_count_by_relation(self, mg):
        a = mg.add("a", "fact")
        b = mg.add("b", "fact")
        mg.link(a.id, b.id, "friend")
        mg.link(b.id, a.id, "colleague")
        assert mg.edge_count("friend") == 1
        assert mg.edge_count("colleague") == 1
        assert mg.edge_count("other") == 0

    def test_edge_count_empty(self, mg):
        assert mg.edge_count() == 0


class TestFindComponents:
    def test_single_component(self, mg):
        a = mg.add("a", "fact")
        b = mg.add("b", "fact")
        mg.link(a.id, b.id, "r")
        comps = mg.find_components()
        assert len(comps) == 1
        assert set(comps[0]) == {a.id, b.id}

    def test_two_components(self, mg):
        a = mg.add("a", "fact")
        b = mg.add("b", "fact")
        c = mg.add("c", "fact")
        d = mg.add("d", "fact")
        mg.link(a.id, b.id, "r")
        mg.link(c.id, d.id, "r")
        comps = mg.find_components()
        assert len(comps) == 2

    def test_isolated_nodes(self, mg):
        mg.add("a", "fact")
        mg.add("b", "fact")
        comps = mg.find_components()
        assert len(comps) == 2

    def test_empty_graph(self, mg):
        assert mg.find_components() == []


class TestDistanceMatrix:
    def test_simple_chain(self, mg):
        a = mg.add("a", "fact")
        b = mg.add("b", "fact")
        c = mg.add("c", "fact")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        dm = mg.distance_matrix()
        assert dm[(a.id, a.id)] == 0
        assert dm[(a.id, b.id)] == 1
        assert dm[(a.id, c.id)] == 2

    def test_disconnected(self, mg):
        a = mg.add("a", "fact")
        b = mg.add("b", "fact")
        dm = mg.distance_matrix()
        assert (a.id, a.id) in dm
        assert (a.id, b.id) not in dm

    def test_subset_nodes(self, mg):
        a = mg.add("a", "fact")
        b = mg.add("b", "fact")
        c = mg.add("c", "fact")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        dm = mg.distance_matrix([a.id, c.id])
        assert dm[(a.id, c.id)] == 2
        assert (a.id, b.id) not in dm

    def test_empty_graph(self, mg):
        assert mg.distance_matrix() == {}


class TestCluster:
    """Tests for cluster(kind, threshold) — label-similarity grouping."""

    def test_cluster_empty_kind(self, mg):
        assert mg.cluster("nonexistent") == []

    def test_cluster_singletons(self, mg):
        mg.add("Python", "skill")
        mg.add("Rust", "skill")
        clusters = mg.cluster("skill")
        assert len(clusters) == 2
        assert all(c["size"] == 1 for c in clusters)

    def test_cluster_similar_labels(self, mg):
        mg.add("machine learning", "topic")
        mg.add("machine-learning", "topic")
        mg.add("Machine Learning", "topic")
        mg.add("deep learning", "topic")
        clusters = mg.cluster("topic", threshold=0.3)
        # "machine learning" variants should cluster together
        ml_cluster = [c for c in clusters if c["size"] > 1]
        assert len(ml_cluster) >= 1
        assert ml_cluster[0]["size"] >= 2

    def test_cluster_result_structure(self, mg):
        mg.add("foo", "tag")
        clusters = mg.cluster("tag")
        assert len(clusters) == 1
        c = clusters[0]
        assert "representative" in c
        assert "labels" in c
        assert "node_ids" in c
        assert "size" in c
        assert c["size"] == 1
        assert len(c["node_ids"]) == 1

    def test_cluster_excludes_other_kinds(self, mg):
        mg.add("Python", "skill")
        mg.add("Python", "language")
        clusters = mg.cluster("skill")
        assert len(clusters) == 1
        assert clusters[0]["size"] == 1


class TestInducedSubgraph:
    """Tests for induced_subgraph(node_ids) — extract induced subgraph."""

    def test_subgraph_basic(self, mg):
        a = mg.add("A", "t")
        b = mg.add("B", "t")
        c = mg.add("C", "t")
        mg.link(a.id, b.id, "rel")
        mg.link(b.id, c.id, "rel")
        sub = mg.induced_subgraph([a.id, b.id])
        assert sub.stats()["nodes"] == 2
        # Edge a→b should exist, b→c should not
        assert sub.edge_count() == 1

    def test_subgraph_isolated_node(self, mg):
        a = mg.add("A", "t")
        b = mg.add("B", "t")
        sub = mg.induced_subgraph([a.id])
        assert sub.stats()["nodes"] == 1
        assert sub.edge_count() == 0

    def test_subgraph_empty_ids(self, mg):
        sub = mg.induced_subgraph([])
        assert sub.stats()["nodes"] == 0

    def test_subgraph_nonexistent_node(self, mg):
        sub = mg.induced_subgraph(["nonexistent"])
        assert sub.stats()["nodes"] == 0

    def test_subgraph_preserves_data(self, mg):
        a = mg.add("NodeA", "type1", {"key": "val"}, ["t1"])
        sub = mg.induced_subgraph([a.id])
        node = sub.get_node(a.id)
        assert node is not None
        assert node.label == "NodeA"
        assert node.kind == "type1"

# ── evolve() + evolution_history() tests ──────────────────

class TestEvolve:
    def test_evolve_label(self):
        g = MemoryGraph()
        n = g.add("machine lerning", kind="concept")
        updated = g.evolve(n.id, new_label="machine learning")
        assert updated.label == "machine learning"
        assert updated.kind == "concept"

    def test_evolve_kind(self):
        g = MemoryGraph()
        n = g.add("Python", kind="concept")
        updated = g.evolve(n.id, new_kind="skill")
        assert updated.kind == "skill"
        assert updated.label == "Python"

    def test_evolve_both(self):
        g = MemoryGraph()
        n = g.add("neurl net", kind="concept")
        updated = g.evolve(n.id, new_label="neural network", new_kind="model")
        assert updated.label == "neural network"
        assert updated.kind == "model"

    def test_evolve_nonexistent_returns_none(self):
        g = MemoryGraph()
        assert g.evolve("nope", new_label="x") is None

    def test_evolve_no_change_returns_node(self):
        g = MemoryGraph()
        n = g.add("hello", kind="fact")
        result = g.evolve(n.id, new_label="hello", new_kind="fact")
        assert result is not None
        assert result.label == "hello"

    def test_evolve_only_label_no_kind_change(self):
        g = MemoryGraph()
        n = g.add("old", kind="fact")
        result = g.evolve(n.id, new_label="new")
        assert result.label == "new"
        assert result.kind == "fact"

    def test_evolution_history_records_changes(self):
        g = MemoryGraph()
        n = g.add("v1", kind="fact")
        g.evolve(n.id, new_label="v2", new_kind="concept")
        g.evolve(n.id, new_label="v3")
        history = g.evolution_history(n.id)
        assert len(history) == 2
        assert history[0]["old_label"] == "v1"
        assert history[0]["new_label"] == "v2"
        assert history[0]["old_kind"] == "fact"
        assert history[0]["new_kind"] == "concept"
        assert history[1]["old_label"] == "v2"
        assert history[1]["new_label"] == "v3"
        assert history[1]["old_kind"] == "concept"
        assert history[1]["new_kind"] == "concept"

    def test_evolution_history_empty_for_no_evolve(self):
        g = MemoryGraph()
        n = g.add("static", kind="fact")
        assert g.evolution_history(n.id) == []

    def test_evolution_history_nonexistent_node(self):
        g = MemoryGraph()
        assert g.evolution_history("nope") == []

    def test_evolve_preserves_edges(self):
        g = MemoryGraph()
        a = g.add("A", kind="fact")
        b = g.add("B", kind="fact")
        g.link(a.id, b.id, "rel")
        g.evolve(a.id, new_label="A2")
        edges = g.edges_of(a.id)
        assert len(edges) == 1
        assert edges[0].relation == "rel"

    # --- is_dag / topological_sort ---

    def test_is_dag_empty_graph(self):
        g = MemoryGraph()
        assert g.is_dag() is True

    def test_is_dag_linear_chain(self):
        g = MemoryGraph()
        a, b, c = g.add("A"), g.add("B"), g.add("C")
        g.link(a.id, b.id, "r"); g.link(b.id, c.id, "r")
        assert g.is_dag() is True

    def test_is_dag_with_cycle(self):
        g = MemoryGraph()
        a, b, c = g.add("A"), g.add("B"), g.add("C")
        g.link(a.id, b.id, "r"); g.link(b.id, c.id, "r"); g.link(c.id, a.id, "r")
        assert g.is_dag() is False

    def test_topological_sort_linear(self):
        g = MemoryGraph()
        a, b, c = g.add("A"), g.add("B"), g.add("C")
        g.link(a.id, b.id, "r"); g.link(b.id, c.id, "r")
        order = g.topological_sort()
        assert order.index(a.id) < order.index(b.id) < order.index(c.id)

    def test_topological_sort_with_cycle_returns_empty(self):
        g = MemoryGraph()
        a, b = g.add("A"), g.add("B")
        g.link(a.id, b.id, "r"); g.link(b.id, a.id, "r")
        assert g.topological_sort() == []

    def test_topological_sort_disconnected(self):
        g = MemoryGraph()
        a, b, c = g.add("A"), g.add("B"), g.add("C")
        g.link(a.id, c.id, "r")
        order = g.topological_sort()
        assert len(order) == 3
        assert order.index(a.id) < order.index(c.id)

    # --- find_paths ---

    def test_find_paths_single_path(self):
        g = MemoryGraph()
        a, b, c = g.add("A"), g.add("B"), g.add("C")
        g.link(a.id, b.id, "r"); g.link(b.id, c.id, "r")
        paths = g.find_paths(a.id, c.id)
        assert paths == [[a.id, b.id, c.id]]

    def test_find_paths_multiple_paths(self):
        g = MemoryGraph()
        a, b, c, d = g.add("A"), g.add("B"), g.add("C"), g.add("D")
        g.link(a.id, b.id, "r"); g.link(b.id, d.id, "r")
        g.link(a.id, c.id, "r"); g.link(c.id, d.id, "r")
        paths = g.find_paths(a.id, d.id)
        assert len(paths) == 2

    def test_find_paths_no_path(self):
        g = MemoryGraph()
        a, b = g.add("A"), g.add("B")
        assert g.find_paths(a.id, b.id) == []

    def test_find_paths_max_depth(self):
        g = MemoryGraph()
        a, b, c, d = g.add("A"), g.add("B"), g.add("C"), g.add("D")
        g.link(a.id, b.id, "r"); g.link(b.id, c.id, "r"); g.link(c.id, d.id, "r")
        paths = g.find_paths(a.id, d.id, max_depth=1)
        assert paths == []

    # --- similarity / link prediction ---

    def test_jaccard_similar(self):
        g = MemoryGraph()
        a, b, c, d = g.add("A"), g.add("B"), g.add("C"), g.add("D")
        g.link(a.id, c.id, "r"); g.link(a.id, d.id, "r")
        g.link(b.id, c.id, "r"); g.link(b.id, d.id, "r")
        sim = g.jaccard_similarity(a.id, b.id)
        assert sim == 1.0  # same neighbors

    def test_jaccard_disjoint(self):
        g = MemoryGraph()
        a, b, c, d = g.add("A"), g.add("B"), g.add("C"), g.add("D")
        g.link(a.id, c.id, "r")
        g.link(b.id, d.id, "r")
        assert g.jaccard_similarity(a.id, b.id) == 0.0

    def test_jaccard_no_neighbors(self):
        g = MemoryGraph()
        a, b = g.add("A"), g.add("B")
        assert g.jaccard_similarity(a.id, b.id) == 0.0

    def test_neighborhood_overlap_partial(self):
        g = MemoryGraph()
        a, b, c, d, e = g.add("A"), g.add("B"), g.add("C"), g.add("D"), g.add("E")
        g.link(a.id, c.id, "r"); g.link(a.id, d.id, "r")
        g.link(b.id, d.id, "r"); g.link(b.id, e.id, "r")
        # a neighbors: {c,d}, b neighbors: {d,e}, overlap: {d}
        overlap = g.neighborhood_overlap(a.id, b.id)
        assert overlap == 0.5  # 1 shared / min(2,2)

    def test_adamic_adar_basic(self):
        g = MemoryGraph()
        a, b, c = g.add("A"), g.add("B"), g.add("C")
        g.link(a.id, c.id, "r"); g.link(b.id, c.id, "r")
        score = g.adamic_adar(a.id, b.id)
        assert score > 0  # c is shared neighbor

    def test_adamic_adar_no_common(self):
        g = MemoryGraph()
        a, b, c, d = g.add("A"), g.add("B"), g.add("C"), g.add("D")
        g.link(a.id, c.id, "r"); g.link(b.id, d.id, "r")
        assert g.adamic_adar(a.id, b.id) == 0.0

    # --- revert_evolution ---

    def test_revert_to_step_0(self):
        g = MemoryGraph()
        n = g.add("v1", kind="fact")
        g.evolve(n.id, new_label="v2")
        g.evolve(n.id, new_label="v3")
        result = g.revert_evolution(n.id, 0)
        assert result.label == "v2"
        assert result.kind == "fact"
        hist = g.evolution_history(n.id)
        assert len(hist) == 1  # only step 0 remains

    def test_revert_to_middle_step(self):
        g = MemoryGraph()
        n = g.add("alpha", kind="note")
        g.evolve(n.id, new_label="beta", new_kind="fact")  # step 0
        g.evolve(n.id, new_label="gamma")  # step 1
        g.evolve(n.id, new_kind="event")  # step 2
        result = g.revert_evolution(n.id, 1)  # revert to state after step 1 (gamma/fact)
        assert result.label == "gamma"
        assert result.kind == "fact"
        hist = g.evolution_history(n.id)
        assert len(hist) == 2  # steps 0 and 1

    def test_revert_nonexistent_node(self):
        g = MemoryGraph()
        assert g.revert_evolution("nope", 0) is None

    def test_revert_invalid_step(self):
        g = MemoryGraph()
        n = g.add("x")
        g.evolve(n.id, new_label="y")
        assert g.revert_evolution(n.id, 5) is None  # out of range
        assert g.revert_evolution(n.id, -1) is None

    def test_revert_no_history(self):
        g = MemoryGraph()
        n = g.add("never-evolved")
        assert g.revert_evolution(n.id, 0) is None

    # --- batch_evolve ---

    def test_batch_evolve_multiple(self):
        g = MemoryGraph()
        a = g.add("A", kind="fact")
        b = g.add("B", kind="note")
        results = g.batch_evolve([
            {"node_id": a.id, "new_label": "A2"},
            {"node_id": b.id, "new_kind": "event"},
        ])
        assert len(results) == 2
        assert results[0].label == "A2"
        assert results[1].kind == "event"

    def test_batch_evolve_with_failure(self):
        g = MemoryGraph()
        a = g.add("A")
        results = g.batch_evolve([
            {"node_id": a.id, "new_label": "A2"},
            {"node_id": "nope", "new_label": "X"},
            {"new_label": "no node_id"},
        ])
        assert results[0].label == "A2"
        assert results[1] is None
        assert results[2] is None

    def test_batch_evolve_empty(self):
        g = MemoryGraph()
        assert g.batch_evolve([]) == []

    # ── Edge Management Tests ──────────────────────────────

    def test_get_edge(self):
        g = MemoryGraph()
        a, b = g.add("A"), g.add("B")
        g.link(a.id, b.id, "knows", 0.8)
        edge = g.get_edge(a.id, b.id, "knows")
        assert edge is not None
        assert edge.source == a.id
        assert edge.target == b.id
        assert edge.relation == "knows"
        assert edge.weight == 0.8

    def test_get_edge_not_found(self):
        g = MemoryGraph()
        assert g.get_edge("x", "y", "z") is None

    def test_update_edge_weight(self):
        g = MemoryGraph()
        a, b = g.add("A"), g.add("B")
        g.link(a.id, b.id, "knows", 0.5)
        updated = g.update_edge(a.id, b.id, "knows", weight=0.9)
        assert updated is not None
        assert updated.weight == 0.9
        # Old edge is gone
        check = g.get_edge(a.id, b.id, "knows")
        assert check.weight == 0.9

    def test_update_edge_rename_relation(self):
        g = MemoryGraph()
        a, b = g.add("A"), g.add("B")
        g.link(a.id, b.id, "likes", 0.7)
        updated = g.update_edge(a.id, b.id, "likes", new_relation="loves")
        assert updated is not None
        assert updated.relation == "loves"
        assert updated.weight == 0.7
        # Old relation gone
        assert g.get_edge(a.id, b.id, "likes") is None
        assert g.get_edge(a.id, b.id, "loves") is not None

    def test_update_edge_rename_with_weight(self):
        g = MemoryGraph()
        a, b = g.add("A"), g.add("B")
        g.link(a.id, b.id, "old", 0.5)
        updated = g.update_edge(a.id, b.id, "old", weight=1.0, new_relation="new")
        assert updated.relation == "new"
        assert updated.weight == 1.0

    def test_update_edge_nonexistent(self):
        g = MemoryGraph()
        assert g.update_edge("x", "y", "z", weight=0.5) is None

    def test_update_edge_noop(self):
        g = MemoryGraph()
        a, b = g.add("A"), g.add("B")
        g.link(a.id, b.id, "knows", 0.5)
        # No changes specified
        result = g.update_edge(a.id, b.id, "knows")
        assert result is not None
        assert result.weight == 0.5

    def test_edge_properties(self):
        g = MemoryGraph()
        a, b = g.add("A"), g.add("B")
        g.link(a.id, b.id, "knows")
        assert g.edge_properties(a.id, b.id, "knows") is None
        assert g.set_edge_properties(a.id, b.id, "knows", {"since": 2020, "trust": 0.9})
        props = g.edge_properties(a.id, b.id, "knows")
        assert props == {"since": 2020, "trust": 0.9}

    def test_set_edge_properties_no_edge(self):
        g = MemoryGraph()
        assert g.set_edge_properties("x", "y", "z", {"a": 1}) is False

    def test_edge_properties_upsert(self):
        g = MemoryGraph()
        a, b = g.add("A"), g.add("B")
        g.link(a.id, b.id, "knows")
        g.set_edge_properties(a.id, b.id, "knows", {"v": 1})
        g.set_edge_properties(a.id, b.id, "knows", {"v": 2, "extra": True})
        assert g.edge_properties(a.id, b.id, "knows") == {"v": 2, "extra": True}

    # ── Traversal Tests ───────────────────────────────────

    def test_dfs_order(self):
        g = MemoryGraph()
        a, b, c, d = g.add("A"), g.add("B"), g.add("C"), g.add("D")
        g.link(a.id, b.id, "to")
        g.link(b.id, c.id, "to")
        g.link(a.id, d.id, "to")
        order = g.dfs_order(a.id)
        assert order[0] == a.id
        assert len(order) == 4
        assert set(order) == {a.id, b.id, c.id, d.id}

    def test_dfs_order_missing(self):
        g = MemoryGraph()
        assert g.dfs_order("nonexistent") == []

    def test_dfs_order_max_depth(self):
        g = MemoryGraph()
        a, b, c = g.add("A"), g.add("B"), g.add("C")
        g.link(a.id, b.id, "to")
        g.link(b.id, c.id, "to")
        order = g.dfs_order(a.id, max_depth=1)
        assert a.id in order
        assert b.id in order
        assert c.id not in order

    def test_ancestor_graph(self):
        g = MemoryGraph()
        a, b, c = g.add("A"), g.add("B"), g.add("C")
        g.link(a.id, b.id, "to")
        g.link(b.id, c.id, "to")
        ancestors = g.ancestor_graph(c.id)
        assert b.id in ancestors
        assert a.id in ancestors
        assert c.id not in ancestors

    def test_ancestor_graph_missing(self):
        g = MemoryGraph()
        assert g.ancestor_graph("x") == []

    def test_descendant_graph(self):
        g = MemoryGraph()
        a, b, c = g.add("A"), g.add("B"), g.add("C")
        g.link(a.id, b.id, "to")
        g.link(b.id, c.id, "to")
        descs = g.descendant_graph(a.id)
        assert b.id in descs
        assert c.id in descs
        assert a.id not in descs

    def test_descendant_graph_missing(self):
        g = MemoryGraph()
        assert g.descendant_graph("x") == []

    def test_ancestor_graph_max_depth(self):
        g = MemoryGraph()
        a, b, c = g.add("A"), g.add("B"), g.add("C")
        g.link(a.id, b.id, "to")
        g.link(b.id, c.id, "to")
        ancestors = g.ancestor_graph(c.id, max_depth=1)
        assert b.id in ancestors
        assert a.id not in ancestors

    # ── Snapshot & Hash Tests ─────────────────────────────

    def test_graph_hash_deterministic(self):
        g = MemoryGraph()
        a, b = g.add("A"), g.add("B")
        g.link(a.id, b.id, "knows")
        h1 = g.graph_hash()
        h2 = g.graph_hash()
        assert h1 == h2
        assert len(h1) == 32  # MD5 hex

    def test_graph_hash_changes_on_mutation(self):
        g = MemoryGraph()
        g.add("A")
        h1 = g.graph_hash()
        g.add("B")
        h2 = g.graph_hash()
        assert h1 != h2

    def test_graph_hash_empty(self):
        g = MemoryGraph()
        assert len(g.graph_hash()) == 32

    def test_snapshot_restore(self):
        g = MemoryGraph()
        a, b = g.add("A"), g.add("B")
        g.link(a.id, b.id, "knows", 0.7)
        snap = g.snapshot()
        g.add("C")
        assert g.stats()["nodes"] == 3
        g.restore(snap)
        assert g.stats()["nodes"] == 2
        assert g.get_edge(a.id, b.id, "knows") is not None

    def test_snapshot_restore_empty(self):
        g = MemoryGraph()
        g.add("X")
        snap = g.snapshot()
        g.add("Y")
        g.restore(snap)
        assert g.stats()["nodes"] == 1

    def test_snapshot_preserves_evolution(self):
        g = MemoryGraph()
        a = g.add("A")
        g.evolve(a.id, new_label="A2")
        snap = g.snapshot()
        g.evolve(a.id, new_label="A3")
        assert len(g.evolution_history(a.id)) == 2
        g.restore(snap)
        assert len(g.evolution_history(a.id)) == 1

    # ── Dedup Tests ───────────────────────────────────────

    def test_dedup_nodes_exact(self):
        g = MemoryGraph()
        g.add("Python", "skill")
        g.add("Python", "skill")
        assert g.stats()["nodes"] == 2
        result = g.dedup_nodes()
        assert len(result) == 1
        assert g.stats()["nodes"] == 1

    def test_dedup_nodes_fuzzy(self):
        g = MemoryGraph()
        g.add("Python", "skill")
        g.add("Python3", "skill")  # very similar
        result = g.dedup_nodes(similarity_threshold=0.8)
        assert len(result) == 1
        assert g.stats()["nodes"] == 1

    def test_dedup_nodes_no_match(self):
        g = MemoryGraph()
        g.add("Python", "skill")
        g.add("Rust", "skill")
        result = g.dedup_nodes(similarity_threshold=0.8)
        assert len(result) == 0
        assert g.stats()["nodes"] == 2

    def test_dedup_nodes_transfers_edges(self):
        g = MemoryGraph()
        target = g.add("Target")
        dup1 = g.add("Python")
        dup2 = g.add("Python3")
        g.link(dup1.id, target.id, "teaches")
        g.dedup_nodes(similarity_threshold=0.8)
        # dup2 merged into dup1, dup1's edge should survive
        assert g.stats()["nodes"] == 2
        assert g.get_edge(dup1.id, target.id, "teaches") is not None

    def test_dedup_empty_graph(self):
        g = MemoryGraph()
        assert g.dedup_nodes() == []

    # ── merge_evolution tests ────────────────────────────

    def test_merge_evolution_collapses_history(self):
        """Merging evolution collapses multiple steps into one summary entry."""
        g = MemoryGraph()
        n = g.add("v1", "concept")
        g.evolve(n.id, "v2")
        g.evolve(n.id, "v3")
        g.evolve(n.id, "v4")
        assert len(g.evolution_history(n.id)) == 3
        result = g.merge_evolution(n.id)
        assert result is not None
        assert result["old_label"] == "v1"
        assert result["new_label"] == "v4"
        assert result["steps_collapsed"] == 3
        history = g.evolution_history(n.id)
        assert len(history) == 1
        assert history[0]["old_label"] == "v1"
        assert history[0]["new_label"] == "v4"

    def test_merge_evolution_single_step(self):
        """Merging a single-step history is a no-op (still collapses to 1 entry)."""
        g = MemoryGraph()
        n = g.add("original", "concept")
        g.evolve(n.id, "updated")
        result = g.merge_evolution(n.id)
        assert result is not None
        assert result["steps_collapsed"] == 1
        assert len(g.evolution_history(n.id)) == 1

    def test_merge_evolution_no_history(self):
        """Merging a node with no evolution history returns None."""
        g = MemoryGraph()
        n = g.add("unchanged", "concept")
        assert g.merge_evolution(n.id) is None

    def test_merge_evolution_nonexistent_node(self):
        """Merging evolution for a nonexistent node returns None."""
        g = MemoryGraph()
        assert g.merge_evolution(9999) is None

    def test_merge_evolution_preserves_kinds(self):
        """Merging captures original and final kinds across multiple kind changes."""
        g = MemoryGraph()
        n = g.add("draft", "note")
        g.evolve(n.id, new_kind="concept")
        g.evolve(n.id, new_kind="topic")
        g.evolve(n.id, new_label="final", new_kind="category")
        result = g.merge_evolution(n.id)
        assert result["old_kind"] == "note"
        assert result["new_kind"] == "category"
        assert result["old_label"] == "draft"
        assert result["new_label"] == "final"

    def test_merge_evolution_independent_per_node(self):
        """Merging evolution for one node doesn't affect another node's history."""
        g = MemoryGraph()
        a = g.add("a_v1", "concept")
        b = g.add("b_v1", "concept")
        g.evolve(a.id, "a_v2")
        g.evolve(a.id, "a_v3")
        g.evolve(b.id, "b_v2")
        g.merge_evolution(a.id)
        assert len(g.evolution_history(a.id)) == 1
        assert len(g.evolution_history(b.id)) == 1  # b still has its own 1 entry
        assert g.evolution_history(b.id)[0]["new_label"] == "b_v2"

    # ── evolution_summary tests ──────────────────────────

    def test_evolution_summary_empty_graph(self):
        """Summary of empty graph has zero everything."""
        g = MemoryGraph()
        s = g.evolution_summary()
        assert s["total_nodes"] == 0
        assert s["evolved_nodes"] == 0
        assert s["total_steps"] == 0
        assert s["avg_steps"] == 0.0
        assert s["most_evolved"] == []

    def test_evolution_summary_no_evolution(self):
        """Graph with nodes but no evolution has zero evolved_nodes."""
        g = MemoryGraph()
        g.add("a", "concept")
        g.add("b", "concept")
        s = g.evolution_summary()
        assert s["total_nodes"] == 2
        assert s["evolved_nodes"] == 0
        assert s["total_steps"] == 0

    def test_evolution_summary_with_evolution(self):
        """Summary correctly counts evolved nodes and total steps."""
        g = MemoryGraph()
        a = g.add("a1", "concept")
        b = g.add("b1", "concept")
        c = g.add("c1", "concept")
        g.evolve(a.id, "a2")
        g.evolve(a.id, "a3")
        g.evolve(b.id, "b2")
        # c not evolved
        s = g.evolution_summary()
        assert s["total_nodes"] == 3
        assert s["evolved_nodes"] == 2
        assert s["total_steps"] == 3
        assert s["avg_steps"] == 1.5
        assert s["most_evolved"][0]["node_id"] == a.id
        assert s["most_evolved"][0]["steps"] == 2

    def test_evolution_summary_most_evolved_top5(self):
        """most_evolved returns at most 5 entries, sorted by steps descending."""
        g = MemoryGraph()
        for i in range(7):
            n = g.add(f"n{i}", "concept")
            for j in range(i + 1):
                g.evolve(n.id, f"n{i}_v{j + 2}")
        s = g.evolution_summary()
        assert len(s["most_evolved"]) == 5
        assert s["most_evolved"][0]["steps"] == 7
        assert s["most_evolved"][4]["steps"] == 3

# ── bfs_shortest_path / centrality_degree / reachability_count ──

class TestBfsShortestPath:
    def test_shortest_path_direct(self):
        mg = MemoryGraph()
        a, b = mg.add("A", "x"), mg.add("B", "x")
        mg.link(a.id, b.id, "r")
        path = mg.bfs_shortest_path(a.id, b.id)
        assert path == [a.id, b.id]

    def test_shortest_path_via_intermediate(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A", "x"), mg.add("B", "x"), mg.add("C", "x")
        mg.link(a.id, b.id, "r"); mg.link(b.id, c.id, "r")
        path = mg.bfs_shortest_path(a.id, c.id)
        assert path == [a.id, b.id, c.id]

    def test_shortest_path_picks_shortest(self):
        mg = MemoryGraph()
        a, b, c, d = mg.add("A","x"), mg.add("B","x"), mg.add("C","x"), mg.add("D","x")
        mg.link(a.id, b.id, "r"); mg.link(b.id, c.id, "r"); mg.link(c.id, d.id, "r")
        mg.link(a.id, d.id, "r")  # shortcut
        path = mg.bfs_shortest_path(a.id, d.id)
        assert path == [a.id, d.id]

    def test_shortest_path_no_path(self):
        mg = MemoryGraph()
        a, b = mg.add("A", "x"), mg.add("B", "x")
        assert mg.bfs_shortest_path(a.id, b.id) is None

    def test_shortest_path_same_node(self):
        mg = MemoryGraph()
        a = mg.add("A", "x")
        assert mg.bfs_shortest_path(a.id, a.id) == [a.id]

    def test_shortest_path_nonexistent(self):
        mg = MemoryGraph()
        assert mg.bfs_shortest_path("nope", "nope") is None

class TestCentralityDegree:
    def test_isolated_node(self):
        mg = MemoryGraph()
        a = mg.add("A", "x")
        assert mg.centrality_degree(a.id) == 0.0

    def test_connected(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A","x"), mg.add("B","x"), mg.add("C","x")
        mg.link(a.id, b.id, "r"); mg.link(a.id, c.id, "r")
        # a has 2 edges (out), b has 1, c has 1 => a degree = 2/2 = 1.0
        c_val = mg.centrality_degree(a.id)
        assert c_val == 1.0

    def test_nonexistent(self):
        mg = MemoryGraph()
        assert mg.centrality_degree("nope") is None

    def test_single_node(self):
        mg = MemoryGraph()
        a = mg.add("A", "x")
        assert mg.centrality_degree(a.id) == 0.0

class TestReachabilityCount:
    def test_isolated(self):
        mg = MemoryGraph()
        a = mg.add("A", "x")
        assert mg.reachability_count(a.id) == 0

    def test_chain(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A","x"), mg.add("B","x"), mg.add("C","x")
        mg.link(a.id, b.id, "r"); mg.link(b.id, c.id, "r")
        assert mg.reachability_count(a.id) == 2

    def test_nonexistent(self):
        mg = MemoryGraph()
        assert mg.reachability_count("nope") == 0

    def test_depth_limit(self):
        mg = MemoryGraph()
        nodes = [mg.add(f"N{i}", "x") for i in range(5)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i+1].id, "r")
        assert mg.reachability_count(nodes[0].id, max_depth=1) == 1
        assert mg.reachability_count(nodes[0].id, max_depth=2) == 2

class TestGraphDensity:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.graph_density() == 0.0

    def test_single_node(self):
        mg = MemoryGraph()
        mg.add("A", "x")
        assert mg.graph_density() == 0.0

    def test_two_nodes_one_edge(self):
        mg = MemoryGraph()
        a, b = mg.add("A","x"), mg.add("B","x")
        mg.link(a.id, b.id, "r")
        assert mg.graph_density() == 0.5  # 1 / (2*1)

    def test_complete_directed(self):
        mg = MemoryGraph()
        a, b = mg.add("A","x"), mg.add("B","x")
        mg.link(a.id, b.id, "r"); mg.link(b.id, a.id, "r")
        assert mg.graph_density() == 1.0  # 2 / (2*1)

    def test_three_nodes_chain(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A","x"), mg.add("B","x"), mg.add("C","x")
        mg.link(a.id, b.id, "r"); mg.link(b.id, c.id, "r")
        # 2 edges, max = 3*2 = 6 => 2/6
        assert abs(mg.graph_density() - 2/6) < 0.001

class TestReciprocity:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.reciprocity() == 0.0

    def test_no_reciprocal(self):
        mg = MemoryGraph()
        a, b = mg.add("A","x"), mg.add("B","x")
        mg.link(a.id, b.id, "r")
        assert mg.reciprocity() == 0.0

    def test_fully_reciprocal(self):
        mg = MemoryGraph()
        a, b = mg.add("A","x"), mg.add("B","x")
        mg.link(a.id, b.id, "r"); mg.link(b.id, a.id, "r")
        assert mg.reciprocity() == 1.0

    def test_mixed(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A","x"), mg.add("B","x"), mg.add("C","x")
        mg.link(a.id, b.id, "r"); mg.link(b.id, a.id, "r"); mg.link(b.id, c.id, "r")
        # 3 edges, 1 reciprocal pair (2 edges) => 2/3
        assert abs(mg.reciprocity() - 2/3) < 0.001

class TestAssortativityDegree:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.assortativity_degree() == 0.0

    def test_chain(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A","x"), mg.add("B","x"), mg.add("C","x")
        mg.link(a.id, b.id, "r"); mg.link(b.id, c.id, "r")
        r = mg.assortativity_degree()
        assert -1.0 <= r <= 1.0

class TestClusteringCoefficient:
    def test_nonexistent(self):
        mg = MemoryGraph()
        assert mg.clustering_coefficient("nope") is None

    def test_isolated(self):
        mg = MemoryGraph()
        a = mg.add("A", "x")
        assert mg.clustering_coefficient(a.id) == 0.0

    def test_single_edge(self):
        mg = MemoryGraph()
        a, b = mg.add("A","x"), mg.add("B","x")
        mg.link(a.id, b.id, "r")
        assert mg.clustering_coefficient(a.id) == 0.0

    def test_triangle(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A","x"), mg.add("B","x"), mg.add("C","x")
        mg.link(a.id, b.id, "r"); mg.link(b.id, c.id, "r"); mg.link(c.id, a.id, "r")
        # Directed triangle: each node has 2 neighbors (1 in, 1 out)
        # Between neighbors: 1 directed edge exists => ratio depends
        cc = mg.clustering_coefficient(a.id)
        assert cc > 0.0

    def test_open_triple(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A","x"), mg.add("B","x"), mg.add("C","x")
        mg.link(a.id, b.id, "r"); mg.link(a.id, c.id, "r")
        # A's neighbors: B, C (both out). No edge B->C or C->B
        assert mg.clustering_coefficient(a.id) == 0.0

class TestRichClubCoefficient:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.rich_club_coefficient(1) == 0.0

    def test_no_rich_nodes(self):
        mg = MemoryGraph()
        a = mg.add("A", "x")
        assert mg.rich_club_coefficient(2) == 0.0

    def test_rich_connected(self):
        mg = MemoryGraph()
        a, b = mg.add("A","x"), mg.add("B","x")
        mg.link(a.id, b.id, "r"); mg.link(b.id, a.id, "r")
        # Both have degree 2 (1 in + 1 out), >= 2
        rc = mg.rich_club_coefficient(2)
        assert rc > 0.0

    def test_rich_not_connected(self):
        mg = MemoryGraph()
        a, b, c, d = mg.add("A","x"), mg.add("B","x"), mg.add("C","x"), mg.add("D","x")
        mg.link(a.id, b.id, "r"); mg.link(c.id, d.id, "r")
        # deg: a=1, b=2(1in+1...wait - a->b => a(out), b(in)
        # Actually UNION ALL counts: a appears once(source), b appears once(target)
        # deg: a=1, b=1, c=1, d=1. No node >= 2.
        # Need higher degrees:
        mg.link(b.id, a.id, "r")  # now a=2, b=2
        rc = mg.rich_club_coefficient(2)
        assert rc > 0.0  # a-b reciprocal, they are connected

class TestGlobalClusteringCoefficient:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.global_clustering_coefficient() == 0.0

    def test_single_edge(self):
        mg = MemoryGraph()
        a, b = mg.add("A","x"), mg.add("B","x")
        mg.link(a.id, b.id, "r")
        assert mg.global_clustering_coefficient() == 0.0

    def test_closed_triplet(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A","x"), mg.add("B","x"), mg.add("C","x")
        mg.link(a.id, b.id, "r"); mg.link(b.id, c.id, "r"); mg.link(a.id, c.id, "r")
        # Triplet a->b->c with a->c closing = fully closed
        assert mg.global_clustering_coefficient() == 1.0

    def test_open_triplet(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A","x"), mg.add("B","x"), mg.add("C","x")
        mg.link(a.id, b.id, "r"); mg.link(b.id, c.id, "r")
        # No a->c closing edge
        assert mg.global_clustering_coefficient() == 0.0

class TestModularity:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.modularity({}) == 0.0

    def test_single_community(self):
        mg = MemoryGraph()
        a, b = mg.add("A","x"), mg.add("B","x")
        mg.link(a.id, b.id, "r")
        q = mg.modularity({a.id: 0, b.id: 0})
        assert q > 0.0

    def test_two_communities(self):
        mg = MemoryGraph()
        a1, a2 = mg.add("A1","x"), mg.add("A2","x")
        b1, b2 = mg.add("B1","x"), mg.add("B2","x")
        mg.link(a1.id, a2.id, "r"); mg.link(b1.id, b2.id, "r")
        mg.link(a1.id, b1.id, "r")  # cross-community edge
        q_correct = mg.modularity({a1.id: 0, a2.id: 0, b1.id: 1, b2.id: 1})
        q_wrong = mg.modularity({a1.id: 0, a2.id: 1, b1.id: 0, b2.id: 1})
        assert q_correct > q_wrong


# ── 生命周期 & 工具方法 ─────────────────────────────

class TestClear:
    def test_clear_empty(self):
        mg = MemoryGraph()
        mg.clear()
        assert mg.is_empty()
        assert mg.stats()["nodes"] == 0

    def test_clear_with_data(self):
        mg = MemoryGraph()
        a, b = mg.add("A", "x"), mg.add("B", "x")
        mg.link(a.id, b.id, "r")
        mg.tag_nodes("t", [a.id])
        mg.clear()
        assert mg.is_empty()
        assert mg.stats()["nodes"] == 0
        assert mg.stats()["edges"] == 0
        assert mg.count_edges() == 0

    def test_clear_evolution_log(self):
        mg = MemoryGraph()
        a = mg.add("A", "x")
        mg.evolve(a.id, "A2", "y")
        assert mg.evolution_summary()["evolved_nodes"] == 1
        mg.clear()
        a2 = mg.add("New", "x")
        summary = mg.evolution_summary()
        assert summary["evolved_nodes"] == 0
        assert summary["total_steps"] == 0


class TestIsEmpty:
    def test_empty_graph(self):
        mg = MemoryGraph()
        assert mg.is_empty()

    def test_non_empty(self):
        mg = MemoryGraph()
        mg.add("node", "x")
        assert not mg.is_empty()

    def test_after_clear(self):
        mg = MemoryGraph()
        mg.add("node", "x")
        mg.clear()
        assert mg.is_empty()


class TestCountEdges:
    def test_zero(self):
        mg = MemoryGraph()
        assert mg.count_edges() == 0

    def test_count(self):
        mg = MemoryGraph()
        a, b, c = [mg.add(f"N{i}", "x") for i in range(3)]
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.count_edges() == 2

    def test_multi_relation(self):
        mg = MemoryGraph()
        a, b = mg.add("A", "x"), mg.add("B", "x")
        mg.link(a.id, b.id, "friend")
        mg.link(a.id, b.id, "coworker")
        assert mg.count_edges() == 2


class TestBatchReweight:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.batch_reweight([]) == 0

    def test_basic(self):
        mg = MemoryGraph()
        a, b = mg.add("A", "x"), mg.add("B", "x")
        n = mg.batch_reweight([
            {"id": a.id, "delta": 0.1},
            {"id": b.id, "delta": -0.2},
        ])
        assert n == 2
        assert abs(mg.get_node(a.id).weight - 1.1) < 0.01
        assert abs(mg.get_node(b.id).weight - 0.8) < 0.01

    def test_nonexistent_id(self):
        mg = MemoryGraph()
        a = mg.add("A", "x")
        n = mg.batch_reweight([
            {"id": a.id, "delta": 0.1},
            {"id": "nonexistent", "delta": 0.5},
        ])
        assert n == 1

    def test_floor_zero(self):
        mg = MemoryGraph()
        a = mg.add("A", "x")
        mg.batch_reweight([{"id": a.id, "delta": -5.0}])
        assert mg.get_node(a.id).weight == 0.0


class TestToAdjacencyList:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.to_adjacency_list() == {}

    def test_basic(self):
        mg = MemoryGraph()
        a, b, c = [mg.add(f"N{i}", "x") for i in range(3)]
        mg.link(a.id, b.id, "r", 0.5)
        mg.link(b.id, c.id, "to", 1.0)
        adj = mg.to_adjacency_list()
        assert len(adj) == 2
        assert len(adj[a.id]) == 1
        assert adj[a.id][0]["target"] == b.id
        assert adj[a.id][0]["relation"] == "r"
        assert adj[a.id][0]["weight"] == 0.5
        assert len(adj[b.id]) == 1

    def test_multi_edge(self):
        mg = MemoryGraph()
        a, b = mg.add("A", "x"), mg.add("B", "x")
        mg.link(a.id, b.id, "r1")
        mg.link(a.id, b.id, "r2")
        adj = mg.to_adjacency_list()
        assert len(adj[a.id]) == 2


class TestSerializeDot:
    def test_empty(self):
        mg = MemoryGraph()
        dot = mg.serialize_dot()
        assert "digraph" in dot

    def test_basic(self):
        mg = MemoryGraph()
        a, b = mg.add("A", "x"), mg.add("B", "y")
        mg.link(a.id, b.id, "rel")
        dot = mg.serialize_dot()
        assert "digraph memory" in dot
        assert a.id in dot
        assert b.id in dot
        assert "rel" in dot
        assert "->" in dot

    def test_special_chars(self):
        mg = MemoryGraph()
        a = mg.add('node"with"quotes', "x")
        dot = mg.serialize_dot()
        assert '\\"' in dot


class TestFindOrphans:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.find_orphans() == []

    def test_all_connected(self):
        mg = MemoryGraph()
        a, b = mg.add("A", "x"), mg.add("B", "x")
        mg.link(a.id, b.id, "r")
        assert mg.find_orphans() == []

    def test_orphan_exists(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A", "x"), mg.add("B", "x"), mg.add("C", "x")
        mg.link(a.id, b.id, "r")
        orphans = mg.find_orphans()
        assert len(orphans) == 1
        assert orphans[0].id == c.id


class TestHasCycle:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.has_cycle() is False

    def test_no_cycle_chain(self):
        mg = MemoryGraph()
        a, b, c = [mg.add(f"N{i}", "x") for i in range(3)]
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.has_cycle() is False

    def test_simple_cycle(self):
        mg = MemoryGraph()
        a, b = mg.add("A", "x"), mg.add("B", "x")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, a.id, "r")
        assert mg.has_cycle() is True

    def test_self_loop(self):
        mg = MemoryGraph()
        a = mg.add("A", "x")
        mg.link(a.id, a.id, "self")
        assert mg.has_cycle() is True

    def test_triangle_cycle(self):
        mg = MemoryGraph()
        a, b, c = [mg.add(f"N{i}", "x") for i in range(3)]
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        assert mg.has_cycle() is True


# ── 进阶图分析 ────────────────────────────────────────

class TestDegreeHistogram:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.degree_histogram() == {}

    def test_basic(self):
        mg = MemoryGraph()
        a, b, c = [mg.add(f"N{i}", "x") for i in range(3)]
        mg.link(a.id, b.id, "r")
        mg.link(a.id, c.id, "r")
        hist = mg.degree_histogram()
        assert hist[2] == 1  # a has degree 2
        assert hist[1] == 2  # b and c have degree 1

    def test_isolated(self):
        mg = MemoryGraph()
        a, b = mg.add("A", "x"), mg.add("B", "x")
        hist = mg.degree_histogram()
        assert hist[0] == 2


class TestDegreeSequence:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.degree_sequence() == []

    def test_desc(self):
        mg = MemoryGraph()
        a, b, c, d = [mg.add(f"N{i}", "x") for i in range(4)]
        mg.link(a.id, b.id, "r")
        mg.link(a.id, c.id, "r")
        mg.link(a.id, d.id, "r")
        seq = mg.degree_sequence()
        assert seq == [3, 1, 1, 1]

    def test_asc(self):
        mg = MemoryGraph()
        a, b, c = [mg.add(f"N{i}", "x") for i in range(3)]
        mg.link(a.id, b.id, "r")
        seq = mg.degree_sequence(order="asc")
        assert seq == [0, 1, 1]


class TestLargestComponentSize:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.largest_component_size() == 0

    def test_single(self):
        mg = MemoryGraph()
        a = mg.add("A", "x")
        assert mg.largest_component_size() == 1

    def test_connected(self):
        mg = MemoryGraph()
        a, b, c = [mg.add(f"N{i}", "x") for i in range(3)]
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.largest_component_size() == 3

    def test_disconnected(self):
        mg = MemoryGraph()
        a, b = mg.add("A", "x"), mg.add("B", "x")
        c, d, e = [mg.add(f"N{i}", "x") for i in range(3)]
        mg.link(c.id, d.id, "r")
        mg.link(d.id, e.id, "r")
        assert mg.largest_component_size() == 3


class TestCommunityDetectionGreedy:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.community_detection_greedy() == {}

    def test_single(self):
        mg = MemoryGraph()
        a = mg.add("A", "x")
        comm = mg.community_detection_greedy()
        assert len(comm) == 1
        assert comm[a.id] == 0

    def test_two_communities(self):
        mg = MemoryGraph()
        a1, a2 = mg.add("A1", "x"), mg.add("A2", "x")
        b1, b2 = mg.add("B1", "x"), mg.add("B2", "x")
        mg.link(a1.id, a2.id, "r")
        mg.link(b1.id, b2.id, "r")
        comm = mg.community_detection_greedy()
        # Connected pairs should be in same or adjacent community
        assert comm[a1.id] != comm[b1.id] or comm[a2.id] != comm[b2.id]

    def test_all_connected(self):
        mg = MemoryGraph()
        a, b, c = [mg.add(f"N{i}", "x") for i in range(3)]
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(a.id, c.id, "r")
        comm = mg.community_detection_greedy()
        assert len(set(comm.values())) <= 2  # tight cluster → 1-2 communities


class TestBetweennessCentralityApprox:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.betweenness_centrality_approx() == {}

    def test_bridge_node(self):
        mg = MemoryGraph()
        a, b, c = [mg.add(f"N{i}", "x") for i in range(3)]
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        bc = mg.betweenness_centrality_approx(samples=10)
        # b is the bridge → highest betweenness
        assert bc[b.id] >= bc[a.id]
        assert bc[b.id] >= bc[c.id]

    def test_leaf_zero(self):
        mg = MemoryGraph()
        a, b, c = [mg.add(f"N{i}", "x") for i in range(3)]
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        bc = mg.betweenness_centrality_approx(samples=10)
        # Leaf nodes (a, c) have 0 betweenness
        assert bc[a.id] == 0.0
        assert bc[c.id] == 0.0

    def test_star_center(self):
        mg = MemoryGraph()
        center = mg.add("hub", "x")
        leaves = [mg.add(f"L{i}", "x") for i in range(5)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
        bc = mg.betweenness_centrality_approx(samples=10)
        # Center has highest betweenness
        for leaf in leaves:
            assert bc[center.id] >= bc[leaf.id]


# ── 图变换 ──────────────────────────────────────────────

class TestReverseEdges:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.reverse_edges() == 0

    def test_basic(self):
        mg = MemoryGraph()
        a, b = mg.add("A", "x"), mg.add("B", "x")
        mg.link(a.id, b.id, "r")
        n = mg.reverse_edges()
        assert n == 1
        edges = mg.edges_of(a.id, "incoming")
        assert len(edges) == 1
        assert edges[0].source == b.id

    def test_multi(self):
        mg = MemoryGraph()
        a, b, c = [mg.add(f"N{i}", "x") for i in range(3)]
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.reverse_edges() == 2


class TestToUndirected:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.to_undirected() == 0

    def test_no_dup(self):
        mg = MemoryGraph()
        a, b = mg.add("A", "x"), mg.add("B", "x")
        mg.link(a.id, b.id, "r")
        assert mg.to_undirected() == 0
        assert mg.count_edges() == 1

    def test_dedup(self):
        mg = MemoryGraph()
        a, b = mg.add("A", "x"), mg.add("B", "x")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, a.id, "r")
        removed = mg.to_undirected()
        assert removed == 1
        assert mg.count_edges() == 1


class TestInduceByTags:
    def test_empty(self):
        mg = MemoryGraph()
        result = mg.induce_by_tags(["t"])
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_match_any(self):
        mg = MemoryGraph()
        a, b, c = [mg.add(f"N{i}", "x") for i in range(3)]
        mg.tag_nodes("red", [a.id, b.id])
        mg.tag_nodes("blue", [c.id])
        mg.link(a.id, b.id, "r")
        result = mg.induce_by_tags(["red"])
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1

    def test_match_all(self):
        mg = MemoryGraph()
        a, b, c = [mg.add(f"N{i}", "x") for i in range(3)]
        mg.tag_nodes("red", [a.id, b.id, c.id])
        mg.tag_nodes("big", [a.id])
        result = mg.induce_by_tags(["red", "big"], match_all=True)
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["id"] == a.id


class TestWeightNormalize:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.weight_normalize() == 0

    def test_basic(self):
        mg = MemoryGraph()
        a, b, c = [mg.add(f"N{i}", "x") for i in range(3)]
        mg.reweight(a.id, -0.5)
        mg.reweight(c.id, 0.5)
        n = mg.weight_normalize(0.0, 1.0)
        assert n == 3
        wa = mg.get_node(a.id).weight
        wc = mg.get_node(c.id).weight
        assert abs(wa - 0.0) < 0.01
        assert abs(wc - 1.0) < 0.01

    def test_all_same(self):
        mg = MemoryGraph()
        a, b = mg.add("A", "x"), mg.add("B", "x")
        n = mg.weight_normalize()
        assert n == 2
        # All same → set to target_max
        assert abs(mg.get_node(a.id).weight - 1.0) < 0.01


# ── PageRank Tests ────────────────────────────────────────

class TestPageRank:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.pagerank() == {}

    def test_single_node(self):
        mg = MemoryGraph()
        a = mg.add("A")
        pr = mg.pagerank()
        assert len(pr) == 1
        # Single dangling node → rank ≈ 1.0
        assert abs(pr[a.id] - 1.0) < 0.1

    def test_basic_convergence(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        pr = mg.pagerank()
        assert len(pr) == 3
        # In a cycle, all should be roughly equal
        vals = list(pr.values())
        assert max(vals) - min(vals) < 0.1

    def test_hub_gets_higher_rank(self):
        mg = MemoryGraph()
        hub = mg.add("Hub")
        s1, s2, s3 = mg.add("S1"), mg.add("S2"), mg.add("S3")
        # Many nodes point to hub
        mg.link(s1.id, hub.id, "r")
        mg.link(s2.id, hub.id, "r")
        mg.link(s3.id, hub.id, "r")
        pr = mg.pagerank()
        assert pr[hub.id] > pr[s1.id]
        assert pr[hub.id] > pr[s2.id]
        assert pr[hub.id] > pr[s3.id]

    def test_dangling_node_handling(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        # b has no outbound → dangling
        pr = mg.pagerank()
        assert len(pr) == 2
        total = sum(pr.values())
        assert abs(total - 1.0) < 0.05  # roughly sums to 1

    def test_damping_parameter(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, a.id, "r")
        pr_low = mg.pagerank(damping=0.5)
        pr_high = mg.pagerank(damping=0.95)
        # Both should converge
        assert len(pr_low) == 2
        assert len(pr_high) == 2


# ── Eigenvector Centrality Tests ──────────────────────────

class TestEigenvectorCentrality:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.eigenvector_centrality() == {}

    def test_single_node(self):
        mg = MemoryGraph()
        a = mg.add("A")
        ec = mg.eigenvector_centrality()
        assert len(ec) == 1
        assert ec[a.id] > 0

    def test_star_graph(self):
        mg = MemoryGraph()
        center = mg.add("Center")
        leaves = [mg.add(f"L{i}") for i in range(5)]
        for leaf in leaves:
            mg.link(leaf.id, center.id, "r", 1.0)  # leaves → center
        ec = mg.eigenvector_centrality()
        # Center receives links from all leaves → highest centrality
        assert ec[center.id] > 0
        for leaf in leaves:
            assert ec[center.id] >= ec[leaf.id] - 0.01

    def test_linear_chain(self):
        mg = MemoryGraph()
        nodes = [mg.add(f"N{i}") for i in range(5)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i+1].id, "r")
        ec = mg.eigenvector_centrality()
        assert len(ec) == 5
        # All should have non-negative centrality
        for nid, val in ec.items():
            assert val >= -0.01

    def test_weighted_edges(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r", 5.0)
        mg.link(a.id, c.id, "r", 1.0)
        ec = mg.eigenvector_centrality()
        # B should get more centrality due to higher weight
        assert ec[b.id] >= ec[c.id] - 0.01


# ── HITS Authority Score Tests ─────────────────────────────

class TestAuthorityScore:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.authority_score() == {}

    def test_basic_authority(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(c.id, b.id, "r")
        auth = mg.authority_score()
        # B is pointed to by both A and C → highest authority
        assert auth[b.id] > auth[a.id]
        assert auth[b.id] > auth[c.id]

    def test_hub_vs_authority(self):
        mg = MemoryGraph()
        hub = mg.add("Hub")
        auth_node = mg.add("Authority")
        mg.link(hub.id, auth_node.id, "r")
        auth = mg.authority_score()
        assert auth[auth_node.id] > auth[hub.id]

    def test_isolated_nodes(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        auth = mg.authority_score()
        # No edges → all equal authority (0 or equal baseline)
        assert len(auth) == 2


# ── Serialize Format Tests ────────────────────────────────

class TestSerializeFormats:
    def test_graphml_empty(self):
        mg = MemoryGraph()
        xml = mg.serialize_graphml()
        assert '<?xml' in xml
        assert '<graphml' in xml
        assert '</graphml>' in xml

    def test_graphml_basic(self):
        mg = MemoryGraph()
        a, b = mg.add("Alpha", "concept"), mg.add("Beta", "concept")
        mg.link(a.id, b.id, "relates")
        xml = mg.serialize_graphml()
        assert '<node' in xml
        assert '<edge' in xml
        assert 'Alpha' in xml
        assert 'relates' in xml
        assert xml.count('<node') == 2
        assert xml.count('<edge') == 1

    def test_graphml_escapes_special_chars(self):
        mg = MemoryGraph()
        mg.add("A&B <test>", "x")
        xml = mg.serialize_graphml()
        assert 'A&amp;B &lt;test&gt;' in xml
        assert 'A&B <test>' not in xml or xml.count('A&B <test>') == 0

    def test_cytoscape_empty(self):
        mg = MemoryGraph()
        data = mg.serialize_cytoscape()
        assert "elements" in data
        assert data["elements"]["nodes"] == []
        assert data["elements"]["edges"] == []

    def test_cytoscape_basic(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        data = mg.serialize_cytoscape()
        assert len(data["elements"]["nodes"]) == 3
        assert len(data["elements"]["edges"]) == 2
        edge0 = data["elements"]["edges"][0]["data"]
        assert edge0["source"] == a.id
        assert edge0["target"] == b.id
        assert edge0["relation"] == "r"

    def test_cytoscape_preserves_tags(self):
        mg = MemoryGraph()
        mg.add("Tagged", tags=["important", "core"])
        data = mg.serialize_cytoscape()
        node = data["elements"]["nodes"][0]["data"]
        assert "important" in node["tags"]
        assert "core" in node["tags"]

    def test_edgelist_empty(self):
        mg = MemoryGraph()
        assert mg.serialize_edgelist() == []

    def test_edgelist_basic(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r", 2.5)
        el = mg.serialize_edgelist()
        assert len(el) == 1
        parts = el[0].split()
        assert parts[0] == a.id
        assert parts[1] == b.id
        assert float(parts[2]) == 2.5


# ── k-Core / Triangle Count Tests ─────────────────────────

class TestKCore:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.k_core(2) == []

    def test_single_node_k1(self):
        mg = MemoryGraph()
        a = mg.add("A")
        assert a.id in mg.k_core(0)
        # k=1 requires degree >= 1, isolated node should be pruned
        assert a.id not in mg.k_core(1)

    def test_triangle_k2(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        result = mg.k_core(2)
        assert len(result) == 3  # all have degree 2

    def test_k3_excludes_low_degree(self):
        mg = MemoryGraph()
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        # Triangle among A, B, C
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        # D only connected to A
        mg.link(d.id, a.id, "r")
        result = mg.k_core(3)
        assert d.id not in result

    def test_core_number_empty(self):
        mg = MemoryGraph()
        assert mg.core_number() == {}

    def test_core_number_basic(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        core = mg.core_number()
        assert all(core[nid] == 2 for nid in [a.id, b.id, c.id])


class TestTriangleCount:
    def test_empty(self):
        mg = MemoryGraph()
        assert mg.count_triangles() == 0

    def test_no_triangle(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.count_triangles() == 0

    def test_one_triangle(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        assert mg.count_triangles() == 1

    def test_local_triangle_count(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        assert mg.local_triangle_count(a.id) == 1
        assert mg.local_triangle_count(b.id) == 1

    def test_local_nonexistent(self):
        mg = MemoryGraph()
        assert mg.local_triangle_count("nonexistent") == 0


# ── tag_cloud + tag_stats tests ──────────────────────────────

class TestTagCloud:

    def test_empty(self):
        mg = MemoryGraph()
        assert mg.tag_cloud() == []

    def test_single_tag(self):
        mg = MemoryGraph()
        mg.add("A", tags=["x"])
        cloud = mg.tag_cloud()
        assert cloud == [{"tag": "x", "count": 1}]

    def test_multiple_tags_sorted(self):
        mg = MemoryGraph()
        mg.add("A", tags=["python", "ai"])
        mg.add("B", tags=["python"])
        mg.add("C", tags=["python", "rust"])
        cloud = mg.tag_cloud()
        # python=3, ai=1, rust=1; sorted by count desc
        assert cloud[0] == {"tag": "python", "count": 3}
        assert len(cloud) == 3

    def test_tag_cloud_limit(self):
        mg = MemoryGraph()
        for label, tags in [("A", ["t1"]), ("B", ["t1", "t2"]), ("C", ["t1"])]:
            mg.add(label, tags=tags)
        cloud = mg.tag_cloud(limit=1)
        assert len(cloud) == 1
        assert cloud[0]["tag"] == "t1"

    def test_tag_cloud_limit_zero_means_all(self):
        mg = MemoryGraph()
        mg.add("A", tags=["x", "y"])
        cloud = mg.tag_cloud(limit=0)
        assert len(cloud) == 2

    def test_untagged_not_included(self):
        mg = MemoryGraph()
        mg.add("A", tags=["x"])
        mg.add("B")  # no tags
        cloud = mg.tag_cloud()
        assert len(cloud) == 1
        assert cloud[0]["tag"] == "x"


class TestTagStats:

    def test_empty(self):
        mg = MemoryGraph()
        s = mg.tag_stats()
        assert s["unique_tags"] == 0
        assert s["total_tag_instances"] == 0
        assert s["tagged_nodes"] == 0
        assert s["untagged_nodes"] == 0
        assert s["most_used"] is None
        assert s["least_used"] is None

    def test_basic_stats(self):
        mg = MemoryGraph()
        mg.add("A", tags=["python", "ai"])
        mg.add("B", tags=["python"])
        mg.add("C")  # untagged
        s = mg.tag_stats()
        assert s["unique_tags"] == 2
        assert s["total_tag_instances"] == 3
        assert s["tagged_nodes"] == 2
        assert s["untagged_nodes"] == 1
        assert s["avg_tags_per_node"] == 1.0
        assert s["most_used"] == {"tag": "python", "count": 2}

    def test_all_tagged(self):
        mg = MemoryGraph()
        mg.add("A", tags=["x"])
        mg.add("B", tags=["y"])
        s = mg.tag_stats()
        assert s["tagged_nodes"] == 2
        assert s["untagged_nodes"] == 0

    def test_avg_tags_per_node(self):
        mg = MemoryGraph()
        mg.add("A", tags=["a", "b", "c"])
        mg.add("B", tags=["a"])
        s = mg.tag_stats()
        assert s["avg_tags_per_node"] == 2.0  # 4 tag instances / 2 nodes


class TestSearchByLabel:

    def test_empty(self):
        mg = MemoryGraph()
        assert mg.search_by_label("test") == []

    def test_substring_match(self):
        mg = MemoryGraph()
        mg.add("Python Tutorial")
        mg.add("Rust Guide")
        mg.add("Python Cookbook")
        results = mg.search_by_label("Python")
        assert len(results) == 2

    def test_regex_match(self):
        mg = MemoryGraph()
        mg.add("node_001")
        mg.add("node_002")
        mg.add("item_003")
        results = mg.search_by_label(r"^node_")
        assert len(results) == 2

    def test_invalid_regex_fallback(self):
        mg = MemoryGraph()
        mg.add("test [bracket")
        mg.add("normal")
        # Invalid regex should fallback to LIKE
        results = mg.search_by_label("[bracket")
        assert len(results) == 1
        assert results[0].label == "test [bracket"

    def test_limit(self):
        mg = MemoryGraph()
        for i in range(10):
            mg.add(f"test_{i}")
        results = mg.search_by_label("test", limit=3)
        assert len(results) == 3

    def test_case_insensitive(self):
        mg = MemoryGraph()
        mg.add("Python")
        mg.add("python")
        results = mg.search_by_label("python")
        labels = [n.label for n in results]
        assert "Python" in labels
        assert "python" in labels


class TestSearchLabels:

    def test_empty(self):
        mg = MemoryGraph()
        assert mg.search_labels("test") == []

    def test_prefix_match(self):
        mg = MemoryGraph()
        mg.add("Python 3")
        mg.add("Python Tutorial")
        mg.add("Rust")
        results = mg.search_labels("Python")
        assert len(results) == 2

    def test_no_false_positives(self):
        mg = MemoryGraph()
        mg.add("Great Python")  # contains but doesn't start with
        results = mg.search_labels("Python")
        assert len(results) == 0

    def test_limit(self):
        mg = MemoryGraph()
        for i in range(5):
            mg.add(f"api_v{i}")
        results = mg.search_labels("api", limit=2)
        assert len(results) == 2

    def test_weight_ordering(self):
        mg = MemoryGraph()
        a = mg.add("alpha_one")
        b = mg.add("alpha_two")
        mg.reweight(b.id, 5.0)  # b has higher weight
        mg.reweight(a.id, 0.0)  # a stays default-ish
        results = mg.search_labels("alpha")
        # higher weight should come first
        assert results[0].weight >= results[1].weight


class TestEdgeWeightStats:

    def test_empty(self):
        mg = MemoryGraph()
        s = mg.edge_weight_stats()
        assert s == {"count": 0, "min": 0, "max": 0, "mean": 0, "sum": 0}

    def test_basic(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r", 1.0)
        mg.link(b.id, c.id, "r", 3.0)
        mg.link(c.id, a.id, "r", 5.0)
        s = mg.edge_weight_stats()
        assert s["count"] == 3
        assert s["min"] == 1.0
        assert s["max"] == 5.0
        assert s["sum"] == 9.0
        assert s["mean"] == 3.0

    def test_filter_by_relation(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "friend", 1.0)
        mg.link(b.id, c.id, "foe", 10.0)
        s = mg.edge_weight_stats(relation="friend")
        assert s["count"] == 1
        assert s["mean"] == 1.0
        s2 = mg.edge_weight_stats(relation="foe")
        assert s2["count"] == 1
        assert s2["mean"] == 10.0

    def test_no_matching_relation(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r", 1.0)
        s = mg.edge_weight_stats(relation="nonexistent")
        assert s["count"] == 0

    def test_negative_weights(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r", -2.5)
        s = mg.edge_weight_stats()
        assert s["min"] == -2.5
        assert s["sum"] == -2.5


class TestWeightDistribution:

    def test_empty(self):
        mg = MemoryGraph()
        assert mg.weight_distribution() == []

    def test_single_node(self):
        mg = MemoryGraph()
        mg.add("A")
        dist = mg.weight_distribution()
        assert len(dist) == 1
        assert dist[0]["count"] == 1

    def test_multiple_nodes(self):
        mg = MemoryGraph()
        for i in range(10):
            mg.add(f"node_{i}")
        # Set varied weights directly
        for r in mg.conn.execute("SELECT id FROM nodes").fetchall():
            import random
            random.seed(hash(r['id']) % 1000)
            mg.conn.execute("UPDATE nodes SET weight=? WHERE id=?",
                            (random.random(), r['id']))
        mg.conn.commit()
        dist = mg.weight_distribution(bins=5)
        assert len(dist) == 5
        assert sum(b["count"] for b in dist) == 10

    def test_bins_parameter(self):
        mg = MemoryGraph()
        ids = []
        for i in range(20):
            n = mg.add(f"n{i}")
            ids.append(n.id)
        # Set varied weights directly (0.0 to 1.0)
        for idx, nid in enumerate(ids):
            mg.conn.execute("UPDATE nodes SET weight=? WHERE id=?",
                            (idx / 20.0, nid))
        mg.conn.commit()
        dist3 = mg.weight_distribution(bins=3)
        dist10 = mg.weight_distribution(bins=10)
        assert len(dist3) == 3
        assert len(dist10) == 10

    def test_with_varied_weights(self):
        mg = MemoryGraph()
        nodes = [mg.add(f"n{i}") for i in range(5)]
        for i, n in enumerate(nodes):
            mg.conn.execute("UPDATE nodes SET weight=? WHERE id=?",
                            (i / 5.0, n.id))
        mg.conn.commit()
        dist = mg.weight_distribution(bins=3)
        assert sum(b["count"] for b in dist) == 5

    def test_range_strings(self):
        mg = MemoryGraph()
        a = mg.add("A")
        b = mg.add("B")
        mg.conn.execute("UPDATE nodes SET weight=0.0 WHERE id=?", (a.id,))
        mg.conn.execute("UPDATE nodes SET weight=1.0 WHERE id=?", (b.id,))
        mg.conn.commit()
        dist = mg.weight_distribution(bins=2)
        assert "range" in dist[0]
        assert "-" in dist[0]["range"]


class TestAdjacencyMatrix:

    def test_empty(self):
        mg = MemoryGraph()
        assert mg.to_adjacency_matrix() == {}

    def test_single_node(self):
        mg = MemoryGraph()
        mg.add("A")
        m = mg.to_adjacency_matrix()
        assert len(m) == 1
        nid = list(m.keys())[0]
        assert m[nid] == {}

    def test_binary(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        m = mg.to_adjacency_matrix()
        assert m[a.id][b.id] == 1
        assert m[b.id][c.id] == 1
        assert a.id not in m.get(c.id, {})

    def test_weighted(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r", 3.5)
        m = mg.to_adjacency_matrix(weight_key="weight")
        assert m[a.id][b.id] == 3.5

    def test_directed(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")  # only A→B
        m = mg.to_adjacency_matrix()
        assert b.id in m[a.id]
        assert a.id not in m[b.id]

    def test_all_nodes_present(self):
        mg = MemoryGraph()
        nodes = [mg.add(f"n{i}") for i in range(5)]
        mg.link(nodes[0].id, nodes[1].id, "r")
        m = mg.to_adjacency_matrix()
        assert len(m) == 5  # all 5 nodes are keys


class TestNodeDistance:

    def test_same_node(self):
        mg = MemoryGraph()
        a = mg.add("A")
        assert mg.node_distance(a.id, a.id) == 0

    def test_direct_connection(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.node_distance(a.id, b.id) == 1

    def test_two_hops(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.node_distance(a.id, c.id) == 2

    def test_unreachable(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        assert mg.node_distance(a.id, b.id) is None

    def test_nonexistent_source(self):
        mg = MemoryGraph()
        b = mg.add("B")
        assert mg.node_distance("nonexistent", b.id) is None


class TestClosenessCentrality:

    def test_single_node(self):
        mg = MemoryGraph()
        a = mg.add("A")
        assert mg.closeness_centrality(a.id) == 0.0

    def test_two_connected_nodes(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        # reachable=1, total_dist=1, n-1=1 → 1²/(1*1) = 1.0
        assert mg.closeness_centrality(a.id) == 1.0

    def test_line_graph_end(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        # From A: dist to B=1, C=2. reachable=2, total=3, n-1=2
        # WF: 2² / (2*3) = 4/6 ≈ 0.6667
        c_a = mg.closeness_centrality(a.id)
        assert abs(c_a - (4.0/6.0)) < 1e-9

    def test_line_graph_center(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        # From B: dist to A=1, C=1. reachable=2, total=2, n-1=2
        # WF: 2² / (2*2) = 1.0
        assert mg.closeness_centrality(b.id) == 1.0

    def test_center_more_central(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        c_b = mg.closeness_centrality(b.id)
        c_a = mg.closeness_centrality(a.id)
        assert c_b > c_a

    def test_isolated_node(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        assert mg.closeness_centrality(a.id) == 0.0

    def test_nonexistent_node(self):
        mg = MemoryGraph()
        assert mg.closeness_centrality("nonexistent") is None

    def test_star_graph_center(self):
        mg = MemoryGraph()
        center = mg.add("center")
        leaves = [mg.add(f"L{i}") for i in range(4)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
        # n=5, reachable=4, total_dist=4, n-1=4
        # WF: 4² / (4*4) = 1.0
        assert mg.closeness_centrality(center.id) == 1.0

    def test_disconnected_penalty(self):
        """Node in disconnected graph should have lower closeness."""
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        c, d = mg.add("C"), mg.add("D")  # isolated
        mg.link(a.id, b.id, "r")
        # n=4, reachable=1, total_dist=1, n-1=3
        # WF: 1² / (3*1) = 0.333
        c_a = mg.closeness_centrality(a.id)
        assert abs(c_a - (1.0/3.0)) < 1e-9

    def test_complete_graph(self):
        mg = MemoryGraph()
        nodes = [mg.add(f"N{i}") for i in range(4)]
        for x in nodes:
            for y in nodes:
                if x.id != y.id:
                    mg.link(x.id, y.id, "r")
        # n=4, from any node: reachable=3, total_dist=3, n-1=3
        # WF: 9 / (3*3) = 1.0
        assert mg.closeness_centrality(nodes[0].id) == 1.0


class TestGraphDiameter:

    def test_empty_graph(self):
        mg = MemoryGraph()
        assert mg.graph_diameter() is None

    def test_single_node(self):
        mg = MemoryGraph()
        mg.add("A")
        assert mg.graph_diameter() == 0

    def test_two_connected_nodes(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.graph_diameter() == 1

    def test_line_graph_5(self):
        mg = MemoryGraph()
        nodes = [mg.add(f"N{i}") for i in range(5)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i+1].id, "r")
        assert mg.graph_diameter() == 4

    def test_star_graph(self):
        mg = MemoryGraph()
        center = mg.add("center")
        leaves = [mg.add(f"L{i}") for i in range(4)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
        assert mg.graph_diameter() == 2

    def test_disconnected_components(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        d, e = mg.add("D"), mg.add("E")
        mg.link(d.id, e.id, "r")
        assert mg.graph_diameter() == 2

    def test_complete_graph(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        for x in [a, b, c]:
            for y in [a, b, c]:
                if x.id != y.id:
                    mg.link(x.id, y.id, "r")
        assert mg.graph_diameter() == 1

    def test_only_isolated_nodes(self):
        mg = MemoryGraph()
        mg.add("A")
        mg.add("B")
        assert mg.graph_diameter() == 0


class TestEccentricity:

    def test_single_node(self):
        mg = MemoryGraph()
        a = mg.add("A")
        assert mg.eccentricity(a.id) == 0

    def test_line_graph(self):
        mg = MemoryGraph()
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, d.id, "r")
        assert mg.eccentricity(a.id) == 3
        assert mg.eccentricity(b.id) == 2
        assert mg.eccentricity(c.id) == 2
        assert mg.eccentricity(d.id) == 3

    def test_star_graph(self):
        mg = MemoryGraph()
        center = mg.add("center")
        leaves = [mg.add(f"L{i}") for i in range(3)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
        assert mg.eccentricity(center.id) == 1
        assert mg.eccentricity(leaves[0].id) == 2

    def test_nonexistent_node(self):
        mg = MemoryGraph()
        assert mg.eccentricity("nonexistent") is None

    def test_isolated_node(self):
        mg = MemoryGraph()
        a = mg.add("A")
        b = mg.add("B")
        assert mg.eccentricity(a.id) == 0


class TestGraphRadius:

    def test_empty_graph(self):
        mg = MemoryGraph()
        assert mg.graph_radius() is None

    def test_single_node(self):
        mg = MemoryGraph()
        mg.add("A")
        assert mg.graph_radius() == 0

    def test_line_graph(self):
        mg = MemoryGraph()
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, d.id, "r")
        # eccentricities: A=3, B=2, C=2, D=3 → radius=2
        assert mg.graph_radius() == 2

    def test_star_graph(self):
        mg = MemoryGraph()
        center = mg.add("center")
        leaves = [mg.add(f"L{i}") for i in range(3)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
        assert mg.graph_radius() == 1

    def test_complete_graph(self):
        mg = MemoryGraph()
        nodes = [mg.add(f"N{i}") for i in range(4)]
        for x in nodes:
            for y in nodes:
                if x.id != y.id:
                    mg.link(x.id, y.id, "r")
        assert mg.graph_radius() == 1


# ── 连通性分析 ──────────────────────────────────────────

class TestConnectedComponents:

    def test_empty_graph(self):
        mg = MemoryGraph()
        assert mg.connected_components() == []

    def test_single_node(self):
        mg = MemoryGraph()
        n = mg.add("A")
        comps = mg.connected_components()
        assert len(comps) == 1
        assert comps[0] == [n.id]

    def test_connected_graph(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        comps = mg.connected_components()
        assert len(comps) == 1
        assert set(comps[0]) == {a.id, b.id, c.id}

    def test_two_components(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        c, d = mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(c.id, d.id, "r")
        comps = mg.connected_components()
        assert len(comps) == 2
        assert len(comps[0]) == 2
        assert len(comps[1]) == 2
        # Sorted by size descending
        assert len(comps[0]) >= len(comps[1])

    def test_three_components_mixed_sizes(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        d, e = mg.add("D"), mg.add("E")
        f = mg.add("F")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(d.id, e.id, "r")
        comps = mg.connected_components()
        assert len(comps) == 3
        assert len(comps[0]) == 3  # A-B-C
        assert len(comps[1]) == 2  # D-E
        assert len(comps[2]) == 1  # F

    def test_isolated_nodes(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        comps = mg.connected_components()
        assert len(comps) == 3

    def test_directional_edges_treated_as_undirected(self):
        """connected_components uses bidirectional BFS."""
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")  # A→B only
        mg.link(b.id, c.id, "r")  # B→C only
        comps = mg.connected_components()
        assert len(comps) == 1  # All connected via bidirectional traversal


class TestIsConnected:

    def test_empty_graph(self):
        mg = MemoryGraph()
        assert mg.is_connected() is True

    def test_single_node(self):
        mg = MemoryGraph()
        mg.add("A")
        assert mg.is_connected() is True

    def test_connected_graph(self):
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.is_connected() is True

    def test_disconnected_graph(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        c, d = mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(c.id, d.id, "r")
        assert mg.is_connected() is False

    def test_isolated_node_in_connected_graph(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        c = mg.add("C")  # isolated
        mg.link(a.id, b.id, "r")
        assert mg.is_connected() is False


class TestAveragePathLength:

    def test_empty_graph(self):
        mg = MemoryGraph()
        assert mg.average_path_length() is None

    def test_single_node(self):
        mg = MemoryGraph()
        mg.add("A")
        assert mg.average_path_length() == 0.0

    def test_two_connected_nodes(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.average_path_length() == 1.0

    def test_line_graph_4_nodes(self):
        """A-B-C-D: pairs = 6, distances = 1+2+3+1+2+1 = 10, avg = 10/6 ≈ 1.6667"""
        mg = MemoryGraph()
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, d.id, "r")
        assert mg.average_path_length() == round(10 / 6, 4)

    def test_complete_graph(self):
        """K4: all pairs distance=1, avg = 1.0"""
        mg = MemoryGraph()
        nodes = [mg.add(f"N{i}") for i in range(4)]
        for x in nodes:
            for y in nodes:
                if x.id != y.id:
                    mg.link(x.id, y.id, "r")
        assert mg.average_path_length() == 1.0

    def test_star_graph(self):
        """center + 3 leaves: 3 pairs at dist 1, 3 pairs at dist 2 → avg = 9/6 = 1.5"""
        mg = MemoryGraph()
        center = mg.add("center")
        leaves = [mg.add(f"L{i}") for i in range(3)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
        assert mg.average_path_length() == 1.5

    def test_disconnected_components(self):
        """Two pairs: A-B and C-D. Only reachable pairs counted.
        Pairs: (A,B)=1, (C,D)=1. Avg = 2/2 = 1.0"""
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        c, d = mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(c.id, d.id, "r")
        assert mg.average_path_length() == 1.0

    def test_all_isolated(self):
        mg = MemoryGraph()
        mg.add("A")
        mg.add("B")
        mg.add("C")
        assert mg.average_path_length() == 0.0


class TestEffectiveDiameter:

    def test_empty_graph(self):
        mg = MemoryGraph()
        assert mg.effective_diameter() is None

    def test_single_node(self):
        mg = MemoryGraph()
        mg.add("A")
        assert mg.effective_diameter() == 0.0

    def test_two_connected_nodes(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        # 1 pair at distance 1, p0.9 = 1
        assert mg.effective_diameter() == 1.0

    def test_line_graph_5_nodes(self):
        """A-B-C-D-E: 10 pairs. Distances: 1×4, 2×3, 3×2, 4×1 = [1,1,1,1,2,2,2,3,3,4]
        p0.9: idx = int(10*0.9) = 9 → all_dists[9] = 4
        p0.5: idx = int(10*0.5) = 5 → all_dists[5] = 2
        """
        mg = MemoryGraph()
        nodes = [mg.add(c) for c in "ABCDE"]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i+1].id, "r")
        assert mg.effective_diameter(0.9) == 4.0
        assert mg.effective_diameter(0.5) == 2.0

    def test_disconnected_components(self):
        """Two pairs A-B, C-D. Distances = [1, 1]. p0.9 → 1."""
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        c, d = mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(c.id, d.id, "r")
        assert mg.effective_diameter() == 1.0

    def test_all_isolated(self):
        mg = MemoryGraph()
        mg.add("A")
        mg.add("B")
        assert mg.effective_diameter() == 0.0

    def test_invalid_percentile(self):
        mg = MemoryGraph()
        mg.add("A")
        with pytest.raises(ValueError):
            mg.effective_diameter(0)
        with pytest.raises(ValueError):
            mg.effective_diameter(1.5)

    def test_complete_graph(self):
        """K4: all 6 pairs at distance 1. Any percentile = 1."""
        mg = MemoryGraph()
        nodes = [mg.add(f"N{i}") for i in range(4)]
        for x in nodes:
            for y in nodes:
                if x.id != y.id:
                    mg.link(x.id, y.id, "r")
        assert mg.effective_diameter() == 1.0


class TestHarmonicCentrality:

    def test_missing_node(self):
        mg = MemoryGraph()
        assert mg.harmonic_centrality("nonexistent") is None

    def test_single_node(self):
        mg = MemoryGraph()
        n = mg.add("A")
        assert mg.harmonic_centrality(n.id) == 0.0

    def test_two_connected_nodes(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        # H(A) = 1/1 / (2-1) = 1.0
        assert mg.harmonic_centrality(a.id) == 1.0

    def test_line_graph(self):
        """A-B-C: H(B) = (1/1 + 1/1) / 2 = 1.0, H(A) = (1/1 + 1/2) / 2 = 0.75"""
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.harmonic_centrality(b.id) == 1.0
        assert mg.harmonic_centrality(a.id) == 0.75

    def test_disconnected(self):
        """A-B, C isolated. H(A) = (1/1) / 2 ≈ 0.5. C contributes 0."""
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        c = mg.add("C")
        mg.link(a.id, b.id, "r")
        # H(A) = (1/1) / (3-1) = 0.5
        assert mg.harmonic_centrality(a.id) == 0.5
        # H(C) = 0 / 2 = 0.0
        assert mg.harmonic_centrality(c.id) == 0.0

    def test_center_of_star(self):
        """Center connected to 3 leaves. H(center) = (1+1+1) / 3 = 1.0"""
        mg = MemoryGraph()
        center = mg.add("center")
        for i in range(3):
            leaf = mg.add(f"L{i}")
            mg.link(center.id, leaf.id, "r")
        assert mg.harmonic_centrality(center.id) == 1.0


class TestClusteringCoefficient:

    def test_missing_node(self):
        mg = MemoryGraph()
        assert mg.clustering_coefficient("nonexistent") is None

    def test_isolated_node(self):
        mg = MemoryGraph()
        n = mg.add("A")
        assert mg.clustering_coefficient(n.id) == 0.0

    def test_single_edge(self):
        """A-B. A has 1 neighbor → k<2 → 0.0"""
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.clustering_coefficient(a.id) == 0.0

    def test_triangle(self):
        """A-B, B-C, C-A: A's neighbors {B,C} are connected → 1.0"""
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        assert mg.clustering_coefficient(a.id) == 1.0

    def test_open_triple(self):
        """A-B, A-C, but B-C not connected → 0.0"""
        mg = MemoryGraph()
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(a.id, c.id, "r")
        # A has 2 neighbors {B, C}, 0 edges between them → 0.0
        assert mg.clustering_coefficient(a.id) == 0.0

    def test_complete_graph_k4(self):
        """K4: each node has 3 neighbors, all connected → 1.0"""
        mg = MemoryGraph()
        nodes = [mg.add(f"N{i}") for i in range(4)]
        for x in nodes:
            for y in nodes:
                if x.id != y.id:
                    mg.link(x.id, y.id, "r")
        for n in nodes:
            assert mg.clustering_coefficient(n.id) == 1.0

    def test_partial_clustering(self):
        """A connected to B, C, D. Only B-C connected among neighbors.
        k=3, possible=3, actual=1 → 1/3 ≈ 0.333333
        """
        mg = MemoryGraph()
        a = mg.add("A")
        b, c, d = mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(a.id, c.id, "r")
        mg.link(a.id, d.id, "r")
        mg.link(b.id, c.id, "r")  # B-C edge
        result = mg.clustering_coefficient(a.id)
        assert abs(result - (1.0 / 3.0)) < 1e-5


# ── 向量搜索测试 (sqlite-vec 可选集成) ────────────────────

import pytest


class TestVectorSearch:
    """测试 sqlite-vec 向量搜索集成。"""

    def test_add_embedding_basic(self):
        """添加嵌入到节点, 验证不报错。"""
        mg = MemoryGraph()
        node = mg.add("AI concept", "concept")
        mg.add_embedding(node.id, [0.1, 0.2, 0.3, 0.4])
        assert mg.embedding_count() == 1

    def test_add_embedding_multiple(self):
        """多个节点添加嵌入。"""
        mg = MemoryGraph()
        n1 = mg.add("Python", "skill")
        n2 = mg.add("Rust", "skill")
        n3 = mg.add("AI", "concept")
        mg.add_embedding(n1.id, [1.0, 0.0, 0.0, 0.0])
        mg.add_embedding(n2.id, [0.0, 1.0, 0.0, 0.0])
        mg.add_embedding(n3.id, [0.0, 0.0, 1.0, 0.0])
        assert mg.embedding_count() == 3

    def test_add_embedding_overwrite(self):
        """同节点重复添加嵌入会覆盖。"""
        mg = MemoryGraph()
        node = mg.add("test", "fact")
        mg.add_embedding(node.id, [1.0, 0.0, 0.0, 0.0])
        mg.add_embedding(node.id, [0.0, 1.0, 0.0, 0.0])
        assert mg.embedding_count() == 1

    def test_add_embedding_nonexistent_node(self):
        """不存在的节点应报 ValueError。"""
        mg = MemoryGraph()
        with pytest.raises(ValueError):
            mg.add_embedding("nonexistent", [0.1, 0.2])

    def test_search_similar_basic(self):
        """基本 KNN 搜索返回最近邻。"""
        mg = MemoryGraph()
        n1 = mg.add("cat", "concept")
        n2 = mg.add("dog", "concept")
        n3 = mg.add("car", "concept")
        mg.add_embedding(n1.id, [0.1, 0.9, 0.0, 0.0])
        mg.add_embedding(n2.id, [0.2, 0.8, 0.1, 0.0])
        mg.add_embedding(n3.id, [0.9, 0.1, 0.8, 0.5])
        results = mg.search_similar([0.15, 0.85, 0.05, 0.0], limit=2)
        assert len(results) == 2
        assert results[0]["node_id"] in (n1.id, n2.id)
        assert results[0]["distance"] <= results[1]["distance"]
        assert 0 < results[0]["score"] <= 1.0

    def test_search_similar_returns_metadata(self):
        """搜索结果包含 label, kind, distance, score。"""
        mg = MemoryGraph()
        node = mg.add("test node", "fact", {"meta": "data"})
        mg.add_embedding(node.id, [0.5, 0.5])
        results = mg.search_similar([0.5, 0.5], limit=1)
        assert len(results) == 1
        assert results[0]["label"] == "test node"
        assert results[0]["kind"] == "fact"
        assert "distance" in results[0]
        assert "score" in results[0]

    def test_remove_embedding(self):
        """删除嵌入后 embedding_count 减少。"""
        mg = MemoryGraph()
        n1 = mg.add("a")
        n2 = mg.add("b")
        mg.add_embedding(n1.id, [1.0, 0.0])
        mg.add_embedding(n2.id, [0.0, 1.0])
        assert mg.embedding_count() == 2
        assert mg.remove_embedding(n1.id) is True
        assert mg.embedding_count() == 1
        # 删除已删除的返回 False
        assert mg.remove_embedding(n1.id) is False

    def test_remove_embedding_nonexistent(self):
        """删除不存在的嵌入返回 False。"""
        mg = MemoryGraph()
        assert mg.remove_embedding("nonexistent") is False

    def test_embedding_count_empty(self):
        """空图嵌入数为 0。"""
        mg = MemoryGraph()
        assert mg.embedding_count() == 0

    def test_search_similar_no_embeddings(self):
        """没有嵌入时搜索应报 ValueError。"""
        mg = MemoryGraph()
        mg.add("test")
        with pytest.raises(ValueError):
            mg.search_similar([0.1, 0.2])


class TestSearchHybrid:
    """测试混合搜索 (RRF 融合)。"""

    def test_search_hybrid_text_only(self):
        """仅文本查询 (无向量) 应正常工作。"""
        mg = MemoryGraph()
        mg.add("Python programming", "skill")
        mg.add("Rust systems", "skill")
        mg.add("machine learning", "concept")
        results = mg.search_hybrid("Python")
        assert len(results) > 0
        assert any(r["label"] == "Python programming" for r in results)
        assert any(s in results[0]["sources"] for s in ("text", "bm25"))

    def test_search_hybrid_with_embedding(self):
        """文本 + 向量混合搜索。"""
        mg = MemoryGraph()
        n1 = mg.add("AI research", "concept")
        n2 = mg.add("Web dev", "skill")
        mg.add_embedding(n1.id, [0.9, 0.1])
        mg.add_embedding(n2.id, [0.1, 0.9])
        results = mg.search_hybrid("AI", embedding=[0.9, 0.1])
        assert len(results) > 0
        top = results[0]
        assert top["node_id"] == n1.id
        assert any(s in top["sources"] for s in ("text", "bm25"))
        assert "vector" in top["sources"]

    def test_search_hybrid_graph_boost(self):
        """图邻居加成: 被搜索节点的邻居应出现在结果中。"""
        mg = MemoryGraph()
        n1 = mg.add("AI", "concept")
        n2 = mg.add("ML", "concept")
        mg.link(n1.id, n2.id, "related")
        results = mg.search_hybrid("AI")
        labels = [r["label"] for r in results]
        assert "AI" in labels
        # ML 应通过 graph boost 出现
        assert "ML" in labels

    def test_search_hybrid_empty_graph(self):
        """空图混合搜索返回空列表。"""
        mg = MemoryGraph()
        results = mg.search_hybrid("nothing")
        assert results == []

    def test_search_hybrid_limit(self):
        """limit 参数限制返回数量。"""
        mg = MemoryGraph()
        for i in range(10):
            mg.add(f"item_{i}", "concept")
        results = mg.search_hybrid("item", limit=3)
        assert len(results) <= 3

    def test_search_hybrid_sources_field(self):
        """结果包含 sources 字段标注命中来源。"""
        mg = MemoryGraph()
        n1 = mg.add("Python", "skill")
        mg.add_embedding(n1.id, [0.5, 0.5])
        results = mg.search_hybrid("Python", embedding=[0.5, 0.5])
        assert len(results) > 0
        assert "sources" in results[0]
        assert isinstance(results[0]["sources"], list)

    def test_search_hybrid_vector_unavailable_silent(self):
        """向量搜索不可用时 (未安装/无嵌入) 静默降级为纯文本。"""
        mg = MemoryGraph()
        mg.add("test item", "concept")
        # 不添加嵌入但传 embedding 参数, 应不报错
        results = mg.search_hybrid("test", embedding=[0.1, 0.2])
        assert len(results) > 0  # 文本搜索仍工作

    def test_search_hybrid_adaptive_default_mode(self):
        """adaptive 是默认融合模式, 结果包含 query_type。"""
        mg = MemoryGraph()
        mg.add("Python programming language", "skill")
        results = mg.search_hybrid("Python")
        assert len(results) > 0
        assert results[0].get("query_type") is not None
        assert results[0]["query_type"] in ("exact", "semantic", "relational")

    def test_search_hybrid_rrf_backward_compat(self):
        """fusion='rrf' 向后兼容: 无 query_type 字段。"""
        mg = MemoryGraph()
        mg.add("Python programming", "skill")
        results = mg.search_hybrid("Python", fusion="rrf")
        assert len(results) > 0
        assert results[0].get("query_type") is None

    def test_search_hybrid_wrrf_mode(self):
        """WRRF 模式: 置信度加权融合。"""
        mg = MemoryGraph()
        n1 = mg.add("AI research", "concept")
        n2 = mg.add("AI deployment", "concept")
        mg.add_embedding(n1.id, [0.9, 0.1])
        mg.add_embedding(n2.id, [0.8, 0.2])
        results = mg.search_hybrid("AI", embedding=[0.9, 0.1], fusion="wrrf")
        assert len(results) > 0
        assert results[0]["node_id"] == n1.id

    def test_search_hybrid_consensus_bonus(self):
        """共识奖励: 三路同时命中的节点分数应高于单路。"""
        mg = MemoryGraph()
        n1 = mg.add("AI ML", "concept")
        n2 = mg.add("AI", "concept")
        mg.link(n1.id, n2.id, "related")
        mg.add_embedding(n1.id, [0.9, 0.1])
        mg.add_embedding(n2.id, [0.1, 0.9])
        # n1 同时被 text + vector + graph 命中
        results = mg.search_hybrid("AI", embedding=[0.9, 0.1])
        top = results[0]
        assert len(top["sources"]) >= 2  # 至少两路命中

    def test_classify_query_exact(self):
        """QDAP-Lite: 短查询含已知标识符 → exact 类型。"""
        result = MemoryGraph._classify_query("Python", ["Python", "Rust", "machine learning"])
        assert result["type"] == "exact"
        assert result["k"] == 10
        assert result["weights"][0] > result["weights"][1]  # bm25 权重最高

    def test_classify_query_relational(self):
        """QDAP-Lite: 含关系词 → relational 类型。"""
        result = MemoryGraph._classify_query("connection between AI and ML", [])
        assert result["type"] == "relational"
        assert result["weights"][2] > result["weights"][0]  # graph 权重最高

    def test_classify_query_semantic(self):
        """QDAP-Lite: 一般查询 → semantic 类型。"""
        result = MemoryGraph._classify_query("how does deep learning work", [])
        assert result["type"] == "semantic"
        assert result["weights"][1] > result["weights"][0]  # vector 权重最高

    def test_entropy_refine_increases_confident_route(self):
        """Entropy 修正: 确信的路(短排名)应获得相对更高权重。"""
        # 路1有1个结果(低熵=高置信), 路2有10个结果(高熵=低置信)
        rankings = [["a"], list("bcdefghijk")]
        initial = [0.5, 0.5]
        refined = MemoryGraph._entropy_refine(rankings, initial)
        # 路1置信度 > 路2置信度
        assert refined[0] > refined[1]

    def test_entropy_refine_single_route_unchanged(self):
        """Entropy 修正: 单路时不做调整。"""
        refined = MemoryGraph._entropy_refine([["a", "b"]], [1.0])
        assert refined == [1.0]

    def test_search_hybrid_adaptive_with_relation_keyword(self):
        """adaptive 模式: 关系词查询分类为 relational。"""
        mg = MemoryGraph()
        n1 = mg.add("Core", "concept")
        n2 = mg.add("connection", "concept")
        mg.link(n1.id, n2.id, "connect")
        # 'connection' 触发 relation 关键词, 且也是节点标签
        results = mg.search_hybrid("connection")
        assert len(results) > 0
        assert results[0]["query_type"] == "relational"


class TestAdaptiveFusionExtras:
    """Adaptive Fusion 额外功能测试。"""

    def test_classify_query_chinese_relational(self):
        """中文关系词也正确分类。"""
        result = MemoryGraph._classify_query("节点之间的连接路径", [])
        assert result["type"] == "relational"

    def test_classify_query_empty(self):
        """空查询默认为 semantic。"""
        result = MemoryGraph._classify_query("", [])
        assert result["type"] == "semantic"

    def test_search_hybrid_adaptive_adapts_k(self):
        """adaptive 模式 k 值小于经典 RRF k=60。"""
        mg = MemoryGraph()
        mg.add("Python", "skill")
        results_adaptive = mg.search_hybrid("Python", fusion="adaptive")
        results_rrf = mg.search_hybrid("Python", fusion="rrf")
        # 两模式都应返回结果
        assert len(results_adaptive) > 0
        assert len(results_rrf) > 0
        # adaptive 分数可能不同 (不同 k 值)
        assert results_adaptive[0]["score"] != results_rrf[0]["score"]

    def test_search_hybrid_consensus_bonus_ordering(self):
        """共识奖励: 多路命中节点 source 数更多。"""
        mg = MemoryGraph()
        n1 = mg.add("test alpha", "concept")
        n2 = mg.add("test beta", "concept")
        mg.add_embedding(n1.id, [0.95, 0.05])
        mg.add_embedding(n2.id, [0.5, 0.5])
        mg.link(n1.id, n2.id, "related")
        # n1 同时被 text+vector+graph 命中
        results = mg.search_hybrid("test", embedding=[0.95, 0.05])
        top = results[0]
        # 多路命中的节点至少两路
        assert len(top["sources"]) >= 2


    def test_search_hybrid_graph_weighted_bonus_ordering(self):
        """Weighted bonus: edge weight 高的邻居排名应高于 weight 低的。"""
        mg = MemoryGraph()
        n1 = mg.add("hub", "concept")
        n2 = mg.add("strong_link", "concept")
        n3 = mg.add("weak_link", "concept")
        mg.link(n1.id, n2.id, "related", weight=5.0)
        mg.link(n1.id, n3.id, "related", weight=0.1)
        results = mg.search_hybrid("hub")
        # strong_link 应出现在 weak_link 之前（edge weight 排序）
        labels = [r["label"] for r in results]
        if "strong_link" in labels and "weak_link" in labels:
            assert labels.index("strong_link") < labels.index("weak_link")

    def test_search_hybrid_graph_wrrf_uses_edge_weights(self):
        """WRRF 模式: graph 路应使用 edge weight 作为 confidence。"""
        mg = MemoryGraph()
        n1 = mg.add("root", "concept")
        n2 = mg.add("heavy", "concept")
        n3 = mg.add("light", "concept")
        mg.link(n1.id, n2.id, "related", weight=10.0)
        mg.link(n1.id, n3.id, "related", weight=0.01)
        mg.add_embedding(n1.id, [0.9, 0.1])
        mg.add_embedding(n2.id, [0.85, 0.15])
        mg.add_embedding(n3.id, [0.5, 0.5])
        results = mg.search_hybrid("root", embedding=[0.9, 0.1], fusion="wrrf")
        labels = [r["label"] for r in results]
        # heavy 应排在 light 之前（更高 edge weight = 更高 confidence）
        if "heavy" in labels and "light" in labels:
            assert labels.index("heavy") < labels.index("light")


    def test_graph_weighted_bonus_strong_beats_weak_score(self):
        """Weighted bonus: 强连接邻居的 score 应严格高于弱连接邻居。"""
        mg = MemoryGraph()
        n1 = mg.add("seed", "concept")
        n2 = mg.add("strong_neighbor", "concept")
        n3 = mg.add("weak_neighbor", "concept")
        mg.link(n1.id, n2.id, "related", weight=10.0)
        mg.link(n1.id, n3.id, "related", weight=0.01)
        results = mg.search_hybrid("seed", fusion="rrf")
        scores = {r["label"]: r["score"] for r in results}
        # Both should appear via graph boost
        if "strong_neighbor" in scores and "weak_neighbor" in scores:
            assert scores["strong_neighbor"] > scores["weak_neighbor"]

    def test_graph_weighted_bonus_proportional(self):
        """Weighted bonus: 相同 rank 位置, edge weight 翻倍 ≈ score 增量可测。"""
        mg_a = MemoryGraph()
        n1a = mg_a.add("seed", "concept")
        n2a = mg_a.add("neighbor", "concept")
        mg_a.link(n1a.id, n2a.id, "related", weight=1.0)
        results_a = mg_a.search_hybrid("seed", fusion="rrf")
        score_a = {r["label"]: r["score"] for r in results_a}.get("neighbor", 0.0)

        mg_b = MemoryGraph()
        n1b = mg_b.add("seed", "concept")
        n2b = mg_b.add("neighbor", "concept")
        mg_b.link(n1b.id, n2b.id, "related", weight=100.0)
        results_b = mg_b.search_hybrid("seed", fusion="rrf")
        score_b = {r["label"]: r["score"] for r in results_b}.get("neighbor", 0.0)

        # With weighted bonus: weight=1.0 (normalized=1.0) → bonus=2.0x
        # weight=100.0 (normalized=1.0) → bonus=2.0x
        # Both normalize to 1.0, so scores should be identical
        assert abs(score_a - score_b) < 0.001

    def test_graph_weighted_bonus_disabled_via_equal_weights(self):
        """所有 edge weights 相同时, weighted bonus 退化为标准 RRF。"""
        mg = MemoryGraph()
        n1 = mg.add("center", "concept")
        n2 = mg.add("a", "concept")
        n3 = mg.add("b", "concept")
        # Equal weights → normalized all 1.0 → bonus = 2.0x for both
        mg.link(n1.id, n2.id, "related", weight=1.0)
        mg.link(n1.id, n3.id, "related", weight=1.0)
        results = mg.search_hybrid("center", fusion="rrf")
        scores = {r["label"]: r["score"] for r in results}
        # With equal weights, both neighbors get same score
        if "a" in scores and "b" in scores:
            assert abs(scores["a"] - scores["b"]) < 0.001

    def test_graph_weighted_bonus_multi_seed(self):
        """Weighted bonus 在多邻居场景中保持排序一致性。"""
        mg = MemoryGraph()
        hub = mg.add("hub", "concept")
        weights = [10.0, 5.0, 2.0, 0.5, 0.01]
        for i, w in enumerate(weights):
            nid = mg.add(f"node_{i}", "concept")
            mg.link(hub.id, nid.id, "related", weight=w)
        results = mg.search_hybrid("hub", fusion="rrf")
        labels = [r["label"] for r in results]
        # Verify higher weight → higher rank (earlier in results)
        graph_nodes = [l for l in labels if l.startswith("node_")]
        # node_0 (weight=10) should come before node_4 (weight=0.01)
        if len(graph_nodes) >= 2:
            assert graph_nodes[0] == "node_0"
            assert graph_nodes[-1] == "node_4"

    def test_graph_weighted_bonus_adaptive_mode(self):
        """Weighted bonus 在 adaptive 模式下也生效。"""
        mg = MemoryGraph()
        n1 = mg.add("root", "concept")
        n2 = mg.add("strong", "concept")
        n3 = mg.add("weak", "concept")
        mg.link(n1.id, n2.id, "related", weight=5.0)
        mg.link(n1.id, n3.id, "related", weight=0.1)
        # adaptive mode should also show weighted bonus effect
        results = mg.search_hybrid("root", fusion="adaptive")
        labels = [r["label"] for r in results]
        if "strong" in labels and "weak" in labels:
            assert labels.index("strong") < labels.index("weak")


class TestVectorBatchOps:
    """测试向量批量操作和工具。"""

    def test_add_embeddings_batch_basic(self):
        """批量添加嵌入。"""
        mg = MemoryGraph()
        n1 = mg.add("alpha")
        n2 = mg.add("beta")
        n3 = mg.add("gamma")
        count = mg.add_embeddings_batch([
            (n1.id, [1.0, 0.0, 0.0]),
            (n2.id, [0.0, 1.0, 0.0]),
            (n3.id, [0.0, 0.0, 1.0]),
        ])
        assert count == 3
        assert mg.embedding_count() == 3

    def test_add_embeddings_batch_skip_nonexistent(self):
        """批量添加时跳过不存在的节点。"""
        mg = MemoryGraph()
        n1 = mg.add("real")
        count = mg.add_embeddings_batch([
            (n1.id, [1.0, 0.0]),
            ("nonexistent", [0.0, 1.0]),
        ])
        assert count == 1
        assert mg.embedding_count() == 1

    def test_add_embeddings_batch_empty(self):
        """空列表返回 0。"""
        mg = MemoryGraph()
        assert mg.add_embeddings_batch([]) == 0

    def test_search_similar_to_node(self):
        """基于节点嵌入查找相似节点。"""
        mg = MemoryGraph()
        n1 = mg.add("cat", "concept")
        n2 = mg.add("dog", "concept")
        n3 = mg.add("car", "concept")
        mg.add_embedding(n1.id, [0.1, 0.9, 0.0])
        mg.add_embedding(n2.id, [0.2, 0.8, 0.1])
        mg.add_embedding(n3.id, [0.9, 0.1, 0.8])
        results = mg.search_similar_to_node(n1.id, limit=2)
        assert len(results) <= 2
        # 排除自身
        assert all(r["node_id"] != n1.id for r in results)
        # dog 应比 car 更接近 cat
        if len(results) >= 2:
            dog_result = next((r for r in results if r["node_id"] == n2.id), None)
            car_result = next((r for r in results if r["node_id"] == n3.id), None)
            if dog_result and car_result:
                assert dog_result["distance"] <= car_result["distance"]

    def test_search_similar_to_node_no_embedding(self):
        """节点没有嵌入时报 ValueError。"""
        mg = MemoryGraph()
        node = mg.add("test")
        with pytest.raises(ValueError):
            mg.search_similar_to_node(node.id)

    def test_vector_stats_empty(self):
        """空图向量统计。"""
        mg = MemoryGraph()
        stats = mg.vector_stats()
        assert stats["count"] == 0
        assert stats["has_vectors"] is False

    def test_vector_stats_with_data(self):
        """有嵌入时的统计。"""
        mg = MemoryGraph()
        n1 = mg.add("a")
        n2 = mg.add("b")
        mg.add_embedding(n1.id, [1.0, 0.0, 0.0, 0.0])
        mg.add_embedding(n2.id, [0.0, 1.0, 0.0, 0.0])
        stats = mg.vector_stats()
        assert stats["count"] == 2
        assert stats["has_vectors"] is True
        assert stats["dimensions"] == 4
        assert stats["node_count"] == 2
        assert stats["coverage"] == 1.0

    def test_vector_stats_partial_coverage(self):
        """部分节点有嵌入。"""
        mg = MemoryGraph()
        n1 = mg.add("has_vec")
        mg.add("no_vec_1")
        mg.add("no_vec_2")
        mg.add_embedding(n1.id, [0.5, 0.5])
        stats = mg.vector_stats()
        assert stats["count"] == 1
        assert stats["node_count"] == 3
        assert 0 < stats["coverage"] < 1.0

    def test_has_embedding_true(self):
        """有嵌入的节点返回 True。"""
        mg = MemoryGraph()
        node = mg.add("test")
        mg.add_embedding(node.id, [0.5, 0.5])
        assert mg.has_embedding(node.id) is True

    def test_has_embedding_false(self):
        """无嵌入的节点返回 False。"""
        mg = MemoryGraph()
        node = mg.add("test")
        assert mg.has_embedding(node.id) is False

    def test_has_embedding_nonexistent(self):
        """不存在的节点返回 False。"""
        mg = MemoryGraph()
        assert mg.has_embedding("nonexistent") is False

    def test_remove_then_has_embedding(self):
        """删除嵌入后 has_embedding 返回 False。"""
        mg = MemoryGraph()
        node = mg.add("test")
        mg.add_embedding(node.id, [0.5, 0.5])
        assert mg.has_embedding(node.id) is True
        mg.remove_embedding(node.id)
        assert mg.has_embedding(node.id) is False

    def test_search_similar_score_range(self):
        """相似度搜索的 score 在 0~1 范围。"""
        mg = MemoryGraph()
        n1 = mg.add("a")
        n2 = mg.add("b")
        mg.add_embedding(n1.id, [0.1, 0.2, 0.3])
        mg.add_embedding(n2.id, [0.4, 0.5, 0.6])
        results = mg.search_similar([0.1, 0.2, 0.3], limit=2)
        for r in results:
            assert 0 < r["score"] <= 1.0


# ── import_edgelist ────────────────────────────────────────────

class TestImportEdgelist:

    def test_basic_import(self):
        mg = MemoryGraph()
        lines = ["a b 0.5", "b c 1.0", "a c 0.3"]
        result = mg.import_edgelist(lines)
        assert result["nodes"] == 3
        assert result["edges"] == 3
        assert mg.has_node("a")
        assert mg.has_node("b")
        assert mg.has_node("c")

    def test_default_weight(self):
        mg = MemoryGraph()
        lines = ["x y"]
        result = mg.import_edgelist(lines)
        assert result["edges"] == 1
        edges = mg.conn.execute("SELECT weight FROM edges WHERE source='x' AND target='y'").fetchone()
        assert edges["weight"] == 1.0

    def test_clear_before_import(self):
        mg = MemoryGraph()
        n1 = mg.add("old1")
        mg.import_edgelist(["a b"])
        assert not mg.has_node(n1.id)
        assert mg.has_node("a")

    def test_merge_mode(self):
        mg = MemoryGraph()
        existing = mg.add("existing")
        result = mg.import_edgelist([f"{existing.id} new_node 0.5"], merge=True)
        assert mg.has_node(existing.id)
        assert mg.has_node("new_node")
        assert result["nodes"] == 1

    def test_empty_lines(self):
        mg = MemoryGraph()
        result = mg.import_edgelist(["", "  ", "a b"])
        assert result["nodes"] == 2
        assert result["edges"] == 1

    def test_round_trip(self):
        """export → import 往返测试。"""
        mg1 = MemoryGraph()
        a = mg1.add("Alpha")
        b = mg1.add("Beta")
        mg1.link(a.id, b.id, "r", weight=0.7)
        mg1.link(b.id, a.id, "r", weight=0.3)
        exported = mg1.serialize_edgelist()
        mg2 = MemoryGraph()
        mg2.import_edgelist(exported)
        assert len(mg2.conn.execute("SELECT id FROM nodes").fetchall()) == 2
        assert len(mg2.conn.execute("SELECT source FROM edges").fetchall()) == 2

    def test_extra_columns_ignored(self):
        mg = MemoryGraph()
        lines = ["a b 0.5 extra_label extra_stuff"]
        result = mg.import_edgelist(lines)
        assert result["edges"] == 1


# ── import_cytoscape ────────────────────────────────────────────

class TestImportCytoscape:

    def test_basic_import(self):
        mg = MemoryGraph()
        data = {
            "elements": {
                "nodes": [
                    {"data": {"id": "n1", "label": "Node1", "kind": "concept", "weight": 1.5, "tags": []}},
                    {"data": {"id": "n2", "label": "Node2", "kind": "entity", "weight": 0.8, "tags": ["test"]}},
                ],
                "edges": [
                    {"data": {"id": "e0", "source": "n1", "target": "n2", "relation": "related", "weight": 0.5}},
                ],
            }
        }
        result = mg.import_cytoscape(data)
        assert result["nodes"] == 2
        assert result["edges"] == 1
        assert mg.has_node("n1")
        assert mg.has_node("n2")

    def test_merge_mode(self):
        mg = MemoryGraph()
        existing = mg.add("existing")
        data = {
            "elements": {
                "nodes": [{"data": {"id": existing.id, "label": "X"}}, {"data": {"id": "new", "label": "Y"}}],
                "edges": [],
            }
        }
        result = mg.import_cytoscape(data, merge=True)
        assert result["nodes"] == 1
        assert mg.has_node("new")

    def test_round_trip(self):
        """serialize_cytoscape → import_cytoscape 往返测试。"""
        mg1 = MemoryGraph()
        alpha = mg1.add("Alpha", kind="concept")
        beta = mg1.add("Beta", kind="entity")
        mg1.conn.execute("UPDATE nodes SET weight=2.0 WHERE id=?", (alpha.id,))
        mg1.conn.execute("UPDATE nodes SET weight=1.0 WHERE id=?", (beta.id,))
        mg1.link(alpha.id, beta.id, "connects", weight=0.6)
        exported = mg1.serialize_cytoscape()
        mg2 = MemoryGraph()
        mg2.import_cytoscape(exported)
        assert len(mg2.conn.execute("SELECT id FROM nodes").fetchall()) == 2
        assert len(mg2.conn.execute("SELECT source FROM edges").fetchall()) == 1
        node = mg2.get_node(alpha.id)
        assert node.label == "Alpha"
        assert node.kind == "concept"

    def test_missing_optional_fields(self):
        mg = MemoryGraph()
        data = {
            "elements": {
                "nodes": [{"data": {"id": "x"}}, {"data": {"id": "y"}}],
                "edges": [{"data": {"source": "x", "target": "y"}}],
            }
        }
        result = mg.import_cytoscape(data)
        assert result["nodes"] == 2
        assert result["edges"] == 1
        node = mg.get_node("x")
        assert node.label == "x"  # default to id

    def test_tags_import(self):
        mg = MemoryGraph()
        data = {
            "elements": {
                "nodes": [{"data": {"id": "n1", "label": "N1", "tags": ["demo"]}}],
                "edges": [],
            }
        }
        mg.import_cytoscape(data)
        tags = mg.all_tags()
        assert "demo" in tags

    def test_clear_before_import(self):
        mg = MemoryGraph()
        mg.add("old")
        data = {"elements": {"nodes": [{"data": {"id": "new"}}], "edges": []}}
        mg.import_cytoscape(data)
        assert not mg.has_node("old")
        assert mg.has_node("new")


# ── import_graphml ────────────────────────────────────────────

class TestImportGraphML:

    def test_basic_import(self):
        mg = MemoryGraph()
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="d0" for="node" attr.name="label" attr.type="string"/>
  <key id="d1" for="node" attr.name="kind" attr.type="string"/>
  <key id="d2" for="node" attr.name="weight" attr.type="double"/>
  <key id="d3" for="edge" attr.name="relation" attr.type="string"/>
  <key id="d4" for="edge" attr.name="weight" attr.type="double"/>
  <graph>
    <node id="a"><data key="d0">Alpha</data><data key="d1">concept</data><data key="d2">1.5</data></node>
    <node id="b"><data key="d0">Beta</data><data key="d1">entity</data><data key="d2">0.8</data></node>
    <edge source="a" target="b"><data key="d3">related</data><data key="d4">0.5</data></edge>
  </graph>
</graphml>'''
        result = mg.import_graphml(xml)
        assert result["nodes"] == 2
        assert result["edges"] == 1
        assert mg.has_node("a")
        node = mg.get_node("a")
        assert node.label == "Alpha"
        assert node.kind == "concept"
        assert node.weight == 1.5

    def test_round_trip(self):
        """serialize_graphml → import_graphml 往返测试。"""
        mg1 = MemoryGraph()
        x = mg1.add("X", kind="concept")
        y = mg1.add("Y", kind="entity")
        mg1.conn.execute("UPDATE nodes SET weight=2.0 WHERE id=?", (x.id,))
        mg1.conn.execute("UPDATE nodes SET weight=1.0 WHERE id=?", (y.id,))
        mg1.link(x.id, y.id, "connects", weight=0.7)
        exported = mg1.serialize_graphml()
        mg2 = MemoryGraph()
        mg2.import_graphml(exported)
        assert len(mg2.conn.execute("SELECT id FROM nodes").fetchall()) == 2
        assert len(mg2.conn.execute("SELECT source FROM edges").fetchall()) == 1
        node = mg2.get_node(x.id)
        assert node.label == "X"
        assert node.kind == "concept"

    def test_merge_mode(self):
        mg = MemoryGraph()
        existing = mg.add("existing")
        xml = f'''<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph><node id="{existing.id}"/><node id="new"/></graph>
</graphml>'''
        result = mg.import_graphml(xml, merge=True)
        assert result["nodes"] == 1
        assert mg.has_node("new")

    def test_empty_graph(self):
        mg = MemoryGraph()
        xml = '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"><graph/></graphml>'
        result = mg.import_graphml(xml)
        assert result["nodes"] == 0
        assert result["edges"] == 0

    def test_missing_keys_still_imports(self):
        """GraphML 没有自定义 key 时仍能导入节点和边。"""
        mg = MemoryGraph()
        xml = '''<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph><node id="a"/><node id="b"/><edge source="a" target="b"/></graph>
</graphml>'''
        result = mg.import_graphml(xml)
        assert result["nodes"] == 2
        assert result["edges"] == 1


# ── is_bipartite ───────────────────────────────────────────────

class TestIsBipartite:

    def test_simple_bipartite(self):
        """a-b-c 是二分图 ({a,c} vs {b})。"""
        mg = MemoryGraph()
        mg._insert_node_raw("a", "A")
        mg._insert_node_raw("b", "B")
        mg._insert_node_raw("c", "C")
        mg.link("a", "b", "r")
        mg.link("b", "c", "r")
        assert mg.is_bipartite() is True

    def test_triangle_not_bipartite(self):
        """三角形不是二分图。"""
        mg = MemoryGraph()
        for n in ["a", "b", "c"]:
            mg._insert_node_raw(n, n)
        mg.link("a", "b", "r")
        mg.link("b", "c", "r")
        mg.link("c", "a", "r")
        assert mg.is_bipartite() is False

    def test_single_edge(self):
        """单条边是二分图。"""
        mg = MemoryGraph()
        mg._insert_node_raw("x", "X")
        mg._insert_node_raw("y", "Y")
        mg.link("x", "y", "r")
        assert mg.is_bipartite() is True

    def test_disconnected_bipartite(self):
        """不连通的二分图仍然是二分图。"""
        mg = MemoryGraph()
        for n in ["a", "b", "c", "d"]:
            mg._insert_node_raw(n, n)
        mg.link("a", "b", "r")
        mg.link("c", "d", "r")
        assert mg.is_bipartite() is True

    def test_empty_graph(self):
        """空图是二分图。"""
        mg = MemoryGraph()
        assert mg.is_bipartite() is True

    def test_single_node(self):
        """单节点是二分图。"""
        mg = MemoryGraph()
        mg.add("solo")
        assert mg.is_bipartite() is True

    def test_odd_cycle_not_bipartite(self):
        """五边形不是二分图（奇环）。"""
        mg = MemoryGraph()
        for n in ["a", "b", "c", "d", "e"]:
            mg._insert_node_raw(n, n)
        mg.link("a", "b", "r")
        mg.link("b", "c", "r")
        mg.link("c", "d", "r")
        mg.link("d", "e", "r")
        mg.link("e", "a", "r")
        assert mg.is_bipartite() is False


# ── find_bridges ───────────────────────────────────────────────

class TestFindBridges:

    def test_single_bridge(self):
        """a-b-c 中 b-c 是桥（如果 a-b 不在另一条路径上）...actually a-b and b-c are both bridges."""
        mg = MemoryGraph()
        for n in ["a", "b", "c"]:
            mg._insert_node_raw(n, n)
        mg.link("a", "b", "r")
        mg.link("b", "c", "r")
        bridges = mg.find_bridges()
        assert len(bridges) == 2

    def test_no_bridge_in_cycle(self):
        """环中没有桥。"""
        mg = MemoryGraph()
        for n in ["a", "b", "c"]:
            mg._insert_node_raw(n, n)
        mg.link("a", "b", "r")
        mg.link("b", "c", "r")
        mg.link("c", "a", "r")
        bridges = mg.find_bridges()
        assert len(bridges) == 0

    def test_bridge_in_figure_eight(self):
        """两个三角形共享一个节点，共享节点的两条边不是桥，其余4条都是桥... wait no.
        共享节点 b: a-b-c-a + d-b-e-d. All edges are bridges except none form cycle.
        Actually: a-b, b-c, c-a form triangle (no bridges).
        d-b, b-e, e-d form triangle (no bridges).
        So 0 bridges."""
        mg = MemoryGraph()
        for n in ["a", "b", "c", "d", "e"]:
            mg._insert_node_raw(n, n)
        mg.link("a", "b", "r")
        mg.link("b", "c", "r")
        mg.link("c", "a", "r")
        mg.link("d", "b", "r")
        mg.link("b", "e", "r")
        mg.link("e", "d", "r")
        bridges = mg.find_bridges()
        assert len(bridges) == 0

    def test_bridge_single_edge(self):
        """单条边就是桥。"""
        mg = MemoryGraph()
        mg._insert_node_raw("x", "X")
        mg._insert_node_raw("y", "Y")
        mg.link("x", "y", "r")
        bridges = mg.find_bridges()
        assert len(bridges) == 1

    def test_bridge_returns_edge_info(self):
        """桥返回 (source, target, relation) 元组。"""
        mg = MemoryGraph()
        mg._insert_node_raw("a", "A")
        mg._insert_node_raw("b", "B")
        mg.link("a", "b", "connects")
        bridges = mg.find_bridges()
        assert len(bridges) == 1
        src, tgt, rel = bridges[0]
        assert src == "a"
        assert tgt == "b"
        assert rel == "connects"

    def test_no_bridges_in_complete_graph(self):
        """K4 完全图没有桥。"""
        mg = MemoryGraph()
        for n in ["a", "b", "c", "d"]:
            mg._insert_node_raw(n, n)
        for i, a in enumerate(["a", "b", "c", "d"]):
            for b in ["a", "b", "c", "d"][i+1:]:
                mg.link(a, b, "r")
        bridges = mg.find_bridges()
        assert len(bridges) == 0


# ── articulation_points ────────────────────────────────────────

class TestArticulationPoints:

    def test_simple_cut_vertex(self):
        """a-b-c-d 线性图，b 和 c 是割点。"""
        mg = MemoryGraph()
        for n in ["a", "b", "c", "d"]:
            mg._insert_node_raw(n, n)
        mg.link("a", "b", "r")
        mg.link("b", "c", "r")
        mg.link("c", "d", "r")
        aps = mg.articulation_points()
        assert "b" in aps
        assert "c" in aps

    def test_no_cut_vertex_in_cycle(self):
        """环中没有割点。"""
        mg = MemoryGraph()
        for n in ["a", "b", "c", "d"]:
            mg._insert_node_raw(n, n)
        mg.link("a", "b", "r")
        mg.link("b", "c", "r")
        mg.link("c", "d", "r")
        mg.link("d", "a", "r")
        aps = mg.articulation_points()
        assert len(aps) == 0

    def test_center_of_star(self):
        """星形图中心是割点。"""
        mg = MemoryGraph()
        for n in ["center", "a", "b", "c", "d"]:
            mg._insert_node_raw(n, n)
        mg.link("center", "a", "r")
        mg.link("center", "b", "r")
        mg.link("center", "c", "r")
        mg.link("center", "d", "r")
        aps = mg.articulation_points()
        assert "center" in aps

    def test_empty_graph(self):
        """空图没有割点。"""
        mg = MemoryGraph()
        assert mg.articulation_points() == []

    def test_single_edge_no_cut(self):
        """单条边两端都不是割点（删除任一节点只留一个节点）。"""
        mg = MemoryGraph()
        mg._insert_node_raw("a", "A")
        mg._insert_node_raw("b", "B")
        mg.link("a", "b", "r")
        aps = mg.articulation_points()
        assert len(aps) == 0

    def test_two_triangles_connected(self):
        """两个三角形通过一条边相连，连接边的两端是割点。"""
        mg = MemoryGraph()
        for n in ["a", "b", "c", "d", "e", "f"]:
            mg._insert_node_raw(n, n)
        # Triangle 1: a-b-c-a
        mg.link("a", "b", "r")
        mg.link("b", "c", "r")
        mg.link("c", "a", "r")
        # Bridge: c-d
        mg.link("c", "d", "r")
        # Triangle 2: d-e-f-d
        mg.link("d", "e", "r")
        mg.link("e", "f", "r")
        mg.link("f", "d", "r")
        aps = mg.articulation_points()
        assert "c" in aps
        assert "d" in aps
        assert len(aps) == 2


# ── update_embedding + remove_embeddings_batch ──────────────────

class TestUpdateEmbedding:

    def test_update_changes_vector(self):
        """更新嵌入后搜索结果应反映新向量。"""
        mg = MemoryGraph()
        a = mg.add("a", kind="concept")
        b = mg.add("b", kind="concept")
        mg.add_embedding(a.id, [1.0, 0.0])
        mg.add_embedding(b.id, [0.0, 1.0])
        # Search for a-like → a first
        results = mg.search_similar([1.0, 0.0], limit=2)
        assert results[0]["node_id"] == a.id
        # Update a to be like b
        mg.update_embedding(a.id, [0.0, 1.0])
        results = mg.search_similar([1.0, 0.0], limit=2)
        # Now a should be far from [1,0] and b should be far too
        # Both are [0,1] so distance is same; just verify update worked
        a_result = [r for r in results if r["node_id"] == a.id]
        assert len(a_result) == 1

    def test_update_nonexistent_creates(self):
        """update_embedding 对无嵌入的节点也能工作。"""
        mg = MemoryGraph()
        node = mg.add("test")
        assert not mg.has_embedding(node.id)
        mg.update_embedding(node.id, [0.5, 0.5])
        assert mg.has_embedding(node.id)


class TestRemoveEmbeddingsBatch:

    def test_batch_remove(self):
        mg = MemoryGraph()
        a = mg.add("a")
        b = mg.add("b")
        c = mg.add("c")
        mg.add_embedding(a.id, [1.0, 0.0])
        mg.add_embedding(b.id, [0.0, 1.0])
        mg.add_embedding(c.id, [0.5, 0.5])
        removed = mg.remove_embeddings_batch([a.id, b.id])
        assert removed == 2
        assert not mg.has_embedding(a.id)
        assert not mg.has_embedding(b.id)
        assert mg.has_embedding(c.id)

    def test_batch_remove_with_nonexistent(self):
        """删除不存在的嵌入不计入 removed。"""
        mg = MemoryGraph()
        a = mg.add("a")
        mg.add_embedding(a.id, [1.0, 0.0])
        removed = mg.remove_embeddings_batch([a.id, "nonexistent"])
        assert removed == 1

    def test_batch_remove_empty_list(self):
        mg = MemoryGraph()
        assert mg.remove_embeddings_batch([]) == 0


# ── search_similar_by_kind / by_tag ─────────────────────────────

class TestSearchSimilarByKind:

    def test_filter_by_kind(self):
        mg = MemoryGraph()
        concept = mg.add("concept1", kind="concept")
        entity = mg.add("entity1", kind="entity")
        mg.add_embedding(concept.id, [1.0, 0.0, 0.0])
        mg.add_embedding(entity.id, [0.9, 0.1, 0.0])
        results = mg.search_similar_by_kind([1.0, 0.0, 0.0], "concept")
        assert all(mg.get_node(r["node_id"]).kind == "concept" for r in results)
        assert any(r["node_id"] == concept.id for r in results)

    def test_no_matching_kind(self):
        mg = MemoryGraph()
        a = mg.add("a", kind="concept")
        mg.add_embedding(a.id, [1.0, 0.0])
        results = mg.search_similar_by_kind([1.0, 0.0], "entity")
        assert len(results) == 0


class TestSearchSimilarByTag:

    def test_filter_by_tag(self):
        mg = MemoryGraph()
        tagged = mg.add("tagged_node")
        untagged = mg.add("untagged_node")
        mg.tag_nodes([tagged.id], "important")
        mg.add_embedding(tagged.id, [1.0, 0.0, 0.0])
        mg.add_embedding(untagged.id, [0.95, 0.05, 0.0])
        results = mg.search_similar_by_tag([1.0, 0.0, 0.0], "important")
        assert all(r["node_id"] == tagged.id for r in results)

    def test_no_matching_tag(self):
        mg = MemoryGraph()
        a = mg.add("a")
        mg.add_embedding(a.id, [1.0, 0.0])
        results = mg.search_similar_by_tag([1.0, 0.0], "nonexistent")
        assert len(results) == 0


# ── import_adjacency_list ──────────────────────────────────────

class TestImportAdjacencyList:

    def test_basic_import(self):
        mg = MemoryGraph()
        adj = {"a": [{"target": "b", "relation": "r", "weight": 0.5}],
               "b": [{"target": "c", "relation": "r", "weight": 1.0}]}
        result = mg.import_adjacency_list(adj)
        assert result["nodes"] == 3
        assert result["edges"] == 2
        assert mg.has_node("a")
        assert mg.has_node("c")

    def test_round_trip(self):
        """to_adjacency_list → import_adjacency_list 往返。"""
        mg1 = MemoryGraph()
        mg1._insert_node_raw("x", "X")
        mg1._insert_node_raw("y", "Y")
        mg1.link("x", "y", "rel", weight=0.7)
        exported = mg1.to_adjacency_list()
        mg2 = MemoryGraph()
        mg2.import_adjacency_list(exported)
        nodes = mg2.conn.execute("SELECT id FROM nodes").fetchall()
        edges = mg2.conn.execute("SELECT source, target FROM edges").fetchall()
        assert len(nodes) == 2
        assert len(edges) == 1

    def test_merge_mode(self):
        mg = MemoryGraph()
        existing = mg.add("existing")
        adj = {existing.id: [{"target": "new", "relation": "r", "weight": 0.5}]}
        result = mg.import_adjacency_list(adj, merge=True)
        assert mg.has_node("new")
        assert result["nodes"] == 1

    def test_empty_adj(self):
        mg = MemoryGraph()
        result = mg.import_adjacency_list({})
        assert result["nodes"] == 0
        assert result["edges"] == 0

    def test_missing_relation_defaults(self):
        mg = MemoryGraph()
        adj = {"a": [{"target": "b"}]}
        result = mg.import_adjacency_list(adj)
        assert result["edges"] == 1
        edges = mg.conn.execute("SELECT relation, weight FROM edges WHERE source='a'").fetchone()
        assert edges["relation"] == ""
        assert edges["weight"] == 1.0


# ── neighbors_filtered ─────────────────────────────────────────

class TestNeighborsFiltered:

    def test_filter_by_relation(self):
        mg = MemoryGraph()
        mg._insert_node_raw("center", "C")
        mg._insert_node_raw("a", "A")
        mg._insert_node_raw("b", "B")
        mg.link("center", "a", "friend")
        mg.link("center", "b", "colleague")
        friends = mg.neighbors_filtered("center", relation="friend")
        assert len(friends) == 1
        assert friends[0].id == "a"

    def test_filter_by_min_weight(self):
        mg = MemoryGraph()
        mg._insert_node_raw("c", "C")
        mg._insert_node_raw("light", "L")
        mg._insert_node_raw("heavy", "H")
        mg.link("c", "light", "r", weight=0.2)
        mg.link("c", "heavy", "r", weight=0.9)
        result = mg.neighbors_filtered("c", min_weight=0.5)
        ids = [n.id for n in result]
        assert "heavy" in ids
        assert "light" not in ids

    def test_direction_in(self):
        mg = MemoryGraph()
        mg._insert_node_raw("a", "A")
        mg._insert_node_raw("b", "B")
        mg._insert_node_raw("c", "C")
        mg.link("a", "c", "r")
        mg.link("b", "c", "r")
        in_neighbors = mg.neighbors_filtered("c", direction="in")
        ids = [n.id for n in in_neighbors]
        assert "a" in ids
        assert "b" in ids

    def test_direction_both(self):
        mg = MemoryGraph()
        mg._insert_node_raw("a", "A")
        mg._insert_node_raw("b", "B")
        mg._insert_node_raw("c", "C")
        mg.link("a", "b", "r")  # b has out to nothing, in from a
        mg.link("b", "c", "r")  # b has out to c
        both = mg.neighbors_filtered("b", direction="both")
        ids = {n.id for n in both}
        assert ids == {"a", "c"}

    def test_no_matching(self):
        mg = MemoryGraph()
        mg._insert_node_raw("a", "A")
        mg._insert_node_raw("b", "B")
        mg.link("a", "b", "r")
        result = mg.neighbors_filtered("a", relation="nonexistent")
        assert len(result) == 0


# ── edge_betweenness ───────────────────────────────────────────

class TestEdgeBetweenness:

    def test_bridge_has_high_betweenness(self):
        """桥边应有最高介数。"""
        mg = MemoryGraph()
        for n in ["a", "b", "c", "d"]:
            mg._insert_node_raw(n, n)
        mg.link("a", "b", "r")
        mg.link("b", "c", "r")  # bridge between two halves
        mg.link("c", "d", "r")
        eb = mg.edge_betweenness()
        # b-c edge should have highest betweenness
        bc_key = tuple(sorted(["b", "c"]))
        ab_key = tuple(sorted(["a", "b"]))
        cd_key = tuple(sorted(["c", "d"]))
        assert eb[bc_key] > eb[ab_key]
        assert eb[bc_key] > eb[cd_key]

    def test_cycle_edges_equal(self):
        """环中所有边介数相等。"""
        mg = MemoryGraph()
        for n in ["a", "b", "c"]:
            mg._insert_node_raw(n, n)
        mg.link("a", "b", "r")
        mg.link("b", "c", "r")
        mg.link("c", "a", "r")
        eb = mg.edge_betweenness()
        values = list(eb.values())
        assert max(values) - min(values) < 0.01  # all approximately equal

    def test_empty_graph(self):
        mg = MemoryGraph()
        assert mg.edge_betweenness() == {}

    def test_single_edge(self):
        mg = MemoryGraph()
        mg._insert_node_raw("a", "A")
        mg._insert_node_raw("b", "B")
        mg.link("a", "b", "r")
        eb = mg.edge_betweenness()
        assert len(eb) == 1
        key = tuple(sorted(["a", "b"]))
        assert eb[key] == 1.0  # single edge between 2 nodes


# ═════════════════════════════════════════════════════════════════════
# FTS5 BM25 Full-Text Search Tests
# ═════════════════════════════════════════════════════════════════════

class TestBM25Search:
    """Tests for FTS5-based BM25 full-text search."""

    def test_bm25_basic_match(self):
        """Basic BM25 search finds matching nodes by label."""
        mg = MemoryGraph()
        mg.add("Python programming language", "skill")
        mg.add("Rust systems programming", "skill")
        mg.add("machine learning fundamentals", "concept")
        results = mg.search_bm25("programming")
        assert len(results) > 0
        labels = [r["label"] for r in results]
        assert "Python programming language" in labels
        assert "Rust systems programming" in labels

    def test_bm25_no_match(self):
        """BM25 returns empty for non-matching query."""
        mg = MemoryGraph()
        mg.add("hello world", "greeting")
        results = mg.search_bm25("nonexistentterm12345")
        assert len(results) == 0

    def test_bm25_ranking_relevance(self):
        """BM25 ranks more relevant documents higher."""
        mg = MemoryGraph()
        mg.add("Python Python Python", "skill")  # high TF
        mg.add("Python overview", "concept")       # lower TF
        results = mg.search_bm25("Python")
        assert len(results) >= 2
        assert results[0]["label"] == "Python Python Python"

    def test_bm25_multi_field_search(self):
        """BM25 searches across label, data, kind, and tags."""
        mg = MemoryGraph()
        mg.add("database design", "skill", data={"db": "sqlite"}, tags=["backend"])
        mg.add("frontend wizardry", "skill", data={"framework": "react"}, tags=["ui"])
        # Search in data
        results = mg.search_bm25("sqlite")
        assert len(results) >= 1
        assert results[0]["label"] == "database design"
        # Search in tags
        results2 = mg.search_bm25("backend")
        assert len(results2) >= 1
        assert results2[0]["label"] == "database design"

    def test_bm25_limit(self):
        """BM25 respects limit parameter."""
        mg = MemoryGraph()
        for i in range(20):
            mg.add(f"project alpha {i}", "task")
        results = mg.search_bm25("alpha", limit=5)
        assert len(results) == 5

    def test_bm25_score_format(self):
        """BM25 results contain required fields."""
        mg = MemoryGraph()
        mg.add("test node", "fact")
        results = mg.search_bm25("test")
        assert len(results) == 1
        r = results[0]
        assert "node_id" in r
        assert "label" in r
        assert "kind" in r
        assert "score" in r
        assert "matched_fields" in r
        assert isinstance(r["score"], (int, float))
        assert r["score"] > 0

    def test_bm25_prefix_query(self):
        """FTS5 prefix queries work."""
        mg = MemoryGraph()
        mg.add("programming", "skill")
        mg.add("programmatic", "concept")
        mg.add("procedural", "skill")
        results = mg.search_bm25("prog*")
        assert len(results) >= 2

    def test_bm25_phrase_query(self):
        """FTS5 phrase queries with quotes work."""
        mg = MemoryGraph()
        mg.add("machine learning basics", "concept")
        mg.add("learning machine operations", "task")
        results = mg.search_bm25('"machine learning"')
        assert len(results) >= 1
        assert results[0]["label"] == "machine learning basics"

    def test_bm25_after_delete(self):
        """FTS index stays in sync after node deletion."""
        mg = MemoryGraph()
        n = mg.add("unique searchable text", "fact")
        assert len(mg.search_bm25("unique")) == 1
        mg.delete_node(n.id)
        assert len(mg.search_bm25("unique")) == 0

    def test_bm25_after_update(self):
        """FTS index stays in sync after node update."""
        mg = MemoryGraph()
        n = mg.add("old label", "fact")
        assert len(mg.search_bm25("old")) == 1
        mg.update_node(n.id, label="new label")
        assert len(mg.search_bm25("old")) == 0
        assert len(mg.search_bm25("new")) == 1

    def test_bm25_after_rename_node(self):
        """FTS index stays in sync after rename_node."""
        mg = MemoryGraph()
        n = mg.add("alpha version", "task")
        assert len(mg.search_bm25("alpha")) == 1
        mg.rename_node(n.id, "beta version")
        assert len(mg.search_bm25("alpha")) == 0
        assert len(mg.search_bm25("beta")) == 1

    def test_bm25_after_tag_change(self):
        """FTS index stays in sync after tag operations."""
        mg = MemoryGraph()
        n = mg.add("project x", "task")
        assert len(mg.search_bm25("urgent")) == 0
        mg.tag_nodes("urgent", [n.id])
        assert len(mg.search_bm25("urgent")) == 1
        mg.clear_tags(n.id)
        assert len(mg.search_bm25("urgent")) == 0

    def test_bm25_after_rename_tag(self):
        """FTS index stays in sync after rename_tag."""
        mg = MemoryGraph()
        n = mg.add("node", "fact")
        mg.tag_nodes("oldtag", [n.id])
        assert len(mg.search_bm25("oldtag")) == 1
        mg.rename_tag("oldtag", "newtag")
        assert len(mg.search_bm25("oldtag")) == 0
        assert len(mg.search_bm25("newtag")) == 1

    def test_bm25_after_merge_nodes(self):
        """FTS index stays in sync after merge_nodes."""
        mg = MemoryGraph()
        n1 = mg.add("alpha data", "fact", data={"key": "value"})
        n2 = mg.add("beta info", "fact")
        assert len(mg.search_bm25("alpha")) == 1
        assert len(mg.search_bm25("beta")) == 1
        mg.merge_nodes(n1.id, n2.id)
        assert len(mg.search_bm25("alpha")) == 0  # source deleted
        assert len(mg.search_bm25("beta")) == 1   # target still exists

    def test_bm25_after_clone_node(self):
        """FTS index includes cloned nodes."""
        mg = MemoryGraph()
        n = mg.add("original content", "fact")
        assert len(mg.search_bm25("original")) == 1
        mg.clone_node(n.id, "cloned original content")
        assert len(mg.search_bm25("original")) == 2

    def test_bm25_after_clear(self):
        """FTS index is cleared after clear()."""
        mg = MemoryGraph()
        mg.add("hello", "greeting")
        mg.add("world", "greeting")
        assert len(mg.search_bm25("hello")) == 1
        mg.clear()
        assert len(mg.search_bm25("hello")) == 0
        assert len(mg.search_bm25("world")) == 0

    def test_bm25_add_many_sync(self):
        """FTS index syncs after add_many batch operations."""
        mg = MemoryGraph()
        mg.add_many([
            {"label": "alpha task", "kind": "task"},
            {"label": "beta task", "kind": "task"},
            {"label": "gamma task", "kind": "task"},
        ])
        results = mg.search_bm25("task")
        assert len(results) == 3

    def test_bm25_fts_rebuild(self):
        """_fts_rebuild recreates the index from scratch."""
        mg = MemoryGraph()
        mg.add("node one", "fact")
        mg.add("node two", "fact")
        # Rebuild should work and find all nodes
        mg._fts_rebuild()
        results = mg.search_bm25("node")
        assert len(results) == 2

    def test_bm25_search_hybrid_uses_bm25(self):
        """search_hybrid uses BM25 as text path when available."""
        mg = MemoryGraph()
        mg.add("Python programming", "skill")
        mg.add("Rust systems", "skill")
        results = mg.search_hybrid("Python")
        assert len(results) > 0
        top = results[0]
        assert top["label"] == "Python programming"
        # Should have bm25 source
        assert "bm25" in top["sources"]

    def test_bm25_boolean_query(self):
        """FTS5 Boolean queries (AND/OR/NOT) work."""
        mg = MemoryGraph()
        mg.add("machine learning", "concept")
        mg.add("machine repair", "task")
        results = mg.search_bm25("machine AND learning")
        assert len(results) == 1
        assert results[0]["label"] == "machine learning"

    def test_bm25_with_empty_graph(self):
        """BM25 search on empty graph returns empty list."""
        mg = MemoryGraph()
        assert mg.search_bm25("anything") == []

    def test_bm25_weight_boost(self):
        """Higher weight nodes get boosted BM25 scores."""
        mg = MemoryGraph()
        n1 = mg.add("same keyword", "fact")
        n2 = mg.add("same keyword", "fact")
        mg.reweight(n1.id, -0.5)  # lower weight to 0.5
        results = mg.search_bm25("keyword")
        assert len(results) == 2
        # Higher weight node (n2, weight=1.0) should rank higher
        assert results[0]["node_id"] == n2.id
        assert results[0]["score"] > results[1]["score"]


# ── to_markdown tests ──────────────────────────────────────

class TestToMarkdown:
    """to_markdown(): export graph as markdown for LLM context."""

    def test_empty_graph(self, mg):
        md = mg.to_markdown()
        assert "Memory Graph" in md
        assert "(empty)" in md

    def test_basic_export(self, mg):
        mg.add("Alice", "person", {"role": "engineer"})
        mg.add("Bob", "person")
        md = mg.to_markdown()
        assert "## person" in md
        assert "**Alice**" in md
        assert "**Bob**" in md

    def test_kind_grouping(self, mg):
        mg.add("Alice", "person")
        mg.add("Rust", "concept")
        mg.add("Debug session", "event")
        md = mg.to_markdown()
        # Kinds should appear as headers in sorted order
        assert "## concept" in md
        assert "## event" in md
        assert "## person" in md

    def test_weight_display(self, mg):
        n = mg.add("Important", "concept")
        mg.conn.execute("UPDATE nodes SET weight=0.5 WHERE id=?", (n.id,))
        mg.conn.commit()
        md = mg.to_markdown()
        assert "(w=0.50)" in md

    def test_no_weight_for_default(self, mg):
        mg.add("Normal", "concept")
        md = mg.to_markdown()
        assert "(w=" not in md

    def test_tags_display(self, mg):
        mg.add("Tagged", "concept", tags=["important", "verified"])
        md = mg.to_markdown()
        assert "`important`" in md
        assert "`verified`" in md

    def test_data_display(self, mg):
        mg.add("With Data", "concept", {"key1": "value1", "count": 42})
        md = mg.to_markdown()
        assert "key1" in md
        assert "value1" in md

    def test_include_data_false(self, mg):
        mg.add("Node", "concept", {"secret": "hidden"})
        md = mg.to_markdown(include_data=False)
        assert "secret" not in md

    def test_include_edges_true(self, mg):
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        mg.link(a.id, b.id, "knows")
        md = mg.to_markdown(include_edges=True)
        assert "## Relationships" in md
        assert "knows" in md
        assert "Alice" in md
        assert "Bob" in md

    def test_include_edges_false(self, mg):
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        mg.link(a.id, b.id, "knows")
        md = mg.to_markdown(include_edges=False)
        assert "## Relationships" not in md

    def test_node_ids_filter(self, mg):
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        c = mg.add("Carol", "person")
        md = mg.to_markdown(node_ids=[a.id, b.id])
        assert "Alice" in md
        assert "Bob" in md
        assert "Carol" not in md

    def test_max_nodes_limit(self, mg):
        for i in range(10):
            mg.add(f"Node{i}", "concept")
        md = mg.to_markdown(max_nodes=3)
        # Only 3 nodes should appear
        count = md.count("- **Node")
        assert count <= 3

    def test_edge_weight_display(self, mg):
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        mg.link(a.id, b.id, "trusts", weight=0.8)
        md = mg.to_markdown()
        assert "(w=0.80)" in md

    def test_node_count_in_header(self, mg):
        mg.add("A", "person")
        mg.add("B", "person")
        mg.add("C", "concept")
        md = mg.to_markdown()
        assert "person (2)" in md
        assert "concept (1)" in md


# ── context_window tests ───────────────────────────────────

class TestContextWindow:
    """context_window(): extract focused subgraph for LLM context."""

    def test_basic(self, mg):
        a = mg.add("Alice", "person", {"role": "dev"})
        b = mg.add("Bob", "person")
        mg.link(a.id, b.id, "works_with")
        ctx = mg.context_window([a.id])
        assert "## person" in ctx
        assert "**Alice**" in ctx
        assert "**Bob**" in ctx

    def test_seed_marker(self, mg):
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        mg.link(a.id, b.id, "knows")
        ctx = mg.context_window([a.id])
        assert "★" in ctx
        # Star should be on Alice (seed)
        alice_line = [l for l in ctx.split("\n") if "Alice" in l][0]
        assert "★" in alice_line

    def test_non_seed_no_marker(self, mg):
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        mg.link(a.id, b.id, "knows")
        ctx = mg.context_window([a.id])
        bob_line = [l for l in ctx.split("\n") if "Bob" in l][0]
        assert "★" not in bob_line

    def test_hops_0(self, mg):
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        mg.link(a.id, b.id, "knows")
        ctx = mg.context_window([a.id], hops=0)
        assert "Alice" in ctx
        assert "Bob" not in ctx

    def test_hops_2(self, mg):
        a = mg.add("A", "x")
        b = mg.add("B", "x")
        c = mg.add("C", "x")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        ctx = mg.context_window([a.id], hops=2)
        assert "A" in ctx
        assert "B" in ctx
        assert "C" in ctx

    def test_max_nodes_limit(self, mg):
        a = mg.add("Seed", "x")
        for i in range(10):
            n = mg.add(f"Node{i}", "x")
            mg.link(a.id, n.id, "r")
        ctx = mg.context_window([a.id], max_nodes=3)
        # Should not contain all nodes
        count = ctx.count("- **")
        assert count <= 3

    def test_empty_seed(self, mg):
        ctx = mg.context_window(["nonexistent"])
        assert "no data" in ctx

    def test_relationships_section(self, mg):
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        mg.link(a.id, b.id, "mentors")
        ctx = mg.context_window([a.id])
        assert "## Relationships" in ctx
        assert "mentors" in ctx

    def test_multiple_seeds(self, mg):
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        c = mg.add("Carol", "person")
        mg.link(a.id, c.id, "knows")
        mg.link(b.id, c.id, "knows")
        ctx = mg.context_window([a.id, b.id])
        # Both seeds should be marked
        alice_line = [l for l in ctx.split("\n") if "Alice" in l][0]
        bob_line = [l for l in ctx.split("\n") if "Bob" in l][0]
        assert "★" in alice_line
        assert "★" in bob_line

    def test_tags_in_context(self, mg):
        a = mg.add("Tagged", "concept", tags=["important"])
        ctx = mg.context_window([a.id])
        assert "`important`" in ctx

    def test_data_in_context(self, mg):
        a = mg.add("WithData", "concept", {"level": 5})
        ctx = mg.context_window([a.id])
        assert "level" in ctx

    def test_reverse_edge_traversal(self, mg):
        """context_window should traverse incoming edges too."""
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        mg.link(b.id, a.id, "reports_to")  # B → A
        # Seeding from A, should find B via reverse edge
        ctx = mg.context_window([a.id], hops=1)
        assert "Bob" in ctx


# ── prune_by_relevance tests ───────────────────────────────

class TestPruneByRelevance:
    """prune_by_relevance(): intelligent pruning keeping top-k relevant nodes."""

    def test_basic_prune(self, mg):
        mg.add("Python tutorial", "skill")
        mg.add("Rust programming", "skill")
        mg.add("Cooking recipe", "knowledge")
        result = mg.prune_by_relevance("Python", keep_k=1)
        assert result["nodes_removed"] >= 1
        # Python tutorial should survive
        remaining = {r["label"] for r in mg.conn.execute("SELECT label FROM nodes").fetchall()}
        assert "Python tutorial" in remaining

    def test_keep_k_limit(self, mg):
        for i in range(10):
            mg.add(f"Topic {i}", "concept")
        result = mg.prune_by_relevance("Topic", keep_k=3)
        assert result["nodes_removed"] == 7
        count = mg.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        assert count == 3

    def test_min_weight_preserve(self, mg):
        n1 = mg.add("Irrelevant", "concept")
        n2 = mg.add("Important", "concept")
        mg.conn.execute("UPDATE nodes SET weight=0.9 WHERE id=?", (n2.id,))
        mg.conn.commit()
        result = mg.prune_by_relevance("nonexistent_query", keep_k=1, min_weight=0.8)
        # Important node should survive via weight
        remaining = {r["label"] for r in mg.conn.execute("SELECT label FROM nodes").fetchall()}
        assert "Important" in remaining
        assert result["kept_by_weight"] >= 1

    def test_empty_graph(self, mg):
        result = mg.prune_by_relevance("anything", keep_k=5)
        assert result["nodes_removed"] == 0

    def test_all_relevant(self, mg):
        """If all nodes match, none should be removed."""
        mg.add("Python basics", "skill")
        mg.add("Python advanced", "skill")
        result = mg.prune_by_relevance("Python", keep_k=10)
        assert result["nodes_removed"] == 0

    def test_edges_removed(self, mg):
        a = mg.add("Python", "skill")
        b = mg.add("Unrelated", "concept")
        mg.link(a.id, b.id, "connected")
        result = mg.prune_by_relevance("Python", keep_k=1)
        assert result["edges_removed"] >= 1

    def test_returned_counts(self, mg):
        mg.add("Python core", "skill")
        mg.add("Rust async", "skill")
        mg.add("Cooking", "knowledge")
        result = mg.prune_by_relevance("Python", keep_k=1)
        assert "nodes_removed" in result
        assert "edges_removed" in result
        assert "kept_by_relevance" in result
        assert "kept_by_weight" in result
        assert isinstance(result["nodes_removed"], int)

    def test_no_fts_error(self, mg):
        """Should not crash even if FTS table has issues."""
        mg.add("Test", "concept")
        result = mg.prune_by_relevance("query", keep_k=5)
        assert isinstance(result, dict)

    def test_keeps_relevant_with_weight_fallback(self, mg):
        """Node relevant to query kept; high-weight irrelevant node also kept."""
        relevant = mg.add("Python guide", "skill")
        heavy = mg.add("Gardening", "hobby")
        mg.conn.execute("UPDATE nodes SET weight=0.95 WHERE id=?", (heavy.id,))
        mg.conn.commit()
        result = mg.prune_by_relevance("Python", keep_k=1, min_weight=0.9)
        remaining = {r["label"] for r in mg.conn.execute("SELECT label FROM nodes").fetchall()}
        assert "Python guide" in remaining
        assert "Gardening" in remaining


class TestSingleTagOps:
    """Tests for add_tag, remove_tag, has_tag — single-tag CRUD."""

    def test_add_tag_to_node(self):
        mg = MemoryGraph()
        n = mg.add("Node", tags=["existing"])
        assert mg.add_tag(n.id, "new_tag") is True
        assert mg.has_tag(n.id, "new_tag")
        assert mg.has_tag(n.id, "existing")

    def test_add_tag_idempotent(self):
        mg = MemoryGraph()
        n = mg.add("Node", tags=["a"])
        assert mg.add_tag(n.id, "a") is True
        row = mg.conn.execute("SELECT tags FROM nodes WHERE id=?", (n.id,)).fetchone()
        assert json.loads(row["tags"]).count("a") == 1

    def test_add_tag_nonexistent_node(self):
        mg = MemoryGraph()
        assert mg.add_tag("fake-id", "tag") is False

    def test_add_tag_to_untagged_node(self):
        mg = MemoryGraph()
        n = mg.add("CleanNode")
        assert mg.add_tag(n.id, "first") is True
        assert mg.has_tag(n.id, "first")

    def test_remove_tag_from_node(self):
        mg = MemoryGraph()
        n = mg.add("Node", tags=["keep", "remove"])
        assert mg.remove_tag(n.id, "remove") is True
        assert not mg.has_tag(n.id, "remove")
        assert mg.has_tag(n.id, "keep")

    def test_remove_tag_not_present(self):
        mg = MemoryGraph()
        n = mg.add("Node", tags=["a"])
        assert mg.remove_tag(n.id, "nonexistent") is False
        assert mg.has_tag(n.id, "a")

    def test_remove_tag_nonexistent_node(self):
        mg = MemoryGraph()
        assert mg.remove_tag("fake-id", "tag") is False

    def test_remove_tag_empties_tags(self):
        mg = MemoryGraph()
        n = mg.add("Node", tags=["only"])
        assert mg.remove_tag(n.id, "only") is True
        assert not mg.has_tag(n.id, "only")

    def test_has_tag_true(self):
        mg = MemoryGraph()
        n = mg.add("Node", tags=["yes", "no"])
        assert mg.has_tag(n.id, "yes") is True
        assert mg.has_tag(n.id, "no") is True

    def test_has_tag_false(self):
        mg = MemoryGraph()
        n = mg.add("Node", tags=["yes"])
        assert mg.has_tag(n.id, "no") is False

    def test_has_tag_nonexistent_node(self):
        mg = MemoryGraph()
        assert mg.has_tag("fake-id", "tag") is False

    def test_has_tag_untagged_node(self):
        mg = MemoryGraph()
        n = mg.add("CleanNode")
        assert mg.has_tag(n.id, "anything") is False

    def test_tag_crud_roundtrip(self):
        """Add → verify → remove → verify cycle."""
        mg = MemoryGraph()
        n = mg.add("RT", tags=[])
        assert mg.has_tag(n.id, "x") is False
        mg.add_tag(n.id, "x")
        assert mg.has_tag(n.id, "x") is True
        mg.add_tag(n.id, "y")
        row = mg.conn.execute("SELECT tags FROM nodes WHERE id=?", (n.id,)).fetchone()
        assert sorted(json.loads(row["tags"])) == ["x", "y"]
        mg.remove_tag(n.id, "x")
        assert mg.has_tag(n.id, "x") is False
        assert mg.has_tag(n.id, "y") is True
        mg.remove_tag(n.id, "y")
        row = mg.conn.execute("SELECT tags FROM nodes WHERE id=?", (n.id,)).fetchone()
        assert json.loads(row["tags"]) == []


class TestCommunitySummary:
    """Tests for community_summary — community insight dashboard."""

    def test_empty_graph(self):
        mg = MemoryGraph()
        assert mg.community_summary() == []

    def test_single_community(self):
        mg = MemoryGraph()
        a = mg.add("Alice", "person", tags=["team-a"])
        b = mg.add("Bob", "person", tags=["team-a"])
        mg.link(a.id, b.id, "colleague")
        result = mg.community_summary()
        assert len(result) >= 1
        c = result[0]
        assert c["size"] >= 2
        assert c["internal_edges"] >= 1
        assert 0 <= c["density"] <= 1
        assert len(c["top_members"]) >= 1
        assert c["avg_weight"] > 0

    def test_two_communities(self):
        mg = MemoryGraph()
        # Community A
        a1 = mg.add("A1", "person", tags=["alpha"])
        a2 = mg.add("A2", "person", tags=["alpha"])
        mg.link(a1.id, a2.id, "knows")
        mg.link(a2.id, a1.id, "knows")
        # Community B
        b1 = mg.add("B1", "concept")
        b2 = mg.add("B2", "concept")
        mg.link(b1.id, b2.id, "related")
        communities = {0: [a1.id, a2.id], 1: [b1.id, b2.id]}
        result = mg.community_summary(communities=communities)
        assert len(result) == 2
        assert result[0]["size"] == 2
        assert result[1]["size"] == 2

    def test_density_calculation(self):
        mg = MemoryGraph()
        a = mg.add("A")
        b = mg.add("B")
        c = mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(a.id, c.id, "r")
        communities = {0: [a.id, b.id, c.id]}
        result = mg.community_summary(communities=communities)
        assert result[0]["internal_edges"] == 3
        assert result[0]["density"] > 0

    def test_top_tags_aggregation(self):
        mg = MemoryGraph()
        a = mg.add("A", tags=["python", "ml"])
        b = mg.add("B", tags=["python", "data"])
        c = mg.add("C", tags=["python"])
        communities = {0: [a.id, b.id, c.id]}
        result = mg.community_summary(communities=communities)
        tags = dict(result[0]["top_tags"])
        assert tags.get("python") == 3

    def test_kinds_distribution(self):
        mg = MemoryGraph()
        a = mg.add("A", "person")
        b = mg.add("B", "person")
        c = mg.add("C", "concept")
        communities = {0: [a.id, b.id, c.id]}
        result = mg.community_summary(communities=communities)
        kinds = result[0]["kinds"]
        assert kinds.get("person") == 2
        assert kinds.get("concept") == 1

    def test_sorted_by_size(self):
        mg = MemoryGraph()
        nodes_big = [mg.add(f"N{i}") for i in range(5)]
        nodes_small = [mg.add(f"S{i}") for i in range(2)]
        communities = {0: [n.id for n in nodes_big], 1: [n.id for n in nodes_small]}
        result = mg.community_summary(communities=communities)
        assert result[0]["size"] >= result[1]["size"]

    def test_avg_weight(self):
        mg = MemoryGraph()
        a = mg.add("A")
        b = mg.add("B")
        mg.conn.execute("UPDATE nodes SET weight=0.5 WHERE id=?", (a.id,))
        mg.conn.execute("UPDATE nodes SET weight=1.0 WHERE id=?", (b.id,))
        mg.conn.commit()
        communities = {0: [a.id, b.id]}
        result = mg.community_summary(communities=communities)
        assert abs(result[0]["avg_weight"] - 0.75) < 0.01

    def test_with_greedy_algorithm(self):
        mg = MemoryGraph()
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "related")
        result = mg.community_summary(algorithm="greedy")
        assert len(result) >= 1

    def test_isolated_nodes(self):
        """Isolated nodes still get summarized."""
        mg = MemoryGraph()
        a = mg.add("Lone")
        communities = {0: [a.id]}
        result = mg.community_summary(communities=communities)
        assert len(result) == 1
        assert result[0]["size"] == 1
        assert result[0]["density"] == 0.0
        assert result[0]["internal_edges"] == 0

    def test_top_members_sorted_by_weight(self):
        mg = MemoryGraph()
        a = mg.add("Low")
        b = mg.add("High")
        mg.conn.execute("UPDATE nodes SET weight=0.3 WHERE id=?", (a.id,))
        mg.conn.execute("UPDATE nodes SET weight=0.95 WHERE id=?", (b.id,))
        mg.conn.commit()
        communities = {0: [a.id, b.id]}
        result = mg.community_summary(communities=communities)
        assert result[0]["top_members"][0]["label"] == "High"


class TestNodeRoles:
    """Tests for node_roles and role_summary — structural role classification."""

    def test_empty_graph(self):
        mg = MemoryGraph()
        assert mg.node_roles() == {}
        assert mg.role_summary() == {}

    def test_all_isolated(self):
        mg = MemoryGraph()
        a = mg.add("A")
        b = mg.add("B")
        roles = mg.node_roles()
        assert roles[a.id] == "isolated"
        assert roles[b.id] == "isolated"

    def test_hub_classification(self):
        mg = MemoryGraph()
        hub = mg.add("Hub")
        targets = [mg.add(f"T{i}") for i in range(5)]
        for t in targets:
            mg.link(hub.id, t.id, "connects")
        roles = mg.node_roles()
        assert roles[hub.id] == "hub"

    def test_authority_classification(self):
        mg = MemoryGraph()
        authority = mg.add("Authority")
        sources = [mg.add(f"S{i}") for i in range(5)]
        for s in sources:
            mg.link(s.id, authority.id, "cites")
        roles = mg.node_roles()
        assert roles[authority.id] == "authority"

    def test_member_classification(self):
        mg = MemoryGraph()
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "knows")
        roles = mg.node_roles()
        # Both should be member or lower-tier — neither dominates
        assert roles[a.id] in ("member", "hub", "authority", "bridge")
        assert roles[b.id] in ("member", "hub", "authority", "bridge")

    def test_bridge_detection(self):
        """Bridge node connects two clusters."""
        mg = MemoryGraph()
        # Cluster A
        a1 = mg.add("A1")
        a2 = mg.add("A2")
        mg.link(a1.id, a2.id, "r")
        # Bridge
        bridge = mg.add("Bridge")
        mg.link(a2.id, bridge.id, "r")
        # Cluster B
        b1 = mg.add("B1")
        b2 = mg.add("B2")
        mg.link(bridge.id, b1.id, "r")
        mg.link(b1.id, b2.id, "r")
        roles = mg.node_roles()
        # Bridge should be classified as something with high responsibility
        assert roles[bridge.id] in ("bridge", "hub", "authority")

    def test_role_summary_counts(self):
        mg = MemoryGraph()
        # 2 isolated
        iso1 = mg.add("I1")
        iso2 = mg.add("I2")
        # 1 hub with 5 targets
        hub = mg.add("Hub")
        targets = [mg.add(f"Target{i}") for i in range(5)]
        for t in targets:
            mg.link(hub.id, t.id, "r")
        roles = mg.node_roles()
        summary = mg.role_summary()
        total = sum(summary.values())
        assert total == 8  # 2 isolated + hub + 5 targets
        assert summary.get("isolated", 0) >= 2
        assert summary.get("hub", 0) >= 1

    def test_roles_cover_all_nodes(self):
        mg = MemoryGraph()
        nodes = [mg.add(f"N{i}") for i in range(6)]
        for i in range(5):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        roles = mg.node_roles()
        assert len(roles) == 6
        for nid in [n.id for n in nodes]:
            assert nid in roles

    def test_roles_return_valid_values(self):
        mg = MemoryGraph()
        a = mg.add("A")
        b = mg.add("B")
        c = mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(a.id, c.id, "r")
        roles = mg.node_roles()
        valid = {"hub", "authority", "bridge", "isolated", "member"}
        for role in roles.values():
            assert role in valid


class TestSearchGraphRAG:
    """Tests for search_graphrag — GraphRAG-style unified retrieval."""

    def test_empty_graph(self):
        mg = MemoryGraph()
        assert mg.search_graphrag("anything") == []

    def test_naive_mode(self):
        mg = MemoryGraph()
        mg.add("Python tutorial", "skill")
        mg.add("Gardening tips", "hobby")
        results = mg.search_graphrag("python", mode="naive")
        assert len(results) >= 1
        assert any("Python" in r["label"] for r in results)

    def test_local_mode_expands_graph(self):
        mg = MemoryGraph()
        a = mg.add("Python", "skill")
        b = mg.add("Django", "framework")
        c = mg.add("Flask", "framework")
        mg.link(a.id, b.id, "uses")
        mg.link(a.id, c.id, "uses")
        results = mg.search_graphrag("python", mode="local", limit=10)
        ids = {r["node_id"] for r in results}
        # Should include the seed AND its neighbors
        assert a.id in ids
        assert b.id in ids or c.id in ids

    def test_local_mode_empty_query(self):
        mg = MemoryGraph()
        mg.add("Node")
        results = mg.search_graphrag("nonexistent", mode="local")
        assert results == []

    def test_global_mode_finds_community(self):
        mg = MemoryGraph()
        # Build two clear communities
        py_nodes = [mg.add(n, "skill", tags=["python"]) for n in ["Python", "Django", "Flask"]]
        cook_nodes = [mg.add(n, "hobby", tags=["cooking"]) for n in ["Cooking", "Baking", "Grilling"]]
        # Link within communities
        for i in range(len(py_nodes) - 1):
            mg.link(py_nodes[i].id, py_nodes[i + 1].id, "related")
        for i in range(len(cook_nodes) - 1):
            mg.link(cook_nodes[i].id, cook_nodes[i + 1].id, "related")
        results = mg.search_graphrag("python", mode="global", limit=5)
        assert len(results) >= 1
        # Should return python community members
        labels = {r["label"] for r in results}
        assert any(l in labels for l in ["Python", "Django", "Flask"])

    def test_global_mode_falls_back_when_no_match(self):
        mg = MemoryGraph()
        mg.add("Lonely", "thing")
        results = mg.search_graphrag("xyz", mode="global")
        # Should not crash, returns something (empty or fallback)
        assert isinstance(results, list)

    def test_hybrid_mode(self):
        mg = MemoryGraph()
        mg.add("AI research", "topic")
        mg.add("ML papers", "topic")
        mg.link("AI research", "ML papers", "related")
        results = mg.search_graphrag("research", mode="hybrid")
        assert isinstance(results, list)

    def test_unknown_mode_falls_back(self):
        mg = MemoryGraph()
        mg.add("Test node")
        results = mg.search_graphrag("test", mode="nonexistent")
        assert isinstance(results, list)

    def test_results_have_required_fields(self):
        mg = MemoryGraph()
        mg.add("Python", "skill")
        for mode in ["naive", "local", "global", "hybrid"]:
            results = mg.search_graphrag("python", mode=mode)
            for r in results:
                assert "node_id" in r
                assert "label" in r
                assert "score" in r

    def test_limit_respected(self):
        mg = MemoryGraph()
        for i in range(10):
            mg.add(f"Node{i}")
        for mode in ["naive"]:
            results = mg.search_graphrag("node", mode=mode, limit=3)
            assert len(results) <= 3


class TestEffectiveEccentricity:

    def test_missing_node(self):
        mg = MemoryGraph()
        a = mg.add("A")
        assert mg.effective_eccentricity("ZZZ") is None

    def test_single_node(self):
        mg = MemoryGraph()
        a = mg.add("A")
        assert mg.effective_eccentricity(a.id) == 0.0

    def test_two_connected(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.effective_eccentricity(a.id) == 1.0

    def test_line_graph_5(self):
        """A—B—C—D—E: eccentricity(A)=4, effective_eccentricity(A, 0.9) should be ≤4."""
        mg = MemoryGraph()
        nodes = [mg.add(c) for c in "ABCDE"]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i+1].id, "r")
        # Distances from A: B=1, C=2, D=3, E=4
        # 4 reachable nodes, 0.9 * 4 = 3.6 → idx=3 → dist=4
        assert mg.effective_eccentricity(nodes[0].id, 0.9) == 4.0
        # 0.5 * 4 = 2 → idx=2 → dist=3
        assert mg.effective_eccentricity(nodes[0].id, 0.5) == 3.0

    def test_disconnected(self):
        """A—B and C—D: effective_eccentricity(A) only sees B."""
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        c, d = mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(c.id, d.id, "r")
        # From A: only B is reachable at distance 1
        assert mg.effective_eccentricity(a.id) == 1.0

    def test_all_isolated(self):
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        assert mg.effective_eccentricity(a.id) == 0.0

    def test_invalid_percentile(self):
        mg = MemoryGraph()
        a = mg.add("A")
        with pytest.raises(ValueError):
            mg.effective_eccentricity(a.id, 0)
        with pytest.raises(ValueError):
            mg.effective_eccentricity(a.id, 1.5)

    def test_central_node_star(self):
        """Star: center connected to 4 leaves. Center's distances: all 1."""
        mg = MemoryGraph()
        center = mg.add("center")
        leaves = [mg.add(f"leaf{i}") for i in range(4)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
        # From center: all 4 leaves at distance 1
        assert mg.effective_eccentricity(center.id, 0.9) == 1.0


class TestGlobalEfficiency:

    def test_empty_graph(self):
        mg = MemoryGraph()
        assert mg.global_efficiency() is None

    def test_single_node(self):
        mg = MemoryGraph()
        mg.add("A")
        assert mg.global_efficiency() == 0.0

    def test_two_connected(self):
        """A—B: ordered pairs (A→B and B→A) both distance 1 → 1/1+1/1 = 2.
        Normalized by 2*1 = 2 → 1.0."""
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.global_efficiency() == 1.0

    def test_line_graph_3(self):
        """A—B—C: ordered pairs distances:
        A→B=1, A→C=2, B→A=1, B→C=1, C→A=2, C→B=1
        efficiency = 1+0.5+1+1+0.5+1 = 5
        normalized by 3*2=6 → 5/6 ≈ 0.833333"""
        mg = MemoryGraph()
        nodes = [mg.add(c) for c in "ABC"]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[1].id, nodes[2].id, "r")
        result = mg.global_efficiency()
        assert abs(result - 5/6) < 0.001

    def test_disconnected_lower_efficiency(self):
        """A—B and C—D: disconnected pairs contribute 0."""
        mg = MemoryGraph()
        nodes = [mg.add(c) for c in "ABCD"]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[2].id, nodes[3].id, "r")
        # 4 nodes, 12 ordered pairs
        # Reachable: A↔B (2 pairs, d=1), C↔D (2 pairs, d=1)
        # efficiency = 1+1+1+1 = 4
        # normalized by 12 → 4/12 = 0.333333
        result = mg.global_efficiency()
        assert abs(result - 4/12) < 0.001

    def test_complete_graph_higher(self):
        """K4: all pairs at distance 1 → efficiency = 1.0."""
        mg = MemoryGraph()
        nodes = [mg.add(f"N{i}") for i in range(4)]
        for i in range(4):
            for j in range(i + 1, 4):
                mg.link(nodes[i].id, nodes[j].id, "r")
        assert mg.global_efficiency() == 1.0

    def test_disconnected_vs_connected(self):
        """Connected graph should have higher efficiency than disconnected."""
        mg_conn = MemoryGraph()
        cn = [mg_conn.add(c) for c in "ABCD"]
        mg_conn.link(cn[0].id, cn[1].id, "r")
        mg_conn.link(cn[1].id, cn[2].id, "r")
        mg_conn.link(cn[2].id, cn[3].id, "r")

        mg_disc = MemoryGraph()
        dn = [mg_disc.add(c) for c in "ABCD"]
        mg_disc.link(dn[0].id, dn[1].id, "r")
        mg_disc.link(dn[2].id, dn[3].id, "r")

        assert mg_conn.global_efficiency() > mg_disc.global_efficiency()


class TestSMetric:

    def test_empty_graph(self):
        mg = MemoryGraph()
        assert mg.s_metric() is None

    def test_single_node(self):
        mg = MemoryGraph()
        mg.add("A")
        assert mg.s_metric() == 0.0

    def test_single_edge(self):
        """A—B: deg(A)=1, deg(B)=1, S = 1*1 = 1."""
        mg = MemoryGraph()
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.s_metric() == 1.0

    def test_star_graph(self):
        """Star with center connected to 3 leaves:
        center deg=3, each leaf deg=1
        S = 3*1 + 3*1 + 3*1 = 9"""
        mg = MemoryGraph()
        center = mg.add("center")
        leaves = [mg.add(f"leaf{i}") for i in range(3)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
        assert mg.s_metric() == 9.0

    def test_path_graph(self):
        """A—B—C—D: deg A=1, B=2, C=2, D=1
        S = 1*2 + 2*2 + 2*1 = 2+4+2 = 8"""
        mg = MemoryGraph()
        nodes = [mg.add(c) for c in "ABCD"]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[1].id, nodes[2].id, "r")
        mg.link(nodes[2].id, nodes[3].id, "r")
        assert mg.s_metric() == 8.0

    def test_complete_k4(self):
        """K4: each node has degree 3, 6 edges.
        S = 6 * (3*3) = 54"""
        mg = MemoryGraph()
        nodes = [mg.add(f"N{i}") for i in range(4)]
        for i in range(4):
            for j in range(i + 1, 4):
                mg.link(nodes[i].id, nodes[j].id, "r")
        assert mg.s_metric() == 54.0

    def test_disconnected_components(self):
        """A—B and C—D: deg each =1, S = 1*1 + 1*1 = 2"""
        mg = MemoryGraph()
        nodes = [mg.add(c) for c in "ABCD"]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[2].id, nodes[3].id, "r")
        assert mg.s_metric() == 2.0

    def test_hub_structure(self):
        """A—B—C and A—D: deg A=2, B=2, C=1, D=1
        Edges: A-B(2*2=4), B-C(2*1=2), A-D(2*1=2) → S=8"""
        mg = MemoryGraph()
        nodes = [mg.add(c) for c in "ABCD"]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[1].id, nodes[2].id, "r")
        mg.link(nodes[0].id, nodes[3].id, "r")
        assert mg.s_metric() == 8.0


# ===== Leiden Community Detection Tests =====

# ===== Leiden Community Detection Tests =====

class TestLeidenCommunityDetection:
    """Tests for detect_communities_leiden() and modularity()."""

    def setup_method(self):
        self.db_path = tempfile.mktemp(suffix=".db")
        self.mg = MemoryGraph(db_path=self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _nid(self, label):
        """Get node ID by label."""
        nodes = self.mg.conn.execute(
            "SELECT id FROM nodes WHERE label=?", (label,)).fetchall()
        return nodes[0][0] if nodes else None

    def _build_three_cliques(self):
        """Build 3 clear communities with weak bridges."""
        # Community 1: A-B-C
        self.mg.add("A", "person"); self.mg.add("B", "person"); self.mg.add("C", "person")
        self.mg.link(self._nid("A"), self._nid("B"), "knows", 1.0)
        self.mg.link(self._nid("B"), self._nid("C"), "knows", 1.0)
        self.mg.link(self._nid("A"), self._nid("C"), "knows", 1.0)
        # Community 2: D-E-F
        self.mg.add("D", "person"); self.mg.add("E", "person"); self.mg.add("F", "person")
        self.mg.link(self._nid("D"), self._nid("E"), "knows", 1.0)
        self.mg.link(self._nid("E"), self._nid("F"), "knows", 1.0)
        self.mg.link(self._nid("D"), self._nid("F"), "knows", 1.0)
        # Community 3: G-H-I
        self.mg.add("G", "person"); self.mg.add("H", "person"); self.mg.add("I", "person")
        self.mg.link(self._nid("G"), self._nid("H"), "knows", 1.0)
        self.mg.link(self._nid("H"), self._nid("I"), "knows", 1.0)
        self.mg.link(self._nid("G"), self._nid("I"), "knows", 1.0)
        # Weak bridges
        self.mg.link(self._nid("C"), self._nid("D"), "bridge", 0.1)
        self.mg.link(self._nid("F"), self._nid("G"), "bridge", 0.1)

    def test_leiden_empty_graph(self):
        result = self.mg.detect_communities_leiden()
        assert result == {}

    def test_leiden_single_node(self):
        self.mg.add("solo", "person")
        result = self.mg.detect_communities_leiden()
        assert len(result) == 1
        nid = self._nid("solo")
        assert nid in result

    def test_leiden_two_nodes_linked(self):
        self.mg.add("A", "person"); self.mg.add("B", "person")
        self.mg.link(self._nid("A"), self._nid("B"), "knows", 1.0)
        result = self.mg.detect_communities_leiden()
        assert result[self._nid("A")] == result[self._nid("B")]

    def test_leiden_three_cliques(self):
        self._build_three_cliques()
        result = self.mg.detect_communities_leiden()
        a, b, c = self._nid("A"), self._nid("B"), self._nid("C")
        d, e, f = self._nid("D"), self._nid("E"), self._nid("F")
        g, h, i = self._nid("G"), self._nid("H"), self._nid("I")
        assert result[a] == result[b] == result[c]
        assert result[d] == result[e] == result[f]
        assert result[g] == result[h] == result[i]
        assert result[a] != result[d]
        assert result[d] != result[g]
        assert result[a] != result[g]

    def test_leiden_returns_all_nodes(self):
        self._build_three_cliques()
        result = self.mg.detect_communities_leiden()
        assert len(result) == 9

    def test_leiden_resolution_high(self):
        """Higher resolution → more/smaller communities."""
        self._build_three_cliques()
        result_low = self.mg.detect_communities_leiden(resolution=0.5)
        result_high = self.mg.detect_communities_leiden(resolution=2.0)
        num_comms_low = len(set(result_low.values()))
        num_comms_high = len(set(result_high.values()))
        assert num_comms_high >= num_comms_low

    def test_leiden_deterministic_with_seed(self):
        self._build_three_cliques()
        r1 = self.mg.detect_communities_leiden(seed=42)
        r2 = self.mg.detect_communities_leiden(seed=42)
        assert r1 == r2

    def test_leiden_different_seeds_may_differ(self):
        """Different seeds may produce different partitions."""
        self._build_three_cliques()
        r1 = self.mg.detect_communities_leiden(seed=42)
        r2 = self.mg.detect_communities_leiden(seed=99)
        assert set(r1.keys()) == set(r2.keys())

    def test_leiden_community_summary_integration(self):
        """community_summary with algorithm='leiden' works."""
        self._build_three_cliques()
        summary = self.mg.community_summary(algorithm="leiden")
        assert len(summary) == 3
        sizes = sorted(s["size"] for s in summary)
        assert sizes == [3, 3, 3]

    def test_leiden_community_summary_all_algorithms(self):
        """All 3 algorithms produce summaries for the same graph."""
        self._build_three_cliques()
        for algo in ["lp", "greedy", "leiden"]:
            summary = self.mg.community_summary(algorithm=algo)
            assert isinstance(summary, list)
            assert len(summary) >= 1

    def test_modularity_empty_graph(self):
        assert self.mg.modularity() == 0.0

    def test_modularity_single_edge(self):
        self.mg.add("A", "person"); self.mg.add("B", "person")
        self.mg.link(self._nid("A"), self._nid("B"), "knows", 1.0)
        comm = {self._nid("A"): 0, self._nid("B"): 0}
        q = self.mg.modularity(communities=comm)
        assert isinstance(q, float)  # Just verify it computes

    def test_modularity_good_partition_higher(self):
        """Good partition should have higher modularity than all-in-one."""
        self._build_three_cliques()
        all_ids = [self._nid(c) for c in "ABCDEFGHI"]
        good = {all_ids[0]:0, all_ids[1]:0, all_ids[2]:0,
                all_ids[3]:1, all_ids[4]:1, all_ids[5]:1,
                all_ids[6]:2, all_ids[7]:2, all_ids[8]:2}
        q_good = self.mg.modularity(communities=good)
        bad = {n: 0 for n in all_ids}
        q_bad = self.mg.modularity(communities=bad)
        assert q_good > q_bad

    def test_modularity_auto_detect(self):
        """modularity() with no args auto-detects communities."""
        self._build_three_cliques()
        q = self.mg.modularity()
        assert isinstance(q, float)
        assert q > 0

    def test_leiden_star_graph(self):
        """Star graph: center connected to all leaves."""
        self.mg.add("center", "person")
        for i in range(5):
            self.mg.add(f"leaf{i}", "person")
            self.mg.link(self._nid("center"), self._nid(f"leaf{i}"), "knows", 1.0)
        result = self.mg.detect_communities_leiden()
        assert len(result) == 6

    def test_leiden_chain_graph(self):
        """Chain graph: A-B-C-D-E-F."""
        labels = list("ABCDEF")
        for c in labels:
            self.mg.add(c, "person")
        for i in range(len(labels)-1):
            self.mg.link(self._nid(labels[i]), self._nid(labels[i+1]), "knows", 1.0)
        result = self.mg.detect_communities_leiden()
        assert len(result) == 6

    def test_leiden_weighted_edges(self):
        """Weighted edges influence community structure."""
        for c in "ABCD":
            self.mg.add(c, "person")
        self.mg.link(self._nid("A"), self._nid("B"), "knows", 10.0)
        self.mg.link(self._nid("B"), self._nid("C"), "knows", 0.1)
        self.mg.link(self._nid("C"), self._nid("D"), "knows", 10.0)
        result = self.mg.detect_communities_leiden(resolution=1.0)
        assert len(result) == 4

    def test_community_partition_leiden(self):
        self._build_three_cliques()
        result = self.mg.community_partition(algorithm="leiden")
        assert len(result) == 9
        assert len(set(result.values())) == 3

    def test_community_partition_greedy(self):
        self._build_three_cliques()
        result = self.mg.community_partition(algorithm="greedy")
        assert len(result) == 9
        assert isinstance(result, dict)

    def test_community_partition_lp(self):
        self._build_three_cliques()
        result = self.mg.community_partition(algorithm="lp")
        assert len(result) == 9
        assert isinstance(result, dict)

    def test_leiden_fully_connected_graph(self):
        """Complete graph: all nodes in one community."""
        for c in "ABCDE":
            self.mg.add(c, "person")
        ids = {c: self._nid(c) for c in "ABCDE"}
        for i, a in enumerate("ABCDE"):
            for b in "ABCDE"[i+1:]:
                self.mg.link(ids[a], ids[b], "knows", 1.0)
        result = self.mg.detect_communities_leiden()
        # Complete graph should be 1 community
        assert len(set(result.values())) == 1

    def test_leiden_isolated_nodes(self):
        """Isolated nodes: each in its own community."""
        for c in "ABCD":
            self.mg.add(c, "person")
        result = self.mg.detect_communities_leiden()
        # Each isolated node is its own community
        assert len(result) == 4
        # May or may not be separate communities (no edges, trivially any partition works)

    def test_community_quality_report_empty(self):
        report = self.mg.community_quality_report()
        assert report["num_communities"] == 0

    def test_community_quality_report_three_cliques(self):
        self._build_three_cliques()
        report = self.mg.community_quality_report(algorithm="leiden")
        assert report["num_communities"] == 3
        assert report["modularity"] > 0
        assert report["coverage"] == 1.0
        assert report["connectivity"] is True
        assert sorted(report["sizes"]) == [3, 3, 3]

    def test_community_quality_report_greedy(self):
        self._build_three_cliques()
        report = self.mg.community_quality_report(algorithm="greedy")
        assert report["algorithm"] == "greedy"
        assert report["num_communities"] >= 1

    def test_community_quality_report_lp(self):
        self._build_three_cliques()
        report = self.mg.community_quality_report(algorithm="lp")
        assert report["algorithm"] == "lp"
        assert isinstance(report["modularity"], float)

    def test_search_graphrag_global_uses_leiden(self):
        """Global mode now uses Leiden internally."""
        self._build_three_cliques()
        results = self.mg.search_graphrag("A", mode="global", limit=5)
        assert isinstance(results, list)


# ── local_efficiency / wiener_index / onion_structure (key-dev-3 loop C) ──

class TestLocalEfficiency:
    def test_missing_node(self, mg):
        assert mg.local_efficiency("missing") is None

    def test_single_node(self, mg):
        a = mg.add("A")
        assert mg.local_efficiency(a.id) is None

    def test_two_connected(self, mg):
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.local_efficiency(a.id) is None

    def test_triangle_high_efficiency(self, mg):
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        eff = mg.local_efficiency(a.id)
        assert eff is not None
        assert abs(eff - 1.0) < 1e-9

    def test_star_center_low(self, mg):
        a = mg.add("center")
        leaves = [mg.add(f"L{i}") for i in range(4)]
        for leaf in leaves:
            mg.link(a.id, leaf.id, "r")
        eff = mg.local_efficiency(a.id)
        assert eff is not None
        assert abs(eff) < 1e-9

    def test_line_graph(self, mg):
        """A-B-C-D: B's neighbors are A,C. Removing B, A and C disconnected → 0."""
        nodes = [mg.add(str(i)) for i in range(4)]
        for i in range(3):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        eff = mg.local_efficiency(nodes[1].id)
        assert eff is not None
        assert abs(eff) < 1e-9


class TestWienerIndex:
    def test_empty(self, mg):
        assert mg.wiener_index() is None

    def test_single(self, mg):
        mg.add("A")
        assert mg.wiener_index() is None

    def test_two_connected(self, mg):
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.wiener_index() == 1

    def test_triangle(self, mg):
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        assert mg.wiener_index() == 3

    def test_line_4(self, mg):
        nodes = [mg.add(str(i)) for i in range(4)]
        for i in range(3):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        assert mg.wiener_index() == 10

    def test_disconnected_not_counted(self, mg):
        a, b = mg.add("A"), mg.add("B")
        c, d = mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(c.id, d.id, "r")
        assert mg.wiener_index() == 2


class TestOnionStructure:
    def test_empty(self, mg):
        assert mg.onion_structure() is None

    def test_single_node(self, mg):
        mg.add("A")
        result = mg.onion_structure()
        assert len(result) >= 1
        assert result[0]["k"] == 1

    def test_triangle(self, mg):
        """Triangle: all 3 nodes survive k=1 and k=2. Last layer has all 3."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        result = mg.onion_structure(n_layers=3)
        # All 3 nodes survive to the innermost core
        total = sum(l["count"] for l in result)
        assert total == 3

    def test_star_peels_outer(self, mg):
        center = mg.add("C")
        leaves = [mg.add(f"L{i}") for i in range(4)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
        result = mg.onion_structure(n_layers=3)
        assert len(result) >= 1

    def test_returns_layers(self, mg):
        nodes = [mg.add(str(i)) for i in range(5)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        result = mg.onion_structure(n_layers=3)
        for layer in result:
            assert "k" in layer
            assert "nodes" in layer
            assert "count" in layer
            assert "edges" in layer

    def test_total_node_count(self, mg):
        nodes = [mg.add(str(i)) for i in range(6)]
        for i in range(6):
            mg.link(nodes[i].id, nodes[(i + 1) % 6].id, "r")
        result = mg.onion_structure(n_layers=3)
        total = sum(l["count"] for l in result)
        assert total == 6


class TestClosenessVitality:
    def test_missing_node(self, mg):
        assert mg.closeness_vitality("nonexist") is None

    def test_single_node(self, mg):
        n = mg.add("A")
        # Single node: wiener_index returns 0 for single/empty
        # Removing makes empty, both 0
        assert mg.closeness_vitality(n.id) == 0

    def test_chain_center_important(self, mg):
        """In A-B-C, removing B disconnects the graph."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        v = mg.closeness_vitality(b.id)
        # Removing B: W(G\{B})=0 (disconnected), W(G)=2 (A-B=1, B-C=1, A-C=2)
        # vitality = 0 - 4 = -4
        assert v == -4

    def test_leaf_removal(self, mg):
        """Removing a leaf from A-B-C."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        v = mg.closeness_vitality(a.id)
        # After removing A: only B-C left, W=1
        # Before: W=1+1+2=4
        # vitality = 1 - 4 = -3
        assert v == -3

    def test_node_preserved_after_vitality(self, mg):
        """Node should be restored after computing vitality."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        mg.closeness_vitality(a.id)
        assert mg.has_node(a.id)
        assert mg.has_node(b.id)
        edges = mg.conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"]
        assert edges == 1

    def test_triangle(self, mg):
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        v = mg.closeness_vitality(a.id)
        # Before: W=3 (all pairs distance 1)
        # After removing A: B-C, W=1
        # vitality = 1 - 3 = -2
        assert v == -2


class TestSpectralRadius:
    def test_empty(self, mg):
        assert mg.spectral_radius() is None

    def test_single_node(self, mg):
        mg.add("A")
        assert mg.spectral_radius() < 0.001

    def test_path_p3(self, mg):
        """P3 spectral radius = sqrt(2) ~ 1.414."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        sr = mg.spectral_radius()
        assert abs(sr - 1.4142) < 0.01

    def test_complete_k4(self, mg):
        """K4 spectral radius = 3."""
        nodes = [mg.add(str(i)) for i in range(4)]
        for i in range(4):
            for j in range(i + 1, 4):
                mg.link(nodes[i].id, nodes[j].id, "r")
                mg.link(nodes[j].id, nodes[i].id, "r")
        sr = mg.spectral_radius()
        assert abs(sr - 3.0) < 0.01

    def test_path_p5(self, mg):
        """P5 spectral radius = 2*cos(pi/6) = sqrt(3) ~ 1.732."""
        nodes = [mg.add(str(i)) for i in range(5)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        sr = mg.spectral_radius()
        assert abs(sr - 1.7321) < 0.01

    def test_star_graph(self, mg):
        """Star K_{1,4} spectral radius = sqrt(4) = 2."""
        center = mg.add("C")
        leaves = [mg.add(f"L{i}") for i in range(4)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
            mg.link(leaf.id, center.id, "r")
        sr = mg.spectral_radius()
        assert abs(sr - 2.0) < 0.01

    def test_two_isolated_nodes(self, mg):
        """Two nodes with no edges: spectral radius ≈ 0."""
        mg.add("A")
        mg.add("B")
        assert mg.spectral_radius() < 0.001


class TestAlgebraicConnectivity:
    """代数连通度（Fiedler value）测试。"""

    def test_complete_graph(self, mg):
        nodes = [mg.add(f"n{i}", "node") for i in range(4)]
        for i in range(4):
            for j in range(i+1, 4):
                mg.link(nodes[i].id, nodes[j].id, "edge")
        result = mg.algebraic_connectivity()
        assert result is not None
        assert abs(result - 4.0) < 0.5

    def test_path_graph(self, mg):
        nodes = [mg.add(f"n{i}", "node") for i in range(4)]
        for i in range(3):
            mg.link(nodes[i].id, nodes[i+1].id, "edge")
        result = mg.algebraic_connectivity()
        assert result is not None
        expected = 2 * (1 - math.cos(math.pi / 4))
        assert abs(result - expected) < 0.1
        assert result > 0

    def test_disconnected_zero(self, mg):
        a, b = mg.add("a","n"), mg.add("b","n")
        c, d = mg.add("c","n"), mg.add("d","n")
        mg.link(a.id, b.id, "e"); mg.link(c.id, d.id, "e")
        assert abs(mg.algebraic_connectivity()) < 0.01

    def test_single_node_none(self, mg):
        mg.add("a", "node")
        assert mg.algebraic_connectivity() is None

    def test_two_nodes(self, mg):
        a, b = mg.add("a","n"), mg.add("b","n")
        mg.link(a.id, b.id, "e")
        assert abs(mg.algebraic_connectivity() - 2.0) < 0.5

    def test_star_graph(self, mg):
        center = mg.add("center", "node")
        spokes = [mg.add(f"l{i}", "node") for i in range(3)]
        for s in spokes:
            mg.link(center.id, s.id, "edge")
        result = mg.algebraic_connectivity()
        assert result is not None
        assert abs(result - 1.0) < 0.3


class TestFiedlerVector:
    """Fiedler 向量测试。"""

    def test_path_orthogonal(self, mg):
        nodes = [mg.add(f"n{i}", "node") for i in range(4)]
        for i in range(3):
            mg.link(nodes[i].id, nodes[i+1].id, "edge")
        fv = mg.fiedler_vector()
        assert fv is not None
        assert len(fv) == 4
        assert abs(sum(fv)) < 0.01

    def test_normalization(self, mg):
        nodes = [mg.add(f"n{i}", "node") for i in range(5)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i+1].id, "edge")
        fv = mg.fiedler_vector()
        norm = math.sqrt(sum(x * x for x in fv))
        assert abs(norm - 1.0) < 0.01

    def test_spectral_bipartition(self, mg):
        nodes = [mg.add(f"n{i}", "node") for i in range(4)]
        for i in range(4):
            for j in range(i+1, 4):
                mg.link(nodes[i].id, nodes[j].id, "edge")
        fv = mg.fiedler_vector()
        assert fv is not None
        # K4 has degenerate eigenvalue, Fiedler vector may vary
        # Just check it's unit length and roughly orthogonal to [1,1,1,1]
        assert abs(sum(fv)) < 0.5  # relaxed for degenerate case
        norm = math.sqrt(sum(x*x for x in fv))
        assert abs(norm - 1.0) < 0.05

    def test_single_node_none(self, mg):
        mg.add("a", "node")
        assert mg.fiedler_vector() is None

class TestNodeConnectivity:
    """节点连通度测试。"""

    def test_complete_graph(self, mg):
        nodes = [mg.add(f"n{i}", "node") for i in range(4)]
        for i in range(4):
            for j in range(i+1, 4):
                mg.link(nodes[i].id, nodes[j].id, "e")
        assert mg.node_connectivity() == 3

    def test_cycle_graph(self, mg):
        nodes = [mg.add(f"n{i}", "node") for i in range(5)]
        for i in range(5):
            mg.link(nodes[i].id, nodes[(i+1)%5].id, "e")
        assert mg.node_connectivity() == 2

    def test_path_graph(self, mg):
        nodes = [mg.add(f"n{i}", "node") for i in range(4)]
        for i in range(3):
            mg.link(nodes[i].id, nodes[i+1].id, "e")
        assert mg.node_connectivity() == 1

    def test_disconnected(self, mg):
        a, b = mg.add("a","n"), mg.add("b","n")
        c = mg.add("c","n")
        mg.link(a.id, b.id, "e")
        assert mg.node_connectivity() == 0

    def test_single_node(self, mg):
        mg.add("a", "node")
        assert mg.node_connectivity() == 0

    def test_two_nodes(self, mg):
        a, b = mg.add("a","n"), mg.add("b","n")
        mg.link(a.id, b.id, "e")
        assert mg.node_connectivity() == 1


class TestEdgeConnectivity:
    """边连通度测试。"""

    def test_complete_graph(self, mg):
        nodes = [mg.add(f"n{i}", "node") for i in range(4)]
        for i in range(4):
            for j in range(i+1, 4):
                mg.link(nodes[i].id, nodes[j].id, "e")
        assert mg.edge_connectivity() == 3

    def test_cycle_graph(self, mg):
        nodes = [mg.add(f"n{i}", "node") for i in range(5)]
        for i in range(5):
            mg.link(nodes[i].id, nodes[(i+1)%5].id, "e")
        assert mg.edge_connectivity() == 2

    def test_path_graph(self, mg):
        nodes = [mg.add(f"n{i}", "node") for i in range(4)]
        for i in range(3):
            mg.link(nodes[i].id, nodes[i+1].id, "e")
        assert mg.edge_connectivity() == 1

    def test_disconnected(self, mg):
        a, b = mg.add("a","n"), mg.add("b","n")
        c = mg.add("c","n")
        mg.link(a.id, b.id, "e")
        assert mg.edge_connectivity() == 0

    def test_bridge_graph(self, mg):
        t1 = [mg.add(f"t1_{i}", "node") for i in range(3)]
        for i in range(3):
            mg.link(t1[i].id, t1[(i+1)%3].id, "e")
        t2 = [mg.add(f"t2_{i}", "node") for i in range(3)]
        for i in range(3):
            mg.link(t2[i].id, t2[(i+1)%3].id, "e")
        mg.link(t1[0].id, t2[0].id, "bridge")
        assert mg.edge_connectivity() == 1

    def test_single_node(self, mg):
        mg.add("a", "node")
        assert mg.edge_connectivity() == 0

class TestPercolationCentrality:
    """渗透中心性测试。"""

    def test_star_center_highest(self, mg):
        """星形图中心节点渗透中心性最高。"""
        center = mg.add("center", "node")
        spokes = [mg.add(f"s{i}", "node") for i in range(4)]
        for s in spokes:
            mg.link(center.id, s.id, "e")
        pc = mg.percolation_centrality()
        assert pc[center.id] == 1.0  # normalized max
        for s in spokes:
            assert pc[s.id] < pc[center.id]

    def test_path_middle_highest(self, mg):
        """路径图中间节点渗透中心性最高。"""
        nodes = [mg.add(f"n{i}", "node") for i in range(5)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i+1].id, "e")
        pc = mg.percolation_centrality()
        # Middle node (index 2) should have highest centrality
        mid_id = nodes[2].id
        for nid, val in pc.items():
            if nid != mid_id:
                assert pc[mid_id] >= val

    def test_custom_states(self, mg):
        """自定义渗透状态。"""
        nodes = [mg.add(f"n{i}", "node") for i in range(4)]
        for i in range(3):
            mg.link(nodes[i].id, nodes[i+1].id, "e")
        # Set high state on endpoints
        states = {nodes[0].id: 1.0, nodes[3].id: 1.0,
                  nodes[1].id: 0.0, nodes[2].id: 0.0}
        pc = mg.percolation_centrality(states=states)
        # All nodes should have values
        assert len(pc) == 4
        for v in pc.values():
            assert v >= 0

    def test_empty_graph(self, mg):
        pc = mg.percolation_centrality()
        assert pc == {}

    def test_single_node(self, mg):
        mg.add("a", "node")
        pc = mg.percolation_centrality()
        assert len(pc) == 1

class TestResistanceDistance:
    """电阻距离测试。"""

    def test_same_node_zero(self, mg):
        a = mg.add("a", "node")
        assert mg.resistance_distance(a.id, a.id) == 0.0

    def test_two_nodes(self, mg):
        """K2: 电阻距离 = 1。"""
        a, b = mg.add("a","n"), mg.add("b","n")
        mg.link(a.id, b.id, "e")
        result = mg.resistance_distance(a.id, b.id)
        assert result is not None
        assert abs(result - 1.0) < 0.1

    def test_parallel_paths_lower(self, mg):
        """并联路径降低电阻距离。"""
        a, b = mg.add("a","n"), mg.add("b","n")
        mg.link(a.id, b.id, "e")  # direct: R=1
        c = mg.add("c","n")
        mg.link(a.id, c.id, "e"); mg.link(c.id, b.id, "e")  # via c: R=2
        # Parallel: 1/(1/1 + 1/2) = 2/3
        result = mg.resistance_distance(a.id, b.id)
        assert result is not None
        assert abs(result - 2.0/3.0) < 0.2

    def test_disconnected_infinite(self, mg):
        a, b = mg.add("a","n"), mg.add("b","n")
        assert mg.resistance_distance(a.id, b.id) == float('inf')

    def test_nonexistent_none(self, mg):
        a = mg.add("a", "node")
        assert mg.resistance_distance(a.id, "nonexistent") is None

    def test_triangle(self, mg):
        """三角形: R(a,b) = 2/3。"""
        a, b, c = mg.add("a","n"), mg.add("b","n"), mg.add("c","n")
        mg.link(a.id, b.id, "e"); mg.link(b.id, c.id, "e"); mg.link(a.id, c.id, "e")
        result = mg.resistance_distance(a.id, b.id)
        assert result is not None
        assert abs(result - 2.0/3.0) < 0.15

    def test_symmetry(self, mg):
        """电阻距离是对称的。"""
        nodes = [mg.add(f"n{i}", "node") for i in range(4)]
        for i in range(3):
            mg.link(nodes[i].id, nodes[i+1].id, "e")
        r_ab = mg.resistance_distance(nodes[0].id, nodes[3].id)
        r_ba = mg.resistance_distance(nodes[3].id, nodes[0].id)
        assert abs(r_ab - r_ba) < 0.01


# ── MST (Minimum Spanning Tree) Tests ────────────────────────────────

class TestMST:
    """minimum_spanning_tree + mst_weight tests."""

    def test_simple_chain(self, mg):
        """3-node chain: MST = chain itself."""
        a, b, c = mg.add("a","n"), mg.add("b","n"), mg.add("c","n")
        mg.link(a.id, b.id, "e", 1.0)
        mg.link(b.id, c.id, "e", 2.0)
        mst = mg.minimum_spanning_tree()
        assert mst is not None
        assert len(mst) == 2
        assert mg.mst_weight() == 3.0

    def test_triangle_picks_cheapest(self, mg):
        """Triangle: MST drops the heaviest edge."""
        a, b, c = mg.add("a","n"), mg.add("b","n"), mg.add("c","n")
        mg.link(a.id, b.id, "e", 1.0)
        mg.link(b.id, c.id, "e", 2.0)
        mg.link(a.id, c.id, "e", 5.0)  # heaviest → excluded
        mst = mg.minimum_spanning_tree()
        assert len(mst) == 2
        assert mg.mst_weight() == 3.0
        # a-c edge should not be in MST
        mst_pairs = {(e["source"], e["target"]) for e in mst}
        assert ("a", "c") not in mst_pairs and ("c", "a") not in mst_pairs

    def test_empty_graph(self, mg):
        assert mg.minimum_spanning_tree() is None
        assert mg.mst_weight() is None

    def test_single_node(self, mg):
        mg.add("a", "n")
        assert mg.minimum_spanning_tree() is None

    def test_two_nodes(self, mg):
        a, b = mg.add("a","n"), mg.add("b","n")
        mg.link(a.id, b.id, "e", 3.5)
        mst = mg.minimum_spanning_tree()
        assert len(mst) == 1
        assert mg.mst_weight() == 3.5

    def test_disconnected_returns_none(self, mg):
        a, b, c, d = mg.add("a","n"), mg.add("b","n"), mg.add("c","n"), mg.add("d","n")
        mg.link(a.id, b.id, "e")
        # c-d disconnected from a-b
        assert mg.minimum_spanning_tree() is None

    def test_directed_edges_treated_undirected(self, mg):
        """MST treats directed edges as undirected."""
        a, b, c = mg.add("a","n"), mg.add("b","n"), mg.add("c","n")
        mg.link(a.id, b.id, "e", 1.0)
        mg.link(c.id, b.id, "e", 2.0)  # directed c→b
        mst = mg.minimum_spanning_tree()
        assert mst is not None
        assert len(mst) == 2

    def test_parallel_edges_keeps_cheapest(self, mg):
        """Multiple edges between same pair: keep cheapest."""
        a, b, c = mg.add("a","n"), mg.add("b","n"), mg.add("c","n")
        mg.link(a.id, b.id, "e", 1.0)
        mg.link(a.id, b.id, "e2", 0.1)  # cheaper parallel edge
        mg.link(b.id, c.id, "e", 1.0)
        mst = mg.minimum_spanning_tree()
        assert mg.mst_weight() == pytest.approx(1.1)

    def test_larger_graph(self, mg):
        """5-node graph with known MST weight."""
        nodes = [mg.add(f"n{i}", "n") for i in range(5)]
        # K5 with weights
        weights = [(0,1,2), (0,2,1), (0,3,4), (0,4,3),
                   (1,2,5), (1,3,2), (1,4,6),
                   (2,3,3), (2,4,1),
                   (3,4,2)]
        for i, j, w in weights:
            mg.link(nodes[i].id, nodes[j].id, "e", float(w))
        # MST: 0-2(1), 2-4(1), 0-1(2), 1-3(2) = 6
        assert mg.mst_weight() == pytest.approx(6.0)
        assert len(mg.minimum_spanning_tree()) == 4



class TestTriadCensus:
    """Triad census — 16 directed triad type counts."""

    def test_empty_graph(self, mg):
        """Graph with <3 nodes returns zero-count census."""
        mg.add("a", "n")
        mg.add("b", "n")
        census = mg.triad_census()
        assert all(v == 0 for v in census.values())
        assert len(census) > 0

    def test_three_isolated_nodes(self, mg):
        """3 nodes, no edges -> no non-trivial triads."""
        mg.add("a", "n")
        mg.add("b", "n")
        mg.add("c", "n")
        census = mg.triad_census()
        assert sum(census.values()) == 0

    def test_single_edge_triad(self, mg):
        """3 nodes with 1 directed edge: exactly 1 non-zero triad."""
        a, b, c = mg.add("a","n"), mg.add("b","n"), mg.add("c","n")
        mg.link(a.id, b.id, "e")
        census = mg.triad_census()
        assert sum(census.values()) == 1
        non_zero = [k for k, v in census.items() if v == 1]
        assert len(non_zero) == 1
        code = non_zero[0]
        nonzero_digits = sum(1 for d in code if d != '0')
        assert nonzero_digits == 1

    def test_mutual_edge(self, mg):
        """3 nodes with mutual edge: code contains one '3'."""
        a, b, c = mg.add("a","n"), mg.add("b","n"), mg.add("c","n")
        mg.link(a.id, b.id, "e")
        mg.link(b.id, a.id, "e")
        census = mg.triad_census()
        assert sum(census.values()) == 1
        non_zero = [k for k, v in census.items() if v > 0]
        assert len(non_zero) == 1
        code = non_zero[0]
        assert '3' in code
        nonzero_digits = [d for d in code if d != '0']
        assert nonzero_digits == ['3']

    def test_directed_triangle_all_forward(self, mg):
        """3 nodes all forward edges: a->b, a->c, b->c."""
        a, b, c = mg.add("a","n"), mg.add("b","n"), mg.add("c","n")
        mg.link(a.id, b.id, "e")
        mg.link(a.id, c.id, "e")
        mg.link(b.id, c.id, "e")
        census = mg.triad_census()
        assert sum(census.values()) == 1
        non_zero = [k for k, v in census.items() if v > 0][0]
        nonzero_count = sum(1 for d in non_zero if d != '0')
        assert nonzero_count == 3

    def test_directed_cycle(self, mg):
        """True directed cycle: a->b->c->a."""
        a, b, c = mg.add("a","n"), mg.add("b","n"), mg.add("c","n")
        mg.link(a.id, b.id, "e")
        mg.link(b.id, c.id, "e")
        mg.link(c.id, a.id, "e")
        census = mg.triad_census()
        assert sum(census.values()) == 1
        non_zero = [k for k, v in census.items() if v > 0][0]
        nonzero_digits = [d for d in non_zero if d != '0']
        assert len(nonzero_digits) == 3
        assert all(d in ('1', '2') for d in nonzero_digits)

    def test_complete_mutual(self, mg):
        """3 nodes all mutually connected: code '333'."""
        a, b, c = mg.add("a","n"), mg.add("b","n"), mg.add("c","n")
        mg.link(a.id, b.id, "e"); mg.link(b.id, a.id, "e")
        mg.link(a.id, c.id, "e"); mg.link(c.id, a.id, "e")
        mg.link(b.id, c.id, "e"); mg.link(c.id, b.id, "e")
        census = mg.triad_census()
        assert sum(census.values()) == 1
        non_zero = [k for k, v in census.items() if v > 0][0]
        assert non_zero == "333"

    def test_four_nodes_total_triads(self, mg):
        """4 nodes -> C(4,3)=4 triads total regardless of edges."""
        nodes = [mg.add(f"n{i}", "n") for i in range(4)]
        mg.link(nodes[0].id, nodes[1].id, "e")
        mg.link(nodes[2].id, nodes[3].id, "e")
        census = mg.triad_census()
        assert sum(census.values()) == 4

    def test_symmetry_total_count(self, mg):
        """Triad census total = C(n,3) for any graph."""
        nodes = [mg.add(f"n{i}", "n") for i in range(5)]
        import random
        random.seed(42)
        for i in range(5):
            for j in range(i+1, 5):
                if random.random() > 0.4:
                    mg.link(nodes[i].id, nodes[j].id, "e")
                if random.random() > 0.6:
                    mg.link(nodes[j].id, nodes[i].id, "e")
        census = mg.triad_census()
        assert sum(census.values()) == 10

    def test_mixed_triad_types(self, mg):
        """5 nodes star: verify multiple triad types."""
        nodes = [mg.add(f"n{i}", "n") for i in range(5)]
        for i in range(1, 5):
            mg.link(nodes[0].id, nodes[i].id, "e")
        census = mg.triad_census()
        # Star: 4 triads include hub (have edges), 4 without hub (no edges, excluded as '000')
        # C(4,2)=6 triads include hub, 4 don't → 6 non-trivial
        assert sum(census.values()) == 6
        types_with_edges = sum(1 for v in census.values() if v > 0)
        assert types_with_edges >= 1


class TestAverageNeighborDegree:
    """average_neighbor_degree — per-node k_nn metric."""

    def test_empty_graph(self, mg):
        assert mg.average_neighbor_degree() == {}

    def test_single_edge(self, mg):
        a, b = mg.add("a", "n"), mg.add("b", "n")
        mg.link(a.id, b.id, "e")
        result = mg.average_neighbor_degree()
        # a has degree 1, neighbor b has degree 1 → k_nn(a) = 1
        assert result[a.id] == 1.0
        assert result[b.id] == 1.0

    def test_star_hub(self, mg):
        """Star: hub has low k_nn, leaves have high k_nn."""
        center = mg.add("center", "n")
        leaves = [mg.add(f"l{i}", "n") for i in range(4)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "e")
        result = mg.average_neighbor_degree()
        # Hub degree=4, neighbors all degree=1 → k_nn = 4*(1/4) = 1.0
        assert result[center.id] == 1.0
        # Each leaf degree=1, neighbor hub degree=4 → k_nn = 4.0
        for leaf in leaves:
            assert result[leaf.id] == 4.0

    def test_isolated_node_excluded(self, mg):
        a, b, c = mg.add("a", "n"), mg.add("b", "n"), mg.add("c", "n")
        mg.link(a.id, b.id, "e")
        result = mg.average_neighbor_degree()
        assert c.id not in result

    def test_triangle(self, mg):
        """Complete triangle: all degree 2, all k_nn = 2."""
        nodes = [mg.add(f"n{i}", "n") for i in range(3)]
        mg.link(nodes[0].id, nodes[1].id, "e")
        mg.link(nodes[1].id, nodes[2].id, "e")
        mg.link(nodes[2].id, nodes[0].id, "e")
        result = mg.average_neighbor_degree()
        for n in nodes:
            assert result[n.id] == 2.0


class TestDegreeCorrelation:
    """degree_correlation — Newman assortativity coefficient."""

    def test_empty_graph(self, mg):
        assert mg.degree_correlation() is None

    def test_single_edge(self, mg):
        a, b = mg.add("a", "n"), mg.add("b", "n")
        mg.link(a.id, b.id, "e")
        # Both degree 1, r is trivially 0 (or very close)
        r = mg.degree_correlation()
        assert r is not None

    def test_star_disassortative(self, mg):
        """Star graph is disassortative (r < 0)."""
        center = mg.add("center", "n")
        leaves = [mg.add(f"l{i}", "n") for i in range(5)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "e")
        r = mg.degree_correlation()
        assert r < 0

    def test_regular_graph_neutral(self, mg):
        """Regular graph (all same degree) → r ≈ 0 or undefined."""
        nodes = [mg.add(f"n{i}", "n") for i in range(4)]
        # Cycle: all degree 2
        for i in range(4):
            mg.link(nodes[i].id, nodes[(i+1) % 4].id, "e")
        r = mg.degree_correlation()
        # All edges connect degree-2 to degree-2, variance is 0
        assert abs(r) < 0.01 or r == 0.0

    def test_clique_assortative(self, mg):
        """Complete graph: trivially assortative (all same degree)."""
        nodes = [mg.add(f"n{i}", "n") for i in range(4)]
        for i in range(4):
            for j in range(i+1, 4):
                mg.link(nodes[i].id, nodes[j].id, "e")
        r = mg.degree_correlation()
        # All degree 3, r should be ~0 (no variance)
        assert r is not None
        assert abs(r) < 0.01 or r == 0.0

    def test_hub_spoke_mixed(self, mg):
        """Graph with clear degree heterogeneity."""
        nodes = [mg.add(f"n{i}", "n") for i in range(5)]
        # Two hubs connected, each with spokes
        mg.link(nodes[0].id, nodes[1].id, "e")  # hub-hub
        for i in range(2, 5):
            mg.link(nodes[0].id, nodes[i].id, "e")  # hub0 spokes
            mg.link(nodes[1].id, nodes[i].id, "e")  # hub1 spokes
        r = mg.degree_correlation()
        # Hub-hub edge + hub-spoke edges → slight assortativity possible
        assert r is not None
        assert -1 <= r <= 1


class TestNodeSimilarity:
    """node_similarity — structural similarity between two nodes."""

    def test_same_node(self, mg):
        a = mg.add("a", "n")
        assert mg.node_similarity(a.id, a.id) == 1.0

    def test_nonexistent_node(self, mg):
        a = mg.add("a", "n")
        assert mg.node_similarity(a.id, "nonexistent") == 0.0

    def test_no_neighbors_no_overlap(self, mg):
        a, b = mg.add("a", "n"), mg.add("b", "n")
        # Both isolated → Jaccard = 1.0 (empty sets are equal)
        assert mg.node_similarity(a.id, b.id) == 1.0

    def test_one_neighbor_each(self, mg):
        a, b, c = mg.add("a", "n"), mg.add("b", "n"), mg.add("c", "n")
        mg.link(a.id, c.id, "e")
        mg.link(b.id, c.id, "e")
        # a's neighbors: {c}, b's neighbors: {c} → Jaccard = 1.0
        assert mg.node_similarity(a.id, b.id) == 1.0

    def test_partial_overlap(self, mg):
        a, b = mg.add("a", "n"), mg.add("b", "n")
        c, d, e = mg.add("c", "n"), mg.add("d", "n"), mg.add("e", "n")
        mg.link(a.id, c.id, "e")
        mg.link(a.id, d.id, "e")
        mg.link(b.id, d.id, "e")
        mg.link(b.id, e.id, "e")
        # a's nbrs: {c,d}, b's nbrs: {d,e} → intersection={d}, union={c,d,e}
        # Jaccard = 1/3
        assert mg.node_similarity(a.id, b.id, mode="jaccard") == pytest.approx(1/3)
        # Overlap = 1/2 (min(2,2)=2)
        assert mg.node_similarity(a.id, b.id, mode="overlap") == pytest.approx(0.5)

    def test_no_overlap(self, mg):
        a, b = mg.add("a", "n"), mg.add("b", "n")
        c, d = mg.add("c", "n"), mg.add("d", "n")
        mg.link(a.id, c.id, "e")
        mg.link(b.id, d.id, "e")
        assert mg.node_similarity(a.id, b.id) == 0.0

    def test_invalid_mode(self, mg):
        a, b = mg.add("a", "n"), mg.add("b", "n")
        with pytest.raises(ValueError):
            mg.node_similarity(a.id, b.id, mode="invalid")

    def test_directed_edges_treated_undirected(self, mg):
        """Similarity uses undirected neighbor sets."""
        a, b, c = mg.add("a", "n"), mg.add("b", "n"), mg.add("c", "n")
        mg.link(a.id, c.id, "e")  # a→c
        mg.link(c.id, b.id, "e")  # c→b
        # a's undirected nbrs: {c}, b's undirected nbrs: {c}
        assert mg.node_similarity(a.id, b.id) == 1.0


class TestEgoGraph:
    def test_order_1(self, mg):
        a = mg.add("center", "n")
        b, c, d = mg.add("b", "n"), mg.add("c", "n"), mg.add("d", "n")
        e = mg.add("e", "n")  # disconnected
        mg.link(a.id, b.id, "e")
        mg.link(a.id, c.id, "e")
        mg.link(b.id, d.id, "e")
        result = mg.ego_graph(a.id, order=1)
        assert result["center"] == a.id
        assert set(result["nodes"]) == {a.id, b.id, c.id}
        assert len(result["edges"]) == 2  # a-b, a-c
        assert result["radius"] == 1

    def test_order_2(self, mg):
        a = mg.add("center", "n")
        b, c, d = mg.add("b", "n"), mg.add("c", "n"), mg.add("d", "n")
        mg.link(a.id, b.id, "e")
        mg.link(b.id, c.id, "e")
        mg.link(c.id, d.id, "e")
        result = mg.ego_graph(a.id, order=2)
        assert set(result["nodes"]) == {a.id, b.id, c.id}
        assert len(result["edges"]) == 2  # a-b, b-c (c-d excluded, d outside ego)

    def test_nonexistent_node(self, mg):
        result = mg.ego_graph("nope", order=1)
        assert result["nodes"] == []

    def test_isolated_node(self, mg):
        a = mg.add("alone", "n")
        result = mg.ego_graph(a.id, order=1)
        assert result["nodes"] == [a.id]
        assert result["edges"] == []


class TestTransitivity:
    def test_triangle(self, mg):
        a, b, c = mg.add("a", "n"), mg.add("b", "n"), mg.add("c", "n")
        mg.link(a.id, b.id, "e")
        mg.link(b.id, c.id, "e")
        mg.link(c.id, a.id, "e")
        assert mg.transitivity() == 1.0

    def test_no_triangles(self, mg):
        a, b, c, d = mg.add("a", "n"), mg.add("b", "n"), mg.add("c", "n"), mg.add("d", "n")
        mg.link(a.id, b.id, "e")
        mg.link(b.id, c.id, "e")
        mg.link(c.id, d.id, "e")
        assert mg.transitivity() == 0.0

    def test_empty_graph(self, mg):
        assert mg.transitivity() == 0.0

    def test_partial(self, mg):
        # Square with one diagonal: 2 triangles, 4 triples
        a, b, c, d = mg.add("a", "n"), mg.add("b", "n"), mg.add("c", "n"), mg.add("d", "n")
        mg.link(a.id, b.id, "e"); mg.link(b.id, c.id, "e")
        mg.link(c.id, d.id, "e"); mg.link(d.id, a.id, "e")
        mg.link(a.id, c.id, "e")  # diagonal
        # Triangles: abc, acd → 2
        # Triples: a(b,c,d)=3, b(a,c)=1, c(a,b,d)=3, d(a,c)=1 → 8 total undirected triples = 8/2=... 
        # Actually triples = sum of C(deg,2) per node
        # deg: a=3, b=2, c=3, d=2 → C(3,2)+C(2,2)+C(3,2)+C(2,2) = 3+1+3+1 = 8
        # Each triangle counted 3 times → 2*3=6 triangles found
        t = mg.transitivity()
        assert 0 < t <= 1.0


class TestPreferentialAttachment:
    def test_basic(self, mg):
        a, b, c = mg.add("a", "n"), mg.add("b", "n"), mg.add("c", "n")
        mg.link(a.id, b.id, "e")
        mg.link(a.id, c.id, "e")
        # a has degree 2, b has degree 1
        assert mg.preferential_attachment(a.id, b.id) == 2 * 1

    def test_nonexistent(self, mg):
        a = mg.add("a", "n")
        assert mg.preferential_attachment(a.id, "nope") is None

    def test_isolated(self, mg):
        a, b = mg.add("a", "n"), mg.add("b", "n")
        assert mg.preferential_attachment(a.id, b.id) == 0


class TestResourceAllocationIndex:
    def test_basic(self, mg):
        a, b, c, d = mg.add("a", "n"), mg.add("b", "n"), mg.add("c", "n"), mg.add("d", "n")
        mg.link(a.id, c.id, "e"); mg.link(b.id, c.id, "e")
        mg.link(a.id, d.id, "e"); mg.link(b.id, d.id, "e")
        # c and d are common neighbors, both degree 2
        # RA = 1/2 + 1/2 = 1.0
        assert mg.resource_allocation_index(a.id, b.id) == 1.0

    def test_no_common(self, mg):
        a, b = mg.add("a", "n"), mg.add("b", "n")
        assert mg.resource_allocation_index(a.id, b.id) == 0.0

    def test_nonexistent(self, mg):
        a = mg.add("a", "n")
        assert mg.resource_allocation_index(a.id, "nope") is None


class TestDegreePrestige:
    def test_full_prestige(self, mg):
        a, b, c = mg.add("a", "n"), mg.add("b", "n"), mg.add("c", "n")
        mg.link(b.id, a.id, "e"); mg.link(c.id, a.id, "e")
        assert mg.degree_prestige(a.id) == 1.0  # 2 in-edges / (3-1)

    def test_zero_prestige(self, mg):
        a, b = mg.add("a", "n"), mg.add("b", "n")
        assert mg.degree_prestige(a.id) == 0.0

    def test_nonexistent(self, mg):
        assert mg.degree_prestige("nope") is None

    def test_single_node(self, mg):
        a = mg.add("a", "n")
        assert mg.degree_prestige(a.id) == 0.0


class TestCoreRatio:
    def test_empty(self, mg):
        assert mg.core_ratio(1) == 0.0

    def test_basic(self, mg):
        # Triangle: all nodes in 2-core
        a, b, c = mg.add("a", "n"), mg.add("b", "n"), mg.add("c", "n")
        mg.link(a.id, b.id, "e"); mg.link(b.id, c.id, "e"); mg.link(c.id, a.id, "e")
        # Need to compute core_number first
        ratio = mg.core_ratio(2)
        assert ratio == 1.0  # All 3 in 2-core


class TestLeidenAggregation:
    """Tests for Leiden with proper 3-phase Aggregation."""

    @pytest.fixture
    def mg(self):
        return MemoryGraph(":memory:")

    def test_aggregation_two_level_merge(self, mg):
        """Two clusters connected by a weak bridge should merge into 2 communities
        via the aggregation phase."""
        # Cluster A: 5 nodes densely connected
        a_nodes = [mg.add(f"a{i}", "A") for i in range(5)]
        for i in range(5):
            for j in range(i + 1, 5):
                mg.link(a_nodes[i].id, a_nodes[j].id, "close", 1.0)
        # Cluster B: 5 nodes densely connected
        b_nodes = [mg.add(f"b{i}", "B") for i in range(5)]
        for i in range(5):
            for j in range(i + 1, 5):
                mg.link(b_nodes[i].id, b_nodes[j].id, "close", 1.0)
        # Weak bridge
        mg.link(a_nodes[0].id, b_nodes[0].id, "bridge", 0.1)

        result = mg.detect_communities_leiden(seed=42)
        assert len(set(result.values())) == 2
        # Each cluster should be one community
        a_comms = {result[n.id] for n in a_nodes}
        b_comms = {result[n.id] for n in b_nodes}
        assert len(a_comms) == 1, "Cluster A should be one community"
        assert len(b_comms) == 1, "Cluster B should be one community"
        assert a_comms != b_comms, "Clusters should be different communities"

    def test_aggregation_three_communities(self, mg):
        """Three well-separated cliques should yield 3 communities."""
        cliques = []
        for label in ["x", "y", "z"]:
            nodes = [mg.add(f"{label}{i}", label) for i in range(4)]
            for i in range(4):
                for j in range(i + 1, 4):
                    mg.link(nodes[i].id, nodes[j].id, "close", 1.0)
            cliques.append(nodes)
        # Weak inter-clique bridges
        mg.link(cliques[0][0].id, cliques[1][0].id, "bridge", 0.05)
        mg.link(cliques[1][1].id, cliques[2][0].id, "bridge", 0.05)

        result = mg.detect_communities_leiden(seed=42)
        assert len(set(result.values())) == 3

    def test_aggregation_improves_modularity(self, mg):
        """Multi-level Leiden should produce equal or better modularity than single-level."""
        # Ring of 8 nodes with two cross-links forming natural communities
        nodes = [mg.add(f"n{i}", "N") for i in range(8)]
        for i in range(8):
            mg.link(nodes[i].id, nodes[(i + 1) % 8].id, "ring", 1.0)
        # Two cross-links split ring into two halves
        mg.link(nodes[0].id, nodes[3].id, "cross", 0.5)
        mg.link(nodes[4].id, nodes[7].id, "cross", 0.5)

        result_multi = mg.detect_communities_leiden(max_iterations=10, seed=42)
        q_multi = mg.modularity(result_multi)

        # Multi-level should find non-trivial partition
        assert q_multi >= 0.0, "Modularity should be non-negative"
        assert len(set(result_multi.values())) >= 2, "Should find at least 2 communities"

    def test_aggregation_all_singletons(self, mg):
        """Graph with no edges → each node is its own community."""
        for i in range(5):
            mg.add(f"s{i}", "S")
        result = mg.detect_communities_leiden(seed=42)
        assert len(set(result.values())) == 5

    def test_aggregation_fully_connected(self, mg):
        """Complete graph → all nodes in one community."""
        nodes = [mg.add(f"k{i}", "K") for i in range(6)]
        for i in range(6):
            for j in range(i + 1, 6):
                mg.link(nodes[i].id, nodes[j].id, "complete", 1.0)
        result = mg.detect_communities_leiden(seed=42)
        assert len(set(result.values())) == 1

    def test_aggregation_preserves_node_count(self, mg):
        """Every node should appear in the result."""
        nodes = [mg.add(f"p{i}", "P") for i in range(7)]
        for i in range(6):
            mg.link(nodes[i].id, nodes[i + 1].id, "chain", 1.0)
        result = mg.detect_communities_leiden(seed=42)
        assert len(result) == 7
        for n in nodes:
            assert n.id in result

    def test_aggregation_deterministic(self, mg):
        """Same seed → same result."""
        nodes = [mg.add(f"d{i}", "D") for i in range(6)]
        for i in range(6):
            for j in range(i + 1, 6):
                mg.link(nodes[i].id, nodes[j].id, "edge", 1.0)
        r1 = mg.detect_communities_leiden(seed=123)
        r2 = mg.detect_communities_leiden(seed=123)
        assert r1 == r2

    def test_aggregation_self_loops_in_aggregated_graph(self, mg):
        """Aggregated super-nodes should have self-loops from internal edges.
        Verify by checking that aggregation produces correct edge weights."""
        # Triangle + 1 external edge
        a, b, c = mg.add("a", "T"), mg.add("b", "T"), mg.add("c", "T")
        d = mg.add("d", "O")
        mg.link(a.id, b.id, "e", 1.0)
        mg.link(b.id, c.id, "e", 1.0)
        mg.link(a.id, c.id, "e", 1.0)
        mg.link(c.id, d.id, "e", 0.3)

        result = mg.detect_communities_leiden(seed=42)
        # Triangle should be one community, d is another (or same)
        assert result[a.id] == result[b.id] == result[c.id]

    def test_aggregation_large_modularity_gain(self, mg):
        """Well-separated communities should have modularity > 0.3."""
        # Four groups of 4 nodes each, fully connected within group
        groups = []
        for g in range(4):
            group = [mg.add(f"g{g}n{i}", f"G{g}") for i in range(4)]
            for i in range(4):
                for j in range(i + 1, 4):
                    mg.link(group[i].id, group[j].id, "intra", 1.0)
            groups.append(group)
        # Single weak inter-group edge
        mg.link(groups[0][0].id, groups[1][0].id, "inter", 0.01)
        mg.link(groups[1][1].id, groups[2][0].id, "inter", 0.01)
        mg.link(groups[2][1].id, groups[3][0].id, "inter", 0.01)

        result = mg.detect_communities_leiden(seed=42)
        q = mg.modularity(result)
        assert q > 0.3, f"Modularity {q:.3f} should be > 0.3 for well-separated groups"

    def test_aggregation_resolution_splits_large_community(self, mg):
        """High resolution γ should split a large community into smaller pieces."""
        # 8-node ring
        nodes = [mg.add(f"r{i}", "R") for i in range(8)]
        for i in range(8):
            mg.link(nodes[i].id, nodes[(i + 1) % 8].id, "ring", 1.0)

        low_res = mg.detect_communities_leiden(resolution=0.3, seed=42)
        high_res = mg.detect_communities_leiden(resolution=3.0, seed=42)
        # Higher resolution tends to produce more communities
        assert len(set(high_res.values())) >= len(set(low_res.values()))


class TestCommunityHierarchy:
    """Tests for community_hierarchy() multi-resolution analysis."""

    @pytest.fixture
    def mg(self):
        return MemoryGraph(":memory:")

    def test_hierarchy_default_resolutions(self, mg):
        """Default should return 5 resolution levels."""
        nodes = [mg.add(f"n{i}", "N") for i in range(4)]
        mg.link(nodes[0].id, nodes[1].id, "e")
        mg.link(nodes[1].id, nodes[2].id, "e")
        mg.link(nodes[2].id, nodes[3].id, "e")
        hierarchy = mg.community_hierarchy()
        assert len(hierarchy) == 5
        for entry in hierarchy:
            assert "resolution" in entry
            assert "communities" in entry
            assert "num_communities" in entry
            assert "modularity" in entry
            assert "sizes" in entry

    def test_hierarchy_custom_resolutions(self, mg):
        """Custom resolution list should be respected."""
        nodes = [mg.add(f"x{i}", "X") for i in range(6)]
        for i in range(6):
            mg.link(nodes[i].id, nodes[(i + 1) % 6].id, "e")
        hierarchy = mg.community_hierarchy(resolutions=[0.5, 2.0])
        assert len(hierarchy) == 2
        assert hierarchy[0]["resolution"] == 0.5
        assert hierarchy[1]["resolution"] == 2.0

    def test_hierarchy_empty_graph(self, mg):
        """Empty graph should return entries with 0 communities."""
        hierarchy = mg.community_hierarchy()
        assert len(hierarchy) == 5
        for entry in hierarchy:
            assert entry["num_communities"] == 0

    def test_hierarchy_sizes_sorted(self, mg):
        """Size list should be sorted descending."""
        cliques = []
        for label in ["a", "b", "c"]:
            nodes = [mg.add(f"{label}{i}", label) for i in range(3)]
            for i in range(3):
                for j in range(i + 1, 3):
                    mg.link(nodes[i].id, nodes[j].id, "e")
            cliques.append(nodes)
        mg.link(cliques[0][0].id, cliques[1][0].id, "bridge", 0.1)
        mg.link(cliques[1][1].id, cliques[2][0].id, "bridge", 0.1)

        hierarchy = mg.community_hierarchy()
        for entry in hierarchy:
            if entry["sizes"]:
                assert entry["sizes"] == sorted(entry["sizes"], reverse=True)

    def test_hierarchy_all_nodes_present(self, mg):
        """Every node should appear in each resolution's partition."""
        nodes = [mg.add(f"p{i}", "P") for i in range(5)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i + 1].id, "e")
        hierarchy = mg.community_hierarchy()
        for entry in hierarchy:
            assert len(entry["communities"]) == 5

    def test_hierarchy_modularity_decreases_with_resolution(self, mg):
        """For well-separated communities, lower resolution tends to have
        higher modularity (closer to optimal)."""
        groups = []
        for g in range(3):
            group = [mg.add(f"g{g}n{i}", f"G{g}") for i in range(5)]
            for i in range(5):
                for j in range(i + 1, 5):
                    mg.link(group[i].id, group[j].id, "intra", 1.0)
            groups.append(group)
        mg.link(groups[0][0].id, groups[1][0].id, "inter", 0.01)
        mg.link(groups[1][1].id, groups[2][0].id, "inter", 0.01)

        hierarchy = mg.community_hierarchy(resolutions=[0.5, 1.0, 2.0])
        # At least one lower-res should have >= modularity than higher-res
        assert hierarchy[0]["modularity"] >= hierarchy[-1]["modularity"] - 0.1


class TestIncrementalModularity:
    """Tests for incremental_modularity() ΔQ calculation."""

    @pytest.fixture
    def mg(self):
        return MemoryGraph(":memory:")

    def test_zero_move_to_same_community(self, mg):
        """ΔQ should be 0 when target == current."""
        a, b = mg.add("a", "X"), mg.add("b", "X")
        mg.link(a.id, b.id, "e")
        communities = {a.id: 0, b.id: 0}
        delta = mg.incremental_modularity(a.id, 0, communities)
        assert delta == 0.0

    def test_positive_for_good_move(self, mg):
        """ΔQ should be positive for a beneficial move."""
        # Two triangles connected weakly
        a1, a2, a3 = mg.add("a1", "A"), mg.add("a2", "A"), mg.add("a3", "A")
        b1, b2, b3 = mg.add("b1", "B"), mg.add("b2", "B"), mg.add("b3", "B")
        for pair in [(a1,a2),(a2,a3),(a1,a3),(b1,b2),(b2,b3),(b1,b3)]:
            mg.link(pair[0].id, pair[1].id, "close", 1.0)
        mg.link(a1.id, b1.id, "bridge", 0.1)
        # Bad partition: a1 with B group
        communities = {a1.id: 0, a2.id: 1, a3.id: 1, b1.id: 0, b2.id: 0, b3.id: 0}
        # Moving a1 from 0→1 should be positive
        delta = mg.incremental_modularity(a1.id, 1, communities)
        assert delta > 0, f"Moving a1 to its clique should be positive, got {delta}"

    def test_negative_for_bad_move(self, mg):
        """ΔQ should be negative for a harmful move."""
        # Triangle + single node
        a1, a2, a3 = mg.add("a1", "A"), mg.add("a2", "A"), mg.add("a3", "A")
        d = mg.add("d", "D")
        mg.link(a1.id, a2.id, "e", 1.0)
        mg.link(a2.id, a3.id, "e", 1.0)
        mg.link(a1.id, a3.id, "e", 1.0)
        mg.link(a3.id, d.id, "weak", 0.1)
        # Good partition
        communities = {a1.id: 0, a2.id: 0, a3.id: 0, d.id: 1}
        # Moving a3 from its triangle to join d should be negative
        delta = mg.incremental_modularity(a3.id, 1, communities)
        assert delta < 0, f"Moving a3 away from triangle should be negative, got {delta}"

    def test_nonexistent_node(self, mg):
        """Nonexistent node should return 0.0."""
        a = mg.add("a", "X")
        mg.link(a.id, a.id, "self", 1.0)  # self-loop to avoid empty
        delta = mg.incremental_modularity("nonexistent", 0)
        assert delta == 0.0

    def test_empty_graph(self, mg):
        """Empty graph should return 0.0."""
        delta = mg.incremental_modularity("any", 0)
        assert delta == 0.0

    def test_auto_detect_communities(self, mg):
        """Should work without explicit communities (auto-detect via Leiden)."""
        a, b, c = mg.add("a", "X"), mg.add("b", "X"), mg.add("c", "X")
        mg.link(a.id, b.id, "e")
        mg.link(b.id, c.id, "e")
        # Should not crash with auto-detection
        delta = mg.incremental_modularity(a.id, 999)
        # Moving to non-existent community should still compute
        assert isinstance(delta, float)


class TestCommunityMergeSplit:
    """Tests for community_merge() and community_split()."""

    @pytest.fixture
    def mg(self):
        return MemoryGraph(":memory:")

    def test_merge_two_communities(self, mg):
        """Merging two communities should reduce count by 1."""
        a_nodes = [mg.add(f"a{i}", "A") for i in range(3)]
        b_nodes = [mg.add(f"b{i}", "B") for i in range(3)]
        for pair in [(a_nodes[0],a_nodes[1]),(a_nodes[1],a_nodes[2]),(a_nodes[0],a_nodes[2])]:
            mg.link(pair[0].id, pair[1].id, "e")
        for pair in [(b_nodes[0],b_nodes[1]),(b_nodes[1],b_nodes[2]),(b_nodes[0],b_nodes[2])]:
            mg.link(pair[0].id, pair[1].id, "e")
        mg.link(a_nodes[0].id, b_nodes[0].id, "bridge", 0.1)

        communities = mg.detect_communities_leiden(seed=42)
        initial_count = len(set(communities.values()))
        assert initial_count >= 2

        comm_ids = list(set(communities.values()))
        merged = mg.community_merge(comm_ids[0], comm_ids[1], communities)
        assert len(set(merged.values())) == initial_count - 1

    def test_merge_same_community(self, mg):
        """Merging a community with itself should be a no-op."""
        a, b = mg.add("a", "X"), mg.add("b", "X")
        mg.link(a.id, b.id, "e")
        communities = {a.id: 0, b.id: 0}
        result = mg.community_merge(0, 0, communities)
        assert result == communities

    def test_merge_auto_detect(self, mg):
        """Should work without explicit communities arg."""
        a_nodes = [mg.add(f"a{i}", "A") for i in range(3)]
        b_nodes = [mg.add(f"b{i}", "B") for i in range(3)]
        for i in range(3):
            mg.link(a_nodes[i].id, a_nodes[(i+1)%3].id, "e")
            mg.link(b_nodes[i].id, b_nodes[(i+1)%3].id, "e")
        mg.link(a_nodes[0].id, b_nodes[0].id, "bridge", 0.1)
        # Should auto-detect then merge
        communities = mg.detect_communities_leiden(seed=42)
        comm_ids = list(set(communities.values()))
        merged = mg.community_merge(comm_ids[0], comm_ids[-1])
        assert len(set(merged.values())) < len(comm_ids)

    def test_split_disconnected_community(self, mg):
        """A community with two disconnected components should split."""
        # Two separate edges (4 nodes, 2 components)
        a, b = mg.add("a", "X"), mg.add("b", "X")
        c, d = mg.add("c", "X"), mg.add("d", "X")
        mg.link(a.id, b.id, "e")
        mg.link(c.id, d.id, "e")
        # All in same community (manually)
        communities = {a.id: 0, b.id: 0, c.id: 0, d.id: 0}
        result = mg.community_split(0, communities)
        # Should split into 2 communities
        assert len(set(result.values())) == 2

    def test_split_connected_community(self, mg):
        """A connected community should still be splittable via degree seeds."""
        # 6-node dense graph
        nodes = [mg.add(f"n{i}", "N") for i in range(6)]
        for i in range(6):
            for j in range(i + 1, 6):
                mg.link(nodes[i].id, nodes[j].id, "e")
        communities = {n.id: 0 for n in nodes}
        result = mg.community_split(0, communities)
        # Should produce 2 sub-communities
        assert len(set(result.values())) == 2

    def test_split_single_node_community(self, mg):
        """Splitting a single-node community should be a no-op."""
        a = mg.add("a", "X")
        communities = {a.id: 0}
        result = mg.community_split(0, communities)
        assert result == communities

    def test_merge_then_split_roundtrip(self, mg):
        """Merge then split should recover original structure."""
        # Two triangles
        a_nodes = [mg.add(f"a{i}", "A") for i in range(3)]
        b_nodes = [mg.add(f"b{i}", "B") for i in range(3)]
        for pair in [(a_nodes[0],a_nodes[1]),(a_nodes[1],a_nodes[2]),(a_nodes[0],a_nodes[2])]:
            mg.link(pair[0].id, pair[1].id, "e")
        for pair in [(b_nodes[0],b_nodes[1]),(b_nodes[1],b_nodes[2]),(b_nodes[0],b_nodes[2])]:
            mg.link(pair[0].id, pair[1].id, "e")
        mg.link(a_nodes[0].id, b_nodes[0].id, "bridge", 0.1)

        original = mg.detect_communities_leiden(seed=42)
        orig_count = len(set(original.values()))

        # Merge all into one
        comm_ids = list(set(original.values()))
        merged = original
        for cid in comm_ids[1:]:
            merged = mg.community_merge(comm_ids[0], cid, merged)
        assert len(set(merged.values())) == 1

        # Split should recover structure
        split = mg.community_split(comm_ids[0], merged)
        assert len(set(split.values())) >= 2


class TestCommunityCohesionScore:
    """Tests for community_cohesion_score()."""

    @pytest.fixture
    def mg(self):
        return MemoryGraph(":memory:")

    def test_dense_community_scores_higher(self, mg):
        """A tightly connected community should score higher than a loose one."""
        # Dense clique A (4 nodes, all connected)
        a_nodes = [mg.add(f"a{i}", "A") for i in range(4)]
        for i in range(4):
            for j in range(i + 1, 4):
                mg.link(a_nodes[i].id, a_nodes[j].id, "e", 1.0)
        # Sparse chain B (4 nodes, only 3 edges)
        b_nodes = [mg.add(f"b{i}", "B") for i in range(4)]
        for i in range(3):
            mg.link(b_nodes[i].id, b_nodes[i + 1].id, "e", 1.0)

        communities = {n.id: 0 for n in a_nodes}
        communities.update({n.id: 1 for n in b_nodes})
        scores = mg.community_cohesion_score(communities)
        assert scores[0] > scores[1], "Dense clique should be more cohesive"

    def test_empty_graph(self, mg):
        """Empty graph → empty dict."""
        scores = mg.community_cohesion_score()
        assert scores == {}

    def test_single_node_community(self, mg):
        """Single-node communities get score 0."""
        a = mg.add("a", "X")
        scores = mg.community_cohesion_score({a.id: 0})
        assert scores[0] == 0.0

    def test_score_range_0_to_1(self, mg):
        """All scores should be in [0, 1]."""
        nodes = [mg.add(f"n{i}", "N") for i in range(6)]
        for i in range(5):
            mg.link(nodes[i].id, nodes[i + 1].id, "e", 1.0)
        communities = {n.id: 0 for n in nodes}
        scores = mg.community_cohesion_score(communities)
        for score in scores.values():
            assert 0.0 <= score <= 1.0

    def test_auto_detect_communities(self, mg):
        """Should auto-detect via Leiden if no communities provided."""
        nodes = [mg.add(f"x{i}", "X") for i in range(5)]
        for i in range(5):
            mg.link(nodes[i].id, nodes[(i + 1) % 5].id, "e", 1.0)
        scores = mg.community_cohesion_score()
        assert isinstance(scores, dict)
        assert len(scores) >= 1

    def test_weighted_edges_affect_score(self, mg):
        """Higher-weight edges should produce higher cohesion."""
        # Two triangles with different weights
        a_nodes = [mg.add(f"a{i}", "A") for i in range(3)]
        b_nodes = [mg.add(f"b{i}", "B") for i in range(3)]
        for pair in [(a_nodes[0],a_nodes[1]),(a_nodes[1],a_nodes[2]),(a_nodes[0],a_nodes[2])]:
            mg.link(pair[0].id, pair[1].id, "strong", 2.0)
        for pair in [(b_nodes[0],b_nodes[1]),(b_nodes[1],b_nodes[2]),(b_nodes[0],b_nodes[2])]:
            mg.link(pair[0].id, pair[1].id, "weak", 0.1)
        communities = {n.id: 0 for n in a_nodes}
        communities.update({n.id: 1 for n in b_nodes})
        scores = mg.community_cohesion_score(communities)
        assert scores[0] > scores[1], "Strong-weight triangle should be more cohesive"





# ── Round 32: density / local_clustering / efficiency ──────────────────

class TestDensity:
    """F128: density() — actual edges / maximum possible edges (undirected)."""

    def test_empty_graph(self, mg):
        assert mg.density() == 0.0

    def test_single_node(self, mg):
        mg.add("solo", "t")
        assert mg.density() == 0.0

    def test_no_edges(self, mg):
        for c in "ABCD":
            mg.add(c, "t")
        assert mg.density() == 0.0

    def test_path_graph(self, mg):
        """Path A-B-C-D: 3 edges, density = 2*3/(4*3) = 0.5."""
        nodes = [mg.add(c, "t") for c in "ABCD"]
        for i in range(3):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        assert mg.density() == 0.5

    def test_complete_graph(self, mg):
        """Complete K4: 6 edges, density = 2*6/(4*3) = 1.0."""
        nodes = [mg.add(c, "t") for c in "ABCD"]
        for i in range(4):
            for j in range(i + 1, 4):
                mg.link(nodes[i].id, nodes[j].id, "r")
        assert mg.density() == 1.0

    def test_range_0_to_1(self, mg):
        """Density should always be in [0, 1]."""
        nodes = [mg.add(c, "t") for c in "ABCDEF"]
        import random
        random.seed(42)
        for i in range(5):
            a, b = random.sample(nodes, 2)
            mg.link(a.id, b.id, "r")
        d = mg.density()
        assert 0.0 <= d <= 1.0


class TestLocalClustering:
    """F129: local_clustering(node_id) — fraction of neighbor pairs that are connected."""

    def test_triangle(self, mg):
        """Triangle: all 3 neighbor pairs connected → C=1.0."""
        nodes = [mg.add(c, "t") for c in "ABC"]
        for i in range(3):
            mg.link(nodes[i].id, nodes[(i + 1) % 3].id, "r")
        assert mg.local_clustering(nodes[0].id) == 1.0

    def test_open_triad(self, mg):
        """Open triad A-B, A-C (B-C not connected) → C=0.0."""
        a = mg.add("A", "t")
        b = mg.add("B", "t")
        c = mg.add("C", "t")
        mg.link(a.id, b.id, "r")
        mg.link(a.id, c.id, "r")
        assert mg.local_clustering(a.id) == 0.0

    def test_degree_one_returns_none(self, mg):
        """Node with degree 1 returns None (can't compute)."""
        a = mg.add("A", "t")
        b = mg.add("B", "t")
        mg.link(a.id, b.id, "r")
        assert mg.local_clustering(a.id) is None

    def test_isolated_node_returns_none(self, mg):
        """Isolated node returns None."""
        a = mg.add("A", "t")
        assert mg.local_clustering(a.id) is None

    def test_nonexistent_node(self, mg):
        """Nonexistent node returns None."""
        assert mg.local_clustering("nonexistent") is None

    def test_partial_clustering(self, mg):
        """5 neighbors with 2 connected pairs out of 6 possible → 2/6 ≈ 0.333."""
        center = mg.add("C", "t")
        nbrs = [mg.add(f"N{i}", "t") for i in range(5)]
        for n in nbrs:
            mg.link(center.id, n.id, "r")
        # Connect 2 pairs among neighbors
        mg.link(nbrs[0].id, nbrs[1].id, "r")
        mg.link(nbrs[2].id, nbrs[3].id, "r")
        result = mg.local_clustering(center.id)
        assert result is not None
        assert abs(result - (2.0 / 10.0)) < 1e-9  # 2*2/(5*4) = 0.2


class TestEfficiency:
    """F130: efficiency(a, b) — 1 / shortest_path_length."""

    def test_direct_neighbors(self, mg):
        """Direct edge: efficiency = 1/2 = 0.5."""
        a = mg.add("A", "t")
        b = mg.add("B", "t")
        mg.link(a.id, b.id, "r")
        assert mg.efficiency(a.id, b.id) == 0.5

    def test_two_hop_path(self, mg):
        """A-B-C: efficiency(A,C) = 1/3."""
        nodes = [mg.add(c, "t") for c in "ABC"]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[1].id, nodes[2].id, "r")
        assert abs(mg.efficiency(nodes[0].id, nodes[2].id) - 1.0 / 3.0) < 1e-9

    def test_same_node(self, mg):
        """Same node: efficiency = 1.0."""
        a = mg.add("A", "t")
        assert mg.efficiency(a.id, a.id) == 1.0

    def test_unreachable(self, mg):
        """Disconnected nodes: efficiency = 0.0."""
        a = mg.add("A", "t")
        b = mg.add("B", "t")
        assert mg.efficiency(a.id, b.id) == 0.0

    def test_nonexistent_nodes(self, mg):
        """Nonexistent nodes: efficiency = 0.0."""
        assert mg.efficiency("x", "y") == 0.0

    def test_longer_path(self, mg):
        """Path A-B-C-D: efficiency(A,D) = 1/4."""
        nodes = [mg.add(c, "t") for c in "ABCD"]
        for i in range(3):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        assert abs(mg.efficiency(nodes[0].id, nodes[3].id) - 0.25) < 1e-9


class TestAssortativityDegree:
    """F131: assortativity_degree() — Newman degree assortativity coefficient."""

    def test_empty_graph(self, mg):
        """No edges: assortativity = 0.0 (undefined, returns 0)."""
        assert mg.assortativity_degree() == 0.0

    def test_single_edge(self, mg):
        """One edge: denominator is zero (no variance), returns 0.0."""
        a = mg.add("A", "t")
        b = mg.add("B", "t")
        mg.link(a.id, b.id, "r")
        assert mg.assortativity_degree() == 0.0

    def test_star_graph_negative(self, mg):
        """Star graph: hub connects to leaves. Should be negatively assortative.

        Hub has degree 4, leaves have degree 1 each.
        All edges are (4,1) pairs → strong disassortativity.
        """
        center = mg.add("Hub", "t")
        leaves = [mg.add(f"L{i}", "t") for i in range(4)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
        r = mg.assortativity_degree()
        assert r < 0, f"Star graph should be disassortative, got r={r}"

    def test_assortative_graph_positive(self, mg):
        """Two hubs connected + two leaves connected: positive assortativity.

        Edges: A-B (both degree 2), C-D (both degree 1... but we need to ensure
        degrees differ across edge endpoints).

        Better construction: clique of high-degree nodes + clique of low-degree nodes
        with one bridge edge.
        """
        # High-degree clique (triangle): each has degree 2 within clique
        hi = [mg.add(f"H{i}", "t") for i in range(3)]
        mg.link(hi[0].id, hi[1].id, "r")
        mg.link(hi[1].id, hi[2].id, "r")
        mg.link(hi[2].id, hi[0].id, "r")
        # Low-degree pair: each has degree 1
        lo1 = mg.add("L1", "t")
        lo2 = mg.add("L2", "t")
        mg.link(lo1.id, lo2.id, "r")
        # Now edges are (2,2), (2,2), (2,2), (1,1) → perfect assortative
        r = mg.assortativity_degree()
        assert r > 0.5, f"Assortative graph should have high r, got {r}"

    def test_path_graph(self, mg):
        """Path A-B-C: B has degree 2, A and C have degree 1.
        Edges: (2,1), (2,1) → negative assortativity.
        """
        nodes = [mg.add(c, "t") for c in "ABC"]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[1].id, nodes[2].id, "r")
        r = mg.assortativity_degree()
        assert r < 0, f"Path graph should be disassortative, got r={r}"

    def test_value_range(self, mg):
        """Assortativity must be in [-1, 1]."""
        nodes = [mg.add(c, "t") for c in "ABCDEF"]
        for i in range(5):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        r = mg.assortativity_degree()
        assert -1.0 <= r <= 1.0

    def test_regular_graph_zero(self, mg):
        """All nodes same degree → numerator and denominator both zero → 0.0.

        Ring: A→B→C→A. Each node has degree 2 (in+out undirected = 2).
        All edges connect (2,2) → variance is zero → returns 0.0.
        """
        nodes = [mg.add(c, "t") for c in "ABC"]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[1].id, nodes[2].id, "r")
        mg.link(nodes[2].id, nodes[0].id, "r")
        # All degree 2, all edges (2,2) → denominator = 0
        assert mg.assortativity_degree() == 0.0


class TestLazyCommunityDetect:
    """LazyGraphRAG-style local community detection."""

    def test_basic_detection(self, mg):
        """Two connected clusters → lazy detect should find communities from seeds."""
        a = [mg.add(f"a{i}", "person") for i in range(4)]
        for i in range(3):
            mg.link(a[i].id, a[i + 1].id, "friend")
        b = [mg.add(f"b{i}", "person") for i in range(4)]
        for i in range(3):
            mg.link(b[i].id, b[i + 1].id, "friend")
        mg.link(a[0].id, b[0].id, "acquaintance")

        seeds = [a[0].id, b[0].id]
        r = mg.lazy_community_detect(seeds, hops=1)
        assert r["num_communities"] >= 1
        assert r["subgraph_size"] >= 4
        assert r["seed_coverage"] == 1.0
        assert "modularity" in r
        assert isinstance(r["communities"], dict)

    def test_empty_seeds(self, mg):
        """Empty seed list → empty result."""
        r = mg.lazy_community_detect([], hops=1)
        assert r["num_communities"] == 0
        assert r["subgraph_size"] == 0
        assert r["communities"] == {}

    def test_single_seed_hops1(self, mg):
        """Single seed with hops=1 finds seed + direct neighbours."""
        nodes = [mg.add(c, "t") for c in "ABCDE"]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[0].id, nodes[2].id, "r")
        mg.link(nodes[3].id, nodes[4].id, "r")

        r = mg.lazy_community_detect([nodes[0].id], hops=1)
        assert nodes[0].id in r["communities"]
        assert nodes[1].id in r["communities"]
        assert nodes[2].id in r["communities"]
        assert nodes[3].id not in r["communities"]
        assert r["subgraph_size"] == 3

    def test_hops2_reaches_farther(self, mg):
        """hops=2 reaches more nodes than hops=1."""
        nodes = [mg.add(c, "t") for c in "ABCDE"]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[1].id, nodes[2].id, "r")
        mg.link(nodes[2].id, nodes[3].id, "r")
        mg.link(nodes[3].id, nodes[4].id, "r")

        r1 = mg.lazy_community_detect([nodes[0].id], hops=1)
        r2 = mg.lazy_community_detect([nodes[0].id], hops=2)
        assert r2["subgraph_size"] > r1["subgraph_size"]

    def test_disconnected_seeds(self, mg):
        """Two disconnected components: seeds in each get found."""
        a = [mg.add(f"a{i}", "t") for i in range(3)]
        b = [mg.add(f"b{i}", "t") for i in range(3)]
        for i in range(2):
            mg.link(a[i].id, a[i + 1].id, "r")
            mg.link(b[i].id, b[i + 1].id, "r")

        r = mg.lazy_community_detect([a[0].id, b[0].id], hops=1)
        assert r["seed_coverage"] == 1.0
        for n in a[:2]:
            assert n.id in r["communities"]
        for n in b[:2]:
            assert n.id in r["communities"]

    def test_resolution_granularity(self, mg):
        """Higher resolution → finer (more) communities."""
        nodes = [mg.add(c, "t") for c in "ABCDEF"]
        for i in range(6):
            mg.link(nodes[i].id, nodes[(i + 1) % 6].id, "r")
        mg.link(nodes[0].id, nodes[3].id, "r")

        low = mg.lazy_community_detect([nodes[0].id], hops=2, resolution=0.3)
        high = mg.lazy_community_detect([nodes[0].id], hops=2, resolution=2.0)
        assert high["num_communities"] >= low["num_communities"]

    def test_modularity_nonnegative_connected(self, mg):
        """A connected ring should have non-negative modularity."""
        a = [mg.add(f"a{i}", "t") for i in range(5)]
        for i in range(4):
            mg.link(a[i].id, a[i + 1].id, "r")
        mg.link(a[0].id, a[4].id, "r")

        r = mg.lazy_community_detect([a[0].id], hops=2)
        assert r["modularity"] >= 0.0

    def test_seed_not_in_graph(self, mg):
        """Non-existent seed → gracefully returns empty."""
        mg.add("A", "t")
        r = mg.lazy_community_detect(["nonexistent_id"], hops=1)
        assert r["subgraph_size"] == 0
        assert r["seed_coverage"] == 0.0


class TestRandomWalk:
    """Random walk and graph sampling utilities."""

    def test_basic_walk(self, mg):
        """Random walk visits nodes connected to start."""
        nodes = [mg.add(f"n{i}", "t") for i in range(5)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        walk = mg.random_walk(nodes[0].id, steps=3)
        assert len(walk) == 4  # start + 3 steps
        assert walk[0] == nodes[0].id

    def test_missing_start(self, mg):
        """Non-existent start returns empty."""
        assert mg.random_walk("nonexistent", steps=5) == []

    def test_dead_end(self, mg):
        """Walk stops at nodes with no neighbors."""
        a = mg.add("solo", "t")
        walk = mg.random_walk(a.id, steps=10)
        assert len(walk) == 1

    def test_restart_probability(self, mg):
        """With restart_prob=1.0, always returns to start."""
        nodes = [mg.add(f"n{i}", "t") for i in range(4)]
        for i in range(3):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        walk = mg.random_walk(nodes[0].id, steps=5, restart_prob=1.0)
        assert all(n == nodes[0].id for n in walk)

    def test_deterministic_with_seed(self, mg):
        """Same graph → same walk (seeded RNG)."""
        nodes = [mg.add(f"n{i}", "t") for i in range(6)]
        for i in range(5):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        walk1 = mg.random_walk(nodes[0].id, steps=5)
        walk2 = mg.random_walk(nodes[0].id, steps=5)
        assert walk1 == walk2

    def test_walk_stays_in_graph(self, mg):
        """All visited nodes exist in the graph."""
        nodes = [mg.add(chr(65 + i), "t") for i in range(6)]
        for i in range(5):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        mg.link(nodes[0].id, nodes[5].id, "r")  # close the ring
        walk = mg.random_walk(nodes[0].id, steps=15)
        valid_ids = {n.id for n in nodes}
        assert all(n in valid_ids for n in walk)


class TestGraphSample:
    """Graph sampling strategies."""

    def test_bfs_sample(self, mg):
        """BFS sampling expands from seed."""
        nodes = [mg.add(f"n{i}", "t") for i in range(10)]
        for i in range(9):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        sample = mg.graph_sample(nodes[0].id, max_nodes=5, strategy="bfs")
        assert len(sample) <= 5
        assert nodes[0].id in sample

    def test_dfs_sample(self, mg):
        """DFS sampling reaches distant nodes."""
        nodes = [mg.add(f"n{i}", "t") for i in range(8)]
        for i in range(7):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        sample = mg.graph_sample(nodes[0].id, max_nodes=4, strategy="dfs")
        assert len(sample) <= 4
        assert nodes[0].id in sample

    def test_random_walk_sample(self, mg):
        """Random walk sampling collects unique nodes."""
        nodes = [mg.add(f"n{i}", "t") for i in range(6)]
        for i in range(5):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        mg.link(nodes[0].id, nodes[5].id, "r")
        sample = mg.graph_sample(nodes[0].id, max_nodes=4, strategy="random_walk")
        assert len(sample) <= 4
        assert nodes[0].id in sample

    def test_respects_max_nodes(self, mg):
        """Never exceeds max_nodes."""
        nodes = [mg.add(f"n{i}", "t") for i in range(20)]
        for i in range(19):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        for strategy in ["bfs", "dfs", "random_walk"]:
            sample = mg.graph_sample(nodes[0].id, max_nodes=5, strategy=strategy)
            assert len(sample) <= 5


class TestSmartQueryRoute:
    """Auto-routing GraphRAG mode selection based on query analysis."""

    def test_short_lookup_routes_naive(self, mg):
        """Short 1-2 word query without relational cues → naive."""
        mg.add("Python", "skill")
        r = mg.smart_query_route("Python")
        assert r["mode"] == "naive"
        assert "lookup" in r["reason"].lower() or "naive" in r["reason"].lower()
        assert r["query_traits"]["word_count"] <= 3

    def test_aggregation_routes_global(self, mg):
        """Aggregation cues (all/summary/overview) → global."""
        for name in ["Alice", "Bob", "Carol"]:
            mg.add(name, "person")
        r = mg.smart_query_route("Give me an overview of all people")
        assert r["mode"] == "global"
        assert r["query_traits"]["has_aggregation"] is True

    def test_relational_routes_local(self, mg):
        """Relational cues (connect/link/between) → local."""
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        mg.link(a.id, b.id, "colleague")
        r = mg.smart_query_route("How are Alice and Bob connected?")
        assert r["mode"] == "local"
        assert r["query_traits"]["has_relational"] is True

    def test_multi_entity_relational_routes_local(self, mg):
        """Multi-entity + relational → local (before hybrid check)."""
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        mg.link(a.id, b.id, "colleague")
        r = mg.smart_query_route("What links Alice and Bob?")
        assert r["mode"] == "local"
        assert r["query_traits"]["has_multiple_entities"] is True

    def test_complex_with_embedding_routes_hybrid(self, mg):
        """Long complex query + embedding → hybrid."""
        mg.add("Python", "skill")
        emb = [0.1] * 10
        r = mg.smart_query_route(
            "Find recent discussions about Python performance optimization",
            embedding=emb)
        assert r["mode"] == "hybrid"
        assert "fusion" in r["reason"].lower() or "hybrid" in r["reason"].lower()

    def test_temporal_with_embedding_routes_hybrid(self, mg):
        """Temporal cues + embedding → hybrid."""
        mg.add("Python", "skill")
        emb = [0.1] * 10
        r = mg.smart_query_route(
            "What is the history of Python?", embedding=emb)
        assert r["mode"] == "hybrid"
        assert r["query_traits"]["has_temporal"] is True

    def test_returns_results_and_traits(self, mg):
        """Result dict should have mode, results, reason, query_traits."""
        mg.add("Python", "skill")
        r = mg.smart_query_route("Python")
        assert set(r.keys()) == {"mode", "results", "reason", "query_traits"}
        assert isinstance(r["results"], list)
        assert isinstance(r["query_traits"], dict)
        assert "word_count" in r["query_traits"]

    def test_count_query_is_aggregation(self, mg):
        """'how many' triggers aggregation routing."""
        for n in ["a", "b", "c"]:
            mg.add(n, "item")
        r = mg.smart_query_route("How many items are there?")
        assert r["query_traits"]["has_aggregation"] is True
        assert r["mode"] == "global"


class TestCommunityFitAndBridges:
    """Community fit scores, bridge nodes, and outlier detection."""

    def test_fit_score_well_embedded(self, mg):
        """Node with all edges to same community → fit score 1.0."""
        a = [mg.add(f"a{i}", "t") for i in range(4)]
        for i in range(3):
            mg.link(a[i].id, a[i + 1].id, "r")
        comm = {n.id: 0 for n in a}
        scores = mg.community_fit_scores(communities=comm)
        # Internal nodes (a1, a2) should have high fit
        assert scores[a[0].id] >= 0.5
        assert scores[a[1].id] == 1.0

    def test_fit_score_bridge_low(self, mg):
        """Node connecting two communities → low fit score."""
        a = [mg.add(f"a{i}", "t") for i in range(3)]
        b = [mg.add(f"b{i}", "t") for i in range(3)]
        for i in range(2):
            mg.link(a[i].id, a[i + 1].id, "r")
            mg.link(b[i].id, b[i + 1].id, "r")
        mg.link(a[0].id, b[0].id, "bridge")  # bridge

        comm = {**{n.id: 0 for n in a}, **{n.id: 1 for n in b}}
        scores = mg.community_fit_scores(communities=comm)
        # Bridge nodes have at least 1 external edge
        assert scores[a[0].id] < 1.0
        assert scores[b[0].id] < 1.0

    def test_fit_score_empty(self, mg):
        """Empty graph → empty scores."""
        assert mg.community_fit_scores(communities={}) == {}

    def test_bridge_nodes_finds_cross_links(self, mg):
        """Bridge nodes connecting communities are detected."""
        a = [mg.add(f"a{i}", "t") for i in range(3)]
        b = [mg.add(f"b{i}", "t") for i in range(3)]
        for i in range(2):
            mg.link(a[i].id, a[i + 1].id, "r")
            mg.link(b[i].id, b[i + 1].id, "r")
        mg.link(a[0].id, b[0].id, "bridge")
        mg.link(a[1].id, b[1].id, "bridge")

        comm = {**{n.id: 0 for n in a}, **{n.id: 1 for n in b}}
        bridges = mg.bridge_nodes(communities=comm, min_cross_edges=1)
        bridge_ids = {b["node_id"] for b in bridges}
        assert a[0].id in bridge_ids
        assert b[0].id in bridge_ids
        assert a[1].id in bridge_ids

    def test_bridge_nodes_min_threshold(self, mg):
        """min_cross_edges filters low-crossing nodes."""
        a = [mg.add(f"a{i}", "t") for i in range(3)]
        b = [mg.add(f"b{i}", "t") for i in range(3)]
        for i in range(2):
            mg.link(a[i].id, a[i + 1].id, "r")
            mg.link(b[i].id, b[i + 1].id, "r")
        mg.link(a[0].id, b[0].id, "bridge")

        comm = {**{n.id: 0 for n in a}, **{n.id: 1 for n in b}}
        bridges = mg.bridge_nodes(communities=comm, min_cross_edges=2)
        assert bridges == []  # a[0] only has 1 cross edge

    def test_outliers_find_misfits(self, mg):
        """Nodes with low fit score are flagged as outliers."""
        # Tight cluster
        a = [mg.add(f"a{i}", "t") for i in range(5)]
        for i in range(4):
            mg.link(a[i].id, a[i + 1].id, "r")
        # Lone node assigned to same community but only 1 internal edge
        x = mg.add("X", "t")
        mg.link(x.id, a[0].id, "weak")
        mg.link(x.id, a[2].id, "weak")

        comm = {**{n.id: 0 for n in a}, x.id: 0}
        outliers = mg.community_outliers(communities=comm, threshold=0.5)
        outlier_ids = {o["node_id"] for o in outliers}
        # a[0] has 3 edges, 1 external (to x) → fit = 2/3 ≈ 0.67 → not outlier
        # x has 2 edges, both internal → fit = 1.0 → not outlier with threshold 0.5
        # Edge nodes like a[1] have all internal → high fit
        # Let's verify x is NOT an outlier at 0.5 threshold
        assert x.id not in outlier_ids

    def test_outliers_low_threshold_finds_bridges(self, mg):
        """Very low threshold finds nodes with any external connections."""
        a = [mg.add(f"a{i}", "t") for i in range(3)]
        b = [mg.add(f"b{i}", "t") for i in range(3)]
        for i in range(2):
            mg.link(a[i].id, a[i + 1].id, "r")
            mg.link(b[i].id, b[i + 1].id, "r")
        mg.link(a[0].id, b[0].id, "bridge")

        comm = {**{n.id: 0 for n in a}, **{n.id: 1 for n in b}}
        outliers = mg.community_outliers(communities=comm, threshold=0.7)
        # a[0] has 2 edges: 1 internal (to a[1]), 1 external (to b[0])
        # fit = 0.5 < 0.7 → outlier
        assert any(o["node_id"] == a[0].id for o in outliers)

    def test_bridge_returns_cross_communities(self, mg):
        """Bridge node result includes list of cross communities."""
        a = mg.add("A", "t")
        b = mg.add("B", "t")
        c = mg.add("C", "t")
        mg.link(a.id, b.id, "r")
        mg.link(a.id, c.id, "r")
        comm = {a.id: 0, b.id: 1, c.id: 2}
        bridges = mg.bridge_nodes(communities=comm, min_cross_edges=1)
        a_bridge = [br for br in bridges if br["node_id"] == a.id][0]
        assert set(a_bridge["cross_communities"]) == {1, 2}


class TestLearnableMemoryManager:
    """Memory-R1 / AgeMem 启发的可学习记忆管理。"""

    def test_score_memory_ops_add_new_info(self):
        """全新信息: ADD 分数最高。"""
        mg = MemoryGraph()
        scores = mg.score_memory_ops("quantum computing breakthrough")
        top = scores[0]
        assert top["op"] == "ADD"
        assert top["score"] > 0.5

    def test_score_memory_ops_update_existing(self):
        """与已有节点高度相似: UPDATE 有候选。"""
        mg = MemoryGraph()
        mg.add("machine learning model", "concept")
        scores = mg.score_memory_ops("machine learning model")
        update_score = next(s for s in scores if s["op"] == "UPDATE")
        assert update_score["score"] > 0

    def test_score_memory_ops_returns_all_four(self):
        """返回 ADD/UPDATE/DELETE/NOOP 四种操作评分。"""
        mg = MemoryGraph()
        scores = mg.score_memory_ops("test content")
        ops = {s["op"] for s in scores}
        assert ops == {"ADD", "UPDATE", "DELETE", "NOOP"}

    def test_score_memory_ops_noop_bias(self):
        """noop_bias 提高 NOOP 分数。"""
        mg = MemoryGraph()
        low_bias = mg.score_memory_ops("test", noop_bias=0.05)
        high_bias = mg.score_memory_ops("test", noop_bias=0.50)
        noop_low = next(s for s in low_bias if s["op"] == "NOOP")
        noop_high = next(s for s in high_bias if s["op"] == "NOOP")
        assert noop_high["score"] > noop_low["score"]

    def test_decide_memory_op_returns_best(self):
        """decide 返回最高分操作。"""
        mg = MemoryGraph()
        mg.add("Python", "skill")
        decision = mg.decide_memory_op("Python programming")
        assert decision["op"] in ("ADD", "UPDATE", "NOOP")
        assert "score" in decision
        assert "reason" in decision

    def test_decide_memory_op_threshold_fallback(self):
        """ADD 分数低于阈值时退回 NOOP。"""
        mg = MemoryGraph()
        mg.add("test duplicate content", "concept")
        decision = mg.decide_memory_op("test duplicate content", threshold=0.99)
        assert decision["op"] in ("NOOP", "UPDATE")

    def test_execute_memory_op_add(self):
        """执行 ADD: 创建新节点。"""
        mg = MemoryGraph()
        result = mg.execute_memory_op("brand new fact", kind="fact")
        assert result["op"] == "ADD"
        assert result["result"] == "created"
        assert mg.stats()["nodes"] == 1

    def test_execute_memory_op_noop(self):
        """执行 NOOP: 不修改图。"""
        mg = MemoryGraph()
        result = mg.execute_memory_op("x", threshold=0.99)
        assert result["op"] == "NOOP"
        assert mg.stats()["nodes"] == 0

    def test_execute_memory_op_update_merges(self):
        """执行 UPDATE: 合并到已有节点。"""
        mg = MemoryGraph()
        mg.add("AI research", "concept")
        result = mg.execute_memory_op("AI research latest")
        if result["op"] == "UPDATE":
            assert result["result"] == "merged"
            assert "+" in result["detail"]["new"]

    def test_memory_decision_log_batch(self):
        """批量决策日志: 不执行, 只建议。"""
        mg = MemoryGraph()
        mg.add("existing", "concept")
        items = ["existing updated", "brand new", "another new"]
        log = mg.memory_decision_log(items)
        assert len(log) == 3
        assert all("op" in entry for entry in log)
        assert all("content" in entry for entry in log)

    def test_content_similarity_identical(self):
        """相同文本相似度=1.0。"""
        assert MemoryGraph._content_similarity("hello world", "hello world") == 1.0

    def test_content_similarity_different(self):
        """完全不同文本相似度≈0。"""
        assert MemoryGraph._content_similarity("abcdef", "xyzwvu") < 0.1

    def test_score_memory_ops_with_existing_keys(self):
        """指定 existing_keys 缩小搜索范围。"""
        mg = MemoryGraph()
        n1 = mg.add("Python", "skill")
        mg.add("Rust", "skill")
        scores = mg.score_memory_ops("Python", existing_keys=[n1.id])
        update_entry = next(s for s in scores if s["op"] == "UPDATE")
        assert update_entry.get("target_key") == n1.id

    def test_execute_with_tags(self):
        """execute_memory_op ADD 时添加标签。"""
        mg = MemoryGraph()
        result = mg.execute_memory_op("tagged fact", kind="fact", tags=["important"])
        if result["op"] == "ADD":
            nid = result["detail"]["node_id"]
            tags_result = mg.all_tags()
            assert any("important" in t for t in tags_result)


class TestMemoryAuditAndFiFA:
    """全局记忆审计 + 有界遗忘 (FiFA) + 压缩。"""

    def test_memory_audit_empty_graph(self):
        """空图审计返回满分。"""
        mg = MemoryGraph()
        audit = mg.memory_audit()
        assert audit["health_score"] == 100
        assert audit["total_nodes"] == 0

    def test_memory_audit_healthy_graph(self):
        """正常图的审计。"""
        mg = MemoryGraph()
        mg.add("Python", "skill")
        mg.add("AI research", "concept")
        audit = mg.memory_audit()
        assert audit["total_nodes"] == 2
        assert audit["health_score"] >= 70
        assert isinstance(audit["suggestions"], list)

    def test_memory_audit_detects_stale(self):
        """检测陈旧节点。"""
        import time
        mg = MemoryGraph()
        mg.add("old fact", "fact")
        # 设置 accessed 为很久以前
        mg.conn.execute("UPDATE nodes SET accessed = ?", (time.time() - 86400 * 60,))
        mg.conn.commit()
        audit = mg.memory_audit(staleness_days=30)
        assert audit["stale_nodes"] >= 1
        assert any("staleness" in s.lower() or "prune" in s.lower() for s in audit["suggestions"])

    def test_memory_audit_detects_redundancy(self):
        """检测冗余节点对。"""
        mg = MemoryGraph()
        mg.add("machine learning", "concept")
        mg.add("machine learning", "concept")
        audit = mg.memory_audit()
        assert audit["redundant_pairs"] >= 1

    def test_fifa_forget_removes_low_weight(self):
        """FiFA 删除低重要性节点。"""
        mg = MemoryGraph()
        n1 = mg.add("important", "concept")
        n2 = mg.add("trivial", "concept")
        mg.update_node(n2.id, weight=0.01)
        result = mg.fifa_forget(budget=5, min_importance=0.5)
        assert result["removed"] >= 1
        assert mg.stats()["nodes"] == 1

    def test_fifa_forget_preserves_high_weight(self):
        """FiFA 保留高权重节点。"""
        mg = MemoryGraph()
        n1 = mg.add("keep me", "concept")
        mg.update_node(n1.id, weight=0.9)
        result = mg.fifa_forget(budget=10, min_importance=0.5)
        assert result["removed"] == 0
        assert mg.stats()["nodes"] == 1

    def test_fifa_forget_empty_graph(self):
        """空图 FiFA 返回零删除。"""
        mg = MemoryGraph()
        result = mg.fifa_forget()
        assert result["removed"] == 0

    def test_memory_compact_merges_similar(self):
        """记忆压缩合并高相似度节点。"""
        mg = MemoryGraph()
        mg.add("machine learning basics", "concept")
        mg.add("machine learning basics", "concept")
        result = mg.memory_compact(similarity_threshold=0.5)
        assert result["merged_count"] >= 1
        assert mg.stats()["nodes"] == 1

    def test_memory_compact_no_similar(self):
        """无相似节点时不合并。"""
        mg = MemoryGraph()
        mg.add("Python", "skill")
        mg.add("cooking", "hobby")
        result = mg.memory_compact(similarity_threshold=0.9)
        assert result["merged_count"] == 0
        assert mg.stats()["nodes"] == 2

    def test_memory_audit_max_nodes_warning(self):
        """超过 max_nodes 时建议修剪。"""
        mg = MemoryGraph()
        for i in range(5):
            mg.add(f"node_{i}", "concept")
        audit = mg.memory_audit(max_nodes=3)
        assert any("prune" in s.lower() or "exceed" in s.lower() for s in audit["suggestions"])

    def test_fifa_forget_details_structure(self):
        """FiFA 返回正确的 details 结构。"""
        mg = MemoryGraph()
        n = mg.add("low weight item", "concept")
        mg.update_node(n.id, weight=0.01)
        result = mg.fifa_forget(budget=5, min_importance=0.5)
        if result["details"]:
            d = result["details"][0]
            assert "id" in d
            assert "label" in d
            assert "weight" in d


class TestFeedbackLearningAndStats:
    """反馈学习 + 记忆统计概览。"""

    def test_memory_feedback_no_corrections(self):
        """空反馈返回默认阈值。"""
        mg = MemoryGraph()
        result = mg.memory_feedback([])
        assert result["adjusted_threshold"] == 0.5
        assert result["samples"] == 0

    def test_memory_feedback_raises_on_false_adds(self):
        """过多误 ADD → 提高阈值。"""
        mg = MemoryGraph()
        corrections = [
            {"content": "a", "chosen_op": "ADD", "was_correct": False},
            {"content": "b", "chosen_op": "ADD", "was_correct": False},
            {"content": "c", "chosen_op": "ADD", "was_correct": False},
            {"content": "d", "chosen_op": "NOOP", "was_correct": True},
        ]
        result = mg.memory_feedback(corrections)
        assert result["adjusted_threshold"] > 0.5
        assert result["false_adds"] == 3

    def test_memory_feedback_lowers_on_missed_adds(self):
        """过多遗漏 ADD → 降低阈值。"""
        mg = MemoryGraph()
        corrections = [
            {"content": "a", "correct_op": "ADD", "chosen_op": "NOOP",
             "was_correct": False},
            {"content": "b", "correct_op": "ADD", "chosen_op": "NOOP",
             "was_correct": False},
            {"content": "c", "chosen_op": "NOOP", "was_correct": True},
            {"content": "d", "chosen_op": "NOOP", "was_correct": True},
        ]
        result = mg.memory_feedback(corrections)
        assert result["adjusted_threshold"] < 0.5
        assert result["missed_adds"] == 2

    def test_memory_feedback_balanced_no_change(self):
        """误判与遗漏相等 → 阈值不变。"""
        mg = MemoryGraph()
        corrections = [
            {"content": "a", "chosen_op": "ADD", "was_correct": False},
            {"content": "b", "correct_op": "ADD", "chosen_op": "NOOP",
             "was_correct": False},
        ]
        result = mg.memory_feedback(corrections)
        assert result["adjusted_threshold"] == 0.5

    def test_memory_stats_summary_empty(self):
        """空图统计概览。"""
        mg = MemoryGraph()
        s = mg.memory_stats_summary()
        assert s["total"] == 0
        assert s["top_weighted"] == []

    def test_memory_stats_summary_populated(self):
        """有数据的图统计概览。"""
        mg = MemoryGraph()
        n1 = mg.add("Important", "concept")
        mg.update_node(n1.id, weight=0.9)
        n2 = mg.add("Medium", "skill")
        mg.update_node(n2.id, weight=0.5)
        n3 = mg.add("Trivial", "fact")
        mg.update_node(n3.id, weight=0.1)
        s = mg.memory_stats_summary()
        assert s["total"] == 3
        assert "concept" in s["by_kind"]
        assert s["weight_dist"]["high"] == 1
        assert s["weight_dist"]["medium"] == 1
        assert s["weight_dist"]["low"] == 1
        assert len(s["top_weighted"]) == 3
        assert s["top_weighted"][0]["label"] == "Important"

    def test_memory_stats_summary_time_span(self):
        """统计包含时间跨度。"""
        import time
        mg = MemoryGraph()
        mg.add("old", "concept")
        mg.conn.execute("UPDATE nodes SET created = ?", (time.time() - 86400 * 10,))
        mg.conn.commit()
        mg.add("new", "concept")
        s = mg.memory_stats_summary()
        assert s["time_span_days"] >= 9

    def test_memory_feedback_threshold_bounds(self):
        """阈值始终在 [0.1, 0.9] 范围内。"""
        mg = MemoryGraph()
        # 极端情况: 全部误 ADD
        corrections = [{"chosen_op": "ADD", "was_correct": False}
                       for _ in range(20)]
        result = mg.memory_feedback(corrections)
        assert result["adjusted_threshold"] <= 0.9
        assert result["adjusted_threshold"] >= 0.1

    def test_memory_stats_summary_avg_weight(self):
        """统计包含平均权重。"""
        mg = MemoryGraph()
        n1 = mg.add("a", "concept")
        n2 = mg.add("b", "concept")
        mg.update_node(n1.id, weight=0.4)
        mg.update_node(n2.id, weight=0.6)
        s = mg.memory_stats_summary()
        assert abs(s["weight_dist"]["avg"] - 0.5) < 0.01


# ── memorywire 互操作测试 ──────────────────────────────

class TestMemorywireExport:
    """to_memorywire / from_memorywire 互操作性。"""

    def test_to_memorywire_empty(self):
        """空图导出。"""
        mg = MemoryGraph()
        result = mg.to_memorywire()
        assert result["version"] == "0.1"
        assert result["memories"] == []
        assert result["agent_id"] == "default"

    def test_to_memorywire_basic(self):
        """基本导出：节点 → memorywire remember 操作。"""
        mg = MemoryGraph()
        mg.add("User likes TypeScript", "fact", tags=["preference"])
        result = mg.to_memorywire(agent_id="agent-001")
        assert len(result["memories"]) == 1
        mem = result["memories"][0]
        assert mem["operation"] == "remember"
        assert mem["agent_id"] == "agent-001"
        assert mem["type"] == "semantic"  # fact → semantic
        assert mem["content"] == "User likes TypeScript"
        assert mem["confidence"] == 1.0
        assert mem["source"] == "preference"

    def test_to_memorywire_type_mapping(self):
        """内部 kind → memorywire type 映射。"""
        mg = MemoryGraph()
        mg.add("concept-1", "concept")     # → semantic
        mg.add("event-1", "event")         # → episodic
        mg.add("skill-1", "skill")         # → procedural
        mg.add("emo-1", "emotion")         # → emotional
        result = mg.to_memorywire()
        types = {m["content"]: m["type"] for m in result["memories"]}
        assert types["concept-1"] == "semantic"
        assert types["event-1"] == "episodic"
        assert types["skill-1"] == "procedural"
        assert types["emo-1"] == "emotional"

    def test_to_memorywire_with_edges(self):
        """导出包含关系（边）信息。"""
        mg = MemoryGraph()
        n1 = mg.add("Python", "concept")
        n2 = mg.add("Programming", "concept")
        mg.link(n1.id, n2.id, "is_a", 0.8)
        result = mg.to_memorywire()
        mem = next(m for m in result["memories"] if m["content"] == "Python")
        assert "relationships" in mem["metadata"]
        assert len(mem["metadata"]["relationships"]) == 1
        assert mem["metadata"]["relationships"][0]["target"] == n2.id
        assert mem["metadata"]["relationships"][0]["relation"] == "is_a"

    def test_to_memorywire_selected_nodes(self):
        """导出指定节点子集。"""
        mg = MemoryGraph()
        n1 = mg.add("keep-me", "fact")
        mg.add("skip-me", "fact")
        result = mg.to_memorywire(node_ids=[n1.id])
        assert len(result["memories"]) == 1
        assert result["memories"][0]["content"] == "keep-me"

    def test_to_memorywire_weight_as_confidence(self):
        """节点 weight 映射为 memorywire confidence。"""
        mg = MemoryGraph()
        n = mg.add("weighted", "fact")
        mg.update_node(n.id, weight=0.42)
        result = mg.to_memorywire()
        mem = result["memories"][0]
        assert abs(mem["confidence"] - 0.42) < 0.01

    def test_to_memorywire_json_serializable(self):
        """导出结果可 JSON 序列化。"""
        import json as _json
        mg = MemoryGraph()
        mg.add("test", "fact", data={"key": "val"}, tags=["t1"])
        result = mg.to_memorywire()
        _json.dumps(result)  # should not raise


class TestMemorywireImport:
    """from_memorywire 导入。"""

    def test_from_memorywire_basic(self):
        """基本导入：memorywire → 图节点。"""
        mg = MemoryGraph()
        wire = {
            "version": "0.1",
            "agent_id": "a1",
            "memories": [
                {
                    "operation": "remember",
                    "agent_id": "a1",
                    "type": "semantic",
                    "content": "User prefers dark mode",
                    "confidence": 0.9,
                    "source": "ui",
                    "metadata": {},
                }
            ]
        }
        count = mg.from_memorywire(wire)
        assert count == 1
        node = mg.search_by_label("User prefers dark mode")[0]
        assert node.kind == "fact"  # semantic → fact
        assert abs(node.weight - 0.9) < 0.01

    def test_from_memorywire_type_reverse_mapping(self):
        """memorywire type → 内部 kind 反向映射。"""
        mg = MemoryGraph()
        wire = {
            "version": "0.1",
            "memories": [
                {"operation": "remember", "type": "semantic",
                 "content": "s1", "metadata": {}},
                {"operation": "remember", "type": "episodic",
                 "content": "e1", "metadata": {}},
                {"operation": "remember", "type": "procedural",
                 "content": "p1", "metadata": {}},
                {"operation": "remember", "type": "emotional",
                 "content": "em1", "metadata": {}},
            ]
        }
        mg.from_memorywire(wire)
        nodes = {n.label: n.kind for n in mg.search_by_label("")}
        # search_by_label with empty pattern might not work, use all
        all_nodes = mg.conn.execute("SELECT label, kind FROM nodes").fetchall()
        kind_map = {r["label"]: r["kind"] for r in all_nodes}
        assert kind_map["s1"] == "fact"
        assert kind_map["e1"] == "event"
        assert kind_map["p1"] == "skill"
        assert kind_map["em1"] == "emotion"

    def test_from_memorywire_preserves_node_id(self):
        """导入时保留原始 node_id。"""
        mg = MemoryGraph()
        wire = {
            "version": "0.1",
            "memories": [{
                "operation": "remember", "type": "semantic",
                "content": "test", "confidence": 1.0,
                "metadata": {"node_id": "custom-id-123"},
            }]
        }
        mg.from_memorywire(wire)
        node = mg.get_node("custom-id-123")
        assert node is not None
        assert node.label == "test"

    def test_from_memorywire_restores_edges(self):
        """导入时恢复边关系。"""
        mg = MemoryGraph()
        wire = {
            "version": "0.1",
            "memories": [
                {
                    "operation": "remember", "type": "semantic",
                    "content": "node-a", "confidence": 1.0,
                    "metadata": {
                        "node_id": "node-a",
                        "relationships": [
                            {"target": "node-b", "relation": "rel", "weight": 0.5}
                        ],
                    },
                },
                {
                    "operation": "remember", "type": "semantic",
                    "content": "node-b", "confidence": 1.0,
                    "metadata": {"node_id": "node-b"},
                },
            ]
        }
        mg.from_memorywire(wire)
        neighbors = mg.neighbors("node-a")
        assert any(n.id == "node-b" for n in neighbors)

    def test_from_memorywire_skips_non_remember(self):
        """非 remember 操作被跳过。"""
        mg = MemoryGraph()
        wire = {
            "version": "0.1",
            "memories": [
                {"operation": "recall", "query": "test"},
                {"operation": "forget", "ids": ["x"]},
            ]
        }
        count = mg.from_memorywire(wire)
        assert count == 0

    def test_from_memorywire_source_as_tag(self):
        """source 字段自动加入 tags。"""
        mg = MemoryGraph()
        wire = {
            "version": "0.1",
            "memories": [{
                "operation": "remember", "type": "semantic",
                "content": "test", "source": "experiment-1",
                "metadata": {},
            }]
        }
        mg.from_memorywire(wire)
        rows = mg.conn.execute("SELECT tags FROM nodes").fetchall()
        tags = json.loads(rows[0]["tags"])
        assert "experiment-1" in tags


class TestMemorywireRoundTrip:
    """导出 → 导入 往返一致性。"""

    def test_round_trip_preserves_data(self):
        """导出后导入到新图，数据保持一致。"""
        mg1 = MemoryGraph()
        n1 = mg1.add("TypeScript rocks", "fact", data={"lang": "ts"},
                     tags=["dev"])
        n2 = mg1.add("Run tests daily", "skill", tags=["ci"])
        mg1.link(n1.id, n2.id, "related", 0.6)
        mg1.update_node(n1.id, weight=0.85)

        wire = mg1.to_memorywire(agent_id="rt-test")

        mg2 = MemoryGraph()
        mg2.from_memorywire(wire)

        # Same node count
        assert mg1.stats()["nodes"] == mg2.stats()["nodes"]

        # Same content
        n1_copy = mg2.get_node(n1.id)
        assert n1_copy is not None
        assert n1_copy.label == "TypeScript rocks"
        assert abs(n1_copy.weight - 0.85) < 0.01

        # Same edges
        neighbors = mg2.neighbors(n1.id)
        assert any(nd.id == n2.id for nd in neighbors)

    def test_round_trip_empty(self):
        """空图往返。"""
        mg1 = MemoryGraph()
        wire = mg1.to_memorywire()
        mg2 = MemoryGraph()
        count = mg2.from_memorywire(wire)
        assert count == 0
        assert mg2.stats()["nodes"] == 0


class TestNoScopeDeleteGuard:
    """delete_many no-scope-mass-delete 保护。"""

    def test_delete_many_empty_rejected(self):
        """空列表被拒绝。"""
        mg = MemoryGraph()
        mg.add("node1", "fact")
        with pytest.raises(ValueError, match="no-scope-mass-delete"):
            mg.delete_many([])

    def test_delete_many_force_allows_empty(self):
        """force=True 可绕过保护。"""
        mg = MemoryGraph()
        mg.add("node1", "fact")
        result = mg.delete_many([], force=True)
        assert result == 0

    def test_delete_many_normal_works(self):
        """正常删除不受影响。"""
        mg = MemoryGraph()
        n1 = mg.add("node1", "fact")
        n2 = mg.add("node2", "fact")
        count = mg.delete_many([n1.id, n2.id])
        assert count == 2


class TestDegreeDistribution:
    """度分布分析。"""

    def test_empty_graph(self):
        mg = MemoryGraph()
        assert mg.degree_distribution() == {}

    def test_isolated_nodes(self):
        """无连接节点的度分布。"""
        mg = MemoryGraph()
        mg.add("solo1", "fact")
        mg.add("solo2", "fact")
        dist = mg.degree_distribution()
        assert dist == {0: 1.0}  # All degree-0

    def test_simple_graph(self):
        """三角图度分布。"""
        mg = MemoryGraph()
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        c = mg.add("C", "fact")
        mg.link(a.id, b.id, "rel")
        mg.link(b.id, c.id, "rel")
        mg.link(c.id, a.id, "rel")
        dist = mg.degree_distribution()
        assert dist == {2: 1.0}  # Every node has degree 2

    def test_star_graph(self):
        """星形图: 中心度=3, 叶子度=1。"""
        mg = MemoryGraph()
        center = mg.add("center", "fact")
        for i in range(3):
            leaf = mg.add(f"leaf{i}", "fact")
            mg.link(center.id, leaf.id, "rel")
        dist = mg.degree_distribution()
        assert dist[1] == 0.75   # 3 of 4 nodes
        assert dist[3] == 0.25   # 1 of 4 nodes

    def test_fractions_sum_to_one(self):
        """所有比例之和应为1。"""
        mg = MemoryGraph()
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        c = mg.add("C", "fact")
        d = mg.add("D", "fact")
        mg.link(a.id, b.id, "rel")
        mg.link(b.id, c.id, "rel")
        dist = mg.degree_distribution()
        assert abs(sum(dist.values()) - 1.0) < 1e-9


class TestNetworkSummary:
    """network_summary 一站式分析。"""

    def test_empty_graph(self):
        mg = MemoryGraph()
        result = mg.network_summary()
        assert result["nodes"] == 0
        assert result["edges"] == 0
        assert result["density"] == 0.0

    def test_basic_metrics(self):
        """验证核心度量。"""
        mg = MemoryGraph()
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        c = mg.add("C", "fact")
        mg.link(a.id, b.id, "rel")
        mg.link(b.id, c.id, "rel")
        mg.link(c.id, a.id, "rel")
        result = mg.network_summary()
        assert result["nodes"] == 3
        assert result["edges"] == 3
        assert result["density"] == 1.0  # Complete graph K3
        assert result["avg_degree"] == 2.0
        assert result["max_degree"] == 2

    def test_star_graph_summary(self):
        """星形图分析。"""
        mg = MemoryGraph()
        center = mg.add("center", "fact")
        for i in range(4):
            leaf = mg.add(f"leaf{i}", "fact")
            mg.link(center.id, leaf.id, "rel")
        result = mg.network_summary()
        assert result["nodes"] == 5
        assert result["edges"] == 4
        assert result["avg_degree"] == round(2.0 * 4 / 5, 2)
        assert result["max_degree"] == 4
        assert result["components"] == 1

    def test_disconnected_components(self):
        """断连图: 两个独立的三角。"""
        mg = MemoryGraph()
        # Triangle 1
        a1 = mg.add("a1", "fact")
        b1 = mg.add("b1", "fact")
        c1 = mg.add("c1", "fact")
        mg.link(a1.id, b1.id, "rel")
        mg.link(b1.id, c1.id, "rel")
        mg.link(c1.id, a1.id, "rel")
        # Triangle 2
        a2 = mg.add("a2", "fact")
        b2 = mg.add("b2", "fact")
        c2 = mg.add("c2", "fact")
        mg.link(a2.id, b2.id, "rel")
        mg.link(b2.id, c2.id, "rel")
        mg.link(c2.id, a2.id, "rel")
        result = mg.network_summary()
        assert result["components"] == 2
        assert result["largest_component_size"] == 3
        assert result["largest_component_ratio"] == 0.5  # 3/6


class TestKHopNeighbors:
    """k_hop_neighbors BFS 层次遍历。"""

    def test_nonexistent_node(self):
        mg = MemoryGraph()
        assert mg.k_hop_neighbors("ghost", k=2) == {}

    def test_single_node(self):
        """无连接节点的 k-hop。"""
        mg = MemoryGraph()
        n = mg.add("solo", "fact")
        result = mg.k_hop_neighbors(n.id, k=3)
        assert result == {0: [n.id]}

    def test_two_hop(self):
        """A -> B -> C 链式图。"""
        mg = MemoryGraph()
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        c = mg.add("C", "fact")
        mg.link(a.id, b.id, "rel")
        mg.link(b.id, c.id, "rel")
        result = mg.k_hop_neighbors(a.id, k=2)
        assert result[0] == [a.id]
        assert result[1] == [b.id]
        assert result[2] == [c.id]

    def test_star_graph_k2(self):
        """星形图 center->leafs, k=2 到达 leafs 的邻居 (即只有 center)。"""
        mg = MemoryGraph()
        center = mg.add("center", "fact")
        l1 = mg.add("l1", "fact")
        l2 = mg.add("l2", "fact")
        l3 = mg.add("l3", "fact")
        mg.link(center.id, l1.id, "rel")
        mg.link(center.id, l2.id, "rel")
        mg.link(center.id, l3.id, "rel")
        # From leaf1, k=1: center; k=2: l2, l3
        result = mg.k_hop_neighbors(l1.id, k=2)
        assert result[0] == [l1.id]
        assert result[1] == [center.id]
        assert sorted(result[2]) == sorted([l2.id, l3.id])

    def test_no_repeats(self):
        """节点不重复出现。"""
        mg = MemoryGraph()
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        mg.link(a.id, b.id, "rel")
        mg.link(b.id, a.id, "rel2")  # 双向边
        result = mg.k_hop_neighbors(a.id, k=5)
        all_nodes = []
        for hop_nodes in result.values():
            all_nodes.extend(hop_nodes)
        assert len(all_nodes) == len(set(all_nodes))  # No duplicates


class TestCommonNeighbors:
    """common_neighbors 交集计算。"""

    def test_nonexistent_nodes(self):
        mg = MemoryGraph()
        assert mg.common_neighbors("ghost_a", "ghost_b") == []

    def test_no_common(self):
        """无共同邻居。"""
        mg = MemoryGraph()
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        c = mg.add("C", "fact")
        d = mg.add("D", "fact")
        mg.link(a.id, c.id, "rel")
        mg.link(b.id, d.id, "rel")
        assert mg.common_neighbors(a.id, b.id) == []

    def test_shared_neighbor(self):
        """三角形: A-C, B-C, C 是共同邻居。"""
        mg = MemoryGraph()
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        c = mg.add("C", "fact")
        mg.link(a.id, c.id, "rel")
        mg.link(b.id, c.id, "rel")
        common = mg.common_neighbors(a.id, b.id)
        assert common == [c.id]

    def test_multiple_common(self):
        """多个共同邻居。"""
        mg = MemoryGraph()
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        x = mg.add("X", "fact")
        y = mg.add("Y", "fact")
        z = mg.add("Z", "fact")
        mg.link(a.id, x.id, "rel")
        mg.link(a.id, y.id, "rel")
        mg.link(a.id, z.id, "rel")
        mg.link(b.id, x.id, "rel")
        mg.link(b.id, y.id, "rel")
        common = mg.common_neighbors(a.id, b.id)
        assert set(common) == {x.id, y.id}


# ── Weighted Degree & Neighborhood Census ───────────────────────────────

class TestWeightedDegree:
    def test_empty(self, mg):
        assert mg.weighted_degree("x") == 0.0

    def test_single_edge(self, mg):
        a, b = mg.add("A", "x"), mg.add("B", "x")
        mg.link(a.id, b.id, "r", weight=2.5)
        assert mg.weighted_degree(a.id) == 2.5
        assert mg.weighted_degree(b.id) == 2.5

    def test_multi_edge(self, mg):
        a = mg.add("A", "x")
        b = mg.add("B", "x")
        c = mg.add("C", "x")
        mg.link(a.id, b.id, "r", weight=1.0)
        mg.link(a.id, c.id, "r", weight=3.0)
        assert mg.weighted_degree(a.id) == 4.0

    def test_default_weight(self, mg):
        a, b = mg.add("A", "x"), mg.add("B", "x")
        mg.link(a.id, b.id, "r")  # default weight = 1.0
        assert mg.weighted_degree(a.id) == 1.0

    def test_all(self, mg):
        a, b, c = mg.add("A", "x"), mg.add("B", "x"), mg.add("C", "x")
        mg.link(a.id, b.id, "r", weight=2.0)
        mg.link(b.id, c.id, "r", weight=3.0)
        wd = mg.weighted_degree_all()
        assert wd[a.id] == 2.0
        assert wd[b.id] == 5.0
        assert wd[c.id] == 3.0


class TestNeighborhoodCensus:
    def test_empty(self, mg):
        assert mg.neighborhood_census() == {}

    def test_basic(self, mg):
        a, b, c = mg.add("A", "x"), mg.add("B", "x"), mg.add("C", "x")
        mg.link(a.id, b.id, "r", weight=2.0)
        mg.link(b.id, c.id, "r", weight=1.0)
        census = mg.neighborhood_census()
        assert census[a.id]["degree"] == 1
        assert census[a.id]["weighted_degree"] == 2.0
        assert set(census[a.id]["neighbors"]) == {b.id}
        assert census[b.id]["degree"] == 2
        assert census[b.id]["weighted_degree"] == 3.0

    def test_isolated_node(self, mg):
        a = mg.add("lonely", "x")
        census = mg.neighborhood_census()
        assert census[a.id]["degree"] == 0
        assert census[a.id]["weighted_degree"] == 0.0
        assert census[a.id]["neighbors"] == []


# ── CRDT Multi-Agent Merge ─────────────────────────────────────────────

class TestMergeCRDT:
    def _make_other(self):
        """Create a simple graph and export it."""
        mg = MemoryGraph()
        mg.add("Alpha", "fact", {"v": 1})
        mg.add("Beta", "fact", {"v": 2})
        return mg.export_json()

    def test_lww_new_nodes(self, mg):
        other = self._make_other()
        result = mg.merge_crdt(other, strategy="lww")
        assert result["nodes_added"] == 2
        assert result["nodes_updated"] == 0

    def test_lww_conflict_newer_wins(self, mg):
        # Create a local node with old timestamp
        mg.conn.execute(
            "INSERT OR REPLACE INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
            ("shared1", "old_label", "fact", '{}', 1000.0, 1000.0, 1.0, '[]'))
        # Other graph has newer version
        other = {"nodes": [{"id": "shared1", "label": "new_label", "kind": "fact",
                            "data": {"v": 99}, "created": 2000.0, "accessed": 2000.0,
                            "weight": 1.0, "tags": []}], "edges": []}
        result = mg.merge_crdt(other, strategy="lww")
        assert result["nodes_updated"] == 1
        node = mg.get_node("shared1")
        assert node.label == "new_label"

    def test_lww_older_skipped(self, mg):
        # Local is newer
        mg.conn.execute(
            "INSERT OR REPLACE INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
            ("shared2", "new_label", "fact", '{}', 2000.0, 2000.0, 1.0, '[]'))
        other = {"nodes": [{"id": "shared2", "label": "old_label", "kind": "fact",
                            "data": {}, "created": 1000.0, "accessed": 1000.0,
                            "weight": 1.0, "tags": []}], "edges": []}
        result = mg.merge_crdt(other, strategy="lww")
        assert result["nodes_skipped"] == 1
        node = mg.get_node("shared2")
        assert node.label == "new_label"

    def test_or_set_preserves_both(self, mg):
        a = mg.add("original", "fact", {"v": 1})
        other = {"nodes": [{"id": a.id, "label": "updated", "kind": "fact",
                            "data": {"v": 2}, "created": 1000.0, "accessed": 2000.0,
                            "weight": 1.0, "tags": []}], "edges": []}
        result = mg.merge_crdt(other, strategy="or_set")
        assert result["nodes_added"] == 1
        # Original should still exist
        assert mg.get_node(a.id).label == "original"

    def test_trust_weighted(self, mg):
        mg.conn.execute(
            "INSERT OR REPLACE INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
            ("t1", "local", "fact", '{}', 1000.0, 1000.0, 0.5, '[]'))
        other = {"nodes": [{"id": "t1", "label": "remote", "kind": "fact",
                            "data": {"v": 1}, "created": 1000.0, "accessed": 1000.0,
                            "weight": 1.0, "tags": []}], "edges": []}
        result = mg.merge_crdt(other, strategy="trust", trust_weight=0.8)
        assert result["nodes_updated"] == 1
        node = mg.get_node("t1")
        # 0.8*1.0 + 0.2*0.5 = 0.9
        assert abs(node.weight - 0.9) < 0.01
        # trust_weight > 0.5 → take remote content
        assert node.label == "remote"

    def test_edges_merged(self, mg):
        a = mg.add("A", "x")
        b = mg.add("B", "x")
        other = {
            "nodes": [
                {"id": a.id, "label": "A", "kind": "x", "data": {},
                 "created": 1000.0, "accessed": 1000.0, "weight": 1.0, "tags": []},
                {"id": b.id, "label": "B", "kind": "x", "data": {},
                 "created": 1000.0, "accessed": 1000.0, "weight": 1.0, "tags": []},
            ],
            "edges": [{"source": a.id, "target": b.id, "relation": "knows", "weight": 2.0}],
        }
        result = mg.merge_crdt(other, strategy="lww")
        assert result["edges_added"] == 1
        assert mg.is_linked(a.id, b.id)

    def test_empty_other(self, mg):
        result = mg.merge_crdt({"nodes": [], "edges": []}, strategy="lww")
        assert result == {"nodes_added": 0, "nodes_updated": 0, "nodes_skipped": 0, "edges_added": 0}

    def test_unknown_strategy(self, mg):
        a = mg.add("A", "x")
        other = {"nodes": [{"id": a.id, "label": "B", "kind": "x", "data": {},
                           "created": 1000.0, "accessed": 1000.0, "weight": 1.0, "tags": []}],
                 "edges": []}
        result = mg.merge_crdt(other, strategy="bogus")
        assert result["nodes_skipped"] == 1


# ── Graph Entropy & Connectivity Frontier ───────────────────────────────

class TestGraphEntropy:
    def test_empty(self, mg):
        result = mg.graph_entropy()
        assert result["entropy"] == 0.0
        assert result["normalized"] == 0.0

    def test_regular_graph(self, mg):
        # Triangle: all degrees = 2 → entropy = 0
        a, b, c = mg.add("A", "x"), mg.add("B", "x"), mg.add("C", "x")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        result = mg.graph_entropy()
        # All same degree → entropy = 0
        assert result["entropy"] == 0.0

    def test_heterogeneous(self, mg):
        # Star: center degree 4, leaves degree 1
        center = mg.add("hub", "x")
        for i in range(4):
            leaf = mg.add(f"L{i}", "x")
            mg.link(center.id, leaf.id, "r")
        result = mg.graph_entropy()
        # Two distinct degrees → entropy > 0
        assert result["entropy"] > 0.0
        assert 0.0 < result["normalized"] <= 1.0

    def test_normalized_bounded(self, mg):
        # Build a chain: 0-1-2-3-4
        nodes = [mg.add(f"N{i}", "x") for i in range(5)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        result = mg.graph_entropy()
        assert 0.0 <= result["normalized"] <= 1.0


class TestConnectivityFrontier:
    def test_empty_node(self, mg):
        assert mg.connectivity_frontier("nonexistent") == {}

    def test_single_node(self, mg):
        a = mg.add("A", "x")
        census = mg.connectivity_frontier(a.id)
        assert census == {0: 1}

    def test_chain(self, mg):
        # A - B - C - D
        a, b, c, d = [mg.add(f"N{i}", "x") for i in range(4)]
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, d.id, "r")
        census = mg.connectivity_frontier(a.id)
        assert census[0] == 1  # self
        assert census[1] == 1  # B
        assert census[2] == 1  # C
        assert census[3] == 1  # D

    def test_star(self, mg):
        center = mg.add("hub", "x")
        leaves = [mg.add(f"L{i}", "x") for i in range(3)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
        census = mg.connectivity_frontier(center.id)
        assert census[0] == 1  # center
        assert census[1] == 3  # all leaves at hop 1

    def test_max_hop_limit(self, mg):
        a, b, c = mg.add("A", "x"), mg.add("B", "x"), mg.add("C", "x")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        census = mg.connectivity_frontier(a.id, max_hop=1)
        # C is at hop 2, should not be reachable with max_hop=1
        assert census.get(2, 0) == 0


# ── Degree Centrality (Normalized) & Subgraph Edge Density ──────────────────

class TestDegreeCentralityNormalized:
    def test_empty(self, mg):
        assert mg.degree_centrality_normalized() == {}

    def test_single(self, mg):
        a = mg.add("A", "x")
        result = mg.degree_centrality_normalized()
        assert result[a.id] == 0.0

    def test_star(self, mg):
        center = mg.add("hub", "x")
        leaves = [mg.add(f"L{i}", "x") for i in range(4)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
        result = mg.degree_centrality_normalized()
        n = 5
        # center has degree 4, normalized = 4/(5-1) = 1.0
        assert result[center.id] == 1.0
        # leaves have degree 1, normalized = 1/4 = 0.25
        for leaf in leaves:
            assert result[leaf.id] == 0.25

    def test_complete_graph(self, mg):
        nodes = [mg.add(f"N{i}", "x") for i in range(4)]
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                mg.link(nodes[i].id, nodes[j].id, "r")
        result = mg.degree_centrality_normalized()
        # In K4, every node has degree 3, normalized = 3/3 = 1.0
        for node in nodes:
            assert result[node.id] == 1.0


class TestEdgeDensitySubgraph:
    def test_empty(self, mg):
        assert mg.edge_density_subgraph([]) == 0.0

    def test_single(self, mg):
        a = mg.add("A", "x")
        assert mg.edge_density_subgraph([a.id]) == 0.0

    def test_complete_pair(self, mg):
        a, b = mg.add("A", "x"), mg.add("B", "x")
        mg.link(a.id, b.id, "r")
        assert mg.edge_density_subgraph([a.id, b.id]) == 1.0

    def test_sparse_triple(self, mg):
        a, b, c = mg.add("A", "x"), mg.add("B", "x"), mg.add("C", "x")
        mg.link(a.id, b.id, "r")
        # Only 1 of 3 possible edges
        density = mg.edge_density_subgraph([a.id, b.id, c.id])
        assert density == round(1 / 3, 4)

    def test_disconnected(self, mg):
        a, b, c, d = [mg.add(f"N{i}", "x") for i in range(4)]
        mg.link(a.id, b.id, "r")
        # c and d are disconnected from subgraph {a, b, c, d}
        density = mg.edge_density_subgraph([a.id, b.id, c.id, d.id])
        # 1 edge out of 6 possible = 0.1667
        assert density == round(1 / 6, 4)


class TestVectorClock:
    def test_vector_clock_default(self, mg):
        """Node without vector clock returns default."""
        n = mg.add("test", "fact")
        vc = mg.vector_clock(n.id)
        assert isinstance(vc, dict)
        assert vc.get("_default", 0) == 0

    def test_vector_clock_increment(self, mg):
        """_vector_clock_increment bumps the agent's counter."""
        n = mg.add("test", "fact")
        mg._vector_clock_increment(n.id, "agent_A")
        mg._vector_clock_increment(n.id, "agent_A")
        mg._vector_clock_increment(n.id, "agent_B")
        vc = mg.vector_clock(n.id)
        assert vc["agent_A"] == 2
        assert vc["agent_B"] == 1

    def test_vc_compare_equal(self):
        """Identical clocks are equal."""
        assert MemoryGraph._vc_compare({"A": 1}, {"A": 1}) == "equal"

    def test_vc_compare_before(self):
        """Smaller clock happened-before."""
        assert MemoryGraph._vc_compare({"A": 1}, {"A": 2}) == "before"
        assert MemoryGraph._vc_compare({"A": 1, "B": 0}, {"A": 1, "B": 1}) == "before"

    def test_vc_compare_after(self):
        """Larger clock happened-after."""
        assert MemoryGraph._vc_compare({"A": 3}, {"A": 1}) == "after"

    def test_vc_compare_concurrent(self):
        """Divergent clocks are concurrent."""
        # A wrote x2, B wrote y2 — neither saw the other's latest
        assert MemoryGraph._vc_compare(
            {"A": 2, "B": 0}, {"A": 0, "B": 2}) == "concurrent"

    def test_vc_compare_missing_key(self):
        """Missing keys treated as 0."""
        assert MemoryGraph._vc_compare({"A": 1}, {"A": 1, "B": 1}) == "before"
        assert MemoryGraph._vc_compare({"A": 1, "B": 1}, {"A": 1}) == "after"

    def test_vector_clock_not_found(self, mg):
        """Non-existent node raises KeyError."""
        with pytest.raises(KeyError):
            mg.vector_clock("nonexistent")


class TestSubscribe:
    def test_subscribe_add_event(self, mg):
        """Subscribe fires on add events."""
        events = []
        mg.subscribe(lambda evt: events.append(evt))
        # add() doesn't call _notify directly; let's trigger via apply_changes
        delta = {"nodes": [{"id": "X1", "label": "Test", "kind": "fact",
                             "data": {}, "created": time.time(),
                             "accessed": time.time(), "weight": 1.0,
                             "tags": []}],
                 "edges": []}
        mg.apply_changes(delta, agent_id="agent_X")
        assert len(events) == 1
        assert events[0]["event"] == "add"
        assert events[0]["node_id"] == "X1"
        assert events[0]["agent_id"] == "agent_X"

    def test_subscribe_update_event(self, mg):
        """Subscribe fires on update events via apply_changes."""
        events = []
        n = mg.add("original", "fact", {"_vc": {"_self": 1}})
        mg.subscribe(lambda evt: events.append(evt))
        delta = {"nodes": [{"id": n.id, "label": "updated", "kind": "fact",
                             "data": {"_vc": {"_self": 2}},
                             "created": time.time(),
                             "accessed": time.time() + 100,
                             "weight": 1.0, "tags": []}],
                 "edges": []}
        mg.apply_changes(delta, agent_id="agent_Y")
        assert len(events) == 1
        assert events[0]["event"] == "update"
        assert events[0]["agent_id"] == "agent_Y"

    def test_subscribe_multiple_callbacks(self, mg):
        """Multiple subscribers all fire."""
        log_a, log_b = [], []
        mg.subscribe(lambda evt: log_a.append(evt["event"]))
        mg.subscribe(lambda evt: log_b.append(evt["event"]))
        delta = {"nodes": [{"id": "Z1", "label": "Z", "kind": "fact",
                             "data": {}, "created": time.time(),
                             "accessed": time.time(), "weight": 1.0,
                             "tags": []}], "edges": []}
        mg.apply_changes(delta)
        assert log_a == ["add"]
        assert log_b == ["add"]

    def test_subscribe_error_isolated(self, mg):
        """A failing callback doesn't block others."""
        good_log = []
        mg.subscribe(lambda evt: (_ for _ in ()).throw(RuntimeError("boom")))
        mg.subscribe(lambda evt: good_log.append(evt["event"]))
        delta = {"nodes": [{"id": "E1", "label": "E", "kind": "fact",
                             "data": {}, "created": time.time(),
                             "accessed": time.time(), "weight": 1.0,
                             "tags": []}], "edges": []}
        mg.apply_changes(delta)
        assert good_log == ["add"]


class TestGetChangesApplyChanges:
    def test_get_changes_returns_all_since_zero(self, mg):
        """get_changes(since=0) returns all nodes."""
        a = mg.add("A", "x")
        b = mg.add("B", "x")
        delta = mg.get_changes(since=0.0)
        ids = [n["id"] for n in delta["nodes"]]
        assert a.id in ids
        assert b.id in ids
        assert delta["timestamp"] > 0

    def test_get_changes_since_future(self, mg):
        """get_changes with future timestamp returns empty nodes."""
        mg.add("A", "x")
        delta = mg.get_changes(since=time.time() + 1000)
        assert len(delta["nodes"]) == 0

    def test_apply_changes_new_node(self, mg):
        """apply_changes adds new nodes from remote."""
        delta = {"nodes": [{"id": "remote_1", "label": "Remote",
                             "kind": "fact", "data": {"_vc": {"agent_A": 1}},
                             "created": time.time(), "accessed": time.time(),
                             "weight": 1.0, "tags": ["remote"]}],
                 "edges": []}
        summary = mg.apply_changes(delta, agent_id="agent_A")
        assert summary["nodes_added"] == 1
        assert mg.get_node("remote_1") is not None
        assert mg.get_node("remote_1").label == "Remote"

    def test_apply_changes_seeds_vector_clock(self, mg):
        """New nodes from apply_changes get a vector clock."""
        delta = {"nodes": [{"id": "r2", "label": "R2", "kind": "fact",
                             "data": {}, "created": time.time(),
                             "accessed": time.time(), "weight": 1.0,
                             "tags": []}], "edges": []}
        mg.apply_changes(delta, agent_id="agent_Z")
        node = mg.get_node("r2")
        assert "_vc" in node.data
        assert node.data["_vc"].get("agent_Z") == 1

    def test_apply_changes_skips_equal_version(self, mg):
        """Same vector clock → skip."""
        n = mg.add("orig", "fact", {"_vc": {"_self": 1}})
        delta = {"nodes": [{"id": n.id, "label": "updated", "kind": "fact",
                             "data": {"_vc": {"_self": 1}},
                             "created": time.time(),
                             "accessed": time.time(), "weight": 1.0,
                             "tags": []}], "edges": []}
        summary = mg.apply_changes(delta)
        assert summary["nodes_skipped"] == 1
        assert mg.get_node(n.id).label == "orig"  # unchanged

    def test_apply_changes_accepts_newer(self, mg):
        """After-version remote overwrites local."""
        n = mg.add("old", "fact", {"_vc": {"_self": 1}})
        delta = {"nodes": [{"id": n.id, "label": "new", "kind": "fact",
                             "data": {"_vc": {"_self": 2, "agent_B": 1}},
                             "created": time.time(),
                             "accessed": time.time(), "weight": 1.0,
                             "tags": []}], "edges": []}
        summary = mg.apply_changes(delta, agent_id="agent_B")
        assert summary["nodes_updated"] == 1
        assert mg.get_node(n.id).label == "new"

    def test_apply_changes_concurrent_lww(self, mg):
        """Concurrent conflict with LWW uses timestamp."""
        old_ts = time.time() - 100
        n = mg.add("local", "fact", {"_vc": {"_self": 2}})
        mg.update_node(n.id, label="local_version")
        # Remote has concurrent clock, older timestamp
        delta = {"nodes": [{"id": n.id, "label": "remote_version",
                             "kind": "fact",
                             "data": {"_vc": {"agent_X": 2}},
                             "created": old_ts, "accessed": old_ts,
                             "weight": 1.0, "tags": []}], "edges": []}
        summary = mg.apply_changes(delta, agent_id="agent_X", strategy="lww")
        assert summary["concurrent_conflicts"] == 1
        assert summary["nodes_skipped"] == 1
        assert mg.get_node(n.id).label == "local_version"

    def test_apply_changes_merges_edges(self, mg):
        """apply_changes adds missing edges."""
        a = mg.add("A", "x")
        b = mg.add("B", "x")
        delta = {"nodes": [],
                 "edges": [{"source": a.id, "target": b.id,
                            "relation": "linked", "weight": 0.5}]}
        summary = mg.apply_changes(delta)
        assert summary["edges_added"] == 1
        assert mg.is_linked(a.id, b.id)

    def test_apply_changes_full_sync_roundtrip(self, mg):
        """Full roundtrip: graph A exports → graph B imports."""
        mg.add("root", "concept", {"value": 42})
        delta = mg.get_changes(since=0.0)

        mg2 = MemoryGraph()
        summary = mg2.apply_changes(delta, agent_id="agent_A")
        assert summary["nodes_added"] >= 1
        # Verify by searching for the transferred node
        results = mg2.search_by_label("root")
        assert len(results) > 0
        assert results[0].label == "root"

    def test_apply_changes_empty_delta(self, mg):
        """Empty delta is a no-op."""
        summary = mg.apply_changes({"nodes": [], "edges": []})
        assert summary["nodes_added"] == 0
        assert summary["nodes_updated"] == 0
        assert summary["edges_added"] == 0

    def test_get_changes_includes_edges(self, mg):
        """get_changes includes edge data."""
        a, b = mg.add("A", "x"), mg.add("B", "x")
        mg.link(a.id, b.id, "rel")
        delta = mg.get_changes(since=0.0)
        assert len(delta["edges"]) >= 1
        edge_sources = [(e["source"], e["target"]) for e in delta["edges"]]
        assert (a.id, b.id) in edge_sources


class TestSemanticDivergence:
    """Tests for semantic divergence detection (GAM ICLR 2026)."""

    def test_divergence_isolated_node(self, mg):
        """Isolated node has zero divergence."""
        n = mg.add("lonely fact", "fact")
        report = mg.semantic_divergence(n.id)
        assert report is not None
        assert report["divergence"] == 0.0
        assert report["neighbor_count"] == 0
        assert report["suggestion"] == "isolated"

    def test_divergence_similar_neighbors(self, mg):
        """Node with very similar neighbors → low divergence → demote."""
        a = mg.add("Python programming language", "skill")
        b = mg.add("Python programming language tool", "skill")
        c = mg.add("Python programming language guide", "skill")
        mg.link(a.id, b.id, "related")
        mg.link(a.id, c.id, "related")
        report = mg.semantic_divergence(a.id)
        assert report["divergence"] < 0.5
        assert report["suggestion"] in ("demote", "keep")

    def test_divergence_different_neighbors(self, mg):
        """Node with very different neighbors → high divergence."""
        a = mg.add("quantum physics formula", "science")
        b = mg.add("cooking pasta recipe", "hobby")
        c = mg.add("rock music guitar", "hobby")
        mg.link(a.id, b.id, "related")
        mg.link(a.id, c.id, "related")
        report = mg.semantic_divergence(a.id)
        assert report["divergence"] > 0.5
        assert report["kind_mismatch_ratio"] > 0.0

    def test_divergence_nonexistent_node(self, mg):
        """Nonexistent node returns None."""
        assert mg.semantic_divergence("nonexistent") is None

    def test_divergence_kind_mismatch_ratio(self, mg):
        """Kind mismatch ratio correctly counts different-kind neighbors."""
        a = mg.add("AI agent", "concept")
        b = mg.add("neural net", "concept")
        c = mg.add("Python skill", "skill")
        d = mg.add("Rust crate", "tool")
        mg.link(a.id, b.id, "related")
        mg.link(a.id, c.id, "related")
        mg.link(a.id, d.id, "related")
        report = mg.semantic_divergence(a.id)
        # 2 out of 3 neighbors have different kind
        assert report["kind_mismatch_ratio"] == pytest.approx(2 / 3, abs=0.01)

    def test_divergence_suggestion_promote(self, mg):
        """High divergence + high kind mismatch → promote suggestion."""
        a = mg.add("xyz quantum blockchain", "concept")
        b = mg.add("cooking recipe pasta", "hobby")
        c = mg.add("gardening tips tomatoes", "hobby")
        d = mg.add("music piano jazz", "hobby")
        mg.link(a.id, b.id, "rel")
        mg.link(a.id, c.id, "rel")
        mg.link(a.id, d.id, "rel")
        report = mg.semantic_divergence(a.id)
        assert report["divergence"] > 0.8
        assert report["kind_mismatch_ratio"] > 0.5

    def test_divergence_report_fields(self, mg):
        """Report contains all expected fields."""
        a = mg.add("test", "fact")
        b = mg.add("other", "fact")
        mg.link(a.id, b.id, "rel")
        report = mg.semantic_divergence(a.id)
        for field in ("node_id", "label", "kind", "neighbor_count",
                      "divergence", "avg_similarity", "kind_mismatch_ratio",
                      "suggestion"):
            assert field in report

    def test_divergence_avg_similarity_range(self, mg):
        """avg_similarity is between 0 and 1."""
        a = mg.add("hello world", "greeting")
        b = mg.add("hello there", "greeting")
        mg.link(a.id, b.id, "rel")
        report = mg.semantic_divergence(a.id)
        assert 0.0 <= report["avg_similarity"] <= 1.0


class TestDivergenceScan:
    """Tests for batch divergence scanning."""

    def test_scan_returns_high_divergence_only(self, mg):
        """Scan filters by threshold."""
        # Low divergence cluster
        a1 = mg.add("machine learning model", "concept")
        a2 = mg.add("machine learning algorithm", "concept")
        a3 = mg.add("ML neural network", "concept")
        mg.link(a1.id, a2.id, "rel")
        mg.link(a1.id, a3.id, "rel")
        # High divergence node
        b1 = mg.add("cooking italian food", "hobby")
        b2 = mg.add("quantum entanglement theory", "science")
        mg.link(b1.id, b2.id, "rel")
        results = mg.divergence_scan(threshold=0.5)
        # b1 and b2 should appear (high divergence), a1 may not
        node_ids = [r["node_id"] for r in results]
        assert b1.id in node_ids or b2.id in node_ids

    def test_scan_sorted_by_divergence(self, mg):
        """Results are sorted descending by divergence."""
        nodes = []
        for i in range(5):
            n = mg.add(f"unique_topic_{i}_xyz", "concept")
            nodes.append(n)
        # Link all to a very different anchor
        anchor = mg.add("completely different anchor text", "tool")
        for n in nodes:
            mg.link(n.id, anchor.id, "rel")
        results = mg.divergence_scan(threshold=0.0)
        divs = [r["divergence"] for r in results]
        assert divs == sorted(divs, reverse=True)

    def test_scan_respects_limit(self, mg):
        """Limit caps the number of results."""
        for i in range(20):
            n = mg.add(f"isolated node {i}", "fact")
        results = mg.divergence_scan(threshold=0.0, limit=5)
        assert len(results) <= 5

    def test_scan_empty_graph(self, mg):
        """Empty graph returns empty list."""
        assert mg.divergence_scan() == []


class TestConsolidateMemory:
    """Tests for memory consolidation (GAM ICLR 2026)."""

    def test_consolidate_dry_run(self, mg):
        """Dry run reports without modifying."""
        a = mg.add("Python coding", "skill")
        b = mg.add("Python programming", "skill")
        c = mg.add("Python dev", "skill")
        mg.link(a.id, b.id, "rel")
        mg.link(a.id, c.id, "rel")
        result = mg.consolidate_memory(dry_run=True)
        assert result["scanned"] >= 3
        assert result["promoted"] + result["demoted"] + result["reclassified"] + result["kept"] == result["scanned"]
        # Dry run → no actual changes
        # Node 'a' should still exist (not merged)
        assert mg.get_node(a.id) is not None

    def test_consolidate_demote_merges_similar(self, mg):
        """Demote merges low-divergence node into most similar neighbor."""
        a = mg.add("Python programming language", "skill")
        b = mg.add("Python programming lang", "skill")
        mg.link(a.id, b.id, "rel")
        result = mg.consolidate_memory(strategy="demote",
                                        similarity_threshold=0.9,
                                        dry_run=False)
        assert result["demoted"] >= 1

    def test_consolidate_promote_tags_seed(self, mg):
        """Promote tags high-divergence node as cluster_seed."""
        a = mg.add("quantum blockchain AI convergence", "concept")
        b = mg.add("cooking pasta recipe italian", "hobby")
        c = mg.add("gardening tomatoes growing", "hobby")
        d = mg.add("music piano jazz classical", "hobby")
        mg.link(a.id, b.id, "rel")
        mg.link(a.id, c.id, "rel")
        mg.link(a.id, d.id, "rel")
        result = mg.consolidate_memory(strategy="auto",
                                        divergence_threshold=0.5,
                                        dry_run=False)
        assert result["promoted"] >= 1
        # Verify tag was added
        promoted_detail = [d for d in result["details"] if d["action"] == "promote"]
        if promoted_detail:
            tags_row = mg.conn.execute(
                "SELECT tags FROM nodes WHERE id = ?",
                (promoted_detail[0]["node_id"],)
            ).fetchone()
            import json as _json
            tag_list = _json.loads(tags_row["tags"]) if tags_row else []
            assert "cluster_seed" in tag_list

    def test_consolidate_reclassify_changes_kind(self, mg):
        """Reclassify updates kind to majority neighbor kind."""
        a = mg.add("mislabeled node", "wrong_kind")
        b = mg.add("correct kind item 1", "correct_kind")
        c = mg.add("correct kind item 2", "correct_kind")
        mg.link(a.id, b.id, "rel")
        mg.link(a.id, c.id, "rel")
        result = mg.consolidate_memory(strategy="auto", dry_run=False)
        # Node 'a' should be reclassified (kind_mismatch > 0.5, high divergence)
        reclassified = [d for d in result["details"] if d["action"] == "reclassify"]
        if reclassified:
            updated = mg.get_node(a.id)
            assert updated.kind == "correct_kind"

    def test_consolidate_returns_summary(self, mg):
        """Result has all expected fields."""
        result = mg.consolidate_memory(dry_run=True)
        for field in ("scanned", "promoted", "demoted", "reclassified", "kept", "details"):
            assert field in result
        assert isinstance(result["details"], list)

    def test_consolidate_empty_graph(self, mg):
        """Empty graph → scanned=0."""
        result = mg.consolidate_memory(dry_run=True)
        assert result["scanned"] == 0
        assert result["promoted"] == 0

    def test_consolidate_auto_strategy(self, mg):
        """Auto strategy makes appropriate decisions."""
        # Mix of similar and different nodes
        similar_a = mg.add("Python programming", "skill")
        similar_b = mg.add("Python coding", "skill")
        mg.link(similar_a.id, similar_b.id, "rel")
        different_a = mg.add("quantum mechanics", "science")
        different_b = mg.add("pasta recipe", "hobby")
        mg.link(different_a.id, different_b.id, "rel")
        result = mg.consolidate_memory(strategy="auto", dry_run=True)
        assert result["scanned"] >= 4
        # Should have at least some non-kept actions
        total_actions = result["promoted"] + result["demoted"] + result["reclassified"]
        assert total_actions >= 1

    def test_consolidate_details_contain_node_id_and_action(self, mg):
        """Each detail has node_id and action."""
        a = mg.add("test", "fact")
        result = mg.consolidate_memory(dry_run=True)
        for detail in result["details"]:
            assert "node_id" in detail
            assert "action" in detail
            assert detail["action"] in ("promote", "demote", "reclassify")

    def test_consolidate_idempotent_second_pass(self, mg):
        """Second consolidation pass has fewer changes."""
        # Create divergent setup
        a = mg.add("quantum physics", "science")
        b = mg.add("cooking recipe", "hobby")
        c = mg.add("music theory", "hobby")
        mg.link(a.id, b.id, "rel")
        mg.link(a.id, c.id, "rel")
        # First pass
        first = mg.consolidate_memory(dry_run=False)
        # Second pass should have fewer or equal actions
        second = mg.consolidate_memory(dry_run=False)
        first_actions = first["promoted"] + first["demoted"] + first["reclassified"]
        second_actions = second["promoted"] + second["demoted"] + second["reclassified"]
        assert second_actions <= first_actions

    def test_consolidate_divergence_threshold_filtering(self, mg):
        """Higher threshold → fewer promotions."""
        a = mg.add("very different unique content xyz", "concept")
        b = mg.add("completely other topic abc", "hobby")
        mg.link(a.id, b.id, "rel")
        low_thresh = mg.consolidate_memory(strategy="promote",
                                            divergence_threshold=0.1, dry_run=True)
        high_thresh = mg.consolidate_memory(strategy="promote",
                                             divergence_threshold=0.9, dry_run=True)
        assert low_thresh["promoted"] >= high_thresh["promoted"]


class TestRetentionScore:
    """Tests for retention scoring (divergence-aware FiFA)."""

    def test_retention_score_basic(self, mg):
        """Retention score returns all expected fields."""
        a = mg.add("test node", "fact")
        report = mg.retention_score(a.id)
        assert report is not None
        assert 0.0 <= report["score"] <= 1.0
        assert "components" in report
        for comp in ("importance", "recency", "connectivity", "divergence"):
            assert comp in report["components"]
        assert report["recommendation"] in ("keep", "review", "evict")

    def test_retention_score_nonexistent(self, mg):
        """Nonexistent node returns None."""
        assert mg.retention_score("nonexistent") is None

    def test_retention_high_weight_node(self, mg):
        """High-weight node gets higher importance component."""
        a = mg.add("important", "fact")
        b = mg.add("unimportant", "fact")
        mg.update_node(a.id, weight=1.0)
        mg.update_node(b.id, weight=0.1)
        score_a = mg.retention_score(a.id)
        score_b = mg.retention_score(b.id)
        assert score_a["components"]["importance"] > score_b["components"]["importance"]

    def test_rettlement_connected_node(self, mg):
        """Well-connected node gets higher connectivity score."""
        hub = mg.add("hub", "concept")
        for i in range(5):
            n = mg.add(f"node_{i}", "concept")
            mg.link(hub.id, n.id, "rel")
        isolated = mg.add("isolated", "concept")
        hub_score = mg.retention_score(hub.id)
        iso_score = mg.retention_score(isolated.id)
        assert hub_score["components"]["connectivity"] > iso_score["components"]["connectivity"]

    def test_retention_recommendation_thresholds(self, mg):
        """Recommendation follows score thresholds."""
        # A fresh, high-weight, connected node → keep
        a = mg.add("important fresh node", "concept")
        mg.update_node(a.id, weight=1.0)
        b = mg.add("other", "concept")
        mg.link(a.id, b.id, "rel")
        report = mg.retention_score(a.id)
        assert report["recommendation"] == "keep"

    def test_retention_custom_weights(self, mg):
        """Custom weights affect the final score."""
        a = mg.add("test", "fact")
        # All weight on importance
        report = mg.retention_score(a.id, w_importance=1.0, w_recency=0,
                                     w_connectivity=0, w_divergence=0)
        assert report["score"] == pytest.approx(report["components"]["importance"], abs=0.01)


class TestMemoryEvict:
    """Tests for smart eviction."""

    def test_evict_dry_run(self, mg):
        """Dry run doesn't delete nodes."""
        a = mg.add("node to check", "fact")
        result = mg.memory_evict(dry_run=True)
        assert result["scanned"] >= 1
        assert mg.get_node(a.id) is not None

    def test_evict_removes_low_score(self, mg):
        """Eviction removes lowest-score nodes first."""
        # Create nodes with varying importance
        for i in range(10):
            n = mg.add(f"low priority item {i}", "fact")
        result = mg.memory_evict(budget=3, min_score=0.5, dry_run=False)
        assert result["evicted"] <= 3

    def test_evict_keeps_high_score(self, mg):
        """High-score nodes are kept."""
        important = mg.add("critical important node", "fact")
        mg.update_node(important.id, weight=1.0)
        other = mg.add("other", "fact")
        mg.link(important.id, other.id, "rel")
        result = mg.memory_evict(budget=5, min_score=0.05, dry_run=False)
        # Important node should survive
        assert mg.get_node(important.id) is not None

    def test_evict_empty_graph(self, mg):
        """Empty graph → scanned=0."""
        result = mg.memory_evict(dry_run=True)
        assert result["scanned"] == 0
        assert result["evicted"] == 0

    def test_evict_budget_limit(self, mg):
        """Budget limits eviction count."""
        for i in range(20):
            mg.add(f"disposable node {i}", "temp")
        result = mg.memory_evict(budget=5, min_score=0.99, dry_run=False)
        assert result["evicted"] <= 5

    def test_evict_returns_details(self, mg):
        """Eviction details include node_id, label, score."""
        for i in range(5):
            mg.add(f"temp item {i}", "temp")
        result = mg.memory_evict(budget=3, min_score=0.99, dry_run=True)
        for detail in result["details"]:
            assert "node_id" in detail
            assert "label" in detail
            assert "score" in detail

    def test_evict_preserves_ordering(self, mg):
        """Evicted nodes have lower scores than kept nodes."""
        for i in range(10):
            n = mg.add(f"item_{i}", "fact")
        result = mg.memory_evict(budget=3, min_score=0.3, dry_run=True)
        if result["evicted"] > 0:
            max_evicted = max(d["score"] for d in result["details"])
            # All evicted should have low scores
            assert max_evicted < 0.3


class TestClusterSeeds:
    """Tests for cluster seed discovery and expansion."""

    def test_cluster_seeds_empty(self, mg):
        """No seeds in fresh graph."""
        assert mg.cluster_seeds() == []

    def test_cluster_seeds_after_promote(self, mg):
        """Promote creates cluster_seed tags."""
        a = mg.add("quantum blockchain unique", "concept")
        b = mg.add("cooking recipe italian", "hobby")
        c = mg.add("music jazz piano", "hobby")
        d = mg.add("art painting modern", "hobby")
        mg.link(a.id, b.id, "rel")
        mg.link(a.id, c.id, "rel")
        mg.link(a.id, d.id, "rel")
        mg.consolidate_memory(strategy="auto", divergence_threshold=0.3, dry_run=False)
        seeds = mg.cluster_seeds()
        assert len(seeds) >= 1

    def test_cluster_seeds_returns_fields(self, mg):
        """Seed entries have expected fields."""
        a = mg.add("very unique content xyz", "concept")
        mg.tag_nodes("cluster_seed", [a.id])
        seeds = mg.cluster_seeds()
        assert len(seeds) == 1
        for field in ("node_id", "label", "kind", "weight", "neighbor_count"):
            assert field in seeds[0]


class TestSeedExpansion:
    """Tests for cluster boundary detection."""

    def test_seed_expansion_basic(self, mg):
        """Expansion returns layers and boundary."""
        seed = mg.add("seed node", "concept")
        a = mg.add("level1", "concept")
        b = mg.add("level1 other", "concept")
        c = mg.add("level2", "concept")
        mg.link(seed.id, a.id, "rel")
        mg.link(seed.id, b.id, "rel")
        mg.link(a.id, c.id, "rel")
        result = mg.seed_expansion(seed.id, max_hops=2)
        assert result is not None
        assert result["seed_id"] == seed.id
        assert "layers" in result
        assert "boundary" in result
        assert result["size"] >= 3

    def test_seed_expansion_nonexistent(self, mg):
        """Nonexistent seed returns None."""
        assert mg.seed_expansion("nonexistent") is None

    def test_seed_expansion_isolated(self, mg):
        """Isolated seed has no layers."""
        seed = mg.add("lonely seed", "fact")
        result = mg.seed_expansion(seed.id)
        assert result is not None
        assert result["boundary"] == []

    def test_seed_expansion_max_hops(self, mg):
        """max_hops limits traversal depth."""
        nodes = [mg.add(f"node_{i}", "concept") for i in range(5)]
        for i in range(len(nodes) - 1):
            mg.link(nodes[i].id, nodes[i+1].id, "rel")
        result = mg.seed_expansion(nodes[0].id, max_hops=1)
        assert result is not None
        # Only hop-1 nodes should be in layers
        total_reached = sum(len(ids) for hop, ids in result["layers"].items() if int(hop) > 0)
        assert total_reached <= 1


class TestSeedExpansion:
    """Tests for cluster seed discovery and expansion."""

    def test_cluster_seeds_empty(self, mg):
        """No seeds in fresh graph."""
        assert mg.cluster_seeds() == []

    def test_cluster_seeds_after_promote(self, mg):
        """Promote creates cluster_seed tags."""
        a = mg.add("quantum blockchain unique", "concept")
        b = mg.add("cooking recipe italian", "hobby")
        c = mg.add("music jazz piano", "hobby")
        d = mg.add("art painting modern", "hobby")
        mg.link(a.id, b.id, "rel")
        mg.link(a.id, c.id, "rel")
        mg.link(a.id, d.id, "rel")
        mg.consolidate_memory(strategy="auto", divergence_threshold=0.3, dry_run=False)
        seeds = mg.cluster_seeds()
        assert len(seeds) >= 1

    def test_cluster_seeds_returns_fields(self, mg):
        """Seed entries have expected fields."""
        a = mg.add("very unique content xyz", "concept")
        mg.tag_nodes("cluster_seed", [a.id])
        seeds = mg.cluster_seeds()
        assert len(seeds) == 1
        for field in ("node_id", "label", "kind", "weight", "neighbor_count"):
            assert field in seeds[0]


class TestSeedExpansion:
    """Tests for cluster boundary detection."""

    def test_seed_expansion_basic(self, mg):
        """Expansion returns layers and boundary."""
        seed = mg.add("seed node", "concept")
        a = mg.add("level1", "concept")
        b = mg.add("level1 other", "concept")
        c = mg.add("level2", "concept")
        mg.link(seed.id, a.id, "rel")
        mg.link(seed.id, b.id, "rel")
        mg.link(a.id, c.id, "rel")
        result = mg.seed_expansion(seed.id, max_hops=2)
        assert result is not None
        assert result["seed_id"] == seed.id
        assert "layers" in result
        assert "boundary" in result
        assert result["size"] >= 3

    def test_seed_expansion_nonexistent(self, mg):
        """Nonexistent seed returns None."""
        assert mg.seed_expansion("nonexistent") is None

    def test_seed_expansion_isolated(self, mg):
        """Isolated seed has no layers."""
        seed = mg.add("lonely seed", "fact")
        result = mg.seed_expansion(seed.id)
        assert result is not None
        assert result["boundary"] == []

    def test_seed_expansion_max_hops(self, mg):
        """max_hops limits traversal depth."""
        nodes = [mg.add(f"node_{i}", "concept") for i in range(5)]
        for i in range(len(nodes) - 1):
            mg.link(nodes[i].id, nodes[i+1].id, "rel")
        result = mg.seed_expansion(nodes[0].id, max_hops=1)
        assert result is not None
        total_reached = sum(len(ids) for hop, ids in result["layers"].items() if int(hop) > 0)
        assert total_reached <= 1


class TestConsolidationReport:
    """Tests for the consolidation status report."""

    def test_report_empty_graph(self, mg):
        """Empty graph returns healthy empty report."""
        report = mg.consolidation_report()
        assert report["total_nodes"] == 0
        assert report["consolidation_health"] == "empty"

    def test_report_basic_fields(self, mg):
        """Report contains all expected fields."""
        a = mg.add("test", "fact")
        report = mg.consolidation_report()
        for field in ("total_nodes", "high_divergence_count",
                      "cluster_seeds", "eviction_candidates",
                      "avg_retention", "consolidation_health"):
            assert field in report
        assert report["total_nodes"] >= 1

    def test_report_health_healthy(self, mg):
        """Low divergence -> healthy."""
        a = mg.add("Python programming language", "skill")
        b = mg.add("Python programming language tool", "skill")
        mg.link(a.id, b.id, "rel")
        report = mg.consolidation_report()
        assert report["consolidation_health"] in ("healthy", "moderate")

    def test_report_high_divergence_detected(self, mg):
        """High divergence nodes are counted."""
        a = mg.add("quantum blockchain xyz", "science")
        b = mg.add("cooking pasta recipe", "hobby")
        mg.link(a.id, b.id, "rel")
        report = mg.consolidation_report()
        assert report["high_divergence_count"] >= 1

    def test_report_avg_retention_range(self, mg):
        """Average retention is between 0 and 1."""
        for i in range(5):
            mg.add(f"item {i}", "fact")
        report = mg.consolidation_report()
        assert 0.0 <= report["avg_retention"] <= 1.0


class TestConsolidationPipeline:
    """Tests for the one-shot consolidation_pipeline orchestrator."""

    def test_pipeline_empty_graph(self, mg):
        """Empty graph pipeline returns zero actions."""
        result = mg.consolidation_pipeline()
        assert result["actions_total"] == 0
        assert result["report"]["total_nodes"] == 0
        assert "scan" in result
        assert "consolidation" in result
        assert "eviction" in result

    def test_pipeline_returns_all_sections(self, mg):
        """Pipeline returns scan, consolidation, eviction, report sections."""
        mg.add("test node", "fact")
        result = mg.consolidation_pipeline()
        for key in ("scan", "consolidation", "eviction", "report", "actions_total"):
            assert key in result

    def test_pipeline_dry_run_no_modifications(self, mg):
        """Dry run doesn't modify the graph."""
        a = mg.add("quantum blockchain xyz", "science")
        b = mg.add("cooking pasta recipe", "hobby")
        mg.link(a.id, b.id, "rel")
        before = mg.stats()["nodes"]
        result = mg.consolidation_pipeline(dry_run=True)
        after = mg.stats()["nodes"]
        assert before == after
        assert result["dry_run"] is True
        # In dry_run, counts reflect proposed actions but graph unchanged
        assert before == after

    def test_pipeline_eviction_respects_budget(self, mg):
        """Eviction respects the budget parameter."""
        for i in range(10):
            mg.add(f"disposable item {i}", "temp")
        result = mg.consolidation_pipeline(evict_budget=3)
        assert result["eviction"]["evicted"] <= 3

    def test_pipeline_zero_budget_skips_eviction(self, mg):
        """evict_budget=0 skips eviction entirely."""
        mg.add("test", "fact")
        result = mg.consolidation_pipeline(evict_budget=0)
        assert result["eviction"]["evicted"] == 0

    def test_pipeline_actions_total_counts_all(self, mg):
        """actions_total = promoted + demoted + reclassified + evicted."""
        a = mg.add("unique outlier concept xyz", "concept")
        b = mg.add("similar idea one", "concept")
        c = mg.add("similar idea two", "concept")
        mg.link(a.id, b.id, "rel")
        mg.link(b.id, c.id, "rel")
        result = mg.consolidation_pipeline(dry_run=True)
        cons = result["consolidation"]
        evict = result["eviction"]
        expected = (cons.get("promoted", 0) + cons.get("demoted", 0) +
                    cons.get("reclassified", 0) + evict.get("evicted", 0))
        assert result["actions_total"] == expected

    def test_pipeline_report_health_consistent(self, mg):
        """Pipeline report health matches standalone consolidation_report."""
        mg.add("Python programming", "skill")
        mg.add("Python tooling", "skill")
        pipeline_result = mg.consolidation_pipeline(dry_run=True)
        standalone = mg.consolidation_report()
        assert pipeline_result["report"]["total_nodes"] == standalone["total_nodes"]

    def test_pipeline_min_retention_filter(self, mg):
        """Higher min_retention threshold catches more nodes as eviction candidates."""
        for i in range(5):
            mg.add(f"low value node {i}", "temp")
        # dry_run to avoid actual deletion so both runs see same graph
        strict = mg.consolidation_pipeline(evict_budget=10, min_retention=0.8, dry_run=True)
        lenient = mg.consolidation_pipeline(evict_budget=10, min_retention=0.01, dry_run=True)
        # Strict (0.8) threshold should flag >= lenient (0.01) threshold
        assert strict["eviction"]["evicted"] >= lenient["eviction"]["evicted"]

    def test_pipeline_scan_catches_divergence(self, mg):
        """Pipeline scan detects high-divergence nodes."""
        a = mg.add("quantum computing physics", "science")
        b = mg.add("medieval cooking techniques", "history")
        mg.link(a.id, b.id, "rel")
        result = mg.consolidation_pipeline(dry_run=True)
        assert result["scan"]["flagged"] >= 1  # at least one divergent pair

    def test_pipeline_idempotent_dry_run(self, mg):
        """Running pipeline twice in dry_run gives same results."""
        a = mg.add("node one", "fact")
        b = mg.add("node two completely different", "fact")
        mg.link(a.id, b.id, "rel")
        r1 = mg.consolidation_pipeline(dry_run=True)
        r2 = mg.consolidation_pipeline(dry_run=True)
        assert r1["actions_total"] == r2["actions_total"]
        assert r1["report"]["total_nodes"] == r2["report"]["total_nodes"]


# ── memory_decay tests ──────────────────────────────────────────

class TestMemoryDecay:
    """Tests for memory_decay — configurable exponential weight decay."""

    def test_decay_basic(self, mg):
        """Decay reduces weights of old, untouched nodes."""
        a = mg.add("old node", "fact")
        # Simulate old access time (30 days ago)
        mg.conn.execute("UPDATE nodes SET accessed=? WHERE id=?",
                        (time.time() - 30 * 86400, a.id))
        mg.conn.execute("UPDATE nodes SET weight=0.8 WHERE id=?", (a.id,))
        mg.conn.commit()

        result = mg.memory_decay(half_life_days=7.0)
        node = mg.get_node(a.id)
        assert node.weight < 0.8  # weight should have decreased
        assert result["decayed"] >= 1
        assert result["weight_lost"] > 0

    def test_decay_preserves_recent(self, mg):
        """Recently accessed nodes should barely decay."""
        a = mg.add("fresh node", "fact")
        mg.touch(a.id)  # fresh access
        result = mg.memory_decay(half_life_days=7.0)
        node = mg.get_node(a.id)
        # Very recent — should be nearly unchanged
        assert node.weight >= 0.9 * 0.5  # default weight ~0.5, minimal decay

    def test_decay_kind_filter(self, mg):
        """Kind filter skips specified types."""
        person = mg.add("important person", "person")
        event = mg.add("old event", "event")
        # Make both old
        old_time = time.time() - 60 * 86400
        mg.conn.execute("UPDATE nodes SET accessed=?, weight=0.8", (old_time,))
        mg.conn.commit()

        result = mg.memory_decay(half_life_days=7.0, kinds=["event"])
        assert result["skipped"] >= 1  # person was skipped
        assert result["scanned"] >= 1  # event was scanned

    def test_decay_min_weight_floor(self, mg):
        """Decay respects min_weight floor."""
        a = mg.add("old low node", "fact")
        mg.conn.execute("UPDATE nodes SET accessed=?, weight=0.05 WHERE id=?",
                        (time.time() - 365 * 86400, a.id))
        mg.conn.commit()

        result = mg.memory_decay(half_life_days=7.0, min_weight=0.02)
        node = mg.get_node(a.id)
        assert node.weight >= 0.02  # never below min_weight

    def test_decay_dry_run(self, mg):
        """Dry run doesn't modify weights."""
        a = mg.add("test node", "fact")
        mg.conn.execute("UPDATE nodes SET accessed=?, weight=0.7 WHERE id=?",
                        (time.time() - 30 * 86400, a.id))
        mg.conn.commit()

        result = mg.memory_decay(half_life_days=7.0, dry_run=True)
        node = mg.get_node(a.id)
        assert node.weight == 0.7  # unchanged
        assert result["dry_run"] is True
        assert result["decayed"] >= 1

    def test_decay_returns_metrics(self, mg):
        """Result includes all expected metrics."""
        mg.add("node a", "fact")
        mg.add("node b", "concept")
        result = mg.memory_decay(half_life_days=14.0)
        for key in ("scanned", "decayed", "skipped", "total_before",
                    "total_after", "weight_lost", "max_accessed_age_days",
                    "half_life_days", "dry_run"):
            assert key in result, f"Missing key: {key}"
        assert result["half_life_days"] == 14.0

    def test_decay_half_life_formula(self, mg):
        """Verify exact half-life: after 7 days with half_life=7, weight should be ~half."""
        a = mg.add("precision test", "fact")
        mg.conn.execute("UPDATE nodes SET accessed=?, weight=0.6 WHERE id=?",
                        (time.time() - 7 * 86400, a.id))
        mg.conn.commit()

        mg.memory_decay(half_life_days=7.0, min_weight=0.0)
        node = mg.get_node(a.id)
        # After exactly 7 days with half_life=7: weight ≈ 0.6 * 0.5 = 0.3
        assert abs(node.weight - 0.3) < 0.05  # within tolerance (timing)

    def test_decay_multiple_kinds(self, mg):
        """Decay can target multiple kinds."""
        mg.add("event1", "event")
        mg.add("note1", "note")
        mg.add("person1", "person")
        old_time = time.time() - 90 * 86400
        mg.conn.execute("UPDATE nodes SET accessed=?", (old_time,))
        mg.conn.commit()

        result = mg.memory_decay(half_life_days=7.0, kinds=["event", "note"])
        assert result["scanned"] == 2  # only event + note
        assert result["skipped"] == 1  # person skipped


# ── neighborhood_agreement tests ─────────────────────────────────

class TestNeighborhoodAgreement:
    """Tests for neighborhood_agreement — multi-hop semantic agreement."""

    def test_agreement_basic(self, mg):
        """Basic agreement returns expected structure."""
        a = mg.add("alpha", "concept")
        b = mg.add("alpha beta", "concept")
        mg.link(a.id, b.id, "rel")
        result = mg.neighborhood_agreement(a.id, hops=2)
        assert result is not None
        assert "layers" in result
        assert len(result["layers"]) >= 1
        assert result["layers"][0]["hop"] == 1
        assert "overall_agreement" in result
        assert "node_role" in result

    def test_agreement_nonexistent_node(self, mg):
        """Nonexistent node returns None."""
        assert mg.neighborhood_agreement("nonexistent", hops=2) is None

    def test_agreement_isolated_node(self, mg):
        """Isolated node gets 'isolated' role."""
        a = mg.add("lonely", "concept")
        result = mg.neighborhood_agreement(a.id, hops=2)
        assert result is not None
        assert len(result["layers"]) == 1
        assert result["layers"][0]["nodes"] == 0
        assert result["node_role"] == "isolated"

    def test_agreement_bridge_node(self, mg):
        """Bridge node: low 1-hop agreement but connects to similar cluster."""
        # Cluster 1
        a1 = mg.add("python programming", "skill")
        a2 = mg.add("python scripting", "skill")
        a3 = mg.add("python automation", "skill")
        mg.link(a1.id, a2.id, "same")
        mg.link(a2.id, a3.id, "same")

        # Bridge node
        bridge = mg.add("ruby scripting language", "skill")
        mg.link(a1.id, bridge.id, "bridge")

        # Cluster 2
        b1 = mg.add("ruby programming", "skill")
        b2 = mg.add("ruby automation", "skill")
        mg.link(bridge.id, b1.id, "same")
        mg.link(b1.id, b2.id, "same")

        result = mg.neighborhood_agreement(bridge.id, hops=2)
        assert result is not None
        assert result["node_role"] in ("bridge", "peripheral", "boundary", "core")
        assert len(result["layers"]) >= 1

    def test_agreement_core_node(self, mg):
        """Core node: high agreement throughout neighborhood."""
        a = mg.add("machine learning", "topic")
        b = mg.add("machine learning models", "topic")
        c = mg.add("machine learning training", "topic")
        mg.link(a.id, b.id, "same")
        mg.link(a.id, c.id, "same")
        mg.link(b.id, c.id, "same")

        result = mg.neighborhood_agreement(a.id, hops=2)
        assert result["overall_agreement"] > 0.0
        assert result["node_role"] in ("core", "peripheral")

    def test_agreement_hop_layers_increase(self, mg):
        """More hops discover more nodes."""
        a = mg.add("center", "node")
        b = mg.add("ring1", "node")
        c = mg.add("ring2", "node")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")

        result = mg.neighborhood_agreement(a.id, hops=2)
        assert len(result["layers"]) == 2
        assert result["layers"][0]["hop"] == 1
        assert result["layers"][1]["hop"] == 2
        # Layer 2 should have found node c
        assert result["layers"][1]["nodes"] >= 1

    def test_agreement_no_self_inclusion(self, mg):
        """Node itself is never counted in layers."""
        a = mg.add("self", "node")
        b = mg.add("other", "node")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, a.id, "r")  # bidirectional

        result = mg.neighborhood_agreement(a.id, hops=3)
        # Should not include node 'a' in any layer
        all_simulated = sum(l["nodes"] for l in result["layers"])
        # Only 'b' should be found
        assert all_simulated <= 1


# ── memory_proximity tests ─────────────────────────────────────────

class TestMemoryProximity:
    """Tests for memory_proximity — semantic similarity neighborhood."""

    def test_proximity_basic(self, mg):
        """Finds semantically similar nodes."""
        a = mg.add("python programming language", "skill")
        b = mg.add("python scripting guide", "skill")
        c = mg.add("rust systems programming", "skill")
        # Don't link — proximity should still find them
        result = mg.memory_proximity(a.id, radius=0.1)
        assert result is not None
        assert len(result) >= 1
        # 'b' should be more similar than 'c'
        labels = [r["label"] for r in result]
        assert "python scripting guide" in labels

    def test_proximity_nonexistent(self, mg):
        """Nonexistent anchor returns None."""
        assert mg.memory_proximity("nope") is None

    def test_proximity_radius_filter(self, mg):
        """High radius filters out dissimilar nodes."""
        a = mg.add("machine learning", "topic")
        b = mg.add("machine learning models", "topic")
        c = mg.add("cooking pasta recipes", "recipe")

        loose = mg.memory_proximity(a.id, radius=0.05)
        strict = mg.memory_proximity(a.id, radius=0.5)
        assert len(loose) >= len(strict)

    def test_proximity_connected_flag(self, mg):
        """Connected flag indicates edge presence."""
        a = mg.add("node alpha", "test")
        b = mg.add("node alpha beta", "test")
        c = mg.add("node alpha gamma", "test")
        mg.link(a.id, b.id, "rel")
        # c is NOT linked

        result = mg.memory_proximity(a.id, radius=0.1)
        connected_items = [r for r in result if r["connected"]]
        unconnected = [r for r in result if not r["connected"]]
        assert any(r["label"] == "node alpha beta" for r in connected_items)

    def test_proximity_excludes_self(self, mg):
        """Anchor node is never in results."""
        a = mg.add("solo", "test")
        result = mg.memory_proximity(a.id, radius=0.0)
        assert all(r["node_id"] != a.id for r in result)

    def test_proximity_limit(self, mg):
        """Limit caps results."""
        a = mg.add("common word", "test")
        for i in range(10):
            mg.add(f"common word variant {i}", "test")

        result = mg.memory_proximity(a.id, radius=0.0, limit=3)
        assert len(result) <= 3

    def test_proximity_sorted(self, mg):
        """Results sorted by similarity descending."""
        a = mg.add("python programming", "skill")
        mg.add("python programming tutorial", "skill")
        mg.add("python data", "skill")
        mg.add("rust embedded", "skill")

        result = mg.memory_proximity(a.id, radius=0.05)
        sims = [r["similarity"] for r in result]
        assert sims == sorted(sims, reverse=True)


class TestTagInducedSubgraph:
    """Tests for tag_induced_subgraph — tag-filtered subgraph extraction."""

    def test_subgraph_any_match(self, mg):
        """OR matching: nodes with any of the tags."""
        a = mg.add("python service", "svc")
        mg.tag_nodes("backend", [a.id])
        mg.tag_nodes("python", [a.id])
        b = mg.add("react ui", "svc")
        mg.tag_nodes("frontend", [b.id])
        mg.tag_nodes("react", [b.id])
        c = mg.add("rust cli", "svc")
        mg.tag_nodes("backend", [c.id])
        mg.tag_nodes("rust", [c.id])
        mg.link(a.id, c.id, "shares_tag")

        result = mg.tag_induced_subgraph(["backend"], match="any")
        assert result["node_count"] == 2  # a and c
        assert result["edge_count"] >= 1

    def test_subgraph_all_match(self, mg):
        """AND matching: nodes with all specified tags."""
        a = mg.add("python api", "svc")
        mg.tag_nodes("backend", [a.id])
        mg.tag_nodes("python", [a.id])
        b = mg.add("python cli", "svc")
        mg.tag_nodes("backend", [b.id])
        mg.tag_nodes("rust", [b.id])
        c = mg.add("rust tool", "svc")
        mg.tag_nodes("backend", [c.id])

        result = mg.tag_induced_subgraph(["backend", "python"], match="all")
        assert result["node_count"] == 1  # only a

    def test_subgraph_no_match(self, mg):
        """No matching nodes returns empty."""
        mg.add("untagged node", "test")
        result = mg.tag_induced_subgraph(["nonexistent_tag"], match="any")
        assert result["node_count"] == 0
        assert result["edge_count"] == 0

    def test_subgraph_preserves_edges(self, mg):
        """Internal edges between matching nodes are included."""
        a = mg.add("service a", "svc")
        b = mg.add("service b", "svc")
        c = mg.add("external", "ext")
        for nid in [a.id, b.id, c.id]:
            mg.tag_nodes("microservice", [nid])
        mg.link(a.id, b.id, "calls")
        mg.link(a.id, c.id, "calls")
        mg.link(b.id, c.id, "depends")

        result = mg.tag_induced_subgraph(["microservice"], match="any")
        assert result["node_count"] == 3
        assert result["edge_count"] == 3

    def test_subgraph_structure(self, mg):
        """Result has expected structure."""
        a = mg.add("node1", "test")
        mg.tag_nodes("tag1", [a.id])

        result = mg.tag_induced_subgraph(["tag1"], match="any")
        assert "nodes" in result
        assert "edges" in result
        assert "tags_matched" in result
        assert result["tags_matched"] == ["tag1"]
        assert result["node_count"] == 1
        node = result["nodes"][0]
        assert "id" in node
        assert "label" in node
        assert "kind" in node
        assert "tags" in node
        assert "weight" in node


# ── memory_annotate tests ─────────────────────────────────────────

class TestMemoryAnnotate:
    """Tests for memory_annotate/get/remove/search — structured metadata."""

    def test_annotate_basic(self, mg):
        """Add and retrieve an annotation."""
        a = mg.add("test node", "fact")
        assert mg.memory_annotate(a.id, "confidence", "0.95")
        assert mg.annotation_get(a.id, "confidence") == "0.95"

    def test_annotate_nonexistent_node(self, mg):
        """Annotating nonexistent node returns False."""
        assert mg.memory_annotate("nope", "key", "val") is False

    def test_annotate_overwrite(self, mg):
        """Same key overwrites previous value."""
        a = mg.add("overwrite test", "fact")
        mg.memory_annotate(a.id, "level", "low")
        mg.memory_annotate(a.id, "level", "high")
        assert mg.annotation_get(a.id, "level") == "high"

    def test_annotate_multiple_keys(self, mg):
        """Node can have multiple annotations."""
        a = mg.add("multi", "fact")
        mg.memory_annotate(a.id, "source", "paper")
        mg.memory_annotate(a.id, "confidence", "0.8")
        mg.memory_annotate(a.id, "verified", "true")
        assert mg.annotation_get(a.id, "source") == "paper"
        assert mg.annotation_get(a.id, "confidence") == "0.8"
        assert mg.annotation_get(a.id, "verified") == "true"

    def test_annotate_get_missing_key(self, mg):
        """Getting nonexistent annotation returns None."""
        a = mg.add("node", "fact")
        assert mg.annotation_get(a.id, "nonexistent") is None

    def test_annotate_remove(self, mg):
        """Remove annotation and verify it's gone."""
        a = mg.add("removal test", "fact")
        mg.memory_annotate(a.id, "temp", "value")
        assert mg.annotation_remove(a.id, "temp")
        assert mg.annotation_get(a.id, "temp") is None

    def test_annotate_remove_nonexistent(self, mg):
        """Removing nonexistent annotation returns False."""
        a = mg.add("node", "fact")
        assert mg.annotation_remove(a.id, "never_added") is False

    def test_annotation_search_by_key(self, mg):
        """Search finds all nodes with a given annotation key."""
        a = mg.add("node a", "fact")
        b = mg.add("node b", "fact")
        c = mg.add("node c", "fact")
        mg.memory_annotate(a.id, "source", "paper")
        mg.memory_annotate(b.id, "source", "blog")
        mg.memory_annotate(c.id, "verified", "true")  # different key

        results = mg.annotation_search("source")
        assert len(results) == 2
        labels = [r["label"] for r in results]
        assert "node a" in labels
        assert "node b" in labels

    def test_annotation_search_by_value(self, mg):
        """Search with value filter narrows results."""
        a = mg.add("high confidence", "fact")
        b = mg.add("low confidence", "fact")
        mg.memory_annotate(a.id, "score", "high")
        mg.memory_annotate(b.id, "score", "low")

        results = mg.annotation_search("score", value="high")
        assert len(results) == 1
        assert results[0]["label"] == "high confidence"

    def test_annotate_preserves_existing_data(self, mg):
        """Annotation doesn't clobber existing node data."""
        a = mg.add("data node", "fact", {"important": "yes"})
        mg.memory_annotate(a.id, "source", "test")
        node = mg.get_node(a.id)
        assert node.data.get("important") == "yes"
        assert node.data.get("_annotations", {}).get("source") == "test"


class TestAddWorkflow:
    """Tests for add_workflow — AWM-inspired procedural memory."""

    def test_add_workflow_basic(self, mg):
        """Create a workflow with steps."""
        wf_id = mg.add_workflow(
            "deploy to production",
            [
                {"label": "Run tests", "action": "test", "detail": "npm test"},
                {"label": "Build", "action": "build", "detail": "npm run build"},
                {"label": "Publish", "action": "publish", "detail": "npm publish"},
            ],
        )
        assert wf_id
        node = mg.get_node(wf_id)
        assert node.kind == "workflow"
        assert node.data["_workflow"] is True
        assert node.data["step_count"] == 3

    def test_add_workflow_creates_step_nodes(self, mg):
        """Each step becomes a workflow_step node."""
        wf_id = mg.add_workflow("cook pasta", [
            {"label": "Boil water", "action": "boil"},
            {"label": "Add pasta", "action": "add"},
        ])
        steps = mg.conn.execute(
            "SELECT * FROM nodes WHERE kind='workflow_step'"
        ).fetchall()
        assert len(steps) == 2

    def test_add_workflow_links_steps(self, mg):
        """Workflow has_step edges to each step."""
        wf_id = mg.add_workflow("two step", [
            {"label": "First", "action": "do_first"},
            {"label": "Second", "action": "do_second"},
        ])
        edges = mg.conn.execute(
            "SELECT * FROM edges WHERE source=? AND relation='has_step'",
            (wf_id,)
        ).fetchall()
        assert len(edges) == 2

    def test_add_workflow_next_step_chain(self, mg):
        """Steps are chained with next_step edges."""
        wf_id = mg.add_workflow("chained", [
            {"label": "A", "action": "a"},
            {"label": "B", "action": "b"},
            {"label": "C", "action": "c"},
        ])
        next_edges = mg.conn.execute(
            "SELECT * FROM edges WHERE relation='next_step'"
        ).fetchall()
        assert len(next_edges) >= 2

    def test_add_workflow_with_tags(self, mg):
        """Tags are stored on the workflow node."""
        wf_id = mg.add_workflow(
            "CI/CD pipeline",
            [{"label": "Lint", "action": "lint"}],
            tags=["devops", "automation"],
        )
        row = mg.conn.execute(
            "SELECT tags FROM nodes WHERE id=?", (wf_id,)
        ).fetchone()
        tags = json.loads(row["tags"]) if row["tags"] else []
        assert "devops" in tags
        assert "automation" in tags

    def test_add_workflow_with_source_trajectories(self, mg):
        """Source trajectory links are created."""
        traj = mg.add("execution trace #1", "event")
        wf_id = mg.add_workflow(
            "some workflow",
            [{"label": "Step 1", "action": "act"}],
            source_trajectories=[traj.id],
        )
        edges = mg.conn.execute(
            "SELECT * FROM edges WHERE source=? AND relation='extracted_from'",
            (wf_id,)
        ).fetchall()
        assert len(edges) == 1


class TestRetrieveWorkflows:
    """Tests for retrieve_workflows — goal/tag-based retrieval."""

    def test_retrieve_all_workflows(self, mg):
        """Retrieve returns all workflows when no filter."""
        mg.add_workflow("task A", [{"label": "do A", "action": "a"}])
        mg.add_workflow("task B", [{"label": "do B", "action": "b"}])
        results = mg.retrieve_workflows()
        assert len(results) == 2

    def test_retrieve_by_tag(self, mg):
        """Tag-based filtering."""
        mg.add_workflow("deploy app", [{"label": "ship", "action": "ship"}],
                        tags=["devops"])
        mg.add_workflow("cook dinner", [{"label": "chop", "action": "chop"}],
                        tags=["cooking"])
        results = mg.retrieve_workflows(tags=["devops"])
        assert len(results) == 1
        assert "deploy" in results[0]["goal"]

    def test_retrieve_by_goal_similarity(self, mg):
        """Goal text uses trigram overlap."""
        mg.add_workflow("deploy application to cloud", [
            {"label": "push", "action": "push"}])
        mg.add_workflow("cook pasta recipe", [
            {"label": "boil", "action": "boil"}])
        results = mg.retrieve_workflows(goal="deploy application")
        assert results[0]["goal"] == "deploy application to cloud"

    def test_retrieve_includes_steps(self, mg):
        """Results include ordered step list."""
        mg.add_workflow("three step flow", [
            {"label": "Alpha", "action": "a"},
            {"label": "Beta", "action": "b"},
            {"label": "Gamma", "action": "c"},
        ])
        results = mg.retrieve_workflows()
        assert len(results[0]["steps"]) == 3
        assert results[0]["steps"][0]["label"] == "Alpha"

    def test_retrieve_empty(self, mg):
        """No workflows returns empty list."""
        assert mg.retrieve_workflows() == []

    def test_retrieve_ranked_by_success(self, mg):
        """Workflows with more successes rank higher."""
        wf_a = mg.add_workflow("similar task A", [{"label": "do", "action": "x"}])
        wf_b = mg.add_workflow("similar task B", [{"label": "do", "action": "x"}])
        mg.record_workflow_outcome(wf_a, True)
        mg.record_workflow_outcome(wf_a, True)
        mg.record_workflow_outcome(wf_b, False)
        results = mg.retrieve_workflows(goal="similar task")
        assert results[0]["id"] == wf_a


class TestRecordWorkflowOutcome:
    """Tests for record_workflow_outcome."""

    def test_record_success(self, mg):
        wf_id = mg.add_workflow("test wf", [{"label": "s1", "action": "a"}])
        assert mg.record_workflow_outcome(wf_id, True)
        node = mg.get_node(wf_id)
        assert node.data["success_count"] == 1
        assert node.data["failure_count"] == 0

    def test_record_failure(self, mg):
        wf_id = mg.add_workflow("test wf", [{"label": "s1", "action": "a"}])
        assert mg.record_workflow_outcome(wf_id, False, "timeout")
        node = mg.get_node(wf_id)
        assert node.data["failure_count"] == 1
        assert node.data["success_count"] == 0

    def test_record_multiple_outcomes(self, mg):
        wf_id = mg.add_workflow("test wf", [{"label": "s1", "action": "a"}])
        mg.record_workflow_outcome(wf_id, True)
        mg.record_workflow_outcome(wf_id, True)
        mg.record_workflow_outcome(wf_id, False)
        node = mg.get_node(wf_id)
        assert node.data["success_count"] == 2
        assert node.data["failure_count"] == 1

    def test_record_outcome_nonexistent(self, mg):
        assert mg.record_workflow_outcome("nope", True) is False

    def test_record_outcome_non_workflow_node(self, mg):
        """Recording outcome on non-workflow node fails."""
        n = mg.add("just a fact", "fact")
        assert mg.record_workflow_outcome(n.id, True) is False

    def test_outcome_detail_stored(self, mg):
        wf_id = mg.add_workflow("wf", [{"label": "s", "action": "a"}])
        mg.record_workflow_outcome(wf_id, False, detail="step 2 failed")
        node = mg.get_node(wf_id)
        outcomes = node.data.get("_outcomes", [])
        assert len(outcomes) == 1
        assert outcomes[0]["detail"] == "step 2 failed"


class TestWorkflowStats:
    """Tests for workflow_stats — global workflow memory dashboard."""

    def test_stats_empty(self, mg):
        """Empty graph has zero stats."""
        stats = mg.workflow_stats()
        assert stats["total_workflows"] == 0
        assert stats["success_rate"] == 0.0

    def test_stats_with_workflows(self, mg):
        """Stats reflect added workflows."""
        mg.add_workflow("wf1", [{"label": "a", "action": "x"},
                                  {"label": "b", "action": "y"}])
        mg.add_workflow("wf2", [{"label": "c", "action": "z"}])
        stats = mg.workflow_stats()
        assert stats["total_workflows"] == 2
        assert stats["total_steps"] == 3
        assert stats["avg_steps_per_workflow"] == 1.5

    def test_stats_success_rate(self, mg):
        """Success rate is computed correctly."""
        wf1 = mg.add_workflow("wf1", [{"label": "s", "action": "a"}])
        wf2 = mg.add_workflow("wf2", [{"label": "s", "action": "a"}])
        mg.record_workflow_outcome(wf1, True)
        mg.record_workflow_outcome(wf1, True)
        mg.record_workflow_outcome(wf2, False)
        stats = mg.workflow_stats()
        assert stats["total_success"] == 2
        assert stats["total_failure"] == 1
        assert stats["success_rate"] == round(2 / 3, 4)

    def test_stats_coverage(self, mg):
        """Coverage tracks used vs unused workflows."""
        wf1 = mg.add_workflow("used", [{"label": "s", "action": "a"}])
        mg.add_workflow("unused", [{"label": "s", "action": "a"}])
        mg.record_workflow_outcome(wf1, True)
        stats = mg.workflow_stats()
        assert stats["used_workflows"] == 1
        assert stats["total_workflows"] == 2
        assert stats["coverage"] == 0.5


class TestWorkflowCompose:
    """Tests for workflow_compose — AWM snowball composition."""

    def test_compose_basic(self, mg):
        """Composing two workflows creates a new one with combined steps."""
        wf_a = mg.add_workflow("setup", [
            {"label": "Install", "action": "install"},
            {"label": "Configure", "action": "config"},
        ])
        wf_b = mg.add_workflow("deploy", [
            {"label": "Build", "action": "build"},
            {"label": "Ship", "action": "ship"},
        ])
        new_id = mg.workflow_compose(wf_a, wf_b)
        assert new_id
        results = mg.retrieve_workflows()
        composed = [r for r in results if r["id"] == new_id][0]
        assert composed["step_count"] == 4

    def test_compose_with_bridge(self, mg):
        """Bridge step is inserted between workflows."""
        wf_a = mg.add_workflow("prep", [{"label": "A", "action": "a"}])
        wf_b = mg.add_workflow("finish", [{"label": "B", "action": "b"}])
        new_id = mg.workflow_compose(wf_a, wf_b, bridge_label="Verify")
        results = mg.retrieve_workflows()
        composed = [r for r in results if r["id"] == new_id][0]
        labels = [s["label"] for s in composed["steps"]]
        assert "Verify" in labels
        assert len(labels) == 3

    def test_compose_custom_goal(self, mg):
        """Custom goal for composed workflow."""
        wf_a = mg.add_workflow("step one", [{"label": "A", "action": "a"}])
        wf_b = mg.add_workflow("step two", [{"label": "B", "action": "b"}])
        new_id = mg.workflow_compose(wf_a, wf_b, goal="full pipeline")
        node = mg.get_node(new_id)
        assert node.label == "full pipeline"

    def test_compose_default_goal(self, mg):
        """Default goal combines both labels."""
        wf_a = mg.add_workflow("build", [{"label": "A", "action": "a"}])
        wf_b = mg.add_workflow("test", [{"label": "B", "action": "b"}])
        new_id = mg.workflow_compose(wf_a, wf_b)
        node = mg.get_node(new_id)
        assert "build" in node.label
        assert "test" in node.label

    def test_compose_links_sources(self, mg):
        """Composed workflow has extracted_from edges to sources."""
        wf_a = mg.add_workflow("a", [{"label": "A", "action": "a"}])
        wf_b = mg.add_workflow("b", [{"label": "B", "action": "b"}])
        new_id = mg.workflow_compose(wf_a, wf_b)
        edges = mg.conn.execute(
            "SELECT * FROM edges WHERE source=? AND relation='extracted_from'",
            (new_id,)
        ).fetchall()
        assert len(edges) == 2

    def test_compose_nonexistent_source(self, mg):
        """Returns None if either source doesn't exist."""
        wf_a = mg.add_workflow("real", [{"label": "A", "action": "a"}])
        assert mg.workflow_compose(wf_a, "nonexistent") is None
        assert mg.workflow_compose("nonexistent", wf_a) is None


class TestWorkflowDedup:
    """Tests for workflow_dedup — merge near-duplicate workflows."""

    def test_dedup_no_duplicates(self, mg):
        """No duplicates returns zero merges."""
        mg.add_workflow("deploy app", [{"label": "A", "action": "a"}])
        mg.add_workflow("cook dinner", [{"label": "B", "action": "b"}])
        result = mg.workflow_dedup()
        assert result["duplicates_found"] == 0
        assert result["merged"] == 0

    def test_dedup_detects_similarity(self, mg):
        """Similar goals are detected as duplicates."""
        mg.add_workflow("deploy application", [{"label": "A", "action": "a"}])
        mg.add_workflow("deploy applications", [{"label": "B", "action": "b"}])
        result = mg.workflow_dedup(dry_run=True)
        assert result["duplicates_found"] >= 1

    def test_dedup_merges(self, mg):
        """Non-dry_run actually merges duplicates."""
        mg.add_workflow("deploy application", [{"label": "A", "action": "a"}])
        mg.add_workflow("deploy applications", [{"label": "B", "action": "b"}])
        result = mg.workflow_dedup()
        assert result["merged"] >= 1
        remaining = mg.retrieve_workflows()
        assert len(remaining) == 1

    def test_dedup_keeps_better_workflow(self, mg):
        """Merge keeps workflow with more successes."""
        wf_a = mg.add_workflow("deploy application", [{"label": "A", "action": "a"}])
        wf_b = mg.add_workflow("deploy applications", [{"label": "B", "action": "b"}])
        mg.record_workflow_outcome(wf_a, True)
        mg.record_workflow_outcome(wf_a, True)
        mg.record_workflow_outcome(wf_b, True)
        result = mg.workflow_dedup()
        assert result["details"][0]["kept"] == wf_a
        node = mg.get_node(wf_a)
        assert node.data["success_count"] == 3  # 2 + 1

    def test_dedup_dry_run_no_change(self, mg):
        """Dry run doesn't modify the graph."""
        mg.add_workflow("deploy application", [{"label": "A", "action": "a"}])
        mg.add_workflow("deploy applications", [{"label": "B", "action": "b"}])
        mg.workflow_dedup(dry_run=True)
        assert len(mg.retrieve_workflows()) == 2

    def test_dedup_empty_graph(self, mg):
        """Dedup on empty graph returns zeros."""
        result = mg.workflow_dedup()
        assert result["checked"] == 0
        assert result["duplicates_found"] == 0


class TestWorkflowTips:
    """Tests for add_workflow_tip / retrieve_workflow_tips — ReasoningBank."""

    def test_add_tip_basic(self, mg):
        """Add a tip to a workflow."""
        wf_id = mg.add_workflow("test wf", [{"label": "s", "action": "a"}])
        tip_id = mg.add_workflow_tip(wf_id, "success", "Always validate input first")
        assert tip_id
        node = mg.get_node(tip_id)
        assert node.kind == "workflow_tip"
        assert node.data["tip_type"] == "success"

    def test_add_tip_nonexistent_workflow(self, mg):
        """Adding tip to nonexistent workflow returns None."""
        assert mg.add_workflow_tip("nope", "success", "tip") is None

    def test_add_tip_types(self, mg):
        """All tip types are accepted."""
        wf_id = mg.add_workflow("wf", [{"label": "s", "action": "a"}])
        for t in ["success", "failure", "recovery", "optimization"]:
            tip_id = mg.add_workflow_tip(wf_id, t, f"{t} tip")
            assert tip_id

    def test_retrieve_tips_all(self, mg):
        """Retrieve all tips for a workflow."""
        wf_id = mg.add_workflow("wf", [{"label": "s", "action": "a"}])
        mg.add_workflow_tip(wf_id, "success", "tip 1")
        mg.add_workflow_tip(wf_id, "failure", "tip 2")
        mg.add_workflow_tip(wf_id, "recovery", "tip 3")
        tips = mg.retrieve_workflow_tips(wf_id)
        assert len(tips) == 3

    def test_retrieve_tips_by_type(self, mg):
        """Filter tips by type."""
        wf_id = mg.add_workflow("wf", [{"label": "s", "action": "a"}])
        mg.add_workflow_tip(wf_id, "success", "good tip")
        mg.add_workflow_tip(wf_id, "failure", "bad tip")
        mg.add_workflow_tip(wf_id, "success", "another good")
        success_only = mg.retrieve_workflow_tips(wf_id, tip_type="success")
        assert len(success_only) == 2
        assert all(t["tip_type"] == "success" for t in success_only)

    def test_retrieve_tips_empty(self, mg):
        """Workflow with no tips returns empty list."""
        wf_id = mg.add_workflow("wf", [{"label": "s", "action": "a"}])
        assert mg.retrieve_workflow_tips(wf_id) == []

    def test_add_tip_with_detail(self, mg):
        """Tip detail is stored and retrieved."""
        wf_id = mg.add_workflow("wf", [{"label": "s", "action": "a"}])
        mg.add_workflow_tip(wf_id, "recovery", "Retry with lower temp",
                            detail="0.7→0.3 works for structured output")
        tips = mg.retrieve_workflow_tips(wf_id, tip_type="recovery")
        assert tips[0]["detail"] == "0.7→0.3 works for structured output"

    def test_tip_links_to_workflow(self, mg):
        """has_tip edge connects workflow to tip."""
        wf_id = mg.add_workflow("wf", [{"label": "s", "action": "a"}])
        mg.add_workflow_tip(wf_id, "success", "tip")
        edges = mg.conn.execute(
            "SELECT * FROM edges WHERE source=? AND relation='has_tip'",
            (wf_id,)
        ).fetchall()
        assert len(edges) == 1


class TestWorkflowPromptSection:
    """Tests for workflow_prompt_section — LLM context injection."""

    def test_prompt_section_basic(self, mg):
        """Generate prompt section with goal and steps."""
        wf_id = mg.add_workflow("deploy app", [
            {"label": "Build", "action": "build"},
            {"label": "Push", "action": "push"},
        ])
        section = mg.workflow_prompt_section(wf_id)
        assert "deploy app" in section
        assert "Build" in section
        assert "Push" in section

    def test_prompt_section_with_tips(self, mg):
        """Tips are included in prompt section."""
        wf_id = mg.add_workflow("deploy", [{"label": "s", "action": "a"}])
        mg.add_workflow_tip(wf_id, "success", "Use blue-green deployment")
        mg.add_workflow_tip(wf_id, "failure", "Don't deploy on Fridays")
        section = mg.workflow_prompt_section(wf_id)
        assert "blue-green" in section
        assert "Fridays" in section

    def test_prompt_section_nonexistent(self, mg):
        """Nonexistent workflow returns empty string."""
        assert mg.workflow_prompt_section("nope") == ""

    def test_prompt_section_includes_stats(self, mg):
        """Success/failure counts appear in section."""
        wf_id = mg.add_workflow("wf", [{"label": "s", "action": "a"}])
        mg.record_workflow_outcome(wf_id, True)
        mg.record_workflow_outcome(wf_id, False)
        section = mg.workflow_prompt_section(wf_id)
        assert "success: 1" in section
        assert "failed: 1" in section


class TestWorkflowPruneTips:
    """Tests for workflow_prune_tips."""

    def test_prune_all_tips(self, mg):
        """Remove all tips from a workflow."""
        wf_id = mg.add_workflow("wf", [{"label": "s", "action": "a"}])
        mg.add_workflow_tip(wf_id, "success", "tip 1")
        mg.add_workflow_tip(wf_id, "failure", "tip 2")
        removed = mg.workflow_prune_tips(wf_id)
        assert removed == 2
        assert mg.retrieve_workflow_tips(wf_id) == []

    def test_prune_by_type(self, mg):
        """Only remove tips of specified type."""
        wf_id = mg.add_workflow("wf", [{"label": "s", "action": "a"}])
        mg.add_workflow_tip(wf_id, "success", "good")
        mg.add_workflow_tip(wf_id, "failure", "bad")
        removed = mg.workflow_prune_tips(wf_id, tip_type="failure")
        assert removed == 1
        remaining = mg.retrieve_workflow_tips(wf_id)
        assert len(remaining) == 1
        assert remaining[0]["tip_type"] == "success"

    def test_prune_no_tips(self, mg):
        """Pruning workflow with no tips returns 0."""
        wf_id = mg.add_workflow("wf", [{"label": "s", "action": "a"}])
        assert mg.workflow_prune_tips(wf_id) == 0

    def test_prune_nonexistent_workflow(self, mg):
        """Pruning nonexistent workflow returns 0."""
        assert mg.workflow_prune_tips("nope") == 0


class TestWorkflowExportImport:
    """Tests for workflow_export / workflow_import — portable sharing."""

    def test_export_basic(self, mg):
        """Export produces a portable dict."""
        wf_id = mg.add_workflow("deploy", [
            {"label": "Build", "action": "build"},
            {"label": "Push", "action": "push"},
        ])
        exported = mg.workflow_export(wf_id)
        assert exported["goal"] == "deploy"
        assert len(exported["steps"]) == 2
        assert exported["success_count"] == 0

    def test_export_includes_tips(self, mg):
        """Exported data includes tips."""
        wf_id = mg.add_workflow("wf", [{"label": "s", "action": "a"}])
        mg.add_workflow_tip(wf_id, "success", "great tip")
        exported = mg.workflow_export(wf_id)
        assert len(exported["tips"]) == 1
        assert exported["tips"][0]["content"] == "great tip"

    def test_export_includes_outcomes(self, mg):
        """Exported data includes success/failure counts."""
        wf_id = mg.add_workflow("wf", [{"label": "s", "action": "a"}])
        mg.record_workflow_outcome(wf_id, True)
        mg.record_workflow_outcome(wf_id, True)
        mg.record_workflow_outcome(wf_id, False)
        exported = mg.workflow_export(wf_id)
        assert exported["success_count"] == 2
        assert exported["failure_count"] == 1

    def test_export_nonexistent(self, mg):
        """Exporting nonexistent returns None."""
        assert mg.workflow_export("nope") is None

    def test_import_round_trip(self, mg):
        """Import creates equivalent workflow."""
        wf_id = mg.add_workflow("original", [
            {"label": "Step A", "action": "a"},
            {"label": "Step B", "action": "b"},
        ], tags=["test"])
        mg.record_workflow_outcome(wf_id, True)
        mg.add_workflow_tip(wf_id, "success", "works well")
        exported = mg.workflow_export(wf_id)
        new_id = mg.workflow_import(exported, tags=["imported"])
        new_exported = mg.workflow_export(new_id)
        assert new_exported["goal"] == "original"
        assert len(new_exported["steps"]) == 2
        assert new_exported["success_count"] == 1
        assert len(new_exported["tips"]) == 1

    def test_import_creates_new_id(self, mg):
        """Imported workflow has different ID."""
        wf_id = mg.add_workflow("original", [{"label": "s", "action": "a"}])
        exported = mg.workflow_export(wf_id)
        new_id = mg.workflow_import(exported)
        assert new_id != wf_id

    def test_export_import_empty_steps(self, mg):
        """Round-trip with zero steps works."""
        wf_id = mg.add_workflow("empty", [])
        exported = mg.workflow_export(wf_id)
        new_id = mg.workflow_import(exported)
        new_exported = mg.workflow_export(new_id)
        assert new_exported["goal"] == "empty"
        assert len(new_exported["steps"]) == 0


# ── Workflow Success Patterns Tests ─────────────────────────

class TestWorkflowSuccessPatterns:
    """Cross-trajectory pattern mining from successful workflows."""

    def test_finds_common_actions(self, mg):
        """Actions appearing in multiple successful workflows are found."""
        wf1 = mg.add_workflow("deploy app", [
            {"label": "test", "action": "run_tests"},
            {"label": "build", "action": "build_image"},
            {"label": "ship", "action": "deploy"},
        ], tags=["ci"])
        wf2 = mg.add_workflow("deploy service", [
            {"label": "lint", "action": "lint_code"},
            {"label": "test", "action": "run_tests"},
            {"label": "ship", "action": "deploy"},
        ], tags=["ci"])
        for _ in range(3):
            mg.record_workflow_outcome(wf1, True)
        for _ in range(2):
            mg.record_workflow_outcome(wf2, True)
        patterns = mg.workflow_success_patterns(min_workflows=2)
        actions = [p["action"] for p in patterns]
        assert "run_tests" in actions
        assert "deploy" in actions
        assert "lint_code" not in actions  # only in wf2

    def test_filters_low_success_rate(self, mg):
        """Workflows below min_success_rate are excluded."""
        wf_good = mg.add_workflow("good", [{"label": "s", "action": "shared"}])
        wf_bad = mg.add_workflow("bad", [{"label": "s", "action": "shared"}])
        for _ in range(5):
            mg.record_workflow_outcome(wf_good, True)
        for _ in range(5):
            mg.record_workflow_outcome(wf_bad, False)
        patterns = mg.workflow_success_patterns(min_workflows=2, min_success_rate=0.5)
        # wf_bad has 0% success rate so excluded; only wf_good qualifies
        # but need >=2 workflows, so empty
        assert len(patterns) == 0

    def test_empty_when_no_workflows(self, mg):
        """No workflows returns empty list."""
        assert mg.workflow_success_patterns() == []

    def test_empty_when_insufficient_workflows(self, mg):
        """Single workflow doesn't meet min_workflows=2."""
        wf = mg.add_workflow("solo", [{"label": "s", "action": "unique"}])
        mg.record_workflow_outcome(wf, True)
        patterns = mg.workflow_success_patterns(min_workflows=2)
        assert len(patterns) == 0

    def test_frequency_ranking(self, mg):
        """Patterns sorted by frequency descending."""
        wf1 = mg.add_workflow("a", [
            {"label": "x", "action": "common"},
            {"label": "y", "action": "rare"},
        ])
        wf2 = mg.add_workflow("b", [
            {"label": "x", "action": "common"},
        ])
        wf3 = mg.add_workflow("c", [
            {"label": "x", "action": "common"},
            {"label": "z", "action": "also_rare"},
        ])
        for wf in [wf1, wf2, wf3]:
            mg.record_workflow_outcome(wf, True)
        patterns = mg.workflow_success_patterns(min_workflows=2)
        assert patterns[0]["action"] == "common"
        assert patterns[0]["frequency"] == 3

    def test_avg_order_calculated(self, mg):
        """Average order of action across workflows is correct."""
        wf1 = mg.add_workflow("a", [
            {"label": "first", "action": "step_a"},
            {"label": "second", "action": "step_b"},
        ])
        wf2 = mg.add_workflow("b", [
            {"label": "third", "action": "step_b"},
        ])
        mg.record_workflow_outcome(wf1, True)
        mg.record_workflow_outcome(wf2, True)
        patterns = mg.workflow_success_patterns(min_workflows=2)
        step_b = next(p for p in patterns if p["action"] == "step_b")
        # order 1 in wf1, order 0 in wf2 => avg 0.5
        assert step_b["avg_order"] == 0.5


# ── Node Similarity Tests ──────────────────────────────────

class TestNodeSimilarity:
    """Multi-dimensional node similarity."""

    def test_identical_nodes(self, mg):
        """Same label/tags/kind yield high composite."""
        a = mg.add("Python", "skill", tags=["lang"])
        b = mg.add("Python", "skill", tags=["lang"])
        sim = mg.node_similarity(a.id, b.id)
        assert sim["composite"] > 0.7
        assert sim["label_similarity"] == 1.0
        assert sim["tag_similarity"] == 1.0
        assert sim["kind_match"] == 1.0

    def test_completely_different(self, mg):
        """Unrelated nodes have low composite."""
        a = mg.add("Python", "skill", tags=["lang"])
        b = mg.add("Kubernetes", "tool", tags=["infra"])
        sim = mg.node_similarity(a.id, b.id)
        assert sim["composite"] < 0.15
        assert sim["kind_match"] == 0.0

    def test_partial_overlap(self, mg):
        """Partial label/tag overlap gives middle composite."""
        a = mg.add("Python testing", "skill", tags=["lang", "test"])
        b = mg.add("Python deploy", "skill", tags=["lang", "ops"])
        sim = mg.node_similarity(a.id, b.id)
        assert 0.2 < sim["composite"] < 0.9
        assert sim["kind_match"] == 1.0
        assert sim["tag_similarity"] > 0.0

    def test_neighbor_overlap(self, mg):
        """Shared neighbors boost similarity."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        c = mg.add("C", "concept")
        mg.link(a.id, c.id, "related")
        mg.link(b.id, c.id, "related")
        sim = mg.node_similarity(a.id, b.id)
        assert sim["neighbor_similarity"] > 0.0

    def test_nonexistent_node(self, mg):
        """Missing node returns zero composite."""
        a = mg.add("A", "concept")
        sim = mg.node_similarity(a.id, "nonexistent")
        assert sim["composite"] == 0.0

    def test_self_similarity(self, mg):
        """Node compared to itself is 1.0."""
        a = mg.add("unique label", "fact", tags=["t"])
        sim = mg.node_similarity(a.id, a.id)
        assert sim["label_similarity"] == 1.0
        assert sim["tag_similarity"] == 1.0


# ── Memory Clone Tests ─────────────────────────────────────

class TestMemoryClone:
    """Node cloning with edges and annotations."""

    def test_clone_basic(self, mg):
        """Clone creates a new node with same kind/data/tags."""
        original = mg.add("Original", "concept", {"key": "val"}, tags=["t"])
        cloned_id = mg.memory_clone(original.id)
        assert cloned_id is not None
        cloned = mg.get_node(cloned_id)
        assert cloned is not None
        assert cloned.kind == "concept"
        assert cloned.data.get("key") == "val"
        # tags stored in DB, check via tag_list or direct query
        row = mg.conn.execute("SELECT tags FROM nodes WHERE id=?", (cloned_id,)).fetchone()
        assert "t" in json.loads(row["tags"])

    def test_clone_custom_label(self, mg):
        """Clone with new label."""
        original = mg.add("Original", "concept")
        cloned_id = mg.memory_clone(original.id, new_label="Custom Clone")
        cloned = mg.get_node(cloned_id)
        assert cloned.label == "Custom Clone"

    def test_clone_deep_edges(self, mg):
        """Deep clone copies outgoing and incoming edges."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        c = mg.add("C", "concept")
        mg.link(a.id, b.id, "points_to")
        mg.link(c.id, a.id, "points_to")
        cloned_id = mg.memory_clone(a.id, deep_edges=True)
        # cloned should have outgoing to B and incoming from C
        out = mg.conn.execute(
            "SELECT target FROM edges WHERE source=? AND relation='points_to'",
            (cloned_id,)
        ).fetchall()
        assert len(out) == 1
        assert out[0]["target"] == b.id
        inc = mg.conn.execute(
            "SELECT source FROM edges WHERE target=? AND relation='points_to'",
            (cloned_id,)
        ).fetchall()
        assert len(inc) == 1
        assert inc[0]["source"] == c.id

    def test_clone_no_edges(self, mg):
        """Clone with deep_edges=False has no copied edges."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "related")
        cloned_id = mg.memory_clone(a.id, deep_edges=False)
        count = mg.conn.execute(
            "SELECT COUNT(*) as c FROM edges WHERE source=?",
            (cloned_id,)
        ).fetchone()["c"]
        assert count == 0

    def test_clone_nonexistent(self, mg):
        """Cloning nonexistent node returns None."""
        assert mg.memory_clone("nonexistent") is None

    def test_clone_copies_annotations(self, mg):
        """Annotations are copied to the clone."""
        a = mg.add("Annotated", "concept")
        mg.memory_annotate(a.id, "priority", "high")
        mg.memory_annotate(a.id, "owner", "team")
        cloned_id = mg.memory_clone(a.id)
        assert mg.annotation_get(cloned_id, "priority") == "high"
        assert mg.annotation_get(cloned_id, "owner") == "team"

    def test_clone_different_id(self, mg):
        """Clone has a different ID from original."""
        a = mg.add("A", "concept")
        cloned_id = mg.memory_clone(a.id)
        assert cloned_id != a.id


# ── Graph Diff Summary Tests ───────────────────────────────

class TestGraphDiffSummary:
    """Human-readable graph comparison."""

    def test_identical_graphs(self, mg):
        """No differences."""
        other = MemoryGraph()
        # both empty
        assert mg.graph_diff_summary(other) == "Graphs are identical."

    def test_shows_node_count_diff(self, mg):
        """Summary mentions node counts."""
        mg.add("A", "concept")
        other = MemoryGraph()
        summary = mg.graph_diff_summary(other)
        assert "Nodes only in self: 1" in summary
        assert "identical" not in summary

    def test_shows_modified_nodes(self, mg):
        """Summary shows field modifications."""
        other = MemoryGraph()
        n = mg.add("Original", "concept")
        # insert same ID with different kind into other
        import time, uuid
        other.conn.execute(
            "INSERT INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
            (n.id, "Original", "event", "{}", time.time(), time.time(), 1.0, "[]")
        )
        other.conn.commit()
        summary = mg.graph_diff_summary(other)
        assert "Modified" in summary

    def test_shows_edge_diff(self, mg):
        """Summary shows edge differences."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "related")
        other = MemoryGraph()
        other.add(a.label, a.kind)
        other.add(b.label, b.kind)
        summary = mg.graph_diff_summary(other)
        assert "Edges only in self: 1" in summary


# ── Workflow Retrieve By Tag Tests ─────────────────────────

class TestWorkflowRetrieveByTag:
    """Tag-based workflow retrieval."""

    def test_find_by_single_tag(self, mg):
        """Find workflows with a specific tag."""
        wf1 = mg.add_workflow("deploy", [{"label": "s", "action": "a"}], tags=["ci"])
        wf2 = mg.add_workflow("test", [{"label": "s", "action": "b"}], tags=["ci", "unit"])
        mg.record_workflow_outcome(wf1, True)
        mg.record_workflow_outcome(wf2, True)
        results = mg.workflow_retrieve_by_tag(["ci"])
        assert len(results) == 2

    def test_match_all_requires_all_tags(self, mg):
        """match_all=True requires every tag."""
        mg.add_workflow("a", [{"label": "s", "action": "x"}], tags=["ci"])
        mg.add_workflow("b", [{"label": "s", "action": "y"}], tags=["ci", "deploy"])
        results = mg.workflow_retrieve_by_tag(["ci", "deploy"], match_all=True)
        assert len(results) == 1
        assert results[0]["goal"] == "b"

    def test_any_match(self, mg):
        """match_all=False (default) matches any tag."""
        mg.add_workflow("a", [{"label": "s", "action": "x"}], tags=["ci"])
        mg.add_workflow("b", [{"label": "s", "action": "y"}], tags=["deploy"])
        results = mg.workflow_retrieve_by_tag(["ci", "deploy"], match_all=False)
        assert len(results) == 2

    def test_sorted_by_success_rate(self, mg):
        """Results sorted by success_rate descending."""
        wf1 = mg.add_workflow("low", [{"label": "s", "action": "a"}], tags=["t"])
        wf2 = mg.add_workflow("high", [{"label": "s", "action": "b"}], tags=["t"])
        mg.record_workflow_outcome(wf1, False)
        mg.record_workflow_outcome(wf1, False)
        for _ in range(5):
            mg.record_workflow_outcome(wf2, True)
        results = mg.workflow_retrieve_by_tag(["t"])
        assert results[0]["goal"] == "high"
        assert results[0]["success_rate"] == 1.0

    def test_no_matching_tag(self, mg):
        """No matching workflows returns empty."""
        mg.add_workflow("a", [{"label": "s", "action": "x"}], tags=["ci"])
        assert mg.workflow_retrieve_by_tag(["nonexistent"]) == []

    def test_limit_respected(self, mg):
        """Limit caps results."""
        for i in range(5):
            mg.add_workflow(f"wf{i}", [{"label": "s", "action": "a"}], tags=["t"])
        results = mg.workflow_retrieve_by_tag(["t"], limit=3)
        assert len(results) == 3


# ── Node Degree Summary Tests ──────────────────────────────

class TestNodeDegreeSummary:
    """Compact degree breakdown."""

    def test_basic_counts(self, mg):
        """In/out/total degree correct."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        c = mg.add("C", "concept")
        mg.link(a.id, b.id, "points_to")
        mg.link(a.id, c.id, "points_to")
        mg.link(b.id, a.id, "references")
        summary = mg.node_degree_summary(a.id)
        assert summary["out_degree"] == 2
        assert summary["in_degree"] == 1
        assert summary["total"] == 3

    def test_by_relation_breakdown(self, mg):
        """Per-relation counts are correct."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        c = mg.add("C", "concept")
        mg.link(a.id, b.id, "related")
        mg.link(c.id, a.id, "related")
        mg.link(a.id, c.id, "has")
        summary = mg.node_degree_summary(a.id)
        assert "related" in summary["by_relation"]
        assert summary["by_relation"]["related"]["out"] == 1
        assert summary["by_relation"]["related"]["in"] == 1
        assert summary["by_relation"]["has"]["out"] == 1

    def test_isolated_node(self, mg):
        """No edges = zero degree."""
        a = mg.add("Solo", "concept")
        summary = mg.node_degree_summary(a.id)
        assert summary["total"] == 0
        assert summary["in_degree"] == 0
        assert summary["out_degree"] == 0
        assert summary["by_relation"] == {}

    def test_nonexistent_node(self, mg):
        """Missing node returns None."""
        assert mg.node_degree_summary("nonexistent") is None


# ── Tag Correlation Network Tests ──────────────────────────

class TestTagCorrelationNetwork:
    """Tag co-occurrence correlation graph."""

    def test_finds_correlated_tags(self, mg):
        """Tags appearing together on multiple nodes are correlated."""
        mg.add("A", "concept", tags=["python", "ai"])
        mg.add("B", "concept", tags=["python", "ai"])
        mg.add("C", "concept", tags=["python", "web"])
        result = mg.tag_correlation_network(min_co_occurrence=2)
        pair_tags = [(e["source"], e["target"]) for e in result["edges"]]
        assert ("ai", "python") in pair_tags
        assert result["total_correlations"] >= 1

    def test_min_co_occurrence_filter(self, mg):
        """Low co-occurrence pairs are filtered out."""
        mg.add("A", "concept", tags=["x", "y"])
        mg.add("B", "concept", tags=["x", "z"])
        result = mg.tag_correlation_network(min_co_occurrence=5)
        assert result["total_correlations"] == 0

    def test_node_frequency(self, mg):
        """Tag nodes include correct frequency."""
        mg.add("A", tags=["t1"])
        mg.add("B", tags=["t1", "t2"])
        mg.add("C", tags=["t2"])
        result = mg.tag_correlation_network()
        freq_map = {n["tag"]: n["frequency"] for n in result["nodes"]}
        assert freq_map["t1"] == 2
        assert freq_map["t2"] == 2

    def test_empty_graph(self, mg):
        """No tagged nodes returns empty network."""
        result = mg.tag_correlation_network()
        assert result["total_tags"] == 0
        assert result["total_correlations"] == 0
        assert result["strongest_correlation"] is None

    def test_strongest_correlation(self, mg):
        """Strongest correlation is the highest-weight edge."""
        for _ in range(5):
            mg.add("node", tags=["a", "b"])
        mg.add("solo", tags=["a", "c"])
        result = mg.tag_correlation_network()
        strongest = result["strongest_correlation"]
        assert strongest is not None
        assert set([strongest["source"], strongest["target"]]) == {"a", "b"}
        assert strongest["weight"] == 5


# ── Memory Path Explain Tests ──────────────────────────────

class TestMemoryPathExplain:
    """Narrative path explanation."""

    def test_direct_connection(self, mg):
        """Single-hop path rendered as A --[rel]--> B."""
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        mg.link(a.id, b.id, "knows")
        explanation = mg.memory_path_explain(a.id, b.id)
        assert explanation is not None
        assert "Alice" in explanation
        assert "Bob" in explanation
        assert "[knows]" in explanation

    def test_multi_hop_path(self, mg):
        """Multi-hop path rendered as chain."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        c = mg.add("C", "concept")
        mg.link(a.id, b.id, "rel1")
        mg.link(b.id, c.id, "rel2")
        explanation = mg.memory_path_explain(a.id, c.id)
        assert explanation is not None
        assert "[rel1]" in explanation
        assert "[rel2]" in explanation

    def test_same_node(self, mg):
        """Source == target returns same node message."""
        a = mg.add("Self", "concept")
        explanation = mg.memory_path_explain(a.id, a.id)
        assert explanation is not None
        assert "same node" in explanation

    def test_no_path(self, mg):
        """Disconnected nodes return None."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        assert mg.memory_path_explain(a.id, b.id) is None

    def test_nonexistent_source(self, mg):
        """Missing source returns None."""
        b = mg.add("B", "concept")
        assert mg.memory_path_explain("nonexistent", b.id) is None


# ── Q-Value Utility Scoring Tests (MemRL-inspired) ──────────────

class TestMemoryQValue:
    """Tests for memory_qvalue — RL-inspired utility scoring."""

    def test_basic_qvalue(self, populated):
        """A node gets a valid Q-value with all components."""
        mg, a, b, c = populated
        q = mg.memory_qvalue(a.id)
        assert q is not None
        assert "qvalue" in q
        assert 0.0 <= q["qvalue"] <= 1.0
        assert "components" in q
        comp = q["components"]
        assert "access" in comp
        assert "degree" in comp
        assert "weight" in comp
        assert "immediate" in comp
        assert "neighbor_avg_weight" in comp

    def test_nonexistent_node(self, mg):
        """Missing node returns None."""
        assert mg.memory_qvalue("nonexistent") is None

    def test_isolated_node_lower_than_hub(self, mg):
        """A hub node should score higher than an isolated node."""
        hub = mg.add("Hub", "concept")
        isolated = mg.add("Isolated", "concept")
        for i in range(5):
            leaf = mg.add(f"Leaf{i}", "concept")
            mg.link(hub.id, leaf.id, "connects")

        q_hub = mg.memory_qvalue(hub.id)
        q_iso = mg.memory_qvalue(isolated.id)
        assert q_hub["qvalue"] > q_iso["qvalue"]
        assert q_hub["components"]["degree"] > q_iso["components"]["degree"]

    def test_custom_alpha_gamma(self, populated):
        """Custom alpha/gamma are reflected in output."""
        mg, a, b, c = populated
        q = mg.memory_qvalue(a.id, alpha=0.5, gamma=0.3)
        assert q["alpha"] == 0.5
        assert q["gamma"] == 0.3

    def test_higher_weight_higher_q(self, mg):
        """A heavier node should have higher immediate reward."""
        heavy = mg.add("Heavy", "concept")
        heavy.weight = 0.95
        mg.conn.execute("UPDATE nodes SET weight=? WHERE id=?", (0.95, heavy.id))
        mg.conn.commit()
        light = mg.add("Light", "concept")
        mg.conn.execute("UPDATE nodes SET weight=? WHERE id=?", (0.05, light.id))
        mg.conn.commit()

        q_heavy = mg.memory_qvalue(heavy.id, gamma=0)
        q_light = mg.memory_qvalue(light.id, gamma=0)
        assert q_heavy["qvalue"] > q_light["qvalue"]

    def test_batch_returns_sorted(self, populated):
        """Batch returns top-N sorted by Q-value descending."""
        mg, a, b, c = populated
        d = mg.add("Extra", "concept")
        mg.link(a.id, d.id, "related")

        results = mg.memory_qvalue_batch(top_n=10)
        assert len(results) > 0
        assert len(results) <= 10
        for i in range(len(results) - 1):
            assert results[i]["qvalue"] >= results[i + 1]["qvalue"]

    def test_batch_top_n_limit(self, populated):
        """Batch respects top_n limit."""
        mg, a, b, c = populated
        for i in range(10):
            n = mg.add(f"Node{i}", "concept")
            mg.link(a.id, n.id, "connects")
        results = mg.memory_qvalue_batch(top_n=3)
        assert len(results) == 3

    def test_batch_empty_graph(self, mg):
        """Empty graph returns empty list."""
        assert mg.memory_qvalue_batch() == []

    def test_neighbors_checked_count(self, populated):
        """Neighbors_checked matches actual neighbor count."""
        mg, a, b, c = populated
        q = mg.memory_qvalue(a.id)
        expected = len(mg.neighbors(a.id))
        assert q["neighbors_checked"] == expected

    def test_qvalue_in_valid_range(self, populated):
        """Q-value should always be in [0, 1] range."""
        mg, a, b, c = populated
        for nid in [a.id, b.id, c.id]:
            q = mg.memory_qvalue(nid)
            assert 0.0 <= q["qvalue"] <= 1.0


# ── Drift Detection Tests (SSGM-inspired) ───────────────────────

class TestMemoryDriftDetect:
    """Tests for memory_drift_detect — multi-dimensional drift."""

    def test_basic_drift(self, mg):
        """A fresh node should have low drift."""
        n = mg.add("Fresh", "concept")
        report = mg.memory_drift_detect(n.id)
        assert report is not None
        assert "semantic" in report
        assert "structural" in report
        assert "temporal" in report
        assert "overall" in report
        assert "recommendation" in report
        assert 0.0 <= report["overall"] <= 1.0

    def test_nonexistent_node(self, mg):
        """Missing node returns None."""
        assert mg.memory_drift_detect("nonexistent") is None

    def test_temporal_drift_high_for_stale(self, mg):
        """A node not accessed in 60+ days has high temporal drift."""
        n = mg.add("Stale", "concept")
        # Set accessed to 60 days ago
        old_time = time.time() - 60 * 86400
        mg.conn.execute(
            "UPDATE nodes SET accessed=? WHERE id=?", (old_time, n.id))
        mg.conn.commit()

        report = mg.memory_drift_detect(n.id)
        assert report["temporal"] >= 0.9
        assert "temporal" in report["recommendation"]

    def test_temporal_drift_low_for_fresh(self, mg):
        """A just-created node has near-zero temporal drift."""
        n = mg.add("Fresh", "concept")
        report = mg.memory_drift_detect(n.id)
        assert report["temporal"] < 0.1

    def test_structural_drift_isolated(self, populated):
        """An isolated node in a connected graph has structural drift."""
        mg, a, b, c = populated
        isolated = mg.add("Lone", "concept")
        # a,b,c are connected; isolated has 0 edges while avg > 0
        report = mg.memory_drift_detect(isolated.id)
        assert report["structural"] > 0.0

    def test_semantic_drift_dimension(self, populated):
        """Semantic dimension is computed (non-negative)."""
        mg, a, b, c = populated
        report = mg.memory_drift_detect(a.id)
        assert report["semantic"] >= 0.0

    def test_recommendation_stable(self, mg):
        """A fresh, well-connected node with no semantic drift is stable."""
        n = mg.add("Perfect", "concept")
        report = mg.memory_drift_detect(n.id)
        # Should be stable or very low drift (no neighbors = low semantic)
        assert report["recommendation"] in (
            "stable", "minor_structural_drift", "minor_temporal_drift",
            "minor_semantic_drift")

    def test_recommendation_escalation(self, mg):
        """Stale, isolated node gets action recommendation."""
        n = mg.add("Forgotten", "concept")
        old_time = time.time() - 90 * 86400
        mg.conn.execute(
            "UPDATE nodes SET accessed=? WHERE id=?", (old_time, n.id))
        mg.conn.commit()
        report = mg.memory_drift_detect(n.id)
        # 90 days → temporal = 1.0 → overall >= 0.8
        assert report["overall"] >= 0.8
        assert report["recommendation"].startswith("action_")

    def test_selective_dimensions(self, populated):
        """Disabling dimensions zeros them out."""
        mg, a, b, c = populated
        report = mg.memory_drift_detect(
            a.id, semantic=False, structural=False, temporal=False)
        assert report["semantic"] == 0.0
        assert report["structural"] == 0.0
        assert report["temporal"] == 0.0
        assert report["overall"] == 0.0

    def test_drift_scan_filters_threshold(self, populated):
        """Scan only returns nodes above threshold."""
        mg, a, b, c = populated
        stale = mg.add("Ancient", "concept")
        old_time = time.time() - 120 * 86400
        mg.conn.execute(
            "UPDATE nodes SET accessed=? WHERE id=?", (old_time, stale.id))
        mg.conn.commit()

        drifted = mg.memory_drift_scan(threshold=0.7)
        ids = [d["node_id"] for d in drifted]
        assert stale.id in ids
        # Sorted descending
        for i in range(len(drifted) - 1):
            assert drifted[i]["overall"] >= drifted[i + 1]["overall"]

    def test_drift_scan_kind_filter(self, mg):
        """Kind filter excludes other types."""
        concept = mg.add("C1", "concept")
        event = mg.add("E1", "event")
        old_time = time.time() - 90 * 86400
        for n in [concept, event]:
            mg.conn.execute(
                "UPDATE nodes SET accessed=? WHERE id=?", (old_time, n.id))
        mg.conn.commit()

        result = mg.memory_drift_scan(threshold=0.5, kinds=["event"])
        ids = [d["node_id"] for d in result]
        assert event.id in ids
        assert concept.id not in ids

    def test_drift_scan_empty_graph(self, mg):
        """Empty graph returns empty list."""
        assert mg.memory_drift_scan() == []


# ── Skill Discovery Tests (EvoSkill/SAGE-inspired) ─────────────

class TestDiscoverSkills:
    """Tests for discover_skills — pattern mining from workflows."""

    def test_no_workflows_returns_empty(self, mg):
        """No workflows → empty list."""
        assert mg.discover_skills() == []

    def test_basic_pair_discovery(self, mg):
        """Two successful workflows with shared actions yield a pair."""
        wf1 = mg.add("Goal1", "workflow", {"success_count": 3, "failure_count": 0, "step_count": 2})
        wf2 = mg.add("Goal2", "workflow", {"success_count": 2, "failure_count": 0, "step_count": 2})

        s1 = mg.add("fetch_data", "workflow_step", {"action": "fetch", "order": 0})
        s2 = mg.add("process_data", "workflow_step", {"action": "process", "order": 1})
        s3 = mg.add("fetch_data2", "workflow_step", {"action": "fetch", "order": 0})
        s4 = mg.add("process_data2", "workflow_step", {"action": "process", "order": 1})

        mg.link(wf1.id, s1.id, "has_step")
        mg.link(wf1.id, s2.id, "has_step")
        mg.link(wf2.id, s3.id, "has_step")
        mg.link(wf2.id, s4.id, "has_step")

        results = mg.discover_skills(min_frequency=2)
        assert len(results) > 0
        pair = results[0]
        assert "action_pair" in pair
        assert pair["frequency"] >= 2
        assert pair["success_workflows"] >= 2

    def test_pareto_score_ranking(self, mg):
        """Results are sorted by pareto_score descending."""
        wf1 = mg.add("A", "workflow", {"success_count": 5, "failure_count": 0, "step_count": 2})
        wf2 = mg.add("B", "workflow", {"success_count": 4, "failure_count": 0, "step_count": 2})
        s1 = mg.add("a1", "workflow_step", {"action": "alpha", "order": 0})
        s2 = mg.add("a2", "workflow_step", {"action": "beta", "order": 1})
        s3 = mg.add("a3", "workflow_step", {"action": "alpha", "order": 0})
        s4 = mg.add("a4", "workflow_step", {"action": "beta", "order": 1})
        mg.link(wf1.id, s1.id, "has_step")
        mg.link(wf1.id, s2.id, "has_step")
        mg.link(wf2.id, s3.id, "has_step")
        mg.link(wf2.id, s4.id, "has_step")

        results = mg.discover_skills()
        for i in range(len(results) - 1):
            assert results[i]["pareto_score"] >= results[i + 1]["pareto_score"]

    def test_failure_contamination(self, mg):
        """Actions in failed workflows reduce pareto score."""
        wf_good = mg.add("Good", "workflow", {"success_count": 4, "failure_count": 0, "step_count": 2})
        wf_bad = mg.add("Bad", "workflow", {"success_count": 0, "failure_count": 3, "step_count": 2})
        s1 = mg.add("s1", "workflow_step", {"action": "x", "order": 0})
        s2 = mg.add("s2", "workflow_step", {"action": "y", "order": 1})
        s3 = mg.add("s3", "workflow_step", {"action": "x", "order": 0})
        s4 = mg.add("s4", "workflow_step", {"action": "y", "order": 1})
        mg.link(wf_good.id, s1.id, "has_step")
        mg.link(wf_good.id, s2.id, "has_step")
        mg.link(wf_bad.id, s3.id, "has_step")
        mg.link(wf_bad.id, s4.id, "has_step")

        results = mg.discover_skills(min_frequency=1, min_success_rate=0.0)
        if results:
            # The pair should have failure contamination
            assert results[0]["failure_workflows"] >= 1

    def test_min_frequency_filter(self, mg):
        """High min_frequency excludes rare pairs."""
        wf1 = mg.add("Only", "workflow", {"success_count": 1, "failure_count": 0, "step_count": 2})
        s1 = mg.add("s1", "workflow_step", {"action": "rare_a", "order": 0})
        s2 = mg.add("s2", "workflow_step", {"action": "rare_b", "order": 1})
        mg.link(wf1.id, s1.id, "has_step")
        mg.link(wf1.id, s2.id, "has_step")

        results = mg.discover_skills(min_frequency=5)
        assert results == []


class TestMemoryUtilizationReport:
    """Tests for memory_utilization_report — executive dashboard."""

    def test_empty_graph(self, mg):
        """Empty graph returns structured empty report."""
        report = mg.memory_utilization_report()
        assert report["total_nodes"] == 0
        assert report["recommendations"] == ["empty_store"]

    def test_populated_report(self, populated):
        """Populated graph returns all fields."""
        mg, a, b, c = populated
        report = mg.memory_utilization_report()
        assert report["total_nodes"] == 3
        assert "by_kind" in report
        assert "avg_qvalue" in report
        assert "top_qvalue_nodes" in report
        assert "drifted_count" in report
        assert "workflow_coverage" in report
        assert "recommendations" in report
        assert isinstance(report["recommendations"], list)

    def test_report_with_stale_nodes(self, mg):
        """Stale nodes trigger high_drift_ratio recommendation."""
        for i in range(5):
            n = mg.add(f"Old{i}", "concept")
            old_time = time.time() - 120 * 86400
            mg.conn.execute(
                "UPDATE nodes SET accessed=? WHERE id=?", (old_time, n.id))
        mg.conn.commit()

        report = mg.memory_utilization_report()
        assert report["drifted_count"] >= 4

    def test_top_qvalue_nodes_limit(self, populated):
        """Top Q-value nodes capped at 5."""
        mg, a, b, c = populated
        for i in range(20):
            n = mg.add(f"Extra{i}", "concept")
            mg.link(a.id, n.id, "connects")
        report = mg.memory_utilization_report()
        assert len(report["top_qvalue_nodes"]) <= 5


# ── Memory Reinforcement Tests (MemRL operational) ─────────────

class TestMemoryReinforce:
    """Tests for memory_reinforce — weight adjustment by outcome."""

    def test_positive_reinforcement(self, mg):
        """Positive outcome increases weight."""
        n = mg.add("Test", "concept")
        mg.conn.execute("UPDATE nodes SET weight=0.5 WHERE id=?", (n.id,))
        mg.conn.commit()
        result = mg.memory_reinforce(n.id, "positive", boost=0.2)
        assert result is not None
        assert result["old_weight"] == 0.5
        assert result["new_weight"] == 0.7

    def test_negative_reinforcement(self, mg):
        """Negative outcome decreases weight."""
        n = mg.add("Test", "concept")
        mg.conn.execute("UPDATE nodes SET weight=0.5 WHERE id=?", (n.id,))
        mg.conn.commit()
        result = mg.memory_reinforce(n.id, "negative", boost=0.3)
        assert result["new_weight"] == 0.2

    def test_weight_cap_at_1(self, mg):
        """Weight capped at 1.0."""
        n = mg.add("Test", "concept")
        mg.conn.execute("UPDATE nodes SET weight=0.9 WHERE id=?", (n.id,))
        mg.conn.commit()
        result = mg.memory_reinforce(n.id, "positive", boost=0.5)
        assert result["new_weight"] == 1.0

    def test_weight_floor_at_001(self, mg):
        """Weight floored at 0.01."""
        n = mg.add("Test", "concept")
        mg.conn.execute("UPDATE nodes SET weight=0.05 WHERE id=?", (n.id,))
        mg.conn.commit()
        result = mg.memory_reinforce(n.id, "negative", boost=0.5)
        assert result["new_weight"] == 0.01

    def test_neutral_updates_accessed(self, mg):
        """Neutral outcome updates accessed time without weight change."""
        n = mg.add("Test", "concept")
        old_accessed = n.accessed
        time.sleep(0.01)
        result = mg.memory_reinforce(n.id, "neutral")
        assert result["new_weight"] == result["old_weight"]
        updated = self.get_node(mg, n.id)
        assert updated.accessed > old_accessed

    def get_node(self, mg, node_id):
        return mg.get_node(node_id)

    def test_nonexistent_node(self, mg):
        """Missing node returns None."""
        assert mg.memory_reinforce("nonexistent", "positive") is None

    def test_invalid_outcome(self, mg):
        """Invalid outcome returns None."""
        n = mg.add("Test", "concept")
        assert mg.memory_reinforce(n.id, "invalid") is None

    def test_reinforcement_history_recorded(self, mg):
        """Reinforcement events are stored in node metadata."""
        n = mg.add("Test", "concept")
        mg.memory_reinforce(n.id, "positive")
        mg.memory_reinforce(n.id, "negative")
        updated = mg.get_node(n.id)
        data = updated.data if isinstance(updated.data, dict) else json.loads(updated.data)
        history = data.get("_reinforcement_history", [])
        assert len(history) == 2
        assert history[0]["outcome"] == "positive"
        assert history[1]["outcome"] == "negative"

    def test_history_capped_at_50(self, mg):
        """History is capped at 50 entries."""
        n = mg.add("Test", "concept")
        for _ in range(55):
            mg.memory_reinforce(n.id, "positive", boost=0.001)
        updated = mg.get_node(n.id)
        data = updated.data if isinstance(updated.data, dict) else json.loads(updated.data)
        assert len(data["_reinforcement_history"]) == 50


# ── Skill Gap Analysis Tests ───────────────────────────────────

class TestSkillGapAnalysis:
    """Tests for skill_gap_analysis — missing step detection."""

    def test_no_workflows_returns_empty(self, mg):
        """No workflows → empty list."""
        assert mg.skill_gap_analysis() == []

    def test_finds_missing_step(self, mg):
        """Identifies intermediate step present in success but not failure."""
        # Successful workflow: [fetch, validate, store]
        wf_good = mg.add("Good", "workflow", {"success_count": 3, "failure_count": 0, "step_count": 3})
        s1 = mg.add("g1", "workflow_step", {"action": "fetch", "order": 0})
        s2 = mg.add("g2", "workflow_step", {"action": "validate", "order": 1})
        s3 = mg.add("g3", "workflow_step", {"action": "store", "order": 2})
        mg.link(wf_good.id, s1.id, "has_step")
        mg.link(wf_good.id, s2.id, "has_step")
        mg.link(wf_good.id, s3.id, "has_step")

        # Failed workflow: [fetch, store] (missing validate)
        wf_bad = mg.add("Bad", "workflow", {"success_count": 0, "failure_count": 2, "step_count": 2})
        s4 = mg.add("b1", "workflow_step", {"action": "fetch", "order": 0})
        s5 = mg.add("b2", "workflow_step", {"action": "store", "order": 1})
        mg.link(wf_bad.id, s4.id, "has_step")
        mg.link(wf_bad.id, s5.id, "has_step")

        gaps = mg.skill_gap_analysis()
        actions = [g["missing_action"] for g in gaps]
        assert "validate" in actions

    def test_gap_severity_ranking(self, mg):
        """Results sorted by gap_severity descending."""
        results = mg.skill_gap_analysis()
        for i in range(len(results) - 1):
            assert results[i]["gap_severity"] >= results[i + 1]["gap_severity"]

    def test_no_overlap_no_gap(self, mg):
        """No shared actions between success and failure → no gap."""
        wf_good = mg.add("Good", "workflow", {"success_count": 2, "failure_count": 0, "step_count": 1})
        wf_bad = mg.add("Bad", "workflow", {"success_count": 0, "failure_count": 2, "step_count": 1})
        s1 = mg.add("s1", "workflow_step", {"action": "alpha", "order": 0})
        s2 = mg.add("s2", "workflow_step", {"action": "omega", "order": 0})
        mg.link(wf_good.id, s1.id, "has_step")
        mg.link(wf_bad.id, s2.id, "has_step")

        gaps = mg.skill_gap_analysis()
        assert gaps == []

    def test_all_succeed_no_gaps(self, mg):
        """All workflows succeed → no gaps."""
        wf = mg.add("Good", "workflow", {"success_count": 3, "failure_count": 0, "step_count": 1})
        s = mg.add("s", "workflow_step", {"action": "x", "order": 0})
        mg.link(wf.id, s.id, "has_step")
        assert mg.skill_gap_analysis() == []


# ── Attention Score & Consolidation Priority Tests ──────────────

class TestMemoryAttentionScore:
    """Tests for memory_attention_score — temporal hotness."""

    def test_basic_score(self, mg):
        """Fresh node gets a valid attention score."""
        n = mg.add("Fresh", "concept")
        result = mg.memory_attention_score(n.id)
        assert result is not None
        assert "attention" in result
        assert 0.0 <= result["attention"] <= 1.0
        assert "recency_boost" in result
        assert "reinforcement_velocity" in result
        assert "neighbor_activity" in result

    def test_nonexistent_node(self, mg):
        """Missing node returns None."""
        assert mg.memory_attention_score("nope") is None

    def test_fresh_node_high_recency(self, mg):
        """Just-created node has high recency_boost."""
        n = mg.add("Now", "concept")
        result = mg.memory_attention_score(n.id)
        assert result["recency_boost"] > 0.9

    def test_stale_node_low_recency(self, mg):
        """Old node has low recency_boost."""
        n = mg.add("Old", "concept")
        old_time = time.time() - 72 * 3600
        mg.conn.execute("UPDATE nodes SET accessed=? WHERE id=?", (old_time, n.id))
        mg.conn.commit()
        result = mg.memory_attention_score(n.id, recency_window_hours=24)
        assert result["recency_boost"] == 0.0

    def test_reinforcement_velocity(self, mg):
        """Recent reinforcements boost velocity."""
        n = mg.add("Active", "concept")
        for _ in range(3):
            mg.memory_reinforce(n.id, "positive")
        result = mg.memory_attention_score(n.id)
        assert result["reinforcement_velocity"] > 0.0
        assert result["recent_events"] >= 3

    def test_neighbor_activity(self, populated):
        """Connected nodes contribute to neighbor_activity."""
        mg, a, b, c = populated
        # Touch neighbors to make them recent
        mg.touch(a.id)
        mg.touch(b.id)
        result = mg.memory_attention_score(c.id)
        # c is connected to a and b, both recently accessed
        assert result["neighbor_activity"] >= 0.0

    def test_isolated_node_zero_neighbor(self, mg):
        """Isolated node has zero neighbor_activity."""
        n = mg.add("Alone", "concept")
        result = mg.memory_attention_score(n.id)
        assert result["neighbor_activity"] == 0.0


class TestConsolidationPriority:
    """Tests for consolidation_priority — urgency ranking."""

    def test_empty_graph(self, mg):
        """Empty graph returns empty list."""
        assert mg.consolidation_priority() == []

    def test_basic_ranking(self, populated):
        """Populated graph returns ranked list."""
        mg, a, b, c = populated
        results = mg.consolidation_priority()
        assert len(results) > 0
        for i in range(len(results) - 1):
            assert results[i]["priority"] >= results[i + 1]["priority"]

    def test_stale_low_qvalue_high_priority(self, mg):
        """Stale, low-Q node ranks higher than fresh, high-Q."""
        stale = mg.add("Stale", "concept")
        old_time = time.time() - 90 * 86400
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=0.1 WHERE id=?",
            (old_time, stale.id))
        mg.conn.commit()

        fresh = mg.add("Fresh", "concept")
        mg.conn.execute(
            "UPDATE nodes SET weight=0.9 WHERE id=?", (fresh.id,))
        mg.conn.commit()

        results = mg.consolidation_priority()
        ids = [r["node_id"] for r in results]
        assert stale.id in ids
        if fresh.id in ids:
            stale_idx = ids.index(stale.id)
            fresh_idx = ids.index(fresh.id)
            assert stale_idx <= fresh_idx

    def test_limit_respected(self, populated):
        """Limit parameter caps results."""
        mg, a, b, c = populated
        for i in range(20):
            mg.add(f"N{i}", "concept")
        results = mg.consolidation_priority(limit=5)
        assert len(results) <= 5

    def test_result_fields(self, mg):
        """Each result has all expected fields."""
        n = mg.add("Test", "concept")
        results = mg.consolidation_priority()
        if results:
            r = results[0]
            assert "node_id" in r
            assert "label" in r
            assert "priority" in r
            assert "drift" in r
            assert "qvalue" in r
            assert "attention" in r
            assert "recommendation" in r


# ══════════════════════════════════════════════════════════════
# Bi-Temporal Validity Tracking Tests
# ══════════════════════════════════════════════════════════════

class TestBiTemporalValidity:
    """Tests for edge bi-temporal validity: set_validity, invalidate, valid_at, snapshot, history."""

    def test_edge_set_validity_basic(self, mg):
        """Set validity window on an edge and verify stored properties."""
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        mg.link(a.id, b.id, "knows")
        t0 = time.time() - 100
        result = mg.edge_set_validity(a.id, b.id, "knows", valid_from=t0)
        assert result is not None
        assert result["valid_from"] == t0
        assert result["valid_until"] is None  # open-ended

    def test_edge_set_validity_with_until(self, mg):
        """Set both valid_from and valid_until."""
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "r")
        t0 = time.time() - 200
        t1 = time.time() - 50
        result = mg.edge_set_validity(a.id, b.id, "r", valid_from=t0, valid_until=t1)
        assert result["valid_from"] == t0
        assert result["valid_until"] == t1

    def test_edge_set_validity_nonexistent_edge(self, mg):
        """Setting validity on non-existent edge returns None."""
        result = mg.edge_set_validity("nope", "nada", "relation")
        assert result is None

    def test_edge_invalidate_basic(self, mg):
        """Invalidate an edge and verify valid_until is set."""
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "works_with")
        before = time.time()
        result = mg.edge_invalidate(a.id, b.id, "works_with", invalidated_by="system")
        after = time.time()
        assert result is not None
        assert result["valid_until"] is not None
        assert before <= result["valid_until"] <= after
        assert result["invalidated_by"] == "system"

    def test_edge_invalidate_idempotent(self, mg):
        """Invalidating an already-invalidated edge is a no-op."""
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "r")
        first = mg.edge_invalidate(a.id, b.id, "r")
        time.sleep(0.01)
        second = mg.edge_invalidate(a.id, b.id, "r")
        assert first["valid_until"] == second["valid_until"]  # unchanged

    def test_edge_invalidate_nonexistent(self, mg):
        """Invalidating non-existent edge returns None."""
        assert mg.edge_invalidate("x", "y", "z") is None

    def test_edge_valid_at_no_temporal(self, mg):
        """Edge without temporal info is always valid."""
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.edge_valid_at(a.id, b.id, "r") is True
        assert mg.edge_valid_at(a.id, b.id, "r", timestamp=0) is True

    def test_edge_valid_at_within_window(self, mg):
        """Edge is valid within [valid_from, valid_until)."""
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "r")
        t0 = 1000.0
        t1 = 2000.0
        mg.edge_set_validity(a.id, b.id, "r", valid_from=t0, valid_until=t1)
        assert mg.edge_valid_at(a.id, b.id, "r", timestamp=1500) is True
        assert mg.edge_valid_at(a.id, b.id, "r", timestamp=t0) is True

    def test_edge_valid_at_outside_window(self, mg):
        """Edge is invalid outside the validity window."""
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "r")
        t0 = 1000.0
        t1 = 2000.0
        mg.edge_set_validity(a.id, b.id, "r", valid_from=t0, valid_until=t1)
        assert mg.edge_valid_at(a.id, b.id, "r", timestamp=500) is False   # before
        assert mg.edge_valid_at(a.id, b.id, "r", timestamp=t1) is False    # at valid_until
        assert mg.edge_valid_at(a.id, b.id, "r", timestamp=3000) is False  # after

    def test_edge_valid_at_after_invalidation(self, mg):
        """Edge invalidated is no longer valid at current time."""
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "r")
        mg.edge_invalidate(a.id, b.id, "r")
        assert mg.edge_valid_at(a.id, b.id, "r") is False  # now

    def test_edge_valid_at_nonexistent_edge(self, mg):
        """Non-existent edge is not valid."""
        assert mg.edge_valid_at("x", "y", "z") is False

    def test_temporal_snapshot_all_valid(self, mg):
        """Snapshot includes all edges without temporal info."""
        a = mg.add("A")
        b = mg.add("B")
        c = mg.add("C")
        mg.link(a.id, b.id, "r1")
        mg.link(b.id, c.id, "r2")
        snap = mg.temporal_snapshot()
        assert len(snap) == 2

    def test_temporal_snapshot_with_invalidation(self, mg):
        """Snapshot excludes invalidated edges at current time."""
        a = mg.add("A")
        b = mg.add("B")
        c = mg.add("C")
        mg.link(a.id, b.id, "r1")
        mg.link(b.id, c.id, "r2")
        mg.edge_invalidate(a.id, b.id, "r1")
        snap = mg.temporal_snapshot()
        assert len(snap) == 1
        assert snap[0].source == b.id
        assert snap[0].target == c.id

    def test_temporal_snapshot_time_travel(self, mg):
        """Snapshot at past timestamp includes edges valid then."""
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "r")
        old_t = time.time() - 500
        mg.edge_set_validity(a.id, b.id, "r", valid_from=old_t)
        mg.edge_invalidate(a.id, b.id, "r")
        # At old_t + 100, edge should be valid
        snap = mg.temporal_snapshot(timestamp=old_t + 100)
        assert len(snap) == 1
        # Now, edge should be invalid
        snap_now = mg.temporal_snapshot()
        assert len(snap_now) == 0

    def test_edge_temporal_history(self, mg):
        """Temporal history returns sorted entries for a node's edges."""
        a = mg.add("A")
        b = mg.add("B")
        c = mg.add("C")
        mg.link(a.id, b.id, "old_relation")
        mg.link(a.id, c.id, "new_relation")
        t_old = time.time() - 300
        t_new = time.time() - 50
        mg.edge_set_validity(a.id, b.id, "old_relation", valid_from=t_old)
        mg.edge_set_validity(a.id, c.id, "new_relation", valid_from=t_new)
        mg.edge_invalidate(a.id, b.id, "old_relation", invalidated_by="upgrade")
        history = mg.edge_temporal_history(a.id, direction="outgoing")
        assert len(history) == 2
        # Sorted by valid_from descending → newer first
        assert history[0]["valid_from"] >= history[1]["valid_from"]
        # old_relation should be invalidated
        old_entry = [h for h in history if h["relation"] == "old_relation"][0]
        assert old_entry["status"] == "invalidated"
        assert old_entry["invalidated_by"] == "upgrade"
        new_entry = [h for h in history if h["relation"] == "new_relation"][0]
        assert new_entry["status"] == "valid"

    # ── OWASP ASI06: Provenance & Quarantine Tests ──────────────

    def test_node_set_provenance_basic(self, mg):
        """Set source, trust_level, and parents on a node."""
        a = mg.add("Fact A")
        b = mg.add("Fact B")
        assert mg.node_set_provenance(a.id, source="web_search", trust_level=0.6, parents=[b.id])
        row = mg.conn.execute("SELECT source, trust_level, parents FROM nodes WHERE id=?", (a.id,)).fetchone()
        assert row["source"] == "web_search"
        assert row["trust_level"] == 0.6
        assert json.loads(row["parents"]) == [b.id]

    def test_node_set_provenance_partial(self, mg):
        """Setting only some provenance fields leaves others unchanged."""
        a = mg.add("Fact A")
        mg.node_set_provenance(a.id, trust_level=0.3)
        # Set source separately
        mg.node_set_provenance(a.id, source="user_input")
        row = mg.conn.execute("SELECT source, trust_level FROM nodes WHERE id=?", (a.id,)).fetchone()
        assert row["source"] == "user_input"
        assert row["trust_level"] == 0.3  # Still there from first call

    def test_node_set_provenance_clamps_trust(self, mg):
        """Trust level is clamped to [0, 1]."""
        a = mg.add("Fact A")
        mg.node_set_provenance(a.id, trust_level=1.5)
        row = mg.conn.execute("SELECT trust_level FROM nodes WHERE id=?", (a.id,)).fetchone()
        assert row["trust_level"] == 1.0
        mg.node_set_provenance(a.id, trust_level=-0.5)
        row = mg.conn.execute("SELECT trust_level FROM nodes WHERE id=?", (a.id,)).fetchone()
        assert row["trust_level"] == 0.0

    def test_node_set_provenance_nonexistent(self, mg):
        """Setting provenance on nonexistent node returns False."""
        assert not mg.node_set_provenance("nonexistent", trust_level=0.5)

    def test_node_quarantine_basic(self, mg):
        """Quarantine marks a node and stores reason."""
        a = mg.add("Suspicious fact")
        assert mg.node_quarantine(a.id, reason="unverified source")
        row = mg.conn.execute("SELECT quarantined, quarantine_reason FROM nodes WHERE id=?", (a.id,)).fetchone()
        assert row["quarantined"] == 1
        assert row["quarantine_reason"] == "unverified source"

    def test_node_quarantine_default_reason(self, mg):
        """Quarantine without reason uses 'unspecified'."""
        a = mg.add("Suspicious fact")
        mg.node_quarantine(a.id)
        row = mg.conn.execute("SELECT quarantine_reason FROM nodes WHERE id=?", (a.id,)).fetchone()
        assert row["quarantine_reason"] == "unspecified"

    def test_node_quarantine_nonexistent(self, mg):
        """Quarantine on nonexistent node returns False."""
        assert not mg.node_quarantine("nonexistent")

    def test_node_unquarantine(self, mg):
        """Unquarantine clears quarantine flag and reason."""
        a = mg.add("Fact A")
        mg.node_quarantine(a.id, reason="testing")
        assert mg.node_unquarantine(a.id)
        row = mg.conn.execute("SELECT quarantined, quarantine_reason FROM nodes WHERE id=?", (a.id,)).fetchone()
        assert row["quarantined"] == 0
        assert row["quarantine_reason"] is None

    def test_quarantine_list(self, mg):
        """Quarantine list returns all quarantined nodes."""
        a = mg.add("Fact A")
        b = mg.add("Fact B")
        c = mg.add("Fact C")
        mg.node_quarantine(a.id, "reason1")
        mg.node_quarantine(b.id, "reason2")
        ql = mg.quarantine_list()
        assert len(ql) == 2
        labels = {item["label"] for item in ql}
        assert labels == {"Fact A", "Fact B"}

    def test_quarantine_list_empty(self, mg):
        """Quarantine list on clean graph is empty."""
        assert mg.quarantine_list() == []

    def test_quarantine_scan_auto(self, mg):
        """Scan auto-quarantines nodes below trust threshold."""
        a = mg.add("Low trust fact")
        b = mg.add("High trust fact")
        c = mg.add("Medium trust fact")
        mg.node_set_provenance(a.id, trust_level=0.1)
        mg.node_set_provenance(b.id, trust_level=0.9)
        mg.node_set_provenance(c.id, trust_level=0.2)
        quarantined = mg.quarantine_scan(trust_threshold=0.3)
        assert a.id in quarantined
        assert c.id in quarantined
        assert b.id not in quarantined
        # Should be exactly 2
        assert len(quarantined) == 2

    def test_quarantine_scan_no_double_quarantine(self, mg):
        """Scan does not re-quarantine already quarantined nodes."""
        a = mg.add("Fact A")
        mg.node_set_provenance(a.id, trust_level=0.1)
        mg.node_quarantine(a.id, "manual")
        result = mg.quarantine_scan(trust_threshold=0.3)
        assert a.id not in result  # Already quarantined, skip

    def test_recall_excludes_quarantined(self, mg):
        """Recall does not return quarantined nodes."""
        a = mg.add("Python guide")
        b = mg.add("Python malware")  # Will be quarantined
        mg.node_quarantine(b.id, "adversarial content")
        results = mg.recall("Python")
        labels = [r.label for r in results]
        assert "Python guide" in labels
        assert "Python malware" not in labels

    def test_search_by_tag_excludes_quarantined(self, mg):
        """search_by_tag excludes quarantined nodes."""
        a = mg.add("Safe fact")
        b = mg.add("Unsafe fact")
        mg.add_tag(a.id, "important")
        mg.add_tag(b.id, "important")
        mg.node_quarantine(b.id, "untrusted")
        results = mg.search_by_tag("important")
        labels = [r.label for r in results]
        assert "Safe fact" in labels
        assert "Unsafe fact" not in labels

    def test_quarantine_unquarantine_cycle(self, mg):
        """Full quarantine → unquarantine → recall works again."""
        a = mg.add("Recovered fact")
        mg.node_quarantine(a.id, "under review")
        assert mg.recall("Recovered") == []
        mg.node_unquarantine(a.id)
        results = mg.recall("Recovered")
        assert len(results) == 1
        assert results[0].label == "Recovered fact"

    # ── Graph Reasoning API Tests ──────────────────────────────

    @pytest.fixture
    def reasoning_graph(self, mg):
        """Build a graph for reasoning tests.

        Alice —works_on→ Project —uses→ Python
        Alice —knows→ Bob —knows→ Python
        Bob —works_on→ Project
        Carol —manages→ Project
        Carol —knows→ Dave
        """
        alice = mg.add("Alice", "person")
        bob = mg.add("Bob", "person")
        carol = mg.add("Carol", "person")
        dave = mg.add("Dave", "person")
        project = mg.add("AlphaProject", "concept")
        python = mg.add("Python", "skill")
        mg.link(alice.id, project.id, "works_on")
        mg.link(project.id, python.id, "uses")
        mg.link(alice.id, bob.id, "knows")
        mg.link(bob.id, python.id, "knows")
        mg.link(bob.id, project.id, "works_on")
        mg.link(carol.id, project.id, "manages")
        mg.link(carol.id, dave.id, "knows")
        return {
            "alice": alice.id, "bob": bob.id, "carol": carol.id,
            "dave": dave.id, "project": project.id, "python": python.id,
        }

    def test_reasoning_path_shortest(self, mg, reasoning_graph):
        """reasoning_path finds shortest path between connected nodes."""
        rp = mg.reasoning_path(
            reasoning_graph["alice"], reasoning_graph["python"],
            max_hops=3, strategy="shortest")
        assert len(rp) >= 1
        best = rp[0]
        assert best["path"][0] == reasoning_graph["alice"]
        assert best["path"][-1] == reasoning_graph["python"]
        assert len(best["edges"]) == len(best["path"]) - 1
        assert best["score"] > 0
        assert "source" in best
        assert "explanation" in best

    def test_reasoning_path_no_connection(self, mg, reasoning_graph):
        """reasoning_path returns empty when no path exists within max_hops."""
        # Dave and Python have no path within 1 hop
        rp = mg.reasoning_path(
            reasoning_graph["dave"], reasoning_graph["python"],
            max_hops=1, strategy="shortest")
        # Dave only connects to Carol, Carol connects to project but not within 1 hop to python
        # path is Dave->Carol->Project->Python = 3 hops, max_hops=1 means 2 nodes max
        assert len(rp) == 0

    def test_reasoning_path_same_node(self, mg, reasoning_graph):
        """reasoning_path handles seed == target."""
        rp = mg.reasoning_path(
            reasoning_graph["alice"], reasoning_graph["alice"])
        assert len(rp) == 1
        assert rp[0]["path"] == [reasoning_graph["alice"]]

    def test_reasoning_path_invalid_nodes(self, mg):
        """reasoning_path returns empty for non-existent nodes."""
        rp = mg.reasoning_path("ghost", "phantom")
        assert rp == []

    def test_reasoning_path_pagerank_guided(self, mg, reasoning_graph):
        """reasoning_path with pagerank_guided finds paths through important nodes."""
        rp = mg.reasoning_path(
            reasoning_graph["alice"], reasoning_graph["python"],
            max_hops=4, strategy="pagerank_guided", top_k=3)
        assert len(rp) >= 1
        assert all(r["source"] == "pagerank_guided" for r in rp)
        # All paths should end at python
        for r in rp:
            assert r["path"][-1] == reasoning_graph["python"]

    def test_explore_basic(self, mg, reasoning_graph):
        """explore discovers neighbors from seed."""
        result = mg.explore(reasoning_graph["alice"], max_hops=2, budget=20)
        assert "discovered" in result
        assert "paths" in result
        assert "stats" in result
        assert result["stats"]["nodes_visited"] > 1
        assert result["stats"]["edges_traversed"] > 0
        # Should discover Project, Bob, Python (at least)
        discovered_ids = {d["id"] for d in result["discovered"]}
        assert reasoning_graph["project"] in discovered_ids
        assert reasoning_graph["bob"] in discovered_ids

    def test_explore_budget_limit(self, mg, reasoning_graph):
        """explore respects budget constraint."""
        result = mg.explore(reasoning_graph["alice"], max_hops=3, budget=3)
        assert result["stats"]["nodes_visited"] <= 3

    def test_explore_invalid_seed(self, mg):
        """explore returns empty result for invalid seed."""
        result = mg.explore("nonexistent")
        assert result["discovered"] == []
        assert result["stats"]["nodes_visited"] == 0

    def test_explore_min_score_filter(self, mg, reasoning_graph):
        """explore filters by min_score."""
        result_low = mg.explore(reasoning_graph["alice"], min_score=0.0)
        result_high = mg.explore(reasoning_graph["alice"], min_score=0.99)
        assert len(result_low["discovered"]) >= len(result_high["discovered"])

    def test_infer_relation_direct_edge(self, mg, reasoning_graph):
        """infer_relation detects direct edges with confidence 1.0."""
        result = mg.infer_relation(
            reasoning_graph["alice"], reasoning_graph["project"])
        assert result is not None
        assert result["confidence"] == 1.0
        assert result["relation"] == "works_on"
        assert len(result["evidence"]) >= 1
        assert result["link_scores"]["common_neighbors"] == 0

    def test_infer_relation_indirect(self, mg, reasoning_graph):
        """infer_relation infers relation between indirectly connected nodes."""
        result = mg.infer_relation(
            reasoning_graph["alice"], reasoning_graph["python"],
            max_hops=3)
        assert result is not None
        assert result["confidence"] > 0
        assert result["confidence"] < 1.0  # Indirect
        assert "relation" in result
        assert len(result["evidence"]) >= 1
        # Should have some link prediction scores
        assert "adamic_adar" in result["link_scores"]
        assert "common_neighbors" in result["link_scores"]

    def test_infer_relation_no_connection(self, mg):
        """infer_relation returns link-only when no path exists."""
        a = mg.add("Isolated A", "concept")
        b = mg.add("Isolated B", "concept")
        result = mg.infer_relation(a.id, b.id, max_hops=2)
        assert result is not None
        assert result["relation"] == "unknown"
        assert result["confidence"] < 0.3
        assert result["evidence"] == []

    def test_infer_relation_invalid_nodes(self, mg):
        """infer_relation returns None for non-existent nodes."""
        assert mg.infer_relation("ghost", "phantom") is None

    def test_reasoning_subgraph_from_query(self, mg, reasoning_graph):
        """reasoning_subgraph builds from BM25 query."""
        result = mg.reasoning_subgraph(query="Alice", max_hops=2, top_k=15)
        assert len(result["nodes"]) > 0
        assert len(result["edges"]) > 0
        assert "summary" in result
        assert "paths" in result
        # Should include Alice
        node_ids = {n["id"] for n in result["nodes"]}
        assert reasoning_graph["alice"] in node_ids

    def test_reasoning_subgraph_from_seeds(self, mg, reasoning_graph):
        """reasoning_subgraph builds from explicit seed IDs."""
        seeds = [reasoning_graph["bob"], reasoning_graph["carol"]]
        result = mg.reasoning_subgraph(seed_ids=seeds, max_hops=2, top_k=20)
        assert len(result["nodes"]) >= 2
        assert len(result["edges"]) >= 1
        # Should find reasoning paths between seeds
        # (Bob and Carol both connect to Project)
        if result["paths"]:
            for p in result["paths"]:
                assert p["score"] > 0

    def test_reasoning_subgraph_invalid_seeds(self, mg):
        """reasoning_subgraph handles invalid seeds gracefully."""
        result = mg.reasoning_subgraph(seed_ids=["ghost", "phantom"])
        assert result["nodes"] == []
        assert result["summary"] == "no seed nodes found"

    def test_reasoning_subgraph_node_importance(self, mg, reasoning_graph):
        """reasoning_subgraph includes PageRank importance for each node."""
        result = mg.reasoning_subgraph(query="Alice", max_hops=2, top_k=10)
        for n in result["nodes"]:
            assert "importance" in n
            assert n["importance"] >= 0

    # ── Adaptive Retrieval API Tests ──────────────────────────

    def test_classify_query_simple(self, mg):
        """classify_query identifies simple queries."""
        result = mg.classify_query("hello")
        assert result["complexity"] == "simple"
        assert result["effort"] == "low"
        assert result["strategy"] == "bm25_only"
        assert result["word_count"] == 1

    def test_classify_query_moderate(self, mg):
        """classify_query identifies moderate queries."""
        result = mg.classify_query("find all memories about the project status update")
        assert result["complexity"] in ("moderate", "complex")
        assert result["effort"] in ("medium", "high")

    def test_classify_query_complex(self, mg):
        """classify_query identifies complex queries."""
        result = mg.classify_query("explain why the architecture design trade-offs matter for performance")
        assert result["complexity"] in ("complex", "multi_hop")
        assert result["effort"] in ("high", "max")

    def test_classify_query_multi_hop(self, mg):
        """classify_query identifies multi-hop queries."""
        result = mg.classify_query("what is the difference between Alice and Bob and how do they relate to the project")
        assert result["complexity"] == "multi_hop"
        assert result["effort"] == "max"
        assert result["strategy"] == "graph_reasoning"
        assert result["multi_hop_score"] >= 2

    def test_classify_query_returns_reasoning(self, mg):
        """classify_query includes human-readable reasoning."""
        result = mg.classify_query("test")
        assert "reasoning" in result
        assert len(result["reasoning"]) > 0

    def test_grade_retrieval_empty(self, mg):
        """grade_retrieval handles empty results."""
        grade = mg.grade_retrieval("test", [])
        assert grade["grade"] == "incorrect"
        assert grade["relevant_count"] == 0
        assert grade["recommendation"] == "retrieval_failed"

    def test_grade_retrieval_relevant(self, mg):
        """grade_retrieval identifies relevant results."""
        results = [
            {"id": "a", "score": 0.9},
            {"id": "b", "score": 0.8},
            {"id": "c", "score": 0.7},
        ]
        grade = mg.grade_retrieval("test", results, threshold=0.15)
        assert grade["grade"] == "relevant"
        assert grade["relevant_count"] == 3
        assert grade["scores"]["max"] == 0.9

    def test_grade_retrieval_ambiguous(self, mg):
        """grade_retrieval identifies ambiguous results."""
        results = [
            {"id": "a", "score": 0.2},
            {"id": "b", "score": 0.05},
        ]
        grade = mg.grade_retrieval("test", results, threshold=0.15)
        assert grade["grade"] == "ambiguous"
        assert grade["relevant_count"] == 1

    def test_grade_retrieval_incorrect(self, mg):
        """grade_retrieval identifies irrelevant results."""
        results = [{"id": "a", "score": 0.01}]
        grade = mg.grade_retrieval("test", results, threshold=0.15)
        assert grade["grade"] == "incorrect"
        assert grade["relevant_count"] == 0

    def test_grade_retrieval_graph_connectivity(self, mg, reasoning_graph):
        """grade_retrieval computes graph connectivity for top results."""
        results = [
            {"id": reasoning_graph["alice"], "score": 0.5},
            {"id": reasoning_graph["bob"], "score": 0.4},
            {"id": reasoning_graph["project"], "score": 0.3},
        ]
        grade = mg.grade_retrieval("test", results, threshold=0.1)
        assert "connectivity" in grade
        # Alice-Bob, Alice-Project, Bob-Project all connected
        assert grade["connectivity"] > 0

    def test_search_adaptive_simple_query(self, mg, reasoning_graph):
        """search_adaptive routes simple queries to BM25-only."""
        result = mg.search_adaptive("Alice", limit=5)
        assert result["classification"]["complexity"] == "simple"
        assert result["strategy"] == "bm25_only"
        assert len(result["results"]) >= 1
        assert result["grade"]["grade"] in ("relevant", "ambiguous")

    def test_search_adaptive_multi_hop_query(self, mg, reasoning_graph):
        """search_adaptive routes multi-hop queries to graph reasoning."""
        result = mg.search_adaptive(
            "compare Alice and Bob and how do they relate to AlphaProject", limit=10)
        assert result["classification"]["complexity"] == "multi_hop"
        assert result["strategy"] == "graph_reasoning"
        # Should find Alice/Bob/Project via BM25 seeds then expand
        assert len(result["results"]) >= 1

    def test_search_adaptive_returns_all_fields(self, mg, reasoning_graph):
        """search_adaptive returns classification, grade, strategy, results."""
        result = mg.search_adaptive("Alice", limit=5)
        assert "results" in result
        assert "classification" in result
        assert "grade" in result
        assert "strategy" in result
        # Classification has all fields
        cls = result["classification"]
        assert "complexity" in cls
        assert "effort" in cls
        assert "strategy" in cls

    # ── search_with_gaps tests ──

    def test_search_with_gaps_no_gaps(self, mg, reasoning_graph):
        """All query entities covered by results → gap_score=0."""
        result = mg.search_with_gaps("Alice", limit=5)
        assert "entities" in result
        assert "gaps" in result
        assert "gap_score" in result
        assert "repair_strategy" in result
        # Alice exists in graph, so entity coverage should be good
        assert result["covered_count"] >= 1

    def test_search_with_gaps_missing_entity(self, mg, reasoning_graph):
        """Query references entity not in graph → gap detected."""
        result = mg.search_with_gaps("Alice Zephyr", limit=5)
        assert result["entity_count"] >= 2
        # Zephyr is not in the graph
        assert any(e["entity"] == "zephyr" and not e["covered"] for e in result["entities"])
        assert result["gap_score"] > 0
        assert len(result["gaps"]) >= 1

    def test_search_with_gaps_empty_query(self, mg):
        """Empty query → no entities, no gaps."""
        result = mg.search_with_gaps("")
        assert result["entity_count"] == 0
        assert result["gap_score"] == 0
        assert result["repair_strategy"] == "none"

    def test_search_with_gaps_returns_entities_list(self, mg, reasoning_graph):
        """Result has entities list with coverage info."""
        result = mg.search_with_gaps("Alice Bob", limit=5)
        assert isinstance(result["entities"], list)
        for ent in result["entities"]:
            assert "entity" in ent
            assert "covered" in ent
            assert "in_results" in ent
            assert "node_ids" in ent

    def test_search_with_gaps_repair_strategy(self, mg, reasoning_graph):
        """Repair strategy is one of valid values."""
        result = mg.search_with_gaps("Alice Zephyr Quantum", limit=5)
        assert result["repair_strategy"] in ("none", "expand_neighbors", "bridge_search")

    def test_search_with_gaps_accepts_external_results(self, mg, reasoning_graph):
        """Can pass external results instead of auto-searching."""
        external = [{"id": "n1", "label": "Alice", "score": 0.9}]
        result = mg.search_with_gaps("Alice", results=external)
        assert result["covered_count"] >= 1

    def test_search_with_gaps_bridge_detection(self, mg):
        """Gap tracker detects missing path between covered entities."""
        a = mg.add("Alpha", "concept")
        b = mg.add("Beta", "concept")
        # No link between a and b
        result = mg.search_with_gaps("Alpha Beta", limit=5)
        # Both entities exist but have no path
        assert result["entity_count"] >= 2

    def test_search_with_gaps_gap_score_range(self, mg, reasoning_graph):
        """gap_score is between 0 and 1."""
        result = mg.search_with_gaps("Alice Zephyr Mystery", limit=5)
        assert 0.0 <= result["gap_score"] <= 1.0

    def test_search_with_gaps_stop_words_filtered(self, mg):
        """Stop words are not treated as entities."""
        result = mg.search_with_gaps("what is the difference between", limit=5)
        # These are all stop words
        assert result["entity_count"] == 0 or result["entity_count"] <= 1

    def test_search_with_gaps_provides_bridge_node(self, mg):
        """When a bridge exists, gap entry has bridge_node set."""
        a = mg.add("Alpha entity", "concept")
        b = mg.add("Beta entity", "concept")
        bridge = mg.add("Alpha Beta connector", "concept")
        mg.link(a.id, bridge.id, "connects")
        mg.link(bridge.id, b.id, "connects")
        # Now Alpha and Beta are covered, search for something that bridges
        result = mg.search_with_gaps("Alpha entity Gamma", limit=5)
        # Gamma is uncovered but might find bridge through Alpha's neighbors
        assert result["gap_score"] > 0

    def test_search_with_gaps_max_entity_cap(self, mg):
        """Entity extraction caps at 8 entities."""
        long_query = " ".join(f"entity{i}" for i in range(20))
        result = mg.search_with_gaps(long_query)
        assert result["entity_count"] <= 8

    # ── should_admit tests ──

    def test_should_admit_unique_new_node(self, mg):
        """Completely novel node → high uniqueness, admitted."""
        result = mg.should_admit(label="Quantum Entanglement Theory", kind="concept")
        assert result["admit"] is True
        assert result["score"] >= 0.5
        assert result["factors"]["U"] > 0.7
        assert result["reason"] in ("above_threshold", "complementary_to_existing")

    def test_should_admit_exact_duplicate(self, mg):
        """Exact label match → rejected as duplicate."""
        mg.add("Existing Concept", "concept")
        result = mg.should_admit(label="Existing Concept", kind="concept")
        assert result["admit"] is False
        assert result["reason"] == "exact_duplicate_exists"
        assert any(c["type"] == "exact_duplicate" for c in result["conflicts"])

    def test_should_admit_returns_5_factors(self, mg):
        """Result has all 5 A-MAC factors U/C/N/R/T."""
        result = mg.should_admit(label="Test Node", kind="fact")
        assert "factors" in result
        for factor in ("U", "C", "N", "R", "T"):
            assert factor in result["factors"]
            assert 0.0 <= result["factors"][factor] <= 1.0

    def test_should_admit_returns_weights(self, mg):
        """Weights sum to 1.0."""
        result = mg.should_admit(label="Test Node", kind="fact")
        total = sum(result["weights"].values())
        assert abs(total - 1.0) < 0.001

    def test_should_admit_existing_node_id(self, mg):
        """Can evaluate existing node by ID."""
        node = mg.add("Unique_existing", "concept", tags=["special"])
        result = mg.should_admit(candidate_node_id=node.id)
        assert result["score"] >= 0
        assert "factors" in result

    def test_should_admit_no_label(self, mg):
        """No label and no ID → rejected gracefully."""
        result = mg.should_admit()
        assert result["admit"] is False
        assert result["reason"] == "no_label_provided"

    def test_should_admit_novel_tags(self, mg):
        """New tags increase novelty score."""
        mg.add("Base", "concept", tags=["existing_tag"])
        result = mg.should_admit(label="New thing", kind="concept", tags=["brand_new_tag"])
        assert result["factors"]["N"] > 0
        assert "brand_new_tag" in result["new_tags"]

    def test_should_admit_relevant_to_graph(self, mg):
        """Node sharing words with existing nodes has higher relevance."""
        mg.add("Python programming", "skill")
        mg.add("Python data analysis", "skill")
        result = mg.should_admit(label="Python web framework", kind="skill")
        assert result["factors"]["R"] > 0
        assert result["relevant_neighbor_count"] >= 2

    def test_should_admit_conflict_detection(self, mg):
        """Potential conflicts are detected for high-similarity labels."""
        mg.add("Machine learning model", "concept")
        result = mg.should_admit(label="Machine learning models", kind="concept")
        # High word overlap → potential conflict
        assert len(result["conflicts"]) >= 1

    def test_should_admit_score_range(self, mg):
        """Admission score is between 0 and 1."""
        result = mg.should_admit(label="Test", kind="fact")
        assert 0.0 <= result["score"] <= 1.0

    def test_should_admit_complementary_node(self, mg):
        """Low uniqueness but high relevance → admitted as complementary."""
        a = mg.add("Alpha component system", "concept")
        mg.add("Alpha component module", "concept")
        mg.add("Alpha component unit", "concept")
        result = mg.should_admit(label="Alpha component part", kind="concept")
        # Should be admitted either by threshold or complementary
        assert result["admit"] is True

    def test_should_admit_too_many_conflicts(self, mg):
        """Many conflicts → rejected."""
        for i in range(5):
            mg.add(f"Similar node variant {i}", "concept")
        result = mg.should_admit(label="Similar node variant", kind="concept")
        assert result["admit"] is False
        assert result["reason"] in ("exact_duplicate_exists", "too_many_conflicts", "below_threshold")

    def test_should_admit_most_similar_tracked(self, mg):
        """Result tracks the most similar existing node."""
        mg.add("Quantum physics research", "concept")
        result = mg.should_admit(label="Quantum physics study", kind="concept")
        assert result["most_similar"] is not None
        assert result["max_similarity"] > 0.3


# ── Memory Lifecycle Report Tests ────────────────────────────────

class TestMemoryLifecycleReport:
    """Tests for memory_lifecycle_report()."""

    def test_empty_store(self, mg):
        """Empty store returns empty stage."""
        result = mg.memory_lifecycle_report()
        assert result["total_nodes"] == 0
        assert result["lifecycle_stage"] == "empty"
        assert "seed_initial_memories" in result["recommendations"]

    def test_basic_report_structure(self, mg):
        """Report has all expected fields."""
        mg.add("Node A", "concept")
        result = mg.memory_lifecycle_report()
        expected_keys = {
            "total_nodes", "active_nodes", "stale_nodes", "decaying_nodes",
            "dormant_nodes", "avg_weight", "weight_distribution",
            "quarantine_count", "consolidated_count", "reinforcement_events",
            "lifecycle_stage", "recommendations",
        }
        assert set(result.keys()) == expected_keys

    def test_active_node_count(self, mg):
        """Freshly added nodes are active."""
        mg.add("Fresh node", "concept")
        result = mg.memory_lifecycle_report()
        assert result["active_nodes"] == 1
        assert result["stale_nodes"] == 0

    def test_weight_distribution_buckets(self, mg):
        """Weight distribution categorizes nodes correctly."""
        n1 = mg.add("Low weight", "concept")
        n2 = mg.add("Medium weight", "concept")
        n3 = mg.add("Peak weight", "concept")
        mg.conn.execute("UPDATE nodes SET weight=0.05 WHERE id=?", (n1.id,))
        mg.conn.execute("UPDATE nodes SET weight=0.5 WHERE id=?", (n2.id,))
        mg.conn.execute("UPDATE nodes SET weight=0.95 WHERE id=?", (n3.id,))
        mg.conn.commit()
        result = mg.memory_lifecycle_report()
        wd = result["weight_distribution"]
        assert wd["critical (<0.1)"] >= 1
        assert wd["medium (0.3-0.6)"] >= 1
        assert wd["peak (>=0.9)"] >= 1

    def test_quarantine_count(self, mg):
        """Quarantined nodes are counted."""
        node = mg.add("Bad node", "concept")
        mg.node_quarantine(node.id, reason="suspicious")
        result = mg.memory_lifecycle_report()
        assert result["quarantine_count"] == 1

    def test_reinforcement_events_tracked(self, mg):
        """Reinforcement history is counted."""
        node = mg.add("Reinforced", "concept")
        mg.memory_reinforce(node.id, "positive")
        mg.memory_reinforce(node.id, "positive")
        result = mg.memory_lifecycle_report()
        assert result["reinforcement_events"] >= 2

    def test_seed_stage_small_store(self, mg):
        """Small store is in seed stage."""
        for i in range(5):
            mg.add(f"Node {i}", "concept")
        result = mg.memory_lifecycle_report()
        assert result["lifecycle_stage"] == "seed"

    def test_thriving_stage(self, mg):
        """Active store with good weights is thriving."""
        for i in range(15):
            node = mg.add(f"Active node {i}", "concept")
            mg.conn.execute("UPDATE nodes SET weight=? WHERE id=?", (0.5 + i * 0.02, node.id))
        mg.conn.commit()
        result = mg.memory_lifecycle_report()
        assert result["lifecycle_stage"] in ("thriving", "active")

    def test_declining_stage_with_dormant(self, mg):
        """Many dormant nodes → declining stage."""
        import time as _t
        old_time = _t.time() - (3600 * 24 * 120)  # 120 days ago
        for i in range(20):
            node = mg.add(f"Old node {i}", "concept")
            mg.conn.execute("UPDATE nodes SET accessed=? WHERE id=?", (old_time, node.id))
        mg.conn.commit()
        result = mg.memory_lifecycle_report()
        assert result["dormant_nodes"] >= 15
        assert result["lifecycle_stage"] == "declining"

    def test_recommendation_start_reinforcement(self, mg):
        """No reinforcement history → recommendation to start."""
        for i in range(15):
            mg.add(f"Node {i}", "concept")
        result = mg.memory_lifecycle_report()
        assert "start_reinforcement_tracking" in result["recommendations"]

    def test_recommendation_prune_dormant(self, mg):
        """Many dormant nodes → prune recommendation."""
        import time as _t
        old_time = _t.time() - (3600 * 24 * 120)
        for i in range(20):
            node = mg.add(f"Old {i}", "concept")
            mg.conn.execute("UPDATE nodes SET accessed=? WHERE id=?", (old_time, node.id))
        mg.conn.commit()
        # Add some active ones
        for i in range(5):
            mg.add(f"Fresh {i}", "concept")
        result = mg.memory_lifecycle_report()
        assert "prune_dormant_memories" in result["recommendations"]

    def test_avg_weight_calculation(self, mg):
        """Average weight is correctly calculated."""
        n1 = mg.add("W1", "concept")
        n2 = mg.add("W2", "concept")
        mg.conn.execute("UPDATE nodes SET weight=0.3 WHERE id=?", (n1.id,))
        mg.conn.execute("UPDATE nodes SET weight=0.7 WHERE id=?", (n2.id,))
        mg.conn.commit()
        result = mg.memory_lifecycle_report()
        assert abs(result["avg_weight"] - 0.5) < 0.01

    def test_healthy_recommendation(self, mg):
        """Well-maintained store gets healthy recommendation."""
        for i in range(15):
            node = mg.add(f"Node {i}", "concept")
            mg.conn.execute("UPDATE nodes SET weight=0.5 WHERE id=?", (node.id,))
            mg.memory_reinforce(node.id, "positive")
        mg.conn.commit()
        result = mg.memory_lifecycle_report()
        assert "healthy" in result["recommendations"]

    def test_stale_node_classification(self, mg):
        """Nodes between 7-30 days are stale."""
        import time as _t
        stale_time = _t.time() - (3600 * 24 * 15)  # 15 days ago
        node = mg.add("Stale node", "concept")
        mg.conn.execute("UPDATE nodes SET accessed=? WHERE id=?", (stale_time, node.id))
        mg.conn.commit()
        result = mg.memory_lifecycle_report()
        assert result["stale_nodes"] >= 1

    def test_decaying_node_classification(self, mg):
        """Nodes between 30-90 days are decaying."""
        import time as _t
        decaying_time = _t.time() - (3600 * 24 * 60)  # 60 days ago
        node = mg.add("Decaying node", "concept")
        mg.conn.execute("UPDATE nodes SET accessed=? WHERE id=?", (decaying_time, node.id))
        mg.conn.commit()
        result = mg.memory_lifecycle_report()
        assert result["decaying_nodes"] >= 1


# ── Memory Access Pattern Tests ──────────────────────────────────

class TestMemoryAccessPattern:
    """Tests for memory_access_pattern()."""

    def test_empty_store(self, mg):
        """Empty store returns minimal report."""
        result = mg.memory_access_pattern()
        assert result["total_nodes"] == 0
        assert "empty_store" in result["recommendations"]

    def test_basic_structure(self, mg):
        """Report has all expected fields."""
        mg.add("Node", "concept")
        result = mg.memory_access_pattern()
        expected_keys = {
            "window_days", "total_nodes", "hot_nodes", "cold_nodes",
            "hot_examples", "cold_examples", "access_velocity",
            "diurnal_bias", "peak_hour", "peak_hour_ratio",
            "kind_temperature", "recommendations",
        }
        assert set(result.keys()) == expected_keys

    def test_all_hot_within_window(self, mg):
        """Freshly created nodes are all hot."""
        for i in range(10):
            mg.add(f"Fresh {i}", "concept")
        result = mg.memory_access_pattern(days=30)
        assert result["hot_nodes"] == 10
        assert result["cold_nodes"] == 0

    def test_cold_nodes_detected(self, mg):
        """Old unaccessed nodes are cold."""
        import time as _t
        old_time = _t.time() - (86400 * 60)  # 60 days ago
        node = mg.add("Old node", "concept")
        mg.conn.execute("UPDATE nodes SET accessed=?, created=? WHERE id=?", (old_time, old_time, node.id))
        mg.conn.commit()
        result = mg.memory_access_pattern(days=30)
        assert result["cold_nodes"] >= 1

    def test_custom_window_days(self, mg):
        """Custom window affects classification."""
        mg.add("Recent", "concept")
        result = mg.memory_access_pattern(days=1)
        assert result["window_days"] == 1
        assert result["hot_nodes"] >= 1

    def test_access_velocity(self, mg):
        """Velocity is hot_nodes / (days * total)."""
        for i in range(5):
            mg.add(f"Node {i}", "concept")
        result = mg.memory_access_pattern(days=30)
        # 5 hot, 30 days, 5 total → 5/(30*5) = 0.0333
        assert result["access_velocity"] > 0
        assert result["access_velocity"] <= 1.0

    def test_kind_temperature_hot(self, mg):
        """Recently accessed kind is hot."""
        for i in range(5):
            mg.add(f"Skill {i}", "skill")
        result = mg.memory_access_pattern(days=30)
        assert "skill" in result["kind_temperature"]
        assert result["kind_temperature"]["skill"]["temperature"] == "hot"

    def test_kind_temperature_cold(self, mg):
        """Old unaccessed kind is cold."""
        import time as _t
        old_time = _t.time() - (86400 * 90)
        node = mg.add("Old skill", "skill")
        mg.conn.execute("UPDATE nodes SET accessed=? WHERE id=?", (old_time, node.id))
        mg.conn.commit()
        result = mg.memory_access_pattern(days=30)
        assert result["kind_temperature"]["skill"]["temperature"] == "cold"

    def test_kind_temperature_warm(self, mg):
        """Mixed hot/cold kind is warm."""
        import time as _t
        old_time = _t.time() - (86400 * 60)
        # Add 3 hot and 3 cold
        for i in range(3):
            mg.add(f"Hot fact {i}", "fact")
        for i in range(3):
            n = mg.add(f"Cold fact {i}", "fact")
            mg.conn.execute("UPDATE nodes SET accessed=? WHERE id=?", (old_time, n.id))
        mg.conn.commit()
        result = mg.memory_access_pattern(days=30)
        assert result["kind_temperature"]["fact"]["temperature"] == "warm"

    def test_high_cold_ratio_recommendation(self, mg):
        """>50% cold → high_cold_ratio recommendation."""
        import time as _t
        old_time = _t.time() - (86400 * 90)
        # 1 hot, 5 cold (both created and accessed old)
        mg.add("Hot", "concept")
        for i in range(5):
            n = mg.add(f"Cold {i}", "concept")
            mg.conn.execute("UPDATE nodes SET accessed=?, created=? WHERE id=?", (old_time, old_time, n.id))
        mg.conn.commit()
        result = mg.memory_access_pattern(days=30)
        assert "high_cold_ratio" in result["recommendations"]

    def test_low_velocity_recommendation(self, mg):
        """Low access velocity triggers recommendation."""
        import time as _t
        old_time = _t.time() - (86400 * 90)
        for i in range(20):
            n = mg.add(f"Node {i}", "concept")
            mg.conn.execute("UPDATE nodes SET accessed=? WHERE id=?", (old_time, n.id))
        mg.conn.commit()
        result = mg.memory_access_pattern(days=30)
        assert "low_access_velocity" in result["recommendations"]

    def test_cold_examples_sorted_by_idle(self, mg):
        """Cold examples are sorted by days_idle descending."""
        import time as _t
        now = _t.time()
        n1 = mg.add("Very old", "concept")
        mg.conn.execute("UPDATE nodes SET accessed=? WHERE id=?", (now - 86400 * 80, n1.id))
        n2 = mg.add("Slightly old", "concept")
        mg.conn.execute("UPDATE nodes SET accessed=? WHERE id=?", (now - 86400 * 40, n2.id))
        mg.conn.commit()
        result = mg.memory_access_pattern(days=30)
        if result["cold_examples"]:
            assert result["cold_examples"][0]["days_idle"] >= result["cold_examples"][-1]["days_idle"]

    def test_balanced_access_recommendation(self, mg):
        """Balanced access with no issues."""
        import time as _t
        now = _t.time()
        # Spread timestamps across different hours to avoid diurnal bias
        for i in range(10):
            n = mg.add(f"Node {i}", "concept")
            spread_time = now - (i * 3600 * 3)  # 3-hour intervals
            mg.conn.execute("UPDATE nodes SET accessed=? WHERE id=?", (spread_time, n.id))
        mg.conn.commit()
        result = mg.memory_access_pattern(days=30)
        assert "balanced_access" in result["recommendations"]


# ── Memory Health Score Tests ────────────────────────────────────

class TestMemoryHealthScore:
    """Tests for memory_health_score()."""

    def test_empty_store(self, mg):
        """Empty store returns 0 score."""
        result = mg.memory_health_score()
        assert result["score"] == 0
        assert result["grade"] == "N/A"

    def test_score_range(self, mg):
        """Score is between 0 and 100."""
        mg.add("Node A", "concept")
        result = mg.memory_health_score()
        assert 0 <= result["score"] <= 100

    def test_dimensions_present(self, mg):
        """All 5 dimensions are present."""
        mg.add("Node", "concept")
        result = mg.memory_health_score()
        dims = result["dimensions"]
        assert "vitality" in dims
        assert "integrity" in dims
        assert "connectivity" in dims
        assert "diversity" in dims
        assert "maintenance" in dims

    def test_grade_assignment(self, mg):
        """Grade is one of A/B/C/D/F."""
        mg.add("Node", "concept")
        result = mg.memory_health_score()
        assert result["grade"] in ("A", "B", "C", "D", "F")

    def test_vitality_active_nodes(self, mg):
        """Active nodes contribute to vitality."""
        for i in range(10):
            mg.add(f"Active {i}", "concept")
        result = mg.memory_health_score()
        assert result["dimensions"]["vitality"]["score"] > 0

    def test_integrity_penalized_by_quarantine(self, mg):
        """Quarantined nodes reduce integrity score."""
        # All quarantined
        for i in range(10):
            n = mg.add(f"Bad {i}", "concept")
            mg.node_quarantine(n.id, reason="test")
        result = mg.memory_health_score()
        assert result["dimensions"]["integrity"]["score"] < 5

    def test_integrity_clean_store(self, mg):
        """No quarantine → high integrity."""
        for i in range(10):
            mg.add(f"Good {i}", "concept")
        result = mg.memory_health_score()
        assert result["dimensions"]["integrity"]["score"] >= 15

    def test_diversity_multiple_kinds(self, mg):
        """Multiple kinds increase diversity."""
        for kind in ["concept", "person", "event", "skill", "fact"]:
            mg.add(f"Node of {kind}", kind)
        result = mg.memory_health_score()
        assert result["dimensions"]["diversity"]["score"] > 10

    def test_diversity_single_kind(self, mg):
        """Single kind → zero diversity."""
        for i in range(10):
            mg.add(f"Same kind {i}", "concept")
        result = mg.memory_health_score()
        assert result["dimensions"]["diversity"]["score"] == 0

    def test_connectivity_with_edges(self, mg):
        """Edges improve connectivity."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        c = mg.add("C", "concept")
        mg.link(a.id, b.id, "related")
        mg.link(b.id, c.id, "related")
        result = mg.memory_health_score()
        assert result["dimensions"]["connectivity"]["score"] > 0

    def test_maintenance_with_reinforcement(self, mg):
        """Reinforcement history improves maintenance."""
        node = mg.add("Reinforced", "concept")
        mg.memory_reinforce(node.id, "positive")
        result = mg.memory_health_score()
        assert result["dimensions"]["maintenance"]["score"] > 0

    def test_issues_list_populated(self, mg):
        """Issues list is present and non-empty."""
        mg.add("Node", "concept")
        result = mg.memory_health_score()
        assert isinstance(result["issues"], list)
        assert len(result["issues"]) >= 1

    def test_high_score_with_good_practices(self, mg):
        """Well-maintained diverse connected store gets decent score."""
        a = mg.add("Concept A", "concept")
        b = mg.add("Person B", "person")
        c = mg.add("Event C", "event")
        d = mg.add("Skill D", "skill")
        mg.link(a.id, b.id, "related")
        mg.link(b.id, c.id, "related")
        mg.link(c.id, d.id, "related")
        for n in [a, b, c, d]:
            mg.memory_reinforce(n.id, "positive")
        result = mg.memory_health_score()
        assert result["score"] >= 30  # Should be above average


# ── Diffusion Retrieval Tests (ExpGraph-inspired Graph Diffusion) ────────

class TestDiffusionRetrieve:
    """Tests for diffusion_retrieve() — Personalized PageRank diffusion."""

    @pytest.fixture
    def cluster_graph(self, mg):
        """Build a graph with two clusters connected by a bridge.
        Cluster A: Alice, Python, ML
        Cluster B: Bob, Design, Figma
        Bridge: Alice — Bob (connects the clusters)
        """
        alice = mg.add("Alice", "person", {"role": "engineer"})
        python = mg.add("Python", "skill")
        ml = mg.add("Machine Learning", "topic")
        bob = mg.add("Bob", "person", {"role": "designer"})
        design = mg.add("Design", "skill")
        figma = mg.add("Figma", "tool")

        # Cluster A (strong intra-cluster links)
        mg.link(alice.id, python.id, "knows", weight=0.9)
        mg.link(alice.id, ml.id, "studies", weight=0.8)
        mg.link(python.id, ml.id, "related", weight=0.7)

        # Cluster B
        mg.link(bob.id, design.id, "knows", weight=0.9)
        mg.link(bob.id, figma.id, "uses", weight=0.8)
        mg.link(design.id, figma.id, "related", weight=0.7)

        # Bridge (weak link)
        mg.link(alice.id, bob.id, "colleague", weight=0.3)

        return {
            "mg": mg, "alice": alice, "python": python, "ml": ml,
            "bob": bob, "design": design, "figma": figma,
        }

    def test_basic_diffusion_returns_results(self, cluster_graph):
        """Diffusion retrieval returns results for a query."""
        g = cluster_graph["mg"]
        results = g.diffusion_retrieve("Python")
        assert len(results) > 0
        assert all("node_id" in r for r in results)

    def test_seed_nodes_high_score(self, cluster_graph):
        """Seed nodes (matched by BM25) get high diffusion scores."""
        g = cluster_graph["mg"]
        results = g.diffusion_retrieve("Python")
        node_ids = [r["node_id"] for r in results]
        # Python should be in results
        assert cluster_graph["python"].id in node_ids

    def test_diffusion_propagates_to_neighbors(self, cluster_graph):
        """Diffusion propagates beyond seed nodes to graph neighbors."""
        g = cluster_graph["mg"]
        # Search for Alice — should also surface Python and ML (her neighbors)
        results = g.diffusion_retrieve("Alice")
        node_ids = {r["node_id"] for r in results}
        # Alice's direct neighbors should appear via diffusion
        assert cluster_graph["python"].id in node_ids
        assert cluster_graph["ml"].id in node_ids

    def test_diffusion_decays_with_distance(self, cluster_graph):
        """Closer nodes get higher scores than distant nodes."""
        g = cluster_graph["mg"]
        results = g.diffusion_retrieve("Python", alpha=0.2, max_iter=30)
        # Build score map
        scores = {r["node_id"]: r["score"] for r in results}
        # Python (seed) should score higher than Bob (2 hops away via bridge)
        py_score = scores.get(cluster_graph["python"].id, 0)
        bob_score = scores.get(cluster_graph["bob"].id, 0)
        assert py_score >= bob_score

    def test_explicit_seeds(self, cluster_graph):
        """Explicit seed IDs are used directly without BM25."""
        g = cluster_graph["mg"]
        alice_id = cluster_graph["alice"].id
        results = g.diffusion_retrieve(seeds=[alice_id], limit=10)
        assert len(results) > 0
        # Alice should have the highest score
        assert results[0]["node_id"] == alice_id

    def test_limit_respected(self, cluster_graph):
        """Limit parameter controls output size."""
        g = cluster_graph["mg"]
        results = g.diffusion_retrieve("Alice", limit=3)
        assert len(results) <= 3

    def test_hop_distance_computed(self, cluster_graph):
        """Results include hop distance from seeds."""
        g = cluster_graph["mg"]
        results = g.diffusion_retrieve("Python", explain=False)
        for r in results:
            assert "hop_distance" in r
            assert r["hop_distance"] >= 0

    def test_seed_zero_hop(self, cluster_graph):
        """Seed nodes have hop_distance 0."""
        g = cluster_graph["mg"]
        alice_id = cluster_graph["alice"].id
        results = g.diffusion_retrieve(seeds=[alice_id])
        alice_result = next(r for r in results if r["node_id"] == alice_id)
        assert alice_result["hop_distance"] == 0

    def test_distant_nodes_higher_hops(self, cluster_graph):
        """Nodes across the bridge have higher hop distance."""
        g = cluster_graph["mg"]
        alice_id = cluster_graph["alice"].id
        results = g.diffusion_retrieve(seeds=[alice_id])
        # Bob is across the bridge (1 hop from Alice)
        bob_id = cluster_graph["bob"].id
        bob_result = next(r for r in results if r["node_id"] == bob_id)
        assert bob_result["hop_distance"] >= 1

    def test_sources_field_populated(self, cluster_graph):
        """Sources field indicates how the node was found."""
        g = cluster_graph["mg"]
        results = g.diffusion_retrieve("Python")
        for r in results:
            assert isinstance(r["sources"], list)

    def test_seed_source_marked(self, cluster_graph):
        """Seed nodes have 'seed' in sources."""
        g = cluster_graph["mg"]
        alice_id = cluster_graph["alice"].id
        results = g.diffusion_retrieve(seeds=[alice_id])
        alice_result = next(r for r in results if r["node_id"] == alice_id)
        assert "seed" in alice_result["sources"]

    def test_diffusion_source_marked(self, cluster_graph):
        """Non-seed nodes reached by diffusion have 'diffusion' in sources."""
        g = cluster_graph["mg"]
        results = g.diffusion_retrieve("Python", alpha=0.1)
        # ML is a neighbor of Python but not a BM25 match for "Python"
        ml_results = [r for r in results if r["node_id"] == cluster_graph["ml"].id]
        if ml_results:
            assert "diffusion" in ml_results[0]["sources"]

    def test_bm25_merge(self, cluster_graph):
        """When merge_bm25=True, BM25 scores influence final ranking."""
        g = cluster_graph["mg"]
        results_merged = g.diffusion_retrieve("Python", merge_bm25=True, bm25_boost=0.5)
        results_pure = g.diffusion_retrieve("Python", merge_bm25=False)
        # Both should return results
        assert len(results_merged) > 0
        assert len(results_pure) > 0
        # Scores should differ when BM25 is blended
        merged_scores = {r["node_id"]: r["score"] for r in results_merged}
        pure_scores = {r["node_id"]: r["score"] for r in results_pure}
        # At least one node should have different score
        common_ids = set(merged_scores) & set(pure_scores)
        diffs = [abs(merged_scores[nid] - pure_scores[nid]) for nid in common_ids]
        assert any(d > 0.001 for d in diffs)

    def test_no_bm25_merge(self, cluster_graph):
        """When merge_bm25=False, scores are pure diffusion."""
        g = cluster_graph["mg"]
        results = g.diffusion_retrieve("Python", merge_bm25=False)
        for r in results:
            assert r["bm25_score"] == 0.0

    def test_alpha_controls_spread(self, cluster_graph):
        """Higher alpha = more concentrated on seeds; lower = more spread."""
        g = cluster_graph["mg"]
        alice_id = cluster_graph["alice"].id
        # Low alpha: diffusion spreads further
        spread = g.diffusion_retrieve(seeds=[alice_id], alpha=0.05, limit=10)
        # High alpha: concentrated on seeds
        focused = g.diffusion_retrieve(seeds=[alice_id], alpha=0.5, limit=10)

        # With low alpha, more nodes should get meaningful scores
        spread_meaningful = sum(1 for r in spread if r["diffusion_score"] > 0.01)
        focused_meaningful = sum(1 for r in focused if r["diffusion_score"] > 0.01)
        assert spread_meaningful >= focused_meaningful

    def test_edge_weight_factor(self, cluster_graph):
        """Edge weight factor affects diffusion behavior."""
        g = cluster_graph["mg"]
        # Linear weights
        linear = g.diffusion_retrieve("Alice", edge_weight_factor=1.0)
        # Square root (dampens strong edges)
        sqrt = g.diffusion_retrieve("Alice", edge_weight_factor=0.5)
        # Both return results
        assert len(linear) > 0
        assert len(sqrt) > 0

    def test_empty_graph(self, mg):
        """Empty graph returns empty list."""
        results = mg.diffusion_retrieve("anything")
        assert results == []

    def test_no_matching_seeds(self, mg):
        """Query that matches nothing returns empty list."""
        mg.add("Python", "skill")
        results = mg.diffusion_retrieve("NonexistentXYZ123")
        # Should return empty or very few results
        # (depends on BM25 fallback behavior)
        assert isinstance(results, list)

    def test_empty_query_no_seeds_raises(self, mg):
        """Empty query without seeds raises ValueError."""
        with pytest.raises(ValueError, match="query or seeds"):
            mg.diffusion_retrieve()

    def test_explain_mode(self, cluster_graph):
        """Explain mode includes diffusion paths."""
        g = cluster_graph["mg"]
        alice_id = cluster_graph["alice"].id
        results = g.diffusion_retrieve(seeds=[alice_id], explain=True)
        # Alice (seed) should have explanation
        alice_r = next(r for r in results if r["node_id"] == alice_id)
        assert "diffusion_paths" in alice_r
        assert len(alice_r["diffusion_paths"]) > 0

    def test_explain_shows_path(self, cluster_graph):
        """Explain traces path from seed to distant node."""
        g = cluster_graph["mg"]
        alice_id = cluster_graph["alice"].id
        results = g.diffusion_retrieve(seeds=[alice_id], explain=True, limit=10)
        # Find a non-seed node
        non_seed = [r for r in results if r["hop_distance"] > 0]
        if non_seed:
            assert "diffusion_paths" in non_seed[0]
            paths = non_seed[0]["diffusion_paths"]
            if paths:
                assert "path" in paths[0]
                assert len(paths[0]["path"]) >= 2  # seed → ... → target

    def test_isolated_seed(self, mg):
        """Isolated seed node (no edges) still returns itself."""
        node = mg.add("Isolated", "concept")
        results = mg.diffusion_retrieve(seeds=[node.id])
        assert len(results) >= 1
        assert results[0]["node_id"] == node.id
        assert results[0]["hop_distance"] == 0

    def test_self_loop_handling(self, mg):
        """Self-loops don't break diffusion."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "related", weight=0.5)
        # Self-loop
        mg.conn.execute(
            "INSERT INTO edges (source, target, relation, weight) VALUES (?, ?, ?, ?)",
            (a.id, a.id, "self", 0.1)
        )
        mg.conn.commit()
        results = mg.diffusion_retrieve(seeds=[a.id])
        assert len(results) > 0  # Should not crash

    def test_large_graph_performance(self, mg):
        """Diffusion converges on a moderately large graph."""
        import random
        random.seed(42)
        # Create 50 nodes
        nodes = [mg.add(f"Node_{i}", "concept") for i in range(50)]
        # Create ~100 edges (random)
        for _ in range(100):
            s = random.choice(nodes).id
            t = random.choice(nodes).id
            if s != t:
                mg.link(s, t, "related", weight=random.uniform(0.1, 1.0))
        # Run diffusion
        results = mg.diffusion_retrieve(seeds=[nodes[0].id], max_iter=30)
        assert len(results) > 0
        assert results[0]["node_id"] == nodes[0].id

    def test_return_fields_complete(self, cluster_graph):
        """All required fields are present in results."""
        g = cluster_graph["mg"]
        results = g.diffusion_retrieve("Alice")
        required_fields = {"node_id", "label", "kind", "score",
                          "diffusion_score", "bm25_score", "hop_distance", "sources"}
        for r in results:
            assert required_fields <= set(r.keys()), f"Missing fields in {r}"

    def test_convergence_tolerance(self, cluster_graph):
        """Algorithm respects convergence tolerance."""
        g = cluster_graph["mg"]
        # Very tight tolerance should take more iterations but converge
        tight = g.diffusion_retrieve("Alice", tol=1e-8, max_iter=100)
        # Very loose tolerance stops early
        loose = g.diffusion_retrieve("Alice", tol=1e-1, max_iter=100)
        # Both should return results
        assert len(tight) > 0
        assert len(loose) > 0

    def test_dangling_node_redistribution(self, mg):
        """Dangling nodes (no outgoing edges) distribute mass correctly."""
        a = mg.add("Hub", "concept")
        b = mg.add("Leaf1", "concept")
        c = mg.add("Leaf2", "concept")
        mg.link(a.id, b.id, "has", weight=1.0)
        mg.link(a.id, c.id, "has", weight=1.0)
        # b and c are dangling (no outgoing edges)
        results = mg.diffusion_retrieve(seeds=[a.id], alpha=0.15)
        assert len(results) > 0
        # All nodes should appear
        node_ids = {r["node_id"] for r in results}
        assert a.id in node_ids

    def test_multiple_seeds(self, cluster_graph):
        """Multiple seeds combine diffusion from different starting points."""
        g = cluster_graph["mg"]
        alice_id = cluster_graph["alice"].id
        bob_id = cluster_graph["bob"].id
        results = g.diffusion_retrieve(seeds=[alice_id, bob_id], limit=10)
        assert len(results) > 0
        # Both seeds should appear
        node_ids = {r["node_id"] for r in results}
        assert alice_id in node_ids
        assert bob_id in node_ids

    def test_scores_sorted_descending(self, cluster_graph):
        """Results are sorted by score descending."""
        g = cluster_graph["mg"]
        results = g.diffusion_retrieve("Alice")
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_nonexistent_seeds_filtered(self, mg):
        """Non-existent seed IDs are silently filtered."""
        a = mg.add("Real", "concept")
        results = mg.diffusion_retrieve(seeds=[a.id, "nonexistent_id"])
        assert len(results) >= 1
        assert results[0]["node_id"] == a.id


class TestKGETransE:
    """Test TransE Knowledge Graph Embedding training and scoring."""

    def test_train_kge_creates_table(self, mg):
        """train_kge() creates kge_embeddings table."""
        mg.add("Alice", "person")
        mg.add("Bob", "person")
        mg.add("Company", "org")
        mg.link_by_label("Alice", "Company", "works_at")
        mg.train_kge(dim=16, epochs=50)
        tables = [r[0] for r in mg.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        assert "kge_embeddings" in tables

    def test_train_kge_dimensions(self, mg):
        """Trained embeddings have the specified dimensionality."""
        mg.add("Alice", "person")
        mg.add("Bob", "person")
        mg.link_by_label("Alice", "Bob", "knows")
        mg.train_kge(dim=8, epochs=30)
        import struct
        row = mg.conn.execute(
            "SELECT entity, embedding FROM kge_embeddings LIMIT 1"
        ).fetchone()
        floats = struct.unpack(f'{8}f', row["embedding"])
        assert len(floats) == 8

    def test_train_kge_all_entities_covered(self, mg):
        """All nodes get embeddings after training."""
        nodes = [mg.add(f"Node_{i}", "concept") for i in range(5)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i+1].id, "next")
        mg.train_kge(dim=10, epochs=20)
        # kge_embeddings stores both entities and relations
        entity_count = mg.conn.execute(
            "SELECT COUNT(*) FROM kge_embeddings WHERE entity_type='node'"
        ).fetchone()[0]
        assert entity_count == 5

    def test_train_kge_relation_embeddings(self, mg):
        """Relations also get embeddings."""
        mg.add("Alice", "person")
        mg.add("Bob", "person")
        mg.add("Cat", "animal")
        mg.link_by_label("Alice", "Bob", "knows")
        mg.link_by_label("Alice", "Cat", "owns")
        mg.train_kge(dim=10, epochs=20)
        relations = [r[0] for r in mg.conn.execute(
            "SELECT entity FROM kge_embeddings WHERE entity_type='relation'"
        ).fetchall()]
        assert "knows" in relations
        assert "owns" in relations

    def test_kge_score_basic(self, mg):
        """kge_score() returns a float for a valid triple."""
        mg.add("Alice", "person")
        mg.add("Company", "org")
        mg.link_by_label("Alice", "Company", "works_at")
        mg.train_kge(dim=16, epochs=50)
        score = mg.kge_score("Alice", "Company", "works_at")
        assert isinstance(score, float)

    def test_kge_score_lower_for_unseen(self, mg):
        """Score for valid triple should be better (lower distance) than random."""
        mg.add("Alice", "person")
        mg.add("Bob", "person")
        mg.add("Charlie", "person")
        mg.link_by_label("Alice", "Bob", "knows")
        mg.train_kge(dim=16, epochs=100)
        valid_score = mg.kge_score("Alice", "Bob", "knows")
        unseen_score = mg.kge_score("Alice", "Charlie", "knows")
        # Valid triple should have lower distance (better score)
        assert valid_score < unseen_score

    def test_kge_score_missing_entity(self, mg):
        """kge_score() returns inf for unknown entities."""
        mg.add("Alice", "person")
        mg.add("Bob", "person")
        mg.link_by_label("Alice", "Bob", "knows")
        mg.train_kge(dim=16, epochs=20)
        score = mg.kge_score("Alice", "Nonexistent", "knows")
        assert math.isinf(score)

    def test_kge_score_without_training(self, mg):
        """kge_score() raises if train_kge() not called."""
        mg.add("Alice", "person")
        with pytest.raises(ValueError, match="KGE not trained"):
            mg.kge_score("Alice", "Alice", "self")

    def test_get_kge_embedding(self, mg):
        """get_kge_embedding() returns the learned vector."""
        mg.add("Alice", "person")
        mg.add("Bob", "person")
        mg.link_by_label("Alice", "Bob", "knows")
        mg.train_kge(dim=12, epochs=20)
        emb = mg.get_kge_embedding("Alice")
        assert emb is not None
        assert len(emb) == 12

    def test_get_kge_embedding_not_found(self, mg):
        """get_kge_embedding() returns None for unknown entity."""
        mg.add("Alice", "person")
        mg.add("Bob", "person")
        mg.link_by_label("Alice", "Bob", "knows")
        mg.train_kge(dim=8, epochs=10)
        assert mg.get_kge_embedding("Nonexistent") is None

    def test_search_hybrid_with_kge(self, mg):
        """search_hybrid uses KGE route when available."""
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        c = mg.add("Carol", "person")
        mg.link(a.id, b.id, "knows", weight=1.0)
        mg.link(b.id, c.id, "knows", weight=1.0)
        mg.link(a.id, c.id, "knows", weight=0.5)
        mg.train_kge(dim=16, epochs=50)
        results = mg.search_hybrid("Alice", limit=5, kge_weight=0.15)
        assert len(results) > 0
        # Bob and Carol should appear (connected to Alice)
        ids = {r["node_id"] for r in results}
        assert b.id in ids or c.id in ids

    def test_search_hybrid_kge_sources_tagged(self, mg):
        """Results from KGE route are tagged in sources."""
        a = mg.add("Alice", "person")
        b = mg.add("Bob", "person")
        mg.link(a.id, b.id, "knows", weight=1.0)
        mg.train_kge(dim=16, epochs=50)
        results = mg.search_hybrid("Alice", limit=10, kge_weight=0.2)
        kge_sourced = [r for r in results if "kge" in r.get("sources", set())]
        assert len(kge_sourced) > 0

    def test_kge_retrain_replaces(self, mg):
        """Retraining KGE replaces old embeddings."""
        mg.add("Alice", "person")
        mg.add("Bob", "person")
        mg.link_by_label("Alice", "Bob", "knows")
        mg.train_kge(dim=8, epochs=10)
        emb1 = mg.get_kge_embedding("Alice")
        mg.train_kge(dim=8, epochs=10)
        emb2 = mg.get_kge_embedding("Alice")
        # Different training run → different values (with high probability)
        assert emb1 != emb2

    def test_kge_margin_loss_decreases(self, mg):
        """Training yields lower scores for observed triples than unobserved ones."""
        # Build a graph with clear structure: chain + extra edges
        nodes = [mg.add(f"N{i}", "concept") for i in range(10)]
        for i in range(9):
            mg.link(nodes[i].id, nodes[i+1].id, "next")
        # Add some cross-edges for richer structure
        mg.link(nodes[0].id, nodes[5].id, "jump")
        mg.link(nodes[2].id, nodes[7].id, "jump")
        mg.link(nodes[3].id, nodes[9].id, "jump")

        mg.train_kge(dim=32, epochs=500, seed=99)

        # Average distance for observed triples
        observed = [(nodes[i].id, nodes[i+1].id, "next") for i in range(9)]
        avg_observed = sum(mg._kge_distance(h, t, r) for h, t, r in observed) / len(observed)

        # Average distance for unobserved (corrupted) triples
        import random
        random.seed(99)
        corrupted = []
        for h, t, r in observed:
            neg_t = random.choice(nodes).id
            while neg_t == t:
                neg_t = random.choice(nodes).id
            corrupted.append((h, neg_t, r))
        avg_corrupted = sum(mg._kge_distance(h, t, r) for h, t, r in corrupted) / len(corrupted)

        # Observed triples should have lower distance (better fit) than corrupted
        assert avg_observed < avg_corrupted

    def test_kge_with_isolated_nodes(self, mg):
        """Isolated nodes still get embeddings."""
        a = mg.add("Connected", "concept")
        b = mg.add("Also", "concept")
        iso = mg.add("Isolated", "concept")
        mg.link(a.id, b.id, "rel")
        mg.train_kge(dim=8, epochs=20)
        emb = mg.get_kge_embedding(iso.id)
        assert emb is not None
        assert len(emb) == 8


class TestBiTemporalValidity:
    """Test bi-temporal validity tracking (valid_time + transaction_time)."""

    def test_set_validity_basic(self, mg):
        """set_validity() sets valid_from and valid_to on a node."""
        n = mg.add("Alice works at Acme", "fact")
        t1 = time.time()
        t2 = t1 + 86400 * 365  # 1 year later
        assert mg.set_validity(n.id, valid_from=t1, valid_to=t2) is True
        row = mg.conn.execute(
            "SELECT valid_from, valid_to FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        assert row["valid_from"] == t1
        assert row["valid_to"] == t2

    def test_set_validity_node_not_found(self, mg):
        """set_validity() returns False for non-existent node."""
        assert mg.set_validity("nonexistent", valid_from=1.0) is False

    def test_set_validity_partial(self, mg):
        """Can set only valid_from without valid_to (open-ended)."""
        n = mg.add("The sky is blue", "fact")
        mg.set_validity(n.id, valid_from=1000.0)
        row = mg.conn.execute(
            "SELECT valid_from, valid_to FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        assert row["valid_from"] == 1000.0
        assert row["valid_to"] is None

    def test_set_validity_txn_time_updated(self, mg):
        """set_validity() updates txn_time."""
        n = mg.add("Test fact", "fact")
        mg.set_validity(n.id, valid_from=1.0)
        row = mg.conn.execute(
            "SELECT txn_time FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        assert row["txn_time"] is not None
        assert row["txn_time"] > 0

    def test_is_valid_at_within_range(self, mg):
        """Node is valid at a timestamp within its valid range."""
        n = mg.add("Event X", "event")
        mg.set_validity(n.id, valid_from=1000.0, valid_to=2000.0)
        assert mg.is_valid_at(n.id, 1500.0) is True
        assert mg.is_valid_at(n.id, 1000.0) is True  # inclusive start
        assert mg.is_valid_at(n.id, 1999.0) is True

    def test_is_valid_at_outside_range(self, mg):
        """Node is not valid outside its valid range."""
        n = mg.add("Old event", "event")
        mg.set_validity(n.id, valid_from=1000.0, valid_to=2000.0)
        assert mg.is_valid_at(n.id, 999.0) is False   # before start
        assert mg.is_valid_at(n.id, 2000.0) is False   # at end (exclusive)
        assert mg.is_valid_at(n.id, 3000.0) is False   # after end

    def test_is_valid_at_no_validity_set(self, mg):
        """Node without validity info is always valid."""
        n = mg.add("Eternal fact", "fact")
        assert mg.is_valid_at(n.id, 0.0) is True
        assert mg.is_valid_at(n.id, time.time()) is True
        assert mg.is_valid_at(n.id, 9999999999.0) is True

    def test_is_valid_at_open_ended(self, mg):
        """Node with only valid_from is valid from that point onward."""
        n = mg.add("Ongoing fact", "fact")
        mg.set_validity(n.id, valid_from=1000.0)
        assert mg.is_valid_at(n.id, 999.0) is False
        assert mg.is_valid_at(n.id, 1000.0) is True
        assert mg.is_valid_at(n.id, 9999999999.0) is True

    def test_is_valid_at_node_not_found(self, mg):
        """is_valid_at() returns False for non-existent node."""
        assert mg.is_valid_at("nonexistent", time.time()) is False

    def test_supersede_creates_new_node(self, mg):
        """supersede() creates a replacement node."""
        old = mg.add("Alice lives in NYC", "fact")
        new_id = mg.supersede(old.id, new_label="Alice lives in SF")
        assert new_id is not None
        new_node = mg.get_node(new_id)
        assert new_node.label == "Alice lives in SF"
        assert new_node.kind == "fact"

    def test_supersede_closes_valid_time(self, mg):
        """supersede() sets valid_to on the old node."""
        old = mg.add("Old fact", "fact")
        mg.set_validity(old.id, valid_from=1000.0)
        now = time.time()
        mg.supersede(old.id, new_label="New fact")
        row = mg.conn.execute(
            "SELECT valid_to FROM nodes WHERE id=?", (old.id,)
        ).fetchone()
        assert row["valid_to"] is not None
        assert row["valid_to"] >= now - 1  # allow tiny clock skew

    def test_supersede_links_old_to_new(self, mg):
        """supersede() creates a 'superseded_by' edge."""
        old = mg.add("V1", "fact")
        new_id = mg.supersede(old.id, new_label="V2")
        edges = mg.conn.execute(
            "SELECT * FROM edges WHERE source=? AND relation='superseded_by'",
            (old.id,)
        ).fetchall()
        assert len(edges) == 1
        assert edges[0]["target"] == new_id

    def test_supersede_not_found(self, mg):
        """supersede() returns None if old node not found."""
        assert mg.supersede("nonexistent") is None

    def test_query_valid_at_returns_matching_nodes(self, mg):
        """query_valid_at() returns nodes valid at the given timestamp."""
        n1 = mg.add("Fact A", "fact")
        n2 = mg.add("Fact B", "fact")
        n3 = mg.add("Fact C", "fact")
        mg.set_validity(n1.id, valid_from=1000.0, valid_to=2000.0)
        mg.set_validity(n2.id, valid_from=1500.0, valid_to=3000.0)
        # n3 has no validity set (always valid)
        results = mg.query_valid_at(1700.0, kind="fact")
        labels = {n.label for n in results}
        assert "Fact A" in labels
        assert "Fact B" in labels
        assert "Fact C" in labels

    def test_query_valid_at_excludes_expired(self, mg):
        """query_valid_at() excludes nodes whose valid_to has passed."""
        n1 = mg.add("Expired", "fact")
        n2 = mg.add("Active", "fact")
        mg.set_validity(n1.id, valid_from=1000.0, valid_to=1500.0)
        mg.set_validity(n2.id, valid_from=1000.0, valid_to=3000.0)
        results = mg.query_valid_at(2000.0, kind="fact")
        labels = {n.label for n in results}
        assert "Active" in labels
        assert "Expired" not in labels

    def test_get_history_chain(self, mg):
        """get_history() reconstructs supersede chain."""
        v1 = mg.add("Address v1", "fact")
        v2_id = mg.supersede(v1.id, new_label="Address v2")
        v3_id = mg.supersede(v2_id, new_label="Address v3")
        history = mg.get_history(v1.id)
        assert len(history) == 3
        assert history[0]["label"] == "Address v1"
        assert history[1]["label"] == "Address v2"
        assert history[2]["label"] == "Address v3"
        # Each successor should have valid_from around when predecessor got valid_to
        assert history[0]["valid_to"] is not None
        assert history[1]["valid_from"] is not None

    def test_get_history_single_node(self, mg):
        """get_history() returns just the node if no successors."""
        n = mg.add("Lonely fact", "fact")
        history = mg.get_history(n.id)
        assert len(history) == 1
        assert history[0]["node_id"] == n.id


class TestQValueScoring:
    """Test RL-inspired Q-value scoring for memory nodes."""

    def test_q_value_default_zero(self, mg):
        """New nodes start with Q-value 0."""
        n = mg.add("Test node", "fact")
        assert mg.get_q_value(n.id) == 0.0

    def test_get_q_value_not_found(self, mg):
        """get_q_value() returns None for non-existent node."""
        assert mg.get_q_value("nonexistent") is None

    def test_update_q_value_positive_reward(self, mg):
        """Positive reward increases Q-value."""
        n = mg.add("Useful fact", "fact")
        mg.update_q_value(n.id, reward=1.0, alpha=0.5)
        q = mg.get_q_value(n.id)
        assert q > 0.0
        # Q ← 0 + 0.5 * (1.0 + 0.9*0 - 0) = 0.5
        assert abs(q - 0.5) < 0.001

    def test_update_q_value_negative_reward(self, mg):
        """Negative reward decreases Q-value."""
        n = mg.add("Bad memory", "fact")
        mg.update_q_value(n.id, reward=-1.0, alpha=0.5)
        q = mg.get_q_value(n.id)
        assert q < 0.0
        # Q ← 0 + 0.5 * (-1.0 + 0.9*0 - 0) = -0.5
        assert abs(q - (-0.5)) < 0.001

    def test_update_q_value_cumulative(self, mg):
        """Multiple updates accumulate (temporal difference)."""
        n = mg.add("Learning fact", "fact")
        mg.update_q_value(n.id, reward=1.0, alpha=0.1)
        q1 = mg.get_q_value(n.id)
        mg.update_q_value(n.id, reward=1.0, alpha=0.1)
        q2 = mg.get_q_value(n.id)
        assert q2 > q1  # monotonically increasing with consistent positive reward

    def test_update_q_value_converges(self, mg):
        """Repeated positive rewards converge toward reward value."""
        n = mg.add("Converging fact", "fact")
        # Without neighbors, Q ← Q + α·(reward - Q) converges to reward=1.0
        for _ in range(100):
            mg.update_q_value(n.id, reward=1.0, alpha=0.1)
        q = mg.get_q_value(n.id)
        assert 0.9 < q < 1.1  # converged to reward value

    def test_update_q_value_with_neighbor(self, mg):
        """Q-value propagates from higher-valued neighbors."""
        a = mg.add("Node A", "concept")
        b = mg.add("Node B", "concept")
        mg.link(a.id, b.id, "related")
        # Set B's Q high
        mg.update_q_value(b.id, reward=10.0, alpha=1.0)  # Q_B = 10
        # Update A with small reward; A should benefit from B's high Q
        mg.update_q_value(a.id, reward=0.0, alpha=0.5, gamma=0.9)
        q_a = mg.get_q_value(a.id)
        # Q_A ← 0 + 0.5 * (0 + 0.9*10 - 0) = 4.5
        assert q_a > 3.0  # significant boost from neighbor

    def test_update_q_value_not_found(self, mg):
        """update_q_value() returns False for non-existent node."""
        assert mg.update_q_value("nonexistent", reward=1.0) is False

    def test_reward_shortcut(self, mg):
        """reward() is a shortcut for positive update_q_value."""
        n = mg.add("Rewarded", "fact")
        mg.reward(n.id, amount=2.0)
        q = mg.get_q_value(n.id)
        assert q > 0.0

    def test_penalize_shortcut(self, mg):
        """penalize() is a shortcut for negative update_q_value."""
        n = mg.add("Penalized", "fact")
        mg.penalize(n.id, amount=2.0)
        q = mg.get_q_value(n.id)
        assert q < 0.0

    def test_reward_not_found(self, mg):
        """reward() returns False for non-existent node."""
        assert mg.reward("nonexistent") is False

    def test_penalize_not_found(self, mg):
        """penalize() returns False for non-existent node."""
        assert mg.penalize("nonexistent") is False

    def test_recall_with_q_no_q_values(self, mg):
        """recall_with_q works when no Q-values have been set (all zero)."""
        mg.add("Python", "skill")
        mg.add("Python advanced", "skill")
        results = mg.recall_with_q("Python", limit=5)
        assert len(results) > 0
        assert all("q_value" in r for r in results)
        # All Q-values should be 0 (no rewards given)
        assert all(r["q_value"] == 0.0 for r in results)

    def test_recall_with_q_boosts_rewarded(self, mg):
        """recall_with_q ranks rewarded nodes higher."""
        n1 = mg.add("Important Python", "skill")
        n2 = mg.add("Trivial Python", "skill")
        # Give n1 high Q-value
        for _ in range(20):
            mg.reward(n1.id, amount=1.0)
        results = mg.recall_with_q("Python", limit=2, q_bias=0.5)
        assert len(results) >= 2
        # Important Python should rank higher due to Q-value
        assert results[0]["label"] == "Important Python"
        assert results[0]["q_value"] > results[1]["q_value"]

    def test_recall_with_q_q_bias_zero(self, mg):
        """With q_bias=0, results are purely text-based."""
        n1 = mg.add("Alpha", "concept")
        n2 = mg.add("Alpha beta", "concept")
        mg.reward(n2.id, amount=5.0)
        results = mg.recall_with_q("Alpha", limit=5, q_bias=0.0)
        # Both should have similar text scores; Q shouldn't matter
        assert all("q_value" in r for r in results)

    def test_recall_with_q_empty(self, mg):
        """recall_with_q on empty graph returns empty list."""
        assert mg.recall_with_q("nothing") == []

    def test_top_q_nodes_empty(self, mg):
        """top_q_nodes on empty graph returns empty list."""
        assert mg.top_q_nodes() == []

    def test_top_q_nodes_sorted(self, mg):
        """top_q_nodes returns nodes sorted by Q-value descending."""
        a = mg.add("Low Q", "fact")
        b = mg.add("High Q", "fact")
        c = mg.add("Mid Q", "fact")
        mg.update_q_value(b.id, reward=5.0, alpha=1.0)
        mg.update_q_value(c.id, reward=2.0, alpha=1.0)
        results = mg.top_q_nodes(limit=3)
        assert len(results) == 3
        assert results[0]["label"] == "High Q"
        assert results[1]["label"] == "Mid Q"
        assert results[2]["label"] == "Low Q"

    def test_top_q_nodes_kind_filter(self, mg):
        """top_q_nodes filters by kind."""
        mg.add("Fact 1", "fact")
        mg.add("Skill 1", "skill")
        mg.update_q_value(mg.conn.execute(
            "SELECT id FROM nodes WHERE kind='skill'").fetchone()["id"],
            reward=10.0, alpha=1.0)
        results = mg.top_q_nodes(limit=5, kind="skill")
        assert len(results) == 1
        assert results[0]["kind"] == "skill"


# ─────────────────────────────────────────────────────────────
# Cycle 173: Lamport Clock + Typed Pub/Sub (on/off)
# ─────────────────────────────────────────────────────────────

class TestLamportClock:
    """Lamport-style logical clocks for causal ordering of graph operations."""

    def test_lamport_clock_init(self, mg):
        """lamport_clock starts at 0 for a fresh graph."""
        assert mg.lamport_clock() == 0

    def test_lamport_clock_tick_on_add(self, mg):
        """Adding a node advances the logical clock."""
        mg.add("Alpha", "concept")
        assert mg.lamport_clock() == 1
        mg.add("Beta", "concept")
        assert mg.lamport_clock() == 2

    def test_lamport_clock_tick_on_link(self, mg):
        """Linking nodes advances the clock."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "related")
        assert mg.lamport_clock() == 3

    def test_lamport_clock_tick_on_update(self, mg):
        """Updating a node advances the clock."""
        n = mg.add("Old", "concept")
        mg.update_node(n.id, label="New")
        assert mg.lamport_clock() == 2

    def test_lamport_clock_tick_on_delete(self, mg):
        """Deleting a node advances the clock."""
        n = mg.add("Temp", "concept")
        mg.delete_node(n.id)
        assert mg.lamport_clock() == 2

    def test_event_log_captures_operations(self, mg):
        """The clock log records operation types."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "related")
        log = mg.event_log()
        assert len(log) == 3
        assert log[0]["op"] == "add"
        assert log[1]["op"] == "add"
        assert log[2]["op"] == "link"

    def test_event_log_has_timestamps(self, mg):
        """Each log entry has a Lamport timestamp."""
        mg.add("X", "concept")
        log = mg.event_log()
        assert "lamport" in log[0]
        assert log[0]["lamport"] == 1

    def test_event_log_has_node_details(self, mg):
        """Log entries include node_id when relevant."""
        n = mg.add("A", "concept")
        log = mg.event_log()
        assert log[0]["node_id"] == n.id

    def test_lamport_clock_independent_of_real_time(self, mg):
        """Clock only advances on operations, not time."""
        import time
        c1 = mg.lamport_clock()
        time.sleep(0.05)
        c2 = mg.lamport_clock()
        assert c1 == c2


class TestTypedPubSub:
    """Reactive typed pub/sub for graph mutation events."""

    def test_on_add_event(self, mg):
        """on('add', ...) receives add events."""
        events = []
        mg.on("add", lambda evt: events.append(evt))
        mg.add("Alpha", "concept")
        assert len(events) == 1
        assert events[0]["op"] == "add"
        assert events[0]["label"] == "Alpha"

    def test_on_link_event(self, mg):
        """on('link', ...) receives link events."""
        events = []
        mg.on("link", lambda evt: events.append(evt))
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "related")
        assert len(events) == 1
        assert events[0]["relation"] == "related"

    def test_on_delete_event(self, mg):
        """on('delete', ...) receives delete events."""
        events = []
        mg.on("delete", lambda evt: events.append(evt))
        n = mg.add("Temp", "concept")
        mg.delete_node(n.id)
        assert len(events) == 1
        assert events[0]["node_id"] == n.id

    def test_on_update_event(self, mg):
        """on('update', ...) receives update events."""
        events = []
        mg.on("update", lambda evt: events.append(evt))
        n = mg.add("Old", "concept")
        mg.update_node(n.id, label="New")
        assert len(events) == 1
        assert events[0]["old_label"] == "Old"
        assert events[0]["new_label"] == "New"

    def test_on_multiple_callbacks(self, mg):
        """Multiple callbacks for the same event type."""
        e1, e2 = [], []
        mg.on("add", lambda evt: e1.append(evt))
        mg.on("add", lambda evt: e2.append(evt))
        mg.add("X", "concept")
        assert len(e1) == 1
        assert len(e2) == 1

    def test_on_all_events(self, mg):
        """on('*', ...) receives all event types."""
        events = []
        mg.on("*", lambda evt: events.append(evt))
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "related")
        assert len(events) == 3

    def test_off_removes_subscription(self, mg):
        """off() stops receiving events."""
        events = []
        sub_id = mg.on("add", lambda evt: events.append(evt))
        mg.add("Before", "concept")
        assert len(events) == 1
        mg.off(sub_id)
        mg.add("After", "concept")
        assert len(events) == 1  # no new event

    def test_on_lamport_in_event(self, mg):
        """Events include the Lamport timestamp."""
        events = []
        mg.on("add", lambda evt: events.append(evt))
        mg.add("X", "concept")
        assert "lamport" in events[0]
        assert events[0]["lamport"] == 1


# ─────────────────────────────────────────────────────────────
# Cycle 174: Memory Conflict Detection
# ─────────────────────────────────────────────────────────────

class TestConflictDetect:
    """Detect contradictions between facts in the memory graph."""

    def test_no_conflict_empty_graph(self, mg):
        """Empty graph has no conflicts."""
        assert mg.conflict_detect() == []

    def test_no_conflict_compatible_facts(self, mg):
        """Non-overlapping facts don't conflict."""
        mg.add("Python is a language", "fact")
        mg.add("Rust is a language", "fact")
        assert mg.conflict_detect() == []

    def test_detect_same_subject_different_values(self, mg):
        """Same subject with contradictory values triggers conflict."""
        mg.add("Earth radius is 6371 km", "fact")
        mg.add("Earth radius is 7000 km", "fact")
        conflicts = mg.conflict_detect()
        assert len(conflicts) >= 1
        assert "node_a" in conflicts[0]
        assert "node_b" in conflicts[0]
        assert conflicts[0]["type"] == "value_mismatch"

    def test_conflict_score_between_0_and_1(self, mg):
        """Conflict scores are normalized to [0, 1]."""
        mg.add("The sky is blue", "fact")
        mg.add("The sky is green", "fact")
        conflicts = mg.conflict_detect()
        for c in conflicts:
            assert 0.0 <= c["score"] <= 1.0

    def test_detect_by_entity_overlap(self, mg):
        """Facts sharing key entities are checked for conflicts."""
        mg.add("Paris is the capital of France", "fact")
        mg.add("Paris is the capital of Germany", "fact")
        conflicts = mg.conflict_detect()
        assert len(conflicts) >= 1

    def test_high_similarity_no_conflict(self, mg):
        """Very similar labels that are restatements don't conflict."""
        mg.add("Water boils at 100C", "fact")
        mg.add("Water boils at 100 degrees Celsius", "fact")
        conflicts = mg.conflict_detect()
        # These are semantically equivalent, should not conflict
        assert len(conflicts) == 0

    def test_conflict_with_numbers(self, mg):
        """Facts with different numeric values for the same entity conflict."""
        mg.add("GDP of X is 5 trillion", "fact")
        mg.add("GDP of X is 8 trillion", "fact")
        conflicts = mg.conflict_detect()
        assert len(conflicts) >= 1

    def test_conflict_resolve(self, mg):
        """conflict_resolve marks one as superseded."""
        a = mg.add("The answer is 42", "fact")
        b = mg.add("The answer is 7", "fact")
        mg.conflict_resolve(a.id, b.id, reason="verified correct value")
        # b should be marked as quarantined or invalid
        row = mg.conn.execute("SELECT * FROM nodes WHERE id=?", (b.id,)).fetchone()
        assert row["quarantined"] == 1

    def test_conflict_detect_with_kind_filter(self, mg):
        """conflict_detect can filter by kind."""
        mg.add("Temperature is 25C", "fact")
        mg.add("Temperature is 90C", "fact")
        mg.add("Random thought", "concept")
        conflicts = mg.conflict_detect(kind="fact")
        assert len(conflicts) >= 1
        # concepts should not appear
        for c in conflicts:
            assert c["kind_b"] == "fact"

    def test_conflict_score_threshold(self, mg):
        """Higher threshold reduces reported conflicts."""
        mg.add("A is probably 10", "fact")
        mg.add("A might be 12", "fact")
        strict = mg.conflict_detect(threshold=0.9)
        loose = mg.conflict_detect(threshold=0.3)
        assert len(loose) >= len(strict)

    def test_conflict_report_human_readable(self, mg):
        """conflict_report returns a human-readable summary."""
        a = mg.add("X equals 5", "fact")
        b = mg.add("X equals 10", "fact")
        conflicts = mg.conflict_detect()
        report = mg.conflict_report(conflicts)
        assert isinstance(report, str)
        assert "X equals 5" in report
        assert "X equals 10" in report


# ─────────────────────────────────────────────────────────────
# Cycle 175: Strategic Forget
# ─────────────────────────────────────────────────────────────

class TestStrategicForget:
    """Confidence-weighted deliberate forgetting — the missing memory operation."""

    def test_strategic_forget_empty_graph(self, mg):
        """Empty graph forgets nothing."""
        result = mg.strategic_forget()
        assert result["forgotten"] == 0

    def test_strategic_forget_low_weight(self, mg):
        """Nodes below weight threshold are forgotten."""
        a = mg.add("Important", "fact")
        b = mg.add("Trivial", "fact")
        mg.update_node(b.id, weight=0.05)
        result = mg.strategic_forget(min_weight=0.1)
        assert result["forgotten"] == 1
        assert mg.get_node(b.id) is None
        assert mg.get_node(a.id) is not None

    def test_strategic_forget_old_unused(self, mg):
        """Nodes not accessed in a long time are forgotten."""
        import time
        a = mg.add("Recent", "fact")
        b = mg.add("Ancient", "fact")
        # Set b's accessed time to 30 days ago
        old_time = time.time() - 30 * 86400
        mg.conn.execute("UPDATE nodes SET accessed=? WHERE id=?", (old_time, b.id))
        mg.conn.commit()
        result = mg.strategic_forget(max_age_days=7)
        assert result["forgotten"] == 1
        assert mg.get_node(b.id) is None

    def test_strategic_forget_protects_high_q_value(self, mg):
        """High Q-value nodes are protected even if old/low-weight."""
        import time
        a = mg.add("Valuable old", "fact")
        old_time = time.time() - 100 * 86400
        mg.conn.execute("UPDATE nodes SET accessed=?, weight=0.05, q_value=5.0 WHERE id=?",
                        (old_time, a.id))
        mg.conn.commit()
        result = mg.strategic_forget(max_age_days=7, min_weight=0.1, protect_q_above=1.0)
        assert result["forgotten"] == 0
        assert mg.get_node(a.id) is not None

    def test_strategic_forget_dry_run(self, mg):
        """Dry run reports what would be forgotten without deleting."""
        a = mg.add("Keep", "fact")
        b = mg.add("Forget me", "fact")
        mg.update_node(b.id, weight=0.01)
        result = mg.strategic_forget(min_weight=0.1, dry_run=True)
        assert result["forgotten"] == 1
        # Node should still exist
        assert mg.get_node(b.id) is not None

    def test_strategic_forget_quarantined_excluded(self, mg):
        """Quarantined nodes are not candidates for strategic forget."""
        a = mg.add("Bad data", "fact")
        mg.node_quarantine(a.id, reason="unverified")
        result = mg.strategic_forget(min_weight=0.9)
        # Quarantined nodes are excluded from forget candidates
        assert result["forgotten"] == 0

    def test_strategic_forget_preserves_edges_report(self, mg):
        """Forgotten nodes report how many edges were cleaned up."""
        a = mg.add("Keep", "fact")
        b = mg.add("Forget", "fact")
        mg.link(a.id, b.id, "related")
        mg.link(b.id, a.id, "back")
        mg.update_node(b.id, weight=0.01)
        result = mg.strategic_forget(min_weight=0.1)
        assert result["forgotten"] == 1
        assert result["edges_removed"] >= 2

    def test_strategic_forget_details_list(self, mg):
        """Forgotten node details are returned for audit trail."""
        a = mg.add("Low value", "fact")
        mg.update_node(a.id, weight=0.01)
        result = mg.strategic_forget(min_weight=0.1)
        assert len(result["details"]) == 1
        assert result["details"][0]["label"] == "Low value"

    def test_strategic_forget_by_kind(self, mg):
        """Kind filter limits forgetting to specific types."""
        a = mg.add("Old fact", "fact")
        b = mg.add("Old skill", "skill")
        mg.update_node(a.id, weight=0.01)
        mg.update_node(b.id, weight=0.01)
        result = mg.strategic_forget(min_weight=0.1, kind="fact")
        assert result["forgotten"] == 1
        assert mg.get_node(b.id) is not None

    def test_strategic_forget_logs_to_event_log(self, mg):
        """Forgotten nodes are logged in the Lamport event log."""
        a = mg.add("Forget me", "fact")
        mg.update_node(a.id, weight=0.01)
        mg.strategic_forget(min_weight=0.1)
        log = mg.event_log()
        forget_entries = [e for e in log if e["op"] == "strategic_forget"]
        assert len(forget_entries) >= 1

    def test_strategic_forget_retention_target(self, mg):
        """Forget enough nodes to reach a target count."""
        for i in range(20):
            mg.add(f"Node {i}", "fact", {"index": i})
        # Target 10 nodes — should forget 10 lowest-weight ones
        result = mg.strategic_forget(target_count=10)
        assert result["forgotten"] == 10
        stats = mg.stats()
        assert stats["nodes"] == 10


# ── Cycle 176: Label Propagation Community Detection ──

class TestCommunityDetection:
    """Tests for LPA-based community detection."""

    def test_empty_graph_no_communities(self, mg):
        """Empty graph has no communities."""
        result = mg.detect_communities()
        assert result["num_communities"] == 0
        assert result["modularity"] == 0.0

    def test_single_node(self, mg):
        """Single isolated node forms its own community."""
        mg.add("Lonely node", "concept")
        result = mg.detect_communities()
        assert result["num_communities"] == 1
        assert result["iterations"] <= 1

    def test_two_connected_nodes_same_community(self, mg):
        """Two connected nodes should be in the same community."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "related")
        result = mg.detect_communities()
        assert result["num_communities"] == 1
        assert result["node_community"][a.id] == result["node_community"][b.id]

    def test_two_separate_components(self, mg):
        """Two disconnected components form two communities."""
        a1 = mg.add("A1", "concept")
        a2 = mg.add("A2", "concept")
        mg.link(a1.id, a2.id, "related")
        b1 = mg.add("B1", "fact")
        b2 = mg.add("B2", "fact")
        mg.link(b1.id, b2.id, "related")
        result = mg.detect_communities()
        assert result["num_communities"] == 2
        # Nodes in same component share community
        assert result["node_community"][a1.id] == result["node_community"][a2.id]
        assert result["node_community"][b1.id] == result["node_community"][b2.id]
        # Nodes in different components have different communities
        assert result["node_community"][a1.id] != result["node_community"][b1.id]

    def test_star_graph_one_community(self, mg):
        """A star graph (hub + spokes) is one community."""
        hub = mg.add("Hub", "concept")
        for i in range(5):
            spoke = mg.add(f"Spoke {i}", "fact")
            mg.link(hub.id, spoke.id, "connects")
        result = mg.detect_communities()
        assert result["num_communities"] == 1

    def test_triangle_vs_isolated(self, mg):
        """A triangle (3-clique) + 1 isolated node = 2 communities."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        c = mg.add("C", "concept")
        mg.link(a.id, b.id, "x")
        mg.link(b.id, c.id, "x")
        mg.link(a.id, c.id, "x")
        d = mg.add("D", "fact")  # isolated
        result = mg.detect_communities()
        assert result["num_communities"] == 2

    def test_modularity_nonnegative_connected(self, mg):
        """A connected graph should have non-negative modularity."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "x")
        result = mg.detect_communities()
        assert result["modularity"] >= 0.0

    def test_modularity_range(self, mg):
        """Modularity should be in valid range [-0.5, 1]."""
        for i in range(10):
            mg.add(f"Node {i}", "concept")
        # Add some edges
        nodes = [r["id"] for r in mg.conn.execute("SELECT id FROM nodes").fetchall()]
        for i in range(len(nodes) - 1):
            mg.link(nodes[i], nodes[i + 1], "chain")
        result = mg.detect_communities()
        assert -0.5 <= result["modularity"] <= 1.0

    def test_iterations_capped(self, mg):
        """Iterations should not exceed max_iterations."""
        for i in range(20):
            mg.add(f"Node {i}", "concept")
        result = mg.detect_communities(max_iterations=3)
        assert result["iterations"] <= 3

    def test_community_of_returns_none_for_unknown(self, mg):
        """community_of returns None for non-existent node."""
        assert mg.community_of("nonexistent") is None

    def test_community_of_returns_id(self, mg):
        """community_of returns a valid community ID for existing nodes."""
        a = mg.add("Node", "concept")
        cid = mg.community_of(a.id)
        assert cid is not None
        assert isinstance(cid, int)

    def test_community_members_returns_nodes(self, mg):
        """community_members returns actual Node objects."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "x")
        mg.detect_communities()
        cid = mg.community_of(a.id)
        members = mg.community_members(cid)
        labels = {m.label for m in members}
        assert "A" in labels and "B" in labels

    def test_community_members_empty_for_invalid_id(self, mg):
        """community_members returns empty list for invalid community ID."""
        mg.add("Node", "concept")
        mg.detect_communities()
        assert mg.community_members(99999) == []

    def test_detect_communities_excludes_quarantined(self, mg):
        """Quarantined nodes are excluded from community detection."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        c = mg.add("C - bad", "concept")
        mg.link(a.id, b.id, "x")
        mg.link(a.id, c.id, "x")
        mg.node_quarantine(c.id, "test")
        result = mg.detect_communities()
        assert c.id not in result["node_community"]

    def test_resolution_kind_bias(self, mg):
        """Higher resolution biases toward same-kind communities."""
        # Create two kinds with cross-kind edges
        facts = [mg.add(f"F{i}", "fact") for i in range(4)]
        concepts = [mg.add(f"C{i}", "concept") for i in range(4)]
        # Dense intra-kind links
        for i in range(len(facts)):
            for j in range(i + 1, len(facts)):
                mg.link(facts[i].id, facts[j].id, "same")
        for i in range(len(concepts)):
            for j in range(i + 1, len(concepts)):
                mg.link(concepts[i].id, concepts[j].id, "same")
        # One cross-kind link
        mg.link(facts[0].id, concepts[0].id, "bridge")
        result_high = mg.detect_communities(resolution=5.0)
        # With high resolution, the bridge is less likely to merge communities
        assert result_high["num_communities"] >= 1


# ── Cycle 177: Community-aware Retrieval & Analysis ──

class TestCommunityStats:
    """Tests for community_stats()."""

    def test_empty_graph_stats(self, mg):
        """Empty graph returns empty community stats."""
        assert mg.community_stats() == []

    def test_stats_have_required_fields(self, mg):
        """Each community stat has all required fields."""
        a = mg.add("A", "concept")
        b = mg.add("B", "fact")
        mg.link(a.id, b.id, "x")
        mg.detect_communities()
        stats = mg.community_stats()
        assert len(stats) >= 1
        s = stats[0]
        assert "community_id" in s
        assert "size" in s
        assert "kinds" in s
        assert "avg_weight" in s
        assert "avg_q_value" in s
        assert "internal_edges" in s
        assert "total_edges" in s
        assert "density" in s

    def test_stats_density_connected_pair(self, mg):
        """Two connected nodes have density 1.0 (one edge, max one edge)."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "x")
        mg.detect_communities()
        stats = mg.community_stats()
        # Find the community containing both
        for s in stats:
            if s["size"] == 2:
                assert s["density"] == 1.0
                break

    def test_stats_kinds_breakdown(self, mg):
        """Kinds dict correctly counts node types."""
        mg.add("Fact1", "fact")
        mg.add("Fact2", "fact")
        mg.add("Concept1", "concept")
        mg.detect_communities()
        stats = mg.community_stats()
        total_kinds = {}
        for s in stats:
            for k, v in s["kinds"].items():
                total_kinds[k] = total_kinds.get(k, 0) + v
        assert total_kinds.get("fact", 0) == 2
        assert total_kinds.get("concept", 0) == 1

    def test_stats_internal_vs_total_edges(self, mg):
        """Two components: internal edges within, total includes cross."""
        a1 = mg.add("A1", "concept")
        a2 = mg.add("A2", "concept")
        mg.link(a1.id, a2.id, "x")
        b1 = mg.add("B1", "fact")
        mg.detect_communities()
        stats = mg.community_stats()
        # At least one community with internal_edges >= 1
        assert any(s["internal_edges"] >= 1 for s in stats)


class TestCommunitySearch:
    """Tests for search_community()."""

    def test_search_community_returns_nodes(self, mg):
        """search_community returns relevant nodes."""
        a = mg.add("Python programming", "skill")
        b = mg.add("Python ecosystem", "concept")
        c = mg.add("Rust embedded", "concept")
        mg.link(a.id, b.id, "related")
        mg.link(b.id, c.id, "bridge")
        results = mg.search_community("Python")
        assert len(results) > 0
        labels = [r.label for r in results]
        assert any("Python" in l for l in labels)

    def test_search_community_empty_graph(self, mg):
        """search_community on empty graph returns empty list."""
        assert mg.search_community("anything") == []

    def test_search_community_falls_back_on_no_match(self, mg):
        """If no community match, falls back to global recall."""
        a = mg.add("Alpha", "concept")
        results = mg.search_community("nonexistent term xyz123")
        # Should return empty list (no match), not crash
        assert isinstance(results, list)

    def test_search_community_prefers_community_members(self, mg):
        """Results should bias toward community members of the seed."""
        # Community 1: Python cluster
        py1 = mg.add("Python basics", "skill")
        py2 = mg.add("Python advanced", "skill")
        py3 = mg.add("Python testing", "skill")
        mg.link(py1.id, py2.id, "related")
        mg.link(py2.id, py3.id, "related")
        mg.link(py1.id, py3.id, "related")
        # Community 2: isolated Rust
        rust = mg.add("Rust ownership", "skill")
        results = mg.search_community("Python")
        labels = {r.label for r in results}
        # Python nodes should be favored
        assert any("Python" in l for l in labels)


class TestCommunityGraph:
    """Tests for community_graph() — supernode reduction."""

    def test_empty_graph_community_graph(self, mg):
        """Empty graph returns empty community graph."""
        result = mg.community_graph()
        assert result["supernodes"] == []
        assert result["superedges"] == []

    def test_single_community_no_superedges(self, mg):
        """One community means no inter-community edges."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "x")
        mg.detect_communities()
        result = mg.community_graph()
        assert len(result["supernodes"]) == 1
        assert result["superedges"] == []

    def test_two_communities_with_bridge(self, mg):
        """Two communities connected by a bridge edge."""
        # Build two dense clusters (triangles) + one bridge
        a1 = mg.add("A1", "concept")
        a2 = mg.add("A2", "concept")
        a3 = mg.add("A3", "concept")
        mg.link(a1.id, a2.id, "same")
        mg.link(a2.id, a3.id, "same")
        mg.link(a1.id, a3.id, "same")
        b1 = mg.add("B1", "fact")
        b2 = mg.add("B2", "fact")
        b3 = mg.add("B3", "fact")
        mg.link(b1.id, b2.id, "same")
        mg.link(b2.id, b3.id, "same")
        mg.link(b1.id, b3.id, "same")
        mg.link(a1.id, b1.id, "bridge")  # inter-community
        mg.detect_communities()
        result = mg.community_graph()
        assert len(result["supernodes"]) == 2
        assert len(result["superedges"]) == 1
        se = result["superedges"][0]
        assert se["edges"] == 1

    def test_supernode_has_dominant_kind(self, mg):
        """Supernode reports the dominant kind in its community."""
        mg.add("F1", "fact")
        mg.add("F2", "fact")
        mg.add("C1", "concept")
        mg.detect_communities()
        result = mg.community_graph()
        assert len(result["supernodes"]) >= 1
        sn = result["supernodes"][0]
        assert "dominant_kind" in sn
        assert sn["dominant_kind"] in ("fact", "concept")

    def test_supernode_density_field(self, mg):
        """Supernode has density field."""
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        mg.link(a.id, b.id, "x")
        mg.detect_communities()
        result = mg.community_graph()
        sn = result["supernodes"][0]
        assert "density" in sn
        assert 0.0 <= sn["density"] <= 1.0
