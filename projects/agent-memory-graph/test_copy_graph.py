"""Tests for copy_graph() — deep copy of entire graph."""
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


class TestCopyGraphBasic:
    def test_returns_new_instance(self, mg):
        mg.add("A")
        clone = mg.copy_graph()
        assert clone is not mg
        assert isinstance(clone, MemoryGraph)

    def test_preserves_node_count(self, mg):
        mg.add("A")
        mg.add("B")
        mg.add("C")
        clone = mg.copy_graph()
        assert clone.stats()["nodes"] == 3

    def test_preserves_edge_count(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "edge")
        clone = mg.copy_graph()
        assert clone.stats()["edges"] == 1

    def test_preserves_labels(self, mg):
        mg.add("Hello")
        mg.add("World")
        clone = mg.copy_graph()
        labels = [n.label for n in [clone.get_node(r[0]) for r in clone.conn.execute("SELECT id FROM nodes").fetchall()] if n]
        assert "Hello" in labels
        assert "World" in labels

    def test_preserves_node_ids(self, mg):
        a = mg.add("A")
        mg.add("B")
        clone = mg.copy_graph()
        assert clone.get_node(a.id) is not None
        assert clone.get_node(a.id).label == "A"

    def test_preserves_edge_relations(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "friend")
        clone = mg.copy_graph()
        edge = clone.get_edge(a.id, b.id, "friend")
        assert edge is not None
        assert edge.relation == "friend"

    def test_preserves_edge_weights(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "edge", weight=3.14)
        clone = mg.copy_graph()
        edge = clone.get_edge(a.id, b.id, "edge")
        assert edge is not None
        assert abs(edge.weight - 3.14) < 0.01


class TestCopyGraphIsolation:
    def test_add_to_clone_no_effect_on_original(self, mg):
        mg.add("A")
        clone = mg.copy_graph()
        clone.add("B")
        assert mg.stats()["nodes"] == 1
        assert clone.stats()["nodes"] == 2

    def test_add_to_original_no_effect_on_clone(self, mg):
        mg.add("A")
        clone = mg.copy_graph()
        mg.add("B")
        assert mg.stats()["nodes"] == 2
        assert clone.stats()["nodes"] == 1

    def test_link_in_clone_no_effect_on_original(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        clone = mg.copy_graph()
        clone.link(a.id, b.id, "edge")
        assert mg.stats()["edges"] == 0
        assert clone.stats()["edges"] == 1

    def test_delete_in_clone_no_effect_on_original(self, mg):
        a = mg.add("A")
        mg.add("B")
        clone = mg.copy_graph()
        clone.delete_node(a.id)
        assert mg.stats()["nodes"] == 2
        assert clone.stats()["nodes"] == 1

    def test_rename_in_clone_no_effect_on_original(self, mg):
        a = mg.add("Original")
        clone = mg.copy_graph()
        clone.rename_node(a.id, "Changed")
        assert mg.get_node(a.id).label == "Original"
        assert clone.get_node(a.id).label == "Changed"


class TestCopyGraphComplex:
    def test_empty_graph_copy(self, mg):
        clone = mg.copy_graph()
        assert clone.stats()["nodes"] == 0
        assert clone.stats()["edges"] == 0

    def test_large_graph_copy(self, mg):
        nodes = [mg.add("N%d" % i) for i in range(50)]
        for i in range(49):
            mg.link(nodes[i].id, nodes[i + 1].id, "edge")
        clone = mg.copy_graph()
        assert clone.stats()["nodes"] == 50
        assert clone.stats()["edges"] == 49

    def test_multiple_edges_same_pair(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "r1", weight=1.0)
        mg.link(a.id, b.id, "r2", weight=2.0)
        clone = mg.copy_graph()
        assert clone.stats()["edges"] == 2

    def test_preserves_kinds(self, mg):
        mg.add("Task1", kind="task")
        mg.add("Note1", kind="note")
        clone = mg.copy_graph()
        rows = clone.conn.execute("SELECT kind FROM nodes").fetchall()
        kinds = {r["kind"] for r in rows}
        assert kinds == {"task", "note"}

    def test_digest_matches(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "edge")
        clone = mg.copy_graph()
        assert mg.graph_digest(include_content=True) == clone.graph_digest(include_content=True)

    def test_disconnected_components(self, mg):
        a1 = mg.add("A1")
        a2 = mg.add("A2")
        b1 = mg.add("B1")
        b2 = mg.add("B2")
        mg.link(a1.id, a2.id, "r")
        mg.link(b1.id, b2.id, "r")
        clone = mg.copy_graph()
        assert clone.stats()["nodes"] == 4
        assert clone.stats()["edges"] == 2
