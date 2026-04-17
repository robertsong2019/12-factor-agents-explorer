/**
 * AI Agent Development Framework - Core Agent Base Class
 * 
 * This provides the foundation for building AI agents with embedded capabilities
 * and rapid prototyping features.
 */

import { EventEmitter } from 'events';

export interface AgentConfig {
  name: string;
  model?: string;
  capabilities: string[];
  memorySize?: number;
  enableRapidProto?: boolean;
}

export interface AgentMemory {
  messages: Array<{
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: Date;
  }>;
  context: Map<string, any>;
}

export interface AgentState {
  active: boolean;
  thinking: boolean;
  lastAction: string | null;
  memory: AgentMemory;
}

export abstract class BaseAgent extends EventEmitter {
  protected config: AgentConfig;
  protected state: AgentState;
  protected memory: AgentMemory;
  protected embeddedAI: boolean = false;

  constructor(config: AgentConfig) {
    super();
    this.config = config;
    this.memory = {
      messages: [],
      context: new Map()
    };
    this.state = {
      active: false,
      thinking: false,
      lastAction: null,
      memory: this.memory
    };
    
    this.initializeAgent();
  }

  abstract process(input: string): Promise<string>;
  abstract think(task: string): Promise<string>;
  abstract act(action: string): Promise<any>;

  protected initializeAgent(): void {
    this.emit('initialized', { name: this.config.name, capabilities: this.config.capabilities });
    
    // Enable rapid prototyping if configured
    if (this.config.enableRapidProto) {
      this.enableRapidPrototyping();
    }
  }

  protected enableRapidPrototyping(): void {
    this.embeddedAI = true;
    this.emit('rapidProtoEnabled');
  }

  async start(): Promise<void> {
    this.state.active = true;
    this.emit('started', { name: this.config.name });
  }

  async stop(): Promise<void> {
    this.state.active = false;
    this.emit('stopped', { name: this.config.name });
  }

  async addMessage(role: 'user' | 'assistant' | 'system', content: string): Promise<void> {
    const message = {
      role,
      content,
      timestamp: new Date()
    };
    
    this.memory.messages.push(message);
    this.state.memory = this.memory;
    this.emit('messageAdded', message);
  }

  async getContext(key: string): Promise<any> {
    return this.memory.context.get(key);
  }

  async setContext(key: string, value: any): Promise<void> {
    this.memory.context.set(key, value);
    this.emit('contextUpdated', { key, value });
  }

  async clearMemory(): Promise<void> {
    this.memory.messages = [];
    this.memory.context.clear();
    this.state.memory = this.memory;
    this.emit('memoryCleared');
  }

  async getState(): Promise<AgentState> {
    return { ...this.state };
  }

  async getCapabilities(): Promise<string[]> {
    return [...this.config.capabilities];
  }
}