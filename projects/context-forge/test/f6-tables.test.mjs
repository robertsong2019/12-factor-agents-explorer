import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  generateAgentsMd,
  generateCursorRules,
  generateClaudeMd,
  formatScriptsTable,
  formatDepsTable,
} from "../context-forge.mjs";

// ─── F6: Markdown Tables ─────────────────────────────────────────

describe("F6: formatScriptsTable", () => {
  it("formats scripts as markdown table", () => {
    const result = formatScriptsTable({ test: "node --test", build: "tsc" });
    assert.ok(result.includes("| Script | Command |"));
    assert.ok(result.includes("|--------|---------|"));
    assert.ok(result.includes("| `test` | node --test |"));
    assert.ok(result.includes("| `build` | tsc |"));
  });

  it("returns placeholder for empty scripts", () => {
    assert.equal(formatScriptsTable({}), "- (none defined)");
  });

  it("respects max parameter", () => {
    const scripts = {};
    for (let i = 0; i < 25; i++) scripts[`s${i}`] = `cmd${i}`;
    const result = formatScriptsTable(scripts, 10);
    assert.ok(result.includes("_15 more_"));
    assert.ok(!result.includes("| `s24`"));
  });

  it("handles scripts with special characters", () => {
    const result = formatScriptsTable({ lint: "eslint --fix \"src/**/*.ts\"" });
    assert.ok(result.includes("| `lint` | eslint --fix \"src/**/*.ts\" |"));
  });

  it("default max is 20", () => {
    const scripts = {};
    for (let i = 0; i < 30; i++) scripts[`s${i}`] = `cmd${i}`;
    const result = formatScriptsTable(scripts);
    assert.ok(result.includes("_10 more_"));
  });
});

describe("F6: formatDepsTable", () => {
  it("formats dependencies as markdown table", () => {
    const result = formatDepsTable({ express: "^4.18.0", lodash: "^4.17.21" });
    assert.ok(result.includes("| Package | Version |"));
    assert.ok(result.includes("|---------|---------|"));
    assert.ok(result.includes("| `express` | ^4.18.0 |"));
    assert.ok(result.includes("| `lodash` | ^4.17.21 |"));
  });

  it("returns placeholder for empty deps", () => {
    assert.equal(formatDepsTable({}), "- (none)");
  });

  it("respects max parameter", () => {
    const deps = {};
    for (let i = 0; i < 25; i++) deps[`pkg${i}`] = `^1.${i}.0`;
    const result = formatDepsTable(deps, 5);
    assert.ok(result.includes("_20 more_"));
  });

  it("handles scoped package names", () => {
    const result = formatDepsTable({ "@types/node": "^20.0.0" });
    assert.ok(result.includes("| `@types/node` | ^20.0.0 |"));
  });

  it("default max is 20", () => {
    const deps = {};
    for (let i = 0; i < 25; i++) deps[`p${i}`] = `^1.0.${i}`;
    const result = formatDepsTable(deps);
    assert.ok(result.includes("_5 more_"));
  });

  it("generates valid table with single entry", () => {
    const result = formatDepsTable({ react: "^18.0.0" });
    const lines = result.split("\n");
    assert.equal(lines[0], "| Package | Version |");
    assert.equal(lines[1], "|---------|---------|");
    assert.equal(lines[2], "| `react` | ^18.0.0 |");
  });
});

describe("F6: table integration in generators", () => {
  it("generateAgentsMd uses table format for scripts", () => {
    const info = {
      root: "/tmp/test", pkg: { name: "test" }, scripts: { dev: "vite" },
      deps: { vite: "^5.0.0" }, entryPoints: ["src/index.ts"], frameworks: [],
    };
    const md = generateAgentsMd(info, new Map([["TypeScript", 1000]]), ".");
    assert.ok(md.includes("| Script | Command |"), "should contain script table header");
    assert.ok(md.includes("| Package | Version |"), "should contain deps table header");
    assert.ok(!md.includes("- `npm run dev` →"), "should not use old bullet format");
  });

  it("generateCursorRules uses table format for scripts", () => {
    const info = {
      root: "/tmp/test", pkg: { name: "test" }, scripts: { build: "tsc" },
      deps: {}, entryPoints: [], frameworks: [],
    };
    const md = generateCursorRules(info, new Map([["TypeScript", 500]]), ".");
    assert.ok(md.includes("| Script | Command |"), "cursor rules should use table format");
  });

  it("generateClaudeMd uses table format for commands", () => {
    const info = {
      root: "/tmp/test", pkg: { name: "test", version: "1.0.0" }, scripts: { test: "jest" },
      deps: {}, entryPoints: [], frameworks: [],
    };
    const md = generateClaudeMd(info, new Map([["JavaScript", 500]]), ".");
    assert.ok(md.includes("| Script | Command |"), "claude md should use table format");
  });
});
