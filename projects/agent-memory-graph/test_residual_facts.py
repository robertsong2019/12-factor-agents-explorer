"""Cycle 449: Compression residuals — atomic fact extraction to prevent
summary loss during consolidation (Research #045, ProGraph pattern).

Tests extract_residuals(), residual_report(), consolidate_with_residuals().
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def g():
    return MemoryGraph()


def _nc(g):
    return g.conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]


class TestExtractResiduals:
    """extract_residuals() — pattern-based atomic fact extraction."""

    def test_date_extraction_iso(self, g):
        g.add("Meeting on 2026-08-16", kind="event")
        r = g.extract_residuals(dry_run=True)
        assert r["unique_facts"] >= 1
        assert any("date:2026-08-16" in f
                   for res in r["residuals"] for f in res["facts"])

    def test_date_extraction_written(self, g):
        g.add("Started on March 15, 2025", kind="event")
        r = g.extract_residuals(dry_run=True)
        assert r["unique_facts"] >= 1
        assert any("date:March 15, 2025" in f
                   for res in r["residuals"] for f in res["facts"])

    def test_date_extraction_slash(self, g):
        g.add("Deadline 12/31/2026", kind="event")
        r = g.extract_residuals(dry_run=True)
        assert r["unique_facts"] >= 1

    def test_quantity_extraction(self, g):
        g.add("Budget is $5000 for 3.5kg of material", kind="fact")
        r = g.extract_residuals(dry_run=True)
        assert r["unique_facts"] >= 1
        facts_flat = [f for res in r["residuals"] for f in res["facts"]]
        assert any("qty:" in f for f in facts_flat)

    def test_entity_extraction(self, g):
        g.add("Alice Johnson met Bob Smith at New York University", kind="event")
        r = g.extract_residuals(dry_run=True)
        facts_flat = [f for res in r["residuals"] for f in res["facts"]]
        entity_facts = [f for f in facts_flat if f.startswith("entity:")]
        assert len(entity_facts) >= 1

    def test_temporal_extraction(self, g):
        g.add("Completed yesterday after 2 weeks of work", kind="event")
        r = g.extract_residuals(dry_run=True)
        facts_flat = [f for res in r["residuals"] for f in res["facts"]]
        assert any(f.startswith("temporal:") for f in facts_flat)

    def test_dry_run_creates_no_nodes(self, g):
        g.add("Release v1.0 on 2026-01-01", kind="event")
        before = _nc(g)
        g.extract_residuals(dry_run=True)
        assert _nc(g) == before

    def test_wet_run_creates_residual_nodes(self, g):
        g.add("Release v1.0 on 2026-01-01", kind="event")
        g.extract_residuals(dry_run=False)
        assert _nc(g) >= 2
        res = g.conn.execute("SELECT COUNT(*) as c FROM nodes WHERE kind='residual'").fetchone()["c"]
        assert res == 1

    def test_residual_links_to_source(self, g):
        n = g.add("Alice went to Paris on 2025-06-15", kind="event")
        g.extract_residuals(dry_run=False)
        edges = g.conn.execute(
            "SELECT source, target FROM edges WHERE relation='has_residual'"
        ).fetchall()
        assert len(edges) == 1
        assert n.id in (edges[0]["source"], edges[0]["target"])

    def test_kinds_filter(self, g):
        g.add("2026-08-16 meeting", kind="event")
        g.add("Random note", kind="note")
        r = g.extract_residuals(dry_run=True, kinds=("event",))
        assert r["nodes_scanned"] == 1

    def test_node_ids_filter(self, g):
        n1 = g.add("2026-01-01", kind="event")
        g.add("2026-12-31", kind="event")
        r = g.extract_residuals(dry_run=True, node_ids=[n1.id])
        assert r["nodes_scanned"] == 1
        assert r["residuals"][0]["source_node"] == n1.id

    def test_empty_graph(self, g):
        r = g.extract_residuals(dry_run=True)
        assert r["nodes_scanned"] == 0
        assert r["unique_facts"] == 0

    def test_dedup_across_nodes(self, g):
        g.add("2026-08-16 meeting A", kind="event")
        g.add("2026-08-16 meeting B", kind="event")
        r = g.extract_residuals(dry_run=True)
        date_count = sum(1 for res in r["residuals"]
                        for f in res["facts"]
                        if "date:2026-08-16" in f)
        assert date_count == 1

    def test_nodes_scanned_count(self, g):
        for i in range(5):
            g.add(f"Node {i} on 2026-01-01", kind="event")
        r = g.extract_residuals(dry_run=True)
        assert r["nodes_scanned"] == 5

    def test_no_facts_no_residuals(self, g):
        g.add("just some plain text here", kind="fact")
        r = g.extract_residuals(dry_run=True)
        assert r["unique_facts"] == 0
        assert r["residuals"] == []


class TestResidualReport:
    def test_empty_graph(self, g):
        r = g.residual_report()
        assert r["count"] == 0

    def test_with_residuals(self, g):
        g.add("2026-08-16 event", kind="event")
        g.extract_residuals(dry_run=False)
        r = g.residual_report()
        assert r["count"] == 1
        assert r["avg_facts"] >= 1.0

    def test_source_coverage(self, g):
        g.add("2026-01-01 meeting", kind="event")
        g.add("plain text", kind="note")
        g.extract_residuals(dry_run=False)
        r = g.residual_report()
        assert r["source_coverage"] > 0


class TestConsolidateWithResiduals:
    def test_returns_both_sections(self, g):
        for i in range(15):
            g.add(f"Node {i} 2026-01-01", kind="fact")
        r = g.consolidate_with_residuals(force=True)
        assert "consolidation" in r
        assert "residuals" in r

    def test_residuals_preserve_facts(self, g):
        g.add("Alice arrived 2025-03-15", kind="event")
        g.add("Alice departed 2025-06-20", kind="event")
        r = g.consolidate_with_residuals(force=True, dry_run=True)
        assert r["residuals"]["unique_facts"] >= 1

    def test_dry_run_no_mutations(self, g):
        for i in range(10):
            g.add(f"Test {i} on 2026-01-01", kind="event")
        before_n = _nc(g)
        before_e = g.conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"]
        g.consolidate_with_residuals(force=True, dry_run=True, extract_kwargs={"dry_run": True})
        assert _nc(g) == before_n
        assert g.conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"] == before_e


class TestPatternCorrectness:
    def test_percentage_as_quantity(self, g):
        g.add("Accuracy reached 95.7%", kind="fact")
        r = g.extract_residuals(dry_run=True)
        facts_flat = [f for res in r["residuals"] for f in res["facts"]]
        assert any("qty:95.7%" in f for f in facts_flat)

    def test_currency_quantity(self, g):
        g.add("Budget is 5000 USD for project", kind="fact")
        r = g.extract_residuals(dry_run=True)
        facts_flat = [f for res in r["residuals"] for f in res["facts"]]
        assert any("qty:5000" in f for f in facts_flat)

    def test_time_units(self, g):
        g.add("Latency 42ms response time", kind="fact")
        r = g.extract_residuals(dry_run=True)
        facts_flat = [f for res in r["residuals"] for f in res["facts"]]
        assert any("qty:" in f for f in facts_flat)

    def test_single_capital_word_not_entity(self, g):
        g.add("Alice visited the park", kind="event")
        r = g.extract_residuals(dry_run=True)
        facts_flat = [f for res in r["residuals"] for f in res["facts"]]
        entity_facts = [f for f in facts_flat if f.startswith("entity:")]
        assert len(entity_facts) == 0

    def test_two_word_entity_captured(self, g):
        g.add("Alice Johnson arrived", kind="event")
        r = g.extract_residuals(dry_run=True)
        facts_flat = [f for res in r["residuals"] for f in res["facts"]]
        entity_facts = [f for f in facts_flat if f.startswith("entity:")]
        assert any("Alice Johnson" in f for f in entity_facts)
