import { MultimodalAgent, MultimodalAgentConfig, MultimodalInput, Intent } from '../src/agents/MultimodalAgent';

// Mock implementations for testing
const mockTextProcessor = {
  process: async (text: string): Promise<Intent> => {
    return {
      primary: 'text_intent',
      confidence: 0.9,
      entities: new Map([['keywords', ['test']]]),
      context: new Map([['text_length', text.length]])
    };
  }
};

const mockImageProcessor = {
  process: async (imageData: Buffer): Promise<Intent> => {
    return {
      primary: 'visual_intent', 
      confidence: 0.8,
      entities: new Map([['objects', ['mock_object']]]),
      context: new Map()
    };
  }
};

const mockAudioProcessor = {
  process: async (audioData: Buffer): Promise<Intent> => {
    return {
      primary: 'audio_intent',
      confidence: 0.85,
      entities: new Map([['transcription', 'mock audio text']]),
      context: new Map()
    };
  }
};

const mockMultimodalFusion = {
  process: async (inputs: MultimodalInput[]): Promise<Intent> => {
    // Simple mock implementation that returns a combined intent
    return {
      primary: 'combined_intent',
      confidence: 0.9,
      entities: new Map([['keywords', ['combined']]]),
      context: new Map()
    };
  }
};

describe('MultimodalAgent Improved Coverage Tests', () => {
  let agent: MultimodalAgent;

  beforeEach(() => {
    const config: MultimodalAgentConfig = {
      name: 'multimodal-coverage-improved',
      capabilities: ['text', 'image', 'audio'],
      enableVision: true,
      enableAudio: true,
      enableText: true,
      confidenceThreshold: 0.7,
    };
    agent = new MultimodalAgent(config);
  });

  // Test basic functionality
  test('agent instance creation', () => {
    expect(agent).toBeDefined();
  });

  // Test intent history management
  test('intent history management', () => {
    expect(typeof agent.getIntentHistory).toBe('function');
    expect(Array.isArray(agent.getIntentHistory())).toBe(true);
    
    // Clear history
    agent.clearIntentHistory();
    expect(agent.getIntentHistory()).toEqual([]);
  });

  // Test basic text processing
  test('basic text processing', async () => {
    const result = await agent.process('Hello world');
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  // Test multimodal input processing with mocked model
  test('multimodal input processing with error handling', async () => {
    // Mock the multimodal model to avoid dependency issues
    const originalModel = (agent as any).multimodalModel;
    (agent as any).multimodalModel = mockTextProcessor;
    
    const result = await agent.process('Test input');
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
    
    // Restore original model
    (agent as any).multimodalModel = originalModel;
  });

  // Test configuration edge cases
  test('configuration edge cases', () => {
    const minimalConfig: MultimodalAgentConfig = {
      name: 'minimal',
      capabilities: [],
      enableVision: false,
      enableAudio: false,
      enableText: false,
      confidenceThreshold: 0.5,
    };
    
    const minimalAgent = new MultimodalAgent(minimalConfig);
    expect(minimalAgent).toBeDefined();
  });

  // Test multimodal input types
  test('multimodal input type validation', async () => {
    const multimodalInputs: MultimodalInput[] = [
      {
        type: 'text',
        content: 'test input',
        metadata: {
          timestamp: new Date(),
          confidence: 0.8,
          source: 'user'
        }
      }
    ];

    // Mock the multimodal fusion processor
    const originalFusion = (agent as any).multimodalModel.fusion;
    (agent as any).multimodalModel.fusion = mockMultimodalFusion;
    
    try {
      const result = await (agent as any).processMultimodal(multimodalInputs);
      expect(typeof result).toBe('string');
      expect(result.length).toBeGreaterThan(0);
    } finally {
      // Restore original model
      (agent as any).multimodalModel.fusion = originalFusion;
    }
  });

  // Test error handling for invalid inputs
  test('error handling for invalid inputs', async () => {
    const result = await agent.process('');
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  // Test capability configuration
  test('capability configuration', () => {
    const textOnlyConfig: MultimodalAgentConfig = {
      name: 'text-only',
      capabilities: ['text'],
      enableVision: false,
      enableAudio: false,
      enableText: true,
    };
    
    const textOnlyAgent = new MultimodalAgent(textOnlyConfig);
    expect(textOnlyAgent).toBeDefined();
  });

  // Test confidence threshold behavior
  test('confidence threshold behavior', async () => {
    const highThresholdConfig: MultimodalAgentConfig = {
      name: 'high-threshold',
      capabilities: ['text'],
      confidenceThreshold: 0.9,
    };
    
    const highThresholdAgent = new MultimodalAgent(highThresholdConfig);
    expect(highThresholdAgent).toBeDefined();
    
    const result = await highThresholdAgent.process('Test message');
    expect(typeof result).toBe('string');
  });
});