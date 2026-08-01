"""Tests for entropy_depth_profile() — Cycle 341.

BFS-layer entropy profile: expands from a seed node, computing
Shannon + Rényi₂ entropy at each induced subgraph layer.
"""
import math
import pytest
from memory_graph import MemoryGraph


def _star(n):
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(1, n):
        mg.link(nodes[0].id, nodes[i].id, "r")
    return mg, nodes


def _complete(n):
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            mg.link(nodes[i].id, nodes[j].id, "r")
    return mg, nodes


def _path(n):
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        mg.link(nodes[i].id, nodes[i + 1].id, "r")
    return mg, nodes


def _cycle(n):
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(n):
        mg.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return mg, nodes


def _binary_tree(depth):
    mg = MemoryGraph(":memory:")
    n = 2 ** depth - 1
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(n):
        left = 2 * i + 1
        right = 2 * i + 2
        if left < n:
            mg.link(nodes[i].id, nodes[left].id, "r")
        if right < n:
            mg.link(nodes[i].id, nodes[right].id, "r")
    return mg, nodes


# ── Basic structure ──

class TestDepthProfileBasic:
    def test_returns_list(self):
        mg, nodes = _path(5)
        result = mg.entropy_depth_profile(nodes[0].id)
        assert isinstance(result, list)

    def test_none_for_nonexistent_node(self):
        mg, _ = _path(5)
        assert mg.entropy_depth_profile("nonexistent") is None

    def test_none_for_no_edges(self):
        mg = MemoryGraph(":memory:")
        n = mg.add("a")
        assert mg.entropy_depth_profile(n.id) is None

    def test_layer_zero_is_seed(self):
        mg, nodes = _path(5)
        profile = mg.entropy_depth_profile(nodes[0].id)
        assert profile[0]["depth"] == 0
        assert profile[0]["frontier_count"] == 1
        assert profile[0]["cumulative_nodes"] == 1

    def test_profile_keys(self):
        mg, nodes = _path(5)
        entry = mg.entropy_depth_profile(nodes[0].id)[0]
        for key in ["depth", "frontier_nodes", "frontier_count",
                     "cumulative_nodes", "induced_edges",
                     "shannon", "renyi_2", "growth_ratio"]:
            assert key in entry

    def test_depth_starts_at_zero(self):
        mg, nodes = _star(6)
        profile = mg.entropy_depth_profile(nodes[0].id)
        assert profile[0]["depth"] == 0

    def test_profile_length_bounded_by_max_depth(self):
        mg, nodes = _path(10)
        profile = mg.entropy_depth_profile(nodes[0].id, max_depth=3)
        assert len(profile) <= 4


# ── BFS expansion ──

class TestBFSExpansion:
    def test_path_expands_one_per_layer(self):
        mg, nodes = _path(5)
        profile = mg.entropy_depth_profile(nodes[0].id)
        for i in range(1, len(profile)):
            assert profile[i]["frontier_count"] == 1

    def test_star_center_two_layers(self):
        mg, nodes = _star(6)
        profile = mg.entropy_depth_profile(nodes[0].id)
        assert len(profile) == 2
        assert profile[1]["frontier_count"] == 5

    def test_star_leaf_three_layers(self):
        mg, nodes = _star(6)
        profile = mg.entropy_depth_profile(nodes[1].id)  # leaf
        assert len(profile) == 3
        assert profile[0]["frontier_count"] == 1
        assert profile[1]["frontier_count"] == 1
        assert profile[2]["frontier_count"] == 4

    def test_cumulative_nodes_grows(self):
        mg, nodes = _complete(6)
        profile = mg.entropy_depth_profile(nodes[0].id)
        for i in range(1, len(profile)):
            assert profile[i]["cumulative_nodes"] >= profile[i - 1]["cumulative_nodes"]

    def test_complete_graph_two_layers(self):
        mg, nodes = _complete(6)
        profile = mg.entropy_depth_profile(nodes[0].id)
        assert len(profile) == 2
        assert profile[1]["frontier_count"] == 5


# ── Entropy values ──

class TestEntropyValues:
    def test_layer_zero_zero_entropy(self):
        mg, nodes = _path(5)
        profile = mg.entropy_depth_profile(nodes[0].id)
        assert profile[0]["shannon"] == 0.0
        assert profile[0]["renyi_2"] == 0.0
        assert profile[0]["induced_edges"] == 0

    def test_shannon_non_negative(self):
        mg, nodes = _path(8)
        profile = mg.entropy_depth_profile(nodes[3].id)
        for entry in profile:
            assert entry["shannon"] >= 0.0

    def test_renyi_2_non_negative(self):
        mg, nodes = _path(8)
        profile = mg.entropy_depth_profile(nodes[3].id)
        for entry in profile:
            assert entry["renyi_2"] >= 0.0

    def test_path_entropy_grows_then_plateaus(self):
        mg, nodes = _path(10)
        profile = mg.entropy_depth_profile(nodes[0].id, max_depth=9)
        shannons = [e["shannon"] for e in profile]
        for i in range(1, len(shannons)):
            assert shannons[i] >= shannons[i - 1] - 1e-10

    def test_induced_edges_grow(self):
        mg, nodes = _path(8)
        profile = mg.entropy_depth_profile(nodes[0].id)
        for i in range(1, len(profile)):
            assert profile[i]["induced_edges"] >= profile[i - 1]["induced_edges"]


# ── Growth ratio ──

class TestGrowthRatio:
    def test_layer_zero_growth_is_one(self):
        mg, nodes = _path(5)
        profile = mg.entropy_depth_profile(nodes[0].id)
        assert profile[0]["growth_ratio"] == 1.0

    def test_star_center_high_growth(self):
        mg, nodes = _star(6)
        profile = mg.entropy_depth_profile(nodes[0].id)
        assert profile[1]["growth_ratio"] == 5.0

    def test_growth_ratio_non_negative(self):
        mg, nodes = _binary_tree(3)
        profile = mg.entropy_depth_profile(nodes[0].id)
        for entry in profile:
            assert entry["growth_ratio"] >= 0.0


# ── Node comparison ──

class TestNodeComparison:
    def test_center_vs_leaf_different_profiles(self):
        mg, nodes = _star(8)
        center = mg.entropy_depth_profile(nodes[0].id)
        leaf = mg.entropy_depth_profile(nodes[1].id)
        assert len(center) != len(leaf) or \
               center[1]["frontier_count"] != leaf[1]["frontier_count"]

    def test_path_middle_reaches_both_ends(self):
        mg, nodes = _path(7)
        profile = mg.entropy_depth_profile(nodes[3].id)
        assert profile[-1]["cumulative_nodes"] == 7

    def test_different_seed_different_profile(self):
        mg, nodes = _binary_tree(3)
        root = mg.entropy_depth_profile(nodes[0].id)
        leaf = mg.entropy_depth_profile(nodes[6].id)
        assert len(root) != len(leaf)


# ── Index parameter ──

class TestIndexParameter:
    @pytest.mark.parametrize("index", [
        "sombor", "reduced_sombor", "randic", "zagreb_m1", "abc", "ga", "augmented_zagreb"
    ])
    def test_index_works(self, index):
        mg, nodes = _path(5)
        result = mg.entropy_depth_profile(nodes[0].id, index=index)
        assert result is not None

    def test_invalid_index_raises(self):
        mg, nodes = _path(5)
        with pytest.raises(ValueError):
            mg.entropy_depth_profile(nodes[0].id, index="nonexistent")


# ── Max depth ──

class TestMaxDepth:
    def test_max_depth_limits_layers(self):
        mg, nodes = _path(10)
        profile = mg.entropy_depth_profile(nodes[0].id, max_depth=2)
        assert len(profile) <= 3

    def test_max_depth_zero(self):
        mg, nodes = _path(5)
        profile = mg.entropy_depth_profile(nodes[0].id, max_depth=0)
        assert len(profile) == 1

    def test_max_depth_exceeds_graph(self):
        mg, nodes = _path(5)
        profile = mg.entropy_depth_profile(nodes[0].id, max_depth=100)
        assert profile[-1]["cumulative_nodes"] == 5


# ── Binary tree ──

class TestBinaryTree:
    def test_root_reaches_all(self):
        mg, nodes = _binary_tree(3)
        profile = mg.entropy_depth_profile(nodes[0].id)
        assert profile[-1]["cumulative_nodes"] == 7

    def test_root_layer_growth(self):
        mg, nodes = _binary_tree(3)
        profile = mg.entropy_depth_profile(nodes[0].id)
        assert profile[0]["frontier_count"] == 1
        assert profile[1]["frontier_count"] == 2
        assert profile[2]["frontier_count"] == 4

    def test_entropy_at_each_layer(self):
        mg, nodes = _binary_tree(4)
        profile = mg.entropy_depth_profile(nodes[0].id)
        assert profile[-1]["shannon"] > profile[1]["shannon"]


# ── Edge cases ──

class TestEdgeCases:
    def test_single_edge(self):
        mg = MemoryGraph(":memory:")
        a = mg.add("a")
        b = mg.add("b")
        mg.link(a.id, b.id, "r")
        profile = mg.entropy_depth_profile(a.id)
        assert len(profile) >= 2
        assert profile[1]["induced_edges"] == 1

    def test_disconnected_graph(self):
        mg = MemoryGraph(":memory:")
        nodes = [mg.add(str(i)) for i in range(6)]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[1].id, nodes[2].id, "r")
        mg.link(nodes[3].id, nodes[4].id, "r")
        mg.link(nodes[4].id, nodes[5].id, "r")
        profile = mg.entropy_depth_profile(nodes[0].id)
        assert profile[-1]["cumulative_nodes"] == 3

    def test_cycle_all_reached(self):
        mg, nodes = _cycle(6)
        profile = mg.entropy_depth_profile(nodes[0].id)
        assert profile[-1]["cumulative_nodes"] == 6
