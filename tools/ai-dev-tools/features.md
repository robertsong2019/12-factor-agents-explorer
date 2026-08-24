# ai-dev-tools Features

> AI 开发效率工具集（aid CLI）：prompt 管理 / session 追踪 / task 模板 / analyze 扫描

## Core
- [x] prompt save/list/search/use/export/delete（真实存储，delete 修复前为假成功）✅ 2026-08-24
- [x] session start/stop/log/stats/list/export ✅ 2026-08-24（log 修复前为假成功）
- [x] task 模板引擎（8 模板，loadTemplate/generateTaskContent 已导出可测）✅ 2026-08-24
- [x] analyze 目录/文件扫描 + AI 特征/质量/安全检测 ✅ 2026-08-24

## Fixes (2026-08-24 evening cycles)
- [x] **deletePrompt 假成功修复** — 原实现打印"✓ 已删除"但从不调用存储；storage 层补 `deletePrompt(id)`（conf + 文件副本双删）✅ 2026-08-24
- [x] **logSession 假成功修复** — 原实现收集内容后什么都不存；现 append 到 `session.logs[]` 持久化 ✅ 2026-08-24
- [x] **generateTaskContent `$&` 注入修复** — 值含 `$&`/`` $` ``/`$'` 时会被解释为替换模式损坏输出；改用函数替换 ✅ 2026-08-24
- [x] **stopSession 崩溃守卫** — `--name` 指向非活动会话时 `undefined.startTime` TypeError；现友好报错 + exit 1 ✅ 2026-08-24
- [x] **stopSession 非交互模式** — 提供 `--tokens/--duration` 不再强制交互提问；`--duration` 按帮助文档以秒解析 ✅ 2026-08-24
- [x] **analyze 单文件文本输出静默修复** — 单文件结果在文本模式下什么都不打印（安全发现完全不可见）；现渲染完整分节 ✅ 2026-08-24
- [x] **安全检测计数/大小写缺口** — password/apiKey/secret 模式缺 `g` 标志（永远计数 1）且漏 camelCase `apiKey`；加 `gi` ✅ 2026-08-24
- [x] **detectAICode NaN 守卫** — 空文件/纯注释文件重复率 0/0=NaN；现返回 0 ✅ 2026-08-24
- [x] **savePrompt/saveSession 文件名路径注入** — 名称含 `/` 时 writeJson ENOENT；sanitize `[\s/\\]+` ✅ 2026-08-24
- [x] **测试密闭性** — 套件未隔离 `conf`（每次 npm test 写真实 `~/.config/ai-dev-tools/`）；现 XDG_CONFIG_HOME 指向 tmp ✅ 2026-08-24
- [x] **虚荣测试重写** — task/analyze/prompt 三套件从不导入真实模块（自建 fixture 自证）；task+analyze 重写为真实模块测试，prompt 补 delete 调用断言 ✅ 2026-08-24

## Planned
- [ ] prompt `save --file` 分支补 category/tags 默认值（现只能存"未分类"）
- [ ] `aid quick` / `aid config` / `aid info` 命令测试（bin/aid.js 其余入口无覆盖）
- [ ] searchPrompts 预览恒附加 "..." 即使内容 < 150 字符（cosmetic）
- [ ] analyze extractFunctions 不识别 class 方法与单参无括号箭头函数
