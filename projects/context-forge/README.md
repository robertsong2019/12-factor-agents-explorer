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
