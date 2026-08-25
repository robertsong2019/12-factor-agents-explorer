# Abstention 教程 —— "I don't know" 是答案，不是失败

> LongMemEval `_abs` 弃权题的规则式解法：预设有失败检测、零提及测试、census 纪律。
> 对应 Cycles 448 / 489 / 498 / 513-516 · 零 LLM 调用 · 零外部依赖

## 🎯 问题：强检索反而制造幻觉

LongMemEval 里有一族 `_abs` 题，ground truth 就是 **abstain**（"I don't know"）。
它们的构造方式是 **预设有失败**（presupposition failure）：

> "How do I get to Shinjuku?" —— 语料里只有 Harajuku，从来没有 Shinjuku。

陷阱在于：**可混淆的兄弟实体就在语料里**。检索强而切线
（strong-but-tangent），置信度居高不下，答案侧每一个门都会拿
Harajuku 的内容编一个答案出来。C511 HEAD 实测：24 道 abs-GT 题，
**18 道被编造回答，0 道弃权**。

RAG 的默认哲学是"检索到什么就答什么"——这在 _abs 族上恰好是错的。
正确姿势：**在回答之前检测预设有失败，宁可弃权，绝不编造**。

## 🧭 核心哲学：三律（弃权版）

1. **预设有失败优先于形态家族**
   问题里有一个全语料零提及的实体 → 这个问题**不可能**被抽取式回答，
   任何形态路由都不该碰它。所以 `neg_exist` 门排在所有 mechanism 门
   **之前**——gate 顺序本身是正确性面（C482 教训的弃权版）。
2. **零提及测试要够硬**
   word-boundary + case-insensitive + 全量 haystack（不是只扫 retrieved）。
   引号标题的正则伪影是唯一的假阳性来源——只认 bare token。
3. **Census 纪律**
   每个弃权门上线前全库普查：恰好 N 次 fire、全部是原本就错的题、
   对其余 470+ 题 **zero hijack**（不劫持任何 currently-correct）。

## 🏗️ 弃权家族谱系（谁在什么条件下说"不知道"）

```
entropy gate (C448)   ≥3 候选且 norm_entropy ≥ 0.95 —— 证据太散，最古老的祖先
      ↓
pairwise (C489)       "Which happened first, X or Y?" 一端锚定、
                      另一端全文零提及 → ABSTAIN（首个负存在弃权）
      ↓
pref (C498)           advice/recommendation 形态 —— GT 是合成元描述，
                      检索桥词法不可达，回显是范畴错误 → 诚实弃权
      ↓
neg_exist (C513)      问题中的专名全语料零提及 → 预设有失败 → ABSTAIN
      ↓（跑在所有 mechanism 门之前）
museum_count (C514)   计数家族内的弃权：月份窗口内零场馆到访
                      → presupposition-failure abstain（唯一返回
                      ABSTAIN 的 counting form）
      ↓
common-noun (C516)    对象名词换轨陷阱（violin/guitar、uncle/niece、
                      iPad/iPhone）：第一人称对象问句中普通名词
                      零提及 → ABSTAIN
```

## 🔑 关键概念

### 1. 预设有失败为什么排在形态门之前

形态路由（counting/temporal/pairwise…）假设"这个问题在问一个语料里
存在的东西"。预设有失败违反这个假设——先于它做任何路由都是在一个
不存在的问题上做题。`answer_question` 里的实际顺序：

```python
if self.pref_abstain and pref_form(question):   # C498 生成原生形态
    return ABSTAIN_ANSWER, meta
if self.neg_exist:                               # C513 预设有失败
    missing = negative_existence(question, haystack_text)
    if missing:
        meta["neg_exist_entity"] = missing
        return ABSTAIN_ANSWER, meta
# ……之后才是 ecm / pairwise / temporal_arith / counting
```

### 2. 常见名词 vs 专名：两个零提及检测器

- **专名版**（C513）：问题里的专有名词在全语料 word-boundary
  case-insensitive 找不到 → 弃权。census 13 fire/500，+3 全部是
  abs-GT 赢面，0 劫持。
- **普通名词版**（C516）：LME 的换轨陷阱把**被问的对象名词**换成
  兄弟词（练 guitar 的语料问 violin）。检测器限定"第一人称对象
  问句"形态，普通名词零提及 → 弃权。census v6：6 fire，5 赢。

两个检测器分开是因为假阳性面完全不同：普通名词太常见
（"time"/"days" 到处都是），不做形态限定会劫持大量正常题。

### 3. 弃权是特性，写进指标

abstain rate 和 exact 一起报告（如 abstain 8.6%）——
pref 门 29 次弃权把 abstain 从 3.2% 抬到 8.6% 是**增益**不是损失。
abs-GT 专用切片（abs24/abs30）追踪弃权题正确率：
C513 后 6→8，C516 后 abs30 10→15（+5/−0）。

### 4. 落回（fall-through）≠ 弃权

- **fall-through**：形态匹配但锚定失败 → 原样交给后续管线，
  后面的门可能救回来。C515 age_diff 的纪律：每个锚必须唯一取值，
  否则整个形态 untouched 落回。
- **ABSTAIN**：有结构化证据表明问题**不可答**（零提及/预设有失败/
  证据太散），直接返回 "I don't know"。

## 📊 负结果书挡：C512 RECORD-NEGATIVE

弃权家族的同期反面教材：knowledge_update #088 原型 oracle 19→54
（2.46×），生产化前 virtual-flip census 三重否证——判分鸿沟
（关键词判分幻觉）、形态不可分、跨类劫持净 −7。**原型数字只代表
研究方向，不代表生产收益**（insight #254），此后 census 升格为
所有 answer-face 生产化的前置关卡。负结果进 `experiments.tsv`
台账（484ea70），比错误上线便宜得多。

## 🧪 动手验证

```bash
python3 -m pytest test_pref_abstain.py -q      # C498 形态门 + census 契约
python3 -m pytest test_museum_count.py -q      # C514 零场馆弃权
python3 -m pytest test_neg_exist_common.py -q  # C516 换轨陷阱
python3 -m pytest test_age_diff.py -q          # C515 fall-through 纪律
```

每个测试文件头部 docstring 都写着 census 契约
（恰好几次 fire、零劫持）——改门逻辑前先读它。
