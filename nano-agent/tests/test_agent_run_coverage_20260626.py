"""
Agent.run() end-to-end coverage + OpenAIBackend.complete() tool format
Targets: run loop flow, memory persistence after run, iteration exhaustion,
  tool execution success path, OpenAIBackend tool serialization, MockBackend keyword trigger.
"""

import os
import sys
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from nano_agent.agent import Agent
from nano_agent.llm import LLM, MockBackend, OpenAIBackend, LLMBackend
from nano_agent.memory import Memory
from nano_agent.tools import Tool, clear_tools


# ---------------------------------------------------------------------------
# Agent.run() — full loop coverage
# ---------------------------------------------------------------------------

class TestAgentRunContextFlow:
    """Agent.run() passes context through to messages."""

    def test_run_with_context_reaches_system_prompt(self):
        """run(context=...) appears in the system prompt seen by the backend."""
        seen_messages = []

        class CaptureBackend(LLMBackend):
            def complete(self, messages, tools=None, **kwargs):
                seen_messages.extend(messages)
                return {"content": "done", "tool_calls": [], "usage": {}}

        agent = Agent(
            name="CtxBot", instructions="follow instructions",
            llm=LLM(CaptureBackend()), verbose=False
        )
        agent.run("hello", context="secret-ctx-42")
        system_prompt = seen_messages[0]["content"]
        assert "secret-ctx-42" in system_prompt


class TestAgentRunSavesMemory:
    """Agent.run() persists interaction to Memory."""

    def test_run_adds_entry_to_memory(self):
        """After run(), memory has a new entry with user input and response."""
        agent = Agent(name="M", instructions="test", verbose=False)
        assert agent.memory.count() == 0
        agent.run("what is 1+1?")
        assert agent.memory.count() == 1
        entry = agent.memory.get_all()[0]
        assert "what is 1+1?" in entry.content
        assert "模拟回复" in entry.content  # MockBackend response

    def test_run_memory_metadata_contains_agent_name(self):
        """Memory entry from run() includes agent name in metadata."""
        agent = Agent(name="NamedBot", instructions="test", verbose=False)
        agent.run("hi")
        entry = agent.memory.get_all()[0]
        assert entry.metadata.get("agent") == "NamedBot"


class TestAgentRunConversationHistory:
    """Agent.run() manages conversation history."""

    def test_run_appends_user_and_assistant_to_history(self):
        """After a single run(), history has 1 user + 1 assistant entry."""
        agent = Agent(name="H", instructions="test", verbose=False)
        agent.run("question?")
        assert len(agent._conversation_history) == 2
        assert agent._conversation_history[0]["role"] == "user"
        assert agent._conversation_history[0]["content"] == "question?"
        assert agent._conversation_history[1]["role"] == "assistant"

    def test_run_multi_turn_accumulates_history(self):
        """Two run() calls produce 4 history entries (2 user + 2 assistant)."""
        agent = Agent(name="H2", instructions="test", verbose=False)
        agent.run("first")
        agent.run("second")
        assert len(agent._conversation_history) == 4
        assert agent.turn_count == 2


class TestAgentRunIterationExhaustion:
    """Agent.run() handles max_iterations gracefully."""

    def test_run_stops_at_max_iterations_with_tool_calls(self):
        """When LLM always returns tool calls, run respects max_iterations."""
        call_count = {"n": 0}

        class AlwaysToolBackend(LLMBackend):
            def complete(self, messages, tools=None, **kwargs):
                call_count["n"] += 1
                return {
                    "content": "",
                    "tool_calls": [{
                        "id": f"call_{call_count['n']}",
                        "name": "noop",
                        "arguments": "{}"
                    }],
                    "usage": {}
                }

        noop_tool = Tool(name="noop", description="does nothing", func=lambda: "ok", parameters={})
        agent = Agent(
            name="Loop", instructions="test", verbose=False,
            llm=LLM(AlwaysToolBackend()),
            tools=[noop_tool],
            max_iterations=3
        )
        result = agent.run("trigger loop")
        # All 3 iterations consumed
        assert call_count["n"] == 3
        # Final response is from last response content (empty string)
        assert isinstance(result, str)


class TestAgentRunToolExecutionSuccess:
    """Agent.run() executes tools and feeds results back."""

    def test_run_executes_tool_and_continues(self):
        """run() calls the tool and the tool result appears in messages."""
        seen_tool_results = []

        class OneToolThenAnswer(LLMBackend):
            def __init__(self):
                self._call = 0

            def complete(self, messages, tools=None, **kwargs):
                self._call += 1
                if self._call == 1:
                    return {
                        "content": "",
                        "tool_calls": [{
                            "id": "tc_1",
                            "name": "greet",
                            "arguments": json.dumps({"name": "World"})
                        }],
                        "usage": {}
                    }
                # Second call: check tool result was added
                tool_msgs = [m for m in messages if m["role"] == "tool"]
                if tool_msgs:
                    seen_tool_results.append(tool_msgs[0]["content"])
                return {"content": "Hello World!", "tool_calls": [], "usage": {}}

        def greet(name):
            return f"Hi {name}!"

        greet_tool = Tool(name="greet", description="greets", func=greet,
                          parameters={"name": {"type": "string"}})

        agent = Agent(
            name="ToolBot", instructions="use tools", verbose=False,
            llm=LLM(OneToolThenAnswer()),
            tools=[greet_tool]
        )
        result = agent.run("greet World")
        assert "Hello World!" in result or result  # got a response
        assert len(seen_tool_results) == 1
        assert "Hi World!" in seen_tool_results[0]


class TestAgentRunOnStepCallback:
    """Agent.run() invokes on_step callback."""

    def test_on_step_called_without_tools(self):
        """on_step fires when agent finishes without tool calls."""
        steps = []
        agent = Agent(name="CB", instructions="test", verbose=False)
        agent.on_step = lambda step: steps.append(step)
        agent.run("hello")
        assert len(steps) == 1
        assert steps[0]["iteration"] == 1
        assert steps[0]["tool_calls"] == []

    def test_on_step_called_with_tool_calls(self):
        """on_step fires with tool call names when tools are used."""
        steps = []

        class OneToolThenAnswer(LLMBackend):
            def __init__(self):
                self._call = 0
            def complete(self, messages, tools=None, **kwargs):
                self._call += 1
                if self._call == 1:
                    return {
                        "content": "",
                        "tool_calls": [{
                            "id": "tc1", "name": "ping", "arguments": "{}"
                        }],
                        "usage": {}
                    }
                return {"content": "pong", "tool_calls": [], "usage": {}}

        ping_tool = Tool(name="ping", description="ping", func=lambda: "pong", parameters={})
        agent = Agent(
            name="CB2", instructions="test", verbose=False,
            llm=LLM(OneToolThenAnswer()),
            tools=[ping_tool]
        )
        agent.on_step = lambda step: steps.append(step)
        agent.run("do ping")
        # Step with tool call (iteration 1) + final step (iteration 2)
        tool_steps = [s for s in steps if s["tool_calls"]]
        assert len(tool_steps) >= 1
        assert "ping" in tool_steps[0]["tool_calls"]


# ---------------------------------------------------------------------------
# OpenAIBackend.complete() — tool format conversion
# ---------------------------------------------------------------------------

class TestOpenAIBackendComplete:
    """OpenAIBackend.complete() tool serialization and response parsing."""

    def _make_backend(self):
        """Create backend with mocked openai client."""
        with patch.dict('sys.modules', {'openai': MagicMock()}):
            backend = OpenAIBackend(api_key="sk-test")
        return backend

    def test_complete_no_tools(self):
        """complete() without tools sends tools=None to API."""
        backend = self._make_backend()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "hello"
        mock_resp.choices[0].message.tool_calls = None
        mock_resp.usage.prompt_tokens = 5
        mock_resp.usage.completion_tokens = 3
        mock_resp.usage.total_tokens = 8
        backend.client.chat.completions.create = MagicMock(return_value=mock_resp)

        result = backend.complete(messages=[{"role": "user", "content": "hi"}])
        assert result["content"] == "hello"
        assert result["tool_calls"] == []
        assert result["usage"]["total_tokens"] == 8

    def test_complete_with_tools_serializes_format(self):
        """complete() converts tool dict to OpenAI function format."""
        backend = self._make_backend()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = None
        mock_resp.choices[0].message.tool_calls = None
        mock_resp.usage.prompt_tokens = 5
        mock_resp.usage.completion_tokens = 3
        mock_resp.usage.total_tokens = 8
        backend.client.chat.completions.create = MagicMock(return_value=mock_resp)

        tools = [
            {"name": "search", "description": "Search web", "parameters": {"query": {"type": "string"}}},
            {"name": "calc", "description": "Calculator", "parameters": {"expr": {"type": "string"}}},
        ]
        backend.complete(messages=[{"role": "user", "content": "test"}], tools=tools)

        call_kwargs = backend.client.chat.completions.create.call_args[1]
        assert call_kwargs["tools"] is not None
        assert len(call_kwargs["tools"]) == 2
        assert call_kwargs["tools"][0]["type"] == "function"
        assert call_kwargs["tools"][0]["function"]["name"] == "search"
        assert call_kwargs["tools"][1]["function"]["name"] == "calc"

    def test_complete_parses_tool_calls(self):
        """complete() extracts tool_calls from OpenAI response."""
        backend = self._make_backend()

        mock_call = MagicMock()
        mock_call.id = "call_abc"
        mock_call.function.name = "search"
        mock_call.function.arguments = '{"query": "cats"}'

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = ""
        mock_resp.choices[0].message.tool_calls = [mock_call]
        mock_resp.usage.prompt_tokens = 10
        mock_resp.usage.completion_tokens = 20
        mock_resp.usage.total_tokens = 30
        backend.client.chat.completions.create = MagicMock(return_value=mock_resp)

        result = backend.complete(
            messages=[{"role": "user", "content": "搜索 cats"}],
            tools=[{"name": "search", "description": "Search", "parameters": {"query": {"type": "string"}}}]
        )
        assert len(result["tool_calls"]) == 1
        tc = result["tool_calls"][0]
        assert tc["id"] == "call_abc"
        assert tc["name"] == "search"
        assert json.loads(tc["arguments"]) == {"query": "cats"}

    def test_complete_passes_kwargs_to_client(self):
        """complete() forwards extra kwargs to OpenAI client."""
        backend = self._make_backend()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "ok"
        mock_resp.choices[0].message.tool_calls = None
        mock_resp.usage.prompt_tokens = 1
        mock_resp.usage.completion_tokens = 1
        mock_resp.usage.total_tokens = 2
        backend.client.chat.completions.create = MagicMock(return_value=mock_resp)

        backend.complete(
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.7,
            max_tokens=200
        )
        call_kwargs = backend.client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 200


# ---------------------------------------------------------------------------
# MockBackend — keyword-triggered tool call path
# ---------------------------------------------------------------------------

class TestMockBackendToolTrigger:
    """MockBackend tool-calling behavior."""

    def test_triggers_tool_when_keyword_present(self):
        """MockBackend returns tool_call when message contains '搜索' and tools given."""
        backend = MockBackend()
        tools = [{"name": "web_search", "description": "Search the web"}]
        result = backend.complete(
            messages=[{"role": "user", "content": "请搜索 AI news"}],
            tools=tools
        )
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "web_search"
        assert result["content"] == ""

    def test_no_tool_call_without_keyword(self):
        """MockBackend returns plain content when no '搜索' keyword."""
        backend = MockBackend()
        tools = [{"name": "web_search", "description": "Search the web"}]
        result = backend.complete(
            messages=[{"role": "user", "content": "just chat"}],
            tools=tools
        )
        assert result["tool_calls"] == []
        assert result["content"] != ""

    def test_no_tool_call_without_tools(self):
        """MockBackend returns plain content when no tools provided."""
        backend = MockBackend()
        result = backend.complete(
            messages=[{"role": "user", "content": "搜索 something"}],
            tools=None
        )
        assert result["tool_calls"] == []

    def test_empty_messages(self):
        """MockBackend handles empty message list."""
        backend = MockBackend()
        result = backend.complete(messages=[])
        assert "content" in result
        assert result["tool_calls"] == []

    def test_usage_format(self):
        """MockBackend returns expected usage fields."""
        backend = MockBackend()
        result = backend.complete(messages=[{"role": "user", "content": "hi"}])
        assert "usage" in result
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 20
        assert result["usage"]["total_tokens"] == 30
