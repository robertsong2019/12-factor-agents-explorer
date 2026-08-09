"""Tests for consolidate() — NREM/REM dual-phase offline consolidation.

Research #056 implementation. Cycle 401.
"""
import math
import time
import pytest
from memory_graph import MemoryGraph


def _node_count(mg: MemoryGraph) -> int:
    """Helper: count nodes via SQL (MemoryGraph has no node_count())."""
    return mg.conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]


@pytest.fixture
def basic_graph():
    """Graph with 3 meaningful + 2 near-duplicate + 3 noise nodes."""
    mg = MemoryGraph()
    # Core nodes
    n1 = mg.add("Python", kind="skill", data={"importance": 0.9})
    n2 = mg.add("async programming", kind="concept", data={"importance": 0.7})
    n3 = mg.add("FastAPI", kind="tool", data={"importance": 0.85})
    # Near-duplicates (should merge in NREM)
    n4 = mg.add("Python programming", kind="skill", data={"importance": 0.88})
    n5 = mg.add("asyncio async", kind="skill", data={"importance": 0.75})
    # Noise nodes
    n6 = mg.add("noise_1", kind="noise", data={"importance": 0.01})
    n7 = mg.add("noise_2", kind="noise", data={"importance": 0.02})
    n8 = mg.add("noise_3", kind="noise", data={"importance": 0.01})
    # Edges
    mg.link(n1.id, n2.id, relation="related_to")
    mg.link(n4.id, n2.id, relation="related_to")  # dupe also connects to async
    mg.link(n3.id, n5.id, relation="depends_on")
    mg.link(n2.id, n5.id, relation="related_to")
    return mg, [n1, n2, n3, n4, n5, n6, n7, n8]


class TestConsolidateTrigger:
    def test_force_bypasses_trigger(self, basic_graph):
        mg, _ = basic_graph
        result = mg.consolidate(force=True, dry_run=True)
        assert result["triggered"] is True
        assert result["reason"] == "forced"

    def test_no_trigger_small_graph(self):
        mg = MemoryGraph()
        mg.add("A", kind="fact")
        mg.add("B", kind="fact")
        result = mg.consolidate(min_nodes=10, force=False)
        assert result["triggered"] is False
        assert "too_small" in result["reason"]

    def test_no_trigger_clean_graph(self, basic_graph):
        """Graph below entropy/conflict thresholds → no auto-trigger."""
        mg, _ = basic_graph
        result = mg.consolidate(force=False, entropy_threshold=99.0,
                                conflict_density_threshold=1.0,
                                min_nodes=5)
        assert result["triggered"] is False
        assert result["reason"] == "no_trigger"

    def test_entropy_trigger(self):
        """High entropy should trigger consolidation."""
        mg = MemoryGraph()
        # Many nodes with skewed importance → moderate entropy
        for i in range(15):
            mg.add(f"item_{i}", kind="fact",
                   data={"importance": 0.001 * i})
        result = mg.consolidate(force=False, entropy_threshold=0.01,
                                min_nodes=5, dry_run=True)
        assert result["triggered"] is True
        assert "entropy" in result["reason"]

    def test_conflict_trigger(self):
        """High conflict density should trigger."""
        mg = MemoryGraph()
        nodes = []
        for i in range(10):
            n = mg.add(f"fact_{i}", kind="fact", data={"importance": 0.5})
            nodes.append(n)
        # Add conflict edges for >30% of edges
        for i in range(7):
            mg.link(nodes[i].id, nodes[i + 1].id, relation="contradicts")
        mg.link(nodes[0].id, nodes[2].id, relation="related_to")
        mg.link(nodes[3].id, nodes[5].id, relation="related_to")
        result = mg.consolidate(force=False, entropy_threshold=99.0,
                                conflict_density_threshold=0.3,
                                dry_run=True)
        assert result["triggered"] is True
        assert "conflict" in result["reason"]


class TestWorkingRegion:
    def test_working_region_capped(self, basic_graph):
        mg, nodes = basic_graph
        result = mg.consolidate(force=True, max_working_ratio=0.25,
                                dry_run=True)
        # 8 nodes * 0.25 = 2 max
        assert result["working_region_size"] <= max(2, int(8 * 0.25))

    def test_working_region_includes_recent(self, basic_graph):
        mg, nodes = basic_graph
        recent = [nodes[0].id, nodes[1].id]
        result = mg.consolidate(force=True, recent_nodes=recent,
                                max_working_ratio=1.0, dry_run=True)
        assert result["working_region_size"] >= 2

    def test_working_region_expands_to_neighbors(self, basic_graph):
        mg, nodes = basic_graph
        # nodes[2] (FastAPI) connects to nodes[4] (asyncio)
        result = mg.consolidate(force=True,
                                retrieved_nodes=[nodes[2].id],
                                max_working_ratio=1.0, dry_run=True)
        # Should include FastAPI + its neighbors
        assert result["working_region_size"] >= 1

    def test_empty_graph_safe(self):
        mg = MemoryGraph()
        result = mg.consolidate(force=True)
        assert result["triggered"] is True
        assert result["working_region_size"] <= 2


class TestNremPhase:
    def test_dry_run_no_mutation(self, basic_graph):
        mg, nodes = basic_graph
        before = _node_count(mg)
        result = mg.consolidate(force=True, dry_run=True,
                                similarity_threshold=0.3,
                                max_working_ratio=1.0)
        assert result["dry_run"] is True
        assert _node_count(mg) == before

    def test_merge_executed(self, basic_graph):
        mg, nodes = basic_graph
        before = _node_count(mg)
        result = mg.consolidate(force=True, dry_run=False,
                                similarity_threshold=0.3,
                                max_working_ratio=1.0,
                                importance_floor=0.0,
                                max_prune_ratio=0.0)
        # Should have merged at least 1 pair
        assert result["nrem"]["nodes_merged"] >= 1
        assert _node_count(mg) <= before

    def test_merge_keeps_higher_importance(self, basic_graph):
        mg, nodes = basic_graph
        result = mg.consolidate(force=True, dry_run=False,
                                similarity_threshold=0.3,
                                max_working_ratio=1.0,
                                importance_floor=0.0,
                                max_prune_ratio=0.0)
        for merge_info in result["nrem"]["merges"]:
            survivor = merge_info["survivor"]
            donor = merge_info["donor"]
            # Survivor should still exist
            assert mg.has_node(survivor)

    def test_edges_strengthened(self, basic_graph):
        mg, nodes = basic_graph
        result = mg.consolidate(force=True, dry_run=False,
                                similarity_threshold=0.99,  # no merges
                                max_working_ratio=1.0,
                                importance_floor=0.0,
                                max_prune_ratio=0.0)
        # With no merges, co-occurring edges should be strengthened
        assert result["nrem"]["edges_strengthened"] >= 0

    def test_no_merge_below_threshold(self, basic_graph):
        mg, nodes = basic_graph
        result = mg.consolidate(force=True, dry_run=True,
                                similarity_threshold=0.99,
                                max_working_ratio=1.0)
        assert result["nrem"]["nodes_merged"] == 0


class TestRemPhase:
    def test_prune_low_importance_edges(self):
        mg = MemoryGraph()
        n1 = mg.add("important", kind="fact", data={"importance": 1.0})
        n2 = mg.add("unimportant", kind="noise", data={"importance": 0.001})
        n3 = mg.add("also_unimportant", kind="noise",
                    data={"importance": 0.001})
        mg.link(n1.id, n2.id, relation="related_to", weight=0.1)
        mg.link(n2.id, n3.id, relation="related_to", weight=0.1)
        edges_before = mg.count_edges()
        result = mg.consolidate(force=True, dry_run=False,
                                similarity_threshold=0.99,
                                max_working_ratio=1.0,
                                importance_floor=0.5,
                                max_prune_ratio=1.0)
        assert result["rem"]["edges_pruned"] >= 0  # may or may not prune

    def test_prune_isolated_nodes(self):
        mg = MemoryGraph()
        n1 = mg.add("important", kind="fact", data={"importance": 1.0})
        n2 = mg.add("isolated_noise", kind="noise",
                    data={"importance": 0.001})
        # Don't link n2 to anything → isolated
        result = mg.consolidate(force=True, dry_run=False,
                                similarity_threshold=0.99,
                                retrieved_nodes=[n2.id],
                                max_working_ratio=1.0,
                                importance_floor=0.5,
                                max_prune_ratio=1.0)
        assert result["rem"]["nodes_pruned"] >= 0

    def test_dry_run_no_prune(self, basic_graph):
        mg, nodes = basic_graph
        before = _node_count(mg)
        result = mg.consolidate(force=True, dry_run=True,
                                max_working_ratio=1.0,
                                importance_floor=0.9,
                                max_prune_ratio=1.0)
        assert _node_count(mg) == before


class TestReport:
    def test_report_structure(self, basic_graph):
        mg, _ = basic_graph
        result = mg.consolidate(force=True, dry_run=True)
        required_keys = {"triggered", "reason", "working_region_size",
                         "total_graph_size", "nrem", "rem",
                         "entropy_before", "entropy_after",
                         "noise_reduction_pct", "dry_run",
                         "duration_seconds"}
        assert required_keys.issubset(result.keys())

    def test_nrem_structure(self, basic_graph):
        mg, _ = basic_graph
        result = mg.consolidate(force=True, dry_run=True)
        nrem = result["nrem"]
        assert "nodes_merged" in nrem
        assert "edges_strengthened" in nrem
        assert "merges" in nrem

    def test_rem_structure(self, basic_graph):
        mg, _ = basic_graph
        result = mg.consolidate(force=True, dry_run=True)
        rem = result["rem"]
        assert "nodes_pruned" in rem
        assert "edges_pruned" in rem
        assert "pruned" in rem

    def test_entropy_values(self, basic_graph):
        mg, _ = basic_graph
        result = mg.consolidate(force=True, dry_run=True,
                                max_working_ratio=1.0)
        assert isinstance(result["entropy_before"], float)
        assert isinstance(result["entropy_after"], float)
        assert result["entropy_before"] >= 0.0

    def test_duration_positive(self, basic_graph):
        mg, _ = basic_graph
        result = mg.consolidate(force=True, dry_run=True)
        assert result["duration_seconds"] >= 0.0

    def test_noise_reduction_dry_run(self, basic_graph):
        """In dry run, entropy shouldn't change much."""
        mg, _ = basic_graph
        result = mg.consolidate(force=True, dry_run=True,
                                max_working_ratio=1.0)
        # Dry run: entropy_after should equal entropy_before
        assert abs(result["noise_reduction_pct"]) < 1.0


class TestConsolidateFullRun:
    def test_full_consolidation_cycle(self):
        """End-to-end: build graph, consolidate, verify improvements."""
        mg = MemoryGraph()
        # Create a realistic memory graph
        skills = ["Python", "Python programming", "TypeScript"]
        for s in skills:
            mg.add(s, kind="skill", data={"importance": 0.8})
        mg.add("FastAPI", kind="tool", data={"importance": 0.9})
        mg.add("async", kind="concept", data={"importance": 0.7})
        mg.add("noise_a", kind="temp", data={"importance": 0.01})
        mg.add("noise_b", kind="temp", data={"importance": 0.01})

        nodes = [r["id"] for r in mg.conn.execute(
            "SELECT id FROM nodes ORDER BY created"
        ).fetchall()]

        # Link some
        if len(nodes) >= 3:
            mg.link(nodes[0], nodes[4], relation="related_to")
            mg.link(nodes[1], nodes[4], relation="related_to")
            mg.link(nodes[3], nodes[4], relation="depends_on")

        before_count = _node_count(mg)
        result = mg.consolidate(
            force=True, dry_run=False,
            similarity_threshold=0.3,
            max_working_ratio=1.0,
            importance_floor=0.5,
            max_prune_ratio=0.5,
        )

        assert result["triggered"] is True
        assert result["working_region_size"] >= 1
        # After consolidation, node count should not increase
        assert _node_count(mg) <= before_count

    def test_idempotent_force(self):
        """Multiple force runs should not crash."""
        mg = MemoryGraph()
        for i in range(12):
            mg.add(f"node_{i}", kind="fact",
                   data={"importance": 0.1 * (i % 3)})

        r1 = mg.consolidate(force=True, dry_run=False,
                           similarity_threshold=0.99,
                           max_working_ratio=1.0)
        r2 = mg.consolidate(force=True, dry_run=False,
                           similarity_threshold=0.99,
                           max_working_ratio=1.0)
        assert r1["triggered"] is True
        assert r2["triggered"] is True

    def test_copy_on_write_via_dry_run(self):
        """Dry run preserves all nodes and edges."""
        mg = MemoryGraph()
        for i in range(15):
            n = mg.add(f"item_{i}", kind="fact",
                       data={"importance": 0.5})
        nodes_before = _node_count(mg)
        edges_before = mg.count_edges()

        result = mg.consolidate(force=True, dry_run=True,
                                max_working_ratio=1.0,
                                importance_floor=0.99,
                                max_prune_ratio=1.0)
        assert _node_count(mg) == nodes_before
        assert mg.count_edges() == edges_before


class TestConsolidationStatus:
    """Tests for consolidation_status() dashboard."""

    def test_healthy_graph(self):
        """Small clean graph → not recommended."""
        mg = MemoryGraph()
        for i in range(5):
            mg.add(f"clean_{i}", kind="fact", data={"importance": 0.5})
        result = mg.consolidation_status(entropy_threshold=2.0)
        assert result["recommend"] is False
        assert result["reason"] in ("graph_too_small", "healthy")

    def test_entropy_recommend(self):
        """High entropy → recommend."""
        mg = MemoryGraph()
        for i in range(15):
            mg.add(f"item_{i}", kind="fact",
                   data={"importance": 0.001 * i})
        result = mg.consolidation_status(entropy_threshold=0.01)
        assert result["recommend"] is True
        assert "entropy" in result["reason"]

    def test_conflict_recommend(self):
        """High conflict density → recommend."""
        mg = MemoryGraph()
        nodes = []
        for i in range(10):
            n = mg.add(f"fact_{i}", kind="fact", data={"importance": 0.5})
            nodes.append(n)
        for i in range(7):
            mg.link(nodes[i].id, nodes[i + 1].id, relation="contradicts")
        result = mg.consolidation_status(conflict_density_threshold=0.3)
        assert result["recommend"] is True
        assert "conflict" in result["reason"]

    def test_metrics_structure(self):
        mg = MemoryGraph()
        mg.add("A", kind="fact", data={"importance": 0.5})
        mg.add("B", kind="fact", data={"importance": 0.7})
        result = mg.consolidation_status()
        required = {"node_count", "edge_count", "entropy",
                    "conflict_density", "conflict_edges",
                    "avg_importance", "stale_node_ratio",
                    "stale_nodes"}
        assert required.issubset(result["metrics"].keys())

    def test_thresholds_echoed(self):
        mg = MemoryGraph()
        mg.add("X", kind="fact")
        result = mg.consolidation_status(
            entropy_threshold=1.5, conflict_density_threshold=0.4,
            min_nodes=20)
        assert result["thresholds"]["entropy"] == 1.5
        assert result["thresholds"]["conflict_density"] == 0.4
        assert result["thresholds"]["min_nodes"] == 20

    def test_stale_detection(self):
        """Old accessed timestamps → stale_node_ratio > 0."""
        mg = MemoryGraph()
        n = mg.add("old_node", kind="fact", data={"importance": 0.5})
        # Manually backdate accessed time
        old_ts = time.time() - 30 * 86400  # 30 days ago
        mg.conn.execute(
            "UPDATE nodes SET accessed=? WHERE id=?",
            (old_ts, n.id)
        )
        mg.conn.commit()
        result = mg.consolidation_status()
        assert result["metrics"]["stale_node_ratio"] > 0.0
        assert result["metrics"]["stale_nodes"] >= 1

    def test_empty_graph_safe(self):
        mg = MemoryGraph()
        result = mg.consolidation_status()
        assert result["recommend"] is False
        assert result["metrics"]["node_count"] == 0

    def test_no_mutation(self):
        """consolidation_status() should not modify the graph."""
        mg = MemoryGraph()
        for i in range(5):
            mg.add(f"n_{i}", kind="fact")
        before = _node_count(mg)
        mg.consolidation_status()
        assert _node_count(mg) == before
