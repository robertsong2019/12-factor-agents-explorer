# HEARTBEAT.md - April 20, 2026 (Sunday)

## 待办任务

### 🔥 今晚任务（4/20）
- [ ] **AMS 加 Skill/SOP 层** — 借鉴 GenericAgent，实现 `learnSkill()` + `getSkill()` API
  - 新增 L3 Skill 层（可复用执行流程，永不衰减）
  - `learnSkill({name, steps, trigger, successRate})` — 从执行经验中提炼 SOP
  - `getSkill(trigger)` — 按触发条件匹配已有 Skill
  - `listSkills()` / `deleteSkill()` — 管理接口
  - 目标：让 AMS 从"记忆系统"升级为"学习系统"
  - 预计新增 8-12 个 tests，~150 行代码

### 高优先级（本周完成）
- [ ] **实现 OpenClaw MCP Server** — TypeScript SDK + Streamable HTTP，3 tools MVP
- [ ] **Agent Memory Service 生产化** — EmbeddingProvider真实接入(ONNX/远程API), Docker化
- [ ] **A2A Agent Trust 集成原型** - Agent Card嵌入信任元数据
- [ ] **集成多Agent框架** - LangGraph Supervisor桥接OpenClaw原型

### 中优先级（本月完成）
- [ ] Hindsight 多策略检索原型
- [ ] Agent Trust Network Web UI
- [ ] Edge Agent Runtime Dashboard
- [ ] Edge Agent Mesh 继续开发

### 探索性（下季度）
- [ ] Edge Agent Runtime 增强
- [ ] Agent Mesh Network P2P通信协议

## 系统状态
- 周日凌晨，Agent Memory Service 搜索三阶段全部完成 ✅
  - v1.0-dev: 284/284 tests, 2911 lines, 零依赖
  - 搜索: BM25 + semantic + embedding → searchUnified() 3-way RRF
  - 标签: suggestTags() 自动推荐
- **⚠️ key-development-2/3 昨晚有编辑错误**: embedding.test.js 和 experiments.tsv 编辑失败，需关注
- **本周重点**: MCP Server 实现 (研究已就绪) + AMS 生产化
- **cron 状态**: 全部14个任务正常运行，consecutiveErrors=0（除 key-dev-2/3 各有1次）
