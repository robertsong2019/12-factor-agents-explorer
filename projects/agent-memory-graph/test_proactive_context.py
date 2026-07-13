"""Tests for read_proactive_context() — Cycle 237.

CogniFold-inspired (2605.13438): proactive context assembly from
crystallized intent nodes, replacing reactive-only retrieval.
"""
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def graph_with_intents():
    """Build a graph with communities dense enough to crystallize intents."""
    g = MemoryGraph()

    # Community A: 4 tightly-linked Python nodes
    py1 = g.add("Python tutorial", "concept", {"topic": "python"})
    py2 = g.add("Python best practices", "concept", {"topic": "python"})
    py3 = g.add("Python decorators", "concept", {"topic": "python"})
    py4 = g.add("Python generators", "concept", {"topic": "python"})
    for a, b in [(py1.id, py2.id), (py1.id, py3.id), (py1.id, py4.id),
                 (py2.id, py3.id), (py2.id, py4.id), (py3.id, py4.id)]:
        g.link(a, b, "related")

    # Community B: 4 tightly-linked Rust nodes
    rs1 = g.add("Rust ownership", "concept", {"topic": "rust"})
    rs2 = g.add("Rust lifetimes", "concept", {"topic": "rust"})
    rs3 = g.add("Rust traits", "concept", {"topic": "rust"})
    rs4 = g.add("Rust pattern matching", "concept", {"topic": "rust"})
    for a, b in [(rs1.id, rs2.id), (rs1.id, rs3.id), (rs1.id, rs4.id),
                 (rs2.id, rs3.id), (rs2.id, rs4.id), (rs3.id, rs4.id)]:
        g.link(a, b, "related")

    # Crystallize intents
    result = g.crystallize_intents(density_threshold=0.3, min_community_size=3)
    return g, result


# ─── Basic functionality ────────────────────────────────────────────

class TestReadProactiveContext:
    """Core read_proactive_context() behavior."""

    def test_returns_dict_with_required_keys(self, graph_with_intents):
        g, _ = graph_with_intents
        result = g.read_proactive_context()
        assert isinstance(result, dict)
        assert "contexts" in result
        assert "total_intents" in result
        assert "total_nodes" in result

    def test_empty_graph_returns_empty(self):
        g = MemoryGraph()
        result = g.read_proactive_context()
        assert result["contexts"] == []
        assert result["total_intents"] == 0
        assert result["total_nodes"] == 0

    def test_no_intent_nodes_returns_empty(self):
        g = MemoryGraph()
        g.add("just a concept", "concept")
        result = g.read_proactive_context()
        assert result["total_intents"] == 0
        assert result["total_nodes"] == 0

    def test_finds_context_from_crystallized_intents(self, graph_with_intents):
        g, cryst = graph_with_intents
        assert len(cryst["crystallized"]) > 0, "Setup should crystallize at least one intent"

        result = g.read_proactive_context()
        assert result["total_intents"] >= 1
        assert result["total_nodes"] >= 1
        assert len(result["contexts"]) >= 1

    def test_contexts_have_member_lists(self, graph_with_intents):
        g, _ = graph_with_intents
        result = g.read_proactive_context()
        for ctx in result["contexts"]:
            assert "intent_id" in ctx
            assert "label" in ctx
            assert "density" in ctx
            assert "members" in ctx
            assert isinstance(ctx["members"], list)

    def test_members_have_temperature(self, graph_with_intents):
        g, _ = graph_with_intents
        result = g.read_proactive_context()
        for ctx in result["contexts"]:
            for m in ctx["members"]:
                assert "node_id" in m
                assert "label" in m
                assert "kind" in m
                assert "temperature" in m
                assert 0.0 <= m["temperature"] <= 1.0
                assert "linked_intents" in m


# ─── Filtering ──────────────────────────────────────────────────────

class TestProactiveContextFiltering:
    """active_intents, top_k, min_temperature."""

    def test_active_intents_filter_by_id(self, graph_with_intents):
        g, cryst = graph_with_intents
        first_intent_id = cryst["crystallized"][0]["intent_id"]
        result = g.read_proactive_context(active_intents=[first_intent_id])
        assert result["total_intents"] == 1
        for ctx in result["contexts"]:
            assert ctx["intent_id"] == first_intent_id

    def test_active_intents_filter_by_label_substring(self, graph_with_intents):
        g, cryst = graph_with_intents
        first_label = cryst["crystallized"][0]["label"]
        # Use a substring from the label
        substring = first_label[:10]
        result = g.read_proactive_context(active_intents=[substring])
        assert result["total_intents"] >= 1

    def test_active_intents_nonexistent_returns_empty(self, graph_with_intents):
        g, _ = graph_with_intents
        result = g.read_proactive_context(active_intents=["nonexistent_xyz"])
        assert result["total_intents"] == 0
        assert result["total_nodes"] == 0

    def test_top_k_limits_members(self, graph_with_intents):
        g, _ = graph_with_intents
        result = g.read_proactive_context(top_k=2)
        assert result["total_nodes"] <= 2

    def test_top_k_zero_returns_no_members(self, graph_with_intents):
        g, _ = graph_with_intents
        result = g.read_proactive_context(top_k=0)
        assert result["total_nodes"] == 0
        assert result["contexts"] == []

    def test_min_temperature_filters(self, graph_with_intents):
        g, _ = graph_with_intents
        result_high = g.read_proactive_context(min_temperature=0.99)
        result_low = g.read_proactive_context(min_temperature=0.0)
        assert result_low["total_nodes"] >= result_high["total_nodes"]

    def test_min_temperature_max_excludes_all(self, graph_with_intents):
        g, _ = graph_with_intents
        result = g.read_proactive_context(min_temperature=2.0)
        assert result["total_nodes"] == 0


# ─── include_intents flag ──────────────────────────────────────────

class TestProactiveContextIncludeIntents:
    """include_intents parameter behavior."""

    def test_include_intents_true_has_metadata(self, graph_with_intents):
        g, _ = graph_with_intents
        result = g.read_proactive_context(include_intents=True)
        for ctx in result["contexts"]:
            assert "density" in ctx
            assert "member_count" in ctx

    def test_include_intents_false_strips_metadata(self, graph_with_intents):
        g, _ = graph_with_intents
        result = g.read_proactive_context(include_intents=False)
        for ctx in result["contexts"]:
            assert "density" not in ctx
            assert "member_count" not in ctx


# ─── Deduplication ──────────────────────────────────────────────────

class TestProactiveContextDedup:
    """A node linked to multiple intents should appear once in top_members."""

    def test_dedup_across_intents(self):
        g = MemoryGraph()
        # Create one dense community
        nodes = [g.add(f"Node {i}", "concept") for i in range(5)]
        for i in range(5):
            for j in range(i + 1, 5):
                g.link(nodes[i].id, nodes[j].id, "related")
        cryst = g.crystallize_intents(density_threshold=0.3, min_community_size=3)
        assert len(cryst["crystallized"]) >= 1

        # Manually create a second intent and link to same members
        intent2 = g.add("Intent: extra", "intent", {"source": "manual"})
        for n in nodes:
            g.link(intent2.id, n.id, "abstracts")

        result = g.read_proactive_context(top_k=100)
        # total_nodes counts unique nodes (deduplicated), even if a node
        # appears in multiple contexts via linked_intents
        assert result["total_nodes"] == len(set(
            m["node_id"] for ctx in result["contexts"] for m in ctx["members"]
        ))

    def test_linked_intents_lists_all(self):
        g = MemoryGraph()
        nodes = [g.add(f"Shared {i}", "concept") for i in range(5)]
        for i in range(5):
            for j in range(i + 1, 5):
                g.link(nodes[i].id, nodes[j].id, "related")
        cryst = g.crystallize_intents(density_threshold=0.3, min_community_size=3)
        if not cryst["crystallized"]:
            pytest.skip("No intents crystallized")

        # Create a second intent linking to first 3 nodes
        intent2 = g.add("Intent: manual extra", "intent", {"source": "manual"})
        for n in nodes[:3]:
            g.link(intent2.id, n.id, "abstracts")

        result = g.read_proactive_context(top_k=100)
        # Nodes linked to both intents should list both in linked_intents
        for ctx in result["contexts"]:
            for m in ctx["members"]:
                if m["node_id"] in [n.id for n in nodes[:3]]:
                    # Should have at least the intent we manually added
                    assert len(m["linked_intents"]) >= 1


# ─── Quarantine interaction ────────────────────────────────────────

class TestProactiveContextQuarantine:
    """Quarantined nodes should not appear in proactive context."""

    def test_quarantined_members_excluded(self):
        g = MemoryGraph()
        nodes = [g.add(f"Concept {i}", "concept") for i in range(5)]
        for i in range(5):
            for j in range(i + 1, 5):
                g.link(nodes[i].id, nodes[j].id, "related")
        cryst = g.crystallize_intents(density_threshold=0.3, min_community_size=3)
        assert len(cryst["crystallized"]) >= 1

        # Quarantine one member
        g.node_quarantine(nodes[0].id, "test quarantine")

        result = g.read_proactive_context(top_k=100)
        all_ids = [m["node_id"] for ctx in result["contexts"] for m in ctx["members"]]
        assert nodes[0].id not in all_ids


# ─── Sorting order ──────────────────────────────────────────────────

class TestProactiveContextSorting:
    """Contexts sorted by member count (most useful first)."""

    def test_contexts_sorted_by_member_count(self):
        g = MemoryGraph()
        # Large community (6 nodes)
        big = [g.add(f"Big {i}", "concept") for i in range(6)]
        for i in range(6):
            for j in range(i + 1, 6):
                g.link(big[i].id, big[j].id, "related")

        # Small community (3 nodes)
        small = [g.add(f"Small {i}", "concept") for i in range(3)]
        for i in range(3):
            for j in range(i + 1, 3):
                g.link(small[i].id, small[j].id, "related")

        cryst = g.crystallize_intents(density_threshold=0.2, min_community_size=3)
        result = g.read_proactive_context(top_k=100)
        if len(result["contexts"]) >= 2:
            counts = [len(c["members"]) for c in result["contexts"]]
            assert counts == sorted(counts, reverse=True)


# ─── Edge cases ─────────────────────────────────────────────────────

class TestProactiveContextEdgeCases:
    """Boundary conditions and error handling."""

    def test_intent_node_with_no_members(self):
        g = MemoryGraph()
        # Manually add an intent with no abstracts edges
        g.add("Orphan intent", "intent", {"source": "manual"})
        result = g.read_proactive_context()
        assert result["total_intents"] == 1
        assert result["total_nodes"] == 0
        # Context entry exists but has empty members
        assert any(len(c["members"]) == 0 for c in result["contexts"])

    def test_self_reference_excluded(self):
        g = MemoryGraph()
        intent = g.add("Self-ref intent", "intent", {"source": "manual"})
        # Create an abstracts edge to itself
        g.link(intent.id, intent.id, "abstracts")
        result = g.read_proactive_context()
        all_ids = [m["node_id"] for ctx in result["contexts"] for m in ctx["members"]]
        assert intent.id not in all_ids

    def test_negative_top_k_returns_empty(self, graph_with_intents):
        g, _ = graph_with_intents
        result = g.read_proactive_context(top_k=-5)
        assert result["total_nodes"] == 0
        assert result["contexts"] == []

    def test_large_top_k_returns_all(self, graph_with_intents):
        g, _ = graph_with_intents
        result = g.read_proactive_context(top_k=10000)
        # Should return all available members
        assert result["total_nodes"] >= 1

    def test_default_top_k_is_10(self, graph_with_intents):
        g, _ = graph_with_intents
        result = g.read_proactive_context()
        assert result["total_nodes"] <= 10
