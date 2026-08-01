/**
 * Tests for storage.js — cost calculation and stats utilities.
 * Uses Node's built-in test runner (node:test) to avoid Jest ESM issues.
 *
 * We test the pure functions by importing them directly.
 * The conf dependency is initialized with default data on first import,
 * so we test against the default model pricing.
 */
const { describe, it } = require("node:test");
const assert = require("node:assert/strict");

// Import the module — it uses ESM, so we need dynamic import
let storage;

(async () => {
  storage = await import("../lib/storage.js");

  describe("calculateCost", () => {
    it("returns explicit cost when provided", () => {
      const log = { cost: 1.5, model: "gpt-4", promptTokens: 1000, completionTokens: 500 };
      assert.equal(storage.calculateCost(log), 1.5);
    });

    it("returns 0 for unknown model", () => {
      const log = { model: "totally-unknown-model", promptTokens: 1000, completionTokens: 500 };
      assert.equal(storage.calculateCost(log), 0);
    });

    it("handles missing token fields", () => {
      const log = { model: "gpt-4" };
      // With no explicit cost and no tokens, cost should be 0 or based on defaults
      const cost = storage.calculateCost(log);
      assert.ok(typeof cost === "number");
      assert.ok(cost >= 0);
    });

    it("handles zero tokens", () => {
      const log = { model: "gpt-4", promptTokens: 0, completionTokens: 0 };
      assert.equal(storage.calculateCost(log), 0);
    });
  });

  describe("calculateTotalCost", () => {
    it("sums costs across multiple logs", () => {
      const logs = [
        { cost: 1.0, model: "gpt-4", promptTokens: 0, completionTokens: 0 },
        { cost: 2.5, model: "gpt-4", promptTokens: 0, completionTokens: 0 },
        { cost: 0.5, model: "gpt-4", promptTokens: 0, completionTokens: 0 },
      ];
      assert.equal(storage.calculateTotalCost(logs), 4.0);
    });

    it("returns 0 for empty array", () => {
      assert.equal(storage.calculateTotalCost([]), 0);
    });
  });

  describe("getStats", () => {
    it("returns aggregate stats when no groupBy", () => {
      const logs = [
        { model: "gpt-4", promptTokens: 100, completionTokens: 50, cost: 1.0 },
        { model: "gpt-3.5-turbo", promptTokens: 200, completionTokens: 100, cost: 0.5 },
      ];
      const stats = storage.getStats(logs);
      assert.equal(stats.totalRequests, 2);
      assert.equal(stats.totalTokens, 450);
      assert.equal(stats.totalCost, 1.5);
    });

    it("handles empty logs", () => {
      const stats = storage.getStats([]);
      assert.equal(stats.totalRequests, 0);
      assert.equal(stats.totalTokens, 0);
      assert.equal(stats.totalCost, 0);
    });

    it("groups by model", () => {
      const logs = [
        { model: "gpt-4", promptTokens: 100, completionTokens: 0, cost: 1.0 },
        { model: "gpt-4", promptTokens: 200, completionTokens: 0, cost: 2.0 },
        { model: "gpt-3.5-turbo", promptTokens: 500, completionTokens: 0, cost: 0.5 },
      ];
      const stats = storage.getStats(logs, "model");
      assert.equal(stats["gpt-4"].requests, 2);
      assert.equal(stats["gpt-4"].tokens, 300);
      assert.equal(stats["gpt-4"].cost, 3.0);
      assert.equal(stats["gpt-3.5-turbo"].requests, 1);
    });

    it("groups by session", () => {
      const logs = [
        { model: "gpt-4", session: "s1", promptTokens: 100, completionTokens: 0, cost: 1.0 },
        { model: "gpt-4", session: "s2", promptTokens: 200, completionTokens: 0, cost: 2.0 },
        { model: "gpt-4", promptTokens: 50, completionTokens: 0, cost: 0.5 },
      ];
      const stats = storage.getStats(logs, "session");
      assert.equal(stats["s1"].requests, 1);
      assert.equal(stats["s2"].requests, 1);
      assert.equal(stats["none"].requests, 1);
    });

    it("groups by day", () => {
      const logs = [
        { model: "gpt-4", timestamp: "2025-01-01T10:00:00Z", promptTokens: 100, completionTokens: 0, cost: 1.0 },
        { model: "gpt-4", timestamp: "2025-01-01T15:00:00Z", promptTokens: 200, completionTokens: 0, cost: 2.0 },
        { model: "gpt-4", timestamp: "2025-01-02T10:00:00Z", promptTokens: 50, completionTokens: 0, cost: 0.5 },
      ];
      const stats = storage.getStats(logs, "day");
      assert.equal(stats["2025-01-01"].requests, 2);
      assert.equal(stats["2025-01-02"].requests, 1);
    });
  });
})();
