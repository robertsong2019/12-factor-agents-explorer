#!/usr/bin/env node

import { Command } from 'commander';
import chalk from 'chalk';
import { init } from '../lib/commands/init.js';
import { validate } from '../lib/commands/validate.js';
import { generate } from '../lib/commands/generate.js';
import { test } from '../lib/commands/test.js';
import { serve } from '../lib/commands/serve.js';

const program = new Command();

program
  .name('mcpt')
  .description('MCP Server 开发工具包 - 开发、测试、管理 MCP 服务器')
  .version('1.0.0');

// 初始化 MCP 服务器项目
program
  .command('init [name]')
  .description('初始化新的 MCP 服务器项目')
  .option('-t, --type <type>', '服务器类型 (stdlib|stdio|sse)', 'stdio')
  .option('-d, --description <desc>', '服务器描述')
  .option('-e, --example', '生成示例代码（echo 工具）')
  .action(init);

// 验证 MCP 服务器配置
program
  .command('validate [config]')
  .description('验证 MCP 服务器配置文件')
  .option('-s, --schema <schema>', '使用指定的 schema 文件')
  .action(validate);

// 生成 MCP 服务器代码
program
  .command('generate')
  .description('生成 MCP 服务器代码')
  .option('-f, --file <file>', '配置文件路径', 'mcp-server.json')
  .option('-o, --output <dir>', '输出目录', 'dist')
  .action(generate);

// 测试 MCP 服务器
program
  .command('test')
  .description('测试 MCP 服务器')
  .option('-s, --server <path>', '服务器路径')
  .option('-t, --transport <type>', '传输类型 (stdio|sse)', 'stdio')
  .option('-v, --verbose', '详细输出')
  .action(test);

// 启动 MCP 服务器
program
  .command('serve')
  .description('启动 MCP 服务器')
  .option('-s, --server <path>', '服务器路径')
  .option('-p, --port <port>', 'SSE 模式下的端口号', '3000')
  .option('-h, --host <host>', 'SSE 模式下的主机地址', 'localhost')
  .action(serve);

// 解析命令行参数（无参数时仅输出帮助并以 0 退出，而非 commander 默认的 error=1）
if (!process.argv.slice(2).length) {
  program.outputHelp();
} else {
  program.parse(process.argv);
}
