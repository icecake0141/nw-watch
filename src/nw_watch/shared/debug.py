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
"""Debug logging and redaction helpers."""

from __future__ import annotations

import logging
import json
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Mapping, Optional

APP_LOG_FILENAME = "app.log"
SSH_LOG_FILENAME = "ssh_sessions.log"
LOG_DIR_ENV = "NW_WATCH_LOG_DIR"
DATA_DIR_ENV = "NW_WATCH_DATA_DIR"

MASK = "********"
SENSITIVE_KEY_NAMES = {
    "password",
    "secret",
    "enable_secret",
    "token",
    "api_key",
    "private_key",
}


class JsonLogFormatter(logging.Formatter):
    """Format log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Return a JSON representation of a log record."""
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def get_log_dir() -> Path:
    """Return the directory used for debug log files."""
    configured = os.environ.get(LOG_DIR_ENV)
    if configured:
        return Path(configured)
    return Path(os.environ.get(DATA_DIR_ENV, "data")) / "logs"


def get_app_log_path() -> Path:
    """Return the application debug log path."""
    return get_log_dir() / APP_LOG_FILENAME


def get_ssh_log_path() -> Path:
    """Return the SSH session debug log path."""
    return get_log_dir() / SSH_LOG_FILENAME


def setup_debug_file_logging() -> None:
    """Attach an application file log handler once per process."""
    log_path = get_app_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler_key = str(log_path.resolve())

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if getattr(handler, "_nw_watch_debug_log_path", None) == handler_key:
            return

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    handler._nw_watch_debug_log_path = handler_key  # type: ignore[attr-defined]
    root_logger.addHandler(handler)


def build_log_formatter(format_name: str) -> logging.Formatter:
    """Build a configured log formatter."""
    if format_name == "json":
        return JsonLogFormatter()
    return logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def configure_logging(config: Optional[Mapping[str, Any]] = None) -> None:
    """Configure root logging from application config."""
    config = config or {}
    level_name = str(config.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    format_name = str(config.get("format", "text")).lower()
    formatter = build_log_formatter(format_name)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    if bool(config.get("console", True)):
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if bool(config.get("file", True)):
        configured_path = config.get("file_path")
        log_path = Path(str(configured_path)) if configured_path else get_app_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=int(config.get("max_bytes", 10485760)),
            backupCount=int(config.get("backup_count", 5)),
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        file_handler._nw_watch_debug_log_path = str(  # type: ignore[attr-defined]
            log_path.resolve()
        )
        root_logger.addHandler(file_handler)


def configure_logging_from_config_path(config_path: str) -> None:
    """Configure logging from a config file, falling back to defaults."""
    from nw_watch.shared.config import Config

    try:
        configure_logging(Config(config_path).get_logging_config())
    except Exception as exc:
        configure_logging()
        logging.getLogger(__name__).warning(
            "Using default logging configuration: %s", exc
        )


def log_ssh_session(message: str) -> None:
    """Append a line to the SSH session debug log."""
    log_path = get_ssh_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip("\n") + "\n")


def mask_sensitive_config(value: Any) -> Any:
    """Return a copy of config-like data with sensitive values masked."""
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered == "password_env_key":
                masked[key] = item
            elif lowered in SENSITIVE_KEY_NAMES or lowered.endswith("_password"):
                masked[key] = MASK if item is not None else None
            else:
                masked[key] = mask_sensitive_config(item)
        return masked
    if isinstance(value, list):
        return [mask_sensitive_config(item) for item in value]
    return value
