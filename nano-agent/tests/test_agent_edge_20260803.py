"""
Edge case tests for Agent — max_iterations, run_batch, conversation_stats,
add_tool replacement, and history boundary conditions.

Discovered during autoresearch testing cycle 2026-08-03.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from nano_agent.agent import Agent
from nano_agent.llm import LLM, MockBackend
from nano_agent.memory import Memory
from nano_agent.tools import Tool, tool, clear_tools, get_tool_from_func


@pytest.fixture
def agent():
    """Create a basic test agent."""
    return Agent(
        name="tester",
        instructions="You are a test agent.",
        llm=LLM(MockBackend()),
        verbose=False
    )


class TestAgentMaxIterationsZero:
    """Tests for max_iterations=0 edge case (bug fix: UnboundLocalError)."""

    def test_zero_iterations_does_not_crash(self):
        """max_iterations=0 should not raise UnboundLocalError."""
        a = Agent("t", "t", llm=LLM(MockBackend()), max_iterations=0, verbose=False)
        result = a.run("hello")
        # Should return empty or default, not crash
        assert result is not None
        assert isinstance(result, str)

    def test_zero_iterations_records_user_in_history(self):
        """Even with 0 iterations, user input should be in conversation history."""
        a = Agent("t", "t", llm=LLM(MockBackend()), max_iterations=0, verbose=False)
        a.run("test input")
        assert len(a._conversation_history) >= 1
        assert a._conversation_history[0]["role"] == "user"
        assert a._conversation_history[0]["content"] == "test input"

    def test_zero_iterations_records_memory(self):
        """Even with 0 iterations, the interaction should be saved to memory."""
        a = Agent("t", "t", llm=LLM(MockBackend()), max_iterations=0, verbose=False)
        a.run("remember this")
        assert a.memory.count() >= 1


class TestAgentRunBatchEdgeCases:
    """Tests for run_batch with mixed success/failure."""

    def test_run_batch_empty_list(self, agent):
        """run_batch with empty list should return empty list."""
        results = agent.run_batch([])
        assert results == []

    def test_run_batch_single_input(self, agent):
        """run_batch with one input."""
        results = agent.run_batch(["hello"])
        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["response"] is not None
        assert results[0]["error"] is None

    def test_run_batch_multiple_inputs(self, agent):
        """run_batch processes all inputs."""
        results = agent.run_batch(["hello", "world", "foo"])
        assert len(results) == 3
        for r in results:
            assert r["success"] is True

    def test_run_batch_handles_exceptions(self):
        """run_batch should catch exceptions and record them."""

        class ExplodingBackend(MockBackend):
            call_count = 0
            def complete(self, messages, tools=None, **kwargs):
                self.call_count += 1
                if self.call_count > 1:
                    raise RuntimeError("boom")
                return {"content": "ok", "tool_calls": []}

        agent = Agent("t", "t", llm=LLM(ExplodingBackend()), verbose=False)
        results = agent.run_batch(["first", "second"])
        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert "boom" in results[1]["error"]


class TestAgentAddToolReplace:
    """Tests for add_tool replacing existing tool with same name."""

    def test_add_tool_replaces_existing(self, agent):
        """Adding a tool with same name should replace, not duplicate."""

        @tool(name="my_tool", description="first version")
        def first_fn():
            return "v1"

        @tool(name="my_tool", description="second version")
        def second_fn():
            return "v2"

        t1 = get_tool_from_func(first_fn)
        agent.add_tool(t1)
        assert len(agent.tools) == 1

        t2 = get_tool_from_func(second_fn)
        agent.add_tool(t2)
        assert len(agent.tools) == 1
        assert agent.tools[0].name == "my_tool"

        clear_tools()

    def test_add_multiple_different_tools(self, agent):
        """Adding different tools should increase count."""

        @tool(name="tool_a", description="tool A")
        def fn_a():
            return "a"

        @tool(name="tool_b", description="tool B")
        def fn_b():
            return "b"

        agent.add_tool(get_tool_from_func(fn_a))
        agent.add_tool(get_tool_from_func(fn_b))
        assert len(agent.tools) == 2
        clear_tools()


class TestAgentHistoryBoundary:
    """Tests for history() boundary conditions."""

    def test_history_limit_zero(self, agent):
        """history(limit=0) should return empty list."""
        agent.run("hello")
        assert agent.history(limit=0) == []

    def test_history_negative_limit(self, agent):
        """history(limit=-1) should return empty list."""
        agent.run("hello")
        assert agent.history(limit=-1) == []

    def test_history_larger_than_actual(self, agent):
        """history with limit larger than history length returns all."""
        agent.run("hello")
        h = agent.history(limit=100)
        assert len(h) >= 1

    def test_history_returns_most_recent(self, agent):
        """history should return most recent messages."""
        agent.run("first message")
        agent.run("second message")
        h = agent.history(limit=2)
        # Should include the last 2 messages (could be user+assistant pairs)
        assert len(h) >= 2


class TestAgentConversationStats:
    """Tests for conversation_stats() accuracy."""

    def test_stats_empty_agent(self, agent):
        """Stats on fresh agent with no conversation."""
        stats = agent.conversation_stats()
        assert stats["total_messages"] == 0
        assert stats["by_role"] == {}
        assert stats["avg_length"] == 0
        assert stats["tool_calls"] == 0
        assert stats["est_tokens"] == 0

    def test_stats_after_conversation(self, agent):
        """Stats should reflect conversation after run."""
        agent.run("hello world")
        stats = agent.conversation_stats()
        assert stats["total_messages"] >= 1
        assert "user" in stats["by_role"]
        assert stats["avg_length"] > 0

    def test_stats_est_tokens_proportional(self, agent):
        """est_tokens should be roughly chars/4."""
        agent.run("abcdefgh")  # 8 chars
        stats = agent.conversation_stats()
        # At least the user message contributes 8 chars
        total_chars = sum(len(m["content"]) for m in agent._conversation_history)
        assert stats["est_tokens"] == total_chars // 4


class TestAgentTurnCount:
    """Tests for turn_count property."""

    def test_turn_count_starts_zero(self, agent):
        assert agent.turn_count == 0

    def test_turn_count_after_one_run(self, agent):
        agent.run("hello")
        assert agent.turn_count == 1

    def test_turn_count_after_multiple_runs(self, agent):
        agent.run("first")
        agent.run("second")
        agent.run("third")
        assert agent.turn_count == 3


class TestAgentReset:
    """Tests for reset() behavior."""

    def test_reset_clears_history(self, agent):
        agent.run("hello")
        assert len(agent._conversation_history) > 0
        agent.reset()
        assert len(agent._conversation_history) == 0

    def test_reset_preserves_tools(self, agent):
        @tool(name="keeper", description="should survive reset")
        def keeper_fn():
            return "kept"

        agent.add_tool(get_tool_from_func(keeper_fn))
        agent.reset()
        assert len(agent.tools) == 1
        assert agent.tools[0].name == "keeper"
        clear_tools()

    def test_reset_preserves_memory(self, agent):
        agent.run("remember this")
        assert agent.memory.count() > 0
        agent.reset()
        assert agent.memory.count() > 0  # Memory should survive reset
