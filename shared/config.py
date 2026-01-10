"""Configuration loading and validation."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import ValidationError

from shared.validation import ConfigSchema

logger = logging.getLogger(__name__)


class Config:
    """Configuration management."""

    def __init__(self, config_path: str):
        """Load configuration from YAML file."""
        self.config_path = Path(config_path)
        with open(self.config_path, "r") as f:
            # Ensure we always have a dictionary to read from
            raw_data = yaml.safe_load(f) or {}

        # Validate configuration with Pydantic
        try:
            self.schema = ConfigSchema(**raw_data)
        except ValidationError as e:
            logger.error("Configuration validation failed:")
            for error in e.errors():
                location = " -> ".join(str(loc) for loc in error["loc"])
                logger.error("  %s: %s", location, error["msg"])
            raise ValueError(f"Invalid configuration in {config_path}") from e

        # Store raw data for backward compatibility
        self.data: Dict[str, Any] = raw_data

        # Cache for command intervals to avoid repeated lookups
        self._interval_cache: Dict[str, Optional[int]] = {}
        self._initialize_interval_cache()

    def _initialize_interval_cache(self):
        """Pre-compute and cache all command intervals."""
        for cmd in self.get_commands():
            command_text = cmd.get("command_text")
            if command_text:
                interval = cmd.get("interval_seconds")
                self._interval_cache[command_text] = interval

    # ------------------------------------------------------------------ #
    # Basic settings
    # ------------------------------------------------------------------ #
    def _legacy_collector(self) -> Dict[str, Any]:
        return self.data.get("collector", {})

    def get_interval_seconds(self) -> int:
        """Command execution interval (seconds)."""
        return int(
            self.data.get(
                "interval_seconds",
                self._legacy_collector().get("interval_seconds", 5),
            )
        )

    def get_ping_interval_seconds(self) -> int:
        """Ping interval (seconds)."""
        return int(
            self.data.get(
                "ping_interval_seconds",
                self._legacy_collector().get("ping_interval_seconds", 1),
            )
        )

    def get_history_size(self) -> int:
        """Maximum runs to keep per device/command."""
        return int(
            self.data.get(
                "history_size",
                self.data.get("webapp", {}).get("history_size", 10),
            )
        )

    def get_ping_window_seconds(self) -> int:
        """Time window for ping tiles."""
        return int(
            self.data.get(
                "ping_window_seconds",
                self.data.get("webapp", {}).get("ping_window_seconds", 60),
            )
        )

    def get_max_output_lines(self) -> int:
        """Maximum output lines to retain after filtering."""
        return int(
            self.data.get(
                "max_output_lines",
                self.data.get("filters", {}).get("max_output_lines", 500),
            )
        )

    # ------------------------------------------------------------------ #
    # WebSocket settings
    # ------------------------------------------------------------------ #
    def get_websocket_enabled(self) -> bool:
        """Check if WebSocket is enabled."""
        websocket_config = self.data.get("websocket", {})
        return bool(websocket_config.get("enabled", False))

    def get_websocket_ping_interval(self) -> int:
        """WebSocket ping interval (seconds)."""
        websocket_config = self.data.get("websocket", {})
        return int(websocket_config.get("ping_interval", 20))

    # ------------------------------------------------------------------ #
    # SSH Connection settings
    # ------------------------------------------------------------------ #
    def get_persistent_connections_enabled(self) -> bool:
        """Check if persistent SSH connections are enabled."""
        ssh_config = self.data.get("ssh", {})
        return bool(ssh_config.get("persistent_connections", True))

    def get_connection_timeout(self) -> int:
        """SSH connection timeout (seconds)."""
        ssh_config = self.data.get("ssh", {})
        return int(ssh_config.get("connection_timeout", 100))

    def get_max_reconnect_attempts(self) -> int:
        """Maximum number of reconnection attempts."""
        ssh_config = self.data.get("ssh", {})
        return int(ssh_config.get("max_reconnect_attempts", 3))

    def get_reconnect_backoff_base(self) -> float:
        """Base time for exponential backoff during reconnection (seconds)."""
        ssh_config = self.data.get("ssh", {})
        return float(ssh_config.get("reconnect_backoff_base", 1.0))

    # ------------------------------------------------------------------ #
    # Devices and commands
    # ------------------------------------------------------------------ #
    def get_devices(self) -> List[Dict[str, Any]]:
        """Configured devices."""
        return self.data.get("devices", [])

    def get_commands(self) -> List[Dict[str, Any]]:
        """Configured commands (global list)."""
        return self.data.get("commands", [])

    def get_device_password(self, device: Dict[str, Any]) -> Optional[str]:
        """Resolve device password from environment (preferred)."""
        env_key = device.get("password_env_key")
        if env_key:
            return os.environ.get(env_key)
        # Fallback for legacy configs that embedded passwords
        fallback = device.get("password")
        if fallback is not None:
            logger.error(
                "Using plaintext password from config for device '%s'; prefer password_env_key",
                device.get("name", "unknown"),
            )
        return fallback

    # ------------------------------------------------------------------ #
    # Filters
    # ------------------------------------------------------------------ #
    def get_global_line_exclusions(self) -> List[str]:
        """Global line filters."""
        if "global_filters" in self.data:
            return self.data["global_filters"].get("line_exclude_substrings", [])
        # Legacy layout
        return self.data.get("filters", {}).get("global_line_exclusions", [])

    def get_global_output_exclusions(self) -> List[str]:
        """Global output filters (mark run as filtered)."""
        if "global_filters" in self.data:
            return self.data["global_filters"].get("output_exclude_substrings", [])
        return self.data.get("filters", {}).get("output_exclusions", [])

    def _find_command_filters(self, command: str) -> Dict[str, Optional[List[str]]]:
        """Return filters configured for a command."""
        filters_for_command: Optional[Dict[str, Optional[List[str]]]] = None

        for cmd in self.get_commands():
            if cmd.get("command_text") == command or cmd.get("name") == command:
                filters = cmd.get("filters", {})
                filters_for_command = {
                    "line_exclude_substrings": filters.get("line_exclude_substrings"),
                    "output_exclude_substrings": filters.get(
                        "output_exclude_substrings"
                    ),
                }
                break

        if filters_for_command is not None:
            return filters_for_command

        # Legacy override map
        legacy_cmd_filters = self.data.get("filters", {}).get(
            "command_line_exclusions", {}
        )
        if command in legacy_cmd_filters:
            return {
                "line_exclude_substrings": legacy_cmd_filters.get(command, []),
                "output_exclude_substrings": None,
            }

        return {
            "line_exclude_substrings": None,
            "output_exclude_substrings": None,
        }

    def get_command_line_exclusions(self, command: str) -> List[str]:
        """Line exclusions for a specific command (overrides global)."""
        filters = self._find_command_filters(command)
        if filters["line_exclude_substrings"] is not None:
            return filters["line_exclude_substrings"]
        return self.get_global_line_exclusions()

    def get_command_output_exclusions(self, command: str) -> List[str]:
        """Output exclusion substrings for a specific command."""
        filters = self._find_command_filters(command)
        if filters["output_exclude_substrings"] is not None:
            return filters["output_exclude_substrings"]
        return self.get_global_output_exclusions()

    def get_command_interval(self, command: str) -> Optional[int]:
        """Get execution interval for a specific command, if configured.
        
        Returns the command-specific interval in seconds (5-60 range), or None if
        the command should use the global interval_seconds setting.
        
        Args:
            command: The command text to look up
            
        Returns:
            Command-specific interval in seconds, or None to use global interval
        """
        # Use cache if available
        if command in self._interval_cache:
            return self._interval_cache[command]

        # Fallback for commands not in cache (shouldn't happen normally)
        logger.warning(
            "Command '%s' not found in interval cache, performing fallback lookup. "
            "This may indicate a configuration initialization issue.",
            command,
        )
        for cmd in self.get_commands():
            if cmd.get("command_text") == command or cmd.get("name") == command:
                interval = cmd.get("interval_seconds")
                self._interval_cache[command] = interval
                return interval

        # Command not found
        self._interval_cache[command] = None
        return None
