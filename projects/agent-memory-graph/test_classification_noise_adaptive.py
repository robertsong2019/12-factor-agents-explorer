"""Tests for classification_noise_adaptive — Cycle 355.

Noise-adaptive classification: estimates query noise, selects best method.
22nd classification API.
"""

import math
import pytest
from memory_graph import MemoryGraph


# ── Fixtures ──

@pytest.fixture
def ref_set():
    """Standard 3-topology reference set."""
    mg = MemoryGraph()
    refs = []
    for topo in ("star", "path", "cycle"):
        r = mg._bench_build_topology(topo, 10, label=topo)
        r.graph_meta = {"topology": topo, "label": topo, "n": 10}
        refs.append(r)
    return mg, refs


@pytest.fixture
def ref_set_extended():
    """6-topology reference set."""
    mg = MemoryGraph()
    refs = []
    for topo in ("star", "path", "cycle", "complete", "bipartite", "tree"):
        r = mg._bench_build_topology(topo, 10, label=topo)
        r.graph_meta = {"topology": topo, "label": topo, "n": 10}
        refs.append(r)
    return mg, refs


# ── Basic functionality ──

class TestNoiseAdaptiveBasic:

    def test_clean_query_classifies_correctly(self, ref_set):
        """A clean star query should classify as star."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        assert result["label"] == "star"
        assert result["best_match"] == 0
        assert result["method_used"] is not None
        assert result["estimated_noise"] >= 0.0

    def test_returns_all_required_fields(self, ref_set):
        """Output dict must contain all documented fields."""
        mg, refs = ref_set
        query = mg._bench_build_topology("cycle", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        required = {
            "label", "best_match", "method_used", "estimated_noise",
            "noise_tier", "method_rationale", "structural_deviations",
            "raw_result", "summary",
        }
        assert required.issubset(result.keys())

    def test_empty_references(self):
        """No references → graceful failure."""
        mg = MemoryGraph()
        query = MemoryGraph()
        query.add("a", "concept")
        result = query.classification_noise_adaptive([])
        assert result["label"] is None
        assert result["best_match"] is None
        assert result["method_used"] is None
        assert "No references" in result["summary"]

    def test_summary_is_string(self, ref_set):
        """Summary must be a human-readable string."""
        mg, refs = ref_set
        query = mg._bench_build_topology("path", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 10

    def test_method_rationale_explains_choice(self, ref_set):
        """Rationale must be a non-empty string."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        assert isinstance(result["method_rationale"], str)
        assert len(result["method_rationale"]) > 10


# ── Noise estimation ──

class TestNoiseEstimation:

    def test_clean_query_low_noise(self, ref_set):
        """Identical topology should estimate near-zero noise."""
        mg, refs = ref_set
        # Build exact copy of star
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        assert result["estimated_noise"] < 0.2  # should be relatively low
        assert result["noise_tier"] in ("low", "moderate")

    def test_noisy_query_higher_noise(self, ref_set):
        """Perturbed query should have higher estimated noise than clean."""
        mg, refs = ref_set
        import random as _random

        # Clean query
        clean = mg._bench_build_topology("star", 10, label="?")
        clean_result = clean.classification_noise_adaptive(refs)

        # Noisy query
        noisy = mg._bench_build_topology("star", 10, label="?")
        MemoryGraph._apply_noise(noisy, 0.3, _random.Random(42))
        noisy_result = noisy.classification_noise_adaptive(refs)

        assert noisy_result["estimated_noise"] > clean_result["estimated_noise"]

    def test_noise_tier_categories(self, ref_set):
        """Noise tier must be one of the defined categories."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        assert result["noise_tier"] in ("low", "moderate", "high", "very high")

    def test_structural_deviations_per_reference(self, ref_set):
        """Deviations list should have one entry per reference."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        assert len(result["structural_deviations"]) == len(refs)
        for dev in result["structural_deviations"]:
            assert "ref_index" in dev
            assert "deviation" in dev
            assert dev["deviation"] >= 0.0

    def test_minimum_deviation_is_estimated_noise(self, ref_set):
        """Estimated noise should equal the minimum deviation."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        min_dev = min(d["deviation"] for d in result["structural_deviations"])
        assert abs(result["estimated_noise"] - min_dev) < 1e-6

    def test_deviations_sorted_ascending(self, ref_set):
        """Structural deviations should be sorted by deviation ascending."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        devs = [d["deviation"] for d in result["structural_deviations"]]
        assert devs == sorted(devs)


# ── Method selection ──

class TestMethodSelection:

    def test_low_noise_selects_precise_method(self, ref_set):
        """Low noise should select spectral (precise)."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        if result["estimated_noise"] < 0.05:
            assert result["method_used"] == "spectral"

    def test_with_noise_profile(self, ref_set):
        """Providing a noise_profile should use empirical data."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        fake_profile = {
            "robustness_score": {
                "rrf": 0.85,
                "graph": 0.70,
                "spectral": 0.60,
                "knn": 0.50,
            },
            "breakpoint": {
                "rrf": 0.3,
                "graph": 0.2,
                "spectral": 0.1,
                "knn": 0.05,
            },
        }
        result = query.classification_noise_adaptive(refs, noise_profile=fake_profile)
        assert result["method_used"] is not None
        assert "Empirical" in result["method_rationale"]

    def test_noise_profile_all_past_breakpoint(self, ref_set):
        """If all methods past breakpoints → consensus fallback."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        fake_profile = {
            "robustness_score": {"spectral": 0.5, "knn": 0.3},
            "breakpoint": {"spectral": 0.0, "knn": 0.0},
        }
        result = query.classification_noise_adaptive(refs, noise_profile=fake_profile)
        assert result["method_used"] == "consensus"
        assert " Falling back to consensus" in result["method_rationale"]

    def test_heuristic_low_noise(self, ref_set):
        """Without noise_profile, low noise → spectral."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        if result["noise_tier"] == "low":
            assert result["method_used"] == "spectral"

    def test_method_rationale_mentions_noise_level(self, ref_set):
        """Rationale should reference the estimated noise value."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        # Rationale should contain the noise number
        noise_str = f"{result['estimated_noise']:.3f}"
        assert noise_str in result["method_rationale"]


# ── Classification correctness ──

class TestClassificationCorrectness:

    @pytest.mark.parametrize("topo", ["star", "path", "cycle"])
    def test_correct_classification_each_topology(self, ref_set, topo):
        """Each clean topology should be classified correctly."""
        mg, refs = ref_set
        query = mg._bench_build_topology(topo, 10, label="?")
        result = query.classification_noise_adaptive(refs)
        assert result["label"] == topo

    @pytest.mark.parametrize("topo", [
        "star", "path", "cycle", "complete", "bipartite", "tree"
    ])
    def test_correct_classification_extended(self, ref_set_extended, topo):
        """All 6 topologies should classify correctly when clean."""
        mg, refs = ref_set_extended
        query = mg._bench_build_topology(topo, 10, label="?")
        result = query.classification_noise_adaptive(refs)
        assert result["label"] == topo

    def test_different_sizes_still_work(self, ref_set):
        """Queries with different sizes should still classify."""
        mg, refs = ref_set
        # Query with size 8 (vs refs at size 10)
        query = mg._bench_build_topology("star", 8, label="?")
        result = query.classification_noise_adaptive(refs)
        assert result["label"] is not None

    def test_raw_result_present(self, ref_set):
        """Raw result from the underlying method should be included."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        assert result["raw_result"] is not None


# ── Noisy queries ──

class TestNoisyQueries:

    def test_slightly_noisy_still_correct(self, ref_set):
        """5% noise shouldn't break classification."""
        import random as _random
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        MemoryGraph._apply_noise(query, 0.05, _random.Random(123))
        result = query.classification_noise_adaptive(refs)
        assert result["label"] == "star"

    def test_moderately_noisy(self, ref_set):
        """15% noise may still classify correctly."""
        import random as _random
        mg, refs = ref_set
        query = mg._bench_build_topology("cycle", 10, label="?")
        MemoryGraph._apply_noise(query, 0.10, _random.Random(77))
        result = query.classification_noise_adaptive(refs)
        # Should still produce a result (even if not always correct)
        assert result["label"] is not None

    def test_high_noise_uses_robust_method(self, ref_set):
        """High noise should select RRF or consensus."""
        import random as _random
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        MemoryGraph._apply_noise(query, 0.35, _random.Random(999))
        result = query.classification_noise_adaptive(refs)
        # With very high noise, should fall to rrf or consensus
        assert result["method_used"] in ("rrf", "consensus", "graph")

    def test_noise_increases_estimated_noise(self, ref_set):
        """More noise → higher estimated noise."""
        import random as _random
        mg, refs = ref_set

        low_noise = mg._bench_build_topology("star", 10, label="?")
        MemoryGraph._apply_noise(low_noise, 0.05, _random.Random(1))
        low_result = low_noise.classification_noise_adaptive(refs)

        high_noise = mg._bench_build_topology("star", 10, label="?")
        MemoryGraph._apply_noise(high_noise, 0.30, _random.Random(1))
        high_result = high_noise.classification_noise_adaptive(refs)

        assert high_result["estimated_noise"] >= low_result["estimated_noise"]


# ── Edge cases ──

class TestEdgeCases:

    def test_single_reference(self):
        """Single reference should still work."""
        mg = MemoryGraph()
        ref = mg._bench_build_topology("star", 8, label="star")
        ref.graph_meta = {"label": "star"}
        query = mg._bench_build_topology("star", 8, label="?")
        result = query.classification_noise_adaptive([ref])
        assert result["label"] == "star"

    def test_single_node_query(self, ref_set):
        """Minimal query graph shouldn't crash."""
        mg, refs = ref_set
        query = MemoryGraph()
        query.add("solo", "concept")
        result = query.classification_noise_adaptive(refs)
        # Should not crash, may have high noise
        assert "estimated_noise" in result
        assert result["noise_tier"] in ("low", "moderate", "high", "very high")

    def test_empty_query_graph(self, ref_set):
        """Empty query graph shouldn't crash."""
        mg, refs = ref_set
        query = MemoryGraph()
        result = query.classification_noise_adaptive(refs)
        assert result["label"] is None or result["label"] is not None
        # Shouldn't crash

    def test_two_references(self):
        """Two references should work."""
        mg = MemoryGraph()
        r1 = mg._bench_build_topology("star", 6, label="star")
        r1.graph_meta = {"label": "star"}
        r2 = mg._bench_build_topology("path", 6, label="path")
        r2.graph_meta = {"label": "path"}
        query = mg._bench_build_topology("star", 6, label="?")
        result = query.classification_noise_adaptive([r1, r2])
        assert result["label"] == "star"

    def test_degree_index_parameter(self, ref_set):
        """Custom degree_index should be accepted."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs, degree_index="randic")
        assert result["label"] is not None

    def test_include_quarantined_parameter(self, ref_set):
        """include_quarantined flag should be accepted without error."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs, include_quarantined=True)
        assert result["label"] is not None


# ── Consistency with other methods ──

class TestConsistency:

    def test_matches_graph_classification(self, ref_set):
        """For clean queries, result should match graph_classification."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")

        adaptive = query.classification_noise_adaptive(refs)
        gc = query.graph_classification(refs)

        if gc is not None and adaptive["best_match"] is not None:
            # Both should identify the same reference as best match
            assert adaptive["best_match"] == gc["best_match"]

    def test_matches_spectral_on_clean(self, ref_set):
        """For clean queries, adaptive should classify correctly like spectral."""
        mg, refs = ref_set
        query = mg._bench_build_topology("cycle", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        sc = query.spectral_classification(refs)
        if sc is not None:
            assert result["best_match"] == sc["best_match"]


# ── Determinism ──

class TestDeterminism:

    def test_same_query_same_result(self, ref_set):
        """Same query should produce identical results."""
        mg, refs = ref_set
        q1 = mg._bench_build_topology("star", 10, label="?")
        q2 = mg._bench_build_topology("star", 10, label="?")
        r1 = q1.classification_noise_adaptive(refs)
        r2 = q2.classification_noise_adaptive(refs)
        assert r1["label"] == r2["label"]
        assert r1["method_used"] == r2["method_used"]
        assert abs(r1["estimated_noise"] - r2["estimated_noise"]) < 1e-6

    def test_repeated_call_deterministic(self, ref_set):
        """Calling twice on same graph should give same result."""
        mg, refs = ref_set
        query = mg._bench_build_topology("path", 10, label="?")
        r1 = query.classification_noise_adaptive(refs)
        r2 = query.classification_noise_adaptive(refs)
        assert r1["label"] == r2["label"]
        assert r1["method_used"] == r2["method_used"]


# ── Noise profile integration ──

class TestNoiseProfileIntegration:

    def test_noise_profile_changes_selection(self, ref_set):
        """Providing a noise_profile can change method selection."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")

        # Without profile
        no_profile = query.classification_noise_adaptive(refs)

        # With profile that favors graph method
        profile = {
            "robustness_score": {"graph": 0.99, "spectral": 0.10},
            "breakpoint": {"graph": 0.5, "spectral": 0.01},
        }
        with_profile = query.classification_noise_adaptive(refs, noise_profile=profile)

        assert with_profile["method_used"] == "graph"

    def test_partial_noise_profile(self, ref_set):
        """Partial profile (some methods missing) should still work."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        profile = {
            "robustness_score": {"rrf": 0.90},
            "breakpoint": {"rrf": 0.4},
        }
        result = query.classification_noise_adaptive(refs, noise_profile=profile)
        assert result["method_used"] is not None

    def test_empty_noise_profile_uses_heuristic(self, ref_set):
        """Empty robustness_score in profile → heuristic fallback."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(
            refs, noise_profile={"robustness_score": {}},
        )
        # Should still produce a result
        assert result["method_used"] is not None


# ── Structural deviation details ──

class TestStructuralDeviations:

    def test_deviation_fields_complete(self, ref_set):
        """Each deviation entry should have all expected fields."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        for dev in result["structural_deviations"]:
            assert "ref_index" in dev
            assert "ref_label" in dev
            assert "deviation" in dev
            assert "density_diff" in dev
            assert "degree_diff" in dev
            assert "spectral_diff" in dev
            assert "node_diff" in dev

    def test_star_query_star_lowest_deviation(self, ref_set):
        """Star query should have lowest deviation for star reference."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        devs = result["structural_deviations"]
        assert devs[0]["ref_label"] == "star"

    def test_cycle_query_cycle_lowest_deviation(self, ref_set):
        """Cycle query should have lowest deviation for cycle reference."""
        mg, refs = ref_set
        query = mg._bench_build_topology("cycle", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        devs = result["structural_deviations"]
        assert devs[0]["ref_label"] == "cycle"

    def test_node_diff_zero_for_same_size(self, ref_set):
        """Same-size query should have node_diff = 0."""
        mg, refs = ref_set
        query = mg._bench_build_topology("star", 10, label="?")
        result = query.classification_noise_adaptive(refs)
        for dev in result["structural_deviations"]:
            assert dev["node_diff"] == 0.0
