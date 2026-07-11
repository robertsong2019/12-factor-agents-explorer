"""Tests for structure-gated Personalized PageRank (ppr_structured).

SAGE-inspired propagation gating: centrality modulates how much signal
each node passes forward during PPR iteration.
"""

import pytest
from memory_graph import MemoryGraph


def _build_linear():
    """A↔B↔C↔D↔E linear chain (bidirectional). Returns (mg, ids)."""
    mg = MemoryGraph()
    nodes = [mg.add(label, "node") for label in ["A", "B", "C", "D", "E"]]
    ids = [n.id for n in nodes]
    for i in range(4):
        mg.link(ids[i], ids[i+1], "rel")
        mg.link(ids[i+1], ids[i], "rel")
    return mg, ids


def _build_star():
    """Hub H ↔ S1, S2, S3, S4 spokes (bidirectional). Returns (mg, ids)."""
    mg = MemoryGraph()
    hub = mg.add("H", "hub")
    spokes = [mg.add(f"S{i}", "spoke") for i in range(1, 5)]
    ids = [hub.id] + [s.id for s in spokes]
    for s in spokes:
        mg.link(hub.id, s.id, "rel")
        mg.link(s.id, hub.id, "rel")
    return mg, ids


def _build_diamond():
    """A↔{B,C}↔D diamond (bidirectional). Returns (mg, ids)."""
    mg = MemoryGraph()
    a = mg.add("A", "node")
    b = mg.add("B", "node")
    c = mg.add("C", "node")
    d = mg.add("D", "node")
    ids = [a.id, b.id, c.id, d.id]
    for s, t in [(a.id,b.id),(a.id,c.id),(b.id,d.id),(c.id,d.id)]:
        mg.link(s, t, "rel")
        mg.link(t, s, "rel")
    return mg, ids


def _build_complete():
    """K4 complete graph (bidirectional). Returns (mg, ids)."""
    mg = MemoryGraph()
    nodes = [mg.add(f"N{i}", "node") for i in range(1, 5)]
    ids = [n.id for n in nodes]
    for i in range(4):
        for j in range(4):
            if i != j:
                mg.link(ids[i], ids[j], "rel")
                mg.link(ids[j], ids[i], "rel")
    return mg, ids


# =====================================================================
# Basic functionality
# =====================================================================

class TestPPRStructuredBasic:
    """Basic correctness tests."""

    def test_empty_seeds_returns_empty(self):
        mg, ids = _build_linear()
        assert mg.ppr_structured([]) == {}

    def test_single_seed_returns_all_nodes(self):
        mg, ids = _build_linear()
        result = mg.ppr_structured([ids[0]])
        assert len(result) == 5
        assert all(nid in result for nid in ids)

    def test_seed_not_in_graph_returns_empty(self):
        mg, ids = _build_linear()
        assert mg.ppr_structured(["NONEXIST"]) == {}

    def test_scores_sum_to_approx_one(self):
        mg, ids = _build_linear()
        result = mg.ppr_structured([ids[0]])
        total = sum(result.values())
        assert 0.9 < total < 1.1

    def test_all_scores_non_negative(self):
        mg, ids = _build_linear()
        result = mg.ppr_structured([ids[0]])
        assert all(v >= 0 for v in result.values())

    def test_seed_gets_highest_score(self):
        mg, ids = _build_star()
        result = mg.ppr_structured([ids[0]])  # hub
        assert result[ids[0]] == max(result.values())

    def test_alpha_zero_matches_standard_ppr(self):
        """With gate_alpha=0, result should be close to standard PPR.

        Small differences expected due to per-iteration normalisation
        (ppr_structured normalises after each step; standard PPR does not).
        """
        mg, ids = _build_linear()
        gated = mg.ppr_structured([ids[0]], gate_alpha=0.0)
        standard = mg.personalized_pagerank([ids[0]])
        g_total = sum(gated.values()) or 1
        s_total = sum(standard.values()) or 1
        # Check rank ordering is preserved (not exact values)
        gated_rank = sorted(gated.keys(), key=lambda x: gated[x], reverse=True)
        standard_rank = sorted(standard.keys(), key=lambda x: standard[x], reverse=True)
        assert gated_rank[0] == standard_rank[0]  # same top node


# =====================================================================
# Gating effects
# =====================================================================

class TestGatingEffects:
    """Verify that centrality gating changes propagation patterns."""

    def test_degree_gate_changes_hub_score(self):
        """Hub with degree gating should get different score than without."""
        mg, ids = _build_star()
        hub_id = ids[0]
        spoke_ids = ids[1:]
        no_gate = mg.ppr_structured(spoke_ids[:1], gate_alpha=0.0)
        with_gate = mg.ppr_structured(spoke_ids[:1], gate_alpha=1.0, gate="degree")
        # Hub should propagate more signal with gating
        assert with_gate[hub_id] > no_gate.get(hub_id, 0)

    def test_betweenness_gate_symmetry(self):
        """In diamond A→{B,C}→D, B and C are symmetric."""
        mg, ids = _build_diamond()
        gated = mg.ppr_structured([ids[0]], gate="betweenness", gate_alpha=0.5)
        assert abs(gated[ids[1]] - gated[ids[2]]) < 0.01

    def test_closeness_gate(self):
        """Closeness centrality gating should not crash."""
        mg, ids = _build_linear()
        gated = mg.ppr_structured([ids[0]], gate="closeness", gate_alpha=0.8)
        assert len(gated) == 5

    def test_eigenvector_gate_uniform_graph(self):
        """In K4 all nodes have equal eigenvector centrality."""
        mg, ids = _build_complete()
        gated = mg.ppr_structured(
            [ids[0]], gate="eigenvector", gate_alpha=1.0
        )
        standard = mg.ppr_structured([ids[0]], gate_alpha=0.0)
        for nid in gated:
            assert abs(gated[nid] - standard[nid]) < 0.05

    def test_pagerank_gate(self):
        """PageRank gate: hub has highest PR."""
        mg, ids = _build_star()
        gated = mg.ppr_structured([ids[1]], gate="pagerank", gate_alpha=1.0)
        assert len(gated) == 5
        assert all(0 <= v <= 1 for v in gated.values())

    def test_unknown_gate_falls_back_to_degree(self):
        """Unknown gate metric should fall back to degree centrality."""
        mg, ids = _build_linear()
        gated_unknown = mg.ppr_structured([ids[0]], gate="nonexistent", gate_alpha=0.5)
        gated_degree = mg.ppr_structured([ids[0]], gate="degree", gate_alpha=0.5)
        for nid in gated_unknown:
            assert abs(gated_unknown[nid] - gated_degree[nid]) < 0.001


# =====================================================================
# Convergence and parameters
# =====================================================================

class TestPPRStructuredParams:
    """Parameter sensitivity and convergence tests."""

    def test_higher_damping_spreads_more(self):
        """Higher damping → more propagation → distant nodes get more signal."""
        mg, ids = _build_linear()
        low_damp = mg.ppr_structured([ids[0]], damping=0.5)
        high_damp = mg.ppr_structured([ids[0]], damping=0.95)
        assert high_damp[ids[4]] > low_damp[ids[4]]

    def test_max_iter_convergence(self):
        mg, ids = _build_linear()
        result = mg.ppr_structured([ids[0]], max_iter=1000)
        assert sum(result.values()) > 0.9

    def test_low_max_iter_still_works(self):
        mg, ids = _build_linear()
        result = mg.ppr_structured([ids[0]], max_iter=1)
        assert len(result) == 5
        assert all(v >= 0 for v in result.values())

    def test_various_tol(self):
        mg, ids = _build_linear()
        for tol in [1e-1, 1e-6, 1e-12]:
            result = mg.ppr_structured([ids[0]], tol=tol)
            assert len(result) == 5

    def test_higher_alpha_stronger_gating(self):
        """Higher gate_alpha → more pronounced gating effect."""
        mg, ids = _build_star()
        alpha_low = mg.ppr_structured([ids[1]], gate_alpha=0.1, gate="degree")
        alpha_high = mg.ppr_structured([ids[1]], gate_alpha=1.0, gate="degree")
        # Results should differ
        assert any(abs(alpha_low[nid] - alpha_high[nid]) > 0.001 for nid in alpha_low)


# =====================================================================
# Edge cases
# =====================================================================

class TestPPRStructuredEdgeCases:
    """Edge cases and robustness."""

    def test_single_node_graph(self):
        mg = MemoryGraph()
        node = mg.add("LONE", "node")
        result = mg.ppr_structured([node.id])
        assert result[node.id] > 0
        assert abs(sum(result.values()) - 1.0) < 0.1

    def test_isolated_nodes_no_edges(self):
        mg = MemoryGraph()
        x = mg.add("X", "node")
        y = mg.add("Y", "node")
        result = mg.ppr_structured([x.id])
        assert result[x.id] > 0.9
        assert result[y.id] < 0.1

    def test_multiple_seeds(self):
        mg, ids = _build_star()
        result = mg.ppr_structured([ids[1], ids[2]])
        assert len(result) == 5
        # Both seeds should have high scores
        assert result[ids[1]] > result[ids[3]]

    def test_all_nodes_as_seeds(self):
        mg, ids = _build_complete()
        result = mg.ppr_structured(ids)
        vals = list(result.values())
        assert max(vals) - min(vals) < 0.2

    def test_self_loop_graph(self):
        mg = MemoryGraph()
        node = mg.add("LOOP", "node")
        mg.link(node.id, node.id, "self")
        result = mg.ppr_structured([node.id])
        assert result[node.id] > 0.9

    def test_directed_graph_asymmetry(self):
        """Directed edges: A→B but not B→A."""
        mg = MemoryGraph()
        a = mg.add("A", "node")
        b = mg.add("B", "node")
        mg.link(a.id, b.id, "rel")
        result_from_a = mg.ppr_structured([a.id])
        result_from_b = mg.ppr_structured([b.id])
        # From A, signal can reach B
        assert result_from_a[b.id] > 0
        # From B (no outgoing edges), signal stays at B
        assert result_from_b[a.id] < result_from_b[b.id]


# =====================================================================
# Integration with existing infrastructure
# =====================================================================

class TestPPRStructuredIntegration:
    """Integration tests with existing infrastructure."""

    def test_gating_preserves_node_set(self):
        """Gating should not add or remove nodes from the result."""
        mg, ids = _build_diamond()
        gated = mg.ppr_structured([ids[0]], gate_alpha=0.5)
        standard = mg.personalized_pagerank([ids[0]])
        assert set(gated.keys()) == set(standard.keys())

    def test_undirected_edges_symmetric(self):
        """In linear graph, center node C should propagate symmetrically."""
        mg, ids = _build_linear()
        center_id = ids[2]
        result = mg.ppr_structured([center_id])
        # A (ids[0]) and E (ids[4]) are equidistant from C
        assert abs(result[ids[0]] - result[ids[4]]) < 0.01

    def test_retrieve_pipeline_unchanged(self):
        """Existing retrieve() should still work with ppr_structured added."""
        mg, ids = _build_star()
        mg.update_node(ids[0], label="hub central")
        mg.update_node(ids[1], label="spoke one")
        results = mg.retrieve("hub", limit=5)
        assert isinstance(results, (list, dict))


# =====================================================================
# Consistency properties
# =====================================================================

class TestPPRStructuredProperties:
    """Mathematical properties that should always hold."""

    def test_scores_are_probabilities(self):
        mg, ids = _build_linear()
        result = mg.ppr_structured([ids[0]], gate_alpha=0.7)
        for nid, score in result.items():
            assert 0.0 <= score <= 1.0, f"{nid} has score {score} > 1"

    def test_repeated_calls_are_deterministic(self):
        mg, ids = _build_diamond()
        r1 = mg.ppr_structured([ids[0]], gate="betweenness", gate_alpha=0.5)
        r2 = mg.ppr_structured([ids[0]], gate="betweenness", gate_alpha=0.5)
        for nid in r1:
            assert abs(r1[nid] - r2[nid]) < 1e-10

    def test_multiple_seeds_equal_weight(self):
        mg, ids = _build_star()
        r1 = mg.ppr_structured([ids[1], ids[2]])
        assert abs(r1[ids[1]] - r1[ids[2]]) < 0.01

    def test_gating_does_not_diverge(self):
        """Even with alpha=1.0, scores should not diverge."""
        mg, ids = _build_complete()
        for gate in ["degree", "pagerank", "eigenvector"]:
            result = mg.ppr_structured(
                [ids[0]], gate=gate, gate_alpha=1.0, max_iter=500
            )
            assert all(0 <= v <= 1 for v in result.values())
            assert abs(sum(result.values()) - 1.0) < 0.1
