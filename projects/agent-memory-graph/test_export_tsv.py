"""Tests for export_tsv() / import_tsv() — Cycle 459."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from memory_graph import MemoryGraph


class TestExportTsv:
    """Cycle 459: TSV export/import for spreadsheet/R/pandas interop."""

    def _sample(self):
        mg = MemoryGraph()
        a = mg.add("Alice", kind="person")
        b = mg.add("Bob", kind="person")
        c = mg.add("ProjectX", kind="project")
        mg.add_tag(a.id, "engineer")
        mg.add_tag(a.id, "senior")
        mg.link(a.id, b.id, "colleague")
        mg.link(a.id, c.id, "works_on")
        mg.link(b.id, c.id, "works_on")
        return mg, a, b, c

    def test_export_returns_dict(self):
        mg, *_ = self._sample()
        r = mg.export_tsv()
        assert isinstance(r, dict)
        assert "nodes" in r
        assert "edges" in r

    def test_export_node_count(self):
        mg, *_ = self._sample()
        r = mg.export_tsv()
        assert r["node_count"] == 3

    def test_export_edge_count(self):
        mg, *_ = self._sample()
        r = mg.export_tsv()
        assert r["edge_count"] == 3

    def test_export_nodes_has_tab(self):
        mg, *_ = self._sample()
        r = mg.export_tsv()
        lines = r["nodes"].strip().split("\n")
        for line in lines:
            assert "\t" in line

    def test_export_edges_has_tab(self):
        mg, *_ = self._sample()
        r = mg.export_tsv()
        lines = r["edges"].strip().split("\n")
        for line in lines:
            assert "\t" in line

    def test_export_with_weights(self):
        mg, *_ = self._sample()
        r = mg.export_tsv(include_weights=True)
        lines = r["edges"].strip().split("\n")
        for line in lines:
            parts = line.split("\t")
            assert len(parts) >= 4  # src, tgt, rel, weight

    def test_export_without_weights(self):
        mg, *_ = self._sample()
        r = mg.export_tsv(include_weights=False)
        lines = r["edges"].strip().split("\n")
        for line in lines:
            parts = line.split("\t")
            assert len(parts) == 3  # src, tgt, rel

    def test_export_without_kinds(self):
        mg, *_ = self._sample()
        r = mg.export_tsv(include_kinds=False)
        lines = r["nodes"].strip().split("\n")
        for line in lines:
            parts = line.split("\t")
            assert len(parts) == 2  # id, label

    def test_export_with_tags(self):
        mg, a, *_ = self._sample()
        r = mg.export_tsv(include_tags=True)
        lines = r["nodes"].strip().split("\n")
        # Alice should have tags
        alice_line = [l for l in lines if a.id in l]
        assert len(alice_line) == 1
        assert "engineer" in alice_line[0]

    def test_export_empty_graph(self):
        mg = MemoryGraph()
        r = mg.export_tsv()
        assert r["node_count"] == 0
        assert r["edge_count"] == 0
        assert r["nodes"] == ""
        assert r["edges"] == ""

    def test_export_no_tags(self):
        mg, *_ = self._sample()
        r = mg.export_tsv(include_tags=False)
        lines = r["nodes"].strip().split("\n")
        for line in lines:
            parts = line.split("\t")
            assert len(parts) <= 3


class TestImportTsv:
    """Cycle 459: TSV import round-trip."""

    def test_import_basic(self):
        mg = MemoryGraph()
        nodes_tsv = "id\tlabel\tkind\nn1\tAlice\tperson\nn2\tBob\tperson"
        edges_tsv = "source\ttarget\trelation\nAlice\tBob\tcolleague"
        r = mg.import_tsv(nodes_tsv, edges_tsv)
        assert r["nodes_imported"] == 2
        assert r["edges_imported"] == 1

    def test_import_with_weights(self):
        mg = MemoryGraph()
        nodes_tsv = "id\tlabel\tkind\nn1\tA\tfact\nn2\tB\tfact"
        edges_tsv = "source\ttarget\trelation\tweight\nA\tB\trel\t2.5"
        r = mg.import_tsv(nodes_tsv, edges_tsv)
        assert r["edges_imported"] == 1

    def test_import_empty(self):
        mg = MemoryGraph()
        r = mg.import_tsv("", "")
        assert r["nodes_imported"] == 0
        assert r["edges_imported"] == 0

    def test_import_merge(self):
        mg = MemoryGraph()
        orig = mg.add("original")
        nodes_tsv = "id\tlabel\tkind\nn1\tnew_node\tfact"
        r = mg.import_tsv(nodes_tsv, "", merge=True)
        assert r["nodes_imported"] == 1
        # Original should still exist
        assert mg.has_node(orig.id)

    def test_import_clears_on_no_merge(self):
        mg = MemoryGraph()
        mg.add("original")
        nodes_tsv = "id\tlabel\tkind\nn1\tnew_node\tfact"
        mg.import_tsv(nodes_tsv, "", merge=False)
        assert not mg.has_node("original")

    def test_import_with_tags(self):
        mg = MemoryGraph()
        nodes_tsv = "id\tlabel\tkind\ttags\nn1\tAlice\tperson\tengineer,senior"
        r = mg.import_tsv(nodes_tsv)
        assert r["nodes_imported"] == 1

    def test_roundtrip_export_import(self):
        """Export then import produces equivalent structure."""
        mg = MemoryGraph()
        a = mg.add("Alice", kind="person")
        b = mg.add("Bob", kind="person")
        c = mg.add("ProjectX", kind="project")
        mg.link(a.id, b.id, "colleague")
        mg.link(a.id, c.id, "works_on")
        mg.link(b.id, c.id, "works_on")
        exported = mg.export_tsv(include_tags=False)

        mg2 = MemoryGraph()
        mg2.import_tsv(exported["nodes"], exported["edges"])

        # Same counts
        assert mg2.conn.execute("SELECT count(*) FROM nodes").fetchone()[0] == 3
        assert mg2.conn.execute("SELECT count(*) FROM edges").fetchone()[0] == 3

        # Same labels
        labels = {row['label'] for row in mg2.conn.execute("SELECT label FROM nodes").fetchall()}
        assert labels == {"Alice", "Bob", "ProjectX"}

    def test_import_skips_header(self):
        mg = MemoryGraph()
        nodes_tsv = "node_id\tlabel\nn1\ttest"
        r = mg.import_tsv(nodes_tsv)
        assert r["nodes_imported"] == 1
