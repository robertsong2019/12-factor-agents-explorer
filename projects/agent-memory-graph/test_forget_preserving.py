"""Cycle 450: forget_preserving() + batch_forget_preserving() —
forget nodes while auto-extracting atomic facts as residuals."""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def g():
    return MemoryGraph()


def _nc(g):
    return g.conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]


class TestForgetPreserving:
    """forget_preserving() — extract + safe_forget in one call."""

    def test_basic_forget_with_residuals(self, g):
        n = g.add("Alice met Bob on 2025-06-15 at New York University",
                  kind="event")
        r = g.forget_preserving(n.id)
        assert r["verdict"] == "deleted"
        assert r["preserved_count"] >= 1
        # Original node gone, residuals remain
        assert g.get_node(n.id) is None
        res_count = g.conn.execute(
            "SELECT COUNT(*) as c FROM nodes WHERE kind='residual'"
        ).fetchone()["c"]
        assert res_count >= 1

    def test_preserves_dates(self, g):
        n = g.add("Conference 2026-03-01 through 2026-03-03", kind="event")
        r = g.forget_preserving(n.id)
        facts = [f for res in r["residuals"]["residuals"] for f in res["facts"]]
        assert any("date:" in f for f in facts)

    def test_preserves_entities(self, g):
        n = g.add("John Smith visited Harvard University", kind="event")
        r = g.forget_preserving(n.id)
        facts = [f for res in r["residuals"]["residuals"] for f in res["facts"]]
        assert any("entity:" in f for f in facts)

    def test_no_extract_flag(self, g):
        n = g.add("2026-01-01 event", kind="event")
        r = g.forget_preserving(n.id, extract=False)
        assert r["verdict"] == "deleted"
        assert r["preserved_count"] == 0
        res_count = g.conn.execute(
            "SELECT COUNT(*) as c FROM nodes WHERE kind='residual'"
        ).fetchone()["c"]
        assert res_count == 0

    def test_nonexistent_node(self, g):
        r = g.forget_preserving("nonexistent-id")
        assert r["verdict"] == "not_found"
        assert r["preserved_count"] == 0

    def test_forget_result_included(self, g):
        n = g.add("Test 2026-01-01", kind="event")
        r = g.forget_preserving(n.id)
        assert "forget_result" in r
        assert "risk_level" in r["forget_result"]


class TestBatchForgetPreserving:
    """batch_forget_preserving() — extract all then forget all."""

    def test_batch_basic(self, g):
        ids = []
        for i in range(5):
            n = g.add(f"Event {i} on 2026-01-01", kind="event")
            ids.append(n.id)
        r = g.batch_forget_preserving(ids)
        assert r["total_deleted"] == 5
        assert r["total_blocked"] == 0
        assert r["total_preserved"] >= 1

    def test_batch_preserves_before_delete(self, g):
        n1 = g.add("Alice at 2026-03-15", kind="event")
        n2 = g.add("Bob at 2026-03-16", kind="event")
        before = _nc(g)
        r = g.batch_forget_preserving([n1.id, n2.id])
        # 2 original deleted, but residuals added
        assert r["total_preserved"] >= 1

    def test_batch_no_extract(self, g):
        ids = [g.add(f"Node {i} 2026-01-01", kind="event").id for i in range(3)]
        r = g.batch_forget_preserving(ids, extract=False)
        assert r["total_preserved"] == 0

    def test_batch_empty(self, g):
        r = g.batch_forget_preserving([])
        assert r["total_deleted"] == 0
        assert r["total_targeted"] == 0

    def test_batch_mixed_results(self, g):
        """Some deleted, some not found."""
        n1 = g.add("Valid node 2026-01-01", kind="event")
        r = g.batch_forget_preserving([n1.id, "ghost-id"])
        assert r["total_deleted"] == 1

    def test_results_list_length(self, g):
        ids = [g.add(f"N{i} 2026-01-01", kind="event").id for i in range(3)]
        r = g.batch_forget_preserving(ids)
        assert len(r["results"]) == 3


class TestIntegrationWithConsolidation:
    """Residual-preserving forget works in consolidation context."""

    def test_consolidate_then_forget_preserves(self, g):
        """Nodes created by consolidation can be forgotten with residuals."""
        # Create nodes that will merge
        g.add("Python programming language", kind="skill",
              data={"importance": 0.9})
        g.add("Python language basics", kind="skill",
              data={"importance": 0.85})
        g.add("Meeting 2026-03-15 at HQ", kind="event")
        # Consolidate (should merge the Python nodes)
        c = g.consolidate(force=True)
        # Forget the event node preserving its date
        event_nodes = [n for n in g.conn.execute(
            "SELECT id FROM nodes WHERE kind='event'").fetchall()]
        if event_nodes:
            r = g.forget_preserving(event_nodes[0]["id"])
            assert r["preserved_count"] >= 1
