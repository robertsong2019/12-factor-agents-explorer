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
- ⏳ **Bi-temporal validity** — time-window edge tracking, point-in-time queries (F31)
- 🔐 **Secret scanner** — detect API keys, tokens, passwords, private keys with risk levels (F32)
- 📖 **Doc readability** — A-F grade scoring, heading hierarchy, paragraph/sentence analysis (F33)
- 🪦 **Dead code detector** — find unused exports by cross-referencing imports (F34)
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

## Bi-Temporal Validity (F31)

Time-window edge tracking for dependency graphs.

```javascript
import {
  edge_set_validity, edge_invalidate, edge_valid_at,
  temporal_snapshot, edge_temporal_history
} from './context-forge.mjs'

// Set validity window on an edge
edge_set_validity(graph, './a', './b', { valid_from: '2026-01-01', valid_until: '2026-06-01' })

// Invalidate an edge (with audit trail)
edge_invalidate(graph, './a', './b', { reason: 'refactored out' })

// Check if edge was valid at a specific time
edge_valid_at(graph, './a', './b', '2026-03-15')  // → true

// Time-travel: all valid edges at time T
temporal_snapshot(graph, '2026-03-15')

// Per-node temporal history
edge_temporal_history(graph, './a')
// [{ edge: './a→./b', valid_from: ..., valid_until: ..., status: 'invalidated' }]
```

---

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

const importData = parseImports('./src')   // from F14: analyzeImports()
const apiSurface = extractApiSurface('./src') // from F28: scanCode()

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
