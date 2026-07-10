"""Tests for current_flow_betweenness and current_flow_closeness centrality."""

import pytest
import math
from memory_graph import MemoryGraph


def _make_complete_graph(n: int) -> MemoryGraph:
    """K_n complete graph."""
    mg = MemoryGraph()
    nodes = [mg.add(label=f"n{i}", kind="test") for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            mg.link(nodes[i].id, nodes[j].id, relation="connect", weight=1.0)
    return mg


def _make_path_graph(n: int) -> MemoryGraph:
    """P_n path graph: n0—n1—n2—...—n(n-1)."""
    mg = MemoryGraph()
    nodes = [mg.add(label=f"n{i}", kind="test") for i in range(n)]
    for i in range(n - 1):
        mg.link(nodes[i].id, nodes[i+1].id, relation="connect", weight=1.0)
    return mg


def _make_cycle_graph(n: int) -> MemoryGraph:
    """C_n cycle graph."""
    mg = MemoryGraph()
    nodes = [mg.add(label=f"n{i}", kind="test") for i in range(n)]
    for i in range(n):
        mg.link(nodes[i].id, nodes[(i+1) % n].id, relation="connect", weight=1.0)
    return mg


def _make_star_graph(n: int) -> tuple:
    """Star graph with n nodes: center n0 connected to n1..n(n-1). Returns (mg, node_ids)."""
    mg = MemoryGraph()
    nodes = [mg.add(label=f"n{i}", kind="test") for i in range(n)]
    for i in range(1, n):
        mg.link(nodes[0].id, nodes[i].id, relation="connect", weight=1.0)
    return mg, [n.id for n in nodes]


def _get_node_ids(mg, n):
    """Get first n node IDs from a MemoryGraph."""
    return [r["id"] for r in mg.conn.execute(
        "SELECT id FROM nodes ORDER BY label LIMIT ?", (n,)
    ).fetchall()]


def _get_all_node_ids(mg):
    """Get all node IDs ordered by label."""
    return [r["id"] for r in mg.conn.execute(
        "SELECT id FROM nodes ORDER BY label"
    ).fetchall()]


class TestCurrentFlowBetweenness:
    """Current-flow betweenness centrality tests."""

    def test_complete_graph_symmetric(self):
        """In K_n all nodes have equal CF betweenness by symmetry."""
        mg = _make_complete_graph(4)
        result = mg.current_flow_betweenness()
        vals = list(result.values())
        for v in vals[1:]:
            assert abs(v - vals[0]) < 1e-9, f"Expected equal CFB in K_n, got {v} vs {vals[0]}"

    def test_path_graph_endpoints_zero(self):
        """In P_4, endpoints have CF betweenness = 0 (no flow passes through them)."""
        mg = _make_path_graph(4)
        ids = _get_all_node_ids(mg)
        result = mg.current_flow_betweenness()
        # Endpoints should have ~0, middle nodes > 0
        endpoint_vals = [result[ids[0]], result[ids[3]]]
        middle_vals = [result[ids[1]], result[ids[2]]]
        for v in endpoint_vals:
            assert abs(v) < 1e-9, f"Endpoint should be ~0, got {v}"
        for v in middle_vals:
            assert v > 1e-9, f"Middle node should be >0, got {v}"

    def test_path_graph_middle_max(self):
        """In P_3, the center node has maximum CF betweenness."""
        mg = _make_path_graph(3)
        ids = _get_all_node_ids(mg)
        result = mg.current_flow_betweenness()
        assert result[ids[1]] > result[ids[0]]
        assert result[ids[1]] > result[ids[2]]
        assert result[ids[1]] == max(result.values())

    def test_star_graph_center_max(self):
        """In star graph, center has highest CF betweenness."""
        mg, ids = _make_star_graph(5)
        result = mg.current_flow_betweenness()
        assert result[ids[0]] == max(result.values()), \
            "Center should have max CF betweenness"
        for i in range(1, 5):
            assert abs(result[ids[i]]) < 1e-9, \
                f"Leaf should be ~0, got {result[ids[i]]}"

    def test_cycle_graph_symmetric(self):
        """In C_4, all nodes have equal CF betweenness."""
        mg = _make_cycle_graph(4)
        result = mg.current_flow_betweenness()
        vals = list(result.values())
        for v in vals[1:]:
            assert abs(v - vals[0]) < 1e-9

    def test_returns_all_nodes(self):
        """Result includes all nodes."""
        mg = _make_complete_graph(5)
        result = mg.current_flow_betweenness()
        assert len(result) == 5

    def test_too_few_nodes_raises(self):
        """<3 nodes should raise ValueError."""
        mg = MemoryGraph()
        n1 = mg.add(label="a", kind="t")
        n2 = mg.add(label="b", kind="t")
        mg.link(n1.id, n2.id, relation="r", weight=1.0)
        with pytest.raises(ValueError, match=">= 3 nodes"):
            mg.current_flow_betweenness()

    def test_normalized_range(self):
        """Normalized scores should be in [0, 1]."""
        mg = _make_path_graph(6)
        result = mg.current_flow_betweenness(normalized=True)
        for v in result.values():
            assert -1e-9 <= v <= 1.0 + 1e-9

    def test_unnormalized(self):
        """Unnormalized scores should be >= 0."""
        mg = _make_path_graph(5)
        result = mg.current_flow_betweenness(normalized=False)
        for v in result.values():
            assert v >= -1e-9

    def test_triangle_complete(self):
        """K_3 (triangle): all nodes have equal CFB by symmetry."""
        mg = _make_complete_graph(3)
        result = mg.current_flow_betweenness()
        vals = list(result.values())
        for v in vals[1:]:
            assert abs(v - vals[0]) < 1e-9

    def test_bridging_node(self):
        """Node bridging two clusters has high CFB."""
        mg = MemoryGraph()
        a = mg.add(label="a"); b = mg.add(label="b"); c = mg.add(label="c")
        d = mg.add(label="d"); e = mg.add(label="e"); f_node = mg.add(label="f")
        mg.link(a.id, b.id, "r"); mg.link(b.id, c.id, "r")
        mg.link(c.id, d.id, "r")  # bridge
        mg.link(d.id, e.id, "r"); mg.link(e.id, f_node.id, "r")
        result = mg.current_flow_betweenness()
        assert result[c.id] > result[a.id]
        assert result[d.id] > result[f_node.id]

    def test_include_quarantined(self):
        """include_quarantined=True includes quarantined nodes."""
        mg = _make_path_graph(4)
        ids = _get_all_node_ids(mg)
        mg.node_quarantine(ids[1])
        result_default = mg.current_flow_betweenness()
        result_all = mg.current_flow_betweenness(include_quarantined=True)
        assert len(result_all) > len(result_default)

    def test_path5_symmetric_middle(self):
        """In P_5, nodes n1 and n3 (symmetric positions) have equal CFB."""
        mg = _make_path_graph(5)
        ids = _get_all_node_ids(mg)
        result = mg.current_flow_betweenness()
        assert abs(result[ids[1]] - result[ids[3]]) < 1e-9

    def test_center_highest_path5(self):
        """In P_5, center node n2 has highest CFB."""
        mg = _make_path_graph(5)
        ids = _get_all_node_ids(mg)
        result = mg.current_flow_betweenness()
        assert result[ids[2]] == max(result.values())


class TestCurrentFlowCloseness:
    """Current-flow closeness centrality tests."""

    def test_complete_graph_symmetric(self):
        """K_n: all nodes have equal CFC."""
        mg = _make_complete_graph(4)
        result = mg.current_flow_closeness()
        vals = list(result.values())
        for v in vals[1:]:
            assert abs(v - vals[0]) < 1e-9

    def test_complete_graph_value(self):
        """K_4: R = 2/4 = 0.5 for each pair. CFC = 3 / (3*0.5) = 2.0."""
        mg = _make_complete_graph(4)
        result = mg.current_flow_closeness()
        for v in result.values():
            assert abs(v - 2.0) < 0.01

    def test_path_graph_endpoints_min(self):
        """P_4: endpoints have lower CFC than middle nodes."""
        mg = _make_path_graph(4)
        ids = _get_all_node_ids(mg)
        result = mg.current_flow_closeness()
        assert result[ids[1]] > result[ids[0]]
        assert result[ids[2]] > result[ids[3]]

    def test_path_graph_center_max(self):
        """P_3: center node has highest CFC."""
        mg = _make_path_graph(3)
        ids = _get_all_node_ids(mg)
        result = mg.current_flow_closeness()
        assert result[ids[1]] == max(result.values())

    def test_star_graph_center_max(self):
        """Star: center has highest CFC."""
        mg, ids = _make_star_graph(5)
        result = mg.current_flow_closeness()
        assert result[ids[0]] == max(result.values())

    def test_cycle_graph_symmetric(self):
        """C_4: all nodes equal CFC."""
        mg = _make_cycle_graph(4)
        result = mg.current_flow_closeness()
        vals = list(result.values())
        for v in vals[1:]:
            assert abs(v - vals[0]) < 1e-9

    def test_returns_all_nodes(self):
        """Result includes all nodes."""
        mg = _make_complete_graph(5)
        result = mg.current_flow_closeness()
        assert len(result) == 5

    def test_too_few_nodes_raises(self):
        """<2 nodes should raise ValueError."""
        mg = MemoryGraph()
        mg.add(label="a", kind="t")
        with pytest.raises(ValueError, match=">= 2 nodes"):
            mg.current_flow_closeness()

    def test_positive_scores(self):
        """All CFC scores should be positive for connected graph."""
        mg = _make_path_graph(5)
        result = mg.current_flow_closeness()
        for v in result.values():
            assert v > 0

    def test_triangle(self):
        """K_3: CFC = 3/2 = 1.5."""
        mg = _make_complete_graph(3)
        result = mg.current_flow_closeness()
        for v in result.values():
            assert abs(v - 1.5) < 0.01

    def test_include_quarantined(self):
        """include_quarantined includes quarantined nodes."""
        mg = _make_complete_graph(4)
        ids = _get_all_node_ids(mg)
        mg.node_quarantine(ids[0])
        result_default = mg.current_flow_closeness()
        result_all = mg.current_flow_closeness(include_quarantined=True)
        assert len(result_all) >= len(result_default)

    def test_monotonic_path(self):
        """In P_5, center node n2 has higher CFC than endpoints."""
        mg = _make_path_graph(5)
        ids = _get_all_node_ids(mg)
        result = mg.current_flow_closeness()
        assert result[ids[2]] > result[ids[0]]
        assert result[ids[2]] > result[ids[4]]

    def test_star_leaves_equal(self):
        """Star graph leaves have equal CFC."""
        mg, ids = _make_star_graph(5)
        result = mg.current_flow_closeness()
        for i in range(2, 5):
            assert abs(result[ids[i]] - result[ids[1]]) < 1e-9
