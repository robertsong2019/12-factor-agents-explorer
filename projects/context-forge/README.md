# context-forge 🔨

> Analyze your codebase and generate optimal context files for AI coding agents.

## Why

AI coding assistants (Cursor, Copilot, Claude Code, Codex) work better when they understand your project. But writing good context files (`AGENTS.md`, `.cursorrules`, `.github/copilot-instructions.md`) is tedious and gets outdated.

**context-forge** scans your repo and generates these files automatically — so your AI tools always have up-to-date project context.

## Quick Start

```bash
# Install
cp context-forge.mjs /usr/local/bin/context-forge

# Run on your project
context-forge /path/to/my-project

# Preview what it would generate (no files written)
context-forge /path/to/my-project --dry-run
```

## Features

- 🔍 **Auto-detects** project type (Node.js, Python, Go, Rust, etc.)
- 📦 **Extracts** dependencies, scripts, entry points from `package.json`/`pyproject.toml`/`Cargo.toml`
- 🏗️ **Maps** directory structure and architecture patterns
- 📝 **Generates** context files for multiple AI tools
- 🔄 **Updates** existing files (preserves manual additions in marked sections)
- 📊 **Markdown tables** for dependencies and scripts (F6)
- 📄 **TOML & YAML export** — structured output for other tools (F7)
- 🧩 **Template system** — register/load/customize output templates (F13)
- ⚡ **Analysis cache** — faster re-runs with mtime-based invalidation (F14)
- 🧪 **Integration tested** against real projects (F16)
- 📊 **Complexity analysis** — Shannon diversity, category scoring, 0-100 metrics (F17)
- 🔄 **Project comparison** — diff two analyses with trend detection (F18)
- 🏥 **Health score & stale detection** — 8-check project health, A-F grade (F19)
- 📊 **Dependency graph** — adjacency list, circular deps, visual format (F20)
- 🔧 **Tech stack inference** — 35+ signatures, confidence scoring (F21)
- 👯 **Duplicate detection** — shared imports + identical signatures (F22)
- 📈 **Project statistics** — maturity, config coverage, test/code ratio (F23)
- 🚪 **Entry point analysis** — type classification, orphan detection (F24)
- ⚠️ **Dependency risk audit** — pinning, abandoned packages, A-F grading (F25)
- 🎯 **Quality signals** — 6 dimensions: typesafety, testing, linting, formatting, CI, docs (F26)
- 🏗️ **Monorepo workspace** — pnpm/npm/yarn/turbo/lerna/nx detection (F27)
- 📝 **TODO extraction** — scan and categorize TODO/FIXME/HACK comments (F28)
- 🔐 **Env var detection** — find hardcoded env references and secrets (F29)
- 📜 **License detection** — SPDX identification + compatibility checks (F30)
- 🔐 **Secret scanner** — detect API keys, tokens, passwords, private keys with risk levels (F32)
- 📖 **Doc readability** — A-F grade scoring, heading hierarchy, paragraph/sentence analysis (F33)
- 🪦 **Dead code detector** — find unused exports by cross-referencing imports (F34)

### Code Quality Suite (F46–F58)

- 🧠 **Code complexity** — decision-point estimation, per-file A-F grading (F46)
- 🔗 **File coupling** — Jaccard similarity, shared dependency tracking (F47)
- ⚖️ **Tech debt score** — weighted multi-signal: TODOs + dead code + complexity + deps + secrets (F48)
- 🚨 **Error handling** — 8 anti-patterns: empty catch, catch-ignore, bare throw, string throw, generic catch-all (F53)
- 👯 **Duplicate code** — normalized line fingerprinting, wasted-lines estimate (F54)
- 💬 **Comment health** — comment-to-code ratio, stale comments, doc coverage (F55)
- ⏳ **Async patterns** — floating promises, missing await, callback hell, unhandled rejections (F56)
- 📤 **Export health** — barrel files, re-export chains, unused exports, mixed styles (F57)
- 📐 **Function metrics** — length, param count, return paths, arrow/async split (F58)

### Code Structure & Safety (F75–F84)

- 🛡️ **Guard clauses** — deep nesting (4+ levels), if/else wrapping candidates (F75)
- 📦 **Parameter objects** — 4+ scalar params, boolean flag confusion, consecutive optionals (F76)
- 🔄 **Cyclomatic complexity** — per-function decision-point counting, 10/15 thresholds (F77)
- ↩️ **Return paths** — excessive returns (5+), unreachable code after return (F78)
- ⚖️ **Equality checks** — `==`/`!=` coercion risks, null-safe patterns (F79)
- 💧 **Resource leaks** — `setInterval`/listeners/streams/DB handles never released (F80)
- 🧩 **Cognitive complexity** — SonarQube-style nesting-aware scoring (F81)
- 🕵️ **Security anti-patterns** — 8 categories: eval, XSS, SQLi, prototype pollution, ReDoS, command injection (F82)
- 📋 **Changelog health** — Keep a Changelog compliance: semver, ISO dates, descending order, empty releases, 6 standard sections, A-F grade (F83)
- 🎯 **Analyzer branch coverage** — direct tests for the 5 largest uncovered analyzer branches; guard-clause style-A `else` detection fix (F84)

### Analysis Extras (F35–F45)

- 🧪 **Test file detection** — framework detection: jest/pytest/go/vitest/mocha (F35)
- 🔥 **Git hotspots** — most frequently changed files (F36)
- 🛣️ **API routes** — Express/FastAPI/Flask/Django endpoints + markdown report (F42–F43)
- 📦 **Import health** — unused deps, import frequency, diversity score (F44–F45)

### Code Health Audit (F59–F67)

- 🖥️ **CLI health** — 8 checks: help/version/usage/arg validation/exit codes/subcommands/stderr/color (F59)
- 📦 **Dependency risk** — version pinning, dev/prod ratio, risky patterns, count scoring (F60)
- 🧪 **Test coverage** — test/source mapping, framework detection, untested file identification (F61)
- 📝 **Logging health** — console.log pollution detector, catch-without-log scanner (F62)
- 🔧 **Env health** — .env.example coverage, undocumented/stale var detection, secret scanner (F63)
- ⚡ **Performance patterns** — sync I/O, nested loops, promise-in-loop, missing await, unbounded ops (F64)
- 🛡️ **Type safety** — any detection, @ts-ignore, type assertions, missing return types (F65)
- 💩 **Code smells** — long files, deep nesting, too many params, magic numbers, god files, empty catch (F66)
- 📖 **README health** — 10-section quality analyzer, placeholder detection, broken link scanner (F67)
- ⚡ **Zero deps** — single file, runs with Node.js

## Usage

```bash
# Generate all context files
context-forge /path/to/project

# Generate specific file only
context-forge /path/to/project --only agents

# Preview without writing
context-forge /path/to/project --dry-run

# Update existing (preserve manual sections)
context-forge /path/to/project --update

# Export as TOML or YAML
context-forge /path/to/project --format=toml
context-forge /path/to/project --format=yaml
```

### Template System (F13)

Register and use custom output templates:

```javascript
import { registerTemplate, generateFromTemplate, listTemplates } from './context-forge.mjs'

// Use a built-in template
generateFromTemplate(project, 'brief')      // minimal summary
generateFromTemplate(project, 'json-compact') // machine-readable
generateFromTemplate(project, 'dockerfile-hint') // container-focused

// Register your own
registerTemplate('my-org', (project) => `# ${project.name}\n...`)
generateFromTemplate(project, 'my-org')

// List available templates
listTemplates()  // ['brief', 'json-compact', 'dockerfile-hint', 'my-org']
```

### Analysis Cache (F14)

Speed up re-runs by caching analysis results. Cache is automatically invalidated when source files change (mtime-based):

```bash
# First run — full analysis
context-forge ~/big-project  # ~5s

# Second run — cached, only changed files re-analyzed
context-forge ~/big-project  # ~0.3s
```

## Generated Files

| File | Target Agent | Purpose |
|------|-------------|---------|
| `AGENTS.md` | OpenClaw, Claude Code | Project context, conventions, build steps |
| `.cursorrules` | Cursor | Editor-specific rules and context |
| `.github/copilot-instructions.md` | GitHub Copilot | PR/code review guidelines |
| `.claude/CLAUDE.md` | Claude Code | Detailed project instructions |

## Tutorial: First Run

### 1. Install
```bash
cp context-forge.mjs /usr/local/bin/context-forge
chmod +x /usr/local/bin/context-forge
```

### 2. Preview (no files changed)
```bash
context-forge ~/my-project --dry-run
```
You'll see a summary of detected project type, dependencies, and what each generated file will contain.

### 3. Generate
```bash
context-forge ~/my-project
```
This creates `AGENTS.md`, `.cursorrules`, `.github/copilot-instructions.md`, and `.claude/CLAUDE.md` in your project root.

### 4. Add custom content
Edit any generated file and wrap your additions:
```markdown
<!-- context-forge:start -->
Your custom rules here — preserved on update
<!-- context-forge:end -->
```

### 5. Keep fresh
```bash
context-forge ~/my-project --update
```
Regenerates auto-detected sections while keeping your manual additions.

### Output Formats (F7)

Beyond the default Markdown, context-forge can export structured data:

```bash
# TOML — great for config-driven tools
ccontext-forge ~/project --format=toml > project.toml

# YAML — works with k8s, CI/CD, etc.
ccontext-forge ~/project --format=yaml > project.yaml
```

---

## Advanced Analysis (F17–F27)

### Complexity Analysis (F17)

```javascript
import { analyzeComplexity, summarizeAnalysis } from './context-forge.mjs'

const complexity = analyzeComplexity(info, langs, importData, apiSurface, configData)
// { diversityIndex: 2.31,         // Shannon entropy
//   category: 'moderate',          // minimal|simple|moderate|complex
//   score: 67,                     // 0-100
//   factors: { languages: 3, deps: 24, exports: 45 } }

const summary = summarizeAnalysis(info, langs, complexity)
// Markdown report string for documentation
```

### Project Comparison (F18)

```javascript
import { compareProjects, formatComparison } from './context-forge.mjs'

const changes = compareProjects(beforeAnalysis, afterAnalysis)
// { languages: {added: [...], removed: [...]}, deps: {...}, trends: {...} }

const report = formatComparison(changes)  // Markdown diff report
```

### Health Score & Stale Detection (F19)

```javascript
import { detectStaleFiles, computeHealthScore } from './context-forge.mjs'

const stale = await detectStaleFiles(root, generatedFiles)
// Files referenced in context that no longer exist

const health = computeHealthScore(info, langs, importData, apiSurface, configData, issues)
// { score: 82, grade: 'B+', checks: {entryPoints: 'pass', scripts: 'warn', ...} }
```

### Dependency Graph (F20)

```javascript
import { buildDependencyGraph, findCircularDependencies, formatDependencyGraph } from './context-forge.mjs'

const graph = buildDependencyGraph(importData)
// { adjacency: { './db': ['./db/users', './db/posts'], ... },
//   reverse: { ... }, stats: { totalModules: 20, totalEdges: 35 } }

const circles = findCircularDependencies(importData)  // → [['./a', './b', './a']]
const report  = formatDependencyGraph(graph)           // → Markdown table
```

### Tech Stack Inference (F21)

```javascript
import { inferTechStack, formatTechStack } from './context-forge.mjs'

const stack = inferTechStack(info, langs, importData, configData)
// { Frontend: [{name: 'React', confidence: 0.95}],
//   Backend:  [{name: 'Express', confidence: 0.80}],
//   Testing:  [{name: 'Vitest', confidence: 0.90}] }
```

### Duplicate Detection (F22)

```javascript
import { findDuplicateImports, formatDuplicateReport } from './context-forge.mjs'

const dups = findDuplicateImports(importData)
// { shared: [{imports: ['lodash'], count: 5}],
//   identical: [{signature: 'default-export', files: [...]}] }
```

### Project Statistics (F23)

```javascript
import { computeProjectStats, formatProjectStats } from './context-forge.mjs'

const stats = computeProjectStats(info, langs, importData, apiSurface, configData, complexity)
// { maturity: 'beta', testToCodeRatio: 0.35, configCoverage: 0.80, topLanguages: [...] }
```

### Entry Point Analysis (F24)

```javascript
import { analyzeEntryPoints, formatEntryPointAnalysis } from './context-forge.mjs'

const entries = analyzeEntryPoints(info, importData, apiSurface)
// [{ file: 'src/index.ts', type: 'entry', importedBy: 12, isOrphan: false }]
```

### Dependency Risk Audit (F25)

```javascript
import { auditDependencies, formatRiskAudit } from './context-forge.mjs'

const audit = auditDependencies(info)
// { riskGrade: 'B', issues: [{type: 'unpinned', pkg: 'lodash'}], score: 72 }
```

### Quality Signals (F26)

```javascript
import { detectQualitySignals, formatQualitySignals } from './context-forge.mjs'

const quality = detectQualitySignals(info, langs, importData, apiSurface, configData)
// { overall: 'B', dimensions: { typesafety: 'A', testing: 'B', linting: 'C', ... } }
```

### Monorepo Workspace (F27)

```javascript
import { detectWorkspaces, analyzeWorkspace, formatWorkspaceAnalysis } from './context-forge.mjs'

const workspaces = await detectWorkspaces(root)
// ['packages/*', 'apps/*']

const analysis = await analyzeWorkspace(root, workspaces)
// { packages: [{name, path, deps, internalDeps}], internalLinks: [...] }
```

## Code Scanning (F28–F30)

### TODO Extraction (F28)

```javascript
import { extractTODOComments, formatTODOReport } from './context-forge.mjs'

const todos = await extractTODOComments(root)
// [{ file: 'src/db.ts', line: 42, type: 'TODO', author: 'alice', text: 'refactor' }]
```

### Environment Variable Detection (F29)

```javascript
import { detectEnvVars, formatEnvVarsReport } from './context-forge.mjs'

const env = await detectEnvVars(root)
// { declared: ['DATABASE_URL', 'PORT'], hardcoded: [{file, line, var}], missing: [...] }
```

### License Detection (F30)

```javascript
import { detectLicense, formatLicenseInfo } from './context-forge.mjs'

const license = await detectLicense(root)
// { spdx: 'MIT', source: 'package.json', compatible: ['Apache-2.0', 'BSD-3-Clause'] }
```

## Security Scanning (F32)

Detect potential secrets and sensitive information in your codebase.

```javascript
import { detectSecrets, formatSecretReport } from './context-forge.mjs'

// Scan project for secrets
const findings = await detectSecrets('./my-project')

// Format as markdown report
console.log(formatSecretReport(findings))
// ### Security Scan
// Found **3** potential secret(s): 🔴 1 high · 🟡 1 medium · 🔵 1 low
// - 🔴 **[HIGH]** AWS Access Key
//   `./config/aws.js:12` — `accessKeyId: 'AKIA...'`
// ...
```

**Features:**
- 20+ pattern types: AWS keys, GitHub tokens, GitLab tokens, Slack tokens, private keys, generic API keys, passwords, JWTs, connection strings
- 3 risk levels: **high** (active credentials), **medium** (likely secrets), **low** (potential references)
- Deduplication by file+line+type
- Sorted by risk (high → medium → low)
- Ignores `.git`, `node_modules`, `.env.example`, etc.

---

## Documentation Readability (F33)

Score documentation quality with 15+ metrics and actionable suggestions.

```javascript
import { analyzeDocReadability, formatReadabilityReport } from './context-forge.mjs'

const content = fs.readFileSync('README.md', 'utf-8')
const analysis = analyzeDocReadability(content)

console.log(formatReadabilityReport(analysis))
// ### Documentation Readability
// **Score: 85/100 (Grade: B)**
// | Metric | Value |
// | Words | 1200 |
// | Headings | 12 (depth: H1-H4) |
// ...
```

**Metrics tracked:**

| Category | Metrics |
|----------|---------|
| Structure | Heading count, max depth, hierarchy issues (skipped levels) |
| Paragraphs | Count, average length, longest paragraph |
| Sentences | Count, average word length |
| Code | Block count, code-to-text ratio |
| Links | Count, density |
| Lists | Item count |

**Scoring penalties:**
- Avg paragraph > 150 words → −10
- Avg sentence > 25 words → −10
- Heading hierarchy skip → −5 per issue
- Long doc with no headings → −15
- Code blocks > 50% of document → −10
- No links in 300+ word docs → −5

**Grade scale:** A (90+) · B (80+) · C (70+) · D (60+) · F (<60)

---

## Dead Code Detection (F34)

Detect exported symbols that are never imported or referenced elsewhere in the codebase.

```javascript
import { detectDeadCode, formatDeadCodeReport } from './context-forge.mjs'

const importData = await extractImports('./src', 3)   // real import graph
const apiSurface = await extractApiSurface('./src')   // exported symbols

const result = detectDeadCode(importData, apiSurface)
console.log(formatDeadCodeReport(result))
// 🔍 Dead Code Analysis: 3/15 exports unused
//
// **src/utils/legacy.ts** (2 unused):
//   - `oldHelper`
//   - `deprecatedFn`
//
// **src/types/extra.ts** (1 unused):
//   - `UnusedType`
//
// **Summary:** 12 used / 3 unused / 15 total
```

**How it works:**
1. Collects all imported names across the project from `importData`
2. Cross-references each exported symbol from `apiSurface` against imports
3. Any export with zero inbound references is flagged as dead code

**Returns:**

| Field | Type | Description |
|-------|------|-------------|
| `dead` | `Array<{file, symbol, type}>` | Unused exports, grouped by file |
| `total` | `number` | Total exported symbols |
| `used` | `number` | Referenced exports |
| `unused` | `number` | Dead code count |

---

## File Size Analysis (F39)

Analyze file size distribution across the project — identify outliers, large files, and per-extension breakdown.

```javascript
import { analyzeFileSizes, formatFileSizeReport } from './context-forge.mjs'

const analysis = await analyzeFileSizes('./src', { maxDepth: 5, maxFiles: 10000 })
console.log(formatFileSizeReport(analysis))
// 📁 File Size Analysis: 142 files, 892.5 KB total
// Mean: 6.28 KB | Median: 3.10 KB | Std Dev: 12.4 KB
// P90: 15.2 KB | P95: 22.8 KB | P99: 48.1 KB
//
// ### Largest Files
// | File | Size |
// |------|------|
// | src/index.mjs | 45.2 KB |
// | src/scanner.mjs | 38.7 KB |
// ...
//
// ### Outliers (> P95)
// ⚠️ src/index.mjs (45.2 KB) — 3.6σ above mean
//
// ### By Extension
// | Ext | Count | Total KB | Avg KB |
// |-----|-------|----------|--------|
// | .mjs | 95 | 720.3 | 7.6 |
// | .json | 47 | 172.2 | 3.7 |
```

**Options:** `{ maxDepth, maxFiles, ignorePatterns }

**Returns:**

| Field | Type | Description |
|-------|------|-------------|
| `totalFiles` | `number` | Files analyzed |
| `totalSizeKB` | `number` | Total size in KB |
| `avgSizeKB` / `medianSizeKB` | `number` | Central tendency |
| `p90/p95/p99SizeKB` | `number` | Percentile thresholds |
| `stdDev` | `number` | Standard deviation |
| `largest` | `Array<{file, sizeKB}>` | Top 10 largest files |
| `outliers` | `Array<{file, sizeKB, sigma}>` | Files > P95 |
| `byExtension` | `Array<{ext, count, totalKB, avgKB}>` | Per-extension stats |

---

## Naming Convention Detection (F40)

Detect naming conventions (camelCase, snake_case, kebab-case, PascalCase, CONST_CASE) for files and report inconsistencies.

```javascript
import { detectNamingConventions, formatNamingReport } from './context-forge.mjs'

const analysis = await detectNamingConventions('./src', { maxDepth: 5 })
console.log(formatNamingReport(analysis))
// 📛 Naming Convention Analysis: 142 files
//
// ### Detected Conventions
// | Convention | Count | Example |
//|------------|-------|---------|
// | kebab-case | 89 | src/agent-memory-graph.mjs |
// | camelCase  | 38 | src/utils/formatReport.mjs |
// | snake_case | 12 | src/legacy/old_module.mjs |
// | PascalCase | 3 | src/components/DataTable.mjs |
//
// ⚠️ Inconsistencies Detected:
//   src/legacy/ uses snake_case (project standard: kebab-case)
//   12 files affected
```

**Options:** `{ maxDepth, ignorePatterns }

**Returns:**

| Field | Type | Description |
|-------|------|-------------|
| `totalFiles` | `number` | Files analyzed |
| `conventions` | `Array<{convention, count, example}>` | Per-convention stats |
| `inconsistencies` | `Array<{dir, expected, found, files}>` | Mismatched directories |
| `byDirectory` | `Array<{dir, conventions}>` | Per-directory breakdown |

---

## Code Health Audit (F59–F67)

Nine specialized analyzers that grade your codebase health from A to F across different dimensions. Each returns a structured report with `formatXxxReport()` for CLI output.

Most of these analyzers take an explicit **file list** (`[{ path, content }]`), not a directory — define the helper once and reuse it:

```javascript
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

// Collect all source files as [{ path, content }]
const loadFiles = (...dirs) => dirs.flatMap(dir =>
  readdirSync(dir, { withFileTypes: true, recursive: true })
    .filter(e => e.isFile())
    .map(e => {
      const path = join(e.parentPath ?? e.path, e.name)
      return { path, content: readFileSync(path, 'utf8') }
    }))
```

> ⚠️ Passing a directory string where a file list is expected does **not** throw — the scan silently finds nothing and returns a perfect grade. Always check `totalFiles`/`filesScanned` > 0.

### CLI Health (F59)

Analyze CLI completeness: help/version flags, usage docs, arg validation, exit codes, subcommands, stderr usage, and color output. Detects CLI frameworks (commander/yargs vs manual).

```javascript
import { analyzeCliHealth, formatCliHealthReport } from './context-forge.mjs'

const report = analyzeCliHealth(loadFiles('./bin'))  // [{ path, content }]
console.log(formatCliHealthReport(report))
// 🖥️ CLI Health: B (6/8 checks passed)
// ✅ Help flag (--help) found in 3/3 files
// ✅ Version flag (--version) found in 2/3 files
// ⚠️ Exit codes: 1/3 files use process.exit() without code
```

**Returns:** `{ cliFileCount, healthScore, grade, totalChecks, totalPassed, checks, framework }`

### Dependency Risk (F60)

5-category dependency risk assessment: version pinning (pinned/caret/tilde/range/wildcard), dev/prod ratio, risky pattern detection (code execution, legacy heavyweight, duplicate functionality), and dependency count scoring.

```javascript
import { detectProject, analyzeDependencyRisk, formatDependencyRiskReport } from './context-forge.mjs'

const info = await detectProject('./')            // project metadata (deps, pkg)
const report = analyzeDependencyRisk(info)
console.log(formatDependencyRiskReport(report))
// 📦 Dependency Risk: A (Low risk)
// Pinning: 95% pinned | Dev/Prod: 60/40
// ⚠️ eval in dependency-xyz@1.2.3
```

**Returns:** `{ grade, categories: {pinning, devRatio, riskPatterns, count}, riskyDeps: [] }`

### Test Coverage Estimation (F61)

Estimate test coverage by mapping test files to source files. Detects test frameworks (jest/mocha/vitest/node_test/pytest/go_test/ava) and identifies untested files with line counts.

```javascript
import { analyzeTestCoverage, formatTestCoverageReport } from './context-forge.mjs'

const report = analyzeTestCoverage(loadFiles('./src', './test'))  // include test files in the list
console.log(formatTestCoverageReport(report))
// 🧪 Test Coverage: C (45% files tested)
// Framework: jest | 18/40 source files have tests
// ⚠️ 22 untested files (avg 85 lines)
```

**Returns:** `{ grade, score, testFileCount, sourceFileCount, testedCount, untestedFiles: [] }`

### Logging Health (F62)

Detect console.log pollution (5-level `console.*` tracking) and catch blocks without logging. Multi-line look-ahead catches `catch (e) {}` patterns.

```javascript
import { analyzeLoggingHealth, formatLoggingHealthReport } from './context-forge.mjs'

const report = analyzeLoggingHealth(loadFiles('./src'))
console.log(formatLoggingHealthReport(report))
// 📝 Logging Health: D
// Found 47 console.log, 12 console.error, 3 console.warn
// ⚠️ 8 catch blocks without any logging
```

**Returns:** `{ grade, score, totalFiles, summary, files }`

### Environment Health (F63)

`.env.example` coverage analysis, undocumented/stale env var detection, and hardcoded secret scanner.

```javascript
import { analyzeEnvHealth, formatEnvHealthReport } from './context-forge.mjs'

const report = analyzeEnvHealth(loadFiles('./'))  // include .env.example in the list if you have one
console.log(formatEnvHealthReport(report))
// 🔧 Env Health: B
// .env.example: 12/15 vars documented (80%)
// ⚠️ 3 undocumented: API_KEY, SECRET, TOKEN
```

**Returns:** `{ grade, score, hasEnvExample, envExampleFile, totalSourceEnvVars, undocumented, hardcodedSecrets: [] }`

### Performance Patterns (F64)

5-pattern scanner: synchronous I/O (`readFileSync`/`writeFileSync`/`execSync`), nested loops (O(n²) detection), promise-in-loop, missing await on async calls, and unbounded array operations.

```javascript
import { analyzePerformancePatterns, formatPerformanceReport } from './context-forge.mjs'

const report = analyzePerformancePatterns(loadFiles('./src'))
console.log(formatPerformanceReport(report))
// ⚡ Performance: C (8 issues found)
// ⚠️ sync I/O: 5 calls (readFileSync in 3 files)
// ⚠️ nested loops: 2 occurrences
// ⚠️ promise-in-loop: 1 occurrence
```

**Returns:** `{ grade, score, totalFiles, summary, files }`

### Type Safety (F65)

TypeScript type safety analysis: explicit/implicit `any` detection, `@ts-ignore`/`@ts-nocheck`/`@ts-expect-error` tracking, type assertions (`as` + angle-bracket), missing return types on exports, and non-null assertions.

```javascript
import { analyzeTypeSafety, formatTypeSafetyReport } from './context-forge.mjs'

// takes a list of { path, content } objects — not a directory
const report = analyzeTypeSafety(files)   // [{ path: 'src/app.ts', content: '...' }, ...]
console.log(formatTypeSafetyReport(report))
// 🛡️ Type Safety: B
// Explicit any: 3 | Implicit any: 8
// @ts-ignore: 2 | Type assertions: 15
```

**Returns:** `{ grade, score, totalFiles, summary: {anyUsage, implicitAny, tsIgnore, tsNocheck, tsExpectError, typeAssertions, missingReturnType, nonNullAssertions}, files }`

### Code Smells (F66)

7-pattern scanner: long files (>500 lines), deep nesting (4+ levels), too many params (5+), magic numbers in comparisons, god files (10+ exports), empty catch blocks, and TODO/FIXME comments.

```javascript
import { analyzeCodeSmells, formatCodeSmellReport } from './context-forge.mjs'

// takes a list of { path, content } objects — not a directory
const report = analyzeCodeSmells(files)   // [{ path: 'src/app.js', content: '...' }, ...]
console.log(formatCodeSmellReport(report))
// 💩 Code Smells: C (12 issues)
// ⚠️ 3 files > 500 lines (largest: 892)
// ⚠️ 5 deeply nested blocks (4+ levels)
// ⚠️ 4 TODO/FIXME comments
```

**Returns:** `{ grade, score, totalFiles, summary: {longFiles, deepNesting, tooManyParams, magicNumbers, godFiles, emptyCatch, todoComments}, files }`

### README Health (F67)

10-section README quality analyzer: title/description/install/usage/license/contributing/tests/badges/examples/apiDocs. Placeholder content detection, broken markdown link scanner, and markdown element statistics.

```javascript
import { analyzeReadmeHealth, formatReadmeHealthReport } from './context-forge.mjs'

const report = await analyzeReadmeHealth('./README.md')
console.log(formatReadmeHealthReport(report))
// 📖 README Health: A
// Sections: 9/10 present (missing: contributing)
// ✅ No placeholders | ✅ No broken links
// Stats: 45 headings, 120 code blocks, 30 links, 5 images
```

**Returns:** `{ grade, sections: {title, description, ...}, placeholders, brokenLinks, stats: {headings, codeBlocks, links, images} }`

---

## Code Quality Suite (F46–F58)

Nine analyzers. Calling conventions vary — check each signature (file lists use the `loadFiles` helper defined above).

### Code Complexity & Coupling (F46–F48)

```javascript
import { analyzeCodeComplexity, analyzeFileCoupling, analyzeTechDebt, extractImports } from './context-forge.mjs'

// F46 takes (root, filesMap): relPath → { lang }
const files = new Map([['src/index.js', { lang: 'JavaScript' }]])
const cx = await analyzeCodeComplexity('./src', files)
// → { files: [{ file, complexity }], totalFiles, totalLines, byGrade: {A,B,C,D,F} }

// F47 takes the import graph from extractImports
const importData = await extractImports('./src', 3)   // → { imports: Map, allImports }
const coupling = analyzeFileCoupling(importData)
// → { couples, totalFiles, totalCouples, avgCoupling, mostCoupled, sharedDeps }

// F48 takes a pre-computed signals object, not a path
const debt = analyzeTechDebt({
  totalFiles: 40, totalLines: 8200,
  todoCount: 12, deadCodeCount: 3,
  avgComplexity: 9, dependencyCount: 24, secretCount: 0,
})
// → { overallScore, grade, items, highPriorityCount, recommendations }
```

### Error Handling, Duplication & Comments (F53–F55)

```javascript
import { analyzeErrorHandling, analyzeDuplicateCode, analyzeCommentHealth } from './context-forge.mjs'

const eh = analyzeErrorHandling(loadFiles('./src'))
// 8 anti-patterns → { total, byType, bySeverity, affectedFiles, healthScore, grade }

const dup = analyzeDuplicateCode(loadFiles('./src'))
// normalized line fingerprinting → { duplicateGroups, totalOccurrences, wastedLines, topDuplicates }

const ch = analyzeCommentHealth(loadFiles('./src'))
// → { overallRatio, overallDocCoverage, staleComments, grade }
```

### Async, Exports & Functions (F56–F58)

```javascript
import { analyzeAsyncPatterns, analyzeExportHealth, analyzeFunctionMetrics } from './context-forge.mjs'

const ap = analyzeAsyncPatterns(loadFiles('./src'))
// → { totalFloatingPromises, totalMissingAwait, totalCallbackHell, totalUnhandledRejections, grade }

const xh = analyzeExportHealth(loadFiles('./src'))
// → { totalBarrelFiles, totalReExports, totalUnusedExports, grade }

const fm = analyzeFunctionMetrics(loadFiles('./src'))
// → { totalFunctions, totalLongFunctions, totalHighParamFunctions, grade }
```

---

## Code Structure & Complexity (F75–F79, F81)

Six analyzers sharing one calling convention (file list via `loadFiles`) and one result shape — `{ stats, issues, score, grade }` — each with a `formatXxxReport()` companion:

```javascript
import {
  analyzeGuardClauses, formatGuardClausesReport,       // F75
  analyzeParameterObjects, formatParameterObjectsReport, // F76
  analyzeCyclomaticComplexity, formatCyclomaticComplexityReport, // F77
  analyzeReturnPaths, formatReturnPathsReport,          // F78
  analyzeEqualityChecks, formatEqualityChecksReport,    // F79
  analyzeCognitiveComplexity, formatCognitiveComplexityReport,   // F81
} from './context-forge.mjs'

const report = await analyzeCyclomaticComplexity(loadFiles('./src'))
console.log(formatCyclomaticComplexityReport(report))
// ## 🔄 Cyclomatic Complexity Analysis
// **Health Score: 100/100 (A)**
// - Total functions: 12
// - Complex functions (≥10): 2
// - Very complex (≥15): 0
```

All six take a `[{ path, content }]` file list and grade A–F: guard-clause nesting depth (F75), parameter-object candidates (F76), per-function cyclomatic complexity with 10/15 thresholds (F77), return-path count with unreachable-code detection (F78), loose-equality coercion risks (F79), and nesting-aware cognitive complexity (F81).

---

## Resource & Security Scanning (F80, F82)

These two take an explicit **list of file paths** (not a directory):

```javascript
import { analyzeResourceLeaks, analyzeSecurityAntiPatterns } from './context-forge.mjs'

const leaks = analyzeResourceLeaks(loadFiles('./src'))
// setInterval without clear, listeners without remove, unclosed streams/DB handles
// → { issues, summary: { totalIssues, high, medium, filesScanned, score, grade } }

const sec = analyzeSecurityAntiPatterns(loadFiles('./src'))
// 8 categories: code-injection (eval/Function), XSS (innerHTML), SQLi,
// prototype pollution, insecure-random, command-injection, ReDoS, hardcoded credentials
// → { issues, summary: { totalIssues, critical, high, medium, low, categories, grade } }
```

---

## Changelog Health (F83)

Keep a Changelog compliance audit. Takes a `{ path, content }` object (pass `null` to model a missing file):

```javascript
import { analyzeChangelogHealth, formatChangelogHealthReport } from './context-forge.mjs'

const health = analyzeChangelogHealth({ path: 'CHANGELOG.md', content: fs.readFileSync('CHANGELOG.md', 'utf8') })
// → { found, path, score, grade,
//     versions: { count, latest, latestIsValidSemVer, inDescendingOrder,
//                 unreleasedSection, versionsWithInvalidSemVer, versionsWithoutDate,
//                 emptyReleases, isoDateFormats, latestValidDate },
//     sections: { added, changed, deprecated, removed, fixed, security },
//     issues: [{ severity, message }], stats: { length, releases } }

console.log(formatChangelogHealthReport(health))
// markdown report: grade + conventions checklist + sections checklist + issues
```

What it checks:

- **Heading parsing** — four forms: `## [1.2.0] - date`, bare `## 1.2.0`, `v`-prefixed, parenthesised dates
- **Semver validity** — latest release validated; per-version invalid-semver count
- **Descending order** — numeric component comparison (1.10.0 > 1.9.0, not string order)
- **ISO dates** — `YYYY-MM-DD` enforcement; undated releases counted per-version
- **Unreleased section** — detected, excluded from release stats
- **Empty releases** — a version heading with no body is flagged
- **Six standard sections** — Added / Changed / Deprecated / Removed / Fixed / Security presence
- **Grading** — additive 100-point scoring (releases +15, valid semver +10, descending +15, dated +10, ISO +10, sections +15, unreleased +5, no empty +10, no placeholders +10) minus severity penalties (critical −30, high −5), mapped to A-F; missing file = instant F

---

## Guard-Clause Else Detection & Branch Coverage (F84)

Two additions to the code-structure suite:

**Style-A `else` detection in `analyzeGuardClauses` (F75)** — the if/else-wrapping-body check only saw `} else {` on the same line; the common style with `else` on its own line after the closing brace was invisible:

```javascript
function handle(ctx) {
  if (ctx.ready) {
    return compute(ctx);   // big if wrapping most of the body
  }
  else {                   // ← style-A: else on the NEXT line — was never detected
    return fallback(ctx);  // missed as a guard-clause opportunity
  }
}
```

The check now scans forward up to 3 lines past the if-block for the next non-empty line before testing for `else`. Known limitation: same-line `} else {` re-opens a brace, so `ifEnd` lands on the function end and this particular check still misses it.

**Branch coverage tests** — the 5 largest non-main uncovered blocks (found via `--experimental-test-coverage`) got direct tests: `analyzeAsyncPatterns` unhandled-rejection look-ahead, `analyzeCodeSmells` arrow ≥5 params, `analyzeGuardClauses` if/else-wraps-body, `analyzeParameterObjects` trailing optional params, `analyzeReturnPaths` unreachable code on the return line. Suite 1511→1555.

---

## More Analyzers (F35, F36, F42–F45)

```javascript
import {
  detectTestFiles, analyzeGitHotspots,
  detectApiRoutes, formatApiRoutesReport,
  extractImports, detectProject, analyzeImportHealth, formatImportHealthReport,
} from './context-forge.mjs'

const tests = await detectTestFiles('./')          // → { files }, framework detection
const hot = await analyzeGitHotspots('./')         // → { hotspots, totalCommits }
const routes = await detectApiRoutes('./')         // → { routes, frameworks, count, byMethod }
console.log(formatApiRoutesReport(routes))         // markdown table by method

const info = await detectProject('./')             // project metadata (deps, pkg)
const imports = await extractImports('./', 3)      // → { imports: Map, allImports }
const ih = analyzeImportHealth(info, imports)      // note: takes BOTH results
// → { unusedDeps, mostImported, totalImports, uniqueImports, diversityScore }
```

---

## How It Works

```
context-forge scans:
  ├── package.json / pyproject.toml / Cargo.toml  → deps, scripts, entry points
  ├── Directory structure                          → architecture patterns
  ├── Git history (optional)                       → naming conventions, recent changes
  └── Existing context files                       → preserve manual additions

Then generates:
  └── Context files with project summary, conventions, and AI instructions
```

### Update Mode

When you use `--update`, context-forge preserves any content you've manually added between `<!-- context-forge:start -->` and `<!-- context-forge:end -->` markers, while refreshing the auto-generated sections.

## Extending

`context-forge.mjs` is a single ESM file. Key extension points:

- **New project detectors** — add a function that returns `{ type, language, framework }` from project files
- **New output templates** — add a generator function for new AI tool formats
- **Custom markers** — modify `MARKER_START`/`MARKER_END` constants

## License

MIT
