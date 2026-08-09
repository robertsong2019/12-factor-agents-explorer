"""Cycle 393-394: temporal_decay_impact + edge_weight_entropy + node_summary"""
import time
import math
from memory_graph import MemoryGraph


class TestTemporalDecayImpact:
    def setUp(self):
        self.g = MemoryGraph(":memory:")

    def test_all_nodes(self):
        self.setUp()
        self.g.add("a"); self.g.add("b"); self.g.add("c")
        r = self.g.temporal_decay_impact()
        assert r["summary"]["fresh_count"] == 3
        assert r["summary"]["mean_retention"] > 0.9
        assert len(r["nodes"]) == 3

    def test_filtered_nodes(self):
        self.setUp()
        a = self.g.add("a"); b = self.g.add("b"); self.g.add("c")
        r = self.g.temporal_decay_impact(node_ids=[a.id, b.id])
        assert len(r["nodes"]) == 2

    def test_categories(self):
        self.setUp()
        self.g.add("fresh"); old = self.g.add("old")
        # Make "old" very stale
        self.g.conn.execute(
            "UPDATE nodes SET accessed = ? WHERE id = ?",
            (time.time() - 30 * 86400, old.id)
        )
        self.g.conn.commit()
        r = self.g.temporal_decay_impact()
        cats = {n["label"]: n["category"] for n in r["nodes"]}
        assert cats["fresh"] == "fresh"
        assert cats["old"] in ("stale", "at_risk")

    def test_decay_impact_score(self):
        self.setUp()
        self.g.add("a"); old = self.g.add("b")
        self.g.conn.execute(
            "UPDATE nodes SET accessed = ? WHERE id = ?",
            (time.time() - 50 * 86400, old.id)
        )
        self.g.conn.commit()
        r = self.g.temporal_decay_impact()
        assert 0 < r["summary"]["decay_impact_score"] <= 1

    def test_empty_graph(self):
        self.setUp()
        r = self.g.temporal_decay_impact()
        assert r["summary"]["mean_retention"] == 0
        assert r["nodes"] == []

    def test_custom_half_life(self):
        self.setUp()
        self.g.add("a")
        r1 = self.g.temporal_decay_impact(half_life_hours=1)
        r2 = self.g.temporal_decay_impact(half_life_hours=168)
        assert r1["summary"]["fresh_count"] == 1
        assert r2["summary"]["fresh_count"] == 1

    def test_summary_structure(self):
        self.setUp()
        self.g.add("x")
        r = self.g.temporal_decay_impact()
        assert set(r.keys()) == {"nodes", "summary", "categories"}
        assert set(r["summary"].keys()) == {
            "mean_retention", "fresh_count", "stale_count",
            "at_risk_count", "decay_impact_score"
        }


class TestEdgeWeightEntropy:
    def setUp(self):
        self.g = MemoryGraph(":memory:")

    def test_uniform_weights_high_entropy(self):
        self.setUp()
        self.g.add("a"); self.g.add("b"); self.g.add("c")
        self.g.link("a", "b", "rel", weight=1.0)
        self.g.link("b", "c", "rel", weight=1.0)
        self.g.link("a", "c", "rel", weight=1.0)
        r = self.g.edge_weight_entropy()
        assert r["num_edges"] == 3
        assert r["entropy"] > 0
        assert r["normalized_entropy"] > 0.9

    def test_skewed_weights_low_entropy(self):
        self.setUp()
        self.g.add("a"); self.g.add("b"); self.g.add("c")
        self.g.link("a", "b", "rel", weight=100.0)
        self.g.link("b", "c", "rel", weight=1.0)
        r = self.g.edge_weight_entropy()
        assert r["normalized_entropy"] < 0.9

    def test_empty_graph(self):
        self.setUp()
        r = self.g.edge_weight_entropy()
        assert r["entropy"] == 0
        assert r["num_edges"] == 0

    def test_relation_filter(self):
        self.setUp()
        self.g.add("a"); self.g.add("b"); self.g.add("c")
        self.g.link("a", "b", "rel1", weight=1.0)
        self.g.link("b", "c", "rel2", weight=1.0)
        r1 = self.g.edge_weight_entropy(relation="rel1")
        r2 = self.g.edge_weight_entropy(relation="rel2")
        assert r1["num_edges"] == 1
        assert r2["num_edges"] == 1

    def test_weight_range(self):
        self.setUp()
        self.g.add("a"); self.g.add("b"); self.g.add("c")
        self.g.link("a", "b", "r", weight=0.1)
        self.g.link("b", "c", "r", weight=5.0)
        r = self.g.edge_weight_entropy()
        assert r["weight_range"][0] <= 0.1
        assert r["weight_range"][1] >= 5.0

    def test_dominant_edges(self):
        self.setUp()
        self.g.add("a"); self.g.add("b"); self.g.add("c")
        self.g.link("a", "b", "r", weight=10.0)
        self.g.link("b", "c", "r", weight=1.0)
        r = self.g.edge_weight_entropy()
        assert len(r["dominant_edges"]) == 2
        assert r["dominant_edges"][0]["weight"] >= r["dominant_edges"][1]["weight"]

    def test_zero_weights(self):
        self.setUp()
        self.g.add("a"); self.g.add("b")
        self.g.link("a", "b", "r", weight=0.0)
        r = self.g.edge_weight_entropy()
        assert r["entropy"] == 0
        assert r["num_edges"] == 1


class TestNodeSummary:
    def setUp(self):
        self.g = MemoryGraph(":memory:")

    def _add(self, label, **kw):
        """Add node and return its string ID."""
        return self.g.add(label, **kw).id

    def test_basic_structure(self):
        self.setUp()
        nid = self._add("test_node", kind="fact", data={"key": "val"})
        r = self.g.node_summary(nid)
        assert r["node"]["label"] == "test_node"
        assert "connectivity" in r
        assert "role" in r

    def test_connectivity(self):
        self.setUp()
        a = self._add("a"); b = self._add("b"); c = self._add("c")
        self.g.link(a, b, "r"); self.g.link(a, c, "r")
        r = self.g.node_summary(a)
        assert r["connectivity"]["out_degree"] == 2

    def test_role_isolated(self):
        self.setUp()
        nid = self._add("lonely")
        r = self.g.node_summary(nid)
        assert r["role"] == "isolated"

    def test_role_hub(self):
        self.setUp()
        hub = self._add("hub")
        leaves = []
        for i in range(10):
            lid = self._add(f"leaf_{i}")
            leaves.append(lid)
            self.g.link(hub, lid, "r")
            self.g.link(lid, hub, "r_back")
        r = self.g.node_summary(hub)
        assert r["role"] in ("hub", "source")

    def test_entropy_included(self):
        self.setUp()
        e1 = self._add("e1"); e2 = self._add("e2")
        self.g.link(e1, e2, "r", weight=1.0)
        r = self.g.node_summary(e1, include_entropy=True)
        assert "entropy" in r

    def test_entropy_excluded(self):
        self.setUp()
        nid = self._add("e1")
        r = self.g.node_summary(nid, include_entropy=False)
        assert "entropy" not in r

    def test_centrality_included(self):
        self.setUp()
        c1 = self._add("c1"); c2 = self._add("c2")
        self.g.link(c1, c2, "r")
        r = self.g.node_summary(c1, include_centrality=True)
        assert "centrality" in r
        assert "degree_centrality" in r["centrality"]

    def test_temporal_included(self):
        self.setUp()
        nid = self._add("t1")
        r = self.g.node_summary(nid, include_temporal=True)
        assert "temporal" in r
        assert "age_hours" in r["temporal"]
        assert "staleness" in r["temporal"]
        assert "retention" in r["temporal"]

    def test_temporal_stale_node(self):
        self.setUp()
        nid = self._add("old_node")
        self.g.conn.execute(
            "UPDATE nodes SET accessed = ? WHERE id = ?",
            (time.time() - 60 * 86400, nid)
        )
        self.g.conn.commit()
        r = self.g.node_summary(nid, include_temporal=True)
        assert r["temporal"]["staleness"] > 0.5
        assert r["temporal"]["retention"] < 0.3

    def test_not_found(self):
        self.setUp()
        r = self.g.node_summary("nonexistent")
        assert "error" in r

    def test_with_all_dimensions(self):
        self.setUp()
        nid = self._add("full", kind="fact")
        neighbor = self._add("neighbor")
        self.g.link(nid, neighbor, "r")
        r = self.g.node_summary(nid,
            include_entropy=True,
            include_centrality=True,
            include_temporal=True,
            include_trust=True)
        assert all(k in r for k in
                   ["node", "connectivity", "role", "entropy",
                    "centrality", "temporal", "trust"])
