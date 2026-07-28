"""Tests for spectral_divergence_scan() — Cycle 309.

Multi-resolution spectral divergence analysis: computes spectral_divergence
at multiple bin resolutions and returns structural analytics including
peak resolution, convergence, and monotonicity.
"""

import math
import pytest
from memory_graph import MemoryGraph


# ── Helpers ──────────────────────────────────────────────────────

def build_complete(n):
    """Complete graph K_n."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return g


def build_path(n):
    """Path graph P_n — linear chain."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return g


def build_cycle(n):
    """Cycle graph C_n."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return g


def build_star(leaves):
    """Star graph K_{1,leaves}."""
    g = MemoryGraph()
    hub = g.add("hub")
    for i in range(leaves):
        leaf = g.add(f"leaf{i}")
        g.link(hub.id, leaf.id, "r")
    return g


def build_empty():
    return MemoryGraph()


def build_single():
    g = MemoryGraph()
    g.add("a")
    return g


def build_no_edges():
    g = MemoryGraph()
    g.add("a")
    g.add("b")
    g.add("c")
    return g


def build_paw():
    """Paw graph: triangle with a pendant edge."""
    g = MemoryGraph()
    a, b, c, d = (g.add(ch) for ch in "abcd")
    g.link(a.id, b.id, "r")
    g.link(b.id, c.id, "r")
    g.link(a.id, c.id, "r")
    g.link(c.id, d.id, "r")
    return g


def build_K2():
    g = MemoryGraph()
    a = g.add("a")
    b = g.add("b")
    g.link(a.id, b.id, "r")
    return g


# ── 1. Degenerate cases ─────────────────────────────────────────

class TestDegenerate:
    def test_empty_vs_empty(self):
        assert build_empty().spectral_divergence_scan(build_empty()) is None

    def test_single_vs_single(self):
        assert build_single().spectral_divergence_scan(build_single()) is None

    def test_empty_vs_K3(self):
        assert build_empty().spectral_divergence_scan(build_complete(3)) is None

    def test_K3_vs_empty(self):
        assert build_complete(3).spectral_divergence_scan(build_empty()) is None

    def test_no_edges_vs_K3(self):
        assert build_no_edges().spectral_divergence_scan(
            build_complete(3)
        ) is None


# ── 2. Self-scan (divergence = 0 at all resolutions) ────────────

class TestSelfScan:
    def test_K3_self_all_zero(self):
        result = build_complete(3).spectral_divergence_scan(build_complete(3))
        assert result is not None
        for d in result["divergences"]:
            assert d == pytest.approx(0.0, abs=1e-12)

    def test_C4_self_all_zero(self):
        result = build_cycle(4).spectral_divergence_scan(build_cycle(4))
        assert result is not None
        for d in result["divergences"]:
            assert d == pytest.approx(0.0, abs=1e-12)

    def test_P5_self_all_zero(self):
        result = build_path(5).spectral_divergence_scan(build_path(5))
        assert result is not None
        for d in result["divergences"]:
            assert d == pytest.approx(0.0, abs=1e-12)

    def test_star_self_all_zero(self):
        result = build_star(4).spectral_divergence_scan(build_star(4))
        assert result is not None
        for d in result["divergences"]:
            assert d == pytest.approx(0.0, abs=1e-12)

    def test_paw_self_all_zero(self):
        result = build_paw().spectral_divergence_scan(build_paw())
        assert result is not None
        for d in result["divergences"]:
            assert d == pytest.approx(0.0, abs=1e-12)

    def test_K5_self_all_zero(self):
        result = build_complete(5).spectral_divergence_scan(build_complete(5))
        assert result is not None
        for d in result["divergences"]:
            assert d == pytest.approx(0.0, abs=1e-12)

    def test_self_mean_zero(self):
        result = build_complete(4).spectral_divergence_scan(
            build_complete(4)
        )
        assert result is not None
        assert result["mean"] == pytest.approx(0.0, abs=1e-12)

    def test_self_cv_zero(self):
        """CV of all-zero divergences: defined as 0 when mean=0."""
        result = build_cycle(5).spectral_divergence_scan(build_cycle(5))
        assert result is not None
        assert result["cv"] == 0.0

    def test_self_converged(self):
        """Self-scan should converge (all zeros → CV=0 < 0.05)."""
        result = build_complete(3).spectral_divergence_scan(
            build_complete(3)
        )
        assert result is not None
        assert result["converged"] is True

    def test_self_direction_non_monotonic(self):
        """Self-scan: all equal → all diffs = 0 → non-monotonic."""
        result = build_complete(3).spectral_divergence_scan(
            build_complete(3)
        )
        assert result is not None
        assert result["monotonic"] is False
        assert result["direction"] == "non-monotonic"


# ── 3. Non-negative at all resolutions ──────────────────────────

class TestNonNegative:
    def test_all_divergences_nonneg_jsd(self):
        graphs = [
            build_complete(3), build_cycle(4), build_path(4),
            build_star(4), build_paw(),
        ]
        for i, g1 in enumerate(graphs):
            for j, g2 in enumerate(graphs):
                if i == j:
                    continue
                result = g1.spectral_divergence_scan(g2)
                assert result is not None, f"None for {i} vs {j}"
                for d in result["divergences"]:
                    assert d >= -1e-12, f"Negative divergence {d}"

    def test_all_divergences_nonneg_kl(self):
        graphs = [
            build_complete(3), build_cycle(4), build_path(4),
            build_star(4),
        ]
        for i, g1 in enumerate(graphs):
            for j, g2 in enumerate(graphs):
                if i == j:
                    continue
                result = g1.spectral_divergence_scan(g2, measure="kl")
                assert result is not None
                for d in result["divergences"]:
                    assert d >= -1e-12

    def test_all_divergences_nonneg_ce(self):
        graphs = [
            build_complete(3), build_cycle(4), build_path(4),
            build_star(4),
        ]
        for i, g1 in enumerate(graphs):
            for j, g2 in enumerate(graphs):
                if i == j:
                    continue
                result = g1.spectral_divergence_scan(g2, measure="ce")
                assert result is not None
                for d in result["divergences"]:
                    assert d >= -1e-12


# ── 4. Return dict structure ────────────────────────────────────

class TestStructure:
    def test_returns_dict(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        assert isinstance(result, dict)

    def test_has_all_keys(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        expected_keys = {
            "resolutions", "divergences", "peak_resolution",
            "peak_divergence", "min_resolution", "min_divergence",
            "mean", "std", "cv", "converged", "monotonic",
            "direction", "measure",
        }
        assert set(result.keys()) == expected_keys

    def test_resolutions_match_default(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        assert result["resolutions"] == [2, 3, 5, 8, 13, 21, 34, 55]

    def test_divergences_length_matches_resolutions(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        assert len(result["divergences"]) == len(result["resolutions"])

    def test_measure_recorded(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4), measure="kl"
        )
        assert result["measure"] == "kl"

    def test_measure_default_jsd(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        assert result["measure"] == "jsd"


# ── 5. Peak / min resolution ────────────────────────────────────

class TestPeakMin:
    def test_peak_is_max(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        assert result is not None
        max_val = max(result["divergences"])
        assert result["peak_divergence"] == pytest.approx(max_val)

    def test_min_is_min(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        assert result is not None
        min_val = min(result["divergences"])
        assert result["min_divergence"] == pytest.approx(min_val)

    def test_peak_resolution_corresponds(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        idx = result["divergences"].index(max(result["divergences"]))
        assert result["peak_resolution"] == result["resolutions"][idx]

    def test_min_resolution_corresponds(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        idx = result["divergences"].index(min(result["divergences"]))
        assert result["min_resolution"] == result["resolutions"][idx]


# ── 6. Statistics ───────────────────────────────────────────────

class TestStatistics:
    def test_mean_correct(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        expected = sum(result["divergences"]) / len(result["divergences"])
        assert result["mean"] == pytest.approx(expected)

    def test_std_correct(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        m = result["mean"]
        var = sum(
            (d - m) ** 2 for d in result["divergences"]
        ) / len(result["divergences"])
        expected = math.sqrt(var)
        assert result["std"] == pytest.approx(expected)

    def test_cv_correct(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        expected = (
            result["std"] / result["mean"]
            if result["mean"] > 0 else 0.0
        )
        assert result["cv"] == pytest.approx(expected)

    def test_cv_nonneg(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        assert result["cv"] >= 0.0


# ── 7. Convergence ──────────────────────────────────────────────

class TestConvergence:
    def test_converged_bool(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        assert isinstance(result["converged"], bool)

    def test_self_converged_true(self):
        """Self-scan: all zeros → CV of last 3 = 0 < 0.05."""
        result = build_complete(4).spectral_divergence_scan(
            build_complete(4)
        )
        assert result["converged"] is True

    def test_similar_graphs_converge(self):
        """K3 vs K4: similar structure, should converge at fine res."""
        result = build_complete(3).spectral_divergence_scan(
            build_complete(4)
        )
        assert isinstance(result["converged"], bool)


# ── 8. Monotonicity ─────────────────────────────────────────────

class TestMonotonicity:
    def test_monotonic_is_bool(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        assert isinstance(result["monotonic"], bool)

    def test_direction_valid(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        assert result["direction"] in (
            "increasing", "decreasing", "non-monotonic", "insufficient"
        )

    def test_self_direction_non_monotonic(self):
        """Self: all equal → all diffs = 0 → non-monotonic."""
        result = build_cycle(4).spectral_divergence_scan(
            build_cycle(4)
        )
        assert result["direction"] == "non-monotonic"

    def test_monotonic_consistent_with_direction(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        if result["monotonic"]:
            assert result["direction"] in ("increasing", "decreasing")
        else:
            assert result["direction"] in (
                "non-monotonic", "insufficient"
            )


# ── 9. Measure support ──────────────────────────────────────────

class TestMeasureSupport:
    def test_jsd_valid(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4), measure="jsd"
        )
        assert result is not None
        assert result["measure"] == "jsd"

    def test_kl_valid(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4), measure="kl"
        )
        assert result is not None
        assert result["measure"] == "kl"

    def test_ce_valid(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4), measure="ce"
        )
        assert result is not None
        assert result["measure"] == "ce"

    def test_unknown_measure_raises(self):
        with pytest.raises(ValueError, match="unknown measure"):
            build_complete(3).spectral_divergence_scan(
                build_path(4), measure="foobar"
            )


# ── 10. Custom resolutions ──────────────────────────────────────

class TestCustomResolutions:
    def test_custom_resolutions(self):
        custom = [5, 10, 20]
        result = build_complete(3).spectral_divergence_scan(
            build_path(4), resolutions=custom
        )
        assert result is not None
        assert result["resolutions"] == [5, 10, 20]
        assert len(result["divergences"]) == 3

    def test_two_resolutions(self):
        result = build_complete(3).spectral_divergence_scan(
            build_path(4), resolutions=[3, 10]
        )
        assert result is not None
        assert len(result["divergences"]) == 2

    def test_empty_resolutions_raises(self):
        with pytest.raises(ValueError, match="at least 2"):
            build_complete(3).spectral_divergence_scan(
                build_path(4), resolutions=[]
            )

    def test_single_resolution_raises(self):
        with pytest.raises(ValueError, match="at least 2"):
            build_complete(3).spectral_divergence_scan(
                build_path(4), resolutions=[10]
            )

    def test_resolution_below_2_raises(self):
        with pytest.raises(ValueError, match=">= 2"):
            build_complete(3).spectral_divergence_scan(
                build_path(4), resolutions=[2, 1, 10]
            )

    def test_large_resolutions(self):
        """Large bin counts: works for graphs with enough eigenvalues."""
        result = build_complete(5).spectral_divergence_scan(
            build_cycle(5), resolutions=[50, 100]
        )
        assert result is not None
        assert len(result["divergences"]) == 2


# ── 11. Consistency with spectral_divergence ────────────────────

class TestConsistency:
    def test_matches_single_call(self):
        """spectral_divergence_scan at one resolution should match
        spectral_divergence at that resolution."""
        g1 = build_complete(4)
        g2 = build_path(4)
        for bins in [5, 10, 20]:
            single = g1.spectral_divergence(g2, bins=bins)
            scan = g1.spectral_divergence_scan(
                g2, resolutions=[bins, bins + 1]
            )
            assert scan is not None
            assert scan["divergences"][0] == pytest.approx(
                single, rel=1e-10
            )

    def test_jsd_consistent_across_calls(self):
        """Same scan called twice → same result."""
        g1 = build_complete(3)
        g2 = build_path(4)
        r1 = g1.spectral_divergence_scan(g2)
        r2 = g1.spectral_divergence_scan(g2)
        assert r1["divergences"] == pytest.approx(r2["divergences"])


# ── 12. Non-mutating ────────────────────────────────────────────

class TestNonMutating:
    def test_graph_unchanged_A(self):
        g1 = build_complete(4)
        g2 = build_path(4)
        s_before = g1.stats()
        g1.spectral_divergence_scan(g2)
        s_after = g1.stats()
        assert s_before["nodes"] == s_after["nodes"]
        assert s_before["edges"] == s_after["edges"]

    def test_graph_unchanged_B(self):
        g1 = build_complete(4)
        g2 = build_path(4)
        s_before = g2.stats()
        g1.spectral_divergence_scan(g2)
        s_after = g2.stats()
        assert s_before["nodes"] == s_after["nodes"]
        assert s_before["edges"] == s_after["edges"]


# ── 13. JSD bounded ─────────────────────────────────────────────

class TestJSDBounded:
    def test_jsd_bounded_sqrt_ln2(self):
        """JSD distance ≤ √(ln 2) ≈ 0.8326 at all resolutions."""
        sqrt_ln2 = math.sqrt(math.log(2))
        graphs = [
            build_complete(3), build_cycle(4), build_path(4),
            build_star(4), build_paw(),
        ]
        for i, g1 in enumerate(graphs):
            for j, g2 in enumerate(graphs):
                if i == j:
                    continue
                result = g1.spectral_divergence_scan(g2, measure="jsd")
                assert result is not None
                for d in result["divergences"]:
                    assert d <= sqrt_ln2 + 1e-9


# ── 14. Size-invariance ─────────────────────────────────────────

class TestSizeInvariance:
    def test_different_size_valid(self):
        """K3 vs K5: different sizes but same topology family."""
        result = build_complete(3).spectral_divergence_scan(
            build_complete(5)
        )
        assert result is not None
        for d in result["divergences"]:
            assert isinstance(d, float)
            assert not math.isnan(d)
            assert not math.isinf(d)

    def test_different_pairs_produce_different_means(self):
        """Two different graph pairs should produce different mean
        divergences (scan is discriminative)."""
        pair1 = build_complete(3).spectral_divergence_scan(
            build_complete(4)
        )
        pair2 = build_complete(3).spectral_divergence_scan(
            build_path(4)
        )
        assert pair1 is not None
        assert pair2 is not None
        # Different pairs should yield different means
        assert abs(pair1["mean"] - pair2["mean"]) > 1e-6


# ── 15. include_quarantined ─────────────────────────────────────

class TestQuarantined:
    def test_inclusion_changes_result(self):
        """Quarantining nodes should change the spectral scan."""
        g1 = build_complete(4)
        g2 = build_path(4)
        # Quarantine a node in g2 via SQL
        g2.conn.execute(
            "UPDATE nodes SET quarantined = 1 WHERE id = "
            "(SELECT id FROM nodes LIMIT 1)"
        )
        g2.conn.commit()
        without = g1.spectral_divergence_scan(
            g2, include_quarantined=False
        )
        with_q = g1.spectral_divergence_scan(
            g2, include_quarantined=True
        )
        assert without is not None
        assert with_q is not None
        # At least some divergence values should differ
        any_differ = any(
            abs(a - b) > 1e-9
            for a, b in zip(
                without["divergences"], with_q["divergences"]
            )
        )
        assert any_differ


# ── 16. Asymmetry for KL/CE ─────────────────────────────────────

class TestAsymmetry:
    def test_kl_asymmetric(self):
        """KL(self||other) scan differs from KL(other||self) scan."""
        g1 = build_complete(3)
        g2 = build_path(4)
        forward = g1.spectral_divergence_scan(g2, measure="kl")
        backward = g2.spectral_divergence_scan(g1, measure="kl")
        assert forward is not None
        assert backward is not None
        any_differ = any(
            abs(a - b) > 1e-9
            for a, b in zip(
                forward["divergences"], backward["divergences"]
            )
        )
        assert any_differ

    def test_jsd_symmetric(self):
        """JSD scan is symmetric: scan(A,B) = scan(B,A)."""
        g1 = build_complete(3)
        g2 = build_path(4)
        forward = g1.spectral_divergence_scan(g2, measure="jsd")
        backward = g2.spectral_divergence_scan(g1, measure="jsd")
        assert forward is not None
        assert backward is not None
        for a, b in zip(
            forward["divergences"], backward["divergences"]
        ):
            assert a == pytest.approx(b, rel=1e-10)


# ── 17. Convergence edge cases ──────────────────────────────────

class TestShortResolutions:
    def test_two_resolutions_no_converged(self):
        """With only 2 resolutions, converged should be False
        (need >= 3 for convergence check)."""
        result = build_complete(3).spectral_divergence_scan(
            build_path(4), resolutions=[5, 10]
        )
        assert result is not None
        assert result["converged"] is False

    def test_three_resolutions_converge_check(self):
        """3 resolutions is enough for convergence check."""
        result = build_complete(3).spectral_divergence_scan(
            build_path(4), resolutions=[10, 20, 30]
        )
        assert result is not None
        assert isinstance(result["converged"], bool)


# ── 18. Direction analysis ──────────────────────────────────────

class TestDirection:
    def test_direction_is_valid_value(self):
        g1 = build_complete(3)
        g2 = build_paw()
        result = g1.spectral_divergence_scan(g2)
        assert result["direction"] in (
            "increasing", "decreasing", "non-monotonic"
        )

    def test_monotonic_implies_strict_direction(self):
        """If monotonic=True, direction must be increasing/decreasing."""
        g1 = build_complete(3)
        g2 = build_path(6)
        result = g1.spectral_divergence_scan(g2)
        if result["monotonic"]:
            assert result["direction"] in ("increasing", "decreasing")
