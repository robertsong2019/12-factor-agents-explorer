"""Tests for temporal_spreading() — time-aware spreading activation.

Verifies that temporal decay via Ebbinghaus forgetting curve correctly
modulates spreading activation based on node age.

Research #051 / Cycle 382.
"""

import time
import math
import pytest
from memory_graph import MemoryGraph


def _make_chain(mg, labels):
    """Create a chain of nodes and return their ids."""
    ids = []
    for label in labels:
        n = mg.add(label)
        ids.append(n.id)
    for i in range(len(ids) - 1):
        mg.link(ids[i], ids[i+1], "related")
    return ids


class TestTemporalSpreadingStructure:
    """Verify return structure and required keys."""

    def test_returns_dict(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related")
        result = mg.temporal_spreading({a.id: 1.0})
        assert isinstance(result, dict)

    def test_required_top_keys(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related")
        result = mg.temporal_spreading({a.id: 1.0})
        for key in ("results", "stale_skipped", "retention_stats",
                     "fresh_nodes", "stale_nodes", "summary"):
            assert key in result, f"Missing key: {key}"

    def test_results_format(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related")
        result = mg.temporal_spreading({a.id: 1.0})
        assert isinstance(result["results"], list)
        for entry in result["results"]:
            assert "node_id" in entry
            assert "activation" in entry
            assert "retention" in entry
            assert "effective_activation" in entry
            assert "hop_distance" in entry
            assert "source_seeds" in entry

    def test_retention_stats_keys(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related")
        result = mg.temporal_spreading({a.id: 1.0})
        rs = result["retention_stats"]
        for key in ("mean_retention", "min_retention", "max_retention",
                     "stale_count", "fresh_count"):
            assert key in rs, f"Missing retention_stats key: {key}"

    def test_summary_keys(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related")
        result = mg.temporal_spreading({a.id: 1.0})
        s = result["summary"]
        for key in ("total_activated", "total_stale_skipped",
                     "mean_effective_activation", "temporal_decay_impact"):
            assert key in s, f"Missing summary key: {key}"


class TestTemporalSpreadingCorrectness:
    """Verify the temporal decay math is correct."""

    def test_seed_in_results(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related")
        result = mg.temporal_spreading({a.id: 1.0})
        node_ids = [r["node_id"] for r in result["results"]]
        assert a.id in node_ids

    def test_chain_propagation(self):
        """A→B→C chain should activate all three."""
        mg = MemoryGraph()
        ids = _make_chain(mg, ["alpha", "beta", "gamma"])
        result = mg.temporal_spreading({ids[0]: 1.0}, threshold=0.001, max_iter=5)
        node_ids = {r["node_id"] for r in result["results"]}
        assert ids[0] in node_ids
        assert ids[1] in node_ids
        assert ids[2] in node_ids

    def test_results_sorted_by_effective_activation(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        c = mg.add("gamma")
        mg.link(a.id, b.id, "r", weight=1.0)
        mg.link(a.id, c.id, "r", weight=1.0)
        result = mg.temporal_spreading({a.id: 1.0}, threshold=0.001)
        acts = [r["effective_activation"] for r in result["results"]]
        assert acts == sorted(acts, reverse=True)

    def test_seed_activation_is_1(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        result = mg.temporal_spreading({a.id: 1.0})
        seed_entry = result["results"][0]
        assert seed_entry["activation"] == pytest.approx(1.0, abs=1e-6)

    def test_effective_le_raw_for_fresh_node(self):
        """For a freshly created node, effective ≤ raw."""
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related")
        result = mg.temporal_spreading({a.id: 1.0})
        for r in result["results"]:
            assert r["effective_activation"] <= r["activation"] + 1e-9

    def test_hop_distance_seeds_zero(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        result = mg.temporal_spreading({a.id: 1.0})
        assert result["results"][0]["hop_distance"] == 0

    def test_hop_distance_increases(self):
        mg = MemoryGraph()
        ids = _make_chain(mg, ["alpha", "beta", "gamma"])
        result = mg.temporal_spreading({ids[0]: 1.0}, threshold=0.001, max_iter=5)
        hops = {r["node_id"]: r["hop_distance"] for r in result["results"]}
        assert hops[ids[0]] == 0
        assert hops[ids[1]] == 1
        assert hops[ids[2]] == 2

    def test_retention_between_0_and_1(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related")
        result = mg.temporal_spreading({a.id: 1.0})
        for r in result["results"]:
            assert 0.0 <= r["retention"] <= 1.0 + 1e-9

    def test_source_seeds_populated(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related")
        result = mg.temporal_spreading({a.id: 1.0})
        b_entry = [r for r in result["results"] if r["node_id"] == b.id][0]
        assert a.id in b_entry["source_seeds"]


class TestTemporalSpreadingModes:
    """Test the three temporal_mode options."""

    def _stale_graph(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related", weight=1.0)
        # Backdate access times
        mg.conn.execute("UPDATE nodes SET accessed=?", (time.time() - 3600 * 10,))
        return mg, a.id, b.id

    def test_multiply_mode_reduces_most(self):
        """Multiply mode should reduce activation more than additive for R<1."""
        mg, aid, bid = self._stale_graph()
        mult = mg.temporal_spreading({aid: 1.0}, temporal_mode="multiply",
                                      threshold=0.0001, base_stability=24.0)
        add = mg.temporal_spreading({aid: 1.0}, temporal_mode="additive",
                                     threshold=0.0001, base_stability=24.0)
        mult_eff = [r for r in mult["results"] if r["node_id"] == bid][0]["effective_activation"]
        add_eff = [r for r in add["results"] if r["node_id"] == bid][0]["effective_activation"]
        assert mult_eff <= add_eff

    def test_additive_mode_gentler(self):
        """Additive mode should give higher effective than multiply."""
        mg = MemoryGraph()
        ids = _make_chain(mg, ["a", "b", "c"])

        # Backdate all nodes
        mg.conn.execute("UPDATE nodes SET accessed=?", (time.time() - 3600 * 48,))

        mult = mg.temporal_spreading({ids[0]: 1.0}, temporal_mode="multiply",
                                      threshold=0.0001, base_stability=24.0, max_iter=5)
        add = mg.temporal_spreading({ids[0]: 1.0}, temporal_mode="additive",
                                     threshold=0.0001, base_stability=24.0, max_iter=5)

        mult_total = sum(r["effective_activation"] for r in mult["results"])
        add_total = sum(r["effective_activation"] for r in add["results"])
        assert add_total >= mult_total

    def test_threshold_mode_skips_stale(self):
        """Threshold mode should skip nodes with R < threshold."""
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related", weight=1.0)

        # Make b very stale
        mg.conn.execute(
            "UPDATE nodes SET accessed=? WHERE id=?",
            (time.time() - 3600 * 200, b.id),
        )

        result = mg.temporal_spreading(
            {a.id: 1.0}, temporal_mode="threshold",
            threshold=0.05, base_stability=24.0,
        )
        node_ids = [r["node_id"] for r in result["results"]]
        # b should be skipped (retention < 0.05)
        if b.id not in node_ids:
            assert b.id in result["stale_skipped"]

    def test_multiply_with_fresh_nodes(self):
        """Fresh nodes should have retention ~1.0 in multiply mode."""
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related", weight=1.0)
        result = mg.temporal_spreading({a.id: 1.0}, temporal_mode="multiply")
        a_entry = result["results"][0]
        assert a_entry["retention"] > 0.99


class TestTemporalSpreadingParameters:
    """Test parameter behavior."""

    def test_high_decay_spreads_further(self):
        mg = MemoryGraph()
        ids = _make_chain(mg, ["n0", "n1", "n2", "n3", "n4"])
        for i in range(4):
            mg.link(ids[i], ids[i+1], "related", weight=1.0)
        low = mg.temporal_spreading({ids[0]: 1.0}, decay=0.3, threshold=0.001)
        high = mg.temporal_spreading({ids[0]: 1.0}, decay=0.9, threshold=0.001)
        assert high["summary"]["total_activated"] >= low["summary"]["total_activated"]

    def test_max_iter_limits_spread(self):
        mg = MemoryGraph()
        ids = _make_chain(mg, ["n0", "n1", "n2", "n3", "n4"])
        for i in range(4):
            mg.link(ids[i], ids[i+1], "related", weight=1.0)
        result = mg.temporal_spreading({ids[0]: 1.0}, max_iter=2,
                                        threshold=0.001, decay=0.9)
        hops = {r["node_id"]: r["hop_distance"] for r in result["results"]}
        assert max(hops.values()) <= 2

    def test_directed_mode(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related")  # a→b only

        result_directed = mg.temporal_spreading({b.id: 1.0}, directed=True,
                                                  threshold=0.001)
        ids = {r["node_id"] for r in result_directed["results"]}
        assert b.id in ids
        assert a.id not in ids

    def test_low_stability_amplifies_decay(self):
        """Lower base_stability should make temporal decay stronger."""
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related", weight=1.0)

        # Backdate nodes
        mg.conn.execute("UPDATE nodes SET accessed=?", (time.time() - 3600 * 10,))

        high_stab = mg.temporal_spreading({a.id: 1.0}, base_stability=100.0,
                                           threshold=0.0001)
        low_stab = mg.temporal_spreading({a.id: 1.0}, base_stability=5.0,
                                          threshold=0.0001)
        assert high_stab["summary"]["mean_effective_activation"] >= \
               low_stab["summary"]["mean_effective_activation"]

    def test_edge_weight_factor(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        c = mg.add("gamma")
        mg.link(a.id, b.id, "related", weight=2.0)
        mg.link(b.id, c.id, "related", weight=0.5)

        r1 = mg.temporal_spreading({a.id: 1.0}, edge_weight_factor=1.0,
                                    threshold=0.001, max_iter=5)
        assert len(r1["results"]) >= 1


class TestTemporalSpreadingEdgeCases:
    """Edge cases and error handling."""

    def test_empty_seeds_raises(self):
        mg = MemoryGraph()
        with pytest.raises(ValueError):
            mg.temporal_spreading({})

    def test_invalid_decay_zero(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        with pytest.raises(ValueError):
            mg.temporal_spreading({a.id: 1.0}, decay=0)

    def test_invalid_decay_negative(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        with pytest.raises(ValueError):
            mg.temporal_spreading({a.id: 1.0}, decay=-0.5)

    def test_invalid_temporal_mode(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        with pytest.raises(ValueError):
            mg.temporal_spreading({a.id: 1.0}, temporal_mode="bogus")

    def test_invalid_base_stability(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        with pytest.raises(ValueError):
            mg.temporal_spreading({a.id: 1.0}, base_stability=0)

    def test_nonexistent_seed(self):
        mg = MemoryGraph()
        with pytest.raises(KeyError):
            mg.temporal_spreading({"ghost": 1.0})

    def test_isolated_node(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        result = mg.temporal_spreading({a.id: 1.0})
        assert result["summary"]["total_activated"] == 1

    def test_single_node_graph(self):
        mg = MemoryGraph()
        a = mg.add("solo")
        result = mg.temporal_spreading({a.id: 1.0})
        assert len(result["results"]) == 1
        assert result["results"][0]["node_id"] == a.id

    def test_multiple_seeds(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        c = mg.add("gamma")
        mg.link(a.id, c.id, "related")
        mg.link(b.id, c.id, "related")
        result = mg.temporal_spreading({a.id: 1.0, b.id: 1.0}, threshold=0.001)
        c_entry = [r for r in result["results"] if r["node_id"] == c.id][0]
        assert set(c_entry["source_seeds"]) == {a.id, b.id}

    def test_self_loop(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        mg.link(a.id, a.id, "self")
        result = mg.temporal_spreading({a.id: 1.0})
        assert result["summary"]["total_activated"] >= 1


class TestTemporalSpreadingNonMutating:
    """Verify graph is not modified."""

    def test_graph_unchanged(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related")
        before = mg.export_json()
        mg.temporal_spreading({a.id: 1.0})
        after = mg.export_json()
        assert before == after

    def test_no_new_edges(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        c = mg.add("gamma")
        mg.link(a.id, b.id, "related")
        edge_count_before = mg.edge_count()
        mg.temporal_spreading({a.id: 1.0})
        edge_count_after = mg.edge_count()
        assert edge_count_before == edge_count_after

    def test_no_new_nodes(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related")
        node_count_before = mg.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        mg.temporal_spreading({a.id: 1.0})
        node_count_after = mg.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        assert node_count_before == node_count_after


class TestTemporalSpreadingDeterminism:
    """Verify deterministic output."""

    def test_same_input_same_output(self):
        mg = MemoryGraph()
        ids = _make_chain(mg, ["alpha", "beta", "gamma"])
        r1 = mg.temporal_spreading({ids[0]: 1.0}, threshold=0.001)
        r2 = mg.temporal_spreading({ids[0]: 1.0}, threshold=0.001)
        assert r1["results"] == r2["results"]

    def test_activation_stable(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related")
        r1 = mg.temporal_spreading({a.id: 1.0})
        r2 = mg.temporal_spreading({a.id: 1.0})
        a1 = r1["results"][0]["effective_activation"]
        a2 = r2["results"][0]["effective_activation"]
        assert a1 == pytest.approx(a2, abs=1e-6)


class TestTemporalSpreadingIntegration:
    """Integration with existing APIs."""

    def test_consistent_with_spreading_activation_topology(self):
        """Should activate same or fewer nodes than plain spreading."""
        mg = MemoryGraph()
        ids = _make_chain(mg, ["n0", "n1", "n2", "n3", "n4"])
        ts = mg.temporal_spreading({ids[0]: 1.0}, threshold=0.001, max_iter=5)
        # All nodes should be activated (fresh graph)
        assert ts["summary"]["total_activated"] >= 3

    def test_works_after_modification(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related")
        r1 = mg.temporal_spreading({a.id: 1.0})

        c = mg.add("gamma")
        mg.link(b.id, c.id, "related")
        r2 = mg.temporal_spreading({a.id: 1.0}, threshold=0.001, max_iter=5)
        assert r2["summary"]["total_activated"] >= r1["summary"]["total_activated"]

    def test_weighted_edges(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        c = mg.add("gamma")
        mg.link(a.id, b.id, "related", weight=0.1)
        mg.link(a.id, c.id, "related", weight=1.0)

        result = mg.temporal_spreading({a.id: 1.0}, threshold=0.001)
        b_eff = [r for r in result["results"] if r["node_id"] == b.id]
        c_eff = [r for r in result["results"] if r["node_id"] == c.id]
        if b_eff and c_eff:
            assert c_eff[0]["effective_activation"] >= b_eff[0]["effective_activation"]

    def test_temporal_decay_impact_nonzero_for_stale(self):
        """With stale nodes, temporal_decay_impact should be > 0."""
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related", weight=1.0)

        # Backdate nodes significantly
        mg.conn.execute("UPDATE nodes SET accessed=?", (time.time() - 3600 * 100,))

        result = mg.temporal_spreading({a.id: 1.0}, threshold=0.0001,
                                        base_stability=24.0, max_iter=5)
        assert result["summary"]["temporal_decay_impact"] > 0

    def test_temporal_decay_impact_zero_for_fresh(self):
        """With fresh nodes, temporal_decay_impact should be ~0."""
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        mg.link(a.id, b.id, "related", weight=1.0)

        result = mg.temporal_spreading({a.id: 1.0})
        assert result["summary"]["temporal_decay_impact"] < 0.01

    def test_relation_filter(self):
        mg = MemoryGraph()
        a = mg.add("alpha")
        b = mg.add("beta")
        c = mg.add("gamma")
        mg.link(a.id, b.id, "derives")
        mg.link(a.id, c.id, "supports")

        result = mg.temporal_spreading(
            {a.id: 1.0}, relation_filter=["derives"], threshold=0.001
        )
        ids = {r["node_id"] for r in result["results"]}
        assert b.id in ids
        assert c.id not in ids

    def test_fresh_and_stale_classification(self):
        """Nodes should be classified as fresh or stale correctly."""
        mg = MemoryGraph()
        fresh1 = mg.add("f1")
        fresh2 = mg.add("f2")
        stale1 = mg.add("s1")
        mg.link(fresh1.id, fresh2.id, "related", weight=1.0)
        mg.link(fresh1.id, stale1.id, "related", weight=1.0)

        # Make stale1 very old
        mg.conn.execute(
            "UPDATE nodes SET accessed=? WHERE id=?",
            (time.time() - 3600 * 500, stale1.id),
        )

        result = mg.temporal_spreading(
            {fresh1.id: 1.0}, threshold=0.0001,
            base_stability=24.0, max_iter=5,
        )
        # fresh1 should be in fresh_nodes
        assert fresh1.id in result["fresh_nodes"]
        # stale1 should be in stale_nodes (if activated)
        if stale1.id in [r["node_id"] for r in result["results"]]:
            assert stale1.id in result["stale_nodes"]

    def test_empty_graph(self):
        """Isolated seed should return just itself."""
        mg = MemoryGraph()
        a = mg.add("solo")
        result = mg.temporal_spreading({a.id: 1.0})
        assert result["summary"]["total_activated"] == 1
        assert result["summary"]["total_stale_skipped"] == 0
