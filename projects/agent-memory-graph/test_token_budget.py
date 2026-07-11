"""Tests for token-budgeted context generation.

Quantitative retrieval: pack nodes into a token budget without LLM calls.
Mandol-inspired deterministic context generation.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def populated_graph():
    mg = MemoryGraph()
    nodes = []
    for i in range(20):
        n = mg.add(f"Topic_{i} detailed content", "concept", {"index": i})
        nodes.append(n)
    # Link some nodes
    for i in range(19):
        mg.link(nodes[i].id, nodes[i+1].id, "rel")
    return mg, nodes


# =====================================================================
# Basic functionality
# =====================================================================

class TestRetrieveTokenBudgetedBasic:

    def test_returns_dict(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=512)
        assert isinstance(result, dict)
        for key in ("context", "nodes", "token_count", "char_count",
                     "truncated", "budget"):
            assert key in result

    def test_empty_query_returns_empty(self):
        mg = MemoryGraph()
        result = mg.retrieve_token_budgeted("nonexistent", token_budget=512)
        assert result["context"] == ""
        assert result["nodes"] == []
        assert result["token_count"] == 0
        assert result["truncated"] is False

    def test_budget_reflected_in_output(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=256)
        assert result["budget"] == 256

    def test_token_count_within_budget(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=100)
        # Allow small overflow for last line
        assert result["token_count"] <= 110

    def test_char_count_proportional_to_tokens(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=200)
        if result["token_count"] > 0:
            ratio = result["char_count"] / result["token_count"]
            assert 3.0 < ratio < 5.0  # ~4 chars/token


# =====================================================================
# Budget control
# =====================================================================

class TestBudgetControl:

    def test_smaller_budget_fewer_nodes(self, populated_graph):
        mg, _ = populated_graph
        large = mg.retrieve_token_budgeted("Topic", token_budget=2000)
        small = mg.retrieve_token_budgeted("Topic", token_budget=100)
        assert len(small["nodes"]) <= len(large["nodes"])

    def test_truncated_when_budget_exceeded(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=50)
        # With 20 matching nodes and tiny budget, should truncate
        assert result["truncated"] is True

    def test_not_truncated_with_large_budget(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=10000)
        # Large budget should fit all results
        assert result["truncated"] is False

    def test_custom_chars_per_token(self, populated_graph):
        mg, _ = populated_graph
        result4 = mg.retrieve_token_budgeted("Topic", token_budget=200, chars_per_token=4.0)
        result6 = mg.retrieve_token_budgeted("Topic", token_budget=200, chars_per_token=6.0)
        # Higher chars/token = larger char budget = more content
        assert result6["char_count"] >= result4["char_count"] - 10


# =====================================================================
# Context format
# =====================================================================

class TestContextFormat:

    def test_context_contains_labels(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=1000)
        assert "Topic_0" in result["context"] or "Topic_" in result["context"]

    def test_context_contains_kinds(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=1000)
        assert "[concept]" in result["context"]

    def test_context_contains_scores(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=1000)
        assert "score=" in result["context"]

    def test_nodes_have_required_fields(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=1000)
        for node in result["nodes"]:
            assert "node_id" in node
            assert "label" in node
            assert "kind" in node
            assert "score" in node
            assert "line" in node

    def test_context_lines_match_nodes(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=1000)
        for node in result["nodes"]:
            assert node["line"] in result["context"]


# =====================================================================
# Edge cases
# =====================================================================

class TestTokenBudgetedEdgeCases:

    def test_zero_budget(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=0)
        assert result["nodes"] == []
        assert result["context"] == ""

    def test_very_small_budget(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=5)
        # At most 1 node should fit (or 0)
        assert len(result["nodes"]) <= 1

    def test_single_node_graph(self):
        mg = MemoryGraph()
        mg.add("Lonely node", "test")
        result = mg.retrieve_token_budgeted("Lonely", token_budget=100)
        assert len(result["nodes"]) == 1
        assert result["truncated"] is False

    def test_no_matching_nodes(self):
        mg = MemoryGraph()
        mg.add("Python", "skill")
        result = mg.retrieve_token_budgeted("Rust", token_budget=1000)
        assert result["nodes"] == []
        assert result["context"] == ""


# =====================================================================
# Ordering
# =====================================================================

class TestTokenBudgetedOrdering:

    def test_nodes_sorted_by_score_desc(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=1000)
        scores = [n["score"] for n in result["nodes"]]
        assert scores == sorted(scores, reverse=True)

    def test_higher_score_nodes_included_first(self, populated_graph):
        mg, _ = populated_graph
        # Use two different budget sizes
        small = mg.retrieve_token_budgeted("Topic", token_budget=80)
        large = mg.retrieve_token_budgeted("Topic", token_budget=2000)
        if small["nodes"] and large["nodes"]:
            # The first node in small should be the top-ranked
            assert small["nodes"][0]["node_id"] == large["nodes"][0]["node_id"]


# =====================================================================
# Integration
# =====================================================================

class TestTokenBudgetedIntegration:

    def test_works_with_rerank(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted(
            "Topic", token_budget=500, rerank=True, rerank_centrality="degree"
        )
        assert len(result["nodes"]) > 0

    def test_works_without_rerank(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=500, rerank=False)
        assert isinstance(result["nodes"], list)

    def test_repeated_calls_deterministic(self, populated_graph):
        mg, _ = populated_graph
        r1 = mg.retrieve_token_budgeted("Topic", token_budget=300)
        r2 = mg.retrieve_token_budgeted("Topic", token_budget=300)
        assert r1["token_count"] == r2["token_count"]
        assert len(r1["nodes"]) == len(r2["nodes"])

    def test_context_is_valid_string(self, populated_graph):
        mg, _ = populated_graph
        result = mg.retrieve_token_budgeted("Topic", token_budget=500)
        assert isinstance(result["context"], str)
        assert len(result["context"]) > 0
