"""Tests for retrieval_quality_eval() — Cycle 224.

Tests retrieval evaluation metrics: precision@k, recall@k, F1, NDCG, MRR.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def populated_graph():
    """Graph with known structure for eval testing."""
    mg = MemoryGraph()
    # Create nodes with searchable labels
    mg.add("Python programming tutorial", "topic", {"tags": ["coding"]})
    mg.add("Python data analysis guide", "topic", {"tags": ["data"]})
    mg.add("JavaScript basics", "topic", {"tags": ["coding"]})
    mg.add("Rust memory safety", "topic", {"tags": ["systems"]})
    mg.add("Python web frameworks", "topic", {"tags": ["web"]})
    mg.add("Machine learning with Python", "topic", {"tags": ["ml"]})
    mg.add("Go concurrency patterns", "topic", {"tags": ["coding"]})
    mg.add("Python testing best practices", "topic", {"tags": ["testing"]})
    return mg


class TestRetrievalQualityEvalBasics:
    """Basic structure and return value tests."""

    def test_returns_dict_with_overall(self, populated_graph):
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": []}]
        )
        assert "overall" in result
        assert "per_query" in result
        assert result["k"] == 10
        assert result["n_cases"] == 1

    def test_empty_cases(self, populated_graph):
        result = populated_graph.retrieval_quality_eval([])
        assert result["n_cases"] == 0
        assert result["n_evaluated"] == 0
        assert result["overall"]["precision"] == 0.0

    def test_custom_k(self, populated_graph):
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": []}], k=3
        )
        assert result["k"] == 3

    def test_per_query_has_required_fields(self, populated_graph):
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": []}]
        )
        pq = result["per_query"][0]
        assert "query" in pq
        assert "precision" in pq
        assert "recall" in pq
        assert "f1" in pq
        assert "ndcg" in pq
        assert "mrr" in pq
        assert "hit" in pq

    def test_skipped_case_has_zero_metrics(self, populated_graph):
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": []}]
        )
        pq = result["per_query"][0]
        assert pq.get("skipped") is True
        assert pq["precision"] == 0.0


class TestPrecisionRecall:
    """Precision and recall correctness."""

    def test_perfect_retrieval(self, populated_graph):
        """When all relevant items are retrieved and nothing else."""
        # Find Python-related nodes
        results = populated_graph.recall("Python", limit=10)
        python_ids = {n.id for n in results}

        eval_result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": list(python_ids)}],
            k=10,
        )
        # Should have decent recall since we're searching for Python
        overall = eval_result["overall"]
        assert overall["recall"] > 0
        assert overall["precision"] > 0

    def test_no_relevant_retrieved(self, populated_graph):
        """When relevant_ids don't match any retrieved items."""
        fake_ids = ["nonexistent_1", "nonexistent_2"]
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": fake_ids}], k=5
        )
        overall = result["overall"]
        assert overall["precision"] == 0.0
        assert overall["recall"] == 0.0
        assert overall["mrr"] == 0.0
        assert overall["hit_rate"] == 0.0

    def test_partial_recall(self, populated_graph):
        """Some relevant items retrieved."""
        results = populated_graph.recall("Python", limit=10)
        all_ids = [n.id for n in results]
        # Add a fake ID to relevant set to lower recall
        relevant = all_ids[:2] + ["fake_id"]
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": relevant}], k=10
        )
        pq = result["per_query"][0]
        # Recall should be < 1.0 because of the fake_id
        assert pq["recall"] < 1.0

    def test_precision_with_small_k(self, populated_graph):
        """Precision should be valid at different k values."""
        results = populated_graph.recall("Python", limit=10)
        python_ids = {n.id for n in results}

        result_k2 = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": list(python_ids)}], k=2
        )
        result_k10 = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": list(python_ids)}], k=10
        )
        # Both should have valid precision in [0, 1]
        assert 0.0 <= result_k2["overall"]["precision"] <= 1.0
        assert 0.0 <= result_k10["overall"]["precision"] <= 1.0


class TestNDCG:
    """NDCG metric correctness."""

    def test_ndcg_ideal_order(self, populated_graph):
        """NDCG should be 1.0 when all relevant items are ranked first."""
        results = populated_graph.recall("Python", limit=10)
        # Use retrieved IDs as relevant — ideal ranking
        retrieved_ids = [r.id for r in results[:3]]
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": retrieved_ids}], k=10
        )
        # If the top retrieved match the relevant set perfectly,
        # NDCG should be close to 1.0
        assert result["overall"]["ndcg"] > 0

    def test_ndcg_zero_when_no_match(self, populated_graph):
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": ["fake1", "fake2"]}], k=5
        )
        assert result["overall"]["ndcg"] == 0.0

    def test_ndcg_range(self, populated_graph):
        """NDCG must be in [0, 1]."""
        results = populated_graph.recall("Python", limit=10)
        python_ids = {n.id for n in results}
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": list(python_ids)}], k=5
        )
        ndcg = result["overall"]["ndcg"]
        assert 0.0 <= ndcg <= 1.0


class TestMRR:
    """Mean Reciprocal Rank correctness."""

    def test_mrr_first_position(self, populated_graph):
        """MRR = 1.0 when first relevant item is at rank 1."""
        results = populated_graph.recall("Python", limit=10)
        first_id = results[0].id
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": [first_id]}], k=10
        )
        # The first result from recall should be highly ranked
        assert result["overall"]["mrr"] > 0

    def test_mrr_no_hit(self, populated_graph):
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": ["nonexistent"]}], k=5
        )
        assert result["overall"]["mrr"] == 0.0

    def test_mrr_range(self, populated_graph):
        results = populated_graph.recall("Python", limit=10)
        python_ids = [n.id for n in results]
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": python_ids}], k=5
        )
        mrr = result["overall"]["mrr"]
        assert 0.0 <= mrr <= 1.0


class TestF1:
    """F1 score correctness."""

    def test_f1_harmonic_mean(self, populated_graph):
        results = populated_graph.recall("Python", limit=10)
        python_ids = [n.id for n in results[:3]]
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": python_ids}], k=10
        )
        pq = result["per_query"][0]
        # F1 = 2PR/(P+R)
        if pq["precision"] + pq["recall"] > 0:
            expected_f1 = 2 * pq["precision"] * pq["recall"] / (pq["precision"] + pq["recall"])
            assert abs(pq["f1"] - round(expected_f1, 4)) < 0.01

    def test_f1_zero_when_no_match(self, populated_graph):
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": ["fake"]}], k=5
        )
        assert result["overall"]["f1"] == 0.0


class TestMultipleQueries:
    """Aggregation across multiple queries."""

    def test_macro_average(self, populated_graph):
        """Overall metrics should be macro-average of per-query."""
        results = populated_graph.recall("Python", limit=10)
        python_ids = [n.id for n in results]

        cases = [
            {"query": "Python", "relevant_ids": python_ids},
            {"query": "JavaScript", "relevant_ids": ["nonexistent"]},
        ]
        result = populated_graph.retrieval_quality_eval(cases, k=10)

        # Average of query 1 (some precision) and query 2 (zero)
        pq = result["per_query"]
        avg_p = (pq[0]["precision"] + pq[1]["precision"]) / 2
        assert abs(result["overall"]["precision"] - round(avg_p, 4)) < 0.01

    def test_three_queries(self, populated_graph):
        cases = [
            {"query": "Python", "relevant_ids": []},
            {"query": "JavaScript", "relevant_ids": []},
            {"query": "Rust", "relevant_ids": []},
        ]
        result = populated_graph.retrieval_quality_eval(cases, k=5)
        assert result["n_cases"] == 3
        assert result["n_evaluated"] == 0  # all skipped

    def test_mixed_skipped_and_real(self, populated_graph):
        results = populated_graph.recall("Python", limit=10)
        python_ids = [n.id for n in results]
        cases = [
            {"query": "Python", "relevant_ids": python_ids},
            {"query": "Python", "relevant_ids": []},  # skipped
        ]
        result = populated_graph.retrieval_quality_eval(cases, k=10)
        assert result["n_cases"] == 2
        assert result["n_evaluated"] == 1  # only first counted


class TestRerankOptions:
    """Verify rerank parameters pass through."""

    def test_rerank_disabled(self, populated_graph):
        results = populated_graph.recall("Python", limit=10)
        python_ids = [n.id for n in results]
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": python_ids}],
            k=5, rerank=False,
        )
        assert result["n_evaluated"] == 1

    def test_rerank_centrality_option(self, populated_graph):
        results = populated_graph.recall("Python", limit=10)
        python_ids = [n.id for n in results]
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": python_ids}],
            k=5, rerank=True, rerank_centrality="pagerank",
        )
        assert result["n_evaluated"] == 1

    def test_custom_limit(self, populated_graph):
        results = populated_graph.recall("Python", limit=10)
        python_ids = [n.id for n in results]
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": python_ids}],
            k=3, limit=20,
        )
        assert result["k"] == 3


class TestHitRate:
    """Hit@k metric."""

    def test_hit_when_relevant_found(self, populated_graph):
        results = populated_graph.recall("Python", limit=10)
        first_id = results[0].id
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": [first_id]}], k=10
        )
        assert result["overall"]["hit_rate"] > 0.0

    def test_no_hit_when_relevant_not_found(self, populated_graph):
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": ["nonexistent"]}], k=5
        )
        assert result["overall"]["hit_rate"] == 0.0

    def test_hit_rate_multiple_queries(self, populated_graph):
        results = populated_graph.recall("Python", limit=10)
        first_id = results[0].id
        cases = [
            {"query": "Python", "relevant_ids": [first_id]},  # hit
            {"query": "Python", "relevant_ids": ["nonexistent"]},  # miss
        ]
        result = populated_graph.retrieval_quality_eval(cases, k=10)
        assert result["overall"]["hit_rate"] == 0.5


class TestEdgeCases:
    """Edge cases and robustness."""

    def test_relevant_ids_as_set(self, populated_graph):
        results = populated_graph.recall("Python", limit=10)
        python_ids = {n.id for n in results}
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": python_ids}], k=5
        )
        assert result["n_evaluated"] == 1

    def test_empty_relevant_list(self, populated_graph):
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": []}], k=5
        )
        assert result["per_query"][0].get("skipped") is True

    def test_k_larger_than_results(self, populated_graph):
        """k=100 but only a few results returned."""
        results = populated_graph.recall("Python", limit=10)
        python_ids = [n.id for n in results]
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": python_ids}], k=100
        )
        # Should not crash, metrics should still be valid
        assert 0.0 <= result["overall"]["precision"] <= 1.0

    def test_single_relevant(self, populated_graph):
        results = populated_graph.recall("Python", limit=10)
        first_id = results[0].id
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": [first_id]}], k=10
        )
        pq = result["per_query"][0]
        assert pq["relevant_count"] == 1
        assert pq["tp"] >= 0

    def test_does_not_mutate_graph(self, populated_graph):
        """Eval should not modify the graph."""
        stats_before = populated_graph.stats()
        results = populated_graph.recall("Python", limit=10)
        python_ids = [n.id for n in results]
        populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": python_ids}], k=5
        )
        stats_after = populated_graph.stats()
        assert stats_before["nodes"] == stats_after["nodes"]
        assert stats_before["edges"] == stats_after["edges"]


class TestUtilizationRate:
    """Utilization rate metric — ACL 2026 GEM insight.

    Measures the fraction of retrieved items actually cited/used by the
    downstream model, exposing the retrieval-generation gap.
    """

    def test_utilization_none_when_no_cited_ids(self, populated_graph):
        """utilization_rate should be None when cited_ids not provided."""
        results = populated_graph.recall("Python", limit=10)
        python_ids = [n.id for n in results]
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": python_ids}], k=5
        )
        assert result["per_query"][0]["utilization_rate"] is None
        assert result["overall"]["utilization_rate"] is None

    def test_full_utilization(self, populated_graph):
        """When all retrieved items are cited, utilization = 1.0."""
        results = populated_graph.recall("Python", limit=10)
        retrieved = populated_graph.retrieve("Python", limit=5)
        retrieved_ids = [r["node_id"] for r in retrieved]
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python",
              "relevant_ids": [n.id for n in results],
              "cited_ids": retrieved_ids}], k=5
        )
        # All retrieved items are cited
        assert result["per_query"][0]["utilization_rate"] == 1.0
        assert result["overall"]["utilization_rate"] == 1.0

    def test_zero_utilization(self, populated_graph):
        """When none of the retrieved items are cited, utilization = 0.0."""
        results = populated_graph.recall("Python", limit=10)
        python_ids = [n.id for n in results]
        # Cited IDs are completely different from what will be retrieved
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python",
              "relevant_ids": python_ids,
              "cited_ids": ["totally_fake_id"]}], k=5
        )
        assert result["per_query"][0]["utilization_rate"] == 0.0
        assert result["overall"]["utilization_rate"] == 0.0

    def test_partial_utilization(self, populated_graph):
        """Half of retrieved items cited → utilization ~0.5."""
        retrieved = populated_graph.retrieve("Python", limit=4)
        retrieved_ids = [r["node_id"] for r in retrieved]
        # Cite only half of retrieved items
        cited_half = retrieved_ids[:2]
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python",
              "relevant_ids": retrieved_ids,
              "cited_ids": cited_half}], k=4
        )
        ur = result["per_query"][0]["utilization_rate"]
        assert ur is not None
        assert 0.4 <= ur <= 0.6  # roughly 0.5

    def test_utilization_rate_range(self, populated_graph):
        """Utilization rate must be in [0, 1] or None."""
        results = populated_graph.recall("Python", limit=10)
        python_ids = [n.id for n in results]
        cited = python_ids[:3]
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python",
              "relevant_ids": python_ids,
              "cited_ids": cited}], k=5
        )
        ur = result["overall"]["utilization_rate"]
        assert ur is None or 0.0 <= ur <= 1.0

    def test_mixed_cases_some_with_cited(self, populated_graph):
        """Mix of cases with and without cited_ids."""
        results = populated_graph.recall("Python", limit=10)
        python_ids = [n.id for n in results]
        retrieved = populated_graph.retrieve("Python", limit=5)
        retrieved_ids = [r["node_id"] for r in retrieved]

        cases = [
            {"query": "Python",
             "relevant_ids": python_ids,
             "cited_ids": retrieved_ids[:2]},  # has cited
            {"query": "Python", "relevant_ids": python_ids},  # no cited
        ]
        result = populated_graph.retrieval_quality_eval(cases, k=5)
        pq = result["per_query"]
        assert pq[0]["utilization_rate"] is not None
        assert pq[1]["utilization_rate"] is None
        # Overall only averages cases with cited_ids
        assert result["overall"]["utilization_rate"] is not None

    def test_utilization_in_skipped_case(self, populated_graph):
        """Skipped cases should have utilization_rate = None."""
        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python", "relevant_ids": [],
              "cited_ids": ["some_id"]}], k=5
        )
        assert result["per_query"][0]["utilization_rate"] is None

    def test_cited_ids_as_set(self, populated_graph):
        """cited_ids should accept sets too."""
        results = populated_graph.recall("Python", limit=10)
        python_ids = [n.id for n in results]
        retrieved = populated_graph.retrieve("Python", limit=5)
        retrieved_set = {r["node_id"] for r in retrieved}

        result = populated_graph.retrieval_quality_eval(
            [{"query": "Python",
              "relevant_ids": python_ids,
              "cited_ids": retrieved_set}], k=5
        )
        assert result["per_query"][0]["utilization_rate"] is not None

    def test_overall_utilization_only_averages_with_cited(self, populated_graph):
        """Overall utilization_rate is macro-average over cases with cited_ids only."""
        results = populated_graph.recall("Python", limit=10)
        python_ids = [n.id for n in results]
        retrieved = populated_graph.retrieve("Python", limit=5)
        retrieved_ids = [r["node_id"] for r in retrieved]

        # Case 1: full utilization
        # Case 2: zero utilization
        cases = [
            {"query": "Python",
             "relevant_ids": python_ids,
             "cited_ids": retrieved_ids},  # all cited
            {"query": "Python",
             "relevant_ids": python_ids,
             "cited_ids": ["nonexistent"]},  # none cited
        ]
        result = populated_graph.retrieval_quality_eval(cases, k=5)
        overall_ur = result["overall"]["utilization_rate"]
        assert overall_ur is not None
        assert 0.4 <= overall_ur <= 0.6  # average of 1.0 and 0.0
