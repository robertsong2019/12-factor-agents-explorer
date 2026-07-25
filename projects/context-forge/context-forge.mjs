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
import { existsSync as fsExistsSync, unlinkSync as fsUnlinkSync, watch as fsWatch, readdirSync as fsReaddirSync } from "node:fs";

export { fsWatch as _fsWatch };

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
    watch: args.includes("--watch"),
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

  // F11: Watch mode — regenerate on file changes
  if (options.watch) {
    console.log(`\n👁  Watch mode enabled — monitoring ${basename(root)} for changes (500ms debounce)...`);
    console.log(`   Press Ctrl+C to stop.\n`);
    const cancel = watchProject(root, { ...options, dryRun: false }, 500, (result) => {
      if (result.success) {
        console.log(`   [${new Date().toLocaleTimeString()}] Regeneration #${result.runCount} completed in ${result.elapsed}s`);
      } else {
        console.log(`   [${new Date().toLocaleTimeString()}] Regeneration #${result.runCount} failed: ${result.error}`);
      }
    });
    process.on('SIGINT', () => {
      console.log('\n👋 Stopping watch mode...');
      cancel();
      process.exit(0);
    });
    // Keep process alive
    setInterval(() => {}, 1000);
  }
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

// ─── F11: Watch Mode ─────────────────────────────────────────────────

/**
 * Debounced watch mode — re-runs analysis when source files change.
 * @param {string} root - Project root directory
 * @param {object} options - Same options as main()
 * @param {number} debounceMs - Debounce delay (default 500ms)
 * @param {function} onRegenerate - Optional callback called after each regeneration
 * @returns {function} cancel function to stop watching
 */
export function watchProject(root, options = {}, debounceMs = 500, onRegenerate = null) {
  let timer = null;
  let running = false;
  let runCount = 0;

  const watchedExtensions = new Set([
    '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx',
    '.py', '.go', '.rs', '.java', '.kt',
    '.json', '.toml', '.yaml', '.yml', '.md',
    '.css', '.scss', '.html', '.vue', '.svelte',
  ]);

  function shouldWatch(filename) {
    if (!filename) return false;
    const ext = filename.slice(filename.lastIndexOf('.'));
    return watchedExtensions.has(ext);
  }

  async function regenerate() {
    if (running) return;
    running = true;
    runCount++;
    const start = Date.now();
    try {
      await runAnalysis(root, options);
      const elapsed = ((Date.now() - start) / 1000).toFixed(1);
      console.log(`\n📊 Regenerated (${runCount}) in ${elapsed}s — watching for changes...`);
      if (onRegenerate) onRegenerate({ success: true, runCount, elapsed: parseFloat(elapsed) });
    } catch (err) {
      console.error(`❌ Regeneration failed: ${err.message}`);
      if (onRegenerate) onRegenerate({ success: false, runCount, error: err.message });
    } finally {
      running = false;
    }
  }

  const watchers = [];
  try {
    const watcher = fsWatch(root, { recursive: true }, (eventType, filename) => {
      if (!shouldWatch(filename)) return;
      if (timer) clearTimeout(timer);
      timer = setTimeout(regenerate, debounceMs);
    });
    watchers.push(watcher);
  } catch {
    console.log('⚠️ Recursive watch not supported, using polling fallback...');
    const pollInterval = setInterval(() => { regenerate(); }, 5000);
    watchers.push({ close: () => clearInterval(pollInterval) });
  }

  return function cancel() {
    if (timer) clearTimeout(timer);
    for (const w of watchers) { try { w.close(); } catch { /* ignore */ } }
  };
}

// ─── F46: Code Complexity Analysis ───────────────────────────────────

const COMPLEXITY_PATTERNS = {
  javascript: [
    /\bif\b/g, /\belse\b/g, /\bfor\b/g, /\bwhile\b/g, /\bdo\b/g,
    /\bswitch\b/g, /\bcase\b/g, /\bcatch\b/g,
    /&&/g, /\|\|/g, /\?[^.]/g, // ternary + logical operators
  ],
  python: [
    /\bif\b/g, /\belif\b/g, /\belse\b/g, /\bfor\b/g, /\bwhile\b/g,
    /\bexcept\b/g, /\band\b/g, /\bor\b/g,
    /\bwith\b/g, // context managers add paths
  ],
  go: [
    /\bif\b/g, /\belse\b/g, /\bfor\b/g, /\bswitch\b/g, /\bcase\b/g,
    /\bselect\b/g, /\bdefer\b/g, /&&/g, /\|\|/g,
  ],
  rust: [
    /\bif\b/g, /\belse\b/g, /\bfor\b/g, /\bwhile\b/g, /\bloop\b/g,
    /\bmatch\b/g, /&&/g, /\|\|/g, /\?\./g,
  ],
  java: [
    /\bif\b/g, /\belse\b/g, /\bfor\b/g, /\bwhile\b/g, /\bswitch\b/g,
    /\bcase\b/g, /\bcatch\b/g, /&&/g, /\|\|/g, /\?[^.]/g,
  ],
};

function getComplexityPatterns(lang) {
  if (!lang) return null;
  const lower = lang.toLowerCase();
  if (lower.includes('javascript') || lower.includes('typescript') || lower.includes('react') || lower.includes('vue') || lower.includes('svelte'))
    return COMPLEXITY_PATTERNS.javascript;
  if (lower.includes('python')) return COMPLEXITY_PATTERNS.python;
  if (lower.includes('go')) return COMPLEXITY_PATTERNS.go;
  if (lower.includes('rust')) return COMPLEXITY_PATTERNS.rust;
  if (lower.includes('java') || lower.includes('kotlin') || lower.includes('swift'))
    return COMPLEXITY_PATTERNS.java;
  return null;
}

/**
 * Estimate cyclomatic complexity per file by counting decision points.
 * @param {string} root - Project root
 * @param {Map} files - Map of filepath → { lang, lines } (from scanLanguages)
 * @param {number} maxFileSize - Skip files larger than this
 * @returns {object} complexity analysis
 */
export async function analyzeCodeComplexity(root, files, maxFileSize = DEFAULT_MAX_FILE_SIZE) {
  const results = [];
  let totalComplexity = 0;
  let totalFiles = 0;
  let totalLines = 0;
  const byGrade = { A: 0, B: 0, C: 0, D: 0, F: 0 };

  for (const [relPath, meta] of files) {
    const lang = typeof meta === 'string' ? meta : meta?.lang;
    const patterns = getComplexityPatterns(lang);
    if (!patterns) continue;

    const fullPath = join(root, relPath);
    let fileStat;
    try { fileStat = await stat(fullPath); } catch { continue; }
    if (fileStat.size > maxFileSize) continue;

    let content;
    try { content = await readFile(fullPath, 'utf8'); } catch { continue; }

    const lineCount = content.split('\n').length;
    let decisionPoints = 0;

    for (const pattern of patterns) {
      const matches = content.match(pattern);
      if (matches) decisionPoints += matches.length;
    }

    // Cyclomatic complexity ≈ decision points + 1
    const complexity = decisionPoints + 1;
    // Density: complexity per 100 lines
    const density = lineCount > 0 ? (complexity / lineCount) * 100 : 0;
    // Grade: A (≤5), B (6-10), C (11-20), D (21-40), F (>40)
    const grade = complexity <= 5 ? 'A' : complexity <= 10 ? 'B' : complexity <= 20 ? 'C' : complexity <= 40 ? 'D' : 'F';

    results.push({ file: relPath, lang, complexity, density: parseFloat(density.toFixed(2)), lines: lineCount, grade });
    totalComplexity += complexity;
    totalFiles++;
    totalLines += lineCount;
    byGrade[grade]++;
  }

  results.sort((a, b) => b.complexity - a.complexity);

  return {
    files: results.slice(0, 20), // top 20 most complex
    totalFiles,
    totalComplexity,
    avgComplexity: totalFiles > 0 ? parseFloat((totalComplexity / totalFiles).toFixed(2)) : 0,
    totalLines,
    overallDensity: totalLines > 0 ? parseFloat((totalComplexity / totalLines * 100).toFixed(2)) : 0,
    gradeDistribution: byGrade,
    hottest: results.slice(0, 5),
  };
}

/**
 * Format complexity analysis as markdown report.
 */
export function formatComplexityReport(analysis) {
  if (!analysis || !analysis.files || analysis.files.length === 0) {
    return '### Code Complexity\n\nNo analyzable source files found.\n';
  }

  const lines = [
    '### Code Complexity', '',
    `| Metric | Value |`,
    `|--------|-------|`,
    `| Files analyzed | ${analysis.totalFiles} |`,
    `| Total complexity | ${analysis.totalComplexity} |`,
    `| Avg complexity/file | ${analysis.avgComplexity} |`,
    `| Complexity density | ${analysis.overallDensity}/100 lines |`,
    '',
    '#### Grade Distribution', '',
    '| Grade | Range | Files |',
    '|-------|-------|-------|',
    `| A | ≤5 | ${analysis.gradeDistribution.A} |`,
    `| B | 6-10 | ${analysis.gradeDistribution.B} |`,
    `| C | 11-20 | ${analysis.gradeDistribution.C} |`,
    `| D | 21-40 | ${analysis.gradeDistribution.D} |`,
    `| F | >40 | ${analysis.gradeDistribution.F} |`,
    '',
    '#### Top Complex Files', '',
    '| File | Complexity | Density | Lines | Grade |',
    '|------|-----------|---------|-------|-------|',
  ];

  for (const f of analysis.files.slice(0, 10)) {
    lines.push(`| \`${f.file}\` | ${f.complexity} | ${f.density} | ${f.lines} | ${f.grade} |`);
  }

  lines.push('');
  return lines.join('\n');
}

// ─── F47: File Coupling Analysis ────────────────────────────────────

/**
 * Analyze file coupling — which files share many dependencies.
 * Files that import the same packages are likely to change together.
 * @param {object} importData - { imports: Map<file, dep[]>, allImports: string[] }
 * @returns {object} coupling analysis
 */
export function analyzeFileCoupling(importData) {
  const { imports: byFile } = importData;
  if (!byFile || byFile.size === 0) {
    return {
      couples: [],
      totalFiles: 0,
      totalCouples: 0,
      avgCoupling: 0,
      mostCoupled: [],
      sharedDeps: [],
    };
  }

  // Build file → unique deps set
  const fileDeps = new Map();
  for (const [file, deps] of byFile) {
    fileDeps.set(file, new Set(deps));
  }

  const files = [...fileDeps.keys()];
  const couples = [];

  // For each pair of files, compute Jaccard similarity of their deps
  for (let i = 0; i < files.length; i++) {
    for (let j = i + 1; j < files.length; j++) {
      const depsA = fileDeps.get(files[i]);
      const depsB = fileDeps.get(files[j]);
      if (depsA.size === 0 && depsB.size === 0) continue;

      let intersection = 0;
      const smaller = depsA.size <= depsB.size ? depsA : depsB;
      const larger = depsA.size <= depsB.size ? depsB : depsA;
      for (const d of smaller) {
        if (larger.has(d)) intersection++;
      }
      const union = depsA.size + depsB.size - intersection;
      if (union === 0) continue;

      const jaccard = intersection / union;
      if (intersection >= 2) {
        couples.push({
          fileA: files[i],
          fileB: files[j],
          sharedCount: intersection,
          jaccard: parseFloat(jaccard.toFixed(3)),
        });
      }
    }
  }

  couples.sort((a, b) => b.sharedCount - a.sharedCount || b.jaccard - a.jaccard);

  // Per-file coupling score: sum of shared deps with all other files
  const couplingScore = {};
  for (const c of couples) {
    couplingScore[c.fileA] = (couplingScore[c.fileA] || 0) + c.sharedCount;
    couplingScore[c.fileB] = (couplingScore[c.fileB] || 0) + c.sharedCount;
  }

  const mostCoupled = Object.entries(couplingScore)
    .map(([file, score]) => ({ file, couplingScore: score }))
    .sort((a, b) => b.couplingScore - a.couplingScore)
    .slice(0, 10);

  // Most shared dependencies across files
  const depFrequency = {};
  for (const c of couples.slice(0, 20)) {
    const depsA = fileDeps.get(c.fileA);
    const depsB = fileDeps.get(c.fileB);
    for (const d of depsA) {
      if (depsB.has(d)) {
        depFrequency[d] = (depFrequency[d] || 0) + 1;
      }
    }
  }
  const sharedDeps = Object.entries(depFrequency)
    .map(([dep, count]) => ({ dep, coupledPairs: count }))
    .sort((a, b) => b.coupledPairs - a.coupledPairs)
    .slice(0, 10);

  return {
    couples: couples.slice(0, 15),
    totalFiles: files.length,
    totalCouples: couples.length,
    avgCoupling: files.length > 1 ? parseFloat((couples.length / (files.length * (files.length - 1) / 2)).toFixed(3)) : 0,
    mostCoupled,
    sharedDeps,
  };
}

/**
 * Format coupling analysis as markdown report.
 */
export function formatCouplingReport(analysis) {
  if (!analysis || !analysis.couples || analysis.couples.length === 0) {
    return '### File Coupling\n\nNo coupled files detected.\n';
  }

  const lines = [
    '### File Coupling', '',
    `| Metric | Value |`,
    `|--------|-------|`,
    `| Files analyzed | ${analysis.totalFiles} |`,
    `| Coupled pairs | ${analysis.totalCouples} |`,
    `| Coupling ratio | ${analysis.avgCoupling} |`,
    '',
    '#### Most Coupled Files', '',
    '| File | Coupling Score |',
    '|------|---------------|',
  ];

  for (const { file, couplingScore } of analysis.mostCoupled.slice(0, 5)) {
    lines.push(`| \`${file}\` | ${couplingScore} |`);
  }

  lines.push('', '#### Top Coupled Pairs', '', '| File A | File B | Shared Deps | Jaccard |', '|--------|--------|-------------|---------|');
  for (const c of analysis.couples.slice(0, 5)) {
    lines.push(`| \`${c.fileA}\` | \`${c.fileB}\` | ${c.sharedCount} | ${c.jaccard} |`);
  }

  if (analysis.sharedDeps.length > 0) {
    lines.push('', '#### Shared Dependencies', '', '| Package | Coupled Pairs |', '|---------|---------------|');
    for (const { dep, coupledPairs } of analysis.sharedDeps.slice(0, 5)) {
      lines.push(`| \`${dep}\` | ${coupledPairs} |`);
    }
  }

  lines.push('');
  return lines.join('\n');
}

// ─── F48: Tech Debt Score ────────────────────────────────────────────

/**
 * Aggregate tech debt signals into a unified score.
 * Combines: TODOs, dead code, complexity, unused deps, secrets, naming issues.
 * @param {object} signals - Individual analysis results
 * @returns {object} tech debt assessment
 */
export function analyzeTechDebt(signals = {}) {
  const {
    todos = null,
    deadCode = null,
    complexity = null,
    importHealth = null,
    secrets = null,
    naming = null,
    fileSizes = null,
  } = signals;

  const items = [];
  let totalWeight = 0;
  let totalScore = 0;

  // Each signal contributes a weighted score (0-100, higher = more debt)

  if (todos && typeof todos === 'object') {
    const todoCount = todos.total ?? todos.length ?? 0;
    const highPriority = Array.isArray(todos.items)
      ? todos.items.filter(t => t.priority === 'high' || t.priority === 'critical').length
      : 0;
    const score = Math.min(100, todoCount * 5 + highPriority * 10);
    items.push({
      category: 'TODOs/FIXMEs',
      count: todoCount,
      highPriority,
      score,
      weight: 15,
      severity: score >= 60 ? 'high' : score >= 30 ? 'medium' : 'low',
    });
    totalScore += score * 15;
    totalWeight += 15;
  }

  if (deadCode && typeof deadCode === 'object') {
    const deadCount = deadCode.unused ?? deadCode.dead?.length ?? 0;
    const totalExports = deadCode.total ?? 0;
    const ratio = totalExports > 0 ? deadCount / totalExports : 0;
    const score = Math.round(ratio * 100);
    items.push({
      category: 'Dead Code',
      count: deadCount,
      total: totalExports,
      ratio: parseFloat(ratio.toFixed(2)),
      score,
      weight: 15,
      severity: score >= 40 ? 'high' : score >= 20 ? 'medium' : 'low',
    });
    totalScore += score * 15;
    totalWeight += 15;
  }

  if (complexity && typeof complexity === 'object') {
    const highComplexity = (complexity.gradeDistribution?.D ?? 0) + (complexity.gradeDistribution?.F ?? 0);
    const avgComplexity = complexity.avgComplexity ?? 0;
    const score = Math.min(100, Math.round(avgComplexity * 5 + highComplexity * 8));
    items.push({
      category: 'Code Complexity',
      avgComplexity,
      highComplexityFiles: highComplexity,
      score,
      weight: 20,
      severity: score >= 60 ? 'high' : score >= 30 ? 'medium' : 'low',
    });
    totalScore += score * 20;
    totalWeight += 20;
  }

  if (importHealth && typeof importHealth === 'object') {
    const unusedCount = importHealth.unusedDeps?.length ?? 0;
    const score = Math.min(100, unusedCount * 10);
    items.push({
      category: 'Unused Dependencies',
      count: unusedCount,
      score,
      weight: 15,
      severity: score >= 50 ? 'high' : score >= 20 ? 'medium' : 'low',
    });
    totalScore += score * 15;
    totalWeight += 15;
  }

  if (secrets && typeof secrets === 'object') {
    const highRisk = secrets.high ?? 0;
    const totalCount = secrets.total ?? (secrets.findings?.length ?? 0);
    const score = Math.min(100, highRisk * 25 + totalCount * 5);
    items.push({
      category: 'Security (Secrets)',
      count: totalCount,
      highRisk,
      score,
      weight: 20,
      severity: score >= 40 ? 'critical' : score >= 20 ? 'high' : 'medium',
    });
    totalScore += score * 20;
    totalWeight += 20;
  }

  if (naming && typeof naming === 'object') {
    const inconsistencies = naming.inconsistencies ?? naming.inconsistentFiles ?? 0;
    const totalFiles = naming.totalFiles ?? naming.total ?? 1;
    const ratio = totalFiles > 0 ? inconsistencies / totalFiles : 0;
    const score = Math.round(ratio * 100);
    items.push({
      category: 'Naming Inconsistencies',
      count: inconsistencies,
      total: totalFiles,
      ratio: parseFloat(ratio.toFixed(2)),
      score,
      weight: 5,
      severity: score >= 50 ? 'medium' : 'low',
    });
    totalScore += score * 5;
    totalWeight += 5;
  }

  if (fileSizes && typeof fileSizes === 'object') {
    const outliers = fileSizes.outliers ?? 0;
    const score = Math.min(100, outliers * 10);
    items.push({
      category: 'File Size Outliers',
      count: outliers,
      score,
      weight: 10,
      severity: score >= 50 ? 'medium' : 'low',
    });
    totalScore += score * 10;
    totalWeight += 10;
  }

  const overallScore = totalWeight > 0 ? Math.round(totalScore / totalWeight) : 0;
  const grade = overallScore <= 20 ? 'A' : overallScore <= 40 ? 'B' : overallScore <= 60 ? 'C' : overallScore <= 80 ? 'D' : 'F';
  const highItems = items.filter(i => i.severity === 'high' || i.severity === 'critical');

  // Recommendations based on top issues
  const recommendations = [];
  for (const item of [...items].sort((a, b) => b.score - a.score)) {
    if (item.score < 20) break;
    if (item.category.includes('TODO')) recommendations.push(`Address ${item.count} TODO/FIXME comments (${item.highPriority} high priority)`);
    else if (item.category.includes('Dead')) recommendations.push(`Remove ${item.count} unused exports (${Math.round(item.ratio * 100)}% dead code ratio)`);
    else if (item.category.includes('Complex')) recommendations.push(`Refactor ${item.highComplexityFiles} high-complexity files (avg: ${item.avgComplexity})`);
    else if (item.category.includes('Unused')) recommendations.push(`Remove ${item.count} unused dependencies`);
    else if (item.category.includes('Security')) recommendations.push(`⚠️ Fix ${item.highRisk} high-risk secret exposures immediately`);
    else if (item.category.includes('Naming')) recommendations.push(`Standardize naming in ${item.count} files`);
    else if (item.category.includes('File Size')) recommendations.push(`Split ${item.count} oversized files`);
  }

  return {
    overallScore,
    grade,
    items,
    highPriorityCount: highItems.length,
    recommendations,
  };
}

/**
 * Format tech debt assessment as markdown report.
 */
export function formatTechDebtReport(debt) {
  if (!debt || !debt.items || debt.items.length === 0) {
    return '### Tech Debt Assessment\n\nNo signals available for assessment.\n';
  }

  const lines = [
    '### Tech Debt Assessment', '',
    `**Overall Score: ${debt.overallScore}/100 (${debt.grade})**`, '',
    '| Category | Score | Severity | Weight | Details |',
    '|----------|-------|----------|--------|---------|',
  ];

  for (const item of debt.items) {
    const emoji = item.severity === 'critical' ? '🔴' : item.severity === 'high' ? '🟠' : item.severity === 'medium' ? '🟡' : '🟢';
    const details = item.count !== undefined ? `${item.count} items` : item.avgComplexity !== undefined ? `avg ${item.avgComplexity}` : '-';
    lines.push(`| ${item.category} | ${item.score}/100 | ${emoji} ${item.severity} | ${item.weight}% | ${details} |`);
  }

  if (debt.recommendations.length > 0) {
    lines.push('', '#### Recommendations', '');
    for (let i = 0; i < debt.recommendations.length; i++) {
      lines.push(`${i + 1}. ${debt.recommendations[i]}`);
    }
  }

  lines.push('');
  return lines.join('\n');
}

/**
 * Core analysis pipeline — extracted from main() for reuse in watch mode.
 */
async function runAnalysis(root, options) {
  const gitignore = await parseGitignore(root);
  const [info, langs, importData, apiSurface, configData] = await Promise.all([
    detectProject(root),
    scanLanguages(root, 3, 0, gitignore),
    extractImports(root, 3, 0, gitignore),
    extractApiSurface(root, 3, 0, gitignore),
    parseConfigFiles(root),
  ]);
  info.apiSurface = apiSurface;
  info.configData = configData;

  const structure = await getDirStructure(root, '', 2, 0, gitignore);
  const gitInfo = await analyzeGitHistory(root);

  const generators = {
    agents: { file: 'AGENTS.md', gen: () => generateAgentsMd(info, langs, structure, gitInfo) },
    cursor: { file: '.cursorrules', gen: () => generateCursorRules(info, langs, structure) },
    copilot: { file: '.github/copilot-instructions.md', gen: () => generateCopilotInstructions(info) },
    claude: { file: '.claude/CLAUDE.md', gen: () => generateClaudeMd(info, langs, structure) },
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
}

/**
 * F49: Detect debug code — scans source files for leftover debug statements,
 * debugger directives, commented-out code blocks, and development artifacts.
 * Returns findings grouped by type with severity and file locations.
 */
export function detectDebugCode(files = []) {
  // files: [{ path, content, lang }]
  const patterns = {
    debugger: {
      regex: /\bdebugger\b/g,
      severity: 'high',
      desc: 'debugger statement',
    },
    console_log: {
      regex: /console\.(log|debug|info|warn|error|trace)\s*\(/g,
      severity: 'medium',
      desc: 'console output',
    },
    print_stmt: {
      regex: /\bprint\s*\(/g,
      severity: 'low',
      desc: 'print statement (may be legitimate in scripts)',
    },
    system_out: {
      regex: /System\.out\.print(ln)?\s*\(/g,
      severity: 'medium',
      desc: 'System.out print',
    },
    commented_code: {
      regex: /^\s*\/\/.*\b(if|for|while|function|return|const|let|var|def|class|import|export)\b/gm,
      severity: 'low',
      desc: 'commented-out code block',
    },
    todo_derelict: {
      regex: /(?:TODO|FIXME|HACK|XXX)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})?/gi,
      severity: 'medium',
      desc: 'stale TODO/FIXME',
    },
    alert: {
      regex: /\balert\s*\(/g,
      severity: 'high',
      desc: 'alert() call',
    },
  };

  const findings = [];
  let total = 0;

  for (const file of files) {
    if (!file.content) continue;
    const lines = file.content.split('\n');

    for (const [type, config] of Object.entries(patterns)) {
      let match;
      const regex = new RegExp(config.regex.source, config.regex.flags);
      while ((match = regex.exec(file.content)) !== null) {
        // Find line number from match index
        const lineNum = file.content.substring(0, match.index).split('\n').length;
        const lineText = lines[lineNum - 1] || '';

        // Skip if inside a string literal (rough heuristic)
        const beforeMatch = lineText.substring(0, match.index - (lineNum > 1 ? file.content.split('\n').slice(0, lineNum - 1).join('\n').length + 1 : 0));

        findings.push({
          type,
          severity: config.severity,
          file: file.path,
          line: lineNum,
          description: config.desc,
          snippet: lineText.trim().substring(0, 120),
        });
        total++;
      }
    }
  }

  // Group by type
  const byType = {};
  for (const f of findings) {
    if (!byType[f.type]) byType[f.type] = [];
    byType[f.type].push(f);
  }

  // Count by severity
  const bySeverity = { high: 0, medium: 0, low: 0 };
  for (const f of findings) {
    bySeverity[f.severity]++;
  }

  // Unique files affected
  const affectedFiles = [...new Set(findings.map(f => f.file))];

  return {
    total,
    byType,
    bySeverity,
    affectedFiles,
    fileCount: affectedFiles.length,
  };
}

/**
 * F49: Format debug code report as markdown.
 */
export function formatDebugCodeReport(result) {
  if (!result || result.total === 0) {
    return '## Debug Code Analysis\n\n✅ No debug statements found.\n';
  }

  let report = '## Debug Code Analysis\n\n';
  report += `**Total findings:** ${result.total} across ${result.fileCount} file(s)\n\n`;

  // Severity summary
  const sevEmoji = { high: '🔴', medium: '🟡', low: '🟢' };
  report += '| Severity | Count |\n|----------|-------|\n';
  for (const sev of ['high', 'medium', 'low']) {
    if (result.bySeverity[sev] > 0) {
      report += `| ${sevEmoji[sev]} ${sev} | ${result.bySeverity[sev]} |\n`;
    }
  }
  report += '\n';

  // Group by type
  for (const [type, items] of Object.entries(result.byType)) {
    report += `### ${type.replace(/_/g, ' ')} (${items.length})\n\n`;
    for (const item of items.slice(0, 20)) {
      report += `- \`${item.file}:${item.line}\` — ${item.snippet}\n`;
    }
    if (items.length > 20) {
      report += `- _...and ${items.length - 20} more_\n`;
    }
    report += '\n';
  }

  return report;
}


// ── F63: Environment Variable Health ─────────────────────────────────

export function analyzeEnvHealth(files = [], options = {}) {
  if (!files) files = [];
  const envExampleVars = new Set();
  const sourceEnvVars = new Set();
  const hardcodedValueIssues = [];
  const fileResults = [];
  let hasEnvExample = false;
  let envExampleFile = null;

  const jsExtensions = new Set(['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx']);
  const envPattern = /process\.env\.([A-Z_][A-Z0-9_]*)/g;
  const hardcodedPattern = /(?:const|let|var)\s+\w*(?:API_KEY|SECRET|TOKEN|PASSWORD|DATABASE_URL|DB_URL|PRIVATE_KEY)\w*\s*=\s*['"]([^'"]{6,})['"]/gi;

  // Parse .env.example / .env.sample if present
  for (const file of files) {
    if (!file.path || !file.content) continue;
    const basename = file.path.split('/').pop();
    if (basename === '.env.example' || basename === '.env.sample' || basename === '.env.template') {
      hasEnvExample = true;
      envExampleFile = file.path;
      for (const line of file.content.split('\n')) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) continue;
        const match = /^([A-Z_][A-Z0-9_]*)\s*=/.exec(trimmed);
        if (match) envExampleVars.add(match[1]);
      }
    }
  }

  // Scan source files for process.env usage and hardcoded secrets
  for (const file of files) {
    if (!file.content) continue;
    const basename = (file.path || '').split('/').pop();

    // Skip .env files themselves for source scanning, skip test files
    if (basename.startsWith('.env')) continue;
    if (/\.test\.|\.spec\.|__tests__|(?:^|\/)tests?\//.test(file.path || '')) continue;

    const ext = extname(file.path || '');
    if (!jsExtensions.has(ext) && ext !== '.py' && ext !== '.go') continue;

    const lines = file.content.split('\n');
    const envUsages = [];
    const hardcoded = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();

      // Skip comments
      if (/^\/\//.test(trimmed) || /^#/.test(trimmed) || /^\*/.test(trimmed)) continue;

      // Detect process.env.VAR_NAME
      let match;
      const reEnv = new RegExp(envPattern.source, 'g');
      while ((match = reEnv.exec(line)) !== null) {
        const varName = match[1];
        sourceEnvVars.add(varName);
        envUsages.push({ line: i + 1, var: varName, code: trimmed.substring(0, 100) });
      }

      // Detect hardcoded secret-like values
      const reHardcoded = new RegExp(hardcodedPattern.source, 'gi');
      while ((match = reHardcoded.exec(line)) !== null) {
        hardcoded.push({
          line: i + 1,
          type: 'hardcoded_secret',
          severity: 'high',
          description: `Potential hardcoded secret in variable assignment`,
          code: trimmed.substring(0, 100),
        });
      }
    }

    if (envUsages.length > 0 || hardcoded.length > 0) {
      fileResults.push({
        path: file.path,
        envUsages,
        hardcoded,
        issueCount: envUsages.length + hardcoded.length,
      });
    }

    // Collect hardcoded issues globally
    for (const h of hardcoded) {
      hardcodedValueIssues.push({ ...h, file: file.path });
    }
  }

  // Find undocumented env vars (used in source but not in .env.example)
  const undocumented = [...sourceEnvVars].filter(v => !envExampleVars.has(v));

  // Find stale env vars (in .env.example but not used in source)
  const stale = [...envExampleVars].filter(v => !sourceEnvVars.has(v));

  // Score calculation
  // Deduct: undocumented var = 5pts, hardcoded secret = 15pts, no .env.example = 20pts
  let deductions = undocumented.length * 5 + hardcodedValueIssues.length * 15;
  if (sourceEnvVars.size > 0 && !hasEnvExample) deductions += 20;
  const score = Math.max(0, 100 - deductions);

  let grade;
  if (score >= 90) grade = 'A';
  else if (score >= 80) grade = 'B';
  else if (score >= 70) grade = 'C';
  else if (score >= 60) grade = 'D';
  else grade = 'F';

  return {
    grade,
    score,
    hasEnvExample,
    envExampleFile,
    totalSourceEnvVars: sourceEnvVars.size,
    totalExampleVars: envExampleVars.size,
    undocumented,
    stale,
    hardcodedSecrets: hardcodedValueIssues,
    files: fileResults,
  };
}

export function formatEnvHealthReport(result) {
  if (!result) return '## Environment Variable Health\n\nNo data.\n';

  let report = '## Environment Variable Health\n\n';
  report += `**Grade:** ${result.grade} (${result.score}/100)\n`;
  report += `**.env.example:** ${result.hasEnvExample ? `✅ ${result.envExampleFile}` : '❌ Not found'}\n`;
  report += `**Source env vars:** ${result.totalSourceEnvVars}\n`;
  report += `**Example vars:** ${result.totalExampleVars}\n\n`;

  if (result.undocumented.length > 0) {
    report += '### ⚠️ Undocumented Environment Variables\n\n';
    report += 'Used in source but missing from .env.example:\n\n';
    for (const v of result.undocumented) {
      report += `- \`${v}\`\n`;
    }
    report += '\n';
  }

  if (result.stale.length > 0) {
    report += '### Stale Environment Variables\n\n';
    report += 'In .env.example but not used in source:\n\n';
    for (const v of result.stale) {
      report += `- \`${v}\`\n`;
    }
    report += '\n';
  }

  if (result.hardcodedSecrets.length > 0) {
    report += `### 🔴 Hardcoded Secrets (${result.hardcodedSecrets.length})\n\n`;
    for (const h of result.hardcodedSecrets.slice(0, 10)) {
      report += `- \`${h.file}:${h.line}\` — ${h.description}\n`;
    }
    report += '\n';
  }

  if (result.undocumented.length === 0 && result.hardcodedSecrets.length === 0) {
    report += '✅ All environment variables are properly documented.\n';
  }

  return report;
}


// Only run main when executed directly (not imported)
/**
 * F50: Analyze import graph — build a file-level directed graph from import data
 * and compute structural metrics: in-degree, out-degree, hub score, authority,
 * strongly connected components, and orphan detection.
 * Complements F20 (package-level dependency graph) with file-level analysis.
 */
export function analyzeImportGraph(importData) {
  const { imports: byFile, allImports = [] } = importData;

  // Collect all known files for path matching
  const knownFiles = new Set();
  for (const [file] of byFile) {
    knownFiles.add(file);
  }

  // Build file → file adjacency by resolving relative imports
  const fileImports = {}; // resolved file → [resolved targets]
  const fileSet = new Set();

  for (const [file, deps] of byFile) {
    fileSet.add(file);
    const resolved = [];
    for (const dep of deps) {
      // Resolve relative imports to file paths (best-effort)
      if (dep.startsWith('.') || dep.startsWith('/')) {
        const resolvedPath = resolveRelativeImport(file, dep, knownFiles);
        if (resolvedPath) {
          resolved.push(resolvedPath);
          fileSet.add(resolvedPath);
        }
      }
    }
    fileImports[file] = [...new Set(resolved)];
  }

  // Compute in-degree and out-degree
  const inDegree = {};
  const outDegree = {};
  for (const f of fileSet) {
    inDegree[f] = 0;
    outDegree[f] = 0;
  }
  for (const [src, targets] of Object.entries(fileImports)) {
    outDegree[src] = (outDegree[src] || 0) + targets.length;
    for (const tgt of targets) {
      inDegree[tgt] = (inDegree[tgt] || 0) + 1;
    }
  }

  // Hub score = normalized out-degree (files that import many others)
  // Authority score = normalized in-degree (files imported by many others)
  const maxIn = Math.max(1, ...Object.values(inDegree));
  const maxOut = Math.max(1, ...Object.values(outDegree));

  const nodes = [...fileSet].map(f => ({
    file: f,
    inDegree: inDegree[f] || 0,
    outDegree: outDegree[f] || 0,
    hubScore: Math.round(((outDegree[f] || 0) / maxOut) * 100) / 100,
    authorityScore: Math.round(((inDegree[f] || 0) / maxIn) * 100) / 100,
  }));

  // Find orphans (no incoming or outgoing edges)
  const orphans = nodes.filter(n => n.inDegree === 0 && n.outDegree === 0);

  // Find sinks (imported by others but import nothing — leaf modules)
  const sinks = nodes.filter(n => n.inDegree > 0 && n.outDegree === 0);

  // Find sources (import others but nobody imports them — entry points)
  const sources = nodes.filter(n => n.inDegree === 0 && n.outDegree > 0);

  // Top authorities (most imported)
  const topAuthorities = nodes
    .filter(n => n.inDegree > 0)
    .sort((a, b) => b.inDegree - a.inDegree)
    .slice(0, 10);

  // Top hubs (most importing)
  const topHubs = nodes
    .filter(n => n.outDegree > 0)
    .sort((a, b) => b.outDegree - a.outDegree)
    .slice(0, 10);

  // Detect cycles via DFS
  const cycles = [];
  const visited = new Set();
  const inStack = new Set();

  function dfs(node, path) {
    visited.add(node);
    inStack.add(node);
    const targets = fileImports[node] || [];
    for (const tgt of targets) {
      if (!fileSet.has(tgt)) continue;
      if (inStack.has(tgt)) {
        const cycleStart = path.indexOf(tgt);
        if (cycleStart !== -1) {
          cycles.push([...path.slice(cycleStart), tgt]);
        }
      } else if (!visited.has(tgt)) {
        dfs(tgt, [...path, tgt]);
      }
    }
    inStack.delete(node);
  }

  for (const f of fileSet) {
    if (!visited.has(f)) dfs(f, [f]);
  }

  return {
    totalFiles: fileSet.size,
    totalEdges: Object.values(fileImports).reduce((sum, arr) => sum + arr.length, 0),
    orphans,
    sinks,
    sources,
    topAuthorities,
    topHubs,
    cycles: cycles.slice(0, 20),
    cycleCount: cycles.length,
    avgOutDegree: fileSet.size > 0
      ? Math.round((Object.values(outDegree).reduce((a, b) => a + b, 0) / fileSet.size) * 100) / 100
      : 0,
  };
}

function resolveRelativeImport(fromFile, importPath, knownFiles = new Set()) {
  // Normalize: strip './' and '../' relative to importing file's directory
  const dir = fromFile.includes('/') ? fromFile.substring(0, fromFile.lastIndexOf('/')) : '';
  const parts = importPath.replace(/^\.\//, '').split('/');
  const resultParts = dir ? dir.split('/') : [];

  for (const part of parts) {
    if (part === '..') {
      resultParts.pop();
    } else if (part !== '.') {
      resultParts.push(part);
    }
  }

  const basePath = resultParts.join('/');

  // Try to match against known files with common extensions
  const extensions = ['', '.js', '.mjs', '.ts', '.jsx', '.tsx', '.py', '/index.js', '/index.mjs', '/index.ts'];
  for (const ext of extensions) {
    const candidate = basePath + ext;
    if (knownFiles.has(candidate)) return candidate;
  }

  // If no match in knownFiles, return base path (for graph construction)
  return basePath;
}

/**
 * F50: Format import graph report as markdown.
 */
export function formatImportGraphReport(result) {
  if (!result || result.totalFiles === 0) {
    return '## Import Graph Analysis\n\n_No import data available._\n';
  }

  let report = '## Import Graph Analysis\n\n';
  report += `| Metric | Value |\n|--------|-------|\n`;
  report += `| Total Files | ${result.totalFiles} |\n`;
  report += `| Total Edges | ${result.totalEdges} |\n`;
  report += `| Avg Out-Degree | ${result.avgOutDegree} |\n`;
  report += `| Cycles Detected | ${result.cycleCount} |\n\n`;

  if (result.topAuthorities.length > 0) {
    report += '### Top Authority Files (most imported)\n\n';
    for (const node of result.topAuthorities) {
      report += `- \`${node.file}\` — in-degree: ${node.inDegree}, authority: ${node.authorityScore}\n`;
    }
    report += '\n';
  }

  if (result.topHubs.length > 0) {
    report += '### Top Hub Files (most importing)\n\n';
    for (const node of result.topHubs) {
      report += `- \`${node.file}\` — out-degree: ${node.outDegree}, hub: ${node.hubScore}\n`;
    }
    report += '\n';
  }

  if (result.orphans.length > 0) {
    report += `### Orphan Files (${result.orphans.length})\n\n`;
    for (const node of result.orphans.slice(0, 10)) {
      report += `- \`${node.file}\`\n`;
    }
    if (result.orphans.length > 10) {
      report += `- _...and ${result.orphans.length - 10} more_\n`;
    }
    report += '\n';
  }

  if (result.cycles.length > 0) {
    report += `### Circular Dependencies (${result.cycleCount})\n\n`;
    for (const cycle of result.cycles.slice(0, 5)) {
      report += `- ${cycle.join(' → ')}\n`;
    }
    if (result.cycles.length > 5) {
      report += `- _...and ${result.cycles.length - 5} more_\n`;
    }
  }

  return report;
}

/**
 * F51: Analyze project maturity — comprehensive assessment combining dependency health,
 * code quality signals, test coverage estimation, documentation, and complexity
 * into a unified maturity scorecard with actionable recommendations.
 * Wraps multiple existing analyses into a single assessment.
 */
export function analyzeMaturity(info, options = {}) {
  const signals = {};
  const recommendations = [];
  let totalScore = 0;
  let maxScore = 0;

  // 1. Dependency Health (0-20)
  maxScore += 20;
  const deps = { ...(info.dependencies || info.pkg?.dependencies || {}) };
  const devDeps = { ...(info.devDependencies || info.pkg?.devDependencies || {}) };
  const depCount = Object.keys(deps).length;
  const devDepCount = Object.keys(devDeps).length;
  const allDepNames = [...Object.keys(deps), ...Object.keys(devDeps)];

  // Check for pinned vs ranged versions
  const pinned = allDepNames.filter(d => {
    const v = deps[d] || devDeps[d];
    return v && /^\d/.test(v);
  }).length;
  const pinRatio = allDepNames.length > 0 ? pinned / allDepNames.length : 1;
  const depScore = Math.round(pinRatio * 20);
  totalScore += depScore;

  signals.dependencyHealth = {
    score: depScore,
    max: 20,
    depCount,
    devDepCount,
    pinnedRatio: Math.round(pinRatio * 100) / 100,
    status: depScore >= 16 ? 'good' : depScore >= 10 ? 'fair' : 'poor',
  };
  if (pinRatio < 0.5) {
    recommendations.push({
      area: 'dependencies',
      priority: 'medium',
      message: `${Math.round((1 - pinRatio) * 100)}% of dependencies use version ranges. Consider pinning for reproducible builds.`,
    });
  }

  // 2. Testing Maturity (0-20)
  maxScore += 20;
  const configFiles = info.configFiles || [];
  const hasTestFramework = configFiles.some(f => /jest|vitest|pytest|mocha|\.mocharc|karma/.test(f));
  const hasTestDir = configFiles.some(f => /^(test|tests|spec|specs|__tests__)\//.test(f));
  const hasCI = configFiles.some(f => f.includes('workflows') || f.includes('.gitlab-ci') || f.includes('.circleci'));
  const hasCoverageConfig = configFiles.some(f => /coverage|codecov|nyc|c8/.test(f));

  const testChecks = [hasTestFramework, hasTestDir, hasCI, hasCoverageConfig];
  const testCheckCount = testChecks.filter(Boolean).length;
  const testScore = Math.round((testCheckCount / 4) * 20);
  totalScore += testScore;

  signals.testing = {
    score: testScore,
    max: 20,
    hasFramework: hasTestFramework,
    hasTestDir,
    hasCI,
    hasCoverage: hasCoverageConfig,
    status: testScore >= 15 ? 'good' : testScore >= 10 ? 'fair' : 'poor',
  };
  if (!hasTestFramework) {
    recommendations.push({
      area: 'testing',
      priority: 'high',
      message: 'No test framework detected. Add tests to improve reliability.',
    });
  }
  if (!hasCI) {
    recommendations.push({
      area: 'testing',
      priority: 'medium',
      message: 'No CI configuration found. Automate testing with GitHub Actions or similar.',
    });
  }

  // 3. Documentation (0-20)
  maxScore += 20;
  const hasReadme = configFiles.some(f => /readme/i.test(f));
  const hasChangelog = configFiles.some(f => /changelog/i.test(f));
  const hasContributing = configFiles.some(f => /contributing/i.test(f));
  const hasLicense = configFiles.some(f => /license/i.test(f)) || !!info.license;
  const hasDocs = configFiles.some(f => /docs?\//i.test(f));

  const docChecks = { hasReadme, hasChangelog, hasContributing, hasLicense, hasDocs };
  const docCount = Object.values(docChecks).filter(Boolean).length;
  const docScore = Math.round((docCount / 5) * 20);
  totalScore += docScore;

  signals.documentation = {
    score: docScore,
    max: 20,
    ...docChecks,
    status: docScore >= 16 ? 'good' : docScore >= 8 ? 'fair' : 'poor',
  };
  if (!hasReadme) {
    recommendations.push({
      area: 'documentation',
      priority: 'high',
      message: 'No README file detected. Add a README for project discoverability.',
    });
  }
  if (!hasLicense && !info.license) {
    recommendations.push({
      area: 'documentation',
      priority: 'high',
      message: 'No LICENSE file found. Add a license for legal clarity.',
    });
  }

  // 4. Code Quality (0-20)
  maxScore += 20;
  const hasLinter = configFiles.some(f => /eslint|tslint|flake8|pylint|ruff|golangci/.test(f));
  const hasFormatter = configFiles.some(f => /prettier|black|gofmt|rustfmt/.test(f));
  const hasTypeChecking = configFiles.some(f => /tsconfig|mypy|pyright/.test(f));
  const hasGitignore = configFiles.some(f => /\.gitignore/.test(f));
  const hasEditorConfig = configFiles.some(f => /editorconfig/.test(f));

  const qualityChecks = { hasLinter, hasFormatter, hasTypeChecking, hasGitignore, hasEditorConfig };
  const qualityCount = Object.values(qualityChecks).filter(Boolean).length;
  const qualityScore = Math.round((qualityCount / 5) * 20);
  totalScore += qualityScore;

  signals.codeQuality = {
    score: qualityScore,
    max: 20,
    ...qualityChecks,
    status: qualityScore >= 16 ? 'good' : qualityScore >= 8 ? 'fair' : 'poor',
  };
  if (!hasLinter) {
    recommendations.push({
      area: 'quality',
      priority: 'medium',
      message: 'No linter configured. Add ESLint/Pylint/Ruff for consistent code style.',
    });
  }

  // 5. Project Structure (0-20)
  maxScore += 20;
  const scripts = info.scripts || info.pkg?.scripts || {};
  const scriptCount = Object.keys(scripts).length;
  const hasBuildScript = !!scripts.build || !!scripts.compile;
  const hasTestScript = !!scripts.test;
  const hasDevScript = !!scripts.dev || !!scripts.start;
  const hasLintScript = !!scripts.lint || !!scripts['lint:check'];
  const hasFormatScript = !!scripts.format || !!scripts['format:check'];

  const structureChecks = { hasBuildScript, hasTestScript, hasDevScript, hasLintScript, hasFormatScript };
  const structureCount = Object.values(structureChecks).filter(Boolean).length;
  const structureScore = Math.round((structureCount / 5) * 20);
  totalScore += structureScore;

  signals.projectStructure = {
    score: structureScore,
    max: 20,
    scriptCount,
    ...structureChecks,
    status: structureScore >= 16 ? 'good' : structureScore >= 8 ? 'fair' : 'poor',
  };
  if (!hasTestScript) {
    recommendations.push({
      area: 'structure',
      priority: 'high',
      message: 'No test script in package.json. Add "test" script for CI integration.',
    });
  }

  // Overall score
  const pct = maxScore > 0 ? Math.round((totalScore / maxScore) * 100) : 0;
  const grade = pct >= 90 ? 'A' : pct >= 80 ? 'B' : pct >= 70 ? 'C' : pct >= 60 ? 'D' : 'F';

  return {
    overallScore: pct,
    grade,
    maxScore,
    achievedScore: totalScore,
    signals,
    recommendations: recommendations.sort((a, b) => {
      const pri = { high: 0, medium: 1, low: 2 };
      return pri[a.priority] - pri[b.priority];
    }),
    summary: `Project maturity: ${grade} (${pct}/100). ${recommendations.length} recommendation(s).`,
  };
}

/**
 * F51: Format maturity report as markdown.
 */
export function formatMaturityReport(result) {
  if (!result || result.overallScore === undefined) {
    return '## Project Maturity\n\n_No data available._\n';
  }

  let report = '## Project Maturity Assessment\n\n';
  report += `**Overall Grade: ${result.grade} (${result.overallScore}/100)**\n\n`;

  // Signal scores table
  report += '| Area | Score | Status |\n|------|-------|--------|\n';
  const areaLabels = {
    dependencyHealth: 'Dependency Health',
    testing: 'Testing',
    documentation: 'Documentation',
    codeQuality: 'Code Quality',
    projectStructure: 'Project Structure',
  };
  for (const [key, signal] of Object.entries(result.signals)) {
    const label = areaLabels[key] || key;
    const statusEmoji = signal.status === 'good' ? '✅' : signal.status === 'fair' ? '🟡' : '🔴';
    report += `| ${label} | ${signal.score}/${signal.max} | ${statusEmoji} ${signal.status} |\n`;
  }
  report += '\n';

  // Recommendations
  if (result.recommendations.length > 0) {
    report += '### Recommendations\n\n';
    const priEmoji = { high: '🔴', medium: '🟡', low: '🟢' };
    for (const rec of result.recommendations) {
      report += `- ${priEmoji[rec.priority] || '•'} **[${rec.priority.toUpperCase()}]** ${rec.message}\n`;
    }
    report += '\n';
  } else {
    report += '### Recommendations\n\n✅ No critical improvements needed.\n\n';
  }

  return report;
}

/**
 * F52: Detect security issues in source code content.
 * Pattern-based vulnerability detection: SQL injection, XSS, hardcoded credentials,
 * eval usage, path traversal, prototype pollution, insecure deserialization.
 * Complements F32 (filesystem secret scanning) with code-level analysis.
 */
export function detectSecurityIssues(files = []) {
  // files: [{ path, content, lang }]
  const patterns = {
    sql_injection: {
      regex: /(?:query|execute|exec)\s*\(\s*["'`]?(?:SELECT|INSERT|UPDATE|DELETE|DROP|UNION).*?\+\s*\w+/gi,
      severity: 'high',
      desc: 'Potential SQL injection — string concatenation in query',
      cwe: 'CWE-89',
    },
    xss_reflected: {
      regex: /(?:innerHTML|document\.write|dangerouslySetInnerHTML)\s*[=\(]/g,
      severity: 'high',
      desc: 'Potential XSS — direct DOM insertion',
      cwe: 'CWE-79',
    },
    hardcoded_password: {
      regex: /(?:password|passwd|pwd|secret|api_?key|token)\s*[:=]\s*["'`][^"'`]{4,}["'`]/gi,
      severity: 'high',
      desc: 'Hardcoded credential',
      cwe: 'CWE-798',
    },
    eval_usage: {
      regex: /\beval\s*\(/g,
      severity: 'medium',
      desc: 'eval() usage — code injection risk',
      cwe: 'CWE-94',
    },
    path_traversal: {
      regex: /(?:readFile|writeFile|readFileSync|writeFileSync|open|createReadStream)\s*\(\s*.*?\+\s*\w+|\.\.\/\.\.\//g,
      severity: 'medium',
      desc: 'Potential path traversal',
      cwe: 'CWE-22',
    },
    prototype_pollution: {
      regex: /(?:__proto__|prototype)\s*\[|Object\.assign\s*\(\s*\w+\.\w+\s*,/g,
      severity: 'medium',
      desc: 'Potential prototype pollution',
      cwe: 'CWE-1321',
    },
    insecure_random: {
      regex: /Math\.random\s*\(\)/g,
      severity: 'low',
      desc: 'Insecure random number generation (use crypto for security)',
      cwe: 'CWE-330',
    },
    http_url: {
      regex: /http:\/\/(?!localhost|127\.0\.0\.1|0\.0\.0\.0)/g,
      severity: 'low',
      desc: 'HTTP URL (not HTTPS)',
      cwe: 'CWE-319',
    },
    disabled_tls: {
      regex: /rejectUnauthorized\s*:\s*false|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*["'`]0["'`]/g,
      severity: 'high',
      desc: 'TLS verification disabled',
      cwe: 'CWE-295',
    },
    command_injection: {
      regex: /(?:exec|execSync|spawn|spawnSync)\s*\(\s*.*?\$\{|(?:exec|execSync)\s*\(\s*["'`].*?\+/g,
      severity: 'high',
      desc: 'Potential command injection',
      cwe: 'CWE-78',
    },
    regex_dos: {
      regex: /new RegExp\s*\(\s*["'`].*?\+/g,
      severity: 'medium',
      desc: 'Dynamic RegExp construction (ReDoS risk)',
      cwe: 'CWE-1333',
    },
  };

  const findings = [];
  let total = 0;

  for (const file of files) {
    if (!file.content) continue;
    const lines = file.content.split('\n');

    for (const [type, config] of Object.entries(patterns)) {
      let match;
      const regex = new RegExp(config.regex.source, config.regex.flags);
      while ((match = regex.exec(file.content)) !== null) {
        const lineNum = file.content.substring(0, match.index).split('\n').length;
        const lineText = lines[lineNum - 1] || '';

        findings.push({
          type,
          severity: config.severity,
          cwe: config.cwe,
          file: file.path,
          line: lineNum,
          description: config.desc,
          snippet: lineText.trim().substring(0, 120),
        });
        total++;
      }
    }
  }

  // Group by type
  const byType = {};
  for (const f of findings) {
    if (!byType[f.type]) byType[f.type] = [];
    byType[f.type].push(f);
  }

  // Count by severity
  const bySeverity = { high: 0, medium: 0, low: 0 };
  for (const f of findings) {
    bySeverity[f.severity]++;
  }

  const affectedFiles = [...new Set(findings.map(f => f.file))];

  return {
    total,
    byType,
    bySeverity,
    affectedFiles,
    fileCount: affectedFiles.length,
    riskLevel: bySeverity.high > 0 ? 'critical' : bySeverity.medium > 0 ? 'elevated' : 'low',
  };
}

/**
 * F52: Format security report as markdown.
 */
export function formatSecurityReport(result) {
  if (!result || result.total === 0) {
    return '## Security Analysis\n\n✅ No security issues detected.\n';
  }

  let report = '## Security Analysis\n\n';
  const riskEmoji = { critical: '🔴', elevated: '🟡', low: '🟢' };
  report += `**Risk Level:** ${riskEmoji[result.riskLevel] || '•'} ${result.riskLevel.toUpperCase()}\n`;
  report += `**Total findings:** ${result.total} across ${result.fileCount} file(s)\n\n`;

  // Severity table
  report += '| Severity | Count |\n|----------|-------|\n';
  for (const sev of ['high', 'medium', 'low']) {
    if (result.bySeverity[sev] > 0) {
      report += `| ${riskEmoji[sev] || '•'} ${sev} | ${result.bySeverity[sev]} |\n`;
    }
  }
  report += '\n';

  // Group by type with CWE references
  for (const [type, items] of Object.entries(result.byType)) {
    const cwe = items[0].cwe;
    report += `### ${type.replace(/_/g, ' ')} (${items.length}) — [${cwe}]\n\n`;
    for (const item of items.slice(0, 15)) {
      report += `- \`${item.file}:${item.line}\` — ${item.snippet}\n`;
    }
    if (items.length > 15) {
      report += `- _...and ${items.length - 15} more_\n`;
    }
    report += '\n';
  }

  return report;
}

/**
 * F53: Analyze error handling patterns in source files.
 * Detects anti-patterns: empty catch, swallowed errors, bare throw, unhandled promise,
 * catch without type check, overly broad catch.
 */
export function analyzeErrorHandling(files = []) {
  const patterns = {
    empty_catch: {
      regex: /catch\s*\([^)]*\)\s*\{\s*\}/g,
      severity: 'high',
      desc: 'Empty catch block — error silently swallowed',
    },
    catch_ignore: {
      regex: /catch\s*\(\s*_\s*\)\s*\{/g,
      severity: 'medium',
      desc: 'Catch binds to underscore — intentional error suppression',
    },
    bare_throw: {
      regex: /^\s*throw\s*;\s*$/gm,
      severity: 'medium',
      desc: 'Bare rethrow without context — loses stack info in some runtimes',
    },
    console_error_catch: {
      regex: /catch\s*\([^)]*\)\s*\{\s*console\.\w+\s*\([^)]*\)\s*;?\s*\}/g,
      severity: 'low',
      desc: 'Catch only logs — error not propagated or handled',
    },
    unhandled_promise: {
      regex: /\.then\s*\([^)]*\)\s*(?!\.catch)/g,
      severity: 'medium',
      desc: 'Promise .then() without corresponding .catch()',
    },
    async_no_try: {
      regex: /async\s+function\s+\w+\s*\([^)]*\)\s*\{/g,
      severity: 'info',
      desc: 'Async function — verify try/catch coverage',
    },
    catch_all: {
      regex: /catch\s*\(\s*\w+\s*\)\s*\{/g,
      severity: 'low',
      desc: 'Generic catch — no error type filtering',
    },
    throw_string: {
      regex: /throw\s+["'`]/g,
      severity: 'high',
      desc: 'Throwing a string instead of Error object — loses stack trace',
    },
  };

  const findings = [];

  for (const file of files) {
    if (!file.content) continue;
    const lines = file.content.split('\n');

    for (const [type, config] of Object.entries(patterns)) {
      const regex = new RegExp(config.regex.source, config.regex.flags);
      let match;
      while ((match = regex.exec(file.content)) !== null) {
        const lineNum = file.content.substring(0, match.index).split('\n').length;
        const lineText = lines[lineNum - 1] || '';
        findings.push({
          type,
          severity: config.severity,
          file: file.path,
          line: lineNum,
          description: config.desc,
          snippet: lineText.trim().substring(0, 120),
        });
      }
    }
  }

  // Group
  const byType = {};
  const bySeverity = { high: 0, medium: 0, low: 0, info: 0 };
  for (const f of findings) {
    if (!byType[f.type]) byType[f.type] = [];
    byType[f.type].push(f);
    if (bySeverity[f.severity] !== undefined) bySeverity[f.severity]++;
  }

  const affectedFiles = [...new Set(findings.map(f => f.file))];
  const score = Math.max(0, 100 - findings.filter(f => f.severity === 'high').length * 10 - findings.filter(f => f.severity === 'medium').length * 5 - findings.filter(f => f.severity === 'low').length * 2);

  return {
    total: findings.length,
    byType,
    bySeverity,
    affectedFiles,
    fileCount: affectedFiles.length,
    healthScore: score,
    grade: score >= 90 ? 'A' : score >= 75 ? 'B' : score >= 60 ? 'C' : score >= 40 ? 'D' : 'F',
  };
}

/**
 * F53: Format error handling report as markdown.
 */
export function formatErrorHandlingReport(result) {
  if (!result || result.total === 0) {
    return '## Error Handling Analysis\n\n✅ No error handling issues detected.\n';
  }

  const sevEmoji = { high: '🔴', medium: '🟡', low: '🟢', info: '🔵' };
  let report = '## Error Handling Analysis\n\n';
  report += `**Health Grade:** ${result.grade} (${result.healthScore}/100)\n`;
  report += `**Total findings:** ${result.total} across ${result.fileCount} file(s)\n\n`;

  // Severity table
  report += '| Severity | Count |\n|----------|-------|\n';
  for (const sev of ['high', 'medium', 'low', 'info']) {
    if (result.bySeverity[sev] > 0) {
      report += `| ${sevEmoji[sev] || '•'} ${sev} | ${result.bySeverity[sev]} |\n`;
    }
  }
  report += '\n';

  for (const [type, items] of Object.entries(result.byType)) {
    report += `### ${type.replace(/_/g, ' ')} (${items.length})\n\n`;
    for (const item of items.slice(0, 10)) {
      report += `- \`${item.file}:${item.line}\` — ${item.description}\n`;
      if (item.snippet) report += `  \` ${item.snippet}\`\n`;
    }
    if (items.length > 10) {
      report += `- _...and ${items.length - 10} more_\n`;
    }
    report += '\n';
  }

  return report;
}

/**
 * F54: Detect near-duplicate code blocks across files.
 * Uses line-based fingerprinting with configurable minimum block size.
 */
export function analyzeDuplicateCode(files = [], opts = {}) {
  const minLines = opts.minLines || 6;
  const minNormalizedLines = opts.minNormalizedLines || 4;
  const skipEmpty = true;

  // Build fingerprint index: normalized line sequences → [file, startLine]
  const blocks = [];

  for (const file of files) {
    if (!file.content) continue;
    const lines = file.content.split('\n');
    const normalized = lines.map(l => {
      let line = l.trim();
      // Strip comments
      line = line.replace(/\/\/.*$/, '').replace(/\/\*.*?\*\//g, '').replace(/#.*$/, '').trim();
      // Normalize whitespace
      line = line.replace(/\s+/g, ' ');
      // Strip string literals (replace with placeholder)
      line = line.replace(/["'`][^"'`]*["'`]/g, '"..."');
      return line;
    });

    // Sliding window over non-empty normalized lines
    for (let i = 0; i <= normalized.length - minLines; i++) {
      const window = normalized.slice(i, i + minLines);
      if (skipEmpty && window.filter(l => l.length > 0).length < minNormalizedLines) continue;

      // Create a hash: join non-empty lines
      const nonEmpty = window.filter(l => l.length > 0);
      if (nonEmpty.length < minNormalizedLines) continue;

      const fingerprint = nonEmpty.join('|');
      if (fingerprint.length < 30) continue; // Skip trivially short blocks

      blocks.push({
        fingerprint,
        file: file.path,
        startLine: i + 1,
        endLine: i + minLines,
        lineCount: minLines,
      });
    }
  }

  // Group by fingerprint
  const fpMap = new Map();
  for (const block of blocks) {
    if (!fpMap.has(block.fingerprint)) {
      fpMap.set(block.fingerprint, []);
    }
    fpMap.get(block.fingerprint).push(block);
  }

  // Find duplicates (same fingerprint appearing in 2+ places)
  const duplicates = [];
  for (const [fingerprint, occurrences] of fpMap) {
    if (occurrences.length < 2) continue;

    // Check if duplicates are in different files or far apart in same file
    const uniqueFiles = [...new Set(occurrences.map(o => o.file))];
    const isSameFileFar = occurrences.some((a, idx) => {
      return occurrences.slice(idx + 1).some(b => b.file === a.file && Math.abs(b.startLine - a.startLine) > minLines);
    });

    if (uniqueFiles.length < 2 && !isSameFileFar) continue;

    duplicates.push({
      fingerprint: fingerprint.substring(0, 80) + (fingerprint.length > 80 ? '...' : ''),
      occurrences,
      fileCount: uniqueFiles.length,
      totalLines: occurrences.length * occurrences[0].lineCount,
    });
  }

  // Sort by impact (fileCount desc, then totalLines desc)
  duplicates.sort((a, b) => b.fileCount - a.fileCount || b.totalLines - a.totalLines);

  const affectedFiles = [...new Set(duplicates.flatMap(d => d.occurrences.map(o => o.file)))];
  const wasteEstimate = duplicates.reduce((sum, d) => sum + (d.occurrences.length - 1) * d.occurrences[0].lineCount, 0);

  return {
    duplicateGroups: duplicates.length,
    totalOccurrences: duplicates.reduce((s, d) => s + d.occurrences.length, 0),
    affectedFiles,
    fileCount: affectedFiles.length,
    wastedLines: wasteEstimate,
    topDuplicates: duplicates.slice(0, 20),
  };
}

/**
 * F54: Format duplicate code report as markdown.
 */
export function formatDuplicateCodeReport(result) {
  if (!result || result.duplicateGroups === 0) {
    return '## Duplicate Code Analysis\n\n✅ No significant duplicate code blocks detected.\n';
  }

  let report = '## Duplicate Code Analysis\n\n';
  report += `**Duplicate groups:** ${result.duplicateGroups}\n`;
  report += `**Total occurrences:** ${result.totalOccurrences}\n`;
  report += `**Affected files:** ${result.fileCount}\n`;
  report += `**Estimated wasted lines:** ~${result.wastedLines}\n\n`;

  for (const dup of result.topDuplicates.slice(0, 10)) {
    report += `### Duplicate block (${dup.fileCount} file(s), ${dup.occurrences[0].lineCount} lines each)\n\n`;
    for (const occ of dup.occurrences) {
      report += `- \`${occ.file}:${occ.startLine}-${occ.endLine}\`\n`;
    }
    report += `  \` ${dup.fingerprint}\`\n\n`;
  }

  if (result.duplicateGroups > 10) {
    report += `_...and ${result.duplicateGroups - 10} more groups_\n`;
  }

  return report;
}

/**
 * F55: Analyze comment health across source files.
 * Measures comment-to-code ratio, detects stale/obsolete comments,
 * and evaluates documentation coverage for exported symbols.
 */
export function analyzeCommentHealth(files = [], opts = {}) {
  const minFileLines = opts.minFileLines || 5;
  const results = [];
  let totalCodeLines = 0;
  let totalCommentLines = 0;
  let totalTodoFixme = 0;
  let totalStaleComments = 0;
  let totalExportedSymbols = 0;
  let totalDocumentedExports = 0;

  const stalePatterns = [
    { regex: /TODO\b/gi, type: 'todo', severity: 'info', desc: 'TODO comment — pending work' },
    { regex: /FIXME\b/gi, type: 'fixme', severity: 'medium', desc: 'FIXME comment — known issue' },
    { regex: /HACK\b/gi, type: 'hack', severity: 'medium', desc: 'HACK comment — workaround' },
    { regex: /XXX\b/gi, type: 'xxx', severity: 'low', desc: 'XXX comment — needs attention' },
    { regex: /@deprecated/gi, type: 'deprecated', severity: 'high', desc: 'Deprecated marker' },
  ];

  for (const file of files) {
    if (!file.content) continue;
    const lines = file.content.split('\n');
    const fileLineCount = lines.length;
    if (fileLineCount < minFileLines) continue;

    let codeLines = 0;
    let commentLines = 0;
    let docLines = 0;
    const issues = [];

    let inBlockComment = false;
    for (let i = 0; i < lines.length; i++) {
      const trimmed = lines[i].trim();

      if (inBlockComment) {
        commentLines++;
        if (trimmed.includes('*/')) inBlockComment = false;
        for (const sp of stalePatterns) {
          const re = new RegExp(sp.regex.source, sp.regex.flags);
          if (re.test(trimmed)) {
            issues.push({ type: sp.type, severity: sp.severity, line: i + 1, description: sp.desc, snippet: trimmed.substring(0, 120) });
          }
        }
        continue;
      }

      // Full-line comment (including single-line block comments)
      if (/^\/\//.test(trimmed) || /^#/.test(trimmed) || /^\/\*[\s\S]*\*\/\s*$/.test(trimmed)) {
        commentLines++;
        if (/\/\*\*/.test(trimmed)) docLines++;
        for (const sp of stalePatterns) {
          const re = new RegExp(sp.regex.source, sp.regex.flags);
          if (re.test(trimmed)) {
            issues.push({ type: sp.type, severity: sp.severity, line: i + 1, description: sp.desc, snippet: trimmed.substring(0, 120) });
          }
        }
        continue;
      }

      // Multi-line block comment start (not closed on same line)
      if (/\/\*/.test(trimmed) && !/\*\//.test(trimmed)) {
        commentLines++;
        inBlockComment = true;
        if (/\/\*\*/.test(trimmed)) docLines++;
        continue;
      }

      // Code line (possibly with trailing comment)
      codeLines++;
      for (const sp of stalePatterns) {
        const re = new RegExp(sp.regex.source, sp.regex.flags);
        if (re.test(trimmed)) {
          issues.push({ type: sp.type, severity: sp.severity, line: i + 1, description: sp.desc, snippet: trimmed.substring(0, 120) });
        }
      }
    }

    // Doc coverage: find exported symbols with preceding JSDoc
    const exportRegexSrc = '\\bexport\\s+(?:async\\s+)?(?:function|class|const|let|var)\\s+(\\w+)';
    const exportMatches = [...file.content.matchAll(new RegExp(exportRegexSrc, 'g'))];
    const exportedNames = exportMatches.map(m => m[1]);
    let documented = 0;

    for (const match of exportMatches) {
      // Check only the lines immediately before the export keyword
      const lineStart = file.content.lastIndexOf('\n', match.index);
      const twoLinesBack = file.content.lastIndexOf('\n', lineStart - 1);
      const preceding = file.content.substring(twoLinesBack + 1, match.index);
      if (/^[\s\/*]*\*\/\s*$/.test(preceding.replace(/\n/g, '')) || /\/\*\*[\s\S]*?\*\/\s*$/.test(preceding)) {
        documented++;
      }
    }

    const ratio = codeLines > 0 ? (commentLines / codeLines) * 100 : 0;
    const docCoverage = exportedNames.length > 0 ? (documented / exportedNames.length) * 100 : -1;

    if (ratio < 5 && codeLines > 50) {
      issues.unshift({ type: 'low_comment_ratio', severity: 'medium', line: 0, description: `Low comment ratio: ${ratio.toFixed(1)}% (${commentLines} comments / ${codeLines} code lines)`, snippet: '' });
    }
    if (ratio > 60 && codeLines > 20) {
      issues.unshift({ type: 'over_commented', severity: 'info', line: 0, description: `High comment ratio: ${ratio.toFixed(1)}% — possible over-commenting`, snippet: '' });
    }

    totalCodeLines += codeLines;
    totalCommentLines += commentLines;
    totalTodoFixme += issues.filter(i => i.type === 'todo' || i.type === 'fixme' || i.type === 'hack').length;
    totalStaleComments += issues.filter(i => i.type !== 'low_comment_ratio' && i.type !== 'over_commented').length;
    totalExportedSymbols += exportedNames.length;
    totalDocumentedExports += documented;

    results.push({
      file: file.path,
      codeLines,
      commentLines,
      docLines,
      ratio: parseFloat(ratio.toFixed(2)),
      exportedSymbols: exportedNames.length,
      documentedExports: documented,
      docCoverage: docCoverage >= 0 ? parseFloat(docCoverage.toFixed(2)) : null,
      issues,
    });
  }

  const overallRatio = totalCodeLines > 0 ? (totalCommentLines / totalCodeLines) * 100 : 0;
  const overallDocCoverage = totalExportedSymbols > 0 ? (totalDocumentedExports / totalExportedSymbols) * 100 : 0;

  const docScore = totalExportedSymbols > 0 ? overallDocCoverage : 75;
  const ratioScore = overallRatio >= 10 && overallRatio <= 35 ? 100 : overallRatio < 10 ? 40 : overallRatio > 50 ? 60 : 80;
  const stalePenalty = Math.min(50, totalStaleComments * 5);
  const healthScore = Math.max(0, Math.round(docScore * 0.4 + ratioScore * 0.3 + (100 - stalePenalty) * 0.3));

  return {
    files: results,
    fileCount: results.length,
    totalCodeLines,
    totalCommentLines,
    overallRatio: parseFloat(overallRatio.toFixed(2)),
    totalExportedSymbols,
    totalDocumentedExports,
    overallDocCoverage: parseFloat(overallDocCoverage.toFixed(2)),
    totalTodoFixme,
    totalStaleComments,
    healthScore,
    grade: healthScore >= 90 ? 'A' : healthScore >= 75 ? 'B' : healthScore >= 60 ? 'C' : healthScore >= 40 ? 'D' : 'F',
  };
}

/**
 * F55: Format comment health report as markdown.
 */
export function formatCommentHealthReport(result) {
  if (!result || result.fileCount === 0) {
    return '## Comment Health Analysis\n\n⚠️ No files to analyze.\n';
  }

  let report = '## Comment Health Analysis\n\n';
  report += `**Health Grade:** ${result.grade} (${result.healthScore}/100)\n`;
  report += `**Overall comment ratio:** ${result.overallRatio}% (${result.totalCommentLines} comment lines / ${result.totalCodeLines} code lines)\n`;
  report += `**Documentation coverage:** ${result.overallDocCoverage}% (${result.totalDocumentedExports}/${result.totalExportedSymbols} exports documented)\n`;
  report += `**TODO/FIXME/HACK markers:** ${result.totalTodoFixme}\n`;
  report += `**Stale/deprecated markers:** ${result.totalStaleComments}\n\n`;

  const allIssues = result.files.flatMap(f => f.issues.map(i => ({ ...i, file: f.file })));
  const highIssues = allIssues.filter(i => i.severity === 'high' || i.severity === 'medium');

  if (highIssues.length > 0) {
    report += '### Key Issues\n\n';
    for (const issue of highIssues.slice(0, 15)) {
      report += `- \`${issue.file}${issue.line ? ':' + issue.line : ''}\` — ${issue.description}\n`;
    }
    if (highIssues.length > 15) {
      report += `- _...and ${highIssues.length - 15} more_\n`;
    }
    report += '\n';
  }

  const sorted = [...result.files].filter(f => f.codeLines > 10).sort((a, b) => b.ratio - a.ratio);
  if (sorted.length > 0) {
    report += '### Comment Ratio by File\n\n';
    report += '| File | Code Lines | Comment % | Doc Coverage |\n';
    report += '|------|-----------|----------|-------------|\n';
    for (const f of sorted.slice(0, 15)) {
      const dc = f.docCoverage !== null ? f.docCoverage + '%' : '—';
      report += `| ${f.file} | ${f.codeLines} | ${f.ratio}% | ${dc} |\n`;
    }
    if (sorted.length > 15) {
      report += `| _...${sorted.length - 15} more_ | | | |\n`;
    }
    report += '\n';
  }

  return report;
}

/**
 * F56: Analyze async/concurrency patterns — detect async/await vs Promise chains
 * vs callbacks, missing awaits, floating promises, unhandled rejections, and
 * callback hell depth.
 */
export function analyzeAsyncPatterns(files = []) {
  const results = [];
  let totalAsyncFunctions = 0;
  let totalAwaitUsage = 0;
  let totalPromiseChains = 0;
  let totalCallbacks = 0;
  let totalFloatingPromises = 0;
  let totalMissingAwait = 0;
  let totalUnhandledRejections = 0;
  let totalCallbackHell = 0;

  const jsExtensions = new Set(['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.vue', '.svelte']);

  for (const file of files) {
    if (!file.content) continue;
    const ext = extname(file.path || '');
    if (!jsExtensions.has(ext)) continue;

    const lines = file.content.split('\n');
    const issues = [];
    let asyncFuncCount = 0;
    let awaitCount = 0;
    let promiseChainCount = 0;
    let callbackCount = 0;
    let floatingPromiseCount = 0;
    let missingAwaitCount = 0;
    let unhandledRejectionCount = 0;
    let callbackHellCount = 0;
    let callbackDepth = 0;

    for (let i = 0; i < lines.length; i++) {
      const trimmed = lines[i].trim();
      const lineNum = i + 1;

      // Track callback nesting depth (callback hell detection)
      const openCallback = (trimmed.match(/(?:=>|function\s*)\s*\{/g) || []).length;
      const closeCallback = (trimmed.match(/\}\s*\)/g) || []).length;

      // Check for callback hell BEFORE updating depth (depth from previous lines)
      if (callbackDepth >= 2 && /(err|callback|cb)/.test(trimmed)) {
        callbackHellCount++;
        issues.push({
          type: 'callback_hell',
          severity: 'medium',
          line: lineNum,
          description: `Deep callback nesting (depth: ${callbackDepth + 1}) — consider async/await`,
          snippet: trimmed.substring(0, 120),
        });
      }

      callbackDepth += openCallback - closeCallback;
      if (callbackDepth < 0) callbackDepth = 0;

      // Skip comments
      if (/^\/\//.test(trimmed) || /^\*/.test(trimmed) || /^#/.test(trimmed)) continue;

      // Async function declaration
      if (/\basync\s+(?:function\s*\*?|\(|\w)/.test(trimmed) || /\basync\s+function\b/.test(trimmed)) {
        asyncFuncCount++;
      }

      // Await usage
      const awaitMatches = trimmed.match(/\bawait\s+/g);
      if (awaitMatches) awaitCount += awaitMatches.length;

      // Promise chain (.then/.catch/.finally without await on same line)
      const thenMatches = trimmed.match(/\.then\s*\(/g);
      const catchMatches = trimmed.match(/\.catch\s*\(/g);
      const finallyMatches = trimmed.match(/\.finally\s*\(/g);
      const chainOnLine = (thenMatches || []).length + (catchMatches || []).length + (finallyMatches || []).length;
      if (chainOnLine > 0) {
        promiseChainCount += chainOnLine;
        // Check for unhandled rejection (no .catch in the chain)
        if (/\.then\s*\(/.test(trimmed) && !/\.catch\s*\(/.test(trimmed) && !/\.finally\s*\(/.test(trimmed)) {
          // Look ahead a few lines for .catch
          let hasCatch = false;
          for (let j = i + 1; j < Math.min(i + 10, lines.length); j++) {
            if (/\.catch\s*\(/.test(lines[j]) || /\.finally\s*\(/.test(lines[j])) {
              hasCatch = true;
              break;
            }
            // If we hit a new statement, stop
            if (/^\s*[\w$]/.test(lines[j]) && !/\.then\s*\(/.test(lines[j]) && !/^\s*\)/.test(lines[j]) && !/^\s*\}/.test(lines[j])) {
              break;
            }
          }
          if (!hasCatch) {
            unhandledRejectionCount++;
            issues.push({
              type: 'unhandled_rejection',
              severity: 'high',
              line: lineNum,
              description: 'Promise .then() chain without .catch() — potential unhandled rejection',
              snippet: trimmed.substring(0, 120),
            });
          }
        }
      }

      // new Promise without await/return
      if (/\bnew\s+Promise\s*\(/.test(trimmed) && !/\bawait\b/.test(trimmed) && !/\breturn\b/.test(trimmed)) {
        floatingPromiseCount++;
        issues.push({
          type: 'floating_promise',
          severity: 'medium',
          line: lineNum,
          description: 'Promise created but not awaited or returned — fire-and-forget',
          snippet: trimmed.substring(0, 120),
        });
      }

      // Missing await: calling a function known to return a promise without await
      // Pattern: function call ending in Async or matching a fetch() call without await
      if (/\bfetch\s*\(/.test(trimmed) && !/\bawait\s+fetch\b/.test(trimmed) && !/\breturn\s+fetch\b/.test(trimmed) && !/\.then\s*\(/.test(trimmed) && !/\.catch\s*\(/.test(trimmed)) {
        missingAwaitCount++;
        issues.push({
          type: 'missing_await',
          severity: 'high',
          line: lineNum,
          description: 'fetch() called without await — response will be a Promise, not Response',
          snippet: trimmed.substring(0, 120),
        });
      }

      // Functions ending in Async without await
      const asyncCallMatch = trimmed.match(/\b(\w*[Aa]sync\w*)\s*\(/);
      if (asyncCallMatch && !/\bawait\b/.test(trimmed) && !/\breturn\b/.test(trimmed) && !/\bnew\s+Promise\b/.test(trimmed) && !/^\s*(?:export\s+)?(?:async\s+)?(?:function|class|const|let|var)\s/.test(trimmed) && !/\basync\s+function\b/.test(trimmed)) {
        // Only flag clear cases: explicit Async naming convention
        const funcName = asyncCallMatch[1];
        if (/Async$/.test(funcName) || /async$/.test(funcName)) {
          missingAwaitCount++;
          issues.push({
            type: 'missing_await',
            severity: 'medium',
            line: lineNum,
            description: `'${funcName}()' appears to be async but called without await`,
            snippet: trimmed.substring(0, 120),
          });
        }
      }

      // Callback pattern: function passed as last arg (heuristic)
      if (/\bfunction\s*\(.*(?:err|error|callback|cb).*\)\s*\{/.test(trimmed) || /\(err,\s*(?:res|response|data|result|docs)\)\s*=>/.test(trimmed) || /,\s*function\s*\(/.test(trimmed)) {
        callbackCount++;
      }

      // Single-line callback hell: deeply nested on one line
      const arrowMatches = (trimmed.match(/=>/g) || []).length;
      const fnMatches = (trimmed.match(/function\s*\(/g) || []).length;
      const singleLineDepth = arrowMatches + fnMatches;
      if (singleLineDepth >= 3 && /(err|callback|cb)/.test(trimmed)) {
        callbackHellCount++;
        issues.push({
          type: 'callback_hell',
          severity: 'medium',
          line: lineNum,
          description: `Deep callback nesting (${singleLineDepth} inline) — consider async/await`,
          snippet: trimmed.substring(0, 120),
        });
      }
    }

    if (asyncFuncCount === 0 && awaitCount === 0 && promiseChainCount === 0 && callbackCount === 0 && floatingPromiseCount === 0 && missingAwaitCount === 0 && unhandledRejectionCount === 0 && callbackHellCount === 0) continue;

    results.push({
      file: file.path,
      asyncFunctions: asyncFuncCount,
      awaitUsage: awaitCount,
      promiseChains: promiseChainCount,
      callbacks: callbackCount,
      floatingPromises: floatingPromiseCount,
      missingAwaits: missingAwaitCount,
      unhandledRejections: unhandledRejectionCount,
      callbackHell: callbackHellCount,
      issues,
    });

    totalAsyncFunctions += asyncFuncCount;
    totalAwaitUsage += awaitCount;
    totalPromiseChains += promiseChainCount;
    totalCallbacks += callbackCount;
    totalFloatingPromises += floatingPromiseCount;
    totalMissingAwait += missingAwaitCount;
    totalUnhandledRejections += unhandledRejectionCount;
    totalCallbackHell += callbackHellCount;
  }

  // Health score calculation
  const totalIssues = totalFloatingPromises + totalMissingAwait + totalUnhandledRejections + totalCallbackHell;
  const hasAsyncCode = totalAsyncFunctions + totalAwaitUsage + totalPromiseChains + totalCallbacks + totalIssues;
  const asyncAdoption = totalAsyncFunctions > 0 ? Math.min(100, Math.round((totalAwaitUsage / totalAsyncFunctions) * 50)) : (hasAsyncCode > 0 ? 50 : 0);
  const issuePenalty = Math.min(80, totalIssues * 8);
  const chainRatio = (totalAsyncFunctions + totalPromiseChains) > 0 ? totalPromiseChains / (totalAsyncFunctions + totalPromiseChains) : 0;
  const chainPenalty = Math.round(chainRatio * 20); // Prefer async/await over .then chains
  const healthScore = hasAsyncCode === 0 ? 0 : Math.max(0, Math.round(asyncAdoption * 0.3 + (100 - issuePenalty) * 0.5 + (100 - chainPenalty) * 0.2));

  return {
    files: results,
    fileCount: results.length,
    totalAsyncFunctions,
    totalAwaitUsage,
    totalPromiseChains,
    totalCallbacks,
    totalFloatingPromises,
    totalMissingAwait,
    totalUnhandledRejections,
    totalCallbackHell,
    healthScore,
    grade: healthScore >= 90 ? 'A' : healthScore >= 75 ? 'B' : healthScore >= 60 ? 'C' : healthScore >= 40 ? 'D' : 'F',
  };
}

/**
 * F56: Format async patterns report as markdown.
 */
export function formatAsyncPatternsReport(result) {
  if (!result || result.fileCount === 0) {
    return '## Async Patterns Analysis\n\n⚠️ No async code detected.\n';
  }

  let report = '## Async Patterns Analysis\n\n';
  report += `**Health Grade:** ${result.grade} (${result.healthScore}/100)\n`;
  report += `**Async functions:** ${result.totalAsyncFunctions}\n`;
  report += `**Await calls:** ${result.totalAwaitUsage}\n`;
  report += `**Promise chains (.then):** ${result.totalPromiseChains}\n`;
  report += `**Callback patterns:** ${result.totalCallbacks}\n\n`;

  if (result.totalFloatingPromises > 0 || result.totalMissingAwait > 0 || result.totalUnhandledRejections > 0 || result.totalCallbackHell > 0) {
    report += '### Risk Summary\n\n';
    report += `| Issue | Count | Severity |\n`;
    report += `|-------|-------|----------|\n`;
    if (result.totalMissingAwait > 0) report += `| Missing await | ${result.totalMissingAwait} | High |\n`;
    if (result.totalUnhandledRejections > 0) report += `| Unhandled rejections | ${result.totalUnhandledRejections} | High |\n`;
    if (result.totalFloatingPromises > 0) report += `| Floating promises | ${result.totalFloatingPromises} | Medium |\n`;
    if (result.totalCallbackHell > 0) report += `| Callback hell | ${result.totalCallbackHell} | Medium |\n`;
    report += '\n';
  }

  const allIssues = result.files.flatMap(f => f.issues.map(i => ({ ...i, file: f.file })));
  const highIssues = allIssues.filter(i => i.severity === 'high');

  if (highIssues.length > 0) {
    report += '### Critical Issues\n\n';
    for (const issue of highIssues.slice(0, 15)) {
      report += `- \`${issue.file}:${issue.line}\` — ${issue.description}\n`;
      if (issue.snippet) report += `  \`\`${issue.snippet}\`\`\n`;
    }
    if (highIssues.length > 15) {
      report += `- _...and ${highIssues.length - 15} more_\n`;
    }
    report += '\n';
  }

  const sorted = [...result.files].sort((a, b) => b.issues.length - a.issues.length);
  if (sorted.length > 0) {
    report += '### Per-file Breakdown\n\n';
    report += '| File | Async Fn | Await | .then | Callbacks | Issues |\n';
    report += '|------|----------|-------|-------|-----------|--------|\n';
    for (const f of sorted.slice(0, 15)) {
      report += `| ${f.file} | ${f.asyncFunctions} | ${f.awaitUsage} | ${f.promiseChains} | ${f.callbacks} | ${f.issues.length} |\n`;
    }
    if (sorted.length > 15) {
      report += `| _...${sorted.length - 15} more_ | | | | | |\n`;
    }
    report += '\n';
  }

  return report;
}

/**
 * F57: Analyze export health — barrel files, re-export chains,
 * unused exports, export consistency (named vs default vs namespace).
 */
export function analyzeExportHealth(files = [], importData = null) {
  const results = [];
  let totalExports = 0;
  let totalReExports = 0;
  let totalBarrelFiles = 0;
  let totalUnusedExports = 0;
  let totalDefaultExports = 0;
  let totalNamedExports = 0;
  let totalNamespaceExports = 0;
  let totalCircularReExports = 0;

  // Collect all imported names across the project for unused-export detection
  const allImportedPaths = new Set();
  const allImportedNames = new Set();
  if (importData && importData.allImports) {
    for (const imp of importData.allImports) allImportedPaths.add(imp);
  }
  if (importData && importData.imports) {
    for (const [file, imps] of importData.imports.entries()) {
      for (const imp of imps) {
        allImportedPaths.add(imp.path || imp);
        if (imp.names) imp.names.forEach(n => allImportedNames.add(n));
      }
    }
  }

  const jsExtensions = new Set(['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx']);

  for (const file of files) {
    if (!file.content) continue;
    const ext = extname(file.path || '');
    if (!jsExtensions.has(ext)) continue;

    const content = file.content;
    const lines = content.split('\n');
    const issues = [];

    // Count export types
    const namedExports = [];
    let defaultExportCount = 0;
    let namespaceReExportCount = 0;
    const reExports = [];

    for (let i = 0; i < lines.length; i++) {
      const trimmed = lines[i].trim();

      // Skip comments
      if (/^\/\//.test(trimmed) || /^\*/.test(trimmed)) continue;

      // export { a, b, c } — named exports
      const namedMatch = trimmed.match(/^export\s+\{([^}]+)\}\s*(?:from\s+['"]([^'"]+)['"])?\s*;?$/);
      if (namedMatch) {
        const names = namedMatch[1].split(',').map(s => s.trim().split(/\s+as\s+/)[0].trim()).filter(Boolean);
        if (namedMatch[2]) {
          // Re-export from another module
          reExports.push({ line: i + 1, names, from: namedMatch[2] });
        } else {
          namedExports.push(...names.map(n => ({ name: n, line: i + 1 })));
        }
        continue;
      }

      // export * from '...' — namespace re-export
      const nsMatch = trimmed.match(/^export\s+\*\s*(?:as\s+(\w+))?\s+from\s+['"]([^'"]+)['"];?$/);
      if (nsMatch) {
        namespaceReExportCount++;
        reExports.push({ line: i + 1, names: nsMatch[1] ? [nsMatch[1]] : ['*'], from: nsMatch[2], namespace: true });
        continue;
      }

      // export default ...
      if (/^export\s+default\s/.test(trimmed)) {
        defaultExportCount++;
        continue;
      }

      // export function/const/class/let/var name
      const declMatch = trimmed.match(/^export\s+(?:async\s+)?(?:function\s*\*?|class|const|let|var)\s+(\w+)/);
      if (declMatch) {
        namedExports.push({ name: declMatch[1], line: i + 1 });
        continue;
      }
    }

    const totalFileReExports = reExports.length;
    const totalFileExports = namedExports.length + defaultExportCount + namespaceReExportCount + totalFileReExports;

    // Barrel file detection: file that only re-exports
    const isBarrelFile = totalFileReExports > 0 && totalFileExports === totalFileReExports && namedExports.length === 0;
    if (isBarrelFile) totalBarrelFiles++;

    // Unused export detection (heuristic: if export name not found in any import across project)
    let unusedCount = 0;
    const unusedNames = [];
    for (const exp of namedExports) {
      // Check if this export name appears in any import statement across the project
      if (allImportedNames.size > 0 && !allImportedNames.has(exp.name)) {
        // Also check if the file path itself is imported (module-level import)
        const basePath = (file.path || '').replace(/\.(js|mjs|cjs|ts|tsx|jsx)$/, '');
        const fileName = basePath.split('/').pop();
        if (!allImportedPaths.has(basePath) && !allImportedPaths.has('./' + fileName) && !allImportedPaths.has('../' + fileName)) {
          unusedCount++;
          unusedNames.push(exp.name);
        }
      }
    }

    if (unusedCount > 0 && unusedCount === namedExports.length && namedExports.length > 2) {
      issues.push({
        type: 'all_exports_unused',
        severity: 'high',
        line: 0,
        description: `All ${unusedCount} named exports appear unused across the project`,
        snippet: unusedNames.slice(0, 5).join(', ') + (unusedNames.length > 5 ? '...' : ''),
      });
    } else if (unusedCount > 0) {
      issues.push({
        type: 'unused_exports',
        severity: 'low',
        line: 0,
        description: `${unusedCount} export(s) appear unused: ${unusedNames.slice(0, 5).join(', ')}`,
        snippet: '',
      });
    }

    // Barrel file warning
    if (isBarrelFile && totalFileReExports > 3) {
      issues.push({
        type: 'large_barrel_file',
        severity: 'low',
        line: 0,
        description: `Large barrel file with ${totalFileReExports} re-exports — consider splitting or using direct imports`,
        snippet: '',
      });
    }

    // Mixed default + named exports (inconsistent API)
    if (defaultExportCount > 0 && namedExports.length > 0) {
      issues.push({
        type: 'mixed_export_style',
        severity: 'info',
        line: 0,
        description: `File has both default export and ${namedExports.length} named exports — consider using only one style`,
        snippet: '',
      });
    }

    // Multiple default exports (error)
    if (defaultExportCount > 1) {
      issues.push({
        type: 'multiple_defaults',
        severity: 'high',
        line: 0,
        description: `File has ${defaultExportCount} default exports — only one is allowed`,
        snippet: '',
      });
    }

    if (totalFileExports === 0) continue;

    results.push({
      file: file.path,
      namedExports: namedExports.length,
      defaultExports: defaultExportCount,
      namespaceReExports: namespaceReExportCount,
      reExports: totalFileReExports,
      totalExports: totalFileExports,
      isBarrelFile,
      unusedExports: unusedCount,
      issues,
    });

    totalExports += totalFileExports;
    totalReExports += totalFileReExports;
    totalUnusedExports += unusedCount;
    totalDefaultExports += defaultExportCount;
    totalNamedExports += namedExports.length;
    totalNamespaceExports += namespaceReExportCount;
  }

  // Health score
  const hasExports = totalExports > 0;
  const exportConsistency = totalNamedExports > 0 && totalDefaultExports === 0 ? 100 : totalDefaultExports > 0 && totalNamedExports === 0 ? 80 : 70;
  const unusedPenalty = Math.min(60, totalUnusedExports * 5);
  const barrelPenalty = Math.min(20, totalBarrelFiles * 3);
  const healthScore = !hasExports ? 0 : Math.max(0, Math.round(exportConsistency * 0.3 + (100 - unusedPenalty) * 0.5 + (100 - barrelPenalty) * 0.2));

  return {
    files: results,
    fileCount: results.length,
    totalExports,
    totalReExports,
    totalBarrelFiles,
    totalUnusedExports,
    totalDefaultExports,
    totalNamedExports,
    totalNamespaceExports,
    healthScore,
    grade: healthScore >= 90 ? 'A' : healthScore >= 75 ? 'B' : healthScore >= 60 ? 'C' : healthScore >= 40 ? 'D' : 'F',
  };
}

/**
 * F57: Format export health report as markdown.
 */
export function formatExportHealthReport(result) {
  if (!result || result.fileCount === 0) {
    return '## Export Health Analysis\n\n⚠️ No exports found.\n';
  }

  let report = '## Export Health Analysis\n\n';
  report += `**Health Grade:** ${result.grade} (${result.healthScore}/100)\n`;
  report += `**Total exports:** ${result.totalExports}\n`;
  report += `**Named exports:** ${result.totalNamedExports}\n`;
  report += `**Default exports:** ${result.totalDefaultExports}\n`;
  report += `**Namespace re-exports:** ${result.totalNamespaceExports}\n`;
  report += `**Re-exports:** ${result.totalReExports}\n`;
  report += `**Barrel files:** ${result.totalBarrelFiles}\n`;
  report += `**Unused exports:** ${result.totalUnusedExports}\n\n`;

  const allIssues = result.files.flatMap(f => f.issues.map(i => ({ ...i, file: f.file })));
  const highIssues = allIssues.filter(i => i.severity === 'high');

  if (highIssues.length > 0) {
    report += '### Critical Issues\n\n';
    for (const issue of highIssues.slice(0, 10)) {
      report += `- \`${issue.file}\` — ${issue.description}\n`;
    }
    report += '\n';
  }

  if (result.totalBarrelFiles > 0) {
    const barrels = result.files.filter(f => f.isBarrelFile);
    report += '### Barrel Files\n\n';
    for (const b of barrels) {
      report += `- \`${b.file}\` — ${b.reExports} re-exports\n`;
    }
    report += '\n';
  }

  const sorted = [...result.files].sort((a, b) => b.totalExports - a.totalExports);
  report += '### Per-file Breakdown\n\n';
  report += '| File | Named | Default | Re-exports | Barrel | Unused |\n';
  report += '|------|-------|---------|------------|--------|--------|\n';
  for (const f of sorted.slice(0, 20)) {
    report += `| ${f.file} | ${f.namedExports} | ${f.defaultExports} | ${f.reExports} | ${f.isBarrelFile ? '✅' : ''} | ${f.unusedExports} |\n`;
  }
  if (sorted.length > 20) {
    report += `| _...${sorted.length - 20} more_ | | | | | |\n`;
  }
  report += '\n';

  return report;
}

/**
 * F58: Analyze function metrics — function length, parameter count,
 * return statements, and overall function quality scoring.
 */
export function analyzeFunctionMetrics(files = []) {
  const results = [];
  let totalFunctions = 0;
  let totalLongFunctions = 0;
  let totalHighParamFunctions = 0;
  let totalArrowFunctions = 0;
  let totalAsyncFunctions = 0;
  let totalFunctionsNoReturn = 0;

  const jsExtensions = new Set(['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx']);
  const longThreshold = 50; // lines
  const paramThreshold = 5;

  for (const file of files) {
    if (!file.content) continue;
    const ext = extname(file.path || '');
    if (!jsExtensions.has(ext)) continue;

    const lines = file.content.split('\n');
    const functions = [];
    const issues = [];

    // Regex patterns for function detection
    const funcPatterns = [
      // function declaration: function name(a, b) {
      { regex: /^\s*(?:export\s+)?(?:async\s+)?function\s*\*?\s*(\w+)\s*\(([^)]*)\)/, type: 'declaration' },
      // function expression: const name = function(a, b) {
      { regex: /^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function\s*\*?\s*\(([^)]*)\)/, type: 'expression' },
      // arrow function: const name = (a, b) => {
      { regex: /^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>/, type: 'arrow' },
      // arrow without parens: const name = x => {
      { regex: /^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(\w+)\s*=>/, type: 'arrow' },
      // method shorthand: name(a, b) {
      { regex: /^\s+(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*\{/, type: 'method' },
    ];

    for (let i = 0; i < lines.length; i++) {
      const trimmed = lines[i];

      // Skip comments
      const stripped = trimmed.trim();
      if (/^\/\//.test(stripped) || /^\*/.test(stripped)) continue;

      let matched = false;
      for (const pattern of funcPatterns) {
        const match = trimmed.match(pattern.regex);
        if (!match) continue;

        matched = true;
        const name = match[1] || '<anonymous>';
        const paramsStr = match[2] || '';
        const isArrow = pattern.type === 'arrow';
        const isAsync = /\basync\b/.test(trimmed);

        // Parse params
        const params = paramsStr.split(',').map(p => p.trim()).filter(p => p && p !== '' && !/^\/\//.test(p));
        // Handle destructuring/rest as 1 param
        const paramCount = params.length;

        // Find function body end (matching braces)
        let braceCount = 0;
        let bodyStarted = false;
        let endLine = i;
        let returnCount = 0;
        let bodyLines = 0;

        for (let j = i; j < lines.length; j++) {
          const line = lines[j];
          for (const ch of line) {
            if (ch === '{') { braceCount++; bodyStarted = true; }
            if (ch === '}') braceCount--;
          }
          // Count returns (only after body starts)
          if (bodyStarted && j > i) {
            bodyLines++;
            const lineTrim = line.trim();
            // Count return statements (not inside strings/comments)
            if (/\breturn\b/.test(lineTrim) && !/^\/\//.test(lineTrim)) {
              returnCount++;
            }
          }
          if (bodyStarted && braceCount === 0) {
            endLine = j;
            break;
          }
          // Safety: if arrow without braces (single expression)
          if (isArrow && !line.includes('{') && j > i) {
            endLine = i;
            bodyLines = 1;
            returnCount = 0; // implicit return, no return statement
            break;
          }
        }

        const funcLength = endLine - i + 1;

        const fnInfo = {
          name,
          line: i + 1,
          params: paramCount,
          length: funcLength,
          returns: returnCount,
          isArrow,
          isAsync,
          type: pattern.type,
        };

        functions.push(fnInfo);

        // Flag issues
        if (funcLength > longThreshold) {
          issues.push({
            type: 'long_function',
            severity: 'medium',
            line: i + 1,
            description: `${name}() is ${funcLength} lines long (threshold: ${longThreshold})`,
            snippet: '',
          });
        }

        if (paramCount > paramThreshold) {
          issues.push({
            type: 'too_many_params',
            severity: 'medium',
            line: i + 1,
            description: `${name}() has ${paramCount} parameters (threshold: ${paramThreshold})`,
            snippet: paramsStr.substring(0, 80),
          });
        }

        // Functions with no return and > 20 lines might be doing too much
        if (returnCount === 0 && funcLength > 20 && !isAsync) {
          issues.push({
            type: 'no_return_long',
            severity: 'low',
            line: i + 1,
            description: `${name}() is ${funcLength} lines with no return statement`,
            snippet: '',
          });
        }

        break; // Only match first pattern per line
      }
    }

    if (functions.length === 0) continue;

    const longCount = functions.filter(f => f.length > longThreshold).length;
    const highParamCount = functions.filter(f => f.params > paramThreshold).length;
    const noReturnCount = functions.filter(f => f.returns === 0 && f.length > 20 && !f.isAsync).length;

    results.push({
      file: file.path,
      functionCount: functions.length,
      arrowFunctions: functions.filter(f => f.isArrow).length,
      asyncFunctions: functions.filter(f => f.isAsync).length,
      longFunctions: longCount,
      highParamFunctions: highParamCount,
      noReturnFunctions: noReturnCount,
      avgLength: functions.length > 0 ? Math.round(functions.reduce((s, f) => s + f.length, 0) / functions.length) : 0,
      maxLength: Math.max(...functions.map(f => f.length)),
      avgParams: functions.length > 0 ? parseFloat((functions.reduce((s, f) => s + f.params, 0) / functions.length).toFixed(1)) : 0,
      functions: functions.map(f => ({ name: f.name, line: f.line, params: f.params, length: f.length, returns: f.returns, isArrow: f.isArrow, isAsync: f.isAsync })),
      issues,
    });

    totalFunctions += functions.length;
    totalLongFunctions += longCount;
    totalHighParamFunctions += highParamCount;
    totalArrowFunctions += functions.filter(f => f.isArrow).length;
    totalAsyncFunctions += functions.filter(f => f.isAsync).length;
    totalFunctionsNoReturn += noReturnCount;
  }

  // Health score
  const hasFunctions = totalFunctions > 0;
  const longRatio = hasFunctions ? totalLongFunctions / totalFunctions : 0;
  const highParamRatio = hasFunctions ? totalHighParamFunctions / totalFunctions : 0;
  const longPenalty = Math.round(longRatio * 50);
  const paramPenalty = Math.round(highParamRatio * 30);
  const noReturnPenalty = Math.min(20, totalFunctionsNoReturn * 2);
  const healthScore = !hasFunctions ? 0 : Math.max(0, Math.round((100 - longPenalty - paramPenalty - noReturnPenalty)));

  return {
    files: results,
    fileCount: results.length,
    totalFunctions,
    totalLongFunctions,
    totalHighParamFunctions,
    totalArrowFunctions,
    totalAsyncFunctions,
    totalFunctionsNoReturn,
    healthScore,
    grade: healthScore >= 90 ? 'A' : healthScore >= 75 ? 'B' : healthScore >= 60 ? 'C' : healthScore >= 40 ? 'D' : 'F',
  };
}

/**
 * F58: Format function metrics report as markdown.
 */
export function formatFunctionMetricsReport(result) {
  if (!result || result.fileCount === 0) {
    return '## Function Metrics Analysis\n\n⚠️ No functions found.\n';
  }

  let report = '## Function Metrics Analysis\n\n';
  report += `**Health Grade:** ${result.grade} (${result.healthScore}/100)\n`;
  report += `**Total functions:** ${result.totalFunctions}\n`;
  report += `**Arrow functions:** ${result.totalArrowFunctions}\n`;
  report += `**Async functions:** ${result.totalAsyncFunctions}\n`;
  report += `**Long functions (>50 lines):** ${result.totalLongFunctions}\n`;
  report += `**High-parameter functions (>5):** ${result.totalHighParamFunctions}\n`;
  report += `**Long functions with no return:** ${result.totalFunctionsNoReturn}\n\n`;

  const allIssues = result.files.flatMap(f => f.issues.map(i => ({ ...i, file: f.file })));
  const mediumIssues = allIssues.filter(i => i.severity === 'medium' || i.severity === 'high');

  if (mediumIssues.length > 0) {
    report += '### Key Issues\n\n';
    for (const issue of mediumIssues.slice(0, 15)) {
      report += `- \`${issue.file}:${issue.line}\` — ${issue.description}\n`;
    }
    if (mediumIssues.length > 15) {
      report += `- _...and ${mediumIssues.length - 15} more_\n`;
    }
    report += '\n';
  }

  // Longest functions
  const allFns = result.files.flatMap(f => f.functions.map(fn => ({ ...fn, file: f.file })));
  const longest = [...allFns].sort((a, b) => b.length - a.length);
  if (longest.length > 0 && longest[0].length > 20) {
    report += '### Longest Functions\n\n';
    report += '| Function | File | Lines | Params | Returns |\n';
    report += '|----------|------|-------|--------|---------|\n';
    for (const fn of longest.slice(0, 15)) {
      if (fn.length < 15) break;
      report += `| ${fn.name}() | ${fn.file}:${fn.line} | ${fn.length} | ${fn.params} | ${fn.returns} |\n`;
    }
    report += '\n';
  }

  const sorted = [...result.files].sort((a, b) => b.functionCount - a.functionCount);
  report += '### Per-file Summary\n\n';
  report += '| File | Functions | Avg Length | Max Length | Avg Params | Issues |\n';
  report += '|------|-----------|------------|------------|------------|--------|\n';
  for (const f of sorted.slice(0, 20)) {
    report += `| ${f.file} | ${f.functionCount} | ${f.avgLength} | ${f.maxLength} | ${f.avgParams} | ${f.issues.length} |\n`;
  }
  if (sorted.length > 20) {
    report += `| _...${sorted.length - 20} more_ | | | | | |\n`;
  }
  report += '\n';

  return report;
}

export function analyzeCliHealth(files = []) {
  if (!files) files = [];
  const jsExtensions = new Set(['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx']);
  const cliFiles = [];
  let totalChecks = 0;
  let totalPassed = 0;
  let totalIssues = 0;

  const allChecks = [];

  for (const file of files) {
    if (!file.content) continue;
    const ext = extname(file.path || '');
    if (!jsExtensions.has(ext)) continue;

    // Identify CLI entry points: files with process.argv references or shebang
    const hasShebang = file.content.startsWith('#!');
    const hasProcessArgv = /process\.argv/.test(file.content);
    const hasCommander = /commander|yargs|meow|clipanion|inquirer/.test(file.content);
    const hasCliKeyword = /\bcli\b|\bcommand[\s-]?line/i.test(file.path || '');

    if (!hasShebang && !hasProcessArgv && !hasCommander && !hasCliKeyword) continue;

    const lines = file.content.split('\n');
    const issues = [];
    const passed = [];
    const checks = []
;
    const lineText = (n) => lines[n - 1] ? lines[n - 1].trim() : '';

    // 1. Help flag
    const helpFlag = lines.findIndex(l => /--help|-h\b/.test(l) && !/^\s*\/\//.test(l));
    if (helpFlag >= 0) {
      passed.push({ check: 'help_flag', line: helpFlag + 1 });
      checks.push({ name: 'help_flag', status: 'pass', line: helpFlag + 1 });
    } else {
      issues.push({ type: 'missing_help', severity: 'high', description: 'No --help or -h flag detected' });
      checks.push({ name: 'help_flag', status: 'fail' });
    }

    // 2. Version flag
    const versionFlag = lines.findIndex(l => /--version|-v\b/.test(l) && !/^\s*\/\//.test(l));
    if (versionFlag >= 0) {
      passed.push({ check: 'version_flag', line: versionFlag + 1 });
      checks.push({ name: 'version_flag', status: 'pass', line: versionFlag + 1 });
    } else {
      issues.push({ type: 'missing_version', severity: 'low', description: 'No --version or -v flag detected' });
      checks.push({ name: 'version_flag', status: 'fail' });
    }

    // 3. Usage/examples
    const hasUsage = lines.some(l => /usage:|examples?:|\$\s/.test(l));
    if (hasUsage) {
      passed.push({ check: 'usage_docs' });
      checks.push({ name: 'usage_docs', status: 'pass' });
    } else {
      issues.push({ type: 'missing_usage', severity: 'medium', description: 'No usage examples in CLI output' });
      checks.push({ name: 'usage_docs', status: 'fail' });
    }

    // 4. Error handling for arg parsing
    const hasArgValidation = lines.some(l => /invalid|missing.*argument|required.*arg|ValidationError|parseArgs/.test(l));
    if (hasArgValidation) {
      passed.push({ check: 'arg_validation' });
      checks.push({ name: 'arg_validation', status: 'pass' });
    } else {
      issues.push({ type: 'no_arg_validation', severity: 'medium', description: 'No argument validation detected' });
      checks.push({ name: 'arg_validation', status: 'fail' });
    }

    // 5. Exit codes
    const hasExitCode = lines.some(l => /process\.exit\s*\(\s*[1-9]/.test(l));
    if (hasExitCode) {
      passed.push({ check: 'error_exit_code' });
      checks.push({ name: 'error_exit_code', status: 'pass' });
    } else {
      issues.push({ type: 'no_error_exit', severity: 'medium', description: 'No non-zero exit code on errors' });
      checks.push({ name: 'error_exit_code', status: 'fail' });
    }

    // 6. Subcommand structure
    const hasSubcommands = lines.some(l => /command\s*\(|subcommand|action\s*[:=]|\.(command|subcommand)\b/.test(l));
    if (hasSubcommands) {
      passed.push({ check: 'subcommands' });
      checks.push({ name: 'subcommands', status: 'pass' });
    }

    // 7. Stderr usage for errors
    const hasStderr = lines.some(l => /process\.stderr|console\.error/.test(l));
    if (hasStderr) {
      passed.push({ check: 'stderr_errors' });
      checks.push({ name: 'stderr_errors', status: 'pass' });
    } else {
      issues.push({ type: 'no_stderr', severity: 'low', description: 'Errors may go to stdout instead of stderr' });
      checks.push({ name: 'stderr_errors', status: 'fail' });
    }

    // 8. Color/output formatting
    const hasColor = lines.some(l => /chalk|kleur|picocolors|\x1b\[|\\u001b\[/.test(l));
    if (hasColor) {
      passed.push({ check: 'color_output' });
      checks.push({ name: 'color_output', status: 'pass' });
    }

    const filePassed = passed.length;
    const fileChecks = checks.length;
    const fileScore = fileChecks > 0 ? Math.round((filePassed / fileChecks) * 100) : 0;

    let grade;
    if (fileScore >= 90) grade = 'A';
    else if (fileScore >= 75) grade = 'B';
    else if (fileScore >= 60) grade = 'C';
    else if (fileScore >= 40) grade = 'D';
    else grade = 'F';

    totalChecks += fileChecks;
    totalPassed += filePassed;
    totalIssues += issues.length;

    cliFiles.push({
      file: file.path,
      grade,
      score: fileScore,
      checks: fileChecks,
      passedChecks: passed,
      passedCount: filePassed,
      issues,
      isEntry: hasShebang || hasProcessArgv,
      framework: hasCommander ? 'commander/yargs' : 'manual',
    });

    allChecks.push(...checks.map(c => ({ ...c, file: file.path })));
  }

  const healthScore = totalChecks > 0 ? Math.round((totalPassed / totalChecks) * 100) : 0;
  let overallGrade;
  if (healthScore >= 90) overallGrade = 'A';
  else if (healthScore >= 75) overallGrade = 'B';
  else if (healthScore >= 60) overallGrade = 'C';
  else if (healthScore >= 40) overallGrade = 'D';
  else overallGrade = 'F';

  // Aggregate missing checks across all CLI files
  const missingChecks = {};
  for (const c of allChecks) {
    if (c.status === 'fail') {
      missingChecks[c.name] = (missingChecks[c.name] || 0) + 1;
    }
  }

  return {
    cliFileCount: cliFiles.length,
    healthScore,
    grade: overallGrade,
    totalChecks,
    totalPassed,
    totalIssues,
    missingChecks,
    files: cliFiles,
  };
}

export function formatCliHealthReport(result) {
  if (!result || result.cliFileCount === 0) {
    return '## CLI Health Analysis\n\n⚠️ No CLI entry points found.\n';
  }

  let report = '## CLI Health Analysis\n\n';
  report += `**Health Grade:** ${result.grade} (${result.healthScore}/100)\n`;
  report += `**CLI files:** ${result.cliFileCount}\n`;
  report += `**Checks passed:** ${result.totalPassed}/${result.totalChecks}\n\n`;

  if (result.totalIssues > 0) {
    report += '### Common Missing Features\n\n';
    const sorted = Object.entries(result.missingChecks).sort((a, b) => b[1] - a[1]);
    for (const [check, count] of sorted) {
      const label = check.replace(/_/g, ' ');
      report += `- **${label}** — missing in ${count} file(s)\n`;
    }
    report += '\n';
  }

  report += '### Per-file Breakdown\n\n';
  report += '| File | Grade | Score | Checks | Framework |\n';
  report += '|------|-------|-------|--------|-----------|\n';
  for (const f of [...result.files].sort((a, b) => a.score - b.score)) {
    report += `| ${f.file} | ${f.grade} | ${f.score}/100 | ${f.passed}/${f.checks} | ${f.framework} |\n`;
  }
  report += '\n';

  const worst = result.files.filter(f => f.issues.length > 0).sort((a, b) => a.score - b.score);
  if (worst.length > 0) {
    report += '### Issues\n\n';
    for (const f of worst.slice(0, 10)) {
      report += `**${f.file}** (${f.grade}):\n`;
      for (const issue of f.issues) {
        report += `  - [${issue.severity}] ${issue.description}\n`;
      }
      report += '\n';
    }
  }

  return report;
}

export function analyzeDependencyRisk(info = {}) {
  if (!info) info = {};
  const deps = { ...(info.dependencies || info.pkg?.dependencies || {}) };
  const devDeps = { ...(info.devDependencies || info.pkg?.devDependencies || {}) };
  const allDeps = [];
  for (const [name, version] of Object.entries(deps)) {
    allDeps.push({ name, version, type: 'prod' });
  }
  for (const [name, version] of Object.entries(devDeps)) {
    allDeps.push({ name, version, type: 'dev' });
  }

  const issues = [];
  let riskScore = 0;
  let maxScore = 0;
  const categories = {};

  // 1. Version pinning (0-25)
  maxScore += 25;
  let pinnedCount = 0;
  let caretCount = 0;
  let tildeCount = 0;
  let rangeCount = 0;
  let starCount = 0;
  const unpinnedDeps = [];

  for (const dep of allDeps) {
    const v = dep.version;
    if (/^\d+\.\d+\.\d+$/.test(v)) {
      pinnedCount++;
    } else if (/^\^/.test(v)) {
      caretCount++;
    } else if (/^~/.test(v)) {
      tildeCount++;
    } else if (/[<>]/.test(v)) {
      rangeCount++;
    } else if (/\*/.test(v)) {
      starCount++;
      unpinnedDeps.push(dep);
    } else {
      unpinnedDeps.push(dep);
    }
  }

  const totalDeps = allDeps.length;
  const pinRatio = totalDeps > 0 ? pinnedCount / totalDeps : 1;
  const wildcards = starCount;
  const pinScore = Math.round(pinRatio * 20) - (wildcards * 5);
  const clampedPinScore = Math.max(0, Math.min(25, pinScore));
  riskScore += clampedPinScore;

  categories.versionPinning = {
    score: clampedPinScore,
    max: 25,
    pinned: pinnedCount,
    caret: caretCount,
    tilde: tildeCount,
    range: rangeCount,
    wildcard: starCount,
    pinRatio: Math.round(pinRatio * 100) / 100,
  };

  if (starCount > 0) {
    issues.push({
      type: 'wildcard_versions',
      severity: 'critical',
      description: `${starCount} dependencies use wildcard (*) versions — unpredictable updates`,
      packages: unpinnedDeps.map(d => `${d.name}@${d.version}`),
    });
  }

  // 2. Dev-to-prod ratio (0-15)
  maxScore += 15;
  const prodCount = Object.keys(deps).length;
  const devOnlyCount = Object.keys(devDeps).length;
  const ratio = prodCount > 0 ? devOnlyCount / prodCount : 0;
  let ratioScore;
  if (ratio <= 3) ratioScore = 15;
  else if (ratio <= 5) ratioScore = 12;
  else if (ratio <= 8) ratioScore = 8;
  else if (ratio <= 12) ratioScore = 5;
  else ratioScore = 2;
  riskScore += ratioScore;

  categories.devProdRatio = {
    score: ratioScore,
    max: 15,
    prodCount,
    devCount: devOnlyCount,
    ratio: Math.round(ratio * 100) / 100,
  };

  if (ratio > 8) {
    issues.push({
      type: 'high_dev_ratio',
      severity: 'medium',
      description: `Dev dependencies outnumber prod ${devOnlyCount}:${prodCount} (ratio ${ratio.toFixed(1)}:1)`,
    });
  }

  // 3. Known risky patterns (0-25)
  maxScore += 25;
  const riskyPatterns = [
    { pattern: /eval|vm2|shelljs|exec-sync/, risk: 'code_execution', severity: 'high' },
    { pattern: /request|axios|node-fetch/, risk: 'http_client', severity: 'low' },
    { pattern: /lodash|underscore|moment/, risk: 'legacy_heavyweight', severity: 'medium' },
    { pattern: /babel|webpack|rollup|esbuild|vite/, risk: 'build_toolchain', severity: 'low' },
    { pattern: /typescript|ts-node|tsx/, risk: 'type_system', severity: 'low' },
  ];

  const flaggedDeps = [];
  let patternPenalty = 0;
  for (const dep of allDeps) {
    for (const { pattern, risk, severity } of riskyPatterns) {
      if (pattern.test(dep.name)) {
        flaggedDeps.push({ name: dep.name, risk, severity });
        if (severity === 'high') patternPenalty += 5;
        else if (severity === 'medium') patternPenalty += 2;
      }
    }
  }
  const riskPatternScore = Math.max(0, 25 - patternPenalty);
  riskScore += riskPatternScore;

  categories.riskyPatterns = {
    score: riskPatternScore,
    max: 25,
    flagged: flaggedDeps,
  };

  // 4. Duplicate functionality (0-15)
  maxScore += 15;
  const functionalityGroups = {
    testing: ['jest', 'mocha', 'vitest', 'ava', 'tape', 'jasmine', 'pytest'],
    linting: ['eslint', 'tslint', 'biome', 'standard', 'jshint'],
    formatting: ['prettier', 'dprint', 'standardjs'],
    http: ['express', 'fastify', 'koa', 'hapi', '@nestjs/core'],
    logging: ['winston', 'pino', 'bunyan', 'log4js', 'morgan'],
    validation: ['joi', 'zod', 'ajv', 'yup', 'class-validator'],
  };

  const duplicates = [];
  for (const [category, packages] of Object.entries(functionalityGroups)) {
    const found = allDeps.filter(d => packages.includes(d.name));
    if (found.length > 1) {
      duplicates.push({ category, packages: found.map(d => d.name) });
    }
  }
  const dupScore = Math.max(0, 15 - duplicates.length * 5);
  riskScore += dupScore;

  categories.duplicateFunctionality = {
    score: dupScore,
    max: 15,
    duplicates,
  };

  for (const dup of duplicates) {
    issues.push({
      type: 'duplicate_functionality',
      severity: 'low',
      description: `Multiple ${dup.category} packages: ${dup.packages.join(', ')}`,
    });
  }

  // 5. Zero-dependency check (0-20)
  maxScore += 20;
  const zeroDepScore = totalDeps === 0 ? 20 : totalDeps <= 5 ? 18 : totalDeps <= 15 ? 14 : totalDeps <= 30 ? 10 : totalDeps <= 50 ? 6 : 3;
  riskScore += zeroDepScore;

  categories.dependencyCount = {
    score: zeroDepScore,
    max: 20,
    total: totalDeps,
    prod: prodCount,
    dev: devOnlyCount,
  };

  if (totalDeps > 50) {
    issues.push({
      type: 'excessive_deps',
      severity: 'medium',
      description: `${totalDeps} total dependencies — consider reducing`,
    });
  }

  const finalScore = maxScore > 0 ? Math.round((riskScore / maxScore) * 100) : 100;
  let grade;
  if (finalScore >= 90) grade = 'A';
  else if (finalScore >= 75) grade = 'B';
  else if (finalScore >= 60) grade = 'C';
  else if (finalScore >= 40) grade = 'D';
  else grade = 'F';

  return {
    riskScore: finalScore,
    grade,
    totalDependencies: totalDeps,
    prodDependencies: prodCount,
    devDependencies: devOnlyCount,
    categories,
    issues,
    flaggedCount: flaggedDeps.length,
    duplicateCount: duplicates.length,
  };
}

export function formatDependencyRiskReport(result) {
  if (!result) return '## Dependency Risk Analysis\n\n⚠️ No dependency data.\n';

  let report = '## Dependency Risk Analysis\n\n';
  report += `**Risk Grade:** ${result.grade} (${result.riskScore}/100)\n`;
  report += `**Total dependencies:** ${result.totalDependencies} (${result.prodDependencies} prod, ${result.devDependencies} dev)\n`;
  report += `**Flagged:** ${result.flaggedCount} • **Duplicate categories:** ${result.duplicateCount}\n\n`;

  const catLabels = {
    versionPinning: 'Version Pinning',
    devProdRatio: 'Dev/Prod Ratio',
    riskyPatterns: 'Risky Patterns',
    duplicateFunctionality: 'Duplicate Functionality',
    dependencyCount: 'Dependency Count',
  };

  report += '### Risk Categories\n\n';
  report += '| Category | Score | Key Metrics |\n';
  report += '|----------|-------|-------------|\n';
  for (const [key, cat] of Object.entries(result.categories)) {
    const label = catLabels[key] || key;
    let metrics = '';
    if (key === 'versionPinning') metrics = `${cat.pinned} pinned, ${cat.wildcard} wildcard`;
    else if (key === 'devProdRatio') metrics = `${cat.prod} prod : ${cat.dev} dev`;
    else if (key === 'riskyPatterns') metrics = `${cat.flagged.length} flagged`;
    else if (key === 'duplicateFunctionality') metrics = `${cat.duplicates.length} duplicates`;
    else if (key === 'dependencyCount') metrics = `${cat.total} total`;
    report += `| ${label} | ${cat.score}/${cat.max} | ${metrics} |\n`;
  }
  report += '\n';

  if (result.issues.length > 0) {
    report += '### Issues\n\n';
    const sorted = [...result.issues].sort((a, b) => {
      const order = { critical: 0, high: 1, medium: 2, low: 3 };
      return (order[a.severity] || 9) - (order[b.severity] || 9);
    });
    for (const issue of sorted) {
      report += `- **[${issue.severity}]** ${issue.description}\n`;
    }
    report += '\n';
  }

  return report;
}

export function analyzeTestCoverage(files = [], options = {}) {
  if (!files) files = [];
  const srcExtensions = new Set(['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.py', '.go', '.rs', '.java']);
  const testPatterns = [
    /\.test\./i,
    /\.spec\./i,
    /\.bench\./i,
    /^test\//i,
    /\/__tests__\//i,
    /_test\./i,
    /_spec\./i,
    /Test\.(java|go)$/i,
    /^test_.*\.py$/i,
    /.*_test\.py$/i,
  ];

  const frameworks = {
    jest: /from\s+['"]jest['"]|require\(['"]jest['"]\)|describe\s*\(|it\s*\(|test\s*\(/,
    mocha: /from\s+['"]mocha['"]|describe\s*\(|it\s*\(/,
    vitest: /from\s+['"]vitest['"]|import.*vitest/,
    node_test: /from\s+['"]node:test['"]|import.*node:test/,
    pytest: /import pytest|def test_|assert /,
    go_test: /func Test\w+/,
    cargo_test: /#\[cfg\(test\)\]|#\[test\]/,
    ava: /import test from ['"]ava['"]/,
    tape: /require\(['"]tape['"]\)/,
  };

  const sourceFiles = [];
  const testFiles = [];

  for (const file of files) {
    if (!file.path) continue;
    const ext = extname(file.path);
    if (!srcExtensions.has(ext)) continue;

    const isTest = testPatterns.some(p => p.test(file.path));

    if (isTest) {
      testFiles.push({ path: file.path, content: file.content || '', ext });
    } else {
      sourceFiles.push({ path: file.path, content: file.content || '', ext });
    }
  }

  // Detect frameworks
  const detectedFrameworks = new Set();
  for (const tf of testFiles) {
    for (const [name, pattern] of Object.entries(frameworks)) {
      if (pattern.test(tf.content)) {
        detectedFrameworks.add(name);
      }
    }
  }

  // Map test files to source files
  const mappings = [];
  const testedSources = new Set();

  for (const tf of testFiles) {
    // Derive source name from test name
    const baseName = tf.path
      .replace(/\.test\./i, '.')
      .replace(/\.spec\./i, '.')
      .replace(/\.bench\./i, '.')
      .replace(/_test\./i, '.')
      .replace(/_spec\./i, '.')
      .replace(/\/__tests__\//, '/')
      .replace(/^test\//, 'src/')
      .replace(/^tests\//, 'src/')
      .replace(/Test\.(java|go)$/, '.$1', 'i')
      .replace(/^test_(.*)\.py$/i, '$1.py')
      .replace(/(.*)_test\.py$/i, '$1.py');

    // Find matching source file
    const matchedSource = sourceFiles.find(sf => sf.path === baseName || sf.path.endsWith(baseName.replace(/^.*\//, '')));
    if (matchedSource) {
      mappings.push({ test: tf.path, source: matchedSource.path });
      testedSources.add(matchedSource.path);
    } else {
      mappings.push({ test: tf.path, source: null });
    }
  }

  // Find untested source files
  const untested = sourceFiles
    .filter(sf => !testedSources.has(sf.path))
    .map(sf => sf.path);

  // Calculate metrics
  const testCount = testFiles.length;
  const sourceCount = sourceFiles.length;
  const testedCount = testedSources.size;
  const untestedCount = untested.length;
  const coverageRatio = sourceCount > 0 ? testedCount / sourceCount : 0;
  const testToSourceRatio = sourceCount > 0 ? testCount / sourceCount : 0;

  // Score calculation (0-100)
  let score = 0;
  // Coverage component (0-60)
  score += Math.round(coverageRatio * 60);
  // Framework detection (0-15)
  score += detectedFrameworks.size > 0 ? 15 : 0;
  // Test-to-source ratio (0-25)
  if (testToSourceRatio >= 0.8) score += 25;
  else if (testToSourceRatio >= 0.5) score += 18;
  else if (testToSourceRatio >= 0.3) score += 12;
  else if (testToSourceRatio >= 0.1) score += 6;

  let grade;
  if (score >= 90) grade = 'A';
  else if (score >= 75) grade = 'B';
  else if (score >= 60) grade = 'C';
  else if (score >= 40) grade = 'D';
  else grade = 'F';

  // Identify critical untested files (large source files)
  const untestedWithSize = untested.map(p => {
    const sf = sourceFiles.find(s => s.path === p);
    const lines = sf ? sf.content.split('\n').length : 0;
    return { path: p, lines };
  }).sort((a, b) => b.lines - a.lines);

  const issues = [];
  if (untestedCount > 0 && sourceCount > 0) {
    const untestedPct = Math.round((untestedCount / sourceCount) * 100);
    if (untestedPct > 50) {
      issues.push({
        type: 'low_coverage',
        severity: 'high',
        description: `${untestedPct}% of source files (${untestedCount}/${sourceCount}) have no corresponding test file`,
      });
    } else if (untestedPct > 25) {
      issues.push({
        type: 'moderate_coverage',
        severity: 'medium',
        description: `${untestedPct}% of source files (${untestedCount}/${sourceCount}) untested`,
      });
    }
  }

  if (detectedFrameworks.size === 0 && testCount > 0) {
    issues.push({
      type: 'unknown_framework',
      severity: 'low',
      description: 'Test files found but no known testing framework detected',
    });
  }

  return {
    grade,
    score,
    testFileCount: testCount,
    sourceFileCount: sourceCount,
    testedCount,
    untestedCount,
    coverageRatio: Math.round(coverageRatio * 100) / 100,
    testToSourceRatio: Math.round(testToSourceRatio * 100) / 100,
    frameworks: [...detectedFrameworks],
    mappings,
    untested: untestedWithSize.slice(0, 20),
    issues,
  };
}

export function formatTestCoverageReport(result) {
  if (!result) return '## Test Coverage Analysis\n\n⚠️ No file data.\n';

  let report = '## Test Coverage Analysis\n\n';
  report += `**Grade:** ${result.grade} (${result.score}/100)\n`;
  report += `**Test files:** ${result.testFileCount}\n`;
  report += `**Source files:** ${result.sourceFileCount}\n`;
  report += `**Tested:** ${result.testedCount} (${Math.round(result.coverageRatio * 100)}%)\n`;
  report += `**Frameworks:** ${result.frameworks.length > 0 ? result.frameworks.join(', ') : 'none detected'}\n\n`;

  if (result.issues.length > 0) {
    report += '### Issues\n\n';
    for (const issue of result.issues) {
      report += `- **[${issue.severity}]** ${issue.description}\n`;
    }
    report += '\n';
  }

  if (result.untested.length > 0) {
    report += '### Untested Source Files\n\n';
    report += '| File | Lines |\n';
    report += '|------|-------|\n';
    for (const f of result.untested.slice(0, 15)) {
      report += `| ${f.path} | ${f.lines} |\n`;
    }
    if (result.untested.length > 15) {
      report += `| _...and ${result.untested.length - 15} more_ | |\n`;
    }
    report += '\n';
  }

  if (result.mappings.length > 0) {
    report += '### Test → Source Mappings\n\n';
    for (const m of result.mappings.slice(0, 15)) {
      const target = m.source || '⚠️ no match';
      report += `- ${m.test} → ${target}\n`;
    }
    if (result.mappings.length > 15) {
      report += `- _...and ${result.mappings.length - 15} more_\n`;
    }
    report += '\n';
  }

  return report;
}


// ── F62: Logging Health ─────────────────────────────────────────────

export function analyzeLoggingHealth(files = []) {
  if (!files) files = [];
  const jsExtensions = new Set(['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx']);
  const allIssues = [];
  const fileResults = [];
  let totalConsoleLog = 0;
  let totalConsoleWarn = 0;
  let totalConsoleError = 0;
  let totalConsoleInfo = 0;
  let totalConsoleDebug = 0;
  let totalCatchWithoutLog = 0;
  let totalFiles = 0;

  for (const file of files) {
    if (!file.content) continue;
    const ext = extname(file.path || '');
    if (!jsExtensions.has(ext)) continue;

    // Skip test files
    if (/\.test\.|\.spec\.|__tests__|(?:^|\/)tests?\//.test(file.path || '')) continue;

    totalFiles++;
    const lines = file.content.split('\n');
    const issues = [];
    let consoleLogCount = 0;
    let consoleWarnCount = 0;
    let consoleErrorCount = 0;
    let consoleInfoCount = 0;
    let consoleDebugCount = 0;
    let catchWithoutLogCount = 0;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();

      // Skip comments
      if (/^\/\//.test(trimmed) || /^\*/.test(trimmed)) continue;

      // Detect console.* calls
      const consoleLogMatch = /console\.log\s*\(/.exec(trimmed);
      const consoleWarnMatch = /console\.warn\s*\(/.exec(trimmed);
      const consoleErrorMatch = /console\.error\s*\(/.exec(trimmed);
      const consoleInfoMatch = /console\.info\s*\(/.exec(trimmed);
      const consoleDebugMatch = /console\.debug\s*\(/.exec(trimmed);

      if (consoleLogMatch) {
        consoleLogCount++;
        totalConsoleLog++;
        issues.push({
          line: i + 1,
          type: 'console_log',
          severity: 'medium',
          description: `console.log in production code`,
          code: trimmed.substring(0, 100),
        });
      }

      if (consoleWarnMatch) {
        consoleWarnCount++;
        totalConsoleWarn++;
      }
      if (consoleErrorMatch) {
        consoleErrorCount++;
        totalConsoleError++;
      }
      if (consoleInfoMatch) {
        consoleInfoCount++;
        totalConsoleInfo++;
      }
      if (consoleDebugMatch) {
        consoleDebugCount++;
        totalConsoleDebug++;
      }

      // Detect catch blocks without logging
      const catchMatch = /\}\s*catch\s*\(|^catch\s*\(/.exec(trimmed);
      if (catchMatch || /^catch\s*\(/.test(trimmed)) {
        // Look ahead 1-5 lines for a console.* or log.* or logger.* call
        const catchIdx = trimmed.indexOf('catch');
        const restOfLine = catchIdx >= 0 ? trimmed.substring(catchIdx) : trimmed;
        const lookAhead = restOfLine + '\n' + lines.slice(i + 1, Math.min(i + 6, lines.length)).join('\n')
        if (!/console\.|log(?:ger|ging)?\.|\bwinston\b|\bpino\b|\bbunyan\b|\bdebug\b/.test(lookAhead)) {
          catchWithoutLogCount++;
          totalCatchWithoutLog++;
          issues.push({
            line: i + 1,
            type: 'catch_without_log',
            severity: 'high',
            description: 'catch block without any error logging',
            code: trimmed.substring(0, 100),
          });
        }
      }
    }

    if (consoleLogCount > 0 || catchWithoutLogCount > 0 || consoleWarnCount > 0 || consoleErrorCount > 0) {
      fileResults.push({
        path: file.path,
        consoleLogCount,
        consoleWarnCount,
        consoleErrorCount,
        consoleInfoCount,
        consoleDebugCount,
        catchWithoutLogCount,
        issues,
      });
    }
  }

  // Calculate score
  // Deduct: console.log = 3pts each, catch_without_log = 5pts each
  const deductions = totalConsoleLog * 3 + totalCatchWithoutLog * 5;
  const score = Math.max(0, 100 - deductions);

  let grade;
  if (score >= 90) grade = 'A';
  else if (score >= 80) grade = 'B';
  else if (score >= 70) grade = 'C';
  else if (score >= 60) grade = 'D';
  else grade = 'F';

  return {
    grade,
    score,
    totalFiles,
    summary: {
      consoleLog: totalConsoleLog,
      consoleWarn: totalConsoleWarn,
      consoleError: totalConsoleError,
      consoleInfo: totalConsoleInfo,
      consoleDebug: totalConsoleDebug,
      catchWithoutLog: totalCatchWithoutLog,
    },
    files: fileResults,
    issues: allIssues,
  };
}

export function formatLoggingHealthReport(result) {
  if (!result) return '## Logging Health Analysis\n\n⚠️ No file data.\n';

  let report = '## Logging Health Analysis\n\n';
  report += `**Grade:** ${result.grade} (${result.score}/100)\n`;
  report += `**Files analyzed:** ${result.totalFiles}\n\n`;

  const s = result.summary;
  report += '### Summary\n\n';
  report += `| Metric | Count |\n`;
  report += `|--------|-------|\n`;
  report += `| console.log | ${s.consoleLog} |\n`;
  report += `| console.warn | ${s.consoleWarn} |\n`;
  report += `| console.error | ${s.consoleError} |\n`;
  report += `| console.info | ${s.consoleInfo} |\n`;
  report += `| console.debug | ${s.consoleDebug} |\n`;
  report += `| catch without log | ${s.catchWithoutLog} |\n\n`;

  if (result.files.length > 0) {
    report += '### Files with Issues\n\n';
    for (const f of result.files.slice(0, 15)) {
      report += `**${f.path}** — ${f.issues.length} issue(s)\n`;
      for (const issue of f.issues.slice(0, 5)) {
        report += `  - L${issue.line}: [${issue.severity}] ${issue.description}\n`;
      }
      if (f.issues.length > 5) {
        report += `  - _...and ${f.issues.length - 5} more_\n`;
      }
      report += '\n';
    }
    if (result.files.length > 15) {
      report += `_...and ${result.files.length - 15} more files_\n\n`;
    }
  }

  return report;
}


// ── F64: Performance Anti-Patterns ──────────────────────────────────

export function analyzePerformancePatterns(files = []) {
  if (!files) files = [];
  const jsExtensions = new Set(['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx']);
  const allIssues = [];
  const fileResults = [];
  let totalSyncIO = 0;
  let totalNestedLoops = 0;
  let totalPromiseInLoop = 0;
  let totalMissingAwait = 0;
  let totalUnboundedOps = 0;
  let totalFiles = 0;

  for (const file of files) {
    if (!file.content) continue;
    const ext = extname(file.path || '');
    if (!jsExtensions.has(ext)) continue;
    if (/\.test\.|\.spec\.|__tests__|(?:^|\/)tests?\//.test(file.path || '')) continue;

    totalFiles++;
    const lines = file.content.split('\n');
    const issues = [];
    let syncIOCount = 0;
    let nestedLoopCount = 0;
    let promiseInLoopCount = 0;
    let missingAwaitCount = 0;
    let unboundedOpsCount = 0;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();
      if (/^\/\//.test(trimmed) || /^\*/.test(trimmed)) continue;

      // 1. Sync I/O: readFileSync, writeFileSync, execSync, existsSync
      if (/\b(?:readFileSync|writeFileSync|appendFileSync|execSync|spawnSync|existsSync|statSync|readdirSync)\b/.test(trimmed)) {
        syncIOCount++;
        totalSyncIO++;
        issues.push({
          line: i + 1,
          type: 'sync_io',
          severity: 'medium',
          description: 'Synchronous I/O call blocks event loop',
          code: trimmed.substring(0, 100),
        });
      }

      // 2. Nested loops (for/while/forEach/map/filter inside another)
      // Detect: line with loop keyword, and previous non-blank line also has loop keyword
      const isLoop = /\b(?:for|while|forEach|\.map|\.filter|\.reduce|\.some|\.every)\b/.test(trimmed);
      if (isLoop && i > 0) {
        // Look back up to 10 lines for matching indentation + loop
        let lookBack = i - 1;
        let depth = 0;
        while (lookBack >= 0 && lookBack >= i - 15) {
          const prevLine = lines[lookBack].trim();
          if (prevLine === '' || /^\/\//.test(prevLine)) { lookBack--; continue; }
          // Check if previous line is a loop at a lower or equal indentation
          if (/\b(?:for|while|forEach|\.map|\.filter|\.reduce)\b/.test(prevLine)) {
            nestedLoopCount++;
            totalNestedLoops++;
            issues.push({
              line: i + 1,
              type: 'nested_loop',
              severity: 'low',
              description: 'Nested loop detected — potential O(n²) complexity',
              code: trimmed.substring(0, 100),
            });
            break;
          }
          depth++;
          if (depth > 5) break;
          lookBack--;
        }
      }

      // 3. Promise creation inside loop (anti-pattern for sequential async)
      if (/\b(?:for|while|forEach)\b/.test(trimmed)) {
        // Look ahead 1-5 lines for `new Promise` or `.then(` or `await fetch`
        const lookAhead = lines.slice(i + 1, Math.min(i + 6, lines.length)).join('\n');
        if (/new Promise|\.then\s*\(|await\s+fetch\s*\(/.test(lookAhead)) {
          // Only flag if it's inside the loop body (indented more)
          promiseInLoopCount++;
          totalPromiseInLoop++;
          issues.push({
            line: i + 1,
            type: 'promise_in_loop',
            severity: 'medium',
            description: 'Async operation inside loop — consider Promise.all for parallelism',
            code: trimmed.substring(0, 100),
          });
        }
      }

      // 4. Missing await (async function call without await)
      // Detect: function call that returns promise but no await
      const asyncCallNoAwait = /^(?:const|let|var)\s+\w+\s*=\s*(?!await\b)(\w+\.(?:fetch|axios|get|post|put|delete|save|find|findOne|update|create|destroy)\b)/.exec(trimmed);
      if (asyncCallNoAwait) {
        missingAwaitCount++;
        totalMissingAwait++;
        issues.push({
          line: i + 1,
          type: 'missing_await',
          severity: 'high',
          description: 'Possible missing await on async operation',
          code: trimmed.substring(0, 100),
        });
      }

      // 5. Unbounded operations: .map/.filter without length limit on potentially large arrays
      const unboundedMatch = /\.(?:map|filter|reduce|forEach|flat|flatMap)\s*\(/.exec(trimmed);
      if (unboundedMatch && /\.(?:querySelectorAll|getElementsByTagName|readdir|readdirSync)\s*\(/.test(trimmed)) {
        unboundedOpsCount++;
        totalUnboundedOps++;
        issues.push({
          line: i + 1,
          type: 'unbounded_operation',
          severity: 'low',
          description: 'Unbounded array operation on potentially large result set',
          code: trimmed.substring(0, 100),
        });
      }
    }

    if (issues.length > 0) {
      fileResults.push({
        path: file.path,
        syncIOCount,
        nestedLoopCount,
        promiseInLoopCount,
        missingAwaitCount,
        unboundedOpsCount,
        issues,
      });
    }
  }

  // Score: sync_io=3, nested_loop=1, promise_in_loop=4, missing_await=5, unbounded=1
  const deductions = totalSyncIO * 3 + totalNestedLoops * 1 + totalPromiseInLoop * 4 + totalMissingAwait * 5 + totalUnboundedOps * 1;
  const score = Math.max(0, 100 - deductions);

  let grade;
  if (score >= 90) grade = 'A';
  else if (score >= 80) grade = 'B';
  else if (score >= 70) grade = 'C';
  else if (score >= 60) grade = 'D';
  else grade = 'F';

  return {
    grade,
    score,
    totalFiles,
    summary: {
      syncIO: totalSyncIO,
      nestedLoops: totalNestedLoops,
      promiseInLoop: totalPromiseInLoop,
      missingAwait: totalMissingAwait,
      unboundedOps: totalUnboundedOps,
    },
    files: fileResults,
  };
}

export function formatPerformanceReport(result) {
  if (!result) return '## Performance Patterns Analysis\n\nNo data.\n';

  let report = '## Performance Patterns Analysis\n\n';
  report += `**Grade:** ${result.grade} (${result.score}/100)\n`;
  report += `**Files analyzed:** ${result.totalFiles}\n\n`;

  const s = result.summary;
  report += '### Summary\n\n';
  report += '| Pattern | Count |\n';
  report += '|---------|-------|\n';
  report += `| Sync I/O | ${s.syncIO} |\n`;
  report += `| Nested Loops | ${s.nestedLoops} |\n`;
  report += `| Promise in Loop | ${s.promiseInLoop} |\n`;
  report += `| Missing Await | ${s.missingAwait} |\n`;
  report += `| Unbounded Ops | ${s.unboundedOps} |\n\n`;

  if (result.files.length > 0) {
    report += '### Files with Issues\n\n';
    for (const f of result.files.slice(0, 15)) {
      report += `**${f.path}** — ${f.issues.length} issue(s)\n`;
      for (const issue of f.issues.slice(0, 5)) {
        report += `  - L${issue.line}: [${issue.severity}] ${issue.description}\n`;
      }
      if (f.issues.length > 5) {
        report += `  - _...and ${f.issues.length - 5} more_\n`;
      }
      report += '\n';
    }
  }

  return report;
}

// ─── F65: Type Safety Analysis ─────────────────────────────────────────

export function analyzeTypeSafety(files = []) {
  const tsExtensions = new Set(['.ts', '.tsx']);
  const tsFiles = files.filter(f => {
    const ext = f.path.slice(f.path.lastIndexOf('.'));
    return tsExtensions.has(ext);
  });

  let totalAny = 0;
  let totalImplicitAny = 0;
  let totalTsIgnore = 0;
  let totalTsNocheck = 0;
  let totalTsExpectError = 0;
  let totalTypeAssertions = 0;
  let totalMissingReturnType = 0;
  let totalNonNullAssertions = 0;

  const fileResults = [];

  for (const file of tsFiles) {
    const issues = [];
    const lines = file.content.split('\n');

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const lineNum = i + 1;

      // @ts-nocheck
      if (/\/\/\s*@ts-nocheck/.test(line) || /\/\*\s*@ts-nocheck/.test(line)) {
        issues.push({ line: lineNum, severity: 'high', description: '@ts-nocheck disables type checking for entire file' });
        totalTsNocheck++;
      }

      // @ts-ignore
      if (/\/\/\s*@ts-ignore/.test(line)) {
        issues.push({ line: lineNum, severity: 'high', description: '@ts-ignore suppresses type error' });
        totalTsIgnore++;
      }

      // @ts-expect-error
      if (/\/\/\s*@ts-expect-error/.test(line)) {
        issues.push({ line: lineNum, severity: 'medium', description: '@ts-expect-error suppresses type error' });
        totalTsExpectError++;
      }

      // Explicit `: any` annotations
      const anyMatches = line.match(/:\s*any\b/g);
      if (anyMatches) {
        for (const _ of anyMatches) {
          issues.push({ line: lineNum, severity: 'high', description: "Explicit 'any' type annotation" });
          totalAny++;
        }
      }

      // `as any` assertions
      const asAnyMatches = line.match(/\bas\s+any\b/g);
      if (asAnyMatches) {
        for (const _ of asAnyMatches) {
          issues.push({ line: lineNum, severity: 'high', description: "'as any' type assertion" });
          totalTypeAssertions++;
          totalAny++;
        }
      }

      // `as Type` assertions (non-any)
      const asMatches = line.match(/\bas\s+[a-zA-Z_]\w*/g);
      if (asMatches) {
        for (const m of asMatches) {
          if (!/\bas\s+any/.test(m)) {
            issues.push({ line: lineNum, severity: 'low', description: `Type assertion (${m})` });
            totalTypeAssertions++;
          }
        }
      }

      // Angle-bracket assertions <Type>expr (heuristic: <string>, <number>, etc.)
      const angleMatches = line.match(/<(string|number|boolean|any|unknown|object|never|void)\s*>/g);
      if (angleMatches) {
        for (const m of angleMatches) {
          issues.push({ line: lineNum, severity: m.includes('any') ? 'high' : 'low', description: `Angle-bracket type assertion ${m}` });
          totalTypeAssertions++;
        }
      }

      // Non-null assertion `!.` (but not `!==` and not `!` at end of expression as negation)
      const nonNullMatches = line.match(/\w\!\./g);
      if (nonNullMatches) {
        for (const _ of nonNullMatches) {
          issues.push({ line: lineNum, severity: 'medium', description: 'Non-null assertion (!) — consider optional chaining' });
          totalNonNullAssertions++;
        }
      }

      // Implicit any: function parameter without type annotation
      // Match: function foo(param) or function foo(param, other) — param has no `: Type`
      const funcParamMatches = line.match(/function\s+\w+\s*\(([^)]*)\)/g);
      if (funcParamMatches) {
        for (const fpm of funcParamMatches) {
          const paramsStr = fpm.match(/\(([^)]*)\)/)[1];
          if (paramsStr.trim()) {
            const params = paramsStr.split(',');
            for (const param of params) {
              const trimmed = param.trim();
              if (!trimmed) continue;
              // Skip destructuring, rest params, typed params, default values with type
              if (trimmed.startsWith('{') || trimmed.startsWith('...') || trimmed.startsWith('[')) continue;
              if (/:\s*\w/.test(trimmed)) continue; // has type annotation
              // Remove default value
              const paramName = trimmed.split('=')[0].trim();
              if (paramName && !/^(@|\/\/)/.test(paramName)) {
                issues.push({ line: lineNum, severity: 'medium', description: `Implicit any: parameter '${paramName}' has no type annotation` });
                totalImplicitAny++;
              }
            }
          }
        }
      }

      // Arrow function implicit any params: (param) => or (param, x) =>
      const arrowMatches = line.match(/\(([^)]*)\)\s*=>/g);
      if (arrowMatches) {
        for (const am of arrowMatches) {
          const paramsStr = am.match(/\(([^)]*)\)/)[1];
          if (paramsStr.trim()) {
            const params = paramsStr.split(',');
            for (const param of params) {
              const trimmed = param.trim();
              if (!trimmed) continue;
              if (trimmed.startsWith('{') || trimmed.startsWith('...') || trimmed.startsWith('[')) continue;
              if (/:\s*\w/.test(trimmed)) continue;
              const paramName = trimmed.split('=')[0].trim();
              if (paramName) {
                issues.push({ line: lineNum, severity: 'medium', description: `Implicit any: arrow param '${paramName}' has no type annotation` });
                totalImplicitAny++;
              }
            }
          }
        }
      }

      // Missing return type on exported functions
      // export function foo(...)  {  — no `: ReturnType` before `{`
      const exportFuncMatch = line.match(/export\s+(async\s+)?function\s+(\w+)\s*\(([^)]*)\)\s*\{/);
      if (exportFuncMatch) {
        // Check if there's a return type between ) and {
        const afterParen = line.slice(line.lastIndexOf(')'));
        if (!/:\s*\w/.test(afterParen)) {
          issues.push({ line: lineNum, severity: 'low', description: `Exported function '${exportFuncMatch[2]}' missing return type` });
          totalMissingReturnType++;
        }
      }

      // Exported arrow const without return type: export const foo = (x) =>
      const exportArrowMatch = line.match(/export\s+const\s+(\w+)\s*=\s*(async\s*)?\(([^)]*)\)\s*=>/);
      if (exportArrowMatch) {
        // Check if params have `: Type` AND there's a return type `: Type` before =>
        const fullMatch = exportArrowMatch[0];
        // If no `: Type` between ) and =>, it's missing return type
        const betweenParenAndArrow = fullMatch.slice(fullMatch.lastIndexOf(')'));
        if (!/:\s*\w/.test(betweenParenAndArrow)) {
          issues.push({ line: lineNum, severity: 'low', description: `Exported arrow '${exportArrowMatch[1]}' missing return type` });
          totalMissingReturnType++;
        }
      }
    }

    if (issues.length > 0) {
      fileResults.push({ path: file.path, issues });
    }
  }

  // Scoring: weighted penalties
  let penalty = 0;
  penalty += totalAny * 8;           // explicit any: heavy
  penalty += totalImplicitAny * 4;    // implicit any: moderate
  penalty += totalTsNocheck * 20;     // @ts-nocheck: severe
  penalty += totalTsIgnore * 10;      // @ts-ignore: heavy
  penalty += totalTsExpectError * 5;  // @ts-expect-error: moderate
  penalty += totalTypeAssertions * 2; // assertions: light
  penalty += totalMissingReturnType * 1; // missing return: cosmetic
  penalty += totalNonNullAssertions * 3;  // non-null: moderate

  const totalFiles = tsFiles.length;
  const maxPenalty = totalFiles * 50; // 50 points per file baseline
  let score = maxPenalty > 0 ? Math.max(0, 100 - Math.round((penalty / maxPenalty) * 100)) : 100;
  if (totalFiles === 0) score = 100;

  let grade;
  if (score >= 90) grade = 'A';
  else if (score >= 80) grade = 'B';
  else if (score >= 70) grade = 'C';
  else if (score >= 60) grade = 'D';
  else grade = 'F';

  return {
    grade,
    score,
    totalFiles,
    summary: {
      anyUsage: totalAny,
      implicitAny: totalImplicitAny,
      tsIgnore: totalTsIgnore,
      tsNocheck: totalTsNocheck,
      tsExpectError: totalTsExpectError,
      typeAssertions: totalTypeAssertions,
      missingReturnType: totalMissingReturnType,
      nonNullAssertions: totalNonNullAssertions,
    },
    files: fileResults,
  };
}

export function formatTypeSafetyReport(result) {
  if (!result) return '## Type Safety Analysis\n\nNo data.\n';

  let report = '## Type Safety Analysis\n\n';
  report += `**Grade:** ${result.grade} (${result.score}/100)\n`;
  report += `**TS files analyzed:** ${result.totalFiles}\n\n`;

  const s = result.summary;
  report += '### Summary\n\n';
  report += '| Issue | Count |\n';
  report += '|-------|-------|\n';
  report += `| Explicit 'any' | ${s.anyUsage} |\n`;
  report += `| Implicit 'any' | ${s.implicitAny} |\n`;
  report += `| @ts-ignore | ${s.tsIgnore} |\n`;
  report += `| @ts-nocheck | ${s.tsNocheck} |\n`;
  report += `| @ts-expect-error | ${s.tsExpectError} |\n`;
  report += `| Type Assertions | ${s.typeAssertions} |\n`;
  report += `| Missing Return Types | ${s.missingReturnType} |\n`;
  report += `| Non-null Assertions | ${s.nonNullAssertions} |\n\n`;

  if (result.files.length > 0) {
    report += '### Files with Issues\n\n';
    for (const f of result.files.slice(0, 15)) {
      report += `**${f.path}** — ${f.issues.length} issue(s)\n`;
      for (const issue of f.issues.slice(0, 5)) {
        report += `  - L${issue.line}: [${issue.severity}] ${issue.description}\n`;
      }
      if (f.issues.length > 5) {
        report += `  - _...and ${f.issues.length - 5} more_\n`;
      }
      report += '\n';
    }
  }

  return report;
}

// ─── F66: Code Smells Analysis ─────────────────────────────────────────

export function analyzeCodeSmells(files = []) {
  let totalLongFiles = 0;
  let totalDeepNesting = 0;
  let totalTooManyParams = 0;
  let totalMagicNumbers = 0;
  let totalGodFiles = 0;
  let totalEmptyCatch = 0;
  let totalTodoComments = 0;

  const fileResults = [];

  for (const file of files) {
    const issues = [];
    const lines = file.content.split('\n');
    const lineCount = lines.length;

    // Long file detection (>500 lines)
    if (lineCount > 500) {
      issues.push({
        line: 1,
        severity: 'medium',
        description: `Long file: ${lineCount} lines (consider splitting)`,
      });
      totalLongFiles++;
    }

    // God file detection: count exports
    const exportCount = (file.content.match(/\bexport\s+(function|const|class|default|\{)/g) || []).length;
    if (exportCount >= 10) {
      issues.push({
        line: 1,
        severity: 'medium',
        description: `God file: ${exportCount} exports (consider splitting)`,
      });
      totalGodFiles++;
    }

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const lineNum = i + 1;

      // Deep nesting detection: count leading whitespace
      const indent = line.match(/^(\s*)/)[1].length;
      const tabIndent = line.match(/^(\t*)/)[1].length;
      const effectiveIndent = Math.max(indent, tabIndent * 4);
      // 4+ levels of nesting (2-space: 8+ = 4 levels, 4-space: 8+ = 2 levels but conservative)
      if (effectiveIndent >= 8 && /\S/.test(line) && !line.trim().startsWith('//') && !line.trim().startsWith('*')) {
        issues.push({
          line: lineNum,
          severity: 'low',
          description: `Deep nesting: ${Math.floor(effectiveIndent / 4)}+ levels`,
        });
        totalDeepNesting++;
      }

      // Too many parameters: function with 5+ params
      const funcMatch = line.match(/function\s+\w+\s*\(([^)]*)\)/);
      if (funcMatch) {
        const params = funcMatch[1].split(',').map(p => p.trim()).filter(p => p && !p.startsWith('...'));
        if (params.length >= 5) {
          issues.push({
            line: lineNum,
            severity: 'medium',
            description: `Too many parameters: ${params.length} (consider using an options object)`,
          });
          totalTooManyParams++;
        }
      }

      // Arrow function with many params
      const arrowMatch = line.match(/\(([^)]*)\)\s*=>/);
      if (arrowMatch) {
        const params = arrowMatch[1].split(',').map(p => p.trim()).filter(p => p && !p.startsWith('...'));
        if (params.length >= 5) {
          issues.push({
            line: lineNum,
            severity: 'medium',
            description: `Too many parameters in arrow: ${params.length}`,
          });
          totalTooManyParams++;
        }
      }

      // Magic numbers in comparisons (not 0, 1, -1)
      const magicMatches = line.match(/(===?|!==?|>=?|<=?|>[^=]|<[^=])\s*(\d+(?:\.\d+)?)/g);
      if (magicMatches) {
        for (const mm of magicMatches) {
          const num = parseFloat(mm.match(/[\d.]+$/)[0]);
          if (num !== 0 && num !== 1 && num !== -1) {
            issues.push({
              line: lineNum,
              severity: 'low',
              description: `Magic number: ${num} in comparison (extract to named constant)`,
            });
            totalMagicNumbers++;
          }
        }
      }

      // Empty catch block
      if (/catch\s*\([^)]*\)\s*\{\s*\}/.test(line)) {
        issues.push({
          line: lineNum,
          severity: 'high',
          description: 'Empty catch block: silently swallows errors',
        });
        totalEmptyCatch++;
      }
      // Multi-line empty catch: catch(e) { followed by closing } on next line
      if (/catch\s*\([^)]*\)\s*\{\s*$/.test(line)) {
        // Check next non-empty line
        for (let j = i + 1; j < Math.min(i + 3, lines.length); j++) {
          const nextLine = lines[j].trim();
          if (nextLine === '}') {
            issues.push({
              line: lineNum,
              severity: 'high',
              description: 'Empty catch block: silently swallows errors',
            });
            totalEmptyCatch++;
            break;
          }
          if (nextLine !== '') break;
        }
      }

      // TODO/FIXME comments
      if (/\/\/\s*(TODO|FIXME|HACK|XXX)\b/i.test(line) || /\*\s*(TODO|FIXME|HACK|XXX)\b/i.test(line)) {
        issues.push({
          line: lineNum,
          severity: 'low',
          description: `${line.match(/(TODO|FIXME|HACK|XXX)/i)[0]} comment: unresolved work marker`,
        });
        totalTodoComments++;
      }
    }

    if (issues.length > 0) {
      fileResults.push({ path: file.path, issues });
    }
  }

  // Scoring
  let penalty = 0;
  penalty += totalLongFiles * 10;
  penalty += totalDeepNesting * 3;
  penalty += totalTooManyParams * 5;
  penalty += totalMagicNumbers * 1;
  penalty += totalGodFiles * 10;
  penalty += totalEmptyCatch * 15;
  penalty += totalTodoComments * 2;

  const totalFiles = files.length;
  const maxPenalty = totalFiles * 40;
  let score = maxPenalty > 0 ? Math.max(0, 100 - Math.round((penalty / maxPenalty) * 100)) : 100;
  if (totalFiles === 0) score = 100;

  let grade;
  if (score >= 90) grade = 'A';
  else if (score >= 80) grade = 'B';
  else if (score >= 70) grade = 'C';
  else if (score >= 60) grade = 'D';
  else grade = 'F';

  return {
    grade,
    score,
    totalFiles,
    summary: {
      longFiles: totalLongFiles,
      deepNesting: totalDeepNesting,
      tooManyParams: totalTooManyParams,
      magicNumbers: totalMagicNumbers,
      godFiles: totalGodFiles,
      emptyCatch: totalEmptyCatch,
      todoComments: totalTodoComments,
    },
    files: fileResults,
  };
}

// F68: Naming Convention Analysis
export function analyzeNamingConventions(files = [], options = {}) {
  const {
    snakeCaseAllowed = false,
    kebabFileNames = true,
    maxIssuesPerFile = 20,
  } = options;

  const stats = {
    totalFiles: files.length,
    filesWithIssues: 0,
    totalIssues: 0,
    conventions: {
      camelCase: { count: 0, label: 'camelCase' },
      PascalCase: { count: 0, label: 'PascalCase' },
      snake_case: { count: 0, label: 'snake_case' },
      SCREAMING_SNAKE: { count: 0, label: 'SCREAMING_SNAKE' },
      kebab_case: { count: 0, label: 'kebab-case' },
      other: { count: 0, label: 'other' },
    },
    violations: {
      inconsistentVariables: 0,
      pascalFunctions: 0,
      camelClasses: 0,
      lowerConstants: 0,
      camelEnums: 0,
      snakeVariables: 0,
      singleLetterNames: 0,
      abbreviatedNames: 0,
    },
  };

  const fileResults = [];

  const isPython = (f) => (f.path || '').endsWith('.py');

  const isCamelCase = (s) => /^[a-z][a-zA-Z0-9]*$/.test(s) && s !== s.toUpperCase();
  const isPascalCase = (s) => /^[A-Z][a-zA-Z0-9]*$/.test(s);
  const isSnakeCase = (s) => /^[a-z][a-z0-9]*(_[a-z0-9]+)+$/.test(s);
  const isScreamingSnake = (s) => /^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$/.test(s);
  const isKebabCase = (s) => /^[a-z][a-z0-9]*(-[a-z0-9]+)+$/.test(s);

  const classifyName = (name) => {
    if (isScreamingSnake(name)) return 'SCREAMING_SNAKE';
    if (isPascalCase(name)) return 'PascalCase';
    if (isSnakeCase(name)) return 'snake_case';
    if (isCamelCase(name)) return 'camelCase';
    if (isKebabCase(name)) return 'kebab_case';
    return 'other';
  };

  const ABBREVS = new Set(['tmp', 'temp', 'arr', 'obj', 'str', 'num', 'val', 'val2', 'val3', 'cnt', 'len', 'btn', 'lbl', 'msg', 'err2', 'el', 'elem', 'ctx2', 'fn', 'cb', 'ref2', 'ret', 'idx2', 'i2', 'j2']);

  // Component-like PascalCase names to skip (React/Vue convention)
  const COMPONENT_SUFFIXES = /(?:Component|Element|Node|Type|Provider|Context|Route|Page|Layout|Modal|Dialog|Form|Button|Input|List|Table|Card|Header|Footer|Nav|Sidebar|Menu|Tab|Toast|Dropdown|Tooltip|Badge|Avatar|Icon|Image|Video|Canvas|Chart|Map|Grid|Flex|Box|Container|Wrapper|Section|Article|Main|Navigation|Link|Handler|Manager|Service|Factory|Builder|Store|Reducer|Middleware|Controller|Gateway|Adapter|Bridge|Proxy|Wrapper|Helper|Util|Utils|Config|Settings|Options|Props|State|Hook|Plugin|Extension|Module|Package|Registry|Resolver|Validator|Formatter|Parser|Compiler|Interpreter|Executor|Runner|Worker|Task|Job|Queue|Scheduler|Emitter|Listener|Observer|Subscriber|Publisher|Stream|Buffer|Cache|Store|Repository|DAO|Entity|Model|Schema|Migration|Seed|Fixture|Mock|Stub|Spy|Factory|Instance|Singleton|Prototype|Mixin|Trait|Decorator|Aspect|Interceptor|Filter|Pipe|Transformer|Converter|Mapper|Adapter|Codec|Serializer|Deserializer|Encoder|Decoder|Reader|Writer|Loader|Saver|Exporter|Importer|Generator|Creator|Builder|Maker|Producer|Consumer|Sender|Receiver|Client|Server|Socket|Connection|Session|Context|Scope|Namespace|Module|Bundle|Chunk|Slice|Segment|Fragment|Portion|Part|Piece|Bit|Byte|Word|Token|Symbol|Character|String|Number|Integer|Float|Double|Decimal|Boolean|Null|Undefined|Void|Never|Any|Unknown|Object|Array|Map|Set|WeakMap|WeakSet|Promise|Future|Observable|Subject|BehaviorSubject|ReplaySubject|AsyncSubject)$/;

  for (const file of files) {
    const issues = [];
    const lines = file.content.split('\n');
    const filePath = file.path || 'unknown';

    // File name analysis
    const fileName = filePath.split('/').pop();
    const baseName = fileName.replace(/\.[^.]+$/, '');
    if (baseName && baseName.length > 1) {
      const fileConv = classifyName(baseName);
      stats.conventions[fileConv].count++;

      if (isPython(file) && isCamelCase(baseName) && !isPascalCase(baseName)) {
        issues.push({
          line: 1, severity: 'medium', category: 'fileName',
          description: `Python file uses camelCase (${baseName}), should use snake_case`,
        });
        stats.violations.inconsistentVariables++;
      }
    }

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const lineNum = i + 1;
      if (issues.length >= maxIssuesPerFile) break;

      const trimmed = line.trim();
      if (trimmed.startsWith('//') || trimmed.startsWith('*') || trimmed.startsWith('#') || trimmed.startsWith("'")) continue;

      // const/let/var
      const varMatch = line.match(/(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)/);
      if (varMatch) {
        const name = varMatch[1];
        const conv = classifyName(name);
        stats.conventions[conv].count++;

        // PascalCase const — skip component-like names
        if (isPascalCase(name) && !COMPONENT_SUFFIXES.test(name) && !line.includes('new ') && !line.includes('extends')) {
          issues.push({
            line: lineNum, severity: 'low', category: 'variable',
            description: `Variable \`${name}\` uses PascalCase, expected camelCase`,
          });
          stats.violations.pascalFunctions++;
        }

        // Single letter names (allow i/j/k/e/_/$ in JS)
        if (/^[a-zA-Z]$/.test(name) && !['i', 'j', 'k', 'e', '_', '$'].includes(name) && !isPython(file)) {
          issues.push({
            line: lineNum, severity: 'low', category: 'naming',
            description: `Single letter name \`${name}\` — consider a descriptive name`,
          });
          stats.violations.singleLetterNames++;
        }

        // Abbreviated names
        if (ABBREVS.has(name)) {
          issues.push({
            line: lineNum, severity: 'low', category: 'naming',
            description: `Abbreviated name \`${name}\` — use full word`,
          });
          stats.violations.abbreviatedNames++;
        }
      }

      // Function declarations
      const funcMatch = line.match(/(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)/);
      if (funcMatch) {
        const name = funcMatch[1];
        stats.conventions[classifyName(name)].count++;

        if (isPascalCase(name) && !isPython(file) && name !== 'constructor') {
          issues.push({
            line: lineNum, severity: 'medium', category: 'function',
            description: `Function \`${name}\` uses PascalCase, expected camelCase`,
          });
          stats.violations.pascalFunctions++;
        }
        if (isPython(file) && isCamelCase(name)) {
          issues.push({
            line: lineNum, severity: 'medium', category: 'function',
            description: `Function \`${name}\` uses camelCase, Python expects snake_case`,
          });
          stats.violations.snakeVariables++;
        }
      }

      // Class declarations
      const classMatch = line.match(/(?:export\s+)?(?:default\s+)?class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)/);
      if (classMatch) {
        const name = classMatch[1];
        stats.conventions[classifyName(name)].count++;
        if (!isPascalCase(name) && name.length > 1) {
          issues.push({
            line: lineNum, severity: 'high', category: 'class',
            description: `Class \`${name}\` should use PascalCase`,
          });
          stats.violations.camelClasses++;
        }
      }

      // Enum declarations
      const enumMatch = line.match(/(?:export\s+)?enum\s+([a-zA-Z_$][a-zA-Z0-9_$]*)/);
      if (enumMatch) {
        const name = enumMatch[1];
        stats.conventions[classifyName(name)].count++;
        if (!isPascalCase(name)) {
          issues.push({
            line: lineNum, severity: 'medium', category: 'enum',
            description: `Enum \`${name}\` should use PascalCase`,
          });
          stats.violations.camelEnums++;
        }
      }

      // Module-level const with numeric value in PascalCase → flag
      const numConstMatch = line.match(/^\s*const\s+([A-Z][a-zA-Z0-9_]*)\s*=\s*\d/);
      if (numConstMatch) {
        const name = numConstMatch[1];
        if (isPascalCase(name)) {
          issues.push({
            line: lineNum, severity: 'low', category: 'constant',
            description: `Constant \`${name}\` may need SCREAMING_SNAKE`,
          });
          stats.violations.lowerConstants++;
        }
      }
    }

    if (issues.length > 0) {
      stats.filesWithIssues++;
      stats.totalIssues += issues.length;
    }
    fileResults.push({ path: filePath, issues });
  }

  const convEntries = Object.entries(stats.conventions).filter(([, v]) => v.count > 0);
  const dominant = convEntries.sort((a, b) => b[1].count - a[1].count)[0];

  return {
    score: Math.max(0, 100 - stats.totalIssues * 0.5),
    stats,
    dominantConvention: dominant ? dominant[0] : null,
    conventionDistribution: Object.fromEntries(
      Object.entries(stats.conventions).filter(([, v]) => v.count > 0)
    ),
    files: fileResults,
  };
}

export function formatNamingConventionsReport(result) {
  let report = '## Naming Conventions Analysis\n\n';
  report += `**Score:** ${result.score}/100\n`;
  report += `**Files analyzed:** ${result.stats.totalFiles}\n`;
  report += `**Files with issues:** ${result.stats.filesWithIssues}\n`;
  report += `**Total issues:** ${result.stats.totalIssues}\n\n`;

  if (result.dominantConvention) {
    report += `**Dominant convention:** ${result.stats.conventions[result.dominantConvention].label}\n\n`;
  }

  report += '### Convention Distribution\n\n';
  const totalConv = Object.values(result.conventionDistribution).reduce((s, v) => s + v.count, 0);
  for (const [conv, data] of Object.entries(result.conventionDistribution)) {
    const pct = totalConv > 0 ? Math.round((data.count / totalConv) * 100) : 0;
    report += `- ${data.label}: ${data.count} (${pct}%)\n`;
  }
  report += '\n';

  const violations = Object.entries(result.stats.violations).filter(([, v]) => v > 0);
  if (violations.length > 0) {
    report += '### Violation Summary\n\n';
    const labels = {
      inconsistentVariables: 'Inconsistent variable naming',
      pascalFunctions: 'PascalCase functions (expected camelCase)',
      camelClasses: 'Non-PascalCase classes',
      lowerConstants: 'Lowercase constants (expected SCREAMING_SNAKE)',
      camelEnums: 'Non-PascalCase enums',
      snakeVariables: 'snake_case in JS/TS variables',
      singleLetterNames: 'Single letter variable names',
      abbreviatedNames: 'Abbreviated variable names',
    };
    for (const [key, count] of violations.sort((a, b) => b[1] - a[1])) {
      report += `- ${labels[key] || key}: ${count}\n`;
    }
    report += '\n';
  }

  const topFiles = result.files
    .filter(f => f.issues.length > 0)
    .sort((a, b) => b.issues.length - a.issues.length)
    .slice(0, 10);

  if (topFiles.length > 0) {
    report += '### Top Files with Issues\n\n';
    for (const file of topFiles) {
      report += `#### ${file.path} (${file.issues.length} issues)\n`;
      for (const issue of file.issues.slice(0, 5)) {
        const icon = issue.severity === 'critical' ? '🔴' : issue.severity === 'high' ? '🟠' : issue.severity === 'medium' ? '🟡' : '🔵';
        report += `  ${icon} L${issue.line}: ${issue.description}\n`;
      }
      if (file.issues.length > 5) report += `  ... and ${file.issues.length - 5} more\n`;
      report += '\n';
    }
  }

  return report;
}

export function formatCodeSmellReport(result) {
  if (!result) return '## Code Smell Analysis\n\nNo data.\n';

  let report = '## Code Smell Analysis\n\n';
  report += `**Grade:** ${result.grade} (${result.score}/100)\n`;
  report += `**Files analyzed:** ${result.totalFiles}\n\n`;

  const s = result.summary;
  report += '### Summary\n\n';
  report += '| Smell | Count |\n';
  report += '|-------|-------|\n';
  report += `| Long Files (>500 lines) | ${s.longFiles} |\n`;
  report += `| Deep Nesting (4+ levels) | ${s.deepNesting} |\n`;
  report += `| Too Many Params (5+) | ${s.tooManyParams} |\n`;
  report += `| Magic Numbers | ${s.magicNumbers} |\n`;
  report += `| God Files (10+ exports) | ${s.godFiles} |\n`;
  report += `| Empty Catch Blocks | ${s.emptyCatch} |\n`;
  report += `| TODO/FIXME Comments | ${s.todoComments} |\n\n`;

  if (result.files.length > 0) {
    report += '### Files with Issues\n\n';
    for (const f of result.files.slice(0, 15)) {
      report += `**${f.path}** — ${f.issues.length} issue(s)\n`;
      for (const issue of f.issues.slice(0, 5)) {
        report += `  - L${issue.line}: [${issue.severity}] ${issue.description}\n`;
      }
      if (f.issues.length > 5) {
        report += `  - _...and ${f.issues.length - 5} more_\n`;
      }
      report += '\n';
    }
  }

  return report;
}

// ─── F67: README Health Analysis ───────────────────────────────────────

/**
 * Analyze README file quality and completeness.
 *
 * Checks for 10 essential README sections:
   * - Title (# heading)
   * - Description (what the project does)
   * - Installation (how to install)
   * - Usage (how to use)
   * - License (license info)
   * - Contributing (contribution guidelines)
   * - Tests (how to run tests)
   * - Badges (shields.io or similar)
   * - Examples (code examples)
   * - API/Documentation (API docs or link)
 *
 * Also checks for common issues:
   * - Placeholder content (TODO, coming soon, etc.)
   * - Missing title
   * - Too short (<100 chars)
   * - Broken markdown links
   * - Missing code blocks in usage
   *
   * @param {Object} readmeFile - { path, content } or null if no README
   * @returns {Object} analysis result with grade, score, sections, issues
   */
export function analyzeReadmeHealth(readmeFile = null) {
  const result = {
    found: false,
    path: null,
    score: 0,
    grade: 'F',
    sections: {
      title: false,
      description: false,
      installation: false,
      usage: false,
      license: false,
      contributing: false,
      tests: false,
      badges: false,
      examples: false,
      apiDocs: false,
    },
    issues: [],
    stats: {
      length: 0,
      headings: 0,
      codeBlocks: 0,
      links: 0,
      images: 0,
    },
  };

  if (!readmeFile || readmeFile.content === null || readmeFile.content === undefined) {
    result.issues.push({ severity: 'critical', message: 'No README file found' });
    result.score = 0;
    result.grade = 'F';
    return result;
  }

  const content = readmeFile.content;
  const lower = content.toLowerCase();
  result.found = true;
  result.path = readmeFile.path || 'README.md';
  result.stats.length = content.length;

  // Count markdown elements
  result.stats.headings = (content.match(/^#{1,6}\s/gm) || []).length;
  result.stats.codeBlocks = (content.match(/```/g) || []).length / 2;
  result.stats.links = (content.match(/\[([^\]]+)\]\(([^)]+)\)/g) || []).length;
  result.stats.images = (content.match(/!\[([^\]]*)\]\(([^)]+)\)/g) || []).length;

  // --- Section detection ---

  // Title: first H1 heading
  const h1Match = content.match(/^#\s+(.+)$/m);
  if (h1Match) {
    result.sections.title = true;
  } else {
    result.issues.push({ severity: 'high', message: 'Missing H1 title heading' });
  }

  // Description: paragraph text after title, or section with "description"/"about"/"overview"
  const hasDescSection = /^#{1,3}\s.*(description|about|overview|introduction|what)/im.test(content);
  const hasIntroPara = h1Match && content.slice(h1Match.index + h1Match[0].length).trim().length > 30;
  if (hasDescSection || hasIntroPara) {
    result.sections.description = true;
  } else {
    result.issues.push({ severity: 'high', message: 'Missing project description' });
  }

  // Installation
  if (/install/i.test(lower) && /(npm|yarn|pnpm|pip|cargo|go install|brew|apt|docker|clone|\$\s)/i.test(content)) {
    result.sections.installation = true;
  } else if (/^#{1,4}\s.*(install|setup|getting started|quick start)/im.test(content)) {
    result.sections.installation = true;
  } else {
    result.issues.push({ severity: 'medium', message: 'Missing installation instructions' });
  }

  // Usage
  if (/^#{1,4}\s.*(usage|how to use|example|quickstart|getting started)/im.test(content)) {
    result.sections.usage = true;
  } else if (/```/.test(content) && /(usage|run|execute|example|import|require)/i.test(lower)) {
    result.sections.usage = true;
  } else {
    result.issues.push({ severity: 'medium', message: 'Missing usage section or examples' });
  }

  // License
  if (/license|licence|mit|apache|gpl|bsd|isc|mozilla/i.test(lower)) {
    result.sections.license = true;
  } else {
    result.issues.push({ severity: 'high', message: 'Missing license information' });
  }

  // Contributing
  if (/contribut|pull request|pr|developing|development guide/i.test(lower)) {
    result.sections.contributing = true;
  }

  // Tests
  if (/test|spec|jest|mocha|vitest|pytest|\bnpm test\b|\bnpx test\b|\brun test/i.test(lower)) {
    result.sections.tests = true;
  }

  // Badges
  if (/shields\.io|badge|\[!\[|\(https:\/\/img\.shields|codecov|travis|github\.com\/.*\/actions/i.test(content)) {
    result.sections.badges = true;
  }

  // Examples / code blocks
  if (result.stats.codeBlocks >= 2) {
    result.sections.examples = true;
  }

  // API docs
  if (/api|documentation|docs\.|\[.*docs?\]|\(docs?\/|reference/i.test(lower) && result.stats.length > 30) {
    result.sections.apiDocs = true;
  }

  // --- Issue detection ---

  // Placeholder content
  if (/todo|coming soon|placeholder|insert (your|the)|lorem ipsum|tbd|wip/i.test(content)) {
    const placeholders = (content.match(/todo|coming soon|placeholder|insert (your|the)|lorem ipsum|tbd|wip/gi) || []).length;
    result.issues.push({ severity: 'low', message: `Contains ${placeholders} placeholder(s) (TODO, coming soon, etc.)` });
  }

  // Too short
  if (result.stats.length < 100) {
    result.issues.push({ severity: 'high', message: `README is very short (${result.stats.length} chars)` });
  }

  // Broken markdown links (empty link text or empty URL)
  const brokenLinks = (content.match(/\[\s*\]\([^)]*\)|\[[^\]]+\]\(\s*\)/g) || []).length;
  if (brokenLinks > 0) {
    result.issues.push({ severity: 'low', message: `${brokenLinks} broken markdown link(s)` });
  }

  // Usage without code blocks
  if (result.sections.usage && result.stats.codeBlocks === 0) {
    result.issues.push({ severity: 'medium', message: 'Usage section has no code examples' });
  }

  // --- Scoring ---
  const sectionWeights = {
    title: 20,
    description: 20,
    installation: 15,
    usage: 15,
    license: 10,
    contributing: 5,
    tests: 5,
    badges: 3,
    examples: 4,
    apiDocs: 3,
  };

  let score = 0;
  for (const [key, present] of Object.entries(result.sections)) {
    if (present) score += sectionWeights[key];
  }

  // Penalty for issues
  for (const issue of result.issues) {
    if (issue.severity === 'critical') score -= 30;
    else if (issue.severity === 'high') score -= 5;
    else if (issue.severity === 'medium') score -= 3;
    else if (issue.severity === 'low') score -= 1;
  }

  result.score = Math.max(0, Math.min(100, score));
  result.grade = result.score >= 90 ? 'A' : result.score >= 80 ? 'B' : result.score >= 70 ? 'C' : result.score >= 60 ? 'D' : 'F';

  return result;
}

export function formatReadmeHealthReport(result) {
  if (!result) return '## README Health Analysis\n\nNo data.\n';
  if (!result.found) return '## README Health Analysis\n\n❌ **No README file found.**\n';

  let report = '## README Health Analysis\n\n';
  report += `**File:** ${result.path}\n`;
  report += `**Grade:** ${result.grade} (${result.score}/100)\n`;
  report += `**Length:** ${result.stats.length} chars, ${result.stats.headings} headings, ${result.stats.codeBlocks} code blocks\n\n`;

  report += '### Sections\n\n';
  const labels = {
    title: 'Title (H1)',
    description: 'Description',
    installation: 'Installation',
    usage: 'Usage',
    license: 'License',
    contributing: 'Contributing',
    tests: 'Tests',
    badges: 'Badges',
    examples: 'Code Examples',
    apiDocs: 'API / Docs',
  };
  for (const [key, label] of Object.entries(labels)) {
    const icon = result.sections[key] ? '✅' : '⬜';
    report += `${icon} ${label}\n`;
  }

  if (result.issues.length > 0) {
    report += '\n### Issues\n\n';
    for (const issue of result.issues) {
      const icon = issue.severity === 'critical' ? '🔴' : issue.severity === 'high' ? '🟠' : issue.severity === 'medium' ? '🟡' : '🔵';
      report += `${icon} [${issue.severity}] ${issue.message}\n`;
    }
  }

  return report;
}

// F69: Deprecation Usage Analysis
// Detects usage of deprecated APIs, patterns, and libraries.
// Patterns are plain substrings matched via includes().
export function analyzeDeprecationUsage(files = [], options = {}) {
  const {
    additionalDeprecations = [],
    maxIssuesPerFile = 50,
  } = options;

  // [substring, message, severity, category]
  const BUILTIN = [
    ['new Buffer(', 'Use Buffer.alloc(), Buffer.from() instead', 'high', 'nodejs'],
    ['fs.exists(', 'Use fs.stat() or fs.access() instead', 'high', 'nodejs'],
    ['fs.existsSync(', 'Use fs.statSync() or fs.accessSync() instead', 'high', 'nodejs'],
    ['util.isArray', 'Use Array.isArray() instead', 'low', 'nodejs'],
    ['util.isString', 'Use typeof x === "string" instead', 'low', 'nodejs'],
    ['util.isNumber', 'Use typeof x === "number" instead', 'low', 'nodejs'],
    ['util.isFunction', 'Use typeof x === "function" instead', 'low', 'nodejs'],
    ['util.isObject', 'Use x !== null && typeof x === "object"', 'low', 'nodejs'],
    ['util.inherits', 'Use ES6 class extends', 'medium', 'nodejs'],
    ['crypto.createCipher(', 'Use crypto.createCipheriv() — insecure key derivation', 'high', 'nodejs'],
    ['crypto.createDecipher(', 'Use crypto.createDecipheriv()', 'high', 'nodejs'],
    ['punycode.', 'Use the "punycode" package — built-in is deprecated', 'medium', 'nodejs'],
    ['domain.', 'Domain module is deprecated — use async/await', 'medium', 'nodejs'],
    ['with (', '"with" statement deprecated in strict mode', 'high', 'javascript'],
    ['arguments.callee', 'Forbidden in strict mode', 'high', 'javascript'],
    ['arguments.caller', 'Forbidden in strict mode', 'high', 'javascript'],
    ['escape(', 'Use encodeURIComponent() instead', 'medium', 'javascript'],
    ['unescape(', 'Use decodeURIComponent() instead', 'medium', 'javascript'],
    ['.substr(', 'Use .substring() or .slice() — .substr() deprecated', 'medium', 'javascript'],
    ['.trimLeft(', 'Use .trimStart()', 'low', 'javascript'],
    ['.trimRight(', 'Use .trimEnd()', 'low', 'javascript'],
    ["require('moment')", 'moment.js in maintenance — use date-fns/dayjs/Temporal', 'medium', 'package'],
    ['from \'moment\'', 'moment.js in maintenance — use date-fns/dayjs/Temporal', 'medium', 'package'],
    ["from \"moment\"", 'moment.js in maintenance — use date-fns/dayjs/Temporal', 'medium', 'package'],
    ["require('lodash')", 'Full lodash — use lodash-es or individual imports', 'low', 'package'],
    ["from 'lodash'", 'Full lodash — use lodash-es or individual imports', 'low', 'package'],
    ["from \"lodash\"", 'Full lodash — use lodash-es or individual imports', 'low', 'package'],
  ];

  const allPatterns = [...BUILTIN, ...additionalDeprecations];

  const stats = {
    totalFiles: files.length,
    filesWithIssues: 0,
    totalIssues: 0,
    categories: {},
    severityCounts: { critical: 0, high: 0, medium: 0, low: 0 },
  };

  const fileResults = [];

  for (const file of files) {
    const issues = [];
    const lines = file.content.split('\n');
    const filePath = file.path || 'unknown';

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const lineNum = i + 1;
      if (issues.length >= maxIssuesPerFile) break;

      const trimmed = line.trim();
      if (trimmed.startsWith('//') || trimmed.startsWith('*') || trimmed.startsWith('#') || trimmed.startsWith("'")) continue;

      for (const [substr, message, severity, category] of allPatterns) {
        if (line.includes(substr)) {
          issues.push({ line: lineNum, severity, category, pattern: substr, description: message });
          stats.severityCounts[severity]++;
          if (!stats.categories[category]) stats.categories[category] = { count: 0, label: category };
          stats.categories[category].count++;
        }
      }
    }

    if (issues.length > 0) {
      stats.filesWithIssues++;
      stats.totalIssues += issues.length;
    }
    fileResults.push({ path: filePath, issues });
  }

  return {
    score: Math.max(0, 100 - stats.totalIssues * 2 - stats.severityCounts.critical * 10 - stats.severityCounts.high * 3),
    stats,
    files: fileResults,
  };
}

export function formatDeprecationUsageReport(result) {
  let report = '## Deprecation Usage Analysis\n\n';
  report += `**Score:** ${result.score}/100\n`;
  report += `**Files analyzed:** ${result.stats.totalFiles}\n`;
  report += `**Files with issues:** ${result.stats.filesWithIssues}\n`;
  report += `**Total issues:** ${result.stats.totalIssues}\n\n`;

  report += '### Severity Breakdown\n\n';
  for (const [sev, count] of Object.entries(result.stats.severityCounts)) {
    if (count > 0) {
      const icon = sev === 'critical' ? '🔴' : sev === 'high' ? '🟠' : sev === 'medium' ? '🟡' : '🔵';
      report += `- ${icon} ${sev}: ${count}\n`;
    }
  }
  report += '\n';

  const cats = Object.entries(result.stats.categories).sort((a, b) => b[1].count - a[1].count);
  if (cats.length > 0) {
    report += '### Category Breakdown\n\n';
    for (const [cat, data] of cats) report += `- ${data.label}: ${data.count} issues\n`;
    report += '\n';
  }

  const topFiles = result.files
    .filter(f => f.issues.length > 0)
    .sort((a, b) => b.issues.length - a.issues.length)
    .slice(0, 10);

  if (topFiles.length > 0) {
    report += '### Top Files with Deprecations\n\n';
    for (const file of topFiles) {
      report += `#### ${file.path} (${file.issues.length} issues)\n`;
      for (const issue of file.issues.slice(0, 5)) {
        const icon = issue.severity === 'critical' ? '🔴' : issue.severity === 'high' ? '🟠' : issue.severity === 'medium' ? '🟡' : '🔵';
        report += `  ${icon} L${issue.line} [${issue.category}]: ${issue.description}\n`;
      }
      if (file.issues.length > 5) report += `  ... and ${file.issues.length - 5} more\n`;
      report += '\n';
    }
  }

  return report;
}

// F70: File Header Analysis
// Detects missing or incomplete file-level documentation headers.
export function analyzeFileHeaders(files = [], options = {}) {
  const {
    requireLicense = true,
    requireModuleTag = false,
    requireDescription = false,
    headerLines = 5,
    licensePatterns = ['@license', 'Licensed', 'MIT License', 'Apache License', 'BSD', 'GPL', 'ISC License', 'UNLICENSED', 'SPDX'],
  } = options;

  const stats = {
    totalFiles: files.length,
    filesWithHeaders: 0,
    filesWithLicense: 0,
    filesWithModuleTag: 0,
    filesWithDescription: 0,
    filesWithoutAnyHeader: 0,
    totalIssues: 0,
  };

  const fileResults = [];

  for (const file of files) {
    const issues = [];
    const lines = file.content.split('\n');
    const filePath = file.path || 'unknown';
    const ext = filePath.split('.').pop();

    // Get header region (first N lines, skipping shebang)
    let startLine = 0;
    if (lines[0]?.startsWith('#!/')) startLine = 1;
    const headerLines_ = lines.slice(startLine, startLine + headerLines);
    const headerText = headerLines_.join('\n').toLowerCase();

    const hasLicense = licensePatterns.some(p => headerText.includes(p.toLowerCase()));
    const hasModuleTag = /@(?:module|file|class|namespace)\s/.test(headerText);
    const hasDescription = headerLines_.some(l => {
      const t = l.trim();
      // Skip non-comment lines, empty lines, bare comment markers
      if (!t || t === '/*' || t === '*' || t === '*/' || t === '/**' || t === '//') return false;
      if (!/^(\s*\*\s*|\/\/\s*|#\s*|<!--\s*)/.test(l)) return false; // must be a comment line
      if (/^\s*(\*\s*)?@(?:license|copyright|author|version|since|see|deprecated|typedef|param|returns?|throws?|example|ignore)/i.test(t)) return false;
      // A description line has > 10 chars of actual text
      const cleaned = t.replace(/^(\s*\*\s*|\/\/\s*|<!--\s*)/, '').replace(/(\s*-->|\s*\*\/)$/, '').trim();
      return cleaned.length > 10 && /[a-zA-Z]/.test(cleaned);
    });
    const hasAnyHeader = hasLicense || hasModuleTag || hasDescription;

    if (hasLicense) stats.filesWithLicense++;
    if (hasModuleTag) stats.filesWithModuleTag++;
    if (hasDescription) stats.filesWithDescription++;
    if (hasAnyHeader) stats.filesWithHeaders++;
    else stats.filesWithoutAnyHeader++;

    if (requireLicense && !hasLicense) {
      issues.push({ line: 1, severity: 'low', category: 'license', description: 'Missing license header' });
      stats.totalIssues++;
    }
    if (requireModuleTag && !hasModuleTag) {
      issues.push({ line: 1, severity: 'low', category: 'module', description: 'Missing @module JSDoc tag' });
      stats.totalIssues++;
    }
    if (requireDescription && !hasDescription) {
      issues.push({ line: 1, severity: 'low', category: 'description', description: 'Missing file description in header' });
      stats.totalIssues++;
    }

    // Check for non-standard header formats
    const hasJSDoc = headerLines_.some(l => /^\s*\/\*\*/.test(l));
    const hasHashComment = headerLines_.some(l => /^\s*#/.test(l));
    let headerStyle = 'none';
    if (hasJSDoc) headerStyle = 'jsdoc';
    else if (hasHashComment) headerStyle = 'hash';
    else if (headerLines_.some(l => /^\s*\/\//.test(l))) headerStyle = 'line-comment';

    fileResults.push({
      path: filePath,
      hasLicense,
      hasModuleTag,
      hasDescription,
      hasAnyHeader,
      headerStyle,
      issues,
    });
  }

  const coverage = stats.totalFiles > 0 ? Math.round((stats.filesWithHeaders / stats.totalFiles) * 100) : 100;
  return {
    score: coverage,
    stats,
    files: fileResults,
  };
}

export function formatFileHeadersReport(result) {
  let report = '## File Header Analysis\n\n';
  report += `**Score:** ${result.score}/100 (header coverage)\n`;
  report += `**Files analyzed:** ${result.stats.totalFiles}\n\n`;

  report += '### Coverage\n\n';
  report += `- Files with any header: ${result.stats.filesWithHeaders}/${result.stats.totalFiles}\n`;
  report += `- Files with license: ${result.stats.filesWithLicense}\n`;
  report += `- Files with @module tag: ${result.stats.filesWithModuleTag}\n`;
  report += `- Files with description: ${result.stats.filesWithDescription}\n`;
  report += `- Files without any header: ${result.stats.filesWithoutAnyHeader}\n\n`;

  // Header style distribution
  const styles = {};
  for (const f of result.files) {
    styles[f.headerStyle] = (styles[f.headerStyle] || 0) + 1;
  }
  if (Object.keys(styles).length > 0) {
    report += '### Header Style Distribution\n\n';
    for (const [style, count] of Object.entries(styles).sort((a, b) => b[1] - a[1])) {
      report += `- ${style}: ${count}\n`;
    }
    report += '\n';
  }

  // Files missing headers
  const missing = result.files.filter(f => !f.hasAnyHeader);
  if (missing.length > 0) {
    report += '### Files Without Headers\n\n';
    for (const f of missing.slice(0, 20)) {
      report += `- ${f.path}\n`;
    }
    if (missing.length > 20) report += `- ... and ${missing.length - 20} more\n`;
    report += '\n';
  }

  return report;
}

// ─── F71: Regex Complexity / ReDoS Risk ───────────────────────────

/**
 * Analyze regex literals for catastrophic backtracking (ReDoS) risk.
 * Detects: nested quantifiers, overlapping alternation, quantified groups,
 * unbounded repetitions in complex contexts.
 *
 * @param {Array} files - Array of { path, content } objects
 * @returns {Object} Analysis result with risk items and stats
 */
export function analyzeRegexComplexity(files = []) {
  const issues = [];
  let regexCount = 0;
  let riskyCount = 0;

  // Patterns that indicate ReDoS vulnerability
  const dangerousPatterns = [
    // Nested quantifiers: (a+)+ , (a*)*, (a+)*, (a*)+
    { regex: /\([^)]*[+*?][^)]*\)[+*?]/, severity: 'high', label: 'nested-quantifier',
      desc: 'Nested quantifier like (a+)+ can cause exponential backtracking' },
    // Quantified group with alternation: (a|a)*
    { regex: /\([^)]*\|[^)]*\)[+*?]/, severity: 'high', label: 'overlapped-alternation',
      desc: 'Quantified alternation with overlapping branches can cause catastrophic backtracking' },
    // Unbounded repetition: .{0,} or x{0,} without anchor
    { regex: /\.\{0,\}/, severity: 'medium', label: 'unbounded-dot-repetition',
      desc: 'Unbounded repetition of dot (.) without anchors' },
    // Multiple unbounded quantifiers: a+.*b+ or similar
    { regex: /[+*][^+*\n]{0,10}[+*]/, severity: 'medium', label: 'adjacent-quantifiers',
      desc: 'Adjacent unbounded quantifiers increase backtracking surface' },
    // Quantified optional group: (a?)+
    { regex: /\([^)]*\?\)[+*]/, severity: 'medium', label: 'quantified-optional-group',
      desc: 'Quantified optional group creates ambiguity' },
  ];

  for (const file of files) {
    if (!file.content || typeof file.content !== 'string') continue;

    // Find regex literals: /pattern/flags
    const regexLiteralRe = /\/([^\/\n]+)\/([gimsuy]*)/g;
    // Also find RegExp() calls
    const regexpCallRe = /new\s+RegExp\s*\(\s*['"]([^'"]+)['"]/g;
    // Also find string patterns in RegExp constructors with template literals
    const regexpTemplateRe = /new\s+RegExp\s*\(`([^`]+)`/g;

    const candidates = [];

    let m;
    while ((m = regexLiteralRe.exec(file.content)) !== null) {
      candidates.push({ pattern: m[1], flags: m[2], type: 'literal', index: m.index });
    }
    while ((m = regexpCallRe.exec(file.content)) !== null) {
      candidates.push({ pattern: m[1], flags: '', type: 'constructor', index: m.index });
    }
    while ((m = regexpTemplateRe.exec(file.content)) !== null) {
      candidates.push({ pattern: m[1], flags: '', type: 'template', index: m.index });
    }

    for (const candidate of candidates) {
      regexCount++;
      const lineNum = file.content.slice(0, candidate.index).split('\n').length;
      const found = [];

      for (const danger of dangerousPatterns) {
        if (danger.regex.test(candidate.pattern)) {
          found.push({
            severity: danger.severity,
            label: danger.label,
            desc: danger.desc,
          });
        }
      }

      // Check pattern length heuristic: very long patterns are harder to optimize
      if (candidate.pattern.length > 100) {
        found.push({
          severity: 'low',
          label: 'long-pattern',
          desc: `Pattern length ${candidate.pattern.length} exceeds 100 chars — consider splitting or simplifying`,
        });
      }

      if (found.length > 0) {
        riskyCount++;
        const maxSeverity = found.some(f => f.severity === 'high') ? 'high'
          : found.some(f => f.severity === 'medium') ? 'medium' : 'low';
        issues.push({
          file: file.path,
          line: lineNum,
          pattern: candidate.pattern.slice(0, 80),
          type: candidate.type,
          severity: maxSeverity,
          findings: found,
        });
      }
    }
  }

  const score = regexCount === 0 ? 100
    : Math.max(0, 100 - Math.round((riskyCount / regexCount) * 100));

  return {
    score,
    stats: {
      totalRegexes: regexCount,
      riskyRegexes: riskyCount,
      safeRegexes: regexCount - riskyCount,
      highSeverity: issues.filter(i => i.severity === 'high').length,
      mediumSeverity: issues.filter(i => i.severity === 'medium').length,
      lowSeverity: issues.filter(i => i.severity === 'low').length,
    },
    issues,
  };
}

export function formatRegexComplexityReport(result) {
  let report = '## Regex Complexity / ReDoS Risk Analysis\n\n';
  report += `**Score:** ${result.score}/100 (regex safety)\n`;
  report += `**Regexes found:** ${result.stats.totalRegexes}\n`;
  report += `**Risky regexes:** ${result.stats.riskyRegexes}\n\n`;

  if (result.stats.totalRegexes === 0) {
    report += 'No regex literals or RegExp() calls found.\n';
    return report;
  }

  report += '### Risk Distribution\n\n';
  report += `- High severity: ${result.stats.highSeverity}\n`;
  report += `- Medium severity: ${result.stats.mediumSeverity}\n`;
  report += `- Low severity: ${result.stats.lowSeverity}\n\n`;

  if (result.issues.length > 0) {
    report += '### Issues Found\n\n';
    for (const issue of result.issues.slice(0, 30)) {
      report += `- **${issue.file}:${issue.line}** [${issue.severity}] \`${issue.pattern}\` (${issue.type})\n`;
      for (const f of issue.findings) {
        report += `  - ${f.label}: ${f.desc}\n`;
      }
    }
    if (result.issues.length > 30) {
      report += `- ... and ${result.issues.length - 30} more\n`;
    }
    report += '\n';
  } else {
    report += 'No risky regex patterns detected. All regexes appear safe.\n\n';
  }

  return report;
}

// Only run main when executed directly (not imported)
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(e => { console.error("❌ Error:", e.message); process.exit(1); });
}
