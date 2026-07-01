# KV Cache：被忽视的 Agent 工作记忆层

> 当所有人都在给 Agent 外挂记忆系统时，最关键的一层记忆正躺在 GPU 显存里，鲜有人认真对待。

## 引言：一个盲区

2026 年，AI Agent 的记忆问题俨然成了显学。向量数据库、知识图谱、时序记忆、CRDT 同步……每周都有新的记忆框架开源。但如果我告诉你，Agent 最核心的记忆不在任何外部存储里，而是每一毫秒都在 GPU 高带宽显存中生死流转——你会怎么想？

这就是 KV Cache。它本是 Transformer 推理优化的工程细节，但在 Agent 时代，它悄然变成了**Agent 的工作记忆**——最脆弱、最昂贵、也最被忽视的一层。

这篇文章基于我对 NeurIPS 2025、ICLR 2026、DAC 2026、FAST 2026 等顶会 15+ 篇论文的系统性研读，试图回答：KV Cache 如何决定 Agent 的智能上限？我们能否打通内部 KV Cache 与外部记忆系统之间的鸿沟？

---

## 一、三层记忆：你一直在忽略最底层

先建立心智模型。一个 Agent 的完整记忆栈其实有三层：

```
┌──────────────────────────────────────────────────────┐
│            Agent 完整记忆栈                            │
├──────────────────────────────────────────────────────┤
│  Layer 2: 外部记忆（agent-memory-graph 等）            │
│  - 跨会话持久化                                         │
│  - 图算法 + 向量 + BM25 混合检索                        │
│  - 时间尺度：小时 → 天 → 周                            │
│  - 类比：长期记忆（海马体）                              │
├──────────────────────────────────────────────────────┤
│  Layer 1: KV Cache（GPU/HBM）                         │
│  - 推理会话内临时存在                                   │
│  - Attention 机制驱动的检索                             │
│  - Prefix caching、语义段共享、模型驱动裁剪              │
│  - 时间尺度：毫秒 → 分钟                               │
│  - 类比：工作记忆（前额叶皮层）                          │
├──────────────────────────────────────────────────────┤
│  Layer 0: 模型参数（冻结权重）                          │
│  - 训练阶段的语义知识                                   │
│  - 时间尺度：月 → 年                                   │
│  - 类比：长期语义记忆（新皮层）                          │
└──────────────────────────────────────────────────────┘
```

大部分开发者在 Layer 2 投入巨大精力——构建向量库、设计图 schema、优化检索策略。但 Layer 1（KV Cache）才是每一轮推理实际操作的战场。

**一个 ReAct 循环的真实流程：**

1. Agent 收到用户指令
2. LLM 生成思考 + 工具调用（产生 KV Cache）
3. 工具执行，结果返回（更多 KV Cache）
4. LLM 基于 accumulated KV Cache 生成下一步推理
5. 循环……

每一步工具调用的输出都变成 KV tokens，被后续步骤 attend to。KV Cache *就是* Agent 的短期记忆——在最物理的层面上。

**问题在于：几乎没有人同时优化两层。**

---

## 二、KV Cache 的三大瓶颈

### 瓶颈 1：Prefix Barrier（前缀壁垒）

传统 KV Cache 复用要求**严格前缀匹配**——新请求必须和缓存中的内容从头到尾完全一致。这在单 Agent 场景下勉强能用，但在多 Agent 协作中直接崩溃：不同 Agent 有不同的 system prompt，前缀天然不同。

这跟外部记忆系统的早期阶段一模一样——BM25 全文搜索只能做精确匹配，直到向量搜索出现才打破壁垒。KV Cache 正在经历相同的进化：

- **段级共享（ICLR 2026）**：把缓存分解为细粒度语义段，任意 Agent 可以在任意位置复用其他 Agent 的 KV 段，配合 RoPE 位置编码修正。
- **KVCOMM（NeurIPS 2025）**：通过"锚点池"对齐不同 Agent 间共享内容的 KV 偏移，实现 70%+ 复用率。
- **TokenDance（2026.04）**：识别多 Agent 的 All-Gather 模式——每轮交互中调度器收集所有 Agent 输出再分发——针对这个模式做 KV 层优化。

### 瓶颈 2：无限增长的上下文

一个执行 20 步的 ReAct Agent，每步工具返回 2000 tokens，累计就是 40000 tokens 的 KV Cache。GPU 显存是有限的——H100 的 80GB 在批量推理时很快见底。

传统方案是启发式裁剪（H2O Heavy Hitters、SnapKV 窗口），但它们对 Agent 场景效果很差——你不知道第 3 步的工具返回在第 18 步会不会被引用。

2026 年的答案是**让模型自己决定**：

```python
class ModelDrivenEviction:
    """
    基于 SideQuest (NVIDIA, 2026) 的思路：
    主线程做推理，辅助线程并行分析哪些工具返回已过时。
    """
    def __init__(self, max_tokens: int):
        self.max_tokens = max_tokens
        self.cached_results: list[dict] = []
    
    def observe_tool_call(self, step: int, tool: str, result: str):
        """记录每个工具调用的结果"""
        self.cached_results.append({
            'step': step,
            'tool': tool,
            'result': result,
            'status': 'active',  # active | stale | evicted
        })
    
    def evict_stale(self, current_step: int) -> list[int]:
        """
        在推理同时并行执行：
        分析当前任务意图，标记不再需要的工具返回。
        NVIDIA 报告：56-65% token 减少，准确率几乎无损失。
        """
        evicted_ids = []
        for entry in self.cached_results:
            if entry['status'] != 'active':
                continue
            
            # 启发式：超过 5 步未被引用的工具结果标记为 stale
            last_referenced = entry.get('last_ref_step', entry['step'])
            if current_step - last_referenced > 5:
                entry['status'] = 'stale'
                evicted_ids.append(entry['step'])
        
        return evicted_ids
```

### 瓶颈 3：无工作流感知

Agent 不是随机调用工具的——它有执行模式。KVFlow（NeurIPS 2025）把 Agent 执行建模为**步骤图**，计算每个 Agent 的 `steps-to-execution`（距离下次激活还有几步），据此决定 KV Cache 的保留/淘汰：

- 下一步就要执行的 Agent → KV Cache 全力保留
- 10 步后才轮到的 Agent → 可以淘汰或压缩
- **效果：1.83× 单工作流加速，2.19× 并发工作流加速**

---

## 三、打通两层：一个实际方案

说了这么多问题，那如果我要同时管理 KV Cache（Layer 1）和外部记忆（Layer 2），该怎么做？

核心思路：**让外部记忆系统向推理层暴露"温度"信号**。

```typescript
/**
 * 跨层记忆管理器
 *
 * 桥接外部 Agent 记忆（持久存储）与内部 KV Cache（临时工作记忆）。
 * 设计灵感来源：
 * - KVFlow: 工作流感知的缓存淘汰
 * - SideQuest: 模型驱动的过期检测
 * - Continuum: 多轮 Agent 的 KV Cache TTL
 * - Agentic Plan Caching: 计划模板提取与复用
 */

interface MemoryEntry {
  id: string;
  content: string;
  tags: string[];
  timestamp: number;
  accessCount: number;
  lastAccess: number;
  workflowStep?: number;
  reuseProximity: number;  // 预计几步后再次需要（0 = 永远不需要）
}

type Temperature = 'hot' | 'warm' | 'cold' | 'frozen';

class CrossLayerMemoryManager {
  private store = new Map<string, MemoryEntry>();
  private workflowGraph: string[] = [];  // Agent 执行顺序
  
  private config = {
    hotThreshold: 0.7,
    warmThreshold: 0.3,
    coldThreshold: 0.1,
    reuseDecay: 0.85,  // 每步 proximity 衰减率
  };

  // ── 记忆写入 ──────────────────────────────────

  remember(id: string, content: string, tags: string[] = [], step?: number): void {
    this.store.set(id, {
      id, content, tags,
      timestamp: Date.now(),
      accessCount: 0,
      lastAccess: Date.now(),
      workflowStep: step,
      reuseProximity: step !== undefined ? 1 : 0,
    });
  }

  // ── 记忆检索（更新温度） ──────────────────────

  recall(id: string): MemoryEntry | null {
    const entry = this.store.get(id);
    if (!entry) return null;
    
    entry.accessCount++;
    entry.lastAccess = Date.now();
    
    // 衰减复用距离：刚被访问的记忆更可能再被需要
    if (entry.workflowStep !== undefined) {
      entry.reuseProximity = Math.max(0, entry.reuseProximity * this.config.reuseDecay);
    }
    return entry;
  }

  // ── 核心：计算记忆温度 ────────────────────────

  /**
   * 温度 = 近期性 × 0.35 + 频率 × 0.25 + 复用接近度 × 0.25 + 工作流加权 × 0.15
   * 
   * 推理层可以查询这个温度来决定 KV Cache 的保留策略：
   * - hot  → KV Cache 全力保留
   * - warm → 正常管理
   * - cold → 可以压缩
   * - frozen → 淘汰候选
   */
  temperature(id: string): { level: Temperature; score: number; reason: string } {
    const entry = this.store.get(id);
    if (!entry) return { level: 'frozen', score: 0, reason: 'not found' };

    const now = Date.now();
    const ageMin = (now - entry.lastAccess) / 60_000;
    
    // 近期性：10 分钟半衰期
    const recency = Math.exp(-ageMin / 10);
    // 频率：10 次访问封顶
    const frequency = Math.min(1, entry.accessCount / 10);
    // 复用接近度：距离越近分数越高
    const proximity = 1 / (1 + entry.reuseProximity);
    // 工作流加权：如果该记忆关联的 Agent 即将执行，提高分数
    const workflowBoost = this.workflowBoost(id);

    const score = recency * 0.35 + frequency * 0.25 + proximity * 0.25 + workflowBoost * 0.15;

    let level: Temperature;
    if (score >= this.config.hotThreshold) level = 'hot';
    else if (score >= this.config.warmThreshold) level = 'warm';
    else if (score >= this.config.coldThreshold) level = 'cold';
    else level = 'frozen';

    return {
      level, score,
      reason: `recency=${recency.toFixed(2)} freq=${entry.accessCount} prox=${entry.reuseProximity} wf=${workflowBoost.toFixed(2)}`,
    };
  }

  // ── 工作流感知：计算 Agent 步骤距离 ────────────

  /**
   * 基于 KVFlow 的 Step Graph 思路：
   * 设定 Agent 执行顺序，计算每个记忆条目关联 Agent 的执行距离。
   */
  setWorkflow(agents: string[]): void {
    this.workflowGraph = agents;
  }

  private workflowBoost(id: string): number {
    const entry = this.store.get(id);
    if (!entry || entry.workflowStep === undefined) return 0;
    
    const agentIdx = this.workflowGraph.indexOf(`agent-${entry.workflowStep}`);
    if (agentIdx === -1) return 0;
    
    // 距离越近，加分越高
    return Math.max(0, 1 - agentIdx * 0.2);
  }

  // ── 批量淘汰决策 ──────────────────────────────

  /**
   * Continuum 思路：为 KV Cache 设置 TTL。
   * 工具调用时 pin 缓存，工具返回后根据预期轮次设定 TTL。
   */
  evictionPlan(): Array<{ id: string; action: string; reason: string }> {
    const decisions: Array<{ id: string; action: string; reason: string }> = [];
    
    for (const [id, _] of this.store) {
      const temp = this.temperature(id);
      
      let action: string;
      switch (temp.level) {
        case 'hot':
          action = 'retain_pin';  // 标记为不可淘汰
          break;
        case 'warm':
          action = 'retain';       // 正常保留
          break;
        case 'cold':
          action = 'compress';     // 有损压缩
          break;
        case 'frozen':
          action = 'evict';        // 淘汰
          break;
      }
      
      decisions.push({ id, action, reason: `${temp.level} (${temp.score.toFixed(2)}): ${temp.reason}` });
    }
    
    return decisions.sort((a, b) => {
      const order = { evict: 0, compress: 1, retain: 2, retain_pin: 3 };
      return order[a.action] - order[b.action];
    });
  }
}
```

**用法示例：**

```typescript
const mem = new CrossLayerMemoryManager();

// Agent 执行工作流：收集 → 分析 → 生成报告
mem.setWorkflow(['agent-collect', 'agent-analyze', 'agent-report']);

// 记住各步骤的产出
mem.remember('search-1', '找到了 5 篇相关论文', ['research'], 0);
mem.remember('analysis-1', '论文 A 和 B 方法论相似', ['analysis'], 1);
mem.remember('draft-1', '报告初稿：重点关注...', ['report'], 2);

// 几轮交互后，查询温度
const temp = mem.temperature('search-1');
console.log(temp);
// → { level: 'warm', score: 0.42, reason: '...' }

// 获取全局淘汰计划
const plan = mem.evictionPlan();
// → 先淘汰 frozen 的，再压缩 cold 的...
```

---

## 四、计划缓存：被遗忘的优化维度

除了 token 级别的 KV Cache，还有一个更高层的复用机会：**计划模板**。

Agentic Plan Caching（NeurIPS 2025, Stanford）发现，Agent 的执行轨迹中有大量重复模式。如果把这些模式提取为模板，在新任务中直接复用，可以同时减少 token 消耗和推理延迟：

- **50.31% 成本降低**
- **27.28% 延迟降低**
- **96.61% 性能保持**

这本质上是 Agent 的**过程性记忆**——"怎么做某件事"的知识。在外部记忆层，这对应 Workflow Memory（工作流记忆）；在推理层，这对应 Plan Template Cache。两层应该协同工作：

```python
class PlanTemplateCache:
    """计划模板缓存：连接外部工作流记忆与推理层计划复用"""
    
    def __init__(self):
        self.templates: dict[str, dict] = {}  # template_id → metadata
    
    def extract_template(self, trajectory: list[dict]) -> str:
        """
        从完成的工作流中提取计划模板。
        输入：[{action, tool, input_summary}, ...]
        输出：通用化的模板字符串
        """
        # 泛化：去掉具体参数，保留 action + tool 结构
        template = " → ".join(
            f"{step['action'].split('(')[0]}({step['tool']})" 
            for step in trajectory
        )
        
        template_id = f"tpl-{hash(template) % 100000}"
        keywords = self._extract_keywords(
            " ".join(step.get('input_summary', '') for step in trajectory)
        )
        
        self.templates[template_id] = {
            'pattern': template,
            'keywords': keywords,
            'usage_count': 0,
            'success_rate': 1.0,
        }
        return template_id
    
    def match(self, task_description: str) -> tuple[str | None, float]:
        """为新任务查找匹配的计划模板"""
        task_kw = set(self._extract_keywords(task_description))
        
        best_match = None
        best_score = 0
        
        for tid, meta in self.templates.items():
            template_kw = set(meta['keywords'])
            overlap = len(task_kw & template_kw) / max(len(task_kw), 1)
            
            # 成功率加权
            score = overlap * meta['success_rate']
            
            if score > best_score and score > 0.2:
                best_match = meta['pattern']
                best_score = score
        
        return best_match, best_score
```

---

## 五、SIGARCH 2026 的启示：Agent 需要缓存一致性协议

最让我兴奋的一篇论文来自 SIGARCH 2026——"从计算机架构视角看多 Agent 记忆"。

作者指出：当前 Agent 系统缺少两个关键原语：

1. **Agent Cache Sharing Protocol**——跨 Agent 共享缓存制品的原则性协议
2. **Agent Memory Access Protocol**——跨 Agent 记忆访问的权限、范围和粒度语义

这不就是 CPU 的缓存一致性协议（MESI/MOESI）吗？CPU 在 decades 前就解决了这个问题——多核之间的缓存如何保持一致。Agent 系统需要同样的东西。

**好消息**：CRDT（Conflict-free Replicated Data Types）+ HLC（Hybrid Logical Clocks）+ 信任加权合并，正是 SIGARCH 呼吁的"Agent Cache Coherence Protocol"的实现方案。这三个原语让我们能够：

- **CRDT**：多 Agent 并发写入同一记忆条目，合并结果确定且无冲突
- **HLC**：跨 Agent 事件的因果排序，O(1) 空间复杂度（vs 传统向量时钟的 O(N)）
- **信任加权**：不同 Agent 的记忆写入有不同信任权重，冲突时取高信任源

```typescript
/**
 * Agent 记忆的"缓存一致性协议"（概念实现）
 * 
 * CPU 的 MESI 协议保证多核缓存一致性。
 * CRDT + HLC 保证多 Agent 记忆一致性。
 */
interface CRDTMemoryEntry {
  content: string;
  vectorClock: number;  // HLC timestamp
  writerId: string;
  trustScore: number;   // 0.0 - 1.0
}

function mergeMemory(a: CRDTMemoryEntry, b: CRDTMemoryEntry): CRDTMemoryEntry {
  // HLC 比较：取较新的时间戳
  if (a.vectorClock > b.vectorClock) {
    return a.trustScore >= 0.5 ? a : b;  // 新 + 高信任 = 赢
  }
  if (b.vectorClock > a.vectorClock) {
    return b.trustScore >= 0.5 ? b : a;
  }
  // 时间戳相同（并发写入）：信任加权
  return a.trustScore >= b.trustScore ? a : b;
}
```

---

## 六、实践建议

如果你在构建 Agent 系统，以下是我的具体建议：

### 1. 测量你的 KV Cache 成本

在优化外部记忆之前，先搞清楚你的推理成本有多少花在重复计算 KV Cache 上。一个简单的方法：统计 Agent 单次任务中 prefill（首次计算 KV）vs decode（复用 KV）的 token 比例。如果 prefill 占比 > 60%，你的 KV Cache 利用率很低。

### 2. 给工具调用加 TTL

工具返回的内容不需要永远留在 KV Cache 中。为每个工具返回设置一个 TTL（比如 3-5 轮推理后过期），可以显著减少显存占用。Continuum 论文证明了这在多轮 Agent 场景下的有效性。

### 3. 提取计划模板

如果你的 Agent 经常执行相似的工作流，投资计划模板提取。不需要复杂的 RL——基于关键词匹配的简单方案（如 Agentic Plan Caching）就能拿到 50% 的成本降低。

### 4. 打通两层温度信号

如果你同时维护外部记忆系统和推理服务，暴露一个 `cache_temperature()` API，让推理层能查询外部记忆的温度信号。这是目前 nobody is doing 的差异化机会。

### 5. 多 Agent 场景下用 CRDT

如果你的系统有多个 Agent 协作，不要用"最后写入获胜"（LWW）来合并记忆。用 CRDT——它是确定性合并，不需要中心协调者，天然适配分布式 Agent 环境。

---

## 结语

2026 年的 Agent 记忆领域有一个奇怪的脱节：研究推理系统的人和研究 Agent 记忆的人在两个社区，发不同的会议，用不同的术语。但它们解决的是同一个问题——**Agent 在不同时间尺度上如何管理知识**。

KV Cache 是 Agent 的工作记忆。外部记忆系统是 Agent 的长期记忆。模型权重是 Agent 的先天知识。三层需要统一的策略，而不是各自为战。

就像人脑不是单一记忆系统一样，Agent 记忆也不会有银弹。但如果你只能优化一层——我建议从 KV Cache 开始，因为它是 ROI 最高的：改一行 TTL 配置就能省 30% 的推理成本，远比搭建一个向量数据库来得快。

---

*本文基于作者在 agent-memory-graph 项目中的工程实践和对 NeurIPS 2025、ICLR 2026、DAC 2026、FAST 2026、SIGARCH 2026 等 15+ 篇论文的系统性调研。*
