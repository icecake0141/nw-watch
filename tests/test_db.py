"""Tests for database operations."""

import pytest
import tempfile
import os
from pathlib import Path
from nw_watch.shared.db import Database


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)

    db = Database(path)
    yield db

    db.close()
    Path(path).unlink(missing_ok=True)


def test_database_initialization(temp_db):
    """Test database schema initialization."""
    cursor = temp_db.conn.cursor()

    # Check that tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    assert "devices" in tables
    assert "commands" in tables
    assert "runs" in tables
    assert "ping_samples" in tables


def test_get_or_create_device(temp_db):
    """Test device creation and retrieval."""
    device_id1 = temp_db.get_or_create_device("Device1")
    assert device_id1 > 0

    # Should return same ID for same device
    device_id2 = temp_db.get_or_create_device("Device1")
    assert device_id1 == device_id2

    # Different device should get different ID
    device_id3 = temp_db.get_or_create_device("Device2")
    assert device_id3 != device_id1


def test_get_or_create_command(temp_db):
    """Test command creation and retrieval."""
    cmd_id1 = temp_db.get_or_create_command("show version")
    assert cmd_id1 > 0

    # Should return same ID for same command
    cmd_id2 = temp_db.get_or_create_command("show version")
    assert cmd_id1 == cmd_id2

    # Different command should get different ID
    cmd_id3 = temp_db.get_or_create_command("show interfaces")
    assert cmd_id3 != cmd_id1


def test_insert_run(temp_db):
    """Test inserting command run."""
    temp_db.insert_run(
        device_name="Device1",
        command_text="show version",
        ts_epoch=1000000,
        output_text="version output",
        ok=True,
        duration_ms=100.5,
        is_filtered=False,
        is_truncated=False,
        original_line_count=10,
    )

    runs = temp_db.get_latest_runs("Device1", "show version", limit=10)
    assert len(runs) == 1

    run = runs[0]
    assert run["ts_epoch"] == 1000000
    assert run["output_text"] == "version output"
    assert run["ok"] == 1
    assert run["duration_ms"] == 100.5
    assert run["is_filtered"] == 0
    assert run["is_truncated"] == 0
    assert run["original_line_count"] == 10


def test_insert_run_with_error(temp_db):
    """Test inserting failed run."""
    temp_db.insert_run(
        device_name="Device1",
        command_text="show version",
        ts_epoch=1000000,
        output_text="",
        ok=False,
        error_message="Connection timeout",
        duration_ms=5000.0,
        original_line_count=0,
    )

    runs = temp_db.get_latest_runs("Device1", "show version", limit=10)
    assert len(runs) == 1

    run = runs[0]
    assert run["ok"] == 0
    assert run["error_message"] == "Connection timeout"


def test_cleanup_old_runs(temp_db):
    """Test that old runs are cleaned up."""
    # Insert 15 runs
    for i in range(15):
        temp_db.insert_run(
            device_name="Device1",
            command_text="show version",
            ts_epoch=1000000 + i,
            output_text=f"output {i}",
            ok=True,
            original_line_count=10,
        )

    # Should only keep 10 most recent
    runs = temp_db.get_latest_runs("Device1", "show version", limit=20)
    assert len(runs) == 10

    # Should have the most recent ones (timestamps 1000005-1000014)
    assert runs[0]["ts_epoch"] == 1000014
    assert runs[-1]["ts_epoch"] == 1000005


def test_filtered_runs_excluded_by_default(temp_db):
    """Filtered runs should not be returned unless requested."""
    temp_db.insert_run(
        device_name="Device1",
        command_text="show version",
        ts_epoch=1000000,
        output_text="filtered output",
        ok=True,
        is_filtered=True,
        original_line_count=1,
    )

    # Default excludes filtered
    runs = temp_db.get_latest_runs("Device1", "show version", limit=5)
    assert runs == []

    # Explicitly include filtered
    runs_with_filtered = temp_db.get_latest_runs(
        "Device1", "show version", limit=5, include_filtered=True
    )
    assert len(runs_with_filtered) == 1
    assert runs_with_filtered[0]["is_filtered"] == 1


def test_get_latest_run(temp_db):
    """Test getting single latest run."""
    temp_db.insert_run(
        device_name="Device1",
        command_text="show version",
        ts_epoch=1000000,
        output_text="old output",
        ok=True,
        original_line_count=5,
    )

    temp_db.insert_run(
        device_name="Device1",
        command_text="show version",
        ts_epoch=1000001,
        output_text="new output",
        ok=True,
        original_line_count=5,
    )

    run = temp_db.get_latest_run("Device1", "show version")
    assert run is not None
    assert run["output_text"] == "new output"
    assert run["ts_epoch"] == 1000001


def test_get_all_commands(temp_db):
    """Test getting all commands."""
    temp_db.get_or_create_command("show version")
    temp_db.get_or_create_command("show interfaces")
    temp_db.get_or_create_command("show ip route")

    commands = temp_db.get_all_commands()
    assert len(commands) == 3
    assert "show version" in commands
    assert "show interfaces" in commands
    assert "show ip route" in commands


def test_get_all_devices(temp_db):
    """Test getting all devices."""
    temp_db.get_or_create_device("Device1")
    temp_db.get_or_create_device("Device2")
    temp_db.get_or_create_device("Device3")

    devices = temp_db.get_all_devices()
    assert len(devices) == 3
    assert "Device1" in devices
    assert "Device2" in devices
    assert "Device3" in devices


def test_insert_ping_sample(temp_db):
    """Test inserting ping sample."""
    temp_db.insert_ping_sample(
        device_name="Device1", ts_epoch=1000000, ok=True, rtt_ms=10.5
    )

    samples = temp_db.get_ping_samples("Device1", since_ts=999999)
    assert len(samples) == 1

    sample = samples[0]
    assert sample["ts_epoch"] == 1000000
    assert sample["ok"] == 1
    assert sample["rtt_ms"] == 10.5
    assert sample["error_message"] is None


def test_insert_ping_sample_failure(temp_db):
    """Test inserting failed ping sample."""
    temp_db.insert_ping_sample(
        device_name="Device1", ts_epoch=1000000, ok=False, error_message="Timeout"
    )

    samples = temp_db.get_ping_samples("Device1", since_ts=999999)
    assert len(samples) == 1

    sample = samples[0]
    assert sample["ok"] == 0
    assert sample["error_message"] == "Timeout"
    assert sample["rtt_ms"] is None


def test_get_ping_samples_time_filter(temp_db):
    """Test ping samples time filtering."""
    # Insert samples at different times
    for i in range(10):
        temp_db.insert_ping_sample(
            device_name="Device1", ts_epoch=1000000 + i, ok=True, rtt_ms=10.0 + i
        )

    # Get only recent samples
    samples = temp_db.get_ping_samples("Device1", since_ts=1000005)
    assert len(samples) == 5

    # Should be ordered by timestamp descending
    assert samples[0]["ts_epoch"] == 1000009
    assert samples[-1]["ts_epoch"] == 1000005
