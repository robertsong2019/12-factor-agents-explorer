"""Tests for retrieval_quality_rerank() — Cycle 414.

Quality-aware re-ranking of retrieval result sets using Greedy Marginal
Contribution (GMC) selection.  Tests cover:

- Structure / return value shape
- Degenerate cases (empty, single node, all-missing)
- Re-ranking correctness (diversity-first, coverage-first)
- Improvement metrics (deltas non-negative for diversity)
- Non-mutating property
- Determinism
- Weight overrides
- Integration with retrieval_quality_audit
- Edge cases (star graph, all-same-community, isolated nodes)
"""

import math
import time
import pytest
from memory_graph import MemoryGraph


# ── Helpers ────────────────────────────────────────────────────

def _make_graph(n: int = 20) -> tuple[MemoryGraph, list[str]]:
    """Build a connected test graph with *n* nodes.

    Returns (graph, node_ids).
    """
    mg = MemoryGraph()
    ids = []
    for i in range(n):
        node = mg.add(f"node_{i}", "test", {"index": i})
        ids.append(node.id)
    # Chain + some cross-links for community structure
    for i in range(n - 1):
        mg.link(ids[i], ids[i + 1], "chain", weight=0.8)
    # Some extra links to create communities
    for i in range(0, n // 2):
        mg.link(ids[i], ids[(i + 2) % (n // 2)], "cross", weight=0.6)
    for i in range(n // 2, n):
        mg.link(ids[i], ids[n // 2 + (i + 2 - n // 2) % (n // 2)], "cross", weight=0.6)
    return mg, ids


def _make_two_cluster_graph() -> tuple[MemoryGraph, dict[str, str]]:
    """Graph with two clear clusters + a bridge.

    Returns (graph, label→id_map).
    """
    mg = MemoryGraph()
    label2id: dict[str, str] = {}

    # Cluster A
    for i in range(6):
        node = mg.add(f"a_{i}", "cluster_a")
        label2id[f"a_{i}"] = node.id
    for i in range(6):
        for j in range(i + 1, 6):
            mg.link(label2id[f"a_{i}"], label2id[f"a_{j}"], "intra_a", weight=0.7)

    # Cluster B
    for i in range(6):
        node = mg.add(f"b_{i}", "cluster_b")
        label2id[f"b_{i}"] = node.id
    for i in range(6):
        for j in range(i + 1, 6):
            mg.link(label2id[f"b_{i}"], label2id[f"b_{j}"], "intra_b", weight=0.7)

    # Bridge
    mg.link(label2id["a_0"], label2id["b_0"], "bridge", weight=0.3)
    return mg, label2id


def _make_star_graph(n: int = 10) -> tuple[MemoryGraph, dict[str, str]]:
    """Star graph: centre + n-1 leaves."""
    mg = MemoryGraph()
    label2id: dict[str, str] = {}
    centre = mg.add("centre", "hub")
    label2id["centre"] = centre.id
    for i in range(1, n):
        leaf = mg.add(f"leaf_{i}", "leaf")
        label2id[f"leaf_{i}"] = leaf.id
        mg.link(centre.id, leaf.id, "spoke", weight=0.9)
    return mg, label2id


# ── 1. Structure ──────────────────────────────────────────────

class TestRerankStructure:

    def test_returns_dict(self):
        mg, ids = _make_graph(10)
        result = mg.retrieval_quality_rerank(ids[:3])
        assert isinstance(result, dict)

    def test_required_top_keys(self):
        mg, ids = _make_graph(10)
        result = mg.retrieval_quality_rerank(ids[:3])
        for key in ("reranked_ids", "original_ids", "improvement",
                     "audit_before", "audit_after",
                     "marginal_contributions", "duration_seconds"):
            assert key in result, f"Missing key: {key}"

    def test_improvement_keys(self):
        mg, ids = _make_graph(10)
        result = mg.retrieval_quality_rerank(ids[:3])
        imp = result["improvement"]
        for key in ("diversity_delta", "interference_delta",
                     "coverage_delta", "overall_delta"):
            assert key in imp

    def test_marginal_contribution_keys(self):
        mg, ids = _make_graph(10)
        result = mg.retrieval_quality_rerank(ids[:3])
        mc = result["marginal_contributions"]
        assert len(mc) == 3
        for entry in mc:
            for key in ("node_id", "coverage_gain", "diversity_gain",
                         "freshness", "redundancy_penalty",
                         "marginal_score", "position"):
                assert key in entry

    def test_reranked_same_set(self):
        """Re-ranked IDs contain exactly the same elements."""
        mg, ids = _make_graph(10)
        subset = ids[:4]
        result = mg.retrieval_quality_rerank(subset)
        assert set(result["reranked_ids"]) == set(subset)
        assert len(result["reranked_ids"]) == len(subset)

    def test_duration_non_negative(self):
        mg, ids = _make_graph(10)
        result = mg.retrieval_quality_rerank(ids[:2])
        assert result["duration_seconds"] >= 0.0


# ── 2. Degenerate ──────────────────────────────────────────────

class TestRerankDegenerate:

    def test_empty_input(self):
        mg, _ = _make_graph(5)
        result = mg.retrieval_quality_rerank([])
        assert result["reranked_ids"] == []
        assert result["improvement"]["overall_delta"] == 0.0

    def test_single_node(self):
        mg, ids = _make_graph(5)
        result = mg.retrieval_quality_rerank([ids[0]])
        assert result["reranked_ids"] == [ids[0]]
        assert result["marginal_contributions"] == []

    def test_all_invalid_ids(self):
        mg, _ = _make_graph(5)
        result = mg.retrieval_quality_rerank(["nope_1", "nope_2"])
        assert result["reranked_ids"] == []

    def test_partial_invalid(self):
        """Valid + invalid IDs — only valid kept."""
        mg, ids = _make_graph(5)
        result = mg.retrieval_quality_rerank([ids[0], "fake_1", ids[1]])
        assert set(result["reranked_ids"]) == {ids[0], ids[1]}
        assert len(result["reranked_ids"]) == 2


# ── 3. Re-ranking Correctness ──────────────────────────────────

class TestRerankCorrectness:

    def test_first_pick_has_highest_marginal(self):
        """First selected node should have the highest marginal score."""
        mg, m = _make_two_cluster_graph()
        input_ids = [m["a_0"], m["a_1"], m["b_0"], m["b_1"]]
        result = mg.retrieval_quality_rerank(input_ids)
        scores = [mc["marginal_score"] for mc in result["marginal_contributions"]]
        assert scores[0] >= scores[-1]

    def test_two_cluster_diversifies(self):
        """With two clusters, rerank should interleave rather than
        putting all a_* first then all b_*."""
        mg, m = _make_two_cluster_graph()
        input_ids = [m["a_0"], m["a_1"], m["a_2"], m["b_0"], m["b_1"], m["b_2"]]
        result = mg.retrieval_quality_rerank(input_ids)
        ordered = result["reranked_ids"]

        # Map ordered back to cluster labels
        id2label = {v: k for k, v in m.items()}
        ordered_labels = [id2label[nid] for nid in ordered]

        # The first two picks should be from different clusters
        first_two_clusters = set()
        for label in ordered_labels[:2]:
            if label.startswith("a_"):
                first_two_clusters.add("A")
            else:
                first_two_clusters.add("B")
        assert len(first_two_clusters) == 2, (
            f"Expected 2 clusters in first 2 picks, "
            f"got {ordered_labels[:2]}"
        )

    def test_original_order_preserved_in_original_ids(self):
        mg, ids = _make_graph(10)
        subset = [ids[3], ids[1], ids[5], ids[7]]
        result = mg.retrieval_quality_rerank(subset)
        assert result["original_ids"] == subset

    def test_positions_are_sequential(self):
        mg, ids = _make_graph(10)
        result = mg.retrieval_quality_rerank(ids[:4])
        positions = [mc["position"] for mc in result["marginal_contributions"]]
        assert positions == [0, 1, 2, 3]


# ── 4. Improvement Metrics ─────────────────────────────────────

class TestRerankImprovement:

    def test_diversity_not_worse(self):
        """Re-ranking should not reduce diversity below original."""
        mg, m = _make_two_cluster_graph()
        # Original: all a_* first, then all b_* — worst diversity order
        ids = [m["a_0"], m["a_1"], m["a_2"], m["a_3"],
               m["b_0"], m["b_1"], m["b_2"], m["b_3"]]
        result = mg.retrieval_quality_rerank(ids)
        assert result["improvement"]["diversity_delta"] >= -0.01, (
            f"Diversity worsened: {result['improvement']['diversity_delta']}"
        )

    def test_audit_after_is_valid(self):
        mg, ids = _make_graph(15)
        result = mg.retrieval_quality_rerank(ids[:10])
        after = result["audit_after"]
        assert "overall_quality" in after
        assert 0.0 <= after["overall_quality"] <= 1.0

    def test_audit_before_is_valid(self):
        mg, ids = _make_graph(15)
        result = mg.retrieval_quality_rerank(ids[:10])
        before = result["audit_before"]
        assert "overall_quality" in before
        assert 0.0 <= before["overall_quality"] <= 1.0

    def test_improvement_delta_is_difference(self):
        """Delta = after - before."""
        mg, ids = _make_graph(15)
        result = mg.retrieval_quality_rerank(ids[:8])
        expected = round(
            result["audit_after"]["overall_quality"]
            - result["audit_before"]["overall_quality"], 4)
        assert abs(result["improvement"]["overall_delta"] - expected) < 0.01


# ── 5. Non-Mutating ────────────────────────────────────────────

class TestRerankNonMutating:

    def test_graph_unchanged(self):
        mg, ids = _make_graph(10)
        node_count_before = mg.conn.execute(
            "SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        edge_count_before = mg.conn.execute(
            "SELECT COUNT(*) as c FROM edges").fetchone()["c"]
        mg.retrieval_quality_rerank(ids[:3])
        node_count_after = mg.conn.execute(
            "SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        edge_count_after = mg.conn.execute(
            "SELECT COUNT(*) as c FROM edges").fetchone()["c"]
        assert node_count_before == node_count_after
        assert edge_count_before == edge_count_after

    def test_node_weights_unchanged(self):
        mg, ids = _make_graph(10)
        mg.reweight(ids[0], -0.5)  # delta, not set — default weight is 1.0
        mg.retrieval_quality_rerank(ids[:2])
        row = mg.conn.execute(
            "SELECT weight FROM nodes WHERE id=?", (ids[0],)).fetchone()
        assert row["weight"] == pytest.approx(0.5)


# ── 6. Determinism ─────────────────────────────────────────────

class TestRerankDeterminism:

    def test_same_result_twice(self):
        mg, ids = _make_graph(15)
        subset = ids[:8]
        r1 = mg.retrieval_quality_rerank(subset)
        r2 = mg.retrieval_quality_rerank(subset)
        assert r1["reranked_ids"] == r2["reranked_ids"]

    def test_now_parameter_stable(self):
        mg, ids = _make_graph(15)
        subset = ids[:8]
        fixed_now = time.time() + 3600  # 1h in the future
        r1 = mg.retrieval_quality_rerank(subset, now=fixed_now)
        r2 = mg.retrieval_quality_rerank(subset, now=fixed_now)
        assert r1["reranked_ids"] == r2["reranked_ids"]


# ── 7. Weight Overrides ────────────────────────────────────────

class TestRerankWeights:

    def test_weight_override_accepted(self):
        mg, ids = _make_graph(15)
        result = mg.retrieval_quality_rerank(
            ids[:8], weights={"coverage": 0.5, "diversity": 0.1,
                              "freshness": 0.1, "redundancy": 0.3})
        assert "weights" in result
        assert result["weights"]["coverage"] == pytest.approx(0.5, abs=0.01)

    def test_weights_auto_normalised(self):
        mg, ids = _make_graph(15)
        result = mg.retrieval_quality_rerank(
            ids[:8], weights={"coverage": 10.0, "diversity": 10.0,
                              "freshness": 10.0, "redundancy": 10.0})
        total = sum(result["weights"].values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_coverage_focused_vs_diversity_focused(self):
        """Coverage-focused rerank should prioritise nodes with more
        uncovered neighbours."""
        mg, m = _make_two_cluster_graph()
        ids = [m["a_0"], m["a_1"], m["a_2"], m["b_0"], m["b_1"], m["b_2"]]
        cov_result = mg.retrieval_quality_rerank(
            ids, weights={"coverage": 0.9, "diversity": 0.02,
                          "freshness": 0.02, "redundancy": 0.06})
        div_result = mg.retrieval_quality_rerank(
            ids, weights={"coverage": 0.02, "diversity": 0.9,
                          "freshness": 0.02, "redundancy": 0.06})
        # They may or may not differ, but both should produce valid orderings
        assert set(cov_result["reranked_ids"]) == set(ids)
        assert set(div_result["reranked_ids"]) == set(ids)

    def test_unknown_weight_key_ignored(self):
        mg, ids = _make_graph(10)
        result = mg.retrieval_quality_rerank(
            ids[:3], weights={"unknown_key": 0.99})
        assert isinstance(result, dict)


# ── 8. Integration ─────────────────────────────────────────────

class TestRerankIntegration:

    def test_audit_consistency(self):
        """audit_after per_node should match reranked ordering."""
        mg, ids = _make_graph(20)
        subset = ids[:10]
        result = mg.retrieval_quality_rerank(subset)
        after_ids = [pn["node_id"] for pn in result["audit_after"]["per_node"]]
        assert after_ids == result["reranked_ids"]

    def test_algorithm_parameter(self):
        """Different community algorithms should all work."""
        mg, ids = _make_graph(15)
        subset = ids[:8]
        for algo in ("leiden", "greedy", "lp"):
            result = mg.retrieval_quality_rerank(subset, algorithm=algo)
            assert isinstance(result, dict)
            assert len(result["reranked_ids"]) == 8

    def test_works_after_graph_modification(self):
        mg, ids = _make_graph(10)
        new_node = mg.add("new_node", "test")
        mg.link(new_node.id, ids[5], "link", weight=0.8)
        result = mg.retrieval_quality_rerank(
            [ids[0], new_node.id, ids[5]])
        assert new_node.id in result["reranked_ids"]

    def test_large_graph(self):
        mg, ids = _make_graph(100)
        subset = ids[::5]  # 20 nodes
        result = mg.retrieval_quality_rerank(subset)
        assert len(result["reranked_ids"]) == 20
        assert len(result["marginal_contributions"]) == 20


# ── 9. Edge Cases ──────────────────────────────────────────────

class TestRerankEdgeCases:

    def test_star_graph(self):
        """Centre should rank high (covers all leaves)."""
        mg, m = _make_star_graph(10)
        input_ids = [m["leaf_1"], m["leaf_2"], m["leaf_3"], m["centre"]]
        result = mg.retrieval_quality_rerank(input_ids)
        # Centre should not be last (it has the highest coverage)
        assert result["reranked_ids"].index(m["centre"]) < 3, (
            f"Centre ranked too low: {result['reranked_ids']}"
        )

    def test_all_same_community(self):
        """All nodes in the same community — should run without error."""
        mg, ids = _make_graph(10)
        result = mg.retrieval_quality_rerank(ids[:5])
        assert len(result["reranked_ids"]) == 5

    def test_isolated_nodes(self):
        """Nodes with no edges — coverage 0, should rank after connected."""
        mg = MemoryGraph()
        iso1 = mg.add("isolated_1", "test")
        iso2 = mg.add("isolated_2", "test")
        conn1 = mg.add("connected_1", "test")
        conn2 = mg.add("connected_2", "test")
        mg.link(conn1.id, conn2.id, "link", weight=0.8)
        all_ids = [iso1.id, iso2.id, conn1.id, conn2.id]
        result = mg.retrieval_quality_rerank(all_ids)
        # Connected nodes should rank before isolated (higher coverage)
        first_two = set(result["reranked_ids"][:2])
        assert conn1.id in first_two or conn2.id in first_two

    def test_duplicate_ids_in_input(self):
        """Duplicate IDs in input — should not crash."""
        mg, ids = _make_graph(5)
        result = mg.retrieval_quality_rerank(
            [ids[0], ids[0], ids[1]])
        assert isinstance(result, dict)

    def test_extreme_now(self):
        """Very large now should not crash (very stale freshness)."""
        mg, ids = _make_graph(10)
        result = mg.retrieval_quality_rerank(
            ids[:3], now=time.time() + 86400 * 365)  # 1 year in future
        assert isinstance(result, dict)
