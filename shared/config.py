"""Configuration loading and validation."""
import yaml
from pathlib import Path
from typing import Any, Dict, List


class Config:
    """Configuration management."""
    
    def __init__(self, config_path: str):
        """Load configuration from YAML file."""
        self.config_path = Path(config_path)
        with open(self.config_path, 'r') as f:
            self.data: Dict[str, Any] = yaml.safe_load(f)
    
    def get_collector_settings(self) -> Dict[str, Any]:
        """Get collector settings."""
        return self.data.get('collector', {})
    
    def get_devices(self) -> List[Dict[str, Any]]:
        """Get list of devices to monitor."""
        return self.data.get('devices', [])
    
    def get_filters(self) -> Dict[str, Any]:
        """Get filter settings."""
        return self.data.get('filters', {})
    
    def get_webapp_settings(self) -> Dict[str, Any]:
        """Get webapp settings."""
        return self.data.get('webapp', {})
    
    def get_interval_seconds(self) -> int:
        """Get command execution interval."""
        return self.get_collector_settings().get('interval_seconds', 5)
    
    def get_ping_interval_seconds(self) -> int:
        """Get ping interval."""
        return self.get_collector_settings().get('ping_interval_seconds', 1)
    
    def get_max_runs_per_command(self) -> int:
        """Get max runs to keep per command."""
        return self.get_collector_settings().get('max_runs_per_command', 10)
    
    def get_global_line_exclusions(self) -> List[str]:
        """Get global line exclusion patterns."""
        return self.get_filters().get('global_line_exclusions', [])
    
    def get_command_line_exclusions(self, command: str) -> List[str]:
        """Get line exclusions for specific command."""
        command_exclusions = self.get_filters().get('command_line_exclusions', {})
        return command_exclusions.get(command, None)
    
    def get_output_exclusions(self) -> List[str]:
        """Get output exclusion patterns."""
        return self.get_filters().get('output_exclusions', [])
    
    def get_max_output_lines(self) -> int:
        """Get maximum output lines."""
        return self.get_filters().get('max_output_lines', 500)
    
    def get_history_size(self) -> int:
        """Get history size for webapp."""
        return self.get_webapp_settings().get('history_size', 10)
    
    def get_ping_window_seconds(self) -> int:
        """Get ping window for webapp."""
        return self.get_webapp_settings().get('ping_window_seconds', 60)
