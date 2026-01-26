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
"""Tests for collector signal handling and graceful shutdown."""

import asyncio
import os
import signal
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nw_watch.collector.main import Collector, async_main
from nw_watch.shared.config import Config


@pytest.mark.asyncio
async def test_sighup_handler_registration():
    """Test that SIGHUP handler is properly registered."""
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
        original_cwd = Path.cwd()

        try:
            os.chdir(tmp_dir)

            # Track signal handler registrations
            registered_signals = []
            original_add_signal_handler = None

            async def mock_run(self):
                """Mock run method that doesn't actually run."""
                # Just wait a bit to ensure signal handlers are registered
                await asyncio.sleep(0.1)

            with patch.object(Collector, "run", mock_run):
                # Get the event loop before async_main starts
                loop = asyncio.get_running_loop()

                def track_signal_handler(sig, callback):
                    registered_signals.append(sig)
                    # Don't actually register to avoid interference
                    return None

                # Patch add_signal_handler
                original_add_signal_handler = loop.add_signal_handler
                loop.add_signal_handler = track_signal_handler

                try:
                    # Run async_main with timeout to prevent hanging
                    await asyncio.wait_for(async_main(str(cfg_path)), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
                finally:
                    # Restore original handler
                    loop.add_signal_handler = original_add_signal_handler

            # Verify all three signals were registered
            assert signal.SIGTERM in registered_signals, "SIGTERM should be registered"
            assert signal.SIGINT in registered_signals, "SIGINT should be registered"
            assert signal.SIGHUP in registered_signals, "SIGHUP should be registered"

        finally:
            os.chdir(original_cwd)
            if "TEST_PASSWORD" in os.environ:
                del os.environ["TEST_PASSWORD"]


@pytest.mark.asyncio
async def test_signal_cancels_async_tasks():
    """Test that signal handler cancels async tasks properly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 60
ping_interval_seconds: 60
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
        original_cwd = Path.cwd()

        try:
            os.chdir(tmp_dir)

            config = Config(str(cfg_path))
            collector = Collector(config)

            # Mock the device command execution to avoid actual SSH
            for device_collector in collector.device_collectors.values():
                device_collector.execute_command = MagicMock()
                device_collector.ping_device = MagicMock()

            # Start the collector in a task
            run_task = asyncio.create_task(collector.run())

            # Give it a moment to start the loops
            await asyncio.sleep(0.5)

            # Verify the task is running
            assert not run_task.done(), "Task should be running"

            # Simulate signal by cancelling all tasks (what the signal handler does)
            collector.running = False
            for task in asyncio.all_tasks():
                if task != asyncio.current_task():
                    task.cancel()

            # Wait for cancellation to propagate
            try:
                await asyncio.wait_for(run_task, timeout=2.0)
            except asyncio.CancelledError:
                pass  # Expected

            # Verify the task completed (was cancelled)
            assert run_task.done(), "Task should be done after cancellation"

            # Cleanup
            collector.stop()

        finally:
            os.chdir(original_cwd)
            if "TEST_PASSWORD" in os.environ:
                del os.environ["TEST_PASSWORD"]


@pytest.mark.asyncio
async def test_collector_terminates_on_signal():
    """Test that collector terminates when signal is received."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "config.yaml"
        cfg_path.write_text("""
interval_seconds: 60
ping_interval_seconds: 60
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
        original_cwd = Path.cwd()

        try:
            os.chdir(tmp_dir)

            config = Config(str(cfg_path))
            collector = Collector(config)

            # Mock the device operations
            for device_collector in collector.device_collectors.values():
                device_collector.execute_command = MagicMock()
                device_collector.ping_device = MagicMock()

            # Track when loops check running flag
            loop_iterations = {"command": 0, "ping": 0}

            original_collect_commands = collector.collect_commands
            original_collect_pings = collector.collect_pings

            async def mock_collect_commands():
                loop_iterations["command"] += 1
                await original_collect_commands()

            async def mock_collect_pings():
                loop_iterations["ping"] += 1
                await original_collect_pings()

            collector.collect_commands = mock_collect_commands
            collector.collect_pings = mock_collect_pings

            # Start the collector
            run_task = asyncio.create_task(collector.run())

            # Wait for at least one iteration
            for _ in range(50):  # 5 seconds max
                await asyncio.sleep(0.1)
                if loop_iterations["command"] > 0 and loop_iterations["ping"] > 0:
                    break

            # Verify loops started
            assert loop_iterations["command"] > 0, "Command loop should have started"
            assert loop_iterations["ping"] > 0, "Ping loop should have started"

            # Trigger shutdown by setting flag and cancelling
            collector.running = False
            run_task.cancel()

            # Wait for task to complete
            try:
                await asyncio.wait_for(run_task, timeout=2.0)
            except asyncio.CancelledError:
                pass  # Expected

            # Verify task is done
            assert run_task.done(), "Task should be completed"

            # Cleanup
            collector.stop()

        finally:
            os.chdir(original_cwd)
            if "TEST_PASSWORD" in os.environ:
                del os.environ["TEST_PASSWORD"]
