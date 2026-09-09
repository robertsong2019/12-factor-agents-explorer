# 2026-09-10 — key-development-3 (C563)

## 结果：+2 rescue / 0 kills — banked 295 → 297（0.590 → 0.594），pp_duration 残差族双修复

cron `key-development-3`（b0fd7e8d，01:00 触发，幂等三查通过）。读 autoresearch.md + kd-1/kd-2 成果（C561: 290→294, C562: 294→295），续 push 同一 LongMemEval 基准。

## 选题

wrong-row census（205 行按 gate 分组）→ pp_duration 残差族 2 行（+2 潜力）优先。gpt4_cd90e484 + 6e984301。

## 双修复（一个问题结构家族）

**Fix 1 同句状态绑定**（gpt4_cd90e484，'3 weeks'→'2 weeks'）：
- route (b) phase-2 单关键词平局（s_ov=1）时 Python max 保首位 → 跨句 tenure（"for about a month now" 所在句无 binoculars）压过同句 acquisition（"Speaking of my new binoculars, I got them exactly three weeks ago"）
- 修法：scored tuple 加 ss 列（_pp_expr_sentence 找 expr 所在句，数其中 state keyword），phase-2 key 变 (s_ov, ss, -e_ov)；ss 平局时保 first-maximal（旧行为零变化）
- 23d → 14d = "2 weeks" = oracle "Two weeks"

**Fix 2 单位进行体头 + route (d)**（6e984301，'6 weeks'→'3 weeks'）：
- "How many weeks **have I been taking** sculpting classes when…" 从不匹配 `_PP_HEAD_RE`（只认 how long）→ 落 counting gate 吃 assistant 自己的 "6-week experience" 幻觉
- 新 `_PP_UNITS_PROG_RE`：how many + 单位 + have/had I been + **动词-ing**。进行体 -ing 判别式把完成被动同胞 gpt4_4cd9eba1（"have I been accepted"，counting banked CORRECT）挡在外面 —— ** census 早期抓到 kill 风险：宽 EXT_HEAD 匹配 25 行含多行已 banked 的 'did it take'/'had passed since'；收窄后全 500 恰 1 行**
- route (d) `_pp_session_span`：证据是同 session "today" 事实（无 ago/now expr）→ span = session 对距离，按问句自身单位渲染（03-04 − 02-11 = 21d = "3 weeks" = oracle "3"）；同 session/缺锚/years 单位 → None 诚实落穿
- judge 配套：裸数字 GT（"3"）仅在 pred 拼问句自身单位（"3 weeks"）时 credit，"3 months" 永远 False

## 验证链

- 红先 14 miniatures（test_pp_duration_faces.py）：RED 恰 4（2 个 fixture 自伤：SOLO 单行误踩 cross-exclusion、TIE 行expr句含关键词——都改成真实形状）；GREEN 14/14
- 全套件 junit：**10413 / 0F / 0E / 0 skipped**（10399+14 严丝合缝，294s）
- 定向 A/B（23 行 pp 全体 + 扩展头邻居，live 同构证据装配）：pred changes 恰 2、drift 恰 2（全 False→True）、gpt4_4cd9eba1 仍在 counting
- live-500 replay：**1162s PASS tripwire**（changes == drift == {6e984301, gpt4_cd90e484}，banked 297/500，abs_banked 18 断言过）
- staged-diff autopsy：amg_bench_quality.py 7 hunk 全对应本次编辑；memory_graph.py 外来 dirty hunk（+24）第 23 天未碰、未 staged

## 提交

- `79d0cf2` 代码（+356/−6，含新测试文件）
- `5f2109b` experiments.tsv C563 行（8 字段与近期行一致）

## 教训

- **定语收窄是零 kill 的关键**：从"扩展 how long 头"到"how many + 单位 + 进行体"，匹配面从 25 行收到 1 行。宽形式必查 census（step4 的 25 行清单直接改写了 fix 2 设计）
- **fixture 也会自伤**：两个 RED fixture 自己写成错误形状（同句/单行），判定"实现错"前先验证 fixture 是不是真实形状
- 8 字段是 experiments.tsv 近期 schema；历史 600+ 行 schema 漂移过，别拿全文件字段数做断言

## 下轮备选

- 92a0aa75（pure tenure 无 tenure line → 落 answer gate 垃圾 pred）—— 需 negative-existence abstention 设计
- e61a7584 / b9cfe692（pp 邻居）
- ollama oracle（human-blocked）
- 新高进度：297/500（0.594），距 0.600 还差 +3
