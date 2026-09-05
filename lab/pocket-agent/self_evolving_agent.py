#!/usr/bin/env python3
"""
🧬 Self-Evolving Agent - 代码实验室实验
Agent 根据运行时需求动态生成并注册新工具。
模拟了 "Agent 可以写代码来扩展自己" 的核心概念。
"""

import json, time, hashlib, textwrap
from dataclasses import dataclass, field
from typing import Callable

# ── Dynamic Tool Generator ───────────────────────────────────

@dataclass
class EvolvingTool:
    name: str
    code: str           # Python source that defines the function
    func: Callable
    description: str
    generation: int = 0  # How many times this tool was refined
    hash: str = ""

    def __post_init__(self):
        self.hash = hashlib.md5(self.code.encode()).hexdigest()[:8]

class EvolutionEngine:
    """Generates new tool functions from natural language specs."""

    TOOL_TEMPLATES = {
        "fibonacci": textwrap.dedent("""\
            def fibonacci(n: int) -> str:
                a, b = 0, 1
                for _ in range(n):
                    a, b = b, a + b
                return f"Fibonacci({n}) = {a}"
        """),
        "prime_check": textwrap.dedent("""\
            def prime_check(n: int) -> str:
                if n < 2: return f"{n} is not prime"
                for i in range(2, int(n**0.5) + 1):
                    if n % i == 0: return f"{n} is not prime (divisible by {i})"
                return f"{n} is prime! ✓"
        """),
        "password_gen": textwrap.dedent("""\
            import secrets, string
            def password_gen(length: int = 16) -> str:
                chars = string.ascii_letters + string.digits + "!@#$%"
                pw = ''.join(secrets.choice(chars) for _ in range(length))
                strength = "strong" if length >= 16 else "medium" if length >= 10 else "weak"
                return json.dumps({"password": pw, "length": length, "strength": strength})
        """),
        "color_palette": textwrap.dedent("""\
            import random
            def color_palette(base_hue: int = 0) -> str:
                colors = []
                for i in range(5):
                    h = (base_hue + i * 72) % 360
                    s, l = 70, 55
                    colors.append(f"hsl({h}, {s}%, {l}%)")
                return json.dumps({"palette": colors, "base_hue": base_hue})
        """),
        "text_stats": textwrap.dedent("""\
            def text_stats(text: str) -> str:
                words = text.split()
                chars = len(text)
                sentences = text.count('.') + text.count('!') + text.count('？') + text.count('。')
                avg_word = sum(len(w) for w in words) / len(words) if words else 0
                return json.dumps({
                    "chars": chars, "words": len(words),
                    "sentences": max(sentences, 1), "avg_word_length": round(avg_word, 1)
                })
        """),
        "uuid_gen": textwrap.dedent("""\
            import uuid
            def uuid_gen(count: int = 1) -> str:
                ids = [str(uuid.uuid4()) for _ in range(count)]
                return json.dumps({"uuids": ids, "count": count})
        """),
        "base64_encode": textwrap.dedent("""\
            import base64
            def base64_encode(text: str) -> str:
                encoded = base64.b64encode(text.encode()).decode()
                return json.dumps({"input": text[:50], "encoded": encoded})
        """),
        "hash_text": textwrap.dedent("""\
            import hashlib
            def hash_text(text: str, algorithm: str = "sha256") -> str:
                h = hashlib.new(algorithm, text.encode())
                return json.dumps({"algorithm": algorithm, "hash": h.hexdigest()})
        """),
    }

    def generate(self, spec: str) -> EvolvingTool:
        """Generate a tool from a spec keyword. Returns EvolvingTool ready to use."""
        spec_lower = spec.lower().replace("-", "_").replace(" ", "_")

        # Find matching template
        for key, code in self.TOOL_TEMPLATES.items():
            if key in spec_lower or spec_lower in key:
                return self._build(key, code)

        # Generate a simple echo tool if no match
        fallback = textwrap.dedent(f"""\
            def {spec_lower.replace(" ", "_")}(text: str) -> str:
                return f"[{spec}] → {{text}}"
        """)
        return self._build(spec_lower.replace(" ", "_"), fallback)

    def _build(self, name: str, code: str) -> EvolvingTool:
        namespace = {"json": json}
        exec(code, namespace)
        func = namespace[name]
        return EvolvingTool(
            name=name, code=code, func=func,
            description=func.__doc__ or f"Auto-generated tool: {name}"
        )

# ── Self-Evolving Agent ──────────────────────────────────────

class SelfEvolvingAgent:
    def __init__(self, name: str = "EvolvingAgent"):
        self.name = name
        self.engine = EvolutionEngine()
        self.tools: dict[str, EvolvingTool] = {}
        self.history: list[dict] = []
        self.total_evolutions = 0

    def evolve(self, spec: str) -> str:
        """Generate and register a new tool from spec."""
        if not spec:
            return "❌ Invalid spec: empty"
        try:
            tool = self.engine.generate(spec)
        except SyntaxError as e:
            return f"❌ Failed to evolve '{spec}': generated code is not valid Python ({e.msg})"

        if tool.name in self.tools:
            tool.generation = self.tools[tool.name].generation + 1

        self.tools[tool.name] = tool
        self.total_evolutions += 1

        self.history.append({
            "action": "evolve", "tool": tool.name,
            "generation": tool.generation, "hash": tool.hash,
            "time": time.strftime("%H:%M:%S")
        })

        return f"🧬 Evolved tool '{tool.name}' (gen {tool.generation}, hash {tool.hash})"

    def use(self, tool_name: str, **kwargs) -> str:
        if tool_name not in self.tools:
            return f"❌ Tool '{tool_name}' not found. Available: {list(self.tools.keys())}"
        try:
            result = self.tools[tool_name].func(**kwargs)
            self.history.append({"action": "use", "tool": tool_name, "result": str(result)[:100]})
            return f"✅ {result}"
        except Exception as e:
            return f"❌ Error: {e}"

    def inspect(self, tool_name: str) -> str:
        if tool_name not in self.tools:
            return f"❌ Unknown tool: {tool_name}"
        t = self.tools[tool_name]
        return f"📋 {t.name} (gen {t.generation}, hash {t.hash})\n{t.code}"

    def status(self) -> str:
        lines = [f"🧬 {self.name} Status:", f"  Tools: {len(self.tools)}", f"  Evolutions: {self.total_evolutions}"]
        for name, t in self.tools.items():
            lines.append(f"  - {name} (gen {t.generation})")
        return "\n".join(lines)

# ── Demo ─────────────────────────────────────────────────────

def main():
    agent = SelfEvolvingAgent(name="🧬 Neuron")

    print(f"{'='*55}")
    print(f"  🧬 Self-Evolving Agent Demo")
    print(f"  Agent starts with NO tools and evolves them on demand")
    print(f"{'='*55}\n")

    # Phase 1: Evolve tools
    print("── Phase 1: Tool Evolution ──")
    for spec in ["fibonacci", "prime_check", "password_gen", "color_palette", "text_stats", "uuid_gen", "base64_encode", "hash_text"]:
        result = agent.evolve(spec)
        print(f"  {result}")

    print(f"\n{agent.status()}\n")

    # Phase 2: Use the evolved tools
    print("── Phase 2: Using Evolved Tools ──")
    demos = [
        ("fibonacci", {"n": 42}),
        ("prime_check", {"n": 97}),
        ("prime_check", {"n": 100}),
        ("password_gen", {"length": 20}),
        ("color_palette", {"base_hue": 210}),
        ("text_stats", {"text": "Hello world! This is a self-evolving agent experiment. 晚安！"}),
        ("uuid_gen", {"count": 3}),
        ("base64_encode", {"text": "Catalyst was here 🧪"}),
        ("hash_text", {"text": "pocket-agent", "algorithm": "sha256"}),
    ]

    for tool_name, args in demos:
        print(f"  👤 {tool_name}({args})")
        print(f"  {agent.use(tool_name, **args)}\n")

    # Phase 3: Inspect generated code
    print("── Phase 3: Code Inspection ──")
    print(agent.inspect("password_gen"))

    # Phase 4: Re-evolve (upgrade)
    print("\n── Phase 4: Re-evolution (upgrade) ──")
    print(agent.evolve("password_gen"))
    print(agent.evolve("password_gen"))
    print(f"\n{agent.status()}")

if __name__ == "__main__":
    main()
