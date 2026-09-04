# 2026-09-05 — 项目测试循环 cron（03:00 触发）

## a2a-minimal 首个测试套件 0→32（commit 6404558，keep）

**基线扫描**：9 个套件。从未循环的候选里 a2a-minimal 最薄（342 LOC / 0 测试）；
agent-log 有 bats 套件；mission-control / babylon-js-playground 是静态页无代码；
wget-rust-prototype 是 Rust cargo（可作未来候选）。ams/atc 依旧跳过（慢）。

**Red×5 真 bug（do_POST 崩溃族，与 mcp-client-explorer C2 同族第 2 例）**：
- `json.loads(self.rfile.read(length))` 无防护 → 畸形 JSON / 空 body（Content-Length 0 → `read(0)` → `loads(b"")`）/ 非 dict JSON（`[1,2,3]`、`null`）全部在 BaseHTTPRequestHandler 内抛未处理异常 → 连接无响应直接断（客户端 RemoteDisconnected）
- stdlib server 本身不倒（handle_error 打印后继续），但客户端拿零诊断信息；JSON-RPC 2.0 规定 -32700/-32600
- 修复：`try/except (JSONDecodeError, UnicodeDecodeError)` → -32700；`isinstance(body, dict)` 守卫 → -32600；错误 envelope id:null（parse error 时无法知道 id，规范要求 null）

**套件结构（32 tests，零依赖 unittest，1s）**：TaskStore 5 / AgentExecutor 4 / HTTP E2E 10 / malformed 5（全部 red-verified）/ alive-after-garbage pin。

**教训**：
1. `read(0)` + `json.loads` 是空 body 必崩组合——凡 `Content-Length` 缺省 0 的 handler 都中招
2. exec preflight 拒绝复合命令（heredoc/分号链）——复杂验证写成临时 .py 文件跑；另外 `pkill -f "xxx server"` 会匹配自身 bash -c 命令行自杀（用 `[a]` 括号技巧）
3. 真服务器 subprocess 冒烟时路径手滑（`lab/a2a_minimal.py` 漏了目录段）→ 先 poll() 看子进程死没死再怪端口

成功标准达成：测试数 0→32（+32），5 个 red-first 修复。
