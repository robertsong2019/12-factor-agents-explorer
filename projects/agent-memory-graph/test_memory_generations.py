"""Tests for memory_generations_report() — Cycle 389.

Cohort analysis: groups nodes into generations by insertion order,
analyses per-generation characteristics and cross-generation connectivity.
"""
import time
from memory_graph import MemoryGraph


def _add_at(mg, label, kind="fact", created=None):
    """Add node and override its created timestamp."""
    n = mg.add(label, kind)
    if created is not None:
        mg.conn.execute("UPDATE nodes SET created = ? WHERE id = ?",
                         (created, n.id))
        mg.conn.commit()
    return n


class TestGenerationsEmpty:
    def test_empty_graph(self):
        mg = MemoryGraph()
        result = mg.memory_generations_report()
        assert result["generations"] == []
        assert result["cross_generation_edges"] == 0
        assert result["balance_score"] == 0.0
        assert result["summary"]["total"] == 0

    def test_empty_graph_with_params(self):
        mg = MemoryGraph()
        result = mg.memory_generations_report(generation_size=10, now=1000000)
        assert result["generations"] == []


class TestGenerationsBasic:
    def test_single_generation(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(10):
            _add_at(mg, f"n{i}", "fact", created=now - (10 - i) * 100)
        result = mg.memory_generations_report(generation_size=50)
        assert result["num_generations"] == 1
        assert result["generations"][0]["size"] == 10

    def test_multiple_generations(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(30):
            _add_at(mg, f"n{i}", "fact", created=now - (30 - i) * 100)
        result = mg.memory_generations_report(generation_size=10)
        assert result["num_generations"] == 3
        assert all(g["size"] == 10 for g in result["generations"])

    def test_last_generation_partial(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(25):
            _add_at(mg, f"n{i}", "fact", created=now - (25 - i) * 100)
        result = mg.memory_generations_report(generation_size=10)
        assert result["num_generations"] == 3
        assert result["generations"][0]["size"] == 10
        assert result["generations"][1]["size"] == 10
        assert result["generations"][2]["size"] == 5

    def test_default_generation_size(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(55):
            _add_at(mg, f"n{i}", "fact", created=now - (55 - i) * 100)
        result = mg.memory_generations_report()
        assert result["num_generations"] == 2
        assert result["generations"][0]["size"] == 50
        assert result["generations"][1]["size"] == 5


class TestGenerationsTimeSpan:
    def test_time_span_computed(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "a", "fact", created=now - 10000)
        _add_at(mg, "b", "fact", created=now - 5000)
        _add_at(mg, "c", "fact", created=now - 100)
        result = mg.memory_generations_report(generation_size=10)
        assert result["generations"][0]["time_span"] > 0

    def test_time_span_zero_same_timestamp(self):
        mg = MemoryGraph()
        ts = 1000000
        _add_at(mg, "a", "fact", created=ts)
        _add_at(mg, "b", "fact", created=ts)
        result = mg.memory_generations_report(generation_size=10)
        assert result["generations"][0]["time_span"] == 0.0

    def test_age_field(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "old", "fact", created=now - 100000)
        result = mg.memory_generations_report(generation_size=10, now=now)
        assert result["generations"][0]["age"] > 0


class TestGenerationsKindDistribution:
    def test_dominant_kind(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(7):
            _add_at(mg, f"f{i}", "fact", created=now - i * 100)
        for i in range(3):
            _add_at(mg, f"e{i}", "event", created=now - i * 100)
        result = mg.memory_generations_report(generation_size=50)
        assert result["generations"][0]["dominant_kind"] == "fact"

    def test_kind_distribution(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "f1", "fact", created=now - 100)
        _add_at(mg, "f2", "fact", created=now - 200)
        _add_at(mg, "e1", "event", created=now - 300)
        result = mg.memory_generations_report(generation_size=50)
        kinds = result["generations"][0]["kind_distribution"]
        assert kinds.get("fact") == 2
        assert kinds.get("event") == 1


class TestCrossGenerationEdges:
    def test_no_edges(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(10):
            _add_at(mg, f"n{i}", "fact", created=now - i * 100)
        result = mg.memory_generations_report(generation_size=5)
        assert result["cross_generation_edges"] == 0
        assert result["within_generation_edges"] == 0

    def test_within_generation_edges(self):
        mg = MemoryGraph()
        now = time.time()
        nodes = []
        for i in range(5):
            n = _add_at(mg, f"n{i}", "fact", created=now - i * 100)
            nodes.append(n.id)
        mg.link(nodes[0], nodes[1], "related")
        mg.link(nodes[2], nodes[3], "related")
        result = mg.memory_generations_report(generation_size=10)
        assert result["within_generation_edges"] == 2
        assert result["cross_generation_edges"] == 0

    def test_cross_generation_edges(self):
        mg = MemoryGraph()
        now = time.time()
        gen1 = [_add_at(mg, f"a{i}", "fact", created=now - 10000).id for i in range(5)]
        gen2 = [_add_at(mg, f"b{i}", "fact", created=now - 100).id for i in range(5)]
        mg.link(gen1[0], gen2[0], "relates_to")
        mg.link(gen1[1], gen2[1], "relates_to")
        result = mg.memory_generations_report(generation_size=5)
        assert result["cross_generation_edges"] == 2
        assert result["within_generation_edges"] == 0

    def test_cross_generation_fraction(self):
        mg = MemoryGraph()
        now = time.time()
        gen1 = [_add_at(mg, f"a{i}", "fact", created=now - 10000).id for i in range(5)]
        gen2 = [_add_at(mg, f"b{i}", "fact", created=now - 100).id for i in range(5)]
        mg.link(gen1[0], gen1[1], "related")     # within
        mg.link(gen1[0], gen2[0], "relates_to")  # cross
        result = mg.memory_generations_report(generation_size=5)
        assert result["cross_generation_fraction"] == 0.5

    def test_top_cross_generation_pairs(self):
        mg = MemoryGraph()
        now = time.time()
        gen1 = [_add_at(mg, f"a{i}", "fact", created=now - 10000).id for i in range(5)]
        gen2 = [_add_at(mg, f"b{i}", "fact", created=now - 100).id for i in range(5)]
        mg.link(gen1[0], gen2[0], "r")
        mg.link(gen1[0], gen2[1], "r")
        mg.link(gen1[1], gen2[0], "r")
        result = mg.memory_generations_report(generation_size=5)
        assert len(result["top_cross_generation_pairs"]) >= 1
        assert result["top_cross_generation_pairs"][0]["generations"] == [0, 1]
        assert result["top_cross_generation_pairs"][0]["edges"] == 3


class TestBalanceScore:
    def test_perfectly_balanced(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(20):
            _add_at(mg, f"n{i}", "fact", created=now - i * 100)
        result = mg.memory_generations_report(generation_size=10)
        # All generations same size → CV=0 → balance=1
        assert result["balance_score"] == 1.0

    def test_skewed_balance(self):
        mg = MemoryGraph()
        now = time.time()
        # Gen 1: 50 nodes, Gen 2: 1 node → very skewed
        for i in range(50):
            _add_at(mg, f"n{i}", "fact", created=now - 10000 + i)
        _add_at(mg, "lonely", "fact", created=now - 100)
        result = mg.memory_generations_report(generation_size=50)
        assert result["balance_score"] < 0.7

    def test_balance_score_range(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(15):
            _add_at(mg, f"n{i}", "fact", created=now - i * 100)
        result = mg.memory_generations_report(generation_size=5)
        assert 0.0 <= result["balance_score"] <= 1.0


class TestDominantGeneration:
    def test_dominant_generation_identified(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(30):
            _add_at(mg, f"n{i}", "fact", created=now - i * 100)
        result = mg.memory_generations_report(generation_size=10)
        assert result["dominant_generation"]["size"] == 10

    def test_dominant_fraction(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(15):
            _add_at(mg, f"n{i}", "fact", created=now - i * 100)
        result = mg.memory_generations_report(generation_size=10)
        # 15 nodes, gen 0 = 10, gen 1 = 5 → dominant fraction = 10/15
        assert abs(result["dominant_generation"]["fraction"] - round(10/15, 4)) < 0.01


class TestGenerationsSummary:
    def test_summary_fields(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(10):
            _add_at(mg, f"n{i}", "fact", created=now - i * 100)
        result = mg.memory_generations_report(generation_size=5)
        s = result["summary"]
        assert "total" in s
        assert "generation_size" in s
        assert "avg_generation_size" in s
        assert "interpretation" in s

    def test_interpretation_well_distributed(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(20):
            _add_at(mg, f"n{i}", "fact", created=now - i * 100)
        result = mg.memory_generations_report(generation_size=10)
        assert result["summary"]["interpretation"] == "well_distributed"

    def test_interpretation_bulk_skewed(self):
        mg = MemoryGraph()
        now = time.time()
        # Two very unequal generations: 50 + 1
        for i in range(50):
            _add_at(mg, f"n{i}", "fact", created=now - 10000 + i)
        _add_at(mg, "x", "fact", created=now - 100)
        result = mg.memory_generations_report(generation_size=50)
        # balance ≈ 0.51 with [50, 1] split
        assert result["summary"]["interpretation"] in ("bulk_skewed", "moderate")
        # Verify the imbalance exists
        assert result["balance_score"] < 0.7

    def test_avg_generation_size(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(15):
            _add_at(mg, f"n{i}", "fact", created=now - i * 100)
        result = mg.memory_generations_report(generation_size=10)
        # 15 nodes / 2 gens → avg = 7.5
        assert result["summary"]["avg_generation_size"] == 7.5


class TestGenerationsEdgeCases:
    def test_single_node(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "only", "fact", created=now - 100)
        result = mg.memory_generations_report(generation_size=50)
        assert result["num_generations"] == 1
        assert result["generations"][0]["size"] == 1

    def test_generation_size_larger_than_graph(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(5):
            _add_at(mg, f"n{i}", "fact", created=now - i * 100)
        result = mg.memory_generations_report(generation_size=1000)
        assert result["num_generations"] == 1

    def test_generation_size_one(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(3):
            _add_at(mg, f"n{i}", "fact", created=now - i * 100)
        result = mg.memory_generations_report(generation_size=1)
        assert result["num_generations"] == 3
        assert all(g["size"] == 1 for g in result["generations"])

    def test_explicit_now(self):
        mg = MemoryGraph()
        fixed_now = 2000000000
        _add_at(mg, "a", "fact", created=fixed_now - 1000)
        result = mg.memory_generations_report(generation_size=10, now=fixed_now)
        assert result["generations"][0]["age"] > 0
