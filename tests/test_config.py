"""Tests for configuration loader."""
from pathlib import Path

from shared.config import Config


def test_config_new_structure(tmp_path, monkeypatch):
    """Ensure new config structure is parsed correctly."""
    cfg_path = Path(tmp_path) / "config.yaml"
    cfg_path.write_text(
        """
interval_seconds: 7
ping_interval_seconds: 2
ping_window_seconds: 90
history_size: 5
max_output_lines: 400

global_filters:
  line_exclude_substrings:
    - "global"
  output_exclude_substrings:
    - "% Invalid"

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
"""
    )

    monkeypatch.setenv("PW_A", "secret")

    config = Config(str(cfg_path))

    assert config.get_interval_seconds() == 7
    assert config.get_ping_interval_seconds() == 2
    assert config.get_ping_window_seconds() == 90
    assert config.get_history_size() == 5
    assert config.get_max_output_lines() == 400
    assert config.get_command_line_exclusions("show run") == ["local"]
    # Falls back to global output exclusions when none are set on the command
    assert config.get_command_output_exclusions("show run") == ["% Invalid"]
    assert config.get_device_password(config.get_devices()[0]) == "secret"
