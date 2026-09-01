# C538 — key-development-2 (autoresearch 循环 B)

**时间**: 2026-09-02 00:00-01:00 cron (88679f9e) | **基线**: kd-1 = C537 (905ec67, banked 252/500 = 0.504)

## 目标

answer-gate 残余的 opener 寄生病理（C468 的 answer-gate 版）：消息级排序把 top 消息**首行**交给 face，多段消息首行常是 hand-over opener / 元文本，而真正的答案陈述句在中段。

## 取证（/tmp/c538）

- census（C533 forensics.json）answer gate 残 49 行，其中 6 行 pred 是 preamble：66f24dbb、8ebdbe50、6b168ec8、3f1e9474、88432d0a、a4996e51
- **66f24dbb**（"What did I buy for my sister's birthday gift?"，GT "a yellow dress"）：GT 行 msg#7 `For my sister's birthday, I got her a yellow dress and a pair of earrings` hits=2，输给 msg#3 opener `Here's a start - I've bought gifts for my sister's birthday, my mom...` hits=3
- **3f1e9474**（"Who did I have a conversation with about destiny?"，GT "Sarah"）：GT 行 `I've been thinking about my conversation with Sarah...` hits=2（floor 达标）
- probe 复现：answer gate 引用 lines[0]（top 消息首行）；C501 role_answer 只看 user 行救不了 assistant 行承载 GT 的场景；best_score 是消息级

## 实现（face）

`answer_acquisition_face`（amg_bench_quality.py ~line 3010+）：**一稘认领 acquisition/conversation 陈述句 tier face**

- 问题侧 form 检测：`what/which ... did i (buy|purchase|complete|finish|get)` → 动词家族（buy→{bought,purchased,got,received}，complete→{completed,finished,earned}，get→{got,received,bought,picked up}）；`who did i (have a) conversation/chat/talk` → conversation 家族
- 候选侧 tier-1：第一人称过去时陈述 RE（`I (got|bought|completed|...)`，排除 modal "can/should I get" 用链式 fixed-width lookbehind）+ 家族成员校验 + **hits≥2 = C501 floor 复用**（零新常数）+ opener 排除（`_RECALL_PREAMBLE_RE`，任意位置）
- 排序：tier 内 max hits（tie 取先出现）；无 tier-1 → fall-through（C488）
- 接线点：answer_extractive 尾部（session_complete_face 之后、最终 return 之前）；flag `acq_face=True`
- 依据：C534/C537 tier 形状、C475 opener 寄生、C531 问题结构非阈值

## 验证

- 单测 test_acquisition_face.py **16/16 过**：form/statement RE 单元 + buy-beats-opener + who-conversation + flag off + no-form fall-through + cross-family 排除 + opener 永不选 + floor 拦截
- smoke 6 行：66f24dbb NEEDS_JUDGE→CORRECT（pred=GT 陈述句）、3f1e9474→CORRECT（含 Sarah）；其余 4 行 face 不触发（符合预期）
- full-500 A/B（金标准 replay + frozen C530 + C533/C534/C537 overlay + C535 banked 公式）：**changed=3/500, banked 252→254 (+2), KILLS=0**
  - +2：66f24dbb、3f1e9474（均 NEEDS_JUDGE→CORRECT，与 smoke 预测完全一致）
  - 1 neutral：gpt4_2d58bcd6（exact=True，acq:finish 把 face 换成用户 "I just finished reading three fiction novels"——更直接的 bearer，两侧都 banked）
- full suite **10185 passed**（10169 + 新增 16），304s，0 失败

## 结果

**KEEP — banked 0.504→0.506**（252/500→254/500）。commit 后轨迹：0.494(C531)→0.496(C532)→0.498(C533)→0.500(C534)→0.502(C535)→0.504(C537)→**0.506(C538)**

## 教训

1. **buy→got 补体缺口**：问句用 "buy"、陈述句用 "got"（异干补词），严格家族映射会漏掉最典型的 rescue——acquisition 家族要含 got/received（词表选择非阈值拟合）
2. **8ebdbe50 未救**（acq:complete, candidate_hits=0）：GT 行不在窗口或 hits<2——face 只能救「窗口内有 floor 达标 GT 陈述句」的行，剩余是 retrieval/窗口组成问题（C525/C526 面）
3. kd-3 (01:00) 与本轮重叠：A/B 跑到 ~00:45 才完，suite 并行争核（304s vs 单独 202s）——cron 链相邻周期的 CPU 竞争可接受，幂等三查防重做是关键

## 决策

KEEP → commit amg_bench_quality.py + test_acquisition_face.py + experiments.tsv + memory 文件（**不动** pre-existing dirty 的 memory_graph.py，monorepo 显式路径提交）
