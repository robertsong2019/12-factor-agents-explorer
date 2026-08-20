#!/usr/bin/env node

import { Command } from 'commander';
import chalk from 'chalk';
import inquirer from 'inquirer';
import { AgentManager } from '../lib/agent-manager.js';
import { ConfigManager } from '../lib/config-manager.js';
import { Monitor } from '../lib/monitor.js';

const program = new Command();
const agentManager = new AgentManager();
const configManager = new ConfigManager();
const monitor = new Monitor();

program
  .name('afm')
  .description('AI Agent Framework Manager - 统一管理AI Agent')
  .version('1.0.0');

// 初始化命令
program
  .command('init')
  .description('初始化Agent框架配置')
  .option('-f, --force', '强制覆盖现有配置')
  .action(async (options) => {
    try {
      await agentManager.init(options.force);
      console.log(chalk.green('✓ Agent框架初始化完成'));
    } catch (error) {
      console.error(chalk.red('✗ 初始化失败:'), error.message);
      process.exit(1);
    }
  });

// Agent管理命令
program
  .command('agent')
  .alias('a')
  .description('Agent管理命令')
  .option('--list', '列出所有Agent')
  .option('--start <name>', '启动指定Agent')
  .option('--stop <name>', '停止指定Agent')
  .option('--status <name>', '查看Agent状态')
  .option('--add', '添加新Agent')
  .action(async (options) => {
    try {
      if (options.list) {
        await agentManager.listAgents();
      } else if (options.start) {
        await agentManager.startAgent(options.start);
      } else if (options.stop) {
        await agentManager.stopAgent(options.stop);
      } else if (options.status) {
        const status = await agentManager.getAgentStatus(options.status);
        console.log(chalk.bold(`\n🤖 Agent "${options.status}":`));
        console.log(`  状态: ${status.running ? chalk.green('运行中') : chalk.red('已停止')}`);
        console.log(`  PID: ${status.pid || 'N/A'}`);
        console.log(`  运行时间: ${status.uptime}秒`);
      } else if (options.add) {
        await addNewAgent();
      } else {
        await showAgentMenu();
      }
    } catch (error) {
      console.error(chalk.red('✗ Agent操作失败:'), error.message);
      process.exit(1);
    }
  });

// 监控命令
program
  .command('monitor')
  .alias('m')
  .description('监控框架和Agent状态')
  .option('--dashboard', '显示监控面板')
  .option('--metrics <name>', '查看指定Agent的详细指标')
  .option('--logs <name>', '查看Agent日志')
  .action(async (options) => {
    try {
      if (options.dashboard) {
        await monitor.showDashboard();
      } else if (options.metrics) {
        await monitor.showMetrics(options.metrics);
      } else if (options.logs) {
        await monitor.showLogs(options.logs);
      } else {
        await monitor.showOverview();
      }
    } catch (error) {
      console.error(chalk.red('✗ 监控操作失败:'), error.message);
      process.exit(1);
    }
  });

// 配置管理命令
program
  .command('config')
  .description('配置管理')
  .option('--show', '显示当前配置')
  .option('--edit', '编辑配置文件')
  .option('--reset', '重置配置')
  .action(async (options) => {
    try {
      if (options.show) {
        await configManager.showConfig();
      } else if (options.edit) {
        await configManager.editConfig();
      } else if (options.reset) {
        await configManager.resetConfig();
      } else {
        await showConfigMenu();
      }
    } catch (error) {
      console.error(chalk.red('✗ 配置操作失败:'), error.message);
      process.exit(1);
    }
  });

// 工具命令
program
  .command('tools')
  .alias('t')
  .description('工具和实用程序')
  .option('--backup', '备份配置和数据')
  .option('--upgrade', '升级到最新版本')
  .option('--diagnose', '运行诊断检查')
  .action(async (options) => {
    try {
      if (options.backup) {
        await configManager.backupConfig();
      } else if (options.upgrade) {
        await configManager.upgrade();
      } else if (options.diagnose) {
        await configManager.diagnose();
      } else {
        await showToolsMenu();
      }
    } catch (error) {
      console.error(chalk.red('✗ 工具操作失败:'), error.message);
      process.exit(1);
    }
  });

program.parse();

// 辅助函数
async function showAgentMenu() {
  const { action } = await inquirer.prompt([
    {
      type: 'list',
      name: 'action',
      message: '选择操作:',
      choices: [
        '列出所有Agent',
        '启动Agent',
        '停止Agent',
        '查看状态',
        '添加新Agent',
        '返回'
      ]
    }
  ]);

  switch (action) {
    case '列出所有Agent':
      await agentManager.listAgents();
      break;
    case '启动Agent':
      const { agentName } = await inquirer.prompt([
        {
          type: 'input',
          name: 'agentName',
          message: '输入Agent名称:'
        }
      ]);
      await agentManager.startAgent(agentName);
      break;
    case '停止Agent':
      const { stopName } = await inquirer.prompt([
        {
          type: 'input',
          name: 'stopName',
          message: '输入要停止的Agent名称:'
        }
      ]);
      await agentManager.stopAgent(stopName);
      break;
    case '查看状态':
      const { statusName } = await inquirer.prompt([
        {
          type: 'input',
          name: 'statusName',
          message: '输入要查看状态的Agent名称:'
        }
      ]);
      await agentManager.getAgentStatus(statusName);
      break;
    case '添加新Agent':
      await addNewAgent();
      break;
  }
}

async function addNewAgent() {
  const answers = await inquirer.prompt([
    {
      type: 'input',
      name: 'name',
      message: 'Agent名称:',
      validate: (input) => input.length > 0 || '名称不能为空'
    },
    {
      type: 'list',
      name: 'type',
      message: 'Agent类型:',
      choices: ['OpenAI', 'Claude', 'Gemini', 'Custom']
    },
    {
      type: 'input',
      name: 'endpoint',
      message: 'API端点:',
      when: (answers) => answers.type !== 'Custom'
    },
    {
      type: 'input',
      name: 'apiKey',
      message: 'API密钥:',
      validate: (input) => input.length > 0 || 'API密钥不能为空'
    },
    {
      type: 'input',
      name: 'model',
      message: '模型名称:',
      default: 'gpt-3.5-turbo'
    },
    {
      type: 'number',
      name: 'maxTokens',
      message: '最大Token数:',
      default: 4000,
      validate: (input) => input > 0 || '最大Token数必须大于0'
    }
  ]);

  await agentManager.addAgent(answers);
  console.log(chalk.green('✓ Agent添加成功'));
}

async function showConfigMenu() {
  const { action } = await inquirer.prompt([
    {
      type: 'list',
      name: 'action',
      message: '选择配置操作:',
      choices: [
        '显示当前配置',
        '编辑配置文件',
        '重置配置',
        '返回'
      ]
    }
  ]);

  switch (action) {
    case '显示当前配置':
      await configManager.showConfig();
      break;
    case '编辑配置文件':
      await configManager.editConfig();
      break;
    case '重置配置':
      await configManager.resetConfig();
      break;
  }
}

async function showToolsMenu() {
  const { action } = await inquirer.prompt([
    {
      type: 'list',
      name: 'action',
      message: '选择工具操作:',
      choices: [
        '备份配置和数据',
        '升级到最新版本',
        '运行诊断检查',
        '返回'
      ]
    }
  ]);

  switch (action) {
    case '备份配置和数据':
      await configManager.backupConfig();
      break;
    case '升级到最新版本':
      await configManager.upgrade();
      break;
    case '运行诊断检查':
      await configManager.diagnose();
      break;
  }
}