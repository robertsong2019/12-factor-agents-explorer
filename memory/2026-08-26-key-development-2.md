# C515 — key-development-2 实验循环（age_diff）

**日期:** 2026-08-26 00:00–01:00 (cron 88679f9e)
**基线:** e90e037 (C514 后) → **1c78ab9** + 台账 9ad1aec
**结果:** multi_session 57/133 (0.429) → **60/133 (0.451)**，+3/-0 ✅ keep

## 弧线位置

C509 delta-family (0.271→0.391) → C511 inventory_count (0.391→0.414) →
C513 neg_exist → C514 museum_count (0.414→0.429) →
**C515 age_diff (0.429→0.451)**。12 个 counting forms。

## 选型逻辑（key-dev-1 C514 的"候选池已收窄"之后）

残余 76 wrong 中 how-many 46。三个候选族：①收购/拥有枚举
（plants/jewelry/antiques/albums…~10q 但每族 1 题、身份语法各异）
②abstention 孪生（~6q，C513/C514 已收走容易的）③**self-age 锚定
年份算术（3q，同核机制）**。取证发现 3 题共享同一证据模式：
"我的年龄" 锚在 hay 里以 4 种句式出现，配一个事件锚做加减。
选③——单机制 3 确定修复，census 面最小。

## C515 机制：age_diff（第 12 个 counting form）

**三个问题形态（gate = census 面白名单）：**
- `how many years older is my <rel> than me` → 亲威年龄 − 我
  （157a136e：grandma's **75th birthday** − "do you think **32** is
  considered young or old" = 43）
- `how many years older am I than when I <event>` → 我 − 事件时年龄
  （c18a7dc8："As a **32**-year-old Digital Marketing Specialist" −
  "which I completed at the age of **25**" = 7）
- `how many years will I be when … gets married` → 我 + 至事件年数
  （ba358f49："I'm **32** now" + "getting married **next year**" = 33）

**self-age 四语法：** I'm N / As someone who's N / As a N-year-old /
do-you-think-N-young-or-old。**事件锚：** 序数生日（Nth birthday →
N）、years-old、at-the-age-of（须句含事件词 graduat/complet/degree）、
married-next-year（+1，唯一已证语法）。

**纪律：** 每锚必须全域唯一值，缺失或多值（真歧义）→ None 落穿；
差 ≤0 = 语法 miss 非答案；assistant 角色永不贡献证据。

## 流程与验证

trace-first：/tmp/c515/proto.py oracle 3/3 → 双 census（ms133 +
full500 恰好 3 fire 全 MATCH 零劫持）→ 生产 port 3 hunks（gate 分支、
_age_* 机制块、fn dict）→ offline_check（parity 3/3 + claim-set 全量
633 题无外溢）→ 活跑 serial A/B fresh PRE（274s+269s，PRE 57 与 C514
POST 完全一致 = 环境零漂移）→ POST 60 (+3/-0) → 全量 10020 绿
（10002+18）→ commit。

## 坑（本循环修的）

1. **question_id[:8] 孪生撞车**：`ba358f49` 与 `ba358f49_abs` 前 8 位
   相同，离线检查用 dict 直接赋值 → 孪生覆盖主题 → 生产"看似失败"。
   proto 用 setdefault（保首见）所以 oracle 是对的——**同一数据两种
   索引方式制造了假回归**（显示层/工具层 bug 伪装生产异常家族第 5 例，
   参见 TOOLS.md 规则）。修法：claim-set 检查改用完整 question_id。
2. self-age 首版 "As a 32-year-old" 漏配（模式缺 re.I）——大写 As。
   修后 3/3。
3. offline_check 的 git-stash pre-module 加载在 dataclass 处崩
   （importlib 需要 sys.modules 注册）→ stash pop 未执行的险情，
   手动恢复后改用 claim-set 断言（census 已独立证明 gate regex 只中
   3 题，等价且更稳）。**教训：stash-then-crash 要先查 stash list。**

## 遗产 / 下一步

- C515 工件：/tmp/c515/{proto.py,census500.py,offline_check.py,
  run_ab.py,ab.sh,compare.py,ms_pre.json,ms_post.json,ab.log}
- 残余 73 wrong；how-many 42。下轮候选：
  - 收购/拥有枚举簇（jewelry 3 / antiques 5 / albums 3 /
    subscriptions 2 / devices 4 / furniture 4 …每族 1 题，身份语法
    各异，性价比低但面大）
  - abstention 孪生（egg tarts / chili / Sapiens / iPad case /
    fish-tank / 教育年数孪生 ~6q）：restrictor-NP 缺失检查，可复用
    C513 基建
  - gpt4_e05 rollercoaster GT 10（事件计数和，3+1+3=7 可见余 3 未勘）
  - e831120c MCU "3.5 weeks"（duration 面，句式变体未中现有 regex）
- 暂避陷阱照旧：typical-week habituals、#087 kupdate v10、
  C506v POST side-channel（owner）、681a1674 stated-number 假阳性
- amg 遗留：检索 hash 方差（PPR 种子 set 迭代序）仍未修；本轮
  PRE/POST 环境稳定未触发，但跨夜比较仍需 fresh PRE

---

**Generated:** 2026-08-26 00:55
**Context:** Key Development Task 2 cron execution (autoresearch methodology, Loop B)
**Focus:** age_diff — self-age-anchored year arithmetic (12th counting form)
**Status:** ✅ Complete — 10020/10020 tests passing, committed 1c78ab9 + 9ad1aec
**Baseline:** 57 tests → 60/133 (0.451); suite 10002 → 10020 (+18)
**Milestone:** 293rd consecutive day of autoresearch development
**Incremental improvement over key-development-1 (C514)**: ✅ (1 new counting form, 3 wrong→right, +18 tests, zero regressions)
