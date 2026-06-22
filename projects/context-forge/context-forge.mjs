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

export function resolvePath(p) {
  return p.startsWith("/") ? p : join(process.cwd(), p);
}

// Only run main when executed directly (not imported)
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(e => { console.error("❌ Error:", e.message); process.exit(1); });
}
