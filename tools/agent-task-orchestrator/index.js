#!/usr/bin/env node
/**
 * Agent Task Orchestrator - 智能Agent任务编排器
 * 基于依赖关系的任务流管理和执行，支持AI Agent协作
 */

import { program } from 'commander';
import chalk from 'chalk';
import fs from 'fs-extra';
import path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

program
  .name('ato')
  .description('智能Agent任务编排器 - 基于依赖关系的任务流管理和执行')
  .version('1.0.0');

program
  .command('create')
  .description('创建新的任务编排')
  .argument('<name>', '编排名称')
  .option('-d, --description <desc>', '编排描述')
  .option('-f, --force', '强制覆盖现有编排')
  .action(async (name, options) => {
    try {
      console.log(chalk.blue(`🚀 创建任务编排: ${name}`));
      
      const orchestratorDir = path.join(process.cwd(), '.orchestrator');
      const orchestratorFile = path.join(orchestratorDir, `${name}.json`);
      
      if (await fs.pathExists(orchestratorFile) && !options.force) {
        console.log(chalk.yellow(`⚠️  编排 ${name} 已存在，使用 --force 覆盖`));
        process.exit(1);
      }
      
      await fs.ensureDir(orchestratorDir);
      
      const orchestrator = {
        name,
        description: options.description || '',
        version: '1.0.0',
        createdAt: new Date().toISOString(),
        tasks: [],
        variables: {},
        settings: {
          parallelExecution: true,
          continueOnError: false,
          timeout: 300000 // 5 minutes
        }
      };
      
      await fs.writeJson(orchestratorFile, orchestrator, { spaces: 2 });
      console.log(chalk.green(`✅ 编排 ${name} 创建成功！`));
      console.log(chalk.gray(`位置: ${orchestratorFile}`));
      
    } catch (error) {
      console.error(chalk.red('❌ 创建失败:'), error.message);
      process.exit(1);
    }
  });

program
  .command('add-task')
  .description('添加任务到编排')
  .argument('<orchestrator>', '编排名称')
  .argument('<task-name>', '任务名称')
  .option('-t, --type <type>', '任务类型', 'shell')
  .option('-c, --command <cmd>', '执行命令')
  .option('-a, --agent <agent>', 'Agent名称')
  .option('-d, --depends <deps>', '依赖任务（逗号分隔）')
  .option('-p, --priority <num>', '优先级 (1-10)', '5')
  .option('-o, --output <path>', '输出文件路径')
  .option('--timeout <ms>', '超时时间（毫秒）')
  .option('--description <desc>', '任务描述')
  .action(async (orchestrator, taskName, options) => {
    try {
      console.log(chalk.blue(`📝 添加任务: ${taskName} 到 ${orchestrator}`));
      
      const orchestratorFile = path.join(process.cwd(), '.orchestrator', `${orchestrator}.json`);
      
      if (!await fs.pathExists(orchestratorFile)) {
        console.log(chalk.red(`❌ 编排 ${orchestrator} 不存在`));
        process.exit(1);
      }
      
      const orchestratorData = await fs.readJson(orchestratorFile);
      
      const task = {
        id: taskName,
        type: options.type,
        description: options.description || '',
        priority: parseInt(options.priority),
        createdAt: new Date().toISOString()
      };
      
      // 根据类型设置不同的配置
      if (options.type === 'shell') {
        task.command = options.command || '';
      } else if (options.type === 'agent') {
        task.agent = options.agent;
        task.prompt = options.command || '';
      } else if (options.type === 'function') {
        task.function = options.command;
      }
      
      // 依赖关系
      if (options.depends) {
        task.dependsOn = options.depends.split(',').map(d => d.trim());
      }
      
      // 超时设置
      if (options.timeout) {
        task.timeout = parseInt(options.timeout);
      }
      
      // 输出设置
      if (options.output) {
        task.output = options.output;
      }
      
      orchestratorData.tasks.push(task);
      await fs.writeJson(orchestratorFile, orchestratorData, { spaces: 2 });
      
      console.log(chalk.green(`✅ 任务 ${taskName} 添加成功！`));
      
    } catch (error) {
      console.error(chalk.red('❌ 添加任务失败:'), error.message);
      process.exit(1);
    }
  });

program
  .command('run')
  .description('执行任务编排')
  .argument('<orchestrator>', '编排名称')
  .option('-s, --sequential', '顺序执行（不并行）')
  .option('-d, --dry-run', '试运行，只显示执行计划')
  .option('-v, --verbose', '详细输出')
  .option('-t, --tasks <tasks>', '只执行指定任务（逗号分隔）')
  .action(async (orchestrator, options) => {
    try {
      console.log(chalk.blue(`🎯 执行编排: ${orchestrator}`));
      
      const orchestratorFile = path.join(process.cwd(), '.orchestrator', `${orchestrator}.json`);
      
      if (!await fs.pathExists(orchestratorFile)) {
        console.log(chalk.red(`❌ 编排 ${orchestrator} 不存在`));
        process.exit(1);
      }
      
      const orchestratorData = await fs.readJson(orchestratorFile);
      let tasks = orchestratorData.tasks;
      
      // 过滤任务
      if (options.tasks) {
        const taskNames = options.tasks.split(',').map(t => t.trim());
        tasks = tasks.filter(t => taskNames.includes(t.id));
      }
      
      // 构建执行计划
      const executionPlan = buildExecutionPlan(tasks, options.sequential);
      
      if (options.dryRun) {
        printExecutionPlan(executionPlan);
        return;
      }
      
      if (options.verbose) {
        printExecutionPlan(executionPlan);
      }
      
      // 执行任务
      const results = await executeTasks(executionPlan, orchestratorData.settings, options.verbose);
      
      // 显示结果
      printResults(results);
      
    } catch (error) {
      console.error(chalk.red('❌ 执行失败:'), error.message);
      process.exit(1);
    }
  });

program
  .command('list')
  .description('列出所有编排')
  .option('-v, --verbose', '显示详细信息')
  .action(async (options) => {
    try {
      const orchestratorDir = path.join(process.cwd(), '.orchestrator');
      
      if (!await fs.pathExists(orchestratorDir)) {
        console.log(chalk.yellow('⚠️  没有找到任何编排'));
        return;
      }
      
      const files = await fs.readdir(orchestratorDir);
      const orchestrators = files.filter(f => f.endsWith('.json'));
      
      if (orchestrators.length === 0) {
        console.log(chalk.yellow('⚠️  没有找到任何编排'));
        return;
      }
      
      console.log(chalk.blue('📋 任务编排列表:\n'));
      
      for (const file of orchestrators) {
        const orchestratorFile = path.join(orchestratorDir, file);
        const orchestrator = await fs.readJson(orchestratorFile);
        
        console.log(chalk.cyan(`📁 ${orchestrator.name}`));
        console.log(chalk.gray(`   描述: ${orchestrator.description || '无'}`));
        console.log(chalk.gray(`   任务数: ${orchestrator.tasks.length}`));
        console.log(chalk.gray(`   创建时间: ${new Date(orchestrator.createdAt).toLocaleString('zh-CN')}`));
        
        if (options.verbose && orchestrator.tasks.length > 0) {
          console.log(chalk.gray('   任务:'));
          orchestrator.tasks.forEach(task => {
            const statusIcon = getStatusIcon(task);
            console.log(chalk.gray(`     ${statusIcon} ${task.id} (${task.type}) - 优先级: ${task.priority}`));
          });
        }
        
        console.log();
      }
      
    } catch (error) {
      console.error(chalk.red('❌ 列出失败:'), error.message);
      process.exit(1);
    }
  });

program
  .command('status')
  .description('查看编排状态')
  .argument('<orchestrator>', '编排名称')
  .action(async (orchestrator) => {
    try {
      const orchestratorFile = path.join(process.cwd(), '.orchestrator', `${orchestrator}.json`);
      
      if (!await fs.pathExists(orchestratorFile)) {
        console.log(chalk.red(`❌ 编排 ${orchestrator} 不存在`));
        process.exit(1);
      }
      
      const orchestratorData = await fs.readJson(orchestratorFile);
      
      console.log(chalk.blue(`📊 编排状态: ${orchestratorData.name}\n`));
      
      console.log(chalk.cyan('信息:'));
      console.log(chalk.gray(`  描述: ${orchestratorData.description || '无'}`));
      console.log(chalk.gray(`  版本: ${orchestratorData.version}`));
      console.log(chalk.gray(`  创建时间: ${new Date(orchestratorData.createdAt).toLocaleString('zh-CN')}`));
      
      console.log(chalk.cyan('\n设置:'));
      console.log(chalk.gray(`  并行执行: ${orchestratorData.settings.parallelExecution ? '是' : '否'}`));
      console.log(chalk.gray(`  错误继续: ${orchestratorData.settings.continueOnError ? '是' : '否'}`));
      console.log(chalk.gray(`  超时时间: ${orchestratorData.settings.timeout}ms`));
      
      if (orchestratorData.tasks.length > 0) {
        console.log(chalk.cyan('\n任务:'));
        const executionPlan = buildExecutionPlan(orchestratorData.tasks, !orchestratorData.settings.parallelExecution);
        
        executionPlan.forEach((stage, index) => {
          console.log(chalk.yellow(`阶段 ${index + 1}:`));
          stage.forEach(task => {
            const deps = task.dependsOn && task.dependsOn.length > 0 
              ? chalk.gray(` (依赖: ${task.dependsOn.join(', ')})`)
              : '';
            console.log(chalk.gray(`  • ${task.id} (${task.type}) - 优先级: ${task.priority}${deps}`));
          });
        });
      }
      
    } catch (error) {
      console.error(chalk.red('❌ 查看状态失败:'), error.message);
      process.exit(1);
    }
  });

program
  .command('validate')
  .description('验证编排配置')
  .argument('<orchestrator>', '编排名称')
  .action(async (orchestrator) => {
    try {
      console.log(chalk.blue(`🔍 验证编排: ${orchestrator}`));
      
      const orchestratorFile = path.join(process.cwd(), '.orchestrator', `${orchestrator}.json`);
      
      if (!await fs.pathExists(orchestratorFile)) {
        console.log(chalk.red(`❌ 编排 ${orchestrator} 不存在`));
        process.exit(1);
      }
      
      const orchestratorData = await fs.readJson(orchestratorFile);
      const validation = validateOrchestrator(orchestratorData);
      
      if (validation.isValid) {
        console.log(chalk.green('✅ 编排验证通过！'));
      } else {
        console.log(chalk.red('❌ 编排验证失败：'));
        validation.errors.forEach(error => {
          console.log(chalk.red(`  • ${error}`));
        });
        process.exit(1);
      }
      
    } catch (error) {
      console.error(chalk.red('❌ 验证失败:'), error.message);
      process.exit(1);
    }
  });

program
  .command('export')
  .description('导出编排配置')
  .argument('<orchestrator>', '编排名称')
  .option('-f, --format <format>', '输出格式 (json|yaml|markdown)', 'json')
  .option('-o, --output <file>', '输出文件路径')
  .action(async (orchestrator, options) => {
    try {
      const orchestratorFile = path.join(process.cwd(), '.orchestrator', `${orchestrator}.json`);
      
      if (!await fs.pathExists(orchestratorFile)) {
        console.log(chalk.red(`❌ 编排 ${orchestrator} 不存在`));
        process.exit(1);
      }
      
      const orchestratorData = await fs.readJson(orchestratorFile);
      let output;
      let extension;
      
      switch (options.format) {
        case 'json':
          output = JSON.stringify(orchestratorData, null, 2);
          extension = '.json';
          break;
        case 'yaml':
          const yaml = await import('yaml');
          output = yaml.stringify(orchestratorData);
          extension = '.yaml';
          break;
        case 'markdown':
          output = generateMarkdownReport(orchestratorData);
          extension = '.md';
          break;
        default:
          console.log(chalk.red(`❌ 不支持的格式: ${options.format}`));
          process.exit(1);
      }
      
      if (options.output) {
        await fs.writeFile(options.output, output);
        console.log(chalk.green(`✅ 已导出到: ${options.output}`));
      } else {
        const defaultOutput = `${orchestrator}_export${extension}`;
        await fs.writeFile(defaultOutput, output);
        console.log(chalk.green(`✅ 已导出到: ${defaultOutput}`));
      }
      
    } catch (error) {
      console.error(chalk.red('❌ 导出失败:'), error.message);
      process.exit(1);
    }
  });

// 辅助函数

function buildExecutionPlan(tasks, sequential = false) {
  if (sequential || tasks.length === 0) {
    return tasks.map(task => [task]);
  }
  
  const taskMap = new Map(tasks.map(t => [t.id, t]));
  const executed = new Set();
  const plan = [];
  let remainingTasks = [...tasks];
  
  while (remainingTasks.length > 0) {
    const stage = [];
    const nextTasks = [];
    
    for (const task of remainingTasks) {
      const canExecute = !task.dependsOn || 
                        task.dependsOn.every(dep => executed.has(dep));
      
      if (canExecute) {
        stage.push(task);
      } else {
        nextTasks.push(task);
      }
    }
    
    if (stage.length === 0) {
      // 循环依赖或任务不可执行
      break;
    }
    
    stage.forEach(task => executed.add(task.id));
    plan.push(stage);
    remainingTasks = nextTasks;
  }
  
  if (remainingTasks.length > 0) {
    console.log(chalk.yellow('⚠️  检测到循环依赖或无法执行的任务:'));
    remainingTasks.forEach(task => {
      console.log(chalk.yellow(`  • ${task.id} (依赖: ${task.dependsOn?.join(', ') || '无'})`));
    });
  }
  
  return plan;
}

async function executeTasks(executionPlan, settings, verbose = false) {
  const results = {
    totalTasks: 0,
    completed: 0,
    failed: 0,
    skipped: 0,
    tasks: []
  };
  
  for (let stageIndex = 0; stageIndex < executionPlan.length; stageIndex++) {
    const stage = executionPlan[stageIndex];
    console.log(chalk.blue(`\n🔄 阶段 ${stageIndex + 1}/${executionPlan.length} (${stage.length} 个任务)`));
    
    const stagePromises = stage.map(async (task) => {
      try {
        results.totalTasks++;
        
        console.log(chalk.cyan(`▶️  执行: ${task.id} (${task.type})`));
        
        let result;
        const timeout = task.timeout || settings.timeout;
        
        switch (task.type) {
          case 'shell':
            result = await executeShellTask(task, timeout, verbose);
            break;
          case 'agent':
            result = await executeAgentTask(task, timeout, verbose);
            break;
          case 'function':
            result = await executeFunctionTask(task, timeout, verbose);
            break;
          default:
            throw new Error(`未知的任务类型: ${task.type}`);
        }
        
        results.completed++;
        console.log(chalk.green(`✅ 完成: ${task.id}`));
        
        return {
          id: task.id,
          status: 'completed',
          result
        };
        
      } catch (error) {
        results.failed++;
        console.log(chalk.red(`❌ 失败: ${task.id} - ${error.message}`));
        
        if (!settings.continueOnError) {
          throw error; // 停止执行
        }
        
        return {
          id: task.id,
          status: 'failed',
          error: error.message
        };
      }
    });
    
    // 等待当前阶段完成
    const stageResults = await Promise.all(stagePromises);
    results.tasks.push(...stageResults);
  }
  
  return results;
}

async function executeShellTask(task, timeout, verbose) {
  const { stdout, stderr } = await execAsync(task.command, {
    timeout,
    maxBuffer: 1024 * 1024 * 10
  });
  
  if (verbose) {
    console.log(chalk.gray('  输出:'), stdout);
    if (stderr) {
      console.log(chalk.yellow('  警告:'), stderr);
    }
  }
  
  // 保存输出到文件
  if (task.output) {
    await fs.writeFile(task.output, stdout);
  }
  
  return { stdout, stderr };
}

async function executeAgentTask(task, timeout, verbose) {
  // 这里可以集成实际的Agent调用
  if (verbose) {
    console.log(chalk.gray(`  Agent: ${task.agent}`));
    console.log(chalk.gray(`  Prompt: ${task.prompt}`));
  }
  
  // 模拟Agent执行
  const result = {
    agent: task.agent,
    prompt: task.prompt,
    response: `Agent ${task.agent} 执行结果`
  };
  
  if (task.output) {
    await fs.writeJson(task.output, result, { spaces: 2 });
  }
  
  return result;
}

async function executeFunctionTask(task, timeout, verbose) {
  if (verbose) {
    console.log(chalk.gray(`  Function: ${task.function}`));
  }
  
  // 这里可以集成实际的函数调用
  const result = {
    function: task.function,
    result: `Function ${task.function} 执行结果`
  };
  
  if (task.output) {
    await fs.writeJson(task.output, result, { spaces: 2 });
  }
  
  return result;
}

function printExecutionPlan(executionPlan) {
  console.log(chalk.blue('\n📋 执行计划:\n'));
  
  executionPlan.forEach((stage, index) => {
    console.log(chalk.yellow(`阶段 ${index + 1} (${stage.length} 个任务):`));
    stage.forEach(task => {
      const deps = task.dependsOn && task.dependsOn.length > 0 
        ? chalk.gray(` [依赖: ${task.dependsOn.join(', ')}]`)
        : '';
      console.log(chalk.gray(`  • ${task.id} (${task.type}) - 优先级: ${task.priority}${deps}`));
    });
    console.log();
  });
}

function printResults(results) {
  console.log(chalk.blue('\n📊 执行结果:'));
  console.log(chalk.blue('═'.repeat(50)));
  console.log(chalk.gray(`总任务数: ${results.totalTasks}`));
  console.log(chalk.green(`✅ 完成: ${results.completed}`));
  console.log(chalk.red(`❌ 失败: ${results.failed}`));
  console.log(chalk.yellow(`⏭️  跳过: ${results.skipped}`));
  
  if (results.totalTasks > 0) {
    const successRate = ((results.completed / results.totalTasks) * 100).toFixed(1);
    console.log(chalk.cyan(`成功率: ${successRate}%`));
  }
  
  if (results.failed > 0) {
    console.log(chalk.red('\n❌ 失败的任务:'));
    results.tasks.filter(t => t.status === 'failed').forEach(task => {
      console.log(chalk.red(`  • ${task.id}: ${task.error}`));
    });
  }
}

function validateOrchestrator(orchestrator) {
  const errors = [];
  
  if (!orchestrator.name) {
    errors.push('缺少编排名称');
  }
  
  if (!orchestrator.tasks || !Array.isArray(orchestrator.tasks)) {
    errors.push('任务列表格式错误');
  } else {
    const taskIds = new Set();
    
    orchestrator.tasks.forEach((task, index) => {
      if (!task.id) {
        errors.push(`任务 ${index + 1} 缺少ID`);
      } else {
        if (taskIds.has(task.id)) {
          errors.push(`任务ID重复: ${task.id}`);
        }
        taskIds.add(task.id);
      }
      
      if (!task.type) {
        errors.push(`任务 ${task.id || index + 1} 缺少类型`);
      }
      
      if (task.dependsOn) {
        task.dependsOn.forEach(dep => {
          if (!taskIds.has(dep) && !orchestrator.tasks.some(t => t.id === dep)) {
            errors.push(`任务 ${task.id} 依赖不存在的任务: ${dep}`);
          }
        });
      }
    });
  }
  
  return {
    isValid: errors.length === 0,
    errors
  };
}

function generateMarkdownReport(orchestrator) {
  let markdown = `# 任务编排: ${orchestrator.name}\n\n`;
  
  if (orchestrator.description) {
    markdown += `**描述:** ${orchestrator.description}\n\n`;
  }
  
  markdown += `## 基本信息\n\n`;
  markdown += `- **版本:** ${orchestrator.version}\n`;
  markdown += `- **创建时间:** ${new Date(orchestrator.createdAt).toLocaleString('zh-CN')}\n`;
  markdown += `- **任务数量:** ${orchestrator.tasks.length}\n\n`;
  
  markdown += `## 配置\n\n`;
  markdown += `- **并行执行:** ${orchestrator.settings.parallelExecution ? '是' : '否'}\n`;
  markdown += `- **错误继续:** ${orchestrator.settings.continueOnError ? '是' : '否'}\n`;
  markdown += `- **超时时间:** ${orchestrator.settings.timeout}ms\n\n`;
  
  if (orchestrator.tasks.length > 0) {
    markdown += `## 任务列表\n\n`;
    
    orchestrator.tasks.forEach((task, index) => {
      markdown += `### ${index + 1}. ${task.id}\n\n`;
      markdown += `- **类型:** ${task.type}\n`;
      markdown += `- **优先级:** ${task.priority}\n`;
      
      if (task.description) {
        markdown += `- **描述:** ${task.description}\n`;
      }
      
      if (task.dependsOn && task.dependsOn.length > 0) {
        markdown += `- **依赖:** ${task.dependsOn.join(', ')}\n`;
      }
      
      markdown += '\n';
    });
  }
  
  return markdown;
}

function getStatusIcon(task) {
  if (!task.status) return '⏸️';
  switch (task.status) {
    case 'completed': return '✅';
    case 'failed': return '❌';
    case 'running': return '🔄';
    case 'pending': return '⏳';
    default: return '⏸️';
  }
}

// Exports for testing
export {
  buildExecutionPlan,
  validateOrchestrator,
  generateMarkdownReport,
  getStatusIcon
};

if (import.meta.url === `file://${process.argv[1]}`) {
  program.parse();
}