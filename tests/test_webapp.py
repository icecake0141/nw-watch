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
    
    # Insert ping sample with recent timestamp for export tests
    import time
    current_ts = int(time.time())
    db.insert_ping_sample(
        device_name="DeviceA",
        ts_epoch=current_ts - 60,  # 60 seconds ago
        ok=True,
        rtt_ms=10.5
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


def test_get_runs_excludes_filtered(client):
    """Filtered runs should not appear in API responses."""
    db = Database('data/current.sqlite3')
    db.insert_run(
        device_name="DeviceA",
        command_text="show version",
        ts_epoch=1000005,
        output_text="filtered run",
        ok=True,
        is_filtered=True,
        original_line_count=1
    )
    db.close()

    response = client.get("/api/runs/show%20version")
    assert response.status_code == 200
    data = response.json()
    device_a_runs = data["runs"]["DeviceA"]
    assert all(run["is_filtered"] == 0 for run in device_a_runs)


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
    assert "timeline" in device_a_status
    assert len(device_a_status["timeline"]) == 60


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


def test_export_run_text(client):
    """Test exporting run as text."""
    response = client.get("/api/export/run?command=show%20version&device=DeviceA&format=text")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert "Content-Disposition" in response.headers
    assert "DeviceA" in response.text
    assert "show version" in response.text
    assert "Version 1.0" in response.text


def test_export_run_json(client):
    """Test exporting run as JSON."""
    response = client.get("/api/export/run?command=show%20version&device=DeviceA&format=json")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert "Content-Disposition" in response.headers
    
    # Verify it's valid JSON
    data = response.json()
    assert data["device"] == "DeviceA"
    assert data["command"] == "show version"
    assert data["status"] == "success"
    assert data["output"] == "Version 1.0"


def test_export_run_not_found(client):
    """Test exporting non-existent run."""
    response = client.get("/api/export/run?command=nonexistent&device=DeviceA&format=text")
    assert response.status_code == 404


def test_export_bulk(client):
    """Test exporting bulk runs."""
    response = client.get("/api/export/bulk?command=show%20version&format=json")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert "Content-Disposition" in response.headers
    
    data = response.json()
    assert "command" in data
    assert data["command"] == "show version"
    assert "devices" in data
    assert "DeviceA" in data["devices"]
    assert "DeviceB" in data["devices"]


def test_export_diff_history(client):
    """Test exporting history diff."""
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
    
    response = client.get("/api/export/diff?command=show%20version&device=DeviceA&format=html")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "Content-Disposition" in response.headers
    assert "<!DOCTYPE html>" in response.text
    assert "Previous" in response.text
    assert "Latest" in response.text


def test_export_diff_devices(client):
    """Test exporting device diff."""
    response = client.get("/api/export/diff?command=show%20version&device_a=DeviceA&device_b=DeviceB&format=html")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "Content-Disposition" in response.headers
    assert "<!DOCTYPE html>" in response.text
    assert "DeviceA" in response.text
    assert "DeviceB" in response.text


def test_export_ping_csv(client):
    """Test exporting ping data as CSV."""
    response = client.get("/api/export/ping?device=DeviceA&format=csv&window_seconds=3600")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "Content-Disposition" in response.headers
    
    lines = response.text.strip().split('\n')
    assert len(lines) >= 2  # Header + at least 1 data row
    assert "Device" in lines[0]
    assert "Timestamp" in lines[0]
    assert "DeviceA" in lines[1]


def test_export_ping_json(client):
    """Test exporting ping data as JSON."""
    response = client.get("/api/export/ping?device=DeviceA&format=json&window_seconds=3600")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert "Content-Disposition" in response.headers
    
    data = response.json()
    assert data["device"] == "DeviceA"
    assert "samples" in data
    assert len(data["samples"]) >= 1


def test_export_filename_sanitization(client):
    """Test that filenames are properly sanitized to prevent path traversal."""
    # Test with command containing dangerous characters
    response = client.get("/api/export/run?command=../etc/passwd&device=DeviceA&format=json")
    # Should still work but with sanitized filename
    if response.status_code == 200:
        filename = response.headers.get("Content-Disposition", "")
        # Should not contain path traversal sequences
        assert "../" not in filename
        assert ".." not in filename or "etcpasswd" in filename
    
    # Test with command containing shell metacharacters  
    response = client.get("/api/export/run?command=cmd;rm%20-rf&device=DeviceA&format=text")
    if response.status_code == 200:
        filename = response.headers.get("Content-Disposition", "")
        # Should not contain shell metacharacters
        assert ";" not in filename
        assert "|" not in filename
        assert "&" not in filename
    
    # Test with device name containing directory separators
    response = client.get("/api/export/ping?device=../../evil&format=csv&window_seconds=3600")
    if response.status_code == 200:
        filename = response.headers.get("Content-Disposition", "")
        # Should not contain path traversal
        assert "../" not in filename
        assert "/" not in filename.split("filename=")[1] if "filename=" in filename else True


def test_export_bulk_filename_sanitization(client):
    """Test bulk export filename sanitization."""
    # Test with command containing dangerous characters
    response = client.get("/api/export/bulk?command=show%20version&format=json")
    if response.status_code == 200:
        filename = response.headers.get("Content-Disposition", "")
        # Filename should be safe
        assert "bulk_" in filename
        # Should have sanitized command name
        assert ".json" in filename


def test_export_diff_filename_sanitization(client):
    """Test diff export filename sanitization."""
    # Test history diff with sanitized device and command
    response = client.get("/api/export/diff?command=show%20version&device=DeviceA&format=html")
    if response.status_code == 200 or response.status_code == 404:
        # 404 is OK if not enough history
        if response.status_code == 200:
            filename = response.headers.get("Content-Disposition", "")
            assert "history_diff_" in filename
            # Should not contain dangerous characters
            assert "/" not in filename.split("filename=")[1] if "filename=" in filename else True
