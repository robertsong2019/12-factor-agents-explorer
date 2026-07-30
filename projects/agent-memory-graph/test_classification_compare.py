"""Tests for classification_compare() — Cycle 328.

Multi-method consensus report: runs all 5 classification methods,
aggregates votes, and provides agreement analysis.
"""
import pytest
from memory_graph import MemoryGraph


# ── Helpers ───────────────────────────────────────────────────────

def _star(n):
    """Star graph: node 0 connected to nodes 1..n-1."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(1, n):
        g.link(nodes[0].id, nodes[i].id, "r")
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

def _complete(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return g

def _empty(n):
    g = MemoryGraph()
    for i in range(n):
        g.add(str(i))
    return g


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def query_graph():
    """Star-like graph — should match ref_star best."""
    return _star(5)

@pytest.fixture
def ref_star():
    return _star(6)

@pytest.fixture
def ref_path():
    return _path(5)

@pytest.fixture
def ref_cycle():
    return _cycle(5)

@pytest.fixture
def references(ref_star, ref_path, ref_cycle):
    return [ref_star, ref_path, ref_cycle]


# ── Basic structure tests ─────────────────────────────────────────

class TestClassificationCompareBasic:
    """Basic structural tests."""

    def test_returns_dict(self, query_graph, references):
        result = query_graph.classification_compare(references)
        assert isinstance(result, dict)

    def test_empty_references_returns_none(self, query_graph):
        assert query_graph.classification_compare([]) is None

    def test_required_keys(self, query_graph, references):
        result = query_graph.classification_compare(references)
        required = {
            "consensus_best", "agreement_score", "agreement_count",
            "disagreement_flag", "methods_run", "methods_failed",
            "per_method", "per_reference", "recommendation",
        }
        assert required.issubset(result.keys())


# ── Consensus logic tests ─────────────────────────────────────────

class TestClassificationCompareConsensus:
    """Consensus and agreement analysis."""

    def test_consensus_best_is_int(self, query_graph, references):
        result = query_graph.classification_compare(references)
        assert isinstance(result["consensus_best"], int)
        assert 0 <= result["consensus_best"] < len(references)

    def test_agreement_score_range(self, query_graph, references):
        result = query_graph.classification_compare(references)
        assert 0.0 < result["agreement_score"] <= 1.0

    def test_agreement_count_format(self, query_graph, references):
        result = query_graph.classification_compare(references)
        # Format: "N/M methods"
        parts = result["agreement_count"].split("/")
        assert len(parts) == 2
        n_votes = int(parts[0])
        total = int(parts[1])
        assert n_votes <= total
        assert total == len(result["methods_run"])

    def test_unanimous_agreement(self, query_graph, references):
        """When query closely matches ref_star, all methods should agree."""
        result = query_graph.classification_compare(references)
        assert result["agreement_score"] == 1.0
        assert result["consensus_best"] == 0  # ref_star
        assert not result["disagreement_flag"]

    def test_disagreement_flag_type(self, query_graph, references):
        result = query_graph.classification_compare(references)
        assert isinstance(result["disagreement_flag"], bool)

    def test_recommendation_is_string(self, query_graph, references):
        result = query_graph.classification_compare(references)
        assert isinstance(result["recommendation"], str)
        assert len(result["recommendation"]) > 0

    def test_recommendation_mentions_unanimous(self, query_graph, references):
        result = query_graph.classification_compare(references)
        assert "All" in result["recommendation"] or "all" in result["recommendation"]


# ── Per-method tests ──────────────────────────────────────────────

class TestClassificationComparePerMethod:
    """Per-method results."""

    def test_methods_run_populated(self, query_graph, references):
        result = query_graph.classification_compare(references)
        assert len(result["methods_run"]) > 0
        valid = {
            "graph_classification", "spectral_classification",
            "hybrid_classification", "rrf_classification",
            "bayesian_classification",
        }
        for m in result["methods_run"]:
            assert m in valid

    def test_methods_failed_is_list(self, query_graph, references):
        result = query_graph.classification_compare(references)
        assert isinstance(result["methods_failed"], list)

    def test_per_method_has_results(self, query_graph, references):
        result = query_graph.classification_compare(references)
        assert len(result["per_method"]) > 0
        for name, info in result["per_method"].items():
            assert "best_match" in info
            assert "best_score" in info
            assert "margin" in info
            assert "confidence" in info

    def test_per_method_best_match_valid(self, query_graph, references):
        result = query_graph.classification_compare(references)
        for name, info in result["per_method"].items():
            bm = info["best_match"]
            assert isinstance(bm, int)
            assert 0 <= bm < len(references)

    def test_at_least_three_methods_run(self, query_graph, references):
        """With well-formed graphs, most methods should succeed."""
        result = query_graph.classification_compare(references)
        assert len(result["methods_run"]) >= 3


# ── Per-reference tests ───────────────────────────────────────────

class TestClassificationComparePerReference:
    """Per-reference summary."""

    def test_per_reference_keys_match_input(self, query_graph, references):
        result = query_graph.classification_compare(references)
        for i in range(len(references)):
            assert i in result["per_reference"]

    def test_per_reference_has_required_fields(self, query_graph, references):
        result = query_graph.classification_compare(references)
        for idx, info in result["per_reference"].items():
            assert "votes" in info
            assert "vote_fraction" in info
            assert "methods_voted" in info

    def test_votes_sum_to_methods_run(self, query_graph, references):
        result = query_graph.classification_compare(references)
        total_votes = sum(
            r["votes"] for r in result["per_reference"].values()
        )
        assert total_votes == len(result["methods_run"])

    def test_consensus_has_most_votes(self, query_graph, references):
        result = query_graph.classification_compare(references)
        consensus = result["consensus_best"]
        max_votes = max(
            r["votes"] for r in result["per_reference"].values()
        )
        assert result["per_reference"][consensus]["votes"] == max_votes

    def test_methods_voted_lists_valid(self, query_graph, references):
        result = query_graph.classification_compare(references)
        all_methods = set(result["methods_run"])
        for idx, info in result["per_reference"].items():
            for m in info["methods_voted"]:
                assert m in all_methods

    def test_vote_fraction_range(self, query_graph, references):
        result = query_graph.classification_compare(references)
        for idx, info in result["per_reference"].items():
            assert 0.0 <= info["vote_fraction"] <= 1.0

    def test_non_best_refs_have_zero_or_fewer_votes(self, query_graph, references):
        result = query_graph.classification_compare(references)
        consensus = result["consensus_best"]
        consensus_votes = result["per_reference"][consensus]["votes"]
        for idx, info in result["per_reference"].items():
            if idx != consensus:
                assert info["votes"] <= consensus_votes


# ── Agreement/disagreement scenarios ──────────────────────────────

class TestClassificationCompareScenarios:
    """Scenario-based tests."""

    def test_clear_best_match_all_agree(self, query_graph, ref_star):
        """Query is a star; only ref is a star → unanimous."""
        result = query_graph.classification_compare([ref_star])
        assert result is not None
        assert result["consensus_best"] == 0
        assert result["agreement_score"] == 1.0

    def test_two_references_consensus(self, query_graph, ref_star, ref_path):
        """Two refs, star should win."""
        result = query_graph.classification_compare([ref_star, ref_path])
        assert result["consensus_best"] == 0  # star
        assert result["agreement_score"] == 1.0

    def test_self_comparison(self, ref_star):
        """Compare ref_star to itself → best match index 0."""
        result = ref_star.classification_compare([ref_star])
        assert result["consensus_best"] == 0

    def test_three_references_all_agree_on_star(
        self, query_graph, ref_star, ref_path, ref_cycle
    ):
        """Star query vs star/path/cycle → all pick star."""
        result = query_graph.classification_compare(
            [ref_star, ref_path, ref_cycle])
        assert result["consensus_best"] == 0
        assert result["agreement_score"] == 1.0
        assert not result["disagreement_flag"]


# ── Edge cases ────────────────────────────────────────────────────

class TestClassificationCompareEdgeCases:
    """Edge cases and robustness."""

    def test_single_reference(self, query_graph, ref_star):
        result = query_graph.classification_compare([ref_star])
        assert result is not None
        assert result["consensus_best"] == 0
        assert result["agreement_score"] == 1.0

    def test_single_node_graphs(self):
        """Compare single-node graphs — should not crash."""
        g1 = MemoryGraph()
        g1.add("x")
        g2 = MemoryGraph()
        g2.add("y")
        result = g1.classification_compare([g2])
        if result is not None:
            assert isinstance(result, dict)

    def test_identical_graphs(self):
        """Identical path graphs → all methods should agree."""
        g1 = _path(5)
        g2 = _path(5)
        result = g1.classification_compare([g2])
        assert result is not None
        assert result["consensus_best"] == 0

    def test_degree_index_parameter(self, query_graph, references):
        """Pass different degree_index."""
        result = query_graph.classification_compare(
            references, degree_index="randic")
        assert result is not None
        assert isinstance(result["consensus_best"], int)

    def test_include_quarantined_parameter(self, query_graph, references):
        """Pass include_quarantined flag."""
        result = query_graph.classification_compare(
            references, include_quarantined=True)
        assert result is not None

    def test_large_reference_set(self, query_graph):
        """Many references — should not crash."""
        refs = [_star(4 + i % 3) for i in range(10)]
        result = query_graph.classification_compare(refs)
        assert result is not None
        assert 0 <= result["consensus_best"] < 10

    def test_empty_query_graph_vs_references(self, references):
        """Empty query graph should handle gracefully."""
        empty = MemoryGraph()
        result = empty.classification_compare(references)
        # May return None or a dict
        if result is not None:
            assert isinstance(result, dict)

    def test_path_vs_cycle_vs_complete(self):
        """Path query vs [cycle, complete, path] → should pick path."""
        q = _path(6)
        refs = [_cycle(6), _complete(6), _path(6)]
        result = q.classification_compare(refs)
        assert result is not None
        # Path should be best match (index 2)
        assert result["consensus_best"] == 2


# ── Determinism tests ─────────────────────────────────────────────

class TestClassificationCompareDeterminism:
    """Results should be deterministic."""

    def test_same_input_same_output(self, query_graph, references):
        r1 = query_graph.classification_compare(references)
        r2 = query_graph.classification_compare(references)
        assert r1["consensus_best"] == r2["consensus_best"]
        assert r1["agreement_score"] == r2["agreement_score"]

    def test_methods_run_stable_order(self, query_graph, references):
        """methods_run should be in the same deterministic order across calls."""
        r1 = query_graph.classification_compare(references)
        r2 = query_graph.classification_compare(references)
        assert r1["methods_run"] == r2["methods_run"]

    def test_per_method_consistent_best_match(self, query_graph, references):
        """Each method should return same best_match across calls."""
        r1 = query_graph.classification_compare(references)
        r2 = query_graph.classification_compare(references)
        for m in r1["per_method"]:
            assert r1["per_method"][m]["best_match"] == r2["per_method"][m]["best_match"]


# ── Vote counting tests ───────────────────────────────────────────

class TestClassificationCompareVoteCounting:
    """Vote counting logic."""

    def test_all_methods_vote_for_same_ref(self, query_graph, references):
        """When star query matches ref_star unanimously."""
        result = query_graph.classification_compare(references)
        consensus = result["consensus_best"]
        # Every method voted for consensus
        assert result["per_reference"][consensus]["vote_fraction"] == 1.0

    def test_methods_voted_complete(self, query_graph, references):
        """All methods that ran should appear in vote lists."""
        result = query_graph.classification_compare(references)
        all_voted = []
        for info in result["per_reference"].values():
            all_voted.extend(info["methods_voted"])
        assert sorted(all_voted) == sorted(result["methods_run"])

    def test_no_double_counting(self, query_graph, references):
        """Each method votes exactly once."""
        result = query_graph.classification_compare(references)
        all_voted = []
        for info in result["per_reference"].values():
            all_voted.extend(info["methods_voted"])
        # No duplicates
        assert len(all_voted) == len(set(all_voted))
        assert len(all_voted) == len(result["methods_run"])
