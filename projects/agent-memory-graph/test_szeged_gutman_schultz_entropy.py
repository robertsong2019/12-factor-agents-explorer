import pytest, math
from memory_graph import MemoryGraph

def build_path(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1): g.link(nodes[i].id, nodes[i+1].id, 'r')
    return nodes

def build_complete(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i+1, n): g.link(nodes[i].id, nodes[j].id, 'r')
    return nodes

def build_cycle(g, n):
    nodes = build_path(g, n)
    g.link(nodes[-1].id, nodes[0].id, 'r')
    return nodes

def build_star(g, k):
    hub = g.add('h')
    leaves = [g.add(str(i)) for i in range(k)]
    for l in leaves: g.link(hub.id, l.id, 'r')
    return hub, leaves

# ── szeged_entropy ──

class TestSzegedEntropy:
    def test_none_empty(self): assert MemoryGraph(':memory:').szeged_entropy() is None
    def test_none_single(self):
        mg = MemoryGraph(':memory:'); mg.add('a')
        assert mg.szeged_entropy() is None
    def test_path3(self):
        mg = MemoryGraph(':memory:'); build_path(mg, 3)
        assert mg.szeged_entropy() is not None and 0 < mg.szeged_entropy() <= 1.0
    def test_complete_uniform(self):
        mg = MemoryGraph(':memory:'); build_complete(mg, 4)
        assert abs(mg.szeged_entropy() - 1.0) < 1e-9
    def test_star_uniform(self):
        mg = MemoryGraph(':memory:'); build_star(mg, 4)
        assert abs(mg.szeged_entropy() - 1.0) < 1e-9
    def test_path5_heterogeneous(self):
        mg = MemoryGraph(':memory:'); build_path(mg, 5)
        h = mg.szeged_entropy()
        assert h is not None and 0 < h < 1.0
    def test_cycle5(self):
        mg = MemoryGraph(':memory:'); build_cycle(mg, 5)
        h = mg.szeged_entropy()
        assert h is not None and h > 0  # C5 may be 1.0 (symmetric edges)
    def test_consistency_szeged_index(self):
        mg = MemoryGraph(':memory:'); build_path(mg, 4)
        assert mg.szeged_index() is not None and mg.szeged_index() > 0
        assert mg.szeged_entropy() is not None

# ── gutman_entropy ──

class TestGutmanEntropy:
    def test_none_empty(self): assert MemoryGraph(':memory:').gutman_entropy() is None
    def test_none_single(self):
        mg = MemoryGraph(':memory:'); mg.add('a')
        assert mg.gutman_entropy() is None
    def test_path3(self):
        mg = MemoryGraph(':memory:'); build_path(mg, 3)
        assert mg.gutman_entropy() is not None and 0 < mg.gutman_entropy() <= 1.0
    def test_complete_uniform(self):
        mg = MemoryGraph(':memory:'); build_complete(mg, 4)
        assert abs(mg.gutman_entropy() - 1.0) < 1e-9
    def test_star(self):
        mg = MemoryGraph(':memory:'); build_star(mg, 4)
        g = mg.gutman_entropy()
        assert g is not None and 0 < g <= 1.0
    def test_cycle4(self):
        mg = MemoryGraph(':memory:'); build_cycle(mg, 4)
        assert mg.gutman_entropy() is not None and 0 < mg.gutman_entropy() <= 1.0
    def test_consistency_gutman_index(self):
        mg = MemoryGraph(':memory:'); build_path(mg, 4)
        assert mg.gutman_index() is not None and mg.gutman_index() > 0
        assert mg.gutman_entropy() is not None

# ── schultz_entropy ──

class TestSchultzEntropy:
    def test_none_empty(self): assert MemoryGraph(':memory:').schultz_entropy() is None
    def test_none_single(self):
        mg = MemoryGraph(':memory:'); mg.add('a')
        assert mg.schultz_entropy() is None
    def test_path3(self):
        mg = MemoryGraph(':memory:'); build_path(mg, 3)
        assert mg.schultz_entropy() is not None and 0 < mg.schultz_entropy() <= 1.0
    def test_complete_uniform(self):
        mg = MemoryGraph(':memory:'); build_complete(mg, 4)
        assert abs(mg.schultz_entropy() - 1.0) < 1e-9
    def test_cycle4(self):
        mg = MemoryGraph(':memory:'); build_cycle(mg, 4)
        assert mg.schultz_entropy() is not None and 0 < mg.schultz_entropy() <= 1.0
    def test_consistency_schultz_index(self):
        mg = MemoryGraph(':memory:'); build_path(mg, 4)
        assert mg.schultz_index() is not None and mg.schultz_index() > 0
        assert mg.schultz_entropy() is not None

# ── cross-checks ──

class TestEdgePartitionCrossCheck:
    def test_gutman_schultz_differ_on_path(self):
        """Product vs sum degree weighting should differ on non-regular graphs."""
        mg = MemoryGraph(':memory:'); build_path(mg, 5)
        ge, se = mg.gutman_entropy(), mg.schultz_entropy()
        assert ge is not None and se is not None
        # On P5: degrees are [1,2,2,2,1], product and sum weighting differ
        assert abs(ge - se) > 1e-6

    def test_gutman_schultz_equal_on_regular(self):
        """On regular graphs (cycle), both weight equally → same entropy."""
        mg = MemoryGraph(':memory:'); build_cycle(mg, 6)
        ge, se = mg.gutman_entropy(), mg.schultz_entropy()
        assert ge is not None and se is not None
        assert abs(ge - se) < 1e-9

    def test_gutman_entropy_increases_with_edges(self):
        mg = MemoryGraph(':memory:'); nodes = build_path(mg, 5)
        gu_sparse = mg.gutman_entropy()
        mg.link(nodes[0].id, nodes[2].id, 'r')
        mg.link(nodes[2].id, nodes[4].id, 'r')
        gu_dense = mg.gutman_entropy()
        assert gu_dense >= gu_sparse

    def test_all_normalized_in_0_1(self):
        mg = MemoryGraph(':memory:'); build_cycle(mg, 7)
        for fn in [mg.szeged_entropy, mg.gutman_entropy, mg.schultz_entropy]:
            v = fn()
            assert v is not None and 0 < v <= 1.0, f'{fn.__name__} = {v}'
