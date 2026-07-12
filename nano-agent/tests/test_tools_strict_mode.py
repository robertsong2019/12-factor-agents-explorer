"""
Tests for Tool.validate_args strict mode (F11)
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.tools import Tool


def make_tool(params):
    """Helper: create a tool with given parameter spec"""
    def dummy(**kwargs):
        return "ok"
    return Tool(name="test", description="test", func=dummy, parameters=params)


class TestValidateArgsStrict:
    """Tool.validate_args(strict=True) — reject unknown parameters"""

    def test_strict_rejects_unknown_param(self):
        t = make_tool({"query": {"type": "string"}})
        errors = t.validate_args(strict=True, query="hi", extra="bad")
        assert len(errors) == 1
        assert "extra" in errors[0]

    def test_strict_allows_known_params(self):
        t = make_tool({"query": {"type": "string"}, "limit": {"type": "integer", "default": 10}})
        errors = t.validate_args(strict=True, query="hi", limit=5)
        assert errors == []

    def test_strict_rejects_multiple_unknown(self):
        t = make_tool({"query": {"type": "string"}})
        errors = t.validate_args(strict=True, query="hi", a="x", b="y", c="z")
        assert len(errors) == 3
        error_text = " ".join(errors)
        assert "a" in error_text
        assert "b" in error_text
        assert "c" in error_text

    def test_non_strict_ignores_unknown(self):
        """Default mode (strict=False) ignores unknown params"""
        t = make_tool({"query": {"type": "string"}})
        errors = t.validate_args(query="hi", extra="ok")
        assert errors == []

    def test_strict_still_checks_required(self):
        """Strict mode also validates required params"""
        t = make_tool({"query": {"type": "string"}, "optional": {"type": "string", "default": "x"}})
        errors = t.validate_args(strict=True, optional="val")
        # query is required but missing
        assert any("query" in e for e in errors)

    def test_strict_with_no_params(self):
        """Tool with no params, strict rejects any kwargs"""
        t = make_tool({})
        errors = t.validate_args(strict=True, foo="bar")
        assert len(errors) == 1

    def test_strict_with_no_kwargs(self):
        """Strict mode with no kwargs and no required = valid"""
        t = make_tool({"opt": {"type": "string", "default": "x"}})
        errors = t.validate_args(strict=True)
        assert errors == []

    def test_strict_combined_required_and_unknown(self):
        """Both missing required and unknown params reported"""
        t = make_tool({"name": {"type": "string"}, "age": {"type": "integer", "default": 0}})
        errors = t.validate_args(strict=True, age=5, bogus=True)
        assert len(errors) == 2
        assert any("name" in e for e in errors)
        assert any("bogus" in e for e in errors)

    def test_strict_default_false_backward_compat(self):
        """Calling without strict= defaults to lenient mode"""
        t = make_tool({"q": {"type": "string"}})
        errors = t.validate_args(q="hi", unknown="val")
        assert errors == []

    def test_strict_message_format(self):
        """Error message contains the未知 parameter name"""
        t = make_tool({"x": {"type": "string"}})
        errors = t.validate_args(strict=True, x="1", mystery="??")
        assert len(errors) == 1
        assert "mystery" in errors[0]
