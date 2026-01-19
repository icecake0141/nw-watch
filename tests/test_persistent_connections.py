"""Tests for persistent SSH connection functionality."""

import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from nw_watch.collector.main import DeviceCollector
from nw_watch.shared.config import Config
from nw_watch.shared.db import Database


def test_device_collector_persistent_connections_enabled():
    """Test that persistent connections are enabled by default."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
commands:
  - name: "test"
    command_text: "show version"
devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        os.environ["TEST_PASSWORD"] = "test"
        config = Config(str(cfg_path))

        device_config = config.get_devices()[0]
        collector = DeviceCollector(device_config, config)

        assert collector.persistent_connections_enabled is True
        assert collector._connection is None
        assert collector._connection_lock is not None


def test_device_collector_persistent_connections_disabled():
    """Test that persistent connections can be disabled."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
ssh:
  persistent_connections: false
commands:
  - name: "test"
    command_text: "show version"
devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        os.environ["TEST_PASSWORD"] = "test"
        config = Config(str(cfg_path))

        device_config = config.get_devices()[0]
        collector = DeviceCollector(device_config, config)

        assert collector.persistent_connections_enabled is False


def test_ssh_config_defaults():
    """Test that SSH configuration has correct defaults."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
commands:
  - name: "test"
    command_text: "show version"
devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        config = Config(str(cfg_path))

        assert config.get_persistent_connections_enabled() is True
        assert config.get_connection_timeout() == 100
        assert config.get_max_reconnect_attempts() == 3
        assert config.get_reconnect_backoff_base() == 1.0


def test_ssh_config_custom_values():
    """Test that SSH configuration can be customized."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
ssh:
  persistent_connections: false
  connection_timeout: 60
  max_reconnect_attempts: 5
  reconnect_backoff_base: 2.0
commands:
  - name: "test"
    command_text: "show version"
devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        config = Config(str(cfg_path))

        assert config.get_persistent_connections_enabled() is False
        assert config.get_connection_timeout() == 60
        assert config.get_max_reconnect_attempts() == 5
        assert config.get_reconnect_backoff_base() == 2.0


def test_connection_params_generation():
    """Test that connection parameters are correctly generated."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
ssh:
  connection_timeout: 60
commands:
  - name: "test"
    command_text: "show version"
devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    port: 2222
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        os.environ["TEST_PASSWORD"] = "mypassword"
        config = Config(str(cfg_path))

        device_config = config.get_devices()[0]
        collector = DeviceCollector(device_config, config)

        params = collector._get_connection_params()

        assert params["device_type"] == "cisco_ios"
        assert params["host"] == "192.168.1.1"
        assert params["port"] == 2222
        assert params["username"] == "admin"
        assert params["password"] == "mypassword"
        assert params["timeout"] == 60


def test_connection_lock_is_thread_safe():
    """Test that connection lock ensures thread safety."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
commands:
  - name: "test"
    command_text: "show version"
devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        os.environ["TEST_PASSWORD"] = "test"
        config = Config(str(cfg_path))

        device_config = config.get_devices()[0]
        collector = DeviceCollector(device_config, config)

        # Test that the lock exists and has lock methods
        assert hasattr(collector._connection_lock, "acquire")
        assert hasattr(collector._connection_lock, "release")

        # Test that we can acquire and release the lock
        assert collector._connection_lock.acquire(blocking=False)
        collector._connection_lock.release()


def test_close_method_closes_connection():
    """Test that close() properly closes the connection."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
commands:
  - name: "test"
    command_text: "show version"
devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        os.environ["TEST_PASSWORD"] = "test"
        config = Config(str(cfg_path))

        device_config = config.get_devices()[0]
        collector = DeviceCollector(device_config, config)

        # Mock a connection
        mock_connection = MagicMock()
        collector._connection = mock_connection

        # Call close
        collector.close()

        # Verify disconnect was called
        mock_connection.disconnect.assert_called_once()

        # Verify connection is None
        assert collector._connection is None


def test_close_method_handles_errors():
    """Test that close() handles errors gracefully."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
commands:
  - name: "test"
    command_text: "show version"
devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        os.environ["TEST_PASSWORD"] = "test"
        config = Config(str(cfg_path))

        device_config = config.get_devices()[0]
        collector = DeviceCollector(device_config, config)

        # Mock a connection that raises an error on disconnect
        mock_connection = MagicMock()
        mock_connection.disconnect.side_effect = Exception("Disconnect error")
        collector._connection = mock_connection

        # Call close - should not raise exception
        collector.close()

        # Verify connection is None even after error
        assert collector._connection is None


def test_is_connection_alive_with_no_connection():
    """Test that _is_connection_alive returns False when no connection exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
commands:
  - name: "test"
    command_text: "show version"
devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        os.environ["TEST_PASSWORD"] = "test"
        config = Config(str(cfg_path))

        device_config = config.get_devices()[0]
        collector = DeviceCollector(device_config, config)

        assert collector._is_connection_alive() is False


def test_is_connection_alive_with_working_connection():
    """Test that _is_connection_alive returns True for working connection."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
commands:
  - name: "test"
    command_text: "show version"
devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        os.environ["TEST_PASSWORD"] = "test"
        config = Config(str(cfg_path))

        device_config = config.get_devices()[0]
        collector = DeviceCollector(device_config, config)

        # Mock a working connection
        mock_connection = MagicMock()
        mock_connection.find_prompt.return_value = "Router#"
        collector._connection = mock_connection

        assert collector._is_connection_alive() is True


def test_is_connection_alive_with_dead_connection():
    """Test that _is_connection_alive returns False for dead connection."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
commands:
  - name: "test"
    command_text: "show version"
devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        os.environ["TEST_PASSWORD"] = "test"
        config = Config(str(cfg_path))

        device_config = config.get_devices()[0]
        collector = DeviceCollector(device_config, config)

        # Mock a dead connection
        mock_connection = MagicMock()
        mock_connection.find_prompt.side_effect = Exception("Connection lost")
        collector._connection = mock_connection

        assert collector._is_connection_alive() is False


def test_execute_command_with_persistent_connection():
    """Test command execution with persistent connections."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
commands:
  - name: "test"
    command_text: "show version"
devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        os.environ["TEST_PASSWORD"] = "test"
        config = Config(str(cfg_path))

        # Create database
        db_path = Path(tmp_dir) / "test.db"
        db = Database(str(db_path))

        device_config = config.get_devices()[0]
        collector = DeviceCollector(device_config, config)

        # Mock the connection
        with patch("nw_watch.collector.main.ConnectHandler") as mock_handler:
            mock_connection = MagicMock()
            mock_connection.send_command.return_value = "Version output"
            mock_connection.find_prompt.return_value = "Router#"
            mock_handler.return_value = mock_connection

            # Execute command twice
            collector.execute_command("show version", db)
            collector.execute_command("show version", db)

            # Verify connection was created only once
            assert mock_handler.call_count == 1

            # Verify commands were executed
            assert mock_connection.send_command.call_count == 2

        db.close()


def test_execute_command_without_persistent_connection():
    """Test command execution without persistent connections (legacy mode)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
ssh:
  persistent_connections: false
commands:
  - name: "test"
    command_text: "show version"
devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        os.environ["TEST_PASSWORD"] = "test"
        config = Config(str(cfg_path))

        # Create database
        db_path = Path(tmp_dir) / "test.db"
        db = Database(str(db_path))

        device_config = config.get_devices()[0]
        collector = DeviceCollector(device_config, config)

        # Mock the connection
        with patch("nw_watch.collector.main.ConnectHandler") as mock_handler:
            mock_connection = MagicMock()
            mock_connection.send_command.return_value = "Version output"
            mock_handler.return_value = mock_connection

            # Execute command twice
            collector.execute_command("show version", db)
            collector.execute_command("show version", db)

            # Verify connection was created twice (not persistent)
            assert mock_handler.call_count == 2

            # Verify disconnect was called twice
            assert mock_connection.disconnect.call_count == 2

        db.close()
