"""Tests for graph_contrast_report() — Cycle 387.

Structural and information-theoretic comparison of two MemoryGraphs.
"""
import pytest
from memory_graph import MemoryGraph


def _build_star(n=6):
    g = MemoryGraph()
    for i in range(n):
        g.add(f"n{i}", kind="concept")
    for i in range(1, n):
        nodes = list(g.conn.execute("SELECT id FROM nodes ORDER BY id").fetchall())
        # Use labels to find nodes
    # Build edges by label lookup
    for i in range(1, n):
        src = g.conn.execute("SELECT id FROM nodes WHERE label=?", (f"n0",)).fetchone()
        tgt = g.conn.execute("SELECT id FROM nodes WHERE label=?", (f"n{i}",)).fetchone()
        if src and tgt:
            g.link(str(src["id"]), str(tgt["id"]), "related")
    return g


def _build_path(n=6):
    g = MemoryGraph()
    for i in range(n):
        g.add(f"n{i}", kind="concept")
    for i in range(n - 1):
        src = g.conn.execute("SELECT id FROM nodes WHERE label=?", (f"n{i}",)).fetchone()
        tgt = g.conn.execute("SELECT id FROM nodes WHERE label=?", (f"n{i+1}",)).fetchone()
        if src and tgt:
            g.link(str(src["id"]), str(tgt["id"]), "related")
    return g


def _build_cycle(n=6):
    g = MemoryGraph()
    for i in range(n):
        g.add(f"n{i}", kind="concept")
    for i in range(n):
        src = g.conn.execute("SELECT id FROM nodes WHERE label=?", (f"n{i}",)).fetchone()
        tgt = g.conn.execute("SELECT id FROM nodes WHERE label=?", (f"n{(i+1)%n}",)).fetchone()
        if src and tgt:
            g.link(str(src["id"]), str(tgt["id"]), "related")
    return g


def _build_identical_pair(n=6, topology="star"):
    """Build two graphs with identical structure (different node IDs)."""
    builder = _build_star if topology == "star" else _build_path if topology == "path" else _build_cycle
    return builder(n), builder(n)


class TestGraphContrastReportBasic:
    """Basic structure tests."""

    def test_returns_dict(self):
        g1, g2 = _build_identical_pair()
        result = g1.graph_contrast_report(g2)
        assert isinstance(result, dict)

    def test_keys_present(self):
        g1, g2 = _build_identical_pair()
        result = g1.graph_contrast_report(g2)
        expected_keys = {
            "node_diff", "edge_diff", "degree_jsd",
            "entropy_contrast", "spectral_contrast",
            "topology", "verdict", "summary",
        }
        assert expected_keys.issubset(result.keys())


class TestGraphContrastReportDiffs:
    """Node and edge difference tests."""

    def test_node_diff_different_ids(self):
        """Two separate MemoryGraphs always have different node IDs."""
        g1, g2 = _build_identical_pair()
        result = g1.graph_contrast_report(g2)
        # Different UUIDs → no common nodes
        assert result["node_diff"]["common"] == 0
        assert result["node_diff"]["only_self"] > 0
        assert result["node_diff"]["only_other"] > 0

    def test_edge_diff_separate_graphs(self):
        g1, g2 = _build_identical_pair()
        result = g1.graph_contrast_report(g2)
        # Different node IDs → different edges
        assert result["edge_diff"]["common"] == 0

    def test_same_graph_self_comparison(self):
        """Comparing graph with itself."""
        g1 = _build_star()
        result = g1.graph_contrast_report(g1)
        assert result["node_diff"]["only_self"] == 0
        assert result["node_diff"]["only_other"] == 0
        assert result["node_diff"]["common"] == 6
        assert result["edge_diff"]["common"] == 5


class TestGraphContrastReportDegreeJSD:
    """Degree distribution JSD tests."""

    def test_identical_topology_same_degree(self):
        """Same topology → same degree distribution → JSD ≈ 0."""
        g1, g2 = _build_identical_pair(n=6)
        result = g1.graph_contrast_report(g2)
        # Star has degrees [5,1,1,1,1,1] for both → JSD = 0
        assert result["degree_jsd"] == pytest.approx(0.0, abs=1e-6)

    def test_different_topology_nonzero_jsd(self):
        """Star vs path → different degree distribution → JSD > 0."""
        g1 = _build_star(n=6)   # [5,1,1,1,1,1]
        g2 = _build_path(n=6)   # [1,2,2,2,2,1]
        result = g1.graph_contrast_report(g2)
        assert result["degree_jsd"] > 0.0

    def test_degree_jsd_bounded(self):
        """JSD should be bounded."""
        g1 = _build_star(n=6)
        g2 = _build_cycle(n=6)
        result = g1.graph_contrast_report(g2)
        assert 0.0 <= result["degree_jsd"] <= 0.7


class TestGraphContrastReportEntropy:
    """Entropy contrast tests."""

    def test_entropy_contrast_present(self):
        g1 = _build_star(n=6)
        g2 = _build_path(n=6)
        result = g1.graph_contrast_report(g2)
        assert isinstance(result["entropy_contrast"], dict)

    def test_entropy_contrast_structure(self):
        g1 = _build_star(n=6)
        g2 = _build_path(n=6)
        result = g1.graph_contrast_report(g2)
        for idx, info in result["entropy_contrast"].items():
            assert "self" in info
            assert "other" in info
            assert "delta" in info
            assert info["delta"] >= 0.0

    def test_entropy_delta_zero_self_comparison(self):
        """Same graph → delta = 0."""
        g1 = _build_star(n=6)
        result = g1.graph_contrast_report(g1)
        for idx, info in result["entropy_contrast"].items():
            assert info["delta"] == pytest.approx(0.0, abs=1e-6)

    def test_custom_indices(self):
        g1 = _build_star(n=6)
        g2 = _build_path(n=6)
        result = g1.graph_contrast_report(g2, indices=["sombor", "randic"])
        assert set(result["entropy_contrast"].keys()) <= {"sombor", "randic"}


class TestGraphContrastReportSpectral:
    """Spectral contrast tests."""

    def test_spectral_keys(self):
        g1 = _build_star(n=6)
        g2 = _build_path(n=6)
        result = g1.graph_contrast_report(g2)
        assert "self_vn" in result["spectral_contrast"]
        assert "other_vn" in result["spectral_contrast"]
        assert "delta" in result["spectral_contrast"]

    def test_spectral_delta_non_negative(self):
        g1 = _build_star(n=6)
        g2 = _build_path(n=6)
        result = g1.graph_contrast_report(g2)
        assert result["spectral_contrast"]["delta"] >= 0.0


class TestGraphContrastReportTopology:
    """Topology metrics tests."""

    def test_topology_structure(self):
        g1 = _build_star(n=6)
        g2 = _build_path(n=6)
        result = g1.graph_contrast_report(g2)
        for key in ["self", "other"]:
            assert "nodes" in result["topology"][key]
            assert "edges" in result["topology"][key]
            assert "density" in result["topology"][key]
            assert "avg_degree" in result["topology"][key]

    def test_topology_same_node_edge_count(self):
        g1 = _build_star(n=6)
        g2 = _build_path(n=6)
        result = g1.graph_contrast_report(g2)
        assert result["topology"]["self"]["nodes"] == 6
        assert result["topology"]["other"]["nodes"] == 6
        assert result["topology"]["self"]["edges"] == 5
        assert result["topology"]["other"]["edges"] == 5


class TestGraphContrastReportVerdict:
    """Verdict tests."""

    def test_self_comparison_similar(self):
        """Comparing graph with itself → similar."""
        g1 = _build_star(n=6)
        result = g1.graph_contrast_report(g1)
        assert result["verdict"] == "similar"

    def test_different_topology_moderate_or_divergent(self):
        """Star vs path → at least moderately different."""
        g1 = _build_star(n=6)
        g2 = _build_path(n=6)
        result = g1.graph_contrast_report(g2)
        assert result["verdict"] in ("moderately_different", "divergent")

    def test_summary_is_string(self):
        g1 = _build_star()
        g2 = _build_path()
        result = g1.graph_contrast_report(g2)
        assert isinstance(result["summary"], str)
        assert "Graph contrast" in result["summary"]


class TestGraphContrastReportEdge:
    """Edge cases."""

    def test_self_comparison_empty(self):
        """Empty graph with itself."""
        g1 = MemoryGraph()
        result = g1.graph_contrast_report(g1)
        assert result["verdict"] == "similar"

    def test_one_empty(self):
        g1 = _build_star(n=6)
        g2 = MemoryGraph()
        result = g1.graph_contrast_report(g2)
        assert result["verdict"] == "divergent"

    def test_self_comparison_large(self):
        g1 = MemoryGraph()
        for i in range(20):
            g1.add(f"n{i}", kind="concept")
        nodes = list(g1.conn.execute("SELECT id, label FROM nodes ORDER BY label").fetchall())
        for i in range(19):
            g1.link(str(nodes[i]["id"]), str(nodes[i+1]["id"]), "related")
        result = g1.graph_contrast_report(g1)
        assert result["verdict"] == "similar"
