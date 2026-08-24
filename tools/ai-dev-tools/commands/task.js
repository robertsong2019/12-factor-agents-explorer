import chalk from 'chalk';
import inquirer from 'inquirer';
import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';
import ora from 'ora';
import { storage } from '../lib/storage.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default async function taskCommand(template, options) {
  if (options.list || !template) {
    await listTemplates();
    return;
  }
  
  await generateTask(template, options);
}

async function listTemplates() {
  console.log(chalk.bold('\n📋 可用任务模板\n'));
  
  const templates = [
    {
      name: 'code-review',
      description: '代码审查任务',
      category: '代码质量',
      variables: ['file_path', 'review_type']
    },
    {
      name: 'refactor',
      description: '重构任务',
      category: '代码质量',
      variables: ['file_path', 'refactor_goal']
    },
    {
      name: 'test-generation',
      description: '测试生成',
      category: '测试',
      variables: ['file_path', 'test_framework']
    },
    {
      name: 'documentation',
      description: '文档生成',
      category: '文档',
      variables: ['file_path', 'doc_type']
    },
    {
      name: 'api-design',
      description: 'API 设计',
      category: '设计',
      variables: ['api_name', 'endpoints']
    },
    {
      name: 'bug-fix',
      description: 'Bug 修复',
      category: '调试',
      variables: ['description', 'error_log']
    },
    {
      name: 'feature-implementation',
      description: '功能实现',
      category: '开发',
      variables: ['feature_name', 'requirements']
    },
    {
      name: 'performance-optimization',
      description: '性能优化',
      category: '优化',
      variables: ['target_file', 'bottleneck']
    }
  ];
  
  const byCategory = {};
  templates.forEach(t => {
    if (!byCategory[t.category]) byCategory[t.category] = [];
    byCategory[t.category].push(t);
  });
  
  Object.entries(byCategory).forEach(([category, items]) => {
    console.log(chalk.bold.cyan(`\n${category}`));
    items.forEach(t => {
      console.log(`  ${chalk.white(t.name.padEnd(25))} ${chalk.gray(t.description)}`);
    });
  });
  
  console.log();
  console.log(chalk.gray('使用 ' + chalk.cyan('aid task <template-name>') + ' 生成任务'));
  console.log(chalk.gray('例如: aid task code-review\n'));
}

async function generateTask(templateName, options) {
  console.log(chalk.bold(`\n🚀 生成任务: ${templateName}\n`));
  
  // 加载模板
  const template = await loadTemplate(templateName);
  
  if (!template) {
    console.log(chalk.red(`模板 "${templateName}" 不存在`));
    console.log(chalk.gray('使用 ' + chalk.cyan('aid task --list') + ' 查看可用模板\n'));
    return;
  }
  
  // 收集变量
  let variables = {};
  
  if (options.variables) {
    try {
      variables = JSON.parse(options.variables);
    } catch (e) {
      console.log(chalk.red('变量 JSON 格式错误'));
      return;
    }
  } else {
    // 交互式收集变量
    for (const varName of template.variables) {
      const answer = await inquirer.prompt([
        {
          type: 'input',
          name: varName,
          message: `${varName}:`,
          validate: (input) => input.trim() ? true : `${varName} 不能为空`
        }
      ]);
      variables[varName] = answer[varName];
    }
  }
  
  // 生成任务内容
  const taskContent = generateTaskContent(template, variables);
  
  // 输出或执行
  if (options.output) {
    await fs.writeFile(options.output, taskContent, 'utf-8');
    console.log(chalk.green(`✓ 任务已保存到: ${options.output}\n`));
  } else {
    console.log(chalk.bold('\n生成的任务:\n'));
    console.log(chalk.white(taskContent));
    console.log();
    
    if (options.execute) {
      console.log(chalk.cyan('执行任务...'));
      // 这里可以集成到 agent-task-cli
    }
  }
}

export async function loadTemplate(name) {
  const templates = {
    'code-review': {
      name: 'code-review',
      description: '代码审查任务',
      variables: ['file_path', 'review_type'],
      template: `# 代码审查任务

## 文件
\`{file_path}\`

## 审查类型
{review_type}

## 审查清单
- [ ] 代码质量和可读性
- [ ] 潜在的 bug 和错误
- [ ] 性能问题
- [ ] 安全漏洞
- [ ] 测试覆盖率
- [ ] 文档完整性

## 注意事项
- 关注代码的可维护性
- 检查是否有重复代码
- 验证错误处理是否完善
- 评估代码复杂度`
    },
    
    'refactor': {
      name: 'refactor',
      description: '重构任务',
      variables: ['file_path', 'refactor_goal'],
      template: `# 重构任务

## 文件
\`{file_path}\`

## 重构目标
{refactor_goal}

## 重构步骤
1. 分析当前代码结构
2. 识别重构点
3. 设计新的结构
4. 实施重构
5. 验证功能不变
6. 更新测试

## 重构原则
- 保持功能不变
- 小步前进
- 持续测试
- 保持代码可读性`
    },
    
    'test-generation': {
      name: 'test-generation',
      description: '测试生成',
      variables: ['file_path', 'test_framework'],
      template: `# 测试生成任务

## 目标文件
\`{file_path}\`

## 测试框架
{test_framework}

## 测试范围
- 单元测试
- 边界条件测试
- 异常处理测试
- 集成测试（如需要）

## 测试要求
- 覆盖率目标: 80%+
- 包含正面和负面测试
- 清晰的测试描述
- 独立的测试用例`
    },
    
    'documentation': {
      name: 'documentation',
      description: '文档生成',
      variables: ['file_path', 'doc_type'],
      template: `# 文档生成任务

## 目标
\`{file_path}\`

## 文档类型
{doc_type}

## 文档结构
- 概述/简介
- 安装/使用说明
- API 参考
- 示例代码
- 常见问题
- 更新日志

## 文档要求
- 清晰易懂
- 包含示例
- 保持更新
- 格式规范`
    },
    
    'api-design': {
      name: 'api-design',
      description: 'API 设计',
      variables: ['api_name', 'endpoints'],
      template: `# API 设计任务

## API 名称
{api_name}

## 端点列表
{endpoints}

## 设计原则
- RESTful 设计
- 版本控制
- 统一的响应格式
- 完善的错误处理
- 认证和授权
- 文档化

## 交付物
- API 规范文档
- 请求/响应示例
- 错误码列表
- 认证说明`
    },
    
    'bug-fix': {
      name: 'bug-fix',
      description: 'Bug 修复',
      variables: ['description', 'error_log'],
      template: `# Bug 修复任务

## 问题描述
{description}

## 错误日志
\`\`\`
{error_log}
\`\`\`

## 修复流程
1. 重现问题
2. 定位根因
3. 设计修复方案
4. 实施修复
5. 添加测试
6. 验证修复
7. 代码审查

## 注意事项
- 不要引入新 bug
- 添加回归测试
- 更新相关文档`
    },
    
    'feature-implementation': {
      name: 'feature-implementation',
      description: '功能实现',
      variables: ['feature_name', 'requirements'],
      template: `# 功能实现任务

## 功能名称
{feature_name}

## 需求
{requirements}

## 实现步骤
1. 需求分析
2. 技术设计
3. 编码实现
4. 单元测试
5. 集成测试
6. 代码审查
7. 文档更新

## 验收标准
- 功能完整
- 测试通过
- 代码质量达标
- 文档完善`
    },
    
    'performance-optimization': {
      name: 'performance-optimization',
      description: '性能优化',
      variables: ['target_file', 'bottleneck'],
      template: `# 性能优化任务

## 目标文件
\`{target_file}\`

## 性能瓶颈
{bottleneck}

## 优化步骤
1. 性能分析
2. 识别瓶颈
3. 设计优化方案
4. 实施优化
5. 性能测试
6. 对比结果

## 优化原则
- 先测量，后优化
- 保持代码可读性
- 权衡时间和空间
- 记录优化效果`
    }
  };
  
  return templates[name];
}

export function generateTaskContent(template, variables) {
  let content = template.template;
  
  Object.entries(variables).forEach(([key, value]) => {
    // Function replacer: prevents `$&`, `$'`, "$`" in values from being
    // interpreted as replacement patterns and corrupting the output
    content = content.replace(new RegExp(`{${key}}`, 'g'), () => String(value));
  });
  
  return content;
}
