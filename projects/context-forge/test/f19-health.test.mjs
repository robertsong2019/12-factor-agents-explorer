import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { computeHealthScore } from "../context-forge.mjs";

describe("computeHealthScore", () => {
  it("returns high score for healthy project", () => {
    const info = {
      entryPoints: ["index.js"],
      scripts: { test: "node --test", build: "tsc" },
      dependencies: { lodash: "4" },
      pkg: {},
    };
    const langs = new Map([["JavaScript", 10]]);
    const importData = { allImports: ["fs"] };
    const apiSurface = [{ name: "foo" }];
    const configData = { eslint: {} };
    const result = computeHealthScore(info, langs, importData, apiSurface, configData, []);
    assert.ok(result.score >= 87, `expected >=87, got ${result.score}`);
    assert.equal(result.grade, 'A');
    assert.equal(result.total, 8);
    assert.equal(result.passed, 8);
  });

  it("returns low score for empty project", () => {
    const info = { entryPoints: [], scripts: {}, dependencies: {}, pkg: {} };
    const result = computeHealthScore(info, new Map(), { allImports: [] }, [], {}, []);
    assert.ok(result.score < 50, `expected <50, got ${result.score}`);
    assert.ok(['D', 'F'].includes(result.grade));
  });

  it("deducts points for validation errors", () => {
    const info = {
      entryPoints: ["index.js"],
      scripts: { test: "x" },
      dependencies: { dep: "1" },
      pkg: {},
    };
    const langs = new Map([["JavaScript", 5]]);
    const apiSurface = [{ name: "f" }];
    const configData = { eslint: {} };
    const errors = [{ severity: "error", message: "bad" }];
    const result = computeHealthScore(info, langs, { allImports: [] }, apiSurface, configData, errors);
    assert.ok(!result.checks.find(c => c.name === 'noErrors').passed);
    assert.ok(result.score < 100);
  });

  it("deducts points for warnings", () => {
    const info = {
      entryPoints: ["index.js"],
      scripts: { test: "x" },
      dependencies: { dep: "1" },
      pkg: {},
    };
    const langs = new Map([["JavaScript", 5]]);
    const apiSurface = [{ name: "f" }];
    const configData = { eslint: {} };
    const warnings = [{ severity: "warning", message: "meh" }];
    const result = computeHealthScore(info, langs, { allImports: [] }, apiSurface, configData, warnings);
    assert.ok(!result.checks.find(c => c.name === 'noWarnings').passed);
    assert.ok(result.score < 100);
  });

  it("assigns correct grades", () => {
    // F grade (0-24): no entry points, no scripts, no deps, no langs, no configs, no api, with errors+warnings
    const f = computeHealthScore(
      { entryPoints: [], scripts: {}, dependencies: {}, pkg: {} },
      new Map(), { allImports: [] }, [], {},
      [{ severity: "error" }, { severity: "warning" }]
    );
    assert.equal(f.grade, 'F');
    assert.ok(f.score < 25);

    // At least C grade (50-74): has some checks passing
    const c = computeHealthScore(
      { entryPoints: ["i"], scripts: {}, dependencies: {}, pkg: {} },
      new Map([["JS", 1]]), { allImports: [] }, [], {},
      [{ severity: "error" }, { severity: "warning" }]
    );
    // entryPoints + noErrors fail, noWarnings fail -> languages fail(no...wait)
    // entryPoints pass, scripts fail, deps fail, noErrors fail, noWarnings fail, languages pass, configs fail, api fail
    // 2/8 pass = 25% = D
    assert.ok(c.score >= 25, `c score ${c.score}`);
  });

  it("reads from pkg fallback when direct fields missing", () => {
    const info = {
      entryPoints: ["index.js"],
      pkg: {
        scripts: { build: "tsc" },
        dependencies: { express: "4" },
      },
    };
    const langs = new Map([["JavaScript", 3]]);
    const apiSurface = [{ name: "x" }];
    const configData = { tsconfig: {} };
    const result = computeHealthScore(info, langs, { allImports: [] }, apiSurface, configData, []);
    assert.ok(result.checks.find(c => c.name === 'scripts').passed);
    assert.ok(result.checks.find(c => c.name === 'dependencies').passed);
  });

  it("includes detail strings for each check", () => {
    const result = computeHealthScore(
      { entryPoints: ["a.js"], scripts: { x: "y" }, dependencies: { d: "1" }, pkg: {} },
      new Map([["JS", 1]]), { allImports: [] }, [{ name: "f" }], { cfg: {} }, []
    );
    for (const check of result.checks) {
      assert.ok(typeof check.detail === 'string');
      assert.ok(check.detail.length > 0);
    }
  });

  it("handles undefined validationIssues gracefully", () => {
    const result = computeHealthScore(
      { entryPoints: [], scripts: {}, dependencies: {}, pkg: {} },
      new Map(), { allImports: [] }, [], {}
    );
    assert.ok(result.score >= 0);
  });

  it("counts passing checks correctly", () => {
    const info = { entryPoints: ["a"], scripts: { x: "y" }, dependencies: { d: "1" }, pkg: {} };
    const langs = new Map([["JS", 1]]);
    const apiSurface = [{ name: "f" }];
    const configData = { cfg: {} };
    const result = computeHealthScore(info, langs, { allImports: [] }, apiSurface, configData, []);
    assert.equal(result.passed, 8);
    assert.equal(result.total, 8);
    // Verify each check has name, passed, detail
    for (const c of result.checks) {
      assert.ok('name' in c);
      assert.ok('passed' in c);
      assert.ok('detail' in c);
    }
  });
});
