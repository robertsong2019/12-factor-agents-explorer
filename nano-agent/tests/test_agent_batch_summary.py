"""
Tests for Agent.run_batch (F9) and Agent.summary (F10)
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.agent import Agent
from nano_agent.llm import LLM


# ── F9: run_batch ──


class TestRunBatch:
    """Agent.run_batch — batch input processing"""

    def test_batch_all_success(self):
        """Multiple inputs all succeed"""
        agent = Agent("test", "test agent", llm=LLM.mock(), verbose=False)
        results = agent.run_batch(["hello", "world", "foo"])

        assert len(results) == 3
        assert all(r["success"] for r in results)
        assert all(r["error"] is None for r in results)
        assert all(r["response"] is not None for r in results)

    def test_batch_single_input(self):
        """Single input in batch returns single result"""
        agent = Agent("t", "t", llm=LLM.mock(), verbose=False)
        results = agent.run_batch(["hi"])

        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["input"] == "hi"

    def test_batch_empty_list(self):
        """Empty input list returns empty results"""
        agent = Agent("t", "t", llm=LLM.mock(), verbose=False)
        results = agent.run_batch([])

        assert results == []

    def test_batch_preserves_input_order(self):
        """Results maintain same order as inputs"""
        agent = Agent("t", "t", llm=LLM.mock(), verbose=False)
        inputs = ["first", "second", "third"]
        results = agent.run_batch(inputs)

        for i, inp in enumerate(inputs):
            assert results[i]["input"] == inp

    def test_batch_with_context(self):
        """Batch passes shared context to each run"""
        agent = Agent("t", "t", llm=LLM.mock(), verbose=False)
        results = agent.run_batch(["q1", "q2"], context="shared context")

        assert len(results) == 2
        assert all(r["success"] for r in results)

    def test_batch_continues_on_error(self):
        """Batch continues processing after error"""
        call_count = [0]

        from nano_agent.llm import LLMBackend

        class FailOnceBackend(LLMBackend):
            def complete(self, messages, tools=None, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise RuntimeError("first fails")
                return {"content": "ok", "tool_calls": []}

        agent = Agent("t", "t", llm=LLM(FailOnceBackend()), verbose=False)
        results = agent.run_batch(["fail", "ok"])

        assert len(results) == 2
        assert results[0]["success"] is False
        assert "first fails" in results[0]["error"]
        assert results[1]["success"] is True

    def test_batch_result_structure(self):
        """Each result has required keys"""
        agent = Agent("t", "t", llm=LLM.mock(), verbose=False)
        results = agent.run_batch(["hi"])

        r = results[0]
        assert "input" in r
        assert "response" in r
        assert "success" in r
        assert "error" in r

    def test_batch_updates_conversation_history(self):
        """Batch processes all inputs through conversation history"""
        agent = Agent("t", "t", llm=LLM.mock(), verbose=False)
        agent.run_batch(["a", "b", "c"])

        # 3 user + 3 assistant = 6 messages
        assert len(agent._conversation_history) == 6


# ── F10: summary ──


class TestSummary:
    """Agent.summary — conversation summary"""

    def test_summary_empty_agent(self):
        """Summary of fresh agent has zero stats"""
        agent = Agent("mybot", "test", llm=LLM.mock(), verbose=False)
        s = agent.summary()

        assert s["agent_name"] == "mybot"
        assert s["turn_count"] == 0
        assert s["total_messages"] == 0
        assert s["user_messages"] == 0
        assert s["assistant_messages"] == 0

    def test_summary_after_single_run(self):
        """Summary reflects one conversation turn"""
        agent = Agent("bot", "test", llm=LLM.mock(), verbose=False)
        agent.run("hello")

        s = agent.summary()
        assert s["turn_count"] == 1
        assert s["user_messages"] == 1
        assert s["assistant_messages"] == 1
        assert s["total_messages"] == 2

    def test_summary_after_batch(self):
        """Summary reflects batch processing"""
        agent = Agent("bot", "test", llm=LLM.mock(), verbose=False)
        agent.run_batch(["a", "b", "c"])

        s = agent.summary()
        assert s["turn_count"] == 3
        assert s["user_messages"] == 3
        assert s["assistant_messages"] == 3
        assert s["total_messages"] == 6

    def test_summary_total_chars(self):
        """Total chars equals sum of all message lengths"""
        agent = Agent("bot", "test", llm=LLM.mock(), verbose=False)
        agent.run("hello")

        s = agent.summary()
        expected = sum(len(m["content"]) for m in agent._conversation_history)
        assert s["total_chars"] == expected

    def test_summary_tool_count(self):
        """Summary reports registered tool count"""
        from nano_agent.tools import Tool

        def my_tool():
            """A tool"""
            return "ok"

        t = Tool(name="test_tool", description="test", func=my_tool, parameters={})
        agent = Agent("bot", "test", llm=LLM.mock(), tools=[t], verbose=False)

        s = agent.summary()
        assert s["tool_count"] == 1

    def test_summary_memory_count(self):
        """Summary reports memory entry count"""
        agent = Agent("bot", "test", llm=LLM.mock(), verbose=False)
        agent.run("hello")  # adds a memory entry

        s = agent.summary()
        assert s["memory_count"] >= 1

    def test_summary_recent_previews(self):
        """Recent entries have role and preview"""
        agent = Agent("bot", "test", llm=LLM.mock(), verbose=False)
        agent.run("hello world")

        s = agent.summary()
        assert len(s["recent"]) > 0
        for entry in s["recent"]:
            assert "role" in entry
            assert "preview" in entry
            assert isinstance(entry["preview"], str)

    def test_summary_recent_truncation(self):
        """Long messages are truncated with ..."""
        agent = Agent("bot", "test", llm=LLM.mock(), verbose=False)
        long_input = "x" * 200
        agent.run(long_input)

        s = agent.summary()
        user_recent = [e for e in s["recent"] if e["role"] == "user"]
        assert len(user_recent) > 0
        assert len(user_recent[0]["preview"]) <= 83  # 80 + "..."
        assert user_recent[0]["preview"].endswith("...")

    def test_summary_after_reset(self):
        """Summary shows zero after reset"""
        agent = Agent("bot", "test", llm=LLM.mock(), verbose=False)
        agent.run("hello")
        agent.reset()

        s = agent.summary()
        assert s["turn_count"] == 0
        assert s["total_messages"] == 0
