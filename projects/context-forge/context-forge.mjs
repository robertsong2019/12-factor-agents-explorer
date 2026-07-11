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
 *   --format <fmt>    Output analysis as structured format (json|toml|yaml)
 */

import { readdir, readFile, writeFile, stat, mkdir } from "node:fs/promises";
import { join, basename, extname, relative, sep } from "node:path";
import { existsSync as fsExistsSync, unlinkSync as fsUnlinkSync } from "node:fs";

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

export async function extractImports(root, maxDepth = 3, depth = 0, gitignore = [], maxFileSize = DEFAULT_MAX_FILE_SIZE, _origRoot = null) {
  const origRoot = _origRoot || root;
  const imports = new Map(); // { filepath: [imports] }
  const allImports = new Set(); // unique import paths

  if (depth >= maxDepth) return { imports, allImports: [...allImports] };

  try {
    const entries = await readdir(root, { withFileTypes: true });
    for (const e of entries) {
      const relativePath = relative(origRoot, join(root, e.name));
      if (isIgnored(relativePath, gitignore)) continue;

      if (e.isDirectory() && !IGNORE_DIRS.has(e.name) && !e.name.startsWith(".")) {
        const result = await extractImports(join(root, e.name), maxDepth, depth + 1, gitignore, maxFileSize, origRoot);
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

// ─── Validation Mode (F10) ────────────────────────────────────────────

export async function validateContext(root, generatedFiles) {
  const issues = [];
  const info = await detectProject(root);
  const gitignore = await parseGitignore(root);
  const langs = await scanLanguages(root, 3, 0, gitignore);

  for (const { file, type } of generatedFiles) {
    const filePath = join(root, file);
    if (!existsSync(filePath)) {
      issues.push({ file, severity: "error", message: "File does not exist" });
      continue;
    }

    const content = await readFile(filePath, "utf8");

    // Check: referenced scripts exist in package.json
    if (type === "agents" || type === "cursor" || type === "copilot" || type === "claude") {
      const scriptRefs = content.matchAll(/`npm run (\w+)`/g);
      for (const m of scriptRefs) {
        if (!info.scripts || !(m[1] in info.scripts)) {
          issues.push({ file, severity: "warning", message: `Script '${m[1]}' referenced but not found in package.json` });
        }
      }
    }

    // Check: entry points exist on disk
    if (type === "agents") {
      for (const ep of info.entryPoints) {
        if (!existsSync(join(root, ep))) {
          issues.push({ file, severity: "warning", message: `Entry point '${ep}' does not exist` });
        }
      }
    }

    // Check: stale update-section markers
    const openMarkers = (content.match(/<!-- context-forge:update-section \w+ -->/g) || []).length;
    const closeMarkers = (content.match(/<!-- \/context-forge:update-section -->/g) || []).length;
    if (openMarkers !== closeMarkers) {
      issues.push({ file, severity: "error", message: `Mismatched update-section markers: ${openMarkers} open, ${closeMarkers} close` });
    }

    // Check: languages detected match file content
    if (type === "agents") {
      const langList = [...langs.entries()].sort((a, b) => b[1] - a[1]).map(([l]) => l);
      for (const lang of langList.slice(0, 3)) {
        if (!content.includes(lang)) {
          issues.push({ file, severity: "info", message: `Language '${lang}' detected but not mentioned in file` });
        }
      }
    }
  }

  return issues;
}

// ─── Git History Analysis (F1) ───────────────────────────────────────────

import { execSync } from "node:child_process";

export async function analyzeGitHistory(root, maxCommits = 20) {
  const result = {
    isRepo: false,
    totalCommits: 0,
    contributors: [],
    recentCommits: [],
    commitFrequency: {},
    topFilesChanged: [],
  };

  try {
    // Check if it's a git repo
    execSync("git rev-parse --git-dir", { cwd: root, stdio: "pipe", timeout: 5000 });
    result.isRepo = true;
  } catch {
    return result;
  }

  const run = (cmd) => {
    try {
      return execSync(cmd, { cwd: root, encoding: "utf8", stdio: "pipe", timeout: 5000 }).trim();
    } catch {
      return "";
    }
  };

  // Total commits
  const totalStr = run("git rev-list --count HEAD");
  result.totalCommits = parseInt(totalStr, 10) || 0;

  // Contributors
  const contributorStr = run("git shortlog -sn HEAD");
  result.contributors = contributorStr
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^\s*(\d+)\s+(.+)$/);
      return match ? { name: match[2].trim(), commits: parseInt(match[1], 10) } : null;
    })
    .filter(Boolean)
    .slice(0, 10);

  // Recent commits
  const logStr = run(`git log --format="%H|%an|%ad|%s" --date=short -n ${maxCommits}`);
  result.recentCommits = logStr
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      const [hash, author, date, ...subjectParts] = line.split("|");
      return { hash: hash.slice(0, 7), author, date, subject: subjectParts.join("|") };
    });

  // Commit frequency by day of week
  const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const freqStr = run("git log --format=%ad --date=short -n 200");
  const freqMap = {};
  for (const line of freqStr.split("\n").filter(Boolean)) {
    const day = dayNames[new Date(line).getDay()];
    if (day) freqMap[day] = (freqMap[day] || 0) + 1;
  }
  result.commitFrequency = freqMap;

  // Top changed files
  const filesStr = run(`git log --name-only --format="" -n ${maxCommits * 3}`);
  const fileCount = {};
  for (const line of filesStr.split("\n").filter(Boolean)) {
    fileCount[line] = (fileCount[line] || 0) + 1;
  }
  result.topFilesChanged = Object.entries(fileCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([file, count]) => ({ file, changes: count }));

  return result;
}

// ─── Mermaid Diagram Generation (F5) ──────────────────────────────────

export async function generateMermaidDiagram(root, maxDepth = 2, depth = 0, gitignore = []) {
  const lines = ["graph TD"];
  const nodeIds = new Map(); // path -> id
  let idCounter = 0;

  function nodeId(path) {
    if (!nodeIds.has(path)) nodeIds.set(path, `N${idCounter++}`);
    return nodeIds.get(path);
  }

  async function walk(dir, parentId, dirName, currentDepth) {
    if (currentDepth >= maxDepth) return;
    try {
      const entries = await readdir(dir, { withFileTypes: true });
      const filtered = entries
        .filter(e => {
          const rp = e.name;
          if (isIgnored(rp, gitignore)) return false;
          return !IGNORE_DIRS.has(e.name) && !e.name.startsWith(".");
        })
        .sort((a, b) => {
          if (a.isDirectory() !== b.isDirectory()) return a.isDirectory() ? -1 : 1;
          return a.name.localeCompare(b.name);
        })
        .slice(0, 15); // limit per level

      for (const e of filtered) {
        const fullPath = join(dir, e.name);
        const displayName = e.isDirectory() ? `📁 ${e.name}` : `📄 ${e.name}`;
        const id = nodeId(fullPath);
        const label = displayName.replace(/"/g, "'");
        lines.push(`  ${id}["${label}"]`);
        if (parentId) lines.push(`  ${parentId} --> ${id}`);
        if (e.isDirectory()) {
          await walk(join(dir, e.name), id, e.name, currentDepth + 1);
        }
      }
      if (filtered.length === 15 && entries.length > 15) {
        const ellipsisId = nodeId(`${dir}__ellipsis`);
        lines.push(`  ${ellipsisId}["... +${entries.length - 15} more"]`);
        if (parentId) lines.push(`  ${parentId} --> ${ellipsisId}`);
      }
    } catch {}
  }

  const rootId = nodeId(root);
  lines.push(`  ${rootId}["📦 ${basename(root)}"]`);
  await walk(root, rootId, basename(root), 0);

  return lines.join("\n");
}

// ─── Analysis Cache (F14) ─────────────────────────────────────

export async function loadCache(root) {
  const cachePath = join(root, ".context-forge-cache.json");
  if (!fsExistsSync(cachePath)) return null;
  try {
    const raw = JSON.parse(await readFile(cachePath, "utf8"));
    // Check root directory mtime hasn't changed since cache was saved
    const rootStat = await stat(root);
    // Allow 2-second tolerance for filesystem mtime granularity
    if (raw.rootMtime && Math.abs(rootStat.mtimeMs - raw.rootMtime) <= 2000) {
      return raw;
    }
    return null;
  } catch {
    return null;
  }
}

export async function saveCache(root, data) {
  const cachePath = join(root, ".context-forge-cache.json");
  const rootStat = await stat(root);
  const cache = {
    rootMtime: rootStat.mtimeMs,
    version: 1,
    ...data,
  };
  await writeFile(cachePath, JSON.stringify(cache, null, 2), "utf8");
  return cache;
}

export function invalidateCache(root) {
  const cachePath = join(root, ".context-forge-cache.json");
  if (fsExistsSync(cachePath)) {
    try { fsUnlinkSync(cachePath); } catch {}
  }
}

// ─── Template System (F13) ─────────────────────────────────────

export function applyTemplate(template, data) {
  if (typeof template !== "string") return "";
  return template.replace(/\{\{(\w+(?:\.\w+)*)\}\}/g, (match, path) => {
    const parts = path.split(".");
    let value = data;
    for (const part of parts) {
      if (value == null) return ""; // null-safe, empty for missing paths
      value = value[part];
    }
    if (value == null) return "";
    if (Array.isArray(value)) return value.join(", ");
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  });
}

export function validateTemplate(template, availableKeys) {
  if (typeof template !== "string") return { valid: false, missing: [] };
  const regex = /\{\{(\w+(?:\.\w+)*)\}\}/g;
  const missing = [];
  let match;
  while ((match = regex.exec(template)) !== null) {
    const topKey = match[1].split(".")[0];
    if (!availableKeys.includes(topKey)) {
      missing.push(match[1]);
    }
  }
  return { valid: missing.length === 0, missing };
}

export function extractTemplateVars(template) {
  if (typeof template !== "string") return [];
  const regex = /\{\{(\w+(?:\.\w+)*)\}\}/g;
  const vars = new Set();
  let match;
  while ((match = regex.exec(template)) !== null) {
    vars.add(match[1]);
  }
  return [...vars];
}

// ─── Template Registry (F13) ───────────────────────────────────────

/**
 * Built-in named templates that can be referenced via --template=<name>.
 * Users can override these or add custom ones via registerTemplate().
 */
const _templateRegistry = new Map();

export function registerTemplate(name, template) {
  if (typeof name !== 'string' || typeof template !== 'string') {
    throw new TypeError('registerTemplate requires (name: string, template: string)');
  }
  _templateRegistry.set(name, template);
}

export function getTemplate(name) {
  return _templateRegistry.get(name) || null;
}

export function listTemplates() {
  return [..._templateRegistry.keys()];
}

export function removeTemplate(name) {
  return _templateRegistry.delete(name);
}

export function clearTemplates() {
  _templateRegistry.clear();
}

// Initialize with built-in templates
registerTemplate('brief', `# {{project.name}} Context Brief

Type: {{project.type}} | Version: {{project.version}}
Description: {{project.description}}

## Languages
{{languages}}

## Key Entry Points
{{entryPoints}}

## Frameworks
{{frameworks}}
`);

registerTemplate('json-compact', `{"name":"{{project.name}}","type":"{{project.type}}","version":"{{project.version}}","langs":[{{languages}}],"entry":[{{entryPoints}}]}`);

registerTemplate('dockerfile-hint', `# Dockerfile hints for {{project.name}}
# Project type: {{project.type}}
# Primary entry: {{entryPoints}}
# Dependencies: {{dependencies}}
# Use this info to choose the right base image and build steps.
`);

/**
 * Generate output from a named template using analysis data.
 * Falls back to inline template string if name not found.
 */
export function generateFromTemplate(templateOrName, data) {
  let template;
  if (_templateRegistry.has(templateOrName)) {
    template = _templateRegistry.get(templateOrName);
  } else {
    template = templateOrName; // treat as inline template string
  }
  const result = applyTemplate(template, data);
  return result;
}

// ─── Table Formatters (F6) ──────────────────────────────────────

export function formatScriptsTable(scripts, max = 20) {
  const entries = Object.entries(scripts).slice(0, max);
  if (entries.length === 0) return "- (none defined)";
  const rows = entries.map(([k, v]) => `| \`${k}\` | ${v} |`);
  const more = Object.keys(scripts).length > max ? `\n| ... | _${Object.keys(scripts).length - max} more_ |` : "";
  return `| Script | Command |\n|--------|---------|\n${rows.join("\n")}${more}`;
}

export function formatDepsTable(deps, max = 20) {
  const entries = Object.entries(deps).slice(0, max);
  if (entries.length === 0) return "- (none)";
  const rows = entries.map(([k, v]) => `| \`${k}\` | ${v} |`);
  const more = Object.keys(deps).length > max ? `\n| ... | _${Object.keys(deps).length - max} more_ |` : "";
  return `| Package | Version |\n|---------|---------|\n${rows.join("\n")}${more}`;
}

// ─── Context Generation ──────────────────────────────────────────

export function generateAgentsMd(info, langs, structure, gitInfo = null) {
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

${formatScriptsTable(info.scripts)}

## Key Dependencies

${formatDepsTable(info.deps)}

## Config Files

${info.configFiles?.length ? info.configFiles.map(f => `- \`${f}\``).join("\n") : "- (none detected)"}

${gitInfo && gitInfo.isRepo ? `## Git Activity

- **Total commits:** ${gitInfo.totalCommits}
${gitInfo.contributors.length ? `- **Top contributors:** ${gitInfo.contributors.slice(0, 5).map(c => `${c.name} (${c.commits})`).join(", ")}` : ""}
${gitInfo.topFilesChanged.length ? `- **Most changed:** ${gitInfo.topFilesChanged.slice(0, 5).map(f => `\`${f.file}\` (${f.changes}x)`).join(", ")}` : ""}
` : ""}

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

## Scripts
${formatScriptsTable(info.scripts)}

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
${formatScriptsTable(info.scripts)}
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
${formatScriptsTable(info.scripts)}

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

// ─── Diff Preview (F12) ───────────────────────────────────────────────────

export function generateDiff(existing, updated) {
  const existingLines = existing.split("\n");
  const updatedLines = updated.split("\n");
  const result = [];

  // Simple LCS-based diff
  const n = existingLines.length;
  const m = updatedLines.length;
  const dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      if (existingLines[i - 1] === updatedLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack to produce diff
  const diffs = [];
  let i = n, j = m;
  while (i > 0 && j > 0) {
    if (existingLines[i - 1] === updatedLines[j - 1]) {
      diffs.unshift({ type: "context", line: existingLines[i - 1], oldLine: i, newLine: j });
      i--; j--;
    } else if (dp[i - 1][j] >= dp[i][j - 1]) {
      diffs.unshift({ type: "removed", line: existingLines[i - 1], oldLine: i });
      i--;
    } else {
      diffs.unshift({ type: "added", line: updatedLines[j - 1], newLine: j });
      j--;
    }
  }
  while (i > 0) {
    diffs.unshift({ type: "removed", line: existingLines[i - 1], oldLine: i });
    i--;
  }
  while (j > 0) {
    diffs.unshift({ type: "added", line: updatedLines[j - 1], newLine: j });
    j--;
  }

  // Condense: keep up to 3 context lines around changes
  const changeIdxs = diffs.map((d, idx) => d.type !== "context" ? idx : -1).filter(idx => idx >= 0);
  if (changeIdxs.length === 0) return [];

  const keep = new Set();
  for (const idx of changeIdxs) {
    for (let k = Math.max(0, idx - 3); k <= Math.min(diffs.length - 1, idx + 3); k++) {
      keep.add(k);
    }
  }

  // Add separators between non-contiguous kept ranges
  const sortedKeep = [...keep].sort((a, b) => a - b);
  let lastIdx = -2;
  for (const idx of sortedKeep) {
    if (idx > lastIdx + 1 && lastIdx >= 0) {
      result.push({ type: "separator" });
    }
    result.push(diffs[idx]);
    lastIdx = idx;
  }

  return result;
}

export function formatDiff(diffs) {
  if (diffs.length === 0) return "(no changes)";
  const lines = [];
  for (const d of diffs) {
    if (d.type === "added") lines.push(`+ ${d.line}`);
    else if (d.type === "removed") lines.push(`- ${d.line}`);
    else if (d.type === "separator") lines.push("...");
    else lines.push(`  ${d.line}`);
  }
  return lines.join("\n");
}

// ─── Structured Export Formats (F7) ────────────────────────────────

/**
 * Export analysis data as TOML.
 * Zero-dependency TOML serializer — handles strings, numbers, booleans,
 * arrays, and flat/nested objects.
 */
export function exportTOML(data) {
  const lines = [];

  function escapeStr(s) {
    if (s === "") return '""';
    // Basic TOML string escaping
    return '"' + String(s)
      .replace(/\\/g, '\\\\')
      .replace(/"/g, '\\"')
      .replace(/\n/g, '\\n')
      .replace(/\t/g, '\\t')
      .replace(/\r/g, '\\r') + '"';
  }

  function formatVal(v) {
    if (v === null || v === undefined) return '""';
    if (typeof v === 'boolean') return v ? 'true' : 'false';
    if (typeof v === 'number') return String(v);
    if (Array.isArray(v)) {
      if (v.length === 0) return '[]';
      const items = v.map(item =>
        typeof item === 'object' && item !== null
          ? '{ ' + Object.entries(item).map(([k, val]) => `${k} = ${formatVal(val)}`).join(', ') + ' }'
          : formatVal(item)
      );
      // Multi-line array for readability if any item is complex
      if (items.some(i => i.length > 40)) {
        return '[\n' + items.map(i => '  ' + i).join(',\n') + '\n]';
      }
      return '[' + items.join(', ') + ']';
    }
    if (typeof v === 'object') return escapeStr(JSON.stringify(v));
    return escapeStr(String(v));
  }

  function writeTable(prefix, obj) {
    const scalarKeys = [];
    const tableKeys = [];
    const arrayTableKeys = [];

    for (const [k, v] of Object.entries(obj)) {
      if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
        tableKeys.push(k);
      } else if (Array.isArray(v) && v.length > 0 && v.every(i => typeof i === 'object' && i !== null)) {
        arrayTableKeys.push(k);
      } else {
        scalarKeys.push(k);
      }
    }

    if (scalarKeys.length > 0 || prefix === '') {
      if (prefix) lines.push(`[${prefix}]`);
      for (const k of scalarKeys) {
        lines.push(`${k} = ${formatVal(obj[k])}`);
      }
      if (prefix && scalarKeys.length > 0) lines.push('');
    }

    for (const k of tableKeys) {
      const newPrefix = prefix ? `${prefix}.${k}` : k;
      writeTable(newPrefix, obj[k]);
    }

    for (const k of arrayTableKeys) {
      const tablePath = prefix ? `${prefix}.${k}` : k;
      for (const item of obj[k]) {
        lines.push(`[[${tablePath}]]`);
        for (const [ik, iv] of Object.entries(item)) {
          if (iv !== null && typeof iv === 'object' && !Array.isArray(iv)) {
            // Nested object in array-of-tables — inline it
            lines.push(`${ik} = ${formatVal(iv)}`);
          } else {
            lines.push(`${ik} = ${formatVal(iv)}`);
          }
        }
        lines.push('');
      }
    }
  }

  writeTable('', data);
  return lines.join('\n');
}

/**
 * Export analysis data as YAML.
 * Zero-dependency YAML serializer — handles strings, numbers, booleans,
 * arrays, and nested objects with proper indentation.
 */
export function exportYAML(data) {
  const lines = [];

  function needsQuote(s) {
    if (s === '') return true;
    // Quote if starts with special chars, contains ': ', '#', or is a YAML keyword
    if (/^[\-?:,[\]{}#&*!|>'"%@`]/.test(s)) return true;
    if (/:\s/.test(s)) return true;
    if (/\s+$/.test(s)) return true;
    if (/^(true|false|null|yes|no|~)$/i.test(s)) return true;
    if (/^\d/.test(s) && !/^\d+$/.test(s)) return true;
    return false;
  }

  function formatScalar(v) {
    if (v === null || v === undefined) return 'null';
    if (typeof v === 'boolean') return v ? 'true' : 'false';
    if (typeof v === 'number') return String(v);
    const s = String(v);
    if (/[\n\r\t]/.test(s) || s.includes('\\n') || s.includes('\\t')) {
      return JSON.stringify(s);  // Use double-quoted style for multiline/special
    }
    if (needsQuote(s)) return JSON.stringify(s);
    return s;
  }

  function writeValue(value, indent) {
    const pad = '  '.repeat(indent);

    if (Array.isArray(value)) {
      if (value.length === 0) {
        lines.push(`${pad}[]`);
        return;
      }
      for (const item of value) {
        if (item !== null && typeof item === 'object' && !Array.isArray(item)) {
          const entries = Object.entries(item);
          if (entries.length === 0) {
            lines.push(`${pad}- {}`);
          } else {
            lines.push(`${pad}-`);
            for (const [k, v] of entries) {
              if (v !== null && typeof v === 'object') {
                lines.push(`${pad}  ${k}:`);
                writeValue(v, indent + 2);
              } else {
                lines.push(`${pad}  ${k}: ${formatScalar(v)}`);
              }
            }
          }
        } else if (Array.isArray(item)) {
          lines.push(`${pad}-`);
          writeValue(item, indent + 1);
        } else {
          lines.push(`${pad}- ${formatScalar(item)}`);
        }
      }
      return;
    }

    if (value !== null && typeof value === 'object') {
      const entries = Object.entries(value);
      if (entries.length === 0) {
        lines.push(`${pad}{}`);
        return;
      }
      for (const [k, v] of entries) {
        if (Array.isArray(v) && v.length === 0) {
          lines.push(`${pad}${k}: []`);
        } else if (v !== null && typeof v === 'object' && Object.keys(v).length === 0) {
          lines.push(`${pad}${k}: {}`);
        } else if (v !== null && typeof v === 'object') {
          lines.push(`${pad}${k}:`);
          writeValue(v, indent + 1);
        } else {
          lines.push(`${pad}${k}: ${formatScalar(v)}`);
        }
      }
      return;
    }

    lines.push(`${pad}${formatScalar(value)}`);
  }

  writeValue(data, 0);
  return lines.join('\n');
}

/**
 * Build a structured analysis object suitable for TOML/YAML/JSON export.
 */
// ─── Complexity Analysis ─────────────────────────────────────────

export function analyzeComplexity(info, langs, importData, apiSurface, configData) {
  const langEntries = [...langs.entries()];
  const totalFiles = langEntries.reduce((s, [, c]) => s + c, 0);
  const totalDeps = Object.keys(info.dependencies || info.pkg?.dependencies || {}).length;
  const totalDevDeps = Object.keys(info.devDependencies || info.pkg?.devDependencies || {}).length;
  const totalScripts = Object.keys(info.scripts || info.pkg?.scripts || {}).length;
  const totalEntryPoints = (info.entryPoints || []).length;
  const totalImports = importData?.allImports?.length || 0;
  const uniqueImports = importData?.allImports ? new Set(importData.allImports).size : 0;
  const apiCount = apiSurface?.length || 0;
  const configCount = configData ? Object.keys(configData).length : 0;

  // Language diversity (Shannon entropy, normalized 0-1)
  let entropy = 0;
  for (const [, count] of langEntries) {
    if (count > 0 && totalFiles > 0) {
      const p = count / totalFiles;
      entropy -= p * Math.log2(p);
    }
  }
  const maxEntropy = Math.log2(Math.max(langEntries.length, 1));
  const languageDiversity = maxEntropy > 0 ? entropy / maxEntropy : 0;

  // Dominant language share (0-1)
  const dominantShare = totalFiles > 0
    ? Math.max(...langEntries.map(([, c]) => c)) / totalFiles
    : 0;

  // Complexity score (0-100): weighted sum of factors
  const depScore = Math.min(totalDeps * 2, 30);    // max 30 from deps
  const fileScore = Math.min(totalFiles, 25);        // max 25 from files
  const importScore = Math.min(uniqueImports, 20);   // max 20 from unique imports
  const apiScore = Math.min(apiCount, 15);           // max 15 from API surface
  const configScore = Math.min(configCount * 2, 10); // max 10 from configs
  const complexityScore = Math.round(depScore + fileScore + importScore + apiScore + configScore);

  // Size category
  const category = complexityScore < 20 ? 'minimal'
    : complexityScore < 40 ? 'small'
    : complexityScore < 60 ? 'medium'
    : complexityScore < 80 ? 'large'
    : 'enterprise';

  return {
    totalFiles,
    totalDeps,
    totalDevDeps,
    totalScripts,
    totalEntryPoints,
    totalImports,
    uniqueImports,
    apiCount,
    configCount,
    languageDiversity: Math.round(languageDiversity * 100) / 100,
    dominantShare: Math.round(dominantShare * 100) / 100,
    dominantLanguage: langEntries.sort((a, b) => b[1] - a[1])[0]?.[0] || 'unknown',
    complexityScore,
    category,
  };
}

export function summarizeAnalysis(info, langs, complexity) {
  const lines = [];
  const c = complexity || {};
  lines.push(`# Analysis Summary`);
  lines.push('');
  lines.push(`**Project:** ${info.name || info.pkg?.name || 'unknown'}`);
  lines.push(`**Type:** ${info.type || 'unknown'}`);
  lines.push(`**Complexity:** ${c.complexityScore ?? 'N/A'}/100 (${c.category ?? 'unknown'})`);
  lines.push('');
  lines.push('## Metrics');
  lines.push(`| Metric | Value |`);
  lines.push(`|--------|-------|`);
  lines.push(`| Files | ${c.totalFiles ?? 'N/A'} |`);
  lines.push(`| Dependencies | ${c.totalDeps ?? 'N/A'} |`);
  lines.push(`| Dev Dependencies | ${c.totalDevDeps ?? 'N/A'} |`);
  lines.push(`| Scripts | ${c.totalScripts ?? 'N/A'} |`);
  lines.push(`| Entry Points | ${c.totalEntryPoints ?? 'N/A'} |`);
  lines.push(`| Unique Imports | ${c.uniqueImports ?? 'N/A'} |`);
  lines.push(`| API Surface | ${c.apiCount ?? 'N/A'} |`);
  lines.push(`| Languages | ${langs.size} |`);
  lines.push(`| Language Diversity | ${c.languageDiversity ?? 'N/A'} |`);
  lines.push(`| Dominant Language | ${c.dominantLanguage ?? 'N/A'} (${Math.round((c.dominantShare || 0) * 100)}%) |`);
  lines.push('');
  lines.push('## Language Breakdown');
  for (const [lang, count] of [...langs.entries()].sort((a, b) => b[1] - a[1])) {
    const pct = c.totalFiles > 0 ? Math.round((count / c.totalFiles) * 100) : 0;
    lines.push(`- **${lang}**: ${count} files (${pct}%)`);
  }
  return lines.join('\n');
}

// ─── Project Comparison ──────────────────────────────────────────

export function compareProjects(before, after) {
  const changes = {
    added: [],
    removed: [],
    changed: [],
    summary: { totalChanges: 0, trend: 'stable' },
  };

  // Compare languages
  const beforeLangs = new Map(before.languages || []);
  const afterLangs = new Map(after.languages || []);
  const allLangs = new Set([...beforeLangs.keys(), ...afterLangs.keys()]);
  for (const lang of allLangs) {
    const b = beforeLangs.get(lang) || 0;
    const a = afterLangs.get(lang) || 0;
    if (b === 0 && a > 0) {
      changes.added.push({ type: 'language', name: lang, value: a });
    } else if (a === 0 && b > 0) {
      changes.removed.push({ type: 'language', name: lang, value: b });
    } else if (a !== b) {
      changes.changed.push({ type: 'language', name: lang, before: b, after: a, delta: a - b });
    }
  }

  // Compare dependencies
  const beforeDeps = new Map(Object.entries(before.dependencies || {}));
  const afterDeps = new Map(Object.entries(after.dependencies || {}));
  const allDeps = new Set([...beforeDeps.keys(), ...afterDeps.keys()]);
  for (const dep of allDeps) {
    const b = beforeDeps.get(dep);
    const a = afterDeps.get(dep);
    if (!b && a) {
      changes.added.push({ type: 'dependency', name: dep, value: a });
    } else if (b && !a) {
      changes.removed.push({ type: 'dependency', name: dep, value: b });
    } else if (b !== a) {
      changes.changed.push({ type: 'dependency', name: dep, before: b, after: a });
    }
  }

  // Compare scripts
  const beforeScripts = new Map(Object.entries(before.scripts || {}));
  const afterScripts = new Map(Object.entries(after.scripts || {}));
  const allScripts = new Set([...beforeScripts.keys(), ...afterScripts.keys()]);
  for (const script of allScripts) {
    const b = beforeScripts.get(script);
    const a = afterScripts.get(script);
    if (!b && a) {
      changes.added.push({ type: 'script', name: script, value: a });
    } else if (b && !a) {
      changes.removed.push({ type: 'script', name: script, value: b });
    } else if (b !== a) {
      changes.changed.push({ type: 'script', name: script, before: b, after: a });
    }
  }

  // Compare entry points
  const beforeEP = new Set(before.entryPoints || []);
  const afterEP = new Set(after.entryPoints || []);
  for (const ep of afterEP) {
    if (!beforeEP.has(ep)) changes.added.push({ type: 'entryPoint', name: ep });
  }
  for (const ep of beforeEP) {
    if (!afterEP.has(ep)) changes.removed.push({ type: 'entryPoint', name: ep });
  }

  // Compare complexity if available
  if (before.complexityScore !== undefined && after.complexityScore !== undefined) {
    const delta = after.complexityScore - before.complexityScore;
    if (delta !== 0) {
      changes.changed.push({
        type: 'complexity',
        name: 'complexityScore',
        before: before.complexityScore,
        after: after.complexityScore,
        delta,
      });
    }
  }

  // Compute summary
  changes.summary.totalChanges = changes.added.length + changes.removed.length + changes.changed.length;
  if (changes.summary.totalChanges === 0) {
    changes.summary.trend = 'stable';
  } else if (changes.added.length > changes.removed.length) {
    changes.summary.trend = 'growing';
  } else if (changes.removed.length > changes.added.length) {
    changes.summary.trend = 'shrinking';
  } else {
    changes.summary.trend = 'changing';
  }

  return changes;
}

export function formatComparison(changes) {
  const lines = [];
  const { added, removed, changed, summary } = changes;

  lines.push(`# Project Comparison`);
  lines.push('');
  lines.push(`**Total changes:** ${summary.totalChanges}`);
  lines.push(`**Trend:** ${summary.trend}`);
  lines.push('');

  if (added.length > 0) {
    lines.push('## Added ✅');
    for (const item of added) {
      const val = item.value ? ` (${item.value})` : '';
      lines.push(`- [${item.type}] ${item.name}${val}`);
    }
    lines.push('');
  }

  if (removed.length > 0) {
    lines.push('## Removed ❌');
    for (const item of removed) {
      const val = item.value ? ` (${item.value})` : '';
      lines.push(`- [${item.type}] ${item.name}${val}`);
    }
    lines.push('');
  }

  if (changed.length > 0) {
    lines.push('## Changed 🔄');
    for (const item of changed) {
      if (item.delta !== undefined) {
        const sign = item.delta > 0 ? '+' : '';
        lines.push(`- [${item.type}] ${item.name}: ${item.before} → ${item.after} (${sign}${item.delta})`);
      } else {
        lines.push(`- [${item.type}] ${item.name}: ${item.before} → ${item.after}`);
      }
    }
  }

  return lines.join('\n');
}

// ─── Stale File Detection ──────────────────────────────────────

export async function detectStaleFiles(root, generatedFiles) {
  const stale = [];
  const info = await detectProject(root);

  for (const { file } of generatedFiles) {
    const filePath = join(root, file);
    if (!existsSync(filePath)) continue;

    const content = await readFile(filePath, "utf8");

    // Extract file path references from content (e.g., `src/index.js`, `./lib/utils.ts`)
    const pathPattern = /[A-Za-z_][\w-]*(?:\.[\w-]+)+[\w./-]*/g;
    const checked = new Set();

    for (const m of content.matchAll(pathPattern)) {
      const ref = m[0];
      if (checked.has(ref)) continue;
      checked.add(ref);

      // Skip URLs, version numbers, node_modules
      if (/^\d/.test(ref) || ref.includes('://') || ref.startsWith('node_modules')) continue;
      // Skip the generated file itself
      if (ref === file) continue;
      // Skip common non-file patterns
      if (!/\.(js|ts|mjs|jsx|tsx|py|go|rs|java|c|cpp|h|rb|php|sh|json|ya?ml|toml|md)$/i.test(ref)) continue;

      const relPath = ref.startsWith('./') ? ref.slice(2) : ref;
      const absPath = join(root, relPath);

      if (!existsSync(absPath)) {
        stale.push({ file, reference: ref, message: `Referenced file '${ref}' not found` });
      }
    }

    // Check for stale entry points
    for (const ep of info.entryPoints || []) {
      if (!existsSync(join(root, ep))) {
        stale.push({ file, reference: ep, message: `Entry point '${ep}' does not exist` });
      }
    }
  }

  // Deduplicate by file+reference
  const seen = new Set();
  return stale.filter(s => {
    const key = `${s.file}:${s.reference}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

// ─── Project Health Score ───────────────────────────────────────

export function computeHealthScore(info, langs, importData, apiSurface, configData, validationIssues) {
  const checks = [];
  const issues = validationIssues || [];
  const errorCount = issues.filter(i => i.severity === 'error').length;
  const warningCount = issues.filter(i => i.severity === 'warning').length;

  // 1. Entry points exist
  const entryPoints = info.entryPoints || [];
  const entryValid = entryPoints.length > 0;
  checks.push({ name: 'entryPoints', passed: entryValid, detail: entryValid ? `${entryPoints.length} found` : 'none detected' });

  // 2. Scripts defined
  const scripts = info.scripts || info.pkg?.scripts || {};
  const scriptCount = Object.keys(scripts).length;
  const scriptsOk = scriptCount > 0;
  checks.push({ name: 'scripts', passed: scriptsOk, detail: `${scriptCount} scripts` });

  // 3. Dependencies documented
  const depCount = Object.keys(info.dependencies || info.pkg?.dependencies || {}).length;
  const depsOk = depCount > 0;
  checks.push({ name: 'dependencies', passed: depsOk, detail: `${depCount} packages` });

  // 4. No validation errors
  const noErrors = errorCount === 0;
  checks.push({ name: 'noErrors', passed: noErrors, detail: `${errorCount} errors` });

  // 5. No validation warnings
  const noWarnings = warningCount === 0;
  checks.push({ name: 'noWarnings', passed: noWarnings, detail: `${warningCount} warnings` });

  // 6. Languages detected
  const langOk = langs.size > 0;
  checks.push({ name: 'languages', passed: langOk, detail: `${langs.size} detected` });

  // 7. Config files present
  const configOk = configData && Object.keys(configData).length > 0;
  checks.push({ name: 'configs', passed: configOk, detail: configOk ? `${Object.keys(configData).length} found` : 'none' });

  // 8. API surface detected
  const apiOk = apiSurface && apiSurface.length > 0;
  checks.push({ name: 'apiSurface', passed: apiOk, detail: apiOk ? `${apiSurface.length} exports` : 'none' });

  const passed = checks.filter(c => c.passed).length;
  const score = Math.round((passed / checks.length) * 100);

  let grade;
  if (score >= 90) grade = 'A';
  else if (score >= 75) grade = 'B';
  else if (score >= 50) grade = 'C';
  else if (score >= 25) grade = 'D';
  else grade = 'F';

  return { score, grade, passed: passed, total: checks.length, checks };
}

// ─── Dependency Graph Analysis (F20) ──────────────────────────────

export function buildDependencyGraph(importData) {
  const { imports: byFile, allImports } = importData;
  const nodes = [];
  const edges = [];
  const nodeSet = new Set();

  // File nodes
  for (const [file] of byFile) {
    if (!nodeSet.has(file)) {
      nodeSet.add(file);
      nodes.push({ id: file, type: 'file' });
    }
  }
  // Package nodes
  for (const pkg of allImports) {
    if (!nodeSet.has(pkg)) {
      nodeSet.add(pkg);
      nodes.push({ id: pkg, type: 'package' });
    }
  }
  // Edges: file → package
  for (const [file, deps] of byFile) {
    for (const dep of deps) {
      edges.push({ from: file, to: dep });
    }
  }

  // Adjacency list (file → [packages])
  const adjacency = {};
  for (const [file, deps] of byFile) {
    adjacency[file] = [...new Set(deps)];
  }

  // Reverse adjacency (package → [files])
  const reverseAdjacency = {};
  for (const [file, deps] of byFile) {
    for (const dep of deps) {
      if (!reverseAdjacency[dep]) reverseAdjacency[dep] = [];
      reverseAdjacency[dep].push(file);
    }
  }

  // Most depended-upon packages (sorted by usage count)
  const packageUsage = Object.entries(reverseAdjacency)
    .map(([pkg, files]) => ({ package: pkg, usedBy: files.length, files: files.sort() }))
    .sort((a, b) => b.usedBy - a.usedBy);

  return {
    nodes,
    edges,
    adjacency,
    reverseAdjacency,
    packageUsage,
    stats: {
      totalNodes: nodes.length,
      totalEdges: edges.length,
      fileNodes: nodes.filter(n => n.type === 'file').length,
      packageNodes: nodes.filter(n => n.type === 'package').length,
      avgDepsPerFile: byFile.size > 0 ? Math.round((edges.length / byFile.size) * 100) / 100 : 0,
      maxDepsFile: packageUsage.length > 0 ? { file: null, count: 0 } : null,
    },
  };
}

export function findCircularDependencies(importData) {
  const { imports: byFile } = importData;
  const visited = new Set();
  const inStack = new Set();
  const cycles = [];

  function dfs(node, path) {
    if (inStack.has(node)) {
      const cycleStart = path.indexOf(node);
      cycles.push(path.slice(cycleStart).concat(node));
      return;
    }
    if (visited.has(node)) return;

    visited.add(node);
    inStack.add(node);
    path.push(node);

    const deps = byFile.get(node) || [];
    for (const dep of deps) {
      if (byFile.has(dep)) {
        dfs(dep, path);
      }
    }

    path.pop();
    inStack.delete(node);
  }

  for (const [file] of byFile) {
    if (!visited.has(file)) {
      dfs(file, []);
    }
  }

  return cycles;
}

export function formatDependencyGraph(graph) {
  const lines = ['# Dependency Graph', ''];
  lines.push(`| Metric | Value |`);
  lines.push(`|--------|-------|`);
  lines.push(`| File Nodes | ${graph.stats.totalNodes - graph.stats.packageNodes} |`);
  lines.push(`| Package Nodes | ${graph.stats.packageNodes} |`);
  lines.push(`| Total Edges | ${graph.stats.totalEdges} |`);
  lines.push(`| Avg Deps/File | ${graph.stats.avgDepsPerFile} |`);
  lines.push('');
  lines.push('## Top Packages by Usage');
  for (const { package: pkg, usedBy, files } of graph.packageUsage.slice(0, 10)) {
    lines.push(`- **${pkg}** — ${usedBy} file${usedBy !== 1 ? 's' : ''}`);
  }
  return lines.join('\n');
}

// ─── Tech Stack Inference (F21) ──────────────────────────────────

const STACK_SIGNATURES = {
  // Frontend frameworks
  react: { deps: ['react', 'react-dom'], lang: ['JavaScript (React)', 'TypeScript (React)'], category: 'Frontend' },
  vue: { deps: ['vue'], lang: ['Vue'], category: 'Frontend' },
  svelte: { deps: ['svelte'], lang: ['Svelte'], category: 'Frontend' },
  angular: { deps: ['@angular/core'], lang: ['TypeScript'], category: 'Frontend' },
  next: { deps: ['next'], lang: null, category: 'Frontend' },
  nuxt: { deps: ['nuxt'], lang: null, category: 'Frontend' },
  // Backend
  express: { deps: ['express'], lang: null, category: 'Backend' },
  fastify: { deps: ['fastify'], lang: null, category: 'Backend' },
  koa: { deps: ['koa'], lang: null, category: 'Backend' },
  nest: { deps: ['@nestjs/core'], lang: null, category: 'Backend' },
  flask: { deps: ['flask'], lang: ['Python'], category: 'Backend' },
  django: { deps: ['django'], lang: ['Python'], category: 'Backend' },
  fastapi: { deps: ['fastapi'], lang: ['Python'], category: 'Backend' },
  actix: { deps: ['actix-web'], lang: ['Rust'], category: 'Backend' },
  axum: { deps: ['axum'], lang: ['Rust'], category: 'Backend' },
  gin: { deps: ['gin-gonic/gin', 'github.com/gin-gonic/gin'], lang: ['Go'], category: 'Backend' },
  rocket: { deps: ['rocket'], lang: ['Rust'], category: 'Backend' },
  // Build tools
  vite: { deps: ['vite'], lang: null, category: 'Build Tool' },
  webpack: { deps: ['webpack'], lang: null, category: 'Build Tool' },
  rollup: { deps: ['rollup'], lang: null, category: 'Build Tool' },
  esbuild: { deps: ['esbuild'], lang: null, category: 'Build Tool' },
  turbo: { deps: ['turbo', '@turbo/tooling'], lang: null, category: 'Build Tool' },
  // Testing
  jest: { deps: ['jest'], lang: null, category: 'Testing' },
  vitest: { deps: ['vitest'], lang: null, category: 'Testing' },
  mocha: { deps: ['mocha'], lang: null, category: 'Testing' },
  pytest: { deps: ['pytest'], lang: ['Python'], category: 'Testing' },
  // Database / ORM
  prisma: { deps: ['@prisma/client', 'prisma'], lang: null, category: 'Database' },
  drizzle: { deps: ['drizzle-orm'], lang: null, category: 'Database' },
  typeorm: { deps: ['typeorm'], lang: null, category: 'Database' },
  sequelize: { deps: ['sequelize'], lang: null, category: 'Database' },
  sqlalchemy: { deps: ['sqlalchemy'], lang: ['Python'], category: 'Database' },
  // Styling
  tailwind: { deps: ['tailwindcss'], lang: null, category: 'Styling' },
  styled: { deps: ['styled-components'], lang: null, category: 'Styling' },
  emotion: { deps: ['@emotion/react'], lang: null, category: 'Styling' },
  // Mobile
  expo: { deps: ['expo'], lang: null, category: 'Mobile' },
  reactnative: { deps: ['react-native'], lang: null, category: 'Mobile' },
  // DevOps
  docker: { deps: null, lang: null, category: 'DevOps', configFile: 'Dockerfile' },
  ci: { deps: null, lang: null, category: 'DevOps', configFile: '.github/workflows' },
};

export function inferTechStack(info, langs, importData, configData) {
  const allDeps = new Set([
    ...Object.keys(info.dependencies || info.pkg?.dependencies || {}),
    ...Object.keys(info.devDependencies || info.pkg?.devDependencies || {}),
    ...(importData?.allImports || []),
  ]);
  const langSet = new Set([...langs.keys()].flatMap(l => [l, l.split(' ')[0]]));
  const configKeys = configData ? new Set(Object.keys(configData)) : new Set();
  const detected = [];

  for (const [name, sig] of Object.entries(STACK_SIGNATURES)) {
    let depMatch = false;
    let langMatch = false;
    let configMatch = false;

    if (sig.deps) {
      depMatch = sig.deps.some(d => {
        // Handle scoped and unscoped package names
        const normalized = d.replace(/^github\.com\//, '');
        return allDeps.has(d) || allDeps.has(normalized) ||
          [...allDeps].some(dep => dep === d || dep.startsWith(d + '@'));
      });
    }
    if (sig.lang) {
      langMatch = sig.lang.some(l =>
        [...langSet].some(ls => ls.includes(l)));
    }
    if (sig.configFile) {
      configMatch = configKeys.has(sig.configFile) ||
        [...configKeys].some(k => k.startsWith(sig.configFile));
    }

    // Require at least a dep match or config match; lang is a bonus signal
    if (depMatch || configMatch) {
      detected.push({
        name,
        category: sig.category,
        confidence: (depMatch ? 0.5 : 0) + (langMatch ? 0.3 : 0) + (configMatch ? 0.2 : 0),
        signals: {
          dependency: depMatch,
          language: langMatch,
          config: configMatch,
        },
      });
    }
  }

  // Group by category, sort by confidence
  const byCategory = {};
  for (const d of detected) {
    if (!byCategory[d.category]) byCategory[d.category] = [];
    byCategory[d.category].push(d);
  }
  for (const cat of Object.keys(byCategory)) {
    byCategory[cat].sort((a, b) => b.confidence - a.confidence);
  }

  return {
    stack: detected.sort((a, b) => b.confidence - a.confidence),
    byCategory,
    summary: detected.map(d => `${d.name} (${d.category}, ${Math.round(d.confidence * 100)}%)`),
  };
}

export function formatTechStack(stack) {
  const lines = ['# Tech Stack', ''];
  const categories = Object.keys(stack.byCategory).sort();
  for (const cat of categories) {
    lines.push(`## ${cat}`);
    for (const { name, confidence, signals } of stack.byCategory[cat]) {
      const sigFlags = [
        signals.dependency ? 'dep' : '',
        signals.language ? 'lang' : '',
        signals.config ? 'cfg' : '',
      ].filter(Boolean).join('+');
      lines.push(`- **${name}** — ${Math.round(confidence * 100)}% (${sigFlags})`);
    }
    lines.push('');
  }
  return lines.join('\n');
}

// ─── Duplicate Import Detection (F22) ────────────────────────────

export function findDuplicateImports(importData) {
  const { imports: byFile, allImports } = importData;
  const importFiles = {}; // import → [files]

  for (const [file, deps] of byFile) {
    for (const dep of deps) {
      if (!importFiles[dep]) importFiles[dep] = [];
      importFiles[dep].push(file);
    }
  }

  // Find files with identical import sets
  const importSignature = {};
  for (const [file, deps] of byFile) {
    const sig = [...new Set(deps)].sort().join('|');
    if (!importSignature[sig]) importSignature[sig] = [];
    importSignature[sig].push(file);
  }
  const duplicateSignatures = Object.entries(importSignature)
    .filter(([, files]) => files.length > 1)
    .map(([sig, files]) => ({ signature: sig, files }))
    .sort((a, b) => b.files.length - a.files.length);

  // Most imported packages (potential shared utility candidates)
  const sharedImports = Object.entries(importFiles)
    .filter(([, files]) => files.length > 1)
    .map(([pkg, files]) => ({ package: pkg, fileCount: files.length, files: files.sort() }))
    .sort((a, b) => b.fileCount - a.fileCount);

  return {
    sharedImports,
    duplicateSignatures,
    stats: {
      totalTracked: Object.keys(importFiles).length,
      sharedCount: sharedImports.length,
      duplicateGroups: duplicateSignatures.length,
      maxSharedUsage: sharedImports.length > 0 ? sharedImports[0].fileCount : 0,
    },
  };
}

export function formatDuplicateReport(duplicates) {
  const lines = ['# Import Analysis', ''];
  lines.push(`| Metric | Value |`);
  lines.push(`|--------|-------|`);
  lines.push(`| Tracked Packages | ${duplicates.stats.totalTracked} |`);
  lines.push(`| Shared Packages | ${duplicates.stats.sharedCount} |`);
  lines.push(`| Duplicate Groups | ${duplicates.stats.duplicateGroups} |`);
  lines.push(`| Max Usage Count | ${duplicates.stats.maxSharedUsage} |`);
  lines.push('');
  if (duplicates.sharedImports.length > 0) {
    lines.push('## Most Shared Packages (extraction candidates)');
    for (const { package: pkg, fileCount } of duplicates.sharedImports.slice(0, 10)) {
      lines.push(`- **${pkg}** — used in ${fileCount} files`);
    }
  }
  if (duplicates.duplicateSignatures.length > 0) {
    lines.push('');
    lines.push('## Files with Identical Imports');
    for (const { files } of duplicates.duplicateSignatures.slice(0, 5)) {
      lines.push(`- ${files.join(', ')}`);
    }
  }
  return lines.join('\n');
}

// ─── Project Statistics (F23) ───────────────────────────────────

export function computeProjectStats(info, langs, importData, apiSurface, configData, complexity) {
  const langEntries = [...langs.entries()].sort((a, b) => b[1] - a[1]);
  const totalFiles = langEntries.reduce((s, [, c]) => s + c, 0);
  const allDeps = { ...(info.dependencies || info.pkg?.dependencies || {}) };
  const allDevDeps = { ...(info.devDependencies || info.pkg?.devDependencies || {}) };
  const depCount = Object.keys(allDeps).length;
  const devDepCount = Object.keys(allDevDeps).length;
  const scriptCount = Object.keys(info.scripts || info.pkg?.scripts || {}).length;
  const entryCount = (info.entryPoints || []).length;

  // Dependency ratio (deps per file)
  const depToFileRatio = totalFiles > 0 ? Math.round((depCount / totalFiles) * 100) / 100 : 0;

  // Test-to-code ratio (approximation: count test files from imports)
  const testFilePattern = /^(test|tests|spec|specs|__tests__)[/\\]|\.(test|spec)\./;
  let testFileCount = 0;
  if (importData?.imports) {
    for (const [file] of importData.imports) {
      if (testFilePattern.test(file)) testFileCount++;
    }
  }
  const codeFileCount = Math.max(totalFiles - testFileCount, 1);
  const testToCodeRatio = Math.round((testFileCount / codeFileCount) * 100) / 100;

  // Config coverage (% of expected configs present)
  const expectedConfigs = ['tsconfig.json', '.eslintrc', '.prettierrc', 'Dockerfile', 'package.json', 'README.md'];
  const presentConfigs = (configData ? Object.keys(configData) : []).concat(info.configFiles || []);
  const configCoverage = expectedConfigs.filter(c =>
    presentConfigs.some(p => p.includes(c.replace(/^\./, '')))
  ).length / expectedConfigs.length;

  // Maturity indicators
  const hasReadme = !!(info.configFiles || []).some(f => f.includes('README')) || !!(info.readme);
  const hasLicense = !!(info.configFiles || []).some(f => f.includes('LICENSE')) || !!(info.license);
  const hasCI = !!(info.configFiles || []).some(f => f.includes('workflows')) || !!(configData && configData['.github/workflows']);
  const hasTests = testFileCount > 0;
  const hasDocker = !!(info.configFiles || []).some(f => f.includes('Dockerfile'));

  const maturityChecks = { hasReadme, hasLicense, hasCI, hasTests, hasDocker };
  const maturityScore = Object.values(maturityChecks).filter(Boolean).length / 5;

  return {
    fileStats: { total: totalFiles, code: codeFileCount, tests: testFileCount, testToCodeRatio },
    depStats: { production: depCount, dev: devDepCount, total: depCount + devDepCount, depToFileRatio },
    scriptCount,
    entryCount,
    apiSurfaceCount: apiSurface?.length || 0,
    configCoverage: Math.round(configCoverage * 100) / 100,
    maturity: { ...maturityChecks, score: Math.round(maturityScore * 100) / 100, grade: maturityScore >= 0.8 ? 'A' : maturityScore >= 0.6 ? 'B' : maturityScore >= 0.4 ? 'C' : 'D' },
    topLanguages: langEntries.slice(0, 5).map(([lang, count]) => ({ language: lang, files: count, pct: totalFiles > 0 ? Math.round((count / totalFiles) * 100) : 0 })),
  };
}

export function formatProjectStats(stats) {
  const lines = ['# Project Statistics', ''];
  lines.push('## Files');
  lines.push(`| Metric | Value |`);
  lines.push(`|--------|-------|`);
  lines.push(`| Total Files | ${stats.fileStats.total} |`);
  lines.push(`| Code Files | ${stats.fileStats.code} |`);
  lines.push(`| Test Files | ${stats.fileStats.tests} |`);
  lines.push(`| Test/Code Ratio | ${stats.fileStats.testToCodeRatio} |`);
  lines.push('');
  lines.push('## Dependencies');
  lines.push(`| Production Deps | ${stats.depStats.production} |`);
  lines.push(`| Dev Deps | ${stats.depStats.dev} |`);
  lines.push(`| Total Deps | ${stats.depStats.total} |`);
  lines.push(`| Dep/File Ratio | ${stats.depStats.depToFileRatio} |`);
  lines.push('');
  lines.push('## Maturity');
  lines.push(`- README: ${stats.maturity.hasReadme ? '✅' : '❌'}`);
  lines.push(`- License: ${stats.maturity.hasLicense ? '✅' : '❌'}`);
  lines.push(`- CI/CD: ${stats.maturity.hasCI ? '✅' : '❌'}`);
  lines.push(`- Tests: ${stats.maturity.hasTests ? '✅' : '❌'}`);
  lines.push(`- Docker: ${stats.maturity.hasDocker ? '✅' : '❌'}`);
  lines.push(`- **Score: ${stats.maturity.grade} (${Math.round(stats.maturity.score * 100)}%)**`);
  lines.push('');
  lines.push('## Top Languages');
  for (const { language, files, pct } of stats.topLanguages) {
    lines.push(`- ${language}: ${files} (${pct}%)`);
  }
  return lines.join('\n');
}

// ─── Entry Point Analysis (F24) ──────────────────────────────────

export function analyzeEntryPoints(info, importData, apiSurface) {
  const entryPoints = info.entryPoints || [];
  const importMap = importData?.imports || new Map();
  const apiSet = new Set((apiSurface || []).map(a => a.name));

  return entryPoints.map(ep => {
    const epNormalized = ep.replace(/^\.\//, '').replace(/^\//, '');
    // Check if entry point is in the import graph (other files import it)
    const importedBy = [];
    for (const [file, deps] of importMap) {
      if (deps.some(d => d.includes(epNormalized) || epNormalized.includes(d))) {
        importedBy.push(file);
      }
    }

    // Check if entry point exports API surface
    const exports = [];
    for (const api of apiSurface || []) {
      if (api.file && (api.file.includes(epNormalized) || epNormalized.includes(api.file))) {
        exports.push(api.name);
      }
    }

    // Classify entry point type
    let type = 'unknown';
    if (ep.includes('bin/') || ep.includes('cli')) type = 'cli';
    else if (ep.includes('server') || ep.includes('app')) type = 'server';
    else if (ep.includes('index') || ep.includes('main')) type = 'library';
    else if (ep.includes('test')) type = 'test';

    return {
      path: ep,
      type,
      importedBy: importedBy.sort(),
      importedByCount: importedBy.length,
      exports: exports.slice(0, 20),
      exportCount: exports.length,
      isOrphan: importedBy.length === 0 && exports.length === 0,
    };
  });
}

export function formatEntryPointAnalysis(analysis) {
  const lines = ['# Entry Point Analysis', ''];
  for (const ep of analysis) {
    lines.push(`## ${ep.path}`);
    lines.push(`- **Type:** ${ep.type}`);
    lines.push(`- **Imported by:** ${ep.importedByCount} file${ep.importedByCount !== 1 ? 's' : ''}`);
    if (ep.importedBy.length > 0 && ep.importedBy.length <= 5) {
      for (const f of ep.importedBy) lines.push(`  - ${f}`);
    }
    lines.push(`- **Exports:** ${ep.exportCount}`);
    if (ep.isOrphan) {
      lines.push(`- ⚠️ **Orphaned** — not imported or exported`);
    }
    lines.push('');
  }
  return lines.join('\n');
}

// ─── Dependency Risk Audit (F25) ────────────────────────────────

const RISK_INDICATORS = {
  // Known potentially risky packages (supply chain concerns, abandoned)
  abandoned: ['gulp-util', 'request', 'node-uuid', 'left-pad', 'core-js@2'],
  // Packages with known security concerns patterns
  riskyPrefixes: ['rm-pkg', 'cross-spawn'],
};

export function auditDependencies(info) {
  const deps = { ...(info.dependencies || info.pkg?.dependencies || {}) };
  const devDeps = { ...(info.devDependencies || info.pkg?.devDependencies || {}) };
  const allDeps = { ...deps, ...devDeps };
  const entries = Object.entries(allDeps);

  // Version analysis
  let pinned = 0, caretRange = 0, tildeRange = 0, exactRange = 0, gitUrl = 0, latestTag = 0;
  const flagged = [];

  for (const [name, version] of entries) {
    const v = String(version).trim();

    // Version type classification
    if (v.startsWith('git+') || v.startsWith('github:') || v.startsWith('https://')) {
      gitUrl++;
      flagged.push({ name, version: v, risk: 'medium', reason: 'Git URL dependency — no version pinning' });
    } else if (v.startsWith('^')) {
      caretRange++;
    } else if (v.startsWith('~')) {
      tildeRange++;
    } else if (v === 'latest' || v === '*') {
      latestTag++;
      flagged.push({ name, version: v, risk: 'high', reason: `Uses '${v}' — unpinned, non-reproducible builds` });
    } else if (/^\d+\.\d+\.\d+/.test(v)) {
      exactRange++;
      pinned++;
    }

    // Check abandoned packages
    if (RISK_INDICATORS.abandoned.some(a => {
      const [pkg, ver] = a.split('@');
      return name === pkg && (!ver || v.includes(ver));
    })) {
      flagged.push({ name, version: v, risk: 'high', reason: 'Package is abandoned/deprecated' });
    }

    // Check risky prefixes
    if (RISK_INDICATORS.riskyPrefixes.some(p => name.startsWith(p))) {
      flagged.push({ name, version: v, risk: 'low', reason: 'Package prefix warrants review' });
    }
  }

  // Duplicate dependency check (same package in deps and devDeps)
  const duplicates = Object.keys(deps).filter(d => d in devDeps);
  for (const d of duplicates) {
    flagged.push({ name: d, version: deps[d], risk: 'low', reason: 'Listed in both dependencies and devDependencies' });
  }

  const total = entries.length || 1;
  const pinRate = Math.round((pinned / total) * 100) / 100;
  const flexibilityRate = Math.round(((caretRange + tildeRange) / total) * 100) / 100;

  // Overall risk score (0-100, lower is better)
  const riskScore = Math.min(100, flagged.filter(f => f.risk === 'high').length * 15 +
    flagged.filter(f => f.risk === 'medium').length * 8 +
    flagged.filter(f => f.risk === 'low').length * 3 +
    (latestTag * 10) + (gitUrl * 5) + Math.round((1 - pinRate) * 10));

  return {
    total: entries.length,
    versionTypes: { pinned, caret: caretRange, tilde: tildeRange, exact: exactRange, git: gitUrl, latest: latestTag },
    pinRate,
    flexibilityRate,
    flagged: flagged.sort((a, b) => {
      const order = { high: 0, medium: 1, low: 2 };
      return order[a.risk] - order[b.risk];
    }),
    duplicates,
    riskScore,
    riskGrade: riskScore < 15 ? 'A' : riskScore < 30 ? 'B' : riskScore < 50 ? 'C' : riskScore < 75 ? 'D' : 'F',
  };
}

export function formatRiskAudit(audit) {
  const lines = ['# Dependency Risk Audit', ''];
  lines.push(`**Risk Grade: ${audit.riskGrade} (${audit.riskScore}/100)**`);
  lines.push('');
  lines.push('## Version Pinning');
  lines.push(`| Type | Count |`);
  lines.push(`|------|-------|`);
  lines.push(`| Exact/Pinned | ${audit.versionTypes.pinned} |`);
  lines.push(`| Caret (^) | ${audit.versionTypes.caret} |`);
  lines.push(`| Tilde (~) | ${audit.versionTypes.tilde} |`);
  lines.push(`| Git URL | ${audit.versionTypes.git} |`);
  lines.push(`| Latest/* | ${audit.versionTypes.latest} |`);
  lines.push(`| **Pin Rate** | **${Math.round(audit.pinRate * 100)}%** |`);
  lines.push('');

  if (audit.flagged.length > 0) {
    lines.push('## Flagged Dependencies');
    for (const { name, version, risk, reason } of audit.flagged) {
      const icon = risk === 'high' ? '🔴' : risk === 'medium' ? '🟡' : '🔵';
      lines.push(`${icon} **${name}@${version}** (${risk}) — ${reason}`);
    }
  }

  if (audit.duplicates.length > 0) {
    lines.push('');
    lines.push('## Duplicated Dependencies');
    for (const d of audit.duplicates) {
      lines.push(`- ${d} (in both deps and devDeps)`);
    }
  }

  return lines.join('\n');
}

// ─── Code Quality Signals (F26) ──────────────────────────────────

export function detectQualitySignals(info, langs, importData, apiSurface, configData) {
  const signals = {
    typesafety: { score: 0, indicators: [] },
    testing: { score: 0, indicators: [] },
    linting: { score: 0, indicators: [] },
    formatting: { score: 0, indicators: [] },
    ci: { score: 0, indicators: [] },
    documentation: { score: 0, indicators: [] },
  };

  const allDeps = new Set([
    ...Object.keys(info.dependencies || info.pkg?.dependencies || {}),
    ...Object.keys(info.devDependencies || info.pkg?.devDependencies || {}),
    ...(importData?.allImports || []),
  ]);
  const configKeys = configData ? new Set(Object.keys(configData)) : new Set();
  const configFileStrs = (info.configFiles || []).join(' ');

  // Type safety
  if (allDeps.has('typescript')) { signals.typesafety.indicators.push('TypeScript dependency'); signals.typesafety.score += 30; }
  const tsFiles = [...langs.keys()].some(k => k.includes('TypeScript'));
  if (tsFiles) { signals.typesafety.indicators.push('TypeScript files present'); signals.typesafety.score += 20; }
  if (configKeys.has('tsconfig.json') || configFileStrs.includes('tsconfig')) { signals.typesafety.indicators.push('tsconfig.json'); signals.typesafety.score += 15; }
  if (allDeps.has('@types/node') || allDeps.has('@types/react')) { signals.typesafety.indicators.push('@types packages'); signals.typesafety.score += 10; }

  // Testing
  for (const framework of ['jest', 'vitest', 'mocha', 'pytest', '@testing-library']) {
    if (allDeps.has(framework)) { signals.testing.indicators.push(`${framework} detected`); signals.testing.score += 25; break; }
  }
  const testPattern = /^(test|tests|spec|__tests__)[/\\]|\.(test|spec)\./;
  let testFileCount = 0;
  if (importData?.imports) {
    for (const [file] of importData.imports) {
      if (testPattern.test(file)) testFileCount++;
    }
  }
  if (testFileCount > 0) { signals.testing.indicators.push(`${testFileCount} test files`); signals.testing.score += Math.min(30, testFileCount * 3); }
  if (configFileStrs.includes('jest.config') || configFileStrs.includes('vitest.config')) { signals.testing.indicators.push('Test config file'); signals.testing.score += 10; }

  // Linting
  for (const linter of ['eslint', 'biome', ' tslint']) {
    if (allDeps.has(linter.trim()) || configFileStrs.includes(linter.trim())) {
      signals.linting.indicators.push(`${linter.trim()} configured`);
      signals.linting.score += 30;
      break;
    }
  }
  if (configKeys.has('.eslintrc') || configFileStrs.includes('eslintrc')) { signals.linting.indicators.push('.eslintrc present'); signals.linting.score += 15; }

  // Formatting
  for (const fmt of ['prettier', 'dprint']) {
    if (allDeps.has(fmt) || configFileStrs.includes(fmt)) {
      signals.formatting.indicators.push(`${fmt} configured`);
      signals.formatting.score += 25;
      break;
    }
  }

  // CI/CD
  if (configFileStrs.includes('workflows') || configKeys.has('.github/workflows')) { signals.ci.indicators.push('GitHub Actions'); signals.ci.score += 30; }
  if (configFileStrs.includes('Dockerfile') || configKeys.has('Dockerfile')) { signals.ci.indicators.push('Docker'); signals.ci.score += 15; }
  if (configFileStrs.includes('docker-compose') || configKeys.has('docker-compose.yml')) { signals.ci.indicators.push('docker-compose'); signals.ci.score += 10; }
  if (configFileStrs.includes('.gitlab-ci') || configFileStrs.includes('Jenkinsfile')) { signals.ci.indicators.push('CI config'); signals.ci.score += 25; }

  // Documentation
  if (configFileStrs.includes('README')) { signals.documentation.indicators.push('README'); signals.documentation.score += 20; }
  if (configFileStrs.includes('LICENSE') || info.license) { signals.documentation.indicators.push('LICENSE'); signals.documentation.score += 15; }
  if (configFileStrs.includes('CONTRIBUTING') || configFileStrs.includes('CODE_OF_CONDUCT')) { signals.documentation.indicators.push('Contributing guidelines'); signals.documentation.score += 10; }
  if (configFileStrs.includes('CHANGELOG')) { signals.documentation.indicators.push('CHANGELOG'); signals.documentation.score += 10; }

  // Cap scores at 100
  for (const key of Object.keys(signals)) {
    signals[key].score = Math.min(100, signals[key].score);
  }

  const overall = Math.round(Object.values(signals).reduce((s, v) => s + v.score, 0) / Object.keys(signals).length);

  return {
    signals,
    overall,
    grade: overall >= 80 ? 'A' : overall >= 60 ? 'B' : overall >= 40 ? 'C' : overall >= 20 ? 'D' : 'F',
  };
}

export function formatQualitySignals(result) {
  const lines = ['# Code Quality Signals', ''];
  lines.push(`**Overall: ${result.grade} (${result.overall}/100)**`);
  lines.push('');

  const labels = { typesafety: 'Type Safety', testing: 'Testing', linting: 'Linting', formatting: 'Formatting', ci: 'CI/CD', documentation: 'Documentation' };
  for (const [key, { score, indicators }] of Object.entries(result.signals)) {
    const bar = '█'.repeat(Math.round(score / 10)) + '░'.repeat(10 - Math.round(score / 10));
    lines.push(`## ${labels[key]} — ${score}/100`);
    lines.push(`\`${bar}\``);
    if (indicators.length > 0) {
      for (const ind of indicators) lines.push(`- ✅ ${ind}`);
    } else {
      lines.push('- ⚠️ No signals detected');
    }
    lines.push('');
  }
  return lines.join('\n');
}

// ─── Monorepo Workspace Analysis (F27) ──────────────────────────

export async function detectWorkspaces(root) {
  const files = await readdir(root).catch(() => []);
  const workspaces = [];

  // pnpm-workspace.yaml
  if (files.includes('pnpm-workspace.yaml')) {
    try {
      const content = await readFile(join(root, 'pnpm-workspace.yaml'), 'utf8');
      const packages = content.split('\n')
        .filter(l => l.trim().startsWith('- '))
        .map(l => l.trim().slice(2).trim().replace(/["']/g, ''));
      workspaces.push({ manager: 'pnpm', config: 'pnpm-workspace.yaml', globs: packages });
    } catch {}
  }

  // package.json workspaces field
  if (files.includes('package.json')) {
    try {
      const pkg = JSON.parse(await readFile(join(root, 'package.json'), 'utf8'));
      if (pkg.workspaces) {
        const globs = Array.isArray(pkg.workspaces) ? pkg.workspaces : (pkg.workspaces.packages || []);
        workspaces.push({ manager: 'npm/yarn', config: 'package.json:workspaces', globs });
      }
    } catch {}
  }

  // turbo.json
  if (files.includes('turbo.json')) {
    workspaces.push({ manager: 'turborepo', config: 'turbo.json', globs: [] });
  }

  // lerna.json
  if (files.includes('lerna.json')) {
    try {
      const lerna = JSON.parse(await readFile(join(root, 'lerna.json'), 'utf8'));
      const globs = lerna.packages || ['packages/*'];
      workspaces.push({ manager: 'lerna', config: 'lerna.json', globs });
    } catch {}
  }

  // nx.json
  if (files.includes('nx.json')) {
    workspaces.push({ manager: 'nx', config: 'nx.json', globs: [] });
  }

  return workspaces;
}

export function matchGlob(path, glob) {
  // Simple glob matching: supports * and **
  // e.g. 'packages/*' matches 'packages/foo', 'packages/bar/baz' does NOT match 'packages/foo/bar'
  // '**' matches any depth
  const regexStr = glob
    .replace(/\./g, '\\.')
    .replace(/\*\*/g, '{{DOUBLE_STAR}}')
    .replace(/\*/g, '[^/]*')
    .replace(/\{\{DOUBLE_STAR\}\}/g, '.*');
  return new RegExp(`^${regexStr}$`).test(path);
}

export async function analyzeWorkspace(root, workspaceGlobs) {
  const packages = [];
  const entries = await readdir(root, { withFileTypes: true }).catch(() => []);

  for (const glob of workspaceGlobs) {
    // Handle simple patterns like 'packages/*'
    if (glob.endsWith('/*')) {
      const dir = glob.slice(0, -2);
      const dirEntries = await readdir(join(root, dir), { withFileTypes: true }).catch(() => []);
      for (const e of dirEntries) {
        if (!e.isDirectory() || e.name.startsWith('.') || e.name === 'node_modules') continue;
        const pkgPath = join(dir, e.name);
        const pkgInfo = await readPackageJson(join(root, pkgPath));
        if (pkgInfo) {
          packages.push({ path: pkgPath, name: pkgInfo.name || e.name, ...pkgInfo });
        }
      }
    }
  }

  // Analyze inter-package dependencies
  const packageNames = new Set(packages.map(p => p.name).filter(Boolean));
  const internalDeps = [];
  for (const pkg of packages) {
    const deps = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) };
    for (const [dep, version] of Object.entries(deps)) {
      if (packageNames.has(dep)) {
        internalDeps.push({ from: pkg.name, to: dep, version, type: pkg.devDependencies?.[dep] ? 'dev' : 'prod' });
      }
    }
  }

  return {
    packages: packages.map(p => ({
      name: p.name,
      path: p.path,
      version: p.version,
      deps: Object.keys(p.dependencies || {}).length,
      devDeps: Object.keys(p.devDependencies || {}).length,
      private: p.private || false,
    })),
    internalDeps,
    stats: {
      totalPackages: packages.length,
      internalDepLinks: internalDeps.length,
      avgDepsPerPackage: packages.length > 0
        ? Math.round(packages.reduce((s, p) => s + Object.keys(p.dependencies || {}).length, 0) / packages.length * 100) / 100
        : 0,
    },
  };
}

async function readPackageJson(pkgRoot) {
  try {
    const content = await readFile(join(pkgRoot, 'package.json'), 'utf8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

export function formatWorkspaceAnalysis(workspaces, analysis) {
  const lines = ['# Workspace Analysis', ''];

  if (workspaces.length === 0) {
    lines.push('No monorepo workspaces detected.');
    return lines.join('\n');
  }

  lines.push('## Workspace Managers');
  for (const ws of workspaces) {
    lines.push(`- **${ws.manager}** (${ws.config})`);
    if (ws.globs.length > 0) lines.push(`  Globs: ${ws.globs.join(', ')}`);
  }
  lines.push('');

  if (analysis && analysis.packages.length > 0) {
    lines.push(`## Packages (${analysis.stats.totalPackages})`);
    lines.push(`| Package | Version | Deps | DevDeps | Private |`);
    lines.push(`|---------|---------|------|---------|---------|`);
    for (const pkg of analysis.packages) {
      lines.push(`| ${pkg.name} | ${pkg.version || '-'} | ${pkg.deps} | ${pkg.devDeps} | ${pkg.private ? 'yes' : 'no'} |`);
    }
    lines.push('');
    lines.push(`**Stats:** ${analysis.stats.totalPackages} packages, ${analysis.stats.internalDepLinks} internal links, avg ${analysis.stats.avgDepsPerPackage} deps/pkg`);

    if (analysis.internalDeps.length > 0) {
      lines.push('');
      lines.push('## Internal Dependencies');
      for (const dep of analysis.internalDeps) {
        lines.push(`- ${dep.from} → ${dep.to} (${dep.type})`);
      }
    }
  }

  return lines.join('\n');
}

export function buildExportData(info, langs, importData, apiSurface, configData, gitInfo) {
  return {
    project: {
      name: info.name || info.pkg?.name || 'unknown',
      type: info.type || info.pkg?.type || 'unknown',
      version: info.version || info.pkg?.version || null,
      description: info.description || info.pkg?.description || null,
    },
    languages: Object.fromEntries(langs),
    frameworks: [...new Set(info.frameworks || [])],
    entryPoints: info.entryPoints || [],
    scripts: info.scripts || info.pkg?.scripts || {},
    dependencies: info.dependencies || info.deps || info.pkg?.dependencies || {},
    devDependencies: info.devDependencies || info.pkg?.devDependencies || {},
    imports: {
      total: importData?.allImports?.length || 0,
      unique: importData?.allImports ? [...new Set(importData.allImports)].length : 0,
    },
    apiSurfaceCount: apiSurface?.length || 0,
    apiSurface: (apiSurface || []).slice(0, 50),
    configs: configData || {},
    git: gitInfo ? {
      totalCommits: gitInfo.totalCommits || 0,
      contributors: (gitInfo.contributors || []).slice(0, 20),
      recentCommits: (gitInfo.recentCommits || []).slice(0, 10),
    } : null,
  };
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
    format: (() => {
      const eq = args.find(a => a.startsWith("--format="));
      if (eq) return eq.split("=")[1];
      const idx = args.indexOf("--format");
      if (idx >= 0 && idx + 1 < args.length && !args[idx + 1].startsWith("--")) return args[idx + 1];
      return undefined;
    })(),
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

  // Handle structured export formats: --json, --format=toml, --format=yaml
  const exportFormat = options.format || (options.json ? 'json' : null);
  if (exportFormat) {
    const exportData = buildExportData(info, langs, importData, apiSurface, configData, null);
    if (exportFormat === 'json') {
      // JSON includes extra fields not in the standard export object
      console.log(JSON.stringify({
        ...exportData,
        gitignore,
        imports: {
          ...exportData.imports,
          byFile: Object.fromEntries(importData.imports),
        },
        apiSurface: apiSurface.slice(0, 100),
      }, null, 2));
    } else if (exportFormat === 'toml') {
      console.log(exportTOML(exportData));
    } else if (exportFormat === 'yaml') {
      console.log(exportYAML(exportData));
    } else {
      console.error(`❌ Unknown format: ${exportFormat}. Use: json, toml, yaml`);
      process.exit(1);
    }
    return;
  }

  const structure = await getDirStructure(root, "", 2, 0, gitignore);
  const gitInfo = await analyzeGitHistory(root);

  const generators = {
    agents: { file: "AGENTS.md", gen: () => generateAgentsMd(info, langs, structure, gitInfo) },
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

// ─── F28: TODO/FIXME Comment Extraction ─────────────────────────────────

const TODO_PATTERNS = [
  { regex: /\bTODO\b[\s:)?]?\s*(.*)/gi, type: 'TODO', priority: 'medium' },
  { regex: /\bFIXME\b[\s:)?]?\s*(.*)/gi, type: 'FIXME', priority: 'high' },
  { regex: /\bHACK\b[\s:)?]?\s*(.*)/gi, type: 'HACK', priority: 'high' },
  { regex: /\bXXX\b[\s:)?]?\s*(.*)/gi, type: 'XXX', priority: 'high' },
  { regex: /\bBUG\b[\s:)?]?\s*(.*)/gi, type: 'BUG', priority: 'critical' },
  { regex: /\bNOTE\b[\s:)?]?\s*(.*)/gi, type: 'NOTE', priority: 'low' },
];

const TODO_FILE_EXTENSIONS = new Set([
  '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx',
  '.py', '.rb', '.go', '.rs', '.java', '.kt',
  '.c', '.cpp', '.h', '.hpp', '.cs', '.php',
  '.swift', '.scala', '.sh', '.bash', '.zsh',
  '.vue', '.svelte', '.astro',
  '.css', '.scss', '.less',
  '.html', '.xml', '.yaml', '.yml', '.toml', '.ini',
  '.sql', '.graphql', '.gql',
]);

export async function extractTODOComments(root, maxDepth = 3, depth = 0, gitignore = [], maxFileSize = DEFAULT_MAX_FILE_SIZE) {
  const results = [];
  const ignored = gitignore.length > 0 ? gitignore : ['.git', 'node_modules', 'dist', 'build', '.next'];

  async function scan(dir, d) {
    if (d > maxDepth) return;
    let entries;
    try { entries = await readdir(dir, { withFileTypes: true }); } catch { return; }
    for (const entry of entries) {
      if (ignored.includes(entry.name)) continue;
      const fullPath = join(dir, entry.name);
      if (entry.isDirectory()) {
        await scan(fullPath, d + 1);
      } else if (entry.isFile()) {
        const ext = extname(entry.name).toLowerCase();
        if (!TODO_FILE_EXTENSIONS.has(ext)) continue;
        let st;
        try { st = await stat(fullPath); } catch { continue; }
      if (st.size > maxFileSize) continue;
        let content;
        try { content = await readFile(fullPath, 'utf-8'); } catch { continue; }
        const lines = content.split('\n');
        for (let i = 0; i < lines.length; i++) {
          for (const pat of TODO_PATTERNS) {
            pat.regex.lastIndex = 0;
            const match = pat.regex.exec(lines[i]);
            if (match) {
              results.push({
                file: relative(root, fullPath),
                line: i + 1,
                type: pat.type,
                priority: pat.priority,
                text: (match[1] || '').trim() || lines[i].trim(),
              });
              break; // one match per line is enough
            }
          }
        }
      }
    }
  }

  await scan(root, depth);
  // Sort: critical > high > medium > low, then by file/line
  const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  results.sort((a, b) => {
    const pd = priorityOrder[a.priority] - priorityOrder[b.priority];
    if (pd !== 0) return pd;
    if (a.file !== b.file) return a.file.localeCompare(b.file);
    return a.line - b.line;
  });
  return results;
}

export function formatTODOReport(todos) {
  if (!todos || todos.length === 0) return 'No TODO/FIXME comments found. ✅';
  const lines = [];
  const byType = {};
  for (const t of todos) {
    if (!byType[t.type]) byType[t.type] = [];
    byType[t.type].push(t);
  }
  const typeOrder = ['BUG', 'FIXME', 'HACK', 'XXX', 'TODO', 'NOTE'];
  const emoji = { BUG: '🐛', FIXME: '🔧', HACK: '⚡', XXX: '⚠️', TODO: '📝', NOTE: '💡' };
  lines.push(`### TODO/FIXME Report (${todos.length} items)`);
  lines.push('');
  for (const type of typeOrder) {
    if (!byType[type]) continue;
    lines.push(`#### ${emoji[type] || '📝'} ${type} (${byType[type].length})`);
    for (const item of byType[type]) {
      const text = item.text.length > 80 ? item.text.slice(0, 77) + '...' : item.text;
      lines.push(`- \`${item.file}:${item.line}\` — ${text}`);
    }
    lines.push('');
  }
  return lines.join('\n');
}

// ─── F29: Environment Variable Detection ────────────────────────────────

const ENV_PATTERNS = {
  javascript: [
    /process\.env\.([A-Z_][A-Z0-9_]*)/g,
    /process\.env\[['"]([A-Z_][A-Z0-9_]*)['"]\]/g,
  ],
  typescript: [
    /process\.env\.([A-Z_][A-Z0-9_]*)/g,
    /process\.env\[['"]([A-Z_][A-Z0-9_]*)['"]\]/g,
  ],
  python: [
    /os\.environ\.get\(['"]([A-Z_][A-Z0-9_]*)['"]/g,
    /os\.environ\[['"]([A-Z_][A-Z0-9_]*)['"]\]/g,
    /os\.getenv\(['"]([A-Z_][A-Z0-9_]*)['"]/g,
  ],
  go: [
    /os\.Getenv\(['"]([A-Z_][A-Z0-9_]*)['"]/g,
  ],
  rust: [
    /std::env::var\(['"]([A-Z_][A-Z0-9_]*)['"]/g,
    /env::var\(['"]([A-Z_][A-Z0-9_]*)['"]/g,
  ],
};

const ENV_FILE_EXTENSIONS = {
  '.js': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript', '.jsx': 'javascript',
  '.ts': 'typescript', '.tsx': 'typescript',
  '.py': 'python',
  '.go': 'go',
  '.rs': 'rust',
};

const DOTENV_LINE = /^\s*([A-Z_][A-Z0-9_]*)\s*=/;

export async function detectEnvVars(root, maxDepth = 3, depth = 0, gitignore = [], maxFileSize = DEFAULT_MAX_FILE_SIZE) {
  const found = {};
  const ignored = gitignore.length > 0 ? gitignore : ['.git', 'node_modules', 'dist', 'build', '.next'];

  // Also check for .env files
  const envFiles = [];

  async function scan(dir, d) {
    if (d > maxDepth) return;
    let entries;
    try { entries = await readdir(dir, { withFileTypes: true }); } catch { return; }
    for (const entry of entries) {
      if (ignored.includes(entry.name)) continue;
      const fullPath = join(dir, entry.name);
      if (entry.isDirectory()) {
        await scan(fullPath, d + 1);
      } else if (entry.isFile()) {
        // Check for .env files
        if (/^\.env(\.|$)/.test(entry.name)) {
          let content;
          try { content = await readFile(fullPath, 'utf-8'); } catch { continue; }
          for (const line of content.split('\n')) {
            const m = DOTENV_LINE.exec(line);
            if (m && !found[m[1]]) {
              found[m[1]] = { name: m[1], source: 'dotenv', file: relative(root, fullPath) };
            }
          }
          envFiles.push(relative(root, fullPath));
          continue;
        }
      const ext = extname(entry.name).toLowerCase();
      const lang = ENV_FILE_EXTENSIONS[ext];
      if (!lang) continue;
      let st;
      try { st = await stat(fullPath); } catch { continue; }
      if (st.size > maxFileSize) continue;
        let content;
        try { content = await readFile(fullPath, 'utf-8'); } catch { continue; }
        const patterns = ENV_PATTERNS[lang] || [];
        for (const pat of patterns) {
          pat.lastIndex = 0;
          let m;
          while ((m = pat.exec(content)) !== null) {
            const varName = m[1];
            if (!found[varName]) {
              const lineNum = content.slice(0, m.index).split('\n').length;
              found[varName] = { name: varName, source: lang, file: relative(root, fullPath), line: lineNum };
            }
          }
        }
      }
    }
  }

  await scan(root, depth);
  const vars = Object.values(found).sort((a, b) => a.name.localeCompare(b.name));
  return { vars, envFiles };
}

export function formatEnvVarsReport(envData) {
  const { vars, envFiles } = envData;
  if (!vars || vars.length === 0) return 'No environment variables detected.';
  const lines = [];
  lines.push(`### Environment Variables (${vars.length} found)`);
  lines.push('');
  if (envFiles.length > 0) {
    lines.push('**Dotenv files found:**');
    for (const f of envFiles) lines.push(`- \`${f}\``);
    lines.push('');
  }
  lines.push('| Variable | Source | File |');
  lines.push('|----------|--------|------|');
  for (const v of vars) {
    lines.push(`| \`${v.name}\` | ${v.source} | ${v.file}${v.line ? ':' + v.line : ''} |`);
  }
  return lines.join('\n');
}

// ─── F30: License Detection ─────────────────────────────────────────────

const LICENSE_KEYWORDS = [
  { id: 'MIT', patterns: [/MIT License/i, /Permission is hereby granted, free of charge/i] },
  { id: 'Apache-2.0', patterns: [/Apache License,? Version 2\.0/i, /Licensed under the Apache License, Version 2\.0/i] },
  { id: 'BSD-2-Clause', patterns: [/Redistribution and use in source and binary forms.*with or without modification.*Redistributions of source code/i] },
  { id: 'BSD-3-Clause', patterns: [/Neither the name of.*nor the names of its contributors may be/i] },
  { id: 'GPL-3.0', patterns: [/GNU GENERAL PUBLIC LICENSE[\s\S]*?Version 3/i, /GPL-3(?:\.0)?(?:\s|$)/i] },
  { id: 'GPL-2.0', patterns: [/GNU GENERAL PUBLIC LICENSE[\s\S]*?Version 2/i, /GPL-2(?:\.0)?(?:\s|$)/i] },
  { id: 'LGPL-3.0', patterns: [/GNU LESSER GENERAL PUBLIC LICENSE/i, /LGPL-3/i] },
  { id: 'AGPL-3.0', patterns: [/GNU AFFERO GENERAL PUBLIC LICENSE/i, /AGPL-3/i] },
  { id: 'Unlicense', patterns: [/This is free and unencumbered software released into the public domain/i] },
  { id: 'ISC', patterns: [/ISC License/i] },
  { id: 'MPL-2.0', patterns: [/Mozilla Public License,? Version 2\.0/i, /MPL-2\.0/i] },
  { id: 'CC0-1.0', patterns: [/Creative Commons Zero.*CC0/i, /CC0 1\.0/i] },
];

export async function detectLicense(root) {
  const result = { id: null, source: null, file: null, confidence: 'none' };

  // 1. Check package.json license field
  try {
    const pkgContent = await readFile(join(root, 'package.json'), 'utf-8');
    const pkg = JSON.parse(pkgContent);
    if (pkg.license) {
      result.id = typeof pkg.license === 'string' ? pkg.license : (pkg.license.type || pkg.license);
      result.source = 'package.json';
      result.confidence = 'high';
      return result;
    }
  } catch {}

  // 2. Check pyproject.toml
  try {
    const pyContent = await readFile(join(root, 'pyproject.toml'), 'utf-8');
    const m = pyContent.match(/license\s*=\s*["']([^"']+)['"]/i);
    if (m) {
      result.id = m[1];
      result.source = 'pyproject.toml';
      result.confidence = 'high';
      return result;
    }
  } catch {}

  // 3. Check Cargo.toml
  try {
    const cargoContent = await readFile(join(root, 'Cargo.toml'), 'utf-8');
    const m = cargoContent.match(/license\s*=\s*["']([^"']+)['"]/i);
    if (m) {
      result.id = m[1];
      result.source = 'Cargo.toml';
      result.confidence = 'high';
      return result;
    }
  } catch {}

  // 4. Scan LICENSE files
  const licenseFileNames = ['LICENSE', 'LICENSE.md', 'LICENSE.txt', 'LICENSE-MIT', 'LICENSE-APACHE', 'COPYING', 'COPYING.md', 'NOTICE'];
  for (const fname of licenseFileNames) {
    try {
      const content = await readFile(join(root, fname), 'utf-8');
      for (const lic of LICENSE_KEYWORDS) {
        for (const pat of lic.patterns) {
          if (pat.test(content)) {
            result.id = lic.id;
            result.source = fname;
            result.file = fname;
            result.confidence = 'high';
            return result;
          }
        }
      }
      // File exists but no pattern matched — low confidence
      result.source = fname;
      result.file = fname;
      result.confidence = 'low';
    } catch {}
  }

  // 5. Check README for license mentions
  for (const rfname of ['README.md', 'README.rst', 'README.txt']) {
    try {
      const content = await readFile(join(root, rfname), 'utf-8');
      const m = content.match(/licen[sc]e\s*:?\s*([A-Za-z0-9\-+.]+)/i);
      if (m) {
        result.id = m[1];
        result.source = rfname;
        result.confidence = 'low';
        return result;
      }
    } catch {}
  }

  return result;
}

export function formatLicenseInfo(license) {
  if (!license || license.confidence === 'none') {
    return 'No license detected. ⚠️';
  }
  const confidenceEmoji = { high: '🟢', low: '🟡' };
  const lines = [
    `### License`,
    '',
    `- **License:** ${license.id || 'Unknown'}`,
    `- **Source:** ${license.source}`,
  ];
  if (license.file) lines.push(`- **File:** \`${license.file}\``);
  lines.push(`- **Confidence:** ${confidenceEmoji[license.confidence] || '⚪'} ${license.confidence}`);
  return lines.join('\n');
}

// --- F32: Secret Detection ---

const SECRET_HIGH_PATTERNS = [
  // AWS Access Key ID (20 chars)
  { regex: /AKIA[0-9A-Z]{16}/g, type: 'aws_access_key', description: 'AWS Access Key ID' },
  // AWS Secret Access Key (40 chars base64)
  { regex: /aws_secret_access_key\s*[=:]\s*['"]([A-Za-z0-9/+=]{40})['"]/gi, type: 'aws_secret_key', description: 'AWS Secret Access Key' },
  // GitHub token (classic + fine-grained)
  { regex: /gh[pousr]_[A-Za-z0-9]{36,255}/g, type: 'github_token', description: 'GitHub Token' },
  // Generic API key (key/apikey/secret assignments with 20+ char values)
  { regex: /(?:api[_-]?key|api[_-]?secret|secret[_-]?key)\s*[=:]\s*['"]([A-Za-z0-9_\-]{20,})['"]/gi, type: 'api_key', description: 'API Key' },
  // Bearer token
  { regex: /Bearer\s+[A-Za-z0-9_\-\.]{20,}/g, type: 'bearer_token', description: 'Bearer Token' },
  // Private key blocks
  { regex: /-----BEGIN\s+(RSA\s+|EC\s+|OPENSSH\s+|PGP\s+)?PRIVATE\s+KEY-----/g, type: 'private_key', description: 'Private Key Block' },
  // Slack token
  { regex: /xox[baprs]-[A-Za-z0-9-]{10,}/g, type: 'slack_token', description: 'Slack Token' },
  // Stripe key
  { regex: /(?:sk|pk|rk)_(?:test_)?(?:live_)?[A-Za-z0-9]{20,}/g, type: 'stripe_key', description: 'Stripe API Key' },
  // JWT tokens
  { regex: /eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]*/g, type: 'jwt_token', description: 'JWT Token' },
];

const SECRET_MEDIUM_PATTERNS = [
  // Password assignments
  { regex: /(?:password|passwd|pwd)\s*[=:]\s*['"]([^'"]{6,})['"]/gi, type: 'password', description: 'Password Assignment' },
  // Token assignments
  { regex: /(?:token|auth[_-]?token|access[_-]?token)\s*[=:]\s*['"]([^'"]{10,})['"]/gi, type: 'token', description: 'Token Assignment' },
  // Generic high-entropy strings assigned to vars (32+ hex/base64)
  { regex: /(?:secret|key|hash|salt|nonce)\s*[=:]\s*['"]([a-f0-9]{32,}|[A-Za-z0-9+/]{32,}={0,2})['"]/gi, type: 'high_entropy', description: 'High-Entropy String' },
  // Database URLs with credentials
  { regex: /(?:mongodb|postgres|postgresql|mysql|redis|amqp)\+?:\/\/[^:\s]+:[^@\s]+@[\w.-]+/gi, type: 'db_url', description: 'Database URL with Credentials' },
];

const SECRET_LOW_PATTERNS = [
  // Variable names that suggest secrets (but no value)
  { regex: /(?:var|let|const|function)\s+\w*(?:api[_-]?key|secret|password|token|credential)\w*/gi, type: 'naming_hint', description: 'Variable Name Suggests Secret' },
  // process.env access
  { regex: /process\.env\.\w*(?:KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL)\w*/gi, type: 'env_reference', description: 'Environment Variable Reference' },
  // .env file key names
  { regex: /^\s*(?:AWS_|GITHUB_|STRIPE_|SLACK_|DATABASE_|DB_)?(?:SECRET|TOKEN|API_KEY|PASSWORD)\s*=/gim, type: 'dotenv_key', description: '.env File Secret Key' },
];

const SECRET_FILE_EXTENSIONS = new Set([
  '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx',
  '.py', '.rb', '.go', '.rs', '.java', '.kt',
  '.c', '.cpp', '.h', '.hpp', '.cs', '.php',
  '.sh', '.bash', '.zsh',
  '.vue', '.svelte',
  '.env', '.env.local', '.env.production', '.env.development',
  '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
  '.json',
  '.pem', '.key', '.crt', '.p12', '.pfx',
]);

const SECRET_IGNORED_DIRS = ['.git', 'node_modules', 'dist', 'build', '.next', 'vendor', '__pycache__', '.cache', 'coverage'];

export async function detectSecrets(root, maxDepth = 4, depth = 0, gitignore = [], maxFileSize = DEFAULT_MAX_FILE_SIZE) {
  const findings = [];
  const ignored = gitignore.length > 0 ? gitignore : SECRET_IGNORED_DIRS;

  async function scan(dir, d) {
    if (d > maxDepth) return;
    let entries;
    try { entries = await readdir(dir, { withFileTypes: true }); } catch { return; }
    for (const entry of entries) {
      if (ignored.includes(entry.name)) continue;
      const fullPath = join(dir, entry.name);
      if (entry.isDirectory()) {
        await scan(fullPath, d + 1);
      } else {
        const ext = extname(entry.name);
        const lowerName = entry.name.toLowerCase();
        const isEnvFile = lowerName.startsWith('.env');
        if (!SECRET_FILE_EXTENSIONS.has(ext) && !isEnvFile) continue;
        let st;
        try { st = await stat(fullPath); } catch { continue; }
        if (stat.size > maxFileSize || stat.size === 0) continue;
        let content;
        try { content = await readFile(fullPath, 'utf-8'); } catch { continue; }
        const lines = content.split('\n');
        const allPatterns = [
          ...SECRET_HIGH_PATTERNS.map(p => ({ ...p, risk: 'high' })),
          ...SECRET_MEDIUM_PATTERNS.map(p => ({ ...p, risk: 'medium' })),
          ...SECRET_LOW_PATTERNS.map(p => ({ ...p, risk: 'low' })),
        ];
        for (const pattern of allPatterns) {
          for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            pattern.regex.lastIndex = 0;
            const match = pattern.regex.exec(line);
            if (match) {
              findings.push({
                file: fullPath.replace(root, '.').replace(/^\.\//, ''),
                line: i + 1,
                type: pattern.type,
                risk: pattern.risk,
                description: pattern.description,
                snippet: line.trim().slice(0, 120),
              });
            }
          }
        }
      }
    }
  }

  await scan(root, depth);
  // Deduplicate by file+line+type
  const seen = new Set();
  const deduped = findings.filter(f => {
    const key = `${f.file}:${f.line}:${f.type}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  deduped.sort((a, b) => {
    const riskOrder = { high: 0, medium: 1, low: 2 };
    if (riskOrder[a.risk] !== riskOrder[b.risk]) return riskOrder[a.risk] - riskOrder[b.risk];
    return a.file.localeCompare(b.file);
  });
  return deduped;
}

export function formatSecretReport(findings) {
  if (findings.length === 0) {
    return '### Security Scan\n\n✅ No potential secrets detected.';
  }
  const counts = { high: 0, medium: 0, low: 0 };
  for (const f of findings) counts[f.risk]++;
  const emoji = { high: '🔴', medium: '🟡', low: '🔵' };
  const lines = [
    '### Security Scan',
    '',
    `Found **${findings.length}** potential secret(s): ${emoji.high} ${counts.high} high · ${emoji.medium} ${counts.medium} medium · ${emoji.low} ${counts.low} low`,
    '',
  ];
  for (const f of findings) {
    lines.push(`- ${emoji[f.risk]} **[${f.risk.toUpperCase()}]** ${f.description}`);
    lines.push(`  \`${f.file}:${f.line}\` — \`${f.snippet}\``);
  }
  if (counts.high > 0) {
    lines.push('');
    lines.push('> ⚠️ **Action required:** High-risk secrets detected. Rotate keys immediately.');
  }
  return lines.join('\n');
}

// --- F33: Documentation Readability Analysis ---

export function analyzeDocReadability(content) {
  if (!content || content.trim().length === 0) {
    return {
      score: 0,
      grade: 'F',
      metrics: {},
      issues: ['Empty content'],
      suggestions: ['Add content to this document'],
    };
  }

  const lines = content.split('\n');
  const totalLines = lines.length;
  const nonEmptyLines = lines.filter(l => l.trim().length > 0);

  // --- Heading analysis ---
  const headings = lines
    .map((l, i) => ({ text: l, level: l.match(/^^(#{1,6})\s/)?.[1]?.length || 0, line: i + 1 }))
    .filter(h => h.level > 0);
  const headingDepths = headings.map(h => h.level);
  const maxDepth = headingDepths.length > 0 ? Math.max(...headingDepths) : 0;
  const headingCount = headings.length;
  const headingDensity = totalLines > 0 ? headingCount / totalLines : 0;

  // Check heading hierarchy (should not skip levels, e.g., H1 -> H3)
  let hierarchyIssues = 0;
  for (let i = 1; i < headings.length; i++) {
    const prev = headings[i - 1].level;
    const curr = headings[i].level;
    if (curr > prev + 1) hierarchyIssues++;
  }

  // --- Paragraph analysis ---
  const paragraphs = content.split(/\n\s*\n/).filter(p => p.trim().length > 0 && !p.trim().startsWith('#'));
  const paragraphCount = paragraphs.length;
  const paragraphLengths = paragraphs.map(p => p.split(/\s+/).filter(Boolean).length);
  const avgParagraphLength = paragraphLengths.length > 0
    ? Math.round(paragraphLengths.reduce((a, b) => a + b, 0) / paragraphLengths.length)
    : 0;
  const longestParagraph = paragraphLengths.length > 0 ? Math.max(...paragraphLengths) : 0;

  // --- Sentence analysis (within paragraphs) ---
  const sentences = content
    .replace(/```[\s\S]*?```/g, ' ') // Remove code blocks
    .replace(/`[^`]+`/g, ' ') // Remove inline code
    .split(/[.!?]+\s+/)
    .filter(s => s.split(/\s+/).filter(Boolean).length >= 3);
  const sentenceCount = sentences.length;
  const sentenceLengths = sentences.map(s => s.split(/\s+/).filter(Boolean).length);
  const avgSentenceLength = sentenceLengths.length > 0
    ? Math.round(sentenceLengths.reduce((a, b) => a + b, 0) / sentenceLengths.length)
    : 0;

  // --- Code block analysis ---
  const codeBlocks = content.match(/```[\s\S]*?```/g) || [];
  const codeBlockCount = codeBlocks.length;
  const codeBlockLines = codeBlocks.reduce((sum, block) => sum + block.split('\n').length - 2, 0);
  const codeRatio = totalLines > 0 ? codeBlockLines / totalLines : 0;

  // --- Link analysis ---
  const mdLinks = content.match(/\[[^\]]+\]\([^)]+\)/g) || [];
  const linkCount = mdLinks.length;
  const linkDensity = nonEmptyLines.length > 0 ? linkCount / nonEmptyLines.length : 0;

  // --- List analysis ---
  const listItems = lines.filter(l => /^\s*[-*+]\s|^\d+\.\s/.test(l));
  const listCount = listItems.length;

  // --- Word count ---
  const words = content.replace(/```[\s\S]*?```/g, ' ').split(/\s+/).filter(Boolean);
  const wordCount = words.length;

  // --- Scoring (0-100) ---
  let score = 100;
  const issues = [];
  const suggestions = [];

  // Penalty: paragraphs too long (>150 words avg)
  if (avgParagraphLength > 150) {
    score -= 10;
    issues.push(`Average paragraph length is ${avgParagraphLength} words (recommended: <150)`);
    suggestions.push('Break long paragraphs into shorter ones (3-5 sentences each)');
  }
  // Penalty: sentences too long (>25 words avg)
  if (avgSentenceLength > 25) {
    score -= 10;
    issues.push(`Average sentence length is ${avgSentenceLength} words (recommended: <25)`);
    suggestions.push('Use shorter sentences for clarity');
  }
  // Penalty: heading hierarchy issues
  if (hierarchyIssues > 0) {
    score -= hierarchyIssues * 5;
    issues.push(`${hierarchyIssues} heading hierarchy issue(s) detected (skipped levels)`);
    suggestions.push('Don\'t skip heading levels (e.g., H1 → H3)');
  }
  // Penalty: no headings for long docs
  if (wordCount > 200 && headingCount === 0) {
    score -= 15;
    issues.push('Long document with no headings');
    suggestions.push('Add headings to break up content and improve navigation');
  }
  // Penalty: too much code (>50% of lines)
  if (codeRatio > 0.5) {
    score -= 10;
    issues.push(`Code blocks are ${Math.round(codeRatio * 100)}% of document (recommended: <50%)`);
    suggestions.push('Add more explanatory text between code blocks');
  }
  // Penalty: no links in long docs
  if (wordCount > 300 && linkCount === 0) {
    score -= 5;
    issues.push('Long document with no links');
    suggestions.push('Add links to related resources for context');
  }
  // Penalty: heading too dense or too sparse
  if (wordCount > 100 && headingDensity < 0.02) {
    score -= 5;
    issues.push('Low heading density — hard to scan');
    suggestions.push('Add more section headings for readability');
  }
  // Penalty: very long single paragraph
  if (longestParagraph > 200) {
    score -= 5;
    issues.push(`Longest paragraph is ${longestParagraph} words`);
    suggestions.push('Split paragraphs longer than 200 words');
  }

  score = Math.max(0, Math.min(100, score));

  // Grade
  let grade;
  if (score >= 90) grade = 'A';
  else if (score >= 80) grade = 'B';
  else if (score >= 70) grade = 'C';
  else if (score >= 60) grade = 'D';
  else grade = 'F';

  return {
    score,
    grade,
    metrics: {
      wordCount,
      headingCount,
      headingDensity: Number(headingDensity.toFixed(3)),
      maxHeadingDepth: maxDepth,
      hierarchyIssues,
      paragraphCount,
      avgParagraphLength,
      longestParagraph,
      sentenceCount,
      avgSentenceLength,
      codeBlockCount,
      codeBlockLines,
      codeRatio: Number(codeRatio.toFixed(3)),
      linkCount,
      linkDensity: Number(linkDensity.toFixed(3)),
      listCount,
    },
    issues,
    suggestions,
  };
}

export function formatReadabilityReport(analysis) {
  const lines = [
    '### Documentation Readability',
    '',
    `**Score: ${analysis.score}/100 (Grade: ${analysis.grade})**`,
    '',
    '| Metric | Value |',
    '|--------|-------|',
    `| Words | ${analysis.metrics.wordCount} |`,
    `| Headings | ${analysis.metrics.headingCount} (depth: H1-H${analysis.metrics.maxHeadingDepth}) |`,
    `| Paragraphs | ${analysis.metrics.paragraphCount} (avg ${analysis.metrics.avgParagraphLength} words) |`,
    `| Sentences | ${analysis.metrics.sentenceCount} (avg ${analysis.metrics.avgSentenceLength} words) |`,
    `| Code Blocks | ${analysis.metrics.codeBlockCount} (${Math.round(analysis.metrics.codeRatio * 100)}% of lines) |`,
    `| Links | ${analysis.metrics.linkCount} |`,
    `| List Items | ${analysis.metrics.listCount} |`,
  ];

  if (analysis.metrics.hierarchyIssues > 0) {
    lines.push(``, `⚠️ ${analysis.metrics.hierarchyIssues} heading hierarchy issue(s)`);
  }

  if (analysis.issues.length > 0) {
    lines.push('', '**Issues:**');
    for (const issue of analysis.issues) {
      lines.push(`- ${issue}`);
    }
  }

  if (analysis.suggestions.length > 0) {
    lines.push('', '**Suggestions:**');
    for (const s of analysis.suggestions) {
      lines.push(`- 💡 ${s}`);
    }
  }

  return lines.join('\n');
}

export function detectDeadCode(importData, apiSurface) {
  /**
   * Detect exported symbols that are never imported/referenced elsewhere.
   * Returns { dead: [{file, symbol, type}], total, used, unused }.
   */
  const dead = [];
  const allRefs = new Set();

  // Collect all imported names from import data
  for (const [file, imports] of Object.entries(importData || {})) {
    if (!Array.isArray(imports)) continue;
    for (const imp of imports) {
      if (imp.name) allRefs.add(imp.name);
      if (imp.imported) allRefs.add(imp.imported);
      // Handle destructured imports: { a, b, c }
      if (typeof imp.imported === 'string' && imp.imported.includes(',')) {
        for (const part of imp.imported.split(',')) {
          const clean = part.trim().replace(/[{}]/g, '').trim();
          if (clean) allRefs.add(clean);
        }
      }
    }
  }

  // Check each exported symbol against references
  for (const [file, exports] of Object.entries(apiSurface || {})) {
    if (!Array.isArray(exports)) continue;
    for (const exp of exports) {
      if (!exp) continue; // skip null/undefined entries
      const name = typeof exp === 'string' ? exp : (exp.name || exp.export || '');
      if (!name) continue;
      // A symbol is "used" if it appears in any import OR is a common entry point
      const isUsed = allRefs.has(name);
      if (!isUsed) {
        dead.push({
          file,
          symbol: name,
          type: typeof exp === 'object' ? (exp.type || 'export') : 'export'
        });
      }
    }
  }

  const total = Object.values(apiSurface || {}).reduce((sum, arr) => sum + (Array.isArray(arr) ? arr.length : 0), 0);
  const used = total - dead.length;

  return { dead, total, used, unused: dead.length };
}

export function formatDeadCodeReport(result) {
  if (!result || !result.dead || result.dead.length === 0) {
    return '✅ No dead code detected — all exports are referenced.';
  }

  const lines = [
    `🔍 Dead Code Analysis: ${result.unused}/${result.total} exports unused`,
    ''
  ];

  // Group by file
  const byFile = {};
  for (const d of result.dead) {
    if (!byFile[d.file]) byFile[d.file] = [];
    byFile[d.file].push(d.symbol);
  }

  for (const [file, syms] of Object.entries(byFile)) {
    lines.push(`**${file}** (${syms.length} unused):`);
    for (const s of syms.sort()) {
      lines.push(`  - \`${s}\``);
    }
    lines.push('');
  }

  lines.push(`**Summary:** ${result.used} used / ${result.unused} unused / ${result.total} total`);
  return lines.join('\n');
}

/**
 * F35: Detect test files and infer testing framework.
 * Scans project for test files and reports framework, count, and coverage ratio.
 */
export async function detectTestFiles(root, maxDepth = 3, depth = 0, gitignore = [], maxFileSize = DEFAULT_MAX_FILE_SIZE) {
  root = resolvePath(root);
  const entries = await readdir(root, { withFileTypes: true }).catch(() => []);
  const testFiles = [];
  const frameworkPatterns = {
    jest: [/\.test\.[jt]sx?$/, /\.spec\.[jt]sx?$/, /__tests__\//],
    pytest: [/test_.*\.py$/, /_test\.py$/, /conftest\.py$/],
    vitest: [/\.test\.[jt]s$/, /\.spec\.[jt]s$/],
    mocha: [/\.test\.js$/, /\.spec\.js$/, /test\//],
    go_test: [/_test\.go$/],
    rust_test: [/tests?\.rs$/, /#\[test\]/],
    dotnet_test: [/Tests?\.cs$/],
  };

  for (const entry of entries) {
    if (depth >= maxDepth) continue;
    const fullPath = join(root, entry.name);
    if (isIgnored(fullPath, gitignore)) continue;

    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === '.git' || entry.name === 'dist' || entry.name === 'build' || entry.name === '.next') continue;
      const sub = await detectTestFiles(fullPath, maxDepth, depth + 1, gitignore, maxFileSize);
      testFiles.push(...sub.files);
    } else if (entry.isFile()) {
      let st;
      try { st = await stat(fullPath); } catch { continue; }
      if (!st || st.size > maxFileSize) continue;
      const isTest = /^(test_|.*[_.]test[._]|.*[_.]spec[._]|.*_test\.|conftest\.|.*Tests?\.[cs])/.test(entry.name) ||
                     /(^|[\/])__tests__[\/]/.test(fullPath) ||
                     /_test\.go$/.test(entry.name);
      if (isTest) {
        let framework = 'unknown';
        for (const [fw, patterns] of Object.entries(frameworkPatterns)) {
          if (patterns.some(p => p.test(entry.name) || p.test(fullPath))) {
            framework = fw;
            break;
          }
        }
        testFiles.push({ path: fullPath, name: entry.name, framework });
      }
    }
  }
  return { files: testFiles };
}

export function formatTestFilesReport(result) {
  if (!result || !result.files || result.files.length === 0) {
    return '⚠️ No test files detected in this project.';
  }
  const byFramework = {};
  for (const f of result.files) {
    byFramework[f.framework] = (byFramework[f.framework] || 0) + 1;
  }
  const lines = [
    `🧪 Test Files: ${result.files.length} found`,
    ''
  ];
  for (const [fw, count] of Object.entries(byFramework).sort((a, b) => b[1] - a[1])) {
    lines.push(`- **${fw}**: ${count} file${count > 1 ? 's' : ''}`);
  }
  lines.push('', 'Test files:');
  for (const f of result.files.slice(0, 20)) {
    lines.push(`  - \`${f.name}\` (${f.framework})`);
  }
  if (result.files.length > 20) {
    lines.push(`  - ... and ${result.files.length - 20} more`);
  }
  return lines.join('\n');
}

/**
 * F36: Analyze git hotspots — files that change most frequently.
 * Uses git log to find the most frequently modified files.
 */
export async function analyzeGitHotspots(root, maxCommits = 50) {
  root = resolvePath(root);
  const { execSync } = await import('child_process');
  let log;
  try {
    log = execSync(
      `git -C "${root}" log --name-only --pretty=format: --max-count=${maxCommits}`,
      { encoding: 'utf8', timeout: 5000, stdio: ['pipe', 'pipe', 'pipe'] }
    );
  } catch {
    return { hotspots: [], totalCommits: 0, error: 'git not available or not a git repo' };
  }

  const counts = {};
  let totalCommits = 0;
  for (const line of log.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed) { continue; }
    counts[trimmed] = (counts[trimmed] || 0) + 1;
    totalCommits++;
  }

  const hotspots = Object.entries(counts)
    .map(([file, changes]) => ({ file, changes, ratio: +(changes / Math.max(totalCommits, 1)).toFixed(2) }))
    .sort((a, b) => b.changes - a.changes)
    .slice(0, 20);

  return { hotspots, totalCommits, totalFiles: Object.keys(counts).length };
}

export function formatGitHotspotsReport(result) {
  if (!result || result.error) {
    return `⚠️ Git hotspot analysis unavailable: ${result?.error || 'unknown error'}`;
  }
  if (!result.hotspots || result.hotspots.length === 0) {
    return 'ℹ️ No git history found for hotspot analysis.';
  }
  const lines = [
    `🔥 Git Hotspots: Top ${result.hotspots.length} most changed files`,
    `   (${result.totalCommits} file changes across ${result.totalFiles} unique files)`,
    ''
  ];
  const maxChanges = result.hotspots[0].changes;
  for (const h of result.hotspots) {
    const bar = '█'.repeat(Math.max(1, Math.round((h.changes / maxChanges) * 20)));
    lines.push(`  ${bar} ${h.changes}× ${h.file}`);
  }
  return lines.join('\n');
}

// ─── F39: File Size Analysis ──────────────────────────────────────────

/**
 * Analyze file size distribution across the project.
 * Finds outlier files, computes percentiles, and groups by extension.
 *
 * @param {string} root — Project root path
 * @param {{ maxDepth?: number, gitignore?: string[], maxFileSize?: number }} opts
 * @returns {Promise<{
 *   totalFiles: number,
 *   totalSizeKB: number,
 *   avgSizeKB: number,
 *   medianSizeKB: number,
 *   p90SizeKB: number,
 *   p95SizeKB: number,
 *   p99SizeKB: number,
 *   largest: Array<{ file: string, sizeKB: number }>,
 *   byExtension: Array<{ ext: string, count: number, totalKB: number, avgKB: number }>,
 *   outliers: Array<{ file: string, sizeKB: number, zScore: number }>
 * }>}
 */
export async function analyzeFileSizes(root, opts = {}) {
  const { maxDepth = 4, gitignore = [], maxFileSize = 2 * 1024 * 1024 } = opts;
  const { readdir, stat } = await import('node:fs/promises');
  const { join, relative, extname } = await import('node:path');

  const files = [];

  async function walk(dir, depth) {
    if (depth > maxDepth) return;
    let entries;
    try { entries = await readdir(dir, { withFileTypes: true }); }
    catch { return; }
    for (const entry of entries) {
      if (entry.name.startsWith('.') || entry.name === 'node_modules') continue;
      const fullPath = join(dir, entry.name);
      const relPath = relative(root, fullPath);
      if (isIgnored(relPath, gitignore)) continue;
      if (entry.isDirectory()) {
        await walk(fullPath, depth + 1);
      } else if (entry.isFile()) {
        try {
          const s = await stat(fullPath);
          if (s.size <= maxFileSize) {
            files.push({ file: relPath, sizeKB: +(s.size / 1024).toFixed(2), ext: extname(entry.name) || '(no ext)' });
          }
        } catch { /* skip */ }
      }
    }
  }

  await walk(root, 0);

  if (files.length === 0) {
    return { totalFiles: 0, totalSizeKB: 0, avgSizeKB: 0, medianSizeKB: 0, p90SizeKB: 0, p95SizeKB: 0, p99SizeKB: 0, largest: [], byExtension: [], outliers: [] };
  }

  const sizes = files.map(f => f.sizeKB).sort((a, b) => a - b);
  const totalSizeKB = +sizes.reduce((a, b) => a + b, 0).toFixed(2);
  const avgSizeKB = +(totalSizeKB / files.length).toFixed(2);

  const percentile = (arr, p) => {
    const idx = Math.min(Math.floor((p / 100) * arr.length), arr.length - 1);
    return +arr[idx].toFixed(2);
  };

  const medianSizeKB = percentile(sizes, 50);
  const p90SizeKB = percentile(sizes, 90);
  const p95SizeKB = percentile(sizes, 95);
  const p99SizeKB = percentile(sizes, 99);

  // Std deviation for z-score
  const variance = sizes.reduce((sum, s) => sum + (s - avgSizeKB) ** 2, 0) / files.length;
  const stdDev = Math.sqrt(variance) || 1;

  const outliers = files
    .map(f => ({ ...f, zScore: +((f.sizeKB - avgSizeKB) / stdDev).toFixed(2) }))
    .filter(f => f.zScore > 2)
    .sort((a, b) => b.sizeKB - a.sizeKB)
    .slice(0, 10);

  const largest = [...files].sort((a, b) => b.sizeKB - a.sizeKB).slice(0, 10).map(f => ({ file: f.file, sizeKB: f.sizeKB }));

  // Group by extension
  const extMap = new Map();
  for (const f of files) {
    if (!extMap.has(f.ext)) extMap.set(f.ext, { count: 0, totalKB: 0 });
    const e = extMap.get(f.ext);
    e.count++;
    e.totalKB += f.sizeKB;
  }
  const byExtension = [...extMap.entries()]
    .map(([ext, v]) => ({ ext, count: v.count, totalKB: +v.totalKB.toFixed(2), avgKB: +(v.totalKB / v.count).toFixed(2) }))
    .sort((a, b) => b.totalKB - a.totalKB);

  return { totalFiles: files.length, totalSizeKB, avgSizeKB, medianSizeKB, p90SizeKB, p95SizeKB, p99SizeKB, largest, byExtension, outliers };
}

/**
 * Format file size analysis as a human-readable report.
 */
export function formatFileSizeReport(analysis) {
  if (analysis.totalFiles === 0) return 'No files found for size analysis.';
  const lines = [
    '## File Size Analysis',
    '',
    `| Metric | Value |`,
    `|--------|-------|`,
    `| Total files | ${analysis.totalFiles} |`,
    `| Total size | ${analysis.totalSizeKB.toFixed(1)} KB (${(analysis.totalSizeKB / 1024).toFixed(1)} MB) |`,
    `| Average | ${analysis.avgSizeKB} KB |`,
    `| Median | ${analysis.medianSizeKB} KB |`,
    `| P90 | ${analysis.p90SizeKB} KB |`,
    `| P95 | ${analysis.p95SizeKB} KB |`,
    `| P99 | ${analysis.p99SizeKB} KB |`,
    '',
    '### Largest Files',
  ];
  for (const f of analysis.largest) {
    lines.push(`- ${f.sizeKB} KB — \`${f.file}\``);
  }
  if (analysis.outliers.length > 0) {
    lines.push('', '### Size Outliers (z-score > 2)');
    for (const o of analysis.outliers) {
      lines.push(`- z=${o.zScore} — ${o.sizeKB} KB — \`${o.file}\``);
    }
  }
  lines.push('', '### By Extension');
  lines.push('| Ext | Count | Total KB | Avg KB |');
  lines.push('|-----|-------|----------|--------|');
  for (const e of analysis.byExtension.slice(0, 10)) {
    lines.push(`| ${e.ext} | ${e.count} | ${e.totalKB} | ${e.avgKB} |`);
  }
  return lines.join('\n');
}

// ─── F40: Naming Convention Detection ─────────────────────────────────

const NAMING_PATTERNS = {
  CONST_CASE: /^[A-Z][A-Z0-9_]+$/,
  PascalCase: /^(?![A-Z0-9_]+$)[A-Z][a-zA-Z0-9]*$/,
  camelCase: /^[a-z][a-zA-Z0-9]*$/,
  snake_case: /^[a-z][a-z0-9_]+$/,
  kebab_case: /^[a-z][a-z0-9-]+$/,
};

/**
 * Detect naming conventions for files in the project.
 * Reports which convention is dominant and any inconsistencies.
 *
 * @param {string} root — Project root path
 * @param {{ maxDepth?: number, gitignore?: string[] }} opts
 * @returns {Promise<{
 *   totalFiles: number,
 *   conventions: Array<{ convention: string, count: number, percentage: number, examples: string[] }>,
 *   dominant: string,
 *   inconsistencies: Array<{ file: string, convention: string }>,
 *   byDirectory: Array<{ dir: string, convention: string, count: number }>
 * }>}
 */
export async function detectNamingConventions(root, opts = {}) {
  const { maxDepth = 4, gitignore = [] } = opts;
  const { readdir } = await import('node:fs/promises');
  const { join, relative, dirname, basename } = await import('node:path');

  const files = [];

  async function walk(dir, depth) {
    if (depth > maxDepth) return;
    let entries;
    try { entries = await readdir(dir, { withFileTypes: true }); }
    catch { return; }
    for (const entry of entries) {
      if (entry.name.startsWith('.') || entry.name === 'node_modules') continue;
      const fullPath = join(dir, entry.name);
      const relPath = relative(root, fullPath);
      if (isIgnored(relPath, gitignore)) continue;
      if (entry.isDirectory()) {
        await walk(fullPath, depth + 1);
      } else if (entry.isFile()) {
        // Strip extension(s) for convention detection
        const name = basename(entry.name).replace(/\.[^.]+$/, '');
        if (name.length === 0) continue;
        const matched = Object.entries(NAMING_PATTERNS).find(([, re]) => re.test(name));
        const convention = matched ? matched[0] : 'mixed/other';
        files.push({ file: relPath, dir: dirname(relPath), name, convention });
      }
    }
  }

  await walk(root, 0);

  if (files.length === 0) {
    return { totalFiles: 0, conventions: [], dominant: 'none', inconsistencies: [], byDirectory: [] };
  }

  // Count conventions
  const convMap = new Map();
  for (const f of files) {
    if (!convMap.has(f.convention)) convMap.set(f.convention, { count: 0, examples: [] });
    const c = convMap.get(f.convention);
    c.count++;
    if (c.examples.length < 3) c.examples.push(f.file);
  }

  const conventions = [...convMap.entries()]
    .map(([conv, v]) => ({ convention: conv, count: v.count, percentage: +((v.count / files.length) * 100).toFixed(1), examples: v.examples }))
    .sort((a, b) => b.count - a.count);

  const dominant = conventions[0].convention;

  // Find inconsistencies (files not following dominant convention)
  const inconsistencies = files
    .filter(f => f.convention !== dominant)
    .map(f => ({ file: f.file, convention: f.convention }))
    .sort((a, b) => a.file.localeCompare(b.file))
    .slice(0, 20);

  // By directory
  const dirMap = new Map();
  for (const f of files) {
    if (!dirMap.has(f.dir)) dirMap.set(f.dir, new Map());
    const dm = dirMap.get(f.dir);
    dm.set(f.convention, (dm.get(f.convention) || 0) + 1);
  }
  const byDirectory = [...dirMap.entries()]
    .map(([dir, convs]) => {
      const sorted = [...convs.entries()].sort((a, b) => b[1] - a[1]);
      return { dir, convention: sorted[0][0], count: sorted[0][1] };
    })
    .sort((a, b) => a.dir.localeCompare(b.dir))
    .slice(0, 15);

  return { totalFiles: files.length, conventions, dominant, inconsistencies, byDirectory };
}

/**
 * Format naming convention analysis as a human-readable report.
 */
export function formatNamingReport(analysis) {
  if (analysis.totalFiles === 0) return 'No files found for naming convention analysis.';
  const lines = [
    '## Naming Convention Analysis',
    '',
    `**Dominant convention:** \`${analysis.dominant}\``,
    '',
    '| Convention | Count | Percentage | Examples |',
    '|-----------|-------|-----------|----------|',
  ];
  for (const c of analysis.conventions) {
    lines.push(`| \`${c.convention}\` | ${c.count} | ${c.percentage}% | ${c.examples.map(e => `\`${e}\``).join(', ')} |`);
  }
  if (analysis.inconsistencies.length > 0) {
    lines.push('', `### Inconsistencies (${analysis.inconsistencies.length} files not following \`${analysis.dominant}\`)`);
    for (const inc of analysis.inconsistencies.slice(0, 10)) {
      lines.push(`- \`${inc.file}\` → \`${inc.convention}\``);
    }
    if (analysis.inconsistencies.length > 10) {
      lines.push(`- _...and ${analysis.inconsistencies.length - 10} more_`);
    }
  }
  return lines.join('\n');
}

export function resolvePath(p) {
  return p.startsWith("/") ? p : join(process.cwd(), p);
}

// ─── F37: Benchmark Analysis ──────────────────────────────────────────

/**
 * Run a function and measure its execution time + memory delta.
 * @returns {{ result: any, durationMs: number, memDeltaKB: number }}
 */
async function measureStage(name, fn) {
  const memBefore = process.memoryUsage().heapUsed;
  const start = performance.now();
  const result = await fn();
  const durationMs = +(performance.now() - start).toFixed(2);
  const memDeltaKB = +((process.memoryUsage().heapUsed - memBefore) / 1024).toFixed(2);
  return { name, result, durationMs, memDeltaKB };
}

/**
 * Benchmark all analysis stages on a given project root.
 * Runs each stage independently, collects timing + memory metrics,
 * and returns a structured report.
 *
 * @param {string} root — Project root path
 * @param {{ maxDepth?: number, maxCommits?: number }} opts
 * @returns {Promise<{
 *   project: string,
 *   timestamp: string,
 *   totalMs: number,
 *   stages: Array<{ name: string, durationMs: number, memDeltaKB: number, error?: string }>,
 *   fileCount: number,
 *   recommendations: string[]
 * }>}
 */
export async function benchmarkAnalysis(root, opts = {}) {
  const { maxDepth = 3, maxCommits = 20 } = opts;
  const stages = [];
  const recommendations = [];

  // Stage 1: detectProject
  stages.push(await measureStage('detectProject', async () => {
    try { return await detectProject(root); }
    catch (e) { return { error: e.message };
    }
  }));

  // Stage 2: parseGitignore
  stages.push(await measureStage('parseGitignore', async () => {
    try { return await parseGitignore(root); }
    catch (e) { return { error: e.message }; }
  }));

  const gitignore = stages[1].result?.patterns || stages[1].result || [];

  // Stage 3: scanLanguages
  stages.push(await measureStage('scanLanguages', async () => {
    try { return await scanLanguages(root, maxDepth, 0, gitignore); }
    catch (e) { return { error: e.message }; }
  }));

  // Stage 4: extractImports
  stages.push(await measureStage('extractImports', async () => {
    try { return await extractImports(root, maxDepth, 0, gitignore); }
    catch (e) { return { error: e.message }; }
  }));

  // Stage 5: extractApiSurface
  stages.push(await measureStage('extractApiSurface', async () => {
    try { return await extractApiSurface(root, maxDepth, 0, gitignore); }
    catch (e) { return { error: e.message }; }
  }));

  // Stage 6: analyzeGitHistory
  stages.push(await measureStage('analyzeGitHistory', async () => {
    try { return await analyzeGitHistory(root, maxCommits); }
    catch (e) { return { error: e.message }; }
  }));

  // Stage 7: detectTestFiles
  stages.push(await measureStage('detectTestFiles', async () => {
    try { return await detectTestFiles(root, maxDepth, 0, gitignore); }
    catch (e) { return { error: e.message }; }
  }));

  // Stage 8: detectSecrets
  stages.push(await measureStage('detectSecrets', async () => {
    try { return await detectSecrets(root, maxDepth, 0, gitignore); }
    catch (e) { return { error: e.message }; }
  }));

  // Compute totals
  const totalMs = stages.reduce((sum, s) => sum + s.durationMs, 0);

  // Count files from language scan
  let fileCount = 0;
  const langResult = stages[2].result;
  if (langResult && !langResult.error && langResult.files) {
    fileCount = langResult.files.length;
  } else if (langResult && typeof langResult === 'object') {
    fileCount = Object.values(langResult).reduce((sum, arr) =>
      sum + (Array.isArray(arr) ? arr.length : 0), 0);
  }

  // Generate recommendations based on timings
  for (const s of stages) {
    if (s.result?.error) {
      recommendations.push(`⚠️ ${s.name} failed: ${s.result.error}`);
    } else if (s.durationMs > 1000) {
      recommendations.push(`🐌 ${s.name} is slow (${s.durationMs}ms) — consider caching or reducing scan depth`);
    }
  }
  if (totalMs > 5000) {
    recommendations.push(`📊 Total analysis takes ${totalMs}ms — consider running stages in parallel`);
  }
  if (recommendations.length === 0) {
    recommendations.push('✅ All stages performing well');
  }

  // Strip actual results from stages (keep only metrics)
  const stageMetrics = stages.map(s => ({
    name: s.name,
    durationMs: s.durationMs,
    memDeltaKB: s.memDeltaKB,
    ...(s.result?.error ? { error: s.result.error } : {}),
  }));

  return {
    project: root,
    timestamp: new Date().toISOString(),
    totalMs: +totalMs.toFixed(2),
    stages: stageMetrics,
    fileCount,
    recommendations,
  };
}

/**
 * Format benchmark results as a human-readable report.
 */
export function formatBenchmarkReport(bench) {
  const lines = [
    '# 🔧 Performance Benchmark Report',
    '',
    `**Project:** ${bench.project}`,
    `**Date:** ${bench.timestamp}`,
    `**Total Time:** ${bench.totalMs}ms`,
    `**Files Scanned:** ${bench.fileCount}`,
    '',
    '## Stage Breakdown',
    '',
    '| Stage | Time (ms) | Memory (KB) | Status |',
    '|-------|-----------|-------------|--------|',
  ];

  for (const s of bench.stages) {
    const status = s.error ? '❌ Error' : '✅ OK';
    lines.push(`| ${s.name} | ${s.durationMs} | ${s.memDeltaKB} | ${status} |`);
  }

  lines.push('', '## Recommendations', '');
  for (const r of bench.recommendations) {
    lines.push(`- ${r}`);
  }

  return lines.join('\n');
}

// ─── F38: Documentation Examples ───────────────────────────────────────

/**
 * Generate example outputs for each file type, using a mock project.
 * Useful for documentation, onboarding, and regression testing.
 *
 * @param {{ includeGitInfo?: boolean }} opts
 * @returns {{ agentsMd: string, cursorRules: string, copilotInstructions: string, claudeMd: string, stats: object }}
 */
export function generateDocExamples(opts = {}) {
  const { includeGitInfo = true } = opts;

  const mockInfo = {
    root: '/example/my-app',
    pkg: {
      name: 'my-app',
      version: '2.1.0',
      description: 'A sample application for documentation examples',
      main: 'src/index.js',
      module: 'src/index.mjs',
    },
    frameworks: ['Express', 'React', 'Jest'],
    monorepo: false,
    entryPoints: ['src/index.js', 'src/server.js'],
    scripts: {
      start: 'node src/server.js',
      dev: 'nodemon src/server.js',
      test: 'jest --coverage',
      build: 'webpack --mode production',
      lint: 'eslint src/',
    },
    deps: {
      express: '^4.18.0',
      react: '^18.2.0',
      jest: '^29.6.0',
      eslint: '^8.45.0',
    },
    configFiles: ['.eslintrc.json', 'jest.config.js', 'webpack.config.js'],
  };

  const mockLangs = new Map([
    ['JavaScript', 45],
    ['TypeScript', 12],
    ['CSS', 8],
    ['HTML', 3],
    ['JSON', 5],
  ]);

  const mockStructure = `my-app/
  src/
    index.js
    server.js
    routes/
      api.js
      auth.js
    components/
      Header.jsx
      Footer.jsx
    utils/
      helpers.js
  test/
    api.test.js
    auth.test.js
  package.json
  webpack.config.js`;

  const mockGitInfo = includeGitInfo ? {
    isRepo: true,
    totalCommits: 342,
    contributors: [
      { name: 'Alice', commits: 180 },
      { name: 'Bob', commits: 120 },
      { name: 'Charlie', commits: 42 },
    ],
    topFilesChanged: [
      { file: 'src/server.js', changes: 45 },
      { file: 'src/routes/api.js', changes: 38 },
      { file: 'package.json', changes: 22 },
    ],
  } : null;

  const agentsMd = generateAgentsMd(mockInfo, mockLangs, mockStructure, mockGitInfo);
  const cursorRules = generateCursorRules(mockInfo, mockLangs, mockStructure);
  const copilotInstructions = generateCopilotInstructions(mockInfo);
  const claudeMd = generateClaudeMd(mockInfo, mockLangs, mockStructure);

  // Collect stats about the generated examples
  const stats = {
    agentsMdLines: agentsMd.split('\n').length,
    cursorRulesLines: cursorRules.split('\n').length,
    copilotInstructionsLines: copilotInstructions.split('\n').length,
    claudeMdLines: claudeMd.split('\n').length,
    totalOutput: agentsMd.length + cursorRules.length + copilotInstructions.length + claudeMd.length,
  };

  return { agentsMd, cursorRules, copilotInstructions, claudeMd, stats };
}

/**
 * Format all documentation examples into a single markdown document.
 */
export function formatDocExamples(examples) {
  const lines = [
    '# 📖 Context-Forge Documentation Examples',
    '',
    'This document shows example outputs for each generated file type',
    'using a mock project (`my-app`).',
    '',
    `**Generated:** ${new Date().toISOString()}`,
    `**Total output:** ${examples.stats.totalOutput} characters`,
    '',
    '---',
    '',
    '## AGENTS.md Example',
    '',
    '```markdown',
    examples.agentsMd,
    '```',
    '',
    '---',
    '',
    '## .cursorrules Example',
    '',
    '```markdown',
    examples.cursorRules,
    '```',
    '',
    '---',
    '',
    '## .github/copilot-instructions.md Example',
    '',
    '```markdown',
    examples.copilotInstructions,
    '```',
    '',
    '---',
    '',
    '## CLAUDE.md Example',
    '',
    '```markdown',
    examples.claudeMd,
    '```',
    '',
    '---',
    '',
    '## Statistics',
    '',
    `| File | Lines |`,
    `|------|-------|`,
    `| AGENTS.md | ${examples.stats.agentsMdLines} |`,
    `| .cursorrules | ${examples.stats.cursorRulesLines} |`,
    `| copilot-instructions | ${examples.stats.copilotInstructionsLines} |`,
    `| CLAUDE.md | ${examples.stats.claudeMdLines} |`,
  ];

  return lines.join('\n');
}

/**
 * F42: Detect API routes — scan for REST endpoints in Express/Fastify/Koa/Flask/FastAPI/Django.
 *
 * @param {string} root - Project root directory
 * @param {object} opts - { maxDepth=3, maxFileSize, gitignore=[] }
 * @returns {Promise<{routes: Array, frameworks: string[], count: number, byMethod: object}>}
 */
export async function detectApiRoutes(root, opts = {}) {
  const maxDepth = opts.maxDepth ?? 3;
  const maxFileSize = opts.maxFileSize ?? DEFAULT_MAX_FILE_SIZE;
  const gitignore = opts.gitignore ?? [];
  const routes = [];
  const frameworks = new Set();

  const ROUTE_PATTERNS = {
    // Express/Fastify/Koa: app.METHOD(path), router.METHOD(path)
    javascript: [
      // Express/Fastify/Koa: app.METHOD(path), router.METHOD(path)
      { regex: /(?:app|fastify|server|router)\s*\.\s*(get|post|put|delete|patch|all|head|options)\s*\(\s*['"`]([^'"`]+)['"`]/gi, framework: 'express' },
    ],
    typescript: [
      { regex: /(?:app|fastify|server|router)\s*\.\s*(get|post|put|delete|patch|all|head|options)\s*[<(]\s*['"`]([^'"`]+)['"`]/gi, framework: 'express' },
    ],
    python: [
      // Flask/FastAPI: @app.route('/path') or @app.get('/path')
      { regex: /@(?:app|router|api)\s*\.\s*(?:route\()?['"]([^'"]*)['"](?:,\s*methods\s*=\s*\[([^\]]+)\])?\)?/g, framework: 'flask' },
      // FastAPI: @app.get('/path'), @router.post('/path')
      { regex: /@(?:app|router|api)\s*\.\s*(get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"]\s*\)/g, framework: 'fastapi' },
      // Django: path('url/', view) — allow empty paths
      { regex: /path\s*\(\s*['"]([^'"]*)['"]\s*,/g, framework: 'django' },
    ],
    go: [
      { regex: /(?:mux|router|r|s)\s*\.\s*(HandleFunc|Get|Post|Put|Delete|Patch)\s*\(\s*['"]([^'"]+)['"]\s*,/g, framework: 'net/http' },
      { regex: /(?:e|echo|g)\s*\.\s*(GET|POST|PUT|DELETE|PATCH)\s*\(\s*['"]([^'"]+)['"]\s*,/g, framework: 'echo' },
    ],
  };

  const FILE_EXTENSIONS = {
    '.js': 'javascript',
    '.mjs': 'javascript',
    '.cjs': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.py': 'python',
    '.go': 'go',
  };

  async function scanDir(dir, depth) {
    if (depth > maxDepth) return;
    try {
      const entries = await readdir(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = join(dir, entry.name);
        const relPath = relative(root, fullPath);
        if (isIgnored(relPath, gitignore)) continue;

        if (entry.isDirectory() && !IGNORE_DIRS.has(entry.name) && !entry.name.startsWith('.')) {
          await scanDir(fullPath, depth + 1);
        } else if (entry.isFile()) {
          const ext = extname(entry.name);
          const lang = FILE_EXTENSIONS[ext];
          if (!lang) continue;

          const fileStat = await stat(fullPath);
          if (fileStat.size > maxFileSize) continue;

          const content = await readFile(fullPath, 'utf8');
          const lines = content.split('\n');
          const patternSet = ROUTE_PATTERNS[lang] || [];

          for (const { regex, framework } of patternSet) {
            const re = new RegExp(regex.source, regex.flags);
            let match;
            while ((match = re.exec(content)) !== null) {
              let method, path;
              if (framework === 'flask' && match[1] && !match[2]) {
                // @app.route('/path') without methods
                method = 'GET';
                path = match[1];
              } else if (framework === 'flask' && match[2]) {
                // @app.route('/path', methods=['GET','POST'])
                method = match[2].replace(/[\[\]'"\s]/g, '').split(',')[0] || 'GET';
                path = match[1];
              } else if (framework === 'django') {
                method = 'ANY';
                path = match[1];
              } else if (framework === 'fastapi') {
                method = (match[1] || 'GET').toUpperCase();
                path = match[2];
              } else if (lang === 'go' && framework === 'net/http') {
                method = match[1].includes('Get') ? 'GET' : match[1].includes('Post') ? 'POST' : match[1].includes('Put') ? 'PUT' : match[1].includes('Delete') ? 'DELETE' : 'ANY';
                path = match[2];
              } else {
                method = (match[1] || 'GET').toUpperCase();
                path = match[2] || match[1];
              }

              // Find line number
              const offset = match.index;
              const lineNum = content.substring(0, offset).split('\n').length;

              routes.push({
                file: relPath,
                line: lineNum,
                method: method.toUpperCase(),
                path,
                framework,
              });
              frameworks.add(framework);
            }
          }
        }
      }
    } catch { /* ignore */ }
  }

  await scanDir(root, 0);

  // Build byMethod summary
  const byMethod = {};
  for (const r of routes) {
    byMethod[r.method] = (byMethod[r.method] || 0) + 1;
  }

  return {
    routes: routes.sort((a, b) => a.file.localeCompare(b.file) || a.line - b.line),
    frameworks: [...frameworks].sort(),
    count: routes.length,
    byMethod,
  };
}

/**
 * F43: Format API routes report as markdown.
 */
export function formatApiRoutesReport(result) {
  if (!result || !result.routes || result.routes.length === 0) {
    return '## 🔌 API Routes\n\nNo API routes detected.\n';
  }

  const lines = [
    '## 🔌 API Routes',
    '',
    `**Detected frameworks:** ${result.frameworks.join(', ')}`,
    `**Total routes:** ${result.count}`,
    '',
    '### By Method',
    '',
    '| Method | Count |',
    '|--------|-------|',
  ];

  for (const [method, count] of Object.entries(result.byMethod).sort((a, b) => b[1] - a[1])) {
    lines.push(`| ${method} | ${count} |`);
  }

  lines.push('', '### Routes', '', '| Method | Path | File:Line | Framework |', '|--------|------|-----------|-----------|');
  for (const r of result.routes) {
    lines.push(`| ${r.method} | \`${r.path}\` | ${r.file}:${r.line} | ${r.framework} |`);
  }

  return lines.join('\n');
}

/**
 * F44: Analyze import health — unused deps, most-imported, diversity score, fan-in.
 *
 * @param {object} info - Project info (from detectProject)
 * @param {object} importData - Import data (from extractImports)
 * @returns {{unusedDeps: string[], mostImported: Array, totalImports: number, uniqueImports: number, diversityScore: number, avgImportsPerFile: number}}
 */
export function analyzeImportHealth(info, importData) {
  const allImports = importData.allImports || [];
  const importsMap = importData.imports || new Map();

  // Get declared dependencies from package.json
  const declared = new Set();
  const deps = info.pkg?.dependencies || {};
  const devDeps = info.pkg?.devDependencies || {};
  for (const k of Object.keys(deps)) declared.add(k);
  for (const k of Object.keys(devDeps)) declared.add(k);

  // Count import frequency
  const importCounts = {};
  for (const imp of allImports) {
    // Normalize: strip scoped package subpaths
    const base = imp.startsWith('@') ? imp.split('/').slice(0, 2).join('/') : imp.split('/')[0];
    importCounts[base] = (importCounts[base] || 0) + 1;
  }

  // Find unused deps (declared but never imported)
  const usedPackages = new Set(Object.keys(importCounts));
  const unusedDeps = [...declared].filter(d => !usedPackages.has(d) && !d.startsWith('@types/'));

  // Most imported packages (sorted by count)
  const mostImported = Object.entries(importCounts)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);

  // Count files with imports
  const filesWithImports = importsMap instanceof Map ? importsMap.size : Object.keys(importsMap).length;

  // Diversity score: unique packages / total imports (0-1, higher = more diverse)
  const uniqueImports = Object.keys(importCounts).length;
  const totalImports = allImports.length;
  const diversityScore = totalImports > 0 ? Math.round((uniqueImports / totalImports) * 100) / 100 : 0;

  // Average imports per file
  const avgImportsPerFile = filesWithImports > 0 ? Math.round((totalImports / filesWithImports) * 100) / 100 : 0;

  return {
    unusedDeps,
    mostImported,
    totalImports,
    uniqueImports,
    diversityScore,
    avgImportsPerFile,
    filesWithImports,
    declaredCount: declared.size,
  };
}

/**
 * F45: Format import health report.
 */
export function formatImportHealthReport(result) {
  if (!result) return '## 📦 Import Health\n\nNo import data available.\n';

  const lines = [
    '## 📦 Import Health',
    '',
    `**Total imports:** ${result.totalImports}`,
    `**Unique packages:** ${result.uniqueImports}`,
    `**Diversity score:** ${result.diversityScore} (0-1, higher = more diverse)`,
    `**Avg imports/file:** ${result.avgImportsPerFile}`,
    '',
  ];

  if (result.unusedDeps.length > 0) {
    lines.push('### ⚠️ Potentially Unused Dependencies', '');
    for (const dep of result.unusedDeps) {
      lines.push(`- \`${dep}\``);
    }
    lines.push('');
  } else {
    lines.push('### ✅ All dependencies are used', '');
  }

  if (result.mostImported.length > 0) {
    lines.push('### Top Imported Packages', '', '| Package | Import Count |', '|---------|-------------|');
    for (const { name, count } of result.mostImported.slice(0, 10)) {
      lines.push(`| \`${name}\` | ${count} |`);
    }
    lines.push('');
  }

  return lines.join('\n');
}

// Only run main when executed directly (not imported)
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(e => { console.error("❌ Error:", e.message); process.exit(1); });
}
