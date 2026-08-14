"""Cycle 434: graphrag_explain() fact-answer diagnostics — query gives answers,
explain gives diagnoses (closed loop with graphrag_query Phase 0).
"""
import pytest
from memory_graph import MemoryGraph


def _novel_graph() -> MemoryGraph:
    g = MemoryGraph()
    g.extract_from_text(
        "Mont St. Michel is located in Normandy. "
        "Mr. Darcy works at Pemberley. "
        "Elizabeth created a tapestry."
    )
    return g


class TestExplainFactAnswer:
    """fact_answer key + explanation lines for matched/unmatched cases."""

    def test_matched_fact_in_result_and_explanation(self):
        g = _novel_graph()
        r = g.graphrag_explain("Where is Mont St. Michel located?")
        fa = r["fact_answer"]
        assert fa["matched"] is True
        assert fa["subject_resolution"] == "exact"
        assert fa["subject"] == "Mont St. Michel"
        assert "Normandy" in fa["answers"]
        assert "Fact answer: Mont St. Michel -located_in→ Normandy" in r["explanation"]

    def test_resolution_field_forward_contains(self):
        g = MemoryGraph()
        g.add("Alice", kind="person")
        g.add("Alice Smith", kind="person")
        r = g.graphrag_explain("Where is Alice located?")
        assert r["fact_answer"]["subject"] == "Alice"          # exact tier wins
        assert r["fact_answer"]["subject_resolution"] == "exact"

    def test_subject_not_found_diagnostic(self):
        g = _novel_graph()
        r = g.graphrag_explain("Where is Atlantis located?")
        fa = r["fact_answer"]
        assert fa["matched"] is False
        assert fa["reason"] == "subject_not_found"
        assert "Atlantis" in r["explanation"]
        assert any("Atlantis" in s for s in r["suggestions"])

    def test_no_matching_edges_diagnostic(self):
        g = MemoryGraph()
        g.add("Alice", kind="person")
        r = g.graphrag_explain("Where is Alice located?")
        fa = r["fact_answer"]
        assert fa["reason"] == "no_matching_edges"
        assert "no 'located_in' edges exist" in r["explanation"]
        assert any("located_in" in s for s in r["suggestions"])

    def test_matched_fact_suggestion(self):
        g = _novel_graph()
        r = g.graphrag_explain("Where is Mont St. Michel located?")
        assert any("supporting context" in s for s in r["suggestions"])

    def test_non_fact_question_untouched(self):
        g = _novel_graph()
        r = g.graphrag_explain("Tell me about Normandy")
        assert r["fact_answer"] == {"matched": False}
        assert "Fact answer:" not in r["explanation"]
        assert "Fact question" not in r["explanation"]


class TestQueryExplainConsistency:
    """Both surfaces must agree — same helper, same result."""

    def test_same_fact_answer(self):
        g = _novel_graph()
        q = g.graphrag_query("Where is Mont St. Michel located?")
        e = g.graphrag_explain("Where is Mont St. Michel located?")
        assert q["fact_answer"] == e["fact_answer"]

    def test_consistency_reverse_direction(self):
        g = MemoryGraph()
        alice = g.add("Alice", kind="person")
        acme = g.add("Acme", kind="company")
        g.link(alice.id, acme.id, "works_at")
        q = g.graphrag_query("Who works at Acme?")
        e = g.graphrag_explain("Who works at Acme?")
        assert q["fact_answer"] == e["fact_answer"]
        assert q["fact_answer"]["direction"] == "reverse"

    def test_query_pipeline_still_works_alongside(self):
        g = _novel_graph()
        r = g.graphrag_explain("Where is Mont St. Michel located?")
        assert len(r["answer_nodes"]) > 0
        assert 0 < r["coverage"] <= 1.0
