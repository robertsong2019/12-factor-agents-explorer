/**
 * Tests for openclaw-api.js
 */
const { describe, it, before, after } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const os = require("os");

const { listLiveSessions, fetchSessionHistory } = require("./openclaw-api.js");

const TMP_HOME = path.join(os.tmpdir(), `sa-api-test-${Date.now()}`);
const SESSIONS_DIR = path.join(TMP_HOME, "sessions");

before(() => {
  fs.mkdirSync(SESSIONS_DIR, { recursive: true });
});

after(() => {
  if (fs.existsSync(TMP_HOME)) fs.rmSync(TMP_HOME, { recursive: true });
});

describe("listLiveSessions", () => {
  it("returns an array", async () => {
    const result = await listLiveSessions();
    assert.ok(Array.isArray(result), "should return an array");
  });

  it("returns empty array in standalone mode", async () => {
    const result = await listLiveSessions();
    assert.equal(result.length, 0);
  });
});

describe("fetchSessionHistory", () => {
  it("returns empty array when session not found", async () => {
    process.env.OPENCLAW_HOME = TMP_HOME;
    const result = await fetchSessionHistory("nonexistent-session");
    assert.ok(Array.isArray(result));
    assert.equal(result.length, 0);
  });

  it("reads JSON session file", async () => {
    process.env.OPENCLAW_HOME = TMP_HOME;
    const sessionData = [{ role: "user", content: "hello" }, { role: "assistant", content: "hi" }];
    fs.writeFileSync(path.join(SESSIONS_DIR, "test-session.json"), JSON.stringify(sessionData));

    const result = await fetchSessionHistory("test-session");
    assert.ok(Array.isArray(result));
    assert.equal(result.length, 2);
    assert.equal(result[0].role, "user");
    assert.equal(result[1].content, "hi");
  });

  it("reads line-delimited JSON session file", async () => {
    process.env.OPENCLAW_HOME = TMP_HOME;
    const lines = [
      JSON.stringify({ role: "user", content: "line1" }),
      JSON.stringify({ role: "assistant", content: "line2" }),
    ].join("\n");
    fs.writeFileSync(path.join(SESSIONS_DIR, "ldjson-session.json"), lines);

    const result = await fetchSessionHistory("ldjson-session");
    assert.ok(Array.isArray(result));
    assert.equal(result.length, 2);
    assert.equal(result[0].content, "line1");
    assert.equal(result[1].content, "line2");
  });

  it("handles malformed JSON gracefully as text lines", async () => {
    process.env.OPENCLAW_HOME = TMP_HOME;
    fs.writeFileSync(path.join(SESSIONS_DIR, "bad-session.json"), "not json\nalso not json");

    const result = await fetchSessionHistory("bad-session");
    assert.ok(Array.isArray(result));
    assert.equal(result.length, 2);
    assert.ok(result[0].text.includes("not json"));
  });

  it("respects OPENCLAW_HOME env variable", async () => {
    const customHome = path.join(os.tmpdir(), `sa-custom-${Date.now()}`);
    const customSessions = path.join(customHome, "sessions");
    fs.mkdirSync(customSessions, { recursive: true });
    process.env.OPENCLAW_HOME = customHome;

    fs.writeFileSync(path.join(customSessions, "custom.json"), JSON.stringify([{ msg: "custom" }]));

    const result = await fetchSessionHistory("custom");
    assert.equal(result.length, 1);
    assert.equal(result[0].msg, "custom");

    fs.rmSync(customHome, { recursive: true });
  });
});
