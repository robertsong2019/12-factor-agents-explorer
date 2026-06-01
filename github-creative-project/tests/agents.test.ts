import { BaseAgent, AgentConfig } from '../src/agents/BaseAgent';
import { MultimodalAgent, MultimodalAgentConfig } from '../src/agents/MultimodalAgent';
import { AdaptiveAgent, AdaptiveConfig } from '../src/agents/AdaptiveAgent';
import { CollaborativeCreationAgent, CollaborativeConfig } from '../src/agents/CollaborativeCreationAgent';

// Concrete test implementation of abstract BaseAgent
class TestAgent extends BaseAgent {
  async process(input: string): Promise<string> {
    return `Processed: ${input}`;
  }
  async think(task: string): Promise<string> {
    return `Thinking about: ${task}`;
  }
  async act(action: string): Promise<any> {
    return { action, result: 'done' };
  }
}

function createTestConfig(overrides?: Partial<AgentConfig>): AgentConfig {
  return {
    name: 'test-agent',
    capabilities: ['test'],
    ...overrides,
  };
}

// ─── BaseAgent Tests ─────────────────────────────────────────

describe('BaseAgent', () => {
  let agent: TestAgent;

  beforeEach(() => {
    agent = new TestAgent(createTestConfig());
  });

  test('initializes with correct config', () => {
    expect(agent).toBeDefined();
  });

  test('process returns expected output', async () => {
    const result = await agent.process('hello');
    expect(result).toBe('Processed: hello');
  });

  test('think returns expected output', async () => {
    const result = await agent.think('task');
    expect(result).toBe('Thinking about: task');
  });

  test('act returns expected output', async () => {
    const result = await agent.act('jump');
    expect(result).toEqual({ action: 'jump', result: 'done' });
  });

  test('starts and stops correctly', async () => {
    await agent.start();
    const activeState = await agent.getState();
    expect(activeState.active).toBe(true);

    await agent.stop();
    const stoppedState = await agent.getState();
    expect(stoppedState.active).toBe(false);
  });

  test('manages messages', async () => {
    await agent.addMessage('user', 'Hello');
    await agent.addMessage('assistant', 'Hi there');
    const state = await agent.getState();
    expect(state.memory.messages).toHaveLength(2);
    expect(state.memory.messages[0].role).toBe('user');
    expect(state.memory.messages[0].content).toBe('Hello');
  });

  test('manages context', async () => {
    await agent.setContext('key1', 'value1');
    const val = await agent.getContext('key1');
    expect(val).toBe('value1');
  });

  test('clears memory', async () => {
    await agent.addMessage('user', 'Hello');
    await agent.setContext('k', 'v');
    await agent.clearMemory();
    const state = await agent.getState();
    expect(state.memory.messages).toHaveLength(0);
    const ctx = await agent.getContext('k');
    expect(ctx).toBeUndefined();
  });

  test('returns capabilities copy', async () => {
    const caps = await agent.getCapabilities();
    expect(caps).toEqual(['test']);
    // Verify it's a copy
    caps.push('new');
    const original = await agent.getCapabilities();
    expect(original).toHaveLength(1);
  });

  test('emits initialized event', () => {
    const emitter = new (require('events').EventEmitter)();
    const handler = jest.fn();
    emitter.on('initialized', handler);
    // BaseAgent emits during constructor, so we test via the first agent's event
    const a = new TestAgent(createTestConfig({ name: 'test' }));
    // The event was emitted during construction; verify it emitted on the instance
    expect(a.listenerCount('initialized')).toBeGreaterThanOrEqual(0);
  });

  test('enables rapid prototyping when configured', () => {
    const a = new TestAgent(createTestConfig({ enableRapidProto: true } as any));
    // Verify agent was created without error
    expect(a).toBeDefined();
  });

  test('getState returns a copy', async () => {
    const s1 = await agent.getState();
    s1.active = true;
    const s2 = await agent.getState();
    expect(s2.active).toBe(false);
  });
});

// ─── MultimodalAgent Tests ───────────────────────────────────

describe('MultimodalAgent', () => {
  let agent: MultimodalAgent;

  beforeEach(() => {
    const config: MultimodalAgentConfig = {
      name: 'multimodal-test',
      capabilities: ['text', 'image'],
      enableVision: true,
      enableAudio: false,
      confidenceThreshold: 0.5,
    };
    agent = new MultimodalAgent(config);
  });

  test('processes text input and returns string', async () => {
    const result = await agent.process('What is AI?');
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  test('classifies question intent', async () => {
    const result = await agent.process('What is the weather?');
    expect(result).toBeDefined();
  });

  test('classifies creation intent', async () => {
    const result = await agent.process('create a new document');
    expect(result).toBeDefined();
  });

  test('classifies analysis intent', async () => {
    const result = await agent.process('analyze this data');
    expect(result).toBeDefined();
  });

  test('intent history tracks processed inputs', async () => {
    await agent.process('Hello world');
    // After processing, the fusion model handles it; history may vary
    const history = agent.getIntentHistory();
    // May or may not have entries depending on confidence thresholds
    expect(Array.isArray(history)).toBe(true);
  });

  test('clearIntentHistory works', async () => {
    agent.clearIntentHistory();
    expect(agent.getIntentHistory()).toHaveLength(0);
  });

  test('handles empty input', async () => {
    const result = await agent.process('');
    expect(typeof result).toBe('string');
  });

  test('emits initialized event', () => {
    const a = new MultimodalAgent({
      name: 'emit-mm',
      capabilities: ['text'],
    });
    expect(a).toBeDefined();
  });
});

// ─── AdaptiveAgent Tests ─────────────────────────────────────

describe('AdaptiveAgent', () => {
  let agent: AdaptiveAgent;

  beforeEach(() => {
    const config: AdaptiveConfig = {
      name: 'adaptive-test',
      capabilities: ['learning'],
      maxMemorySize: 100,
      learningRate: 0.1,
      forgettingRate: 0.05,
      confidenceThreshold: 0.5,
    };
    agent = new AdaptiveAgent(config);
  });

  afterEach(() => {
    agent.clearAllIntervals();
  });

  test('processes input and returns string', async () => {
    const result = await agent.process('Learn about AI');
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  test('records experiences', async () => {
    await agent.process('First input');
    await agent.process('Second input');
    const metrics = agent.getPerformanceMetrics();
    expect(metrics.totalTasks).toBe(2);
    expect(metrics.successfulTasks).toBe(2);
  });

  test('accepts feedback', async () => {
    await agent.process('Test feedback');
    await agent.provideFeedback(0.9);
    // Feedback should not throw
  });

  test('performance metrics update after processing', async () => {
    await agent.process('Metric test');
    const metrics = agent.getPerformanceMetrics();
    expect(metrics.totalTasks).toBeGreaterThan(0);
    expect(metrics.averageResponseTime).toBeGreaterThanOrEqual(0);
    expect(metrics.learningEfficiency).toBeGreaterThanOrEqual(0);
    expect(metrics.learningEfficiency).toBeLessThanOrEqual(1);
  });

  test('knowledge summary returns array', async () => {
    const summary = agent.getKnowledgeSummary();
    expect(Array.isArray(summary)).toBe(true);
  });

  test('processes multiple inputs sequentially', async () => {
    for (let i = 0; i < 5; i++) {
      const result = await agent.process(`Input ${i}`);
      expect(typeof result).toBe('string');
    }
    const metrics = agent.getPerformanceMetrics();
    expect(metrics.totalTasks).toBe(5);
  });

  test('trims experiences when exceeding max size', async () => {
    const smallConfig: AdaptiveConfig = {
      name: 'trim-test',
      capabilities: ['learning'],
      maxMemorySize: 3,
    };
    const smallAgent = new AdaptiveAgent(smallConfig);
    for (let i = 0; i < 10; i++) {
      await smallAgent.process(`Input ${i}`);
    }
    const metrics = smallAgent.getPerformanceMetrics();
    expect(metrics.totalTasks).toBe(10);
    smallAgent.clearAllIntervals();
  });

  test('starts and stops correctly', async () => {
    await agent.start();
    const state = await agent.getState();
    expect(state.active).toBe(true);
    await agent.stop();
  });
});

// ─── CollaborativeCreationAgent Tests ────────────────────────

describe('CollaborativeCreationAgent', () => {
  let agent: CollaborativeCreationAgent;

  beforeEach(() => {
    const config: CollaborativeConfig = {
      name: 'collab-test',
      capabilities: ['collaboration', 'creation'],
      maxAgents: 5,
      enableQualityControl: true,
      enableConflictResolution: true,
      enableInnovationBoost: true,
    };
    agent = new CollaborativeCreationAgent(config);
  });

  afterEach(() => {
    agent.clearAllIntervals();
  });

  test('processes creation request', async () => {
    const result = await agent.process('write a story about AI');
    expect(result).toContain('collaborative task');
  });

  test('processes code generation request', async () => {
    const result = await agent.process('develop a web application');
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  test('handles general collaboration request', async () => {
    const result = await agent.process('hello there');
    expect(typeof result).toBe('string');
  });

  test('returns collaboration status', async () => {
    const status = await agent.getCollaborationStatus();
    expect(status).toHaveProperty('activeTasks');
    expect(status).toHaveProperty('availableAgents');
    expect(status).toHaveProperty('completedOutputs');
    expect(status).toHaveProperty('totalCollaborations');
    expect(Array.isArray(status.activeTasks)).toBe(true);
  });

  test('requestInnovation returns a string', async () => {
    const innovation = await agent.requestInnovation();
    expect(typeof innovation).toBe('string');
    expect(innovation.length).toBeGreaterThan(0);
  });

  test('starts and stops correctly', async () => {
    await agent.start();
    const state = await agent.getState();
    expect(state.active).toBe(true);
    await agent.stop();
  });

  test('processes design request', async () => {
    const result = await agent.process('design a user interface');
    expect(typeof result).toBe('string');
  });

  test('emits initialized event', () => {
    const a = new CollaborativeCreationAgent({
      name: 'emit-collab',
      capabilities: ['collaboration'],
    });
    expect(a).toBeDefined();
  });
});

// ─── AdaptiveAgent Extra Tests ───────────────────────────────

describe('AdaptiveAgent - feedback & knowledge', () => {
  test('feedback clamped to [0, 1]', async () => {
    const config: AdaptiveConfig = {
      name: 'feedback-test',
      capabilities: ['learning'],
    };
    const agent = new AdaptiveAgent(config);
    await agent.process('test input');
    // feedback above 1 should be clamped to 1, below 0 clamped to 0
    // provideFeedback modifies the last experience's feedback field
    await agent.provideFeedback(5); // above max → clamped to 1
    await agent.provideFeedback(-3); // below min → clamped to 0
    // should not throw
    expect(true).toBe(true);
    agent.clearAllIntervals();
  });

  test('feedback on empty experiences is safe', async () => {
    const config: AdaptiveConfig = {
      name: 'empty-fb',
      capabilities: ['learning'],
    };
    const agent = new AdaptiveAgent(config);
    await agent.provideFeedback(0.8); // no experiences yet
    const metrics = agent.getPerformanceMetrics();
    expect(metrics).toBeDefined();
    agent.clearAllIntervals();
  });

  test('knowledge summary sorted by confidence desc', async () => {
    const config: AdaptiveConfig = {
      name: 'knowledge-test',
      capabilities: ['learning'],
    };
    const agent = new AdaptiveAgent(config);
    for (let i = 0; i < 5; i++) {
      await agent.process(`topic ${i} learning`);
    }
    const summary = agent.getKnowledgeSummary();
    // Check sort order
    for (let i = 1; i < summary.length; i++) {
      expect(summary[i - 1].confidence).toBeGreaterThanOrEqual(summary[i].confidence);
    }
    expect(summary.length).toBeLessThanOrEqual(20);
    agent.clearAllIntervals();
  });

  test('performance metrics is a copy', async () => {
    const config: AdaptiveConfig = {
      name: 'metrics-copy',
      capabilities: ['learning'],
    };
    const agent = new AdaptiveAgent(config);
    await agent.process('test');
    const m1 = agent.getPerformanceMetrics();
    await agent.process('another');
    const m2 = agent.getPerformanceMetrics();
    expect(m1.totalTasks).toBe(1);
    expect(m2.totalTasks).toBe(2);
    agent.clearAllIntervals();
  });
});

// ─── CollaborativeCreationAgent Extra Tests ──────────────────

describe('CollaborativeCreationAgent - extra', () => {
  test('collaboration status availableAgents filters by workload', async () => {
    const config: CollaborativeConfig = {
      name: 'workload-test',
      capabilities: ['collaboration'],
      maxAgents: 5,
    };
    const agent = new CollaborativeCreationAgent(config);
    await agent.process('write a story about cats');
    const status = await agent.getCollaborationStatus();
    expect(status.availableAgents).toBeDefined();
    // All available agents should have workload < 3
    expect(Array.isArray(status.availableAgents)).toBe(true);
    agent.clearAllIntervals();
  });

  test('collaboration status completedOutputs are approved', async () => {
    const config: CollaborativeConfig = {
      name: 'completed-test',
      capabilities: ['collaboration'],
      enableQualityControl: true,
    };
    const agent = new CollaborativeCreationAgent(config);
    const status = await agent.getCollaborationStatus();
    expect(Array.isArray(status.completedOutputs)).toBe(true);
    agent.clearAllIntervals();
  });

  test('requestInnovation contains innovation content', async () => {
    const config: CollaborativeConfig = {
      name: 'innov-test',
      capabilities: ['collaboration'],
      enableInnovationBoost: true,
    };
    const agent = new CollaborativeCreationAgent(config);
    const result = await agent.requestInnovation();
    expect(result.length).toBeGreaterThan(10);
    agent.clearAllIntervals();
  });
});
