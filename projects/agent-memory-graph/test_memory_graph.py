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
