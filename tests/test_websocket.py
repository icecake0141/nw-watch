"""Tests for WebSocket functionality."""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from shared.config import Config
from shared.db import Database


@pytest.fixture
def test_db():
    """Create a test database with sample data."""
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)

    db = Database(path)

    # Insert test data
    db.insert_run(
        device_name="DeviceA",
        command_text="show version",
        ts_epoch=1000000,
        output_text="Version 1.0",
        ok=True,
        duration_ms=100.0,
        original_line_count=10,
    )

    db.close()

    yield path

    Path(path).unlink(missing_ok=True)


@pytest.fixture
def client(test_db, monkeypatch):
    """Create test client with mocked database."""
    # Move test db to expected location
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    current_db = data_dir / "current.sqlite3"

    # Copy test db to current.sqlite3
    shutil.copy2(test_db, current_db)

    from webapp.main import app

    client = TestClient(app)

    yield client

    # Cleanup
    if current_db.exists():
        current_db.unlink()


def test_websocket_endpoint(client):
    """Test WebSocket endpoint connectivity."""
    with client.websocket_connect("/ws") as websocket:
        # Send ping
        websocket.send_text("ping")
        # Should receive pong
        data = websocket.receive_text()
        assert data == "pong"


def test_api_config_includes_websocket_flag(client):
    """Test that /api/config includes websocket_enabled flag."""
    response = client.get("/api/config")
    assert response.status_code == 200

    data = response.json()
    assert "websocket_enabled" in data
    # Default should be False when no config exists
    assert isinstance(data["websocket_enabled"], bool)


def test_websocket_manager_broadcast():
    """Test WebSocket connection manager broadcast functionality."""
    from webapp.websocket_manager import ConnectionManager

    manager = ConnectionManager()

    async def test_broadcast():
        # Test broadcast with no connections (should not error)
        await manager.broadcast({"type": "test", "data": "hello"})

        # Verify no connections
        assert len(manager.active_connections) == 0

    asyncio.run(test_broadcast())


def test_config_websocket_settings():
    """Test Config class WebSocket methods."""
    # Create a test config file
    fd, config_path = tempfile.mkstemp(suffix=".yaml")
    os.close(fd)

    try:
        # Write test config
        with open(config_path, "w") as f:
            f.write("""
interval_seconds: 5
websocket:
  enabled: true
  ping_interval: 30
""")

        config = Config(config_path)
        assert config.get_websocket_enabled() is True
        assert config.get_websocket_ping_interval() == 30

        # Test defaults when websocket section is missing
        with open(config_path, "w") as f:
            f.write("interval_seconds: 5\n")

        config2 = Config(config_path)
        assert config2.get_websocket_enabled() is False
        assert config2.get_websocket_ping_interval() == 20  # default

    finally:
        Path(config_path).unlink(missing_ok=True)


def test_websocket_manager_connect_disconnect():
    """Test WebSocket connection manager connect/disconnect."""
    from webapp.websocket_manager import ConnectionManager

    manager = ConnectionManager()

    async def test_connections():
        # Create mock WebSocket
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()

        # Test connect
        await manager.connect(mock_ws)
        assert mock_ws in manager.active_connections
        assert len(manager.active_connections) == 1

        # Test disconnect
        await manager.disconnect(mock_ws)
        assert mock_ws not in manager.active_connections
        assert len(manager.active_connections) == 0

    asyncio.run(test_connections())
