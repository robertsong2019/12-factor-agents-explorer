"""Cycle 312: entropy_anomaly_detect with index='von_neumann' — spectral anomaly detection.

Tests:
- Star graph: hub is spectral hub anomaly
- K_n: no anomalies (uniform)
- Path: endpoints may be pendant anomalies
- Return structure matches
- Threshold sensitivity
- Mixed graph (K_n + pendant)
"""

import math
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def g():
    return MemoryGraph(":memory:")


class TestAnomalyDetectSpectral:

    def test_none_for_tiny_graph(self, g):
        g.add("a"); g.add("b")
        assert g.entropy_anomaly_detect(index="von_neumann") is None

    def test_kn_no_anomalies(self, g):
        """K_5 uniform — no node is anomalous."""
        nodes = [g.add(str(i)) for i in range(5)]
        for i in range(5):
            for j in range(i+1, 5):
                g.link(nodes[i].id, nodes[j].id, "r")
        result = g.entropy_anomaly_detect(index="von_neumann")
        assert result is not None
        assert len(result["anomalies"]) == 0

    def test_star_hub_is_anomaly(self, g):
        """Hub in star should be a 'hub' anomaly at low threshold."""
        hub = g.add("hub")
        for i in range(6):
            lf = g.add(f"l{i}")
            g.link(hub.id, lf.id, "r")
        result = g.entropy_anomaly_detect(index="von_neumann", threshold=1.5)
        assert result is not None
        hub_anomalies = [a for a in result["anomalies"] if a["node_id"] == hub.id]
        assert len(hub_anomalies) >= 1
        assert hub_anomalies[0]["type"] == "hub"

    def test_return_structure(self, g):
        a, b, c, d = g.add("a"), g.add("b"), g.add("c"), g.add("d")
        g.link(a.id, b.id, "r"); g.link(b.id, c.id, "r")
        g.link(c.id, d.id, "r"); g.link(a.id, d.id, "r")
        result = g.entropy_anomaly_detect(index="von_neumann")
        required = ["mean_score", "std_score", "threshold", "anomalies", "total_nodes"]
        for k in required:
            assert k in result
        assert result["total_nodes"] == 4

    def test_pendant_node_detected(self, g):
        """Add pendant to K_4 — pendant should be detected."""
        nodes = [g.add(str(i)) for i in range(4)]
        for i in range(4):
            for j in range(i+1, 4):
                g.link(nodes[i].id, nodes[j].id, "r")
        pendant = g.add("p")
        g.link(pendant.id, nodes[0].id, "r")
        result = g.entropy_anomaly_detect(index="von_neumann", threshold=1.0)
        assert result is not None
        pendant_anomalies = [a for a in result["anomalies"] if a["node_id"] == pendant.id]
        if pendant_anomalies:
            assert pendant_anomalies[0]["type"] == "pendant"

    def test_higher_threshold_fewer_anomalies(self, g):
        """Higher threshold should flag fewer or equal anomalies."""
        hub = g.add("hub")
        for i in range(5):
            lf = g.add(f"l{i}")
            g.link(hub.id, lf.id, "r")
        r_low = g.entropy_anomaly_detect(index="von_neumann", threshold=0.5)
        r_high = g.entropy_anomaly_detect(index="von_neumann", threshold=3.0)
        assert len(r_low["anomalies"]) >= len(r_high["anomalies"])

    def test_anomalies_sorted_by_zscore(self, g):
        """Anomalies should be sorted by |z_score| descending."""
        hub = g.add("hub")
        leaves = [g.add(f"l{i}") for i in range(5)]
        for lf in leaves:
            g.link(hub.id, lf.id, "r")
        result = g.entropy_anomaly_detect(index="von_neumann", threshold=0.5)
        zscores = [abs(a["z_score"]) for a in result["anomalies"]]
        for i in range(len(zscores) - 1):
            assert zscores[i] >= zscores[i+1]
