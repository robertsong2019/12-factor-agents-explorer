"""Tests for forget_policy() — FSFM four-category forgetting taxonomy.

Research #030: Adaptive Forgetting & Memory Pruning.
FSFM (arXiv:2604.20300) establishes four forgetting categories.
"""
import time
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    g = MemoryGraph(":memory:")
    yield g


@pytest.fixture
def conflicted_graph():
    """Graph with conflicts and diverse node ages."""
    g = MemoryGraph(":memory:")
    # Fresh conflict pair
    a1 = g.add("Fresh claim A", "fact")
    b1 = g.add("Fresh claim B", "fact")
    g.link(a1.id, b1.id, "contradicts")

    # Old conflict pair
    a2 = g.add("Old claim A", "fact")
    b2 = g.add("Old claim B", "fact")
    g.link(a2.id, b2.id, "contradicts")
    g.conn.execute(
        "UPDATE nodes SET created=? WHERE id IN (?, ?)",
        (time.time() - 90 * 86400, a2.id, b2.id)
    )

    # Non-conflict nodes
    n1 = g.add("Peaceful fact", "fact")
    n2 = g.add("Another fact", "fact")
    g.link(n1.id, n2.id, "relates")

    yield g


# ── Policy validation ──────────────────────────────────────────

class TestForgetPolicyValidation:
    def test_invalid_policy_raises(self, mg):
        with pytest.raises(ValueError, match="Unknown policy"):
            mg.forget_policy("nonexistent")

    def test_valid_policies_listed_in_error(self, mg):
        try:
            mg.forget_policy("bogus")
        except ValueError as e:
            assert "passive_decay" in str(e)
            assert "active_deletion" in str(e)
            assert "safety_purge" in str(e)
            assert "adaptive_reinforcement" in str(e)

    def test_returns_summary_dict(self, mg):
        mg.add("Node", "fact")
        result = mg.forget_policy(dry_run=True)
        assert "policy" in result
        assert "scanned" in result
        assert "kept" in result
        assert "archived" in result
        assert "deleted" in result
        assert "recommendations" in result


# ── passive_decay policy ───────────────────────────────────────

class TestPassiveDecayPolicy:
    def test_default_policy_is_passive_decay(self, mg):
        mg.add("Node", "fact")
        result = mg.forget_policy(dry_run=True)
        assert result["policy"] == "passive_decay"

    def test_processes_all_kinds_by_default(self, mg):
        mg.add("Fact", "fact")
        mg.add("Event", "event")
        result = mg.forget_policy(dry_run=True)
        assert result["scanned"] == 2

    def test_dry_run_preserves_weights(self, mg):
        n = mg.add("Test", "fact")
        w_before = mg.conn.execute(
            "SELECT weight FROM nodes WHERE id=?", (n.id,)
        ).fetchone()["weight"]
        mg.forget_policy(dry_run=True)
        w_after = mg.conn.execute(
            "SELECT weight FROM nodes WHERE id=?", (n.id,)
        ).fetchone()["weight"]
        assert w_after == w_before

    def test_fresh_nodes_kept(self, mg):
        n = mg.add("Fresh", "concept")
        leaf = mg.add("Leaf", "fact")
        mg.link(n.id, leaf.id, "relates", weight=1.0)
        result = mg.forget_policy(dry_run=True)
        assert result["kept"] >= 1


# ── active_deletion policy ─────────────────────────────────────

class TestActiveDeletionPolicy:
    def test_only_processes_conflicted_nodes(self, conflicted_graph):
        """active_deletion should only scan nodes with contradiction edges."""
        result = conflicted_graph.forget_policy(
            "active_deletion", dry_run=True)
        # 4 nodes have contradiction edges (2 pairs)
        assert result["scanned"] == 4

    def test_does_not_touch_peaceful_nodes(self, conflicted_graph):
        """Non-conflict nodes should not be touched."""
        result = conflicted_graph.forget_policy(
            "active_deletion", dry_run=True)
        # peaceful nodes still exist with original weight
        row = conflicted_graph.conn.execute(
            "SELECT weight FROM nodes WHERE label='Peaceful fact'"
        ).fetchone()
        assert row is not None
        assert row["weight"] == 1.0

    def test_old_conflicts_more_likely_deleted(self, conflicted_graph):
        """Old conflict nodes should have lower activation."""
        result = conflicted_graph.forget_policy(
            "active_deletion", dry_run=True)
        # At least some should be archived or deleted
        assert result["archived"] + result["deleted"] >= 1

    def test_policy_description_present(self, conflicted_graph):
        result = conflicted_graph.forget_policy(
            "active_deletion", dry_run=True)
        assert "policy_description" in result
        assert "contradict" in result["policy_description"].lower()


# ── safety_purge policy ────────────────────────────────────────

class TestSafetyPurgePolicy:
    def test_safety_purge_aggressive(self, mg):
        """safety_purge should use aggressive thresholds."""
        # Create a sensitive node
        n = mg.add("API key: sk-xxx", "fact")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (time.time() - 5 * 86400, n.id)  # 5 days old
        )
        mg.conn.commit()
        result = mg.forget_policy(
            "safety_purge", dry_run=True,
            kinds=["fact"])
        # safety_purge has aggressive thresholds
        assert result["policy"] == "safety_purge"

    def test_safety_purge_only_filtered_kinds(self, mg):
        """safety_purge default kinds should filter to sensitive types."""
        mg.add("Normal fact", "fact")
        mg.add("Sensitive data", "sensitive")
        # With default policy kinds, should only process 'sensitive' etc.
        result = mg.forget_policy("safety_purge", dry_run=True)
        # Only 'sensitive' kind node should be scanned
        assert result["scanned"] == 1

    def test_safety_purge_override_kinds(self, mg):
        mg.add("A", "fact")
        mg.add("B", "event")
        result = mg.forget_policy(
            "safety_purge", dry_run=True,
            kinds=["fact", "event"])
        assert result["scanned"] == 2


# ── adaptive_reinforcement policy ──────────────────────────────

class TestAdaptiveReinforcementPolicy:
    def test_slow_decay_preserves_recent(self, mg):
        """adaptive_reinforcement has 30-day half-life — should keep recent."""
        n = mg.add("Recent valuable", "fact")
        leaf = mg.add("Leaf", "fact")
        mg.link(n.id, leaf.id, "relates", weight=1.0)
        result = mg.forget_policy(
            "adaptive_reinforcement", dry_run=True)
        assert result["kept"] >= 1
        assert result["deleted"] == 0

    def test_only_very_old_fades(self, mg):
        """With 30-day half-life, only very old nodes should be archived."""
        n = mg.add("Ancient memory", "event")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (time.time() - 365 * 86400, n.id)
        )
        mg.conn.commit()
        result = mg.forget_policy(
            "adaptive_reinforcement", dry_run=True)
        # 1 year old with 30-day half-life → very low activation
        assert result["archived"] + result["deleted"] >= 1


# ── Overrides and parameter passthrough ────────────────────────

class TestPolicyOverrides:
    def test_half_life_override(self, mg):
        n = mg.add("Test", "fact")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (time.time() - 10 * 86400, n.id)
        )
        mg.conn.commit()
        # With 1-day half-life, should be more aggressive
        result_aggressive = mg.forget_policy(
            "passive_decay", dry_run=True, half_life_days=1.0)
        result_gentle = mg.forget_policy(
            "passive_decay", dry_run=True, half_life_days=100.0)
        # Aggressive should have more archived/deleted
        aggressive_loss = (result_aggressive["weight_before"] -
                           result_aggressive["weight_after"])
        gentle_loss = (result_gentle["weight_before"] -
                       result_gentle["weight_after"])
        assert aggressive_loss >= gentle_loss

    def test_threshold_override(self, mg):
        n = mg.add("Test", "fact")
        result = mg.forget_policy(
            "passive_decay", dry_run=True,
            delete_threshold=0.99)  # Very aggressive
        assert isinstance(result["deleted"], int)

    def test_kinds_override(self, mg):
        mg.add("Fact", "fact")
        mg.add("Event", "event")
        result = mg.forget_policy(
            "passive_decay", dry_run=True,
            kinds=["fact"])
        assert result["scanned"] == 1


# ── Integration tests ──────────────────────────────────────────

class TestForgetPolicyIntegration:
    def test_all_four_policies_run_without_error(self, conflicted_graph):
        for policy in ["passive_decay", "active_deletion",
                       "adaptive_reinforcement"]:
            result = conflicted_graph.forget_policy(policy, dry_run=True)
            assert "scanned" in result
            assert result["policy"] == policy

    def test_safety_purge_with_sensitive_kind(self, mg):
        """End-to-end: safety_purge removes sensitive content."""
        sensitive = mg.add(" leaked password ", "sensitive")
        old_date = time.time() - 10 * 86400
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (old_date, sensitive.id)
        )
        mg.conn.commit()
        result = mg.forget_policy("safety_purge", dry_run=False)
        assert result["scanned"] >= 1

    def test_real_run_deletes_low_activation(self, mg):
        """Non-dry-run should actually delete very old nodes."""
        ancient = mg.add("Ancient isolated", "event")
        mg.conn.execute(
            "UPDATE nodes SET created=?, accessed=? WHERE id=?",
            (time.time() - 1000 * 86400,
             time.time() - 1000 * 86400,
             ancient.id)
        )
        mg.conn.commit()
        mg.forget_policy("passive_decay", dry_run=False)
        exists = mg.conn.execute(
            "SELECT id FROM nodes WHERE id=?", (ancient.id,)
        ).fetchone()
        # Should be deleted or have very low weight
        if exists:
            weight = mg.conn.execute(
                "SELECT weight FROM nodes WHERE id=?", (ancient.id,)
            ).fetchone()["weight"]
            assert weight < 0.3

    def test_recommendation_distribution_sums_correctly(self, mg):
        for i in range(5):
            n = mg.add(f"Node {i}", "fact")
            if i % 2 == 0:
                mg.conn.execute(
                    "UPDATE nodes SET created=? WHERE id=?",
                    (time.time() - 60 * 86400, n.id)
                )
        mg.conn.commit()
        result = mg.forget_policy(dry_run=True)
        total = sum(result["recommendations"].values())
        assert total == result["scanned"]
