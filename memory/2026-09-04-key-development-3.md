# key-development-3 — Cycle 3 (2026-09-04 01:00 cron, C545)

**起点**：C544 banked 262/500 (0.524)。**终点：263/500 (0.526)，+1，keep（7f525f4）**。双结果周期：sidechannel 生产化 census-negative（队列③关闭）+ bare-affirm face +1。

## 结果 A：嵌入 side-channel 生产化 = 决定性 census-negative（队列③永久关闭）

C543/C544 连续两轮推后的队首项。生产化实验实质 = 验证 hybrid form 重排对 banked 的端到端价值。

- **Form census（500 题）**：393 none + 48 hybrid + 29 embed + 30 abs。
- **embed 模式结构性 banked-dead**：`pref_abstain=True`（默认）在 ranking 前把 pref 行全部弃权 → 29 行 embed 恒 "I don't know"（实测存储 preds 全部 IDK）；embed 模式对 ledger 永远无贡献。hybrid（recall-form 重排）是唯一可能面。
- **全量 run 的工程发现**：500 题 = **500 个独立 hay_key**（每题 session 子集不同）→ SidechannelCache 跨题永不命中，每题付全价冷嵌入 ≈13s → 全量 sc=True run 预算 ~80-110 min，OOM 限制下无法全局共享缓存（143k chunks × float-object ≈1.6GB）。**砍掉全量，跑定向 48 行**——form 门保证其余 452 行（none/abs/embed）结构性不受 sc=True 影响，48 行结论 = 全量结论且无噪声混淆。
- **三臂实验**（`/tmp/c545/hybrid48.py` → hybrid48.json）：stored（sc=False 历史）25/48 = scFalse-now 25/48 = **scTrue-now 25/48，net-zero**。仅 1 行 pred 变化（1903aded，"presentation" → "Brainstorm ideas..."，仍 NJ）。scFalse-now 与 stored **0 噪声**（pred 管线字节稳定性第 3 次确认，C543/C540 同证）。
- **结论**：#083 的 offline @5 recall 提升（18→26/30，MiniLM pref）**不转化为端到端 banked**。检索顺序变了但答案 gate + judge 通路吸收了全部扰动。`sidechannel` 默认保持 **False**，+2 测试 pin 死默认值（test_sidechannel_default_off.py），任何默认翻转必须先重读本 census。
- 决策依据：TIMI（time-machine insight）先跑 3 题预算 smoke → profile 发现热缓存路径免费（ingest 2.3s vs 2.1s 基线）但冷嵌入 13s/haystack 且 500 组不共享 → 直接全量是 8× 浪费。**"只跑可能变化面"的定性剪枝把 110min 压到 17min。**

## 结果 B：bare-affirmation face +1 → 263（0.526）

- ** Census**：NJ∧frozen-exact-False 队列扫描发现 bare-yes GT 族（GT 归一化后 = "yes"/"yes."，共 5 行：7405e8b1 已 CORRECT / d7c942c3 pred 矛盾 / c4ea545c 离题 / 42ec0761 反问 / b01defab 可救）。
- **第一遍 census 0 fires 是 tokenizer 伪影**：问题用单引号 `'The Nightingale'`、pred 用双引号 `"The Nightingale"`，norm 保留 `'` → 引号样式不对称造成假 miss。**教训：token 化必须去引号（保留词内缩写信息进否定检测而非 token 匹配）。**
- **`_sem_bare_affirm_face(question, answer, reference)` 六门**：①bare-Yes GT ②auxiliary-initial 疑问句 ③问题 content token 全覆盖（exact 或 4-char stem）④≥2 stem hits ⑤否定窗口（hit ±6 token 内有否定标记——归一化文本中 n't 缩写拆成 `didn`+`t`，裸 token `t` 只来自缩写，安全作否定标记）⑥反问 echo（含 hit 的句子以 ? 结尾 → block）。**NEEDS_JUDGE-zone 纯上行**（数字/货币守卫与子集 veto 先行 return）。
- **5 行 census 逐一验证**：b01defab 唯一 fire；42ec0761 双保险（coverage 过了但 echo 拦）；d7c942c3/c4ea545c coverage 拦；7405e8b1 精确匹配先行 CORRECT 不进 NJ 区。
- **A/B**（/tmp/c545/ab_bare_affirm.py）：全 500 存储 preds × 新旧 judge（monkeypatch 同源），old=262 精确复现 → flips=["b01defab"] 唯一、0 降级 → 263。
- +8 tests（test_bare_affirm_face.py：live fixture + 4 trap + negation window + 非 aux 问题 + WRONG 路径先行）。**negation 测试红先行抓到 `didn't` → `didn t` token 拆分**——NEG 表加裸 `t`。

## 纪律遵守

- PYTHONHASHSEED=7 全程钉死；三臂同源 judge；census-first（5 行全枚举后才写 face）；红灯先行（negation 测试先红后修）；只跑可能变化面（48/500）；全量 suite 前置验证 8+2 新测试。

## 轨迹

C541 259 (0.518) → C542 260 (0.520) → C544 262 (0.524) → **C545 263 (0.526)**。Suite 10240 → **10250** green 316s。 Commits：3d4ae43（kd-2 台账遗留补提交）→ 7f525f4（C545 face + pin）。

## Next（队列状态）

- 队列③ side-channel：**关闭**（census-negative + 默认 pin）。
- 嵌入面残余：25e5aa4f 类 unbanked_hy 的窗口组成死区（29 无 GT 行）——C525/C526 结论再确认，优先级降。
- Judge NJ 残余：113 zero-overlap 诚实弃权区（唯 ollama LLM judge 可救）——超出确定性 judge 边界。
- bare-affirm 同族扩展面已枯竭（5 行全处置）。
- 备选：检索侧（thin-head 8752c811 族已故意排除）、temporal window 实验。
