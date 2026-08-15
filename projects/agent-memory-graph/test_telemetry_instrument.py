"""
Tests for enable_telemetry() / disable_telemetry() / telemetry_status()
auto-instrumentation of MemoryGraph core methods.
"""

import pytest
from memory_graph import MemoryGraph


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def g():
    return MemoryGraph(":memory:")


@pytest.fixture
def populated(g):
    a = g.add("Alice", "person")
    b = g.add("Bob", "person")
    c = g.add("Carol", "person")
    g.link(a.id, b.id, "knows")
    g.link(b.id, c.id, "knows")
    g.link(a.id, c.id, "works_with")
    return g


# ── enable_telemetry ────────────────────────────────────────────────────

class TestEnableTelemetry:
    def test_returns_dict(self, g):
        result = g.enable_telemetry()
        assert isinstance(result, dict)

    def test_all_methods_instrumented_by_default(self, g):
        result = g.enable_telemetry()
        for method in ("add", "link", "get_node", "neighbors",
                       "recall", "search_unified", "delete_node"):
            assert result.get(method) == "instrumented", f"{method}: {result.get(method)}"

    def test_subset_wrap(self, g):
        result = g.enable_telemetry(wrap=["add", "recall"])
        assert result["add"] == "instrumented"
        assert result["recall"] == "instrumented"
        assert "get_node" not in result or result.get("get_node", "").startswith("skip")

    def test_unknown_method_skipped(self, g):
        result = g.enable_telemetry(wrap=["nonexistent"])
        assert result["nonexistent"].startswith("skipped")

    def test_idempotent_no_double_wrap(self, g):
        g.enable_telemetry()
        result2 = g.enable_telemetry()
        for method in ("add", "link", "get_node"):
            assert result2[method] == "skipped (already instrumented)"

    def test_wrapped_flag_set(self, g):
        g.enable_telemetry()
        assert getattr(g.add, "_amg_telemetry_wrapped", False) is True
        assert getattr(g.recall, "_amg_telemetry_wrapped", False) is True

    def test_original_preserved(self, g):
        g.enable_telemetry()
        assert hasattr(g.add, "_amg_telemetry_original")

    def test_custom_store_name(self, g):
        g.enable_telemetry(store="my_store")
        status = g.telemetry_status()
        assert status["store"] == "my_store"


# ── Functionality preserved after wrapping ──────────────────────────────

class TestFunctionalityPreserved:
    def test_add_works(self, g):
        g.enable_telemetry()
        node = g.add("test", "fact", {"key": "value"})
        assert node.label == "test"
        assert node.kind == "fact"

    def test_get_node_works(self, g):
        g.enable_telemetry()
        node = g.add("test", "fact")
        retrieved = g.get_node(node.id)
        assert retrieved is not None
        assert retrieved.id == node.id

    def test_recall_works(self, g):
        g.enable_telemetry()
        g.add("quantum computing", "concept")
        results = g.recall("quantum")
        assert len(results) > 0

    def test_search_unified_works(self, g):
        g.enable_telemetry()
        g.add("machine learning", "concept")
        results = g.search_unified("machine")
        assert len(results) > 0

    def test_link_works(self, g):
        g.enable_telemetry()
        a = g.add("X", "concept")
        b = g.add("Y", "concept")
        g.link(a.id, b.id, "relates_to")
        nbrs = g.neighbors(a.id)
        assert any(n.id == b.id for n in nbrs)

    def test_neighbors_works(self, populated):
        populated.enable_telemetry()
        a = populated.add("Alice", "person")
        b = populated.add("Bob", "person")
        populated.link(a.id, b.id, "knows")
        nbrs = populated.neighbors(a.id)
        assert any(n.id == b.id for n in nbrs)

    def test_search_graphrag_works(self, populated):
        populated.enable_telemetry()
        results = populated.search_graphrag("Alice", mode="local", limit=3)
        assert isinstance(results, list)  # wrapped call must not crash

    def test_delete_node_works(self, g):
        g.enable_telemetry()
        node = g.add("temp", "fact")
        result = g.delete_node(node.id)
        assert result is True or result is None  # just verify no crash


# ── disable_telemetry ───────────────────────────────────────────────────

class TestDisableTelemetry:
    def test_disables_all(self, g):
        g.enable_telemetry()
        result = g.disable_telemetry()
        for method in ("add", "link", "get_node", "neighbors",
                       "recall", "search_unified", "delete_node"):
            assert result[method] == "restored"

    def test_unwrapped_flag_cleared(self, g):
        g.enable_telemetry()
        g.disable_telemetry()
        assert not getattr(g.add, "_amg_telemetry_wrapped", False)

    def test_disable_without_enable(self, g):
        result = g.disable_telemetry()
        for method in ("add", "link", "get_node"):
            assert result[method] == "skipped (not instrumented)"

    def test_re_enable_after_disable(self, g):
        g.enable_telemetry()
        g.disable_telemetry()
        result = g.enable_telemetry()
        assert result["add"] == "instrumented"

    def test_functionality_after_disable(self, g):
        g.enable_telemetry()
        g.disable_telemetry()
        node = g.add("test", "fact")
        assert node.label == "test"


# ── telemetry_status ────────────────────────────────────────────────────

class TestTelemetryStatus:
    def test_status_before_enable(self, g):
        status = g.telemetry_status()
        assert "instrumented" in status
        assert "not_instrumented" in status
        assert len(status["instrumented"]) == 0
        assert len(status["not_instrumented"]) > 0

    def test_status_after_enable(self, g):
        g.enable_telemetry()
        status = g.telemetry_status()
        assert len(status["instrumented"]) == 8
        assert len(status["not_instrumented"]) == 0

    def test_status_after_enable_seven_methods(self, g):
        # search variants might not exist on all variants
        g.enable_telemetry(wrap=[
            "add", "link", "get_node", "neighbors",
            "recall", "search_unified", "delete_node",
        ])
        status = g.telemetry_status()
        assert len(status["instrumented"]) >= 7

    def test_status_after_partial_enable(self, g):
        g.enable_telemetry(wrap=["add", "recall"])
        status = g.telemetry_status()
        assert "add" in status["instrumented"]
        assert "recall" in status["instrumented"]
        assert "get_node" in status["not_instrumented"]

    def test_status_after_disable(self, g):
        g.enable_telemetry()
        g.disable_telemetry()
        status = g.telemetry_status()
        assert len(status["instrumented"]) == 0

    def test_otel_available_field(self, g):
        status = g.telemetry_status()
        assert "otel_available" in status
        assert isinstance(status["otel_available"], bool)

    def test_store_field_none_before_enable(self, g):
        status = g.telemetry_status()
        assert status["store"] is None

    def test_store_field_set_after_enable(self, g):
        g.enable_telemetry(store="prod")
        status = g.telemetry_status()
        assert status["store"] == "prod"


# ── Inert mode (no opentelemetry installed) ─────────────────────────────

class TestInertMode:
    def test_wrapped_method_does_not_crash_without_otel(self, g):
        """Even without opentelemetry installed, wrapped methods should work."""
        g.enable_telemetry()
        # This should not raise even if OTel is not installed
        node = g.add("inert_test", "fact")
        assert node is not None
        retrieved = g.get_node(node.id)
        assert retrieved is not None

    def test_multiple_operations_in_inert_mode(self, g):
        g.enable_telemetry()
        a = g.add("A", "concept")
        b = g.add("B", "concept")
        g.link(a.id, b.id, "connects")
        results = g.recall("A")
        assert len(results) > 0
        nbrs = g.neighbors(a.id)
        assert len(nbrs) > 0
        # All worked without OTel


# ── Edge cases ──────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_enable_with_empty_wrap_list(self, g):
        result = g.enable_telemetry(wrap=[])
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_enable_telemetry_on_subclass(self):
        """Subclasses of MemoryGraph inherit instrumentation too."""
        class MyGraph(MemoryGraph):
            pass
        sg = MyGraph(":memory:")
        result = sg.enable_telemetry()
        assert "add" in result
        sg.disable_telemetry()

    def test_store_attribute_persists(self, g):
        g.enable_telemetry(store="custom_store")
        assert g._telemetry_store == "custom_store"

    def test_concurrent_enable_disable(self, g):
        """Rapid enable/disable cycle should be stable."""
        for _ in range(3):
            g.enable_telemetry()
            g.disable_telemetry()
        status = g.telemetry_status()
        assert len(status["instrumented"]) == 0
