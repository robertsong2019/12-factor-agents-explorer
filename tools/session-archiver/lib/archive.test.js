const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const os = require("os");
const TMP_DIR = fs.mkdtempSync(path.join(os.tmpdir(), "sa-test-"));

// Override archive dir for tests — MUST be set before require():
// archive.js captures SESSION_ARCHIVE_DIR at module load time.
// (Previously set after require, so every run wrote fixtures into the
// real ~/.openclaw/session-archives/ directory.)
process.env.SESSION_ARCHIVE_DIR = TMP_DIR;

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
  mergeArchives,
  diffArchives,
} = require("./archive");

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

// === Feature: Merge archives ===

test("mergeArchives combines two sessions", () => {
  // Create two sessions with different timestamps
  archiveSession({ id: "merge-a", label: "Session A", history: [
    { role: "user", content: "from A" },
  ] });
  archiveSession({ id: "merge-b", label: "Session B", history: [
    { role: "assistant", content: "from B" },
  ] });

  const result = mergeArchives(["merge-a", "merge-b"], { label: "Merged" });
  assert.equal(result.sourceCount, 2);
  assert.equal(result.totalMessages, 2);
  assert.ok(result.id.startsWith("merged-"));

  // Verify content via export
  const json = JSON.parse(exportSession(result.id, "json"));
  assert.equal(json.label, "Merged");
  assert.equal(json.history.length, 2);
  assert.equal(json.history[0]._source, "merge-a");
  assert.equal(json.history[1]._source, "merge-b");
  assert.ok(json.meta.sources.length === 2);
});

test("mergeArchives preserves tags from all sources", () => {
  addTags("merge-a", ["alpha"]);
  addTags("merge-b", ["beta"]);
  const result = mergeArchives(["merge-a", "merge-b"], { id: "merge-tagged" });
  const json = JSON.parse(exportSession("merge-tagged", "json"));
  assert.deepEqual(json.tags.sort(), ["alpha", "beta"]);
});

test("mergeArchives throws for less than 2 ids", () => {
  assert.throws(() => mergeArchives(["only-one"]), /at least 2/);
});

test("mergeArchives throws for missing archive", () => {
  assert.throws(() => mergeArchives(["merge-a", "nonexistent"]), /not found/);
});

test("mergeArchives custom label defaults to source labels joined", () => {
  const result = mergeArchives(["merge-a", "merge-b"]);
  const json = JSON.parse(exportSession(result.id, "json"));
  assert.ok(json.label.includes("Session A"));
  assert.ok(json.label.includes("Session B"));
});

// === Feature: Diff archives ===

test("diffArchives shows only-in messages", () => {
  archiveSession({ id: "diff-a", label: "Diff A", history: [
    { role: "user", content: "shared msg" },
    { role: "user", content: "unique to A" },
  ] });
  archiveSession({ id: "diff-b", label: "Diff B", history: [
    { role: "user", content: "shared msg" },
    { role: "user", content: "unique to B" },
  ] });

  const diff = diffArchives("diff-a", "diff-b");
  assert.equal(diff.commonCount, 1);
  assert.equal(diff.onlyInA.length, 1);
  assert.equal(diff.onlyInB.length, 1);
  assert.equal(diff.onlyInA[0].text, "unique to A");
  assert.equal(diff.onlyInB[0].text, "unique to B");
});

test("diffArchives identical sessions", () => {
  archiveSession({ id: "diff-c", label: "Same", history: [
    { role: "user", content: "same content" },
  ] });
  archiveSession({ id: "diff-d", label: "Same", history: [
    { role: "user", content: "same content" },
  ] });

  const diff = diffArchives("diff-c", "diff-d");
  assert.equal(diff.commonCount, 1);
  assert.equal(diff.onlyInA.length, 0);
  assert.equal(diff.onlyInB.length, 0);
  assert.equal(diff.similarity, "1.00");
});

test("diffArchives throws for missing archive", () => {
  assert.throws(() => diffArchives("nope", "diff-c"), /not found/);
});

// === Edge-case coverage boost (2026-08-16 morning cycle) ===

test("exportSession throws for missing archive", () => {
  assert.throws(() => exportSession("totally-absent-id"), /Archive not found/);
});

test("exportSession resolves partial ID prefix", () => {
  archiveSession({
    id: "zz-part-42",
    label: "Partial Resolve",
    history: [{ role: "user", content: "resolve me by prefix" }],
  });
  const md = exportSession("zz-part");
  assert.ok(md.includes("Partial Resolve"));
});

test("exportSession html escapes dangerous content (XSS)", () => {
  archiveSession({
    id: "xss-check",
    label: "XSS Probe",
    history: [{ role: "user", content: "<script>alert('xss')</script> & <b>bold</b>" }],
  });
  const html = exportSession("xss-check", "html");
  assert.ok(html.includes("&lt;script&gt;"));
  assert.ok(html.includes("&amp;"));
  assert.ok(!html.includes("<script>"));
});

test("archiveSession auto-generates id when omitted", () => {
  const result = archiveSession({
    label: "Auto ID",
    history: [{ role: "user", content: "no id given" }],
  });
  assert.ok(result.id.startsWith("session-"));
  assert.equal(result.messageCount, 1);
});

test("archiveSession tolerates non-array history", () => {
  const result = archiveSession({ id: "hist-string", label: "str", history: "not-an-array" });
  assert.equal(result.messageCount, 0);
  const json = JSON.parse(exportSession("hist-string", "json"));
  assert.deepEqual(json.history, []);
});

test("archiveSession tolerates undefined history and persists meta", () => {
  const result = archiveSession({ id: "hist-undef", label: "undef", meta: { agent: "catalyst" } });
  assert.equal(result.messageCount, 0);
  const json = JSON.parse(exportSession("hist-undef", "json"));
  assert.deepEqual(json.meta, { agent: "catalyst" });
});

test("archiveSession builds token index (frequency + punctuation stripping)", () => {
  archiveSession({
    id: "idx-check",
    label: "Index",
    history: [{ role: "user", content: "catalyst catalyst research! don't stop" }],
  });
  const json = JSON.parse(exportSession("idx-check", "json"));
  assert.equal(json.index.catalyst, 2);
  assert.equal(json.index.research, 1);
  assert.equal(json.index.don, 1); // apostrophe stripped -> "don"
  assert.equal(json.index.stop, 1);
  assert.ok(!("t" in json.index)); // 1-char tokens dropped
});

test("listArchives respects limit", () => {
  assert.equal(listArchives({ limit: 2 }).length, 2);
});

test("listArchives skips corrupt JSON files without crashing", () => {
  const corrupt = path.join(TMP_DIR, "corrupt-file.json");
  fs.writeFileSync(corrupt, "{invalid json!!", "utf-8");
  const archives = listArchives();
  assert.ok(!archives.some((a) => a.id === "corrupt-file"));
  fs.rmSync(corrupt, { force: true });
});

test("searchArchives respects limit", () => {
  for (let i = 1; i <= 3; i++) {
    archiveSession({ id: `limq-${i}`, label: `LimQ ${i}`, history: [
      { role: "user", content: `uniquewordlimq number ${i}` },
    ] });
  }
  const results = searchArchives("uniquewordlimq", { limit: 2 });
  assert.equal(results.length, 2);
});

test("searchArchives combines substring and token scores", () => {
  archiveSession({ id: "score-check", label: "Score", history: [
    { role: "user", content: "the quick brown fox jumps" },
  ] });
  const results = searchArchives("quick brown fox");
  const hit = results.find((r) => r.archiveId === "score-check");
  assert.ok(hit);
  assert.ok(hit.score >= 13); // substring +10, each of 3 tokens in index +1
  assert.equal(hit.matches.length, 1);
});

test("searchArchives caps match previews at 5", () => {
  const history = [];
  for (let i = 0; i < 6; i++) history.push({ role: "user", content: `capmatch line ${i}` });
  archiveSession({ id: "cap-match", label: "Cap", history });
  const results = searchArchives("capmatch");
  const hit = results.find((r) => r.archiveId === "cap-match");
  assert.equal(hit.matches.length, 5); // capped from 6
});

test("getStats reports oldest/newest when archives exist", () => {
  const stats = getStats();
  assert.ok(stats.totalArchives >= 1);
  assert.ok(typeof stats.oldest === "string");
  assert.ok(typeof stats.newest === "string");
  assert.ok(/(KB|MB)$/.test(stats.diskUsage));
});

test("cleanOldArchives with future threshold removes nothing", () => {
  const before = listArchives().length;
  const result = cleanOldArchives(36500, false); // 100 years
  assert.equal(result.count, 0);
  assert.equal(listArchives().length, before);
});

test("addTags with empty array reports added 0", () => {
  archiveSession({ id: "empty-tags", label: "Empty", history: [] });
  const result = addTags("empty-tags", []);
  assert.equal(result.added, 0);
  assert.deepEqual(result.tags, []);
});

test("removeTags with non-existent tag reports removed 0", () => {
  const result = removeTags("tag-test", ["ghost-tag"]);
  assert.equal(result.removed, 0);
  assert.deepEqual(result.tags, ["important", "new-tag"]); // unchanged
});

test("removeTags throws for missing archive", () => {
  assert.throws(() => removeTags("no-such-archive", ["x"]), /not found/);
});

test("diffArchives matching is role-sensitive", () => {
  archiveSession({ id: "diff-role-a", label: "RA", history: [
    { role: "user", content: "same words here" },
  ] });
  archiveSession({ id: "diff-role-b", label: "RB", history: [
    { role: "assistant", content: "same words here" },
  ] });
  const diff = diffArchives("diff-role-a", "diff-role-b");
  assert.equal(diff.commonCount, 0);
  assert.equal(diff.onlyInA.length, 1);
  assert.equal(diff.onlyInB.length, 1);
});

test("diffArchives similarity reflects partial overlap", () => {
  archiveSession({ id: "diff-g", label: "G", history: [
    { role: "user", content: "common line" },
    { role: "user", content: "g only line" },
  ] });
  archiveSession({ id: "diff-h", label: "H", history: [
    { role: "user", content: "common line" },
  ] });
  const diff = diffArchives("diff-g", "diff-h");
  assert.equal(diff.commonCount, 1);
  assert.equal(diff.similarity, "0.67"); // 2*1/(2+1)
});

test("toMarkdown falls back to msg.text and unknown role", () => {
  archiveSession({ id: "md-fallback", label: "Fallback", history: [
    { text: "via text field only" },
  ] });
  const md = exportSession("md-fallback", "markdown");
  assert.ok(md.includes("UNKNOWN"));
  assert.ok(md.includes("via text field only"));
});

test("mergeArchives orders sources chronologically by archivedAt", async () => {
  archiveSession({ id: "merge-first", label: "First", history: [
    { role: "user", content: "earlier message" },
  ] });
  await new Promise((r) => setTimeout(r, 15)); // ensure distinct archivedAt
  archiveSession({ id: "merge-second", label: "Second", history: [
    { role: "assistant", content: "later message" },
  ] });
  const result = mergeArchives(["merge-second", "merge-first"], { id: "merge-ordered" }); // reversed input order
  const json = JSON.parse(exportSession("merge-ordered", "json"));
  assert.equal(json.history[0]._source, "merge-first");
  assert.equal(json.history[1]._source, "merge-second");
  assert.equal(json.meta.sources[0].id, "merge-first");
  assert.equal(result.totalMessages, 2);
});
