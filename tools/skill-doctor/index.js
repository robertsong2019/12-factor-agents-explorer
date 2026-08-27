#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

// ── ANSI helpers ──────────────────────────────────────────────
const c = {
  reset: "\x1b[0m", bold: "\x1b[1m",
  green: "\x1b[32m", yellow: "\x1b[33m", red: "\x1b[31m", dim: "\x1b[2m", cyan: "\x1b[36m",
};
const ok = (msg) => `${c.green}✓${c.reset} ${msg}`;
const warn = (msg) => `${c.yellow}⚠${c.reset} ${msg}`;
const fail = (msg) => `${c.red}✗${c.reset} ${msg}`;

// ── Check registry ────────────────────────────────────────────
const checks = [];

function check(name, fn) { checks.push({ name, fn }); }

// ── Individual checks ─────────────────────────────────────────

check("SKILL.md exists", (dir) => {
  const p = path.join(dir, "SKILL.md");
  if (!fs.existsSync(p)) return { status: "fail", msg: "SKILL.md not found" };
  const stat = fs.statSync(p);
  if (stat.size < 50) return { status: "warn", msg: `SKILL.md is only ${stat.size} bytes — likely too short` };
  return { status: "pass", msg: `${stat.size} bytes` };
});

check("SKILL.md has description", (dir) => {
  const p = path.join(dir, "SKILL.md");
  if (!fs.existsSync(p)) return { status: "skip", msg: "no SKILL.md" };
  const content = fs.readFileSync(p, "utf8");
  // Look for description field in frontmatter or a clear description paragraph
  const hasDescription = /description:/i.test(content) || content.length > 200;
  if (!hasDescription) return { status: "warn", msg: "No explicit description found" };
  return { status: "pass", msg: "description present" };
});

// Extract a leading YAML-ish frontmatter block: returns its text or null.
function parseFrontmatter(content) {
  if (!content.startsWith("---")) return null;
  const end = content.indexOf("\n---", 3);
  if (end === -1) return null;
  return content.slice(3, end);
}

function parseFrontmatterFields(block) {
  const fields = {};
  for (const line of block.split(/\r?\n/)) {
    const m = line.match(/^([\w-]+)\s*:\s*(.+?)\s*$/);
    if (m && !(m[1] in fields)) fields[m[1]] = m[2];
  }
  return fields;
}

// OpenClaw/AgentSkills spec: SKILL.md needs a frontmatter block with non-empty
// name and description — a skill without one won't load at all.
check("Valid SKILL.md frontmatter", (dir) => {
  const p = path.join(dir, "SKILL.md");
  if (!fs.existsSync(p)) return { status: "skip", msg: "no SKILL.md" };
  const content = fs.readFileSync(p, "utf8");
  const block = parseFrontmatter(content);
  if (block === null)
    return { status: "warn", msg: "no frontmatter block (--- ... ---) — skill will not load; run --fix to add one" };
  const fields = parseFrontmatterFields(block);
  const missing = ["name", "description"].filter((k) => !fields[k]);
  if (missing.length)
    return { status: "warn", msg: `frontmatter missing: ${missing.join(", ")}` };
  return { status: "pass", msg: `${fields.name} — ok` };
});

check("README.md exists", (dir) => {
  const p = path.join(dir, "README.md");
  if (!fs.existsSync(p)) return { status: "warn", msg: "No README.md" };
  return { status: "pass", msg: "present" };
});

check("No oversized files (>500KB)", (dir) => {
  const walk = (d) => {
    let big = [];
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      if (entry.name.startsWith(".") || entry.name === "node_modules") continue;
      const full = path.join(d, entry.name);
      if (entry.isDirectory()) big.push(...walk(full));
      else if (fs.statSync(full).size > 500_000)
        big.push(`${entry.name} (${(fs.statSync(full).size / 1024).toFixed(0)}KB)`);
    }
    return big;
  };
  const big = walk(dir);
  if (big.length) return { status: "warn", msg: `Large files: ${big.join(", ")}` };
  return { status: "pass", msg: "all files under 500KB" };
});

check("No suspicious patterns", (dir) => {
  const walk = (d) => {
    let results = [];
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      if (entry.name.startsWith(".") || entry.name === "node_modules") continue;
      const full = path.join(d, entry.name);
      if (entry.isDirectory()) { results.push(...walk(full)); continue; }
      if (!/\.(js|ts|sh|py|md)$/.test(entry.name)) continue;
      try {
        const content = fs.readFileSync(full, "utf8");
        // Check for common red flags
        // NOTE: anchored via (?<![\w.$]) so identifiers ending in "eval"
        // (retrieval(, medieval(, relevel() don't false-positive.
        if (/(?<![\w.$])eval\s*\(/.test(content) && !/no.*eval/i.test(content))
          results.push(`${entry.name}: eval() usage`);
        if (/child_process.*execSync.*\+/.test(content))
          results.push(`${entry.name}: possible command injection`);
        // Shell out with an interpolated template literal = unescaped input reaches the shell
        if (/\bexec(?:Sync)?\s*\(\s*`[^`]*\$\{/.test(content))
          results.push(`${entry.name}: possible command injection (interpolated exec)`);
        if (/curl.*\|.*sh/.test(content))
          results.push(`${entry.name}: pipe to shell`);
        if (/process\.env\.\w+.*(?:fetch|axios|http)/i.test(content))
          results.push(`${entry.name}: env var in network call — verify no exfiltration`);
      } catch {}
    }
    return results;
  };
  const issues = walk(dir);
  if (issues.length) return { status: "warn", msg: issues.join("; ") };
  return { status: "pass", msg: "no suspicious patterns" };
});

check("Scripts referenced in SKILL.md exist", (dir) => {
  const skillPath = path.join(dir, "SKILL.md");
  if (!fs.existsSync(skillPath)) return { status: "skip", msg: "no SKILL.md" };
  const content = fs.readFileSync(skillPath, "utf8");
  // Find script references: ./scripts/foo.sh, ./foo.py, etc.
  const refs = [...content.matchAll(/[`'"]\.\/(?:scripts\/)?[\w.-]+\.(?:sh|py|js|ts)[`'"]/g)]
    .map((m) => m[0].replace(/[`'"]/g, ""));
  const missing = refs.filter((r) => !fs.existsSync(path.join(dir, r)));
  if (missing.length) return { status: "fail", msg: `Missing: ${missing.join(", ")}` };
  if (refs.length === 0) return { status: "pass", msg: "no script references" };
  return { status: "pass", msg: `${refs.length} script(s) found and valid` };
});

check("No node_modules committed", (dir) => {
  if (fs.existsSync(path.join(dir, "node_modules"))) {
    const hasGitignore = fs.existsSync(path.join(dir, ".gitignore"));
    if (hasGitignore) {
      const gi = fs.readFileSync(path.join(dir, ".gitignore"), "utf8");
      if (/node_modules/.test(gi)) return { status: "pass", msg: "in .gitignore" };
    }
    return { status: "warn", msg: "node_modules present, not in .gitignore" };
  }
  return { status: "pass", msg: "no node_modules" };
});

check("Valid package.json (if present)", (dir) => {
  const p = path.join(dir, "package.json");
  if (!fs.existsSync(p)) return { status: "pass", msg: "no package.json (not required)" };
  try {
    const pkg = JSON.parse(fs.readFileSync(p, "utf8"));
    const issues = [];
    if (!pkg.name) issues.push("missing name");
    if (!pkg.version) issues.push("missing version");
    if (issues.length) return { status: "warn", msg: issues.join(", ") };
    return { status: "pass", msg: `${pkg.name}@${pkg.version}` };
  } catch (e) {
    return { status: "fail", msg: `invalid JSON: ${e.message}` };
  }
});

// ── Runner ────────────────────────────────────────────────────

function diagnose(dir, quiet = false) {
  const resolved = path.resolve(dir);
  if (!fs.existsSync(resolved)) {
    console.error(fail(`Directory not found: ${resolved}`));
    process.exit(2);
  }

  const allChecks = [...checks, ...loadCustomChecks(resolved)];

  console.log(`\n${c.bold}${c.cyan}🩺 skill-doctor${c.reset} — ${resolved}\n`);

  let passes = 0, warns = 0, fails = 0, skips = 0;

  for (const { name, fn } of allChecks) {
    try {
      const result = fn(resolved);
      if (quiet && result.status === "pass") { passes++; continue; }
      const icon =
        result.status === "pass" ? ok(name) :
        result.status === "warn" ? warn(name) :
        result.status === "fail" ? fail(name) :
        `${c.dim}→ ${name}${c.reset}`;

      console.log(`  ${icon}  ${c.dim}${result.msg}${c.reset}`);
      if (result.status === "pass") passes++;
      else if (result.status === "warn") warns++;
      else if (result.status === "fail") fails++;
      else skips++;
    } catch (e) {
      console.log(`  ${fail(name)}  ${c.dim}check error: ${e.message}${c.reset}`);
      fails++;
    }
  }

  console.log(
    `\n  ${c.bold}Summary:${c.reset} ${c.green}${passes} pass${c.reset} / ${c.yellow}${warns} warn${c.reset} / ${c.red}${fails} fail${c.reset} / ${c.dim}${skips} skip${c.reset}\n`
  );

  return fails > 0 ? 2 : warns > 0 ? 1 : 0;
}

// ── JSON output ───────────────────────────────────────────────

function diagnoseJSON(dir) {
  const resolved = path.resolve(dir);
  const allChecks = [...checks, ...loadCustomChecks(resolved)];
  const results = allChecks.map(({ name, fn }) => {
    try {
      const r = fn(resolved);
      return { name, ...r };
    } catch (e) {
      return { name, status: "fail", msg: `check error: ${e.message}` };
    }
  });
  const summary = {
    pass: results.filter((r) => r.status === "pass").length,
    warn: results.filter((r) => r.status === "warn").length,
    fail: results.filter((r) => r.status === "fail").length,
    skip: results.filter((r) => r.status === "skip").length,
  };
  return { directory: resolved, results, summary, exitCode: summary.fail > 0 ? 2 : summary.warn > 0 ? 1 : 0 };
}

// ── GitHub Actions annotations format ───────────────────────────

function escapeGithubData(s) {
  return String(s).replace(/%/g, "%25").replace(/\r/g, "%0D").replace(/\n/g, "%0A");
}

// Turn a diagnoseJSON() report into GitHub Actions workflow-command lines.
// fail → ::error, warn → ::warning; pass/skip are silent (annotations are for problems).
function formatGithubAnnotations(report) {
  const lines = [];
  for (const r of report.results) {
    if (r.status !== "fail" && r.status !== "warn") continue;
    const cmd = r.status === "fail" ? "error" : "warning";
    lines.push(
      `::${cmd} title=skill-doctor::${escapeGithubData(`${r.name}: ${r.msg}`)}`
    );
  }
  return lines;
}

// ── Auto-fix ─────────────────────────────────────────────────

const fixers = [];

function fixer(name, fn) { fixers.push({ name, fn }); }

fixer("Add .gitignore with node_modules", (dir) => {
  const nmPath = path.join(dir, "node_modules");
  const giPath = path.join(dir, ".gitignore");
  if (!fs.existsSync(nmPath)) return { fixed: false, msg: "no node_modules dir" };
  if (fs.existsSync(giPath)) {
    const content = fs.readFileSync(giPath, "utf8");
    if (/node_modules/.test(content)) return { fixed: false, msg: "already in .gitignore" };
    fs.appendFileSync(giPath, "\nnode_modules\n");
    return { fixed: true, msg: "appended node_modules to .gitignore" };
  }
  fs.writeFileSync(giPath, "node_modules\n");
  return { fixed: true, msg: "created .gitignore with node_modules" };
});

// OpenClaw skills must load from frontmatter — emit a spec-valid skeleton,
// not just markdown (previously generated frontmatter-less files).
const slugify = (s) => s.toLowerCase().replace(/[^\w.-]+/g, "-").replace(/^[-.]+|[-.]+$/g, "") || "skill";

fixer("Create minimal SKILL.md", (dir) => {
  const p = path.join(dir, "SKILL.md");
  if (fs.existsSync(p)) return { fixed: false, msg: "SKILL.md already exists" };
  const name = path.basename(dir);
  fs.writeFileSync(
    p,
    `---\nname: ${slugify(name)}\ndescription: Description of this skill.\n---\n\n# ${name}\n\n## Usage\n\nHow to use this skill.\n`
  );
  return { fixed: true, msg: "created minimal SKILL.md with frontmatter" };
});

fixer("Create minimal README.md", (dir) => {
  const p = path.join(dir, "README.md");
  if (fs.existsSync(p)) return { fixed: false, msg: "README.md already exists" };
  const name = path.basename(dir);
  fs.writeFileSync(p, `# ${name}\n\nSee [SKILL.md](./SKILL.md) for details.\n`);
  return { fixed: true, msg: "created minimal README.md" };
});

function autoFix(dir) {
  const resolved = path.resolve(dir);
  if (!fs.existsSync(resolved)) {
    console.error(fail(`Directory not found: ${resolved}`));
    return 0;
  }

  console.log(`\n${c.bold}${c.cyan}🔧 skill-doctor --fix${c.reset} — ${resolved}\n`);
  let fixCount = 0;

  for (const { name, fn } of fixers) {
    const result = fn(resolved);
    if (result.fixed) {
      console.log(`  ${ok(name)}  ${c.dim}${result.msg}${c.reset}`);
      fixCount++;
    }
  }

  if (fixCount === 0) console.log(`  ${c.dim}Nothing to auto-fix.${c.reset}`);
  else console.log(`\n  ${c.bold}${fixCount} issue(s) fixed.${c.reset}`);

  return fixCount;
}

function autoFixJSON(dir) {
  const resolved = path.resolve(dir);
  const results = fixers.map(({ name, fn }) => {
    const r = fn(resolved);
    return { name, ...r };
  });
  const fixed = results.filter((r) => r.fixed).length;
  return { directory: resolved, fixes: results, fixCount: fixed };
}

// ── CLI ───────────────────────────────────────────────────────

// ── Custom checks loader ────────────────────────────────────

function loadCustomChecks(dir) {
  const customPath = path.join(dir, ".skill-doctor.js");
  if (!fs.existsSync(customPath)) return [];
  try {
    const mod = require(customPath);
    const customChecks = Array.isArray(mod) ? mod : (mod.checks || []);
    return customChecks.map((c, i) => ({
      name: c.name || `Custom check #${i + 1}`,
      fn: c.fn || c.check || (() => ({ status: "skip", msg: "no function" })),
    }));
  } catch (e) {
    return [{ name: "Load .skill-doctor.js", fn: () => ({ status: "fail", msg: e.message }) }];
  }
}

// Export for testing
module.exports = { checks, diagnose, diagnoseJSON, fixers, autoFix, autoFixJSON, loadCustomChecks, formatGithubAnnotations, escapeGithubData, parseFrontmatter, parseFrontmatterFields };

if (require.main === module) {
  const args = process.argv.slice(2);
  const jsonMode = args.includes("--json");
  const fixMode = args.includes("--fix");
  const quietMode = args.includes("--quiet");
  const formatIdx = args.indexOf("--format");
  const formatMode = formatIdx !== -1 ? args[formatIdx + 1] : null; // "github" expected
  const dirs = args.filter(
    (a, i) =>
      a !== "--json" && a !== "--fix" && a !== "--quiet" && a !== "--format" &&
      !(formatIdx !== -1 && i === formatIdx + 1)
  );

  if (dirs.length === 0 || args.includes("--help") || args.includes("-h")) {
    console.log(`${c.bold}skill-doctor${c.reset} — Diagnose OpenClaw Agent Skills

${c.bold}Usage:${c.reset}
  skill-doctor <skill-dir> [skill-dir ...]
  skill-doctor --json <skill-dir>   machine-readable output
  skill-doctor --fix <skill-dir>    auto-fix simple issues
  skill-doctor --fix --json        auto-fix with JSON output
  skill-doctor --quiet <skill-dir> only show warnings/failures
  skill-doctor --format github <skill-dir>  GitHub Actions annotations (::error/::warning)
  skill-doctor --help

${c.bold}Exit codes:${c.reset}
  0  all checks pass
  1  warnings (no failures)
  2  failures detected`);
    process.exit(0);
  }

  if (fixMode) {
    if (jsonMode) {
      const reports = dirs.map((d) => autoFixJSON(d));
      console.log(JSON.stringify(reports, null, 2));
    } else {
      for (const arg of dirs) autoFix(arg);
    }
    // After fixing, re-diagnose to show current state
    console.log(`\n${c.bold}${c.cyan}--- Re-running diagnosis ---${c.reset}`);
  }

  if (formatMode === "github" && !jsonMode && !fixMode) {
    const reports = dirs.map((d) => diagnoseJSON(d));
    for (const report of reports) {
      for (const line of formatGithubAnnotations(report)) console.log(line);
    }
    const worst = Math.max(...reports.map((r) => r.exitCode));
    process.exit(worst);
  }

  if (jsonMode && !fixMode) {
    const reports = dirs.map((d) => diagnoseJSON(d));
    console.log(JSON.stringify(reports, null, 2));
    const worst = Math.max(...reports.map((r) => r.exitCode));
    process.exit(worst);
  }

  let exitCode = 0;
  for (const arg of dirs) {
    const code = diagnose(arg, quietMode);
    if (code > exitCode) exitCode = code;
  }
  process.exit(exitCode);
}
