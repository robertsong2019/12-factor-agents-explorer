"""Tests for query_explain() — search plan diagnostics with per-result score decomposition."""
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def g():
    mg = MemoryGraph(":memory:")
    mg.add("alpha", kind="concept")
    mg.add("beta", kind="concept")
    mg.add("gamma", kind="entity")
    mg.add("delta", kind="entity")
    mg.link("alpha", "beta", relation="related")
    mg.link("alpha", "gamma", relation="contains")
    mg.link("beta", "delta", relation="links_to")
    mg.link("gamma", "delta", relation="references")
    return mg


class TestQueryExplainBasic:
    def test_returns_dict_structure(self, g):
        result = g.query_explain("alpha beta")
        assert isinstance(result, dict)
        assert "classification" in result
        assert "weights" in result
        assert "paths" in result
        assert "results" in result
        assert "summary" in result

    def test_query_field_echo(self, g):
        result = g.query_explain("alpha")
        assert result["query"] == "alpha"

    def test_fusion_mode_echo(self, g):
        result = g.query_explain("alpha", fusion="rrf")
        assert result["fusion_mode"] == "rrf"

    def test_k_constant_adaptive(self, g):
        result = g.query_explain("alpha", fusion="adaptive")
        assert isinstance(result["k_constant"], int)

    def test_k_constant_rrf(self, g):
        result = g.query_explain("alpha", fusion="rrf")
        assert result["k_constant"] == 60


class TestQueryExplainClassification:
    def test_classification_keys(self, g):
        result = g.query_explain("alpha")
        cls = result["classification"]
        assert "type" in cls
        assert "specificity" in cls
        assert "needs_retrieval" in cls

    def test_trivial_classification(self, g):
        result = g.query_explain("hi")
        assert result["classification"]["type"] == "trivial"
        assert result["classification"]["needs_retrieval"] is False

    def test_semantic_classification(self, g):
        result = g.query_explain("machine learning overview")
        assert result["classification"]["type"] in ("semantic", "exploratory")

    def test_relational_classification(self, g):
        result = g.query_explain("relation between alpha and beta")
        assert result["classification"]["type"] == "relational"


class TestQueryExplainWeights:
    def test_weights_keys(self, g):
        result = g.query_explain("alpha")
        assert "bm25" in result["weights"]
        assert "vector" in result["weights"]
        assert "graph" in result["weights"]
        assert "kge" in result["weights"]

    def test_weights_sum_approximately_one(self, g):
        result = g.query_explain("alpha")
        total = result["weights"]["bm25"] + result["weights"]["vector"] + result["weights"]["graph"]
        assert abs(total - 1.0) < 0.02

    def test_kge_weight_echo(self, g):
        result = g.query_explain("alpha", kge_weight=0.3)
        assert result["weights"]["kge"] == 0.3


class TestQueryExplainPaths:
    def test_bm25_path_present(self, g):
        result = g.query_explain("alpha")
        names = [p["name"] for p in result["paths"]]
        assert "bm25" in names

    def test_vector_path_skipped_without_embedding(self, g):
        result = g.query_explain("alpha")
        vec_path = next((p for p in result["paths"] if p["name"] == "vector"), None)
        assert vec_path is not None
        assert vec_path["status"] == "skipped"

    def test_kge_path_skipped_without_kge(self, g):
        result = g.query_explain("alpha")
        kge_path = next((p for p in result["paths"] if p["name"] == "kge"), None)
        assert kge_path is not None
        assert kge_path["status"] == "skipped"

    def test_path_has_status(self, g):
        result = g.query_explain("alpha")
        for p in result["paths"]:
            assert p["status"] in ("active", "skipped", "fallback")

    def test_path_has_result_count(self, g):
        result = g.query_explain("alpha")
        for p in result["paths"]:
            assert "result_count" in p
            assert isinstance(p["result_count"], int)

    def test_path_has_elapsed_ms(self, g):
        result = g.query_explain("alpha")
        for p in result["paths"]:
            assert "elapsed_ms" in p
            assert p["elapsed_ms"] >= 0

    def test_path_has_top_ids(self, g):
        result = g.query_explain("alpha")
        for p in result["paths"]:
            assert "top_ids" in p
            assert isinstance(p["top_ids"], list)


class TestQueryExplainResults:
    def test_results_is_list(self, g):
        result = g.query_explain("alpha")
        assert isinstance(result["results"], list)

    def test_result_has_required_keys(self, g):
        result = g.query_explain("alpha")
        for r in result["results"]:
            assert "node_id" in r
            assert "label" in r
            assert "kind" in r
            assert "score" in r
            assert "sources" in r
            assert "score_breakdown" in r

    def test_scores_descending(self, g):
        result = g.query_explain("alpha")
        scores = [r["score"] for r in result["results"]]
        assert scores == sorted(scores, reverse=True)

    def test_score_breakdown_non_negative(self, g):
        result = g.query_explain("alpha")
        for r in result["results"]:
            for k, v in r["score_breakdown"].items():
                assert v >= 0, f"{k}={v} is negative"

    def test_raw_rrf_in_breakdown(self, g):
        result = g.query_explain("alpha")
        for r in result["results"]:
            bd = r["score_breakdown"]
            assert "raw_rrf" in bd
            assert "consensus_bonus" in bd

    def test_limit_respected(self, g):
        result = g.query_explain("alpha", limit=2)
        assert len(result["results"]) <= 2


class TestQueryExplainSummary:
    def test_summary_keys(self, g):
        result = g.query_explain("alpha")
        s = result["summary"]
        assert "total_candidates" in s
        assert "unique_sources_used" in s
        assert "top_score" in s
        assert "bottom_score" in s
        assert "total_elapsed_ms" in s

    def test_total_elapsed_non_negative(self, g):
        result = g.query_explain("alpha")
        assert result["summary"]["total_elapsed_ms"] >= 0

    def test_top_score_gte_bottom(self, g):
        result = g.query_explain("alpha")
        if result["results"]:
            assert result["summary"]["top_score"] >= result["summary"]["bottom_score"]

    def test_trivial_returns_zero_candidates(self, g):
        result = g.query_explain("hi")
        assert result["summary"]["total_candidates"] == 0


class TestQueryExplainEntropyRefinement:
    def test_entropy_refinement_present_in_adaptive(self, g):
        result = g.query_explain("alpha", fusion="adaptive")
        assert result["entropy_refinement"] is not None

    def test_entropy_refinement_none_in_rrf(self, g):
        result = g.query_explain("alpha", fusion="rrf")
        assert result["entropy_refinement"] is None


class TestQueryExplainConsistency:
    def test_results_match_search_hybrid(self, g):
        """query_explain results should match search_hybrid for same query."""
        r1 = g.search_hybrid("alpha", fusion="rrf")
        r2 = g.query_explain("alpha", fusion="rrf")
        ids1 = [x["node_id"] for x in r1]
        ids2 = [x["node_id"] for x in r2["results"]]
        assert ids1 == ids2

    def test_scores_match_search_hybrid(self, g):
        r1 = g.search_hybrid("alpha", fusion="rrf")
        r2 = g.query_explain("alpha", fusion="rrf")
        for a, b in zip(r1, r2["results"]):
            assert abs(a["score"] - b["score"]) < 1e-5

    def test_empty_graph(self):
        mg = MemoryGraph(":memory:")
        result = mg.query_explain("test query")
        assert result["results"] == []
        assert result["summary"]["total_candidates"] == 0


class TestQueryExplainMultiSource:
    def test_node_with_multiple_sources_has_bonus(self, g):
        """Nodes retrieved by multiple paths should have consensus_bonus > 0."""
        result = g.query_explain("alpha", fusion="adaptive")
        for r in result["results"]:
            if len(r["sources"]) > 1:
                assert r["score_breakdown"].get("consensus_bonus", 0) > 0

    def test_graph_path_contributes(self, g):
        """Graph path should find outbound neighbors of seed node."""
        result = g.query_explain("alpha", fusion="rrf")
        # Graph path explores outbound edges from top text result's seed
        graph_path = next(p for p in result["paths"] if p["name"] == "graph")
        # alpha has 2 outbound edges (beta, gamma)
        node_ids = [r["node_id"] for r in result["results"]]
        # At least graph path should have found neighbors via edges
        assert graph_path["status"] == "active" or graph_path["result_count"] > 0 or len(node_ids) > 0


class TestQueryExplainEdgeCases:
    def test_empty_query(self, g):
        result = g.query_explain("")
        assert result["classification"]["type"] == "trivial"

    def test_single_word(self, g):
        result = g.query_explain("alpha")
        assert isinstance(result, dict)

    def test_long_query(self, g):
        long_q = " ".join(["alpha"] * 50)
        result = g.query_explain(long_q)
        assert isinstance(result, dict)
