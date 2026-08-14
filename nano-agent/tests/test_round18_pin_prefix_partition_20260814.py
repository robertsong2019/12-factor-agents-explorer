"""
Round 18 (2026-08-14): F61 pin system, F62 search_prefix, F63 partition.

F61: Memory.pin/unpin/is_pinned/pinned + eviction protection in resize() & forget()
F62: Memory.search_prefix(prefix, limit) — case-insensitive content prefix scan
F63: Memory.partition(predicate) — split into two functional Memory instances
"""

import pytest
from src.nano_agent.memory import Memory, MemoryEntry


class TestF61Pin:
    """F61: pin system — eviction protection."""

    def test_pin_marks_entry(self):
        m = Memory()
        m.add("important fact")
        assert m.pin(0) is True
        assert m.is_pinned(0) is True

    def test_pin_out_of_range(self):
        m = Memory()
        m.add("only")
        assert m.pin(5) is False
        assert m.pin(-1) is False

    def test_unpin_removes_flag(self):
        m = Memory()
        m.add("temp")
        m.pin(0)
        assert m.unpin(0) is True
        assert m.is_pinned(0) is False

    def test_unpin_unpinned_is_noop_true(self):
        m = Memory()
        m.add("never pinned")
        assert m.unpin(0) is True
        assert m.is_pinned(0) is False

    def test_unpin_out_of_range(self):
        m = Memory()
        m.add("x")
        assert m.unpin(99) is False

    def test_is_pinned_out_of_range_false(self):
        m = Memory()
        assert m.is_pinned(0) is False

    def test_pinned_lists_indices_in_order(self):
        m = Memory()
        m.add("a"); m.add("b"); m.add("c"); m.add("d")
        m.pin(3); m.pin(1)
        assert m.pinned() == [1, 3]

    def test_pinned_empty_when_none(self):
        m = Memory()
        m.add("x")
        assert m.pinned() == []

    def test_pin_survives_export_import(self):
        m = Memory()
        m.add("pinned content", importance=0.9)
        m.pin(0)
        m2 = Memory()
        m2.import_json(m.export_json())
        assert m2.is_pinned(0) is True

    def test_pin_survives_snapshot_restore(self):
        m = Memory()
        m.add("snapshot me")
        m.pin(0)
        snap = m.snapshot()
        m2 = Memory()
        m2.restore(snap)
        assert m2.is_pinned(0) is True


class TestF61EvictionProtection:
    """F61: pinned entries survive resize() and forget()."""

    def test_forget_skips_pinned(self):
        m = Memory()
        m.add("low a", importance=0.1)
        m.add("low b", importance=0.2)
        m.add("low c", importance=0.1)
        m.pin(0)  # pin the lowest-importance entry
        removed = m.forget(threshold=0.15)
        assert removed == 1  # only "low c" removed
        assert m.count() == 2
        assert "low a" in [e.content for e in m.get_all()]

    def test_forget_all_low_but_one_pinned(self):
        m = Memory()
        m.add("only entry", importance=0.05)
        m.pin(0)
        assert m.forget(threshold=0.5) == 0
        assert m.count() == 1

    def test_resize_oldest_skips_pinned(self):
        m = Memory()
        for i in range(5):
            m.add(f"entry {i}", importance=0.5)
        m.pin(0)  # pin the oldest
        result = m.resize(max_size=3, strategy="oldest")
        assert result["removed_count"] == 2
        assert result["remaining_count"] == 3
        assert result["pinned_count"] == 1
        contents = [e.content for e in m.get_all()]
        assert "entry 0" in contents  # pinned oldest survived
        assert "entry 1" not in contents  # next-oldest evicted instead

    def test_resize_least_important_skips_pinned(self):
        m = Memory()
        m.add("lowest", importance=0.1)
        m.add("mid", importance=0.5)
        m.add("high", importance=0.9)
        m.add("second low", importance=0.2)
        m.pin(0)  # pin the least important
        result = m.resize(max_size=2, strategy="least_important")
        assert result["removed_count"] == 2
        contents = [e.content for e in m.get_all()]
        assert "lowest" in contents
        assert "second low" not in contents

    def test_resize_all_pinned_removes_nothing(self):
        m = Memory()
        for i in range(3):
            m.add(f"p{i}")
            m.pin(i)
        result = m.resize(max_size=1, strategy="oldest")
        assert result["removed_count"] == 0
        assert result["remaining_count"] == 3

    def test_resize_random_respects_pins(self):
        m = Memory()
        for i in range(10):
            m.add(f"e{i}")
        m.pin(4)
        for _ in range(20):  # random strategy, repeated for coverage
            result = m.resize(max_size=5, strategy="random")
        assert "e4" in [e.content for e in m.get_all()]
        assert result["pinned_count"] == 1

    def test_resize_no_change_when_under_limit(self):
        m = Memory()
        m.add("one"); m.add("two")
        result = m.resize(max_size=10, strategy="oldest")
        assert result["removed_count"] == 0
        assert result["remaining_count"] == 2
        assert result["pinned_count"] == 0

    def test_unpin_restores_eviction(self):
        m = Memory()
        m.add("old", importance=0.1)
        m.add("new", importance=0.9)
        m.pin(0)
        m.unpin(0)
        removed = m.forget(threshold=0.5)
        assert removed == 1
        assert m.count() == 1


class TestF62SearchPrefix:
    """F62: search_prefix — case-insensitive prefix scan."""

    def test_basic_prefix_match(self):
        m = Memory()
        m.add("TODO: write tests")
        m.add("FIXME: broken")
        m.add("note to self")
        results = m.search_prefix("todo")
        assert len(results) == 1
        assert results[0].content == "TODO: write tests"

    def test_case_insensitive(self):
        m = Memory()
        m.add("Alpha command")
        assert len(m.search_prefix("ALPHA")) == 1

    def test_no_midstring_match(self):
        m = Memory()
        m.add("the TODO is buried")
        assert m.search_prefix("todo") == []

    def test_multiple_matches_order_and_limit(self):
        m = Memory()
        for i in range(6):
            m.add(f"ERROR {i}: failure")
        recent = m.search_prefix("error", limit=2)
        assert [e.content for e in recent] == ["ERROR 4: failure", "ERROR 5: failure"]
        assert len(m.search_prefix("error", limit=0)) == 6

    def test_empty_prefix_returns_empty(self):
        m = Memory()
        m.add("anything")
        assert m.search_prefix("") == []

    def test_prefix_on_empty_memory(self):
        assert Memory().search_prefix("x") == []

    def test_prefix_longer_than_content(self):
        m = Memory()
        m.add("ab")
        assert m.search_prefix("abc") == []


class TestF63Partition:
    """F63: partition — predicate split into two Memory instances."""

    def test_basic_split(self):
        m = Memory()
        m.add("python note", tags=["lang"])
        m.add("rust note", tags=["lang"])
        m.add("grocery list", tags=["errand"])
        hi, rest = m.partition(lambda e: "lang" in e.tags)
        assert hi.count() == 2
        assert rest.count() == 1
        assert "grocery list" in [e.content for e in rest.get_all()]

    def test_both_halves_are_functional_memory(self):
        m = Memory()
        m.add("alpha"); m.add("beta"); m.add("gamma")
        hi, rest = m.partition(lambda e: e.content.startswith("a"))
        # halves support further chained operations
        assert hi.search("alpha") != []
        assert rest.top_important(5) != []
        sub_hi, sub_rest = hi.partition(lambda e: True)
        assert sub_hi.count() == 1 and sub_rest.count() == 0

    def test_original_untouched(self):
        m = Memory()
        m.add("a"); m.add("b")
        m.partition(lambda e: True)
        assert m.count() == 2

    def test_all_match(self):
        m = Memory()
        m.add("x1"); m.add("x2")
        hi, rest = m.partition(lambda e: e.content.startswith("x"))
        assert hi.count() == 2 and rest.count() == 0

    def test_none_match(self):
        m = Memory()
        m.add("a"); m.add("b")
        hi, rest = m.partition(lambda e: False)
        assert hi.count() == 0 and rest.count() == 2

    def test_empty_memory(self):
        hi, rest = Memory().partition(lambda e: True)
        assert hi.count() == 0 and rest.count() == 0

    def test_non_callable_raises(self):
        m = Memory()
        m.add("x")
        with pytest.raises(TypeError):
            m.partition("not callable")

    def test_entries_preserve_fields(self):
        m = Memory()
        m.add("keep", tags=["t"], importance=0.9)
        m.pin(0)
        hi, _ = m.partition(lambda e: e.content == "keep")
        entry = hi.get_all()[0]
        assert entry.tags == ["t"]
        assert entry.importance == 0.9
        assert entry.metadata.get("_pinned") is True  # F61 flag travels along

    def test_partition_composes_with_resize(self):
        m = Memory()
        for i in range(6):
            m.add(f"item {i}")
        hi, rest = m.partition(lambda e: int(e.content.split()[-1]) < 3)
        hi.resize(max_size=1, strategy="oldest")
        assert hi.count() == 1
        assert rest.count() == 3
