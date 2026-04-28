# HEARTBEAT.md - April 28, 2026 (Monday)

## 待办任务

### 高优先级（本周）
- [ ] **实现 OpenClaw MCP Server** — TypeScript SDK v2 + Streamable HTTP，3 tools MVP（v2实现指南已就绪）
- [ ] **Agent Memory Service 生产化** — EmbeddingProvider真实接入(ONNX/远程API), Docker化
- [ ] **A2A Agent Trust 集成原型** - Agent Card嵌入信任元数据
- [ ] **集成多Agent框架** - LangGraph Supervisor桥接OpenClaw原型

### 中优先级（本月）
- [x] ~~AMS: searchByTimeRange, contentRollback~~ ✅ (04-27)
- [ ] AMS: memoryMerge(id1,id2) 冲突合并, contentVersion 持久化, searchByBranch(id)
- [ ] Hindsight 多策略检索原型
- [ ] Agent Trust Network Web UI
- [ ] Edge Agent Runtime Dashboard

### 探索性（下季度）
- [ ] Edge Agent Runtime 增强
- [ ] Agent Mesh Network P2P通信协议

## 系统状态
- **AMS v1.0-dev**: 499/499 tests, 56个API (8路检索+内容版本化+Hindsight Phase 1+contentBranch)
- **agent-task-cli**: 335/335 tests
- **agent-role-orchestrator**: 151/151 tests
- **本周重点**: MCP Server 实现 + AMS Phase 2 (searchGraph) + LangGraph bridge
- **autoresearch**: 零回滚率持续保持（连续22天）

## 近期发现
- AMS 8路检索完成: BM25+向量+RRF融合+实体+时间+事实类型+标签+内容模式
- AMS 内容版本化完成: history→diff→rollback→branch (四部曲)
- Hindsight Phase 1 完成: 四网络事实分类 (world/experience/opinion/observation)
- 下一步突破点: MCP Server 实现 + AMS searchGraph (图遍历) + LangGraph bridge
- Bug教训: `opts.x || default` → `?? default`（0是falsy值会误判）
