"""Tests for command scheduling functionality."""

import pytest
import time
from pathlib import Path

from shared.config import Config


def test_command_interval_parsing(tmp_path, monkeypatch):
    """Test parsing of interval_seconds from config."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text("""
interval_seconds: 5
commands:
  - name: "long_interval"
    command_text: "show version"
    interval_seconds: 30  # Every 30 seconds
  - name: "short_interval"
    command_text: "show interfaces"
    interval_seconds: 10  # Every 10 seconds
  - name: "no_interval"
    command_text: "show ip route"
    # No interval_seconds - should use global interval_seconds

devices:
  - name: "Device1"
    host: "1.1.1.1"
    username: "admin"
    password_env_key: "PW"
    device_type: "cisco_ios"
""")

    monkeypatch.setenv("PW", "secret")
    config = Config(str(cfg_path))

    # Test interval retrieval
    assert config.get_command_interval("show version") == 30
    assert config.get_command_interval("show interfaces") == 10
    assert config.get_command_interval("show ip route") is None


def test_command_interval_validation_min(tmp_path, monkeypatch):
    """Test that intervals below 5 seconds are rejected."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text("""
interval_seconds: 5
commands:
  - name: "too_fast"
    command_text: "show version"
    interval_seconds: 3  # Too low, below minimum of 5

devices:
  - name: "Device1"
    host: "1.1.1.1"
    username: "admin"
    password_env_key: "PW"
    device_type: "cisco_ios"
""")

    monkeypatch.setenv("PW", "secret")

    # Invalid interval should raise ValueError during config loading
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_command_interval_validation_max(tmp_path, monkeypatch):
    """Test that intervals above 60 seconds are rejected."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text("""
interval_seconds: 5
commands:
  - name: "too_slow"
    command_text: "show version"
    interval_seconds: 120  # Too high, above maximum of 60

devices:
  - name: "Device1"
    host: "1.1.1.1"
    username: "admin"
    password_env_key: "PW"
    device_type: "cisco_ios"
""")

    monkeypatch.setenv("PW", "secret")

    # Invalid interval should raise ValueError during config loading
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_interval_validation_error_message(tmp_path, monkeypatch):
    """Test that interval validation provides clear error messages."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text("""
interval_seconds: 5
commands:
  - name: "invalid_interval"
    command_text: "show version"
    interval_seconds: 100  # Out of range

devices:
  - name: "Device1"
    host: "1.1.1.1"
    username: "admin"
    password_env_key: "PW"
    device_type: "cisco_ios"
""")

    monkeypatch.setenv("PW", "secret")

    # Check that error message is clear and informative
    with pytest.raises(ValueError) as exc_info:
        Config(str(cfg_path))

    error_msg = str(exc_info.value)
    # Should mention the configuration is invalid
    assert "Invalid configuration" in error_msg


def test_backward_compatibility(tmp_path, monkeypatch):
    """Test that commands without interval_seconds still work with global interval_seconds."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text("""
interval_seconds: 10
commands:
  - name: "legacy_command"
    command_text: "show version"
    # No interval_seconds field

devices:
  - name: "Device1"
    host: "1.1.1.1"
    username: "admin"
    password_env_key: "PW"
    device_type: "cisco_ios"
""")

    monkeypatch.setenv("PW", "secret")
    config = Config(str(cfg_path))

    # Command without interval_seconds should return None
    assert config.get_command_interval("show version") is None
    # Should still have global interval_seconds configured
    assert config.get_interval_seconds() == 10


def test_mixed_intervals(tmp_path, monkeypatch):
    """Test configuration with mixed interval and global-based commands."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text("""
interval_seconds: 5
commands:
  - name: "custom_interval_cmd"
    command_text: "show version"
    interval_seconds: 30  # Every 30 seconds
  - name: "global_interval_cmd"
    command_text: "show interfaces"
    # Uses global interval_seconds
  - name: "fast_interval_cmd"
    command_text: "show ip int brief"
    interval_seconds: 5  # Minimum allowed

devices:
  - name: "Device1"
    host: "1.1.1.1"
    username: "admin"
    password_env_key: "PW"
    device_type: "cisco_ios"
""")

    monkeypatch.setenv("PW", "secret")
    config = Config(str(cfg_path))

    # Verify each command has correct interval
    assert config.get_command_interval("show version") == 30
    assert config.get_command_interval("show interfaces") is None
    assert config.get_command_interval("show ip int brief") == 5


def test_interval_boundary_values(tmp_path, monkeypatch):
    """Test that boundary values (5 and 60) are accepted."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text("""
interval_seconds: 5
commands:
  - name: "min_interval"
    command_text: "show version"
    interval_seconds: 5  # Minimum boundary
  - name: "max_interval"
    command_text: "show interfaces"
    interval_seconds: 60  # Maximum boundary

devices:
  - name: "Device1"
    host: "1.1.1.1"
    username: "admin"
    password_env_key: "PW"
    device_type: "cisco_ios"
""")

    monkeypatch.setenv("PW", "secret")
    config = Config(str(cfg_path))

    # Both boundary values should be accepted
    assert config.get_command_interval("show version") == 5
    assert config.get_command_interval("show interfaces") == 60
