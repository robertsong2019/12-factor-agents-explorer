import pytest
from memory_graph import MemoryGraph

@pytest.fixture
def g():
    return MemoryGraph(":memory:")

class TestEdgeTypeStats:
    def test_empty_graph(self, g):
        result = g.edge_type_stats()
        assert result == {}

    def test_single_relation(self, g):
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.link_by_label("a", "b", "rel1", weight=2.0)
        result = g.edge_type_stats()
        assert "rel1" in result
        assert result["rel1"]["count"] == 1
        assert result["rel1"]["avg_weight"] == 2.0
        assert result["rel1"]["unique_sources"] == 1
        assert result["rel1"]["unique_targets"] == 1
        assert result["rel1"]["reciprocity"] == 0.0

    def test_multiple_relations(self, g):
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.add("c", kind="fact")
        g.link_by_label("a", "b", "rel1", weight=1.0)
        g.link_by_label("a", "c", "rel2", weight=3.0)
        g.link_by_label("b", "c", "rel1", weight=5.0)
        result = g.edge_type_stats()
        assert len(result) == 2
        assert result["rel1"]["count"] == 2
        assert result["rel2"]["count"] == 1
        assert result["rel1"]["min_weight"] == 1.0
        assert result["rel1"]["max_weight"] == 5.0

    def test_reciprocity_detected(self, g):
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.add("c", kind="fact")
        g.link_by_label("a", "b", "rel1")
        g.link_by_label("b", "a", "rel1")
        g.link_by_label("b", "c", "rel1")
        result = g.edge_type_stats()
        assert result["rel1"]["reciprocity"] == pytest.approx(2/3, abs=0.01)

    def test_reciprocity_zero_no_reverse(self, g):
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.add("c", kind="fact")
        g.link_by_label("a", "b", "rel1")
        g.link_by_label("a", "c", "rel1")
        result = g.edge_type_stats()
        assert result["rel1"]["reciprocity"] == 0.0

    def test_weight_stats(self, g):
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.add("c", kind="fact")
        g.link_by_label("a", "b", "rel1", weight=0.5)
        g.link_by_label("a", "c", "rel1", weight=1.5)
        r = g.edge_type_stats()["rel1"]
        assert r["min_weight"] == 0.5
        assert r["max_weight"] == 1.5
        assert r["avg_weight"] == 1.0

    def test_unique_sources_targets(self, g):
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.add("c", kind="fact")
        g.link_by_label("a", "b", "rel1")
        g.link_by_label("a", "c", "rel1")
        r = g.edge_type_stats()["rel1"]
        assert r["unique_sources"] == 1  # only a
        assert r["unique_targets"] == 2  # b and c

    def test_result_types(self, g):
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.link_by_label("a", "b", "rel1")
        r = g.edge_type_stats()["rel1"]
        assert isinstance(r["count"], int)
        assert isinstance(r["avg_weight"], float)
        assert isinstance(r["reciprocity"], float)

    def test_multiple_edges_same_pair(self, g):
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.link_by_label("a", "b", "rel1")
        g.link_by_label("a", "b", "rel2")
        result = g.edge_type_stats()
        assert len(result) == 2
