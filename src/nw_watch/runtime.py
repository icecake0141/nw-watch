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
"""Run collector and web application as a single managed process group."""

import argparse
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def validate_startup_paths(config_path: Path, data_dir: Path) -> None:
    """Validate required runtime paths before spawning child processes."""
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. Copy config.example.yaml to config.yaml first."
        )
    if not config_path.is_file():
        raise IsADirectoryError(f"Config path is not a file: {config_path}")
    data_dir.mkdir(parents=True, exist_ok=True)


def start_process(
    name: str, command: Sequence[str], env: dict[str, str]
) -> subprocess.Popen:
    """Start a child process and log the exact command."""
    logger.info("Starting %s | command=%s", name, " ".join(command))
    return subprocess.Popen(command, env=env)


def terminate_process(
    name: str, process: subprocess.Popen, timeout: float = 10.0
) -> None:
    """Terminate a child process, escalating to kill if needed."""
    if process.poll() is not None:
        return

    logger.info("Stopping %s | pid=%s", name, process.pid)
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        logger.warning("%s did not stop within %.1fs; killing", name, timeout)
        process.kill()
        process.wait(timeout=timeout)


def run(args: argparse.Namespace) -> int:
    """Run collector and Uvicorn until one exits or a signal is received."""
    config_path = Path(args.config)
    data_dir = Path(args.data_dir)
    validate_startup_paths(config_path, data_dir)

    env = os.environ.copy()
    env["NW_WATCH_CONFIG"] = str(config_path)
    env["NW_WATCH_DATA_DIR"] = str(data_dir)

    collector_command = [
        sys.executable,
        "-m",
        "nw_watch.collector.main",
        "--config",
        str(config_path),
        "--data-dir",
        str(data_dir),
    ]
    web_command = [
        sys.executable,
        "-m",
        "uvicorn",
        "nw_watch.webapp.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]

    processes: dict[str, subprocess.Popen] = {
        "collector": start_process("collector", collector_command, env),
        "webapp": start_process("webapp", web_command, env),
    }
    stopping = False

    def request_stop(signum, _frame):
        nonlocal stopping
        stopping = True
        logger.info("Shutdown signal received | signal=%s", signal.Signals(signum).name)

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    exit_code = 0
    try:
        while not stopping:
            for name, process in processes.items():
                returncode = process.poll()
                if returncode is not None:
                    logger.error(
                        "Managed process exited | name=%s pid=%s exit_code=%s",
                        name,
                        process.pid,
                        returncode,
                    )
                    exit_code = returncode if returncode != 0 else 1
                    stopping = True
                    break
            time.sleep(0.5)
    finally:
        for name, process in processes.items():
            terminate_process(name, process)

    return exit_code


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Start nw-watch collector and web app together."
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config YAML")
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("NW_WATCH_DATA_DIR", "data"),
        help="Directory for SQLite data files",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Uvicorn bind host")
    parser.add_argument("--port", default=8000, type=int, help="Uvicorn bind port")
    try:
        raise SystemExit(run(parser.parse_args()))
    except Exception as exc:
        logger.error("Startup failed | category=runtime_startup_failed message=%s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
