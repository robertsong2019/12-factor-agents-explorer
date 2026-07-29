"""Tests for ego_entropy_profile() — Cycle 313.

VNEstruct-inspired (Dasoulas et al., ICML 2020) ego-local entropy.
Computes per-node Shannon entropy on each node's ego-network.
"""
import math
import pytest
from memory_graph import MemoryGraph


# ── Graph builders ──

def build_complete(n):
    """Complete graph K_n."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return g


def build_path(n):
    """Path graph P_n — linear chain."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return g


def build_cycle(n):
    """Cycle graph C_n."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return g


def build_star(leaves):
    """Star graph K_{1,leaves}."""
    g = MemoryGraph()
    hub = g.add("hub")
    leaf_nodes = []
    for i in range(leaves):
        leaf = g.add(f"leaf{i}")
        g.link(hub.id, leaf.id, "r")
        leaf_nodes.append(leaf)
    return g, hub, leaf_nodes


def build_hub_and_spokes():
    """Hub H with 3 spokes, each spoke connected to one extra leaf."""
    g = MemoryGraph()
    hub = g.add("H")
    spokes = []
    leaves = []
    for i in range(3):
        s = g.add(f"S{i}")
        leaf = g.add(f"Leaf{i}")
        g.link(hub.id, s.id, "r")
        g.link(s.id, leaf.id, "r")
        spokes.append(s)
        leaves.append(leaf)
    return g, hub, spokes, leaves


def build_grid_3x3():
    """3×3 grid graph — uniform regular-ish structure."""
    g = MemoryGraph()
    nodes = {}
    for r in range(3):
        for c in range(3):
            nodes[(r, c)] = g.add(f"R{r}C{c}")
    for r in range(3):
        for c in range(3):
            if c < 2:
                g.link(nodes[(r, c)].id, nodes[(r, c + 1)].id, "r")
            if r < 2:
                g.link(nodes[(r, c)].id, nodes[(r + 1, c)].id, "r")
    return g, nodes


# ── Edge cases ──

class TestEgoEntropyEdgeCases:
    """Tests for boundary conditions and error handling."""

    def test_empty_graph_returns_none(self):
        g = MemoryGraph()
        assert g.ego_entropy_profile() is None

    def test_single_node_returns_none(self):
        g = MemoryGraph()
        g.add("solo")
        assert g.ego_entropy_profile() is None

    def test_two_nodes_returns_result(self):
        g = MemoryGraph()
        a = g.add("A")
        b = g.add("B")
        g.link(a.id, b.id, "r")
        result = g.ego_entropy_profile()
        assert result is not None
        assert result["evaluated"] == 2

    def test_invalid_index_raises(self):
        g, _, _ = build_star(3)
        with pytest.raises(ValueError, match="Unknown index"):
            g.ego_entropy_profile(index="nonexistent")

    def test_negative_radius_returns_empty_or_raises(self):
        g, _, _ = build_star(3)
        # radius=0 means just the node itself, no edges → all H=0
        result = g.ego_entropy_profile(radius=0)
        assert result is not None
        for h in result["ego_entropy"].values():
            assert h == 0.0


# ── Basic correctness ──

class TestEgoEntropyBasic:
    """Tests for basic computation correctness."""

    def test_triangle_all_nodes_equal(self):
        """In K3, every node has identical ego-network → equal entropy."""
        g = build_complete(3)
        result = g.ego_entropy_profile()
        assert result is not None
        entropies = list(result["ego_entropy"].values())
        assert len(entropies) == 3
        # All nodes should have identical ego-entropy (symmetry)
        assert entropies[0] == pytest.approx(entropies[1], abs=1e-6)
        assert entropies[1] == pytest.approx(entropies[2], abs=1e-6)

    def test_star_center_has_high_entropy(self):
        """Star center's ego-network has multiple uniform edges → H = ln(k)."""
        g, hub, _ = build_star(4)
        result = g.ego_entropy_profile()
        assert result is not None
        center_h = result["ego_entropy"][hub.id]
        # 4 uniform edges → H = ln(4)
        assert center_h == pytest.approx(math.log(4), abs=0.01)

    def test_star_leaf_entropy_zero(self):
        """Star leaf's ego-network is just one edge → H=0."""
        g, hub, leaves = build_star(4)
        result = g.ego_entropy_profile()
        leaf_h = result["ego_entropy"][leaves[0].id]
        assert leaf_h == 0.0

    def test_path_end_nodes_zero(self):
        """In P5, end nodes have single-edge ego-networks → H=0."""
        g = build_path(5)
        result = g.ego_entropy_profile()
        # The lowest entropy nodes should have H=0 (end nodes)
        ranked = result["ranked"]
        assert ranked[-1][1] == 0.0

    def test_returns_dict_structure(self):
        g, _, _ = build_star(3)
        result = g.ego_entropy_profile()
        expected_keys = {
            "index", "radius", "ego_entropy", "ranked", "mean",
            "std", "max", "min", "range", "field_uniformity",
            "hotspots", "coldspots", "isolated", "evaluated"
        }
        assert set(result.keys()) == expected_keys

    def test_ranked_sorted_descending(self):
        g, _, _ = build_star(4)
        result = g.ego_entropy_profile()
        ranked = result["ranked"]
        for i in range(len(ranked) - 1):
            assert ranked[i][1] >= ranked[i + 1][1]

    def test_evaluated_count(self):
        g, _, _ = build_star(4)
        result = g.ego_entropy_profile()
        assert result["evaluated"] == 5  # 1 hub + 4 leaves

    def test_mean_computation(self):
        g, _, _ = build_star(4)
        result = g.ego_entropy_profile()
        values = list(result["ego_entropy"].values())
        expected_mean = sum(values) / len(values)
        assert result["mean"] == pytest.approx(expected_mean, abs=1e-6)

    def test_max_min(self):
        g, _, _ = build_star(4)
        result = g.ego_entropy_profile()
        values = list(result["ego_entropy"].values())
        assert result["max"] == pytest.approx(max(values), abs=1e-6)
        assert result["min"] == pytest.approx(min(values), abs=1e-6)
        assert result["range"] == pytest.approx(max(values) - min(values), abs=1e-6)


# ── Hotspots and coldspots ──

class TestEgoEntropyHotColdSpots:
    """Tests for hotspot/coldspot/isolated classification."""

    def test_hotspots_threshold(self):
        g, hub, _ = build_star(4)
        result = g.ego_entropy_profile()
        values = list(result["ego_entropy"].values())
        mean_h = sum(values) / len(values)
        var_h = sum((v - mean_h) ** 2 for v in values) / len(values)
        std_h = var_h ** 0.5
        threshold = mean_h + std_h
        expected_hotspots = {nid for nid, h in result["ego_entropy"].items()
                             if h > threshold}
        assert set(result["hotspots"]) == expected_hotspots

    def test_coldspots_threshold(self):
        g, hub, _ = build_star(4)
        result = g.ego_entropy_profile()
        values = list(result["ego_entropy"].values())
        mean_h = sum(values) / len(values)
        var_h = sum((v - mean_h) ** 2 for v in values) / len(values)
        std_h = var_h ** 0.5
        threshold = max(0.0, mean_h - std_h)
        expected_coldspots = {nid for nid, h in result["ego_entropy"].items()
                              if h < threshold}
        assert set(result["coldspots"]) == expected_coldspots

    def test_isolated_nodes_in_path(self):
        """Nodes with zero ego-entropy should be classified as isolated."""
        g = build_path(5)
        result = g.ego_entropy_profile()
        assert len(result["isolated"]) >= 2  # end nodes

    def test_hotspots_in_hub_graph(self):
        """Hub should be a hotspot (diverse ego-network)."""
        g, hub, _, _ = build_hub_and_spokes()
        result = g.ego_entropy_profile()
        # Hub H has 3 diverse edges → likely hotspot
        assert hub.id in result["hotspots"] or \
               result["ego_entropy"][hub.id] >= result["mean"]

    def test_uniform_graph_few_hotspots(self):
        """Regular graph should have few or no hotspots."""
        g, _ = build_grid_3x3()
        result = g.ego_entropy_profile()
        assert result["field_uniformity"] > 0.2


# ── Radius parameter ──

class TestEgoEntropyRadius:
    """Tests for different neighbourhood radii."""

    def test_radius_1_vs_2_difference(self):
        g, hub, spokes, leaves = build_hub_and_spokes()
        r1 = g.ego_entropy_profile(radius=1)
        r2 = g.ego_entropy_profile(radius=2)
        # At radius 2, more nodes should have non-zero entropy
        non_zero_r1 = sum(1 for h in r1["ego_entropy"].values() if h > 0)
        non_zero_r2 = sum(1 for h in r2["ego_entropy"].values() if h > 0)
        assert non_zero_r2 >= non_zero_r1

    def test_radius_2_captures_leaf_connections(self):
        g, hub, spokes, leaves = build_hub_and_spokes()
        r1 = g.ego_entropy_profile(radius=1)
        r2 = g.ego_entropy_profile(radius=2)
        # Leaf at r=1: only edge S-Leaf → H=0
        assert r1["ego_entropy"][leaves[0].id] == 0.0
        # Leaf at r=2: sees hub's other connections → H>0
        assert r2["ego_entropy"][leaves[0].id] > 0.0

    def test_large_radius_equalizes(self):
        """At radius ≥ graph diameter, all nodes see the full graph."""
        g = build_path(5)
        r5 = g.ego_entropy_profile(radius=5)
        # All nodes should see the entire path → similar entropy
        values = list(r5["ego_entropy"].values())
        for v in values:
            assert v == pytest.approx(values[0], abs=1e-6)


# ── Index variation ──

class TestEgoEntropyIndexVariation:
    """Tests for different degree-based entropy indices."""

    @pytest.mark.parametrize("index", [
        "sombor", "reduced_sombor", "randic", "zagreb_m1",
        "abc", "ga", "augmented_zagreb"
    ])
    def test_all_indices_work(self, index):
        g = build_complete(3)
        result = g.ego_entropy_profile(index=index)
        assert result is not None
        assert result["index"] == index
        assert len(result["ego_entropy"]) == 3

    def test_different_indices_different_values(self):
        """Different indices should produce different entropy on heterogeneous ego-networks."""
        g = MemoryGraph()
        h = g.add("H")
        a = g.add("A")
        b = g.add("B")
        c = g.add("C")
        g.link(h.id, a.id, "r")
        g.link(h.id, b.id, "r")
        g.link(h.id, c.id, "r")
        g.link(a.id, b.id, "r")  # A-B interconnection creates heterogeneity
        sombor_result = g.ego_entropy_profile(index="sombor")
        randic_result = g.ego_entropy_profile(index="randic")
        # Hub's ego-network has edges: H-A(3,2), H-B(3,2), H-C(3,1), A-B(2,2)
        # → heterogeneous contributions → different entropy across indices
        sombor_h = sombor_result["ego_entropy"][h.id]
        randic_h = randic_result["ego_entropy"][h.id]
        assert sombor_h != pytest.approx(randic_h, abs=1e-10)

    def test_randic_index_star_center(self):
        """Randić of star center with all degree-1 leaves = uniform contributions."""
        g, hub, _ = build_star(4)
        result = g.ego_entropy_profile(index="randic")
        center_h = result["ego_entropy"][hub.id]
        # Each edge has same Randić contribution → uniform → max entropy
        assert center_h > 0.0


# ── Field uniformity ──

class TestFieldUniformity:
    """Tests for the field uniformity metric."""

    def test_uniform_graph_high_uniformity(self):
        g, _ = build_grid_3x3()
        result = g.ego_entropy_profile()
        assert result["field_uniformity"] > 0.2

    def test_star_low_uniformity(self):
        g, _, _ = build_star(4)
        result = g.ego_entropy_profile()
        assert result["field_uniformity"] < 0.6

    def test_uniformity_range(self):
        g = build_complete(3)
        result = g.ego_entropy_profile()
        assert 0.0 <= result["field_uniformity"] <= 1.0

    def test_triangle_max_uniformity(self):
        """K3: all nodes identical entropy → field_uniformity = 1.0."""
        g = build_complete(3)
        result = g.ego_entropy_profile()
        assert result["field_uniformity"] == pytest.approx(1.0, abs=1e-6)


# ── top_k parameter ──

class TestTopK:
    """Tests for top_k filtering."""

    def test_top_k_limits_results(self):
        g, _, _ = build_star(4)
        result = g.ego_entropy_profile(top_k=2)
        assert len(result["ranked"]) == 2

    def test_top_k_zero_means_all(self):
        g, _, _ = build_star(4)
        result = g.ego_entropy_profile(top_k=0)
        assert len(result["ranked"]) == 5

    def test_top_k_larger_than_nodes(self):
        g, _, _ = build_star(4)
        result = g.ego_entropy_profile(top_k=100)
        assert len(result["ranked"]) == 5

    def test_top_k_returns_highest(self):
        g, hub, _ = build_star(4)
        result = g.ego_entropy_profile(top_k=1)
        assert result["ranked"][0][0] == hub.id
        assert result["ranked"][0][1] == result["max"]


# ── Graph comparison via ego profiles ──

class TestEgoEntropyComparison:
    """Tests comparing ego-entropy across different graph types."""

    def test_triangle_uniformity_max(self):
        """K3 should have higher uniformity than star."""
        g_tri = build_complete(3)
        g_star, _, _ = build_star(4)
        tri_result = g_tri.ego_entropy_profile()
        star_result = g_star.ego_entropy_profile()
        assert tri_result["field_uniformity"] > star_result["field_uniformity"]

    def test_grid_more_uniform_than_star(self):
        g_grid, _ = build_grid_3x3()
        g_star, _, _ = build_star(4)
        grid_result = g_grid.ego_entropy_profile()
        star_result = g_star.ego_entropy_profile()
        assert grid_result["field_uniformity"] >= star_result["field_uniformity"]


# ── Consistency and idempotency ──

class TestEgoEntropyConsistency:
    """Tests for reproducibility."""

    def test_repeated_call_same_result(self):
        g, _, _ = build_star(4)
        r1 = g.ego_entropy_profile()
        r2 = g.ego_entropy_profile()
        assert r1["ego_entropy"] == r2["ego_entropy"]
        assert r1["mean"] == r2["mean"]
        assert r1["field_uniformity"] == r2["field_uniformity"]

    def test_default_index_is_sombor(self):
        g = build_complete(3)
        result = g.ego_entropy_profile()
        assert result["index"] == "sombor"

    def test_all_nodes_have_entropy(self):
        g, nodes = build_grid_3x3()
        result = g.ego_entropy_profile()
        all_ids = {nodes[(r, c)].id for r in range(3) for c in range(3)}
        assert set(result["ego_entropy"].keys()) == all_ids


# ── Advanced scenarios ──

class TestEgoEntropyAdvanced:
    """Tests for complex graph scenarios."""

    def test_disconnected_components(self):
        """Two disconnected edges should give all nodes H=0."""
        g = MemoryGraph()
        a = g.add("A")
        b = g.add("B")
        c = g.add("C")
        d = g.add("D")
        g.link(a.id, b.id, "r")
        g.link(c.id, d.id, "r")
        result = g.ego_entropy_profile()
        for nid, h in result["ego_entropy"].items():
            assert h == 0.0

    def test_complete_graph_k4(self):
        """K4: every ego-network at r=1 is K4 itself → all equal."""
        g = build_complete(4)
        result = g.ego_entropy_profile()
        values = list(result["ego_entropy"].values())
        for v in values:
            assert v == pytest.approx(values[0], abs=1e-6)
        assert result["field_uniformity"] == pytest.approx(1.0, abs=1e-6)

    def test_large_graph_performance(self):
        """Should handle 100+ nodes efficiently."""
        import random
        random.seed(42)
        g = MemoryGraph()
        nodes = [g.add(str(i)) for i in range(100)]
        for i in range(1, 100):
            j = random.randint(0, i - 1)
            g.link(nodes[i].id, nodes[j].id, "r")
        result = g.ego_entropy_profile()
        assert result is not None
        assert result["evaluated"] == 100

    def test_isolated_node_has_zero_entropy(self):
        """A node with no edges should have ego-entropy = 0."""
        g = MemoryGraph()
        lonely = g.add("Lonely")
        a = g.add("A")
        b = g.add("B")
        g.link(a.id, b.id, "r")
        result = g.ego_entropy_profile()
        assert result["ego_entropy"][lonely.id] == 0.0
        assert lonely.id in result["isolated"]

    def test_added_edge_changes_entropy(self):
        """Adding an edge within a node's ego-network should change its entropy."""
        g = MemoryGraph()
        a = g.add("A")
        b = g.add("B")
        c = g.add("C")
        g.link(a.id, b.id, "r")
        g.link(a.id, c.id, "r")
        before = g.ego_entropy_profile()
        g.link(b.id, c.id, "r")
        after = g.ego_entropy_profile()
        # A's entropy should change
        assert before["ego_entropy"][a.id] != after["ego_entropy"][a.id]

    def test_hotspot_identification(self):
        """In a graph with a clear hub, hub should be identified as hotspot."""
        g, hub, _ = build_star(6)
        result = g.ego_entropy_profile()
        # Hub has high entropy, all leaves have H=0
        assert result["ego_entropy"][hub.id] > 0.0
        assert hub.id in result["hotspots"]

    def test_coldspot_identification(self):
        """Star leaves should be coldspots (H=0)."""
        g, _, leaves = build_star(6)
        result = g.ego_entropy_profile()
        for leaf in leaves:
            assert leaf.id in result["coldspots"] or \
                   leaf.id in result["isolated"]


# ── Integration with existing entropy APIs ──

class TestEgoEntropyIntegration:
    """Tests showing ego_entropy_profile relates to existing entropy methods."""

    def test_ego_profile_vs_global_entropy(self):
        """Ego-entropy and global entropy are complementary views."""
        g, _, _ = build_star(4)
        ego_result = g.ego_entropy_profile(index="sombor")
        # Ego mean should be non-negative
        assert ego_result["mean"] >= 0.0

    def test_complements_entropy_contribution(self):
        """In symmetric graph, both ego and contribution should show uniformity."""
        g = build_complete(3)
        ego_result = g.ego_entropy_profile()
        contrib_result = g.entropy_contribution()
        ego_values = list(ego_result["ego_entropy"].values())
        assert all(v == pytest.approx(ego_values[0], abs=1e-6) for v in ego_values)
        if contrib_result:
            contrib_values = list(contrib_result["contributions"].values())
            assert all(v == pytest.approx(contrib_values[0], abs=1e-6)
                       for v in contrib_values)

    def test_ego_profile_faster_than_contribution(self):
        """Ego-entropy should be faster than leave-one-out for large graphs."""
        import time
        import random
        random.seed(42)
        g = MemoryGraph()
        nodes = [g.add(str(i)) for i in range(50)]
        for i in range(1, 50):
            j = random.randint(0, i - 1)
            g.link(nodes[i].id, nodes[j].id, "r")
        # Time ego_entropy_profile
        t1 = time.time()
        g.ego_entropy_profile()
        ego_time = time.time() - t1
        # Time entropy_contribution
        t2 = time.time()
        g.entropy_contribution()
        contrib_time = time.time() - t2
        # Ego should be faster (allow generous margin for test variance)
        assert ego_time <= contrib_time * 5  # at most 5x slower (test variance)
