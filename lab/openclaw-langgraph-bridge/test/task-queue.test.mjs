import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { TaskQueue } from "../dist/task-queue.js";

describe("TaskQueue", () => {
  it("enqueues and dequeues tasks", () => {
    const q = new TaskQueue();
    q.enqueue({ id: "t1", payload: "hello" });
    q.enqueue({ id: "t2", payload: "world" });
    assert.equal(q.size, 2);
    const task = q.dequeue();
    assert.equal(task.id, "t1");
    assert.equal(q.size, 1);
  });

  it("respects priority ordering", () => {
    const q = new TaskQueue();
    q.enqueue({ id: "low", payload: "low", priority: 1 });
    q.enqueue({ id: "high", payload: "high", priority: 10 });
    q.enqueue({ id: "mid", payload: "mid", priority: 5 });
    assert.equal(q.dequeue().id, "high");
    assert.equal(q.dequeue().id, "mid");
    assert.equal(q.dequeue().id, "low");
  });

  it("FIFO within same priority", () => {
    const q = new TaskQueue();
    q.enqueue({ id: "a", payload: "a", priority: 5 });
    q.enqueue({ id: "b", payload: "b", priority: 5 });
    assert.equal(q.dequeue().id, "a");
    assert.equal(q.dequeue().id, "b");
  });

  it("default priority is 0", () => {
    const q = new TaskQueue();
    q.enqueue({ id: "no-pri", payload: "x" });
    q.enqueue({ id: "pri-1", payload: "y", priority: 1 });
    assert.equal(q.dequeue().id, "pri-1");
  });

  it("peek returns next task without removing", () => {
    const q = new TaskQueue();
    q.enqueue({ id: "t1", payload: "hello" });
    const peeked = q.peek();
    assert.equal(peeked.id, "t1");
    assert.equal(q.size, 1);
  });

  it("peek returns undefined on empty queue", () => {
    const q = new TaskQueue();
    assert.equal(q.peek(), undefined);
  });

  it("dequeue returns undefined on empty queue", () => {
    const q = new TaskQueue();
    assert.equal(q.dequeue(), undefined);
  });

  it("isEmpty and size", () => {
    const q = new TaskQueue();
    assert.equal(q.isEmpty, true);
    assert.equal(q.size, 0);
    q.enqueue({ id: "t1", payload: "x" });
    assert.equal(q.isEmpty, false);
    assert.equal(q.size, 1);
  });

  it("drain returns all tasks and empties queue", () => {
    const q = new TaskQueue();
    q.enqueue({ id: "t1", payload: "a", priority: 2 });
    q.enqueue({ id: "t2", payload: "b", priority: 1 });
    const drained = q.drain();
    assert.equal(drained.length, 2);
    assert.equal(drained[0].id, "t1"); // higher priority first
    assert.equal(q.size, 0);
    assert.equal(q.isEmpty, true);
  });

  it("filterByCapability returns matching tasks", () => {
    const q = new TaskQueue();
    q.enqueue({ id: "t1", payload: "a", capability: "code" });
    q.enqueue({ id: "t2", payload: "b", capability: "review" });
    q.enqueue({ id: "t3", payload: "c" }); // no capability = matches all
    const code = q.filterByCapability("code");
    assert.equal(code.length, 2); // t1 (explicit) + t3 (wildcard)
    const ids = code.map(t => t.id).sort();
    assert.deepEqual(ids, ["t1", "t3"]);
  });

  it("remove by ID", () => {
    const q = new TaskQueue();
    q.enqueue({ id: "t1", payload: "a" });
    q.enqueue({ id: "t2", payload: "b" });
    const removed = q.remove("t1");
    assert.equal(removed.id, "t1");
    assert.equal(q.size, 1);
    assert.equal(q.peek().id, "t2");
  });

  it("remove returns undefined for unknown ID", () => {
    const q = new TaskQueue();
    assert.equal(q.remove("nope"), undefined);
  });

  it("getAll returns snapshot without modifying queue", () => {
    const q = new TaskQueue();
    q.enqueue({ id: "t1", payload: "a" });
    const all = q.getAll();
    assert.equal(all.length, 1);
    assert.equal(q.size, 1); // not modified
  });

  it("sets enqueuedAt timestamp", () => {
    const q = new TaskQueue();
    const before = Date.now();
    q.enqueue({ id: "t1", payload: "x" });
    const after = Date.now();
    const task = q.peek();
    assert.ok(task.enqueuedAt >= before);
    assert.ok(task.enqueuedAt <= after);
  });

  it("enqueue returns this for chaining", () => {
    const q = new TaskQueue();
    const result = q.enqueue({ id: "t1", payload: "a" });
    assert.ok(result instanceof TaskQueue);
  });
});
