import EventEmitter from 'events';
import axios from 'axios';
import chalk from 'chalk';

export class AgentRunner extends EventEmitter {
  constructor(config) {
    super();
    this.config = config;
    this.running = false;
    this.startTime = null;
    this.requestCount = 0;
    this.errorCount = 0;
    this.stats = {
      requests: 0,
      responses: 0,
      errors: 0,
      averageResponseTime: 0,
      lastResponseTime: 0
    };
  }

  async start() {
    if (this.running) {
      throw new Error('Agent已在运行中');
    }

    this.running = true;
    this.startTime = Date.now();
    
    console.log(chalk.green(`🚀 启动Agent: ${this.config.name}`));
    console.log(chalk.blue(`配置: ${this.config.model} (${this.config.type})`));
    
    // 启动主循环
    this.mainLoop();
    
    // 发送启动事件
    this.emit('started', {
      name: this.config.name,
      pid: process.pid,
      startTime: this.startTime
    });
  }

  async stop() {
    if (!this.running) {
      throw new Error('Agent未运行');
    }

    this.running = false;
    
    console.log(chalk.yellow(`⏹ 停止Agent: ${this.config.name}`));
    
    // 发送停止事件
    this.emit('stopped', {
      name: this.config.name,
      endTime: Date.now(),
      uptime: Date.now() - this.startTime,
      stats: this.stats
    });
  }

  async mainLoop() {
    if (!this.running) return;

    try {
      // 模拟Agent工作
      await this.performAgentTask();
      
      // 检查状态
      if (this.running) {
        // 继续循环
        setTimeout(() => this.mainLoop(), 5000); // 5秒间隔
      }
    } catch (error) {
      this.errorCount++;
      this.stats.errors++;
      
      console.error(chalk.red(`✗ Agent错误: ${error.message}`));
      this.emit('error', {
        name: this.config.name,
        error: error.message,
        timestamp: Date.now()
      });
      
      // 如果是致命错误，停止Agent
      if (this.isFatalError(error)) {
        await this.stop();
      } else {
        // 继续运行
        setTimeout(() => this.mainLoop(), 10000); // 错误后等待10秒
      }
    }
  }

  async performAgentTask() {
    const startTime = Date.now();
    
    try {
      // 根据Agent类型执行不同的任务
      switch (this.config.type) {
        case 'openai':
          await this.handleOpenAITask();
          break;
        case 'claude':
          await this.handleClaudeTask();
          break;
        case 'gemini':
          await this.handleGeminiTask();
          break;
        case 'custom':
          await this.handleCustomTask();
          break;
        default:
          throw new Error(`不支持的Agent类型: ${this.config.type}`);
      }
      
      const responseTime = Date.now() - startTime;
      this.updateStats(responseTime);
      
      this.requestCount++;
      this.stats.lastResponseTime = responseTime;
      
      this.emit('taskCompleted', {
        name: this.config.name,
        taskType: this.config.type,
        responseTime,
        timestamp: Date.now()
      });
      
    } catch (error) {
      throw error;
    }
  }

  async handleOpenAITask() {
    try {
      // 模拟OpenAI API调用
      const prompt = `Agent ${this.config.name} 正在处理任务...`;
      
      console.log(chalk.blue(`🔄 发送OpenAI请求: ${prompt}`));
      
      // 模拟API调用延迟
      await new Promise(resolve => setTimeout(resolve, Math.random() * 2000 + 1000));
      
      // 模拟API响应
      const response = {
        id: `chatcmpl-${Math.random().toString(36).substr(2, 9)}`,
        object: 'chat.completion',
        created: Math.floor(Date.now() / 1000),
        model: this.config.model,
        choices: [{
          index: 0,
          message: {
            role: 'assistant',
            content: `处理完成: ${prompt}`,
            finish_reason: 'stop'
          }
        }]
      };
      
      console.log(chalk.green(`✓ OpenAI响应: ${response.choices[0].message.content}`));
      
    } catch (error) {
      throw new Error(`OpenAI API调用失败: ${error.message}`);
    }
  }

  async handleClaudeTask() {
    try {
      // 模拟Claude API调用
      const prompt = `Agent ${this.config.name} 正在处理Claude任务...`;
      
      console.log(chalk.blue(`🔄 发送Claude请求: ${prompt}`));
      
      // 模拟API调用延迟
      await new Promise(resolve => setTimeout(resolve, Math.random() * 3000 + 1500));
      
      // 模拟API响应
      const response = {
        id: `msg_${Math.random().toString(36).substr(2, 9)}`,
        type: 'message',
        role: 'assistant',
        content: [
          {
            type: 'text',
            text: `Claude处理完成: ${prompt}`
          }
        ],
        model: this.config.model,
        stop_reason: 'end_turn'
      };
      
      console.log(chalk.green(`✓ Claude响应: ${response.content[0].text}`));
      
    } catch (error) {
      throw new Error(`Claude API调用失败: ${error.message}`);
    }
  }

  async handleGeminiTask() {
    try {
      // 模拟Gemini API调用
      const prompt = `Agent ${this.config.name} 正在处理Gemini任务...`;
      
      console.log(chalk.blue(`🔄 发送Gemini请求: ${prompt}`));
      
      // 模拟API调用延迟
      await new Promise(resolve => setTimeout(resolve, Math.random() * 2500 + 1200));
      
      // 模拟API响应
      const response = {
        candidates: [
          {
            content: {
              role: 'model',
              parts: [{ text: `Gemini处理完成: ${prompt}` }]
            },
            finishReason: 'STOP'
          }
        ],
        usageMetadata: {
          promptTokenCount: 50,
          candidatesTokenCount: 30,
              totalTokenCount: 80
        }
      };
      
      console.log(chalk.green(`✓ Gemini响应: ${response.candidates[0].content.parts[0].text}`));
      
    } catch (error) {
      throw new Error(`Gemini API调用失败: ${error.message}`);
    }
  }

  async handleCustomTask() {
    try {
      // 模拟自定义任务处理
      const task = `自定义任务处理: Agent ${this.config.name} 正在执行工作...`;
      
      console.log(chalk.blue(`🔄 执行自定义任务: ${task}`));
      
      // 模拟任务处理延迟
      await new Promise(resolve => setTimeout(resolve, Math.random() * 2000 + 800));
      
      console.log(chalk.green(`✓ 自定义任务完成`));
      
    } catch (error) {
      throw new Error(`自定义任务处理失败: ${error.message}`);
    }
  }

  updateStats(responseTime) {
    // 用旧计数计算增量均值（修复：首样本 Infinity + requests 双重计数）
    const totalRequests = this.stats.requests + 1;
    const totalTime = (this.stats.averageResponseTime * this.stats.requests) + responseTime;
    this.stats = {
      requests: totalRequests,
      responses: this.stats.responses + 1,
      errors: this.stats.errors,
      averageResponseTime: totalTime / totalRequests,
      lastResponseTime: responseTime
    };
  }

  isFatalError(error) {
    // 判断是否为致命错误
    const fatalErrors = [
      'API_KEY_INVALID',
      'QUOTA_EXCEEDED',
      'NETWORK_ERROR',
      'AUTHENTICATION_FAILED'
    ];
    
    return fatalErrors.some(fatalError => error.message.includes(fatalError));
  }

  getStatus() {
    return {
      name: this.config.name,
      type: this.config.type,
      running: this.running,
      startTime: this.startTime,
      uptime: this.startTime ? Date.now() - this.startTime : 0,
      requestCount: this.requestCount,
      errorCount: this.errorCount,
      stats: this.stats
    };
  }

  async handleShutdown() {
    console.log(chalk.yellow(`🔄 Agent ${this.config.name} 正在关闭...`));
    
    // 执行清理工作
    try {
      // 发送最终状态
      this.emit('shutdown', {
        name: this.config.name,
        finalStats: this.stats,
        shutdownTime: Date.now()
      });
      
      console.log(chalk.green(`✓ Agent ${this.config.name} 已安全关闭`));
    } catch (error) {
      console.error(chalk.red(`✗ Agent关闭时出错: ${error.message}`));
      this.emit('error', {
        name: this.config.name,
        error: `关闭失败: ${error.message}`,
        timestamp: Date.now()
      });
    }
  }
}