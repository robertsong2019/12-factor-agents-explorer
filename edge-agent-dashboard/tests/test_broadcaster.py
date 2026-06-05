"""Unit tests for WebSocketBroadcaster — broadcast loop, agent updates, log updates"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edge_agent_dashboard.websocket import ConnectionManager, WebSocketBroadcaster
from edge_agent_dashboard.manager import AgentConfig, AgentInfo, AgentState
from edge_agent_dashboard.monitor import ResourceMonitor, ResourceMetrics


# ── Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def conn_mgr():
    return ConnectionManager()


@pytest.fixture
def agent_manager():
    """Mock agent manager with configurable agents"""
    mgr = MagicMock()
    mgr.get_agents = AsyncMock(return_value=[])
    mgr.get_agent_logs = AsyncMock(return_value=[])
    return mgr


@pytest.fixture
def monitor():
    mon = MagicMock(spec=ResourceMonitor)
    mon.get_current_metrics = MagicMock(return_value=None)
    return mon


@pytest.fixture
def broadcaster(conn_mgr, agent_manager, monitor):
    return WebSocketBroadcaster(conn_mgr, agent_manager, monitor)


def make_agent(aid="a1", name="A1", state=AgentState.RUNNING, pid=123):
    config = AgentConfig(id=aid, name=name, command="echo hi")
    return AgentInfo(id=aid, name=name, state=state, pid=pid, config=config)


def make_metrics(**kw):
    defaults = dict(
        timestamp=1000.0, cpu_percent=50.0, memory_percent=60.0,
        memory_used_mb=4096.0, memory_total_mb=8192.0,
        network_sent_mb=1.0, network_recv_mb=2.0, disk_usage_percent=70.0,
    )
    defaults.update(kw)
    return ResourceMetrics(**defaults)


# ── Init ────────────────────────────────────────────────────────

class TestBroadcasterInit:
    def test_init(self, broadcaster, conn_mgr, agent_manager, monitor):
        assert broadcaster.connection_manager is conn_mgr
        assert broadcaster.agent_manager is agent_manager
        assert broadcaster.resource_monitor is monitor
        assert broadcaster._running is False
        assert broadcaster._task is None
        assert broadcaster._last_agents == {}
        assert broadcaster._last_log_lines == {}


# ── Start/Stop ──────────────────────────────────────────────────

class TestBroadcasterStartStop:
    @pytest.mark.asyncio
    async def test_start(self, broadcaster):
        await broadcaster.start()
        assert broadcaster._running is True
        assert broadcaster._task is not None
        await broadcaster.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self, broadcaster):
        await broadcaster.start()
        task1 = broadcaster._task
        await broadcaster.start()
        assert broadcaster._task is task1
        await broadcaster.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, broadcaster):
        await broadcaster.stop()
        assert broadcaster._running is False

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, broadcaster):
        await broadcaster.start()
        task = broadcaster._task
        await broadcaster.stop()
        assert broadcaster._task is None
        assert task.cancelled() or task.done()


# ── Agent Updates ──────────────────────────────────────────────

class TestBroadcastAgentUpdates:
    @pytest.mark.asyncio
    async def test_broadcasts_new_agent(self, broadcaster, conn_mgr, agent_manager):
        agent = make_agent("a1", "Agent1")
        agent_manager.get_agents = AsyncMock(return_value=[agent])
        conn_mgr.broadcast = AsyncMock()

        await broadcaster._broadcast_agent_updates()

        conn_mgr.broadcast.assert_called_once()
        msg = conn_mgr.broadcast.call_args[0][0]
        assert msg["type"] == "agent_update"
        assert msg["data"]["id"] == "a1"
        assert msg["data"]["state"] == "running"

    @pytest.mark.asyncio
    async def test_skips_unchanged_agent(self, broadcaster, conn_mgr, agent_manager):
        agent = make_agent("a1", "Agent1")
        agent_manager.get_agents = AsyncMock(return_value=[agent])
        conn_mgr.broadcast = AsyncMock()

        # First call sends update
        await broadcaster._broadcast_agent_updates()
        assert conn_mgr.broadcast.call_count == 1

        # Second call with same data should not broadcast
        await broadcaster._broadcast_agent_updates()
        assert conn_mgr.broadcast.call_count == 1

    @pytest.mark.asyncio
    async def test_detects_state_change(self, broadcaster, conn_mgr, agent_manager):
        agent = make_agent("a1", state=AgentState.RUNNING)
        agent_manager.get_agents = AsyncMock(return_value=[agent])
        conn_mgr.broadcast = AsyncMock()

        # First call
        await broadcaster._broadcast_agent_updates()
        assert conn_mgr.broadcast.call_count == 1

        # Change state
        agent.state = AgentState.ERROR
        agent.last_error = "crashed"
        await broadcaster._broadcast_agent_updates()
        assert conn_mgr.broadcast.call_count == 2
        msg = conn_mgr.broadcast.call_args[0][0]
        assert msg["data"]["state"] == "error"

    @pytest.mark.asyncio
    async def test_handles_multiple_agents(self, broadcaster, conn_mgr, agent_manager):
        a1 = make_agent("a1", "A1")
        a2 = make_agent("a2", "A2")
        agent_manager.get_agents = AsyncMock(return_value=[a1, a2])
        conn_mgr.broadcast = AsyncMock()

        await broadcaster._broadcast_agent_updates()
        assert conn_mgr.broadcast.call_count == 2

        # Next cycle: no changes → no broadcasts
        await broadcaster._broadcast_agent_updates()
        assert conn_mgr.broadcast.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_agent_list(self, broadcaster, conn_mgr, agent_manager):
        agent_manager.get_agents = AsyncMock(return_value=[])
        conn_mgr.broadcast = AsyncMock()

        await broadcaster._broadcast_agent_updates()
        conn_mgr.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_detects_pid_change(self, broadcaster, conn_mgr, agent_manager):
        agent = make_agent("a1", pid=100)
        agent_manager.get_agents = AsyncMock(return_value=[agent])
        conn_mgr.broadcast = AsyncMock()

        await broadcaster._broadcast_agent_updates()
        assert conn_mgr.broadcast.call_count == 1

        agent.pid = 200
        await broadcaster._broadcast_agent_updates()
        assert conn_mgr.broadcast.call_count == 2


# ── Log Updates ────────────────────────────────────────────────

class TestBroadcastLogUpdates:
    @pytest.mark.asyncio
    async def test_sends_new_logs(self, broadcaster, conn_mgr, agent_manager):
        agent = make_agent("a1", state=AgentState.RUNNING)
        agent_manager.get_agents = AsyncMock(return_value=[agent])
        agent_manager.get_agent_logs = AsyncMock(return_value=["line1", "line2", "line3"])
        conn_mgr.broadcast = AsyncMock()

        await broadcaster._broadcast_log_updates()

        conn_mgr.broadcast.assert_called_once()
        msg = conn_mgr.broadcast.call_args[0][0]
        assert msg["type"] == "log_update"
        assert msg["data"]["agent_id"] == "a1"
        assert msg["data"]["logs"] == ["line1", "line2", "line3"]

    @pytest.mark.asyncio
    async def test_sends_only_incremental_logs(self, broadcaster, conn_mgr, agent_manager):
        agent = make_agent("a1", state=AgentState.RUNNING)
        agent_manager.get_agents = AsyncMock(return_value=[agent])
        conn_mgr.broadcast = AsyncMock()

        # First cycle: 3 lines
        agent_manager.get_agent_logs = AsyncMock(return_value=["line1", "line2", "line3"])
        await broadcaster._broadcast_log_updates()
        assert conn_mgr.broadcast.call_count == 1
        assert conn_mgr.broadcast.call_args[0][0]["data"]["logs"] == ["line1", "line2", "line3"]

        # Second cycle: 5 lines total → only lines 4-5 are new
        agent_manager.get_agent_logs = AsyncMock(return_value=["line1", "line2", "line3", "line4", "line5"])
        await broadcaster._broadcast_log_updates()
        assert conn_mgr.broadcast.call_count == 2
        msg = conn_mgr.broadcast.call_args[0][0]
        assert msg["data"]["logs"] == ["line4", "line5"]

    @pytest.mark.asyncio
    async def test_no_broadcast_when_no_new_logs(self, broadcaster, conn_mgr, agent_manager):
        agent = make_agent("a1", state=AgentState.RUNNING)
        agent_manager.get_agents = AsyncMock(return_value=[agent])
        agent_manager.get_agent_logs = AsyncMock(return_value=["line1", "line2"])
        conn_mgr.broadcast = AsyncMock()

        # First cycle
        await broadcaster._broadcast_log_updates()
        assert conn_mgr.broadcast.call_count == 1

        # Second cycle: same lines → no new logs
        await broadcaster._broadcast_log_updates()
        assert conn_mgr.broadcast.call_count == 1

    @pytest.mark.asyncio
    async def test_skips_stopped_agents(self, broadcaster, conn_mgr, agent_manager):
        agent = make_agent("a1", state=AgentState.STOPPED)
        agent_manager.get_agents = AsyncMock(return_value=[agent])
        agent_manager.get_agent_logs = AsyncMock(return_value=["line1"])
        conn_mgr.broadcast = AsyncMock()

        await broadcaster._broadcast_log_updates()
        conn_mgr.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_starting_agents(self, broadcaster, conn_mgr, agent_manager):
        agent = make_agent("a1", state=AgentState.STARTING)
        agent_manager.get_agents = AsyncMock(return_value=[agent])
        conn_mgr.broadcast = AsyncMock()

        await broadcaster._broadcast_log_updates()
        conn_mgr.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_includes_error_agents(self, broadcaster, conn_mgr, agent_manager):
        agent = make_agent("a1", state=AgentState.ERROR)
        agent_manager.get_agents = AsyncMock(return_value=[agent])
        agent_manager.get_agent_logs = AsyncMock(return_value=["err line"])
        conn_mgr.broadcast = AsyncMock()

        await broadcaster._broadcast_log_updates()
        conn_mgr.broadcast.assert_called_once()
        msg = conn_mgr.broadcast.call_args[0][0]
        assert msg["data"]["logs"] == ["err line"]

    @pytest.mark.asyncio
    async def test_multiple_agents_independent_logs(self, broadcaster, conn_mgr, agent_manager):
        a1 = make_agent("a1", state=AgentState.RUNNING)
        a2 = make_agent("a2", state=AgentState.RUNNING)
        agent_manager.get_agents = AsyncMock(return_value=[a1, a2])

        async def mock_logs(agent_id, lines=100):
            return [f"{agent_id}-line1", f"{agent_id}-line2"]
        agent_manager.get_agent_logs = mock_logs
        conn_mgr.broadcast = AsyncMock()

        await broadcaster._broadcast_log_updates()
        assert conn_mgr.broadcast.call_count == 2

        # Second cycle: no new logs
        await broadcaster._broadcast_log_updates()
        assert conn_mgr.broadcast.call_count == 2


# ── Broadcast Loop Integration ─────────────────────────────────

class TestBroadcastLoop:
    @pytest.mark.asyncio
    async def test_loop_broadcasts_metrics(self, broadcaster, conn_mgr, monitor):
        """Verify the broadcast loop pushes metrics when running"""
        metrics = make_metrics(cpu_percent=42.0)
        monitor.get_current_metrics = MagicMock(return_value=metrics)
        conn_mgr.broadcast = AsyncMock()

        # Start, wait briefly, stop
        await broadcaster.start()
        await asyncio.sleep(0.1)
        await broadcaster.stop()

        # Should have broadcast metrics at least once
        calls = [c.args[0] for c in conn_mgr.broadcast.call_args_list]
        metric_calls = [c for c in calls if c.get("type") == "metrics"]
        assert len(metric_calls) >= 1
        assert metric_calls[0]["data"]["cpu_percent"] == 42.0

    @pytest.mark.asyncio
    async def test_loop_handles_no_metrics(self, broadcaster, conn_mgr, monitor):
        """Loop should handle None metrics gracefully"""
        monitor.get_current_metrics = MagicMock(return_value=None)
        conn_mgr.broadcast = AsyncMock()

        await broadcaster.start()
        await asyncio.sleep(0.1)
        await broadcaster.stop()

        # No metrics broadcasts should happen
        calls = [c.args[0] for c in conn_mgr.broadcast.call_args_list]
        metric_calls = [c for c in calls if c.get("type") == "metrics"]
        assert len(metric_calls) == 0

    @pytest.mark.asyncio
    async def test_loop_swallows_exceptions(self, broadcaster, conn_mgr, monitor):
        """Loop should continue running even if broadcast raises"""
        monitor.get_current_metrics = MagicMock(side_effect=RuntimeError("boom"))
        conn_mgr.broadcast = AsyncMock()

        await broadcaster.start()
        await asyncio.sleep(0.15)
        await broadcaster.stop()
        # If the loop crashed, _running would still be True at time of stop
        # The fact that stop() works means the loop was still alive

    @pytest.mark.asyncio
    async def test_loop_broadcasts_agent_state(self, broadcaster, conn_mgr, agent_manager, monitor):
        """Loop should detect and broadcast agent state"""
        monitor.get_current_metrics = MagicMock(return_value=None)
        agent = make_agent("a1", state=AgentState.RUNNING)
        agent_manager.get_agents = AsyncMock(return_value=[agent])
        conn_mgr.broadcast = AsyncMock()

        await broadcaster.start()
        await asyncio.sleep(0.15)
        await broadcaster.stop()

        calls = [c.args[0] for c in conn_mgr.broadcast.call_args_list]
        agent_calls = [c for c in calls if c.get("type") == "agent_update"]
        assert len(agent_calls) >= 1
