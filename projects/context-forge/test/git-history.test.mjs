import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile, mkdir } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { execFileSync } from "node:child_process";
import { analyzeGitHistory } from "../context-forge.mjs";

function git(cwd, ...args) {
  return execFileSync("git", args, { cwd, encoding: "utf8", stdio: "pipe" });
}

async function makeRepo(files = {}) {
  const dir = await mkdtemp(join(tmpdir(), "ctxforge-git-"));
  git(dir, "init", "--quiet");
  git(dir, "config", "user.email", "test@test.com");
  git(dir, "config", "user.name", "Test User");
  for (const [path, content] of Object.entries(files)) {
    const fullPath = join(dir, path);
    const parent = fullPath.substring(0, fullPath.lastIndexOf("/"));
    await mkdir(parent, { recursive: true });
    await writeFile(fullPath, content);
  }
  return dir;
}

describe("analyzeGitHistory", () => {
  let tmpDir;

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("returns isRepo=false for non-git directory", async () => {
    tmpDir = await mkdtemp(join(tmpdir(), "ctxforge-nogit-"));
    const result = await analyzeGitHistory(tmpDir);
    assert.equal(result.isRepo, false);
    assert.equal(result.totalCommits, 0);
    assert.deepEqual(result.contributors, []);
    assert.deepEqual(result.recentCommits, []);
  });

  it("detects git repo and counts commits", async () => {
    tmpDir = await makeRepo({ "README.md": "# hello" });
    git(tmpDir, "add", ".");
    git(tmpDir, "commit", "--quiet", "-m", "initial commit");

    const result = await analyzeGitHistory(tmpDir);
    assert.equal(result.isRepo, true);
    assert.ok(result.totalCommits >= 1);
  });

  it("extracts contributors", async () => {
    tmpDir = await makeRepo({ "file.txt": "v1" });
    git(tmpDir, "add", ".");
    git(tmpDir, "commit", "--quiet", "-m", "first");

    git(tmpDir, "config", "user.name", "Alice");
    git(tmpDir, "config", "user.email", "alice@test.com");
    await writeFile(join(tmpDir, "file.txt"), "v2");
    git(tmpDir, "add", ".");
    git(tmpDir, "commit", "--quiet", "-m", "second");

    const result = await analyzeGitHistory(tmpDir);
    assert.ok(result.contributors.length >= 1);
    const alice = result.contributors.find((c) => c.name === "Alice");
    assert.ok(alice, "Alice should be in contributors");
    assert.ok(alice.commits >= 1);
  });

  it("returns recent commits with hash/author/date/subject", async () => {
    tmpDir = await makeRepo({ "f.txt": "1" });
    git(tmpDir, "add", ".");
    git(tmpDir, "commit", "--quiet", "-m", "fix: something");

    const result = await analyzeGitHistory(tmpDir);
    assert.ok(result.recentCommits.length >= 1);
    const c = result.recentCommits[0];
    assert.ok(c.hash.length >= 7);
    assert.ok(c.author);
    assert.ok(c.date);
    assert.ok(c.subject.includes("something"));
  });

  it("limits recent commits to maxCommits", async () => {
    tmpDir = await makeRepo({});
    for (let i = 0; i < 10; i++) {
      await writeFile(join(tmpDir, `f${i}.txt`), String(i));
      git(tmpDir, "add", ".");
      git(tmpDir, "commit", "--quiet", "-m", `commit ${i}`);
    }

    const result = await analyzeGitHistory(tmpDir, 3);
    assert.ok(result.recentCommits.length <= 3);
  });

  it("computes commit frequency by day of week", async () => {
    tmpDir = await makeRepo({ "a.txt": "1" });
    git(tmpDir, "add", ".");
    git(tmpDir, "commit", "--quiet", "-m", "init");

    const result = await analyzeGitHistory(tmpDir);
    assert.ok(typeof result.commitFrequency === "object");
    const totalFreq = Object.values(result.commitFrequency).reduce((a, b) => a + b, 0);
    assert.ok(totalFreq >= 1, "at least one commit should be counted");
  });

  it("tracks top changed files", async () => {
    tmpDir = await makeRepo({ "hot.txt": "1", "cold.txt": "1" });
    git(tmpDir, "add", ".");
    git(tmpDir, "commit", "--quiet", "-m", "init");

    // Modify hot.txt multiple times
    for (let i = 0; i < 3; i++) {
      await writeFile(join(tmpDir, "hot.txt"), `v${i + 2}`);
      git(tmpDir, "add", ".");
      git(tmpDir, "commit", "--quiet", "-m", `update ${i}`);
    }

    const result = await analyzeGitHistory(tmpDir);
    assert.ok(result.topFilesChanged.length >= 1);
    const hot = result.topFilesChanged.find((f) => f.file === "hot.txt");
    assert.ok(hot, "hot.txt should be in top changed files");
    assert.ok(hot.changes >= 3, "hot.txt should have at least 3 changes");
  });

  it("handles empty repo (no commits) gracefully", async () => {
    tmpDir = await mkdtemp(join(tmpdir(), "ctxforge-empty-"));
    git(tmpDir, "init", "--quiet");
    git(tmpDir, "config", "user.email", "test@test.com");
    git(tmpDir, "config", "user.name", "Test");

    const result = await analyzeGitHistory(tmpDir);
    assert.equal(result.isRepo, true);
    assert.equal(result.totalCommits, 0);
    assert.deepEqual(result.contributors, []);
    assert.deepEqual(result.recentCommits, []);
  });
});
