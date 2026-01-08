# nw-watch - Dual-Device Network CLI Monitor

A Python-based network monitoring system that collects command outputs and ping data from multiple network devices via SSH and displays them in a real-time web interface with diff capabilities.

## Features

- **Multi-Device SSH Collection**: Connect to multiple network devices and execute commands in parallel
- **Continuous Ping Monitoring**: Track device connectivity with 1-second ping intervals
- **Real-Time Web Interface**: FastAPI-based web application with auto-refreshing UI
- **Command History**: Store and display the latest 10 runs per device/command
- **Diff Views**: 
  - Compare previous vs latest output for the same device
  - Compare outputs between different devices for the same command
- **Output Filtering**: 
  - Filter out lines containing specific substrings
  - Mark outputs as filtered based on error patterns
  - Truncate long outputs to configurable line limits
- **Time-Series Ping Data**: Visual status indicators with success rates and RTT metrics
- **JST Timezone Display**: All timestamps are displayed in Japan Standard Time

## Quick Start

### 1. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 2. Configure Devices

Copy the example configuration and edit it with your device details:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` to add your network devices:

```yaml
devices:
  - name: "DeviceA"
    host: "192.168.1.1"
    port: 22
    username: "admin"
    password: "password123"
    device_type: "cisco_ios"  # netmiko device type
    ping_host: "192.168.1.1"
    commands:
      - "show version"
      - "show interfaces status"
      - "show ip interface brief"
```

### 3. Start the Collector

The collector connects to devices and gathers data:

```bash
python -m collector.main --config config.yaml
```

The collector will:
- Execute configured commands every 5 seconds (configurable)
- Ping each device every 1 second
- Store results in SQLite database (`data/current.sqlite3`)
- Keep the latest 10 runs per device/command

### 4. Start the Web Application

In a separate terminal, start the web server:

```bash
uvicorn webapp.main:app --reload --host 127.0.0.1 --port 8000
```

### 5. Access the Web Interface

Open your browser and navigate to:

```
http://127.0.0.1:8000
```

## Project Structure

```
nw-watch/
├── collector/          # Data collection module
│   ├── __init__.py
│   └── main.py        # Main collector logic
├── webapp/            # Web application module
│   ├── __init__.py
│   ├── main.py        # FastAPI application
│   ├── templates/     # Jinja2 templates
│   │   └── index.html
│   └── static/        # Static assets
│       ├── style.css
│       └── app.js
├── shared/            # Shared utilities
│   ├── __init__.py
│   ├── config.py      # Configuration loader
│   ├── db.py          # Database operations
│   ├── diff.py        # Diff generation
│   └── filters.py     # Output filtering and truncation
├── tests/             # Test suite
│   ├── __init__.py
│   ├── test_diff.py
│   ├── test_filters.py
│   ├── test_truncate.py
│   ├── test_db.py
│   └── test_webapp.py
├── data/              # Database storage (created at runtime)
│   └── .gitkeep
├── config.example.yaml
├── pyproject.toml
└── README.md
```

## Configuration

### Collector Settings

```yaml
collector:
  interval_seconds: 5          # Command execution interval
  ping_interval_seconds: 1     # Ping interval
  max_runs_per_command: 10     # History depth per command
```

### Device Configuration

Each device requires:
- `name`: Unique identifier
- `host`: IP address or hostname
- `port`: SSH port (default: 22)
- `username`: SSH username
- `password`: SSH password
- `device_type`: Netmiko device type (e.g., `cisco_ios`, `juniper_junos`)
- `ping_host`: Host to ping for connectivity checks
- `commands`: List of CLI commands to execute

### Output Filtering

```yaml
filters:
  # Remove lines containing these substrings
  global_line_exclusions:
    - "Temperature"
    - "Last input"
  
  # Per-command overrides
  command_line_exclusions:
    "show version":
      - "uptime"
  
  # Mark output as filtered if it contains these
  output_exclusions:
    - "% Invalid"
    - "% Ambiguous"
  
  # Truncate output to N lines
  max_output_lines: 500
```

### Web Application Settings

```yaml
webapp:
  history_size: 10             # Max runs to display in UI
  ping_window_seconds: 60      # Time window for ping status
```

## Database Schema

The system uses SQLite with the following schema:

- **devices**: Device registry (id, name)
- **commands**: Command registry (id, command_text)
- **runs**: Command execution history
  - ts_epoch: Timestamp (UTC seconds)
  - output_text: Processed command output
  - ok: Success/failure flag
  - error_message: Error details if failed
  - duration_ms: Execution time
  - is_filtered: Output contains filter patterns
  - is_truncated: Output was truncated
  - original_line_count: Original line count before filtering
- **ping_samples**: Ping results (ts_epoch, ok, rtt_ms, error_message)

## Web UI Features

### Device Connectivity Panel
- Real-time ping status tiles (green/red)
- Success rate percentage
- Average RTT
- Sample counts

### Command Tabs
- One tab per unique command
- Per-device output history (latest first)
- Expandable run entries with metadata

### Diff Views
- **Previous vs Latest**: Compare consecutive runs for the same device
- **Device A vs Device B**: Compare outputs between devices

### Auto-Refresh Control
- Pause/Resume button to stop automatic updates
- Manual refresh button for on-demand updates
- Independent polling intervals for runs and pings

## Running Tests

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run specific test file
pytest tests/test_diff.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=shared --cov=collector --cov=webapp
```

## Development

### Adding New Device Types

The system supports any device type compatible with [Netmiko](https://github.com/ktbyers/netmiko). Common types:

- `cisco_ios`
- `cisco_nxos`
- `juniper_junos`
- `arista_eos`
- `hp_procurve`

### Extending Filters

To add custom filtering logic:

1. Edit `shared/filters.py`
2. Add filter functions
3. Update `process_output()` to use new filters
4. Add tests in `tests/test_filters.py`

### Customizing the UI

- Templates: `webapp/templates/index.html`
- Styles: `webapp/static/style.css`
- JavaScript: `webapp/static/app.js`

## Architecture

### Data Flow

1. **Collector** connects to devices via SSH (Netmiko)
2. Commands are executed in parallel using ThreadPoolExecutor
3. Outputs are filtered and truncated per configuration
4. Results are stored in session-specific SQLite database
5. Session database is atomically copied to `current.sqlite3`
6. **Web App** reads from `current.sqlite3` and serves via FastAPI
7. **Frontend** polls API endpoints and updates UI

### Database Lifecycle

- New session creates `data/session_{epoch}.sqlite3`
- Each update creates temporary copy `current.sqlite3.tmp`
- Old `current.sqlite3` is deleted
- Temporary file is renamed to `current.sqlite3` (atomic operation)
- Ensures readers always see consistent database state

### Polling Strategy

- **Run Updates**: `max(1, floor(interval_seconds/2))` seconds
- **Ping Updates**: `ping_interval_seconds` seconds
- Frontend respects auto-refresh toggle

## Requirements

- Python 3.11+
- Network devices accessible via SSH
- Devices must support command-line interface

## Security Considerations

**Important**: This example configuration stores passwords in plain text. For production use:

- Use environment variables for sensitive data
- Implement encrypted configuration files
- Use a secrets management system (e.g., HashiCorp Vault)
- Restrict file permissions on config.yaml (e.g., `chmod 600 config.yaml`)
- Consider using SSH key-based authentication where supported

## License

MIT License

## Troubleshooting

### Collector won't connect to device
- Verify SSH credentials
- Check `device_type` matches your device
- Ensure network connectivity to `host:port`
- Review logs for specific errors

### Web UI shows "No data available"
- Ensure collector is running
- Check that `data/current.sqlite3` exists
- Verify collector has successfully executed at least one command

### Outputs are too long
- Adjust `max_output_lines` in config
- Add more entries to `global_line_exclusions`

### Timestamps are wrong
- Frontend converts UTC to JST (UTC+9)
- Collector stores all timestamps in UTC epoch seconds
