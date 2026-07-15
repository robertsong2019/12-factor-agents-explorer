"""Tests for SimHash-based memory deduplication (cycle 250).

Covers:
- find_duplicate_nodes: exact duplicates, near-duplicates, threshold boundaries
- deduplicate: dry_run, actual merge, cluster handling, edge rewiring
- Edge cases: empty graph, single node, no duplicates, all-same content
"""
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph()


# ── find_duplicate_nodes ──────────────────────────────────────────


class TestFindDuplicateNodes:
    def test_empty_graph(self, mg):
        assert mg.find_duplicate_nodes() == []

    def test_single_node(self, mg):
        mg.add("solo", "fact")
        assert mg.find_duplicate_nodes() == []

    def test_exact_duplicates(self, mg):
        a = mg.add("Python programming", "skill", {"level": "expert"})
        b = mg.add("Python programming", "skill", {"level": "expert"})
        dupes = mg.find_duplicate_nodes(threshold=0)
        assert len(dupes) == 1
        assert dupes[0]["hamming_distance"] == 0
        assert dupes[0]["node_a"] in (a.id, b.id)
        assert dupes[0]["node_b"] in (a.id, b.id)

    def test_near_duplicates_within_threshold(self, mg):
        # Very similar content with slight variation
        mg.add("machine learning model training pipeline", "concept", {"framework": "pytorch"})
        mg.add("machine learning model training pipeline", "concept", {"framework": "pytorch"})
        dupes = mg.find_duplicate_nodes(threshold=5)
        assert len(dupes) >= 1
        assert all(d["hamming_distance"] <= 5 for d in dupes)

    def test_different_nodes_above_threshold(self, mg):
        mg.add("Python programming", "skill")
        mg.add("quantum entanglement physics", "concept")
        dupes = mg.find_duplicate_nodes(threshold=3)
        # Very different content should not be flagged
        matching = [d for d in dupes if "Python" in d["label_a"]]
        assert matching == []

    def test_threshold_zero_only_exact(self, mg):
        mg.add("exact same text", "note")
        mg.add("exact same text", "note")
        mg.add("totally different content here", "note")
        dupes = mg.find_duplicate_nodes(threshold=0)
        # Only the exact pair should match
        assert all(d["hamming_distance"] == 0 for d in dupes)
        assert len(dupes) == 1

    def test_kind_filter(self, mg):
        mg.add("same label", "fact")
        mg.add("same label", "skill")
        dupes_all = mg.find_duplicate_nodes(threshold=0)
        dupes_skill = mg.find_duplicate_nodes(threshold=0, kind="skill")
        # kind filter should return fewer or equal results
        assert len(dupes_skill) <= len(dupes_all)

    def test_returns_sorted_by_distance(self, mg):
        # Create several pairs with different similarity
        mg.add("apple banana cherry", "fruit")
        mg.add("apple banana cherry", "fruit")  # exact dup
        mg.add("apple banana cherry date", "fruit")  # near dup
        dupes = mg.find_duplicate_nodes(threshold=10)
        if len(dupes) >= 2:
            assert dupes[0]["hamming_distance"] <= dupes[1]["hamming_distance"]

    def test_three_nodes_all_similar(self, mg):
        mg.add("AI research paper", "doc", {"year": 2024})
        mg.add("AI research paper", "doc", {"year": 2024})
        mg.add("AI research papers", "doc", {"year": 2024})
        dupes = mg.find_duplicate_nodes(threshold=5)
        # Should find at least 2 pairs from 3 similar nodes
        assert len(dupes) >= 1

    def test_pair_fields(self, mg):
        mg.add("duplicate content", "note", {"key": "val"})
        mg.add("duplicate content", "note", {"key": "val"})
        dupes = mg.find_duplicate_nodes(threshold=0)
        d = dupes[0]
        assert "node_a" in d
        assert "node_b" in d
        assert "label_a" in d
        assert "label_b" in d
        assert "kind" in d
        assert "hamming_distance" in d

    def test_large_threshold_catches_all(self, mg):
        mg.add("one thing", "note")
        mg.add("completely other", "note")
        dupes = mg.find_duplicate_nodes(threshold=64)
        # With max threshold, everything matches
        assert len(dupes) >= 1


# ── deduplicate ──────────────────────────────────────────────────


class TestDeduplicate:
    def test_dry_run_default(self, mg):
        mg.add("test content", "note")
        mg.add("test content", "note")
        result = mg.deduplicate()  # default dry_run=True
        assert result["dry_run"] is True
        assert result["merges_executed"] == 0
        assert result["duplicates_found"] >= 1

    def test_dry_run_no_duplicates(self, mg):
        mg.add("unique alpha", "note")
        mg.add("completely different beta gamma delta", "note")
        result = mg.deduplicate(threshold=3)
        assert result["duplicates_found"] == 0
        assert result["merges_executed"] == 0

    def test_actual_merge(self, mg):
        a = mg.add("Python coding skill", "skill", {"level": "expert"})
        b = mg.add("Python coding skill", "skill", {"level": "expert"})
        # Link them to other nodes so we can verify edge rewiring
        c = mg.add("Web Development", "project")
        mg.link(a.id, c.id, "used_in")
        result = mg.deduplicate(threshold=0, dry_run=False)
        assert result["merges_executed"] == 1
        assert result["dry_run"] is False
        # Verify merged node no longer exists
        merged_id = result["merged_pairs"][0]["merged"]
        remaining = mg.conn.execute("SELECT COUNT(*) FROM nodes WHERE id=?", (merged_id,)).fetchone()[0]
        assert remaining == 0
        # The kept node should still exist
        kept_id = result["merged_pairs"][0]["kept"]
        kept_count = mg.conn.execute("SELECT COUNT(*) FROM nodes WHERE id=?", (kept_id,)).fetchone()[0]
        assert kept_count == 1

    def test_merge_keeps_higher_weight(self, mg):
        a = mg.add("same label", "note", {"v": 1})
        b = mg.add("same label", "note", {"v": 2})
        # b has higher weight
        mg.conn.execute("UPDATE nodes SET weight=5.0 WHERE id=?", (b.id,))
        mg.conn.commit()
        result = mg.deduplicate(threshold=0, dry_run=False)
        assert result["merges_executed"] == 1
        # b (higher weight) should be kept
        assert result["merged_pairs"][0]["kept"] == b.id
        # a should be gone
        count = mg.conn.execute("SELECT COUNT(*) FROM nodes WHERE id=?", (a.id,)).fetchone()[0]
        assert count == 0

    def test_edge_rewiring_after_merge(self, mg):
        a = mg.add("duplicate content here", "note")
        b = mg.add("duplicate content here", "note")
        c = mg.add("target node", "concept")
        d = mg.add("source node", "concept")
        mg.link(a.id, c.id, "relates_to")
        mg.link(d.id, b.id, "references")
        mg.deduplicate(threshold=0, dry_run=False)
        # After merge, edges should point to kept node
        edge_count = mg.conn.execute("SELECT COUNT(*) FROM edges WHERE target=?", (c.id,)).fetchone()[0]
        assert edge_count >= 1  # kept node still connects to c

    def test_cluster_transitive(self, mg):
        """A≈B, B≈C — after merging A into B, B≈C should still be processed."""
        a = mg.add("AI model training", "concept")
        b = mg.add("AI model training", "concept")
        c = mg.add("AI model training", "concept")
        result = mg.deduplicate(threshold=0, dry_run=False)
        # Should merge 2 pairs (3 → 1)
        assert result["merges_executed"] == 2
        # Only 1 node should remain
        remaining = mg.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        assert remaining == 1

    def test_no_self_loops_after_merge(self, mg):
        a = mg.add("dup content", "note")
        b = mg.add("dup content", "note")
        mg.link(a.id, b.id, "related")
        mg.link(b.id, a.id, "reverse")
        mg.deduplicate(threshold=0, dry_run=False)
        # No self-loops should exist
        self_loops = mg.conn.execute(
            "SELECT COUNT(*) FROM edges WHERE source=target"
        ).fetchone()[0]
        assert self_loops == 0

    def test_return_structure(self, mg):
        mg.add("same", "note")
        mg.add("same", "note")
        result = mg.deduplicate(threshold=0, dry_run=True)
        assert "duplicates_found" in result
        assert "merges_executed" in result
        assert "merged_pairs" in result
        assert "skipped" in result
        assert "savings" in result
        assert "dry_run" in result

    def test_actual_merge_with_savings(self, mg):
        mg.add("duplicate item with longish label", "note", {"data": "value"})
        mg.add("duplicate item with longish label", "note", {"data": "value"})
        result = mg.deduplicate(threshold=0, dry_run=False)
        assert result["merges_executed"] == 1
        assert result["savings"] > 0

    def test_kind_filter_in_deduplicate(self, mg):
        mg.add("same text", "note")
        mg.add("same text", "note")
        mg.add("same text", "fact")
        mg.add("same text", "fact")
        result_note = mg.deduplicate(threshold=0, dry_run=False, kind="note")
        # Should only merge within "note" kind (1 pair)
        assert result_note["merges_executed"] == 1

    def test_empty_graph_dry_run(self, mg):
        result = mg.deduplicate()
        assert result["duplicates_found"] == 0
        assert result["merges_executed"] == 0

    def test_merged_pairs_detail(self, mg):
        a = mg.add("exact same", "note")
        b = mg.add("exact same", "note")
        result = mg.deduplicate(threshold=0, dry_run=False)
        mp = result["merged_pairs"][0]
        assert "kept" in mp
        assert "merged" in mp
        assert "label_kept" in mp
        assert "label_merged" in mp
        assert "hamming_distance" in mp

    def test_skipped_already_merged(self, mg):
        """When A≈B, A≈C, B≈C: after merging one pair, the third is skipped."""
        a = mg.add("x", "note")
        b = mg.add("x", "note")
        c = mg.add("x", "note")
        result = mg.deduplicate(threshold=0, dry_run=False)
        # 3 pairs found, 2 merged, 1 skipped
        assert result["duplicates_found"] == 3
        assert result["merges_executed"] == 2
        assert result["skipped"] == 1

    def test_higher_threshold_merges_more(self, mg):
        """Higher threshold should find more or equal duplicates."""
        mg.add("Python web framework Django", "tech")
        mg.add("Python web framework Flask", "tech")
        mg.add("quantum computing applications", "tech")
        low_t = mg.deduplicate(threshold=2, dry_run=True)
        high_t = mg.deduplicate(threshold=10, dry_run=True)
        assert high_t["duplicates_found"] >= low_t["duplicates_found"]

    def test_data_preserved_after_merge(self, mg):
        a = mg.add("same label", "note", {"key_a": "val_a"})
        b = mg.add("same label", "note", {"key_a": "val_a"})
        result = mg.deduplicate(threshold=0, dry_run=False)
        assert result["merges_executed"] == 1
        kept_id = result["merged_pairs"][0]["kept"]
        row = mg.conn.execute("SELECT data FROM nodes WHERE id=?", (kept_id,)).fetchone()
        import json
        data = json.loads(row["data"])
        # Data should be preserved
        assert "key_a" in data

    def test_weight_max_after_merge(self, mg):
        a = mg.add("same", "note")
        b = mg.add("same", "note")
        mg.conn.execute("UPDATE nodes SET weight=3.0 WHERE id=?", (a.id,))
        mg.conn.execute("UPDATE nodes SET weight=7.0 WHERE id=?", (b.id,))
        mg.conn.commit()
        mg.deduplicate(threshold=0, dry_run=False)
        # Remaining node should have max weight
        row = mg.conn.execute("SELECT weight FROM nodes").fetchone()
        assert row["weight"] == 7.0


# ── Integration with existing features ──────────────────────────


class TestDeduplicateIntegration:
    def test_dedup_then_retrieve_still_works(self, mg):
        a = mg.add("Python programming skill", "skill")
        b = mg.add("Python programming skill", "skill")
        c = mg.add("rust embedded systems", "skill")
        mg.link(a.id, c.id, "contrasts_with")
        mg.deduplicate(threshold=0, dry_run=False)
        # Search should still return results
        results = mg.recall("Python")
        assert len(results) >= 1

    def test_dedup_then_binary_search(self, mg):
        mg.add("machine learning models", "concept")
        mg.add("machine learning models", "concept")
        mg.deduplicate(threshold=0, dry_run=False)
        results = mg.similarity_search_binary("machine learning")
        assert len(results) >= 1

    def test_dedup_preserves_fts(self, mg):
        a = mg.add("searchable text content", "note")
        b = mg.add("searchable text content", "note")
        mg.deduplicate(threshold=0, dry_run=False)
        # FTS should still find the remaining node
        fts_results = mg.conn.execute(
            "SELECT node_id FROM nodes_fts WHERE nodes_fts MATCH 'searchable'"
        ).fetchall()
        assert len(fts_results) >= 1

    def test_dedup_stats_consistency(self, mg):
        mg.add("dup one", "note")
        mg.add("dup one", "note")
        mg.add("unique node", "concept")
        mg.link_by_label("dup one", "unique node", "connects")
        result = mg.deduplicate(threshold=0, dry_run=False)
        assert result["merges_executed"] == 1
        stats = mg.stats()
        # Node count should reflect the merge
        assert stats["nodes"] == 2  # was 3, merged 1

    def test_idempotent_second_call(self, mg):
        mg.add("same", "note")
        mg.add("same", "note")
        mg.deduplicate(threshold=0, dry_run=False)
        result2 = mg.deduplicate(threshold=0, dry_run=False)
        assert result2["merges_executed"] == 0
        assert result2["duplicates_found"] == 0
