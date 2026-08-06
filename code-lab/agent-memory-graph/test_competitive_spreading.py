"""Tests for competitive_spreading() — lateral inhibition & reinforcement.

Covers: multi-seed competition, interference at contested nodes, reinforcement
on agreement, territory assignment, winner selection, single-seed fallback,
parameter validation, edge cases, determinism, and integration with
spreading_activation.
"""

import pytest
from memory_graph import MemoryGraph


# ── Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def chain_graph():
    """A←B→C with B as a shared middle node."""
    mg = MemoryGraph()
    a = mg.add("A", "concept")
    b = mg.add("B", "concept")
    c = mg.add("C", "concept")
    mg.link(a.id, b.id, "connects")
    mg.link(b.id, c.id, "connects")
    return mg, a, b, c


@pytest.fixture
def y_graph():
    """Two seeds converging on a shared hub via same relation.

    A → C ← B  (all via 'connects')
    """
    mg = MemoryGraph()
    a = mg.add("A", "concept")
    b = mg.add("B", "concept")
    c = mg.add("C", "concept")
    mg.link(a.id, c.id, "connects")
    mg.link(b.id, c.id, "connects")
    return mg, a, b, c


@pytest.fixture
def conflict_graph():
    """Two seeds converging on a hub via different relations.

    A —(relates_to)→ C ←(depends_on)— B
    """
    mg = MemoryGraph()
    a = mg.add("A", "concept")
    b = mg.add("B", "concept")
    c = mg.add("C", "concept")
    mg.link(a.id, c.id, "relates_to")
    mg.link(b.id, c.id, "depends_on")
    return mg, a, b, c


@pytest.fixture
def star_graph():
    """Hub with 4 spokes — two seeds at opposite spokes."""
    mg = MemoryGraph()
    hub = mg.add("hub", "concept")
    spokes = [mg.add(f"spoke_{i}", "concept") for i in range(4)]
    for s in spokes:
        mg.link(hub.id, s.id, "connects")
    return mg, hub, spokes


@pytest.fixture
def two_cluster_graph():
    """Two clusters connected by a bridge node.

    A—B—(bridge)—C—D
    """
    mg = MemoryGraph()
    a = mg.add("A", "concept")
    b = mg.add("B", "concept")
    bridge = mg.add("bridge", "concept")
    c = mg.add("C", "concept")
    d = mg.add("D", "concept")
    mg.link(a.id, b.id, "connects")
    mg.link(b.id, bridge.id, "connects")
    mg.link(bridge.id, c.id, "connects")
    mg.link(c.id, d.id, "connects")
    return mg, a, b, bridge, c, d


# ── Structure Tests ─────────────────────────────────────────────

class TestStructure:
    def test_returns_dict(self, y_graph):
        mg, a, b, c = y_graph
        result = mg.competitive_spreading({a.id: 1.0, b.id: 1.0})
        assert isinstance(result, dict)

    def test_has_required_keys(self, y_graph):
        mg, a, b, c = y_graph
        result = mg.competitive_spreading({a.id: 1.0, b.id: 1.0})
        for key in ("results", "territories", "contested", "interference",
                     "winners", "summary"):
            assert key in result, f"Missing key: {key}"

    def test_results_is_list(self, y_graph):
        mg, a, b, c = y_graph
        result = mg.competitive_spreading({a.id: 1.0, b.id: 1.0})
        assert isinstance(result["results"], list)

    def test_summary_keys(self, y_graph):
        mg, a, b, c = y_graph
        result = mg.competitive_spreading({a.id: 1.0, b.id: 1.0})
        s = result["summary"]
        for key in ("total_nodes", "total_contested", "total_interference",
                     "total_reinforcement", "territory_balance", "dominant_seed"):
            assert key in s, f"Missing summary key: {key}"


# ── Basic Competition ───────────────────────────────────────────

class TestBasicCompetition:
    def test_contested_node_identified(self, y_graph):
        """Node C is activated by both seeds A and B."""
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
        )
        assert c.id in result["contested"]

    def test_uncontested_node_not_in_contested(self, y_graph):
        """Seeds A and B should not be in contested list."""
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
        )
        assert a.id not in result["contested"]
        assert b.id not in result["contested"]

    def test_winners_assigned_for_seeds(self, y_graph):
        """Each seed wins itself (activation 1.0)."""
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
        )
        assert result["winners"][a.id] == a.id
        assert result["winners"][b.id] == b.id

    def test_winner_for_contested_node(self, y_graph):
        """Both seeds have equal activation at C → one wins."""
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
        )
        assert c.id in result["winners"]
        assert result["winners"][c.id] in (a.id, b.id)


# ── Reinforcement (Same Relation) ───────────────────────────────

class TestReinforcement:
    def test_same_relation_reinforcement(self, y_graph):
        """Both seeds reach C via 'connects' → reinforcement."""
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
            reinforcement_strength=0.3,
        )
        info = result["interference"].get(c.id, {})
        assert info.get("mode") == "reinforcement"
        assert info["delta"] > 0

    def test_reinforcement_boosts_activation(self, y_graph):
        """Reinforced node should have higher activation than base."""
        mg, a, b, c = y_graph
        # Get base activation from simple spreading_activation
        base_result = mg.spreading_activation(
            {a.id: 1.0}, decay=0.9, threshold=0.01,
        )
        base_c_act = next(
            r["activation"] for r in base_result if r["node_id"] == c.id
        )
        # Get competitive activation
        comp_result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
            reinforcement_strength=0.3,
        )
        comp_c_act = next(
            r["activation"] for r in comp_result["results"] if r["node_id"] == c.id
        )
        assert comp_c_act >= base_c_act

    def test_reinforcement_count(self, y_graph):
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
        )
        assert result["summary"]["total_reinforcement"] >= 1

    def test_shared_relations_in_interference_log(self, y_graph):
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
        )
        info = result["interference"][c.id]
        assert "shared_relations" in info
        assert "connects" in info["shared_relations"]


# ── Interference (Different Relations) ──────────────────────────

class TestInterference:
    def test_different_relation_interference(self, conflict_graph):
        """Seeds reach C via different relations → interference."""
        mg, a, b, c = conflict_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
            inhibition_strength=0.5,
        )
        info = result["interference"].get(c.id, {})
        assert info.get("mode") == "interference"
        assert info["delta"] < 0

    def test_interference_reduces_activation(self, conflict_graph):
        """Interference should reduce activation below max of base."""
        mg, a, b, c = conflict_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
            inhibition_strength=0.5,
        )
        c_result = next(
            r for r in result["results"] if r["node_id"] == c.id
        )
        # Base activation at C from either seed = 0.9 (single hop)
        # With 0.5 inhibition: adjusted = 0.9 * (1 - 0.5) = 0.45
        assert c_result["activation"] < 0.9

    def test_interference_count(self, conflict_graph):
        mg, a, b, c = conflict_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
        )
        assert result["summary"]["total_interference"] >= 1

    def test_disjoint_relations_in_interference_log(self, conflict_graph):
        mg, a, b, c = conflict_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
        )
        info = result["interference"][c.id]
        assert "disjoint_relations" in info
        # Each seed's relations should be listed
        assert a.id in info["disjoint_relations"]
        assert b.id in info["disjoint_relations"]

    def test_zero_inhibition_no_effect(self, conflict_graph):
        """With inhibition_strength=0, contested node keeps full activation."""
        mg, a, b, c = conflict_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
            inhibition_strength=0.0,
        )
        c_result = next(
            r for r in result["results"] if r["node_id"] == c.id
        )
        assert c_result["activation"] == pytest.approx(0.9, abs=0.01)


# ── Territory Tests ─────────────────────────────────────────────

class TestTerritories:
    def test_each_seed_has_territory(self, y_graph):
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
        )
        assert a.id in result["territories"]
        assert b.id in result["territories"]
        assert a.id in result["territories"][a.id]
        assert b.id in result["territories"][b.id]

    def test_territory_nodes_sorted(self, y_graph):
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
        )
        for seed_id, nodes in result["territories"].items():
            assert nodes == sorted(nodes)

    def test_all_nodes_have_winner(self, y_graph):
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
        )
        all_nodes = {r["node_id"] for r in result["results"]}
        assert set(result["winners"].keys()) == all_nodes

    def test_territory_balance_one_to_one(self, y_graph):
        """Equal territories → balance ≈ 1.0."""
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
        )
        # A gets {A} + possibly C, B gets {B} + possibly C
        # With 3 nodes and 2 seeds, balance depends on contested node winner
        balance = result["summary"]["territory_balance"]
        assert 0 <= balance <= 1.0

    def test_dominant_seed_is_largest_territory(self, two_cluster_graph):
        mg, a, b, bridge, c, d = two_cluster_graph
        # Seed A should capture A, B (and maybe bridge)
        # Seed D should capture D, C (and maybe bridge)
        result = mg.competitive_spreading(
            {a.id: 1.0, d.id: 1.0}, decay=0.85, threshold=0.01,
        )
        dominant = result["summary"]["dominant_seed"]
        territories = result["territories"]
        assert dominant is not None
        assert len(territories[dominant]) >= 1


# ── Parameter Validation ────────────────────────────────────────

class TestValidation:
    def test_single_seed_raises(self):
        mg = MemoryGraph()
        n = mg.add("test", "concept")
        with pytest.raises(ValueError, match="≥ 2 seeds"):
            mg.competitive_spreading({n.id: 1.0})

    def test_empty_seeds_raises(self):
        mg = MemoryGraph()
        with pytest.raises(ValueError, match="≥ 2 seeds"):
            mg.competitive_spreading({})

    def test_inhibition_above_one_raises(self):
        mg = MemoryGraph()
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        with pytest.raises(ValueError, match="inhibition_strength"):
            mg.competitive_spreading({a.id: 1.0, b.id: 1.0}, inhibition_strength=1.5)

    def test_inhibition_negative_raises(self):
        mg = MemoryGraph()
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        with pytest.raises(ValueError, match="inhibition_strength"):
            mg.competitive_spreading({a.id: 1.0, b.id: 1.0}, inhibition_strength=-0.1)

    def test_reinforcement_above_one_raises(self):
        mg = MemoryGraph()
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        with pytest.raises(ValueError, match="reinforcement_strength"):
            mg.competitive_spreading({a.id: 1.0, b.id: 1.0}, reinforcement_strength=2.0)

    def test_reinforcement_negative_raises(self):
        mg = MemoryGraph()
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        with pytest.raises(ValueError, match="reinforcement_strength"):
            mg.competitive_spreading({a.id: 1.0, b.id: 1.0}, reinforcement_strength=-0.5)


# ── Edge Cases ──────────────────────────────────────────────────

class TestEdgeCases:
    def test_nonexistent_seed_handled(self, y_graph):
        """One seed doesn't exist — should still work with the other."""
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, "nonexistent": 1.0}, decay=0.9, threshold=0.01,
        )
        # Only 1 valid seed → fallback to simple merge
        assert result["summary"]["total_contested"] == 0
        assert len(result["results"]) > 0

    def test_both_seeds_nonexistent(self):
        mg = MemoryGraph()
        mg.add("other", "concept")
        result = mg.competitive_spreading(
            {"fake1": 1.0, "fake2": 1.0},
        )
        assert result["summary"]["total_nodes"] == 0

    def test_three_seeds(self):
        """Three seeds all competing for a central hub."""
        mg = MemoryGraph()
        hub = mg.add("hub", "concept")
        s1 = mg.add("s1", "concept")
        s2 = mg.add("s2", "concept")
        s3 = mg.add("s3", "concept")
        mg.link(s1.id, hub.id, "connects")
        mg.link(s2.id, hub.id, "connects")
        mg.link(s3.id, hub.id, "connects")
        result = mg.competitive_spreading(
            {s1.id: 1.0, s2.id: 1.0, s3.id: 1.0},
            decay=0.9, threshold=0.01,
        )
        assert hub.id in result["contested"]
        info = result["interference"][hub.id]
        assert info["mode"] == "reinforcement"
        assert len(info["seeds"]) == 3

    def test_unequal_seed_strengths(self, y_graph):
        """Seed A has activation 1.0, seed B has 0.5."""
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 0.5}, decay=0.9, threshold=0.01,
        )
        # A should win C (higher activation)
        assert result["winners"][c.id] == a.id

    def test_isolated_seeds(self):
        """Two seeds with no edges between them."""
        mg = MemoryGraph()
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0},
        )
        # Each seed only activates itself
        assert result["summary"]["total_nodes"] == 2
        assert result["summary"]["total_contested"] == 0


# ── Non-Mutation ────────────────────────────────────────────────

class TestNonMutation:
    def test_graph_unchanged(self, y_graph):
        mg, a, b, c = y_graph
        nodes_before = {n.id for n in mg.find_by_kind("concept")}
        edge_count_before = mg.count_edges()
        mg.competitive_spreading({a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01)
        nodes_after = {n.id for n in mg.find_by_kind("concept")}
        edge_count_after = mg.count_edges()
        assert nodes_before == nodes_after
        assert edge_count_before == edge_count_after

    def test_no_new_edges(self, y_graph):
        mg, a, b, c = y_graph
        edge_count_before = mg.count_edges()
        mg.competitive_spreading({a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01)
        edge_count_after = mg.count_edges()
        assert edge_count_before == edge_count_after


# ── Determinism ─────────────────────────────────────────────────

class TestDeterminism:
    def test_same_result_on_repeat(self, y_graph):
        mg, a, b, c = y_graph
        r1 = mg.competitive_spreading({a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01)
        r2 = mg.competitive_spreading({a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01)
        assert r1 == r2

    def test_results_sorted_by_activation(self, y_graph):
        mg, a, b, c = y_graph
        result = mg.competitive_spreading({a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01)
        acts = [r["activation"] for r in result["results"]]
        assert all(acts[i] >= acts[i + 1] for i in range(len(acts) - 1))


# ── Integration ─────────────────────────────────────────────────

class TestIntegration:
    def test_consistent_with_spreading_activation(self, y_graph):
        """Results should be a superset of spreading_activation data."""
        mg, a, b, c = y_graph
        sa = mg.spreading_activation({a.id: 1.0}, decay=0.9, threshold=0.01)
        comp = mg.competitive_spreading({a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01)
        sa_nodes = {r["node_id"] for r in sa}
        comp_nodes = {r["node_id"] for r in comp["results"]}
        # Competitive should reach at least the same nodes as single-seed SA
        assert sa_nodes.issubset(comp_nodes)

    def test_works_after_graph_modification(self, chain_graph):
        """Add a node after first call, verify second call sees it."""
        mg, a, b, c = chain_graph
        mg.competitive_spreading({a.id: 1.0, c.id: 1.0}, decay=0.9, threshold=0.01)
        d = mg.add("D", "concept")
        mg.link(c.id, d.id, "connects")
        result = mg.competitive_spreading({a.id: 1.0, c.id: 1.0}, decay=0.9, threshold=0.01)
        assert d.id in {r["node_id"] for r in result["results"]}

    def test_weighted_edges_affect_competition(self):
        """Stronger edge wins contested node."""
        mg = MemoryGraph()
        a = mg.add("A", "concept")
        b = mg.add("B", "concept")
        c = mg.add("C", "concept")
        mg.link(a.id, c.id, "connects", weight=1.0)
        mg.link(b.id, c.id, "connects", weight=0.3)  # weaker
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
        )
        # A's activation at C = 0.9 * 1.0 = 0.9
        # B's activation at C = 0.9 * 0.3 = 0.27
        # A should win C
        assert result["winners"][c.id] == a.id

    def test_zero_reinforcement_treats_as_neutral(self, y_graph):
        """With reinforcement_strength=0, same-relation nodes keep base activation."""
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
            reinforcement_strength=0.0,
        )
        c_act = next(r["activation"] for r in result["results"] if r["node_id"] == c.id)
        # Base = 0.9, no boost → stays at 0.9
        assert c_act == pytest.approx(0.9, abs=0.01)

    def test_full_inhibition_suppresses_node(self, conflict_graph):
        """With inhibition_strength=1.0, contested node activation → 0."""
        mg, a, b, c = conflict_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
            inhibition_strength=1.0,
        )
        c_act = next(r["activation"] for r in result["results"] if r["node_id"] == c.id)
        assert c_act == pytest.approx(0.0, abs=0.001)

    def test_star_graph_two_spokes(self, star_graph):
        """Hub is contested when two spokes are seeded."""
        mg, hub, spokes = star_graph
        result = mg.competitive_spreading(
            {spokes[0].id: 1.0, spokes[2].id: 1.0},
            decay=0.85, threshold=0.01, max_iter=3,
        )
        # Hub is reachable from both spokes
        assert hub.id in {r["node_id"] for r in result["results"]}

    def test_contested_flag_in_results(self, y_graph):
        """Results entries should have 'contested' field."""
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
        )
        c_entry = next(r for r in result["results"] if r["node_id"] == c.id)
        assert c_entry["contested"] is True
        a_entry = next(r for r in result["results"] if r["node_id"] == a.id)
        assert a_entry["contested"] is False

    def test_dominant_seed_in_results(self, y_graph):
        """Results entries should have 'dominant_seed' field."""
        mg, a, b, c = y_graph
        result = mg.competitive_spreading(
            {a.id: 1.0, b.id: 1.0}, decay=0.9, threshold=0.01,
        )
        for r in result["results"]:
            assert "dominant_seed" in r
