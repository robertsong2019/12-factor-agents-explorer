"""Tests for trace_derivation() — provenance tracking via derived_from / computed_from edges.

Covers:
- Basic single-hop derivation
- Multi-hop chain (summary → raw_data → sensor)
- Diamond dependency (two sources converge)
- No derivation edges (root node)
- Nonexistent node
- Cycle safety
- Mixed derived_from / computed_from
- Confidence propagation
- max_depth cutoff
- Roots identification
- all_sources completeness
- Integration with add_causal_edge (new relation types accepted)
- New relation types in _CAUSAL_RELATIONS
- invalidate_cascade / propagate_correction still work with new relation types
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


def _add(mg, label, kind="fact"):
    """Helper: add node and return its auto-generated ID."""
    return mg.add(label=label, kind=kind).id


# ── New causal relation types accepted ────────────────────────

class TestNewCausalRelations:
    def test_derived_from_accepted(self, mg):
        """derived_from should be a valid causal relation."""
        src = _add(mg, "Source data")
        der = _add(mg, "Derived insight")
        result = mg.add_causal_edge(der, src, "derived_from", confidence=0.85)
        assert result["relation"] == "derived_from"
        assert result["confidence"] == 0.85

    def test_computed_from_accepted(self, mg):
        """computed_from should be a valid causal relation."""
        raw = _add(mg, "Raw data")
        comp = _add(mg, "Computed metric")
        result = mg.add_causal_edge(comp, raw, "computed_from", confidence=1.0)
        assert result["relation"] == "computed_from"

    def test_derived_from_in_causal_relations(self):
        """_CAUSAL_RELATIONS must include derived_from."""
        assert "derived_from" in MemoryGraph._CAUSAL_RELATIONS

    def test_computed_from_in_causal_relations(self):
        """_CAUSAL_RELATIONS must include computed_from."""
        assert "computed_from" in MemoryGraph._CAUSAL_RELATIONS


# ── Basic derivation tracing ──────────────────────────────────

class TestBasicDerivation:
    def test_single_hop(self, mg):
        """One derived_from edge → simple chain."""
        a = _add(mg, "Source A")
        b = _add(mg, "Derived from A")
        mg.add_causal_edge(b, a, "derived_from", confidence=0.9)

        result = mg.trace_derivation(b)
        assert result["node"] == b
        assert len(result["chains"]) == 1
        assert result["chains"][0][0]["source"] == b
        assert result["chains"][0][0]["target"] == a
        assert result["chains"][0][0]["relation"] == "derived_from"
        assert result["chains"][0][0]["confidence"] == 0.9
        assert result["roots"] == [a]
        assert result["all_sources"] == [a]
        assert result["depth_reached"] == 1

    def test_no_derivation_edges(self, mg):
        """Node with no incoming derivation edges → empty chains."""
        root = _add(mg, "Root observation")
        result = mg.trace_derivation(root)
        assert result["chains"] == []
        assert result["roots"] == [root]
        assert result["all_sources"] == []
        assert result["depth_reached"] == 0


# ── Multi-hop chains ──────────────────────────────────────────

class TestMultiHop:
    def test_three_hop_chain(self, mg):
        """summary → raw_data → sensor_1."""
        sensor = _add(mg, "Sensor reading")
        raw = _add(mg, "Aggregated raw")
        summary = _add(mg, "Daily summary")
        mg.add_causal_edge(summary, raw, "derived_from", confidence=0.8)
        mg.add_causal_edge(raw, sensor, "computed_from", confidence=1.0)

        result = mg.trace_derivation(summary)
        assert len(result["chains"]) == 1
        chain = result["chains"][0]
        assert len(chain) == 2
        assert chain[0]["source"] == summary
        assert chain[0]["target"] == raw
        assert chain[1]["source"] == raw
        assert chain[1]["target"] == sensor
        assert result["roots"] == [sensor]
        assert set(result["all_sources"]) == {raw, sensor}
        assert result["depth_reached"] == 2

    def test_mixed_relations_in_chain(self, mg):
        """Chain with both derived_from and computed_from."""
        a = _add(mg, "A")
        b = _add(mg, "B")
        c = _add(mg, "C")
        mg.add_causal_edge(c, b, "computed_from")
        mg.add_causal_edge(b, a, "derived_from")

        result = mg.trace_derivation(c)
        assert len(result["chains"]) == 1
        chain = result["chains"][0]
        assert chain[0]["relation"] == "computed_from"
        assert chain[1]["relation"] == "derived_from"
        assert result["roots"] == [a]


# ── Diamond / branching ───────────────────────────────────────

class TestDiamond:
    def test_diamond_dependency(self, mg):
        """Two paths converging: D ← B ← A and D ← C ← A."""
        a = _add(mg, "Root source")
        b = _add(mg, "Intermediate B")
        c = _add(mg, "Intermediate C")
        d = _add(mg, "Final")
        mg.add_causal_edge(b, a, "derived_from")
        mg.add_causal_edge(c, a, "derived_from")
        mg.add_causal_edge(d, b, "computed_from")
        mg.add_causal_edge(d, c, "computed_from")

        result = mg.trace_derivation(d)
        # Two chains: D→B→A and D→C→A
        assert len(result["chains"]) == 2
        assert result["depth_reached"] == 2
        # Both chains end at A
        assert result["roots"] == [a]
        # All intermediates
        assert set(result["all_sources"]) == {a, b, c}

    def test_multiple_roots(self, mg):
        """Node derived from two independent roots."""
        r1 = _add(mg, "Root 1")
        r2 = _add(mg, "Root 2")
        child = _add(mg, "Child")
        mg.add_causal_edge(child, r1, "derived_from")
        mg.add_causal_edge(child, r2, "derived_from")

        result = mg.trace_derivation(child)
        assert len(result["chains"]) == 2
        assert set(result["roots"]) == {r1, r2}


# ── Edge cases ────────────────────────────────────────────────

class TestEdgeCases:
    def test_nonexistent_node(self, mg):
        """Nonexistent node → error in result."""
        result = mg.trace_derivation("ghost_node")
        assert result["node"] == "ghost_node"
        assert result["chains"] == []
        assert "error" in result

    def test_cycle_safety(self, mg):
        """A → B → A cycle should not loop forever."""
        a = _add(mg, "A")
        b = _add(mg, "B")
        mg.add_causal_edge(b, a, "derived_from")
        mg.add_causal_edge(a, b, "derived_from")

        result = mg.trace_derivation(b)
        # Should terminate, producing finite chains
        assert isinstance(result["chains"], list)
        # Each chain should have finite length
        for chain in result["chains"]:
            assert len(chain) <= 10

    def test_max_depth_cutoff(self, mg):
        """max_depth=1 should truncate long chains."""
        a = _add(mg, "A")
        b = _add(mg, "B")
        c = _add(mg, "C")
        mg.add_causal_edge(c, b, "derived_from")
        mg.add_causal_edge(b, a, "derived_from")

        result = mg.trace_derivation(c, max_depth=1)
        # Only first hop visible
        assert result["depth_reached"] == 1
        # B should appear as a root (can't go deeper)
        assert b in result["roots"]

    def test_isolated_node(self, mg):
        """Node with no edges at all."""
        lonely = _add(mg, "Lonely node")
        result = mg.trace_derivation(lonely)
        assert result["chains"] == []
        assert result["roots"] == [lonely]
        assert result["depth_reached"] == 0


# ── Confidence propagation ────────────────────────────────────

class TestConfidence:
    def test_confidence_stored_in_chain(self, mg):
        """Each edge in chain should carry its confidence."""
        a = _add(mg, "A")
        b = _add(mg, "B")
        c = _add(mg, "C")
        mg.add_causal_edge(c, b, "derived_from", confidence=0.7)
        mg.add_causal_edge(b, a, "computed_from", confidence=0.95)

        result = mg.trace_derivation(c)
        chain = result["chains"][0]
        assert chain[0]["confidence"] == 0.7
        assert chain[1]["confidence"] == 0.95

    def test_default_confidence_one(self, mg):
        """If no confidence specified, defaults to 1.0."""
        a = _add(mg, "A")
        b = _add(mg, "B")
        mg.add_causal_edge(b, a, "derived_from")  # no confidence

        result = mg.trace_derivation(b)
        assert result["chains"][0][0]["confidence"] == 1.0

    def test_chains_sorted_by_confidence(self, mg):
        """When multiple chains exist, higher-confidence sorted first."""
        a = _add(mg, "A")
        b = _add(mg, "B")
        c = _add(mg, "C")
        d = _add(mg, "D")
        # High confidence path: D ← C ← A
        mg.add_causal_edge(c, a, "derived_from", confidence=0.95)
        mg.add_causal_edge(d, c, "derived_from", confidence=0.9)
        # Low confidence path: D ← B ← A
        mg.add_causal_edge(b, a, "derived_from", confidence=0.3)
        mg.add_causal_edge(d, b, "derived_from", confidence=0.2)

        result = mg.trace_derivation(d)
        # Both chains same length (2), so sorted by total confidence
        assert len(result["chains"]) == 2
        # Higher confidence chain first
        total_0 = sum(e["confidence"] for e in result["chains"][0])
        total_1 = sum(e["confidence"] for e in result["chains"][1])
        assert total_0 >= total_1


# ── Integration with existing features ────────────────────────

class TestIntegration:
    def test_cascade_with_new_relation(self, mg):
        """invalidate_cascade should work when depends_on edges exist
        alongside derived_from edges."""
        source = _add(mg, "Source")
        derived = _add(mg, "Derived")
        dependent = _add(mg, "Dependent")
        mg.add_causal_edge(derived, source, "derived_from")
        mg.add_causal_edge(dependent, source, "depends_on")

        # Invalidate source → dependent should cascade
        result = mg.invalidate_cascade(source)
        assert dependent in result["cascaded"]

    def test_get_causal_edges_returns_new_types(self, mg):
        """get_causal_edges should return derived_from / computed_from."""
        a = _add(mg, "A")
        b = _add(mg, "B")
        mg.add_causal_edge(b, a, "derived_from")

        edges = mg.get_causal_edges(b, direction="outgoing")
        assert len(edges) == 1
        assert edges[0]["relation"] == "derived_from"

    def test_trace_causal_chain_includes_derivation(self, mg):
        """trace_causal_chain backward should follow derivation edges.
        Edge B→A means 'B derived_from A'. For backward traversal
        (effects→causes), we follow edges where target = current,
        which finds A from B."""
        a = _add(mg, "A")
        b = _add(mg, "B")
        mg.add_causal_edge(b, a, "derived_from", confidence=0.8)

        # Forward from B: follow outgoing edges B→A
        chains_fwd = mg.trace_causal_chain(b, direction="forward")
        assert len(chains_fwd) >= 1
        # The chain should reach A
        targets = {e["target"] for chain in chains_fwd for e in chain}
        assert a in targets

    def test_propagate_correction_with_derived(self, mg):
        """propagate_correction should not break with derived_from present."""
        source = _add(mg, "Source data")
        derived = _add(mg, "Derived")
        dep = _add(mg, "Dependent")
        mg.add_causal_edge(derived, source, "derived_from")
        mg.add_causal_edge(dep, source, "depends_on")

        result = mg.propagate_correction(source, new_content="Updated source")
        assert result["count"] >= 1

    def test_evidence_and_note_stored(self, mg):
        """derived_from edge should store evidence and note metadata."""
        a = _add(mg, "A")
        b = _add(mg, "B")
        ev = _add(mg, "Evidence 1")
        result = mg.add_causal_edge(b, a, "derived_from",
                                    confidence=0.9,
                                    evidence=[ev],
                                    note="Extracted from A")
        assert result["evidence"] == [ev]
        assert result["note"] == "Extracted from A"


# ── Return structure completeness ─────────────────────────────

class TestReturnStructure:
    def test_result_has_all_fields(self, mg):
        """Result dict should have all required keys."""
        a = _add(mg, "A")
        b = _add(mg, "B")
        mg.add_causal_edge(b, a, "derived_from")

        result = mg.trace_derivation(b)
        for key in ("node", "roots", "chains", "all_sources", "depth_reached"):
            assert key in result, f"Missing key: {key}"

    def test_all_sources_excludes_query_node(self, mg):
        """The query node should not appear in all_sources."""
        a = _add(mg, "A")
        b = _add(mg, "B")
        mg.add_causal_edge(b, a, "derived_from")

        result = mg.trace_derivation(b)
        assert b not in result["all_sources"]

    def test_roots_are_sources_without_derivation(self, mg):
        """Roots should have no outgoing derivation edges (not derived
        from anything themselves)."""
        a = _add(mg, "A")
        b = _add(mg, "B")
        c = _add(mg, "C")
        mg.add_causal_edge(c, b, "derived_from")
        mg.add_causal_edge(b, a, "derived_from")

        result = mg.trace_derivation(c)
        for root in result["roots"]:
            # Root nodes should have no outgoing derivation edges
            outgoing = mg.get_causal_edges(root, direction="outgoing",
                                           relation="derived_from")
            computed = mg.get_causal_edges(root, direction="outgoing",
                                           relation="computed_from")
            assert len(outgoing) == 0
            assert len(computed) == 0
