"""
Tests for @tool decorator with *args/**kwargs and related edge cases.
Covers bug fix: VAR_POSITIONAL and VAR_KEYWORD were incorrectly treated as required parameters.
"""

import inspect
import pytest
from src.nano_agent.tools import tool, Tool, clear_tools, _tools
from src.nano_agent.memory import Memory
from src.nano_agent.agent import Agent
from src.nano_agent.llm import LLM


class TestToolVariadicParams:
    """Tests for @tool decorator with *args / **kwargs."""

    def setup_method(self):
        clear_tools()

    def test_star_args_excluded_from_params(self):
        @tool
        def func(name: str, *args):
            """Func with *args"""
            return name
        t = func._nano_agent_tool
        assert "args" not in t.parameters
        assert "name" in t.parameters

    def test_kwargs_excluded_from_params(self):
        @tool
        def func(name: str, **kwargs):
            """Func with **kwargs"""
            return name
        t = func._nano_agent_tool
        assert "kwargs" not in t.parameters
        assert "name" in t.parameters

    def test_both_variadic_excluded(self):
        @tool
        def func(name: str, *args, **kwargs):
            """Func with both"""
            return name
        t = func._nano_agent_tool
        assert "args" not in t.parameters
        assert "kwargs" not in t.parameters
        assert list(t.parameters.keys()) == ["name"]

    def test_variadic_func_validate_no_errors(self):
        @tool
        def func(name: str, *args, **kwargs):
            """Func"""
            return name
        t = func._nano_agent_tool
        errors = t.validate_args(name="test")
        assert errors == []

    def test_variadic_func_validate_strict_no_false_positive(self):
        @tool
        def func(name: str, *args, **kwargs):
            """Func"""
            return name
        t = func._nano_agent_tool
        # strict mode should only flag genuine unknowns, not *args/**kwargs
        errors = t.validate_args(strict=True, name="test")
        assert errors == []

    def test_variadic_func_still_catches_missing_required(self):
        @tool
        def func(name: str, *args, **kwargs):
            """Func"""
            return name
        t = func._nano_agent_tool
        errors = t.validate_args()
        assert len(errors) == 1
        assert "name" in errors[0]

    def test_variadic_func_execute_works(self):
        @tool
        def func(name: str, *args, **kwargs):
            """Func"""
            return f"{name}-{len(args)}-{len(kwargs)}"
        t = func._nano_agent_tool
        result = t.execute(name="test", extra1=1, extra2=2)
        assert "test-0-2" in result

    def test_variadic_to_dict_excludes_variadic(self):
        @tool
        def func(name: str, *args, **kwargs):
            """Func"""
            return name
        d = func._nano_agent_tool.to_dict()
        assert "args" not in d["parameters"]
        assert "kwargs" not in d["parameters"]
        assert "name" in d["parameters"]


class TestMemoryEmptyContent:
    """Edge cases for Memory with empty/special content."""

    def test_add_empty_string_content(self):
        m = Memory()
        m.add("")
        assert m.count() == 1
        assert m.get_all()[0].content == ""

    def test_search_special_characters(self):
        m = Memory()
        m.add("test [special] {chars} (paren)")
        m.add("normal text")
        results = m.search("[special]")
        assert len(results) == 1
        assert "special" in results[0].content

    def test_search_unicode(self):
        m = Memory()
        m.add("你好世界 🌍")
        m.add("Hello World")
        results = m.search("你好")
        assert len(results) == 1

    def test_update_to_empty_content(self):
        m = Memory()
        m.add("original content")
        ok = m.update(0, "")
        assert ok
        assert m.get_all()[0].content == ""

    def test_import_json_with_extra_fields(self):
        """Extra fields in import data should be silently ignored."""
        import json
        m = Memory()
        data = json.dumps([{
            "content": "test",
            "timestamp": "2026-01-01T00:00:00",
            "metadata": {},
            "tags": [],
            "importance": 0.5,
            "extra_field": "should be ignored",
            "another": 42
        }])
        count = m.import_json(data)
        assert count == 1
        assert m.get_all()[0].content == "test"

    def test_export_then_import_replace_mode(self):
        """export → import with merge=False replaces everything."""
        m = Memory()
        m.add("old1", importance=0.9)
        m.add("old2", importance=0.3)
        exported = m.export_json()

        m2 = Memory()
        m2.add("placeholder")
        count = m2.import_json(exported, merge=False)
        assert count == 2
        assert m2.count() == 2
        assert "placeholder" not in [e.content for e in m2.get_all()]


class TestAgentHistoryEdgeCases:
    """Edge cases for Agent history and summary."""

    def test_history_limit_zero(self):
        agent = Agent("test", "instructions", llm=LLM.mock(), verbose=False)
        agent._conversation_history.append({"role": "user", "content": "hi"})
        result = agent.history(limit=0)
        assert result == []

    def test_history_limit_negative_returns_empty(self):
        """Negative limit should return empty list (same as <= 0)."""
        agent = Agent("test", "instructions", llm=LLM.mock(), verbose=False)
        agent._conversation_history.append({"role": "user", "content": "hi"})
        agent._conversation_history.append({"role": "assistant", "content": "hello"})
        result = agent.history(limit=-1)
        assert result == []

    def test_summary_exactly_six_messages(self):
        """Summary recent field shows last 6 messages."""
        agent = Agent("test", "instructions", llm=LLM.mock(), verbose=False)
        for i in range(6):
            agent._conversation_history.append({"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"})
        s = agent.summary()
        assert len(s["recent"]) == 6

    def test_summary_more_than_six_messages_truncates(self):
        agent = Agent("test", "instructions", llm=LLM.mock(), verbose=False)
        for i in range(10):
            agent._conversation_history.append({"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"})
        s = agent.summary()
        assert len(s["recent"]) == 6
        # Should show last 6
        assert "msg9" in s["recent"][-1]["preview"]

    def test_run_verbose_false_produces_no_stdout(self, capsys):
        agent = Agent("test", "instructions", llm=LLM.mock(), verbose=False)
        agent.run("hello")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_run_verbose_true_produces_output(self, capsys):
        agent = Agent("test", "instructions", llm=LLM.mock(), verbose=True)
        agent.run("hello")
        captured = capsys.readouterr()
        assert len(captured.out) > 0
