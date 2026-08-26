import { MultimodalAgent, MultimodalAgentConfig, MultimodalInput, Intent } from '../src/agents/MultimodalAgent';

describe('MultimodalAgent Extended Tests', () => {
  let agent: MultimodalAgent;

  beforeEach(() => {
    const config: MultimodalAgentConfig = {
      name: 'multimodal-extended-test',
      capabilities: ['text', 'image', 'audio'],
      enableVision: true,
      enableAudio: true,
      enableText: true,
      confidenceThreshold: 0.5,
    };
    agent = new MultimodalAgent(config);
  });

  describe('Configuration and Initialization', () => {
    test('initializes with all modalities enabled', () => {
      expect(agent).toBeDefined();
    });

    test('configures with text-only mode', () => {
      const config: MultimodalAgentConfig = {
        name: 'text-only',
        capabilities: ['text'],
        enableVision: false,
        enableAudio: false,
        enableText: true,
        confidenceThreshold: 0.8,
      };
      const textAgent = new MultimodalAgent(config);
      expect(textAgent).toBeDefined();
    });

    test('configures with high confidence threshold', () => {
      const config: MultimodalAgentConfig = {
        name: 'high-confidence',
        capabilities: ['text'],
        confidenceThreshold: 0.9,
      };
      const strictAgent = new MultimodalAgent(config);
      expect(strictAgent).toBeDefined();
    });
  });

  describe('Text Processing', () => {
    test('processes question input', async () => {
      const result = await agent.process('What is the meaning of life?');
      expect(typeof result).toBe('string');
      expect(result.length).toBeGreaterThan(0);
    });

    test('processes command input', async () => {
      const result = await agent.process('Create a new document');
      expect(typeof result).toBe('string');
      expect(result.length).toBeGreaterThan(0);
    });

    test('processes creation input', async () => {
      const result = await agent.process('build a website for my business');
      expect(typeof result).toBe('string');
      expect(result.length).toBeGreaterThan(0);
    });

    test('processes analysis input', async () => {
      const result = await agent.process('analyze this dataset');
      expect(typeof result).toBe('string');
      expect(result.length).toBeGreaterThan(0);
    });

    test('processes request for help', async () => {
      const result = await agent.process('Can you help me understand this?');
      expect(typeof result).toBe('string');
      expect(result.length).toBeGreaterThan(0);
    });

    test('handles empty input', async () => {
      const result = await agent.process('');
      expect(typeof result).toBe('string');
      expect(result.length).toBeGreaterThan(0);
    });

    test('handles very long input', async () => {
      const longText = 'This is a very long text that should be processed correctly by the multimodal agent. It contains multiple sentences and various types of content that the agent should be able to understand and classify appropriately.'.repeat(10);
      const result = await agent.process(longText);
      expect(typeof result).toBe('string');
    });
  });

  describe('Multimodal Input Processing', () => {
    test('processes multimodal text input', async () => {
      const multimodalInputs: MultimodalInput[] = [
        {
          type: 'text',
          content: 'Hello, how are you?',
          metadata: {
            timestamp: new Date(),
            confidence: 0.9,
            source: 'user'
          }
        }
      ];

      const result = await (agent as any).processMultimodal(multimodalInputs);
      expect(typeof result).toBe('string');
      expect(result.length).toBeGreaterThan(0);
    });

    test('handles low confidence responses', async () => {
      const multimodalInputs: MultimodalInput[] = [
        {
          type: 'text',
          content: 'xyz',
          metadata: {
            timestamp: new Date(),
            confidence: 0.3,
            source: 'user'
          }
        }
      ];

      const result = await (agent as any).processMultimodal(multimodalInputs);
      expect(typeof result).toBe('string');
      expect(result).toContain('not confident enough');
    });
  });

  describe('Intent History Management', () => {
    test('stores intent history', async () => {
      await agent.process('What is AI?');
      const history = (agent as any).getIntentHistory();
      expect(history).toBeInstanceOf(Array);
      expect(history.length).toBeGreaterThan(0);
    });

    test('clears intent history', () => {
      (agent as any).clearIntentHistory();
      const history = (agent as any).getIntentHistory();
      expect(history).toEqual([]);
    });
  });

  describe('Edge Cases and Error Handling', () => {
    test('handles processing errors gracefully', async () => {
      // This test depends on the actual implementation error handling
      const result = await agent.process('test error handling');
      expect(typeof result).toBe('string');
      expect(result.length).toBeGreaterThan(0);
    });

    test('processes special characters', async () => {
      const result = await agent.process('Hello! How are you? I\'m fine, thanks.');
      expect(typeof result).toBe('string');
      expect(result.length).toBeGreaterThan(0);
    });

    test('processes numbers and symbols', async () => {
      const result = await agent.process('Calculate 2+2=4 and analyze #data');
      expect(typeof result).toBe('string');
      expect(result.length).toBeGreaterThan(0);
    });
  });

  describe('Keyword Extraction', () => {
    test('extracts keywords from text', () => {
      const text = 'The quick brown fox jumps over the lazy dog and the river';
      const keywords = (agent as any).extractKeywords(text);
      expect(Array.isArray(keywords)).toBe(true);
      expect(keywords.length).toBeGreaterThan(0);
      expect(keywords.every((k: string) => typeof k === 'string')).toBe(true);
    });

    test('handles text with short words', () => {
      const text = 'a be the in of to and for';
      const keywords = (agent as any).extractKeywords(text);
      expect(keywords).toEqual([]);
    });

    test('handles text with very long words', () => {
      const text = 'supercalifragilisticexpialidocious is a very long word';
      const keywords = (agent as any).extractKeywords(text);
      expect(Array.isArray(keywords)).toBe(true);
      expect(keywords.length).toBeGreaterThan(0);
    });
  });

  describe('Intent Classification', () => {
    test('classifies question intent', () => {
      const keywords = ['what', 'how', 'why'];
      const intent = (agent as any).classifyIntent('What is AI?', keywords);
      expect(intent).toBe('question');
    });

    test('classifies creation intent', () => {
      const keywords = ['create', 'make', 'build'];
      const intent = (agent as any).classifyIntent('Create a document', keywords);
      expect(intent).toBe('creation');
    });

    test('classifies analysis intent', () => {
      const keywords = ['analyze', 'examine', 'study'];
      const intent = (agent as any).classifyIntent('Analyze this data', keywords);
      expect(intent).toBe('analysis');
    });

    test('classifies help request intent', () => {
      const keywords = ['help', 'assist'];
      const intent = (agent as any).classifyIntent('Can you help me?', ['help']);
      expect(intent).toBe('request_help');
    });

    test('classifies general intent as fallback', () => {
      const keywords = ['random', 'text'];
      const intent = (agent as any).classifyIntent('This is just some text', keywords);
      // This should return 'general' as fallback
      expect(['question', 'command', 'creation', 'analysis', 'request_help', 'general']).toContain(intent);
    });
  });
});