"""Tests for spread_activation() — Collins & Loftus (1975) spreading activation.

Covers: basic propagation, decay, threshold filtering, max_hops, edge weight
influence, quarantine exclusion, bidirectional spread, multi-seed fusion,
parameter validation, and determinism.
"""

import pytest
from memory_graph import MemoryGraph


# ── Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def chain_graph():
    """A→B→C→D→E linear chain."""
    mg = MemoryGraph()
    nodes = [mg.add(f"node_{i}", "concept") for i in range(5)]
    for i in range(4):
        mg.link(nodes[i].id, nodes[i + 1].id, "next")
    return mg, nodes


@pytest.fixture
def star_graph():
    """Hub with 5 spokes."""
    mg = MemoryGraph()
    hub = mg.add("hub", "concept")
    spokes = [mg.add(f"spoke_{i}", "concept") for i in range(5)]
    for s in spokes:
        mg.link(hub.id, s.id, "connects")
    return mg, hub, spokes


@pytest.fixture
def weighted_graph():
    """A—(0.9)—B—(0.1)—C: different edge weights."""
    mg = MemoryGraph()
    a = mg.add("A", "concept")
    b = mg.add("B", "concept")
    c = mg.add("C", "concept")
    mg.link(a.id, b.id, "strong", weight=0.9)
    mg.link(b.id, c.id, "weak", weight=0.1)
    return mg, a, b, c


@pytest.fixture
def grid_graph():
    """2x3 grid with uniform connections."""
    mg = MemoryGraph()
    nodes = {}
    for r in range(2):
        for col in range(3):
            nodes[(r, col)] = mg.add(f"n_{r}_{col}", "concept")
    # Horizontal links
    for r in range(2):
        for col in range(2):
            mg.link(nodes[(r, col)].id, nodes[(r, col + 1)].id, "h")
    # Vertical links
    for r in range(1):
        for col in range(3):
            mg.link(nodes[(r, col)].id, nodes[(r + 1, col)].id, "v")
    return mg, nodes


# ── Basic Propagation ───────────────────────────────────────────

class TestBasicPropagation:
    def test_seed_gets_full_activation(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.spread_activation([nodes[0].id])
        assert result[nodes[0].id] == pytest.approx(1.0)

    def test_one_hop_neighbor(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.spread_activation([nodes[0].id], decay_factor=0.5)
        assert nodes[1].id in result
        assert result[nodes[1].id] == pytest.approx(0.5)

    def test_two_hop_neighbor(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.spread_activation([nodes[0].id], decay_factor=0.5)
        assert nodes[2].id in result
        assert result[nodes[2].id] == pytest.approx(0.25)

    def test_three_hop_neighbor(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.spread_activation([nodes[0].id], decay_factor=0.5, max_hops=3)
        assert nodes[3].id in result
        assert result[nodes[3].id] == pytest.approx(0.125)

    def test_activation_decreases_with_distance(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.spread_activation([nodes[0].id], decay_factor=0.7, max_hops=4)
        acts = [result[nodes[i].id] for i in range(5)]
        for i in range(len(acts) - 1):
            assert acts[i] > acts[i + 1]


class TestBidirectionalSpread:
    def test_spreads_in_both_directions(self, chain_graph):
        """Activation from middle node goes both ways."""
        mg, nodes = chain_graph
        result = mg.spread_activation([nodes[2].id], decay_factor=0.5, max_hops=2)
        # Should reach nodes 0, 1, 3, 4
        assert nodes[1].id in result
        assert nodes[3].id in result
        assert nodes[0].id in result  # 2 hops back
        assert nodes[4].id in result  # 2 hops forward

    def test_symmetric_spread(self, chain_graph):
        """Activation from center is symmetric in a chain."""
        mg, nodes = chain_graph
        result = mg.spread_activation([nodes[2].id], decay_factor=0.5, max_hops=1)
        assert result[nodes[1].id] == pytest.approx(result[nodes[3].id])


class TestStarGraph:
    def test_all_spokes_activated(self, star_graph):
        mg, hub, spokes = star_graph
        result = mg.spread_activation([hub.id], decay_factor=0.5)
        for s in spokes:
            assert s.id in result

    def test_spoke_activation_equal(self, star_graph):
        mg, hub, spokes = star_graph
        result = mg.spread_activation([hub.id], decay_factor=0.5)
        values = [result[s.id] for s in spokes]
        assert all(v == pytest.approx(values[0]) for v in values)

    def test_spoke_to_hub(self, star_graph):
        """Activation from a spoke reaches hub and then other spokes."""
        mg, hub, spokes = star_graph
        result = mg.spread_activation([spokes[0].id], decay_factor=0.5, max_hops=2)
        assert hub.id in result
        # Hub activation = 0.5, other spokes = 0.5 * 0.5 = 0.25
        assert result[hub.id] == pytest.approx(0.5)
        for s in spokes[1:]:
            assert s.id in result
            assert result[s.id] == pytest.approx(0.25)


# ── Parameter Tests ─────────────────────────────────────────────

class TestDecayFactor:
    def test_decay_1_no_loss(self, chain_graph):
        """With decay=1.0, activation doesn't decrease per hop (only edge weight)."""
        mg, nodes = chain_graph
        result = mg.spread_activation([nodes[0].id], decay_factor=1.0, max_hops=4)
        # All nodes at ~1.0 (edges have default weight 1.0)
        for n in nodes:
            assert n.id in result
            assert result[n.id] == pytest.approx(1.0, abs=0.01)

    def test_low_decay_stays_local(self, chain_graph):
        """With very low decay, only nearest neighbors get meaningful activation."""
        mg, nodes = chain_graph
        result = mg.spread_activation([nodes[0].id], decay_factor=0.1, threshold=0.05, max_hops=4)
        assert nodes[0].id in result  # seed = 1.0
        assert nodes[1].id in result  # 1.0 * 0.1 = 0.1
        # nodes[2] would be 0.01, below threshold
        assert nodes[2].id not in result

    def test_decay_validation_zero(self):
        mg = MemoryGraph()
        n = mg.add("test", "concept")
        with pytest.raises(ValueError, match="decay_factor"):
            mg.spread_activation([n.id], decay_factor=0.0)

    def test_decay_validation_negative(self):
        mg = MemoryGraph()
        n = mg.add("test", "concept")
        with pytest.raises(ValueError, match="decay_factor"):
            mg.spread_activation([n.id], decay_factor=-0.5)

    def test_decay_validation_over_one(self):
        mg = MemoryGraph()
        n = mg.add("test", "concept")
        with pytest.raises(ValueError, match="decay_factor"):
            mg.spread_activation([n.id], decay_factor=1.5)


class TestThreshold:
    def test_threshold_filters_low_activation(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.spread_activation([nodes[0].id], decay_factor=0.3, threshold=0.2, max_hops=4)
        assert nodes[0].id in result  # 1.0
        assert nodes[1].id in result  # 0.3
        assert nodes[2].id not in result  # 0.09 < 0.2

    def test_threshold_zero_includes_all(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.spread_activation([nodes[0].id], decay_factor=0.3, threshold=0.0, max_hops=4)
        for n in nodes:
            assert n.id in result

    def test_threshold_validation_negative(self):
        mg = MemoryGraph()
        n = mg.add("test", "concept")
        with pytest.raises(ValueError, match="threshold"):
            mg.spread_activation([n.id], threshold=-1)


class TestMaxHops:
    def test_max_hops_1(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.spread_activation([nodes[0].id], decay_factor=0.9, max_hops=1)
        assert nodes[0].id in result
        assert nodes[1].id in result
        assert nodes[2].id not in result

    def test_max_hops_2(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.spread_activation([nodes[0].id], decay_factor=0.9, max_hops=2)
        assert nodes[2].id in result
        assert nodes[3].id not in result

    def test_max_hops_validation_zero(self):
        mg = MemoryGraph()
        n = mg.add("test", "concept")
        with pytest.raises(ValueError, match="max_hops"):
            mg.spread_activation([n.id], max_hops=0)


# ── Edge Weight Tests ───────────────────────────────────────────

class TestEdgeWeights:
    def test_high_weight_propagates_more(self, weighted_graph):
        mg, a, b, c = weighted_graph
        result = mg.spread_activation([a.id], decay_factor=1.0, threshold=0.01, max_hops=2)
        # A→B weight=0.9, so B gets 1.0*1.0*0.9 = 0.9
        assert result[b.id] == pytest.approx(0.9, abs=0.01)
        # B→C weight=0.1, so C gets 0.9*1.0*0.1 = 0.09
        assert result[c.id] == pytest.approx(0.09, abs=0.01)

    def test_disable_edge_weight_factor(self, weighted_graph):
        """With edge_weight_factor=False, all edges treated as weight=1."""
        mg, a, b, c = weighted_graph
        result = mg.spread_activation(
            [a.id], decay_factor=1.0, threshold=0.01, max_hops=2,
            edge_weight_factor=False,
        )
        assert result[b.id] == pytest.approx(1.0)
        assert result[c.id] == pytest.approx(1.0)


# ── Multi-Seed Tests ────────────────────────────────────────────

class TestMultiSeed:
    def test_two_seeds_fuse_activation(self, chain_graph):
        """Activation from two seeds should sum (take max)."""
        mg, nodes = chain_graph
        result = mg.spread_activation(
            [nodes[0].id, nodes[4].id], decay_factor=0.5, max_hops=4, threshold=0.05,
        )
        # nodes[0] seed = 1.0, nodes[4] seed = 1.0
        assert result[nodes[0].id] == pytest.approx(1.0)
        assert result[nodes[4].id] == pytest.approx(1.0)
        # nodes[2] gets activation from both directions: 0.25 each, max = 0.25
        assert nodes[2].id in result

    def test_multi_seed_overlapping(self, star_graph):
        """Two seeds in star graph: hub + spoke0."""
        mg, hub, spokes = star_graph
        result = mg.spread_activation(
            [hub.id, spokes[0].id], decay_factor=0.5, max_hops=2,
        )
        # hub: max(1.0, 0.5) = 1.0
        assert result[hub.id] == pytest.approx(1.0)
        # spokes[0]: max(0.5, 1.0) = 1.0
        assert result[spokes[0].id] == pytest.approx(1.0)

    def test_empty_seeds_raises(self):
        mg = MemoryGraph()
        with pytest.raises(ValueError, match="seed_ids"):
            mg.spread_activation([])


# ── Quarantine Tests ────────────────────────────────────────────

class TestQuarantine:
    def test_quarantined_excluded_by_default(self, chain_graph):
        mg, nodes = chain_graph
        mg.node_quarantine(nodes[2].id)
        result = mg.spread_activation([nodes[0].id], decay_factor=0.5, max_hops=4)
        assert nodes[2].id not in result

    def test_quarantined_included_when_flag_set(self, chain_graph):
        mg, nodes = chain_graph
        mg.node_quarantine(nodes[2].id)
        result = mg.spread_activation(
            [nodes[0].id], decay_factor=0.5, max_hops=4,
            include_quarantined=True,
        )
        assert nodes[2].id in result


# ── Validation & Edge Cases ─────────────────────────────────────

class TestValidation:
    def test_nonexistent_seed_raises_keyerror(self):
        mg = MemoryGraph()
        with pytest.raises(KeyError, match="not found"):
            mg.spread_activation(["nonexistent_id"])

    def test_isolated_node_returns_only_self(self):
        mg = MemoryGraph()
        n = mg.add("isolated", "concept")
        result = mg.spread_activation([n.id])
        assert list(result.keys()) == [n.id]
        assert result[n.id] == pytest.approx(1.0)

    def test_empty_graph_raises_on_seed(self):
        mg = MemoryGraph()
        with pytest.raises(KeyError):
            mg.spread_activation(["any_id"])


# ── Grid / Complex Topology ─────────────────────────────────────

class TestGridTopology:
    def test_grid_reaches_all_nodes(self, grid_graph):
        mg, nodes = grid_graph
        seed = nodes[(0, 0)]
        result = mg.spread_activation(
            [seed.id], decay_factor=0.6, threshold=0.01, max_hops=5,
        )
        # All 6 nodes should be reached
        assert len(result) == 6

    def test_grid_corner_reaches_farthest(self, grid_graph):
        mg, nodes = grid_graph
        seed = nodes[(0, 0)]
        result = mg.spread_activation(
            [seed.id], decay_factor=0.5, threshold=0.01, max_hops=5,
        )
        # (1,2) is 3 hops away
        far = nodes[(1, 2)]
        assert far.id in result

    def test_grid_center_max_activation(self, grid_graph):
        """Corner seed: adjacent nodes have highest activation."""
        mg, nodes = grid_graph
        seed = nodes[(0, 0)]
        result = mg.spread_activation(
            [seed.id], decay_factor=0.5, threshold=0.01, max_hops=5,
        )
        adjacent = [nodes[(0, 1)], nodes[(1, 0)]]
        non_adjacent = [nodes[(0, 2)], nodes[(1, 1)], nodes[(1, 2)]]
        for n in adjacent:
            for nn in non_adjacent:
                assert result[n.id] > result[nn.id]


# ── Determinism ─────────────────────────────────────────────────

class TestDeterminism:
    def test_same_result_on_repeat(self, chain_graph):
        mg, nodes = chain_graph
        r1 = mg.spread_activation([nodes[0].id], decay_factor=0.5, max_hops=4)
        r2 = mg.spread_activation([nodes[0].id], decay_factor=0.5, max_hops=4)
        assert r1 == r2

    def test_result_sorted_by_activation_descending(self, chain_graph):
        mg, nodes = chain_graph
        result = mg.spread_activation([nodes[0].id], decay_factor=0.5, max_hops=4)
        values = list(result.values())
        assert all(values[i] >= values[i + 1] for i in range(len(values) - 1))
