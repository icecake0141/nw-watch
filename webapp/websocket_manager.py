"""WebSocket connection manager for real-time updates."""
import asyncio
import json
import logging
from typing import Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts updates."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info("WebSocket client connected. Total connections: %d", len(self.active_connections))

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info("WebSocket client disconnected. Total connections: %d", len(self.active_connections))

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return

        message_json = json.dumps(message)
        disconnected = set()

        async with self._lock:
            connections = list(self.active_connections)

        for websocket in connections:
            try:
                await websocket.send_text(message_json)
            except Exception as exc:
                logger.warning("Error sending to WebSocket client: %s", exc)
                disconnected.add(websocket)

        if disconnected:
            async with self._lock:
                self.active_connections -= disconnected
            logger.info("Removed %d disconnected clients", len(disconnected))

    async def broadcast_update(self, update_type: str, data: dict = None):
        """Broadcast an update notification to all clients."""
        message = {
            "type": update_type,
            "timestamp": asyncio.get_event_loop().time(),
        }
        if data:
            message["data"] = data
        await self.broadcast(message)


# Global connection manager instance
manager = ConnectionManager()
