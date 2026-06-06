/**
 * Edge case tests for safePath, validateExecCommand, setWorkspaceRoot.
 * Targets untested branches in path sandboxing and command validation.
 */
import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdir, writeFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { toolHandlers, safePath, validateExecCommand, setWorkspaceRoot, WORKSPACE_ROOT } from "../dist/tools.js";

const TEST_DIR = join(process.cwd(), ".test-validation");

describe("safePath edge cases", () => {
  it("should resolve absolute path within workspace", () => {
    const result = safePath(WORKSPACE_ROOT + "/subdir/file.txt");
    assert.ok(result.startsWith(WORKSPACE_ROOT));
  });

  it("should resolve relative path within workspace", () => {
    const result = safePath("src/index.ts");
    assert.ok(result.startsWith(WORKSPACE_ROOT));
  });

  it("should resolve . without traversal", () => {
    const result = safePath(".");
    assert.ok(result.startsWith(WORKSPACE_ROOT));
  });

  it("should reject double-dot traversal", () => {
    assert.throws(() => safePath("../../etc/passwd"), /Path traversal/);
  });

  it("should reject deep traversal", () => {
    assert.throws(() => safePath("a/b/../../../etc"), /Path traversal/);
  });

  it("should allow subdir with .. in name (non-traversing)", () => {
    // "foo/../bar" resolves to "bar" within workspace — should be fine
    const result = safePath("foo/../bar");
    assert.ok(result.startsWith(WORKSPACE_ROOT));
  });

  it("should reject absolute path outside workspace", () => {
    assert.throws(() => safePath("/etc/shadow"), /Path traversal/);
  });

  it("should reject /tmp", () => {
    assert.throws(() => safePath("/tmp/evil"), /Path traversal/);
  });
});

describe("setWorkspaceRoot", () => {
  it("should change the workspace root", () => {
    const original = WORKSPACE_ROOT;
    setWorkspaceRoot("/tmp");
    // After set, paths resolve relative to /tmp
    const result = safePath("myfile.txt");
    assert.ok(result.startsWith("/tmp"));
    // Restore
    setWorkspaceRoot(original);
  });

  it("should affect traversal check boundaries", () => {
    const original = WORKSPACE_ROOT;
    setWorkspaceRoot("/tmp");
    // /etc is now outside workspace
    assert.throws(() => safePath("/etc/shadow"), /Path traversal/);
    // But /tmp is fine
    const result = safePath("/tmp/sub/file");
    assert.ok(result.startsWith("/tmp"));
    setWorkspaceRoot(original);
  });
});

describe("validateExecCommand edge cases", () => {
  it("should block format command (Windows)", () => {
    const result = validateExecCommand("format C:");
    assert.equal(result.valid, false);
  });

  it("should block chmod 777 /", () => {
    const result = validateExecCommand("chmod 777 /");
    assert.equal(result.valid, false);
  });

  it("should block :> redirect to file path", () => {
    const result = validateExecCommand(":>./important-file");
    assert.equal(result.valid, false);
  });

  it("should allow chmod on regular files", () => {
    const result = validateExecCommand("chmod 755 script.sh");
    assert.equal(result.valid, true);
  });

  it("should allow safe piped commands", () => {
    const result = validateExecCommand("cat file | grep pattern");
    assert.equal(result.valid, true);
  });

  it("should allow npm install", () => {
    const result = validateExecCommand("npm install express");
    assert.equal(result.valid, true);
  });

  it("should allow git commands", () => {
    const result = validateExecCommand("git commit -m 'fix'");
    assert.equal(result.valid, true);
  });

  it("should block writing to device files", () => {
    const result = validateExecCommand("echo data > /dev/sda");
    assert.equal(result.valid, false);
  });

  it("should allow empty string", () => {
    const result = validateExecCommand("");
    assert.equal(result.valid, true);
  });

  it("should block rm -rf / with extra spaces", () => {
    const result = validateExecCommand("  rm   -rf   /  ");
    assert.equal(result.valid, false);
  });

  it("should block chown to root", () => {
    const result = validateExecCommand("chown root:* /");
    assert.equal(result.valid, false);
  });

  it("should block Windows del /f", () => {
    const result = validateExecCommand("del /f *");
    assert.equal(result.valid, false);
  });
});
