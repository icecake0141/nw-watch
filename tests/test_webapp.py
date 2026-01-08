"""Tests for web application API."""
import pytest
from fastapi.testclient import TestClient
import tempfile
import os
from pathlib import Path
from shared.db import Database


@pytest.fixture
def test_db():
    """Create a test database with sample data."""
    fd, path = tempfile.mkstemp(suffix='.sqlite3')
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
        original_line_count=10
    )
    
    db.insert_run(
        device_name="DeviceB",
        command_text="show version",
        ts_epoch=1000001,
        output_text="Version 2.0",
        ok=True,
        duration_ms=150.0,
        original_line_count=12
    )
    
    db.insert_ping_sample(
        device_name="DeviceA",
        ts_epoch=1000000,
        ok=True,
        rtt_ms=10.5
    )
    
    db.close()
    
    yield path
    
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def client(test_db, monkeypatch):
    """Create test client with mocked database."""
    # Move test db to expected location
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    current_db = data_dir / 'current.sqlite3'
    
    # Copy test db to current.sqlite3
    import shutil
    shutil.copy2(test_db, current_db)
    
    from webapp.main import app
    client = TestClient(app)
    
    yield client
    
    # Cleanup
    if current_db.exists():
        current_db.unlink()


def test_index_page(client):
    """Test main page loads."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Network Watch" in response.text


def test_get_commands(client):
    """Test getting list of commands."""
    response = client.get("/api/commands")
    assert response.status_code == 200
    
    data = response.json()
    assert "commands" in data
    assert "show version" in data["commands"]


def test_get_devices(client):
    """Test getting list of devices."""
    response = client.get("/api/devices")
    assert response.status_code == 200
    
    data = response.json()
    assert "devices" in data
    assert "DeviceA" in data["devices"]
    assert "DeviceB" in data["devices"]


def test_get_runs(client):
    """Test getting command runs."""
    response = client.get("/api/runs/show%20version")
    assert response.status_code == 200
    
    data = response.json()
    assert "runs" in data
    assert "DeviceA" in data["runs"]
    assert "DeviceB" in data["runs"]
    
    # Check DeviceA run
    device_a_runs = data["runs"]["DeviceA"]
    assert len(device_a_runs) > 0
    assert device_a_runs[0]["output_text"] == "Version 1.0"


def test_get_runs_single_device(client):
    """Test getting runs for single device."""
    response = client.get("/api/runs/show%20version?device=DeviceA")
    assert response.status_code == 200
    
    data = response.json()
    assert "runs" in data
    assert "DeviceA" in data["runs"]
    assert "DeviceB" not in data["runs"]


def test_get_history_diff(client):
    """Test getting history diff."""
    # Add another run to have history
    db = Database('data/current.sqlite3')
    db.insert_run(
        device_name="DeviceA",
        command_text="show version",
        ts_epoch=1000002,
        output_text="Version 1.1",
        ok=True,
        duration_ms=100.0,
        original_line_count=10
    )
    db.close()
    
    response = client.get("/api/diff/history?command=show%20version&device=DeviceA")
    assert response.status_code == 200
    
    data = response.json()
    assert "diff" in data
    assert "has_diff" in data


def test_get_device_diff(client):
    """Test getting diff between devices."""
    response = client.get("/api/diff/devices?command=show%20version&device_a=DeviceA&device_b=DeviceB")
    assert response.status_code == 200
    
    data = response.json()
    assert "diff" in data
    assert "has_diff" in data


def test_get_ping_status(client):
    """Test getting ping status."""
    response = client.get("/api/ping?window_seconds=60")
    assert response.status_code == 200
    
    data = response.json()
    assert "ping_status" in data
    assert "DeviceA" in data["ping_status"]
    
    device_a_status = data["ping_status"]["DeviceA"]
    assert "status" in device_a_status
    assert "success_rate" in device_a_status
    assert "total_samples" in device_a_status


def test_get_config(client):
    """Test getting configuration."""
    response = client.get("/api/config")
    assert response.status_code == 200
    
    data = response.json()
    assert "run_poll_interval_seconds" in data
    assert "ping_poll_interval_seconds" in data
    assert "ping_window_seconds" in data


def test_api_without_database():
    """Test API endpoints when database doesn't exist."""
    # Ensure no current.sqlite3 exists
    current_db = Path('data/current.sqlite3')
    if current_db.exists():
        current_db.unlink()
    
    from webapp.main import app
    client = TestClient(app)
    
    response = client.get("/api/commands")
    assert response.status_code == 200
    data = response.json()
    assert data["commands"] == []
    
    response = client.get("/api/devices")
    assert response.status_code == 200
    data = response.json()
    assert data["devices"] == []
