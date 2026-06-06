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
        assert "text" in results[0]["sources"]

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
        assert "text" in top["sources"]
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
