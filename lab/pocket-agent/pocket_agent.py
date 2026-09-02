#!/usr/bin/env python3
"""
🧪 Pocket Agent - A minimal AI agent framework in ~150 lines
Demonstrates: Tool use, ReAct loop, Memory, Streaming thoughts
"""

import json, time, re, inspect, textwrap
from dataclasses import dataclass, field
from typing import Callable, Any

# ── Tool System ──────────────────────────────────────────────

@dataclass
class Tool:
    name: str
    func: Callable
    description: str
    parameters: dict  # JSON Schema

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, func: Callable | None = None, description: str = ""):
        """Register a tool. Works as bare decorator (@reg.register) or
        parameterized (@reg.register(description="..."))."""
        if func is None:
            def decorator(f: Callable) -> Callable:
                return self._add(f, description)
            return decorator
        return self._add(func, description)

    def _add(self, func: Callable, description: str) -> Callable:
        sig = inspect.signature(func)
        props, required = {}, []
        for name, param in sig.parameters.items():
            if name == "self": continue
            t = param.annotation if param.annotation != inspect.Parameter.empty else str
            type_map = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array"}
            props[name] = {"type": type_map.get(t, "string")}
            if param.default == inspect.Parameter.empty:
                required.append(name)
        schema = {"type": "object", "properties": props, "required": required}
        self._tools[func.__name__] = Tool(func.__name__, func, description or func.__doc__ or "", schema)
        return func

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_schemas(self) -> list[dict]:
        return [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}} for t in self._tools.values()]

    def execute(self, name: str, args: dict) -> str:
        tool = self.get(name)
        if not tool: return f"Error: unknown tool '{name}'"
        try:
            result = tool.func(**args)
            return str(result)
        except Exception as e:
            return f"Error: {e}"

# ── Memory System ────────────────────────────────────────────

class Memory:
    def __init__(self, max_entries: int = 100):
        self.entries: list[str] = []
        self.max = max_entries

    def store(self, thought: str):
        if self.max <= 0:
            return  # capacity zero remembers nothing
        if len(self.entries) >= self.max:
            self.entries.pop(0)
        self.entries.append(f"[{time.strftime('%H:%M:%S')}] {thought}")

    def recall(self, query: str, top_k: int = 3) -> list[str]:
        """Simple keyword-based recall (swap for vector search IRL)"""
        words = set(query.lower().split())
        scored = [(sum(w in entry.lower() for w in words), entry) for entry in self.entries]
        scored.sort(key=lambda x: -x[0])
        return [e for s, e in scored[:top_k] if s > 0]

    def recent(self, n: int = 5) -> list[str]:
        if n <= 0:
            return []
        return self.entries[-n:]

# ── Mock LLM (swap this for real API) ───────────────────────

class MockLLM:
    """Simulates an LLM that can reason and call tools.
    Replace this class with real API calls (OpenAI, Anthropic, etc.)"""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def respond(self, messages: list[dict]) -> dict:
        # If last message is a tool result, summarize it
        if messages and messages[-1].get("role") == "tool":
            result = messages[-1]["content"]
            tool_name = messages[-1].get("name", "tool")
            return {"role": "assistant", "content": f"✅ {tool_name} 返回结果: {result}"}

        last = messages[-1]["content"].lower() if messages else ""

        if any(w in last for w in ["weather", "温度", "天气"]):
            tool_name, tool_args = "get_weather", {"city": "Beijing"}
        elif any(w in last for w in ["calculate", "计算", "math", "算"]):
            tool_name, tool_args = "calculate", {"expression": "42 * 137"}
        elif any(w in last for w in ["time", "时间", "几点"]):
            tool_name, tool_args = "current_time", {}
        elif any(w in last for w in ["remember", "记住", "记忆"]):
            return {"role": "assistant", "content": f"💭 我的记忆中有 {len(messages)} 轮对话。我用关键词匹配来回忆（生产环境用向量嵌入）。试试问我天气、数学、时间或搜索！"}
        elif any(w in last for w in ["search", "搜索", "查找"]):
            tool_name, tool_args = "web_search", {"query": last[:50]}
        else:
            return {"role": "assistant", "content": f"🤔 收到: '{last[:80]}'。试试问我天气、数学、时间、搜索或记忆！"}

        return {
            "role": "assistant",
            "content": f"💭 让我用 {tool_name} 来查一下...",
            "tool_calls": [{"name": tool_name, "arguments": tool_args}]
        }

# ── Agent Core ───────────────────────────────────────────────

class PocketAgent:
    def __init__(self, name: str = "PocketAgent", max_iterations: int = 5):
        self.name = name
        self.registry = ToolRegistry()
        self.memory = Memory()
        self.llm = MockLLM(self.registry)
        self.max_iterations = max_iterations
        self.history: list[dict] = []

    def tool(self, description: str = ""):
        """Decorator to register a tool"""
        def wrapper(func):
            self.registry.register(func, description)
            return func
        return wrapper

    def run(self, user_input: str) -> str:
        self.history.append({"role": "user", "content": user_input})

        for i in range(self.max_iterations):
            response = self.llm.respond(self.history)
            self.history.append({"role": "assistant", "content": response["content"]})
            print(f"  {response['content']}")

            if "tool_calls" not in response:
                self.memory.store(f"Final answer: {response['content'][:100]}")
                return response["content"]

            # Execute tool calls
            for call in response["tool_calls"]:
                name, args = call["name"], call["arguments"]
                print(f"  🔧 Calling {name}({args})...")
                result = self.registry.execute(name, args)
                print(f"  📋 Result: {result}")
                self.history.append({"role": "tool", "name": name, "content": result})
                self.memory.store(f"Tool {name}({args}) → {result[:100]}")

        return "⚠️ Max iterations reached"

# ── Demo ─────────────────────────────────────────────────────

def main():
    agent = PocketAgent(name="🧪 Catalyst")

    # Register built-in tools
    @agent.tool(description="Get current weather for a city")
    def get_weather(city: str) -> str:
        """Returns simulated weather data"""
        return json.dumps({"city": city, "temp": "22°C", "condition": "sunny", "humidity": "45%"})

    @agent.tool(description="Evaluate a math expression")
    def calculate(expression: str) -> str:
        try:
            result = eval(expression, {"__builtins__": {}}, {})
            return f"{expression} = {result}"
        except:
            return f"Could not evaluate: {expression}"

    @agent.tool(description="Get current date and time")
    def current_time() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S %Z")

    @agent.tool(description="Search the web (simulated)")
    def web_search(query: str) -> str:
        return json.dumps({"results": [f"Simulated result for '{query}': ..."], "source": "mock"})

    print(f"{'='*50}")
    print(f"  {agent.name} - Pocket Agent Demo")
    print(f"  Tools: {[t.name for t in agent.registry._tools.values()]}")
    print(f"{'='*50}\n")

    # Interactive loop
    test_inputs = [
        "今天北京天气怎么样？",
        "帮我算一下 42 * 137",
        "现在几点了？",
        "搜索 AI agent 2026",
        "你有什么记忆功能？",
    ]

    for inp in test_inputs:
        print(f"👤 {inp}")
        result = agent.run(inp)
        print(f"✅ {result}\n")

    # Show memory
    print("─── Memory ───")
    for entry in agent.memory.recent(10):
        print(f"  {entry}")

if __name__ == "__main__":
    main()
