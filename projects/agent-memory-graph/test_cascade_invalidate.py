"""Tests for invalidate_cascade() — PLACEMEM-inspired cascade invalidation.

When a node is invalidated, all nodes that depend on it (via depends_on,
enables edges) should also be invalidated.
"""
import pytest
from memory_graph import MemoryGraph


class TestInvalidateCascade:
    """Cascade invalidation via causal dependency edges."""

    def setup_method(self):
        self.mg = MemoryGraph()
        # Build a dependency chain: A --depends_on--> B --depends_on--> C
        self.a = self.mg.add("Feature A", category="feature")
        self.b = self.mg.add("Feature B", category="feature")
        self.c = self.mg.add("Feature C", category="feature")
        self.mg.link(self.a.id, self.b.id, "depends_on")
        self.mg.link(self.b.id, self.c.id, "depends_on")

    def test_basic_cascade_invalidates_dependents(self):
        """Invalidating C should cascade to B and A (reverse dependency)."""
        # Wait — depends_on means A depends on B, B depends on C.
        # If we invalidate C, then B (which depends on C) should be invalidated,
        # and A (which depends on B) should also be invalidated.
        result = self.mg.invalidate_cascade(self.c.id, reason="C is broken")

        assert result["root"] == self.c.id
        assert result["count"] == 3  # C, B, A
        assert self.c.id in result["cascaded"]
        assert self.b.id in result["cascaded"]
        assert self.a.id in result["cascaded"]

    def test_cascade_with_enables_relation(self):
        """enables edges should also trigger cascade."""
        mg = MemoryGraph()
        root = mg.add("Root Service")
        child = mg.add("Child Service")
        mg.link(root.id, child.id, "enables")

        result = mg.invalidate_cascade(root.id, reason="root down")
        assert result["count"] == 2
        assert root.id in result["cascaded"]
        assert child.id in result["cascaded"]

    def test_cascade_respects_max_depth(self):
        """max_depth should limit cascade propagation."""
        mg = MemoryGraph()
        nodes = [mg.add(f"N{i}") for i in range(5)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[i + 1].id, "depends_on")

        # max_depth=1: only root + immediate dependents
        result = mg.invalidate_cascade(nodes[4].id, max_depth=1)
        assert result["count"] == 2  # N4 + N3

    def test_cascade_cycle_safe(self):
        """Circular dependencies should not cause infinite loop."""
        mg = MemoryGraph()
        n1 = mg.add("Node 1")
        n2 = mg.add("Node 2")
        n3 = mg.add("Node 3")
        mg.link(n1.id, n2.id, "depends_on")
        mg.link(n2.id, n3.id, "depends_on")
        mg.link(n3.id, n1.id, "depends_on")  # cycle

        result = mg.invalidate_cascade(n1.id, reason="cycle test")
        assert result["count"] == 3

    def test_cascade_idempotent(self):
        """Invalidating an already-invalidated node should be safe."""
        result1 = self.mg.invalidate_cascade(self.c.id, reason="first")
        result2 = self.mg.invalidate_cascade(self.c.id, reason="second")

        # Both should succeed, same nodes
        assert result1["count"] == result2["count"]

    def test_cascade_custom_relations(self):
        """Custom cascade_relations should work."""
        mg = MemoryGraph()
        n1 = mg.add("Source")
        n2 = mg.add("Target")
        mg.link(n1.id, n2.id, "custom_dep")

        result = mg.invalidate_cascade(
            n1.id, cascade_relations=["custom_dep"]
        )
        assert n2.id in result["cascaded"]

    def test_cascade_default_relations_excludes_causes(self):
        """'causes' and 'prevents' should NOT cascade by default."""
        mg = MemoryGraph()
        n1 = mg.add("Event X")
        n2 = mg.add("Effect Y")
        mg.link(n1.id, n2.id, "causes")  # n1 causes n2

        result = mg.invalidate_cascade(n1.id)
        # n2 should NOT be cascaded because 'causes' is not in default cascade_relations
        assert n2.id not in result["cascaded"]

    def test_cascade_returns_reason(self):
        """Result should include the reason."""
        result = self.mg.invalidate_cascade(
            self.c.id, reason="deprecated API"
        )
        assert result["reason"] == "deprecated API"

    def test_cascade_root_not_found(self):
        """Should return error for non-existent root."""
        result = self.mg.invalidate_cascade("nonexistent")
        assert "error" in result
        assert result["count"] == 0

    def test_cascade_invalidated_by_recorded(self):
        """invalidated_by should be passed to node_invalidate."""
        mg = MemoryGraph()
        n1 = mg.add("Node")
        n2 = mg.add("Dependent")
        mg.link(n1.id, n2.id, "depends_on")

        self.mg.invalidate_cascade(n1.id, invalidated_by="agent_42")
        # Check that invalidated_by was recorded
        # node_invalidate stores it in _node_temporal
        node = mg.get_node(n1.id)
        data = node.data if isinstance(node.data, dict) else __import__("json").loads(node.data)
        temporal = data.get("_node_temporal", {})
        # Note: n1 was invalidated in self.mg, not mg. Let me test with mg.
        mg2 = MemoryGraph()
        a = mg2.add("A")
        b = mg2.add("B")
        mg2.link(a.id, b.id, "depends_on")
        mg2.invalidate_cascade(a.id, invalidated_by="test_agent")

        node_a = mg2.get_node(a.id)
        a_data = node_a.data if isinstance(node_a.data, dict) else __import__("json").loads(node_a.data)
        a_temporal = a_data.get("_node_temporal", {})
        assert a_temporal.get("invalidated_by") == "test_agent"

    def test_cascade_diamond_dependency(self):
        """Diamond: A→B, A→C, B→D, C→D — D should only be invalidated once."""
        mg = MemoryGraph()
        a = mg.add("A")
        b = mg.add("B")
        c = mg.add("C")
        d = mg.add("D")
        mg.link(a.id, b.id, "depends_on")
        mg.link(a.id, c.id, "depends_on")
        mg.link(b.id, d.id, "depends_on")
        mg.link(c.id, d.id, "depends_on")

        result = mg.invalidate_cascade(a.id)
        # A, B, C, D = 4 unique nodes (D appears once despite dual path)
        assert result["count"] == 4
        assert len(result["cascaded"]) == len(set(result["cascaded"]))

    def test_cascade_no_edges(self):
        """Isolated node should just invalidate itself."""
        mg = MemoryGraph()
        n = mg.add("Lonely")
        result = mg.invalidate_cascade(n.id)
        assert result["count"] == 1
        assert result["cascaded"] == [n.id]

    def test_cascade_empty_graph(self):
        """Empty graph with nonexistent root."""
        mg = MemoryGraph()
        result = mg.invalidate_cascade("ghost")
        assert result["count"] == 0
        assert "error" in result


class TestAddCategory:
    """Tests for the category parameter on add()."""

    def test_add_with_category(self):
        mg = MemoryGraph()
        node = mg.add("likes Python", kind="fact", category="preference")
        assert node is not None

    def test_add_category_stored(self):
        mg = MemoryGraph()
        mg.add("Always reply in Chinese", kind="fact", category="protocol")
        rows = mg.conn.execute("SELECT category FROM nodes").fetchall()
        assert rows[0]["category"] == "protocol"

    def test_add_without_category_defaults_null(self):
        mg = MemoryGraph()
        mg.add("some fact")
        rows = mg.conn.execute("SELECT category FROM nodes").fetchall()
        assert rows[0]["category"] is None

    def test_search_by_category(self):
        mg = MemoryGraph()
        n1 = mg.add("prefers dark mode", category="preference")
        n2 = mg.add("uses vim", category="preference")
        n3 = mg.add("Python 3.12 released", category="reference")

        prefs = mg.search_by_category("preference")
        assert len(prefs) == 2
        labels = {p.label for p in prefs}
        assert "prefers dark mode" in labels
        assert "uses vim" in labels

    def test_search_by_category_empty(self):
        mg = MemoryGraph()
        results = mg.search_by_category("nonexistent")
        assert results == []

    def test_search_by_category_excludes_quarantined(self):
        mg = MemoryGraph()
        n1 = mg.add("fact A", category="test_cat")
        mg.conn.execute("UPDATE nodes SET quarantined=1 WHERE id=?", (n1.id,))
        results = mg.search_by_category("test_cat")
        assert results == []

    def test_category_different_kinds(self):
        """Category and kind are orthogonal dimensions."""
        mg = MemoryGraph()
        mg.add("meeting notes", kind="event", category="episodic")
        mg.add("user name is Bob", kind="fact", category="episodic")
        results = mg.search_by_category("episodic")
        assert len(results) == 2
