"""Tests for classification_parameter_sensitivity() — Cycle 347, API #14.

Evaluates how robust each parameterised classification method is to
its own hyperparameters.
"""
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph()


@pytest.fixture
def sens_result(mg):
    """Run with minimal topology/size for speed."""
    return mg.classification_parameter_sensitivity(
        topologies=["star", "path", "cycle"],
        size=8,
        num_references_per_category=1,
        num_queries=1,
    )


# ── Structural / schema tests ─────────────────────────────

class TestSchema:
    def test_returns_dict(self, sens_result):
        assert isinstance(sens_result, dict)

    def test_has_required_keys(self, sens_result):
        required = {
            "size", "topologies", "num_references", "num_queries",
            "param_grid", "sensitivity_profiles", "rankings",
            "most_stable", "least_stable", "summary",
        }
        assert required <= set(sens_result.keys())

    def test_size_matches(self, sens_result):
        assert sens_result["size"] == 8

    def test_topologies_match(self, sens_result):
        assert set(sens_result["topologies"]) == {"star", "path", "cycle"}

    def test_param_grid_keys(self, sens_result):
        expected = {"spectral_bins", "rrf_k", "knn_k", "weighted_configs"}
        assert expected <= set(sens_result["param_grid"].keys())

    def test_summary_is_string(self, sens_result):
        assert isinstance(sens_result["summary"], str)
        assert len(sens_result["summary"]) > 10

    def test_rankings_non_empty(self, sens_result):
        assert len(sens_result["rankings"]) >= 1
        for entry in sens_result["rankings"]:
            assert isinstance(entry, tuple) or isinstance(entry, list)
            assert len(entry) == 2

    def test_most_and_least_stable(self, sens_result):
        assert sens_result["most_stable"] != "none"
        assert sens_result["least_stable"] != "none"
        # Should differ if more than 1 method tested
        if len(sens_result["rankings"]) > 1:
            assert sens_result["most_stable"] != sens_result["least_stable"]


# ── Sensitivity profile tests ─────────────────────────────

class TestSensitivityProfiles:
    def test_all_methods_present(self, sens_result):
        profiles = sens_result["sensitivity_profiles"]
        assert "spectral" in profiles
        assert "rrf" in profiles
        assert "knn" in profiles
        assert "weighted_average" in profiles

    def test_profile_has_stats(self, sens_result):
        for method, profile in sens_result["sensitivity_profiles"].items():
            required = {
                "param_name", "param_values", "accuracy_at_param",
                "mean_accuracy", "std_accuracy", "stability_score",
                "best_param", "best_accuracy",
                "worst_param", "worst_accuracy", "accuracy_range",
            }
            assert required <= set(profile.keys()), f"{method} missing keys: {required - set(profile.keys())}"

    def test_stability_score_range(self, sens_result):
        for method, profile in sens_result["sensitivity_profiles"].items():
            score = profile["stability_score"]
            assert 0.0 <= score <= 1.0, f"{method} stability_score={score} out of [0,1]"

    def test_mean_accuracy_range(self, sens_result):
        for method, profile in sens_result["sensitivity_profiles"].items():
            ma = profile["mean_accuracy"]
            assert 0.0 <= ma <= 1.0, f"{method} mean_accuracy={ma} out of [0,1]"

    def test_best_gte_worst(self, sens_result):
        for method, profile in sens_result["sensitivity_profiles"].items():
            assert profile["best_accuracy"] >= profile["worst_accuracy"]

    def test_accuracy_range_non_negative(self, sens_result):
        for method, profile in sens_result["sensitivity_profiles"].items():
            assert profile["accuracy_range"] >= 0.0

    def test_std_non_negative(self, sens_result):
        for method, profile in sens_result["sensitivity_profiles"].items():
            assert profile["std_accuracy"] >= 0.0

    def test_accuracy_at_param_keys(self, sens_result):
        """Each accuracy_at_param dict should have same number of entries as param_values."""
        for method, profile in sens_result["sensitivity_profiles"].items():
            n_vals = len(profile["param_values"])
            n_accs = len(profile["accuracy_at_param"])
            assert n_vals == n_accs, f"{method}: {n_vals} params but {n_accs} accuracies"

    def test_best_param_in_accuracy(self, sens_result):
        for method, profile in sens_result["sensitivity_profiles"].items():
            assert profile["best_param"] in profile["accuracy_at_param"]

    def test_worst_param_in_accuracy(self, sens_result):
        for method, profile in sens_result["sensitivity_profiles"].items():
            assert profile["worst_param"] in profile["accuracy_at_param"]


# ── Param-specific tests ──────────────────────────────────

class TestParamSpecific:
    def test_spectral_bins_values(self, sens_result):
        p = sens_result["sensitivity_profiles"]["spectral"]
        assert p["param_name"] == "bins"
        assert p["param_values"] == [5, 10, 20, 40, 60]

    def test_rrf_k_values(self, sens_result):
        p = sens_result["sensitivity_profiles"]["rrf"]
        assert p["param_name"] == "k"
        assert p["param_values"] == [1, 3, 6, 10, 20]

    def test_knn_k_values(self, sens_result):
        p = sens_result["sensitivity_profiles"]["knn"]
        assert p["param_name"] == "k"
        assert p["param_values"] == [1, 2, 3, 5, 7]

    def test_weighted_configs_values(self, sens_result):
        p = sens_result["sensitivity_profiles"]["weighted_average"]
        assert p["param_name"] == "weight_config"
        assert p["param_values"] == ["equal", "degree_heavy", "spectral_heavy", "fingerprint_heavy", "degree_only"]


# ── Ranking correctness ───────────────────────────────────

class TestRankings:
    def test_rankings_sorted_descending(self, sens_result):
        scores = [s for _, s in sens_result["rankings"]]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_most_stable_is_top(self, sens_result):
        assert sens_result["rankings"][0][0] == sens_result["most_stable"]

    def test_least_stable_is_bottom(self, sens_result):
        assert sens_result["rankings"][-1][0] == sens_result["least_stable"]


# ── Custom param_grid ─────────────────────────────────────

class TestCustomGrid:
    def test_custom_grid_spectral_only(self, mg):
        result = mg.classification_parameter_sensitivity(
            topologies=["star", "path"],
            size=6,
            param_grid={
                "spectral_bins": [10, 20, 30],
            },
        )
        profiles = result["sensitivity_profiles"]
        assert "spectral" in profiles
        assert "rrf" not in profiles
        assert "knn" not in profiles
        assert len(profiles["spectral"]["param_values"]) == 3

    def test_custom_grid_rrf_only(self, mg):
        result = mg.classification_parameter_sensitivity(
            topologies=["cycle", "complete"],
            size=6,
            param_grid={
                "rrf_k": [3, 6, 9],
            },
        )
        assert "rrf" in result["sensitivity_profiles"]
        assert "spectral" not in result["sensitivity_profiles"]

    def test_custom_weighted_configs(self, mg):
        custom = [
            ("high_d", 5.0, 0.5, 0.5),
            ("high_s", 0.5, 5.0, 0.5),
        ]
        result = mg.classification_parameter_sensitivity(
            topologies=["star"],
            size=6,
            param_grid={"weighted_configs": custom},
        )
        p = result["sensitivity_profiles"]["weighted_average"]
        assert len(p["accuracy_at_param"]) == 2
        assert "high_d" in p["accuracy_at_param"]
        assert "high_s" in p["accuracy_at_param"]


# ── Edge cases ────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_param_grid(self, mg):
        result = mg.classification_parameter_sensitivity(
            topologies=["star"],
            size=6,
            param_grid={},
        )
        assert result["sensitivity_profiles"] == {}
        assert result["rankings"] == []
        assert result["most_stable"] == "none"
        assert result["least_stable"] == "none"

    def test_single_topology(self, mg):
        result = mg.classification_parameter_sensitivity(
            topologies=["star"],
            size=8,
        )
        assert "star" in result["topologies"]
        assert len(result["sensitivity_profiles"]) == 4

    def test_num_queries_affects_count(self, mg):
        r1 = mg.classification_parameter_sensitivity(
            topologies=["star", "path"],
            size=6,
            num_queries=1,
        )
        r2 = mg.classification_parameter_sensitivity(
            topologies=["star", "path"],
            size=6,
            num_queries=3,
        )
        assert r2["num_queries"] > r1["num_queries"]


# ── Consistency with benchmark ────────────────────────────

class TestConsistency:
    def test_default_params_close_to_benchmark(self, mg):
        """Methods at default params should achieve reasonable accuracy
        (not dramatically worse than benchmark)."""
        result = mg.classification_parameter_sensitivity(
            topologies=["star", "path", "cycle"],
            size=10,
        )
        for method, profile in result["sensitivity_profiles"].items():
            # At least one param setting should achieve > 0.3 accuracy
            max_acc = max(profile["accuracy_at_param"].values())
            assert max_acc > 0.3, f"{method} max accuracy {max_acc} too low"
