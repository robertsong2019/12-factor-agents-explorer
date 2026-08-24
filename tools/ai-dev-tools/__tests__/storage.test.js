import { DataStorage } from '../lib/storage.js';
import fs from 'fs-extra';
import path from 'path';
import os from 'os';

describe('DataStorage', () => {
  let storage;
  let testDir;

  beforeAll(async () => {
    // Create a temporary test directory
    testDir = path.join(os.tmpdir(), `ai-dev-tools-test-${Date.now()}`);
    process.env.AID_DATA_PATH = testDir;
    // Isolate `conf` too (XDG_CONFIG_HOME) — otherwise every test run writes
    // to the real ~/.config/ai-dev-tools/config.json
    process.env.XDG_CONFIG_HOME = path.join(testDir, 'config');
  });

  afterAll(async () => {
    // Clean up test directory
    try {
      await fs.remove(testDir);
    } catch (error) {
      // Ignore cleanup errors
    }
  });

  beforeEach(async () => {
    storage = new DataStorage();
    await storage._dirsReady;
  });

  describe('constructor', () => {
    it('should initialize with test data path', () => {
      expect(storage.dataPath).toBe(testDir);
    });

    it('should create config instance', () => {
      expect(storage.config).toBeDefined();
    });
  });

  describe('savePrompt', () => {
    it('should save a new prompt with generated ID', async () => {
      const prompt = {
        name: 'Test Prompt',
        category: 'test',
        content: 'This is a test prompt'
      };

      const result = await storage.savePrompt(prompt);
      
      expect(result.id).toBeDefined();
      expect(result.name).toBe(prompt.name);
      expect(result.createdAt).toBeDefined();
      expect(result.usageCount).toBe(0);
    });

    it('should save prompt to config', async () => {
      const prompt = {
        name: 'Config Test',
        category: 'test',
        content: 'Test content'
      };

      await storage.savePrompt(prompt);
      
      const prompts = storage.getPrompts();
      expect(prompts.length).toBeGreaterThan(0);
      expect(prompts[prompts.length - 1].name).toBe('Config Test');
    });
  });

  describe('getPrompts', () => {
    beforeEach(async () => {
      // Clear existing prompts
      storage.config.set('prompts', []);
      
      // Add test prompts
      await storage.savePrompt({ name: 'JS Prompt', category: 'coding', content: 'JavaScript code', tags: ['js', 'node'] });
      await storage.savePrompt({ name: 'Python Prompt', category: 'coding', content: 'Python code', tags: ['python'] });
      await storage.savePrompt({ name: 'Doc Prompt', category: 'docs', content: 'Write documentation', tags: ['docs'] });
    });

    it('should return all prompts when no filter', () => {
      const result = storage.getPrompts();
      expect(result.length).toBeGreaterThanOrEqual(3);
    });

    it('should filter by category', () => {
      const result = storage.getPrompts({ category: 'coding' });
      expect(result.length).toBeGreaterThanOrEqual(2);
      expect(result.every(p => p.category === 'coding')).toBe(true);
    });

    it('should filter by tags', () => {
      const result = storage.getPrompts({ tags: 'js' });
      expect(result.length).toBeGreaterThanOrEqual(1);
      expect(result.some(p => p.tags && p.tags.includes('js'))).toBe(true);
    });

    it('should filter by query', () => {
      const result = storage.getPrompts({ query: 'python' });
      expect(result.length).toBeGreaterThanOrEqual(1);
      expect(result.some(p => 
        p.name.toLowerCase().includes('python') ||
        p.content.toLowerCase().includes('python')
      )).toBe(true);
    });
  });

  describe('deletePrompt', () => {
    test('removes the prompt from config and returns it', async () => {
      const saved = await storage.savePrompt({ name: 'del-me', content: 'x' });
      const removed = await storage.deletePrompt(saved.id);
      expect(removed.id).toBe(saved.id);
      expect(storage.getPrompts().find(p => p.id === saved.id)).toBeUndefined();
    });

    test('removes the file copy as well', async () => {
      const saved = await storage.savePrompt({ name: 'del-file', content: 'y' });
      await storage.deletePrompt(saved.id);
      const fsx = await import('fs-extra');
      const file = path.join(testDir, 'prompts', `${saved.id}-del-file.json`);
      expect(await fsx.pathExists(file)).toBe(false);
    });

    test('throws for unknown id', async () => {
      await expect(storage.deletePrompt('nonexistent-id')).rejects.toThrow('Prompt not found');
    });
  });

  describe('savePrompt filename safety', () => {
    test('name with slash does not crash and sanitizes filename', async () => {
      const saved = await storage.savePrompt({ name: 'a/b c', content: 'z' });
      expect(saved.id).toBeTruthy();
      const fsx = await import('fs-extra');
      expect(await fsx.pathExists(path.join(testDir, 'prompts', `${saved.id}-a-b-c.json`))).toBe(true);
    });
  });

  describe('updatePrompt', () => {
    it('should update existing prompt', async () => {
      const prompt = await storage.savePrompt({
        name: 'Update Test',
        content: 'Original content'
      });
      
      const result = await storage.updatePrompt(prompt.id, { name: 'Updated Name' });
      
      expect(result.name).toBe('Updated Name');
      expect(result.updatedAt).toBeDefined();
    });

    it('should throw error if prompt not found', async () => {
      await expect(storage.updatePrompt('nonexistent-id', { name: 'New' }))
        .rejects.toThrow('Prompt not found');
    });
  });

  describe('saveSession', () => {
    it('should save a new session', async () => {
      const session = {
        name: 'Test Session',
        model: 'gpt-4'
      };
      
      const result = await storage.saveSession(session);
      
      expect(result.id).toBeDefined();
      expect(result.name).toBe(session.name);
      expect(result.status).toBe('active');
      expect(result.startTime).toBeDefined();
    });
  });

  describe('updateSession', () => {
    it('should update session', async () => {
      const session = await storage.saveSession({
        name: 'Session to Update',
        status: 'active'
      });
      
      const result = await storage.updateSession(session.id, { status: 'completed' });
      
      expect(result.status).toBe('completed');
      expect(result.endTime).toBeDefined();
    });

    it('should throw error if session not found', async () => {
      await expect(storage.updateSession('nonexistent-id', { status: 'completed' }))
        .rejects.toThrow('Session not found');
    });
  });

  describe('getSessions', () => {
    beforeEach(async () => {
      // Clear existing sessions
      storage.config.set('sessions', []);
      
      // Add test sessions
      await storage.saveSession({ name: 'Active Session', model: 'gpt-4', status: 'active' });
      await storage.saveSession({ name: 'Completed Session', model: 'gpt-3.5', status: 'completed' });
    });

    it('should filter sessions by status', () => {
      const result = storage.getSessions({ status: 'active' });
      expect(result.length).toBeGreaterThanOrEqual(1);
      expect(result.every(s => s.status === 'active')).toBe(true);
    });

    it('should filter sessions by model', () => {
      const result = storage.getSessions({ model: 'gpt-4' });
      expect(result.length).toBeGreaterThanOrEqual(1);
      expect(result.every(s => s.model === 'gpt-4')).toBe(true);
    });
  });

  describe('getStats', () => {
    beforeEach(async () => {
      // Clear and add test data
      storage.config.set('prompts', []);
      storage.config.set('sessions', []);
      
      await storage.savePrompt({ name: 'Prompt 1', category: 'coding' });
      await storage.savePrompt({ name: 'Prompt 2', category: 'coding' });
      await storage.savePrompt({ name: 'Prompt 3', category: 'docs' });
      
      await storage.saveSession({ name: 'Session 1', model: 'gpt-4', status: 'active', tokens: 100 });
      await storage.saveSession({ name: 'Session 2', model: 'gpt-4', status: 'completed', tokens: 200 });
    });

    it('should return correct statistics', () => {
      const stats = storage.getStats();
      
      expect(stats.prompts.total).toBeGreaterThanOrEqual(3);
      expect(stats.prompts.byCategory.coding).toBeGreaterThanOrEqual(2);
      expect(stats.sessions.total).toBeGreaterThanOrEqual(2);
      expect(stats.sessions.totalTokens).toBeGreaterThanOrEqual(300);
      expect(stats.sessions.modelUsage['gpt-4']).toBeGreaterThanOrEqual(2);
    });
  });

  describe('getSetting', () => {
    it('should get all settings when no key provided', () => {
      const result = storage.getSetting();
      expect(result).toBeDefined();
      expect(result.defaultModel).toBeDefined();
    });

    it('should get specific setting by key', () => {
      const result = storage.getSetting('defaultModel');
      expect(result).toBeDefined();
    });
  });

  describe('setSetting', () => {
    it('should update setting and return updated settings', () => {
      const result = storage.setSetting('defaultModel', 'gpt-3.5');
      
      expect(result.defaultModel).toBe('gpt-3.5');
      
      // Verify it was saved
      const saved = storage.getSetting('defaultModel');
      expect(saved).toBe('gpt-3.5');
    });
  });

  describe('exportData', () => {
    it('should export data as JSON', async () => {
      const outputPath = path.join(testDir, 'test-export.json');
      const result = await storage.exportData('json', outputPath);
      
      expect(result).toBe(outputPath);
      
      // Verify file exists
      const exists = await fs.pathExists(outputPath);
      expect(exists).toBe(true);
      
      // Verify content
      const content = await fs.readFile(outputPath, 'utf-8');
      const data = JSON.parse(content);
      expect(data.exportedAt).toBeDefined();
      expect(data.prompts).toBeDefined();
      expect(data.sessions).toBeDefined();
    });

    it('should export data as Markdown', async () => {
      const outputPath = path.join(testDir, 'test-export.md');
      const result = await storage.exportData('markdown', outputPath);
      
      expect(result).toBe(outputPath);
      
      // Verify file exists
      const exists = await fs.pathExists(outputPath);
      expect(exists).toBe(true);
      
      // Verify content
      const content = await fs.readFile(outputPath, 'utf-8');
      expect(content).toContain('# AI Dev Tools Export');
      expect(content).toContain('## 提示词');
      expect(content).toContain('## 会话统计');
    });
  });

  describe('toMarkdown', () => {
    it('should convert data to markdown format', () => {
      const data = {
        exportedAt: '2024-01-01T00:00:00Z',
        prompts: [
          { name: 'Test', category: 'test', tags: ['js'], usageCount: 5, content: 'Test content' }
        ],
        sessions: [
          { tokens: 100 }
        ]
      };
      
      const markdown = storage.toMarkdown(data);
      
      expect(markdown).toContain('# AI Dev Tools Export');
      expect(markdown).toContain('## 提示词');
      expect(markdown).toContain('## 会话统计');
      expect(markdown).toContain('Test');
    });
  });
});
