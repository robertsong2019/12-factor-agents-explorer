"""Tests for spectral_classification() — Cycle 318.

Classify a graph against reference graphs using spectral divergence,
spectral divergence scan, or entropy fingerprint distance.
"""
import math
import pytest
from memory_graph import MemoryGraph


def _make_complete(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return g


def _make_path(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return g


def _make_cycle(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return g


def _make_star(n):
    """Star graph: node 0 connected to all others."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(1, n):
        g.link(nodes[0].id, nodes[i].id, "r")
    return g


def _make_empty(n):
    g = MemoryGraph()
    for i in range(n):
        g.add(str(i))
    return g


# ── Degenerate cases ──

class TestDegenerate:
    def test_empty_references(self):
        g = _make_complete(3)
        assert g.spectral_classification([]) is None

    def test_self_in_empty(self):
        """Empty graph classifying against anything → None."""
        g = _make_empty(1)
        refs = [_make_complete(3)]
        result = g.spectral_classification(refs)
        assert result is None

    def test_all_degenerate_references(self):
        """All references too small → None."""
        g = _make_complete(3)
        refs = [_make_empty(0), _make_empty(1)]
        result = g.spectral_classification(refs)
        assert result is None


class TestValidation:
    def test_unknown_method(self):
        g = _make_complete(3)
        with pytest.raises(ValueError, match="unknown method"):
            g.spectral_classification([_make_path(3)], method="bogus")

    def test_unknown_measure_spectral(self):
        g = _make_complete(3)
        with pytest.raises(ValueError, match="unknown measure"):
            g.spectral_classification([_make_path(3)], method="spectral", measure="bogus")


# ── Method: spectral ──

class TestSpectralMethod:
    def test_best_match_self(self):
        """Self should match closest to identical graph."""
        k3 = _make_complete(3)
        p5 = _make_path(5)
        c4 = _make_cycle(4)
        k3_copy = _make_complete(3)
        result = k3.spectral_classification([k3_copy, p5, c4])
        assert result is not None
        assert result["best_match"] == 0
        assert result["best_score"] == pytest.approx(0.0, abs=1e-8)

    def test_ranking_sorted_ascending(self):
        k4 = _make_complete(4)
        p3 = _make_path(3)
        c5 = _make_cycle(5)
        s4 = _make_star(4)
        result = k4.spectral_classification([p3, c5, s4, _make_complete(4)])
        assert result is not None
        scores = [r["score"] for r in result["rankings"]]
        assert scores == sorted(scores)

    def test_method_field(self):
        k3 = _make_complete(3)
        result = k3.spectral_classification([_make_path(3)])
        assert result["method"] == "spectral"

    def test_measure_field(self):
        k3 = _make_complete(3)
        result = k3.spectral_classification([_make_path(3)], measure="kl")
        assert result["measure"] == "kl"

    def test_jsd_symmetric_best(self):
        """JSD is symmetric: classifying A vs [B] should give same score as B vs [A]."""
        k3 = _make_complete(3)
        c4 = _make_cycle(4)
        r1 = k3.spectral_classification([c4])
        r2 = c4.spectral_classification([k3])
        assert r1["best_score"] == pytest.approx(r2["best_score"], abs=1e-6)

    def test_kl_asymmetric(self):
        """KL is asymmetric: direction matters."""
        k3 = _make_complete(3)
        s4 = _make_star(4)
        r1 = k3.spectral_classification([s4], measure="kl")
        r2 = s4.spectral_classification([k3], measure="kl")
        assert r1["best_score"] != pytest.approx(r2["best_score"], abs=1e-6)

    def test_bins_parameter(self):
        """Different bin counts may produce different classifications."""
        k3 = _make_complete(3)
        refs = [_make_path(4), _make_cycle(5)]
        r20 = k3.spectral_classification(refs, bins=20)
        r5 = k3.spectral_classification(refs, bins=5)
        assert r20 is not None
        assert r5 is not None
        assert r20["best_score"] >= 0
        assert r5["best_score"] >= 0

    def test_best_match_complete_over_path(self):
        """K4 should be closer to K5 than to P5 (fingerprint method)."""
        k4 = _make_complete(4)
        k5 = _make_complete(5)
        p5 = _make_path(5)
        # Fingerprint method captures broader structural signal
        result = k4.spectral_classification([p5, k5], method="fingerprint")
        assert result["best_match"] == 1  # K5 is closer

    def test_best_match_cycle_over_star(self):
        """C4 should be closer to C5 than to S4 (fingerprint method)."""
        c4 = _make_cycle(4)
        c5 = _make_cycle(5)
        s4 = _make_star(4)
        result = c4.spectral_classification([s4, c5], method="fingerprint")
        assert result["best_match"] == 1  # C5 is closer


# ── Method: spectral_scan ──

class TestSpectralScanMethod:
    def test_best_match_self_scan(self):
        k3 = _make_complete(3)
        k3_copy = _make_complete(3)
        p4 = _make_path(4)
        result = k3.spectral_classification([k3_copy, p4], method="spectral_scan")
        assert result is not None
        assert result["best_match"] == 0
        assert result["best_score"] == pytest.approx(0.0, abs=1e-6)

    def test_method_field_scan(self):
        k3 = _make_complete(3)
        result = k3.spectral_classification([_make_path(3)], method="spectral_scan")
        assert result["method"] == "spectral_scan"

    def test_measure_field_scan(self):
        k3 = _make_complete(3)
        result = k3.spectral_classification([_make_path(3)], method="spectral_scan", measure="ce")
        assert result["measure"] == "ce"

    def test_scan_identifies_correct_match(self):
        """Scan should correctly identify K5 as closest to K4."""
        k4 = _make_complete(4)
        refs = [_make_path(3), _make_complete(5), _make_cycle(6)]
        r_scan = k4.spectral_classification(refs, method="spectral_scan")
        assert r_scan is not None
        # Scan mean correctly ranks K5 (index 1) as closest
        assert r_scan["best_match"] == 1

    def test_scan_ranking_ascending(self):
        k3 = _make_complete(3)
        refs = [_make_path(5), _make_cycle(4), _make_star(4)]
        result = k3.spectral_classification(refs, method="spectral_scan")
        scores = [r["score"] for r in result["rankings"]]
        assert scores == sorted(scores)


# ── Method: fingerprint ──

class TestFingerprintMethod:
    def test_best_match_self_fp(self):
        k3 = _make_complete(3)
        k3_copy = _make_complete(3)
        p5 = _make_path(5)
        result = k3.spectral_classification([p5, k3_copy], method="fingerprint")
        assert result is not None
        assert result["best_match"] == 1
        assert result["best_score"] == pytest.approx(0.0, abs=1e-6)

    def test_method_field_fp(self):
        k3 = _make_complete(3)
        result = k3.spectral_classification([_make_path(3)], method="fingerprint")
        assert result["method"] == "fingerprint"

    def test_measure_field_fp(self):
        k3 = _make_complete(3)
        result = k3.spectral_classification([_make_path(3)], method="fingerprint")
        assert result["measure"] == "l2"

    def test_fp_ranking_ascending(self):
        k4 = _make_complete(4)
        refs = [_make_path(3), _make_star(5), _make_cycle(6), _make_complete(5)]
        result = k4.spectral_classification(refs, method="fingerprint")
        scores = [r["score"] for r in result["rankings"]]
        assert scores == sorted(scores)

    def test_fp_best_complete_over_path(self):
        """K4 fingerprint closer to K5 than P5."""
        k4 = _make_complete(4)
        k5 = _make_complete(5)
        p5 = _make_path(5)
        result = k4.spectral_classification([p5, k5], method="fingerprint")
        assert result["best_match"] == 1

    def test_fp_ignore_measure_param(self):
        """measure param should be ignored for fingerprint method."""
        k3 = _make_complete(3)
        result = k3.spectral_classification(
            [_make_path(3)], method="fingerprint", measure="kl"
        )
        assert result["measure"] == "l2"


# ── Confidence & margin ──

class TestConfidence:
    def test_confidence_zero_for_single_ref(self):
        """With only 1 reference, margin = best - best = 0."""
        k3 = _make_complete(3)
        result = k3.spectral_classification([_make_path(3)])
        assert result["margin"] == 0.0
        assert result["confidence"] == 0.0

    def test_confidence_positive_for_multiple(self):
        """With >1 refs, margin > 0 when scores differ."""
        k3 = _make_complete(3)
        refs = [_make_complete(3), _make_path(5), _make_star(5)]
        result = k3.spectral_classification(refs)
        assert result["margin"] > 0
        assert result["confidence"] > 0

    def test_confidence_inf_when_best_zero(self):
        """When best_score = 0 (exact match) and second > 0 → inf."""
        k3 = _make_complete(3)
        k3_copy = _make_complete(3)
        p5 = _make_path(5)
        result = k3.spectral_classification([k3_copy, p5])
        assert result["best_score"] == pytest.approx(0.0, abs=1e-8)
        assert result["confidence"] == float("inf")

    def test_confidence_strong_separation(self):
        """Similar refs to self → high confidence."""
        k3 = _make_complete(3)
        refs = [_make_complete(3), _make_path(10), _make_star(10)]
        result = k3.spectral_classification(refs)
        assert result["confidence"] > 0.5 or result["confidence"] == float("inf")


# ── Ranking structure ──

class TestRankingStructure:
    def test_ranking_has_index_score_label(self):
        k3 = _make_complete(3)
        result = k3.spectral_classification([_make_path(3), _make_cycle(4)])
        for r in result["rankings"]:
            assert "index" in r
            assert "score" in r
            assert "label" in r

    def test_ranking_index_matches_input_order(self):
        k3 = _make_complete(3)
        refs = [_make_path(3), _make_cycle(4), _make_star(5)]
        result = k3.spectral_classification(refs)
        indices = sorted([r["index"] for r in result["rankings"]])
        assert indices == [0, 1, 2]

    def test_result_keys(self):
        k3 = _make_complete(3)
        result = k3.spectral_classification([_make_path(3)])
        expected_keys = {
            "best_match", "best_score", "rankings",
            "method", "measure", "confidence", "margin",
        }
        assert set(result.keys()) == expected_keys


# ── Non-mutating ──

class TestNonMutating:
    def test_self_unchanged(self):
        k3 = _make_complete(3)
        nodes_before = set(k3.conn.execute("SELECT id FROM nodes").fetchall())
        edges_before = set(k3.conn.execute("SELECT source, target FROM edges").fetchall())
        k3.spectral_classification([_make_path(3), _make_cycle(4)])
        nodes_after = set(k3.conn.execute("SELECT id FROM nodes").fetchall())
        edges_after = set(k3.conn.execute("SELECT source, target FROM edges").fetchall())
        assert nodes_before == nodes_after
        assert edges_before == edges_after

    def test_references_unchanged(self):
        k3 = _make_complete(3)
        ref = _make_path(4)
        ref_nodes_before = set(ref.conn.execute("SELECT id FROM nodes").fetchall())
        k3.spectral_classification([ref])
        ref_nodes_after = set(ref.conn.execute("SELECT id FROM nodes").fetchall())
        assert ref_nodes_before == ref_nodes_after


# ── Cross-method consistency ──

class TestCrossMethod:
    def test_all_methods_agree_on_self(self):
        """All 3 methods should identify exact match as best."""
        k3 = _make_complete(3)
        k3_copy = _make_complete(3)
        p5 = _make_path(5)
        refs = [p5, k3_copy]
        for method in ("spectral", "spectral_scan", "fingerprint"):
            result = k3.spectral_classification(refs, method=method)
            assert result["best_match"] == 1, f"method={method}"

    def test_all_methods_non_negative(self):
        k4 = _make_complete(4)
        refs = [_make_path(3), _make_cycle(5), _make_star(4)]
        for method in ("spectral", "spectral_scan", "fingerprint"):
            result = k4.spectral_classification(refs, method=method)
            for r in result["rankings"]:
                assert r["score"] >= 0, f"method={method}"


# ── Include quarantined ──

class TestQuarantined:
    def test_include_quarantined_spectral(self):
        k3 = _make_complete(3)
        ref = _make_path(4)
        # Add and quarantine a node in ref
        extra = ref.add("q1")
        ref.link("0", extra.id, "r")
        ref.node_quarantine(extra.id, "test")
        r_excl = k3.spectral_classification([ref], method="spectral", include_quarantined=False)
        r_incl = k3.spectral_classification([ref], method="spectral", include_quarantined=True)
        assert r_excl is not None
        assert r_incl is not None

    def test_include_quarantined_scan(self):
        k3 = _make_complete(3)
        ref = _make_cycle(4)
        extra = ref.add("q1")
        ref.link("0", extra.id, "r")
        ref.node_quarantine(extra.id, "test")
        r = k3.spectral_classification([ref], method="spectral_scan", include_quarantined=True)
        assert r is not None
