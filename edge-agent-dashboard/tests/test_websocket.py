"""Unit tests for WebSocket ConnectionManager and WebSocketBroadcaster"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edge_agent_dashboard.websocket import ConnectionManager
from edge_agent_dashboard.manager import AgentManager, AgentConfig, AgentInfo, AgentState
from edge_agent_dashboard.monitor import ResourceMonitor


class TestConnectionManager:
    def test_init(self):
        cm = ConnectionManager()
        assert cm.active_connections == set()

    @pytest.mark.asyncio
    async def test_connect(self):
        cm = ConnectionManager()
        ws = AsyncMock()
        await cm.connect(ws)
        ws.accept.assert_called_once()
        assert ws in cm.active_connections

    def test_disconnect(self):
        cm = ConnectionManager()
        ws = MagicMock()
        cm.active_connections.add(ws)
        cm.disconnect(ws)
        assert ws not in cm.active_connections

    def test_disconnect_not_connected(self):
        cm = ConnectionManager()
        ws = MagicMock()
        cm.disconnect(ws)  # should not raise
        assert ws not in cm.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_to_single(self):
        cm = ConnectionManager()
        ws = AsyncMock()
        cm.active_connections.add(ws)
        await cm.broadcast({"type": "test"})
        ws.send_json.assert_called_once_with({"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple(self):
        cm = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        cm.active_connections.add(ws1)
        cm.active_connections.add(ws2)
        await cm.broadcast({"data": 42})
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_empty(self):
        cm = ConnectionManager()
        await cm.broadcast({"msg": "hi"})  # should not raise

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self):
        cm = ConnectionManager()
        ws_good = AsyncMock()
        ws_bad = AsyncMock()
        ws_bad.send_json.side_effect = Exception("connection closed")
        cm.active_connections.add(ws_good)
        cm.active_connections.add(ws_bad)
        await cm.broadcast({"type": "ping"})
        assert ws_good in cm.active_connections
        assert ws_bad not in cm.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_removes_all_dead(self):
        cm = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws1.send_json.side_effect = Exception("dead")
        ws2.send_json.side_effect = Exception("dead")
        cm.active_connections.add(ws1)
        cm.active_connections.add(ws2)
        await cm.broadcast({"type": "ping"})
        assert len(cm.active_connections) == 0

    @pytest.mark.asyncio
    async def test_send_personal(self):
        cm = ConnectionManager()
        ws = AsyncMock()
        await cm.send_personal({"msg": "hello"}, ws)
        ws.send_json.assert_called_once_with({"msg": "hello"})

    @pytest.mark.asyncio
    async def test_send_personal_error_caught(self):
        cm = ConnectionManager()
        ws = AsyncMock()
        ws.send_json.side_effect = Exception("send failed")
        await cm.send_personal({"msg": "hello"}, ws)  # should not raise

    @pytest.mark.asyncio
    async def test_broadcast_preserves_good_after_partial_failure(self):
        cm = ConnectionManager()
        ws_good = AsyncMock()
        ws_bad = AsyncMock()
        ws_neutral = AsyncMock()
        ws_bad.send_json.side_effect = RuntimeError("broken")
        cm.active_connections.update({ws_good, ws_bad, ws_neutral})
        await cm.broadcast({"type": "update"})
        assert ws_good in cm.active_connections
        assert ws_neutral in cm.active_connections
        assert ws_bad not in cm.active_connections
        ws_good.send_json.assert_called_once()
        ws_neutral.send_json.assert_called_once()


class TestConnectionManagerEdgeCases:
    @pytest.mark.asyncio
    async def test_broadcast_does_not_modify_set_during_iteration(self):
        """broadcast should collect dead first, then remove — no Set changed size during iteration"""
        cm = ConnectionManager()
        ws = AsyncMock()
        ws.send_json.side_effect = Exception("fail")
        cm.active_connections.add(ws)
        # should not raise RuntimeError
        await cm.broadcast({"x": 1})

    @pytest.mark.asyncio
    async def test_connect_then_disconnect_cycle(self):
        cm = ConnectionManager()
        ws = AsyncMock()
        await cm.connect(ws)
        assert len(cm.active_connections) == 1
        cm.disconnect(ws)
        assert len(cm.active_connections) == 0
        # reconnect
        await cm.connect(ws)
        assert len(cm.active_connections) == 1
