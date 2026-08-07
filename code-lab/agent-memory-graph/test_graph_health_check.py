"""Tests for graph_health_check() — unified diagnostic."""
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def healthy_graph():
    """Well-connected multi-kind graph."""
    g = MemoryGraph()
    a = g.add("a", kind="fact")
    b = g.add("b", kind="task")
    c = g.add("c", kind="idea")
    d = g.add("d", kind="fact")
    g.link(a.id, b.id, "rel")
    g.link(b.id, c.id, "rel")
    g.link(c.id, d.id, "rel")
    g.link(d.id, a.id, "rel")
    return g


@pytest.fixture
def empty_graph():
    return MemoryGraph()


@pytest.fixture
def sparse_graph():
    """Only isolated nodes, no edges."""
    g = MemoryGraph()
    g.add("n1", kind="fact")
    g.add("n2", kind="fact")
    return g


class TestGraphHealthCheck:

    def test_basic_structure(self, healthy_graph):
        r = healthy_graph.graph_health_check()
        for key in ("overall_status", "score", "checks", "summary"):
            assert key in r

    def test_overall_status_values(self, healthy_graph):
        r = healthy_graph.graph_health_check()
        assert r["overall_status"] in ("healthy", "warning", "critical")

    def test_score_range(self, healthy_graph):
        r = healthy_graph.graph_health_check()
        assert 0 <= r["score"] <= 100

    def test_checks_list(self, healthy_graph):
        r = healthy_graph.graph_health_check()
        assert isinstance(r["checks"], list)
        assert len(r["checks"]) >= 5
        for c in r["checks"]:
            assert "name" in c
            assert "status" in c
            assert "value" in c
            assert "detail" in c

    def test_summary_is_string(self, healthy_graph):
        r = healthy_graph.graph_health_check()
        assert isinstance(r["summary"], str)

    def test_healthy_graph_scores_well(self, healthy_graph):
        r = healthy_graph.graph_health_check()
        assert r["overall_status"] in ("healthy", "warning")
        assert r["score"] >= 50

    def test_empty_graph_critical(self, empty_graph):
        r = empty_graph.graph_health_check()
        # Empty graph should have low score
        assert r["overall_status"] in ("warning", "critical")
        assert r["score"] < 70

    def test_sparse_graph_warning(self, sparse_graph):
        """Isolated nodes → isolation warning."""
        r = sparse_graph.graph_health_check()
        iso_check = [c for c in r["checks"] if c["name"] == "isolation_ratio"]
        assert len(iso_check) == 1
        assert iso_check[0]["status"] == "warning"

    def test_check_names(self, healthy_graph):
        r = healthy_graph.graph_health_check()
        names = {c["name"] for c in r["checks"]}
        assert "has_nodes" in names
        assert "edge_density" in names
        assert "connectivity" in names
        assert "kind_diversity" in names
        assert "avg_weight" in names
        assert "isolation_ratio" in names

    def test_status_values(self, healthy_graph):
        r = healthy_graph.graph_health_check()
        for c in r["checks"]:
            assert c["status"] in ("pass", "warning", "critical", "fail")

    def test_single_node(self):
        g = MemoryGraph()
        g.add("only")
        r = g.graph_health_check()
        assert r["score"] >= 0
        # Single node has no edges → density check should be warning/ok
        dens = [c for c in r["checks"] if c["name"] == "edge_density"][0]
        assert dens["status"] in ("warning", "pass")

    def test_dense_graph_warning(self):
        """Complete graph → density warning (>0.8)."""
        g = MemoryGraph()
        nodes = [g.add(f"n{i}") for i in range(4)]
        for i in range(4):
            for j in range(i + 1, 4):
                g.link(nodes[i].id, nodes[j].id, "rel")
        r = g.graph_health_check()
        dens = [c for c in r["checks"] if c["name"] == "edge_density"][0]
        assert dens["value"] > 0.8

    def test_summary_mentions_failed(self, sparse_graph):
        """When checks fail, summary should list them."""
        r = sparse_graph.graph_health_check()
        failed = [c for c in r["checks"] if c["status"] != "pass"]
        if failed:
            assert "attention" in r["summary"] or "warning" in r["summary"].lower()

    def test_overall_critical_on_critical(self):
        """Any critical check → overall critical."""
        g = MemoryGraph()
        n = g.add("n1")
        # Manually set weight to 0 to trigger critical
        g.conn.execute("UPDATE nodes SET weight=0.01 WHERE id=?", (n.id,))
        g.conn.commit()
        r = g.graph_health_check()
        w_check = [c for c in r["checks"] if c["name"] == "avg_weight"][0]
        assert w_check["status"] == "critical"
        assert r["overall_status"] == "critical"

    def test_all_pass_summary(self, healthy_graph):
        """If all pass, summary says 'All N checks passed'."""
        r = healthy_graph.graph_health_check()
        all_pass = all(c["status"] == "pass" for c in r["checks"])
        if all_pass:
            assert "All" in r["summary"] and "passed" in r["summary"]
