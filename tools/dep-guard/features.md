# dep-guard 功能清单

> 依赖健康扫描器（Node.js / Python）· bash · 336 行 · v1.0.0

## 状态总览

- 测试：0 → **58**（2026-08-19，hermetic：stub npm/pip + 临时 fixture，58/58 × 3 稳定）
- 修复：6 个真 bug（管道子 shell / 函数外 local / 算术零崩溃 / 玄学引号嵌套 / json 裸字 / append_lines 假值传播）

## 功能点

### 核心
- [x] F1 项目类型检测（node: package.json；python: requirements.txt/pyproject.toml/Pipfile）
- [x] F2 漏洞扫描（npm audit --json / pip-audit）severity 分级
- [x] F3 过期依赖（npm outdated / pip list --outdated），major/minor 分类
- [x] F4 健康分：high/critical -15、low/moderate -5、major -5、minor -2、无锁文件 -5，下限 0 上限 100
- [x] F5 输出格式：text（默认）/ json / markdown
- [x] F6 --security-only（跳过过期检查）
- [x] F7 --min-score N CI 门禁（低于阈值 exit 1）
- [x] F8 --fail-on {none,vuln,major,outdated} 细粒度 CI 门禁（2026-08-19 新增）
- [x] F9 --format csv（机器可读行式输出，2026-08-19 新增）
- [x] F10 json 输出含 details 明细数组（vulnerabilities/outdated，2026-08-19 新增）
- [x] F11 --ignore A,B,C 排除故意 pin 的包（2026-08-19 C480 第二循环新增）

## 已修复 bug（2026-08-19，C480）

| # | bug | 影响 |
|---|-----|------|
| 1 | `python3 \| while read; do ARR+=(); done` 管道子 shell | 全部扫描结果丢失，分数恒为 100 —— 工具核心功能形同虚设 |
| 2 | text 输出里 `local total_out`（函数外） | set -e 下非 --security-only 的 text 输出直接崩溃 |
| 3 | `(( SCORE -= X ))` 结果恰为 0 时返回状态 1 | set -e 崩溃（如 20 个 major 过期 = 100-100=0） |
| 4 | `"${ARR[@+"${ARR[@]}"}"}"` 玄学嵌套（含 `[@]+`/`[@+` 两种变体） | 在 `$(...)` 上下文直接语法错误；文件从未被 commit、从未跑通过 |
| 5 | json 输出内嵌 `$( $HAS_LOCKFILE && echo true \|\| echo false )` 展开成 bash 裸字 | Python NameError: 'false'，json 格式从未可用 |
| 6 | 新 append_lines 的 `[[ -n ]] && append` 假值传播 | 空解析结果时 while 返回 1 → set -e 杀脚本（新代码 bug，被测试当场抓住） |

## 已知问题 / 未做

- README 权重表（40/30/20/10）与实现（逐项扣分）不一致 → 已在 C480 第二循环修正为逐项扣分表
- text 输出框宽对齐在长项目名下会歪（printf 负宽度）——纯外观
- pip-audit / pip 分支已有 hermetic stub 通道，但 python fixture 测试仅覆盖类型检测
- `vuln_count`（high/critical 数）曾为死代码，已随 F1 修复移除
