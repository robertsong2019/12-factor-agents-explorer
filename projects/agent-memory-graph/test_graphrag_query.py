"""Tests for graphrag_query() — GraphRAG read-side retrieval.

Cycle 429: Completes the extract_from_text → graphrag_query pipeline.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def kg():
    """Build a small KG via extract_from_text for testing."""
    mg = MemoryGraph()
    mg.extract_from_text(
        "Apple is a company. "
        "Tim Cook works at Apple. "
        "Apple created iPhone. "
        "iPhone is a smartphone. "
        "Cupertino is located in California. "
        "Apple is located in Cupertino. "
        "iPhone has a camera. "
        "Apple is part of the tech industry."
    )
    return mg


# ──────────────────────────────────────────────
# Basic structure
# ──────────────────────────────────────────────

class TestGraphRAGQueryBasic:

    def test_empty_question_returns_empty(self):
        mg = MemoryGraph()
        r = mg.graphrag_query("")
        assert r["answer_nodes"] == []
        assert r["keywords"] == []
        assert r["context"] == ""

    def test_none_question(self):
        mg = MemoryGraph()
        r = mg.graphrag_query(None)
        assert r["answer_nodes"] == []

    def test_whitespace_only(self):
        mg = MemoryGraph()
        r = mg.graphrag_query("   ")
        assert r["answer_nodes"] == []

    def test_returns_required_keys(self):
        mg = MemoryGraph()
        mg.add("Apple", kind="entity")
        r = mg.graphrag_query("What is Apple?")
        assert "answer_nodes" in r
        assert "context_edges" in r
        assert "seed_nodes" in r
        assert "keywords" in r
        assert "context" in r


# ──────────────────────────────────────────────
# Keyword extraction
# ──────────────────────────────────────────────

class TestKeywordExtraction:

    def test_stop_words_filtered(self, kg):
        r = kg.graphrag_query("What is the Apple?")
        # "what", "is", "the" should be filtered
        assert "apple" in r["keywords"]
        assert "what" not in r["keywords"]
        assert "the" not in r["keywords"]

    def test_multiple_keywords(self, kg):
        r = kg.graphrag_query("Apple iPhone camera")
        assert "apple" in r["keywords"]
        assert "iphone" in r["keywords"]
        assert "camera" in r["keywords"]

    def test_keywords_lowercased(self, kg):
        r = kg.graphrag_query("APPLE Company")
        assert "apple" in r["keywords"]
        assert "company" in r["keywords"]

    def test_keywords_deduplicated(self, kg):
        r = kg.graphrag_query("Apple apple APPLE")
        kw_count = r["keywords"].count("apple")
        assert kw_count == 1

    def test_no_keywords_after_filtering(self, kg):
        r = kg.graphrag_query("the is a of")
        assert r["keywords"] == []
        assert r["answer_nodes"] == []

    def test_single_char_filtered(self, kg):
        r = kg.graphrag_query("a I x")
        # Single char words should be filtered
        assert r["keywords"] == []


# ──────────────────────────────────────────────
# Seed node matching
# ──────────────────────────────────────────────

class TestSeedMatching:

    def test_exact_label_match(self, kg):
        r = kg.graphrag_query("Apple")
        assert len(r["seed_nodes"]) > 0
        # Apple should be a seed node — verify via answer_nodes
        labels = [an["label"] for an in r["answer_nodes"]]
        assert any("Apple" in l for l in labels)

    def test_partial_label_match(self, kg):
        r = kg.graphrag_query("iph")
        # "iph" should match "iPhone" via LIKE
        assert len(r["seed_nodes"]) > 0

    def test_no_match_returns_empty(self, kg):
        r = kg.graphrag_query("quantum mechanics")
        assert r["seed_nodes"] == []
        assert r["answer_nodes"] == []

    def test_tag_match_boosts_score(self):
        mg = MemoryGraph()
        n = mg.add("Python", kind="entity", tags=["programming", "language"])
        mg.add("Snake", kind="entity", tags=["animal"])
        r = mg.graphrag_query("programming")
        assert n.id in r["seed_nodes"] or len(r["answer_nodes"]) > 0
        # Python should appear in results
        labels = [an["label"] for an in r["answer_nodes"]]
        assert "Python" in labels


# ──────────────────────────────────────────────
# Traversal & hops
# ──────────────────────────────────────────────

class TestTraversal:

    def test_max_hops_default_2(self, kg):
        r = kg.graphrag_query("Apple", max_hops=2)
        # Should find nodes up to 2 hops from Apple
        hops_found = {an["hops"] for an in r["answer_nodes"]}
        assert max(hops_found) <= 2

    def test_max_hops_1_limited(self, kg):
        r = kg.graphrag_query("Apple", max_hops=1)
        hops_found = {an["hops"] for an in r["answer_nodes"]}
        assert max(hops_found) <= 1

    def test_max_hops_3_expands(self, kg):
        r2 = kg.graphrag_query("Apple", max_hops=2)
        r3 = kg.graphrag_query("Apple", max_hops=3)
        # More hops should find >= nodes
        assert len(r3["context_edges"]) >= len(r2["context_edges"])

    def test_max_hops_clamped_to_5(self, kg):
        r = kg.graphrag_query("Apple", max_hops=100)
        # Should not crash, clamped to 5
        hops_found = {an["hops"] for an in r["answer_nodes"]}
        assert max(hops_found) <= 5

    def test_max_hops_min_1(self, kg):
        r = kg.graphrag_query("Apple", max_hops=0)
        # Should be clamped to 1
        hops_found = {an["hops"] for an in r["answer_nodes"]}
        assert max(hops_found) <= 1

    def test_context_edges_populated(self, kg):
        r = kg.graphrag_query("Apple")
        assert len(r["context_edges"]) > 0
        for e in r["context_edges"]:
            assert "source" in e
            assert "target" in e
            assert "relation" in e


# ──────────────────────────────────────────────
# Answer node ranking
# ──────────────────────────────────────────────

class TestRanking:

    def test_top_k_limit(self, kg):
        r = kg.graphrag_query("Apple", top_k=2)
        assert len(r["answer_nodes"]) <= 2

    def test_top_k_default_5(self, kg):
        r = kg.graphrag_query("Apple")
        assert len(r["answer_nodes"]) <= 5

    def test_seed_nodes_ranked_higher(self, kg):
        r = kg.graphrag_query("Apple")
        if len(r["answer_nodes"]) >= 2:
            # Seed nodes (hop 0) should generally rank higher
            top = r["answer_nodes"][0]
            assert top["hops"] == 0 or top["keyword_match"] > 0

    def test_scores_sorted_descending(self, kg):
        r = kg.graphrag_query("Apple iPhone")
        scores = [an["score"] for an in r["answer_nodes"]]
        assert scores == sorted(scores, reverse=True)

    def test_score_fields_present(self, kg):
        r = kg.graphrag_query("Apple")
        for an in r["answer_nodes"]:
            assert "node_id" in an
            assert "label" in an
            assert "kind" in an
            assert "score" in an
            assert "hops" in an
            assert "keyword_match" in an
            assert "degree" in an


# ──────────────────────────────────────────────
# Context string generation
# ──────────────────────────────────────────────

class TestContextString:

    def test_context_has_entities_section(self, kg):
        r = kg.graphrag_query("Apple")
        assert "## Relevant Entities" in r["context"]

    def test_context_has_relations_section(self, kg):
        r = kg.graphrag_query("Apple")
        assert "## Relations" in r["context"]

    def test_context_contains_labels(self, kg):
        r = kg.graphrag_query("Apple")
        assert "Apple" in r["context"]

    def test_context_contains_relation_arrows(self, kg):
        kg2 = MemoryGraph()
        kg2.extract_from_text("Apple created iPhone.")
        r = kg2.graphrag_query("Apple")
        assert "-->" in r["context"]
        assert "created" in r["context"]

    def test_include_context_false(self, kg):
        r = kg.graphrag_query("Apple", include_context=False)
        assert "context" not in r or r.get("context") is None or r["context"] == ""

    def test_empty_graph_context(self):
        mg = MemoryGraph()
        r = mg.graphrag_query("anything")
        assert r["context"] == ""

    def test_no_match_context(self, kg):
        r = kg.graphrag_query("quantum")
        assert r["context"] == ""


# ──────────────────────────────────────────────
# Integration with extract_from_text
# ──────────────────────────────────────────────

class TestExtractQueryPipeline:

    def test_full_pipeline(self):
        """extract_from_text → graphrag_query round trip."""
        mg = MemoryGraph()
        text = (
            "Tesla is a company. "
            "Elon Musk works at Tesla. "
            "Tesla created Model S. "
            "Model S is a car. "
            "Tesla is located in Austin."
        )
        extract_result = mg.extract_from_text(text)
        assert extract_result["nodes_created"] > 0

        # Query the built graph
        q_result = mg.graphrag_query("Who created Model S?")
        assert len(q_result["answer_nodes"]) > 0
        labels = [an["label"] for an in q_result["answer_nodes"]]
        # Model S or Tesla should appear
        assert any("Model" in l or "Tesla" in l or "Musk" in l
                    for l in labels)

    def test_multi_hop_traversal_finds_distant_nodes(self):
        mg = MemoryGraph()
        a = mg.add("Alpha")
        b = mg.add("Beta")
        c = mg.add("Gamma")
        d = mg.add("Delta")
        mg.link(a.id, b.id, "connects")
        mg.link(b.id, c.id, "connects")
        mg.link(c.id, d.id, "connects")

        r = mg.graphrag_query("Alpha", max_hops=3)
        labels = [an["label"] for an in r["answer_nodes"]]
        assert "Delta" in labels

    def test_query_after_adding_nodes_manually(self):
        mg = MemoryGraph()
        mg.add("Python", tags=["language"])
        mg.add("JavaScript", tags=["language"])
        mg.link("n0", "n1", "similar_to")

        r = mg.graphrag_query("Python language")
        assert len(r["answer_nodes"]) > 0

    def test_repeated_queries_consistent(self, kg):
        r1 = kg.graphrag_query("Apple")
        r2 = kg.graphrag_query("Apple")
        assert r1["answer_nodes"] == r2["answer_nodes"]

    def test_bidirectional_traversal(self):
        """graphrag_query should traverse edges in both directions."""
        mg = MemoryGraph()
        src = mg.add("Source")
        tgt = mg.add("Target")
        mg.link(src.id, tgt.id, "points_to")

        # Query from Target should find Source via reverse edge
        r = mg.graphrag_query("Target")
        labels = [an["label"] for an in r["answer_nodes"]]
        assert "Source" in labels


# ──────────────────────────────────────────────
# Edge cases
# ──────────────────────────────────────────────

class TestEdgeCases:

    def test_graph_with_no_edges(self):
        mg = MemoryGraph()
        mg.add("Isolated")
        r = mg.graphrag_query("Isolated")
        assert len(r["answer_nodes"]) == 1
        assert r["answer_nodes"][0]["degree"] == 0

    def test_query_with_numbers(self):
        mg = MemoryGraph()
        mg.add("GPT4", kind="model")
        r = mg.graphrag_query("GPT4")
        assert len(r["answer_nodes"]) > 0

    def test_large_top_k(self, kg):
        r = kg.graphrag_query("Apple", top_k=1000)
        # Should return all available, not crash
        assert len(r["answer_nodes"]) >= 1

    def test_empty_graph_no_crash(self):
        mg = MemoryGraph()
        r = mg.graphrag_query("test")
        assert r["answer_nodes"] == []
        assert r["context"] == ""

    def test_special_chars_in_query(self, kg):
        r = kg.graphrag_query("Apple!!! @#$%")
        # Should extract "apple" and not crash
        assert "apple" in r["keywords"] or r["keywords"] == []
