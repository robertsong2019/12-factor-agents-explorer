# 🤝 A2A Minimal

零依赖 Python 实现，演示 Google A2A（Agent-to-Agent）协议核心概念。

## 它是什么

一个~340行的单文件实现，展示了 A2A 协议的三个核心机制：

1. **Agent Card** — 能力声明（JSON 格式，描述 agent 能做什么）
2. **Task 生命周期** — `submitted → working → completed/failed` 状态机
3. **JSON-RPC 通信** — agent 之间通过 HTTP + JSON-RPC 2.0 交互

## 快速开始

```bash
# 终端 1: 启动第一个 agent
python a2a_minimal.py server --port 8001

# 终端 2: 启动第二个 agent（不同能力）
python a2a_minimal.py server --port 8002 --name "TranslatorAgent"

# 终端 3: 客户端连接
python a2a_minimal.py client --url http://localhost:8001
```

## 核心概念

### Agent Card
每个 agent 启动时声明自己的能力（skills）、支持的输入输出模式、认证方式。客户端通过 `/.well-known/agent.json` 获取。

### Task 生命周期
A2A 协议以 Task 为中心：
- 客户端发送 `tasks/send` 创建 task
- agent 处理后返回 `completed` 状态 + 结果
- 支持 `working`（进行中）、`failed`（失败）等中间状态

### JSON-RPC 2.0
所有通信走标准 JSON-RPC，方便任何语言实现客户端。

## 内置 Skills

| Skill | 说明 |
|-------|------|
| `echo` | 回显输入消息 |
| `reverse` | 反转输入文本 |

## 扩展方向

- 替换内置 skills 为真实业务逻辑（翻译、摘要、搜索）
- 添加 `streaming` 支持（SSE）
- 加入认证（API Key / OAuth）
- 连接 LLM 后端实现智能路由
- 多 agent 编排（agent A 调用 agent B 的能力）

## 测试（32 用例，零依赖 unittest）

```bash
python test_a2a_minimal.py        # 或 python -m unittest test_a2a_minimal -v
```

五个分组：**TaskStore**（5，创建/显式 id/get-missing/状态更新）、**AgentExecutor**（4，echo/reverse、artifact 索引递增、空 parts 完成、unicode 码点反转）、**HTTP E2E**（10，agent card 发现、404、message/send 往返、多轮 taskId 累积、tasks/get -32602、cancel、未知方法 -32601、card 隔离）、**畸形输入**（5）、**服务存活**（1）。

### 稳健性保证：畸形输入不崩连接

`BaseHTTPRequestHandler` 里未捕获异常会直接掐断连接——客户端拿到 `RemoteDisconnected` 而非 JSON-RPC 错误响应。修复后的行为：

| 输入 | 响应 |
|------|------|
| 非 JSON / 畸形 JSON | `-32700` Parse error |
| JSON 数组 / 字符串 / null 等非 dict body | `-32600` Invalid Request |
| 空 body | `-32700` |
| 合法 JSON-RPC 但未知方法 | `-32601` Method not found |

每个畸形用例都是先红后修（修前实测连接被提断），另有一枚 server-alive pin：吞垃圾后继续服务正常请求。

## 参考

- [A2A Protocol Spec](https://github.com/google/A2A)
