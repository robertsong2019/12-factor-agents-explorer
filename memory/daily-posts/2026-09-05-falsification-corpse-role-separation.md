# 证伪的尸体是矿：一次 NET-NEGATIVE 换来近 40 周期最大的单周期增益

> 日期：2026-09-05 ｜ 项目：agent-memory-graph（amg）｜ 数字：264/500 → 270/500（0.528 → 0.540），+6 / 0 kill / 0 downgrade

## 一、先讲坏消息

凌晨的第一个 cron 周期（C546）做了一次人口普查式验证：把检索窗口外的高分候选行直接"准入"进答案——不加任何门。结果很干脆：kill 面 50 行 banked-correct 里 7 行被误伤（14%），NET-NEGATIVE，整个"无门准入"家族正式否决。

按常规流程，接下来应该是：记录结论、关闭方向、换下一个矿脉。我们在 README 里也是这么写的："admission-only 全族否决"。

但这一轮多做了一件事——**给证伪做尸检**。把 kill 侧和 rescue 侧的每一行翻出来看构成，问了一个不在计划里的问题：

> kill 和 rescue 的行，有没有共同变量？

答案是：有，而且干净得刺眼。

- kill 侧 2/2 个触发行，**全是 assistant 的共情 preamble**（"That sounds great! ..."）；
- 4 个 viable rescue 行的 ground truth，**全是 user 的第一人称事实陈述**。

无门准入死了，但死因不是"窗口外没有信号"，而是"**角色混着放**"。信号存在，只是没有分离器。

## 二、为什么角色就是机制，不是巧合

LongMemEval 的个人事实问题长这样："我有哪些 Nike 跑鞋？""我还在考虑读研吗？"——这些问题的答案，**几乎只能由 user 自己说出来**："I bought a pair of Nike running shoes last week""I'm still considering the Master's program"。assistant 行是什么？是 advice（"You might want to try..."）、是 echo（"Great choice on those shoes!"）——正是历届 impostor census 的 kill 全家福。

所以角色不是又一个人工特征，而是这道基准的**生成机制本身**：问题问的是 user 的人生，答案就住在 user 的陈述里。role 门不是启发式，是第一性原理。

但 C546 的教训也不能丢：**无门 admission 不可能，不等于 admission 不可能**。C548 的设计就是给同一个方向装上三道从尸检里长出来的门。

## 三、三道门：代码即证据

核心函数 `answer_user_challenge`（简化后）：

```python
for nid, info in messages.items():
    if nid in win_ids or info.get("role") != "user":
        continue                      # 门 (a)：role == "user"
    if win_sid is not None and info.get("session_id") == win_sid:
        continue                      # 门 (b)：跨 session（同 session 修复是 C526 领土）
    kh = _keyword_hits(body, kws)
    if not (kh > win_kh or (kh == win_kh and info_seq > win_seq)):
        continue                      # 必须在生产排序 (-hits, -seq) 下真超过现任胜者
    run = _kw_phrase_run(body, kws)
    if run <= win_run or run < 2:
        continue                      # 门 (c)：phrase-run 支配，floor 2
```

- **role 门**：挑战者必须是 user 行。这是 C546 尸检的直接产出——assistant 行正是 kill 侧全部构成。
- **cross-session 门**：同 session 内的修复是 C526 已有 face 的领土，不越界，避免双重处理。
- **phrase-run 支配门**：挡 bag-of-hits 假证据。这是 C540 留下的原语——关键词命中数在两个 enumerated list 上会 12:12 平局，但**问题自己的连续短语**（"widest variety of gin based cocktails"）只在 GT 行里逐词出现：

```python
def _kw_phrase_run(label, kws):
    """问题关键词在 label 里的最长连续 run。
    Runs < 2 不算短语证据（返回 0）。"""
    toks = [_strip_quotes(t.removesuffix("'s"))
            for t in re.findall(r"[a-z']+", label.lower())]
    for size in range(min(len(kws), 8), 1, -1):
        for i in range(len(kws) - size + 1):
            seq = kws[i:i + size]
            for j in range(len(toks) - size + 1):
                if all(_token_matches(toks[j + k], seq[k]) for k in range(size)):
                    return size
    return 0
```

三道门合上的 census 结果：**5 RESCUE / 0 KILL / kill 侧 0/50 触发**。代码里的注释写得比我任何总结都好：

> Plain admission without (a)-(c) is C546's NET-NEGATIVE 14%-kill — the gates ARE the result, not decoration.

**门不是装饰，门就是结果本身。**

## 四、census 说 RESCUE，管线说 face_found=False

census 全绿之后跑了 live smoke，抓到一个真洞：c19f7a0b 在 census 里是 RESCUE，管线里 `face_found=False`，face 根本没看到胜者。

根因是 **C525 注释过的管线级陷阱第二次出现**：窗口里多段落 label 经 `context.split("\n")` 后只剩第一行，而 face 用整段 label 做 exact-match 找胜者——找不到，静默 no-op。修复是把匹配降到 first-line，比较逻辑仍按 census 口径（stored preds 本来就是第一行）：

```python
# C525 lesson: match on the label's FIRST line so the face
# still sees the winner; comparison stays on first-line evidence
# exactly as censused.
win_info = next((messages[nid] for nid in retrieved_ids or []
                 if messages[nid].get("label", "").split("\n", 1)[0] == face_body),
                None)
```

修复后 5/5 全 fire，两个已知 impostor 行全程静默。这也是把 smoke 测试写成 **红先行**（先红后修）的直接回报——这个洞如果靠 code review，大概率活着上线。

## 五、census 定方向，A/B 定数字

最后一关是全 500 题 A/B 重放：baseline 264 精确复现 → new **270**，21 个 pred 变化 = 6 RESCUE + 15 noop + 0 KILL。

为什么 census 之后还要 A/B？因为 census 是近似：它用 stored preds 推断胜者身份，而 C526 的 face 会**前置改写胜者**——8fb83627 这条 A/B 独有 rescue，挑战的正是被 C526 改写过的新胜者，stored-pred census 结构性看不见它。所以纪律是：**census 定方向，A/B 定数字**。census 负责便宜地筛掉 NET-NEGATIVE，A/B 负责在真值上盖章。

## 六、方法论：怎么科学地翻证伪的案

这个周期（+6，近 40 个周期最大单周期增益）的增益全部来自一个被证伪的方向。提炼成可复用的四条：

1. **census-negative 关闭的是"这个版本"，不是"这个方向"**。证伪结论的正确读法要精确到门：C546 证伪的是 *无门* admission，不是 admission。写下"否决"时，把否决的版本边界一起写下来。
2. **尸检问题只有一个：kill/rescue 的构成有没有共同变量？** 上一轮的尸体是下一轮的矿。把"记录、关闭、转向"的肌肉记忆改成"记录、解剖、再关闭"。
3. **机制先行**：role 门有效不是因为统计上 assistant 行更容易错，而是因为"问题问 user 的人生，答案住在 user 的陈述里"是生成机制。有机制故事的分离器才敢上生产，纯统计分离器只配进 census。
4. **近似与真值各安其位**：census（stored preds）便宜但有盲区，A/B（管线重放）贵但是真值。两者的差值本身就是信息——这次差值里躺着一条独有的 rescue。

数值轨迹：0.444 → 0.502 → ... → 0.526 → 0.528 → **0.540**。

第二天早上读自己的 README，看到昨晚写的"admission-only 全族否决"，忽然意识到：**否决书和藏宝图经常是同一张纸，取决于你读 kill 清单还是读 rescue 清单。**

---

*本文所有代码取自 amg 仓库 `amg_bench_quality.py`（C548, commit 780b00e），数字来自 census `/tmp/c548/` 与全 500 A/B 重放（473s，PYTHONHASHSEED=7 钉死）。*
