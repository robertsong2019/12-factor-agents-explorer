"""F36-F37: Agent.conversation_stats() + Memory.tag_cloud()"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.agent import Agent
from nano_agent.memory import Memory
from nano_agent.llm import LLM


# --- F36: conversation_stats ---

def test_stats_empty_conversation():
    agent = Agent("test", "instructions", llm=LLM.mock())
    stats = agent.conversation_stats()
    assert stats["total_messages"] == 0
    assert stats["by_role"] == {}
    assert stats["avg_length"] == 0


def test_stats_after_run():
    agent = Agent("test", "you are helpful", llm=LLM.mock())
    agent.run("Hello")
    stats = agent.conversation_stats()
    assert stats["total_messages"] >= 2  # at least user + assistant
    assert "user" in stats["by_role"]
    assert "assistant" in stats["by_role"]


def test_stats_avg_length_positive():
    agent = Agent("test", "you are helpful", llm=LLM.mock())
    agent.run("This is a longer message to ensure avg length is positive")
    stats = agent.conversation_stats()
    assert stats["avg_length"] > 0


def test_stats_est_tokens():
    agent = Agent("test", "you are helpful", llm=LLM.mock())
    agent.run("Hello world")
    stats = agent.conversation_stats()
    assert stats["est_tokens"] >= 0


def test_stats_multiple_turns():
    agent = Agent("test", "you are helpful", llm=LLM.mock())
    agent.run("first message")
    agent.run("second message")
    stats = agent.conversation_stats()
    assert stats["by_role"]["user"] >= 2


def test_stats_after_reset():
    agent = Agent("test", "you are helpful", llm=LLM.mock())
    agent.run("Hello")
    agent.reset()
    stats = agent.conversation_stats()
    assert stats["total_messages"] == 0


def test_stats_tool_calls_key_present():
    agent = Agent("test", "you are helpful", llm=LLM.mock())
    agent.run("Hello")
    stats = agent.conversation_stats()
    assert "tool_calls" in stats
    assert isinstance(stats["tool_calls"], int)


# --- F37: tag_cloud ---

def test_tag_cloud_basic():
    m = Memory()
    m.add("a", tags=["python", "code"])
    m.add("b", tags=["python"])
    m.add("c", tags=["python", "test"])
    cloud = m.tag_cloud()
    assert "python" in cloud
    assert "code" in cloud
    assert "test" in cloud


def test_tag_cloud_weights_normalized():
    m = Memory()
    for _ in range(3):
        m.add("x", tags=["popular"])
    m.add("y", tags=["rare"])
    cloud = m.tag_cloud()
    # Most frequent tag should have weight 1.0
    assert cloud["popular"] == 1.0
    # Less frequent proportional
    assert cloud["rare"] < 1.0
    assert cloud["rare"] > 0


def test_tag_cloud_empty():
    m = Memory()
    assert m.tag_cloud() == {}


def test_tag_cloud_no_tags():
    m = Memory()
    m.add("no tags")
    assert m.tag_cloud() == {}


def test_tag_cloud_min_count():
    m = Memory()
    m.add("a", tags=["rare"])
    m.add("b", tags=["common"])
    m.add("c", tags=["common"])
    m.add("d", tags=["common"])
    cloud = m.tag_cloud(min_count=2)
    assert "common" in cloud
    assert "rare" not in cloud


def test_tag_cloud_max_tags():
    m = Memory()
    for i in range(10):
        m.add(f"entry{i}", tags=[f"tag{i}"])
    cloud = m.tag_cloud(max_tags=3)
    assert len(cloud) == 3


def test_tag_cloud_sorted_by_frequency():
    m = Memory()
    for _ in range(5):
        m.add("x", tags=["frequent"])
    for _ in range(2):
        m.add("y", tags=["medium"])
    m.add("z", tags=["rare"])
    cloud = m.tag_cloud()
    tags = list(cloud.keys())
    assert tags[0] == "frequent"
    assert tags[-1] == "rare"


def test_tag_cloud_weight_range():
    m = Memory()
    for _ in range(10):
        m.add("x", tags=["a"])
    m.add("y", tags=["b"])
    cloud = m.tag_cloud()
    for w in cloud.values():
        assert 0.0 < w <= 1.0
