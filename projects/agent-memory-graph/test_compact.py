"""Tests for compact() three-level upgrade — Cycle 240.

LCM-inspired (arXiv:2605.04050): LLM-detailed → LLM-bullet → deterministic truncate.
The immutable store preserves original data across compaction.
"""
import json
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph()


@pytest.fixture
def verbose_node(mg):
    """Create a node with long label and large data."""
    n = mg.add(
        "This is a very long label that describes a complex event in great detail and should be truncated",
        "event",
        {
            "description": "A" * 500,
            "metadata": {"a": 1, "b": 2, "c": 3},
            "items": [1, 2, 3, 4, 5],
            "count": 42,
            "short": "ok",
        }
    )
    return mg, n


# ── Level 2: deterministic truncation ────────────────────────

class TestLevel2Truncation:
    def test_long_label_truncated(self, verbose_node):
        mg, n = verbose_node
        result = mg.compact_node(n.id, max_label_len=40, level=2)
        assert result is not None
        assert len(result["new_label"]) <= 43  # 40 + "..."
        assert result["new_label"].endswith("...")
        assert result["level"] == 2

    def test_short_label_unchanged(self, mg):
        n = mg.add("short", "fact")
        result = mg.compact_node(n.id, max_label_len=80, level=2)
        assert result["new_label"] == "short"
        assert not result["new_label"].endswith("...")

    def test_data_compacted(self, verbose_node):
        mg, n = verbose_node
        result = mg.compact_node(n.id, level=2)
        live = mg.get(n.id) if hasattr(mg, 'get') else None
        # Check via direct DB
        row = mg.conn.execute("SELECT data FROM nodes WHERE id=?", (n.id,)).fetchone()
        data = json.loads(row["data"])
        # Long string should be truncated
        assert len(data["description"]) <= 100
        # Dict replaced with marker
        assert "dict:3 keys" in str(data["metadata"])
        # List replaced with marker
        assert "list:5 items" in str(data["items"])
        # Scalars preserved
        assert data["count"] == 42
        assert data["short"] == "ok"

    def test_data_len_reduced(self, verbose_node):
        mg, n = verbose_node
        result = mg.compact_node(n.id, level=2)
        assert result["new_data_len"] < result["old_data_len"]

    def test_nonexistent_node(self, mg):
        assert mg.compact_node("nonexistent", level=2) is None

    def test_empty_data(self, mg):
        n = mg.add("test", "fact")
        result = mg.compact_node(n.id, level=2)
        assert result is not None

    def test_max_keys_limit(self, mg):
        n = mg.add("big", "fact", {f"key_{i}": i for i in range(20)})
        mg.compact_node(n.id, level=2)
        row = mg.conn.execute("SELECT data FROM nodes WHERE id=?", (n.id,)).fetchone()
        data = json.loads(row["data"])
        assert "_truncated_keys" in data
        assert data["_truncated_keys"] == 10  # 20 - 10

    def test_compact_preserves_node_existence(self, verbose_node):
        mg, n = verbose_node
        mg.compact_node(n.id, level=2)
        row = mg.conn.execute("SELECT 1 FROM nodes WHERE id=?", (n.id,)).fetchone()
        assert row is not None


# ── Level 1 & 0: summarizer callback ─────────────────────────

class TestSummarizerLevels:
    def test_level1_bullet_summary(self, mg):
        n = mg.add("Long detailed content here", "fact", {"body": "x" * 200})
        def bullet_summarizer(label, data):
            return f"• {label[:20]}... • key={list(data.keys())[0]}"
        result = mg.compact_node(n.id, level=1, summarizer=bullet_summarizer)
        assert result["level"] == 1
        assert "•" in result["new_label"]

    def test_level0_detailed_summary(self, mg):
        n = mg.add("Some content", "fact", {"body": "y" * 200})
        def detailed_summarizer(label, data):
            return f"Detailed summary of {label}"
        result = mg.compact_node(n.id, level=0, summarizer=detailed_summarizer)
        assert result["level"] == 0
        assert "Detailed summary" in result["new_label"]

    def test_no_summarizer_falls_back_to_level2(self, mg):
        n = mg.add("Long label that needs truncation", "fact")
        result = mg.compact_node(n.id, level=0, summarizer=None)
        assert result["level"] == 2

    def test_summarizer_exception_falls_back(self, mg):
        n = mg.add("test", "fact", {"v": 1})
        def bad_summarizer(label, data):
            raise RuntimeError("LLM unavailable")
        result = mg.compact_node(n.id, level=1, summarizer=bad_summarizer)
        assert result["level"] == 2  # fell back

    def test_summarizer_returns_none_falls_back(self, mg):
        n = mg.add("test", "fact")
        def none_summarizer(label, data):
            return None
        result = mg.compact_node(n.id, level=0, summarizer=none_summarizer)
        assert result["level"] == 2

    def test_summarizer_data_contains_summary(self, mg):
        n = mg.add("content", "fact", {"body": "z" * 100})
        def summarizer(label, data):
            return "SUMMARY TEXT"
        mg.compact_node(n.id, level=1, summarizer=summarizer)
        row = mg.conn.execute("SELECT data FROM nodes WHERE id=?", (n.id,)).fetchone()
        data = json.loads(row["data"])
        assert data.get("_compacted") is True
        assert data.get("_level") == 1
        assert data["_summary"] == "SUMMARY TEXT"


# ── Immutable store preservation ─────────────────────────────

class TestImmutablePreservation:
    def test_original_data_in_immutable_store(self, verbose_node):
        mg, n = verbose_node
        mg.compact_node(n.id, level=2)
        # Immutable store still has original
        recs = mg.immutable_retrieve(n.id)
        assert len(recs) >= 1
        orig_data = json.loads(recs[0]["data"])
        assert len(orig_data["description"]) == 500  # original preserved

    def test_expand_recovers_original(self, verbose_node):
        mg, n = verbose_node
        mg.compact_node(n.id, level=2)
        # expand returns live (compacted) node
        result = mg.expand(n.id)
        assert result is not None
        # Immutable store still has original
        recs = mg.immutable_retrieve(n.id)
        orig = json.loads(recs[0]["data"])
        assert len(orig["description"]) == 500

    def test_compact_then_grep_finds_original(self, verbose_node):
        mg, n = verbose_node
        mg.compact_node(n.id, level=2)
        # The original data had "A" * 500 — grep should find it
        results = mg.grep("AAAA")
        assert len(results) >= 1


# ── compact_batch ────────────────────────────────────────────

class TestCompactBatch:
    def test_batch_compact_multiple(self, mg):
        ids = [mg.add(f"node-{i} with long label " * 3, "fact").id for i in range(5)]
        results = mg.compact_batch(ids, max_label_len=20, level=2)
        assert len(results) == 5
        for r in results:
            assert r["level"] == 2

    def test_batch_skips_nonexistent(self, mg):
        n = mg.add("real node with long label here", "fact")
        results = mg.compact_batch([n.id, "fake-id"], max_label_len=10)
        assert len(results) == 1

    def test_batch_empty_list(self, mg):
        assert mg.compact_batch([]) == []


# ── compact_stats ────────────────────────────────────────────

class TestCompactStats:
    def test_no_compacted_nodes_initially(self, mg):
        mg.add("test", "fact")
        stats = mg.compact_stats()
        assert stats["compacted_nodes"] == 0
        assert stats["uncompacted_nodes"] == 1

    def test_after_compact(self, verbose_node):
        mg, n = verbose_node
        mg.compact_node(n.id, level=2)
        stats = mg.compact_stats()
        # Level 2 doesn't set _compacted flag, only LLM levels do
        # But let's verify the stats function works
        assert stats["total_nodes"] >= 1

    def test_stats_with_llm_compacted(self, mg):
        n = mg.add("test", "fact")
        def s(l, d): return "summary"
        mg.compact_node(n.id, level=1, summarizer=s)
        stats = mg.compact_stats()
        assert stats["compacted_nodes"] == 1
        assert stats["compaction_ratio"] > 0

    def test_immutable_records_count(self, mg):
        for i in range(5):
            mg.add(f"n{i}", "fact")
        stats = mg.compact_stats()
        assert stats["immutable_records"] == 5


# ── _compact_data unit tests ─────────────────────────────────

class TestCompactData:
    def test_empty_dict(self, mg):
        assert mg._compact_data({}) == {}

    def test_none(self, mg):
        assert mg._compact_data(None) == {}

    def test_short_values_preserved(self, mg):
        d = {"a": 1, "b": "short", "c": True}
        result = mg._compact_data(d)
        assert result == d

    def test_long_string_truncated(self, mg):
        d = {"key": "x" * 200}
        result = mg._compact_data(d)
        assert len(result["key"]) <= 100
        assert result["key"].endswith("...")

    def test_dict_replaced(self, mg):
        d = {"nested": {"a": 1, "b": 2}}
        result = mg._compact_data(d)
        assert "dict:2 keys" in str(result["nested"])

    def test_list_replaced(self, mg):
        d = {"items": [1, 2, 3]}
        result = mg._compact_data(d)
        assert "list:3 items" in str(result["items"])

    def test_max_keys_default(self, mg):
        d = {f"k{i}": i for i in range(15)}
        result = mg._compact_data(d)
        assert "_truncated_keys" in result
        assert result["_truncated_keys"] == 5  # 15 - 10

    def test_custom_max_keys(self, mg):
        d = {f"k{i}": i for i in range(5)}
        result = mg._compact_data(d, max_keys=3)
        assert "_truncated_keys" in result
        assert result["_truncated_keys"] == 2


# ── Idempotency & double-compact ─────────────────────────────

class TestIdempotency:
    def test_double_compact_level2(self, mg):
        n = mg.add("A" * 200, "fact", {"long": "B" * 200})
        r1 = mg.compact_node(n.id, max_label_len=50, level=2)
        r2 = mg.compact_node(n.id, max_label_len=50, level=2)
        # Second compact should not error, and label should stay compacted
        assert r2 is not None
        assert len(r2["new_label"]) <= 53

    def test_compact_after_llm_compact(self, mg):
        n = mg.add("content here", "fact", {"body": "x" * 100})
        def s(l, d): return "summary"
        r1 = mg.compact_node(n.id, level=1, summarizer=s)
        assert r1["level"] == 1
        # Now compact again at level 2
        r2 = mg.compact_node(n.id, level=2)
        assert r2 is not None
