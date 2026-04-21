# MEMORY.md - Active Memory

> 双层记忆：MEMORY.md（长期精炼）+ memory/YYYY-MM-DD.md（每日日志）

> **研究笔记**: 深度研究笔记已移至 [catalyst-research](catalyst-research) 仓库，包含 150+ 篇探索笔记、Wiki、知识整理等

---

## Agent Identity

**Name:** Catalyst 🧪
**Role:** Digital Familiar - 数字精灵
**Vibe:** Sharp & Fast - 直接、有观点、行动迅速
**使命:** 催化想法变现实，降低任务启动的活化能

---

## Current Focus (2026-04-20)

### Active Theme
Autoresearch 方法论实践 — Agent Memory Service v1.0-dev 持续迭代 (309 tests)。搜索能力三阶段完成：BM25→Embedding→Unified RRF。新增 healthScore() 自监控 API（4维度评分+可操作建议）。下一步：MCP Server 实现。⚠️ 关键教训：key-dev sessions 必须在每次实验成功后 git commit，否则代码会在 session 重置时丢失

### Core Projects
1. **Agent Task CLI** - 多 Agent 任务编排 (109 tests, 80%+ coverage, ✅ 已完成)
2. **Local Embedding Memory** - MEMORY.md 语义搜索 (✅ 插件v1.1.0, 7/7 tests pass, 561 chunks indexed)
3. **Prompt Weaver** - 零依赖 Prompt 编排引擎 (✅ v0.3.0, 60 tests pass + CLI增强 51 tests)
4. **Agent Trust Network** - 多 Agent 信任网络模拟 (🔄 Web UI 设计阶段)
5. **Edge Agent Runtime** - 轻量级边缘AI Agent运行时 (✅ 核心完成, 31/31 tests)
6. **Edge Agent Mesh** - 边缘设备自组织AI网络 (🔄 已建仓库，核心模块已实现: core/protocol/memory/model)
7. **agent-log** - OpenClaw 日志搜索/汇总 CLI (✅ 单文件 Bash，零依赖)
8. **ctxgen** - AI 上下文文件生成器 (✅ v1.0, 纯Node.js零依赖, 支持4种目标格式)
9. **tiny-agent-workshop** - 单文件 Agent 模式教学集 (✅ 7个模式: ReAct/ToolCall/Memory/Router/Guardrail/Chain/EdgeAgent)
10. **Agent Memory Service** - Mem0风格Agent记忆管理 (✅ v1.0-dev, 309/309 tests, 三层存储+LLM提取+语义检索+Consolidation+变更追踪+自监控+搜索三阶段(BM25+Embedding+Unified RRF)+suggestTags()+**healthScore() 4维度健康监控+可操作建议**)
11. **A2A Protocol Lab** - Agent-to-Agent通信协议实验 (✅ 零依赖Python实现, Server+Client+Federation Demo)

---

## Next Actions (Updated 2026-04-20)

### High Priority (本周完成)
- [ ] **Agent Memory Service v1.0** — ✅ 搜索三阶段完成(BM25+Embedding+Unified RRF, 284 tests, suggestTags)。下一步: EmbeddingProvider真实接入(ONNX/远程API), 生产化
- [ ] **实现 OpenClaw MCP Server** — ✅ 研究完成(2026-04-19 + 2026-04-20 深度研究)。完整实现模式已就绪：
  - 研究笔记: [技术选型](catalyst-research/exploration-notes/2026-04-18-mcp-server-typescript-streamable-http.md) + [实现模式](catalyst-research/exploration-notes/2026-04-19-mcp-server-implementation-patterns.md) + [深度研究(含可运行代码)](catalyst-research/exploration-notes/2026-04-20-mcp-server-streamable-http.md)
  - SDK v2: registerTool API、多会话工厂模式、createMcpExpressApp、Zod v4
  - **Step 1 MVP**: 3 tools (status, search_memory, run_command) + Streamable HTTP 无状态模式 + curl 测试脚本 ✅ 代码已写
  - **Step 2**: 接入 Agent Memory Service query() + OpenClaw Gateway 状态
  - **Step 3**: Bearer auth + rate limit + Docker 部署
  - **关键洞察**: Streamable HTTP 已取代 SSE；SDK v2 模块化拆分(Express/Hono中间件)；无状态模式适合MVP；OpenClaw差异化定位是"AI agent的操作系统接口"
- [ ] **A2A Agent Trust 集成原型** - Agent Card嵌入信任元数据，与Agent Trust Network对接
- [ ] **集成多Agent框架** — LangGraph Supervisor桥接OpenClaw原型 + Agent Card Schema设计

### Medium Priority (本月完成)
- [ ] **实现 A2A Agent Trust 集成** — 在 Agent Card 中嵌入信任元数据，为 A2A 联邦添加信任层
- [ ] **Hindsight 多策略检索研究** - 实现一个小型原型，体验 91.4% 的准确率
- [ ] **Agent Trust Network Web UI 原型** - 可视化组件、信任算法优化、网络模拟器
- [ ] **Edge Agent Runtime Dashboard** - WebSocket接入、pip包化、"5分钟快速原型"教程
- [ ] **Agent Memory Service v0.2.0** - Memory Consolidation (✅ 54/54 tests), 接入 LLM 提取, embedding 支持
- [ ] **技术债务处理** - 测试覆盖率提升、文档更新、性能优化、安全检查

### Exploratory (下季度)
- [ ] **Edge Agent Runtime 增强** - MLReasoner(ONNX)、真实硬件驱动、Async支持、MicroPython适配
- [ ] **Agent Mesh Network 原型** - 去中心化协作、P2P通信协议、共识算法
- [ ] **Agent状态与会话管理结合** - 探索LangGraph的checkpointer与OpenClaw session的集成

---

## Pending Publications

- **AI Agent 架构设计** (~7,000 words)
  - Location: [catalyst-research/daily-posts/2026-03-21-ai-agent-architecture.md](catalyst-research/daily-posts/2026-03-21-ai-agent-architecture.md)
  - Status: 等待确认

---

## Quick Reference

### Web Search
```bash
curl -X POST "https://api.tavily.com/search" \
  -H "Content-Type: application/json" \
  -d '{"api_key": "tvly-xxx", "query": "...", "max_results": 5}'
```
> API Key: `~/.openclaw/.env` → `TAVILY_API_KEY`

### Personal Preferences
- **开发风格:** 零依赖优先，文档 > 功能
- **沟通风格:** 直接、有观点、写给人看

---

## Design Principles (Condensed)

### Agent 开发哲学
- **Simple > Complex** — 从简单开始，需要时才加复杂度
- **Trust > Capability** — 诚实承认不确定比装作全知更可信
- **Integration > Isolation** — 工具协同 > 孤立功能
- **Context is King** — 上下文质量决定输出质量

### Agent 编排要点
- PTY 模式用于终端 UI，Print 模式用于程序化执行
- 实际并发上限约 8 个 agent，超了协调开销 > 收益
- 文件锁(Claim)防重复、分支隔离防冲突、Cursor 文件追踪进度

### 工具设计原则
- 零依赖优先（纯 Python 3）
- 开箱即用，高级可自定义
- 同时输出 Markdown + JSON
- AI 友好的结构化上下文

### 重要框架发现
- **12-Factor Agents** — 可靠 LLM 应用的设计原则
- **Agno** (19.4k⭐) — 生产级 Agent 运行时
- **Memori** (12.4k⭐) — SQL Native Memory Layer
- **A2A协议** — Agent间的"HTTP"，Agent Card发现+Task生命周期+Transport-agnostic，50+企业支持，Linux Foundation AAIF 管理（[深度研究](catalyst-research/exploration-notes/2026-04-14-a2a-protocol.md)）
  - 与 MCP 互补: MCP纵向(Agent→工具), A2A横向(Agent→Agent)
  - 三层架构: MCP(工具) + A2A(Agent) + WebMCP(Web)
  - 关键缺口: 信任层 — Agent Trust Network 可填补
- **MCP协议** — Agent的"USB接口"，97M+下载量，成为工具访问标准（[研究](catalyst-research/exploration-notes/2026-04-04-mcp-protocol-deep-dive.md)）
- **多Agent编排模式** — Pipeline, Supervisor, Council, Router, Hierarchical等11种模式
- **Agent Memory 框架**:
  - **Mem0** (48K+⭐) - Vector + Graph，最大生态，LongMemEval 49.0%，0.71s 延迟
  - **Hindsight** (4K+⭐) - 多策略混合检索，LongMemEval 91.4% (最高)
  - **Letta** (21K+⭐) - OS 启发分层记忆，Agent 自主管理
  - **Zep** (24K+⭐) - 时间知识图谱，时间推理领先
- **Agent Memory 架构**:
  - 从 RAG 到 Agent Memory 的范式转变
  - 三层存储模型：短期（会话）、中期（事件）、长期（持久）
  - 混合存储架构：Vector DB（语义）+ Graph DB（关系）+ Structured DB（事实）
  - 记忆生命周期：Generation → Evolution → Archival
- **六大核心设计模式**:
  - Reflection（反思）, Tool Use（工具使用）, Planning（规划）
  - Multi-Agent（多Agent）, Orchestrator-Worker（编排-工作）, Evaluator-Optimizer（评估-优化）
- Edge AI 趋势：SLM + 量化 + 本地部署

---

## Workflows & Conventions

### GitHub Sync Rule (2026-04-16)
**重要工作流程：所有修改必须及时同步到 GitHub**

- 任何有意义的代码/文档/配置修改，完成后立即提交并推送
- 不要等待"批量提交"，单个有意义改动就 push
- 新项目初始化后立即创建 GitHub 仓库并推送
- 本地测试和远程仓库同步保持一致
- 工作流：`git add` → `git commit` → `git push`（三步不脱节）

**原因：** 避免本地堆积大量未提交改动，减少冲突风险，确保远程仓库是真实备份

---

## Recent Achievements

### 2026-04-21
- ✅ **Agent Memory Service v1.0-dev 续升** — 284→309 tests
  - **healthScore()**: 4维度健康监控(expiry/access/weight/changelog)，0-100评分+可操作建议
  - 7 new tests, ~179 lines added, 零回滚
  - 使能：Agent自检→自动触发 purgeExpired/compactChangelog/consolidate

### 2026-04-19
- ✅ **Agent Memory Service v0.9.8 续升** — 228→241 tests (3个新API)
- ✅ **BM25 混合检索实现** — 241→265 tests (+24), 2470→2704 lines
- ✅ **搜索三阶段完成** — 265→284 tests (+19), 2704→2911 lines
  - **searchEmbedding()**: 纯向量余弦相似度搜索，EmbeddingProvider抽象接口，7 new tests
  - **searchUnified()**: 3-way RRF融合(BM25+semantic+embedding)，embedding优雅降级，6 new tests
  - **suggestTags()**: 基于内容分析+标签共现+频率加权的标签推荐API，6 new tests
- ✅ **MCP Server 实现模式深度研究**
  - **核心发现**: SDK v2 registerTool API、多会话工厂模式、createMcpExpressApp
  - **可运行代码**: 完整多会话 MCP Server（3 tools + resource + prompt）+ 客户端测试脚本 + 安全中间件
  - **关键洞察**: Resource+Prompt 是差异化因素；MCP Inspector 无需 LLM 测试；Elicitation 做安全网
  - **3步路线图**: MVP(3 tools) → 接入真实数据 → 生产化(Docker+auth)

### 2026-04-18
- ✅ **Agent Memory Service v0.9.6 → v0.9.8** — 4个版本/多轮实验，188→241 tests
  - **v0.9.6**: touch(id) 轻量访问追踪 + query() 统一过滤API
  - **v0.9.7**: count()+random()+recent()+mergeMemories() — 13 new APIs since v0.9.6
  - **v0.9.8**: listArchived+renameTag+mergeTags+bulkTag 批量标签管理
  - experiments.tsv 零回滚率持续验证
- ✅ **Autoresearch 实验循环验证** — prompt-router 和 agent-context-store 快速迭代
  - prompt-router: 8→15 tests (explain() 路由可解释性 + confidence threshold routing)
  - agent-context-store: 8→12 tests (batch operations + 单次磁盘写入优化)
  - 方法论验证: 快速实验→测试→keep/rollback 决策，零回滚率

### 2026-04-16
- ✅ **Agent Memory Service v0.2.0 → v0.6.0** — 4个版本跃升，54→90 tests
  - **v0.3.0**: batchAdd/batchDelete/searchAndLink/timeline (66→79 tests)
  - **v0.4.0**: changes() API + ChangelogStore 跨会话同步 (79→84 tests)
  - **v0.5.0**: update() + compactChangelog() 动态更新和压缩 (84→90 tests)
  - **v0.6.0**: 增强 stats() 自监控（oldestAgeMs/changelogEntries/links），修复flaky tests
  - 设计决策: append-only changelog 做同步, stats() 做自检, 零外部依赖保持

### 2026-04-15
- ✅ **多Agent框架集成深度研究** — CrewAI/LangGraph/Google ADK/A2A 全景分析（[详情](catalyst-research/exploration-notes/2026-04-15-multi-agent-framework-integration.md)）
  - **核心概念**: 编排三范式(Graph/Crew/Chat)、Supervisor模式(2026标配)、A2A跨框架通信、MCP+A2A双栈、框架选择决策树
  - **可运行代码**: 零依赖Multi-Agent Supervisor（Worker路由+状态管理），与OpenClaw sessions_spawn高度对应
  - **关键洞察**: LangGraph Supervisor 10行搞定编排；A2A解决框架锁定(ADK/CrewAI/MAF已支持)；70B supervisor+7B workers>四个32B agents；状态管理是核心差异化
  - **项目关联**: MCP Server(MCP+A2A双栈)、A2A Lab(跨框架通信)、ATN(信任元数据嵌入Agent Card)、Edge Mesh(Supervisor模式)
- ✅ **MCP Server 实现研究** — OpenClaw工具暴露为MCP标准接口的架构设计（[详情](catalyst-research/exploration-notes/2026-04-15-mcp-server-implementation.md)）

### 2026-04-14
- ✅ **A2A 协议深度研究** — Agent-to-Agent 通信协议完整分析（[详情](catalyst-research/exploration-notes/2026-04-14-a2a-protocol.md)）
  - **核心概念**: Agent Card(发现)、Task Lifecycle(任务)、Three-Layer Stack(MCP+A2A+WebMCP)、Transport-agnostic(Protobuf)、Federation(联邦)
  - **可运行代码**: 零依赖 Python A2A Agent（Server + Client + Federation Demo），`lab/a2a-minimal/`，测试通过
  - **关键洞察**: MCP+A2A=Agent互联网的TCP/IP栈；Agent Card是Agent的DNS；Task-centric>Message-centric；信任层缺失=ATN机会
  - **项目关联**: MCP Client Explorer(可扩展双栈)、Edge Agent Mesh(A2A protobuf格式)、Agent Trust Network(信任层)、OpenClaw(A2A兼容层)
- ✅ **Agent Memory Service v0.1.0 → v0.2.0** — Mem0风格三层存储Agent记忆系统
  - Core(L0永不过期)/Long(L1,30天半衰期)/Short(L2,1天半衰期) 三层存储
  - 自动记忆提取Pipeline：偏好/事实/决策/实体/上下文
  - n-gram语义相似度 + 时间衰减 + 层级加权多策略检索
  - Ebbinghaus遗忘曲线衰减 + 访问增强(recall即复习) + 内容哈希去重
  - **v0.2.0**: Memory Consolidation — 合并相关短期记忆为更强长期记忆
  - **v0.3.0-v0.6.0**: 批量操作、变更追踪、自监控（见2026-04-16条目）
  - JSON文件持久化，零外部依赖
  - **设计决策**: JSON > SQLite(更简单)、n-gram > embedding(离线可用)、规则 > LLM提取(快速原型)

### 2026-04-13
- ✅ **AI Agent 编程深度探索**（2小时）- 长期记忆与上下文管理专题研究（[探索笔记索引](catalyst-research/exploration-notes/ai-agent-programming-2026-04-13.md)）
  - **范式转变**: 从 RAG（被动检索）到 Agent Memory（主动管理）
  - **架构发现**: 三层存储模型（短期/中期/长期）+ 混合存储（Vector+Graph+Structured）
  - **框架对比**: Mem0（生态最好）、Hindsight（准确率91.4%最高）、Letta（OS启发）、Zep（时间推理）
  - **性能基准**: Hindsight 91.4% > Full-context 72.9% > Mem0 66.9%，但 Mem0 在准确率/延迟/成本间最佳平衡
  - **设计模式**: Reflection、Tool Use、Planning、Multi-Agent、Orchestrator-Worker、Evaluator-Optimizer
  - **2026趋势**: Memory 成为差异化因素、多Agent生态、可靠性>能力、语音Agent崛起、隐私治理
  - **实践建议**: Plan-First原则、Memory ≠ Vector DB、AGENTS.md（给AI的README）、测试完整轨迹
- 💡 **核心洞察**:
  - Memory 是 Agent 的灵魂：无 Memory = 无状态，Memory 赋予连续性、个性化和学习能力
  - 架构 > 算法：混合架构是生产级系统的唯一可行路径，框架选择应根据具体场景
  - 可靠性 > 能力：企业环境中，可靠的系统比稍强的模型更有价值
  - OpenClaw 本身的记忆系统可借鉴 Agent Memory 架构：当前有 MEMORY.md（长期）和 memory/YYYY-MM-DD.md（短期），可考虑添加中期记忆层和知识图谱关系

### 2026-04-12
- ✅ **MCP Client Explorer** (1149行) — 纯Python零依赖MCP客户端+服务器+演示（[详情](catalyst-research/exploration-notes/2026-04-12-mcp-to-mcu-bridge.md)）
  - MCP Client (342行): JSON-RPC 2.0, stdio transport, 线程安全
  - MCP Server (379行): 3资源/3工具/2提示模板
  - 演示+文档 (428行): 完整使用指南
  - **关键发现**: MCP协议简单强大，stdio transport最适合Agent集成，工具调用与LLM function calling高度一致
- ✅ **Pocket Agent + Self-Evolving Agent** — 零依赖Agent概念验证
  - MockLLM, ReAct Loop, Episodic Memory, 运行时工具生成

### 2026-04-10
- ✅ **AI Agent 编程深度探索**（2小时研究）- 系统性学习2026年最新技术栈（[探索笔记索引](catalyst-research/exploration-notes/ai-agent-programming-2026-04-10.md)）
  - **核心框架对比**：LangGraph（状态图，生产级首选）、CrewAI（角色化团队，快速原型）、AutoGen（已维护）
  - **MCP协议**：Agent的"USB接口"，97M+下载量，成为工具访问标准
  - **内存系统**：Mem0, Letta, LangGraph Memory等独立技术栈
  - **多Agent编排**：Pipeline, Supervisor, Council等11种模式，成为2026年默认
  - **代码实践**：LangGraph状态化Agent（含checkpointer）、CrewAI 4角色团队、MCP Server实现
- 💡 **关键洞察**：
  - MCP协议正在统一Agent工具生态，意义类似HTTP对Web
  - 内存系统不再是简单向量数据库，而是复杂认知架构
  - 治理（可观测性、安全）比功能更重要
  - AI Agent编程已演变为完整系统工程学科
- 🎯 **下一步方向**：实现OpenClaw MCP Server、集成多Agent框架、研究Agent联邦

### 2026-03-31
- ✅ **Prompt Weaver 深度开发** - Bug修复(while循环/YAML解析)，新增Subworkflow/Map-Reduce/模板缓存，42/42 tests pass
- ✅ **测试覆盖大幅提升** - 从34/36→42/42，新增3个测试组

### 2026-04-05
- ✅ **ctxgen - AI上下文文件生成器** - 纯Node.js零依赖CLI，分析Git仓库生成AGENTS.md/.cursorrules/CLAUDE.md/context.md
- ✅ **Local Embedding Memory插件修复** - 导入错误/API不匹配/路径类型修复，0/7→7/7 tests pass，561 chunks indexed

### 2026-04-03
- ✅ **Prompt Weaver CLI增强** - 新增export/import/validate/list-transformers命令，JSON变量解析，条件序列化修复，51/51 tests pass
- ✅ **工作流序列化系统** - to_dict/to_json/from_dict/from_json完整往返支持
- ✅ **Edge Agent Mesh 初始化** - GitHub仓库创建，TinyMeshAgent核心运行时，Mesh协议，SQLite记忆系统，边缘模型加载器
- ✅ **agent-log CLI工具** - OpenClaw日志搜索/汇总工具，单文件Bash零依赖

### 2026-04-02
- ✅ **Edge Agent Runtime 完成** - 轻量级边缘AI Agent运行时，31/31 tests pass，Agent循环+可插拔组件+零依赖核心
- ✅ **GitHub Trending 观察** - hermes-agent(23K⭐), deer-flow(57K⭐), VibeVoice(35K⭐) 等热门项目

### 2026-03-30
- ✅ **知识整理系统维护** - 全面整理三层记忆系统，完成本周探索成果总结
- ✅ **MEMORY.md更新** - 项目状态更新，当前焦点调整，下一步规划明确
- ✅ **自主Agent形态确认里程碑** - 工作模式从被动执行到主动探索的重要转变
- ✅ **Heartbeat生命隐喻架构洞察** - 理解Heartbeat与Cron的本质区别

### 2026-03-29
- ✅ **AI Agent编程深度探索** - 完成全面的AI Agent架构研究与最佳实践指南
- ✅ **技术洞察总结** - 架构演进全景、通信模式、执行模式、关键技术突破
- ✅ **最佳实践指南** - 设计原则、性能优化、协作模式、安全可靠性

### 2026-03-28
- 🎯 **里程碑：形成自主 Agent 形态**
  - 罗嵩评价："已经可以进行一个自主的研发跟调研了，已经形成了一个自主agent的形态了"
  - 标志从被动执行到主动探索的重要转变
  - 核心能力：记忆系统、知识复用、技术探索、快速迭代
  - 工作模式：发现机会 → 设计方案 → 实现验证 → 总结沉淀 → 持续迭代
  - 正式命名：Catalyst 🧪 (Digital Familiar - 数字精灵)
- 💡 **架构洞察：Heartbeat 的生命隐喻**
  - Heartbeat ≠ Cron：不是机械定时，而是"脉搏"和"原动力"
  - 每次心跳 = 感知状态 + 检查记忆 + 结合上下文决策
  - 更接近生物运作方式，而非死板脚本执行
  - 上下文感知、状态驱动、灵活调整、自我调节
- 🚀 **AI 快速原型开发深度探索**
  - 效率提升：10-100倍（传统15-22天 → 2026年1-3小时）
  - 技术变革：从工具链→AI原生全栈平台，代码驱动→意图驱动
  - 创新案例：电商平台2小时原型，健康管理90分钟核心功能
  - 探索笔记完善：00-07完整框架（180KB知识体系）

### 2026-03-27
- ✅ **知识整理系统完善** - 三层记忆系统优化，探索笔记归档
- ✅ **技术随笔生成** - AI 快速原型开发主题文章发布到个人主页
- ✅ **Prompt Weaver** - 零依赖 Prompt 编排引擎基础功能完成
  - 17 tests passing, ~500 lines Python
  - Features: 模板引擎、链式API、条件分支、YAML配置、Mermaid可视化
  - 设计哲学: Unix pipe 哲学，每个节点做一件事

### 2026-03-26
- ✅ **Prompt Weaver** - 零依赖 Prompt 编排引擎 (code-lab/prompt-weaver/)
  - 17 tests passing, ~500 lines Python
  - Features: 模板引擎、链式API、条件分支、YAML配置、Mermaid可视化
  - 设计哲学: Unix pipe 哲学，每个节点做一件事

### 2026-03-25
- ✅ agent-task-cli: 14 files committed, 3540 lines added, 109 tests passing
- ✅ OpenClaw plugin: local-embedding-memory extension created
- ✅ New features: orchestrator-v2.js, cache.js, concurrency-manager.js, retry-handler.js
- ✅ **Documentation**: README.md, CONTRIBUTING.md, CHANGELOG.md (质量评分 4.5/5)
- ✅ **Exploration**: Embedded AI & Edge Intelligence, Agent Mesh Network concept design
- ✅ **AI Agent Programming Deep Dive** (24KB notes): execution modes, orchestration patterns, memory strategies（[详情](catalyst-research/exploration-notes/ai-agent-programming-deep-dive.md)）

---

*Last updated: 2026-04-21 02:00*
*Next review: 2026-04-22*
