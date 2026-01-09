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


def test_get_runs_side_by_side(client):
    """Test getting side-by-side comparison with character-level diff."""
    response = client.get("/api/runs/show%20version/side_by_side")
    assert response.status_code == 200
    
    data = response.json()
    assert "devices" in data
    assert len(data["devices"]) == 2
    assert "has_diff" in data
    
    # Check first device
    device_a = data["devices"][0]
    assert "name" in device_a
    assert "run" in device_a
    assert "output_text" in device_a["run"]
    assert "output_html" in device_a["run"]
    
    # Check second device
    device_b = data["devices"][1]
    assert "name" in device_b
    assert "run" in device_b
    assert "output_text" in device_b["run"]
    assert "output_html" in device_b["run"]
    
    # Since Version 1.0 and Version 2.0 are different, should have diff
    assert data["has_diff"] is True


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


def test_sanitize_filename():
    """Test filename sanitization function."""
    from webapp.main import sanitize_filename
    
    # Normal cases - should pass through unchanged
    assert sanitize_filename("device1") == "device1"
    assert sanitize_filename("show_version") == "show_version"
    assert sanitize_filename("device-a.txt") == "device-a.txt"
    
    # Path traversal attempts - should be sanitized
    assert sanitize_filename("../etc/passwd") == ".._etc_passwd"
    assert sanitize_filename("../../secrets") == ".._.._secrets"
    assert sanitize_filename("/etc/passwd") == "_etc_passwd"
    
    # Special characters - should be replaced with underscores
    assert sanitize_filename("device/name") == "device_name"
    assert sanitize_filename("cmd with spaces") == "cmd_with_spaces"
    assert sanitize_filename("test:file") == "test_file"
    assert sanitize_filename("file|name") == "file_name"
    assert sanitize_filename("test*wild") == "test_wild"
    
    # Null bytes and other dangerous characters
    assert sanitize_filename("test\x00file") == "test_file"
    assert sanitize_filename("test\nfile") == "test_file"
    
    # Unicode characters - should be replaced
    assert sanitize_filename("device™") == "device_"
    assert sanitize_filename("测试设备") == "____"


def test_export_with_malicious_device_name(client):
    """Test that export endpoints sanitize device names to prevent path traversal."""
    # Add a device with a malicious name to the database
    db = Database('data/current.sqlite3')
    db.insert_run(
        device_name="../../../evil",
        command_text="show version",
        ts_epoch=1000003,
        output_text="Hacked",
        ok=True,
        duration_ms=100.0,
        original_line_count=5
    )
    db.close()
    
    # Test export - filename should be sanitized
    response = client.get("/api/export/run?command=show%20version&device=../../../evil&format=json")
    assert response.status_code == 200
    
    # Check that the filename is sanitized in the Content-Disposition header
    content_disposition = response.headers.get("Content-Disposition", "")
    assert "filename=" in content_disposition
    # The path traversal attempt should be sanitized
    assert "../" not in content_disposition
    assert ".._.._.._evil" in content_disposition


def test_export_with_malicious_command_name(client):
    """Test that export endpoints sanitize command names to prevent path traversal."""
    # Add a command with a malicious name to the database
    db = Database('data/current.sqlite3')
    db.insert_run(
        device_name="DeviceA",
        command_text="../../etc/passwd",
        ts_epoch=1000004,
        output_text="Hacked",
        ok=True,
        duration_ms=100.0,
        original_line_count=5
    )
    db.close()
    
    # Test export - filename should be sanitized
    response = client.get("/api/export/run?command=../../etc/passwd&device=DeviceA&format=json")
    assert response.status_code == 200
    
    # Check that the filename is sanitized in the Content-Disposition header
    content_disposition = response.headers.get("Content-Disposition", "")
    assert "filename=" in content_disposition
    # The path traversal attempt should be sanitized
    assert "../" not in content_disposition
    assert ".._.._etc_passwd" in content_disposition


def test_security_headers(client):
    """Test that security headers are present in responses."""
    response = client.get("/")
    
    # Check for security headers
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    
    # Test on API endpoint as well
    response = client.get("/api/commands")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


