# Abstention 教程 —— "I don't know" 是答案，不是失败

> LongMemEval `_abs` 弃权题的规则式解法：预设有失败检测、零提及测试、census 纪律。
> 对应 Cycles 448 / 489 / 498 / 513-519 · 零 LLM 调用 · 零外部依赖

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
      ↓（同一个 fabrication 点的三个新入口）
abs-form gates (C518) at-which 前缀、第 4 age 形态 other_until、
                      所有格 N-gallon 复合词 → 预设有失败
      ↓（门也会误杀）
forensics (C519)      老门全量 census：accent-fold + 取证驱动的 stop 表
                      把 9 fire 压到 5（严格子集，零新 fire）
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

C518 给了两个对照实例：`other_until` 形态（“我结婚时 Rachel 多大”）
**主体年龄锚全库缺失 = 已解析的否定存在 → counting 层 owns abstain**；
锚存在但取值不唯一 → fall-through 不猜。同一个形态里两种结局，
分界线就是“证据是否结构性缺席”。

### 5. 预设有失败不止一种入口（C518）

零提及检测器捕到的“缺席”有三种形态，修复位置各不相同：

- **at-which 对象问句**（“at which poster session…”）：问题形态正则
  补一个前缀，C516 的门自然释放——检测器本来就对，形态面漏了。
- **other_until 年龄锚缺席**：门在 counting-resolver 里，不在
  answer-gate——弃权发生在**锚定失败被发现的那一刻**。
- **所有格数字复合词**（“my 30-gallon tank”，语料只有 20/10-gallon）：
  **所有格数字属性 ≠ 可释义名词**——“my N-X” 里的 N-X 缺席就是预设
  失败，但绝不能泛化到裸名词复合（C510 sibling-signature 已证伪）。
  收窄限定条件，而不是加宽检测器。

### 6. 门也会误杀：老门也要 census（C519）

C513 的专名门上线三天，fire 面从未被审计；C516 给普通名词版做了
六轮 census，却没人回头着老版。全量普查发现 9 fire 里藏着
**4 个误杀**——语料明明提到（Bachelor 被转述成 "CS from UCLA"、
Hawaii 全文都在说 Maui、Aragón 提了 6 次、问 EPs 语料只有 EP），
却被零提及检测器判了缺席。修复的三个普适教训：

1. **accent-fold 要在 tokenize 之前、且两侧同做**。`[A-Za-z]` token
   类在 ó 处截断：'Aragón' → 'Arag'，`\barag\b` 永远匹配不上
   'aragón'。这是匹配层 bug 伪装成数据缺席——工具层 bug 伪装成
   数据异常家族的经典形态。
2. **stop 表必须由真实误杀驱动**，不拍脑袋：学位词（Bachelor/
   Master/PhD 是属性词不是实体）、媒体复数（EPs→EP）、地理下位词
   （Hawaii→Maui）——每一条都能指着具体误杀题。
3. **弃权率下降可以是好消息**：abstain 11.8%→11.4% 不是变弱，是
   误杀减少。所以弃权率要和误弃权取证一起读，不能单看方向。

修复只能减 fire 不能加（fold/stop/sub 都是加宽匹配或收窄 fire 面），
census 确认 POST fires ⊂ before fires，严格子集 → 不需要全量重跑
就能论证零新增劫持。

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
C518/C519 的行为变更由 `test_age_diff.py`（契约已改写为
claimed+abstain+anchored-fall-through 三态）与全套件
10040 tests 共同覆盖。
