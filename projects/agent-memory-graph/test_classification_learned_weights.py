"""Tests for classification_learned_weights() — Cycle 348.

Learn optimal modality weights from labelled training data via grid search.
"""

import pytest
import math
import memory_graph as mg


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def canonical_training():
    """Standard 4-topology training set."""
    training = []
    for topo in ["star", "path", "cycle", "complete"]:
        for i in range(3):
            g = mg.MemoryGraph._bench_build_topology(topo, 10, f"train_{i}")
            training.append((g, topo))
    return training


@pytest.fixture
def hard_training():
    """Hard case: path vs cycle at small sizes (genuine ambiguity)."""
    training = []
    for topo in ["path", "cycle"]:
        for i in range(6):
            g = mg.MemoryGraph._bench_build_topology(topo, 5 + i, f"hard_{i}")
            training.append((g, topo))
    return training


@pytest.fixture
def host():
    """Host MemoryGraph for method calls."""
    return mg.MemoryGraph()


# ── Structure tests ───────────────────────────────────────────────

class TestResultStructure:
    def test_returns_dict(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        assert isinstance(r, dict)

    def test_has_required_keys(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        required = {
            "best_weights", "best_accuracy", "total_combinations",
            "weight_profile", "per_method_accuracy",
            "recommendation", "methods_used",
        }
        assert required <= set(r.keys())

    def test_best_weights_is_tuple_of_3(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        assert len(r["best_weights"]) == 3
        assert all(isinstance(w, (int, float)) for w in r["best_weights"])

    def test_best_accuracy_in_range(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        assert 0.0 <= r["best_accuracy"] <= 1.0

    def test_total_combinations_positive(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        assert r["total_combinations"] > 0

    def test_weight_profile_is_list(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        assert isinstance(r["weight_profile"], list)
        assert len(r["weight_profile"]) == r["total_combinations"]

    def test_weight_profile_sorted_by_accuracy(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        accs = [e["accuracy"] for e in r["weight_profile"]]
        assert accs == sorted(accs, reverse=True)

    def test_per_method_accuracy_keys(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        assert set(r["per_method_accuracy"].keys()) == {"degree", "spectral", "fingerprint"}

    def test_per_method_accuracy_in_range(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        for v in r["per_method_accuracy"].values():
            assert 0.0 <= v <= 1.0

    def test_recommendation_is_string(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        assert isinstance(r["recommendation"], str)
        assert len(r["recommendation"]) > 10

    def test_methods_used_subset(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        assert set(r["methods_used"]) <= {"degree", "spectral", "fingerprint"}

    def test_weight_profile_entries_have_keys(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        for entry in r["weight_profile"]:
            assert "weights" in entry
            assert "accuracy" in entry
            assert "correct" in entry
            assert "total" in entry


# ── Correctness tests ─────────────────────────────────────────────

class TestCorrectness:
    def test_best_accuracy_is_max(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        max_acc = max(e["accuracy"] for e in r["weight_profile"])
        assert r["best_accuracy"] == pytest.approx(max_acc)

    def test_best_weights_match_first_profile_entry(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        assert r["best_weights"] == r["weight_profile"][0]["weights"]

    def test_canonical_topologies_high_accuracy(self, host, canonical_training):
        """Canonical topologies are easy — all methods should get ~100%."""
        r = host.classification_learned_weights(canonical_training)
        assert r["best_accuracy"] >= 0.9

    def test_equal_weights_on_canonical(self, host, canonical_training):
        """With 1:1:1 default, accuracy should be perfect for canonical."""
        r = host.classification_learned_weights(canonical_training)
        # Find the equal-weight combo
        for entry in r["weight_profile"]:
            d, s, f = entry["weights"]
            if d == s == f and d > 0:
                assert entry["accuracy"] >= 0.9
                break

    def test_hard_case_fingerprint_weighted(self, host, hard_training):
        """Path vs cycle: fingerprint should be most informative."""
        r = host.classification_learned_weights(hard_training)
        # Fingerprint alone should outperform degree alone
        assert r["per_method_accuracy"]["fingerprint"] >= r["per_method_accuracy"]["degree"]

    def test_per_method_consistent_with_profile(self, host, canonical_training):
        """per_method_accuracy should match weight_profile for unit vectors."""
        r = host.classification_learned_weights(canonical_training)
        for name, idx in [("degree", 0), ("spectral", 1), ("fingerprint", 2)]:
            # Find the entry where only that modality has weight
            for entry in r["weight_profile"]:
                w = list(entry["weights"])
                if w[idx] > 0 and w[(idx + 1) % 3] == 0 and w[(idx + 2) % 3] == 0:
                    assert entry["accuracy"] == pytest.approx(
                        r["per_method_accuracy"][name], abs=0.01
                    )
                    break

    def test_best_combo_at_least_as_good_as_any_single(self, host, hard_training):
        """Best ensemble should be >= best single modality."""
        r = host.classification_learned_weights(hard_training)
        best_single = max(r["per_method_accuracy"].values())
        assert r["best_accuracy"] >= best_single - 0.01  # tolerance for rounding

    def test_weights_sum_positive(self, host, canonical_training):
        """Best weights should have positive sum."""
        r = host.classification_learned_weights(canonical_training)
        assert sum(r["best_weights"]) > 0

    def test_correct_le_total(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        for entry in r["weight_profile"]:
            assert entry["correct"] <= entry["total"]

    def test_accuracy_equals_correct_over_total(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training)
        for entry in r["weight_profile"]:
            if entry["total"] > 0:
                expected = entry["correct"] / entry["total"]
                assert entry["accuracy"] == pytest.approx(expected)


# ── Parameter tests ───────────────────────────────────────────────

class TestParameters:
    def test_weight_resolution_3(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training, weight_resolution=3)
        assert r["total_combinations"] > 0
        # R=3 → steps {0, 1/3, 2/3, 1} → 4^3 - 1 = 63 combos
        assert r["total_combinations"] == 4**3 - 1

    def test_weight_resolution_5(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training, weight_resolution=5)
        # R=5 → steps {0, 0.2, 0.4, 0.6, 0.8, 1.0} → 6^3 - 1 = 215 combos
        assert r["total_combinations"] == 6**3 - 1

    def test_higher_resolution_same_or_better(self, host, hard_training):
        """Higher resolution should find same or better accuracy."""
        r5 = host.classification_learned_weights(hard_training, weight_resolution=5)
        r10 = host.classification_learned_weights(hard_training, weight_resolution=10)
        assert r10["best_accuracy"] >= r5["best_accuracy"] - 0.01

    def test_different_degree_index(self, host, canonical_training):
        """Should work with different degree indices."""
        r = host.classification_learned_weights(
            canonical_training, degree_index="randic"
        )
        assert r["best_accuracy"] >= 0.0

    def test_different_spectral_measure(self, host, canonical_training):
        """Should work with different spectral measures."""
        r = host.classification_learned_weights(
            canonical_training, spectral_measure="kl"
        )
        assert r["best_accuracy"] >= 0.0

    def test_different_bins(self, host, canonical_training):
        """Should work with different bin counts."""
        r = host.classification_learned_weights(
            canonical_training, bins=10
        )
        assert r["best_accuracy"] >= 0.0


# ── Edge case tests ───────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_training_raises(self, host):
        with pytest.raises(ValueError, match="training_set must not be empty"):
            host.classification_learned_weights([])

    def test_single_label_raises(self, host):
        g = mg.MemoryGraph._bench_build_topology("star", 10, "only")
        with pytest.raises(ValueError, match=">= 2 distinct labels"):
            host.classification_learned_weights([(g, "only")])

    def test_resolution_too_low_raises(self, host, canonical_training):
        with pytest.raises(ValueError, match="weight_resolution must be >= 2"):
            host.classification_learned_weights(canonical_training, weight_resolution=1)

    def test_resolution_too_high_raises(self, host, canonical_training):
        with pytest.raises(ValueError, match="weight_resolution must be <= 20"):
            host.classification_learned_weights(canonical_training, weight_resolution=21)

    def test_single_graph_per_label(self, host):
        """Only 1 graph per label: should still work."""
        training = [
            (mg.MemoryGraph._bench_build_topology("star", 8, "s"), "star"),
            (mg.MemoryGraph._bench_build_topology("path", 8, "p"), "path"),
        ]
        r = host.classification_learned_weights(training, weight_resolution=3)
        assert r["best_accuracy"] >= 0.0

    def test_two_labels_two_graphs_each(self, host):
        training = []
        for topo in ["star", "path"]:
            for i in range(2):
                training.append(
                    (mg.MemoryGraph._bench_build_topology(topo, 8, f"t{i}"), topo)
                )
        r = host.classification_learned_weights(training, weight_resolution=3)
        assert r["best_accuracy"] >= 0.0

    def test_many_labels(self, host):
        """All 6 canonical topologies."""
        training = []
        for topo in ["star", "path", "cycle", "complete", "bipartite", "tree"]:
            for i in range(2):
                training.append(
                    (mg.MemoryGraph._bench_build_topology(topo, 8, f"t{i}"), topo)
                )
        r = host.classification_learned_weights(training, weight_resolution=3)
        assert r["best_accuracy"] >= 0.0

    def test_minimal_resolution_2(self, host, canonical_training):
        """weight_resolution=2 should work."""
        r = host.classification_learned_weights(canonical_training, weight_resolution=2)
        # R=2 → steps {0, 0.5, 1.0} → 3^3 - 1 = 26 combos
        assert r["total_combinations"] == 3**3 - 1


# ── Determinism tests ─────────────────────────────────────────────

class TestDeterminism:
    def test_same_input_same_output(self, host, canonical_training):
        r1 = host.classification_learned_weights(canonical_training, weight_resolution=3)
        r2 = host.classification_learned_weights(canonical_training, weight_resolution=3)
        assert r1["best_weights"] == r2["best_weights"]
        assert r1["best_accuracy"] == r2["best_accuracy"]

    def test_profile_ordering_stable(self, host, canonical_training):
        r1 = host.classification_learned_weights(canonical_training, weight_resolution=3)
        r2 = host.classification_learned_weights(canonical_training, weight_resolution=3)
        for a, b in zip(r1["weight_profile"], r2["weight_profile"]):
            assert a["weights"] == b["weights"]
            assert a["accuracy"] == b["accuracy"]


# ── Integration tests ─────────────────────────────────────────────

class TestIntegration:
    def test_learned_weights_usable_with_weighted_average(self, host, canonical_training):
        """The learned weights should be directly usable with weighted_average_classification."""
        r = host.classification_learned_weights(canonical_training, weight_resolution=3)
        d_w, s_w, f_w = r["best_weights"]

        # Build references and a query
        refs = [mg.MemoryGraph._bench_build_topology(t, 10, f"ref_{t}") for t in ["star", "path", "cycle", "complete"]]
        query = mg.MemoryGraph._bench_build_topology("star", 10, "query")

        result = query.weighted_average_classification(
            refs,
            degree_weight=d_w,
            spectral_weight=s_w,
            fingerprint_weight=f_w,
        )
        assert result is not None
        assert "best_match" in result

    def test_learned_weights_recommendation_mentions_method(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training, weight_resolution=3)
        assert "weighted_average_classification" in r["recommendation"]

    def test_all_zero_weights_excluded(self, host, canonical_training):
        """The (0,0,0) combo should not appear in weight_profile."""
        r = host.classification_learned_weights(canonical_training, weight_resolution=3)
        for entry in r["weight_profile"]:
            assert sum(entry["weights"]) > 0

    def test_methods_used_reflects_best_weights(self, host, canonical_training):
        r = host.classification_learned_weights(canonical_training, weight_resolution=3)
        d, s, f = r["best_weights"]
        expected = []
        if d > 0:
            expected.append("degree")
        if s > 0:
            expected.append("spectral")
        if f > 0:
            expected.append("fingerprint")
        assert set(r["methods_used"]) == set(expected)

    def test_large_training_set(self, host):
        """Performance: should handle 50+ training graphs."""
        training = []
        for topo in ["star", "path", "cycle", "complete", "bipartite"]:
            for i in range(10):
                training.append(
                    (mg.MemoryGraph._bench_build_topology(topo, 10, f"big_{i}"), topo)
                )
        r = host.classification_learned_weights(training, weight_resolution=3)
        assert r["best_accuracy"] >= 0.0
        assert r["total_combinations"] > 0

    def test_recommendation_includes_percentages(self, host, canonical_training):
        """Recommendation should include percentage breakdown."""
        r = host.classification_learned_weights(canonical_training, weight_resolution=3)
        assert "%" in r["recommendation"]
