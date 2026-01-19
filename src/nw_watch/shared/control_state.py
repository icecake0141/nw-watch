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
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

CONTROL_STATE_FILENAME = "collector_control.json"
DEFAULT_CONTROL_DIR = "control"
CONTROL_DIR_ENV = "NW_WATCH_CONTROL_DIR"

DEFAULT_CONTROL_STATE: Dict[str, Any] = {
    "commands_paused": False,
    "shutdown_requested": False,
    "updated_at": 0,
}


def get_control_state_path() -> Path:
    """Resolve the control state file path."""
    control_dir = Path(os.environ.get(CONTROL_DIR_ENV, DEFAULT_CONTROL_DIR))
    return control_dir / CONTROL_STATE_FILENAME


def normalize_control_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure a control state has all required fields."""
    normalized = DEFAULT_CONTROL_STATE.copy()
    normalized.update({k: state.get(k, v) for k, v in DEFAULT_CONTROL_STATE.items()})
    normalized["commands_paused"] = bool(normalized.get("commands_paused"))
    normalized["shutdown_requested"] = bool(normalized.get("shutdown_requested"))
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
