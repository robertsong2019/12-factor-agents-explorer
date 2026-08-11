"""Tests for retrieval_quality_compare() — Cycle 415.

Multi-set retrieval quality comparison: given 2+ retrieval result
sets, compute audit for each and produce head-to-head comparison.
"""
import math
import time
import pytest
from memory_graph import MemoryGraph


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

def _build_rich_graph():
    """Graph with 3 communities for diversity testing."""
    mg = MemoryGraph()
    ids: dict[str, str] = {}

    # Community 1
    ids["alpha"] = mg.add("A1", "concept", {"importance": 0.9}).id
    ids["beta"] = mg.add("A2", "concept", {"importance": 0.7}).id
    ids["gamma"] = mg.add("A3", "concept", {"importance": 0.5}).id
    mg.link(ids["alpha"], ids["beta"], "related", 2.0)
    mg.link(ids["beta"], ids["gamma"], "related", 1.5)

    # Community 2
    ids["delta"] = mg.add("B1", "concept", {"importance": 0.9}).id
    ids["epsilon"] = mg.add("B2", "concept", {"importance": 0.7}).id
    ids["zeta"] = mg.add("B3", "concept", {"importance": 0.5}).id
    mg.link(ids["delta"], ids["epsilon"], "related", 2.0)
    mg.link(ids["epsilon"], ids["zeta"], "related", 1.5)

    # Community 3
    ids["eta"] = mg.add("C1", "concept", {"importance": 0.9}).id
    ids["theta"] = mg.add("C2", "concept", {"importance": 0.7}).id
    mg.link(ids["eta"], ids["theta"], "related", 2.0)

    # Cross-community bridge
    mg.link(ids["gamma"], ids["delta"], "bridge", 0.5)
    return mg, ids


@pytest.fixture
def basic_graph():
    mg, ids = _build_rich_graph()
    # Attach ids dict so tests can use label→id mapping
    mg._test_ids = ids
    return mg


@pytest.fixture
def basic_ids(basic_graph):
    return basic_graph._test_ids


@pytest.fixture
def large_graph():
    mg = MemoryGraph()
    for i in range(100):
        mg.add(f"node{i}", "concept", {"idx": i})
    for i in range(99):
        mg.link(f"n{i}", f"n{i+1}", "next", 1.0) if False else None
    # Use proper node IDs
    all_ids = [r["id"] for r in mg.conn.execute("SELECT id FROM nodes").fetchall()]
    for i in range(99):
        mg.link(all_ids[i], all_ids[i + 1], "next", 1.0)
    for i in range(0, 100, 7):
        mg.link(all_ids[i], all_ids[(i + 13) % 100], "skip", 0.5)
    mg._test_ids = {"all": all_ids}
    return mg


# ──────────────────────────────────────────────────────────────
# 1. Structure
# ──────────────────────────────────────────────────────────────

class TestStructure:

    def test_returns_dict(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        assert isinstance(result, dict)

    def test_required_top_keys(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        for key in ("per_set", "pairwise_overlap", "labels",
                     "unique_nodes", "common_nodes", "ranking",
                     "dimension_winners", "overall_winner",
                     "agreement", "summary", "recommendations",
                     "duration_seconds"):
            assert key in result, f"Missing key: {key}"

    def test_per_set_length_matches_input(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"]], [basic_ids["beta"]], [basic_ids["gamma"]]]
        )
        assert len(result["per_set"]) == 3

    def test_pairwise_overlap_is_matrix(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]],
             [basic_ids["eta"], basic_ids["theta"]]]
        )
        matrix = result["pairwise_overlap"]
        assert len(matrix) == 3
        for row in matrix:
            assert len(row) == 3

    def test_duration_positive(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"]], [basic_ids["delta"]]]
        )
        assert result["duration_seconds"] >= 0.0


# ──────────────────────────────────────────────────────────────
# 2. Validation & Errors
# ──────────────────────────────────────────────────────────────

class TestValidation:

    def test_single_set_returns_error(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"]]]
        )
        assert "error" in result

    def test_empty_list_returns_error(self, basic_graph):
        result = basic_graph.retrieval_quality_compare([])
        assert "error" in result

    def test_label_count_mismatch(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"]], [basic_ids["delta"]]],
            labels=["only_one"]
        )
        assert "error" in result


# ──────────────────────────────────────────────────────────────
# 3. Degenerate Cases
# ──────────────────────────────────────────────────────────────

class TestDegenerate:

    def test_all_empty_sets(self, basic_graph):
        """All sets empty — should still return structure."""
        result = basic_graph.retrieval_quality_compare([[], []])
        assert "per_set" in result
        assert result["agreement"]["intersection_size"] == 0

    def test_one_empty_one_full(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]], []]
        )
        assert result["ranking"][0]["set_index"] == 0
        assert result["per_set"][1]["overall_quality"] == 0.0

    def test_all_invalid_ids(self, basic_graph):
        result = basic_graph.retrieval_quality_compare(
            [["nonexist1"], ["nonexist2"]]
        )
        assert "per_set" in result


# ──────────────────────────────────────────────────────────────
# 4. Pairwise Overlap
# ──────────────────────────────────────────────────────────────

class TestPairwiseOverlap:

    def test_diagonal_is_one(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        matrix = result["pairwise_overlap"]
        for i in range(2):
            assert matrix[i][i] == 1.0

    def test_identical_sets_overlap_one(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["alpha"], basic_ids["beta"]]]
        )
        assert result["pairwise_overlap"][0][1] == 1.0

    def test_disjoint_sets_overlap_zero(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        assert result["pairwise_overlap"][0][1] == 0.0

    def test_partial_overlap(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"], basic_ids["gamma"]],
             [basic_ids["beta"], basic_ids["gamma"], basic_ids["delta"]]]
        )
        # Intersection: {beta, gamma} = 2, Union = {alpha, beta, gamma, delta} = 4
        expected = 2 / 4
        assert abs(result["pairwise_overlap"][0][1] - expected) < 0.01

    def test_matrix_symmetric(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"], basic_ids["gamma"]],
             [basic_ids["beta"], basic_ids["delta"], basic_ids["epsilon"]],
             [basic_ids["eta"], basic_ids["theta"]]]
        )
        matrix = result["pairwise_overlap"]
        for i in range(3):
            for j in range(3):
                assert matrix[i][j] == matrix[j][i]


# ──────────────────────────────────────────────────────────────
# 5. Unique & Common Nodes
# ──────────────────────────────────────────────────────────────

class TestUniqueCommon:

    def test_unique_nodes_disjoint(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        assert set(result["unique_nodes"][0]) == {basic_ids["alpha"], basic_ids["beta"]}
        assert set(result["unique_nodes"][1]) == {basic_ids["delta"], basic_ids["epsilon"]}

    def test_unique_nodes_identical(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["alpha"], basic_ids["beta"]]]
        )
        assert result["unique_nodes"][0] == []
        assert result["unique_nodes"][1] == []

    def test_unique_nodes_partial(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"], basic_ids["gamma"]],
             [basic_ids["beta"], basic_ids["gamma"], basic_ids["delta"]]]
        )
        assert set(result["unique_nodes"][0]) == {basic_ids["alpha"]}
        assert set(result["unique_nodes"][1]) == {basic_ids["delta"]}

    def test_common_nodes_identical(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["alpha"], basic_ids["beta"]]]
        )
        assert set(result["common_nodes"]) == {basic_ids["alpha"], basic_ids["beta"]}

    def test_common_nodes_disjoint(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        assert result["common_nodes"] == []

    def test_common_nodes_three_sets(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"], basic_ids["gamma"]],
             [basic_ids["beta"], basic_ids["gamma"], basic_ids["delta"]],
             [basic_ids["beta"], basic_ids["epsilon"]]]
        )
        assert set(result["common_nodes"]) == {basic_ids["beta"]}


# ──────────────────────────────────────────────────────────────
# 6. Ranking
# ──────────────────────────────────────────────────────────────

class TestRanking:

    def test_ranking_sorted_descending(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["alpha"], basic_ids["beta"], basic_ids["delta"], basic_ids["eta"]]]
        )
        qualities = [r["overall_quality"] for r in result["ranking"]]
        assert qualities == sorted(qualities, reverse=True)

    def test_ranking_first_is_best(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"]],
             [basic_ids["alpha"], basic_ids["beta"], basic_ids["delta"], basic_ids["eta"], basic_ids["theta"]]]
        )
        assert result["ranking"][0]["rank"] == 1
        winner_quality = result["ranking"][0]["overall_quality"]
        for r in result["ranking"][1:]:
            assert winner_quality >= r["overall_quality"]

    def test_ranking_has_labels(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"]], [basic_ids["delta"]]],
            labels=["bm25", "vector"]
        )
        labels_in_ranking = {r["label"] for r in result["ranking"]}
        assert labels_in_ranking == {"bm25", "vector"}

    def test_ranking_has_set_size(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]], [basic_ids["delta"]]]
        )
        assert result["ranking"][0]["set_size"] in (2, 1)


# ──────────────────────────────────────────────────────────────
# 7. Dimension Winners
# ──────────────────────────────────────────────────────────────

class TestDimensionWinners:

    def test_all_dimensions_present(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        dw = result["dimension_winners"]
        for dim in ("diversity_score", "interference_score",
                     "freshness_score", "coverage_score",
                     "overall_quality"):
            assert dim in dw
            assert "set_index" in dw[dim]
            assert "label" in dw[dim]
            assert "value" in dw[dim]

    def test_more_diverse_set_wins_diversity(self, basic_graph, basic_ids):
        """Set with cross-community nodes should win diversity."""
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"], basic_ids["gamma"]],          # one community
             [basic_ids["alpha"], basic_ids["delta"], basic_ids["eta"]]])            # three communities
        dw = result["dimension_winners"]
        assert dw["diversity_score"]["set_index"] == 1

    def test_larger_set_wins_coverage(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"]],
             [basic_ids["alpha"], basic_ids["beta"], basic_ids["delta"], basic_ids["eta"], basic_ids["theta"]]]
        )
        dw = result["dimension_winners"]
        assert dw["coverage_score"]["set_index"] == 1


# ──────────────────────────────────────────────────────────────
# 8. Overall Winner
# ──────────────────────────────────────────────────────────────

class TestOverallWinner:

    def test_winner_structure(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        ow = result["overall_winner"]
        assert "set_index" in ow
        assert "label" in ow
        assert "overall_quality" in ow

    def test_winner_matches_ranking_first(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"]],
             [basic_ids["alpha"], basic_ids["beta"], basic_ids["delta"], basic_ids["eta"], basic_ids["theta"]]]
        )
        assert (result["overall_winner"]["set_index"] ==
                result["ranking"][0]["set_index"])

    def test_winner_with_labels(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"]],
             [basic_ids["alpha"], basic_ids["beta"], basic_ids["delta"], basic_ids["eta"]]],
            labels=["small", "big"]
        )
        ow = result["overall_winner"]
        assert ow["label"] in ("small", "big")


# ──────────────────────────────────────────────────────────────
# 9. Agreement
# ──────────────────────────────────────────────────────────────

class TestAgreement:

    def test_agreement_structure(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        ag = result["agreement"]
        for key in ("mean_pairwise_overlap", "label",
                     "union_size", "intersection_size"):
            assert key in ag

    def test_disjoint_low_agreement(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        assert result["agreement"]["label"] in ("very_low", "low")
        assert result["agreement"]["mean_pairwise_overlap"] < 0.2

    def test_identical_high_agreement(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"], basic_ids["gamma"]],
             [basic_ids["alpha"], basic_ids["beta"], basic_ids["gamma"]]]
        )
        assert result["agreement"]["label"] == "very_high"
        assert result["agreement"]["mean_pairwise_overlap"] == 1.0

    def test_union_and_intersection(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"], basic_ids["gamma"]],
             [basic_ids["beta"], basic_ids["gamma"], basic_ids["delta"]]]
        )
        assert result["agreement"]["union_size"] == 4
        assert result["agreement"]["intersection_size"] == 2


# ──────────────────────────────────────────────────────────────
# 10. Summary & Recommendations
# ──────────────────────────────────────────────────────────────

class TestSummaryRecommendations:

    def test_summary_nonempty(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        assert len(result["summary"]) > 0

    def test_summary_contains_winner(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"]], [basic_ids["delta"], basic_ids["eta"]]],
            labels=["small", "diverse"]
        )
        assert "winner" in result["summary"].lower()

    def test_recommendations_nonempty(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        assert len(result["recommendations"]) >= 1

    def test_recommendation_for_low_overlap(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]],
             [basic_ids["eta"], basic_ids["theta"]]]
        )
        recs = result["recommendations"]
        assert any("overlap" in r.lower() or "ensemble" in r.lower()
                   for r in recs)

    def test_recommendation_for_high_overlap(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"], basic_ids["gamma"]],
             [basic_ids["alpha"], basic_ids["beta"], basic_ids["gamma"]]]
        )
        recs = result["recommendations"]
        assert any("overlap" in r.lower() or "converg" in r.lower()
                   for r in recs)


# ──────────────────────────────────────────────────────────────
# 11. Non-Mutating
# ──────────────────────────────────────────────────────────────

class TestNonMutating:

    def test_graph_unchanged(self, basic_graph, basic_ids):
        nodes_before = set(basic_graph.conn.execute(
            "SELECT id FROM nodes").fetchall())
        edges_before = set(basic_graph.conn.execute(
            "SELECT source, target FROM edges").fetchall())
        basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        nodes_after = set(basic_graph.conn.execute(
            "SELECT id FROM nodes").fetchall())
        edges_after = set(basic_graph.conn.execute(
            "SELECT source, target FROM edges").fetchall())
        assert nodes_before == nodes_after
        assert edges_before == edges_after

    def test_node_weights_unchanged(self, basic_graph, basic_ids):
        weights_before = dict(basic_graph.conn.execute(
            "SELECT id, weight FROM nodes").fetchall())
        basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        weights_after = dict(basic_graph.conn.execute(
            "SELECT id, weight FROM nodes").fetchall())
        assert weights_before == weights_after


# ──────────────────────────────────────────────────────────────
# 12. Determinism
# ──────────────────────────────────────────────────────────────

class TestDeterminism:

    def test_same_result_twice(self, basic_graph, basic_ids):
        r1 = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        r2 = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        assert (r1["pairwise_overlap"] == r2["pairwise_overlap"])
        assert (r1["overall_winner"]["set_index"] ==
                r2["overall_winner"]["set_index"])
        assert r1["ranking"] == r2["ranking"]

    def test_now_parameter_stable(self, basic_graph, basic_ids):
        fixed_now = time.time() + 3600  # 1 hour in the future
        r1 = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]],
            now=fixed_now
        )
        r2 = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]],
            now=fixed_now
        )
        assert (r1["per_set"][0]["freshness_score"] ==
                r2["per_set"][0]["freshness_score"])


# ──────────────────────────────────────────────────────────────
# 13. Integration & Edge Cases
# ──────────────────────────────────────────────────────────────

class TestIntegration:

    def test_works_after_modification(self, basic_graph, basic_ids):
        """Compare should work after graph is modified."""
        new_node = basic_graph.add("new", "concept", {"importance": 1.0})
        basic_graph.link(new_node.id, basic_ids["alpha"], "related", 1.0)
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], new_node.id],
             [basic_ids["beta"], basic_ids["delta"]]]
        )
        assert "per_set" in result

    def test_large_graph(self, large_graph):
        """Compare on 100-node graph."""
        all_ids = large_graph._test_ids["all"]
        result = large_graph.retrieval_quality_compare(
            [all_ids[0:5],
             all_ids[50:55],
             [all_ids[0], all_ids[25], all_ids[50], all_ids[75], all_ids[99]]]
        )
        assert len(result["per_set"]) == 3
        assert len(result["pairwise_overlap"]) == 3
        assert result["overall_winner"]["set_index"] >= 0

    def test_algorithm_parameter(self, basic_graph, basic_ids):
        """Should work with different community algorithms."""
        for algo in ("leiden", "greedy", "lp"):
            result = basic_graph.retrieval_quality_compare(
                [[basic_ids["alpha"], basic_ids["beta"]],
                 [basic_ids["delta"], basic_ids["epsilon"]]],
                algorithm=algo
            )
            assert "per_set" in result

    def test_three_sets(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]],
             [basic_ids["eta"], basic_ids["theta"]]]
        )
        assert len(result["per_set"]) == 3
        assert len(result["pairwise_overlap"]) == 3
        assert len(result["ranking"]) == 3

    def test_overlapping_sets(self, basic_graph, basic_ids):
        """Sets that share some nodes."""
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"], basic_ids["gamma"],
              basic_ids["delta"]],
             [basic_ids["beta"], basic_ids["gamma"], basic_ids["epsilon"],
              basic_ids["zeta"]],
             [basic_ids["gamma"], basic_ids["delta"], basic_ids["eta"],
              basic_ids["theta"]]]
        )
        assert result["agreement"]["intersection_size"] == 1  # gamma only
        assert basic_ids["gamma"] in result["common_nodes"]

    def test_custom_weights(self, basic_graph, basic_ids):
        """Custom quality weights should be passed through."""
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]],
            weights={"diversity": 0.5, "coverage": 0.5,
                      "interference": 0.0, "freshness": 0.0}
        )
        assert "per_set" in result
        for audit in result["per_set"]:
            assert audit["weights"]["diversity"] > 0.4


# ──────────────────────────────────────────────────────────────
# 14. Per-Set Audit Consistency
# ──────────────────────────────────────────────────────────────

class TestPerSetConsistency:

    def test_per_set_has_audit_keys(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        for audit in result["per_set"]:
            for key in ("overall_quality", "diversity_score",
                        "interference_score", "freshness_score",
                        "coverage_score"):
                assert key in audit

    def test_per_set_has_label(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"]], [basic_ids["delta"]]],
            labels=["bm25", "vector"]
        )
        assert result["per_set"][0]["_label"] == "bm25"
        assert result["per_set"][1]["_label"] == "vector"

    def test_per_set_matches_direct_audit(self, basic_graph, basic_ids):
        """per_set audit should match calling audit() directly."""
        direct = basic_graph.retrieval_quality_audit(
            [basic_ids["alpha"], basic_ids["beta"]])
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        assert (abs(result["per_set"][0]["overall_quality"] -
                    direct["overall_quality"]) < 0.001)

    def test_dimension_winners_match_per_set(self, basic_graph, basic_ids):
        result = basic_graph.retrieval_quality_compare(
            [[basic_ids["alpha"], basic_ids["beta"]],
             [basic_ids["delta"], basic_ids["epsilon"]]]
        )
        dw = result["dimension_winners"]
        idx = dw["overall_quality"]["set_index"]
        assert (result["per_set"][idx]["overall_quality"] ==
                dw["overall_quality"]["value"])
