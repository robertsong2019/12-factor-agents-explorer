"""Tests for causal edges — Cycle 230 (ActMem-inspired).

Tests for add_causal_edge(), get_causal_edges(), trace_causal_chain().
"""
import pytest
from memory_graph import MemoryGraph


# ─── Fixtures ────────────────────────────────────────────────

@pytest.fixture
def mg():
    g = MemoryGraph()
    return g


@pytest.fixture
def causal_graph(mg):
    """Build a small causal chain: A causes B, B enables C, C prevents D."""
    a = mg.add("Event A", "event")
    b = mg.add("Event B", "event")
    c = mg.add("State C", "state")
    d = mg.add("State D", "state")
    e = mg.add("Evidence E", "evidence")
    return mg, a, b, c, d, e


# ─── add_causal_edge: basic creation ────────────────────────

class TestAddCausalEdgeBasic:
    def test_creates_edge_with_default_confidence(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        result = mg.add_causal_edge(a.id, b.id, "causes")
        assert result["source"] == a.id
        assert result["target"] == b.id
        assert result["relation"] == "causes"
        assert result["confidence"] == 1.0

    def test_creates_edge_with_custom_confidence(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        result = mg.add_causal_edge(a.id, b.id, "enables", confidence=0.7)
        assert result["confidence"] == 0.7

    def test_edge_stored_in_graph(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        mg.add_causal_edge(a.id, b.id, "causes")
        assert mg.is_linked(a.id, b.id, "causes")

    def test_confidence_used_as_edge_weight(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        mg.add_causal_edge(a.id, b.id, "causes", confidence=0.5)
        edges = mg.conn.execute(
            "SELECT weight FROM edges WHERE source=? AND target=? AND relation=?",
            (a.id, b.id, "causes"),
        ).fetchone()
        assert edges["weight"] == 0.5

    def test_returns_evidence_list(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        ev = mg.add("Proof", "evidence")
        result = mg.add_causal_edge(a.id, b.id, "causes", evidence=[ev.id])
        assert result["evidence"] == [ev.id]

    def test_returns_empty_evidence_by_default(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        result = mg.add_causal_edge(a.id, b.id, "causes")
        assert result["evidence"] == []

    def test_note_stored_and_returned(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        result = mg.add_causal_edge(a.id, b.id, "causes", note="A triggered B")
        assert result["note"] == "A triggered B"

    def test_note_defaults_empty(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        result = mg.add_causal_edge(a.id, b.id, "causes")
        assert result["note"] == ""

    def test_created_at_is_set(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        result = mg.add_causal_edge(a.id, b.id, "causes")
        assert result["created_at"] is not None
        assert result["created_at"] > 0


# ─── add_causal_edge: all five relation types ───────────────

class TestCausalRelationTypes:
    @pytest.mark.parametrize("rel", [
        "causes", "prevents", "conflicts_with", "enables", "depends_on",
    ])
    def test_each_relation_type_accepted(self, mg, rel):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        result = mg.add_causal_edge(a.id, b.id, rel)
        assert result["relation"] == rel

    def test_unknown_relation_rejected(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        with pytest.raises(ValueError, match="Unknown causal relation"):
            mg.add_causal_edge(a.id, b.id, "makes_coffee")

    def test_empty_string_relation_rejected(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        with pytest.raises(ValueError):
            mg.add_causal_edge(a.id, b.id, "")


# ─── add_causal_edge: validation ────────────────────────────

class TestAddCausalEdgeValidation:
    def test_confidence_below_zero_rejected(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        with pytest.raises(ValueError, match="confidence"):
            mg.add_causal_edge(a.id, b.id, "causes", confidence=-0.1)

    def test_confidence_above_one_rejected(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        with pytest.raises(ValueError, match="confidence"):
            mg.add_causal_edge(a.id, b.id, "causes", confidence=1.5)

    def test_confidence_zero_allowed(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        result = mg.add_causal_edge(a.id, b.id, "causes", confidence=0.0)
        assert result["confidence"] == 0.0

    def test_confidence_one_allowed(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        result = mg.add_causal_edge(a.id, b.id, "causes", confidence=1.0)
        assert result["confidence"] == 1.0

    def test_nonexistent_source_rejected(self, mg):
        b = mg.add("B", "event")
        with pytest.raises(ValueError, match="source node"):
            mg.add_causal_edge("nonexistent", b.id, "causes")

    def test_nonexistent_target_rejected(self, mg):
        a = mg.add("A", "event")
        with pytest.raises(ValueError, match="target node"):
            mg.add_causal_edge(a.id, "nonexistent", "causes")

    def test_both_nonexistent_rejected(self, mg):
        with pytest.raises(ValueError):
            mg.add_causal_edge("nope1", "nope2", "causes")


# ─── add_causal_edge: overwrite behaviour ───────────────────

class TestCausalEdgeOverwrite:
    def test_updating_existing_edge(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        mg.add_causal_edge(a.id, b.id, "causes", confidence=0.5)
        result = mg.add_causal_edge(a.id, b.id, "causes", confidence=0.9)
        assert result["confidence"] == 0.9
        edges = mg.get_causal_edges(a.id, direction="outgoing")
        assert len(edges) == 1
        assert edges[0]["confidence"] == 0.9

    def test_updating_with_evidence(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        ev = mg.add("Proof", "evidence")
        mg.add_causal_edge(a.id, b.id, "causes", confidence=0.3)
        mg.add_causal_edge(a.id, b.id, "causes", confidence=0.8,
                           evidence=[ev.id], note="Updated")
        edges = mg.get_causal_edges(a.id, direction="outgoing")
        assert edges[0]["evidence"] == [ev.id]
        assert edges[0]["note"] == "Updated"


# ─── get_causal_edges ───────────────────────────────────────

class TestGetCausalEdges:
    def test_outgoing_only(self, causal_graph):
        mg, a, b, c, d, e = causal_graph
        mg.add_causal_edge(a.id, b.id, "causes")
        mg.add_causal_edge(b.id, c.id, "enables")
        edges = mg.get_causal_edges(a.id, direction="outgoing")
        assert len(edges) == 1
        assert edges[0]["relation"] == "causes"
        assert edges[0]["target"] == b.id

    def test_incoming_only(self, causal_graph):
        mg, a, b, c, d, e = causal_graph
        mg.add_causal_edge(a.id, b.id, "causes")
        mg.add_causal_edge(b.id, c.id, "enables")
        edges = mg.get_causal_edges(c.id, direction="incoming")
        assert len(edges) == 1
        assert edges[0]["relation"] == "enables"
        assert edges[0]["source"] == b.id

    def test_both_directions(self, causal_graph):
        mg, a, b, c, d, e = causal_graph
        mg.add_causal_edge(a.id, b.id, "causes")
        mg.add_causal_edge(c.id, b.id, "prevents")
        edges = mg.get_causal_edges(b.id, direction="both")
        assert len(edges) == 2

    def test_filter_by_relation(self, causal_graph):
        mg, a, b, c, d, e = causal_graph
        mg.add_causal_edge(a.id, b.id, "causes")
        mg.add_causal_edge(a.id, c.id, "enables")
        edges = mg.get_causal_edges(a.id, relation="causes")
        assert len(edges) == 1
        assert edges[0]["relation"] == "causes"

    def test_no_causal_edges(self, mg):
        a = mg.add("A", "event")
        edges = mg.get_causal_edges(a.id)
        assert edges == []

    def test_nonexistent_node_returns_empty(self, mg):
        edges = mg.get_causal_edges("nonexistent")
        assert edges == []

    def test_invalid_direction_rejected(self, mg):
        a = mg.add("A", "event")
        with pytest.raises(ValueError, match="direction"):
            mg.get_causal_edges(a.id, direction="sideways")

    def test_non_causal_edges_excluded(self, mg):
        """Regular link() edges with non-causal relations should not appear."""
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        mg.link(a.id, b.id, "related_to")
        edges = mg.get_causal_edges(a.id)
        assert edges == []

    def test_props_enriched_in_results(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        ev = mg.add("Proof", "evidence")
        mg.add_causal_edge(a.id, b.id, "causes", confidence=0.8,
                           evidence=[ev.id], note="Strong link")
        edges = mg.get_causal_edges(a.id)
        assert edges[0]["confidence"] == 0.8
        assert edges[0]["evidence"] == [ev.id]
        assert edges[0]["note"] == "Strong link"

    def test_multiple_relation_types_returned(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        c = mg.add("C", "event")
        mg.add_causal_edge(a.id, b.id, "causes")
        mg.add_causal_edge(a.id, c.id, "prevents")
        edges = mg.get_causal_edges(a.id, direction="outgoing")
        rels = {e["relation"] for e in edges}
        assert rels == {"causes", "prevents"}


# ─── trace_causal_chain ─────────────────────────────────────

class TestTraceCausalChain:
    def test_simple_two_hop_chain(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        mg.add_causal_edge(a.id, b.id, "causes")
        chains = mg.trace_causal_chain(a.id, direction="forward")
        assert len(chains) >= 1
        assert chains[0][0]["source"] == a.id
        assert chains[0][0]["target"] == b.id

    def test_three_hop_chain(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        c = mg.add("C", "event")
        mg.add_causal_edge(a.id, b.id, "causes")
        mg.add_causal_edge(b.id, c.id, "enables")
        chains = mg.trace_causal_chain(a.id, direction="forward")
        assert len(chains) >= 1
        assert len(chains[0]) == 2
        assert chains[0][0]["source"] == a.id
        assert chains[0][1]["target"] == c.id

    def test_branching_chain(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        c = mg.add("C", "event")
        mg.add_causal_edge(a.id, b.id, "causes")
        mg.add_causal_edge(a.id, c.id, "prevents")
        chains = mg.trace_causal_chain(a.id, direction="forward")
        assert len(chains) == 2

    def test_backward_traces_to_root(self, mg):
        a = mg.add("Root Cause", "event")
        b = mg.add("Mid", "event")
        c = mg.add("Effect", "event")
        mg.add_causal_edge(a.id, b.id, "causes")
        mg.add_causal_edge(b.id, c.id, "causes")
        chains = mg.trace_causal_chain(c.id, direction="backward")
        assert len(chains) >= 1
        longest = chains[0]
        assert len(longest) == 2
        assert longest[0]["source"] == b.id
        assert longest[1]["source"] == a.id

    def test_cycle_detection_prevents_infinite_loop(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        mg.add_causal_edge(a.id, b.id, "causes")
        mg.add_causal_edge(b.id, a.id, "enables")
        chains = mg.trace_causal_chain(a.id, direction="forward")
        # Should terminate, not hang
        assert len(chains) >= 1
        for chain in chains:
            sources = [e["source"] for e in chain]
            assert len(sources) == len(set(sources)), "Cycle not handled"

    def test_max_depth_limit(self, mg):
        nodes = [mg.add(f"N{i}", "event") for i in range(15)]
        for i in range(len(nodes) - 1):
            mg.add_causal_edge(nodes[i].id, nodes[i + 1].id, "causes")
        chains = mg.trace_causal_chain(nodes[0].id, max_depth=5)
        for chain in chains:
            assert len(chain) <= 5

    def test_no_chain_returns_empty(self, mg):
        a = mg.add("Lonely", "event")
        chains = mg.trace_causal_chain(a.id)
        assert chains == []

    def test_invalid_direction_rejected(self, mg):
        a = mg.add("A", "event")
        with pytest.raises(ValueError, match="direction"):
            mg.trace_causal_chain(a.id, direction="sideways")

    def test_chain_includes_confidence(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        mg.add_causal_edge(a.id, b.id, "causes", confidence=0.7)
        chains = mg.trace_causal_chain(a.id, direction="forward")
        assert chains[0][0]["confidence"] == 0.7

    def test_chains_sorted_longest_first(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        c = mg.add("C", "event")
        d = mg.add("D", "event")
        mg.add_causal_edge(a.id, b.id, "causes")
        mg.add_causal_edge(b.id, c.id, "causes")
        mg.add_causal_edge(c.id, d.id, "causes")
        mg.add_causal_edge(a.id, d.id, "prevents")
        chains = mg.trace_causal_chain(a.id, direction="forward")
        # Longest chain (3 hops) should be first
        assert len(chains[0]) >= len(chains[-1])

    def test_diamond_dependency(self, mg):
        """A → B → D and A → C → D (diamond)."""
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        c = mg.add("C", "event")
        d = mg.add("D", "event")
        mg.add_causal_edge(a.id, b.id, "causes")
        mg.add_causal_edge(a.id, c.id, "causes")
        mg.add_causal_edge(b.id, d.id, "enables")
        mg.add_causal_edge(c.id, d.id, "enables")
        chains = mg.trace_causal_chain(a.id, direction="forward")
        assert len(chains) == 2
        # Both chains should reach D
        targets = {chain[-1]["target"] for chain in chains}
        assert d.id in targets


# ─── Integration: causal + existing graph features ──────────

class TestCausalIntegration:
    def test_causal_edges_visible_in_subgraph_by_edge_type(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        mg.add_causal_edge(a.id, b.id, "causes")
        sub = mg.subgraph_by_edge_type("causes")
        assert sub["stats"]["edge_count"] == 1

    def test_causal_edge_can_be_traced_via_decision_chain(self, mg):
        """Causal edges are regular edges, visible in traversal."""
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        mg.add_causal_edge(a.id, b.id, "enables")
        neighbors = mg.neighbors(a.id)
        labels = [n.label for n in neighbors]
        assert "B" in labels

    def test_multiple_causal_edges_on_same_pair(self, mg):
        """Same pair can have both 'causes' and 'prevents' (different relations)."""
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        mg.add_causal_edge(a.id, b.id, "causes")
        mg.add_causal_edge(a.id, b.id, "prevents")
        edges = mg.get_causal_edges(a.id, direction="outgoing")
        assert len(edges) == 2
        rels = {e["relation"] for e in edges}
        assert rels == {"causes", "prevents"}

    def test_causal_edges_persist_in_snapshot(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        mg.add_causal_edge(a.id, b.id, "causes", note="persistent")
        snap = mg.snapshot()
        mg.restore(snap)
        edges = mg.get_causal_edges(a.id, direction="outgoing")
        assert len(edges) == 1
        assert edges[0]["relation"] == "causes"

    def test_causal_edge_props_stored(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        ev = mg.add("Proof1", "evidence")
        mg.add_causal_edge(a.id, b.id, "causes", confidence=0.6,
                           evidence=[ev.id], note="Test note")
        prop = mg.conn.execute(
            "SELECT properties FROM edge_props "
            "WHERE source=? AND target=? AND relation=?",
            (a.id, b.id, "causes"),
        ).fetchone()
        import json
        p = json.loads(prop["properties"])
        assert p["confidence"] == 0.6
        assert p["evidence"] == [ev.id]
        assert p["note"] == "Test note"
        assert p["causal"] is True


# ─── Edge cases ─────────────────────────────────────────────

class TestCausalEdgeCases:
    def test_self_causal_edge(self, mg):
        """A node causing itself (self-loop)."""
        a = mg.add("Recursive", "event")
        result = mg.add_causal_edge(a.id, a.id, "causes")
        assert result["source"] == a.id
        assert result["target"] == a.id
        chains = mg.trace_causal_chain(a.id, direction="forward")
        # Should not infinite loop
        for chain in chains:
            sources = [e["source"] for e in chain]
            assert len(sources) == len(set(sources))

    def test_empty_graph_causal_query(self, mg):
        edges = mg.get_causal_edges("anyone")
        assert edges == []

    def test_trace_from_nonexistent_node(self, mg):
        chains = mg.trace_causal_chain("ghost")
        # Should return empty, not crash
        assert chains == []

    def test_confidence_boundary_values(self, mg):
        a = mg.add("A", "event")
        b = mg.add("B", "event")
        # Exact 0 and exact 1 should work
        mg.add_causal_edge(a.id, b.id, "causes", confidence=0.0)
        mg.add_causal_edge(a.id, b.id, "enables", confidence=1.0)
        edges = mg.get_causal_edges(a.id)
        confidences = sorted(e["confidence"] for e in edges)
        assert confidences == [0.0, 1.0]
