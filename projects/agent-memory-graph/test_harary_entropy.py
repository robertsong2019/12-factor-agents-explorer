import pytest, math
from memory_graph import MemoryGraph

# ─── Helpers ────────────────────────────────────────────────────────────

def build_path(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return nodes

def build_complete(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return nodes

def build_cycle(g, n):
    nodes = build_path(g, n)
    g.link(nodes[-1].id, nodes[0].id, "r")
    return nodes

def build_star(g, k):
    hub = g.add('h')
    leaves = [g.add(str(i)) for i in range(k)]
    for l in leaves:
        g.link(hub.id, l.id, 'r')
    return hub, leaves

# --- Cycle 289: harary_entropy + wiener_entropy ---

class TestHararyEntropyBasic:
    def test_none_for_empty(self):
        assert MemoryGraph(':memory:').harary_entropy() is None

    def test_none_for_single(self):
        mg = MemoryGraph(':memory:')
        mg.add('a')
        assert mg.harary_entropy() is None

    def test_path3_returns_value(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        h = mg.harary_entropy()
        assert h is not None
        assert 0 < h <= 1.0

    def test_raw_not_normalized(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        raw = mg.harary_entropy(normalized=False)
        assert raw is not None and raw > 0

    def test_complete_graph_uniform(self):
        mg = MemoryGraph(':memory:')
        build_complete(mg, 4)
        assert abs(mg.harary_entropy() - 1.0) < 1e-9

    def test_star_graph_heterogeneous(self):
        mg = MemoryGraph(':memory:')
        build_star(mg, 4)
        h = mg.harary_entropy()
        assert 0 < h < 1.0

    def test_disconnected_graph(self):
        mg = MemoryGraph(':memory:')
        a, b = mg.add('a'), mg.add('b')
        mg.add('c'); mg.add('d')
        mg.link(a.id, b.id, 'r')
        h = mg.harary_entropy(normalized=False)
        assert h == 0.0  # single pair → entropy 0

    def test_cycle4(self):
        mg = MemoryGraph(':memory:')
        build_cycle(mg, 4)
        h = mg.harary_entropy()
        assert 0 < h < 1.0

    def test_consistency_with_harary_index(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        h_idx = mg.harary_index()
        assert h_idx > 0
        # entropy should be computable
        assert mg.harary_entropy() is not None


class TestWienerEntropyBasic:
    def test_none_for_empty(self):
        assert MemoryGraph(':memory:').wiener_entropy() is None

    def test_none_for_single(self):
        mg = MemoryGraph(':memory:')
        mg.add('a')
        assert mg.wiener_entropy() is None

    def test_path3_returns_value(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        w = mg.wiener_entropy()
        assert w is not None and 0 < w <= 1.0

    def test_raw_not_normalized(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        raw = mg.wiener_entropy(normalized=False)
        assert raw is not None and raw > 0

    def test_complete_graph_uniform(self):
        mg = MemoryGraph(':memory:')
        build_complete(mg, 4)
        assert abs(mg.wiener_entropy() - 1.0) < 1e-9

    def test_star_graph(self):
        mg = MemoryGraph(':memory:')
        build_star(mg, 4)
        w = mg.wiener_entropy()
        assert 0 < w <= 1.0

    def test_disconnected_graph(self):
        mg = MemoryGraph(':memory:')
        a, b = mg.add('a'), mg.add('b')
        mg.add('c'); mg.add('d')
        mg.link(a.id, b.id, 'r')
        w = mg.wiener_entropy(normalized=False)
        assert w == 0.0

    def test_cycle4(self):
        mg = MemoryGraph(':memory:')
        build_cycle(mg, 4)
        w = mg.wiener_entropy()
        assert 0 < w < 1.0

    def test_consistency_with_wiener_index(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        w_idx = mg.wiener_index()
        assert w_idx > 0
        assert mg.wiener_entropy() is not None


class TestCrossCheck:
    def test_harary_wiener_complementary(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        h, w = mg.harary_entropy(), mg.wiener_entropy()
        assert h is not None and w is not None
        # P3: distances [1,1,2], reciprocals [1,1,0.5]
        # They weight differently → should differ
        assert abs(h - w) > 1e-6

    def test_complete_both_one(self):
        mg = MemoryGraph(':memory:')
        build_complete(mg, 3)
        assert abs(mg.harary_entropy() - 1.0) < 1e-9
        assert abs(mg.wiener_entropy() - 1.0) < 1e-9

    def test_monotonicity_star_vs_complete(self):
        ms = MemoryGraph(':memory:')
        build_star(ms, 5)
        mk = MemoryGraph(':memory:')
        build_complete(mk, 6)
        assert mk.harary_entropy() > ms.harary_entropy()
        assert mk.wiener_entropy() > ms.wiener_entropy()

    def test_five_node_path(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 5)
        h, w = mg.harary_entropy(), mg.wiener_entropy()
        assert h is not None and w is not None
        assert 0 < h < 1.0 and 0 < w < 1.0

    def test_entropy_increases_with_uniformity(self):
        mg = MemoryGraph(':memory:')
        nodes = build_path(mg, 5)
        h_sparse = mg.harary_entropy()
        w_sparse = mg.wiener_entropy()
        mg.link(nodes[0].id, nodes[2].id, 'r')
        mg.link(nodes[2].id, nodes[4].id, 'r')
        h_dense = mg.harary_entropy()
        w_dense = mg.wiener_entropy()
        assert h_dense >= h_sparse
        assert w_dense >= w_sparse

    def test_normalized_in_0_1(self):
        mg = MemoryGraph(':memory:')
        build_cycle(mg, 5)
        h, w = mg.harary_entropy(), mg.wiener_entropy()
        assert 0 < h <= 1.0
        assert 0 < w <= 1.0
