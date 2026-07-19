"""
WebSocket Manager - 管理WebSocket连接和实时数据推送
"""

import asyncio
import json
from typing import Set, Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from .manager import AgentManager, AgentInfo
from .monitor import ResourceMonitor


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """接受新连接"""
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        """断开连接"""
        self.active_connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """广播消息到所有连接"""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error sending to connection: {e}")
                disconnected.add(connection)

        # 清理断开的连接
        for conn in disconnected:
            self.active_connections.discard(conn)

    async def send_personal(self, message: Dict[str, Any], websocket: WebSocket):
        """发送个人消息"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"Error sending personal message: {e}")


class WebSocketBroadcaster:
    """WebSocket广播器 - 定期推送更新"""

    def __init__(self, manager: ConnectionManager, agent_manager: AgentManager, resource_monitor: ResourceMonitor):
        self.connection_manager = manager
        self.agent_manager = agent_manager
        self.resource_monitor = resource_monitor
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_agents: Dict[str, Dict] = {}
        self._last_log_lines: Dict[str, int] = {}

    async def start(self):
        """启动广播"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._broadcast_loop())

    async def stop(self):
        """停止广播"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _broadcast_loop(self):
        """广播循环"""
        while self._running:
            try:
                # 推送资源指标
                metrics = self.resource_monitor.get_current_metrics()
                if metrics:
                    await self.connection_manager.broadcast({
                        "type": "metrics",
                        "data": metrics.model_dump()
                    })

                # 推送Agent状态变化
                await self._broadcast_agent_updates()

                # 推送新日志
                await self._broadcast_log_updates()

                await asyncio.sleep(1.0)  # 每秒更新

            except Exception as e:
                print(f"Error in broadcast loop: {e}")
                await asyncio.sleep(1.0)

    async def _broadcast_agent_updates(self):
        """广播Agent状态更新"""
        agents = await self.agent_manager.get_agents()

        for agent in agents:
            agent_dict = {
                "id": agent.id,
                "name": agent.name,
                "state": agent.state.value,
                "pid": agent.pid,
                "uptime": agent.uptime,
                "last_error": agent.last_error,
            }

            # 检查状态是否变化
            if agent.id not in self._last_agents or self._last_agents[agent.id] != agent_dict:
                await self.connection_manager.broadcast({
                    "type": "agent_update",
                    "data": agent_dict
                })
                self._last_agents[agent.id] = agent_dict

    async def _broadcast_log_updates(self):
        """广播新日志"""
        agents = await self.agent_manager.get_agents()

        for agent in agents:
            if agent.state not in ["running", "error"]:
                continue

            logs = await self.agent_manager.get_agent_logs(agent.id, lines=100)
            last_line = self._last_log_lines.get(agent.id, 0)

            if len(logs) > last_line:
                new_logs = logs[last_line:]
                await self.connection_manager.broadcast({
                    "type": "log_update",
                    "data": {
                        "agent_id": agent.id,
                        "logs": new_logs
                    }
                })
                self._last_log_lines[agent.id] = len(logs)
