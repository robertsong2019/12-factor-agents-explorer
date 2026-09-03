#!/usr/bin/env python3
"""
MCP Client - 轻量级 Model Context Protocol 客户端
零依赖，纯 Python 3 实现

核心功能：
- JSON-RPC 2.0 通信
- stdio transport
- 资源列表、读取
- 工具列表、调用
- 提示模板列表、获取
"""

import json
import subprocess
import threading
import uuid
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum


class TransportType(Enum):
    """传输层类型"""
    STDIO = "stdio"


@dataclass
class Resource:
    """MCP 资源"""
    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"

    @classmethod
    def from_dict(cls, data: Dict) -> "Resource":
        return cls(
            uri=data.get("uri", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            # 兼容两种字段名：MCP 规范 camelCase（mimeType）与早期 snake_case（mime_type）
            mime_type=data.get("mime_type") or data.get("mimeType") or "text/plain"
        )


@dataclass
class Tool:
    """MCP 工具"""
    name: str
    description: str
    input_schema: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict) -> "Tool":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            # 兼容两种字段名：MCP 规范 camelCase（inputSchema）与早期 snake_case（input_schema）
            # 旧实现只读 snake_case，服务器发来的 inputSchema 被静默丢弃成 {}
            input_schema=data.get("input_schema") or data.get("inputSchema") or {}
        )


@dataclass
class Prompt:
    """MCP 提示模板"""
    name: str
    description: str = ""
    arguments: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.arguments is None:
            self.arguments = []

    @classmethod
    def from_dict(cls, data: Dict) -> "Prompt":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            arguments=data.get("arguments", [])
        )


class MCPClient:
    """
    MCP 客户端实现

    通过 stdio 与 MCP 服务器通信，实现 JSON-RPC 2.0 协议
    """

    def __init__(self, server_command: List[str]):
        """
        初始化客户端

        Args:
            server_command: 启动服务器的命令列表，如 ["python", "server.py"]
        """
        self.server_command = server_command
        self.process: Optional[subprocess.Popen] = None
        self.request_id = 0
        self.pending_requests: Dict[str, threading.Event] = {}
        self.responses: Dict[str, Any] = {}
        self._initialized = False

    def start(self) -> bool:
        """启动 MCP 服务器进程"""
        try:
            self.process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # 启动响应监听线程
            threading.Thread(target=self._listen_responses, daemon=True).start()

            # 发送 initialize 请求
            self._initialize()
            self._initialized = True
            return True
        except Exception as e:
            print(f"[MCP Client] 启动失败: {e}")
            return False

    def stop(self):
        """停止 MCP 服务器"""
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
        self._initialized = False

    def _initialize(self):
        """发送初始化请求"""
        self._send_request({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "resources": {},
                    "tools": {},
                    "prompts": {}
                },
                "clientInfo": {
                    "name": "mcp-client-explorer",
                    "version": "0.1.0"
                }
            }
        })

        # 发送 initialized 通知
        self._send_notification({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        })

    def _next_id(self) -> str:
        """生成下一个请求 ID"""
        self.request_id += 1
        return str(self.request_id)

    def _send_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        发送 JSON-RPC 请求并等待响应

        Args:
            request: JSON-RPC 请求对象

        Returns:
            响应对象或 None（出错时）
        """
        if not self.process or not self.process.stdin:
            return None

        request_id = request.get("id")
        event = threading.Event()
        self.pending_requests[request_id] = event

        # 发送请求
        message = json.dumps(request) + "\n"
        self.process.stdin.write(message)
        self.process.stdin.flush()

        # 等待响应
        event.wait(timeout=5.0)

        # 清理
        del self.pending_requests[request_id]
        return self.responses.pop(request_id, None)

    def _send_notification(self, notification: Dict[str, Any]):
        """发送 JSON-RPC 通知（无响应）"""
        if not self.process or not self.process.stdin:
            return

        message = json.dumps(notification) + "\n"
        self.process.stdin.write(message)
        self.process.stdin.flush()

    def _listen_responses(self):
        """监听服务器的响应"""
        if not self.process or not self.process.stdout:
            return

        for line in self.process.stdout:
            if not line.strip():
                continue

            try:
                response = json.loads(line.strip())
                request_id = response.get("id")

                if request_id in self.pending_requests:
                    self.responses[request_id] = response
                    self.pending_requests[request_id].set()
            except json.JSONDecodeError:
                continue

    # ========== 资源操作 ==========

    def list_resources(self) -> List[Resource]:
        """列出所有可用资源"""
        response = self._send_request({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "resources/list"
        })

        if not response or "error" in response:
            return []

        resources = response.get("result", {}).get("resources", [])
        return [Resource.from_dict(r) for r in resources]

    def read_resource(self, uri: str) -> Optional[Dict[str, Any]]:
        """读取指定资源内容"""
        response = self._send_request({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "resources/read",
            "params": {"uri": uri}
        })

        if not response or "error" in response:
            return None

        return response.get("result")

    # ========== 工具操作 ==========

    def list_tools(self) -> List[Tool]:
        """列出所有可用工具"""
        response = self._send_request({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list"
        })

        if not response or "error" in response:
            return []

        tools = response.get("result", {}).get("tools", [])
        return [Tool.from_dict(t) for t in tools]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """调用指定工具"""
        response = self._send_request({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        })

        if not response or "error" in response:
            return None

        return response.get("result")

    # ========== 提示模板操作 ==========

    def list_prompts(self) -> List[Prompt]:
        """列出所有可用提示模板"""
        response = self._send_request({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "prompts/list"
        })

        if not response or "error" in response:
            return []

        prompts = response.get("result", {}).get("prompts", [])
        return [Prompt.from_dict(p) for p in prompts]

    def get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """获取提示模板内容"""
        response = self._send_request({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "prompts/get",
            "params": {
                "name": name,
                "arguments": arguments or {}
            }
        })

        if not response or "error" in response:
            return None

        return response.get("result")

    def __enter__(self):
        """上下文管理器支持"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器支持"""
        self.stop()


# ========== 简化 API ==========

def connect(server_command: List[str]) -> MCPClient:
    """
    便捷函数：连接到 MCP 服务器

    Args:
        server_command: 启动服务器的命令

    Returns:
        MCPClient 实例
    """
    client = MCPClient(server_command)
    client.start()
    return client
