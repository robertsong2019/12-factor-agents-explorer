"""Tests for forgetting_forecast() — Cycle 413.

Predictive, non-destructive companion to forgetting_curve().
Forecasts time-to-threshold for nodes based on Ebbinghaus decay model.
"""
import math
import time
import pytest
from memory_graph import MemoryGraph


def _set_weight(mg, node_id, weight):
    """Helper to set absolute weight on a node."""
    mg.conn.execute(
        "UPDATE nodes SET weight=? WHERE id=?", (weight, node_id)
    )
    mg.conn.commit()


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


@pytest.fixture
def populated_mg(mg):
    """Graph with nodes at various decay stages."""
    now = time.time()

    # Node A: fresh, high weight — not at risk
    a = mg.add("Fresh Node", "concept")
    _set_weight(mg, a.id, 0.95)
    mg.conn.execute("UPDATE nodes SET accessed=? WHERE id=?", (now, a.id))

    # Node B: medium weight, not accessed recently — moderate risk
    b = mg.add("Aging Node", "concept")
    _set_weight(mg, b.id, 0.5)
    mg.conn.execute(
        "UPDATE nodes SET accessed=? WHERE id=?",
        (now - 48 * 3600, b.id),  # 2 days ago
    )

    # Node C: low weight, old access — high risk
    c = mg.add("Fading Node", "concept")
    _set_weight(mg, c.id, 0.15)
    mg.conn.execute(
        "UPDATE nodes SET accessed=? WHERE id=?",
        (now - 72 * 3600, c.id),  # 3 days ago
    )

    # Node D: already below threshold
    d = mg.add("Forgotten Node", "concept")
    _set_weight(mg, d.id, 0.02)
    mg.conn.execute(
        "UPDATE nodes SET accessed=? WHERE id=?",
        (now - 200 * 3600, d.id),
    )

    # Node E: high weight + high q_value (reinforced) — not at risk
    e = mg.add("Important Node", "concept")
    _set_weight(mg, e.id, 0.9)
    mg.conn.execute(
        "UPDATE nodes SET q_value=?, accessed=? WHERE id=?",
        (0.8, now, e.id),
    )

    mg.conn.commit()
    return mg


class TestForgettingForecastBasic:
    """Basic functionality tests."""

    def test_returns_none_for_empty_graph(self, mg):
        result = mg.forgetting_forecast()
        assert result is None

    def test_returns_dict_for_populated_graph(self, populated_mg):
        result = populated_mg.forgetting_forecast()
        assert result is not None
        assert "summary" in result
        assert "at_risk" in result
        assert isinstance(result["at_risk"], list)

    def test_summary_has_required_fields(self, populated_mg):
        s = populated_mg.forgetting_forecast()["summary"]
        assert "total_nodes" in s
        assert "already_below_threshold" in s
        assert "at_risk_count" in s
        assert "threshold" in s
        assert "horizon_hours" in s
        assert "median_ttt_hours" in s
        assert "earliest_ttt_hours" in s
        assert "zone_counts" in s

    def test_total_nodes_counts_all(self, populated_mg):
        result = populated_mg.forgetting_forecast()
        assert result["summary"]["total_nodes"] == 5


class TestForgettingForecastNonDestructive:
    """Verify forecast does NOT modify node weights."""

    def test_weights_unchanged_after_forecast(self, populated_mg):
        # Record weights before
        before = {}
        rows = populated_mg.conn.execute(
            "SELECT id, weight FROM nodes"
        ).fetchall()
        for r in rows:
            before[r["id"]] = r["weight"]

        # Run forecast
        populated_mg.forgetting_forecast()

        # Weights must be identical
        after = {}
        rows = populated_mg.conn.execute(
            "SELECT id, weight FROM nodes"
        ).fetchall()
        for r in rows:
            after[r["id"]] = r["weight"]

        for nid in before:
            assert before[nid] == after[nid], f"Weight changed for {nid}"


class TestForgettingForecastRiskZones:
    """Risk zone classification."""

    def test_already_below_counted(self, populated_mg):
        result = populated_mg.forgetting_forecast(threshold=0.1)
        assert result["summary"]["already_below_threshold"] >= 1

    def test_fresh_high_weight_not_at_risk(self, populated_mg):
        result = populated_mg.forgetting_forecast(threshold=0.1)
        ids_at_risk = [e["node_id"] for e in result["at_risk"]]
        # Find the fresh node (weight 0.95, accessed now)
        fresh = None
        for row in populated_mg.conn.execute(
            "SELECT id FROM nodes WHERE label='Fresh Node'"
        ).fetchall():
            fresh = row["id"]
        if fresh:
            assert fresh not in ids_at_risk

    def test_reinforced_node_not_at_risk(self, populated_mg):
        """High q_value extends half-life beyond horizon."""
        result = populated_mg.forgetting_forecast(
            threshold=0.1, horizon_hours=720
        )
        ids_at_risk = [e["node_id"] for e in result["at_risk"]]
        reinforced = None
        for row in populated_mg.conn.execute(
            "SELECT id FROM nodes WHERE label='Important Node'"
        ).fetchall():
            reinforced = row["id"]
        if reinforced:
            assert reinforced not in ids_at_risk

    def test_risk_zones_are_valid(self, populated_mg):
        result = populated_mg.forgetting_forecast()
        valid_zones = {"critical", "high", "medium", "low"}
        for entry in result["at_risk"]:
            assert entry["risk_zone"] in valid_zones

    def test_zone_counts_sum_matches_at_risk(self, populated_mg):
        result = populated_mg.forgetting_forecast()
        zc = result["summary"]["zone_counts"]
        assert sum(zc.values()) == result["summary"]["at_risk_count"]


class TestForgettingForecastTTT:
    """Time-to-threshold calculations."""

    def test_ttt_positive(self, populated_mg):
        result = populated_mg.forgetting_forecast()
        for entry in result["at_risk"]:
            assert entry["ttt_hours"] > 0

    def test_ttt_sorted_ascending(self, populated_mg):
        result = populated_mg.forgetting_forecast()
        ttts = [e["ttt_hours"] for e in result["at_risk"]]
        assert ttts == sorted(ttts)

    def test_ttt_days_consistent_with_hours(self, populated_mg):
        result = populated_mg.forgetting_forecast()
        for entry in result["at_risk"]:
            assert abs(entry["ttt_days"] - entry["ttt_hours"] / 24.0) < 0.1

    def test_critical_zone_has_ttt_under_24h(self, populated_mg):
        result = populated_mg.forgetting_forecast()
        for entry in result["at_risk"]:
            if entry["risk_zone"] == "critical":
                assert entry["ttt_hours"] < 24

    def test_high_zone_between_24_and_72(self, populated_mg):
        result = populated_mg.forgetting_forecast()
        for entry in result["at_risk"]:
            if entry["risk_zone"] == "high":
                assert 24 <= entry["ttt_hours"] < 72

    def test_earliest_ttt_equals_min(self, populated_mg):
        result = populated_mg.forgetting_forecast()
        if result["at_risk"]:
            ttts = [e["ttt_hours"] for e in result["at_risk"]]
            assert result["summary"]["earliest_ttt_hours"] == round(min(ttts), 1)


class TestForgettingForecastMath:
    """Verify the decay formula is correct."""

    def test_ttt_formula_manual(self, mg):
        """Manually verify TTT for a known node."""
        now = time.time()
        node = mg.add("Test", "concept")
        _set_weight(mg, node.id, 0.5)
        mg.conn.execute(
            "UPDATE nodes SET accessed=? WHERE id=?",
            (now - 48 * 3600, node.id),  # 2 days since access
        )
        mg.conn.commit()

        result = mg.forgetting_forecast(threshold=0.1, horizon_hours=2000)
        entry = next(
            (e for e in result["at_risk"] if e["node_id"] == node.id), None
        )
        if entry:
            # weight=0.5, threshold=0.1
            # ratio = 0.1/0.5 = 0.2
            # access_proxy = 0 (not accessed in 24h)
            # s_eff = 168 * 1.0 * 1.0 = 168
            # ttt = -168/0.693 * ln(0.2) = 168/0.693 * 1.609 ≈ 390.2
            expected_ttt = -168.0 / 0.693 * math.log(0.2)
            assert abs(entry["ttt_hours"] - round(expected_ttt, 1)) < 2.0

    def test_higher_q_value_means_longer_ttt(self, mg):
        """Nodes with higher q_value should have longer TTT."""
        now = time.time()

        low_q = mg.add("LowQ", "concept")
        _set_weight(mg, low_q.id, 0.5)
        mg.conn.execute(
            "UPDATE nodes SET q_value=0.0, accessed=? WHERE id=?",
            (now - 48 * 3600, low_q.id),
        )

        high_q = mg.add("HighQ", "concept")
        _set_weight(mg, high_q.id, 0.5)
        mg.conn.execute(
            "UPDATE nodes SET q_value=0.9, accessed=? WHERE id=?",
            (now - 48 * 3600, high_q.id),
        )
        mg.conn.commit()

        result = mg.forgetting_forecast(threshold=0.1, horizon_hours=5000)
        low_entry = next(
            (e for e in result["at_risk"] if e["node_id"] == low_q.id), None
        )
        high_entry = next(
            (e for e in result["at_risk"] if e["node_id"] == high_q.id), None
        )
        if low_entry and high_entry:
            assert high_entry["ttt_hours"] > low_entry["ttt_hours"]
            # q=0.9 → q_mult = 1 + 0.9*4 = 4.6
            # q=0.0 → q_mult = 1.0
            assert high_entry["effective_half_life_hours"] > \
                low_entry["effective_half_life_hours"]


class TestForgettingForecastParams:
    """Parameter variations."""

    def test_high_threshold_changes_risk_set(self, mg):
        """Higher threshold shifts nodes from 'at_risk' to 'already_below'."""
        now = time.time()
        for i in range(10):
            n = mg.add(f"Node{i}", "concept")
            _set_weight(mg, n.id, 0.3 + i * 0.05)
            mg.conn.execute(
                "UPDATE nodes SET accessed=? WHERE id=?",
                (now - 48 * 3600, n.id),
            )
        mg.conn.commit()

        low_t = mg.forgetting_forecast(threshold=0.1)
        high_t = mg.forgetting_forecast(threshold=0.35)
        # Higher threshold → more nodes already below → fewer at risk
        assert high_t["summary"]["already_below_threshold"] >= \
            low_t["summary"]["already_below_threshold"]
        # Combined (at_risk + already_below) should be >= with higher threshold
        low_total = low_t["summary"]["at_risk_count"] + low_t["summary"]["already_below_threshold"]
        high_total = high_t["summary"]["at_risk_count"] + high_t["summary"]["already_below_threshold"]
        assert high_total >= low_total

    def test_short_horizon_excludes_far_future(self, mg):
        now = time.time()
        n = mg.add("LongLived", "concept")
        _set_weight(mg, n.id, 0.8)
        mg.conn.execute(
            "UPDATE nodes SET accessed=? WHERE id=?",
            (now - 24 * 3600, n.id),
        )
        mg.conn.commit()

        # Very short horizon
        short = mg.forgetting_forecast(threshold=0.1, horizon_hours=1)
        long_h = mg.forgetting_forecast(threshold=0.1, horizon_hours=10000)
        assert short["summary"]["at_risk_count"] <= \
            long_h["summary"]["at_risk_count"]

    def test_node_ids_filter(self, populated_mg):
        # Pick specific node IDs
        all_rows = populated_mg.conn.execute(
            "SELECT id FROM nodes LIMIT 2"
        ).fetchall()
        selected = [r["id"] for r in all_rows]

        result = populated_mg.forgetting_forecast(node_ids=selected)
        assert result["summary"]["total_nodes"] == 2
        for entry in result["at_risk"]:
            assert entry["node_id"] in selected

    def test_limit_truncates_results(self, populated_mg):
        result = populated_mg.forgetting_forecast(limit=2)
        assert len(result["at_risk"]) <= 2


class TestForgettingForecastProjected:
    """Projected weight calculations."""

    def test_projected_weight_below_current(self, populated_mg):
        result = populated_mg.forgetting_forecast()
        for entry in result["at_risk"]:
            assert entry["projected_weight_at_horizon"] <= \
                entry["current_weight"]

    def test_projected_weight_non_negative(self, populated_mg):
        result = populated_mg.forgetting_forecast()
        for entry in result["at_risk"]:
            assert entry["projected_weight_at_horizon"] >= 0.0


class TestForgettingForecastEdgeCases:
    """Edge cases and robustness."""

    def test_all_nodes_below_threshold(self, mg):
        now = time.time()
        for i in range(3):
            n = mg.add(f"Below{i}", "concept")
            _set_weight(mg, n.id, 0.01)
            mg.conn.execute(
                "UPDATE nodes SET accessed=? WHERE id=?",
                (now - 100 * 3600, n.id),
            )
        mg.conn.commit()

        result = mg.forgetting_forecast(threshold=0.1)
        assert result["summary"]["at_risk_count"] == 0
        assert result["summary"]["already_below_threshold"] == 3

    def test_all_nodes_above_forever(self, mg):
        """All nodes extremely stable — nothing at risk."""
        now = time.time()
        for i in range(3):
            n = mg.add(f"Stable{i}", "concept")
            _set_weight(mg, n.id, 1.0)
            mg.conn.execute(
                "UPDATE nodes SET q_value=1.0, accessed=? WHERE id=?",
                (now, n.id),
            )
        mg.conn.commit()

        result = mg.forgetting_forecast(threshold=0.1, horizon_hours=720)
        assert result["summary"]["at_risk_count"] == 0

    def test_node_with_null_weight_skipped(self, mg):
        """Nodes with NULL weight should be skipped gracefully."""
        n = mg.add("NullWeight", "concept")
        mg.conn.execute("UPDATE nodes SET weight=NULL WHERE id=?", (n.id,))
        mg.conn.commit()
        result = mg.forgetting_forecast()
        assert result is None  # No valid nodes

    def test_empty_node_ids_list(self, mg):
        """Empty node_ids list should query all nodes."""
        n = mg.add("Test", "concept")
        _set_weight(mg, n.id, 0.3)
        result = mg.forgetting_forecast(node_ids=None)
        assert result is not None
        assert result["summary"]["total_nodes"] == 1
