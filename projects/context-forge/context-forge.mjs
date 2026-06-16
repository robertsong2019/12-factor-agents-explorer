#!/usr/bin/env node
/**
 * context-forge 🔨 — Generate AI coding assistant context files from your codebase.
 *
 * Usage:
 *   node context-forge.mjs <project-path> [options]
 *
 * Options:
 *   --only <type>     Generate specific file only (agents|cursor|copilot|claude)
 *   --dry-run         Print to stdout instead of writing files
 *   --update          Update existing files, preserving manual sections
 *   --json            Output analysis as JSON
 */

import { readdir, readFile, writeFile, stat, mkdir } from "node:fs/promises";
import { join, basename, extname, relative } from "node:path";
import { existsSync } from "node:fs";

// ─── Project Detection ───────────────────────────────────────────

const LANGUAGE_MAP = {
  ".js": "JavaScript", ".mjs": "JavaScript (ESM)", ".cjs": "JavaScript (CJS)",
  ".ts": "TypeScript", ".tsx": "TypeScript (React)", ".jsx": "JavaScript (React)",
  ".py": "Python", ".go": "Go", ".rs": "Rust", ".rb": "Ruby",
  ".java": "Java", ".kt": "Kotlin", ".swift": "Swift", ".zig": "Zig",
  ".vue": "Vue", ".svelte": "Svelte",
};

const IGNORE_DIRS = new Set([
  "node_modules", ".git", "dist", "build", ".next", "__pycache__",
  ".venv", "venv", "target", ".turbo", "coverage", ".nuxt", ".output",
  ".cache", ".sass-cache", "vendor", "Pods", ".gradle", ".idea",
]);

export async function detectProject(root) {
  const files = await readdir(root);
  const info = { languages: new Map(), frameworks: [], entryPoints: [], scripts: {}, deps: {}, root };

  // package.json
  if (files.includes("package.json")) {
    try {
      const pkg = JSON.parse(await readFile(join(root, "package.json"), "utf8"));
      info.pkg = pkg;
      info.scripts = pkg.scripts || {};
      info.deps = { ...pkg.dependencies, ...pkg.devDependencies };
      if (pkg.main) info.entryPoints.push(pkg.main);
      if (pkg.module) info.entryPoints.push(pkg.module);
      if (pkg.bin) Object.values(pkg.bin).forEach(b => info.entryPoints.push(b));
      // Framework detection
      if (info.deps["next"]) info.frameworks.push("Next.js");
      if (info.deps["nuxt"]) info.frameworks.push("Nuxt");
      if (info.deps["express"]) info.frameworks.push("Express");
      if (info.deps["fastify"]) info.frameworks.push("Fastify");
      if (info.deps["hono"]) info.frameworks.push("Hono");
      if (info.deps["react"]) info.frameworks.push("React");
      if (info.deps["vue"]) info.frameworks.push("Vue");
      if (info.deps["svelte"]) info.frameworks.push("Svelte");
      if (info.deps["@angular/core"]) info.frameworks.push("Angular");
      if (info.deps["vitest"] || info.deps["jest"]) info.frameworks.push("Testing");
      if (info.deps["prisma"]) info.frameworks.push("Prisma");
      if (info.deps["drizzle-orm"]) info.frameworks.push("Drizzle");
    } catch {}
  }

  // pyproject.toml
  if (files.includes("pyproject.toml")) {
    info.frameworks.push("Python");
    try {
      const toml = await readFile(join(root, "pyproject.toml"), "utf8");
      if (toml.includes("fastapi")) info.frameworks.push("FastAPI");
      if (toml.includes("django")) info.frameworks.push("Django");
      if (toml.includes("flask")) info.frameworks.push("Flask");
      if (toml.includes("pytest")) info.frameworks.push("pytest");
    } catch {}
  }

  // Cargo.toml
  if (files.includes("Cargo.toml")) {
    info.frameworks.push("Rust/Cargo");
    try {
      const cargo = await readFile(join(root, "Cargo.toml"), "utf8");
      if (cargo.includes("actix")) info.frameworks.push("Actix");
      if (cargo.includes("axum")) info.frameworks.push("Axum");
      if (cargo.includes("tokio")) info.frameworks.push("Tokio");
      if (cargo.includes("clap")) info.frameworks.push("Clap CLI");
    } catch {}
  }

  // go.mod
  if (files.includes("go.mod")) {
    info.frameworks.push("Go Modules");
  }

  // Config files
  const configFiles = ["tsconfig.json", ".eslintrc", ".eslintrc.json", ".prettierrc",
    "tailwind.config", "vite.config", "webpack.config", "docker-compose.yml",
    "Dockerfile", ".env.example", "Makefile", "justfile"];
  info.configFiles = files.filter(f => configFiles.some(c => f.startsWith(c)));

  // Docker
  if (files.includes("Dockerfile") || files.includes("docker-compose.yml")) {
    info.frameworks.push("Docker");
  }

  // Monorepo detection
  if (files.includes("pnpm-workspace.yaml") || files.includes("lerna.json") || files.includes("turbo.json")) {
    info.monorepo = true;
    info.frameworks.push("Monorepo");
  }

  return info;
}

export async function scanLanguages(root, maxDepth = 3, depth = 0) {
  const langs = new Map();
  if (depth >= maxDepth) return langs;

  try {
    const entries = await readdir(root, { withFileTypes: true });
    for (const e of entries) {
      if (e.isDirectory() && !IGNORE_DIRS.has(e.name) && !e.name.startsWith(".")) {
        const sub = await scanLanguages(join(root, e.name), maxDepth, depth + 1);
        for (const [k, v] of sub) langs.set(k, (langs.get(k) || 0) + v);
      } else if (e.isFile()) {
        const ext = extname(e.name);
        const lang = LANGUAGE_MAP[ext];
        if (lang) langs.set(lang, (langs.get(lang) || 0) + 1);
      }
    }
  } catch {}

  return langs;
}

export async function getDirStructure(root, prefix = "", maxDepth = 2, depth = 0) {
  if (depth >= maxDepth) return "";
  let out = "";
  try {
    const entries = await readdir(root, { withFileTypes: true });
    const filtered = entries.filter(e =>
      !IGNORE_DIRS.has(e.name) && !e.name.startsWith(".") && e.name !== "node_modules"
    ).sort((a, b) => {
      if (a.isDirectory() !== b.isDirectory()) return a.isDirectory() ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    for (const e of filtered.slice(0, 30)) {
      out += `${prefix}${e.isDirectory() ? "📁" : "📄"} ${e.name}\n`;
      if (e.isDirectory()) {
        out += await getDirStructure(join(root, e.name), prefix + "  ", maxDepth, depth + 1);
      }
    }
    if (filtered.length > 30) out += `${prefix}... (${filtered.length - 30} more)\n`;
  } catch {}
  return out;
}

// ─── Context Generation ──────────────────────────────────────────

export function generateAgentsMd(info, langs, structure) {
  const langList = [...langs.entries()].sort((a, b) => b[1] - a[1]).map(([l, c]) => `${l} (${c} files)`);
  const primaryLang = langList[0] || "Unknown";

  let md = `# AGENTS.md — ${basename(info.root)}

## Project Overview

- **Primary Language:** ${primaryLang}
${info.pkg ? `- **Package:** ${info.pkg.name || basename(info.root)} v${info.pkg.version || "0.0.0"}` : ""}
${info.frameworks.length ? `- **Frameworks:** ${[...new Set(info.frameworks)].join(", ")}` : ""}
${info.monorepo ? "- **Structure:** Monorepo" : ""}

## Directory Structure

\`\`\`
${structure || "(empty)"}
\`\`\`

## Entry Points

${info.entryPoints.length ? info.entryPoints.map(e => `- \`${e}\``).join("\n") : "- (auto-detect from main/module fields)"}

## Key Scripts

${Object.keys(info.scripts).length
    ? Object.entries(info.scripts).map(([k, v]) => `- \`npm run ${k}\` → ${v}`).join("\n")
    : "- (none defined)"}

## Key Dependencies

${Object.keys(info.deps).length
    ? Object.entries(info.deps).slice(0, 15).map(([k, v]) => `- ${k}: ${v}`).join("\n") + (Object.keys(info.deps).length > 15 ? `\n- ... (${Object.keys(info.deps).length - 15} more)` : "")
    : "- (none)"}

## Config Files

${info.configFiles?.length ? info.configFiles.map(f => `- \`${f}\``).join("\n") : "- (none detected)"}

## Conventions

<!-- Add your coding conventions here -->
<!-- context-forge:update-section conventions -->

## Architecture Notes

<!-- Add architectural decisions and patterns here -->
<!-- context-forge:update-section architecture -->

## Development Workflow

1. Install: \`npm install\` (or equivalent)
2. Develop: \`npm run dev\` (if available)
3. Test: \`npm test\` (if available)
4. Build: \`npm run build\` (if available)

## Important Notes

<!-- Add anything AI assistants should know about this project -->
<!-- context-forge:update-section notes -->
`;

  return md;
}

export function generateCursorRules(info, langs, structure) {
  const primaryLang = [...langs.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || "Unknown";
  const frameworks = [...new Set(info.frameworks)];

  let rules = `# Context Rules for ${basename(info.root)}

## Project: ${basename(info.root)}
- Language: ${primaryLang}
${frameworks.length ? `- Frameworks: ${frameworks.join(", ")}` : ""}

## Code Style
- Follow existing patterns in the codebase
- Use TypeScript for new files when the project uses TypeScript
- Prefer named exports

## Important Files
${info.entryPoints.map(e => `- ${e}`).join("\n") || "- (auto-detect)"}

## Testing
- Write tests for new features
- Run tests before committing: ${info.scripts.test || "npm test"}

## Architecture
- Read existing code before making changes
- Follow the established directory structure
- Keep modules focused and small
`;

  return rules;
}

export function generateCopilotInstructions(info) {
  const frameworks = [...new Set(info.frameworks)];
  return `# Copilot Instructions — ${basename(info.root)}

## Project Context
${info.pkg ? `Package: ${info.pkg.name} — ${info.pkg.description || "No description"}` : basename(info.root)}
${frameworks.length ? `Frameworks: ${frameworks.join(", ")}` : ""}

## Guidelines
- Follow existing code style and patterns
- Use the project's established conventions
- Prefer the frameworks already in use
- Write tests for new functionality

## Scripts
${Object.entries(info.scripts).map(([k, v]) => `- \`npm run ${k}\`: ${v}`).join("\n") || "- (none)"}
`;
}

export function generateClaudeMd(info, langs, structure) {
  return `# CLAUDE.md — ${basename(info.root)}

This file provides context for Claude Code when working on this project.

## Project
${info.pkg ? `${info.pkg.name} v${info.pkg.version || "0.0.0"} — ${info.pkg.description || ""}` : basename(info.root)}

## Tech Stack
${[...langs.entries()].sort((a, b) => b[1] - a[1]).map(([l]) => `- ${l}`).join("\n") || "- (auto-detect)"}
${[...new Set(info.frameworks)].map(f => `- ${f}`).join("\n")}

## Commands
${Object.entries(info.scripts).map(([k]) => `- \`npm run ${k}\``).join("\n") || "- (check package.json)"}

## Structure
\`\`\`
${structure || "(see source)"}
\`\`\`
`;
}

// ─── File Update Logic ───────────────────────────────────────────

export async function writeOrUpdate(filePath, content, options) {
  if (options.dryRun) {
    console.log(`\n${"=".repeat(60)}`);
    console.log(`📄 ${filePath}`);
    console.log("=".repeat(60));
    console.log(content);
    return;
  }

  if (options.update && existsSync(filePath)) {
    const existing = await readFile(filePath, "utf8");
    // Preserve sections between <!-- context-forge:update-section X --> markers
    const sectionRegex = /<!-- context-forge:update-section (\w+) -->\n([\s\S]*?)<!-- \/context-forge:update-section -->/g;
    let match;
    while ((match = sectionRegex.exec(existing)) !== null) {
      const [full, name] = match;
      content = content.replace(
        new RegExp(`<!-- context-forge:update-section ${name} -->[\\s\\S]*?<!-- /context-forge:update-section -->`),
        full
      );
    }
  }

  const dir = filePath.substring(0, filePath.lastIndexOf("/"));
  if (dir && !existsSync(dir)) await mkdir(dir, { recursive: true });
  await writeFile(filePath, content, "utf8");
  console.log(`✅ Written: ${filePath}`);
}

// ─── Main ────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  const projectPath = args.find(a => !a.startsWith("--")) || ".";
  const options = {
    only: (() => {
      const eq = args.find(a => a.startsWith("--only="));
      if (eq) return eq.split("=")[1];
      const idx = args.indexOf("--only");
      if (idx >= 0 && idx + 1 < args.length && !args[idx + 1].startsWith("--")) return args[idx + 1];
      return undefined;
    })(),
    dryRun: args.includes("--dry-run"),
    update: args.includes("--update"),
    json: args.includes("--json"),
  };

  const root = resolve(projectPath);
  if (!existsSync(root)) {
    console.error(`❌ Path not found: ${root}`);
    process.exit(1);
  }

  console.log(`🔨 context-forge — Analyzing ${basename(root)}...\n`);

  const [info, langs] = await Promise.all([
    detectProject(root),
    scanLanguages(root),
  ]);

  if (options.json) {
    console.log(JSON.stringify({
      languages: Object.fromEntries(langs),
      frameworks: [...new Set(info.frameworks)],
      entryPoints: info.entryPoints,
      scripts: info.scripts,
      configFiles: info.configFiles,
    }, null, 2));
    return;
  }

  const structure = await getDirStructure(root);

  const generators = {
    agents: { file: "AGENTS.md", gen: () => generateAgentsMd(info, langs, structure) },
    cursor: { file: ".cursorrules", gen: () => generateCursorRules(info, langs, structure) },
    copilot: { file: ".github/copilot-instructions.md", gen: () => generateCopilotInstructions(info) },
    claude: { file: ".claude/CLAUDE.md", gen: () => generateClaudeMd(info, langs, structure) },
  };

  const targets = options.only
    ? { [options.only]: generators[options.only] }
    : generators;

  for (const [name, { file, gen }] of Object.entries(targets)) {
    if (!gen || !generators[name]) {
      console.error(`❌ Unknown type: ${name}. Use: agents, cursor, copilot, claude`);
      continue;
    }
    await writeOrUpdate(join(root, file), gen(), options);
  }

  console.log(`\n✨ Done! ${options.dryRun ? "(dry run — no files written)" : "Context files generated."}`);
}

export function resolvePath(p) {
  return p.startsWith("/") ? p : join(process.cwd(), p);
}

// Only run main when executed directly (not imported)
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(e => { console.error("❌ Error:", e.message); process.exit(1); });
}
