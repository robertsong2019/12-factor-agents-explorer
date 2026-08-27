import { MultimodalAgent, MultimodalAgentConfig, MultimodalInput, Intent } from '../src/agents/MultimodalAgent';

describe('MultimodalAgent Cycle 3 - Target 50% Coverage', () => {
  let agent: MultimodalAgent;

  beforeEach(() => {
    const config: MultimodalAgentConfig = {
      name: 'cycle3-agent',
      capabilities: ['text', 'image', 'audio'],
      enableVision: true,
      enableAudio: true,
      enableText: true,
      confidenceThreshold: 0.7,
    };
    agent = new MultimodalAgent(config);
  });

  // Cover response generation handlers (lines 211-239)
  test('handleQuestion response', async () => {
    const intent: Intent = { primary: 'question', confidence: 0.8, entities: new Map([['topic', 'AI']]), context: new Map() };
    const result = await (agent as any).handleQuestion(intent);
    expect(result).toContain('question');
  });

  test('handleCommand response', async () => {
    const intent: Intent = { primary: 'command', confidence: 0.9, entities: new Map(), context: new Map() };
    const result = await (agent as any).handleCommand(intent);
    expect(result).toContain('Command');
  });

  test('handleCreation response', async () => {
    const intent: Intent = { primary: 'creation', confidence: 0.8, entities: new Map(), context: new Map() };
    const result = await (agent as any).handleCreation(intent);
    expect(result).toContain('Creation');
  });

  test('handleAnalysis response', async () => {
    const intent: Intent = { primary: 'analysis', confidence: 0.8, entities: new Map(), context: new Map() };
    const result = await (agent as any).handleAnalysis(intent);
    expect(result).toContain('Analysis');
  });

  test('generateResponse default case', async () => {
    const intent: Intent = { primary: 'greeting', confidence: 0.9, entities: new Map(), context: new Map() };
    const result = await (agent as any).generateResponse(intent);
    expect(result).toContain('greeting');
  });

  // Cover text processing helpers (lines 253-301)
  test('extractKeywords', () => {
    const keywords = (agent as any).extractKeywords('This is a test sentence with some longer words');
    expect(Array.isArray(keywords)).toBe(true);
    expect(keywords.length).toBeGreaterThan(0);
    expect(keywords.every((w: string) => w.length > 3)).toBe(true);
  });

  test('extractKeywords empty string', () => {
    const keywords = (agent as any).extractKeywords('');
    expect(keywords).toEqual([]);
  });

  test('extractKeywords short words only', () => {
    const keywords = (agent as any).extractKeywords('a an the is it');
    expect(keywords).toEqual([]);
  });

  test('classifyIntent question', () => {
    expect((agent as any).classifyIntent('What is this?', ['this'])).toBe('question');
  });

  test('classifyIntent creation', () => {
    expect((agent as any).classifyIntent('create a document', ['document'])).toBe('creation');
    expect((agent as any).classifyIntent('make a new file', ['file'])).toBe('creation');
    expect((agent as any).classifyIntent('build this feature', ['feature'])).toBe('creation');
  });

  test('classifyIntent analysis', () => {
    expect((agent as any).classifyIntent('analyze the data', ['data'])).toBe('analysis');
    expect((agent as any).classifyIntent('examine this report', ['report'])).toBe('analysis');
  });

  test('classifyIntent help', () => {
    expect((agent as any).classifyIntent('help me please', ['help'])).toBe('request_help');
    expect((agent as any).classifyIntent('assist with this', ['assist'])).toBe('request_help');
  });

  test('classifyIntent general', () => {
    expect((agent as any).classifyIntent('hello there', ['hello'])).toBe('general');
  });

  // Cover image/audio processor methods (lines 72-87, 96-112, 121-137)
  test('detectObjects', async () => {
    const objects = await (agent as any).detectObjects(Buffer.from('fake-image'));
    expect(objects).toEqual(['object1', 'object2']);
  });

  test('classifyScene', async () => {
    const scenes = await (agent as any).classifyScene(Buffer.from('fake-image'));
    expect(scenes).toEqual(['indoor', 'office']);
  });

  test('detectEmotions', async () => {
    const emotions = await (agent as any).detectEmotions(Buffer.from('fake-image'));
    expect(emotions).toEqual(['neutral']);
  });

  test('transcribeAudio', async () => {
    const text = await (agent as any).transcribeAudio(Buffer.from('fake-audio'));
    expect(text).toBe('Transcribed text from audio');
  });

  test('analyzeSentiment', async () => {
    const sentiment = await (agent as any).analyzeSentiment('hello world');
    expect(sentiment).toBe('neutral');
  });

  test('identifySpeaker', async () => {
    const speaker = await (agent as any).identifySpeaker(Buffer.from('fake-audio'));
    expect(speaker).toBe('speaker1');
  });

  // Cover fusion methods (more thorough)
  test('fusePrimaryIntents single', () => {
    const intents: Intent[] = [{ primary: 'question', confidence: 0.8, entities: new Map(), context: new Map() }];
    expect((agent as any).fusePrimaryIntents(intents)).toBe('question');
  });

  test('fusePrimaryIntents multiple unique', () => {
    const intents: Intent[] = [
      { primary: 'question', confidence: 0.8, entities: new Map(), context: new Map() },
      { primary: 'command', confidence: 0.9, entities: new Map(), context: new Map() },
    ];
    expect((agent as any).fusePrimaryIntents(intents)).toBe('question');
  });

  test('fusePrimaryIntents duplicates', () => {
    const intents: Intent[] = [
      { primary: 'question', confidence: 0.8, entities: new Map(), context: new Map() },
      { primary: 'question', confidence: 0.7, entities: new Map(), context: new Map() },
    ];
    expect((agent as any).fusePrimaryIntents(intents)).toBe('question');
  });

  test('fusePrimaryIntents empty', () => {
    expect((agent as any).fusePrimaryIntents([])).toBe('unknown');
  });

  test('calculateConfidence normal', () => {
    const intents: Intent[] = [
      { primary: 'q', confidence: 0.6, entities: new Map(), context: new Map() },
      { primary: 'c', confidence: 0.8, entities: new Map(), context: new Map() },
    ];
    const conf = (agent as any).calculateConfidence(intents);
    expect(conf).toBeCloseTo(0.8);
  });

  test('calculateConfidence capped at 1.0', () => {
    const intents: Intent[] = [
      { primary: 'q', confidence: 0.95, entities: new Map(), context: new Map() },
      { primary: 'c', confidence: 0.95, entities: new Map(), context: new Map() },
    ];
    const conf = (agent as any).calculateConfidence(intents);
    expect(conf).toBeLessThanOrEqual(1.0);
    expect(conf).toBeGreaterThan(0);
  });

  test('fuseEntities', () => {
    const intents: Intent[] = [
      { primary: 'q', confidence: 0.8, entities: new Map([['kw', ['ai']]]), context: new Map() },
      { primary: 'c', confidence: 0.9, entities: new Map([['obj', ['car']]]), context: new Map() },
    ];
    const fused = (agent as any).fuseEntities(intents);
    expect(fused.get('kw')).toEqual([['ai']]);
    expect(fused.get('obj')).toEqual([['car']]);
  });

  test('fuseEntities merge same key', () => {
    const intents: Intent[] = [
      { primary: 'q', confidence: 0.8, entities: new Map([['kw', 'ai']]), context: new Map() },
      { primary: 'c', confidence: 0.9, entities: new Map([['kw', 'ml']]), context: new Map() },
    ];
    const fused = (agent as any).fuseEntities(intents);
    expect(fused.get('kw')).toEqual(['ai', 'ml']);
  });

  test('fuseContext', () => {
    const intents: Intent[] = [
      { primary: 'q', confidence: 0.8, entities: new Map(), context: new Map([['len', 10]]) },
      { primary: 'c', confidence: 0.9, entities: new Map(), context: new Map([['src', 'user']]) },
    ];
    const fused = (agent as any).fuseContext(intents);
    expect(fused.get('len')).toBe(10);
    expect(fused.get('src')).toBe('user');
  });

  test('fuseContext last wins', () => {
    const intents: Intent[] = [
      { primary: 'q', confidence: 0.8, entities: new Map(), context: new Map([['key', 'first']]) },
      { primary: 'c', confidence: 0.9, entities: new Map(), context: new Map([['key', 'second']]) },
    ];
    const fused = (agent as any).fuseContext(intents);
    expect(fused.get('key')).toBe('second');
  });

  // Cover think/act methods (line 170-175)
  test('think method', async () => {
    const result = await agent.think('test question?');
    expect(typeof result).toBe('string');
  });

  test('act method', async () => {
    const result = await agent.act('test input');
    expect(typeof result).toBe('string');
  });

  // Cover processMultimodal confidence threshold (line 196)
  test('processMultimodal low confidence', async () => {
    const originalFusion = (agent as any).multimodalModel.fusion;
    (agent as any).multimodalModel.fusion = {
      process: async () => ({ primary: 'test', confidence: 0.1, entities: new Map(), context: new Map() })
    };
    const result = await (agent as any).processMultimodal([{
      type: 'text', content: 'test', metadata: { timestamp: new Date(), confidence: 0.1, source: 'test' }
    }]);
    expect(result).toContain('not confident');
    (agent as any).multimodalModel.fusion = originalFusion;
  });

  // Cover getIntentHistoryForTest and classifyIntentForTest
  test('getIntentHistoryForTest', () => {
    expect((agent as any).getIntentHistoryForTest()).toEqual([]);
  });

  test('classifyIntentForTest', () => {
    expect((agent as any).classifyIntentForTest('what is this?', ['this'])).toBe('question');
  });
});
