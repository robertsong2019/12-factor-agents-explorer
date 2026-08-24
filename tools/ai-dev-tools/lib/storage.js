import fs from 'fs-extra';
import path from 'path';
import Conf from 'conf';

export class DataStorage {
  constructor() {
    this.dataPath = process.env.AID_DATA_PATH || 
      path.join(process.env.HOME || '~', '.ai-dev-tools');
    this.config = new Conf({
      projectName: 'ai-dev-tools',
      defaults: {
        dataPath: this.dataPath,
        prompts: [],
        sessions: [],
        templates: [],
        settings: {
          defaultModel: 'gpt-4',
          outputFormat: 'text',
          autoSave: true
        }
      }
    });
    
    this._dirsReady = this.ensureDirectories();
  }

  async ensureDirectories() {
    const dirs = [
      'prompts',
      'sessions',
      'templates',
      'logs',
      'exports'
    ];

    for (const dir of dirs) {
      await fs.ensureDir(path.join(this.dataPath, dir));
    }
  }

  // Prompts
  async savePrompt(prompt) {
    await this._dirsReady;
    const prompts = this.config.get('prompts') || [];
    const newPrompt = {
      id: Date.now().toString(),
      ...prompt,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      usageCount: 0
    };
    prompts.push(newPrompt);
    this.config.set('prompts', prompts);
    
    // Also save to file
    const filename = `${newPrompt.id}-${prompt.name.replace(/[\s/\\]+/g, '-')}.json`;
    await fs.writeJson(
      path.join(this.dataPath, 'prompts', filename),
      newPrompt,
      { spaces: 2 }
    );
    
    return newPrompt;
  }

  getPrompts(filter = {}) {
    let prompts = this.config.get('prompts') || [];
    
    if (filter.category) {
      prompts = prompts.filter(p => p.category === filter.category);
    }
    if (filter.tags) {
      const tags = filter.tags.split(',').map(t => t.trim().toLowerCase());
      prompts = prompts.filter(p => 
        p.tags && p.tags.some(t => tags.includes(t.toLowerCase()))
      );
    }
    if (filter.query) {
      const query = filter.query.toLowerCase();
      prompts = prompts.filter(p => 
        p.name.toLowerCase().includes(query) ||
        p.description?.toLowerCase().includes(query) ||
        p.content.toLowerCase().includes(query)
      );
    }
    
    return prompts;
  }

  async deletePrompt(id) {
    const prompts = this.config.get('prompts') || [];
    const target = prompts.find(p => p.id === id);
    if (!target) {
      throw new Error(`Prompt not found: ${id}`);
    }
    this.config.set('prompts', prompts.filter(p => p.id !== id));
    
    // Remove the file copy if present
    const filename = `${target.id}-${String(target.name || '').replace(/[\s/\\]+/g, '-')}.json`;
    try {
      await fs.remove(path.join(this.dataPath, 'prompts', filename));
    } catch {
      // File copy already gone — config is the source of truth
    }
    return target;
  }

  async updatePrompt(id, updates) {
    const prompts = this.config.get('prompts') || [];
    const index = prompts.findIndex(p => p.id === id);
    
    if (index === -1) {
      throw new Error(`Prompt not found: ${id}`);
    }
    
    prompts[index] = {
      ...prompts[index],
      ...updates,
      updatedAt: new Date().toISOString()
    };
    
    this.config.set('prompts', prompts);
    return prompts[index];
  }

  // Sessions
  async saveSession(session) {
    await this._dirsReady;
    const sessions = this.config.get('sessions') || [];
    const newSession = {
      id: Date.now().toString(),
      ...session,
      startTime: new Date().toISOString(),
      endTime: null,
      status: 'active'
    };
    sessions.push(newSession);
    this.config.set('sessions', sessions);
    
    const filename = `${newSession.id}-${session.name.replace(/[\s/\\]+/g, '-')}.json`;
    await fs.writeJson(
      path.join(this.dataPath, 'sessions', filename),
      newSession,
      { spaces: 2 }
    );
    
    return newSession;
  }

  async updateSession(id, updates) {
    const sessions = this.config.get('sessions') || [];
    const index = sessions.findIndex(s => s.id === id);
    
    if (index === -1) {
      throw new Error(`Session not found: ${id}`);
    }
    
    sessions[index] = {
      ...sessions[index],
      ...updates,
      updatedAt: new Date().toISOString()
    };
    
    if (updates.status === 'completed') {
      sessions[index].endTime = new Date().toISOString();
    }
    
    this.config.set('sessions', sessions);
    return sessions[index];
  }

  getSessions(filter = {}) {
    let sessions = this.config.get('sessions') || [];
    
    if (filter.status) {
      sessions = sessions.filter(s => s.status === filter.status);
    }
    if (filter.model) {
      sessions = sessions.filter(s => s.model === filter.model);
    }
    if (filter.startDate) {
      const start = new Date(filter.startDate);
      sessions = sessions.filter(s => new Date(s.startTime) >= start);
    }
    
    return sessions;
  }

  // Statistics
  getStats() {
    const prompts = this.config.get('prompts') || [];
    const sessions = this.config.get('sessions') || [];
    
    const activeSessions = sessions.filter(s => s.status === 'active');
    const completedSessions = sessions.filter(s => s.status === 'completed');
    
    const totalTokens = sessions.reduce((sum, s) => sum + (s.tokens || 0), 0);
    const totalDuration = sessions.reduce((sum, s) => sum + (s.duration || 0), 0);
    
    const promptsByCategory = prompts.reduce((acc, p) => {
      acc[p.category] = (acc[p.category] || 0) + 1;
      return acc;
    }, {});
    
    const modelUsage = sessions.reduce((acc, s) => {
      if (s.model) {
        acc[s.model] = (acc[s.model] || 0) + 1;
      }
      return acc;
    }, {});
    
    return {
      prompts: {
        total: prompts.length,
        byCategory: promptsByCategory
      },
      sessions: {
        total: sessions.length,
        active: activeSessions.length,
        completed: completedSessions.length,
        totalTokens,
        totalDuration,
        modelUsage
      }
    };
  }

  // Settings
  getSetting(key) {
    const settings = this.config.get('settings') || {};
    return key ? settings[key] : settings;
  }

  setSetting(key, value) {
    const settings = this.config.get('settings') || {};
    settings[key] = value;
    this.config.set('settings', settings);
    return settings;
  }

  // Export/Import
  async exportData(type, outputPath) {
    await this._dirsReady;
    const data = {
      prompts: this.config.get('prompts') || [],
      sessions: this.config.get('sessions') || [],
      templates: this.config.get('templates') || [],
      settings: this.config.get('settings') || {},
      exportedAt: new Date().toISOString()
    };
    
    const content = type === 'json' 
      ? JSON.stringify(data, null, 2)
      : this.toMarkdown(data);
    
    await fs.writeFile(outputPath, content, 'utf-8');
    return outputPath;
  }

  toMarkdown(data) {
    let md = '# AI Dev Tools Export\n\n';
    md += `导出时间: ${data.exportedAt}\n\n`;
    
    md += '## 提示词\n\n';
    data.prompts.forEach(p => {
      md += `### ${p.name}\n`;
      md += `- 分类: ${p.category || '未分类'}\n`;
      md += `- 标签: ${(p.tags || []).join(', ')}\n`;
      md += `- 使用次数: ${p.usageCount}\n\n`;
      md += '```\n' + p.content + '\n```\n\n';
    });
    
    md += '## 会话统计\n\n';
    md += `- 总会话数: ${data.sessions.length}\n`;
    md += `- 总 Token: ${data.sessions.reduce((s, x) => s + (x.tokens || 0), 0)}\n`;
    
    return md;
  }
}

export const storage = new DataStorage();
