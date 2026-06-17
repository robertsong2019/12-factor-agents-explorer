"""
边界情况与集成测试 — 2026-06-18

覆盖之前未测试的代码路径：
- Memory 持久化完整 round-trip（save → load → verify）
- Memory.search 带 tags 但 query 无匹配
- Memory.add 带 metadata 和 tags 的完整性
- Agent._execute_tool 无效 JSON 参数
- Agent._execute_tool 未知工具
- Agent verbose=False 无输出
- Agent._build_system_prompt 带 context
- Tool.execute 直接调用
- MemoryEntry.to_dict 带 tags 和不带 tags
- Memory persistence 文件不存在时的 _load
- Memory 搜索 tag 子集匹配
- Agent 多轮对话 history 累积
"""

import sys
import os
import json
import tempfile
import io
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.agent import Agent
from nano_agent.llm import LLM, MockBackend
from nano_agent.memory import Memory, MemoryEntry
from nano_agent.tools import Tool, tool, clear_tools, get_tool, list_tools


class TestMemoryPersistenceRoundTrip:
    """Memory 持久化完整往返测试"""

    def test_save_load_round_trip(self, tmp_path):
        """保存后重新加载，数据一致"""
        db_path = tmp_path / "mem.json"
        m1 = Memory(persistence_path=str(db_path))
        m1.add("hello world", metadata={"k": "v"}, tags=["a", "b"])
        m1.add("second entry", metadata={"num": 1})

        # 重新加载
        m2 = Memory(persistence_path=str(db_path))
        assert m2.count() == 2
        entries = m2.get_all()
        assert entries[0].content == "hello world"
        assert entries[0].metadata == {"k": "v"}
        assert entries[1].content == "second entry"

    def test_load_nonexistent_file(self, tmp_path):
        """加载不存在的文件不报错"""
        m = Memory(persistence_path=str(tmp_path / "noexist.json"))
        assert m.count() == 0

    def test_save_creates_parent_dirs(self, tmp_path):
        """保存时自动创建父目录"""
        nested = tmp_path / "a" / "b" / "c" / "mem.json"
        m = Memory(persistence_path=str(nested))
        m.add("test")
        assert nested.exists()

    def test_clear_persists_to_file(self, tmp_path):
        """clear 后文件也被更新（清空）"""
        db_path = tmp_path / "mem.json"
        m = Memory(persistence_path=str(db_path))
        m.add("entry1")
        m.add("entry2")
        assert db_path.exists()

        m.clear()
        m2 = Memory(persistence_path=str(db_path))
        assert m2.count() == 0

    def test_remove_persists_to_file(self, tmp_path):
        """remove 后持久化"""
        db_path = tmp_path / "mem.json"
        m = Memory(persistence_path=str(db_path))
        m.add("keep me")
        m.add("delete me")
        m.remove(1)

        m2 = Memory(persistence_path=str(db_path))
        assert m2.count() == 1
        assert m2.get_all()[0].content == "keep me"


class TestMemorySearchTags:
    """Memory 搜索标签边界测试"""

    def test_search_tags_no_query_match(self):
        """tag 匹配但 query 不匹配 → 空结果"""
        m = Memory()
        m.add("hello world", tags=["python"])
        results = m.search("javascript", tags=["python"])
        assert results == []

    def test_search_tags_partial_overlap(self):
        """tag 部分重叠匹配（交集）"""
        m = Memory()
        m.add("learn python", tags=["python", "ai"])
        m.add("learn rust", tags=["rust", "systems"])
        m.add("learn go", tags=["go", "ai"])

        results = m.search("learn", tags=["ai"])
        assert len(results) == 2
        contents = [r.content for r in results]
        assert "learn python" in contents
        assert "learn go" in contents

    def test_search_tags_no_tags_in_entries(self):
        """过滤 tag 但条目没有 tag → 无匹配"""
        m = Memory()
        m.add("hello")  # no tags
        results = m.search("hello", tags=["anything"])
        assert results == []

    def test_search_empty_string_with_tags(self):
        """空 query + tag 过滤"""
        m = Memory()
        m.add("data science", tags=["data"])
        m.add("more data", tags=["data"])
        results = m.search("", tags=["data"])
        assert len(results) == 2


class TestMemoryEntryDict:
    """MemoryEntry.to_dict 边界测试"""

    def test_to_dict_without_tags(self):
        """无 tags 时不包含 tags 键"""
        entry = MemoryEntry(content="test")
        d = entry.to_dict()
        assert "tags" not in d
        assert d["content"] == "test"
        assert "timestamp" in d
        assert d["metadata"] == {}

    def test_to_dict_with_tags(self):
        """有 tags 时包含 tags 键"""
        entry = MemoryEntry(content="test", tags=["a", "b"])
        d = entry.to_dict()
        assert d["tags"] == ["a", "b"]

    def test_to_dict_with_metadata(self):
        """metadata 正确序列化"""
        entry = MemoryEntry(content="test", metadata={"key": "val", "num": 42})
        d = entry.to_dict()
        assert d["metadata"]["key"] == "val"
        assert d["metadata"]["num"] == 42


class TestToolExecute:
    """Tool.execute 直接调用测试"""

    def test_execute_direct_call(self):
        """直接调用 execute"""
        def adder(x: int, y: int) -> int:
            """Add two numbers"""
            return x + y
        t = Tool(name="add", description="加法", func=adder, parameters={})
        result = t.execute(x=1, y=2)
        assert result == 3

    def test_execute_with_defaults(self):
        """带默认参数的 execute"""
        def greeter(name: str, greeting: str = "hi") -> str:
            """Greet"""
            return f"{greeting} {name}"
        t = Tool(name="greet", description="问候", func=greeter, parameters={})
        assert t.execute(name="world") == "hi world"
        assert t.execute(name="world", greeting="hello") == "hello world"


class TestAgentExecuteToolEdgeCases:
    """Agent._execute_tool 边界测试"""

    def test_invalid_json_arguments(self):
        """无效 JSON 参数返回错误"""
        llm = LLM.mock()
        agent = Agent("test", "test", llm=llm, verbose=False)
        result = agent._execute_tool({
            "id": "1",
            "name": "nonexistent",
            "arguments": "{invalid json}"
        })
        assert "错误" in result

    def test_unknown_tool(self):
        """调用不存在的工具"""
        llm = LLM.mock()
        agent = Agent("test", "test", llm=llm, verbose=False)
        result = agent._execute_tool({
            "id": "1",
            "name": "ghost_tool",
            "arguments": "{}"
        })
        assert "不存在" in result

    def test_tool_execution_error_handled(self):
        """工具执行抛异常时被捕获"""
        def boom(**kwargs):
            raise ValueError("boom!")

        t = Tool(name="boom", description="爆炸", func=boom, parameters={})
        llm = LLM.mock()
        agent = Agent("test", "test", llm=llm, tools=[t], verbose=False)
        result = agent._execute_tool({
            "id": "1",
            "name": "boom",
            "arguments": "{}"
        })
        assert "错误" in result
        assert "boom" in result


class TestAgentVerboseAndContext:
    """Agent verbose 和 context 测试"""

    def test_verbose_false_no_stdout(self, capsys):
        """verbose=False 时不输出到 stdout"""
        llm = LLM.mock()
        agent = Agent("quiet", "be quiet", llm=llm, verbose=False)
        agent.run("hello")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_verbose_true_outputs(self, capsys):
        """verbose=True 时有输出"""
        llm = LLM.mock()
        agent = Agent("loud", "be loud", llm=llm, verbose=True)
        agent.run("hello")
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_build_system_prompt_with_context(self):
        """带 context 的系统提示词"""
        llm = LLM.mock()
        agent = Agent("ctx", "do things", llm=llm, verbose=False)
        prompt = agent._build_system_prompt("extra context here")
        assert "extra context here" in prompt
        assert "do things" in prompt

    def test_build_system_prompt_without_context(self):
        """不带 context 的系统提示词"""
        llm = LLM.mock()
        agent = Agent("noctx", "do things", llm=llm, verbose=False)
        prompt = agent._build_system_prompt(None)
        assert "do things" in prompt

    def test_build_system_prompt_with_tools(self):
        """带 tools 的系统提示词"""
        def searcher(query: str) -> str:
            """搜索"""
            return query
        t = Tool(name="search", description="搜索工具", func=searcher, parameters={})
        llm = LLM.mock()
        agent = Agent("toolagent", "use tools", llm=llm, tools=[t], verbose=False)
        prompt = agent._build_system_prompt()
        assert "search" in prompt
        assert "搜索工具" in prompt


class TestAgentConversationAccumulation:
    """Agent 多轮对话累积测试"""

    def test_history_grows_with_turns(self):
        """多轮对话后 history 增长"""
        llm = LLM.mock()
        agent = Agent("chat", "chat", llm=llm, verbose=False)
        assert len(agent.history()) == 0

        agent.run("hello")
        assert len(agent.history()) == 2  # user + assistant

        agent.run("world")
        assert len(agent.history()) == 4

    def test_history_limit(self):
        """history(limit) 返回最近 N 条"""
        llm = LLM.mock()
        agent = Agent("chat", "chat", llm=llm, verbose=False)
        agent.run("first")
        agent.run("second")
        agent.run("third")

        recent = agent.history(limit=2)
        assert len(recent) == 2
        assert recent[-1]["content"] == "这是对 'third' 的模拟回复"

    def test_reset_clears_history(self):
        """reset 清空对话历史"""
        llm = LLM.mock()
        agent = Agent("chat", "chat", llm=llm, verbose=False)
        agent.run("hello")
        assert len(agent.history()) > 0

        agent.reset()
        assert len(agent.history()) == 0

    def test_memory_grows_across_turns(self):
        """多轮对话后 memory 增长"""
        llm = LLM.mock()
        agent = Agent("mem", "chat", llm=llm, verbose=False)
        assert agent.memory.count() == 0

        agent.run("question 1")
        assert agent.memory.count() == 1

        agent.run("question 2")
        assert agent.memory.count() == 2


class TestMemoryToContextEdgeCases:
    """Memory.to_context 边界测试"""

    def test_context_with_single_entry(self):
        """单条记忆的 context"""
        m = Memory()
        m.add("only entry")
        ctx = m.to_context()
        assert "only entry" in ctx
        assert "记忆" in ctx

    def test_context_zero_max_tokens(self):
        """max_tokens=0 → 只有标题"""
        m = Memory()
        m.add("entry 1")
        m.add("entry 2")
        ctx = m.to_context(max_tokens=0)
        # 极小 budget → 标题存在但无条目
        assert "记忆" in ctx

    def test_context_preserves_timestamp_format(self):
        """context 中包含时间戳格式"""
        m = Memory()
        m.add("timed entry")
        ctx = m.to_context()
        # 应该包含 YYYY-MM-DD HH:MM 格式的时间戳
        import re
        assert re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', ctx)
