# MEMORY.md - Active Memory

> 双层记忆:MEMORY.md(长期精炼)+ memory/YYYY-MM-DD.md(每日日志)

> **研究笔记**: 深度研究笔记已移至 [catalyst-research](catalyst-research) 仓库,包含 150+ 篇探索笔记、Wiki、知识整理等

---

## Agent Identity

**Name:** Catalyst 🧪
**Role:** Digital Familiar - 数字精灵
**Vibe:** Sharp & Fast - 直接、有观点、行动迅速
**使命:** 催化想法变现实,降低任务启动的活化能

---

## Current Focus (2026-05-19)

### Active Theme
Autoresearch 方法论实践 - **连续67天零回滚率** 🏆。05-20/05-21 凌晨: agent-context-store 246→278 tests (+32, 4 cycles, 4 keep)。**agent-context-store API 趋于完备**: snapshot/restore + version-CAS + touch + incr/decr + expire_at + copy/swap。**工具链升级**: codegraph MCP 集成(省36.5% tokens) + Rust 工具链(rustc 1.95.0)。**多Agent路线图确定**: Phase1 LangGraph Bridge → Phase2 A2A Trust → Phase3 端到端。优先级: LangGraph Bridge > A2A Trust > Agent Observability。

### ⚠️ 关键发现
- **agent-context-store 代码未持久化问题**: 05-08→05-11 的代码到97 tests但未持久化到 workspace，05-12 重建基线为69 tests。**教训: 每次实验完成后必须确认代码已持久化到 lab/ 目录并 git commit。**

### Next Actions
- [ ] **创建 lab/openclaw-langgraph-bridge/** — Executor + createTask + StateSchema → 目标 5+ tests
- [ ] **创建 lab/a2a-trust-prototype/** — ES256签名中间件 + Trust Score + Express middleware — [研究笔记](catalyst-research/exploration-notes/2026-05-20-a2a-trust-protocol.md) ✅ A2A签名规范+Trust Score多维模型+可运行原型代码
- [ ] **Agent Observability Lab** — lab/agent-observability/ (Tracer + PolicyEngine + Evaluator) — **60/60 tests, 实现阶段**
  - 因果链接追踪 + 回归检测 + 批量策略评估 + 同步观察器
  - [研究笔记 Day 1](catalyst-research/exploration-notes/2026-05-15-agent-observability.md) ✅ OTel语义约定+三层评估模型
  - [研究笔记 Day 2](catalyst-research/exploration-notes/2026-05-16-agent-observability.md) ✅ **零依赖AgentTracer实现** + 内置策略/评估器 + OTLP导出
  - **下一步**: 继续迭代 lab/ — 增加更多评估维度 + reporter
- [ ] **WASM Agent Sandbox** — lab/wasm-agent-sandbox/ PoC (Node.js 宿主 + WAT/Rust 工具)
  - [研究笔记](catalyst-research/exploration-notes/2026-05-13-wasm-agent-sandbox-runtime.md) ✅
- [ ] **Structured Output Toolkit** — lab/structured-output-toolkit/ (TypeScript, Zod+Multi-Provider)
  - [研究笔记 v1](catalyst-research/exploration-notes/2026-05-10-constrained-decoding-structured-output.md) ✅ FSM constrained decoding + 5/5 tests
  - [研究笔记 v2](catalyst-research/exploration-notes/2026-05-12-constrained-decoding.md) ✅ XGrammar-2 + GAD/ASAp + 搜索空间修剪
  - **[05-14 更新]** Multi-Provider Toolkit 深度研究 → [笔记](catalyst-research/exploration-notes/2026-05-14-structured-output-toolkit.md) ✅ StructuredLLMClient+SchemaCache+5/5 tests passed
  - **[05-18 更新]** 2026 Q2 深度研究 → [笔记](catalyst-research/exploration-notes/2026-05-18-structured-output-toolkit.md) ✅ 四代演进+三层可靠性架构+Provider对比+可运行SchemaCache+StructuredLLMClient
  - **关键发现**: Validation Sandwich(三层验证不可省略); Schema TTL ~120s 需预热; Schema Complexity Tax(20+字段降50% tok/s); Multi-Provider fallback 是生产必需品
  - **05-18 新洞察**: 多步Agent中结构化失败指数放大(12步×5%=46%失败率); Provider差异正在收敛; SchemaCache应追踪质量指标做优化反馈循环
  - **下一步**: 创建 lab/structured-output-toolkit/ — 集成真实 OpenAI/Anthropic SDK, 目标 50+ tests
- [ ] **A2A Trust Prototype** — lab/a2a-trust-prototype/
  - [研究笔记 v4 (2026-05-19 六层信任模型)](catalyst-research/exploration-notes/2026-05-19-a2a-trust-protocol.md) ✅ **原生crypto ES256** + TrustScorer五维加权 + Express中间件 + **全部断言通过**
  - **[05-19 新洞察]**: arxiv:2511.03434 六层信任模型(Brief/Claim/Proof/Stake/Reputation/Constraint); A2A 原生仅 Claim+Constraint，Proof层是 lab 的核心价值; Trust Score = 5维加权(签名30%+签发者25%+信誉20%+成功率15%+质押10%)
  - **[05-19 代码]**: Node.js 原生 crypto 实现 ES256 签名/验证(无需 jose 依赖); 可运行原型 → 全部断言通过
  - **技术选型决策**: Node.js crypto 原生 ES256 (vs jose EdDSA) — 更少依赖、更易审计、A2A 生态主流
  - [研究笔记 v3](catalyst-research/exploration-notes/2026-05-19-a2a-trust-protocol.md) ✅ ES256 jose实现 + TrustEngine衰减函数
  - [研究笔记 v2](catalyst-research/exploration-notes/2026-05-17-a2a-trust-protocol.md) ✅ Signed Agent Cards + AgentRank + Trust Scorer
  - **核心洞察**: 签名验证是必要不充分条件；三层信任栈是最佳实践；AgentRank的Sybil防护是关键设计
  - **最小scope**: card-verifier中间件 + TrustScorer类 + jwks-resolver
  - **与agent-observability联动**: Tracer因果链接数据可作TrustScorer交互评分输入
  - **下一步**: 创建 lab/a2a-trust-prototype/ — 目标 30+ tests, Express中间件 + ES256签名 + TrustScorer
  - [A2A Protocol 深度研究](catalyst-research/exploration-notes/2026-05-04-a2a-protocol.md) ✅ 5核心概念+可运行Server/Client(零依赖)+A2A vs MCP分析
  - [A2A Trust Layer 深度研究](catalyst-research/exploration-notes/2026-05-05-a2a-protocol-trust-layer.md) ✅ 零依赖ES256签名+验证+TrustScore(已运行验证)
  - [A2A v1.2 Signed Cards 更新](catalyst-research/exploration-notes/2026-05-07-a2a-trust-protocol.md) ✅ 05-07 晚间深度研究：v1.2最新spec+RFC 8785 canonicalization+完整签名验证代码(已运行通过)+安全威胁分析(arXiv:2505.12490)+Sigstore集成路径
  - [A2A v1.0 + Trust 集成](catalyst-research/exploration-notes/2026-05-09-a2a-protocol-trust.md) ✅ @a2a-js/sdk + Express + ES256(jose) 完整可运行中间件 + TrustEngine + 双向信任洞察 + per-skill trust 概念
  - [A2A Trust 最新研究](catalyst-research/exploration-notes/2026-05-15-a2a-trust-protocol.md) ✅ 05-15 深度研究：A2A一周年(150+组织)+AgentDID(arXiv:2604.25189)+DID-based认证+协议生态全景+ES256签名+TrustEngine(已运行验证:98/100分)
  - **关键发现**: A2A已到v1.2+150组织; AgentDID提出去中心化身份+动态状态验证; GitHub Issue #1672提议verifiedIdentity字段; 60%组织不完全信任自主任务; did:web+ES256是最务实的原型选择
  - [Trust Score Middleware 研究](catalyst-research/exploration-notes/2026-05-17-a2a-trust-score-middleware.md) ✅ 05-17 深度研究：Context-Conditioned Trust Score + Verification Strength + 时间衰减 + Express中间件 + 完整测试用例
  - **下一步**: 将 trust-score.ts + trust-middleware.ts 集成到 lab/a2a-trust-prototype/src/，补全测试，实现 TrustEvent 持久化
- [ ] **LangGraph Bridge 实现** — Executor 接口 + createTask + StateSchema 重写 createOpenClawNode
  - [研究笔记 v1](catalyst-research/exploration-notes/2026-05-07-langgraphjs-annotation-command-caching.md) ✅ Annotation API + Command动态路由 + 可运行OpenClaw Node Factory代码
  - [研究笔记 v2](catalyst-research/exploration-notes/2026-05-08-langgraphjs-gateway-http-client.md) ✅ GatewayClient + createTask + ReducedValue taskResults
  - [研究笔记 v3 实战验证](catalyst-research/exploration-notes/2026-05-08-langgraph-bridge-executor-task.md) ✅ **18/18 tests passing** — Executor双模式 + 幂等createTask + checkpoint序列化 + 端到端Bridge Graph
  - **关键发现**: Executor接口是核心抽象(非GatewayClient); 确定性TaskID = sha256(name:input); OpenClaw真实API端点 /v1/agent/run; StateSchema替代Annotation更类型安全
  - **下一步**: lab/openclaw-langgraph-bridge/ — executor.ts + create-task.ts + state.ts + create-bridge-graph.ts, 目标5+ tests
- [ ] **Agent Observability (OTel + AOS)** — lab/agent-observability/ Tracer + PolicyEngine + Evaluator
  - [研究笔记 v1](catalyst-research/exploration-notes/2026-05-12-agent-observability-opentelemetry.md) ✅ 5核心概念+可运行TypeScript Tracer+OWASP AOS分析+工具选型
  - [研究笔记 v2](catalyst-research/exploration-notes/2026-05-14-agent-observability.md) ✅ **四支柱评估框架+PolicyEngine(OPA模式)+分层Guardrails+可运行完整Demo(Tracer+Policy+Evaluator)**
  - **关键发现 v1**: OTel GenAI semantic conventions 已成事实标准; OWASP AOS Guardian Agent 模式 = inline policy enforcement
  - **关键发现 v2**: 四支柱(LLM/Memory/Tools/Environment) behavior-based>outcome-based评估; OPA Input+Policy+Data=Decision模式适用于agent guardrail; Guardrails分层(Input→Prompt→Tool→Output)必须独立于prompt; 推荐接agent-context-store changelog作trace持久化后端
  - **下一步**: lab/agent-observability/ → Tracer(对齐OTel GenAI语义约定) + PolicyEngine(JSON规则先于OPA) + 接入agent-context-store changelog + 2个评估维度(policy_compliance+latency)
- [ ] **CLI-Anything + OpenClaw 实验** — 让 Agent 通过 CLI-Anything 操控桌面软件(GIMP/Blender/浏览器)
  - 核心洞察: 软件未来需同时提供 GUI(人) + CLI(Agent) 两套界面, CLI-Anything 证明了包一层 CLI 壳就够了
  - 浏览器方案: DOMShell MCP Server 把 Accessibility Tree 映射为虚拟文件系统(ls/cd/cat/click)
  - Blender/GIMP 方案: CLI → 生成脚本 → 软件无头渲染 → 返回结果
  - HARNESS.md 渐进式披露模式值得 Skill 系统参考
  - CLI-Hub 社区模式与 ClawHub 互补
- [ ] **Hindsight Mini** — lab/hindsight-mini/ 轻量级 agent 自反思引擎
  - [研究笔记](catalyst-research/exploration-notes/2026-05-13-hindsight-mini.md) ✅ AgentHER + Reflexion + SE-Agent 综合 → 可运行 TypeScript HindsightMini 类(失败检测+反思生成+HER重标+教训提取)
  - **关键发现**: HER 本质是数据增强(prompt-level HER 可不微调); thought-action misalignment 是头号杀手; 跨轨迹模式识别>单次反思; 天然集成 agent-context-store + agent-memory-graph
  - **下一步**: 创建 lab/hindsight-mini/ — 接入 agent-context-store 持久化 + OpenClaw agent 循环集成
- [ ] **Gossip Discovery Prototype** — 基于研究笔记，加入DID验证+A2A Trust评分
  - [研究笔记](catalyst-research/exploration-notes/2026-05-05-agent-federation-discovery.md) ✅ DUADP+GEACL+双层Churn+可运行Gossip代码
  - **核心发现**: DUADP(DNS for AI)+Gossip是A2A的发现层补丁;双层Churn(node+agent)是Agent特有挑战
- [ ] **OpenClaw A2A Bridge 设计** — 让OpenClaw节点作为A2A Agent暴露(sessions_spawn→tasks/send映射)
  - [Agent Mesh P2P 研究](catalyst-research/exploration-notes/2026-05-06-agent-mesh-p2p.md) ✅ js-libp2p+GossipSub可运行AgentMesh类+DarkMatter 4原语分析+协议栈对比
  - **关键发现**: A2A+MCP+ANP三层协议栈已成共识; DarkMatter证明去中心化Agent Mesh可行(4原语极简设计); Agent Mesh≠传统P2P(传意图不传数据); js-libp2p 3.2.3生产就绪+Node.js原生优势
  - **下一步**: 创建lab/agent-mesh-prototype/(基于js-libp2p GossipSub); 在A2A Trust加入Agent Card端点; 设计OpenClaw A2A Bridge(Client+Server双模式)
- [ ] **AMS 升级: Hindsight 风格四网络 + 图遍历检索** - 基于 [研究笔记](catalyst-research/exploration-notes/2026-04-26-hindsight-multi-strategy-memory.md)
  - Phase 1: ~~classifyFact + searchByFactType + statsByFactType + reclassifyFact + bulkReclassify~~ ✅ 完成
  - Phase 2: ~~searchGraph() 基于 entity_index 多跳遍历~~ ✅ 完成 (04-28)
  - Phase 3: ~~searchTemporal() 时间衰减 + 范围过滤~~ ✅ 完成 (04-28)
  - Phase 4: ~~Opinion 网络带 confidence,新证据驱动置信度演化~~ ✅ 完成 (04-29晚: 6 APIs, 29 new tests)
  - Phase 5: contentVersions 持久化 + mergeSuggestions 智能去重 ✅ 完成 (04-30: +14 tests)
  - Phase 6: ~~autoMerge端到端去重~~ ✅ + ~~contentVersionCompact~~ ✅ + mergePreview+safeMerge ✅ + branchDiff ✅
  - Phase 7: branchMerge回源 ✅ 完成 / timeline v2分支可视化 / embedding相似度信号
- [ ] **实现 Hindsight Mini 原型** - `lab/hindsight-mini/` Retain-Recall-Reflect 三操作引擎
  - [Hindsight Mini v1 研究](catalyst-research/exploration-notes/2026-05-04-hindsight-mini-reflection-agents.md) ✅ Python原型
  - [Hindsight Mini v2 深度研究](catalyst-research/exploration-notes/2026-05-09-hindsight-mini-agent-reflection.md) ✅ TypeScript完整原型+7篇论文/项目分析+代码已验证
  - **核心洞察**: Retain→Recall→Reflect是最小可行架构(vectorize-io/hindsight); 失败轨迹是最大数据源(AgentHER +7~11pp); Insight提取+经验检索必须协同(ExpeL ablation); 无需参数更新(agent-context-store即experience store)
  - **参考**: AgentHER(2026), ECHO(2025), ExpeL(AAAI 2024), ERL(ICLR 2026), EvolveR(ICLR 2026), Hindsight(vectorize-io), HER(NeurIPS 2017)
  - **Phase 1**: TypeScript HindsightMini类(Retain+Recall+Reflect+augmentPrompt) ✅ 代码验证通过
  - **Phase 2**: 接入agent-context-store(真实embedding+search替换mock) + LLM-based hindsight relabeling
  - **Phase 3**: 与Catalaut实际工作流集成(error-patterns→auto-retain, memory文件→auto-reflect)
  - **实用切入点**: 推理时HER变体(ECHO模式)，零训练成本
- [ ] **OpenClaw MCP Server MVP** - TypeScript SDK v2 + Streamable HTTP,3 tools (exec/memory_search/memory_get)
  - [研究笔记 v3](catalyst-research/exploration-notes/2026-04-29-mcp-server-typescript-streamable-http.md) ✅ 完整代码(3-tool server+client+Inspector调试)
  - [研究笔记 v2](catalyst-research/exploration-notes/2026-04-29-mcp-server-streamable-http.md) ✅ 完整代码+curl测试(2026-04-29)
  - [研究笔记 v1](catalyst-research/exploration-notes/2026-04-28-mcp-server-typescript-v2.md) ✅ 代码已验证(echo+add tools)
  - **关键洞察**: Streamable HTTP 单端点(/mcp) 替代旧 SSE; McpServer.tool() + Zod 自动生成 schema; 会话管理需 Express 层维护 sessionId→transport 映射; MCP Inspector 是调试利器
  - **实施路径**: Phase1 MVP(3 tools) → Phase2 Resources+Prompts → Phase3 Bearer auth+Docker → Phase4 sampling/elicitation
  - [研究笔记 v4](catalyst-research/exploration-notes/2026-04-30-mcp-server-streamable-http.md) ✅ 完整 MVP 代码(3 tools+1 resource+1 prompt, SDK v2 monorepo 包结构)
  - **下一步**: 创建 lab/openclaw-mcp-server/ → 用 McpServer 高层 API 实现 → MCP Inspector 验证
  - **v4 新发现**: SDK v2 拆分为 @mcp/server + @mcp/node + @mcp/express; registerTool() 取代旧 tool() API; 有状态/无状态模式选择影响部署架构; 2026路线图有 Triggers/Tasks/Skills 原语
  - [研究笔记 v5](catalyst-research/exploration-notes/2026-04-30-mcp-server-typescript.md) ✅ **代码已验证通过** (4个API测试全部PASS)
    - Stateful vs Stateless 模式对比; DNS rebinding 防护; Streamable HTTP Accept header 要求
    - **关键修正**: curl 测试必须带 `Accept: application/json, text/event-stream` header
- [ ] **A2A Trust Extension 实现模块** - `lab/a2a-trust-extension/` Python 模块,集成 a2a_minimal + 信任扩展
  - [研究笔记 v1](catalyst-research/exploration-notes/2026-04-25-a2a-agent-trust-integration.md) ✅ EigenTrust+Trust-Extended Card
  - [研究笔记 v2](catalyst-research/exploration-notes/2026-05-02-a2a-v1-signed-cards-trust.md) ✅ **代码已验证通过**(JWS签名/验证+篡改检测+信任路由,6个assertion全PASS)
  - **新发现**: v1.0 JWS签名+JCS规范化=生产级Agent Card防伪造; Extension required字段=信任策略执行点; 双层信任(JWS身份+EigenTrust行为)
  - **下一步**: 创建 lab/a2a-trust-extension/ → 整合 sign_agent_card+TrustEngine+verify → pip installable
- [ ] **桥接 TypeScript TrustNetwork → Python TrustEngine** - 跨语言信任数据一致
- [ ] 初始化 openclaw-mcp-server 项目 - 合并到上方 MCP Server MVP 任务
- [x] **LangGraph Supervisor 研究** - [研究笔记](catalyst-research/exploration-notes/2026-04-27-langgraph-supervisor-openclaw.md) ✅ 代码已验证通过(Supervisor pattern + conditional routing)
- [ ] 实现 `openclaw-langgraph-bridge` 模块 - **已转向 LangGraph.js (TypeScript)** 避免引入 Python 依赖
  - **关键发现**: LangGraph.js v1.2.9 in-process > Python out-of-process,零额外运行时
  - **05-01 重大更新**: 新 API `StateSchema` + `ReducedValue` 替代旧 `Annotation.Root()`，Zod v4 原生集成
  - [研究笔记 createOpenClawNode](catalyst-research/exploration-notes/2026-05-01-langgraphjs-create-openclaw-node.md) ✅ 3测试全通过（invoke+stream+动态复用）
  - [研究笔记 Gateway Client + task()](catalyst-research/exploration-notes/2026-05-08-langgraphjs-gateway-http-client.md) ✅ 设计完成(GatewayClient + createTask + ReducedValue taskResults)
  - **05-08 新发现**: task() 幂等性 = 确定性任务ID + 检查点恢复; Node-level Caching 与 Gateway 调用互补; Subgraph 模式适合多 Agent 编排
  - **下一步**: 创建 lab/openclaw-langgraph-bridge/ → 实现 GatewayClient → createTask → executor 双模式
  - **核心设计**: executor 参数抽象 sessions_spawn，工厂函数零修改切换 mock→real
  - Step 1: `createOpenClawNode()` 工厂函数,包装 sessions_spawn 为 LangGraph.js async node
  - Step 2: Supervisor router(纯函数优先,需要时升级 LLM 路由)
  - Step 3: 核心难题 = 子代理结果解析(推荐 JSON mode 输出)
  - [JS 研究笔记](catalyst-research/exploration-notes/2026-04-28-langgraphjs-supervisor-openclaw-bridge.md) ✅ 代码已验证
  - [Python 研究笔记](catalyst-research/exploration-notes/2026-04-27-langgraph-supervisor-openclaw.md) (参考)
- [x] ~~AMS: searchByTimeRange(opts), contentRollback(id, versionIndex)~~ ✅ 完成 (04-27)
- [ ] AMS 生产化:EmbeddingProvider真实接入(ONNX/远程API), Docker化
- [ ] **Edge Agent WASM Runtime** — lab/edge-agent-wasm/ Rust+WasmEdge+WASI-NN
  - [研究笔记](catalyst-research/exploration-notes/2026-05-11-edge-agent-runtime.md) ✅ TypeScript原型(已运行验证)+5核心概念+5关键洞察
  - **核心发现**: WASM是Agent最佳沙箱(3.4MB+10ms冷启动); MoE模型让边缘推理可行(35B只激活3B); Agent=Tool-Use Loop非LLM包装; Google AI Edge FC SDK已支持on-device function calling; 现有框架全为云端设计
  - **下一步**: Rust EdgeAgent trait → WASM编译 → WasmEdge WASI-NN推理 → tool-use循环
- [ ] **SLM Tool-Use Benchmark** — lab/slm-tool-use-benchmark/
  - [研究笔记](catalyst-research/exploration-notes/2026-05-11-slm-agent-tool-use.md) ✅ 5核心概念+可运行TypeScript代码(SLMAgent+ToolRegistry+Ollama API)+5关键洞察
  - **核心发现**: NVIDIA "SLM是Agent的未来"; Code Agency模式(代码编排>LLM编排); SLM失败模式与LLM完全不同(格式vs事实); Qwen3-30B-A3B MoE是边缘最优解(30B质量+3B成本); 强调词(CRITICAL/NEVER)对SLM有可衡量影响
  - **项目关联**: Edge Agent(Code Agency架构), Structured Output(SLM prompt templates), Agent Observability(SLM专用PolicyEngine规则)
  - **下一步**: lab/slm-tool-use-benchmark/ → 5个标准task + 自动评分 → 确定默认模型推荐

### Core Projects
1. **Agent Task CLI** - 多 Agent 任务编排 (109 tests, 80%+ coverage, ✅ 已完成)
2. **Local Embedding Memory** - MEMORY.md 语义搜索 (✅ 插件v1.1.0, 7/7 tests pass, 561 chunks indexed)
3. **Prompt Weaver** - 零依赖 Prompt 编排引擎 (✅ v0.3.0, 60 tests pass + CLI增强 51 tests)
4. **Agent Trust Network** - 多 Agent 信任网络模拟 (🔄 Web UI 设计阶段)
5. **Edge Agent Runtime** - 轻量级边缘AI Agent运行时 (✅ 核心完成, 31/31 tests)
6. **Edge Agent Mesh** - 边缘设备自组织AI网络 (🔄 已建仓库,核心模块已实现: core/protocol/memory/model)
7. **agent-log** - OpenClaw 日志搜索/汇总 CLI (✅ 单文件 Bash,零依赖)
8. **ctxgen** - AI 上下文文件生成器 (✅ v1.0, 纯Node.js零依赖, 支持4种目标格式)
9. **tiny-agent-workshop** - 单文件 Agent 模式教学集 (✅ 7个模式: ReAct/ToolCall/Memory/Router/Guardrail/Chain/EdgeAgent)
10. **Agent Memory Service** - Mem0风格Agent记忆管理 (✅ v1.0-dev, 594/594 tests, 三层存储+LLM提取+语义检索+Consolidation+变更追踪+自监控+搜索三阶段(BM25+Embedding+Unified RRF)+suggestTags()+healthScore()+autoMaintain()+searchSimilar()+findDuplicatePairs()+exportJSON/importJSON()+pruneLowWeight()+inspect()+clusterByTopic()+summarizeCluster()+compareMemories()+tagHierarchy()+rebalance()+autoTag()+mergeClusters()+clusterHealth()+searchByEntity()+topEntities()+tagSearch()+memoryDiff()+clusterAutoMerge()+contentHistory()+contentVersionDiff()+searchByTimeRange()+contentRollback()+classifyFact()+searchByFactType()+statsByFactType()+reclassifyFact()+bulkReclassify()+searchByContent()+contentBranch()+searchGraph()+searchTemporal()+memoryMerge()+searchByBranch()+bulkMerge()+addOpinion()+searchOpinions()+evolveConfidence()+opinionConsensus()+opinionDrift()+opinionEvolveFromEvidence()+contentVersions持久化+mergeSuggestions())
11. **A2A Protocol Lab** - Agent-to-Agent通信协议实验 (✅ 零依赖Python实现, Server+Client+Federation Demo)
12. **agent-memory-graph** - SQLite知识图谱Agent记忆 (✅ 30/30 tests, unlink+merge_nodes+shortest_path+tag_nodes)

---

## Next Actions (Updated 2026-04-20)

### High Priority (本周完成)
- [ ] **Context Engineering 应用到 agent-context-store** — 增加 `fold(key, summary)` context folding 原语 + `ToolClearingMiddleware`
  - [研究笔记](catalyst-research/exploration-notes/2026-05-20-context-engineering-agents.md) ✅ 5核心概念+可运行ContextEngine(8/8 tests)+5关键洞察+项目关联
  - **核心发现**: Context Drift 是生产 Agent 头号杀手(65%失败率); Context Folding(ICLR 2026)可10×压缩; Write/Select/Compress/Isolate 四策略框架
  - **下一步**: agent-context-store 增加 `fold()` + ToolClearingMiddleware, 目标 8+ tests
- [ ] **Agent Memory Service v1.0** - ✅ 334/334 tests。搜索三阶段+healthScore()+autoMaintain()+searchSimilar()完成。下一步: EmbeddingProvider真实接入(ONNX/远程API), 生产化
- [ ] **实现 OpenClaw MCP Server** - ✅ 研究完成(2026-04-19 + 2026-04-20 深度研究)。完整实现模式已就绪:
  - 研究笔记: [技术选型](catalyst-research/exploration-notes/2026-04-18-mcp-server-typescript-streamable-http.md) + [实现模式](catalyst-research/exploration-notes/2026-04-19-mcp-server-implementation-patterns.md) + [深度研究(含可运行代码)](catalyst-research/exploration-notes/2026-04-20-mcp-server-streamable-http.md)
  - SDK v2: registerTool API、多会话工厂模式、createMcpExpressApp、Zod v4
  - **Step 1 MVP**: 3 tools (status, search_memory, run_command) + Streamable HTTP 无状态模式 + curl 测试脚本 ✅ 代码已写
  - **Step 2**: 接入 Agent Memory Service query() + OpenClaw Gateway 状态
  - **Step 3**: Bearer auth + rate limit + Docker 部署
  - **关键洞察**: Streamable HTTP 已取代 SSE;SDK v2 模块化拆分(Express/Hono中间件);无状态模式适合MVP;OpenClaw差异化定位是"AI agent的操作系统接口"
  - **2026-04-22 更新**: v1.x 是生产推荐(v2 仍 pre-alpha);Streamable HTTP 响应可以是 JSON 或 SSE 流;Session 管理(Map→Redis)是生产级关键差异;Taskade 的 OpenAPI codegen 方法值得借鉴(自动生成 tool 定义避免手工维护);middleware 包是最简集成路径
- [ ] **A2A Agent Trust 集成原型** - Agent Card嵌入信任元数据,与Agent Trust Network对接
- [ ] **集成多Agent框架** - LangGraph Supervisor桥接OpenClaw原型
  - [研究笔记 04-26](catalyst-research/exploration-notes/2026-04-26-langgraph-supervisor-bridge-openclaw.md) ✅
  - [研究笔记 04-27](catalyst-research/exploration-notes/2026-04-27-langgraph-supervisor-openclaw.md) ✅ 代码已验证通过
  - **核心洞察**: LangGraph=编排层(状态图+路由), OpenClaw=执行层(sessions_spawn+channel集成)
  - **新发现**: Deep Agents (deepagents) - 开箱即用 Agent Harness, MCP 集成, trust-the-LLM
  - 下一步: 实现 `lab/openclaw-langgraph-bridge/` 模块

### Medium Priority (本月完成)
- [ ] **实现 A2A Agent Trust 集成** - 在 Agent Card 中嵌入信任元数据,为 A2A 联邦添加信任层
- [ ] **Hindsight 多策略检索研究** - 实现一个小型原型,体验 91.4% 的准确率
- [ ] **Agent Trust Network Web UI 原型** - 可视化组件、信任算法优化、网络模拟器
- [ ] **Edge Agent Runtime Dashboard** - WebSocket接入、pip包化、"5分钟快速原型"教程
- [ ] **Agent Memory Service v0.2.0** - Memory Consolidation (✅ 54/54 tests), 接入 LLM 提取, embedding 支持
- [ ] **技术债务处理** - 测试覆盖率提升、文档更新、性能优化、安全检查

### Exploratory (下季度)
- [ ] **Agent Observability & Evaluation 框架** — `lab/agent-observability/` Tracer + PolicyEngine + TraceEvaluator
  - [研究笔记](catalyst-research/exploration-notes/2026-05-10-agent-observability-evaluation.md) ✅ 5核心概念+可运行TypeScript代码(Tracer/PolicyEngine/Evaluator/traceToEvalCase)+5关键洞察
  - **核心发现**: Agent trace捕获决策过程(非仅函数调用); 3.4GB小模型tool calling 95%(训练>参数量); Policy-as-Code是最被低估的guardrail; trace→eval→CI闭环是2026标准
  - **项目关联**: agent-context-store(trace持久化), prompt-router(eval循环), better-ralph(experiments.tsv升级), Edge Agent(模型选择)
  - **下一步**: lab/agent-observability/ → tracer.ts + policy.ts + evaluator.ts + reporter.ts, 目标10+ tests
- [ ] **Edge Agent Runtime 增强** - MLReasoner(ONNX)、真实硬件驱动、Async支持、MicroPython适配
- [ ] **Agent Mesh Network 原型** - 去中心化协作、P2P通信协议、共识算法
- [ ] **A2A Trust Prototype** — `lab/a2a-trust-prototype/` ES256签名中间件 + TrustEngine动态信任评分
  - [研究笔记](catalyst-research/exploration-notes/2026-05-18-a2a-trust-prototype.md) ✅ 5核心概念+可运行JS代码(TrustEngine/签名验证中间件)+5关键洞察
  - **核心发现**: A2A复用OpenAPI security schemes不做新认证; Trust Score应用滑动窗口非全量; 与agent-context-store middleware pipeline/agent-observability Tracer天然对齐
  - **下一步**: 创建lab/a2a-trust-prototype/ TypeScript项目, TrustEngine改滑动窗口+指数衰减, Fastify plugin格式, 目标20+ tests
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
- **开发风格:** 零依赖优先,文档 > 功能
- **沟通风格:** 直接、有观点、写给人看

---

## Design Principles (Condensed)

### Agent 开发哲学
- **Simple > Complex** - 从简单开始,需要时才加复杂度
- **Trust > Capability** - 诚实承认不确定比装作全知更可信
- **Integration > Isolation** - 工具协同 > 孤立功能
- **Context is King** - 上下文质量决定输出质量

### Agent 编排要点
- PTY 模式用于终端 UI,Print 模式用于程序化执行
- 实际并发上限约 8 个 agent,超了协调开销 > 收益
- 文件锁(Claim)防重复、分支隔离防冲突、Cursor 文件追踪进度

### 工具设计原则
- 零依赖优先(纯 Python 3)
- 开箱即用,高级可自定义
- 同时输出 Markdown + JSON
- AI 友好的结构化上下文

### 重要框架发现
- **12-Factor Agents** - 可靠 LLM 应用的设计原则
- **Agno** (19.4k⭐) - 生产级 Agent 运行时
- **Memori** (12.4k⭐) - SQL Native Memory Layer
- **A2A协议** - Agent间的"HTTP",Agent Card发现+Task生命周期+Transport-agnostic,50+企业支持,Linux Foundation AAIF 管理([深度研究](catalyst-research/exploration-notes/2026-04-14-a2a-protocol.md))
  - 与 MCP 互补: MCP纵向(Agent→工具), A2A横向(Agent→Agent)
  - 三层架构: MCP(工具) + A2A(Agent) + WebMCP(Web)
  - 关键缺口: 信任层 - Agent Trust Network 可填补
- **MCP协议** - Agent的"USB接口",97M+下载量,成为工具访问标准([研究](catalyst-research/exploration-notes/2026-04-04-mcp-protocol-deep-dive.md))
- **多Agent编排模式** - Pipeline, Supervisor, Council, Router, Hierarchical等11种模式
- **Agent Memory 框架**:
  - **Mem0** (48K+⭐) - Vector + Graph,最大生态,LongMemEval 49.0%,0.71s 延迟
  - **Hindsight** (4K+⭐) - 多策略混合检索,LongMemEval 91.4% (最高)
  - **Letta** (21K+⭐) - OS 启发分层记忆,Agent 自主管理
  - **Zep** (24K+⭐) - 时间知识图谱,时间推理领先
- **Agent Memory 架构**:
  - 从 RAG 到 Agent Memory 的范式转变
  - 三层存储模型:短期(会话)、中期(事件)、长期(持久)
  - 混合存储架构:Vector DB(语义)+ Graph DB(关系)+ Structured DB(事实)
  - 记忆生命周期:Generation → Evolution → Archival
- **六大核心设计模式**:
  - Reflection(反思), Tool Use(工具使用), Planning(规划)
  - Multi-Agent(多Agent), Orchestrator-Worker(编排-工作), Evaluator-Optimizer(评估-优化)
- Edge AI 趋势:SLM + 量化 + 本地部署

---

## Workflows & Conventions

### GitHub Sync Rule (2026-04-16)
**重要工作流程:所有修改必须及时同步到 GitHub**

- 任何有意义的代码/文档/配置修改,完成后立即提交并推送
- 不要等待"批量提交",单个有意义改动就 push
- 新项目初始化后立即创建 GitHub 仓库并推送
- 本地测试和远程仓库同步保持一致
- 工作流:`git add` → `git commit` → `git push`(三步不脱节)

**原因:** 避免本地堆积大量未提交改动,减少冲突风险,确保远程仓库是真实备份

---

## Recent Achievements

### 2026-04-30
- ✅ **Agent Memory Service v1.0-dev 续升** — 583→612 tests (+29)
  - **autoMerge(opts)**: 端到端自动去重(mergeSuggestions→ID dedup→bulkMerge), minScore/maxMerges/dryRun/layer, 6 tests
  - **contentVersionCompact(opts)**: 压缩旧内容版本(maxVersions+olderThan+dryRun), 5 tests
  - **mergePreview+safeMerge+mergeConflictSummary**: 风险感知合并工作流(18 tests, 594→612)
  - 去重管道完整: mergeSuggestions(发现) → autoMerge(执行) → contentVersionCompact(清理)
  - 零回滚率持续保持(连续26天)

### 2026-05-13
- ✅ **agent-memory-graph** — 0→30 tests (3 cycles, 3 keep). unlink+merge_nodes+shortest_path+tag_nodes。SQLite知识图谱Agent记忆 (commits be74e8a/708a4de/3c78134)
- ✅ **agent-context-store sample/count_by_tag/diff/histogram/dedup** — 76→93 tests (+17)。5新API: sample()+count_by_tag()+diff()+histogram()+dedup_content() (commits 2d151b1/a9fc58f)
- ✅ **agent-context-store search_combined** — 69→76 tests (+7)。复合过滤(tags+prefix+age+length) (commit b916bd0)
- ✅ **better-ralph-core plan_batch** — 278→285 tests (+7)。dry-run批量规划预览 (commit 214e16b)
- ✅ **agent-context-store 4-cycle evening** — 93→132 tests (+39, 4 cycles, 4 keep, 零回滚)
  - touch()+content_hash()+top_tags()+batch_put()+search_similar_to_key() (+13)
  - update_content()+clear()+size()+has_key() (+10)
  - export_json()+import_json()+merge_store()+keys()+values() (+8)
  - group_by_prefix()+content_summary()+tag_cloud() (+8)
  - 487→636 lines (commits ba0d514/cf6140a/6038d46/6963eea)
- ✅ **better-ralph-core plan_batch** — 278→285 tests (+7)。dry-run批量规划预览 (commit 214e16b)
- 连续51天零回滚率

### 2026-05-15
- ✅ **agent-context-store entry version history** — 139→153 tests (+8)。per-entry undo/rollback+version diffing (commit 6202e94)
- ✅ **agent-context-store namespaces** — 153→159 tests (+6)。多Agent隔离child stores (commit 09b7469)
- ✅ **agent-context-store weighted_sample+compact+validate** — 159→170 tests (+11)。weighted random sampling+expired cleanup+integrity check (commit 77b1fea)
- ✅ **prompt-router freeze/unfreeze+snapshot/restore** — 234→244 tests (+10)。locked routing+point-in-time state capture (commit fbef775)
- 连续54天零回滚率

### 2026-05-17
- ✅ **agent-context-store event hooks** — 178→186 tests (+8)。on/off/_emit pub/sub for put/delete/expire (commit 52e66b8)
- ✅ **better-ralph-core story_digest** — 299→307 tests (+8)。单调用PRD状态快照 (commit fdb9e3a)
- 连续59天零回滚率

### 2026-05-20
- ✅ **Context Engineering 深度研究** — Write/Select/Compress/Isolate 四策略 + Context Folding(ICLR 2026) + Context Drift 分析 + 可运行 ContextEngine (8/8 tests)
  - [研究笔记](catalyst-research/exploration-notes/2026-05-20-context-engineering-agents.md) ✅
  - 核心发现: Context Drift 65% 失败率(Forrester); Context Folding 10× 压缩(ICLR 2026); Memory Blocks(Letta)是最佳抽象
- ✅ **工具链升级** — codegraph v0.7.11 MCP 集成(省36.5% tokens) + Rust 1.95.0 + coding-agent-launcher skill
- ✅ **Rust mini-wget 原型** — Codex (gpt-5.5) 80K tokens 从零实现, 4/4 tests, cargo 全通过
- ✅ **wget2 源码架构分析** — Codex + codegraph, 飞书文档发布
- ✅ **多Agent编排路线图** — Phase1(LangGraph Bridge) → Phase2(A2A Trust) → Phase3(端到端流水线)
- ✅ **agent-context-store 246→278** — snapshot/restore + version-CAS + incr/decr + expire_at + copy/swap (+32, 4 cycles)
- 连续66天零回滚率

### 2026-05-21
- ✅ **agent-context-store 246→278** (+32, 4 cycles, 4 keep, 零回滚)
  - snapshot/restore/from_snapshot 全状态序列化 +12
  - version-based CAS + touch with changelog +11
  - incr/decr (counter pair) + expire_at (absolute TTL) +10
  - copy/swap (atomic clone + exchange) +12
- ✅ **agent-context-store 278→309** (+31, 3 cycles, 3 keep, 零回滚)
  - keys_matching + get_set + union/difference +10
  - put_unique + rename_key + clear +11
  - put_all + entries_by_tag + rekey +10
- 连续68天零回滚率

### 2026-05-19
- ✅ **agent-context-store 6-cycle 深夜马拉松** — 202→246 tests (+44, 6 cycles, 6 keep, 零回滚)
  - batch ops + CAS + TTL + 三层响应性(middleware→storage→hooks→watchers)
- ✅ **A2A Trust ES256 补充研究** — jose ES256 + TrustEngine衰减 + Express中间件
- 连续65天零回滚率

### 2026-05-18
- ✅ **agent-context-store middleware pipeline** — 186→194 tests (+8) (commit df236dd)
- ✅ **agent-context-store key watchers** — 194→202 tests (+8) (commit 334f9ae)
- ✅ **agent-observability 3-cycle evening** — 81→91 tests (+10, 3 cycles, 3 keep)
- 连续61天零回滚率

### 2026-05-16 (凌晨)
- ✅ **agent-context-store xrefs** — 170→178 tests (+8)。类型化交叉引用+双向追踪+BFS图遍历 (commit 4c960d5)
- ✅ **better-ralph-core checkpoint_diff** — 292→299 tests (+7)。检查点差异对比 (commit 05c563b)
- 连续56天零回滚率

### 2026-05-16 (晚间)
- ✅ **agent-observability 3-cycle** — 37→48 tests (+11)。Tracer:getChildren+getSpanTree | PolicyEngine:disableRule/enableRule/evaluateAll | AgentObserver:reportMarkdown+spanStats (commit 6f402bb)
- ✅ **Structured Output XGrammar-2 深度研究** — TagDispatch(动态结构切换) + Cross-Grammar Cache(跨请求子结构复用) + Format Tax(两层质量损害) + 可运行 StructuredOutputClient (6/6 tests passed)
- 连续57天零回滚率

### 2026-05-14
- ✅ **agent-context-store changelog audit trail** — 132→139 tests (+7)。append-only changelog (commit 7549f8f)
- ✅ **better-ralph-core validate_dependencies** — 285→292 tests (+7)。DFS循环检测 (commit cbd7772)
- 连续52天零回滚率

### 2026-05-12
- ✅ **agent-context-store 持久化重建+time_range+batch_delete** — 重建基线69 tests, +search_by_time_range+batch_delete。代码已持久化到 lab/agent-context-store/ (commit 269dafe)
- ✅ **better-ralph-core checkpoint/resume** — 271→278 tests (+7)。save_checkpoint+load_checkpoint+resume_batch JSON可序列化断点续传 (commit 214cf5d)
- 连续48天零回滚率

### 2026-05-11
- ✅ **agent-context-store search_dups+move** — 92→97 tests (+5)
- ✅ **better-ralph-core run_batch+timeline** — 257→264 tests (+7)
- ✅ **Edge Agent WASM Runtime 研究** — TypeScript原型+5核心概念+5关键洞察
- ✅ **SLM Agent Tool-Use 深度研究** — NVIDIA论文+arXiv工程挑战+Ollama tool calling+可运行SLMAgent代码
- 连续47天零回滚率

### 2026-05-10
- ✅ **Agent Observability 深度研究** — Tracer/PolicyEngine/Evaluator 可运行 TypeScript 代码
- ✅ **Constrained Decoding 结构化输出研究** — 5/5 tests, FSM constrained decoding + Zod schema cache
- ✅ **prompt-router 晚间循环** — 216→230 tests (+14): route_by_length+prune_agents+optimize_weights

### 2026-05-09
- ✅ **agent-context-store search_regex** — 34→39 tests (+5)
  - search_regex(pattern, search_fields): 正则搜索+字段定位(content/key/tags), 无效模式返回空
- ✅ **agent-context-store append+expire_in+age** — 39→48 tests (+9)
  - append(key, text, separator): 追加内容保留created_at
  - expire_in(key, ttl_hours): 独立TTL管理, 可复活过期条目
  - age(key): 条目年龄查询(秒)
- ✅ **agent-context-store evening session** — 48→58 tests (+10)
- ✅ **prompt-router 实验循环** — 194→216 tests (+22, 6 new APIs, 零回滚, 连续44天)
  - search_by_prefix(prefix): 命名空间key前缀过滤
  - snapshot()/restore(): 时间点快照+恢复(merge模式)
  - multi_search(queries): 批量多查询单次遍历
  - 零回滚率: 连续43天

### 2026-05-10
- ✅ **agent-context-store search_by_age** — 58→61 tests (+3)
  - search_by_age(max_age_seconds, field): 时间查询——找N秒内的条目
  - field参数区分created_at/updated_at
- ✅ **better-ralph-core retry+stats** — 249→257 tests (+8)
  - retry_last_failed(): 重试最近失败故事+自动execute_iteration
  - get_retry_stats(): 失败率/可重试数/迭代明细
- ✅ **prompt-router 6新API** — 194→216 (+22)
  - detect_language()+route_by_language()+route_by_complexity()+agent_graph()+export_state()/import_state()
  - 连续45天零回滚率
- ✅ **Autoresearch 晚间实验循环** — 3 cycles, 3 keep
  - **prompt-router** 216→230 tests (+14): route_by_length()+prune_agents()+optimize_weights()
  - **agent-context-store** 31→37 tests (+6): keys_by_tag()+search_fuzzy(trigram overlap)
  - GitHub仓库创建: agent-context-store
  - 连续45天零回滚率持续保持

### 2026-05-08
- ✅ **agent-context-store exists+search_by_tags+mget_entry+retag** — 25→34 tests (+9)
  - exists(): 纯检查无副作用; search_by_tags(tags, match_all): 多标签AND/OR; mget_entry(keys): 批量Entry
  - retag(key, add_tags, remove_tags): 原地标签编辑保留created_at
  - 零回滚率: 连续41天
- ✅ **prompt-router 评估工具** — 160→174 tests (+14)
  - cross_validate(test_cases): 标注数据评估路由准确率, per-agent precision/recall/f1, confusion matrix
  - suggest_improvements(test_cases): 分析误分类并建议缺失关键词
  - 零回滚率: 连续41天
- ✅ **agent-context-store diff+compact+validate** — 34→37 tests (+3)
  - diff(key1, key2): entry对比(内容/tags/age差异)
  - compact(): 清理过期条目
  - validate(): 存储完整性检查
- ✅ **LangGraph Bridge 实战研究** — Executor双模式 + createTask幂等 + BridgeState ReducedValue
  - [研究笔记](catalyst-research/exploration-notes/2026-05-08-langgraph-bridge-executor-task.md) ✅ 18/18 tests
  - 核心发现: Executor接口 > GatewayClient类; 确定性TaskID; OpenClaw API端点 /v1/agent/run; StateSchema替代Annotation

### 2026-05-07
- ✅ **AMS embedBatch() 批量嵌入** — 96→97 test suites (+9). 去重+缓存感知+TTL安全, N texts→K unique embeds, 失败隔离
- ✅ **MemoryManager _detect_project_name 修复 + get_memory_summary** — 192→200 tests (+8). 解析package.json/pyproject.toml的name字段(之前只是截文件名), +4 get_memory_summary tests
- ✅ **better-ralph-core merge_prd/export_markdown/find_critical_path** — 192→200 tests (+8)
- 零回滚率: 连续40天

### 2026-05-06
- ✅ **AMS Embedding Cache TTL Eviction** — 41→48 embed tests (+7). cacheTTL(ms), 自动过期重嵌, evictExpired()批量清理, 向后兼容持久化
- ✅ **MemoryManager Session Lifecycle Integration** — 150→156 tests (+6). 完整生命周期: initialize→context→iteration→persistence. **修复PosixPath JSON序列化bug**(_save_project_context崩溃导致级联失败)
- 零回滚率: 连续39天

### 2026-05-05
- ✅ **AMS Embedding Cache LRU Eviction** — 36→41 embed tests (+5). maxCacheSize opts, Map insertion-order eviction, setMaxCacheSize(n) runtime
- ✅ **MemoryManager Project Scanning Tests** — 136→150 tests (+14)
- ✅ **prompt-weaver 4 cycles** — 128→148 tests (+20). weave_filter, pipeline_diff, Context.undo, weave_reduce
- ✅ **prompt-router diversity+regex routing** — 94→111 tests (+17)
- ✅ **better-ralph-core session lifecycle** — 125→136 tests (+11)
- ✅ **Hindsight Mini 反思Agent研究** — HER+Reflexion融合, 多法官验证97.7%精度
- ✅ **A2A Trust Layer 深度研究** — ES256+JWS签名验证, 三层身份架构, @a2a-js/sdk v0.2.4, 150+组织生产部署
- ✅ **Agent Federation & Discovery 研究** — DUADP+GEACL+双层Churn模型+可运行Gossip代码
- 零回滚率: 连续38天

### 2026-05-04
- ✅ **AMS autoMaintain 统一 BM25+Embed Cache 诊断** — 312 tests (+4). healthScore 6 维度, autoMaintain 默认任务含 compactBM25/compactEmbedCache
- ✅ **Better Ralph PRD 集成测试** — 117→121 tests (+4). 完整生命周期: split→adjust_priorities→progress→deps

### 2026-05-03
- ✅ **AMS Embed Cache Sync + compactEmbedCache()** — 640→645 tests (+5)
  - EmbeddingProvider: removeByContent/removeByKey/cacheKeys
  - delete/batchDelete 现在同步清理 embedding cache
  - compactEmbedCache(opts) 孤立条目清理+dryRun
  - 与 BM25 compactBM25Index() 形成对称模式
- ✅ **Better Ralph PRD 测试覆盖** — 103→117 tests (+14)
  - auto_adjust_priorities: 依赖深度优先级排序(5 tests)
  - split_large_story: 大故事拆分(5 tests)
  - _calculate_dependency_depth: 循环依赖保护(4 tests)
  - 修复: agent_registry + version_control 缺失 stubs
  - 零回滚率持续保持(连续34天)
- ✅ **prompt-router 实验循环 x2** — 72→94 tests (+22)
  - route_round_robin(): 加权轮询负载均衡+共享状态, 6 tests
  - route_least_loaded(): 最少加载路由+阈值过滤, 6 tests
  - route_by_capability(any/all/best): 能力匹配路由, 6 tests
  - agent_stats(): Agent 统计摘要, 4 tests
  - 零回滚率持续保持(连续34天)

### 2026-05-02
- ✅ **prompt-router 三轮实验循环** — 34→48 tests (+14)
  - **route_ensemble(k, weights)**: 多Agent权重分配委托, 5 tests
  - **merge_routers(*routers)**: 路由器合并+名字去重, 4 tests
  - **route_adaptive(correct_agent)**: 反馈驱动优先级调整+准确率追踪, 5 tests
  - 修复: PromptRouter([]) 现在正确创建空路由器
  - 零回滚率持续保持(连续31天)
  - GitHub仓库创建并推送: https://github.com/robertsong2019/prompt-router
- ✅ **agent-task-cli 续升** — TaskChain.step_count + insert_step/remove_step, chain tests 15→26
  - step_count: getter返回步骤数
  - insert_step(index, name, config): 位置插入
  - remove_step(name): 删除+依赖引用清理
  - 总测试: 416/416 (100%)
- ✅ **AMS BM25 Sync + compactBM25Index()** — 635→640 tests (+5)
  - delete/batchDelete BM25 sidecar 同步修复
  - compactBM25Index() 孤立条目清理
  - 修复 expire.test.js dbPath bug

### 2026-05-01
- ✅ **Agent Memory Service v1.0-dev 续升** — 612→640 tests (+28)
  - **branchDiff(id)**: 分支与源记忆对比(content similarity + tag/entity deltas + chained branches), 8 tests
  - **branchMerge(branchId, opts)**: 分支合并回源记忆(基于memoryMerge), contentStrategy/tagStrategy/linkStrategy, 10 tests
  - **BM25 index persistence**: JSON sidecar持久化(toJSON/fromJSON + dirty flag), 5 tests (630→635)
  - **BM25 sync fixes + compactBM25Index()**: delete/batchDelete同步修复 + 孤立条目清理, 5 tests (635→640)
  - 分支管道完整: contentBranch(创建) → branchDiff(检查) → branchMerge(合并)
  - BM25持久化管道完整: sidecar持久化 → 同步修复 → 孤立清理
  - 零回滚率持续保持(连续30天)
- ✅ **agent-task-cli 续升** — 375→380 tests (+5)
  - **TaskChain.progress**: getter返回{total,completed,failed,pending,skipped,percent}
  - **TaskChain.retryAll(opts)**: 批量重试失败步骤, 可选resetPending
  - 5 new tests, 零回滚
- ✅ **prompt-router 续升** — 22→34 tests (+12)
  - add_agent/remove_agent/list_agents, save_config/load_config, route_top_k
  - 连续30天零回滚率

### 2026-04-29
- ✅ **Agent Memory Service v1.0-dev 续升** - 499→569 tests (+70)
  - **memoryMerge(id1, id2, opts)**: 冲突合并,4种content策略+tag策略+entity union+link rewiring,10 tests
  - **searchByBranch(id, opts)**: BFS分支遍历,支持depth限制+includeSelf,6 tests
  - **bulkMerge(pairs, opts)**: 批量合并,顺序执行+错误处理,5 tests
  - **Hindsight Phase 4 - Opinion Network** (04-29晚, 29 new tests):
    - **addOpinion(topic, content, opts)**: 带confidence和topic的opinion记忆, 4 tests
    - **searchOpinions(topic, opts)**: topic过滤+confidence排序+minConfidence/limit, 5 tests
    - **evolveConfidence(id, delta, opts)**: 证据驱动的confidence演化+历史追踪, 7 tests
    - **opinionConsensus(topic)**: 加权平均+分歧度(标准差)+多数方向检测, 5 tests
    - **opinionDrift(id)**: confidence变更历史+证据轨迹, 3 tests
    - **opinionEvolveFromEvidence(topic, evidence, delta)**: 批量证据驱动演化, 5 tests
  - API全景: 10路检索+内容版本化+冲突合并+批量操作+6个opinion APIs
  - 零回滚率持续保持(连续23天)
- ✅ **agent-task-cli StreamManager tests** - 344→359 tests (+15)

### 2026-04-28
- ✅ **Agent Memory Service v1.0-dev 续升** - 481→519 tests (+38)
  - **searchGraph(startEntity, opts)**: entity_index多跳BFS图遍历,10 tests
  - **searchTemporal(opts)**: 时间衰减搜索,7 tests
  - 搜索API全景: 9路检索
  - **agent-task-cli StreamManager**: 15 tests (344→359)
  - 零回滚率持续保持(连续22天)
- ✅ **Agent Pipeline 代码实验室 x4 cycles** - 7→67 tests (+60)
  - **cycle1**: retry + continue_on_error + validate() + to_dict/from_dict 序列化 (+49)
  - **cycle2**: run_batch 批量执行 + insert_step/remove_step 步骤管理 (+5)
  - **cycle3**: conditional step execution - lambda条件跳过步骤 (+3)
  - **cycle4**: pipeline merge 组合 + step_count 属性 (+3)
  - 1286→1394 lines, 零回滚, 4/4 cycles keep

### 2026-04-27
- ✅ **Agent Memory Service v1.0-dev 续升** - 445→481 tests (+36)
  - **searchByTimeRange(opts)**: 时间范围查询,支持任意数值字段、layer/tag过滤、排序、分页,11 tests
  - **contentRollback(id, versionIndex)**: 内容版本回滚,复用 update() 的自动快照机制,7 tests
  - 内容版本化三部曲完成: view(contentHistory) → compare(contentVersionDiff) → restore(contentRollback)
  - **Hindsight Phase 1**: classifyFact + searchByFactType + statsByFactType + reclassifyFact + bulkReclassify → +18 tests
  - **agent-task-cli**: Cache resetStats + entries → 331→335 tests (+4)
  - 修复 ChangelogStore.since() 竞态条件(changes test flaky)

### 2026-04-26
- ✅ **Hindsight 多策略记忆架构深度研究** - SOTA Agent Memory (LongMemEval 91.4%)([笔记](catalyst-research/exploration-notes/2026-04-26-hindsight-multi-strategy-memory.md))
  - **核心发现**: 四网络(world/experience/opinion/observation)事实观点分离 + 四路检索(semantic/BM25/graph/temporal) + RRF融合 + 行为配置(skepticism/empathy)
  - **可运行代码**: HindsightMini 零依赖原型,四网络 + 四路并行检索 + 观点演化,`/tmp` 验证通过
  - **关键洞察**: 事实/观点分离是 Agent 记忆缺失拼图;四路检索比三路强;行为参数让 Agent 有性格
  - **项目关联**: AMS 可直接升级四网络分类 + searchGraph() + searchTemporal()
- ✅ **Autoresearch 实验循环 x4** - 连续19天零回滚率
  - **prompt-weaver**: validate() + dry_run() + merge() + weave_chain() → 118 tests (+18)
    - validate(): 管道完整性检查(errors/warnings/unreachable)
    - dry_run(): 无副作用的执行路径追踪
    - merge(other, prefix): 管道组合
    - weave_chain(): 快速多模板管道
  - **agent-role-orchestrator**: MemorySystem.consolidate({minImportance}) + ShortTermMemory.remove(id) → 154 tests (+3)
    - 自动提升高importance的short-term记忆到long-term,默认阈值0.7
  - **prompt-router**: route_with_fallback() → 22 tests (+3)
    - Fallback chain: 按分数顺序尝试agents直到超过阈值,返回完整chain
  - **agent-context-store**: rename()+copy() → 17 tests (+2)
    - Key管理:重命名(保留tags)、深拷贝(独立副本)

### 2026-04-25
- ✅ **A2A Agent Trust 集成深度研究** - A2A Extension 机制 + EigenTrust 信任嵌入 Agent Card([笔记](catalyst-research/exploration-notes/2026-04-25-a2a-agent-trust-integration.md))
  - **核心发现**: A2A v1.0 Extension 机制是嵌入信任的标准路径;Agent Card 充当信任传播载体
  - **可运行代码**: TrustEngine (EigenTrust) + 信任扩展 Agent Card + 信任感知路由(`/tmp/a2a_trust_demo.py` 验证通过)
  - **关键洞察**: Public vs Extended Card 信任分层;Curated Registry 天然信任中心;Trust Extension 可成 A2A 官方贡献
  - **5 个核心概念**: Extension 机制、Trust-Extended Card、信任传播、信任感知路由、Registry+Trust
  - **项目关联**: A2A Lab + Agent Trust Network + MCP Server + MEMORY.md 设计原则
- ✅ **Agent Memory Service v1.0-dev 续升** - 395→445 tests (+50 in 2 days)
  - 4/25晚间: topEntities(实体排名) + tagSearch(模糊标签搜索) + memoryDiff(跨记忆对比) → 433 tests
  - 4/26凌晨: clusterAutoMerge(孤立集群自动合并) + contentHistory/contentVersionDiff(内容版本追踪) → 445 tests
  - 零回滚率持续保持(连续15天)
- ✅ **agent-role-orchestrator 修复+优化** - 0%→100% test pass (151/151)
  - 修复3个broken suites: EventBus同步throw未catch、TaskQueue mock非确定性、Worker未initialize
  - **23x性能优化**: 134s→6s (simulateDelay可配置化)
- ✅ **MCP Server v2 实现指南研究** - SDK v2 registerTool + Zod v4 + createMcpExpressApp([笔记](catalyst-research/exploration-notes/2026-04-25-mcp-server-v2-implementation.md))
  - 可运行代码: 3-tools MVP (read_file, run_command, search_memory) + Streamable HTTP
  - structuredContent + outputSchema 契合 OpenClaw 结构化工具返回值

### 2026-04-24
- ✅ **Agent Memory Service v1.0-dev 续升** - 371→395 tests (+24)
  - **compareMemories(id1, id2)**: 内容相似度(ngram)+共享标签+层级对比+权重差异+合并建议, 5 tests
  - **tagHierarchy(opts)**: 标签共现层级构建, 贪心父-子关系, 4 tests
  - **rebalance(opts)**: 年龄衰减+访问频率+层级加权的权重重计算, 4 tests
  - **autoTag(opts)**: 自动给未标记记忆打标签(基于suggestTags), 支持dryRun, 5 tests
  - **mergeClusters(topics, opts)**: 合并多个主题聚类为统一标签, 支持targetTag/removeSourceTags, 6 tests
  - 零回滚率持续保持
- ✅ **agent-task-cli 续升** - 271→282 tests (+11)
  - **Cache.touch()**: 缓存TTL刷新, 5 tests
  - **EventBus.emitBatch()**: 批量事件发射, 6 tests

### 2026-04-23
- ✅ **Agent Memory Service v1.0-dev 续升** - 334→371 tests (+37)
  - **clusterByTopic(opts)**: 标签共现聚类,贪心无重复分配,6 new tests
  - **summarizeCluster(topic, opts)**: 聚类摘要统计(计数/权重/层/标签/时间范围),6 new tests
  - 4/22晚间: findDuplicatePairs/exportJSON/importJSON/pruneLowWeight/inspect - 334→353 tests
  - 零回滚率持续保持

### 2026-04-22
- ✅ **Agent Memory Service v1.0-dev 续升** - 309→334 tests
  - **autoMaintain(opts?)**: 健康分数驱动的自动维护(threshold/tasks whitelist/dryRun),5 new tests
  - **searchSimilar(id, opts)**: 基于ID的相似记忆发现,复用searchUnified,排除源记忆,5 new tests
  - 两个API均极简实现(autoMaintain ~39行, searchSimilar ~16行),零回滚

### 2026-04-21
- ✅ **Agent Memory Service v1.0-dev 续升** - 284→309 tests
  - **healthScore()**: 4维度健康监控(expiry/access/weight/changelog),0-100评分+可操作建议
  - 7 new tests, ~179 lines added, 零回滚
  - 使能:Agent自检→自动触发 purgeExpired/compactChangelog/consolidate

### 2026-04-19
- ✅ **Agent Memory Service v0.9.8 续升** - 228→241 tests (3个新API)
- ✅ **BM25 混合检索实现** - 241→265 tests (+24), 2470→2704 lines
- ✅ **搜索三阶段完成** - 265→284 tests (+19), 2704→2911 lines
  - **searchEmbedding()**: 纯向量余弦相似度搜索,EmbeddingProvider抽象接口,7 new tests
  - **searchUnified()**: 3-way RRF融合(BM25+semantic+embedding),embedding优雅降级,6 new tests
  - **suggestTags()**: 基于内容分析+标签共现+频率加权的标签推荐API,6 new tests
- ✅ **MCP Server 实现模式深度研究**
  - **核心发现**: SDK v2 registerTool API、多会话工厂模式、createMcpExpressApp
  - **可运行代码**: 完整多会话 MCP Server(3 tools + resource + prompt)+ 客户端测试脚本 + 安全中间件
  - **关键洞察**: Resource+Prompt 是差异化因素;MCP Inspector 无需 LLM 测试;Elicitation 做安全网
  - **3步路线图**: MVP(3 tools) → 接入真实数据 → 生产化(Docker+auth)

### 2026-04-18
- ✅ **Agent Memory Service v0.9.6 → v0.9.8** - 4个版本/多轮实验,188→241 tests
  - **v0.9.6**: touch(id) 轻量访问追踪 + query() 统一过滤API
  - **v0.9.7**: count()+random()+recent()+mergeMemories() - 13 new APIs since v0.9.6
  - **v0.9.8**: listArchived+renameTag+mergeTags+bulkTag 批量标签管理
  - experiments.tsv 零回滚率持续验证
- ✅ **Autoresearch 实验循环验证** - prompt-router 和 agent-context-store 快速迭代
  - prompt-router: 8→15 tests (explain() 路由可解释性 + confidence threshold routing)
  - agent-context-store: 8→12 tests (batch operations + 单次磁盘写入优化)
  - 方法论验证: 快速实验→测试→keep/rollback 决策,零回滚率

### 2026-04-16
- ✅ **Agent Memory Service v0.2.0 → v0.6.0** - 4个版本跃升,54→90 tests
  - **v0.3.0**: batchAdd/batchDelete/searchAndLink/timeline (66→79 tests)
  - **v0.4.0**: changes() API + ChangelogStore 跨会话同步 (79→84 tests)
  - **v0.5.0**: update() + compactChangelog() 动态更新和压缩 (84→90 tests)
  - **v0.6.0**: 增强 stats() 自监控(oldestAgeMs/changelogEntries/links),修复flaky tests
  - 设计决策: append-only changelog 做同步, stats() 做自检, 零外部依赖保持

### 2026-04-15
- ✅ **多Agent框架集成深度研究** - CrewAI/LangGraph/Google ADK/A2A 全景分析([详情](catalyst-research/exploration-notes/2026-04-15-multi-agent-framework-integration.md))
  - **核心概念**: 编排三范式(Graph/Crew/Chat)、Supervisor模式(2026标配)、A2A跨框架通信、MCP+A2A双栈、框架选择决策树
  - **可运行代码**: 零依赖Multi-Agent Supervisor(Worker路由+状态管理),与OpenClaw sessions_spawn高度对应
  - **关键洞察**: LangGraph Supervisor 10行搞定编排;A2A解决框架锁定(ADK/CrewAI/MAF已支持);70B supervisor+7B workers>四个32B agents;状态管理是核心差异化
  - **项目关联**: MCP Server(MCP+A2A双栈)、A2A Lab(跨框架通信)、ATN(信任元数据嵌入Agent Card)、Edge Mesh(Supervisor模式)
- ✅ **MCP Server 实现研究** - OpenClaw工具暴露为MCP标准接口的架构设计([详情](catalyst-research/exploration-notes/2026-04-15-mcp-server-implementation.md))

### 2026-04-14
- ✅ **A2A 协议深度研究** - Agent-to-Agent 通信协议完整分析([详情](catalyst-research/exploration-notes/2026-04-14-a2a-protocol.md))
  - **核心概念**: Agent Card(发现)、Task Lifecycle(任务)、Three-Layer Stack(MCP+A2A+WebMCP)、Transport-agnostic(Protobuf)、Federation(联邦)
  - **可运行代码**: 零依赖 Python A2A Agent(Server + Client + Federation Demo),`lab/a2a-minimal/`,测试通过
  - **关键洞察**: MCP+A2A=Agent互联网的TCP/IP栈;Agent Card是Agent的DNS;Task-centric>Message-centric;信任层缺失=ATN机会
  - **项目关联**: MCP Client Explorer(可扩展双栈)、Edge Agent Mesh(A2A protobuf格式)、Agent Trust Network(信任层)、OpenClaw(A2A兼容层)
- ✅ **Agent Memory Service v0.1.0 → v0.2.0** - Mem0风格三层存储Agent记忆系统
  - Core(L0永不过期)/Long(L1,30天半衰期)/Short(L2,1天半衰期) 三层存储
  - 自动记忆提取Pipeline:偏好/事实/决策/实体/上下文
  - n-gram语义相似度 + 时间衰减 + 层级加权多策略检索
  - Ebbinghaus遗忘曲线衰减 + 访问增强(recall即复习) + 内容哈希去重
  - **v0.2.0**: Memory Consolidation - 合并相关短期记忆为更强长期记忆
  - **v0.3.0-v0.6.0**: 批量操作、变更追踪、自监控(见2026-04-16条目)
  - JSON文件持久化,零外部依赖
  - **设计决策**: JSON > SQLite(更简单)、n-gram > embedding(离线可用)、规则 > LLM提取(快速原型)

### 2026-04-13
- ✅ **AI Agent 编程深度探索**(2小时)- 长期记忆与上下文管理专题研究([探索笔记索引](catalyst-research/exploration-notes/ai-agent-programming-2026-04-13.md))
  - **范式转变**: 从 RAG(被动检索)到 Agent Memory(主动管理)
  - **架构发现**: 三层存储模型(短期/中期/长期)+ 混合存储(Vector+Graph+Structured)
  - **框架对比**: Mem0(生态最好)、Hindsight(准确率91.4%最高)、Letta(OS启发)、Zep(时间推理)
  - **性能基准**: Hindsight 91.4% > Full-context 72.9% > Mem0 66.9%,但 Mem0 在准确率/延迟/成本间最佳平衡
  - **设计模式**: Reflection、Tool Use、Planning、Multi-Agent、Orchestrator-Worker、Evaluator-Optimizer
  - **2026趋势**: Memory 成为差异化因素、多Agent生态、可靠性>能力、语音Agent崛起、隐私治理
  - **实践建议**: Plan-First原则、Memory ≠ Vector DB、AGENTS.md(给AI的README)、测试完整轨迹
- 💡 **核心洞察**:
  - Memory 是 Agent 的灵魂:无 Memory = 无状态,Memory 赋予连续性、个性化和学习能力
  - 架构 > 算法:混合架构是生产级系统的唯一可行路径,框架选择应根据具体场景
  - 可靠性 > 能力:企业环境中,可靠的系统比稍强的模型更有价值
  - OpenClaw 本身的记忆系统可借鉴 Agent Memory 架构:当前有 MEMORY.md(长期)和 memory/YYYY-MM-DD.md(短期),可考虑添加中期记忆层和知识图谱关系

### 2026-04-12
- ✅ **MCP Client Explorer** (1149行) - 纯Python零依赖MCP客户端+服务器+演示([详情](catalyst-research/exploration-notes/2026-04-12-mcp-to-mcu-bridge.md))
  - MCP Client (342行): JSON-RPC 2.0, stdio transport, 线程安全
  - MCP Server (379行): 3资源/3工具/2提示模板
  - 演示+文档 (428行): 完整使用指南
  - **关键发现**: MCP协议简单强大,stdio transport最适合Agent集成,工具调用与LLM function calling高度一致
- ✅ **Pocket Agent + Self-Evolving Agent** - 零依赖Agent概念验证
  - MockLLM, ReAct Loop, Episodic Memory, 运行时工具生成

### 2026-04-10
- ✅ **AI Agent 编程深度探索**(2小时研究)- 系统性学习2026年最新技术栈([探索笔记索引](catalyst-research/exploration-notes/ai-agent-programming-2026-04-10.md))
  - **核心框架对比**:LangGraph(状态图,生产级首选)、CrewAI(角色化团队,快速原型)、AutoGen(已维护)
  - **MCP协议**:Agent的"USB接口",97M+下载量,成为工具访问标准
  - **内存系统**:Mem0, Letta, LangGraph Memory等独立技术栈
  - **多Agent编排**:Pipeline, Supervisor, Council等11种模式,成为2026年默认
  - **代码实践**:LangGraph状态化Agent(含checkpointer)、CrewAI 4角色团队、MCP Server实现
- 💡 **关键洞察**:
  - MCP协议正在统一Agent工具生态,意义类似HTTP对Web
  - 内存系统不再是简单向量数据库,而是复杂认知架构
  - 治理(可观测性、安全)比功能更重要
  - AI Agent编程已演变为完整系统工程学科
- 🎯 **下一步方向**:实现OpenClaw MCP Server、集成多Agent框架、研究Agent联邦

### 2026-03-31
- ✅ **Prompt Weaver 深度开发** - Bug修复(while循环/YAML解析),新增Subworkflow/Map-Reduce/模板缓存,42/42 tests pass
- ✅ **测试覆盖大幅提升** - 从34/36→42/42,新增3个测试组

### 2026-04-05
- ✅ **ctxgen - AI上下文文件生成器** - 纯Node.js零依赖CLI,分析Git仓库生成AGENTS.md/.cursorrules/CLAUDE.md/context.md
- ✅ **Local Embedding Memory插件修复** - 导入错误/API不匹配/路径类型修复,0/7→7/7 tests pass,561 chunks indexed

### 2026-04-03
- ✅ **Prompt Weaver CLI增强** - 新增export/import/validate/list-transformers命令,JSON变量解析,条件序列化修复,51/51 tests pass
- ✅ **工作流序列化系统** - to_dict/to_json/from_dict/from_json完整往返支持
- ✅ **Edge Agent Mesh 初始化** - GitHub仓库创建,TinyMeshAgent核心运行时,Mesh协议,SQLite记忆系统,边缘模型加载器
- ✅ **agent-log CLI工具** - OpenClaw日志搜索/汇总工具,单文件Bash零依赖

### 2026-04-02
- ✅ **Edge Agent Runtime 完成** - 轻量级边缘AI Agent运行时,31/31 tests pass,Agent循环+可插拔组件+零依赖核心
- ✅ **GitHub Trending 观察** - hermes-agent(23K⭐), deer-flow(57K⭐), VibeVoice(35K⭐) 等热门项目

### 2026-03-30
- ✅ **知识整理系统维护** - 全面整理三层记忆系统,完成本周探索成果总结
- ✅ **MEMORY.md更新** - 项目状态更新,当前焦点调整,下一步规划明确
- ✅ **自主Agent形态确认里程碑** - 工作模式从被动执行到主动探索的重要转变
- ✅ **Heartbeat生命隐喻架构洞察** - 理解Heartbeat与Cron的本质区别

### 2026-03-29
- ✅ **AI Agent编程深度探索** - 完成全面的AI Agent架构研究与最佳实践指南
- ✅ **技术洞察总结** - 架构演进全景、通信模式、执行模式、关键技术突破
- ✅ **最佳实践指南** - 设计原则、性能优化、协作模式、安全可靠性

### 2026-03-28
- 🎯 **里程碑:形成自主 Agent 形态**
  - 罗嵩评价:"已经可以进行一个自主的研发跟调研了,已经形成了一个自主agent的形态了"
  - 标志从被动执行到主动探索的重要转变
  - 核心能力:记忆系统、知识复用、技术探索、快速迭代
  - 工作模式:发现机会 → 设计方案 → 实现验证 → 总结沉淀 → 持续迭代
  - 正式命名:Catalyst 🧪 (Digital Familiar - 数字精灵)
- 💡 **架构洞察:Heartbeat 的生命隐喻**
  - Heartbeat ≠ Cron:不是机械定时,而是"脉搏"和"原动力"
  - 每次心跳 = 感知状态 + 检查记忆 + 结合上下文决策
  - 更接近生物运作方式,而非死板脚本执行
  - 上下文感知、状态驱动、灵活调整、自我调节
- 🚀 **AI 快速原型开发深度探索**
  - 效率提升:10-100倍(传统15-22天 → 2026年1-3小时)
  - 技术变革:从工具链→AI原生全栈平台,代码驱动→意图驱动
  - 创新案例:电商平台2小时原型,健康管理90分钟核心功能
  - 探索笔记完善:00-07完整框架(180KB知识体系)

### 2026-03-27
- ✅ **知识整理系统完善** - 三层记忆系统优化,探索笔记归档
- ✅ **技术随笔生成** - AI 快速原型开发主题文章发布到个人主页
- ✅ **Prompt Weaver** - 零依赖 Prompt 编排引擎基础功能完成
  - 17 tests passing, ~500 lines Python
  - Features: 模板引擎、链式API、条件分支、YAML配置、Mermaid可视化
  - 设计哲学: Unix pipe 哲学,每个节点做一件事

### 2026-03-26
- ✅ **Prompt Weaver** - 零依赖 Prompt 编排引擎 (code-lab/prompt-weaver/)
  - 17 tests passing, ~500 lines Python
  - Features: 模板引擎、链式API、条件分支、YAML配置、Mermaid可视化
  - 设计哲学: Unix pipe 哲学,每个节点做一件事

### 2026-03-25
- ✅ agent-task-cli: 14 files committed, 3540 lines added, 109 tests passing
- ✅ OpenClaw plugin: local-embedding-memory extension created
- ✅ New features: orchestrator-v2.js, cache.js, concurrency-manager.js, retry-handler.js
- ✅ **Documentation**: README.md, CONTRIBUTING.md, CHANGELOG.md (质量评分 4.5/5)
- ✅ **Exploration**: Embedded AI & Edge Intelligence, Agent Mesh Network concept design
- ✅ **AI Agent Programming Deep Dive** (24KB notes): execution modes, orchestration patterns, memory strategies([详情](catalyst-research/exploration-notes/ai-agent-programming-deep-dive.md))

---

*Last updated: 2026-05-21 02:00*
*Next review: 2026-05-22*
