/**
 * Clear Command - 清空成本数据
 */

import chalk from 'chalk';
import { clearLogs, getLogs } from '../storage.js';

export default async function clearCommand(options) {
  // 安全确认：必须 -y
  if (!options.yes) {
    const count = getLogs({ period: 'all' }).length;
    console.log(chalk.yellow(`⚠️  将清空 ${count} 条成本记录${options.before ? `（${options.before} 之前）` : '（全部）'}`));
    console.log(chalk.gray('确认请加 -y / --yes'));
    process.exit(1);
  }

  try {
    if (options.before) {
      const removed = clearLogs(options.before);
      const remaining = getLogs({ period: 'all' }).length;
      console.log(chalk.green(`✅ 已删除 ${options.before} 之前的 ${removed} 条记录，剩余 ${remaining} 条`));
    } else {
      clearLogs();
      console.log(chalk.green('✅ 已清空全部成本记录'));
    }
  } catch (error) {
    console.error(chalk.red(`清空失败: ${error.message}`));
    process.exit(1);
  }
}
