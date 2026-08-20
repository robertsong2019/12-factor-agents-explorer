import fs from 'fs-extra';
import path from 'path';
import chalk from 'chalk';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export class Monitor {
  constructor() {
    this.agentsDir = path.join(process.cwd(), '.afm', 'agents');
    this.logsDir = path.join(process.cwd(), '.afm', 'logs');
    this.pidsDir = path.join(process.cwd(), '.afm', 'pids');
    this.config = null;
    this.loadConfig();
  }

  loadConfig() {
    try {
      const configPath = path.join(process.cwd(), '.afm', 'config.json');
      if (fs.pathExistsSync(configPath)) {
        const configContent = fs.readFileSync(configPath, 'utf8');
        this.config = JSON.parse(configContent);
      }
    } catch (error) {
      console.warn(chalk.yellow('⚠ 加载配置失败'));
    }
  }

  async showOverview() {
    console.log(chalk.bold('\n📊 Agent框架概览:\n'));
    
    // 获取所有Agent状态
    const agents = await this.getAllAgentsStatus();
    
    // 统计信息
    const totalAgents = agents.length;
    const runningAgents = agents.filter(a => a.running).length;
    const stoppedAgents = totalAgents - runningAgents;
    
    // 显示统计信息
    console.log(chalk.blue('📈 统计信息:'));
    console.log(`  总Agent数: ${totalAgents}`);
    console.log(`  运行中: ${runningAgents}`);
    console.log(`  已停止: ${stoppedAgents}`);
    console.log('');
    
    // 显示每个Agent的状态
    console.log(chalk.blue('🤖 Agent状态:'));
    for (const agent of agents) {
      const status = agent.running ? chalk.green('运行中') : chalk.red('已停止');
      const uptime = agent.uptime ? this.formatUptime(agent.uptime) : 'N/A';
      
      console.log(`  ${chalk.bold(agent.name)} ${status}`);
      console.log(`    PID: ${agent.pid || 'N/A'}`);
      console.log(`    运行时间: ${uptime}`);
      console.log(`    内存使用: ${agent.memory || 'N/A'}`);
      console.log('');
    }
    
    // 显示系统资源使用情况
    await this.showSystemResources();
  }

  async showDashboard() {
    console.clear();
    console.log(chalk.bold('\n🎛️ Agent框架监控面板\n'));
    console.log(chalk.blue('=' .repeat(60)));
    
    // 获取系统信息
    const systemInfo = await this.getSystemInfo();
    
    // 显示系统信息
    console.log(chalk.green('🖥️  系统信息:'));
    console.log(`  CPU使用率: ${systemInfo.cpu}%`);
    console.log(`  内存使用: ${systemInfo.memory.used} / ${systemInfo.memory.total} (${systemInfo.memory.percentage}%)`);
    console.log(`  运行时间: ${systemInfo.uptime}`);
    console.log('');
    
    // 显示Agent状态
    const agents = await this.getAllAgentsStatus();
    console.log(chalk.blue('🤖 Agent状态:'));
    
    for (const agent of agents) {
      const status = agent.running ? chalk.green('▶ 运行中') : chalk.red('⏸ 已停止');
      const uptime = agent.uptime ? this.formatUptime(agent.uptime) : 'N/A';
      const memory = agent.memory || 'N/A';
      
      console.log(`  ${agent.name} ${status}`);
      console.log(`    PID: ${agent.pid || 'N/A'}`);
      console.log(`    运行时间: ${uptime}`);
      console.log(`    内存: ${memory}`);
      console.log('');
    }
    
    // 显示最近的日志
    console.log(chalk.yellow('📝 最近日志:'));
    await this.showRecentLogs();
    
    console.log(chalk.blue('=' .repeat(60)));
    console.log(chalk.gray('按 Ctrl+C 退出监控面板'));
  }

  async showMetrics(agentName) {
    console.log(chalk.bold(`\n📊 ${agentName} 详细指标:\n`));
    
    const agentPidPath = path.join(this.pidsDir, `${agentName}.pid`);
    
    if (!await fs.pathExists(agentPidPath)) {
      console.log(chalk.red(`✗ Agent "${agentName}" 未运行`));
      return;
    }

    try {
      const pid = (await fs.readFile(agentPidPath, 'utf8')).trim();
      
      // 获取进程详细信息
      const metrics = await this.getProcessMetrics(pid);
      
      console.log(chalk.blue('📈 进程信息:'));
      console.log(`  PID: ${pid}`);
      console.log(`  CPU使用率: ${metrics.cpu}%`);
      console.log(`  内存使用: ${metrics.memory} MB`);
      console.log(`  虚拟内存: ${metrics.vmem} MB`);
      console.log(`  CPU时间: ${metrics.cpuTime}`);
      console.log('');
      
      // 获取网络信息
      console.log(chalk.blue('🌐 网络连接:'));
      const networkInfo = await this.getNetworkInfo(pid);
      console.log(networkInfo);
      
      // 获取文件描述符
      console.log(chalk.blue('📁 文件描述符:'));
      const fdInfo = await this.getFileDescriptorInfo(pid);
      console.log(fdInfo);
      
      // 获取环境变量
      console.log(chalk.blue('🔧 环境变量:'));
      const envInfo = await this.getEnvironmentInfo(pid);
      console.log(envInfo);
      
    } catch (error) {
      console.error(chalk.red('✗ 获取指标失败:'), error.message);
    }
  }

  async showLogs(agentName) {
    const logPath = path.join(this.logsDir, `${agentName}.log`);
    
    if (!await fs.pathExists(logPath)) {
      console.log(chalk.red(`✗ Agent "${agentName}" 日志文件不存在`));
      return;
    }

    try {
      const stats = await fs.stat(logPath);
      const size = stats.size;
      
      console.log(chalk.bold(`\n📝 ${agentName} 日志 (大小: ${this.formatBytes(size)})\n`));
      console.log(chalk.blue('=' .repeat(60)));
      
      // 读取最后100行日志
      const logContent = await fs.readFile(logPath, 'utf8');
      const lines = logContent.split('\n').filter(line => line.trim());
      
      // 显示最后100行
      const recentLines = lines.slice(-100);
      for (const line of recentLines) {
        this.formatLogLine(line);
      }
      
      console.log(chalk.blue('=' .repeat(60)));
      
      if (lines.length > 100) {
        console.log(chalk.yellow(`📄 显示最近100行，共${lines.length}行`));
      }
      
    } catch (error) {
      console.error(chalk.red('✗ 读取日志失败:'), error.message);
    }
  }

  async getAllAgentsStatus() {
    const agents = [];
    
    try {
      const agentFiles = await fs.readdir(this.agentsDir);
      
      for (const file of agentFiles) {
        if (file.endsWith('.json')) {
          const agentName = file.replace('.json', '');
          const status = await this.getAgentStatus(agentName);
          agents.push({
            name: agentName,
            ...status
          });
        }
      }
    } catch (error) {
      console.warn(chalk.yellow('⚠ 获取Agent状态失败:'), error.message);
    }
    
    return agents;
  }

  async getAgentStatus(agentName) {
    const agentPidPath = path.join(this.pidsDir, `${agentName}.pid`);
    
    if (!await fs.pathExists(agentPidPath)) {
      return { running: false, pid: null, uptime: 0, memory: null };
    }

    try {
      const pid = (await fs.readFile(agentPidPath, 'utf8')).trim();
      
      // 检查进程是否仍在运行
      await execAsync(`kill -0 ${pid}`);
      
      // 获取进程统计信息
      const stats = await this.getProcessMetrics(pid);
      
      // 获取运行时间
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
      
      return {
        running: true,
        pid,
        uptime,
        memory: stats.memory
      };
    } catch (error) {
      // 进程不存在，清理PID文件
      await fs.remove(agentPidPath);
      return { running: false, pid: null, uptime: 0, memory: null };
    }
  }

  async getProcessMetrics(pid) {
    try {
      // 获取CPU和内存使用情况
      const { stdout } = await execAsync(`ps -p ${pid} -o %cpu,%mem,rss,etime,comm,pcpu,pmem`);
      const lines = stdout.trim().split('\n');
      
      if (lines.length < 2) {
        throw new Error('无法获取进程信息');
      }
      
      const metrics = lines[1].split(/\s+/);
      return {
        cpu: parseFloat(metrics[0]) || 0,
        memory: parseFloat(metrics[1]) || 0,
        rss: parseInt(metrics[2]) || 0,
        uptime: metrics[3] || 'N/A',
        command: metrics[4] || 'N/A',
        pcpu: parseFloat(metrics[5]) || 0,
        pmem: parseFloat(metrics[6]) || 0
      };
    } catch (error) {
      throw new Error(`获取进程指标失败: ${error.message}`);
    }
  }

  async getSystemInfo() {
    try {
      // 获取CPU使用率
      const { stdout: cpuInfo } = await execAsync('top -bn1 | grep "Cpu(s)" | sed "s/.*, *\\([0-9.]*\\)%* id.*/\\1/" | awk \'{print 100 - $1}\'');
      const cpuUsage = parseFloat(cpuInfo.trim()) || 0;
      
      // 获取内存使用情况
      const { stdout: memInfo } = await execAsync('free -m');
      const memLines = memInfo.trim().split('\n');
      const memTotal = parseInt(memLines[1].split(/\s+/)[1]);
      const memUsed = parseInt(memLines[1].split(/\s+/)[2]);
      const memFree = parseInt(memLines[1].split(/\s+/)[3]);
      const memPercentage = ((memUsed / memTotal) * 100).toFixed(1);
      
      // 获取系统运行时间
      const { stdout: uptimeInfo } = await execAsync('uptime -p');
      
      return {
        cpu: cpuUsage.toFixed(1),
        memory: {
          total: memTotal,
          used: memUsed,
          free: memFree,
          percentage: memPercentage
        },
        uptime: uptimeInfo.trim()
      };
    } catch (error) {
      return {
        cpu: 'N/A',
        memory: { total: 0, used: 0, free: 0, percentage: 0 },
        uptime: 'N/A'
      };
    }
  }

  async showSystemResources() {
    console.log(chalk.blue('💻 系统资源使用情况:'));
    
    try {
      // 显示CPU信息
      const { stdout: cpuInfo } = await execAsync('lscpu | grep "Model name" | cut -d: -f2 | xargs');
      console.log(`  CPU: ${cpuInfo.trim()}`);
      
      // 显示内存信息
      const { stdout: memInfo } = await execAsync('free -h');
      console.log(`  内存: ${memInfo.split('\n')[1].trim()}`);
      
      // 显示磁盘信息
      const { stdout: diskInfo } = await execAsync('df -h /');
      console.log(`  磁盘: ${diskInfo.split('\n')[1].trim()}`);
      
    } catch (error) {
      console.log(chalk.yellow('  无法获取详细系统信息'));
    }
  }

  async showRecentLogs() {
    try {
      const logFiles = await fs.readdir(this.logsDir);
      
      if (logFiles.length === 0) {
        console.log(chalk.gray('  没有日志文件'));
        return;
      }
      
      // 获取最新的日志文件
      const logStats = [];
      for (const file of logFiles) {
        const fullPath = path.join(this.logsDir, file);
        const stats = await fs.stat(fullPath);
        logStats.push({ file, stats });
      }
      
      logStats.sort((a, b) => b.stats.mtime - a.stats.mtime);
      const latestLogFile = logStats[0].file;
      
      const logPath = path.join(this.logsDir, latestLogFile);
      const logContent = await fs.readFile(logPath, 'utf8');
      const lines = logContent.split('\n').filter(line => line.trim());
      
      // 显示最后10行
      const recentLines = lines.slice(-10);
      for (const line of recentLines) {
        this.formatLogLine(line);
      }
      
    } catch (error) {
      console.log(chalk.yellow('  无法读取日志文件'));
    }
  }

  formatLogLine(line) {
    const timestampRegex = /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/;
    const timestampMatch = line.match(timestampRegex);
    
    if (timestampMatch) {
      const timestamp = timestampMatch[0];
      const message = line.replace(timestampRegex, '');
      
      // 根据日志级别着色
      let color = 'white';
      if (line.includes('ERROR')) color = 'red';
      else if (line.includes('WARN')) color = 'yellow';
      else if (line.includes('INFO')) color = 'blue';
      else if (line.includes('DEBUG')) color = 'gray';
      
      console.log(`${chalk.gray(timestamp)} ${chalk[color](message.trim())}`);
    } else {
      console.log(line);
    }
  }

  async getNetworkInfo(pid) {
    try {
      const { stdout } = await execAsync(`ss -tpn | grep ${pid}`);
      return stdout.trim();
    } catch (error) {
      return 'N/A';
    }
  }

  async getFileDescriptorInfo(pid) {
    try {
      const { stdout } = await execAsync(`lsof -p ${pid} | wc -l`);
      const count = parseInt(stdout.trim()) - 1; // 减去标题行
      return `${count} 个文件描述符`;
    } catch (error) {
      return 'N/A';
    }
  }

  async getEnvironmentInfo(pid) {
    try {
      const { stdout } = await execAsync(`cat /proc/${pid}/environ | tr '\\0' '\\n' | head -10`);
      return stdout.trim();
    } catch (error) {
      return 'N/A';
    }
  }

  formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (days > 0) {
      return `${days}天 ${hours}小时 ${minutes}分钟`;
    } else if (hours > 0) {
      return `${hours}小时 ${minutes}分钟 ${secs}秒`;
    } else if (minutes > 0) {
      return `${minutes}分钟 ${secs}秒`;
    } else {
      return `${secs}秒`;
    }
  }

  formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
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
}