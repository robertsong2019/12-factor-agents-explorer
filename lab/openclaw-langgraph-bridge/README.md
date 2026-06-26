# openclaw-langgraph-bridge

Bridge [OpenClaw](https://github.com/nicepkg/openclaw) agent execution to [LangGraph.js](https://github.com/langchain-ai/langgraphjs) workflow nodes.

## Install

```bash
npm install openclaw-langgraph-bridge @langchain/langgraph zod
```

## Usage

```ts
import { createOpenClawNode, sequentialRouter } from "openclaw-langgraph-bridge";
import { OpenClawClient } from "openclaw-langgraph-bridge";
import { StateGraph, StateSchema, ReducedValue, MessagesValue, START, END } from "@langchain/langgraph";
import { z } from "zod";

// 1. Define state
const State = new StateSchema({
  messages: MessagesValue,
  task: z.string(),
  researcherResult: z.string().optional(),
  analystResult: z.string().optional(),
  writerResult: z.string().optional(),
  completedSteps: new ReducedValue(
    z.array(z.string()).default(() => []),
    { inputSchema: z.string(), reducer: (c, n) => [...c, n] }
  ),
});

// 2. Create nodes
const researcher = createOpenClawNode({
  name: "researcher",
  systemPrompt: "Research: {input}",
  executor: async (task) => `Research results for: ${task}`,
});

const analyst = createOpenClawNode({
  name: "analyst",
  systemPrompt: "Analyze: {input}",
  executor: async (task) => `Analysis of: ${task}`,
});

// 3. Build workflow
const roles = ["researcher", "analyst", "writer"];
const router = sequentialRouter(roles);

const graph = new StateGraph(State)
  .addNode("researcher", researcher)
  .addNode("analyst", analyst)
  .addNode("writer", writer)
  .addConditionalEdges(START, router, [...roles, END])
  .addConditionalEdges("researcher", router, [...roles, END])
  .addConditionalEdges("analyst", router, [...roles, END])
  .addEdge("writer", END)
  .compile();

// 4. Run
const result = await graph.invoke(
  { messages: [{ role: "user", content: "AI trends 2026" }], task: "AI trends 2026" },
  { configurable: { thread_id: crypto.randomUUID() } }
);
```

## OpenClaw Gateway Integration

```ts
const client = new OpenClawClient({ baseUrl: "http://localhost:3000" });

const realResearcher = createOpenClawNode({
  name: "researcher",
  systemPrompt: "Research: {input}",
  executor: client.executor("You are a research assistant"),
});
```

## API

### `createOpenClawNode(config)`
Creates a LangGraph.js node function from an OpenClaw-style agent config.

### `OpenClawClient`
HTTP client for OpenClaw Gateway. Methods: `spawn()`, `executor()`.

### `sequentialRouter(steps)`
Returns a router function that visits steps in order, skipping completed ones.

### `conditionalRouter(field, mapping, fallback)`
Routes based on a state field value.

### `Supervisor` class
Dynamic agent management with health tracking, circuit breaker, and strategies (round-robin / least-busy / weighted).

```ts
const sup = new Supervisor({ strategy: "round-robin", maxFailures: 3 });
sup.register({ id: "researcher", role: "researcher", systemPrompt: "...", executor: async (t) => "..." });

// Select next agent
const agent = sup.selectAgent();

// Record outcomes
sup.recordSuccess("researcher", 150);
sup.recordFailure("researcher", 500);

// Per-agent metrics (latency percentiles, throughput, error rate)
sup.getMetrics("researcher");
// { totalRequests: 42, successCount: 40, failureCount: 2, successRate: 0.95,
//   errorRate: 0.05, avgLatency: 152, p50Latency: 130, p95Latency: 280, p99Latency: 450, throughputPerMin: 5 }

// Pool-wide aggregate metrics
sup.getPoolMetrics();
// { totalRequests: 120, totalErrors: 5, overallErrorRate: 0.04, avgLatency: 140,
//   p50Latency: 120, p95Latency: 250, p99Latency: 400, activeAgents: 3, circuitOpenAgents: 0, throughputPerMin: 15 }

// State management
sup.saveState();    // snapshot for persistence
sup.loadState(s);   // restore
sup.toPool();       // convert to AgentPool
```

### LLM Smart Routing (Cycle 170)

Beyond strategy-based routing (round-robin / least-busy / weighted), the Supervisor supports **LLM-based smart routing** for intelligent agent selection.

#### `setLLMScorer(scorer: LLMScorer): this`

Register an async scoring function for LLM-based agent selection. The scorer receives the task description, agent role, and agent health, returning a 0..1 score.

```ts
import type { LLMScorer } from "openclaw-langgraph-bridge";

const scorer: LLMScorer = async (task, agent, health) => {
  // Call your LLM here to score agent-task fit
  const response = await llm.chat({
    messages: [{ role: "user", content: `Rate 0-1 how well agent "${agent.role}" handles: ${task}` }],
  });
  return parseFloat(response);
};

sup.setLLMScorer(scorer);
```

#### `clearLLMScorer(): void`

Remove the LLM scorer, reverting to strategy-based selection.

#### `selectAgentSmart(task: string, capability?: string): Promise<AgentRole | undefined>`

Select the best agent using the registered LLM scorer. Falls back to `selectAgent()` if no scorer is set.

- Filters unhealthy agents first (circuit breaker open = excluded)
- Optionally filters by capability
- Scores each candidate via the LLM scorer (0..1 clamped)
- **Error handling:** scorer exceptions result in score 0 (graceful degradation)
- **Tie-breaking:** equal scores broken by fewer consecutive failures

#### `executeSmart(task: string, opts?: { capability?: string }): Promise<{ agentId, result, smartRouted }>`

Execute a task using LLM-based smart routing. Returns the result with a `smartRouted` flag indicating whether LLM routing was used.

```ts
const result = await sup.executeSmart("Analyze Q3 revenue data", { capability: "analysis" });
// { agentId: "analyst", result: "...", smartRouted: true }
```

**Key design decisions:**
- Scores clamped to [0, 1] for predictable comparison
- Scorer errors don't crash the pipeline (score 0 fallback)
- `saveState()` persists `llmScorer` presence flag for observability

## License

MIT
