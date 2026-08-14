/**
 * Export Command - 导出成本数据
 */

import chalk from 'chalk';
import { getLogs, calculateCost } from '../storage.js';
import { writeFileSync } from 'fs';
import { format } from 'date-fns';

export default async function exportCommand(options) {
  try {
    const logs = getLogs({ period: options.period });

    if (logs.length === 0) {
      console.log(chalk.yellow('⚠️  没有数据可导出'));
      return;
    }

    let output = '';
    let filename = '';
    const timestamp = format(new Date(), 'yyyyMMdd-HHmmss');

    switch (options.format) {
      case 'csv':
        output = exportToCSV(logs);
        filename = `act-export-${timestamp}.csv`;
        break;

      case 'markdown':
        output = exportToMarkdown(logs, options.period);
        filename = `act-export-${timestamp}.md`;
        break;

      case 'json':
      default:
        output = exportToJSON(logs);
        filename = `act-export-${timestamp}.json`;
        break;
    }

    if (options.output) {
      writeFileSync(options.output, output, 'utf-8');
      console.log(chalk.green(`✅ 数据已导出到: ${options.output}`));
    } else {
      console.log(output);

      if (!options.format || options.format === 'json') {
        console.log(chalk.gray('\n💡 提示: 使用 -o <file> 保存到文件'));
      }
    }

  } catch (error) {
    console.error(chalk.red('❌ 导出失败:'), error.message);
    process.exit(1);
  }
}

export function exportToJSON(logs) {
  const data = logs.map(log => ({
    id: log.id,
    timestamp: log.timestamp,
    model: log.model,
    promptTokens: log.promptTokens,
    completionTokens: log.completionTokens,
    totalTokens: (log.promptTokens || 0) + (log.completionTokens || 0),
    cost: calculateCost(log),
    session: log.session,
    note: log.note
  }));

  const totalCost = data.reduce((sum, item) => sum + item.cost, 0);
  const totalTokens = data.reduce((sum, item) => sum + item.totalTokens, 0);

  return JSON.stringify({
    exportedAt: new Date().toISOString(),
    summary: {
      totalRequests: data.length,
      totalCost,
      totalTokens
    },
    data
  }, null, 2);
}

export function exportToCSV(logs) {
  const headers = ['ID', 'Timestamp', 'Model', 'Prompt Tokens', 'Completion Tokens', 'Total Tokens', 'Cost', 'Session', 'Note'];

  const rows = logs.map(log => [
    log.id,
    log.timestamp,
    log.model,
    log.promptTokens || 0,
    log.completionTokens || 0,
    (log.promptTokens || 0) + (log.completionTokens || 0),
    calculateCost(log).toFixed(6),
    log.session || '',
    (log.note || '').replace(/,/g, '；')
  ]);

  return [headers, ...rows]
    .map(row => row.join(','))
    .join('\n');
}

export function exportToMarkdown(logs, period) {
  const totalCost = logs.reduce((sum, log) => sum + calculateCost(log), 0);
  const totalTokens = logs.reduce((sum, log) => sum + (log.promptTokens || 0) + (log.completionTokens || 0), 0);

  let md = `# AI 成本报告\n\n`;
  md += `**导出时间:** ${format(new Date(), 'yyyy-MM-dd HH:mm:ss')}\n\n`;
  md += `## 汇总\n\n`;
  md += `- **时间范围:** ${period}\n`;
  md += `- **总请求次数:** ${logs.length}\n`;
  md += `- **总 Tokens:** ${totalTokens.toLocaleString()}\n`;
  md += `- **总成本:** $${totalCost.toFixed(4)}\n\n`;
  md += `## 详细记录\n\n`;
  md += `| 时间 | 模型 | 输入 | 输出 | 总 Tokens | 成本 | 会话 |\n`;
  md += `|------|------|------|------|-----------|------|------|\n`;

  logs.forEach(log => {
    const time = format(new Date(log.timestamp), 'MM-dd HH:mm');
    const promptTokens = (log.promptTokens || 0).toLocaleString();
    const completionTokens = (log.completionTokens || 0).toLocaleString();
    const totalTokens = ((log.promptTokens || 0) + (log.completionTokens || 0)).toLocaleString();
    const cost = calculateCost(log).toFixed(4);
    const session = log.session || '-';

    md += `| ${time} | ${log.model} | ${promptTokens} | ${completionTokens} | ${totalTokens} | $${cost} | ${session} |\n`;
  });

  return md;
}
