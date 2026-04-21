const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const os = require("os");
const {
  archiveSession,
  listArchives,
  searchArchives,
  exportSession,
  getStats,
  cleanOldArchives,
  addTags,
  removeTags,
  searchByTag,
} = require("./archive");

const TMP_DIR = fs.mkdtempSync(path.join(os.tmpdir(), "sa-test-"));

// Override archive dir for tests
process.env.SESSION_ARCHIVE_DIR = TMP_DIR;

// Clean slate
for (const f of fs.readdirSync(TMP_DIR)) fs.rmSync(path.join(TMP_DIR, f), { force: true });

test("archiveSession creates archive file", () => {
  const result = archiveSession({
    id: "test-001",
    label: "Test Session",
    history: [
      { role: "user", content: "Hello world" },
      { role: "assistant", content: "Hi there! How can I help?" },
    ],
  });
  assert.equal(result.id, "test-001");
  assert.equal(result.messageCount, 2);
  assert.ok(fs.existsSync(result.path));
});

test("listArchives returns archived sessions", () => {
  const archives = listArchives();
  assert.ok(archives.length >= 1);
  assert.ok(archives.some((a) => a.id === "test-001"));
});

test("searchArchives finds matching content", () => {
  const results = searchArchives("hello");
  assert.equal(results.length, 1);
  assert.ok(results[0].score > 0);
  assert.equal(results[0].archiveId, "test-001");
});

test("searchArchives returns empty for no match", () => {
  const results = searchArchives("xyznonexistent");
  assert.equal(results.length, 0);
});

test("exportSession markdown format", () => {
  const md = exportSession("test-001", "markdown");
  assert.ok(md.includes("Test Session"));
  assert.ok(md.includes("Hello world"));
  assert.ok(md.includes("USER"));
});

test("exportSession json format", () => {
  const json = exportSession("test-001", "json");
  const parsed = JSON.parse(json);
  assert.equal(parsed.id, "test-001");
});

test("exportSession html format", () => {
  const html = exportSession("test-001", "html");
  assert.ok(html.includes("<!DOCTYPE html>"));
  assert.ok(html.includes("Hello world"));
});

test("getStats returns correct stats", () => {
  const stats = getStats();
  assert.ok(stats.totalArchives >= 1);
  assert.ok(stats.totalMessages >= 2);
});

test("cleanOldArchives dry run", () => {
  const before = listArchives().length;
  const result = cleanOldArchives(0, true);
  assert.ok(result.count >= 1);
  // Should still exist
  assert.equal(listArchives().length, before);
});

test("cleanOldArchives removes old", () => {
  cleanOldArchives(0, false);
  assert.equal(listArchives().length, 0);
});

// Cleanup
test.after(() => {
  fs.rmSync(TMP_DIR, { recursive: true, force: true });
});

// === Feature: Tag system ===

test("addTags adds tags to archive", () => {
  archiveSession({
    id: "tag-test",
    label: "Tagged Session",
    history: [{ role: "user", content: "tag me" }],
  });
  const result = addTags("tag-test", ["important", "review"]);
  assert.deepEqual(result.tags, ["important", "review"]);
  assert.equal(result.added, 2);
});

test("addTags skips duplicates", () => {
  const result = addTags("tag-test", ["important", "new-tag"]);
  assert.deepEqual(result.tags, ["important", "review", "new-tag"]);
  assert.equal(result.added, 1);
});

test("removeTags removes specified tags", () => {
  const result = removeTags("tag-test", ["review"]);
  assert.deepEqual(result.tags, ["important", "new-tag"]);
  assert.equal(result.removed, 1);
});

test("searchByTag finds tagged archives", () => {
  const results = searchByTag("important");
  assert.equal(results.length, 1);
  assert.equal(results[0].id, "tag-test");
});

test("searchByTag returns empty for unknown tag", () => {
  const results = searchByTag("nonexistent");
  assert.equal(results.length, 0);
});

test("addTags throws for missing archive", () => {
  assert.throws(() => addTags("no-such-id", ["tag"]), /not found/);
});

// === Feature: Date-range filtering ===

test("listArchives filters by from date", () => {
  const results = listArchives({ from: "2020-01-01" });
  assert.ok(results.length >= 1); // at least tag-test
});

test("listArchives filters by to date (far past = empty)", () => {
  const results = listArchives({ to: "2019-01-01" });
  assert.equal(results.length, 0);
});

test("listArchives filters by date range", () => {
  const results = listArchives({ from: "2020-01-01", to: "2030-12-31" });
  assert.ok(results.length >= 1);
});
