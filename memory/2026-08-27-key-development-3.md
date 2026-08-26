# 2026-08-27 key-development-3 (C519): proper-noun neg_exist 误杀取证修复

## 接力点

C517 full-500 0.444（222/500）→ C518 abs-form gates 0.448（224/500，50c4406）。
本会话避开 key-dev-2 的 abs/age_diff 方向，选 C513/C516 自家 neg_exist 假阳性长尾。

## 洞察：C513 的 proper-noun gate 从未被 census

C516 给 common-noun 版做了 v1→v6 census（170→6 fires），但 C513 的
`negative_existence`（proper-noun，pipeline 910 行，早于 object-form 检查）
fire 面从未审计。C517 报告误弃权归因显示 4 题误杀全部来自它。

## 全量 census（ijson 流式，before 基线）

proper-noun fires = **9**：
- 4 误杀（abstained 且 answer_session_hit）：25e5aa4f（Bachelor）、
  2318644b（Hawaii）、bf659f65（EPs）、488d3006（Aragón）
- 4 正确 ABS-GT 弃权：edced276_abs（Seattle）、gpt4_70e84552_abs（Peter）、
  982b5123_abs（Sacramento）、gpt4_c27434e8_abs（Porsche）
- 1 wrong→wrong：0edc2aef（Miami，pref gate 反正挡住）

## 四个根因 → 三层修复

1. **Unicode 截断**（488d3006，普适 bug）：`[A-Za-z]` token 类在 ó 处截断，
   'Aragón'→'Arag'，`\barag\b` 匹配不上 'aragón'（ó 是 word char）。语料明明
   提到 6 次。修复：`_neg_exist_fold`（NFKD 去组合符）**两侧**折叠——
   问题侧必须在 tokenize **之前** fold（先 tokenize 后 fold 治不了 'Arag'）。
   纯加宽匹配关系：fires 只减不增。
2. **学位类别词**（25e5aa4f）：'Bachelor' 是属性词不是实体，语料用
   "background in CS from UCLA" 转述。→ stop 表 +Master/PhD/MBA 等。
3. **媒体复数**（bf659f65）："albums or EPs" 语料只有单数 'EP'。
   → stop 表 +CDs/LPs/DVDs。
4. **地理下位词**（2318644b）：州名缺席、语料全说 Maui。→ 保守
   `_NEG_EXIST_GEO_SUB` 映射（hawaii→maui/honolulu/oahu/...），每条必须
   由真实 misfire 证明存在合理性。

common_noun_missing 的 haystack 侧同步 fold（同样只减不增）。

## 验证链

- proto parity 9/9（4 误杀停火 + 5 合法保持）
- POST 活跑 15 题切片（9 proper + 6 common fires）：
  **11 正确弃权全保持，2318644b wrong→correct（$270, delta_agg），
  3 wrong→wrong 无回归**
- 严格子集论证：fold/stop/sub 只能减 fire，census 确认 POST fires=5 ⊂
  before 9，无新 fire 可能 → 全 500 净效果 +1（预测 224→225）
- 主树落地后活跑切片与 proto **逐字节一致**
- suite 10040 全绿（与 C518 gates 共存无冲突）

## 结果（预测口径，下次 full-500 兑现）

C518 0.448 → **0.450**（+1/-0）。abstain 11.8%→11.4%（诚实弃权下降=误杀减少）。

## 遗留

- 25e5aa4f/bf659f65/488d3006 解锁后暴露 answer-face fabrications
  （where-gate / answer / speaker_recall 路径各自的转述失配）——下一个
  增量方向：这些 gate 的转述容忍（undergrad~Bachelor 之类），风险高于
  本轮，不动。
- entropy gate 6 题误杀未动（0.95 阈值经 C447/C448 sweep，动它影响全量）。
- gpt4_d12ceb0（avg age 59.6 被 entropy 杀）可作 age 锚定扩展候选。

## 工件

/tmp/c519/{census_proper.py, census_proper_before.txt, amg_post.py,
proto_parity.py, proto_parity.txt, run_post_slice.py, post_slice.txt,
run_main_slice.py, main_slice.txt}
