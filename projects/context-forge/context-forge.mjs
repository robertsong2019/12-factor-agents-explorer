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
import { join, basename, extname, relative, sep } from "node:path";
import { existsSync as fsExistsSync } from "node:fs";

export const existsSync = fsExistsSync;

// ─── Import Statement Extraction ───────────────────────────────────────

const IMPORT_PATTERNS = {
  javascript: [
    // import ... from '...'
    /import\s+(?:(?:\{[^}]*\})|(?:[^\s]+)|(?:\*\s+as\s+[^\s]+))\s+from\s+['"]([^'"]+)['"]/g,
    // import('...')
    /import\(['"]([^'"]+)['"]\)/g,
    // require('...')
    /require\(['"]([^'"]+)['"]\)/g,
  ],
  typescript: [
    // All JS patterns plus TypeScript specifics
    /import\s+(?:(?:\{[^}]*\})|(?:[^\s]+)|(?:\*\s+as\s+[^\s]+))\s+from\s+['"]([^'"]+)['"]/g,
    /import\(['"]([^'"]+)['"]\)/g,
    /require\(['"]([^'"]+)['"]\)/g,
    // TypeScript import type
    /import\s+type\s+(?:(?:\{[^}]*\})|(?:[^\s]+))\s+from\s+['"]([^'"]+)['"]/g,
  ],
  python: [
    // import ...
    /^import\s+([\w.]+)/gm,
    // from ... import ...
    /^from\s+([\w.]+)\s+import/gm,
  ],
};

const DEFAULT_MAX_FILE_SIZE = 1024 * 100; // 100KB — skip files larger than this

export async function extractImports(root, maxDepth = 3, depth = 0, gitignore = [], maxFileSize = DEFAULT_MAX_FILE_SIZE) {
  const imports = new Map(); // { filepath: [imports] }
  const allImports = new Set(); // unique import paths

  if (depth >= maxDepth) return { imports, allImports: [...allImports] };

  try {
    const entries = await readdir(root, { withFileTypes: true });
    for (const e of entries) {
      const relativePath = depth === 0 ? e.name : relative(root, join(root, e.name));
      if (isIgnored(relativePath, gitignore)) continue;

      if (e.isDirectory() && !IGNORE_DIRS.has(e.name) && !e.name.startsWith(".")) {
        const result = await extractImports(join(root, e.name), maxDepth, depth + 1, gitignore, maxFileSize);
        for (const [k, v] of result.imports) imports.set(k, v);
        result.allImports.forEach(i => allImports.add(i));
      } else if (e.isFile()) {
        const fullPath = join(root, e.name);
        const fileStat = await stat(fullPath);
        if (fileStat.size > maxFileSize) continue;
        const ext = extname(e.name);
        const lang = LANGUAGE_MAP[ext];
        if (lang) {
          const content = await readFile(fullPath, "utf8");
          const fileImports = [];

          if (lang.includes("JavaScript") || lang.includes("TypeScript")) {
            const patterns = lang.includes("TypeScript") ? IMPORT_PATTERNS.typescript : IMPORT_PATTERNS.javascript;
            for (const pattern of patterns) {
              let match;
              while ((match = pattern.exec(content)) !== null) {
                const importPath = match[1] || match[2];
                if (importPath && !importPath.startsWith(".") && !importPath.startsWith("/")) {
                  fileImports.push(importPath);
                  allImports.add(importPath);
                }
              }
              pattern.lastIndex = 0; // Reset regex
            }
          } else if (lang.includes("Python")) {
            for (const line of content.split("\n")) {
              const trimmed = line.trim();
              if (trimmed.startsWith("import ") || trimmed.startsWith("from ")) {
                const match = trimmed.match(/^import\s+([\w.]+)/) || trimmed.match(/^from\s+([\w.]+)\s+import/);
                if (match) {
                  const importPath = match[1].split(".")[0]; // Get base module
                  fileImports.push(importPath);
                  allImports.add(importPath);
                }
              }
            }
          }

          if (fileImports.length > 0) {
            imports.set(relativePath, fileImports);
          }
        }
      }
    }
  } catch {}

  return { imports, allImports: [...allImports] };
}

// ─── Configuration File Parser (F4) ───────────────────────────────────

export async function parseConfigFiles(root) {
  const configs = {};

  // tsconfig.json
  const tsconfigPath = join(root, "tsconfig.json");
  if (existsSync(tsconfigPath)) {
    try {
      const raw = await readFile(tsconfigPath, "utf8");
      // Strip comments and trailing commas for JSON.parse
      const clean = raw.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "").replace(/,\s*([}\]])/g, "$1");
      const parsed = JSON.parse(clean);
      const co = parsed.compilerOptions || {};
      configs.tsconfig = {
        target: co.target || null,
        module: co.module || null,
        strict: co.strict ?? false,
        jsx: co.jsx || null,
        outDir: co.outDir || null,
        baseUrl: co.baseUrl || null,
        paths: co.paths ? Object.keys(co.paths) : [],
        hasTypeChecking: co.strict || co.noImplicitAny || co.strictNullChecks || false,
      };
    } catch {}
  }

  // .eslintrc.json
  for (const name of [".eslintrc.json", ".eslintrc"]) {
    const p = join(root, name);
    if (existsSync(p)) {
      try {
        const raw = await readFile(p, "utf8");
        const parsed = JSON.parse(raw);
        configs.eslint = {
          env: parsed.env ? Object.keys(parsed.env) : [],
          parser: parsed.parser || null,
          extends: parsed.extends || [],
          ruleCount: parsed.rules ? Object.keys(parsed.rules).length : 0,
          keyRules: parsed.rules ? Object.keys(parsed.rules).slice(0, 10) : [],
        };
        break;
      } catch {}
    }
  }

  // .prettierrc
  for (const name of [".prettierrc", ".prettierrc.json", ".prettierrc.js"]) {
    const p = join(root, name);
    if (existsSync(p)) {
      try {
        const raw = await readFile(p, "utf8");
        let parsed;
        if (name.endsWith(".js")) {
          // Extract object literal from JS file
          const m = raw.match(/\{[\s\S]*\}/);
          parsed = m ? eval("(" + m[0] + ")") : {};
        } else {
          parsed = JSON.parse(raw);
        }
        configs.prettier = {
          printWidth: parsed.printWidth || null,
          tabWidth: parsed.tabWidth ?? null,
          semi: parsed.semi ?? null,
          singleQuote: parsed.singleQuote ?? null,
          trailingComma: parsed.trailingComma || null,
        };
        break;
      } catch {}
    }
  }

  // vite.config / webpack.config presence
  for (const [key, files] of [
    ["vite", ["vite.config.js", "vite.config.mjs", "vite.config.ts"]],
    ["webpack", ["webpack.config.js", "webpack.config.ts"]],
    ["tailwind", ["tailwind.config.js", "tailwind.config.ts"]],
    ["postcss", ["postcss.config.js", "postcss.config.cjs"]],
  ]) {
    for (const f of files) {
      if (existsSync(join(root, f))) {
        configs[key] = { file: f };
        break;
      }
    }
  }

  // Dockerfile
  const dockerfilePath = join(root, "Dockerfile");
  if (existsSync(dockerfilePath)) {
    try {
      const raw = await readFile(dockerfilePath, "utf8");
      const fromMatch = raw.match(/^FROM\s+(\S+)/m);
      configs.docker = {
        baseImage: fromMatch ? fromMatch[1] : null,
        hasMultiStage: (raw.match(/^FROM/gm) || []).length > 1,
      };
    } catch {}
  }

  return configs;
}

// ─── API Surface Extraction (F3) ──────────────────────────────────────

const API_PATTERNS = {
  javascript: [
    // export function name(args) { / export async function name(args) {
    /(?:^|\n)\s*export\s+(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)/g,
    // export const/let/var name = (args) => { / export const name = function(args) {
    /(?:^|\n)\s*export\s+(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\(([^)]*)\)|function\s*\(([^)]*)\))/g,
    // export class Name { / export default class Name {
    /(?:^|\n)\s*export\s+(?:default\s+)?class\s+(\w+)/g,
    // module.exports = { name: function(args) { ... } }
    /(?:^|\n)\s*(\w+)\s*\(([^)]*)\)\s*\{/g,  // captures less precisely, used as fallback
  ],
  typescript: [
    // Same as JS plus TypeScript-specific
    /(?:^|\n)\s*export\s+(?:async\s+)?function\s+(\w+)\s*(?:<[^>]+>)?\s*\(([^)]*)\)/g,
    /(?:^|\n)\s*export\s+(?:const|let|var)\s+(\w+)\s*(?::\s*[^=]+)?=\s*(?:async\s*)?(?:\(([^)]*)\)|function\s*\(([^)]*)\))/g,
    /(?:^|\n)\s*export\s+(?:default\s+)?(?:abstract\s+)?class\s+(\w+)/g,
    // export interface Name / export type Name
    /(?:^|\n)\s*export\s+(?:interface|type)\s+(\w+)/g,
    // public methods inside classes: methodName(args) {
  ],
  python: [
    // def function_name(args):
    /^def\s+(\w+)\s*\(([^)]*)\)/gm,
    // class ClassName:
    /^class\s+(\w+)/gm,
    // async def function_name(args):
    /^async\s+def\s+(\w+)\s*\(([^)]*)\)/gm,
  ],
};

export async function extractApiSurface(root, maxDepth = 3, depth = 0, gitignore = [], maxFileSize = DEFAULT_MAX_FILE_SIZE) {
  const api = []; // { file, name, type, params, visibility }

  if (depth >= maxDepth) return api;

  try {
    const entries = await readdir(root, { withFileTypes: true });
    for (const e of entries) {
      const relativePath = depth === 0 ? e.name : relative(root, join(root, e.name));
      if (isIgnored(relativePath, gitignore)) continue;

      if (e.isDirectory() && !IGNORE_DIRS.has(e.name) && !e.name.startsWith(".")) {
        const sub = await extractApiSurface(join(root, e.name), maxDepth, depth + 1, gitignore, maxFileSize);
        api.push(...sub);
      } else if (e.isFile()) {
        const fullPath = join(root, e.name);
        const fileStat = await stat(fullPath);
        if (fileStat.size > maxFileSize) continue;
        const ext = extname(e.name);
        const lang = LANGUAGE_MAP[ext];
        if (!lang) continue;

        const content = await readFile(fullPath, "utf8");
        const filePath = depth === 0 ? e.name : relativePath;

        const isTS = lang.includes("TypeScript");
        const isJS = lang.includes("JavaScript");
        const isPy = lang.includes("Python");

        if (isJS || isTS) {
          const patterns = isTS ? API_PATTERNS.typescript : API_PATTERNS.javascript;
          // Functions
          let match;
          const funcRe = isTS
            ? /(?:^|\n)\s*export\s+(?:async\s+)?function\s+(\w+)\s*(?:<[^>]+>)?\s*\(([^)]*)\)/g
            : /(?:^|\n)\s*export\s+(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)/g;
          while ((match = funcRe.exec(content)) !== null) {
            api.push({ file: filePath, name: match[1], type: "function", params: match[2].trim(), visibility: "exported" });
          }
          // Arrow / const functions
          const arrowRe = isTS
            ? /(?:^|\n)\s*export\s+(?:const|let|var)\s+(\w+)\s*(?::\s*[^=]+)?=\s*(?:async\s*)?(?:\(([^)]*)\)|function\s*\(([^)]*)\))/g
            : /(?:^|\n)\s*export\s+(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\(([^)]*)\)|function\s*\(([^)]*)\))/g;
          while ((match = arrowRe.exec(content)) !== null) {
            const params = (match[2] || match[3] || "").trim();
            api.push({ file: filePath, name: match[1], type: "function", params, visibility: "exported" });
          }
          // Classes
          const classRe = isTS
            ? /(?:^|\n)\s*export\s+(?:default\s+)?(?:abstract\s+)?class\s+(\w+)/g
            : /(?:^|\n)\s*export\s+(?:default\s+)?class\s+(\w+)/g;
          while ((match = classRe.exec(content)) !== null) {
            api.push({ file: filePath, name: match[1], type: "class", params: "", visibility: "exported" });
          }
          // TypeScript interfaces and types
          if (isTS) {
            const typeRe = /(?:^|\n)\s*export\s+(?:interface|type)\s+(\w+)/g;
            while ((match = typeRe.exec(content)) !== null) {
              api.push({ file: filePath, name: match[1], type: "type", params: "", visibility: "exported" });
            }
          }
        } else if (isPy) {
          // Functions
          const funcRe = /^(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)/gm;
          let match;
          while ((match = funcRe.exec(content)) !== null) {
            // Skip dunder methods except __init__
            if (match[1].startsWith("__") && match[1].endsWith("__") && match[1] !== "__init__") continue;
            api.push({ file: filePath, name: match[1], type: "function", params: match[2].trim(), visibility: "public" });
          }
          // Classes
          const classRe = /^class\s+(\w+)/gm;
          while ((match = classRe.exec(content)) !== null) {
            api.push({ file: filePath, name: match[1], type: "class", params: "", visibility: "public" });
          }
        }
      }
    }
  } catch {}

  return api;
}

// ─── Gitignore Parsing ─────────────────────────────────────────────

export async function parseGitignore(root) {
  const gitignorePath = join(root, ".gitignore");
  if (!existsSync(gitignorePath)) return [];

  try {
    const content = await readFile(gitignorePath, "utf8");
    const patterns = [];
    for (const line of content.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      patterns.push(trimmed);
    }
    return patterns;
  } catch {
    return [];
  }
}

export function isIgnored(path, ignoredPatterns) {
  let ignored = false;
  const parts = path.split(sep);
  for (const pattern of ignoredPatterns) {
    let p = pattern;
    let isDir = p.endsWith("/");
    if (isDir) p = p.slice(0, -1);
    const isNegated = p.startsWith("!");
    if (isNegated) p = p.slice(1);

    const isWildcard = p.includes("*");

    let matches = false;
    if (isWildcard) {
      const regex = new RegExp(
        "^" +
        p
          .replace(/\./g, "\\.")
          .replace(/\*/g, ".*")
          .replace(/\?/g, ".") +
        "$"
      );
      for (const part of parts) {
        if (regex.test(part)) matches = true;
      }
      if (regex.test(path)) matches = true;
    } else {
      // Exact match or directory prefix match
      if (parts.includes(p)) matches = true;
      if (path.startsWith(p + sep)) matches = true;
      if (path === p) matches = true;
    }

    if (matches) {
      ignored = isNegated ? false : true;
    }
  }
  return ignored;
}

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

export async function scanLanguages(root, maxDepth = 3, depth = 0, gitignore = [], maxFileSize = DEFAULT_MAX_FILE_SIZE) {
  const langs = new Map();
  if (depth >= maxDepth) return langs;

  try {
    const entries = await readdir(root, { withFileTypes: true });
    for (const e of entries) {
      const relativePath = depth === 0 ? e.name : relative(root, join(root, e.name));
      if (isIgnored(relativePath, gitignore)) continue;
      if (e.isDirectory() && !IGNORE_DIRS.has(e.name) && !e.name.startsWith(".")) {
        const sub = await scanLanguages(join(root, e.name), maxDepth, depth + 1, gitignore, maxFileSize);
        for (const [k, v] of sub) langs.set(k, (langs.get(k) || 0) + v);
      } else if (e.isFile()) {
        const fullPath = join(root, e.name);
        let fileStat;
        try { fileStat = await stat(fullPath); } catch { continue; }
        if (maxFileSize > 0 && fileStat.size > maxFileSize) continue;
        const ext = extname(e.name);
        const lang = LANGUAGE_MAP[ext];
        if (lang) langs.set(lang, (langs.get(lang) || 0) + 1);
      }
    }
  } catch {}

  return langs;
}

export async function getDirStructure(root, prefix = "", maxDepth = 2, depth = 0, gitignore = []) {
  if (depth >= maxDepth) return "";
  let out = "";
  try {
    const entries = await readdir(root, { withFileTypes: true });
    const filtered = entries.filter(e => {
      const relativePath = depth === 0 ? e.name : relative(root, join(root, e.name));
      if (isIgnored(relativePath, gitignore)) return false;
      return !IGNORE_DIRS.has(e.name) && !e.name.startsWith(".") && e.name !== "node_modules";
    }).sort((a, b) => {
      if (a.isDirectory() !== b.isDirectory()) return a.isDirectory() ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    for (const e of filtered.slice(0, 30)) {
      out += `${prefix}${e.isDirectory() ? "📁" : "📄"} ${e.name}\n`;
      if (e.isDirectory()) {
        out += await getDirStructure(join(root, e.name), prefix + "  ", maxDepth, depth + 1, gitignore);
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

  const root = resolvePath(projectPath);
  if (!existsSync(root)) {
    console.error(`❌ Path not found: ${root}`);
    process.exit(1);
  }

  console.log(`🔨 context-forge — Analyzing ${basename(root)}...\n`);

  const [info, gitignore, langs, importData, apiSurface, configData] = await Promise.all([
    detectProject(root),
    parseGitignore(root),
    scanLanguages(root, 3, 0, gitignore),
    extractImports(root, 3, 0, gitignore),
    extractApiSurface(root, 3, 0, gitignore),
    parseConfigFiles(root),
  ]);
  info.apiSurface = apiSurface;
  info.configData = configData;

  if (options.json) {
    console.log(JSON.stringify({
      languages: Object.fromEntries(langs),
      frameworks: [...new Set(info.frameworks)],
      entryPoints: info.entryPoints,
      scripts: info.scripts,
      configFiles: info.configFiles,
      gitignore,
      imports: {
        total: importData.allImports.length,
        unique: [...new Set(importData.allImports)].length,
        byFile: Object.fromEntries(importData.imports),
      },
      apiSurface: apiSurface.slice(0, 100),
      apiSurfaceCount: apiSurface.length,
      configs: configData,
    }, null, 2));
    return;
  }

  const structure = await getDirStructure(root, "", 2, 0, gitignore);

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
