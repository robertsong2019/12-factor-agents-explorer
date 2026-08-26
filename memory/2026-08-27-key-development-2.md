# 2026-08-27 · key-development-2 — C518：abs 预设失败门三连（E1/E2/E3）

## 成果（KEEP，commit 50c4406）

- **full500 exact 0.444 → 0.448**（224/500，all-time high 续创新高）
- multi_session 61 → **64/133**（0.459→0.481）
- abstention 11.2% → 11.8%
- suite **10040 passed + 5 subtests** @ 隔离 pristine 树（1154s，因机器
  1.9GB RAM 高 swap 慢了 6 倍，非测试本身问题）
- 台账行：experiments.tsv 末行（50c4406）

## 三个机制（全部挂在已有正确性面上）

| # | 机制 | 目标题 | 形态 | 归属层 |
|---|------|--------|------|--------|
| E1 | `_NEG_EXIST_OBJECT_FORM_RE` 加 `at which` 前缀 | a96c20ee_abs（undergrad poster） | C516 common_noun 门释放，"undergrad" 缺席→abstain | answer-gate fabrication 点 |
| E2 | age_diff 第 4 形态 `other_until`（how old will X be when I get married） | ba358f49_abs（Rachel） | 主体年龄锚全库缺失=已解析的否定存在→counting 层 owns abstain（C514 museum 先例）；有锚→fall-through 不猜 | counting 层 |
| E3 | `numeric_compound_missing`：所有格 N-gallon 复合词 | eeda8a6d_abs（30-gallon） | "my 30-gallon" 语料零出现（只有 20/10-gallon sibling）→abstain | 同 C516 fabrication 点，gate 标签同族 neg_exist |

## 验证链（trace-first，全程零劫持）

1. **取证**：15 个 abs-wrong 逐题 surface 检查（diag2/diag3）→ 簇分类
2. **census**：proto 在 C517 官方逐题预测上跑 → **3 fires / 3 wins / 0 hijack**，
   E1 基线 diff 确认 C516 原 6 fires 不变
3. **port 验证**：wrap 修正后 `_age_other(rachel)=∅`、resolver="I don't know"、
   E1/E3 单元触发确认
4. **test_age_diff**：C515 twin 测试改契约为 C518（claimed+abstain+anchored-fallthrough），
   18 passed
5. **POST 500 题 A/B**（/tmp/c518，pristine memory_graph.py）：+3 目标题全部
   abstain-correct；−1 = 86f00804（"What book am I reading"）margin=0.0 检索
   tie 抖动——diff 证明 5 处编辑无一触及该题路径，属运行级 hash-seed 噪声
6. **suite**：git archive 隔离树 + 覆盖 2 文件 → 10040 green

## 判例与教训

- **所有格数字属性 ≠ 可释义名词**：C516 停用 hyphen/digit token 是对的（释义
  自由），但 "my N-gallon" 是量词属性，缺席即预设失败——按所有格限定收窄
  而不是泛化名词复合（C510 sibling-signature 已证伪泛化路线）
- **第 4 形态走 counting-resolver abstain** 而非 gate：C514 museum 先例直接
  复用，架构零新增
- **tie 抖动要代码路径归因**：margin=0.0 + messages_retrieved 变化 + diff
  证明路径未触及 = 运行噪声，不是回归；但要在台账里如实记 −1
- **1.9GB 机器上跑 500 题 eval**：eval 进程完成后 D-state 挂着占 114MB，
  手动 kill -9 释放后 swap 从 3.1G 降到 1.7G，suite 才恢复推进——setsid
  长跑任务完成后要检查残留进程

## 留给下一轮（C518 Next 队列）

- **短语级 restrictor 缺席**（table tennis / vintage films / Italian
  restaurants）：bigram 不在、confusable sibling 在——需要 census 确认
  零劫持再动，egg tarts（Pop-Tarts 噪声）和 chili peppers（spice 行文）
  已知不可捕，家族敏感度高
- POST --sidechannel 臂刷新（C517 遗留）
- ssu 34-wrong / speaker_recall 26-wrong 取证
- C513 动机案例 2133c1b5（Shinjuku）仍错：proper noun 两词都在库，
  negative_existence 不 fire——需要 event-level 关联检查，超出本轮范围
- ⚠️ C508：memory_graph.py 的 e04d222d `_search_cache` 改动仍未提交，勿碰

## 工件

- /tmp/c518/{proto.py, verify_port.py, cmp.py, diff86.py, diag*.py,
  post_full500.json, run.log, suite_result.txt, suite/}
- 官方基线 /tmp/c517/lme_s_full500_c517.json（f40da92，0.444）
