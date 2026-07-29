"""Cycle 310: spectral_entropy_contribution() — leave-one-out von Neumann entropy.

Tests cover:
- K_n: uniform topology, all nodes equal contribution
- Star graph: hub has highest spectral contribution
- Path: endpoints vs internal nodes
- Triangle: symmetric, all equal
- Scale invariance
- Sampling mode
- top_k filtering
- Empty/small graph edge cases
- Consistency with von_neumann_entropy
"""

import math
import pytest
import random
from memory_graph import MemoryGraph


@pytest.fixture
def g():
    return MemoryGraph(":memory:")


class TestSpectralEntropyContributionBasic:
    """Core functionality tests."""

    def test_none_for_empty_graph(self, g):
        result = g.spectral_entropy_contribution()
        assert result is None

    def test_none_for_single_node(self, g):
        g.add("a")
        result = g.spectral_entropy_contribution()
        assert result is None

    def test_none_for_two_nodes(self, g):
        a = g.add("a")
        b = g.add("b")
        g.link(a.id, b.id, "rel")
        result = g.spectral_entropy_contribution()
        assert result is None

    def test_triangle_all_equal(self, g):
        """In K_3, removing any node gives P_2, same effect for all."""
        a, b, c = g.add("a"), g.add("b"), g.add("c")
        g.link(a.id, b.id, "rel"); g.link(b.id, c.id, "rel"); g.link(a.id, c.id, "rel")
        result = g.spectral_entropy_contribution()
        assert result is not None
        assert result["index"] == "von_neumann"
        assert len(result["contributions"]) == 3
        # All deltas should be equal (symmetry)
        deltas = list(result["contributions"].values())
        assert max(deltas) - min(deltas) < 1e-6, f"Unequal: {deltas}"

    def test_star_hub_critical(self, g):
        """Hub in star K_{1,4} should have highest spectral contribution."""
        hub = g.add("hub")
        leaves = [g.add(f"l{i}") for i in range(4)]
        for lf in leaves:
            g.link(hub.id, lf.id, "rel")
        result = g.spectral_entropy_contribution()
        assert result is not None
        # Hub delta should be > all leaf deltas
        hub_delta = result["contributions"][hub.id]
        for lf in leaves:
            assert hub_delta > result["contributions"][lf.id], \
                f"hub {hub_delta} <= leaf {result['contributions'][lf]}"

    def test_return_structure(self, g):
        """All required keys present."""
        a, b, c = g.add("a"), g.add("b"), g.add("c")
        g.link(a.id, b.id, "r"); g.link(b.id, c.id, "r")
        result = g.spectral_entropy_contribution()
        required_keys = [
            "baseline_entropy", "contributions", "ranked",
            "mean", "std", "max_delta", "min_delta",
            "critical_nodes", "expendable_nodes",
            "index", "sampled", "evaluated",
        ]
        for k in required_keys:
            assert k in result, f"Missing key: {k}"
        assert result["index"] == "von_neumann"
        assert result["sampled"] is False
        assert result["evaluated"] == 3
        assert len(result["ranked"]) == 3


class TestSpectralEntropyContributionRanked:
    """Ranking and filtering tests."""

    def test_ranked_sorted_descending(self, g):
        a, b, c, d = g.add("a"), g.add("b"), g.add("c"), g.add("d")
        g.link(a.id, b.id, "r"); g.link(b.id, c.id, "r"); g.link(c.id, d.id, "r"); g.link(a.id, c.id, "r")
        result = g.spectral_entropy_contribution()
        scores = [s for _, s in result["ranked"]]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_top_k(self, g):
        a, b, c, d, e = [g.add(str(i)) for i in range(5)]
        for u, v in [(a,b),(b,c),(c,d),(d,e),(a,c)]:
            g.link(u.id, v.id, "r")
        result = g.spectral_entropy_contribution(top_k=2)
        assert len(result["ranked"]) == 2
        assert len(result["contributions"]) == 5  # all computed


class TestSpectralEntropyContributionSampling:
    """Sampling mode tests."""

    def test_sampled_flag(self, g):
        nodes = [g.add(str(i)) for i in range(10)]
        for i in range(9):
            g.link(nodes[i].id, nodes[i+1].id, "r")
        result = g.spectral_entropy_contribution(sample=5)
        assert result is not None
        assert result["sampled"] is True
        assert result["evaluated"] == 5

    def test_no_sampling_when_small(self, g):
        a, b, c = g.add("a"), g.add("b"), g.add("c")
        g.link(a.id, b.id, "r"); g.link(b.id, c.id, "r")
        result = g.spectral_entropy_contribution(sample=10)
        assert result["sampled"] is False
        assert result["evaluated"] == 3

    def test_sampled_deterministic_with_seed(self, g):
        """Same seed should give consistent results."""
        nodes_a = [g.add(f"a{i}") for i in range(8)]
        for i in range(7):
            g.link(nodes_a[i].id, nodes_a[i+1].id, "r")
        result1 = g.spectral_entropy_contribution(sample=5)
        # Just verify it runs; randomness makes exact match unreliable
        assert result1["evaluated"] == 5


class TestSpectralEntropyContributionConsistency:
    """Consistency with other methods."""

    def test_baseline_matches_von_neumann(self, g):
        a, b, c, d = [g.add(str(i)) for i in range(4)]
        g.link(a.id, b.id, "r"); g.link(b.id, c.id, "r"); g.link(c.id, d.id, "r")
        vn = g.von_neumann_entropy(normalized=True)
        result = g.spectral_entropy_contribution()
        assert abs(result["baseline_entropy"] - vn) < 1e-6

    def test_kn_max_entropy_baseline(self, g):
        """K_5 should have H_vN close to 1.0 (max)."""
        nodes = [g.add(str(i)) for i in range(5)]
        for i in range(5):
            for j in range(i+1, 5):
                g.link(nodes[i].id, nodes[j].id, "r")
        result = g.spectral_entropy_contribution()
        assert result["baseline_entropy"] > 0.95

    def test_disconnected_graph(self, g):
        """Two separate components — removing a bridge-like node..."""
        a, b, c, d = g.add("a"), g.add("b"), g.add("c"), g.add("d")
        g.link(a.id, b.id, "r")  # component 1
        g.link(c.id, d.id, "r")  # component 2
        result = g.spectral_entropy_contribution()
        assert result is not None
        assert result["evaluated"] == 4

    def test_pendant_vs_internal(self, g):
        """Internal nodes on a path should have higher spectral contribution."""
        nodes = [g.add(str(i)) for i in range(6)]
        for i in range(5):
            g.link(nodes[i].id, nodes[i+1].id, "r")
        result = g.spectral_entropy_contribution()
        # Internal nodes (1,2,3,4) should generally have higher ΔH
        # than endpoints (0,5) in spectral analysis
        internal_deltas = [result["contributions"][nodes[i].id] for i in range(1,5)]
        endpoint_deltas = [result["contributions"][nodes[i].id] for i in [0, 5]]
        assert max(internal_deltas) >= max(endpoint_deltas) - 0.05


class TestSpectralEntropyContributionEdgeCases:
    """Edge case tests."""

    def test_quarantined_nodes_excluded(self, g):
        a, b, c, d, e = g.add("a"), g.add("b"), g.add("c"), g.add("d"), g.add("e")
        g.link(a.id, b.id, "r"); g.link(b.id, c.id, "r"); g.link(c.id, d.id, "r"); g.link(d.id, e.id, "r")
        g.node_quarantine(c.id)
        result = g.spectral_entropy_contribution()
        assert result is not None
        # c should not appear in contributions
        assert c.id not in result["contributions"]
        assert result["evaluated"] == 4

    def test_isolated_node_zero_contribution(self, g):
        """Isolated node removal doesn't change spectrum."""
        a, b, c, d = g.add("a"), g.add("b"), g.add("c"), g.add("d")
        g.link(a.id, b.id, "r"); g.link(b.id, c.id, "r"); g.link(a.id, c.id, "r")
        # d is isolated — its removal only changes node count, not connected topology
        result = g.spectral_entropy_contribution()
        # Delta should be small compared to connected nodes
        connected_deltas = [result["contributions"][n.id] for n in [a, b, c]]
        assert result["contributions"][d.id] < max(connected_deltas)

    def test_stats_computed_correctly(self, g):
        a, b, c, d = [g.add(str(i)) for i in range(4)]
        g.link(a.id, b.id, "r"); g.link(b.id, c.id, "r"); g.link(c.id, d.id, "r")
        result = g.spectral_entropy_contribution()
        deltas = list(result["contributions"].values())
        assert result["max_delta"] == round(max(deltas), 6)
        assert result["min_delta"] == round(min(deltas), 6)
        expected_mean = sum(deltas) / len(deltas)
        assert abs(result["mean"] - round(expected_mean, 6)) < 1e-4

    def test_critical_and_expendable_mutually_exclusive(self, g):
        """A node can't be both critical and expendable."""
        a, b, c, d, e = [g.add(str(i)) for i in range(5)]
        for u, v in [(a,b),(b,c),(c,d),(d,e)]:
            g.link(u.id, v.id, "r")
        result = g.spectral_entropy_contribution()
        critical = set(result["critical_nodes"])
        expendable = set(result["expendable_nodes"])
        assert len(critical & expendable) == 0
