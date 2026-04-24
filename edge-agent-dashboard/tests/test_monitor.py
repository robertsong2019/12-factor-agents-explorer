"""Unit tests for ResourceMonitor"""

import asyncio
import pytest

from edge_agent_dashboard.monitor import ResourceMonitor, ResourceMetrics


class TestResourceMetrics:
    def test_creation(self):
        m = ResourceMetrics(
            timestamp=1000.0,
            cpu_percent=50.0,
            memory_percent=60.0,
            memory_used_mb=4096.0,
            memory_total_mb=8192.0,
            network_sent_mb=1.0,
            network_recv_mb=2.0,
            disk_usage_percent=70.0,
        )
        assert m.cpu_percent == 50.0
        assert m.load_average is None

    def test_with_load_avg(self):
        m = ResourceMetrics(
            timestamp=0,
            cpu_percent=0,
            memory_percent=0,
            memory_used_mb=0,
            memory_total_mb=0,
            network_sent_mb=0,
            network_recv_mb=0,
            disk_usage_percent=0,
            load_average=1.5,
        )
        assert m.load_average == 1.5


class TestResourceMonitor:
    def test_init_defaults(self):
        mon = ResourceMonitor()
        assert mon.current_metrics is None
        assert mon.history == []
        assert mon.max_history == 300
        assert mon._running is False

    def test_custom_interval(self):
        mon = ResourceMonitor(update_interval=5.0)
        assert mon.update_interval == 5.0

    def test_get_current_metrics_none(self):
        mon = ResourceMonitor()
        assert mon.get_current_metrics() is None

    def test_get_history_empty(self):
        mon = ResourceMonitor()
        assert mon.get_history(60) == []

    def test_get_history_dict_empty(self):
        mon = ResourceMonitor()
        d = mon.get_history_dict(60)
        assert d == {"timestamps": [], "cpu": [], "memory": [], "network_sent": [], "network_recv": []}

    @pytest.mark.asyncio
    async def test_start_stop(self):
        mon = ResourceMonitor(update_interval=0.05)
        await mon.start()
        assert mon._running is True
        await asyncio.sleep(0.15)
        await mon.stop()
        assert mon._running is False

    @pytest.mark.asyncio
    async def test_collects_metrics(self):
        mon = ResourceMonitor(update_interval=0.05)
        await mon.start()
        await asyncio.sleep(0.15)
        await mon.stop()
        assert mon.current_metrics is not None
        assert isinstance(mon.current_metrics, ResourceMetrics)
        assert mon.current_metrics.cpu_percent >= 0

    @pytest.mark.asyncio
    async def test_history_grows(self):
        mon = ResourceMonitor(update_interval=0.05)
        await mon.start()
        await asyncio.sleep(0.2)
        await mon.stop()
        assert len(mon.history) >= 1

    @pytest.mark.asyncio
    async def test_history_respects_max(self):
        mon = ResourceMonitor(update_interval=0.01)
        mon.max_history = 5
        await mon.start()
        await asyncio.sleep(0.1)
        await mon.stop()
        assert len(mon.history) <= 5

    @pytest.mark.asyncio
    async def test_get_history_filters_by_time(self):
        mon = ResourceMonitor(update_interval=0.05)
        await mon.start()
        await asyncio.sleep(0.2)
        await mon.stop()
        # asking for 0 seconds should return empty
        assert mon.get_history(0) == []
        # asking for large window should return all
        assert len(mon.get_history(3600)) == len(mon.history)

    @pytest.mark.asyncio
    async def test_get_history_dict_format(self):
        mon = ResourceMonitor(update_interval=0.05)
        await mon.start()
        await asyncio.sleep(0.15)
        await mon.stop()
        d = mon.get_history_dict(3600)
        assert len(d["timestamps"]) == len(mon.history)
        assert len(d["cpu"]) == len(mon.history)
        # timestamps in ms
        if d["timestamps"]:
            assert d["timestamps"][0] > 1e12  # ms since epoch

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        mon = ResourceMonitor(update_interval=0.1)
        await mon.start()
        task1 = mon._task
        await mon.start()
        assert mon._task is task1  # same task, not duplicated
        await mon.stop()

    @pytest.mark.asyncio
    async def test_stop_idempotent(self):
        mon = ResourceMonitor()
        await mon.stop()  # should not raise
        assert mon._running is False
