"""
Coverage gap tests for nano-agent — 2026-06-26 cycle 2
Targets: MockBackend tool-call behavior, Memory.to_context truncation,
Memory.search combined tags+query, MemoryEntry.to_dict conditional tags
"""

import json
import pytest
from datetime import datetime

from src.nano_agent.llm import LLM, MockBackend, LLMBackend
from src.nano_agent.memory import Memory, MemoryEntry
from src.nano_agent.agent import Agent


# ─── MockBackend tool-call behavior ─────────────────────────────────

class TestMockBackendToolCalls:
    def test_tool_call_when_search_in_message(self):
        backend = MockBackend()
        tools = [{"name": "search_engine", "description": "Search the web", "parameters": {"query": {"type": "string"}}}]
        result = backend.complete(
            messages=[{"role": "user", "content": "请搜索 AI 新闻"}],
            tools=tools
        )
        assert result["content"] == ""
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "search_engine"
        assert "query" in json.loads(result["tool_calls"][0]["arguments"])

    def test_no_tool_call_without_search_keyword(self):
        backend = MockBackend()
        tools = [{"name": "search_engine", "description": "Search", "parameters": {"query": {"type": "string"}}}]
        result = backend.complete(
            messages=[{"role": "user", "content": "你好"}],
            tools=tools
        )
        assert result["tool_calls"] == []
        assert "模拟回复" in result["content"]

    def test_no_tool_call_without_tools(self):
        backend = MockBackend()
        result = backend.complete(
            messages=[{"role": "user", "content": "搜索一下"}],
            tools=None
        )
        assert result["tool_calls"] == []

    def test_empty_messages(self):
        backend = MockBackend()
        result = backend.complete(messages=[], tools=None)
        assert "content" in result
        assert result["tool_calls"] == []

    def test_usage_always_present(self):
        backend = MockBackend()
        result = backend.complete(messages=[{"role": "user", "content": "hi"}])
        assert "usage" in result
        assert result["usage"]["total_tokens"] > 0


# ─── MemoryEntry.to_dict conditional tags ───────────────────────────

class TestMemoryEntryToDict:
    def test_to_dict_without_tags(self):
        entry = MemoryEntry(content="hello", importance=0.8)
        d = entry.to_dict()
        assert "tags" not in d
        assert d["content"] == "hello"
        assert d["importance"] == 0.8

    def test_to_dict_with_tags(self):
        entry = MemoryEntry(content="hello", tags=["a", "b"], importance=0.9)
        d = entry.to_dict()
        assert d["tags"] == ["a", "b"]

    def test_to_dict_includes_metadata(self):
        entry = MemoryEntry(content="test", metadata={"key": "val"})
        d = entry.to_dict()
        assert d["metadata"] == {"key": "val"}

    def test_to_dict_timestamp_is_iso(self):
        entry = MemoryEntry(content="x")
        d = entry.to_dict()
        # Should be ISO format string
        datetime.fromisoformat(d["timestamp"])


# ─── Memory.to_context truncation ───────────────────────────────────

class TestMemoryToContext:
    def test_empty_memory_context(self):
        m = Memory()
        assert m.to_context() == ""

    def test_context_has_memory_header(self):
        m = Memory()
        m.add("test entry")
        ctx = m.to_context()
        assert "## 记忆" in ctx
        assert "test entry" in ctx

    def test_context_truncation(self):
        m = Memory()
        # Add entries with long content to trigger truncation
        for i in range(20):
            m.add(f"Entry number {i} " * 20)  # ~400 bytes each
        ctx = m.to_context(max_tokens=200)
        # Should be truncated — not all entries present
        assert "## 记忆" in ctx
        # The total text should be limited
        assert len(ctx.encode('utf-8')) < 500  # header + a few entries

    def test_context_no_truncation_needed(self):
        m = Memory()
        m.add("short")
        ctx = m.to_context(max_tokens=10000)
        assert "short" in ctx

    def test_context_format_includes_timestamp(self):
        m = Memory()
        m.add("timestamped entry")
        ctx = m.to_context()
        # Should contain a date pattern
        assert "-" in ctx  # YYYY-MM-DD format


# ─── Memory.search combined tags + query ────────────────────────────

class TestMemorySearchCombined:
    def test_search_with_tags_filters(self):
        m = Memory()
        m.add("python tutorial", tags=["tech"])
        m.add("python news", tags=["news"])
        m.add("cooking recipe", tags=["food"])
        results = m.search("python", tags=["tech"])
        assert len(results) == 1
        assert "tutorial" in results[0].content

    def test_search_tags_no_match(self):
        m = Memory()
        m.add("python code", tags=["tech"])
        results = m.search("python", tags=["nonexistent"])
        assert results == []

    def test_search_multiple_tags_any_match(self):
        m = Memory()
        m.add("entry A", tags=["x", "y"])
        m.add("entry B", tags=["z"])
        results = m.search("entry", tags=["x", "z"])
        assert len(results) == 2

    def test_search_no_tags_searches_all(self):
        m = Memory()
        m.add("hello world", tags=["greeting"])
        m.add("hello there", tags=["other"])
        results = m.search("hello")
        assert len(results) == 2

    def test_search_limit_zero_returns_all(self):
        m = Memory()
        m.add("match 1")
        m.add("match 2")
        m.add("match 3")
        results = m.search("match", limit=0)
        assert len(results) == 3


# ─── Agent.reset / history / turn_count deeper tests ────────────────

class TestAgentConversationManagement:
    def test_reset_clears_history(self):
        agent = Agent(name="T", instructions="test")
        agent._conversation_history.append({"role": "user", "content": "hi"})
        agent._conversation_history.append({"role": "assistant", "content": "hello"})
        agent.reset()
        assert agent._conversation_history == []
        assert agent.turn_count == 0

    def test_history_limit(self):
        agent = Agent(name="T", instructions="test")
        for i in range(20):
            agent._conversation_history.append({"role": "user", "content": f"msg{i}"})
        hist = agent.history(limit=5)
        assert len(hist) == 5
        assert hist[-1]["content"] == "msg19"

    def test_history_default_limit(self):
        agent = Agent(name="T", instructions="test")
        for i in range(15):
            agent._conversation_history.append({"role": "user", "content": f"u{i}"})
        hist = agent.history()
        assert len(hist) == 10  # default limit=10

    def test_turn_count_only_users(self):
        agent = Agent(name="T", instructions="test")
        agent._conversation_history = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
            {"role": "user", "content": "c"},
        ]
        assert agent.turn_count == 2


# ─── LLM class factory tests ────────────────────────────────────────

class TestLLMFactories:
    def test_mock_factory_returns_mock_backend(self):
        llm = LLM.mock()
        assert isinstance(llm.backend, MockBackend)

    def test_chat_delegates_to_backend(self):
        llm = LLM.mock()
        result = llm.chat(messages=[{"role": "user", "content": "hi"}])
        assert "content" in result
        assert "tool_calls" in result

    def test_chat_passes_kwargs(self):
        llm = LLM.mock()
        result = llm.chat(
            messages=[{"role": "user", "content": "搜索 test"}],
            tools=[{"name": "search", "description": "d", "parameters": {"q": {"type": "string"}}}],
            temperature=0.7
        )
        assert len(result["tool_calls"]) == 1
