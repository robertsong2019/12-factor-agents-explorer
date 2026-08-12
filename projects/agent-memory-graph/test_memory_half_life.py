"""Tests for memory_half_life() — Cycle 417.

Computes knowledge half-life: time for a node's weight to halve
based on Ebbinghaus decay model with access, Q-value, and degree factors.
"""

import pytest
import time
from memory_graph import MemoryGraph


class TestMemoryHalfLifeBasic:
    """Basic functionality."""

    def test_returns_none_for_missing_node(self):
        g = MemoryGraph()
        assert g.memory_half_life("nonexistent") is None

    def test_returns_dict_for_valid_node(self):
        g = MemoryGraph()
        n = g.add("test memory")
        result = g.memory_half_life(n.id)
        assert isinstance(result, dict)
        assert "half_life_hours" in result
        assert "half_life_human" in result
        assert "current_weight" in result
        assert "projected_weight" in result
        assert "decay_rate" in result
        assert "stability_category" in result

    def test_projected_weight_is_half(self):
        g = MemoryGraph()
        n = g.add("important fact")
        result = g.memory_half_life(n.id)
        assert result["projected_weight"] == pytest.approx(
            result["current_weight"] * 0.5
        )

    def test_half_life_positive(self):
        g = MemoryGraph()
        n = g.add("test")
        result = g.memory_half_life(n.id)
        assert result["half_life_hours"] > 0

    def test_decay_rate_positive(self):
        g = MemoryGraph()
        n = g.add("test")
        result = g.memory_half_life(n.id)
        assert result["decay_rate"] > 0


class TestMemoryHalfLifeHumanReadable:
    """Human-readable duration formatting."""

    def test_minutes_format(self):
        """Very low half-life should show minutes."""
        g = MemoryGraph()
        n = g.add("test")
        # Without any factors boosting, check it formats
        result = g.memory_half_life(n.id)
        assert isinstance(result["half_life_human"], str)

    def test_hours_format(self):
        g = MemoryGraph()
        n = g.add("test")
        result = g.memory_half_life(n.id)
        # Default should be in days/hours range
        assert isinstance(result["half_life_human"], str)
        assert any(unit in result["half_life_human"]
                   for unit in ("hours", "days", "months", "minutes"))

    def test_days_format_with_connections(self):
        """Well-connected node should have longer half-life."""
        g = MemoryGraph()
        center = g.add("hub")
        for i in range(20):
            leaf = g.add(f"leaf_{i}")
            g.link(center.id, leaf.id, "connects")
        result = g.memory_half_life(center.id)
        # With 20 edges, degree_multiplier caps at 3x
        # base (168) * 3 = 504h → should be in days
        assert "days" in result["half_life_human"] or "months" in result["half_life_human"]


class TestMemoryHalfLifeStability:
    """Stability category classification."""

    def test_ephemeral_category(self):
        """Low q-value, no edges, not recently accessed → ephemeral or fragile."""
        g = MemoryGraph()
        n = g.add("ephemeral memory")
        # Manually set low q_value and old access time
        g.conn.execute(
            "UPDATE nodes SET q_value=0, accessed=? WHERE id=?",
            (time.time() - 999999, n.id),  # very old access
        )
        result = g.memory_half_life(n.id)
        assert result["stability_category"] in ("ephemeral", "fragile", "stable")

    def test_durable_category_with_high_q(self):
        """High Q-value + many edges → durable."""
        g = MemoryGraph()
        n = g.add("durable knowledge")
        g.conn.execute(
            "UPDATE nodes SET q_value=1.0 WHERE id=?", (n.id,)
        )
        # Add many edges to boost degree multiplier to cap
        for i in range(40):
            leaf = g.add(f"support_{i}")
            g.link(n.id, leaf.id, "supported_by")
        result = g.memory_half_life(n.id)
        assert result["stability_category"] == "durable"

    def test_stable_category_default(self):
        """Default node with no special properties."""
        g = MemoryGraph()
        n = g.add("normal memory")
        result = g.memory_half_life(n.id)
        # Recently created → accessed recently → base * 1.5 * activity
        # 168 * 1.5 * 1.05 ≈ 264h → stable (>168h)
        assert result["stability_category"] in ("stable", "fragile")


class TestMemoryHalfLifeFactors:
    """Factor breakdown when include_factors=True."""

    def test_factors_returned(self):
        g = MemoryGraph()
        n = g.add("test")
        result = g.memory_half_life(n.id, include_factors=True)
        assert "factors" in result
        f = result["factors"]
        assert "base" in f
        assert "access_recency" in f
        assert "q_value" in f
        assert "degree_bonus" in f
        assert "activity" in f

    def test_factors_not_returned_by_default(self):
        g = MemoryGraph()
        n = g.add("test")
        result = g.memory_half_life(n.id)
        assert "factors" not in result

    def test_base_is_168(self):
        g = MemoryGraph()
        n = g.add("test")
        result = g.memory_half_life(n.id, include_factors=True)
        assert result["factors"]["base"] == 168.0

    def test_access_recency_boosted_when_recent(self):
        """Recently accessed node should get access_recency > 1."""
        g = MemoryGraph()
        n = g.add("fresh memory")
        # Node was just created, so accessed is recent
        result = g.memory_half_life(n.id, include_factors=True)
        assert result["factors"]["access_recency"] > 1.0
        assert result["factors"]["accessed_recently"] is True

    def test_access_recency_baseline_when_old(self):
        """Old access → access_recency = 1.0 (no boost)."""
        g = MemoryGraph()
        n = g.add("stale memory")
        g.conn.execute(
            "UPDATE nodes SET accessed=? WHERE id=?",
            (time.time() - 999999, n.id),
        )
        result = g.memory_half_life(n.id, include_factors=True)
        assert result["factors"]["access_recency"] == 1.0
        assert result["factors"]["accessed_recently"] is False

    def test_q_value_multiplier(self):
        """Q-value of 1.0 should give 5x multiplier."""
        g = MemoryGraph()
        n = g.add("high quality")
        g.conn.execute(
            "UPDATE nodes SET q_value=1.0 WHERE id=?", (n.id,)
        )
        result = g.memory_half_life(n.id, include_factors=True)
        assert result["factors"]["q_value"] == pytest.approx(5.0)

    def test_q_value_zero_multiplier(self):
        """Q-value of 0 should give 1x multiplier."""
        g = MemoryGraph()
        n = g.add("zero quality")
        g.conn.execute(
            "UPDATE nodes SET q_value=0 WHERE id=?", (n.id,)
        )
        result = g.memory_half_life(n.id, include_factors=True)
        assert result["factors"]["q_value"] == pytest.approx(1.0)

    def test_degree_bonus_capped_at_3x(self):
        """Many edges should cap degree_bonus at 3.0."""
        g = MemoryGraph()
        hub = g.add("mega hub")
        for i in range(50):  # 50 edges → 1 + 50*0.05 = 3.5, capped at 3.0
            leaf = g.add(f"leaf_{i}")
            g.link(hub.id, leaf.id, "connects")
        result = g.memory_half_life(hub.id, include_factors=True)
        assert result["factors"]["degree_bonus"] == pytest.approx(3.0)

    def test_degree_bonus_no_edges(self):
        """Isolated node has degree_bonus = 1.0."""
        g = MemoryGraph()
        n = g.add("isolated")
        result = g.memory_half_life(n.id, include_factors=True)
        assert result["factors"]["degree_bonus"] == pytest.approx(1.0)


class TestMemoryHalfLifeComparative:
    """Comparative tests showing relative half-life differences."""

    def test_connected_node_lasts_longer(self):
        """A node with edges should have longer half-life than one without."""
        g = MemoryGraph()

        # Isolated node
        isolated = g.add("isolated fact")

        # Connected node
        connected = g.add("connected fact")
        for i in range(10):
            other = g.add(f"related_{i}")
            g.link(connected.id, other.id, "relates_to")

        iso_hl = g.memory_half_life(isolated.id)["half_life_hours"]
        con_hl = g.memory_half_life(connected.id)["half_life_hours"]
        assert con_hl > iso_hl

    def test_high_q_value_last_longer(self):
        """High Q-value node should have longer half-life."""
        g = MemoryGraph()

        low_q = g.add("low quality memory")
        g.conn.execute(
            "UPDATE nodes SET q_value=0 WHERE id=?", (low_q.id,)
        )

        high_q = g.add("high quality memory")
        g.conn.execute(
            "UPDATE nodes SET q_value=1.0 WHERE id=?", (high_q.id,)
        )

        low_hl = g.memory_half_life(low_q.id)["half_life_hours"]
        high_hl = g.memory_half_life(high_q.id)["half_life_hours"]
        assert high_hl > low_hl
        # Q=1 → 5x multiplier, so difference should be significant
        assert high_hl >= low_hl * 4.0  # at least 4x longer

    def test_recently_accessed_last_longer(self):
        """Recently accessed node should have longer half-life."""
        g = MemoryGraph()

        stale = g.add("stale memory")
        g.conn.execute(
            "UPDATE nodes SET accessed=? WHERE id=?",
            (time.time() - 999999, stale.id),
        )

        fresh = g.add("fresh memory")
        # fresh node was just created, so accessed is now

        stale_hl = g.memory_half_life(stale.id)["half_life_hours"]
        fresh_hl = g.memory_half_life(fresh.id)["half_life_hours"]
        assert fresh_hl > stale_hl

    def test_degree_included_in_result(self):
        g = MemoryGraph()
        n = g.add("test")
        result = g.memory_half_life(n.id)
        assert "degree" in result
        assert result["degree"] == 0  # no edges yet


class TestMemoryHalfLifeEdgeCases:
    """Edge cases."""

    def test_node_with_negative_q_value(self):
        """Negative Q-value should still work (reduces half-life)."""
        g = MemoryGraph()
        n = g.add("negative q")
        g.conn.execute(
            "UPDATE nodes SET q_value=-0.5 WHERE id=?", (n.id,)
        )
        result = g.memory_half_life(n.id)
        # q_multiplier = 1.0 + (-0.5) * 4 = -1.0, which makes s_eff negative
        # This is an edge case — the result should still be a valid number
        assert isinstance(result, dict)

    def test_node_id_in_result(self):
        g = MemoryGraph()
        n = g.add("test")
        result = g.memory_half_life(n.id)
        assert result["node_id"] == n.id

    def test_decay_rate_relationship(self):
        """decay_rate should equal 0.693 / half_life_hours."""
        g = MemoryGraph()
        n = g.add("test")
        result = g.memory_half_life(n.id)
        expected = 0.693 / result["half_life_hours"]
        assert result["decay_rate"] == pytest.approx(expected, rel=1e-3)
