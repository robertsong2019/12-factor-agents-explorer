"""
Memory & Agent 边界测试 — get_recent, get_all, to_context truncation,
Agent _build_system_prompt, _execute_tool edge cases
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.memory import Memory, MemoryEntry
from nano_agent.agent import Agent
from nano_agent.tools import Tool, tool, clear_tools, get_tool, unregister_tool
from nano_agent.llm import LLM, MockBackend


class TestMemoryGetRecent:
    """Memory.get_recent 测试"""

    def test_get_recent_fewer_than_n(self):
        """条目少于 n"""
        m = Memory()
        m.add("a")
        m.add("b")
        recent = m.get_recent(5)
        assert len(recent) == 2

    def test_get_recent_exact_n(self):
        """条目恰好等于 n"""
        m = Memory()
        for i in range(3):
            m.add(f"entry_{i}")
        recent = m.get_recent(3)
        assert len(recent) == 3

    def test_get_recent_more_than_n(self):
        """条目多于 n"""
        m = Memory()
        for i in range(10):
            m.add(f"entry_{i}")
        recent = m.get_recent(3)
        assert len(recent) == 3
        assert recent[-1].content == "entry_9"

    def test_get_recent_empty(self):
        """空记忆"""
        m = Memory()
        assert m.get_recent(5) == []

    def test_get_recent_zero(self):
        """get_recent(0)"""
        m = Memory()
        m.add("a")
        assert m.get_recent(0) == []


class TestMemoryGetAll:
    """Memory.get_all 测试"""

    def test_get_all_returns_copy(self):
        """get_all 返回副本"""
        m = Memory()
        m.add("a")
        first = m.get_all()
        m.add("b")
        assert len(first) == 1  # 副本不受影响

    def test_get_all_empty(self):
        """空记忆返回空列表"""
        m = Memory()
        assert m.get_all() == []


class TestMemoryToContext:
    """Memory.to_context 测试"""

    def test_empty_context(self):
        """空记忆返回空字符串"""
        m = Memory()
        assert m.to_context() == ""

    def test_context_has_format(self):
        """上下文包含格式化内容"""
        m = Memory()
        m.add("test content")
        ctx = m.to_context()
        assert "记忆" in ctx
        assert "test content" in ctx

    def test_context_truncation(self):
        """超大 max_tokens 截断"""
        m = Memory()
        for i in range(50):
            m.add(f"这是一个很长的记忆条目编号 {i} " * 20)
        ctx = m.to_context(max_tokens=200)
        # Should be truncated
        assert len(ctx.encode('utf-8')) <= 500  # some overhead allowed

    def test_context_large_budget(self):
        """大 max_tokens 不截断"""
        m = Memory()
        m.add("short")
        ctx = m.to_context(max_tokens=10000)
        assert "short" in ctx


class TestMemoryLoadErrors:
    """Memory 文件加载错误处理"""

    def test_load_corrupted_json(self):
        """损坏的 JSON 文件不崩溃"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json !!!")
            path = f.name
        try:
            m = Memory(persistence_path=path)
            assert m.count() == 0  # gracefully empty
        finally:
            os.unlink(path)

    def test_load_empty_file(self):
        """空文件不崩溃"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            pass
            path = f.name
        try:
            m = Memory(persistence_path=path)
            assert m.count() == 0
        finally:
            os.unlink(path)


class TestMemoryEntryEquality:
    """MemoryEntry 额外测试"""

    def test_equality_different_content(self):
        """不同内容不相等"""
        a = MemoryEntry(content="a")
        b = MemoryEntry(content="b")
        assert a != b

    def test_equality_non_memoryentry(self):
        """与非 MemoryEntry 比较返回 False"""
        entry = MemoryEntry(content="test")
        assert entry != "test"


class TestAgentBuildSystemPrompt:
    """Agent._build_system_prompt 测试"""

    def test_basic_prompt(self):
        """基本提示词包含名字和指令"""
        agent = Agent(name="TestBot", instructions="做测试", verbose=False)
        prompt = agent._build_system_prompt()
        assert "TestBot" in prompt
        assert "做测试" in prompt

    def test_prompt_with_tools(self):
        """有工具时提示词包含工具"""
        clear_tools()
        t = Tool(name="calc", description="计算器", func=lambda: "ok", parameters={})
        agent = Agent(name="TestBot", instructions="test", verbose=False, tools=[t])
        prompt = agent._build_system_prompt()
        assert "calc" in prompt
        assert "计算器" in prompt

    def test_prompt_with_context(self):
        """有上下文时提示词包含上下文"""
        agent = Agent(name="TestBot", instructions="test", verbose=False)
        prompt = agent._build_system_prompt(context="额外信息123")
        assert "额外信息123" in prompt

    def test_prompt_with_memory(self):
        """有记忆时提示词包含记忆"""
        agent = Agent(name="TestBot", instructions="test", verbose=False)
        agent.memory.add("之前的记忆xyz")
        prompt = agent._build_system_prompt()
        assert "之前的记忆xyz" in prompt


class TestAgentExecuteTool:
    """Agent._execute_tool 边界测试"""

    def test_unknown_tool(self):
        """调用不存在的工具"""
        agent = Agent(name="t", instructions="t", verbose=False)
        result = agent._execute_tool({"name": "nonexistent", "arguments": "{}", "id": "1"})
        assert "错误" in result

    def test_invalid_json_arguments(self):
        """无效 JSON 参数"""
        clear_tools()
        t = Tool(name="echo", description="echo", func=lambda text: text, parameters={"text": {"type": "string"}})
        agent = Agent(name="t", instructions="t", verbose=False, tools=[t])
        result = agent._execute_tool({"name": "echo", "arguments": "not json{", "id": "1"})
        assert "错误" in result

    def test_tool_exception(self):
        """工具执行抛异常"""
        clear_tools()
        def bad_tool(**kwargs):
            raise ValueError("boom")
        t = Tool(name="bad", description="bad", func=bad_tool, parameters={})
        agent = Agent(name="t", instructions="t", verbose=False, tools=[t])
        result = agent._execute_tool({"name": "bad", "arguments": "{}", "id": "1"})
        assert "错误" in result
        assert "boom" in result


class TestAgentHistory:
    """Agent 对话历史额外测试"""

    def test_history_limit(self):
        """history 限制返回数量"""
        agent = Agent(name="t", instructions="t", verbose=False)
        for i in range(20):
            agent._conversation_history.append({"role": "user", "content": f"msg_{i}"})
        hist = agent.history(limit=5)
        assert len(hist) == 5
        assert hist[-1]["content"] == "msg_19"

    def test_turn_count(self):
        """turn_count 只计算 user 消息"""
        agent = Agent(name="t", instructions="t", verbose=False)
        agent._conversation_history = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
            {"role": "user", "content": "c"},
        ]
        assert agent.turn_count == 2


class TestToolsExtra:
    """Tools 模块额外测试"""

    def test_clear_tools(self):
        """clear_tools 清空注册表"""
        clear_tools()
        @tool
        def temp_tool(x: str) -> str:
            """temp"""
            return x
        assert get_tool("temp_tool") is not None
        clear_tools()
        assert get_tool("temp_tool") is None

    def test_get_tool_from_func(self):
        """get_tool_from_func 获取装饰器附加的工具"""
        clear_tools()
        @tool
        def my_func(x: str) -> str:
            """my func"""
            return x
        from nano_agent.tools import get_tool_from_func
        t = get_tool_from_func(my_func)
        assert t is not None
        assert t.name == "my_func"

    def test_get_tool_from_func_unregistered(self):
        """get_tool_from_func 回退到全局注册表"""
        clear_tools()
        def plain_func(x: str) -> str:
            """plain"""
            return x
        from nano_agent.tools import get_tool_from_func
        # Should return None since not registered
        result = get_tool_from_func(plain_func)
        assert result is None

    def test_unregister_returns_false_for_unknown(self):
        """注销不存在的工具返回 False"""
        clear_tools()
        assert unregister_tool("nonexistent") is False

    def test_tool_execute_with_args(self):
        """Tool.execute 传递参数"""
        def adder(a: int, b: int) -> int:
            return a + b
        t = Tool(name="add", description="加法", func=adder, parameters={"a": {"type": "integer"}, "b": {"type": "integer"}})
        assert t.execute(a=1, b=2) == 3

    def test_tool_validate_args_with_default(self):
        """有默认值的参数不报错"""
        def func(a: str, b: str = "default") -> str:
            return a + b
        t = Tool(name="f", description="f", func=func,
                 parameters={"a": {"type": "string"}, "b": {"type": "string", "default": "default"}})
        errors = t.validate_args(a="hi")
        assert errors == []
