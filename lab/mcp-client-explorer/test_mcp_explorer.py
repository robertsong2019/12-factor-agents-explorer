#!/usr/bin/env python3
"""
mcp-client-explorer 集成测试

两层测试策略：
- RawServer harness：直接走 stdio 行协议，做协议级测试（不依赖 MCPClient）
- MCPClient E2E：真实客户端↔真实服务器子进程，做集成往返测试
"""

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from mcp_client import MCPClient, Resource, Tool, Prompt, connect

DIR = Path(__file__).parent
SERVER_CMD = [sys.executable, "mcp_server.py"]

INIT_REQUEST = {
    "jsonrpc": "2.0",
    "id": "0",
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-harness", "version": "0.0.1"},
    },
}


class RawServer:
    """直接与 mcp_server.py 子进程按 JSON-RPC 行协议通信的测试 harness"""

    def __init__(self):
        self.p = subprocess.Popen(
            SERVER_CMD,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=DIR,
        )
        self._buf = []
        self._lock = threading.Lock()
        self._t = threading.Thread(target=self._read, daemon=True)
        self._t.start()

    def _read(self):
        for line in self.p.stdout:
            line = line.strip()
            if not line:
                continue
            with self._lock:
                self._buf.append(json.loads(line))

    def send_raw(self, text):
        self.p.stdin.write(text + "\n")
        self.p.stdin.flush()

    def send(self, obj):
        self.send_raw(json.dumps(obj))

    def recv(self, timeout=2.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if self._buf:
                    return self._buf.pop(0)
            time.sleep(0.01)
        return None

    def request(self, obj, timeout=2.0):
        self.send(obj)
        return self.recv(timeout)

    def silent(self, window=0.4):
        """window 秒内服务器没有任何输出则 True"""
        return self.recv(timeout=window) is None

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        self.p.terminate()
        try:
            self.p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.p.kill()


@pytest.fixture
def server():
    s = RawServer()
    yield s
    s.close()


# ========== initialize 握手 ==========

def test_initialize_handshake(server):
    resp = server.request(INIT_REQUEST)
    assert resp is not None
    assert resp["id"] == "0"
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert resp["result"]["serverInfo"]["name"] == "test-mcp-server"


def test_initialized_notification_gets_no_response(server):
    server.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert server.silent()


# ========== resources ==========

def test_resources_list(server):
    server.request(INIT_REQUEST)
    resp = server.request({"jsonrpc": "2.0", "id": "1", "method": "resources/list"})
    uris = [r["uri"] for r in resp["result"]["resources"]]
    assert "data://weather/current" in uris
    assert "data://system/status" in uris


def test_resources_read_ok(server):
    server.request(INIT_REQUEST)
    resp = server.request({
        "jsonrpc": "2.0", "id": "2", "method": "resources/read",
        "params": {"uri": "data://weather/current"},
    })
    content = resp["result"]["contents"][0]
    assert content["uri"] == "data://weather/current"
    payload = json.loads(content["text"])
    assert "temperature" in payload


def test_resources_read_not_found(server):
    server.request(INIT_REQUEST)
    resp = server.request({
        "jsonrpc": "2.0", "id": "3", "method": "resources/read",
        "params": {"uri": "data://nope"},
    })
    assert resp["error"]["code"] == -32602


# ========== tools ==========

def test_tools_list(server):
    server.request(INIT_REQUEST)
    resp = server.request({"jsonrpc": "2.0", "id": "4", "method": "tools/list"})
    names = [t["name"] for t in resp["result"]["tools"]]
    assert names == ["calculate", "fibonacci", "reverse_string"]


@pytest.mark.parametrize("op,a,b,expected", [
    ("add", 2, 3, 5),
    ("subtract", 10, 4, 6),
    ("multiply", 6, 7, 42),
    ("divide", 7, 2, 3.5),
])
def test_calculate_four_ops(server, op, a, b, expected):
    server.request(INIT_REQUEST)
    resp = server.request({
        "jsonrpc": "2.0", "id": "5", "method": "tools/call",
        "params": {"name": "calculate", "arguments": {"operation": op, "a": a, "b": b}},
    })
    assert json.loads(resp["result"]["content"][0]["text"]) == expected


@pytest.mark.parametrize("n,expected", [(0, 0), (1, 1), (2, 1), (10, 55)])
def test_fibonacci(server, n, expected):
    server.request(INIT_REQUEST)
    resp = server.request({
        "jsonrpc": "2.0", "id": "6", "method": "tools/call",
        "params": {"name": "fibonacci", "arguments": {"n": n}},
    })
    assert json.loads(resp["result"]["content"][0]["text"]) == expected


def test_reverse_string(server):
    server.request(INIT_REQUEST)
    resp = server.request({
        "jsonrpc": "2.0", "id": "7", "method": "tools/call",
        "params": {"name": "reverse_string", "arguments": {"text": "mcp"}},
    })
    assert json.loads(resp["result"]["content"][0]["text"]) == "pcm"


def test_calculate_unknown_op_is_error(server):
    server.request(INIT_REQUEST)
    resp = server.request({
        "jsonrpc": "2.0", "id": "8", "method": "tools/call",
        "params": {"name": "calculate",
                   "arguments": {"operation": "modulo", "a": 1, "b": 2}},
    })
    assert resp["error"]["code"] == -32603


def test_divide_by_zero_is_error_not_crash(server):
    server.request(INIT_REQUEST)
    resp = server.request({
        "jsonrpc": "2.0", "id": "9", "method": "tools/call",
        "params": {"name": "calculate", "arguments": {"operation": "divide", "a": 1, "b": 0}},
    })
    assert resp["error"]["code"] == -32603
    # 服务器必须存活：下一个合法请求仍可回答
    resp2 = server.request({"jsonrpc": "2.0", "id": "10", "method": "resources/list"})
    assert "result" in resp2


def test_fibonacci_negative_is_error(server):
    server.request(INIT_REQUEST)
    resp = server.request({
        "jsonrpc": "2.0", "id": "11", "method": "tools/call",
        "params": {"name": "fibonacci", "arguments": {"n": -1}},
    })
    assert resp["error"]["code"] == -32603


def test_unknown_tool_is_error(server):
    server.request(INIT_REQUEST)
    resp = server.request({
        "jsonrpc": "2.0", "id": "12", "method": "tools/call",
        "params": {"name": "nope", "arguments": {}},
    })
    assert resp["error"]["code"] == -32603


# ========== prompts ==========

def test_prompts_list(server):
    server.request(INIT_REQUEST)
    resp = server.request({"jsonrpc": "2.0", "id": "13", "method": "prompts/list"})
    names = [p["name"] for p in resp["result"]["prompts"]]
    assert names == ["code_review", "task_breakdown"]


def test_prompt_code_review_default_and_custom_language(server):
    server.request(INIT_REQUEST)
    resp = server.request({
        "jsonrpc": "2.0", "id": "14", "method": "prompts/get",
        "params": {"name": "code_review", "arguments": {"language": "Rust"}},
    })
    msgs = resp["result"]["messages"]
    assert len(msgs) == 2
    assert "Rust" in msgs[0]["content"]
    # 默认 language=Python 的分支也验证
    resp2 = server.request({
        "jsonrpc": "2.0", "id": "15", "method": "prompts/get",
        "params": {"name": "code_review", "arguments": {}},
    })
    assert "Python" in resp2["result"]["messages"][0]["content"]


def test_prompt_task_breakdown_embeds_task(server):
    server.request(INIT_REQUEST)
    resp = server.request({
        "jsonrpc": "2.0", "id": "16", "method": "prompts/get",
        "params": {"name": "task_breakdown", "arguments": {"task": "write tests"}},
    })
    assert "write tests" in resp["result"]["messages"][1]["content"]


def test_unknown_prompt_is_error(server):
    server.request(INIT_REQUEST)
    resp = server.request({
        "jsonrpc": "2.0", "id": "17", "method": "prompts/get",
        "params": {"name": "nope", "arguments": {}},
    })
    assert resp["error"]["code"] == -32602


# ========== 协议健壮性 ==========

def test_unknown_method_is_error(server):
    server.request(INIT_REQUEST)
    resp = server.request({"jsonrpc": "2.0", "id": "18", "method": "no/such/method"})
    assert resp["error"]["code"] == -32601


def test_malformed_json_line_ignored_server_survives(server):
    server.send_raw("this is not json {{{")
    server.request(INIT_REQUEST)  # 首个请求（不被垃圾行干扰）
    resp = server.request({"jsonrpc": "2.0", "id": "19", "method": "resources/list"})
    assert "result" in resp


# ========== MCPClient E2E（真实客户端 ↔ 真实服务器） ==========

@pytest.fixture
def client():
    c = MCPClient(SERVER_CMD)
    assert c.start(), "client.start() 应成功"
    yield c
    c.stop()


def test_client_start_stop(client):
    assert client._initialized is True


def test_client_list_resources(client):
    resources = client.list_resources()
    assert len(resources) == 2
    assert all(isinstance(r, Resource) for r in resources)
    assert resources[0].name  # 非空名称


def test_client_read_resource(client):
    result = client.read_resource("data://system/status")
    assert result is not None
    payload = json.loads(result["contents"][0]["text"])
    assert "cpu_usage" in payload
    assert client.read_resource("data://nope") is None  # 错误→None


def test_client_list_tools(client):
    tools = client.list_tools()
    assert len(tools) == 3
    assert all(isinstance(t, Tool) for t in tools)
    calc = next(t for t in tools if t.name == "calculate")
    # 回归：服务器发 camelCase inputSchema，客户端不得静默丢成 {}
    assert set(calc.input_schema["required"]) == {"operation", "a", "b"}
    assert calc.input_schema["properties"]["operation"]["enum"] == [
        "add", "subtract", "multiply", "divide"]
    fib = next(t for t in tools if t.name == "fibonacci")
    assert fib.input_schema["properties"]["n"]["type"] == "integer"


def test_tool_from_dict_accepts_both_field_names():
    """红色回归：from_dict 必须同时接受 inputSchema / input_schema"""
    camel = Tool.from_dict({"name": "t", "inputSchema": {"type": "object"}})
    snake = Tool.from_dict({"name": "t", "input_schema": {"type": "string"}})
    assert camel.input_schema == {"type": "object"}
    assert snake.input_schema == {"type": "string"}
    assert Tool.from_dict({"name": "t"}).input_schema == {}


def test_resource_from_dict_accepts_both_field_names():
    camel = Resource.from_dict({"uri": "u://1", "name": "n", "mimeType": "application/json"})
    snake = Resource.from_dict({"uri": "u://2", "name": "n", "mime_type": "text/csv"})
    assert camel.mime_type == "application/json"
    assert snake.mime_type == "text/csv"
    assert Resource.from_dict({"uri": "u", "name": "n"}).mime_type == "text/plain"


def test_client_call_tool_roundtrip(client):
    result = client.call_tool("calculate", {"operation": "add", "a": 20, "b": 22})
    assert json.loads(result["content"][0]["text"]) == 42
    assert client.call_tool("nope", {}) is None  # 未知工具→None


def test_client_prompts_roundtrip(client):
    prompts = client.list_prompts()
    assert len(prompts) == 2
    assert all(isinstance(p, Prompt) for p in prompts)
    result = client.get_prompt("code_review", {"focus": "security"})
    assert "security" in result["messages"][1]["content"]
    assert client.get_prompt("nope") is None


def test_client_connect_helper(client=None):
    c = connect(SERVER_CMD)
    try:
        assert c._initialized
        assert len(c.list_tools()) == 3
    finally:
        c.stop()
