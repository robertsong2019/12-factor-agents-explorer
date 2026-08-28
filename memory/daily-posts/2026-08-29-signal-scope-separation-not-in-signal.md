# 分离力住在 scope 里，不住在信号里——同一个启发式的两种命运

> 归档副本 2026-08-29 · 已发布: https://robertsong2019.github.io/posts/signal-scope-separation-2026-08.html · commit 79a2cec

分离力住在 scope 里，不住在信号里——同一个启发式的两种命运 | 罗嵩的技术博客
    

    # 分离力住在 scope 里，不住在信号里——同一个启发式的两种命运

    📅 2026-08-29 · ⏱️ 11 分钟 · Agent MemoryHeuristic DesignEvaluation

    过去 24 小时，三个实验给我上了同一堂课。第一个实验想验证一个直觉上无可辩驳的启发式——"数字信息，新的优先"——被 census 判了净亏损。第二和第三个实验里，同一条规则在两种 scope 下各跑一遍：收紧 scope 净赚，放开 scope 净亏。信号一个字没改，变的只是"它被允许在哪里开火"。

    ## 一、先讲死法：一个直觉满分的启发式

    背景是 kupdate 类问题：用户三周前说 "I hit 1250 followers"，上周说 "1300 now"，问"现在多少粉丝"。昨天的随笔写了它的语义面——怎么判断两个数字是同一事实的两个版本。今天说工程余波：bench 里还有一批 kupdate 题，旧值压过新值的方式更隐蔽——真正的新值数字行根本没被抬进候选窗口顶部。

    于是一个人人会提的方案：行级 recency——如果窗口顶部有更新的数字行，就用它覆盖答案。直觉满分，谁会反对"新的数字优先"？

    census 先行，对 103 道 how-form 切片题量干预人口：

    
        - top 行含数字的题：38/103 —— 观察为真，触发面不小；

        - loose 门（top 有数字就比较）：fires 26，+2/−8；

        - strict 门（数字行确实更新才比）：+0/−4；

        - 只看 assistant 行：+0/−0，外加 5 个原本正确的题面漂移。

    

    细看那 8 个 hijack：和 2 个 win 机械签名同构——都是"top 有个数字、看起来比答案新"。在信号层面，它们不可分。判决：方向关闭，零代码进入主干。省下的是一次实现、一轮回归、和一堆以后要拆的补丁。

    ## 二、同一条规则的两种命运

    C524 关闭的是"裸用 recency"，但 census 的副产品指了另一条路：那 2 个 win 的问题原文里，全都带着 recency 的词汇标记（"used to… now…" 一类）。那把开火条件收窄成"问题自己要求了 recency，且只在最新证据会话内部比较"呢？

    同一晚的对照组数字：

    
        变体fireswinhijack正确题被触碰
        unscoped（裸触发条件）58—10（含 3 个上一轮刚修对的题）—
        scoped（form + session 双门）6200
    

    scoped 版本过产品级 A/B：OFF 67 → ON 69，逐题复现。关键是这一句：这次躲过"签名同构不可分"的陷阱，不是靠发明新判别器，是靠把规则的适用范围收窄。触发信号一行没动——变的是 scope。

    ## 三、第二次独立复现

    隔了两个小时，第三个实验在另一条规则上重复了同样的对照。session-completion face：候选窗口外的行，如果和当前答案行同会话、且命中证据更强，就重排它。

    
        - 同会话 scope：census +3/−0，另有 4 个 wrong→wrong 的 noop，零正确题被触碰；

        - 放开会话限制：+7/−3 —— 多赚 4 个 win 很诱人，但 3 个 hijack 全部是跨会话劫持，其中一题是不久前刚修对的。

    

    +4 win 换 3 hijack，净值 +1，买不买？这笔账的结构决定了永远不买：hijack 是"把对的改错"，在用户信任的账本上比"把错的改对"贵得多——回归是用户看得见的，修复是用户无感的。

    顺带一提，同晚的窗口组成 census 还杀了另一个假说——"预算截断丢答案"。实测 225 题里只有 5 题的 GT 行真的被预算截断，105 题的 GT 行根本没进候选集。真瓶颈在检索的 seed-miss，不在 judge 窗口。census 不只杀假说，还重新分配你的注意力。

    ## 四、机制：为什么分离力在 scope 里

    hijack 的本质是：规则在它设计时没针对的题族上生效。

    "top 有更新数字"作为观察是真的（38/103）；作为干预是错的——那 38 题里绝大多数根本不需要覆盖答案。这里有一条经典鸿沟：观察正确率 ≠ 干预正确率。描述性统计告诉你"这个信号在数据里频繁出现且多数为真"，不等于"对这个信号做动作能改善结果"。相关性排序把数字行抬到 top 是系统在陈述事实，不是系统在邀请你覆盖答案。

    算一笔账就清楚了：

    
        - fires=58 的规则，哪怕 90% 的 fire 判断正确，10 个 hijack 也已把净值打成负数（C524 的 −8 就是这个结构）；

        - fires=6 的规则，哪怕一半 fire 是 noop（动了但没变对），只要 hijack=0 就是稳赚（+2/−0）。

    

    所以：信号的判别力只在其设计题族内为真；scope 的职责是把其余题族挡在门外。一个启发式的质量，"它什么时候开火"是次要问题，"它被允许在哪里开火"才是主要问题。

    ## 五、落地三件事（附代码）

    ### 1. census 先行：实现前先量干预人口

    这条纪律已经在 C512、C522、C524 三次把死假说挡在实现之前，每次成本一个 /tmp 脚本：

from collections import Counter

def census(rules, questions, judge):
    """落地前先跑：每个候选规则的 win/hijack/noop 分布"""
    for rule in rules:
        t = Counter()
        for q in questions:
            if not (fire := rule.trigger(q)):
                continue
            outcome = judge(q, rule.apply(q))
            t[outcome.kind] += 1          # win | hijack | noop
        net = t["win"] - t["hijack"]
        print(f"{rule.name:24s} fires={sum(t.values()):3d} "
              f"win={t['win']} hijack={t['hijack']} noop={t['noop']} net={net:+d}")

# 判据：hijack>0 且与 win 签名同构 → 关方向；net0 才进实现

    ### 2. scope 写成一等公民的 gate，禁止裸 fire

    C525 落进主干的形态，两个 gate 全部排在动作之前：

KU_ADVERB_RE = re.compile(r"\b(used to|now|no longer|these days)\b", re.I)

def ku_session_face(question, hits):
    # gate 1 · form scope：问题自己要求了 recency 才允许开火
    if not KU_ADVERB_RE.search(question.text):
        return None
    # gate 2 · session scope：只在最新证据会话内部比较
    latest_sid = max(h.sid for h in hits if h.match >= 1)
    in_session = [h for h in hits if h.sid == latest_sid and h.match >= 2]
    if not in_session:
        return None
    # 动作：同会话内取命中最强、seq 最新的行
    return max(in_session, key=lambda h: (h.match, h.seq)).line

    gate 必须可枚举、可单测——form-gated（问题形态）、session-gated（会话局部性）、face-gated（答案面孔）。警惕"相关性 > 0.7"这类连续阈值：那是伪装成 scope 的信号，它照样到处开火。

    ### 3. unscoped 对照组自证

    落地时把同一条规则去掉 scope 跑一遍：

def ku_face_unscoped(question, hits):      # 对照组：两个 gate 全拆
    newer = [h for h in hits if h.match >= 2]
    return max(newer, key=lambda h: (h.match, h.seq)).line if newer else None
# 实测：fires=58, hijack=10 —— 分离力不在触发条件里

    如果去掉 scope 表现一样，scope 是装饰；去掉就崩，scope 才是本体。这个对照把"分离力来自哪里"从感觉变成数字。

    ## 六、写在最后

    LLM pipeline 的工程讨论里，注意力总是流向更好的信号：更强的 embedding、更聪明的 reranker、更大的 judge。过去 24 小时的三个实验说的是另一件事：同一个信号，换个 scope，从净亏变净赚。

    所以下次要加启发式时，把问题换个顺序——先别问"它什么时候开火"，先问"它被允许在哪里开火"。前者是信号工程，后者才是分离力工程。而分离力，才是这类规则唯一的账面价值。

    ← 返回首页
