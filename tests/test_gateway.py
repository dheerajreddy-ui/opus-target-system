"""Tests for the FastAPI gateway."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock anthropic before any app imports
sys.modules.setdefault("anthropic", MagicMock())

from httpx import AsyncClient, ASGITransport


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator to avoid real API calls."""
    mock = AsyncMock()
    mock.process = AsyncMock(return_value="Mock response from orchestrator.")
    return mock


@pytest.fixture
def client(mock_orchestrator):
    """Create test client with mocked orchestrator (sync fixture)."""
    import src.bluestack.app as app_module
    app_module.orchestrator = mock_orchestrator
    from src.bluestack.app import app
    return app


@pytest.mark.asyncio
async def test_health_endpoint(client):
    transport = ASGITransport(app=client)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "defense_level" in data


@pytest.mark.asyncio
async def test_chat_endpoint(client):
    transport = ASGITransport(app=client)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/chat", json={
            "message": "Hello, what products do you have?",
            "session_id": "test-session"
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "response" in data
    assert data["session_id"] == "test-session"


@pytest.mark.asyncio
async def test_chat_missing_message(client):
    transport = ASGITransport(app=client)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/chat", json={"session_id": "test"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_reset_endpoint(client):
    transport = ASGITransport(app=client)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/reset", json={"session_id": "test-session"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_defense_level_change(client):
    transport = ASGITransport(app=client)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/admin/defense-level", json={"level": 2})
    assert resp.status_code == 200
    assert resp.json()["defense_level"] == 2


@pytest.mark.asyncio
async def test_invalid_defense_level(client):
    transport = ASGITransport(app=client)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/admin/defense-level", json={"level": 99})
    assert resp.status_code == 400
