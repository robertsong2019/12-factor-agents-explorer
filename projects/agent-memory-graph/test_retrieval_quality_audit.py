"""
Tests for retrieval_quality_audit() — Cycle 404.

Post-retrieval quality assessment bridging community detection,
interference analysis, temporal freshness, and graph coverage.
"""

import math
import time
import unittest

from memory_graph import MemoryGraph


def _build_rich_graph() -> tuple[MemoryGraph, dict[str, str]]:
    """Build a graph with multiple communities and varied freshness.

    Returns (graph, label_to_id) mapping for test convenience.
    """
    mg = MemoryGraph()
    ids: dict[str, str] = {}

    # Community 1: Python ecosystem
    ids["Python"] = mg.add("Python", "concept", {"importance": 0.9}).id
    ids["Django"] = mg.add("Django", "concept", {"importance": 0.7}).id
    ids["Flask"] = mg.add("Flask", "concept", {"importance": 0.6}).id
    mg.link(ids["Python"], ids["Django"], "framework")
    mg.link(ids["Python"], ids["Flask"], "framework")
    mg.link(ids["Django"], ids["Flask"], "alternative")

    # Community 2: Rust ecosystem
    ids["Rust"] = mg.add("Rust", "concept", {"importance": 0.85}).id
    ids["Tokio"] = mg.add("Tokio", "concept", {"importance": 0.7}).id
    ids["Actix"] = mg.add("Actix", "concept", {"importance": 0.6}).id
    mg.link(ids["Rust"], ids["Tokio"], "framework")
    mg.link(ids["Rust"], ids["Actix"], "framework")
    mg.link(ids["Tokio"], ids["Actix"], "related")

    # Community 3: Go ecosystem
    ids["Go"] = mg.add("Go", "concept", {"importance": 0.8}).id
    ids["Gin"] = mg.add("Gin", "concept", {"importance": 0.5}).id
    mg.link(ids["Go"], ids["Gin"], "framework")

    # Bridge
    mg.link(ids["Python"], ids["Rust"], "compared")
    mg.link(ids["Rust"], ids["Go"], "compared")

    return mg, ids


def _ids(ids_map: dict[str, str], *labels: str) -> list[str]:
    """Extract node IDs from the label→id mapping."""
    return [ids_map[l] for l in labels]


def _build_stale_graph() -> tuple[MemoryGraph, list[str]]:
    """Build a graph where nodes have old access times."""
    mg = MemoryGraph()
    n1 = mg.add("old1", "fact")
    n2 = mg.add("old2", "fact")
    n3 = mg.add("old3", "fact")
    mg.link(n1.id, n2.id, "related")
    mg.link(n2.id, n3.id, "related")

    # Set old access times (30 days ago)
    old_ts = time.time() - 30 * 86400
    mg.conn.execute(
        "UPDATE nodes SET accessed=? WHERE id IN (?,?,?)",
        (old_ts, n1.id, n2.id, n3.id),
    )
    mg.conn.commit()
    return mg, [n1.id, n2.id, n3.id]


class TestStructure(unittest.TestCase):
    """Test basic return structure."""

    def test_returns_dict(self):
        mg = MemoryGraph()
        n = mg.add("A", "fact")
        result = mg.retrieval_quality_audit([n.id])
        self.assertIsInstance(result, dict)

    def test_required_top_keys(self):
        mg = MemoryGraph()
        n = mg.add("A", "fact")
        result = mg.retrieval_quality_audit([n.id])
        for key in ("overall_quality", "diversity_score",
                    "interference_score", "freshness_score",
                    "coverage_score", "weights", "per_node",
                    "conflict_pairs", "recommendations", "summary",
                    "duration_seconds"):
            self.assertIn(key, result)

    def test_summary_keys(self):
        mg = MemoryGraph()
        n = mg.add("A", "fact")
        result = mg.retrieval_quality_audit([n.id])
        for key in ("result_count", "graph_size",
                    "communities_represented", "conflict_pair_count",
                    "mean_freshness"):
            self.assertIn(key, result["summary"])

    def test_weights_keys(self):
        mg = MemoryGraph()
        n = mg.add("A", "fact")
        result = mg.retrieval_quality_audit([n.id])
        for key in ("diversity", "interference", "freshness", "coverage"):
            self.assertIn(key, result["weights"])

    def test_per_node_entry_keys(self):
        mg = MemoryGraph()
        n1 = mg.add("A", "fact")
        n2 = mg.add("B", "fact")
        result = mg.retrieval_quality_audit([n1.id, n2.id])
        for entry in result["per_node"]:
            self.assertIn("node_id", entry)
            self.assertIn("label", entry)
            self.assertIn("weight", entry)
            self.assertIn("freshness", entry)
            self.assertIn("community", entry)
            self.assertIn("neighbour_count", entry)

    def test_conflict_pair_keys(self):
        mg, ids = _build_rich_graph()
        result = mg.retrieval_quality_audit(_ids(ids, "Python", "Django", "Flask"))
        for pair in result["conflict_pairs"]:
            self.assertIn("node_a", pair)
            self.assertIn("node_b", pair)
            self.assertIn("overlap", pair)
            self.assertIn("shared_neighbours", pair)


class TestDegenerate(unittest.TestCase):
    """Test edge cases."""

    def test_empty_node_ids(self):
        mg = MemoryGraph()
        result = mg.retrieval_quality_audit([])
        self.assertEqual(result["overall_quality"], 0.0)
        self.assertTrue(len(result["recommendations"]) > 0)

    def test_nonexistent_nodes(self):
        mg = MemoryGraph()
        result = mg.retrieval_quality_audit(["fake1", "fake2"])
        self.assertEqual(result["summary"]["result_count"], 0)

    def test_mixed_valid_invalid(self):
        mg = MemoryGraph()
        n = mg.add("real", "fact")
        result = mg.retrieval_quality_audit([n.id, "fake"])
        self.assertEqual(result["summary"]["result_count"], 1)

    def test_single_node(self):
        mg = MemoryGraph()
        n = mg.add("solo", "fact")
        result = mg.retrieval_quality_audit([n.id])
        # Single node → max interference score (no conflicts)
        self.assertEqual(result["interference_score"], 1.0)
        self.assertEqual(result["summary"]["conflict_pair_count"], 0)

    def test_empty_graph(self):
        mg = MemoryGraph()
        result = mg.retrieval_quality_audit([])
        self.assertEqual(result["summary"]["graph_size"], 0)


class TestCorrectness(unittest.TestCase):
    """Test value correctness."""

    def test_all_scores_in_range(self):
        mg, ids = _build_rich_graph()
        result = mg.retrieval_quality_audit(_ids(ids, "Python", "Rust", "Go"))
        for score_key in ("diversity_score", "interference_score",
                          "freshness_score", "coverage_score",
                          "overall_quality"):
            val = result[score_key]
            self.assertGreaterEqual(val, 0.0, f"{score_key} below 0: {val}")
            self.assertLessEqual(val, 1.0, f"{score_key} above 1: {val}")

    def test_overall_is_weighted_sum(self):
        mg, ids = _build_rich_graph()
        result = mg.retrieval_quality_audit(_ids(ids, "Python", "Rust", "Go"))
        w = result["weights"]
        expected = (
            w["diversity"] * result["diversity_score"]
            + w["interference"] * result["interference_score"]
            + w["freshness"] * result["freshness_score"]
            + w["coverage"] * result["coverage_score"]
        )
        self.assertAlmostEqual(result["overall_quality"], round(expected, 4), places=3)

    def test_diverse_results_higher_diversity(self):
        mg, ids = _build_rich_graph()
        diverse = mg.retrieval_quality_audit(_ids(ids, "Python", "Rust", "Go"))
        same_comm = mg.retrieval_quality_audit(_ids(ids, "Python", "Django", "Flask"))
        self.assertGreaterEqual(
            diverse["diversity_score"], same_comm["diversity_score"],
            "Diverse picks should score >= same-community")

    def test_overlapping_results_lower_interference(self):
        mg, ids = _build_rich_graph()
        overlapping = mg.retrieval_quality_audit(_ids(ids, "Python", "Django", "Flask"))
        separate = mg.retrieval_quality_audit(_ids(ids, "Python", "Rust", "Go"))
        self.assertGreater(
            separate["interference_score"], overlapping["interference_score"],
            "Separate results should have higher interference score")

    def test_fresh_graph_high_freshness(self):
        mg, ids = _build_rich_graph()
        result = mg.retrieval_quality_audit(_ids(ids, "Python", "Rust"))
        self.assertGreater(result["freshness_score"], 0.5)

    def test_stale_graph_low_freshness(self):
        mg, node_ids = _build_stale_graph()
        result = mg.retrieval_quality_audit(node_ids)
        self.assertLess(result["freshness_score"], 0.3)

    def test_conflict_pairs_sorted_by_overlap(self):
        mg, ids = _build_rich_graph()
        result = mg.retrieval_quality_audit(
            _ids(ids, "Python", "Django", "Flask", "Rust"))
        if len(result["conflict_pairs"]) >= 2:
            self.assertGreaterEqual(
                result["conflict_pairs"][0]["overlap"],
                result["conflict_pairs"][1]["overlap"])

    def test_coverage_non_decreasing_with_more_nodes(self):
        mg, ids = _build_rich_graph()
        fewer = mg.retrieval_quality_audit(_ids(ids, "Python"))
        more = mg.retrieval_quality_audit(_ids(ids, "Python", "Rust", "Go", "Django"))
        self.assertGreaterEqual(more["coverage_score"], fewer["coverage_score"])

    def test_per_node_count_matches(self):
        mg, ids = _build_rich_graph()
        target_ids = _ids(ids, "Python", "Rust", "Go")
        result = mg.retrieval_quality_audit(target_ids)
        self.assertEqual(len(result["per_node"]), len(target_ids))


class TestWeights(unittest.TestCase):
    """Test weight configuration."""

    def test_default_weights_sum_to_one(self):
        mg = MemoryGraph()
        n = mg.add("A", "fact")
        result = mg.retrieval_quality_audit([n.id])
        total = sum(result["weights"].values())
        self.assertAlmostEqual(total, 1.0, places=3)

    def test_custom_weights_normalised(self):
        mg = MemoryGraph()
        n1 = mg.add("A", "fact")
        n2 = mg.add("B", "fact")
        result = mg.retrieval_quality_audit(
            [n1.id, n2.id], weights={"diversity": 10, "interference": 0,
                                      "freshness": 0, "coverage": 0})
        self.assertAlmostEqual(result["weights"]["diversity"], 1.0, places=3)

    def test_custom_weights_affect_overall(self):
        mg, ids = _build_rich_graph()
        target = _ids(ids, "Python", "Django", "Flask")
        hi = mg.retrieval_quality_audit(
            target, weights={"interference": 1.0, "diversity": 0,
                              "freshness": 0, "coverage": 0})
        hd = mg.retrieval_quality_audit(
            target, weights={"diversity": 1.0, "interference": 0,
                              "freshness": 0, "coverage": 0})
        self.assertNotAlmostEqual(
            hi["overall_quality"], hd["overall_quality"], places=2)

    def test_partial_weights(self):
        mg = MemoryGraph()
        n = mg.add("A", "fact")
        result = mg.retrieval_quality_audit(
            [n.id], weights={"diversity": 0.5})
        total = sum(result["weights"].values())
        self.assertAlmostEqual(total, 1.0, places=3)


class TestNonMutating(unittest.TestCase):
    """Test graph is not modified."""

    def test_graph_unchanged(self):
        mg, ids = _build_rich_graph()
        before = mg.conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        mg.retrieval_quality_audit(_ids(ids, "Python", "Rust"))
        after = mg.conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        self.assertEqual(before, after)

    def test_no_new_edges(self):
        mg, ids = _build_rich_graph()
        before = mg.edge_count()
        mg.retrieval_quality_audit(_ids(ids, "Python", "Rust"))
        after = mg.edge_count()
        self.assertEqual(before, after)


class TestDeterminism(unittest.TestCase):
    """Test deterministic output."""

    def test_same_results_twice(self):
        mg, ids = _build_rich_graph()
        target = _ids(ids, "Python", "Rust", "Go")
        r1 = mg.retrieval_quality_audit(target)
        r2 = mg.retrieval_quality_audit(target)
        self.assertEqual(r1["overall_quality"], r2["overall_quality"])
        self.assertEqual(r1["diversity_score"], r2["diversity_score"])

    def test_now_parameter_stable(self):
        mg, ids = _build_rich_graph()
        ts = time.time()
        target = _ids(ids, "Python", "Rust")
        r1 = mg.retrieval_quality_audit(target, now=ts)
        r2 = mg.retrieval_quality_audit(target, now=ts)
        self.assertEqual(r1["freshness_score"], r2["freshness_score"])


class TestIntegration(unittest.TestCase):
    """Integration with graph operations."""

    def test_works_after_graph_modification(self):
        mg, ids = _build_rich_graph()
        numpy_id = mg.add("NumPy", "concept").id
        mg.link(ids["Python"], numpy_id, "library")
        result = mg.retrieval_quality_audit(
            [ids["Python"], ids["Rust"], numpy_id])
        self.assertGreater(result["overall_quality"], 0.0)

    def test_now_parameter_affects_freshness(self):
        mg = MemoryGraph()
        n = mg.add("test", "fact")
        fresh_result = mg.retrieval_quality_audit([n.id], now=time.time())
        stale_result = mg.retrieval_quality_audit(
            [n.id], now=time.time() + 365 * 86400)
        self.assertGreater(
            fresh_result["freshness_score"],
            stale_result["freshness_score"])

    def test_consistent_with_interference_report(self):
        """High interference in audit → high overlap in interference report."""
        mg, ids = _build_rich_graph()
        target = _ids(ids, "Django", "Flask")
        audit = mg.retrieval_quality_audit(target)
        report = mg.memory_interference_report(ids["Django"])
        if audit["interference_score"] < 0.8:
            self.assertGreater(report["summary"]["max_similarity"], 0.0)

    def test_algorithm_parameter(self):
        mg, ids = _build_rich_graph()
        target = _ids(ids, "Python", "Rust")
        for algo in ("leiden", "greedy", "lp"):
            result = mg.retrieval_quality_audit(target, algorithm=algo)
            self.assertGreaterEqual(result["diversity_score"], 0.0)
            self.assertLessEqual(result["diversity_score"], 1.0)

    def test_recommendations_generated(self):
        mg, ids = _build_rich_graph()
        result = mg.retrieval_quality_audit(_ids(ids, "Python", "Django", "Flask"))
        self.assertIsInstance(result["recommendations"], list)
        self.assertGreater(len(result["recommendations"]), 0)

    def test_stale_recommendation_triggered(self):
        mg, node_ids = _build_stale_graph()
        result = mg.retrieval_quality_audit(node_ids)
        stale_recs = [r for r in result["recommendations"]
                       if "stale" in r.lower() or "refresh" in r.lower()]
        self.assertGreater(len(stale_recs), 0)

    def test_low_diversity_recommendation(self):
        mg, ids = _build_rich_graph()
        result = mg.retrieval_quality_audit(_ids(ids, "Python", "Django", "Flask"))
        if result["diversity_score"] < 0.3:
            div_recs = [r for r in result["recommendations"]
                        if "diversity" in r.lower()
                        or "cluster" in r.lower()
                        or "expansion" in r.lower()]
            self.assertGreater(len(div_recs), 0)

    def test_isolated_node_high_interference_score(self):
        mg = MemoryGraph()
        n = mg.add("lonely", "fact")
        result = mg.retrieval_quality_audit([n.id])
        self.assertEqual(result["interference_score"], 1.0)


class TestConflictPairs(unittest.TestCase):
    """Test conflict pair detection."""

    def test_no_conflict_for_disconnected(self):
        mg = MemoryGraph()
        n1 = mg.add("A", "fact")
        n2 = mg.add("B", "fact")
        result = mg.retrieval_quality_audit([n1.id, n2.id])
        self.assertEqual(len(result["conflict_pairs"]), 0)

    def test_conflict_for_overlapping(self):
        mg = MemoryGraph()
        nA = mg.add("A", "fact")
        nB = mg.add("B", "fact")
        nS1 = mg.add("shared1", "fact")
        nS2 = mg.add("shared2", "fact")
        mg.link(nA.id, nS1.id, "related")
        mg.link(nA.id, nS2.id, "related")
        mg.link(nB.id, nS1.id, "related")
        mg.link(nB.id, nS2.id, "related")
        result = mg.retrieval_quality_audit([nA.id, nB.id])
        self.assertGreater(len(result["conflict_pairs"]), 0)
        self.assertGreaterEqual(result["conflict_pairs"][0]["overlap"], 0.5)

    def test_conflict_pairs_capped_at_20(self):
        """Conflict pairs list should not exceed 20 entries."""
        mg = MemoryGraph()
        mg.add("common", "fact")
        mg.add("hub", "fact")
        node_ids = []
        for i in range(30):
            n = mg.add(f"node_{i}", "fact")
            node_ids.append(n.id)
            mg.link(n.id, "common", "related")  # type: ignore
            mg.link(n.id, "hub", "related")  # type: ignore
        result = mg.retrieval_quality_audit(node_ids)
        self.assertLessEqual(len(result["conflict_pairs"]), 20)


class TestCoverage(unittest.TestCase):
    """Test coverage scoring."""

    def test_single_node_small_graph(self):
        mg = MemoryGraph()
        n = mg.add("A", "fact")
        result = mg.retrieval_quality_audit([n.id])
        self.assertGreater(result["coverage_score"], 0.0)

    def test_single_node_large_graph(self):
        mg, ids = _build_rich_graph()
        result = mg.retrieval_quality_audit(_ids(ids, "Python"))
        self.assertGreater(result["coverage_score"], 0.0)
        self.assertLess(result["coverage_score"], 1.0)

    def test_all_nodes_full_coverage(self):
        mg = MemoryGraph()
        n1 = mg.add("A", "fact")
        n2 = mg.add("B", "fact")
        mg.link(n1.id, n2.id, "related")
        result = mg.retrieval_quality_audit([n1.id, n2.id])
        self.assertEqual(result["coverage_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
