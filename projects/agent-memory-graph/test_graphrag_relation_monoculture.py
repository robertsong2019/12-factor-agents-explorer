"""Tests for relation monoculture warning in graphrag_coverage_report().

Cycle 436: When one relation type dominates the KG (e.g. everything is
"related_to"), fact-style answers lose discriminative power. The report
now flags monoculture graphs and suggests diversifying relation types.
"""

import pytest
from memory_graph import MemoryGraph


def _build(nodes_n: int = 8):
    mg = MemoryGraph()
    ns = [mg.add(f"node{i}", "thing") for i in range(nodes_n)]
    return mg, ns


class TestMonocultureSuggestion:
    """Warning when a single relation dominates."""

    def test_monoculture_flagged(self):
        mg, ns = _build()
        hub = ns[0]
        for n in ns[1:]:
            mg.link(hub.id, n.id, "related_to")
        r = mg.graphrag_coverage_report()
        assert any("diversif" in s.lower() for s in r["suggestions"])

    def test_diverse_not_flagged(self):
        mg, ns = _build()
        mg.link(ns[0].id, ns[1].id, "created")
        mg.link(ns[0].id, ns[2].id, "similar_to")
        mg.link(ns[1].id, ns[3].id, "depends_on")
        mg.link(ns[2].id, ns[4].id, "part_of")
        r = mg.graphrag_coverage_report()
        monoculture_suggestions = [
            s for s in r["suggestions"]
            if "dominates" in s.lower() or "diversif" in s.lower()
        ]
        assert not monoculture_suggestions

    def test_small_graph_not_flagged(self):
        """< 5 typed edges: too little data to call monoculture."""
        mg, ns = _build(4)
        mg.link(ns[0].id, ns[1].id, "related_to")
        mg.link(ns[0].id, ns[2].id, "related_to")
        mg.link(ns[1].id, ns[3].id, "related_to")
        r = mg.graphrag_coverage_report()
        assert not any("diversif" in s.lower() for s in r["suggestions"])

    def test_majority_but_below_threshold_not_flagged(self):
        """70% one relation across 10 edges (threshold 80%) — no warning."""
        mg, ns = _build(11)
        mg.link(ns[0].id, ns[1].id, "main")
        mg.link(ns[0].id, ns[2].id, "main")
        mg.link(ns[0].id, ns[3].id, "main")
        mg.link(ns[0].id, ns[4].id, "main")
        mg.link(ns[0].id, ns[5].id, "main")
        mg.link(ns[0].id, ns[6].id, "main")
        mg.link(ns[0].id, ns[7].id, "main")
        mg.link(ns[1].id, ns[8].id, "other_a")
        mg.link(ns[2].id, ns[9].id, "other_b")
        mg.link(ns[3].id, ns[10].id, "other_c")
        r = mg.graphrag_coverage_report()
        assert not any("diversif" in s.lower() for s in r["suggestions"])

    def test_warning_mentions_dominant_relation(self):
        mg, ns = _build()
        hub = ns[0]
        for n in ns[1:]:
            mg.link(hub.id, n.id, "generic_link")
        r = mg.graphrag_coverage_report()
        warn = [s for s in r["suggestions"] if "generic_link" in s]
        assert warn, "warning should name the dominant relation"


class TestDominantRelationField:
    """Optional structured field for programmatic consumers."""

    def test_dominant_relation_reported(self):
        mg, ns = _build()
        hub = ns[0]
        for n in ns[1:]:
            mg.link(hub.id, n.id, "related_to")
        r = mg.graphrag_coverage_report()
        assert r["dominant_relation"] == "related_to"

    def test_dominant_relation_none_when_no_edges(self):
        mg = MemoryGraph()
        mg.add("solo", "thing")
        r = mg.graphrag_coverage_report()
        assert r["dominant_relation"] is None
