import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm, mkdir, writeFile, readFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
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

// ─── detectProject ────────────────────────────────────────────────

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
      "pyproject.toml": `[project]
name = "myapp"
dependencies = ["fastapi", "flask"]`,
      "main.py": "print('hello')",
    });

    const info = await detectProject(tmpDir);
    assert.ok(info.frameworks.includes("Python"));
    assert.ok(info.frameworks.includes("FastAPI"));
    assert.ok(info.frameworks.includes("Flask"));
  });

  it("detects Rust project via Cargo.toml", async () => {
    tmpDir = await makeFixture({
      "Cargo.toml": `[package]
name = "myapp"
[dependencies]
tokio = "1"
clap = "4"`,
    });

    const info = await detectProject(tmpDir);
    assert.ok(info.frameworks.includes("Rust/Cargo"));
    assert.ok(info.frameworks.includes("Tokio"));
    assert.ok(info.frameworks.includes("Clap CLI"));
  });

  it("detects Go project via go.mod", async () => {
    tmpDir = await makeFixture({
      "go.mod": "module github.com/test/myapp\n\ngo 1.21",
    });

    const info = await detectProject(tmpDir);
    assert.ok(info.frameworks.includes("Go Modules"));
  });

  it("detects Docker from Dockerfile", async () => {
    tmpDir = await makeFixture({
      "Dockerfile": "FROM node:18\nCMD [\"node\", \"index.js\"]",
    });

    const info = await detectProject(tmpDir);
    assert.ok(info.frameworks.includes("Docker"));
  });

  it("detects monorepo", async () => {
    tmpDir = await makeFixture({
      "package.json": JSON.stringify({ name: "monorepo-root" }),
      "pnpm-workspace.yaml": "packages:\n  - packages/*",
    });

    const info = await detectProject(tmpDir);
    assert.equal(info.monorepo, true);
    assert.ok(info.frameworks.includes("Monorepo"));
  });

  it("detects config files", async () => {
    tmpDir = await makeFixture({
      "package.json": "{}",
      "tsconfig.json": "{}",
      ".eslintrc.json": "{}",
      ".prettierrc": "{}",
    });

    const info = await detectProject(tmpDir);
    assert.ok(info.configFiles.includes("tsconfig.json"));
    assert.ok(info.configFiles.includes(".eslintrc.json"));
    assert.ok(info.configFiles.includes(".prettierrc"));
  });

  it("handles empty directory gracefully", async () => {
    tmpDir = await mkdtemp(join(tmpdir(), "ctxforge-"));
    const info = await detectProject(tmpDir);
    assert.equal(info.pkg, undefined);
    assert.deepEqual(info.entryPoints, []);
    assert.deepEqual(info.scripts, {});
  });

  it("handles malformed package.json", async () => {
    tmpDir = await makeFixture({
      "package.json": "{ broken json",
    });

    const info = await detectProject(tmpDir);
    // Should not crash, just skip parsing
    assert.equal(info.pkg, undefined);
  });
});

// ─── scanLanguages ───────────────────────────────────────────────

describe("scanLanguages", () => {
  let tmpDir;

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("counts files by language", async () => {
    tmpDir = await makeFixture({
      "a.js": "",
      "b.js": "",
      "c.ts": "",
      "d.py": "",
      "e.go": "",
    });

    const langs = await scanLanguages(tmpDir);
    assert.equal(langs.get("JavaScript"), 2);
    assert.equal(langs.get("TypeScript"), 1);
    assert.equal(langs.get("Python"), 1);
    assert.equal(langs.get("Go"), 1);
  });

  it("ignores node_modules and .git", async () => {
    tmpDir = await makeFixture({
      "real.js": "",
      "node_modules/fake.js": "",
      ".git/secret.js": "",
      "dist/build.js": "",
    });

    const langs = await scanLanguages(tmpDir);
    assert.equal(langs.get("JavaScript"), 1);
  });

  it("ignores hidden directories", async () => {
    tmpDir = await makeFixture({
      "visible.ts": "",
      ".hidden/secret.ts": "",
    });

    const langs = await scanLanguages(tmpDir);
    assert.equal(langs.get("TypeScript"), 1);
  });

  it("respects maxDepth", async () => {
    tmpDir = await makeFixture({
      "top.py": "",
      "sub/deep.py": "",
      "sub/nested/very/deep.py": "",
    });

    const depth1 = await scanLanguages(tmpDir, 1);
    const depth4 = await scanLanguages(tmpDir, 4);
    assert.equal(depth1.get("Python"), 1);
    assert.equal(depth4.get("Python"), 3);
  });

  it("returns empty map for non-existent directory", async () => {
    const langs = await scanLanguages("/nonexistent/path/xyz");
    assert.equal(langs.size, 0);
  });
});

// ─── getDirStructure ─────────────────────────────────────────────

describe("getDirStructure", () => {
  let tmpDir;

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("lists directories and files", async () => {
    tmpDir = await makeFixture({
      "file1.js": "",
      "dir1/file2.ts": "",
    });

    const structure = await getDirStructure(tmpDir);
    assert.ok(structure.includes("dir1"));
    assert.ok(structure.includes("file1.js"));
    assert.ok(structure.includes("file2.ts"));
  });

  it("sorts directories first", async () => {
    tmpDir = await makeFixture({
      "zfile.js": "",
      "adir/file.ts": "",
    });

    const structure = await getDirStructure(tmpDir);
    const dirIdx = structure.indexOf("adir");
    const fileIdx = structure.indexOf("zfile.js");
    assert.ok(dirIdx < fileIdx);
  });

  it("respects maxDepth", async () => {
    tmpDir = await makeFixture({
      "top.js": "",
      "d1/d2/deep.js": "",
    });

    const s1 = await getDirStructure(tmpDir, "", 1);
    assert.ok(s1.includes("top.js"));
    assert.ok(!s1.includes("deep.js"));
  });

  it("ignores IGNORE_DIRS", async () => {
    tmpDir = await makeFixture({
      "real.js": "",
      "node_modules/nm.js": "",
      ".git/config.js": "",
    });

    const structure = await getDirStructure(tmpDir);
    assert.ok(!structure.includes("node_modules"));
    assert.ok(!structure.includes(".git"));
    assert.ok(structure.includes("real.js"));
  });
});

// ─── Generator functions ─────────────────────────────────────────

describe("generateAgentsMd", () => {
  const mockInfo = {
    root: "/fake/myproject",
    pkg: { name: "myproject", version: "2.0.0" },
    frameworks: ["Express", "React"],
    entryPoints: ["index.js"],
    scripts: { start: "node index.js", test: "jest" },
    deps: { express: "^4.0.0", react: "^18.0.0" },
    configFiles: ["tsconfig.json"],
  };
  const mockLangs = new Map([["JavaScript", 5], ["TypeScript", 3]]);
  const mockStructure = "📁 src\n  📄 index.js\n";

  it("includes project name in title", () => {
    const md = generateAgentsMd(mockInfo, mockLangs, mockStructure);
    assert.ok(md.includes("# AGENTS.md — myproject"));
  });

  it("lists primary language with file count", () => {
    const md = generateAgentsMd(mockInfo, mockLangs, mockStructure);
    assert.ok(md.includes("JavaScript (5 files)"));
  });

  it("includes framework list", () => {
    const md = generateAgentsMd(mockInfo, mockLangs, mockStructure);
    assert.ok(md.includes("Express"));
    assert.ok(md.includes("React"));
  });

  it("includes entry points", () => {
    const md = generateAgentsMd(mockInfo, mockLangs, mockStructure);
    assert.ok(md.includes("`index.js`"));
  });

  it("includes scripts", () => {
    const md = generateAgentsMd(mockInfo, mockLangs, mockStructure);
    assert.ok(md.includes("npm run start"));
    assert.ok(md.includes("npm run test"));
  });

  it("includes update-section markers", () => {
    const md = generateAgentsMd(mockInfo, mockLangs, mockStructure);
    assert.ok(md.includes("context-forge:update-section conventions"));
    assert.ok(md.includes("context-forge:update-section architecture"));
    assert.ok(md.includes("context-forge:update-section notes"));
  });

  it("handles minimal info (no pkg)", () => {
    const minimal = { root: "/fake/x", frameworks: [], entryPoints: [], scripts: {}, deps: {}, configFiles: [] };
    const md = generateAgentsMd(minimal, new Map(), "");
    assert.ok(md.includes("# AGENTS.md — x"));
    assert.ok(md.includes("Unknown"));
  });

  it("truncates deps over 15", () => {
    const bigDeps = {};
    for (let i = 0; i < 20; i++) bigDeps[`dep${i}`] = "^1.0.0";
    const info = { ...mockInfo, deps: bigDeps };
    const md = generateAgentsMd(info, mockLangs, mockStructure);
    assert.ok(md.includes("5 more)"));
  });
});

describe("generateCursorRules", () => {
  const mockInfo = {
    root: "/fake/proj",
    frameworks: ["Next.js"],
    entryPoints: ["app/layout.tsx"],
    scripts: { test: "jest" },
  };
  const mockLangs = new Map([["TypeScript (React)", 10]]);

  it("includes project name", () => {
    const rules = generateCursorRules(mockInfo, mockLangs, "");
    assert.ok(rules.includes("proj"));
  });

  it("includes primary language", () => {
    const rules = generateCursorRules(mockInfo, mockLangs, "");
    assert.ok(rules.includes("TypeScript (React)"));
  });

  it("includes frameworks", () => {
    const rules = generateCursorRules(mockInfo, mockLangs, "");
    assert.ok(rules.includes("Next.js"));
  });

  it("includes test command", () => {
    const rules = generateCursorRules(mockInfo, mockLangs, "");
    assert.ok(rules.includes("jest"));
  });
});

describe("generateCopilotInstructions", () => {
  it("includes package name and description", () => {
    const info = {
      root: "/fake/p",
      pkg: { name: "my-lib", description: "A cool lib" },
      frameworks: ["Express"],
      scripts: { build: "tsc" },
    };
    const result = generateCopilotInstructions(info);
    assert.ok(result.includes("my-lib"));
    assert.ok(result.includes("A cool lib"));
    assert.ok(result.includes("Express"));
    assert.ok(result.includes("npm run build"));
  });

  it("handles missing pkg", () => {
    const info = { root: "/fake/basename-test", frameworks: [], scripts: {} };
    const result = generateCopilotInstructions(info);
    assert.ok(result.includes("basename-test"));
  });
});

describe("generateClaudeMd", () => {
  it("generates with package info", () => {
    const info = {
      root: "/fake/claude-proj",
      pkg: { name: "claude-test", version: "3.0.0", description: "Test desc" },
      frameworks: ["FastAPI"],
      scripts: { dev: "uvicorn main:app" },
    };
    const langs = new Map([["Python", 8]]);
    const md = generateClaudeMd(info, langs, "📁 src\n");
    assert.ok(md.includes("claude-test"));
    assert.ok(md.includes("3.0.0"));
    assert.ok(md.includes("Python"));
    assert.ok(md.includes("FastAPI"));
  });

  it("handles no package", () => {
    const info = { root: "/fake/nopkg", frameworks: [], scripts: {} };
    const md = generateClaudeMd(info, new Map(), "");
    assert.ok(md.includes("nopkg"));
  });
});

// ─── writeOrUpdate ───────────────────────────────────────────────

describe("writeOrUpdate", () => {
  let tmpDir;
  let origLog;

  beforeEach(() => { 
    tmpDir = null; 
    origLog = console.log;
    console.log = () => {};
  });
  afterEach(async () => {
    console.log = origLog;
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("writes new file", async () => {
    tmpDir = await mkdtemp(join(tmpdir(), "ctxforge-"));
    const filePath = join(tmpDir, "output.md");
    await writeOrUpdate(filePath, "# Hello", { dryRun: false, update: false });
    const content = await readFile(filePath, "utf8");
    assert.equal(content, "# Hello");
  });

  it("creates parent directories", async () => {
    tmpDir = await mkdtemp(join(tmpdir(), "ctxforge-"));
    const filePath = join(tmpDir, "nested/deep/dir/file.md");
    await writeOrUpdate(filePath, "# Nested", { dryRun: false, update: false });
    const content = await readFile(filePath, "utf8");
    assert.equal(content, "# Nested");
  });

  it("dry run outputs to stdout but does not write", async () => {
    tmpDir = await mkdtemp(join(tmpdir(), "ctxforge-"));
    const filePath = join(tmpDir, "dry.md");
    await writeOrUpdate(filePath, "# Dry", { dryRun: true, update: false });
    await assert.rejects(() => readFile(filePath, "utf8"));
  });

  it("update preserves manual sections", async () => {
    tmpDir = await mkdtemp(join(tmpdir(), "ctxforge-"));
    const filePath = join(tmpDir, "preserve.md");
    const existing = `# Doc\n\n<!-- context-forge:update-section conventions -->\nMy custom conventions\n<!-- /context-forge:update-section -->\n`;
    await writeFile(filePath, existing);

    const newContent = `# Doc\n\n<!-- context-forge:update-section conventions -->\nAuto-generated\n<!-- /context-forge:update-section -->\n`;
    await writeOrUpdate(filePath, newContent, { dryRun: false, update: true });

    const result = await readFile(filePath, "utf8");
    assert.ok(result.includes("My custom conventions"));
    assert.ok(!result.includes("Auto-generated"));
  });

  it("overwrite without update flag", async () => {
    tmpDir = await mkdtemp(join(tmpdir(), "ctxforge-"));
    const filePath = join(tmpDir, "overwrite.md");
    await writeFile(filePath, "old content");
    await writeOrUpdate(filePath, "new content", { dryRun: false, update: false });
    const result = await readFile(filePath, "utf8");
    assert.equal(result, "new content");
  });
});

// ─── resolvePath ─────────────────────────────────────────────────

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
