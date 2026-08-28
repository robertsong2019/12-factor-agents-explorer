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

### [2026-08-24] append-only 台账被 trivial 会话整文件覆写（607→2 行）
- **场景:** KO 例行核查发现 amg experiments.tsv 只剩 8 行
- **错误:** 08-23 19:04 "C501 删除demo函数" 会话（6ef39db）用自己的 2 行新文件整文件覆写了 607 行实验台账（Cycle 1 2026-05-12 → C501/e703ddd 全史），而非追加。同晚 21:27 会话又用 stale base 编辑 MEMORY.md 冲掉 02:00 KO 的表格数字/insights #250-#251/日期
- **根因:** ①琐碎自动化会话对共享台账做写-整-文件而非 append；写前无行数校验 ②长文件并发编辑未先重读目标区域（08-18 checkout 事故同族的第三案）
- **修正:** git show 6ef39db^ 恢复 + 7 行重放（20071f7）；MEMORY 冲掉内容全部补回；insight #252 固化规则
- **出现次数:** 1（同类：git 拓扑事故 08-18 = 第 2 案同根因家族）

### [2026-08-25] 比率分母用平行常量制造假异常
- **场景:** Research #088 写时嵌入原型——A/B 一致率打印 `agree/{Q}`，Q=20 全局常量而 queries 实为 18 条
- **错误:** 输出 "18/20" 读作两臂有分歧，把位级确定性引擎当可疑对象排查三轮（同批组成性→跨实例→才到列表长度）；实际 18/18 全一致
- **根因:** 分母用了与集合平行的常量而非 len(实际集合)——显示层 bug 伪装成数据异常家族第 3 案（#083 tie-break 伪影 / 08-24 stale-base 台账 / 本次分母）
- **修正:** 所有比率/均值打印改用 len(集合)；规则升入 TOOLS.md（家族第 3 次触发永久规则）
- **出现次数:** 1（家族 3 → 已升级永久规则）

### [2026-08-26] cron 双触发（重复执行已完成的定时任务）第 4 例 → 已升级 TOOLS.md 规则
- **场景:** knowledge-organization-morning 02:00 与 02:05 双触发（前例：2026-08-22 essay 02:04/05:02、2026-08-25 essay 05:00/05:03 等，笔记记为第 3 例）
- **错误风险:** 第二次触发若盲目重做会重复发布博客/重复写文档/覆盖并发会话工作
- **根因:** cron 调度层重复投递（间隔 1-5 分钟）；任务入口无幂等检查
- **修正:** 核实产物已存在（MEMORY/HEARTBEAT 时间戳+内容、commit hash、发布状态）→ 不重做，只补增量（本轮补 AI×Neuro #22 漏记）；记录触发事件
- **出现次数:** 4（08-22 essay / 更早 ×1 / 08-25 essay / 08-26 KO）
- **Prevention:** 已按 Error Escalation Protocol 第 3+ 次升级为 TOOLS.md 永久规则（cron 幂等三查）

### [2026-08-26] ConcurrencyManager 测试假设不存在的 API（重犯）
- **场景：** agent-task-cli Round 63 waterfall 测试
- **错误：** afterEach 调 cm.destroy()，但 ConcurrencyManager 没有 destroy 方法（Round 59 已踩过并记录在 experiments.tsv）
- **根因：** 写测试时凭其他类（Cache.destroy 存在）的模式惯性外推，未查目标类实际 API
- **修正：** 删除 afterEach 调用
- **出现次数：** 2（Round 59 一次，Round 63 一次）⚠️ 第 3 次将升级为 TOOLS.md 永久规则

### [2026-08-28] node --test runner IPC corruption（环境级第 3 例 → 已升级 TOOLS.md 规则）
- **场景：** context-forge 测试循环基线，`npm test`（node --test 80 个测试文件）
- **错误：** 5 跑 2 红，file 级 `ERR_TEST_FAILURE: Unable to deserialize cloned data due to invalid or unsupported version`，stack 全在 `node:internal/test_runner/runner` 的 `FileTest.parseMessage`（父进程侧）
- **根因：** Node test runner 上游 IPC 竞态 bug（nodejs/node#44526 家族），多子进程套件偶发消息帧损坏；已排除 OOM（dmesg 的 kill 是 76 天前旧事件）
- **修正：** 不在项目层修（不可修）。重跑 2 次定性为 flake 再继续工作
- **出现次数：** 3（8/18 afm、8/21 afm、8/28 context-forge）→ Prevention 已升 TOOLS.md 永久规则

### [2026-08-28] 重复实现的 bug 修复漏网（prompt-mgr render 反斜杠，家族再犯）
- **场景：** prompt-mgr morning 测试循环，红验证 `--vars "p=C:\Users\test"` → CLI exit 1（re.error bad-escape）
- **错误：** `utils.substitute_variables()` 把值当 re.sub replacement 字符串；同款 bug 在 models.Template.render() 已于 08-17（b21d0ee）修掉，但 utils 重复实现漏修——而 CLI 实际走 manager→utils 路径
- **根因：** 修 bug 时只修当前报错路径，未 grep 同 pattern 的其他实现点；重复代码 = 每个实例都是独立病灶
- **修正：** utils 用同样的 lambda replacement 修复 + 3 个红验证回归测试（324→327）
- **出现次数：** 家族第 2 次明确记录（08-27 essay 系统化过该家族）；修 bug 后应 `grep -n "re.sub("` 全仓扫同 pattern

### [2026-08-29] 重复实现孪生家族第 7 例：孪生长进测试层（acs rename_key + TestRenameKey 遮蔽）
- **场景：** acs morning 测试循环，覆盖率扫描发现 rename_key 区块 100% 未覆盖，红验证 xref rename 行为
- **错误：** src 层 `rename_key` 双 def（贫血版遮蔽完整版）；tests 层 `TestRenameKey` 双 class（后定义遮蔽前定义）——`test_preserves_versions` 必 FAIL 却显示 2898 全绿
- **根因：** Python 模块级/class 内后定义静默覆盖前定义，无任何告警；套件"绿"只说明收集到的测试通过，不说明该测的都在
- **修正：** 删贫血孪生 + 四角索引重写；shadow class 改名去遮蔽；红验证 4 回归
- **出现次数：** 家族第 7 次；**新变体**：前 6 次都在实现层，这次测试层也长孪生 → 检查规则升级：测 bug 前 `grep -c "def <name>" file` 和 `grep -c "^class <Name>" tests/`，>1 先去重再修
