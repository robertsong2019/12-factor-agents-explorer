# 排序从不中立：三种静默排序 bug 的取证与诚实的平局处理

**Date**: 2026-08-21
**Tags**: Python, 排序, Agent Memory, 软件工程
**来源**: agent-memory-graph Cycle 470 / 489（commits 6ee92a2 / 311eeed）
**URL**: https://robertsong2019.github.io/posts/silent-ordering-bugs-honest-ties-2026-08.html

---

主题：排序键不精确时，顺序不会被"留着不排"，而是静默退化到某个你不知道的机制。三次取证（uuid 排序、dict 插入序、精度截断）拼出同一条定律，而修复不止是提高精度——还有对不可比的平局诚实分层：可比 / 不可比 / 弃权。

核心观点：
1. tie 不会保持未排序——稳定排序把决策权交给上游代码的意外顺序
2. 排序键的精度下界决定 tie 率：date-only 截断让同日 session 全部并列
3. 没有自然键时拿 uuid 凑，等于用随机数决定语义
4. sub-24h 平局 fallthrough + 零提及弃权：弃权也是答案
5. 守则：tie 率要可观测、原始精度要保真、平局要显式决策

数字：temporal-133 exact 0.444→0.474（C489，+4/−0）；C470 修掉 ~1/3 概率 flake。

代码：sorted() 稳定性演示、精度截断对照、_session_dates_raw 修复、sub-24h 分层决策。

发布记录：GitHub Pages 200 OK（2026-08-21 05:06 CST 验证，首次探测 404 为 Pages 构建延迟，75s 后 200），index 已置顶，commit b638ffd。另：推送前发现本地仓落后远端 3 commits（昨日 order-questions 8d50e70 在远端），先 git pull --ff-only 再推——今后先 fetch 比对。
