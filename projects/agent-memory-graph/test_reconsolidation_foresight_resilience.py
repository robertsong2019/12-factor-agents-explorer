"""Tests for reconsolidation_feedback, foresight_signals, graph_resilience_score."""

import unittest
import time
import os
import json

import sys
sys.path.insert(0, os.path.dirname(__file__))
from memory_graph import MemoryGraph


class TestReconsolidationFeedback(unittest.TestCase):
    """HiMem-inspired memory reconsolidation: retrieval failure -> learning signal."""

    def setUp(self):
        self.mg = MemoryGraph()

    def test_empty_graph_returns_empty(self):
        result = self.mg.reconsolidation_feedback("what is quantum computing?")
        self.assertEqual(result["promotions"], [])
        self.assertEqual(result["action_counts"],
                         {"added": 0, "updated": 0, "deleted": 0, "skipped": 0})
        self.assertEqual(result["gain_score"], 0.0)

    def test_return_structure(self):
        result = self.mg.reconsolidation_feedback("test")
        self.assertEqual(set(result.keys()),
                         {"promotions", "action_counts", "gain_score", "query"})

    def test_skipped_empty_content(self):
        self.mg.add("")
        evidence = [self.mg.conn.execute("SELECT id FROM nodes").fetchone()["id"]]
        result = self.mg.reconsolidation_feedback("empty", evidence_ids=evidence)
        self.assertEqual(result["action_counts"]["skipped"], 1)

    def test_explicit_evidence_ids(self):
        n = self.mg.add("TypeScript basics")
        result = self.mg.reconsolidation_feedback("TS", evidence_ids=[n.id])
        self.assertIn("action_counts", result)

    def test_evidence_search_fallback(self):
        self.mg.add("Python is a programming language")
        self.mg.add("Rust is a systems programming language")
        result = self.mg.reconsolidation_feedback("programming language")
        self.assertIn("promotions", result)

    def test_independent_evidence_creates_new_node(self):
        self.mg.add("Machine learning uses neural networks")
        evidence = [self.mg.conn.execute("SELECT id FROM nodes").fetchone()["id"]]
        result = self.mg.reconsolidation_feedback("ML topic", evidence_ids=evidence)
        has_add = any(a["action"] == "add" for a in result["promotions"])
        self.assertTrue(has_add, "Expected independent evidence to create new node")

    def test_max_new_nodes_respected(self):
        ids = [self.mg.add(f"Topic {i} is about subject {i}").id for i in range(10)]
        result = self.mg.reconsolidation_feedback("topic", evidence_ids=ids, max_new_nodes=2)
        self.assertLessEqual(result["action_counts"]["added"], 2)

    def test_gain_score_calculation(self):
        ids = [self.mg.add(f"Unique topic about {i}").id for i in range(5)]
        result = self.mg.reconsolidation_feedback("unique", evidence_ids=ids)
        useful = result["action_counts"]["added"] + result["action_counts"]["updated"]
        expected = useful / max(len(ids), 1)
        self.assertAlmostEqual(result["gain_score"], expected, places=2)

    def test_failure_ids_excluded_from_matches(self):
        fid = self.mg.add("Already known fact")
        eid = self.mg.add("New evidence fact")
        result = self.mg.reconsolidation_feedback(
            "fact", failure_ids=[fid.id], evidence_ids=[eid.id])
        for a in result["promotions"]:
            self.assertNotEqual(a.get("node_id"), fid.id)

    def test_extendable_boosts_confidence(self):
        self.mg.add("Neural networks process data in layers")
        evidence = [self.mg.conn.execute("SELECT id FROM nodes").fetchone()["id"]]
        result = self.mg.reconsolidation_feedback(
            "neural networks process data in layers", evidence_ids=evidence)
        # Identical content should be skipped (sim >= 0.9) or updated
        self.assertIn(result["action_counts"]["added"] + result["action_counts"]["skipped"], [0, 1])


class TestForesightSignals(unittest.TestCase):
    """EverMemOS-inspired prospective memory."""

    def setUp(self):
        self.mg = MemoryGraph()

    def test_empty_history(self):
        result = self.mg.foresight_signals()
        self.assertEqual(result["signals"], [])
        self.assertEqual(result["total_queries_analyzed"], 0)

    def test_return_structure(self):
        result = self.mg.foresight_signals()
        self.assertEqual(set(result.keys()),
                         {"signals", "window_seconds", "total_queries_analyzed"})

    def test_signal_structure(self):
        # Insert a manual clock_log entry
        self.mg._tick("search", details={"query": "test", "text": "test", "hits": 5})
        result = self.mg.foresight_signals()
        for sig in result["signals"]:
            self.assertIn("topic", sig)
            self.assertIn("score", sig)
            self.assertIn("source", sig)
            self.assertIn("reason", sig)
            self.assertIn("ttl", sig)

    def test_single_query_frequency(self):
        self.mg._tick("search", details={"query": "Python", "text": "Python", "hits": 10})
        result = self.mg.foresight_signals()
        self.assertEqual(result["total_queries_analyzed"], 1)
        freq = [s for s in result["signals"] if s["source"] == "query_frequency"]
        self.assertTrue(len(freq) >= 1)

    def test_repeated_query_higher_score(self):
        for _ in range(3):
            self.mg._tick("search", details={"query": "Python", "text": "Python", "hits": 10})
        result = self.mg.foresight_signals()
        freq = [s for s in result["signals"]
                if s["source"] == "query_frequency" and s["topic"] == "Python"]
        if freq:
            self.assertGreaterEqual(freq[0]["score"], 0.4)

    def test_gap_detection(self):
        self.mg._tick("search", details={"query": "rare topic", "text": "rare topic", "hits": 1})
        result = self.mg.foresight_signals()
        gap = [s for s in result["signals"] if s["source"] == "gap_neighborhood"]
        self.assertTrue(any(s["topic"] == "rare topic" for s in gap))

    def test_temporal_proximity(self):
        for i in range(3):
            self.mg._tick("search", details={"query": f"topic{i}", "text": f"topic{i}", "hits": 5})
        result = self.mg.foresight_signals()
        prox = [s for s in result["signals"] if s["source"] == "temporal_proximity"]
        self.assertTrue(len(prox) >= 1)

    def test_limit_respected(self):
        for i in range(20):
            self.mg._tick("search", details={"query": f"topic{i}", "text": f"topic{i}", "hits": 5})
        result = self.mg.foresight_signals(limit=3)
        self.assertLessEqual(len(result["signals"]), 3)

    def test_window_filtering(self):
        # Old query outside window
        self.mg.conn.execute(
            "INSERT INTO clock_log (lamport,op,node_id,details,wall_time) VALUES (0,'search',NULL,?,?)",
            (json.dumps({"query": "old topic", "text": "old topic"}), time.time() - 7200))
        # Recent query
        self.mg._tick("search", details={"query": "new topic", "text": "new topic", "hits": 5})
        result = self.mg.foresight_signals(recent_window=3600.0)
        old_found = any(s["topic"] == "old topic" for s in result["signals"])
        self.assertFalse(old_found)

    def test_sorted_by_score(self):
        for i in range(5):
            self.mg._tick("search", details={"query": f"topic{i}", "text": f"topic{i}", "hits": 5})
        result = self.mg.foresight_signals()
        scores = [s["score"] for s in result["signals"]]
        self.assertEqual(scores, sorted(scores, reverse=True))


class TestGraphResilienceScore(unittest.TestCase):
    """Single-point-of-failure detection via bottleneck analysis."""

    def setUp(self):
        self.mg = MemoryGraph()

    def test_empty_graph(self):
        result = self.mg.graph_resilience_score()
        self.assertEqual(result["bottlenecks"], [])
        self.assertEqual(result["overall_resilience"], 1.0)
        self.assertEqual(result["critical_nodes"], 0)

    def test_return_structure(self):
        self.mg.add("test")
        result = self.mg.graph_resilience_score()
        self.assertEqual(set(result.keys()),
                         {"bottlenecks", "overall_resilience", "critical_nodes", "total_analyzed"})

    def test_single_isolated_node(self):
        self.mg.add("isolated")
        result = self.mg.graph_resilience_score()
        self.assertEqual(len(result["bottlenecks"]), 1)
        self.assertEqual(result["bottlenecks"][0]["bottleneck_score"], 0.0)

    def test_fan_out_bottleneck(self):
        hub = self.mg.add("hub").id
        for i in range(5):
            leaf = self.mg.add(f"leaf{i}").id
            self.mg.link(hub, leaf, "depends_on")
        result = self.mg.graph_resilience_score(node_id=hub)
        b = result["bottlenecks"][0]
        self.assertEqual(b["fan_out"], 5)
        self.assertEqual(b["fan_in"], 0)
        self.assertEqual(b["bottleneck_score"], 5.0)
        self.assertGreater(result["critical_nodes"], 0)

    def test_balanced_node(self):
        n = self.mg.add("balanced").id
        for i in range(3):
            s = self.mg.add(f"src{i}").id
            t = self.mg.add(f"tgt{i}").id
            self.mg.link(s, n, "rel")
            self.mg.link(n, t, "rel")
        result = self.mg.graph_resilience_score(node_id=n)
        b = result["bottlenecks"][0]
        self.assertEqual(b["fan_in"], 3)
        self.assertEqual(b["fan_out"], 3)
        self.assertAlmostEqual(b["bottleneck_score"], 1.0)

    def test_overall_resilience_formula(self):
        hub = self.mg.add("hub").id
        for i in range(3):
            self.mg.link(hub, self.mg.add(f"leaf{i}").id, "dep")
        result = self.mg.graph_resilience_score()
        expected = 1.0 / (1.0 + 3.0)
        self.assertAlmostEqual(result["overall_resilience"], expected, places=2)

    def test_top_n_limit(self):
        for i in range(20):
            h = self.mg.add(f"hub{i}").id
            for j in range(i + 1):
                self.mg.link(h, self.mg.add(f"leaf_{i}_{j}").id, "dep")
        result = self.mg.graph_resilience_score(top_n=3)
        self.assertLessEqual(len(result["bottlenecks"]), 3)
        scores = [b["bottleneck_score"] for b in result["bottlenecks"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_removal_impact(self):
        hub = self.mg.add("hub").id
        for i in range(4):
            self.mg.link(hub, self.mg.add(f"leaf{i}").id, "dep")
        result = self.mg.graph_resilience_score(node_id=hub)
        self.assertAlmostEqual(result["bottlenecks"][0]["removal_impact"], 1.0, places=1)

    def test_specific_node_analysis(self):
        n1 = self.mg.add("n1").id
        n2 = self.mg.add("n2").id
        self.mg.link(n1, n2, "rel")
        result = self.mg.graph_resilience_score(node_id=n1)
        self.assertEqual(result["total_analyzed"], 1)
        self.assertEqual(result["bottlenecks"][0]["node_id"], n1)

    def test_critical_threshold(self):
        hub = self.mg.add("hub").id
        for i in range(5):
            self.mg.link(hub, self.mg.add(f"leaf{i}").id, "dep")
        result = self.mg.graph_resilience_score()
        self.assertGreaterEqual(result["critical_nodes"], 1)

    def test_diamond_pattern(self):
        a = self.mg.add("A").id
        b = self.mg.add("B").id
        c = self.mg.add("C").id
        d = self.mg.add("D").id
        self.mg.link(a, c, "dep")
        self.mg.link(b, c, "dep")
        self.mg.link(c, d, "dep")
        result = self.mg.graph_resilience_score()
        c_bn = [bn for bn in result["bottlenecks"] if bn["node_id"] == c]
        self.assertEqual(len(c_bn), 1)
        self.assertEqual(c_bn[0]["fan_in"], 2)
        self.assertEqual(c_bn[0]["fan_out"], 1)
        self.assertAlmostEqual(c_bn[0]["bottleneck_score"], 0.5, places=1)


if __name__ == "__main__":
    unittest.main()
