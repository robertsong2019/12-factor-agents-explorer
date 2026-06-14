"""Tests for FastAPI API routes in main.py"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from edge_agent_dashboard.main import app
from edge_agent_dashboard.manager import AgentConfig, AgentInfo, AgentState
from edge_agent_dashboard.monitor import ResourceMetrics


@pytest.fixture
def mock_dependencies():
    """Patch global dependencies with mocks."""
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
def client(mock_dependencies):
    """TestClient with mocked dependencies."""
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


@pytest.fixture
def sample_config():
    return {
        "id": "agent-1",
        "name": "Test Agent",
        "command": "echo hello",
    }


# ========== GET /api/agents ==========

class TestListAgents:
    def test_empty_list(self, client, mock_dependencies):
        mock_mgr = mock_dependencies[0]
        resp = client.get("/api/agents")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_with_agents(self, client, mock_dependencies, sample_agent_info):
        mock_mgr = mock_dependencies[0]
        mock_mgr.get_agents = AsyncMock(return_value=[sample_agent_info])
        resp = client.get("/api/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "agent-1"


# ========== GET /api/agents/{id} ==========

class TestGetAgent:
    def test_found(self, client, mock_dependencies, sample_agent_info):
        mock_mgr = mock_dependencies[0]
        mock_mgr.get_agent = AsyncMock(return_value=sample_agent_info)
        resp = client.get("/api/agents/agent-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "agent-1"

    def test_not_found(self, client, mock_dependencies):
        mock_mgr = mock_dependencies[0]
        mock_mgr.get_agent = AsyncMock(return_value=None)
        resp = client.get("/api/agents/missing")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ========== POST /api/agents ==========

class TestCreateAgent:
    def test_create_success(self, client, mock_dependencies, sample_config, sample_agent_info):
        mock_mgr = mock_dependencies[0]
        mock_mgr.create_agent = AsyncMock(return_value=sample_agent_info)
        resp = client.post("/api/agents", json=sample_config)
        assert resp.status_code == 200
        assert resp.json()["id"] == "agent-1"

    def test_create_missing_fields(self, client, mock_dependencies):
        resp = client.post("/api/agents", json={"id": "x"})
        assert resp.status_code == 422  # Pydantic validation


# ========== PUT /api/agents/{id} ==========

class TestUpdateAgent:
    def test_update_success(self, client, mock_dependencies, sample_config, sample_agent_info):
        mock_mgr = mock_dependencies[0]
        mock_mgr.update_agent_config = AsyncMock(return_value=sample_agent_info)
        resp = client.put("/api/agents/agent-1", json=sample_config)
        assert resp.status_code == 200

    def test_update_not_found(self, client, mock_dependencies, sample_config):
        mock_mgr = mock_dependencies[0]
        mock_mgr.update_agent_config = AsyncMock(return_value=None)
        resp = client.put("/api/agents/missing", json=sample_config)
        assert resp.status_code == 404


# ========== DELETE /api/agents/{id} ==========

class TestDeleteAgent:
    def test_delete_success(self, client, mock_dependencies):
        mock_mgr = mock_dependencies[0]
        mock_mgr.delete_agent = AsyncMock(return_value=True)
        resp = client.delete("/api/agents/agent-1")
        assert resp.status_code == 200

    def test_delete_not_found(self, client, mock_dependencies):
        mock_mgr = mock_dependencies[0]
        mock_mgr.delete_agent = AsyncMock(return_value=False)
        resp = client.delete("/api/agents/missing")
        assert resp.status_code == 404


# ========== POST /api/agents/{id}/start|stop|restart ==========

class TestAgentActions:
    def test_start_success(self, client, mock_dependencies):
        mock_mgr = mock_dependencies[0]
        mock_mgr.start_agent = AsyncMock(return_value=True)
        resp = client.post("/api/agents/agent-1/start")
        assert resp.status_code == 200

    def test_start_failure(self, client, mock_dependencies):
        mock_mgr = mock_dependencies[0]
        mock_mgr.start_agent = AsyncMock(return_value=False)
        resp = client.post("/api/agents/agent-1/start")
        assert resp.status_code == 400

    def test_stop_success(self, client, mock_dependencies):
        mock_mgr = mock_dependencies[0]
        mock_mgr.stop_agent = AsyncMock(return_value=True)
        resp = client.post("/api/agents/agent-1/stop")
        assert resp.status_code == 200

    def test_stop_failure(self, client, mock_dependencies):
        mock_mgr = mock_dependencies[0]
        mock_mgr.stop_agent = AsyncMock(return_value=False)
        resp = client.post("/api/agents/agent-1/stop")
        assert resp.status_code == 400

    def test_restart_success(self, client, mock_dependencies):
        mock_mgr = mock_dependencies[0]
        mock_mgr.restart_agent = AsyncMock(return_value=True)
        resp = client.post("/api/agents/agent-1/restart")
        assert resp.status_code == 200

    def test_restart_failure(self, client, mock_dependencies):
        mock_mgr = mock_dependencies[0]
        mock_mgr.restart_agent = AsyncMock(return_value=False)
        resp = client.post("/api/agents/agent-1/restart")
        assert resp.status_code == 400


# ========== GET /api/agents/{id}/logs ==========

class TestGetLogs:
    def test_empty_logs(self, client, mock_dependencies):
        mock_mgr = mock_dependencies[0]
        mock_mgr.get_agent_logs = AsyncMock(return_value=[])
        resp = client.get("/api/agents/agent-1/logs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_with_logs(self, client, mock_dependencies):
        mock_mgr = mock_dependencies[0]
        mock_mgr.get_agent_logs = AsyncMock(return_value=["line1", "line2"])
        resp = client.get("/api/agents/agent-1/logs")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_custom_lines_param(self, client, mock_dependencies):
        mock_mgr = mock_dependencies[0]
        mock_mgr.get_agent_logs = AsyncMock(return_value=["a"] * 50)
        resp = client.get("/api/agents/agent-1/logs?lines=50")
        assert resp.status_code == 200
        assert len(resp.json()) == 50


# ========== GET /api/metrics ==========

class TestGetMetrics:
    def test_no_metrics(self, client, mock_dependencies):
        mock_mon = mock_dependencies[1]
        mock_mon.get_current_metrics = MagicMock(return_value=None)
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        assert resp.json() is None

    def test_with_metrics(self, client, mock_dependencies):
        mock_mon = mock_dependencies[1]
        metrics = ResourceMetrics(
            timestamp=1000.0, cpu_percent=50.0, memory_percent=60.0,
            memory_used_mb=1024.0, memory_total_mb=2048.0,
            network_sent_mb=10.0, network_recv_mb=20.0,
            disk_usage_percent=40.0,
        )
        mock_mon.get_current_metrics = MagicMock(return_value=metrics)
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cpu_percent"] == 50.0
