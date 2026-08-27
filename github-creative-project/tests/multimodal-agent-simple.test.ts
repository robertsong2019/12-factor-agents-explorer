import { MultimodalAgent, MultimodalAgentConfig } from '../src/agents/MultimodalAgent';

describe('MultimodalAgent Coverage Improvement Tests', () => {
  let agent: MultimodalAgent;

  beforeEach(() => {
    const config: MultimodalAgentConfig = {
      name: 'multimodal-coverage-test',
      capabilities: ['text'],
      enableVision: false,
      enableAudio: false,
      enableText: true,
      confidenceThreshold: 0.7,
    };
    agent = new MultimodalAgent(config);
  });

  test('agent instance creation', () => {
    expect(agent).toBeDefined();
    expect(typeof agent.process).toBe('function');
  });

  test('process method exists', async () => {
    const result = await agent.process('test input');
    expect(typeof result).toBe('string');
  });

  test('process method handles error gracefully', async () => {
    const result = await agent.process('test input');
    expect(typeof result).toBe('string');
    expect(['I encountered an error processing your input. Please try again.', 'Multimodal processing error']).toContain(result);
  });
});