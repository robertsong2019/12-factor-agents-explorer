# code-quality-checker Features

## Core (v1.0.0) ✅
- [x] ESLint 检查（委托 npx eslint --format json，无配置则跳过）
- [x] 启发式复杂度分析（if/for/while/do/switch/case/catch 计数、深缩进、长行）
- [x] 安全模式扫描（eval、innerHTML、document.write、字符串参数 setTimeout/setInterval、模板字符串插值）
- [x] 依赖检查（npm outdated 聚合）
- [x] 健康分数（0-100，各检查加权平均）
- [x] CLI（check/init 命令，console/json 输出，-o 落盘）

## 2026-08-25 晚间循环（3 真 bug 修复 + 1 虚荣配置转正）
- [x] **node_modules 跳过** — findJavaScriptFiles 原本只跳隐藏目录，任何装过依赖的项目复杂度/安全统计都被几百个 vendor 文件淹没 ✅ 2026-08-25
- [x] **bin 符号链接 CLI DOA 修复** — argv[1].endsWith('index.js') 判定在 `cqc` bin 调用时永假 → 静默空转退出 0；改 realpath 比较 ✅ 2026-08-25
- [x] **npm outdated exit-1 吞结果** — npm outdated 有过期依赖时 exit 1，exec 抛错 → catch 返回 []，outdated 永远为 0；现在从 error.stdout 打捞 JSON ✅ 2026-08-25
- [x] **`.complexityrc.json` 真正生效** — init 写出的配置（maxComplexity/ignoreFiles/fileExtensions）从未被读取（虚荣配置）；runComplexityCheck 现在加载并应用，ignoreFiles 支持简化 glob（`**`/`*`/`?`，globToRegex） ✅ 2026-08-25

## Planned
- [x] **`--fail-on` / `--min-score`** — CI 门控退出码（error|warning 两级 + 分数阈值，skipped 不触发门控，非法值 exit 1） ✅ 2026-08-25
- [ ] 安全问题附行号
- [ ] `.securityrc.json` 也接入读取（blockedPatterns/allowedPatterns）
- [ ] 模板字符串告警降噪（当前所有 `${}` 插值都报 SQL 注入风险，噪声大）
