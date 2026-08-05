"""Tests for expanded CODE_EDGE_KINDS (Cycle 360, Research #044)."""

import pytest
from memory_graph import MemoryGraph


class TestExpandedCodeEdgeKinds:
    """CODE_EDGE_KINDS now includes OOP and structural relations."""

    def test_inherits_in_edge_kinds(self):
        assert "inherits" in MemoryGraph.CODE_EDGE_KINDS

    def test_implements_in_edge_kinds(self):
        assert "implements" in MemoryGraph.CODE_EDGE_KINDS

    def test_references_in_edge_kinds(self):
        assert "references" in MemoryGraph.CODE_EDGE_KINDS

    def test_contains_in_edge_kinds(self):
        assert "contains" in MemoryGraph.CODE_EDGE_KINDS

    def test_overrides_in_edge_kinds(self):
        assert "overrides" in MemoryGraph.CODE_EDGE_KINDS

    def test_decorates_in_edge_kinds(self):
        assert "decorates" in MemoryGraph.CODE_EDGE_KINDS

    def test_type_of_in_edge_kinds(self):
        assert "type_of" in MemoryGraph.CODE_EDGE_KINDS

    def test_total_count(self):
        assert len(MemoryGraph.CODE_EDGE_KINDS) == 14

    def test_original_kinds_preserved(self):
        for kind in ("calls", "imports", "defined_in", "depends_on",
                     "decided_by", "fixed_by", "tested_by"):
            assert kind in MemoryGraph.CODE_EDGE_KINDS

    def test_code_edge_audit_uses_edge_kinds(self):
        """code_edge_audit should recognize all CODE_EDGE_KINDS."""
        g = MemoryGraph()
        # Verify all edge kinds can be created without error
        fn = g.add_code_node("fn", "function")
        dep = g.add_code_node("dep", "function")
        for kind in MemoryGraph.CODE_EDGE_KINDS:
            g.link(fn.id, dep.id, kind)


class TestCodeEdgesFunctional:
    """Functional tests for new edge kinds."""

    def test_inherits_edge(self):
        g = MemoryGraph()
        parent = g.add_code_node("BaseService", "class")
        child = g.add_code_node("UserService", "class")
        g.link(child.id, parent.id, "inherits")
        # Verify edge exists (explain_code callees only tracks 'calls' edges)
        edges = g.edges_of(child.id)
        inherits_edges = [e for e in edges if e.relation == "inherits"]
        assert len(inherits_edges) == 1
        assert inherits_edges[0].target == parent.id

    def test_contains_edge(self):
        g = MemoryGraph()
        module = g.add_code_node("auth", "module")
        fn = g.add_code_node("login", "function")
        g.link(module.id, fn.id, "contains")
        edges = g.edges_of(module.id)
        contains_edges = [e for e in edges if e.relation == "contains"]
        assert len(contains_edges) == 1

    def test_references_edge(self):
        g = MemoryGraph()
        a = g.add_code_node("A", "function")
        b = g.add_code_node("B", "variable")
        g.link(a.id, b.id, "references")
        edges = g.edges_of(a.id)
        ref_edges = [e for e in edges if e.relation == "references"]
        assert len(ref_edges) == 1

    def test_overrides_edge(self):
        g = MemoryGraph()
        parent = g.add_code_node("Base.render", "method")
        child = g.add_code_node("Child.render", "method")
        g.link(child.id, parent.id, "overrides")
        edges = g.edges_of(child.id)
        override_edges = [e for e in edges if e.relation == "overrides"]
        assert len(override_edges) == 1

    def test_implements_edge(self):
        g = MemoryGraph()
        iface = g.add_code_node("Serializable", "class")
        cls = g.add_code_node("User", "class")
        g.link(cls.id, iface.id, "implements")
        edges = g.edges_of(cls.id)
        impl_edges = [e for e in edges if e.relation == "implements"]
        assert len(impl_edges) == 1

    def test_decorates_edge(self):
        g = MemoryGraph()
        decorator = g.add_code_node("cached", "function")
        fn = g.add_code_node("getData", "function")
        g.link(fn.id, decorator.id, "decorates")
        edges = g.edges_of(fn.id)
        dec_edges = [e for e in edges if e.relation == "decorates"]
        assert len(dec_edges) == 1

    def test_type_of_edge(self):
        g = MemoryGraph()
        alias = g.add_code_node("UserID", "variable")
        primitive = g.add_code_node("string", "variable")
        g.link(alias.id, primitive.id, "type_of")
        edges = g.edges_of(alias.id)
        type_edges = [e for e in edges if e.relation == "type_of"]
        assert len(type_edges) == 1

    def test_multiple_edge_kinds_between_graphs(self):
        """All 14 edge kinds create valid edges in graph."""
        g = MemoryGraph()
        node = g.add_code_node("target", "function")
        for kind in MemoryGraph.CODE_EDGE_KINDS:
            dep = g.add_code_node(f"dep_{kind}", "function")
            g.link(dep.id, node.id, kind)
        # Verify all 14 edges exist
        incoming = g.edges_of(node.id)
        assert len(incoming) == 14
