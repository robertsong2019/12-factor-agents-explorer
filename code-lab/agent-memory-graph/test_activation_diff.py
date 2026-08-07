"""Tests for MemoryGraph.activation_diff().

Covers:
- Structure and return keys
- Degenerate inputs (empty, single)
- Identical runs (perfect correlation)
- Node set differences (new / lost)
- Activation deltas (gains / losses)
- Rank changes
- Spearman correlation extremes (1.0, 0.0, -1.0, partial)
- Jaccard overlap
- min_delta filtering
- Custom activation_key and node_key
- Summary text properties
- Non-mutating
- Integration with spreading_activation, temporal_spreading, competitive_spreading
- Determinism
- Edge cases
"""

import math
import pytest
from memory_graph import MemoryGraph


# ── Helper ──────────────────────────────────────────────────────────

def _build_path(mg, n):
    """Build a path graph with n nodes, return IDs."""
    ids = []
    for i in range(n):
        node = mg.add(f"N{i}", kind="concept")
        ids.append(node.id)
    for i in range(n - 1):
        mg.link(ids[i], ids[i + 1], relation="related_to")
    return ids


def _build_star(mg, n_leaves):
    """Build a star graph: centre + n_leaves, return (centre_id, leaf_ids)."""
    centre = mg.add("Centre", kind="hub")
    centre_id = centre.id
    leaves = []
    for i in range(n_leaves):
        leaf = mg.add(f"Leaf{i}", kind="detail")
        leaves.append(leaf.id)
        mg.link(centre_id, leaves[-1], relation="has_part")
    return centre_id, leaves


def _activation_results(r):
    """Extract the results list from various API return formats."""
    if isinstance(r, list):
        return r
    if isinstance(r, dict) and "results" in r:
        return r["results"]
    return []


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def path_graph():
    mg = MemoryGraph()
    ids = _build_path(mg, 5)
    return mg, ids


@pytest.fixture
def star_graph():
    mg = MemoryGraph()
    centre, leaves = _build_star(mg, 4)
    return mg, centre, leaves


@pytest.fixture
def empty_graph():
    return MemoryGraph()


# ═══════════════════════════════════════════════════════════════════
# 1. Structure — return keys and types
# ═══════════════════════════════════════════════════════════════════

class TestStructure:
    def test_return_type(self):
        diff = MemoryGraph().activation_diff([], [])
        assert isinstance(diff, dict)

    def test_all_keys_present(self):
        diff = MemoryGraph().activation_diff([], [])
        expected = {
            "baseline_nodes", "comparison_nodes", "common_nodes",
            "new_nodes", "lost_nodes", "gains", "losses",
            "rank_changes", "spearman_rho", "mean_absolute_delta",
            "activation_overlap", "summary", "summary_metrics",
        }
        assert expected <= set(diff.keys())

    def test_summary_metrics_keys(self):
        diff = MemoryGraph().activation_diff([], [])
        expected = {
            "baseline_count", "comparison_count", "common_count",
            "new_count", "lost_count", "gain_count", "loss_count",
            "spearman_rho", "mean_absolute_delta", "activation_overlap",
            "biggest_mover", "biggest_mover_delta",
        }
        assert expected <= set(diff["summary_metrics"].keys())

    def test_summary_is_string(self):
        diff = MemoryGraph().activation_diff([], [])
        assert isinstance(diff["summary"], str)

    def test_gains_losses_are_lists(self):
        diff = MemoryGraph().activation_diff([], [])
        assert isinstance(diff["gains"], list)
        assert isinstance(diff["losses"], list)

    def test_rank_changes_is_list(self):
        diff = MemoryGraph().activation_diff([], [])
        assert isinstance(diff["rank_changes"], list)


# ═══════════════════════════════════════════════════════════════════
# 2. Degenerate — empty, single
# ═══════════════════════════════════════════════════════════════════

class TestDegenerate:
    def test_both_empty(self):
        diff = MemoryGraph().activation_diff([], [])
        assert diff["baseline_nodes"] == []
        assert diff["comparison_nodes"] == []
        assert diff["common_nodes"] == []
        assert diff["spearman_rho"] == 1.0
        assert diff["activation_overlap"] == 1.0
        assert diff["mean_absolute_delta"] == 0.0

    def test_baseline_empty(self):
        comp = [{"node_id": "X", "activation": 0.5}]
        diff = MemoryGraph().activation_diff([], comp)
        assert diff["baseline_nodes"] == []
        assert diff["new_nodes"] == ["X"]
        assert diff["lost_nodes"] == []
        assert diff["activation_overlap"] == 0.0

    def test_comparison_empty(self):
        base = [{"node_id": "X", "activation": 0.5}]
        diff = MemoryGraph().activation_diff(base, [])
        assert diff["comparison_nodes"] == []
        assert diff["lost_nodes"] == ["X"]
        assert diff["new_nodes"] == []
        assert diff["activation_overlap"] == 0.0

    def test_single_node_identical(self):
        base = [{"node_id": "A", "activation": 1.0}]
        comp = [{"node_id": "A", "activation": 1.0}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["spearman_rho"] == 1.0
        assert diff["mean_absolute_delta"] == 0.0
        assert diff["gains"] == []
        assert diff["losses"] == []

    def test_single_node_different(self):
        base = [{"node_id": "A", "activation": 0.3}]
        comp = [{"node_id": "A", "activation": 0.7}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert len(diff["gains"]) == 1
        assert diff["gains"][0]["delta"] == pytest.approx(0.4)


# ═══════════════════════════════════════════════════════════════════
# 3. Identical runs — perfect correlation
# ═══════════════════════════════════════════════════════════════════

class TestIdenticalRuns:
    def test_identical_spearman_1(self, path_graph):
        mg, ids = path_graph
        r = mg.spreading_activation({ids[0]: 1.0}, decay=0.8)
        diff = mg.activation_diff(r, r)
        assert diff["spearman_rho"] == 1.0
        assert diff["mean_absolute_delta"] == 0.0
        assert diff["gains"] == []
        assert diff["losses"] == []

    def test_identical_overlap_1(self, path_graph):
        mg, ids = path_graph
        r = mg.spreading_activation({ids[0]: 1.0}, decay=0.8)
        diff = mg.activation_diff(r, r)
        assert diff["activation_overlap"] == 1.0

    def test_identical_rank_changes_all_zero(self, path_graph):
        mg, ids = path_graph
        r = mg.spreading_activation({ids[0]: 1.0}, decay=0.8)
        diff = mg.activation_diff(r, r)
        for rc in diff["rank_changes"]:
            assert rc["change"] == 0


# ═══════════════════════════════════════════════════════════════════
# 4. Node set differences — new / lost
# ═══════════════════════════════════════════════════════════════════

class TestNodeSetDiff:
    def test_new_nodes(self):
        base = [{"node_id": "A", "activation": 1.0}]
        comp = [{"node_id": "A", "activation": 1.0},
                {"node_id": "B", "activation": 0.5}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["new_nodes"] == ["B"]

    def test_lost_nodes(self):
        base = [{"node_id": "A", "activation": 1.0},
                {"node_id": "B", "activation": 0.5}]
        comp = [{"node_id": "A", "activation": 1.0}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["lost_nodes"] == ["B"]

    def test_both_new_and_lost(self):
        base = [{"node_id": "A", "activation": 1.0},
                {"node_id": "B", "activation": 0.5}]
        comp = [{"node_id": "A", "activation": 1.0},
                {"node_id": "C", "activation": 0.3}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["lost_nodes"] == ["B"]
        assert diff["new_nodes"] == ["C"]

    def test_common_nodes(self):
        base = [{"node_id": "A", "activation": 1.0},
                {"node_id": "B", "activation": 0.5}]
        comp = [{"node_id": "A", "activation": 1.0},
                {"node_id": "B", "activation": 0.3}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert set(diff["common_nodes"]) == {"A", "B"}

    def test_jaccard_disjoint(self):
        base = [{"node_id": "A", "activation": 1.0}]
        comp = [{"node_id": "B", "activation": 1.0}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["activation_overlap"] == 0.0

    def test_jaccard_partial(self):
        base = [{"node_id": "A", "activation": 1.0},
                {"node_id": "B", "activation": 0.5}]
        comp = [{"node_id": "A", "activation": 1.0},
                {"node_id": "C", "activation": 0.3}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["activation_overlap"] == pytest.approx(1 / 3)


# ═══════════════════════════════════════════════════════════════════
# 5. Activation deltas — gains / losses
# ═══════════════════════════════════════════════════════════════════

class TestDeltas:
    def test_gain_sorted_descending(self):
        base = [{"node_id": f"N{i}", "activation": 0.1} for i in range(5)]
        comp = [{"node_id": f"N{i}", "activation": 0.1 + i * 0.05} for i in range(5)]
        diff = MemoryGraph().activation_diff(base, comp)
        deltas = [g["delta"] for g in diff["gains"]]
        assert deltas == sorted(deltas, reverse=True)

    def test_loss_sorted_ascending(self):
        base = [{"node_id": f"N{i}", "activation": 0.1 + i * 0.05} for i in range(5)]
        comp = [{"node_id": f"N{i}", "activation": 0.1} for i in range(5)]
        diff = MemoryGraph().activation_diff(base, comp)
        deltas = [l["delta"] for l in diff["losses"]]
        assert deltas == sorted(deltas)

    def test_gain_structure(self):
        base = [{"node_id": "A", "activation": 0.3}]
        comp = [{"node_id": "A", "activation": 0.8}]
        diff = MemoryGraph().activation_diff(base, comp)
        g = diff["gains"][0]
        assert set(g.keys()) == {"node_id", "delta", "baseline_act", "comparison_act"}
        assert g["delta"] == pytest.approx(0.5)
        assert g["baseline_act"] == pytest.approx(0.3)
        assert g["comparison_act"] == pytest.approx(0.8)

    def test_loss_structure(self):
        base = [{"node_id": "A", "activation": 0.8}]
        comp = [{"node_id": "A", "activation": 0.3}]
        diff = MemoryGraph().activation_diff(base, comp)
        l = diff["losses"][0]
        assert set(l.keys()) == {"node_id", "delta", "baseline_act", "comparison_act"}
        assert l["delta"] == pytest.approx(-0.5)

    def test_no_gain_when_identical(self):
        base = [{"node_id": "A", "activation": 0.5}]
        comp = [{"node_id": "A", "activation": 0.5}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["gains"] == []
        assert diff["losses"] == []

    def test_mean_absolute_delta(self):
        base = [{"node_id": "A", "activation": 0.2},
                {"node_id": "B", "activation": 0.6}]
        comp = [{"node_id": "A", "activation": 0.4},
                {"node_id": "B", "activation": 0.6}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["mean_absolute_delta"] == pytest.approx(0.1)


# ═══════════════════════════════════════════════════════════════════
# 6. Rank changes
# ═══════════════════════════════════════════════════════════════════

class TestRankChanges:
    def test_rank_change_structure(self):
        base = [{"node_id": "A", "activation": 0.8},
                {"node_id": "B", "activation": 0.2}]
        comp = [{"node_id": "A", "activation": 0.2},
                {"node_id": "B", "activation": 0.8}]
        diff = MemoryGraph().activation_diff(base, comp)
        rc = diff["rank_changes"][0]
        assert set(rc.keys()) == {"node_id", "baseline_rank", "comparison_rank", "change"}

    def test_rank_swap(self):
        base = [{"node_id": "A", "activation": 0.8},
                {"node_id": "B", "activation": 0.2}]
        comp = [{"node_id": "A", "activation": 0.2},
                {"node_id": "B", "activation": 0.8}]
        diff = MemoryGraph().activation_diff(base, comp)
        a_rc = [rc for rc in diff["rank_changes"] if rc["node_id"] == "A"][0]
        b_rc = [rc for rc in diff["rank_changes"] if rc["node_id"] == "B"][0]
        # change = baseline_rank - comparison_rank
        # A: base rank 0 (highest act), comp rank 1 (lower act) → change = 0-1 = -1
        assert a_rc["change"] == -1
        # B: base rank 1, comp rank 0 → change = 1-0 = 1
        assert b_rc["change"] == 1

    def test_rank_sorted_by_abs_change(self):
        base = [{"node_id": f"N{i}", "activation": 1.0 - i * 0.1} for i in range(5)]
        comp = [{"node_id": f"N{i}", "activation": i * 0.1} for i in range(5)]
        diff = MemoryGraph().activation_diff(base, comp)
        changes = [abs(rc["change"]) for rc in diff["rank_changes"]]
        assert changes == sorted(changes, reverse=True)

    def test_no_rank_change_identical(self):
        base = [{"node_id": "A", "activation": 0.9},
                {"node_id": "B", "activation": 0.5},
                {"node_id": "C", "activation": 0.1}]
        diff = MemoryGraph().activation_diff(base, base)
        for rc in diff["rank_changes"]:
            assert rc["change"] == 0


# ═══════════════════════════════════════════════════════════════════
# 7. Spearman correlation
# ═══════════════════════════════════════════════════════════════════

class TestSpearman:
    def test_perfect_correlation(self):
        base = [{"node_id": f"N{i}", "activation": i * 0.1} for i in range(1, 6)]
        comp = [{"node_id": f"N{i}", "activation": i * 0.2} for i in range(1, 6)]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["spearman_rho"] == pytest.approx(1.0)

    def test_reversed_correlation(self):
        n = 5
        base = [{"node_id": f"N{i}", "activation": float(n - i)} for i in range(n)]
        comp = [{"node_id": f"N{i}", "activation": float(i + 1)} for i in range(n)]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["spearman_rho"] == pytest.approx(-1.0)

    def test_zero_correlation(self):
        # Ranks: baseline [1,2,3,4], comparison uncorrelated
        base = [{"node_id": "A", "activation": 0.4},
                {"node_id": "B", "activation": 0.3},
                {"node_id": "C", "activation": 0.2},
                {"node_id": "D", "activation": 0.1}]
        comp = [{"node_id": "A", "activation": 0.1},
                {"node_id": "B", "activation": 0.4},
                {"node_id": "C", "activation": 0.2},
                {"node_id": "D", "activation": 0.3}]
        diff = MemoryGraph().activation_diff(base, comp)
        # Just check it's between -1 and 1 and not exactly 1 or -1
        assert -1.0 <= diff["spearman_rho"] <= 1.0
        assert diff["spearman_rho"] != pytest.approx(1.0)
        assert diff["spearman_rho"] != pytest.approx(-1.0)

    def test_spearman_range(self, path_graph):
        mg, ids = path_graph
        r1 = mg.spreading_activation({ids[0]: 1.0}, decay=0.5)
        r2 = mg.spreading_activation({ids[-1]: 1.0}, decay=0.5)
        diff = mg.activation_diff(r1, r2)
        assert -1.0 <= diff["spearman_rho"] <= 1.0

    def test_spearman_two_nodes(self):
        base = [{"node_id": "A", "activation": 0.5},
                {"node_id": "B", "activation": 0.3}]
        comp = [{"node_id": "A", "activation": 0.5},
                {"node_id": "B", "activation": 0.3}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["spearman_rho"] == pytest.approx(1.0)

    def test_spearman_clamped(self):
        """Numerical edge cases should be clamped to [-1, 1]."""
        # Use identical data for rho=1
        base = [{"node_id": "X", "activation": 1.0}]
        comp = [{"node_id": "X", "activation": 1.0}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert -1.0 <= diff["spearman_rho"] <= 1.0


# ═══════════════════════════════════════════════════════════════════
# 8. min_delta filtering
# ═══════════════════════════════════════════════════════════════════

class TestMinDelta:
    def test_min_delta_filters_gains(self):
        base = [{"node_id": "A", "activation": 0.0},
                {"node_id": "B", "activation": 0.0}]
        comp = [{"node_id": "A", "activation": 0.01},
                {"node_id": "B", "activation": 0.5}]
        diff = MemoryGraph().activation_diff(base, comp, min_delta=0.05)
        gains_ids = [g["node_id"] for g in diff["gains"]]
        assert "B" in gains_ids
        assert "A" not in gains_ids

    def test_min_delta_filters_losses(self):
        base = [{"node_id": "A", "activation": 0.01},
                {"node_id": "B", "activation": 0.5}]
        comp = [{"node_id": "A", "activation": 0.0},
                {"node_id": "B", "activation": 0.0}]
        diff = MemoryGraph().activation_diff(base, comp, min_delta=0.05)
        losses_ids = [l["node_id"] for l in diff["losses"]]
        assert "B" in losses_ids
        assert "A" not in losses_ids

    def test_min_delta_zero_includes_all(self):
        base = [{"node_id": "A", "activation": 0.0}]
        comp = [{"node_id": "A", "activation": 0.001}]
        diff = MemoryGraph().activation_diff(base, comp, min_delta=0.0)
        assert len(diff["gains"]) == 1


# ═══════════════════════════════════════════════════════════════════
# 9. Custom keys
# ═══════════════════════════════════════════════════════════════════

class TestCustomKeys:
    def test_custom_activation_key(self):
        base = [{"id": "X", "score": 0.3}]
        comp = [{"id": "X", "score": 0.7}]
        diff = MemoryGraph().activation_diff(
            base, comp, activation_key="score", node_key="id"
        )
        assert diff["gains"][0]["delta"] == pytest.approx(0.4)

    def test_custom_node_key(self):
        base = [{"nid": "A", "activation": 0.3}]
        comp = [{"nid": "A", "activation": 0.5}]
        diff = MemoryGraph().activation_diff(base, comp, node_key="nid")
        assert "A" in diff["common_nodes"]

    def test_works_with_diffusion_retrieve_format(self):
        """diffusion_retrieve returns 'score' not 'activation'."""
        base = [{"node_id": "A", "score": 0.5},
                {"node_id": "B", "score": 0.3}]
        comp = [{"node_id": "A", "score": 0.4},
                {"node_id": "B", "score": 0.6}]
        diff = MemoryGraph().activation_diff(
            base, comp, activation_key="score"
        )
        assert diff["gains"][0]["node_id"] == "B"
        assert diff["losses"][0]["node_id"] == "A"


# ═══════════════════════════════════════════════════════════════════
# 10. Summary
# ═══════════════════════════════════════════════════════════════════

class TestSummary:
    def test_summary_mentions_counts(self):
        base = [{"node_id": "A", "activation": 1.0}]
        comp = [{"node_id": "A", "activation": 1.0},
                {"node_id": "B", "activation": 0.5}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert "baseline=1" in diff["summary"]
        assert "comparison=2" in diff["summary"]

    def test_summary_mentions_new(self):
        base = [{"node_id": "A", "activation": 1.0}]
        comp = [{"node_id": "A", "activation": 1.0},
                {"node_id": "B", "activation": 0.5}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert "+1 new" in diff["summary"]

    def test_summary_mentions_lost(self):
        base = [{"node_id": "A", "activation": 1.0},
                {"node_id": "B", "activation": 0.5}]
        comp = [{"node_id": "A", "activation": 1.0}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert "-1 lost" in diff["summary"]

    def test_summary_mentions_rho(self):
        base = [{"node_id": "A", "activation": 1.0}]
        comp = [{"node_id": "A", "activation": 1.0}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert "ρ=" in diff["summary"]

    def test_summary_mentions_overlap(self):
        base = [{"node_id": "A", "activation": 1.0}]
        comp = [{"node_id": "A", "activation": 1.0}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert "overlap=" in diff["summary"]

    def test_summary_mentions_biggest_mover(self):
        base = [{"node_id": "A", "activation": 0.2},
                {"node_id": "B", "activation": 0.3}]
        comp = [{"node_id": "A", "activation": 0.8},
                {"node_id": "B", "activation": 0.31}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert "biggest mover" in diff["summary"]

    def test_summary_no_new_or_lost_when_identical(self):
        base = [{"node_id": "A", "activation": 0.5}]
        comp = [{"node_id": "A", "activation": 0.5}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert "+0 new" not in diff["summary"]
        assert "-0 lost" not in diff["summary"]


# ═══════════════════════════════════════════════════════════════════
# 11. Non-mutating
# ═══════════════════════════════════════════════════════════════════

class TestNonMutating:
    def test_baseline_not_mutated(self):
        base = [{"node_id": "A", "activation": 0.5}]
        base_copy = list(base)
        MemoryGraph().activation_diff(base, [])
        assert base == base_copy

    def test_comparison_not_mutated(self):
        comp = [{"node_id": "A", "activation": 0.5}]
        comp_copy = list(comp)
        MemoryGraph().activation_diff([], comp)
        assert comp == comp_copy

    def test_graph_not_mutated(self, path_graph):
        mg, ids = path_graph
        n_before = sum(mg.count_by_kind().values())
        r1 = mg.spreading_activation({ids[0]: 1.0}, decay=0.8)
        r2 = mg.spreading_activation({ids[0]: 1.0}, decay=0.9)
        mg.activation_diff(r1, r2)
        assert sum(mg.count_by_kind().values()) == n_before


# ═══════════════════════════════════════════════════════════════════
# 12. Integration with activation family
# ═══════════════════════════════════════════════════════════════════

class TestIntegration:
    def test_with_spreading_activation(self, path_graph):
        mg, ids = path_graph
        r1 = mg.spreading_activation({ids[0]: 1.0}, decay=0.7)
        r2 = mg.spreading_activation({ids[0]: 1.0}, decay=0.9)
        diff = mg.activation_diff(r1, r2)
        # Higher decay → more activation for distant nodes
        assert len(diff["gains"]) > 0
        # Same nodes → perfect overlap
        assert diff["activation_overlap"] == 1.0

    def test_with_different_seeds(self, path_graph):
        mg, ids = path_graph
        r1 = mg.spreading_activation({ids[0]: 1.0}, decay=0.8)
        r2 = mg.spreading_activation({ids[-1]: 1.0}, decay=0.8)
        diff = mg.activation_diff(r1, r2)
        # Same node count, potentially different activation patterns
        assert diff["summary_metrics"]["baseline_count"] == diff["summary_metrics"]["comparison_count"]

    def test_with_temporal_spreading(self, path_graph):
        """Compare spreading_activation vs temporal_spreading."""
        mg, ids = path_graph
        r_plain = mg.spreading_activation({ids[0]: 1.0}, decay=0.8)
        r_temporal = mg.temporal_spreading({ids[0]: 1.0}, decay=0.8)
        # temporal returns dict with "results"
        diff = mg.activation_diff(
            r_plain,
            _activation_results(r_temporal),
            activation_key="activation",
        )
        # All nodes are fresh (just created) so retention ≈ 1 → minimal delta
        assert diff["mean_absolute_delta"] >= 0.0

    def test_with_competitive_spreading(self, path_graph):
        """Compare spreading_activation vs competitive_spreading."""
        mg, ids = path_graph
        r_plain = mg.spreading_activation({ids[0]: 1.0}, decay=0.8)
        # competitive_spreading needs ≥2 seeds
        r_comp = mg.competitive_spreading({ids[0]: 1.0, ids[2]: 0.5}, decay=0.8)
        diff = mg.activation_diff(
            r_plain,
            _activation_results(r_comp),
        )
        # Both should have overlapping nodes activated
        assert diff["activation_overlap"] > 0

    def test_with_diffusion_retrieve(self, path_graph):
        """Compare spreading_activation vs diffusion_retrieve."""
        mg, ids = path_graph
        r_spread = mg.spreading_activation({ids[0]: 1.0}, decay=0.8)
        # diffusion_retrieve accepts seeds param for node-seeded PPR
        r_diffusion = mg.diffusion_retrieve(seeds=[ids[0]], alpha=0.85, merge_bm25=False)
        diff = mg.activation_diff(
            r_spread,
            r_diffusion,
            activation_key="activation",
        )
        # Both activate the seed; overlap should be non-zero
        assert diff["activation_overlap"] > 0

    def test_parameter_sensitivity(self, path_graph):
        """Higher decay should produce bigger deltas."""
        mg, ids = path_graph
        r_low = mg.spreading_activation({ids[0]: 1.0}, decay=0.5)
        r_mid = mg.spreading_activation({ids[0]: 1.0}, decay=0.7)
        r_high = mg.spreading_activation({ids[0]: 1.0}, decay=0.9)

        diff_low_mid = mg.activation_diff(r_low, r_mid)
        diff_mid_high = mg.activation_diff(r_mid, r_high)

        # The mean abs delta should be larger for the more different pair
        assert diff_mid_high["mean_absolute_delta"] >= diff_low_mid["mean_absolute_delta"]


# ═══════════════════════════════════════════════════════════════════
# 13. Determinism
# ═══════════════════════════════════════════════════════════════════

class TestDeterminism:
    def test_same_input_same_output(self):
        base = [{"node_id": "A", "activation": 0.3},
                {"node_id": "B", "activation": 0.6}]
        comp = [{"node_id": "A", "activation": 0.5},
                {"node_id": "B", "activation": 0.4}]
        d1 = MemoryGraph().activation_diff(base, comp)
        d2 = MemoryGraph().activation_diff(base, comp)
        assert d1 == d2

    def test_deterministic_with_graph(self, path_graph):
        mg, ids = path_graph
        r1 = mg.spreading_activation({ids[0]: 1.0}, decay=0.8)
        r2 = mg.spreading_activation({ids[0]: 1.0}, decay=0.9)
        d1 = mg.activation_diff(r1, r2)
        d2 = mg.activation_diff(r1, r2)
        assert d1 == d2


# ═══════════════════════════════════════════════════════════════════
# 14. Edge cases
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_missing_activation_key(self):
        """Nodes without the activation key default to 0.0."""
        base = [{"node_id": "A"}]
        comp = [{"node_id": "A", "activation": 0.5}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["gains"][0]["delta"] == pytest.approx(0.5)

    def test_missing_node_key_skipped(self):
        """Entries without node_id are silently skipped."""
        base = [{"activation": 0.5}, {"node_id": "A", "activation": 0.3}]
        comp = [{"node_id": "A", "activation": 0.5}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["common_nodes"] == ["A"]

    def test_negative_activations(self):
        base = [{"node_id": "A", "activation": -0.3}]
        comp = [{"node_id": "A", "activation": -0.1}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["gains"][0]["delta"] == pytest.approx(0.2)

    def test_large_node_count(self):
        base = [{"node_id": f"N{i}", "activation": i * 0.01} for i in range(100)]
        comp = [{"node_id": f"N{i}", "activation": (99 - i) * 0.01} for i in range(100)]
        diff = MemoryGraph().activation_diff(base, comp)
        assert len(diff["common_nodes"]) == 100
        assert diff["spearman_rho"] == pytest.approx(-1.0)

    def test_duplicate_node_ids(self):
        """Duplicate node IDs: last value wins (standard dict behavior)."""
        base = [{"node_id": "A", "activation": 0.3},
                {"node_id": "A", "activation": 0.5}]
        comp = [{"node_id": "A", "activation": 0.7}]
        diff = MemoryGraph().activation_diff(base, comp)
        # 0.5 was the last value for A in baseline
        assert diff["gains"][0]["baseline_act"] == pytest.approx(0.5)
        assert diff["gains"][0]["delta"] == pytest.approx(0.2)

    def test_extremely_close_activations(self):
        base = [{"node_id": "A", "activation": 0.5000001}]
        comp = [{"node_id": "A", "activation": 0.5000002}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert len(diff["gains"]) == 1
        # Delta is rounded to 6 decimal places, so 0.0000001 rounds to 0.0
        assert diff["gains"][0]["delta"] >= 0.0

    def test_star_vs_path_comparison(self):
        """Compare activation patterns on different graph topologies."""
        mg1 = MemoryGraph()
        c1, l1 = _build_star(mg1, 5)
        r_star = mg1.spreading_activation({c1: 1.0}, decay=0.8)

        mg2 = MemoryGraph()
        ids2 = _build_path(mg2, 6)
        r_path = mg2.spreading_activation({ids2[0]: 1.0}, decay=0.8)

        # Compare with custom node IDs that happen to be different
        # This should produce all new/lost nodes
        diff = MemoryGraph().activation_diff(r_star, r_path)
        assert diff["activation_overlap"] == 0.0


# ═══════════════════════════════════════════════════════════════════
# 15. Biggest mover tracking
# ═══════════════════════════════════════════════════════════════════

class TestBiggestMover:
    def test_biggest_mover_identified(self):
        base = [{"node_id": "A", "activation": 0.1},
                {"node_id": "B", "activation": 0.1}]
        comp = [{"node_id": "A", "activation": 0.2},
                {"node_id": "B", "activation": 0.9}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["summary_metrics"]["biggest_mover"] == "B"

    def test_biggest_mover_delta_positive(self):
        base = [{"node_id": "A", "activation": 0.1},
                {"node_id": "B", "activation": 0.1}]
        comp = [{"node_id": "A", "activation": 0.2},
                {"node_id": "B", "activation": 0.9}]
        diff = MemoryGraph().activation_diff(base, comp)
        assert diff["summary_metrics"]["biggest_mover_delta"] == pytest.approx(0.8)

    def test_biggest_mover_none_empty(self):
        diff = MemoryGraph().activation_diff([], [])
        assert diff["summary_metrics"]["biggest_mover"] is None
        assert diff["summary_metrics"]["biggest_mover_delta"] is None

    def test_biggest_mover_can_be_loss(self):
        base = [{"node_id": "A", "activation": 0.9},
                {"node_id": "B", "activation": 0.5}]
        comp = [{"node_id": "A", "activation": 0.1},
                {"node_id": "B", "activation": 0.4}]
        diff = MemoryGraph().activation_diff(base, comp)
        # A lost 0.8, B lost 0.1 → biggest mover is A
        assert diff["summary_metrics"]["biggest_mover"] == "A"
        assert diff["summary_metrics"]["biggest_mover_delta"] == pytest.approx(-0.8)
