/**
 * Collaborative Creation Agent
 * 
 * An AI system that coordinates multiple specialized agents to work together on 
 * creative tasks, combining different perspectives and skills.
 */

import { BaseAgent, AgentConfig } from './BaseAgent';
import { MultimodalAgent, MultimodalAgentConfig } from './MultimodalAgent';
import { AdaptiveAgent, AdaptiveConfig } from './AdaptiveAgent';

export interface CreativeTask {
  id: string;
  title: string;
  description: string;
  type: 'content_creation' | 'code_generation' | 'design' | 'research' | 'problem_solving';
  requirements: string[];
  constraints: string[];
  deadline?: Date;
  priority: 'low' | 'medium' | 'high';
}

export interface AgentRole {
  name: string;
  expertise: string[];
  capabilities: string[];
  assignedAgent: BaseAgent;
  workload: number;
}

export interface CollaborationProtocol {
  communicationMethod: 'direct' | 'mediated' | 'hierarchical';
  decisionMaking: 'consensus' | 'majority' | 'expert';
  qualityControl: 'peer_review' | 'automated' | 'hybrid';
  conflictResolution: 'voting' | 'mediation' | 'escalation';
}

export interface CreativeOutput {
  id: string;
  taskId: string;
  content: any;
  qualityScore: number;
  contributors: string[];
  reviewStatus: 'draft' | 'review' | 'approved' | 'rejected';
  createdAt: Date;
  revisedAt?: Date;
}

export interface CollaborativeConfig extends AgentConfig {
  maxAgents?: number;
  enableQualityControl?: boolean;
  enableConflictResolution?: boolean;
  enableInnovationBoost?: boolean;
  protocol?: CollaborationProtocol;
}

export class CollaborativeCreationAgent extends BaseAgent {
  private agents: Map<string, AgentRole> = new Map();
  private activeTasks: Map<string, CreativeTask> = new Map();
  private completedOutputs: Map<string, CreativeOutput> = new Map();
  private collaborationHistory: any[] = [];
  
  private maxAgents: number;
  private enableQualityControl: boolean;
  private enableConflictResolution: boolean;
  private enableInnovationBoost: boolean;
  private protocol: CollaborationProtocol;
  
  private intervals: ReturnType<typeof setInterval>[] = [];
  private taskQueue: CreativeTask[] = [];
  private innovationPrompts: string[] = [
    "Think outside the box and challenge conventional approaches",
    "Combine ideas from different domains to create something novel",
    "What if we approached this problem from a completely different perspective?",
    "How can we make this 10x better or simpler?",
    "What unexpected connections can we make between different concepts?"
  ];

  constructor(config: CollaborativeConfig) {
    super(config);
    this.maxAgents = config.maxAgents ?? 5;
    this.enableQualityControl = config.enableQualityControl ?? true;
    this.enableConflictResolution = config.enableConflictResolution ?? true;
    this.enableInnovationBoost = config.enableInnovationBoost ?? true;
    this.protocol = config.protocol ?? {
      communicationMethod: 'mediated',
      decisionMaking: 'consensus',
      qualityControl: 'hybrid',
      conflictResolution: 'mediation'
    };
    
    this.initializeCollaborativeSystem();
  }

  private initializeCollaborativeSystem(): void {
    // Initialize specialized agents
    this.createSpecializedAgents();
    
    // Setup collaboration workflows
    this.setupCollaborationWorkflows();
    
    // Setup quality control
    if (this.enableQualityControl) {
      this.setupQualityControl();
    }
  }

  private createSpecializedAgents(): void {
    // Create different specialized agents
    const multimodalConfig: MultimodalAgentConfig = {
      name: 'multimodal-expert',
      capabilities: ['text_analysis', 'image_recognition', 'audio_processing'],
      enableRapidProto: true
    };
    
    const adaptiveConfig: AdaptiveConfig = {
      name: 'adaptive-learner',
      capabilities: ['pattern_learning', 'knowledge_adaptation', 'continuous_improvement'],
      enableTransferLearning: true
    };
    
    // Create specialized agents
    const multimodalAgent = new MultimodalAgent(multimodalConfig);
    const adaptiveAgent = new AdaptiveAgent(adaptiveConfig);
    
    // Register agents
    this.registerAgent('multimodal-expert', multimodalAgent, ['analysis', 'interpretation', 'understanding']);
    this.registerAgent('adaptive-learner', adaptiveAgent, ['learning', 'optimization', 'adaptation']);
  }

  private registerAgent(name: string, agent: BaseAgent, expertise: string[]): void {
    const role: AgentRole = {
      name,
      expertise,
      capabilities: [],  // populated asynchronously
      assignedAgent: agent,
      workload: 0
    };
    
    this.agents.set(name, role);
    
    // Set up event handlers
    agent.on('messageAdded', (message) => {
      this.handleAgentMessage(name, message);
    });
    
    agent.on('completed', (result) => {
      this.handleAgentCompletion(name, result);
    });
  }

  async think(task: string): Promise<string> {
    return this.process(task);
  }

  async act(action: string): Promise<any> {
    return this.process(action);
  }

  async process(input: string): Promise<string> {
    // Parse the input as a creative task
    const task = this.parseCreativeTask(input);
    
    if (task) {
      await this.assignTask(task);
      return `I've created a collaborative task: ${task.title}. My team of agents is working on it now.`;
    } else {
      // Handle general collaboration requests
      return await this.handleCollaborationRequest(input);
    }
  }

  private parseCreativeTask(input: string): CreativeTask | null {
    // Parse input to extract creative task requirements
    const lowerInput = input.toLowerCase();
    
    if (lowerInput.includes('write') || lowerInput.includes('create') || lowerInput.includes('generate')) {
      return {
        id: `task_${Date.now()}`,
        title: 'Creative Content Generation',
        description: input,
        type: 'content_creation',
        requirements: [input],
        constraints: ['maintain quality', 'be creative'],
        priority: 'medium'
      };
    }
    
    if (lowerInput.includes('code') || lowerInput.includes('program') || lowerInput.includes('develop')) {
      return {
        id: `task_${Date.now()}`,
        title: 'Code Generation Task',
        description: input,
        type: 'code_generation',
        requirements: [input],
        constraints: ['best practices', 'efficient code'],
        priority: 'high'
      };
    }
    
    if (lowerInput.includes('design') || lowerInput.includes('visual') || lowerInput.includes('creative')) {
      return {
        id: `task_${Date.now()}`,
        title: 'Design and Creative Task',
        description: input,
        type: 'design',
        requirements: [input],
        constraints: ['aesthetically pleasing', 'functional'],
        priority: 'medium'
      };
    }
    
    return null;
  }

  private async assignTask(task: CreativeTask): Promise<void> {
    this.activeTasks.set(task.id, task);
    this.taskQueue.push(task);
    
    // Assign suitable agents to the task
    const suitableAgents = this.findSuitableAgents(task);
    await this.coordinateAgents(task, suitableAgents);
  }

  private findSuitableAgents(task: CreativeTask): AgentRole[] {
    // Find agents whose expertise matches the task requirements
    const suitableAgents = Array.from(this.agents.values()).filter(agent => {
      return agent.expertise.some(skill => 
        task.description.toLowerCase().includes(skill.toLowerCase())
      );
    });
    
    // Sort by workload (lower workload first)
    return suitableAgents.sort((a, b) => a.workload - b.workload).slice(0, 3);
  }

  private async coordinateAgents(task: CreativeTask, agents: AgentRole[]): Promise<void> {
    // Coordinate the selected agents to work on the task
    const coordination: any = {
      taskId: task.id,
      agents: agents.map(a => a.name),
      startTime: new Date(),
      strategy: this.determineCoordinationStrategy(agents)
    };
    
    // Start collaborative work
    await this.startCollaborativeWork(task, agents, coordination);
  }

  private determineCoordinationStrategy(agents: AgentRole[]): string {
    // Determine the best coordination strategy based on agent capabilities
    const hasMultimodal = agents.some(a => a.name === 'multimodal-expert');
    const hasAdaptive = agents.some(a => a.name === 'adaptive-learner');
    
    if (hasMultimodal && hasAdaptive) {
      return 'hybrid_coordination';
    } else if (hasMultimodal) {
      return 'multimodal_first';
    } else if (hasAdaptive) {
      return 'adaptive_learning';
    } else {
      return 'basic_collaboration';
    }
  }

  private async startCollaborativeWork(task: CreativeTask, agents: AgentRole[], coordination: any): Promise<void> {
    // Start the collaborative work process
    const promises = agents.map(async (agent) => {
      const taskSegment = this.createTaskSegment(task, agent);
      await agent.assignedAgent.process(taskSegment);
      agent.workload++;
    });
    
    await Promise.all(promises);
    
    // Gather and combine results
    const results = await this.gatherResults(agents);
    const finalOutput = this.combineResults(task, results);
    
    // Apply quality control if enabled
    if (this.enableQualityControl) {
      await this.performQualityControl(finalOutput);
    }
    
    // Store the completed output
    this.storeOutput(finalOutput);
  }

  private createTaskSegment(task: CreativeTask, agent: AgentRole): string {
    // Create a specific task segment for each agent based on their expertise
    const taskContext = `Collaborative task: ${task.title}\nDescription: ${task.description}`;
    const agentRole = `Your role: ${agent.name} with expertise in ${agent.expertise.join(', ')}`;
    const collaborationRequest = `Please contribute your specific expertise to complete this creative task.`;
    
    // Add innovation prompt if enabled
    let innovationPrompt = '';
    if (this.enableInnovationBoost) {
      innovationPrompt = `\nInnovation challenge: ${this.innovationPrompts[Math.floor(Math.random() * this.innovationPrompts.length)]}`;
    }
    
    return `${taskContext}\n${agentRole}\n${collaborationRequest}${innovationPrompt}`;
  }

  private async gatherResults(agents: AgentRole[]): Promise<any[]> {
    // Gather results from all participating agents
    const results = [];
    
    for (const agent of agents) {
      try {
        const state = await agent.assignedAgent.getState();
        if (state && state.memory) {
          results.push({
            agent: agent.name,
            contribution: state.memory,
            timestamp: new Date()
          });
        }
      } catch (error) {
        console.error(`Error gathering result from ${agent.name}:`, error);
      }
    }
    
    return results;
  }

  private combineResults(task: CreativeTask, results: any[]): CreativeOutput {
    // Combine individual results into a final creative output
    const combinedContent = this.mergeResults(results);
    
    const output: CreativeOutput = {
      id: `output_${Date.now()}`,
      taskId: task.id,
      content: combinedContent,
      qualityScore: 0.8, // Initial quality score
      contributors: results.map(r => r.agent),
      reviewStatus: 'draft',
      createdAt: new Date()
    };
    
    return output;
  }

  private mergeResults(results: any[]): any {
    // Merge individual agent results into a coherent output
    if (results.length === 0) return {};
    
    // Simple merge strategy - in real implementation, would be more sophisticated
    const merged: Record<string, any> = {};
    
    results.forEach((result, index) => {
      const agentName = `agent_${index + 1}`;
      merged[agentName] = result.contribution;
    });
    
    return merged;
  }

  private async performQualityControl(output: CreativeOutput): Promise<void> {
    // Perform quality control on the creative output
    const qualityChecks = [
      this.checkCoherence(output),
      this.checkCompleteness(output),
      this.checkCreativity(output)
    ];
    
    const qualityResults = await Promise.all(qualityChecks);
    const overallQuality = qualityResults.reduce((sum, score) => sum + score, 0) / qualityResults.length;
    
    output.qualityScore = overallQuality;
    output.reviewStatus = overallQuality > 0.7 ? 'review' : 'draft';
    
    if (overallQuality < 0.5) {
      // Request revisions
      output.reviewStatus = 'rejected';
    }
  }

  private async checkCoherence(output: CreativeOutput): Promise<number> {
    // Check coherence of the output
    const contentStr = JSON.stringify(output.content);
    const coherenceScore = contentStr.length > 100 ? 0.8 : 0.3;
    return coherenceScore;
  }

  private async checkCompleteness(output: CreativeOutput): Promise<number> {
    // Check completeness of the output
    const hasAllContributors = output.contributors.length >= 2;
    return hasAllContributors ? 0.9 : 0.4;
  }

  private async checkCreativity(output: CreativeOutput): Promise<number> {
    // Check creativity of the output
    const contentStr = JSON.stringify(output.content);
    const noveltyScore = contentStr.includes('novel') || contentStr.includes('innovative') ? 0.9 : 0.6;
    return noveltyScore;
  }

  private storeOutput(output: CreativeOutput): void {
    this.completedOutputs.set(output.id, output);
    
    // Update agent workloads
    output.contributors.forEach(agentName => {
      const agent = this.agents.get(agentName);
      if (agent) {
        agent.workload = Math.max(0, agent.workload - 1);
      }
    });
  }

  private handleAgentMessage(agentName: string, message: any): void {
    // Handle messages from collaborative agents
    this.collaborationHistory.push({
      timestamp: new Date(),
      agent: agentName,
      message,
      type: 'agent_message'
    });
  }

  private handleAgentCompletion(agentName: string, result: any): void {
    // Handle completion notifications from agents
    this.collaborationHistory.push({
      timestamp: new Date(),
      agent: agentName,
      result,
      type: 'agent_completion'
    });
  }

  private async handleCollaborationRequest(input: string): Promise<string> {
    // Handle general collaboration requests
    const availableAgents = Array.from(this.agents.values())
      .filter(agent => agent.workload < 3)
      .slice(0, 3);
    
    if (availableAgents.length === 0) {
      return 'All my agents are currently busy. Please try again later.';
    }
    
    return `I have ${availableAgents.length} agents available to help with your collaboration request: ${availableAgents.map(a => a.name).join(', ')}.`;
  }

  private setupCollaborationWorkflows(): void {
    // Setup regular collaboration workflows
    this.intervals.push(setInterval(() => {
      this.processTaskQueue();
    }, 30000)); // Process queue every 30 seconds
    
    this.intervals.push(setInterval(() => {
      this.optimizeAgentAllocation();
    }, 60000)); // Optimize allocation every minute
  }

  private setupQualityControl(): void {
    // Setup quality control mechanisms
    this.intervals.push(setInterval(() => {
      this.reviewPendingOutputs();
    }, 120000)); // Review outputs every 2 minutes
  }

  private async processTaskQueue(): Promise<void> {
    // Process pending tasks in the queue
    if (this.taskQueue.length > 0) {
      const task = this.taskQueue.shift()!;
      await this.assignTask(task);
    }
  }

  private optimizeAgentAllocation(): void {
    // Optimize agent workload distribution
    const agents = Array.from(this.agents.values());
    
    // Sort by workload
    agents.sort((a, b) => a.workload - b.workload);
    
    // Redistribute tasks if necessary
    const overloadedAgents = agents.filter(agent => agent.workload > 5);
    const underloadedAgents = agents.filter(agent => agent.workload < 2);
    
    if (overloadedAgents.length > 0 && underloadedAgents.length > 0) {
      // Transfer some workload from overloaded to underloaded agents
      this.transferWorkload(overloadedAgents, underloadedAgents);
    }
  }

  private transferWorkload(fromAgents: AgentRole[], toAgents: AgentRole[]): void {
    // Transfer workload between agents
    const workToTransfer = Math.min(fromAgents.length, toAgents.length);
    
    for (let i = 0; i < workToTransfer; i++) {
      fromAgents[i].workload--;
      toAgents[i].workload++;
    }
  }

  private async reviewPendingOutputs(): Promise<void> {
    // Review pending outputs
    const pendingOutputs = Array.from(this.completedOutputs.values())
      .filter(output => output.reviewStatus === 'draft');
    
    for (const output of pendingOutputs) {
      await this.performQualityControl(output);
    }
  }

  // Public methods
  clearAllIntervals(): void {
    for (const id of this.intervals) {
      clearInterval(id);
    }
    this.intervals = [];
  }

  async getCollaborationStatus(): Promise<any> {
    return {
      activeTasks: Array.from(this.activeTasks.values()),
      availableAgents: Array.from(this.agents.values())
        .filter(agent => agent.workload < 3)
        .map(agent => agent.name),
      completedOutputs: Array.from(this.completedOutputs.values())
        .filter(output => output.reviewStatus === 'approved'),
      totalCollaborations: this.collaborationHistory.length
    };
  }

  async requestInnovation(): Promise<string> {
    // Request innovation from the collaborative system
    const innovationPrompt = this.innovationPrompts[Math.floor(Math.random() * this.innovationPrompts.length)];
    const innovativeAgents = Array.from(this.agents.values())
      .filter(agent => agent.name === 'adaptive-learner');
    
    if (innovativeAgents.length > 0) {
      return `Innovation challenge: ${innovationPrompt}. Let's work on this together!`;
    }
    
    return `Here's an innovative idea: ${innovationPrompt}. How can we apply this?`;
  }
}