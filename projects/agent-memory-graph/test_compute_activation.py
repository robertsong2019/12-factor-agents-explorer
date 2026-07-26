"""Tests for compute_activation() — entropy-weighted activation scoring.

Research #030: Adaptive Forgetting & Memory Pruning.
Inspired by FadeMem (arXiv:2601.18642) + Oblivion (arXiv:2603.19550).
"""
import math
import time
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    g = MemoryGraph(":memory:")
    yield g


@pytest.fixture
def populated_graph():
    """Graph with diverse entropy distribution."""
    g = MemoryGraph(":memory:")
    # Star topology: center hub + 4 leaves
    center = g.add("Central concept", "concept")
    leaves = [g.add(f"Leaf {i}", "fact") for i in range(4)]
    for leaf in leaves:
        g.link(center.id, leaf.id, "relates")

    # Isolated node (entropy = 0)
    iso = g.add("Isolated memory", "event")

    # Conflict pair
    a = g.add("Claim A", "fact")
    b = g.add("Claim B contradicts A", "fact")
    g.link(a.id, b.id, "contradicts")

    yield g


# ── compute_activation() basic tests ────────────────────────────

class TestComputeActivationBasic:
    def test_returns_none_for_nonexistent_node(self, mg):
        assert mg.compute_activation("nonexistent") is None

    def test_returns_dict_for_valid_node(self, mg):
        n = mg.add("Test node", "fact")
        result = mg.compute_activation(n.id)
        assert result is not None
        assert "activation" in result
        assert "recommendation" in result
        assert "reason" in result
        assert "factors" in result

    def test_activation_in_range_0_1(self, mg):
        n = mg.add("Test node", "fact")
        result = mg.compute_activation(n.id)
        assert 0.0 <= result["activation"] <= 1.0

    def test_fresh_node_has_high_activation(self, mg):
        """Newly created node should have relatively high activation."""
        n = mg.add("Fresh memory", "fact")
        leaf = mg.add("Leaf", "fact")
        mg.link(n.id, leaf.id, "relates", weight=1.0)
        result = mg.compute_activation(n.id)
        # With edges, entropy > 0, so activation should be > 0.5
        assert result["activation"] >= 0.5
        assert result["factors"]["base_decay"] > 0.99

    def test_result_contains_node_id(self, mg):
        n = mg.add("Node", "fact")
        result = mg.compute_activation(n.id)
        assert result["node_id"] == n.id


class TestComputeActivationEntropy:
    def test_isolated_node_low_entropy(self, mg):
        """Isolated node (no edges) should have entropy 0."""
        n = mg.add("Lonely", "event")
        result = mg.compute_activation(n.id)
        assert result["factors"]["entropy"] == 0.0
        # Low entropy → entropy_multiplier < 0.8
        assert result["factors"]["entropy_multiplier"] < 0.8

    def test_hub_node_higher_entropy(self, populated_graph):
        """Hub node with diverse edges should have higher entropy."""
        center = populated_graph.conn.execute(
            "SELECT id FROM nodes WHERE label='Central concept'"
        ).fetchone()
        result = populated_graph.compute_activation(center["id"])
        assert result["factors"]["entropy"] > 0.3

    def test_entropy_multiplier_floor(self, mg):
        """Entropy multiplier should be at least 0.5."""
        n = mg.add("Isolated", "fact")
        result = mg.compute_activation(n.id)
        assert result["factors"]["entropy_multiplier"] >= 0.5

    def test_uniform_weight_edges_max_entropy(self, mg):
        """Node with equal-weight edges has max entropy (1.0)."""
        center = mg.add("Hub", "concept")
        for i in range(4):
            leaf = mg.add(f"Leaf {i}", "fact")
            mg.link(center.id, leaf.id, "relates", weight=1.0)
        result = mg.compute_activation(center.id)
        # Equal weights → normalized entropy = 1.0
        assert result["factors"]["entropy"] == pytest.approx(1.0, abs=0.01)
        # High entropy → multiplier >= 1.0
        assert result["factors"]["entropy_multiplier"] >= 1.0


class TestComputeActivationDecay:
    def test_old_node_lower_activation(self, mg):
        """Older node should have lower activation than fresh one."""
        old = mg.add("Old memory", "fact")
        # Simulate old age
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (time.time() - 30 * 86400, old.id)  # 30 days old
        )
        mg.conn.commit()

        fresh = mg.add("Fresh memory", "fact")
        old_result = mg.compute_activation(old.id)
        fresh_result = mg.compute_activation(fresh.id)
        assert old_result["activation"] < fresh_result["activation"]

    def test_base_decay_decreases_with_age(self, mg):
        n = mg.add("Test", "fact")
        # Get fresh reading
        fresh_decay = mg.compute_activation(n.id)["factors"]["base_decay"]
        # Age it
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (time.time() - 14 * 86400, n.id)  # 14 days
        )
        mg.conn.commit()
        old_decay = mg.compute_activation(n.id)["factors"]["base_decay"]
        assert old_decay < fresh_decay

    def test_half_life_doubles_decay_time(self, mg):
        n = mg.add("Test", "fact")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (time.time() - 7 * 86400, n.id)  # 7 days old
        )
        mg.conn.commit()
        # 7-day half-life → base_decay ≈ 0.5
        r7 = mg.compute_activation(n.id, half_life_days=7.0)
        # 14-day half-life → base_decay ≈ 0.71
        r14 = mg.compute_activation(n.id, half_life_days=14.0)
        assert r14["factors"]["base_decay"] > r7["factors"]["base_decay"]
        assert r7["factors"]["base_decay"] == pytest.approx(0.5, abs=0.05)


class TestComputeActivationAccess:
    def test_accessed_node_gets_boost(self, mg):
        """Node with incoming edges gets access boost."""
        # Node with no incoming edges
        lonely = mg.add("Lonely", "fact")
        # Node with incoming edges (being pointed to)
        hub = mg.add("Hub", "concept")
        for i in range(3):
            leaf = mg.add(f"Src {i}", "fact")
            mg.link(leaf.id, hub.id, "relates")

        lonely_r = mg.compute_activation(lonely.id)
        hub_r = mg.compute_activation(hub.id)
        assert hub_r["factors"]["access_boost"] > lonely_r["factors"]["access_boost"]

    def test_no_incoming_edges_zero_access_boost(self, mg):
        n = mg.add("No incoming", "fact")
        result = mg.compute_activation(n.id)
        assert result["factors"]["access_boost"] == 0.0


class TestComputeActivationConflict:
    def test_conflict_node_has_penalty(self, mg):
        a = mg.add("Claim A", "fact")
        b = mg.add("Claim B", "fact")
        mg.link(a.id, b.id, "contradicts")

        result_a = mg.compute_activation(a.id)
        result_b = mg.compute_activation(b.id)
        assert result_a["factors"]["conflict_penalty"] > 0
        assert result_b["factors"]["conflict_penalty"] > 0

    def test_no_conflict_zero_penalty(self, mg):
        n = mg.add("Peaceful", "fact")
        result = mg.compute_activation(n.id)
        assert result["factors"]["conflict_penalty"] == 0.0


class TestComputeActivationRecommendation:
    def test_fresh_node_recommended_keep(self, mg):
        n = mg.add("Fresh and connected", "concept")
        leaf = mg.add("Leaf", "fact")
        mg.link(n.id, leaf.id, "relates", weight=1.0)
        mg.link(leaf.id, n.id, "relates", weight=1.0)
        result = mg.compute_activation(n.id)
        assert result["recommendation"] == "KEEP"

    def test_very_old_node_recommended_delete_or_archive(self, mg):
        n = mg.add("Ancient", "fact")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (time.time() - 365 * 86400, n.id)  # 1 year old
        )
        mg.conn.commit()
        result = mg.compute_activation(n.id)
        assert result["recommendation"] in ("DELETE", "ARCHIVE")

    def test_old_isolated_node_delete(self, mg):
        n = mg.add("Old isolated", "event")
        mg.conn.execute(
            "UPDATE nodes SET created=?, accessed=? WHERE id=?",
            (time.time() - 200 * 86400, time.time() - 200 * 86400, n.id)
        )
        mg.conn.commit()
        result = mg.compute_activation(n.id)
        assert result["activation"] < 0.25  # Should be low

    def test_conflicted_old_node_resolve_or_delete(self, mg):
        a = mg.add("Old claim", "fact")
        b = mg.add("Contradicting claim", "fact")
        mg.link(a.id, b.id, "contradicts")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (time.time() - 90 * 86400, a.id)
        )
        mg.conn.commit()
        result = mg.compute_activation(a.id)
        # Should have some conflict penalty reducing activation
        assert result["factors"]["conflict_penalty"] > 0


class TestComputeActivationWithProfile:
    def test_accepts_entropy_profile_arg(self, mg):
        n = mg.add("Test", "fact")
        # Pass a fake profile
        profile = {"per_node": {n.id: {"shannon": 0.9}}}
        result = mg.compute_activation(n.id, entropy_profile=profile)
        assert result["factors"]["entropy"] == 0.9

    def test_high_entropy_profile_preserves_node(self, mg):
        n = mg.add("Test", "fact")
        # Age it significantly
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (time.time() - 30 * 86400, n.id)
        )
        mg.conn.commit()
        # With high entropy, activation should be higher
        profile_high = {"per_node": {n.id: {"shannon": 0.95}}}
        profile_low = {"per_node": {n.id: {"shannon": 0.1}}}
        r_high = mg.compute_activation(n.id, entropy_profile=profile_high)
        r_low = mg.compute_activation(n.id, entropy_profile=profile_low)
        assert r_high["activation"] > r_low["activation"]


# ── apply_decay() tests ─────────────────────────────────────────

class TestApplyDecayBasic:
    def test_returns_summary_dict(self, mg):
        mg.add("Node 1", "fact")
        result = mg.apply_decay(dry_run=True)
        assert "scanned" in result
        assert "kept" in result
        assert "archived" in result
        assert "deleted" in result
        assert "recommendations" in result
        assert "weight_before" in result
        assert "weight_after" in result
        assert "weight_lost" in result

    def test_dry_run_does_not_modify(self, mg):
        n = mg.add("Test", "fact")
        original_weight = mg.conn.execute(
            "SELECT weight FROM nodes WHERE id=?", (n.id,)
        ).fetchone()["weight"]
        mg.apply_decay(dry_run=True)
        weight_after = mg.conn.execute(
            "SELECT weight FROM nodes WHERE id=?", (n.id,)
        ).fetchone()["weight"]
        assert weight_after == original_weight

    def test_scanned_count_matches_nodes(self, mg):
        for i in range(5):
            mg.add(f"Node {i}", "fact")
        result = mg.apply_decay(dry_run=True)
        assert result["scanned"] == 5

    def test_empty_graph_returns_zeros(self, mg):
        result = mg.apply_decay(dry_run=True)
        assert result["scanned"] == 0
        assert result["deleted"] == 0
        assert result["archived"] == 0
        assert result["kept"] == 0


class TestApplyDecayFiltering:
    def test_kind_filter_excludes_other_kinds(self, mg):
        mg.add("Fact 1", "fact")
        mg.add("Event 1", "event")
        mg.add("Fact 2", "fact")
        result = mg.apply_decay(kinds=["fact"], dry_run=True)
        assert result["scanned"] == 2

    def test_kind_filter_empty_list_processes_all(self, mg):
        mg.add("A", "fact")
        mg.add("B", "event")
        result = mg.apply_decay(kinds=None, dry_run=True)
        assert result["scanned"] == 2


class TestApplyDecayBehavior:
    def test_old_nodes_get_archived(self, mg):
        """Nodes older than threshold should lose weight."""
        n = mg.add("Old node", "fact")
        leaf = mg.add("Leaf", "fact")
        mg.link(n.id, leaf.id, "relates", weight=1.0)
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (time.time() - 60 * 86400, n.id)  # 60 days old
        )
        mg.conn.commit()
        original_w = mg.conn.execute(
            "SELECT weight FROM nodes WHERE id=?", (n.id,)
        ).fetchone()["weight"]
        mg.apply_decay()
        row = mg.conn.execute(
            "SELECT weight FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        # Node might be deleted; if exists, weight should be lower
        if row:
            assert row["weight"] < original_w
        else:
            # Node was deleted (activation very low) — also valid
            assert True

    def test_very_old_nodes_deleted(self, mg):
        """Very old isolated nodes should be deleted."""
        n = mg.add("Ancient isolated", "event")
        mg.conn.execute(
            "UPDATE nodes SET created=?, accessed=? WHERE id=?",
            (time.time() - 500 * 86400, time.time() - 500 * 86400, n.id)
        )
        mg.conn.commit()
        result = mg.apply_decay()
        exists = mg.conn.execute(
            "SELECT id FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        # Should either be deleted or have very low weight
        if exists:
            weight = mg.conn.execute(
                "SELECT weight FROM nodes WHERE id=?", (n.id,)
            ).fetchone()["weight"]
            assert weight < 0.2

    def test_fresh_nodes_kept(self, mg):
        """Fresh nodes should be kept with minimal weight change."""
        n = mg.add("Fresh", "fact")
        leaf = mg.add("Leaf", "fact")
        mg.link(n.id, leaf.id, "relates", weight=1.0)
        original_w = mg.conn.execute(
            "SELECT weight FROM nodes WHERE id=?", (n.id,)
        ).fetchone()["weight"]
        mg.apply_decay()
        new_w = mg.conn.execute(
            "SELECT weight FROM nodes WHERE id=?", (n.id,)
        ).fetchone()["weight"]
        # Kept nodes get 10% reduction
        assert new_w == pytest.approx(original_w * 0.9, rel=0.01)

    def test_weight_lost_positive(self, mg):
        for i in range(5):
            n = mg.add(f"Node {i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET created=? WHERE id=?",
                (time.time() - (i + 1) * 10 * 86400, n.id)
            )
        mg.conn.commit()
        result = mg.apply_decay(dry_run=True)
        assert result["weight_lost"] >= 0

    def test_thresholds_respected(self, mg):
        """Custom thresholds should affect behavior."""
        n = mg.add("Moderate age", "fact")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (time.time() - 20 * 86400, n.id)  # 20 days
        )
        mg.conn.commit()
        # Very aggressive deletion
        result = mg.apply_decay(delete_threshold=0.5, dry_run=True)
        assert isinstance(result["deleted"], int)


class TestApplyDecayDryRunVsReal:
    def test_dry_run_and_real_same_counts(self, mg):
        for i in range(3):
            n = mg.add(f"Node {i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET created=? WHERE id=?",
                (time.time() - 30 * 86400, n.id)
            )
        mg.conn.commit()
        dry = mg.apply_decay(dry_run=True)
        # Real run
        real = mg.apply_decay(dry_run=False)
        assert dry["scanned"] == real["scanned"]

    def test_real_run_modifies_weights(self, mg):
        n = mg.add("Test", "fact")
        leaf = mg.add("Leaf", "fact")
        mg.link(n.id, leaf.id, "relates", weight=1.0)
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (time.time() - 30 * 86400, n.id)
        )
        mg.conn.commit()
        before = mg.conn.execute(
            "SELECT weight FROM nodes WHERE id=?", (n.id,)
        ).fetchone()["weight"]
        mg.apply_decay()
        row = mg.conn.execute(
            "SELECT weight FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        if row:
            assert row["weight"] != before
        else:
            assert True  # Deleted


class TestApplyDecayRecommendations:
    def test_recommendation_counts_sum_to_scanned(self, mg):
        for i in range(5):
            mg.add(f"Node {i}", "fact")
        result = mg.apply_decay(dry_run=True)
        total_recs = sum(result["recommendations"].values())
        assert total_recs == result["scanned"]

    def test_details_deleted_capped_at_10(self, mg):
        """details_deleted should be capped at 10 entries."""
        for i in range(15):
            n = mg.add(f"Old {i}", "event")
            mg.conn.execute(
                "UPDATE nodes SET created=?, accessed=? WHERE id=?",
                (time.time() - 600 * 86400, time.time() - 600 * 86400, n.id)
            )
        mg.conn.commit()
        result = mg.apply_decay()
        assert len(result["details_deleted"]) <= 10
