/**
 * CLI end-to-end tests for bin/cli.js — hermetic via env overrides.
 * SESSION_ARCHIVE_DIR: temp store (archive.js reads it at module load).
 * OPENCLAW_HOME: temp openclaw home so archive --id can find fake sessions.
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const { spawnSync } = require("node:child_process");

const CLI = path.join(__dirname, "..", "bin", "cli.js");
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "sa-cli-test-"));
const ARCHIVE_DIR = path.join(TMP, "archives");
const OC_HOME = path.join(TMP, "openclaw-home");
fs.mkdirSync(ARCHIVE_DIR, { recursive: true });
fs.mkdirSync(path.join(OC_HOME, "sessions"), { recursive: true });

const ENV = {
  ...process.env,
  SESSION_ARCHIVE_DIR: ARCHIVE_DIR,
  OPENCLAW_HOME: OC_HOME,
};

function cli(args, opts = {}) {
  return spawnSync(process.execPath, [CLI, ...args], {
    encoding: "utf-8",
    env: opts.env || ENV,
  });
}

function seedArchive(id, label, history, archivedAtOverride) {
  // Seed via lib in a child process so it uses the same env-captured dir
  const script = `
    const { archiveSession } = require(${JSON.stringify(path.join(__dirname, "..", "lib", "archive"))});
    archiveSession(${JSON.stringify({ id, label, history })});
  `;
  const r = spawnSync(process.execPath, ["-e", script], { encoding: "utf-8", env: ENV });
  assert.equal(r.status, 0, `seed failed: ${r.stderr}`);
  if (archivedAtOverride) {
    const fp = path.join(ARCHIVE_DIR, `${id}.json`);
    const data = JSON.parse(fs.readFileSync(fp, "utf-8"));
    data.archivedAt = archivedAtOverride;
    fs.writeFileSync(fp, JSON.stringify(data, null, 2));
  }
}

test("help and version exit 0", () => {
  assert.equal(cli(["--help"]).status, 0);
  assert.match(cli(["--version"]).stdout, /^1\.0\.0/);
});

test("list --json on empty store returns []", () => {
  const r = cli(["list", "--json"]);
  assert.equal(r.status, 0);
  assert.deepEqual(JSON.parse(r.stdout), []);
});

test("archive --id reads fake openclaw session end-to-end", () => {
  const sessionFile = path.join(OC_HOME, "sessions", "sess-alpha.json");
  fs.writeFileSync(
    sessionFile,
    JSON.stringify([
      { role: "user", content: "deploy the thing" },
      { role: "assistant", content: "done" },
    ]),
    "utf-8"
  );
  const r = cli(["archive", "--id", "sess-alpha", "--label", "Alpha"]);
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /Archived/);

  const listed = JSON.parse(cli(["list", "--json"]).stdout);
  assert.equal(listed.length, 1);
  assert.equal(listed[0].id, "sess-alpha");
  assert.equal(listed[0].label, "Alpha");
  assert.equal(listed[0].messageCount, 2);
});

test("search finds seeded content and --json shape", () => {
  seedArchive("srch-1", "Search target", [
    { role: "user", content: "needle in haystack" },
  ]);
  const r = cli(["search", "needle", "--json"]);
  assert.equal(r.status, 0, r.stderr);
  const results = JSON.parse(r.stdout);
  assert.ok(results.length >= 1);
  assert.ok(results.some((x) => x.archiveId === "srch-1" && x.score > 0));
});

test("search --limit abc is rejected, not silently empty", () => {
  const r = cli(["search", "needle", "--limit", "abc"]);
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /invalid/i);
});

test("list --limit abc is rejected", () => {
  const r = cli(["list", "--limit", "abc"]);
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /invalid/i);
});

test("export not-found exits 1 with friendly error, no stack trace", () => {
  const r = cli(["export", "no-such-archive"]);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /Archive not found/);
  assert.ok(!r.stderr.includes("at "), `expected no stack trace, got:\n${r.stderr}`);
});

test("export markdown/json formats match content", () => {
  seedArchive("fmt-1", "Format Test", [
    { role: "user", content: "hello export" },
  ]);
  const md = cli(["export", "fmt-1"]);
  assert.equal(md.status, 0);
  assert.match(md.stdout, /### USER/);
  assert.match(md.stdout, /hello export/);

  const js = cli(["export", "fmt-1", "--format", "json"]);
  assert.equal(js.status, 0);
  assert.equal(JSON.parse(js.stdout).id, "fmt-1");
});

test("export html escapes label (no <script> leakage)", () => {
  seedArchive("xss-1", '<script>alert(1)</script>', [
    { role: "user", content: "safe text" },
  ]);
  const r = cli(["export", "xss-1", "--format", "html"]);
  assert.equal(r.status, 0);
  assert.ok(!r.stdout.includes("<script>"), "raw <script> leaked into html");
  assert.match(r.stdout, /&lt;script&gt;/);
});

test("export --output writes file", () => {
  seedArchive("out-1", "Out Test", [{ role: "user", content: "file body" }]);
  const out = path.join(TMP, "out.md");
  const r = cli(["export", "out-1", "--output", out]);
  assert.equal(r.status, 0);
  assert.match(fs.readFileSync(out, "utf-8"), /file body/);
});

test("stats reports seeded archives", () => {
  const r = cli(["stats"]);
  assert.equal(r.status, 0);
  assert.match(r.stdout, /Total archives:/);
});

test("clean --dry-run reports old archives without deleting", () => {
  seedArchive("old-1", "Old", [{ role: "user", content: "old" }], "2020-01-01T00:00:00.000Z");
  const r = cli(["clean", "--days", "90", "--dry-run"]);
  assert.equal(r.status, 0);
  assert.match(r.stdout, /Would remove/);
  assert.match(r.stdout, /[1-9]/);
  assert.ok(fs.existsSync(path.join(ARCHIVE_DIR, "old-1.json")));
});

test("clean actually removes old archives", () => {
  const r = cli(["clean", "--days", "90"]);
  assert.equal(r.status, 0);
  assert.ok(!fs.existsSync(path.join(ARCHIVE_DIR, "old-1.json")));
});

test("clean --days abc is rejected", () => {
  const r = cli(["clean", "--days", "abc"]);
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /invalid/i);
});

test("archive with no flags exits non-zero", () => {
  const r = cli(["archive"]);
  assert.equal(r.status, 1);
  assert.match(r.stdout, /--all or --id/);
});

test("archive --id for unknown session archives empty history, does not crash", () => {
  const r = cli(["archive", "--id", "ghost-session"]);
  assert.equal(r.status, 0, r.stderr);
  const listed = JSON.parse(cli(["list", "--json"]).stdout);
  assert.ok(listed.some((a) => a.id === "ghost-session" && a.messageCount === 0));
});
