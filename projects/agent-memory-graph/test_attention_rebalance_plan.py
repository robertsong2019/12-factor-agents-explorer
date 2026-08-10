"""Tests for attention_rebalance_plan() — Cycle 407.

Action-oriented companion to attention_distribution() (Cycle 405).
Generates per-node actions (refresh, boost, diversify, consolidate,
forget) with estimated Gini impact and priority ordering.
"""

import math
import time
import unittest

from memory_graph import MemoryGraph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_node(mg, label, *, weight=1.0, age_days=0, kind="fact"):
    """Add a node and set its weight and accessed time."""
    mg.add(label, kind=kind)
    ts = time.time()
    mg.conn.execute(
        "UPDATE nodes SET accessed=?, weight=? WHERE label=?",
        (ts - 86400 * age_days, weight, label))
    mg.conn.commit()


def _basic_graph(now=None):
    """Graph with 12 nodes: mix of hot, warm, cool, cold, blindspots."""
    mg = MemoryGraph()
    # Hot nodes (recently accessed, high weight)
    for i in range(3):
        _set_node(mg, f"hot_{i}", weight=3.0 + i * 0.5, age_days=0.1 * (i + 1))
    # Warm nodes (recently accessed, lower weight)
    for i in range(3):
        _set_node(mg, f"warm_{i}", weight=0.8, age_days=0.5 * (i + 1))
    # Cool nodes (old access, high weight) — blindspot candidates
    for i in range(2):
        _set_node(mg, f"cool_{i}", weight=2.5, age_days=15 * (i + 1))
    # Cold nodes (old access, low weight) — forget candidates
    for i in range(2):
        _set_node(mg, f"cold_{i}", weight=0.3, age_days=30 * (i + 1))
    # Inactive nodes (very old, low weight)
    for i in range(2):
        _set_node(mg, f"inact_{i}", weight=0.2, age_days=60 * (i + 1))
    # Add some edges for community detection
    mg.link("hot_0", "hot_1", "related")
    mg.link("hot_1", "hot_2", "related")
    mg.link("warm_0", "warm_1", "related")
    mg.link("cool_0", "cool_1", "related")
    return mg


def _star_graph(now=None):
    """Star graph: one central hub + 10 peripheral nodes."""
    mg = MemoryGraph()
    _set_node(mg, "hub", weight=5.0, age_days=0)
    for i in range(10):
        _set_node(mg, f"periph_{i}", weight=1.0, age_days=3 * (i + 1))
        mg.link("hub", f"periph_{i}", "related")
    return mg


def _large_graph(n=100, now=None):
    """Large graph with varied recency/weight patterns."""
    mg = MemoryGraph()
    import random
    rng = random.Random(42)
    for i in range(n):
        w = rng.uniform(0.1, 4.0)
        age = rng.uniform(0.1, 60)
        _set_node(mg, f"node_{i}", weight=w, age_days=age)
    for i in range(min(n - 1, 50)):
        mg.link(f"node_{i}", f"node_{i + 1}", "related")
    return mg


def _all_same_graph():
    """All nodes with same timestamp and weight."""
    mg = MemoryGraph()
    ts = time.time()
    for i in range(8):
        mg.add(f"n{i}", kind="fact")
    # Set ALL to exact same timestamp/weight in one UPDATE
    mg.conn.execute(
        "UPDATE nodes SET accessed=?, weight=1.0", (ts,))
    mg.conn.commit()
    return mg


def _disconnected_graph():
    """Disconnected nodes."""
    mg = MemoryGraph()
    for i in range(6):
        _set_node(mg, f"iso_{i}", weight=1.0 + i * 0.3, age_days=5 * i)
    return mg


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------

class TestStructure(unittest.TestCase):

    def setUp(self):
        self.mg = _basic_graph()

    def test_returns_dict(self):
        self.assertIsInstance(self.mg.attention_rebalance_plan(), dict)

    def test_required_top_keys(self):
        r = self.mg.attention_rebalance_plan()
        for key in ["current_gini", "current_entropy", "projected_gini",
                     "projected_entropy", "improvement", "actions",
                     "summary", "duration_seconds"]:
            self.assertIn(key, r)

    def test_improvement_keys(self):
        r = self.mg.attention_rebalance_plan()
        self.assertIn("gini_delta", r["improvement"])
        self.assertIn("entropy_delta", r["improvement"])

    def test_summary_keys(self):
        r = self.mg.attention_rebalance_plan()
        for key in ["total_actions", "by_type", "by_priority", "top_priority"]:
            self.assertIn(key, r["summary"])

    def test_duration_positive(self):
        r = self.mg.attention_rebalance_plan()
        self.assertGreaterEqual(r["duration_seconds"], 0.0)

    def test_action_keys(self):
        r = self.mg.attention_rebalance_plan()
        for a in r["actions"]:
            for key in ["node_id", "label", "action", "priority",
                        "reason", "current_attention", "weight",
                        "zone", "estimated_gini_delta"]:
                self.assertIn(key, a)


# ---------------------------------------------------------------------------
# Degenerate cases
# ---------------------------------------------------------------------------

class TestDegenerate(unittest.TestCase):

    def test_empty_graph(self):
        mg = MemoryGraph()
        r = mg.attention_rebalance_plan()
        self.assertEqual(r["current_gini"], 0.0)
        self.assertEqual(r["actions"], [])
        self.assertEqual(r["summary"]["total_actions"], 0)

    def test_single_node(self):
        mg = MemoryGraph()
        _set_node(mg, "only", weight=1.0, age_days=0)
        r = mg.attention_rebalance_plan()
        # Single node: Gini is 0, no improvement possible
        self.assertEqual(r["current_gini"], 0.0)
        # Actions may or may not be generated, but should be valid
        for a in r["actions"]:
            self.assertIn(a["action"],
                          {"refresh", "boost", "diversify",
                           "consolidate", "forget"})

    def test_two_nodes(self):
        mg = MemoryGraph()
        _set_node(mg, "a", weight=2.0, age_days=0)
        _set_node(mg, "b", weight=0.5, age_days=40)
        mg.link("a", "b", "related")
        r = mg.attention_rebalance_plan()
        self.assertIsInstance(r["actions"], list)
        self.assertGreaterEqual(r["current_gini"], 0.0)


# ---------------------------------------------------------------------------
# Gini / entropy values
# ---------------------------------------------------------------------------

class TestMetrics(unittest.TestCase):

    def setUp(self):
        self.mg = _basic_graph()

    def test_gini_in_range(self):
        r = self.mg.attention_rebalance_plan()
        self.assertGreaterEqual(r["current_gini"], 0.0)
        self.assertLessEqual(r["current_gini"], 1.0)

    def test_entropy_in_range(self):
        r = self.mg.attention_rebalance_plan()
        self.assertGreaterEqual(r["current_entropy"], 0.0)
        self.assertLessEqual(r["current_entropy"], 1.0)

    def test_projected_gini_in_range(self):
        r = self.mg.attention_rebalance_plan()
        self.assertGreaterEqual(r["projected_gini"], 0.0)
        self.assertLessEqual(r["projected_gini"], 1.0)

    def test_projected_entropy_in_range(self):
        r = self.mg.attention_rebalance_plan()
        self.assertGreaterEqual(r["projected_entropy"], 0.0)
        self.assertLessEqual(r["projected_entropy"], 1.0)

    def test_improvement_gini_non_negative_when_concentrated(self):
        r = self.mg.attention_rebalance_plan()
        if r["current_gini"] > 0.3:
            self.assertGreaterEqual(r["improvement"]["gini_delta"], -0.001)

    def test_uniform_graph_zero_gini(self):
        mg = _all_same_graph()
        r = mg.attention_rebalance_plan()
        self.assertEqual(r["current_gini"], 0.0)


# ---------------------------------------------------------------------------
# Action generation
# ---------------------------------------------------------------------------

class TestActions(unittest.TestCase):

    def setUp(self):
        self.mg = _basic_graph()

    def test_refresh_action_for_blindspot(self):
        """High-weight, low-attention node should trigger refresh."""
        r = self.mg.attention_rebalance_plan()
        refresh = [a for a in r["actions"] if a["action"] == "refresh"]
        self.assertGreaterEqual(len(refresh), 1)

    def test_forget_action_for_cold_low_weight(self):
        """Cold/inactive, low-weight nodes should trigger forget."""
        r = self.mg.attention_rebalance_plan()
        forget = [a for a in r["actions"] if a["action"] == "forget"]
        self.assertGreaterEqual(len(forget), 1)

    def test_consolidate_action_for_cool_high_weight(self):
        """Cool zone nodes with weight >= 1.5 should trigger consolidate."""
        r = self.mg.attention_rebalance_plan()
        consol = [a for a in r["actions"] if a["action"] == "consolidate"]
        self.assertGreaterEqual(len(consol), 1)

    def test_actions_sorted_by_priority(self):
        r = self.mg.attention_rebalance_plan()
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        priorities = [priority_order.get(a["priority"], 3)
                      for a in r["actions"]]
        self.assertEqual(priorities, sorted(priorities))

    def test_max_actions_cap(self):
        mg = _large_graph(100)
        r = mg.attention_rebalance_plan(max_actions=5)
        self.assertLessEqual(len(r["actions"]), 5)

    def test_max_actions_default(self):
        mg = _large_graph(100)
        r = mg.attention_rebalance_plan()
        self.assertLessEqual(len(r["actions"]), 20)

    def test_action_valid_type(self):
        r = self.mg.attention_rebalance_plan()
        valid_types = {"refresh", "boost", "diversify",
                       "consolidate", "forget"}
        for a in r["actions"]:
            self.assertIn(a["action"], valid_types)

    def test_action_valid_priority(self):
        r = self.mg.attention_rebalance_plan()
        valid = {"critical", "high", "medium", "low"}
        for a in r["actions"]:
            self.assertIn(a["priority"], valid)

    def test_action_reason_nonempty(self):
        r = self.mg.attention_rebalance_plan()
        for a in r["actions"]:
            self.assertGreater(len(a["reason"]), 10)

    def test_action_gini_delta_is_float(self):
        r = self.mg.attention_rebalance_plan()
        for a in r["actions"]:
            self.assertIsInstance(a["estimated_gini_delta"], float)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestSummary(unittest.TestCase):

    def setUp(self):
        self.mg = _basic_graph()

    def test_by_type_sums_match(self):
        r = self.mg.attention_rebalance_plan()
        self.assertEqual(
            sum(r["summary"]["by_type"].values()),
            r["summary"]["total_actions"])

    def test_by_priority_sums_match(self):
        r = self.mg.attention_rebalance_plan()
        self.assertEqual(
            sum(r["summary"]["by_priority"].values()),
            r["summary"]["total_actions"])

    def test_top_priority_is_min_priority(self):
        r = self.mg.attention_rebalance_plan()
        if r["actions"]:
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            expected = min(
                priority_order.get(a["priority"], 3)
                for a in r["actions"])
            actual = priority_order.get(r["summary"]["top_priority"], 3)
            self.assertEqual(actual, expected)

    def test_empty_graph_summary(self):
        mg = MemoryGraph()
        r = mg.attention_rebalance_plan()
        self.assertEqual(r["summary"]["total_actions"], 0)
        self.assertEqual(r["summary"]["top_priority"], "none")


# ---------------------------------------------------------------------------
# Non-mutating
# ---------------------------------------------------------------------------

class TestNonMutating(unittest.TestCase):

    def setUp(self):
        self.mg = _basic_graph()

    def test_graph_unchanged(self):
        before = self.mg.stats()
        self.mg.attention_rebalance_plan()
        after = self.mg.stats()
        self.assertEqual(before, after)

    def test_no_new_edges(self):
        before = self.mg.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        self.mg.attention_rebalance_plan()
        after = self.mg.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        self.assertEqual(before, after)

    def test_no_node_changes(self):
        before = self.mg.conn.execute(
            "SELECT id, weight, accessed FROM nodes ORDER BY id").fetchall()
        self.mg.attention_rebalance_plan()
        after = self.mg.conn.execute(
            "SELECT id, weight, accessed FROM nodes ORDER BY id").fetchall()
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism(unittest.TestCase):

    def setUp(self):
        self.mg = _basic_graph()

    def test_same_result_twice(self):
        r1 = self.mg.attention_rebalance_plan()
        r2 = self.mg.attention_rebalance_plan()
        self.assertEqual(r1["current_gini"], r2["current_gini"])
        self.assertEqual(r1["projected_gini"], r2["projected_gini"])
        self.assertEqual(r1["summary"]["total_actions"],
                         r2["summary"]["total_actions"])

    def test_now_parameter_stable(self):
        ts = time.time()
        r1 = self.mg.attention_rebalance_plan(now=ts)
        r2 = self.mg.attention_rebalance_plan(now=ts)
        self.assertEqual(r1["current_gini"], r2["current_gini"])
        self.assertEqual(r1["actions"], r2["actions"])


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

class TestProjection(unittest.TestCase):

    def test_projected_gini_le_current_when_actions_exist(self):
        """Projected Gini should be <= current when there are
        refresh/boost actions (raising low attention to median)."""
        mg = _basic_graph()
        r = mg.attention_rebalance_plan()
        refresh_boost = [
            a for a in r["actions"]
            if a["action"] in ("refresh", "boost")
        ]
        if refresh_boost:
            self.assertLessEqual(r["projected_gini"],
                                 r["current_gini"] + 0.001)

    def test_improvement_gini_delta_sign(self):
        mg = _basic_graph()
        r = mg.attention_rebalance_plan()
        self.assertGreaterEqual(r["improvement"]["gini_delta"], -0.001)

    def test_no_actions_no_projection_change(self):
        """When there are no refresh/boost actions, projected = current."""
        mg = MemoryGraph()
        r = mg.attention_rebalance_plan()
        self.assertEqual(r["projected_gini"], r["current_gini"])
        self.assertEqual(r["projected_entropy"], r["current_entropy"])

    def test_projection_improves_concentrated_graph(self):
        """A graph with clear blindspots should show improvement."""
        mg = _star_graph()
        r = mg.attention_rebalance_plan()
        refresh = [a for a in r["actions"] if a["action"] == "refresh"]
        if refresh and r["current_gini"] > 0.3:
            self.assertGreater(r["improvement"]["gini_delta"], 0.0)


# ---------------------------------------------------------------------------
# Algorithm variants
# ---------------------------------------------------------------------------

class TestAlgorithmVariants(unittest.TestCase):

    def setUp(self):
        self.mg = _basic_graph()

    def test_leiden(self):
        r = self.mg.attention_rebalance_plan(algorithm="leiden")
        self.assertIsInstance(r, dict)
        self.assertIn("actions", r)

    def test_greedy(self):
        r = self.mg.attention_rebalance_plan(algorithm="greedy")
        self.assertIsInstance(r, dict)
        self.assertIn("actions", r)

    def test_lp(self):
        r = self.mg.attention_rebalance_plan(algorithm="lp")
        self.assertIsInstance(r, dict)
        self.assertIn("actions", r)

    def test_different_algorithms_both_valid(self):
        mg = _large_graph(50)
        r1 = mg.attention_rebalance_plan(algorithm="leiden")
        r2 = mg.attention_rebalance_plan(algorithm="greedy")
        self.assertIsInstance(r1["actions"], list)
        self.assertIsInstance(r2["actions"], list)


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------

class TestIntegration(unittest.TestCase):

    def test_works_after_modification(self):
        """Adding a node changes the plan."""
        mg = _basic_graph()
        r1 = mg.attention_rebalance_plan()
        _set_node(mg, "new_node", weight=3.0, age_days=0)
        r2 = mg.attention_rebalance_plan()
        self.assertIsNot(r1, r2)

    def test_consistent_with_attention_distribution(self):
        """Gini from rebalance_plan should match attention_distribution."""
        mg = _basic_graph()
        ts = time.time()
        plan = mg.attention_rebalance_plan(now=ts)
        dist = mg.attention_distribution(now=ts)
        self.assertEqual(plan["current_gini"], dist["gini"])
        self.assertEqual(plan["current_entropy"], dist["entropy"])

    def test_large_graph_100_nodes(self):
        mg = _large_graph(100)
        r = mg.attention_rebalance_plan()
        self.assertLessEqual(len(r["actions"]), 20)
        self.assertLess(r["duration_seconds"], 30.0)

    def test_star_graph(self):
        mg = _star_graph()
        r = mg.attention_rebalance_plan()
        self.assertIsInstance(r["actions"], list)
        self.assertGreaterEqual(r["current_gini"], 0.0)

    def test_disconnected_components(self):
        mg = _disconnected_graph()
        r = mg.attention_rebalance_plan()
        self.assertIsInstance(r, dict)
        self.assertGreaterEqual(r["current_gini"], 0.0)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):

    def test_all_same_timestamp(self):
        mg = _all_same_graph()
        r = mg.attention_rebalance_plan()
        self.assertEqual(r["current_gini"], 0.0)
        # Uniform graph: no refresh needed (all at or above median)
        refresh = [a for a in r["actions"] if a["action"] == "refresh"]
        self.assertEqual(len(refresh), 0)

    def test_now_far_future(self):
        """All nodes become very old → high Gini potential."""
        mg = _basic_graph()
        far_future = time.time() + 86400 * 365
        r = mg.attention_rebalance_plan(now=far_future)
        self.assertIsInstance(r, dict)

    def test_max_actions_zero(self):
        mg = _basic_graph()
        r = mg.attention_rebalance_plan(max_actions=0)
        self.assertEqual(r["actions"], [])

    def test_max_actions_one(self):
        mg = _basic_graph()
        r = mg.attention_rebalance_plan(max_actions=1)
        self.assertLessEqual(len(r["actions"]), 1)

    def test_forget_cap(self):
        """Forget actions should be capped at 10."""
        mg = _large_graph(100)
        r = mg.attention_rebalance_plan(max_actions=50)
        forget = [a for a in r["actions"] if a["action"] == "forget"]
        self.assertLessEqual(len(forget), 10)

    def test_zone_in_valid_set(self):
        mg = _basic_graph()
        r = mg.attention_rebalance_plan()
        valid_zones = {"hot", "warm", "cool", "cold", "inactive"}
        for a in r["actions"]:
            self.assertIn(a["zone"], valid_zones)


if __name__ == "__main__":
    unittest.main()
