"""
Coverage Cycle 3 — 2026-06-27
Targeted untested paths in memory.py and agent.py
"""

import pytest
import json
from src.nano_agent.memory import Memory, MemoryEntry
from src.nano_agent.agent import Agent
from src.nano_agent.llm import LLM, MockBackend
from src.nano_agent.tools import Tool
from datetime import datetime


# ─── Memory.update() edge cases ───

class TestMemoryUpdate:
    def test_update_negative_index_fails(self):
        m = Memory()
        m.add("hello")
        assert m.update(-1, "world") is False

    def test_update_out_of_range_fails(self):
        m = Memory()
        m.add("hello")
        assert m.update(5, "world") is False

    def test_update_preserves_tags(self):
        m = Memory()
        m.add("original", tags=["a", "b"])
        m.update(0, "updated")
        entry = m.get_all()[0]
        assert entry.content == "updated"
        assert entry.tags == ["a", "b"]

    def test_update_none_metadata_preserves_old(self):
        m = Memory()
        m.add("x", metadata={"key": "val"})
        m.update(0, "y", metadata=None)
        entry = m.get_all()[0]
        assert entry.metadata == {"key": "val"}

    def test_update_replaces_metadata(self):
        m = Memory()
        m.add("x", metadata={"a": 1})
        m.update(0, "y", metadata={"b": 2})
        entry = m.get_all()[0]
        assert entry.metadata == {"b": 2}

    def test_update_refreshes_timestamp(self):
        m = Memory()
        m.add("x")
        old_ts = m.get_all()[0].timestamp
        # tiny delay
        import time; time.sleep(0.001)
        m.update(0, "y")
        new_ts = m.get_all()[0].timestamp
        assert new_ts > old_ts


# ─── Memory.importance_decay() edge cases ───

class TestImportanceDecay:
    def test_decay_normal_factor(self):
        m = Memory()
        m.add("a", importance=1.0)
        m.add("b", importance=0.8)
        count = m.importance_decay(0.9)
        assert count == 2
        entries = m.get_all()
        assert abs(entries[0].importance - 0.9) < 0.001
        assert abs(entries[1].importance - 0.72) < 0.001

    def test_decay_zero_factor_no_op(self):
        m = Memory()
        m.add("a", importance=0.5)
        count = m.importance_decay(0)
        assert count == 0
        assert m.get_all()[0].importance == 0.5

    def test_decay_factor_one_no_op(self):
        m = Memory()
        m.add("a", importance=0.7)
        count = m.importance_decay(1.0)
        assert count == 0
        assert m.get_all()[0].importance == 0.7

    def test_decay_negative_factor_no_op(self):
        m = Memory()
        m.add("a", importance=0.6)
        count = m.importance_decay(-0.5)
        assert count == 0

    def test_decay_empty_memory(self):
        m = Memory()
        count = m.importance_decay(0.95)
        assert count == 0


# ─── Memory.forget() edge cases ───

class TestForget:
    def test_forget_removes_below_threshold(self):
        m = Memory()
        m.add("low", importance=0.05)
        m.add("mid", importance=0.3)
        m.add("high", importance=0.9)
        removed = m.forget(0.1)
        assert removed == 1
        assert m.count() == 2

    def test_forget_all_below_threshold(self):
        m = Memory()
        m.add("a", importance=0.01)
        m.add("b", importance=0.02)
        removed = m.forget(0.1)
        assert removed == 2
        assert m.count() == 0

    def test_forget_none_below_threshold(self):
        m = Memory()
        m.add("a", importance=0.5)
        m.add("b", importance=0.8)
        removed = m.forget(0.1)
        assert removed == 0
        assert m.count() == 2

    def test_forget_empty_memory(self):
        m = Memory()
        removed = m.forget(0.1)
        assert removed == 0

    def test_forget_boundary_equal_threshold(self):
        m = Memory()
        m.add("edge", importance=0.1)
        removed = m.forget(0.1)
        # 0.1 >= 0.1 → kept
        assert removed == 0


# ─── Memory.top_important() edge cases ───

class TestTopImportant:
    def test_top_n_more_than_count(self):
        m = Memory()
        m.add("a", importance=0.5)
        m.add("b", importance=0.9)
        result = m.top_important(10)
        assert len(result) == 2

    def test_top_empty_memory(self):
        m = Memory()
        result = m.top_important(5)
        assert result == []

    def test_top_zero_n(self):
        m = Memory()
        m.add("a", importance=0.9)
        result = m.top_important(0)
        assert result == []

    def test_top_negative_n(self):
        m = Memory()
        m.add("a", importance=0.9)
        result = m.top_important(-1)
        assert result == []

    def test_top_sorted_descending(self):
        m = Memory()
        m.add("low", importance=0.3)
        m.add("high", importance=0.9)
        m.add("mid", importance=0.6)
        result = m.top_important(3)
        assert result[0].importance >= result[1].importance >= result[2].importance
        assert result[0].importance == 0.9

    def test_top_ties_preserved(self):
        m = Memory()
        m.add("a", importance=0.5)
        m.add("b", importance=0.5)
        m.add("c", importance=0.5)
        result = m.top_important(2)
        assert len(result) == 2


# ─── Memory.remove() edge cases ───

class TestMemoryRemove:
    def test_remove_valid_index(self):
        m = Memory()
        m.add("a")
        m.add("b")
        assert m.remove(0) is True
        assert m.count() == 1
        assert m.get_all()[0].content == "b"

    def test_remove_out_of_range(self):
        m = Memory()
        m.add("only")
        assert m.remove(1) is False
        assert m.remove(-1) is False

    def test_remove_from_empty(self):
        m = Memory()
        assert m.remove(0) is False

    def test_remove_last_element(self):
        m = Memory()
        m.add("only")
        assert m.remove(0) is True
        assert m.count() == 0

    def test_remove_middle_element(self):
        m = Memory()
        m.add("a")
        m.add("b")
        m.add("c")
        m.remove(1)
        assert m.count() == 2
        assert m.get_all()[0].content == "a"
        assert m.get_all()[1].content == "c"


# ─── Agent._execute_tool edge cases ───

class TestExecuteToolEdgeCases:
    def test_invalid_json_arguments(self):
        agent = Agent("test", "test", llm=LLM.mock(), verbose=False)
        from src.nano_agent.tools import Tool
        def dummy(x):
            return x
        agent.tools = [Tool(name="dummy", description="test", func=dummy, parameters={"x": {"type": "string"}})]
        result = agent._execute_tool({"name": "dummy", "arguments": "not json{", "id": "1"})
        assert "错误" in result

    def test_missing_tool_name(self):
        agent = Agent("test", "test", llm=LLM.mock(), verbose=False)
        result = agent._execute_tool({"name": "nonexistent", "arguments": "{}", "id": "1"})
        assert "不存在" in result

    def test_tool_execution_exception(self):
        agent = Agent("test", "test", llm=LLM.mock(), verbose=False)
        def boom(**kwargs):
            raise RuntimeError("kaboom")
        from src.nano_agent.tools import Tool
        agent.tools = [Tool(name="boom", description="explodes", func=boom, parameters={})]
        result = agent._execute_tool({"name": "boom", "arguments": "{}", "id": "1"})
        assert "错误" in result
        assert "kaboom" in result

    def test_tool_none_arguments(self):
        agent = Agent("test", "test", llm=LLM.mock(), verbose=False)
        from src.nano_agent.tools import Tool
        def dummy(x="default"):
            return x
        agent.tools = [Tool(name="dummy", description="test", func=dummy, parameters={"x": {"type": "string", "default": "default"}})]
        result = agent._execute_tool({"name": "dummy", "arguments": None, "id": "1"})
        assert "错误" in result


# ─── MemoryEntry edge cases ───

class TestMemoryEntryEquality:
    def test_equal_entries(self):
        e1 = MemoryEntry(content="hello")
        e2 = MemoryEntry(content="hello")
        assert e1 == e2

    def test_not_equal_content(self):
        e1 = MemoryEntry(content="hello")
        e2 = MemoryEntry(content="world")
        assert e1 != e2

    def test_not_equal_to_non_entry(self):
        e = MemoryEntry(content="hello")
        assert e != "hello"
        assert e != 42
        assert e is not None

    def test_to_dict_without_tags_omits_key(self):
        e = MemoryEntry(content="x")
        d = e.to_dict()
        assert "tags" not in d

    def test_to_dict_with_tags_includes_key(self):
        e = MemoryEntry(content="x", tags=["a"])
        d = e.to_dict()
        assert d["tags"] == ["a"]


# ─── Tool.validate_args ───

class TestValidateArgs:
    def test_all_required_present(self):
        def fn(a, b):
            return f"{a}{b}"
        t = Tool(name="fn", description="test", func=fn,
                 parameters={"a": {"type": "string"}, "b": {"type": "integer"}})
        assert t.validate_args(a=1, b=2) == []

    def test_missing_required(self):
        def fn(a, b):
            return f"{a}{b}"
        t = Tool(name="fn", description="test", func=fn,
                 parameters={"a": {"type": "string"}, "b": {"type": "integer"}})
        errors = t.validate_args(a=1)
        assert len(errors) == 1
        assert "b" in errors[0]

    def test_optional_param_not_required(self):
        def fn(a, b="default"):
            return f"{a}{b}"
        t = Tool(name="fn", description="test", func=fn,
                 parameters={"a": {"type": "string"}, "b": {"type": "string", "default": "default"}})
        assert t.validate_args(a="x") == []

    def test_no_params(self):
        def fn():
            return "ok"
        t = Tool(name="fn", description="test", func=fn, parameters={})
        assert t.validate_args() == []

    def test_multiple_missing(self):
        def fn(a, b, c):
            return ""
        t = Tool(name="fn", description="test", func=fn,
                 parameters={"a": {"type": "string"}, "b": {"type": "string"}, "c": {"type": "string"}})
        errors = t.validate_args()
        assert len(errors) == 3
