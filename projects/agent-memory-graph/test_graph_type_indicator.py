"""Tests for graph_type_indicator() — Cycle 315.

Classifies graph topology type (complete, star, path, cycle, tree,
random, scale_free) from structural and entropy metrics.
Pure heuristic — no reference graphs or ML needed.
"""
import pytest
import random
from memory_graph import MemoryGraph


# ── Graph builders ──

def build_complete(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return g


def build_path(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return g


def build_cycle(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return g


def build_star(leaves):
    g = MemoryGraph()
    hub = g.add("hub")
    for i in range(leaves):
        leaf = g.add(f"leaf{i}")
        g.link(hub.id, leaf.id, "r")
    return g


def build_random(n, p=0.3, seed=42):
    random.seed(seed)
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if random.random() < p:
                g.link(nodes[i].id, nodes[j].id, "r")
    return g


def build_scale_free(n, m=3, seed=42):
    """Barabási-Albert preferential attachment."""
    random.seed(seed)
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    # Start with a small complete graph
    for i in range(m + 1):
        for j in range(i + 1, m + 1):
            g.link(nodes[i].id, nodes[j].id, "r")
    # Add remaining nodes with preferential attachment
    degree_count = {nodes[i].id: m for i in range(m + 1)}
    total_degree = m * (m + 1)
    for i in range(m + 1, n):
        new_node = nodes[i].id
        targets = []
        for _ in range(m):
            # Weighted random selection by degree
            r = random.random() * total_degree
            cumulative = 0
            for nid, deg in degree_count.items():
                cumulative += deg
                if r <= cumulative:
                    targets.append(nid)
                    break
        for target in targets:
            g.link(new_node, target, "r")
            degree_count[new_node] = degree_count.get(new_node, 0) + 1
            degree_count[target] = degree_count.get(target, 0) + 1
            total_degree += 2
    return g


def build_tree(n):
    """Random tree via random spanning tree."""
    random.seed(42)
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(1, n):
        parent = random.randint(0, i - 1)
        g.link(nodes[i].id, nodes[parent].id, "r")
    return g


def build_empty():
    return MemoryGraph()


def build_single():
    g = MemoryGraph()
    g.add("solo")
    return g


def build_two():
    g = MemoryGraph()
    a = g.add("A")
    b = g.add("B")
    g.link(a.id, b.id, "r")
    return g


# ── Edge cases ──

class TestGraphTypeEdgeCases:
    def test_empty_returns_none(self):
        assert build_empty().graph_type_indicator() is None

    def test_single_node_returns_none(self):
        assert build_single().graph_type_indicator() is None

    def test_two_nodes_returns_none(self):
        assert build_two().graph_type_indicator() is None


# ── Return structure ──

class TestGraphTypeStructure:
    def test_returns_dict_with_keys(self):
        g = build_complete(5)
        result = g.graph_type_indicator()
        assert "type" in result
        assert "confidence" in result
        assert "scores" in result
        assert "metrics" in result

    def test_scores_sorted_descending(self):
        g = build_star(5)
        result = g.graph_type_indicator()
        scores = list(result["scores"].values())
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_metrics_has_required_keys(self):
        g = build_complete(5)
        result = g.graph_type_indicator()
        metrics = result["metrics"]
        for key in ["nodes", "edges", "density", "degree_mean", "degree_cv",
                     "triangles", "triangle_density", "avg_clustering",
                     "connected", "components"]:
            assert key in metrics

    def test_confidence_in_range(self):
        g = build_path(5)
        result = g.graph_type_indicator()
        assert 0.0 <= result["confidence"] <= 1.0


# ── Classification correctness ──

class TestGraphTypeClassification:
    def test_complete_graph_classified(self):
        g = build_complete(6)
        result = g.graph_type_indicator()
        assert result["type"] == "complete"
        assert result["confidence"] > 0.5

    def test_star_graph_classified(self):
        g = build_star(5)
        result = g.graph_type_indicator()
        assert result["type"] == "star"
        assert result["scores"]["star"] > 0.8

    def test_path_graph_classified(self):
        g = build_path(6)
        result = g.graph_type_indicator()
        assert result["type"] in ("path", "tree")  # path is a special tree

    def test_cycle_graph_classified(self):
        g = build_cycle(6)
        result = g.graph_type_indicator()
        assert result["type"] == "cycle"
        assert result["scores"]["cycle"] > 0.5

    def test_tree_graph_classified(self):
        g = build_tree(10)
        result = g.graph_type_indicator()
        assert result["type"] in ("tree", "path", "star")

    def test_scale_free_classified(self):
        g = build_scale_free(30, m=2)
        result = g.graph_type_indicator()
        # Scale-free should at least score somewhat
        assert result["scores"].get("scale_free", 0) > 0.05

    def test_random_graph_scores(self):
        g = build_random(15, p=0.3)
        result = g.graph_type_indicator()
        # Random should have positive score
        assert result["scores"].get("random", 0) > 0.0


# ── Metrics correctness ──

class TestGraphTypeMetrics:
    def test_complete_metrics(self):
        g = build_complete(5)
        result = g.graph_type_indicator()
        m = result["metrics"]
        assert m["nodes"] == 5
        assert m["edges"] == 10  # K5 has 10 edges
        assert m["density"] == pytest.approx(1.0, abs=0.01)
        assert m["degree_cv"] == pytest.approx(0.0, abs=0.01)  # uniform degree
        assert m["connected"] is True
        assert m["components"] == 1

    def test_star_metrics(self):
        g = build_star(4)
        result = g.graph_type_indicator()
        m = result["metrics"]
        assert m["nodes"] == 5  # hub + 4 leaves
        assert m["edges"] == 4
        assert m["connected"] is True

    def test_path_metrics(self):
        g = build_path(5)
        result = g.graph_type_indicator()
        m = result["metrics"]
        assert m["nodes"] == 5
        assert m["edges"] == 4
        assert m["connected"] is True
        assert m["degree_cv"] > 0.0  # some degree variance

    def test_disconnected_components(self):
        g = MemoryGraph()
        a = g.add("A")
        b = g.add("B")
        c = g.add("C")
        d = g.add("D")
        g.link(a.id, b.id, "r")
        g.link(c.id, d.id, "r")
        result = g.graph_type_indicator()
        assert result["metrics"]["components"] == 2
        assert result["metrics"]["connected"] is False

    def test_triangle_count_complete(self):
        g = build_complete(4)
        result = g.graph_type_indicator()
        # K4 has C(4,3) = 4 triangles
        assert result["metrics"]["triangles"] == 4
        assert result["metrics"]["triangle_density"] == pytest.approx(1.0, abs=0.01)

    def test_triangle_count_path(self):
        g = build_path(5)
        result = g.graph_type_indicator()
        assert result["metrics"]["triangles"] == 0
        assert result["metrics"]["triangle_density"] == 0.0


# ── Clustering coefficient ──

class TestGraphTypeClustering:
    def test_complete_max_clustering(self):
        g = build_complete(5)
        result = g.graph_type_indicator()
        assert result["metrics"]["avg_clustering"] == pytest.approx(1.0, abs=0.01)

    def test_path_zero_clustering(self):
        g = build_path(5)
        result = g.graph_type_indicator()
        # Path has no inter-neighbor edges → clustering = 0
        assert result["metrics"]["avg_clustering"] == pytest.approx(0.0, abs=0.01)

    def test_star_zero_clustering(self):
        g = build_star(4)
        result = g.graph_type_indicator()
        # Leaves' neighbors (just the hub) have no inter-connections
        # Hub's neighbors (leaves) have no inter-connections
        assert result["metrics"]["avg_clustering"] == pytest.approx(0.0, abs=0.01)


# ── Robustness ──

class TestGraphTypeRobustness:
    def test_repeated_call_same_result(self):
        g = build_complete(5)
        r1 = g.graph_type_indicator()
        r2 = g.graph_type_indicator()
        assert r1["type"] == r2["type"]
        assert r1["scores"] == r2["scores"]

    def test_large_complete(self):
        g = build_complete(10)
        result = g.graph_type_indicator()
        assert result["type"] == "complete"
        assert result["confidence"] > 0.5

    def test_large_star(self):
        g = build_star(10)
        result = g.graph_type_indicator()
        assert result["type"] == "star"

    def test_large_path(self):
        g = build_path(10)
        result = g.graph_type_indicator()
        assert result["type"] in ("path", "tree")


# ── Disambiguation ──

class TestGraphTypeDisambiguation:
    def test_complete_vs_cycle(self):
        """K3 and C3 are the same graph, but K4 ≠ C4."""
        k4 = build_complete(4)
        c4 = build_cycle(4)
        r_k4 = k4.graph_type_indicator()
        r_c4 = c4.graph_type_indicator()
        assert r_k4["type"] == "complete"
        assert r_c4["type"] == "cycle"

    def test_path_vs_star(self):
        """P5 should be path/tree, not star."""
        path = build_path(5)
        star = build_star(4)
        r_path = path.graph_type_indicator()
        r_star = star.graph_type_indicator()
        assert r_path["type"] != r_star["type"]

    def test_star_score_higher_than_path(self):
        star = build_star(5)
        r = star.graph_type_indicator()
        assert r["scores"]["star"] > r["scores"]["path"]
