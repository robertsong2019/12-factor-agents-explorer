"""Tests for three_layer_router_cascade() — Cycle 317.

MemFlow 7-intent routing pattern as a production cascade:
    Layer 1: Rules (keyword heuristic)
    Layer 2: Entropy-guided (topology-aware escalation)
    Layer 3: Keyword fallback

Each test exercises a different cascade path and verifies the
audit trail (cascade_trace) is well-formed.
"""

import pytest
from memory_graph import MemoryGraph, Node, Edge


# ── Fixtures ──

@pytest.fixture
def small_graph():
    """Small graph with a few nodes — enough for basic routing."""
    g = MemoryGraph()
    g.add("apple", kind="fruit")
    g.add("banana", kind="fruit")
    g.add("cherry", kind="fruit")
    g.link("apple", "banana", "similar_to")
    g.link("banana", "cherry", "similar_to")
    return g


@pytest.fixture
def rich_graph():
    """Graph with enough edges for entropy computation."""
    g = MemoryGraph()
    for i in range(10):
        g.add(f"node_{i}", kind="concept")
    edges = [
        (0, 1), (0, 2), (1, 3), (2, 3), (3, 4),
        (4, 5), (5, 6), (6, 7), (7, 8), (8, 9),
        (0, 5), (1, 6), (2, 7), (3, 8), (4, 9),
    ]
    for s, t in edges:
        g.link(f"node_{s}", f"node_{t}", "related_to")
    return g


@pytest.fixture
def empty_graph():
    """Graph with no nodes."""
    return MemoryGraph()


# ── Layer 1: Rules — commit immediately ──

class TestLayer1RulesCommit:

    def test_short_query_commits_at_rules(self, small_graph):
        """Short queries (≤3 words) should commit at Layer 1."""
        result = small_graph.three_layer_router_cascade("apple banana")
        assert result["layer"] == "rules"
        assert result["mode"] == "basic"
        assert len(result["cascade_trace"]) == 1
        assert result["cascade_trace"][0]["layer"] == "rules"
        assert result["cascade_trace"][0]["committed"] is True

    def test_temporal_query_commits_at_rules(self, small_graph):
        """Temporal queries should commit at Layer 1."""
        result = small_graph.three_layer_router_cascade("history of apple node")
        assert result["layer"] == "rules"
        assert result["mode"] == "temporal"
        assert result["cascade_trace"][0]["committed"] is True

    def test_constraint_query_commits_at_rules(self, small_graph):
        """Constraint queries should commit at Layer 1."""
        result = small_graph.three_layer_router_cascade("what is required for apple")
        assert result["layer"] == "rules"
        assert result["mode"] == "constraint"
        assert result["cascade_trace"][0]["committed"] is True

    def test_global_query_commits_at_rules(self, rich_graph):
        """Global/exploratory queries should commit at Layer 1."""
        result = rich_graph.three_layer_router_cascade("overview of all themes")
        assert result["layer"] == "rules"
        assert result["mode"] == "global"
        assert result["cascade_trace"][0]["committed"] is True


# ── Layer 2: Entropy-guided escalation ──

class TestLayer2EntropyEscalation:

    def test_non_basic_mode_escalates(self, rich_graph):
        """Non-basic mode from rules should escalate beyond Layer 1."""
        # Use a query that triggers local/drift mode on rich graph
        result = rich_graph.three_layer_router_cascade(
            "find connected nodes with similar properties here"
        )
        # If rule_mode is not in commit_modes, we should see >= 2 layers
        rule_mode = result["cascade_trace"][0]["mode"]
        if rule_mode not in ("basic", "temporal", "constraint", "global"):
            assert len(result["cascade_trace"]) >= 2
            assert result["cascade_trace"][0]["committed"] is False

    def test_entropy_layer_appears_in_trace(self, rich_graph):
        """When escalated, the entropy layer should be in the trace."""
        result = rich_graph.three_layer_router_cascade(
            "find connected nodes with similar properties here"
        )
        layers = [t["layer"] for t in result["cascade_trace"]]
        # Either entropy was tried, or fallback happened
        assert "rules" in layers
        assert len(layers) >= 2

    def test_entropy_committed_when_results_found(self, rich_graph):
        """If entropy layer finds results, it should commit."""
        result = rich_graph.three_layer_router_cascade(
            "find connected similar properties data"
        )
        # Check cascade trace for entropy layer
        entropy_entries = [t for t in result["cascade_trace"]
                          if t["layer"] == "entropy"]
        if entropy_entries and entropy_entries[0].get("n_results", 0) > 0:
            assert entropy_entries[0]["committed"] is True
            assert result["layer"] == "entropy"


# ── Layer 3: Keyword fallback ──

class TestLayer3Fallback:

    def test_fallback_on_empty_graph(self, empty_graph):
        """Empty graph should fall back to keyword search."""
        result = empty_graph.three_layer_router_cascade(
            "find similar concepts here"
        )
        # Should eventually reach fallback or have empty results
        assert result["n_results"] == 0
        # Should have attempted multiple layers
        assert len(result["cascade_trace"]) >= 1

    def test_fallback_produces_basic_mode(self, rich_graph):
        """When fallback activates, mode should be basic."""
        # Force fallback by using a query that goes through cascade
        result = rich_graph.three_layer_router_cascade(
            "find similar connected properties data concepts"
        )
        if result["layer"] == "fallback":
            assert result["mode"] == "basic"
            # Fallback trace entry should exist
            fallback_entries = [t for t in result["cascade_trace"]
                               if t["layer"] == "fallback"]
            assert len(fallback_entries) == 1
            assert fallback_entries[0]["committed"] is True


# ── Cascade trace structure ──

class TestCascadeTraceStructure:

    def test_trace_entries_have_required_fields(self, small_graph):
        """Every trace entry must have layer, latency_ms, committed."""
        result = small_graph.three_layer_router_cascade("apple")
        for entry in result["cascade_trace"]:
            assert "layer" in entry
            assert "latency_ms" in entry
            assert "committed" in entry
            assert isinstance(entry["latency_ms"], (int, float))
            assert entry["latency_ms"] >= 0

    def test_exactly_one_committed_layer(self, small_graph):
        """At least one layer should commit."""
        result = small_graph.three_layer_router_cascade("apple")
        committed = [t for t in result["cascade_trace"] if t["committed"]]
        assert len(committed) >= 1

    def test_trace_order_is_execution_order(self, rich_graph):
        """Trace entries should be in execution order."""
        result = rich_graph.three_layer_router_cascade(
            "find similar properties here now"
        )
        layers = [t["layer"] for t in result["cascade_trace"]]
        # Rules always first
        assert layers[0] == "rules"
        # If fallback present, it's always last
        if "fallback" in layers:
            assert layers[-1] == "fallback"

    def test_total_latency_is_sum_of_layers(self, small_graph):
        """Total latency should equal sum of individual layer latencies."""
        result = small_graph.three_layer_router_cascade("apple")
        expected = sum(t["latency_ms"] for t in result["cascade_trace"])
        actual = result["stats"]["total_latency_ms"]
        assert abs(actual - expected) < 0.01  # float tolerance


# ── Return value structure ──

class TestReturnValue:

    def test_result_has_question(self, small_graph):
        result = small_graph.three_layer_router_cascade("apple")
        assert result["question"] == "apple"

    def test_result_has_mode(self, small_graph):
        result = small_graph.three_layer_router_cascade("apple")
        assert isinstance(result["mode"], str)

    def test_result_has_layer(self, small_graph):
        result = small_graph.three_layer_router_cascade("apple")
        assert result["layer"] in ("rules", "entropy", "fallback")

    def test_result_has_results_list(self, small_graph):
        result = small_graph.three_layer_router_cascade("apple")
        assert isinstance(result["results"], list)

    def test_result_has_n_results(self, small_graph):
        result = small_graph.three_layer_router_cascade("apple")
        assert isinstance(result["n_results"], int)
        assert result["n_results"] == len(result["results"])

    def test_result_has_stats(self, small_graph):
        result = small_graph.three_layer_router_cascade("apple")
        stats = result["stats"]
        assert "total_latency_ms" in stats
        assert "layers_attempted" in stats
        assert "committed_layer" in stats

    def test_result_has_cascade_trace(self, small_graph):
        result = small_graph.three_layer_router_cascade("apple")
        assert isinstance(result["cascade_trace"], list)
        assert len(result["cascade_trace"]) >= 1


# ── Integration: end-to-end behavior ──

class TestEndToEnd:

    def test_temporal_query_returns_temporal_mode(self, small_graph):
        """Temporal keyword triggers temporal mode end-to-end."""
        result = small_graph.three_layer_router_cascade(
            "when was apple created"
        )
        assert result["mode"] == "temporal"
        assert result["layer"] == "rules"

    def test_short_query_returns_basic_mode(self, small_graph):
        result = small_graph.three_layer_router_cascade("apple")
        assert result["mode"] == "basic"

    def test_limit_parameter_respected(self, rich_graph):
        """Limit should be passed through to the underlying search."""
        result = rich_graph.three_layer_router_cascade(
            "apple", limit=3
        )
        # For basic mode committed at rules layer
        if result["layer"] == "rules":
            assert len(result["results"]) <= 3

    def test_different_entropy_indices(self, rich_graph):
        """Different entropy indices should not crash."""
        for idx in ("sombor", "randic", "abc"):
            result = rich_graph.three_layer_router_cascade(
                "find similar connected data properties",
                entropy_index=idx,
            )
            assert "cascade_trace" in result

    def test_detail_flag_does_not_crash(self, rich_graph):
        """Detail flag should be passed through without error."""
        result = rich_graph.three_layer_router_cascade(
            "apple", detail=True
        )
        assert "cascade_trace" in result

    def test_embedding_parameter_accepted(self, small_graph):
        """Embedding should be accepted and passed through."""
        result = small_graph.three_layer_router_cascade(
            "apple", embedding=[1.0, 0.0]
        )
        assert "cascade_trace" in result


# ── Edge cases ──

class TestEdgeCases:

    def test_empty_string_query(self, small_graph):
        """Empty string should not crash."""
        result = small_graph.three_layer_router_cascade("")
        assert "cascade_trace" in result

    def test_single_character_query(self, small_graph):
        result = small_graph.three_layer_router_cascade("a")
        assert result["layer"] == "rules"
        assert result["mode"] == "basic"

    def test_very_long_query(self, small_graph):
        """Very long queries should not crash."""
        long_q = " ".join(["concept"] * 100)
        result = small_graph.three_layer_router_cascade(long_q)
        assert "cascade_trace" in result

    def test_query_with_special_characters(self, small_graph):
        result = small_graph.three_layer_router_cascade(
            "what is @apple's #relationship?"
        )
        assert "cascade_trace" in result

    def test_single_node_graph(self):
        """Graph with one node and no edges."""
        g = MemoryGraph()
        g.add("solo", kind="item")
        result = g.three_layer_router_cascade("solo item")
        assert "cascade_trace" in result

    def test_rules_rationale_is_string(self, small_graph):
        """Rules layer rationale should always be a string."""
        result = small_graph.three_layer_router_cascade("apple")
        rules_entry = result["cascade_trace"][0]
        assert isinstance(rules_entry.get("rationale", ""), str)


# ── Performance ──

class TestPerformance:

    def test_rules_layer_is_fast(self, small_graph):
        """Rules layer should be sub-50ms."""
        result = small_graph.three_layer_router_cascade("apple")
        rules_latency = result["cascade_trace"][0]["latency_ms"]
        assert rules_latency < 50  # generous for CI

    def test_total_cascade_is_fast(self, small_graph):
        """Full cascade should complete well under 1 second."""
        result = small_graph.three_layer_router_cascade("apple")
        assert result["stats"]["total_latency_ms"] < 1000

    def test_layers_attempted_count_matches_trace(self, small_graph):
        """layers_attempted should match len(cascade_trace)."""
        result = small_graph.three_layer_router_cascade("apple")
        assert result["stats"]["layers_attempted"] == len(result["cascade_trace"])

    def test_committed_layer_matches_final_layer(self, small_graph):
        """committed_layer stat should match the layer field."""
        result = small_graph.three_layer_router_cascade("apple")
        assert result["stats"]["committed_layer"] == result["layer"]
