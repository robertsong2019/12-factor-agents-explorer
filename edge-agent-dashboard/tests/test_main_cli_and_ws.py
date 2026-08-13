"""
Tests for main.py uncovered areas:
1. cli() argument parsing
2. WebSocket endpoint (/ws) - connection, init message, disconnect
3. Lifespan startup/shutdown
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from edge_agent_dashboard.main import app
from edge_agent_dashboard.manager import AgentConfig, AgentInfo, AgentState
from edge_agent_dashboard.monitor import ResourceMetrics


# ─── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def mock_deps():
    mock_manager = MagicMock()
    mock_monitor = MagicMock()
    mock_conn = MagicMock()
    # connect must call websocket.accept() like the real ConnectionManager
    async def _mock_connect(ws):
        await ws.accept()
    mock_conn.connect = _mock_connect
    # send_personal must actually send data through the websocket
    async def _mock_send_personal(data, ws):
        await ws.send_json(data)
    mock_conn.send_personal = _mock_send_personal
    mock_conn.disconnect = MagicMock()
    mock_broadcaster = MagicMock()

    mock_manager.get_agents = AsyncMock(return_value=[])
    mock_manager.get_agent = AsyncMock(return_value=None)

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


@pytest.fixture
def sample_agent_info():
    return AgentInfo(
        id="agent-1",
        name="Test Agent",
        state=AgentState.STOPPED,
        pid=None,
        config=AgentConfig(id="agent-1", name="Test Agent", command="echo hi"),
    )


# ─── CLI Tests ──────────────────────────────────────────────────────

class TestCLI:
    """Test the cli() argument parser."""

    def test_cli_default_args(self):
        """cli() should use default host/port when no args given."""
        with patch("sys.argv", ["edge-agent-dashboard"]), \
             patch("edge_agent_dashboard.main.uvicorn") as mock_uvicorn, \
             patch("edge_agent_dashboard.main.AgentManager") as mock_mgr:
            from edge_agent_dashboard.main import cli
            cli()
            call_kwargs = mock_uvicorn.run.call_args.kwargs
            assert call_kwargs["host"] == "0.0.0.0"
            assert call_kwargs["port"] == 8000
            assert call_kwargs["reload"] is False

    def test_cli_custom_host_port(self):
        """cli() should parse custom --host and --port."""
        with patch("sys.argv", ["edge-agent-dashboard", "--host", "127.0.0.1", "--port", "9999"]), \
             patch("edge_agent_dashboard.main.uvicorn") as mock_uvicorn, \
             patch("edge_agent_dashboard.main.AgentManager") as mock_mgr:
            from edge_agent_dashboard.main import cli
            cli()
            call_kwargs = mock_uvicorn.run.call_args.kwargs
            assert call_kwargs["host"] == "127.0.0.1"
            assert call_kwargs["port"] == 9999

    def test_cli_reload_flag(self):
        """cli() should set reload=True when --reload passed."""
        with patch("sys.argv", ["edge-agent-dashboard", "--reload"]), \
             patch("edge_agent_dashboard.main.uvicorn") as mock_uvicorn, \
             patch("edge_agent_dashboard.main.AgentManager") as mock_mgr:
            from edge_agent_dashboard.main import cli
            cli()
            assert mock_uvicorn.run.call_args.kwargs["reload"] is True

    def test_cli_custom_config_dir(self):
        """cli() should pass config_dir to AgentManager."""
        with patch("sys.argv", ["edge-agent-dashboard", "--config-dir", "/tmp/agents"]), \
             patch("edge_agent_dashboard.main.uvicorn"), \
             patch("edge_agent_dashboard.main.AgentManager") as mock_mgr:
            from edge_agent_dashboard.main import cli
            cli()
            mock_mgr.assert_called_once_with(config_dir="/tmp/agents")


# ─── WebSocket Endpoint Tests ───────────────────────────────────────

class TestWebSocketEndpoint:
    """Test the /ws WebSocket endpoint."""

    def test_ws_connect_empty_agents(self, client, mock_deps):
        """WebSocket should accept connection and send init with empty agents."""
        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "init"
            assert "data" in data
            assert data["data"]["agents"] == []

    def test_ws_connect_with_agents(self, client, mock_deps, sample_agent_info):
        """WebSocket init message should include agent list."""
        mock_manager = mock_deps[0]
        mock_manager.get_agents = AsyncMock(return_value=[sample_agent_info])
        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "init"
            assert len(data["data"]["agents"]) == 1
            assert data["data"]["agents"][0]["id"] == "agent-1"

    def test_ws_init_metrics_none(self, client, mock_deps):
        """When metrics are None, init data should have metrics: null."""
        mock_monitor = mock_deps[1]
        mock_monitor.get_current_metrics = MagicMock(return_value=None)
        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert data["data"]["metrics"] is None

    def test_ws_init_with_metrics(self, client, mock_deps):
        """When metrics exist, init data should include them."""
        mock_monitor = mock_deps[1]
        metrics = ResourceMetrics(
            timestamp=1000.0,
            cpu_percent=50.0,
            memory_percent=60.0,
            memory_used_mb=1024.0,
            memory_total_mb=2048.0,
            network_sent_mb=10.0,
            network_recv_mb=20.0,
            disk_usage_percent=40.0,
            load_average=1.5,
        )
        mock_monitor.get_current_metrics = MagicMock(return_value=metrics)
        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert data["data"]["metrics"] is not None
            assert data["data"]["metrics"]["cpu_percent"] == 50.0
