"""F67/F68/F69 — sequence protocol, copy + content_hash, subscribe/unsubscribe.

Round 20 (2026-08-17).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest

from nano_agent.memory import Memory, MemoryEntry


def _mem(*contents, **kw):
    m = Memory(**kw)
    for c in contents:
        m.add(c)
    return m


# ---------------------------------------------------------------- F67: sequence protocol

class TestF67SequenceProtocol:
    def test_len_matches_count(self):
        m = _mem("a", "b", "c")
        assert len(m) == 3 == m.count()

    def test_len_empty(self):
        assert len(Memory()) == 0

    def test_iter_yields_all_entries_in_order(self):
        m = _mem("one", "two", "three")
        assert [e.content for e in m] == ["one", "two", "three"]

    def test_iter_is_snapshot_safe_during_mutation(self):
        m = _mem("a", "b", "c")
        it = iter(m)
        first = next(it)
        m.add("d")  # mutate mid-iteration
        rest = list(it)
        assert first.content == "a"
        assert [e.content for e in rest] == ["b", "c"]  # iterator unaffected

    def test_getitem_int(self):
        m = _mem("alpha", "beta")
        assert m[0].content == "alpha"
        assert m[1].content == "beta"

    def test_getitem_negative_index(self):
        m = _mem("alpha", "beta", "gamma")
        assert m[-1].content == "gamma"
        assert m[-3].content == "alpha"

    def test_getitem_out_of_range_raises(self):
        m = _mem("only")
        with pytest.raises(IndexError):
            _ = m[5]
        with pytest.raises(IndexError):
            _ = m[-2]

    def test_getitem_slice_returns_list(self):
        m = _mem("a", "b", "c", "d")
        sub = m[1:3]
        assert isinstance(sub, list)
        assert [e.content for e in sub] == ["b", "c"]

    def test_getitem_step_and_negative_slice(self):
        m = _mem("a", "b", "c", "d", "e")
        assert [e.content for e in m[::2]] == ["a", "c", "e"]
        assert [e.content for e in m[-2:]] == ["d", "e"]

    def test_getitem_slice_empty_memory(self):
        assert Memory()[0:2] == []

    def test_getitem_type_error_for_non_int(self):
        m = _mem("a")
        with pytest.raises(TypeError):
            _ = m["0"]
        with pytest.raises(TypeError):
            _ = m[1.5]

    def test_contains_memoryentry_content_equality(self):
        m = _mem("hello world")
        assert MemoryEntry(content="hello world") in m
        assert MemoryEntry(content="hello") not in m  # eq is exact content

    def test_contains_str_exact_match(self):
        m = _mem("hello world")
        assert "hello world" in m
        assert "hello" not in m  # exact match, not substring (search() covers that)

    def test_contains_other_types_false(self):
        m = _mem("a")
        assert (123,) not in m
        assert 42 not in m
        assert None not in m

    def test_pythonic_composition(self):
        """len/iter/getitem unlock enumerate, any, comprehensions."""
        m = _mem("task: a", "note: b", "task: c")
        tasks = [e.content for i, e in enumerate(m) if e.content.startswith("task:")]
        assert tasks == ["task: a", "task: c"]
        assert any("note" in e.content for e in m)
        assert sum(1 for _ in m) == 3

    def test_reversed_builtin(self):
        m = _mem("a", "b", "c")
        assert [e.content for e in reversed(list(m)[::-1])] == ["a", "b", "c"]


# ---------------------------------------------------------------- F68: copy + content_hash

class TestF68Copy:
    def test_copy_same_contents_and_length(self):
        m = _mem("a", "b")
        c = m.copy()
        assert len(c) == 2
        assert [e.content for e in c] == ["a", "b"]

    def test_copy_independent_entries(self):
        m = _mem("original")
        c = m.copy()
        c[0].content = "mutated"
        assert m[0].content == "original"  # original untouched

    def test_copy_isolated_from_original_mutations(self):
        m = _mem("a", "b")
        c = m.copy()
        m.remove(0)
        m.add("new")
        assert [e.content for e in c] == ["a", "b"]

    def test_copy_has_no_persistence_path(self):
        m = Memory(persistence_path="/tmp/f68_should_not_exist.json")
        m.add("x")
        c = m.copy()
        assert c.persistence_path is None
        c.add("y")  # must not touch the original's file

    def test_copy_preserves_reserved_metadata(self):
        m = _mem("important")
        m.pin(0)
        m.touch(0)
        m.annotate(0, "keep")
        c = m.copy()
        assert c.is_pinned(0) is True
        assert "_last_accessed" in c[0].metadata
        assert len(c.annotations(0)) == 1

    def test_copy_carries_archived_entries(self):
        m = _mem("a", "b")
        m.archive(0)
        c = m.copy()
        assert len(c.archived()) == 1
        assert c.unarchive(0) is True

    def test_copy_preserves_max_entries(self):
        m = Memory(max_entries=7)
        c = m.copy()
        assert c.max_entries == 7


class TestF68ContentHash:
    def test_hash_is_sha256_hex(self):
        h = _mem("a").content_hash()
        assert len(h) == 64
        int(h, 16)  # valid hex

    def test_hash_deterministic_via_snapshot_restore(self):
        """Full-state fingerprint: identical state (incl. timestamps) → identical hash.
        Two independently-created memories differ (timestamps), but a
        snapshot/restore round-trip reproduces state exactly."""
        a = _mem("x", "y")
        b = Memory()
        assert b.restore(a.snapshot()) == 2
        assert a.content_hash() == b.content_hash()

    def test_independent_creation_differs_due_to_timestamps(self):
        """Timestamps are part of state → separately-built twins hash differently."""
        assert _mem("x").content_hash() != _mem("x").content_hash()

    def test_hash_empty_memory_stable(self):
        assert Memory().content_hash() == Memory().content_hash()

    def test_hash_changes_on_content(self):
        m = _mem("a")
        h1 = m.content_hash()
        m.update(0, "changed")
        assert m.content_hash() != h1

    def test_hash_changes_on_metadata_only(self):
        m = _mem("a")
        h1 = m.content_hash()
        m.merge_metadata(0, {"k": "v"})
        assert m.content_hash() != h1

    def test_hash_changes_on_importance(self):
        m = _mem("a")
        h1 = m.content_hash()
        m.batch_update([{"index": 0, "importance": 0.9}])
        assert m.content_hash() != h1

    def test_hash_order_sensitive(self):
        a = _mem("x", "y")
        b = _mem("y", "x")
        assert a.content_hash() != b.content_hash()

    def test_hash_ignores_archived_by_default(self):
        m = _mem("a", "b")
        m.archive(0)
        h_active = m.content_hash()
        h_arch_before = m.content_hash(include_archived=True)
        m._archived[0].metadata["k"] = "v"  # mutate the archived entry
        assert m.content_hash() == h_active        # default: archived invisible
        assert m.content_hash(include_archived=True) != h_arch_before  # flag sees it

    def test_hash_include_archived_flag(self):
        m = _mem("a", "b")
        h1 = m.content_hash(include_archived=True)
        m.archive(0)
        h2 = m.content_hash(include_archived=True)
        assert h1 != h2

    def test_copy_hash_equality(self):
        m = _mem("a", "b", "c")
        assert m.copy().content_hash() == m.content_hash()


# ---------------------------------------------------------------- F69: subscribe/unsubscribe

class TestF69Subscribe:
    def test_add_event_fires(self):
        m = Memory()
        seen = []
        m.subscribe("add", lambda ev, e, i: seen.append((ev, e.content, i)))
        m.add("hello")
        assert seen == [("add", "hello", 0)]

    def test_remove_event_fires_with_entry_and_index(self):
        m = _mem("a", "b")
        seen = []
        m.subscribe("remove", lambda ev, e, i: seen.append((ev, e.content, i)))
        m.remove(0)
        assert seen == [("remove", "a", 0)]

    def test_update_event_fires(self):
        m = _mem("old")
        seen = []
        m.subscribe("update", lambda ev, e, i: seen.append((e.content, i)))
        m.update(0, "new")
        assert seen == [("new", 0)]

    def test_batch_add_emits_per_entry(self):
        m = Memory()
        seen = []
        m.subscribe("add", lambda ev, e, i: seen.append(e.content))
        m.batch_add([{"content": "x"}, {"content": "y"}])
        assert seen == ["x", "y"]

    def test_batch_remove_emits_per_removed(self):
        m = _mem("a", "b", "c")
        seen = []
        m.subscribe("remove", lambda ev, e, i: seen.append(e.content))
        assert m.batch_remove([0, 2]) == 2
        assert sorted(seen) == ["a", "c"]

    def test_batch_update_emits_per_updated(self):
        m = _mem("a", "b")
        seen = []
        m.subscribe("update", lambda ev, e, i: seen.append(i))
        assert m.batch_update([{"index": 0, "content": "A"}, {"index": 1, "content": "B"}]) == 2
        assert seen == [0, 1]

    def test_events_are_isolated(self):
        m = Memory()
        adds, removes = [], []
        m.subscribe("add", lambda ev, e, i: adds.append(e.content))
        m.subscribe("remove", lambda ev, e, i: removes.append(e.content))
        m.add("x")
        assert adds == ["x"] and removes == []

    def test_callback_exception_swallowed(self):
        m = Memory()
        ok = []
        def boom(ev, e, i):
            raise RuntimeError("observer bug")
        m.subscribe("add", boom)
        m.subscribe("add", lambda ev, e, i: ok.append(e.content))
        m.add("survives")  # must not raise
        assert ok == ["survives"]  # later callbacks still run

    def test_multiple_callbacks_same_event(self):
        m = Memory()
        hits = []
        m.subscribe("add", lambda ev, e, i: hits.append("first"))
        m.subscribe("add", lambda ev, e, i: hits.append("second"))
        m.add("z")
        assert hits == ["first", "second"]  # registration order

    def test_invalid_event_raises_value_error(self):
        with pytest.raises(ValueError):
            Memory().subscribe("explode", lambda *a: None)

    def test_non_callable_raises_type_error(self):
        with pytest.raises(TypeError):
            Memory().subscribe("add", "not-callable")

    def test_unsubscribe_by_token_stops_events(self):
        m = Memory()
        seen = []
        token = m.subscribe("add", lambda ev, e, i: seen.append(e.content))
        assert m.unsubscribe(token) is True
        m.add("gone")
        assert seen == []

    def test_unsubscribe_unknown_token_false(self):
        assert Memory().unsubscribe("sub_999") is False

    def test_unsubscribe_only_removes_target(self):
        m = Memory()
        seen = []
        t1 = m.subscribe("add", lambda ev, e, i: seen.append("t1"))
        m.subscribe("add", lambda ev, e, i: seen.append("t2"))
        m.unsubscribe(t1)
        m.add("q")
        assert seen == ["t2"]

    def test_maintenance_ops_do_not_emit(self):
        """resize/forget/clear/trim are silent by contract."""
        m = Memory(max_entries=2)
        seen = []
        m.subscribe("add", lambda ev, e, i: seen.append(("add", e.content)))
        m.subscribe("remove", lambda ev, e, i: seen.append(("remove", e.content)))
        m.add("a"); m.add("b"); m.add("c")  # third add evicts "a" — trim is silent
        assert seen == [("add", "a"), ("add", "b"), ("add", "c")]
        m.resize(1)
        m.clear()
        assert len(seen) == 3  # resize/clear emitted nothing

    def test_copy_has_no_subscribers(self):
        m = Memory()
        seen = []
        m.subscribe("add", lambda ev, e, i: seen.append(e.content))
        c = m.copy()
        c.add("ghost")
        assert seen == []
