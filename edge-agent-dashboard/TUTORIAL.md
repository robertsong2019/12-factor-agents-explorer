# Edge Agent Dashboard 教程

> 从零开始搭建 Agent 监控面板，5 分钟上手，30 分钟精通

---

## 1. 环境准备

### 前置要求

- Python 3.9+
- pip

### 安装

```bash
pip install edge-agent-dashboard
# 或者从源码
git clone https://github.com/robertsong2019/edge-agent-dashboard.git
cd edge-agent-dashboard
pip install -e .
```

### 验证安装

```bash
edge-agent-dashboard --help
```

---

## 2. 启动 Dashboard

```bash
# 默认端口 8000
edge-agent-dashboard

# 指定端口
edge-agent-dashboard --port 9000

# 开发模式（自动重载）
edge-agent-dashboard --reload
```

打开 http://localhost:8000 ，你会看到空的 Agent 列表。

---

## 3. 创建你的第一个 Agent

### 方式一：Web 界面

1. 点击右上角「+ 添加 Agent」
2. 填写：
   - **Agent ID**: `hello-agent`
   - **名称**: `Hello Agent`
   - **启动命令**: `python -c "import time; [print(f'tick {i}') or time.sleep(1) for i in range(100)]"`
   - **工作目录**: `/tmp`
3. 勾选「自动启动」→ 点击创建

你会立刻看到日志开始滚动。

### 方式二：API 调用

```bash
curl -X POST http://localhost:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "id": "hello-agent",
    "name": "Hello Agent",
    "command": "python -c \"import time; [print(f tick {i}) or time.sleep(1) for i in range(100)]\"",
    "working_dir": "/tmp",
    "auto_start": true
  }'
```

### 方式三：Python 脚本

```python
import requests

resp = requests.post("http://localhost:8000/api/agents", json={
    "id": "hello-agent",
    "name": "Hello Agent",
    "command": "python example_agent.py",
    "working_dir": "/path/to/agent",
    "auto_start": True,
})
print(resp.json())
```

---

## 4. 监控 Agent

### 资源监控

Dashboard 每秒采集一次数据：

| 指标 | 说明 |
|------|------|
| CPU% | Agent 进程的 CPU 使用率 |
| 内存 (MB) | RSS 内存占用 |
| 网络 (KB/s) | 实时上传/下载速率 |

图表自动滚动显示最近 60 秒的趋势。

### 日志查看

- 实时日志以 `tail -f` 风格展示
- stdout → 白色，stderr → 红色
- 支持暂停/继续滚动

### Agent 控制

- ▶️ **启动** — 运行 Agent 的启动命令
- ⏹️ **停止** — 发送 SIGTERM
- 🔄 **重启** — 停止后重新启动
- 🗑️ **删除** — 移除 Agent（先停止）

---

## 5. WebSocket 实时集成

如果你想把 Dashboard 数据接入自己的系统：

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => console.log('Connected to Dashboard');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  switch (msg.type) {
    case 'agent_status':   // Agent 状态变化
      console.log(`Agent ${msg.data.id}: ${msg.data.status}`);
      break;
    case 'resource_update': // 资源数据
      console.log(`CPU: ${msg.data.cpu}%, MEM: ${msg.data.memory}MB`);
      break;
    case 'log_line':        // 日志行
      console.log(`[${msg.data.agent_id}] ${msg.data.line}`);
      break;
  }
};

ws.onclose = () => {
  console.log('Disconnected, auto-reconnecting...');
};
```

---

## 6. 实战：监控多个 Agent

假设你有 3 个 Agent 需要管理：

```bash
# 数据采集 Agent
curl -X POST http://localhost:8000/api/agents -H "Content-Type: application/json" \
  -d '{"id":"collector","name":"Data Collector","command":"python collector.py","working_dir":"/app/collector"}'

# 处理 Agent
curl -X POST http://localhost:8000/api/agents -H "Content-Type: application/json" \
  -d '{"id":"processor","name":"Data Processor","command":"python processor.py","working_dir":"/app/processor"}'

# 报告 Agent
curl -X POST http://localhost:8000/api/agents -H "Content-Type: application/json" \
  -d '{"id":"reporter","name":"Report Generator","command":"python reporter.py","working_dir":"/app/reporter"}'
```

Dashboard 会同时展示所有 Agent 的状态和资源使用情况。

---

## 7. API 速查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/agents` | 列出所有 Agent |
| POST | `/api/agents` | 创建 Agent |
| GET | `/api/agents/{id}` | 获取单个 Agent |
| POST | `/api/agents/{id}/start` | 启动 |
| POST | `/api/agents/{id}/stop` | 停止 |
| POST | `/api/agents/{id}/restart` | 重启 |
| DELETE | `/api/agents/{id}` | 删除 |
| GET | `/api/agents/{id}/logs` | 获取历史日志 |

完整 API 文档：http://localhost:8000/docs （Swagger UI）

---

## 8. 常见问题

### Q: Agent 显示 "error" 状态？
检查启动命令是否正确，工作目录是否存在。查看日志获取错误详情。

### Q: WebSocket 断开？
Dashboard 会自动重连。如果持续断开，检查网络和服务器负载。

### Q: 资源图表不动？
确保 Agent 进程正在运行。Dashboard 只监控运行中的进程。

### Q: 端口被占用？
```bash
edge-agent-dashboard --port 9000
```

---

## 下一步

- 阅读 [USAGE.md](USAGE.md) 了解高级配置
- 阅读 [SCREENSHOTS.md](SCREENSHOTS.md) 了解界面布局
- 查看 [example_agent.py](example_agent.py) 了解如何编写可监控的 Agent
