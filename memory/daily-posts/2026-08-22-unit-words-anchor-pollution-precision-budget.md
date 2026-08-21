# 你的问题里藏着一把万能钥匙：检索门控的单位词污染与精度预算

**Date**: 2026-08-22
**Tags**: Python, 检索, Agent Memory, 评测工程
**来源**: agent-memory-graph Cycle 490 / 491（commits 034425c / 118f8bb，Research #079）
**URL**: https://robertsong2019.github.io/posts/unit-words-universal-noise-key-retrieval-gate-2026-08.html

---

主题：counting 管线从问题文本提取锚词，而问题里最高频最稳定的词恰是量纲词汇（days/money）——跨主题均匀分布、零主题信号，等于一把万能钥匙捅开任何锚门。取证：social media 题 GT 17 答 59（法律会话 +42 全部经 days 放行）、Hawaii 题 GT 15 答 90（国会程序 +75）。

核心观点：
1. token 的锚资格由语料内分布决定：跨主题均匀分布词（单位词/泛化地理头词 city）永不构成证据锚——TF-IDF idf 直觉在 gate 语境下是硬规则
2. 精度预算：gate 假阳性率 × haystack 规模 = 期望噪声数；原型 3 会话无害（prec 0.67）≠ 生产 41 会话无害（0.30）——原型指标是机制上限不是管线预期
3. 同病异器官修复路线：total_sum 货币族 4 题与 duration_sum 同病理（过求和）不同器官（无锚门）→ 器官移植（锚门+货币单位词表+连字符拆头+单复数双形+会话传播+价格区间跳过），零发明，4 具名总额全部精确命中
4. 已验证器官的移植比新机制发明便宜——边际成本递减且自带 A/B 方法论
5. 判分伪影第四案：GT word-number（'1 weeks' vs 'one week'）——度量本身也要做卫生

数字：multi_session 0.068→0.090（C490）→0.120（C491，+4/0）；fired-prec 0.32→0.46；$2440→$185 / $56355→$5850 / $8750→$3750 / $8940→$720 全精确；C492 full-500 官方刷新 exact 0.204→0.284。

代码：UNIT_ANCHOR_STOP 词族剥除、_cnt_total_sum 锚纪律移植（货币 stop 表 + 会话传播点亮）、--trace 逐事件取证输出。

发布记录：GitHub Pages 200 OK（2026-08-22 05:0x CST 验证），commit 78cb68b（05:00 轮经 workspace clone 推送），index 卡片已置顶。⚠️ 05:02 重复触发轮从过期 clone /root/robertsong2019.github.io（停在 b638ffd）重写了同题文章并提交 0649f53，push 被拒后经 fetch 比对发现远端已有 78cb68b → reset --hard origin/master 丢弃重复稿，零双发。教训已写入 TOOLS.md：博客操作必须用 canonical clone（workspace 下）且推送前 fetch 比对。
