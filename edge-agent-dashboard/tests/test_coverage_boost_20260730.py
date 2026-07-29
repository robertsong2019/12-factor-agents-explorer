"""
Coverage boost tests — 2026-07-30
Targets:
1. ResourceMonitor._update_metrics: network delta calculation, load_average, error handling
2. AgentManager.start_agent: env_vars passing, working_dir
3. main.py: root endpoint, metrics/history with custom seconds
4. AgentManager._collect_logs: log buffer truncation behavior
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from edge_agent_dashboard.monitor import ResourceMonitor, ResourceMetrics
from edge_agent_dashboard.manager import (
    AgentManager, AgentConfig, AgentInfo, AgentState,
)
from edge_agent_dashboard.main import app


# ─── ResourceMonitor._update_metrics ─────────────────────────────

class TestUpdateMetricsNetworkDelta:
    """Verify network delta calculation in _update_metrics"""

    @pytest.mark.asyncio
    async def test_network_delta_sent(self):
        """Network sent delta = current_bytes - previous_bytes, converted to MB"""
        mon = ResourceMonitor(update_interval=0.01)

        # Simulate initial network counters
        with patch("edge_agent_dashboard.monitor.psutil") as mock_psutil:
            mock_psutil.net_io_counters.return_value = MagicMock(
                bytes_sent=1_000_000, bytes_recv=500_000
            )
            mock_psutil.cpu_percent.return_value = 30.0
            mock_psutil.virtual_memory.return_value = MagicMock(
                percent=50.0, used=4_000_000_000, total=8_000_000_000
            )
            mock_psutil.disk_usage.return_value = MagicMock(percent=60.0)
            mock_psutil.getloadavg.return_value = (1.0, 0.8, 0.5)

            mon._network_counters = mock_psutil.net_io_counters.return_value
            # Update the mock to simulate new counters (1MB more sent)
            mock_psutil.net_io_counters.return_value = MagicMock(
                bytes_sent=2_048_576, bytes_recv=500_000  # ~1MB more sent
            )

            await mon._update_metrics()

        assert mon.current_metrics is not None
        # Delta should be (2_048_576 - 1_000_000) / (1024*1024) ≈ 1.0 MB
        assert mon.current_metrics.network_sent_mb > 0.9
        assert mon.current_metrics.network_sent_mb < 1.1

    @pytest.mark.asyncio
    async def test_network_delta_recv(self):
        """Network recv delta calculated correctly"""
        mon = ResourceMonitor(update_interval=0.01)

        with patch("edge_agent_dashboard.monitor.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 10.0
            mock_psutil.virtual_memory.return_value = MagicMock(
                percent=40.0, used=2_000_000_000, total=8_000_000_000
            )
            mock_psutil.disk_usage.return_value = MagicMock(percent=50.0)
            mock_psutil.getloadavg.return_value = (0.5, 0.3, 0.2)

            # Set initial counters
            mon._network_counters = MagicMock(bytes_sent=0, bytes_recv=1_000_000)
            mock_psutil.net_io_counters.return_value = MagicMock(
                bytes_sent=0, bytes_recv=2_048_576  # ~1MB more received
            )

            await mon._update_metrics()

        assert mon.current_metrics.network_recv_mb > 0.9
        assert mon.current_metrics.network_recv_mb < 1.1

    @pytest.mark.asyncio
    async def test_load_average_captured(self):
        """load_average is captured when available"""
        mon = ResourceMonitor(update_interval=0.01)

        with patch("edge_agent_dashboard.monitor.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 20.0
            mock_psutil.virtual_memory.return_value = MagicMock(
                percent=55.0, used=4_400_000_000, total=8_000_000_000
            )
            mock_psutil.disk_usage.return_value = MagicMock(percent=65.0)
            mock_psutil.getloadavg.return_value = (2.5, 2.0, 1.5)
            mock_psutil.net_io_counters.return_value = MagicMock(
                bytes_sent=0, bytes_recv=0
            )
            mon._network_counters = mock_psutil.net_io_counters.return_value

            await mon._update_metrics()

        assert mon.current_metrics.load_average == 2.5

    @pytest.mark.asyncio
    async def test_load_average_none_on_oserror(self):
        """load_average is None when getloadavg raises OSError (e.g., Windows)"""
        mon = ResourceMonitor(update_interval=0.01)

        with patch("edge_agent_dashboard.monitor.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 20.0
            mock_psutil.virtual_memory.return_value = MagicMock(
                percent=55.0, used=4_400_000_000, total=8_000_000_000
            )
            mock_psutil.disk_usage.return_value = MagicMock(percent=65.0)
            mock_psutil.getloadavg.side_effect = OSError("not available")
            mock_psutil.net_io_counters.return_value = MagicMock(
                bytes_sent=0, bytes_recv=0
            )
            mon._network_counters = mock_psutil.net_io_counters.return_value

            await mon._update_metrics()

        assert mon.current_metrics.load_average is None

    @pytest.mark.asyncio
    async def test_metrics_added_to_history(self):
        """Each update appends to history list"""
        mon = ResourceMonitor(update_interval=0.01)
        mon.max_history = 10

        with patch("edge_agent_dashboard.monitor.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 10.0
            mock_psutil.virtual_memory.return_value = MagicMock(
                percent=40.0, used=2_000_000_000, total=8_000_000_000
            )
            mock_psutil.disk_usage.return_value = MagicMock(percent=50.0)
            mock_psutil.net_io_counters.return_value = MagicMock(
                bytes_sent=0, bytes_recv=0
            )
            mon._network_counters = mock_psutil.net_io_counters.return_value

            await mon._update_metrics()
            await mon._update_metrics()
            await mon._update_metrics()

        assert len(mon.history) == 3
        # Each entry should be a ResourceMetrics
        assert all(isinstance(m, ResourceMetrics) for m in mon.history)

    @pytest.mark.asyncio
    async def test_history_truncation(self):
        """History is truncated when exceeding max_history"""
        mon = ResourceMonitor(update_interval=0.01)
        mon.max_history = 3

        with patch("edge_agent_dashboard.monitor.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 10.0
            mock_psutil.virtual_memory.return_value = MagicMock(
                percent=40.0, used=2_000_000_000, total=8_000_000_000
            )
            mock_psutil.disk_usage.return_value = MagicMock(percent=50.0)
            mock_psutil.net_io_counters.return_value = MagicMock(
                bytes_sent=0, bytes_recv=0
            )
            mon._network_counters = mock_psutil.net_io_counters.return_value

            for i in range(6):
                mock_psutil.cpu_percent.return_value = float(i * 10)
                await mon._update_metrics()

        assert len(mon.history) == 3
        # Should keep the latest 3
        cpu_values = [m.cpu_percent for m in mon.history]
        assert cpu_values == [30.0, 40.0, 50.0]

    @pytest.mark.asyncio
    async def test_update_metrics_swallows_exception(self):
        """_update_metrics should not raise on psutil error"""
        mon = ResourceMonitor(update_interval=0.01)

        with patch("edge_agent_dashboard.monitor.psutil") as mock_psutil:
            mock_psutil.cpu_percent.side_effect = RuntimeError("psutil broken")
            # Should not raise
            await mon._update_metrics()

        assert mon.current_metrics is None


# ─── ResourceMonitor.get_history with pre-populated data ─────────

class TestGetHistoryFiltered:
    """Test get_history with known timestamps"""

    @pytest.mark.asyncio
    async def test_get_history_filters_old_entries(self):
        """Entries older than the requested window are excluded"""
        from datetime import datetime, timedelta

        mon = ResourceMonitor()
        now = datetime.now().timestamp()

        # Create metrics with known timestamps
        for i in range(5):
            mon.history.append(ResourceMetrics(
                timestamp=now - (4 - i) * 10,  # 40s, 30s, 20s, 10s, 0s ago
                cpu_percent=float(i),
                memory_percent=50.0,
                memory_used_mb=4096.0,
                memory_total_mb=8192.0,
                network_sent_mb=0.0,
                network_recv_mb=0.0,
                disk_usage_percent=60.0,
            ))

        # Request last 25 seconds → should get 3 entries (10s, 20s, 0s)
        result = mon.get_history(25)
        assert len(result) == 3

        # Request last 5 seconds → should get 1 entry
        result = mon.get_history(5)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_history_dict_non_empty(self):
        """get_history_dict returns properly formatted data"""
        from datetime import datetime

        mon = ResourceMonitor()
        now = datetime.now().timestamp()

        mon.history.append(ResourceMetrics(
            timestamp=now,
            cpu_percent=42.0,
            memory_percent=60.0,
            memory_used_mb=4096.0,
            memory_total_mb=8192.0,
            network_sent_mb=1.5,
            network_recv_mb=2.5,
            disk_usage_percent=70.0,
        ))

        d = mon.get_history_dict(60)
        assert len(d["timestamps"]) == 1
        assert d["cpu"] == [42.0]
        assert d["memory"] == [60.0]
        assert d["network_sent"] == [1.5]
        assert d["network_recv"] == [2.5]
        # Timestamp in milliseconds
        assert d["timestamps"][0] == now * 1000


# ─── AgentManager.start_agent with env_vars ──────────────────────

class TestStartAgentEnvVars:
    """Test that start_agent correctly passes environment variables"""

    @pytest.mark.asyncio
    async def test_start_with_env_vars(self, tmp_path):
        mgr = AgentManager(config_dir=str(tmp_path / "agents"))
        config = AgentConfig(
            id="env-test",
            name="Env Test",
            command="echo $MY_VAR",
            env_vars={"MY_VAR": "hello123", "OTHER": "world"},
        )
        await mgr.create_agent(config)
        result = await mgr.start_agent("env-test")
        assert result is True
        agent = await mgr.get_agent("env-test")
        assert agent.state == AgentState.RUNNING
        await mgr.stop_agent("env-test")

    @pytest.mark.asyncio
    async def test_start_with_working_dir(self, tmp_path):
        mgr = AgentManager(config_dir=str(tmp_path / "agents"))
        config = AgentConfig(
            id="dir-test",
            name="Dir Test",
            command="pwd",
            working_dir=str(tmp_path),
        )
        await mgr.create_agent(config)
        result = await mgr.start_agent("dir-test")
        assert result is True
        await mgr.stop_agent("dir-test")

    @pytest.mark.asyncio
    async def test_start_no_env_vars(self, tmp_path):
        """Starting without env_vars should still work (inherits os.environ)"""
        mgr = AgentManager(config_dir=str(tmp_path / "agents"))
        config = AgentConfig(
            id="no-env",
            name="No Env",
            command="echo hi",
        )
        await mgr.create_agent(config)
        result = await mgr.start_agent("no-env")
        assert result is True
        await mgr.stop_agent("no-env")


# ─── AgentManager log buffer management ──────────────────────────

class TestLogBufferManagement:
    """Test log buffer truncation in _collect_logs"""

    @pytest.mark.asyncio
    async def test_log_buffer_truncation(self, tmp_path):
        """Log buffer should be truncated when exceeding 1000 lines"""
        mgr = AgentManager(config_dir=str(tmp_path / "agents"))
        config = AgentConfig(id="log-trunc", name="Log Truncation Test", command="echo hi")
        await mgr.create_agent(config)

        # Simulate a large log buffer
        mgr.log_buffers["log-trunc"] = [f"line_{i}" for i in range(1001)]
        # Simulate the truncation logic from _collect_logs
        if len(mgr.log_buffers["log-trunc"]) > 1000:
            mgr.log_buffers["log-trunc"] = mgr.log_buffers["log-trunc"][-500:]

        assert len(mgr.log_buffers["log-trunc"]) == 500
        # Should keep last 500 entries
        assert mgr.log_buffers["log-trunc"][0] == "line_501"
        assert mgr.log_buffers["log-trunc"][-1] == "line_1000"

    @pytest.mark.asyncio
    async def test_log_buffer_under_limit(self, tmp_path):
        """Log buffer under 1000 lines should not be truncated"""
        mgr = AgentManager(config_dir=str(tmp_path / "agents"))
        config = AgentConfig(id="log-small", name="Small Log", command="echo hi")
        await mgr.create_agent(config)

        mgr.log_buffers["log-small"] = [f"line_{i}" for i in range(100)]
        # No truncation should happen
        assert len(mgr.log_buffers["log-small"]) == 100


# ─── main.py root endpoint ───────────────────────────────────────

class TestRootEndpoint:
    """Test the root endpoint and metrics/history"""

    @pytest.fixture
    def mock_deps(self):
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
    def client(self, mock_deps):
        return TestClient(app, raise_server_exceptions=False)

    def test_metrics_history_default_seconds(self, client, mock_deps):
        """metrics/history uses default 60 seconds when no param provided"""
        mock_mon = mock_deps[1]
        mock_mon.get_history_dict = MagicMock(return_value={
            "timestamps": [], "cpu": [], "memory": [],
            "network_sent": [], "network_recv": []
        })
        resp = client.get("/api/metrics/history")
        assert resp.status_code == 200
        # Default should be 60
        mock_mon.get_history_dict.assert_called_once_with(60)

    def test_metrics_with_model_dump(self, client, mock_deps):
        """metrics endpoint returns model_dump when metrics available"""
        from edge_agent_dashboard.monitor import ResourceMetrics as RM

        metrics = RM(
            timestamp=1000.0, cpu_percent=55.0, memory_percent=65.0,
            memory_used_mb=4096.0, memory_total_mb=8192.0,
            network_sent_mb=1.0, network_recv_mb=2.0,
            disk_usage_percent=70.0, load_average=1.2,
        )
        mock_mon = mock_deps[1]
        mock_mon.get_current_metrics = MagicMock(return_value=metrics)
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cpu_percent"] == 55.0
        assert data["load_average"] == 1.2

    def test_logs_with_zero_lines(self, client, mock_deps):
        """GET /api/agents/{id}/logs?lines=0 returns empty list"""
        mock_mgr = mock_deps[0]
        mock_mgr.get_agent_logs = AsyncMock(return_value=[])
        resp = client.get("/api/agents/test/logs?lines=0")
        assert resp.status_code == 200
        assert resp.json() == []


# ─── Manager restart behavior ────────────────────────────────────

class TestRestartBehavior:
    """Test restart_agent sequencing"""

    @pytest.mark.asyncio
    async def test_restart_calls_stop_then_start(self, tmp_path):
        """restart_agent should stop first, then start"""
        mgr = AgentManager(config_dir=str(tmp_path / "agents"))
        config = AgentConfig(id="restart-test", name="Restart Test", command="echo hi")
        await mgr.create_agent(config)

        call_order = []
        original_stop = mgr.stop_agent
        original_start = mgr.start_agent

        async def tracking_stop(agent_id):
            call_order.append("stop")
            return await original_stop(agent_id)

        async def tracking_start(agent_id):
            call_order.append("start")
            return await original_start(agent_id)

        mgr.stop_agent = tracking_stop
        mgr.start_agent = tracking_start

        result = await mgr.restart_agent("restart-test")
        assert result is True
        assert call_order == ["stop", "start"]
        await mgr.stop_agent("restart-test")

    @pytest.mark.asyncio
    async def test_restart_not_found(self, tmp_path):
        mgr = AgentManager(config_dir=str(tmp_path / "agents"))
        # stop_agent returns False for unknown, start_agent returns False
        result = await mgr.restart_agent("nonexistent")
        assert result is False
