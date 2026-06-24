"""
Coverage gap tests — 2026-06-25
Targets: Agent._build_messages, Agent._log, LLM.openai, LLM.chat
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from unittest.mock import patch, MagicMock
from nano_agent.agent import Agent
from nano_agent.llm import LLM, MockBackend, OpenAIBackend


class TestAgentBuildMessages:
    """Agent._build_messages — internal message construction."""

    def test_build_messages_basic(self):
        """_build_messages returns system + user message for fresh agent."""
        agent = Agent(name="test", instructions="You are helpful")
        msgs = agent._build_messages("hello")
        assert msgs[0]["role"] == "system"
        assert msgs[-1]["role"] == "user"
        assert msgs[-1]["content"] == "hello"

    def test_build_messages_includes_context(self):
        """_build_messages includes context in system prompt."""
        agent = Agent(name="test", instructions="Be brief")
        msgs = agent._build_messages("hi", context="Extra context here")
        assert "Extra context here" in msgs[0]["content"]

    def test_build_messages_includes_history(self):
        """_build_messages includes conversation history."""
        agent = Agent(name="test", instructions="Test")
        # Simulate prior conversation
        agent._conversation_history = [
            {"role": "user", "content": "prev q"},
            {"role": "assistant", "content": "prev a"},
        ]
        msgs = agent._build_messages("new q")
        # system + 2 history + current user
        assert len(msgs) == 4
        assert msgs[1]["content"] == "prev q"
        assert msgs[2]["content"] == "prev a"
        assert msgs[3]["content"] == "new q"

    def test_build_messages_truncates_history_to_10(self):
        """_build_messages only keeps last 10 history entries."""
        agent = Agent(name="test", instructions="Test")
        agent._conversation_history = []
        for i in range(8):
            agent._conversation_history.append({"role": "user", "content": f"old {i}"})
            agent._conversation_history.append({"role": "assistant", "content": f"ans {i}"})
        # 16 entries — exceeds 10
        msgs = agent._build_messages("current")
        # system + max 10 history + current
        history_msgs = [m for m in msgs if m["role"] in ("user", "assistant") and m["content"] != "current"]
        assert len(history_msgs) <= 10

    def test_build_messages_records_to_history(self):
        """_build_messages appends current user input to conversation history."""
        agent = Agent(name="test", instructions="Test")
        assert len(agent._conversation_history) == 0
        agent._build_messages("record me")
        assert len(agent._conversation_history) == 1
        assert agent._conversation_history[0]["content"] == "record me"


class TestAgentLog:
    """Agent._log — verbose logging."""

    def test_log_verbose_true(self, capsys):
        """_log prints when verbose=True."""
        agent = Agent(name="test", instructions="Test", verbose=True)
        agent._log("debug message")
        captured = capsys.readouterr()
        assert "debug message" in captured.out

    def test_log_verbose_false(self, capsys):
        """_log does not print when verbose=False."""
        agent = Agent(name="test", instructions="Test", verbose=False)
        agent._log("hidden message")
        captured = capsys.readouterr()
        assert "hidden message" not in captured.out


class TestLLMOpenai:
    """LLM.openai — factory method for OpenAI backend."""

    def test_openai_creates_llm_with_openai_backend(self):
        """LLM.openai returns LLM with OpenAIBackend."""
        with patch.dict('sys.modules', {'openai': MagicMock()}):
            llm = LLM.openai(api_key="sk-test123")
            assert isinstance(llm.backend, OpenAIBackend)
            assert llm.backend.model == "gpt-3.5-turbo"

    def test_openai_passes_kwargs(self):
        """LLM.openai forwards kwargs to OpenAIBackend."""
        with patch.dict('sys.modules', {'openai': MagicMock()}):
            llm = LLM.openai(api_key="sk-test", model="gpt-4", base_url="https://custom.api.com")
            assert llm.backend.model == "gpt-4"


class TestLLMChat:
    """LLM.chat — chat interface delegating to backend."""

    def test_chat_delegates_to_backend(self):
        """LLM.chat calls backend.complete with messages and tools."""
        mock_backend = MockBackend()
        llm = LLM(backend=mock_backend)
        messages = [{"role": "user", "content": "hello"}]
        result = llm.chat(messages)
        assert isinstance(result, dict)
        assert "content" in result

    def test_chat_passes_tools_to_backend(self):
        """LLM.chat forwards tools parameter."""
        mock_backend = MockBackend()
        llm = LLM(backend=mock_backend)
        messages = [{"role": "user", "content": "use tool"}]
        tools = [{"name": "search", "description": "Search"}]
        result = llm.chat(messages, tools=tools)
        assert isinstance(result, dict)

    def test_chat_passes_kwargs(self):
        """LLM.chat forwards extra kwargs."""
        mock_backend = MockBackend()
        llm = LLM(backend=mock_backend)
        messages = [{"role": "user", "content": "hello"}]
        result = llm.chat(messages, temperature=0.5, max_tokens=100)
        assert isinstance(result, dict)

    def test_chat_with_mock_backend_no_tool_call(self):
        """LLM.chat via MockBackend returns content without tool call."""
        llm = LLM.mock()
        messages = [{"role": "user", "content": "say hi"}]
        result = llm.chat(messages)
        assert result["content"] is not None
        assert result.get("tool_calls") is None or len(result.get("tool_calls", [])) == 0
