"""Tests for tsallis_entropy() — generalized Tsallis entropy of degree-based edge contributions.

S_q = (1 − Σ p_e^q) / (q − 1), where q is the entropic index.
q → 1 recovers Shannon entropy. q = 2 gives Gini-Simpson diversity.
Supports all 6 degree-based contribution types.

Cycle 281.
"""
import math
import pytest
from memory_graph import MemoryGraph


# ─── Helpers ────────────────────────────────────────────────────────────

def build_complete(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return nodes


def build_path(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return nodes


def build_cycle(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return nodes


def build_star(g, k):
    center = g.add("0")
    leaves = [g.add(str(i + 1)) for i in range(k)]
    for leaf in leaves:
        g.link(center.id, leaf.id, "r")
    return center, leaves


def build_paw(g):
    a, b, c, d = g.add("a"), g.add("b"), g.add("c"), g.add("d")
    g.link(a.id, b.id, "r")
    g.link(b.id, c.id, "r")
    g.link(a.id, c.id, "r")
    g.link(c.id, d.id, "r")
    return a, b, c, d


# ─── Degenerate cases ──────────────────────────────────────────────────

class TestTsallisDegenerate:
    def test_empty_graph(self):
        g = MemoryGraph()
        assert g.tsallis_entropy(q=2.0) is None

    def test_single_node(self):
        g = MemoryGraph()
        g.add("a")
        assert g.tsallis_entropy(q=2.0) is None

    def test_no_edges(self):
        g = MemoryGraph()
        g.add("a")
        g.add("b")
        assert g.tsallis_entropy(q=2.0) is None

    def test_q_equals_1_raises(self):
        """q=1 is Shannon entropy; should raise ValueError."""
        g = MemoryGraph()
        build_complete(g, 3)
        with pytest.raises(ValueError, match="q=1"):
            g.tsallis_entropy(q=1.0)


# ─── Regular graphs: normalized = 1.0 ─────────────────────────────────

class TestTsallisRegular:
    def test_k3_normalized_one(self):
        """K₃: uniform → Tsallis normalized = 1.0 for any q."""
        g = MemoryGraph()
        build_complete(g, 3)
        for q in [0.5, 1.5, 2.0, 3.0, 5.0]:
            val = g.tsallis_entropy(q=q, normalized=True)
            assert val == pytest.approx(1.0, abs=1e-10), f"q={q} failed"

    def test_k4_normalized_one(self):
        g = MemoryGraph()
        build_complete(g, 4)
        for q in [2.0, 3.0]:
            assert g.tsallis_entropy(q=q) == pytest.approx(1.0, abs=1e-10)

    def test_c4_normalized_one(self):
        g = MemoryGraph()
        build_cycle(g, 4)
        assert g.tsallis_entropy(q=2.0) == pytest.approx(1.0, abs=1e-10)

    def test_c5_normalized_one(self):
        g = MemoryGraph()
        build_cycle(g, 5)
        assert g.tsallis_entropy(q=2.0) == pytest.approx(1.0, abs=1e-10)

    def test_star_normalized_one(self):
        """K_{1,k}: all edges identical → normalized = 1.0."""
        g = MemoryGraph()
        build_star(g, 4)
        assert g.tsallis_entropy(q=2.0) == pytest.approx(1.0, abs=1e-10)


# ─── Irregular graphs: normalized < 1.0 ───────────────────────────────

class TestTsallisIrregular:
    def test_p4_less_than_one(self):
        g = MemoryGraph()
        build_path(g, 4)
        val = g.tsallis_entropy(q=2.0)
        assert val is not None
        assert 0 < val < 1.0

    def test_p5_less_than_one(self):
        g = MemoryGraph()
        build_path(g, 5)
        val = g.tsallis_entropy(q=2.0)
        assert val is not None
        assert 0 < val < 1.0

    def test_paw_less_than_one(self):
        g = MemoryGraph()
        build_paw(g)
        val = g.tsallis_entropy(q=2.0)
        assert val is not None
        assert 0 < val < 1.0


# ─── q-parameter behavior ─────────────────────────────────────────────

class TestTsallisQParameter:
    def test_higher_q_compresses_diversity(self):
        """For sufficiently irregular graphs, higher q → lower Tsallis raw entropy."""
        g = MemoryGraph()
        build_paw(g)  # Paw: highly irregular (triangle + pendant)
        q2 = g.tsallis_entropy(q=2.0, normalized=False)
        q5 = g.tsallis_entropy(q=5.0, normalized=False)
        assert q5 < q2

    def test_lower_q_amplifies_rare(self):
        """Lower q (superextensive) → higher normalized Tsallis."""
        g = MemoryGraph()
        build_path(g, 6)
        q05 = g.tsallis_entropy(q=0.5)
        q2 = g.tsallis_entropy(q=2.0)
        assert q05 > q2

    def test_q2_gini_simpson(self):
        """q=2 Tsallis = 1 − Σp² = Gini-Simpson index."""
        g = MemoryGraph()
        build_path(g, 4)
        # Manual calculation
        edges = g.conn.execute("SELECT source, target FROM edges").fetchall()
        deg = {str(r["id"]): g.degree(str(r["id"]))
               for r in g.conn.execute("SELECT id FROM nodes").fetchall()}
        # Sombor contributions
        contribs = []
        for r in edges:
            s, t = str(r["source"]), str(r["target"])
            ds, dt = deg.get(s, 0), deg.get(t, 0)
            contribs.append(math.sqrt(ds * ds + dt * dt))
        total = sum(contribs)
        probs = [c / total for c in contribs]
        gini_simpson = 1 - sum(p ** 2 for p in probs)
        # Tsallis q=2, normalized=False
        tsallis_raw = g.tsallis_entropy(q=2.0, normalized=False, index="sombor")
        assert tsallis_raw == pytest.approx(gini_simpson, abs=1e-10)

    def test_converges_to_shannon(self):
        """As q → 1, Tsallis raw → Shannon raw."""
        g = MemoryGraph()
        build_path(g, 5)
        shannon = g.sombor_entropy(normalized=False)
        tsallis_near1 = g.tsallis_entropy(q=1.001, normalized=False, index="sombor")
        assert tsallis_near1 == pytest.approx(shannon, abs=0.01)


# ─── Index parameter ──────────────────────────────────────────────────

class TestTsallisIndex:
    @pytest.mark.parametrize("index", [
        "sombor", "reduced_sombor", "randic", "zagreb_m1", "ga"
    ])
    def test_all_indices_return_float(self, index):
        g = MemoryGraph()
        build_path(g, 5)
        val = g.tsallis_entropy(q=2.0, index=index)
        assert val is not None
        assert isinstance(val, float)

    def test_abc_index_skips_k2(self):
        """ABC index skips K₂ edges."""
        g = MemoryGraph()
        build_path(g, 5)
        # P₅ has no K₂ edges (all degree pairs ≥ (1,2))
        val = g.tsallis_entropy(q=2.0, index="abc")
        assert val is not None

    def test_abc_index_only_k2_returns_none(self):
        """Pure K₂ graph: abc skips all edges → None."""
        g = MemoryGraph()
        a, b = g.add("a"), g.add("b")
        g.link(a.id, b.id, "r")
        val = g.tsallis_entropy(q=2.0, index="abc")
        assert val is None

    def test_unknown_index_raises(self):
        g = MemoryGraph()
        build_complete(g, 3)
        with pytest.raises(ValueError, match="unknown index"):
            g.tsallis_entropy(q=2.0, index="nonexistent")

    def test_different_indices_different_values(self):
        """Different indices give different Tsallis entropies on irregular graphs."""
        g = MemoryGraph()
        build_paw(g)
        vals = set()
        for idx in ["sombor", "randic", "zagreb_m1", "ga"]:
            v = g.tsallis_entropy(q=2.0, index=idx)
            if v is not None:
                vals.add(round(v, 8))
        # At least 2 distinct values
        assert len(vals) >= 2


# ─── Normalization ────────────────────────────────────────────────────

class TestTsallisNormalization:
    def test_normalized_bounded_01(self):
        """Normalized Tsallis should be in (0, 1]."""
        g = MemoryGraph()
        build_path(g, 8)
        for q in [0.5, 1.5, 2.0, 3.0, 5.0]:
            val = g.tsallis_entropy(q=q, normalized=True)
            assert 0 < val <= 1.0 + 1e-10, f"q={q}: val={val}"

    def test_raw_positive(self):
        """Raw Tsallis entropy is always non-negative."""
        g = MemoryGraph()
        build_path(g, 6)
        for q in [0.5, 1.5, 2.0, 3.0]:
            val = g.tsallis_entropy(q=q, normalized=False)
            assert val >= 0

    def test_normalized_regular_is_one(self):
        """Regular graphs → normalized = 1.0 regardless of q."""
        g = MemoryGraph()
        build_complete(g, 4)
        for q in [0.5, 2.0, 3.0, 10.0]:
            val = g.tsallis_entropy(q=q, normalized=True)
            assert val == pytest.approx(1.0, abs=1e-10)


# ─── Non-mutating ─────────────────────────────────────────────────────

class TestTsallisNonMutating:
    def test_does_not_add_nodes(self):
        g = MemoryGraph()
        build_complete(g, 3)
        before = len(g.conn.execute("SELECT id FROM nodes").fetchall())
        g.tsallis_entropy(q=2.0)
        after = len(g.conn.execute("SELECT id FROM nodes").fetchall())
        assert before == after

    def test_does_not_add_edges(self):
        g = MemoryGraph()
        build_path(g, 4)
        before = len(g.conn.execute("SELECT source, target FROM edges").fetchall())
        g.tsallis_entropy(q=3.0)
        after = len(g.conn.execute("SELECT source, target FROM edges").fetchall())
        assert before == after


# ─── Mathematical properties ──────────────────────────────────────────

class TestTsallisMath:
    def test_uniform_distribution(self):
        """For uniform p_e = 1/m: S_q(raw) = (m^(1-q) - 1)/(q-1) * m^(q-1)... actually:
        Σ p^q = m * (1/m)^q = m^(1-q)
        S_q = (1 - m^(1-q)) / (q-1)
        """
        g = MemoryGraph()
        build_complete(g, 3)  # K₃: 3 identical edges, p_e = 1/3
        m = 3
        q = 2.0
        expected_raw = (1.0 - m ** (1.0 - q)) / (q - 1.0)
        actual = g.tsallis_entropy(q=q, normalized=False, index="sombor")
        assert actual == pytest.approx(expected_raw, abs=1e-10)

    def test_normalized_divides_by_smax(self):
        """Normalized = raw / S_q^max where S_q^max = (1 - m^(1-q))/(q-1)."""
        g = MemoryGraph()
        build_path(g, 5)
        q = 2.0
        raw = g.tsallis_entropy(q=q, normalized=False)
        norm = g.tsallis_entropy(q=q, normalized=True)
        m = len(g.conn.execute("SELECT source, target FROM edges").fetchall())
        s_max = (1.0 - m ** (1.0 - q)) / (q - 1.0)
        assert norm == pytest.approx(raw / s_max, abs=1e-10)

    def test_q2_equals_gini_simpson_all_indices(self):
        """q=2 Tsallis = 1 − Σp² (Gini-Simpson) for all indices."""
        g = MemoryGraph()
        build_paw(g)
        for idx in ["sombor", "randic", "zagreb_m1", "ga"]:
            tsallis = g.tsallis_entropy(q=2.0, normalized=False, index=idx)
            # Manual: 1 - Σp²
            edges = g.conn.execute("SELECT source, target FROM edges").fetchall()
            deg = {str(r["id"]): g.degree(str(r["id"]))
                   for r in g.conn.execute("SELECT id FROM nodes").fetchall()}
            contribs = []
            for r in edges:
                s, t = str(r["source"]), str(r["target"])
                ds, dt = deg.get(s, 0), deg.get(t, 0)
                if ds <= 0 or dt <= 0:
                    continue
                if idx == "sombor":
                    contribs.append(math.sqrt(ds * ds + dt * dt))
                elif idx == "randic":
                    contribs.append(1.0 / math.sqrt(ds * dt))
                elif idx == "zagreb_m1":
                    contribs.append(float(ds + dt))
                elif idx == "ga":
                    contribs.append(2.0 * math.sqrt(ds * dt) / (ds + dt))
            total = sum(contribs)
            probs = [c / total for c in contribs]
            expected = 1.0 - sum(p ** 2 for p in probs)
            assert tsallis == pytest.approx(expected, abs=1e-10), f"{idx} mismatch"
