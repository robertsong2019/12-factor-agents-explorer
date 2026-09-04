#!/usr/bin/env python3
"""
Minimal A2A-Compliant Agent — 零依赖 Python 实现
演示 A2A 协议核心概念：Agent Card、Task 生命周期、JSON-RPC 通信

运行方式:
  1. 启动服务器: python a2a_minimal.py server --port 8001
  2. 启动另一个: python a2a_minimal.py server --port 8002 --name "TranslatorAgent"
  3. 运行客户端: python a2a_minimal.py client --url http://localhost:8001
"""

import json
import uuid
import argparse
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from datetime import datetime, timezone

# ============================================================
# Agent Card — 能力声明
# ============================================================

AGENT_CARD = {
    "name": "EchoAgent",
    "description": "A minimal A2A agent that echoes and transforms messages",
    "url": "http://localhost:8001",
    "version": "0.1.0",
    "capabilities": {"streaming": False, "pushNotifications": False},
    "authentication": {"schemes": ["none"]},
    "skills": [
        {
            "id": "echo",
            "name": "Echo",
            "description": "Echoes back the input message",
            "inputModes": ["text"],
            "outputModes": ["text"],
        },
        {
            "id": "reverse",
            "name": "Reverse",
            "description": "Reverses the input text",
            "inputModes": ["text"],
            "outputModes": ["text"],
        },
    ],
}


# ============================================================
# Task Store — 内存任务存储
# ============================================================

class TaskStore:
    def __init__(self):
        self.tasks = {}

    def create(self, task_id=None):
        tid = task_id or str(uuid.uuid4())
        task = {
            "id": tid,
            "status": "submitted",
            "messages": [],
            "artifacts": [],
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        self.tasks[tid] = task
        return task

    def get(self, task_id):
        return self.tasks.get(task_id)

    def update_status(self, task_id, status):
        task = self.tasks.get(task_id)
        if task:
            task["status"] = status
        return task


# ============================================================
# Agent Executor — Agent 逻辑（核心业务）
# ============================================================

class AgentExecutor:
    """Agent 的核心逻辑：处理消息，生成响应"""

    def execute(self, task, message_parts):
        """处理任务消息，返回响应 parts"""
        task["status"] = "working"

        results = []
        for part in message_parts:
            if part.get("kind") == "text" or "text" in part:
                text = part.get("text", "")
                # 简单能力：echo + reverse
                results.append({"kind": "text", "text": f"Echo: {text}"})
                results.append({"kind": "text", "text": f"Reverse: {text[::-1]}"})

        task["status"] = "completed"
        task["artifacts"].append({
            "parts": results,
            "index": len(task["artifacts"]),
        })
        return results


# ============================================================
# A2A Server — JSON-RPC 2.0 over HTTP
# ============================================================

class A2AHandler(BaseHTTPRequestHandler):
    """处理 A2A JSON-RPC 请求"""
    store = TaskStore()
    executor = AgentExecutor()

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        """Agent Card 发现: GET /.well-known/agent.json"""
        if self.path == "/.well-known/agent.json":
            self._send_json(AGENT_CARD)
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        """JSON-RPC 2.0 端点"""
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        # 垃圾输入防御：畸形 JSON / 非 object 体必须回 JSON-RPC 错误，
        # 而不是让 handler 抛异常断连（客户端只见 RemoteDisconnected）。
        try:
            body = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json({
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": "Parse error: body is not valid JSON"},
                "id": None,
            })
            return
        if not isinstance(body, dict):
            self._send_json({
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request: body must be a JSON object"},
                "id": None,
            })
            return

        method = body.get("method", "")
        params = body.get("params", {})
        req_id = body.get("id")

        # ---- A2A 核心操作 ----
        if method == "message/send":
            # 发送消息给 Agent，创建或继续 Task
            task_id = params.get("taskId") or str(uuid.uuid4())
            task = self.store.get(task_id) or self.store.create(task_id)
            message = params.get("message", {})
            task["messages"].append(message)

            # 执行 Agent 逻辑
            parts = message.get("parts", [])
            response_parts = self.executor.execute(task, parts)

            result = {
                "id": task["id"],
                "status": task["status"],
                "artifacts": task["artifacts"],
            }
            self._send_json({"jsonrpc": "2.0", "result": result, "id": req_id})

        elif method == "tasks/get":
            task_id = params.get("id")
            task = self.store.get(task_id)
            if task:
                self._send_json({"jsonrpc": "2.0", "result": task, "id": req_id})
            else:
                self._send_json({
                    "jsonrpc": "2.0",
                    "error": {"code": -32602, "message": f"Task {task_id} not found"},
                    "id": req_id,
                })

        elif method == "tasks/cancel":
            task_id = params.get("id")
            task = self.store.update_status(task_id, "cancelled")
            if task:
                self._send_json({"jsonrpc": "2.0", "result": task, "id": req_id})
            else:
                self._send_json({
                    "jsonrpc": "2.0",
                    "error": {"code": -32602, "message": "Task not found"},
                    "id": req_id,
                })

        else:
            self._send_json({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method {method} not found"},
                "id": req_id,
            })

    def log_message(self, format, *args):
        print(f"[A2A Server] {args[0]}")


# ============================================================
# A2A Client — 发现 Agent 并发送任务
# ============================================================

class A2AClient:
    """轻量级 A2A 客户端"""

    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def discover(self):
        """发现远程 Agent 的能力 (获取 Agent Card)"""
        url = f"{self.base_url}/.well-known/agent.json"
        req = Request(url)
        with urlopen(req) as resp:
            return json.loads(resp.read())

    def _rpc(self, method, params):
        """发送 JSON-RPC 请求"""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": str(uuid.uuid4()),
        }
        data = json.dumps(payload).encode()
        req = Request(
            f"{self.base_url}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req) as resp:
            return json.loads(resp.read())

    def send_message(self, text, task_id=None):
        """发送文本消息给 Agent"""
        params = {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
            }
        }
        if task_id:
            params["taskId"] = task_id
        return self._rpc("message/send", params)

    def get_task(self, task_id):
        """查询任务状态"""
        return self._rpc("tasks/get", {"id": task_id})

    def cancel_task(self, task_id):
        """取消任务"""
        return self._rpc("tasks/cancel", {"id": task_id})


# ============================================================
# Agent-to-Agent Federation: 多 Agent 协作演示
# ============================================================

def demo_federation():
    """
    演示 Agent 联邦协作：
    1. Client 发现多个 Agent
    2. 根据能力匹配选择合适的 Agent
    3. 委派任务并收集结果
    """
    print("=" * 60)
    print("🤝 Agent Federation Demo")
    print("=" * 60)

    agents_urls = [
        "http://localhost:8001",
        "http://localhost:8002",
    ]

    discovered = []
    for url in agents_urls:
        try:
            client = A2AClient(url)
            card = client.discover()
            discovered.append({"url": url, "card": card, "client": client})
            print(f"\n📡 Discovered: {card['name']}")
            print(f"   Skills: {[s['name'] for s in card.get('skills', [])]}")
        except Exception as e:
            print(f"\n❌ Failed to discover {url}: {e}")

    if not discovered:
        print("\n⚠️  No agents found. Start servers first:")
        print("   python a2a_minimal.py server --port 8001")
        print("   python a2a_minimal.py server --port 8002 --name TranslatorAgent")
        return

    # 选择第一个可用 Agent 发送任务
    agent = discovered[0]
    print(f"\n📤 Sending task to {agent['card']['name']}...")
    result = agent["client"].send_message("Hello A2A Protocol!")
    print(f"\n✅ Result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Minimal A2A Agent")
    sub = parser.add_subparsers(dest="command")

    # Server
    srv = sub.add_parser("server", help="Start A2A agent server")
    srv.add_argument("--port", type=int, default=8001)
    srv.add_argument("--name", default="EchoAgent")

    # Client
    cli = sub.add_parser("client", help="Connect to A2A agent")
    cli.add_argument("--url", default="http://localhost:8001")
    cli.add_argument("--message", default="Hello A2A!")

    # Federation demo
    sub.add_parser("federation", help="Demo multi-agent federation")

    args = parser.parse_args()

    if args.command == "server":
        AGENT_CARD["name"] = args.name
        AGENT_CARD["url"] = f"http://localhost:{args.port}"
        server = HTTPServer(("0.0.0.0", args.port), A2AHandler)
        print(f"🚀 A2A Agent '{args.name}' on port {args.port}")
        print(f"📋 Agent Card: http://localhost:{args.port}/.well-known/agent.json")
        server.serve_forever()

    elif args.command == "client":
        client = A2AClient(args.url)
        # 1. 发现
        card = client.discover()
        print(f"📡 Discovered: {card['name']}")
        print(f"   Skills: {[s['name'] for s in card.get('skills', [])]}")

        # 2. 发送任务
        print(f"\n📤 Sending: {args.message}")
        result = client.send_message(args.message)
        print(f"\n✅ Response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.command == "federation":
        demo_federation()

    else:
        parser.print_help()
