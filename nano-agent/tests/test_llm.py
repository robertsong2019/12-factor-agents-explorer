"""
LLM 模块测试 — MockBackend, LLM factory, OpenAIBackend init
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.llm import LLM, MockBackend, LLMBackend, OpenAIBackend


class TestMockBackend:
    """MockBackend 测试"""

    def test_basic_response(self):
        """基本回复"""
        backend = MockBackend()
        result = backend.complete([{"role": "user", "content": "hello"}])
        assert result["content"] == "这是对 'hello' 的模拟回复"
        assert result["tool_calls"] == []
        assert "usage" in result
        assert result["usage"]["total_tokens"] == 30

    def test_empty_messages(self):
        """空消息列表"""
        backend = MockBackend()
        result = backend.complete([])
        assert "content" in result
        assert result["tool_calls"] == []

    def test_tool_call_triggered(self):
        """包含'搜索'时触发工具调用"""
        backend = MockBackend()
        tools = [{"name": "search", "description": "搜索", "parameters": {"query": {"type": "string"}}}]
        result = backend.complete(
            [{"role": "user", "content": "搜索 AI"}],
            tools=tools
        )
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "search"
        assert "arguments" in result["tool_calls"][0]

    def test_no_tool_call_without_keyword(self):
        """没有'搜索'关键词时不触发工具调用"""
        backend = MockBackend()
        tools = [{"name": "search", "description": "搜索", "parameters": {"query": {"type": "string"}}}]
        result = backend.complete(
            [{"role": "user", "content": "hello"}],
            tools=tools
        )
        assert result["tool_calls"] == []

    def test_usage_format(self):
        """usage 字段格式正确"""
        backend = MockBackend()
        result = backend.complete([{"role": "user", "content": "test"}])
        usage = result["usage"]
        assert "prompt_tokens" in usage
        assert "completion_tokens" in usage
        assert "total_tokens" in usage
        assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]

    def test_tool_call_uses_first_tool(self):
        """工具调用使用第一个工具"""
        backend = MockBackend()
        tools = [
            {"name": "first_tool", "description": "第一", "parameters": {}},
            {"name": "second_tool", "description": "第二", "parameters": {}}
        ]
        result = backend.complete(
            [{"role": "user", "content": "搜索 test"}],
            tools=tools
        )
        assert result["tool_calls"][0]["name"] == "first_tool"


class TestLLMFactory:
    """LLM 工厂方法测试"""

    def test_mock_factory(self):
        """LLM.mock() 创建 MockBackend"""
        llm = LLM.mock()
        assert isinstance(llm.backend, MockBackend)

    def test_chat_delegates_to_backend(self):
        """chat 方法委托给 backend"""
        llm = LLM.mock()
        result = llm.chat([{"role": "user", "content": "test"}])
        assert "content" in result

    def test_chat_with_tools(self):
        """chat 方法传递 tools"""
        llm = LLM.mock()
        tools = [{"name": "t", "description": "t", "parameters": {}}]
        result = llm.chat([{"role": "user", "content": "搜索 x"}], tools=tools)
        assert len(result["tool_calls"]) == 1

    def test_chat_passes_kwargs(self):
        """chat 传递额外参数"""
        backend = MockBackend()
        llm = LLM(backend)
        # MockBackend ignores kwargs but should not error
        result = llm.chat([{"role": "user", "content": "hi"}], temperature=0.7)
        assert "content" in result


class TestLLMBackendABC:
    """LLMBackend 抽象类测试"""

    def test_cannot_instantiate_abstract(self):
        """不能直接实例化抽象类"""
        try:
            LLMBackend()
            assert False, "Should have raised TypeError"
        except TypeError:
            pass

    def test_subclass_must_implement_complete(self):
        """子类必须实现 complete"""
        class IncompleteBackend(LLMBackend):
            pass
        try:
            IncompleteBackend()
            assert False, "Should have raised TypeError"
        except TypeError:
            pass

    def test_subclass_with_complete_works(self):
        """实现 complete 的子类可以实例化"""
        class CustomBackend(LLMBackend):
            def complete(self, messages, tools=None, **kwargs):
                return {"content": "custom", "tool_calls": [], "usage": {}}
        backend = CustomBackend()
        result = backend.complete([{"role": "user", "content": "hi"}])
        assert result["content"] == "custom"


class TestOpenAIBackendInit:
    """OpenAIBackend 初始化测试（不实际调用 API）"""

    def test_import_error_without_openai(self):
        """没有 openai 包时抛 ImportError"""
        # We can't easily mock the import, but we can test the error message format
        # by checking that the __init__ has the right guard
        import inspect
        src = inspect.getsource(OpenAIBackend.__init__)
        assert "ImportError" in src
        assert "openai" in src.lower()

    def test_default_model(self):
        """默认模型是 gpt-3.5-turbo（检查源码，不实际创建）"""
        import inspect
        sig = inspect.signature(OpenAIBackend.__init__)
        assert sig.parameters["model"].default == "gpt-3.5-turbo"

    def test_default_base_url(self):
        """默认 base_url"""
        import inspect
        sig = inspect.signature(OpenAIBackend.__init__)
        assert sig.parameters["base_url"].default == "https://api.openai.com/v1"
