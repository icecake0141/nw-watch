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
"""Tests for configuration loader."""

from pathlib import Path

from nw_watch.shared.config import Config


def test_config_new_structure(tmp_path, monkeypatch):
    """Ensure new config structure is parsed correctly."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text("""
interval_seconds: 7
ping_interval_seconds: 2
ping_window_seconds: 90
history_size: 5
max_output_lines: 400
logging:
  level: DEBUG
  format: json
  console: false
  file: true
  file_path: "logs/test.log"
  max_bytes: 2048
  backup_count: 2

ping_targets:
  - name: "GatewayVIP"
    host: "192.0.2.254"

global_filters:
  line_exclude_substrings:
    - "global"
  output_exclude_substrings:
    - "% Invalid"

ssh:
  initial_commands:
    - "terminal length 0"

commands:
  - name: "cmd1"
    command_text: "show run"
    filters:
      line_exclude_substrings:
        - "local"

devices:
  - name: "DeviceA"
    host: "1.1.1.1"
    username: "admin"
    password_env_key: "PW_A"
    device_type: "cisco_ios"
    initial_commands:
      - "enable"
""")

    monkeypatch.setenv("PW_A", "secret")

    config = Config(str(cfg_path))

    assert config.get_interval_seconds() == 7
    assert config.get_ping_interval_seconds() == 2
    assert config.get_ping_window_seconds() == 90
    assert config.get_history_size() == 5
    assert config.get_max_output_lines() == 400
    assert config.get_logging_config() == {
        "level": "DEBUG",
        "format": "json",
        "console": False,
        "file": True,
        "file_path": "logs/test.log",
        "max_bytes": 2048,
        "backup_count": 2,
    }
    assert config.get_ping_targets() == [{"name": "GatewayVIP", "host": "192.0.2.254"}]
    assert config.get_command_line_exclusions("show run") == ["local"]
    # Falls back to global output exclusions when none are set on the command
    assert config.get_command_output_exclusions("show run") == ["% Invalid"]
    assert config.get_device_password(config.get_devices()[0]) == "secret"
    assert config.get_global_initial_commands() == ["terminal length 0"]
    assert config.get_device_initial_commands(config.get_devices()[0]) == [
        "terminal length 0",
        "enable",
    ]


def test_config_structured_initial_commands(tmp_path, monkeypatch):
    """Ensure structured initial commands with expect_string are preserved."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text("""
commands:
  - name: "cmd1"
    command_text: "show run"
ssh:
  initial_commands:
    - command_text: "config global"
      expect_string: '\\(global\\) #'
devices:
  - name: "DeviceA"
    host: "1.1.1.1"
    username: "admin"
    password_env_key: "PW_A"
    device_type: "fortinet"
    initial_commands:
      - command_text: "diagnose debug cli 8"
        expect_string: "#"
""")

    monkeypatch.setenv("PW_A", "secret")

    config = Config(str(cfg_path))

    assert config.get_global_initial_commands() == [
        {"command_text": "config global", "expect_string": "\\(global\\) #"}
    ]
    assert config.get_device_initial_commands(config.get_devices()[0]) == [
        {"command_text": "config global", "expect_string": "\\(global\\) #"},
        {"command_text": "diagnose debug cli 8", "expect_string": "#"},
    ]
