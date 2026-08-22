# Error Patterns

### 2026-07-06 Duplicate class name silently shadowing tests (Occurrence: 1)
- **场景:** test_memory_graph.py had two `class TestBiTemporalValidity` definitions
- **错误:** 88 test methods in the first class never ran — Python class shadowing is silent
- **根因:** No linting check for duplicate class names; copy-paste of class header without renaming
- **修正:** Renamed first instance to `TestAdaptiveRetrieval`
- **出现次数:** 1
- **Prevention:** Add to pre-commit hook: `grep -c "^class TestBiTemporalValidity" test_*.py` uniqueness check

### 2026-07-07 Phantom commits — entire evening's work lost (Occurrence: 1, ESCALATED)
- **场景:** Code lab + evening cron (21:00-22:25) committed 6 APIs claiming +63 tests (1975→2038)
- **错误:** Commits modified test files but NOT memory_graph.py. Test classes were shadowed, so pytest reported inflated counts. Key-dev-1 (23:00) discovered source unchanged at 1975.
- **根因:** No verification that source files were actually modified in commit. TDD assumes tests reflect real code — shadowed classes break this assumption.
- **修正:** Key-dev-1 started fresh from real baseline 1975. 6 APIs need reimplementation.
- **出现次数:** 1 (但影响 6 个 API + 整晚工作)
- **Lost APIs:** Memory Maturation (sigmoid activation), RecurrenceDetector, ConsolidationRouter (FAST/SMART), Recall with Activation, confidence_score, forgetting_curve
- **Prevention:** 
  1. Pre-commit: verify `git diff --name-only` includes source file (not just test file)
  2. Post-test: `pytest --co -q | tail -1` vs claimed count in commit message
  3. Consider: `grep -c "^class Test" test_*.py` vs actual pytest collection count

### [2026-08-15] 多副本项目打包了过期代码
- **场景:** amg PyPI 打包研究（Research #066），需对 memory_graph.py 构建 wheel
- **错误:** 直接对 `code-lab/agent-memory-graph`（08-10/C424 过期副本）构建；冒烟时 `extract_from_text(mode=...)` 签名对不上才暴露。真身在 `projects/agent-memory-graph`（08-15/C440，54k 行）
- **根因:** workspace 有三处同名项目目录，未先按 mtime/内容认主就动手
- **修正:** `find -name <file> -printf "%T@ %p\n" | sort -rn` 认主后重建；两副本 API 面已漂移（类导出、chunk_text 位置）
- **出现次数:** 1（关联既有教训: 2026-08-13 GitHub 周报文档源目录误判）

### [2026-08-15] 大文件类边界盲插（"选仓先验真身"家族变体）
- **场景:** amg Cycle 446，向 55k 行 memory_graph.py 的 MemoryGraph 类插入 telemetry 方法
- **错误:** 锚点选文件尾部 is_healthy 之后插入，但 is_healthy 属于 FastAppendQueue 类。`grep "class.*Graph"` 只匹配含 "Graph" 的类名，漏掉 TemporalEntropyTracker/FastAppendQueue
- **根因:** 假设"文件尾=目标类尾"；grep 模式过窄（只搜 Graph 类名）
- **修正:** git restore 回退；`grep -n "^class "` 列全类边界后插到 graphrag_coverage_report（MemoryGraph 真正末方法）之后
- **出现次数:** 1（同家族: 选仓先验真身 ×N，nano-agent 嵌套 git ×1）

### 2026-08-18 git checkout 在 workspace-monorepo 下销毁未提交跨-cycle 代码
- **场景:** amg C469 revert（`git checkout -- amg_bench_quality.py`）
- **错误:** 项目目录 /projects/agent-memory-graph 无独立 .git，toplevel=workspace 根；C468 改动未提交 → checkout 直接恢复到 C467 提交态，C468 实现全丢（test 文件幸存因之前被误暂存进 0865b03）
- **根因:** 误以为项目=独立仓库；revert 前未确认 git 上下文与未提交内容；跨 cycle 依赖工作树存续
- **修正:** 从昨晚 cron 会话 transcript jsonl 提取 edit 工具 arguments 里的 12 块 oldText/newText payload，回放到 C467 态文件，19/19 测试复活
- **出现次数:** 1
- **永久规则:** amg 每个 cycle keep 时必须同命令 `git add <具体文件> && git commit`；任何 revert/checkout 前先 `git status` 确认目标文件没有跨 cycle 未提交改动；会话 transcript jsonl 是最后救援线（edit/write 工具调用的 arguments 含完整代码）

### [2026-08-20] regex 大小写类（第 2 次）
- **场景:** order_proto v2 sport 名词 alternation 小写 `triathlon` 不匹配大写 `Triathlon`
- **错误:** regex alternation 默认大小写敏感，语料大小写混合
- **根因:** 未加 re.I 或显式 [Tt] 类
- **修正:** 名词 alternation 写 [Gg]ame|[Tt]ournament 形式
- **出现次数:** 2

### [2026-08-20] kw-子集合并过合并（新）
- **场景:** "Museum of History" {museum,history} ⊆ "Natural History Museum" {natural,history,museum} 被吞并
- **错误:** 用关键词集合包含做实体合并，专名短语不是词袋
- **根因:** 集合语义 ≠ 标签语义
- **修正:** 子串包含（大小写不敏感、剥所有格/动词前缀后）
- **出现次数:** 1

### [2026-08-20] 子句粒度假设（新）
- **场景:** 同一行混 planning 子句（"next game"）与证据子句（NFL playoffs）；Alex 的 "who graduated" 在逗号后关系从句
- **错误:** 行级统一判 planning/fresh——NFL 被误杀（planning 同行）、Alex 被误杀（eventive 在相邻子句）
- **根因:** "today" 是话语级时间戳但 planning 是子句级意图，粒度不同
- **修正:** fresh 行级判 + planning/eventive 子句级判 + 关系子句窗口 [c, c+next]
- **出现次数:** 1

### [2026-08-22] tie-break 字母序伪影（基准评测）
- **场景：** Research #083 嵌入原型第一跑，turn 字典被展开成垃圾文本致所有嵌入相同
- **错误：** sorted(key=(-score, sid)) 全同分时退化为 sid 字典序排序；LME 的 answer_* sid 恰好字母序靠前 → 伪造 12/30 @1 命中率
- **根因：** 隐藏第二键（tie-break）在"分数全同"时成为唯一排序器；数据集 id 命名前缀与字母序相关
- **修正：** 修 as_text 后重跑；语义真实性抽查 3 题确认
- **出现次数：** 1
- **规律：** 好得可疑的数字先查 tie-break；每臂独立 sanity 基线（词法臂 0/86 反常）是最好的伪影检测器
