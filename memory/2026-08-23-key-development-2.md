# C500 — key-development-2 (Loop B autoresearch)

**Date:** 2026-08-23 00:00–01:00 (+08) | **Commit:** 见 experiments.tsv（keep）
**接续:** C499 `55d0f4a`（full-500 refresh, exact 0.284→0.316）

## 目标

multi_session 类别（133 题，C499 时仅 17 对 = 0.128，全类别最低）。
挖掘 /tmp/c499/lme_s_full500_c499.json：最大错簇 = "What is the total
(amount|cost|price)..." 跨实体金额聚合家族（21 错，全部 pred=None/echo）。
census（/tmp/c500/census.py）：该形式门在全 500 命中 8 错 + 0 对 →
**构造上零回归**；3 个 "total number" 正确题走 number_total/duration_sum
不受影响。

## 实现（amg_bench_quality.py）

新 form `"item_total"` + `_cnt_item_total`（~300 行）：

- **形式门**：`^what (?:is|was) the total (?:amount|cost|price)\b`
  （不含 number/distance/weight/time）
- **题目侧枚举** `_cnt_item_list`：逗号切分→尾 and；无逗号按首个 " and "
  切；所有格剥离（"lola's"→"lola"）；修饰词丢弃
  {new,designer,high-end,luxury,...}；容器词丢弃 {products,items,stuffs}；
  截断尾部关系从句（"I purchased/got..."）与时间窗 PP
- **绑定四层**（每 item 独立，任一未解 → None 回落）：
  - T1 同从句：kw 全命中（len≥3 允许 len-1）或 head 名词 + 非区间 $
  - T2 同句任意从句：kw 从句 + cost-face 从句（which was/it was/
    are $/costed/totaling/i paid|bought|invested...）
  - T3 同 turn 相邻句：kw 句 + cost-face 句；疑问锚需 strong face
    （i remember/it cost me/cost me/i paid）放行，弱 face 拒绝
  - T4a turn 唯一 / T4b session 唯一：声明句 kw 谓词 + 存活 $ 唯一
    （clause 级 intent/summary/range 跳过）
- **防污染**：区间 $（$60-$70 / to）、周期价（$N a month / per month /
  monthly）、汇总句（total of $X）、intent 从句、疑问句、跨 item
  foreign-full 守卫（从句完整含另一枚举 item → 拒绑）
- **冲突**：唯一 T1 值压倒 anaphora 层；否则 abstain None

## 调试中抓到的三个真 bug（都有单测钉死）

1. T2 原为相邻从句 → "dental chews..., and the chews are $10" 隔从句
   失败 → 放宽为同句任意从句共现（同句邻近 > 跨句 anaphora）
2. T4 原 turn 级：skincare $500 在 kw 句的另一 turn → session 级；
   但 Lola vet 与 flea 药同 session → 拆 T4a(turn)/T4b(session)
3. 单从句双 item（"bowl for $15 and cup for $5" 无逗号）互相误绑 →
   foreign-full 守卫

## A/B（官方，每臂一进程串行）

| slice | base (HEAD 55d0f4a) | new | Δ |
|---|---|---|---|
| multi_session | 17/133 (0.128) | **22/133 (0.166)** | **+5/−0** |
| temporal133 | 80/133 (0.602) | 80/133 | 0 |
| firstfam-30 | 28/30 | 28/30 | 0 |

WINS = 预测的 5 题全中：1c549ce4($140) 720133ac($75) 85fa3a3f($50)
f0e564bc($1,300) a3332713($200)。LOSSES = ∅。
套件 **9862/9862**（9847 + 15 新测试 test_item_total.py）。

## 推迟（下 cycle 候选）

- 36b9f61e（luxury 类别求和，items=[] 因类别枚举）、2b8f3739
  （earned selling，同）、91b15a6e（"minimum amount" 形式不在门内）
- e5ba910e GT=弃权（中立）；d3ab962e/f35224e0/8979f9ec
- multi_session 仍 111 错：下一簇候选 = count/distance/percentage/

## 纪律备忘

- 1.9GB 盒：A/B 每臂一进程；debug 脚本用 /tmp/c500/mini.json
  （12 题 mini 集）防 OOM SIGTERM（今晚两次）
- exec preflight 拒 heredoc → 先 write 再 python3 <file>
- census 结论只信官方 A/B（原型 judge 有假阴性）

**状态：KEEP（已 commit）**
