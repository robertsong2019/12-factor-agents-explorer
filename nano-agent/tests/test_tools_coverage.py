"""Tests for tools.py edge cases: get_tool_from_func, clear_tools, tool re-registration, execute"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.tools import Tool, tool, get_tool, get_tool_from_func, list_tools, clear_tools, unregister_tool


@pytest.fixture(autouse=True)
def cleanup():
    clear_tools()
    yield
    clear_tools()


class TestGetToolFromFunc:
    def test_returns_attached_tool(self):
        @tool
        def my_func(x: str) -> str:
            """Does stuff"""
            return f"result: {x}"
        result = get_tool_from_func(my_func)
        assert result is not None
        assert result.name == "my_func"

    def test_returns_by_name_for_non_decorated(self):
        @tool
        def named_tool(x: str) -> str:
            """A tool"""
            return x
        # Access via a different reference
        def plain_func():
            pass
        plain_func.__name__ = "named_tool"
        result = get_tool_from_func(plain_func)
        assert result is not None
        assert result.name == "named_tool"

    def test_returns_none_for_unknown(self):
        def unknown():
            pass
        result = get_tool_from_func(unknown)
        assert result is None


class TestClearTools:
    def test_clears_all_tools(self):
        @tool
        def tool_a(x: str) -> str:
            """A"""
            return x
        @tool
        def tool_b(x: str) -> str:
            """B"""
            return x
        assert len(list_tools()) == 2
        clear_tools()
        assert len(list_tools()) == 0

    def test_clear_when_empty(self):
        clear_tools()
        assert len(list_tools()) == 0


class TestToolExecute:
    def test_execute_with_kwargs(self):
        @tool
        def adder(a: int, b: int) -> int:
            """Add two numbers"""
            return a + b
        t = get_tool("adder")
        assert t.execute(a=3, b=4) == 7

    def test_execute_with_defaults(self):
        @tool
        def greet(name: str, greeting: str = "hello") -> str:
            """Greet"""
            return f"{greeting} {name}"
        t = get_tool("greet")
        assert t.execute(name="world") == "hello world"
        assert t.execute(name="world", greeting="hi") == "hi world"


class TestToolReRegistration:
    def test_overwrite_same_name(self):
        @tool
        def shared(x: str) -> str:
            """v1"""
            return "v1"
        @tool
        def shared(x: str) -> str:
            """v2"""
            return "v2"
        t = get_tool("shared")
        assert t.description == "v2"
        assert t.execute(x="test") == "v2"

    def test_custom_name_overrides_function_name(self):
        @tool(name="custom_name")
        def original_func(x: str) -> str:
            """Custom"""
            return x
        assert get_tool("custom_name") is not None
        assert get_tool("original_func") is None


class TestToolValidation:
    def test_validate_args_no_required(self):
        @tool
        def optional_tool(x: str = "default") -> str:
            """Has default"""
            return x
        t = get_tool("optional_tool")
        errors = t.validate_args()
        assert errors == []

    def test_validate_args_missing_required(self):
        @tool
        def strict_tool(x: str, y: str) -> str:
            """Strict"""
            return f"{x}{y}"
        t = get_tool("strict_tool")
        errors = t.validate_args(x="a")
        assert len(errors) == 1
        assert "y" in errors[0]

    def test_validate_args_all_present(self):
        @tool
        def strict_tool(x: str, y: str) -> str:
            """Strict"""
            return f"{x}{y}"
        t = get_tool("strict_tool")
        errors = t.validate_args(x="a", y="b")
        assert errors == []
