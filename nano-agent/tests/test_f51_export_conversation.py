"""Tests for F51: Agent.export_conversation(format)."""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.agent import Agent
from nano_agent.llm import LLM


def _make_agent_with_history():
    """Create an agent with some conversation history."""
    llm = LLM.mock()
    agent = Agent("TestBot", "You are a test bot.", llm=llm, verbose=False)
    # Simulate conversation history
    agent._conversation_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "It's 4."},
    ]
    return agent


class TestF51ExportConversation:
    """F51: Agent.export_conversation."""

    def test_export_markdown_basic(self):
        agent = _make_agent_with_history()
        result = agent.export_conversation("markdown")
        assert isinstance(result, str)
        assert "# Conversation: TestBot" in result
        assert "Hello" in result
        assert "Hi there!" in result

    def test_export_markdown_default(self):
        agent = _make_agent_with_history()
        result = agent.export_conversation()
        assert "# Conversation: TestBot" in result

    def test_export_markdown_role_labels(self):
        agent = _make_agent_with_history()
        md = agent.export_conversation("markdown")
        assert "🧑 User" in md
        assert "🤖 Assistant" in md

    def test_export_json_basic(self):
        agent = _make_agent_with_history()
        result = agent.export_conversation("json")
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 4
        assert parsed[0]["role"] == "user"
        assert parsed[0]["content"] == "Hello"

    def test_export_json_roundtrip(self):
        agent = _make_agent_with_history()
        json_str = agent.export_conversation("json")
        parsed = json.loads(json_str)
        # Verify it matches internal history
        assert parsed == agent._conversation_history

    def test_export_empty_conversation_markdown(self):
        llm = LLM.mock()
        agent = Agent("Empty", "test", llm=llm, verbose=False)
        result = agent.export_conversation("markdown")
        assert "# Conversation: Empty" in result

    def test_export_empty_conversation_json(self):
        llm = LLM.mock()
        agent = Agent("Empty", "test", llm=llm, verbose=False)
        result = agent.export_conversation("json")
        parsed = json.loads(result)
        assert parsed == []

    def test_export_markdown_preserves_content(self):
        agent = _make_agent_with_history()
        md = agent.export_conversation("markdown")
        # All content should appear
        assert "Hello" in md
        assert "Hi there!" in md
        assert "What is 2+2?" in md
        assert "It's 4." in md

    def test_export_after_run(self):
        """export_conversation should reflect actual run() output."""
        llm = LLM.mock()
        agent = Agent("RunBot", "test instructions", llm=llm, verbose=False)
        agent.run("test input")
        md = agent.export_conversation("markdown")
        assert "test input" in md
