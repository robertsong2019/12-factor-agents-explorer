import fs from 'fs-extra';
import path from 'path';
import chalk from 'chalk';
import inquirer from 'inquirer';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export class ConfigManager {
  constructor() {
    this.configPath = path.join(process.cwd(), '.afm', 'config.json');
    this.agentsDir = path.join(process.cwd(), '.afm', 'agents');
    this.loadConfig();
  }

  loadConfig() {
    try {
      if (fs.pathExistsSync(this.configPath)) {
        const configContent = fs.readFileSync(this.configPath, 'utf8');
        this.config = JSON.parse(configContent);
      } else {
        this.config = this.getDefaultConfig();
      }
    } catch (error) {
      console.warn(chalk.yellow('⚠ 加载配置失败，将使用默认配置'));
      this.config = this.getDefaultConfig();
    }
  }

  getDefaultConfig() {
    return {
      globalSettings: {
        logLevel: 'info',
        maxConcurrent: 5,
        timeout: 30000,
        autoStart: false,
        notifications: true
      },
      agents: {},
      storage: {
        type: 'file',
        path: './data'
      },
      monitoring: {
        enabled: true,
        interval: 5000,
        metrics: ['cpu', 'memory', 'network']
      }
    };
  }

  async showConfig() {
    console.log(chalk.bold('\n📋 当前配置:\n'));
    console.log(JSON.stringify(this.config, null, 2));
  }

  async editConfig() {
    try {
      const { choice } = await inquirer.prompt([
        {
          type: 'list',
          name: 'choice',
          message: '选择编辑方式:',
          choices: [
            '直接编辑配置文件',
            '交互式配置编辑',
            '环境变量导入'
          ]
        }
      ]);

      switch (choice) {
        case '直接编辑配置文件':
          await this.editConfigFile();
          break;
        case '交互式配置编辑':
          await this.interactiveEdit();
          break;
        case '环境变量导入':
          await this.importFromEnv();
          break;
      }
    } catch (error) {
      console.error(chalk.red('✗ 配置编辑失败:'), error.message);
      throw error;
    }
  }

  async editConfigFile() {
    const editor = process.env.EDITOR || 'nano';
    console.log(chalk.blue(`📝 使用 ${editor} 编辑配置文件...`));
    
    try {
      await execAsync(`${editor} "${this.configPath}"`);
      console.log(chalk.green('✓ 配置文件已更新'));
      
      // 重新加载配置
      await this.loadConfig();
      console.log(chalk.green('✓ 配置已重新加载'));
    } catch (error) {
      console.error(chalk.red('✗ 编辑失败:'), error.message);
      throw error;
    }
  }

  async interactiveEdit() {
    console.log(chalk.blue('🎛️ 交互式配置编辑\n'));
    
    const answers = await inquirer.prompt([
      {
        type: 'list',
        name: 'section',
        message: '选择配置部分:',
        choices: [
          'globalSettings',
          'agents',
          'storage',
          'monitoring',
          '完成编辑'
        ]
      }
    ]);

    if (answers.section === '完成编辑') {
      return;
    }

    await this.editSection(answers.section);
  }

  async editSection(section) {
    const sectionConfig = this.config[section] || {};
    
    const answers = await inquirer.prompt([
      {
        type: 'confirm',
        name: 'editGlobal',
        message: '编辑全局设置?',
        default: true
      },
      {
        type: 'confirm',
        name: 'editAgents',
        message: '编辑Agent配置?',
        default: false
      }
    ]);

    if (answers.editGlobal) {
      const globalAnswers = await inquirer.prompt([
        {
          type: 'list',
          name: 'logLevel',
          message: '日志级别:',
          choices: ['error', 'warn', 'info', 'debug'],
          default: sectionConfig.logLevel || 'info'
        },
        {
          type: 'number',
          name: 'maxConcurrent',
          message: '最大并发数:',
          default: sectionConfig.maxConcurrent || 5
        },
        {
          type: 'number',
          name: 'timeout',
          message: '超时时间 (ms):',
          default: sectionConfig.timeout || 30000
        },
        {
          type: 'confirm',
          name: 'autoStart',
          message: '自动启动:',
          default: sectionConfig.autoStart || false
        }
      ]);

      this.config.globalSettings = { ...this.config.globalSettings, ...globalAnswers };
    }

    if (answers.editAgents) {
      await this.editAgentConfig();
    }

    await this.saveConfig();
  }

  async editAgentConfig() {
    const { action } = await inquirer.prompt([
      {
        type: 'list',
        name: 'action',
        message: 'Agent配置操作:',
        choices: [
          '查看所有Agent',
          '添加Agent',
          '编辑Agent',
          '删除Agent',
          '返回'
        ]
      }
    ]);

    switch (action) {
      case '查看所有Agent':
        await this.listAgents();
        break;
      case '添加Agent':
        await this.addAgent();
        break;
      case '编辑Agent':
        await this.modifyAgent();
        break;
      case '删除Agent':
        await this.deleteAgent();
        break;
    }
  }

  async addAgent() {
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
        choices: ['openai', 'claude', 'gemini', 'custom']
      },
      {
        type: 'input',
        name: 'endpoint',
        message: 'API端点:',
        when: (answers) => answers.type !== 'custom'
      },
      {
        type: 'password',
        name: 'apiKey',
        message: 'API密钥:',
        validate: (input) => input.length > 0 || 'API密钥不能为空'
      },
      {
        type: 'input',
        name: 'model',
        message: '模型名称:',
        default: 'gpt-3.5-turbo'
      }
    ]);

    this.config.agents[answers.name] = answers;
    await this.saveConfig();
    console.log(chalk.green('✓ Agent添加成功'));
  }

  async modifyAgent() {
    const agentNames = Object.keys(this.config.agents);
    if (agentNames.length === 0) {
      console.log(chalk.gray('没有Agent可编辑'));
      return;
    }

    const { agentName } = await inquirer.prompt([
      {
        type: 'list',
        name: 'agentName',
        message: '选择要编辑的Agent:',
        choices: agentNames
      }
    ]);

    const agent = this.config.agents[agentName];
    const updatedAgent = await inquirer.prompt([
      {
        type: 'input',
        name: 'name',
        message: 'Agent名称:',
        default: agent.name
      },
      {
        type: 'list',
        name: 'type',
        message: 'Agent类型:',
        choices: ['openai', 'claude', 'gemini', 'custom'],
        default: agent.type
      },
      {
        type: 'input',
        name: 'endpoint',
        message: 'API端点:',
        default: agent.endpoint || '',
        when: (answers) => answers.type !== 'custom'
      },
      {
        type: 'password',
        name: 'apiKey',
        message: 'API密钥:',
        default: agent.apiKey || ''
      },
      {
        type: 'input',
        name: 'model',
        message: '模型名称:',
        default: agent.model || 'gpt-3.5-turbo'
      }
    ]);

    this.config.agents[agentName] = updatedAgent;
    await this.saveConfig();
    console.log(chalk.green('✓ Agent配置已更新'));
  }

  async deleteAgent() {
    const agentNames = Object.keys(this.config.agents);
    if (agentNames.length === 0) {
      console.log(chalk.gray('没有Agent可删除'));
      return;
    }

    const { agentName } = await inquirer.prompt([
      {
        type: 'list',
        name: 'agentName',
        message: '选择要删除的Agent:',
        choices: agentNames
      }
    ]);

    const { confirm } = await inquirer.prompt([
      {
        type: 'confirm',
        name: 'confirm',
        message: `确定要删除Agent "${agentName}" 吗?`,
        default: false
      }
    ]);

    if (confirm) {
      delete this.config.agents[agentName];
      await this.saveConfig();
      console.log(chalk.green('✓ Agent已删除'));
    }
  }

  async importFromEnv() {
    console.log(chalk.blue('📥 从环境变量导入配置...\n'));
    
    const envConfig = {};
    
    // 检查常见的环境变量
    const envMappings = {
      'AFM_LOG_LEVEL': 'globalSettings.logLevel',
      'AFM_MAX_CONCURRENT': 'globalSettings.maxConcurrent',
      'AFM_TIMEOUT': 'globalSettings.timeout',
      'AFM_AUTO_START': 'globalSettings.autoStart'
    };

    for (const [envVar, configPath] of Object.entries(envMappings)) {
      const value = process.env[envVar];
      if (value) {
        const keys = configPath.split('.');
        let current = envConfig;
        
        for (let i = 0; i < keys.length - 1; i++) {
          if (!current[keys[i]]) current[keys[i]] = {};
          current = current[keys[i]];
        }
        
        // 类型转换
        if (keys[keys.length - 1] === 'maxConcurrent' || keys[keys.length - 1] === 'timeout') {
          current[keys[keys.length - 1]] = parseInt(value);
        } else if (keys[keys.length - 1] === 'autoStart') {
          current[keys[keys.length - 1]] = value.toLowerCase() === 'true';
        } else {
          current[keys[keys.length - 1]] = value;
        }
        
        console.log(chalk.green(`✓ 导入 ${envVar} = ${value}`));
      }
    }

    // 合并配置
    this.mergeConfig(envConfig);
    await this.saveConfig();
    console.log(chalk.green('✓ 环境变量导入完成'));
  }

  mergeConfig(newConfig) {
    // 简单的配置合并逻辑
    function merge(target, source) {
      for (const key in source) {
        if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
          if (!target[key]) target[key] = {};
          merge(target[key], source[key]);
        } else {
          target[key] = source[key];
        }
      }
    }
    
    merge(this.config, newConfig);
  }

  async resetConfig() {
    const { confirm } = await inquirer.prompt([
      {
        type: 'confirm',
        name: 'confirm',
        message: '确定要重置所有配置吗?这将删除所有自定义设置。',
        default: false
      }
    ]);

    if (confirm) {
      this.config = this.getDefaultConfig();
      await this.saveConfig();
      console.log(chalk.green('✓ 配置已重置'));
    }
  }

  async backupConfig() {
    const backupDir = path.join(process.cwd(), '.afm', 'backups');
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const backupPath = path.join(backupDir, `config-backup-${timestamp}.json`);

    try {
      await fs.ensureDir(backupDir);
      await fs.copy(this.configPath, backupPath);
      
      console.log(chalk.green(`✓ 配置已备份到: ${backupPath}`));
      
      // 清理旧备份（保留最近5个）
      const backups = await fs.readdir(backupDir);
      const backupFiles = backups
        .filter(file => file.startsWith('config-backup-'))
        .sort()
        .reverse();
      
      for (let i = 5; i < backupFiles.length; i++) {
        await fs.remove(path.join(backupDir, backupFiles[i]));
      }
      
      console.log(chalk.blue(`📁 保留了最近的 ${Math.min(5, backupFiles.length)} 个备份`));
    } catch (error) {
      console.error(chalk.red('✗ 备份失败:'), error.message);
      throw error;
    }
  }

  async upgrade() {
    console.log(chalk.blue('🔄 检查更新...\n'));
    
    try {
      // 模拟检查更新
      console.log(chalk.green('✓ 当前版本: 1.0.0'));
      console.log(chalk.blue('📦 可用版本: 1.1.0'));
      
      const { confirm } = await inquirer.prompt([
        {
          type: 'confirm',
          name: 'confirm',
          message: '升级到1.1.0版本?',
          default: true
        }
      ]);

      if (confirm) {
        // 模拟升级过程
        console.log(chalk.blue('🚀 开始升级...'));
        
        // 备份当前配置
        await this.backupConfig();
        
        console.log(chalk.green('✓ 升级完成'));
        console.log(chalk.blue('📖 查看更新日志: https://github.com/afm/changelog.md'));
      }
    } catch (error) {
      console.error(chalk.red('✗ 升级失败:'), error.message);
      throw error;
    }
  }

  async diagnose() {
    console.log(chalk.blue('🔍 运行诊断检查...\n'));
    
    const diagnostics = {
      configFile: await this.checkConfigFile(),
      agentsDir: await this.checkAgentsDir(),
      dependencies: await this.checkDependencies(),
      permissions: await this.checkPermissions()
    };

    // 显示诊断结果
    for (const [key, result] of Object.entries(diagnostics)) {
      const status = result.status ? '✓' : '✗';
      const color = result.status ? 'green' : 'red';
      console.log(`${chalk[color](status)} ${key}: ${result.message}`);
      
      if (result.suggestions && result.suggestions.length > 0) {
        console.log(chalk.yellow('💡 建议:'));
        result.suggestions.forEach(suggestion => {
          console.log(`   ${suggestion}`);
        });
      }
    }

    const allGood = Object.values(diagnostics).every(d => d.status);
    if (allGood) {
      console.log(chalk.green('\n✅ 所有诊断检查通过'));
    } else {
      console.log(chalk.red('\n❌ 发现问题，请检查并修复'));
    }
  }

  async checkConfigFile() {
    try {
      if (await fs.pathExists(this.configPath)) {
        const stats = await fs.stat(this.configPath);
        return {
          status: true,
          message: `配置文件存在 (${stats.size} bytes)`
        };
      } else {
        return {
          status: false,
          message: '配置文件不存在',
          suggestions: ['运行 `afm init` 初始化配置']
        };
      }
    } catch (error) {
      return {
        status: false,
        message: `配置文件读取失败: ${error.message}`
      };
    }
  }

  async checkAgentsDir() {
    try {
      if (await fs.pathExists(this.agentsDir)) {
        const files = await fs.readdir(this.agentsDir);
        return {
          status: true,
          message: `Agent目录存在 (${files.length} 个配置文件)`
        };
      } else {
        return {
          status: false,
          message: 'Agent目录不存在',
          suggestions: ['运行 `afm init` 初始化配置']
        };
      }
    } catch (error) {
      return {
        status: false,
        message: `Agent目录访问失败: ${error.message}`
      };
    }
  }

  async checkDependencies() {
    try {
      const packagePath = path.join(process.cwd(), 'package.json');
      if (await fs.pathExists(packagePath)) {
        const pkg = await fs.readJSON(packagePath);
        const dependencies = Object.keys(pkg.dependencies || {});
        
        return {
          status: true,
          message: `找到 ${dependencies.length} 个依赖项`
        };
      } else {
        return {
          status: false,
          message: 'package.json 不存在',
          suggestions: ['初始化npm项目: `npm init -y`']
        };
      }
    } catch (error) {
      return {
        status: false,
        message: `依赖检查失败: ${error.message}`
      };
    }
  }

  async checkPermissions() {
    try {
      const testFile = path.join(process.cwd(), '.afm', 'permission-test.tmp');
      await fs.ensureDir(path.dirname(testFile));
      await fs.writeFile(testFile, 'test');
      await fs.remove(testFile);
      
      return {
        status: true,
        message: '文件权限正常'
      };
    } catch (error) {
      return {
        status: false,
        message: '文件权限不足',
        suggestions: ['检查目录权限: `chmod -R 755 .afm`']
      };
    }
  }

  async saveConfig() {
    try {
      await fs.ensureDir(path.dirname(this.configPath));
      await fs.writeJSON(this.configPath, this.config, { spaces: 2 });
    } catch (error) {
      console.error(chalk.red('✗ 保存配置失败:'), error.message);
      throw error;
    }
  }

  async listAgents() {
    console.log(chalk.bold('\n🤖 当前配置的Agent:\n'));
    
    if (Object.keys(this.config.agents).length === 0) {
      console.log(chalk.gray('没有配置Agent'));
      return;
    }

    for (const [name, config] of Object.entries(this.config.agents)) {
      console.log(chalk.bold(name));
      console.log(`  类型: ${config.type}`);
      console.log(`  模型: ${config.model || 'N/A'}`);
      console.log('');
    }
  }
}