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
            arguments = json.loads(tool_call["arguments"])
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

    def reset(self) -> None:
        """重置对话历史"""
        self._conversation_history.clear()

    def history(self, limit: int = 10) -> List[Dict[str, str]]:
        """获取对话历史"""
        return self._conversation_history[-limit:]

    @property
    def turn_count(self) -> int:
        """返回对话轮次"""
        return len([m for m in self._conversation_history if m["role"] == "user"])
