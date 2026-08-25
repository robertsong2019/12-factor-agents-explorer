#!/usr/bin/env node
/**
 * Code Quality Checker - 代码质量检查工具
 * 统一检查代码风格、复杂度、安全等问题
 */

import { program } from 'commander';
import chalk from 'chalk';
import fs from 'fs-extra';
import path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';
import { realpathSync } from 'fs';
import { fileURLToPath } from 'url';

const execAsync = promisify(exec);

program
  .name('cqc')
  .description('代码质量检查工具 - 统一检查代码风格、复杂度、安全等问题')
  .version('1.0.0');

program
  .command('check')
  .description('检查指定目录的代码质量')
  .argument('[path]', '检查目录路径', process.cwd())
  .option('-f, --format <format>', '输出格式', 'console')
  .option('-o, --output <file>', '输出文件路径')
  .option('--eslint', '运行ESLint检查')
  .option('--complexity', '检查代码复杂度')
  .option('--security', '检查安全问题')
  .option('--dependencies', '检查依赖安全')
  .option('--all', '运行所有检查')
  .action(async (targetPath, options) => {
    try {
      console.log(chalk.blue('🔍 开始代码质量检查...'));

      const results = {
        path: targetPath,
        timestamp: new Date().toISOString(),
        checks: {}
      };

      // 如果没有指定具体检查,默认运行所有
      const runAll = options.all || (!options.eslint && !options.complexity && !options.security && !options.dependencies);

      // ESLint 检查
      if (runAll || options.eslint) {
        results.checks.eslint = await runESLintCheck(targetPath);
      }

      // 代码复杂度检查
      if (runAll || options.complexity) {
        results.checks.complexity = await runComplexityCheck(targetPath);
      }

      // 安全检查
      if (runAll || options.security) {
        results.checks.security = await runSecurityCheck(targetPath);
      }

      // 依赖安全检查
      if (runAll || options.dependencies) {
        results.checks.dependencies = await runDependencyCheck(targetPath);
      }

      // 输出结果
      outputResults(results, options.format, options.output);

    } catch (error) {
      console.error(chalk.red('❌ 检查失败:'), error.message);
      process.exit(1);
    }
  });

program
  .command('init')
  .description('初始化代码质量配置文件')
  .option('-f, --force', '强制覆盖现有配置')
  .action(async (options) => {
    try {
      console.log(chalk.blue('🚀 初始化代码质量配置...'));

      const configTemplates = {
        '.eslintrc.js': `module.exports = {
  env: {
    browser: true,
    es2021: true,
    node: true
  },
  extends: [
    'eslint:recommended',
    '@typescript-eslint/recommended'
  ],
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 12,
    sourceType: 'module'
  },
  rules: {
    'indent': ['error', 2],
    'linebreak-style': ['error', 'unix'],
    'quotes': ['error', 'single'],
    'semi': ['error', 'always'],
    'no-unused-vars': 'warn',
    'no-console': 'warn'
  }
};`,
        '.complexityrc.json': `{
  "maxComplexity": 10,
  "maxDepth": 4,
  "maxConditions": 5,
  "ignoreFiles": [
    "**/*.test.js",
    "**/*.spec.js",
    "**/node_modules/**"
  ],
  "fileExtensions": [".js", ".ts", ".jsx", ".tsx"]
}`,
        '.securityrc.json': `{
  "allowedPatterns": [
    "^\\\\$[a-zA-Z_][a-zA-Z0-9_]*$",
    "^require\\\\(''\\\\)$",
    "^console\\\\.log$"
  ],
  "blockedPatterns": [
    "eval\\\\(",
    "innerHTML",
    "document\\.write",
    "setTimeout\\s*\\(",
    "setInterval\\s*\\("
  ],
  "allowedLibraries": [
    "lodash",
    "axios",
    "express"
  ]
}`
      };

      for (const [filename, content] of Object.entries(configTemplates)) {
        const filePath = path.join(process.cwd(), filename);

        if (fs.existsSync(filePath) && !options.force) {
          console.log(chalk.yellow(`⚠️  ${filename} 已存在,使用 --force 覆盖`));
          continue;
        }

        await fs.writeFile(filePath, content);
        console.log(chalk.green(`✅ ${filename} 已创建`));
      }

      console.log(chalk.green('🎉 代码质量配置初始化完成!'));

    } catch (error) {
      console.error(chalk.red('❌ 初始化失败:'), error.message);
      process.exit(1);
    }
  });

async function runESLintCheck(targetPath) {
  console.log(chalk.yellow('📝 运行ESLint检查...'));

  try {
    // 检查是否有ESLint配置
    const hasEslint = await fs.pathExists(path.join(targetPath, '.eslintrc.js')) ||
                    await fs.pathExists(path.join(targetPath, '.eslintrc.json'));

    if (!hasEslint) {
      console.log(chalk.yellow('⚠️  未找到ESLint配置文件,跳过ESLint检查'));
      return { status: 'skipped', reason: 'No ESLint config found' };
    }

    // 运行ESLint
    const { stdout, stderr } = await execAsync(`npx eslint ${targetPath} --format json`, {
      cwd: targetPath
    });

    const results = JSON.parse(stdout);
    const errorCount = results.reduce((sum, file) => sum + file.errorCount, 0);
    const warningCount = results.reduce((sum, file) => sum + file.warningCount, 0);

    console.log(chalk.green(`✅ ESLint检查完成: ${errorCount} 错误, ${warningCount} 警告`));

    return {
      status: 'completed',
      errorCount,
      warningCount,
      files: results.length
    };

  } catch (error) {
    console.log(chalk.red(`❌ ESLint检查失败: ${error.message}`));
    return { status: 'failed', error: error.message };
  }
}

async function runComplexityCheck(targetPath) {
  console.log(chalk.yellow('🧮 运行代码复杂度检查...'));
  
  try {
    // 使用简单的复杂度分析（.complexityrc.json 可配置阈值/忽略/扩展名）
    const config = await loadComplexityConfig(targetPath);
    const maxComplexity = typeof config.maxComplexity === 'number' ? config.maxComplexity : 10;
    const ignorePatterns = (Array.isArray(config.ignoreFiles) ? config.ignoreFiles : []).map(globToRegex);
    const extRegex = (Array.isArray(config.fileExtensions) && config.fileExtensions.length > 0)
      ? new RegExp('(' + config.fileExtensions.map(e => e.replace(/[.+^${}()|[\]\\]/g, '\\$&')).join('|') + ')$')
      : /\.(js|ts|jsx|tsx)$/;

    const jsFiles = (await findJavaScriptFiles(targetPath)).filter(file => {
      if (!extRegex.test(file)) return false;
      const rel = path.relative(targetPath, file).split(path.sep).join('/');
      return !ignorePatterns.some(p => p.test(rel));
    });
    const complexityResults = [];

    for (const file of jsFiles) {
      const { complexity: score, issues } = analyzeComplexity(file);
      complexityResults.push({
        file: path.relative(targetPath, file),
        complexity: score,
        issues: issues
      });
    }

    const avgComplexity = complexityResults.reduce((sum, r) => sum + r.complexity, 0) / complexityResults.length || 0;
    const highComplexityFiles = complexityResults.filter(r => r.complexity > maxComplexity);

    console.log(chalk.green(`✅ 复杂度检查完成: 平均复杂度 ${avgComplexity.toFixed(2)}, ${highComplexityFiles.length} 个文件复杂度过高`));

    return {
      status: 'completed',
      averageComplexity: avgComplexity,
      filesAnalyzed: complexityResults.length,
      highComplexityFiles: highComplexityFiles.length,
      results: complexityResults
    };

  } catch (error) {
    console.log(chalk.red(`❌ 复杂度检查失败: ${error.message}`));
    return { status: 'failed', error: error.message };
  }
}

async function runSecurityCheck(targetPath) {
  console.log(chalk.yellow('🔒 运行安全检查...'));

  try {
    const jsFiles = await findJavaScriptFiles(targetPath);
    const securityResults = [];

    for (const file of jsFiles) {
      const securityIssues = await analyzeSecurity(file);
      if (securityIssues.length > 0) {
        securityResults.push({
          file: path.relative(targetPath, file),
          issues: securityIssues
        });
      }
    }

    const totalIssues = securityResults.reduce((sum, r) => sum + r.issues.length, 0);

    console.log(chalk.green(`✅ 安全检查完成: 发现 ${totalIssues} 个安全问题`));

    return {
      status: 'completed',
      totalIssues,
      filesWithIssues: securityResults.length,
      results: securityResults
    };

  } catch (error) {
    console.log(chalk.red(`❌ 安全检查失败: ${error.message}`));
    return { status: 'failed', error: error.message };
  }
}

async function runDependencyCheck(targetPath) {
  console.log(chalk.yellow('📦 运行依赖安全检查...'));

  try {
    // 检查package.json
    const packageJsonPath = path.join(targetPath, 'package.json');
    if (!await fs.pathExists(packageJsonPath)) {
      console.log(chalk.yellow('⚠️  未找到package.json,跳过依赖检查'));
      return { status: 'skipped', reason: 'No package.json found' };
    }

    const packageJson = await fs.readJson(packageJsonPath);
    const dependencies = { ...packageJson.dependencies, ...packageJson.devDependencies };

    // 检查过时依赖
    const outdatedDeps = await checkOutdatedDependencies(targetPath);

    console.log(chalk.green(`✅ 依赖检查完成: ${Object.keys(dependencies).length} 个依赖,${outdatedDeps.length} 个需要更新`));

    return {
      status: 'completed',
      totalDependencies: Object.keys(dependencies).length,
      outdatedDependencies: outdatedDeps.length,
      dependencies: Object.keys(dependencies),
      outdated: outdatedDeps
    };

  } catch (error) {
    console.log(chalk.red(`❌ 依赖检查失败: ${error.message}`));
    return { status: 'failed', error: error.message };
  }
}

function outputResults(results, format, outputFile) {
  switch (format) {
    case 'json':
      const jsonOutput = JSON.stringify(results, null, 2);
      if (outputFile) {
        fs.writeFileSync(outputFile, jsonOutput);
        console.log(chalk.green(`📄 结果已保存到: ${outputFile}`));
      } else {
        console.log(jsonOutput);
      }
      break;

    case 'console':
    default:
      printConsoleResults(results);
      if (outputFile) {
        fs.writeFileSync(outputFile, JSON.stringify(results, null, 2));
        console.log(chalk.green(`📄 结果已保存到: ${outputFile}`));
      }
      break;
  }
}

function printConsoleResults(results) {
  console.log(chalk.blue('\\n📊 代码质量检查报告'));
  console.log(chalk.blue('═'.repeat(50)));

  const { checks } = results;

  for (const [checkName, checkResult] of Object.entries(checks)) {
    console.log(chalk.yellow(`\\n${checkName.toUpperCase()}`));

    if (checkResult.status === 'completed') {
      switch (checkName) {
        case 'eslint':
          console.log(`  状态: ${chalk.green('✅ 完成')}`);
          console.log(`  错误: ${checkResult.errorCount}`);
          console.log(`  警告: ${checkResult.warningCount}`);
          console.log(`  检查文件: ${checkResult.files}`);
          break;

        case 'complexity':
          console.log(`  状态: ${chalk.green('✅ 完成')}`);
          console.log(`  平均复杂度: ${checkResult.averageComplexity.toFixed(2)}`);
          console.log(`  分析文件: ${checkResult.filesAnalyzed}`);
          console.log(`  高复杂度文件: ${checkResult.highComplexityFiles}`);
          break;

        case 'security':
          console.log(`  状态: ${chalk.green('✅ 完成')}`);
          console.log(`  安全问题: ${checkResult.totalIssues}`);
          console.log(`  问题文件: ${checkResult.filesWithIssues}`);
          break;

        case 'dependencies':
          console.log(`  状态: ${chalk.green('✅ 完成')}`);
          console.log(`  总依赖数: ${checkResult.totalDependencies}`);
          console.log(`  需更新依赖: ${checkResult.outdatedDependencies}`);
          break;
      }
    } else if (checkResult.status === 'skipped') {
      console.log(`  状态: ${chalk.yellow('⏭️  跳过')} - ${checkResult.reason}`);
    } else {
      console.log(`  状态: ${chalk.red('❌ 失败')} - ${checkResult.error}`);
    }
  }

  // 计算总体健康分数
  const healthScore = calculateHealthScore(checks);
  console.log(`\\n${chalk.blue('总体健康分数')}: ${healthScore}/100`);

  if (healthScore >= 80) {
    console.log(chalk.green('🎉 代码质量良好!'));
  } else if (healthScore >= 60) {
    console.log(chalk.yellow('⚠️  代码质量一般,建议改进'));
  } else {
    console.log(chalk.red('❌ 代码质量较差,需要重点关注'));
  }
}

function calculateHealthScore(checks) {
  let totalScore = 0;
  let checkCount = 0;

  for (const [checkName, checkResult] of Object.entries(checks)) {
    if (checkResult.status === 'completed') {
      let score = 0;

      switch (checkName) {
        case 'eslint':
          score = Math.max(0, 100 - (checkResult.errorCount * 5) - (checkResult.warningCount * 2));
          break;

        case 'complexity':
          score = Math.max(0, 100 - (checkResult.highComplexityFiles * 10));
          break;

        case 'security':
          score = Math.max(0, 100 - (checkResult.totalIssues * 15));
          break;

        case 'dependencies':
          score = Math.max(0, 100 - (checkResult.outdatedDependencies * 5));
          break;
      }

      totalScore += score;
      checkCount++;
    }
  }

  return checkCount > 0 ? Math.round(totalScore / checkCount) : 0;
}

async function findJavaScriptFiles(dir) {
  const files = [];
  const entries = await fs.readdir(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);

    if (entry.isDirectory() && !entry.name.startsWith('.') && entry.name !== 'node_modules') {
      const subFiles = await findJavaScriptFiles(fullPath);
      files.push(...subFiles);
    } else if (entry.isFile() && entry.name.match(/\.(js|ts|jsx|tsx)$/)) {
      files.push(fullPath);
    }
  }

  return files;
}

function globToRegex(glob) {
  // 支持 ** 跨目录、* 单段、? 单字符的简化 glob
  let re = glob.replace(/[.+^${}()|[\]\\]/g, ch => '\\' + ch);
  re = re.replace(/\*\*/g, '\u0000');
  re = re.replace(/\*/g, '[^/]*');
  re = re.replace(/\?/g, '[^/]');
  re = re.replace(/\u0000\//g, '(?:.*/)?');
  re = re.replace(/\/\u0000/g, '/.*');
  re = re.replace(/\u0000/g, '.*');
  return new RegExp('^' + re + '$');
}

async function loadComplexityConfig(targetPath) {
  const configPath = path.join(targetPath, '.complexityrc.json');
  if (!(await fs.pathExists(configPath))) return {};
  try {
    return await fs.readJson(configPath);
  } catch {
    return {};
  }
}

function analyzeComplexity(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.split('\n');

  let complexity = 0;
  const issues = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    // 检查循环复杂度
    if (line.match(/\b(if|for|while|do|switch|case|catch)\b/)) {
      complexity++;
    }

    // 检查嵌套层次(使用原始行而非 trimmed 行)
    const indentLevel = lines[i].match(/^\s*/)?.[0].length || 0;
    if (indentLevel > 16) {
      issues.push(`第${i + 1}行: 缩进过深 (${indentLevel}级)`);
    }

    // 检查行长度
    if (line.length > 100) {
      issues.push(`第${i + 1}行: 行过长 (${line.length}字符)`);
    }
  }

  return { complexity, issues };
}

async function analyzeSecurity(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const securityIssues = [];

  // 检查常见的安全问题
  const patterns = [
    { regex: /eval\s*\(/g, issue: '使用eval函数,存在安全风险' },
    { regex: /innerHTML\s*=/g, issue: '使用innerHTML,可能存在XSS风险' },
    { regex: /document\.write\s*\(/g, issue: '使用document.write,已废弃且有安全风险' },
    { regex: /setTimeout\s*\(['"][^'"]*['"]/, issue: '使用setTimeout字符串参数,可能有安全风险' },
    { regex: /setInterval\s*\(['"][^'"]*['"]/, issue: '使用setInterval字符串参数,可能有安全风险' },
    { regex: /\$\{[^}]*\}/g, issue: '使用模板字符串拼接,注意SQL注入风险' }
  ];

  for (const pattern of patterns) {
    const matches = content.match(pattern.regex);
    if (matches) {
      securityIssues.push({
        type: 'security',
        message: pattern.issue,
        count: matches.length
      });
    }
  }

  return securityIssues;
}

async function checkOutdatedDependencies(targetPath) {
  // npm outdated exits 1 when outdated packages EXIST - stdout still carries the JSON.
  // Salvage it from the error instead of returning [].
  try {
    const { stdout } = await execAsync('npm outdated --json', { cwd: targetPath });
    const outdated = JSON.parse(stdout);
    return Object.keys(outdated);
  } catch (error) {
    if (error.stdout) {
      try {
        const outdated = JSON.parse(error.stdout);
        return Object.keys(outdated);
      } catch { /* fall through */ }
    }
    return [];
  }
}

// Export for testing
export {
  findJavaScriptFiles,
  analyzeComplexity,
  analyzeSecurity,
  calculateHealthScore,
  runESLintCheck,
  runComplexityCheck,
  runSecurityCheck,
  runDependencyCheck,
  globToRegex,
  loadComplexityConfig
};

// Only parse CLI if run directly (realpath comparison survives bin symlinks like `cqc`)
const isMain = (() => {
  try {
    return process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url);
  } catch {
    return false;
  }
})();
if (isMain) {
  program.parse();
}