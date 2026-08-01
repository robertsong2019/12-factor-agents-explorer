"""Tests for propagate_correction() — cascading correction propagation.

When a node's content is corrected, dependent nodes (connected via
depends_on / enables edges) should be marked for review, since they
may have been derived from the old content.

Unlike invalidate_cascade (which marks nodes invalid), propagate_correction
uses a softer 'needs_review' flag in the node's _correction metadata,
preserving the knowledge while signaling it needs re-evaluation.
"""
import pytest
from memory_graph import MemoryGraph


class TestPropagateCorrection:
    """Correction propagation via causal dependency edges."""

    def setup_method(self):
        self.mg = MemoryGraph()
        # A --depends_on--> B --depends_on--> C
        self.a = self.mg.add("Feature A", category="feature")
        self.b = self.mg.add("Feature B", category="feature")
        self.c = self.mg.add("Feature C", category="feature")
        self.mg.link(self.a.id, self.b.id, "depends_on")
        self.mg.link(self.b.id, self.c.id, "depends_on")

    # ── Basic propagation ────────────────────────────────

    def test_basic_propagation_marks_dependents(self):
        """Correcting C should mark B and A as needs_review."""
        result = self.mg.propagate_correction(self.c.id, reason="fixed typo in C")

        assert result["root"] == self.c.id
        assert result["count"] == 3  # C, B, A
        assert self.c.id in result["impacted"]
        assert self.b.id in result["impacted"]
        assert self.a.id in result["impacted"]

    def test_needs_review_flag_set_in_data(self):
        """Each impacted node should have _correction metadata."""
        self.mg.propagate_correction(self.c.id, reason="fix")

        b_data = self.mg.get_node(self.b.id).data
        if isinstance(b_data, str):
            import json
            b_data = json.loads(b_data)
        assert "_correction" in b_data
        assert b_data["_correction"]["status"] == "needs_review"
        assert b_data["_correction"]["source"] == self.c.id
        assert "reason" in b_data["_correction"]

    def test_correction_does_not_invalidate(self):
        """propagate_correction should NOT set valid_until (unlike invalidate_cascade)."""
        self.mg.propagate_correction(self.c.id, reason="fix")

        for nid in [self.a.id, self.b.id, self.c.id]:
            node = self.mg.get_node(nid)
            data = node.data if isinstance(node.data, dict) else json.loads(node.data)
            temporal = data.get("_node_temporal", {})
            assert temporal.get("valid_until") is None, \
                f"Node {nid} was invalidated, not just flagged"

    # ── Content update ───────────────────────────────────

    def test_new_content_updates_root_node(self):
        """If new_content is provided, root node label should be updated."""
        self.mg.propagate_correction(self.c.id, new_content="Feature C (corrected)",
                                      reason="typo fix")

        node = self.mg.get_node(self.c.id)
        assert "corrected" in node.label

    def test_no_new_content_keeps_original_label(self):
        """Without new_content, root label stays the same."""
        original_label = self.c.label
        self.mg.propagate_correction(self.c.id, reason="metadata fix")

        assert self.mg.get_node(self.c.id).label == original_label

    # ── Edge relations ───────────────────────────────────

    def test_enables_relation_triggers_propagation(self):
        """enables edges should also trigger propagation."""
        mg = MemoryGraph()
        root = mg.add("Root Service")
        child = mg.add("Child Service")
        mg.link(root.id, child.id, "enables")

        result = mg.propagate_correction(root.id, reason="root updated")
        assert result["count"] == 2
        assert root.id in result["impacted"]
        assert child.id in result["impacted"]

    def test_custom_impact_relations(self):
        """User should be able to specify custom relations to traverse."""
        mg = MemoryGraph()
        x = mg.add("Node X")
        y = mg.add("Node Y")
        mg.link(x.id, y.id, "derived_from")

        result = mg.propagate_correction(
            x.id, reason="recompute",
            impact_relations=["derived_from"]
        )
        assert y.id in result["impacted"]

    def test_unrelated_edges_not_traversed(self):
        """Edges not in impact_relations should be ignored."""
        mg = MemoryGraph()
        a = mg.add("A")
        b = mg.add("B")
        c = mg.add("C")
        mg.link(b.id, c.id, "depends_on")  # B depends_on C → B impacted
        mg.link(a.id, b.id, "related_to")  # not a causal edge → A NOT impacted

        result = mg.propagate_correction(c.id, reason="fix")
        assert c.id in result["impacted"]
        assert b.id in result["impacted"]
        assert a.id not in result["impacted"]  # related_to not traversed

    # ── Depth control ────────────────────────────────────

    def test_max_depth_limits_propagation(self):
        """max_depth should limit how far the correction propagates."""
        mg = MemoryGraph()
        nodes = [mg.add(f"N{i}") for i in range(5)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i + 1].id, "depends_on")

        # N4 is the root, N3 depends_on N4, N2 depends_on N3, etc.
        result = mg.propagate_correction(nodes[4].id, reason="fix", max_depth=1)
        assert result["count"] == 2  # N4 + N3 only
        assert nodes[3].id in result["impacted"]
        assert nodes[2].id not in result["impacted"]

    # ── Idempotency ──────────────────────────────────────

    def test_idempotent_re_marking(self):
        """Calling propagate_correction twice should not error."""
        self.mg.propagate_correction(self.c.id, reason="first fix")
        result2 = self.mg.propagate_correction(self.c.id, reason="second fix")

        assert result2["count"] == 3  # still works

    def test_correction_metadata_updates_on_re_mark(self):
        """Re-marking updates the reason and timestamp."""
        self.mg.propagate_correction(self.c.id, reason="first")
        import time
        time.sleep(0.01)
        self.mg.propagate_correction(self.c.id, reason="second")

        b_data = self.mg.get_node(self.b.id).data
        if isinstance(b_data, str):
            import json
            b_data = json.loads(b_data)
        assert b_data["_correction"]["reason"] == "second"

    # ── Cycle safety ─────────────────────────────────────

    def test_cycle_does_not_loop_infinitely(self):
        """Circular dependencies should not cause infinite loops."""
        mg = MemoryGraph()
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "depends_on")
        mg.link(b.id, a.id, "depends_on")  # cycle!

        result = mg.propagate_correction(a.id, reason="fix")
        assert a.id in result["impacted"]
        assert b.id in result["impacted"]
        assert result["count"] == 2  # not infinite

    # ── Edge cases ───────────────────────────────────────

    def test_nonexistent_root_returns_empty(self):
        """Non-existent root should return count=0."""
        result = self.mg.propagate_correction("nonexistent-id", reason="fix")
        assert result["count"] == 0
        assert result["impacted"] == []

    def test_no_dependents_only_marks_root(self):
        """A node with no dependents should only mark itself."""
        mg = MemoryGraph()
        lonely = mg.add("Lonely node")

        result = mg.propagate_correction(lonely.id, reason="fix")
        assert result["count"] == 1
        assert lonely.id in result["impacted"]

    def test_corrected_by_recorded(self):
        """corrected_by should be recorded in metadata."""
        self.mg.propagate_correction(self.c.id, reason="fix",
                                     corrected_by="agent-007")

        c_data = self.mg.get_node(self.c.id).data
        if isinstance(c_data, str):
            import json
            c_data = json.loads(c_data)
        assert c_data["_correction"]["corrected_by"] == "agent-007"

    def test_mark_status_customizable(self):
        """User should be able to customize the status mark."""
        self.mg.propagate_correction(self.c.id, reason="fix",
                                     mark_status="stale")

        b_data = self.mg.get_node(self.b.id).data
        if isinstance(b_data, str):
            import json
            b_data = json.loads(b_data)
        assert b_data["_correction"]["status"] == "stale"

    def test_corrected_at_timestamp_recorded(self):
        """Each impacted node should have a corrected_at timestamp."""
        self.mg.propagate_correction(self.c.id, reason="fix")

        b_data = self.mg.get_node(self.b.id).data
        if isinstance(b_data, str):
            import json
            b_data = json.loads(b_data)
        assert "corrected_at" in b_data["_correction"]
        assert isinstance(b_data["_correction"]["corrected_at"], float)

    def test_propagation_chain_depth_tracking(self):
        """Each node records how far it is from the correction root."""
        # A depends_on B depends_on C; correcting C
        self.mg.propagate_correction(self.c.id, reason="fix")

        for nid, expected_hops in [(self.c.id, 0), (self.b.id, 1), (self.a.id, 2)]:
            data = self.mg.get_node(nid).data
            if isinstance(data, str):
                import json
                data = json.loads(data)
            assert data["_correction"]["hops"] == expected_hops, \
                f"Node {nid} should be {expected_hops} hops from root"

    def test_return_structure_has_required_fields(self):
        """Result dict should have all expected fields."""
        result = self.mg.propagate_correction(self.c.id, reason="test")

        assert "root" in result
        assert "impacted" in result
        assert "count" in result
        assert "reason" in result
        assert "corrected_by" in result
        assert "depth_reached" in result

    # ── Mark vs Invalidate interplay ─────────────────────

    def test_already_invalidated_node_skipped(self):
        """If a node is already invalidated, it should be skipped."""
        self.mg.node_invalidate(self.b.id)
        result = self.mg.propagate_correction(self.c.id, reason="fix")

        # C gets marked, B is already invalidated (skipped), A still reachable via B's edges
        assert self.c.id in result["impacted"]
        # B should be in the skipped list, not impacted
        assert self.b.id not in result["impacted"]
        assert self.b.id in result.get("skipped", [])

    def test_mark_then_invalidate_works(self):
        """A node marked needs_review can still be invalidated later."""
        self.mg.propagate_correction(self.c.id, reason="fix")
        self.mg.node_invalidate(self.b.id)

        b_data = self.mg.get_node(self.b.id).data
        if isinstance(b_data, str):
            import json
            b_data = json.loads(b_data)
        # Both correction metadata AND invalidation should coexist
        assert "_correction" in b_data
        assert b_data.get("_node_temporal", {}).get("valid_until") is not None

    # ── Larger graph ─────────────────────────────────────

    def test_diamond_dependency(self):
        """Diamond: A->B->D, A->C->D. Correcting D should reach all."""
        mg = MemoryGraph()
        a = mg.add("A")
        b = mg.add("B")
        c = mg.add("C")
        d = mg.add("D")
        mg.link(a.id, b.id, "depends_on")
        mg.link(b.id, d.id, "depends_on")
        mg.link(a.id, c.id, "depends_on")
        mg.link(c.id, d.id, "depends_on")

        result = mg.propagate_correction(d.id, reason="fix")
        assert result["count"] == 4
        for n in [a, b, c, d]:
            assert n.id in result["impacted"]

    def test_branching_tree(self):
        """Tree: root has 3 children, each has 2 grandchildren."""
        mg = MemoryGraph()
        root = mg.add("Root")

        children = []
        grandchildren = []
        for i in range(3):
            child = mg.add(f"Child{i}")
            mg.link(child.id, root.id, "depends_on")
            children.append(child)
            for j in range(2):
                gc = mg.add(f"GC{i}-{j}")
                mg.link(gc.id, child.id, "depends_on")
                grandchildren.append(gc)

        result = mg.propagate_correction(root.id, reason="fix")
        # root + 3 children + 6 grandchildren = 10
        assert result["count"] == 10
