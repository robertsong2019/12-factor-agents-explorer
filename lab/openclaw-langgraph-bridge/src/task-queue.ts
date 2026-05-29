/**
 * Priority-based task queue for Supervisor agent scheduling.
 */

export interface QueueTask {
  /** Unique task ID */
  id: string;
  /** Task payload */
  payload: string;
  /** Priority (higher = more urgent, default 0) */
  priority?: number;
  /** Required capability (optional) */
  capability?: string;
  /** Enqueue timestamp */
  enqueuedAt: number;
}

export class TaskQueue {
  private queue: QueueTask[] = [];

  /** Enqueue a task */
  enqueue(task: Omit<QueueTask, "enqueuedAt">): this {
    this.queue.push({ ...task, enqueuedAt: Date.now(), priority: task.priority ?? 0 });
    // Keep sorted by priority desc, then FIFO within same priority
    this.queue.sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0) || a.enqueuedAt - b.enqueuedAt);
    return this;
  }

  /** Dequeue the highest-priority task */
  dequeue(): QueueTask | undefined {
    return this.queue.shift();
  }

  /** Peek at the next task without removing it */
  peek(): QueueTask | undefined {
    return this.queue[0];
  }

  /** Current queue size */
  get size(): number {
    return this.queue.length;
  }

  /** Check if queue is empty */
  get isEmpty(): boolean {
    return this.queue.length === 0;
  }

  /** Drain all tasks (returns them in priority order) */
  drain(): QueueTask[] {
    const tasks = [...this.queue];
    this.queue = [];
    return tasks;
  }

  /** Filter tasks by capability */
  filterByCapability(capability: string): QueueTask[] {
    return this.queue.filter(t => !t.capability || t.capability === capability);
  }

  /** Remove a specific task by ID */
  remove(taskId: string): QueueTask | undefined {
    const idx = this.queue.findIndex(t => t.id === taskId);
    if (idx === -1) return undefined;
    return this.queue.splice(idx, 1)[0];
  }

  /** Get all tasks (read-only snapshot) */
  getAll(): QueueTask[] {
    return [...this.queue];
  }
}
