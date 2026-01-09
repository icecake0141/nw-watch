"""Configuration validation using Pydantic models."""
import re
from typing import Any, Dict, List, Optional

from croniter import croniter
from pydantic import BaseModel, Field, field_validator, model_validator


class FiltersConfig(BaseModel):
    """Filter configuration."""
    line_exclude_substrings: Optional[List[str]] = None
    output_exclude_substrings: Optional[List[str]] = None


class CommandConfig(BaseModel):
    """Command configuration."""
    name: Optional[str] = None
    command_text: str
    schedule: Optional[str] = None
    sort_order: Optional[int] = None
    filters: Optional[FiltersConfig] = None

    @field_validator("command_text")
    @classmethod
    def validate_command_text(cls, v: str) -> str:
        """Validate command text is not empty."""
        if not v or not v.strip():
            raise ValueError("command_text must not be empty")
        return v

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, v: Optional[str]) -> Optional[str]:
        """Validate cron schedule format."""
        if v is not None:
            try:
                croniter(v)
            except (ValueError, KeyError) as e:
                raise ValueError(f"Invalid cron schedule '{v}': {e}")
        return v


class DeviceConfig(BaseModel):
    """Device configuration."""
    name: str
    host: str
    port: int = 22
    username: str
    password_env_key: Optional[str] = None
    password: Optional[str] = None
    device_type: str
    ping_host: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate device name is not empty."""
        if not v or not v.strip():
            raise ValueError("Device name must not be empty")
        return v

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate host is not empty."""
        if not v or not v.strip():
            raise ValueError("Host must not be empty")
        return v

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if not (1 <= v <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {v}")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username is not empty."""
        if not v or not v.strip():
            raise ValueError("Username must not be empty")
        return v

    @field_validator("device_type")
    @classmethod
    def validate_device_type(cls, v: str) -> str:
        """Validate device_type is not empty."""
        if not v or not v.strip():
            raise ValueError("Device type must not be empty")
        # Common Netmiko device types - could be extended
        known_types = {
            "cisco_ios", "cisco_nxos", "cisco_xe", "cisco_xr", "cisco_asa",
            "arista_eos", "juniper", "juniper_junos",
            "hp_procurve", "hp_comware",
            "linux", "generic_termserver",
        }
        if v not in known_types:
            # Warning, not error - allow custom types
            pass
        return v

    @field_validator("ping_host")
    @classmethod
    def validate_ping_host(cls, v: Optional[str]) -> Optional[str]:
        """Validate ping host format to prevent command injection."""
        if v is not None:
            # Allow IPv4, IPv6, and hostnames
            # This regex is permissive but prevents command injection
            pattern = r'^[a-zA-Z0-9\.\:\-\_]+$'
            if not re.match(pattern, v):
                raise ValueError(
                    f"Invalid ping_host format '{v}'. Must contain only "
                    "alphanumeric characters, dots, colons, hyphens, and underscores."
                )
        return v

    @model_validator(mode='after')
    def validate_password_config(self) -> 'DeviceConfig':
        """Ensure either password_env_key or password is provided."""
        if not self.password_env_key and not self.password:
            raise ValueError(
                f"Device '{self.name}' must specify either password_env_key or password"
            )
        return self


class GlobalFiltersConfig(BaseModel):
    """Global filters configuration."""
    line_exclude_substrings: Optional[List[str]] = Field(default_factory=list)
    output_exclude_substrings: Optional[List[str]] = Field(default_factory=list)


class WebSocketConfig(BaseModel):
    """WebSocket configuration."""
    enabled: bool = False
    ping_interval: int = Field(default=20, gt=0)

    @field_validator("ping_interval")
    @classmethod
    def validate_ping_interval(cls, v: int) -> int:
        """Validate ping interval is positive."""
        if v <= 0:
            raise ValueError(f"WebSocket ping_interval must be positive, got {v}")
        return v


class SSHConfig(BaseModel):
    """SSH connection configuration."""
    persistent_connections: bool = True
    connection_timeout: int = Field(default=100, gt=0)
    max_reconnect_attempts: int = Field(default=3, ge=0)
    reconnect_backoff_base: float = Field(default=1.0, gt=0)

    @field_validator("connection_timeout")
    @classmethod
    def validate_connection_timeout(cls, v: int) -> int:
        """Validate connection timeout is positive."""
        if v <= 0:
            raise ValueError(f"SSH connection_timeout must be positive, got {v}")
        return v

    @field_validator("max_reconnect_attempts")
    @classmethod
    def validate_max_reconnect_attempts(cls, v: int) -> int:
        """Validate max reconnect attempts is non-negative."""
        if v < 0:
            raise ValueError(f"SSH max_reconnect_attempts must be non-negative, got {v}")
        return v

    @field_validator("reconnect_backoff_base")
    @classmethod
    def validate_reconnect_backoff_base(cls, v: float) -> float:
        """Validate reconnect backoff base is positive."""
        if v <= 0:
            raise ValueError(f"SSH reconnect_backoff_base must be positive, got {v}")
        return v


class ConfigSchema(BaseModel):
    """Root configuration schema."""
    interval_seconds: int = Field(default=5, gt=0)
    ping_interval_seconds: int = Field(default=1, gt=0)
    ping_window_seconds: int = Field(default=60, gt=0)
    history_size: int = Field(default=10, gt=0)
    max_output_lines: int = Field(default=500, gt=0)
    
    global_filters: Optional[GlobalFiltersConfig] = Field(default_factory=GlobalFiltersConfig)
    websocket: Optional[WebSocketConfig] = Field(default_factory=WebSocketConfig)
    ssh: Optional[SSHConfig] = Field(default_factory=SSHConfig)
    
    commands: List[CommandConfig] = Field(default_factory=list)
    devices: List[DeviceConfig] = Field(default_factory=list)
    
    # Legacy fields for backward compatibility
    collector: Optional[Dict[str, Any]] = None
    webapp: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None

    @field_validator("interval_seconds")
    @classmethod
    def validate_interval_seconds(cls, v: int) -> int:
        """Validate interval is positive."""
        if v <= 0:
            raise ValueError(f"interval_seconds must be positive, got {v}")
        return v

    @field_validator("ping_interval_seconds")
    @classmethod
    def validate_ping_interval_seconds(cls, v: int) -> int:
        """Validate ping interval is positive."""
        if v <= 0:
            raise ValueError(f"ping_interval_seconds must be positive, got {v}")
        return v

    @field_validator("ping_window_seconds")
    @classmethod
    def validate_ping_window_seconds(cls, v: int) -> int:
        """Validate ping window is positive."""
        if v <= 0:
            raise ValueError(f"ping_window_seconds must be positive, got {v}")
        return v

    @field_validator("history_size")
    @classmethod
    def validate_history_size(cls, v: int) -> int:
        """Validate history size is positive."""
        if v <= 0:
            raise ValueError(f"history_size must be positive, got {v}")
        return v

    @field_validator("max_output_lines")
    @classmethod
    def validate_max_output_lines(cls, v: int) -> int:
        """Validate max output lines is positive."""
        if v <= 0:
            raise ValueError(f"max_output_lines must be positive, got {v}")
        return v

    @field_validator("devices")
    @classmethod
    def validate_devices_not_empty(cls, v: List[DeviceConfig]) -> List[DeviceConfig]:
        """Validate at least one device is configured."""
        if not v:
            raise ValueError("At least one device must be configured")
        return v

    @field_validator("commands")
    @classmethod
    def validate_commands_not_empty(cls, v: List[CommandConfig]) -> List[CommandConfig]:
        """Validate at least one command is configured."""
        if not v:
            raise ValueError("At least one command must be configured")
        return v

    @model_validator(mode='after')
    def validate_unique_device_names(self) -> 'ConfigSchema':
        """Ensure device names are unique."""
        names = [d.name for d in self.devices]
        if len(names) != len(set(names)):
            duplicates = [name for name in names if names.count(name) > 1]
            raise ValueError(f"Duplicate device names found: {set(duplicates)}")
        return self

    @model_validator(mode='after')
    def validate_unique_command_texts(self) -> 'ConfigSchema':
        """Ensure command texts are unique."""
        texts = [c.command_text for c in self.commands]
        if len(texts) != len(set(texts)):
            duplicates = [text for text in texts if texts.count(text) > 1]
            raise ValueError(f"Duplicate command_text found: {set(duplicates)}")
        return self
