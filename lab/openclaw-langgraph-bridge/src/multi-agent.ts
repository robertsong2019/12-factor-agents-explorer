/**
 * multi-agent.ts — 多 Agent 编排的高层 API
 * 
 * Phase 1: 单机多 Agent 编排
 * - AgentPool: 管理多个 Agent（Claude Code / Codex / 自定义）
 * - createCodeWorkflow: 标准编码工作流（分析→编码→测试→审查）
 */

import { createOpenClawNode, type OpenClawNodeConfig, type AgentState } from "./create-node.js";
import { withRetry, type RetryConfig } from "./retry.js";

// ── Types ──────────────────────────────────────────────

/** Agent 角色定义 */
export interface AgentRole {
  id: string;
  description: string;
  config: OpenClawNodeConfig;
  capabilities: string[];
}

/** 任务定义 */
export interface Task {
  id: string;
  description: string;
  type: string;
  input: Record<string, unknown>;
  dependsOn?: string[];
}

/** 执行日志条目 */
export interface ExecutionLog {
  task: string;
  agent: string;
  status: "success" | "failure";
  duration: number;
  output?: string;
}

/** 编排结果 */
export interface OrchestratorResult {
  results: Map<string, string>;
  stats: { total: number; passed: number; failed: number };
  log: ExecutionLog[];
}

/** Agent Pool 配置 */
export interface AgentPoolConfig {
  roles: AgentRole[];
  defaultRetry?: RetryConfig;
}

/** 代码工作流配置 */
export interface CodeWorkflowConfig {
  pool: AgentPoolConfig;
  maxFixLoops?: number;
}

// ── Agent Pool ─────────────────────────────────────────

export class AgentPool {
  private roles: Map<string, AgentRole> = new Map();

  constructor(config: AgentPoolConfig) {
    for (const role of config.roles) {
      this.roles.set(role.id, role);
    }
  }

  getRole(id: string): AgentRole | undefined {
    return this.roles.get(id);
  }

  listRoles(): AgentRole[] {
    return [...this.roles.values()];
  }

  /** 根据任务类型找到最合适的 Agent */
  findBestAgent(taskType: string): AgentRole | undefined {
    // 精确匹配优先
    for (const role of this.roles.values()) {
      if (role.capabilities.includes(taskType)) return role;
    }
    // 通配符兜底
    for (const role of this.roles.values()) {
      if (role.capabilities.includes("*")) return role;
    }
    return undefined;
  }

  /** 执行单个任务 */
  async execute(roleId: string, task: string): Promise<string> {
    const role = this.roles.get(roleId);
    if (!role) throw new Error(`Unknown agent role: ${roleId}`);
    return role.config.executor(task);
  }

  /** 为角色创建 LangGraph 节点函数 */
  createNode(roleId: string): (state: AgentState) => Promise<AgentState> {
    const role = this.roles.get(roleId);
    if (!role) throw new Error(`Unknown agent role: ${roleId}`);

    let node = createOpenClawNode(role.config);

    // 包装重试
    const retry = role.config.retry;
    if (retry) {
      node = withRetry(node, retry);
    }

    return node;
  }

  /** 按类型路由并执行 */
  async routeAndExecute(taskType: string, task: string): Promise<{ agent: string; result: string }> {
    const agent = this.findBestAgent(taskType);
    if (!agent) throw new Error(`No agent available for task type: ${taskType}`);
    const result = await agent.config.executor(task);
    return { agent: agent.id, result };
  }
}

// ── Orchestrator ───────────────────────────────────────

/**
 * 简单编排器：按依赖顺序执行任务列表
 */
export class Orchestrator {
  constructor(private pool: AgentPool) {}

  async run(tasks: Task[]): Promise<OrchestratorResult> {
    const results = new Map<string, string>();
    const log: ExecutionLog[] = [];
    let passed = 0;
    let failed = 0;

    // 拓扑排序：先执行无依赖的，再执行有依赖的
    const completed = new Set<string>();
    const remaining = [...tasks];

    while (remaining.length > 0) {
      const ready = remaining.filter(t =>
        !t.dependsOn || t.dependsOn.every(d => completed.has(d))
      );

      if (ready.length === 0) {
        // 循环依赖，全部标记失败
        for (const t of remaining) {
          log.push({ task: t.id, agent: "none", status: "failure", duration: 0 });
          failed++;
        }
        break;
      }

      // 并行执行所有就绪任务
      const promises = ready.map(async (task) => {
        const start = Date.now();
        try {
          const { agent, result } = await this.pool.routeAndExecute(task.type, task.description);
          const duration = Date.now() - start;
          results.set(task.id, result);
          log.push({ task: task.id, agent, status: "success", duration, output: result });
          passed++;
          return { id: task.id, ok: true as const };
        } catch (err) {
          const duration = Date.now() - start;
          const msg = err instanceof Error ? err.message : String(err);
          log.push({ task: task.id, agent: "unknown", status: "failure", duration, output: msg });
          failed++;
          return { id: task.id, ok: false as const };
        }
      });

      const outcomes = await Promise.all(promises);
      for (const o of outcomes) {
        completed.add(o.id);
        // 从 remaining 中移除
        const idx = remaining.findIndex(t => t.id === o.id);
        if (idx >= 0) remaining.splice(idx, 1);
      }
    }

    return { results, stats: { total: tasks.length, passed, failed }, log };
  }
}

// ── Code Workflow ──────────────────────────────────────

/**
 * 创建标准编码工作流配置
 * 包含 4 个角色：analyzer → coder → tester → reviewer
 */
export function createCodeWorkflow(config: CodeWorkflowConfig) {
  const pool = new AgentPool(config.pool);
  const maxLoops = config.maxFixLoops ?? 3;

  return { pool, maxLoops };
}
