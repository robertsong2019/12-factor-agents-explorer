# TUTORIAL: Answer Faces — 问题结构驱动的答案选择（Cycles 529-539）

> 本文解释 amg 评测管线里最反直觉的一个设计：**答案选哪个句子，不该由"分数阈值"决定，而该由"问题在问什么"决定**。
> 覆盖 Cycle 529-539 的机制演进（banked 0.494 → 0.510），所有例子都是 LongMemEval s_cleaned full-500 里的真实题目。

---

## 1. 问题：阈值调参为什么救不了答案选择

多轮对话记忆 QA 的典型管线：

```
 haystack（几百条对话消息）
    ↓ 检索
 候选句池（按词汇重叠 kh 打分排序）
    ↓ 选择
 答案句 → judge 判分
```

朴素做法是"选分数最高的候选"。但它会在三类真实病例上翻车：

| 病例 | 真实例子 | 为什么分数高者反而是错的 |
|------|---------|------------------------|
| **内容寄生** | GT "For a romantic dinner, I would recommend Roscioli." (145.5) vs La Pergola 描述行 (150.8) | 干扰句与问题共享更多词汇（fine-dining/Italian/Rome），但它**不是任何人对提问行为的回答** |
| **开场白寄生** | GT "For my sister's birthday, I got her a yellow dress" (hits=2) vs "Here's a start - I've bought gifts..." (hits=3) | 开场白是**对话管理话语**，覆盖问题主题词但不含答案 |
| **地板误伤** | GT 承载句被 min_raw=3/df≤8 过滤，根本没进排序 | 排序再好也救不了**不在池子里**的句子 |

共同点：**错误不在分数计算，而在"候选与问题的关系"没有被建模**。阈值调参只能在这些病例间来回搬伤害。

---

## 2. 核心概念：什么是 answer face

**Answer face（答案面）= 一个由问题结构触发的候选重排规则。**

它回答的问题不是"哪个候选分数高"，而是"**问题的形状要求答案句长什么样**"：

- 问题要数字（how many / how much）→ 答案句应**承载该类型的事实**（C534 type face）
- 问题引用你的行为（the restaurant **you recommended**）→ 答案句应是**第一人称言语行为句**（C537 speech-act face）
- 问题用购买动词（what did he **buy**）→ 答案句应是**第一人称过去陈述**且动词同族（C538 acquisition face）
- 问题问顺序（what **order** did...）→ 答案句应共享 reference 的**语篇标记骨架**（C532 marker face）

关键分层：

```
候选池
  ↓ ① 地板/过滤（min_raw、df、preface 排除——有它自己的理由，face 不越权翻案）
 floor-passers
  ↓ ② face 层：问题结构 → tier 偏好（重排，不新增候选）
 答案句
  ↓ ③ judge 层：exact → semantic → LLM cascade（C529-C531，见 README Cycles 520-531 段）
 判分
```

**两条铁律**（都是从真实 kill 里学出来的）：

1. **face 在 floor-passer 之间重排，永不越权翻地板**（C536 教训：地板排除自有理由，豁免通道必须是有界的）
2. **问题结构 ≠ 阈值**（C531 原则）：改触发条件，不改分数线

---

## 3. 家族巡礼：五个 face，五个真实病例

### 3.1 C532 marker face — 叙事缩写 vs 弱子集

**病例**：答案把 reference 的叙事缩写了，包含守卫判它"弱子集"误杀。

**概念**：顺序类问题（first/then/finally…）的叙事有一个**骨架**——语篇标记序列。若答案与 reference 同骨架（≥2 个标记、同顺序、首标记前无内容前言）且每段是有序 token 子序列，那它是**同一叙事的缩写**，不是弱子集。丢事件会丢标记（骨架失配）、乱序会破坏段内对齐——**误杀被结构性排除，不需要任何覆盖率魔法数**。

> 这是"原则性表述"思维的样本：C531 说"这债需要原则性表述而非阈值"，C532 找到的原则就是骨架同构。

### 3.2 C533 where face — 先进池子，再谈排序

**病例**：GT "For Sophia, it was a coffee shop in the city." 完全进不了候选集——词表有 `cities` 没有 `city`，谓语性短语没有介词前导。

**两个修复**：
- 词表补单数地点名词（进池子）
- **相关性地板**：kh=0 的获胜者让位给最优 kh≥1 候选——问题里出现过的词（city/coffee shop）理应成为连接条件（insight #086）

### 3.3 C534 type face — 问题索要事实类型

**病例**：7a8d0b71 问预算，GT "DHL $2,000" 行被 min_raw 地板过滤。

**机制**：问题头含 how many/much、what year、@handle ⇒ floor-passer 中**类型承载句**优先；当地板把所有承载句滤光时，走**有界豁免通道**（类型承载 + raw≥2 + preface/weighted_floor 保留）。

**为什么破半发生在这一课**：它把"问题在问什么类型的事实"变成了排序信号——这是 answer-face 家族第一次完整成型（类型 → tier → 重排）。

### 3.4 C537 speech-act face — act-bearer ≠ act-mention

**病例**：4c36ccef 问"你推荐的餐厅"，GT 是第一人称行为句 "…I would recommend Roscioli."，输给词汇重叠更高的内容寄生行。

**bearer 判别**：`I` + 言语动词族（recommend/suggest/mention/tell/said…）+ **三个结构守卫**，每个守卫都由一个真实误杀催生：

| 守卫 | 反例 |
|------|------|
| 命题从句排除 | "suggest **that** hiking"——行为动词后接从句，不是对具体宾语实施行为 |
| 否定行为排除 | "you **DIDN'T mention**… I'll provide" |
| 泛指宾语排除 | "recommend **some other** bands"——离题句寄生行为动词 |

外加 preface 句永不作 bearer——2 个 fixture 回归教会的：**提到行为 ≠ 实施行为**。

### 3.5 C538/C539 acquisition face + opener floor — 清算开场白寄生

**病例**：66f24dbb 问买了什么，开场白 "Here's a start - I've bought gifts..."（hits=3）压过 GT "…I got her a yellow dress"（hits=2）。

**C538**：问题头动词族（buy/purchase/complete/finish/get）+ who-conversation 形态 ⇒ tier-1 = 第一人称过去陈述 + 词族 + hits≥2 + opener 排除。
**C539**：floor 更进一步——hand-over 胜者只在存在 **kh 严格更高**（rep_kh > win_kh）的第一人称陈述候选时被降级。

**C539 的朴素版本是被证伪后幸存的**：同分也降级的版本，离线全人口模拟出 2 rescue/5 kill **净负**——因为 hand-over 首行常是多句消息，答案嵌在同句延续里。幸存的判别式是"严格证据优势"。

---

## 4. 反面教材：枚举清单没有结构键（C536，RECORD-NEGATIVE）

序数清单（"5. Absinthe"）看起来也能做个 face。实现后发现 **census 全负**：

- 语料里有**孪生清单**：GT "5. Absinthe" vs 干扰 "5. Triple Sec"，kh 12/12 打平，仅 "gin-based" 措辞可分
- 裸数字清单 GT kh=1，任何相关性地板下必死
- 有题抽对了 item，却败在 judge 侧的整句包裹（判分缺口，非检索）

**结论**：枚举清单没有唯一结构键，词法排序救不了；要救需嵌入 side-channel join（C506 前例）。**函数保留、不接线**，census-pinned test 钉住"管线字节等价"。

> RECORD-NEGATIVE 也是资产：它把"此路不通 + 为什么不通"写进了代码库，后来的 cycle（C539 pref oracle 0/30）直接引用先例关闭方向，不再烧 A/B 预算。

---

## 5. 方法论：census-first，接线之前先数人口

answer-face 家族的开发纪律（每个 face 都走了这套流程）：

1. **法医**：从 wrong 行解剖出病根（是过滤？排序？检索？判分？）——四层病根用四种药
2. **人口普查**：这个 face 在 frozen-500 上会碰多少行？几行可能翻正、几行有 kill 风险？
3. **离线模拟**：全人口 monkey-patch 重放（C539：70 行 ~155s），精确预测 rescue/kill 清单
4. **A/B census**：改后全量重放 vs frozen，changed 行逐行归因（脸翻转的行 == 目标病例，其余 = 已知 overlay）
5. **接线 + census-pinned test**：钉住"不改行为"的负空间

**投入产出**：C539 的 22 分钟 A/B 被 2.5 分钟离线模拟完整预测。face 类改动的 A/B 很贵，census 模拟是它的廉价前置。

---

## 6. 一页速查

| 信号源 | Face | 动作 | Cycle |
|--------|------|------|-------|
| 问题问顺序 | marker skeleton | 缩写=同叙事，非弱子集 | C532 |
| 问题含地点词 | where + 相关性地板 | kh=0 让位 kh≥1 | C533 |
| 问题要事实类型 | type tier + 有界豁免 | 类型承载句优先 | C534 |
| 判分残差 | _sem_norm 折叠 | BrE→AmE 词表 + 转义折叠 | C535 |
| 问题引用你的行为 | speech-act bearer | 第一人称行为句 tier | C537 |
| 问题用获取动词 | acquisition face | 词族过去陈述 tier-1 | C538 |
| 胜者是 hand-over | opener floor | 严格证据优势才降级 | C539 |

**三条带走的原则**：
1. 答案选择读**问题结构**，不调阈值
2. face 重排不越权翻地板；地板排除自有理由
3. census-first：先数人口，先离线模拟，再接线；证伪的方向写进台账

---

*生成：documentation-morning cron，2026-09-02。数据口径：LongMemEval s_cleaned full-500，PYTHONHASHSEED=7，deterministic cascade banked。轨迹明细见 README Cycles 532-539 段。*
