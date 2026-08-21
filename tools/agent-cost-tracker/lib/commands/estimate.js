/**
 * Estimate Command - 快速估算成本（不写入日志）
 */

import chalk from 'chalk';
import { getModel } from '../storage.js';

export default async function estimateCommand(options) {
  const model = getModel(options.model);
  if (!model) {
    console.error(chalk.red(`错误: 未知模型 ${options.model}`));
    console.error(chalk.gray('使用 act config list 查看已配置的模型'));
    process.exit(1);
  }

  // 解析 token 数量（三选一：直接指定 / total 按输入:输出=1:2 拆分 / 字数换算）
  let promptTokens = parseInt(options.promptTokens) || 0;
  let completionTokens = parseInt(options.completionTokens) || 0;
  const basis = [];  // 记录换算依据，用于展示

  if (!promptTokens && !completionTokens) {
    if (options.totalTokens) {
      const total = parseInt(options.totalTokens) || 0;
      promptTokens = Math.round(total / 3);
      completionTokens = total - promptTokens;
      basis.push(`total ${total.toLocaleString()} → 1:2 拆分`);
    } else if (options.words) {
      const totalTokens = Math.round(parseFloat(options.words) * 1.3);
      promptTokens = Math.round(totalTokens / 3);
      completionTokens = totalTokens - promptTokens;
      basis.push(`words ${options.words} × 1.3 tokens/word → 1:2 拆分`);
    }
  }

  if (!promptTokens && !completionTokens) {
    console.error(chalk.red('错误: 必须提供 --prompt-tokens/--completion-tokens、--total-tokens 或 --words'));
    process.exit(1);
  }

  const rate = parseInt(options.rate) || 1;
  const currency = model.currency === 'CNY' ? '¥' : '$';

  const inputCost = promptTokens / 1000000 * model.inputPrice;
  const outputCost = completionTokens / 1000000 * model.outputPrice;
  const perCallCost = inputCost + outputCost;
  const totalCost = perCallCost * rate;

  console.log(chalk.bold('💰 成本估算'));
  console.log(`  模型: ${chalk.cyan(options.model)} (${currency}${model.inputPrice}/${model.outputPrice} per 1M tokens)`);
  console.log(`  输入 tokens: ${chalk.yellow(promptTokens.toLocaleString())} → ${currency}${inputCost.toFixed(6)}`);
  console.log(`  输出 tokens: ${chalk.yellow(completionTokens.toLocaleString())} → ${currency}${outputCost.toFixed(6)}`);
  if (basis.length) {
    console.log(`  换算: ${chalk.gray(basis.join('; '))}`);
  }
  if (rate > 1) {
    console.log(`  单次成本: ${currency}${perCallCost.toFixed(6)} × ${rate} 次`);
  }
  console.log(`  ${chalk.green.bold('总成本')}: ${chalk.green(currency + totalCost.toFixed(4))}`);
}
