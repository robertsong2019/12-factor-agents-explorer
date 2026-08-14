"""Cycle 432: extract_from_text() abbreviation-safe sentence segmentation.

GraphRAG-Bench Novel-domain lesson (Research #064): un-protected periods in
Mr./Mrs./St. fragment entities ("Mont St. Michel" → "Mont St" + "Michel")
and break relation cues. Tests verify abbreviations stay inside their
sentence while normal splitting is unaffected.
"""
import pytest
from memory_graph import MemoryGraph


class TestAbbreviationSentenceSplit:
    """Abbreviation periods must not split sentences."""

    def test_st_abbreviation_one_sentence(self):
        g = MemoryGraph()
        result = g.extract_from_text(
            "Mont St. Michel is located in Normandy. Alice visited it."
        )
        # 2 sentences — not 3 (St. period protected)
        assert result["sentences"] == 2

    def test_mr_abbreviation_one_sentence(self):
        g = MemoryGraph()
        result = g.extract_from_text("Mr. Darcy works at Pemberley.")
        assert result["sentences"] == 1
        rels = result["relations"]
        assert any(r["relation"] == "works_at" for r in rels)
        assert any(r["source"] == "Mr. Darcy" for r in rels)

    def test_mrs_abbreviation(self):
        g = MemoryGraph()
        result = g.extract_from_text("Mrs. Bennet has five daughters.")
        assert result["sentences"] == 1
        rels = result["relations"]
        assert any(r["source"] == "Mrs. Bennet" for r in rels)

    def test_dr_abbreviation(self):
        g = MemoryGraph()
        result = g.extract_from_text(
            "Dr. Watson created a journal. Sherlock Holmes is a detective."
        )
        assert result["sentences"] == 2
        rels = result["relations"]
        assert any(r["relation"] == "created" for r in rels)
        assert any(r["source"] == "Dr. Watson" for r in rels)

    def test_multiple_abbreviations_same_sentence(self):
        g = MemoryGraph()
        result = g.extract_from_text(
            "Mr. Collins works at Mrs. Bennet House."
        )
        assert result["sentences"] == 1

    def test_initials_protected(self):
        g = MemoryGraph()
        result = g.extract_from_text(
            "J. K. Rowling created Harry Potter. Harry Potter is a wizard."
        )
        # Initial periods protected → exactly 2 sentences
        assert result["sentences"] == 2

    def test_st_entity_not_fragmented(self):
        g = MemoryGraph()
        result = g.extract_from_text("Mont St. Michel is located in France.")
        # The full entity survives: located_in relation Mont St. Michel → France
        rels = result["relations"]
        loc = [r for r in rels if r["relation"] == "located_in"]
        assert len(loc) == 1
        assert loc[0]["source"] == "Mont St. Michel"
        assert loc[0]["target"] == "France"

    def test_month_abbreviation(self):
        g = MemoryGraph()
        result = g.extract_from_text(
            "Alice joined in Jan. Bob joined in Feb. Charlie joined in Mar."
        )
        assert result["sentences"] == 3

    def test_eg_abbreviation(self):
        g = MemoryGraph()
        result = g.extract_from_text(
            "Alice likes fruit, e.g. apples. Bob likes vegetables."
        )
        assert result["sentences"] == 2


class TestNormalSplittingUnaffected:
    """Normal periods, !, ?, ;, newlines still split."""

    def test_regular_periods_split(self):
        g = MemoryGraph()
        result = g.extract_from_text(
            "Alice works at Google. Bob works at Apple."
        )
        assert result["sentences"] == 2

    def test_question_exclamation_split(self):
        g = MemoryGraph()
        result = g.extract_from_text(
            "Is Alice a person! Bob is a person? Charlie too."
        )
        assert result["sentences"] == 3

    def test_newline_split(self):
        g = MemoryGraph()
        result = g.extract_from_text(
            "Alice works at Google.\nBob works at Apple."
        )
        assert result["sentences"] == 2

    def test_semicolon_split(self):
        g = MemoryGraph()
        result = g.extract_from_text(
            "Alice works at Google; Bob works at Apple."
        )
        assert result["sentences"] == 2

    def test_period_restored_in_output(self):
        # After protection + restore, internal periods survive in labels
        g = MemoryGraph()
        g.extract_from_text("Mr. Darcy works at Pemberley.")
        found = g.search_by_label("Mr. Darcy")
        assert len(found) == 1


class TestNovelDomainPassage:
    """E2E: Novel-style passage dense with abbreviations."""

    def test_pride_and_prejudice_style(self):
        g = MemoryGraph()
        text = (
            "Mr. Darcy works at Pemberley. "
            "Mrs. Bennet has five daughters. "
            "Elizabeth is part of the Bennet Family."
        )
        result = g.extract_from_text(text)
        assert result["sentences"] == 3
        assert result["edges_created"] >= 3

    def test_mixed_abbrev_and_normal(self):
        g = MemoryGraph()
        text = (
            "Dr. Frankenstein created the Monster. "
            "The Monster is located in the Arctic. "
            "Capt. Walton recorded the tale."
        )
        result = g.extract_from_text(text)
        assert result["sentences"] == 3
        rels = result["relations"]
        assert any(r["relation"] == "created" and r["source"] == "Dr. Frankenstein" for r in rels)
        assert any(r["relation"] == "located_in" for r in rels)
