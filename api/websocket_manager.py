"""
WebSocket Manager for Live Recognition Events
==============================================

Manages WebSocket connections for real-time face recognition
event streaming to dashboard clients.

Features:
    - Per-camera event streams
    - Global recognition event broadcast
    - Connection management with authentication
    - Heartbeat/ping for connection health
    - Event buffering for slow clients

Usage::

    from api.websocket_manager import ws_manager

    # Broadcast a recognition event
    await ws_manager.broadcast_event({
        "type": "recognition",
        "student_name": "Alice",
        "camera_id": 1,
        "confidence": 0.95,
        "timestamp": "2026-07-27T12:00:00Z"
    })
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ClientConnection:
    """Represents a connected WebSocket client."""

    def __init__(
        self,
        websocket: WebSocket,
        user_id: int,
        username: str,
        roles: List[str],
        camera_filter: Optional[int] = None,
    ):
        self.websocket = websocket
        self.user_id = user_id
        self.username = username
        self.roles = roles
        self.camera_filter = camera_filter
        self.connected_at = time.time()
        self.last_pong = time.time()
        self.events_sent = 0

    @property
    def is_alive(self) -> bool:
        """Check if connection is alive (pong within 30s)."""
        return (time.time() - self.last_pong) < 30

    def __repr__(self) -> str:
        return f"<Client {self.username} cam={self.camera_filter}>"


class WebSocketManager:
    """Manages WebSocket connections and event broadcasting."""

    def __init__(self):
        self._connections: List[ClientConnection] = []
        self._lock = asyncio.Lock()
        self._event_buffer: List[dict] = []
        self._max_buffer_size = 100
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def connect(
        self,
        websocket: WebSocket,
        user_id: int,
        username: str,
        roles: List[str],
        camera_filter: Optional[int] = None,
    ) -> ClientConnection:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()

        client = ClientConnection(
            websocket=websocket,
            user_id=user_id,
            username=username,
            roles=roles,
            camera_filter=camera_filter,
        )

        async with self._lock:
            self._connections.append(client)

        logger.info(
            "WebSocket connected: %s (total: %d)",
            client, len(self._connections)
        )

        # Send recent events buffer to new client
        for event in self._event_buffer:
            if self._should_send_to_client(client, event):
                try:
                    await websocket.send_json(event)
                    client.events_sent += 1
                except Exception:
                    break

        # Start heartbeat if not running
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        return client

    async def disconnect(self, client: ClientConnection) -> None:
        """Remove a client connection."""
        async with self._lock:
            if client in self._connections:
                self._connections.remove(client)

        logger.info(
            "WebSocket disconnected: %s (remaining: %d)",
            client, len(self._connections)
        )

    async def broadcast_event(self, event: dict) -> int:
        """
        Broadcast a recognition event to all connected clients.

        Args:
            event: Event dict with at least 'type' and 'timestamp' keys.

        Returns:
            Number of clients the event was sent to.
        """
        # Add server timestamp if missing
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Buffer the event
        self._event_buffer.append(event)
        if len(self._event_buffer) > self._max_buffer_size:
            self._event_buffer = self._event_buffer[-self._max_buffer_size:]

        sent_count = 0
        dead_clients = []

        async with self._lock:
            for client in self._connections:
                if not self._should_send_to_client(client, event):
                    continue

                try:
                    await client.websocket.send_json(event)
                    client.events_sent += 1
                    sent_count += 1
                except Exception:
                    dead_clients.append(client)

        # Clean up dead connections
        for client in dead_clients:
            await self.disconnect(client)

        return sent_count

    async def send_personal(self, user_id: int, event: dict) -> bool:
        """Send an event to a specific user."""
        async with self._lock:
            for client in self._connections:
                if client.user_id == user_id:
                    try:
                        await client.websocket.send_json(event)
                        return True
                    except Exception:
                        await self.disconnect(client)
        return False

    def _should_send_to_client(self, client: ClientConnection, event: dict) -> bool:
        """Determine if an event should be sent to a client."""
        # Camera filter
        if client.camera_filter is not None:
            event_camera = event.get("camera_id")
            if event_camera is not None and event_camera != client.camera_filter:
                return False

        # Role-based filtering (e.g., students only see their own events)
        event_type = event.get("type", "")
        if "student" in client.roles and event_type == "recognition":
            # Students only see events about themselves
            event_user_id = event.get("user_id")
            if event_user_id is not None and event_user_id != client.user_id:
                return False

        return True

    async def _heartbeat_loop(self) -> None:
        """Send periodic pings and clean up dead connections."""
        while True:
            try:
                await asyncio.sleep(15)
                dead = []

                async with self._lock:
                    for client in self._connections:
                        if not client.is_alive:
                            dead.append(client)
                            continue
                        try:
                            asyncio.create_task(
                                client.websocket.send_json({"type": "ping"})
                            )
                        except Exception:
                            dead.append(client)

                for client in dead:
                    await self.disconnect(client)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Heartbeat error: %s", exc)
                await asyncio.sleep(5)

    @property
    def connection_count(self) -> int:
        """Number of active connections."""
        return len(self._connections)

    def status(self) -> dict:
        """Return connection status summary."""
        return {
            "active_connections": self.connection_count,
            "buffered_events": len(self._event_buffer),
            "clients": [
                {
                    "username": c.username,
                    "camera_filter": c.camera_filter,
                    "events_sent": c.events_sent,
                    "connected_at": c.connected_at,
                }
                for c in self._connections
            ],
        }


# Global instance
ws_manager = WebSocketManager()
