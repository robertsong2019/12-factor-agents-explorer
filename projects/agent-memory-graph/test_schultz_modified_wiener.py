"""Tests for Schultz index and Modified Wiener index — Cycle 226.

Schultz index: S = Σ_{u<v} (d_u + d_v) · d(u, v)
Modified Wiener: W_λ = Σ_{u<v} d(u, v)^λ
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph()


class TestSchultzIndex:
    """Schultz molecular topological index (Schultz 1989).
    S(G) = Σ_{u<v} (d_u + d_v) · d(u, v)
    """

    def test_empty(self, mg):
        assert mg.schultz_index() is None

    def test_single_node(self, mg):
        mg.add("A")
        assert mg.schultz_index() is None

    def test_two_isolated(self, mg):
        mg.add("A")
        mg.add("B")
        assert mg.schultz_index() is None  # no edges

    def test_single_edge_k2(self, mg):
        """K₂: degrees (1,1), distance 1. S = (1+1)·1 = 2."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.schultz_index() == 2

    def test_triangle_k3(self, mg):
        """K₃: all degrees 2, all pairwise distances 1.
        3 pairs × (2+2)·1 = 12.
        """
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(a.id, c.id, "r")
        assert mg.schultz_index() == 12

    def test_path_p3(self, mg):
        """P₃: a-b-c. Degrees: a=1, b=2, c=1.
        pair(a,b): (1+2)·1=3. pair(b,c): (2+1)·1=3. pair(a,c): (1+1)·2=4.
        S = 3+3+4 = 10.
        """
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.schultz_index() == 10

    def test_path_p4(self, mg):
        """P₄: a-b-c-d. Degrees: a=1, b=2, c=2, d=1.
        pairs: (a,b)=3, (a,c)=(1+2)·2=6, (a,d)=(1+1)·3=6,
        (b,c)=(2+2)·1=4, (b,d)=(2+1)·2=6, (c,d)=3.
        S = 3+6+6+4+6+3 = 28.
        """
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, d.id, "r")
        assert mg.schultz_index() == 28

    def test_star_k1_3(self, mg):
        """Star K_{1,3}: center degree 3, leaves degree 1.
        center-leaves: 3 pairs × (3+1)·1 = 12.
        leaf-leaf: 3 pairs × (1+1)·2 = 12.
        S = 24.
        """
        c = mg.add("center")
        l1, l2, l3 = mg.add("L1"), mg.add("L2"), mg.add("L3")
        mg.link(c.id, l1.id, "r")
        mg.link(c.id, l2.id, "r")
        mg.link(c.id, l3.id, "r")
        assert mg.schultz_index() == 24

    def test_cycle_c4(self, mg):
        """C₄: all degrees 2. Distances: 4 pairs at d=1, 2 pairs at d=2.
        S = 4·(2+2)·1 + 2·(2+2)·2 = 16 + 16 = 32.
        """
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, d.id, "r")
        mg.link(d.id, a.id, "r")
        assert mg.schultz_index() == 32

    def test_complete_k4(self, mg):
        """K₄: all degrees 3, all pairwise distances 1.
        6 pairs × (3+3)·1 = 36.
        """
        nodes = [mg.add(f"N{i}") for i in range(4)]
        for i in range(4):
            for j in range(i + 1, 4):
                mg.link(nodes[i].id, nodes[j].id, "r")
        assert mg.schultz_index() == 36

    def test_regular_graph_relation(self, mg):
        """For 2-regular graph (cycle): S = 2k·W = 4·W."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(a.id, c.id, "r")
        w = mg.wiener_index()
        assert mg.schultz_index() == 4 * w  # 2k=4, W=3

    def test_isolated_node_excluded(self, mg):
        """Isolated nodes have degree 0 but still contribute to pairs."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        mg.add("C")  # isolated
        # pair(a,b): (1+1)·1=2. pair(a,c): unreachable. pair(b,c): unreachable.
        assert mg.schultz_index() == 2

    def test_directed_graph_undirected_behavior(self, mg):
        """Schultz index uses undirected distance (BFS treats graph as undirected)."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        # Same as P₃ regardless of link direction
        assert mg.schultz_index() == 10


class TestModifiedWienerIndex:
    """Modified Wiener index W_λ = Σ_{u<v} d(u,v)^λ."""

    def test_empty(self, mg):
        assert mg.modified_wiener_index() is None

    def test_single_node(self, mg):
        mg.add("A")
        assert mg.modified_wiener_index() is None

    def test_two_isolated(self, mg):
        mg.add("A")
        mg.add("B")
        # No edge → unreachable → no contribution but 2 nodes exist
        # Actually: unreachable pairs are excluded. With 0 contributions it's 0.0
        result = mg.modified_wiener_index()
        assert result is not None
        assert result == 0.0

    def test_single_edge_lambda_minus1(self, mg):
        """K₂, λ=-1: d=1, 1^(-1)=1. W_{-1}=1."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.modified_wiener_index(lam=-1) == 1.0

    def test_single_edge_lambda_1_equals_wiener(self, mg):
        """λ=1 reduces to classic Wiener index."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.modified_wiener_index(lam=1) == 1.0
        assert mg.modified_wiener_index(lam=1) == mg.wiener_index()

    def test_path_p3_lambda_1(self, mg):
        """P₃ λ=1: d(a,b)=1, d(b,c)=1, d(a,c)=2. W = 1+1+2 = 4 = Wiener."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.modified_wiener_index(lam=1) == mg.wiener_index()

    def test_path_p3_lambda_minus1(self, mg):
        """P₃ λ=-1: 1^(-1) + 1^(-1) + 2^(-1) = 1 + 1 + 0.5 = 2.5."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.modified_wiener_index(lam=-1) == 2.5

    def test_path_p3_lambda_2(self, mg):
        """P₃ λ=2: 1² + 1² + 2² = 1 + 1 + 4 = 6."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.modified_wiener_index(lam=2) == 6.0

    def test_path_p4_lambda_minus1(self, mg):
        """P₄ λ=-1: pairs at d=1: 3×1=3, d=2: 2×0.5=1, d=3: 1×(1/3)=1/3.
        W_{-1} = 3 + 1 + 1/3 = 4.333...
        """
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, d.id, "r")
        result = mg.modified_wiener_index(lam=-1)
        assert result == pytest.approx(3 + 1 + 1/3)

    def test_triangle_k3_lambda_minus1(self, mg):
        """K₃ λ=-1: 3 pairs at d=1. W_{-1} = 3 × 1 = 3."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(a.id, c.id, "r")
        assert mg.modified_wiener_index(lam=-1) == 3.0

    def test_complete_k4_lambda_minus1(self, mg):
        """K₄ λ=-1: 6 pairs all at d=1. W_{-1} = 6."""
        nodes = [mg.add(f"N{i}") for i in range(4)]
        for i in range(4):
            for j in range(i + 1, 4):
                mg.link(nodes[i].id, nodes[j].id, "r")
        assert mg.modified_wiener_index(lam=-1) == 6.0

    def test_lambda_3_path_p3(self, mg):
        """P₃ λ=3: 1³ + 1³ + 2³ = 1 + 1 + 8 = 10."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.modified_wiener_index(lam=3) == 10.0

    def test_lambda_0(self, mg):
        """λ=0: every reachable pair contributes d^0 = 1.
        P₃ has 3 reachable pairs. W_0 = 3.
        """
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.modified_wiener_index(lam=0) == 3.0

    def test_star_k1_3_lambda_2(self, mg):
        """Star K_{1,3} λ=2: center-leaf d=1 (3 pairs × 1²=1),
        leaf-leaf d=2 (3 pairs × 2²=4). W_2 = 3 + 12 = 15.
        """
        c = mg.add("center")
        l1, l2, l3 = mg.add("L1"), mg.add("L2"), mg.add("L3")
        mg.link(c.id, l1.id, "r")
        mg.link(c.id, l2.id, "r")
        mg.link(c.id, l3.id, "r")
        assert mg.modified_wiener_index(lam=2) == 15.0

    def test_cycle_c4_lambda_minus1(self, mg):
        """C₄ λ=-1: 4 pairs at d=1 (4×1=4), 2 pairs at d=2 (2×0.5=1).
        W_{-1} = 5.
        """
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, d.id, "r")
        mg.link(d.id, a.id, "r")
        assert mg.modified_wiener_index(lam=-1) == 5.0

    def test_default_lambda_is_minus1(self, mg):
        """Default λ should be -1."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.modified_wiener_index() == mg.modified_wiener_index(lam=-1)

    def test_isolated_node_excluded_from_pairs(self, mg):
        """Isolated node: pair with it is unreachable, contributes 0."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        mg.add("C")  # isolated
        # pair(a,b): 1^(-1)=1. pairs with C: unreachable.
        assert mg.modified_wiener_index(lam=-1) == 1.0

    def test_negative_lambda_floating_point(self, mg):
        """λ=-2 should produce float results."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        result = mg.modified_wiener_index(lam=-2)
        # 1^(-2) + 1^(-2) + 2^(-2) = 1 + 1 + 0.25 = 2.25
        assert result == pytest.approx(2.25)
        assert isinstance(result, float)
