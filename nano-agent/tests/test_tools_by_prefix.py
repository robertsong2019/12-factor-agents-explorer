"""
Tests for list_tools_by_prefix (F12)
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.tools import (
    tool, clear_tools, list_tools_by_prefix,
    _tools
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear registry before each test"""
    clear_tools()
    yield
    clear_tools()


class TestListToolsByPrefix:
    """list_tools_by_prefix — filter tools by name prefix"""

    def test_exact_match(self):
        @tool
        def search(query: str) -> str:
            """search"""
            return query

        result = list_tools_by_prefix("search")
        assert len(result) == 1
        assert result[0].name == "search"

    def test_prefix_match_multiple(self):
        @tool
        def db_query(q: str) -> str:
            """db query"""
            return q

        @tool
        def db_insert(table: str) -> str:
            """db insert"""
            return table

        @tool
        def web_search(q: str) -> str:
            """web search"""
            return q

        result = list_tools_by_prefix("db_")
        assert len(result) == 2
        names = [t.name for t in result]
        assert "db_query" in names
        assert "db_insert" in names
        assert "web_search" not in names

    def test_no_match(self):
        @tool
        def search(query: str) -> str:
            """search"""
            return query

        result = list_tools_by_prefix("nonexistent_")
        assert result == []

    def test_empty_prefix_matches_all(self):
        @tool
        def alpha(x: str) -> str:
            """alpha"""
            return x

        @tool
        def beta(x: str) -> str:
            """beta"""
            return x

        result = list_tools_by_prefix("")
        assert len(result) == 2

    def test_empty_registry(self):
        """No tools registered returns empty"""
        result = list_tools_by_prefix("anything")
        assert result == []

    def test_case_sensitive(self):
        @tool
        def Search(query: str) -> str:
            """Search"""
            return query

        # lowercase doesn't match
        result = list_tools_by_prefix("search")
        assert len(result) == 0

        # exact case matches
        result = list_tools_by_prefix("Search")
        assert len(result) == 1

    def test_returns_tool_objects(self):
        @tool
        def my_tool(x: str) -> str:
            """my tool"""
            return x

        result = list_tools_by_prefix("my_")
        assert len(result) == 1
        assert hasattr(result[0], "execute")
        assert hasattr(result[0], "to_dict")
        assert result[0].name == "my_tool"

    def test_single_char_prefix(self):
        @tool
        def api_get() -> str:
            """get"""
            return "get"

        @tool
        def api_post() -> str:
            """post"""
            return "post"

        @tool
        def web_scrape() -> str:
            """scrape"""
            return "scrape"

        result = list_tools_by_prefix("a")
        assert len(result) == 2
        assert all(t.name.startswith("a") for t in result)
