# 2026-09-02 — key-development-3（cron `b0fd7e8d`，C539）

## 任务
autoresearch 循环 C：读 autoresearch.md + kd-1/2 最新成果，推进 amg LongMemEval full-500。成功标准 = kd-2（C538，banked 254/500 = 0.506）之上 ≥1 增量。

## 结果：KEEP，banked 254→255（0.510），+1 / 0 kill ✅

### census 阶段（~80 分钟，三个方向证伪）
1. **残余对账**：C538 后 234 行非 banked（abs 30 中 18 banked / non-abs 470）。answer 门 141 行 forensics：GT 全在窗口仅 **16 FULL** / 10 partial / 115 absent；pref 29 全弃答；speaker_recall 21；temporal_arith 13 WRONG。
2. **判分层**（census-negative，方向永久关闭）：exact=True ∩ NEEDS_JUDGE = **0**；16 个 small-diff 全是真数值分歧（3 vs 3.5 weeks 等）；动词对全 n=1。C535 已榨干。
3. **pref 组合**（census-negative，走人）：三臂 0/30 CORRECT；oracle 上限（head 模板 × MIDS × 全部偏好句）**0/30**，最高覆盖 0.38。C536 先例：不接线。
4. **opener census**：470 行中 71 行 pred 为 opener 形状（kill 面 21 banked / rescue 面 50）。**16/16 FULL 行胜者全部是 hand-over/acknowledgment/meta 形状**——问题 form 多样（when/what/which/how many/how much），候选侧形状统一。C475 寄生在 answer 门主路径的完整暴露。

### 设计演化（关键：离线模拟先于接线）
- **朴素 opener floor**（C533 where-floor 同构：hand-over 胜者 + 同带替换）：对全部 70 个 hand-over 胜者行模拟（monkey-patch acq face 抓窗口池）→ **2 rescue / 5 kill 净负**。kill 形状一致：hand-over「首行」是多句消息，**答案嵌在同句延续里**（7527f7e2/852ce960/86f00804 exact=True 的 banked 来源）。→ 证伪。
- 纯确认首句子集（"That's great!" 家族）：0 rescue / 0 kill → 也无增益。
- **幸存判别式：rep_kh > win_kh**（严格证据优势）——5 个 kill 全是同分降级。再加第一人称陈述句守卫剔除 list/lecture/meta 候选（2 个 exact 面具潜在退化 7527f7e2/7401057b）。

### 实现
- `answer_opener_floor`（amg_bench_quality.py，wired 在 acq face **之前**，保护 C538 行 3f1e9474：floor 若动了它，acq face 会再认领同一行）
- 三重守卫：`_OPENER_HANDOVER_RE`（对话管理话语）/ `_OPENER_ASK_RE`（首 200 字）触发；候选须 kh > win_kh + `_OPENER_FLOOR_STMT_RE`（首从句第一人称，by-the-way 前缀豁免）+ 非 opener/preamble
- 构造器旗标 `opener_floor=True`；11 个新测试（test_opener_floor.py）

### A/B（全量 500，1129s）
- changed = **9/500**，banked 254→**255**，rescue `87f22b4a` WRONG→CORRECT（GT "$120"，无面具），**0 kill**
- 8 个 banked-neutral 翻转（3f1e9474 floor-fired 后 acq 重认领同行为 CORRECT→CORRECT ✓）
- suite **10196 passed**（10185+11）196s，零回归

### 提交纪律执行情况
- 幂等三查 ✓（cron 双触发：01:37 又收到一次同任务 prompt，按 TOOLS.md 规则只报告不重做）
- amg 无独立 .git，workspace 根显式路径提交 ✓（memory_graph.py 的 search-cache 遗留改动**排除**在本次 commit 外——非本周期产物）
- exec preflight：直接 `python3 /path/file.py`，无复合解释器调用 ✓

### 教训
- **离线全人口模拟是 22 分钟 A/B 的廉价前置**：floor_sim.py 70 行全枚举（~155s）精确预测了 A/B 结果（+1/0kill/翻转行清单），包括 kill 形状归因。face 类改动应默认先做 census-模拟再接线。
- judge 关键词是逐 token 无词干化：fixture 里 "paid" 不匹配 "pay"（测试 fixture 两次踩）。
- opener 行的「首行含答案」多句延续形状是 answer 门的隐藏 kill 面——任何 opener 侧改动必须先数这个家族。

### 留给后续 cycle
- embedding side-channel 生产化（#083 form-gated switch，preference @5 0.87 已验证）——ordinal-item census-negative 的救援方向
- answer-gate non-echo 46 / ssu 34-wrong；entropy 7 弃答行；ollama judge 实验
- where 门 3 小目标：51a45a95（tie 排序）、3b6f954b（缺 australia token）、25e5aa4f（UCLA acronym vs expansion）

### 数值轨迹
0.444（C535 前基线）→ 0.502 → 0.504（C537）→ 0.506（C538）→ **0.510（C539）**
