"""Tests for attention_distribution() — Cycle 405.

Attention distribution analysis: Gini coefficient, Shannon entropy,
zone classification (hot/warm/cool/cold/inactive), community attention
share, hotspots, and blindspots.
"""

import math
import time
import unittest

from memory_graph import MemoryGraph


class TestAttentionDistributionStructure(unittest.TestCase):
    """Verify return structure and required keys."""

    def setUp(self):
        self.mg = MemoryGraph()
        self.mg.add("A", "fact")
        self.mg.add("B", "fact")
        self.mg.link("A", "B", "related")

    def test_returns_dict(self):
        r = self.mg.attention_distribution()
        self.assertIsInstance(r, dict)

    def test_required_top_keys(self):
        r = self.mg.attention_distribution()
        for key in [
            "gini", "entropy", "zones", "zone_distribution",
            "per_community", "hotspots", "blindspots",
            "summary", "recommendations", "duration_seconds",
        ]:
            self.assertIn(key, r, f"Missing key: {key}")

    def test_summary_keys(self):
        r = self.mg.attention_distribution()
        for key in [
            "total_nodes", "hot_count", "cold_count",
            "blindspot_count", "hotspot_count",
            "dominant_zone", "attention_concentration",
        ]:
            self.assertIn(key, r["summary"], f"Missing summary key: {key}")

    def test_duration_positive(self):
        r = self.mg.attention_distribution()
        self.assertGreaterEqual(r["duration_seconds"], 0.0)


class TestAttentionDistributionDegenerate(unittest.TestCase):
    """Edge cases: empty, single, two nodes."""

    def test_empty_graph(self):
        mg = MemoryGraph()
        r = mg.attention_distribution()
        self.assertEqual(r["summary"]["total_nodes"], 0)
        self.assertEqual(r["gini"], 0.0)
        self.assertEqual(r["entropy"], 0.0)
        self.assertEqual(r["summary"]["dominant_zone"], "N/A")
        self.assertTrue(len(r["recommendations"]) > 0)

    def test_single_node(self):
        mg = MemoryGraph()
        mg.add("Solo", "fact")
        r = mg.attention_distribution()
        self.assertEqual(r["summary"]["total_nodes"], 1)
        # Single node = no inequality
        self.assertEqual(r["gini"], 0.0)
        # All attention on one node
        self.assertEqual(r["summary"]["dominant_zone"], "hot")

    def test_two_nodes_no_edge(self):
        mg = MemoryGraph()
        mg.add("A", "fact")
        mg.add("B", "fact")
        r = mg.attention_distribution()
        self.assertEqual(r["summary"]["total_nodes"], 2)
        # Same timestamps → equal attention
        self.assertLess(r["gini"], 0.1)


class TestAttentionGini(unittest.TestCase):
    """Gini coefficient correctness."""

    def test_gini_range(self):
        """Gini must be in [0, 1]."""
        mg = MemoryGraph()
        now = time.time()
        for i in range(20):
            mg.add(f"N{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - i * 3600, 0.1 + i * 0.5, f"N{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertGreaterEqual(r["gini"], 0.0)
        self.assertLessEqual(r["gini"], 1.0)

    def test_equal_attention_low_gini(self):
        """All nodes with same access + weight → low Gini."""
        mg = MemoryGraph()
        now = time.time()
        for i in range(10):
            mg.add(f"N{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now, 1.0, f"N{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertLess(r["gini"], 0.05)

    def test_skewed_attention_high_gini(self):
        """One node much more attended → higher Gini."""
        mg = MemoryGraph()
        now = time.time()
        mg.add("Star", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now, 10.0, "Star"),
        )
        for i in range(20):
            mg.add(f"Low{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - 86400 * 60, 0.01, f"Low{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertGreater(r["gini"], 0.5)


class TestAttentionEntropy(unittest.TestCase):
    """Shannon entropy of attention distribution."""

    def test_entropy_range(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(15):
            mg.add(f"N{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - i * 100, 0.5 + i * 0.1, f"N{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertGreaterEqual(r["entropy"], 0.0)
        self.assertLessEqual(r["entropy"], 1.0)

    def test_equal_attention_high_entropy(self):
        """Uniform attention → high normalised entropy."""
        mg = MemoryGraph()
        now = time.time()
        for i in range(10):
            mg.add(f"N{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now, 1.0, f"N{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertGreater(r["entropy"], 0.9)

    def test_concentrated_attention_low_entropy(self):
        """One dominant node → low entropy."""
        mg = MemoryGraph()
        now = time.time()
        mg.add("Dom", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now, 100.0, "Dom"),
        )
        for i in range(20):
            mg.add(f"Tiny{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - 86400 * 90, 0.001, f"Tiny{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertLess(r["entropy"], 0.5)


class TestAttentionZones(unittest.TestCase):
    """Zone classification: hot/warm/cool/cold."""

    def test_zone_counts_sum_to_total(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(20):
            mg.add(f"N{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - i * 86400, 0.5 + i * 0.05, f"N{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        total = sum(r["zones"].values())
        self.assertEqual(total, 20)

    def test_zone_distribution_sums_to_one(self):
        mg = MemoryGraph()
        mg.add("A", "fact")
        mg.add("B", "fact")
        mg.add("C", "fact")
        mg.add("D", "fact")
        r = mg.attention_distribution()
        total = sum(r["zone_distribution"].values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_hot_zone_exists_for_recent_high_weight(self):
        mg = MemoryGraph()
        now = time.time()
        mg.add("Hot", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now, 5.0, "Hot"),
        )
        r = mg.attention_distribution()
        self.assertGreater(r["zones"].get("hot", 0), 0)

    def test_cold_zone_for_old_low_weight(self):
        mg = MemoryGraph()
        now = time.time()
        mg.add("Cold", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now - 86400 * 30, 0.1, "Cold"),
        )
        r = mg.attention_distribution()
        # Should be in cool or cold
        cool_or_cold = r["zones"].get("cool", 0) + r["zones"].get("cold", 0)
        self.assertGreater(cool_or_cold, 0)

    def test_five_zone_mode_has_inactive(self):
        mg = MemoryGraph()
        now = time.time()
        mg.add("Ancient", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now - 86400 * 365, 0.5, "Ancient"),
        )
        r = mg.attention_distribution(num_zones=5)
        self.assertIn("inactive", r["zones"])

    def test_dominant_zone_is_max(self):
        mg = MemoryGraph()
        now = time.time()
        # Make most nodes hot
        for i in range(8):
            mg.add(f"H{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now, 2.0, f"H{i}"),
            )
        mg.add("Cold1", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now - 86400 * 30, 0.1, "Cold1"),
        )
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertEqual(r["summary"]["dominant_zone"], "hot")


class TestAttentionCommunity(unittest.TestCase):
    """Per-community attention share."""

    def test_per_community_structure(self):
        mg = MemoryGraph()
        now = time.time()
        # Create two connected groups
        for i in range(5):
            mg.add(f"A{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now, 1.0, f"A{i}"),
            )
        for i in range(5):
            mg.add(f"B{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - 86400 * 30, 0.3, f"B{i}"),
            )
        # Intra-group edges
        for i in range(4):
            mg.link(f"A{i}", f"A{i + 1}", "related")
            mg.link(f"B{i}", f"B{i + 1}", "related")
        mg.conn.commit()
        r = mg.attention_distribution()
        for comm in r["per_community"]:
            for key in [
                "community", "size", "attention_share",
                "expected_share", "over_under_ratio", "label",
            ]:
                self.assertIn(key, comm)
            self.assertGreaterEqual(comm["attention_share"], 0.0)
            self.assertLessEqual(comm["attention_share"], 1.0)
            self.assertIn(comm["label"], [
                "over-attended", "under-attended", "balanced",
            ])

    def test_over_attended_community(self):
        mg = MemoryGraph()
        now = time.time()
        # Community 1: high attention
        for i in range(5):
            mg.add(f"Hot{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now, 3.0, f"Hot{i}"),
            )
        # Community 2: low attention
        for i in range(5):
            mg.add(f"Cold{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - 86400 * 90, 0.01, f"Cold{i}"),
            )
        for i in range(4):
            mg.link(f"Hot{i}", f"Hot{i + 1}", "related")
            mg.link(f"Cold{i}", f"Cold{i + 1}", "related")
        mg.conn.commit()
        r = mg.attention_distribution()
        if r["per_community"]:
            labels = [c["label"] for c in r["per_community"]]
            self.assertIn("over-attended", labels)

    def test_per_community_shares_sum_to_one(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(10):
            mg.add(f"N{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - i * 3600, 0.5 + i * 0.1, f"N{i}"),
            )
        for i in range(8):
            mg.link(f"N{i}", f"N{i + 1}", "related")
        mg.conn.commit()
        r = mg.attention_distribution()
        if r["per_community"]:
            total = sum(c["attention_share"] for c in r["per_community"])
            self.assertAlmostEqual(total, 1.0, places=2)


class TestHotspotsAndBlindspots(unittest.TestCase):
    """Hotspot and blindspot identification."""

    def test_hotspot_identified(self):
        mg = MemoryGraph()
        now = time.time()
        # Create many nodes, one dominant
        mg.add("Star", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now, 10.0, "Star"),
        )
        for i in range(20):
            mg.add(f"Bg{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - 86400 * 14, 0.1, f"Bg{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertGreater(len(r["hotspots"]), 0)
        self.assertEqual(r["hotspots"][0]["label"], "Star")

    def test_blindspot_identified(self):
        mg = MemoryGraph()
        now = time.time()
        # High weight but old access → blindspot
        mg.add("Neglected", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now - 86400 * 60, 5.0, "Neglected"),
        )
        # Low weight, recent → not a blindspot
        for i in range(20):
            mg.add(f"Fresh{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now, 0.1, f"Fresh{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertGreater(len(r["blindspots"]), 0)
        self.assertEqual(r["blindspots"][0]["label"], "Neglected")

    def test_hotspot_structure(self):
        mg = MemoryGraph()
        now = time.time()
        mg.add("H", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now, 5.0, "H"),
        )
        for i in range(20):
            mg.add(f"B{i}", "fact")
        mg.conn.commit()
        r = mg.attention_distribution()
        if r["hotspots"]:
            hs = r["hotspots"][0]
            for key in ["node_id", "label", "attention", "weight", "recency"]:
                self.assertIn(key, hs)

    def test_blindspot_structure(self):
        mg = MemoryGraph()
        now = time.time()
        mg.add("BS", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now - 86400 * 90, 4.0, "BS"),
        )
        for i in range(20):
            mg.add(f"F{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now, 0.5, f"F{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        if r["blindspots"]:
            bs = r["blindspots"][0]
            for key in ["node_id", "label", "weight", "attention", "recency"]:
                self.assertIn(key, bs)

    def test_hotspots_capped_at_20(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(50):
            mg.add(f"H{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now, 5.0 + i * 0.1, f"H{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertLessEqual(len(r["hotspots"]), 20)

    def test_blindspots_capped_at_20(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(50):
            mg.add(f"B{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - 86400 * 90, 3.0 + i * 0.1, f"B{i}"),
            )
        for i in range(50):
            mg.add(f"F{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now, 0.1, f"F{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertLessEqual(len(r["blindspots"]), 20)


class TestAttentionNonMutating(unittest.TestCase):
    """Verify the API doesn't modify the graph."""

    def test_graph_unchanged(self):
        mg = MemoryGraph()
        mg.add("A", "fact")
        mg.add("B", "fact")
        mg.link("A", "B", "related")
        nodes_before = mg.stats()["nodes"]
        edges_before = mg.edge_count()
        mg.attention_distribution()
        self.assertEqual(mg.stats()["nodes"], nodes_before)
        self.assertEqual(mg.edge_count(), edges_before)

    def test_no_new_edges(self):
        mg = MemoryGraph()
        mg.add("X", "fact")
        mg.add("Y", "fact")
        before = mg.edge_count()
        mg.attention_distribution()
        self.assertEqual(mg.edge_count(), before)


class TestAttentionDeterminism(unittest.TestCase):
    """Same inputs → same outputs."""

    def test_same_result_twice(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(10):
            mg.add(f"N{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - i * 3600, 1.0 + i * 0.1, f"N{i}"),
            )
        mg.conn.commit()
        r1 = mg.attention_distribution(now=now)
        r2 = mg.attention_distribution(now=now)
        self.assertEqual(r1["gini"], r2["gini"])
        self.assertEqual(r1["entropy"], r2["entropy"])
        self.assertEqual(r1["zones"], r2["zones"])

    def test_now_parameter_stable(self):
        mg = MemoryGraph()
        mg.add("A", "fact")
        mg.add("B", "fact")
        fixed_now = 1700000000.0
        r1 = mg.attention_distribution(now=fixed_now)
        r2 = mg.attention_distribution(now=fixed_now)
        self.assertAlmostEqual(r1["gini"], r2["gini"])
        self.assertAlmostEqual(r1["entropy"], r2["entropy"])


class TestAttentionRecommendations(unittest.TestCase):
    """Recommendation generation."""

    def test_high_gini_recommendation(self):
        mg = MemoryGraph()
        now = time.time()
        mg.add("Star", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now, 100.0, "Star"),
        )
        for i in range(30):
            mg.add(f"Tiny{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - 86400 * 90, 0.001, f"Tiny{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        joined = " ".join(r["recommendations"])
        if r["gini"] > 0.7:
            self.assertIn("concentration", joined.lower())

    def test_cold_majority_recommendation(self):
        mg = MemoryGraph()
        now = time.time()
        # 1 hot node
        mg.add("Hot", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now, 2.0, "Hot"),
        )
        # 10 cold nodes
        for i in range(10):
            mg.add(f"C{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - 86400 * 30, 0.1, f"C{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        joined = " ".join(r["recommendations"])
        self.assertTrue(
            "cold" in joined.lower() or "within" in joined.lower()
        )

    def test_blindspot_recommendation(self):
        mg = MemoryGraph()
        now = time.time()
        mg.add("BS", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now - 86400 * 90, 5.0, "BS"),
        )
        for i in range(25):
            mg.add(f"F{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now, 0.5, f"F{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        if r["blindspots"]:
            joined = " ".join(r["recommendations"])
            self.assertIn("Blindspot", joined)

    def test_healthy_recommendation(self):
        mg = MemoryGraph()
        now = time.time()
        # Moderate distribution — not perfectly uniform, not skewed
        for i in range(15):
            mg.add(f"N{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - i * 7200, 0.8 + i * 0.05, f"N{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        # Should have recommendations (healthy or otherwise)
        self.assertGreater(len(r["recommendations"]), 0)
        joined = " ".join(r["recommendations"])
        # Either healthy or some specific advice
        self.assertTrue(len(joined) > 10)

    def test_recommendations_not_empty(self):
        mg = MemoryGraph()
        mg.add("A", "fact")
        r = mg.attention_distribution()
        self.assertGreater(len(r["recommendations"]), 0)


class TestAttentionConcentrationLabel(unittest.TestCase):
    """Attention concentration classification."""

    def test_high_concentration(self):
        mg = MemoryGraph()
        now = time.time()
        mg.add("Dom", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now, 50.0, "Dom"),
        )
        for i in range(30):
            mg.add(f"Bg{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - 86400 * 90, 0.001, f"Bg{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertIn(r["summary"]["attention_concentration"], [
            "high", "moderate",
        ])

    def test_distributed_concentration(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(20):
            mg.add(f"N{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now, 1.0, f"N{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertEqual(r["summary"]["attention_concentration"], "distributed")


class TestAttentionAlgorithmVariants(unittest.TestCase):
    """Different community algorithms should all work."""

    def setUp(self):
        self.mg = MemoryGraph()
        now = time.time()
        for i in range(10):
            self.mg.add(f"N{i}", "fact")
            self.mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - i * 3600, 1.0, f"N{i}"),
            )
        for i in range(8):
            self.mg.link(f"N{i}", f"N{i + 1}", "related")
        self.mg.conn.commit()

    def test_leiden(self):
        r = self.mg.attention_distribution(algorithm="leiden")
        self.assertGreaterEqual(r["summary"]["total_nodes"], 10)

    def test_greedy(self):
        r = self.mg.attention_distribution(algorithm="greedy")
        self.assertGreaterEqual(r["summary"]["total_nodes"], 10)

    def test_lp(self):
        r = self.mg.attention_distribution(algorithm="lp")
        self.assertGreaterEqual(r["summary"]["total_nodes"], 10)


class TestAttentionIntegration(unittest.TestCase):
    """Integration with graph modifications."""

    def test_works_after_modification(self):
        mg = MemoryGraph()
        mg.add("A", "fact")
        mg.add("B", "fact")
        r1 = mg.attention_distribution()
        mg.add("C", "concept")
        r2 = mg.attention_distribution()
        self.assertEqual(r2["summary"]["total_nodes"], r1["summary"]["total_nodes"] + 1)

    def test_now_affects_gini(self):
        """Different `now` timestamps should affect attention decay."""
        mg = MemoryGraph()
        mg.add("A", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (1000.0, 2.0, "A"),
        )
        mg.add("B", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (1000.0, 2.0, "B"),
        )
        mg.conn.commit()
        # Near-time: both fresh
        r1 = mg.attention_distribution(now=1100.0)
        # Far-future: both decayed but equally
        r2 = mg.attention_distribution(now=1000000.0)
        # Both scenarios should have similar Gini since nodes are symmetric
        self.assertAlmostEqual(r1["gini"], r2["gini"], places=1)

    def test_now_affects_zones(self):
        """Further `now` → more cold/inactive zones."""
        mg = MemoryGraph()
        now = time.time()
        mg.add("N", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now, 1.0, "N"),
        )
        mg.conn.commit()
        r_near = mg.attention_distribution(now=now + 1)
        r_far = mg.attention_distribution(now=now + 86400 * 365)
        self.assertEqual(r_near["summary"]["dominant_zone"], "hot")
        self.assertIn(r_far["summary"]["dominant_zone"], ["cold", "inactive", "cool"])

    def test_large_graph(self):
        """Should handle a larger graph without error."""
        mg = MemoryGraph()
        now = time.time()
        for i in range(100):
            mg.add(f"N{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - i * 600, 0.5 + (i % 5) * 0.5, f"N{i}"),
            )
        for i in range(99):
            mg.link(f"N{i}", f"N{i + 1}", "related")
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertEqual(r["summary"]["total_nodes"], 100)
        self.assertGreater(r["duration_seconds"], 0.0)


class TestAttentionEdgeCases(unittest.TestCase):
    """Specific edge case scenarios."""

    def test_all_same_timestamp(self):
        """All nodes created/accessed at the same time."""
        mg = MemoryGraph()
        now = time.time()
        for i in range(10):
            mg.add(f"N{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now, 1.0, f"N{i}"),
            )
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertLess(r["gini"], 0.01)
        self.assertGreater(r["entropy"], 0.95)

    def test_star_graph(self):
        """Star topology — hub gets all attention."""
        mg = MemoryGraph()
        now = time.time()
        mg.add("Hub", "fact")
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
            (now, 5.0, "Hub"),
        )
        for i in range(10):
            mg.add(f"Leaf{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - 86400 * 14, 0.1, f"Leaf{i}"),
            )
            mg.link("Hub", f"Leaf{i}", "related")
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertGreater(r["gini"], 0.3)
        # Hub should be a hotspot
        if r["hotspots"]:
            self.assertEqual(r["hotspots"][0]["label"], "Hub")

    def test_disconnected_components(self):
        """Disconnected subgraphs."""
        mg = MemoryGraph()
        now = time.time()
        # Component 1
        for i in range(5):
            mg.add(f"A{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now, 1.0, f"A{i}"),
            )
        for i in range(4):
            mg.link(f"A{i}", f"A{i + 1}", "related")
        # Component 2
        for i in range(5):
            mg.add(f"B{i}", "fact")
            mg.conn.execute(
                "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
                (now - 86400 * 30, 0.5, f"B{i}"),
            )
        for i in range(4):
            mg.link(f"B{i}", f"B{i + 1}", "related")
        mg.conn.commit()
        r = mg.attention_distribution()
        self.assertEqual(r["summary"]["total_nodes"], 10)
        # Should not crash with disconnected components
        self.assertGreaterEqual(r["gini"], 0.0)


if __name__ == "__main__":
    unittest.main()
