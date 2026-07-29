"""Tests for hybrid_classification() — Cycle 319.

Ensemble classification combining degree-based and spectral divergence
scores via min-max normalisation and weighted combination.
"""

import math
import pytest
from memory_graph import MemoryGraph


# ── Helpers ──

def _complete(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return g

def _path(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return g

def _cycle(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return g

def _star(n):
    """Star graph: node 0 connected to nodes 1..n-1."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(1, n):
        g.link(nodes[0].id, nodes[i].id, "r")
    return g

def _paw():
    """Paw graph: triangle on 0-1-2 with a pendant on 2."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(4)]
    g.link(nodes[0].id, nodes[1].id, "r")
    g.link(nodes[1].id, nodes[2].id, "r")
    g.link(nodes[0].id, nodes[2].id, "r")
    g.link(nodes[2].id, nodes[3].id, "r")
    return g

def _empty(n):
    g = MemoryGraph()
    for i in range(n):
        g.add(str(i))
    return g


# ── Degenerate cases ──

class TestDegenerate:
    def test_empty_references(self):
        g = _complete(3)
        assert g.hybrid_classification([]) is None

    def test_single_node_self(self):
        g = _empty(1)
        ref = _empty(1)
        assert g.hybrid_classification([ref]) is None

    def test_no_edges(self):
        g = _empty(2)
        refs = [_complete(3), _path(4)]
        result = g.hybrid_classification(refs)
        assert result is None

    def test_single_reference(self):
        """Single valid reference → best_match=0, margin=0."""
        g = _complete(4)
        ref = _complete(4)
        result = g.hybrid_classification([ref])
        assert result is not None
        assert result["best_match"] == 0
        assert result["margin"] == 0.0


# ── Validation ──

class TestValidation:
    def test_unknown_degree_method(self):
        g = _complete(3)
        with pytest.raises(ValueError, match="unknown degree_method"):
            g.hybrid_classification([_path(3)], degree_method="invalid")

    def test_unknown_spectral_method(self):
        g = _complete(3)
        with pytest.raises(ValueError, match="unknown spectral_method"):
            g.hybrid_classification([_path(3)], spectral_method="invalid")

    def test_bad_weights_length(self):
        g = _complete(3)
        with pytest.raises(ValueError, match="weights must be a 2-tuple"):
            g.hybrid_classification([_path(3)], weights=(0.5,))

    def test_zero_weights(self):
        g = _complete(3)
        with pytest.raises(ValueError, match="weights must sum to a positive"):
            g.hybrid_classification([_path(3)], weights=(0.0, 0.0))


# ── Basic classification ──

class TestBasicClassification:
    def test_self_is_best_match(self):
        """Self should be the best match when included in references."""
        g = _complete(5)
        refs = [_path(5), g, _star(5)]
        result = g.hybrid_classification(refs)
        assert result is not None
        assert result["best_match"] == 1  # self at index 1

    def test_ranking_sorted_ascending(self):
        g = _complete(4)
        refs = [_path(4), _complete(4), _star(4)]
        result = g.hybrid_classification(refs)
        scores = [r["score"] for r in result["rankings"]]
        assert scores == sorted(scores)

    def test_ranking_has_seven_keys(self):
        g = _complete(3)
        result = g.hybrid_classification([_complete(3), _path(3)])
        r = result["rankings"][0]
        expected_keys = {"index", "score", "degree_raw", "spectral_raw",
                         "degree_norm", "spectral_norm", "label"}
        assert set(r.keys()) == expected_keys

    def test_result_has_eight_keys(self):
        g = _complete(3)
        result = g.hybrid_classification([_complete(3), _path(3)])
        expected_keys = {"best_match", "best_score", "rankings",
                         "degree_method", "spectral_method", "weights",
                         "confidence", "margin"}
        assert set(result.keys()) == expected_keys

    def test_self_match_ensemble_zero(self):
        """Self vs self → both normalised scores = 0 → ensemble = 0."""
        g = _complete(4)
        refs = [g, _path(4)]
        result = g.hybrid_classification(refs)
        assert result is not None
        assert result["rankings"][0]["index"] == 0
        assert result["rankings"][0]["score"] == 0.0


# ── Normalisation ──

class TestNormalisation:
    def test_degree_norm_range_01(self):
        """Normalised degree scores should be in [0, 1]."""
        g = _complete(4)
        refs = [_complete(4), _path(4), _star(4), _cycle(4)]
        result = g.hybrid_classification(refs)
        for r in result["rankings"]:
            if r["degree_norm"] is not None:
                assert 0.0 <= r["degree_norm"] <= 1.0

    def test_spectral_norm_range_01(self):
        """Normalised spectral scores should be in [0, 1]."""
        g = _complete(4)
        refs = [_complete(4), _path(4), _star(4), _cycle(4)]
        result = g.hybrid_classification(refs)
        for r in result["rankings"]:
            if r["spectral_norm"] is not None:
                assert 0.0 <= r["spectral_norm"] <= 1.0

    def test_best_has_zero_norms(self):
        """Best match should have norm=0 in both modalities (or None)."""
        g = _complete(4)
        refs = [_complete(4), _path(4), _star(4)]
        result = g.hybrid_classification(refs)
        best = result["rankings"][0]
        if best["degree_norm"] is not None:
            assert best["degree_norm"] == 0.0
        if best["spectral_norm"] is not None:
            assert best["spectral_norm"] == 0.0

    def test_all_equal_scores_in_modality(self):
        """If all degree scores are equal, norms should all be 0."""
        g = _complete(3)
        refs = [_complete(3), _complete(3)]
        result = g.hybrid_classification(refs)
        for r in result["rankings"]:
            assert r["degree_norm"] == 0.0


# ── Weights ──

class TestWeights:
    def test_default_equal_weights(self):
        g = _complete(3)
        result = g.hybrid_classification([_complete(3), _path(3)])
        assert result["weights"] == (0.5, 0.5)

    def test_custom_weights_normalised(self):
        g = _complete(3)
        result = g.hybrid_classification(
            [_complete(3), _path(3)],
            weights=(3.0, 1.0),
        )
        assert result["weights"] == (0.75, 0.25)

    def test_degree_only_weights(self):
        """Weight (1, 0) → purely degree-based."""
        g = _complete(4)
        refs = [_complete(4), _path(4), _star(4)]
        result = g.hybrid_classification(refs, weights=(1.0, 0.0))
        for r in result["rankings"]:
            if r["degree_norm"] is not None:
                assert abs(r["score"] - r["degree_norm"]) < 1e-8

    def test_spectral_only_weights(self):
        """Weight (0, 1) → purely spectral."""
        g = _complete(4)
        refs = [_complete(4), _path(4), _star(4)]
        result = g.hybrid_classification(refs, weights=(0.0, 1.0))
        for r in result["rankings"]:
            if r["spectral_norm"] is not None:
                assert abs(r["score"] - r["spectral_norm"]) < 1e-8

    def test_unequal_weights_produce_valid_result(self):
        """Different weights should all produce valid results."""
        g = _paw()
        refs = [_complete(5), _path(5), _star(5), _cycle(5)]

        result_d = g.hybrid_classification(refs, weights=(1.0, 0.0))
        result_s = g.hybrid_classification(refs, weights=(0.0, 1.0))
        result_eq = g.hybrid_classification(refs, weights=(0.5, 0.5))

        assert result_d is not None
        assert result_s is not None
        assert result_eq is not None
        assert len(result_eq["rankings"]) == 4


# ── Degree method variants ──

class TestDegreeMethods:
    @pytest.mark.parametrize("method", ["jsd", "ce", "kl"])
    def test_all_degree_methods_produce_valid_result(self, method):
        g = _complete(4)
        refs = [_complete(4), _path(4), _star(4)]
        result = g.hybrid_classification(refs, degree_method=method)
        assert result is not None
        assert result["degree_method"] == method

    def test_jsd_vs_kl_may_differ(self):
        """JSD (symmetric) vs KL (asymmetric) can produce different rankings."""
        g = _paw()
        refs = [_path(4), _star(5), _cycle(5)]
        r_jsd = g.hybrid_classification(refs, degree_method="jsd")
        r_kl = g.hybrid_classification(refs, degree_method="kl")
        assert r_jsd is not None
        assert r_kl is not None
        assert len(r_jsd["rankings"]) == 3
        assert len(r_kl["rankings"]) == 3


# ── Spectral method variants ──

class TestSpectralMethods:
    @pytest.mark.parametrize("method", ["spectral", "spectral_scan", "fingerprint"])
    def test_all_spectral_methods_produce_valid_result(self, method):
        g = _complete(4)
        refs = [_complete(4), _path(4), _star(4)]
        result = g.hybrid_classification(refs, spectral_method=method)
        assert result is not None
        assert result["spectral_method"] == method

    def test_spectral_measure_field(self):
        g = _complete(4)
        refs = [_complete(4), _path(4)]
        result = g.hybrid_classification(
            refs, spectral_method="spectral", spectral_measure="kl",
        )
        assert result is not None


# ── Confidence and margin ──

class TestConfidenceMargin:
    def test_single_ref_margin_zero(self):
        g = _complete(4)
        result = g.hybrid_classification([_complete(4)])
        assert result["margin"] == 0.0

    def test_multiple_refs_margin_nonneg(self):
        g = _paw()
        refs = [_path(4), _star(5), _cycle(5), _complete(5)]
        result = g.hybrid_classification(refs)
        assert result["margin"] >= 0.0

    def test_exact_match_confidence_inf(self):
        """If best ensemble score = 0 (exact match), confidence = inf."""
        g = _complete(4)
        refs = [g, _path(4), _star(4)]
        result = g.hybrid_classification(refs)
        assert math.isinf(result["confidence"])

    def test_strong_separation_confidence_high(self):
        """When best is clearly better than rest, confidence should be high."""
        g = _complete(5)
        refs = [_complete(5), _path(3)]
        result = g.hybrid_classification(refs)
        assert result["confidence"] > 0.5 or math.isinf(result["confidence"])


# ── Cross-modality consistency ──

class TestCrossModalityConsistency:
    def test_ensemble_between_degree_and_spectral(self):
        """Ensemble score should be between the two modality norms."""
        g = _paw()
        refs = [_path(5), _star(5), _cycle(5), _complete(5)]
        result = g.hybrid_classification(refs, weights=(0.5, 0.5))
        for r in result["rankings"]:
            if r["degree_norm"] is not None and r["spectral_norm"] is not None:
                lo = min(r["degree_norm"], r["spectral_norm"])
                hi = max(r["degree_norm"], r["spectral_norm"])
                assert lo - 1e-8 <= r["score"] <= hi + 1e-8

    def test_self_match_both_zero(self):
        """Self match should have 0 in both modalities when included."""
        g = _complete(5)
        refs = [g, _path(5), _star(5)]
        result = g.hybrid_classification(refs)
        self_rank = result["rankings"][0]
        assert self_rank["index"] == 0
        assert self_rank["degree_norm"] == 0.0
        assert self_rank["spectral_norm"] == 0.0

    def test_agrees_with_graph_classification_for_clear_case(self):
        """For a clear case, hybrid (degree-only) should agree with graph_classification."""
        g = _complete(5)
        refs = [_complete(5), _path(5)]
        hybrid_result = g.hybrid_classification(refs, weights=(1.0, 0.0))
        degree_result = g.graph_classification(refs, method="jsd")
        assert hybrid_result["best_match"] == degree_result["best_match"]


# ── Non-mutating ──

class TestNonMutating:
    def test_self_unchanged(self):
        g = _complete(4)
        edges_before = set(g.conn.execute("SELECT source, target FROM edges").fetchall())
        nodes_before = set(g.conn.execute("SELECT id FROM nodes").fetchall())
        g.hybrid_classification([_path(4), _star(4)])
        edges_after = set(g.conn.execute("SELECT source, target FROM edges").fetchall())
        nodes_after = set(g.conn.execute("SELECT id FROM nodes").fetchall())
        assert edges_before == edges_after
        assert nodes_before == nodes_after

    def test_references_unchanged(self):
        g = _complete(4)
        refs = [_path(4), _star(4)]
        ref_edges = []
        for ref in refs:
            ref_edges.append(set(ref.conn.execute("SELECT source, target FROM edges").fetchall()))
        g.hybrid_classification(refs)
        for ref, before in zip(refs, ref_edges):
            after = set(ref.conn.execute("SELECT source, target FROM edges").fetchall())
            assert before == after


# ── Include quarantined ──

class TestQuarantined:
    def test_include_quarantined_flag_accepted(self):
        g = _complete(4)
        refs = [_complete(4), _path(4)]
        result = g.hybrid_classification(refs, include_quarantined=True)
        assert result is not None

    def test_include_quarantined_false_default(self):
        g = _complete(4)
        refs = [_complete(4), _path(4)]
        result_default = g.hybrid_classification(refs)
        result_false = g.hybrid_classification(refs, include_quarantined=False)
        assert result_default is not None
        assert result_false is not None
        assert result_default["best_match"] == result_false["best_match"]


# ── Robustness ──

class TestRobustness:
    def test_many_references(self):
        """Should handle many references without error."""
        g = _complete(5)
        refs = [_complete(3), _path(3), _cycle(3), _star(3),
                _complete(4), _path(4), _cycle(4), _star(4),
                _complete(5), _path(5)]
        result = g.hybrid_classification(refs)
        assert result is not None
        assert len(result["rankings"]) == 10
        # K5 (index 8) should be best match for K5 query
        assert result["best_match"] == 8

    def test_different_graph_sizes(self):
        """Should handle references of different sizes."""
        g = _path(5)
        refs = [_complete(3), _path(7), _cycle(4)]
        result = g.hybrid_classification(refs)
        assert result is not None
        assert len(result["rankings"]) == 3

    def test_ensemble_score_nonneg(self):
        """All ensemble scores should be >= 0."""
        g = _paw()
        refs = [_path(4), _star(5), _cycle(5), _complete(5)]
        result = g.hybrid_classification(refs)
        for r in result["rankings"]:
            assert r["score"] >= 0.0


# ── Label propagation ──

class TestLabelPropagation:
    def test_label_none_when_absent(self):
        g = _complete(3)
        refs = [_complete(3), _path(3)]
        result = g.hybrid_classification(refs)
        for r in result["rankings"]:
            assert r["label"] is None


# ── Raw scores present ──

class TestRawScores:
    def test_degree_raw_nonneg(self):
        """Raw degree scores should be >= 0 (or None)."""
        g = _paw()
        refs = [_path(4), _star(5), _cycle(5)]
        result = g.hybrid_classification(refs)
        for r in result["rankings"]:
            if r["degree_raw"] is not None:
                assert r["degree_raw"] >= 0.0

    def test_spectral_raw_nonneg(self):
        """Raw spectral scores should be >= 0 (or None)."""
        g = _paw()
        refs = [_path(4), _star(5), _cycle(5)]
        result = g.hybrid_classification(refs)
        for r in result["rankings"]:
            if r["spectral_raw"] is not None:
                assert r["spectral_raw"] >= 0.0

    def test_raw_scores_match_direct_calls(self):
        """Raw scores in rankings should match direct method calls."""
        g = _complete(4)
        ref = _path(4)
        result = g.hybrid_classification([ref, _star(4)])
        direct_degree = g.entropy_distance(ref, index="sombor")
        for r in result["rankings"]:
            if r["index"] == 0 and r["degree_raw"] is not None and direct_degree is not None:
                assert abs(r["degree_raw"] - round(direct_degree, 8)) < 1e-6
