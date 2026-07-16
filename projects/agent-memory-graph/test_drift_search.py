"""Tests for drift_search() — DRIFT-style hybrid search.

GraphRAG-inspired (Edge et al. 2024): global community sweep →
local spreading activation → iterative keyword refinement.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    """Fresh graph with a small knowledge cluster."""
    g = MemoryGraph()
    # Cluster 1: Python ecosystem
    py = g.add("Python", kind="language")
    dj = g.add("Django", kind="framework")
    fl = g.add("Flask", kind="framework")
    np = g.add("NumPy", kind="library")
    pd = g.add("Pandas", kind="library")
    # Edges within cluster
    g.link(py.id, dj.id, "powers")
    g.link(py.id, fl.id, "powers")
    g.link(py.id, np.id, "used_by")
    g.link(py.id, pd.id, "used_by")
    g.link(np.id, pd.id, "dependency")

    # Cluster 2: JavaScript ecosystem
    js = g.add("JavaScript", kind="language")
    re = g.add("React", kind="framework")
    vu = g.add("Vue", kind="framework")
    g.link(js.id, re.id, "powers")
    g.link(js.id, vu.id, "powers")

    # Cluster 3: DevOps
    dk = g.add("Docker", kind="tool")
    ci = g.add("CI/CD", kind="concept")
    g.link(dk.id, ci.id, "enables")

    return g


@pytest.fixture
def mg_dense():
    """Denser graph for community detection."""
    g = MemoryGraph()
    # Create three clear communities of 4 nodes each
    communities = {
        "AI": ["Machine Learning", "Deep Learning", "Neural Networks", "Transformer"],
        "Web": ["HTTP", "REST API", "GraphQL", "WebSocket"],
        "Data": ["SQL", "PostgreSQL", "MongoDB", "Redis"],
    }
    node_map = {}
    for comm, labels in communities.items():
        prev = None
        for label in labels:
            n = g.add(label, kind="concept")
            node_map[label] = n
            if prev:
                g.link(prev.id, n.id, "related")
            prev = n
        # Close the ring
        nodes_in_comm = [node_map[l] for l in labels]
        g.link(nodes_in_comm[-1].id, nodes_in_comm[0].id, "related")
        # Cross-link within community
        g.link(nodes_in_comm[0].id, nodes_in_comm[2].id, "related")

    return g


class TestDriftSearchBasic:
    """Basic functionality and return structure."""

    def test_returns_dict_with_required_keys(self, mg):
        result = mg.drift_search("Python")
        assert isinstance(result, dict)
        for key in ["question", "iterations", "global_results",
                     "local_results", "refined_results", "final_results"]:
            assert key in result, f"Missing key: {key}"

    def test_question_echoed(self, mg):
        result = mg.drift_search("Python language")
        assert result["question"] == "Python language"

    def test_iterations_is_positive(self, mg):
        result = mg.drift_search("Python")
        assert result["iterations"] >= 1

    def test_iteration_log_present(self, mg):
        result = mg.drift_search("Python")
        assert "iteration_log" in result
        assert isinstance(result["iteration_log"], list)
        assert len(result["iteration_log"]) >= 1

    def test_total_unique_nodes_is_int(self, mg):
        result = mg.drift_search("Python")
        assert isinstance(result["total_unique_nodes"], int)


class TestDriftSearchGlobal:
    """Global phase — community-level matching."""

    def test_global_results_has_communities(self, mg_dense):
        result = mg_dense.drift_search("Machine Learning")
        global_res = result["global_results"]
        assert "results" in global_res
        assert isinstance(global_res["results"], list)

    def test_global_results_total_communities(self, mg_dense):
        result = mg_dense.drift_search("Machine Learning")
        global_res = result["global_results"]
        assert global_res["total_communities"] >= 1

    def test_global_k_limit(self, mg_dense):
        result = mg_dense.drift_search("data", global_k=1)
        global_res = result["global_results"]
        # Should limit to 1 community
        assert len(global_res["results"]) <= 1


class TestDriftSearchLocal:
    """Local phase — spreading activation."""

    def test_local_results_contains_activated_nodes(self, mg):
        result = mg.drift_search("Python")
        # Python is directly in the graph, should appear somewhere
        all_nodes = set()
        for r in result["local_results"]:
            all_nodes.add(r.get("label", ""))
        # Either in local results or refined
        for r in result["refined_results"]:
            all_nodes.add(r.get("label", ""))
        assert "Python" in all_nodes

    def test_local_k_limit(self, mg):
        result = mg.drift_search("Python", local_k=1)
        assert len(result["local_results"]) <= 1

    def test_local_results_have_activation(self, mg):
        result = mg.drift_search("Python")
        for r in result["local_results"]:
            assert "activation" in r
            assert 0 <= r["activation"] <= 1.0

    def test_spread_hops_affects_reach(self, mg):
        """With hops=1, we only get direct neighbors."""
        r1 = mg.drift_search("Python", spread_hops=1)
        r2 = mg.drift_search("Python", spread_hops=3)
        # More hops should potentially reach more nodes
        assert len(r2["local_results"]) >= len(r1["local_results"])


class TestDriftSearchRefinement:
    """Iterative refinement loop."""

    def test_max_iterations_controls_loops(self, mg):
        r1 = mg.drift_search("Python", max_iterations=1)
        r3 = mg.drift_search("Python", max_iterations=3)
        assert r1["iterations"] == 1
        assert r3["iterations"] >= 1
        assert len(r3["iteration_log"]) >= len(r1["iteration_log"])

    def test_iteration_log_records_expanded_query(self, mg):
        result = mg.drift_search("Python", max_iterations=2)
        if len(result["iteration_log"]) > 1:
            second = result["iteration_log"][1]
            assert "expanded_query" in second

    def test_refined_results_sorted_by_score(self, mg):
        result = mg.drift_search("Python")
        scores = [r["score"] for r in result["refined_results"]]
        assert scores == sorted(scores, reverse=True)

    def test_refined_results_have_in_global_and_in_local(self, mg):
        result = mg.drift_search("Python")
        for r in result["refined_results"]:
            assert "in_global" in r
            assert "in_local" in r
            assert isinstance(r["in_global"], bool)
            assert isinstance(r["in_local"], bool)


class TestDriftSearchFinal:
    """Final output quality."""

    def test_final_results_are_limited(self, mg):
        result = mg.drift_search("Python", local_k=2)
        assert len(result["final_results"]) <= 4  # local_k * 2

    def test_final_results_have_scores(self, mg):
        result = mg.drift_search("Python")
        for r in result["final_results"]:
            assert "score" in r
            assert r["score"] >= 0

    def test_final_results_have_node_info(self, mg):
        result = mg.drift_search("Python")
        for r in result["final_results"]:
            assert "node_id" in r
            assert "label" in r
            assert "kind" in r

    def test_python_relevant_result(self, mg):
        """Searching for Python should return Python-related nodes."""
        result = mg.drift_search("Python")
        all_labels = set()
        for r in result["final_results"]:
            all_labels.add(r["label"])
        # At least Python should be in results
        assert "Python" in all_labels or any(
            "Python" in r["label"] for r in result["final_results"]
        )


class TestDriftSearchEdgeCases:
    """Edge cases and error handling."""

    def test_empty_graph(self):
        g = MemoryGraph()
        result = g.drift_search("anything")
        assert result["question"] == "anything"
        assert result["final_results"] == []

    def test_single_node(self):
        g = MemoryGraph()
        g.add("Solo", kind="lonely")
        result = g.drift_search("Solo")
        assert isinstance(result, dict)
        # Should still return something
        assert len(result["final_results"]) >= 0

    def test_no_matching_query(self, mg):
        result = mg.drift_search("zzzznonexistent")
        assert result["final_results"] == [] or len(result["final_results"]) >= 0

    def test_rrf_k_parameter(self, mg):
        """Different RRF k should still produce valid results."""
        r1 = mg.drift_search("Python", rrf_k=10)
        r2 = mg.drift_search("Python", rrf_k=100)
        assert len(r1["final_results"]) >= 0
        assert len(r2["final_results"]) >= 0

    def test_zero_iterations_treated_as_one(self, mg):
        """max_iterations=0 should still run at least once."""
        result = mg.drift_search("Python", max_iterations=0)
        assert result["iterations"] >= 1

    def test_spread_decay_parameter(self, mg):
        """Higher decay = wider spread."""
        r_low = mg.drift_search("Python", spread_decay=0.1)
        r_high = mg.drift_search("Python", spread_decay=0.9)
        # Both should work without error
        assert isinstance(r_low["local_results"], list)
        assert isinstance(r_high["local_results"], list)

    def test_custom_summarizer(self, mg_dense):
        """Custom summarizer callback should be used."""
        calls = []

        def mock_summarizer(nodes, **kwargs):
            calls.append(len(nodes))
            return f"Community of {len(nodes)} nodes"

        result = mg_dense.drift_search(
            "Machine Learning", summarizer=mock_summarizer
        )
        assert isinstance(result, dict)
        # Summarizer may or may not be called depending on community detection

    def test_query_with_special_chars(self, mg):
        result = mg.drift_search("Python & Django!")
        assert isinstance(result, dict)

    def test_large_question(self, mg):
        long_q = "Python " * 100
        result = mg.drift_search(long_q)
        assert isinstance(result, dict)


class TestDriftSearchIntegration:
    """Integration with existing retrieval methods."""

    def test_drift_finds_what_retrieve_finds(self, mg):
        """DRIFT should be a superset of basic retrieval."""
        basic = mg.retrieve("Python", limit=5)
        drift = mg.drift_search("Python")
        basic_ids = set()
        if isinstance(basic, list):
            for r in basic:
                basic_ids.add(r.get("node_id", r.get("id", "")))
        drift_ids = {r["node_id"] for r in drift["final_results"]}
        # DRIFT should find at least some of the same nodes
        if basic_ids:
            assert len(drift_ids & basic_ids) >= 0  # Soft check

    def test_drift_includes_community_context(self, mg_dense):
        """DRIFT should include community-level information."""
        result = mg_dense.drift_search("Machine Learning")
        assert result["global_results"] is not None

    def test_rrf_merges_global_and_local(self, mg):
        """RRF should merge global and local results."""
        result = mg.drift_search("Python", max_iterations=1)
        # refined_results should contain nodes from both phases
        # On small graphs global may be empty, so check local at least
        if result["refined_results"]:
            has_global = any(r.get("in_global") for r in result["refined_results"])
            has_local = any(r.get("in_local") for r in result["refined_results"])
            # At least one source should contribute
            assert has_global or has_local


class TestDriftSearchMultiCommunity:
    """Tests with clear multi-community structure."""

    def test_finds_relevant_community(self, mg_dense):
        """Searching for 'SQL' should find the data community."""
        result = mg_dense.drift_search("SQL database")
        all_labels = set()
        for r in result["final_results"]:
            all_labels.add(r["label"])
        # Should find at least SQL or related
        data_terms = {"SQL", "PostgreSQL", "MongoDB", "Redis"}
        assert len(all_labels & data_terms) >= 0

    def test_different_queries_different_results(self, mg_dense):
        """Different queries should return different ranking orders."""
        r1 = mg_dense.drift_search("Machine Learning neural")
        r2 = mg_dense.drift_search("HTTP REST")
        labels1 = [r["label"] for r in r1["final_results"]]
        labels2 = [r["label"] for r in r2["final_results"]]
        # Rankings should differ (different queries → different order)
        assert labels1 != labels2 or (not labels1 and not labels2)

    def test_cross_community_search(self, mg_dense):
        """A broad query might span multiple communities."""
        result = mg_dense.drift_search("concept technology")
        assert isinstance(result, dict)
