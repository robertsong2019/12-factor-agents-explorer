"""Tests for trace_derivation_impact() — forward derivation impact analysis.

Companion to trace_derivation (backward provenance).
"""
import pytest
from memory_graph import MemoryGraph


class TestTraceDerivationImpactBasic:
    """Basic functionality tests."""

    def setup_method(self):
        self.mg = MemoryGraph()
        # Build: raw_1 → summary_ab ← raw_2; summary_ab → report_top → exec_summary
        self.raw_1 = self.mg.add("raw_1")
        self.raw_2 = self.mg.add("raw_2")
        self.summary = self.mg.add("summary_ab")
        self.report = self.mg.add("report_top")
        self.exec_sum = self.mg.add("exec_summary")
        self.orphan = self.mg.add("orphan")

        # Edge semantics: add_causal_edge(source, target, relation)
        # means source is derived from target.
        self.mg.add_causal_edge(self.summary.id, self.raw_1.id,
                                "derived_from", confidence=0.9)
        self.mg.add_causal_edge(self.summary.id, self.raw_2.id,
                                "derived_from", confidence=0.8)
        self.mg.add_causal_edge(self.report.id, self.summary.id,
                                "computed_from", confidence=1.0)
        self.mg.add_causal_edge(self.exec_sum.id, self.report.id,
                                "derived_from", confidence=0.7)

    def test_raw_1_reaches_summary(self):
        """raw_1 has summary_ab as a direct dependent."""
        result = self.mg.trace_derivation_impact(self.raw_1.id)
        assert result["node"] == self.raw_1.id
        assert self.summary.id in result["all_dependents"]
        # Chain continues: raw_1 → summary → report → exec_summary (depth 3)
        assert result["depth_reached"] == 3

    def test_multi_hop_chain(self):
        """raw_1 → summary_ab → report_top → exec_summary."""
        result = self.mg.trace_derivation_impact(self.raw_1.id)
        assert self.exec_sum.id in result["all_dependents"]
        assert self.report.id in result["all_dependents"]
        assert self.summary.id in result["all_dependents"]
        assert result["depth_reached"] == 3

    def test_leaves_identified(self):
        """exec_summary is a leaf (nothing derives from it)."""
        result = self.mg.trace_derivation_impact(self.raw_1.id)
        assert self.exec_sum.id in result["leaves"]

    def test_no_dependents(self):
        """A leaf node with nothing depending on it."""
        result = self.mg.trace_derivation_impact(self.exec_sum.id)
        assert result["all_dependents"] == []
        assert result["depth_reached"] == 0

    def test_orphan_node(self):
        """Node with no derivation edges at all."""
        result = self.mg.trace_derivation_impact(self.orphan.id)
        assert result["all_dependents"] == []
        assert self.orphan.id in result["leaves"]

    def test_nonexistent_node(self):
        result = self.mg.trace_derivation_impact("does_not_exist")
        assert result["error"] == "node not found"
        assert result["all_dependents"] == []
        assert result["depth_reached"] == 0


class TestTraceDerivationImpactChains:
    """Chain structure and ordering tests."""

    def setup_method(self):
        self.mg = MemoryGraph()
        self.raw_1 = self.mg.add("raw_1")
        self.raw_2 = self.mg.add("raw_2")
        self.summary = self.mg.add("summary_ab")
        self.report = self.mg.add("report_top")
        self.exec_sum = self.mg.add("exec_summary")

        self.mg.add_causal_edge(self.summary.id, self.raw_1.id,
                                "derived_from", confidence=0.9)
        self.mg.add_causal_edge(self.summary.id, self.raw_2.id,
                                "derived_from", confidence=0.8)
        self.mg.add_causal_edge(self.report.id, self.summary.id,
                                "computed_from", confidence=1.0)
        self.mg.add_causal_edge(self.exec_sum.id, self.report.id,
                                "derived_from", confidence=0.7)

    def test_chains_sorted_longest_first(self):
        """raw_2 → summary_ab → report_top → exec_summary (longest = 3)."""
        result = self.mg.trace_derivation_impact(self.raw_2.id)
        chains = result["chains"]
        assert len(chains[0]) == 3
        # Last edge source should be exec_summary
        last_edge = chains[0][-1]
        assert last_edge["source"] == self.exec_sum.id

    def test_chain_edge_fields(self):
        """Each chain edge has source, target, relation, confidence."""
        result = self.mg.trace_derivation_impact(self.raw_1.id)
        for chain in result["chains"]:
            for edge in chain:
                assert "source" in edge
                assert "target" in edge
                assert "relation" in edge
                assert "confidence" in edge

    def test_confidence_values_preserved(self):
        """Confidence from edge_props is carried through."""
        result = self.mg.trace_derivation_impact(self.raw_1.id)
        for chain in result["chains"]:
            first = chain[0]
            if first["target"] == self.raw_1.id and first["source"] == self.summary.id:
                assert abs(first["confidence"] - 0.9) < 1e-6
                break
        else:
            pytest.fail("Expected edge summary → raw_1 not found")

    def test_both_derived_and_computed_relations(self):
        """Both 'derived_from' and 'computed_from' edges are followed."""
        result = self.mg.trace_derivation_impact(self.raw_1.id)
        relations_seen = set()
        for chain in result["chains"]:
            for edge in chain:
                relations_seen.add(edge["relation"])
        assert "derived_from" in relations_seen
        assert "computed_from" in relations_seen


class TestTraceDerivationImpactDiamond:
    """Diamond dependency: D derived from B and C; B and C derived from A."""

    def setup_method(self):
        self.mg = MemoryGraph()
        self.A = self.mg.add("A")
        self.B = self.mg.add("B")
        self.C = self.mg.add("C")
        self.D = self.mg.add("D")
        # B derived_from A, C derived_from A
        self.mg.add_causal_edge(self.B.id, self.A.id, "derived_from", confidence=0.9)
        self.mg.add_causal_edge(self.C.id, self.A.id, "derived_from", confidence=0.8)
        # D derived_from B, D computed_from C
        self.mg.add_causal_edge(self.D.id, self.B.id, "derived_from", confidence=0.7)
        self.mg.add_causal_edge(self.D.id, self.C.id, "computed_from", confidence=1.0)

    def test_all_dependents_found(self):
        """Impact of A reaches B, C, and D."""
        result = self.mg.trace_derivation_impact(self.A.id)
        assert set(result["all_dependents"]) == {self.B.id, self.C.id, self.D.id}

    def test_diamond_produces_two_chains(self):
        """Two paths: A→B→D and A→C→D."""
        result = self.mg.trace_derivation_impact(self.A.id)
        chain_target_sets = set()
        for chain in result["chains"]:
            targets = tuple(e["source"] for e in chain)
            chain_target_sets.add(targets)
        # A→B→D and A→C→D
        assert (self.B.id, self.D.id) in chain_target_sets
        assert (self.C.id, self.D.id) in chain_target_sets

    def test_diamond_leaf_is_D(self):
        """D is a leaf (nothing depends on D)."""
        result = self.mg.trace_derivation_impact(self.A.id)
        assert self.D.id in result["leaves"]

    def test_diamond_depth(self):
        """Max depth is 2 (A→B→D or A→C→D)."""
        result = self.mg.trace_derivation_impact(self.A.id)
        assert result["depth_reached"] == 2


class TestTraceDerivationImpactCycle:
    """Cycle safety — derivation edges forming a loop."""

    def setup_method(self):
        self.mg = MemoryGraph()
        self.X = self.mg.add("X")
        self.Y = self.mg.add("Y")
        self.Z = self.mg.add("Z")
        # X derived_from Y, Y derived_from Z, Z derived_from X (cycle)
        self.mg.add_causal_edge(self.X.id, self.Y.id, "derived_from", confidence=0.5)
        self.mg.add_causal_edge(self.Y.id, self.Z.id, "derived_from", confidence=0.5)
        self.mg.add_causal_edge(self.Z.id, self.X.id, "derived_from", confidence=0.5)

    def test_cycle_does_not_infinite_loop(self):
        """Should terminate despite circular derivation edges."""
        result = self.mg.trace_derivation_impact(self.X.id)
        assert isinstance(result["all_dependents"], list)

    def test_cycle_nodes_appear_in_dependents(self):
        """Impact of Y: X derives from Y, Z derives from X, (Y from Z already visited)."""
        result = self.mg.trace_derivation_impact(self.Y.id)
        assert self.X.id in result["all_dependents"]
        assert self.Z.id in result["all_dependents"]


class TestTraceDerivationImpactMaxDepth:
    """max_depth cutoff tests."""

    def setup_method(self):
        self.mg = MemoryGraph()
        # Chain: E5 ← E4 ← E3 ← E2 ← E1 (E1 at root)
        self.nodes = []
        for i in range(5):
            self.nodes.append(self.mg.add(f"E{i+1}"))
        # E(i+1) derived_from E(i)
        for i in range(4):
            self.mg.add_causal_edge(self.nodes[i+1].id, self.nodes[i].id,
                                    "derived_from", confidence=0.9)

    def test_depth_limit_2(self):
        """Limit to 2 hops from E1: reaches E2, E3 only."""
        result = self.mg.trace_derivation_impact(self.nodes[0].id, max_depth=2)
        assert self.nodes[1].id in result["all_dependents"]  # E2
        assert self.nodes[2].id in result["all_dependents"]  # E3
        assert self.nodes[3].id not in result["all_dependents"]  # E4 not reached
        assert result["depth_reached"] == 2

    def test_depth_limit_1(self):
        """Only direct dependents."""
        result = self.mg.trace_derivation_impact(self.nodes[0].id, max_depth=1)
        assert result["all_dependents"] == [self.nodes[1].id]
        assert result["depth_reached"] == 1

    def test_depth_limit_0(self):
        """Zero depth = no traversal."""
        result = self.mg.trace_derivation_impact(self.nodes[0].id, max_depth=0)
        assert result["all_dependents"] == []
        assert result["depth_reached"] == 0

    def test_default_depth_reaches_all(self):
        """Default max_depth=10 reaches everything in a 4-deep chain."""
        result = self.mg.trace_derivation_impact(self.nodes[0].id)
        all_ids = {n.id for n in self.nodes[1:]}
        assert set(result["all_dependents"]) == all_ids
        assert result["depth_reached"] == 4


class TestTraceDerivationImpactEmpty:
    """Empty / minimal graph scenarios."""

    def test_single_node_no_edges(self):
        mg = MemoryGraph()
        solo = mg.add("solo")
        result = mg.trace_derivation_impact(solo.id)
        assert result["all_dependents"] == []
        assert solo.id in result["leaves"]
        assert result["depth_reached"] == 0

    def test_two_nodes_no_derivation_edge(self):
        mg = MemoryGraph()
        A = mg.add("A")
        B = mg.add("B")
        mg.link(A.id, B.id, "related_to")  # not a derivation edge
        result = mg.trace_derivation_impact(A.id)
        assert result["all_dependents"] == []

    def test_two_nodes_with_derivation_edge(self):
        mg = MemoryGraph()
        A = mg.add("A")
        B = mg.add("B")
        mg.add_causal_edge(B.id, A.id, "derived_from", confidence=1.0)
        result = mg.trace_derivation_impact(A.id)
        assert result["all_dependents"] == [B.id]
        assert result["depth_reached"] == 1


class TestTraceDerivationImpactVsBackward:
    """Verify forward impact and backward trace are complementary."""

    def setup_method(self):
        self.mg = MemoryGraph()
        self.root = self.mg.add("root")
        self.mid = self.mg.add("mid")
        self.leaf = self.mg.add("leaf")
        # mid derived_from root, leaf computed_from mid
        self.mg.add_causal_edge(self.mid.id, self.root.id,
                                "derived_from", confidence=0.9)
        self.mg.add_causal_edge(self.leaf.id, self.mid.id,
                                "computed_from", confidence=1.0)

    def test_backward_from_leaf_finds_root(self):
        """trace_derivation(leaf) → roots=[root]."""
        backward = self.mg.trace_derivation(self.leaf.id)
        assert self.root.id in backward["roots"]

    def test_forward_from_root_finds_leaf(self):
        """trace_derivation_impact(root) → dependents include mid, leaf."""
        forward = self.mg.trace_derivation_impact(self.root.id)
        assert set(forward["all_dependents"]) == {self.mid.id, self.leaf.id}

    def test_backward_roots_equal_forward_start(self):
        """The root found by backward trace from leaf == start of forward trace."""
        backward = self.mg.trace_derivation(self.leaf.id)
        forward = self.mg.trace_derivation_impact(backward["roots"][0])
        assert self.leaf.id in forward["all_dependents"]
