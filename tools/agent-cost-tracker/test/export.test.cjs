/**
 * Tests for export.js formatters (exportToJSON/exportToCSV/exportToMarkdown)
 * and additional storage.js edge cases.
 *
 * Covers the 2026-08-15 bug fix: export.js previously imported a
 * non-existent `getBudgetStart` from storage.js, crashing `act export`
 * at module load. These tests pin the module contract.
 */
const { describe, it } = require("node:test");
const assert = require("node:assert/strict");

(async () => {
  // Must load without SyntaxError (regression: phantom getBudgetStart import)
  const exportMod = await import("../lib/commands/export.js");
  const storage = await import("../lib/storage.js");

  const logs = [
    {
      id: "a1",
      timestamp: "2026-08-14T10:00:00.000Z",
      model: "gpt-4",
      promptTokens: 1000,
      completionTokens: 500,
      cost: 1.0,
      session: "s1",
      note: "first run"
    },
    {
      id: "b2",
      timestamp: "2026-08-14T11:30:00.000Z",
      model: "gpt-4",
      promptTokens: 200,
      completionTokens: 100
      // no cost → derived from default pricing (gpt-4: $30/$60 per 1M)
    }
  ];

  describe("export module contract", () => {
    it("loads without phantom import error (getBudgetStart regression)", async () => {
      assert.equal(typeof exportMod.default, "function");
      assert.equal(typeof exportMod.exportToJSON, "function");
      assert.equal(typeof exportMod.exportToCSV, "function");
      assert.equal(typeof exportMod.exportToMarkdown, "function");
    });
  });

  describe("exportToJSON", () => {
    it("returns valid JSON with summary and data array", () => {
      const parsed = JSON.parse(exportMod.exportToJSON(logs));
      assert.equal(parsed.summary.totalRequests, 2);
      assert.equal(parsed.summary.totalTokens, 1800);
      assert.equal(parsed.summary.totalCost, 1.0 + 200 / 1e6 * 30 + 100 / 1e6 * 60);
      assert.ok(Array.isArray(parsed.data));
      assert.equal(parsed.data.length, 2);
      assert.ok(parsed.exportedAt);
    });

    it("computes totalTokens per row and defaults missing fields", () => {
      const parsed = JSON.parse(exportMod.exportToJSON([
        { id: "x", timestamp: "2026-08-14T10:00:00.000Z", model: "glm-4", cost: 0.5 }
      ]));
      const row = parsed.data[0];
      assert.equal(row.totalTokens, 0);
      assert.equal(row.session, undefined);
      assert.equal(row.cost, 0.5);
    });

    it("handles empty logs", () => {
      const parsed = JSON.parse(exportMod.exportToJSON([]));
      assert.equal(parsed.summary.totalRequests, 0);
      assert.equal(parsed.summary.totalCost, 0);
    });
  });

  describe("exportToCSV", () => {
    it("emits header row followed by one row per log", () => {
      const lines = exportMod.exportToCSV(logs).split("\n");
      assert.equal(lines.length, 3);
      assert.match(lines[0], /^ID,Timestamp,Model,/);
      assert.match(lines[1], /^a1,/);
    });

    it("formats cost to 6 decimal places", () => {
      const line = exportMod.exportToCSV(logs).split("\n")[1];
      const costField = line.split(",")[6];
      assert.match(costField, /^\d+\.\d{6}$/);
    });

    it("replaces commas in notes to keep CSV well-formed", () => {
      const csv = exportMod.exportToCSV([
        { id: "n1", timestamp: "2026-08-14T10:00:00.000Z", model: "gpt-4", promptTokens: 1, completionTokens: 1, cost: 1, note: "a,b,c" }
      ]);
      const dataRow = csv.split("\n")[1];
      assert.equal(dataRow.split(",").length, 9);
      assert.ok(dataRow.includes("a；b；c"));
    });

    it("defaults missing tokens/session to 0/empty", () => {
      const row = exportMod.exportToCSV([
        { id: "z", timestamp: "2026-08-14T10:00:00.000Z", model: "gpt-4", cost: 2 }
      ]).split("\n")[1].split(",");
      assert.equal(row[3], "0"); // prompt
      assert.equal(row[4], "0"); // completion
      assert.equal(row[5], "0"); // total
      assert.equal(row[7], "");  // session
    });
  });

  describe("exportToMarkdown", () => {
    it("renders summary section and one table row per log", () => {
      const md = exportMod.exportToMarkdown(logs, "month");
      assert.match(md, /^# AI 成本报告/);
      assert.match(md, /\*\*时间范围:\*\* month/);
      assert.match(md, /\*\*总请求次数:\*\* 2/);
      const tableRows = md.split("\n").filter(l => l.startsWith("| 08-14"));
      assert.equal(tableRows.length, 2);
    });

    it("uses '-' for missing session", () => {
      const md = exportMod.exportToMarkdown(
        [{ id: "m", timestamp: "2026-08-14T10:00:00.000Z", model: "gpt-4", promptTokens: 10, completionTokens: 5, cost: 1 }],
        "all"
      );
      const row = md.split("\n").find(l => l.startsWith("| 08-14"));
      assert.ok(row.trim().endsWith("| - |"));
    });
  });

  describe("calculateCost default pricing (additional coverage)", () => {
    it("computes gpt-4 cost from default per-1M pricing", () => {
      // input $30/M, output $60/M
      const cost = storage.calculateCost({ model: "gpt-4", promptTokens: 1_000_000, completionTokens: 500_000 });
      assert.ok(Math.abs(cost - 60) < 1e-9);
    });

    it("supports CNY-priced models (glm-4)", () => {
      const cost = storage.calculateCost({ model: "glm-4", promptTokens: 2_000_000, completionTokens: 0 });
      assert.ok(Math.abs(cost - 1) < 1e-9); // ¥0.5/M × 2M
    });

    it("cost of 0 falls through to token-based calculation", () => {
      const cost = storage.calculateCost({ model: "gpt-4", cost: 0, promptTokens: 1_000_000, completionTokens: 0 });
      assert.ok(cost > 0); // explicit 0 is falsy — derived instead
    });
  });

  describe("getStats fallback grouping", () => {
    it("uses 'other' key for unknown groupBy", () => {
      const stats = storage.getStats(
        [{ model: "gpt-4", promptTokens: 10, completionTokens: 5, cost: 1 }],
        "nonsense"
      );
      assert.equal(stats["other"].requests, 1);
      assert.equal(stats["other"].tokens, 15);
      assert.equal(stats["other"].cost, 1);
    });
  });
})();
