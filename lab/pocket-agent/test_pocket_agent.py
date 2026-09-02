#!/usr/bin/env python3
"""Tests for pocket_agent.py — ToolRegistry, Memory, MockLLM routing, PocketAgent loop."""

import pytest

from pocket_agent import Memory, MockLLM, PocketAgent, ToolRegistry


# ── ToolRegistry ─────────────────────────────────────────────

class TestToolRegistry:
    def test_register_plain_function_schema(self):
        reg = ToolRegistry()

        @reg.register(description="add numbers")
        def add(a: int, b: int) -> int:
            return a + b

        schemas = reg.list_schemas()
        assert len(schemas) == 1
        fn = schemas[0]["function"]
        assert fn["name"] == "add"
        assert fn["description"] == "add numbers"
        assert fn["parameters"]["required"] == ["a", "b"]
        assert fn["parameters"]["properties"] == {"a": {"type": "integer"}, "b": {"type": "integer"}}

    def test_register_default_param_not_required(self):
        reg = ToolRegistry()

        @reg.register()
        def greet(name: str, punctuation: str = "!") -> str:
            return name + punctuation

        params = reg.list_schemas()[0]["function"]["parameters"]
        assert params["required"] == ["name"]
        assert "punctuation" in params["properties"]

    def test_docstring_fallback_description(self):
        reg = ToolRegistry()

        @reg.register()
        def documented() -> str:
            """Doc becomes description."""
            return ""

        assert reg.list_schemas()[0]["function"]["description"] == "Doc becomes description."

    def test_get_miss_returns_none(self):
        assert ToolRegistry().get("nope") is None

    def test_execute_returns_str(self):
        reg = ToolRegistry()

        @reg.register()
        def shout(text: str) -> str:
            return text.upper()

        assert reg.execute("shout", {"text": "hi"}) == "HI"

    def test_execute_unknown_tool_error_string(self):
        result = ToolRegistry().execute("ghost", {})
        assert "unknown tool" in result

    def test_execute_exception_caught_as_error_string(self):
        reg = ToolRegistry()

        @reg.register()
        def boom() -> str:
            raise ValueError("kapow")

        assert "kapow" in reg.execute("boom", {})

    def test_execute_missing_required_arg_is_error_string(self):
        reg = ToolRegistry()

        @reg.register()
        def needs_arg(x: str) -> str:
            return x

        assert "Error" in reg.execute("needs_arg", {})


# ── Memory ───────────────────────────────────────────────────

class TestMemory:
    def test_store_and_recent(self):
        m = Memory()
        m.store("alpha")
        m.store("beta")
        assert m.recent(2) == [e for e in m.entries][-2:]

    def test_recall_matches_keywords(self):
        m = Memory()
        m.store("the weather in Paris is nice")
        m.store("unrelated grocery list")
        hits = m.recall("weather Paris")
        assert len(hits) == 1
        assert "Paris" in hits[0]

    def test_recall_no_match_returns_empty(self):
        m = Memory()
        m.store("totally different")
        assert m.recall("zzz qqq") == []

    def test_recall_top_k_limits_results(self):
        m = Memory()
        for i in range(5):
            m.store(f"topic shared {i}")
        assert len(m.recall("topic shared", top_k=2)) == 2

    def test_max_entries_evicts_oldest_fifo(self):
        m = Memory(max_entries=3)
        for i in range(5):
            m.store(f"e{i}")
        assert len(m.entries) == 3
        joined = "\n".join(m.entries)
        assert "e0" not in joined and "e1" not in joined
        assert "e4" in joined

    def test_recent_zero_returns_empty(self):
        """recent(0) must return [], not everything (list[-0:] == list[0:] gotcha)."""
        m = Memory()
        m.store("one")
        m.store("two")
        assert m.recent(0) == []

    def test_max_entries_zero_store_does_not_crash(self):
        """Constructor accepts max_entries=0; store() must not IndexError."""
        m = Memory(max_entries=0)
        m.store("x")
        assert m.entries == []

    def test_recent_more_than_len_returns_all(self):
        m = Memory()
        m.store("only")
        assert m.recent(10) == m.entries


# ── MockLLM routing ──────────────────────────────────────────

class TestMockLLM:
    def _agent(self) -> PocketAgent:
        return PocketAgent(name="t")

    def test_weather_route_emits_tool_call(self):
        agent = self._agent()
        resp = agent.llm.respond([{"role": "user", "content": "what is the weather"}])
        assert resp["tool_calls"][0]["name"] == "get_weather"
        assert "city" in resp["tool_calls"][0]["arguments"]

    def test_math_route_emits_tool_call(self):
        agent = self._agent()
        resp = agent.llm.respond([{"role": "user", "content": "please calculate 1+1"}])
        assert resp["tool_calls"][0]["name"] == "calculate"

    def test_tool_result_message_gets_summarized(self):
        agent = self._agent()
        resp = agent.llm.respond([{"role": "tool", "name": "get_weather", "content": "sunny"}])
        assert resp["role"] == "assistant"
        assert "get_weather" in resp["content"]
        assert "sunny" in resp["content"]

    def test_fallback_no_tool_calls(self):
        agent = self._agent()
        resp = agent.llm.respond([{"role": "user", "content": "hello there"}])
        assert "tool_calls" not in resp


# ── PocketAgent loop ─────────────────────────────────────────

class TestPocketAgent:
    def _with_weather_tool(self) -> PocketAgent:
        agent = PocketAgent(name="t")

        @agent.tool(description="weather")
        def get_weather(city: str) -> str:
            return "sunny"

        return agent

    def test_run_completes_tool_roundtrip(self, capsys):
        agent = self._with_weather_tool()
        result = agent.run("what's the weather")
        assert "get_weather" in result
        assert "sunny" in result
        # history: user, thought, tool result, summary
        roles = [h["role"] for h in agent.history]
        assert roles == ["user", "assistant", "tool", "assistant"]

    def test_run_stores_memory_entries(self):
        agent = self._with_weather_tool()
        agent.run("what's the weather")
        assert any("get_weather" in e for e in agent.memory.entries)
        assert any("Final answer" in e for e in agent.memory.entries)

    def test_run_plain_input_no_tools(self):
        agent = PocketAgent(name="t")
        result = agent.run("hello there")
        assert "tool_calls" not in str(result)
        roles = [h["role"] for h in agent.history]
        assert roles == ["user", "assistant"]

    def test_max_iterations_reached(self):
        agent = PocketAgent(name="t", max_iterations=2)

        def always_tool(messages):
            return {"role": "assistant", "content": "thinking",
                    "tool_calls": [{"name": "loop", "arguments": {}}]}

        agent.llm.respond = always_tool

        @agent.tool()
        def loop() -> str:
            return "ok"

        assert agent.run("anything") == "⚠️ Max iterations reached"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
