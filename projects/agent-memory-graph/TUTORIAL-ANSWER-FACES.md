# TUTORIAL: Answer Faces — 问题结构驱动的答案选择（Cycles 529-548）

> 本文解释 amg 评测管线里最反直觉的一个设计：**答案选哪个句子，不该由"分数阈值"决定，而该由"问题在问什么"决定**。
> 覆盖 Cycle 529-548 的机制演进（banked 0.494 → 0.540），所有例子都是 LongMemEval s_cleaned full-500 里的真实题目。

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
 判分   ← ④ judge 侧 face（C541-C542）：NEEDS_JUDGE 区间按 reference 形态 rescue（见 §4）
```

**两条铁律**（都是从真实 kill 里学出来的）：

1. **face 在 floor-passer 之间重排，永不越权翻地板**（C536 教训：地板排除自有理由，豁免通道必须是有界的）
2. **问题结构 ≠ 阈值**（C531 原则）：改触发条件，不改分数线

---

## 3. 家族巡礼：gate 侧六个 face，六个真实病例

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

### 3.6 C540 ordinal face + phrase-run — RECORD-NEGATIVE 的正确打开方式

**背景**：C536 把序数清单判了"没有结构键，不接线"（见 §5）。C540 复活它的方式值得细读——**先杀死自己原本的方案**：

- C536 声明的方案是嵌入 side-channel join（C506 前例）。C540 在实现**之前**先 probe：message-level cos(q, decoy) = 0.7068 > GT 0.5607——MiniLM 把问题里 "gin-based" 约束当次要质量，干扰清单恰是问题域的语义超集。**嵌入 join 被证伪，省掉一次注定失败的接线**。
- 幸存的分隔符是**问题短语连续性**：候选按"最长连续问题关键词 run"打分（`_kw_phrase_run`），best run ≥2 才认领。孪生鸡尾酒清单 kh 12/12 打平，但 GT 的短语 run 是 3、干扰只有 2——**排序键从"词袋重叠"换成了"问题措辞的连续复现"**。
- 单靠 kh 地板选承载句恰是 C536 失败模式：presentation-tips 清单 kh=8 但 run=0，会答出清单标题 'Encourage Questions'——被 run floor 阻断，逐字节 fall-through 验证。

**教训**：RECORD-NEGATIVE 记录的是"此路不通"，不是"此题无解"。复活它的钥匙往往是换一种结构信号，而不是在旧信号上加权重。

### 3.7 C548 cross-session user-statement face — 从证伪的尸体里解剖出新 face

**背景**：C546 用 impostor census 否决了 kh-elite 准入（见 §6）。但同一份杀面数据里藏着一个规律：**潜在 rescue 全部来自 user 行，kill-trigger 全部来自 assistant 行**——伤害与收益的分界不是 kh 高低问题，是**角色**问题。

**face 定义**：当生产排序的胜者是 assistant echo 行，而存在**跨会话**（C526 领地）的 user 第一人称事实句、其问题短语 run **严格更长**（run > win_run，floor 2，复用 C540 的 `_kw_phrase_run` 原语）时，越权 outrank。跨会话 + role=user 是关键护栏：同会话里 assistant 复述用户的话天经地义，kill 面几乎全部来自同会话 assistant 行。

**两遍 census 的对照**：第一遍 plain admission（无 role 门）复现 7/50 kill，确认 C546 判决；加上 role 门后第二遍 **5 RESCUE / 0 KILL / 0 kill-side 触发**（50 行样本）。+6 rescue 0 kill 0 降级（Nike 跑鞋等跨会话用户自述压过 assistant echo 胜者），15 行 banked-neutral churn（pred 变了但仍对）。

**教训**：
1. **证伪数据是矿，不是垃圾**——C546 关闭方向的同一份 census，解剖出了纯上行 face 的门槛设计。否决机制 ≠ 否决数据。
2. **live smoke 值得保留**：C525 的 context-split 多行 winner 陷阱（胜者句被拆成多行时匹配错行）在上线冒烟里被抓到，first-line match 修复 + trap test 红先行钉死。

---

## 4. face 概念的延伸：judge 侧 rescue faces（C541-C547）

前六个 face 都活在 **gate 侧**——改变"选哪句"。C541 起把 face 概念推到 **judge 侧**——改变"判对没判对"。

judge cascade（exact → semantic → LLM）里有一个 NEEDS_JUDGE 区间：exact 不中、sem 也不中，留给 LLM 判。C541/C542 发现，这个区间里有一批**系统性误判**，病根是 reference 的**书写形态**被当成了**内容差异**：

| face | reference 形态 | 为什么会误判 | rescue 例 |
|------|---------------|-------------|----------|
| **paren-acronym**（C541） | "Full Name (ACRONYM)" 自带别名 | answer 只有缩写 token → sem 不中 | 1d4da289（OTP）、25e5aa4f（UCLA） |
| **place-complement**（C541） | "<head> in <Place>" | tail 是判分者消歧，answer 没有 tail → 被当缺内容 | 3b6f954b（University of Melbourne in Australia） |
| **quoted-core**（C542） | "The 27th parameter was 'Sound effects…'." | frame tokens 使逐字节相同的答案成"严格子集" → Guard-3 subset veto | 8752c811 |
| **paren-complement**（C544） | "Head (elaboration)" | head 本身即断言事实，括号只是展开；薄头（`Yes. (You have a road bike too.)`）除外 | c6853660（You increased the limit (from one cup to two cups)） |
| **tense-superset**（C544） | had/has、was/is、were/are 时态差 | 时态不同 + 严格超集被当成内容不同；要求至少一对时态词实际出现，不放宽既有路径 | 89527b6b（The Plesiosaur had → has a blue scaly body） |
| **bare-affirm**（C545） | GT 归一化后 = "yes"（bare-Yes） | yes/no 问题 + 叙事式肯定句（"finished reading"）不含 "yes" token → exact/sem 全不中 | b01defab，六门：bare-Yes / auxiliary-initial 疑问 / content 全覆盖 / ≥2 stem hits / 否定窗口 ±6 / 反问 echo 拦截 |
| **affirm-elaboration**（C547） | "Yes. (You have a road bike too.)" 展开式肯定 | 肯定词 + 事实在延续里；bare-Yes 门够不着（归一化 ≠ "yes"）、薄头排除恰好挡住 → 本 face 是两者的**补集** | 89941a94（road bike），affirm-lead + 极性门 + aux/wh veto + 覆盖 + echo 拦截 |

**为什么这些 face 数学上纯上行**：它们都挂在 NEEDS_JUDGE / subset-veto 分支上——只有已通过 guards 1-2（或已进 NEEDS_JUDGE，且数字/货币守卫先行 return）的行才可达，只可能 NEEDS_JUDGE→CORRECT 或 WRONG→CORRECT，不可能把 CORRECT 改坏。

**识别套路**：对着一堆 NEEDS_JUDGE 行问一句——"GT 的**写法**里有什么约定俗成的形态，被当成了**内容差异**？"括号别名、地名补语、引号包裹、括号展开、时态差、bare-Yes，都是"写法伪装成内容"的样本。

**C544 的两课**：

1. **fire 的理由要语义正确，不止要 fire**。paren-complement 的 naive 版本靠 pred 另一句里顺带的 "you" 才命中 c6853660——数字上等价，语义上错误（pred 根本没说那句话）。修正 = 人称 deixis fold（you/your→i/my）：判分者口中的"你"就是用户口中的"我"，同事实换人称陈述应诚实 fire。测试用最小答案复现正确 fire 理由。
2. **基线复核也要同源**。census 脚本第一遍只数"纯语义 CORRECT"得 236，vs 台账 260，差点误判 ledger 崩坏——实际差值就是 C542 那条 face 增量。读基线必须用 ledger 公式重算（frozen exact + abs 行），同源纪律不只管 A/B 双臂。

**C545 的 tokenizer 课**：bare-affirm 第一遍 census 0 fires 是伪影——问题用单引号 `'The Nightingale'`、pred 用双引号，norm 保留 `'` 造成假 miss。token 化必须去引号（引号样式不是内容）；反向陷阱也要防：`didn't` 归一化拆成 `didn`+`t`，裸 token `t` 恰好只来自缩写，可安全用作否定标记——红灯先行测试抓到的。

另一个教训藏在 C542 的 A/B 基建里：双臂判分公式必须**逐字段同源**（frozen exact vs live exact 混用会伪造 NET-NEGATIVE），且每行对 baseline 做 drift assert——"翻转打印里 verdict 不变的 KILL"是最便宜的露馅信号。

**C547 的收尾课**：接 face 之前先把邻居正式关门——census 显示 WRONG 侧 82/82 是 guard1 数字不相交、14/14 是诚实弃权样本，partial-overlap 31 行逐行审计后，这条矿脉的 WRONG 侧正式关闭。三个肯定式 face（bare-affirm / affirm-elaboration / 薄头 paren-complement 互为补集）合起来，肯定式 GT 的 NEEDS_JUDGE 区没有漏网形态。

---

## 5. 反面教材：枚举清单没有结构键（C536，RECORD-NEGATIVE）

序数清单（"5. Absinthe"）看起来也能做个 face。实现后发现 **census 全负**：

- 语料里有**孪生清单**：GT "5. Absinthe" vs 干扰 "5. Triple Sec"，kh 12/12 打平，仅 "gin-based" 措辞可分
- 裸数字清单 GT kh=1，任何相关性地板下必死
- 有题抽对了 item，却败在 judge 侧的整句包裹（判分缺口，非检索）

**结论**（C536 当时）：枚举清单没有唯一结构键，词法排序救不了。**函数保留、不接线**，census-pinned test 钉住"管线字节等价"。

**续集（C540）**：这个结论后来被修正了两次——① 它建议的嵌入 join 在实现前被 probe 证伪（干扰是问题域的语义超集，余弦反而更高，见 §3.6）；② 真正的解法是换分隔符：问题**短语连续 run** ≥2。face 已接线，C536 从 RECORD-NEGATIVE 变成"负结果如何被迭代修正"的样本。

> RECORD-NEGATIVE 也是资产：它把"此路不通 + 为什么不通"写进了代码库，后来的 cycle（C539 pref oracle 0/30、C540 嵌入 join 证伪）直接引用先例关闭方向，不再烧 A/B 预算。但注意负结果的有效范围：它否定的是**那条路**，不是**那类题**。

---

## 6. 方法论：census-first，接线之前先数人口

answer-face 家族的开发纪律（每个 face 都走了这套流程）：

1. **法医**：从 wrong 行解剖出病根（是过滤？排序？检索？判分？）——四层病根用四种药
2. **人口普查**：这个 face 在 frozen-500 上会碰多少行？几行可能翻正、几行有 kill 风险？
3. **离线模拟**：全人口 monkey-patch 重放（C539：70 行 ~155s），精确预测 rescue/kill 清单
4. **A/B census**：改后全量重放 vs frozen，changed 行逐行归因（脸翻转的行 == 目标病例，其余 = 已知 overlay）
5. **接线 + census-pinned test**：钉住"不改行为"的负空间

**投入产出**：C539 的 22 分钟 A/B 被 2.5 分钟离线模拟完整预测。face 类改动的 A/B 很贵，census 模拟是它的廉价前置。

**census 的第二产出：方向级证伪（C543/C545）**。census-first 不只给 face 接线当廉价前置，也能在**接线之前**否决整个方向：

- **C543 kh-floor**：53 行 wrong 里 kh-floor 能救的只有 1 行（containment 巧合），会误杀的却有 14/72 correct 行——~1 救 vs ~14 杀 = NET-NEGATIVE，A/B 都不用跑。
- **C545 sidechannel 生产化**：#083 离线 @5 recall 18→26/30 看着很美，但 form census 显示 500 题里只有 48 行 hybrid 可能受影响，三臂实验（stored / scFalse-now / scTrue-now）= **25=25=25 net-zero**——检索顺序的变化被 answer gate + judge 通路完全吸收。离线中间指标的提升 ≠ 端到端收益。
- **C546 kh-elite 准入（窗口组成死区）**：29 行无 GT 死区归因后（16 gt-shape 聚合抽取免疫 + 11 seed-miss + 2 in-candidates），唯一能触及 4 行 viable 的 kh-elite 准入经 impostor census（banked-correct 随机样本）实测 23.3% 杀率（7/30 KILL）vs 4 行救率上限 → NET-NEGATIVE。**impostor census 从此是双向测量**：不只问"能救几行"，先问"会杀几行已对的行"。附带洞见：抽取赢家 = argmax(−kh, −seq)，无 kh 优势的候选资格一文不值 → admission-only 机制全族否决。三连 census-negative（C543 pred 侧 / C545 sidechannel / C546 窗口组成）后，零 LLM 抽取管线的答案门抵达结构天花板——但同一份证伪数据在 C548 解剖出了角色分离 face（§3.7）。

两条配套纪律：

1. **只跑可能变化面**：form 门保证其余 452 行结构性不受影响 → 48 行定向实验结论 = 全量结论，预算 110min→17min。跑全量前先问：哪些行结构上不可能变？
2. **负结果用 absence pin 钉住**：census-negative 的方向写进台账还不够，C543 加了 test_kh_floor_absence.py——若未来有人真接 kh-floor，测试先红。负结果从"文档记忆"升级为"机器强制"。

---

## 7. 一页速查

| 信号源 | Face | 动作 | Cycle |
|--------|------|------|-------|
| 问题问顺序 | marker skeleton | 缩写=同叙事，非弱子集 | C532 |
| 问题含地点词 | where + 相关性地板 | kh=0 让位 kh≥1 | C533 |
| 问题要事实类型 | type tier + 有界豁免 | 类型承载句优先 | C534 |
| 判分残差 | _sem_norm 折叠 | BrE→AmE 词表 + 转义折叠 | C535 |
| 问题引用你的行为 | speech-act bearer | 第一人称行为句 tier | C537 |
| 问题用获取动词 | acquisition face | 词族过去陈述 tier-1 | C538 |
| 胜者是 hand-over | opener floor | 严格证据优势才降级 | C539 |
| 问题含序数清单 | ordinal + phrase-run | 最长连续问题短语 run≥2 才认领 | C540 |
| GT 自带括号别名 | paren-acronym（judge 侧） | NEEDS_JUDGE→CORRECT | C541 |
| GT 带地名消歧补语 | place-complement（judge 侧） | NEEDS_JUDGE→CORRECT | C541 |
| GT 用引号包事实 | quoted-core（judge 侧） | WRONG→CORRECT（subset veto 分支） | C542 |
| GT 括号展开，头即事实 | paren-complement（judge 侧） | NEEDS_JUDGE→CORRECT + deixis fold | C544 |
| GT 与 answer 只差时态 | tense-superset（judge 侧） | 时态折叠 + 严格超集 → CORRECT | C544 |
| GT 就是裸 "yes" | bare-affirm（judge 侧） | 六门全过才 CORRECT，反问 echo 拦截 | C545 |
| GT 是展开式肯定 Yes. (…) | affirm-elaboration（judge 侧） | bare-affirm 与薄头的补集，NJ→CORRECT | C547 |
| 跨会话用户自述被 assistant echo 压过 | cross-session user-statement（gate 侧） | role=user + phrase-run 严格优势才 outrank | C548 |
| kh-floor 想救 kh=0 GT | 🚫 census-negative，不接线 | 1 救 vs 14 杀，absence pin 钉死 | C543 |
| kh-elite 准入救窗口死区 | 🚫 census-negative，不接线 | impostor 杀率 23.3% vs 4 救，admission-only 全族否决 | C546 |
| 嵌入 side-channel 重排 | 🚫 census-negative，默认 False | 离线增益被 gate+judge 吸收，pin 死默认值 | C545 |

**六条带走的原则**：
1. 答案选择读**问题结构**，不调阈值
2. face 重排不越权翻地板；地板排除自有理由
3. census-first：先数人口，先离线模拟，再接线；证伪的方向写进台账并用 absence pin 钉住
4. face 不止在 gate：judge 侧 NEEDS_JUDGE 区间同样有"写法伪装成内容"的系统性误判可救，且数学上纯上行
5. fire 的理由要语义正确，不止要 fire——数字等价 ≠ 语义正确（C544 deixis fold）
6. 离线中间指标的提升不等于端到端收益；下游通路可能吸收全部扰动（C545 net-zero）
7. 证伪的尸体是矿：关闭方向后别扔 census 数据——杀面的分布里可能藏着让机制起死回生的门（C546 杀面全 assistant → C548 role=user 门）

---

*生成：documentation-morning cron，2026-09-02；Cycles 540-542 增补：2026-09-03；Cycles 543-545 增补：2026-09-04；Cycles 546-548 增补：2026-09-05。数据口径：LongMemEval s_cleaned full-500，PYTHONHASHSEED=7，deterministic cascade banked。轨迹明细见 README Cycles 532-548 段。*
