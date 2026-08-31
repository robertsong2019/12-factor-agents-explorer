# 2026-09-01 01:00 — key-development-3 (C535: judge residue fold, banked 0.500→0.502)

cron `key-development-3`（b0fd7e8d…，01:00 触发，Loop C）。承接 kd-2 C534（24220b1，00:00）队列 #1：判分层拼写变体折叠。幂等三查通过（无今日 kd-3 产物、无 30 分钟内提交、无在飞 eval）。

## 结论 TL;DR

- **banked 250→251（0.500→0.502）**，唯一 rescue = b759caee（C534 遗留的 NEEDS_JUDGE 行），0 kills，套件 10152→10158 全绿 181s。
- **修复（KEEP）**：`judge_semantic` 的 `_sem_norm` 尾部加两步——(1) 非 `[a-z0-9@%\s]` 字符折为词分隔符（markdown 转义 `\_\_`、引号、括号、冒号、下划线等 markup 胶水不再参与 token 同一性）；(2) `_SEM_BRE_VARIANTS` 英式→美式词形折叠表（jewellery→jewelry、colour→color、centre→center、-ise→-ize、-ogue→-og、双写辅音、grey/defence/judgement 等约 50 词）。
- **C534 记忆的低估被实测纠正**：b759caee 的真凶是**三层**——markdown 转义（`\_` vs `_`）、括号/冒号粘连（`(@...):`）、BrE/AmE 词对。C534 只看到 jewellery/jewelry。单一拼写折叠救不动（handle token 里 `\b` 不匹配 `_` 前边界），必须三层同修。

## 记账口径（本次沉淀，防止下 cycle 再踩）

官方 banked ≠ 冻结文件 `correct_llm` 计数。可复算公式：

```
banked = 18 (abs 行 correct_exact True，常量)
       + |{非 abs: (exact & semantic != WRONG) or (!exact & semantic == CORRECT)}|
```

HEAD 复算 = 18 + 225 − 3 kills + 10 rescues = 250 ✓（kills 恰为 C531 复核过的 3 个正确 kill：00ca467f/a9f6b44c/e56a43b9；rescues 含 C533/C534 两个 win）。有效预测 = 冻结 C530 叠加 /tmp/c533/ab19.json + /tmp/c534/ab48.json 的 changed 行（共 7 行：3d86fd0a/gpt4_b5700ca0/830ce83f/18dcd5a5/e8a79c70/7a8d0b71/b759caee）。

## Census → 枚举的完整证据链

1. **census v1（1-1 opcode 对齐）零命中**——太窄，漏多词块替换。教训：census 先用集合差 + 近似配对（共享前缀 + ratio≥0.75）。
2. **census v2（集合差）**：冻结 500 非 CORRECT 行中 BrE/AmE 变体对**零出现**；但暴露 9+ 行**标点粘连族**（`hugo` vs `hugo":`、`meditation'`、`pogodi!` vs `pogodi!”`）。
3. **有效人口才见 jewellery**：b759caee 的 jewelleny 只存在于 C534 新预测——判分层改动的枚举人口必须用**有效预测**（冻结 + overlay），否则量不到 win。
4. **verdict-delta 枚举**（补丁前后全 500）：1 rescue（b759caee NEEDS_JUDGE→CORRECT）/ 0 kills / 9 中性翻转（全为标点粘连行 NEEDS_JUDGE→CORRECT，exact=True 本由 LLM 救回，现语义层直判 → **省 9 次 cascade LLM 调用**，86f00804/1faac195/fea54f57/gpt4_483dd43c/gpt4_2d58bcd6/2bf43736/1b9b7252/51b23612/28bcfaac）。抽查 3 行全部合法（引号风格差异、quote 胶水 superset）。无 CORRECT→非 CORRECT 翻转、无 WRONG→NEEDS_JUDGE 塌陷，符合「双侧一致折叠保单调」的论证。

## 设计决定（反拟合纪律）

- **显式词表而非后缀规则**：our→or 类重写会污染代词 our（及 hour/sour）。词表有界、每对同词位。
- **排除 sense-split 对**：programme/program、storey/story、licence/license、practise/practice 在同一变体内指不同物，不折叠（测试钉住）。
- **分隔符化在 `[,$.]` 之后**：2,000→2000 保持（逗号不能变空格，否则 Guard-1 数字签名会误杀）。测试钉住。
- census 全量零 harmful 出现 → 全表无拟合风险；规则是词形类折叠，不是行定向补丁。

## 下 cycle 队列

1. **4c36ccef speech-act face**（惜败 5.3 分）：问题含 "you recommended" ⇒ 候选含第一人称 "I (would) recommend" 言语行为分层——原则性，需爆炸半径评估（C534 queue #2 顺延）。
2. **3249768e 序数词**：`_split_sentences` 把 "5. Absinthe:…" 拆散丢序数信息——sentence-split 序数保真 + ordinal face（C534 queue #3 顺延）。
3. **答案门侧胶水审计**：9 行标点粘连证明判分层有此病；recall/候选抽取侧（answer-gate 的 distinctive/df 地板）是否也因胶水丢候选？对 9 行跑 gate 侧探针（cheap）。
4. 遗留：answer-gate 非 echo 46 / ssu 34-wrong / c4f10528（GT 行 raw=2 无解，需跨句证据）/ ollama oracle 真 cascade A/B。

## 工件

- /tmp/c535/{census_variants.py, census_variants2.py, probe_b759.py, banked_head.py, banked_breakdown.py, snapshot_head.py, enumerate_delta.py, verdicts_head.json, verdict_delta.json, banked_head.json}
- 套件：10158 passed 181.55s（首轮即绿）
- commit：ecf74a2（代码）、本 memory + tsv 行随行提交

---

**Generated**: 2026-09-01 01:00 AM
**Context**: Key Development Task 3 cron execution (autoresearch methodology, Loop C)
**Focus**: judge-layer normalization residue fold — C534 queue #1 (spelling variants) 扩为三层修复
**Status:** ✅ Complete — banked 250→251 (0.500→0.502), +6 tests, zero regressions
**Milestone:** 294th consecutive day of autoresearch development
**Incremental improvement over key-development-2 (C534)**: ✅ (1 new rescue, 9 LLM calls avoided, +6 tests, 0 kills)
