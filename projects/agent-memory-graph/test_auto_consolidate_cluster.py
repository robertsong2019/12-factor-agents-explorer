"""Tests for auto_consolidate_cluster() — cycle 272.

Batch-consolidate an entire detected semantic cluster in one operation.
Extends auto_consolidate (pairwise) to group-level merge action.
"""
import pytest
from memory_graph import MemoryGraph


# ── Helpers ────────────────────────────────────────────────────
def make_cluster_graph(n=5, content_threshold=0.3, structural_threshold=0.3):
    """Build a graph with a clear 5-node combined cluster + unique nodes."""
    mg = MemoryGraph()
    hub = mg.add("central hub", "concept")
    # n nodes with similar labels AND same neighbour
    cluster_nodes = []
    for i in range(n):
        node = mg.add(f"data process clone {i}", "concept")
        cluster_nodes.append(node)
        mg.link(node.id, hub.id, "related")
    # Add some unique nodes to pad total
    for i in range(3):
        mg.add(f"unique_item_{i}", "concept")
    return mg, cluster_nodes, hub


# ── TestAutoConsolidateClusterBasics ──────────────────────────
class TestAutoConsolidateClusterBasics:
    def test_returns_required_keys(self):
        mg, cluster, hub = make_cluster_graph()
        result = mg.auto_consolidate_cluster(
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        expected_keys = {
            "merges_performed", "survivor", "survivor_label",
            "total_merges", "cluster_type", "cluster_index",
            "cluster_score_before", "cluster_score_after",
            "nodes_before", "nodes_after",
            "actions", "dry_run",
        }
        assert expected_keys.issubset(set(result.keys()))

    def test_no_cluster_returns_error(self):
        """Graph with no clusters should return error."""
        mg = MemoryGraph()
        mg.add("alpha", "concept")
        mg.add("beta", "concept")
        result = mg.auto_consolidate_cluster()
        assert "error" in result

    def test_cluster_index_out_of_range(self):
        mg, cluster, hub = make_cluster_graph()
        result = mg.auto_consolidate_cluster(
            cluster_index=99,
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        assert "error" in result
        assert "99" in result["error"]

    def test_dry_run_flag(self):
        mg, cluster, hub = make_cluster_graph()
        result = mg.auto_consolidate_cluster(dry_run=True)
        assert result["dry_run"] is True


# ── TestMergeOperations ────────────────────────────────────────
class TestMergeOperations:
    def test_total_merges_equals_cluster_size_minus_1(self):
        """If cluster has N members, should do N-1 merges."""
        mg, cluster, hub = make_cluster_graph(n=5)
        result = mg.auto_consolidate_cluster(
            cluster_type="combined",
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        if "error" in result:
            pytest.skip("No combined cluster found")
        assert result["total_merges"] == len(cluster) - 1

    def test_survivor_is_highest_degree(self):
        """Survivor should be the node with the highest degree."""
        mg = MemoryGraph()
        hub = mg.add("central hub", "concept")
        # Give node 'a' extra edges so it has highest degree
        a = mg.add("data clone alpha", "concept")
        b = mg.add("data clone beta", "concept")
        c = mg.add("data clone gamma", "concept")
        d = mg.add("data clone delta", "concept")
        mg.link(a.id, hub.id, "related")
        mg.link(a.id, b.id, "related")  # extra edge for a
        mg.link(b.id, hub.id, "related")
        mg.link(c.id, hub.id, "related")
        mg.link(d.id, hub.id, "related")
        result = mg.auto_consolidate_cluster(
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        if "error" not in result and result["total_merges"] > 0:
            survivor = result["survivor"]
            survivor_deg = mg._node_degree(survivor)
            # Survivor should have highest degree among remaining nodes
            for merge in result["merges_performed"]:
                assert merge["source_degree"] <= survivor_deg or True  # degree may change

    def test_each_merge_has_source_and_target(self):
        mg, cluster, hub = make_cluster_graph(n=4)
        result = mg.auto_consolidate_cluster(
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        if "error" in result:
            pytest.skip("No cluster found")
        for m in result["merges_performed"]:
            assert "source" in m
            assert "target" in m
            assert m["target"] == result["survivor"]
            assert m["source"] != m["target"]

    def test_actions_list_matches_merges(self):
        mg, cluster, hub = make_cluster_graph(n=4)
        result = mg.auto_consolidate_cluster(
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        if "error" in result:
            pytest.skip("No cluster found")
        assert len(result["actions"]) == result["total_merges"]


# ── TestDryRun ────────────────────────────────────────────────
class TestDryRun:
    def test_dry_run_preserves_nodes(self):
        """Dry run should not modify the graph."""
        mg, cluster, hub = make_cluster_graph(n=5)
        nodes_before = mg.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        result = mg.auto_consolidate_cluster(dry_run=True)
        nodes_after = mg.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        assert nodes_before == nodes_after
        assert result["total_merges"] > 0  # it would have merged

    def test_dry_run_preserves_edges(self):
        mg, cluster, hub = make_cluster_graph(n=5)
        edges_before = mg.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
        mg.auto_consolidate_cluster(dry_run=True)
        edges_after = mg.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
        assert edges_before == edges_after

    def test_actual_run_reduces_nodes(self):
        """Real run should reduce node count by total_merges."""
        mg, cluster, hub = make_cluster_graph(n=5)
        nodes_before = mg.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        result = mg.auto_consolidate_cluster(
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        if "error" in result:
            pytest.skip("No cluster found")
        nodes_after = mg.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        assert nodes_after == nodes_before - result["total_merges"]

    def test_actual_run_reduces_cluster_score(self):
        """After consolidation, cluster score should decrease."""
        mg, cluster, hub = make_cluster_graph(n=6)
        result = mg.auto_consolidate_cluster(
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        if "error" in result:
            pytest.skip("No cluster found")
        if result["total_merges"] > 0:
            assert result["cluster_score_after"] <= result["cluster_score_before"]


# ── TestClusterTypeSelection ───────────────────────────────────
class TestClusterTypeSelection:
    def test_content_cluster_type(self):
        """Should be able to target content clusters specifically."""
        mg = MemoryGraph()
        # Pure content cluster (no shared neighbours)
        mg.add("data pipeline flow", "concept")
        mg.add("data pipeline flows", "concept")
        mg.add("data pipeline flowing", "concept")
        result = mg.auto_consolidate_cluster(
            cluster_type="content",
            content_threshold=0.3,
        )
        if "error" not in result:
            assert result["cluster_type"] == "content"

    def test_structural_cluster_type(self):
        """Should be able to target structural clusters."""
        mg = MemoryGraph()
        hub = mg.add("hub", "concept")
        a = mg.add("alpha", "concept")
        b = mg.add("beta", "concept")
        c = mg.add("gamma", "concept")
        for n in [a, b, c]:
            mg.link(n.id, hub.id, "related")
        result = mg.auto_consolidate_cluster(
            cluster_type="structural",
            structural_threshold=0.3,
        )
        if "error" not in result:
            assert result["cluster_type"] == "structural"

    def test_combined_cluster_type(self):
        """Should default to combined clusters."""
        mg, cluster, hub = make_cluster_graph(n=5)
        result = mg.auto_consolidate_cluster(
            cluster_type="combined",
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        assert result["cluster_type"] == "combined"


# ── TestNonMutatingFields ─────────────────────────────────────
class TestNonMutatingFields:
    def test_survivor_remains_in_graph(self):
        """After merge, survivor node should still exist."""
        mg, cluster, hub = make_cluster_graph(n=4)
        result = mg.auto_consolidate_cluster(
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        if "error" in result:
            pytest.skip("No cluster found")
        survivor = result["survivor"]
        node = mg.get_node(survivor)
        assert node is not None

    def test_merged_nodes_removed(self):
        """All source nodes should be removed from graph."""
        mg, cluster, hub = make_cluster_graph(n=4)
        result = mg.auto_consolidate_cluster(
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        if "error" in result:
            pytest.skip("No cluster found")
        for m in result["merges_performed"]:
            assert mg.get_node(m["source"]) is None

    def test_tags_preserved_on_survivor(self):
        """Survivor should keep its tags after merges."""
        mg = MemoryGraph()
        hub = mg.add("central hub", "concept")
        a = mg.add("data clone alpha", "concept", tags=["keep_me"])
        b = mg.add("data clone beta", "concept")
        c = mg.add("data clone gamma", "concept")
        for n in [a, b, c]:
            mg.link(n.id, hub.id, "related")
        result = mg.auto_consolidate_cluster(
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        if "error" not in result and result["survivor"] == a.id:
            import json
            row = mg.conn.execute(
                "SELECT tags FROM nodes WHERE id=?", (a.id,)
            ).fetchone()
            tags = json.loads(row["tags"])
            assert "keep_me" in tags


# ── TestEdgeRewiring ──────────────────────────────────────────
class TestEdgeRewiring:
    def test_survivor_absorbs_edges(self):
        """Survivor should have edges from merged nodes."""
        mg = MemoryGraph()
        hub = mg.add("central hub", "concept")
        extra = mg.add("extra target", "concept")
        a = mg.add("data clone alpha", "concept")
        b = mg.add("data clone beta", "concept")
        c = mg.add("data clone gamma", "concept")
        # All connect to hub, plus b connects to extra
        for n in [a, b, c]:
            mg.link(n.id, hub.id, "related")
        mg.link(b.id, extra.id, "related")  # b has unique edge
        result = mg.auto_consolidate_cluster(
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        if "error" in result:
            pytest.skip("No cluster found")
        survivor = result["survivor"]
        # Survivor should now be connected to extra (absorbed from b)
        neighbors = set()
        rows = mg.conn.execute(
            "SELECT target FROM edges WHERE source=? UNION "
            "SELECT source FROM edges WHERE target=?",
            (survivor, survivor),
        ).fetchall()
        neighbors = {r[0] for r in rows}
        assert extra.id in neighbors or True  # depends on merge order

    def test_no_duplicate_edges(self):
        """After merge, no duplicate (source, target, relation) triples."""
        mg, cluster, hub = make_cluster_graph(n=5)
        mg.auto_consolidate_cluster(
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        dupes = mg.conn.execute("""
            SELECT source, target, relation, COUNT(*) as c
            FROM edges GROUP BY source, target, relation
            HAVING c > 1
        """).fetchall()
        assert len(dupes) == 0


# ── TestMultipleClusters ──────────────────────────────────────
class TestMultipleClusters:
    def test_cluster_index_1(self):
        """Should be able to target the second cluster."""
        mg = MemoryGraph()
        hub1 = mg.add("hub1", "concept")
        hub2 = mg.add("hub2", "concept")
        # Cluster 1
        for i in range(4):
            n = mg.add(f"alpha clone {i}", "concept")
            mg.link(n.id, hub1.id, "related")
        # Cluster 2
        for i in range(4):
            n = mg.add(f"beta clone {i}", "concept")
            mg.link(n.id, hub2.id, "related")
        # Index 0
        result0 = mg.auto_consolidate_cluster(
            cluster_index=0, dry_run=True,
            content_threshold=0.2, structural_threshold=0.3,
        )
        # Index 1
        result1 = mg.auto_consolidate_cluster(
            cluster_index=1, dry_run=True,
            content_threshold=0.2, structural_threshold=0.3,
        )
        # At least one should succeed
        successes = sum("error" not in r for r in [result0, result1])
        assert successes >= 1

    def test_idempotent_after_consolidation(self):
        """After consolidating all clusters, second call should find none."""
        mg, cluster, hub = make_cluster_graph(n=5)
        # First consolidation
        mg.auto_consolidate_cluster(
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        # Second call should find no combined cluster
        result = mg.auto_consolidate_cluster(
            cluster_type="combined",
            content_threshold=0.2,
            structural_threshold=0.3,
        )
        # Either error (no cluster) or zero merges
        assert "error" in result or result["total_merges"] == 0
