"""Tests for Cycle 1-3 (2026-08-14 creative evening).

Cycle 1: Memory.range_query() — time-bounded search with tag/content filters
Cycle 2: Memory.annotate() / annotations() / most_annotated()
Cycle 3: Agent.inspect_tools()
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from datetime import datetime, timedelta
from nano_agent.memory import Memory, MemoryEntry
from nano_agent.agent import Agent
from nano_agent.llm import LLM
from nano_agent.tools import Tool


class TestRangeQuery:
    """Cycle 1: Memory.range_query()"""

    def _make_memory(self) -> Memory:
        m = Memory(persistence_path=None)
        now = datetime.now()
        for i in range(10):
            t = now - timedelta(hours=i * 2)
            entry = MemoryEntry(
                content=f"event-{i}",
                timestamp=t,
                tags=[f"tag{i % 3}"],
                importance=0.5,
            )
            m._entries.append(entry)
        return m

    def test_basic_range(self):
        m = self._make_memory()
        now = datetime.now()
        start = now - timedelta(hours=5)
        results = m.range_query(start)
        # entries 0-2 are within 5h
        assert len(results) >= 3

    def test_narrow_range(self):
        m = self._make_memory()
        now = datetime.now()
        start = now - timedelta(hours=1)
        end = now - timedelta(minutes=30)
        results = m.range_query(start, end)
        # event-0 at ~0h, should be excluded (>= end)
        # event-1 at ~2h, excluded
        assert len(results) == 0 or all(start <= e.timestamp < end for e in results)

    def test_tag_filter(self):
        m = self._make_memory()
        now = datetime.now()
        results = m.range_query(now - timedelta(hours=20), tags=["tag1"])
        for e in results:
            assert "tag1" in e.tags

    def test_content_filter(self):
        m = self._make_memory()
        now = datetime.now()
        results = m.range_query(now - timedelta(hours=20), content_filter="event-3")
        for e in results:
            assert "event-3" in e.content

    def test_limit(self):
        m = self._make_memory()
        now = datetime.now()
        results = m.range_query(now - timedelta(hours=20), limit=3)
        assert len(results) <= 3

    def test_sort_asc(self):
        m = self._make_memory()
        now = datetime.now()
        results = m.range_query(now - timedelta(hours=20), sort_desc=False)
        if len(results) >= 2:
            assert results[0].timestamp <= results[1].timestamp

    def test_empty_range(self):
        m = self._make_memory()
        future = datetime.now() + timedelta(days=1)
        results = m.range_query(future)
        assert len(results) == 0

    def test_no_tag_match(self):
        m = self._make_memory()
        now = datetime.now()
        results = m.range_query(now - timedelta(hours=20), tags=["nonexistent"])
        assert len(results) == 0

    def test_default_end_is_now(self):
        m = self._make_memory()
        # Should not raise
        results = m.range_query(datetime.now() - timedelta(hours=1))
        assert isinstance(results, list)


class TestAnnotate:
    """Cycle 2: Memory.annotate() / annotations() / most_annotated()"""

    def test_basic_annotate(self):
        m = Memory(persistence_path=None)
        m.add("hello")
        assert m.annotate(0, "useful note")
        anns = m.annotations(0)
        assert len(anns) == 1
        assert anns[0]["note"] == "useful note"

    def test_multiple_annotations(self):
        m = Memory(persistence_path=None)
        m.add("item")
        m.annotate(0, "first")
        m.annotate(0, "second")
        assert len(m.annotations(0)) == 2

    def test_annotate_invalid_index(self):
        m = Memory(persistence_path=None)
        assert m.annotate(-1, "nope") is False
        assert m.annotate(0, "nope") is False  # empty memory

    def test_annotations_empty(self):
        m = Memory(persistence_path=None)
        assert m.annotations(0) == []
        m.add("entry")
        assert m.annotations(0) == []  # no annotations yet

    def test_annotation_has_timestamp(self):
        m = Memory(persistence_path=None)
        m.add("x")
        m.annotate(0, "ts check")
        anns = m.annotations(0)
        assert "timestamp" in anns[0]
        # parseable ISO format
        datetime.fromisoformat(anns[0]["timestamp"])

    def test_annotate_preserves_existing_metadata(self):
        m = Memory(persistence_path=None)
        m.add("data", metadata={"key": "val"})
        m.annotate(0, "note")
        assert m._entries[0].metadata["key"] == "val"
        assert len(m._entries[0].metadata["_annotations"]) == 1

    def test_most_annotated(self):
        m = Memory(persistence_path=None)
        m.add("a")
        m.add("b")
        m.add("c")
        m.annotate(0, "n1")
        m.annotate(0, "n2")
        m.annotate(1, "n3")
        top = m.most_annotated()
        assert len(top) == 2  # only entries with annotations
        assert top[0]["index"] == 0  # most annotated first
        assert top[0]["annotation_count"] == 2

    def test_most_annotated_empty(self):
        m = Memory(persistence_path=None)
        assert m.most_annotated() == []

    def test_most_annotated_limit(self):
        m = Memory(persistence_path=None)
        for i in range(5):
            m.add(f"entry-{i}")
            for j in range(i + 1):
                m.annotate(i, f"note-{j}")
        top = m.most_annotated(limit=2)
        assert len(top) == 2
        assert top[0]["annotation_count"] == 5

    def test_annotations_invalid_index(self):
        m = Memory(persistence_path=None)
        assert m.annotations(-1) == []
        assert m.annotations(999) == []


def _dummy(x=0):
    return x


class TestInspectTools:
    """Cycle 3: Agent.inspect_tools()"""

    def test_no_tools(self):
        a = Agent(name="test", instructions="do stuff", llm=LLM.mock())
        assert a.inspect_tools() == []

    def test_with_tools(self):
        tool = Tool(name="calc", description="calculate", func=_dummy, parameters={})
        a = Agent(name="test", instructions="do stuff", llm=LLM.mock(), tools=[tool])
        result = a.inspect_tools()
        assert len(result) == 1
        assert result[0]["name"] == "calc"

    def test_multiple_tools(self):
        tools = [
            Tool(name=f"tool_{i}", description=f"desc_{i}", func=_dummy, parameters={})
            for i in range(3)
        ]
        a = Agent(name="test", instructions="do stuff", llm=LLM.mock(), tools=tools)
        result = a.inspect_tools()
        assert len(result) == 3

    def test_tool_schema_content(self):
        params = {"type": "object", "properties": {"x": {"type": "number"}}}
        tool = Tool(name="add", description="add numbers", func=_dummy, parameters=params)
        a = Agent(name="test", instructions="do stuff", llm=LLM.mock(), tools=[tool])
        result = a.inspect_tools()
        assert result[0]["parameters"] == params

    def test_reflects_dynamic_changes(self):
        a = Agent(name="test", instructions="do stuff", llm=LLM.mock())
        assert a.inspect_tools() == []
        a.add_tool(Tool(name="new", description="d", func=_dummy, parameters={}))
        assert len(a.inspect_tools()) == 1
        a.remove_tool("new")
        assert a.inspect_tools() == []
