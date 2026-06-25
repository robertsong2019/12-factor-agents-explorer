"""
Coverage gap tests — 2026-06-26
Targets: /api/metrics/history, manager._collect_logs edge cases,
WebSocketBroadcaster log updates, Memory.to_context truncation
"""

import asyncio
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from edge_agent_dashboard.main import app
from edge_agent_dashboard.manager import AgentManager, AgentConfig, AgentInfo, AgentState
from edge_agent_dashboard.monitor import ResourceMonitor, ResourceMetrics
from edge_agent_dashboard.websocket import ConnectionManager, WebSocketBroadcaster


# ─── /api/metrics/history ───────────────────────────────────────────

@pytest.fixture
def mock_deps():
    mock_manager = MagicMock()
    mock_monitor = MagicMock()
    mock_conn = MagicMock()
    mock_broadcaster = MagicMock()
    mock_manager.get_agents = AsyncMock(return_value=[])
    mock_manager.get_agent = AsyncMock(return_value=None)
    mock_manager.create_agent = AsyncMock(return_value=None)
    mock_manager.update_agent_config = AsyncMock(return_value=None)
    mock_manager.delete_agent = AsyncMock(return_value=False)
    mock_manager.start_agent = AsyncMock(return_value=False)
    mock_manager.stop_agent = AsyncMock(return_value=False)
    mock_manager.restart_agent = AsyncMock(return_value=False)
    mock_manager.get_agent_logs = AsyncMock(return_value=[])
    mock_monitor.get_current_metrics = MagicMock(return_value=None)
    mock_monitor.get_history_dict = MagicMock(return_value=[])
    with patch("edge_agent_dashboard.main.agent_manager", mock_manager), \
         patch("edge_agent_dashboard.main.resource_monitor", mock_monitor), \
         patch("edge_agent_dashboard.main.connection_manager", mock_conn), \
         patch("edge_agent_dashboard.main.broadcaster", mock_broadcaster):
        yield mock_manager, mock_monitor, mock_conn, mock_broadcaster


@pytest.fixture
def client(mock_deps):
    return TestClient(app, raise_server_exceptions=False)


class TestMetricsHistory:
    def test_empty_history(self, client, mock_deps):
        mock_mon = mock_deps[1]
        mock_mon.get_history_dict = MagicMock(return_value={
            "timestamps": [], "cpu": [], "memory": [],
            "network_sent": [], "network_recv": []
        })
        resp = client.get("/api/metrics/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["timestamps"] == []

    def test_with_data(self, client, mock_deps):
        mock_mon = mock_deps[1]
        mock_mon.get_history_dict = MagicMock(return_value={
            "timestamps": [1000, 2000],
            "cpu": [30.0, 50.0],
            "memory": [40.0, 60.0],
            "network_sent": [1.0, 2.0],
            "network_recv": [3.0, 4.0],
        })
        resp = client.get("/api/metrics/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["cpu"]) == 2
        assert data["cpu"][1] == 50.0

    def test_custom_seconds_param(self, client, mock_deps):
        mock_mon = mock_deps[1]
        mock_mon.get_history_dict = MagicMock(return_value={"timestamps": [], "cpu": [], "memory": [], "network_sent": [], "network_recv": []})
        resp = client.get("/api/metrics/history?seconds=120")
        assert resp.status_code == 200
        mock_mon.get_history_dict.assert_called_once_with(120)


# ─── WebSocketBroadcaster._broadcast_log_updates ────────────────────

class TestBroadcastLogUpdates:
    @pytest.mark.asyncio
    async def test_log_update_sends_new_lines(self):
        mock_cm = AsyncMock()
        mock_mgr = AsyncMock()
        mock_mon = MagicMock()
        mock_mon.get_current_metrics = MagicMock(return_value=None)

        agent = MagicMock()
        agent.id = "a1"
        agent.name = "Agent1"
        agent.state = "running"
        agent.pid = 123
        agent.uptime = 10.0
        agent.last_error = None
        mock_mgr.get_agents = AsyncMock(return_value=[agent])
        mock_mgr.get_agent_logs = AsyncMock(return_value=["line1", "line2", "line3"])

        bcast = WebSocketBroadcaster(mock_cm, mock_mgr, mock_mon)
        await bcast._broadcast_log_updates()

        mock_cm.broadcast.assert_called_once_with({
            "type": "log_update",
            "data": {"agent_id": "a1", "logs": ["line1", "line2", "line3"]}
        })

    @pytest.mark.asyncio
    async def test_log_update_incremental(self):
        mock_cm = AsyncMock()
        mock_mgr = AsyncMock()
        mock_mon = MagicMock()

        agent = MagicMock()
        agent.id = "a1"
        agent.name = "Agent1"
        agent.state = "running"
        agent.pid = 1
        agent.uptime = 5.0
        agent.last_error = None
        mock_mgr.get_agents = AsyncMock(return_value=[agent])
        mock_mgr.get_agent_logs = AsyncMock(return_value=["l1", "l2", "l3", "l4", "l5"])

        bcast = WebSocketBroadcaster(mock_cm, mock_mgr, mock_mon)
        bcast._last_log_lines["a1"] = 2  # already sent 2 lines

        await bcast._broadcast_log_updates()

        mock_cm.broadcast.assert_called_once_with({
            "type": "log_update",
            "data": {"agent_id": "a1", "logs": ["l3", "l4", "l5"]}
        })

    @pytest.mark.asyncio
    async def test_log_update_no_new_lines(self):
        mock_cm = AsyncMock()
        mock_mgr = AsyncMock()
        mock_mon = MagicMock()

        agent = MagicMock()
        agent.id = "a1"
        agent.name = "A"
        agent.state = "running"
        agent.pid = 1
        agent.uptime = 1.0
        agent.last_error = None
        mock_mgr.get_agents = AsyncMock(return_value=[agent])
        mock_mgr.get_agent_logs = AsyncMock(return_value=["l1", "l2"])

        bcast = WebSocketBroadcaster(mock_cm, mock_mgr, mock_mon)
        bcast._last_log_lines["a1"] = 2  # all already sent

        await bcast._broadcast_log_updates()
        mock_cm.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_update_skips_stopped_agent(self):
        mock_cm = AsyncMock()
        mock_mgr = AsyncMock()
        mock_mon = MagicMock()

        agent = MagicMock()
        agent.id = "a1"
        agent.state = "stopped"
        mock_mgr.get_agents = AsyncMock(return_value=[agent])

        bcast = WebSocketBroadcaster(mock_cm, mock_mgr, mock_mon)
        await bcast._broadcast_log_updates()
        mock_cm.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_update_skips_starting_agent(self):
        mock_cm = AsyncMock()
        mock_mgr = AsyncMock()
        mock_mon = MagicMock()

        agent = MagicMock()
        agent.id = "a1"
        agent.state = "starting"
        mock_mgr.get_agents = AsyncMock(return_value=[agent])

        bcast = WebSocketBroadcaster(mock_cm, mock_mgr, mock_mon)
        await bcast._broadcast_log_updates()
        mock_cm.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_update_multi_agent(self):
        mock_cm = AsyncMock()
        mock_mgr = AsyncMock()
        mock_mon = MagicMock()

        a1 = MagicMock()
        a1.id = "a1"
        a1.name = "A1"
        a1.state = "running"
        a1.pid = 1
        a1.uptime = 1.0
        a1.last_error = None

        a2 = MagicMock()
        a2.id = "a2"
        a2.name = "A2"
        a2.state = "running"
        a2.pid = 2
        a2.uptime = 2.0
        a2.last_error = None

        mock_mgr.get_agents = AsyncMock(return_value=[a1, a2])
        mock_mgr.get_agent_logs = AsyncMock(side_effect=[
            ["log_a1"], ["log_a2"]
        ])

        bcast = WebSocketBroadcaster(mock_cm, mock_mgr, mock_mon)
        await bcast._broadcast_log_updates()
        assert mock_cm.broadcast.call_count == 2


# ─── WebSocketBroadcaster._broadcast_agent_updates ──────────────────

class TestBroadcastAgentUpdates:
    @pytest.mark.asyncio
    async def test_new_agent_broadcast(self):
        mock_cm = AsyncMock()
        mock_mgr = AsyncMock()
        mock_mon = MagicMock()

        agent = MagicMock()
        agent.id = "a1"
        agent.name = "Agent1"
        agent.state = MagicMock()
        agent.state.value = "running"
        agent.pid = 123
        agent.uptime = 10.0
        agent.last_error = None
        mock_mgr.get_agents = AsyncMock(return_value=[agent])

        bcast = WebSocketBroadcaster(mock_cm, mock_mgr, mock_mon)
        await bcast._broadcast_agent_updates()

        mock_cm.broadcast.assert_called_once()
        msg = mock_cm.broadcast.call_args[0][0]
        assert msg["type"] == "agent_update"
        assert msg["data"]["id"] == "a1"

    @pytest.mark.asyncio
    async def test_unchanged_agent_no_broadcast(self):
        mock_cm = AsyncMock()
        mock_mgr = AsyncMock()
        mock_mon = MagicMock()

        agent = MagicMock()
        agent.id = "a1"
        agent.name = "Agent1"
        agent.state = MagicMock()
        agent.state.value = "running"
        agent.pid = 123
        agent.uptime = 10.0
        agent.last_error = None
        mock_mgr.get_agents = AsyncMock(return_value=[agent])

        bcast = WebSocketBroadcaster(mock_cm, mock_mgr, mock_mon)
        # Pre-populate last_agents with identical data
        bcast._last_agents["a1"] = {
            "id": "a1", "name": "Agent1", "state": "running",
            "pid": 123, "uptime": 10.0, "last_error": None
        }

        await bcast._broadcast_agent_updates()
        mock_cm.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_state_change_triggers_broadcast(self):
        mock_cm = AsyncMock()
        mock_mgr = AsyncMock()
        mock_mon = MagicMock()

        agent = MagicMock()
        agent.id = "a1"
        agent.name = "Agent1"
        agent.state = MagicMock()
        agent.state.value = "error"
        agent.pid = 123
        agent.uptime = 10.0
        agent.last_error = "crashed"
        mock_mgr.get_agents = AsyncMock(return_value=[agent])

        bcast = WebSocketBroadcaster(mock_cm, mock_mgr, mock_mon)
        bcast._last_agents["a1"] = {
            "id": "a1", "name": "Agent1", "state": "running",
            "pid": 123, "uptime": 10.0, "last_error": None
        }

        await bcast._broadcast_agent_updates()
        mock_cm.broadcast.assert_called_once()
        msg = mock_cm.broadcast.call_args[0][0]
        assert msg["data"]["state"] == "error"

    @pytest.mark.asyncio
    async def test_empty_agents_no_broadcast(self):
        mock_cm = AsyncMock()
        mock_mgr = AsyncMock()
        mock_mon = MagicMock()
        mock_mgr.get_agents = AsyncMock(return_value=[])

        bcast = WebSocketBroadcaster(mock_cm, mock_mgr, mock_mon)
        await bcast._broadcast_agent_updates()
        mock_cm.broadcast.assert_not_called()


# ─── AgentManager._collect_logs edge cases ──────────────────────────

class TestManagerLogCollection:
    @pytest.mark.asyncio
    async def test_get_logs_returns_only_requested_lines(self, tmp_path):
        mgr = AgentManager(config_dir=str(tmp_path / "agents"))
        agent_id = "test-agent"
        mgr.log_buffers[agent_id] = [f"line_{i}" for i in range(200)]
        logs = await mgr.get_agent_logs(agent_id, lines=50)
        assert len(logs) == 50
        assert logs[0] == "line_150"
        assert logs[-1] == "line_199"

    @pytest.mark.asyncio
    async def test_get_logs_more_than_buffer(self, tmp_path):
        mgr = AgentManager(config_dir=str(tmp_path / "agents"))
        agent_id = "test-agent"
        mgr.log_buffers[agent_id] = ["a", "b", "c"]
        logs = await mgr.get_agent_logs(agent_id, lines=100)
        assert logs == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_get_logs_not_found(self, tmp_path):
        mgr = AgentManager(config_dir=str(tmp_path / "agents"))
        logs = await mgr.get_agent_logs("nobody", lines=10)
        assert logs == []


# ─── AgentConfig / AgentInfo model tests ────────────────────────────

class TestAgentModels:
    def test_agent_config_defaults(self):
        c = AgentConfig(id="a1", name="Test", command="echo hi")
        assert c.working_dir is None
        assert c.env_vars is None
        assert c.auto_start is False

    def test_agent_config_with_all_fields(self):
        c = AgentConfig(
            id="a1", name="Test", command="echo hi",
            working_dir="/tmp", env_vars={"KEY": "val"},
            auto_start=True
        )
        assert c.working_dir == "/tmp"
        assert c.env_vars == {"KEY": "val"}
        assert c.auto_start is True

    def test_agent_state_enum_values(self):
        assert AgentState.STOPPED.value == "stopped"
        assert AgentState.STARTING.value == "starting"
        assert AgentState.RUNNING.value == "running"
        assert AgentState.STOPPING.value == "stopping"
        assert AgentState.ERROR.value == "error"

    def test_agent_info_serialization(self):
        config = AgentConfig(id="a1", name="Test", command="echo hi")
        info = AgentInfo(
            id="a1", name="Test", state=AgentState.RUNNING,
            pid=123, uptime=5.0, config=config
        )
        d = info.model_dump()
        assert d["id"] == "a1"
        assert d["state"] == "running"
        assert d["pid"] == 123
        assert d["config"]["command"] == "echo hi"

    def test_agent_info_defaults(self):
        config = AgentConfig(id="a1", name="T", command="echo")
        info = AgentInfo(id="a1", name="T", state=AgentState.STOPPED, config=config)
        assert info.pid is None
        assert info.uptime is None
        assert info.last_error is None
