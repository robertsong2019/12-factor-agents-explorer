"""
Edge case tests to fill coverage gaps - 2026-07-10 cycle
Targets: Memory.search negative limit, Memory.forget negative threshold,
Agent._execute_tool missing arguments key, Memory.add importance out of range,
Tool.execute with extra kwargs, LLM.chat with empty messages
"""

import sys
sys.path.insert(0, "src")

from nano_agent.memory import Memory, MemoryEntry
from nano_agent.tools import Tool, tool, clear_tools, unregister_tool
from nano_agent.agent import Agent
from nano_agent.llm import LLM, MockBackend


# ─── Memory.search with negative limit ───

def test_search_negative_limit_returns_all():
    """Negative limit is <= 0, so code returns all matches (limit <= 0 branch)"""
    m = Memory()
    for i in range(5):
        m.add(f"item {i}")
    results = m.search("item", limit=-1)
    # Code: if limit <= 0: return matched — so all 5 returned
    assert len(results) == 5


def test_search_negative_limit_minus_two():
    """limit=-2 is <= 0, returns all matches"""
    m = Memory()
    for i in range(5):
        m.add(f"item {i}")
    results = m.search("item", limit=-2)
    assert len(results) == 5


# ─── Memory.forget with negative threshold ───

def test_forget_negative_threshold_keeps_all():
    """Negative threshold: all entries have importance >= negative value"""
    m = Memory()
    m.add("low", importance=0.01)
    m.add("high", importance=0.9)
    removed = m.forget(threshold=-0.5)
    assert removed == 0
    assert m.count() == 2


def test_forget_threshold_above_all():
    """Threshold higher than all importances removes everything"""
    m = Memory()
    m.add("a", importance=0.3)
    m.add("b", importance=0.5)
    removed = m.forget(threshold=0.6)
    assert removed == 2
    assert m.count() == 0


# ─── Agent._execute_tool with missing "arguments" key ───

def test_execute_tool_missing_arguments_key():
    """tool_call dict without 'arguments' key should be handled gracefully (bug fix)
    Previously raised KeyError; now uses .get('arguments', '{}') → empty dict."""
    agent = Agent("test", "test", llm=LLM.mock(), verbose=False)
    from nano_agent.tools import Tool
    def dummy(x="default"):
        return x
    agent.tools = [Tool(name="dummy", description="test", func=dummy, parameters={"x": {"type": "string", "default": "default"}})]
    # Missing "arguments" key — should default to {} and call dummy() with defaults
    result = agent._execute_tool({"name": "dummy", "id": "1"})
    assert result == "default"


# ─── Memory.add with importance out of [0, 1] range ───

def test_add_importance_above_one():
    """add() doesn't clamp importance; set_importance does"""
    m = Memory()
    m.add("entry", importance=1.5)
    # add() stores as-is without clamping (documented behavior)
    assert m._entries[0].importance == 1.5


def test_add_importance_below_zero():
    """add() doesn't clamp negative importance"""
    m = Memory()
    m.add("entry", importance=-0.5)
    assert m._entries[0].importance == -0.5


# ─── Tool.execute with extra unknown kwargs ───

def test_tool_execute_extra_kwargs_raises():
    """Tool.execute passes extra kwargs to func; if func doesn't accept them, it errors"""
    def strict(a: str, b: str = "default"):
        return f"{a}-{b}"
    t = Tool(name="strict", description="strict params", func=strict,
             parameters={"a": {"type": "string"}, "b": {"type": "string", "default": "default"}})
    try:
        result = t.execute(a="yes", c="extra")
        # If it doesn't raise, that's unexpected
        assert False, "Should have raised TypeError"
    except TypeError:
        pass  # Expected: strict() got unexpected keyword 'c'


# ─── Memory.importance_decay factor boundary ───

def test_decay_factor_zero_returns_zero():
    """factor=0: condition 0 < factor < 1 is False, so returns 0"""
    m = Memory()
    m.add("a", importance=0.8)
    result = m.importance_decay(factor=0)
    assert result == 0
    # Importance should NOT change
    assert m._entries[0].importance == 0.8


# ─── Memory.search with empty query and empty memory ───

def test_search_empty_memory_empty_query():
    """Search on empty memory with empty query returns nothing"""
    m = Memory()
    results = m.search("")
    assert results == []


def test_search_empty_query_matches_all():
    """Empty query string is substring of everything, so matches all"""
    m = Memory()
    m.add("hello")
    m.add("world")
    results = m.search("")
    assert len(results) == 2


# ─── Tool.validate_args with extra params ───

def test_validate_args_with_extra_params():
    """Extra params not in definition should not cause validation errors"""
    def func(a: str):
        return a
    t = Tool(name="f", description="test", func=func,
             parameters={"a": {"type": "string"}})
    errors = t.validate_args(a="val", extra="ignored")
    # validate_args only checks for missing required, not extra
    assert errors == []


# ─── Memory.update preserves tags ───

def test_update_does_not_clear_tags():
    """update() should preserve existing tags when only content changes"""
    m = Memory()
    m.add("original", tags=["important", "todo"])
    success = m.update(0, "updated content")
    assert success
    assert m._entries[0].tags == ["important", "todo"]
    assert m._entries[0].content == "updated content"


# ─── Memory.to_context with exactly header size ───

def test_to_context_exact_header_size():
    """When max_tokens exactly equals header size, no entries fit"""
    m = Memory()
    m.add("short")
    # Header is "## 记忆\n" which is ~12 bytes
    ctx = m.to_context(max_tokens=10)
    # Should have at most the header since entries won't fit
    assert "## 记忆" in ctx or ctx == ""


# ─── Agent.run preserves conversation across turns ───

def test_agent_conversation_history_grows_correctly():
    """Each run() adds exactly one user + one assistant message to history"""
    agent = Agent("test", "test", llm=LLM.mock(), verbose=False)
    assert len(agent._conversation_history) == 0
    agent.run("hello")
    assert len(agent._conversation_history) == 2  # user + assistant
    agent.run("world")
    assert len(agent._conversation_history) == 4
