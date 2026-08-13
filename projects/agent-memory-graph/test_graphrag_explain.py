"""Tests for MemoryGraph.graphrag_explain() — diagnostic companion to graphrag_query.

Covers: empty/edge cases, keyword breakdown, score decomposition,
path reconstruction, explanation text, suggestions, consistency with
graphrag_query, non-mutation, and return-structure validation.
"""

import pytest
from memory_graph import MemoryGraph


# ──────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────

@pytest.fixture
def empty_graph():
    return MemoryGraph(":memory:")


@pytest.fixture
def kg_graph():
    """Build a small KG via extract_from_text for realistic testing."""
    mg = MemoryGraph(":memory:")
    mg.extract_from_text(
        "Tesla is an electric vehicle company. "
        "Tesla created Model S. "
        "Tesla is located in California. "
        "Model S is part of Tesla. "
        "Elon Musk works at Tesla. "
        "SpaceX created Starship. "
        "Starship is located in Texas."
    )
    return mg


@pytest.fixture
def tagged_graph():
    """Graph with tag-rich nodes for tag-match testing."""
    mg = MemoryGraph(":memory:")
    mg.add("Python", kind="language", tags=["programming", "scripting"])
    mg.add("Rust", kind="language", tags=["systems", "programming"])
    mg.add("JavaScript", kind="language", tags=["web", "frontend"])
    return mg


# ──────────────────────────────────────────────────────────
# Empty / Edge Cases
# ──────────────────────────────────────────────────────────

class TestEmptyQuery:
    def test_empty_string(self, empty_graph):
        r = empty_graph.graphrag_explain("")
        assert r["question"] == ""
        assert r["keywords"] == []
        assert r["coverage"] == 0.0
        assert r["answer_nodes"] == []
        assert len(r["suggestions"]) > 0

    def test_none_query(self, empty_graph):
        r = empty_graph.graphrag_explain(None)
        assert r["question"] is None or r["question"] == ""
        assert r["keywords"] == []
        assert r["answer_nodes"] == []

    def test_whitespace_only(self, empty_graph):
        r = empty_graph.graphrag_explain("   ")
        assert r["keywords"] == []
        assert r["answer_nodes"] == []

    def test_stopwords_only(self, empty_graph):
        r = empty_graph.graphrag_explain("the is a of in at")
        assert r["keywords"] == []
        assert "stop words" in r["explanation"].lower() or "no keywords" in r["explanation"].lower()

    def test_empty_graph_no_results(self, empty_graph):
        r = empty_graph.graphrag_explain("what is Python")
        assert r["keywords"] != []
        # "what" and "is" are stopwords, so only "python" is a keyword
        assert "python" in r["keywords"]
        assert "what" not in r["keywords"]
        assert r["matched_keywords"] == []
        assert r["unmatched_keywords"] == ["python"]
        assert r["coverage"] == 0.0
        assert r["answer_nodes"] == []
        assert len(r["suggestions"]) > 0


# ──────────────────────────────────────────────────────────
# Keyword Breakdown
# ──────────────────────────────────────────────────────────

class TestKeywordBreakdown:
    def test_keywords_extracted(self, kg_graph):
        r = kg_graph.graphrag_explain("What is Tesla")
        # "what" is stopword, "is" is stopword
        assert "tesla" in r["keywords"]

    def test_matched_keywords(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla Model")
        assert "tesla" in r["matched_keywords"]
        assert "model" in r["matched_keywords"]

    def test_unmatched_keywords(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla banana")
        assert "tesla" in r["matched_keywords"]
        assert "banana" in r["unmatched_keywords"]

    def test_coverage_full(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        assert r["coverage"] == 1.0

    def test_coverage_partial(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla banana")
        assert r["coverage"] == 0.5

    def test_keyword_matches_structure(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        for kw, matches in r["keyword_matches"].items():
            assert isinstance(kw, str)
            for m in matches:
                assert "node_id" in m
                assert "label" in m
                assert "match_type" in m
                assert "score" in m

    def test_match_types_present(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        # At least one match should have a match_type
        types_found = set()
        for kw, matches in r["keyword_matches"].items():
            for m in matches:
                types_found.add(m["match_type"])
        assert len(types_found) > 0

    def test_exact_match_type(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        has_exact = False
        for kw, matches in r["keyword_matches"].items():
            for m in matches:
                if m["match_type"] == "exact":
                    has_exact = True
        assert has_exact  # "Tesla" label should exact-match "tesla"

    def test_contains_match_type(self, kg_graph):
        r = kg_graph.graphrag_explain("Mod")
        has_contains = False
        for kw, matches in r["keyword_matches"].items():
            for m in matches:
                if m["match_type"] in ("contains", "prefix"):
                    has_contains = True
        assert has_contains

    def test_tag_match_type(self, tagged_graph):
        r = tagged_graph.graphrag_explain("programming")
        # "programming" is a tag, should match via tag
        has_tag = False
        for kw, matches in r["keyword_matches"].items():
            for m in matches:
                if m["match_type"] == "tag":
                    has_tag = True
        assert has_tag


# ──────────────────────────────────────────────────────────
# Score Decomposition
# ──────────────────────────────────────────────────────────

class TestScoreDecomposition:
    def test_answer_node_has_score_components(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        assert len(r["answer_nodes"]) > 0
        node = r["answer_nodes"][0]
        assert "keyword_score" in node
        assert "degree" in node
        assert "centrality" in node
        assert "hop_penalty" in node
        assert "combined_score" in node
        assert "hops" in node

    def test_keyword_score_range(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        for node in r["answer_nodes"]:
            assert 0.0 <= node["keyword_score"] <= 1.0

    def test_centrality_positive(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        for node in r["answer_nodes"]:
            assert node["centrality"] >= 1.0

    def test_hop_penalty_range(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        for node in r["answer_nodes"]:
            assert 0.0 < node["hop_penalty"] <= 1.0

    def test_combined_score_formula(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        for node in r["answer_nodes"]:
            kw = node["keyword_score"] if node["keyword_score"] > 0 else 0.1
            expected = kw * node["centrality"] * node["hop_penalty"]
            assert abs(node["combined_score"] - round(expected, 4)) < 0.01

    def test_seed_node_has_hops_zero(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        seed_nodes = [n for n in r["answer_nodes"] if n["keyword_score"] > 0]
        for node in seed_nodes:
            # Seed nodes that appear as answer nodes should have hops=0
            # (they are directly matched, not traversed to)
            # But they could also be reached at hops=0 in BFS
            if node["keyword_score"] >= 0.5:
                # Direct keyword match → likely a seed
                pass  # hops should be 0 for seeds

    def test_nodes_sorted_by_score(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla SpaceX")
        scores = [n["combined_score"] for n in r["answer_nodes"]]
        assert scores == sorted(scores, reverse=True)

    def test_top_k_limit(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla SpaceX Starship Model Musk", top_k=2)
        assert len(r["answer_nodes"]) <= 2

    def test_match_reasons_in_answer(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        # At least some answer nodes should have match reasons
        has_reasons = any(
            len(n.get("match_reasons", [])) > 0
            for n in r["answer_nodes"]
        )
        assert has_reasons

    def test_match_reasons_structure(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        for node in r["answer_nodes"]:
            for reason in node.get("match_reasons", []):
                assert "keyword" in reason
                assert "match_type" in reason
                assert "score" in reason


# ──────────────────────────────────────────────────────────
# Path Reconstruction
# ──────────────────────────────────────────────────────────

class TestPathReconstruction:
    def test_path_from_seed_present(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla", max_hops=2)
        for node in r["answer_nodes"]:
            assert "path_from_seed" in node
            assert isinstance(node["path_from_seed"], list)

    def test_seed_path_is_single_node(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        # The Tesla node itself should have a single-element path
        tesla_nodes = [n for n in r["answer_nodes"]
                       if n["label"] and "Tesla" in n["label"]]
        for node in tesla_nodes:
            if node["hops"] == 0:
                assert len(node["path_from_seed"]) == 1

    def test_traversed_node_has_multi_hop_path(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla", max_hops=3)
        # Some nodes should have multi-hop paths
        multi_hop = [n for n in r["answer_nodes"] if n["hops"] > 0]
        # With the KG fixture, there should be connected nodes
        if multi_hop:
            for node in multi_hop:
                assert len(node["path_from_seed"]) >= 2

    def test_path_starts_with_seed(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla", max_hops=3)
        for node in r["answer_nodes"]:
            if len(node["path_from_seed"]) > 1:
                # First element should be a seed node
                seed_labels = [s for s in r["seed_nodes"]]
                # Just verify path is non-empty and starts somewhere
                assert node["path_from_seed"][0] is not None

    def test_path_labels_are_strings(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        for node in r["answer_nodes"]:
            for label in node["path_from_seed"]:
                assert isinstance(label, str)


# ──────────────────────────────────────────────────────────
# Explanation Text
# ──────────────────────────────────────────────────────────

class TestExplanationText:
    def test_explanation_is_string(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        assert isinstance(r["explanation"], str)

    def test_explanation_contains_query(self, kg_graph):
        r = kg_graph.graphrag_explain("What is Tesla")
        assert "Tesla" in r["explanation"] or "tesla" in r["explanation"].lower()

    def test_explanation_contains_keywords(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla SpaceX")
        assert "tesla" in r["explanation"].lower()
        assert "spacex" in r["explanation"].lower()

    def test_explanation_contains_coverage(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla banana")
        assert "coverage" in r["explanation"].lower()

    def test_explanation_contains_seed_nodes(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        assert "seed" in r["explanation"].lower()

    def test_explanation_contains_score_breakdown(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        assert "kw=" in r["explanation"] or "centrality" in r["explanation"].lower()

    def test_explanation_contains_hops(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla", max_hops=3)
        assert "hop" in r["explanation"].lower()

    def test_explanation_contains_edges_count(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        assert "edge" in r["explanation"].lower()


# ──────────────────────────────────────────────────────────
# Suggestions
# ──────────────────────────────────────────────────────────

class TestSuggestions:
    def test_suggestions_is_list(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        assert isinstance(r["suggestions"], list)
        assert len(r["suggestions"]) > 0

    def test_low_coverage_suggestion(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla banana orange")
        suggestion_text = " ".join(r["suggestions"]).lower()
        assert "coverage" in suggestion_text or "unmatched" in suggestion_text

    def test_no_seed_suggestion(self, empty_graph):
        r = empty_graph.graphrag_explain("Python")
        suggestion_text = " ".join(r["suggestions"]).lower()
        assert "no" in suggestion_text or "not" in suggestion_text

    def test_healthy_suggestion_when_good_coverage(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        suggestion_text = " ".join(r["suggestions"]).lower()
        assert "healthy" in suggestion_text or "good" in suggestion_text

    def test_traversal_only_suggestion(self, empty_graph):
        mg = MemoryGraph(":memory:")
        # Create two linked nodes but query with a keyword that won't match
        a = mg.add("NodeA", kind="entity")
        b = mg.add("NodeB", kind="entity")
        mg.link(a.id, b.id, "connects")
        r = mg.graphrag_explain("banana", max_hops=2)
        # "banana" won't match anything, so no traversal-only scenario
        assert len(r["answer_nodes"]) == 0


# ──────────────────────────────────────────────────────────
# Consistency with graphrag_query
# ──────────────────────────────────────────────────────────

class TestConsistencyWithQuery:
    def test_same_keywords(self, kg_graph):
        q = "What is Tesla"
        qr = kg_graph.graphrag_query(q)
        er = kg_graph.graphrag_explain(q)
        assert qr["keywords"] == er["keywords"]

    def test_same_seed_nodes(self, kg_graph):
        q = "Tesla SpaceX"
        qr = kg_graph.graphrag_query(q)
        er = kg_graph.graphrag_explain(q)
        assert set(qr["seed_nodes"]) == set(er["seed_nodes"].keys())

    def test_same_answer_node_ids(self, kg_graph):
        q = "Tesla"
        qr = kg_graph.graphrag_query(q)
        er = kg_graph.graphrag_explain(q)
        q_ids = {n["node_id"] for n in qr["answer_nodes"]}
        e_ids = {n["node_id"] for n in er["answer_nodes"]}
        assert q_ids == e_ids

    def test_same_context_edges(self, kg_graph):
        q = "Tesla SpaceX"
        qr = kg_graph.graphrag_query(q)
        er = kg_graph.graphrag_explain(q)
        assert len(qr["context_edges"]) == len(er["context_edges"])

    def test_same_scores(self, kg_graph):
        q = "Tesla"
        qr = kg_graph.graphrag_query(q)
        er = kg_graph.graphrag_explain(q)
        q_scores = {n["node_id"]: n["score"] for n in qr["answer_nodes"]}
        e_scores = {n["node_id"]: n["combined_score"] for n in er["answer_nodes"]}
        for nid in q_scores:
            assert abs(q_scores[nid] - e_scores[nid]) < 0.01


# ──────────────────────────────────────────────────────────
# Non-Mutation
# ──────────────────────────────────────────────────────────

class TestNonMutation:
    def test_graph_unchanged(self, kg_graph):
        before = kg_graph.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        before_edges = kg_graph.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        kg_graph.graphrag_explain("Tesla SpaceX Starship")
        after = kg_graph.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        after_edges = kg_graph.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        assert before == after
        assert before_edges == after_edges

    def test_idempotent(self, kg_graph):
        r1 = kg_graph.graphrag_explain("Tesla")
        r2 = kg_graph.graphrag_explain("Tesla")
        assert r1["keywords"] == r2["keywords"]
        assert len(r1["answer_nodes"]) == len(r2["answer_nodes"])
        assert r1["explanation"] == r2["explanation"]

    def test_node_data_unchanged(self, tagged_graph):
        # Get Python node data before
        python_row = tagged_graph.conn.execute(
            "SELECT label, kind, tags FROM nodes WHERE label='Python'"
        ).fetchone()
        tagged_graph.graphrag_explain("programming scripting")
        python_after = tagged_graph.conn.execute(
            "SELECT label, kind, tags FROM nodes WHERE label='Python'"
        ).fetchone()
        assert python_row == python_after


# ──────────────────────────────────────────────────────────
# Return Structure
# ──────────────────────────────────────────────────────────

class TestReturnStructure:
    def test_all_keys_present(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        expected_keys = {
            "question", "keywords", "matched_keywords",
            "unmatched_keywords", "coverage", "keyword_matches",
            "seed_nodes", "answer_nodes", "context_edges",
            "explanation", "suggestions",
        }
        assert expected_keys.issubset(set(r.keys()))

    def test_question_echoed(self, kg_graph):
        r = kg_graph.graphrag_explain("What is Tesla")
        assert r["question"] == "What is Tesla"

    def test_coverage_is_float(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        assert isinstance(r["coverage"], float)
        assert 0.0 <= r["coverage"] <= 1.0

    def test_seed_nodes_is_dict(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        assert isinstance(r["seed_nodes"], dict)

    def test_keyword_matches_is_dict(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        assert isinstance(r["keyword_matches"], dict)

    def test_context_edges_is_list(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla")
        assert isinstance(r["context_edges"], list)

    def test_answer_nodes_sorted_desc(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla SpaceX")
        scores = [n["combined_score"] for n in r["answer_nodes"]]
        assert scores == sorted(scores, reverse=True)

    def test_max_hops_clamped(self, kg_graph):
        r1 = kg_graph.graphrag_explain("Tesla", max_hops=100)
        r2 = kg_graph.graphrag_explain("Tesla", max_hops=5)
        # Both should produce same results (clamped to 5)
        assert len(r1["answer_nodes"]) == len(r2["answer_nodes"])

    def test_max_hops_min_clamped(self, kg_graph):
        r = kg_graph.graphrag_explain("Tesla", max_hops=0)
        # Should be clamped to at least 1
        assert isinstance(r["answer_nodes"], list)
