# Better Ralph Core

> Autonomous development loop orchestration engine — turns PRD stories into commits.

## 🎯 What It Does

Better Ralph Core automates iterative software development by:

1. **Loading PRD stories** from a structured requirements document
2. **Selecting the right agent** for each story based on capabilities
3. **Executing stories** one by one with full context management
4. **Running quality checks** after each iteration
5. **Committing changes** with conventional commit messages
6. **Persisting memory** across iterations for continuous improvement

## 🏗 Architecture

```
better-ralph-core/
├── core/
│   ├── orchestrator.py    # Main loop — session → iteration → commit
│   ├── prd_manager.py     # PRD loading, story parsing, completion tracking
│   ├── memory_manager.py  # Cross-iteration context & learning persistence
│   └── agent_registry.py  # Agent discovery and selection
├── data/                  # Sample PRD and task data
├── plugins/               # Extensions (version control)
├── utils/
│   ├── config.py          # Configuration management
│   ├── logger.py          # Structured logging
│   └── monitor.py         # Performance metrics
└── tests/unit/            # Unit tests (30+ test files)
```

## 🔑 Core Concepts

### Session Lifecycle
```
start_session(prd_path, project_root)
  → execute_iteration() × N
  → end_session()
```

A **session** is one complete run against a PRD. Each **iteration** picks the next incomplete story, executes it, runs quality checks, and commits on success.

### PRD Stories
Stories follow this structure:
```json
{
  "id": "US-001",
  "title": "Add user authentication",
  "description": "Implement JWT-based auth",
  "acceptance_criteria": ["Users can log in", "Tokens refresh automatically"],
  "priority": 1,
  "dependencies": []
}
```

### Memory System
The `MemoryManager` tracks:
- **Iteration context** — artifacts, learnings, patterns from each run
- **Project context** — code conventions, common gotchas, file types
- **Progress** — completed stories, cumulative stats

This means each iteration starts with knowledge from all previous ones.

## 🚀 Quick Start

```python
from pathlib import Path
from core.orchestrator import RalphOrchestrator

orchestrator = RalphOrchestrator()

# Start a session with your PRD
session_id = orchestrator.start_session(
    prd_path=Path("prd.json"),
    project_root=Path("/my/project")
)

# Run iterations until all stories are done
while not orchestrator.is_complete():
    result = orchestrator.execute_iteration()
    print(f"Story {result.story_id}: {'✅' if result.success else '❌'}")

# Get summary and clean up
summary = orchestrator.get_session_summary()
orchestrator.end_session()
```

## 📊 Iteration Result

Each iteration returns:
- `story_id` / `story_title` — what was worked on
- `success` — did it pass quality checks?
- `duration` — time taken
- `commit_hash` — git commit (if successful)
- `error_message` — failure reason (if failed)
- `artifacts` — files created/modified

## 🧪 Testing

30+ unit test files covering all core modules:

```bash
cd better-ralph-core
pytest                  # run all
pytest tests/unit/test_orchestrator.py  # specific module
pytest -k "memory"     # by keyword
```

测试覆盖范围：orchestrator（session/status/retry/batch）、PRD（merge/export/validate/priority）、memory manager、monitor、config、checkpoint 等。

## 📦 Dependencies

Pure Python 3 — no external dependencies required for the core engine.

## 📚 更多文档

- [教程](TUTORIAL.md) — 从准备 PRD 到实战的完整指南
- [OpenClaw Better Ralph Skill](../skills/better-ralph/SKILL.md) — 通过 OpenClaw skill 运行

---

*Part of the [OpenClaw workspace](https://github.com/robertsong2019)*
