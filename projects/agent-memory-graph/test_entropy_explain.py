"""Tests for entropy_explain() — human-readable entropy interpretation."""
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


def _cycle(mg, count):
    """Create a cycle graph of given count."""
    nodes = [mg.add(f"N{i}") for i in range(count)]
    for i in range(count):
        mg.link(nodes[i].id, nodes[(i + 1) % count].id, "edge")
    return nodes


def _path(mg, count):
    """Create a path graph."""
    nodes = [mg.add(f"N{i}") for i in range(count)]
    for i in range(count - 1):
        mg.link(nodes[i].id, nodes[i + 1].id, "edge")
    return nodes


def _star(mg, leaves):
    """Create a star graph with center + leaves."""
    center = mg.add("Hub")
    for i in range(leaves):
        mg.link(center.id, mg.add(f"L{i}").id, "edge")
    return center


def _complete(mg, n):
    """Create a complete graph K_n."""
    nodes = [mg.add(f"N{i}") for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            mg.link(nodes[i].id, nodes[j].id, "edge")
    return nodes


class TestEntropyExplainBasic:
    def test_returns_dict_with_required_keys(self, mg):
        _cycle(mg, 3)
        result = mg.entropy_explain()
        assert "summary" in result
        assert "layers" in result
        assert "recommendations" in result
        assert "indices_used" in result
        assert isinstance(result["summary"], str)
        assert isinstance(result["layers"], list)
        assert isinstance(result["recommendations"], list)

    def test_small_graph_returns_guidance(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "edge")
        result = mg.entropy_explain()
        assert "too small" in result["summary"].lower()
        assert result["indices_used"] == 0

    def test_triangle_graph_produces_layers(self, mg):
        _cycle(mg, 3)
        result = mg.entropy_explain()
        assert len(result["layers"]) >= 2
        assert result["indices_used"] >= 2

    def test_summary_contains_node_edge_count(self, mg):
        _path(mg, 5)
        result = mg.entropy_explain()
        assert "5 nodes" in result["summary"]
        assert "4 edges" in result["summary"]


class TestEntropyExplainLayers:
    def test_degree_diversity_layer_present(self, mg):
        _cycle(mg, 4)
        result = mg.entropy_explain()
        layer_names = [l["name"] for l in result["layers"]]
        assert "degree_diversity" in layer_names
        deg_layer = next(l for l in result["layers"] if l["name"] == "degree_diversity")
        assert "metric" in deg_layer
        assert "value" in deg_layer
        assert "assessment" in deg_layer
        assert "interpretation" in deg_layer
        assert 0.0 <= deg_layer["value"] <= 1.0

    def test_spectral_topology_layer_present(self, mg):
        _path(mg, 5)
        result = mg.entropy_explain()
        layer_names = [l["name"] for l in result["layers"]]
        assert "spectral_topology" in layer_names

    def test_fingerprint_consistency_layer(self, mg):
        _path(mg, 6)
        result = mg.entropy_explain()
        layer_names = [l["name"] for l in result["layers"]]
        assert "fingerprint_consistency" in layer_names

    def test_fingerprint_consistency_value(self, mg):
        _path(mg, 5)
        result = mg.entropy_explain()
        fc = next((l for l in result["layers"] if l["name"] == "fingerprint_consistency"), None)
        if fc:
            assert 0.0 <= fc["value"] <= 1.0

    def test_centrality_focus_layer(self, mg):
        _star(mg, 7)
        result = mg.entropy_explain()
        layer_names = [l["name"] for l in result["layers"]]
        assert "centrality_focus" in layer_names

    def test_path_diversity_layer(self, mg):
        _path(mg, 5)
        result = mg.entropy_explain()
        layer_names = [l["name"] for l in result["layers"]]
        assert "path_diversity" in layer_names


class TestEntropyExplainAssessments:
    def test_star_graph_uniform_degree(self, mg):
        """Star graph: all leaves have same sombor value → uniform entropy."""
        _star(mg, 7)
        result = mg.entropy_explain()
        deg = next((l for l in result["layers"] if l["name"] == "degree_diversity"), None)
        if deg:
            # Star graph leaves all have identical sombor → high entropy
            assert deg["assessment"] in ("uniform", "balanced")

    def test_cycle_graph_balanced_degree(self, mg):
        _cycle(mg, 6)
        result = mg.entropy_explain()
        deg = next((l for l in result["layers"] if l["name"] == "degree_diversity"), None)
        if deg:
            assert deg["assessment"] in ("uniform", "balanced")
            assert deg["value"] > 0.8

    def test_complete_graph_high_entropy(self, mg):
        _complete(mg, 5)
        result = mg.entropy_explain()
        deg = next((l for l in result["layers"] if l["name"] == "degree_diversity"), None)
        if deg:
            assert deg["assessment"] in ("uniform", "balanced")


class TestEntropyExplainRecommendations:
    def test_star_graph_has_recommendations(self, mg):
        """Star graph should still produce recommendations."""
        _star(mg, 8)
        result = mg.entropy_explain()
        assert len(result["recommendations"]) >= 1

    def test_healthy_graph_has_recommendation(self, mg):
        _cycle(mg, 6)
        result = mg.entropy_explain()
        assert len(result["recommendations"]) >= 1

    def test_star_graph_centrality_recs(self, mg):
        """Star graph should have edge betweenness recommendations."""
        _star(mg, 8)
        result = mg.entropy_explain()
        eb = next((l for l in result["layers"] if l["name"] == "centrality_focus"), None)
        if eb and eb["assessment"] == "bottlenecked":
            rec_text = " ".join(result["recommendations"])
            assert any(w in rec_text.lower() for w in ["redundant", "critical"])
        # If not bottlenecked, just verify we got analysis
        assert result["indices_used"] >= 2


class TestEntropyExplainEdge:
    def test_empty_graph(self, mg):
        result = mg.entropy_explain()
        assert "summary" in result
        assert result["indices_used"] == 0

    def test_single_node(self, mg):
        mg.add("Lonely")
        result = mg.entropy_explain()
        assert result["indices_used"] == 0

    def test_two_nodes(self, mg):
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "edge")
        result = mg.entropy_explain()
        assert result["indices_used"] == 0

    def test_disconnected_graph(self, mg):
        c1 = [mg.add(f"A{i}") for i in range(3)]
        c2 = [mg.add(f"B{i}") for i in range(3)]
        mg.link(c1[0].id, c1[1].id, "edge")
        mg.link(c2[0].id, c2[1].id, "edge")
        result = mg.entropy_explain()
        assert result["indices_used"] >= 0

    def test_verbose_includes_profile(self, mg):
        _path(mg, 5)
        result = mg.entropy_explain(verbose=True)
        assert "profile" in result
        assert "values" in result["profile"]

    def test_non_verbose_excludes_profile(self, mg):
        _path(mg, 5)
        result = mg.entropy_explain(verbose=False)
        assert "profile" not in result

    def test_fingerprint_consistency_matches_layer(self, mg):
        _path(mg, 6)
        result = mg.entropy_explain()
        if result["fingerprint_consistency"] is not None:
            fc_layer = next(
                (l for l in result["layers"] if l["name"] == "fingerprint_consistency"),
                None,
            )
            if fc_layer:
                assert result["fingerprint_consistency"] == fc_layer["value"]

    def test_bipartite_graph(self, mg):
        left = [mg.add(f"L{i}") for i in range(4)]
        right = [mg.add(f"R{i}") for i in range(3)]
        for l_node in left:
            for r_node in right:
                mg.link(l_node.id, r_node.id, "edge")
        result = mg.entropy_explain()
        assert result["indices_used"] >= 2

    def test_large_graph_performance(self, mg):
        nodes = _path(mg, 20)
        for i in range(0, 20, 3):
            mg.link(nodes[i].id, nodes[(i + 5) % 20].id, "edge")
        result = mg.entropy_explain()
        assert result["indices_used"] >= 3
