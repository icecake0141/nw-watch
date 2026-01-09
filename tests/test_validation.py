"""Tests for configuration validation."""
import pytest
from pathlib import Path

from shared.config import Config


def test_valid_config(tmp_path):
    """Test that a valid configuration passes validation."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
interval_seconds: 5
ping_interval_seconds: 1
ping_window_seconds: 60
history_size: 10
max_output_lines: 500

global_filters:
  line_exclude_substrings:
    - "Temperature"
  output_exclude_substrings:
    - "% Invalid"

commands:
  - name: "show_version"
    command_text: "show version"

devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    port: 22
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
    ping_host: "192.168.1.1"
"""
    )
    
    config = Config(str(cfg_path))
    assert config.get_interval_seconds() == 5
    assert config.get_history_size() == 10


def test_negative_interval_seconds(tmp_path):
    """Test that negative interval_seconds is rejected."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
interval_seconds: -5
commands:
  - command_text: "show version"
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
"""
    )
    
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_zero_history_size(tmp_path):
    """Test that zero history_size is rejected."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
history_size: 0
commands:
  - command_text: "show version"
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
"""
    )
    
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_negative_max_output_lines(tmp_path):
    """Test that negative max_output_lines is rejected."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
max_output_lines: -100
commands:
  - command_text: "show version"
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
"""
    )
    
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_invalid_cron_schedule(tmp_path):
    """Test that invalid cron schedule is rejected."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
commands:
  - command_text: "show version"
    schedule: "invalid cron expression"
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
"""
    )
    
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_valid_cron_schedule(tmp_path):
    """Test that valid cron schedule is accepted."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
commands:
  - command_text: "show version"
    schedule: "0 */6 * * *"
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
"""
    )
    
    config = Config(str(cfg_path))
    assert config.get_command_schedule("show version") == "0 */6 * * *"


def test_empty_command_text(tmp_path):
    """Test that empty command_text is rejected."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
commands:
  - command_text: ""
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
"""
    )
    
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_invalid_port(tmp_path):
    """Test that invalid port is rejected."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
commands:
  - command_text: "show version"
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    port: 99999
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
"""
    )
    
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_invalid_ping_host(tmp_path):
    """Test that ping_host with command injection is rejected."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
commands:
  - command_text: "show version"
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
    ping_host: "192.168.1.1; rm -rf /"
"""
    )
    
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_valid_ping_host_formats(tmp_path):
    """Test that various valid ping_host formats are accepted."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
commands:
  - command_text: "show version"
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
    ping_host: "192.168.1.1"
  - name: "DeviceB"
    host: "example.com"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
    ping_host: "example.com"
  - name: "DeviceC"
    host: "2001:db8::1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
    ping_host: "2001:db8::1"
"""
    )
    
    config = Config(str(cfg_path))
    devices = config.get_devices()
    assert devices[0]["ping_host"] == "192.168.1.1"
    assert devices[1]["ping_host"] == "example.com"
    assert devices[2]["ping_host"] == "2001:db8::1"


def test_no_devices(tmp_path):
    """Test that configuration with no devices is rejected."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
commands:
  - command_text: "show version"
devices: []
"""
    )
    
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_no_commands(tmp_path):
    """Test that configuration with no commands is rejected."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
commands: []
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
"""
    )
    
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_duplicate_device_names(tmp_path):
    """Test that duplicate device names are rejected."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
commands:
  - command_text: "show version"
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
  - name: "DeviceA"
    host: "192.168.1.2"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
"""
    )
    
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_duplicate_command_texts(tmp_path):
    """Test that duplicate command_text values are rejected."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
commands:
  - command_text: "show version"
  - command_text: "show version"
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
"""
    )
    
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_device_without_password(tmp_path):
    """Test that device without password_env_key or password is rejected."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
commands:
  - command_text: "show version"
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    username: "admin"
    device_type: "cisco_ios"
"""
    )
    
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_websocket_config_validation(tmp_path):
    """Test WebSocket configuration validation."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
websocket:
  enabled: true
  ping_interval: -5
commands:
  - command_text: "show version"
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
"""
    )
    
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))


def test_ssh_config_validation(tmp_path):
    """Test SSH configuration validation."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
ssh:
  connection_timeout: -100
commands:
  - command_text: "show version"
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
"""
    )
    
    with pytest.raises(ValueError, match="Invalid configuration"):
        Config(str(cfg_path))
