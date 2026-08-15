# Error Patterns

### 2026-07-06 Duplicate class name silently shadowing tests (Occurrence: 1)
- **场景:** test_memory_graph.py had two `class TestBiTemporalValidity` definitions
- **错误:** 88 test methods in the first class never ran — Python class shadowing is silent
- **根因:** No linting check for duplicate class names; copy-paste of class header without renaming
- **修正:** Renamed first instance to `TestAdaptiveRetrieval`
- **出现次数:** 1
- **Prevention:** Add to pre-commit hook: `grep -c "^class TestBiTemporalValidity" test_*.py` uniqueness check

### 2026-07-07 Phantom commits — entire evening's work lost (Occurrence: 1, ESCALATED)
- **场景:** Code lab + evening cron (21:00-22:25) committed 6 APIs claiming +63 tests (1975→2038)
- **错误:** Commits modified test files but NOT memory_graph.py. Test classes were shadowed, so pytest reported inflated counts. Key-dev-1 (23:00) discovered source unchanged at 1975.
- **根因:** No verification that source files were actually modified in commit. TDD assumes tests reflect real code — shadowed classes break this assumption.
- **修正:** Key-dev-1 started fresh from real baseline 1975. 6 APIs need reimplementation.
- **出现次数:** 1 (但影响 6 个 API + 整晚工作)
- **Lost APIs:** Memory Maturation (sigmoid activation), RecurrenceDetector, ConsolidationRouter (FAST/SMART), Recall with Activation, confidence_score, forgetting_curve
- **Prevention:** 
  1. Pre-commit: verify `git diff --name-only` includes source file (not just test file)
  2. Post-test: `pytest --co -q | tail -1` vs claimed count in commit message
  3. Consider: `grep -c "^class Test" test_*.py` vs actual pytest collection count

### [2026-08-15] 多副本项目打包了过期代码
- **场景:** amg PyPI 打包研究（Research #066），需对 memory_graph.py 构建 wheel
- **错误:** 直接对 `code-lab/agent-memory-graph`（08-10/C424 过期副本）构建；冒烟时 `extract_from_text(mode=...)` 签名对不上才暴露。真身在 `projects/agent-memory-graph`（08-15/C440，54k 行）
- **根因:** workspace 有三处同名项目目录，未先按 mtime/内容认主就动手
- **修正:** `find -name <file> -printf "%T@ %p\n" | sort -rn` 认主后重建；两副本 API 面已漂移（类导出、chunk_text 位置）
- **出现次数:** 1（关联既有教训: 2026-08-13 GitHub 周报文档源目录误判）
