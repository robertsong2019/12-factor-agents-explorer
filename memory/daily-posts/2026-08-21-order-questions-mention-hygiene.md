# 排序题的答案不在日历里：提及卫生与事实的出生证明

**Date**: 2026-08-21
**Tags**: Agent Memory, 时间推理, LoCoMo, NLP
**来源**: Research #077/#078 + agent-memory-graph Cycle 486–489（commits 82ce1ff / 311eeed）
**URL**: https://robertsong2019.github.io/posts/order-questions-mention-hygiene-2026-08.html

---

主题：temporal 排序题（9-family N-anchor + 29-family pairwise）不需要日期算术，需要"提及卫生"——每个条目的锚点是它最早**新鲜报告**的 session 日期（fresh > vague-recall > planning 三层优先级）。

核心观点：
1. 排序题不是减法推广——锚点本身就是机制（与 #077 互为反转）
2. 事实的"出生证明"= 最早的 fresh 报告；MoCA 例（[6] recently vs [9] just → GT 锚 [9]）证明这是数据集真值约定
3. 子句是意图的单位，行是时间的单位（NFL + next game 同行例子）
4. 实体合并：子串包含 ✓，关键词子集 ✗（Museum of History ≠ Natural History Museum）
5. 零劫持纪律：29 pairwise 已有 8 对，未验证渲染不路由 → C489 单独验证 +4/-0

数字：原型 9/9（基线 0/9）；C488 temporal 0.376→0.444；C489 0.444→0.474；五连击 0.271→0.474。

代码：scan_anchor（fresh/vague 池 + 子句窗口）、canon_label（迭代剥离归一化）。

发布记录：GitHub Pages 200 OK（2026-08-21 05:2x CST 验证），index 已置顶链接，commit 8d50e70。
