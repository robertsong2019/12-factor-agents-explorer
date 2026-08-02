"""Test hub_nodes, peripheral_nodes, mean_degree for MemoryGraph."""
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def graph():
    g = MemoryGraph(":memory:")
    return g


class TestHubNodes:
    def test_empty_graph(self, graph):
        assert graph.hub_nodes() == []

    def test_returns_top_n(self, graph):
        center = graph.add("center", kind="hub")
        leaves = [graph.add(f"leaf{i}", kind="data") for i in range(4)]
        for leaf in leaves:
            graph.link(center.id, leaf.id, "related")
        hubs = graph.hub_nodes(2)
        assert hubs[0][0] == center.id
        assert hubs[0][1] == 4  # degree 4
        assert len(hubs) == 2

    def test_default_n_is_10(self, graph):
        nodes = [graph.add(f"n{i}", kind="data") for i in range(15)]
        for i in range(14):
            graph.link(nodes[i].id, nodes[14].id, "related")  # n14 gets degree 14
        hubs = graph.hub_nodes()
        assert len(hubs) == 10
        assert hubs[0][0] == nodes[14].id

    def test_ties_broken_by_weight(self, graph):
        a = graph.add("a", kind="x")
        b = graph.add("b", kind="x")
        graph.link(a.id, b.id, "related")
        hubs = graph.hub_nodes(5)
        assert len(hubs) == 2
        degrees = [d for _, d in hubs]
        assert all(d == 1 for d in degrees)


class TestPeripheralNodes:
    def test_empty_graph(self, graph):
        assert graph.peripheral_nodes() == []

    def test_star_graph_finds_leaves(self, graph):
        center = graph.add("center")
        leaves = [graph.add(f"l{i}") for i in range(4)]
        for leaf in leaves:
            graph.link(center.id, leaf.id, "related")
        periph = set(graph.peripheral_nodes())
        assert periph == {leaf.id for leaf in leaves}
        assert center.id not in periph

    def test_isolated_nodes_excluded(self, graph):
        graph.add("iso")  # degree 0
        a = graph.add("a")
        b = graph.add("b")
        graph.link(a.id, b.id, "related")
        periph = set(graph.peripheral_nodes())
        assert periph == {a.id, b.id}

    def test_high_degree_excluded(self, graph):
        hub = graph.add("hub")
        a = graph.add("a")
        b = graph.add("b")
        graph.link(hub.id, a.id, "related")
        graph.link(hub.id, b.id, "related")
        periph = set(graph.peripheral_nodes())
        assert hub.id not in periph
        assert a.id in periph
        assert b.id in periph


class TestMeanDegree:
    def test_empty_graph(self, graph):
        assert graph.mean_degree() == 0.0

    def test_single_edge(self, graph):
        a = graph.add("a")
        b = graph.add("b")
        graph.link(a.id, b.id, "related")
        # Each node has degree 1, mean = 1.0
        assert graph.mean_degree() == 1.0

    def test_star_graph(self, graph):
        center = graph.add("center")
        leaves = [graph.add(f"l{i}") for i in range(4)]
        for leaf in leaves:
            graph.link(center.id, leaf.id, "related")
        # center: degree 4, leaves: degree 1 each (x4)
        # mean = (4 + 1*4) / 5 = 8/5 = 1.6
        assert graph.mean_degree() == pytest.approx(1.6)

    def test_no_edges(self, graph):
        for i in range(5):
            graph.add(f"n{i}")
        assert graph.mean_degree() == 0.0

    def test_complete_triangle(self, graph):
        a = graph.add("a")
        b = graph.add("b")
        c = graph.add("c")
        graph.link(a.id, b.id, "related")
        graph.link(b.id, c.id, "related")
        graph.link(a.id, c.id, "related")
        # Each has degree 2, mean = 2.0
        assert graph.mean_degree() == 2.0
