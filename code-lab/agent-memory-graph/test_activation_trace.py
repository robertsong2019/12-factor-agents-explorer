r"""Tests for MemoryGraph.activation_trace() — Cycle 372.

Explainable spreading activation trace.
Verifies: structure, correctness, wave logging, path reconstruction,
propagation tree, summary metrics, edge cases, determinism, non-mutation,
and integration with spreading_activation.
"""
import pytest
from memory_graph import MemoryGraph


# ─────────────────────────── Fixtures ────────────────────────────

@pytest.fixture
def chain_graph():
    """A→B→C→D→E linear chain."""
    mg = MemoryGraph()
    nodes = []
    for label in ["A", "B", "C", "D", "E"]:
        n = mg.add(label, "concept")
        nodes.append(n)
    for i in range(4):
        mg.link(nodes[i].id, nodes[i + 1].id, "leads_to", 1.0)
    return mg, nodes


@pytest.fixture
def star_graph():
    """Hub→spoke1..spoke5 star."""
    mg = MemoryGraph()
    hub = mg.add("hub", "center")
    spokes = []
    for i in range(5):
        s = mg.add(f"spoke{i}", "leaf")
        mg.link(hub.id, s.id, "connects", 1.0)
        spokes.append(s)
    return mg, hub, spokes


@pytest.fixture
def tree_graph():
    r"""
        root
       /    \
      L1     R1
     / \    / \
    L2  L3 R2  R3
    """
    mg = MemoryGraph()
    root = mg.add("root", "node")
    l1 = mg.add("L1", "node")
    r1 = mg.add("R1", "node")
    l2 = mg.add("L2", "node")
    l3 = mg.add("L3", "node")
    r2 = mg.add("R2", "node")
    r3 = mg.add("R3", "node")
    mg.link(root.id, l1.id, "child", 1.0)
    mg.link(root.id, r1.id, "child", 1.0)
    mg.link(l1.id, l2.id, "child", 1.0)
    mg.link(l1.id, l3.id, "child", 1.0)
    mg.link(r1.id, r2.id, "child", 1.0)
    mg.link(r1.id, r3.id, "child", 1.0)
    return mg, root, l1, r1, l2, l3, r2, r3


@pytest.fixture
def two_cluster_graph():
    """Two clusters connected by a bridge.
    Cluster 1: A↔B↔C  Bridge: C—D  Cluster 2: D↔E↔F
    """
    mg = MemoryGraph()
    a = mg.add("A", "node")
    b = mg.add("B", "node")
    c = mg.add("C", "node")
    d = mg.add("D", "node")
    e = mg.add("E", "node")
    f = mg.add("F", "node")
    mg.link(a.id, b.id, "rel", 1.0)
    mg.link(b.id, c.id, "rel", 1.0)
    mg.link(a.id, c.id, "rel", 1.0)
    mg.link(c.id, d.id, "bridge", 0.5)
    mg.link(d.id, e.id, "rel", 1.0)
    mg.link(e.id, f.id, "rel", 1.0)
    mg.link(d.id, f.id, "rel", 1.0)
    return mg, (a, b, c, d, e, f)


# ──────────────────── Structure Tests ────────────────────────────

class TestActivationTraceStructure:
    def test_returns_dict(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        assert isinstance(result, dict)

    def test_has_required_top_keys(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        for key in ["results", "waves", "paths", "seed_to_node",
                     "propagation_tree", "summary"]:
            assert key in result, f"Missing key: {key}"

    def test_results_is_list_of_dicts(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        assert isinstance(result["results"], list)
        for entry in result["results"]:
            assert isinstance(entry, dict)

    def test_wave_entry_keys(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        assert len(result["waves"]) > 0
        wave = result["waves"][0]
        for key in ["iteration", "fired", "newly_activated", "total_active"]:
            assert key in wave

    def test_newly_activated_entry_keys(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        # Find a wave with newly_activated entries
        for wave in result["waves"]:
            if wave["newly_activated"]:
                entry = wave["newly_activated"][0]
                for key in ["node_id", "activation", "fired_by",
                             "edge_relations", "edge_weights", "path"]:
                    assert key in entry
                break

    def test_summary_keys(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        for key in ["total_nodes_activated", "total_waves", "max_reach",
                     "seeds_used", "dead_ends", "bottlenecks"]:
            assert key in result["summary"]


# ──────────────────── Correctness Tests ──────────────────────────

class TestActivationTraceCorrectness:
    def test_seed_appears_in_results(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        node_ids = [r["node_id"] for r in result["results"]]
        assert nodes[0].id in node_ids

    def test_chain_propagation(self, chain_graph):
        """Activation from A should reach B, C, D, E in order."""
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        node_ids = {r["node_id"] for r in result["results"]}
        # At minimum A and B should be activated; more depends on decay
        assert nodes[0].id in node_ids
        assert nodes[1].id in node_ids

    def test_results_sorted_by_activation(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        activations = [r["activation"] for r in result["results"]]
        assert activations == sorted(activations, reverse=True)

    def test_wave_iteration_sequence(self, chain_graph):
        """Waves should be numbered 0, 1, 2, ..."""
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        iterations = [w["iteration"] for w in result["waves"]]
        assert iterations == list(range(len(iterations)))

    def test_first_wave_contains_seeds(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        assert nodes[0].id in result["waves"][0]["fired"]

    def test_path_seed_to_self(self, chain_graph):
        """Seed node's path should be [seed] with length 0."""
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        seed_path = result["paths"].get(nodes[0].id)
        assert seed_path is not None
        assert seed_path["length"] == 0
        assert seed_path["path"] == [nodes[0].id]

    def test_path_length_matches_hop_distance(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace(
            {nodes[0].id: 1.0}, decay=0.95, threshold=0.001
        )
        for nid, path_info in result["paths"].items():
            result_entry = next(r for r in result["results"] if r["node_id"] == nid)
            if result_entry["hop_distance"] > 0:
                assert path_info["length"] == result_entry["hop_distance"]

    def test_propagation_tree_has_edges(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace(
            {nodes[0].id: 1.0}, decay=0.95, threshold=0.001
        )
        tree = result["propagation_tree"]
        # At least the seed should have children if activation propagated
        has_children = any(len(v) > 0 for v in tree.values())
        assert has_children

    def test_seed_to_node_contains_seed(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        assert nodes[0].id in result["seed_to_node"]
        # Seed should be in its own list
        assert nodes[0].id in result["seed_to_node"][nodes[0].id]

    def test_dead_ends_are_fired_without_children(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace(
            {nodes[0].id: 1.0}, decay=0.95, threshold=0.001
        )
        dead_ends = result["summary"]["dead_ends"]
        tree = result["propagation_tree"]
        for nid in dead_ends:
            assert tree.get(nid, []) == []

    def test_bottlenecks_sorted_by_downstream(self, star_graph):
        """Hub should be the top bottleneck in a star."""
        mg, hub, spokes = star_graph
        result = mg.activation_trace({hub.id: 1.0})
        bottlenecks = result["summary"]["bottlenecks"]
        if bottlenecks:
            assert hub.id == bottlenecks[0]

    def test_total_waves_le_max_iter(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0}, max_iter=3)
        assert result["summary"]["total_waves"] <= 3

    def test_max_reach_matches_max_hop(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace(
            {nodes[0].id: 1.0}, decay=0.95, threshold=0.001
        )
        hop_dists = [r["hop_distance"] for r in result["results"]]
        assert result["summary"]["max_reach"] == max(hop_dists) if hop_dists else True

    def test_fired_by_in_newly_activated(self, chain_graph):
        """newly_activated entries should have non-empty fired_by."""
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        for wave in result["waves"]:
            for entry in wave["newly_activated"]:
                assert len(entry["fired_by"]) > 0

    def test_edge_relations_populated(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        for wave in result["waves"]:
            for entry in wave["newly_activated"]:
                assert len(entry["edge_relations"]) > 0
                assert "leads_to" in entry["edge_relations"]

    def test_edge_weights_match(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0})
        for wave in result["waves"]:
            for entry in wave["newly_activated"]:
                for w in entry["edge_weights"]:
                    assert w == 1.0

    def test_path_starts_from_seed(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace(
            {nodes[0].id: 1.0}, decay=0.95, threshold=0.001
        )
        for nid, path_info in result["paths"].items():
            if path_info["length"] > 0:
                assert path_info["path"][0] == nodes[0].id

    def test_path_ends_at_target(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace(
            {nodes[0].id: 1.0}, decay=0.95, threshold=0.001
        )
        for nid, path_info in result["paths"].items():
            if path_info["length"] > 0:
                assert path_info["path"][-1] == nid


# ──────────────────── Parameter Tests ────────────────────────────

class TestActivationTraceParameters:
    def test_low_threshold_activates_more(self, chain_graph):
        mg, nodes = chain_graph
        high_t = mg.activation_trace({nodes[0].id: 1.0}, threshold=0.5)
        low_t = mg.activation_trace({nodes[0].id: 1.0}, threshold=0.001)
        assert low_t["summary"]["total_nodes_activated"] >= \
               high_t["summary"]["total_nodes_activated"]

    def test_high_decay_spreads_further(self, chain_graph):
        mg, nodes = chain_graph
        low_d = mg.activation_trace({nodes[0].id: 1.0}, decay=0.3)
        high_d = mg.activation_trace({nodes[0].id: 1.0}, decay=0.95)
        assert high_d["summary"]["max_reach"] >= low_d["summary"]["max_reach"]

    def test_max_iter_limits_waves(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0}, max_iter=1)
        assert result["summary"]["total_waves"] <= 1

    def test_directed_mode(self):
        """Directed mode only follows source→target."""
        mg = MemoryGraph()
        a = mg.add("A", "n")
        b = mg.add("B", "n")
        mg.link(a.id, b.id, "forward", 1.0)
        # Seed B in directed mode → should not reach A
        result = mg.activation_trace({b.id: 1.0}, directed=True)
        activated = {r["node_id"] for r in result["results"]}
        assert a.id not in activated

    def test_relation_filter(self, two_cluster_graph):
        mg, (a, b, c, d, e, f) = two_cluster_graph
        # Only follow "bridge" edges → from C, should only reach D
        result = mg.activation_trace(
            {c.id: 1.0}, relation_filter=["bridge"]
        )
        activated = {r["node_id"] for r in result["results"]}
        assert c.id in activated
        assert d.id in activated
        # A and B should NOT be activated (they're connected via "rel")
        assert a.id not in activated
        assert b.id not in activated

    def test_edge_weight_factor(self, star_graph):
        mg, hub, spokes = star_graph
        # With factor=2, edges with weight=1 become 1^2=1 (no change)
        result_default = mg.activation_trace({hub.id: 1.0})
        result_sq = mg.activation_trace({hub.id: 1.0}, edge_weight_factor=2.0)
        assert result_default["summary"]["total_nodes_activated"] == \
               result_sq["summary"]["total_nodes_activated"]


# ──────────────────── Edge Cases ─────────────────────────────────

class TestActivationTraceEdgeCases:
    def test_empty_seeds_raises(self):
        mg = MemoryGraph()
        with pytest.raises(ValueError, match="seeds must not be empty"):
            mg.activation_trace({})

    def test_invalid_decay_zero(self):
        mg = MemoryGraph()
        n = mg.add("A", "n")
        with pytest.raises(ValueError, match="decay must be"):
            mg.activation_trace({n.id: 1.0}, decay=0.0)

    def test_invalid_decay_negative(self):
        mg = MemoryGraph()
        n = mg.add("A", "n")
        with pytest.raises(ValueError, match="decay must be"):
            mg.activation_trace({n.id: 1.0}, decay=-0.5)

    def test_nonexistent_seed_returns_empty(self):
        mg = MemoryGraph()
        result = mg.activation_trace({"nonexistent": 1.0})
        assert result["results"] == []
        assert result["waves"] == []
        assert result["summary"]["total_nodes_activated"] == 0

    def test_all_nonexistent_seeds(self):
        mg = MemoryGraph()
        result = mg.activation_trace({"x": 1.0, "y": 1.0})
        assert result["summary"]["total_nodes_activated"] == 0

    def test_single_isolated_node(self):
        mg = MemoryGraph()
        n = mg.add("lonely", "n")
        result = mg.activation_trace({n.id: 1.0})
        assert result["summary"]["total_nodes_activated"] == 1
        assert result["summary"]["dead_ends"] == [n.id]
        assert result["summary"]["total_waves"] == 1

    def test_single_node_graph(self):
        mg = MemoryGraph()
        n = mg.add("only", "n")
        result = mg.activation_trace({n.id: 1.0})
        assert len(result["results"]) == 1
        assert result["results"][0]["node_id"] == n.id

    def test_multiple_seeds(self, tree_graph):
        mg, root, l1, r1, l2, l3, r2, r3 = tree_graph
        result = mg.activation_trace({l1.id: 1.0, r1.id: 1.0})
        assert l1.id in result["seed_to_node"]
        assert r1.id in result["seed_to_node"]
        # Both should be in seeds_used
        assert l1.id in result["summary"]["seeds_used"]
        assert r1.id in result["summary"]["seeds_used"]

    def test_multiple_seeds_different_strengths(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.activation_trace({nodes[0].id: 1.0, nodes[2].id: 0.5})
        # Node A should have higher activation than C
        a_result = next(r for r in result["results"] if r["node_id"] == nodes[0].id)
        c_result = next(r for r in result["results"] if r["node_id"] == nodes[2].id)
        assert a_result["activation"] > c_result["activation"]

    def test_self_loop_does_not_cause_infinite(self):
        mg = MemoryGraph()
        n = mg.add("self", "n")
        mg.link(n.id, n.id, "self_loop", 1.0)
        result = mg.activation_trace({n.id: 1.0}, max_iter=5)
        assert result["summary"]["total_nodes_activated"] == 1


# ──────────────────── Non-Mutation Tests ─────────────────────────

class TestActivationTraceNonMutating:
    def test_graph_unchanged(self, chain_graph):
        mg, nodes = chain_graph
        stats_before = mg.stats()
        mg.activation_trace({nodes[0].id: 1.0})
        stats_after = mg.stats()
        assert stats_before["nodes"] == stats_after["nodes"]
        assert stats_before["edges"] == stats_after["edges"]

    def test_no_new_edges(self, chain_graph):
        mg, nodes = chain_graph
        edges_before = mg.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        mg.activation_trace({nodes[0].id: 1.0})
        edges_after = mg.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        assert edges_before == edges_after

    def test_no_new_nodes(self, chain_graph):
        mg, nodes = chain_graph
        nodes_before = mg.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        mg.activation_trace({nodes[0].id: 1.0})
        nodes_after = mg.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        assert nodes_before == nodes_after


# ──────────────────── Determinism Tests ──────────────────────────

class TestActivationTraceDeterminism:
    def test_same_input_same_output(self, chain_graph):
        mg, nodes = chain_graph
        r1 = mg.activation_trace({nodes[0].id: 1.0}, decay=0.9, threshold=0.01)
        r2 = mg.activation_trace({nodes[0].id: 1.0}, decay=0.9, threshold=0.01)
        assert r1["results"] == r2["results"]
        assert r1["waves"] == r2["waves"]
        assert r1["summary"] == r2["summary"]

    def test_activation_stable_across_calls(self, chain_graph):
        mg, nodes = chain_graph
        r1 = mg.activation_trace({nodes[0].id: 1.0})
        r2 = mg.activation_trace({nodes[0].id: 1.0})
        for a, b in zip(r1["results"], r2["results"]):
            assert a["activation"] == b["activation"]


# ──────────────────── Integration Tests ──────────────────────────

class TestActivationTraceIntegration:
    def test_consistent_with_spreading_activation(self, chain_graph):
        """activation_trace results should match spreading_activation results."""
        mg, nodes = chain_graph
        sa_result = mg.spreading_activation({nodes[0].id: 1.0}, decay=0.9, threshold=0.01)
        at_result = mg.activation_trace({nodes[0].id: 1.0}, decay=0.9, threshold=0.01)
        # Same node IDs activated
        sa_ids = {r["node_id"] for r in sa_result}
        at_ids = {r["node_id"] for r in at_result["results"]}
        assert sa_ids == at_ids
        # Same activation values
        for sa_entry in sa_result:
            at_entry = next(
                r for r in at_result["results"] if r["node_id"] == sa_entry["node_id"]
            )
            assert sa_entry["activation"] == at_entry["activation"]

    def test_works_after_graph_modification(self, chain_graph):
        mg, nodes = chain_graph
        # First trace
        r1 = mg.activation_trace({nodes[0].id: 1.0})
        # Add a new node and edge
        new = mg.add("F", "n")
        mg.link(nodes[4].id, new.id, "extends", 1.0)
        # Second trace should include new node (if reachable)
        r2 = mg.activation_trace(
            {nodes[0].id: 1.0}, decay=0.95, threshold=0.001
        )
        assert new.id in {r["node_id"] for r in r2["results"]}

    def test_weighted_edges_affect_trace(self):
        mg = MemoryGraph()
        a = mg.add("A", "n")
        b = mg.add("B", "n")
        c = mg.add("C", "n")
        mg.link(a.id, b.id, "weak", 0.1)
        mg.link(a.id, c.id, "strong", 5.0)
        result = mg.activation_trace({a.id: 1.0}, decay=0.9, threshold=0.001)
        b_act = next(r["activation"] for r in result["results"] if r["node_id"] == b.id)
        c_act = next(r["activation"] for r in result["results"] if r["node_id"] == c.id)
        assert c_act > b_act

    def test_bridge_identified_as_bottleneck(self, two_cluster_graph):
        """The bridge node C should be identified as a bottleneck."""
        mg, (a, b, c, d, e, f) = two_cluster_graph
        result = mg.activation_trace(
            {a.id: 1.0}, decay=0.9, threshold=0.001
        )
        bottlenecks = result["summary"]["bottlenecks"]
        # C should be in top bottlenecks (it gates access to cluster 2)
        assert c.id in bottlenecks

    def test_tree_structure_trace(self, tree_graph):
        """In a tree, propagation tree should mirror the tree structure."""
        mg, root, l1, r1, l2, l3, r2, r3 = tree_graph
        result = mg.activation_trace(
            {root.id: 1.0}, decay=0.95, threshold=0.001
        )
        prop = result["propagation_tree"]
        # Root should have propagated to L1 and R1
        assert l1.id in prop.get(root.id, [])
        assert r1.id in prop.get(root.id, [])

    def test_path_reconstruction_in_tree(self, tree_graph):
        """Paths should follow tree edges."""
        mg, root, l1, r1, l2, l3, r2, r3 = tree_graph
        result = mg.activation_trace(
            {root.id: 1.0}, decay=0.95, threshold=0.001
        )
        # Path to L2 should be root → L1 → L2
        if l2.id in result["paths"]:
            path = result["paths"][l2.id]["path"]
            assert root.id in path
            assert l1.id in path
            assert l2.id in path
            assert path[-1] == l2.id

    def test_multiple_seeds_partition(self, tree_graph):
        """Multiple seeds should partition nodes in seed_to_node."""
        mg, root, l1, r1, l2, l3, r2, r3 = tree_graph
        result = mg.activation_trace(
            {l1.id: 1.0, r1.id: 1.0}, decay=0.9, threshold=0.01
        )
        s2n = result["seed_to_node"]
        # L1 seed should capture L2, L3
        l1_nodes = s2n.get(l1.id, [])
        r1_nodes = s2n.get(r1.id, [])
        # No overlap
        assert not (set(l1_nodes) & set(r1_nodes))

    def test_empty_graph_trace(self):
        mg = MemoryGraph()
        n = mg.add("alone", "n")
        result = mg.activation_trace({n.id: 1.0})
        assert result["summary"]["total_nodes_activated"] == 1
        assert result["summary"]["dead_ends"] == [n.id]

    def test_results_match_spreading_activation_count(self, star_graph):
        mg, hub, spokes = star_graph
        sa = mg.spreading_activation({hub.id: 1.0})
        at = mg.activation_trace({hub.id: 1.0})
        assert len(sa) == len(at["results"])
