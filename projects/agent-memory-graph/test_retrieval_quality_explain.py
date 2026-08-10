"""Tests for retrieval_quality_explain() — Cycle 406.

Per-node diagnostic explanation for retrieval quality.
Companion to retrieval_quality_audit() (Cycle 404).
"""
import math
import time

import pytest

from memory_graph import MemoryGraph


# ── Helpers ───────────────────────────────────────────────

def _build_graph(spec: dict) -> tuple[MemoryGraph, dict[str, str]]:
    """Build a graph from a spec, return (graph, label_to_id_map).
    
    spec = {
        "nodes": [("label", weight), ...],
        "edges": [("label1", "label2"), ...],
    }
    """
    g = MemoryGraph()
    label_map: dict[str, str] = {}
    for item in spec.get("nodes", []):
        if isinstance(item, tuple):
            label, weight = item
        else:
            label, weight = item, 1.0
        node = g.add(label, weight=weight) if hasattr(g.add, "__code__") and "weight" in g.add.__code__.co_varnames else g.add(label)
        label_map[label] = node.id
        # Set weight manually if add() doesn't support it
        g.conn.execute("UPDATE nodes SET weight=? WHERE id=?", (weight, node.id))
    g.conn.commit()
    for src_label, tgt_label in spec.get("edges", []):
        g.link(label_map[src_label], label_map[tgt_label], relation="r")
    return g, label_map


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def simple_graph():
    """Graph with 5 nodes, 4 edges (path-like)."""
    g, lm = _build_graph({
        "nodes": [("Alpha", 1.0), ("Beta", 2.0), ("Gamma", 1.5),
                   ("Delta", 0.5), ("Epsilon", 1.0)],
        "edges": [("Alpha", "Beta"), ("Beta", "Gamma"),
                  ("Gamma", "Delta"), ("Delta", "Epsilon")],
    })
    return g, lm


@pytest.fixture
def community_graph():
    """Graph with two clear communities."""
    g, lm = _build_graph({
        "nodes": [("N1", 2.0), ("N2", 1.5), ("N3", 1.0),
                   ("N4", 2.0), ("N5", 1.5), ("N6", 1.0)],
        "edges": [("N1", "N2"), ("N2", "N3"), ("N1", "N3"),
                  ("N4", "N5"), ("N5", "N6"), ("N4", "N6")],
    })
    return g, lm


@pytest.fixture
def stale_graph():
    """Graph where one node is much older than others."""
    g, lm = _build_graph({
        "nodes": [("Fresh1", 1.0), ("Fresh2", 1.0), ("Stale1", 1.0)],
        "edges": [("Fresh1", "Fresh2"), ("Fresh2", "Stale1")],
    })
    now = time.time()
    g.conn.execute(
        "UPDATE nodes SET accessed=? WHERE id=?",
        (now - 86400 * 30, lm["Stale1"]),
    )
    g.conn.commit()
    return g, lm


# ── Structure Tests ───────────────────────────────────────

class TestStructure:
    def test_returns_dict(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"], lm["Gamma"]], lm["Beta"]
        )
        assert isinstance(result, dict)

    def test_required_top_keys(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"], lm["Gamma"]], lm["Beta"]
        )
        expected_keys = {
            "target_node", "freshness", "interference",
            "diversity", "coverage", "explanation",
            "suggestions", "duration_seconds",
        }
        assert expected_keys.issubset(result.keys())

    def test_target_node_keys(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"], lm["Gamma"]], lm["Beta"]
        )
        tn = result["target_node"]
        for key in ("node_id", "label", "weight", "community",
                     "neighbour_count", "freshness"):
            assert key in tn

    def test_freshness_keys(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"], lm["Gamma"]], lm["Beta"]
        )
        f = result["freshness"]
        for key in ("score", "set_mean", "ratio", "status"):
            assert key in f

    def test_interference_keys(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"], lm["Gamma"]], lm["Beta"]
        )
        i = result["interference"]
        for key in ("mean_overlap", "score", "status",
                     "top_overlapping_peers"):
            assert key in i

    def test_diversity_keys(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"], lm["Gamma"]], lm["Beta"]
        )
        d = result["diversity"]
        for key in ("community", "unique_contribution",
                     "communities_without", "communities_with", "gain"):
            assert key in d

    def test_coverage_keys(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"], lm["Gamma"]], lm["Beta"]
        )
        c = result["coverage"]
        for key in ("marginal_nodes", "marginal_pct", "status",
                     "graph_size"):
            assert key in c


# ── Validation Tests ──────────────────────────────────────

class TestValidation:
    def test_target_not_in_set(self, simple_graph):
        g, lm = simple_graph
        with pytest.raises(ValueError, match="not in node_ids"):
            g.retrieval_quality_explain(
                [lm["Alpha"], lm["Beta"]], lm["Gamma"]
            )

    def test_target_does_not_exist(self, simple_graph):
        g, lm = simple_graph
        with pytest.raises(ValueError, match="does not exist"):
            g.retrieval_quality_explain(
                [lm["Alpha"], "nonexistent_id"], "nonexistent_id"
            )


# ── Degenerate Cases ──────────────────────────────────────

class TestDegenerate:
    def test_single_node(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain([lm["Alpha"]], lm["Alpha"])
        assert result["interference"]["mean_overlap"] == 0.0
        assert result["interference"]["score"] == 1.0
        assert result["coverage"]["marginal_nodes"] >= 0

    def test_target_only_with_invalid_peers(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], "fake1", "fake2"], lm["Alpha"]
        )
        assert result["target_node"]["node_id"] == lm["Alpha"]
        assert result["interference"]["mean_overlap"] == 0.0


# ── Freshness Tests ───────────────────────────────────────

class TestFreshness:
    def test_fresh_score_range(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"], lm["Gamma"]], lm["Beta"]
        )
        assert 0.0 <= result["freshness"]["score"] <= 1.0

    def test_stale_node_below_average(self, stale_graph):
        g, lm = stale_graph
        result = g.retrieval_quality_explain(
            [lm["Fresh1"], lm["Fresh2"], lm["Stale1"]], lm["Stale1"]
        )
        assert result["freshness"]["status"] == "below"
        assert result["freshness"]["score"] < result["freshness"]["set_mean"]

    def test_fresh_node_above_average(self, stale_graph):
        g, lm = stale_graph
        result = g.retrieval_quality_explain(
            [lm["Fresh1"], lm["Fresh2"], lm["Stale1"]], lm["Fresh1"]
        )
        assert result["freshness"]["status"] == "above"
        assert result["freshness"]["score"] > result["freshness"]["set_mean"]

    def test_now_parameter(self, simple_graph):
        g, lm = simple_graph
        fixed_now = 2000000000.0
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"]], lm["Alpha"], now=fixed_now
        )
        assert isinstance(result["freshness"]["score"], float)


# ── Interference Tests ────────────────────────────────────

class TestInterference:
    def test_distinct_nodes_low_overlap(self, community_graph):
        g, lm = community_graph
        result = g.retrieval_quality_explain(
            [lm["N1"], lm["N4"]], lm["N1"]
        )
        assert result["interference"]["mean_overlap"] < 0.5

    def test_same_community_higher_overlap(self, community_graph):
        g, lm = community_graph
        result_same = g.retrieval_quality_explain(
            [lm["N1"], lm["N2"], lm["N3"]], lm["N1"]
        )
        result_diff = g.retrieval_quality_explain(
            [lm["N1"], lm["N4"], lm["N5"]], lm["N1"
            ]
        )
        # Same-community should have >= overlap than cross-community
        assert (
            result_same["interference"]["mean_overlap"]
            >= result_diff["interference"]["mean_overlap"]
        )

    def test_peer_structure(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"], lm["Gamma"]], lm["Alpha"]
        )
        peers = result["interference"]["top_overlapping_peers"]
        for p in peers:
            assert "node_id" in p
            assert "overlap" in p
            assert "shared_neighbours" in p
            assert 0.0 <= p["overlap"] <= 1.0

    def test_peers_sorted_descending(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"], lm["Gamma"], lm["Delta"]], lm["Alpha"]
        )
        peers = result["interference"]["top_overlapping_peers"]
        overlaps = [p["overlap"] for p in peers]
        assert overlaps == sorted(overlaps, reverse=True)


# ── Diversity Tests ───────────────────────────────────────

class TestDiversity:
    def test_unique_contribution_is_bool(self, community_graph):
        g, lm = community_graph
        result = g.retrieval_quality_explain(
            [lm["N1"], lm["N2"], lm["N4"]], lm["N4"]
        )
        assert isinstance(result["diversity"]["unique_contribution"], bool)

    def test_gain_nonneg(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"]], lm["Alpha"]
        )
        assert result["diversity"]["gain"] >= 0

    def test_communities_with_geq_without(self, community_graph):
        g, lm = community_graph
        result = g.retrieval_quality_explain(
            [lm["N1"], lm["N2"], lm["N4"]], lm["N4"]
        )
        assert (
            result["diversity"]["communities_with"]
            >= result["diversity"]["communities_without"]
        )


# ── Coverage Tests ────────────────────────────────────────

class TestCoverage:
    def test_marginal_nonneg(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Epsilon"], lm["Gamma"]], lm["Gamma"]
        )
        assert result["coverage"]["marginal_nodes"] >= 0

    def test_graph_size(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"]], lm["Alpha"]
        )
        assert result["coverage"]["graph_size"] == 5

    def test_marginal_pct_range(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"]], lm["Alpha"]
        )
        assert 0.0 <= result["coverage"]["marginal_pct"] <= 1.0


# ── Explanation & Suggestions ─────────────────────────────

class TestExplanationSuggestions:
    def test_explanation_nonempty(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"], lm["Gamma"]], lm["Beta"]
        )
        assert len(result["explanation"]) > 0

    def test_explanation_contains_label(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"]], lm["Alpha"]
        )
        assert "Alpha" in result["explanation"]

    def test_suggestions_nonempty(self, simple_graph):
        g, lm = simple_graph
        result = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"]], lm["Alpha"]
        )
        assert len(result["suggestions"]) >= 1

    def test_stale_suggestion(self, stale_graph):
        g, lm = stale_graph
        result = g.retrieval_quality_explain(
            [lm["Fresh1"], lm["Fresh2"], lm["Stale1"]], lm["Stale1"]
        )
        assert any("refresh" in s.lower() for s in result["suggestions"])


# ── Non-Mutating Tests ────────────────────────────────────

class TestNonMutating:
    def test_graph_unchanged(self, simple_graph):
        g, lm = simple_graph
        nodes_before = set(
            r["id"] for r in g.conn.execute(
                "SELECT id FROM nodes ORDER BY id"
            )
        )
        edges_before = list(
            g.conn.execute(
                "SELECT source, target FROM edges ORDER BY source, target"
            )
        )
        g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"], lm["Gamma"]], lm["Beta"]
        )
        nodes_after = set(
            r["id"] for r in g.conn.execute(
                "SELECT id FROM nodes ORDER BY id"
            )
        )
        edges_after = list(
            g.conn.execute(
                "SELECT source, target FROM edges ORDER BY source, target"
            )
        )
        assert nodes_before == nodes_after
        assert edges_before == edges_after


# ── Determinism Tests ─────────────────────────────────────

class TestDeterminism:
    def test_same_result_twice(self, simple_graph):
        g, lm = simple_graph
        r1 = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"], lm["Gamma"]], lm["Beta"]
        )
        r2 = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"], lm["Gamma"]], lm["Beta"]
        )
        assert r1["freshness"]["score"] == r2["freshness"]["score"]
        assert (
            r1["interference"]["mean_overlap"]
            == r2["interference"]["mean_overlap"]
        )

    def test_now_stable(self, simple_graph):
        g, lm = simple_graph
        fixed = 2000000000.0
        r1 = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"]], lm["Alpha"], now=fixed
        )
        r2 = g.retrieval_quality_explain(
            [lm["Alpha"], lm["Beta"]], lm["Alpha"], now=fixed
        )
        assert r1["freshness"]["score"] == r2["freshness"]["score"]


# ── Integration Tests ─────────────────────────────────────

class TestIntegration:
    def test_works_after_modification(self, simple_graph):
        g, lm = simple_graph
        new_node = g.add("NewNode")
        g.conn.execute(
            "UPDATE nodes SET weight=? WHERE id=?", (3.0, new_node.id)
        )
        g.conn.commit()
        g.link(lm["Alpha"], new_node.id, relation="new")
        result = g.retrieval_quality_explain(
            [lm["Alpha"], new_node.id], new_node.id
        )
        assert result["target_node"]["label"] == "NewNode"

    def test_consistent_with_audit(self, community_graph):
        g, lm = community_graph
        node_ids = [lm["N1"], lm["N2"], lm["N4"]]
        audit = g.retrieval_quality_audit(node_ids)
        explain = g.retrieval_quality_explain(node_ids, lm["N1"])
        # The per-node freshness in explain should match audit's per_node
        audit_n1 = next(
            (p for p in audit["per_node"] if p["node_id"] == lm["N1"]), None
        )
        if audit_n1:
            assert (
                abs(explain["freshness"]["score"] - audit_n1["freshness"])
                < 0.01
            )

    def test_algorithm_parameter(self, simple_graph):
        g, lm = simple_graph
        for algo in ["leiden", "greedy", "lp"]:
            result = g.retrieval_quality_explain(
                [lm["Alpha"], lm["Beta"], lm["Gamma"]], lm["Beta"],
                algorithm=algo,
            )
            assert "community" in result["diversity"]

    def test_large_graph(self):
        g = MemoryGraph()
        ids = []
        for i in range(100):
            n = g.add(f"Node{i}")
            g.conn.execute(
                "UPDATE nodes SET weight=? WHERE id=?",
                (float(i % 5 + 1), n.id),
            )
            ids.append(n.id)
        g.conn.commit()
        for i in range(99):
            g.link(ids[i], ids[i + 1], relation="r")
        for i in range(0, 99, 7):
            g.link(ids[i], ids[(i + 13) % 100], relation="cross")
        result = g.retrieval_quality_explain(
            [ids[i] for i in range(0, 100, 10)], ids[50]
        )
        assert result["target_node"]["node_id"] == ids[50]
        assert result["coverage"]["graph_size"] == 100


# ── Edge Cases ────────────────────────────────────────────

class TestEdgeCases:
    def test_isolated_node(self):
        g = MemoryGraph()
        iso = g.add("Isolated")
        other = g.add("Other")
        result = g.retrieval_quality_explain([iso.id, other.id], iso.id)
        assert result["interference"]["mean_overlap"] == 0.0
        assert result["coverage"]["marginal_nodes"] >= 0

    def test_all_same_timestamp(self):
        g = MemoryGraph()
        x = g.add("X")
        y = g.add("Y")
        g.link(x.id, y.id, relation="r")
        now = time.time()
        g.conn.execute("UPDATE nodes SET accessed=?", (now,))
        g.conn.commit()
        result = g.retrieval_quality_explain([x.id, y.id], x.id, now=now)
        assert result["freshness"]["status"] == "par"

    def test_star_graph(self):
        g = MemoryGraph()
        hub = g.add("Hub")
        g.conn.execute(
            "UPDATE nodes SET weight=? WHERE id=?", (5.0, hub.id)
        )
        spoke_ids = []
        for i in range(5):
            s = g.add(f"Spoke{i}")
            g.conn.execute(
                "UPDATE nodes SET weight=? WHERE id=?", (1.0, s.id)
            )
            g.link(hub.id, s.id, relation="spoke")
            spoke_ids.append(s.id)
        g.conn.commit()
        result = g.retrieval_quality_explain(
            [hub.id, spoke_ids[0], spoke_ids[1]], hub.id
        )
        assert result["coverage"]["marginal_nodes"] >= 0
