"""Tests for export_graphml() — Cycle 438, Research #064 Gap #3.

GraphRAG-Bench (ICLR 2026) indexing_eval consumes generic GraphML via
``--framework graphml``; export_graphml() is the file-writing adapter
on top of serialize_graphml().
"""
import os
import xml.etree.ElementTree as ET

import pytest

import memory_graph as mg
from memory_graph import MemoryGraph

try:
    import networkx  # noqa: F401
    HAS_NX = True
except ImportError:
    HAS_NX = False


def _build_graph():
    g = MemoryGraph()
    a = g.add("Mont St. Michel", kind="place")
    b = g.add("Normandy", kind="region")
    c = g.add("France", kind="country")
    g.link(a.id, b.id, "located_in", weight=2.5)
    g.link(b.id, c.id, "part_of")
    return g, a, b, c


class TestExportGraphmlBasic:

    def test_writes_valid_xml_file(self, tmp_path):
        g, *_ = _build_graph()
        p = tmp_path / "kg.graphml"
        result = g.export_graphml(p)
        assert result["written"] is True
        assert os.path.exists(p)
        ET.fromstring(p.read_text(encoding="utf-8"))  # parses => valid XML

    def test_summary_counts_match_graph(self, tmp_path):
        g, *_ = _build_graph()
        result = g.export_graphml(tmp_path / "kg.graphml")
        assert result["nodes"] == 3
        assert result["edges"] == 2
        assert result["path"] == str(tmp_path / "kg.graphml")

    def test_bytes_matches_file_size(self, tmp_path):
        g, *_ = _build_graph()
        p = tmp_path / "kg.graphml"
        result = g.export_graphml(p)
        assert result["bytes"] == os.path.getsize(p)

    def test_directed_graph_element(self, tmp_path):
        g, *_ = _build_graph()
        p = tmp_path / "kg.graphml"
        g.export_graphml(p)
        root = ET.fromstring(p.read_text(encoding="utf-8"))
        ns = "{http://graphml.graphdrawing.org/xmlns}"
        graph = root.find(f"{ns}graph")
        assert graph is not None
        assert graph.get("edgedefault") == "directed"

    def test_empty_graph_export(self, tmp_path):
        g = MemoryGraph()
        result = g.export_graphml(tmp_path / "empty.graphml")
        assert result["written"] is True
        assert result["nodes"] == 0 and result["edges"] == 0
        root = ET.fromstring(
            (tmp_path / "empty.graphml").read_text(encoding="utf-8"))
        ns = "{http://graphml.graphdrawing.org/xmlns}"
        assert len(root.find(f"{ns}graph").findall(f"{ns}node")) == 0


class TestExportGraphmlSafety:

    def test_refuses_overwrite_by_default(self, tmp_path):
        g, *_ = _build_graph()
        p = tmp_path / "kg.graphml"
        g.export_graphml(p)
        before = p.read_text(encoding="utf-8")
        result = g.export_graphml(p)  # second call, no overwrite
        assert result["written"] is False
        assert "overwrite" in result["reason"]
        assert p.read_text(encoding="utf-8") == before  # untouched

    def test_overwrite_true_rewrites(self, tmp_path):
        g, *_ = _build_graph()
        p = tmp_path / "kg.graphml"
        g.export_graphml(p)
        g.add("Extra Node")
        result = g.export_graphml(p, overwrite=True)
        assert result["written"] is True
        assert result["nodes"] == 4
        assert "Extra Node" in p.read_text(encoding="utf-8")

    def test_accepts_str_and_pathlib(self, tmp_path):
        g, *_ = _build_graph()
        assert g.export_graphml(tmp_path / "a.graphml")["written"]
        assert g.export_graphml(str(tmp_path / "b.graphml"))["written"]


class TestExportGraphmlRoundtrip:

    def test_import_graphml_roundtrip(self, tmp_path):
        g, a, b, c = _build_graph()
        p = tmp_path / "kg.graphml"
        g.export_graphml(p)
        g2 = MemoryGraph()
        stats = g2.import_graphml(p.read_text(encoding="utf-8"))
        assert stats["nodes"] == 3
        assert stats["edges"] == 2
        assert g2.edge_count() == 2

    def test_special_characters_survive_roundtrip(self, tmp_path):
        g = MemoryGraph()
        n = g.add('Quotes " & <angles> & ampersand', kind="fact")
        p = tmp_path / "weird.graphml"
        g.export_graphml(p)
        g2 = MemoryGraph()
        g2.import_graphml(p.read_text(encoding="utf-8"))
        row = g2.conn.execute(
            "SELECT label FROM nodes LIMIT 1").fetchone()
        assert row["label"] == 'Quotes " & <angles> & ampersand'

    @pytest.mark.skipif(not HAS_NX, reason="networkx not installed")
    def test_networkx_loads_export(self, tmp_path):
        """The path GraphRAG-Bench indexing_eval takes: read_graphml."""
        import networkx as nx
        g, a, b, c = _build_graph()
        p = tmp_path / "kg.graphml"
        g.export_graphml(p)
        loaded = nx.read_graphml(p)
        assert loaded.number_of_nodes() == 3
        assert loaded.number_of_edges() == 2
        # attributes survive: relation + weights
        (u, v, data) = list(loaded.edges(data=True))[0]
        assert data["relation"] in ("located_in", "part_of")
        node_attrs = loaded.nodes[a.id]
        assert node_attrs["label"] == "Mont St. Michel"


class TestExportGraphmlGraphRagPipeline:
    """E2E: extract_from_text → export_graphml → networkx — the exact
    chain the GraphRAG-Bench adapter (run_amg.py, Gap #4) will use."""

    @pytest.mark.skipif(not HAS_NX, reason="networkx not installed")
    def test_extract_then_export_then_networkx(self, tmp_path):
        import networkx as nx
        g = MemoryGraph()
        r = g.extract_from_text(
            "Alice works at Acme. Acme is located in Paris.")
        p = tmp_path / "bench.graphml"
        result = g.export_graphml(p)
        assert result["nodes"] == len(r["entities"])
        assert result["edges"] == len(r["relations"])
        loaded = nx.read_graphml(p)
        assert loaded.number_of_nodes() == 3
        assert loaded.number_of_edges() == 2
        labels = {d["label"] for _, d in loaded.nodes(data=True)}
        assert labels == {"Alice", "Acme", "Paris"}
        rels = {d["relation"] for _, _, d in loaded.edges(data=True)}
        assert rels == {"works_at", "located_in"}
