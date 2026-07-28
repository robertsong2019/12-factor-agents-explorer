"""Tests for entropy_anomaly_detect() — detect anomalous nodes by local entropy.

Flags hub (high diversity) and pendant (low diversity) nodes based on
statistical deviation from the graph mean.
"""
import math
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


@pytest.fixture
def diverse_graph(mg):
    """Graph with a clear hub and pendants.

    Star: center connected to 5 leaves, plus a triangle elsewhere.
    Center = high-degree hub, leaves = low-degree pendants.
    """
    center = mg.add("Hub", "concept")
    leaves = []
    for i in range(5):
        leaf = mg.add(f"Leaf{i}", "concept")
        mg.link(center.id, leaf.id, "relates")
        leaves.append(leaf)
    # Add a triangle to create degree diversity
    t1 = mg.add("Tri1", "concept")
    t2 = mg.add("Tri2", "concept")
    t3 = mg.add("Tri3", "concept")
    mg.link(t1.id, t2.id, "relates")
    mg.link(t2.id, t3.id, "relates")
    mg.link(t3.id, t1.id, "relates")
    return {"graph": mg, "center": center, "leaves": leaves, "tri": [t1, t2, t3]}


class TestAnomalyDetectStructure:
    def test_returns_none_for_small_graph(self, mg):
        mg.add("A", "concept")
        mg.add("B", "concept")
        result = mg.entropy_anomaly_detect()
        assert result is None

    def test_returns_dict_with_keys(self, diverse_graph):
        mg = diverse_graph["graph"]
        result = mg.entropy_anomaly_detect()
        assert isinstance(result, dict)
        assert "mean_score" in result
        assert "std_score" in result
        assert "threshold" in result
        assert "anomalies" in result
        assert "total_nodes" in result

    def test_total_nodes_count(self, diverse_graph):
        mg = diverse_graph["graph"]
        result = mg.entropy_anomaly_detect()
        # 1 hub + 5 leaves + 3 triangle = 9
        assert result["total_nodes"] == 9


class TestAnomalyDetectHub:
    def test_hub_detected(self, diverse_graph):
        mg = diverse_graph["graph"]
        result = mg.entropy_anomaly_detect()
        anomaly_ids = {a["node_id"] for a in result["anomalies"]}
        # The hub should be flagged (degree 5 vs degree 2 for triangle, degree 1 for leaves)
        assert diverse_graph["center"].id in anomaly_ids

    def test_hub_type_is_hub(self, diverse_graph):
        mg = diverse_graph["graph"]
        result = mg.entropy_anomaly_detect()
        hub_anomaly = next(
            a for a in result["anomalies"]
            if a["node_id"] == diverse_graph["center"].id
        )
        assert hub_anomaly["type"] == "hub"
        assert hub_anomaly["z_score"] > 0


class TestAnomalyDetectPendant:
    def test_pendants_detected(self, diverse_graph):
        mg = diverse_graph["graph"]
        result = mg.entropy_anomaly_detect(threshold=0.5)
        anomaly_ids = {a["node_id"] for a in result["anomalies"]}
        # At least some leaves should be flagged as pendants
        leaf_ids = {leaf.id for leaf in diverse_graph["leaves"]}
        flagged_leaves = anomaly_ids & leaf_ids
        assert len(flagged_leaves) > 0

    def test_pendant_type(self, diverse_graph):
        mg = diverse_graph["graph"]
        result = mg.entropy_anomaly_detect(threshold=0.5)
        pendants = [a for a in result["anomalies"] if a["type"] == "pendant"]
        assert len(pendants) > 0
        for p in pendants:
            assert p["z_score"] < 0


class TestAnomalyDetectThreshold:
    def test_higher_threshold_fewer_anomalies(self, diverse_graph):
        mg = diverse_graph["graph"]
        low_t = mg.entropy_anomaly_detect(threshold=1.0)
        high_t = mg.entropy_anomaly_detect(threshold=5.0)
        assert len(low_t["anomalies"]) >= len(high_t["anomalies"])

    def test_zero_threshold_all_anomalies(self, diverse_graph):
        mg = diverse_graph["graph"]
        result = mg.entropy_anomaly_detect(threshold=0.0)
        # Every node with non-zero z-score is an anomaly
        assert len(result["anomalies"]) >= 1


class TestAnomalyDetectEdgeCases:
    def test_uniform_graph_no_anomalies(self, mg):
        """Triangle (all nodes degree 2) should have zero std → no anomalies."""
        a = mg.add("A", "c")
        b = mg.add("B", "c")
        c = mg.add("C", "c")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        result = mg.entropy_anomaly_detect()
        assert result["std_score"] == 0.0
        assert result["anomalies"] == []

    def test_path_graph(self, mg):
        """Path of 4 nodes: endpoints (degree 1) vs middle (degree 2)."""
        nodes = [mg.add(f"N{i}", "c") for i in range(4)]
        for i in range(3):
            mg.link(nodes[i].id, nodes[i + 1].id, "r")
        result = mg.entropy_anomaly_detect(threshold=0.5)
        assert result is not None
        assert result["total_nodes"] == 4

    def test_single_isolated_node(self, mg):
        """Graph with an isolated node — it should have score 0."""
        nodes = [mg.add(f"N{i}", "c") for i in range(4)]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[1].id, nodes[2].id, "r")
        # nodes[3] is isolated
        result = mg.entropy_anomaly_detect(threshold=0.5)
        assert result is not None
        # Isolated node should be a pendant anomaly
        pendant_ids = {a["node_id"] for a in result["anomalies"] if a["type"] == "pendant"}
        assert nodes[3].id in pendant_ids


class TestAnomalyDetectIndex:
    def test_different_indices(self, diverse_graph):
        mg = diverse_graph["graph"]
        for idx in ["sombor", "randic", "zagreb_m1"]:
            result = mg.entropy_anomaly_detect(index=idx)
            assert result is not None
            assert result["total_nodes"] == 9


class TestAnomalyDetectSorting:
    def test_anomalies_sorted_by_zscore(self, diverse_graph):
        mg = diverse_graph["graph"]
        result = mg.entropy_anomaly_detect(threshold=0.5)
        z_scores = [abs(a["z_score"]) for a in result["anomalies"]]
        assert z_scores == sorted(z_scores, reverse=True)
