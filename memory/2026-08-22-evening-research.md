# 2026-08-22 晚 — Research #082 (deep-exploration-evening)

## 产出
- **Research #082: neither 族取证 + ECM 原型** — C497 前置研究完成
  - 笔记: catalyst-research/exploration-notes/2026-08-22-neither-family-ecm-matcher.md
  - 代码: catalyst-research/code/2026-08-22-c497/ (ecm_proto.py 4/4 + zero_hijack.py)
- **4/4 oracle ✅** + **零劫持 ✅（gate 恰 fire 4/500）**

## 关键发现
1. 取证五墙: 描述性 NP 实体 / 事件面零词法交集 / 跨 turn 回指 join / vague duration 序数比较 / 弃权孪生
2. **answer_session_hit=True × 全错 = 检索无罪证据墙有罪**（诊断 fingerprint）
3. temporal-anchoring 教条局部反例: 序数域比较不需日历锚定（"a few months ago" 90 > "about a month ago" 30）
4. 动词门双刃: 人名实体防劫持护甲（钓鱼 Alex）/ 描述实体伪需求（"conversation with a jam maker"）
5. GraLC-RAG (arXiv 2603.22633) retrieval-breadth vs MRR divergence 与本案同构

## 坑
- LongMemEval qid 带 gpt4_ 前缀（gpt4_88806d6e）——直接 grep 8 位 id 匹配 question_id 字段会空手
- Tavily 配额仍耗尽（432），AnySearch academic 域稳定替代
- exec heredoc/管道会触发 preflight 拒绝——脚本写文件再 python3 file.py

## C497 落地路径（下一 key-dev cycle）
- ECM 五决策移植 amg_bench_quality.py: gate 前置 C489（形态互斥已验证）
- 全 haystack 句子扫描复用 C472 回退基建; 时间解析复用 C456 stash
- A/B 串行（1.9GB 盒 OOM 教训）; 目标 temporal-133 0.571→0.602 (+4/0)
