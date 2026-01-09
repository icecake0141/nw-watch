"""Configuration loading and validation."""
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from croniter import croniter

logger = logging.getLogger(__name__)


class Config:
    """Configuration management."""

    def __init__(self, config_path: str):
        """Load configuration from YAML file."""
        self.config_path = Path(config_path)
        with open(self.config_path, "r") as f:
            # Ensure we always have a dictionary to read from
            self.data: Dict[str, Any] = yaml.safe_load(f) or {}
        
        # Cache for command schedules to avoid repeated lookups
        self._schedule_cache: Dict[str, Optional[str]] = {}
        self._initialize_schedule_cache()
    
    def _validate_and_cache_schedule(self, command: str, schedule: str) -> Optional[str]:
        """Validate a cron schedule and return it if valid, None otherwise."""
        try:
            croniter(schedule)
            return schedule
        except ValueError as e:
            logger.error(
                "Invalid cron schedule '%s' for command '%s': %s",
                schedule,
                command,
                e,
            )
            return None
    
    def _initialize_schedule_cache(self):
        """Pre-compute and cache all command schedules."""
        for cmd in self.get_commands():
            command_text = cmd.get("command_text")
            if command_text:
                schedule = cmd.get("schedule")
                if schedule:
                    validated_schedule = self._validate_and_cache_schedule(command_text, schedule)
                    self._schedule_cache[command_text] = validated_schedule
                else:
                    self._schedule_cache[command_text] = None

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

    def get_command_schedule(self, command: str) -> Optional[str]:
        """Get cron schedule for a specific command, if configured."""
        # Use cache if available
        if command in self._schedule_cache:
            return self._schedule_cache[command]
        
        # Fallback for commands not in cache (shouldn't happen normally)
        logger.warning(
            "Command '%s' not found in schedule cache, performing fallback lookup. "
            "This may indicate a configuration initialization issue.",
            command
        )
        for cmd in self.get_commands():
            if cmd.get("command_text") == command or cmd.get("name") == command:
                schedule = cmd.get("schedule")
                if schedule:
                    validated_schedule = self._validate_and_cache_schedule(command, schedule)
                    self._schedule_cache[command] = validated_schedule
                    return validated_schedule
                # Command found but no schedule
                self._schedule_cache[command] = None
                return None
        
        # Command not found
        self._schedule_cache[command] = None
        return None
