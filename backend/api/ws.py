"""
WebSocket endpoint for real-time job status updates.

Clients connect to /ws/jobs and receive JSON messages when any
job's status changes.  The API-side listener picks up notifications
published to Redis (channel ``job:updates``) by the Celery worker
and forwards them to every connected WebSocket.

If Redis is unavailable the WebSocket still works -- clients just
won't receive push updates until Redis comes back (the frontend
falls back to HTTP polling on disconnect).
"""

import asyncio
import json
import logging
from typing import Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Track active WebSocket connections and broadcast messages."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info("WebSocket client connected (%d total)", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(self._connections))

    async def broadcast(self, message: dict) -> None:
        """Send *message* to every connected client, dropping dead ones."""
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


async def websocket_endpoint(ws: WebSocket) -> None:
    """Handle a single WebSocket client lifetime."""
    await manager.connect(ws)
    try:
        while True:
            # Keep the connection alive by reading (clients may send pings)
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ---------------------------------------------------------------------------
# Redis subscriber (runs as a FastAPI background task on startup)
# ---------------------------------------------------------------------------

REDIS_CHANNEL = "job:updates"

_subscriber_task: Optional[asyncio.Task] = None


async def _redis_subscriber() -> None:
    """Subscribe to Redis ``job:updates`` and forward to WebSocket clients."""
    try:
        import redis.asyncio as aioredis
    except ImportError:
        logger.warning("redis.asyncio not available -- WebSocket push disabled")
        return

    redis_url = _get_redis_url()
    backoff = 1

    while True:
        try:
            r = aioredis.from_url(redis_url, decode_responses=True)
            pubsub = r.pubsub()
            await pubsub.subscribe(REDIS_CHANNEL)
            logger.info("Subscribed to Redis channel '%s'", REDIS_CHANNEL)
            backoff = 1

            async for raw_message in pubsub.listen():
                if raw_message["type"] != "message":
                    continue
                try:
                    data = json.loads(raw_message["data"])
                    await manager.broadcast(data)
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Bad message on %s: %s", REDIS_CHANNEL, raw_message["data"])

        except Exception as exc:
            logger.warning("Redis subscriber error (retry in %ds): %s", backoff, exc)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)


def _get_redis_url() -> str:
    import os
    return os.environ.get(
        "CELERY_BROKER_URL",
        "redis://localhost:6379/0",
    )


def start_subscriber() -> None:
    """Start the Redis subscriber as an asyncio task (call during app startup)."""
    global _subscriber_task
    _subscriber_task = asyncio.create_task(_redis_subscriber())
    logger.info("Started Redis subscriber background task")


def stop_subscriber() -> None:
    """Cancel the subscriber (call during app shutdown)."""
    global _subscriber_task
    if _subscriber_task:
        _subscriber_task.cancel()
        _subscriber_task = None


# ---------------------------------------------------------------------------
# Helper for the worker side (sync publish to Redis)
# ---------------------------------------------------------------------------

def publish_job_update(job: Dict) -> None:
    """Publish a job update to Redis so the WS endpoint can broadcast it.

    Call this from the Celery worker after updating the DB.
    Fails silently if Redis is unreachable.
    """
    try:
        import redis as sync_redis
        r = sync_redis.from_url(_get_redis_url())
        message = {"type": "job_update", "job": job}
        r.publish(REDIS_CHANNEL, json.dumps(message))
    except Exception as exc:
        logger.debug("Could not publish job update to Redis: %s", exc)
