"""Tests for command scheduling functionality."""

import pytest
import time
from pathlib import Path

from croniter import croniter

from shared.config import Config


def test_command_schedule_parsing(tmp_path, monkeypatch):
    """Test parsing of cron schedules from config."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
interval_seconds: 5
commands:
  - name: "hourly_command"
    command_text: "show version"
    schedule: "0 * * * *"  # Every hour
  - name: "every_5_min"
    command_text: "show interfaces"
    schedule: "*/5 * * * *"  # Every 5 minutes
  - name: "no_schedule"
    command_text: "show ip route"
    # No schedule - should use interval_seconds

devices:
  - name: "Device1"
    host: "1.1.1.1"
    username: "admin"
    password_env_key: "PW"
    device_type: "cisco_ios"
"""
    )

    monkeypatch.setenv("PW", "secret")
    config = Config(str(cfg_path))

    # Test schedule retrieval
    assert config.get_command_schedule("show version") == "0 * * * *"
    assert config.get_command_schedule("show interfaces") == "*/5 * * * *"
    assert config.get_command_schedule("show ip route") is None


def test_command_schedule_validation(tmp_path, monkeypatch):
    """Test that invalid cron schedules are rejected."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
interval_seconds: 5
commands:
  - name: "invalid_schedule"
    command_text: "show version"
    schedule: "invalid cron expression"

devices:
  - name: "Device1"
    host: "1.1.1.1"
    username: "admin"
    password_env_key: "PW"
    device_type: "cisco_ios"
"""
    )

    monkeypatch.setenv("PW", "secret")

    # Invalid schedule should raise ValueError during config loading
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_croniter_next_execution():
    """Test croniter calculates next execution correctly."""
    # Test every 5 minutes
    base_time = time.time()
    cron = croniter("*/5 * * * *", base_time)
    next_run = cron.get_next()

    # Next run should be within 5 minutes
    assert next_run > base_time
    assert next_run <= base_time + 300  # 5 minutes = 300 seconds

    # Test hourly
    cron = croniter("0 * * * *", base_time)
    next_run = cron.get_next()

    # Next run should be within 1 hour
    assert next_run > base_time
    assert next_run <= base_time + 3600  # 1 hour = 3600 seconds


def test_backward_compatibility(tmp_path, monkeypatch):
    """Test that commands without schedule still work with interval_seconds."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
interval_seconds: 10
commands:
  - name: "legacy_command"
    command_text: "show version"
    # No schedule field

devices:
  - name: "Device1"
    host: "1.1.1.1"
    username: "admin"
    password_env_key: "PW"
    device_type: "cisco_ios"
"""
    )

    monkeypatch.setenv("PW", "secret")
    config = Config(str(cfg_path))

    # Command without schedule should return None
    assert config.get_command_schedule("show version") is None
    # Should still have interval_seconds configured
    assert config.get_interval_seconds() == 10


def test_mixed_schedules(tmp_path, monkeypatch):
    """Test configuration with mixed scheduled and interval-based commands."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
interval_seconds: 5
commands:
  - name: "scheduled_cmd"
    command_text: "show version"
    schedule: "0 */6 * * *"  # Every 6 hours
  - name: "interval_cmd"
    command_text: "show interfaces"
    # Uses interval_seconds
  - name: "frequent_cmd"
    command_text: "show ip int brief"
    schedule: "* * * * *"  # Every minute

devices:
  - name: "Device1"
    host: "1.1.1.1"
    username: "admin"
    password_env_key: "PW"
    device_type: "cisco_ios"
"""
    )

    monkeypatch.setenv("PW", "secret")
    config = Config(str(cfg_path))

    # Verify each command has correct schedule
    assert config.get_command_schedule("show version") == "0 */6 * * *"
    assert config.get_command_schedule("show interfaces") is None
    assert config.get_command_schedule("show ip int brief") == "* * * * *"
