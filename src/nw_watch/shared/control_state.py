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
"""Shared collector control state helpers."""

import json
import logging
import os
import time
import signal
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

CONTROL_STATE_FILENAME = "collector_control.json"
COLLECTOR_PID_FILENAME = "collector.pid"
DEFAULT_CONTROL_DIR = "control"
CONTROL_DIR_ENV = "NW_WATCH_CONTROL_DIR"

DEFAULT_CONTROL_STATE: Dict[str, Any] = {
    "commands_paused": False,
    "manual_mode": False,
    "manual_run_requested": False,
    "shutdown_requested": False,
    "command_schedule": {},
    "updated_at": 0,
}


def get_control_state_path() -> Path:
    """Resolve the control state file path."""
    control_dir = Path(os.environ.get(CONTROL_DIR_ENV, DEFAULT_CONTROL_DIR))
    return control_dir / CONTROL_STATE_FILENAME


def get_collector_pid_path() -> Path:
    """Resolve the collector PID file path."""
    control_dir = Path(os.environ.get(CONTROL_DIR_ENV, DEFAULT_CONTROL_DIR))
    return control_dir / COLLECTOR_PID_FILENAME


def normalize_control_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure a control state has all required fields."""
    normalized = DEFAULT_CONTROL_STATE.copy()
    normalized.update({k: state.get(k, v) for k, v in DEFAULT_CONTROL_STATE.items()})
    normalized["commands_paused"] = bool(normalized.get("commands_paused"))
    normalized["manual_mode"] = bool(normalized.get("manual_mode"))
    normalized["manual_run_requested"] = bool(normalized.get("manual_run_requested"))
    normalized["shutdown_requested"] = bool(normalized.get("shutdown_requested"))
    if not isinstance(normalized.get("command_schedule"), dict):
        normalized["command_schedule"] = {}
    normalized["updated_at"] = int(normalized.get("updated_at") or 0)
    return normalized


def read_control_state() -> Dict[str, Any]:
    """Read the current control state from disk."""
    path = get_control_state_path()
    if not path.exists():
        return DEFAULT_CONTROL_STATE.copy()

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return normalize_control_state(data)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read control state from %s: %s", path, exc)
        return DEFAULT_CONTROL_STATE.copy()


def write_control_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Persist the control state to disk (atomic write)."""
    path = get_control_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    normalized = normalize_control_state(state)
    normalized["updated_at"] = int(time.time())

    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle, indent=2, sort_keys=True)
        handle.write("\n")

    tmp_path.replace(path)
    return normalized


def update_control_state(update: Dict[str, Any]) -> Dict[str, Any]:
    """Update the control state with new values and persist."""
    current = read_control_state()
    current.update(update)
    return write_control_state(current)


def write_collector_pid(pid: int) -> Path:
    """Persist the active collector PID."""
    path = get_collector_pid_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(f"{pid}\n")
    tmp_path.replace(path)
    return path


def read_collector_pid() -> int | None:
    """Read the active collector PID."""
    path = get_collector_pid_path()
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return None
        return int(content)
    except (OSError, ValueError) as exc:
        logger.warning("Failed to read collector PID from %s: %s", path, exc)
        return None


def clear_collector_pid() -> None:
    """Remove the collector PID file if present."""
    path = get_collector_pid_path()
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Failed to remove collector PID file %s: %s", path, exc)


def is_process_running(pid: int) -> bool:
    """Return True if a process exists for the given PID."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def request_collector_shutdown(pid: int) -> bool:
    """Request collector shutdown by PID."""
    if not is_process_running(pid):
        return False
    os.kill(pid, signal.SIGTERM)
    return True
