# 🧪 Pocket Agent

A minimal AI agent framework in pure Python — two modules, zero dependencies, no LLM API needed:

| Module | ~LOC | What it shows |
|--------|------|---------------|
| `pocket_agent.py` | ~220 | **Tool use** (type hints → JSON Schema), **ReAct loop** (Reason → Act → Observe), **Memory** (short-term + keyword recall), streaming thoughts. Includes a **mock LLM backend** — swap in `openai.ChatCompletion` with one function change. |
| `self_evolving_agent.py` | ~220 | **Self-evolution** — the agent starts with *zero tools* and generates them on demand from natural-language specs via `exec()`. "Agent writes code to extend itself" in miniature. |

## Quick Start

```bash
python3 pocket_agent.py          # ReAct agent demo (mock LLM)
python3 self_evolving_agent.py   # self-evolution demo (no LLM at all)
```

## Concepts Demonstrated

1. **Tool Registry** — functions auto-registered with type hints → JSON Schema
2. **ReAct Loop** — agent reasons, picks tools, observes results, repeats
3. **Episodic Memory** — stores important observations for later retrieval
4. **Guard Rails** — max iterations, tool timeout, output validation
5. **Runtime Tool Generation** — spec → code template → `exec()` → callable `EvolvingTool`, with code-hash identity (`hash = md5(code)[:8]`) and generation counting on re-evolution

## Self-Evolving Agent in 30 Seconds

```python
from self_evolving_agent import SelfEvolvingAgent

agent = SelfEvolvingAgent()
agent.evolve("fibonacci")            # generates & registers a fibonacci tool
agent.evolve("password_gen")         # ...another one, from an 8-template library
agent.evolve("my_custom_thing")      # no match? falls back to an echo tool
agent.use("fibonacci", n=42)         # ✅ Fibonacci(42) = 267914296
agent.evolve("password_gen")         # re-evolve → generation increments
agent.inspect("password_gen")        # read back the generated source
```

📚 Deep dive: [TUTORIAL.md](TUTORIAL.md) — 30-minute walkthrough of both modules, including the three real bugs our test suite caught in this pattern (dead templates, `exec()` crashes, spec edge cases) and the parametrized "template integrity" test that guards against them.

## Tests

58 tests, pure pytest, run in <0.1s:

```bash
python3 -m pytest test_pocket_agent.py test_self_evolving_agent.py -v
```

Coverage highlights: template-integrity (every template defines its own function name), value checks per template, spec-matching edge cases, re-evolution generation counting, and malformed-spec robustness (never raises, always returns a message).

## Extend It

- Replace `MockLLM` with real API calls
- Add your own tools with `@agent.tool`
- Add new `TOOL_TEMPLATES` entries (the integrity test will keep them honest)
- Connect to MCP servers
- Add persistence (sqlite/jsonl)
