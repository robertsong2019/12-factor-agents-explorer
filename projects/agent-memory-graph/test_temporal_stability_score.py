"""Tests for temporal_stability_score() — Cycle 409.

Composite stability score from growth consistency, retention rate,
and changepoint density. Score 0–1 where 1 = perfectly stable.
"""

import pytest
from memory_graph import MemoryGraph


# ── Fixtures ───────────────────────────────────────────────

@pytest.fixture
def stable_graph():
    """Graph with steady, uniform growth — high stability expected."""
    mg = MemoryGraph()
    base = 1700000000
    for i in range(10):
        node = mg.add(f"stable_{i}", "fact")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (base + i * 86400, node.id)  # one node per day
        )
    mg.conn.commit()
    return mg


@pytest.fixture
def chaotic_graph():
    """Graph with bursts and high supersession — low stability expected."""
    mg = MemoryGraph()
    base = 1700000000

    # Burst: 8 nodes in 1 minute
    for i in range(8):
        node = mg.add(f"burst_{i}", "fact")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (base + i * 10, node.id)
        )

    # Supersede half of them immediately
    nodes = mg.conn.execute(
        "SELECT id FROM nodes ORDER BY created LIMIT 4"
    ).fetchall()
    for j, row in enumerate(nodes):
        mg.conn.execute(
            "UPDATE nodes SET valid_to=? WHERE id=?",
            (base + 600 + j * 10, row["id"])
        )

    # Another burst much later
    for i in range(6):
        node = mg.add(f"burst2_{i}", "fact")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (base + 30 * 86400 + i * 5, node.id)
        )

    mg.conn.commit()
    return mg


@pytest.fixture
def minimal_graph():
    """Graph with < 3 temporal events."""
    mg = MemoryGraph()
    mg.add("only_one", "test")
    return mg


# ── Basic functionality ────────────────────────────────────

class TestBasicFunctionality:

    def test_returns_dict(self, stable_graph):
        result = stable_graph.temporal_stability_score()
        assert isinstance(result, dict)

    def test_required_keys(self, stable_graph):
        result = stable_graph.temporal_stability_score()
        expected_keys = {
            "stability_score", "growth_cv", "growth_consistency",
            "retention_rate", "changepoint_density_score",
            "total_created", "total_superseded", "span_seconds",
            "interpretation",
        }
        assert expected_keys.issubset(result.keys())

    def test_none_for_minimal(self, minimal_graph):
        result = minimal_graph.temporal_stability_score()
        assert result is None

    def test_score_in_range(self, stable_graph):
        result = stable_graph.temporal_stability_score()
        assert 0.0 <= result["stability_score"] <= 1.0


# ── Score semantics ────────────────────────────────────────

class TestScoreSemantics:

    def test_stable_graph_high_score(self, stable_graph):
        """Uniform daily growth → high stability."""
        result = stable_graph.temporal_stability_score()
        assert result["stability_score"] >= 0.5

    def test_chaotic_graph_low_score(self, chaotic_graph):
        """Bursts + supersession → lower stability."""
        result = chaotic_graph.temporal_stability_score()
        assert result["stability_score"] < result["retention_rate"]

    def test_stable_better_than_chaotic(self, stable_graph, chaotic_graph):
        s = stable_graph.temporal_stability_score()
        c = chaotic_graph.temporal_stability_score()
        assert s["stability_score"] > c["stability_score"]

    def test_full_retention(self, stable_graph):
        """No supersessions → retention_rate = 1.0."""
        result = stable_graph.temporal_stability_score()
        assert result["retention_rate"] == 1.0

    def test_partial_retention(self, chaotic_graph):
        """Some nodes superseded → retention_rate < 1.0."""
        result = chaotic_graph.temporal_stability_score()
        assert result["retention_rate"] < 1.0

    def test_low_growth_cv_for_uniform(self, stable_graph):
        """Uniform inter-arrival → low CV."""
        result = stable_graph.temporal_stability_score()
        # Inter-arrivals are all ~86400, CV should be low
        assert result["growth_cv"] < 0.5


# ── Interpretation ─────────────────────────────────────────

class TestInterpretation:

    def test_interpretation_is_string(self, stable_graph):
        result = stable_graph.temporal_stability_score()
        assert isinstance(result["interpretation"], str)

    def test_stable_interpretation(self, stable_graph):
        result = stable_graph.temporal_stability_score()
        assert result["interpretation"] in (
            "very stable", "stable", "moderate turnover",
            "unstable — frequent structural change",
            "chaotic — rapid, unpredictable evolution"
        )

    def test_chaotic_interpretation(self, chaotic_graph):
        result = chaotic_graph.temporal_stability_score()
        assert result["interpretation"] in (
            "very stable", "stable", "moderate turnover",
            "unstable — frequent structural change",
            "chaotic — rapid, unpredictable evolution"
        )


# ── Growth consistency ─────────────────────────────────────

class TestGrowthConsistency:

    def test_uniform_growth_high_consistency(self, stable_graph):
        result = stable_graph.temporal_stability_score()
        assert result["growth_consistency"] > 0.7

    def test_bursty_growth_low_consistency(self, chaotic_graph):
        result = chaotic_graph.temporal_stability_score()
        # Bursty growth should have lower consistency than uniform
        assert result["growth_consistency"] < 1.0


# ── Changepoint density ────────────────────────────────────

class TestChangepointDensity:

    def test_changepoint_score_in_range(self, stable_graph):
        result = stable_graph.temporal_stability_score()
        assert 0.0 <= result["changepoint_density_score"] <= 1.0

    def test_stable_has_higher_cp_score(self, stable_graph, chaotic_graph):
        s = stable_graph.temporal_stability_score()
        c = chaotic_graph.temporal_stability_score()
        assert s["changepoint_density_score"] >= c["changepoint_density_score"]


# ── Edge cases ─────────────────────────────────────────────

class TestEdgeCases:

    def test_all_same_time(self):
        """All events at same time → span=0 → None."""
        mg = MemoryGraph()
        ts = 1700000000
        for i in range(5):
            node = mg.add(f"n{i}", "x")
            mg.conn.execute(
                "UPDATE nodes SET created=? WHERE id=?", (ts, node.id))
        mg.conn.commit()
        result = mg.temporal_stability_score()
        assert result is None

    def test_two_events(self):
        mg = MemoryGraph()
        mg.add("a", "x")
        mg.add("b", "x")
        result = mg.temporal_stability_score()
        assert result is None

    def test_does_not_mutate_graph(self, stable_graph):
        n_before = stable_graph.conn.execute(
            "SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        e_before = stable_graph.conn.execute(
            "SELECT COUNT(*) c FROM edges").fetchone()["c"]

        stable_graph.temporal_stability_score()

        n_after = stable_graph.conn.execute(
            "SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        e_after = stable_graph.conn.execute(
            "SELECT COUNT(*) c FROM edges").fetchone()["c"]

        assert n_before == n_after
        assert e_before == e_after

    def test_three_events_works(self):
        mg = MemoryGraph()
        base = 1700000000
        for i in range(3):
            node = mg.add(f"n{i}", "x")
            mg.conn.execute(
                "UPDATE nodes SET created=? WHERE id=?",
                (base + i * 3600, node.id))
        mg.conn.commit()
        result = mg.temporal_stability_score()
        assert result is not None
        assert result["total_created"] == 3


# ── Window parameter ───────────────────────────────────────

class TestWindowParameter:

    def test_default_window(self, stable_graph):
        result = stable_graph.temporal_stability_score()
        assert isinstance(result, dict)

    def test_custom_window(self, stable_graph):
        result = stable_graph.temporal_stability_score(window=5)
        assert isinstance(result, dict)

    def test_window_1(self, stable_graph):
        result = stable_graph.temporal_stability_score(window=1)
        assert isinstance(result, dict)
