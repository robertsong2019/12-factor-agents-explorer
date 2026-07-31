"""Tests for multi_perspective_analysis() — comparative relation views (Research #040).

Projects the graph onto each relation type, computes metrics per view,
and returns a comparative analysis.
"""
import pytest
from memory_graph import MemoryGraph


class TestMultiPerspectiveAnalysis:
    """Multi-perspective graph analysis via per-relation projections."""

    def setup_method(self):
        """Build a multi-relational graph with 3 relation types.

        Edges:
            A --causes--> B --causes--> C
            A --similar_to--> D
            C --similar_to--> D
            B --depends_on--> E
            A --depends_on--> C
        """
        self.mg = MemoryGraph()
        self.a = self.mg.add("Event A", kind="event")
        self.b = self.mg.add("Event B", kind="event")
        self.c = self.mg.add("Event C", kind="event")
        self.d = self.mg.add("Concept D", kind="concept")
        self.e = self.mg.add("Resource E", kind="resource")

        self.mg.link(self.a.id, self.b.id, "causes")
        self.mg.link(self.b.id, self.c.id, "causes")
        self.mg.link(self.a.id, self.d.id, "similar_to")
        self.mg.link(self.c.id, self.d.id, "similar_to")
        self.mg.link(self.b.id, self.e.id, "depends_on")
        self.mg.link(self.a.id, self.c.id, "depends_on")

    def test_returns_dict_with_expected_keys(self):
        result = self.mg.multi_perspective_analysis()
        assert "perspectives" in result
        assert "relation_ranking" in result
        assert "dominant_relation" in result
        assert "cross_perspective_nodes" in result
        assert "total_relations" in result

    def test_detects_all_relation_types(self):
        result = self.mg.multi_perspective_analysis()
        assert result["total_relations"] == 3
        assert "causes" in result["perspectives"]
        assert "similar_to" in result["perspectives"]
        assert "depends_on" in result["perspectives"]

    def test_dominant_relation_has_most_edges(self):
        """causes has 2 edges, similar_to has 2, depends_on has 2.
        All are tied, so any could be dominant."""
        result = self.mg.multi_perspective_analysis()
        dominant = result["dominant_relation"]
        assert dominant in ("causes", "similar_to", "depends_on")
        # dominant should have max edge count
        max_edges = max(v["edge_count"] for v in result["perspectives"].values())
        assert result["perspectives"][dominant]["edge_count"] == max_edges

    def test_relation_ranking_sorted_by_edge_count(self):
        result = self.mg.multi_perspective_analysis()
        ranking = result["relation_ranking"]
        edges = [result["perspectives"][r]["edge_count"] for r in ranking]
        assert edges == sorted(edges, reverse=True)

    def test_each_perspective_has_metrics(self):
        result = self.mg.multi_perspective_analysis()
        for rel, view in result["perspectives"].items():
            assert "node_count" in view
            assert "edge_count" in view
            assert "density" in view
            assert "avg_degree" in view
            assert view["node_count"] > 0
            assert view["edge_count"] > 0

    def test_density_between_0_and_1(self):
        result = self.mg.multi_perspective_analysis()
        for view in result["perspectives"].values():
            assert 0 <= view["density"] <= 1

    def test_cross_perspective_nodes_exist(self):
        """Nodes connected by multiple relation types should appear in cross list."""
        result = self.mg.multi_perspective_analysis()
        cross = result["cross_perspective_nodes"]
        assert len(cross) > 0

        # Node C is connected by causes (B→C), similar_to (C→D), depends_on (A→C)
        cross_ids = [n["node_id"] for n in cross]
        # At least some nodes appear in multiple perspectives
        assert any(n["perspective_count"] >= 2 for n in cross)

    def test_cross_nodes_sorted_by_perspective_count(self):
        result = self.mg.multi_perspective_analysis()
        cross = result["cross_perspective_nodes"]
        counts = [n["perspective_count"] for n in cross]
        assert counts == sorted(counts, reverse=True)

    def test_with_focal_node(self):
        """With node_id, perspectives should include traversal data."""
        result = self.mg.multi_perspective_analysis(node_id=self.a.id)
        for view in result["perspectives"].values():
            if "traversal" in view:
                t = view["traversal"]
                assert "reachable" in t
                assert "max_depth_reached" in t
                assert "top_nodes" in t

    def test_empty_graph_returns_empty_result(self):
        mg = MemoryGraph()
        result = mg.multi_perspective_analysis()
        assert result["total_relations"] == 0
        assert result["perspectives"] == {}
        assert result["dominant_relation"] is None
        assert result["cross_perspective_nodes"] == []

    def test_single_relation_type(self):
        """Graph with only one relation type should have one perspective."""
        mg = MemoryGraph()
        n1 = mg.add("A")
        n2 = mg.add("B")
        mg.link(n1.id, n2.id, "causes")

        result = mg.multi_perspective_analysis()
        assert result["total_relations"] == 1
        assert result["dominant_relation"] == "causes"
        assert len(result["cross_perspective_nodes"]) == 0  # only 1 perspective

    def test_node_not_in_any_edge(self):
        """Isolated node should not appear in any perspective."""
        mg = MemoryGraph()
        n1 = mg.add("Connected")
        n2 = mg.add("Also Connected")
        mg.add("Lonely")  # no edges
        mg.link(n1.id, n2.id, "causes")

        result = mg.multi_perspective_analysis()
        cross_ids = [n["node_id"] for n in result["cross_perspective_nodes"]]
        # Lonely node should not appear
        lonely = mg.search_by_label("Lonely")[0]
        assert lonely.id not in cross_ids

    def test_avg_degree_correctness(self):
        """avg_degree should be 2*edges/nodes for undirected approximation."""
        mg = MemoryGraph()
        n1 = mg.add("N1")
        n2 = mg.add("N2")
        n3 = mg.add("N3")
        mg.link(n1.id, n2.id, "causes")
        mg.link(n1.id, n3.id, "causes")

        result = mg.multi_perspective_analysis()
        view = result["perspectives"]["causes"]
        # 2 edges, 3 nodes → avg_degree = 2*2/3 ≈ 1.33
        assert abs(view["avg_degree"] - 1.33) < 0.1

    def test_density_single_edge(self):
        """Two nodes, one edge → density = 1.0."""
        mg = MemoryGraph()
        n1 = mg.add("A")
        n2 = mg.add("B")
        mg.link(n1.id, n2.id, "causes")

        result = mg.multi_perspective_analysis()
        view = result["perspectives"]["causes"]
        assert view["density"] == 1.0

    def test_focal_node_not_in_all_perspectives(self):
        """Focal node may not exist in all relation projections."""
        mg = MemoryGraph()
        n1 = mg.add("In All")
        n2 = mg.add("In Causes")
        n3 = mg.add("In Similar")
        mg.link(n1.id, n2.id, "causes")
        mg.link(n1.id, n3.id, "similar_to")

        result = mg.multi_perspective_analysis(node_id=n1.id)
        # n1 is in both perspectives
        for view in result["perspectives"].values():
            assert "traversal" in view

    def test_large_graph_performance(self):
        """Should handle larger graphs without performance issues."""
        mg = MemoryGraph()
        for i in range(50):
            mg.add(f"Node{i}")
        nodes = [r["id"] for r in mg.conn.execute("SELECT id FROM nodes").fetchall()]
        for i in range(49):
            mg.link(nodes[i], nodes[i + 1], "causes")
        for i in range(0, 49, 2):
            mg.link(nodes[i], nodes[i + 1], "similar_to")

        result = mg.multi_perspective_analysis()
        assert result["total_relations"] == 2
        assert len(result["cross_perspective_nodes"]) > 0

    def test_perspectives_keyed_by_relation_name(self):
        result = self.mg.multi_perspective_analysis()
        for key in result["perspectives"]:
            assert isinstance(key, str)
            assert key in ("causes", "similar_to", "depends_on")
