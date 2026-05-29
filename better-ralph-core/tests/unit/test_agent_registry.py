"""Tests for core/agent_registry.py — Agent dataclass and AgentRegistry."""

import pytest
from core.agent_registry import Agent, AgentRegistry


class TestAgent:
    def test_default_agent(self):
        a = Agent()
        assert a.name == "default"
        assert a.capabilities == []

    def test_custom_agent(self):
        a = Agent(name="coder", capabilities=["code", "review"])
        assert a.name == "coder"
        assert len(a.capabilities) == 2

    def test_agent_capabilities_independent(self):
        """Each Agent gets its own list (factory default)."""
        a1 = Agent()
        a2 = Agent()
        a1.capabilities.append("x")
        assert a2.capabilities == []


class TestAgentRegistry:
    def test_empty_registry(self):
        reg = AgentRegistry()
        assert reg.agents == []

    def test_select_agent_returns_default(self):
        reg = AgentRegistry()
        agent = reg.select_agent("some story")
        assert isinstance(agent, Agent)
        assert agent.name == "default"

    def test_select_agent_with_none_story(self):
        reg = AgentRegistry()
        agent = reg.select_agent(None)
        assert isinstance(agent, Agent)

    def test_agents_mutable(self):
        reg = AgentRegistry()
        reg.agents.append(Agent(name="a1"))
        assert len(reg.agents) == 1
        assert reg.agents[0].name == "a1"
