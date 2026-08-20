import chalk from 'chalk';

// 诚实占位：命令已注册但尚未实现，明确退出而非静默失败
export async function serve() {
  console.error(chalk.yellow('⚠ mcpt serve（启动 MCP 服务器）尚未实现 — 此命令当前为占位符'));
  process.exit(1);
}
