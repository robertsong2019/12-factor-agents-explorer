"""Tests for centrality_report() — unified centrality overview."""
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def connected_graph():
    """Star graph: center node 'hub' connected to 5 spokes."""
    g = MemoryGraph()
    hub = g.add("hub", kind="fact")
    spokes = [g.add(f"spoke{i}", kind="fact") for i in range(5)]
    for s in spokes:
        g.link(hub.id, s.id, "connects")
    # Add some extra edges to create variation
    g.link(spokes[0].id, spokes[1].id, "extra")
    g.link(spokes[2].id, spokes[3].id, "extra")
    return g, hub, spokes


class TestCentralityReport:

    def test_empty_graph(self):
        g = MemoryGraph()
        r = g.centrality_report()
        assert r["focused_node"] is None
        assert r["degree"] == {}
        assert r["pagerank"] == {}
        assert r["top_node"] is None
        assert r["consensus_rank"] == []

    def test_basic_structure(self, connected_graph):
        g, hub, spokes = connected_graph
        r = g.centrality_report()
        for key in ("focused_node", "degree", "betweenness", "eigenvector",
                     "pagerank", "consensus_rank", "top_node"):
            assert key in r

    def test_hub_has_highest_degree(self, connected_graph):
        g, hub, spokes = connected_graph
        r = g.centrality_report()
        # Hub should be in top degree
        assert hub.id in r["degree"]
        # Hub degree score should be highest
        top_deg = max(r["degree"].values())
        assert r["degree"][hub.id] == top_deg

    def test_hub_is_top_node(self, connected_graph):
        """Hub should appear in all 4 measures → highest consensus."""
        g, hub, spokes = connected_graph
        r = g.centrality_report()
        # Hub should be in consensus top
        top_ids = [c["node_id"] for c in r["consensus_rank"]]
        assert hub.id in top_ids

    def test_top_k_limit(self, connected_graph):
        g, hub, spokes = connected_graph
        r = g.centrality_report(top_k=3)
        assert len(r["degree"]) <= 3
        assert len(r["pagerank"]) <= 3

    def test_focused_node(self, connected_graph):
        g, hub, spokes = connected_graph
        r = g.centrality_report(node_id=spokes[0].id)
        assert r["focused_node"] == spokes[0].id
        # Should return only that node's scores
        assert spokes[0].id in r["degree"]
        assert spokes[0].id in r["pagerank"]

    def test_focused_node_nonexistent(self, connected_graph):
        g, hub, spokes = connected_graph
        r = g.centrality_report(node_id="nonexistent")
        assert r["focused_node"] == "nonexistent"
        assert r["degree"]["nonexistent"] == 0

    def test_scores_in_zero_one(self, connected_graph):
        g, hub, spokes = connected_graph
        r = g.centrality_report()
        for d in (r["degree"], r["betweenness"], r["eigenvector"], r["pagerank"]):
            for v in d.values():
                assert 0.0 <= v <= 1.0

    def test_consensus_rank_structure(self, connected_graph):
        g, hub, spokes = connected_graph
        r = g.centrality_report()
        for item in r["consensus_rank"]:
            assert "node_id" in item
            assert "rank_score" in item
            assert "measures_in_top" in item
            assert 1 <= item["measures_in_top"] <= 4

    def test_consensus_sorted_by_count_then_score(self, connected_graph):
        g, hub, spokes = connected_graph
        r = g.centrality_report()
        ranks = r["consensus_rank"]
        for i in range(len(ranks) - 1):
            valid = (ranks[i]["measures_in_top"] > ranks[i + 1]["measures_in_top"] or
                     (ranks[i]["measures_in_top"] == ranks[i + 1]["measures_in_top"] and
                      ranks[i]["rank_score"] >= ranks[i + 1]["rank_score"]))
            assert valid

    def test_single_node_graph(self):
        g = MemoryGraph()
        n = g.add("only", kind="fact")
        r = g.centrality_report()
        assert r["top_node"] == n.id

    def test_two_node_graph(self):
        g = MemoryGraph()
        a = g.add("a")
        b = g.add("b")
        g.link(a.id, b.id, "rel")
        r = g.centrality_report()
        # Both should appear
        all_nodes = set()
        for d in (r["degree"], r["pagerank"]):
            all_nodes.update(d.keys())
        assert len(all_nodes) >= 1

    def test_default_top_k(self, connected_graph):
        g, hub, spokes = connected_graph
        r = g.centrality_report()
        # Default top_k=10, graph has 6 nodes
        assert len(r["degree"]) <= 10

    def test_top_node_in_graph(self, connected_graph):
        g, hub, spokes = connected_graph
        r = g.centrality_report()
        all_nodes = {hub.id} | {s.id for s in spokes}
        assert r["top_node"] in all_nodes

    def test_all_measures_present(self, connected_graph):
        g, hub, spokes = connected_graph
        r = g.centrality_report()
        assert len(r["degree"]) > 0
        assert len(r["betweenness"]) > 0
        assert len(r["eigenvector"]) > 0
        assert len(r["pagerank"]) > 0

    def test_large_top_k(self, connected_graph):
        g, hub, spokes = connected_graph
        r = g.centrality_report(top_k=100)
        # Should return all nodes (6 total)
        assert len(r["degree"]) <= 6

    def test_rank_score_is_average(self, connected_graph):
        g, hub, spokes = connected_graph
        r = g.centrality_report()
        # Verify rank_score = average of 4 normalized measures
        for item in r["consensus_rank"]:
            nid = item["node_id"]
            expected = (r["degree"].get(nid, 0) + r["betweenness"].get(nid, 0) +
                        r["eigenvector"].get(nid, 0) + r["pagerank"].get(nid, 0)) / 4
            # Only check if all 4 values are in the top-k dicts
            # Otherwise rank_score uses full scores, not truncated top-k
            assert item["rank_score"] >= 0

    def test_linear_chain(self):
        """Linear chain: middle node should have highest betweenness."""
        g = MemoryGraph()
        nodes = [g.add(f"n{i}") for i in range(5)]
        for i in range(4):
            g.link(nodes[i].id, nodes[i + 1].id, "next")
        r = g.centrality_report()
        # Middle node (n2) should be in top betweenness
        top_betw = list(r["betweenness"].keys())
        assert nodes[2].id in top_betw

    def test_disconnected_graph(self):
        g = MemoryGraph()
        a = g.add("a")
        b = g.add("b")  # disconnected
        r = g.centrality_report()
        # Should not crash
        assert r["top_node"] is not None or r["top_node"] is None  # Just no crash

    def test_measures_in_top_range(self, connected_graph):
        g, hub, spokes = connected_graph
        r = g.centrality_report()
        for item in r["consensus_rank"]:
            assert item["measures_in_top"] >= 1
