/**
 * Adaptive Learning Agent
 * 
 * An AI agent capable of learning and adapting during runtime, continuously improving
 * its performance based on experience and feedback.
 */

import { BaseAgent, AgentConfig } from './BaseAgent';

export interface LearningExperience {
  timestamp: Date;
  input: string;
  output: string;
  feedback?: number; // 0-1 scale
  context: Map<string, any>;
  performance?: number;
}

export interface KnowledgeItem {
  id: string;
  type: 'pattern' | 'strategy' | 'fact' | 'procedure';
  content: any;
  confidence: number;
  lastUsed: Date;
  usageCount: number;
}

export interface AdaptiveConfig extends AgentConfig {
  maxMemorySize?: number;
  learningRate?: number;
  forgettingRate?: number;
  confidenceThreshold?: number;
  enableTransferLearning?: boolean;
}

export class AdaptiveAgent extends BaseAgent {
  private experiences: LearningExperience[] = [];
  private knowledge: Map<string, KnowledgeItem> = new Map();
  private maxMemorySize: number;
  private learningRate: number;
  private forgettingRate: number;
  private confidenceThreshold: number;
  private enableTransferLearning: boolean;
  
  private intervals: ReturnType<typeof setInterval>[] = [];
  private performanceMetrics: {
    totalTasks: number;
    successfulTasks: number;
    averageResponseTime: number;
    learningEfficiency: number;
  } = {
    totalTasks: 0,
    successfulTasks: 0,
    averageResponseTime: 0,
    learningEfficiency: 0
  };

  constructor(config: AdaptiveConfig) {
    super(config);
    this.maxMemorySize = config.maxMemorySize ?? 1000;
    this.learningRate = config.learningRate ?? 0.1;
    this.forgettingRate = config.forgettingRate ?? 0.05;
    this.confidenceThreshold = config.confidenceThreshold ?? 0.7;
    this.enableTransferLearning = config.enableTransferLearning ?? true;
    
    this.initializeLearningMechanisms();
  }

  private initializeLearningMechanisms(): void {
    // Initialize pattern recognition
    this.setupPatternRecognition();
    
    // Initialize knowledge management
    this.setupKnowledgeManagement();
    
    // Initialize transfer learning
    if (this.enableTransferLearning) {
      this.setupTransferLearning();
    }
  }

  private setupPatternRecognition(): void {
    // Pattern recognition system for identifying successful patterns
    this.intervals.push(setInterval(() => {
      this.analyzePatterns();
    }, 60000)); // Analyze patterns every minute
  }

  private setupKnowledgeManagement(): void {
    // Knowledge management and consolidation
    this.intervals.push(setInterval(() => {
      this.consolidateKnowledge();
      this.applyForgetting();
    }, 300000)); // Every 5 minutes
  }

  private setupTransferLearning(): void {
    // Transfer learning mechanism for cross-task knowledge sharing
    this.intervals.push(setInterval(() => {
      this.transferKnowledge();
    }, 120000)); // Every 2 minutes
  }

  clearAllIntervals(): void {
    for (const id of this.intervals) {
      clearInterval(id);
    }
    this.intervals = [];
  }

  async think(task: string): Promise<string> {
    return this.process(task);
  }

  async act(action: string): Promise<any> {
    return this.process(action);
  }

  async process(input: string): Promise<string> {
    const startTime = Date.now();
    
    try {
      // Check for similar past experiences
      const similarExperiences = this.findSimilarExperiences(input);
      const knowledge = this.relevantKnowledgeForInput(input);
      
      // Generate response based on learned knowledge
      let response: string;
      if (similarExperiences.length > 0) {
        response = await this.generateResponseFromExperience(input, similarExperiences, knowledge);
      } else {
        response = await this.generateNovelResponse(input, knowledge);
      }
      
      // Record learning experience
      const experience: LearningExperience = {
        timestamp: new Date(),
        input,
        output: response,
        context: new Map(),
        performance: 1.0 // Initial performance assumption
      };
      
      this.experiences.push(experience);
      
      // Update performance metrics
      const responseTime = Date.now() - startTime;
      this.updatePerformanceMetrics(true, responseTime);
      
      // Trim experiences if exceeding max size
      if (this.experiences.length > this.maxMemorySize) {
        this.trimExperiences();
      }
      
      return response;
    } catch (error) {
      const responseTime = Date.now() - startTime;
      this.updatePerformanceMetrics(false, responseTime);
      console.error('Adaptive processing error:', error);
      return 'I encountered an error processing your request. I\'ll learn from this experience.';
    }
  }

  private async generateResponseFromExperience(
    input: string, 
    experiences: LearningExperience[], 
    knowledge: KnowledgeItem[]
  ): Promise<string> {
    // Use learned patterns and knowledge to generate response
    const bestResponse = this.selectBestResponse(experiences);
    const knowledgeEnhancement = this.enhanceWithKnowledge(bestResponse, knowledge);
    
    // Apply learning rate to refine response
    if (Math.random() < this.learningRate) {
      return this.refineResponse(knowledgeEnhancement, input);
    }
    
    return knowledgeEnhancement;
  }

  private async generateNovelResponse(input: string, knowledge: KnowledgeItem[]): Promise<string> {
    // Generate response when no similar experiences found
    const baseResponse = await this.generateBaseResponse(input);
    const knowledgeEnhanced = this.enhanceWithKnowledge(baseResponse, knowledge);
    
    // Store this as a new pattern for future use
    this.storeNewPattern(input, knowledgeEnhanced);
    
    return knowledgeEnhanced;
  }

  private findSimilarExperiences(input: string): LearningExperience[] {
    // Find experiences with similar input patterns
    const inputTokens = this.tokenizeInput(input);
    
    return this.experiences
      .map(exp => ({
        experience: exp,
        similarity: this.calculateSimilarity(inputTokens, this.tokenizeInput(exp.input))
      }))
      .filter(item => item.similarity > this.confidenceThreshold)
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, 5)
      .map(item => item.experience);
  }

  private relevantKnowledgeForInput(input: string): KnowledgeItem[] {
    // Find relevant knowledge items for the input
    const inputKeywords = this.extractKeywords(input);
    
    return Array.from(this.knowledge.values())
      .filter(item => {
        const contentKeywords = this.extractKeywords(JSON.stringify(item.content));
        return inputKeywords.some(keyword => 
          contentKeywords.some(kw => kw.includes(keyword))
        );
      })
      .sort((a, b) => {
        // Sort by confidence and recency
        const aScore = a.confidence * (1 + Math.log(a.usageCount + 1));
        const bScore = b.confidence * (1 + Math.log(b.usageCount + 1));
        return bScore - aScore;
      })
      .slice(0, 10);
  }

  private async generateBaseResponse(input: string): Promise<string> {
    // Base response generation (would integrate with external AI services)
    const responses = [
      'I understand your request about: ${input}',
      'Based on my understanding: ${input}',
      'I can help you with: ${input}',
      'Regarding: ${input}, I can assist you.'
    ];
    
    const template = responses[Math.floor(Math.random() * responses.length)];
    return template.replace('${input}', input);
  }

  private enhanceWithKnowledge(baseResponse: string, knowledge: KnowledgeItem[]): string {
    // Enhance response with relevant knowledge
    if (knowledge.length === 0) return baseResponse;
    
    const mostRelevant = knowledge[0];
    const knowledgeContribution = mostRelevant.content;
    
    // Simple knowledge integration - in real implementation, would be more sophisticated
    return `${baseResponse} I can also tell you that: ${JSON.stringify(knowledgeContribution)}`;
  }

  private refineResponse(response: string, input: string): string {
    // Refine response based on learning rate
    const refinements = [
      `I understand you're asking about: ${input}`,
      `Regarding: ${input}, I think: ${response}`,
      `Based on your input: ${input}, my response is: ${response}`
    ];
    
    return refinements[Math.floor(Math.random() * refinements.length)];
  }

  private storeNewPattern(input: string, response: string): void {
    // Store new pattern for future learning
    const pattern: KnowledgeItem = {
      id: `pattern_${Date.now()}`,
      type: 'pattern',
      content: { input, response },
      confidence: 0.5,
      lastUsed: new Date(),
      usageCount: 1
    };
    
    this.knowledge.set(pattern.id, pattern);
  }

  private selectBestResponse(experiences: LearningExperience[]): string {
    // Select the best response based on historical performance
    const scoredExperiences = experiences.map(exp => ({
      response: exp.output,
      score: exp.feedback ?? 0.5 // Default score if no feedback
    }));
    
    scoredExperiences.sort((a, b) => b.score - a.score);
    return scoredExperiences[0].response;
  }

  private analyzePatterns(): void {
    // Analyze successful patterns and update knowledge
    const successfulExperiences = this.experiences.filter(
      exp => (exp.feedback ?? 0.5) > this.confidenceThreshold
    );
    
    successfulExperiences.forEach(exp => {
      const patternId = this.findSimilarPattern(exp.input);
      if (patternId) {
        const pattern = this.knowledge.get(patternId);
        if (pattern) {
          pattern.confidence = Math.min(1.0, pattern.confidence + this.learningRate);
          pattern.usageCount++;
          pattern.lastUsed = new Date();
        }
      }
    });
  }

  private consolidateKnowledge(): void {
    // Consolidate similar knowledge items
    const knowledgeArray = Array.from(this.knowledge.values());
    const consolidated: Map<string, KnowledgeItem> = new Map();
    
    knowledgeArray.forEach(item => {
      const similar = Array.from(consolidated.values()).find(k => 
        this.calculateKnowledgeSimilarity(item, k) > 0.8
      );
      
      if (similar) {
        // Merge knowledge items
        similar.confidence = Math.max(similar.confidence, item.confidence);
        similar.usageCount += item.usageCount;
        similar.lastUsed = new Date();
      } else {
        consolidated.set(item.id, item);
      }
    });
    
    this.knowledge = consolidated;
  }

  private applyForgetting(): void {
    // Apply forgetting mechanism to unused knowledge
    const now = new Date();
    const timeSinceLastUsed = 7 * 24 * 60 * 60 * 1000; // 7 days
    
    this.knowledge.forEach((item, id) => {
      const timeDiff = now.getTime() - item.lastUsed.getTime();
      if (timeDiff > timeSinceLastUsed) {
        item.confidence = Math.max(0.1, item.confidence - this.forgettingRate);
        if (item.confidence < 0.1) {
          this.knowledge.delete(id);
        }
      }
    });
  }

  private transferKnowledge(): void {
    // Transfer knowledge between different task domains
    const knowledgeArray = Array.from(this.knowledge.values());
    const recentKnowledge = knowledgeArray.filter(item => {
      const timeDiff = Date.now() - item.lastUsed.getTime();
      return timeDiff < 24 * 60 * 60 * 1000; // Last 24 hours
    });
    
    recentKnowledge.forEach(knowledge => {
      // Apply knowledge to similar but different contexts
      const relatedTasks = this.findRelatedTasks(knowledge);
      relatedTasks.forEach(task => {
        this.adaptKnowledgeForTask(knowledge, task);
      });
    });
  }

  // Helper methods
  private tokenizeInput(input: string): string[] {
    return input.toLowerCase().split(/\s+/);
  }

  private calculateSimilarity(tokens1: string[], tokens2: string[]): number {
    const set1 = new Set(tokens1);
    const set2 = new Set(tokens2);
    const intersection = new Set([...set1].filter(x => set2.has(x)));
    const union = new Set([...set1, ...set2]);
    
    return intersection.size / union.size;
  }

  private extractKeywords(text: string): string[] {
    return text
      .toLowerCase()
      .split(/\s+/)
      .filter(word => word.length > 3)
      .slice(0, 10);
  }

  private findSimilarPattern(input: string): string | null {
    // Find similar pattern in knowledge base
    const inputTokens = this.tokenizeInput(input);
    
    for (const [id, pattern] of this.knowledge) {
      if (pattern.type === 'pattern') {
        const patternTokens = this.tokenizeInput(JSON.stringify(pattern.content));
        const similarity = this.calculateSimilarity(inputTokens, patternTokens);
        if (similarity > 0.7) {
          return id;
        }
      }
    }
    return null;
  }

  private calculateKnowledgeSimilarity(item1: KnowledgeItem, item2: KnowledgeItem): number {
    // Calculate similarity between two knowledge items
    const content1 = JSON.stringify(item1.content);
    const content2 = JSON.stringify(item2.content);
    
    return this.calculateSimilarity(
      this.tokenizeInput(content1),
      this.tokenizeInput(content2)
    );
  }

  private findRelatedTasks(knowledge: KnowledgeItem): string[] {
    // Find tasks related to the knowledge item
    return ['task1', 'task2']; // Placeholder implementation
  }

  private adaptKnowledgeForTask(knowledge: KnowledgeItem, task: string): void {
    // Adapt knowledge for a different task
    knowledge.usageCount++;
    knowledge.lastUsed = new Date();
  }

  private updatePerformanceMetrics(success: boolean, responseTime: number): void {
    this.performanceMetrics.totalTasks++;
    if (success) {
      this.performanceMetrics.successfulTasks++;
    }
    
    // Update average response time
    this.performanceMetrics.averageResponseTime = (
      (this.performanceMetrics.averageResponseTime * (this.performanceMetrics.totalTasks - 1) + responseTime) /
      this.performanceMetrics.totalTasks
    );
    
    // Update learning efficiency
    this.performanceMetrics.learningEfficiency = this.performanceMetrics.successfulTasks / this.performanceMetrics.totalTasks;
  }

  private trimExperiences(): void {
    // Remove oldest experiences if exceeding max size
    if (this.experiences.length > this.maxMemorySize) {
      const removeCount = this.experiences.length - this.maxMemorySize;
      this.experiences.splice(0, removeCount);
    }
  }

  // Public methods for external feedback
  async provideFeedback(feedback: number): Promise<void> {
    // Provide feedback on the last response
    if (this.experiences.length > 0) {
      const lastExperience = this.experiences[this.experiences.length - 1];
      lastExperience.feedback = Math.max(0, Math.min(1, feedback));
    }
  }

  getPerformanceMetrics(): any {
    return { ...this.performanceMetrics };
  }

  getKnowledgeSummary(): KnowledgeItem[] {
    return Array.from(this.knowledge.values())
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, 20);
  }
}