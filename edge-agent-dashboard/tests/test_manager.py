"""Unit tests for AgentManager"""

import asyncio
import json
import os
import pytest
import tempfile

from edge_agent_dashboard.manager import (
    AgentConfig, AgentInfo, AgentManager, AgentState,
)


@pytest.fixture
def config_dir(tmp_path):
    return str(tmp_path / "agents")


@pytest.fixture
def manager(config_dir):
    return AgentManager(config_dir=config_dir)


@pytest.fixture
def sample_config():
    return AgentConfig(
        id="test-agent",
        name="Test Agent",
        command="echo hello",
        working_dir="/tmp",
    )


class TestAgentConfig:
    def test_defaults(self):
        c = AgentConfig(id="a", name="b", command="c")
        assert c.auto_start is False
        assert c.env_vars is None
        assert c.working_dir is None

    def test_with_env(self):
        c = AgentConfig(id="a", name="b", command="c", env_vars={"K": "V"})
        assert c.env_vars == {"K": "V"}


class TestAgentManagerInit:
    def test_creates_config_dir(self, tmp_path):
        d = str(tmp_path / "new_dir")
        AgentManager(config_dir=d)
        assert os.path.isdir(d)

    def test_starts_empty(self, manager):
        assert len(manager.agents) == 0

    def test_loads_existing_config(self, config_dir):
        os.makedirs(config_dir, exist_ok=True)
        cfg = {"id": "x", "name": "X", "command": "true"}
        with open(os.path.join(config_dir, "x.json"), "w") as f:
            json.dump(cfg, f)
        m = AgentManager(config_dir=config_dir)
        assert "x" in m.agents
        assert m.agents["x"].state == AgentState.STOPPED


class TestAgentManagerCRUD:
    @pytest.mark.asyncio
    async def test_create_agent(self, manager, sample_config):
        agent = await manager.create_agent(sample_config)
        assert agent.id == "test-agent"
        assert agent.state == AgentState.STOPPED
        assert "test-agent" in manager.agents

    @pytest.mark.asyncio
    async def test_create_agent_persists_config(self, manager, sample_config, config_dir):
        await manager.create_agent(sample_config)
        path = os.path.join(config_dir, "test-agent.json")
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data["id"] == "test-agent"

    @pytest.mark.asyncio
    async def test_get_agents(self, manager, sample_config):
        await manager.create_agent(sample_config)
        agents = await manager.get_agents()
        assert len(agents) == 1
        assert agents[0].id == "test-agent"

    @pytest.mark.asyncio
    async def test_get_agent(self, manager, sample_config):
        await manager.create_agent(sample_config)
        agent = await manager.get_agent("test-agent")
        assert agent is not None
        assert agent.name == "Test Agent"

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, manager):
        assert await manager.get_agent("nonexistent") is None

    @pytest.mark.asyncio
    async def test_delete_agent(self, manager, sample_config):
        await manager.create_agent(sample_config)
        assert await manager.delete_agent("test-agent") is True
        assert "test-agent" not in manager.agents
        assert "test-agent" not in manager.log_buffers

    @pytest.mark.asyncio
    async def test_delete_agent_not_found(self, manager):
        assert await manager.delete_agent("nope") is False

    @pytest.mark.asyncio
    async def test_delete_agent_removes_config_file(self, manager, sample_config, config_dir):
        await manager.create_agent(sample_config)
        path = os.path.join(config_dir, "test-agent.json")
        assert os.path.exists(path)
        await manager.delete_agent("test-agent")
        assert not os.path.exists(path)

    @pytest.mark.asyncio
    async def test_get_agent_logs_empty(self, manager, sample_config):
        await manager.create_agent(sample_config)
        logs = await manager.get_agent_logs("test-agent")
        assert logs == []

    @pytest.mark.asyncio
    async def test_get_agent_logs_not_found(self, manager):
        logs = await manager.get_agent_logs("nope")
        assert logs == []


class TestAgentManagerStartStop:
    @pytest.mark.asyncio
    async def test_start_agent_not_found(self, manager):
        assert await manager.start_agent("nope") is False

    @pytest.mark.asyncio
    async def test_start_agent(self, manager, sample_config):
        await manager.create_agent(sample_config)
        result = await manager.start_agent("test-agent")
        assert result is True
        agent = await manager.get_agent("test-agent")
        assert agent.state == AgentState.RUNNING
        assert agent.pid is not None
        # cleanup
        await manager.stop_agent("test-agent")

    @pytest.mark.asyncio
    async def test_stop_agent_not_found(self, manager):
        assert await manager.stop_agent("nope") is False

    @pytest.mark.asyncio
    async def test_stop_agent(self, manager, sample_config):
        await manager.create_agent(sample_config)
        await manager.start_agent("test-agent")
        result = await manager.stop_agent("test-agent")
        assert result is True
        agent = await manager.get_agent("test-agent")
        assert agent.state == AgentState.STOPPED
        assert agent.pid is None

    @pytest.mark.asyncio
    async def test_start_already_running(self, manager, sample_config):
        await manager.create_agent(sample_config)
        await manager.start_agent("test-agent")
        result = await manager.start_agent("test-agent")
        assert result is True
        await manager.stop_agent("test-agent")

    @pytest.mark.asyncio
    async def test_restart_agent(self, manager, sample_config):
        await manager.create_agent(sample_config)
        await manager.start_agent("test-agent")
        result = await manager.restart_agent("test-agent")
        assert result is True
        await manager.stop_agent("test-agent")


class TestAgentManagerUpdate:
    @pytest.mark.asyncio
    async def test_update_config(self, manager, sample_config):
        await manager.create_agent(sample_config)
        new_config = AgentConfig(
            id="test-agent", name="Updated", command="echo updated"
        )
        result = await manager.update_agent_config("test-agent", new_config)
        assert result is not None
        assert result.name == "Updated"

    @pytest.mark.asyncio
    async def test_update_config_not_found(self, manager):
        c = AgentConfig(id="x", name="x", command="x")
        assert await manager.update_agent_config("nope", c) is None
