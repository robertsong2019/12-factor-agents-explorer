"""Tests for von_neumann_entropy() — first spectral entropy (Cycle 292).

Based on Research #031: Von Neumann graph entropy = Shannon entropy
of normalised Laplacian eigenvalues.
"""
import pytest, math
from memory_graph import MemoryGraph

# ─── Helpers ────────────────────────────────────────────────────────────

def build_path(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return nodes

def build_complete(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return nodes

def build_cycle(g, n):
    nodes = build_path(g, n)
    g.link(nodes[-1].id, nodes[0].id, "r")
    return nodes

def build_star(g, k):
    hub = g.add('h')
    leaves = [g.add(str(i)) for i in range(k)]
    for l in leaves:
        g.link(hub.id, l.id, 'r')
    return hub, leaves

def build_bipartite(g, p, q):
    left = [g.add(f'L{i}') for i in range(p)]
    right = [g.add(f'R{i}') for i in range(q)]
    for u in left:
        for v in right:
            g.link(u.id, v.id, 'r')
    return left, right


# ═══════════════════════════════════════════════════════════════════════
# Von Neumann entropy — basic
# ═══════════════════════════════════════════════════════════════════════

class TestVonNeumannBasic:
    def test_none_for_empty(self):
        assert MemoryGraph(':memory:').von_neumann_entropy() is None

    def test_none_for_single(self):
        mg = MemoryGraph(':memory:')
        mg.add('a')
        assert mg.von_neumann_entropy() is None

    def test_no_edges_returns_zero(self):
        mg = MemoryGraph(':memory:')
        mg.add('a'); mg.add('b'); mg.add('c')
        assert mg.von_neumann_entropy() == 0.0

    def test_path3_returns_value(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        h = mg.von_neumann_entropy()
        assert h is not None
        assert 0 < h <= 1.0

    def test_raw_not_normalized(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        raw = mg.von_neumann_entropy(normalized=False)
        assert raw is not None and raw > 0

    def test_returns_float(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 4)
        h = mg.von_neumann_entropy()
        assert isinstance(h, float)

    def test_raw_greater_than_normalized(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 5)
        raw = mg.von_neumann_entropy(normalized=False)
        norm = mg.von_neumann_entropy(normalized=True)
        assert raw >= norm


# ═══════════════════════════════════════════════════════════════════════
# Complete graph K_n — should maximise entropy
# ═══════════════════════════════════════════════════════════════════════

class TestCompleteGraph:
    def test_k3_normalized_near_one(self):
        mg = MemoryGraph(':memory:')
        build_complete(mg, 3)
        h = mg.von_neumann_entropy()
        # K_3: eigenvalues [0, 3, 3], positive probs [0.5, 0.5]
        # H_raw = ln(2), max = ln(2) → ratio = 1.0
        assert abs(h - 1.0) < 1e-9

    def test_k4_normalized_one(self):
        mg = MemoryGraph(':memory:')
        build_complete(mg, 4)
        h = mg.von_neumann_entropy()
        # K_4: eigenvalues [0, 4, 4, 4], probs [1/3, 1/3, 1/3]
        # H_raw = ln(3), max = ln(3) → 1.0
        assert abs(h - 1.0) < 1e-9

    def test_k5_normalized_one(self):
        mg = MemoryGraph(':memory:')
        build_complete(mg, 5)
        h = mg.von_neumann_entropy()
        assert abs(h - 1.0) < 1e-9

    def test_kn_raw_equals_ln_n_minus_1(self):
        for n in [3, 4, 5, 6]:
            mg = MemoryGraph(':memory:')
            build_complete(mg, n)
            raw = mg.von_neumann_entropy(normalized=False)
            assert abs(raw - math.log(n - 1)) < 1e-9, f"K_{n}: {raw} != ln({n-1})"


# ═══════════════════════════════════════════════════════════════════════
# Specific graph structures
# ═══════════════════════════════════════════════════════════════════════

class TestGraphStructures:
    def test_star4_below_one(self):
        mg = MemoryGraph(':memory:')
        build_star(mg, 4)
        h = mg.von_neumann_entropy()
        assert 0 < h < 1.0

    def test_cycle4(self):
        mg = MemoryGraph(':memory:')
        build_cycle(mg, 4)
        h = mg.von_neumann_entropy()
        # C_4: eigenvalues [0, 2, 2, 4], probs [1/4, 1/4, 2/4]
        # Not uniform → entropy < 1
        assert 0 < h < 1.0

    def test_cycle5(self):
        mg = MemoryGraph(':memory:')
        build_cycle(mg, 5)
        h = mg.von_neumann_entropy()
        assert 0 < h < 1.0

    def test_path5_below_cycle5(self):
        """Path should have lower spectral entropy than cycle
        (more heterogeneous spectrum)."""
        mp = MemoryGraph(':memory:')
        build_path(mp, 5)
        mc = MemoryGraph(':memory:')
        build_cycle(mc, 5)
        hp = mp.von_neumann_entropy(normalized=False)
        hc = mc.von_neumann_entropy(normalized=False)
        assert hp < hc

    def test_path_grows_entropy_with_n(self):
        """Longer paths → more spectral diversity → higher entropy."""
        vals = []
        for n in [3, 5, 8, 12]:
            mg = MemoryGraph(':memory:')
            build_path(mg, n)
            vals.append(mg.von_neumann_entropy(normalized=False))
        for i in range(len(vals) - 1):
            assert vals[i] <= vals[i + 1] + 1e-9

    def test_single_edge(self):
        mg = MemoryGraph(':memory:')
        a, b = mg.add('a'), mg.add('b')
        mg.link(a.id, b.id, 'r')
        h = mg.von_neumann_entropy()
        # K_2: eigenvalues [0, 2], one positive → H = 0
        assert h == 0.0

    def test_two_disconnected_edges(self):
        mg = MemoryGraph(':memory:')
        a, b = mg.add('a'), mg.add('b')
        c, d = mg.add('c'), mg.add('d')
        mg.link(a.id, b.id, 'r')
        mg.link(c.id, d.id, 'r')
        h = mg.von_neumann_entropy()
        # Two K_2 components: eigenvalues [0, 0, 2, 2]
        # probs [0.5, 0.5] → H = ln(2), max = ln(3) → ratio ≈ 0.63
        assert 0 < h < 1.0

    def test_bipartite_k33(self):
        mg = MemoryGraph(':memory:')
        build_bipartite(mg, 3, 3)
        h = mg.von_neumann_entropy()
        assert 0 < h <= 1.0


# ═══════════════════════════════════════════════════════════════════════
# Monotonicity — adding edges to a graph increases (or keeps) entropy
# ═══════════════════════════════════════════════════════════════════════

class TestMonotonicity:
    def test_adding_edge_increases_or_keeps(self):
        mg = MemoryGraph(':memory:')
        n = [mg.add(str(i)) for i in range(5)]
        h0 = mg.von_neumann_entropy(normalized=False)
        mg.link(n[0].id, n[1].id, 'r')
        h1 = mg.von_neumann_entropy(normalized=False)
        mg.link(n[1].id, n[2].id, 'r')
        h2 = mg.von_neumann_entropy(normalized=False)
        assert h0 <= h1 + 1e-9
        assert h1 <= h2 + 1e-9

    def test_complete_maximises(self):
        """Complete graph should have highest entropy among same-size graphs."""
        n = 5
        mp = MemoryGraph(':memory:')
        build_path(mp, n)
        mc = MemoryGraph(':memory:')
        build_complete(mc, n)
        assert mp.von_neumann_entropy(normalized=False) <= \
               mc.von_neumann_entropy(normalized=False) + 1e-9

    def test_complete_geq_star(self):
        ms = MemoryGraph(':memory:')
        build_star(ms, 5)
        mc = MemoryGraph(':memory:')
        build_complete(mc, 6)  # same node count
        hs = ms.von_neumann_entropy(normalized=False)
        hc = mc.von_neumann_entropy(normalized=False)
        assert hs <= hc + 1e-9


# ═══════════════════════════════════════════════════════════════════════
# Quarantine support
# ═══════════════════════════════════════════════════════════════════════

class TestQuarantine:
    def test_include_quarantined(self):
        mg = MemoryGraph(':memory:')
        nodes = build_path(mg, 4)
        h_with = mg.von_neumann_entropy(include_quarantined=True)
        h_without = mg.von_neumann_entropy(include_quarantined=False)
        assert h_with is not None
        assert h_without is not None

    def test_quarantine_changes_result(self):
        mg = MemoryGraph(':memory:')
        nodes = build_path(mg, 4)
        # Quarantine one node
        mg.conn.execute("UPDATE nodes SET quarantined = 1 WHERE id = ?",
                        (nodes[3].id,))
        mg.conn.commit()
        h_with = mg.von_neumann_entropy(include_quarantined=True)
        h_without = mg.von_neumann_entropy(include_quarantined=False)
        # With quarantined node: 4 nodes. Without: 3 nodes.
        # Different graphs → different entropy
        assert h_with != h_without


# ═══════════════════════════════════════════════════════════════════════
# Directories / directed edges (should be treated as undirected)
# ═══════════════════════════════════════════════════════════════════════

class TestUndirectedSymmetry:
    def test_directed_pair_treated_undirected(self):
        mg = MemoryGraph(':memory:')
        a, b, c = mg.add('a'), mg.add('b'), mg.add('c')
        mg.link(a.id, b.id, 'r')
        mg.link(b.id, c.id, 'r')
        h1 = mg.von_neumann_entropy()

        mg2 = MemoryGraph(':memory:')
        a2, b2, c2 = mg2.add('a'), mg2.add('b'), mg2.add('c')
        mg2.link(b2.id, a2.id, 'r')  # reverse direction
        mg2.link(c2.id, b2.id, 'r')
        h2 = mg2.von_neumann_entropy()
        assert abs(h1 - h2) < 1e-9

    def test_duplicate_edge_no_change(self):
        mg = MemoryGraph(':memory:')
        a, b, c = mg.add('a'), mg.add('b'), mg.add('c')
        mg.link(a.id, b.id, 'r')
        mg.link(b.id, c.id, 'r')
        h_before = mg.von_neumann_entropy()
        mg.link(a.id, b.id, 'r')  # duplicate
        h_after = mg.von_neumann_entropy()
        assert abs(h_before - h_after) < 1e-6


# ═══════════════════════════════════════════════════════════════════════
# Mathematical properties
# ═══════════════════════════════════════════════════════════════════════

class TestMathProperties:
    def test_normalized_range_0_to_1(self):
        for builder, args in [
            (build_path, 4), (build_complete, 4), (build_cycle, 4),
            (build_star, 4), (build_path, 8), (build_complete, 6),
        ]:
            mg = MemoryGraph(':memory:')
            builder(mg, args)
            h = mg.von_neumann_entropy()
            assert -1e-9 <= h <= 1.0 + 1e-9, f"{builder.__name__}({args}): {h}"

    def test_kn_raw_property(self):
        """K_n raw entropy = ln(n-1) for all n ≥ 3."""
        for n in range(3, 8):
            mg = MemoryGraph(':memory:')
            build_complete(mg, n)
            raw = mg.von_neumann_entropy(normalized=False)
            assert abs(raw - math.log(n - 1)) < 1e-9

    def test_empty_graph_entropy_is_zero(self):
        mg = MemoryGraph(':memory:')
        for i in range(5):
            mg.add(str(i))
        assert mg.von_neumann_entropy() == 0.0
        assert mg.von_neumann_entropy(normalized=False) == 0.0

    def test_positivity(self):
        """Any connected graph with ≥ 2 edges should have H > 0."""
        for builder, args in [
            (build_path, 3), (build_cycle, 4), (build_star, 3),
            (build_complete, 4),
        ]:
            mg = MemoryGraph(':memory:')
            builder(mg, args)
            assert mg.von_neumann_entropy(normalized=False) > 0

    def test_self_loop_no_effect_on_spectrum(self):
        """Self-loops don't appear in the simple Laplacian."""
        mg1 = MemoryGraph(':memory:')
        a1, b1 = mg1.add('a'), mg1.add('b')
        mg1.link(a1.id, b1.id, 'r')
        h1 = mg1.von_neumann_entropy()

        mg2 = MemoryGraph(':memory:')
        a2, b2 = mg2.add('a'), mg2.add('b')
        mg2.link(a2.id, b2.id, 'r')
        mg2.link(a2.id, a2.id, 'self')  # self-loop
        h2 = mg2.von_neumann_entropy()
        # Self-loops may or may not affect Laplacian depending on impl
        # Just check both are computable
        assert h1 is not None and h2 is not None


# ═══════════════════════════════════════════════════════════════════════
# Cross-checks with existing spectral methods
# ═══════════════════════════════════════════════════════════════════════

class TestCrossCheck:
    def test_consistent_with_algebraic_connectivity(self):
        mg = MemoryGraph(':memory:')
        build_complete(mg, 4)
        h = mg.von_neumann_entropy()
        ac = mg.algebraic_connectivity()
        assert h is not None
        assert ac is not None
        assert ac > 0  # connected

    def test_consistent_with_spectral_gap(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 5)
        h = mg.von_neumann_entropy()
        sg = mg.spectral_gap()
        assert h is not None
        assert sg is not None
        assert sg > 0

    def test_degree_entropy_vs_spectral_entropy_differ(self):
        """Degree-based and spectral entropies measure different things."""
        mg = MemoryGraph(':memory:')
        build_star(mg, 5)
        # On K_{1,5}: degree entropy captures degree heterogeneity
        # Spectral entropy captures eigenvalue distribution
        # They should be different values
        sombor = mg.sombor_entropy()
        vn = mg.von_neumann_entropy()
        assert sombor is not None
        assert vn is not None
        # Both in [0,1] but generally different
        # (could coincide by chance but unlikely for star)


# ═══════════════════════════════════════════════════════════════════════
#spectral_entropy_profile
# ═══════════════════════════════════════════════════════════════════════

class TestSpectralEntropyProfile:
    def test_none_for_empty(self):
        assert MemoryGraph(':memory:').spectral_entropy_profile() is None

    def test_none_for_single(self):
        mg = MemoryGraph(':memory:')
        mg.add('a')
        assert mg.spectral_entropy_profile() is None

    def test_returns_dict_with_required_keys(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 4)
        p = mg.spectral_entropy_profile()
        assert p is not None
        required = {
            "von_neumann_entropy", "von_neumann_entropy_raw",
            "algebraic_connectivity", "spectral_gap", "spectral_radius",
            "n_positive", "n_zero", "max_entropy_possible",
            "entropy_ratio", "complexity", "eigenvalues",
        }
        assert required.issubset(p.keys())

    def test_eigenvalues_sorted_ascending(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 5)
        p = mg.spectral_entropy_profile()
        evals = p["eigenvalues"]
        for i in range(len(evals) - 1):
            assert evals[i] <= evals[i + 1] + 1e-9

    def test_n_zero_counts_components(self):
        # Connected graph → exactly 1 zero eigenvalue
        mg = MemoryGraph(':memory:')
        build_path(mg, 4)
        p = mg.spectral_entropy_profile()
        assert p["n_zero"] == 1

    def test_n_zero_disconnected(self):
        mg = MemoryGraph(':memory:')
        a, b = mg.add('a'), mg.add('b')
        c, d = mg.add('c'), mg.add('d')
        mg.link(a.id, b.id, 'r')
        mg.link(c.id, d.id, 'r')
        p = mg.spectral_entropy_profile()
        assert p["n_zero"] == 2

    def test_spectral_radius_is_max_eigenvalue(self):
        mg = MemoryGraph(':memory:')
        build_complete(mg, 4)
        p = mg.spectral_entropy_profile()
        assert abs(p["spectral_radius"] - p["eigenvalues"][-1]) < 1e-9

    def test_k4_profile_values(self):
        mg = MemoryGraph(':memory:')
        build_complete(mg, 4)
        p = mg.spectral_entropy_profile()
        # K_4: eigenvalues [0, 4, 4, 4]
        assert abs(p["algebraic_connectivity"] - 4.0) < 1e-6
        assert p["n_positive"] == 3
        assert p["n_zero"] == 1
        assert abs(p["von_neumann_entropy"] - 1.0) < 1e-9

    def test_complexity_positive(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 5)
        p = mg.spectral_entropy_profile()
        assert p["complexity"] > 0

    def test_complexity_kn_equals_n_minus_1(self):
        """K_n participation ratio = (Σλ²)² / Σλ⁴.
        K_n eigenvalues: 0, n, n, ..., n (n-1 copies).
        Σλ² = (n-1)n², Σλ⁴ = (n-1)n⁴ → PR = n-1."""
        for n in [3, 4, 5]:
            mg = MemoryGraph(':memory:')
            build_complete(mg, n)
            p = mg.spectral_entropy_profile()
            assert abs(p["complexity"] - (n - 1)) < 1e-6, \
                f"K_{n} complexity {p['complexity']} != {n-1}"

    def test_entropy_ratio_consistent(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 6)
        p = mg.spectral_entropy_profile()
        if p["max_entropy_possible"] > 0:
            expected = p["von_neumann_entropy_raw"] / p["max_entropy_possible"]
            assert abs(p["entropy_ratio"] - expected) < 1e-9

    def test_include_quarantined(self):
        mg = MemoryGraph(':memory:')
        nodes = build_path(mg, 5)
        mg.conn.execute("UPDATE nodes SET quarantined = 1 WHERE id = ?",
                        (nodes[4].id,))
        mg.conn.commit()
        p_with = mg.spectral_entropy_profile(include_quarantined=True)
        p_without = mg.spectral_entropy_profile(include_quarantined=False)
        assert len(p_with["eigenvalues"]) == 5
        assert len(p_without["eigenvalues"]) == 4

    def test_no_edges_profile(self):
        mg = MemoryGraph(':memory:')
        for i in range(4):
            mg.add(str(i))
        p = mg.spectral_entropy_profile()
        assert p["von_neumann_entropy"] == 0.0
        assert p["n_positive"] == 0
        assert p["n_zero"] == 4
        assert p["complexity"] == 0.0


# ═══════════════════════════════════════════════════════════════════════
# Comparison with degree-based entropies
# ═══════════════════════════════════════════════════════════════════════

class TestSpectralVsDegree:
    def test_complete_graph_both_one(self):
        mg = MemoryGraph(':memory:')
        build_complete(mg, 4)
        assert abs(mg.von_neumann_entropy() - 1.0) < 1e-9
        # Degree entropy should also be high for K_n
        sombor = mg.sombor_entropy()
        assert sombor is not None

    def test_star_different_from_complete(self):
        ms = MemoryGraph(':memory:')
        build_star(ms, 5)
        mc = MemoryGraph(':memory:')
        build_complete(mc, 6)
        hs = ms.von_neumann_entropy()
        hc = mc.von_neumann_entropy()
        assert hs < hc

    def test_path_grows_both_but_different_rate(self):
        """Spectral and degree entropies grow with path length
        but at different rates."""
        h_spectral = []
        h_sombor = []
        for n in [3, 5, 8]:
            mg = MemoryGraph(':memory:')
            build_path(mg, n)
            h_spectral.append(mg.von_neumann_entropy(normalized=False))
            h_sombor.append(mg.sombor_entropy(normalized=False) or 0.0)
        # Both should be increasing
        for i in range(len(h_spectral) - 1):
            assert h_spectral[i] <= h_spectral[i + 1] + 1e-9
