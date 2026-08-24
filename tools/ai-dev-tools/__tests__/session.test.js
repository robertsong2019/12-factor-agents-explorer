import { jest } from '@jest/globals';

jest.unstable_mockModule('../lib/storage.js', () => ({
  storage: {
    getSessions: jest.fn(),
    saveSession: jest.fn(),
    updateSession: jest.fn(),
    getStats: jest.fn(),
    exportData: jest.fn(),
  }
}));

jest.unstable_mockModule('inquirer', () => ({
  default: { prompt: jest.fn() }
}));

jest.unstable_mockModule('chalk', () => ({
  default: {
    bold: (s) => s, green: (s) => s, red: (s) => s, yellow: (s) => s,
    gray: (s) => s, cyan: { bold: (s) => s }, white: (s) => s,
  }
}));

jest.unstable_mockModule('ora', () => ({
  default: () => ({ start: () => ({ succeed: jest.fn(), fail: jest.fn() }) })
}));

const { storage } = await import('../lib/storage.js');
const { default: inquirer } = await import('inquirer');
const { default: sessionCommand } = await import('../commands/session.js');

describe('session command', () => {
  let consoleLogSpy;
  let consoleErrorSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
    consoleErrorSpy.mockRestore();
  });

  describe('stop', () => {
    test('unknown session name: friendly error + exitCode 1, no crash (bugfix)', async () => {
      storage.getSessions.mockReturnValue([
        { id: '1', name: 's1', task: 't', startTime: new Date().toISOString() }
      ]);

      await sessionCommand('stop', { name: 'ghost' });

      const text = consoleLogSpy.mock.calls.flat().join('\n');
      expect(text).toContain('未找到活动会话');
      expect(process.exitCode).toBe(1);
      expect(storage.updateSession).not.toHaveBeenCalled();
      process.exitCode = 0;
    });

    test('non-interactive stop with --tokens/--duration: no prompt, duration flag is seconds (bugfix)', async () => {
      storage.getSessions.mockReturnValue([
        { id: '1', name: 's1', task: 't', startTime: new Date().toISOString() }
      ]);
      storage.updateSession.mockResolvedValue({
        id: '1', name: 's1', status: 'completed',
        startTime: new Date().toISOString(), endTime: new Date().toISOString()
      });

      await sessionCommand('stop', { name: 's1', tokens: '500', duration: '180' });

      expect(inquirer.prompt).not.toHaveBeenCalled();
      // 180s flag → 3 min → stored as 180 seconds
      expect(storage.updateSession).toHaveBeenCalledWith('1', {
        status: 'completed',
        tokens: 500,
        duration: 180,
      });
    });

    test('stop by id works too', async () => {
      storage.getSessions.mockReturnValue([
        { id: 'abc', name: 's1', task: 't', startTime: new Date().toISOString() }
      ]);
      storage.updateSession.mockResolvedValue({ id: 'abc', name: 's1' });

      await sessionCommand('stop', { name: 'abc', tokens: '1', duration: '60' });

      expect(storage.updateSession).toHaveBeenCalledWith('abc', expect.objectContaining({ status: 'completed' }));
    });
  });

  describe('log', () => {
    test('actually persists the log entry (regression: used to be a pure fake)', async () => {
      const target = { id: '1', name: 's1', task: 't', logs: [{ time: '2026-01-01', content: 'old' }] };
      storage.getSessions.mockReturnValue([target]);
      storage.updateSession.mockResolvedValue(target);
      inquirer.prompt.mockResolvedValue({ session: '1', log: 'did some work' });

      await sessionCommand('log', {});

      expect(storage.updateSession).toHaveBeenCalledWith('1', {
        logs: [
          { time: '2026-01-01', content: 'old' },
          expect.objectContaining({ content: 'did some work' }),
        ],
      });
      const text = consoleLogSpy.mock.calls.flat().join('\n');
      expect(text).toContain('日志已记录');
    });

    test('no active sessions: message, no interaction', async () => {
      storage.getSessions.mockReturnValue([]);
      await sessionCommand('log', {});
      expect(inquirer.prompt).not.toHaveBeenCalled();
      const text = consoleLogSpy.mock.calls.flat().join('\n');
      expect(text).toContain('当前没有活动会话');
    });
  });

  describe('stats (default action)', () => {
    test('renders prompt + session stats', async () => {
      storage.getStats.mockReturnValue({
        prompts: { total: 3, byCategory: { '代码生成': 2, '其他': 1 } },
        sessions: { total: 5, active: 1, completed: 4, totalTokens: 12000, totalDuration: 1800, modelUsage: { 'GPT-4': 3 } },
      });

      await sessionCommand(undefined, {});

      const text = consoleLogSpy.mock.calls.flat().join('\n');
      expect(text).toContain('总数:');
      expect(text).toContain('3');
      expect(text).toContain('GPT-4: 3 次');
    });
  });
});
