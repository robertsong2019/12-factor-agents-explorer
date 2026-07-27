"""Tests for EntityResolver — alias management and entity resolution.

Research #032 identified entity resolution as "table stakes" — both Mem0 v3
and Graphiti have it. This fills the gap for agent-memory-graph.
"""

import pytest
from memory_graph import MemoryGraph


# ─── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture
def mg():
    g = MemoryGraph()
    a = g.add("Alice Wang", kind="person")
    b = g.add("Bob Li", kind="person")
    p = g.add("Project Phoenix", kind="project")
    g._alice_id = a.id
    g._bob_id = b.id
    g._proj_id = p.id
    return g


# ── register_alias / resolve_alias ─────────────────────────────────────────────

class TestRegisterAlias:
    def test_register_single_alias(self, mg):
        """Register an alias and resolve it back to canonical."""
        mg.register_alias("Alice Wang", "A. Wang")
        assert mg.resolve_alias("A. Wang") == "Alice Wang"

    def test_register_multiple_aliases(self, mg):
        """Multiple aliases map to same canonical."""
        mg.register_alias("Alice Wang", "Alice")
        mg.register_alias("Alice Wang", "AW")
        mg.register_alias("Alice Wang", "alice_w")
        assert mg.resolve_alias("Alice") == "Alice Wang"
        assert mg.resolve_alias("AW") == "Alice Wang"
        assert mg.resolve_alias("alice_w") == "Alice Wang"

    def test_canonical_resolves_to_self(self, mg):
        """Canonical label resolves to itself."""
        mg.register_alias("Alice Wang", "Alice")
        assert mg.resolve_alias("Alice Wang") == "Alice Wang"

    def test_unregistered_alias_returns_none(self, mg):
        assert mg.resolve_alias("Unknown") is None

    def test_register_alias_case_insensitive(self, mg):
        """Aliases are case-insensitive."""
        mg.register_alias("Alice Wang", "ALICE")
        assert mg.resolve_alias("alice") == "Alice Wang"
        assert mg.resolve_alias("Alice") == "Alice Wang"

    def test_register_alias_whitespace_trimmed(self, mg):
        """Leading/trailing whitespace is trimmed."""
        mg.register_alias("Alice Wang", "  Alice  ")
        assert mg.resolve_alias("Alice") == "Alice Wang"

    def test_register_alias_for_nonexistent_canonical_raises(self, mg):
        """Cannot register alias for a label that doesn't exist."""
        with pytest.raises(ValueError, match="not found"):
            mg.register_alias("Nobody", "Ghost")


# ── list_aliases ───────────────────────────────────────────────────────────────

class TestListAliases:
    def test_list_empty(self, mg):
        assert mg.list_aliases() == {}

    def test_list_after_registration(self, mg):
        mg.register_alias("Alice Wang", "Alice")
        mg.register_alias("Alice Wang", "AW")
        mg.register_alias("Bob Li", "Bobby")
        result = mg.list_aliases()
        assert set(result["Alice Wang"]) == {"Alice", "AW"}
        assert result["Bob Li"] == ["Bobby"]

    def test_list_filtered_by_canonical(self, mg):
        mg.register_alias("Alice Wang", "Alice")
        mg.register_alias("Bob Li", "Bobby")
        result = mg.list_aliases(canonical="Alice Wang")
        assert result == {"Alice Wang": ["Alice"]}


# ── remove_alias ───────────────────────────────────────────────────────────────

class TestRemoveAlias:
    def test_remove_alias(self, mg):
        mg.register_alias("Alice Wang", "Alice")
        assert mg.remove_alias("Alice") is True
        assert mg.resolve_alias("Alice") is None

    def test_remove_nonexistent_alias(self, mg):
        assert mg.remove_alias("Ghost") is False

    def test_remove_one_of_many(self, mg):
        mg.register_alias("Alice Wang", "Alice")
        mg.register_alias("Alice Wang", "AW")
        mg.remove_alias("Alice")
        assert mg.resolve_alias("Alice") is None
        assert mg.resolve_alias("AW") == "Alice Wang"


# ── suggest_duplicates (fuzzy matching) ────────────────────────────────────────

class TestSuggestDuplicates:
    def test_exact_match(self, mg):
        """Two nodes with identical labels are flagged."""
        mg.add("Alice Wang", kind="person")
        dupes = mg.suggest_duplicates()
        assert len(dupes) >= 1
        labels = [d["canonical"] for d in dupes]
        assert "Alice Wang" in labels

    def test_case_variant(self, mg):
        """Case-only differences are flagged."""
        mg.add("alice wang", kind="person")
        dupes = mg.suggest_duplicates()
        matched = [d for d in dupes if d["canonical"].lower() == "alice wang"]
        assert len(matched) >= 1

    def test_no_false_positive(self, mg):
        """Different labels are not flagged."""
        dupes = mg.suggest_duplicates()
        canonical_labels = [d["canonical"] for d in dupes]
        assert "Bob Li" not in canonical_labels

    def test_whitespace_variant(self, mg):
        """Whitespace-padded variants are flagged."""
        mg.add("  Alice Wang  ", kind="person")
        dupes = mg.suggest_duplicates()
        assert any(d["canonical"].strip() == "Alice Wang" for d in dupes)

    def test_kind_filtered(self, mg):
        """Only same-kind nodes are compared."""
        mg.add("Alice Wang", kind="project")
        # Different kind, should not be flagged as duplicate of person Alice
        dupes = mg.suggest_duplicates()
        for d in dupes:
            if d["canonical"] == "Alice Wang":
                assert d["kind"] == d.get("duplicate_kind")

    def test_empty_graph(self):
        g = MemoryGraph()
        assert g.suggest_duplicates() == []


# ── merge_entities ─────────────────────────────────────────────────────────────

class TestMergeEntities:
    def test_merge_basic(self, mg):
        """Merge a duplicate node into canonical."""
        dup = mg.add("Alice Wang", kind="person")
        mg.link(dup.id, mg._bob_id, "colleague")
        mg.link(mg._proj_id, dup.id, "member")
        # Merge dup → alice
        merged = mg.merge_entities(dup.id, mg._alice_id)
        assert merged is True
        # dup should be gone
        assert mg.get_node(dup.id) is None
        # Edges should be redirected
        edges = mg.edges_of(mg._alice_id)
        targets = {e.target for e in edges}
        assert mg._bob_id in targets
        sources = {e.source for e in edges}
        assert mg._proj_id in sources

    def test_merge_nonexistent_source(self, mg):
        assert mg.merge_entities("ghost", mg._alice_id) is False

    def test_merge_nonexistent_target(self, mg):
        assert mg.merge_entities(mg._alice_id, "ghost") is False

    def test_preserves_data(self, mg):
        """Merged node's data is merged into canonical."""
        dup = mg.add("Alice Wang", kind="person")
        mg.update_node(dup.id, data={"skill": "python"})
        mg.update_node(mg._alice_id, data={"skill": "rust", "level": "senior"})
        mg.merge_entities(dup.id, mg._alice_id)
        node = mg.get_node(mg._alice_id)
        # Canonical data takes precedence, but new keys are added
        assert node.data["skill"] == "rust"  # canonical wins
        assert node.data["level"] == "senior"

    def test_merge_self_is_noop(self, mg):
        assert mg.merge_entities(mg._alice_id, mg._alice_id) is True


# ── resolve_or_add (convenience) ───────────────────────────────────────────────

class TestResolveOrAdd:
    def test_resolves_existing_alias(self, mg):
        """If alias exists, returns canonical node without creating new."""
        mg.register_alias("Alice Wang", "Alice")
        node = mg.resolve_or_add("Alice", kind="person")
        assert node.label == "Alice Wang"

    def test_creates_new_if_no_alias(self, mg):
        """No alias found → create new node."""
        node = mg.resolve_or_add("Charlie", kind="person")
        assert node is not None
        assert node.label == "Charlie"

    def test_case_insensitive_resolution(self, mg):
        mg.register_alias("Alice Wang", "Alice")
        node = mg.resolve_or_add("alice", kind="person")
        assert node.label == "Alice Wang"


# ── auto_resolve_check ─────────────────────────────────────────────────────────

class TestAutoResolveCheck:
    def test_no_duplicates(self, mg):
        """Clean graph returns empty report."""
        report = mg.auto_resolve_check()
        assert report["duplicates_found"] == 0
        assert report["suggestions"] == []

    def test_with_duplicates(self, mg):
        mg.add("Alice Wang", kind="person")
        report = mg.auto_resolve_check()
        assert report["duplicates_found"] >= 1
        assert len(report["suggestions"]) >= 1
        suggestion = report["suggestions"][0]
        assert "canonical" in suggestion
        assert "duplicates" in suggestion
        assert "recommended_action" in report

    def test_includes_alias_count(self, mg):
        """Report includes alias coverage stats."""
        mg.register_alias("Alice Wang", "Alice")
        report = mg.auto_resolve_check()
        assert "total_aliases" in report
        assert report["total_aliases"] == 1
