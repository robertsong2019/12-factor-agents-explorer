"""Tests for relation coverage dimension in graphrag_coverage_report().

Cycle 435: Adds edge-relation analytics to the KG-wide health report —
relation distribution, typed-edge rate, relation diversity, top relations,
and a targeted suggestion when edges lack relation types.
"""

import pytest
from memory_graph import MemoryGraph


def _build_basic():
    mg = MemoryGraph()
    a = mg.add("Python", "skill")
    b = mg.add("Rust", "skill")
    c = mg.add("Guido", "person")
    return mg, a, b, c


class TestRelationDistribution:
    """Relation type distribution across edges."""

    def test_all_typed(self):
        mg, a, b, c = _build_basic()
        mg.link(a.id, b.id, "similar_to")
        mg.link(c.id, a.id, "created")
        r = mg.graphrag_coverage_report()
        assert r["relation_distribution"] == {"similar_to": 1, "created": 1}

    def test_counts_aggregated(self):
        mg, a, b, c = _build_basic()
        mg.link(a.id, b.id, "similar_to")
        mg.link(a.id, c.id, "similar_to")
        mg.link(c.id, b.id, "similar_to")
        r = mg.graphrag_coverage_report()
        assert r["relation_distribution"]["similar_to"] == 3

    def test_no_edges_empty_dict(self):
        mg = MemoryGraph()
        mg.add("Python", "skill")
        r = mg.graphrag_coverage_report()
        assert r["relation_distribution"] == {}

    def test_empty_graph_empty_dict(self):
        mg = MemoryGraph()
        r = mg.graphrag_coverage_report()
        assert r["relation_distribution"] == {}


class TestTypedEdgeRate:
    """Fraction of edges carrying a non-empty relation type."""

    def test_all_typed_rate_one(self):
        mg, a, b, c = _build_basic()
        mg.link(a.id, b.id, "similar_to")
        mg.link(c.id, a.id, "created")
        r = mg.graphrag_coverage_report()
        assert r["typed_edge_rate"] == 1.0
        assert r["untyped_edge_count"] == 0

    def test_partial_rate(self):
        mg, a, b, c = _build_basic()
        mg.link(a.id, b.id, "similar_to")
        mg.link(c.id, a.id, "")  # untyped
        r = mg.graphrag_coverage_report()
        assert r["typed_edge_rate"] == pytest.approx(0.5, abs=0.01)
        assert r["untyped_edge_count"] == 1

    def test_all_untyped_rate_zero(self):
        mg, a, b, c = _build_basic()
        mg.link(a.id, b.id, "")
        mg.link(c.id, a.id, "")
        r = mg.graphrag_coverage_report()
        assert r["typed_edge_rate"] == 0.0
        assert r["untyped_edge_count"] == 2

    def test_empty_graph_zero(self):
        mg = MemoryGraph()
        r = mg.graphrag_coverage_report()
        assert r["typed_edge_rate"] == 0.0
        assert r["untyped_edge_count"] == 0

    def test_null_relation_counted_untyped(self):
        mg, a, b, c = _build_basic()
        mg.link(a.id, b.id, "similar_to")
        mg.conn.execute(
            "INSERT INTO edges (source, target, relation) VALUES (?,?,NULL)",
            (a.id, c.id),
        )
        mg.conn.commit()
        r = mg.graphrag_coverage_report()
        assert r["untyped_edge_count"] == 1
        assert r["typed_edge_rate"] == pytest.approx(0.5, abs=0.01)


class TestRelationDiversity:
    """Unique relations / total edges, capped at 1.0."""

    def test_max_diversity(self):
        mg, a, b, c = _build_basic()
        mg.link(a.id, b.id, "similar_to")
        mg.link(c.id, a.id, "created")
        r = mg.graphrag_coverage_report()
        assert r["relation_diversity"] == 1.0

    def test_low_diversity(self):
        mg, a, b, c = _build_basic()
        mg.link(a.id, b.id, "related")
        mg.link(a.id, c.id, "related")
        r = mg.graphrag_coverage_report()
        assert r["relation_diversity"] == pytest.approx(0.5, abs=0.01)

    def test_empty_graph_zero(self):
        mg = MemoryGraph()
        r = mg.graphrag_coverage_report()
        assert r["relation_diversity"] == 0.0


class TestTopRelations:
    """Most frequent relation types, sorted descending."""

    def test_sorted_desc(self):
        mg, a, b, c = _build_basic()
        mg.link(a.id, b.id, "rare")
        mg.link(a.id, c.id, "common")
        mg.link(c.id, b.id, "common")
        r = mg.graphrag_coverage_report()
        assert r["top_relations"][0] == ("common", 2)
        assert r["top_relations"][1] == ("rare", 1)

    def test_capped_at_ten(self):
        mg = MemoryGraph()
        nodes = [mg.add(f"n{i}", "thing") for i in range(12)]
        hub = mg.add("hub", "thing")
        for i, n in enumerate(nodes):
            mg.link(hub.id, n.id, f"rel_{i:02d}")
        r = mg.graphrag_coverage_report()
        assert len(r["top_relations"]) == 10

    def test_empty_list_no_edges(self):
        mg = MemoryGraph()
        mg.add("Python", "skill")
        r = mg.graphrag_coverage_report()
        assert r["top_relations"] == []


class TestRelationSuggestions:
    """Context-aware suggestions for relation coverage."""

    def test_low_typed_rate_suggestion(self):
        mg, a, b, c = _build_basic()
        mg.link(a.id, b.id, "similar_to")
        mg.link(c.id, a.id, "")
        r = mg.graphrag_coverage_report()
        assert any("relation" in s.lower() for s in r["suggestions"])

    def test_good_typed_edges_no_relation_suggestion(self):
        mg, a, b, c = _build_basic()
        mg.link(a.id, b.id, "similar_to")
        mg.link(c.id, a.id, "created")
        r = mg.graphrag_coverage_report()
        assert not any(
            "relation type" in s.lower() for s in r["suggestions"]
        )


class TestRelationFieldsSchema:
    """New fields appear in the report schema."""

    def test_new_keys_present(self):
        mg, a, b, c = _build_basic()
        mg.link(a.id, b.id, "similar_to")
        r = mg.graphrag_coverage_report()
        for key in (
            "relation_distribution",
            "typed_edge_rate",
            "untyped_edge_count",
            "relation_diversity",
            "top_relations",
        ):
            assert key in r, f"missing key: {key}"

    def test_health_score_still_reasonable(self):
        """Relation fields must not break existing composite score range."""
        mg, a, b, c = _build_basic()
        mg.link(a.id, b.id, "similar_to")
        mg.link(c.id, a.id, "created")
        r = mg.graphrag_coverage_report()
        assert 0.0 <= r["health_score"] <= 1.0
