import fs from 'fs-extra';
import path from 'path';
import chalk from 'chalk';
import { exec, spawn } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export class AgentManager {
  constructor() {
    this.agentsDir = path.join(process.cwd(), '.afm', 'agents');
    this.config = null;
    this.loadConfig();
  }

  loadConfig() {
    try {
      const configPath = path.join(process.cwd(), '.afm', 'config.json');
      if (fs.pathExistsSync(configPath)) {
        const configContent = fs.readFileSync(configPath, 'utf8');
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
      agents: {},
      globalSettings: {
        logLevel: 'info',
        maxConcurrent: 5,
        timeout: 30000
      }
    };
  }

  async init(force = false) {
    const afmDir = path.join(process.cwd(), '.afm');
    
    if (await fs.pathExists(afmDir) && !force) {
      throw new Error('AFM配置已存在，使用 --force 强制覆盖');
    }

    await fs.ensureDir(afmDir);
    await fs.ensureDir(path.join(afmDir, 'agents'));
    await fs.ensureDir(path.join(afmDir, 'logs'));
    await fs.ensureDir(path.join(afmDir, 'backups'));

    const defaultConfig = this.getDefaultConfig();
    await fs.writeJSON(path.join(afmDir, 'config.json'), defaultConfig, { spaces: 2 });

    // 创建示例Agent配置
    const sampleAgent = {
      name: 'sample-agent',
      type: 'openai',
      endpoint: 'https://api.openai.com/v1/chat/completions',
      apiKey: 'your-api-key-here',
      model: 'gpt-3.5-turbo',
      maxTokens: 4000,
      temperature: 0.7,
      enabled: true
    };

    await fs.writeJSON(path.join(afmDir, 'agents', 'sample-agent.json'), sampleAgent, { spaces: 2 });

    console.log(chalk.green('✓ AFM初始化完成'));
    console.log(chalk.blue('💡 编辑 .afm/agents/sample-agent.json 来配置你的第一个Agent'));
  }

  async listAgents() {
    const agentsDir = path.join(this.agentsDir);
    if (!await fs.pathExists(agentsDir)) {
      console.log(chalk.gray('没有找到Agent配置文件（请先运行 afm init）'));
      return;
    }
    const agentFiles = await fs.readdir(agentsDir);
    
    console.log(chalk.bold('\n🤖 Agent列表:\n'));
    
    if (agentFiles.length === 0) {
      console.log(chalk.gray('没有找到Agent配置文件'));
      return;
    }

    for (const file of agentFiles) {
      if (file.endsWith('.json')) {
        const agentPath = path.join(agentsDir, file);
        const agentConfig = await fs.readJSON(agentPath);
        
        const status = await this.getAgentStatus(agentConfig.name);
        const statusColor = status.running ? 'green' : 'red';
        const statusIcon = status.running ? '▶' : '⏸';
        
        console.log(`${chalk.bold(agentConfig.name)} ${chalk[statusColor](statusIcon)}`);
        console.log(`  类型: ${agentConfig.type}`);
        console.log(`  模型: ${agentConfig.model}`);
        console.log(`  状态: ${status.running ? '运行中' : '已停止'}`);
        console.log(`  PID: ${status.pid || 'N/A'}`);
        console.log('');
      }
    }
  }

  async addAgent(agentConfig) {
    const agentPath = path.join(this.agentsDir, `${agentConfig.name}.json`);
    
    // 检查Agent是否已存在
    if (await fs.pathExists(agentPath)) {
      throw new Error(`Agent "${agentConfig.name}" 已存在`);
    }

    // 创建Agent配置
    const agent = {
      name: agentConfig.name,
      type: agentConfig.type,
      endpoint: agentConfig.endpoint,
      apiKey: agentConfig.apiKey,
      model: agentConfig.model,
      maxTokens: agentConfig.maxTokens,
      temperature: agentConfig.temperature || 0.7,
      enabled: true,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    await fs.writeJSON(agentPath, agent, { spaces: 2 });
    
    // 更新主配置
    if (!this.config.agents) {
      this.config.agents = {};
    }
    this.config.agents[agentConfig.name] = agent;
    await this.saveConfig();
  }

  async startAgent(agentName) {
    const agentPath = path.join(this.agentsDir, `${agentName}.json`);
    
    if (!await fs.pathExists(agentPath)) {
      throw new Error(`Agent "${agentName}" 不存在`);
    }

    const agentConfig = await fs.readJSON(agentPath);
    
    // 检查是否已在运行
    const status = await this.getAgentStatus(agentName);
    if (status.running) {
      console.log(chalk.yellow(`⚠ Agent "${agentName}" 已在运行中 (PID: ${status.pid})`));
      return;
    }

    console.log(chalk.blue(`🚀 启动Agent "${agentName}"...`));

    try {
      // 创建启动脚本
      const scriptPath = path.join(process.cwd(), '.afm', 'scripts', `start-${agentName}.js`);
      await fs.ensureDir(path.dirname(scriptPath));
      
      const runnerPath = new URL('../lib/agent-runner.js', import.meta.url).href;
      const script = `
import { AgentRunner } from '${runnerPath}';

const runner = new AgentRunner({
  name: '${agentName}',
  config: ${JSON.stringify(agentConfig, null, 2)}
});

runner.start().catch(console.error);
`;

      await fs.writeFile(scriptPath, script);
      
      // 启动Agent进程（detached + unref，exec 不返回 pid）
      const child = spawn('node', [scriptPath], {
        detached: true,
        stdio: 'ignore'
      });
      child.unref();
      const pid = child.pid;

      // 记录PID
      const agentPidPath = path.join(process.cwd(), '.afm', 'pids', `${agentName}.pid`);
      await fs.ensureDir(path.dirname(agentPidPath));
      await fs.writeFile(agentPidPath, pid.toString());

      console.log(chalk.green(`✓ Agent "${agentName}" 启动成功 (PID: ${pid})`));
    } catch (error) {
      console.error(chalk.red(`✗ 启动失败: ${error.message}`));
      throw error;
    }
  }

  async stopAgent(agentName) {
    const agentPidPath = path.join(process.cwd(), '.afm', 'pids', `${agentName}.pid`);
    
    if (!await fs.pathExists(agentPidPath)) {
      console.log(chalk.yellow(`⚠ Agent "${agentName}" 未运行`));
      return;
    }

    try {
      const pid = await fs.readFile(agentPidPath, 'utf8');
      
      // 检查进程是否仍在运行
      try {
        await execAsync(`kill -0 ${pid}`);
        // 终止进程
        await execAsync(`kill ${pid}`);
        console.log(chalk.green(`✓ Agent "${agentName}" 已停止`));
      } catch (error) {
        if (error.signal === 'SIGTERM' || error.signal === 'SIGKILL') {
          console.log(chalk.green(`✓ Agent "${agentName}" 已停止`));
        } else {
          console.log(chalk.yellow(`⚠ Agent "${agentName}" 进程不存在，清理PID文件`));
        }
      }
      
      // 清理PID文件
      await fs.remove(agentPidPath);
    } catch (error) {
      console.error(chalk.red(`✗ 停止失败: ${error.message}`));
      throw error;
    }
  }

  async getAgentStatus(agentName) {
    const agentPidPath = path.join(process.cwd(), '.afm', 'pids', `${agentName}.pid`);
    
    if (!await fs.pathExists(agentPidPath)) {
      return { running: false, pid: null, uptime: 0 };
    }

    try {
      const pid = (await fs.readFile(agentPidPath, 'utf8')).trim();
      
      // 检查进程是否仍在运行
      await execAsync(`kill -0 ${pid}`);
      
      // 获取进程运行时间
      let uptime = 0;
      try {
        const { stdout } = await execAsync(`ps -o etime= -p ${pid}`);
        const timeStr = stdout.trim();
        if (timeStr) {
          uptime = this.parseUptime(timeStr);
        }
      } catch (error) {
        console.warn(chalk.yellow(`⚠ 无法获取进程运行时间: ${error.message}`));
      }
      
      return { running: true, pid, uptime };
    } catch (error) {
      console.error('DBG getAgentStatus catch:', error.message);
      // 进程不存在，清理PID文件
      await fs.remove(agentPidPath);
      return { running: false, pid: null, uptime: 0 };
    }
  }

  parseUptime(timeStr) {
    // 解析 ps 命令的 etime 格式: DD-HH:MM:SS 或 HH:MM:SS 或 MM:SS 或 SS
    const parts = timeStr.split('-');
    let days = 0;
    let timePart;
    
    if (parts.length > 1) {
      days = parseInt(parts[0]);
      timePart = parts[1];
    } else {
      timePart = parts[0];
    }
    
    const fields = timePart.split(':').map(Number);
    let hours = 0, minutes = 0, seconds = 0;
    if (fields.length === 3) {
      [hours, minutes, seconds] = fields;
    } else if (fields.length === 2) {
      [minutes, seconds] = fields;
    } else {
      [seconds] = fields;
    }
    
    return days * 86400 + hours * 3600 + minutes * 60 + (seconds || 0);
  }

  async saveConfig() {
    const configPath = path.join(process.cwd(), '.afm', 'config.json');
    await fs.writeJSON(configPath, this.config, { spaces: 2 });
  }
}