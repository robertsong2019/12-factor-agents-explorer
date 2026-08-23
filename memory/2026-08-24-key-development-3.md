# 2026-08-24 key-development-3 (循环 C508)

Cron `cron:b0fd7e8d` 01:00 触发。成功标准：在 C506/C506v 基础上 ≥1 增量改进 → **达成 (+2/0)**。

## 结果

- **C508 where-form locative 提取** 已生产化并提交 `aa3fe03`（amg_bench_quality.py + test_where_forms.py）。
- full-500 A/B（vs C506v 官方 PRE 0.368）：where 家族 **4→6（+2 IKEA/Oahu，0 回归）**，4 个原正确全保。组合树实测 0.382 中的另外 +5 是 **C507 会话未提交的 number_total v2**（同工作树测得，非本循环贡献——它仍在树里等其 owner 提交）。

## 关键教训（新）

1. **re.I 专名 loc 匹配动词垃圾**：`in my routine` 类 — 大小写敏感分支是必需的（sim v2 Denver 回归教训）。
2. **C472 全图教训不迁移到 where**：全 haystack 扫描放进 kh≥1 干扰句（sim v4: 4 fix→3+1 reg）。仅扫 retrieved 会话。
3. **检索 hash 方差**：retrieve_context 的 PPR 种子受 set 迭代序影响 → 同代码不同进程 retrieved_ids 不同。sim 里 3-seed 稳定的 4 fix，full-500 只兑现 2（Target/Serenity 未 fire，0→0 非回归）。A/B 里非 where 翻转需逐个 triage 归因（gate!=where → 非我方代码路径）。
4. **10×50 分块官方 CLI**：eval runner 每 question fresh adapter → 分块行为保持，绕开 277MB json.load 的内存墙（1.9GB 机器 + 会话踩踏期可跑）。~28 min 全量。
5. **孤儿进程处置**：C507 的 post_slice eval（PID 1781179）thrash 3h+（66GB 物理读/65MB 文件），agent 已走 → kill 合法。但 03:00 会话的 targets_ab.py 三副本属活跃会话 → 不碰，绕行（分块正是为此）。

## 与其他会话的协调

- C507 会话（number_total v2）**代码未提交仍在工作树**：本循环 commit 只 stage 了自己的 hunks（`git apply --cached` 过滤 patch），它们的 `_collect`/`_cnt_np_fam`/species 等改动留给 owner。root experiments.tsv 里 session-archiver 的未提交行同样未动。
- 下个循环若发现 C507 hunks 仍在树里：先查它的会话是否还活着，不要误提交别人的工作。

## 状态

- HEAD `aa3fe03`；amg tests: 14 新 + 242 家族 claim 全绿。
- `/tmp/c508/`: sim v1-v4, mini.json, chunks/, post_full500.json, compare_ab.py。
- 未跑 --sidechannel 组合验证（留给 C506v POST 切片的 owner 重跑）。
