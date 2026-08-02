"""
Agent - 核心代理类
"""

import json
from typing import List, Dict, Any, Optional, Callable
from .llm import LLM
from .memory import Memory
from .tools import Tool


class Agent:
    """AI Agent 核心类"""

    def __init__(
        self,
        name: str,
        instructions: str,
        llm: Optional[LLM] = None,
        tools: Optional[List[Tool]] = None,
        memory: Optional[Memory] = None,
        max_iterations: int = 10,
        verbose: bool = True
    ):
        self.name = name
        self.instructions = instructions
        self.llm = llm or LLM.mock()
        self.tools = tools or []
        self.memory = memory or Memory()
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.on_step: Optional[Callable[[Dict[str, Any]], None]] = None
        self._conversation_history: List[Dict[str, str]] = []

    def run(self, user_input: str, context: Optional[str] = None) -> str:
        """
        运行代理

        Args:
            user_input: 用户输入
            context: 额外上下文

        Returns:
            代理的最终响应
        """
        self._log(f"🤖 {self.name} 开始处理: {user_input}")

        # 构建初始消息
        messages = self._build_messages(user_input, context)

        # 多轮迭代
        response = {"content": "", "tool_calls": []}
        for iteration in range(self.max_iterations):
            self._log(f"\n📍 迭代 {iteration + 1}/{self.max_iterations}")

            # 调用 LLM
            response = self.llm.chat(
                messages=messages,
                tools=[tool.to_dict() for tool in self.tools] if self.tools else None
            )

            # 保存响应
            if response["content"]:
                messages.append({"role": "assistant", "content": response["content"]})
                self._log(f"💬 Agent: {response['content'][:200]}{'...' if len(response['content']) > 200 else ''}")

            # 处理工具调用
            tool_calls = response.get("tool_calls", [])
            if tool_calls:
                for call in tool_calls:
                    tool_result = self._execute_tool(call)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "name": call["name"],
                        "content": tool_result
                    })
                    self._log(f"🔧 工具 {call['name']}: {tool_result[:150]}{'...' if len(tool_result) > 150 else ''}")
            else:
                # 没有工具调用，结束
                if self.on_step:
                    self.on_step({"iteration": iteration + 1, "response": response.get("content", ""), "tool_calls": []})
                break

            if self.on_step:
                self.on_step({"iteration": iteration + 1, "response": response.get("content", ""), "tool_calls": [c["name"] for c in tool_calls]})

        # 保存到记忆
        final_response = response.get("content", "处理完成")

        # 记录助手回复到对话历史
        self._conversation_history.append({"role": "assistant", "content": final_response})

        self.memory.add(
            f"用户: {user_input}\n回复: {final_response}",
            metadata={"agent": self.name}
        )

        return final_response

    def _build_messages(self, user_input: str, context: Optional[str] = None) -> List[Dict[str, str]]:
        """构建消息列表"""
        messages = [
            {"role": "system", "content": self._build_system_prompt(context)}
        ]

        # 添加历史对话（最近 10 轮）
        for msg in self._conversation_history[-10:]:
            messages.append(msg)

        # 添加当前输入
        messages.append({"role": "user", "content": user_input})

        # 记录到对话历史
        self._conversation_history.append({"role": "user", "content": user_input})

        return messages

    def _build_system_prompt(self, context: Optional[str] = None) -> str:
        """构建系统提示词"""
        parts = [
            f"你是 {self.name}。",
            f"\n## 你的指令\n{self.instructions}",
        ]

        if self.tools:
            parts.append("\n## 可用工具")
            for tool in self.tools:
                parts.append(f"- {tool.name}: {tool.description}")

        if context:
            parts.append(f"\n## 上下文\n{context}")

        # 添加记忆
        memory_context = self.memory.to_context(max_tokens=500)
        if memory_context:
            parts.append(f"\n{memory_context}")

        parts.append("\n## 工作流程")
        parts.append("1. 理解用户需求")
        parts.append("2. 分析需要哪些信息")
        parts.append("3. 调用适当的工具获取信息")
        parts.append("4. 综合信息并提供有用的回复")
        parts.append("\n重要: 只在必要时调用工具，不要重复调用相同的工具。")

        return "\n".join(parts)

    def _execute_tool(self, tool_call: Dict[str, Any]) -> str:
        """执行工具调用"""
        tool_name = tool_call["name"]
        try:
            arguments = json.loads(tool_call.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError) as e:
            return f"错误: 无效的参数格式 - {e}"

        # 查找工具
        tool = next((t for t in self.tools if t.name == tool_name), None)
        if not tool:
            return f"错误: 工具 {tool_name} 不存在"

        try:
            result = tool.execute(**arguments)
            return str(result)
        except Exception as e:
            return f"错误: {str(e)}"

    def _log(self, message: str) -> None:
        """日志输出"""
        if self.verbose:
            print(message)

    def run_batch(self, inputs: List[str], context: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        批量处理多个输入

        Args:
            inputs: 用户输入列表
            context: 共享的额外上下文（可选）

        Returns:
            结果列表，每项包含 {input, response, success, error}
        """
        results: List[Dict[str, Any]] = []
        for i, user_input in enumerate(inputs):
            try:
                response = self.run(user_input, context)
                results.append({
                    "input": user_input,
                    "response": response,
                    "success": True,
                    "error": None
                })
            except Exception as e:
                results.append({
                    "input": user_input,
                    "response": None,
                    "success": False,
                    "error": str(e)
                })
                self._log(f"⚠️ 输入 {i+1} 处理失败: {e}")
        return results

    def summary(self) -> Dict[str, Any]:
        """
        生成对话历史的摘要信息

        Returns:
            包含对话统计信息的字典
        """
        user_msgs = [m for m in self._conversation_history if m["role"] == "user"]
        assistant_msgs = [m for m in self._conversation_history if m["role"] == "assistant"]

        # 计算总字符数
        total_chars = sum(len(m["content"]) for m in self._conversation_history)

        # 最近几轮对话（简略）
        recent = []
        for m in self._conversation_history[-6:]:
            content = m["content"]
            recent.append({
                "role": m["role"],
                "preview": content[:80] + ("..." if len(content) > 80 else "")
            })

        return {
            "agent_name": self.name,
            "turn_count": len(user_msgs),
            "total_messages": len(self._conversation_history),
            "user_messages": len(user_msgs),
            "assistant_messages": len(assistant_msgs),
            "total_chars": total_chars,
            "tool_count": len(self.tools),
            "memory_count": self.memory.count(),
            "recent": recent
        }

    def reset(self) -> None:
        """重置对话历史"""
        self._conversation_history.clear()

    def history(self, limit: int = 10) -> List[Dict[str, str]]:
        """获取对话历史"""
        if limit <= 0:
            return []
        return self._conversation_history[-limit:]

    @property
    def turn_count(self) -> int:
        """返回对话轮次"""
        return len([m for m in self._conversation_history if m["role"] == "user"])

    def add_tool(self, tool: Tool) -> None:
        """运行时动态添加工具。如果同名工具已存在则替换。"""
        self.tools = [t for t in self.tools if t.name != tool.name]
        self.tools.append(tool)

    def remove_tool(self, name: str) -> bool:
        """按名称移除工具，返回是否成功。"""
        before = len(self.tools)
        self.tools = [t for t in self.tools if t.name != name]
        return len(self.tools) < before

    def conversation_stats(self) -> Dict[str, Any]:
        """Statistics about the current conversation history.

        Returns message counts by role, average message length, and tool usage.
        """
        history = self._conversation_history
        if not history:
            return {"total_messages": 0, "by_role": {}, "avg_length": 0,
                    "tool_calls": 0, "est_tokens": 0}

        by_role: Dict[str, int] = {}
        total_chars = 0
        tool_calls = 0

        for msg in history:
            role = msg.get("role", "unknown")
            by_role[role] = by_role.get(role, 0) + 1
            content = msg.get("content", "")
            total_chars += len(content)
            # Detect tool calls in assistant messages
            if role == "assistant" and "tool_call" in content.lower():
                tool_calls += 1

        return {
            "total_messages": len(history),
            "by_role": by_role,
            "avg_length": round(total_chars / len(history), 1),
            "tool_calls": tool_calls,
            "est_tokens": total_chars // 4,  # rough estimate
        }
