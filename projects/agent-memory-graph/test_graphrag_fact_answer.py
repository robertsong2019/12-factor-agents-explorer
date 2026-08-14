"""Cycle 433: graphrag_query() fact-answer extraction — edge objects, not top-1 node.

GraphRAG-Bench lesson (Research #064): fact questions ("Where is X located?")
must be answered from the edge OBJECT (X -located_in→ Y), not the top-1 ranked
node (which is the subject X itself).
"""
import pytest
from memory_graph import MemoryGraph


def _novel_graph() -> MemoryGraph:
    """Graph built via extract_from_text with abbreviations (Cycle 432 synergy)."""
    g = MemoryGraph()
    g.extract_from_text(
        "Mont St. Michel is located in Normandy. "
        "Mr. Darcy works at Pemberley. "
        "Mrs. Bennet has five daughters. "
        "Elizabeth created a tapestry."
    )
    return g


class TestLocatedInForward:
    """'Where is X located?' → target of X's located_in edges."""

    def test_where_is_located(self):
        g = _novel_graph()
        r = g.graphrag_query("Where is Mont St. Michel located?")
        fa = r["fact_answer"]
        assert fa["matched"] is True
        assert fa["relation"] == "located_in"
        assert fa["direction"] == "forward"
        assert fa["subject"] == "Mont St. Michel"
        assert "Normandy" in fa["answers"]

    def test_answer_is_edge_object_not_seed(self):
        g = _novel_graph()
        r = g.graphrag_query("Where is Mont St. Michel located?")
        # top-1 ranked node is the subject itself; fact answer must differ
        fa = r["fact_answer"]
        top1_label = r["answer_nodes"][0]["label"]
        assert fa["answers"] != [top1_label] or top1_label == "Normandy"
        assert fa["answer_edges"][0] == {
            "source": "Mont St. Michel", "target": "Normandy",
            "relation": "located_in",
        }

    def test_case_insensitive_question(self):
        g = _novel_graph()
        r = g.graphrag_query("where is mont st. michel located")
        assert r["fact_answer"]["matched"] is True
        assert "Normandy" in r["fact_answer"]["answers"]


class TestWorksAtDirections:
    """works_at forward and reverse."""

    def test_where_does_x_work_forward(self):
        g = _novel_graph()
        r = g.graphrag_query("Where does Mr. Darcy work?")
        fa = r["fact_answer"]
        assert fa["matched"] is True
        assert fa["relation"] == "works_at"
        assert fa["direction"] == "forward"
        assert fa["subject"] == "Mr. Darcy"
        assert "Pemberley" in fa["answers"]

    def test_who_works_at_reverse(self):
        g = MemoryGraph()
        alice = g.add("Alice", kind="person")
        bob = g.add("Bob", kind="person")
        acme = g.add("Acme", kind="company")
        g.link(alice.id, acme.id, "works_at")
        g.link(bob.id, acme.id, "works_at")
        r = g.graphrag_query("Who works at Acme?")
        fa = r["fact_answer"]
        assert fa["matched"] is True
        assert fa["direction"] == "reverse"
        assert fa["subject"] == "Acme"
        assert set(fa["answers"]) == {"Alice", "Bob"}

    def test_worked_past_tense_reverse(self):
        g = MemoryGraph()
        alice = g.add("Alice", kind="person")
        acme = g.add("Acme", kind="company")
        g.link(alice.id, acme.id, "works_at")
        r = g.graphrag_query("Who worked at Acme?")
        fa = r["fact_answer"]
        assert fa["matched"] is True
        assert "Alice" in fa["answers"]


class TestCreatedDirections:
    """created forward and reverse."""

    def test_what_did_x_create_forward(self):
        g = _novel_graph()
        r = g.graphrag_query("What did Elizabeth create?")
        fa = r["fact_answer"]
        assert fa["matched"] is True
        assert fa["relation"] == "created"
        assert fa["direction"] == "forward"
        assert fa["subject"] == "Elizabeth"
        assert any("tapestry" in a.lower() for a in fa["answers"])

    def test_who_created_x_reverse(self):
        g = MemoryGraph()
        guido = g.add("Guido", kind="person")
        py = g.add("Python", kind="language")
        g.link(guido.id, py.id, "created")
        r = g.graphrag_query("Who created Python?")
        fa = r["fact_answer"]
        assert fa["matched"] is True
        assert fa["direction"] == "reverse"
        assert fa["subject"] == "Python"
        assert fa["answers"] == ["Guido"]

    def test_who_built_x_reverse(self):
        g = MemoryGraph()
        frank = g.add("Frank", kind="person")
        m = g.add("Monster", kind="creature")
        g.link(frank.id, m.id, "created")
        r = g.graphrag_query("Who built the Monster?")
        fa = r["fact_answer"]
        assert fa["matched"] is True
        assert fa["answers"] == ["Frank"]


class TestPartOfAndHas:
    """part_of / has forward."""

    def test_what_is_x_part_of(self):
        g = MemoryGraph()
        texas = g.add("Texas", kind="state")
        us = g.add("United States", kind="country")
        g.link(texas.id, us.id, "part_of")
        r = g.graphrag_query("What is Texas part of?")
        fa = r["fact_answer"]
        assert fa["matched"] is True
        assert fa["relation"] == "part_of"
        assert "United States" in fa["answers"]

    def test_what_does_x_have(self):
        g = _novel_graph()
        r = g.graphrag_query("What does Mrs. Bennet have?")
        fa = r["fact_answer"]
        assert fa["matched"] is True
        assert fa["relation"] == "has"
        assert fa["subject"] == "Mrs. Bennet"
        assert any("daughters" in a.lower() for a in fa["answers"])


class TestNoMatchCases:
    """Graceful handling when no cue matches or subject missing."""

    def test_no_cue_matched_false(self):
        g = _novel_graph()
        r = g.graphrag_query("Tell me about Normandy")
        assert r["fact_answer"]["matched"] is False
        assert "reason" not in r["fact_answer"]

    def test_subject_not_found(self):
        g = _novel_graph()
        r = g.graphrag_query("Where is Atlantis located?")
        fa = r["fact_answer"]
        assert fa["matched"] is False
        assert fa["reason"] == "subject_not_found"
        assert fa["subject_fragment"] == "Atlantis"

    def test_no_matching_edges(self):
        g = MemoryGraph()
        g.add("Alice", kind="person")  # no located_in edges
        r = g.graphrag_query("Where is Alice located?")
        fa = r["fact_answer"]
        assert fa["matched"] is False
        assert fa["reason"] == "no_matching_edges"
        assert fa["subject"] == "Alice"

    def test_empty_question_fact_answer_present(self):
        g = _novel_graph()
        r = g.graphrag_query("")
        assert r["fact_answer"] == {"matched": False}

    def test_contains_match_fallback(self):
        # Subject fragment longer than stored label
        g = MemoryGraph()
        g.add("Normandy", kind="place")
        r = g.graphrag_query("Where is the beautiful region of Normandy located?")
        # No located_in edges → subject found via contains, but no answers
        fa = r["fact_answer"]
        assert fa["reason"] == "no_matching_edges"
        assert fa["subject"] == "Normandy"


class TestContextIntegration:
    """Fact answer surfaces in the LLM context string."""

    def test_context_has_fact_answer_section(self):
        g = _novel_graph()
        r = g.graphrag_query("Where is Mont St. Michel located?")
        assert "## Fact Answer" in r["context"]
        assert "Normandy" in r["context"]

    def test_context_fact_section_first(self):
        g = _novel_graph()
        r = g.graphrag_query("Where is Mont St. Michel located?")
        lines = r["context"].split("\n")
        fact_idx = lines.index("## Fact Answer")
        ent_idx = lines.index("## Relevant Entities")
        assert fact_idx < ent_idx

    def test_context_no_fact_section_when_unmatched(self):
        g = _novel_graph()
        r = g.graphrag_query("Tell me about Normandy")
        assert "## Fact Answer" not in r["context"]

    def test_pipeline_still_returns_ranking(self):
        g = _novel_graph()
        r = g.graphrag_query("Where is Mont St. Michel located?")
        assert len(r["answer_nodes"]) > 0
        assert len(r["context_edges"]) > 0
        assert r["keywords"]


class TestAbbreviationSynergy:
    """E2E: Cycle 432 fix enables Cycle 433 answers (Research #064 scenario)."""

    def test_full_pipeline_novel_domain(self):
        """The exact GraphRAG-Bench failure: St. period used to fragment the
        entity, so the located_in edge never existed and the question failed."""
        g = MemoryGraph()
        r0 = g.extract_from_text("Mont St. Michel is located in France.")
        assert r0["relations"][0]["source"] == "Mont St. Michel"
        r = g.graphrag_query("Where is Mont St. Michel located?")
        assert r["fact_answer"]["matched"] is True
        assert r["fact_answer"]["answers"] == ["France"]
