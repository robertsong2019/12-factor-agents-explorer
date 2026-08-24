import { jest } from '@jest/globals';

// Mock ESM modules before importing the module under test
jest.unstable_mockModule('../lib/storage.js', () => ({
  storage: {
    getPrompts: jest.fn(),
    savePrompt: jest.fn(),
    updatePrompt: jest.fn(),
    exportData: jest.fn(),
    deletePrompt: jest.fn(),
  }
}));

jest.unstable_mockModule('inquirer', () => ({
  default: { prompt: jest.fn() }
}));

jest.unstable_mockModule('fs-extra', () => ({
  default: {
    readFile: jest.fn(),
    ensureDir: jest.fn(),
    writeJson: jest.fn(),
    remove: jest.fn(),
  }
}));

jest.unstable_mockModule('chalk', () => {
  const chain = (s) => s;
  const proxy = new Proxy(chain, { get: () => proxy });
  return { default: proxy };
});

jest.unstable_mockModule('ora', () => ({
  default: jest.fn(() => ({
    start: jest.fn().mockReturnThis(),
    succeed: jest.fn(),
    fail: jest.fn(),
    stop: jest.fn(),
  }))
}));

const { storage } = await import('../lib/storage.js');
const { default: inquirer } = await import('inquirer');
const { default: fs } = await import('fs-extra');
const { default: promptCommand } = await import('../commands/prompt.js');

describe('promptCommand', () => {
  let consoleLogSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
  });

  describe('list action', () => {
    it('should display empty message when no prompts', async () => {
      storage.getPrompts.mockReturnValue([]);

      await promptCommand('list', {});

      expect(storage.getPrompts).toHaveBeenCalled();
      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('暂无保存的提示词')
      );
    });

    it('should display prompts grouped by category', async () => {
      const prompts = [
        { id: '1', name: 'Prompt 1', category: '代码生成', tags: ['js'] },
        { id: '2', name: 'Prompt 2', category: '代码生成', tags: ['python'] },
        { id: '3', name: 'Prompt 3', category: '文档编写', tags: [] }
      ];

      storage.getPrompts.mockReturnValue(prompts);

      await promptCommand('list', {});

      expect(storage.getPrompts).toHaveBeenCalled();
      expect(consoleLogSpy).toHaveBeenCalled();
    });

    it('should display prompts with usage count', async () => {
      const prompts = [
        { id: '1', name: 'Prompt 1', category: 'test', usageCount: 10 }
      ];

      storage.getPrompts.mockReturnValue(prompts);

      await promptCommand('list', {});

      expect(consoleLogSpy).toHaveBeenCalled();
    });

    it('should pass filter options to getPrompts', async () => {
      storage.getPrompts.mockReturnValue([]);

      await promptCommand('list', { category: '代码生成', tags: 'js' });

      expect(storage.getPrompts).toHaveBeenCalledWith(
        expect.objectContaining({
          category: '代码生成',
          tags: 'js'
        })
      );
    });
  });

  describe('search action', () => {
    it('should search prompts with query option', async () => {
      const prompts = [
        { id: '1', name: 'Code Review', content: 'Review code for bugs', category: 'dev' }
      ];

      storage.getPrompts.mockReturnValue(prompts);

      await promptCommand('search', { query: 'code' });

      expect(storage.getPrompts).toHaveBeenCalledWith({ query: 'code' });
    });

    it('should prompt for query if not provided', async () => {
      inquirer.prompt.mockResolvedValue({ query: 'test query' });
      storage.getPrompts.mockReturnValue([]);

      await promptCommand('search', {});

      expect(inquirer.prompt).toHaveBeenCalled();
      expect(storage.getPrompts).toHaveBeenCalledWith({ query: 'test query' });
    });

    it('should display no results message', async () => {
      storage.getPrompts.mockReturnValue([]);

      await promptCommand('search', { query: 'nonexistent' });

      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('未找到匹配的提示词')
      );
    });

    it('should display search results', async () => {
      const prompts = [
        {
          id: '1',
          name: 'Test Prompt',
          content: 'This is a long content that should be truncated...',
          category: 'test',
          description: 'Test description'
        }
      ];

      storage.getPrompts.mockReturnValue(prompts);

      await promptCommand('search', { query: 'test' });

      expect(consoleLogSpy).toHaveBeenCalled();
    });
  });

  describe('save action', () => {
    it('should save prompt from options', async () => {
      const savedPrompt = {
        id: '123',
        name: 'Test Prompt',
        category: 'test',
        tags: ['js']
      };

      storage.savePrompt.mockResolvedValue(savedPrompt);

      inquirer.prompt.mockResolvedValue({
        name: 'Test Prompt',
        content: 'Test content',
        description: 'Test description',
        category: 'test',
        tags: 'js, node'
      });

      await promptCommand('save', {});

      expect(storage.savePrompt).toHaveBeenCalled();
    });

    it('should load content from file if provided', async () => {
      const fileContent = 'Prompt content from file';
      fs.readFile.mockResolvedValue(fileContent);

      const savedPrompt = {
        id: '123',
        name: 'test-prompt',
        content: fileContent
      };

      storage.savePrompt.mockResolvedValue(savedPrompt);

      await promptCommand('save', { file: 'test.txt' });

      expect(fs.readFile).toHaveBeenCalledWith('test.txt', 'utf-8');
      expect(storage.savePrompt).toHaveBeenCalled();
    });

    it('should handle save errors', async () => {
      const error = new Error('Save failed');
      storage.savePrompt.mockRejectedValue(error);

      inquirer.prompt.mockResolvedValue({
        name: 'Test',
        content: 'Content',
        category: 'test',
        tags: ''
      });

      await promptCommand('save', {});

      expect(storage.savePrompt).toHaveBeenCalled();
    });
  });

  describe('use action', () => {
    it('should display empty message when no prompts', async () => {
      storage.getPrompts.mockReturnValue([]);

      await promptCommand('use', {});

      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('暂无保存的提示词')
      );
    });

    it('should use prompt by name', async () => {
      const prompts = [
        { id: '1', name: 'Test Prompt', content: 'Test content', usageCount: 0 }
      ];

      storage.getPrompts.mockReturnValue(prompts);
      storage.updatePrompt.mockResolvedValue({
        ...prompts[0],
        usageCount: 1
      });

      await promptCommand('use', { name: 'Test Prompt' });

      expect(storage.updatePrompt).toHaveBeenCalledWith('1', {
        usageCount: 1
      });
      expect(consoleLogSpy).toHaveBeenCalled();
    });

    it('should prompt for selection if no name provided', async () => {
      const prompts = [
        { id: '1', name: 'Prompt 1', content: 'Content 1' }
      ];

      storage.getPrompts.mockReturnValue(prompts);
      storage.updatePrompt.mockResolvedValue(prompts[0]);

      inquirer.prompt.mockResolvedValue({
        prompt: prompts[0]
      });

      await promptCommand('use', {});

      expect(inquirer.prompt).toHaveBeenCalled();
    });

    it('should handle prompt not found', async () => {
      const prompts = [
        { id: '1', name: 'Prompt 1', content: 'Content 1' }
      ];

      storage.getPrompts.mockReturnValue(prompts);

      await promptCommand('use', { name: 'Nonexistent' });

      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('未找到提示词')
      );
    });
  });

  describe('export action', () => {
    it('should export prompts to default file', async () => {
      storage.exportData.mockResolvedValue('/default/path');

      await promptCommand('export', {});

      expect(storage.exportData).toHaveBeenCalledWith(
        'markdown',
        expect.stringContaining('prompts-export-')
      );
    });

    it('should export prompts to specified file', async () => {
      const outputPath = '/custom/path/export.md';
      storage.exportData.mockResolvedValue(outputPath);

      await promptCommand('export', { output: outputPath });

      expect(storage.exportData).toHaveBeenCalledWith('markdown', outputPath);
    });

    it('should handle export errors', async () => {
      const error = new Error('Export failed');
      storage.exportData.mockRejectedValue(error);

      await promptCommand('export', {});

      expect(storage.exportData).toHaveBeenCalled();
    });
  });

  describe('delete action', () => {
    it('should prompt for deletion if no name provided', async () => {
      const prompts = [
        { id: '1', name: 'Prompt 1', category: 'test' }
      ];

      storage.getPrompts.mockReturnValue(prompts);

      inquirer.prompt
        .mockResolvedValueOnce({ prompt: '1', confirm: false });

      await promptCommand('delete', {});

      expect(inquirer.prompt).toHaveBeenCalled();
    });

    it('should cancel deletion if not confirmed', async () => {
      const prompts = [
        { id: '1', name: 'Prompt 1', category: 'test' }
      ];

      storage.getPrompts.mockReturnValue(prompts);

      inquirer.prompt
        .mockResolvedValueOnce({ prompt: '1', confirm: false });

      await promptCommand('delete', {});

      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('已取消')
      );
    });

    it('should delete prompt when confirmed', async () => {
      const prompts = [
        { id: '1', name: 'Prompt 1', category: 'test' }
      ];

      storage.getPrompts.mockReturnValue(prompts);

      inquirer.prompt
        .mockResolvedValueOnce({ prompt: '1', confirm: true });
      storage.deletePrompt.mockResolvedValue({ id: '1', name: 'Prompt 1' });

      await promptCommand('delete', {});

      // Regression: delete used to print success WITHOUT calling storage at all
      expect(storage.deletePrompt).toHaveBeenCalledWith('1');
      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('已删除')
      );
    });
  });

  describe('default action', () => {
    it('should list prompts when no action specified', async () => {
      storage.getPrompts.mockReturnValue([]);

      await promptCommand(undefined, {});

      expect(storage.getPrompts).toHaveBeenCalled();
    });
  });
});
