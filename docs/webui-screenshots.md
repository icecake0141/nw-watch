# Web UI Screenshots Guide

This guide provides visual documentation of the Network Watch web interface with detailed explanations of each feature and component.

![Web UI Overview](images/webui-overview.png)

## Interface Overview

The Network Watch web interface is a single-page application that displays real-time network device monitoring data. The interface is divided into several key sections:

1. **Header with Auto-Refresh Controls**
2. **Device Connectivity Panel**
3. **Command Output Tabs**
4. **Run History Displays**
5. **Diff Viewers**

---

## 1. Header and Controls

Located at the top of the page, the header provides application branding and refresh controls.

### Components:
- **Title**: "Network Watch - Dual Device Monitor"
- **⏸ Pause Auto-Refresh Button**: 
  - Toggles automatic polling of data from the backend
  - Changes to "▶ Resume Auto-Refresh" when paused
  - When paused, a banner appears indicating auto-refresh is disabled
- **🔄 Refresh Now Button**: 
  - Manually triggers an immediate data refresh
  - Works independently of auto-refresh state
  - Useful for on-demand updates while auto-refresh is paused

### Usage:
Click "Pause Auto-Refresh" during troubleshooting to freeze the display, then use "Refresh Now" to update data at your own pace.

---

## 2. Device Connectivity Panel

This panel provides real-time ping monitoring for all configured devices, showing connectivity status over a 60-second window.

### Displayed Information:

For each device, you'll see:

- **Device Name**: Configured device identifier
- **Status Indicator**: 
  - 🟢 Green: Device is reachable (≥50% success rate)
  - 🔴 Red: Device is down (<50% success rate)
  - ⚪ Gray: Status unknown (no ping data)
- **Success Rate**: Percentage of successful pings in the window (e.g., "95.0%")
- **Sample Count**: Number of successful vs total samples (e.g., "57/60")
- **Average RTT**: Average round-trip time in milliseconds (e.g., "12.5 ms")
- **Last Check**: Timestamp of most recent ping (displayed in JST)
- **Timeline**: 60-second visualization with color-coded tiles:
  - 🟩 Green tile: Successful ping
  - 🟥 Red tile: Failed ping
  - ⬜ Gray tile: No data for that second
  - Timeline flows left (oldest) to right (newest)

### Interpretation:
- Consistent green timeline indicates stable connectivity
- Intermittent red tiles suggest network instability
- Complete red timeline indicates device is unreachable
- Gray tiles at the beginning are normal for newly started collector

---

## 3. Command Output Tabs

Commands are organized into tabs, with one tab per unique command configured in the system.

### Features:
- **Tab Organization**: Each tab is labeled with the command text (e.g., "show version", "show interfaces status")
- **Tab Ordering**: Controlled by `sort_order` in configuration file
- **Active Tab Highlight**: Currently selected tab is visually distinguished
- **Click to Switch**: Click any tab to view that command's output across all devices

### Example Tabs:
- `show version` - Device software and hardware information
- `show interfaces status` - Interface operational status
- `show ip interface brief` - IP address configuration summary

---

## 4. Run History Display

Within each command tab, outputs are displayed per device with full execution history.

### Display Structure:

Each device section shows:

**Device Header**: Device name in bold

**Run Entries** (newest first):
Each run entry displays:

- **Timestamp**: Execution time in JST (e.g., "2024-01-09 21:15:30")
- **Duration Badge**: Execution time in milliseconds (e.g., "234 ms")
- **Status Badge**:
  - ✅ Success: Command completed successfully
  - ❌ Error: Command failed (shows error message)
- **Filter Badge**: 🔍 Filtered - Output matched exclusion pattern (hidden by default)
- **Truncate Badge**: ✂️ Truncated - Output exceeded max line limit
- **Line Count**: Shows original vs displayed line count (e.g., "Original: 150 lines → Showing: 100 lines")

**Output Display**:
- Click run header to expand/collapse output
- Output shown in monospace font for readability
- Preserves original formatting and whitespace
- Error messages displayed in red text

---

## 5. Diff Views

The interface provides two types of diff comparisons to identify changes in network device states.

### 5.1 Historical Diff (Previous vs Latest)

Compares the two most recent runs for the same device and command.

**Features**:
- **Button**: "Show Previous vs Latest" (appears when ≥2 runs exist)
- **Comparison Labels**: 
  - Left column: "Previous" (older run with timestamp)
  - Right column: "Latest" (newer run with timestamp)
- **Color Coding**:
  - 🟩 Green background: Lines added in latest run
  - 🟥 Red background: Lines removed from previous run
  - 🟨 Yellow background: Diff hunk headers (line numbers)
  - White background: Unchanged context lines

**Use Cases**:
- Detect configuration changes
- Identify new or removed interfaces
- Track version updates
- Monitor routing table changes

### 5.2 Cross-Device Diff (Device A vs Device B)

Compares outputs between two different devices for the same command.

**Features**:
- **Button**: "Show Device Diff" with device selector dropdowns
- **Device Selection**: Choose which two devices to compare
- **Comparison Labels**: Shows device names as column headers
- **Same Color Coding**: Green (added), Red (removed), Yellow (headers)

**Use Cases**:
- Verify configuration consistency across devices
- Identify discrepancies in redundant setups
- Compare active/standby device states
- Audit configuration standards compliance

### Diff Display Format:

Both diff types use side-by-side HTML table format:
- **Two-column layout**: Left and right comparison
- **Line numbers**: Displayed for each column
- **Synchronized scrolling**: Corresponding lines aligned horizontally
- **Full output**: Shows complete diff (not truncated)
- **Empty diff**: If outputs are identical, shows message "Outputs are identical"

---

## Technical Details

### Auto-Refresh Behavior

The interface polls two endpoints at different intervals:

- **Command Runs**: Polls `/api/runs/{command}` every `max(1, floor(interval_seconds/2))` seconds
- **Ping Status**: Polls `/api/ping` every `ping_interval_seconds`

Both intervals are configured in `config.yaml` and automatically retrieved by the frontend via `/api/config`.

### Timezone Display

- All timestamps stored in database as UTC epoch seconds
- Frontend converts to JST (UTC+9) for display
- Conversion happens client-side using JavaScript `Date` object

### Data Freshness

- "Last Check" timestamps indicate when data was last collected
- Stale data can occur if collector is stopped
- Check collector logs if timestamps stop updating

---

## Navigation Tips

1. **Quick Status Check**: Glance at Device Connectivity panel for overall health
2. **Investigate Issues**: Click failed device in ping panel → Check command tabs for error details
3. **Track Changes**: Use "Previous vs Latest" diff to see what changed since last run
4. **Verify Consistency**: Use "Device Diff" to compare configurations between devices
5. **Freeze Display**: Pause auto-refresh when analyzing complex outputs
6. **Force Update**: Use "Refresh Now" to immediately pull latest data

---

## Responsive Design

The interface is optimized for desktop viewing but adapts to different screen sizes:
- Tabs wrap on narrow screens
- Diff tables provide horizontal scrolling
- Ping timeline tiles scale to available width

---

## Related Documentation

- **English README**: [README.md](../README.md)
- **Japanese README**: [README.ja.md](../README.ja.md)
- **Configuration Guide**: See "Configuration" section in README files
- **API Documentation**: FastAPI auto-generated docs at `/docs` endpoint
