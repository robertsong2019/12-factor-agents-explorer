#!/usr/bin/env node

import { Command } from 'commander';
import chalk from 'chalk';
import { createSkill, listTemplates, validateSkill } from '../lib/index.js';

const program = new Command();

program
  .name('skill-create')
  .description('快速生成 OpenClaw Agent Skill 骨架')
  .version('1.0.0');

program
  .command('new <name>')
  .description('创建新的 skill 项目')
  .option('-d, --description <desc>', 'Skill 描述')
  .option('-t, --template <type>', '模板类型: basic|api|mcp|coding', 'basic')
  .option('-o, --output <dir>', '输出目录', process.cwd())
  .option('--with-references', '包含 references/ 目录')
  .option('--with-scripts', '包含 scripts/ 目录')
  .action(async (name, options) => {
    try {
      const result = await createSkill(name, options);
      console.log(chalk.green(`✅ Skill "${name}" 创建成功！`));
      console.log(chalk.gray(`   📁 ${result.path}`));
      console.log(chalk.gray(`   📄 生成 ${result.files.length} 个文件`));
      result.files.forEach(f => console.log(chalk.gray(`      - ${f}`)));
      console.log();
      console.log(chalk.cyan('下一步:'));
      console.log(chalk.cyan(`  1. 编辑 SKILL.md 添加详细说明`));
      console.log(chalk.cyan(`  2. 在 ${name}/ 中实现你的逻辑`));
      console.log(chalk.cyan(`  3. 用 openclaw skill load 加载测试`));
    } catch (err) {
      console.error(chalk.red(`❌ 创建失败: ${err.message}`));
      process.exit(1);
    }
  });

program
  .command('templates')
  .description('列出可用模板')
  .action(() => {
    const templates = listTemplates();
    console.log(chalk.bold('可用模板:\n'));
    templates.forEach(t => {
      console.log(chalk.cyan(`  ${t.name.padEnd(12)}`) + chalk.gray(t.description));
    });
  });

program
  .command('validate <path>')
  .description('验证 skill 结构是否完整')
  .action(async (path) => {
    try {
      const result = await validateSkill(path);
      if (result.valid) {
        console.log(chalk.green('✅ Skill 结构验证通过'));
      } else {
        console.log(chalk.yellow('⚠️  发现问题:'));
        result.issues.forEach(i => console.log(chalk.yellow(`   - ${i}`)));
        process.exitCode = 1;
      }
    } catch (err) {
      console.error(chalk.red(`❌ 验证失败: ${err.message}`));
      process.exit(1);
    }
  });

program.parse();
