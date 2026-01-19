"""Integration tests for end-to-end functionality.

These tests verify the complete flow from collector to database to webapp.
They test component interactions rather than isolated units.
"""

import os
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

from shared.config import Config
from shared.db import Database
from shared.filters import process_output


@pytest.fixture
def integration_config(tmp_path):
    """Create a test configuration for integration tests."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("""
interval_seconds: 1
ping_interval_seconds: 1
ping_window_seconds: 60
history_size: 5
max_output_lines: 100

global_filters:
  line_exclude_substrings:
    - "uptime"
  output_exclude_substrings:
    - "% Invalid"

commands:
  - name: "show_version"
    command_text: "show version"
  - name: "show_interfaces"
    command_text: "show interfaces"

devices:
  - name: "TestDevice1"
    host: "192.168.1.1"
    port: 22
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
    ping_host: "192.168.1.1"
  - name: "TestDevice2"
    host: "192.168.1.2"
    port: 22
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
    ping_host: "192.168.1.2"
""")

    # Set environment variable
    os.environ["TEST_PASSWORD"] = "testpass123"

    yield config_path

    # Cleanup
    if "TEST_PASSWORD" in os.environ:
        del os.environ["TEST_PASSWORD"]


@pytest.fixture
def integration_db(tmp_path):
    """Create a test database for integration tests."""
    db_path = tmp_path / "test.sqlite3"
    db = Database(str(db_path))
    yield db
    db.close()


class TestCollectorDatabaseIntegration:
    """Test collector -> database integration."""

    def test_collector_creates_database_schema(self, integration_db):
        """Test that collector initializes database with correct schema."""
        # Verify tables exist
        cursor = integration_db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}

        assert "devices" in tables
        assert "commands" in tables
        assert "runs" in tables
        assert "ping_samples" in tables

    def test_collector_stores_device_command_data(self, integration_db):
        """Test that collector can store device and command data."""
        # Simulate collector storing data
        device_id = integration_db.get_or_create_device("TestDevice1")
        command_id = integration_db.get_or_create_command("show version")

        # Store a run
        integration_db.insert_run(
            device_name="TestDevice1",
            command_text="show version",
            ts_epoch=int(time.time()),
            output_text="Cisco IOS Software, Version 15.0",
            ok=True,
            duration_ms=123.45,
            original_line_count=10,
        )

        # Verify data was stored using get_latest_runs (device_name, command_text)
        runs = integration_db.get_latest_runs("TestDevice1", "show version", limit=1)
        assert len(runs) == 1
        assert runs[0]["output_text"] == "Cisco IOS Software, Version 15.0"

    def test_collector_stores_ping_data(self, integration_db):
        """Test that collector can store ping samples."""
        # Store ping samples
        current_time = int(time.time())

        integration_db.insert_ping_sample(
            device_name="TestDevice1", ts_epoch=current_time - 10, ok=True, rtt_ms=5.2
        )

        integration_db.insert_ping_sample(
            device_name="TestDevice1",
            ts_epoch=current_time - 5,
            ok=False,
            error_message="Timeout",
        )

        # Verify data was stored
        samples = integration_db.get_ping_samples("TestDevice1", current_time - 60)
        assert len(samples) == 2
        # Samples are ordered newest first
        assert samples[0]["ok"] == 0  # Most recent (failed)
        assert samples[1]["ok"] == 1  # Older (succeeded)

    def test_history_cleanup_works(self, integration_db):
        """Test that old runs are cleaned up according to history_size."""
        history_size = 3

        # Set history_size on the database instance
        integration_db.history_size = history_size

        # Insert more runs than history_size
        for i in range(10):
            integration_db.insert_run(
                device_name="TestDevice1",
                command_text="show version",
                ts_epoch=int(time.time()) + i,
                output_text=f"Output {i}",
                ok=True,
                duration_ms=100.0,
                original_line_count=5,
            )

        # Get device and command IDs for cleanup
        device_id = integration_db.get_or_create_device("TestDevice1")
        command_id = integration_db.get_or_create_command("show version")

        # Cleanup old runs (private method needs device_id and command_id)
        integration_db._cleanup_old_runs(device_id, command_id)

        # Verify only history_size runs remain
        runs = integration_db.get_latest_runs("TestDevice1", "show version", limit=10)
        assert len(runs) == history_size


class TestEndToEndFlow:
    """Test complete end-to-end flow."""

    def test_config_to_database_to_webapp(self, integration_config, tmp_path):
        """Test complete flow: config -> collector simulation -> database -> webapp."""
        # 1. Load config
        config = Config(str(integration_config))
        assert len(config.get_devices()) == 2
        assert len(config.get_commands()) == 2

        # 2. Simulate collector storing data
        db_path = tmp_path / "current.sqlite3"
        db = Database(str(db_path))

        for device in config.get_devices():
            for command in config.get_commands():
                db.insert_run(
                    device_name=device["name"],
                    command_text=command["command_text"],
                    ts_epoch=int(time.time()),
                    output_text=f"Output from {device['name']} for {command['command_text']}",
                    ok=True,
                    duration_ms=100.0,
                    original_line_count=10,
                )

        # 3. Verify database has data
        runs = db.get_latest_runs("TestDevice1", "show version", limit=10)
        assert len(runs) >= 1

        db.close()

        # 4. Simulate webapp reading data
        db2 = Database(str(db_path))
        devices = db2.get_all_devices()
        commands = db2.get_all_commands()

        assert len(devices) == 2
        assert len(commands) == 2

        db2.close()

    def test_filtering_integration(self, integration_config, tmp_path):
        """Test that filters from config are applied in data flow."""
        config = Config(str(integration_config))

        # Get filters from config
        line_filters = config.get_command_line_exclusions("show version")
        output_filters = config.get_command_output_exclusions("show version")
        max_lines = config.get_max_output_lines()

        # Process output
        test_output = """System uptime: 5 days
Cisco IOS Software, Version 15.0
uptime is 5 days, 3 hours
Interface GigabitEthernet0/1
"""

        # process_output returns tuple: (output_text, is_filtered, is_truncated, original_line_count)
        output_text, is_filtered, is_truncated, original_line_count = process_output(
            test_output, line_filters, output_filters, max_lines
        )

        # Verify "uptime" lines are filtered out
        assert "uptime" not in output_text.lower()

    def test_atomic_database_update(self, tmp_path):
        """Test atomic database update mechanism."""
        # Create session database
        session_db_path = tmp_path / "session_123.sqlite3"
        session_db = Database(str(session_db_path))

        # Add data to session database
        session_db.insert_run(
            device_name="TestDevice1",
            command_text="show version",
            ts_epoch=int(time.time()),
            output_text="Test output",
            ok=True,
            duration_ms=100.0,
            original_line_count=5,
        )
        session_db.close()

        # Simulate atomic copy
        current_db_path = tmp_path / "current.sqlite3"
        tmp_db_path = tmp_path / "current.sqlite3.tmp"

        # Copy session to tmp
        import shutil

        shutil.copy(str(session_db_path), str(tmp_db_path))

        # Atomic rename
        if current_db_path.exists():
            current_db_path.unlink()
        tmp_db_path.rename(current_db_path)

        # Verify current database has data
        current_db = Database(str(current_db_path))
        runs = current_db.get_latest_runs("TestDevice1", "show version", limit=10)
        assert len(runs) == 1
        current_db.close()


class TestConcurrentAccess:
    """Test concurrent access scenarios."""

    def test_concurrent_read_access(self, integration_db):
        """Test multiple readers can access database simultaneously."""
        # Add some data
        integration_db.insert_run(
            device_name="TestDevice1",
            command_text="show version",
            ts_epoch=int(time.time()),
            output_text="Test output",
            ok=True,
            duration_ms=100.0,
            original_line_count=5,
        )

        # Create multiple database connections (read-only)
        db_path = integration_db.db_path

        readers = []
        for _ in range(5):
            reader = Database(db_path)
            readers.append(reader)

        # All readers should be able to read
        for reader in readers:
            runs = reader.get_latest_runs("TestDevice1", "show version", limit=10)
            assert len(runs) == 1
            reader.close()

    def test_database_remains_consistent(self, integration_db):
        """Test database maintains consistency during operations."""
        # Insert multiple runs
        for i in range(10):
            integration_db.insert_run(
                device_name="TestDevice1",
                command_text="show version",
                ts_epoch=int(time.time()) + i,
                output_text=f"Output {i}",
                ok=True,
                duration_ms=100.0,
                original_line_count=5,
            )

        # Verify all runs are retrievable
        runs = integration_db.get_latest_runs("TestDevice1", "show version", limit=20)
        assert len(runs) == 10

        # Verify they're in correct order (newest first)
        for i in range(len(runs) - 1):
            assert runs[i]["ts_epoch"] >= runs[i + 1]["ts_epoch"]


class TestErrorHandling:
    """Test error handling in integrated components."""

    def test_database_handles_missing_file(self, tmp_path):
        """Test database gracefully handles missing file."""
        # Try to open non-existent database
        # Database should be created
        db_path = tmp_path / "nonexistent.sqlite3"
        db = Database(str(db_path))

        # Should work without errors
        devices = db.get_all_devices()
        assert devices == []

        db.close()

    def test_config_validation_catches_errors(self, tmp_path):
        """Test that config validation catches errors before database operations."""
        # Create invalid config
        config_path = tmp_path / "invalid_config.yaml"
        config_path.write_text("""
interval_seconds: -5
commands:
  - command_text: "show version"
devices:
  - name: "Device1"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        # Should raise validation error
        with pytest.raises(ValueError, match="Invalid configuration"):
            Config(str(config_path))


class TestDataExport:
    """Test data export functionality integration."""

    def test_export_preserves_data_integrity(self, integration_db):
        """Test that exported data matches database data."""
        from shared.export import export_run_as_json

        # Add test data
        current_time = int(time.time())
        integration_db.insert_run(
            device_name="TestDevice1",
            command_text="show version",
            ts_epoch=current_time,
            output_text="Test output",
            ok=True,
            duration_ms=123.45,
            original_line_count=10,
            is_filtered=False,
            is_truncated=False,
        )

        # Get run from database
        runs = integration_db.get_latest_runs("TestDevice1", "show version", limit=1)
        run = runs[0]

        # Export and verify (export_run_as_json takes run dict, device, command)
        exported = export_run_as_json(run, "TestDevice1", "show version")

        import json

        data = json.loads(exported)

        assert data["output"] == "Test output"
        assert data["status"] == "success"
        assert data["duration_ms"] == 123.45
        assert data["device"] == "TestDevice1"
        assert data["command"] == "show version"
        assert data["is_filtered"] is False
        assert data["is_truncated"] is False
