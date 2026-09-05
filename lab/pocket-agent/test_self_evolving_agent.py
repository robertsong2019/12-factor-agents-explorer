#!/usr/bin/env python3
"""Tests for self_evolving_agent.py — EvolutionEngine templates, fallback generation,
SelfEvolvingAgent evolve/use/inspect/status lifecycle, malformed-spec robustness."""

import base64
import hashlib
import json

import pytest

from self_evolving_agent import EvolutionEngine, EvolvingTool, SelfEvolvingAgent


# ── EvolvingTool ─────────────────────────────────────────────

class TestEvolvingTool:
    def test_hash_is_md5_of_code_first_8_hex(self):
        code = "def x():\n    return 1\n"
        t = EvolvingTool(name="x", code=code, func=lambda: 1, description="d")
        assert t.hash == hashlib.md5(code.encode()).hexdigest()[:8]

    def test_hash_stable_and_distinct(self):
        t1 = EvolvingTool(name="x", code="a", func=lambda: 1, description="d")
        t2 = EvolvingTool(name="x", code="a", func=lambda: 1, description="d")
        t3 = EvolvingTool(name="x", code="b", func=lambda: 1, description="d")
        assert t1.hash == t2.hash and t1.hash != t3.hash

    def test_generation_defaults_zero(self):
        t = EvolvingTool(name="x", code="a", func=lambda: 1, description="d")
        assert t.generation == 0


# ── EvolutionEngine templates ────────────────────────────────

class TestTemplates:
    def setup_method(self):
        self.engine = EvolutionEngine()

    def test_fibonacci_values(self):
        out = self.engine.generate("fibonacci").func(n=10)
        assert "55" in out

    def test_prime_check_prime_and_composite(self):
        f = self.engine.generate("prime_check").func
        assert "97 is prime" in f(n=97)
        assert "100 is not prime" in f(n=100)

    def test_password_gen_json_shape_and_strength(self):
        out = json.loads(self.engine.generate("password_gen").func(length=20))
        assert out["length"] == 20 and out["strength"] == "strong"
        assert len(out["password"]) == 20
        weak = json.loads(self.engine.generate("password_gen").func(length=8))
        assert weak["strength"] == "weak"

    def test_color_palette_five_colors_hue_wraps(self):
        out = json.loads(self.engine.generate("color_palette").func(base_hue=300))
        assert len(out["palette"]) == 5
        hues = [int(c.split("(")[1].split(",")[0]) for c in out["palette"]]
        assert hues == [(300 + i * 72) % 360 for i in range(5)]

    def test_text_stats_counts(self):
        out = json.loads(self.engine.generate("text_stats").func(text="Hello world. Nice day!"))
        assert out["chars"] == len("Hello world. Nice day!")
        assert out["words"] == 4
        assert out["sentences"] == 2

    def test_uuid_gen_count_and_uniqueness(self):
        out = json.loads(self.engine.generate("uuid_gen").func(count=5))
        assert out["count"] == 5 and len(set(out["uuids"])) == 5

    def test_hash_text_known_vector(self):
        out = json.loads(self.engine.generate("hash_text").func(text="abc", algorithm="sha256"))
        assert out["hash"] == hashlib.sha256(b"abc").hexdigest()

    def test_base64_encode_spec_roundtrip(self):
        """spec 'base64_encode' must reach the real base64 template, not an echo fallback."""
        tool = self.engine.generate("base64_encode")
        out = json.loads(tool.func(text="hello"))
        assert out["encoded"] == base64.b64encode(b"hello").decode()
        assert out["input"] == "hello"

    def test_base64_short_spec_still_matches(self):
        tool = self.engine.generate("base64")
        assert json.loads(tool.func(text="hi"))["encoded"] == "aGk="

    def test_unmatched_spec_gets_echo_tool(self):
        tool = self.engine.generate("greeting-widget")
        assert tool.name == "greeting_widget"
        assert "[greeting-widget]" in tool.func(text="yo")

    @pytest.mark.parametrize("key", sorted(EvolutionEngine.TOOL_TEMPLATES))
    def test_template_defines_its_own_key(self, key):
        """Every template key must name the function its code defines —
        guards the dead-template KeyError family (base64_tool was unreachable)."""
        tool = self.engine.generate(key)
        assert tool.name == key
        assert callable(tool.func)


# ── SelfEvolvingAgent lifecycle ──────────────────────────────

class TestSelfEvolvingAgent:
    def setup_method(self):
        self.agent = SelfEvolvingAgent(name="TestAgent")

    def test_evolve_registers_tool_and_status_counts(self):
        msg = self.agent.evolve("fibonacci")
        assert "fibonacci" in msg and "fibonacci" in self.agent.tools
        assert self.agent.total_evolutions == 1
        assert "Tools: 1" in self.agent.status()

    def test_re_evolve_increments_generation(self):
        self.agent.evolve("prime_check")
        self.agent.evolve("prime_check")
        self.agent.evolve("prime_check")
        assert self.agent.tools["prime_check"].generation == 2
        assert self.agent.total_evolutions == 3

    def test_use_unknown_tool_lists_available(self):
        self.agent.evolve("fibonacci")
        out = self.agent.use("nope", n=3)
        assert "❌" in out and "fibonacci" in out

    def test_use_success_prefixes_and_records_history(self):
        self.agent.evolve("fibonacci")
        out = self.agent.use("fibonacci", n=5)
        assert out.startswith("✅") and "5" in out
        assert self.agent.history[-1] == {"action": "use", "tool": "fibonacci", "result": "Fibonacci(5) = 5"}

    def test_use_bad_args_returns_error_not_raise(self):
        self.agent.evolve("fibonacci")
        out = self.agent.use("fibonacci", n="not-a-number")
        assert out.startswith("❌")

    def test_inspect_shows_code(self):
        self.agent.evolve("fibonacci")
        out = self.agent.inspect("fibonacci")
        assert "def fibonacci" in out and "gen 0" in out
        assert "❌" in self.agent.inspect("ghost")

    def test_evolve_records_history_entry(self):
        self.agent.evolve("fibonacci")
        entry = self.agent.history[0]
        assert entry["action"] == "evolve" and entry["tool"] == "fibonacci" and entry["generation"] == 0


# ── Malformed-spec robustness (red-first) ────────────────────

class TestMalformedSpecs:
    def setup_method(self):
        self.agent = SelfEvolvingAgent()

    @pytest.mark.parametrize("spec", ["my tool!", "1abc", "bad-name$", "f(x)"])
    def test_malformed_spec_never_crashes(self, spec):
        out = self.agent.evolve(spec)
        assert out.startswith("❌"), f"spec {spec!r} should fail cleanly, got: {out}"
        assert self.agent.total_evolutions == 0
        assert self.agent.tools == {}

    def test_empty_spec_rejected(self):
        out = self.agent.evolve("")
        assert out.startswith("❌")
        assert self.agent.tools == {} and self.agent.total_evolutions == 0

    def test_agent_still_usable_after_failures(self):
        self.agent.evolve("1bad")
        self.agent.evolve("")
        msg = self.agent.evolve("fibonacci")
        assert "fibonacci" in msg
        assert self.agent.use("fibonacci", n=6).startswith("✅")
