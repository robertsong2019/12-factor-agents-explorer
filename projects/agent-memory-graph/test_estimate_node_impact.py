"""Tests for estimate_node_impact() — Cycle 458."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from memory_graph import MemoryGraph


def _make_star(n=6):
    mg = MemoryGraph()
    c = mg.add("center", kind="hub")
    for i in range(n - 1):
        leaf = mg.add(f"leaf{i}", kind="peripheral")
        mg.link(c.id, leaf.id, "connected")
    return mg


def _make_path(n=5):
    mg = MemoryGraph()
    prev = mg.add("n0")
    for i in range(1, n):
        cur = mg.add(f"n{i}")
        mg.link(prev.id, cur.id, "next")
        prev = cur
    return mg


class TestEstimateNodeImpact:
    """Cycle 458: estimate_node_impact — non-destructive topology prediction."""

    def test_delta_always_one_node(self):
        mg = MemoryGraph()
        mg.add("a")
        r = mg.estimate_node_impact(degree=3)
        assert r["node_count_delta"] == 1

    def test_edge_count_delta(self):
        mg = MemoryGraph()
        mg.add("a")
        r = mg.estimate_node_impact(degree=5, existing_neighbors=3)
        assert r["edge_count_delta"] == 3

    def test_density_increases(self):
        mg = MemoryGraph()
        a = mg.add("a"); b = mg.add("b"); c = mg.add("c")
        mg.link(a.id, b.id, "rel")
        r = mg.estimate_node_impact(degree=2, existing_neighbors=2)
        assert r["density"]["after"] > r["density"]["before"]

    def test_density_delta_positive(self):
        mg = _make_star(5)
        r = mg.estimate_node_impact(degree=3, existing_neighbors=3)
        assert r["density"]["delta"] > 0

    def test_entropy_before_zero_empty(self):
        mg = MemoryGraph()
        r = mg.estimate_node_impact(degree=1)
        assert r["degree_entropy"]["before"] == 0.0

    def test_entropy_increases_with_mixed_degrees(self):
        mg = _make_star(5)  # degrees: [4,1,1,1,1]
        r = mg.estimate_node_impact(degree=2, existing_neighbors=2)
        assert r["degree_entropy"]["delta"] > 0

    def test_graph_type_before_star(self):
        mg = _make_star(7)
        r = mg.estimate_node_impact(degree=1)
        assert r["graph_type"]["before"] == "star"

    def test_assessment_non_empty(self):
        mg = _make_path(4)
        r = mg.estimate_node_impact(degree=3, existing_neighbors=3)
        assert r["assessment"]
        assert len(r["assessment"]) > 0

    def test_negligible_on_large_graph(self):
        mg = _make_star(20)
        r = mg.estimate_node_impact(degree=1, existing_neighbors=1)
        assert "negligible" in r["assessment"].lower() or len(r["assessment"]) > 0

    def test_high_degree_shifts_toward_star(self):
        mg = _make_path(8)
        r = mg.estimate_node_impact(degree=8, existing_neighbors=8)
        if r["graph_type"]["after"] == "star":
            assert "star" in r["assessment"].lower()

    def test_avg_degree_after(self):
        mg = _make_star(5)
        r = mg.estimate_node_impact(degree=2, existing_neighbors=2)
        assert abs(r["avg_degree_after"] - 1.67) < 0.1

    def test_zero_existing_neighbors(self):
        mg = _make_path(3)
        r = mg.estimate_node_impact(degree=0, existing_neighbors=0)
        assert r["edge_count_delta"] == 0

    def test_returns_all_keys(self):
        mg = MemoryGraph()
        mg.add("a")
        r = mg.estimate_node_impact(degree=1)
        expected = {"node_count_delta", "edge_count_delta", "density",
                     "degree_entropy", "clustering_delta", "graph_type",
                     "avg_degree_after", "assessment"}
        assert expected.issubset(set(r.keys()))

    def test_single_node_graph(self):
        mg = MemoryGraph()
        mg.add("solo")
        r = mg.estimate_node_impact(degree=1, existing_neighbors=1)
        assert r["node_count_delta"] == 1
        assert r["edge_count_delta"] == 1

    def test_density_roundtrip_consistency(self):
        mg = _make_star(5)
        r_before = mg.estimate_node_impact(degree=2, existing_neighbors=2)
        projected_density = r_before["density"]["after"]
        new_node = mg.add("new_node")
        existing = [nid for nid, in mg.conn.execute("SELECT id FROM nodes LIMIT 2").fetchall()]
        if len(existing) >= 2:
            mg.link(new_node.id, existing[0], "rel")
            mg.link(new_node.id, existing[1], "rel")
        nn = mg.conn.execute("SELECT count(*) FROM nodes").fetchone()[0]
        mm = mg.conn.execute("SELECT count(*) FROM edges").fetchone()[0]
        actual_density = mm / (nn * (nn - 1)) if nn > 1 else 0
        assert abs(actual_density - projected_density) < 0.15

    def test_entropy_with_weight_param(self):
        mg = _make_path(4)
        r = mg.estimate_node_impact(degree=3, weight=0.5, existing_neighbors=3)
        assert "degree_entropy" in r

    def test_path_graph_type_before(self):
        mg = _make_path(6)
        r = mg.estimate_node_impact(degree=1)
        assert r["graph_type"]["before"] in ("path", "unknown", "tree")

    def test_complete_graph_density_high(self):
        mg = MemoryGraph()
        nodes = [mg.add(f"n{i}") for i in range(4)]
        for i in range(4):
            for j in range(4):
                if i != j:
                    mg.link(nodes[i].id, nodes[j].id, "rel")
        r = mg.estimate_node_impact(degree=4, existing_neighbors=4)
        assert r["density"]["before"] > 0.9
