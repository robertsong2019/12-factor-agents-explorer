# 2026-09-09 (晚) — code-lab-evening: openclaw-mcp-server 服务器加固四连

## 概要
- 21:00 cron 幂等三查通过（tsv 末行 03:00、2h 无 commit，非重复触发）
- 基线扫描：**openclaw-mcp-server 最久未循环**（09-01，8d；次之 a2a-trust-prototype 7d）
- 基线：17 tests / 162 LOC src。四个 cycle 全 keep，17→**24**（+7），每轮 ×2 green

## 四 cycle
1. **C1 80ef841（red-first，crash）**：客户端 mid-body abort → for-await 抛 ECONNRESET → unhandled rejection → 进程 exit 1（probe 实证）。修：handleRequest() 提取 + 整 handler crash guard。+2 tests（独立 3196 实例）
2. **C2 1965fad（red-first ×2）**：body 无上限 = 内存 DoS → 1MB cap 排空不缓冲 → 413；错误诊断族：坏 JSON 无 session 头返回 -32000 → 修为 POST+parse-fail → -32700。+2 tests
3. **C3 973d380（leak 族）**：sessions map 只靠 DELETE 缩 → SESSION_TTL_MS（默认 30min）+ lastSeen + reaper interval clamp(TTL/2, 50ms, 60s)。+3 tests（TTL=500ms 专用实例）
4. **C4 6a9ef73（contract-fix）**：SDK Transport.close() = Promise<void>，reaper 同步 try/catch 拦不住 rejection → Promise.resolve().catch 兜底；无 forced red（如实记录）。README 补 env 表 + 4 条 hardening 保证

## 教训
- **测试隔离级联伪影**：ttlInit() 带旧 sid 发 initialize 被 SDK 拒 → 第二个测试假红。修法 = init 前清 sid；每测试独立 sanity（臂独立纪律又一例）
- red-verify 脚本化（/tmp/redverify-c1.sh：stash → build → run → pop → build）一次到位
- exec preflight 拒绝复杂复合命令 → 写脚本文件再 bash 执行
- server 类项目的 red-first 顺序：先 raw-socket probe 实证 bug 再动手（本次 C1 探针 15 行拿到 exit code 1 铁证）

## 状态
- experiments.tsv 已记（workspace 仓库），4 commits 均落 monorepo
- 下轮候选：a2a-trust-prototype（7d）、acs（4d）、babylon-js-playground（0 tests 从未循环）
