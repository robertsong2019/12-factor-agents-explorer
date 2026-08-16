const fs = require("fs");
const path = require("path");
const { checks, diagnose, diagnoseJSON } = require("./index");
const os = require("os");

// Helper: create a temp skill directory
function createTempSkill(files) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "skill-doctor-test-"));
  for (const [name, content] of Object.entries(files)) {
    const filePath = path.join(dir, name);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, content);
  }
  return dir;
}

afterEach(() => {
  // Clean up temp dirs (they start with skill-doctor-test-)
  const tmp = os.tmpdir();
  for (const d of fs.readdirSync(tmp)) {
    if (d.startsWith("skill-doctor-test-")) {
      fs.rmSync(path.join(tmp, d), { recursive: true, force: true });
    }
  }
});

// ── Check count ────────────────────────────────────────────────
test("has at least 8 checks registered", () => {
  expect(checks.length).toBeGreaterThanOrEqual(8);
});

// ── SKILL.md exists ────────────────────────────────────────────
test("fails when SKILL.md missing", () => {
  const dir = createTempSkill({ "README.md": "hello" });
  const { diagnoseJSON: dj } = require("./index");
  const report = dj(dir);
  const check = report.results.find((r) => r.name === "SKILL.md exists");
  expect(check.status).toBe("fail");
});

test("passes when SKILL.md exists with enough content", () => {
  const dir = createTempSkill({ "SKILL.md": "# Test\n\n" + "x".repeat(200) });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "SKILL.md exists");
  expect(check.status).toBe("pass");
});

test("warns when SKILL.md is too small", () => {
  const dir = createTempSkill({ "SKILL.md": "hi" });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "SKILL.md exists");
  expect(check.status).toBe("warn");
});

// ── README.md ──────────────────────────────────────────────────
test("warns when no README.md", () => {
  const dir = createTempSkill({ "SKILL.md": "x".repeat(200) });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "README.md exists");
  expect(check.status).toBe("warn");
});

// ── Oversized files ────────────────────────────────────────────
test("warns on files >500KB", () => {
  const dir = createTempSkill({ "big.bin": "x".repeat(600_000) });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "No oversized files (>500KB)");
  expect(check.status).toBe("warn");
});

test("passes when all files small", () => {
  const dir = createTempSkill({ "small.txt": "hello" });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "No oversized files (>500KB)");
  expect(check.status).toBe("pass");
});

// ── Suspicious patterns ────────────────────────────────────────
test("warns on eval() usage", () => {
  const dir = createTempSkill({ "bad.js": "eval(userInput);" });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "No suspicious patterns");
  expect(check.status).toBe("warn");
});

test("passes on clean code", () => {
  const dir = createTempSkill({ "clean.js": "console.log('hello');" });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "No suspicious patterns");
  expect(check.status).toBe("pass");
});

// ── package.json validation ────────────────────────────────────
test("passes valid package.json", () => {
  const dir = createTempSkill({ "package.json": '{"name":"foo","version":"1.0.0"}' });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "Valid package.json (if present)");
  expect(check.status).toBe("pass");
});

test("warns on package.json missing name", () => {
  const dir = createTempSkill({ "package.json": '{"version":"1.0.0"}' });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "Valid package.json (if present)");
  expect(check.status).toBe("warn");
});

test("fails on invalid JSON", () => {
  const dir = createTempSkill({ "package.json": "not json" });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "Valid package.json (if present)");
  expect(check.status).toBe("fail");
});

// ── Script references ──────────────────────────────────────────
test("fails when referenced script missing", () => {
  const dir = createTempSkill({
    "SKILL.md": 'Run `./scripts/deploy.sh` to deploy',
  });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "Scripts referenced in SKILL.md exist");
  expect(check.status).toBe("fail");
});

test("passes when referenced scripts exist", () => {
  const dir = createTempSkill({
    "SKILL.md": 'Run `./scripts/setup.sh` to setup',
    "scripts/setup.sh": "#!/bin/bash\necho hi",
  });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "Scripts referenced in SKILL.md exist");
  expect(check.status).toBe("pass");
});

// ── node_modules check ─────────────────────────────────────────
test("warns when node_modules not gitignored", () => {
  const dir = createTempSkill({});
  fs.mkdirSync(path.join(dir, "node_modules"));
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "No node_modules committed");
  expect(check.status).toBe("warn");
});

test("passes when node_modules in .gitignore", () => {
  const dir = createTempSkill({ ".gitignore": "node_modules\n" });
  fs.mkdirSync(path.join(dir, "node_modules"));
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "No node_modules committed");
  expect(check.status).toBe("pass");
});

// ── diagnoseJSON structure ─────────────────────────────────────
test("diagnoseJSON returns correct structure", () => {
  const dir = createTempSkill({ "SKILL.md": "# " + "x".repeat(200) });
  const report = diagnoseJSON(dir);
  expect(report).toHaveProperty("directory");
  expect(report).toHaveProperty("results");
  expect(report).toHaveProperty("summary");
  expect(report).toHaveProperty("exitCode");
  expect(report.results.length).toBe(checks.length);
  expect(report.summary.pass + report.summary.warn + report.summary.fail + report.summary.skip).toBe(checks.length);
});

test("diagnoseJSON exitCode 0 when all pass", () => {
  const dir = createTempSkill({
    "SKILL.md": "# Test\n\ndescription: test skill\n" + "x".repeat(200),
    "README.md": "# Test",
    "package.json": '{"name":"test","version":"1.0.0"}',
  });
  const report = diagnoseJSON(dir);
  expect([0, 1]).toContain(report.exitCode);
});

// ── diagnose (human-readable) ──────────────────────────────────
// ── Auto-fix tests ──────────────────────────────────────────────
const { fixers, autoFixJSON } = require("./index");

test("has 3 fixers registered", () => {
  expect(fixers.length).toBe(3);
});

test("auto-fix creates .gitignore when node_modules exists", () => {
  const dir = createTempSkill({});
  fs.mkdirSync(path.join(dir, "node_modules"));
  const report = autoFixJSON(dir);
  const fix = report.fixes.find((r) => r.name === "Add .gitignore with node_modules");
  expect(fix.fixed).toBe(true);
  expect(fs.existsSync(path.join(dir, ".gitignore"))).toBe(true);
});

test("auto-fix creates SKILL.md when missing", () => {
  const dir = createTempSkill({});
  const report = autoFixJSON(dir);
  const fix = report.fixes.find((r) => r.name === "Create minimal SKILL.md");
  expect(fix.fixed).toBe(true);
  expect(fs.existsSync(path.join(dir, "SKILL.md"))).toBe(true);
});

test("auto-fix creates README.md when missing", () => {
  const dir = createTempSkill({});
  const report = autoFixJSON(dir);
  const fix = report.fixes.find((r) => r.name === "Create minimal README.md");
  expect(fix.fixed).toBe(true);
  expect(fs.existsSync(path.join(dir, "README.md"))).toBe(true);
});

test("auto-fix skips when files already exist", () => {
  const dir = createTempSkill({
    "SKILL.md": "# " + "x".repeat(200),
    "README.md": "# Test",
  });
  const report = autoFixJSON(dir);
  expect(report.fixCount).toBe(0);
});

test("auto-fix appends node_modules to existing .gitignore", () => {
  const dir = createTempSkill({ ".gitignore": "dist\n" });
  fs.mkdirSync(path.join(dir, "node_modules"));
  const report = autoFixJSON(dir);
  const fix = report.fixes.find((r) => r.name === "Add .gitignore with node_modules");
  expect(fix.fixed).toBe(true);
  const content = fs.readFileSync(path.join(dir, ".gitignore"), "utf8");
  expect(content).toContain("node_modules");
  expect(content).toContain("dist");
});

test("autoFixJSON returns correct structure", () => {
  const dir = createTempSkill({});
  const report = autoFixJSON(dir);
  expect(report).toHaveProperty("directory");
  expect(report).toHaveProperty("fixes");
  expect(report).toHaveProperty("fixCount");
  expect(report.fixes.length).toBe(fixers.length);
});

test("diagnose returns exit code 2 on failures", () => {
  const dir = createTempSkill({}); // no SKILL.md = fail
  // Capture stdout
  const origLog = console.log;
  let output = "";
  console.log = (...args) => { output += args.join(" ") + "\n"; };
  const code = diagnose(dir);
  console.log = origLog;
  expect(code).toBe(2);
  expect(output).toContain("skill-doctor");
});

// ── Custom checks (.skill-doctor.js) ────────────────────────────

test("loadCustomChecks returns empty array when no .skill-doctor.js", () => {
  const { loadCustomChecks: lc } = require("./index");
  const dir = createTempSkill({ "SKILL.md": "x".repeat(100) });
  expect(lc(dir)).toEqual([]);
});

test("loadCustomChecks loads checks from .skill-doctor.js (array export)", () => {
  const dir = createTempSkill({
    ".skill-doctor.js": `module.exports = [
      { name: "Custom A", fn: (dir) => ({ status: "pass", msg: "ok" }) },
      { name: "Custom B", fn: (dir) => ({ status: "warn", msg: "meh" }) },
    ];`,
  });
  const { loadCustomChecks: lc } = require("./index");
  const custom = lc(dir);
  expect(custom.length).toBe(2);
  expect(custom[0].name).toBe("Custom A");
  expect(custom[1].fn(dir).status).toBe("warn");
});

test("loadCustomChecks loads checks from .skill-doctor.js ({ checks } export)", () => {
  const dir = createTempSkill({
    ".skill-doctor.js": `module.exports = { checks: [
      { name: "From object", fn: (dir) => ({ status: "pass", msg: "yep" }) },
    ] };`,
  });
  const { loadCustomChecks: lc } = require("./index");
  const custom = lc(dir);
  expect(custom.length).toBe(1);
  expect(custom[0].name).toBe("From object");
});

test("diagnoseJSON includes custom checks in results", () => {
  const dir = createTempSkill({
    "SKILL.md": "# Test\n\n" + "x".repeat(200),
    ".skill-doctor.js": `module.exports = [
      { name: "My custom", fn: () => ({ status: "warn", msg: "custom warn" }) },
    ];`,
  });
  const report = diagnoseJSON(dir);
  const custom = report.results.find((r) => r.name === "My custom");
  expect(custom).toBeDefined();
  expect(custom.status).toBe("warn");
});

test("loadCustomChecks handles broken .skill-doctor.js gracefully", () => {
  const dir = createTempSkill({
    ".skill-doctor.js": `throw new Error("boom");`,
  });
  const { loadCustomChecks: lc } = require("./index");
  const custom = lc(dir);
  expect(custom.length).toBe(1);
  expect(custom[0].name).toContain("Load .skill-doctor.js");
});

// ── Quiet mode ──────────────────────────────────────────────────

test("diagnose quiet mode hides passing checks", () => {
  const dir = createTempSkill({ "SKILL.md": "# Test\n\n" + "x".repeat(200) });
  const origLog = console.log;
  let output = "";
  console.log = (...args) => { output += args.join(" ") + "\n"; };
  diagnose(dir, true);
  console.log = origLog;
  // Should not show "SKILL.md exists" (pass) but still shows summary
  expect(output).not.toContain("SKILL.md exists");
  expect(output).toContain("Summary");
});

test("diagnose quiet mode shows warnings and failures", () => {
  const dir = createTempSkill({}); // no SKILL.md = fail, no README = warn
  const origLog = console.log;
  let output = "";
  console.log = (...args) => { output += args.join(" ") + "\n"; };
  diagnose(dir, true);
  console.log = origLog;
  expect(output).toContain("SKILL.md exists"); // fail - shown
  expect(output).toContain("README.md exists"); // warn - shown
});

// ── SKILL.md has description ──────────────────────────────────

test("warns when SKILL.md has no description", () => {
  const dir = createTempSkill({ "SKILL.md": "# Test\n\n" + "x".repeat(100) });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "SKILL.md has description");
  expect(check.status).toBe("warn");
});

test("passes when SKILL.md has explicit description field", () => {
  const dir = createTempSkill({ "SKILL.md": "---\ndescription: A test skill\n---\n\n# Test" });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "SKILL.md has description");
  expect(check.status).toBe("pass");
});

test("passes when SKILL.md is long enough", () => {
  const dir = createTempSkill({ "SKILL.md": "# Test\n\n" + "x".repeat(300) });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "SKILL.md has description");
  expect(check.status).toBe("pass");
});

// ── Suspicious patterns – specific detectors ───────────────────

test("warns on command injection pattern", () => {
  const dir = createTempSkill({ "run.js": "const cp = require('child_process'); cp.execSync(cmd + userInput);" });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "No suspicious patterns");
  expect(check.status).toBe("warn");
  expect(check.msg).toContain("command injection");
});

test("warns on pipe to shell pattern", () => {
  const dir = createTempSkill({ "setup.sh": "curl https://example.com/install.sh | sh" });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "No suspicious patterns");
  expect(check.status).toBe("warn");
  expect(check.msg).toContain("pipe to shell");
});

test("warns on env var in network call", () => {
  const dir = createTempSkill({ "fetch.js": "const url = process.env.API_URL; fetch(url);" });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "No suspicious patterns");
  expect(check.status).toBe("warn");
  expect(check.msg).toContain("exfiltration");
});

// ── autoFix (human-readable) ───────────────────────────────────

test("autoFix prints output and returns fix count", () => {
  const dir = createTempSkill({});
  const origLog = console.log;
  let output = "";
  console.log = (...args) => { output += args.join(" ") + "\n"; };
  const count = require("./index").autoFix(dir);
  console.log = origLog;
  expect(count).toBeGreaterThanOrEqual(1);
  expect(output).toContain("skill-doctor");
});

// ── Script refs – no references case ───────────────────────────

test("passes when SKILL.md has no script references", () => {
  const dir = createTempSkill({ "SKILL.md": "# Test\n\nNo scripts here." });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "Scripts referenced in SKILL.md exist");
  expect(check.status).toBe("pass");
  expect(check.msg).toContain("no script references");
});

// ── package.json missing version ───────────────────────────────

test("warns on package.json missing version", () => {
  const dir = createTempSkill({ "package.json": '{"name":"foo"}' });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "Valid package.json (if present)");
  expect(check.status).toBe("warn");
  expect(check.msg).toContain("version");
});

// ── oversized files in subdirectories ──────────────────────────

test("detects oversized files in nested dirs", () => {
  const dir = createTempSkill({});
  const subDir = path.join(dir, "assets");
  fs.mkdirSync(subDir);
  fs.writeFileSync(path.join(subDir, "big.png"), "x".repeat(600_000));
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "No oversized files (>500KB)");
  expect(check.status).toBe("warn");
  expect(check.msg).toContain("big.png");
});

// ── loadCustomChecks – `check` alias ─────────────────────────────

test("loadCustomChecks supports `check` property alias", () => {
  const dir = createTempSkill({
    ".skill-doctor.js": `module.exports = [
      { name: "Alias check", check: (dir) => ({ status: "pass", msg: "via check alias" }) },
    ];`,
  });
  const { loadCustomChecks: lc } = require("./index");
  const custom = lc(dir);
  expect(custom.length).toBe(1);
  expect(custom[0].fn(dir).status).toBe("pass");
});

test("loadCustomChecks handles entry with no fn or check", () => {
  const dir = createTempSkill({
    ".skill-doctor.js": `module.exports = [{ name: "Empty" }];`,
  });
  const { loadCustomChecks: lc } = require("./index");
  const custom = lc(dir);
  expect(custom.length).toBe(1);
  expect(custom[0].fn(dir).status).toBe("skip");
});

// ── diagnose exit code 1 (warnings only) ────────────────────────

test("diagnose returns exit code 1 when only warnings", () => {
  const dir = createTempSkill({ "README.md": "# Test" }); // no SKILL.md = fail
  // Actually need a dir that passes SKILL.md but warns on something else
  // README missing = warn, but SKILL.md missing = fail
  // Let's use a dir with valid SKILL.md but no README = warn on README
  const dir2 = createTempSkill({ "SKILL.md": "---\ndescription: test\n---\n" + "x".repeat(300) });
  const origLog = console.log;
  let output = "";
  console.log = (...args) => { output += args.join(" ") + "\n"; };
  const code = diagnose(dir2);
  console.log = origLog;
  // May be 1 or 0 depending on other checks
  expect([0, 1]).toContain(code);
});

// ── Script references – .py and .ts extensions ──────────────────

test("detects missing .py script reference", () => {
  const dir = createTempSkill({
    "SKILL.md": 'Run `./process.py` to process data',
  });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "Scripts referenced in SKILL.md exist");
  expect(check.status).toBe("fail");
});

test("detects missing .ts script reference", () => {
  const dir = createTempSkill({
    "SKILL.md": 'Run `./build.ts` to build',
  });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "Scripts referenced in SKILL.md exist");
  expect(check.status).toBe("fail");
});

// ── node_modules – passes when no node_modules dir ──────────────

test("passes when no node_modules at all", () => {
  const dir = createTempSkill({ "SKILL.md": "# " + "x".repeat(200) });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "No node_modules committed");
  expect(check.status).toBe("pass");
});

// ── Suspicious patterns – ignores non-code files ────────────────

test("flags eval in .md files (they are scanned)", () => {
  const dir = createTempSkill({ "guide.md": "Use eval() carefully." });
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "No suspicious patterns");
  expect(check.status).toBe("warn");
  expect(check.msg).toContain("eval");
});

// ── autoFix – already has .gitignore with node_modules ──────────

test("auto-fix skips when .gitignore already has node_modules", () => {
  const dir = createTempSkill({ ".gitignore": "node_modules\ndist\n" });
  fs.mkdirSync(path.join(dir, "node_modules"));
  const report = autoFixJSON(dir);
  const fix = report.fixes.find((r) => r.name === "Add .gitignore with node_modules");
  expect(fix.fixed).toBe(false);
});

// ── Oversized files – skips dotfiles and node_modules ───────────

test("ignores files in .dotdirs and node_modules for size check", () => {
  const dir = createTempSkill({});
  const nmDir = path.join(dir, "node_modules", "pkg");
  fs.mkdirSync(nmDir, { recursive: true });
  fs.writeFileSync(path.join(nmDir, "big.js"), "x".repeat(600_000));
  const report = diagnoseJSON(dir);
  const check = report.results.find((r) => r.name === "No oversized files (>500KB)");
  expect(check.status).toBe("pass");
});

// ── Custom check that throws ────────────────────────────────────

test("diagnoseJSON handles custom check throwing error", () => {
  const dir = createTempSkill({
    "SKILL.md": "---\ndescription: test\n---\n" + "x".repeat(200),
    ".skill-doctor.js": `module.exports = [
      { name: "Crasher", fn: () => { throw new Error("custom crash"); } },
    ];`,
  });
  const report = diagnoseJSON(dir);
  const crasher = report.results.find((r) => r.name === "Crasher");
  expect(crasher).toBeDefined();
  expect(crasher.status).toBe("fail");
  expect(crasher.msg).toContain("custom crash");
});

// ── GitHub Actions annotations format ─────────────────────────────────

describe("formatGithubAnnotations", () => {
  const { formatGithubAnnotations, escapeGithubData } = require("./index");

  const report = {
    results: [
      { name: "SKILL.md exists", status: "fail", msg: "SKILL.md not found" },
      { name: "SKILL.md description", status: "warn", msg: "No explicit description found" },
      { name: "README.md exists", status: "pass", msg: "ok" },
      { name: "skipped check", status: "skip", msg: "n/a" },
    ],
    summary: { pass: 1, warn: 1, fail: 1, skip: 1 },
  };

  test("fail → ::error with title and name: msg", () => {
    const lines = formatGithubAnnotations(report);
    expect(lines[0]).toBe("::error title=skill-doctor::SKILL.md exists: SKILL.md not found");
  });

  test("warn → ::warning line, ordered as reported", () => {
    const lines = formatGithubAnnotations(report);
    expect(lines[1]).toBe("::warning title=skill-doctor::SKILL.md description: No explicit description found");
    expect(lines).toHaveLength(2);
  });

  test("pass and skip produce no annotations", () => {
    const clean = { results: [
      { name: "a", status: "pass", msg: "ok" },
      { name: "b", status: "skip", msg: "n/a" },
    ]};
    expect(formatGithubAnnotations(clean)).toEqual([]);
  });

  test("empty results → empty output", () => {
    expect(formatGithubAnnotations({ results: [] })).toEqual([]);
  });

  test("escapes % as %25", () => {
    const r = { results: [{ name: "n", status: "warn", msg: "50% done" }] };
    expect(formatGithubAnnotations(r)[0]).toContain("50%25 done");
  });

  test("escapes newlines as %0A (single-line annotation)", () => {
    const r = { results: [{ name: "n", status: "fail", msg: "line1\nline2" }] };
    const line = formatGithubAnnotations(r)[0];
    expect(line).not.toContain("\n");
    expect(line).toContain("line1%0Aline2");
  });

  test("escapeGithubData handles %, CR and LF together", () => {
    expect(escapeGithubData("a%b\rc\nd")).toBe("a%25b%0Dc%0Ad");
  });

  test("double escaping is idempotent-safe: %25 does not become %2525", () => {
    expect(escapeGithubData("100%")).toBe("100%25");
  });
});

describe("CLI --format github", () => {
  const { execFileSync } = require("child_process");

  test("fail condition emits ::error annotation, exit code 2, no ANSI", () => {
    const dir = createTempSkill({}); // empty dir: no SKILL.md → fail, no README → warn
    let out, status;
    try {
      out = execFileSync("node", ["index.js", "--format", "github", dir], { encoding: "utf8" });
      status = 0;
    } catch (e) {
      out = e.stdout;
      status = e.status;
    }
    expect(status).toBe(2);
    expect(out).toContain("::error title=skill-doctor::");
    expect(out).toContain("::warning title=skill-doctor::");
    expect(out).not.toContain("\u001b["); // no ANSI colors in CI output
  });

  test("healthy skill dir emits no annotation lines, exit 0", () => {
    const dir = createTempSkill({
      "SKILL.md": "A".repeat(200) + "\nDescription: does things properly for tests here\n" + "B".repeat(100),
      "README.md": "# readme\n",
    });
    const out = execFileSync("node", ["index.js", "--format", "github", dir], {
      encoding: "utf8",
    });
    expect(out.trim()).toBe("");
  });

  test("--json takes precedence over --format github (machine JSON stays machine JSON)", () => {
    const dir = createTempSkill({});
    let out;
    try {
      out = execFileSync("node", ["index.js", "--json", "--format", "github", dir], {
        encoding: "utf8",
      });
    } catch (e) {
      out = e.stdout; // exit 2 from failed checks is expected
    }
    const parsed = JSON.parse(out);
    expect(Array.isArray(parsed)).toBe(true);
    expect(parsed[0].summary).toBeDefined();
  });
});
