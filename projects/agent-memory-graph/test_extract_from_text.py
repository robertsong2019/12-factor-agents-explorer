"""Cycle 428: extract_from_text() — Rule-based KG construction from raw text.

Tests for automatic entity/relation extraction and graph building.
"""
import pytest
from memory_graph import MemoryGraph


class TestExtractFromTextBasic:
    """Basic extraction functionality."""

    def test_returns_result_dict(self):
        g = MemoryGraph()
        result = g.extract_from_text("Alice works at Google.")
        assert isinstance(result, dict)
        assert "nodes_created" in result
        assert "edges_created" in result
        assert "entities" in result
        assert "relations" in result

    def test_empty_text(self):
        g = MemoryGraph()
        result = g.extract_from_text("")
        assert result["nodes_created"] == 0
        assert result["edges_created"] == 0
        assert result["entities"] == []

    def test_whitespace_only(self):
        g = MemoryGraph()
        result = g.extract_from_text("   \n  \t  ")
        assert result["nodes_created"] == 0

    def test_single_entity_no_relation(self):
        g = MemoryGraph()
        result = g.extract_from_text("Alice went to the store.")
        # "Alice" should be detected as entity
        labels = [e["label"] for e in result["entities"]]
        assert "Alice" in labels

    def test_multiple_entities(self):
        g = MemoryGraph()
        result = g.extract_from_text(
            "Alice met Bob at the park. Charlie was also there."
        )
        labels = [e["label"] for e in result["entities"]]
        assert "Alice" in labels
        assert "Bob" in labels
        assert "Charlie" in labels


class TestRelationPatterns:
    """Test specific relation pattern detection."""

    def test_is_a_relation(self):
        g = MemoryGraph()
        result = g.extract_from_text("Python is a programming language.")
        rels = result["relations"]
        assert any(r["relation"] == "is_a" for r in rels)
        assert result["edges_created"] >= 1

    def test_works_at_relation(self):
        g = MemoryGraph()
        result = g.extract_from_text("Alice works at Google.")
        rels = result["relations"]
        assert any(r["relation"] == "works_at" for r in rels)

    def test_created_relation(self):
        g = MemoryGraph()
        result = g.extract_from_text("Guido created Python.")
        rels = result["relations"]
        assert any(r["relation"] == "created" for r in rels)

    def test_located_in_relation(self):
        g = MemoryGraph()
        result = g.extract_from_text("The Eiffel Tower is located in Paris.")
        rels = result["relations"]
        assert any(r["relation"] == "located_in" for r in rels)

    def test_has_relation(self):
        g = MemoryGraph()
        result = g.extract_from_text("Alice has a laptop.")
        rels = result["relations"]
        assert any(r["relation"] == "has" for r in rels)

    def test_part_of_relation(self):
        g = MemoryGraph()
        result = g.extract_from_text("Texas is part of the United States.")
        rels = result["relations"]
        assert any(r["relation"] == "part_of" for r in rels)


class TestGraphIntegration:
    """Verify nodes and edges are actually added to the graph."""

    def test_nodes_exist_in_graph(self):
        g = MemoryGraph()
        g.extract_from_text("Alice works at Google.")
        alice = g.search_by_label("Alice")
        google = g.search_by_label("Google")
        assert len(alice) > 0
        assert len(google) > 0

    def test_edges_exist_in_graph(self):
        g = MemoryGraph()
        g.extract_from_text("Alice works at Google.")
        alice = g.search_by_label("Alice")[0]
        google = g.search_by_label("Google")[0]
        # Verify edge exists
        edges = g.conn.execute(
            "SELECT * FROM edges WHERE source=? AND target=?",
            (alice.id, google.id)
        ).fetchall()
        assert len(edges) >= 1

    def test_dedup_same_entity(self):
        g = MemoryGraph()
        g.extract_from_text("Alice works at Google.")
        g.extract_from_text("Alice created a project.")
        # Alice should only appear once
        alice_nodes = g.search_by_label("Alice")
        assert len(alice_nodes) == 1

    def test_entity_kind(self):
        g = MemoryGraph()
        g.extract_from_text("Alice works at Google.")
        alice = g.search_by_label("Alice")[0]
        assert alice.kind == "entity"


class TestMultiSentence:
    """Multi-sentence extraction."""

    def test_multi_sentence_creates_graph(self):
        g = MemoryGraph()
        text = (
            "Alice works at Google. "
            "Bob works at Apple. "
            "Google is a company."
        )
        result = g.extract_from_text(text)
        assert result["nodes_created"] >= 4  # Alice, Google, Bob, Apple
        assert result["edges_created"] >= 3  # works_at x2 + is_a

    def test_paragraph_extraction(self):
        g = MemoryGraph()
        text = (
            "Tesla is a company. "
            "Elon Musk created Tesla. "
            "Tesla is located in California."
        )
        result = g.extract_from_text(text)
        labels = [e["label"] for e in result["entities"]]
        assert "Tesla" in labels
        assert "Elon Musk" in labels
        assert "California" in labels

    def test_handles_newlines(self):
        g = MemoryGraph()
        text = "Alice works at Google.\nBob works at Apple."
        result = g.extract_from_text(text)
        assert result["nodes_created"] >= 4


class TestEntityFiltering:
    """Entity extraction edge cases."""

    def test_lowercase_sentence_no_entities(self):
        g = MemoryGraph()
        result = g.extract_from_text("the cat sat on the mat.")
        # No capitalized words → no entities
        assert result["nodes_created"] == 0

    def test_quoted_entities(self):
        g = MemoryGraph()
        result = g.extract_from_text('The concept of "machine learning" is important.')
        labels = [e["label"] for e in result["entities"]]
        assert any("machine learning" in l for l in labels)

    def test_multi_word_entity(self):
        g = MemoryGraph()
        result = g.extract_from_text("Elon Musk created SpaceX.")
        labels = [e["label"] for e in result["entities"]]
        # "Elon Musk" should be captured as multi-word
        assert any("Elon" in l for l in labels)

    def test_sentence_split(self):
        g = MemoryGraph()
        text = "Alice is a person! Bob is a person? Charlie too."
        result = g.extract_from_text(text)
        labels = [e["label"] for e in result["entities"]]
        assert "Alice" in labels
        assert "Bob" in labels
        assert "Charlie" in labels
