#!/usr/bin/env node
/**
 * Agent Cost Tracker (act) - AI Agent 成本追踪器
 * 追踪 token 使用、计算成本、优化 AI 开支
 */

import { program } from 'commander';
import chalk from 'chalk';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { existsSync } from 'fs';
import { readFileSync, writeFileSync, mkdirSync } from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const packageJson = JSON.parse(
  readFileSync(join(__dirname, '../package.json'), 'utf-8')
);

program
  .name('act')
  .description('AI Agent 成本追踪器 - 追踪 token 使用、计算成本、优化 AI 开支')
  .version(packageJson.version);

// 日志记录
program
  .command('log')
  .description('记录一次 AI 使用')
  .option('-m, --model <model>', '模型名称 (如 gpt-4, claude-3-opus)')
  .option('-p, --prompt-tokens <num>', '输入 token 数量')
  .option('-c, --completion-tokens <num>', '输出 token 数量')
  .option('-s, --session <session>', '会话标识')
  .option('--cost <cost>', '直接指定成本 (美元)', '0')
  .option('-n, --note <note>', '备注说明')
  .action(async (options) => {
    const { default: logCommand } = await import('../lib/commands/log.js');
    await logCommand(options);
  });

// 查看统计
program
  .command('stats')
  .description('查看成本统计')
  .option('-p, --period <period>', '时间周期: day, week, month, all', 'week')
  .option('-m, --model <model>', '按模型筛选')
  .option('-s, --session <session>', '按会话筛选')
  .option('-g, --group-by <field>', '分组方式: model, session, day', 'model')
  .option('--format <format>', '输出格式: table, json', 'table')
  .action(async (options) => {
    const { default: statsCommand } = await import('../lib/commands/stats.js');
    await statsCommand(options);
  });

// 趋势分析
program
  .command('trend')
  .description('查看成本趋势')
  .option('-d, --days <days>', '查看最近 N 天', '30')
  .option('--chart', '显示 ASCII 图表')
  .action(async (options) => {
    const { default: trendCommand } = await import('../lib/commands/trend.js');
    await trendCommand(options);
  });

// 模型配置
program
  .command('config')
  .description('管理模型价格配置')
  .argument('[action]', '操作: list, add, remove, update', 'list')
  .option('-m, --model <model>', '模型名称')
  .option('-i, --input-price <price>', '输入价格 (每 1M tokens)')
  .option('-o, --output-price <price>', '输出价格 (每 1M tokens)')
  .option('-c, --currency <currency>', '货币单位', 'USD')
  .action(async (action, options) => {
    const { default: configCommand } = await import('../lib/commands/config.js');
    await configCommand(action, options);
  });

// 导出数据
program
  .command('export')
  .description('导出成本数据')
  .option('-p, --period <period>', '时间周期: day, week, month, all', 'month')
  .option('-f, --format <format>', '导出格式: json, csv, markdown', 'json')
  .option('-o, --output <file>', '输出文件路径')
  .action(async (options) => {
    const { default: exportCommand } = await import('../lib/commands/export.js');
    await exportCommand(options);
  });

// 预算警告
program
  .command('budget')
  .description('设置和检查预算')
  .argument('[action]', '操作: set, check, reset', 'check')
  .option('-a, --amount <amount>', '预算金额')
  .option('-p, --period <period>', '预算周期: day, week, month', 'month')
  .option('-w, --warning <percent>', '警告阈值 (%)', '80')
  .action(async (action, options) => {
    const { default: budgetCommand } = await import('../lib/commands/budget.js');
    await budgetCommand(action, options);
  });

// 快速估算
program
  .command('estimate')
  .description('快速估算成本')
  .requiredOption('-m, --model <model>', '模型名称')
  .option('-p, --prompt-tokens <num>', '输入 token 数量')
  .option('-c, --completion-tokens <num>', '输出 token 数量')
  .option('-t, --total-tokens <num>', '总 token 数量 (假设输入:输出 = 1:2)')
  .option('--words <num>', '字数 (约 1.3 tokens/word)')
  .option('-r, --rate <rate>', '预期请求次数', '1')
  .action(async (options) => {
    const { default: estimateCommand } = await import('../lib/commands/estimate.js');
    await estimateCommand(options);
  });

// 清空数据
program
  .command('clear')
  .description('清空成本数据')
  .option('-y, --yes', '确认清空')
  .option('--before <date>', '清空指定日期之前的数据')
  .action(async (options) => {
    const { default: clearCommand } = await import('../lib/commands/clear.js');
    await clearCommand(options);
  });

program.parse();
