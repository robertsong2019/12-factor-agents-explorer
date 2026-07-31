"""Tests for project_graph() — relation-specific subgraph projection (Research #040).

Projects the graph onto a single relation type, returning a new
MemoryGraph instance that supports all graph algorithms.
"""
import pytest
from memory_graph import MemoryGraph


class TestProjectGraph:
    """Relation-specific graph projection."""

    def setup_method(self):
        """Build a multi-relational graph.

        Edges:
            A --causes--> B
            B --causes--> C
            A --similar_to--> D
            D --similar_to--> C
            C --depends_on--> E
        """
        self.mg = MemoryGraph()
        self.a = self.mg.add("Event A", kind="event", data={"importance": "high"})
        self.b = self.mg.add("Event B", kind="event", data={"importance": "medium"})
        self.c = self.mg.add("Event C", kind="event")
        self.d = self.mg.add("Concept D", kind="concept")
        self.e = self.mg.add("Resource E", kind="resource")

        self.mg.link(self.a.id, self.b.id, "causes")
        self.mg.link(self.b.id, self.c.id, "causes")
        self.mg.link(self.a.id, self.d.id, "similar_to")
        self.mg.link(self.d.id, self.c.id, "similar_to")
        self.mg.link(self.c.id, self.e.id, "depends_on")

    def _node_count(self, mg):
        return mg.stats()["nodes"]

    def _node_labels(self, mg):
        rows = mg.conn.execute("SELECT label FROM nodes").fetchall()
        return {r["label"] for r in rows}

    def _node_kinds(self, mg):
        rows = mg.conn.execute("SELECT kind FROM nodes").fetchall()
        return {r["kind"] for r in rows}

    def test_returns_memory_graph_instance(self):
        """project_graph should return a MemoryGraph instance."""
        projected = self.mg.project_graph("causes")
        assert isinstance(projected, MemoryGraph)

    def test_empty_relation_returns_empty_graph(self):
        """Non-existent relation should return empty graph."""
        projected = self.mg.project_graph("nonexistent")
        assert isinstance(projected, MemoryGraph)
        assert self._node_count(projected) == 0

    def test_only_specified_edges_in_projection(self):
        """Projected graph should contain only the specified relation type."""
        projected = self.mg.project_graph("causes")
        edges = projected.conn.execute("SELECT relation FROM edges").fetchall()
        relations = {e["relation"] for e in edges}
        assert relations == {"causes"}

    def test_preserves_correct_nodes(self):
        """Projection should contain nodes that participate in the relation."""
        projected = self.mg.project_graph("causes")
        labels = self._node_labels(projected)
        assert "Event A" in labels
        assert "Event B" in labels
        assert "Event C" in labels
        assert "Concept D" not in labels
        assert "Resource E" not in labels

    def test_preserves_node_metadata(self):
        """Node metadata (kind, data) should be preserved."""
        projected = self.mg.project_graph("causes")
        rows = projected.conn.execute(
            "SELECT * FROM nodes WHERE label='Event A'"
        ).fetchall()
        assert len(rows) == 1
        import json
        data = json.loads(rows[0]["data"]) if rows[0]["data"] else {}
        assert data.get("importance") == "high"
        assert rows[0]["kind"] == "event"

    def test_preserves_edge_weights(self):
        """Edge weights should be preserved in projection."""
        mg = MemoryGraph()
        n1 = mg.add("X")
        n2 = mg.add("Y")
        mg.link(n1.id, n2.id, "causes", weight=0.7)

        projected = mg.project_graph("causes")
        edges = projected.conn.execute("SELECT weight FROM edges").fetchall()
        assert len(edges) == 1
        assert abs(edges[0]["weight"] - 0.7) < 0.01

    def test_projected_graph_supports_algorithms(self):
        """Projected graph should support all MemoryGraph algorithms."""
        projected = self.mg.project_graph("causes")
        rows = projected.conn.execute("SELECT id FROM nodes LIMIT 1").fetchall()
        if rows:
            bfs = projected.bfs_order(rows[0]["id"])
            assert isinstance(bfs, list)

    def test_projected_graph_has_correct_edge_count(self):
        """Edge count should match the number of edges of that relation."""
        projected_causes = self.mg.project_graph("causes")
        cause_edges = projected_causes.conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()
        assert cause_edges["c"] == 2  # A→B, B→C

        projected_sim = self.mg.project_graph("similar_to")
        sim_edges = projected_sim.conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()
        assert sim_edges["c"] == 2  # A→D, D→C

    def test_projected_graph_has_correct_node_count(self):
        """Node count should match nodes participating in that relation."""
        projected_causes = self.mg.project_graph("causes")
        assert self._node_count(projected_causes) == 3  # A, B, C

        projected_sim = self.mg.project_graph("similar_to")
        assert self._node_count(projected_sim) == 3  # A, D, C

    def test_no_metadata_strips_data(self):
        """include_metadata=False should strip node data."""
        projected = self.mg.project_graph("causes", include_metadata=False)
        rows = projected.conn.execute("SELECT * FROM nodes").fetchall()
        for r in rows:
            assert r["kind"] == "fact"
            import json
            data = json.loads(r["data"]) if r["data"] else {}
            assert data == {}

    def test_projection_independent_of_original(self):
        """Modifying the projection should not affect the original graph."""
        projected = self.mg.project_graph("causes")
        projected.add("New Node")

        original_new = self.mg.search_by_label("New Node")
        assert len(original_new) == 0

    def test_project_single_edge_relation(self):
        """Single-edge relation should produce correct projection."""
        projected = self.mg.project_graph("depends_on")
        assert self._node_count(projected) == 2  # C, E
        edges = projected.conn.execute("SELECT * FROM edges").fetchall()
        assert len(edges) == 1

    def test_project_with_self_loop(self):
        """Self-loops should be handled correctly."""
        mg = MemoryGraph()
        n1 = mg.add("Self")
        mg.link(n1.id, n1.id, "causes")

        projected = mg.project_graph("causes")
        assert self._node_count(projected) == 1
        edges = projected.conn.execute("SELECT * FROM edges").fetchall()
        assert len(edges) == 1

    def test_project_preserves_graph_structure(self):
        """Projection should maintain connectivity."""
        projected = self.mg.project_graph("causes")
        rows = projected.conn.execute(
            "SELECT id FROM nodes WHERE label='Event A'"
        ).fetchall()
        assert len(rows) == 1
        neighbors = projected.neighbors(rows[0]["id"])
        assert len(neighbors) == 1  # only B

    def test_different_relations_produce_different_graphs(self):
        """Different relation types should produce different projections."""
        proj_causes = self.mg.project_graph("causes")
        proj_similar = self.mg.project_graph("similar_to")

        causes_labels = self._node_labels(proj_causes)
        similar_labels = self._node_labels(proj_similar)

        assert causes_labels != similar_labels

    def test_project_empty_graph(self):
        """Projecting an empty graph should return empty graph."""
        mg = MemoryGraph()
        projected = mg.project_graph("causes")
        assert isinstance(projected, MemoryGraph)
        assert self._node_count(projected) == 0

    def test_projected_graph_can_add_new_data(self):
        """Projected graph should be fully functional (can add new nodes/edges)."""
        projected = self.mg.project_graph("causes")
        new_node = projected.add("New")
        assert new_node is not None
        assert projected.has_node(new_node.id)

    def test_projected_graph_entropy_calculation(self):
        """Projected graph should support entropy calculations."""
        projected = self.mg.project_graph("causes")
        try:
            result = projected.entropy_profile()
            assert isinstance(result, dict)
        except (ValueError, ZeroDivisionError):
            pass  # OK for very small graphs

    def test_multiple_edges_same_relation_preserved(self):
        """Multiple edges of the same relation should all be preserved."""
        mg = MemoryGraph()
        n1 = mg.add("Hub")
        for i in range(5):
            leaf = mg.add(f"Leaf{i}")
            mg.link(n1.id, leaf.id, "causes")

        projected = mg.project_graph("causes")
        assert self._node_count(projected) == 6  # hub + 5 leaves
        edges = projected.conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()
        assert edges["c"] == 5

    def test_project_preserves_node_weight(self):
        """Node weights should be preserved in projection."""
        mg = MemoryGraph()
        n1 = mg.add("Heavy", data={"w": 1})
        n2 = mg.add("Light")
        mg.link(n1.id, n2.id, "causes")
        mg.conn.execute("UPDATE nodes SET weight=2.5 WHERE id=?", (n1.id,))
        mg.conn.commit()

        projected = mg.project_graph("causes")
        row = projected.conn.execute(
            "SELECT weight FROM nodes WHERE label='Heavy'"
        ).fetchone()
        assert row is not None
        assert abs(row["weight"] - 2.5) < 0.01
