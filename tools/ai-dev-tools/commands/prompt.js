import chalk from 'chalk';
import inquirer from 'inquirer';
import fs from 'fs-extra';
import ora from 'ora';
import { storage } from '../lib/storage.js';

export default async function promptCommand(action, options) {
  switch (action) {
    case 'save':
      await savePrompt(options);
      break;
    case 'list':
      await listPrompts(options);
      break;
    case 'search':
      await searchPrompts(options);
      break;
    case 'use':
      await usePrompt(options);
      break;
    case 'export':
      await exportPrompts(options);
      break;
    case 'delete':
      await deletePrompt(options);
      break;
    default:
      await listPrompts(options);
  }
}

async function savePrompt(options) {
  console.log(chalk.bold('\n💾 保存提示词\n'));
  
  let promptData = {};
  
  // 从文件加载或交互式输入
  if (options.file) {
    const content = await fs.readFile(options.file, 'utf-8');
    promptData.content = content;
    promptData.name = options.name || path.basename(options.file, path.extname(options.file));
  } else {
    const answers = await inquirer.prompt([
      {
        type: 'input',
        name: 'name',
        message: '提示词名称:',
        default: options.name,
        validate: (input) => input.trim() ? true : '名称不能为空'
      },
      {
        type: 'editor',
        name: 'content',
        message: '提示词内容:',
        default: ''
      },
      {
        type: 'input',
        name: 'description',
        message: '描述（可选）:',
      },
      {
        type: 'list',
        name: 'category',
        message: '分类:',
        choices: [
          '代码生成',
          '代码审查',
          '文档编写',
          '数据分析',
          '创意写作',
          '翻译',
          '对话',
          '其他'
        ],
        default: options.category || '其他'
      },
      {
        type: 'input',
        name: 'tags',
        message: '标签（逗号分隔）:',
        default: options.tags || ''
      }
    ]);
    
    promptData = {
      ...answers,
      tags: answers.tags.split(',').map(t => t.trim()).filter(t => t)
    };
  }
  
  const spinner = ora('保存提示词...').start();
  
  try {
    const saved = await storage.savePrompt(promptData);
    spinner.succeed(chalk.green(`✓ 提示词已保存: ${saved.name} (ID: ${saved.id})`));
    
    console.log('\n提示词信息:');
    console.log(chalk.gray('  名称:'), saved.name);
    console.log(chalk.gray('  分类:'), saved.category);
    console.log(chalk.gray('  标签:'), (saved.tags || []).join(', '));
    console.log(chalk.gray('  ID:'), saved.id);
    console.log();
  } catch (error) {
    spinner.fail(chalk.red(`保存失败: ${error.message}`));
  }
}

async function listPrompts(options) {
  console.log(chalk.bold('\n📋 提示词列表\n'));
  
  const prompts = storage.getPrompts(options);
  
  if (prompts.length === 0) {
    console.log(chalk.gray('暂无保存的提示词'));
    console.log(chalk.gray('使用 ' + chalk.cyan('aid prompt save') + ' 保存你的第一个提示词\n'));
    return;
  }
  
  // 按分类分组
  const byCategory = {};
  prompts.forEach(p => {
    const cat = p.category || '未分类';
    if (!byCategory[cat]) byCategory[cat] = [];
    byCategory[cat].push(p);
  });
  
  Object.entries(byCategory).forEach(([category, items]) => {
    console.log(chalk.bold.cyan(`\n${category} (${items.length})`));
    items.forEach(p => {
      const tags = p.tags?.length ? chalk.gray(` [${p.tags.join(', ')}]`) : '';
      const usage = p.usageCount ? chalk.yellow(` (使用 ${p.usageCount} 次)`) : '';
      console.log(`  • ${chalk.white(p.name)}${tags}${usage}`);
      if (p.description) {
        console.log(chalk.gray(`    ${p.description}`));
      }
    });
  });
  
  console.log();
}

async function searchPrompts(options) {
  const query = options.query;
  
  if (!query) {
    const answer = await inquirer.prompt([
      {
        type: 'input',
        name: 'query',
        message: '搜索关键词:',
        validate: (input) => input.trim() ? true : '请输入搜索关键词'
      }
    ]);
    options.query = answer.query;
  }
  
  const spinner = ora('搜索中...').start();
  const prompts = storage.getPrompts({ query: options.query });
  spinner.stop();
  
  console.log(chalk.bold(`\n🔍 搜索结果: "${options.query}"\n`));
  
  if (prompts.length === 0) {
    console.log(chalk.gray('未找到匹配的提示词\n'));
    return;
  }
  
  prompts.forEach(p => {
    console.log(chalk.cyan(`\n${p.name}`));
    console.log(chalk.gray('分类:'), p.category || '未分类');
    if (p.description) {
      console.log(chalk.gray('描述:'), p.description);
    }
    console.log(chalk.gray('内容预览:'));
    console.log(chalk.gray(p.content.substring(0, 150) + '...'));
  });
  
  console.log();
}

async function usePrompt(options) {
  const prompts = storage.getPrompts();
  
  if (prompts.length === 0) {
    console.log(chalk.yellow('暂无保存的提示词'));
    return;
  }
  
  let selectedPrompt;
  
  if (options.name) {
    selectedPrompt = prompts.find(p => 
      p.name === options.name || p.id === options.name
    );
    if (!selectedPrompt) {
      console.log(chalk.red(`未找到提示词: ${options.name}`));
      return;
    }
  } else {
    const answer = await inquirer.prompt([
      {
        type: 'list',
        name: 'prompt',
        message: '选择提示词:',
        choices: prompts.map(p => ({
          name: `${p.name} (${p.category || '未分类'})`,
          value: p
        }))
      }
    ]);
    selectedPrompt = answer.prompt;
  }
  
  // 更新使用计数
  await storage.updatePrompt(selectedPrompt.id, {
    usageCount: (selectedPrompt.usageCount || 0) + 1
  });
  
  console.log(chalk.bold('\n📝 提示词内容:\n'));
  console.log(chalk.white(selectedPrompt.content));
  console.log();
  console.log(chalk.gray('复制以上内容到你的 AI 工具中使用\n'));
}

async function exportPrompts(options) {
  const outputPath = options.output || `prompts-export-${Date.now()}.md`;
  const spinner = ora('导出提示词...').start();
  
  try {
    await storage.exportData('markdown', outputPath);
    spinner.succeed(chalk.green(`✓ 已导出到: ${outputPath}\n`));
  } catch (error) {
    spinner.fail(chalk.red(`导出失败: ${error.message}`));
  }
}

async function deletePrompt(options) {
  const prompts = storage.getPrompts();
  
  if (prompts.length === 0) {
    console.log(chalk.yellow('暂无保存的提示词'));
    return;
  }
  
  let targetId;
  let targetName;
  
  if (options.name) {
    const target = prompts.find(p => p.name === options.name || p.id === options.name);
    if (!target) {
      console.log(chalk.red(`未找到提示词: ${options.name}`));
      process.exitCode = 1;
      return;
    }
    targetId = target.id;
    targetName = target.name;
  } else {
    const answer = await inquirer.prompt([
      {
        type: 'list',
        name: 'prompt',
        message: '选择要删除的提示词:',
        choices: prompts.map(p => ({
          name: `${p.name} (${p.category || '未分类'})`,
          value: p.id
        }))
      },
      {
        type: 'confirm',
        name: 'confirm',
        message: '确认删除？',
        default: false
      }
    ]);
    
    if (!answer.confirm) {
      console.log(chalk.gray('已取消\n'));
      return;
    }
    
    targetId = answer.prompt;
    const target = prompts.find(p => p.id === targetId);
    targetName = target ? target.name : targetId;
  }
  
  try {
    await storage.deletePrompt(targetId);
    console.log(chalk.green(`✓ 提示词已删除${targetName ? `: ${targetName}` : ''}\n`));
  } catch (error) {
    console.log(chalk.red(`删除失败: ${error.message}`));
    process.exitCode = 1;
  }
}

import path from 'path';
