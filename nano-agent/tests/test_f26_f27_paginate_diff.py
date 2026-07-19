"""
F26-F27 测试: Memory.paginate() + Memory.diff()
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from nano_agent.memory import Memory, MemoryEntry


# ─── F26: paginate ───

class TestPaginate:
    def test_basic_pagination(self):
        m = Memory()
        for i in range(25):
            m.add(f"entry_{i}")
        result = m.paginate(page=1, page_size=10)
        assert result["page"] == 1
        assert result["page_size"] == 10
        assert result["total"] == 25
        assert result["total_pages"] == 3
        assert len(result["entries"]) == 10

    def test_second_page(self):
        m = Memory()
        for i in range(25):
            m.add(f"entry_{i}")
        result = m.paginate(page=2, page_size=10)
        assert len(result["entries"]) == 10
        assert result["entries"][0].content == "entry_10"

    def test_last_page_partial(self):
        m = Memory()
        for i in range(25):
            m.add(f"entry_{i}")
        result = m.paginate(page=3, page_size=10)
        assert len(result["entries"]) == 5
        assert result["entries"][0].content == "entry_20"

    def test_desc_order(self):
        m = Memory()
        m.add("first")
        m.add("second")
        m.add("third")
        result = m.paginate(page=1, page_size=2, order="desc")
        assert result["entries"][0].content == "third"
        assert result["entries"][1].content == "second"

    def test_asc_order(self):
        m = Memory()
        m.add("first")
        m.add("second")
        result = m.paginate(page=1, page_size=10, order="asc")
        assert result["entries"][0].content == "first"

    def test_empty_memory(self):
        m = Memory()
        result = m.paginate(page=1, page_size=10)
        assert result["entries"] == []
        assert result["total"] == 0
        assert result["total_pages"] == 0

    def test_page_out_of_range(self):
        m = Memory()
        m.add("only one")
        result = m.paginate(page=5, page_size=10)
        assert result["entries"] == []
        assert result["total"] == 1

    def test_invalid_page(self):
        m = Memory()
        m.add("data")
        result = m.paginate(page=0, page_size=10)
        assert result["entries"] == []

    def test_invalid_page_size(self):
        m = Memory()
        m.add("data")
        result = m.paginate(page=1, page_size=0)
        assert result["entries"] == []
        assert result["total_pages"] == 0

    def test_exact_division(self):
        m = Memory()
        for i in range(20):
            m.add(f"e_{i}")
        result = m.paginate(page=2, page_size=10)
        assert result["total_pages"] == 2
        assert len(result["entries"]) == 10

    def test_single_page(self):
        m = Memory()
        m.add("only entry")
        result = m.paginate(page=1, page_size=10)
        assert result["total_pages"] == 1
        assert len(result["entries"]) == 1

    def test_page_size_larger_than_total(self):
        m = Memory()
        m.add("a")
        m.add("b")
        m.add("c")
        result = m.paginate(page=1, page_size=100)
        assert len(result["entries"]) == 3
        assert result["total_pages"] == 1

    def test_return_type(self):
        m = Memory()
        m.add("entry")
        result = m.paginate(page=1, page_size=10)
        assert isinstance(result, dict)
        assert "entries" in result
        assert "page" in result
        assert "page_size" in result
        assert "total" in result
        assert "total_pages" in result

    def test_entries_are_memory_entry_objects(self):
        m = Memory()
        m.add("test")
        result = m.paginate(page=1, page_size=10)
        assert isinstance(result["entries"][0], MemoryEntry)


# ─── F27: diff ───

class TestDiff:
    def test_identical_memories(self):
        m1 = Memory()
        m1.add("a")
        m1.add("b")
        m2 = Memory()
        m2.add("a")
        m2.add("b")
        result = m1.diff(m2)
        assert len(result["added"]) == 0
        assert len(result["removed"]) == 0
        assert len(result["common"]) == 2

    def test_completely_different(self):
        m1 = Memory()
        m1.add("x")
        m2 = Memory()
        m2.add("y")
        result = m1.diff(m2)
        assert len(result["added"]) == 1
        assert result["added"][0].content == "y"
        assert len(result["removed"]) == 1
        assert result["removed"][0].content == "x"
        assert len(result["common"]) == 0

    def test_partial_overlap(self):
        m1 = Memory()
        m1.add("shared")
        m1.add("only_m1")
        m2 = Memory()
        m2.add("shared")
        m2.add("only_m2")
        result = m1.diff(m2)
        assert len(result["added"]) == 1
        assert result["added"][0].content == "only_m2"
        assert len(result["removed"]) == 1
        assert result["removed"][0].content == "only_m1"
        assert len(result["common"]) == 1
        assert result["common"][0].content == "shared"

    def test_empty_self(self):
        m1 = Memory()
        m2 = Memory()
        m2.add("a")
        m2.add("b")
        result = m1.diff(m2)
        assert len(result["added"]) == 2
        assert len(result["removed"]) == 0
        assert len(result["common"]) == 0

    def test_empty_other(self):
        m1 = Memory()
        m1.add("a")
        m1.add("b")
        m2 = Memory()
        result = m1.diff(m2)
        assert len(result["added"]) == 0
        assert len(result["removed"]) == 2
        assert len(result["common"]) == 0

    def test_both_empty(self):
        m1 = Memory()
        m2 = Memory()
        result = m1.diff(m2)
        assert len(result["added"]) == 0
        assert len(result["removed"]) == 0
        assert len(result["common"]) == 0

    def test_diff_is_symmetric_complement(self):
        m1 = Memory()
        m1.add("a")
        m1.add("b")
        m2 = Memory()
        m2.add("b")
        m2.add("c")

        forward = m1.diff(m2)
        backward = m2.diff(m1)

        # forward.added == backward.removed
        assert forward["added"][0].content == backward["removed"][0].content
        # forward.removed == backward.added
        assert forward["removed"][0].content == backward["added"][0].content

    def test_common_preserves_self_entries(self):
        m1 = Memory()
        m1.add("shared", tags=["from_m1"], importance=0.9)
        m2 = Memory()
        m2.add("shared", tags=["from_m2"], importance=0.1)

        result = m1.diff(m2)
        # common entries come from self (m1)
        assert result["common"][0].tags == ["from_m1"]
        assert result["common"][0].importance == 0.9

    def test_duplicate_content_treated_as_same(self):
        m1 = Memory()
        m1.add("dup")
        m2 = Memory()
        m2.add("dup")
        m2.add("dup")
        result = m1.diff(m2)
        assert len(result["added"]) == 0
        assert len(result["common"]) == 1

    def test_return_type(self):
        m1 = Memory()
        m2 = Memory()
        m1.add("a")
        result = m1.diff(m2)
        assert isinstance(result, dict)
        assert "added" in result
        assert "removed" in result
        assert "common" in result
