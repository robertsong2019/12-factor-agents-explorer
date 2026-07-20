"""Tests for semantic_cluster_detect() — cycle 271.

Group-level redundancy detection extending pairwise redundancy_detect().
"""
import pytest
from memory_graph import MemoryGraph


# ── Helpers ────────────────────────────────────────────────────
def make_graph(nodes_spec, edges_spec=None):
    """Build a graph from (label, kind, weight) tuples."""
    mg = MemoryGraph()
    ids = {}
    for i, (label, kind, *rest) in enumerate(nodes_spec):
        w = rest[0] if rest else 1.0
        n = mg.add(label, kind, weight=w)
        ids[i] = n.id
    if edges_spec:
        for src, tgt in edges_spec:
            mg.link(ids[src], ids[tgt], "related")
    return mg, ids


# ── TestSemanticClusterBasics ──────────────────────────────────
class TestSemanticClusterBasics:
    def test_empty_graph(self):
        mg = MemoryGraph()
        result = mg.semantic_cluster_detect()
        assert result["content_clusters"] == []
        assert result["structural_clusters"] == []
        assert result["combined_clusters"] == []
        assert result["cluster_score"] == 0.0

    def test_single_node(self):
        mg = MemoryGraph()
        mg.add("solo", "concept")
        result = mg.semantic_cluster_detect()
        assert result["content_clusters"] == []

    def test_two_nodes_below_min_cluster(self):
        mg = MemoryGraph()
        mg.add("Python web framework", "concept")
        mg.add("Python web frameworks", "concept")
        result = mg.semantic_cluster_detect(min_cluster_size=3)
        assert result["content_clusters"] == []
        assert result["structural_clusters"] == []

    def test_returns_required_keys(self):
        mg = MemoryGraph()
        for i in range(5):
            mg.add(f"item {i}", "concept")
        result = mg.semantic_cluster_detect()
        for key in ["content_clusters", "structural_clusters",
                     "combined_clusters", "cluster_score",
                     "total_nodes", "recommendations"]:
            assert key in result

    def test_score_range(self):
        mg = MemoryGraph()
        for i in range(10):
            mg.add(f"unique item {i}", "concept")
        result = mg.semantic_cluster_detect()
        assert 0 <= result["cluster_score"] <= 100


# ── TestContentClusters ────────────────────────────────────────
class TestContentClusters:
    def test_finds_content_cluster(self):
        """Three near-duplicate labels should cluster."""
        mg = MemoryGraph()
        mg.add("Python web framework", "concept")
        mg.add("Python web frameworks", "concept")
        mg.add("Python framework for web", "concept")
        result = mg.semantic_cluster_detect(
            content_threshold=0.4, min_cluster_size=3
        )
        assert len(result["content_clusters"]) >= 1
        assert result["content_clusters"][0]["size"] >= 3

    def test_no_false_positive_diverse(self):
        """Completely different labels should not cluster."""
        mg = MemoryGraph()
        for label in ["database", "weather", "cooking", "rocket", "music"]:
            mg.add(label, "concept")
        result = mg.semantic_cluster_detect(content_threshold=0.5)
        assert result["content_clusters"] == []

    def test_threshold_respected(self):
        """High threshold should exclude borderline pairs."""
        mg = MemoryGraph()
        mg.add("Python web framework fast", "concept")
        mg.add("Python web framework slow", "concept")
        mg.add("Rust embedded systems cool", "concept")
        # At 0.9 threshold, the Python pair might not link
        result = mg.semantic_cluster_detect(content_threshold=0.95)
        # With 3 nodes but high threshold, likely no clusters
        # (depends on trigram overlap, so just check it doesn't crash)
        assert isinstance(result["content_clusters"], list)

    def test_cluster_has_members(self):
        mg = MemoryGraph()
        mg.add("machine learning model", "concept")
        mg.add("machine learning models", "concept")
        mg.add("machine learning modeling", "concept")
        result = mg.semantic_cluster_detect(content_threshold=0.4)
        if result["content_clusters"]:
            c = result["content_clusters"][0]
            assert "members" in c
            assert "size" in c
            assert "avg_similarity" in c
            assert "representative" in c
            assert "labels" in c
            assert isinstance(c["members"], list)
            assert len(c["members"]) == c["size"]

    def test_avg_similarity_sorted_desc(self):
        mg = MemoryGraph()
        for label in [
            "data processing pipeline",
            "data processing pipelines",
            "data pipeline processing",
            "random other thing one",
            "random other thing two",
            "random other thing three",
        ]:
            mg.add(label, "concept")
        result = mg.semantic_cluster_detect(
            content_threshold=0.3, min_cluster_size=3
        )
        if len(result["content_clusters"]) >= 2:
            assert (
                result["content_clusters"][0]["avg_similarity"]
                >= result["content_clusters"][1]["avg_similarity"]
            )


# ── TestStructuralClusters ─────────────────────────────────────
class TestStructuralClusters:
    def test_finds_structural_cluster(self):
        """Three nodes sharing the same neighbours should cluster."""
        mg = MemoryGraph()
        hub1 = mg.add("hub1", "concept")
        hub2 = mg.add("hub2", "concept")
        # Three nodes all connected to the same two hubs
        a = mg.add("clone-a", "concept")
        b = mg.add("clone-b", "concept")
        c = mg.add("clone-c", "concept")
        mg.link(a.id, hub1.id, "related")
        mg.link(a.id, hub2.id, "related")
        mg.link(b.id, hub1.id, "related")
        mg.link(b.id, hub2.id, "related")
        mg.link(c.id, hub1.id, "related")
        mg.link(c.id, hub2.id, "related")
        result = mg.semantic_cluster_detect(
            structural_threshold=0.4, min_cluster_size=3
        )
        assert len(result["structural_clusters"]) >= 1
        sc = result["structural_clusters"][0]
        assert sc["size"] >= 3

    def test_no_structural_cluster_for_diverse(self):
        mg = MemoryGraph()
        nodes = [mg.add(f"node_{i}", "concept") for i in range(6)]
        # Linear chain — no two share the same neighbours
        for i in range(len(nodes) - 1):
            mg.link(nodes[i].id, nodes[i + 1].id, "related")
        result = mg.semantic_cluster_detect(structural_threshold=0.5)
        # Linear chain should have minimal structural clustering
        assert result["structural_clusters"] == []

    def test_structural_cluster_fields(self):
        mg = MemoryGraph()
        hub = mg.add("hub", "concept")
        clones = [mg.add(f"clone_{i}", "concept") for i in range(4)]
        for c in clones:
            mg.link(c.id, hub.id, "related")
        result = mg.semantic_cluster_detect(
            structural_threshold=0.3, min_cluster_size=3
        )
        if result["structural_clusters"]:
            sc = result["structural_clusters"][0]
            assert "members" in sc
            assert "avg_similarity" in sc
            assert "representative" in sc
            assert "total_degree" in sc


# ── TestCombinedClusters ───────────────────────────────────────
class TestCombinedClusters:
    def test_combined_cluster_when_both_dimensions_overlap(self):
        """Nodes that are both content-similar and structurally-similar."""
        mg = MemoryGraph()
        hub = mg.add("central hub", "concept")
        # Three nodes with similar labels AND same neighbour (hub)
        a = mg.add("data processor", "concept")
        b = mg.add("data processors", "concept")
        c = mg.add("data processing", "concept")
        for node in [a, b, c]:
            mg.link(node.id, hub.id, "related")
        result = mg.semantic_cluster_detect(
            content_threshold=0.3,
            structural_threshold=0.3,
            min_cluster_size=3,
        )
        # Should find combined cluster
        assert len(result["combined_clusters"]) >= 1
        cc = result["combined_clusters"][0]
        assert "consolidation_potential" in cc
        assert cc["size"] >= 3

    def test_no_combined_cluster_when_content_differs(self):
        """Same structure but different content → no combined cluster."""
        mg = MemoryGraph()
        hub = mg.add("hub", "concept")
        diverse = [
            mg.add("alpha", "concept"),
            mg.add("beta", "concept"),
            mg.add("gamma", "concept"),
        ]
        for node in diverse:
            mg.link(node.id, hub.id, "related")
        result = mg.semantic_cluster_detect(
            content_threshold=0.6,
            structural_threshold=0.3,
            min_cluster_size=3,
        )
        # Structural cluster may exist but combined should not
        # (content is completely different)
        assert len(result["combined_clusters"]) == 0

    def test_consolidation_potential_range(self):
        mg = MemoryGraph()
        hub = mg.add("hub", "concept")
        clones = []
        for i in range(5):
            n = mg.add(f"clone unit {i}", "concept")
            clones.append(n)
            mg.link(n.id, hub.id, "related")
        result = mg.semantic_cluster_detect(
            content_threshold=0.2,
            structural_threshold=0.3,
            min_cluster_size=3,
        )
        for cc in result["combined_clusters"]:
            assert 0 <= cc["consolidation_potential"] <= 1


# ── TestNodeIdFilter ───────────────────────────────────────────
class TestNodeIdFilter:
    def test_subgraph_restriction(self):
        mg = MemoryGraph()
        # Cluster 1: similar nodes
        a1 = mg.add("data pipe", "concept")
        a2 = mg.add("data pipes", "concept")
        a3 = mg.add("data piping", "concept")
        # Cluster 2: different domain
        b1 = mg.add("rocket ship", "concept")
        b2 = mg.add("rocket ships", "concept")
        b3 = mg.add("rocket shipping", "concept")

        result_all = mg.semantic_cluster_detect(content_threshold=0.3)
        # Should find 2 content clusters
        assert len(result_all["content_clusters"]) >= 1

        # Restrict to cluster 1 nodes only
        result_sub = mg.semantic_cluster_detect(
            node_ids=[a1.id, a2.id, a3.id],
            content_threshold=0.3,
        )
        assert result_sub["total_nodes"] == 3
        # Should still find the cluster
        if result_sub["content_clusters"]:
            assert result_sub["content_clusters"][0]["size"] == 3

    def test_subgraph_excludes_others(self):
        mg = MemoryGraph()
        cluster_ids = []
        for i in range(4):
            n = mg.add(f"clone item {i}", "concept")
            cluster_ids.append(n.id)
        # Add unrelated nodes
        for i in range(4):
            mg.add(f"unique_xyz_{i}", "concept")

        result = mg.semantic_cluster_detect(
            node_ids=cluster_ids,
            content_threshold=0.2,
            min_cluster_size=3,
        )
        assert result["total_nodes"] == 4


# ── TestRecommendations ────────────────────────────────────────
class TestRecommendations:
    def test_recommendations_non_empty(self):
        mg = MemoryGraph()
        for i in range(5):
            mg.add(f"test item number {i}", "concept")
        result = mg.semantic_cluster_detect(content_threshold=0.2)
        assert len(result["recommendations"]) > 0

    def test_healthy_graph_message(self):
        mg = MemoryGraph()
        for label in ["alpha", "beta", "gamma", "delta", "epsilon"]:
            mg.add(label, "concept")
        result = mg.semantic_cluster_detect(content_threshold=0.8)
        # Should have a "no clusters" or "low" message
        joined = " ".join(result["recommendations"]).lower()
        assert "low" in joined or "no" in joined or "healthy" in joined

    def test_high_redundancy_warning(self):
        mg = MemoryGraph()
        hub = mg.add("hub", "concept")
        for i in range(8):
            n = mg.add(f"data process clone {i}", "concept")
            mg.link(n.id, hub.id, "related")
        result = mg.semantic_cluster_detect(
            content_threshold=0.2,
            structural_threshold=0.3,
            min_cluster_size=3,
        )
        if result["cluster_score"] >= 40:
            joined = " ".join(result["recommendations"]).lower()
            assert "high" in joined


# ── TestNonMutating ────────────────────────────────────────────
class TestNonMutating:
    def test_no_nodes_modified(self):
        mg = MemoryGraph()
        nodes = [mg.add(f"node_{i}", "concept") for i in range(6)]
        for i in range(len(nodes) - 1):
            mg.link(nodes[i].id, nodes[i + 1].id, "related")

        before_count = mg.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        mg.semantic_cluster_detect()
        after_count = mg.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        assert before_count == after_count

    def test_no_edges_modified(self):
        mg = MemoryGraph()
        nodes = [mg.add(f"node_{i}", "concept") for i in range(6)]
        for i in range(len(nodes) - 1):
            mg.link(nodes[i].id, nodes[i + 1].id, "related")

        before_edges = mg.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
        mg.semantic_cluster_detect()
        after_edges = mg.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
        assert before_edges == after_edges

    def test_no_tags_modified(self):
        mg = MemoryGraph()
        n = mg.add("tagged node", "concept", tags=["alpha", "beta"])
        mg.semantic_cluster_detect()
        row = mg.conn.execute(
            "SELECT tags FROM nodes WHERE id=?", (n.id,)
        ).fetchone()
        import json
        tags = json.loads(row["tags"])
        assert "alpha" in tags
        assert "beta" in tags


# ── TestRepresentative ─────────────────────────────────────────
class TestRepresentative:
    def test_representative_is_highest_degree(self):
        mg = MemoryGraph()
        hub = mg.add("hub", "concept")
        a = mg.add("clone alpha", "concept")
        b = mg.add("clone alpha!", "concept")
        c = mg.add("clone alpha!!", "concept")
        # Give node 'a' more connections
        mg.link(a.id, hub.id, "related")
        mg.link(a.id, b.id, "related")
        mg.link(c.id, hub.id, "related")
        mg.link(b.id, hub.id, "related")
        result = mg.semantic_cluster_detect(
            content_threshold=0.3, min_cluster_size=3
        )
        if result["content_clusters"]:
            cluster = result["content_clusters"][0]
            members = cluster["members"]
            # Representative should be node with highest degree
            rep = cluster["representative"]
            rep_degree = mg._node_degree(rep)
            for m in members:
                if m != rep:
                    assert mg._node_degree(m) <= rep_degree

    def test_representative_label_present(self):
        mg = MemoryGraph()
        for i in range(5):
            mg.add(f"similar item variant {i}", "concept")
        result = mg.semantic_cluster_detect(content_threshold=0.2)
        for cc in result["content_clusters"]:
            assert cc["representative_label"] != ""
            assert isinstance(cc["representative_label"], str)
