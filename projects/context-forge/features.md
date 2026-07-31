# context-forge Feature Backlog

## ✅ Existing Features
- Auto-detects project type (Node.js, Python, Go, Rust, etc.)
- Extracts dependencies, scripts, entry points from package.json/pyproject.toml/Cargo.toml
- Maps directory structure and architecture patterns
- Generates context files for multiple AI tools (AGENTS.md, .cursorrules, .github/copilot-instructions.md)
- Updates existing files (preserves manual additions in marked sections)
- Zero dependencies, single file Node.js script
- CLI with options: --only, --dry-run, --update, --json

## 🔲 Feature Backlog

### Core Analysis
- [x] **F8**: .gitignore parsing — respect ignored paths during analysis ✅ 2026-06-17
- [x] **F2**: Import statement analysis — actual imports from source files (not just package.json) ✅ 2026-06-17
- [x] **F3**: API surface extraction — exported functions/classes/methods from source files ✅ 2026-06-18
- [x] **F4**: Configuration file parser — tsconfig, eslint, prettier, docker, vite/webpack/tailwind ✅ 2026-06-18
- [x] **F1**: Git history analysis — commit patterns, contributors, recent activity ✅ 2026-06-20

### Output Formats
- [x] **F5**: Mermaid.js diagrams — directory structure visualization ✅ 2026-06-19
- [x] **F6**: Markdown tables — better formatted dependency/script lists ✅ 2026-06-21
- [x] **F7**: TOML/YAML export — structured output for other tools ✅ 2026-06-21

### Quality & Safety
- [x] **F9**: File size limits — skip huge files in analysis ✅ 2026-06-19
- [x] **F10**: Validation mode — check generated files against actual codebase ✅ 2026-06-19

### Developer Experience
- [x] **F11**: Watch mode — regenerate on file changes ✅ 2026-07-16
- [x] **F12**: Diff preview — show what would change before updating ✅ 2026-06-20
- [x] **F13**: Template system — customizable output templates ✅ 2026-06-21
- [x] **F14**: Cache analysis results — faster re-runs ✅ 2026-06-21

### Testing & Documentation
- [x] **F15**: Unit tests for core functions
- [x] **F16**: Integration tests with real projects ✅ 2026-06-21
- [x] **F35**: Test file detection — scan for test files, detect framework (jest/pytest/go/vitest/mocha) ✅ 2026-06-27
- [x] **F36**: Git hotspot analysis — find most frequently changed files ✅ 2026-06-27
- [x] **F17**: Performance benchmarks on large repos — benchmarkAnalysis + formatBenchmarkReport ✅ 2026-07-07
- [x] **F18**: Documentation examples for each generated file type ✅ 2026-07-07

### File Analysis
- [x] **F39**: File size analysis — distribution, percentiles, outliers, by-extension breakdown ✅ 2026-07-10
- [x] **F40**: Naming convention detection — camelCase/snake_case/kebab_case/PascalCase/CONST_CASE detection with inconsistency reporting ✅ 2026-07-10
- [x] **F42**: API route detection — scan Express/FastAPI/Flask/Django endpoints ✅ 2026-07-11

### Output Formats (Route Reports)
- [x] **F43**: formatApiRoutesReport() — markdown report with method summary and route detail table ✅ 2026-07-11
- [x] **F44**: analyzeImportHealth() — unused deps, import frequency, diversity score ✅ 2026-07-11
- [x] **F45**: formatImportHealthReport() — markdown report for import health ✅ 2026-07-11

### Security & Quality
- [x] **F32**: Secret detection — scan source for API keys, tokens, passwords ✅ 2026-06-23
- [x] **F33**: Documentation readability analysis — A-F scoring with 15+ metrics ✅ 2026-06-23
- [x] **F34**: Dead code detection — find exported symbols never imported ✅ 2026-06-24

### Code Quality
- [x] **F46**: analyzeCodeComplexity() — cyclomatic complexity estimation (decision point counting) with A-F grading per file ✅ 2026-07-18
- [x] **F47**: analyzeFileCoupling() — Jaccard similarity-based file coupling analysis, shared dependency tracking ✅ 2026-07-18
- [x] **F48**: analyzeTechDebt() — weighted multi-signal tech debt score (TODOs+dead code+complexity+deps+secrets) with recommendations ✅ 2026-07-18

### Error & Code Quality (Round 5 — 2026-07-21)
- [x] **F53**: analyzeErrorHandling() — 8-pattern error handling anti-pattern scanner (empty catch, catch-ignore, bare throw, console-only catch, throw string, generic catch-all, etc.) with health score + A-F grading ✅ 2026-07-21
- [x] **F54**: analyzeDuplicateCode() — normalized line fingerprinting for cross-file duplicate detection, string literal + comment normalization, wasted lines estimate ✅ 2026-07-21
- [x] **F55**: analyzeCommentHealth() — comment-to-code ratio, stale/obsolete comments, doc coverage ✅ 2026-07-22

### Async & Concurrency (Round 6 — 2026-07-23)
- [x] **F56**: analyzeAsyncPatterns() — async/await vs Promise chains vs callbacks, missing await, floating promises, unhandled rejections, callback hell ✅ 2026-07-23
- [x] **F57**: analyzeExportHealth() — barrel files, re-export chains, unused exports, mixed export styles ✅ 2026-07-23
- [x] **F58**: analyzeFunctionMetrics() — function length, parameter count, return paths, arrow/async detection ✅ 2026-07-23

### Code Structure (Round 11 — 2026-07-25)
- [x] **F75**: analyzeGuardClauses() — deep nesting detection (4+ levels), if/else wrapping detection for guard clause refactoring, indentation analysis. A-F grading. formatGuardClausesReport(). ✅ 2026-07-25
- [x] **F76**: analyzeParameterObjects() — 4+ scalar param detection, boolean param confusion, consecutive optional param detection. Destructured/rest params excluded. A-F grading. formatParameterObjectsReport(). ✅ 2026-07-25

## Priorities
**Round 1 (Core):** F1, F2, F3 — Better codebase understanding
**Round 2 (Output):** F5, F6 — Better visualization
**Round 3 (DX):** F11, F12 — Better workflow
### DevOps & Risk (Round 7 — 2026-07-24)
- [x] **F59**: analyzeCliHealth() — CLI completeness analysis: 8 checks (help/version/usage/arg validation/exit codes/subcommands/stderr/color), A-F grading, framework detection (commander/yargs vs manual). formatCliHealthReport(). ✅ 2026-07-24
- [x] **F60**: analyzeDependencyRisk() — 5-category dependency risk assessment: version pinning (pinned/caret/tilde/range/wildcard), dev/prod ratio, risky pattern detection (code execution/legacy heavyweight/duplicate functionality), dependency count. A-F grading. formatDependencyRiskReport(). ✅ 2026-07-24
- [x] **F61**: analyzeTestCoverage() — test coverage estimation: test/source file mapping, framework detection (jest/mocha/vitest/node_test/pytest/go_test/ava), untested file identification with line counts. A-F grading. formatTestCoverageReport(). ✅ 2026-07-24

### Code Hygiene (Round 8 — 2026-07-24)
- [x] **F62**: analyzeLoggingHealth() — console.log pollution detector (5-level console.* tracking), catch-without-log scanner with multi-line look-ahead, A-F grading. formatLoggingHealthReport(). ✅ 2026-07-24
- [x] **F63**: analyzeEnvHealth() — .env.example coverage analysis, undocumented/stale env var detection, hardcoded secret scanner. A-F grading. formatEnvHealthReport(). ✅ 2026-07-24
- [x] **F64**: analyzePerformancePatterns() — 5-pattern scanner: sync I/O, nested loops, promise-in-loop, missing await, unbounded ops. A-F grading. formatPerformanceReport(). ✅ 2026-07-24

### TypeScript & Code Quality (Round 9 — 2026-07-24)
- [x] **F65**: analyzeTypeSafety() — TS type safety: explicit/implicit any, @ts-ignore/@ts-nocheck/@ts-expect-error, type assertions (as + angle-bracket), missing return types, non-null assertions. A-F grading. formatTypeSafetyReport(). ✅ 2026-07-24
- [x] **F66**: analyzeCodeSmells() — 7 smells: long files, deep nesting, too many params, magic numbers, god files, empty catch, TODO/FIXME. A-F grading. formatCodeSmellReport(). ✅ 2026-07-24

### Documentation Health (Round 10 — 2026-07-24)
- [x] **F67**: analyzeReadmeHealth() — 10-section README quality analyzer (title/description/install/usage/license/contributing/tests/badges/examples/apiDocs), placeholder content detection, broken markdown link scanner, markdown element stats (headings/codeBlocks/links/images). A-F grading. formatReadmeHealthReport(). ✅ 2026-07-24

### Code Structure (Round 12 — 2026-07-25)
- [x] **F77**: analyzeCyclomaticComplexity() — per-function cyclomatic complexity: decision-point counting (if/else if, for, while, do, case, catch, ternary ?, &&, ||, ??). 10/15 thresholds, avg/max stats, A-F grading. formatCyclomaticComplexityReport(). ✅ 2026-07-25
- [x] **F78**: analyzeReturnPaths() — excessive return-statement detection (5+ threshold, 8+ high severity), unreachable code after return. A-F grading. formatReturnPathsReport(). ✅ 2026-07-25

### Code Safety (Round 13 — 2026-07-25)
- [x] **F79**: analyzeEqualityChecks() — loose equality detector: ==/!= type coercion risk, null/undefined safe pattern detection (low severity), strict comparison counting, A-F grading. formatEqualityChecksReport(). ✅ 2026-07-25

### Resource Safety (Round 14 — 2026-07-27)
- [x] **F80**: analyzeResourceLeaks() — resource leak detector: setInterval without clear, addEventListener without remove, unclosed file handles/streams, DB connections without close/disconnect. A-F grading. formatResourceLeaksReport(). Fixed pre-existing duplicate formatDeadCodeReport (renamed to formatDeadCodeAnalysisReport). ✅ 2026-07-27
- [x] **F82**: analyzeSecurityAntiPatterns() — 8-category security scanner: eval/Function() (code-injection), innerHTML/dangerouslySetInnerHTML/document.write (XSS), SQL string concatenation (SQLi), __proto__/constructor.prototype (prototype pollution), Math.random() in security contexts (insecure-random), exec/spawn with interpolation (command-injection), nested quantifier regexes (ReDoS), hardcoded credential literals. Weighted severity scoring (critical/high/medium/low). formatSecurityAntiPatternsReport() with category breakdown and severity-sorted issue table. +47 tests. ✅ 2026-07-31
