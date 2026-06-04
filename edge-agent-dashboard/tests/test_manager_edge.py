"""Edge case tests for AgentManager — error paths, logging, config loading"""

import asyncio
import json
import os
import pytest

from edge_agent_dashboard.manager import (
    AgentConfig, AgentInfo, AgentManager, AgentState,
)


@pytest.fixture
def config_dir(tmp_path):
    return str(tmp_path / "agents")


@pytest.fixture
def manager(config_dir):
    return AgentManager(config_dir=config_dir)


class TestConfigLoading:
    def test_load_bad_json_skips(self, config_dir):
        os.makedirs(config_dir, exist_ok=True)
        with open(os.path.join(config_dir, "bad.json"), "w") as f:
            f.write("NOT JSON !!!")
        m = AgentManager(config_dir=config_dir)
        assert "bad" not in m.agents

    def test_load_missing_fields_skips(self, config_dir):
        os.makedirs(config_dir, exist_ok=True)
        with open(os.path.join(config_dir, "incomplete.json"), "w") as f:
            json.dump({"id": "x"}, f)  # missing name, command
        m = AgentManager(config_dir=config_dir)
        assert "incomplete" not in m.agents

    def test_load_multiple_configs(self, config_dir):
        os.makedirs(config_dir, exist_ok=True)
        for name in ("a", "b", "c"):
            cfg = {"id": name, "name": name.upper(), "command": "true"}
            with open(os.path.join(config_dir, f"{name}.json"), "w") as f:
                json.dump(cfg, f)
        m = AgentManager(config_dir=config_dir)
        assert len(m.agents) == 3
        assert set(m.agents.keys()) == {"a", "b", "c"}

    def test_ignores_non_json_files(self, config_dir):
        os.makedirs(config_dir, exist_ok=True)
        with open(os.path.join(config_dir, "readme.txt"), "w") as f:
            f.write("not a config")
        with open(os.path.join(config_dir, "agent.json"), "w") as f:
            json.dump({"id": "agent", "name": "A", "command": "ls"}, f)
        m = AgentManager(config_dir=config_dir)
        assert len(m.agents) == 1


class TestStopAgentEdgeCases:
    @pytest.mark.asyncio
    async def test_stop_already_stopped(self, manager):
        config = AgentConfig(id="a1", name="A1", command="echo hi")
        await manager.create_agent(config)
        # agent is STOPPED, stop should return True
        result = await manager.stop_agent("a1")
        assert result is True
        agent = await manager.get_agent("a1")
        assert agent.state == AgentState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_after_error(self, manager):
        config = AgentConfig(id="err", name="Err", command="false")
        await manager.create_agent(config)
        manager.agents["err"].state = AgentState.ERROR
        result = await manager.stop_agent("err")
        assert result is True


class TestGetAgentLogs:
    @pytest.mark.asyncio
    async def test_get_logs_partial(self, manager):
        config = AgentConfig(id="log-agent", name="Log", command="echo hi")
        await manager.create_agent(config)
        manager.log_buffers["log-agent"] = ["line1", "line2", "line3", "line4", "line5"]
        logs = await manager.get_agent_logs("log-agent", lines=3)
        assert logs == ["line3", "line4", "line5"]

    @pytest.mark.asyncio
    async def test_get_logs_more_than_available(self, manager):
        config = AgentConfig(id="log2", name="L2", command="echo hi")
        await manager.create_agent(config)
        manager.log_buffers["log2"] = ["a", "b"]
        logs = await manager.get_agent_logs("log2", lines=100)
        assert logs == ["a", "b"]


class TestUpdateConfigEdgeCases:
    @pytest.mark.asyncio
    async def test_update_config_persists(self, manager, config_dir):
        config = AgentConfig(id="u1", name="Original", command="echo hi")
        await manager.create_agent(config)
        new_cfg = AgentConfig(id="u1", name="Renamed", command="echo new")
        await manager.update_agent_config("u1", new_cfg)
        path = os.path.join(config_dir, "u1.json")
        with open(path) as f:
            data = json.load(f)
        assert data["name"] == "Renamed"
        assert data["command"] == "echo new"

    @pytest.mark.asyncio
    async def test_update_config_with_env_vars(self, manager):
        config = AgentConfig(id="u2", name="U2", command="echo hi")
        await manager.create_agent(config)
        new_cfg = AgentConfig(id="u2", name="U2", command="echo hi", env_vars={"FOO": "BAR"})
        result = await manager.update_agent_config("u2", new_cfg)
        assert result.config.env_vars == {"FOO": "BAR"}


class TestCreateAgentAutoStart:
    @pytest.mark.asyncio
    async def test_create_auto_start_false(self, manager):
        config = AgentConfig(id="auto1", name="A1", command="echo hi", auto_start=False)
        agent = await manager.create_agent(config)
        assert agent.state == AgentState.STOPPED

    @pytest.mark.asyncio
    async def test_create_auto_start_true(self, manager):
        config = AgentConfig(id="auto2", name="A2", command="echo hi", auto_start=True)
        agent = await manager.create_agent(config)
        # auto_start triggers start_agent
        assert agent.state in (AgentState.STARTING, AgentState.RUNNING)
        await manager.stop_agent("auto2")
