import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { toolHandlers, OPENCLAW_TOOLS } from "../dist/tools.js";

const webSearch = toolHandlers.web_search;

describe("web_search tool", () => {
  it("should return results structure for valid query", async () => {
    const r = await webSearch({ query: "test query" });
    assert.equal(r.tool, "web_search");
    assert.equal(r.query, "test query");
    assert.ok(Array.isArray(r.results));
  });

  it("should handle empty results gracefully", async () => {
    const r = await webSearch({ query: "obscure query with no results" });
    assert.equal(r.results.length, 0);
    assert.ok(r.note, "should include a note about the search");
  });

  it("should accept optional count parameter", async () => {
    const r = await webSearch({ query: "test", count: 5 });
    assert.equal(r.tool, "web_search");
    assert.equal(r.query, "test");
  });

  it("should accept optional country parameter", async () => {
    const r = await webSearch({ query: "test", country: "US" });
    assert.equal(r.query, "test");
  });

  it("should accept optional language parameter", async () => {
    const r = await webSearch({ query: "test", language: "en" });
    assert.equal(r.query, "test");
  });

  it("should accept optional freshness parameter", async () => {
    const r = await webSearch({ query: "test", freshness: "week" });
    assert.equal(r.query, "test");
  });

  it("should throw on missing query parameter", async () => {
    await assert.rejects(
      async () => webSearch({}),
      { message: /query/ }
    );
  });

  it("should throw on non-string query", async () => {
    await assert.rejects(
      async () => webSearch({ query: 123 }),
      { message: /query/ }
    );
  });
});

describe("web_search tool definition", () => {
  const def = OPENCLAW_TOOLS.find(t => t.name === "web_search");

  it("should be registered in OPENCLAW_TOOLS", () => {
    assert.ok(def, "web_search tool definition not found");
  });

  it("should have correct name", () => {
    assert.equal(def.name, "web_search");
  });

  it("should have a description", () => {
    assert.ok(def.description.length > 10);
  });

  it("should require query parameter", () => {
    assert.ok(def.inputSchema.required.includes("query"));
  });

  it("should define query as string", () => {
    assert.equal(def.inputSchema.properties.query.type, "string");
  });

  it("should define count as number with default 5", () => {
    assert.equal(def.inputSchema.properties.count.type, "number");
    assert.equal(def.inputSchema.properties.count.default, 5);
  });

  it("should define count min/max bounds", () => {
    assert.equal(def.inputSchema.properties.count.minimum, 1);
    assert.equal(def.inputSchema.properties.count.maximum, 10);
  });

  it("should support country parameter", () => {
    assert.equal(def.inputSchema.properties.country.type, "string");
    assert.equal(def.inputSchema.properties.country.default, "US");
  });

  it("should support language parameter", () => {
    assert.equal(def.inputSchema.properties.language.type, "string");
  });

  it("should support freshness enum", () => {
    const fresh = def.inputSchema.properties.freshness;
    assert.deepEqual(fresh.enum, ["day", "week", "month", "year"]);
  });
});
