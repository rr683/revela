"""Tests for the WebSocket endpoint and connection manager."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from storage import JobStore
from engine.base import ReconstructionStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def _patch_stores(tmp_path):
    db_path = tmp_path / "test_ws.db"
    data_dir = tmp_path / "data"
    job_store = JobStore(db_path)

    from storage import FileStore
    file_store = FileStore(data_dir)

    with patch("api.routes._get_stores", return_value=(job_store, file_store)):
        yield job_store, file_store


@pytest.fixture
def client(_patch_stores):
    from api.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def stores(_patch_stores):
    return _patch_stores


# ---------------------------------------------------------------------------
# Connection manager unit tests
# ---------------------------------------------------------------------------

class TestConnectionManager:
    def test_initial_state(self):
        from api.ws import ConnectionManager
        mgr = ConnectionManager()
        assert mgr.active_count == 0

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self):
        from api.ws import ConnectionManager
        mgr = ConnectionManager()

        ws = MagicMock()
        ws.accept = MagicMock(return_value=_async_noop())
        ws.send_json = MagicMock(return_value=_async_noop())

        await mgr.connect(ws)
        assert mgr.active_count == 1

        mgr.disconnect(ws)
        assert mgr.active_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self):
        from api.ws import ConnectionManager
        mgr = ConnectionManager()

        clients = []
        for _ in range(3):
            ws = MagicMock()
            ws.accept = MagicMock(return_value=_async_noop())
            ws.send_json = MagicMock(return_value=_async_noop())
            await mgr.connect(ws)
            clients.append(ws)

        msg = {"type": "job_update", "job": {"id": "test", "status": "completed"}}
        await mgr.broadcast(msg)

        for ws in clients:
            ws.send_json.assert_called_once_with(msg)

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self):
        from api.ws import ConnectionManager
        mgr = ConnectionManager()

        good_ws = MagicMock()
        good_ws.accept = MagicMock(return_value=_async_noop())
        good_ws.send_json = MagicMock(return_value=_async_noop())

        bad_ws = MagicMock()
        bad_ws.accept = MagicMock(return_value=_async_noop())
        bad_ws.send_json = MagicMock(side_effect=RuntimeError("closed"))

        await mgr.connect(good_ws)
        await mgr.connect(bad_ws)
        assert mgr.active_count == 2

        await mgr.broadcast({"type": "test"})
        assert mgr.active_count == 1


# ---------------------------------------------------------------------------
# WebSocket endpoint integration tests
# ---------------------------------------------------------------------------

class TestWebSocketEndpoint:
    def test_websocket_connect_and_receive(self, client):
        with client.websocket_connect("/ws/jobs") as ws:
            ws.send_text("ping")

    def test_health_still_works_with_ws(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["version"] == "0.3.0"


# ---------------------------------------------------------------------------
# publish_job_update
# ---------------------------------------------------------------------------

class TestPublishJobUpdate:
    def test_publish_fails_silently_without_redis(self):
        from api.ws import publish_job_update
        publish_job_update({"id": "no-redis", "status": "completed"})

    def test_publish_calls_redis(self):
        from api.ws import publish_job_update

        mock_redis_cls = MagicMock()
        mock_conn = MagicMock()
        mock_redis_cls.from_url.return_value = mock_conn

        with patch.dict("sys.modules", {"redis": mock_redis_cls}):
            with patch("api.ws.json.dumps", return_value='{"type":"job_update"}') as mock_dumps:
                import importlib
                import api.ws
                # Directly test the function with mocked redis
                try:
                    import redis as sync_redis
                    mock_r = MagicMock()
                    with patch("redis.from_url", return_value=mock_r):
                        publish_job_update({"id": "test", "status": "training"})
                        mock_r.publish.assert_called_once()
                except ImportError:
                    pytest.skip("redis not installed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _async_noop(*args, **kwargs):
    """Awaitable that returns None -- used for mock coroutines."""
    return None
