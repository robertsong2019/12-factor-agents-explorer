"""Tests for conditioned_traverse() — query-conditioned BFS (Research #040).

Different query intents should traverse different edge types.
Edge traversal weights control which paths are explored and how
nodes are ranked.
"""
import pytest
from memory_graph import MemoryGraph


class TestConditionedTraverse:
    """Query-conditioned BFS with per-relation weights."""

    def setup_method(self):
        """Build a multi-relational graph for testing.

        Layout:
            A --causes--> B --causes--> C
            A --similar_to--> D
            B --depends_on--> E
            D --relates_to--> C
            A --contradicts--> F
        """
        self.mg = MemoryGraph()
        self.a = self.mg.add("Event A", kind="event")
        self.b = self.mg.add("Event B", kind="event")
        self.c = self.mg.add("Event C", kind="event")
        self.d = self.mg.add("Concept D", kind="concept")
        self.e = self.mg.add("Resource E", kind="resource")
        self.f = self.mg.add("Counter F", kind="event")

        self.mg.link(self.a.id, self.b.id, "causes")
        self.mg.link(self.b.id, self.c.id, "causes")
        self.mg.link(self.a.id, self.d.id, "similar_to")
        self.mg.link(self.b.id, self.e.id, "depends_on")
        self.mg.link(self.d.id, self.c.id, "relates_to")
        self.mg.link(self.a.id, self.f.id, "contradicts")

    # --- Basic traversal ---

    def test_returns_empty_for_nonexistent_node(self):
        result = self.mg.conditioned_traverse("nonexistent")
        assert result["visited"] == []
        assert result["stats"]["nodes_visited"] == 0

    def test_entry_node_not_in_visited_list(self):
        """Entry node should be in stats but not in the visited results list."""
        result = self.mg.conditioned_traverse(self.a.id)
        visited_ids = [v["node_id"] for v in result["visited"]]
        assert self.a.id not in visited_ids
        assert result["entry"] == self.a.id

    def test_default_weights_traverses_all_relations(self):
        """With default weights, all relation types should be traversed."""
        result = self.mg.conditioned_traverse(self.a.id)
        assert len(result["visited"]) > 0
        assert "causes" in result["edge_types_used"]
        assert "similar_to" in result["edge_types_used"]

    def test_bfs_visits_reachable_nodes(self):
        """All nodes reachable within max_depth should be visited."""
        result = self.mg.conditioned_traverse(self.a.id, max_depth=5)
        visited_ids = {v["node_id"] for v in result["visited"]}
        assert self.b.id in visited_ids
        assert self.c.id in visited_ids
        assert self.d.id in visited_ids

    # --- Intent-specific traversal ---

    def test_causal_intent_follows_causes_edges(self):
        """A causal intent should prioritize causes/depends_on edges."""
        causal_profile = {
            "causes": 1.0,
            "depends_on": 0.9,
            "similar_to": 0.0,
            "relates_to": 0.0,
            "contradicts": 0.0,
        }
        result = self.mg.conditioned_traverse(
            self.a.id, intent_profile=causal_profile, min_weight=0.5
        )
        visited_ids = {v["node_id"] for v in result["visited"]}

        assert self.b.id in visited_ids  # direct causes edge
        assert self.c.id in visited_ids  # transitive via B
        assert self.d.id not in visited_ids  # similar_to pruned
        assert self.f.id not in visited_ids  # contradicts pruned

    def test_similarity_intent_follows_similar_edges(self):
        """A similarity intent should follow similar_to/relates_to edges."""
        sim_profile = {
            "causes": 0.0,
            "depends_on": 0.0,
            "similar_to": 1.0,
            "relates_to": 0.8,
            "contradicts": 0.0,
        }
        result = self.mg.conditioned_traverse(
            self.a.id, intent_profile=sim_profile, min_weight=0.5
        )
        visited_ids = {v["node_id"] for v in result["visited"]}

        assert self.d.id in visited_ids  # similar_to from A
        assert self.b.id not in visited_ids  # causes pruned

    def test_min_weight_prunes_low_weight_edges(self):
        """min_weight should prune edges below threshold."""
        result = self.mg.conditioned_traverse(
            self.a.id, min_weight=0.5, max_depth=1
        )
        visited_ids = {v["node_id"] for v in result["visited"]}

        # causes (1.0) and depends_on via B would be high enough
        # contradicts (0.1) should be pruned
        assert self.f.id not in visited_ids

    # --- Score and ranking ---

    def test_score_decays_with_depth(self):
        """Deeper nodes should have lower scores than shallower ones."""
        result = self.mg.conditioned_traverse(self.a.id, max_depth=5)
        scores = {v["node_id"]: v["score"] for v in result["visited"]}

        # B is depth 1, C is depth 2 (via causes)
        assert scores[self.b.id] > scores.get(self.c.id, 0)

    def test_results_sorted_by_score(self):
        """Results should be sorted by score descending."""
        result = self.mg.conditioned_traverse(self.a.id)
        scores = [v["score"] for v in result["visited"]]
        assert scores == sorted(scores, reverse=True)

    def test_top_k_limit(self):
        """top_k should limit number of returned nodes."""
        result = self.mg.conditioned_traverse(self.a.id, top_k=2)
        assert len(result["visited"]) <= 2

    # --- Stats ---

    def test_stats_track_traversal(self):
        """Stats should correctly track traversal metrics."""
        result = self.mg.conditioned_traverse(self.a.id, max_depth=3)
        assert result["stats"]["nodes_visited"] > 0
        assert result["stats"]["edges_traversed"] > 0
        assert result["stats"]["max_depth_reached"] > 0

    def test_max_depth_limits_traversal(self):
        """max_depth=0 should not traverse any edges."""
        result = self.mg.conditioned_traverse(self.a.id, max_depth=0)
        assert result["visited"] == []
        assert result["stats"]["edges_traversed"] == 0

    # --- Edge cases ---

    def test_single_node_graph(self):
        """Single node with no edges should return empty visited."""
        mg = MemoryGraph()
        node = mg.add("Lonely")
        result = mg.conditioned_traverse(node.id)
        assert result["visited"] == []

    def test_cycle_handling(self):
        """Circular edges should not cause infinite loop."""
        mg = MemoryGraph()
        n1 = mg.add("N1")
        n2 = mg.add("N2")
        n3 = mg.add("N3")
        mg.link(n1.id, n2.id, "causes")
        mg.link(n2.id, n3.id, "causes")
        mg.link(n3.id, n1.id, "causes")  # cycle

        result = mg.conditioned_traverse(n1.id, max_depth=10, min_weight=0.5)
        visited_ids = {v["node_id"] for v in result["visited"]}
        assert len(visited_ids) == 2  # N2 + N3 (entry N1 excluded from results)
        assert result["stats"]["nodes_visited"] == 3  # includes entry node

    def test_unknown_relation_gets_default_weight(self):
        """Unknown relation types should get a low default weight."""
        mg = MemoryGraph()
        n1 = mg.add("A")
        n2 = mg.add("B")
        mg.link(n1.id, n2.id, "custom_relation")

        result = mg.conditioned_traverse(n1.id)
        visited_ids = {v["node_id"] for v in result["visited"]}
        assert n2.id in visited_ids  # should still traverse
        # Score should be low due to 0.3 default weight
        score = next(v["score"] for v in result["visited"] if v["node_id"] == n2.id)
        assert score < 0.5

    def test_path_is_recorded(self):
        """Each visited node should have a path from entry."""
        result = self.mg.conditioned_traverse(self.a.id, max_depth=3)
        for v in result["visited"]:
            assert len(v["path"]) > 1
            assert v["path"][0] == self.a.id

    def test_intent_profile_extends_defaults(self):
        """Intent profile should extend, not replace, defaults."""
        result_default = self.mg.conditioned_traverse(self.a.id)
        result_custom = self.mg.conditioned_traverse(
            self.a.id, intent_profile={"custom_rel": 0.5}
        )
        # Both should traverse causes edges (from defaults)
        assert "causes" in result_default["edge_types_used"]
        assert "causes" in result_custom["edge_types_used"]

    def test_bidirectional_traversal(self):
        """Traversal should follow outgoing edges only (directed)."""
        mg = MemoryGraph()
        n1 = mg.add("Source")
        n2 = mg.add("Target")
        mg.link(n2.id, n1.id, "causes")  # edge points TO n1

        # Starting from n1, should not reach n2 (edge is incoming)
        result = mg.conditioned_traverse(n1.id, max_depth=3)
        visited_ids = {v["node_id"] for v in result["visited"]}
        assert n2.id not in visited_ids

    def test_score_better_for_high_weight_relations(self):
        """Nodes reached via high-weight edges should score higher."""
        mg = MemoryGraph()
        root = mg.add("Root")
        high = mg.add("HighWeight")
        low = mg.add("LowWeight")
        mg.link(root.id, high.id, "causes")  # weight 1.0
        mg.link(root.id, low.id, "contradicts")  # weight 0.1

        result = mg.conditioned_traverse(root.id, max_depth=1)
        scores = {v["node_id"]: v["score"] for v in result["visited"]}
        assert scores[high.id] > scores[low.id]

    def test_empty_intent_profile_uses_all_defaults(self):
        """Empty intent_profile should use all defaults."""
        result = self.mg.conditioned_traverse(self.a.id, intent_profile={})
        assert len(result["visited"]) > 0

    def test_deep_graph_respects_max_depth(self):
        """Deep chain should respect max_depth."""
        mg = MemoryGraph()
        nodes = [mg.add(f"N{i}") for i in range(10)]
        for i in range(9):
            mg.link(nodes[i].id, nodes[i + 1].id, "causes")

        result = mg.conditioned_traverse(nodes[0].id, max_depth=3)
        assert result["stats"]["max_depth_reached"] <= 3

    def test_no_redundant_visits(self):
        """Each node should appear only once in results."""
        result = self.mg.conditioned_traverse(self.a.id, max_depth=5)
        node_ids = [v["node_id"] for v in result["visited"]]
        assert len(node_ids) == len(set(node_ids))
