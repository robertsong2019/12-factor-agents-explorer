"""Tests for derivation_lineage_report() — Cycle 339.

Unified lineage analysis combining backward provenance
(trace_derivation) and forward impact (trace_derivation_impact).
"""
import pytest
from memory_graph import MemoryGraph


def _add(g, label, kind="fact"):
    """Helper: add a node and return its id."""
    return g.add(label, kind=kind).id


@pytest.fixture
def populated():
    """Create a derivation graph:
        sensor_1 → raw_data → summary → report
        sensor_2 → raw_data
        summary → insight
    """
    g = MemoryGraph()
    ids = {}
    for name in ["sensor_1", "sensor_2", "raw_data",
                 "summary", "report", "insight"]:
        ids[name] = _add(g, name)
    g.add_causal_edge(ids["summary"], ids["raw_data"],
                      "derived_from", confidence=0.9)
    g.add_causal_edge(ids["raw_data"], ids["sensor_1"],
                      "computed_from", confidence=1.0)
    g.add_causal_edge(ids["raw_data"], ids["sensor_2"],
                      "computed_from", confidence=1.0)
    g.add_causal_edge(ids["report"], ids["summary"],
                      "derived_from", confidence=0.8)
    g.add_causal_edge(ids["insight"], ids["summary"],
                      "derived_from", confidence=0.85)
    g._test_ids = ids
    return g


# ── Structure ──────────────────────────────────────────────

class TestStructure:
    def test_result_keys(self):
        mg = MemoryGraph()
        nid = _add(mg, "a")
        rep = mg.derivation_lineage_report(nid)
        expected = {
            "node", "backward", "forward", "fan_in", "fan_out",
            "lineage_size", "max_upstream_depth", "max_downstream_depth",
            "is_root", "is_leaf", "is_isolated", "completeness",
            "avg_confidence", "bottleneck_score", "summary",
        }
        assert set(rep.keys()) == expected

    def test_node_field(self):
        mg = MemoryGraph()
        nid = _add(mg, "x")
        rep = mg.derivation_lineage_report(nid)
        assert rep["node"] == nid

    def test_backward_is_dict(self):
        mg = MemoryGraph()
        nid = _add(mg, "a")
        rep = mg.derivation_lineage_report(nid)
        assert isinstance(rep["backward"], dict)

    def test_forward_is_dict(self):
        mg = MemoryGraph()
        nid = _add(mg, "a")
        rep = mg.derivation_lineage_report(nid)
        assert isinstance(rep["forward"], dict)

    def test_backward_has_trace_keys(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert "roots" in rep["backward"]
        assert "chains" in rep["backward"]
        assert "all_sources" in rep["backward"]

    def test_forward_has_impact_keys(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert "leaves" in rep["forward"]
        assert "chains" in rep["forward"]
        assert "all_dependents" in rep["forward"]


# ── Isolated node (no lineage) ────────────────────────────

class TestIsolated:
    def test_isolated_root(self):
        mg = MemoryGraph()
        nid = _add(mg, "lonely")
        rep = mg.derivation_lineage_report(nid)
        assert rep["is_root"] is True

    def test_isolated_leaf(self):
        mg = MemoryGraph()
        nid = _add(mg, "lonely")
        rep = mg.derivation_lineage_report(nid)
        assert rep["is_leaf"] is True

    def test_isolated_flag(self):
        mg = MemoryGraph()
        nid = _add(mg, "lonely")
        rep = mg.derivation_lineage_report(nid)
        assert rep["is_isolated"] is True

    def test_isolated_fan_in_zero(self):
        mg = MemoryGraph()
        nid = _add(mg, "lonely")
        rep = mg.derivation_lineage_report(nid)
        assert rep["fan_in"] == 0

    def test_isolated_fan_out_zero(self):
        mg = MemoryGraph()
        nid = _add(mg, "lonely")
        rep = mg.derivation_lineage_report(nid)
        assert rep["fan_out"] == 0

    def test_isolated_lineage_size_one(self):
        mg = MemoryGraph()
        nid = _add(mg, "lonely")
        rep = mg.derivation_lineage_report(nid)
        assert rep["lineage_size"] == 1

    def test_isolated_completeness(self):
        mg = MemoryGraph()
        nid = _add(mg, "lonely")
        rep = mg.derivation_lineage_report(nid)
        assert rep["completeness"] == 1.0

    def test_isolated_avg_confidence(self):
        mg = MemoryGraph()
        nid = _add(mg, "lonely")
        rep = mg.derivation_lineage_report(nid)
        assert rep["avg_confidence"] == 1.0

    def test_isolated_summary_text(self):
        mg = MemoryGraph()
        nid = _add(mg, "lonely")
        rep = mg.derivation_lineage_report(nid)
        assert "no derivation lineage" in rep["summary"]

    def test_nonexistent_node(self):
        mg = MemoryGraph()
        rep = mg.derivation_lineage_report("ghost")
        assert rep["is_isolated"] is True
        assert rep["lineage_size"] == 1


# ── Root node (has downstream but no upstream) ─────────────

class TestRoot:
    def test_sensor_is_root(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["sensor_1"])
        assert rep["is_root"] is True

    def test_sensor_not_leaf(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["sensor_1"])
        assert rep["is_leaf"] is False

    def test_sensor_not_isolated(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["sensor_1"])
        assert rep["is_isolated"] is False

    def test_sensor_fan_in_zero(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["sensor_1"])
        assert rep["fan_in"] == 0

    def test_sensor_fan_out_positive(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["sensor_1"])
        assert rep["fan_out"] >= 1

    def test_sensor_downstream_depth(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["sensor_1"])
        assert rep["max_downstream_depth"] >= 1

    def test_sensor_upstream_depth_zero(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["sensor_1"])
        assert rep["max_upstream_depth"] == 0


# ── Leaf node (has upstream but no downstream) ─────────────

class TestLeaf:
    def test_report_is_leaf(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["report"])
        assert rep["is_leaf"] is True

    def test_report_not_root(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["report"])
        assert rep["is_root"] is False

    def test_report_fan_out_zero(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["report"])
        assert rep["fan_out"] == 0

    def test_report_fan_in_positive(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["report"])
        assert rep["fan_in"] >= 1

    def test_report_upstream_depth(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["report"])
        assert rep["max_upstream_depth"] >= 1


# ── Middle node (both upstream and downstream) ────────────

class TestMiddle:
    def test_summary_not_root(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert rep["is_root"] is False

    def test_summary_not_leaf(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert rep["is_leaf"] is False

    def test_summary_not_isolated(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert rep["is_isolated"] is False

    def test_summary_fan_in(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert rep["fan_in"] == 1  # derived_from raw_data

    def test_summary_fan_out(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert rep["fan_out"] == 2  # report + insight derive from it

    def test_summary_lineage_size(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        # upstream: raw_data, sensor_1, sensor_2 (3)
        # downstream: report, insight (2)
        # self: summary (1) → total 6
        assert rep["lineage_size"] == 6

    def test_summary_both_depths_positive(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert rep["max_upstream_depth"] >= 1
        assert rep["max_downstream_depth"] >= 1


# ── Confidence metrics ────────────────────────────────────

class TestConfidence:
    def test_avg_confidence_range(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert 0.0 <= rep["avg_confidence"] <= 1.0

    def test_completeness_range(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert 0.0 <= rep["completeness"] <= 1.0

    def test_completeness_all_high(self, populated):
        ids = populated._test_ids
        # All edges have confidence >= 0.8 (0.8, 0.85, 0.9, 1.0, 1.0)
        rep = populated.derivation_lineage_report(ids["summary"])
        assert rep["completeness"] == 1.0

    def test_avg_confidence_value(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        # Edges from summary's perspective:
        # backward: summary->raw_data (0.9), raw_data->sensor_1 (1.0), raw_data->sensor_2 (1.0)
        # forward: report->summary (0.8), insight->summary (0.85)
        # avg = (0.9 + 1.0 + 1.0 + 0.8 + 0.85) / 5 = 0.91
        assert abs(rep["avg_confidence"] - 0.91) < 0.01

    def test_low_completeness_with_threshold(self):
        g = MemoryGraph()
        a = _add(g, "a")
        b = _add(g, "b")
        c = _add(g, "c")
        g.add_causal_edge(b, a, "derived_from", confidence=0.3)
        g.add_causal_edge(c, b, "derived_from", confidence=0.4)
        rep = g.derivation_lineage_report(b)
        assert rep["completeness"] == 0.0  # no edge >= 0.8


# ── Bottleneck score ──────────────────────────────────────

class TestBottleneck:
    def test_bottleneck_isolated(self):
        mg = MemoryGraph()
        nid = _add(mg, "a")
        rep = mg.derivation_lineage_report(nid)
        # fan_out=0, fan_in=0 -> 0/1 = 0
        assert rep["bottleneck_score"] == 0.0

    def test_bottleneck_root_fanout(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["sensor_1"])
        # fan_out>=1, fan_in=0 -> fan_out/max(0,1) = fan_out
        assert rep["bottleneck_score"] >= 1.0

    def test_bottleneck_middle(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        # fan_out=2, fan_in=1 -> 2/1 = 2.0
        assert abs(rep["bottleneck_score"] - 2.0) < 0.01

    def test_bottleneck_summary_text(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert "Bottleneck" in rep["summary"]

    def test_no_bottleneck_when_balanced(self):
        g = MemoryGraph()
        ids = {n: _add(g, n) for n in ["a", "b", "c", "d"]}
        g.add_causal_edge(ids["a"], ids["b"], "derived_from", confidence=0.9)
        g.add_causal_edge(ids["a"], ids["c"], "derived_from", confidence=0.9)
        g.add_causal_edge(ids["d"], ids["a"], "derived_from", confidence=0.9)
        rep = g.derivation_lineage_report(ids["a"])
        # fan_in=2 (b,c), fan_out=1 (d) -> 0.5, no bottleneck
        assert rep["bottleneck_score"] < 1.0
        assert "Bottleneck" not in rep["summary"]


# ── Summary text ──────────────────────────────────────────

class TestSummary:
    def test_summary_is_string(self):
        mg = MemoryGraph()
        nid = _add(mg, "a")
        rep = mg.derivation_lineage_report(nid)
        assert isinstance(rep["summary"], str)

    def test_summary_mentions_node(self):
        mg = MemoryGraph()
        nid = _add(mg, "special_node")
        rep = mg.derivation_lineage_report(nid)
        assert nid in rep["summary"]

    def test_summary_mentions_lineage_size(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert "6 node" in rep["summary"]

    def test_summary_mentions_depth(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert "depth" in rep["summary"]

    def test_summary_mentions_confidence(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert "confidence" in rep["summary"]

    def test_summary_isolated_wording(self):
        mg = MemoryGraph()
        nid = _add(mg, "alone")
        rep = mg.derivation_lineage_report(nid)
        assert "no derivation lineage" in rep["summary"]

    def test_summary_root_wording(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["sensor_1"])
        assert "root" in rep["summary"].lower()

    def test_summary_leaf_wording(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["report"])
        assert "leaf" in rep["summary"].lower()

    def test_summary_mentions_sources_count(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert "1 upstream source" in rep["summary"]

    def test_summary_mentions_dependents_count(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        assert "2 downstream dependent" in rep["summary"]


# ── Max depth parameter ───────────────────────────────────

class TestMaxDepth:
    def test_max_depth_truncates(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["report"], max_depth=1)
        assert rep["max_upstream_depth"] == 1

    def test_max_depth_default_10(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["report"])
        # Full chain: report->summary->raw_data->sensor_1/sensor_2 = depth 3
        assert rep["max_upstream_depth"] == 3

    def test_max_depth_1_summary(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"], max_depth=1)
        # backward: only summary->raw_data
        assert rep["max_upstream_depth"] == 1
        # forward: only report->summary, insight->summary
        assert rep["max_downstream_depth"] == 1


# ── Non-mutating ──────────────────────────────────────────

class TestNonMutating:
    def test_query_node_unchanged(self, populated):
        ids = populated._test_ids
        before = populated.get_node(ids["summary"])
        populated.derivation_lineage_report(ids["summary"])
        after = populated.get_node(ids["summary"])
        assert before == after

    def test_no_new_edges(self, populated):
        ids = populated._test_ids
        count_before = populated.count_edges()
        populated.derivation_lineage_report(ids["summary"])
        count_after = populated.count_edges()
        assert count_before == count_after

    def test_backward_trace_unchanged(self, populated):
        ids = populated._test_ids
        before = populated.trace_derivation(ids["summary"])
        populated.derivation_lineage_report(ids["summary"])
        after = populated.trace_derivation(ids["summary"])
        assert before == after


# ── Integration with existing APIs ────────────────────────

class TestIntegration:
    def test_consistent_with_trace_derivation(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        direct = populated.trace_derivation(ids["summary"])
        assert rep["backward"]["roots"] == direct["roots"]
        assert rep["backward"]["all_sources"] == direct["all_sources"]
        assert rep["backward"]["depth_reached"] == direct["depth_reached"]

    def test_consistent_with_trace_derivation_impact(self, populated):
        ids = populated._test_ids
        rep = populated.derivation_lineage_report(ids["summary"])
        direct = populated.trace_derivation_impact(ids["summary"])
        assert rep["forward"]["leaves"] == direct["leaves"]
        assert rep["forward"]["all_dependents"] == direct["all_dependents"]
        assert rep["forward"]["depth_reached"] == direct["depth_reached"]

    def test_works_after_propagate_correction(self):
        g = MemoryGraph()
        base = _add(g, "base")
        mid = _add(g, "mid")
        top = _add(g, "top")
        g.add_causal_edge(mid, base, "derived_from", confidence=1.0)
        g.add_causal_edge(top, mid, "derived_from", confidence=1.0)
        g.propagate_correction(base, new_content="corrected base")
        rep = g.derivation_lineage_report(top)
        assert rep["is_leaf"] is True
        assert rep["max_upstream_depth"] >= 1

    def test_diamond_dependency(self):
        """Diamond: A -> B, A -> C, B -> D, C -> D"""
        g = MemoryGraph()
        ids = {n: _add(g, n) for n in ["A", "B", "C", "D"]}
        g.add_causal_edge(ids["B"], ids["A"], "derived_from", confidence=0.9)
        g.add_causal_edge(ids["C"], ids["A"], "derived_from", confidence=0.9)
        g.add_causal_edge(ids["D"], ids["B"], "derived_from", confidence=0.8)
        g.add_causal_edge(ids["D"], ids["C"], "derived_from", confidence=0.8)
        rep = g.derivation_lineage_report(ids["A"])
        assert rep["is_root"] is True
        assert rep["fan_out"] == 2  # B and C derive from A
        assert rep["max_downstream_depth"] == 2  # A -> B/C -> D
        assert ids["D"] in rep["forward"]["all_dependents"]

    def test_diamond_from_d(self):
        """From D's perspective in the diamond."""
        g = MemoryGraph()
        ids = {n: _add(g, n) for n in ["A", "B", "C", "D"]}
        g.add_causal_edge(ids["B"], ids["A"], "derived_from", confidence=0.9)
        g.add_causal_edge(ids["C"], ids["A"], "derived_from", confidence=0.9)
        g.add_causal_edge(ids["D"], ids["B"], "derived_from", confidence=0.8)
        g.add_causal_edge(ids["D"], ids["C"], "derived_from", confidence=0.8)
        rep = g.derivation_lineage_report(ids["D"])
        assert rep["is_leaf"] is True
        assert rep["fan_in"] == 2  # D derives from both B and C
        assert rep["max_upstream_depth"] == 2  # D -> B/C -> A
        assert ids["A"] in rep["backward"]["all_sources"]

    def test_cycle_safe(self):
        """Circular derivation should not hang."""
        g = MemoryGraph()
        x = _add(g, "x")
        y = _add(g, "y")
        g.add_causal_edge(x, y, "derived_from", confidence=0.5)
        g.add_causal_edge(y, x, "derived_from", confidence=0.5)
        rep = g.derivation_lineage_report(x)
        assert isinstance(rep["summary"], str)
        assert rep["lineage_size"] >= 2


# ── Determinism ───────────────────────────────────────────

class TestDeterminism:
    def test_same_result_twice(self, populated):
        ids = populated._test_ids
        rep1 = populated.derivation_lineage_report(ids["summary"])
        rep2 = populated.derivation_lineage_report(ids["summary"])
        assert rep1 == rep2

    def test_summary_deterministic(self, populated):
        ids = populated._test_ids
        rep1 = populated.derivation_lineage_report(ids["summary"])
        rep2 = populated.derivation_lineage_report(ids["summary"])
        assert rep1["summary"] == rep2["summary"]


# ── Edge cases ────────────────────────────────────────────

class TestEdgeCases:
    def test_single_edge(self):
        g = MemoryGraph()
        a = _add(g, "a")
        b = _add(g, "b")
        g.add_causal_edge(b, a, "derived_from", confidence=1.0)
        rep = g.derivation_lineage_report(a)
        assert rep["is_root"] is True
        assert rep["fan_out"] == 1
        assert rep["lineage_size"] == 2

    def test_single_edge_reverse(self):
        g = MemoryGraph()
        a = _add(g, "a")
        b = _add(g, "b")
        g.add_causal_edge(b, a, "derived_from", confidence=1.0)
        rep = g.derivation_lineage_report(b)
        assert rep["is_leaf"] is True
        assert rep["fan_in"] == 1
        assert rep["lineage_size"] == 2

    def test_long_chain(self):
        g = MemoryGraph()
        node_ids = [_add(g, f"n{i}") for i in range(10)]
        for i in range(9):
            g.add_causal_edge(
                node_ids[i + 1], node_ids[i],
                "derived_from", confidence=0.9
            )
        rep = g.derivation_lineage_report(node_ids[5])
        assert rep["is_root"] is False
        assert rep["is_leaf"] is False
        assert rep["max_upstream_depth"] == 5
        assert rep["max_downstream_depth"] == 4
        assert rep["lineage_size"] == 10

    def test_computed_from_relation(self):
        g = MemoryGraph()
        result = _add(g, "result")
        inp = _add(g, "input")
        g.add_causal_edge(
            result, inp, "computed_from", confidence=0.95
        )
        rep = g.derivation_lineage_report(result)
        assert rep["fan_in"] == 1
        assert rep["is_leaf"] is True
        assert inp in rep["backward"]["all_sources"]

    def test_mixed_relations(self):
        g = MemoryGraph()
        ids = {n: _add(g, n) for n in ["raw", "processed", "analyzed", "report"]}
        g.add_causal_edge(
            ids["processed"], ids["raw"],
            "computed_from", confidence=1.0
        )
        g.add_causal_edge(
            ids["analyzed"], ids["processed"],
            "derived_from", confidence=0.9
        )
        g.add_causal_edge(
            ids["report"], ids["analyzed"],
            "derived_from", confidence=0.8
        )
        rep = g.derivation_lineage_report(ids["processed"])
        assert rep["fan_in"] == 1
        assert rep["fan_out"] == 1
        assert rep["lineage_size"] == 4
