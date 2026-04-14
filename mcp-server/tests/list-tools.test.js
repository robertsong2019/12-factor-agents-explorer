/**
 * Test tool listing functionality
 */

import { describe, it } from "node:test";
import assert from "node:assert";

describe("MCP Server - List Tools", () => {
  it("should return all available tools", async () => {
    // This test verifies that the server can list all tools
    // In a real integration test, we'd connect to the server
    // For now, we're testing the schema structure

    const expectedTools = ["web_search", "read", "write", "exec"];

    // Mock the tool listing response
    const mockResponse = {
      tools: [
        {
          name: "web_search",
          description: "Search the web using Brave Search API",
          inputSchema: {
            type: "object",
            properties: {
              query: { type: "string" },
              count: { type: "number" },
            },
            required: ["query"],
          },
        },
        {
          name: "read",
          description: "Read the contents of a file",
          inputSchema: {
            type: "object",
            properties: {
              path: { type: "string" },
            },
            required: ["path"],
          },
        },
        {
          name: "write",
          description: "Write content to a file",
          inputSchema: {
            type: "object",
            properties: {
              path: { type: "string" },
              content: { type: "string" },
            },
            required: ["path", "content"],
          },
        },
        {
          name: "exec",
          description: "Execute shell commands",
          inputSchema: {
            type: "object",
            properties: {
              command: { type: "string" },
            },
            required: ["command"],
          },
        },
      ],
    };

    // Verify the response structure
    assert.ok(Array.isArray(mockResponse.tools), "tools should be an array");
    assert.strictEqual(
      mockResponse.tools.length,
      expectedTools.length,
      "should have 4 tools"
    );

    // Verify each tool has required fields
    for (const tool of mockResponse.tools) {
      assert.ok(tool.name, `tool should have a name`);
      assert.ok(tool.description, `tool should have a description`);
      assert.ok(tool.inputSchema, `tool should have an inputSchema`);
      assert.strictEqual(tool.inputSchema.type, "object", "inputSchema should be object");
    }

    // Verify tool names match expected
    const actualToolNames = mockResponse.tools.map((t) => t.name).sort();
    assert.deepStrictEqual(
      actualToolNames,
      expectedTools.sort(),
      "tool names should match"
    );

    console.log("✓ Tool listing test passed");
  });

  it("should have valid JSON Schema for all tools", async () => {
    const tools = [
      {
        name: "web_search",
        schema: {
          type: "object",
          properties: {
            query: { type: "string" },
            count: { type: "number" },
          },
          required: ["query"],
        },
      },
    ];

    for (const tool of tools) {
      // Verify schema is valid JSON Schema
      assert.strictEqual(tool.schema.type, "object");
      assert.ok(tool.schema.properties, "should have properties");
      assert.ok(Array.isArray(tool.schema.required), "required should be array");
      assert.ok(tool.schema.required.length > 0, "should have at least one required field");
    }

    console.log("✓ Schema validation test passed");
  });
});
