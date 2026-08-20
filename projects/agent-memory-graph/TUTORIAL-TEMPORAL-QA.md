# Temporal QA 教程 —— 不用 LLM 回答时间推理题

> LongMemEval temporal-reasoning 的规则式解法：form gate、日历锚定、abstention。
> 对应 Cycles 456-489 · 零 LLM 调用 · 零外部依赖

## 🎯 问题：temporal 问题根本不是 "when" 问题

C456 在 LoCoMo 上发现、C457 在 LongMemEval 上证实的事实：
**temporal-reasoning 类问题几乎从不是「X 是什么时候发生的」**。它们的真实形态是：

- **时长算术** — "How many days passed between X and Y?" / "How many weeks ago did I start X?"
- **状态时长** — "How long had I been X when Y happened?" / "How long have I been X?"
- **事件排序** — "What is the order of X, Y, Z?" / "Which happened first, X or Y?"

这类题的陷阱：检索做得再好也没用——答案不在任何一句话里，
**必须对两个日期做日历减法**。RAG 管线在这里天然哑火。

而数据集给了结构化接地（grounding）：每个问题带 `question_date`，
每个 session 带 `haystack_dates`。所以答案侧可以做纯日历算术，零 LLM。

## 🧭 核心哲学：三律

所有 temporal 路由共享同一条纪律（贯穿 C457→C489）：

1. **Form gate 触发，retrieved context 求解**
   触发只看问题形态，与类别无关；求解只看检索到的上下文。形态匹配但锚定失败 → 原样落回后续管线。
2. **绝不编造，宁可弃权**
   锚不定 → fall through。一端锚定、另一端全文零提及 → ABSTAIN（负存在弃权，这类题的 ground truth 本来就是 abstain）。
3. **Zero-flip 纪律**
   每个新路由上线前跑 A/B：OFF 臂必须逐题复现基线。只许加分，不许碰任何原本正确的题。

## 🏗️ 路由级联（谁先认领问题）

`amg_bench_quality.py` 的 `answer_question` 中，temporal 家族按此顺序布防
（**精确算术家族优先认领重叠形态**，C482 gate-order 教训）：

```
order_sort (C488)     "What is the order of X, Y, Z" — N-anchor 排序
      ↓ 形态互斥后
pairwise   (C489)     "Which happened first, X or Y?" — 双锚 + 弃权
      ↓ （必须在 TA 之前：TA 的 "first" 形态会误抢此家族 2 题）
temporal_arith (C457) "how many days between/ago/since/before" — 双锚日历减法
      ↓ 窗口锚不定时全图重试 (C472)
pp_duration (C486)    "How long had I been X when Y?" — 过去完成时
pure_tenure (C487)    "How long have I been X?" — all-keywords 单行墙
      ↓
counting (C483-485)   multi_session 计数家族
```

## 🔑 关键概念

### 1. 锚定：最早 FRESH 行

回答 "which came first" 的本质是给每个候选事件找一条**可信的、带日期的行**。
不是任意匹配行——同一事件会被 planning（"I'm thinking of visiting MoMA"）、
vague recall（"I remember the MoMA trip"）、fresh report 反复提及。
可信度排序（C488/C489 反复验证）：

```
fresh report > vague eventive > planning
```

- **fresh** 行有话语时间戳标记：`today / just / yesterday / last night / this morning`
- **planning** 标记只作用于它所在的**子句**（clause = intent 的单位）——一行里可以既计划一件事、又新鲜地报告另一件事（C488 granularity law）
- 话语时间戳作用于**整行**；两者作用域不同，不能混

### 2. 子句粒度

C488 的教训：把 planning 标记当行级过滤会错杀同行的新鲜报告。
例句 "I'm planning to visit Rome, though I just got back from Tokyo"——
Rome 是 planning，Tokyo 是 fresh，同在一行。窗口载荷只认子句。

### 3. 负存在弃权

"Which happened first, learning piano or joining the choir?"
若 piano 锚定成功、choir 全文**零提及** → 答案是 ABSTAIN。
这类题的 ground truth 就是 abstain（另一事件在 haystack 里不存在）。
注意区分：**有提及但锚不定** ≠ 零提及——前者 fall through，后者弃权。

### 4. Sub-24h tie → fall through

两个锚落在 24 小时内 → 不裁决。原因：rec-echo hazard——
同 session 内助手复述用户话会被再次锚定，分钟级精度反而制造假信号。

### 5. 绝对日期锚定

C482 洞察的泛化：每个 "N units ago" / "for N units" 表达式
都锚定到**所在 session 的绝对日期**，而不是相对解读。
之后一切答案都是纯日历减法。

## 📈 战绩：temporal-133 演进

| Cycle | 路由 | temporal-133 | 变化 |
|-------|------|:---:|:---:|
| — | 基线 | 0.323 | — |
| C486 | pp_duration | 0.376 | +7/−0 |
| C487 | pure_tenure | 0.376 | (multi_session +8) |
| C488 | order_sort | 0.444 | +9/−0 |
| C489 | pairwise | **0.474** | +4/−0 |

每一步 zero-flip：从没有一道原本正确的题被翻错。

## 🛠️ 上手

```python
from amg_bench_quality import (
    temporal_arith_form, answer_temporal_arith, temporal_arith_judge,
    pp_duration_form, answer_pp_duration,
    order_form, answer_order, order_judge,
    pw_form, answer_pairwise, pairwise_judge,
)

# 1) 形态门：只认已知形态，未匹配返回 None（fall through）
form = temporal_arith_form("How many days passed between I moved and the wedding?")

# 2) 带日期上下文求解：dated = [(date_str, turns), ...]
answer, detail = answer_temporal_arith(question, dated, question_date)

# 3) 三种结果
# answer == "15"        → 日历算术命中
# answer is None        → 锚未解析，fall through 给后续管线
# answer == ABSTAIN     → 负存在弃权
```

细节都在 `answer_pairwise` 的 decision matrix 里（代码即文档）。

## 🧪 验证方法

```bash
python3 -m pytest test_amg_temporal_arith.py test_pp_duration.py \
    test_order_forms.py -q
```

## 🔗 延伸阅读

- [TUTORIAL-GRAPHRAG.md](TUTORIAL-GRAPHRAG.md) — 同一哲学在 GraphRAG 检索上的应用
- `amg_bench_quality.py` 模块头注释 — LongMemEval 适配器全貌
- `experiments.tsv` — 每个 cycle 的 A/B 数据（off-arm 复现纪律的原始记录）
