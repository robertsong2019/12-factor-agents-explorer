"""Tests for retrieval_quality_trend() — Cycle 416.

Retrieval quality family: audit → explain → rerank → compare → trend.
Analyzes temporal snapshots of audit results to detect improving,
degrading, or stable quality patterns.
"""

import pytest
from memory_graph import MemoryGraph


def _make_audit(overall, div=0.5, inter=0.5, fresh=0.5, cov=0.5,
                label=None, timestamp=None):
    """Quick audit snapshot constructor."""
    d = {
        "overall_quality": overall,
        "diversity_score": div,
        "interference_score": inter,
        "freshness_score": fresh,
        "coverage_score": cov,
    }
    if label:
        d["label"] = label
    if timestamp is not None:
        d["timestamp"] = timestamp
    return d


class TestRetrievalQualityTrendBasic:
    """Basic functionality tests."""

    def test_requires_at_least_2_snapshots(self):
        result = MemoryGraph().retrieval_quality_trend([])
        assert "error" in result

    def test_single_snapshot_error(self):
        result = MemoryGraph().retrieval_quality_trend(
            [_make_audit(0.8)]
        )
        assert "error" in result

    def test_two_snapshots_stable(self):
        snaps = [
            _make_audit(0.75, label="t0"),
            _make_audit(0.75, label="t1"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert "error" not in result
        assert result["n_snapshots"] == 2
        assert result["overall_trend"]["direction"] == "stable"

    def test_returns_all_dimensions(self):
        snaps = [
            _make_audit(0.7, div=0.6, inter=0.8, fresh=0.5, cov=0.7),
            _make_audit(0.8, div=0.7, inter=0.85, fresh=0.6, cov=0.75),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        for dim in ["overall_quality", "diversity_score",
                     "interference_score", "freshness_score",
                     "coverage_score"]:
            assert dim in result["dimensions"]

    def test_labels_preserved(self):
        snaps = [
            _make_audit(0.7, label="baseline"),
            _make_audit(0.8, label="after_tuning"),
            _make_audit(0.85, label="optimized"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert result["labels"] == ["baseline", "after_tuning", "optimized"]


class TestRetrievalQualityTrendDirection:
    """Test trend direction detection."""

    def test_improving_trend(self):
        snaps = [
            _make_audit(0.50, label="w1"),
            _make_audit(0.60, label="w2"),
            _make_audit(0.70, label="w3"),
            _make_audit(0.80, label="w4"),
            _make_audit(0.90, label="w5"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert result["overall_trend"]["direction"] == "improving"
        assert result["overall_trend"]["slope"] > 0
        assert result["overall_trend"]["significance"] == "strong"

    def test_degrading_trend(self):
        snaps = [
            _make_audit(0.90, label="w1"),
            _make_audit(0.80, label="w2"),
            _make_audit(0.70, label="w3"),
            _make_audit(0.60, label="w4"),
            _make_audit(0.50, label="w5"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert result["overall_trend"]["direction"] == "degrading"
        assert result["overall_trend"]["slope"] < 0
        assert result["overall_trend"]["significance"] == "strong"
        assert result["overall_trend"]["label"] == "quality_regression"

    def test_stable_trend(self):
        snaps = [
            _make_audit(0.75, label="d1"),
            _make_audit(0.75, label="d2"),
            _make_audit(0.75, label="d3"),
            _make_audit(0.75, label="d4"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert result["overall_trend"]["direction"] == "stable"
        assert result["overall_trend"]["label"] == "stable"

    def test_fluctuating_trend(self):
        """No clear direction with high volatility."""
        snaps = [
            _make_audit(0.90, label="t1"),
            _make_audit(0.30, label="t2"),
            _make_audit(0.85, label="t3"),
            _make_audit(0.35, label="t4"),
            _make_audit(0.80, label="t5"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        # High CV and low r² → fluctuating
        assert result["overall_trend"]["label"] in ("fluctuating",)
        assert result["overall_trend"]["volatility_cv"] > 0.1 or result["overall_trend"]["r_squared"] < 0.5

    def test_healthy_improvement_label(self):
        snaps = [
            _make_audit(0.50),
            _make_audit(0.65),
            _make_audit(0.80),
            _make_audit(0.90),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert result["overall_trend"]["label"] == "healthy_improvement"


class TestRetrievalQualityTrendBestWorst:
    """Best/worst snapshot identification."""

    def test_best_snapshot(self):
        snaps = [
            _make_audit(0.60, label="low"),
            _make_audit(0.90, label="high"),
            _make_audit(0.70, label="mid"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert result["best_snapshot"]["label"] == "high"
        assert result["best_snapshot"]["value"] == pytest.approx(0.90)

    def test_worst_snapshot(self):
        snaps = [
            _make_audit(0.60, label="low"),
            _make_audit(0.90, label="high"),
            _make_audit(0.70, label="mid"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert result["worst_snapshot"]["label"] == "low"
        assert result["worst_snapshot"]["value"] == pytest.approx(0.60)

    def test_best_equals_worst_when_constant(self):
        snaps = [
            _make_audit(0.50, label="a"),
            _make_audit(0.50, label="b"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        # When all values are equal, best and worst are both index 0
        assert result["best_snapshot"]["value"] == result["worst_snapshot"]["value"]


class TestRetrievalQualityTrendChangePoints:
    """Change point detection."""

    def test_detects_quality_drop(self):
        """A sudden drop after stable period should be detected."""
        snaps = [
            _make_audit(0.85, label="s1"),
            _make_audit(0.83, label="s2"),
            _make_audit(0.84, label="s3"),
            _make_audit(0.40, label="drop!"),  # sudden drop
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        # Should detect at least 1 change point at index 3
        drops = [cp for cp in result["change_points"] if cp["direction"] == "drop"]
        assert len(drops) >= 1
        assert drops[0]["snapshot_index"] == 3

    def test_detects_quality_spike(self):
        snaps = [
            _make_audit(0.40, label="s1"),
            _make_audit(0.38, label="s2"),
            _make_audit(0.42, label="s3"),
            _make_audit(0.90, label="spike!"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        spikes = [cp for cp in result["change_points"] if cp["direction"] == "spike"]
        assert len(spikes) >= 1

    def test_no_change_points_when_stable(self):
        snaps = [
            _make_audit(0.75, label="s1"),
            _make_audit(0.76, label="s2"),
            _make_audit(0.74, label="s3"),
            _make_audit(0.75, label="s4"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert len(result["change_points"]) == 0

    def test_change_point_has_z_score(self):
        snaps = [
            _make_audit(0.80, label="s1"),
            _make_audit(0.81, label="s2"),
            _make_audit(0.79, label="s3"),
            _make_audit(0.30, label="drop"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        for cp in result["change_points"]:
            assert "z_score" in cp
            assert isinstance(cp["z_score"], float)


class TestRetrievalQualityTrendVolatility:
    """Volatility analysis."""

    def test_volatility_per_dimension(self):
        snaps = [
            _make_audit(0.70, div=0.80, inter=0.50, fresh=0.90, cov=0.60),
            _make_audit(0.75, div=0.50, inter=0.52, fresh=0.50, cov=0.61),
            _make_audit(0.72, div=0.70, inter=0.48, fresh=0.85, cov=0.59),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        vol = result["volatility"]["per_dimension"]
        assert "diversity_score" in vol
        assert "interference_score" in vol
        assert "freshness_score" in vol
        # Interference is most stable (0.50, 0.52, 0.48)
        assert vol["interference_score"] < vol["diversity_score"]

    def test_most_volatile_dimension(self):
        snaps = [
            _make_audit(0.70, div=0.90, inter=0.50, fresh=0.50, cov=0.50),
            _make_audit(0.70, div=0.20, inter=0.50, fresh=0.50, cov=0.50),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert result["volatility"]["most_volatile"] == "diversity_score"

    def test_least_volatile_dimension(self):
        # overall set constant (0.70) so it's least volatile,
        # interference has tiny change (0.50→0.51)
        snaps = [
            _make_audit(0.70, div=0.90, inter=0.50, fresh=0.80, cov=0.60),
            _make_audit(0.70, div=0.20, inter=0.51, fresh=0.30, cov=0.40),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        # overall_quality is constant → CV=0 → least volatile
        assert result["volatility"]["least_volatile"] == "overall_quality"


class TestRetrievalQualityTrendDimensions:
    """Per-dimension trend analysis."""

    def test_dimension_has_series(self):
        snaps = [
            _make_audit(0.70, div=0.60),
            _make_audit(0.80, div=0.70),
            _make_audit(0.85, div=0.80),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        div_trend = result["dimensions"]["diversity_score"]
        assert "series" in div_trend
        assert len(div_trend["series"]) == 3
        assert div_trend["series"][0] == pytest.approx(0.60)

    def test_dimension_slope_correct(self):
        snaps = [
            _make_audit(0.50, div=0.40),
            _make_audit(0.60, div=0.50),
            _make_audit(0.70, div=0.60),
            _make_audit(0.80, div=0.70),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        div_slope = result["dimensions"]["diversity_score"]["slope"]
        # Linear increase of 0.10 per step → slope ≈ 0.10
        assert div_slope == pytest.approx(0.10, abs=1e-4)

    def test_dimension_r_squared_perfect_linear(self):
        snaps = [
            _make_audit(0, div=0.10),
            _make_audit(0, div=0.20),
            _make_audit(0, div=0.30),
            _make_audit(0, div=0.40),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        r2 = result["dimensions"]["diversity_score"]["r_squared"]
        assert r2 == pytest.approx(1.0, abs=1e-4)

    def test_dimension_delta_computed(self):
        snaps = [
            _make_audit(0.70, fresh=0.60),
            _make_audit(0.75, fresh=0.80),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        fresh_delta = result["dimensions"]["freshness_score"]["delta"]
        assert fresh_delta == pytest.approx(0.20, abs=1e-4)

    def test_dimension_direction_improving(self):
        snaps = [
            _make_audit(0, cov=0.30),
            _make_audit(0, cov=0.40),
            _make_audit(0, cov=0.50),
            _make_audit(0, cov=0.60),
            _make_audit(0, cov=0.70),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert result["dimensions"]["coverage_score"]["direction"] == "improving"


class TestRetrievalQualityTrendRecommendations:
    """Recommendation generation."""

    def test_regression_warning(self):
        snaps = [
            _make_audit(0.90, label="before"),
            _make_audit(0.80, label="t1"),
            _make_audit(0.70, label="t2"),
            _make_audit(0.60, label="t3"),
            _make_audit(0.50, label="t4"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        recs = result["recommendations"]
        assert any("degrading" in r.lower() or "regression" in r.lower() for r in recs)

    def test_improvement_positive(self):
        snaps = [
            _make_audit(0.50, label="w1"),
            _make_audit(0.60, label="w2"),
            _make_audit(0.70, label="w3"),
            _make_audit(0.80, label="w4"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        recs = result["recommendations"]
        assert any("improving" in r.lower() for r in recs)

    def test_change_point_mentioned_in_recs(self):
        snaps = [
            _make_audit(0.85, label="s1"),
            _make_audit(0.83, label="s2"),
            _make_audit(0.84, label="s3"),
            _make_audit(0.30, label="crash"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        recs = result["recommendations"]
        # Should mention the drop
        assert any("drop" in r.lower() for r in recs)

    def test_stable_no_action(self):
        snaps = [
            _make_audit(0.75, label="d1"),
            _make_audit(0.75, label="d2"),
            _make_audit(0.75, label="d3"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        recs = result["recommendations"]
        assert any("stable" in r.lower() or "no action" in r.lower() for r in recs)


class TestRetrievalQualityTrendSummary:
    """Summary generation."""

    def test_summary_contains_snapshot_count(self):
        snaps = [
            _make_audit(0.7),
            _make_audit(0.8),
            _make_audit(0.75),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert "3" in result["summary"]

    def test_summary_contains_best_label(self):
        snaps = [
            _make_audit(0.60, label="bad_run"),
            _make_audit(0.95, label="best_run"),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert "best_run" in result["summary"]

    def test_summary_contains_trend_label(self):
        snaps = [
            _make_audit(0.50),
            _make_audit(0.60),
            _make_audit(0.70),
            _make_audit(0.80),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert "healthy_improvement" in result["summary"]


class TestRetrievalQualityTrendEdgeCases:
    """Edge cases and robustness."""

    def test_all_same_values(self):
        snaps = [
            _make_audit(0.50, div=0.50, inter=0.50, fresh=0.50, cov=0.50),
            _make_audit(0.50, div=0.50, inter=0.50, fresh=0.50, cov=0.50),
            _make_audit(0.50, div=0.50, inter=0.50, fresh=0.50, cov=0.50),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert result["overall_trend"]["direction"] == "stable"
        assert result["overall_trend"]["volatility_cv"] == 0.0

    def test_extreme_values(self):
        snaps = [
            _make_audit(0.0),
            _make_audit(1.0),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert result["best_snapshot"]["value"] == pytest.approx(1.0)
        assert result["worst_snapshot"]["value"] == pytest.approx(0.0)

    def test_many_snapshots(self):
        """20 snapshots should work fine."""
        snaps = [_make_audit(0.50 + i * 0.02, label=f"w{i}")
                 for i in range(20)]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert result["n_snapshots"] == 20
        assert result["overall_trend"]["direction"] == "improving"

    def test_missing_dimensions_default_to_zero(self):
        """Snapshots without all dimension keys should still work."""
        snaps = [
            {"overall_quality": 0.70, "label": "a"},
            {"overall_quality": 0.80, "label": "b"},
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert "error" not in result
        assert "diversity_score" in result["dimensions"]

    def test_default_labels_generated(self):
        snaps = [
            _make_audit(0.70),
            _make_audit(0.75),
            _make_audit(0.80),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert result["labels"] == ["snap_0", "snap_1", "snap_2"]

    def test_per_dimension_has_all_fields(self):
        snaps = [
            _make_audit(0.7, div=0.6, inter=0.7, fresh=0.8, cov=0.5),
            _make_audit(0.8, div=0.7, inter=0.75, fresh=0.85, cov=0.6),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        for dim_name, dim_data in result["dimensions"].items():
            assert "slope" in dim_data
            assert "r_squared" in dim_data
            assert "direction" in dim_data
            assert "significance" in dim_data
            assert "mean" in dim_data
            assert "std" in dim_data
            assert "cv" in dim_data
            assert "delta" in dim_data
            assert "series" in dim_data

    def test_timestamps_not_required(self):
        """Timestamps are optional metadata."""
        snaps = [
            _make_audit(0.70, timestamp=1000.0),
            _make_audit(0.80),  # no timestamp
            _make_audit(0.75, timestamp=2000.0),
        ]
        result = MemoryGraph().retrieval_quality_trend(snaps)
        assert "error" not in result
