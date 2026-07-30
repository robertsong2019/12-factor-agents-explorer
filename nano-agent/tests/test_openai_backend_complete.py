"""
Tests for OpenAIBackend.complete — tool format conversion and response parsing.
Uses unittest.mock to avoid real API calls.
"""

import sys
import os
import json
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.llm import LLM, MockBackend, LLMBackend, OpenAIBackend


class TestOpenAIBackendComplete:
    """Test OpenAIBackend.complete with mocked OpenAI client."""

    def _make_backend(self):
        """Create an OpenAIBackend with a mocked OpenAI client."""
        with patch.dict(sys.modules, {"openai": MagicMock()}):
            backend = OpenAIBackend(api_key="fake", model="gpt-4")
            # Replace the client with a mock
            backend.client = MagicMock()
            return backend

    def test_complete_no_tools(self):
        """complete() without tools should pass messages and return parsed response."""
        backend = self._make_backend()

        # Mock response
        mock_msg = MagicMock()
        mock_msg.content = "Hello!"
        mock_msg.tool_calls = None
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage.prompt_tokens = 5
        mock_resp.usage.completion_tokens = 3
        mock_resp.usage.total_tokens = 8

        backend.client.chat.completions.create.return_value = mock_resp

        result = backend.complete(
            messages=[{"role": "user", "content": "hi"}]
        )

        assert result["content"] == "Hello!"
        assert result["tool_calls"] == []
        assert result["usage"]["total_tokens"] == 8

    def test_complete_with_tools(self):
        """complete() with tools should convert to OpenAI function format."""
        backend = self._make_backend()

        mock_msg = MagicMock()
        mock_msg.content = None
        mock_msg.tool_calls = None
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage.prompt_tokens = 10
        mock_resp.usage.completion_tokens = 0
        mock_resp.usage.total_tokens = 10

        backend.client.chat.completions.create.return_value = mock_resp

        tools = [
            {
                "name": "search",
                "description": "Search the web",
                "parameters": {"query": {"type": "string"}}
            }
        ]

        result = backend.complete(
            messages=[{"role": "user", "content": "search for cats"}],
            tools=tools
        )

        # Verify the create call received tools in OpenAI format
        call_kwargs = backend.client.chat.completions.create.call_args
        passed_tools = call_kwargs.kwargs.get("tools")
        assert passed_tools is not None
        assert passed_tools[0]["type"] == "function"
        assert passed_tools[0]["function"]["name"] == "search"
        assert "query" in passed_tools[0]["function"]["parameters"]["properties"]

    def test_complete_parses_tool_calls(self):
        """complete() should parse tool_calls from response."""
        backend = self._make_backend()

        mock_call = MagicMock()
        mock_call.id = "call_123"
        mock_call.function.name = "get_weather"
        mock_call.function.arguments = '{"city": "Tokyo"}'

        mock_msg = MagicMock()
        mock_msg.content = ""
        mock_msg.tool_calls = [mock_call]
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage.prompt_tokens = 10
        mock_resp.usage.completion_tokens = 20
        mock_resp.usage.total_tokens = 30

        backend.client.chat.completions.create.return_value = mock_resp

        result = backend.complete(
            messages=[{"role": "user", "content": "weather in Tokyo"}],
            tools=[{"name": "get_weather", "description": "Get weather", "parameters": {"city": {"type": "string"}}}]
        )

        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["id"] == "call_123"
        assert result["tool_calls"][0]["name"] == "get_weather"
        assert json.loads(result["tool_calls"][0]["arguments"])["city"] == "Tokyo"

    def test_complete_passes_kwargs(self):
        """complete() should forward extra kwargs to the OpenAI API."""
        backend = self._make_backend()

        mock_msg = MagicMock()
        mock_msg.content = "ok"
        mock_msg.tool_calls = None
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage.prompt_tokens = 1
        mock_resp.usage.completion_tokens = 1
        mock_resp.usage.total_tokens = 2

        backend.client.chat.completions.create.return_value = mock_resp

        backend.complete(
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.5,
            max_tokens=100
        )

        call_kwargs = backend.client.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.5
        assert call_kwargs.kwargs.get("max_tokens") == 100

    def test_complete_passes_model(self):
        """complete() should use the configured model."""
        backend = self._make_backend()

        mock_msg = MagicMock()
        mock_msg.content = "ok"
        mock_msg.tool_calls = None
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage.prompt_tokens = 1
        mock_resp.usage.completion_tokens = 1
        mock_resp.usage.total_tokens = 2

        backend.client.chat.completions.create.return_value = mock_resp

        backend.complete(messages=[{"role": "user", "content": "hi"}])

        call_kwargs = backend.client.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("model") == "gpt-4"

    def test_complete_multiple_tool_calls(self):
        """complete() should handle multiple tool calls in one response."""
        backend = self._make_backend()

        call1 = MagicMock()
        call1.id = "c1"
        call1.function.name = "search"
        call1.function.arguments = '{"q": "python"}'

        call2 = MagicMock()
        call2.id = "c2"
        call2.function.name = "translate"
        call2.function.arguments = '{"text": "hello", "lang": "ja"}'

        mock_msg = MagicMock()
        mock_msg.content = ""
        mock_msg.tool_calls = [call1, call2]
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage.prompt_tokens = 15
        mock_resp.usage.completion_tokens = 25
        mock_resp.usage.total_tokens = 40

        backend.client.chat.completions.create.return_value = mock_resp

        result = backend.complete(
            messages=[{"role": "user", "content": "search and translate"}],
            tools=[
                {"name": "search", "description": "Search", "parameters": {"q": {"type": "string"}}},
                {"name": "translate", "description": "Translate", "parameters": {"text": {"type": "string"}, "lang": {"type": "string"}}}
            ]
        )

        assert len(result["tool_calls"]) == 2
        assert result["tool_calls"][0]["name"] == "search"
        assert result["tool_calls"][1]["name"] == "translate"

    def test_complete_null_content(self):
        """complete() should convert None content to empty string."""
        backend = self._make_backend()

        mock_msg = MagicMock()
        mock_msg.content = None
        mock_msg.tool_calls = None
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage.prompt_tokens = 1
        mock_resp.usage.completion_tokens = 1
        mock_resp.usage.total_tokens = 2

        backend.client.chat.completions.create.return_value = mock_resp

        result = backend.complete(messages=[{"role": "user", "content": "hi"}])
        assert result["content"] == ""
