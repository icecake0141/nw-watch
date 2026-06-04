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
"""Network device data collector."""

import argparse
import asyncio
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException

from nw_watch.shared.config import Config
from nw_watch.shared.control_state import (
    DEFAULT_CONTROL_STATE,
    clear_collector_pid,
    read_control_state,
    write_collector_pid,
    update_control_state,
)
from nw_watch.shared.db import Database
from nw_watch.shared.debug import log_ssh_session, setup_debug_file_logging
from nw_watch.shared.filters import process_output

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
setup_debug_file_logging()
logger = logging.getLogger(__name__)
PING_HOST_PATTERN = re.compile(r"^[a-zA-Z0-9._:-]+$")
InitialCommand = Dict[str, Optional[str]]


def normalize_initial_command(command: Any) -> InitialCommand:
    """Normalize legacy and structured initial command config."""
    if isinstance(command, str):
        if not command.strip():
            raise ValueError("initial_commands must not contain empty commands")
        return {"command_text": command, "expect_string": None}

    if isinstance(command, dict):
        command_text = command.get("command_text")
        expect_string = command.get("expect_string")
        if not isinstance(command_text, str) or not command_text.strip():
            raise ValueError("initial command command_text must not be empty")
        if expect_string is not None and (
            not isinstance(expect_string, str) or not expect_string.strip()
        ):
            raise ValueError("initial command expect_string must be a non-empty string")
        return {"command_text": command_text, "expect_string": expect_string}

    raise ValueError(
        "initial_commands entries must be strings or objects with command_text"
    )


def classify_command_error_detail(error: Exception) -> tuple[str, str]:
    """Return a troubleshooting category and user-facing command error message."""
    error_text = str(error).strip()
    error_text_lower = error_text.lower()

    if isinstance(error, NetmikoAuthenticationException):
        return "ssh_authentication_failed", "Authentication Failed"

    if (
        "no route to host" in error_text_lower
        or "network is unreachable" in error_text_lower
    ):
        return "network_unreachable", "Network Unreachable"

    if "host is unreachable" in error_text_lower:
        return "host_unreachable", "Host Unreachable"

    if "connection refused" in error_text_lower:
        return "ssh_connection_refused", "Connection Refused"

    if (
        "name or service not known" in error_text_lower
        or "temporary failure in name resolution" in error_text_lower
    ):
        return "dns_resolution_failed", "DNS Resolution Failed"

    if (
        isinstance(error, NetmikoTimeoutException)
        or "timed out" in error_text_lower
        or "timeout" in error_text_lower
    ):
        return "ssh_timeout", "Connection Timed Out"

    if any(
        marker in error_text_lower
        for marker in (
            "connection lost",
            "connection reset",
            "connection closed",
            "socket is closed",
            "session closed",
            "broken pipe",
            "eof",
            "disconnect",
        )
    ):
        return "ssh_disconnected", "Disconnected"

    return "command_failed", error_text or "Command Failed"


def classify_command_error(error: Exception) -> str:
    """Return a user-facing command error message."""
    return classify_command_error_detail(error)[1]


def classify_ping_error(returncode: int, stdout: str, stderr: str) -> str:
    """Return a granular ping failure message for UI and logs."""
    detail = f"{stderr}\n{stdout}".strip().lower()
    if "unknown host" in detail or "name or service not known" in detail:
        return "DNS Resolution Failed"
    if "network is unreachable" in detail:
        return "Network Unreachable"
    if "no route to host" in detail:
        return "No Route to Host"
    if "host is down" in detail or "host unreachable" in detail:
        return "Host Unreachable"
    if "100% packet loss" in detail or "request timeout" in detail:
        return "No Ping Reply"
    return f"Ping Failed (exit={returncode})"


def ping_target(db: Database, target_name: str, ping_host: str) -> None:
    """Ping a host and store the result under the target name."""
    ts_epoch = int(time.time())

    if not PING_HOST_PATTERN.match(ping_host):
        logger.error(
            "Ping validation failed | target=%s ping_host=%s category=invalid_ping_host",
            target_name,
            ping_host,
        )
        db.insert_ping_sample(
            device_name=target_name,
            ts_epoch=ts_epoch,
            ok=False,
            error_message="Invalid ping_host format",
        )
        return

    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", ping_host],
            capture_output=True,
            text=True,
            timeout=2,
        )

        if result.returncode == 0:
            rtt_ms = None
            for line in result.stdout.splitlines():
                if "time=" in line:
                    try:
                        parts = line.split("time=")[1].split()[0]
                        rtt_ms = float(parts)
                        break
                    except (IndexError, ValueError):
                        pass

            db.insert_ping_sample(
                device_name=target_name,
                ts_epoch=ts_epoch,
                ok=True,
                rtt_ms=rtt_ms,
            )
        else:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            detail = stderr or stdout
            error_message = classify_ping_error(result.returncode, stdout, stderr)
            logger.warning(
                "Ping failed | target=%s ping_host=%s category=ping_failed "
                "message=%s exit_code=%s detail=%s",
                target_name,
                ping_host,
                error_message,
                result.returncode,
                detail,
            )
            db.insert_ping_sample(
                device_name=target_name,
                ts_epoch=ts_epoch,
                ok=False,
                error_message=error_message,
            )

    except Exception as e:
        logger.warning(
            "Ping command error | target=%s ping_host=%s category=ping_exception "
            "message=%s raw_error=%s",
            target_name,
            ping_host,
            classify_command_error(e),
            str(e).strip(),
            exc_info=logger.isEnabledFor(logging.DEBUG),
        )
        db.insert_ping_sample(
            device_name=target_name,
            ts_epoch=ts_epoch,
            ok=False,
            error_message=classify_command_error(e),
        )


class DeviceCollector:
    """Collector for a single device."""

    def __init__(self, device_config: Dict[str, Any], config: Config):
        """Initialize device collector."""
        self.device_config = device_config
        self.config = config
        self.device_name = device_config["name"]
        self.max_output_lines = self.config.get_max_output_lines()

        # Persistent connection support
        self.persistent_connections_enabled = (
            self.config.get_persistent_connections_enabled()
        )
        self.connection_timeout = self.config.get_connection_timeout()
        self.max_reconnect_attempts = self.config.get_max_reconnect_attempts()
        self.reconnect_backoff_base = self.config.get_reconnect_backoff_base()
        self.initial_commands = [
            normalize_initial_command(initial_command)
            for initial_command in self.config.get_device_initial_commands(
                self.device_config
            )
        ]

        # Connection state (only used if persistent_connections_enabled)
        self._connection: Optional[ConnectHandler] = None
        self._connection_lock = threading.Lock()

        if self.persistent_connections_enabled:
            logger.info(f"Persistent connections enabled for {self.device_name}")

    def _get_connection_params(self) -> Dict[str, Any]:
        """Get connection parameters for Netmiko."""
        password = self.config.get_device_password(self.device_config)
        if password is None:
            password_env_key = self.device_config.get("password_env_key")
            if password_env_key:
                raise ValueError(
                    f"Password not provided for device '{self.device_name}'; set environment variable '{password_env_key}'"
                )
            raise ValueError(
                f"Password not provided for device '{self.device_name}' and no password_env_key set in config"
            )

        return {
            "device_type": self.device_config["device_type"],
            "host": self.device_config["host"],
            "port": self.device_config.get("port", 22),
            "username": self.device_config["username"],
            "password": password,
            "timeout": self.connection_timeout,
        }

    def _connect(self) -> ConnectHandler:
        """Establish a new connection to the device."""
        params = self._get_connection_params()
        logger.info(f"Establishing SSH connection to {self.device_name}")
        log_ssh_session(
            f"[{self.device_name}] connect host={params['host']} port={params['port']} "
            f"username={params['username']}"
        )
        connection = ConnectHandler(**params)
        try:
            self._run_initial_commands(connection)
        except Exception:
            try:
                connection.disconnect()
            except Exception:
                pass
            raise
        return connection

    def _run_initial_commands(self, connection: ConnectHandler) -> None:
        """Run device login initialization commands for this SSH session."""
        for initial_command in self.initial_commands:
            command_text = initial_command["command_text"]
            expect_string = initial_command.get("expect_string")
            logger.info(
                "Executing initial SSH command for %s: %s",
                self.device_name,
                command_text,
            )
            log_ssh_session(f"[{self.device_name}] initial-command> {command_text}")
            send_kwargs = {}
            if expect_string:
                send_kwargs["expect_string"] = expect_string
            output = connection.send_command(command_text, **send_kwargs)
            if output:
                log_ssh_session(f"[{self.device_name}] initial-output\n{output}")

    def _is_connection_alive(self) -> bool:
        """Check if the current connection is alive."""
        if self._connection is None:
            return False

        try:
            # Send a simple command to check connection
            self._connection.find_prompt()
            return True
        except Exception as e:
            logger.debug(f"Connection check failed for {self.device_name}: {e}")
            return False

    def _ensure_connected(self) -> ConnectHandler:
        """Ensure we have a live connection, reconnecting if necessary.

        Must be called with _connection_lock held.
        Returns a valid connection or raises an exception.
        """
        # Check if current connection is alive
        if self._connection is not None and self._is_connection_alive():
            return self._connection

        # Need to reconnect
        if self._connection is not None:
            logger.warning(f"Connection to {self.device_name} is dead, reconnecting...")
            try:
                self._connection.disconnect()
            except Exception:
                pass
            self._connection = None

        # Attempt to connect with retries and exponential backoff
        last_exception = None
        for attempt in range(self.max_reconnect_attempts):
            try:
                self._connection = self._connect()
                logger.info(
                    f"Successfully connected to {self.device_name} (attempt {attempt + 1})"
                )
                return self._connection
            except (
                NetmikoTimeoutException,
                NetmikoAuthenticationException,
                Exception,
            ) as e:
                last_exception = e
                logger.error(
                    f"Connection attempt {attempt + 1}/{self.max_reconnect_attempts} "
                    f"failed for {self.device_name}: {e}"
                )

                if attempt < self.max_reconnect_attempts - 1:
                    # Exponential backoff
                    sleep_time = self.reconnect_backoff_base * (2**attempt)
                    logger.info(f"Waiting {sleep_time:.2f}s before retry...")
                    time.sleep(sleep_time)

        # All attempts failed
        raise Exception(
            f"Failed to connect to {self.device_name} after {self.max_reconnect_attempts} attempts: {last_exception}"
        )

    def execute_command(self, command: str, db: Database) -> None:
        """Execute a single command on the device."""
        start_time = time.time()
        ts_epoch = int(start_time)

        # Get filters (command-specific overrides global)
        line_exclusions = self.config.get_command_line_exclusions(command)
        output_exclusions = self.config.get_command_output_exclusions(command)

        try:
            if self.persistent_connections_enabled:
                # Use persistent connection with lock
                with self._connection_lock:
                    connection = self._ensure_connected()
                    log_ssh_session(f"[{self.device_name}] command> {command}")
                    output = connection.send_command(command)
            else:
                # Legacy mode: create new connection for each command.
                connection = self._connect()
                log_ssh_session(f"[{self.device_name}] command> {command}")
                output = connection.send_command(command)
                connection.disconnect()
                log_ssh_session(f"[{self.device_name}] disconnect")

            duration_ms = (time.time() - start_time) * 1000

            # Process output
            processed_output, is_filtered, is_truncated, original_line_count = (
                process_output(
                    output,
                    line_exclusions=line_exclusions,
                    output_exclusions=output_exclusions,
                    max_lines=self.max_output_lines,
                )
            )

            # Store in database
            db.insert_run(
                device_name=self.device_name,
                command_text=command,
                ts_epoch=ts_epoch,
                output_text=processed_output,
                ok=True,
                duration_ms=duration_ms,
                is_filtered=is_filtered,
                is_truncated=is_truncated,
                original_line_count=original_line_count,
            )

            logger.info(
                f"Executed '{command}' on {self.device_name} in {duration_ms:.2f}ms"
            )
            log_ssh_session(
                f"[{self.device_name}] output command={command!r} "
                f"duration_ms={duration_ms:.2f}\n{output}"
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_code, error_msg = classify_command_error_detail(e)

            db.insert_run(
                device_name=self.device_name,
                command_text=command,
                ts_epoch=ts_epoch,
                output_text="",
                ok=False,
                error_message=error_msg,
                duration_ms=duration_ms,
                original_line_count=0,
            )

            logger.error(
                "Command execution failed | device=%s host=%s command=%r "
                "category=%s message=%s duration_ms=%.2f raw_error=%s",
                self.device_name,
                self.device_config.get("host"),
                command,
                error_code,
                error_msg,
                duration_ms,
                str(e).strip(),
                exc_info=logger.isEnabledFor(logging.DEBUG),
            )
            log_ssh_session(
                f"[{self.device_name}] error command={command!r} "
                f"category={error_code} message={error_msg}"
            )

    def close(self) -> None:
        """Close the persistent connection if open."""
        if self.persistent_connections_enabled:
            with self._connection_lock:
                if self._connection is not None:
                    try:
                        logger.info(
                            f"Closing persistent connection to {self.device_name}"
                        )
                        self._connection.disconnect()
                    except Exception as e:
                        logger.error(
                            f"Error closing connection to {self.device_name}: {e}"
                        )
                    finally:
                        self._connection = None

    def ping_device(self, db: Database) -> None:
        """Ping the device and store result."""
        ping_host = self.device_config.get("ping_host", self.device_config["host"])
        ping_target(db, self.device_name, ping_host)


class Collector:
    """Main collector orchestrator."""

    def __init__(self, config: Config, data_dir: str | Path | None = None):
        """Initialize collector."""
        self.config = config
        self.devices = config.get_devices()
        self.ping_targets = config.get_ping_targets()
        self.data_dir = Path(data_dir or os.environ.get("NW_WATCH_DATA_DIR", "data"))
        self.data_dir.mkdir(exist_ok=True)

        # Create session database
        session_epoch = int(time.time())
        self.session_db_path = self.data_dir / f"session_{session_epoch}.sqlite3"
        self.current_db_path = self.data_dir / "current.sqlite3"
        self.pid_path = None

        self.db = Database(
            str(self.session_db_path), history_size=self.config.get_history_size()
        )
        logger.info(f"Created session database: {self.session_db_path}")

        self.executor = ThreadPoolExecutor(max_workers=self.config.get_max_workers())
        self.running = True
        self.commands: List[str] = self._resolve_commands()
        self.commands_paused = False
        self.manual_mode = False
        self.control_poll_interval = 2

        # Cache global interval to avoid repeated method calls
        self.global_interval = self.config.get_interval_seconds()

        # Create persistent DeviceCollector instances
        self.device_collectors: Dict[str, DeviceCollector] = {}
        for device_config in self.devices:
            collector = DeviceCollector(device_config, self.config)
            self.device_collectors[device_config["name"]] = collector
            logger.info(f"Created DeviceCollector for {device_config['name']}")

        # Track next execution time and interval for each command
        self.command_next_run: Dict[str, float] = {}
        self.command_intervals: Dict[str, int] = {}  # Cache intervals
        self._initialize_command_intervals()

    def _initialize_command_intervals(self):
        """Initialize next run times for all commands and cache intervals."""
        now = time.time()

        for command in self.commands:
            # Get command-specific interval or use global interval
            cmd_interval = self.config.get_command_interval(command)

            if cmd_interval is not None:
                # Command has a specific interval (5-60 seconds)
                self.command_intervals[command] = cmd_interval
                logger.info(
                    f"Command '{command}' configured with interval {cmd_interval}s"
                )
            else:
                # Command uses global interval_seconds
                self.command_intervals[command] = self.global_interval
                logger.info(
                    f"Command '{command}' uses global interval {self.global_interval}s"
                )

            # All commands run immediately on first iteration
            self.command_next_run[command] = now

    def _load_control_state(self) -> Dict[str, Any]:
        """Load the collector control state from disk."""
        try:
            return read_control_state()
        except Exception as exc:
            logger.warning("Failed to load control state: %s", exc)
            return DEFAULT_CONTROL_STATE.copy()

    def _apply_control_state(self, state: Dict[str, Any]) -> None:
        """Apply control state changes and log transitions."""
        paused = bool(state.get("commands_paused", False))
        if paused != self.commands_paused:
            self.commands_paused = paused
            if paused:
                logger.info("Command execution paused via control state.")
            else:
                logger.info("Command execution resumed via control state.")

        manual_mode = bool(state.get("manual_mode", False))
        if manual_mode != self.manual_mode:
            self.manual_mode = manual_mode
            if manual_mode:
                logger.info("Command execution switched to manual mode.")
            else:
                logger.info("Command execution switched to automatic mode.")

    def _resolve_commands(self) -> List[str]:
        """Build command list honoring global commands or per-device fallbacks."""
        configured_commands = self.config.get_commands()
        if configured_commands:
            # Use global command list
            command_texts = []
            for cmd in configured_commands:
                command_text = cmd.get("command_text")
                if isinstance(command_text, str):
                    command_texts.append(command_text)
            return command_texts
        # Legacy per-device commands; assume all devices share same list
        all_cmds: List[str] = []
        for dev in self.devices:
            all_cmds.extend(dev.get("commands", []))
        # Preserve order, remove duplicates
        seen = set()
        ordered: List[str] = []
        for legacy_cmd in all_cmds:
            if legacy_cmd not in seen:
                ordered.append(legacy_cmd)
                seen.add(legacy_cmd)
        return ordered

    async def collect_commands(self, force: bool = False):
        """Collect commands from all devices (only commands due to run)."""
        loop = asyncio.get_event_loop()
        futures = []
        now = time.time()
        commands_executed = set()  # Track which commands were executed

        for device_name, collector in self.device_collectors.items():
            for command in self.commands:
                # Check if this command should run now
                next_run = self.command_next_run.get(command, now)
                if force or now >= next_run:
                    # Run in thread pool to avoid blocking
                    future = loop.run_in_executor(
                        self.executor, collector.execute_command, command, self.db
                    )
                    futures.append(future)

                    # Track that this command was executed (will update schedule after all devices)
                    commands_executed.add(command)

        # Wait for all commands to complete
        if futures:
            await asyncio.gather(*futures, return_exceptions=True)

        # Update next run times for commands that were executed
        # This must happen AFTER all devices have run the command
        for command in commands_executed:
            interval = self.command_intervals.get(command, self.global_interval)
            self.command_next_run[command] = now + interval

        # Atomically update current.sqlite3
        if futures:  # Only update if we actually ran commands
            self._update_current_db()

    async def collect_pings(self):
        """Collect pings from all devices."""
        loop = asyncio.get_event_loop()
        futures = []

        for device_name, collector in self.device_collectors.items():
            future = loop.run_in_executor(self.executor, collector.ping_device, self.db)
            futures.append(future)

        for target in self.ping_targets:
            future = loop.run_in_executor(
                self.executor,
                ping_target,
                self.db,
                target["name"],
                target["host"],
            )
            futures.append(future)

        if futures:
            await asyncio.gather(*futures, return_exceptions=True)

        # Update current.sqlite3 after pings
        self._update_current_db()

    def _update_current_db(self):
        """Atomically replace current.sqlite3 with a consistent SQLite snapshot."""
        delay = 1
        for attempt in range(5):
            try:
                tmp_path = self.data_dir / "current.sqlite3.tmp"
                if tmp_path.exists():
                    tmp_path.unlink()

                src_conn = self.db.conn
                dest_conn = sqlite3.connect(str(tmp_path))
                try:
                    src_conn.backup(dest_conn)
                finally:
                    dest_conn.close()

                tmp_path.replace(self.current_db_path)
                self._prune_session_databases()
                return
            except Exception as e:
                logger.error(
                    f"Error updating current database (attempt {attempt + 1}): {e}"
                )
                if attempt == 4:
                    return
                time.sleep(min(5, delay))
                delay = min(5, delay * 2)

    def _prune_session_databases(self, keep: int = 3) -> None:
        """Keep only the most recent session databases to avoid unbounded growth."""
        try:
            session_files = sorted(
                self.data_dir.glob("session_*.sqlite3"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        except Exception as exc:
            logger.warning("Failed to enumerate session databases: %s", exc)
            return

        for old_path in session_files[keep:]:
            try:
                old_path.unlink()
                logger.info("Pruned old session database: %s", old_path.name)
            except FileNotFoundError:
                continue
            except Exception as exc:
                logger.warning("Failed to prune %s: %s", old_path, exc)

    async def run(self):  # noqa: C901
        """Main collection loop."""
        ping_interval_seconds = self.config.get_ping_interval_seconds()

        # Schedule command collection with intelligent sleep intervals
        async def command_loop():
            try:
                while self.running:
                    control_state = self._load_control_state()
                    self._apply_control_state(control_state)
                    if self.commands_paused:
                        await asyncio.sleep(self.control_poll_interval)
                        continue

                    if self.manual_mode:
                        if not control_state.get("manual_run_requested"):
                            await asyncio.sleep(self.control_poll_interval)
                            continue
                        await self.collect_commands(force=True)
                        try:
                            update_control_state({"manual_run_requested": False})
                        except Exception as exc:
                            logger.warning(
                                "Failed to clear manual run request: %s", exc
                            )
                        await asyncio.sleep(self.control_poll_interval)
                        continue

                    await self.collect_commands()

                    # Calculate minimum time until next command needs to run
                    now = time.time()
                    min_wait = float("inf")
                    for cmd in self.commands:
                        next_run = self.command_next_run.get(cmd, now)
                        wait_time = max(0, next_run - now)
                        min_wait = min(min_wait, wait_time)

                    # Handle empty commands or no scheduled commands
                    if min_wait == float("inf"):
                        # No commands configured, use cached global interval
                        sleep_time = self.global_interval
                    else:
                        # Sleep until next command, but check at most every 60 seconds
                        # and no less than 1 second to avoid busy waiting
                        sleep_time = max(1, min(60, min_wait))

                    await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                logger.info("Command loop cancelled")
                raise

        # Schedule ping collection
        async def ping_loop():
            try:
                while self.running:
                    await self.collect_pings()
                    await asyncio.sleep(ping_interval_seconds)
            except asyncio.CancelledError:
                logger.info("Ping loop cancelled")
                raise

        # Run both loops concurrently
        try:
            await asyncio.gather(command_loop(), ping_loop())
        except asyncio.CancelledError:
            logger.info("Main loop cancelled")
            raise
        finally:
            if not self.running:
                self.stop()

    def stop(self):
        """Stop the collector."""
        self.running = False
        self.executor.shutdown(wait=True)

        # Close all device collectors (persistent connections)
        for device_name, collector in self.device_collectors.items():
            try:
                collector.close()
            except Exception as e:
                logger.error(f"Error closing collector for {device_name}: {e}")

        self.db.close()


async def async_main(config_path: str, data_dir: str | None = None):
    """Async main function with proper signal handling."""
    collector = None

    try:
        config = Config(config_path)
        collector = Collector(config, data_dir=data_dir)
        write_collector_pid(os.getpid())

        # Set up signal handlers in the event loop
        loop = asyncio.get_running_loop()

        def signal_handler(signame):
            """Handle shutdown signals by canceling tasks."""
            logger.info(
                f"Shutdown signal {signame} received, finishing current operations..."
            )
            if collector:
                collector.running = False
                # Cancel all pending tasks except the current one to force immediate shutdown
                current_task = asyncio.current_task(loop)
                for task in asyncio.all_tasks(loop):
                    if task != current_task:
                        task.cancel()

        # Register signal handlers for SIGTERM, SIGINT, and SIGHUP
        def make_signal_callback(sig: signal.Signals) -> Callable[[], None]:
            return lambda: signal_handler(sig.name)

        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            loop.add_signal_handler(sig, make_signal_callback(sig))

        # Run the collector
        await collector.run()

    except asyncio.CancelledError:
        logger.info("Collector stopped by signal")
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        raise
    finally:
        if collector:
            collector.stop()
        clear_collector_pid()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Network device data collector")
    parser.add_argument("--config", required=True, help="Path to config YAML file")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Directory for SQLite data files (default: NW_WATCH_DATA_DIR or data)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(async_main(args.config, data_dir=args.data_dir))
    except KeyboardInterrupt:
        logger.info("Collector stopped by user")
        sys.exit(0)
    except FileNotFoundError:
        sys.exit(1)
    except Exception as e:
        logger.error(f"Collector error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
