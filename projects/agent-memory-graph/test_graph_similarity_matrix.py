"""Tests for graph_similarity_matrix() — pairwise inter-graph measure matrix.

Computes N×N JSD/CE/KL across multiple MemoryGraphs.
Symmetric for JSD (upper triangle mirrored), asymmetric for CE/KL.
"""
import math
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def make_graph():
    """Factory fixture: returns a function to build a graph from edges."""
    def _make(edges, nodes=None):
        mg = MemoryGraph(":memory:")
        labels = {}
        node_set = set()
        for s, t in edges:
            if s not in node_set:
                labels[s] = mg.add(f"N{s}", "concept")
                node_set.add(s)
            if t not in node_set:
                labels[t] = mg.add(f"N{t}", "concept")
                node_set.add(t)
        for s, t in edges:
            mg.link(labels[s].id, labels[t].id, "relates")
        return mg
    return _make


@pytest.fixture
def triangle(make_graph):
    return make_graph([(1, 2), (2, 3), (3, 1)])


@pytest.fixture
def path_graph(make_graph):
    return make_graph([(1, 2), (2, 3)])


@pytest.fixture
def star(make_graph):
    return make_graph([(1, 2), (1, 3), (1, 4)])


@pytest.fixture
def kite(make_graph):
    """A kite graph: 1-2-3-4-5-1 plus 2-4. Varied degrees for non-trivial entropy."""
    return make_graph([(1, 2), (2, 3), (3, 4), (4, 5), (5, 1), (2, 4)])


@pytest.fixture
def paw(make_graph):
    """Paw graph: triangle 1-2-3-1 plus tail 3-4. Asymmetric degrees."""
    return make_graph([(1, 2), (2, 3), (3, 1), (3, 4)])


@pytest.fixture
def single_edge(make_graph):
    return make_graph([(1, 2)])


# ── Basic structure ────────────────────────────────────────

class TestSimilarityMatrixStructure:
    def test_returns_none_for_empty(self):
        mg = MemoryGraph(":memory:")
        assert mg.graph_similarity_matrix([]) is None

    def test_returns_none_for_single(self, triangle):
        assert triangle.graph_similarity_matrix([triangle]) is None

    def test_matrix_dimensions(self, triangle, path_graph, star):
        result = triangle.graph_similarity_matrix([triangle, path_graph, star])
        assert result["size"] == 3
        assert len(result["matrix"]) == 3
        for row in result["matrix"]:
            assert len(row) == 3

    def test_matrix_keys(self, triangle, path_graph):
        result = triangle.graph_similarity_matrix([triangle, path_graph])
        assert "matrix" in result
        assert "method" in result
        assert "index" in result
        assert "size" in result
        assert "symmetric" in result


# ── JSD symmetric properties ───────────────────────────────

class TestJSDMatrix:
    def test_diagonal_is_zero(self, triangle, path_graph, star):
        result = triangle.graph_similarity_matrix(
            [triangle, path_graph, star], method="jsd"
        )
        m = result["matrix"]
        for i in range(3):
            assert m[i][i] == 0.0

    def test_symmetric(self, triangle, path_graph, star):
        result = triangle.graph_similarity_matrix(
            [triangle, path_graph, star], method="jsd"
        )
        m = result["matrix"]
        for i in range(3):
            for j in range(3):
                assert m[i][j] == m[j][i]

    def test_symmetric_flag(self, triangle, path_graph):
        result = triangle.graph_similarity_matrix(
            [triangle, path_graph], method="jsd"
        )
        assert result["symmetric"] is True

    def test_identical_graphs_zero_distance(self, triangle, make_graph):
        clone = make_graph([(1, 2), (2, 3), (3, 1)])
        result = triangle.graph_similarity_matrix([triangle, clone], method="jsd")
        assert result["matrix"][0][1] == pytest.approx(0.0, abs=1e-6)

    def test_values_bounded_0_1(self, triangle, path_graph, star):
        result = triangle.graph_similarity_matrix(
            [triangle, path_graph, star], method="jsd"
        )
        for row in result["matrix"]:
            for val in row:
                if not math.isnan(val):
                    assert 0.0 <= val <= 1.0

    def test_different_indices(self, triangle, path_graph):
        """JSD matrix should work with different degree indices."""
        for idx in ["sombor", "randic", "zagreb_m1"]:
            result = triangle.graph_similarity_matrix(
                [triangle, path_graph], method="jsd", index=idx
            )
            assert result is not None
            assert result["index"] == idx


# ── Cross-entropy matrix ───────────────────────────────────

class TestCEMatrix:
    def test_asymmetric_flag(self, kite, paw, path_graph):
        """CE matrix should be marked as asymmetric."""
        result = kite.graph_similarity_matrix(
            [kite, paw, path_graph], method="ce"
        )
        assert result["symmetric"] is False

    def test_diagonal_is_entropy(self, kite):
        """CE(G, G) = H(G) — self cross-entropy equals own entropy."""
        result = kite.graph_similarity_matrix(
            [kite, kite], method="ce"
        )
        # Diagonal should be the entropy of kite (non-trivial graph)
        diag = result["matrix"][0][0]
        assert diag > 0  # Kite has varied degrees → positive entropy

    def test_non_negative(self, kite, paw, path_graph):
        result = kite.graph_similarity_matrix(
            [kite, paw, path_graph], method="ce"
        )
        for row in result["matrix"]:
            for val in row:
                if not math.isnan(val):
                    assert val >= 0


# ── KL divergence matrix ───────────────────────────────────

class TestKLMatrix:
    def test_diagonal_is_zero(self, kite, paw):
        result = kite.graph_similarity_matrix(
            [kite, paw], method="kl"
        )
        m = result["matrix"]
        for i in range(2):
            assert m[i][i] == 0.0

    def test_asymmetric(self, kite, paw, path_graph):
        result = kite.graph_similarity_matrix(
            [kite, paw, path_graph], method="kl"
        )
        assert result["symmetric"] is False

    def test_non_negative(self, kite, paw, path_graph):
        """KL divergence is always non-negative (Gibbs' inequality)."""
        result = kite.graph_similarity_matrix(
            [kite, paw, path_graph], method="kl"
        )
        for row in result["matrix"]:
            for val in row:
                if not math.isnan(val):
                    assert val >= 0


# ── Error handling ─────────────────────────────────────────

class TestSimilarityMatrixErrors:
    def test_invalid_method_raises(self, triangle, path_graph):
        with pytest.raises(ValueError, match="unknown method"):
            triangle.graph_similarity_matrix(
                [triangle, path_graph], method="invalid"
            )


# ── Integration with graph_classification ──────────────────

class TestIntegrationWithClassification:
    def test_matrix_then_classify(self, kite, paw, path_graph, single_edge):
        """Matrix and classification should give consistent best_match."""
        refs = [paw, path_graph, single_edge]
        # Classify kite against refs
        cls = kite.graph_classification(refs, method="jsd")
        assert cls is not None
        # Matrix of all 5 graphs (kite first, then refs)
        mat = kite.graph_similarity_matrix(
            [kite] + refs, method="jsd"
        )
        # Matrix row 0 = kite vs all
        for ref_idx in range(len(refs)):
            expected = cls["rankings"][ref_idx]["score"]
            actual = mat["matrix"][0][ref_idx + 1]
            if math.isnan(actual):
                assert expected is None
            else:
                assert actual == pytest.approx(expected, abs=1e-6)


# ── Two-graph edge case ────────────────────────────────────

class TestTwoGraphs:
    def test_pair_jgd_matches_direct(self, triangle, path_graph):
        """2-graph JSD matrix should match direct entropy_distance call."""
        direct = triangle.entropy_distance(path_graph)
        result = triangle.graph_similarity_matrix(
            [triangle, path_graph], method="jsd"
        )
        assert result["matrix"][0][1] == pytest.approx(direct, abs=1e-6)
        assert result["matrix"][1][0] == pytest.approx(direct, abs=1e-6)

    def test_pair_kl_matches_direct(self, triangle, path_graph):
        direct = triangle.kl_divergence_graph(path_graph)
        result = triangle.graph_similarity_matrix(
            [triangle, path_graph], method="kl"
        )
        assert result["matrix"][0][1] == pytest.approx(direct, abs=1e-6)
