"""Tests for entropy_dashboard() — Cycle 325.

Unified one-call entropy overview aggregating all entropy signals.
"""
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def empty_graph():
    return MemoryGraph()


@pytest.fixture
def triangle():
    mg = MemoryGraph()
    a = mg.add("A", kind="concept")
    b = mg.add("B", kind="concept")
    c = mg.add("C", kind="concept")
    mg.link(a.id, b.id, "relates", weight=0.9)
    mg.link(b.id, c.id, "relates", weight=0.8)
    mg.link(a.id, c.id, "relates", weight=0.7)
    return mg


@pytest.fixture
def rich_graph():
    import random
    random.seed(42)
    mg = MemoryGraph()
    nodes = [mg.add(f"N{i}").id for i in range(10)]
    for i in range(9):
        mg.link(nodes[i], nodes[i + 1], "next", weight=0.8)
    for _ in range(15):
        s, t = random.sample(nodes, 2)
        mg.link(s, t, "relates", weight=random.uniform(0.3, 0.9))
    return mg


class TestStructure:
    def test_returns_dict(self, triangle):
        d = triangle.entropy_dashboard()
        assert isinstance(d, dict)

    def test_returns_none_for_empty(self, empty_graph):
        assert empty_graph.entropy_dashboard() is None

    def test_has_required_sections(self, triangle):
        d = triangle.entropy_dashboard()
        for section in ("stats", "degree_entropy", "spectral_entropy",
                         "fingerprint", "health", "top_contributors", "density"):
            assert section in d, f"Missing section: {section}"


class TestStats:
    def test_stats_has_node_edge_count(self, triangle):
        d = triangle.entropy_dashboard()
        assert d["stats"]["nodes"] == 3
        assert d["stats"]["edges"] == 3


class TestDegreeEntropy:
    def test_populated_for_graph_with_edges(self, triangle):
        d = triangle.entropy_dashboard()
        assert d["degree_entropy"] is not None
        assert "mean" in d["degree_entropy"]
        assert "std" in d["degree_entropy"]

    def test_none_for_no_edges(self):
        mg = MemoryGraph()
        mg.add("Lonely")
        d = mg.entropy_dashboard()
        assert d["degree_entropy"] is None


class TestSpectralEntropy:
    def test_has_von_neumann(self, triangle):
        d = triangle.entropy_dashboard()
        assert d["spectral_entropy"] is not None
        assert d["spectral_entropy"]["von_neumann_normalized"] is not None

    def test_none_for_no_edges(self):
        mg = MemoryGraph()
        mg.add("Lonely")
        d = mg.entropy_dashboard()
        assert d["spectral_entropy"] is None


class TestFingerprint:
    def test_has_vector(self, triangle):
        d = triangle.entropy_dashboard()
        assert d["fingerprint"] is not None
        assert "vector" in d["fingerprint"]
        assert d["fingerprint"]["dimensions"] > 0

    def test_vector_is_list_of_floats(self, triangle):
        d = triangle.entropy_dashboard()
        vec = d["fingerprint"]["vector"]
        assert isinstance(vec, list)
        for v in vec:
            assert isinstance(v, (int, float))


class TestHealth:
    def test_has_score_and_grade(self, triangle):
        d = triangle.entropy_dashboard()
        assert d["health"] is not None
        assert "score" in d["health"]
        assert "grade" in d["health"]
        assert 0 <= d["health"]["score"] <= 100


class TestTopContributors:
    def test_is_list(self, rich_graph):
        d = rich_graph.entropy_dashboard()
        assert isinstance(d["top_contributors"], list)

    def test_respects_top_n(self, rich_graph):
        d = rich_graph.entropy_dashboard(top_n=3)
        assert len(d["top_contributors"]) <= 3

    def test_default_top_5(self, rich_graph):
        d = rich_graph.entropy_dashboard()
        assert len(d["top_contributors"]) <= 5


class TestDensity:
    def test_populated(self, triangle):
        d = triangle.entropy_dashboard()
        assert d["density"] is not None
        assert isinstance(d["density"], dict)


class TestConsistency:
    def test_idempotent(self, rich_graph):
        d1 = rich_graph.entropy_dashboard()
        d2 = rich_graph.entropy_dashboard()
        assert d1["health"]["score"] == d2["health"]["score"]
        assert d1["fingerprint"]["vector"] == d2["fingerprint"]["vector"]

    def test_rich_graph_all_sections_populated(self, rich_graph):
        d = rich_graph.entropy_dashboard()
        for section in ("degree_entropy", "spectral_entropy",
                         "fingerprint", "health"):
            assert d[section] is not None, f"{section} should be populated"
