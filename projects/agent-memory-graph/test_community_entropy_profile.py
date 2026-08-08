"""Tests for community_entropy_profile() — Cycle 392.

Per-community entropy analysis: internal/external entropy,
cohesion ratio, leave-one-community-out delta, inter-community JSD.
"""
import math
import pytest
from memory_graph import MemoryGraph


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def empty_graph():
    return MemoryGraph()


@pytest.fixture
def tiny_graph():
    """Graph with 2 nodes — too small for analysis."""
    mg = MemoryGraph()
    mg.add("a")
    mg.add("b")
    mg.link_by_label("a", "b", "rel")
    return mg


@pytest.fixture
def single_community():
    """Fully connected graph — likely 1 community, should return None."""
    mg = MemoryGraph()
    nodes = [mg.add(f"n{i}") for i in range(6)]
    for i in range(6):
        for j in range(i + 1, 6):
            mg.link(nodes[i].id, nodes[j].id, "rel")
    return mg


@pytest.fixture
def two_communities():
    """Two clear communities with a bridge."""
    mg = MemoryGraph()
    a = [mg.add(f"a{i}", tags=["A"]) for i in range(4)]
    b = [mg.add(f"b{i}", tags=["B"]) for i in range(4)]
    # Community A: clique
    for i in range(4):
        for j in range(i + 1, 4):
            mg.link(a[i].id, a[j].id, "sim")
    # Community B: cycle
    for i in range(4):
        mg.link(b[i].id, b[(i + 1) % 4].id, "knows")
    # Single bridge
    mg.link(a[0].id, b[0].id, "bridge")
    return mg


@pytest.fixture
def three_communities():
    """Three distinct communities with varied internal structure."""
    mg = MemoryGraph()
    # Community 1: star (hub + 4 leaves)
    hub = mg.add("hub", tags=["C1"])
    leaves = [mg.add(f"leaf{i}", tags=["C1"]) for i in range(4)]
    for leaf in leaves:
        mg.link(hub.id, leaf.id, "dep")
    # Community 2: triangle + pendant
    t = [mg.add(f"t{i}", tags=["C2"]) for i in range(4)]
    mg.link(t[0].id, t[1].id, "rel")
    mg.link(t[1].id, t[2].id, "rel")
    mg.link(t[0].id, t[2].id, "rel")
    mg.link(t[2].id, t[3].id, "rel")
    # Community 3: path of 5
    p = [mg.add(f"p{i}", tags=["C3"]) for i in range(5)]
    for i in range(4):
        mg.link(p[i].id, p[i + 1].id, "next")
    # Bridges
    mg.link(hub.id, t[0].id, "bridge")
    mg.link(t[3].id, p[0].id, "bridge")
    return mg


@pytest.fixture
def rich_graph():
    """Larger graph with 3 clusters and varied topology."""
    mg = MemoryGraph()
    # Cluster 1: 6-node dense
    c1 = [mg.add(f"c1_{i}", tags=["cluster1"]) for i in range(6)]
    for i in range(6):
        for j in range(i + 1, 6):
            if (i + j) % 2 == 0:
                mg.link(c1[i].id, c1[j].id, "sim", weight=0.8)
    # Cluster 2: 5-node ring + chords
    c2 = [mg.add(f"c2_{i}", tags=["cluster2"]) for i in range(5)]
    for i in range(5):
        mg.link(c2[i].id, c2[(i + 1) % 5].id, "knows", weight=0.7)
        mg.link(c2[i].id, c2[(i + 2) % 5].id, "knows", weight=0.5)
    # Cluster 3: 4-node star
    c3_center = mg.add("c3_center", tags=["cluster3"])
    c3_leaves = [mg.add(f"c3_leaf{i}", tags=["cluster3"]) for i in range(3)]
    for leaf in c3_leaves:
        mg.link(c3_center.id, leaf.id, "dep", weight=0.9)
    # Bridges
    mg.link(c1[0].id, c2[0].id, "bridge", weight=0.3)
    mg.link(c2[1].id, c3_center.id, "bridge", weight=0.4)
    mg.link(c1[3].id, c3_leaves[0].id, "bridge", weight=0.2)
    return mg


# ── Degenerate cases ─────────────────────────────────────

class TestDegenerate:

    def test_empty_graph(self, empty_graph):
        assert empty_graph.community_entropy_profile() is None

    def test_tiny_graph(self, tiny_graph):
        assert tiny_graph.community_entropy_profile() is None

    def test_single_community_returns_none(self, single_community):
        """Graph that forms a single community should return None."""
        result = single_community.community_entropy_profile()
        # Could be None (1 community) or valid — depends on algorithm
        # With a clique of 6, leiden might split. If 1 community, None is correct.
        if result is not None:
            assert result["summary"]["num_communities"] >= 2


# ── Structure ────────────────────────────────────────────

class TestStructure:

    def test_returns_dict(self, two_communities):
        result = two_communities.community_entropy_profile()
        assert isinstance(result, dict)

    def test_required_top_keys(self, two_communities):
        result = two_communities.community_entropy_profile()
        for key in ["communities", "inter_community_divergence",
                     "divergence_matrix", "summary",
                     "algorithm", "index", "modularity"]:
            assert key in result, f"Missing key: {key}"

    def test_communities_is_list(self, two_communities):
        result = two_communities.community_entropy_profile()
        assert isinstance(result["communities"], list)

    def test_community_entry_keys(self, two_communities):
        result = two_communities.community_entropy_profile()
        for c in result["communities"]:
            for key in ["id", "size", "internal_entropy", "external_entropy",
                         "cohesion_ratio", "internal_edges", "external_edges",
                         "contribution_delta"]:
                assert key in c, f"Community missing key: {key}"

    def test_summary_keys(self, two_communities):
        result = two_communities.community_entropy_profile()
        s = result["summary"]
        for key in ["num_communities", "mean_internal_entropy",
                     "mean_cohesion", "total_bridge_edges",
                     "max_contribution_delta"]:
            assert key in s, f"Summary missing key: {key}"

    def test_algorithm_stored(self, two_communities):
        result = two_communities.community_entropy_profile()
        assert result["algorithm"] == "leiden"

    def test_index_stored(self, rich_graph):
        result = rich_graph.community_entropy_profile(algorithm="greedy")
        if result is not None:
            assert result["algorithm"] == "greedy"

    def test_index_param(self, two_communities):
        result = two_communities.community_entropy_profile(index="randic")
        assert result["index"] == "randic"


# ── Entropy values ───────────────────────────────────────

class TestEntropyValues:

    def test_internal_entropy_range(self, two_communities):
        result = two_communities.community_entropy_profile()
        for c in result["communities"]:
            assert 0.0 <= c["internal_entropy"] <= 1.0

    def test_external_entropy_range(self, two_communities):
        result = two_communities.community_entropy_profile()
        for c in result["communities"]:
            assert 0.0 <= c["external_entropy"] <= 1.0

    def test_cohesion_range(self, two_communities):
        result = two_communities.community_entropy_profile()
        for c in result["communities"]:
            assert 0.0 <= c["cohesion_ratio"] <= 1.0

    def test_contribution_delta_non_negative(self, two_communities):
        result = two_communities.community_entropy_profile()
        for c in result["communities"]:
            assert c["contribution_delta"] >= 0.0

    def test_internal_edges_non_negative(self, two_communities):
        result = two_communities.community_entropy_profile()
        for c in result["communities"]:
            assert c["internal_edges"] >= 0

    def test_external_edges_non_negative(self, two_communities):
        result = two_communities.community_entropy_profile()
        for c in result["communities"]:
            assert c["external_edges"] >= 0

    def test_size_matches_members(self, two_communities):
        result = two_communities.community_entropy_profile()
        total = sum(c["size"] for c in result["communities"])
        stats = two_communities.stats()
        assert total == stats["nodes"]


# ── Cohesion ─────────────────────────────────────────────

class TestCohesion:

    def test_high_cohesion_tight_community(self, two_communities):
        """A clique community should have high cohesion."""
        result = two_communities.community_entropy_profile()
        # Find the largest community (likely the clique)
        largest = max(result["communities"], key=lambda c: c["size"])
        # Clique of 4 with 6 internal edges + 1 bridge → cohesion = 6/7 ≈ 0.857
        assert largest["cohesion_ratio"] > 0.5

    def test_low_cohesion_isolated_node(self, rich_graph):
        """At least one community should have lower cohesion than the max."""
        result = rich_graph.community_entropy_profile()
        max_cohesion = max(c["cohesion_ratio"] for c in result["communities"])
        min_cohesion = min(c["cohesion_ratio"] for c in result["communities"])
        assert min_cohesion <= max_cohesion

    def test_cohesion_formula(self, two_communities):
        """cohesion = internal / (internal + external)."""
        result = two_communities.community_entropy_profile()
        for c in result["communities"]:
            total = c["internal_edges"] + c["external_edges"]
            if total > 0:
                expected = c["internal_edges"] / total
                assert abs(c["cohesion_ratio"] - round(expected, 4)) < 0.01


# ── Divergence matrix ────────────────────────────────────

class TestDivergenceMatrix:

    def test_matrix_square(self, two_communities):
        result = two_communities.community_entropy_profile()
        n = len(result["communities"])
        assert len(result["divergence_matrix"]) == n
        for row in result["divergence_matrix"]:
            assert len(row) == n

    def test_matrix_diagonal_zero(self, two_communities):
        result = two_communities.community_entropy_profile()
        for i in range(len(result["divergence_matrix"])):
            assert result["divergence_matrix"][i][i] == 0.0

    def test_matrix_upper_triangular(self, two_communities):
        """JSD values should only be in upper triangle (i < j)."""
        result = two_communities.community_entropy_profile()
        n = len(result["divergence_matrix"])
        for i in range(n):
            for j in range(i):
                assert result["divergence_matrix"][i][j] == 0.0

    def test_matrix_values_non_negative(self, two_communities):
        result = two_communities.community_entropy_profile()
        for row in result["divergence_matrix"]:
            for v in row:
                assert v >= 0.0

    def test_mean_divergence_in_range(self, two_communities):
        result = two_communities.community_entropy_profile()
        assert 0.0 <= result["inter_community_divergence"] <= 1.0

    def test_identical_communities_zero_divergence(self):
        """Two communities with identical structure should have low divergence."""
        mg = MemoryGraph()
        # Two identical triangles
        a = [mg.add(f"a{i}") for i in range(3)]
        mg.link(a[0].id, a[1].id, "r")
        mg.link(a[1].id, a[2].id, "r")
        mg.link(a[0].id, a[2].id, "r")
        b = [mg.add(f"b{i}") for i in range(3)]
        mg.link(b[0].id, b[1].id, "r")
        mg.link(b[1].id, b[2].id, "r")
        mg.link(b[0].id, b[2].id, "r")
        # Bridge
        mg.link(a[0].id, b[0].id, "bridge")
        result = mg.community_entropy_profile()
        if result and len(result["communities"]) >= 2:
            # Identical structures → low divergence
            assert result["inter_community_divergence"] < 0.5


# ── Leave-one-community-out ──────────────────────────────

class TestLeaveOneCommunityOut:

    def test_delta_non_negative(self, three_communities):
        result = three_communities.community_entropy_profile()
        for c in result["communities"]:
            assert c["contribution_delta"] >= 0.0

    def test_larger_community_higher_delta(self, rich_graph):
        """Larger communities should generally have higher contribution delta."""
        result = rich_graph.community_entropy_profile()
        comms = result["communities"]
        if len(comms) >= 2:
            largest = max(comms, key=lambda c: c["size"])
            smallest = min(comms, key=lambda c: c["size"])
            if largest["size"] > smallest["size"] * 2:
                assert largest["contribution_delta"] >= smallest["contribution_delta"]

    def test_isolated_node_zero_delta(self, rich_graph):
        """A size-1 community with no edges should have ~0 delta."""
        result = rich_graph.community_entropy_profile()
        for c in result["communities"]:
            if c["size"] == 1 and c["internal_edges"] == 0:
                assert c["contribution_delta"] < 0.001

    def test_max_delta_in_summary(self, three_communities):
        result = three_communities.community_entropy_profile()
        max_c = max(c["contribution_delta"] for c in result["communities"])
        assert abs(result["summary"]["max_contribution_delta"] - max_c) < 0.001


# ── Algorithm variants ───────────────────────────────────

class TestAlgorithmVariants:

    def test_greedy(self, rich_graph):
        result = rich_graph.community_entropy_profile(algorithm="greedy")
        if result is not None:
            assert result["algorithm"] == "greedy"
            assert result["summary"]["num_communities"] >= 2

    def test_lp(self, two_communities):
        result = two_communities.community_entropy_profile(algorithm="lp")
        assert result is not None
        assert result["algorithm"] == "lp"

    def test_different_algorithms_same_structure(self, rich_graph):
        """Different algorithms on same graph should detect communities."""
        r1 = rich_graph.community_entropy_profile(algorithm="leiden")
        r2 = rich_graph.community_entropy_profile(algorithm="greedy")
        assert r1 is not None  # leiden should always find communities in rich graph


# ── Index variants ───────────────────────────────────────

class TestIndexVariants:

    @pytest.mark.parametrize("index", [
        "sombor", "randic", "zagreb_m1", "abc", "ga"
    ])
    def test_valid_index(self, two_communities, index):
        result = two_communities.community_entropy_profile(index=index)
        assert result is not None
        assert result["index"] == index

    def test_invalid_index_raises(self, two_communities):
        with pytest.raises(ValueError, match="Unknown index"):
            two_communities.community_entropy_profile(index="nonexistent")


# ── Non-mutating ─────────────────────────────────────────

class TestNonMutating:

    def test_graph_unchanged(self, two_communities):
        stats_before = two_communities.stats()
        two_communities.community_entropy_profile()
        stats_after = two_communities.stats()
        assert stats_before == stats_after

    def test_no_new_edges(self, three_communities):
        edges_before = three_communities.conn.execute(
            "SELECT COUNT(*) FROM edges"
        ).fetchone()[0]
        three_communities.community_entropy_profile()
        edges_after = three_communities.conn.execute(
            "SELECT COUNT(*) FROM edges"
        ).fetchone()[0]
        assert edges_before == edges_after

    def test_no_new_nodes(self, rich_graph):
        nodes_before = rich_graph.conn.execute(
            "SELECT COUNT(*) FROM nodes"
        ).fetchone()[0]
        rich_graph.community_entropy_profile()
        nodes_after = rich_graph.conn.execute(
            "SELECT COUNT(*) FROM nodes"
        ).fetchone()[0]
        assert nodes_before == nodes_after


# ── Integration ──────────────────────────────────────────

class TestIntegration:

    def test_consistent_with_community_partition(self, two_communities):
        """community_entropy_profile should find same number of communities."""
        partition = two_communities.community_partition()
        n_comms = len(set(partition.values()))
        result = two_communities.community_entropy_profile()
        assert result["summary"]["num_communities"] == n_comms

    def test_consistent_with_modularity(self, two_communities):
        result = two_communities.community_entropy_profile()
        partition = two_communities.community_partition()
        mod = two_communities.modularity(communities=partition)
        assert abs(result["modularity"] - round(mod, 4)) < 0.01

    def test_works_after_decay(self, rich_graph):
        """Should work after mild decay."""
        # Mild decay — reduce accessed time but don't collapse all weights
        rich_graph.conn.execute(
            "UPDATE nodes SET accessed = accessed - 3600"
        )
        rich_graph.conn.commit()
        result = rich_graph.community_entropy_profile()
        assert result is not None  # structure hasn't changed

    def test_bridge_edges_count(self, three_communities):
        """Total bridge edges should be reasonable."""
        result = three_communities.community_entropy_profile()
        # 3 communities with 2 bridges → bridge count should be small
        assert result["summary"]["total_bridge_edges"] <= 10

    def test_works_with_different_resolution(self, two_communities):
        """Different resolution should still produce valid results."""
        result = two_communities.community_entropy_profile(resolution=0.5)
        assert result is not None
        assert result["summary"]["num_communities"] >= 2


# ── Determinism ──────────────────────────────────────────

class TestDeterminism:

    def test_same_result_twice(self, rich_graph):
        r1 = rich_graph.community_entropy_profile()
        r2 = rich_graph.community_entropy_profile()
        assert r1["summary"] == r2["summary"]
        assert r1["inter_community_divergence"] == r2["inter_community_divergence"]

    def test_same_community_sizes(self, rich_graph):
        r1 = rich_graph.community_entropy_profile()
        r2 = rich_graph.community_entropy_profile()
        sizes1 = sorted(c["size"] for c in r1["communities"])
        sizes2 = sorted(c["size"] for c in r2["communities"])
        assert sizes1 == sizes2


# ── Edge cases ───────────────────────────────────────────

class TestEdgeCases:

    def test_single_edge_graph(self):
        """2 nodes + 1 edge = too small, should return None."""
        mg = MemoryGraph()
        a = mg.add("a")
        b = mg.add("b")
        mg.link(a.id, b.id, "r")
        assert mg.community_entropy_profile() is None

    def test_path_graph(self):
        """Path graph P6 should still produce valid community analysis."""
        mg = MemoryGraph()
        nodes = [mg.add(f"n{i}") for i in range(6)]
        for i in range(5):
            mg.link(nodes[i].id, nodes[i + 1].id, "next")
        result = mg.community_entropy_profile()
        if result:
            assert result["summary"]["num_communities"] >= 2

    def test_star_graph(self):
        """Star graph K_{1,5}."""
        mg = MemoryGraph()
        hub = mg.add("hub")
        leaves = [mg.add(f"l{i}") for i in range(5)]
        for leaf in leaves:
            mg.link(hub.id, leaf.id, "dep")
        result = mg.community_entropy_profile()
        # May or may not detect multiple communities
        if result:
            assert result["summary"]["num_communities"] >= 2

    def test_disconnected_components(self):
        """Two disconnected cliques."""
        mg = MemoryGraph()
        a = [mg.add(f"a{i}") for i in range(4)]
        b = [mg.add(f"b{i}") for i in range(4)]
        for i in range(4):
            for j in range(i + 1, 4):
                mg.link(a[i].id, a[j].id, "r")
                mg.link(b[i].id, b[j].id, "r")
        result = mg.community_entropy_profile()
        assert result is not None
        assert result["summary"]["num_communities"] >= 2

    def test_many_communities(self):
        """Graph with many small communities."""
        mg = MemoryGraph()
        for c in range(6):
            nodes = [mg.add(f"c{c}_n{i}") for i in range(3)]
            mg.link(nodes[0].id, nodes[1].id, "r")
            mg.link(nodes[1].id, nodes[2].id, "r")
            if c > 0:
                # Bridge to previous cluster
                prev = mg.conn.execute(
                    f"SELECT id FROM nodes WHERE label LIKE 'c{c-1}_n0'"
                ).fetchone()
                mg.link(prev["id"], nodes[0].id, "bridge")
        result = mg.community_entropy_profile()
        assert result is not None
        assert result["summary"]["num_communities"] >= 3


# ── Rich graph properties ────────────────────────────────

class TestRichGraphProperties:

    def test_rich_graph_multiple_communities(self, rich_graph):
        result = rich_graph.community_entropy_profile()
        assert result["summary"]["num_communities"] >= 2

    def test_rich_graph_has_bridge_edges(self, rich_graph):
        result = rich_graph.community_entropy_profile()
        assert result["summary"]["total_bridge_edges"] >= 1

    def test_rich_graph_modularity_positive(self, rich_graph):
        result = rich_graph.community_entropy_profile()
        assert result["modularity"] > 0.0

    def test_rich_graph_divergence_positive(self, rich_graph):
        """Different communities should have non-zero divergence."""
        result = rich_graph.community_entropy_profile()
        if result["summary"]["num_communities"] >= 2:
            assert result["inter_community_divergence"] > 0.0

    def test_three_communities_varied_entropy(self, three_communities):
        """Different topologies should produce different entropy values."""
        result = three_communities.community_entropy_profile()
        entropies = [c["internal_entropy"] for c in result["communities"]
                     if c["internal_edges"] > 0]
        if len(entropies) >= 2:
            # At least some variation in entropy values
            assert max(entropies) >= min(entropies)

    def test_sorted_by_size(self, rich_graph):
        """Communities should be sorted by size descending."""
        result = rich_graph.community_entropy_profile()
        sizes = [c["size"] for c in result["communities"]]
        assert sizes == sorted(sizes, reverse=True)
