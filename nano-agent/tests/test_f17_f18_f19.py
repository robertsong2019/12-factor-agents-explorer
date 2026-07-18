"""
Tests for F17 (search_fuzzy), F18 (group_by_tag), F19 (add_tool/remove_tool)
"""
import pytest
from nano_agent.memory import Memory, MemoryEntry
from nano_agent.agent import Agent
from nano_agent.tools import Tool


# ─── F17: search_fuzzy ───

class TestSearchFuzzy:
    def test_exact_substring_match(self):
        m = Memory()
        m.add("The quick brown fox jumps over the lazy dog")
        m.add("Python programming language tutorial")
        results = m.search_fuzzy("python")
        assert len(results) == 1
        assert "Python" in results[0].content

    def test_fuzzy_match_similar_content(self):
        m = Memory()
        m.add("Machine learning models for prediction")
        m.add("Deep neural network architecture")
        m.add("Cooking Italian pasta recipes")
        results = m.search_fuzzy("machine learning model", threshold=0.3)
        assert len(results) >= 1
        assert results[0].content == "Machine learning models for prediction"

    def test_threshold_filters_low_similarity(self):
        m = Memory()
        m.add("abc")
        m.add("The quick brown fox")
        results = m.search_fuzzy("xyz", threshold=0.5)
        assert len(results) == 0

    def test_limit_restricts_results(self):
        m = Memory()
        for i in range(10):
            m.add(f"Python script number {i} for automation")
        results = m.search_fuzzy("python", limit=3)
        assert len(results) == 3

    def test_limit_zero_returns_all(self):
        m = Memory()
        m.add("Python one")
        m.add("Python two")
        m.add("Python three")
        results = m.search_fuzzy("python", limit=0)
        assert len(results) == 3

    def test_empty_query_returns_empty(self):
        m = Memory()
        m.add("hello world")
        assert m.search_fuzzy("") == []

    def test_empty_memory_returns_empty(self):
        m = Memory()
        assert m.search_fuzzy("anything") == []

    def test_results_sorted_by_similarity_desc(self):
        m = Memory()
        m.add("Python programming")          # high match
        m.add("Python programming advanced")  # high match
        m.add("Ruby on rails")               # low match
        results = m.search_fuzzy("python programming", threshold=0.2)
        assert len(results) >= 2
        # First result should be exact or near-exact match
        assert results[0].content == "Python programming"

    def test_case_insensitive_match(self):
        m = Memory()
        m.add("PYTHON IS GREAT")
        results = m.search_fuzzy("python is great", threshold=0.5)
        assert len(results) == 1

    def test_default_threshold_works(self):
        m = Memory()
        m.add("The weather is nice today")
        m.add("Completely unrelated content about space")
        results = m.search_fuzzy("weather nice today")
        assert len(results) >= 1
        assert "weather" in results[0].content


# ─── F18: group_by_tag ───

class TestGroupByTag:
    def test_basic_grouping(self):
        m = Memory()
        m.add("task one", tags=["work"])
        m.add("task two", tags=["work"])
        m.add("grocery list", tags=["personal"])
        groups = m.group_by_tag()
        assert len(groups["work"]) == 2
        assert len(groups["personal"]) == 1

    def test_multi_tag_entry_appears_in_all_groups(self):
        m = Memory()
        m.add("project review", tags=["work", "important"])
        groups = m.group_by_tag()
        assert "project review" in [e.content for e in groups["work"]]
        assert "project review" in [e.content for e in groups["important"]]

    def test_untagged_entries(self):
        m = Memory()
        m.add("no tags here")
        m.add("also untagged")
        groups = m.group_by_tag()
        assert "_untagged" in groups
        assert len(groups["_untagged"]) == 2

    def test_mixed_tagged_and_untagged(self):
        m = Memory()
        m.add("tagged entry", tags=["alpha"])
        m.add("untagged entry")
        groups = m.group_by_tag()
        assert "alpha" in groups
        assert "_untagged" in groups
        assert len(groups["alpha"]) == 1
        assert len(groups["_untagged"]) == 1

    def test_empty_memory_returns_empty_dict(self):
        m = Memory()
        assert m.group_by_tag() == {}

    def test_single_entry_multiple_tags(self):
        m = Memory()
        m.add("multi", tags=["a", "b", "c"])
        groups = m.group_by_tag()
        assert len(groups) == 3
        for tag in ["a", "b", "c"]:
            assert len(groups[tag]) == 1

    def test_entries_preserved_in_full(self):
        m = Memory()
        m.add("entry 1", tags=["x"])
        m.add("entry 2", tags=["x"])
        groups = m.group_by_tag()
        contents = sorted(e.content for e in groups["x"])
        assert contents == ["entry 1", "entry 2"]


# ─── F19: Agent.add_tool / remove_tool ───

class TestAddRemoveTool:
    def _make_tool(self, name="test_tool", desc="A test tool"):
        def fn(x: str = "default"):
            return f"result: {x}"
        return Tool(name=name, description=desc, func=fn)

    def test_add_new_tool(self):
        agent = Agent("test", "test instructions")
        tool = self._make_tool("calculator")
        agent.add_tool(tool)
        assert any(t.name == "calculator" for t in agent.tools)

    def test_add_tool_replaces_existing_same_name(self):
        agent = Agent("test", "test instructions")
        tool1 = self._make_tool("calc", "v1")
        agent.add_tool(tool1)
        tool2 = self._make_tool("calc", "v2")
        agent.add_tool(tool2)
        assert len([t for t in agent.tools if t.name == "calc"]) == 1
        assert agent.tools[0].description == "v2"

    def test_remove_existing_tool(self):
        agent = Agent("test", "test instructions")
        tool = self._make_tool("removable")
        agent.add_tool(tool)
        assert agent.remove_tool("removable") is True
        assert not any(t.name == "removable" for t in agent.tools)

    def test_remove_nonexistent_tool_returns_false(self):
        agent = Agent("test", "test instructions")
        assert agent.remove_tool("ghost") is False

    def test_add_multiple_different_tools(self):
        agent = Agent("test", "test instructions")
        agent.add_tool(self._make_tool("tool_a"))
        agent.add_tool(self._make_tool("tool_b"))
        agent.add_tool(self._make_tool("tool_c"))
        assert len(agent.tools) == 3

    def test_remove_tool_from_empty_list(self):
        agent = Agent("test", "test instructions", tools=[])
        assert agent.remove_tool("anything") is False

    def test_add_then_remove_then_add_again(self):
        agent = Agent("test", "test instructions")
        tool = self._make_tool("cyclic")
        agent.add_tool(tool)
        assert len(agent.tools) == 1
        agent.remove_tool("cyclic")
        assert len(agent.tools) == 0
        agent.add_tool(tool)
        assert len(agent.tools) == 1

    def test_remove_does_not_affect_other_tools(self):
        agent = Agent("test", "test instructions")
        agent.add_tool(self._make_tool("keep"))
        agent.add_tool(self._make_tool("remove_me"))
        agent.add_tool(self._make_tool("also_keep"))
        agent.remove_tool("remove_me")
        names = [t.name for t in agent.tools]
        assert "keep" in names
        assert "also_keep" in names
        assert "remove_me" not in names
        assert len(agent.tools) == 2
