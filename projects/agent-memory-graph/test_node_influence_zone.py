"""Tests for node_influence_zone() — Cycle 388.

K-hop influence zone with per-layer entropy and density statistics.
"""
import pytest
from memory_graph import MemoryGraph


def _build_star(n=6):
    g = MemoryGraph()
    ids = []
    for i in range(n):
        g.add(f"n{i}", kind="concept")
    ids = [str(r["id"]) for r in g.conn.execute("SELECT id FROM nodes ORDER BY label").fetchall()]
    for i in range(1, n):
        g.link(ids[0], ids[i], "related")
    return g, ids


def _build_path(n=6):
    g = MemoryGraph()
    for i in range(n):
        g.add(f"n{i}", kind="concept")
    ids = [str(r["id"]) for r in g.conn.execute("SELECT id FROM nodes ORDER BY label").fetchall()]
    for i in range(n - 1):
        g.link(ids[i], ids[i + 1], "related")
    return g, ids


def _build_cycle(n=6):
    g = MemoryGraph()
    for i in range(n):
        g.add(f"n{i}", kind="concept")
    ids = [str(r["id"]) for r in g.conn.execute("SELECT id FROM nodes ORDER BY label").fetchall()]
    for i in range(n):
        g.link(ids[i], ids[(i + 1) % n], "related")
    return g, ids


def _build_two_clusters():
    """Two clusters connected by a bridge edge."""
    g = MemoryGraph()
    for i in range(8):
        g.add(f"n{i}", kind="concept")
    ids = [str(r["id"]) for r in g.conn.execute("SELECT id FROM nodes ORDER BY label").fetchall()]
    # Cluster A: n0-n1, n0-n2, n1-n2
    g.link(ids[0], ids[1], "related")
    g.link(ids[0], ids[2], "related")
    g.link(ids[1], ids[2], "related")
    # Cluster B: n4-n5, n4-n6, n5-n6
    g.link(ids[4], ids[5], "related")
    g.link(ids[4], ids[6], "related")
    g.link(ids[5], ids[6], "related")
    # Bridge: n2-n4
    g.link(ids[2], ids[4], "related")
    return g, ids


class TestNodeInfluenceZoneBasic:
    """Basic structure tests."""

    def test_returns_dict(self):
        g, ids = _build_star()
        result = g.node_influence_zone(ids[0])
        assert isinstance(result, dict)

    def test_keys_present(self):
        g, ids = _build_star()
        result = g.node_influence_zone(ids[0])
        expected = {"node_id", "max_radius", "layers", "total_reach",
                    "influence_score", "influence_radius", "summary"}
        assert expected.issubset(result.keys())

    def test_nonexistent_node(self):
        g = MemoryGraph()
        assert g.node_influence_zone("nonexistent") is None

    def test_summary_is_string(self):
        g, ids = _build_star()
        result = g.node_influence_zone(ids[0])
        assert isinstance(result["summary"], str)
        assert "Influence zone" in result["summary"]


class TestNodeInfluenceZoneStar:
    """Star topology tests."""

    def test_star_center_reaches_all(self):
        g, ids = _build_star(n=6)
        result = g.node_influence_zone(ids[0], max_radius=3)
        assert result["total_reach"] == 6  # center + 5 leaves
        assert result["influence_radius"] >= 1

    def test_star_center_one_hop(self):
        """Star center reaches all in 1 hop."""
        g, ids = _build_star(n=6)
        result = g.node_influence_zone(ids[0], max_radius=3)
        assert len(result["layers"]) >= 1
        assert result["layers"][0]["frontier_nodes"] == 5
        assert result["layers"][0]["cumulative_nodes"] == 6

    def test_star_leaf_two_hops(self):
        """Star leaf reaches center (1 hop), then other leaves (2 hops)."""
        g, ids = _build_star(n=6)
        result = g.node_influence_zone(ids[1], max_radius=3)
        assert result["total_reach"] == 6
        assert result["influence_radius"] == 2

    def test_star_leaf_layer_counts(self):
        """Leaf: 1 hop → center, 2 hops → 4 other leaves."""
        g, ids = _build_star(n=6)
        result = g.node_influence_zone(ids[1], max_radius=3)
        assert result["layers"][0]["frontier_nodes"] == 1  # center
        assert result["layers"][1]["frontier_nodes"] == 4  # other leaves


class TestNodeInfluenceZonePath:
    """Path topology tests."""

    def test_path_endpoint(self):
        g, ids = _build_path(n=6)
        result = g.node_influence_zone(ids[0], max_radius=5)
        assert result["total_reach"] == 6
        assert result["influence_radius"] == 5

    def test_path_endpoint_layer_progression(self):
        """Path endpoint: each layer adds exactly 1 node."""
        g, ids = _build_path(n=6)
        result = g.node_influence_zone(ids[0], max_radius=5)
        for i, layer in enumerate(result["layers"]):
            assert layer["frontier_nodes"] == 1
            assert layer["cumulative_nodes"] == i + 2  # start + i+1 new

    def test_path_center_reaches_fewer_hops(self):
        """Path center: reaches all within 3 hops."""
        g, ids = _build_path(n=7)
        result = g.node_influence_zone(ids[3], max_radius=5)
        assert result["total_reach"] == 7
        assert result["influence_radius"] == 3

    def test_path_influence_score(self):
        """Closer nodes weighted higher → influence score < total_reach."""
        g, ids = _build_path(n=6)
        result = g.node_influence_zone(ids[0], max_radius=5)
        # influence_score = sum(n_layer / (depth+1)) < total_reach
        assert result["influence_score"] < result["total_reach"]


class TestNodeInfluenceZoneCycle:
    """Cycle topology tests."""

    def test_cycle_reaches_all(self):
        g, ids = _build_cycle(n=6)
        result = g.node_influence_zone(ids[0], max_radius=5)
        assert result["total_reach"] == 6

    def test_cycle_symmetric(self):
        """In a cycle, all nodes have same influence score."""
        g, ids = _build_cycle(n=6)
        r0 = g.node_influence_zone(ids[0], max_radius=3)
        r1 = g.node_influence_zone(ids[3], max_radius=3)
        assert r0["influence_score"] == pytest.approx(r1["influence_score"], abs=1e-6)


class TestNodeInfluenceZoneClusters:
    """Two-cluster bridge topology."""

    def test_bridge_reaches_both(self):
        g, ids = _build_two_clusters()
        # n2 is the bridge node in cluster A; reaches n0,n1,n2,n4,n5,n6 = 6
        result = g.node_influence_zone(ids[2], max_radius=3)
        assert result["total_reach"] == 6  # connected nodes only (n3,n7 isolated)

    def test_cluster_member_stays_local_first(self):
        g, ids = _build_two_clusters()
        # n0 in cluster A
        result = g.node_influence_zone(ids[0], max_radius=1)
        # Layer 1: n1, n2
        assert result["layers"][0]["frontier_nodes"] == 2


class TestNodeInfluenceZoneLayerStats:
    """Per-layer statistics tests."""

    def test_layer_keys(self):
        g, ids = _build_star(n=6)
        result = g.node_influence_zone(ids[0])
        for layer in result["layers"]:
            assert "depth" in layer
            assert "frontier_nodes" in layer
            assert "cumulative_nodes" in layer
            assert "layer_mean_entropy" in layer
            assert "subgraph_density" in layer
            assert "layer_influence" in layer

    def test_density_decreases_or_stable(self):
        """As we expand, density typically decreases."""
        g, ids = _build_path(n=8)
        result = g.node_influence_zone(ids[0], max_radius=7)
        densities = [l["subgraph_density"] for l in result["layers"]]
        # Density should be non-increasing as we add sparse frontier
        for i in range(1, len(densities)):
            assert densities[i] <= densities[i - 1] + 0.01  # tolerance

    def test_layer_influence_decreasing(self):
        """Layers further out have lower per-node influence."""
        g, ids = _build_path(n=8)
        result = g.node_influence_zone(ids[0], max_radius=5)
        for i in range(1, len(result["layers"])):
            assert result["layers"][i]["layer_influence"] <= result["layers"][i - 1]["layer_influence"] + 0.01


class TestNodeInfluenceZoneEdgeCases:
    """Edge cases."""

    def test_isolated_node(self):
        g = MemoryGraph()
        g.add("lonely", kind="concept")
        nid = str(g.conn.execute("SELECT id FROM nodes WHERE label=?", ("lonely",)).fetchone()["id"])
        result = g.node_influence_zone(nid, max_radius=3)
        assert result["total_reach"] == 1
        assert result["influence_radius"] == 0
        assert len(result["layers"]) == 0

    def test_max_radius_1(self):
        g, ids = _build_star(n=6)
        result = g.node_influence_zone(ids[0], max_radius=1)
        assert result["influence_radius"] == 1
        assert len(result["layers"]) == 1

    def test_max_radius_exceeds_graph(self):
        """max_radius larger than graph diameter."""
        g, ids = _build_star(n=4)
        result = g.node_influence_zone(ids[0], max_radius=10)
        # Should stop at actual diameter (1 for star center)
        assert result["influence_radius"] == 1

    def test_different_indices(self):
        g, ids = _build_path(n=6)
        r_sombor = g.node_influence_zone(ids[0], index="sombor")
        r_randic = g.node_influence_zone(ids[0], index="randic")
        assert r_sombor is not None
        assert r_randic is not None
        # Both should reach the same nodes
        assert r_sombor["total_reach"] == r_randic["total_reach"]
