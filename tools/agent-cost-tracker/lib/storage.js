/**
 * 存储模块 - 管理成本数据和配置
 */

import Conf from 'conf';
import { join } from 'path';
import { homedir } from 'os';
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'fs';

// 配置存储
const config = new Conf({
  projectName: 'agent-cost-tracker',
  cwd: join(homedir(), '.config'),
  defaults: {
    logs: [],
    models: getDefaultModels(),
    budget: {
      enabled: false,
      amount: 0,
      period: 'month',
      warningThreshold: 80
    }
  }
});

// 默认模型价格 (每 1M tokens, USD)
function getDefaultModels() {
  return {
    'gpt-4-turbo': { inputPrice: 10, outputPrice: 30, currency: 'USD' },
    'gpt-4': { inputPrice: 30, outputPrice: 60, currency: 'USD' },
    'gpt-3.5-turbo': { inputPrice: 0.5, outputPrice: 1.5, currency: 'USD' },
    'claude-3-opus': { inputPrice: 15, outputPrice: 75, currency: 'USD' },
    'claude-3-sonnet': { inputPrice: 3, outputPrice: 15, currency: 'USD' },
    'claude-3-haiku': { inputPrice: 0.25, outputPrice: 1.25, currency: 'USD' },
    'glm-4': { inputPrice: 0.5, outputPrice: 2, currency: 'CNY' },
    'glm-5': { inputPrice: 1.5, outputPrice: 6, currency: 'CNY' }
  };
}

// 日志操作
export function addLog(logData) {
  const logs = config.get('logs') || [];
  const log = {
    id: Date.now().toString(36) + Math.random().toString(36).substr(2),
    timestamp: new Date().toISOString(),
    ...logData
  };
  logs.push(log);
  config.set('logs', logs);
  return log;
}

export function getLogs(filters = {}) {
  let logs = config.get('logs') || [];

  // 时间过滤
  if (filters.period) {
    const now = new Date();
    const periodStart = getPeriodStart(filters.period, now);
    logs = logs.filter(log => new Date(log.timestamp) >= periodStart);
  }

  // 模型过滤
  if (filters.model) {
    logs = logs.filter(log => log.model === filters.model);
  }

  // 会话过滤
  if (filters.session) {
    logs = logs.filter(log => log.session === filters.session);
  }

  // 日期范围过滤
  if (filters.before) {
    logs = logs.filter(log => new Date(log.timestamp) < new Date(filters.before));
  }

  return logs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
}

export function deleteLogs(logIds) {
  const logs = config.get('logs') || [];
  const filtered = logs.filter(log => !logIds.includes(log.id));
  config.set('logs', filtered);
  return filtered.length;
}

export function clearLogs(beforeDate = null) {
  if (beforeDate) {
    const logs = getLogs({ before: beforeDate });
    const ids = logs.map(log => log.id);
    deleteLogs(ids);
    return ids.length;  // 返回删除条数
  } else {
    config.set('logs', []);
    return 0;
  }
}

// 模型配置操作
export function getModels() {
  return config.get('models') || {};
}

export function getModel(modelName) {
  const models = getModels();
  return models[modelName];
}

export function addModel(modelName, configData) {
  const models = getModels();
  models[modelName] = {
    ...configData,
    createdAt: new Date().toISOString()
  };
  config.set('models', models);
  return models[modelName];
}

export function updateModel(modelName, updates) {
  const models = getModels();
  if (!models[modelName]) {
    throw new Error(`模型 ${modelName} 不存在`);
  }
  models[modelName] = {
    ...models[modelName],
    ...updates,
    updatedAt: new Date().toISOString()
  };
  config.set('models', models);
  return models[modelName];
}

export function removeModel(modelName) {
  const models = getModels();
  delete models[modelName];
  config.set('models', models);
  return true;
}

// 预算操作
export function getBudget() {
  return config.get('budget');
}

export function setBudget(amount, period = 'month', warningThreshold = 80) {
  config.set('budget', {
    enabled: true,
    amount: parseFloat(amount),
    period,
    warningThreshold: parseInt(warningThreshold)
  });
}

export function resetBudget() {
  config.set('budget', {
    enabled: false,
    amount: 0,
    period: 'month',
    warningThreshold: 80
  });
}

// 辅助函数
function getPeriodStart(period, now = new Date()) {
  const start = new Date(now);

  switch (period) {
    case 'day':
      start.setHours(0, 0, 0, 0);
      break;
    case 'week':
      const dayOfWeek = start.getDay();
      const diff = start.getDate() - dayOfWeek + (dayOfWeek === 0 ? -6 : 1);
      start.setDate(diff);
      start.setHours(0, 0, 0, 0);
      break;
    case 'month':
      start.setDate(1);
      start.setHours(0, 0, 0, 0);
      break;
    case 'all':
    default:
      start.setFullYear(start.getFullYear() - 10);
      break;
  }

  return start;
}

// 成本计算
export function calculateCost(log) {
  if (log.cost && log.cost > 0) {
    return parseFloat(log.cost);
  }

  const model = getModel(log.model);
  if (!model) {
    console.warn(`未知模型: ${log.model}`);
    return 0;
  }

  const inputCost = (log.promptTokens || 0) / 1000000 * model.inputPrice;
  const outputCost = (log.completionTokens || 0) / 1000000 * model.outputPrice;

  return inputCost + outputCost;
}

export function calculateTotalCost(logs) {
  return logs.reduce((total, log) => total + calculateCost(log), 0);
}

// 数据统计
export function getStats(logs, groupBy = null) {
  if (!groupBy) {
    return {
      totalRequests: logs.length,
      totalTokens: logs.reduce((sum, log) => sum + (log.promptTokens || 0) + (log.completionTokens || 0), 0),
      totalCost: calculateTotalCost(logs)
    };
  }

  const groups = {};
  logs.forEach(log => {
    let key;
    switch (groupBy) {
      case 'model':
        key = log.model;
        break;
      case 'session':
        key = log.session || 'none';
        break;
      case 'day':
        key = log.timestamp.split('T')[0];
        break;
      default:
        key = 'other';
    }

    if (!groups[key]) {
      groups[key] = {
        requests: 0,
        tokens: 0,
        cost: 0
      };
    }

    groups[key].requests++;
    groups[key].tokens += (log.promptTokens || 0) + (log.completionTokens || 0);
    groups[key].cost += calculateCost(log);
  });

  return groups;
}
