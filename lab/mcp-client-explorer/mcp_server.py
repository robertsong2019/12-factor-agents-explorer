#!/usr/bin/env python3
"""
MCP Server - 简单的测试服务器
演示 MCP 协议的资源、工具、提示模板功能
"""

import json
import sys
import math
from datetime import datetime
from typing import Dict, Any, List


class MCPServer:
    """
    简单的 MCP 服务器实现

    通过 stdin/stdout 实现 JSON-RPC 2.0 通信
    """

    def __init__(self):
        self.initialized = False

    def run(self):
        """主循环：读取请求并返回响应"""
        for line in sys.stdin:
            if not line.strip():
                continue

            try:
                request = json.loads(line.strip())
                response = self._handle_request(request)

                if response:  # 通知不需要响应
                    print(json.dumps(response))
                    sys.stdout.flush()
            except json.JSONDecodeError:
                continue
            except Exception:
                # 单行处理异常绝不允许杀死主循环（否则服务器对后续所有请求静默失联）
                continue

    def _handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理单个请求"""
        # 合法 JSON 但非 object（如 [1,2,3] / 42 / null）→ -32600 Invalid Request
        if not isinstance(request, dict):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request: expected object"}
            }

        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        # initialized 通知（无响应）
        if method == "notifications/initialized":
            self.initialized = True
            return None

        # JSON-RPC 2.0：通知（无 id）绝不回包——否则下游客户端会收到 id:null 的孤儿错误
        if request_id is None:
            return None

        # 初始化
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "resources": {"subscribe": False, "listChanged": False},
                        "tools": {"listChanged": False},
                        "prompts": {"listChanged": False}
                    },
                    "serverInfo": {
                        "name": "test-mcp-server",
                        "version": "0.1.0"
                    }
                }
            }

        # 资源列表
        if method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "resources": [
                        {
                            "uri": "data://weather/current",
                            "name": "当前天气",
                            "description": "模拟的当前天气数据",
                            "mime_type": "application/json"
                        },
                        {
                            "uri": "data://system/status",
                            "name": "系统状态",
                            "description": "模拟的系统状态信息",
                            "mime_type": "application/json"
                        }
                    ]
                }
            }

        # 读取资源
        if method == "resources/read":
            uri = params.get("uri")
            content = self._get_resource_content(uri)
            if content:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": json.dumps(content, ensure_ascii=False)
                            }
                        ]
                    }
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": f"Resource not found: {uri}"
                    }
                }

        # 工具列表
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "calculate",
                            "description": "执行数学计算（加、减、乘、除）",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "operation": {
                                        "type": "string",
                                        "enum": ["add", "subtract", "multiply", "divide"],
                                        "description": "运算类型"
                                    },
                                    "a": {
                                        "type": "number",
                                        "description": "第一个操作数"
                                    },
                                    "b": {
                                        "type": "number",
                                        "description": "第二个操作数"
                                    }
                                },
                                "required": ["operation", "a", "b"]
                            }
                        },
                        {
                            "name": "fibonacci",
                            "description": "计算斐波那契数列的第 n 项",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "n": {
                                        "type": "integer",
                                        "minimum": 0,
                                        "description": "要计算的项数"
                                    }
                                },
                                "required": ["n"]
                            }
                        },
                        {
                            "name": "reverse_string",
                            "description": "反转字符串",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "text": {
                                        "type": "string",
                                        "description": "要反转的字符串"
                                    }
                                },
                                "required": ["text"]
                            }
                        }
                    ]
                }
            }

        # 调用工具
        if method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})

            try:
                result = self._execute_tool(tool_name, args)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, ensure_ascii=False)
                            }
                        ]
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                }

        # 提示模板列表
        if method == "prompts/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "prompts": [
                        {
                            "name": "code_review",
                            "description": "代码审查提示模板",
                            "arguments": [
                                {
                                    "name": "language",
                                    "description": "编程语言",
                                    "required": False
                                },
                                {
                                    "name": "focus",
                                    "description": "审查重点",
                                    "required": False
                                }
                            ]
                        },
                        {
                            "name": "task_breakdown",
                            "description": "任务分解提示模板",
                            "arguments": [
                                {
                                    "name": "task",
                                    "description": "要分解的任务",
                                    "required": True
                                }
                            ]
                        }
                    ]
                }
            }

        # 获取提示模板
        if method == "prompts/get":
            prompt_name = params.get("name")
            args = params.get("arguments", {})

            try:
                result = self._get_prompt(prompt_name, args)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "messages": result
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": str(e)
                    }
                }

        # 未知方法
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }

    def _get_resource_content(self, uri: str) -> Dict[str, Any]:
        """获取资源内容"""
        if uri == "data://weather/current":
            return {
                "location": "Shanghai",
                "temperature": 22,
                "humidity": 65,
                "condition": "Cloudy",
                "timestamp": datetime.now().isoformat()
            }
        elif uri == "data://system/status":
            return {
                "cpu_usage": 45.2,
                "memory_usage": 62.8,
                "disk_usage": 71.5,
                "uptime": "5d 12h 34m",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return None

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """执行工具"""
        if tool_name == "calculate":
            op = args["operation"]
            a = args["a"]
            b = args["b"]

            if op == "add":
                return a + b
            elif op == "subtract":
                return a - b
            elif op == "multiply":
                return a * b
            elif op == "divide":
                return a / b
            else:
                raise ValueError(f"Unknown operation: {op}")

        elif tool_name == "fibonacci":
            n = args["n"]
            if n < 0:
                raise ValueError("n must be non-negative")

            # 迭代计算
            a, b = 0, 1
            for _ in range(n):
                a, b = b, a + b
            return a

        elif tool_name == "reverse_string":
            text = args["text"]
            return text[::-1]

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _get_prompt(self, prompt_name: str, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取提示模板"""
        if prompt_name == "code_review":
            language = args.get("language", "Python")
            focus = args.get("focus", "general")

            return [
                {
                    "role": "system",
                    "content": f"You are an expert {language} code reviewer."
                },
                {
                    "role": "user",
                    "content": f"Please review the code focusing on: {focus}\n\nProvide feedback on:\n1. Correctness\n2. Performance\n3. Best practices\n4. Security considerations"
                }
            ]

        elif prompt_name == "task_breakdown":
            task = args.get("task", "")

            return [
                {
                    "role": "system",
                    "content": "You are an expert project manager and technical lead."
                },
                {
                    "role": "user",
                    "content": f"Break down the following task into actionable steps:\n\nTask: {task}\n\nFor each step, provide:\n- Description\n- Estimated effort\n- Dependencies\n- Success criteria"
                }
            ]

        else:
            raise ValueError(f"Unknown prompt: {prompt_name}")


if __name__ == "__main__":
    server = MCPServer()
    server.run()
