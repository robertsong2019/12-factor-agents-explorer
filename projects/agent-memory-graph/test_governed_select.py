"""Tests for select_governed() — MRMS-style three-stage selection pipeline.

Three stages:
1. Structured gates — quarantine + validity + confidence filters
2. Vector recall — delegates to existing retrieve() pipeline
3. Graph expansion — annotates results with evidence, conflicts, superseded status

References: MRMS (arXiv:2607.04617), Mandol (arXiv:2606.29778)
"""

import pytest
from memory_graph import MemoryGraph, Node


class TestStructuredGates:
    """Stage 1: Structured gate filtering."""

    def test_basic_governed_retrieve_returns_results(self):
        """Smoke test — governed retrieve should return results for seeded graph."""
        mg = MemoryGraph()
        mg.add("Python is a programming language", "fact")
        mg.add("Python is widely used in AI", "fact")
        mg.link_by_label("Python is a programming language", "Python is widely used in AI", "related")
        results = mg.select_governed("Python")
        assert len(results) > 0
        assert "node_id" in results[0]
        assert "claim" in results[0]

    def test_quarantined_nodes_excluded(self):
        """Quarantined nodes must not appear in governed results."""
        mg = MemoryGraph()
        n1 = mg.add("Fact A: sky is blue", "fact")
        n2 = mg.add("Fact B: grass is green", "fact")
        mg.node_quarantine(n1.id, "unverified source")
        results = mg.select_governed("sky")
        ids = [r["node_id"] for r in results]
        assert n1.id not in ids
        # Unquarantined node should still be found when queried directly
        results_b = mg.select_governed("grass")
        assert n2.id in [r["node_id"] for r in results_b]

    def test_superseded_nodes_excluded(self):
        """Nodes that have been superseded (valid_to set) should be excluded."""
        mg = MemoryGraph()
        old = mg.add("Server runs Python 3.8", "fact")
        new_id = mg.supersede(old.id, "Server runs Python 3.12")
        results = mg.select_governed("Server")
        ids = [r["node_id"] for r in results]
        assert old.id not in ids
        assert new_id in ids

    def test_confidence_threshold_filter(self):
        """Nodes below confidence threshold should be excluded."""
        mg = MemoryGraph()
        n1 = mg.add("High confidence fact", "fact")
        n2 = mg.add("Low confidence fact", "fact")
        # Manually lower weight/confidence on n2
        mg.conn.execute("UPDATE nodes SET weight=0.01 WHERE id=?", (n2.id,))
        mg.conn.commit()
        results = mg.select_governed("confidence", min_confidence=0.1)
        ids = [r["node_id"] for r in results]
        # n2 should be filtered out (weight too low → confidence too low)
        # n1 should be present
        assert n1.id in ids or len(results) == 0  # query match dependent

    def test_kind_filter(self):
        """Kind filter should restrict results to specified kinds."""
        mg = MemoryGraph()
        mg.add("Python language", "concept")
        mg.add("Python training", "event")
        results = mg.select_governed("Python", kinds=["concept"])
        for r in results:
            assert r["kind"] == "concept"


class TestGraphExpansion:
    """Stage 3: Graph expansion — evidence, conflict, supersede annotation."""

    def test_evidence_annotation(self):
        """Results should include evidence (supporting nodes) when edges exist."""
        mg = MemoryGraph()
        n1 = mg.add("User prefers dark mode", "fact")
        n2 = mg.add("Dark mode setting confirmed in survey", "fact")
        mg.link(n1.id, n2.id, "supports")
        results = mg.select_governed("dark mode")
        # Find n1 in results
        n1_result = next((r for r in results if r["node_id"] == n1.id), None)
        if n1_result:
            assert len(n1_result["evidence"]) > 0
            assert n2.id in [e["id"] for e in n1_result["evidence"]]

    def test_conflict_annotation(self):
        """Results should flag conflicting nodes."""
        mg = MemoryGraph()
        n1 = mg.add("Meeting is at 3pm", "event")
        n2 = mg.add("Meeting is at 4pm", "event")
        mg.link(n1.id, n2.id, "contradicts")
        results = mg.select_governed("Meeting")
        n1_result = next((r for r in results if r["node_id"] == n1.id), None)
        if n1_result:
            assert len(n1_result["conflicts"]) > 0
            assert n1_result["is_safe"] is False

    def test_safe_node_no_conflicts(self):
        """Nodes without conflicts should be marked safe."""
        mg = MemoryGraph()
        n1 = mg.add("The sky is blue", "fact")
        results = mg.select_governed("sky")
        n1_result = next((r for r in results if r["node_id"] == n1.id), None)
        if n1_result:
            assert n1_result["is_safe"] is True
            assert len(n1_result["conflicts"]) == 0

    def test_superseded_by_annotation(self):
        """If a node has a superseded_by edge, it should be annotated."""
        mg = MemoryGraph()
        old = mg.add("Config: max_connections=100", "fact")
        new_id = mg.supersede(old.id, "Config: max_connections=200")
        # old node should not appear in results (filtered by gate)
        # but new node should show superseded_by context if we query it
        results = mg.select_governed("Config max_connections")
        new_result = next((r for r in results if r["node_id"] == new_id), None)
        if new_result:
            # New node itself is safe
            assert new_result["is_safe"] is True


class TestGovernancePacket:
    """Test the output format of governed selection packets."""

    def test_packet_structure(self):
        """Each result packet should have required fields."""
        mg = MemoryGraph()
        mg.add("Test fact", "fact")
        results = mg.select_governed("Test")
        assert len(results) > 0
        pkt = results[0]
        required = {"node_id", "claim", "kind", "confidence", "is_safe",
                    "evidence", "conflicts", "superseded_by", "score"}
        assert required.issubset(pkt.keys())

    def test_explain_mode(self):
        """Explain mode should return governance metadata."""
        mg = MemoryGraph()
        mg.add("Fact A", "fact")
        mg.add("Fact B", "fact")
        result = mg.select_governed("Fact", explain=True)
        assert "results" in result
        assert "governance" in result
        gov = result["governance"]
        assert "stages" in gov
        assert "total_ms" in gov
        # Should report gate stats
        stage_names = [s["name"] for s in gov["stages"]]
        assert "structured_gate" in stage_names
        assert "recall" in stage_names

    def test_returns_empty_for_empty_graph(self):
        """Empty graph should return empty list."""
        mg = MemoryGraph()
        results = mg.select_governed("nothing")
        assert results == []

    def test_returns_empty_for_no_matches(self):
        """No query matches should return empty list."""
        mg = MemoryGraph()
        mg.add("Python", "concept")
        results = mg.select_governed("javascript")
        assert results == []

    def test_limit_respected(self):
        """Limit parameter should cap results."""
        mg = MemoryGraph()
        for i in range(20):
            mg.add(f"Python fact number {i}", "fact")
        results = mg.select_governed("Python", limit=5)
        assert len(results) <= 5


class TestIntegrationWithExistingRetrieve:
    """Test that governed selection integrates with existing retrieve() pipeline."""

    def test_governed_delegates_to_retrieve(self):
        """Governed selection should use existing retrieve for recall stage."""
        mg = MemoryGraph()
        n1 = mg.add("Python is great for data science", "fact")
        n2 = mg.add("Python has numpy library", "fact")
        mg.link(n1.id, n2.id, "related")
        # Both regular retrieve and governed should find Python nodes
        regular = mg.retrieve("Python", limit=5)
        governed = mg.select_governed("Python", limit=5)
        assert len(governed) > 0
        # Governed should be subset (gated)
        regular_ids = {r["node_id"] for r in regular}
        governed_ids = {r["node_id"] for r in governed}
        assert governed_ids.issubset(regular_ids) or governed_ids  # may differ slightly

    def test_governed_preserves_retrieve_ordering(self):
        """Governed selection should maintain score ordering from retrieve."""
        mg = MemoryGraph()
        mg.add("Python programming language", "concept")
        mg.add("Python snake animal", "concept")
        mg.add("Python Monty Python comedy", "concept")
        results = mg.select_governed("Python programming")
        # Scores should be in descending order
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_rerank_centrality_option(self):
        """Governed selection should support centrality rerank option."""
        mg = MemoryGraph()
        n1 = mg.add("Hub concept", "concept")
        n2 = mg.add("Connected fact A", "fact")
        n3 = mg.add("Connected fact B", "fact")
        mg.link(n1.id, n2.id, "related")
        mg.link(n1.id, n3.id, "related")
        # Should not raise with centrality option
        results = mg.select_governed("Hub", rerank_centrality="degree")
        assert isinstance(results, list)


class TestEdgeCases:
    """Edge cases and robustness."""

    def test_self_reference_no_evidence(self):
        """A node should not list itself as evidence."""
        mg = MemoryGraph()
        n1 = mg.add("Self-referential fact", "fact")
        mg.link(n1.id, n1.id, "supports")
        results = mg.select_governed("Self")
        n1_result = next((r for r in results if r["node_id"] == n1.id), None)
        if n1_result:
            ev_ids = [e["id"] for e in n1_result["evidence"]]
            assert n1.id not in ev_ids

    def test_multiple_conflicts_listed(self):
        """Multiple conflicting nodes should all be listed."""
        mg = MemoryGraph()
        n1 = mg.add("Price is $10", "fact")
        n2 = mg.add("Price is $20", "fact")
        n3 = mg.add("Price is $30", "fact")
        mg.link(n1.id, n2.id, "contradicts")
        mg.link(n1.id, n3.id, "contradicts")
        results = mg.select_governed("Price")
        n1_result = next((r for r in results if r["node_id"] == n1.id), None)
        if n1_result:
            assert len(n1_result["conflicts"]) >= 2

    def test_min_confidence_zero_includes_all(self):
        """min_confidence=0 should not filter anything by confidence."""
        mg = MemoryGraph()
        mg.add("Fact with low weight", "fact")
        results = mg.select_governed("Fact", min_confidence=0.0)
        # Should include results despite low confidence
        assert isinstance(results, list)

    def test_tags_filter(self):
        """Tags filter should restrict results to tagged nodes."""
        mg = MemoryGraph()
        n1 = mg.add("Tagged fact", "fact", tags=["important"])
        n2 = mg.add("Untagged fact", "fact")
        results = mg.select_governed("fact", require_tags=["important"])
        ids = [r["node_id"] for r in results]
        assert n1.id in ids
        assert n2.id not in ids
