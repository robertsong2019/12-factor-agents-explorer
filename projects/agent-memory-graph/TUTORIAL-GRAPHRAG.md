# GraphRAG 端到端教程

> 从原始文本到知识图谱检索、诊断与基准评测的完整链路。
> 对应 Cycles 425-440 · 零外部依赖 · 零 LLM 调用成本

本教程串联 agent-memory-graph 的完整 GraphRAG 流水线：

```
segment_sentences (432)     缩写安全句切分
        ↓
chunk_text (440)            长文档分块（共享同一套句边界）
        ↓
extract_from_text (428)     规则式实体/关系提取 → 构建知识图谱
        ↓
graphrag_query (429/433)    关键词子图检索 + 事实型直接作答
        ↓
graphrag_explain (430)      逐查询诊断（为什么返回这些节点）
        ↓
graphrag_coverage_report (431/435/436)  全局检索健康度
        ↓
export_graphml (438)        图导出（外部工具互操作）
        ↓
run_amg.py (439)            GraphRAG-Bench (ICLR 2026) 完整适配器
```

## 🎯 你将学到什么

- 如何用纯规则方法从自由文本构建知识图谱（无需 LLM）
- 如何检索子图回答自然语言问题，包括事实型问题的直接作答
- 如何诊断"为什么检索不到"和"图谱哪里不健康"
- 如何把整个流水线接入官方基准 GraphRAG-Bench

## 📋 前置条件

```bash
pip install -e .        # 安装 agent-memory-graph（零依赖）
python3 -c "from memory_graph import MemoryGraph; print('ok')"
```

---

## 第 1 步：缩写安全的句切分

GraphRAG 的第一课来自 GraphRAG-Bench 小说域的惨痛教训：`Mr. Darcy`、`J. K. Rowling`、`St. Louis` 里的句点会被天真切分当成句子边界，把实体撕成碎片。

`segment_sentences()` 用两级 Punkt 式保护解决这一问题：

```python
from memory_graph import segment_sentences

segment_sentences("Dr. Smith met J. K. Rowling at Mr. Darcy's; it rained. St. Louis was wet!")
# => ["Dr. Smith met J. K. Rowling at Mr. Darcy's", 'it rained', 'St. Louis was wet']
```

**关键设计**：`extract_from_text` 和 `chunk_text` 共享这同一个函数——分块边界和提取边界永远一致，不会出现"半个实体落在一块的末尾"。

## 第 2 步：长文档分块

小说是整本书一个字符串，而规则提取器按句工作。`chunk_text()`（在 `run_amg.py` 中）把整句贪婪打包到 token 预算内：

```python
from run_amg import chunk_text

chunks = chunk_text(novel_text, max_tokens=512)
# 每块包含若干完整句子，估算 token 数不超过 max_tokens
# 不会在句子中间截断
```

## 第 3 步：从文本构建知识图谱

```python
from memory_graph import MemoryGraph

mg = MemoryGraph(":memory:")   # 或 "agent.db" 持久化

text = """Alice works at Acme Corp. Acme Corp is a company.
Alice created Neo4j. Bob works at Acme Corp.
Neo4j is a database. Alice is a person."""

result = mg.extract_from_text(text)
print(result["nodes_created"])   # 7
print(result["edges_created"])   # 6
print(result["entities"])        # [{'label': 'Alice', 'node_id': '...', 'new': True}, ...]
print(result["relations"])
# [{'source': 'Alice', 'target': 'Acme Corp', 'relation': 'works_at'}, ...]
```

**提取规则**（零外部依赖）：

| 环节 | 方法 |
|------|------|
| 实体检测 | 1-3 词大写短语、双引号/单引号术语 |
| 关系模式 | 7 种：`is_a`、`works_at`、`created`、`located_in`、`has`、`part_of`、`built` |
| 去重 | 按 label 精确匹配已有节点，存在即复用（不重复建） |
| 句切分 | 缩写安全（见第 1 步） |

重复调用是安全的——第二次处理同一段文本会复用全部已有节点，`nodes_created` 为 0。

## 第 4 步：检索与作答

`graphrag_query()` 接受自然语言问题，走五步流水线：
关键词提取（停用词过滤）→ 种子节点匹配（label/tags）→ 双向 BFS 遍历（≤ max_hops 跳）→ 节点排名（`keyword_score × degree_centrality × hop_penalty`）→ 输出 top-k 子图。

```python
answer = mg.graphrag_query("Who created Neo4j?", max_hops=2, top_k=5)

# 事实型问题走捷径：Cycle 433 的 fact-answer 直接返回边宾语
print(answer["fact_answer"])
# {'matched': True, 'relation': 'created', 'question_type': 'created_reverse',
#  'answers': ['Alice'], ...}

# 开放式问题走子图检索
print([(n["label"], round(n["score"], 3)) for n in answer["answer_nodes"]])

# context 是格式化好的字符串，可直接注入 LLM prompt
print(answer["context"])
```

**两种答案路径**：

| 路径 | 触发条件 | 返回 |
|------|---------|------|
| **fact_answer** | 问题命中 7 种问句 cue（Who created... / Where is... 等）且主语可解析 | 边的宾语列表，如 `['Alice']` |
| **answer_nodes** | 通用 | 排名后的子图节点 + context 字符串 |

主语解析有三级：精确匹配 → 正向包含 → 反向包含（`? LIKE '%'||label||'%'` 取最长内嵌 label）。

## 第 5 步：诊断单次检索

检索不到时，别猜——`graphrag_explain()` 告诉你每一步发生了什么：

```python
exp = mg.graphrag_explain("Who created Neo4j?")

exp["keywords"]           # 提取出的关键词
exp["keyword_matches"]    # 每个关键词如何命中种子（exact/prefix/contains/tag）
exp["matched_keywords"]   # 命中的关键词
exp["unmatched_keywords"] # 未命中的——检索失败的直接线索
exp["coverage"]           # 关键词覆盖率（0-1）
exp["answer_nodes"]       # 每个答案节点的得分分解
exp["fact_answer"]        # fact 路径诊断（含 no-seed 早退原因）
exp["suggestions"]        # 人类可读的改进建议
```

**典型排障**：
- `unmatched_keywords` 非空 → 图谱缺实体，重新 `extract_from_text` 补充语料
- 种子命中但答案弱 → `max_hops` 太小或图太稀疏，看下一步全局报告

## 第 6 步：全局健康度报告

`graphrag_coverage_report()` 从单查询诊断升级到整张图：哪些节点对检索不可见？关系类型是否单一到病态？

```python
c = mg.graphrag_coverage_report()

c["health_score"]           # 综合健康分（0-1）
c["label_coverage"]         # label 可匹配率
c["tag_coverage"]           # tag 覆盖率
c["orphan_count"]           # 孤立节点数（遍历不可达）
c["matchability"]           # 分级：{'high': 1, 'medium': 8, 'low': 0}
c["sparse_nodes"]           # 近乎不可见的节点列表
c["suggestions"]            # 上下文相关的改进建议

# Cycle 435 新增：关系维度
c["relation_distribution"]  # {'works_at': 2, 'is_a': 2, 'created': 2}
c["typed_edge_rate"]        # 有类型边的占比（1.0 = 全部有类型）
c["relation_diversity"]     # 关系类型多样性
c["top_relations"]          # 高频关系排行

# Cycle 436 新增：关系单一化告警
c["dominant_relation"]      # 占比最高的关系类型
# 当 typed_edges ≥ 5 且 top share ≥ 80% 时触发 diversify 建议
```

**解读速查**：

| 症状 | 含义 | 药方 |
|------|------|------|
| `sparse_nodes` 长 | 大量节点缺 tags/邻居 | 补 tags、补边 |
| `dominant_relation` 告警 | 全图都是 `related` 这类万金油边 | 换用 `extract_from_text` 获得类型化关系 |
| `orphan_count` 高 | 孤岛节点检索不可达 | `link` 到主干或删除 |

## 第 7 步：导出 GraphML

与外部工具（Gephi、networkx、GraphRAG-Bench 的 indexing_eval）互操作：

```python
result = mg.export_graphml("kg.graphml", overwrite=True)
# {'written': True, 'path': 'kg.graphml', 'nodes': 7, 'edges': 6, 'bytes': 2191}

# 默认拒绝覆盖已存在文件；overwrite=True 放行
# label/kind/relation/weight 全部保留，networkx.read_graphml 可完整往返
```

```python
import networkx as nx
G = nx.read_graphml("kg.graphml")   # 往返验证通过
```

## 第 8 步：接入 GraphRAG-Bench

`run_amg.py` 是官方基准（ICLR 2026）的完整适配器——检索式、分阶段、零 LLM 成本：

```bash
# 一次性下载（此后离线可用）
huggingface-cli download GraphRAG-Bench/GraphRAG-Bench \
    --repo-type dataset --include "Novel/*" --local-dir data/

# 跑 100 题 + 导出 GraphML 供 indexing_eval
python run_amg.py --data-dir data/ --out results/amg.json \
    --sample 100 --graphml results/amg.graphml
```

内部流程：

```
corpus + questions (HF 布局 JSON)
    → index_corpus()     # chunk_text + extract_from_text，规则模式
    → answer_question()  # graphrag_query + fact_answer 取边宾语
    → 官方 prediction schema（8 键严格对齐）
    → 可选 export_graphml()
```

官方 schema 的 8 个键：`id, question, source, context, evidence, question_type, generated_answer, ground_truth` —— 检索/生成评估器直接消费；诊断信息放在 summary dict 里，不污染 schema。

---

## 💡 完整实战：给 Agent 接上 GraphRAG

```python
from memory_graph import MemoryGraph, FastAppendQueue
from run_amg import chunk_text

mg = MemoryGraph("agent_memory.db")

# 启动：把领域文档灌进图谱（幂等，可增量）
for chunk in chunk_text(domain_docs, max_tokens=512):
    mg.extract_from_text(chunk, kind="knowledge", tags=["domain"])

# 运行中：会话记忆走双进程写路径（System-1 热路径）
faq = FastAppendQueue(mg, auto_flush_threshold=100)
faq.append("用户询问了退货政策", kind="interaction")

# 问答：先试事实捷径，再走子图检索
q = mg.graphrag_query("退货政策适用哪些商品？")
if q["fact_answer"]["matched"]:
    answer = q["fact_answer"]["answers"]
else:
    answer = call_llm(q["context"])   # context 已格式化好

# 每周：体检 + 清理
report = mg.graphrag_coverage_report()
if report["sparse_nodes"]:
    enrich(report["sparse_nodes"])     # 补 tags/边
mg.export_graphml("backup/amg.graphml", overwrite=True)
```

## 🔍 概念速查

| 概念 | 一句话 |
|------|--------|
| **规则式提取** | 用大写短语 + 关系模式匹配代替 LLM 抽取——可复现、零成本、零依赖 |
| **fact-answer** | 事实型问题（Who created X?）直接返回边宾语，跳过子图排名——Cycle 433 |
| **hop_penalty** | 离种子越远的节点得分越低——检索偏好局部相关性 |
| **matchability 分级** | 节点对关键词检索的可见度预测：high/medium/low |
| **关系单一化** | 全图 80%+ 是同一种关系 = 语义信息量趋零——Cycle 436 告警 |
| **FAMA 新鲜度** | 过时知识惩罚 15-43 分；`knowledge_freshness_report()` 按 5 级时间桶诊断 |

## 延伸阅读

- [README.md](README.md) — 完整 API 参考（565+ 方法）
- [TUTORIAL.md](TUTORIAL.md) — 基础入门：节点、边、衰减、可视化
- Cycles 425-440 实验记录：`experiments.tsv`

---

*Generated: 2026-08-15 · Documentation cron · Cycle 440 (8,942 tests)*
