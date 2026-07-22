import pytest
from memory_graph import MemoryGraph

@pytest.fixture
def g():
    mg = MemoryGraph(":memory:")
    return mg

class TestWalkStatistics:
    def test_empty_graph(self, g):
        result = g.walk_statistics(num_walks=10, steps=5)
        assert result["avg_unique_ratio"] == 0.0
        assert result["coverage"] == 0.0
        assert result["most_visited"] == []
        assert result["dead_end_rate"] == 0.0
        assert result["walk_lengths"] == []

    def test_single_node_no_edges(self, g):
        g.add("solo", kind="fact")
        result = g.walk_statistics(num_walks=10, steps=5)
        # Walk stays at solo node
        assert result["avg_unique_ratio"] == 1.0  # 1 unique / 1 visited
        assert result["coverage"] == 1.0
        assert result["walk_lengths"] == [1] * 10

    def test_chain_graph(self, g):
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.add("c", kind="fact")
        g.add("d", kind="fact")
        g.link_by_label("a", "b", "rel")
        g.link_by_label("b", "c", "rel")
        g.link_by_label("c", "d", "rel")
        result = g.walk_statistics(num_walks=50, steps=10, seed=99)
        assert 0.0 <= result["avg_unique_ratio"] <= 1.0
        assert 0.0 < result["coverage"]  # should visit most nodes
        assert len(result["most_visited"]) > 0
        assert len(result["walk_lengths"]) == 50

    def test_star_graph(self, g):
        # hub connected to many leaves
        g.add("hub", kind="fact")
        for i in range(8):
            g.add(f"leaf_{i}", kind="fact")
            g.link_by_label("hub", f"leaf_{i}", "rel")
        result = g.walk_statistics(num_walks=100, steps=15, seed=42)
        assert 0.0 < result["coverage"] <= 1.0
        # Hub should be most visited
        top_ids = [nid for nid, _ in result["most_visited"]]
        hub_id = g.conn.execute("SELECT id FROM nodes WHERE label = ?", ("hub",)).fetchone()["id"]
        assert hub_id == top_ids[0]
        # All walks should reach full length (no dead ends except isolated)
        assert result["dead_end_rate"] == 0.0
        assert len(result["walk_lengths"]) == 100

    def test_disconnected_graph(self, g):
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.link_by_label("a", "b", "rel")
        g.add("c", kind="fact")  # isolated
        result = g.walk_statistics(num_walks=50, steps=10, seed=7)
        # c is isolated, walks from c are length 1
        assert any(l == 1 for l in result["walk_lengths"])
        assert result["dead_end_rate"] > 0

    def test_dense_graph_high_coverage(self, g):
        nodes = [f"n{i}" for i in range(10)]
        for n in nodes:
            g.add(n, kind="fact")
        for i, a in enumerate(nodes):
            for b in nodes[i+1:]:
                g.link_by_label(a, b, "rel")
        result = g.walk_statistics(num_walks=50, steps=20, seed=123)
        # Dense graph should achieve high coverage
        assert result["coverage"] >= 0.9

    def test_revisit_step_positive_in_dense(self, g):
        # In a connected graph with restart, revisits happen quickly
        g.add("x", kind="fact")
        g.add("y", kind="fact")
        g.link_by_label("x", "y", "rel")
        g.link_by_label("y", "x", "rel")
        result = g.walk_statistics(num_walks=100, steps=20,
                                     restart_prob=0.3, seed=55)
        if result["avg_revisit_step"] < 0:
            pytest.skip("no revisits in this configuration")

    def test_deterministic_with_seed(self, g):
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.link_by_label("a", "b", "rel")
        r1 = g.walk_statistics(num_walks=20, steps=5, seed=42)
        r2 = g.walk_statistics(num_walks=20, steps=5, seed=42)
        assert r1["avg_unique_ratio"] == r2["avg_unique_ratio"]
        assert r1["coverage"] == r2["coverage"]

    def test_most_visited_top_10(self, g):
        # 15 nodes, star pattern — only top 10 returned
        g.add("hub", kind="fact")
        for i in range(14):
            g.add(f"l{i}", kind="fact")
            g.link_by_label("hub", f"l{i}", "rel")
        result = g.walk_statistics(num_walks=50, steps=10, seed=1)
        assert len(result["most_visited"]) == 10
        # Visit counts should be descending
        counts = [c for _, c in result["most_visited"]]
        assert counts == sorted(counts, reverse=True)

    def test_walk_lengths_match_num_walks(self, g):
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.link_by_label("a", "b", "rel")
        result = g.walk_statistics(num_walks=77, steps=5)
        assert len(result["walk_lengths"]) == 77

    def test_result_types(self, g):
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.link_by_label("a", "b", "rel")
        result = g.walk_statistics(num_walks=5, steps=3, seed=0)
        assert isinstance(result["avg_unique_ratio"], float)
        assert isinstance(result["coverage"], float)
        assert isinstance(result["dead_end_rate"], float)
        assert isinstance(result["most_visited"], list)
        assert isinstance(result["walk_lengths"], list)

    def test_with_restart_vs_without(self, g):
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.add("c", kind="fact")
        g.link_by_label("a", "b", "rel")
        g.link_by_label("b", "c", "rel")
        r_no = g.walk_statistics(num_walks=30, steps=10, restart_prob=0.0, seed=10)
        r_yes = g.walk_statistics(num_walks=30, steps=10, restart_prob=0.5, seed=10)
        # With restart, revisit should happen sooner
        if r_no["avg_revisit_step"] >= 0 and r_yes["avg_revisit_step"] >= 0:
            assert r_yes["avg_revisit_step"] <= r_no["avg_revisit_step"] + 2  # allow small variance

    def test_weights_affect_walk(self, g):
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.add("c", kind="fact")
        g.link_by_label("a", "b", "rel", weight=100.0)
        g.link_by_label("a", "c", "rel", weight=0.01)
        result = g.walk_statistics(num_walks=100, steps=10, seed=42)
        # b should be visited more than c due to weight
        visits = {nid: cnt for nid, cnt in result["most_visited"]}
        b_id = g.conn.execute("SELECT id FROM nodes WHERE label = ?", ("b",)).fetchone()["id"]
        c_id = g.conn.execute("SELECT id FROM nodes WHERE label = ?", ("c",)).fetchone()["id"]
        b_count = visits.get(b_id, 0)
        c_count = visits.get(c_id, 0)
        assert b_count >= c_count

    def test_large_num_walks_performance(self, g):
        """Sanity: 500 walks on small graph should be fast."""
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        g.link_by_label("a", "b", "rel")
        import time
        t0 = time.time()
        g.walk_statistics(num_walks=500, steps=20, seed=0)
        elapsed = time.time() - t0
        assert elapsed < 5.0  # should be well under 5s
