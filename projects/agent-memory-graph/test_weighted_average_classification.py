"""Tests for weighted_average_classification() — Cycle 330.

Research #038 strategy 3/4: explicit user-controlled weights over all 3
topological modalities (degree, spectral, fingerprint).
"""

import math
import pytest
from memory_graph import MemoryGraph


# ── Helpers ────────────────────────────────────────────────────────

def _star(n: int, label: str = None) -> MemoryGraph:
    """Star graph: hub connected to n-1 leaves."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(1, n):
        g.link(nodes[0].id, nodes[i].id, "r")
    if label:
        g.graph_meta = {"label": label}
    return g


def _path(n: int, label: str = None) -> MemoryGraph:
    """Path graph: 0-1-2-...-n-1."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    if label:
        g.graph_meta = {"label": label}
    return g


def _cycle(n: int, label: str = None) -> MemoryGraph:
    """Cycle graph: 0-1-2-...-n-1-0."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    if label:
        g.graph_meta = {"label": label}
    return g


def _complete(n: int, label: str = None) -> MemoryGraph:
    """Complete graph: every pair connected."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    if label:
        g.graph_meta = {"label": label}
    return g


# ── Degenerate cases ──────────────────────────────────────────────

class TestDegenerate:
    def test_empty_references_returns_none(self):
        g = _star(5)
        assert g.weighted_average_classification([]) is None

    def test_single_reference_returns_result(self):
        g = _star(5)
        ref = _star(5)
        result = g.weighted_average_classification([ref])
        assert result is not None
        assert result["best_match"] == 0

    def test_self_vs_self_exact_match(self):
        g = _star(6, label="star")
        result = g.weighted_average_classification([g])
        assert result is not None
        assert result["best_match"] == 0
        assert result["best_score"] == 0.0  # minmax: self = min = 0

    def test_all_none_scores_returns_none(self, monkeypatch):
        g = _star(5)
        ref = _path(5)
        # Force all scoring methods to fail
        monkeypatch.setattr(g, "entropy_distance", lambda *a, **k: None)
        monkeypatch.setattr(g, "spectral_divergence", lambda *a, **k: None)
        monkeypatch.setattr(g, "fingerprint_distance", lambda *a, **k: None)
        assert g.weighted_average_classification([ref]) is None


# ── Validation ────────────────────────────────────────────────────

class TestValidation:
    def test_negative_degree_weight_raises(self):
        g = _star(5)
        with pytest.raises(ValueError, match="degree_weight"):
            g.weighted_average_classification([_path(5)], degree_weight=-1.0)

    def test_negative_spectral_weight_raises(self):
        g = _star(5)
        with pytest.raises(ValueError, match="spectral_weight"):
            g.weighted_average_classification([_path(5)], spectral_weight=-0.5)

    def test_negative_fingerprint_weight_raises(self):
        g = _star(5)
        with pytest.raises(ValueError, match="fingerprint_weight"):
            g.weighted_average_classification([_path(5)], fingerprint_weight=-2.0)

    def test_all_zero_weights_raises(self):
        g = _star(5)
        with pytest.raises(ValueError, match="at least one weight"):
            g.weighted_average_classification(
                [_path(5)],
                degree_weight=0, spectral_weight=0, fingerprint_weight=0)

    def test_invalid_normalise_raises(self):
        g = _star(5)
        with pytest.raises(ValueError, match="normalise"):
            g.weighted_average_classification([_path(5)], normalise="invalid")

    def test_valid_normalise_modes(self):
        g = _star(5)
        for mode in ("minmax", "softmax"):
            result = g.weighted_average_classification([_path(5)], normalise=mode)
            assert result is not None
            assert result["normalise"] == mode


# ── Weight normalisation ──────────────────────────────────────────

class TestWeightNormalisation:
    def test_equal_weights_normalised(self):
        g = _star(5)
        result = g.weighted_average_classification(
            [_path(5), _cycle(5)],
            degree_weight=1.0, spectral_weight=1.0, fingerprint_weight=1.0)
        w = result["weights"]
        assert abs(w[0] - 1/3) < 1e-6
        assert abs(w[1] - 1/3) < 1e-6
        assert abs(w[2] - 1/3) < 1e-6

    def test_unequal_weights_normalised(self):
        g = _star(5)
        result = g.weighted_average_classification(
            [_path(5), _cycle(5)],
            degree_weight=3.0, spectral_weight=1.0, fingerprint_weight=0.0)
        w = result["weights"]
        assert abs(w[0] - 0.75) < 1e-6
        assert abs(w[1] - 0.25) < 1e-6
        assert w[2] == 0.0

    def test_zero_weight_excludes_modality(self):
        g = _star(5)
        result = g.weighted_average_classification(
            [_path(5), _cycle(5)],
            degree_weight=0, spectral_weight=0, fingerprint_weight=1.0)
        assert "fingerprint" in result["methods_used"]
        assert "degree" not in result["methods_used"]
        assert "spectral" not in result["methods_used"]

    def test_weights_sum_to_one(self):
        g = _star(5)
        result = g.weighted_average_classification(
            [_path(5), _cycle(5), _complete(5)],
            degree_weight=2.0, spectral_weight=3.0, fingerprint_weight=5.0)
        assert abs(sum(result["weights"]) - 1.0) < 1e-6


# ── Basic classification ──────────────────────────────────────────

class TestBasicClassification:
    def test_star_matches_star_over_path(self):
        query = _star(6)
        refs = [_path(6), _star(6), _cycle(6)]
        result = query.weighted_average_classification(refs)
        assert result["best_match"] == 1  # star is ref[1]

    def test_path_matches_path_over_star(self):
        query = _path(6)
        refs = [_star(6), _path(6), _cycle(6)]
        result = query.weighted_average_classification(refs)
        assert result["best_match"] == 1  # path is ref[1]

    def test_self_classification_score_zero(self):
        query = _star(6)
        result = query.weighted_average_classification([query, _path(6)])
        assert result["best_match"] == 0
        assert result["best_score"] == 0.0  # self = min in minmax

    def test_rankings_sorted_ascending_minmax(self):
        query = _star(6)
        refs = [_path(6), _star(6), _cycle(6), _complete(6)]
        result = query.weighted_average_classification(refs, normalise="minmax")
        scores = [r["score"] for r in result["rankings"]]
        assert scores == sorted(scores)

    def test_rankings_sorted_descending_softmax(self):
        query = _star(6)
        refs = [_path(6), _star(6), _cycle(6), _complete(6)]
        result = query.weighted_average_classification(refs, normalise="softmax")
        scores = [r["score"] for r in result["rankings"]]
        assert scores == sorted(scores, reverse=True)

    def test_result_has_expected_keys(self):
        query = _star(6)
        result = query.weighted_average_classification([_path(6), _cycle(6)])
        expected = {"best_match", "best_score", "rankings", "weights",
                    "normalise", "methods_used", "confidence", "margin"}
        assert expected.issubset(result.keys())

    def test_ranking_entry_has_expected_keys(self):
        query = _star(6)
        result = query.weighted_average_classification([_path(6), _cycle(6)])
        entry = result["rankings"][0]
        expected = {"index", "score", "degree_raw", "spectral_raw",
                    "fingerprint_raw", "degree_norm", "spectral_norm",
                    "fingerprint_norm", "label"}
        assert expected.issubset(entry.keys())


# ── Weight influence ─────────────────────────────────────────────

class TestWeightInfluence:
    def test_degree_only_vs_fingerprint_only_may_differ(self):
        """When degree and fingerprint disagree on best match,
        using only one vs only the other should reflect that."""
        query = _star(8)
        refs = [_path(8), _cycle(8), _complete(8)]

        d_only = query.weighted_average_classification(
            refs, degree_weight=1, spectral_weight=0, fingerprint_weight=0)
        f_only = query.weighted_average_classification(
            refs, degree_weight=0, spectral_weight=0, fingerprint_weight=1)

        # Both should produce valid results
        assert d_only is not None
        assert f_only is not None
        assert "degree" in d_only["methods_used"]
        assert "fingerprint" in f_only["methods_used"]

    def test_heavy_degree_weight_favours_degree_ranking(self):
        """With degree_weight=100, result should closely match degree-only."""
        query = _star(7)
        refs = [_path(7), _star(7), _cycle(7), _complete(7)]

        d_only = query.weighted_average_classification(
            refs, degree_weight=1, spectral_weight=0, fingerprint_weight=0)
        heavy_d = query.weighted_average_classification(
            refs, degree_weight=100, spectral_weight=1, fingerprint_weight=1)

        # Best match should agree when degree dominates
        assert d_only["best_match"] == heavy_d["best_match"]

    def test_spectral_only_classification(self):
        query = _star(6)
        refs = [_path(6), _star(6), _cycle(6)]
        result = query.weighted_average_classification(
            refs, degree_weight=0, spectral_weight=1.0, fingerprint_weight=0)
        assert result is not None
        assert "spectral" in result["methods_used"]
        assert result["best_match"] == 1  # star matches star

    def test_fingerprint_only_classification(self):
        query = _star(6)
        refs = [_path(6), _star(6), _cycle(6)]
        result = query.weighted_average_classification(
            refs, degree_weight=0, spectral_weight=0, fingerprint_weight=1.0)
        assert result is not None
        assert "fingerprint" in result["methods_used"]


# ── Normalisation modes ───────────────────────────────────────────

class TestNormalisationModes:
    def test_minmax_best_score_is_zero(self):
        """In minmax mode, best match always has normalised score 0
        (the minimum raw score maps to 0)."""
        query = _star(6)
        result = query.weighted_average_classification(
            [_path(6), _star(6)], normalise="minmax")
        assert result["best_score"] == 0.0

    def test_softmax_scores_sum_to_one_per_modality(self):
        """Softmax normalised scores for each modality sum to 1
        across references (for valid entries)."""
        query = _star(6)
        refs = [_path(6), _star(6), _cycle(6)]
        result = query.weighted_average_classification(
            refs, normalise="softmax")
        # Check that degree_norm values sum to ~1
        d_norms = [r["degree_norm"] for r in result["rankings"]
                   if r["degree_norm"] is not None]
        assert abs(sum(d_norms) - 1.0) < 0.01

    def test_softmax_best_score_positive(self):
        query = _star(6)
        result = query.weighted_average_classification(
            [_path(6), _star(6)], normalise="softmax")
        assert result["best_score"] > 0

    def test_minmax_and_softmax_same_best_match(self):
        """Both normalisation modes should identify the same best match
        for well-separated reference graphs."""
        query = _star(6)
        refs = [_path(6), _star(6), _cycle(6)]
        mm = query.weighted_average_classification(refs, normalise="minmax")
        sm = query.weighted_average_classification(refs, normalise="softmax")
        assert mm["best_match"] == sm["best_match"]


# ── Confidence and margin ─────────────────────────────────────────

class TestConfidenceMargin:
    def test_single_reference_margin_zero(self):
        query = _star(5)
        result = query.weighted_average_classification([_path(5)])
        assert result["margin"] == 0.0

    def test_multiple_references_margin_positive(self):
        query = _star(6)
        refs = [_path(6), _star(6), _cycle(6)]
        result = query.weighted_average_classification(refs)
        assert result["margin"] > 0

    def test_confidence_non_negative(self):
        query = _star(6)
        refs = [_path(6), _star(6), _cycle(6)]
        result = query.weighted_average_classification(refs)
        assert result["confidence"] >= 0

    def test_exact_match_confidence_high(self):
        query = _star(6)
        result = query.weighted_average_classification(
            [query, _path(6)], normalise="minmax")
        # Self-match gets norm = 0, so best = 0 → very high confidence
        assert result["confidence"] > 1e6


# ── Methods used tracking ─────────────────────────────────────────

class TestMethodsUsed:
    def test_all_three_methods_used_by_default(self):
        query = _star(6)
        refs = [_path(6), _cycle(6)]
        result = query.weighted_average_classification(refs)
        assert "degree" in result["methods_used"]
        assert "spectral" in result["methods_used"]
        assert "fingerprint" in result["methods_used"]

    def test_only_requested_methods_used(self):
        query = _star(6)
        refs = [_path(6), _cycle(6)]
        result = query.weighted_average_classification(
            refs, degree_weight=0, spectral_weight=0, fingerprint_weight=1.0)
        assert result["methods_used"] == ["fingerprint"]

    def test_zero_weight_modality_not_in_methods(self):
        query = _star(6)
        refs = [_path(6), _cycle(6)]
        result = query.weighted_average_classification(
            refs, degree_weight=1.0, spectral_weight=0, fingerprint_weight=1.0)
        assert "spectral" not in result["methods_used"]


# ── Non-mutating ──────────────────────────────────────────────────

class TestNonMutating:
    def test_query_graph_unchanged(self):
        query = _star(6)
        query_stats_before = query.stats()
        query.weighted_average_classification([_path(6), _cycle(6)])
        assert query.stats() == query_stats_before

    def test_reference_graphs_unchanged(self):
        query = _star(6)
        refs = [_path(6), _cycle(6)]
        ref_stats_before = [r.stats() for r in refs]
        query.weighted_average_classification(refs)
        for ref, before in zip(refs, ref_stats_before):
            assert ref.stats() == before


# ── Quarantined ───────────────────────────────────────────────────

class TestQuarantined:
    def test_include_quarantined_flag_accepted(self):
        query = _star(6)
        result = query.weighted_average_classification(
            [_path(6), _cycle(6)], include_quarantined=True)
        assert result is not None

    def test_exclude_quarantined_flag_accepted(self):
        query = _star(6)
        result = query.weighted_average_classification(
            [_path(6), _cycle(6)], include_quarantined=False)
        assert result is not None


# ── Robustness ────────────────────────────────────────────────────

class TestRobustness:
    def test_many_references(self):
        query = _star(6)
        refs = [_path(6), _cycle(6), _star(6), _complete(6),
                _path(5), _cycle(5)]
        result = query.weighted_average_classification(refs)
        assert result is not None
        assert 0 <= result["best_match"] < len(refs)

    def test_different_sizes_handled(self):
        query = _star(8)
        refs = [_path(5), _star(10), _cycle(6)]
        result = query.weighted_average_classification(refs)
        assert result is not None

    def test_all_equal_scores_no_crash(self):
        """All references identical → all scores equal → no division by zero."""
        query = _star(6)
        ref = _star(6)
        result = query.weighted_average_classification([ref, ref, ref])
        assert result is not None

    def test_label_extraction_from_graph_meta(self):
        query = _star(6)
        refs = [
            _path(6, label="pathway"),
            _star(6, label="stellar"),
            _cycle(6, label="circular"),
        ]
        result = query.weighted_average_classification(refs)
        for entry in result["rankings"]:
            assert entry["label"] is not None

    def test_no_graph_meta_uses_none_label(self):
        query = _star(6)
        refs = [_path(6), _cycle(6)]  # no graph_meta set
        result = query.weighted_average_classification(refs)
        for entry in result["rankings"]:
            assert entry["label"] is None

    def test_partial_graph_meta(self):
        query = _star(6)
        refs = [_path(6, label="path"), _cycle(6)]  # only ref[0] has label
        result = query.weighted_average_classification(refs)
        rankings_by_index = {r["index"]: r for r in result["rankings"]}
        assert rankings_by_index[0]["label"] == "path"
        assert rankings_by_index[1]["label"] is None


# ── Integration with other classification methods ─────────────────

class TestIntegrationWithOtherMethods:
    def test_agrees_with_graph_classification(self):
        """weighted_average with degree-only should agree with
        graph_classification on clear cases."""
        query = _star(6)
        refs = [_path(6), _star(6), _cycle(6)]

        gc = query.graph_classification(refs)
        wa = query.weighted_average_classification(
            refs, degree_weight=1, spectral_weight=0, fingerprint_weight=0)

        assert gc is not None
        assert wa is not None
        assert gc["best_match"] == wa["best_match"]

    def test_agrees_with_spectral_classification(self):
        query = _star(6)
        refs = [_path(6), _star(6), _cycle(6)]

        sc = query.spectral_classification(refs)
        wa = query.weighted_average_classification(
            refs, degree_weight=0, spectral_weight=1, fingerprint_weight=0)

        assert sc is not None
        assert wa is not None
        assert sc["best_match"] == wa["best_match"]

    def test_works_with_classification_with_rejection(self):
        query = _star(6)
        refs = [_path(6), _star(6), _cycle(6)]
        wa = query.weighted_average_classification(refs)
        rejected = query.classification_with_rejection(wa, threshold=0.5)
        assert rejected is not None
        assert "decision" in rejected

    def test_classification_compare_includes_method(self):
        """classification_compare runs all methods; this method is not
        included there (it's user-driven), but both should agree on
        the best match for clear cases."""
        query = _star(6)
        refs = [_path(6), _star(6), _cycle(6)]
        cc = query.classification_compare(refs)
        wa = query.weighted_average_classification(refs)
        assert cc["consensus_best"] == wa["best_match"]


# ── Determinism ───────────────────────────────────────────────────

class TestDeterminism:
    def test_same_result_on_repeat_call(self):
        query = _star(6)
        refs = [_path(6), _star(6), _cycle(6)]
        r1 = query.weighted_average_classification(refs)
        r2 = query.weighted_average_classification(refs)
        assert r1["best_match"] == r2["best_match"]
        assert r1["best_score"] == r2["best_score"]

    def test_different_degree_indices(self):
        """Different degree_index should still produce valid results."""
        query = _star(6)
        refs = [_path(6), _cycle(6)]
        for idx in ("sombor", "randic", "zagreb"):
            result = query.weighted_average_classification(
                refs, degree_index=idx)
            assert result is not None
