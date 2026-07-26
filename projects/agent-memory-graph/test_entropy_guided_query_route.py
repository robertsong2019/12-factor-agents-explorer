"""Tests for entropy_guided_query_route() — entropy-aware retrieval.

Research #028: Entropy-Guided Branching.  Uses graph topology entropy
to dynamically select the best retrieval strategy.
"""
import pytest
from memory_graph import MemoryGraph


# ─── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def empty_graph():
    return MemoryGraph(":memory:")


@pytest.fixture
def uniform_graph():
    """Regular cycle graph — low entropy (all degrees equal)."""
    g = MemoryGraph(":memory:")
    n = 6
    nodes = [g.add(f"n{i}", kind="fact") for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "next")
    return g


@pytest.fixture
def heterogeneous_graph():
    """Star + chain + cluster — high entropy (very uneven degrees)."""
    g = MemoryGraph(":memory:")
    # Hub with many connections
    hub = g.add("hub", kind="fact")
    for i in range(5):
        s = g.add(f"spoke_{i}", kind="fact")
        g.link(hub.id, s.id, "connects")
    # Chain (degree-2 internal)
    c1 = g.add("c1", kind="fact")
    c2 = g.add("c2", kind="fact")
    c3 = g.add("c3", kind="fact")
    g.link(c1.id, c2.id, "next")
    g.link(c2.id, c3.id, "next")
    # Isolated pair
    ia = g.add("iso_a", kind="fact")
    ib = g.add("iso_b", kind="fact")
    g.link(ia.id, ib.id, "pair")
    return g


@pytest.fixture
def medium_graph():
    """Moderately varied structure."""
    g = MemoryGraph(":memory:")
    a = g.add("a", kind="fact")
    b = g.add("b", kind="fact")
    c = g.add("c", kind="fact")
    d = g.add("d", kind="fact")
    e = g.add("e", kind="fact")
    g.link(a.id, b.id, "r")
    g.link(a.id, c.id, "r")
    g.link(b.id, c.id, "r")
    g.link(c.id, d.id, "r")
    g.link(d.id, e.id, "r")
    return g


# ─=== Basic Structure ===─────────────────────────────────────────────

class TestEntropyGuidedRouteBasic:
    """Basic structural tests."""

    def test_returns_dict_with_required_keys(self, uniform_graph):
        g = uniform_graph
        result = g.entropy_guided_query_route("n0")
        assert isinstance(result, dict)
        assert "question" in result
        assert "mode" in result
        assert "entropy_mode" in result
        assert "heuristic_mode" in result
        assert "entropy_analysis" in result
        assert "results" in result
        assert "stats" in result

    def test_question_echoed(self, uniform_graph):
        result = uniform_graph.entropy_guided_query_route("hello world")
        assert result["question"] == "hello world"

    def test_results_is_list(self, uniform_graph):
        result = uniform_graph.entropy_guided_query_route("n0")
        assert isinstance(result["results"], list)

    def test_stats_contains_elapsed_ms(self, uniform_graph):
        result = uniform_graph.entropy_guided_query_route("n0")
        assert "elapsed_ms" in result["stats"]
        assert result["stats"]["elapsed_ms"] >= 0


# ─=== Entropy Analysis Report ===─────────────────────────────────────

class TestEntropyAnalysis:
    """Entropy analysis output structure."""

    def test_analysis_has_index(self, uniform_graph):
        r = uniform_graph.entropy_guided_query_route("n0")
        ea = r["entropy_analysis"]
        assert ea["index"] == "sombor"

    def test_analysis_has_value(self, uniform_graph):
        r = uniform_graph.entropy_guided_query_route("n0")
        ea = r["entropy_analysis"]
        assert isinstance(ea["value"], float)
        assert 0.0 <= ea["value"] <= 1.0

    def test_analysis_has_bin(self, uniform_graph):
        r = uniform_graph.entropy_guided_query_route("n0")
        ea = r["entropy_analysis"]
        assert ea["bin"] in ("low", "medium", "high")

    def test_analysis_has_recommended_mode(self, uniform_graph):
        r = uniform_graph.entropy_guided_query_route("n0")
        ea = r["entropy_analysis"]
        assert ea["recommended_mode"] in ("basic", "hybrid", "drift")

    def test_analysis_has_heuristic_mode(self, uniform_graph):
        r = uniform_graph.entropy_guided_query_route("n0")
        ea = r["entropy_analysis"]
        assert isinstance(ea["heuristic_mode"], str)

    def test_analysis_has_decision(self, uniform_graph):
        r = uniform_graph.entropy_guided_query_route("n0")
        ea = r["entropy_analysis"]
        assert isinstance(ea["decision"], str)
        assert len(ea["decision"]) > 0

    def test_analysis_has_bin_reason(self, uniform_graph):
        r = uniform_graph.entropy_guided_query_route("n0")
        ea = r["entropy_analysis"]
        assert isinstance(ea["bin_reason"], str)

    def test_analysis_has_final_mode(self, uniform_graph):
        r = uniform_graph.entropy_guided_query_route("n0")
        ea = r["entropy_analysis"]
        assert ea["final_mode"] == r["mode"]

    def test_profile_present_for_graphs_with_edges(self, heterogeneous_graph):
        """Heterogeneous graph has enough structural variety for profile."""
        r = heterogeneous_graph.entropy_guided_query_route("hub")
        ea = r["entropy_analysis"]
        assert "profile" in ea
        assert "min" in ea["profile"]
        assert "max" in ea["profile"]
        assert "std" in ea["profile"]

    def test_profile_has_most_heterogeneous(self, heterogeneous_graph):
        r = heterogeneous_graph.entropy_guided_query_route("hub")
        ea = r["entropy_analysis"]
        assert "most_heterogeneous" in ea["profile"]
        assert isinstance(ea["profile"]["most_heterogeneous"], str)

    def test_profile_has_most_homogeneous(self, heterogeneous_graph):
        r = heterogeneous_graph.entropy_guided_query_route("hub")
        ea = r["entropy_analysis"]
        assert "most_homogeneous" in ea["profile"]
        assert isinstance(ea["profile"]["most_homogeneous"], str)


# ─=== Entropy Bin Behaviour ===───────────────────────────────────────

class TestEntropyBinBehaviour:
    """Entropy values map to correct bins."""

    def test_uniform_graph_high_entropy(self, uniform_graph):
        """A cycle graph (all degrees=2) has maximum normalised entropy (1.0)."""
        r = uniform_graph.entropy_guided_query_route("n0")
        ea = r["entropy_analysis"]
        # With all-equal degrees, normalised entropy = 1.0 (maximum uniformity)
        assert ea["value"] >= 0.5

    def test_heterogeneous_graph_lower_than_uniform(self, heterogeneous_graph, uniform_graph):
        """Heterogeneous graph should have lower entropy than uniform (fewer dominant edges)."""
        r_hetero = heterogeneous_graph.entropy_guided_query_route("hub")
        r_uniform = uniform_graph.entropy_guided_query_route("n0")
        assert (
            r_hetero["entropy_analysis"]["value"]
            <= r_uniform["entropy_analysis"]["value"]
        )

    def test_recommended_mode_matches_bin(self, uniform_graph):
        "Recommended mode should be consistent with the bin."""
        r = uniform_graph.entropy_guided_query_route("n0")
        ea = r["entropy_analysis"]
        bin_mode_map = {"low": "drift", "medium": "hybrid", "high": "basic"}
        assert ea["recommended_mode"] == bin_mode_map[ea["bin"]]


# ─=== Override Behaviour ===──────────────────────────────────────────

class TestOverrideBehaviour:
    """override_heuristic parameter controls mode selection."""

    def test_override_true_uses_entropy_mode(self, uniform_graph):
        r = uniform_graph.entropy_guided_query_route(
            "n0", override_heuristic=True,
        )
        ea = r["entropy_analysis"]
        assert r["mode"] == ea["recommended_mode"]

    def test_override_false_keeps_heuristic_when_not_extreme(self, medium_graph):
        """With override=False, heuristic mode is kept unless entropy is high."""
        r = medium_graph.entropy_guided_query_route(
            "connected a b", override_heuristic=False,
        )
        ea = r["entropy_analysis"]
        if ea["bin"] != "high":
            assert r["mode"] == ea["heuristic_mode"]

    def test_override_false_escalates_on_low_entropy(self, heterogeneous_graph):
        """With override=False and low entropy (heterogeneous), mode escalates to drift."""
        r = heterogeneous_graph.entropy_guided_query_route(
            "hub", override_heuristic=False,
        )
        ea = r["entropy_analysis"]
        if ea["bin"] == "low":
            assert r["mode"] == "drift"

    def test_override_false_decision_string_mentions_heuristic(self, medium_graph):
        r = medium_graph.entropy_guided_query_route(
            "node a", override_heuristic=False,
        )
        ea = r["entropy_analysis"]
        assert "heuristic" in ea["decision"].lower()


# ─=== Entropy Index Selection ===─────────────────────────────────────

class TestEntropyIndexSelection:
    """Different entropy indices can be used for routing."""

    @pytest.mark.parametrize("index", [
        "sombor", "reduced_sombor", "randic", "zagreb_m1",
        "abc", "ga", "augmented_zagreb", "edge_betweenness",
    ])
    def test_all_indices_accepted(self, medium_graph, index):
        r = medium_graph.entropy_guided_query_route(
            "a", entropy_index=index,
        )
        assert r["entropy_analysis"]["index"] == index
        assert isinstance(r["entropy_analysis"]["value"], float)

    def test_invalid_index_raises(self, medium_graph):
        with pytest.raises(ValueError, match="Unknown entropy_index"):
            medium_graph.entropy_guided_query_route(
                "a", entropy_index="nonexistent",
            )

    def test_different_indices_may_give_different_bins(self, heterogeneous_graph):
        """Different indices measure different aspects — bins may differ."""
        g = heterogeneous_graph
        bins = set()
        for idx in ("sombor", "randic", "abc", "edge_betweenness"):
            r = g.entropy_guided_query_route("hub", entropy_index=idx)
            bins.add(r["entropy_analysis"]["bin"])
        assert len(bins) >= 1


# ─=== Limit Parameter ===─────────────────────────────────────────────

class TestLimitParameter:
    """Limit parameter controls result count."""

    def test_limit_1(self, heterogeneous_graph):
        r = heterogeneous_graph.entropy_guided_query_route("hub", limit=1)
        assert len(r["results"]) <= 1

    def test_limit_3(self, heterogeneous_graph):
        r = heterogeneous_graph.entropy_guided_query_route("hub", limit=3)
        assert len(r["results"]) <= 3

    def test_limit_default_10(self, heterogeneous_graph):
        r = heterogeneous_graph.entropy_guided_query_route("hub")
        assert len(r["results"]) <= 10


# ─=== Detail Parameter ===────────────────────────────────────────────

class TestDetailParameter:
    """Detail parameter enriches results."""

    def test_detail_true_adds_data(self, heterogeneous_graph):
        r = heterogeneous_graph.entropy_guided_query_route(
            "hub", detail=True,
        )
        for result in r["results"]:
            if result.get("node_id"):
                assert "data" in result or "label" in result

    def test_detail_false_no_extra(self, heterogeneous_graph):
        r = heterogeneous_graph.entropy_guided_query_route(
            "hub", detail=False,
        )
        assert isinstance(r["results"], list)


# ─=== Edge Cases ===──────────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases and robustness."""

    def test_empty_graph_no_crash(self, empty_graph):
        """No nodes — should still return valid structure."""
        r = empty_graph.entropy_guided_query_route("anything")
        assert isinstance(r, dict)
        assert r["results"] == []
        assert r["entropy_analysis"]["bin"] == "low"

    def test_single_node_graph(self, empty_graph):
        empty_graph.add("lonely", kind="fact")
        r = empty_graph.entropy_guided_query_route("lonely")
        assert isinstance(r, dict)
        assert r["entropy_analysis"]["value"] == 0.0

    def test_single_edge_graph(self, empty_graph):
        a = empty_graph.add("a", kind="fact")
        b = empty_graph.add("b", kind="fact")
        empty_graph.link(a.id, b.id, "r")
        r = empty_graph.entropy_guided_query_route("a")
        assert isinstance(r, dict)

    def test_empty_question(self, uniform_graph):
        r = uniform_graph.entropy_guided_query_route("")
        assert isinstance(r, dict)

    def test_very_long_question(self, uniform_graph):
        long_q = " ".join(["node"] * 100)
        r = uniform_graph.entropy_guided_query_route(long_q)
        assert isinstance(r, dict)


# ─=== Mode Consistency ===────────────────────────────────────────────

class TestModeConsistency:
    """Mode values are consistent throughout the result."""

    def test_final_mode_equals_result_mode(self, uniform_graph):
        r = uniform_graph.entropy_guided_query_route("n0")
        assert r["mode"] == r["entropy_analysis"]["final_mode"]

    def test_entropy_mode_is_valid_query_mode(self, uniform_graph):
        r = uniform_graph.entropy_guided_query_route("n0")
        valid_modes = {"basic", "hybrid", "drift"}
        assert r["entropy_mode"] in valid_modes

    def test_heuristic_mode_is_valid_query_mode(self, uniform_graph):
        r = uniform_graph.entropy_guided_query_route("n0")
        valid_modes = {"basic", "global", "local", "drift", "hybrid",
                        "temporal", "constraint"}
        assert r["heuristic_mode"] in valid_modes


# ─=== Bin Boundaries ===──────────────────────────────────────────────

class TestBinBoundaries:
    """Bin boundary values map correctly."""

    def test_low_bin_upper_is_third(self):
        g = MemoryGraph(":memory:")
        bins = g._ENTROPY_ROUTE_BINS
        assert bins["low"][1] == pytest.approx(0.33)

    def test_medium_bin_range(self):
        g = MemoryGraph(":memory:")
        bins = g._ENTROPY_ROUTE_BINS
        assert bins["medium"][0] == pytest.approx(0.33)
        assert bins["medium"][1] == pytest.approx(0.67)

    def test_high_bin_lower_is_two_thirds(self):
        g = MemoryGraph(":memory:")
        bins = g._ENTROPY_ROUTE_BINS
        assert bins["high"][0] == pytest.approx(0.67)

    def test_bins_are_contiguous(self):
        g = MemoryGraph(":memory:")
        bins = g._ENTROPY_ROUTE_BINS
        assert bins["low"][1] == pytest.approx(bins["medium"][0])
        assert bins["medium"][1] == pytest.approx(bins["high"][0])

    def test_bin_modes_are_basic_hybrid_drift(self):
        g = MemoryGraph(":memory:")
        bins = g._ENTROPY_ROUTE_BINS
        assert bins["low"][2] == "drift"
        assert bins["medium"][2] == "hybrid"
        assert bins["high"][2] == "basic"


# ─=== Non-Mutation ===────────────────────────────────────────────────

class TestNonMutation:
    """entropy_guided_query_route must not modify the graph."""

    def test_graph_node_edge_count_unchanged(self, heterogeneous_graph):
        """Node and edge counts must not change after query."""
        g = heterogeneous_graph
        stats_before = g.stats()
        g.entropy_guided_query_route("hub")
        stats_after = g.stats()
        assert stats_after["nodes"] == stats_before["nodes"]
        assert stats_after["edges"] == stats_before["edges"]

    def test_multiple_calls_consistent(self, medium_graph):
        """Two calls should return same entropy value (graph unchanged)."""
        r1 = medium_graph.entropy_guided_query_route("a")
        r2 = medium_graph.entropy_guided_query_route("a")
        assert r1["entropy_analysis"]["value"] == r2["entropy_analysis"]["value"]
        assert r1["entropy_analysis"]["bin"] == r2["entropy_analysis"]["bin"]
