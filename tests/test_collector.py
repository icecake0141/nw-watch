# Copyright 2026 icecake0141
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# This file was created or modified with the assistance of an AI (Large Language Model).
# Review required for correctness, security, and licensing.
"""Tests for collector graceful shutdown."""

import asyncio
import os
import signal
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from nw_watch.collector.main import Collector, main
from nw_watch.shared.config import Config


def test_collector_stop_method():
    """Test that the collector stop method properly cleans up resources."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
ping_interval_seconds: 1
history_size: 10
max_output_lines: 500

commands:
  - name: "test_cmd"
    command_text: "show version"

devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        # Set the password environment variable
        os.environ["TEST_PASSWORD"] = "test"

        config = Config(str(cfg_path))

        # Change to tmp_dir so data folder is created there
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_dir)

            collector = Collector(config)

            # Verify collector is initialized
            assert collector.running is True
            assert collector.executor is not None
            assert collector.db is not None

            # Call stop method
            collector.stop()

            # Verify cleanup
            assert collector.running is False
            # Executor should be shutdown (we can't easily verify this without internal state)
            # DB should be closed (we can't easily verify this without internal state)
        finally:
            os.chdir(original_cwd)


def test_signal_handler_registration():
    """Test that signal handlers are properly registered."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
ping_interval_seconds: 1
history_size: 10
max_output_lines: 500

commands:
  - name: "test_cmd"
    command_text: "show version"

devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        os.environ["TEST_PASSWORD"] = "test"

        with patch("nw_watch.collector.main.asyncio.run") as mock_asyncio_run:
            with patch("nw_watch.collector.main.signal.signal") as mock_signal:
                with patch("sys.argv", ["collector", "--config", str(cfg_path)]):
                    # Mock asyncio.run to return immediately instead of running the loop
                    mock_asyncio_run.return_value = None

                    # Change to tmp_dir so data folder is created there
                    original_cwd = Path.cwd()
                    try:
                        os.chdir(tmp_dir)

                        main()

                        # Verify signal handlers were registered
                        assert mock_signal.call_count >= 2

                        # Check that SIGTERM and SIGINT were registered
                        call_args_list = [
                            call[0] for call in mock_signal.call_args_list
                        ]
                        signals_registered = [args[0] for args in call_args_list]

                        assert signal.SIGTERM in signals_registered
                        assert signal.SIGINT in signals_registered
                    finally:
                        os.chdir(original_cwd)


def test_signal_handler_calls_stop():
    """Test that the signal handler properly calls collector.stop()."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
ping_interval_seconds: 1
history_size: 10
max_output_lines: 500

commands:
  - name: "test_cmd"
    command_text: "show version"

devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        os.environ["TEST_PASSWORD"] = "test"

        with patch("nw_watch.collector.main.asyncio.run") as mock_asyncio_run:
            with patch("sys.argv", ["collector", "--config", str(cfg_path)]):
                # Mock asyncio.run to return immediately
                mock_asyncio_run.return_value = None

                # Change to tmp_dir so data folder is created there
                original_cwd = Path.cwd()
                try:
                    os.chdir(tmp_dir)

                    # Capture the collector instance from within main()
                    original_collector_init = Collector.__init__
                    collector_instance = None

                    def capture_collector(self, *args, **kwargs):
                        nonlocal collector_instance
                        original_collector_init(self, *args, **kwargs)
                        collector_instance = self

                    with patch.object(Collector, "__init__", capture_collector):
                        main()

                        # Verify collector was created
                        assert collector_instance is not None

                        # Now simulate signal handling by directly calling the handler
                        # Get the signal handler that was registered
                        current_sigterm_handler = signal.getsignal(signal.SIGTERM)

                        # The handler should be our signal_handler function
                        # We can't easily test sys.exit(0), but we can verify the stop was called
                        with patch.object(collector_instance, "stop") as mock_stop:
                            with patch("sys.exit") as mock_exit:
                                # Call the signal handler
                                current_sigterm_handler(signal.SIGTERM, None)

                                # Verify stop was called
                                mock_stop.assert_called_once()
                                # Verify sys.exit was called
                                mock_exit.assert_called_once_with(0)
                finally:
                    os.chdir(original_cwd)


def test_multi_device_command_execution():
    """Test that commands are executed for all devices, not just the first one.

    This is a regression test for the bug where command_next_run is indexed
    only by command name, causing second device commands to be skipped.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 5
ping_interval_seconds: 1
history_size: 10
max_output_lines: 500

commands:
  - name: "show_version"
    command_text: "show version"
  - name: "show_interfaces"
    command_text: "show interfaces"

devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
  - name: "DeviceB"
    host: "192.168.1.2"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")

        os.environ["TEST_PASSWORD"] = "test"

        config = Config(str(cfg_path))

        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_dir)

            collector = Collector(config)

            # Mock execute_command to track calls
            execution_log = []

            # Patch execute_command for all device collectors
            for device_name, device_collector in collector.device_collectors.items():
                # Create a closure to capture device_name
                def make_mock(dev_name):
                    def mock_exec(command, db):
                        execution_log.append({"device": dev_name, "command": command})

                    return mock_exec

                device_collector.execute_command = make_mock(device_name)

            # Run collect_commands once
            asyncio.run(collector.collect_commands())

            # Verify that commands were executed for BOTH devices
            # Expected: 2 devices × 2 commands = 4 executions
            assert (
                len(execution_log) == 4
            ), f"Expected 4 executions, got {len(execution_log)}"

            # Verify DeviceA executions
            devicea_execs = [e for e in execution_log if e["device"] == "DeviceA"]
            assert (
                len(devicea_execs) == 2
            ), f"DeviceA should have 2 executions, got {len(devicea_execs)}"

            # Verify DeviceB executions (this is the bug - it would be 0)
            deviceb_execs = [e for e in execution_log if e["device"] == "DeviceB"]
            assert (
                len(deviceb_execs) == 2
            ), f"DeviceB should have 2 executions, got {len(deviceb_execs)}"

            # Verify all commands were executed
            commands_executed = {e["command"] for e in execution_log}
            assert "show version" in commands_executed
            assert "show interfaces" in commands_executed

            collector.stop()

        finally:
            os.chdir(original_cwd)
            if "TEST_PASSWORD" in os.environ:
                del os.environ["TEST_PASSWORD"]
