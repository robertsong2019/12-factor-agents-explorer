"""Tests for query() adaptive routing — GraphRAG/LightRAG-inspired mode selection."""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def populated_graph():
    """Graph with enough nodes for meaningful routing decisions."""
    mg = MemoryGraph()

    # People
    alice = mg.add("Alice", "person", {"role": "engineer"})
    bob = mg.add("Bob", "person", {"role": "manager"})
    carol = mg.add("Carol", "person", {"role": "designer"})
    dave = mg.add("Dave", "person", {"role": "devops"})
    eve = mg.add("Eve", "person", {"role": "security"})
    frank = mg.add("Frank", "person", {"role": "qa"})
    grace = mg.add("Grace", "person", {"role": "data"})
    heidi = mg.add("Heidi", "person", {"role": "product"})

    # Projects
    proj1 = mg.add("Project Alpha", "project", {"status": "active"})
    proj2 = mg.add("Project Beta", "project", {"status": "planning"})
    proj3 = mg.add("Project Gamma", "project", {"status": "done"})

    # Concepts
    arch = mg.add("Microservices Architecture", "concept", {"area": "backend"})
    auth = mg.add("OAuth 2.0", "concept", {"area": "security"})
    ml = mg.add("Machine Learning Pipeline", "concept", {"area": "data"})

    # Connections
    mg.link(alice.id, proj1.id, "works_on")
    mg.link(bob.id, proj1.id, "manages")
    mg.link(carol.id, proj2.id, "designs")
    mg.link(dave.id, proj1.id, "deploys")
    mg.link(eve.id, proj3.id, "audits")
    mg.link(frank.id, proj1.id, "tests")
    mg.link(grace.id, proj3.id, "analyzes")
    mg.link(heidi.id, proj2.id, "owns")
    mg.link(proj1.id, arch.id, "uses")
    mg.link(proj3.id, auth.id, "implements")
    mg.link(proj3.id, ml.id, "leverages")
    mg.link(alice.id, bob.id, "reports_to")
    mg.link(eve.id, auth.id, "expert_in")

    return mg


@pytest.fixture
def small_graph():
    """Tiny graph (<10 nodes) — router should prefer basic."""
    mg = MemoryGraph()
    mg.add("Node A", "item")
    mg.add("Node B", "item")
    mg.add("Node C", "item")
    return mg


class TestQueryRouter:
    """Tests for the _route_query heuristic router."""

    def test_short_query_routes_to_basic(self, populated_graph):
        mode, reason = populated_graph._route_query("Alice")
        assert mode == "basic"
        assert "short" in reason.lower()

    def test_two_word_query_routes_to_basic(self, populated_graph):
        mode, reason = populated_graph._route_query("Bob role")
        assert mode == "basic"

    def test_three_word_query_still_basic(self, populated_graph):
        mode, _ = populated_graph._route_query("Project Alpha status")
        assert mode == "basic"

    def test_global_keywords_route_to_global(self, populated_graph):
        mode, reason = populated_graph._route_query("Give me an overview of all projects")
        assert mode == "global"
        assert "exploratory" in reason.lower() or "community" in reason.lower()

    def test_summary_keyword_routes_to_global(self, populated_graph):
        mode, _ = populated_graph._route_query("What are the main themes in this memory store?")
        assert mode == "global"

    def test_categories_keyword_routes_to_global(self, populated_graph):
        mode, _ = populated_graph._route_query("What categories of things exist here?")
        assert mode == "global"

    def test_relationship_keywords_route_to_local(self, populated_graph):
        mode, reason = populated_graph._route_query("What is connected to Alice?")
        assert mode == "local"
        assert "relationship" in reason.lower() or "spreading" in reason.lower()

    def test_related_keyword_routes_to_local(self, populated_graph):
        mode, _ = populated_graph._route_query("Which projects are related to each other?")
        assert mode == "local"

    def test_depends_on_routes_to_local(self, populated_graph):
        mode, _ = populated_graph._route_query("What depends on the microservices architecture?")
        assert mode == "local"

    def test_how_question_routes_to_drift(self, populated_graph):
        mode, reason = populated_graph._route_query("How does the security model work across projects?")
        assert mode == "drift"
        assert "complex" in reason.lower() or "drift" in reason.lower()

    def test_why_question_routes_to_drift(self, populated_graph):
        mode, _ = populated_graph._route_query("Why was OAuth chosen for Project Gamma?")
        assert mode == "drift"

    def test_trace_keyword_routes_to_drift(self, populated_graph):
        mode, _ = populated_graph._route_query("Trace the decision chain from requirements to deployment")
        assert mode == "drift"

    def test_multiclause_question_routes_to_drift(self, populated_graph):
        mode, _ = populated_graph._route_query(
            "What is the architecture of Project Alpha and how is it connected to authentication?"
        )
        assert mode == "drift"

    def test_general_query_large_graph_routes_to_hybrid(self, populated_graph):
        mode, _ = populated_graph._route_query("Find information about deployment practices")
        assert mode == "hybrid"

    def test_general_query_small_graph_routes_to_basic(self, small_graph):
        mode, reason = small_graph._route_query("Find information about deployment practices")
        assert mode == "basic"
        assert "small" in reason.lower()


class TestQueryDispatch:
    """Tests for the query() method dispatching to each mode."""

    def test_query_returns_question_and_mode(self, populated_graph):
        result = populated_graph.query("Alice")
        assert result["question"] == "Alice"
        assert result["mode"] == "basic"

    def test_query_auto_detects_mode(self, populated_graph):
        result = populated_graph.query("overview of all projects")
        assert result["mode"] == "global"

    def test_query_explicit_basic_mode(self, populated_graph):
        result = populated_graph.query("overview of everything", mode="basic")
        assert result["mode"] == "basic"

    def test_query_explicit_global_mode(self, populated_graph):
        result = populated_graph.query("Alice", mode="global")
        assert result["mode"] == "global"

    def test_query_explicit_local_mode(self, populated_graph):
        result = populated_graph.query("Alice", mode="local")
        assert result["mode"] == "local"
        assert isinstance(result["results"], list)

    def test_query_explicit_drift_mode(self, populated_graph):
        result = populated_graph.query("architecture", mode="drift")
        assert result["mode"] == "drift"
        assert isinstance(result["results"], list)

    def test_query_explicit_hybrid_mode(self, populated_graph):
        result = populated_graph.query("Project", mode="hybrid")
        assert result["mode"] == "hybrid"

    def test_query_invalid_mode_raises(self, populated_graph):
        with pytest.raises(ValueError, match="Unknown mode"):
            populated_graph.query("test", mode="invalid")

    def test_query_returns_rationale(self, populated_graph):
        result = populated_graph.query("Alice")
        assert "rationale" in result
        assert len(result["rationale"]) > 0

    def test_query_returns_stats(self, populated_graph):
        result = populated_graph.query("Alice")
        assert "stats" in result
        stats = result["stats"]
        assert "elapsed_ms" in stats
        assert "node_count" in stats
        assert "edge_count" in stats
        assert "total_results" in stats

    def test_query_respects_limit(self, populated_graph):
        result = populated_graph.query("Project", mode="basic", limit=2)
        assert len(result["results"]) <= 2

    def test_query_basic_finds_entity(self, populated_graph):
        result = populated_graph.query("Alice")
        labels = [r.get("label", "") for r in result["results"]]
        assert any("Alice" in l for l in labels)

    def test_query_local_returns_activation_scores(self, populated_graph):
        result = populated_graph.query("What is connected to Alice?", mode="local")
        for r in result["results"]:
            assert "score" in r
            assert r["score"] >= 0

    def test_query_detail_enriches_results(self, populated_graph):
        result = populated_graph.query("Alice", detail=True)
        for r in result["results"]:
            if r.get("node_id"):
                assert "data" in r or "weight" in r

    def test_query_empty_graph_returns_empty(self):
        mg = MemoryGraph()
        result = mg.query("anything")
        assert result["results"] == []
        assert result["stats"]["node_count"] == 0

    def test_query_global_returns_community_results(self, populated_graph):
        result = populated_graph.query("overview", mode="global")
        assert isinstance(result["results"], list)

    def test_query_drift_returns_results(self, populated_graph):
        result = populated_graph.query(
            "How does security work and what depends on authentication?",
            mode="drift",
        )
        assert isinstance(result["results"], list)

    def test_query_rationale_changes_with_graph_size(self, small_graph, populated_graph):
        """Same question should route differently based on graph size."""
        small_result = small_graph.query("find information about practices")
        large_result = populated_graph.query("find information about practices")
        # Small → basic, large → hybrid
        assert small_result["mode"] == "basic"
        assert large_result["mode"] == "hybrid"

    def test_query_passes_kwargs_to_drift(self, populated_graph):
        """kwargs like max_iterations should reach drift_search."""
        result = populated_graph.query(
            "how does it work",
            mode="drift",
            max_iterations=1,
        )
        assert result["mode"] == "drift"

    def test_query_results_have_node_id(self, populated_graph):
        result = populated_graph.query("Alice", mode="basic")
        for r in result["results"]:
            assert "node_id" in r

    def test_query_results_have_label(self, populated_graph):
        result = populated_graph.query("Project", mode="basic")
        for r in result["results"]:
            assert "label" in r

    def test_auto_mode_matches_explicit_basic(self, populated_graph):
        """Auto-routing for short query should produce same mode as explicit basic."""
        auto = populated_graph.query("Alice")
        explicit = populated_graph.query("Alice", mode="basic")
        assert auto["mode"] == explicit["mode"]

    def test_query_local_with_no_seeds(self):
        """Local mode with no matching seeds should return empty results."""
        mg = MemoryGraph()
        mg.add("X", "item")
        result = mg.query("nonexistent", mode="local")
        assert result["results"] == []

    def test_query_hybrid_on_small_graph(self, small_graph):
        """Hybrid mode should work even on small graphs."""
        result = small_graph.query("Node", mode="hybrid")
        assert result["mode"] == "hybrid"
        assert isinstance(result["results"], list)
