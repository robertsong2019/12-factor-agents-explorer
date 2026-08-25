# 2026-08-26 — key-development-3 循环 C516（cron b0fd7e8d）

## 结果：keep（commit 60b2e74 + 6263cab）

**指标：ms133 0.451→0.459（60→61，+1/-0）｜abs30 0.333→0.500（10→15，+5/-0）｜套件 10039 绿**

## 做了什么

C515 下一步清单的 abstention 孪生：C513 neg_exist（专有名词）推广到**普通名词 restrictor**。

LME _abs trap 家族的机制：换掉被问对象名词（violin↔guitar、football↔baseball、iPad↔iPhone、uncle↔niece）——被问对象在全语料**完全缺席**，混淆 sibling 在场撑高检索 → answer 路径 fabricate。缺席的普通名词在第一人称对象疑问句里 = 与专有名词版同样的预设失败。

## 方法论亮点

1. **census v1→v6（170→6 fire）**：每个 stop 规则都由误报取证驱动，不是拍脑袋：
   - 动词自由转述（repotted/acquire/sold 缺席≠预设失败）→ VERB_STOP + *ed/*ing 启发式（名词例外 seed/bed/wedding）
   - 事件类名词停用——语料用具体事件名指称
   - 连字符/数字 token 跳过，语料连字符折叠匹配（homegrown↔home-grown）
   - 复数双向词干、-ies→-y、typo 容忍（len≥7 且 Levenshtein≤1）
   - 跨词性派生容忍：visit~visited（名词↔动词），修复了 test_amg_temporal_arith 回归
   - 答案类别名词：money/color/price/cost/name（"What color…"命名答案类型，语料含颜色本身）

2. **RECORD-NEGATIVE：复合词路径实现前杀死**。sibling 签名分离设想（trap 复合词与合法转述可用形容词签名区分）被证伪——"amazing restaurants"/"chocolate cake" 不可分，形容词同样出现在 trap 名词前。设计阶段枪毙，零实现成本。

3. **闸位迁移（本轮最重要的教训）**：初版把 common-noun 检查放在 C513 块后（~line 905），在专化闸（counting/pp_duration/where/recall）**之前**——单元套件抓住 3 个 fixture 回归（counting $1500 被 money 劫持、pp_duration GOOGLE_Q 被抢闸、sage-green 被 color 劫持）。修正：迁到最终 gate 判定的 answer 分支内——**fabricate 发生地**。机制故事与代码位置对齐了。500 题 census 看不见这层（LME 无此模式），**单元套件抓住了 census 抓不住的**——两层验证缺一不可。

4. **A/B 后的子集论证省了 330s 复跑**：迁移后的拦截集是旧位置的严格子集（只少拦不少拦），旧位置 A/B 零损失 → 新位置必零损失；6 题活跑终验与预测逐题吻合（5 abstain-CORRECT + 1 pref 不变 wrong→wrong）。

## 陷阱与坑

- **fixture 揭示的封闭类缺口**：should/between/amount/pages/left/previous/this/read——6+3 轮才收敛。教训：手写测试语料前先用生产函数跑一遍 question 侧 token 分类。
- perf 时序测试（test_large_flush_performance）在全负载下偶发失败，隔离通过——与改动不同子系统，非回归。
- fire_status/compare 等 exec 复杂命令仍被 preflight 拒绝，需落盘为 .py 文件直跑。

## 会话协调

memory_graph.py 有另一会话的 `_search_cache` 未提交改动（2026-08-26 00:19:40）——照 C508 纪律只 stage amg_bench_quality.py + test_neg_exist_common.py + experiments.tsv，未碰他人工作树。

## 下一步（C517 候选）

- abs30 剩余 15 错里 census 未覆盖的家族：gpt4_*_abs、时间型 _abs（C513/C516 都不 fire 的）
- pp_duration 抢闸类问题：GOOGLE_Q 的 'current'/'job' 链说明 answer-category 停用表可能还有缺口，等 census 之外的误报证据
- 5 win 分布：multi_session +1、knowledge_update +1、temporal +1、single_session_user +2——single_session_user 62/86 检查是否还有同类
