# 2026-08-20 key-development-3 (Cycle 483) — multi_session 答案侧：计数单位纪律

cron `b0fd7e8d-f946-4228-bb85-1baaa3502c7c`，Loop C 实验循环，基于 C482（2d3d305）。
**结果：keep（b0ac76b）— multi_session-133 exact 0.045→0.068（6→9/133，+3/0），evhit 0.962 持平，套件 9639→9647。**

## 问题定位（vs C481 参考，forensics）
multi_session 133 题 = 6 correct + 29 fired_wrong + 98 form_missed。29 个 fired_wrong 的结构性根因：
**`counting_form` 把所有 "how much/many … total" 路由到 `_cnt_total_sum`，而它只会求和 $ 金额** → hours 题答 "$4292"、fish 题答 "$545"、courses 题 "$85180"（单位失配的荒谬答案）。
duration_sum 过求和：faith 84 天 vs GT 3（"A 12-Week Study" 书名 ×7 被当日期求和）。

## 放弃的方向（第 3 次撞墙，勿再试）
how_many 实体计数（谓词门控 NP 抽取 / 句级事件计数+实体签名去重原型 prec 0.18 < 0.5 门槛）。
GT 枚举句（"I attended three weddings…"）需要谓词级语义，零 LLM 表层机制不够。C469、#075 之后第 3 次确认。

## 修复族（全部落地 amg_bench_quality.py）
1. **counting_form 单位纪律路由**：`how many hours/years/months … total` → 新 `unit_sum`；count-noun "in total" → `number_total`；`how much … total`（钱）→ `total_sum`；`how many days a/per week` → 新 `freq_days`。
2. **`_cnt_unit_sum`**：句级→**子句级** 门控（计数可藏在问句的声明式关系从句："…similar to Celeste, which took me 10 hours to complete?"——尾子句带 ？ 但以 which/that/and 开头则处理）；strip $金额/数字区间/N-Week 标题；(数字, 句内专名签名) 跨会话去重（TLOU2 30h 两会话重复提及算一次，25h normal 二周目保留）。games 140 = 70+5+30+10+25 ✓。
3. **`_cnt_total_sum` money 门**（`_cnt_money_q`）：非钱题不求和 $。
4. **species sum**（`number_total` 内，`_CNT_SPECIES_FAMS = {'fish'}` 白名单）：hyponym 家族按 per-species max 聚合，单数提及算 1 条，相邻亚种名合并。fish 17 = 10 tetra + 5 gourami + 1 pleco + 1 betta（另一缸）。
5. **`_cnt_durations_days` 标题守卫**：连字符时长后跟大写词 = 书名/课程名，排除。
6. **`_cnt_freq_days`**：distinct weekday 计数（fitness GT 4：Tue/Thu Zumba + Wed yoga + Sat weightlifting）。

## 踩坑（重要）
- **`_CNT_HYPONYM` 原有 'course': {module, class, program} 键**——species 分支首版未白名单，courses 题（GT 20）被 hyponym 误触发抢答 14，A/B 双臂 diff 抓住后加白名单修复（20 恢复）。教训：插入基于共享 dict 的新分支前先查该 dict 的既有键。
- edit 工具大块替换后**缩进易掉层级**（unit_sum 的 strip/finditer 掉出 clause 循环、hypos 未定义 NameError），症状=行为怪异/`error: True`，修复=看块结构对齐。
- 手工 trace sessions 必须 `{'turns': [...]}` shape（pipeline 的 `_counting_sessions` 吃 turns 不吃 messages）；且"旧代码 trace"前必须确认文件真的是旧代码（本循环浪费一次：备份文件名 C483 是新代码，cp 后误当旧代码跑）。
- 单臂 vs C481 参考的 diff 会混入 C482 效应；严格 A/B 需 checkout HEAD 重跑基线臂（C482 只动 temporal，本例两基线恰好都是 6/133，但流程上双臂才干净）。

## 证据/数据
- 真实路径双臂报告：`/tmp/c483/ms133_base.json`（C482 HEAD 6/133）、`/tmp/c483/ms133_post2.json`（C483 9/133）。
- oracle 冒烟（机制级，金标证据会话）：fired 24 / correct 15 / prec 0.62（>0.5 门槛 ✓）；oracle MISS 多为证据范围 artifact（oracle 只有 gold sessions，真实路径检索更全）。
- GAINS：28dc39ac games 140h（原 $250）、eeda8a6d fish 17（原 $545）、c2ac3c61 courses 5（原 $85180）。零 LOSS。
- 单测：test_counting_forms.py +8（TestCycle483UnitDiscipline：路由/去重/问句子句/守卫/频率/species/money门）。

## Next Steps（C484 候选）
1. multi_session 剩余 29 fired_wrong 中未覆盖的形式（social media 59 vs 17 过求和、Hawaii 90 vs 15——duration_sum 的传播/anchoring 语义仍偏松）。
2. `unit_sum` 扩展 driving 类：GT 15 = 用户自述三段路程，当前 19（含未成行计划）——需要 plan/factual 区分（intent 门已挡部分，"I'm planning" 命中但 "It's about X hours from NC" 未挡）。
3. freq_days 的"every other week"式非周频题（若有）。
4. preference 30 题 0.000 结构性缺口（evhit 0.567 是六类最低）——候选下一个大方向，但需先做 forensics 确认是检索侧还是答案侧。
