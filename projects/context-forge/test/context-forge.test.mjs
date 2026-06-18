import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm, mkdir, writeFile, readFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { existsSync } from "node:fs";
import {
  detectProject,
  scanLanguages,
  getDirStructure,
  generateAgentsMd,
  generateCursorRules,
  generateCopilotInstructions,
  generateClaudeMd,
  writeOrUpdate,
  resolvePath,
  parseGitignore,
  isIgnored,
  extractImports,
  extractApiSurface,
  parseConfigFiles,
} from "../context-forge.mjs";

// ─── Helpers ─────────────────────────────────────────────────────

async function makeFixture(files) {
  const dir = await mkdtemp(join(tmpdir(), "ctxforge-"));
  for (const [path, content] of Object.entries(files)) {
    const fullPath = join(dir, path);
    const parent = fullPath.substring(0, fullPath.lastIndexOf("/"));
    await mkdir(parent, { recursive: true });
    await writeFile(fullPath, content);
  }
  return dir;
}

// ─── extractImports (F2) ───────────────────────────────────────

describe("extractImports", () => {
  let tmpDir;

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("extracts ES6 imports from JS files", async () => {
    tmpDir = await makeFixture({
      "src/app.js": `
        import React from 'react';
        import express from 'express';
        import { useState } from 'react';
      `,
    });

    const { imports, allImports } = await extractImports(tmpDir);
    assert.ok(allImports.includes("react"));
    assert.ok(allImports.includes("express"));
    assert.equal(allImports.length, 2); // Unique only
  });

  it("extracts CommonJS require statements", async () => {
    tmpDir = await makeFixture({
      "src/app.js": `
        const fs = require('fs');
        const path = require('path');
      `,
    });

    const { allImports } = await extractImports(tmpDir);
    assert.ok(allImports.includes("fs"));
    assert.ok(allImports.includes("path"));
  });

  it("extracts TypeScript import type", async () => {
    tmpDir = await makeFixture({
      "src/types.ts": `
        import type { User } from './user';
        import type { Config } from 'config';
      `,
    });

    const { allImports } = await extractImports(tmpDir);
    assert.ok(allImports.includes("config"));
  });

  it("extracts Python imports", async () => {
    tmpDir = await makeFixture({
      "main.py": `
        import os
        import sys
        from pathlib import Path
        from datetime import datetime
      `,
    });

    const { allImports } = await extractImports(tmpDir);
    assert.ok(allImports.includes("os"));
    assert.ok(allImports.includes("pathlib"));
    assert.ok(allImports.includes("datetime"));
  });

  it("ignores relative imports", async () => {
    tmpDir = await makeFixture({
      "src/app.js": `
        import { helper } from './helper';
        import { Component } from '../components/Component';
      `,
    });

    const { allImports } = await extractImports(tmpDir);
    assert.equal(allImports.length, 0);
  });

  it("respects .gitignore", async () => {
    tmpDir = await makeFixture({
      ".gitignore": "dist",
      "src/app.js": "import express from 'express';",
      "dist/bundle.js": "import unused from 'unused-lib';",
    });

    const gitignore = await parseGitignore(tmpDir);
    const { allImports } = await extractImports(tmpDir, 3, 0, gitignore);
    assert.ok(allImports.includes("express"));
    assert.ok(!allImports.includes("unused-lib"));
  });

  it("returns imports by file", async () => {
    tmpDir = await makeFixture({
      "src/app.js": "import express from 'express';",
      "src/utils.js": "import fs from 'fs';",
    });

    const { imports } = await extractImports(tmpDir);
    assert.ok(imports.has("src/app.js"));
    assert.ok(imports.has("src/utils.js"));
    assert.deepEqual(imports.get("src/app.js"), ["express"]);
    assert.deepEqual(imports.get("src/utils.js"), ["fs"]);
  });

  it("handles dynamic imports", async () => {
    tmpDir = await makeFixture({
      "src/app.js": `
        const load = async () => {
          const module = await import('lodash');
          return module;
        };
      `,
    });

    const { allImports } = await extractImports(tmpDir);
    assert.ok(allImports.includes("lodash"));
  });
});

// ─── extractApiSurface (F3) ───────────────────────────────────────

describe("extractApiSurface", () => {
  let tmpDir;

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("extracts exported JS functions", async () => {
    tmpDir = await makeFixture({
      "src/app.js": `
        export function hello(name) { return name; }
        export async function fetchData(url) { return fetch(url); }
        function private() { return 'secret'; }
      `,
    });

    const api = await extractApiSurface(tmpDir);
    const names = api.map(a => a.name);
    assert.ok(names.includes("hello"));
    assert.ok(names.includes("fetchData"));
    assert.ok(!names.includes("private"));
  });

  it("extracts exported arrow functions", async () => {
    tmpDir = await makeFixture({
      "src/utils.js": `
        export const add = (a, b) => a + b;
        export const greet = function(name) { return 'hi ' + name; };
        export async function asyncFn(x) { return x; }
      `,
    });

    const api = await extractApiSurface(tmpDir);
    const names = api.map(a => a.name);
    assert.ok(names.includes("add"));
    assert.ok(names.includes("greet"));
    assert.ok(names.includes("asyncFn"));
  });

  it("extracts exported classes", async () => {
    tmpDir = await makeFixture({
      "src/store.js": `
        export class Store { constructor() {} }
        export default class DefaultStore { }
      `,
    });

    const api = await extractApiSurface(tmpDir);
    const classes = api.filter(a => a.type === "class").map(a => a.name);
    assert.ok(classes.includes("Store"));
    assert.ok(classes.includes("DefaultStore"));
  });

  it("extracts TypeScript interfaces and types", async () => {
    tmpDir = await makeFixture({
      "src/types.ts": `
        export interface User { id: number; name: string; }
        export type Status = 'active' | 'inactive';
        export function getUser(id: number): User { return null; }
      `,
    });

    const api = await extractApiSurface(tmpDir);
    const names = api.map(a => a.name);
    assert.ok(names.includes("User"));
    assert.ok(names.includes("Status"));
    assert.ok(names.includes("getUser"));
  });

  it("extracts Python functions and classes", async () => {
    tmpDir = await makeFixture({
      "main.py": `
class DataProcessor:
    def process(self, data):
        return data

def main(args):
    return args

async def fetch_items(url, limit=10):
    return []

__private__ = 'skip'
`,
    });

    const api = await extractApiSurface(tmpDir);
    const names = api.map(a => a.name);
    assert.ok(names.includes("DataProcessor"));
    assert.ok(names.includes("main"));
    assert.ok(names.includes("fetch_items"));
    assert.ok(!names.includes("__private__"));
  });

  it("respects .gitignore", async () => {
    tmpDir = await makeFixture({
      ".gitignore": "dist",
      "src/app.js": "export function main() {}",
      "dist/bundle.js": "export function bundled() {}",
    });

    const gitignore = await parseGitignore(tmpDir);
    const api = await extractApiSurface(tmpDir, 3, 0, gitignore);
    const names = api.map(a => a.name);
    assert.ok(names.includes("main"));
    assert.ok(!names.includes("bundled"));
  });

  it("records file paths", async () => {
    tmpDir = await makeFixture({
      "src/app.js": "export function app() {}",
      "src/utils.js": "export function util() {}",
    });

    const api = await extractApiSurface(tmpDir);
    const appEntry = api.find(a => a.name === "app");
    const utilEntry = api.find(a => a.name === "util");
    assert.ok(appEntry.file.includes("app.js"));
    assert.ok(utilEntry.file.includes("utils.js"));
  });

  it("records params for functions", async () => {
    tmpDir = await makeFixture({
      "src/app.js": "export function compute(a, b, c) { return a + b + c; }",
    });

    const api = await extractApiSurface(tmpDir);
    const fn = api.find(a => a.name === "compute");
    assert.equal(fn.params, "a, b, c");
    assert.equal(fn.type, "function");
  });

  it("handles empty directories", async () => {
    tmpDir = await makeFixture({
      "README.md": "# empty",
    });

    const api = await extractApiSurface(tmpDir);
    assert.equal(api.length, 0);
  });
});

// ─── Other tests (kept from before) ───────────────────────────────

describe("detectProject", () => {
  let tmpDir;

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("detects Node.js project with package.json", async () => {
    tmpDir = await makeFixture({
      "package.json": JSON.stringify({
        name: "test-pkg",
        version: "1.2.3",
        main: "index.js",
        scripts: { dev: "node index.js", test: "jest" },
        dependencies: { express: "^4.0.0", react: "^18.0.0" },
        devDependencies: { jest: "^29.0.0" },
      }),
      "index.js": "console.log('hi');",
    });

    const info = await detectProject(tmpDir);
    assert.equal(info.pkg.name, "test-pkg");
    assert.equal(info.pkg.version, "1.2.3");
    assert.deepEqual(info.entryPoints, ["index.js"]);
    assert.equal(info.scripts.dev, "node index.js");
    assert.ok(info.deps.express);
    assert.ok(info.deps.jest);
    assert.ok(info.frameworks.includes("Express"));
    assert.ok(info.frameworks.includes("React"));
    assert.ok(info.frameworks.includes("Testing"));
  });

  it("detects module entry point", async () => {
    tmpDir = await makeFixture({
      "package.json": JSON.stringify({
        name: "mod-pkg",
        module: "dist/index.mjs",
        bin: { cli: "./cli.mjs" },
      }),
    });

    const info = await detectProject(tmpDir);
    assert.ok(info.entryPoints.includes("dist/index.mjs"));
    assert.ok(info.entryPoints.includes("./cli.mjs"));
  });

  it("detects Python project via pyproject.toml", async () => {
    tmpDir = await makeFixture({
      "pyproject.toml": `
[project]
name = "fastapi-app"
dependencies = ["fastapi", "pytest"]
`,
      "main.py": "print('hello')",
    });

    const info = await detectProject(tmpDir);
    assert.ok(info.frameworks.includes("Python"));
    assert.ok(info.frameworks.includes("FastAPI"));
    assert.ok(info.frameworks.includes("pytest"));
  });

  it("detects Rust project via Cargo.toml", async () => {
    tmpDir = await makeFixture({
      "Cargo.toml": `
[package]
name = "rust-app"
dependencies = { tokio = "1.0", clap = "4.0" }
`,
      "src/main.rs": "fn main() {}",
    });

    const info = await detectProject(tmpDir);
    assert.ok(info.frameworks.includes("Rust/Cargo"));
    assert.ok(info.frameworks.includes("Tokio"));
    assert.ok(info.frameworks.includes("Clap CLI"));
  });

  it("detects Docker projects", async () => {
    tmpDir = await makeFixture({
      "Dockerfile": "FROM node:18",
      "docker-compose.yml": "version: '3'",
    });

    const info = await detectProject(tmpDir);
    assert.ok(info.frameworks.includes("Docker"));
  });

  it("detects monorepo structure", async () => {
    tmpDir = await makeFixture({
      "package.json": JSON.stringify({ name: "mono" }),
      "turbo.json": "{}",
      "packages/app/package.json": JSON.stringify({ name: "app" }),
    });

    const info = await detectProject(tmpDir);
    assert.ok(info.monorepo);
    assert.ok(info.frameworks.includes("Monorepo"));
  });
});

describe("scanLanguages", () => {
  let tmpDir;

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("counts JavaScript files", async () => {
    tmpDir = await makeFixture({
      "a.js": "1",
      "b.js": "2",
      "c.mjs": "3",
      "README.md": "# hi",
    });

    const langs = await scanLanguages(tmpDir);
    assert.equal(langs.get("JavaScript"), 2);
    assert.equal(langs.get("JavaScript (ESM)"), 1);
  });

  it("handles TypeScript with JSX", async () => {
    tmpDir = await makeFixture({
      "app.tsx": "1",
      "components/Button.tsx": "2",
      "utils.ts": "3",
    });

    const langs = await scanLanguages(tmpDir);
    assert.equal(langs.get("TypeScript (React)"), 2);
    assert.equal(langs.get("TypeScript"), 1);
  });

  it("respects maxDepth", async () => {
    tmpDir = await makeFixture({
      "a.js": "1",
      "deep/b.js": "2",
      "deep/c.js": "3",
      "deep/deep/d.js": "4",
    });

    const langs = await scanLanguages(tmpDir, 2);
    assert.equal(langs.get("JavaScript"), 3);
  });

  it("ignores node_modules", async () => {
    tmpDir = await makeFixture({
      "a.js": "1",
      "node_modules/lib.js": "2",
    });

    const langs = await scanLanguages(tmpDir);
    assert.equal(langs.get("JavaScript"), 1);
  });
});

describe("getDirStructure", () => {
  let tmpDir;

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("shows directory structure with emojis", async () => {
    tmpDir = await makeFixture({
      "README.md": "# hi",
      "src/index.js": "console.log()",
      "package.json": "{}",
    });

    const structure = await getDirStructure(tmpDir);
    assert.ok(structure.includes("📄 package.json"));
    assert.ok(structure.includes("📄 README.md"));
    assert.ok(structure.includes("📁 src"));
  });

  it("limits output to 30 items", async () => {
    tmpDir = await makeFixture({});
    const files = Array.from({ length: 35 }, (_, i) => [`f${i}.js`, "1"]);
    await makeFixture(Object.fromEntries(files));

    const structure = await getDirStructure(tmpDir);
    assert.ok(structure.includes("... ("));
  });

  it("respects maxDepth", async () => {
    tmpDir = await makeFixture({
      "a/a/a/file.js": "1",
    });

    const structure = await getDirStructure(tmpDir, "", 2);
    assert.ok(structure.includes("📁 a"));
  });
});

describe("parseGitignore", () => {
  let tmpDir;

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("returns empty array when no .gitignore exists", async () => {
    tmpDir = await makeFixture({});
    const patterns = await parseGitignore(tmpDir);
    assert.deepEqual(patterns, []);
  });

  it("parses simple patterns", async () => {
    tmpDir = await makeFixture({
      ".gitignore": "node_modules\ndist\n.env",
    });

    const patterns = await parseGitignore(tmpDir);
    assert.equal(patterns.length, 3);
    assert.ok(patterns.includes("node_modules"));
    assert.ok(patterns.includes("dist"));
    assert.ok(patterns.includes(".env"));
  });

  it("ignores comments and empty lines", async () => {
    tmpDir = await makeFixture({
      ".gitignore": "# Comment\n\nnode_modules\n",
    });

    const patterns = await parseGitignore(tmpDir);
    assert.deepEqual(patterns, ["node_modules"]);
  });

  it("handles wildcards", async () => {
    tmpDir = await makeFixture({
      ".gitignore": "*.log\n*.min.js\ntest_*.js",
    });

    const patterns = await parseGitignore(tmpDir);
    assert.equal(patterns.length, 3);
  });
});

describe("isIgnored", () => {
  it("matches exact file names", () => {
    const patterns = ["node_modules", ".env", "dist"];
    assert.equal(isIgnored("node_modules", patterns), true);
    assert.equal(isIgnored(".env", patterns), true);
    assert.equal(isIgnored("src", patterns), false);
  });

  it("matches directory prefixes", () => {
    const patterns = ["dist", "build"];
    assert.equal(isIgnored("dist/index.js", patterns), true);
    assert.equal(isIgnored("build/output", patterns), true);
    assert.equal(isIgnored("src/index.js", patterns), false);
  });

  it("handles wildcard patterns", () => {
    const patterns = ["*.log", "*.min.js"];
    assert.equal(isIgnored("error.log", patterns), true);
    assert.equal(isIgnored("bundle.min.js", patterns), true);
    assert.equal(isIgnored("app.js", patterns), false);
  });

  it("handles negation patterns", () => {
    const patterns = ["*.log", "!important.log"];
    assert.equal(isIgnored("error.log", patterns), true);
    assert.equal(isIgnored("important.log", patterns), false);
  });

  it("handles path separators correctly", () => {
    const patterns = ["src/temp"];
    assert.equal(isIgnored(join("src", "temp", "file.js"), patterns), true);
    assert.equal(isIgnored(join("other", "temp", "file.js"), patterns), false);
  });

  it("returns false for no patterns", () => {
    assert.equal(isIgnored("anything", []), false);
  });
});

describe("scanLanguages with gitignore", () => {
  let tmpDir;

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("skips ignored directories", async () => {
    tmpDir = await makeFixture({
      ".gitignore": "build\ntemp",
      "src/main.js": "1",
      "build/output.js": "2",
      "temp/cache.js": "3",
    });

    const gitignore = await parseGitignore(tmpDir);
    const langs = await scanLanguages(tmpDir, 3, 0, gitignore);
    assert.equal(langs.get("JavaScript"), 1);
  });

  it("skips ignored files with wildcards", async () => {
    tmpDir = await makeFixture({
      ".gitignore": "*.min.js\n*.log",
      "src/app.js": "1",
      "dist/bundle.min.js": "2",
      "logs/error.log": "3",
    });

    const gitignore = await parseGitignore(tmpDir);
    const langs = await scanLanguages(tmpDir, 3, 0, gitignore);
    assert.equal(langs.get("JavaScript"), 1);
  });

  it("respects negation patterns", async () => {
    tmpDir = await makeFixture({
      ".gitignore": "*.js\n!app.js",
      "app.js": "1",
      "lib/util.js": "2",
    });

    const gitignore = await parseGitignore(tmpDir);
    const langs = await scanLanguages(tmpDir, 3, 0, gitignore);
    assert.equal(langs.get("JavaScript"), 1);
  });
});

describe("getDirStructure with gitignore", () => {
  let tmpDir;

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("excludes ignored directories", async () => {
    tmpDir = await makeFixture({
      ".gitignore": "build",
      "src/app.js": "1",
      "build/bundle.js": "2",
    });

    const gitignore = await parseGitignore(tmpDir);
    const structure = await getDirStructure(tmpDir, "", 2, 0, gitignore);
    assert.ok(structure.includes("📁 src"));
    assert.ok(!structure.includes("📁 build"));
  });

  it("excludes ignored files", async () => {
    tmpDir = await makeFixture({
      ".gitignore": "*.min.js",
      "src/app.js": "1",
      "dist/bundle.min.js": "2",
    });

    const gitignore = await parseGitignore(tmpDir);
    const structure = await getDirStructure(tmpDir, "", 2, 0, gitignore);
    assert.ok(structure.includes("📁 src"));
    assert.ok(!structure.includes("bundle.min.js"));
  });
});

describe("generateAgentsMd", () => {
  it("generates valid markdown", () => {
    const info = {
      root: "/my-project",
      pkg: { name: "my-app", version: "1.0.0" },
      entryPoints: ["index.js"],
      scripts: { dev: "node index.js" },
      deps: { express: "^4.0.0" },
      frameworks: ["Express", "React"],
      configFiles: ["tsconfig.json"],
      monorepo: false,
    };
    const langs = new Map([["JavaScript", 10]]);
    const structure = "📁 src\n  📄 index.js";

    const md = generateAgentsMd(info, langs, structure);
    assert.ok(md.includes("# AGENTS.md — my-project"));
    assert.ok(md.includes("**Package:** my-app v1.0.0"));
    assert.ok(md.includes("JavaScript (10 files)"));
    assert.ok(md.includes("**Frameworks:** Express, React"));
  });
});

describe("generateCursorRules", () => {
  it("generates cursor rules with project info", () => {
    const info = {
      root: "/my-project",
      entryPoints: ["index.js"],
      scripts: { test: "jest" },
      frameworks: ["React"],
    };
    const langs = new Map([["TypeScript", 5]]);
    const structure = "📁 src";

    const rules = generateCursorRules(info, langs, structure);
    assert.ok(rules.includes("# Context Rules for my-project"));
    assert.ok(rules.includes("- Frameworks: React"));
    assert.ok(rules.includes("- index.js"));
  });
});

describe("generateCopilotInstructions", () => {
  it("generates copilot instructions", () => {
    const info = {
      root: "/my-project",
      pkg: { name: "my-app", description: "A great app" },
      frameworks: ["Express"],
      scripts: { dev: "node index.js" },
    };

    const instr = generateCopilotInstructions(info);
    assert.ok(instr.includes("# Copilot Instructions — my-project"));
    assert.ok(instr.includes("Package: my-app — A great app"));
    assert.ok(instr.includes("Frameworks: Express"));
  });
});

describe("generateClaudeMd", () => {
  it("generates claude markdown", () => {
    const info = {
      root: "/my-project",
      pkg: { name: "my-app", version: "2.0.0" },
      scripts: { build: "tsc" },
      frameworks: ["TypeScript"],
    };
    const langs = new Map([["TypeScript", 20]]);
    const structure = "📁 src";

    const md = generateClaudeMd(info, langs, structure);
    assert.ok(md.includes("# CLAUDE.md — my-project"));
    assert.ok(md.includes("my-app v2.0.0"));
  });
});

describe("writeOrUpdate", () => {
  let tmpDir;

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("writes new file", async () => {
    tmpDir = await makeFixture({});
    const filePath = join(tmpDir, "AGENTS.md");
    await writeOrUpdate(filePath, "# Test", { dryRun: false, update: false });

    const content = await readFile(filePath, "utf8");
    assert.equal(content, "# Test");
  });

  it("dry-run does not write", async () => {
    tmpDir = await makeFixture({});
    const filePath = join(tmpDir, "AGENTS.md");

    await writeOrUpdate(filePath, "# Test", { dryRun: true, update: false });

    assert.ok(!existsSync(filePath));
  });

  it("preserves manual sections on update", async () => {
    tmpDir = await makeFixture({
      "AGENTS.md": `# AGENTS.md

<!-- context-forge:update-section conventions -->
- Use tabs
<!-- /context-forge:update-section -->
`,
    });

    const newContent = `# AGENTS.md

## Conventions

<!-- context-forge:update-section conventions -->
<!-- context-forge:update-section -->

## Notes
`;
    const filePath = join(tmpDir, "AGENTS.md");
    await writeOrUpdate(filePath, newContent, { dryRun: false, update: true });

    const content = await readFile(filePath, "utf8");
    assert.ok(content.includes("<!-- context-forge:update-section conventions -->\n- Use tabs\n<!-- /context-forge:update-section -->"));
  });
});

describe("resolvePath", () => {
  it("resolves absolute paths as-is", () => {
    const result = resolvePath("/usr/local/bin");
    assert.equal(result, "/usr/local/bin");
  });

  it("resolves relative paths from cwd", () => {
    const result = resolvePath("relative/path");
    assert.ok(result.startsWith("/"));
    assert.ok(result.endsWith("relative/path"));
  });

  it("resolves . to cwd", () => {
    const result = resolvePath(".");
    assert.ok(result.startsWith("/"));
  });
});

// ─── parseConfigFiles (F4) ──────────────────────────────────────────

describe("parseConfigFiles", () => {
  let tmpDir;

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("parses tsconfig.json", async () => {
    tmpDir = await makeFixture({
      "tsconfig.json": JSON.stringify({
        compilerOptions: {
          target: "ES2022",
          module: "ESNext",
          strict: true,
          jsx: "react-jsx",
          outDir: "./dist",
          baseUrl: "./src",
          paths: { "@/*": ["./*"], "@lib/*": ["./lib/*"] },
        },
      }),
    });

    const configs = await parseConfigFiles(tmpDir);
    assert.ok(configs.tsconfig);
    assert.equal(configs.tsconfig.target, "ES2022");
    assert.equal(configs.tsconfig.module, "ESNext");
    assert.equal(configs.tsconfig.strict, true);
    assert.equal(configs.tsconfig.jsx, "react-jsx");
    assert.equal(configs.tsconfig.outDir, "./dist");
    assert.equal(configs.tsconfig.baseUrl, "./src");
    assert.deepEqual(configs.tsconfig.paths, ["@/*", "@lib/*"]);
    assert.equal(configs.tsconfig.hasTypeChecking, true);
  });

  it("handles tsconfig with comments and trailing commas", async () => {
    tmpDir = await makeFixture({
      "tsconfig.json": `{\n  // comment\n  "compilerOptions": {\n    "target": "ES2020",\n    "strict": true,\n  }\n}\n`,
    });

    const configs = await parseConfigFiles(tmpDir);
    assert.ok(configs.tsconfig);
    assert.equal(configs.tsconfig.target, "ES2020");
    assert.equal(configs.tsconfig.strict, true);
  });

  it("parses .eslintrc.json", async () => {
    tmpDir = await makeFixture({
      ".eslintrc.json": JSON.stringify({
        env: { browser: true, node: true, es2022: true },
        parser: "@typescript-eslint/parser",
        extends: ["eslint:recommended", "plugin:@typescript-eslint/recommended"],
        rules: {
          "no-unused-vars": "warn",
          "no-console": "error",
          "prefer-const": "warn",
        },
      }),
    });

    const configs = await parseConfigFiles(tmpDir);
    assert.ok(configs.eslint);
    assert.ok(configs.eslint.env.includes("browser"));
    assert.ok(configs.eslint.env.includes("node"));
    assert.equal(configs.eslint.parser, "@typescript-eslint/parser");
    assert.equal(configs.eslint.ruleCount, 3);
    assert.ok(configs.eslint.keyRules.includes("no-unused-vars"));
  });

  it("parses .prettierrc", async () => {
    tmpDir = await makeFixture({
      ".prettierrc": JSON.stringify({
        printWidth: 100,
        tabWidth: 2,
        semi: false,
        singleQuote: true,
        trailingComma: "es5",
      }),
    });

    const configs = await parseConfigFiles(tmpDir);
    assert.ok(configs.prettier);
    assert.equal(configs.prettier.printWidth, 100);
    assert.equal(configs.prettier.tabWidth, 2);
    assert.equal(configs.prettier.semi, false);
    assert.equal(configs.prettier.singleQuote, true);
    assert.equal(configs.prettier.trailingComma, "es5");
  });

  it("detects vite/webpack/tailwind config presence", async () => {
    tmpDir = await makeFixture({
      "vite.config.js": "export default {};",
      "tailwind.config.js": "module.exports = {};",
    });

    const configs = await parseConfigFiles(tmpDir);
    assert.ok(configs.vite);
    assert.equal(configs.vite.file, "vite.config.js");
    assert.ok(configs.tailwind);
    assert.equal(configs.tailwind.file, "tailwind.config.js");
    assert.ok(!configs.webpack);
  });

  it("parses Dockerfile", async () => {
    tmpDir = await makeFixture({
      "Dockerfile": "FROM node:18-alpine\nWORKDIR /app\nCOPY . .\nCMD [\"node\", \"index.js\"]",
    });

    const configs = await parseConfigFiles(tmpDir);
    assert.ok(configs.docker);
    assert.equal(configs.docker.baseImage, "node:18-alpine");
    assert.equal(configs.docker.hasMultiStage, false);
  });

  it("detects multi-stage Dockerfile", async () => {
    tmpDir = await makeFixture({
      "Dockerfile": "FROM node:18 AS build\nRUN npm run build\nFROM nginx:alpine\nCOPY --from=build /dist /usr/share/nginx/html",
    });

    const configs = await parseConfigFiles(tmpDir);
    assert.ok(configs.docker);
    assert.equal(configs.docker.hasMultiStage, true);
  });

  it("returns empty object when no config files exist", async () => {
    tmpDir = await makeFixture({
      "README.md": "# project",
    });

    const configs = await parseConfigFiles(tmpDir);
    assert.deepEqual(configs, {});
  });

  it("handles multiple config files at once", async () => {
    tmpDir = await makeFixture({
      "tsconfig.json": JSON.stringify({ compilerOptions: { target: "ES2022", strict: true } }),
      ".eslintrc.json": JSON.stringify({ env: { node: true }, rules: { "no-console": "error" } }),
      ".prettierrc": JSON.stringify({ printWidth: 80 }),
      "Dockerfile": "FROM node:18",
      "vite.config.ts": "export default {}",
    });

    const configs = await parseConfigFiles(tmpDir);
    assert.ok(configs.tsconfig);
    assert.ok(configs.eslint);
    assert.ok(configs.prettier);
    assert.ok(configs.docker);
    assert.ok(configs.vite);
  });
});