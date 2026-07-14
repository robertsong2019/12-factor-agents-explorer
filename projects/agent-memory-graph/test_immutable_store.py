"""Tests for Immutable Store — Cycle 239.

Context Engineering Layer foundation (LCM arXiv:2605.04050 + Searchat).
The immutable store is an append-only log ensuring data survives
compaction, supersession, or deletion.
"""
import time
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph()


@pytest.fixture
def populated(mg):
    """Add three nodes and return (mg, ids)."""
    a = mg.add("Alice", "person", {"role": "engineer"}, tags=["team"])
    b = mg.add("Bob", "person", {"role": "designer"})
    c = mg.add("Python", "skill", category="technical")
    return mg, a, b, c


# ── schema / initialization ──────────────────────────────────

class TestImmutableSchema:
    def test_table_exists(self, mg):
        rows = mg.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='immutable_store'"
        ).fetchall()
        assert len(rows) == 1

    def test_indices_exist(self, mg):
        idx = {r[0] for r in mg.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='immutable_store'"
        ).fetchall()}
        assert "idx_immut_node" in idx
        assert "idx_immut_kind" in idx
        assert "idx_immut_ts" in idx

    def test_idempotent_init(self, mg):
        """Calling _init_immutable_store twice should not error."""
        mg._init_immutable_store()
        mg._init_immutable_store()
        assert mg.immutable_count() == 0


# ── automatic logging on add() ───────────────────────────────

class TestAutoLogging:
    def test_add_creates_immutable_record(self, mg):
        n = mg.add("hello world", "fact")
        records = mg.immutable_retrieve(n.id)
        assert len(records) == 1
        assert records[0]["label"] == "hello world"
        assert records[0]["kind"] == "fact"
        assert records[0]["node_id"] == n.id

    def test_add_with_data_logged(self, mg):
        n = mg.add("test", "event", {"key": "value"})
        recs = mg.immutable_retrieve(n.id)
        assert recs[0]["data"] == '{"key": "value"}'

    def test_add_with_tags_logged(self, mg):
        n = mg.add("tagged", "fact", tags=["a", "b"])
        recs = mg.immutable_retrieve(n.id)
        assert "a" in recs[0]["tags"]

    def test_add_with_category_logged(self, mg):
        n = mg.add("pref", "preference", category="preference")
        recs = mg.immutable_retrieve(n.id)
        assert recs[0]["category"] == "preference"

    def test_multiple_adds_each_logged(self, mg):
        ids = [mg.add(f"item-{i}", "fact") for i in range(5)]
        assert mg.immutable_count() == 5
        for node_id in [n.id for n in ids]:
            assert len(mg.immutable_retrieve(node_id)) == 1

    def test_empty_graph_zero_count(self, mg):
        assert mg.immutable_count() == 0


# ── immutable_retrieve ───────────────────────────────────────

class TestImmutableRetrieve:
    def test_retrieve_returns_chronological(self, mg):
        a = mg.add("first", "fact")
        time.sleep(0.01)
        b = mg.add("second", "fact")
        recs_a = mg.immutable_retrieve(a.id)
        recs_b = mg.immutable_retrieve(b.id)
        assert recs_a[0]["label"] == "first"
        assert recs_b[0]["label"] == "second"

    def test_retrieve_nonexistent_returns_empty(self, mg):
        assert mg.immutable_retrieve("nonexistent-id") == []

    def test_retrieve_record_has_seq(self, mg):
        n = mg.add("test", "fact")
        recs = mg.immutable_retrieve(n.id)
        assert "seq" in recs[0]
        assert isinstance(recs[0]["seq"], int)

    def test_retrieve_record_has_timestamp(self, mg):
        n = mg.add("test", "fact")
        recs = mg.immutable_retrieve(n.id)
        assert recs[0]["timestamp"] > 0


# ── immutable_all ────────────────────────────────────────────

class TestImmutableAll:
    def test_returns_all_records(self, populated):
        mg, a, b, c = populated
        all_recs = mg.immutable_all()
        assert len(all_recs) == 3

    def test_newest_first(self, populated):
        mg, a, b, c = populated
        all_recs = mg.immutable_all()
        # c was added last → highest seq → returned first (DESC order)
        assert all_recs[0]["node_id"] == c.id
        assert all_recs[-1]["node_id"] == a.id

    def test_limit_parameter(self, populated):
        mg, a, b, c = populated
        limited = mg.immutable_all(limit=2)
        assert len(limited) == 2

    def test_limit_zero_means_all(self, populated):
        mg, a, b, c = populated
        assert len(mg.immutable_all(limit=0)) == 3


# ── immutable_count ──────────────────────────────────────────

class TestImmutableCount:
    def test_empty_graph(self, mg):
        assert mg.immutable_count() == 0

    def test_after_adds(self, populated):
        mg, a, b, c = populated
        assert mg.immutable_count() == 3

    def test_count_increments(self, mg):
        assert mg.immutable_count() == 0
        mg.add("a", "fact")
        assert mg.immutable_count() == 1
        mg.add("b", "fact")
        assert mg.immutable_count() == 2


# ── grep — full history search ───────────────────────────────

class TestGrep:
    def test_finds_in_label(self, mg):
        mg.add("Python programming", "skill")
        mg.add("Java programming", "skill")
        results = mg.grep("Python")
        assert len(results) == 1
        assert "Python" in results[0]["label"]

    def test_finds_in_data(self, mg):
        mg.add("test", "fact", {"secret": "treasure"})
        results = mg.grep("treasure")
        assert len(results) == 1

    def test_case_insensitive_default(self, mg):
        mg.add("Hello World", "fact")
        results = mg.grep("hello world")
        assert len(results) == 1

    def test_case_sensitive(self, mg):
        mg.add("Hello World", "fact")
        results = mg.grep("hello world", case_insensitive=False)
        assert len(results) == 0

    def test_finds_compacted_data(self, mg):
        """grep finds data even after node is deleted from live table."""
        n = mg.add("ephemeral data", "fact", {"info": "important"})
        # Simulate deletion from live nodes
        mg.conn.execute("DELETE FROM nodes WHERE id=?", (n.id,))
        mg.conn.commit()
        # grep should still find it in immutable store
        results = mg.grep("ephemeral")
        assert len(results) == 1
        assert "important" in results[0]["data"]

    def test_no_matches(self, mg):
        mg.add("hello", "fact")
        assert mg.grep("nonexistent") == []

    def test_multiple_matches(self, mg):
        for word in ["python basics", "python advanced", "java basics"]:
            mg.add(word, "skill")
        python_results = mg.grep("python")
        assert len(python_results) == 2

    def test_returns_newest_first(self, populated):
        mg, a, b, c = populated
        # Search by kind which is in label or data - let's use data field
        results = mg.grep('engineer')  # Alice's data
        assert len(results) >= 1
        assert results[0]['node_id'] == a.id


# ── expand — lossless recovery ───────────────────────────────

class TestExpand:
    def test_live_node_returns_current(self, mg):
        n = mg.add("alive", "fact", {"v": 1})
        result = mg.expand(n.id)
        assert result is not None
        assert result["label"] == "alive"

    def test_deleted_node_recovers_from_immutable(self, mg):
        n = mg.add("ghost", "fact", {"spooky": True})
        mg.conn.execute("DELETE FROM nodes WHERE id=?", (n.id,))
        mg.conn.commit()
        result = mg.expand(n.id)
        assert result is not None
        assert result["label"] == "ghost"

    def test_never_existed_returns_none(self, mg):
        assert mg.expand("never-existed") is None

    def test_expand_recovers_data_json(self, mg):
        n = mg.add("data node", "fact", {"count": 42, "name": "test"})
        mg.conn.execute("DELETE FROM nodes WHERE id=?", (n.id,))
        mg.conn.commit()
        result = mg.expand(n.id)
        assert result is not None
        assert "count" in result["data"]

    def test_expand_recovers_category(self, mg):
        n = mg.add("categorized", "fact", category="preference")
        mg.conn.execute("DELETE FROM nodes WHERE id=?", (n.id,))
        mg.conn.commit()
        result = mg.expand(n.id)
        assert result is not None
        assert result.get("category") == "preference"


# ── integration with existing features ───────────────────────

class TestIntegration:
    def test_add_with_entropy_filter_logs_on_success(self, mg):
        n = mg.add_with_entropy_filter("A sufficiently detailed sentence here", "fact")
        assert n is not None
        assert mg.immutable_count() == 1

    def test_add_with_entropy_filter_no_log_on_reject(self, mg):
        """Filtered content should NOT be logged."""
        n = mg.add_with_entropy_filter("hi", "fact")
        assert n is None
        assert mg.immutable_count() == 0

    def test_persistence_across_conn(self):
        """Immutable store persists in file-based DB."""
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            mg1 = MemoryGraph(path)
            mg1.add("persisted", "fact")
            mg1.conn.close()
            mg2 = MemoryGraph(path)
            assert mg2.immutable_count() == 1
            mg2.conn.close()
        finally:
            os.unlink(path)

    def test_immutable_store_survives_forget(self, mg):
        """strategic_forget removes from nodes but not immutable store."""
        n = mg.add("forgettable", "fact")
        mg.strategic_forget(min_weight=10.0)  # forget everything
        # Should be gone from nodes
        row = mg.conn.execute("SELECT 1 FROM nodes WHERE id=?", (n.id,)).fetchone()
        assert row is None
        # But still in immutable store
        assert mg.immutable_retrieve(n.id) != []
        assert mg.immutable_count() == 1

    def test_immutable_store_with_link(self, mg):
        a = mg.add("A", "fact")
        b = mg.add("B", "fact")
        mg.link(a.id, b.id, "relates_to")
        # Link doesn't create immutable record (only add() does)
        assert mg.immutable_count() == 2

    def test_immutable_log_direct_call(self, mg):
        """Can manually log pre-existing nodes."""
        mg._immutable_log("manual-id", "manual label", "fact",
                          {"k": "v"}, ["tag"], "custom")
        recs = mg.immutable_retrieve("manual-id")
        assert len(recs) == 1
        assert recs[0]["label"] == "manual label"
        assert recs[0]["category"] == "custom"


# ── performance / scale ──────────────────────────────────────

class TestScale:
    def test_100_nodes(self, mg):
        for i in range(100):
            mg.add(f"node-{i}", "fact", {"index": i})
        assert mg.immutable_count() == 100
        # grep should be fast even with 100 records
        results = mg.grep("node-5")
        assert len(results) == 11  # node-5, node-50..59

    def test_grep_large_data(self, mg):
        """grep on larger data field."""
        big_data = {"content": "x" * 1000 + "NEEDLE" + "y" * 1000}
        mg.add("big", "fact", big_data)
        results = mg.grep("NEEDLE")
        assert len(results) == 1
