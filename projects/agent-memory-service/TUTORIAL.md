# Agent Memory Service 教程

> 从零开始：让 AI Agent 拥有持久记忆

## 🎯 你将学到什么

- 三层记忆存储的设计原理和使用方法
- 从对话中自动提取记忆
- 多策略搜索（关键词 + 语义 + 图谱遍历）
- 记忆衰减与维护
- 高级功能：去重、合并、归档、增量同步

## 📋 前置条件

- Node.js 18+
- 无需外部依赖（纯 Node.js 内置模块）

## 第 1 步：安装与初始化

```bash
cd agent-memory-service
npm install    # 只有一个依赖：测试框架
```

```javascript
import { MemoryService } from './src/index.js';

const mem = new MemoryService({ dbPath: './my-agent-memory' });
await mem.init();
```

`dbPath` 是记忆数据的存储目录，所有数据以 JSON 文件保存。初始化后即可使用。

## 第 2 步：添加记忆

### 直接添加

```javascript
// 基础：添加一条短期记忆
const m1 = await mem.add({
  content: '用户问了一个关于 Rust 的问题',
});

// 指定层级和标签
const m2 = await mem.add({
  content: '用户偏好 TypeScript，不喜欢 Python',
  layer: 'core',       // 核心记忆，永不过期
  tags: ['preference', 'language'],
  entities: ['typescript', 'python'],
});
```

### 三层存储解释

| 层级 | 用途 | 衰减周期 | 适合存什么 |
|------|------|---------|-----------|
| `core` (L0) | 身份、偏好、关键决策 | 永不过期 | "用户是素食者"、"项目用 React" |
| `long` (L1) | 项目、人物、经验 | ~30天半衰期 | "上周讨论了 API 重构方案" |
| `short` (L2) | 近期对话、临时上下文 | ~1天半衰期 | "刚提到明天有会议" |

**选择原则**：如果忘记这条信息会造成严重问题 → `core`。如果一个月后还有参考价值 → `long`。其余 → `short`。

## 第 3 步：从对话自动提取

这是最强大的功能——无需手动添加，直接从对话中提取记忆：

```javascript
const newMemories = await mem.extractFromConversation([
  { role: 'user', content: '我喜欢用 VSCode 写代码' },
  { role: 'assistant', content: '好的，已记录您的偏好' },
  { role: 'user', content: '项目用的是 Next.js 框架' },
  { role: 'user', content: '我要下个月开始学 Rust' },
]);

console.log(`提取了 ${newMemories.length} 条记忆`);
// 自动识别：偏好 → core, 事实 → long, 计划 → core
```

提取器基于规则模式匹配（偏好、事实、决策、技术实体），无需 LLM。如果需要更高精度：

```javascript
// 使用 LLM 增强提取（可选）
const better = await mem.extractHybrid(text, async (prompt) => {
  // 调用你的 LLM API
  return await llm.chat(prompt);
});
```

## 第 4 步：搜索记忆

```javascript
// 基础搜索（混合策略：关键词 + 语义）
const results = await mem.search('TypeScript 项目');
for (const r of results) {
  console.log(`[${r.layer}] ${r.content} (score=${r.score.toFixed(2)})`);
}

// 只搜索核心记忆
const coreResults = await mem.search('偏好', { layer: 'core' });

// BM25 高级搜索（带解释）
const advanced = await mem.searchAdvanced('API 设计', { explain: true });
for (const r of advanced) {
  console.log(r.content, r.explanation);
  // { bm25: 1.2, ngram: 0.3, recency: 0.9, weight: 0.8, layer: 1.5 }
}

// 纯向量搜索（需要配置 embedding 函数）
const mem = new MemoryService({
  dbPath: './data',
  embedFn: async (text) => yourEmbeddingAPI(text),
});
await mem.init();
const vectorResults = await mem.searchByEmbedding('用户的技术栈', { threshold: 0.7 });
```

## 第 5 步：记忆关联

记忆不是孤立的，可以建立关联：

```javascript
// 手动关联
await mem.link({
  source: m1.id,
  target: m2.id,
  type: 'relates_to',  // 或 contradicts, supersedes, derived_from, causes
});

// 自动关联（基于共享的实体和标签）
const { created } = await mem.autoLink();
console.log(`自动创建了 ${created} 条关联`);

// 图谱遍历：从一条记忆出发，发现相关记忆
const { neighbors } = await mem.traverse(m1.id, { depth: 2 });
for (const n of neighbors) {
  console.log(`${n.hop} 跳: ${n.memory.content}`);
}
```

## 第 6 步：记忆维护

### 遗忘衰减

```javascript
const { decayed, removed } = await mem.decay();
console.log(`${decayed} 条记忆衰减，${removed} 条被遗忘`);
```

衰减基于 Ebbinghaus 遗忘曲线。每次搜索或获取记忆时，被访问的记忆会增强（类似人类复习）。

### 记忆整合

```javascript
// 将相似的短期记忆合并为长期记忆（类似睡眠整合）
const result = await mem.consolidate();
console.log(`${result.clusters} 个集群，合并了 ${result.merged} 条记忆`);

// 预览模式（不实际修改）
const preview = await mem.consolidate({ dryRun: true });
```

### 去重

```javascript
// 查找重复记忆
const dupes = await mem.findDuplicates({ threshold: 0.7 });

// 自动合并
const deduped = await mem.deduplicate({ threshold: 0.8 });
```

### 定期维护（推荐在 heartbeat 中调用）

```javascript
const report = await mem.scheduledMaintenance();
// 包含：decay + consolidate + compactChangelog + reindex
```

## 第 7 步：数据管理

```javascript
// 查看统计
const stats = await mem.stats();
// { total: 42, byLayer: { core: 5, long: 20, short: 17 }, avgWeight: 0.72 }

// 完整备份
const backup = await mem.exportAll();

// 恢复备份
await mem.importAll(backup);

// 归档旧记忆（移到冷存储）
await mem.archive({ olderThanMs: 90 * 24 * 60 * 60 * 1000 }); // 90天前

// 增量同步（跨 session）
const changes = await mem.changes(lastSyncTimestamp);
// { added: [...], updated: [...], deleted: [...] }

// 标签云分析
const tags = await mem.tagCloud({ top: 10 });
```

## 💡 实战模式

### Agent 启动时

```javascript
// 1. 初始化
await mem.init();
// 2. 维护
await mem.scheduledMaintenance();
// 3. 加载核心记忆作为上下文
const core = await mem.search('', { layer: 'core', limit: 10 });
```

### 每次对话后

```javascript
// 1. 从对话提取记忆
await mem.extractFromConversation(messages);
// 2. 自动关联
await mem.autoLink();
```

### 定期（heartbeat）

```javascript
await mem.scheduledMaintenance();
```

## 🏗️ 架构概览

```
MemoryService
├── MemoryStore      — 记忆存储 + 索引（tag/entity）
├── LinkStore        — 记忆关联图
├── ChangelogStore   — 变更日志（支持增量同步）
├── MemoryExtractor  — 对话→记忆提取（规则 + LLM）
└── EmbeddingProvider — 向量嵌入（可选，带缓存）
```

## 下一步

- 查看 [README.md](./README.md) 了解 API 概览
- 阅读 [源码](./src/index.js) 了解实现细节（~1000行，注释详尽）
- 尝试配置 `embedFn` 启用向量搜索
